import uuid
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.project import Project
from app.models.script import Script, Scene
from app.models.plot_flag import PlotFlag
from app.schemas.script import (
    ScriptResponse,
    ScriptParseResponse,
    ScriptGenerateRequest,
    ScriptGenerateResponse,
    ScriptUpdateRequest,
    ScriptAnalyzeResponse,
)
from app.services.script_parser import ScriptParser
from app.services.script_structurer import ScriptStructurer
from app.services.script_generator import ScriptGenerator
from app.services.guardrails import InputSanitizer
from app.services.usage_tracker import track_project
from app.graph.sync import sync_scenes
from app.mcp_tools.registry import get_tool
from app.websocket.emitter import emit

from app.deps import get_current_user

router = APIRouter(prefix="/api/script", tags=["script"],
                   # every pipeline endpoint requires a signed-in user
                   dependencies=[Depends(get_current_user)])


@router.post("/parse", response_model=ScriptParseResponse)
async def parse_script(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    content = await file.read()
    parser = ScriptParser()
    try:
        raw_text = parser.parse_bytes(content, file.filename)
    except ValueError as e:
        # the parser's messages are user-facing (legacy .doc, scanned PDF,
        # unsupported extension) — surface them instead of an opaque 500
        raise HTTPException(status_code=400, detail=str(e))

    emit("stage:progress", {"stage": "script", "status": "started",
         "agent": "Screenwriter", "label": "Reading your imported script"}, project_id)
    from app.websocket.tool_events import tool_run
    structurer = ScriptStructurer()
    with track_project(project_id, db):
        with tool_run(project_id, "script", "structure_scenes", "Screenwriter") as tb:
            # an import has no request.language — read it off the script itself,
            # or a zh screenplay structures in en mode (summaries/rosters drift)
            from app.services.language import detect_language
            structured = await structurer.structure(
                raw_text, language=detect_language(raw_text))
            tb["artifact"] = f"{len(structured.get('scenes', []))} scenes"
    emit("stage:progress", {"stage": "script", "status": "completed", "agent": "Screenwriter",
         "label": f"Imported: {len(structured.get('scenes', []))} scene(s) found"}, project_id)

    script = Script(
        project_id=uuid.UUID(project_id),
        raw_text=raw_text,
        structured_json=structured,
    )
    db.add(script)
    db.flush()  # assign script.id before creating scenes

    scene_uuids = {}
    for scene_data in structured.get("scenes", []):
        scene = Scene(
            script_id=script.id,
            number=scene_data.get("scene_number", 0),
            title=scene_data.get("heading", ""),
            heading=scene_data.get("heading", ""),
            location=scene_data.get("location", ""),
            time_of_day=scene_data.get("time_of_day", ""),
            characters_json=scene_data.get("characters_present", []),
            description=scene_data.get("summary", ""),
            emotional_beat=scene_data.get("emotional_beat", ""),
            dialogue_json=scene_data.get("dialogue_lines", []),
            stage_directions=scene_data.get("stage_directions", []),
        )
        db.add(scene)
        scene_uuids[scene.number] = str(scene.id)

    db.commit()
    db.refresh(script)
    from app.websocket.tool_events import tool_event
    tool_event(project_id, "script", "write_script_db", "succeeded",
               agent="Screenwriter", artifact=f"{len(scene_uuids)} rows")

    sync_scenes(str(script.project_id), structured, scene_uuids=scene_uuids)

    return ScriptParseResponse(
        script_id=script.id,
        raw_text=raw_text,
        structured_json=structured,
        characters_mentioned=structured.get("characters_mentioned", []),
    )


@router.post("/generate", response_model=ScriptGenerateResponse)
async def generate_script(
    request: ScriptGenerateRequest,
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == request.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    from app.services.guardrails import PREMISE_MAX
    clean_premise = InputSanitizer().sanitize(request.premise, max_length=PREMISE_MAX)

    pid = str(request.project_id)
    emit("stage:progress", {"stage": "script", "status": "started",
         "agent": "Screenwriter",
         "label": ("Rewriting with the judge's notes"
                   if (request.notes or "").strip() else "Writing your screenplay")}, pid)
    generator = ScriptGenerator()
    from app.websocket.tool_events import tool_run
    from app.services.story_developer import StoryDeveloper
    try:
        with track_project(request.project_id, db):
            # develop the premise into a dramatic spine BEFORE writing — but
            # only on a first write, never on a judge-note revision (we already
            # have a shaped story then)
            development = ""
            if not (request.notes or "").strip():
                with tool_run(pid, "script", "develop_story", "Screenwriter") as tb:
                    treatment = await StoryDeveloper().develop(
                        premise=clean_premise, genre=request.genre, tone=request.tone,
                        episode_count=request.episode_count, language=request.language)
                    development = StoryDeveloper.as_brief(treatment)
                    tb["artifact"] = StoryDeveloper.headline(treatment)
            with tool_run(pid, "script", "llm_write", "Screenwriter") as tb:
                raw_text = await generator.generate(
                    genre=request.genre,
                    premise=clean_premise,
                    tone=request.tone,
                    episode_count=request.episode_count,
                    target_length=request.target_length,
                    notes=request.notes or "",
                    language=request.language,
                    model=request.model,
                    development=development,
                )
                tb["artifact"] = "1 draft"

            emit("stage:progress", {"stage": "script", "status": "update",
                 "agent": "Screenwriter", "label": "Structuring scenes and beats"}, pid)
            structurer = ScriptStructurer()
            with tool_run(pid, "script", "structure_scenes", "Screenwriter") as tb:
                structured = await structurer.structure(raw_text, language=request.language)
                tb["artifact"] = f"{len(structured.get('scenes', []))} scenes"
            # dialogue-budget ENFORCEMENT, same as the full-auto path: one trim
            # rewrite when the draft overshoots the line budget the prompt set
            from app.services.script_generator import (
                over_line_budget, count_dialogue_lines, trim_note)
            budget = over_line_budget(structured, request.target_length)
            if budget is not None:
                n_lines = count_dialogue_lines(structured)
                emit("stage:progress", {"stage": "script", "status": "update",
                     "agent": "Screenwriter",
                     "label": f"Draft runs long ({n_lines} lines), trimming to {budget}"}, pid)
                with tool_run(pid, "script", "trim_dialogue", "Screenwriter") as tb:
                    raw_text = await generator.generate(
                        genre=request.genre,
                        premise=clean_premise,
                        tone=request.tone,
                        episode_count=request.episode_count,
                        target_length=request.target_length,
                        notes=trim_note(n_lines, budget, request.target_length),
                        language=request.language,
                        model=request.model,
                        development=development,
                    )
                    structured = await structurer.structure(raw_text, language=request.language)
                    tb["artifact"] = f"{count_dialogue_lines(structured)} lines"
    except Exception:
        emit("stage:progress", {"stage": "script", "status": "failed",
             "agent": "Screenwriter", "label": "Script generation failed"}, pid)
        raise

    script = Script(
        project_id=request.project_id,
        raw_text=raw_text,
        structured_json=structured,
    )
    db.add(script)
    db.flush()  # assign script.id before creating scenes

    scene_uuids = {}
    for scene_data in structured.get("scenes", []):
        scene = Scene(
            script_id=script.id,
            number=scene_data.get("scene_number", 0),
            title=scene_data.get("heading", ""),
            heading=scene_data.get("heading", ""),
            location=scene_data.get("location", ""),
            time_of_day=scene_data.get("time_of_day", ""),
            characters_json=scene_data.get("characters_present", []),
            description=scene_data.get("summary", ""),
            emotional_beat=scene_data.get("emotional_beat", ""),
            dialogue_json=scene_data.get("dialogue_lines", []),
            stage_directions=scene_data.get("stage_directions", []),
        )
        db.add(scene)
        scene_uuids[scene.number] = str(scene.id)

    project.genre = request.genre
    project.premise = request.premise
    # The create modal only asks for a name now — an unnamed drama takes its
    # title from the premise once a real script exists.
    if (project.title or "").strip().lower() in ("", "untitled drama"):
        try:
            from app.routers.projects import _clean_title, _llm_title
            with track_project(str(request.project_id), db):
                suggested = _clean_title(await _llm_title(request.premise))
            if suggested:
                project.title = suggested
        except Exception:  # noqa: BLE001
            pass
    db.commit()
    db.refresh(script)
    from app.websocket.tool_events import tool_event
    tool_event(pid, "script", "write_script_db", "succeeded",
               agent="Screenwriter", artifact=f"{len(scene_uuids)} rows")

    sync_scenes(str(script.project_id), structured, scene_uuids=scene_uuids)

    emit("stage:progress", {"stage": "script", "status": "completed", "agent": "Screenwriter",
         "label": f"Script ready: {len(structured.get('scenes', []))} scene(s)"}, pid)

    return ScriptGenerateResponse(
        script_id=script.id,
        raw_text=raw_text,
        structured_json=structured,
        characters_mentioned=structured.get("characters_mentioned", []),
    )


@router.get("/project/{project_id}/latest", response_model=ScriptResponse)
async def latest_script_for_project(project_id: str, db: Session = Depends(get_db)):
    """The most recent script for a project, so opening an existing project can
    resume straight into the editor instead of a blank 'write a script' screen."""
    script = (
        db.query(Script)
        .filter(Script.project_id == uuid.UUID(project_id))
        .order_by(Script.created_at.desc())
        .first()
    )
    if not script:
        raise HTTPException(status_code=404, detail="No script for project")
    return script


@router.get("/{script_id}", response_model=ScriptResponse)
async def get_script(script_id: str, db: Session = Depends(get_db)):
    script = db.query(Script).filter(Script.id == uuid.UUID(script_id)).first()
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    return script


@router.patch("/{script_id}", response_model=ScriptResponse)
async def update_script(
    script_id: str,
    request: ScriptUpdateRequest,
    db: Session = Depends(get_db),
):
    script = db.query(Script).filter(Script.id == uuid.UUID(script_id)).first()
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")

    if request.raw_text is not None:
        script.raw_text = request.raw_text
        script.version += 1

    db.commit()
    db.refresh(script)
    return script


@router.post("/{script_id}/analyze", response_model=ScriptAnalyzeResponse)
async def analyze_script(script_id: str, db: Session = Depends(get_db)):
    script = db.query(Script).filter(Script.id == uuid.UUID(script_id)).first()
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    if not script.structured_json:
        raise HTTPException(status_code=400, detail="Script has no structured data")

    # Call the shared tool registry — same code path the MCP server serves.
    from app.websocket.tool_events import tool_run
    with track_project(script.project_id, db):
        with tool_run(script.project_id, "script", "plot_gap_check", "Story Analyst") as tb:
            gaps = await get_tool("plot_gap_detector")({"script": script.structured_json})
            tb["artifact"] = f"{len(gaps.get('flags', []))} flags"
        with tool_run(script.project_id, "script", "ending_engine", "Story Analyst") as tb:
            ending = await get_tool("ending_engine")({"script": script.structured_json})
            tb["artifact"] = f"{len((ending or {}).get('variants', []) or (ending or {}).get('options', []) or [])} endings" if isinstance(ending, dict) else None

    # Persist plot flags so they can be acknowledged/dismissed later.
    # Re-running analysis replaces any previously stored flags for this script.
    db.query(PlotFlag).filter(PlotFlag.script_id == script.id).delete()
    saved_flags = []
    for flag in gaps.get("flags", []):
        db_flag = PlotFlag(
            script_id=script.id,
            flag_type=flag.get("flag_type", "PACING_ISSUE"),
            severity=flag.get("severity", "MINOR"),
            scene_number=flag.get("scene_number"),
            description=flag.get("description", ""),
            evidence=flag.get("evidence"),
            suggestion=flag.get("suggestion"),
            status="OPEN",
        )
        db.add(db_flag)
        saved_flags.append(db_flag)
    db.commit()

    # Return flags with their real DB ids so the frontend can dismiss them.
    gaps["flags"] = [
        {
            "id": str(f.id),
            "flag_type": f.flag_type,
            "severity": f.severity,
            "scene_number": f.scene_number,
            "description": f.description,
            "evidence": f.evidence,
            "suggestion": f.suggestion,
            "status": f.status,
        }
        for f in saved_flags
    ]

    return ScriptAnalyzeResponse(plot_gaps=gaps, ending=ending)


@router.patch("/flags/{flag_id}")
async def update_flag(flag_id: str, request: dict, db: Session = Depends(get_db)):
    flag = db.query(PlotFlag).filter(PlotFlag.id == uuid.UUID(flag_id)).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    new_status = request.get("status")
    if new_status in {"OPEN", "ACKNOWLEDGED", "FIXED", "DISMISSED"}:
        flag.status = new_status
    db.commit()
    return {"flag_id": str(flag.id), "status": flag.status}


@router.post("/{script_id}/judge")
async def judge_script(script_id: str, db: Session = Depends(get_db)):
    script = db.query(Script).filter(Script.id == uuid.UUID(script_id)).first()
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    if not script.structured_json:
        raise HTTPException(status_code=400, detail="Script has no structured data")

    from app.websocket.tool_events import tool_run
    with track_project(script.project_id, db):
        with tool_run(script.project_id, "script", "narrative_judge", "Story Analyst") as t:
            verdict = await get_tool("narrative_judge")({"script": script.structured_json})
            t["artifact"] = f"scored {len((verdict or {}).get('scores', {}))} axes"
        return verdict

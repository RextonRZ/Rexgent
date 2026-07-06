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

router = APIRouter(prefix="/api/script", tags=["script"])


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
    raw_text = parser.parse_bytes(content, file.filename)

    emit("stage:progress", {"stage": "script", "status": "started",
         "agent": "Screenwriter", "label": "Reading your imported script"}, project_id)
    structurer = ScriptStructurer()
    with track_project(project_id, db):
        structured = await structurer.structure(raw_text)
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

    clean_premise = InputSanitizer().sanitize(request.premise, max_length=300)

    pid = str(request.project_id)
    emit("stage:progress", {"stage": "script", "status": "started",
         "agent": "Screenwriter", "label": "Writing your screenplay"}, pid)
    generator = ScriptGenerator()
    try:
        with track_project(request.project_id, db):
            raw_text = await generator.generate(
                genre=request.genre,
                premise=clean_premise,
                tone=request.tone,
                episode_count=request.episode_count,
                target_length=request.target_length,
                notes=request.notes or "",
                language=request.language,
                model=request.model,
            )

            emit("stage:progress", {"stage": "script", "status": "update",
                 "agent": "Screenwriter", "label": "Structuring scenes and beats"}, pid)
            structurer = ScriptStructurer()
            structured = await structurer.structure(raw_text, language=request.language)
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
    db.commit()
    db.refresh(script)

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
    with track_project(script.project_id, db):
        gaps = await get_tool("plot_gap_detector")({"script": script.structured_json})
        ending = await get_tool("ending_engine")({"script": script.structured_json})

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

    with track_project(script.project_id, db):
        return await get_tool("narrative_judge")({"script": script.structured_json})

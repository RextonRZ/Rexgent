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
from app.mcp_tools.plot_gap_detector import PlotGapDetector
from app.mcp_tools.ending_engine import EndingEngine

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

    structurer = ScriptStructurer()
    structured = await structurer.structure(raw_text)

    script = Script(
        project_id=uuid.UUID(project_id),
        raw_text=raw_text,
        structured_json=structured,
    )
    db.add(script)
    db.flush()  # assign script.id before creating scenes

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

    db.commit()
    db.refresh(script)

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

    generator = ScriptGenerator()
    raw_text = await generator.generate(
        genre=request.genre,
        premise=request.premise,
        tone=request.tone,
        episode_count=request.episode_count,
        target_length=request.target_length,
        notes=request.notes or "",
    )

    structurer = ScriptStructurer()
    structured = await structurer.structure(raw_text)

    script = Script(
        project_id=request.project_id,
        raw_text=raw_text,
        structured_json=structured,
    )
    db.add(script)
    db.flush()  # assign script.id before creating scenes

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

    project.genre = request.genre
    project.premise = request.premise
    db.commit()
    db.refresh(script)

    return ScriptGenerateResponse(
        script_id=script.id,
        raw_text=raw_text,
        structured_json=structured,
        characters_mentioned=structured.get("characters_mentioned", []),
    )


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

    detector = PlotGapDetector()
    gaps = await detector.detect(script.structured_json)

    engine = EndingEngine()
    ending = await engine.analyse(script.structured_json)

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

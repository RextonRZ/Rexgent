import uuid
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.project import Project
from app.models.script import Script, Scene
from app.schemas.script import ScriptResponse, ScriptParseResponse, ScriptGenerateRequest, ScriptGenerateResponse, ScriptUpdateRequest
from app.services.script_parser import ScriptParser
from app.services.script_structurer import ScriptStructurer
from app.services.script_generator import ScriptGenerator

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

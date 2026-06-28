import uuid
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.project import Project
from app.models.script import Script, Scene
from app.schemas.script import ScriptResponse, ScriptParseResponse
from app.services.script_parser import ScriptParser
from app.services.script_structurer import ScriptStructurer

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


@router.get("/{script_id}", response_model=ScriptResponse)
async def get_script(script_id: str, db: Session = Depends(get_db)):
    script = db.query(Script).filter(Script.id == uuid.UUID(script_id)).first()
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    return script

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.script import Script, Scene
from app.models.shot import Shot
from app.models.character import Character
from app.schemas.shot import ShotResponse
from app.services.storyboard_generator import StoryboardGenerator, plan_shot_budget

router = APIRouter(prefix="/api/storyboard", tags=["storyboard"])


@router.post("/generate")
async def generate_storyboard(request: dict, db: Session = Depends(get_db)):
    project_id = request.get("project_id")
    script_id = request.get("script_id")
    target_length = int(request.get("target_length", 30))  # seconds

    if script_id:
        script = db.query(Script).filter(Script.id == uuid.UUID(script_id)).first()
    elif project_id:
        script = (
            db.query(Script)
            .filter(Script.project_id == uuid.UUID(project_id))
            .order_by(Script.created_at.desc())
            .first()
        )
    else:
        raise HTTPException(status_code=400, detail="script_id or project_id is required")

    if not script or not script.structured_json:
        raise HTTPException(status_code=404, detail="Script not found")

    scenes = db.query(Scene).filter(Scene.script_id == script.id).order_by(Scene.number).all()
    if not scenes:
        raise HTTPException(status_code=400, detail="Script has no scenes")

    characters = db.query(Character).filter(Character.project_id == script.project_id).all()
    char_map = {
        c.name.upper(): {
            "name": c.name,
            "role": c.role,
            "visual_description": c.visual_description or "",
        }
        for c in characters
    }

    # Replace existing shots for these scenes (re-generation).
    scene_ids = [s.id for s in scenes]
    db.query(Shot).filter(Shot.scene_id.in_(scene_ids)).delete(synchronize_session=False)

    shots_per_scene, shot_seconds = plan_shot_budget(len(scenes), target_length)
    generator = StoryboardGenerator()
    all_shots = []

    for scene in scenes:
        scene_chars = [
            char_map.get(str(name).upper(), {"name": name})
            for name in (scene.characters_json or [])
        ]
        scene_data = {
            "scene_number": scene.number,
            "heading": scene.heading,
            "description": scene.description,
            "emotional_beat": scene.emotional_beat,
        }

        shots_data = await generator.generate_for_scene(
            scene_data, scene_chars,
            max_shots=shots_per_scene, shot_seconds=shot_seconds,
        )

        for shot_data in shots_data:
            shot = Shot(
                scene_id=scene.id,
                number=shot_data.get("shot_number", 1),
                shot_type=shot_data.get("shot_type"),
                camera_movement=shot_data.get("camera_movement"),
                lighting=shot_data.get("lighting"),
                colour_mood=shot_data.get("colour_mood"),
                action=shot_data.get("action"),
                dialogue=shot_data.get("dialogue"),
                emotional_beat=shot_data.get("emotional_beat"),
                estimated_duration_seconds=shot_data.get("estimated_duration_seconds", 5),
                characters_in_frame=shot_data.get("characters_in_frame", []),
                notes=shot_data.get("notes"),
            )
            db.add(shot)
            all_shots.append(shot)

    db.commit()
    for s in all_shots:
        db.refresh(s)

    return {
        "total_shots": len(all_shots),
        "shots": [ShotResponse.model_validate(s) for s in all_shots],
    }


@router.get("/project/{project_id}")
async def list_shots(project_id: str, db: Session = Depends(get_db)):
    script = (
        db.query(Script)
        .filter(Script.project_id == uuid.UUID(project_id))
        .order_by(Script.created_at.desc())
        .first()
    )
    if not script:
        return {"scenes": []}

    scenes = db.query(Scene).filter(Scene.script_id == script.id).order_by(Scene.number).all()
    result = []
    for scene in scenes:
        shots = db.query(Shot).filter(Shot.scene_id == scene.id).order_by(Shot.number).all()
        result.append({
            "scene_number": scene.number,
            "heading": scene.heading,
            "shots": [ShotResponse.model_validate(s).model_dump() for s in shots],
        })
    return {"scenes": result}


@router.patch("/{shot_id}", response_model=ShotResponse)
async def update_shot(shot_id: str, updates: dict, db: Session = Depends(get_db)):
    shot = db.query(Shot).filter(Shot.id == uuid.UUID(shot_id)).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")
    allowed = {
        "shot_type", "camera_movement", "lighting", "colour_mood", "action",
        "dialogue", "emotional_beat", "estimated_duration_seconds",
        "characters_in_frame", "notes", "director_note", "quality_tier",
    }
    for key, value in updates.items():
        if key in allowed:
            setattr(shot, key, value)
    db.commit()
    db.refresh(shot)
    return shot


@router.delete("/{shot_id}")
async def delete_shot(shot_id: str, db: Session = Depends(get_db)):
    shot = db.query(Shot).filter(Shot.id == uuid.UUID(shot_id)).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")
    db.delete(shot)
    db.commit()
    return {"deleted": shot_id}

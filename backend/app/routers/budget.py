import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.script import Script, Scene
from app.models.shot import Shot
from app.mcp_tools.token_optimizer import TokenOptimizer

router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.post("/calculate")
async def calculate_budget(request: dict, db: Session = Depends(get_db)):
    project_id = request.get("project_id")
    budget = request.get("budget_usd", 40.0)
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id required")

    script = (
        db.query(Script)
        .filter(Script.project_id == uuid.UUID(project_id))
        .order_by(Script.created_at.desc())
        .first()
    )
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")

    scenes = db.query(Scene).filter(Scene.script_id == script.id).all()
    scene_ids = [s.id for s in scenes]
    shots = db.query(Shot).filter(Shot.scene_id.in_(scene_ids)).order_by(Shot.number).all()

    shots_data = [{
        "shot_id": str(s.id),
        "shot_type": s.shot_type,
        "emotional_beat": s.emotional_beat,
        "characters_in_frame": s.characters_in_frame or [],
        "dialogue": s.dialogue,
        "estimated_duration_seconds": s.estimated_duration_seconds,
    } for s in shots]

    optimizer = TokenOptimizer()
    result = optimizer.allocate(shots_data, budget)

    # Persist the assigned tier back onto each shot.
    tier_by_id = {s["shot_id"]: s["quality_tier"] for s in result["scored_shots"]}
    for shot in shots:
        tier = tier_by_id.get(str(shot.id))
        if tier:
            shot.quality_tier = tier
    db.commit()

    return result

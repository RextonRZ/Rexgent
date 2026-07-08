import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.script import Script, Scene
from app.models.shot import Shot
from app.mcp_tools.token_optimizer import TokenOptimizer
from app.services.usage_tracker import global_usage
from app.services.cost_ledger import aggregate

from app.deps import get_current_user

router = APIRouter(prefix="/api/budget", tags=["budget"],
                   # every pipeline endpoint requires a signed-in user
                   dependencies=[Depends(get_current_user)])


@router.post("/calculate")
async def calculate_budget(request: dict, db: Session = Depends(get_db)):
    project_id = request.get("project_id")
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id required")

    budget = request.get("budget_usd")
    if budget is None:
        from app.models.project import Project
        project = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
        budget = float(project.credit_budget) if project and project.credit_budget else 40.0

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
    scene_number_by_id = {s.id: s.number for s in scenes}
    shots = db.query(Shot).filter(Shot.scene_id.in_(scene_ids)).order_by(Shot.number).all()

    shots_data = [{
        "shot_id": str(s.id),
        "shot_number": s.number,
        "shot_type": s.shot_type,
        "scene_number": scene_number_by_id.get(s.scene_id),
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

    # LLM tokens/cost from THIS drama's ledger (all models, all entry paths);
    # the in-memory tracker only covers calls that never had a project set.
    agg = aggregate(db, project_id, budget)
    ledger_llm = agg.get("llm") or {}
    if ledger_llm.get("total_tokens"):
        llm = {"input_tokens": ledger_llm["input_tokens"],
               "output_tokens": ledger_llm["output_tokens"],
               "cost_usd": round(agg["by_category"].get("llm", 0.0), 4)}
        result["llm_by_model"] = ledger_llm.get("by_model", {})
    else:
        llm = global_usage().snapshot()
    # Plates (image) and voice (tts) are already-spent ledger costs — the
    # projection must include them or the total understates the drama.
    image_usd = round(agg["by_category"].get("image", 0.0), 4)
    tts_usd = round(agg["by_category"].get("tts", 0.0), 4)
    video_cost = result["video_cost_usd"]
    grand_total = round(video_cost + llm["cost_usd"] + image_usd + tts_usd, 2)
    result["llm"] = llm
    result["llm_cost_usd"] = llm["cost_usd"]
    result["image_cost_usd"] = image_usd
    result["tts_cost_usd"] = tts_usd
    result["grand_total_cost"] = grand_total
    result["within_budget"] = grand_total <= budget

    return result


@router.get("/ledger/{project_id}")
def ledger(project_id: str, db: Session = Depends(get_db)):
    return aggregate(db, project_id)

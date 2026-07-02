import uuid
from app.models.cost_event import CostEvent
from app.services.cost_rates import video_cost, image_cost, tts_cost, llm_cost
from app.websocket.emitter import emit


def _as_uuid(project_id):
    """Best-effort coercion to a real UUID; falls back to the raw value
    (e.g. plain test ids) so callers/tests aren't forced onto real UUIDs."""
    try:
        return uuid.UUID(str(project_id))
    except (ValueError, AttributeError, TypeError):
        return project_id


def record(db, project_id, category, stage, unit, quantity, amount_usd, ref_id=None):
    ev = CostEvent(project_id=_as_uuid(project_id), category=category, stage=stage,
                   unit=unit, quantity=quantity, amount_usd=amount_usd, ref_id=ref_id)
    db.add(ev)
    db.commit()
    emit("cost:updated", aggregate(db, project_id), str(project_id))
    return amount_usd


def aggregate(db, project_id, budget=40.0) -> dict:
    rows = db.query(CostEvent).filter(CostEvent.project_id == _as_uuid(project_id)).all()
    by_cat: dict = {}
    by_stage: dict = {}
    for r in rows:
        by_cat[r.category] = round(by_cat.get(r.category, 0.0) + (r.amount_usd or 0.0), 4)
        if r.stage:
            by_stage[r.stage] = round(by_stage.get(r.stage, 0.0) + (r.amount_usd or 0.0), 4)
    grand = round(sum(by_cat.values()), 4)
    return {"by_category": by_cat, "by_stage": by_stage, "grand_total": grand,
            "budget": budget, "within_budget": grand <= budget,
            "remaining": round(budget - grand, 4)}


def record_video(db, project_id, seconds, model, ref_id=None):
    return record(db, project_id, "video", "generation", "second", seconds,
                  video_cost(seconds, model), ref_id)


def record_image(db, project_id, n=1, stage="casting"):
    return record(db, project_id, "image", stage, "image", n, image_cost(n))


def record_tts(db, project_id, chars):
    return record(db, project_id, "tts", "audio", "char", chars, tts_cost(chars))


def record_llm(db, project_id, in_tokens, out_tokens, stage="script"):
    return record(db, project_id, "llm", stage, "tokens", in_tokens + out_tokens,
                  llm_cost(in_tokens, out_tokens))

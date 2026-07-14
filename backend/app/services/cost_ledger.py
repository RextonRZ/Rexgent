import uuid
from app.models.cost_event import CostEvent
from app.services.cost_rates import video_cost, image_cost, llm_cost
from app.websocket.emitter import emit


def _as_uuid(project_id):
    """Best-effort coercion to a real UUID; falls back to the raw value
    (e.g. plain test ids) so callers/tests aren't forced onto real UUIDs."""
    try:
        return uuid.UUID(str(project_id))
    except (ValueError, AttributeError, TypeError):
        return project_id


def record(db, project_id, category, stage, unit, quantity, amount_usd, ref_id=None,
           model=None, input_tokens=None, output_tokens=None):
    ev = CostEvent(project_id=_as_uuid(project_id), category=category, stage=stage,
                   unit=unit, quantity=quantity, amount_usd=amount_usd, ref_id=ref_id,
                   model=model, input_tokens=input_tokens, output_tokens=output_tokens)
    db.add(ev)
    db.commit()
    # Distinct event name: the aggregate payload here differs from the generation
    # runner's legacy `cost:updated` ({current_cost, budget_remaining}), which the
    # old CostTracker/store still consume. Keep them separate to avoid shape clashes.
    emit("ledger:updated", aggregate(db, project_id), str(project_id))
    return amount_usd


def aggregate(db, project_id, budget=None) -> dict:
    if budget is None:
        # read this drama's budget; fall back to the historical default
        try:
            from app.models.project import Project
            project = db.query(Project).filter(Project.id == _as_uuid(project_id)).first()
            budget = float(project.credit_budget) if project and project.credit_budget else 40.0
        except Exception:  # noqa: BLE001
            budget = 40.0
    rows = db.query(CostEvent).filter(CostEvent.project_id == _as_uuid(project_id)).all()
    by_cat: dict = {}
    by_stage: dict = {}
    llm_in = llm_out = llm_total = 0
    llm_by_model: dict = {}
    llm_tokens_by_stage: dict = {}
    media_models: dict = {}
    for r in rows:
        by_cat[r.category] = round(by_cat.get(r.category, 0.0) + (r.amount_usd or 0.0), 4)
        if r.stage:
            by_stage[r.stage] = round(by_stage.get(r.stage, 0.0) + (r.amount_usd or 0.0), 4)
        if r.category != "llm":
            # per-model media detail (video seconds, images, tts chars)
            m = getattr(r, "model", None) or "untracked"
            cat = media_models.setdefault(r.category, {})
            entry = cat.setdefault(m, {"qty": 0.0, "usd": 0.0})
            entry["qty"] = round(entry["qty"] + (r.quantity or 0.0), 2)
            entry["usd"] = round(entry["usd"] + (r.amount_usd or 0.0), 4)
        if r.category == "llm":
            ti = int(r.input_tokens or 0)
            to = int(r.output_tokens or 0)
            tq = int(r.quantity or 0) or (ti + to)
            llm_in += ti
            llm_out += to
            llm_total += tq
            m = (getattr(r, "model", None) or "qwen-max")
            entry = llm_by_model.setdefault(m, {"tokens": 0, "usd": 0.0})
            entry["tokens"] += tq
            entry["usd"] = round(entry["usd"] + (r.amount_usd or 0.0), 4)
            if r.stage:
                llm_tokens_by_stage[r.stage] = llm_tokens_by_stage.get(r.stage, 0) + tq
    grand = round(sum(by_cat.values()), 4)
    return {"by_category": by_cat, "by_stage": by_stage, "grand_total": grand,
            "media_models": media_models,
            "budget": budget, "within_budget": grand <= budget,
            "remaining": round(budget - grand, 4),
            "llm": {"input_tokens": llm_in, "output_tokens": llm_out,
                    "total_tokens": llm_total, "by_model": llm_by_model,
                    "tokens_by_stage": llm_tokens_by_stage}}


# tier keys -> the ledger's readable model names (usage analytics groups on these).
# wan_r2v and videoedit are Wan modes, so they group under the same "wan2.7"
# label as wan i2v.
VIDEO_MODEL_NAMES = {"wan": "wan2.7", "wan_r2v": "wan2.7", "videoedit": "wan2.7",
                     "happyhorse": "happyhorse-1.1"}


def record_video(db, project_id, seconds, model, ref_id=None, model_name=None):
    return record(db, project_id, "video", "generation", "second", seconds,
                  video_cost(seconds, model), ref_id,
                  model=model_name or VIDEO_MODEL_NAMES.get(model, model))


def record_image(db, project_id, n=1, stage="casting", model=None):
    return record(db, project_id, "image", stage, "image", n, image_cost(n),
                  model=model)


def record_llm(db, project_id, in_tokens, out_tokens, stage="script", model=None):
    from app.services.model_router import llm_cost_for
    amount = llm_cost_for(model, in_tokens, out_tokens) if model else llm_cost(in_tokens, out_tokens)
    return record(db, project_id, "llm", stage, "tokens", in_tokens + out_tokens,
                  amount, model=model, input_tokens=in_tokens, output_tokens=out_tokens)

"""Usage & analytics: cross-project aggregation for the dashboard.

One endpoint feeds the whole page. Everything is derived from data that
already exists — CostEvent rows (tokens, images, seconds, chars, USD),
GeneratedClip verdicts (continuity/retries/face) and FinalExport runtimes.
Aggregation runs in Python: event volumes are small and it keeps the math
identical across Postgres and the SQLite test database.
"""
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.cost_event import CostEvent
from app.models.generation_job import GenerationJob
from app.models.generated_clip import GeneratedClip
from app.models.final_export import FinalExport
from app.models.shot import Shot
from app.services.model_router import llm_cost_for

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# the all-premium counterfactual reprices every token at these models' rates
PREMIUM_MODELS = {"qwen-max", "qwen3-max", "qwen-vl-max"}


def _cutoff(range_key: str) -> datetime | None:
    days = {"7d": 7, "30d": 30}.get(range_key)
    return datetime.utcnow() - timedelta(days=days) if days else None


def summarize_events(events: list) -> dict:
    """Pure aggregation over CostEvent-shaped rows — unit-testable."""
    llm_by_model: dict = {}
    categories: dict = {}
    llm_usd = premium_usd = 0.0
    llm_tokens = cheap_tokens = 0
    for e in events:
        cat = categories.setdefault(e.category, {"usd": 0.0, "quantity": 0.0})
        cat["usd"] = round(cat["usd"] + (e.amount_usd or 0.0), 4)
        cat["quantity"] = round(cat["quantity"] + (e.quantity or 0.0), 2)
        if e.category != "llm":
            continue
        ti, to = int(e.input_tokens or 0), int(e.output_tokens or 0)
        tokens = int(e.quantity or 0) or (ti + to)
        model = e.model or "qwen-max"
        row = llm_by_model.setdefault(model, {"model": model, "tokens": 0, "usd": 0.0})
        row["tokens"] += tokens
        row["usd"] = round(row["usd"] + (e.amount_usd or 0.0), 4)
        llm_usd += e.amount_usd or 0.0
        llm_tokens += tokens
        # what this exact call would have cost on the premium model
        premium_usd += llm_cost_for("qwen-max", ti, to)
        if model not in PREMIUM_MODELS:
            cheap_tokens += tokens
    return {
        "categories": categories,
        "llm": {
            "total_tokens": llm_tokens,
            "total_usd": round(llm_usd, 4),
            "all_premium_usd": round(premium_usd, 4),
            "saved_usd": round(max(0.0, premium_usd - llm_usd), 4),
            "cheap_share": round(cheap_tokens / llm_tokens, 4) if llm_tokens else 0.0,
            "by_model": sorted(llm_by_model.values(),
                               key=lambda r: r["tokens"], reverse=True),
        },
    }


def summarize_clips(clips: list) -> dict:
    """Reliability + tier ratio from GeneratedClip-shaped rows."""
    total = len(clips)
    judged = [c for c in clips if c.status in ("APPROVED", "NEEDS_REVIEW")]
    passed = sum(1 for c in judged if c.status == "APPROVED")
    faces = [c.face_score for c in clips if c.face_score is not None]
    by_tier: dict = {}
    for c in clips:
        tier = (c.model_used or "happyhorse").lower()
        tier = "wan" if "wan" in tier else "happyhorse"
        row = by_tier.setdefault(tier, {"clips": 0, "retried": 0})
        row["clips"] += 1
        if (c.retries or 0) > 0:
            row["retried"] += 1
    for row in by_tier.values():
        row["retry_rate"] = round(row["retried"] / row["clips"], 4) if row["clips"] else 0.0
    return {
        "clips_total": total,
        "continuity_pass_rate": round(passed / len(judged), 4) if judged else None,
        "flagged": len(judged) - passed,
        "avg_face_score": round(sum(faces) / len(faces), 1) if faces else None,
        "by_tier": by_tier,
    }


@router.get("/usage")
def usage(
    range: str = "30d",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    projects = (db.query(Project)
                .filter(Project.user_id == str(current_user.id)).all())
    ids = [p.id for p in projects]
    title_by_id = {p.id: (p.title or "Untitled drama") for p in projects}
    project_by_id = {p.id: p for p in projects}
    cutoff = _cutoff(range)
    if not ids:
        empty_rel = summarize_clips([])
        empty_rel["flagged_samples"] = []
        empty_rel["retried_samples"] = []
        return {"range": range, "llm": summarize_events([])["llm"],
                "categories": {}, "dramas": [], "reliability": empty_rel,
                "hero_stills": [], "trend": []}

    q = db.query(CostEvent).filter(CostEvent.project_id.in_(ids))
    if cutoff:
        q = q.filter(CostEvent.created_at >= cutoff)
    events = q.all()
    summary = summarize_events(events)

    # ── per-drama spend + runtime of the finished film ──
    usd_by_project: dict = {}
    for e in events:
        usd_by_project[e.project_id] = round(
            usd_by_project.get(e.project_id, 0.0) + (e.amount_usd or 0.0), 4)
    runtime_by_project: dict = {}
    for ex in (db.query(FinalExport).filter(FinalExport.project_id.in_(ids))
               .order_by(FinalExport.created_at.asc()).all()):
        runtime_by_project[ex.project_id] = ex.duration_seconds  # latest wins

    cq = (db.query(GeneratedClip)
          .join(GenerationJob, GeneratedClip.job_id == GenerationJob.id)
          .filter(GenerationJob.project_id.in_(ids)))
    if cutoff:
        cq = cq.filter(GeneratedClip.created_at >= cutoff)
    clips = cq.all()
    clips_by_project: dict = {}
    job_project = {j.id: j.project_id for j in
                   db.query(GenerationJob).filter(GenerationJob.project_id.in_(ids)).all()}
    for c in clips:
        pid = job_project.get(c.job_id)
        if pid:
            clips_by_project[pid] = clips_by_project.get(pid, 0) + 1

    dramas = []
    for pid, usd in sorted(usd_by_project.items(), key=lambda kv: kv[1], reverse=True):
        runtime = runtime_by_project.get(pid)
        project = project_by_id.get(pid)
        dramas.append({
            "id": str(pid),
            "title": title_by_id.get(pid, "Untitled drama"),
            "poster_url": getattr(project, "poster_url", None),
            "genre": getattr(project, "genre", None),
            "usd": usd,
            "runtime_seconds": runtime,
            "clips": clips_by_project.get(pid, 0),
            "usd_per_min": round(usd / (runtime / 60), 2) if runtime else None,
        })

    # ── evidence footage: the clips BEHIND the reliability numbers ──
    def _samples(rows, limit):
        rows = sorted((c for c in rows if c.url),
                      key=lambda c: c.created_at or datetime.min, reverse=True)[:limit]
        shot_no = {s.id: s.number for s in
                   db.query(Shot).filter(Shot.id.in_([c.shot_id for c in rows])).all()} \
            if rows else {}
        return [{
            "url": c.url,
            "title": title_by_id.get(job_project.get(c.job_id), "Untitled drama"),
            "shot_number": shot_no.get(c.shot_id),
        } for c in rows]

    flagged_samples = _samples([c for c in clips if c.status == "NEEDS_REVIEW"], 4)
    retried_samples = _samples([c for c in clips if (c.retries or 0) > 0], 3)

    # a handful of recent posters for the routing hero's faint backdrop
    hero_stills = [p.poster_url for p in
                   sorted(projects, key=lambda p: p.created_at or datetime.min,
                          reverse=True) if p.poster_url][:6]

    # ── daily trend: spend + clip volume ──
    daily: dict = {}
    for e in events:
        day = e.created_at.date().isoformat() if e.created_at else None
        if not day:
            continue
        row = daily.setdefault(day, {"date": day, "usd": 0.0, "clips": 0})
        row["usd"] = round(row["usd"] + (e.amount_usd or 0.0), 4)
    for c in clips:
        day = c.created_at.date().isoformat() if c.created_at else None
        if day:
            daily.setdefault(day, {"date": day, "usd": 0.0, "clips": 0})["clips"] += 1

    reliability = summarize_clips(clips)
    reliability["flagged_samples"] = flagged_samples
    reliability["retried_samples"] = retried_samples

    return {
        "range": range,
        "llm": summary["llm"],
        "categories": summary["categories"],
        "dramas": dramas,
        "reliability": reliability,
        "hero_stills": hero_stills,
        "trend": sorted(daily.values(), key=lambda r: r["date"]),
    }

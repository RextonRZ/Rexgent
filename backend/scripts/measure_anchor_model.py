"""Anchor-model measurement harness (run manually — it spends render credit).

For each candidate anchor_ref_model, render an ALREADY-PREPARED project (script +
storyboard + casting done) and score the resulting clips, then print a scorecard
and the winner. Use the winner as `anchor_ref_model` in production.

Usage:  python backend/scripts/measure_anchor_model.py <project_id>
The harness turns on identity_routing_v2 for the run.
"""
import asyncio
import sys

CONFIGS = ["happyhorse", "wan"]


def collect_clip_scores(clips) -> list[dict]:
    """ORM clips -> plain score dicts for model_measurement.summarize."""
    return [{"face_score": c.face_score, "outfit_score": c.outfit_score,
             "consistency_score": c.consistency_score} for c in clips]


async def _render_under_config(db, project_id, anchor_model):
    from app.config import get_settings
    from app.services.generation_runner import GenerationRunner
    from app.models.generated_clip import GeneratedClip
    from app.models.generation_job import GenerationJob
    import uuid
    s = get_settings()
    s.identity_routing_v2 = True
    s.anchor_ref_model = anchor_model
    job = GenerationJob(project_id=uuid.UUID(project_id))
    db.add(job); db.commit(); db.refresh(job)
    await GenerationRunner(db).run_job(str(job.id))
    clips = db.query(GeneratedClip).filter(GeneratedClip.job_id == job.id).all()
    return collect_clip_scores(clips)


def main(project_id: str) -> None:
    from app.services.model_measurement import summarize, format_scorecard
    db = _open_session()
    try:
        results = []
        for cfg in CONFIGS:
            print(f"Rendering under anchor_ref_model={cfg} ...")
            clips = asyncio.run(_render_under_config(db, project_id, cfg))
            results.append({"config": cfg, **summarize(clips)})
        print()
        print(format_scorecard(results))
    finally:
        db.close()


def _open_session():
    """Open a DB session (the codebase exposes a session factory)."""
    from app.database import get_session_factory
    return get_session_factory()()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python backend/scripts/measure_anchor_model.py <project_id>")
        sys.exit(1)
    main(sys.argv[1])

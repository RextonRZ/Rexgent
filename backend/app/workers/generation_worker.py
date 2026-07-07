import asyncio
import logging
from app.workers.celery_app import celery_app
from app.database import get_session_factory
from app.services.generation_runner import GenerationRunner

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="run_generation_job")
def run_generation_job(self, job_id: str):
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        runner = GenerationRunner(db)
        asyncio.run(runner.run_job(job_id))
    except Exception as e:  # noqa: BLE001
        # surface the crash — otherwise the pipeline spinner sticks forever
        logger.error(f"Generation job {job_id} crashed: {e}")
        try:
            from app.models.generation_job import GenerationJob
            from app.websocket.emitter import emit
            import uuid as _uuid
            db.rollback()  # the session may hold a failed transaction
            job = (db.query(GenerationJob)
                   .filter(GenerationJob.id == _uuid.UUID(job_id)).first())
            if job:
                job.status = "FAILED"
                db.commit()
                emit("stage:progress", {"stage": "generate", "status": "failed",
                     "agent": "Renderer",
                     "label": f"Generation crashed: {str(e)[:120]}"},
                     str(job.project_id))
        except Exception:  # noqa: BLE001
            pass
        raise
    finally:
        db.close()

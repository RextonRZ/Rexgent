import asyncio
from app.workers.celery_app import celery_app
from app.database import get_session_factory
from app.services.generation_runner import GenerationRunner


@celery_app.task(bind=True, name="run_generation_job")
def run_generation_job(self, job_id: str):
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        runner = GenerationRunner(db)
        asyncio.run(runner.run_job(job_id))
    finally:
        db.close()

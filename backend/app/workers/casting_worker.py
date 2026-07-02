import asyncio
import uuid
from app.workers.celery_app import celery_app
from app.database import get_session_factory
from app.services.casting_director import CastingDirector


@celery_app.task(bind=True, name="run_casting_job")
def run_casting_job(self, project_id: str):
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        asyncio.run(CastingDirector(db).cast_bible(uuid.UUID(project_id)))
    finally:
        db.close()

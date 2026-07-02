import asyncio
import uuid
import logging
from app.workers.celery_app import celery_app
from app.database import get_session_factory
from app.services.casting_director import CastingDirector

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="run_casting_job")
def run_casting_job(self, project_id: str):
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        # Plate generation is the primary job — must succeed.
        asyncio.run(CastingDirector(db).cast_bible(uuid.UUID(project_id)))
        # Dialogue synthesis is best-effort: a TTS/model issue must NOT undo the plates.
        try:
            from app.agent.pipeline_ops import synth_dialogue_op
            asyncio.run(synth_dialogue_op(db, project_id))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Casting: dialogue synthesis skipped ({e})")
    finally:
        db.close()

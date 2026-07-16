import asyncio
import uuid
import logging
from app.workers.celery_app import celery_app
from app.database import get_session_factory
from app.services.casting_director import CastingDirector

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="run_casting_job")
def run_casting_job(self, project_id: str, design_voice: bool = True,
                    redesign_voice: bool = False, regen_plates: bool = True):
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        from app.services.api_keys import use_project_key
        use_project_key(db, project_id)  # bill the project owner's key
        # Plate generation is the primary job — must succeed. The spend
        # dialog's ticks ride along: design_voice (unticked, free presets),
        # redesign_voice (replace designed/preset voices) and regen_plates
        # (unticked, only cast members missing plates get painted).
        asyncio.run(CastingDirector(db).cast_bible(uuid.UUID(project_id),
                                                   design_voice=design_voice,
                                                   redesign_voice=redesign_voice,
                                                   regen_plates=regen_plates))
    except Exception as e:  # noqa: BLE001
        # surface the crash — otherwise the casting spinner sticks forever
        # (mirrors generation_worker's guard)
        logger.error(f"Casting job for {project_id} crashed: {e}")
        try:
            from app.websocket.emitter import emit
            emit("stage:progress", {"stage": "generate", "status": "failed",
                 "agent": "Casting",
                 "label": f"Casting crashed: {str(e)[:120]}"}, str(project_id))
        except Exception:  # noqa: BLE001
            pass
        raise
    finally:
        db.close()

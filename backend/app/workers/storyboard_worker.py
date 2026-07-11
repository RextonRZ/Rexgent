import asyncio
import logging
from app.workers.celery_app import celery_app
from app.database import get_session_factory

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="run_storyboard_job")
def run_storyboard_job(self, script_id: str, target_length: int = 30):
    """Board a script in the background. Boarding a multi-scene drama takes
    minutes (per-scene LLM staging + set dressing + location plates), far too
    long for one HTTP request — a browser hiccup used to CANCEL the request
    server-side and kill the board mid-scene with zero shots saved. The op
    already narrates itself over stage:progress and tool events, so the UI
    follows along and refreshes when the completed event lands."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        from app.agent.pipeline_ops import generate_storyboard_op
        asyncio.run(generate_storyboard_op(db, script_id, target_length=target_length))
    except Exception as e:  # noqa: BLE001
        logger.error(f"Storyboard job for script {script_id} crashed: {e}")
        try:
            from app.models.script import Script
            import uuid as _uuid
            from app.websocket.emitter import emit
            script = db.query(Script).filter(Script.id == _uuid.UUID(script_id)).first()
            if script:
                emit("stage:progress", {"stage": "storyboard", "status": "failed",
                     "agent": "Director",
                     "label": f"Storyboard crashed: {str(e)[:120]}"},
                     str(script.project_id))
        except Exception:  # noqa: BLE001
            pass
        raise
    finally:
        db.close()

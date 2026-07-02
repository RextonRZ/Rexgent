from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "rexgent",
    broker=settings.redis_url,
    backend=settings.redis_url,
    # Import the modules that define @celery_app.task so the worker registers
    # them. Without this the worker starts with an empty [tasks] list and
    # discards run_generation_job as "unregistered".
    include=[
        "app.workers.generation_worker",
        "app.workers.export_worker",
        "app.workers.casting_worker",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

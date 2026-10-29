from celery import Celery

from backend.app.core.config import settings

celery_app = Celery(
    "docvane",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["backend.app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # Guarantee tasks are not lost if a worker dies mid-processing
    worker_prefetch_multiplier=1,
)

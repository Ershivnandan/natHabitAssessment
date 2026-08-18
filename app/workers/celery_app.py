from celery import Celery

from app.core.config import settings

celery_app = Celery("taskflow", broker=settings.celery_broker_url, backend=None)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
    beat_schedule={
        "scan-overdue-tasks": {
            "task": "app.workers.tasks.scan_overdue_tasks",
            "schedule": float(settings.overdue_scan_interval_seconds),
        }
    },
)

# Ensure task functions are registered when the worker/beat process boots.
celery_app.autodiscover_tasks(["app.workers"])

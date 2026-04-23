from __future__ import annotations

from celery import Celery

from app.config import settings


celery_app = Celery(
    "community_bot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.funnel_tasks"],
)

celery_app.conf.beat_schedule = {
    "process-scheduled-tasks-every-30s": {
        "task": "app.tasks.funnel_tasks.process_scheduled_tasks",
        "schedule": 30.0,
    },
}

celery_app.conf.timezone = "UTC"
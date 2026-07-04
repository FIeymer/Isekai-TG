from celery import Celery
from config.settings import settings

celery_app = Celery(
    "storyweave",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "workers.text.tasks.*": {"queue": "text"},
        "workers.image.tasks.*": {"queue": "media"},
    },
)
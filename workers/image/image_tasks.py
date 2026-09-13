import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from config.settings import settings
from infrastructure.queue.celery_app import celery_app
from infrastructure.db.models import GenerationJob, JobStatus

logger = logging.getLogger(__name__)


def get_fresh_session():
    """Создаём новый engine и сессию для каждой задачи — избегаем проблем с event loop в Celery."""
    engine = create_async_engine(settings.database_url, pool_pre_ping=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task(
    queue="media",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
)
def generate_image_task(self, job_id: str):
    """Celery задача генерации изображения."""
    asyncio.run(_generate_image(self, job_id))


async def _generate_image(task, job_id: str):
    from workers.image.image_provider import generate_and_upload

    SessionFactory = get_fresh_session()

    async with SessionFactory() as db:
        result = await db.execute(
            select(GenerationJob).where(GenerationJob.id == job_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            logger.error(f"Job {job_id} not found")
            return

        job.status = JobStatus.RUNNING
        await db.commit()

    try:
        url = await generate_and_upload(job.prompt, job_id)

        async with SessionFactory() as db:
            result = await db.execute(
                select(GenerationJob).where(GenerationJob.id == job_id)
            )
            job = result.scalar_one_or_none()
            job.status = JobStatus.DONE
            job.result_url = url
            await db.commit()

        logger.info(f"Job {job_id} done: {url}")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")

        async with SessionFactory() as db:
            result = await db.execute(
                select(GenerationJob).where(GenerationJob.id == job_id)
            )
            job = result.scalar_one_or_none()

            if task.request.retries < task.max_retries:
                job.status = JobStatus.PENDING
                await db.commit()
                raise task.retry(exc=e)
            else:
                job.status = JobStatus.FAILED
                job.error = str(e)
                await db.commit()
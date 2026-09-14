import asyncio
import json
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from functools import partial

import aio_pika
from aio_pika.abc import AbstractChannel

from app.config import settings
from app.db.client import get_scheduler_user_id, insert_scraping_job
from app.models.job import JobSource

logger = logging.getLogger(__name__)


def _next_delay_seconds() -> float:
    """Interval with random jitter, so runs don't fire on a robotic fixed clock."""
    base = settings.scheduler_interval_minutes * 60
    jitter = settings.scheduler_jitter_minutes * 60
    return max(60.0, base + random.uniform(-jitter, jitter))


async def _enqueue_scrape(channel: AbstractChannel) -> None:
    loop = asyncio.get_running_loop()

    user_id = await loop.run_in_executor(
        None, partial(get_scheduler_user_id, settings.scheduler_user_email or None)
    )
    if user_id is None:
        logger.warning(
            "Scheduler could not resolve a user — set SCHEDULER_USER_EMAIL in .env "
            "(required when more than one user exists). Skipping this run."
        )
        return

    source = JobSource(settings.scheduler_source)
    job_id = str(uuid.uuid4())

    # Same row the web's POST /api/scraping creates, so the run appears in the dashboard.
    await loop.run_in_executor(None, partial(insert_scraping_job, job_id, user_id, source.value))

    payload = {
        "id": job_id,
        "user_id": user_id,
        "source": source.value,
        "time_posted_seconds": settings.scheduler_time_posted_seconds,
    }

    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(payload).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        ),
        routing_key=settings.scrape_queue,
    )

    logger.info("Scheduled scrape queued: id=%s source=%s", job_id, source.value)


async def run_scheduler(channel: AbstractChannel) -> None:
    logger.info(
        "Scheduler started: every ~%d min (±%d) for source=%s, f_TPR=r%d",
        settings.scheduler_interval_minutes,
        settings.scheduler_jitter_minutes,
        settings.scheduler_source,
        settings.scheduler_time_posted_seconds,
    )

    while True:
        # Sleep first: a restart (or --reload) shouldn't immediately launch Chrome.
        delay = _next_delay_seconds()
        next_run = datetime.now(timezone.utc) + timedelta(seconds=delay)
        logger.info("Next scheduled scrape at %s (in %.1f min)", next_run.isoformat(), delay / 60)

        await asyncio.sleep(delay)

        try:
            await _enqueue_scrape(channel)
        except Exception:
            # One bad tick (DB down, RabbitMQ blip) must not kill the loop.
            logger.exception("Scheduled scrape failed to enqueue — waiting for the next tick")

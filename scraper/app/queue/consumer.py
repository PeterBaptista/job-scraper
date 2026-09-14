import asyncio
import json
import logging
from datetime import datetime, timezone
from functools import partial

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from app.config import settings
from app.db.client import save_jobs, save_scraping_session, update_scraping_job
from app.models.job import ScrapeMessage
from app.notify.telegram import notify_new_jobs
from app.scrapers import get_scraper

logger = logging.getLogger(__name__)


async def _process(msg: ScrapeMessage) -> None:
    started_at = datetime.now(timezone.utc)
    loop = asyncio.get_running_loop()

    await loop.run_in_executor(
        None,
        partial(
            update_scraping_job,
            msg.id,
            status="processing",
            progress=0,
            message="Starting scraper...",
            started_at=started_at,
        ),
    )

    await loop.run_in_executor(
        None,
        partial(update_scraping_job, msg.id, status="processing", progress=20, message="Connecting to source..."),
    )

    scraper = get_scraper(msg.source, time_posted_seconds=msg.time_posted_seconds)

    await loop.run_in_executor(
        None,
        partial(update_scraping_job, msg.id, status="processing", progress=40, message="Searching for jobs..."),
    )

    # Serialise with the apply worker — SeleniumBase drives one real Chrome.
    from app.apply.worker import BROWSER_LOCK
    async with BROWSER_LOCK:
        jobs = await loop.run_in_executor(None, scraper.scrape)

    await loop.run_in_executor(
        None,
        partial(update_scraping_job, msg.id, status="processing", progress=80, message="Saving results..."),
    )

    new_jobs = await loop.run_in_executor(None, partial(save_jobs, msg.user_id, msg.source.value, jobs))
    jobs_found = len(new_jobs)

    completed_at = datetime.now(timezone.utc)

    await loop.run_in_executor(
        None,
        partial(
            save_scraping_session,
            msg.id,
            msg.user_id,
            msg.source.value,
            jobs_found,
            started_at,
            completed_at,
        ),
    )

    await loop.run_in_executor(
        None,
        partial(
            update_scraping_job,
            msg.id,
            status="completed",
            progress=100,
            message="Scraping completed!",
            completed_at=completed_at,
            jobs_found=jobs_found,
        ),
    )

    logger.info("Completed scrape: source=%s jobs=%d", msg.source, jobs_found)

    await notify_new_jobs(new_jobs, msg.source.value)

    # Score the newly saved jobs and ask for approval on the good ones.
    if new_jobs:
        try:
            from app.apply.pipeline import score_and_request
            await score_and_request()
        except Exception:
            logger.exception('Auto-apply scoring pass failed')


async def _handle_message(message: AbstractIncomingMessage) -> None:
    async with message.process(requeue=True):
        try:
            payload = json.loads(message.body)
            msg = ScrapeMessage.model_validate(payload)
        except Exception:
            logger.exception("Failed to parse message: %s", message.body)
            return

        logger.info("Received scrape request: source=%s id=%s", msg.source, msg.id)

        try:
            await _process(msg)
        except Exception:
            logger.exception("Scraping failed for source=%s id=%s", msg.source, msg.id)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                partial(
                    update_scraping_job,
                    msg.id,
                    status="failed",
                    progress=0,
                    message="Scraping failed.",
                ),
            )


async def start_consumer():
    logger.info("Connecting to RabbitMQ at %s", settings.rabbitmq_url)

    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)

    queue = await channel.declare_queue(settings.scrape_queue, durable=True)
    await queue.consume(_handle_message)

    logger.info("Listening on queue '%s'", settings.scrape_queue)
    return connection

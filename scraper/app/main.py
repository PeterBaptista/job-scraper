import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.apply.worker import start_apply_consumer
from app.config import settings
from app.notify.telegram_bot import run_approval_bot
from app.queue.consumer import start_consumer
from app.routers import health, resume
from app.scheduler import run_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Profile drift is silent and ships on real applications — surface it at boot.
    try:
        from resume import consistency_issues
        for issue in consistency_issues():
            logger.warning("Resume profile inconsistency: %s", issue)
    except Exception:
        logger.exception("Could not run resume consistency check")

    connection = await start_consumer()

    scheduler_task: asyncio.Task | None = None
    if settings.scheduler_enabled:
        channel = await connection.channel()
        scheduler_task = asyncio.create_task(run_scheduler(channel))
    else:
        logger.info("Scheduler disabled (SCHEDULER_ENABLED=false)")

    approval_task: asyncio.Task | None = None
    if settings.apply_enabled:
        await start_apply_consumer(connection)
        approval_channel = await connection.channel()
        approval_task = asyncio.create_task(run_approval_bot(approval_channel))
    else:
        logger.info("Auto-apply disabled (APPLY_ENABLED=false)")

    yield

    for name, task in (("Scheduler", scheduler_task), ("Approval bot", approval_task)):
        if task is None:
            continue
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        logger.info("%s stopped", name)

    await connection.close()
    logger.info("RabbitMQ connection closed")


app = FastAPI(
    title="Job Scraper Service",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(resume.router)

"""Ingest a LinkedIn job posted by URL in Telegram.

The scheduled scraper only sees what its keyword queries surface; this is how a
specific posting gets into the pipeline on demand.
"""

import asyncio
import logging
import uuid
from functools import partial

import psycopg
from psycopg.rows import dict_row

from app.config import settings
from app.db.client import get_scheduler_user_id
from app.scrapers.linkedin import scrape_single

logger = logging.getLogger(__name__)


def _existing(user_id: str, url: str) -> dict | None:
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        row = conn.execute(
            "SELECT id, title, company, apply_state FROM job WHERE user_id = %s AND url = %s",
            (user_id, url),
        ).fetchone()
    return dict(row) if row else None


def _insert(user_id: str, job) -> str:
    job_id = str(uuid.uuid4())
    with psycopg.connect(settings.database_url) as conn:
        conn.execute(
            """
            INSERT INTO job (id, user_id, title, company, location, salary, description,
                             url, source, status, tags, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'new', %s, %s)
            ON CONFLICT (user_id, url) DO NOTHING
            """,
            (job_id, user_id, job.title, job.company, job.location, job.salary,
             job.description, job.url, job.source.value, job.tags, job.note),
        )
    return job_id


async def ingest_url(url: str) -> dict:
    """Scrape one posting and store it. Returns {job_id|error, ...}."""
    from app.apply.worker import BROWSER_LOCK

    loop = asyncio.get_running_loop()
    user_id = await loop.run_in_executor(
        None, partial(get_scheduler_user_id, settings.scheduler_user_email or None)
    )
    if not user_id:
        return {"error": "could not resolve user"}

    canonical = url.split("?")[0].rstrip("/") + "/"
    known = await loop.run_in_executor(None, partial(_existing, user_id, canonical))
    if known:
        return {"job_id": known["id"], "existing": True, **known}

    async with BROWSER_LOCK:
        job = await loop.run_in_executor(None, partial(scrape_single, url))

    if job is None:
        return {"error": "could not read that posting (expired, or cookies stale)"}

    known = await loop.run_in_executor(None, partial(_existing, user_id, job.url))
    if known:
        return {"job_id": known["id"], "existing": True, **known}

    job_id = await loop.run_in_executor(None, partial(_insert, user_id, job))
    return {"job_id": job_id, "existing": False, "title": job.title, "company": job.company}

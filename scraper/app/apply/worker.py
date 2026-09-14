"""Consumes approved applications and drives the browser.

Shares BROWSER_LOCK with the scrape consumer: SeleniumBase drives one real Chrome,
so a scheduled scrape and an approved application must never run at the same time.
"""

import asyncio
import json
import logging
from functools import partial
from pathlib import Path

from aio_pika.abc import AbstractIncomingMessage

from app.apply.external import ApplyAbort, apply_external
from app.apply.pipeline import is_easy_apply
from app.config import settings
from app.db.client import get_job, mark_applied, record_ats
from app.notify.telegram import send_message

logger = logging.getLogger(__name__)

# One browser at a time, process-wide.
BROWSER_LOCK = asyncio.Lock()


def _easy_apply(job: dict, pdf: Path, dry_run: bool) -> tuple[bool, str]:
    from easy_apply import easy_apply

    if dry_run:
        return False, "DRY RUN — Easy Apply not submitted"
    ok = easy_apply(job["url"], pdf)
    return ok, ("submitted via Easy Apply" if ok
                else "Easy Apply flow did not reach Submit")


async def _process(job_id: str) -> None:
    loop = asyncio.get_running_loop()
    job = await loop.run_in_executor(None, partial(get_job, job_id))
    if not job:
        logger.warning("Apply worker: job %s not found", job_id)
        return

    pdf_path = job.get("resume_path")
    if not pdf_path or not Path(pdf_path).exists():
        await loop.run_in_executor(None, partial(
            record_ats, job_id, score=job.get("ats_score") or 0,
            state="failed", reason="tailored resume file missing",
        ))
        await send_message(f"⚠️ <b>{job['company']}</b>: CV gerado não encontrado")
        return

    pdf = Path(pdf_path)
    dry = settings.apply_dry_run
    route = "Easy Apply" if is_easy_apply(job) else "external"

    async with BROWSER_LOCK:
        logger.info("Applying to %s (%s, dry_run=%s)", job["title"][:50], route, dry)
        try:
            if is_easy_apply(job):
                submitted, reason = await loop.run_in_executor(
                    None, partial(_easy_apply, job, pdf, dry))
            else:
                submitted, reason = await loop.run_in_executor(
                    None, partial(apply_external, job["url"], pdf, dry))
        except ApplyAbort as exc:
            await loop.run_in_executor(None, partial(
                record_ats, job_id, score=job.get("ats_score") or 0,
                state="failed", reason=str(exc),
            ))
            await send_message(
                f"🚫 <b>{job['company']}</b> — não foi possível candidatar\n"
                f"<i>{exc}</i>\n{job['url']}"
            )
            return
        except Exception as exc:
            logger.exception("Apply failed for %s", job_id)
            await loop.run_in_executor(None, partial(
                record_ats, job_id, score=job.get("ats_score") or 0,
                state="failed", reason=f"unexpected error: {exc}"[:400],
            ))
            await send_message(f"⚠️ <b>{job['company']}</b>: erro inesperado ao candidatar")
            return

    if submitted:
        await loop.run_in_executor(None, partial(mark_applied, job_id, reason=reason))
        await send_message(f"🎉 <b>Candidatura enviada</b> — {job['company']}\n{job['url']}")
    else:
        state = "pending_approval" if dry else "failed"
        await loop.run_in_executor(None, partial(
            record_ats, job_id, score=job.get("ats_score") or 0,
            state=state, reason=reason,
        ))
        await send_message(f"ℹ️ <b>{job['company']}</b>: {reason}")


async def _handle(message: AbstractIncomingMessage) -> None:
    async with message.process(requeue=False):
        try:
            job_id = json.loads(message.body)["job_id"]
        except Exception:
            logger.exception("Bad apply message: %s", message.body[:200])
            return
        await _process(job_id)


async def start_apply_consumer(connection) -> None:
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    queue = await channel.declare_queue(settings.apply_queue, durable=True)
    await queue.consume(_handle)
    logger.info("Listening on queue '%s' (dry_run=%s)", settings.apply_queue, settings.apply_dry_run)

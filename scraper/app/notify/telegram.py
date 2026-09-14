import asyncio
import html
import logging
from pathlib import Path

import httpx

from app.blocklist import is_blocked
from app.config import settings
from app.models.job import ScrapedJob

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"

# Telegram throttles bursts to a single chat; one message per job past this many
# would be spam anyway, so the rest are summarised in a single trailing line.
MAX_MESSAGES_PER_RUN = 15


def _is_configured() -> bool:
    if not settings.telegram_enabled:
        logger.info("Telegram notifications disabled (TELEGRAM_ENABLED=false)")
        return False
    if not settings.telegram_token:
        logger.warning("TELEGRAM_TOKEN not set — skipping notifications")
        return False
    if not settings.telegram_chat_id:
        logger.warning(
            "TELEGRAM_CHAT_ID not set — skipping notifications "
            "(run: uv run python scripts/telegram_chat_id.py)"
        )
        return False
    return True


async def send_message(text: str) -> bool:
    """Send one HTML message. Never raises — notification failures must not
    break the scrape that produced them."""
    if not _is_configured():
        return False

    url = f"{API_BASE}/bot{settings.telegram_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json=payload)
        if response.status_code != 200:
            logger.error("Telegram sendMessage failed (%s): %s", response.status_code, response.text)
            return False
        return True
    except Exception:
        logger.exception("Telegram sendMessage raised")
        return False


def _format_job(job: ScrapedJob, source: str) -> str:
    e = html.escape  # scraped company names contain & regularly, which would 400 the API

    lines = [f'<b><a href="{e(job.url)}">{e(job.title)}</a></b>']
    lines.append(f"🏢 {e(job.company)}")

    if job.location:
        lines.append(f"📍 {e(job.location)}")
    if job.posted_at:
        lines.append(f"🕒 {e(job.posted_at)}")
    if job.applicants:
        lines.append(f"👥 {e(job.applicants)}")
    if job.salary:
        lines.append(f"💰 {e(job.salary)}")
    if job.note == "Candidatura simplificada":
        lines.append("🟢 Easy Apply")

    lines.append(f"<i>via {e(source)}</i>")
    return "\n".join(lines)


async def notify_new_jobs(jobs: list[ScrapedJob], source: str) -> None:
    """Send one message per newly inserted job."""
    if not jobs:
        logger.info("No new jobs to notify about")
        return
    if not _is_configured():
        return

    allowed = [j for j in jobs if not is_blocked(j.company)]
    if len(allowed) != len(jobs):
        logger.info("Blocklist hid %d job(s) from Telegram", len(jobs) - len(allowed))
    if not allowed:
        return

    jobs = allowed
    logger.info("Sending %d new job(s) to Telegram", len(jobs))

    for job in jobs[:MAX_MESSAGES_PER_RUN]:
        text = _format_job(job, source)
        if job.db_id:
            # Every posting is actionable, including ones the ATS gate would skip —
            # the reader decides, rather than only seeing what passed a threshold.
            buttons = [[
                {"text": "📄 Gerar CV", "callback_data": f"gen:{job.db_id}"},
                {"text": "🎯 Lacunas", "callback_data": f"gaps:{job.db_id}"},
            ]]
            await send_with_buttons(text, buttons)
        else:
            await send_message(text)
        await asyncio.sleep(0.5)  # stay under Telegram's per-chat rate limit

    remaining = len(jobs) - MAX_MESSAGES_PER_RUN
    if remaining > 0:
        await send_message(f"➕ <b>{remaining} more new job(s)</b> — see the dashboard")


async def send_document(path: "Path", caption: str = "") -> bool:
    """Upload a file (the tailored resume) so it can be reviewed before approving."""
    if not _is_configured():
        return False

    url = f"{API_BASE}/bot{settings.telegram_token}/sendDocument"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            with open(path, "rb") as fh:
                response = await client.post(
                    url,
                    data={
                        "chat_id": settings.telegram_chat_id,
                        "caption": caption[:1024],
                        "parse_mode": "HTML",
                    },
                    files={"document": (path.name, fh, "application/pdf")},
                )
        if response.status_code != 200:
            logger.error("Telegram sendDocument failed (%s): %s", response.status_code, response.text)
            return False
        return True
    except Exception:
        logger.exception("Telegram sendDocument raised")
        return False


async def send_with_buttons(text: str, buttons: list[list[dict]]) -> int | None:
    """Send a message with an inline keyboard. Returns the message_id."""
    if not _is_configured():
        return None

    url = f"{API_BASE}/bot{settings.telegram_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": {"inline_keyboard": buttons},
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json=payload)
        if response.status_code != 200:
            logger.error("Telegram send_with_buttons failed (%s): %s", response.status_code, response.text)
            return None
        return response.json()["result"]["message_id"]
    except Exception:
        logger.exception("Telegram send_with_buttons raised")
        return None

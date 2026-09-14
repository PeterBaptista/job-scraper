"""Companies to keep out of Telegram.

Filtering happens at notification and CV-generation time, not at scrape time: the
postings stay in the database (so the dashboard and stats remain complete) but never
reach the phone or burn an OpenAI call.
"""

import logging

from app.config import settings

logger = logging.getLogger(__name__)


def blocked_companies() -> list[str]:
    return [c.strip().lower() for c in settings.blocked_companies.split(",") if c.strip()]


def is_blocked(company: str | None) -> bool:
    """Substring match, case-insensitive — "BairesDev" also catches
    "BairesDev LLC" and "Bairesdev Brasil"."""
    if not company:
        return False
    name = company.strip().lower()
    return any(b in name for b in blocked_companies())

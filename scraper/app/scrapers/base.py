import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from seleniumbase import SB

from app.config import settings
from app.models.job import JobSource, ScrapedJob

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    source: JobSource

    def __init__(self, **kwargs) -> None:
        # kwargs are per-scraper options (e.g. time_posted_seconds); scrapers that
        # don't support an option simply ignore it, so get_scraper() stays dumb.
        self.cookies_path = Path(settings.cookies_dir) / f"{self.source.value}.json"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape(self) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []

        with SB(headless=False, headed=True, uc=True, xvfb=settings.browser_xvfb) as sb:
            self._load_cookies(sb)
            jobs = self._do_scrape(sb)

        logger.info("Scraped %d jobs from %s", len(jobs), self.source.value)
        return jobs

    # ------------------------------------------------------------------
    # Subclass contract
    # ------------------------------------------------------------------

    @abstractmethod
    def _do_scrape(self, sb: SB) -> list[ScrapedJob]:
        """Navigate the site and return a list of scraped jobs."""

    # ------------------------------------------------------------------
    # Cookie helpers
    # ------------------------------------------------------------------

    def _load_cookies(self, sb: SB) -> None:
        if not self.cookies_path.exists():
            logger.debug("No cookies file found at %s, skipping", self.cookies_path)
            return

        try:
            sb.open(self._base_url())
            cookies: list[dict] = json.loads(self.cookies_path.read_text())
            for cookie in cookies:
                # SeleniumBase / Selenium expect specific keys only
                sb.driver.add_cookie(
                    {k: v for k, v in cookie.items() if k in {"name", "value", "domain", "path", "secure", "httpOnly", "expiry"}}
                )
            sb.driver.refresh()
            logger.info("Loaded %d cookies for %s", len(cookies), self.source.value)
        except Exception:
            logger.exception("Failed to load cookies for %s", self.source.value)

    def save_cookies(self, sb: SB) -> None:
        """Call this after a manual login to persist cookies for future runs."""
        self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        cookies = sb.driver.get_cookies()
        self.cookies_path.write_text(json.dumps(cookies, indent=2))
        logger.info("Saved %d cookies to %s", len(cookies), self.cookies_path)

    @abstractmethod
    def _base_url(self) -> str:
        """Return the site's base URL (used for cookie injection)."""

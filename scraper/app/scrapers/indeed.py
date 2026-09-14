import logging

from seleniumbase import SB

from app.models.job import JobSource, ScrapedJob
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.indeed.com/jobs?q=software+engineer&l=Remote"


class IndeedScraper(BaseScraper):
    source = JobSource.indeed

    def _base_url(self) -> str:
        return "https://www.indeed.com"

    def _do_scrape(self, sb: SB) -> list[ScrapedJob]:
        sb.open(SEARCH_URL)
        sb.sleep(3)

        jobs: list[ScrapedJob] = []

        try:
            sb.wait_for_element("#mosaic-provider-jobcards", timeout=15)
        except Exception:
            logger.warning("Job cards not found on Indeed — may need fresh cookies")
            return jobs

        cards = sb.find_elements(".job_seen_beacon")
        logger.info("Found %d job cards on Indeed", len(cards))

        for card in cards[:20]:
            try:
                title = card.find_element("css selector", "h2.jobTitle span").text.strip()
                company = card.find_element("css selector", "[data-testid='company-name']").text.strip()
                location = card.find_element("css selector", "[data-testid='text-location']").text.strip()

                link = card.find_element("css selector", "h2.jobTitle a")
                job_id = link.get_attribute("id") or ""
                url = f"https://www.indeed.com/viewjob?jk={job_id.replace('job_', '')}"

                salary = None
                try:
                    salary = card.find_element("css selector", "[data-testid='attribute_snippet_testid']").text.strip()
                except Exception:
                    pass

                jobs.append(
                    ScrapedJob(
                        title=title,
                        company=company,
                        location=location,
                        salary=salary,
                        description="",
                        url=url,
                        source=self.source,
                        tags=["indeed"],
                    )
                )
            except Exception:
                logger.debug("Failed to parse Indeed card", exc_info=True)

        return jobs

import logging

from seleniumbase import SB

from app.models.job import JobSource, ScrapedJob
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.glassdoor.com/Job/software-engineer-jobs-SRCH_KO0,17.htm"


class GlassdoorScraper(BaseScraper):
    source = JobSource.glassdoor

    def _base_url(self) -> str:
        return "https://www.glassdoor.com"

    def _do_scrape(self, sb: SB) -> list[ScrapedJob]:
        sb.open(SEARCH_URL)
        sb.sleep(3)

        # Dismiss sign-in modal if present
        try:
            sb.click('[alt="Close"]', timeout=5)
        except Exception:
            pass

        jobs: list[ScrapedJob] = []

        try:
            sb.wait_for_element("ul.JobsList_jobsList__Ey2Vo", timeout=15)
        except Exception:
            logger.warning("Job list not found on Glassdoor — may need fresh cookies")
            return jobs

        cards = sb.find_elements("li.JobsList_jobListItem__JBBUV")
        logger.info("Found %d job cards on Glassdoor", len(cards))

        for card in cards[:20]:
            try:
                title = card.find_element("css selector", "a.JobCard_seoLink__WdqHZ").text.strip()
                company = card.find_element("css selector", ".EmployerProfile_compactEmployerName__9MGcV").text.strip()
                location = card.find_element("css selector", ".JobCard_location__rCz3x").text.strip()
                url = card.find_element("css selector", "a.JobCard_seoLink__WdqHZ").get_attribute("href") or ""

                salary = None
                try:
                    salary = card.find_element("css selector", ".JobCard_salaryEstimate__arV5J").text.strip()
                except Exception:
                    pass

                jobs.append(
                    ScrapedJob(
                        title=title,
                        company=company,
                        location=location,
                        salary=salary,
                        description="",
                        url=url.split("?")[0],
                        source=self.source,
                        tags=["glassdoor"],
                    )
                )
            except Exception:
                logger.debug("Failed to parse Glassdoor card", exc_info=True)

        return jobs

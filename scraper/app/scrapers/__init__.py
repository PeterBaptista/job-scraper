from app.models.job import JobSource
from app.scrapers.base import BaseScraper
from app.scrapers.glassdoor import GlassdoorScraper
from app.scrapers.indeed import IndeedScraper
from app.scrapers.linkedin import LinkedInScraper

_REGISTRY: dict[JobSource, type[BaseScraper]] = {
    JobSource.linkedin: LinkedInScraper,
    JobSource.glassdoor: GlassdoorScraper,
    JobSource.indeed: IndeedScraper,
}


def get_scraper(source: JobSource, **kwargs) -> BaseScraper:
    cls = _REGISTRY.get(source)
    if cls is None:
        raise ValueError(f"No scraper registered for source: {source}")
    return cls(**kwargs)

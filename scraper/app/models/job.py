from enum import Enum
from typing import Optional

from pydantic import BaseModel


class JobSource(str, Enum):
    linkedin = "linkedin"
    glassdoor = "glassdoor"
    indeed = "indeed"
    other = "other"


class ScrapeMessage(BaseModel):
    id: str
    user_id: str
    source: JobSource
    # Only recent postings when set (LinkedIn f_TPR). Absent on web-triggered
    # scrapes, which stay unfiltered.
    time_posted_seconds: Optional[int] = None


class ScrapedJob(BaseModel):
    title: str
    company: str
    location: str
    salary: Optional[str] = None
    description: str
    url: str
    source: JobSource
    tags: list[str] = []
    note: Optional[str] = None
    # How long ago the posting went up, as the site words it ("há 24 minutos").
    # Used in notifications only — not a `job` table column.
    posted_at: Optional[str] = None
    # How many people have applied, as the site words it ("1 candidatura").
    applicants: Optional[str] = None
    # Set by save_jobs() after insert, so Telegram buttons can reference the row.
    db_id: Optional[str] = None

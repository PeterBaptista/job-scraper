import logging
import re
from urllib.parse import urlencode

from seleniumbase import SB

from app.config import settings
from app.models.job import JobSource, ScrapedJob
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# URL parameters reference:
#   keywords  — job title / skills
#   f_WT      — work type: 1=onsite, 2=remote, 3=hybrid
#   f_JT      — job type: F=full-time, P=part-time, C=contract, T=temp, I=internship
#   f_E       — experience: 1=intern, 2=entry, 3=assoc, 4=mid-senior, 5=director
#   f_TPR     — time posted: r3600=1h, r86400=24h, r604800=1wk, r2592000=1mo
#   sortBy    — DD=most recent, R=relevance
#   geoId     — numeric location id (e.g. 106057199 = Brazil)
#
# Tailored for a Full Stack Developer profile (React/Next.js/TypeScript/Node.js)
#
# Bilingual coverage is done with several plain-text queries rather than one
# boolean query. Measured on the same 2h window: the plain English query returned
# 17 cards, while a quoted `(...) AND (...)` boolean query returned 5 — LinkedIn
# matches loose keyword text far more generously than strict boolean syntax.
# Results are merged and deduped by job id, so overlap between queries is free.
KEYWORD_QUERIES = [
    "full stack developer react typescript",
    "desenvolvedor full stack react typescript",
    "engenheiro de software react node",
]

SEARCH_PARAMS = {
    "keywords": KEYWORD_QUERIES[0],
    "f_WT": "2",          # remote
    "f_JT": "F",          # full-time
    "f_E": "2,3,4",       # entry, associate, mid-senior
    "sortBy": "DD",       # most recent first
    "geoId": "106057199", # Brazil
}


def build_search_url(time_posted_seconds: int | None = None, keywords: str | None = None) -> str:
    """Search URL, optionally narrowed to jobs posted in the last N seconds."""
    params = dict(SEARCH_PARAMS)
    if keywords:
        params["keywords"] = keywords
    if time_posted_seconds:
        params["f_TPR"] = f"r{time_posted_seconds}"
    return "https://www.linkedin.com/jobs/search/?" + urlencode(params)



# The broad queries above maximise recall, but LinkedIn ORs loose keyword text —
# "desenvolvedor" on its own matches PowerBuilder, ABAP and mining-engineer roles.
# Precision is therefore enforced here, where it can be tuned, instead of in the
# query, where tightening it collapsed results (17 cards -> 5).
STACK_RE = re.compile(
    r"\b("
    r"react|next\.?js|typescript|javascript|node(?:\.?js)?|"
    r"vue(?:\.?js)?|angular|nest\.?js|"
    r"full[\s-]?stack|front[\s-]?end"
    r")\b",
    re.IGNORECASE,
)


# A single stack mention in a long description is usually incidental — ABAP and
# middleware posts list "React" among nice-to-haves. Requiring several distinct
# terms separates real JS roles from passing references. Measured over 32 scraped
# jobs: >=2 still let ABAP through, >=4 dropped genuine generalist roles, >=3 kept
# all 11 real matches and none of the noise.
MIN_DESCRIPTION_STACK_TERMS = 3


def is_relevant(job: ScrapedJob) -> bool:
    """Keep jobs naming the target stack in the title, or repeatedly in the body."""
    if STACK_RE.search(job.title):
        return True
    if not job.description:
        # The detail panel failed to load, so there is nothing to judge on. Missing
        # data is not evidence of irrelevance — fail open, or a throttled run where
        # every panel times out would silently discard the entire scrape.
        return True
    distinct = {m.group(0).lower() for m in STACK_RE.finditer(job.description)}
    return len(distinct) >= MIN_DESCRIPTION_STACK_TERMS


CARD_SEL = ".job-card-container"

_EXTRACT_JS = """
(() => Array.from(document.querySelectorAll('.job-card-container')).map(card => {
    const jobId = card.getAttribute('data-job-id') || '';
    const anchor = card.querySelector('.job-card-list__title--link, .job-card-container__link');
    const title = anchor?.getAttribute('aria-label')?.replace(/ with verification$/, '').trim()
        || anchor?.innerText?.trim()
        || card.querySelector('strong')?.innerText?.trim()
        || '';
    const company = card.querySelector('.artdeco-entity-lockup__subtitle')?.innerText?.trim() || '';
    const location = card.querySelector('.artdeco-entity-lockup__caption')?.innerText?.trim() || '';
    const salary = card.querySelector('.artdeco-entity-lockup__metadata')?.innerText?.trim() || '';
    const footerItems = [...card.querySelectorAll('.job-card-container__footer-item')];
    const isEasyApply = footerItems.some(el => el.innerText.includes('simplificada') || el.innerText.includes('Easy Apply'));
    return { jobId, title, company, location, salary, isEasyApply };
}))()
"""

# After clicking a card, inspect the apply button in the detail panel:
# - "Candidatura simplificada" → Easy Apply (LinkedIn modal) → no external href
# - external apply → <a href="https://company.com/..."> button
_APPLY_URL_JS = """
(() => {
    const btn = document.querySelector(
        '.jobs-apply-button--top-card a[href],' +
        '.jobs-s-apply a[href],' +
        'a.jobs-apply-button[href]'
    );
    const easyApplyBtn = document.querySelector(
        'button.jobs-apply-button, .jobs-apply-button--top-card button'
    );
    const easyApplyText = easyApplyBtn?.innerText?.toLowerCase() || '';
    const isEasyApply = easyApplyText.includes('simplificada') || easyApplyText.includes('easy apply');
    return {
        externalUrl: btn ? btn.getAttribute('href') : '',
        isEasyApply: isEasyApply || !btn
    };
})()
"""


# Posting age and applicant count live only in the detail panel, never on the card.
# They share one row of middot-separated spans: "Brasil · há 24 minutos · 1 candidatura".
# Both are read in a single call to keep it to one round-trip per job.
_DETAIL_META_JS = """
(() => {
    const TIME_RE = /(h[áa]\\s|atr[áa]s|\\bago\\b|hace\\s)/i;
    const APP_RE = /(candidatura|candidato|applicant|solicitude)/i;
    // LinkedIn moves these between markup revisions, so try progressively wider
    // roots rather than betting on one container class.
    const ROOTS = [
        '.job-details-jobs-unified-top-card__primary-description-container',
        '.job-details-jobs-unified-top-card__tertiary-description-container',
        '.job-details-jobs-unified-top-card__container--two-pane',
        '.jobs-unified-top-card',
        '.jobs-details__main-content',
    ];

    const out = { posted_at: '', applicants: '' };
    // Prefer the shortest matching leaf — "há 24 minutos" over a whole paragraph
    const shortest = (arr, re) =>
        arr.filter(t => re.test(t)).sort((a, b) => a.length - b.length)[0] || '';

    for (const sel of ROOTS) {
        const root = document.querySelector(sel);
        if (!root) continue;

        const leaves = [...root.querySelectorAll('.tvm__text, span, li')]
            .map(e => (e.innerText || '').trim())
            .filter(t => t && t.length < 45);

        if (!out.posted_at) out.posted_at = shortest(leaves, TIME_RE);
        if (!out.applicants) out.applicants = shortest(leaves, APP_RE);

        if (!out.posted_at || !out.applicants) {
            const parts = (root.innerText || '')
                .split(/[·\\n]/).map(s => s.trim()).filter(p => p && p.length < 45);
            if (!out.posted_at) out.posted_at = shortest(parts, TIME_RE);
            if (!out.applicants) out.applicants = shortest(parts, APP_RE);
        }
        if (out.posted_at && out.applicants) break;
    }
    return out;
})()
"""


class LinkedInScraper(BaseScraper):
    source = JobSource.linkedin

    def __init__(self, time_posted_seconds: int | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.time_posted_seconds = time_posted_seconds

    def _base_url(self) -> str:
        return "https://www.linkedin.com"

    def _scroll_to_bottom(self, sb: SB) -> None:
        """Scroll the job list panel step-by-step so occluded cards lazy-load.
        The actual scrollable element is the first child div of .scaffold-layout__list.
        """
        sb.execute_script(
            "(() => { const p = document.querySelector('.scaffold-layout__list > div'); if (p) p.scrollTop = 0; })()"
        )
        sb.sleep(0.5)

        for _ in range(40):
            at_bottom = sb.execute_script("""
                (() => {
                    const p = document.querySelector('.scaffold-layout__list > div');
                    if (!p) return true;
                    p.scrollBy({ top: 300, behavior: 'smooth' });
                    return p.scrollTop + p.clientHeight >= p.scrollHeight - 5;
                })()
            """)
            sb.sleep(0.6)
            if at_bottom:
                break

    def _do_scrape(self, sb: SB) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []
        seen_ids: set[str] = set()
        max_pages = 4
        per_page = 24

        for query in KEYWORD_QUERIES:
            search_url = build_search_url(self.time_posted_seconds, keywords=query)
            logger.info("LinkedIn query %r", query)
            self._scrape_query(sb, search_url, jobs, seen_ids, max_pages, per_page)

        # Log capture rates BEFORE filtering — when the filter drops everything, this
        # is the line that says whether the cause was irrelevance or a failed page load.
        if jobs:
            logger.info(
                "Detail capture: posted_at %d/%d, applicants %d/%d, description %d/%d",
                sum(1 for j in jobs if j.posted_at),
                len(jobs),
                sum(1 for j in jobs if j.applicants),
                len(jobs),
                sum(1 for j in jobs if j.description),
                len(jobs),
            )

        scraped = len(jobs)
        jobs = [j for j in jobs if is_relevant(j)]
        if scraped != len(jobs):
            logger.info(
                "Relevance filter: kept %d of %d (dropped %d off-stack)",
                len(jobs), scraped, scraped - len(jobs),
            )

        return jobs

    def _scrape_query(
        self,
        sb: SB,
        search_url: str,
        jobs: list[ScrapedJob],
        seen_ids: set[str],
        max_pages: int,
        per_page: int,
    ) -> None:
        for page in range(max_pages):
            start = page * per_page
            page_url = search_url + f"&start={start}"
            sb.open(page_url)
            sb.sleep(4)

            try:
                sb.wait_for_element(CARD_SEL, timeout=20)
            except Exception:
                logger.warning("Page %d (start=%d): no cards found, stopping", page + 1, start)
                break

            self._scroll_to_bottom(sb)

            raw_cards: list[dict] = sb.execute_script(_EXTRACT_JS) or []
            logger.info("Page %d (start=%d): extracted %d raw cards", page + 1, start, len(raw_cards))

            if not raw_cards:
                logger.info("No cards on page %d — stopping", page + 1)
                break

            page_jobs_before = len(jobs)

            for i, data in enumerate(raw_cards):
                job_id = data.get("jobId", "")
                title = data.get("title", "")
                company = data.get("company", "")
                location = data.get("location", "")
                salary = data.get("salary") or None
                is_easy_apply = data.get("isEasyApply", True)

                # LinkedIn mixes non-job elements into .job-card-container (e.g. a
                # placeholder with data-job-id="search"). A real id is always numeric;
                # anything else would build a bogus /jobs/view/<junk>/ URL.
                if not job_id.isdigit():
                    logger.debug("Page %d card %d: non-numeric job id %r, skipping", page + 1, i, job_id)
                    continue
                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)

                if not title:
                    logger.warning("Page %d card %d (job_id=%s): no title, skipping", page + 1, i, job_id)
                    continue

                # Click the card to load the detail panel (for description + external URL)
                try:
                    sb.execute_script(f"document.querySelector('[data-job-id=\"{job_id}\"]').click()")
                    # The detail panel loads async; too short a wait yields empty
                    # descriptions and no posted-at.
                    sb.sleep(2.2)
                except Exception:
                    logger.warning("Page %d card %d (job_id=%s): click failed, skipping", page + 1, i, job_id)
                    continue

                # Description from the detail panel
                description = sb.execute_script(
                    "document.querySelector("
                    "'.jobs-description__content, "
                    ".jobs-description-content__text, "
                    ".job-details-jobs-unified-top-card__job-description'"
                    ")?.innerText?.trim() || ''"
                ) or ""

                # Posting age + applicant count — only exist in the detail panel
                meta: dict = sb.execute_script(_DETAIL_META_JS) or {}
                posted_at = meta.get("posted_at") or None
                applicants = meta.get("applicants") or None

                # For external apply jobs, get the actual company URL from the detail panel
                linkedin_url = f"https://www.linkedin.com/jobs/view/{job_id}/"
                if is_easy_apply:
                    url = linkedin_url
                else:
                    apply_info: dict = sb.execute_script(_APPLY_URL_JS) or {}
                    external_url = (apply_info.get("externalUrl") or "").split("?")[0]
                    if external_url.startswith("/"):
                        # relative href — resolve against LinkedIn, not the bare path
                        external_url = "https://www.linkedin.com" + external_url
                    url = external_url if external_url.startswith("http") else linkedin_url

                jobs.append(
                    ScrapedJob(
                        title=title,
                        company=company,
                        location=location,
                        salary=salary,
                        description=description,
                        url=url,
                        source=self.source,
                        posted_at=posted_at,
                        applicants=applicants,
                        tags=["linkedin", "react", "typescript", "full-stack"],
                        note="Candidatura simplificada" if is_easy_apply else None,
                    )
                )

            logger.info("Page %d: scraped %d new jobs (total so far: %d)", page + 1, len(jobs) - page_jobs_before, len(jobs))


def scrape_single(url: str) -> ScrapedJob | None:
    """Fetch one LinkedIn posting by URL.

    Used by the Telegram link command — the search-page scraper can't reach a job
    the keyword queries never surfaced.
    """
    scraper = LinkedInScraper()
    with SB(headless=False, headed=True, uc=True, xvfb=settings.browser_xvfb) as sb:
        scraper._load_cookies(sb)
        sb.open(url)
        sb.sleep(4)

        data = sb.execute_script(_SINGLE_JOB_JS) or {}
        if not data.get("title"):
            logger.warning("scrape_single: no title found at %s", url)
            return None

        job_id = re.search(r"/jobs/view/(\d+)", url)
        canonical = f"https://www.linkedin.com/jobs/view/{job_id.group(1)}/" if job_id else url

        return ScrapedJob(
            title=data["title"],
            company=data.get("company") or "",
            location=data.get("location") or "",
            salary=data.get("salary") or None,
            description=data.get("description") or "",
            url=canonical,
            source=JobSource.linkedin,
            posted_at=data.get("posted_at") or None,
            applicants=data.get("applicants") or None,
            tags=["linkedin", "manual"],
            note="Candidatura simplificada" if data.get("isEasyApply") else None,
        )


_SINGLE_JOB_JS = """
(() => {
  const txt = sel => document.querySelector(sel)?.innerText?.trim() || '';
  const TIME_RE = /(h[áa]\\s|atr[áa]s|\\bago\\b|hace\\s)/i;
  const APP_RE = /(candidatura|candidato|applicant)/i;

  const title = txt('.job-details-jobs-unified-top-card__job-title, .top-card-layout__title, h1');
  const company = txt('.job-details-jobs-unified-top-card__company-name, .topcard__org-name-link');
  const container = document.querySelector(
    '.job-details-jobs-unified-top-card__primary-description-container, .topcard__flavor-row'
  );
  const leaves = container
    ? [...container.querySelectorAll('.tvm__text, span, li')]
        .map(e => (e.innerText || '').trim()).filter(t => t && t.length < 45)
    : [];
  const shortest = re => leaves.filter(t => re.test(t)).sort((a,b) => a.length - b.length)[0] || '';

  const applyBtn = document.querySelector('.jobs-apply-button, button.jobs-apply-button');
  const applyText = (applyBtn?.innerText || '').toLowerCase();

  return {
    title,
    company,
    location: leaves.find(t => !TIME_RE.test(t) && !APP_RE.test(t) && t.length > 2) || '',
    salary: txt('.job-details-jobs-unified-top-card__salary-info'),
    posted_at: shortest(TIME_RE),
    applicants: shortest(APP_RE),
    description: txt('.jobs-description__content, .jobs-description-content__text, .description__text'),
    isEasyApply: applyText.includes('simplificada') || applyText.includes('easy apply'),
  };
})()
"""

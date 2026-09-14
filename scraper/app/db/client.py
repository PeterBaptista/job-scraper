import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from app.config import settings
from app.models.job import ScrapedJob


def _conn() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def update_scraping_job(
    job_id: str,
    *,
    status: str,
    progress: int,
    message: str,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    jobs_found: int | None = None,
) -> None:
    fields: dict[str, Any] = {
        "status": status,
        "progress": progress,
        "message": message,
    }
    if started_at is not None:
        fields["started_at"] = started_at
    if completed_at is not None:
        fields["completed_at"] = completed_at
    if jobs_found is not None:
        fields["jobs_found"] = jobs_found

    set_clause = ", ".join(f"{k} = %({k})s" for k in fields)
    fields["id"] = job_id

    with _conn() as conn:
        conn.execute(
            f"UPDATE scraping_job SET {set_clause} WHERE id = %(id)s",  # noqa: S608
            fields,
        )


def save_scraping_session(
    session_id: str,
    user_id: str,
    source: str,
    jobs_found: int,
    started_at: datetime,
    completed_at: datetime,
) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO scraping_session
                (id, user_id, source, status, jobs_found, new_jobs, started_at, completed_at)
            VALUES (%s, %s, %s, 'completed', %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
                SET status = 'completed',
                    jobs_found = EXCLUDED.jobs_found,
                    new_jobs = EXCLUDED.new_jobs,
                    completed_at = EXCLUDED.completed_at
            """,
            (session_id, user_id, source, jobs_found, jobs_found, started_at, completed_at),
        )


def save_jobs(user_id: str, source: str, jobs: list[ScrapedJob]) -> list[ScrapedJob]:
    """Insert scraped jobs, skipping ones already saved for this user.

    Returns only the jobs that were actually inserted — callers use this to
    notify about genuinely new postings without re-alerting on every scrape.
    """
    if not jobs:
        return []

    now = datetime.now(timezone.utc)

    inserted: list[ScrapedJob] = []
    with _conn() as conn:
        with conn.cursor() as cur:
            for job in jobs:
                new_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO job
                        (id, user_id, title, company, location, salary, description,
                         url, source, status, tags, note, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, url) DO NOTHING
                    RETURNING id
                    """,
                    (
                        new_id,
                        user_id,
                        job.title,
                        job.company,
                        job.location,
                        job.salary,
                        job.description,
                        job.url,
                        source,
                        "new",
                        job.tags,
                        job.note,
                        now,
                    ),
                )
                if cur.fetchone() is not None:
                    job.db_id = new_id
                    inserted.append(job)

    return inserted


def insert_scraping_job(job_id: str, user_id: str, source: str) -> None:
    """Create a queued scraping_job row, mirroring the web's POST /api/scraping.

    Scheduled runs go through this so they show up in the dashboard alongside
    manually triggered ones.
    """
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO scraping_job (id, user_id, source, status, progress, created_at)
            VALUES (%s, %s, %s, 'queued', 0, %s)
            """,
            (job_id, user_id, source, datetime.now(timezone.utc)),
        )


def get_scheduler_user_id(email: str | None = None) -> str | None:
    """Resolve the user the scheduler scrapes for.

    With an email, look it up directly. Without one, fall back to the single
    registered user — but only if there is exactly one, since guessing between
    several would silently file jobs under the wrong account.
    """
    with _conn() as conn:
        if email:
            row = conn.execute('SELECT id FROM "user" WHERE email = %s', (email,)).fetchone()
            return str(row["id"]) if row else None

        rows = conn.execute('SELECT id FROM "user" LIMIT 2').fetchall()

    if len(rows) == 1:
        return str(rows[0]["id"])
    return None


def record_ats(job_id: str, *, score: int, state: str, reason: str, resume_path: str | None = None) -> None:
    """Persist the auto-apply pipeline's verdict for one job."""
    with _conn() as conn:
        conn.execute(
            """
            UPDATE job
               SET ats_score = %s, apply_state = %s, apply_reason = %s,
                   resume_path = COALESCE(%s, resume_path)
             WHERE id = %s
            """,
            (score, state, reason[:1000], resume_path, job_id),
        )


def mark_applied(job_id: str, *, reason: str) -> None:
    with _conn() as conn:
        conn.execute(
            """
            UPDATE job
               SET status = 'applied', applied_at = %s,
                   apply_state = 'applied', apply_reason = %s
             WHERE id = %s
            """,
            (datetime.now(timezone.utc), reason[:1000], job_id),
        )


def get_job(job_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT id, title, company, location, salary, description, url, note,
                   ats_score, apply_state, apply_reason, resume_path, user_id
              FROM job WHERE id = %s
            """,
            (job_id,),
        ).fetchone()
    return dict(row) if row else None


def jobs_pending_scoring(user_id: str, limit: int = 20) -> list[dict]:
    """New jobs that the apply pipeline hasn't looked at yet."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, title, company, location, salary, description, url, note
              FROM job
             WHERE user_id = %s AND apply_state IS NULL AND status = 'new'
             ORDER BY scraped_at DESC
             LIMIT %s
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]



# ---------------------------------------------------------------------------
# Resume drafts
#
# The tailored content dict, not the rendered PDF. Rendering is one-way — once
# ReportLab has written the file, the structure it was built from is gone — so
# the dashboard editor needs the dict kept alongside the output.
# ---------------------------------------------------------------------------

_DRAFT_COLUMNS = """
    id, job_id, user_id, status, language, content, generated_content, meta,
    ats_score, ats_detail, extra_prompt, error, pdf_path, pdf_committed_at,
    created_at, updated_at
"""


def get_draft(job_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            f"SELECT {_DRAFT_COLUMNS} FROM resume_draft WHERE job_id = %s",
            (job_id,),
        ).fetchone()
    return dict(row) if row else None


def upsert_draft(
    job_id: str,
    user_id: str,
    *,
    status: str,
    content: dict | None = None,
    generated_content: dict | None = None,
    meta: dict | None = None,
    language: str | None = None,
    ats_score: int | None = None,
    ats_detail: dict | None = None,
    extra_prompt: str | None = None,
    error: str | None = None,
    pdf_path: str | None = None,
    pdf_committed: bool = False,
) -> dict:
    """Insert or replace the single draft for a job.

    Optional arguments are COALESCEd, following record_ats: passing None means
    "leave what is there", not "blank it". `error` is the exception — a run that
    succeeds must clear the previous failure, so it is written unconditionally.
    """
    now = datetime.now(timezone.utc)
    with _conn() as conn:
        row = conn.execute(
            f"""
            INSERT INTO resume_draft (
                id, job_id, user_id, status, language, content, generated_content,
                meta, ats_score, ats_detail, extra_prompt, error, pdf_path,
                pdf_committed_at, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, COALESCE(%s, 'pt'), %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s)
            ON CONFLICT (job_id) DO UPDATE SET
                status            = EXCLUDED.status,
                language          = COALESCE(EXCLUDED.language, resume_draft.language),
                content           = COALESCE(EXCLUDED.content, resume_draft.content),
                generated_content = COALESCE(EXCLUDED.generated_content,
                                             resume_draft.generated_content),
                meta              = COALESCE(EXCLUDED.meta, resume_draft.meta),
                ats_score         = COALESCE(EXCLUDED.ats_score,
                                             resume_draft.ats_score),
                ats_detail        = COALESCE(EXCLUDED.ats_detail,
                                             resume_draft.ats_detail),
                extra_prompt      = COALESCE(EXCLUDED.extra_prompt,
                                             resume_draft.extra_prompt),
                error             = EXCLUDED.error,
                pdf_path          = COALESCE(EXCLUDED.pdf_path, resume_draft.pdf_path),
                pdf_committed_at  = COALESCE(EXCLUDED.pdf_committed_at,
                                             resume_draft.pdf_committed_at),
                updated_at        = EXCLUDED.updated_at
            RETURNING {_DRAFT_COLUMNS}
            """,
            (
                str(uuid.uuid4()), job_id, user_id, status, language,
                Json(content) if content is not None else None,
                Json(generated_content) if generated_content is not None else None,
                Json(meta) if meta is not None else None,
                ats_score,
                Json(ats_detail) if ats_detail is not None else None,
                extra_prompt, error, pdf_path,
                now if pdf_committed else None,
                now, now,
            ),
        ).fetchone()
    return dict(row)

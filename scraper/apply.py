"""
Job application bot

Two-step workflow:
  Step 1 — fetch.py (this file with --fetch): prints job prompts to paste into Claude Code
  Step 2 — apply.py --apply <json>: takes Claude's JSON output, generates PDF, automates browser

Usage:
  uv run python apply.py --fetch              # print jobs for Claude Code analysis
  uv run python apply.py --fetch --limit 5    # limit to 5 jobs
  uv run python apply.py --apply analysis.json          # apply using Claude's output
  uv run python apply.py --apply analysis.json --dry-run  # PDF only, skip browser
"""

import argparse
import re
import sys
import tempfile
import webbrowser
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from app.apply.profile import profile_block
from resume import CONTENT, PROFILE, build_with_content

load_dotenv()

DB_URL = "postgresql://jobscraper:jobscraper@localhost:5432/jobscraper"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _conn() -> psycopg.Connection:
    return psycopg.connect(DB_URL, row_factory=dict_row)


def get_user_id(email: str) -> str | None:
    with _conn() as conn:
        row = conn.execute('SELECT id FROM "user" WHERE email = %s', (email,)).fetchone()
    return str(row["id"]) if row else None


def fetch_new_jobs(user_id: str, limit: int) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, title, company, location, salary, description, url, source
            FROM job
            WHERE user_id = %s AND status = 'new'
            ORDER BY scraped_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def update_job_status(user_id: str, job_id: str, status: str, note: str | None = None) -> None:
    with _conn() as conn:
        if note:
            conn.execute(
                "UPDATE job SET status = %s, note = %s WHERE id = %s AND user_id = %s",
                (status, note, job_id, user_id),
            )
        else:
            conn.execute(
                "UPDATE job SET status = %s WHERE id = %s AND user_id = %s",
                (status, job_id, user_id),
            )


# ---------------------------------------------------------------------------
# Step 1 — generate prompt for Claude Code
# ---------------------------------------------------------------------------

# The profile lives in the git-ignored ME.md — never inline it here.
_PROFILE_TEXT = profile_block()


def print_prompt(jobs: list[dict]) -> None:
    print("=" * 70)
    print("Paste the block below into Claude Code chat")
    print("=" * 70)
    print()
    print("Analyse these job postings for the candidate and return a JSON array.")
    print()
    print("## Candidate profile")
    print(_PROFILE_TEXT)
    print()
    print("## Jobs")
    for i, job in enumerate(jobs, 1):
        print(f"\n### Job {i}")
        print(f"id: {job['id']}")
        print(f"title: {job['title']}")
        print(f"company: {job['company']}")
        print(f"location: {job['location']}")
        print(f"url: {job['url']}")
        print(f"description:\n{job['description'][:3000]}")
    print()
    print("## Instructions")
    print("""For each job return a JSON object in an array with:
  - id: (same job id from above)
  - score: int 1-10 (fit score)
  - should_apply: bool (score >= 7)
  - language: "pt" if posting is in Portuguese, else "en"
  - reason: str (1-2 sentences)
  - tailored_title: str (match the job title exactly)
  - tailored_summary: str (2-3 sentences, mirror exact keywords from job)
  - current_role_bullets: list[str] (4 tailored bullets for the current role)
  - internship_bullets: list[str] (4 tailored bullets for internship role)

Keep bullets factual — do NOT invent experience the candidate doesn't have.
Return ONLY the JSON array, no markdown fences.""")
    print()
    print("=" * 70)
    print("After Claude replies, save the JSON array to a file and run:")
    print("  uv run python apply.py --apply <file.json>")
    print("=" * 70)


# ---------------------------------------------------------------------------
# Step 2 — PDF generation
# ---------------------------------------------------------------------------

def generate_tailored_pdf(job_id: str, analysis: dict, out_dir: Path) -> Path:
    lang = analysis["language"]
    import copy
    base = copy.deepcopy(CONTENT[lang])

    base["title"] = analysis["tailored_title"]
    base["summary"] = analysis["tailored_summary"]
    base["experience"][0]["bullets"] = analysis["current_role_bullets"]
    base["experience"][1]["bullets"] = analysis["internship_bullets"]

    safe = re.sub(r"[^a-z0-9]+", "_", analysis.get("tailored_title", job_id).lower()).strip("_")
    out_path = out_dir / f"resume_{safe}.pdf"
    build_with_content(out_path, base)
    return out_path


# ---------------------------------------------------------------------------
# Browser automation
# ---------------------------------------------------------------------------

def apply_easy_apply(job_url: str, pdf_path: Path) -> bool:
    from easy_apply import easy_apply
    return easy_apply(job_url, pdf_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def cmd_fetch(args) -> None:
    user_id = get_user_id(PROFILE["email"])
    if not user_id:
        print(f"[error] No user found with email {PROFILE['email']}")
        sys.exit(1)

    jobs = fetch_new_jobs(user_id, args.limit)
    if not jobs:
        print("No new jobs found.")
        return

    print_prompt(jobs)


def cmd_apply(args) -> None:
    analysis_path = Path(args.apply)
    if not analysis_path.exists():
        print(f"[error] File not found: {analysis_path}")
        sys.exit(1)

    analyses: list[dict] = json.loads(analysis_path.read_text())
    user_id = get_user_id(PROFILE["email"])
    if not user_id:
        print(f"[error] No user found with email {PROFILE['email']}")
        sys.exit(1)

    # fetch job URLs/details by id so we can open/apply
    ids = [a["id"] for a in analyses]
    with _conn() as conn:
        placeholders = ",".join(["%s"] * len(ids))
        rows = conn.execute(
            f"SELECT id, title, company, url, source FROM job WHERE id::text = ANY(ARRAY[{placeholders}])",
            ids,
        ).fetchall()
    jobs_by_id = {str(r["id"]): dict(r) for r in rows}

    results = {"applied": 0, "skipped": 0, "errors": 0}

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)

        for analysis in analyses:
            job_id = str(analysis["id"])
            job = jobs_by_id.get(job_id)
            if not job:
                print(f"[warn] Job {job_id} not found in DB — skipping")
                continue

            print(f"[{job['company']}] {job['title']}")
            print(f"  Score: {analysis['score']}/10 — {analysis['reason']}")

            if not analysis.get("should_apply", False):
                print("  → Skipping (low score)\n")
                update_job_status(user_id, job_id, "rejected",
                                  f"Score {analysis['score']}/10: {analysis['reason']}")
                results["skipped"] += 1
                continue

            try:
                pdf_path = generate_tailored_pdf(job_id, analysis, out_dir)
                print(f"  Resume: {pdf_path.name}")

                if args.dry_run:
                    print("  → Dry run — skipping browser\n")
                    results["skipped"] += 1
                    continue

                is_linkedin = "linkedin.com" in job["url"]
                if is_linkedin:
                    print("  → LinkedIn Easy Apply …")
                    ok = apply_easy_apply(job["url"], pdf_path)
                    if ok:
                        print("  → Submitted!")
                    else:
                        print("  → Auto-submit failed; opening in browser")
                        webbrowser.open(job["url"])
                    update_job_status(user_id, job_id, "applied",
                                      f"Score {analysis['score']}/10. {'Auto-submitted.' if ok else 'Opened manually.'}")
                else:
                    print("  → Opening external URL")
                    webbrowser.open(job["url"])
                    update_job_status(user_id, job_id, "applied",
                                      f"Score {analysis['score']}/10. Opened external URL.")

                results["applied"] += 1

            except Exception as exc:
                print(f"  [error] {exc}")
                update_job_status(user_id, job_id, "error", str(exc))
                results["errors"] += 1

            print()

    print(f"Done — applied: {results['applied']}, skipped: {results['skipped']}, errors: {results['errors']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Job application bot")
    sub = parser.add_subparsers(dest="cmd")

    fetch_p = parser.add_argument_group("fetch")
    fetch_p.add_argument("--fetch", action="store_true", help="Print jobs prompt for Claude Code")
    fetch_p.add_argument("--limit", type=int, default=10, help="Max jobs to fetch")

    apply_p = parser.add_argument_group("apply")
    apply_p.add_argument("--apply", metavar="FILE", help="JSON file with Claude's analysis")
    apply_p.add_argument("--dry-run", action="store_true", help="Generate PDFs only, skip browser")

    args = parser.parse_args()

    if args.fetch:
        cmd_fetch(args)
    elif args.apply:
        cmd_apply(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

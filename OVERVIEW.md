# Project Overview — Job Scraper

*Snapshot as of 2026-08-17 (branch `main`, HEAD `232712e`).*

## What it is

A personal **job hunting automation platform** built for one user. It has grown
beyond a "scraper" — today it covers the full pipeline from finding a posting to submitting a
tailored application:

```
scrape listings → store & track them in a dashboard → score fit with Claude
  → generate a tailored PDF resume → auto-submit via LinkedIn Easy Apply
```

It is split into two services that share one PostgreSQL database and talk over RabbitMQ.

| Piece | Location | Stack |
|---|---|---|
| Web dashboard + API | `web/` | Next.js 16 (App Router), React 19, Drizzle ORM, Better Auth, TanStack Query, shadcn/ui + Tailwind v4 |
| Scraper / automation | `scraper/` | FastAPI, SeleniumBase (UC mode), aio-pika, psycopg3, ReportLab |
| Database | Docker | PostgreSQL 17 |
| Queue | Docker | RabbitMQ 4 |

---

## 1. Scraping pipeline

**Trigger.** The user picks a source in the dashboard → `POST /api/scraping` writes a
`scraping_job` row (`status: queued`) and publishes `{id, user_id, source}` to the RabbitMQ
queue `scrape_jobs`.

**Execution.** The FastAPI service starts its consumer in the app lifespan. On each message it:

1. Resolves the scraper from a registry (`app/scrapers/__init__.py`).
2. Runs it inside `loop.run_in_executor` — SeleniumBase is synchronous.
3. Pushes progress updates (0 → 20 → 40 → 80 → 100) straight into the `scraping_job` row.
4. Writes results with `save_jobs()` and records a `scraping_session` on completion.

The scraper **writes directly to Postgres**; it never calls the web API.

**Feedback.** The frontend polls `GET /api/scraping/:id` every 2s while a run is active and
invalidates the jobs query when it completes.

**Sources implemented** — all extend `BaseScraper`, which opens `SB(headless=False, headed=True,
uc=True)` and injects session cookies from `cookies/<source>.json`:

- **LinkedIn** (`linkedin.py`, ~188 lines) — the mature one. Builds a parameterised search URL
  (keywords, remote-only `f_WT=2`, full-time, entry→mid-senior, sorted by most recent, `geoId`
  Brazil), scrolls to load the full result list, and extracts full job descriptions.
- **Glassdoor** (`glassdoor.py`) — card-list parsing, caps at 20 results, no description text.
- **Indeed** (`indeed.py`) — card-list parsing, caps at 20 results, no description text.

Both Glassdoor and Indeed rely on hashed CSS class names, so they are the brittle ones and
degrade gracefully (log a warning, return an empty list) when the markup or cookies go stale.

---

## 2. Dashboard & tracking

Auth is Better Auth (email + password). `proxy.ts` — Next.js 16's replacement for
`middleware.ts` — gates every route except `/login`, `/signup`, and `/api/auth/**`. Every
repository query is scoped to `userId`.

The dashboard (`app/page.tsx` → `DashboardContent`) provides:

- **Stats cards** — job counts by status.
- **Jobs table** with source badges, status badges, filtering, sorted newest-first.
- **Scraping controls** — start a run, live progress card, session history.
- **Status transitions** — `new → viewed → applied → interviewing → rejected → offer`, plus a
  dedicated `POST /api/jobs/:id/apply` that stamps `appliedAt`.

### Schema (`web/lib/db/schema.ts`, 3 migrations applied)

| Table | Purpose |
|---|---|
| `user` / `session` / `account` / `verification` | Better Auth |
| `job` | Scraped listings: title, company, location, salary, description, url, source, status, tags[], note, scrapedAt, appliedAt. Unique on `(userId, url)` so re-scrapes dedupe. |
| `scraping_job` | Live progress row the Python service updates during a run. |
| `scraping_session` | Completed-run history (jobs found / new jobs). |

Enums: `job_source` (linkedin, glassdoor, indeed, other), `job_status`, `scraping_job_status`,
`scraping_session_status`.

---

## 3. Resume generation

`scraper/resume.py` builds an **ATS-optimised, single-column PDF** with ReportLab in two
languages from one `CONTENT` dict:

```bash
uv run python resume.py        # English  → resume.pdf
uv run python resume.py --pt   # Portuguese → curriculo.pdf
```

`scraper/ME.md` is the authoritative profile source (contact, stack, experience, education) —
it is what should be read before editing resume content. The generator deliberately avoids
tables, columns, icons, and keyword dumps, keeping keywords inline in experience bullets.

---

## 4. Claude-assisted application bot

Documented in `scraper/APPLY.md`. It uses **no API key** — analysis happens by pasting into a
Claude Code chat.

```bash
# 1. Print new jobs as a prompt
uv run python apply.py --fetch [--limit 5]

# 2. Paste that prompt into Claude Code → it returns a JSON array of per-job analysis

# 3. Save the response as analysis.json

# 4. Generate tailored PDFs and submit
uv run python apply.py --apply analysis.json [--dry-run]
```

Claude's JSON per job carries `score`, `should_apply`, `language` (en/pt), `reason`, plus
tailored overrides — `tailored_title`, `tailored_summary`, and rewritten experience bullets.
`apply.py` deep-copies the base resume content, patches in those overrides, and renders a
**per-job PDF**.

`easy_apply.py` (~302 lines) then drives LinkedIn: opens the job URL in UC-mode Chrome, clicks
**Easy Apply / Candidatura Simplificada**, uploads the tailored PDF, steps through **Next /
Próximo**, and clicks **Submit / Enviar** on the last step. It falls back to just opening the URL
in the default browser if automation fails, and the window stays visible so the user can handle
the extra questions LinkedIn forms sometimes add.

Applied jobs get their status and note written back to the `job` table.

---

## Running it

```bash
docker compose up -d                              # Postgres + RabbitMQ

cd web    && pnpm install && pnpm db:migrate && pnpm dev
cd scraper && uv sync && uv run uvicorn app.main:app --reload
```

- Postgres — `postgresql://jobscraper:jobscraper@localhost:5432/jobscraper`
- RabbitMQ AMQP — `amqp://jobscraper:jobscraper@localhost:5672`
- RabbitMQ UI — http://localhost:15672 (jobscraper / jobscraper)
- Web — http://localhost:3000 · Scraper — http://localhost:8000 (only `GET /health`)

Copy `.env.example` → `.env` in both services first.

---

## State of things

**Solid.** The scrape → store → dashboard loop is complete and real (no mock data). Auth,
migrations, per-user scoping, live progress, and URL dedupe all work. The LinkedIn scraper and
the resume generator are the most developed pieces.

**Manual by design.** The Claude analysis step is a copy/paste handoff, not an API call — even
though `anthropic` is already a dependency in `pyproject.toml`, so wiring it up is an obvious
next step.

**Fragile spots.**

- Cookies are the whole auth story for scraping and expire every few weeks; refreshing them is
  a manual EditThisCookie export into `cookies/<source>.json`.
- Glassdoor and Indeed depend on hashed CSS class names and capture no job description, which
  also means the fit-scoring step has little to work with for those sources.
- Search parameters are hardcoded in each scraper module rather than configurable per user.
- The scraper needs a headed browser, so it can't run on a headless server as-is.
- There are no automated tests in either service.

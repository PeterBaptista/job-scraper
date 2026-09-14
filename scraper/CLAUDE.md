# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from `scraper/`:

```bash
uv sync                                        # Install dependencies
uv run uvicorn app.main:app --reload           # Dev server (port 8000)
uv run uvicorn app.main:app --host 0.0.0.0    # Production
uv run ruff check .                            # Lint
uv run ruff format .                           # Format
```

## Running in Docker

`docker compose up -d` builds and runs the scraper alongside Postgres and RabbitMQ. The
container is the intended way to run the scheduler unattended — on the host it needs a
visible desktop and dies with the terminal.

The browser runs **headed Chrome under Xvfb**, never headless: SeleniumBase UC mode's
anti-detection depends on a real browser, and headless Chrome is trivially fingerprinted.
`BROWSER_XVFB=true` switches this on (`app/config.py` → `settings.browser_xvfb`, consumed
in `app/scrapers/base.py`). Verified inside the container: `navigator.webdriver` is
`False` and the UA carries no `HeadlessChrome` marker.

Container specifics worth keeping:

- **Non-root user.** Chrome's sandbox refuses to run as root; running as `scraper` keeps
  the sandbox on instead of resorting to `--no-sandbox`.
- **`shm_size: 2gb`.** Chrome writes heavily to `/dev/shm`; Docker's 64MB default crashes tabs.
- **Drivers baked at build time** (`sbase get uc_driver`), so a recreate doesn't re-download
  them mid-run.
- **Cookies bind-mounted** from `./scraper/cookies`, so `linkedin.json` can be refreshed
  without rebuilding the image.
- **`.env` is dockerignored.** Secrets arrive via compose `env_file` at runtime rather than
  being baked into the image; compose then overrides `DATABASE_URL` / `RABBITMQ_URL` with
  in-network service names (`postgres`, `rabbitmq`) instead of `localhost`.

Schedule is set in `docker-compose.yml`: 60 min ± 12 (so 48–72 min). Watch the logs with
`docker logs -f job-scraper-scraper-1`.

## Resume rendering

`resume.py` serves two audiences and the priority is fixed: **ATS parsers first, the human
reader second**. Anything that improves the look must leave the extracted text intact.

- `build_with_content(output, content, highlight=None)` is the only rendering path — the CLI
  `build()` delegates to it, so the pipeline and `uv run python resume.py` cannot diverge.
- It returns `{"pages", "tier", "dropped_bullets"}`. One-page fitting runs in tiers: default →
  tighter rhythm → 9.5pt body → drop the oldest role's last bullets. Tier 4 changes what the
  document says, so it is **reported, never silent**, and `app/apply/pipeline.py` re-scores the
  trimmed content so the ATS number in Telegram matches the PDF actually sent.
- `highlight` bolds only the technologies the target posting asks for (from
  `app/apply/ats.py:extract_requirements`). Verified: 12 extra bold runs, extracted text
  byte-identical — emphasis is visual only.
- **Everything interpolated is escaped** via `_esc()`. ReportLab parses paragraph text as XML;
  a bare `&` in an LLM-written bullet ("R&D", "CI/CD & DevOps") used to raise a parse error and
  fail the application. 7 scraped jobs already contain `&`.
- The role/period line uses one invisible `Table`. That is the single ATS risk in the layout and
  it was checked against `pdftotext` (order stays role → period → company). `use_table=False`
  reverts to inline dates if it ever regresses.

Regression check after touching this file — the score must not move:

```bash
uv run python resume.py && uv run python resume.py --pt
# then score the extracted PDF text with app/apply/ats.py against a known posting
```

## Auto-apply pipeline

After each scrape, `app/apply/pipeline.py` scores the newly saved jobs, tailors a resume for
the ones that pass, and asks for approval in Telegram. **Nothing is ever submitted without a
human tapping Approve** — `app/notify/telegram_bot.py` is the only path that enqueues an
application.

```
scrape -> save_jobs -> notify -> score_and_request()
    ATS gate (deterministic) -> tailor (OpenAI) -> truthfulness guard -> PDF
    -> Telegram card + PDF + [Candidatar | Pular]
        tap Candidatar -> apply_jobs queue -> app/apply/worker.py
            note has "simplificada" -> easy_apply.py
            otherwise               -> app/apply/external.py (LLM form mapping)
```

### Pruning is part of tailoring

A tailored resume is for ONE posting, so `app/apply/tailor.py` drops skills and bullets the
role doesn't need. Two guards keep that from backfiring:

- **`ats.over_pruned_requirements()`** — the ATS score is coverage of the posting's
  requirements, so removing something the posting asked for silently lowers it while looking
  tidier. Anything in this list was in the base resume, is wanted by the posting, and went
  missing: always a mistake. It triggers one retry with the terms fed back.
- **Floors and caps** in `_apply_to_content` (3-4 current-role bullets, 2-3 internship, 4-6
  skill categories). Caps exist because the first version, told only to "prune", trimmed detail
  *inside* bullets and returned **more** of them (4 → 6). Tailoring must shorten.

Measured on a real posting: skills 7 → 6 (Testing dropped), internship bullets 4 → 3,
pruned RabbitMQ / Better Auth / Pytest — and the ATS score stayed **81**, unchanged. That is the
design working: prune only what the posting never asked for, and the score cannot move.

### The two checks, and why they are separate

`app/apply/ats.py` scores **deterministically** — keyword coverage of the posting, weighted
toward terms in the job title, penalised for off-discipline signals (ABAP, PowerBuilder, data
engineering, civil/mining). It never calls an LLM: the resume is *written* by one, so letting
the same model grade it would not be a check.

`truthfulness_violations()` is the second, more important check. It rejects any resume
claiming a technology absent from the truthful corpus (`resume.py` CONTENT + `ME.md`). This is
what stops a tailored CV absorbing the posting's requirements — the failure mode where a job
asking for MaterialUI produces a CV claiming MaterialUI. On a violation the tailoring retries
once with the violations fed back, then gives up and skips the job with a reason.

Do not "simplify" the allowlist into a hand-maintained list. It is derived from the base resume
and `ME.md` precisely so it cannot drift from what the candidate actually knows.

### Indeterminate is not a rejection

A posting with an empty description, or one naming no technologies at all, returns
`indeterminate: True` rather than a confident score of 0 — and is skipped with the reason
"cannot score", not "poor fit". Missing data is not evidence of a bad match.

### Threshold

`ATS_MIN_SCORE` defaults to **40**, not a rounder 60, because a real fullstack role the candidate
actually applied to scores 44 — it demands a lot the candidate lacks, which is real signal, but they still
wanted it. 40 admits stretch roles while filtering the 0-score iOS/Golang/data-engineer noise.

### Hard boundaries in the external applier

`app/apply/external.py` aborts and records a reason instead of proceeding when it meets: an
account/signup wall, a password field, a CAPTCHA, a missing resume upload field, or any
**required** field with no truthful answer in `answers.yml`. These are not TODOs — they are
deliberate stops.

### One browser at a time

`app/apply/worker.py:BROWSER_LOCK` is shared with the scrape consumer. SeleniumBase drives one
real Chrome; without the lock a scheduled scrape and an approved application would collide.

### The CV lives in the dashboard, not in the chat

Telegram no longer attaches PDFs. A document in a chat is final — there is no way
to fix a bullet once it has been sent — so cards carry an **✏️ Editar CV** deep link
to `{DASHBOARD_URL}/jobs/{id}/resume` instead, and the tailored *content dict* is
persisted in `resume_draft` so it can be edited and re-rendered.

`app/routers/resume.py` serves that editor. Two rules hold it together:

- **`app/apply/render.py` is the only way to render.** `build_with_content` can
  *remove* content at tier 4, so `render_and_score()` replays the drops before
  scoring. Anything that renders without replaying will report coverage for text
  that is not in the PDF. `generate_cv` used to score before rendering; it no
  longer does.
- **Handlers are sync `def`.** This process shares one event loop with the
  RabbitMQ consumers, the scheduler and the Telegram long-poll. An `async def`
  doing ReportLab would freeze the bot for every keystroke's render.

`/preview` renders into a temp dir; only `/commit` writes into `generated_resumes/`
and repoints `job.resume_path`. That split is what keeps `app/apply/worker.py`
working — it reads that path from disk, so autosave must never churn the file it
may be uploading.

`INTERNAL_API_TOKEN` gates the whole router and a blank value disables it: port
8000 is published to the host, so failing closed is the only safe default. The web
app proxies every call and checks job ownership first, since the scraper has no
sessions of its own.

### Telegram commands

`app/notify/telegram_bot.py` polls `getUpdates` for both button taps and text:

| Input | Effect |
|---|---|
| a LinkedIn job URL | `app/apply/intake.py` scrapes that one posting (`scrape_single`), stores it, scores + tailors it, and sends the approval card |
| `/gaps <url\|id>` | what the posting asks for that the CV doesn't show |
| `/skill <text>` | appends a genuinely-held skill to `ME.md`, widening the truthfulness allowlist |
| `/cv <url\|id> [instructions]` | generates the CV on demand; trailing text becomes extra tailoring instructions |
| `/pending` | jobs awaiting approval |

Every job notification carries **📄 Gerar CV** and **🎯 Lacunas** buttons, so any posting is
actionable — including ones the ATS gate would have skipped. Generation via button or `/cv`
deliberately **bypasses the score threshold**: the reader asked for that specific job, so a low
score is information to show them, not grounds to refuse.

After the CV is sent, the follow-up buttons depend on the route: **✅ Candidatar** only when the
posting is Easy Apply (the only flow this bot can drive end to end), otherwise a **🌐 Abrir vaga**
URL button — offering one-tap submission for an arbitrary external ATS would be a promise it
cannot keep.

The optional instructions on `/cv` are steering, not an override: they are appended after the
HARD RULES, and `truthfulness_violations()` still rejects anything they ask for that the profile
does not support.

**`ME.md` is bind-mounted read-write in `docker-compose.yml`.** Without that mount `/skill`
writes into the container layer — invisible in the repo and lost on the next rebuild. `_append_skill`
inserts into the **Stack** table specifically, bounded to that section; an unbounded search finds
the diversity table's last row further down the file and appends there instead.

`/skill` is the intended way to close an ATS gap: it records the skill in `ME.md`, which is
also the allowlist source, so tailoring may then use it. It exists because the guard would
otherwise strip a skill the candidate really has just because the profile hadn't caught up.

### Two-step confirmation

Tapping **Candidatar** does not submit. It sends a second message requiring **Confirmar
envio**, and only that second tap enqueues to `apply_jobs`. An irreversible outward-facing
action should not be one mis-tap away.

### Settings

| Setting | Default | Purpose |
|---|---|---|
| `APPLY_ENABLED` | `true` | Master switch for scoring + applying |
| `APPLY_DRY_RUN` | `true` | Fill everything, stop before the final submit |
| `ATS_MIN_SCORE` | `40` | Gate for requesting approval |
| `OPENAI_MODEL` | `gpt-5.1` | Resume tailoring — its wording reaches a real employer |
| `OPENAI_FORM_MODEL` | `gpt-5-mini` | External-form field mapping — mechanical label→value work |
| `ATS_GATE_ENABLED` | `false` | When false the score labels the card instead of blocking it, so every job gets a tailored CV |
| `ANSWERS_FILE` | `answers.yml` | Salary/experience answers (git-ignored) |
| `DASHBOARD_URL` | `http://localhost:3000` | Where Telegram cards deep-link for CV editing |
| `INTERNAL_API_TOKEN` | blank | Shared secret for the resume API; blank disables it |

## Architecture

### Startup flow

`app/main.py` uses a FastAPI `lifespan` context. On startup it calls `start_consumer()` which opens a `connect_robust` connection to RabbitMQ and begins consuming the `scrape_jobs` queue. The connection is closed on shutdown.

### Message processing flow

```
RabbitMQ message: {id, user_id, source, time_posted_seconds?}
  → parsed into ScrapeMessage (Pydantic)
  → _process() runs the step loop:
      for each step: asyncio.sleep → update scraping_job row in DB
  → on completion: save_jobs() + save_scraping_session() to DB
  → notify_new_jobs() pushes newly inserted jobs to Telegram
```

`time_posted_seconds` is optional. The web never sends it (its scrapes stay unfiltered);
the scheduler does, and LinkedIn turns it into `f_TPR=r<seconds>`.

SeleniumBase is synchronous — all scraper calls run in `loop.run_in_executor(None, ...)` to avoid blocking the async event loop.

### Key layers

| Layer | Location | Role |
|---|---|---|
| Config | `app/config.py` | pydantic-settings; reads `.env` |
| Models | `app/models/job.py` | `ScrapeMessage`, `ScrapedJob` Pydantic models |
| DB | `app/db/client.py` | psycopg3 helpers: `update_scraping_job`, `save_jobs`, `save_scraping_session`, `insert_scraping_job`, `get_scheduler_user_id` |
| Consumer | `app/queue/consumer.py` | aio-pika consumer; orchestrates step loop and persistence |
| Scrapers | `app/scrapers/` | One class per site extending `BaseScraper`; registry in `__init__.py` |
| Scheduler | `app/scheduler.py` | Background asyncio task; enqueues a jittered hourly scrape |
| Notify | `app/notify/telegram.py` | Pushes newly inserted jobs to Telegram |
| Health | `app/routers/health.py` | `GET /health` — only HTTP endpoint |

### BaseScraper

`app/scrapers/base.py` — all scrapers extend this:

- `scrape()` opens `SB(headless=False, headed=True, uc=True)`, loads cookies, calls `_do_scrape(sb)`
- `_load_cookies(sb)` reads `cookies/<source>.json`, navigates to `_base_url()`, injects cookies, refreshes
- `save_cookies(sb)` exports current driver cookies to `cookies/<source>.json` — call after manual login
- Subclasses must implement `_base_url()` and `_do_scrape(sb) -> list[ScrapedJob]`

### LinkedIn search strategy

`KEYWORD_QUERIES` holds several **plain-text** queries that are run in sequence and merged,
deduped by job id. Do not "improve" this into one quoted boolean query — measured on the same
2h window, `full stack developer react typescript` returned 17 cards while
`("Desenvolvedor Full Stack" OR …) AND (React OR …)` returned 5. LinkedIn matches loose keyword
text generously and strict boolean literally.

The cost of that generosity is precision: loose matching effectively ORs the terms, so
`desenvolvedor` alone pulls in PowerBuilder, ABAP and mining-engineer roles. Relevance is
therefore enforced locally by `is_relevant()` after scraping — a job is kept if `STACK_RE`
matches its **title**, or if its description contains at least `MIN_DESCRIPTION_STACK_TERMS`
(3) distinct stack terms. A single mention is usually incidental. Both numbers were tuned
against 32 real scraped jobs; the log line `Relevance filter: kept N of M` shows the effect.

Three queries means 3× the page loads per run. If LinkedIn starts throttling (symptom: card
counts collapse and `Detail capture` drops toward 0), cut a query before anything else.

### Detail-panel fields

`posted_at` ("há 24 minutos") and `applicants` ("1 candidatura") exist **only** in the detail
panel, never on the card — `_DETAIL_META_JS` reads both in one call after the card click. They
are notification-only fields on `ScrapedJob`, not `job` table columns.

Both depend on selectors LinkedIn revises without notice, so `_do_scrape` logs a
`Detail capture: posted_at N/M, applicants N/M, description N/M` line. Treat a drop here as a
regression signal — it is the difference between "the field is missing" and "nobody noticed".
The panel loads async; the post-click wait is 2.2s because 1.5s left 8 of 31 descriptions empty.

### Adding a new scraper

1. Add the new source to `JobSource` enum in `app/models/job.py`
2. Create `app/scrapers/mysite.py` extending `BaseScraper`
3. Register it in `app/scrapers/__init__.py` `_REGISTRY`
4. Add the same source value to the web's `JobSource` type and DB enum

### Cookies

Drop session cookies (JSON array) at `cookies/<source>.json`. The `cookies/` directory is git-tracked but `*.json` files are git-ignored. Use a browser extension (e.g. EditThisCookie) to export after logging in manually.

### Scheduler & Telegram notifications

`app/scheduler.py` runs as an asyncio task started in the `lifespan` (alongside the consumer).
It **sleeps first**, so a restart never immediately launches Chrome — relevant with `--reload`.

Each tick it resolves the user, inserts a `queued` `scraping_job` row, and publishes to the same
`scrape_jobs` queue the web uses. So scheduled runs appear in the dashboard, and
`prefetch_count=1` means a scheduled run can never open a second browser on top of a manual one.

The interval is jittered (`60 ± 12` min by default → 48–72 min) so runs don't fire on a fixed
clock. Because the window can stretch past an hour, `f_TPR` defaults to `r7200` (2h) rather than
`r3600` — overlap is free since `ON CONFLICT (user_id, url) DO NOTHING` dedupes.

Notifications fire on *every* run, not just scheduled ones. Telegram failures are logged and
swallowed — they must never fail a scrape or nack a message.

| Setting | Default | Purpose |
|---|---|---|
| `SCHEDULER_ENABLED` | `true` | Master switch for the background task |
| `SCHEDULER_INTERVAL_MINUTES` | `60` | Base interval |
| `SCHEDULER_JITTER_MINUTES` | `12` | ± randomisation on the interval |
| `SCHEDULER_SOURCE` | `linkedin` | Only LinkedIn supports `f_TPR` |
| `SCHEDULER_TIME_POSTED_SECONDS` | `7200` | Becomes `f_TPR=r7200` |
| `SCHEDULER_USER_EMAIL` | blank | Blank → the sole DB user; required if there are several |
| `TELEGRAM_TOKEN` / `TELEGRAM_CHAT_ID` | — | Get the chat id via `scripts/telegram_chat_id.py` |
| `TELEGRAM_ENABLED` | `true` | Master switch for notifications |

### DB writes

The scraper writes directly to the shared PostgreSQL instance — it does not call the web API. Tables written:
- `scraping_job` — created by the scheduler (`insert_scraping_job`), progress updates (`update_scraping_job`)
- `job` — scraped listings (`save_jobs`)
- `scraping_session` — completion record (`save_scraping_session`)

`save_jobs` returns the **list of jobs it actually inserted** (via `RETURNING id`), not a count.
This is what makes notifications fire only for genuinely new postings — if it ever goes back to
returning everything scraped, you'd get re-alerted on every job every hour.

# Scraper — Job Scraper Microservice

FastAPI microservice that consumes scraping jobs from RabbitMQ, runs SeleniumBase against LinkedIn, Glassdoor, and Indeed, and writes results directly to the shared PostgreSQL database.

## Stack

- **Framework** — FastAPI with lifespan context
- **Browser automation** — SeleniumBase (headed, UC mode)
- **Queue** — RabbitMQ via aio-pika (async)
- **Database** — PostgreSQL via psycopg3
- **Package manager** — uv

## Running in Docker (recommended)

From the repo root:

```bash
docker compose up -d                    # postgres + rabbitmq + scraper
docker logs -f job-scraper-scraper-1    # watch schedule + scrapes
docker compose restart scraper          # pick up .env or cookie changes
```

The container runs **headed Chrome under Xvfb** — not headless, which LinkedIn
fingerprints easily. Verified inside the container: `navigator.webdriver` is `False`,
the UA has no `HeadlessChrome` marker, and `DISPLAY` points at a real virtual screen.

The schedule lives in `docker-compose.yml` (`SCHEDULER_INTERVAL_MINUTES=30`,
`SCHEDULER_JITTER_MINUTES=8` → fires every 22–38 minutes).

`scraper/.env` is supplied at runtime via compose `env_file` and is deliberately
excluded from the image, and `cookies/` is bind-mounted — so refreshing your LinkedIn
cookies or your Telegram token needs only a `docker compose restart scraper`, never a
rebuild.

Rebuild after changing Python dependencies or the Dockerfile:

```bash
docker compose build scraper && docker compose up -d scraper
```

## Setup (running on the host)

Only needed if you want to run outside Docker. Requires a visible desktop — the
scraper opens real Chrome windows and stops when the terminal closes.

### 1. Environment

Create `.env` in this directory:

```env
RABBITMQ_URL=amqp://jobscraper:jobscraper@localhost:5672
DATABASE_URL=postgresql://jobscraper:jobscraper@localhost:5432/jobscraper
SCRAPE_QUEUE=scrape_jobs
COOKIES_DIR=cookies

TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=

SCHEDULER_ENABLED=true
SCHEDULER_INTERVAL_MINUTES=60
SCHEDULER_JITTER_MINUTES=12
SCHEDULER_TIME_POSTED_SECONDS=7200
SCHEDULER_USER_EMAIL=
```

See `.env.example` for the full annotated list.

### 2. Install dependencies

```bash
uv sync
```

### 3. Cookies

SeleniumBase loads cookies from the `cookies/` directory to bypass login walls. Drop exported cookies (JSON array format from a browser extension like EditThisCookie) at:

```
cookies/linkedin.json
cookies/glassdoor.json
cookies/indeed.json
```

If a cookies file is missing the scraper will proceed without it (results may be limited).

### 4. Telegram notifications

New jobs are pushed to Telegram after every scrape — one message per job, with the title
linked, company, location, how long ago it was posted, how many people have applied, salary
and an Easy Apply marker.

1. Create a bot with [@BotFather](https://t.me/BotFather) → copy the token into
   `TELEGRAM_TOKEN`.
2. Open your bot in Telegram and send it any message (e.g. `hi`).
3. Run the helper and paste the printed id into `TELEGRAM_CHAT_ID`:

```bash
uv run python scripts/telegram_chat_id.py
```

Step 2 is required — Telegram only reveals chats that have messaged the bot, and it drops
those updates after 24h. If `TELEGRAM_CHAT_ID` is blank the scraper logs a warning and skips
notifications; scraping itself is unaffected. Set `TELEGRAM_ENABLED=false` to turn it off.

### 5. Run

```bash
# Development (with auto-reload)
uv run uvicorn app.main:app --reload

# Production
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The service starts, connects to RabbitMQ, and begins consuming the `scrape_jobs` queue. The FastAPI HTTP server only exposes a health check endpoint at `GET /health`.

It also starts the **scheduler**, which queues a LinkedIn scrape roughly every hour (60 ± 12
min of jitter) restricted to jobs posted in the last 2 hours, then pushes anything new to
Telegram. It sleeps before the first run, so starting the service doesn't immediately open
Chrome. Disable it with `SCHEDULER_ENABLED=false`.

Prefer running without `--reload` when the scheduler is on — each reload restarts the timer.

## Architecture

### Message flow

```
web publishes  → RabbitMQ queue: scrape_jobs
  payload: {id, user_id, source}
scheduler publishes ↗
  payload: {id, user_id, source, time_posted_seconds}

consumer picks up message
  → runs scraper for source in thread executor (SeleniumBase is sync)
  → updates scraping_job table with progress at each step
  → on completion: inserts job rows + scraping_session row into DB
  → sends the newly inserted jobs to Telegram
```

`time_posted_seconds` becomes LinkedIn's `f_TPR=r<seconds>` filter. Only the scheduler sets it,
so manual dashboard scrapes stay unfiltered.

### Project structure

```
app/
├── main.py              # FastAPI app, lifespan starts RabbitMQ consumer + scheduler
├── scheduler.py         # Jittered hourly task that enqueues a scrape
├── notify/telegram.py   # Sends newly inserted jobs to Telegram
├── config.py            # pydantic-settings, reads .env
├── models/job.py        # ScrapeMessage, ScrapedJob Pydantic models
├── db/client.py         # psycopg3 helpers: update_scraping_job, save_jobs, save_scraping_session
├── queue/consumer.py    # aio-pika consumer, orchestrates scraping steps
├── scrapers/
│   ├── __init__.py      # get_scraper() registry
│   ├── base.py          # BaseScraper: SB(headless=False, headed=True), cookie loading
│   ├── linkedin.py
│   ├── glassdoor.py
│   └── indeed.py
└── routers/health.py    # GET /health → {status: ok}
scripts/
└── telegram_chat_id.py  # One-off: discover your Telegram chat_id
cookies/                 # Session cookies per site (git-ignored)
```

### Adding a new scraper

1. Create `app/scrapers/mysite.py` extending `BaseScraper`
2. Implement `_base_url()` and `_do_scrape(sb)` 
3. Add the source value to `JobSource` enum in `app/models/job.py`
4. Register it in `app/scrapers/__init__.py`

### Saving cookies after manual login

```python
from seleniumbase import SB
from app.scrapers.linkedin import LinkedInScraper

scraper = LinkedInScraper()
with SB(headless=False, headed=True) as sb:
    sb.open(scraper._base_url())
    input("Log in manually, then press Enter...")
    scraper.save_cookies(sb)
```

### Lint

```bash
uv run ruff check .
uv run ruff format .
```

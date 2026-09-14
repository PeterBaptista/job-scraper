# Job Scraper

A full-stack job tracking application with a Next.js frontend and a Python scraper microservice that communicates via RabbitMQ and shares a PostgreSQL database.

## Services

| Service | Location | Stack |
|---|---|---|
| Web | `web/` | Next.js 16, Drizzle ORM, Better Auth |
| Scraper | `scraper/` | FastAPI, SeleniumBase, aio-pika |
| Database | Docker | PostgreSQL 17 |
| Queue | Docker | RabbitMQ 4 |

## Prerequisites

- Node.js 20+, pnpm
- Python 3.12+, uv
- Docker + Docker Desktop

## Quick start

The scraper now runs as a container too, so `docker compose up -d` brings up the whole
backend — Postgres, RabbitMQ, and the scraper service with its scheduler. It scrapes
LinkedIn every ~30 minutes (jittered 22–38 min) and pushes new jobs to Telegram.

Set `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` in `scraper/.env` first, and drop valid
session cookies at `scraper/cookies/linkedin.json` — both are read at runtime, so
neither needs a rebuild.

```bash
# 1. Start infrastructure + scraper
docker compose up -d
docker logs -f job-scraper-scraper-1   # watch the schedule and scrapes

# 2. Web — install deps, run migrations, start dev server
cd web
pnpm install
pnpm db:migrate
pnpm dev

# 3. Scraper runs in Docker (see step 1). To run it on the host instead:
cd scraper
uv sync
uv run uvicorn app.main:app --reload   # needs a visible desktop; opens Chrome windows
```

Running the scraper on the host requires a real display and dies with the terminal —
the container uses Xvfb, so prefer it for anything unattended.

See `web/README.md` and `scraper/README.md` for full details on each service.

## Environment

Copy and fill in secrets before running:

```bash
cp web/.env.example web/.env
cp scraper/.env.example scraper/.env
```

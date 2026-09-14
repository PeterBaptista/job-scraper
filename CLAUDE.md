# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo structure

```
job-scraper/
├── web/        — Next.js 16 frontend (App Router)
├── scraper/    — FastAPI scraper microservice
└── docker-compose.yml  — PostgreSQL 17 + RabbitMQ 4
```

## Infrastructure

```bash
docker compose up -d    # start Postgres + RabbitMQ
docker compose down     # stop
docker compose down -v  # stop and wipe volumes
```

- **Postgres**: `postgresql://jobscraper:jobscraper@localhost:5432/jobscraper`
- **RabbitMQ AMQP**: `amqp://jobscraper:jobscraper@localhost:5672`
- **RabbitMQ UI**: `http://localhost:15672` (jobscraper / jobscraper)

## Running both services

```bash
# Terminal 1
cd web && pnpm dev

# Terminal 2
cd scraper && uv run uvicorn app.main:app --reload
```

See `web/CLAUDE.md` and `scraper/CLAUDE.md` for service-specific guidance.

## Resume generation

The candidate's full profile (stack, experience, education) is in **`scraper/ME.md`** (git-ignored; template: `scraper/ME.example.md`, contact details in `scraper/profile.local.json`) — read it before editing or generating a resume.

Resume content lives in one folder per stack; `resume.py` only renders it.

```
scraper/resumes/
├── example/content.py      — committed placeholder template
├── clean/content.py        — personal base resume (git-ignored); pipeline tailors from this
├── php-laravel/content.py  — EXTENDS = "clean", overrides title/summary/skills/projects
└── <company>/              — per-company variant: content.py + job.md (the posting)
```

For a new posting use the `resume-builder` skill (`.claude/skills/resume-builder/`): it
maps the posting's keywords to ME.md evidence, writes the variant, and scores it with
`score.py` (ATS coverage + truthfulness check).

```bash
cd scraper
uv run python resume.py                            # clean, English
uv run python resume.py --pt                       # clean, Portuguese
uv run python resume.py --stack php-laravel --pt   # a variant
uv run python resume.py --list                     # available stacks
```

PDFs are written into the stack's folder. A variant inherits every key it doesn't define
(per language, shallow), so experience/education facts are written once in `clean`.

When tailoring for a job opportunity:
1. Read `scraper/ME.md` for the authoritative profile data.
2. Pick the closest stack, or copy `resumes/php-laravel/` to a new folder for a new stack.
3. Mirror exact keywords from the job description in `summary` and experience bullets.
4. Match the job title in `title`.
5. Edit both `"en"` and `"pt"` blocks, or only the relevant language.
6. Use `--pt` for Brazilian postings, no flag for international.

# Web — Job Scraper Frontend

Next.js 16 (App Router) dashboard for tracking scraped job opportunities. Handles authentication, job management, and delegates scraping to the scraper microservice via RabbitMQ.

## Stack

- **Framework** — Next.js 16 (App Router)
- **Auth** — Better Auth (email + password)
- **Database** — PostgreSQL via Drizzle ORM
- **Queue** — RabbitMQ via amqplib
- **UI** — shadcn/ui (Radix + Tailwind CSS v4)
- **Data fetching** — TanStack Query

## Setup

### 1. Environment

Create `.env` in this directory:

```env
DATABASE_URL=postgresql://jobscraper:jobscraper@localhost:5432/jobscraper
BETTER_AUTH_SECRET=<random 32+ char string>
BETTER_AUTH_URL=http://localhost:3000
RABBITMQ_URL=amqp://jobscraper:jobscraper@localhost:5672
RABBITMQ_QUEUE=scrape_jobs
```

### 2. Install dependencies

```bash
pnpm install
```

### 3. Database

Make sure the Docker containers are running first (`docker compose up -d` from the repo root).

```bash
# Generate a migration from schema changes
pnpm db:generate

# Apply pending migrations
pnpm db:migrate

# Open Drizzle Studio (DB browser)
pnpm db:studio
```

### 4. Run

```bash
pnpm dev      # Development server on http://localhost:3000
pnpm build    # Production build
pnpm start    # Start production build
pnpm lint     # ESLint
```

## Architecture

### Auth

- Better Auth handles sessions. The `proxy.ts` file (Next.js 16 equivalent of middleware) checks for a session cookie and redirects unauthenticated users to `/login`.
- Server-side session access: `lib/auth/get-session.ts` → `requireSession()`.
- Public routes: `/login`, `/signup`, `/api/auth/**`.

### Data flow

```
UI → POST /api/scraping
  → writes scraping_job row to DB (status: queued)
  → publishes {id, user_id, source} to RabbitMQ

scraper service picks up message → updates scraping_job progress in DB

UI polls GET /api/scraping/:id → reads scraping_job from DB → shows progress bar
```

All state is persisted in PostgreSQL. Restarting the dev server does not lose data.

### Key layers

| Layer | Location | Role |
|---|---|---|
| Auth | `lib/auth/` | Better Auth server + client + session helper |
| Schema | `lib/db/schema.ts` | Drizzle table definitions |
| Repository | `lib/repositories/job.repository.ts` | DB queries scoped to `userId` |
| Services | `lib/services/` | Business logic, delegates to repository |
| Queue | `lib/queue/message-queue.ts` | Publishes to RabbitMQ, reads job status from DB |
| API routes | `app/api/` | Thin handlers — call `requireSession()`, delegate to services |
| Features | `features/` | Co-located components, hooks, API clients per domain |

### Database schema

| Table | Purpose |
|---|---|
| `user`, `session`, `account`, `verification` | Better Auth |
| `job` | Scraped job listings (scoped to user) |
| `scraping_job` | Real-time scraping progress (written by scraper) |
| `scraping_session` | Completed scraping history |

### Migrations

Schema is defined in `lib/db/schema.ts`. After any change:

```bash
pnpm db:generate   # creates a new file in lib/db/migrations/
pnpm db:migrate    # applies it to the database
```

Never edit migration files after they've been applied.

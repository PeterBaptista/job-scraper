import { sql } from 'drizzle-orm';
import {
  boolean,
  integer,
  jsonb,
  pgEnum,
  pgTable,
  text,
  timestamp,
  uniqueIndex,
} from 'drizzle-orm/pg-core';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const jobSourceEnum = pgEnum('job_source', ['linkedin', 'glassdoor', 'indeed', 'other']);

export const jobStatusEnum = pgEnum('job_status', [
  'new',
  'viewed',
  'applied',
  'interviewing',
  'rejected',
  'offer',
]);

export const scrapingSessionStatusEnum = pgEnum('scraping_session_status', [
  'running',
  'completed',
  'failed',
]);

export const scrapingJobStatusEnum = pgEnum('scraping_job_status', [
  'queued',
  'processing',
  'completed',
  'failed',
]);

// ---------------------------------------------------------------------------
// Better Auth tables (required by better-auth)
// ---------------------------------------------------------------------------

export const user = pgTable('user', {
  id: text('id').primaryKey(),
  name: text('name').notNull(),
  email: text('email').notNull().unique(),
  emailVerified: boolean('email_verified').notNull().default(false),
  image: text('image'),
  createdAt: timestamp('created_at').notNull().defaultNow(),
  updatedAt: timestamp('updated_at').notNull().defaultNow(),
});

export const session = pgTable('session', {
  id: text('id').primaryKey(),
  expiresAt: timestamp('expires_at').notNull(),
  token: text('token').notNull().unique(),
  ipAddress: text('ip_address'),
  userAgent: text('user_agent'),
  userId: text('user_id')
    .notNull()
    .references(() => user.id, { onDelete: 'cascade' }),
  createdAt: timestamp('created_at').notNull().defaultNow(),
  updatedAt: timestamp('updated_at').notNull().defaultNow(),
});

export const account = pgTable('account', {
  id: text('id').primaryKey(),
  accountId: text('account_id').notNull(),
  providerId: text('provider_id').notNull(),
  userId: text('user_id')
    .notNull()
    .references(() => user.id, { onDelete: 'cascade' }),
  accessToken: text('access_token'),
  refreshToken: text('refresh_token'),
  idToken: text('id_token'),
  accessTokenExpiresAt: timestamp('access_token_expires_at'),
  refreshTokenExpiresAt: timestamp('refresh_token_expires_at'),
  scope: text('scope'),
  password: text('password'),
  createdAt: timestamp('created_at').notNull().defaultNow(),
  updatedAt: timestamp('updated_at').notNull().defaultNow(),
});

export const verification = pgTable('verification', {
  id: text('id').primaryKey(),
  identifier: text('identifier').notNull(),
  value: text('value').notNull(),
  expiresAt: timestamp('expires_at').notNull(),
  createdAt: timestamp('created_at').default(sql`now()`),
  updatedAt: timestamp('updated_at').default(sql`now()`),
});

// ---------------------------------------------------------------------------
// App tables
// ---------------------------------------------------------------------------

export const job = pgTable('job', {
  id: text('id').primaryKey(),
  title: text('title').notNull(),
  company: text('company').notNull(),
  location: text('location').notNull(),
  salary: text('salary'),
  description: text('description').notNull(),
  url: text('url').notNull(),
  source: jobSourceEnum('source').notNull(),
  status: jobStatusEnum('status').notNull().default('new'),
  tags: text('tags').array().notNull().default(sql`'{}'::text[]`),
  note: text('note'),
  scrapedAt: timestamp('scraped_at').notNull().defaultNow(),
  appliedAt: timestamp('applied_at'),
  // Auto-apply pipeline. apply_state is plain text, not an enum, so new states
  // don't each require their own migration.
  atsScore: integer('ats_score'),
  applyState: text('apply_state'),
  applyReason: text('apply_reason'),
  resumePath: text('resume_path'),
  userId: text('user_id')
    .notNull()
    .references(() => user.id, { onDelete: 'cascade' }),
}, (t) => [
  uniqueIndex('job_user_url_idx').on(t.userId, t.url),
]);

export const scrapingJob = pgTable('scraping_job', {
  id: text('id').primaryKey(),
  source: jobSourceEnum('source').notNull(),
  status: scrapingJobStatusEnum('status').notNull().default('queued'),
  progress: integer('progress').notNull().default(0),
  message: text('message'),
  jobsFound: integer('jobs_found'),
  createdAt: timestamp('created_at').notNull().defaultNow(),
  startedAt: timestamp('started_at'),
  completedAt: timestamp('completed_at'),
  userId: text('user_id')
    .notNull()
    .references(() => user.id, { onDelete: 'cascade' }),
});

export const scrapingSession = pgTable('scraping_session', {
  id: text('id').primaryKey(),
  source: jobSourceEnum('source').notNull(),
  status: scrapingSessionStatusEnum('status').notNull().default('running'),
  jobsFound: integer('jobs_found').notNull().default(0),
  newJobs: integer('new_jobs').notNull().default(0),
  startedAt: timestamp('started_at').notNull().defaultNow(),
  completedAt: timestamp('completed_at'),
  userId: text('user_id')
    .notNull()
    .references(() => user.id, { onDelete: 'cascade' }),
});

// The editable tailored resume for one posting. The PDF is generated from this
// content, so this — not the rendered file — is what a human edits. Before it
// existed the tailored dict was discarded the moment ReportLab finished, which
// is why a generated CV could never be corrected.
//
// Two content columns on purpose: `generatedContent` is the immutable LLM output
// and `content` is the live, hand-edited version, which gives "revert to what the
// AI produced" for free. Full revision history is a deliberate deferral.
export const resumeDraft = pgTable('resume_draft', {
  id: text('id').primaryKey(),
  jobId: text('job_id')
    .notNull()
    .references(() => job.id, { onDelete: 'cascade' }),
  userId: text('user_id')
    .notNull()
    .references(() => user.id, { onDelete: 'cascade' }),
  // 'tailoring' | 'ready' | 'failed' — plain text for the same reason as
  // job.applyState: a new state shouldn't cost a migration.
  status: text('status').notNull().default('tailoring'),
  // 'en' | 'pt' — which base CONTENT block this was tailored from.
  language: text('language').notNull().default('pt'),
  // The resume.py CONTENT shape: title, summary, skills, experience, education.
  // skills stay [category, values] pairs end to end — resume.py destructures them.
  content: jsonb('content'),
  generatedContent: jsonb('generated_content'),
  // tailor()'s _meta: pruned, omitted_requirements, ats_passes, reason. Kept out
  // of `content` because build_with_content only tolerates the keys it knows.
  meta: jsonb('meta'),
  atsScore: integer('ats_score'),
  // Full ats.score() result, so the panel can show matched/missing/off_stack
  // without re-running the scorer on every page load.
  atsDetail: jsonb('ats_detail'),
  extraPrompt: text('extra_prompt'),
  error: text('error'),
  pdfPath: text('pdf_path'),
  // When the draft was last committed to a real PDF on the scraper's disk. If
  // updatedAt is newer, job.resume_path still points at the pre-edit document
  // and applying now would send the wrong CV.
  pdfCommittedAt: timestamp('pdf_committed_at'),
  createdAt: timestamp('created_at').notNull().defaultNow(),
  updatedAt: timestamp('updated_at').notNull().defaultNow(),
}, (t) => [
  uniqueIndex('resume_draft_job_idx').on(t.jobId),
]);

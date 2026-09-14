import { and, desc, eq, ilike, or } from 'drizzle-orm';
import { db } from '@/lib/db/client';
import { job, scrapingSession } from '@/lib/db/schema';
import type { Job, JobFilters, JobStats, JobStatus, ScrapingSession } from '@/lib/types/job.types';

function toJob(row: typeof job.$inferSelect): Job {
  return {
    id: row.id,
    title: row.title,
    company: row.company,
    location: row.location,
    salary: row.salary ?? undefined,
    description: row.description,
    url: row.url,
    source: row.source,
    status: row.status,
    tags: row.tags,
    scrapedAt: row.scrapedAt,
    appliedAt: row.appliedAt ?? undefined,
  };
}

function toScrapingSession(row: typeof scrapingSession.$inferSelect): ScrapingSession {
  return {
    id: row.id,
    source: row.source,
    status: row.status,
    jobsFound: row.jobsFound,
    newJobs: row.newJobs,
    startedAt: row.startedAt,
    completedAt: row.completedAt ?? undefined,
  };
}

export const jobRepository = {
  async findAll(userId: string, filters?: JobFilters): Promise<Job[]> {
    const conditions = [eq(job.userId, userId)];

    if (filters?.source) conditions.push(eq(job.source, filters.source));
    if (filters?.status) conditions.push(eq(job.status, filters.status));
    if (filters?.search) {
      conditions.push(
        or(
          ilike(job.title, `%${filters.search}%`),
          ilike(job.company, `%${filters.search}%`),
          ilike(job.location, `%${filters.search}%`),
        )!,
      );
    }

    const rows = await db
      .select()
      .from(job)
      .where(and(...conditions))
      .orderBy(desc(job.scrapedAt));

    return rows.map(toJob);
  },

  async findById(userId: string, id: string): Promise<Job | undefined> {
    const [row] = await db
      .select()
      .from(job)
      .where(and(eq(job.id, id), eq(job.userId, userId)))
      .limit(1);

    return row ? toJob(row) : undefined;
  },

  async updateStatus(userId: string, id: string, status: JobStatus): Promise<Job | undefined> {
    const [row] = await db
      .update(job)
      .set({
        status,
        ...(status === 'applied' ? { appliedAt: new Date() } : {}),
      })
      .where(and(eq(job.id, id), eq(job.userId, userId)))
      .returning();

    return row ? toJob(row) : undefined;
  },

  async getStats(userId: string): Promise<JobStats> {
    const rows = await db
      .select()
      .from(job)
      .where(eq(job.userId, userId));

    return {
      total: rows.length,
      new: rows.filter((j) => j.status === 'new').length,
      applied: rows.filter((j) => j.status === 'applied').length,
      interviewing: rows.filter((j) => j.status === 'interviewing').length,
      rejected: rows.filter((j) => j.status === 'rejected').length,
      offer: rows.filter((j) => j.status === 'offer').length,
    };
  },

  async createJobs(userId: string, jobs: Omit<Job, 'id'>[]): Promise<Job[]> {
    if (jobs.length === 0) return [];

    const rows = await db
      .insert(job)
      .values(
        jobs.map((j) => ({
          id: crypto.randomUUID(),
          userId,
          title: j.title,
          company: j.company,
          location: j.location,
          salary: j.salary,
          description: j.description,
          url: j.url,
          source: j.source,
          status: j.status,
          tags: j.tags,
          scrapedAt: j.scrapedAt,
          appliedAt: j.appliedAt,
        })),
      )
      .returning();

    return rows.map(toJob);
  },

  async getScrapingSessions(userId: string): Promise<ScrapingSession[]> {
    const rows = await db
      .select()
      .from(scrapingSession)
      .where(eq(scrapingSession.userId, userId))
      .orderBy(desc(scrapingSession.startedAt));

    return rows.map(toScrapingSession);
  },

  async createScrapingSession(
    userId: string,
    data: Omit<ScrapingSession, 'id'>,
  ): Promise<ScrapingSession> {
    const [row] = await db
      .insert(scrapingSession)
      .values({
        id: crypto.randomUUID(),
        userId,
        source: data.source,
        status: data.status,
        jobsFound: data.jobsFound,
        newJobs: data.newJobs,
        startedAt: data.startedAt,
        completedAt: data.completedAt,
      })
      .returning();

    return toScrapingSession(row);
  },
};

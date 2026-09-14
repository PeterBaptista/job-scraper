import amqplib from 'amqplib';
import { eq } from 'drizzle-orm';
import { db } from '@/lib/db/client';
import { scrapingJob } from '@/lib/db/schema';
import type { JobSource, ScrapingJob } from '@/lib/types/job.types';

const QUEUE_NAME = process.env.RABBITMQ_QUEUE ?? 'scrape_jobs';
const RABBITMQ_URL = process.env.RABBITMQ_URL ?? 'amqp://jobscraper:jobscraper@localhost:5672';

export const messageQueue = {
  async publish(userId: string, source: JobSource): Promise<string> {
    const id = `scraping-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

    await db.insert(scrapingJob).values({
      id,
      userId,
      source,
      status: 'queued',
      progress: 0,
      message: 'Queued for processing...',
    });

    const connection = await amqplib.connect(RABBITMQ_URL);
    const channel = await connection.createChannel();
    await channel.assertQueue(QUEUE_NAME, { durable: true });
    channel.sendToQueue(
      QUEUE_NAME,
      Buffer.from(JSON.stringify({ id, user_id: userId, source })),
      { persistent: true },
    );
    await channel.close();
    await connection.close();

    return id;
  },

  async getStatus(id: string): Promise<ScrapingJob | null> {
    const [row] = await db
      .select()
      .from(scrapingJob)
      .where(eq(scrapingJob.id, id))
      .limit(1);

    if (!row) return null;

    return {
      id: row.id,
      source: row.source,
      status: row.status,
      progress: row.progress,
      message: row.message ?? undefined,
      jobsFound: row.jobsFound ?? undefined,
      createdAt: row.createdAt,
      startedAt: row.startedAt ?? undefined,
      completedAt: row.completedAt ?? undefined,
    };
  },

  async getAllActive(): Promise<ScrapingJob[]> {
    const rows = await db
      .select()
      .from(scrapingJob)
      .where(eq(scrapingJob.status, 'queued'));

    return rows.map((row) => ({
      id: row.id,
      source: row.source,
      status: row.status,
      progress: row.progress,
      message: row.message ?? undefined,
      jobsFound: row.jobsFound ?? undefined,
      createdAt: row.createdAt,
      startedAt: row.startedAt ?? undefined,
      completedAt: row.completedAt ?? undefined,
    }));
  },
};

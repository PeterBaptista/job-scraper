import { messageQueue } from '@/lib/queue/message-queue';
import { jobRepository } from '@/lib/repositories/job.repository';
import type { JobSource, ScrapingJob, ScrapingSession } from '@/lib/types/job.types';

export const scrapingService = {
  async startScraping(userId: string, source: JobSource): Promise<string> {
    return messageQueue.publish(userId, source);
  },

  async getScrapingStatus(id: string): Promise<ScrapingJob | null> {
    return messageQueue.getStatus(id);
  },

  async getActiveScrapingJobs(): Promise<ScrapingJob[]> {
    return messageQueue.getAllActive();
  },

  async getScrapingSessions(userId: string): Promise<ScrapingSession[]> {
    return jobRepository.getScrapingSessions(userId);
  },
};

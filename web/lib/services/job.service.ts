import { jobRepository } from '@/lib/repositories/job.repository';
import type { Job, JobFilters, JobStats, JobStatus } from '@/lib/types/job.types';

export const jobService = {
  async getJobs(userId: string, filters?: JobFilters): Promise<Job[]> {
    return jobRepository.findAll(userId, filters);
  },

  async getJobById(userId: string, id: string): Promise<Job | undefined> {
    return jobRepository.findById(userId, id);
  },

  async updateJobStatus(userId: string, id: string, status: JobStatus): Promise<Job> {
    const updated = await jobRepository.updateStatus(userId, id, status);
    if (!updated) throw new Error('Job not found');
    return updated;
  },

  async applyToJob(userId: string, id: string): Promise<Job> {
    const existing = await jobRepository.findById(userId, id);
    if (!existing) throw new Error('Job not found');
    if (existing.status === 'applied') throw new Error('Job already applied');

    const updated = await jobRepository.updateStatus(userId, id, 'applied');
    return updated!;
  },

  async getStats(userId: string): Promise<JobStats> {
    return jobRepository.getStats(userId);
  },
};

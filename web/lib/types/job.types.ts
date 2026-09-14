export type JobSource = 'linkedin' | 'glassdoor' | 'indeed' | 'other';

export type JobStatus = 'new' | 'viewed' | 'applied' | 'interviewing' | 'rejected' | 'offer';

export interface Job {
  id: string;
  title: string;
  company: string;
  location: string;
  salary?: string;
  description: string;
  url: string;
  source: JobSource;
  status: JobStatus;
  scrapedAt: Date;
  appliedAt?: Date;
  tags: string[];
}

export interface JobFilters {
  source?: JobSource;
  status?: JobStatus;
  search?: string;
}

export interface ScrapingSession {
  id: string;
  source: JobSource;
  status: 'running' | 'completed' | 'failed';
  startedAt: Date;
  completedAt?: Date;
  jobsFound: number;
  newJobs: number;
}

export type ScrapingJobStatus = 'queued' | 'processing' | 'completed' | 'failed';

export interface ScrapingJob {
  id: string;
  source: JobSource;
  status: ScrapingJobStatus;
  progress: number;
  message?: string;
  createdAt: Date;
  startedAt?: Date;
  completedAt?: Date;
  jobsFound?: number;
}

export interface JobStats {
  total: number;
  new: number;
  applied: number;
  interviewing: number;
  rejected: number;
  offer: number;
}

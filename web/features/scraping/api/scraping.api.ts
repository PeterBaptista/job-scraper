import type { JobSource, ScrapingJob, ScrapingSession } from '@/lib/types/job.types';

interface GetScrapingSessionsResponse {
  sessions: ScrapingSession[];
}

interface GetActiveScrapingJobsResponse {
  jobs: ScrapingJob[];
}

interface StartScrapingResponse {
  id: string;
  message: string;
}

export async function getScrapingSessions(): Promise<GetScrapingSessionsResponse> {
  const response = await fetch('/api/scraping-sessions');
  
  if (!response.ok) {
    throw new Error('Failed to fetch scraping sessions');
  }
  
  return response.json();
}

export async function getActiveScrapingJobs(): Promise<GetActiveScrapingJobsResponse> {
  const response = await fetch('/api/scraping');
  
  if (!response.ok) {
    throw new Error('Failed to fetch active scraping jobs');
  }
  
  return response.json();
}

export async function startScraping(source: JobSource): Promise<StartScrapingResponse> {
  const response = await fetch('/api/scraping', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source }),
  });
  
  if (!response.ok) {
    throw new Error('Failed to start scraping');
  }
  
  return response.json();
}

export async function getScrapingStatus(id: string): Promise<ScrapingJob> {
  const response = await fetch(`/api/scraping/${id}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch scraping status');
  }
  
  return response.json();
}

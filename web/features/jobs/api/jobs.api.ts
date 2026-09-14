import type { Job, JobFilters, JobStats, JobStatus } from '@/lib/types/job.types';

interface GetJobsResponse {
  jobs: Job[];
  stats: JobStats;
}

export async function getJobs(filters?: JobFilters): Promise<GetJobsResponse> {
  const params = new URLSearchParams();
  
  if (filters?.source) params.set('source', filters.source);
  if (filters?.status) params.set('status', filters.status);
  if (filters?.search) params.set('search', filters.search);
  
  const response = await fetch(`/api/jobs?${params.toString()}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch jobs');
  }
  
  return response.json();
}

export async function getJobById(id: string): Promise<Job> {
  const response = await fetch(`/api/jobs/${id}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch job');
  }
  
  return response.json();
}

export async function updateJobStatus(id: string, status: JobStatus): Promise<Job> {
  const response = await fetch(`/api/jobs/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  
  if (!response.ok) {
    throw new Error('Failed to update job status');
  }
  
  return response.json();
}

export async function applyToJob(id: string): Promise<Job> {
  const response = await fetch(`/api/jobs/${id}/apply`, {
    method: 'POST',
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to apply to job');
  }
  
  return response.json();
}

import { useQuery } from '@tanstack/react-query';
import { getJobs } from '../api/jobs.api';
import type { JobFilters } from '@/lib/types/job.types';

export const JOBS_QUERY_KEY = 'jobs';

export function useJobs(filters?: JobFilters) {
  return useQuery({
    queryKey: [JOBS_QUERY_KEY, filters],
    queryFn: () => getJobs(filters),
  });
}

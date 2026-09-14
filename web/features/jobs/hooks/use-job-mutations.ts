import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateJobStatus, applyToJob } from '../api/jobs.api';
import { JOBS_QUERY_KEY } from './use-jobs';
import type { JobStatus } from '@/lib/types/job.types';

export function useUpdateJobStatus() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: JobStatus }) =>
      updateJobStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [JOBS_QUERY_KEY] });
    },
  });
}

export function useApplyToJob() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => applyToJob(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [JOBS_QUERY_KEY] });
    },
  });
}

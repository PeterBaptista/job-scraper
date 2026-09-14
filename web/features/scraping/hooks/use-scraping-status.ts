import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { getScrapingStatus } from '../api/scraping.api';
import { JOBS_QUERY_KEY } from '@/features/jobs/hooks/use-jobs';

export const SCRAPING_STATUS_QUERY_KEY = 'scraping-status';

interface UseScrapingStatusOptions {
  enabled?: boolean;
}

export function useScrapingStatus(id: string | null, options?: UseScrapingStatusOptions) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: [SCRAPING_STATUS_QUERY_KEY, id],
    queryFn: () => getScrapingStatus(id!),
    enabled: !!id && options?.enabled !== false,
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      return status === 'completed' || status === 'failed' ? false : 2000;
    },
  });

  useEffect(() => {
    if (query.data?.status === 'completed') {
      queryClient.invalidateQueries({ queryKey: [JOBS_QUERY_KEY] });
    }
  }, [query.data?.status, queryClient]);

  return query;
}

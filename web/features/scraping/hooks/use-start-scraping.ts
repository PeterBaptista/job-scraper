import { useMutation, useQueryClient } from '@tanstack/react-query';
import { startScraping } from '../api/scraping.api';
import { SCRAPING_SESSIONS_QUERY_KEY } from './use-scraping-sessions';
import type { JobSource } from '@/lib/types/job.types';

export function useStartScraping() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (source: JobSource) => startScraping(source),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [SCRAPING_SESSIONS_QUERY_KEY] });
    },
  });
}

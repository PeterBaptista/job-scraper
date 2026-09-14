import { useQuery } from '@tanstack/react-query';
import { getScrapingSessions } from '../api/scraping.api';

export const SCRAPING_SESSIONS_QUERY_KEY = 'scraping-sessions';

export function useScrapingSessions() {
  return useQuery({
    queryKey: [SCRAPING_SESSIONS_QUERY_KEY],
    queryFn: getScrapingSessions,
  });
}

import { NextResponse } from 'next/server';
import { ScraperError, ScraperUnavailableError } from '@/lib/services/scraper.client';

/**
 * The same 401/404/500 mapping every other route handler uses, plus the two
 * scraper-specific cases: a down service is a 503 the UI can explain, and a
 * scraper 4xx (bad content, no draft) is passed through rather than flattened
 * into a 500 that hides what went wrong.
 */
export function handleRouteError(error: unknown, context: string) {
  if (error instanceof Error && error.message === 'Unauthorized') {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }
  if (error instanceof Error && error.message === 'Job not found') {
    return NextResponse.json({ error: 'Job not found' }, { status: 404 });
  }
  if (error instanceof ScraperUnavailableError) {
    return NextResponse.json(
      { error: 'O serviço de currículo está fora do ar. Ele roda junto ao scraper.' },
      { status: 503 },
    );
  }
  if (error instanceof ScraperError && error.status < 500) {
    return NextResponse.json({ error: error.message }, { status: error.status });
  }
  console.error(`Error in ${context}:`, error);
  return NextResponse.json({ error: `Failed to ${context}` }, { status: 500 });
}

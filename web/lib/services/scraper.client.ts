/**
 * The only place that knows where the scraper lives.
 *
 * The browser never calls port 8000 directly — every request is proxied through
 * a Next route handler so Better Auth stays the single auth boundary and job
 * ownership is checked before anything reaches a service that has no sessions of
 * its own. The shared token is a second lock on a port published to the host.
 */

const SCRAPER_URL = process.env.SCRAPER_URL ?? 'http://localhost:8000';
const SCRAPER_TOKEN = process.env.SCRAPER_TOKEN ?? '';

export class ScraperUnavailableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ScraperUnavailableError';
  }
}

export class ScraperError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'ScraperError';
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT';
  body?: unknown;
  /** Tailoring is several sequential OpenAI calls; rendering is sub-second. */
  timeoutMs?: number;
}

export async function scraperRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, timeoutMs = 30_000 } = options;

  let response: Response;
  try {
    response = await fetch(`${SCRAPER_URL}${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Token': SCRAPER_TOKEN,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
      cache: 'no-store',
    });
  } catch (error) {
    // A dead scraper is an operational state, not a bug in the request — route
    // handlers turn this into a 503 so the UI can say "the service is down"
    // rather than showing a generic failure.
    throw new ScraperUnavailableError(
      error instanceof Error ? error.message : 'scraper unreachable',
    );
  }

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new ScraperError(detail || response.statusText, response.status);
  }

  return response.json() as Promise<T>;
}

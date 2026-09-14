import { NextRequest, NextResponse } from 'next/server';
import { requireSession } from '@/lib/auth/get-session';
import { jobRepository } from '@/lib/repositories/job.repository';
import { handleRouteError } from '../_shared';

/**
 * Proxies the scraper's SSE tailoring stream.
 *
 * The token never reaches the browser: ownership is checked here with the
 * session, then the shared secret is attached server-side, exactly as the JSON
 * routes do. The body is piped through untouched so events arrive as they are
 * produced rather than being buffered into one response.
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const [{ user }, { id }] = await Promise.all([requireSession(), params]);

    const job = await jobRepository.findById(user.id, id);
    if (!job) return NextResponse.json({ error: 'Job not found' }, { status: 404 });

    const extraPrompt = new URL(request.url).searchParams.get('extraPrompt') ?? '';
    const target = new URL(
      `${process.env.SCRAPER_URL ?? 'http://localhost:8000'}/internal/resume/${id}/tailor/stream`,
    );
    target.searchParams.set('token', process.env.SCRAPER_TOKEN ?? '');
    if (extraPrompt) target.searchParams.set('extra_prompt', extraPrompt);

    const upstream = await fetch(target, {
      headers: { Accept: 'text/event-stream' },
      cache: 'no-store',
      // Tailoring runs several model passes; the default timeout would cut the
      // stream off mid-generation.
      signal: AbortSignal.timeout(10 * 60 * 1000),
    });

    if (!upstream.ok || !upstream.body) {
      return NextResponse.json(
        { error: 'Falha ao iniciar a geração' },
        { status: upstream.status || 502 },
      );
    }

    return new NextResponse(upstream.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        Connection: 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    });
  } catch (error) {
    return handleRouteError(error, 'stream tailoring');
  }
}

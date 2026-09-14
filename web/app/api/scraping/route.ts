import { NextRequest, NextResponse } from 'next/server';
import { scrapingService } from '@/lib/services/scraping.service';
import { requireSession } from '@/lib/auth/get-session';
import type { JobSource } from '@/lib/types/job.types';

const validSources: JobSource[] = ['linkedin', 'glassdoor', 'indeed', 'other'];

export async function POST(request: NextRequest) {
  try {
    const { user } = await requireSession();
    const { source } = (await request.json()) as { source: JobSource };

    if (!source || !validSources.includes(source)) {
      return NextResponse.json({ error: 'Invalid source' }, { status: 400 });
    }

    const id = await scrapingService.startScraping(user.id, source);
    return NextResponse.json({ id, message: 'Scraping job queued successfully' });
  } catch (error) {
    if (error instanceof Error && error.message === 'Unauthorized') {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    console.error('Error starting scraping:', error);
    return NextResponse.json({ error: 'Failed to start scraping' }, { status: 500 });
  }
}

export async function GET() {
  try {
    const activeJobs = await scrapingService.getActiveScrapingJobs();
    return NextResponse.json({ jobs: activeJobs });
  } catch (error) {
    console.error('Error fetching active scraping jobs:', error);
    return NextResponse.json({ error: 'Failed to fetch active scraping jobs' }, { status: 500 });
  }
}

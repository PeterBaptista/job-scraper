import { NextResponse } from 'next/server';
import { scrapingService } from '@/lib/services/scraping.service';
import { requireSession } from '@/lib/auth/get-session';

export async function GET() {
  try {
    const { user } = await requireSession();
    const sessions = await scrapingService.getScrapingSessions(user.id);
    return NextResponse.json({ sessions });
  } catch (error) {
    if (error instanceof Error && error.message === 'Unauthorized') {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    console.error('Error fetching scraping sessions:', error);
    return NextResponse.json({ error: 'Failed to fetch scraping sessions' }, { status: 500 });
  }
}

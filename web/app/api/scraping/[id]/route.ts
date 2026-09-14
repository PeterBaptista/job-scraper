import { NextRequest, NextResponse } from 'next/server';
import { scrapingService } from '@/lib/services/scraping.service';

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await params;
    const status = await scrapingService.getScrapingStatus(id);

    if (!status) {
      return NextResponse.json({ error: 'Scraping job not found' }, { status: 404 });
    }

    return NextResponse.json(status);
  } catch (error) {
    console.error('Error fetching scraping status:', error);
    return NextResponse.json({ error: 'Failed to fetch scraping status' }, { status: 500 });
  }
}

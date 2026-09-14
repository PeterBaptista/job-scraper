import { NextRequest, NextResponse } from 'next/server';
import { jobService } from '@/lib/services/job.service';
import { requireSession } from '@/lib/auth/get-session';
import type { JobFilters } from '@/lib/types/job.types';

export async function GET(request: NextRequest) {
  try {
    const { user } = await requireSession();
    const searchParams = request.nextUrl.searchParams;

    const filters: JobFilters = {};
    const source = searchParams.get('source');
    if (source) filters.source = source as JobFilters['source'];
    const status = searchParams.get('status');
    if (status) filters.status = status as JobFilters['status'];
    const search = searchParams.get('search');
    if (search) filters.search = search;

    const [jobs, stats] = await Promise.all([
      jobService.getJobs(user.id, filters),
      jobService.getStats(user.id),
    ]);

    return NextResponse.json({ jobs, stats });
  } catch (error) {
    if (error instanceof Error && error.message === 'Unauthorized') {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    console.error('Error fetching jobs:', error);
    return NextResponse.json({ error: 'Failed to fetch jobs' }, { status: 500 });
  }
}

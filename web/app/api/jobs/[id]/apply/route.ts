import { NextRequest, NextResponse } from 'next/server';
import { jobService } from '@/lib/services/job.service';
import { requireSession } from '@/lib/auth/get-session';

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const [{ user }, { id }] = await Promise.all([requireSession(), params]);
    const updated = await jobService.applyToJob(user.id, id);
    return NextResponse.json(updated);
  } catch (error) {
    if (error instanceof Error && error.message === 'Unauthorized') {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    if (error instanceof Error && error.message === 'Job not found') {
      return NextResponse.json({ error: 'Job not found' }, { status: 404 });
    }
    console.error('Error applying to job:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to apply to job' },
      { status: 400 },
    );
  }
}

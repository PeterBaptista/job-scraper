import { NextRequest, NextResponse } from 'next/server';
import { requireSession } from '@/lib/auth/get-session';
import { resumeService } from '@/lib/services/resume.service';
import { handleRouteError } from '../_shared';

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const [{ user }, { id }] = await Promise.all([requireSession(), params]);
    return NextResponse.json(await resumeService.gaps(user.id, id));
  } catch (error) {
    return handleRouteError(error, 'fetch ATS gaps');
  }
}

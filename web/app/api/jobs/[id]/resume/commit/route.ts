import { NextRequest, NextResponse } from 'next/server';
import { requireSession } from '@/lib/auth/get-session';
import { resumeService } from '@/lib/services/resume.service';
import type { ResumeContent } from '@/lib/types/resume.types';
import { handleRouteError } from '../_shared';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const [{ user }, { id }] = await Promise.all([requireSession(), params]);
    const { content } = (await request.json()) as { content?: ResumeContent };

    return NextResponse.json(await resumeService.commit(user.id, id, content as ResumeContent));
  } catch (error) {
    return handleRouteError(error, 'commit resume');
  }
}

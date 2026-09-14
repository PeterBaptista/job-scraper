import { NextRequest, NextResponse } from 'next/server';
import { requireSession } from '@/lib/auth/get-session';
import { resumeService } from '@/lib/services/resume.service';
import { handleRouteError } from '../_shared';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const [{ user }, { id }] = await Promise.all([requireSession(), params]);
    const lang = new URL(request.url).searchParams.get('lang') ?? undefined;

    return NextResponse.json(await resumeService.reset(user.id, id, lang));
  } catch (error) {
    return handleRouteError(error, 'reset resume draft');
  }
}

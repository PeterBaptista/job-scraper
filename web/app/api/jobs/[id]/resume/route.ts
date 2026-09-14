import { NextRequest, NextResponse } from 'next/server';
import { requireSession } from '@/lib/auth/get-session';
import { resumeService } from '@/lib/services/resume.service';
import type { ResumeContent } from '@/lib/types/resume.types';
import { handleRouteError } from './_shared';

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const [{ user }, { id }] = await Promise.all([requireSession(), params]);
    const draft = await resumeService.getDraft(user.id, id);

    // Null rather than 404: "no CV yet" is the normal first state for a job, and
    // the editor renders an empty state for it, not an error.
    return NextResponse.json(draft);
  } catch (error) {
    return handleRouteError(error, 'fetch resume draft');
  }
}

/** Autosave. Persists edits without rendering, so it stays cheap. */
export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const [{ user }, { id }] = await Promise.all([requireSession(), params]);
    const { content } = (await request.json()) as { content: ResumeContent };

    if (!content) {
      return NextResponse.json({ error: 'Content is required' }, { status: 400 });
    }

    return NextResponse.json(await resumeService.saveContent(user.id, id, content));
  } catch (error) {
    return handleRouteError(error, 'save resume draft');
  }
}

/** Start tailoring. Returns immediately; the UI polls GET for the status. */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const [{ user }, { id }] = await Promise.all([requireSession(), params]);
    const body = await request.json().catch(() => ({}));
    const result = await resumeService.startTailoring(user.id, id, body?.extraPrompt);

    return NextResponse.json(result, { status: 202 });
  } catch (error) {
    return handleRouteError(error, 'start tailoring');
  }
}

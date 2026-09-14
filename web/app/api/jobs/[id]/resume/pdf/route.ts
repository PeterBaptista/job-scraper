import { NextRequest, NextResponse } from 'next/server';
import { requireSession } from '@/lib/auth/get-session';
import { jobRepository } from '@/lib/repositories/job.repository';
import { resumeService } from '@/lib/services/resume.service';
import { handleRouteError } from '../_shared';

/**
 * Download the current draft as a PDF.
 *
 * Renders through the preview path (a temp file on the scraper), not by reading
 * `generated_resumes/`: those paths are relative to the scraper container's
 * working directory and the web process cannot reliably resolve them. It also
 * means downloading never disturbs the file the apply worker may be uploading.
 */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const [{ user }, { id }] = await Promise.all([requireSession(), params]);

    const [job, draft] = await Promise.all([
      jobRepository.findById(user.id, id),
      resumeService.getDraft(user.id, id),
    ]);

    if (!job) return NextResponse.json({ error: 'Job not found' }, { status: 404 });
    if (!draft?.content) {
      return NextResponse.json({ error: 'Nenhum CV gerado para esta vaga' }, { status: 404 });
    }

    const { pdf_base64 } = await resumeService.preview(user.id, id, draft.content);
    const bytes = Buffer.from(pdf_base64, 'base64');

    const safe = `${job.company} - ${job.title}`.replace(/[^\p{L}\p{N} .-]/gu, '').slice(0, 80);

    return new NextResponse(new Uint8Array(bytes), {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Length': String(bytes.length),
        'Content-Disposition': `attachment; filename="${process.env.RESUME_FILE_PREFIX ?? 'Resume'} - ${safe}.pdf"`,
        'Cache-Control': 'no-store',
      },
    });
  } catch (error) {
    return handleRouteError(error, 'download resume PDF');
  }
}

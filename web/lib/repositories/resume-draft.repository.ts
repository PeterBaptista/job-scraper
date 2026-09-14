import { and, eq } from 'drizzle-orm';
import { db } from '@/lib/db/client';
import { resumeDraft } from '@/lib/db/schema';
import type {
  AtsResult,
  ResumeContent,
  ResumeDraft,
  ResumeDraftStatus,
  ResumeMeta,
} from '@/lib/types/resume.types';

/** Tailoring that has not reported in this long is presumed dead. */
const TAILORING_TIMEOUT_MS = 5 * 60 * 1000;

function toDraft(row: typeof resumeDraft.$inferSelect): ResumeDraft {
  // A scraper restart mid-tailor leaves the row stuck on 'tailoring' forever;
  // without this the editor would spin indefinitely waiting for a dead task.
  const abandoned =
    row.status === 'tailoring' && Date.now() - row.updatedAt.getTime() > TAILORING_TIMEOUT_MS;

  return {
    id: row.id,
    jobId: row.jobId,
    status: (abandoned ? 'failed' : row.status) as ResumeDraftStatus,
    language: row.language,
    content: row.content as ResumeContent | null,
    generatedContent: row.generatedContent as ResumeContent | null,
    meta: row.meta as ResumeMeta | null,
    atsScore: row.atsScore,
    atsDetail: row.atsDetail as AtsResult | null,
    extraPrompt: row.extraPrompt,
    error: abandoned ? 'A geração não terminou — tente novamente.' : row.error,
    pdfPath: row.pdfPath,
    pdfCommittedAt: row.pdfCommittedAt,
    createdAt: row.createdAt,
    updatedAt: row.updatedAt,
    stale:
      row.pdfCommittedAt !== null && row.updatedAt.getTime() > row.pdfCommittedAt.getTime(),
  };
}

export const resumeDraftRepository = {
  async findByJobId(userId: string, jobId: string): Promise<ResumeDraft | null> {
    const [row] = await db
      .select()
      .from(resumeDraft)
      .where(and(eq(resumeDraft.userId, userId), eq(resumeDraft.jobId, jobId)))
      .limit(1);

    return row ? toDraft(row) : null;
  },
};

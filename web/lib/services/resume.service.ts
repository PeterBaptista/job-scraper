import { jobRepository } from '@/lib/repositories/job.repository';
import { resumeDraftRepository } from '@/lib/repositories/resume-draft.repository';
import { scraperRequest } from '@/lib/services/scraper.client';
import type {
  AnalysisResponse,
  CommitResponse,
  PreviewResponse,
  ResumeContent,
  ResumeDraft,
} from '@/lib/types/resume.types';

/**
 * Ownership is checked here, not in the scraper.
 *
 * The resume API has no notion of sessions — it trusts whoever holds the shared
 * token. That is only safe because every call passes through this function
 * first, so a job id from another user's account never reaches it.
 */
async function assertOwnedJob(userId: string, jobId: string) {
  const job = await jobRepository.findById(userId, jobId);
  if (!job) throw new Error('Job not found');
  return job;
}

export const resumeService = {
  async getDraft(userId: string, jobId: string): Promise<ResumeDraft | null> {
    await assertOwnedJob(userId, jobId);
    return resumeDraftRepository.findByJobId(userId, jobId);
  },

  /** Fire-and-forget: the draft row carries the status and the UI polls for it. */
  async startTailoring(userId: string, jobId: string, extraPrompt?: string) {
    await assertOwnedJob(userId, jobId);
    return scraperRequest<{ status: string }>(`/internal/resume/${jobId}/tailor`, {
      method: 'POST',
      body: { extra_prompt: extraPrompt ?? null },
    });
  },

  async saveContent(userId: string, jobId: string, content: ResumeContent) {
    await assertOwnedJob(userId, jobId);
    return scraperRequest(`/internal/resume/${jobId}/draft`, {
      method: 'PUT',
      body: { content },
    });
  },

  /** Render + score in one call, so the number always describes the document. */
  async preview(userId: string, jobId: string, content: ResumeContent): Promise<PreviewResponse> {
    await assertOwnedJob(userId, jobId);
    return scraperRequest<PreviewResponse>(`/internal/resume/${jobId}/preview`, {
      method: 'POST',
      body: { content },
    });
  },

  /** Score only — cheap enough to run while typing, but pre-fitting. */
  async analyze(userId: string, jobId: string, content?: ResumeContent): Promise<AnalysisResponse> {
    await assertOwnedJob(userId, jobId);
    return scraperRequest<AnalysisResponse>(`/internal/resume/${jobId}/analyze`, {
      method: 'POST',
      body: content ? { content } : {},
    });
  },

  /** The only path that writes a real PDF and repoints job.resume_path. */
  async commit(userId: string, jobId: string, content: ResumeContent): Promise<CommitResponse> {
    await assertOwnedJob(userId, jobId);
    return scraperRequest<CommitResponse>(`/internal/resume/${jobId}/commit`, {
      method: 'POST',
      body: { content },
    });
  },

  async gaps(userId: string, jobId: string) {
    await assertOwnedJob(userId, jobId);
    return scraperRequest(`/internal/resume/${jobId}/gaps`);
  },

  async reset(userId: string, jobId: string, lang?: string) {
    await assertOwnedJob(userId, jobId);
    const query = lang ? `?lang=${encodeURIComponent(lang)}` : '';
    return scraperRequest(`/internal/resume/${jobId}/reset${query}`, { method: 'POST' });
  },
};

import type {
  AnalysisResponse,
  AtsResult,
  CommitResponse,
  PreviewResponse,
  ResumeContent,
  ResumeDraft,
} from '@/lib/types/resume.types';

async function unwrap<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error || fallback);
  }
  return response.json() as Promise<T>;
}

const json = (body: unknown) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export async function getDraft(jobId: string): Promise<ResumeDraft | null> {
  return unwrap(await fetch(`/api/jobs/${jobId}/resume`), 'Falha ao carregar o CV');
}

export async function startTailoring(jobId: string, extraPrompt?: string) {
  return unwrap(
    await fetch(`/api/jobs/${jobId}/resume`, json({ extraPrompt })),
    'Falha ao iniciar a geração',
  );
}

export async function saveDraft(jobId: string, content: ResumeContent) {
  return unwrap(
    await fetch(`/api/jobs/${jobId}/resume`, {
      ...json({ content }),
      method: 'PUT',
    }),
    'Falha ao salvar',
  );
}

export async function previewResume(
  jobId: string,
  content: ResumeContent,
  signal?: AbortSignal,
): Promise<PreviewResponse> {
  return unwrap(
    await fetch(`/api/jobs/${jobId}/resume/preview`, { ...json({ content }), signal }),
    'Falha ao renderizar o PDF',
  );
}

export async function analyzeResume(
  jobId: string,
  content: ResumeContent,
  signal?: AbortSignal,
): Promise<AnalysisResponse> {
  return unwrap(
    await fetch(`/api/jobs/${jobId}/resume/analyze`, { ...json({ content }), signal }),
    'Falha ao analisar',
  );
}

export async function commitResume(
  jobId: string,
  content: ResumeContent,
): Promise<CommitResponse> {
  return unwrap(
    await fetch(`/api/jobs/${jobId}/resume/commit`, json({ content })),
    'Falha ao salvar o CV para candidatura',
  );
}

export async function getGaps(jobId: string): Promise<AtsResult> {
  return unwrap(await fetch(`/api/jobs/${jobId}/resume/gaps`), 'Falha ao buscar lacunas');
}

export async function resetDraft(jobId: string, lang?: string) {
  const query = lang ? `?lang=${encodeURIComponent(lang)}` : '';
  return unwrap(
    await fetch(`/api/jobs/${jobId}/resume/reset${query}`, { method: 'POST' }),
    'Falha ao reverter',
  );
}

export function downloadUrl(jobId: string) {
  return `/api/jobs/${jobId}/resume/pdf`;
}

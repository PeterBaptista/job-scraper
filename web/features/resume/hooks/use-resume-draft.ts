'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import * as api from '../api/resume.api';
import type { ResumeContent } from '@/lib/types/resume.types';

export const RESUME_DRAFT_QUERY_KEY = 'resume-draft';

export function useResumeDraft(jobId: string) {
  return useQuery({
    queryKey: [RESUME_DRAFT_QUERY_KEY, jobId],
    queryFn: () => api.getDraft(jobId),
    // Tailoring is several OpenAI calls, so poll while it runs — the same 2s
    // cadence the scraping progress card already uses. The repository flips a
    // stalled row to 'failed', so this cannot poll forever.
    refetchInterval: (query) => (query.state.data?.status === 'tailoring' ? 2000 : false),
  });
}

export function useStartTailoring(jobId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (extraPrompt?: string) => api.startTailoring(jobId, extraPrompt),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [RESUME_DRAFT_QUERY_KEY, jobId] });
      toast.success('Gerando o CV — isso leva até um minuto.');
    },
    onError: (error: Error) => toast.error(error.message),
  });
}

export function useSaveDraft(jobId: string) {
  return useMutation({
    mutationFn: (content: ResumeContent) => api.saveDraft(jobId, content),
    onError: (error: Error) => toast.error(`Não salvou: ${error.message}`),
  });
}

/** Writes the real PDF and repoints job.resume_path — what Easy Apply uploads. */
export function useCommitResume(jobId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (content: ResumeContent) => api.commitResume(jobId, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [RESUME_DRAFT_QUERY_KEY, jobId] });
      toast.success('CV salvo — é este que será enviado na candidatura.');
    },
    onError: (error: Error) => toast.error(error.message),
  });
}

export function useResetDraft(jobId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (lang?: string) => api.resetDraft(jobId, lang),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [RESUME_DRAFT_QUERY_KEY, jobId] });
      toast.success('Revertido.');
    },
    onError: (error: Error) => toast.error(error.message),
  });
}

export function useGaps(jobId: string, enabled: boolean) {
  return useQuery({
    queryKey: [RESUME_DRAFT_QUERY_KEY, jobId, 'gaps'],
    queryFn: () => api.getGaps(jobId),
    enabled,
  });
}

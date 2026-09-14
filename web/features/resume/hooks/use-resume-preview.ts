'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import * as api from '../api/resume.api';
import type { AtsResult, FitResult, ResumeContent } from '@/lib/types/resume.types';

interface PreviewState {
  pdfUrl: string | null;
  fit: FitResult | null;
  ats: AtsResult | null;
  violations: string[];
  overPruned: string[];
  coverable: string[];
  /** Post-fitting content — what the PDF says, which may be less than was sent. */
  effectiveContent: ResumeContent | null;
  isRendering: boolean;
  error: string | null;
}

const EMPTY: PreviewState = {
  pdfUrl: null,
  fit: null,
  ats: null,
  violations: [],
  overPruned: [],
  coverable: [],
  effectiveContent: null,
  isRendering: false,
  error: null,
};

function toObjectUrl(base64: string): string {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' }));
}

/**
 * Renders the resume on a debounce and keeps the PDF object URL alive exactly as
 * long as the iframe needs it.
 *
 * Object URLs are not garbage collected — every render leaks one unless revoked,
 * and a debounced editor produces one per typing pause. They are revoked on
 * replacement and on unmount.
 */
export function useResumePreview(jobId: string, debounceMs = 900) {
  const [state, setState] = useState<PreviewState>(EMPTY);

  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const urlRef = useRef<string | null>(null);

  const replaceUrl = useCallback((next: string | null) => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = next;
  }, []);

  const run = useCallback(
    async (content: ResumeContent) => {
      // Only the newest render matters; abandoning the in-flight one stops an
      // earlier, slower response from overwriting a newer preview.
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setState((prev) => ({ ...prev, isRendering: true, error: null }));
      try {
        const result = await api.previewResume(jobId, content, controller.signal);
        const url = toObjectUrl(result.pdf_base64);
        replaceUrl(url);
        setState({
          pdfUrl: url,
          fit: result.fit,
          ats: result.ats,
          violations: result.violations,
          overPruned: result.over_pruned,
          coverable: result.coverable ?? [],
          effectiveContent: result.content,
          isRendering: false,
          error: null,
        });
      } catch (error) {
        if (controller.signal.aborted) return;
        setState((prev) => ({
          ...prev,
          isRendering: false,
          error: error instanceof Error ? error.message : 'Falha ao renderizar',
        }));
      }
    },
    [jobId, replaceUrl],
  );

  const schedule = useCallback(
    (content: ResumeContent) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => run(content), debounceMs);
    },
    [run, debounceMs],
  );

  const renderNow = useCallback(
    (content: ResumeContent) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      return run(content);
    },
    [run],
  );

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      abortRef.current?.abort();
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    },
    [],
  );

  return { ...state, schedule, renderNow };
}

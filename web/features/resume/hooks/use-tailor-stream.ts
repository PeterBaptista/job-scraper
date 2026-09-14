'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { parsePartialJson } from '../lib/partial-json';

/** The raw shape the model streams, before _apply_to_content reshapes it. */
export interface StreamingDraft {
  language?: string;
  tailored_title?: string;
  tailored_summary?: string;
  skills?: [string, string][];
  current_role_bullets?: string[];
  internship_bullets?: string[];
  omitted_requirements?: string[];
  pruned?: string[];
  reason?: string;
}

interface StreamState {
  isStreaming: boolean;
  /**
   * The model is done but the refetched draft has not landed yet. Kept separate
   * from `isStreaming` so the view stays up across that gap instead of falling
   * back to the "no CV yet" state for a frame.
   */
  finishing: boolean;
  /** Which optimisation pass the server is on (1..ats_max_passes). */
  pass: number;
  /** Last usable snapshot of the partially written object. */
  partial: StreamingDraft | null;
  /** Characters received — drives a "still working" indicator when fields lag. */
  received: number;
  error: string | null;
}

const IDLE: StreamState = {
  isStreaming: false,
  finishing: false,
  pass: 0,
  partial: null,
  received: 0,
  error: null,
};

export function useTailorStream(jobId: string, onDone: () => void | Promise<unknown>) {
  const [state, setState] = useState<StreamState>(IDLE);
  const abortRef = useRef<AbortController | null>(null);
  const doneRef = useRef(onDone);
  doneRef.current = onDone;

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState(IDLE);
  }, []);

  useEffect(() => () => abortRef.current?.abort(), []);

  const start = useCallback(
    async (extraPrompt?: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setState({ ...IDLE, isStreaming: true, pass: 1 });

      const query = extraPrompt ? `?extraPrompt=${encodeURIComponent(extraPrompt)}` : '';

      try {
        const response = await fetch(`/api/jobs/${jobId}/resume/stream${query}`, {
          headers: { Accept: 'text/event-stream' },
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.error ?? 'Falha ao iniciar a geração');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let jsonText = '';

        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // SSE frames are separated by a blank line; keep the tail, which may
          // be a frame that has not finished arriving.
          const frames = buffer.split('\n\n');
          buffer = frames.pop() ?? '';

          for (const frame of frames) {
            const eventLine = frame.match(/^event: (.+)$/m);
            const dataLine = frame.match(/^data: ([\s\S]*)$/m);
            if (!eventLine || !dataLine) continue;

            const event = eventLine[1].trim();
            let payload: unknown;
            try {
              payload = JSON.parse(dataLine[1]);
            } catch {
              continue;
            }

            if (event === 'pass') {
              // A retry restarts the object, so drop what the last pass wrote.
              jsonText = '';
              setState((prev) => ({ ...prev, pass: payload as number }));
            } else if (event === 'delta') {
              jsonText += payload as string;
              const partial = parsePartialJson<StreamingDraft>(jsonText);
              setState((prev) => ({
                ...prev,
                received: jsonText.length,
                partial: partial ?? prev.partial,
              }));
            } else if (event === 'done') {
              setState((prev) => ({ ...prev, isStreaming: false, finishing: true }));
              try {
                await doneRef.current();
              } finally {
                // Clear `partial` too — leaving it set is what previously pinned
                // the editor on the streaming view until a manual refresh.
                setState(IDLE);
              }
              return;
            } else if (event === 'error') {
              setState({ ...IDLE, error: String(payload) });
              return;
            }
          }
        }

        // The stream ended without a terminal event — treat it as done rather
        // than leaving the view spinning on whatever the last delta was.
        setState((prev) => ({ ...prev, isStreaming: false, finishing: true }));
        try {
          await doneRef.current();
        } finally {
          setState(IDLE);
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        setState({
          ...IDLE,
          error: error instanceof Error ? error.message : 'Falha na geração',
        });
      }
    },
    [jobId],
  );

  return { ...state, start, stop };
}

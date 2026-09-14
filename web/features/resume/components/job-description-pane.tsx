'use client';

import { Building2, Copy, ExternalLink, Link2, MapPin } from 'lucide-react';
import { toast } from 'sonner';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import type { AtsResult } from '@/lib/types/resume.types';
import type { Job } from '@/lib/types/job.types';

/**
 * The posting itself, with the terms the ATS scorer extracted highlighted in
 * place — so a "missing" chip in the analysis panel can be traced back to the
 * sentence it came from, rather than being an opaque keyword.
 */
function Highlighted({ text, ats }: { text: string; ats: AtsResult | null }) {
  if (!ats || ats.indeterminate || (!ats.matched.length && !ats.missing.length)) {
    return <>{text}</>;
  }

  const matched = new Set(ats.matched.map((term) => term.toLowerCase()));
  const missing = new Set(ats.missing.map((term) => term.toLowerCase()));

  // Longest first, so "react native" wins over "react".
  const terms = [...ats.matched, ...ats.missing]
    .filter((term) => term.trim().length > 1)
    .sort((a, b) => b.length - a.length)
    .map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));

  if (terms.length === 0) return <>{text}</>;

  const pattern = new RegExp(`(${terms.join('|')})`, 'gi');

  return (
    <>
      {text.split(pattern).map((part, index) => {
        const lower = part.toLowerCase();
        if (matched.has(lower)) {
          return (
            <mark
              key={index}
              className="rounded bg-success/20 px-0.5 font-medium text-foreground"
            >
              {part}
            </mark>
          );
        }
        if (missing.has(lower)) {
          return (
            <mark
              key={index}
              className="rounded bg-warning/20 px-0.5 font-medium text-foreground"
            >
              {part}
            </mark>
          );
        }
        return <span key={index}>{part}</span>;
      })}
    </>
  );
}

export function JobDescriptionPane({ job, ats }: { job: Job; ats: AtsResult | null }) {
  return (
    <div className="flex h-full flex-col">
      <div className="space-y-3 border-b p-4">
        <div>
          <h2 className="text-base font-semibold">{job.title}</h2>
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Building2 className="h-3 w-3" />
              {job.company}
            </span>
            {job.location && (
              <span className="flex items-center gap-1">
                <MapPin className="h-3 w-3" />
                {job.location}
              </span>
            )}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {job.salary && (
            <Badge variant="secondary" className="border-chart-2/30 bg-chart-2/10 font-normal">
              {job.salary}
            </Badge>
          )}
          <Button asChild variant="outline" size="sm" className="ml-auto">
            <a href={job.url} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="mr-1 h-3.5 w-3.5" />
              Abrir vaga
            </a>
          </Button>
        </div>

        {/* The link as text, not only behind a button — so it can be read,
            checked against the company, and copied. */}
        <div className="flex items-center gap-2 rounded-md border bg-muted/40 px-2 py-1.5">
          <Link2 className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="min-w-0 flex-1 truncate font-mono text-xs text-primary hover:underline"
          >
            {job.url}
          </a>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-6 w-6 shrink-0"
            aria-label="Copiar link da vaga"
            onClick={() => {
              navigator.clipboard
                .writeText(job.url)
                .then(() => toast.success('Link copiado'))
                .catch(() => toast.error('Não consegui copiar'));
            }}
          >
            <Copy className="h-3 w-3" />
          </Button>
        </div>

        {ats && !ats.indeterminate && (
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm bg-success/40" />
              coberto no CV
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm bg-warning/40" />
              faltando
            </span>
          </p>
        )}
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="p-4">
          {job.description?.trim() ? (
            <p className="whitespace-pre-wrap text-sm leading-relaxed">
              <Highlighted text={job.description} ats={ats} />
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              Esta vaga foi salva sem descrição — é por isso que a análise ATS não consegue
              pontuar. Abra a vaga no site para ver os requisitos.
            </p>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

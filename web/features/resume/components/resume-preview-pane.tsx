'use client';

import { FileWarning, Loader2, Scissors } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import type { FitResult } from '@/lib/types/resume.types';

const TIER_LABEL: Record<number, string> = {
  1: 'espaçamento padrão',
  2: 'espaçamento reduzido para caber',
  3: 'corpo 9.5pt para caber',
  4: 'bullets removidos para caber',
  5: 'não coube em uma página',
};

interface Props {
  pdfUrl: string | null;
  fit: FitResult | null;
  isRendering: boolean;
  error: string | null;
}

export function ResumePreviewPane({ pdfUrl, fit, isRendering, error }: Props) {
  return (
    <div className="flex h-full flex-col gap-3 p-4">
      <div className="flex items-center gap-2">
        {fit && (
          <Badge variant={fit.tier >= 4 ? 'destructive' : 'secondary'} className="font-normal">
            {fit.pages} página{fit.pages === 1 ? '' : 's'} · {TIER_LABEL[fit.tier] ?? 'ajustado'}
          </Badge>
        )}
        {isRendering && (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" />
            renderizando
          </span>
        )}
      </div>

      {/* Tier 4 changes what the document says. scraper/CLAUDE.md is explicit
          that this is reported, never silent — so it gets a real alert, not a
          badge the eye slides past. */}
      {fit && fit.dropped_bullets.length > 0 && (
        <Alert variant="destructive">
          <Scissors className="h-4 w-4" />
          <AlertTitle>
            {fit.dropped_bullets.length} bullet
            {fit.dropped_bullets.length === 1 ? '' : 's'} cortado
            {fit.dropped_bullets.length === 1 ? '' : 's'} para caber em uma página
          </AlertTitle>
          <AlertDescription>
            <ul className="list-inside list-disc space-y-1 text-xs">
              {fit.dropped_bullets.map((bullet) => (
                <li key={bullet}>{bullet}</li>
              ))}
            </ul>
            <p className="mt-2 text-xs">
              A nota ATS ao lado já considera o corte — ela descreve o PDF, não o formulário.
              Encurte outros bullets se quiser recuperá-los.
            </p>
          </AlertDescription>
        </Alert>
      )}

      {fit && fit.pages > 1 && (
        <Alert variant="destructive">
          <FileWarning className="h-4 w-4" />
          <AlertTitle>Passou de uma página</AlertTitle>
          <AlertDescription className="text-xs">
            Nem cortando bullets coube. Reduza o resumo ou as skills.
          </AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive">
          <FileWarning className="h-4 w-4" />
          <AlertTitle>Falha ao renderizar</AlertTitle>
          <AlertDescription className="text-xs">{error}</AlertDescription>
        </Alert>
      )}

      <div className="min-h-0 flex-1 overflow-hidden rounded-lg border bg-muted">
        {pdfUrl ? (
          <iframe
            src={`${pdfUrl}#toolbar=0&view=FitH`}
            title="Prévia do currículo"
            className="h-full w-full"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {isRendering ? 'Renderizando…' : 'A prévia aparece aqui.'}
          </div>
        )}
      </div>
    </div>
  );
}

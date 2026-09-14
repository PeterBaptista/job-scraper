'use client';

import { Loader2, Sparkles } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { StreamingDraft } from '../hooks/use-tailor-stream';

/** A field that has not arrived yet gets a shimmer rather than empty space. */
function Pending({ lines = 2 }: { lines?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-3 animate-pulse rounded bg-muted"
          style={{ width: `${92 - i * 14}%`, animationDelay: `${i * 120}ms` }}
        />
      ))}
    </div>
  );
}

/** A caret that trails the text while it is still being written. */
function Caret() {
  return <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-primary align-middle" />;
}

interface Props {
  partial: StreamingDraft | null;
  pass: number;
  maxPasses?: number;
  isStreaming: boolean;
  /** Model finished; the saved draft is still being fetched. */
  finishing?: boolean;
}

export function StreamingPreview({
  partial,
  pass,
  maxPasses = 3,
  isStreaming,
  finishing,
}: Props) {
  const bullets = [
    ...(partial?.current_role_bullets ?? []),
    ...(partial?.internship_bullets ?? []),
  ];

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <div className="flex items-center gap-3">
        <div className="rounded-lg bg-primary/10 p-2">
          {isStreaming || finishing ? (
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
          ) : (
            <Sparkles className="h-5 w-5 text-primary" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">
            {finishing ? 'Renderizando o PDF e medindo o ATS…' : 'Escrevendo o CV para esta vaga…'}
          </p>
          <p className="text-xs text-muted-foreground">
            {finishing
              ? 'Quase lá — abrindo o editor com o resultado.'
              : 'Só usa o que está no seu perfil — nada é inventado para fechar uma lacuna.'}
          </p>
        </div>
        {pass > 1 && !finishing && (
          <Badge variant="secondary" className="shrink-0">
            passe {pass}/{maxPasses}
          </Badge>
        )}
      </div>

      {pass > 1 && !finishing && (
        <p className="rounded-md border border-chart-4/30 bg-chart-4/10 px-3 py-2 text-xs text-muted-foreground">
          A primeira versão deixou requisitos que você tem de fora — reescrevendo para cobri-los.
        </p>
      )}

      <Card className="border-primary/20">
        <CardHeader className="pb-3">
          <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Cargo
          </CardTitle>
        </CardHeader>
        <CardContent>
          {partial?.tailored_title ? (
            <p className="text-lg font-semibold text-chart-1">
              {partial.tailored_title}
              {isStreaming && !partial.tailored_summary && <Caret />}
            </p>
          ) : (
            <Pending lines={1} />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Resumo
          </CardTitle>
        </CardHeader>
        <CardContent>
          {partial?.tailored_summary ? (
            <p className="text-sm leading-relaxed">
              {partial.tailored_summary}
              {isStreaming && !partial.skills?.length && <Caret />}
            </p>
          ) : (
            <Pending lines={4} />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Skills
            {partial?.skills?.length ? (
              <span className="ml-2 text-chart-2">{partial.skills.length}</span>
            ) : null}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {partial?.skills?.length ? (
            partial.skills.map(([category, values], index) => (
              <div key={`${category}-${index}`} className="space-y-1">
                <p className="text-xs font-medium text-chart-2">{category}</p>
                <div className="flex flex-wrap gap-1">
                  {String(values ?? '')
                    .split(',')
                    .map((value) => value.trim())
                    .filter(Boolean)
                    .map((value) => (
                      <Badge
                        key={value}
                        variant="secondary"
                        className="animate-in fade-in zoom-in-95 font-normal"
                      >
                        {value}
                      </Badge>
                    ))}
                </div>
              </div>
            ))
          ) : (
            <Pending lines={3} />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Experiência
            {bullets.length > 0 && <span className="ml-2 text-chart-3">{bullets.length}</span>}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {bullets.length > 0 ? (
            bullets.map((bullet, index) => (
              <p
                key={index}
                className="animate-in fade-in slide-in-from-bottom-1 border-l-2 border-chart-3/40 pl-3 text-sm leading-relaxed"
              >
                {bullet}
              </p>
            ))
          ) : (
            <Pending lines={3} />
          )}
        </CardContent>
      </Card>

      {/* What it refused to claim is the most reassuring thing on screen —
          show it as soon as it exists, not only at the end. */}
      {partial?.omitted_requirements?.length ? (
        <Card className="border-warning/30 bg-warning/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium uppercase tracking-wide text-warning">
              Deixado de fora de propósito
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              A vaga pede, mas seu perfil não confirma — então não foi escrito.
            </p>
            <div className="mt-2 flex flex-wrap gap-1">
              {partial.omitted_requirements.slice(0, 8).map((item) => (
                <Badge key={item} variant="outline" className="font-normal text-xs">
                  {item.length > 40 ? `${item.slice(0, 40)}…` : item}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

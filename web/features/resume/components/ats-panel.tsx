'use client';

import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Check,
  HelpCircle,
  Plus,
  ShieldAlert,
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import type { AtsResult, ResumeMeta } from '@/lib/types/resume.types';

/** Mirrors ATS_MIN_SCORE in scraper/app/config.py. */
const MIN_SCORE = 40;

interface Props {
  ats: AtsResult | null;
  baseAts?: AtsResult | null;
  violations: string[];
  overPruned: string[];
  coverable: string[];
  meta?: ResumeMeta | null;
  /** Category names the "+" can drop a term into. */
  categories: string[];
  onAddTerm: (term: string, categoryIndex: number) => void;
  provisional?: boolean;
  isLoading?: boolean;
}

function Section({
  title,
  count,
  accent,
  children,
}: {
  title: string;
  count?: number;
  accent?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-2">
      <h3 className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <span className={`h-3 w-1 rounded-full ${accent ?? 'bg-border'}`} />
        {title}
        {count !== undefined && <span className="tabular-nums">{count}</span>}
      </h3>
      {children}
    </section>
  );
}

/** A missing requirement, with a menu to drop it into a skill category. */
function MissingTerm({
  term,
  backed,
  categories,
  onAdd,
}: {
  term: string;
  backed: boolean;
  categories: string[];
  onAdd: (categoryIndex: number) => void;
}) {
  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded-md border py-0.5 pl-2 pr-0.5 text-xs ${
        backed
          ? 'border-success/40 bg-success/10 text-foreground'
          : 'border-border bg-muted/40 text-muted-foreground'
      }`}
    >
      {term}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className={`h-5 w-5 ${backed ? 'text-success hover:text-success' : ''}`}
            aria-label={`Adicionar ${term}`}
            disabled={categories.length === 0}
          >
            <Plus className="h-3 w-3" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuLabel className="text-xs font-normal">
            {backed ? (
              <span className="flex items-center gap-1.5 text-success">
                <Check className="h-3 w-3" />
                Seu perfil confirma isso
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-warning">
                <AlertTriangle className="h-3 w-3" />
                Seu perfil não confirma — vai bloquear o envio
              </span>
            )}
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          {categories.map((category, index) => (
            <DropdownMenuItem key={`${category}-${index}`} onClick={() => onAdd(index)}>
              Adicionar em <strong className="ml-1">{category || 'sem nome'}</strong>
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </span>
  );
}

export function AtsPanel({
  ats,
  baseAts,
  violations,
  overPruned,
  coverable,
  meta,
  categories,
  onAddTerm,
  provisional,
  isLoading,
}: Props) {
  if (isLoading || !ats) {
    return (
      <div className="space-y-4 p-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  // An empty description or one naming no technologies is unknown fit, not bad
  // fit. Rendering a red 0 would be a confident answer to an unanswerable question.
  if (ats.indeterminate) {
    return (
      <div className="p-4">
        <Alert>
          <HelpCircle className="h-4 w-4" />
          <AlertTitle>Não dá para pontuar</AlertTitle>
          <AlertDescription>
            {ats.indeterminate_reason === 'job description is empty'
              ? 'Esta vaga foi salva sem descrição, então não há requisitos para comparar.'
              : 'A descrição não cita nenhuma tecnologia identificável.'}{' '}
            Isso é ausência de dados, não um match ruim.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const good = ats.score >= MIN_SCORE;
  const penalty = Math.min(40, 15 * ats.off_stack.length);
  const backed = new Set(coverable.map((term) => term.toLowerCase()));
  const newlyCovered = baseAts
    ? ats.matched.filter((term) => baseAts.missing.includes(term))
    : [];

  return (
    <div className="space-y-6 p-4">
      <div className="rounded-xl border bg-gradient-to-br from-primary/5 to-transparent p-4">
        <div className="flex items-end gap-3">
          <span
            className={`text-5xl font-semibold tabular-nums ${
              good ? 'text-success' : 'text-destructive'
            }`}
          >
            {ats.score}
          </span>
          <span className="pb-1.5 text-sm text-muted-foreground">/ 100</span>
          {provisional && (
            <Badge variant="outline" className="mb-1.5 ml-auto text-warning">
              provisório
            </Badge>
          )}
        </div>
        <Progress value={ats.score} className="mt-3 h-2" />
        <p className="mt-2 text-xs text-muted-foreground">
          {ats.matched.length} de {ats.requirements} requisitos da vaga aparecem no CV.
          {!good && ` Abaixo do corte de ${MIN_SCORE}.`}
        </p>
        {provisional && (
          <p className="mt-1 text-xs text-muted-foreground">
            Calculado antes da renderização — se o ajuste de uma página cortar algo, o número
            final pode cair.
          </p>
        )}
      </div>

      {violations.length > 0 && (
        <Alert variant="destructive">
          <ShieldAlert className="h-4 w-4" />
          <AlertTitle>Fora do seu perfil</AlertTitle>
          <AlertDescription className="space-y-2">
            <p>
              O CV cita {violations.length === 1 ? 'algo que' : 'coisas que'} o{' '}
              <code className="text-xs">ME.md</code> não confirma:{' '}
              <strong>{violations.join(', ')}</strong>.
            </p>
            <p className="text-xs">
              Se você realmente tem essa experiência, adicione ao perfil (ou use{' '}
              <code>/skill</code> no Telegram). Enquanto isso, não dá para salvar para
              candidatura.
            </p>
          </AlertDescription>
        </Alert>
      )}

      {overPruned.length > 0 && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Removido, mas a vaga pede</AlertTitle>
          <AlertDescription>
            <strong>{overPruned.join(', ')}</strong> estava no CV base e a vaga pede — tirar
            baixa a nota sem ganhar nada.
          </AlertDescription>
        </Alert>
      )}

      <Separator />

      <Section title="Faltando" count={ats.missing.length} accent="bg-warning">
        {ats.missing.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nada faltando.</p>
        ) : (
          <>
            <div className="flex flex-wrap gap-1.5">
              {ats.missing.map((term) => (
                <MissingTerm
                  key={term}
                  term={term}
                  backed={backed.has(term.toLowerCase())}
                  categories={categories}
                  onAdd={(categoryIndex) => onAddTerm(term, categoryIndex)}
                />
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              <span className="mr-1 inline-block h-2 w-2 rounded-full bg-success align-middle" />
              {coverable.length} destes seu perfil confirma — adicionar é recuperar um fato. Os
              demais seriam invenção, e o envio fica bloqueado.
            </p>
          </>
        )}
      </Section>

      <Section title="Cobertos" count={ats.matched.length} accent="bg-success">
        <div className="flex flex-wrap gap-1.5">
          {ats.matched.length === 0 && (
            <p className="text-sm text-muted-foreground">Nenhum requisito coberto.</p>
          )}
          {ats.matched.map((term) => (
            <Badge
              key={term}
              variant="secondary"
              className="border-success/30 bg-success/10 font-normal"
            >
              {term}
              {newlyCovered.includes(term) && <ArrowUp className="ml-1 h-3 w-3 text-success" />}
            </Badge>
          ))}
        </div>
        {newlyCovered.length > 0 && (
          <p className="text-xs text-muted-foreground">
            <ArrowUp className="inline h-3 w-3 text-success" /> {newlyCovered.length} que o CV
            base não mostrava.
          </p>
        )}
      </Section>

      {ats.off_stack.length > 0 && (
        <Section title="Fora da sua área" accent="bg-destructive">
          <div className="flex flex-wrap gap-1.5">
            {ats.off_stack.map((term) => (
              <Badge key={term} variant="destructive" className="font-normal">
                {term}
              </Badge>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            <ArrowDown className="inline h-3 w-3" /> −{penalty} pontos. A vaga pede coisas de
            outra disciplina, então a nota bruta ({ats.raw_score}) foi penalizada.
          </p>
        </Section>
      )}

      {(meta?.pruned?.length || meta?.omitted_requirements?.length) && (
        <>
          <Separator />
          <Section title="O que a geração decidiu" accent="bg-chart-4">
            {meta.pruned && meta.pruned.length > 0 && (
              <p className="text-xs text-muted-foreground">
                <strong>Podado</strong> (a vaga não pedia): {meta.pruned.join(' · ')}
              </p>
            )}
            {meta.omitted_requirements && meta.omitted_requirements.length > 0 && (
              <p className="text-xs text-muted-foreground">
                <strong>Omitido de propósito</strong> (a vaga pede, você não tem):{' '}
                {meta.omitted_requirements.join(' · ')}
              </p>
            )}
          </Section>
        </>
      )}
    </div>
  );
}

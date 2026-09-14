'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  Building2,
  Download,
  ExternalLink,
  FileText,
  Loader2,
  RotateCcw,
  Save,
  Sparkles,
} from 'lucide-react';
import Link from 'next/link';
import { useQueryClient } from '@tanstack/react-query';
import { FormProvider, useForm, useWatch } from 'react-hook-form';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/components/ui/resizable';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import type { Job } from '@/lib/types/job.types';
import type { ResumeContent } from '@/lib/types/resume.types';
import * as api from '../api/resume.api';
import {
  RESUME_DRAFT_QUERY_KEY,
  useCommitResume,
  useGaps,
  useResetDraft,
  useResumeDraft,
  useSaveDraft,
} from '../hooks/use-resume-draft';
import { useResumePreview } from '../hooks/use-resume-preview';
import { useTailorStream } from '../hooks/use-tailor-stream';
import { addValue } from '../lib/skill-values';
import { toContent, toFormValues } from '../lib/content-mapping';
import { resumeFormSchema, type ResumeFormValues } from '../lib/resume.schema';
import { AtsPanel } from './ats-panel';
import { ExperienceFields } from './experience-fields';
import { ResumePreviewPane } from './resume-preview-pane';
import { SkillFields } from './skill-fields';
import { JobDescriptionPane } from './job-description-pane';
import { StreamingPreview } from './streaming-preview';
import { TailorEmptyState } from './tailor-empty-state';

const AUTOSAVE_MS = 1200;

export function ResumeEditor({ job }: { job: Job }) {
  const { data: draft, isLoading } = useResumeDraft(job.id);
  const queryClient = useQueryClient();
  const stream = useTailorStream(job.id, () =>
    // Returned, not fired and forgotten: the hook awaits it so the streaming view
    // hands over to an editor that already has the new draft.
    queryClient.invalidateQueries({ queryKey: [RESUME_DRAFT_QUERY_KEY, job.id] }),
  );
  const saveDraft = useSaveDraft(job.id);
  const commitResume = useCommitResume(job.id);
  const resetDraft = useResetDraft(job.id);
  const preview = useResumePreview(job.id);
  const { data: baseAts } = useGaps(job.id, Boolean(draft?.content));

  const [autoPreview, setAutoPreview] = useState(true);
  const baseContentRef = useRef<ResumeContent | null>(null);
  const autosaveRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hydratedFor = useRef<string | null>(null);

  const form = useForm<ResumeFormValues>({
    resolver: zodResolver(resumeFormSchema),
    defaultValues: { title: '', summary: '', skills: [], experience: [] },
  });

  const { reset } = form;

  // Hydrate once per draft revision. Re-running on every render would stomp on
  // what is being typed; keying on updatedAt lets an external change (a Telegram
  // /cv regeneration) still reach the form.
  useEffect(() => {
    if (!draft?.content) return;
    const revision = `${draft.id}:${new Date(draft.updatedAt).getTime()}`;
    if (hydratedFor.current === revision) return;

    hydratedFor.current = revision;
    baseContentRef.current = draft.content;
    reset(toFormValues(draft.content));
    preview.renderNow(draft.content);
    // preview is a stable-enough callback bag; re-running on it would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft?.id, draft?.updatedAt, draft?.content, reset]);

  const values = useWatch({ control: form.control });

  const currentContent = useCallback((): ResumeContent | null => {
    if (!baseContentRef.current) return null;
    return toContent(baseContentRef.current, form.getValues());
  }, [form]);

  // Autosave and re-render on the same edit, on separate clocks: persisting is
  // cheap and should feel immediate, rendering costs a round trip through
  // ReportLab so it waits a little longer.
  useEffect(() => {
    if (!baseContentRef.current || !draft?.content) return;
    if (!form.formState.isDirty) return;

    const content = currentContent();
    if (!content) return;

    if (autosaveRef.current) clearTimeout(autosaveRef.current);
    autosaveRef.current = setTimeout(() => saveDraft.mutate(content), AUTOSAVE_MS);

    if (autoPreview) preview.schedule(content);

    return () => {
      if (autosaveRef.current) clearTimeout(autosaveRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [values, autoPreview, form.formState.isDirty]);

  /** Drop a missing requirement into a skill category, from the ATS panel. */
  const handleAddTerm = useCallback(
    (term: string, categoryIndex: number) => {
      const current = form.getValues(`skills.${categoryIndex}.values`) ?? '';
      form.setValue(`skills.${categoryIndex}.values`, addValue(current, term), {
        shouldDirty: true,
        shouldValidate: true,
      });
    },
    [form],
  );

  if (isLoading) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  // While the model writes, show what it is writing. The spinner it replaces gave
  // no signal about whether anything was happening, or what was being claimed.
  if (stream.isStreaming || stream.finishing) {
    return (
      <StreamingPreview
        partial={stream.partial}
        pass={stream.pass}
        isStreaming={stream.isStreaming}
        finishing={stream.finishing}
      />
    );
  }

  const tailoring = draft?.status === 'tailoring';

  if (!draft?.content || tailoring) {
    return (
      <TailorEmptyState
        onGenerate={(extraPrompt) => stream.start(extraPrompt)}
        isPending={stream.isStreaming}
        isTailoring={tailoring}
        error={stream.error ?? (draft?.status === 'failed' ? draft.error : null)}
      />
    );
  }

  const blockedByTruth = preview.violations.length > 0;

  return (
    <FormProvider {...form}>
      <div className="flex h-[calc(100vh-8rem)] flex-col">
        <div className="flex flex-wrap items-center gap-2 border-b px-4 py-3">
          <div className="mr-auto flex min-w-0 items-center gap-2.5">
            <div className="rounded-md bg-primary/10 p-1.5">
              <FileText className="h-4 w-4 text-primary" />
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-sm font-medium">{job.title}</h1>
              <p className="truncate text-xs text-muted-foreground">{job.company}</p>
            </div>
          </div>

          {draft.stale && (
            <Badge variant="outline" className="border-warning/40 bg-warning/10 text-warning">
              não salvo para candidatura
            </Badge>
          )}

          <div className="flex items-center gap-2">
            <Switch
              id="auto-preview"
              checked={autoPreview}
              onCheckedChange={setAutoPreview}
            />
            <Label htmlFor="auto-preview" className="text-xs text-muted-foreground">
              prévia automática
            </Label>
          </div>

          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={preview.isRendering}
            onClick={() => {
              const content = currentContent();
              if (content) preview.renderNow(content);
            }}
          >
            {preview.isRendering ? (
              <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Sparkles className="mr-1 h-3.5 w-3.5" />
            )}
            Renderizar
          </Button>

          <Button asChild variant="outline" size="sm" title={job.url}>
            <a href={job.url} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="mr-1 h-3.5 w-3.5" />
              Abrir vaga
            </a>
          </Button>

          <Button asChild variant="outline" size="sm">
            <Link href={api.downloadUrl(job.id)} prefetch={false}>
              <Download className="mr-1 h-3.5 w-3.5" />
              Baixar PDF
            </Link>
          </Button>

          <Button
            type="button"
            size="sm"
            disabled={blockedByTruth || commitResume.isPending}
            title={
              blockedByTruth
                ? 'Corrija as afirmações fora do perfil antes de usar este CV numa candidatura'
                : undefined
            }
            onClick={() => {
              const content = currentContent();
              if (content) commitResume.mutate(content);
            }}
          >
            {commitResume.isPending ? (
              <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="mr-1 h-3.5 w-3.5" />
            )}
            Usar na candidatura
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button type="button" variant="ghost" size="icon" aria-label="Mais ações">
                <RotateCcw className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => resetDraft.mutate(undefined)}>
                Reverter para o gerado
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => resetDraft.mutate('pt')}>
                Reverter para o CV base (PT)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => resetDraft.mutate('en')}>
                Reverter para o CV base (EN)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => stream.start()}>
                Gerar de novo
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {draft.stale && (
          <Alert className="rounded-none border-x-0 border-t-0 border-l-2 border-l-warning bg-warning/5">
            <AlertTitle className="text-sm">Suas edições ainda não valem na candidatura</AlertTitle>
            <AlertDescription className="text-xs">
              O PDF que o Easy Apply envia continua sendo o anterior. Clique em{' '}
              <strong>Usar na candidatura</strong> para gravar esta versão.
            </AlertDescription>
          </Alert>
        )}

        <ResizablePanelGroup direction="horizontal" className="min-h-0 flex-1">
          <ResizablePanel defaultSize={45} minSize={30}>
            <ScrollArea className="h-full">
              <div className="space-y-4 p-4">
                <div className="space-y-2">
                  <Label htmlFor="resume-title">Cargo</Label>
                  <Input id="resume-title" {...form.register('title')} />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="resume-summary">Resumo</Label>
                  <Textarea id="resume-summary" rows={6} {...form.register('summary')} />
                </div>

                <Accordion
                  type="multiple"
                  defaultValue={['skills', 'experience']}
                  className="w-full"
                >
                  <AccordionItem value="skills">
                    <AccordionTrigger>Skills</AccordionTrigger>
                    <AccordionContent>
                      <SkillFields />
                    </AccordionContent>
                  </AccordionItem>

                  <AccordionItem value="experience">
                    <AccordionTrigger>Experiência</AccordionTrigger>
                    <AccordionContent className="space-y-3">
                      {form.getValues('experience').map((_, index) => (
                        <ExperienceFields key={index} index={index} />
                      ))}
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              </div>
            </ScrollArea>
          </ResizablePanel>

          <ResizableHandle withHandle />

          <ResizablePanel defaultSize={55} minSize={30}>
            <Tabs defaultValue="preview" className="flex h-full flex-col">
              <TabsList className="mx-4 mt-3 w-fit">
                <TabsTrigger value="preview">
                  <FileText className="mr-1.5 h-3.5 w-3.5" />
                  Prévia
                </TabsTrigger>
                <TabsTrigger value="ats">
                  Análise ATS
                  {preview.ats && !preview.ats.indeterminate && (
                    <Badge
                      variant="secondary"
                      className={`ml-2 tabular-nums ${
                        preview.ats.score >= 40
                          ? 'border-success/30 bg-success/15 text-success'
                          : 'border-destructive/30 bg-destructive/15 text-destructive'
                      }`}
                    >
                      {preview.ats.score}
                    </Badge>
                  )}
                </TabsTrigger>
                <TabsTrigger value="job">
                  <Building2 className="mr-1.5 h-3.5 w-3.5" />
                  Vaga
                </TabsTrigger>
              </TabsList>

              <TabsContent value="preview" className="mt-0 min-h-0 flex-1">
                <ResumePreviewPane
                  pdfUrl={preview.pdfUrl}
                  fit={preview.fit}
                  isRendering={preview.isRendering}
                  error={preview.error}
                />
              </TabsContent>

              <TabsContent value="ats" className="mt-0 min-h-0 flex-1 overflow-auto">
                <AtsPanel
                  ats={preview.ats ?? draft.atsDetail}
                  baseAts={baseAts}
                  violations={preview.violations}
                  overPruned={preview.overPruned}
                  coverable={preview.coverable}
                  meta={draft.meta}
                  categories={(values.skills ?? []).map((s) => s?.category ?? '')}
                  onAddTerm={handleAddTerm}
                  isLoading={!preview.ats && !draft.atsDetail}
                />
              </TabsContent>

              <TabsContent value="job" className="mt-0 min-h-0 flex-1">
                <JobDescriptionPane job={job} ats={preview.ats ?? draft.atsDetail} />
              </TabsContent>
            </Tabs>
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>
    </FormProvider>
  );
}

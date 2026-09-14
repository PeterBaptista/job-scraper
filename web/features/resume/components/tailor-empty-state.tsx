'use client';

import { useState } from 'react';
import { FileText, Loader2, Sparkles } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

interface Props {
  onGenerate: (extraPrompt?: string) => void;
  isPending: boolean;
  isTailoring: boolean;
  error?: string | null;
}

export function TailorEmptyState({ onGenerate, isPending, isTailoring, error }: Props) {
  const [extraPrompt, setExtraPrompt] = useState('');

  if (isTailoring) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-sm font-medium">Gerando o CV para esta vaga…</p>
        <p className="max-w-sm text-xs text-muted-foreground">
          O modelo escreve, a nota ATS é medida e o texto volta para revisão — normalmente até um
          minuto. Pode sair desta página; o progresso fica salvo.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 py-16 text-center">
      <FileText className="h-10 w-10 text-muted-foreground" />
      <div className="space-y-1">
        <h2 className="text-lg font-medium">Nenhum CV para esta vaga ainda</h2>
        <p className="text-sm text-muted-foreground">
          A geração usa só o que está no seu perfil — nada é inventado para fechar uma lacuna.
        </p>
      </div>

      {error && (
        <Alert variant="destructive" className="text-left">
          <AlertTitle>A última tentativa falhou</AlertTitle>
          <AlertDescription className="text-xs">{error}</AlertDescription>
        </Alert>
      )}

      <Textarea
        value={extraPrompt}
        onChange={(event) => setExtraPrompt(event.target.value)}
        placeholder="Instruções extras (opcional) — ex.: enfatize backend, escreva em inglês"
        rows={3}
        className="text-sm"
      />

      <Button onClick={() => onGenerate(extraPrompt || undefined)} disabled={isPending}>
        {isPending ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <Sparkles className="mr-2 h-4 w-4" />
        )}
        Gerar CV
      </Button>
    </div>
  );
}

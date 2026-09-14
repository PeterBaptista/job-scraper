'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Plus, Trash2, X } from 'lucide-react';
import { useFieldArray, useFormContext } from 'react-hook-form';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { ResumeFormValues } from '../lib/resume.schema';
import { RECOMMENDED } from '../lib/resume.schema';
import { addValue, removeValue, splitValues } from '../lib/skill-values';

/**
 * Each skill value is its own chip.
 *
 * The underlying field is still one comma-separated string, because that is what
 * `resume.py` renders — chips are a view over it, not a change to the wire format.
 */
function ValueChips({ index }: { index: number }) {
  const form = useFormContext<ResumeFormValues>();
  const [draft, setDraft] = useState('');

  const raw = form.watch(`skills.${index}.values`) ?? '';
  const values = splitValues(raw);

  const setValues = (next: string) =>
    form.setValue(`skills.${index}.values`, next, {
      shouldDirty: true,
      shouldValidate: true,
    });

  const commitDraft = () => {
    const trimmed = draft.trim().replace(/,+$/, '');
    if (!trimmed) return;
    setValues(addValue(raw, trimmed));
    setDraft('');
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {values.map((value) => (
          <span
            key={value}
            className="group inline-flex items-center gap-1 rounded-md border border-primary/25 bg-primary/10 px-2 py-1 text-xs font-medium text-foreground transition-colors hover:border-destructive/40 hover:bg-destructive/10"
          >
            {value}
            <button
              type="button"
              aria-label={`Remover ${value}`}
              onClick={() => setValues(removeValue(raw, value))}
              className="rounded-sm text-muted-foreground transition-colors hover:text-destructive"
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        {values.length === 0 && (
          <span className="text-xs text-muted-foreground">Nenhum item nesta categoria.</span>
        )}
      </div>

      <Input
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commitDraft}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ',') {
            event.preventDefault();
            commitDraft();
          }
          // Backspace on an empty box removes the last chip — the usual tag-input feel.
          if (event.key === 'Backspace' && !draft && values.length > 0) {
            setValues(removeValue(raw, values[values.length - 1]));
          }
        }}
        placeholder="Adicionar… (Enter)"
        className="h-8 text-xs"
      />
    </div>
  );
}

export function SkillFields() {
  const form = useFormContext<ResumeFormValues>();
  const { fields, append, remove, swap } = useFieldArray({
    control: form.control,
    name: 'skills',
  });

  const [min, max] = RECOMMENDED.skillCategories;
  const offBand = fields.length < min || fields.length > max;

  return (
    <div className="space-y-3">
      {offBand && (
        <p className="rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
          {fields.length} categorias — a geração mira {min}–{max}. Mais que isso vira lista de
          palavras-chave; menos, e a vaga pode não achar o que procura.
        </p>
      )}

      {fields.map((field, index) => (
        <div
          key={field.id}
          className="space-y-2 rounded-lg border border-l-2 border-l-chart-2 p-3"
        >
          <div className="flex gap-1.5">
            <Input
              {...form.register(`skills.${index}.category`)}
              placeholder="Categoria"
              className="h-8 text-sm font-medium"
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              aria-label="Mover para cima"
              disabled={index === 0}
              onClick={() => swap(index, index - 1)}
            >
              <ChevronUp className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              aria-label="Mover para baixo"
              disabled={index === fields.length - 1}
              onClick={() => swap(index, index + 1)}
            >
              <ChevronDown className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-destructive"
              aria-label="Remover categoria"
              onClick={() => remove(index)}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
          <ValueChips index={index} />
        </div>
      ))}

      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => append({ category: '', values: '' })}
      >
        <Plus className="mr-1 h-3.5 w-3.5" />
        Adicionar categoria
      </Button>
    </div>
  );
}

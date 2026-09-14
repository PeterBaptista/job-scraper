'use client';

import { Plus, Trash2 } from 'lucide-react';
import { useFieldArray, useFormContext } from 'react-hook-form';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import type { ResumeFormValues } from '../lib/resume.schema';
import { RECOMMENDED } from '../lib/resume.schema';

/**
 * One component per role: useFieldArray cannot reach two levels of nesting in a
 * single hook, so `experience[i].bullets` needs its own instance.
 */
export function ExperienceFields({ index }: { index: number }) {
  const form = useFormContext<ResumeFormValues>();
  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: `experience.${index}.bullets`,
  });

  const role = form.watch(`experience.${index}`);
  const [min, max] = index === 0 ? RECOMMENDED.currentRoleBullets : RECOMMENDED.olderRoleBullets;
  const offBand = fields.length < min || fields.length > max;

  return (
    <div className="space-y-3 rounded-lg border p-3">
      <div className="flex items-baseline justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{role?.title}</p>
          <p className="truncate text-xs text-muted-foreground">
            {role?.company} · {role?.period}
          </p>
        </div>
        <span
          className={`shrink-0 text-xs ${offBand ? 'text-warning' : 'text-muted-foreground'}`}
        >
          {fields.length} bullet{fields.length === 1 ? '' : 's'}
          {offBand && ` (ideal ${min}–${max})`}
        </span>
      </div>

      {fields.map((field, bulletIndex) => (
        <div key={field.id} className="flex gap-2">
          <Textarea
            {...form.register(`experience.${index}.bullets.${bulletIndex}.text`)}
            rows={3}
            className="text-sm"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Remover bullet"
            onClick={() => remove(bulletIndex)}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ))}

      <Button type="button" variant="outline" size="sm" onClick={() => append({ text: '' })}>
        <Plus className="mr-1 h-3.5 w-3.5" />
        Adicionar bullet
      </Button>
    </div>
  );
}

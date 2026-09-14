import type { ResumeContent } from '@/lib/types/resume.types';
import type { ResumeFormValues } from './resume.schema';

/**
 * react-hook-form's useFieldArray needs objects with stable keys, but resume.py
 * wants `skills` as [category, values] tuples and `bullets` as plain strings.
 * These two functions are the only place that translation happens — keeping the
 * wire format exactly what the renderer destructures.
 */

export function toFormValues(content: ResumeContent): ResumeFormValues {
  return {
    title: content.title ?? '',
    summary: content.summary ?? '',
    skills: (content.skills ?? []).map(([category, values]) => ({ category, values })),
    experience: (content.experience ?? []).map((role) => ({
      title: role.title,
      company: role.company,
      period: role.period,
      bullets: (role.bullets ?? []).map((text) => ({ text })),
    })),
  };
}

export function toContent(base: ResumeContent, values: ResumeFormValues): ResumeContent {
  return {
    ...base,
    title: values.title,
    summary: values.summary,
    skills: values.skills.map(({ category, values: v }) => [category, v]),
    experience: values.experience.map((role, index) => ({
      ...(base.experience?.[index] ?? {}),
      title: role.title,
      company: role.company,
      period: role.period,
      bullets: role.bullets.map((b) => b.text),
    })),
  };
}

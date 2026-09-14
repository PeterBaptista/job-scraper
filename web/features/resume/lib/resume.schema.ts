import { z } from 'zod';

/**
 * Validates shape, not editorial policy.
 *
 * The tailoring floors and caps (3-4 current-role bullets, 4-6 skill categories)
 * exist to constrain an LLM told to "prune" — they are not rules a human editing
 * his own CV should be blocked by. Those are surfaced as soft warnings instead;
 * the only hard constraint is what the one-page fitter reports back.
 */
export const resumeFormSchema = z.object({
  title: z.string().min(1, 'Obrigatório'),
  summary: z.string().min(1, 'Obrigatório'),
  skills: z
    .array(
      z.object({
        category: z.string().min(1, 'Obrigatório'),
        values: z.string().min(1, 'Obrigatório'),
      }),
    )
    .min(1, 'Pelo menos uma categoria'),
  experience: z.array(
    z.object({
      title: z.string(),
      company: z.string(),
      period: z.string(),
      bullets: z.array(z.object({ text: z.string().min(1, 'Obrigatório') })),
    }),
  ),
});

export type ResumeFormValues = z.infer<typeof resumeFormSchema>;

/** Counts the tailoring pipeline aims for. Advisory in the editor. */
export const RECOMMENDED = {
  skillCategories: [4, 6] as const,
  currentRoleBullets: [3, 4] as const,
  olderRoleBullets: [2, 3] as const,
};

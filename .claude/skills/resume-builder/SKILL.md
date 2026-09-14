---
name: resume-builder
description: Build or tailor the candidate's resume for a job posting — pick/extend a stack under scraper/resumes/, mirror the posting's keywords truthfully, render the one-page PDF and score it with the repo's ATS. Use when the user pastes a job description, says "create a resume/CV for <company>", or asks for a new stack variant (e.g. PHP/Laravel, Python/React).
---

# Resume builder

Goal: raise the odds of being shortlisted — pass the ATS keyword filter, then win the
recruiter's 6-second scan — **without claiming anything the candidate hasn't done**. A lie found in
an interview costs more than a missing keyword.

## Layout (read before editing)

```
scraper/ME.md                       — source of truth for every fact. Read it first, always.
scraper/resume.py                   — renderer only (ATS-safe, one page, auto-fit tiers)
scraper/resumes/clean/content.py    — base template (Next.js · TypeScript · Python)
scraper/resumes/<stack>/content.py  — EXTENDS = "clean" + only the keys that change
scraper/resumes/<company>/job.md    — the posting, saved for re-scoring later
```

A variant's keys replace the parent's **per language, shallowly**: override `experience`
and you must restate the whole list (keep periods/companies identical to clean —
`consistency_issues()` checks en vs pt).

## Workflow

1. **Read `scraper/ME.md`** and `resumes/clean/content.py`.
2. **Save the posting** to `scraper/resumes/<company-slug>/job.md` (first line `# Company — Title`).
3. **Extract 15–20 keywords** from the posting: job title, hard skills, tools, methods,
   domain words. Mark each *must* (in "requisitos"/"required", or repeated) or *nice*.
4. **Map every keyword to evidence** in ME.md, in three buckets:
   - **have** — use the posting's exact spelling ("APIs REST", "testes automatizados").
   - **reframe** — true but worded differently in ME.md; rephrase, don't inflate.
   - **gap** — not in ME.md. **Never write it.** List gaps in the variant's docstring and
     tell the user. If the user says they genuinely have it, add it to ME.md first
     (the Stack table), then use it.
5. **Pick the base**: reuse an existing stack if it's close; otherwise create
   `resumes/<company-slug>/content.py` with `EXTENDS = "clean"` (or another stack).
   Language: `pt` for Brazilian postings, `en` for international — tailor that block only.
6. **Write** (priority order — ATS weights the top of the page most):
   - `title`: mirror the posting's title, anchored in the real role ("Engenheiro de
     Software Fullstack — Python · React"). The experience entry keeps the real job title.
   - `summary`: 3–4 sentences, top *must* keywords in the first sentence, one metric.
   - **First bullet of the current role** carries the posting's #1 requirement.
   - Bullets: XYZ — *did X, measured by Y, by doing Z*. Keep existing metrics
     (200+ scrapers, ~500 mil ofertas/dia, 65%, 200%, >80% coverage, ~90%); never invent new ones.
   - Keywords **in context** in bullets beat keyword dumps; the skills table still needs them
     (skills-based filters). Reorder skill rows/items so posting terms come first.
   - Prune what the posting never asks for rather than adding length. One page.
   - Study-level skills (PHP/Laravel) stay labelled "estudos / study projects".
   - Soft skills: show them through a bullet (collaboration with Produto, technical
     discussions), not as adjectives in the skills table.
7. **Render and check**:
   ```bash
   cd scraper
   uv run python resume.py --stack <slug> [--pt]
   uv run python ../.claude/skills/resume-builder/score.py <slug> resumes/<slug>/job.md [--pt]
   uv run python -c "from resume import consistency_issues; print(consistency_issues())"
   pdftotext -layout resumes/<slug>/curriculo.pdf - | head -40
   ```
   Required: `pages=1`, `UNTRUTHFUL: none`, `consistency_issues() == []`, score ≥ clean's.
   Tier 4 means bullets were dropped — shorten instead. `missing` must contain only real gaps.
   The scorer counts tech keywords only — placement, title and domain phrasing are your job.
8. **Report** to the user: PDF path, score vs clean, the gaps (and how to address them in an
   interview or cover letter), and anything you reframed that they should confirm.

## Hard rules

- No technology, title, employer, date, or metric that isn't in ME.md.
- Don't touch `resumes/clean/` for a single posting — the auto-apply pipeline tailors from it.
- Never use two columns, icons, images or tables beyond what `resume.py` already renders.
- `&` and other XML characters are escaped by the renderer — write plain text.

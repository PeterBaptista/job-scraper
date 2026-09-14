"""Generate a resume tailored to one posting, using OpenAI.

The model rewrites emphasis and wording only. It is told, and then separately
checked, that it may not introduce a skill the candidate does not have — mirroring a
posting's keywords is useful; absorbing its requirements is a lie to an employer.
"""

import copy
import json
import logging
import re
from pathlib import Path

from openai import OpenAI

from app.apply import ats
from app.apply.profile import profile_block
from app.config import settings

logger = logging.getLogger(__name__)

_SYSTEM = """You tailor a software engineer's resume to a specific job posting.

HARD RULES:
1. Never introduce a technology, tool, framework or responsibility that does not
   already appear in the candidate profile. If the posting requires something the
   candidate lacks, OMIT it — do not soften, imply, or hedge it.
2. You may reorder, re-emphasise and re-word existing facts, and mirror the
   posting's vocabulary for things the candidate genuinely has. Prefer the
   POSTING'S exact wording over the profile's: if the profile says "Full Stack"
   and the posting says "Fullstack", write "Fullstack"; "React Testing Library"
   becomes "RTL" if that is how the posting writes it. Same fact, their words.
3. Never claim a seniority the profile does not support. Mirror the posting's job
   title only where it is truthful; otherwise use a neutral variant.
4. Write in the language of the posting (pt for Portuguese, en otherwise).

PRUNE WHAT THE ROLE DOES NOT NEED:
5. This resume is for ONE posting. Drop skills and bullets that do not support it.
   A backend-heavy posting does not need the candidate's design tooling; a frontend
   posting does not need his data-pipeline work. Fewer, sharper lines beat a
   complete inventory — the reader has seconds.
6. NEVER drop anything the posting mentions, even in passing, and never drop a
   skill category the posting's requirements fall under. Pruning is for what is
   irrelevant to THIS role, not for shortening at any cost.
7. Target sizes — pruning must make the resume SHORTER, never longer:
     - current role: 3-4 bullets (never more than 4)
     - internship:   2-3 bullets (never more than 3)
     - skills:       4-6 categories (drop whole categories the role does not need)
   Merge or drop rather than expand. If everything looks relevant, still cut the
   weakest item: a focused resume beats a complete one.
8. List what you removed in "pruned" as SHORT items ("RabbitMQ", "Testing category"),
   not sentences.

Return ONLY a JSON object, no markdown fences."""

_SCHEMA_HINT = """{
  "language": "pt" | "en",
  "tailored_title": str,
  "tailored_summary": str,
  "skills": [[category, "comma, separated, values"], ...],
  "current_role_bullets": [str, str, str, str],
  "internship_bullets": [str, str, str, str],
  "omitted_requirements": [str],
  "pruned": [str],
  "reason": str
}"""


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=settings.openai_api_key)


def _ask(messages: list[dict], on_delta=None) -> dict:
    """One tailoring call. With `on_delta`, stream the raw JSON text as it arrives.

    Streaming is for the reader's benefit only — the parsed result is identical
    either way, and every guard still runs on the finished object. Nothing shown
    mid-stream is trusted.
    """
    if on_delta is None:
        resp = _client().chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

    chunks: list[str] = []
    stream = _client().chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        response_format={"type": "json_object"},
        stream=True,
    )
    for event in stream:
        if not event.choices:
            continue
        piece = event.choices[0].delta.content
        if piece:
            chunks.append(piece)
            on_delta(piece)
    return json.loads("".join(chunks))


def tailor(job: dict, extra_prompt: str | None = None,
           on_delta=None, on_pass=None) -> tuple[dict | None, list[str]]:
    """Return (content_dict_ready_for_build, violations).

    content is None when the result could not be made truthful.
    """
    # Hand the model the exact terms the posting wants but the base resume does not
    # show. It may cover ONLY those the profile actually supports — the rest exist
    # to be omitted knowingly, not quietly missed.
    from app.apply import ats as _ats
    from resume import CONTENT
    from resume import CONTENT as _CONTENT

    _base = "\n".join(_ats.resume_text_of(c) for c in _CONTENT.values())
    _gap = _ats.score(_base, job.get("description") or "", job["title"])
    missing_terms = "" if _gap.get("indeterminate") else ", ".join(_gap["missing"][:25])

    user = f"""## Candidate profile (the ONLY facts you may use)
{profile_block()}

## Job posting
title: {job['title']}
company: {job['company']}
location: {job.get('location', '')}
description:
{(job.get('description') or '')[:6000]}

## Terms this posting asks for that the base resume does not currently show
{missing_terms or "(none)"}

Cover the ones the candidate genuinely has, using the posting's wording. Ignore
the rest — never claim one to close the gap. List those you could not cover in
"omitted_requirements".

## Output schema
{_SCHEMA_HINT}"""

    if extra_prompt:
        # Steering, not an override: the HARD RULES stand, and the truthfulness
        # guard still rejects anything this asks for that the profile lacks.
        user += (
            "\n\n## Additional instructions from the candidate\n"
            f"{extra_prompt.strip()}\n"
            "(The HARD RULES above still apply — never claim anything absent "
            "from the profile, whatever these instructions ask for.)"
        )

    messages = [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]

    best: dict | None = None
    best_score = -1
    last_violations: list[str] = []

    for attempt in range(1, max(1, settings.ats_max_passes) + 1):
        if on_pass:
            on_pass(attempt)
        try:
            data = _ask(messages, on_delta)
        except Exception:
            logger.exception("OpenAI tailoring call failed")
            return (best, []) if best else (None, ["openai call failed"])

        content = _apply_to_content(CONTENT, data)
        violations = ats.truthfulness_violations(ats.resume_text_of(content))
        over_pruned = ats.over_pruned_requirements(
            CONTENT, content, job.get("description") or ""
        )

        if violations or over_pruned:
            last_violations = violations or over_pruned
            if attempt >= settings.ats_max_passes:
                break
            problem = (
                f"These are NOT in the candidate profile and must be removed entirely: "
                f"{', '.join(violations)}."
                if violations else
                f"You removed these, but the posting asks for them — put them back and "
                f"prune something irrelevant instead: {', '.join(over_pruned)}."
            )
            messages = _feedback(messages, data, problem)
            continue

        result = ats.score(ats.resume_text_of(content), job.get("description") or "", job["title"])
        if result["score"] > best_score:
            best, best_score = content, result["score"]

        # Only spend another call if something still missing is actually claimable.
        corpus = ats.truthful_corpus()
        coverable = [m for m in result["missing"] if ats._norm(m) in corpus]
        if not coverable or result["score"] >= 95 or attempt >= settings.ats_max_passes:
            logger.info(
                "Tailoring pass %d: ATS %d (best %d), %d coverable term(s) left",
                attempt, result["score"], best_score, len(coverable),
            )
            break

        logger.info(
            "Tailoring pass %d: ATS %d — retrying for %s",
            attempt, result["score"], ", ".join(coverable[:6]),
        )
        messages = _feedback(messages, data, (
            f"ATS coverage is {result['score']}/100. The candidate DOES have these, "
            f"but the resume does not show them: {', '.join(coverable[:12])}. "
            "Work them in using the posting's wording, without inventing anything "
            "and without removing what is already covered. Return corrected JSON."
        ))

    if best is None:
        return None, last_violations

    best["_meta"] = {
        "omitted_requirements": data.get("omitted_requirements", []),
        "pruned": data.get("pruned", []),
        "over_pruned": [],
        "ats_passes": attempt,
        "reason": data.get("reason", ""),
        "language": data.get("language", "pt"),
    }
    return best, []


def _feedback(messages: list[dict], data: dict, instruction: str) -> list[dict]:
    """Keep the thread bounded: system + original request + one correction turn."""
    return messages[:2] + [
        {"role": "assistant", "content": json.dumps(data)},
        {"role": "user", "content": instruction},
    ]


# Floors so pruning sharpens the resume instead of hollowing it out. Enforced here
# rather than trusted to the prompt — a model that over-trims produces a document
# that looks thin to a recruiter, which no ATS score would reveal.
MIN_CURRENT_ROLE_BULLETS = 3
MIN_INTERNSHIP_BULLETS = 2
MIN_SKILL_CATEGORIES = 4

# Caps matter as much as floors: asked only to "prune", the model trimmed detail
# inside bullets and returned MORE of them (4 -> 6). Tailoring must shorten.
MAX_CURRENT_ROLE_BULLETS = 4
MAX_INTERNSHIP_BULLETS = 3
MAX_SKILL_CATEGORIES = 6


def _apply_to_content(CONTENT: dict, data: dict) -> dict:
    lang = data.get("language", "pt")
    base = CONTENT.get(lang, CONTENT["pt"])
    content = copy.deepcopy(base)

    if data.get("tailored_title"):
        content["title"] = data["tailored_title"]
    if data.get("tailored_summary"):
        content["summary"] = data["tailored_summary"]

    skills = [tuple(s) for s in (data.get("skills") or []) if len(s) == 2]
    if len(skills) >= MIN_SKILL_CATEGORIES:
        content["skills"] = skills[:MAX_SKILL_CATEGORIES]
    elif skills:
        # Keep the model's ordering, then top up from the base until the floor is met.
        kept = list(skills)
        chosen = {c.lower() for c, _ in kept}
        for cat, vals in base["skills"]:
            if len(kept) >= MIN_SKILL_CATEGORIES:
                break
            if cat.lower() not in chosen:
                kept.append((cat, vals))
        content["skills"] = kept

    for idx, key, floor, cap in (
        (0, "current_role_bullets", MIN_CURRENT_ROLE_BULLETS, MAX_CURRENT_ROLE_BULLETS),
        (1, "internship_bullets", MIN_INTERNSHIP_BULLETS, MAX_INTERNSHIP_BULLETS),
    ):
        bullets = [b for b in (data.get(key) or []) if b and b.strip()]
        if len(bullets) >= floor:
            content["experience"][idx]["bullets"] = bullets[:cap]
        elif bullets:
            base_bullets = base["experience"][idx]["bullets"]
            topped = list(bullets) + [b for b in base_bullets if b not in bullets]
            content["experience"][idx]["bullets"] = topped[:floor]

    return content


def build_pdf(job: dict, content: dict, out_dir: Path | None = None) -> tuple[Path, dict]:
    """Render the tailored content. Reuses resume.build_with_content.

    Bolds the technologies this posting actually asks for, so a recruiter's eye
    lands on what they are hiring for. Returns (path, fit_result) — the fit result
    reports any bullet the one-page fitting had to drop.
    """
    from resume import build_with_content

    out_dir = out_dir or Path(settings.resume_out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Scoped by job id: the slug alone is company+title, so two postings for the
    # same role at the same company rendered over each other's PDF — and the
    # apply worker then uploaded whichever won.
    slug = re.sub(r"[^a-z0-9]+", "_", (job.get("company", "") + "_" + job["title"]).lower()).strip("_")[:60]
    out = out_dir / f"resume_{slug}_{str(job.get('id', ''))[:8]}.pdf"

    highlight = ats.extract_requirements(job.get("description") or "")
    payload = {k: v for k, v in content.items() if not k.startswith("_")}
    fit = build_with_content(out, payload, highlight=highlight)

    if fit["dropped_bullets"]:
        logger.warning(
            "One-page fit dropped %d bullet(s) for %s: %s",
            len(fit["dropped_bullets"]), job.get("company"), fit["dropped_bullets"],
        )
    if fit["pages"] > 1:
        logger.warning("Resume for %s is %d pages (could not fit)", job.get("company"), fit["pages"])
    return out, fit

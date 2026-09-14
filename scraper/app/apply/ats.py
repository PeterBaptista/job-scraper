"""Mini-ATS: does this tailored resume actually fit the posting, and is it honest?

Deliberately deterministic. The resume is written by an LLM, so letting that same
LLM grade it would not be a check at all — this scores by keyword coverage in plain
Python, and separately refuses any resume claiming a skill the profile doesn't have.
"""

import logging
import re
import unicodedata
from pathlib import Path

logger = logging.getLogger(__name__)

# Skills we can legitimately claim. Seeded from resume.py's skills table and ME.md
# so there is a single factual source; anything outside this is a fabrication.
_EXTRA_KNOWN = {
    "full stack", "fullstack", "full-stack", "front-end", "frontend", "backend",
    "back-end", "rest", "api", "apis", "scraping", "selenium", "seleniumbase",
    "rabbitmq", "async", "agile", "clean code", "clean architecture",
    "solid", "ci/cd", "ci", "cd", "git", "github", "linux", "sql", "orm",
    "microservices", "testing", "unit tests", "integration tests",
}
# Deliberately NOT here: "e2e" (he writes unit/integration tests, not end-to-end)
# and "scrum" (his squad does stand-ups and sprints, but only he can confirm the
# label). Facts about the candidate belong in ME.md, which this list only
# supplements with spelling variants — once the optimiser started hunting for
# coverable terms, an over-permissive entry stopped being theoretical.

# Terms that signal a *different* discipline. Their presence in a posting is a
# strong negative signal for fit even when generic words overlap.
_OFF_STACK = {
    "abap", "sap", "powerbuilder", "centura", "mainframe", "cobol", "delphi",
    "mulesoft", "salesforce", "sharepoint", "dynamics", "oracle forms",
    "data engineer", "data architect", "etl", "spark", "hadoop", "databricks",
    "power bi", "tableau", "qlik", "informatica", "talend",
    "devsecops", "sre", "kubernetes administrator", "dba",
    "engenheiro civil", "engenheiro mecânico", "engenheiro de minas",
    "mecânica", "metalurgia", "mineração", "petróleo",
}

_STOPWORDS = {
    "a", "o", "e", "de", "da", "do", "das", "dos", "para", "com", "em", "no", "na",
    "por", "que", "um", "uma", "os", "as", "ao", "aos", "se", "sua", "seu", "ou",
    "the", "and", "for", "with", "in", "of", "to", "a", "an", "is", "are", "on",
    "you", "your", "we", "our", "will", "be", "as", "at", "it", "this", "that",
    "experiência", "experience", "conhecimento", "knowledge", "anos", "years",
    "boas", "práticas", "practices", "desenvolvimento", "development", "software",
}


def _norm(text: str) -> str:
    """Lowercase, strip accents — 'experiência' and 'experiencia' must match."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def truthful_corpus() -> str:
    """Everything the candidate can truthfully claim, as one blob of text.

    The untailored resume and ME.md *are* the source of truth, so the allowlist is
    derived from them directly rather than maintained as a parallel list that would
    drift the moment a skill is added in one place and not the other.
    """
    parts: list[str] = []

    try:
        from resume import CONTENT
        for lang in CONTENT.values():
            parts.append(resume_text_of(lang))
    except Exception:
        logger.warning("Could not read resume.CONTENT for the skill allowlist", exc_info=True)

    me = Path("ME.md")
    if me.exists():
        parts.append(me.read_text())

    parts.append(" ".join(_EXTRA_KNOWN))
    return _norm("\n".join(parts))


def extract_requirements(description: str) -> list[str]:
    """Technology/skill terms the posting asks for, most-signal first."""
    text = _norm(description)

    # Multi-word tech phrases first so "next.js" doesn't degrade into "next"
    phrases = [
        "next.js", "nextjs", "node.js", "nodejs", "react native", "vue.js",
        "spring boot", "clean architecture", "clean code", "ci/cd", "unit test",
        "integration test", "full stack", "fullstack", "front-end", "frontend",
        "back-end", "backend", "material ui", "materialui", "sql server",
        "power bi", "github actions", "docker compose", "react query",
        "design patterns", "microservices", "microfrontend", "serverless",
        "rest api", "graphql", "web scraping", "pnpm workspaces", "yarn workspaces",
        "solid principles", "design patterns", "arquitetura limpa", "codigo limpo",
    ]
    found: list[str] = [p for p in phrases if p in text]

    # Then single tokens, keeping only plausible tech words
    tokens = re.findall(r"[a-z][a-z0-9\+\#\.]{1,}", text)
    for tok in tokens:
        tok = tok.strip(".")
        if len(tok) < 2 or tok in _STOPWORDS or tok in found:
            continue
        if tok in _TECH_TOKENS:
            found.append(tok)

    # Preserve order, drop duplicates
    seen: set[str] = set()
    return [f for f in found if not (f in seen or seen.add(f))]


_TECH_TOKENS = {
    "react", "typescript", "javascript", "python", "node", "nodejs", "vue", "angular",
    "next", "nestjs", "express", "fastapi", "django", "flask", "graphql", "rest",
    "postgresql", "postgres", "mysql", "mongodb", "dynamodb", "redis", "sql",
    "docker", "kubernetes", "aws", "gcp", "azure", "terraform", "linux", "git",
    "jest", "pytest", "cypress", "playwright", "vitest", "storybook", "vite",
    "tailwind", "css", "html", "sass", "webpack", "prisma", "drizzle", "orm",
    "java", "kotlin", "golang", "rust", "php", "ruby", "csharp", "dotnet", "abap",
    "rabbitmq", "kafka", "celery", "serverless", "lambda", "microservices",
    "pydantic", "zod", "redux", "zustand", "apollo", "selenium", "scraping",
    "agile", "scrum", "kanban", "jira", "figma", "storybook",
    "nestjs", "nest", "turborepo", "pnpm", "monorepo", "monorepos", "nx", "lerna",
    "solid", "kubernetes", "k8s", "helm",
}


# Equivalent spellings of one skill. A posting saying "Postgres" and a resume
# saying "PostgreSQL" describe the same thing; counting that as a miss understates
# the match. Only true equivalents belong here — react/react-native are NOT.
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "postgres": ("postgresql",),
    "postgresql": ("postgres",),
    "node": ("node.js", "nodejs"),
    "nodejs": ("node.js", "node"),
    "next": ("next.js", "nextjs"),
    "nextjs": ("next.js", "next"),
    "nestjs": ("nest.js", "nest"),
    "fullstack": ("full stack", "full-stack"),
    "full stack": ("fullstack", "full-stack"),
    "frontend": ("front-end", "front end"),
    "front-end": ("frontend", "front end"),
    "backend": ("back-end", "back end"),
    "back-end": ("backend", "back end"),
    "k8s": ("kubernetes",),
    "kubernetes": ("k8s",),
    "ci/cd": ("ci-cd", "cicd", "github actions"),
    "typescript": ("ts",),
    "javascript": ("js",),
    "rest": ("rest api", "restful", "apis rest"),
    "unit test": ("unit tests", "testes unitarios"),
    "integration test": ("integration tests", "testes de integracao"),
    "design patterns": ("padroes de projeto",),
    "clean architecture": ("arquitetura limpa",),
    "microservices": ("microsservicos", "microservicos"),
}


def _present(term: str, haystack: str) -> bool:
    """Term (or an equivalent spelling of it) appears in the text."""
    if term in haystack:
        return True
    return any(alt in haystack for alt in _SYNONYMS.get(term, ()))


def score(resume_text: str, description: str, title: str = "") -> dict:
    """Keyword coverage of the posting by the resume. Returns score 0-100 plus detail."""
    reqs = extract_requirements(description)
    if not reqs:
        # No named technologies to match against — either the description failed to
        # scrape or the posting is written without a stack. That is unknown fit, not
        # bad fit, so flag it instead of reporting a confident 0.
        return {
            "score": 0,
            "raw_score": 0,
            "matched": [],
            "missing": [],
            "off_stack": [],
            "requirements": 0,
            "indeterminate": True,
            "indeterminate_reason": (
                "job description is empty" if not (description or "").strip()
                else "posting names no identifiable technologies"
            ),
        }

    resume_norm = _norm(resume_text)
    title_norm = _norm(title)

    matched, missing = [], []
    weight_total = weight_hit = 0.0
    for req in reqs:
        # Terms echoed in the job title matter more than ones buried in a list
        weight = 2.0 if req in title_norm else 1.0
        weight_total += weight
        if _present(req, resume_norm):
            matched.append(req)
            weight_hit += weight
        else:
            missing.append(req)

    off_stack = sorted({t for t in _OFF_STACK if t in _norm(description) or t in title_norm})
    raw = (weight_hit / weight_total) * 100 if weight_total else 0.0

    # An off-discipline posting can still share generic words; penalise it directly.
    penalty = min(40, 15 * len(off_stack))
    final = max(0, round(raw - penalty))

    return {
        "score": final,
        "raw_score": round(raw),
        "matched": matched,
        "missing": missing,
        "off_stack": off_stack,
        "requirements": len(reqs),
        "indeterminate": False,
    }


def truthfulness_violations(resume_text: str, corpus: str | None = None) -> list[str]:
    """Skills the resume claims that the profile doesn't support.

    This is the guard against a tailored resume quietly absorbing the posting's
    requirements — the exact failure that would put 'MaterialUI' on the CV because
    the job asked for it.
    """
    truth = corpus if corpus is not None else truthful_corpus()
    text = _norm(resume_text)

    candidates = _TECH_TOKENS | {
        "material ui", "materialui", "storybook", "vite", "dynamodb", "mongodb",
        "kotlin", "abap", "powerbuilder", "mulesoft", "salesforce", "spark",
    }

    violations: list[str] = []
    for token in sorted(candidates):
        pattern = rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])"
        if re.search(pattern, text) and not re.search(pattern, truth):
            violations.append(token)

    return violations


def resume_text_of(content: dict) -> str:
    """Flatten a resume content dict to plain text for scoring (no PDF parsing).

    Must mirror what actually appears on the page. Two omissions here were
    under-scoring every job: skill *category* labels ("Backend", "Frontend") were
    dropped although they are printed, and the Projects section was skipped
    entirely — which is why RabbitMQ read as missing while sitting in the PDF.
    """
    parts = [content.get("title", ""), content.get("summary", "")]
    for category, values in content.get("skills", []):
        parts.append(category)
        parts.append(values)
    for role in content.get("experience", []):
        parts.append(role.get("title", ""))
        parts.extend(role.get("bullets", []))
    for proj in content.get("projects", []):
        parts.append(proj.get("name", ""))
        parts.append(proj.get("tech", ""))
        parts.extend(proj.get("bullets", []))
    for edu in content.get("education", []):
        parts.append(edu.get("degree", ""))
        parts.append(edu.get("institution", ""))
    return "\n".join(p for p in parts if p)


def over_pruned_requirements(base_content: dict, tailored: dict, description: str) -> list[str]:
    """Requirements the posting asks for that pruning removed from the resume.

    Tailoring is allowed — encouraged — to drop what a role doesn't need. But the
    ATS score is coverage of the posting's requirements, so dropping something the
    posting actually asked for silently lowers the score while looking tidier.
    Anything listed here was in the base resume, is wanted by the posting, and is
    now missing: always a mistake, never a judgement call.
    """
    reqs = extract_requirements(description)
    if not reqs:
        return []

    base_text = _norm("\n".join(
        resume_text_of(lang) for lang in base_content.values()
    ) if isinstance(next(iter(base_content.values()), None), dict) else resume_text_of(base_content))
    new_text = _norm(resume_text_of(tailored))

    lost = []
    for req in reqs:
        pattern = rf"(?<![a-z0-9]){re.escape(req)}(?![a-z0-9])"
        if re.search(pattern, base_text) and not re.search(pattern, new_text):
            lost.append(req)
    return lost

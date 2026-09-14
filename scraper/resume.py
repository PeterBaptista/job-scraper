"""
Resume generator
Usage:
  uv run python resume.py                          # clean stack, English
  uv run python resume.py --pt                     # clean stack, Portuguese
  uv run python resume.py --stack php-laravel --pt # a stack variant
  uv run python resume.py --pt out.pdf             # custom output path
  uv run python resume.py --list                   # available stacks

Content lives in resumes/<stack>/content.py (PDFs are written next to it):
- resumes/clean/       the base template (Next.js · TypeScript · Python)
- resumes/<variant>/   EXTENDS = "clean" and overrides only what changes

New stack: copy resumes/php-laravel/, rename the folder, edit the overrides.
Pass --pt for Brazilian jobs, omit for international.

Two audiences, in this order of constraint:

ATS parsers (non-negotiable)
- Single-column reading order: name -> title -> contact -> summary -> experience -> skills -> education
- Standard section headings in the job's language
- No icons, no images, no text inside graphics
- Keywords inline in experience bullets, not isolated in a keyword dump
- The one table used (role/period on a shared line) is invisible and was verified
  against pdftotext to preserve reading order. If it ever regresses, pass
  use_table=False and dates fall back inline.

The human reading it
- Fits one page; build_with_content() tightens typography in tiers and only drops
  content as a last resort, reporting whatever it dropped
- Clickable email/LinkedIn/GitHub/portfolio links
- Phone number actually present (it was missing for a long time)
- Optional highlight=[...] bolds the technologies the target posting asks for.
  Extracted text is identical with and without it, so ATS output is unaffected.

Everything interpolated is escaped: ReportLab parses paragraphs as XML, so a bare
'&' in "R&D" or "CI/CD & DevOps" used to raise a parse error mid-application.
"""

import copy
import importlib.util
import io
import json
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# PROFILE — language-independent
# ---------------------------------------------------------------------------
# Contact details are personal, so they live in profile.local.json (git-ignored).
# profile.example.json documents the shape; without a local file the resume
# renders with its placeholders.
_PROFILE_DIR = Path(__file__).resolve().parent
_PROFILE_FILE = _PROFILE_DIR / "profile.local.json"
if not _PROFILE_FILE.exists():
    _PROFILE_FILE = _PROFILE_DIR / "profile.example.json"
PROFILE = json.loads(_PROFILE_FILE.read_text())

# ---------------------------------------------------------------------------
# CONTENT — one folder per stack under resumes/<stack>/content.py
# ---------------------------------------------------------------------------
STACKS_DIR = Path(__file__).resolve().parent / "resumes"
# `clean` is personal and git-ignored; a fresh clone falls back to the placeholder template.
BASE_STACK = "clean" if (STACKS_DIR / "clean").exists() else "example"


def list_stacks() -> list[str]:
    return sorted(p.parent.name for p in STACKS_DIR.glob("*/content.py"))


def load_stack(name: str = BASE_STACK, _seen: tuple[str, ...] = ()) -> dict:
    """Load resumes/<name>/content.py as a bilingual CONTENT dict.

    A variant sets EXTENDS = "<parent>" and defines only the keys it changes;
    they replace the parent's keys per language (shallow), so experience and
    education facts are written once in the base and inherited.
    """
    path = STACKS_DIR / name / "content.py"
    if not path.exists():
        raise ValueError(f"unknown stack {name!r}; available: {', '.join(list_stacks())}")
    if name in _seen:
        raise ValueError(f"EXTENDS cycle: {' -> '.join((*_seen, name))}")

    spec = importlib.util.spec_from_file_location(f"resume_stack_{name.replace('-', '_')}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    content = copy.deepcopy(module.CONTENT)

    parent = getattr(module, "EXTENDS", None)
    if parent:
        base = load_stack(parent, (*_seen, name))
        content = {lang: {**base[lang], **content.get(lang, {})} for lang in base}
    return content


# The clean template. The auto-apply pipeline tailors and derives its skill
# allowlist from this, so it stays the untailored baseline.
CONTENT = load_stack(BASE_STACK)

# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

MARGIN = 2.0 * cm
DARK = "#1a1a1a"
ACCENT = "#2563eb"
LIGHT = "#4b5563"
RULE = "#d4d8de"
USABLE_WIDTH = A4[0] - 2 * (2.0 * cm)


def _esc(text: str) -> str:
    """Escape before any markup is added.

    ReportLab parses paragraph text as XML, so a bare '&' (R&D, CI/CD & DevOps)
    raises a parse error and kills PDF generation mid-application.
    """
    return _xml_escape(str(text or ""))


def _link(display: str, href: str) -> str:
    return f'<link href="{_xml_escape(href)}" color="{ACCENT}">{_esc(display)}</link>'


# Metrics are the achievement signal — a recruiter skimming should land on "65%"
# and "500,000" before reading the sentence around them.
_METRIC_RE = re.compile(
    r"""(?<![\w.;])(
        # Thousands, either separator: 500,000 (en) and 6.900 (pt). Portuguese uses a
        # dot, which previously split "6.900" into a bolded "6" and a plain ".900".
        (?:&gt;|&lt;|[>~<])?\d{1,3}(?:[.,]\d{3})+   |
        (?:&gt;|&lt;|[>~<])?\d+(?:[.,]\d+)?\s?%    |   # 65%, &gt;80%, 99,9 %
        \d+(?:[.,]\d+)?x                  |   # 3x, 2.5x
        \d+\+                             |   # 200+
        ~\d+                               |   # ~20
        \d+(?:[.,]\d+)?                       # bare count, decimals kept whole
    )(?![\w])""",
    re.VERBOSE,
)

# Years and framework versions are not achievements: "Next.js 15", "ES2022+", "2024".
_NOT_A_METRIC = re.compile(r"^(?:19|20)\d{2}\+?$")


def _bold_metrics(text_escaped: str) -> str:
    def repl(m: re.Match) -> str:
        token = m.group(0)
        if _NOT_A_METRIC.match(token):
            return token
        # skip framework versions: "Next.js 15", "React 19"
        before = text_escaped[max(0, m.start() - 12):m.start()].lower()
        if before.rstrip().endswith((".js", "js", "react", "node", "python", "v")):
            return token
        return f"<b>{token}</b>"

    return _METRIC_RE.sub(repl, text_escaped)


def _highlight(text_escaped: str, terms: list[str] | None, max_terms: int = 3) -> str:
    """Bold the technologies this posting actually asks for.

    Applied AFTER escaping so the inserted <b> tags survive. Longest terms first
    so 'next.js' wins over 'next'. Capped so emphasis still means something.
    """
    text_escaped = _bold_metrics(text_escaped)
    if not terms:
        return text_escaped

    used = 0
    for term in sorted({t for t in terms if len(t) > 1}, key=len, reverse=True):
        if used >= max_terms:
            break
        pattern = rf"(?<![\w.]){re.escape(_xml_escape(term))}(?![\w])"
        new, n = re.subn(pattern, lambda m: f"<b>{m.group(0)}</b>", text_escaped, count=1,
                         flags=re.IGNORECASE)
        if n:
            text_escaped = new
            used += 1
    return text_escaped


def _styles(scale: float = 1.0, body: float = 10.0) -> dict:
    base = getSampleStyleSheet()

    def s(name, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    def lead(size: float, mult: float = 1.32) -> float:
        return round(size * mult * scale, 2)

    return {
        "name":      s("name",      fontSize=21, leading=lead(21, 1.15), textColor=DARK,
                        fontName="Helvetica-Bold"),
        "title":     s("title",     fontSize=12.5, leading=lead(12.5, 1.2), textColor=ACCENT,
                        fontName="Helvetica"),
        "contact":   s("contact",   fontSize=8.8, leading=lead(8.8, 1.35), textColor=LIGHT),
        "section":   s("section",   fontSize=10.5, leading=lead(10.5, 1.15), textColor=DARK,
                        fontName="Helvetica-Bold", spaceBefore=0, spaceAfter=0),
        "summary":   s("summary",   fontSize=body, leading=lead(body, 1.38), textColor=DARK),
        "job_title": s("job_title", fontSize=body, leading=lead(body, 1.25), textColor=DARK,
                        fontName="Helvetica-Bold"),
        "job_period": s("job_period", fontSize=body - 1, leading=lead(body, 1.25),
                        textColor=LIGHT, alignment=2),
        "job_meta":  s("job_meta",  fontSize=body - 1, leading=lead(body, 1.2), textColor=LIGHT),
        "bullet":    s("bullet",    fontSize=body, leading=lead(body, 1.34), textColor=DARK,
                        leftIndent=11, firstLineIndent=-11),
        "skill_row": s("skill_row", fontSize=body, leading=lead(body, 1.32), textColor=DARK,
                        leftIndent=0),
        "edu":       s("edu",       fontSize=body, leading=lead(body, 1.3), textColor=DARK),
    }


def _story(c: dict, st: dict, highlight: list[str] | None, gap: float,
           use_table: bool = True) -> list:
    """Single-column flow. Order on the page is the order a parser reads."""
    story: list = []

    def sp(frac: float) -> Spacer:
        return Spacer(1, frac * gap)

    # --- header -------------------------------------------------------------
    story.append(Paragraph(_esc(PROFILE["name"]), st["name"]))
    story.append(Paragraph(_esc(c["title"]), st["title"]))
    story.append(sp(0.45))

    line1 = "  ·  ".join([
        _link(PROFILE["email"], f"mailto:{PROFILE['email']}"),
        _esc(PROFILE["phone"]),
        _esc(c["location"]),
    ])
    line2 = "  ·  ".join([
        _link(PROFILE["linkedin"], f"https://{PROFILE['linkedin']}"),
        _link(PROFILE["github"], f"https://{PROFILE['github']}"),
        _link(PROFILE["portfolio"], f"https://{PROFILE['portfolio']}"),
    ])
    story.append(Paragraph(line1, st["contact"]))
    story.append(Paragraph(line2, st["contact"]))

    def section(heading: str) -> list:
        return [
            sp(1.0),
            Paragraph(_esc(heading), st["section"]),
            sp(0.18),
            HRFlowable(width="100%", thickness=0.6, color=RULE, spaceBefore=0, spaceAfter=0),
            sp(0.35),
        ]

    # --- summary ------------------------------------------------------------
    story += section(c["h_summary"])
    story.append(Paragraph(_highlight(_esc(c["summary"]), highlight), st["summary"]))

    # --- experience ---------------------------------------------------------
    story += section(c["h_experience"])
    for i, job in enumerate(c["experience"]):
        block: list = []
        if use_table:
            # Role left, period right. Invisible 2-column table; verified against
            # pdftotext so the reading order stays role -> period -> company.
            block.append(Table(
                [[Paragraph(_esc(job["title"]), st["job_title"]),
                  Paragraph(_esc(job["period"]), st["job_period"])]],
                colWidths=[USABLE_WIDTH * 0.68, USABLE_WIDTH * 0.32],
                style=TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]),
                hAlign="LEFT",
            ))
            block.append(Paragraph(_esc(job["company"]), st["job_meta"]))
        else:
            block.append(Paragraph(_esc(job["title"]), st["job_title"]))
            block.append(Paragraph(f'{_esc(job["company"])}  ·  {_esc(job["period"])}',
                                   st["job_meta"]))

        block.append(Spacer(1, 0.18 * gap))
        for bullet in job["bullets"]:
            block.append(Paragraph("•  " + _highlight(_esc(bullet), highlight), st["bullet"]))

        # Never let a role split across a page break.
        story.append(KeepTogether(block))
        if i < len(c["experience"]) - 1:
            story.append(sp(0.55))

    # --- projects (optional) -------------------------------------------------
    if c.get("projects"):
        story += section(c.get("h_projects", "PROJECTS"))
        for i, proj in enumerate(c["projects"]):
            block = [
                Paragraph(_esc(proj["name"]), st["job_title"]),
                Paragraph(_esc(proj["tech"]), st["job_meta"]),
                Spacer(1, 0.18 * gap),
            ]
            block += [
                Paragraph("•  " + _highlight(_esc(b), highlight), st["bullet"])
                for b in proj["bullets"]
            ]
            story.append(KeepTogether(block))
            if i < len(c["projects"]) - 1:
                story.append(sp(0.55))

    # --- skills -------------------------------------------------------------
    story += section(c["h_skills"])
    for category, items in c["skills"]:
        story.append(Paragraph(
            f'<b>{_esc(category)}:</b>  {_highlight(_esc(items), highlight, max_terms=4)}',
            st["skill_row"],
        ))

    # --- education ----------------------------------------------------------
    story += section(c["h_education"])
    for edu in c["education"]:
        story.append(Paragraph(
            f'<b>{_esc(edu["degree"])}</b>  ·  {_esc(edu["institution"])}  ·  {_esc(edu["period"])}',
            st["edu"],
        ))

    return story


def _render(path_or_buf, c: dict, st: dict, highlight, gap: float,
            use_table: bool, keywords: str) -> None:
    doc = SimpleDocTemplate(
        path_or_buf,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN * 0.85, bottomMargin=MARGIN * 0.85,
        title=f"{PROFILE['name']} — {c['title']}",
        author=PROFILE["name"],
        subject=c["title"],
        keywords=keywords,
        creator="resume.py",
    )
    doc.build(_story(c, st, highlight, gap, use_table))


def build_with_content(output: Path, c: dict, highlight: list[str] | None = None,
                       use_table: bool = True) -> dict:
    """Render the resume, fitting it onto a single page.

    Returns {"pages", "tier", "dropped_bullets"}. Tier 4 removes content, so it is
    reported rather than done silently — the caller re-scores what was actually sent.
    """
    from pypdf import PdfReader

    c = copy.deepcopy(c)
    keywords = ", ".join(v for _, v in c.get("skills", []))
    dropped: list[str] = []

    # 1: default  2: tighter rhythm  3: smaller body  4: drop oldest bullets
    attempts = [
        (1.00, 10.0, 0.30 * cm),
        (0.93, 10.0, 0.24 * cm),
        (0.90, 9.5, 0.21 * cm),
    ]

    for tier, (scale, body, gap) in enumerate(attempts, start=1):
        buf = io.BytesIO()
        _render(buf, c, _styles(scale, body), highlight, gap, use_table, keywords)
        if len(PdfReader(io.BytesIO(buf.getvalue())).pages) == 1:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(buf.getvalue())
            return {"pages": 1, "tier": tier, "dropped_bullets": dropped}

    # Tier 4 — trim the oldest role's least important bullets, up to two.
    scale, body, gap = attempts[-1]
    for _ in range(2):
        oldest = c["experience"][-1]
        if len(oldest["bullets"]) <= 2:
            break
        dropped.append(oldest["bullets"].pop())
        buf = io.BytesIO()
        _render(buf, c, _styles(scale, body), highlight, gap, use_table, keywords)
        if len(PdfReader(io.BytesIO(buf.getvalue())).pages) == 1:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(buf.getvalue())
            return {"pages": 1, "tier": 4, "dropped_bullets": dropped}

    # Give up on one page rather than mutilate the content further.
    output.parent.mkdir(parents=True, exist_ok=True)
    _render(str(output), c, _styles(scale, body), highlight, gap, use_table, keywords)
    pages = len(PdfReader(str(output)).pages)
    return {"pages": pages, "tier": 5, "dropped_bullets": dropped}


# Anchored end-to-end on purpose: matching a mere prefix flagged a real
# "Universidade Federal de ... (...)" as an unfilled template.
_PLACEHOLDER_RE = re.compile(
    r"^(tech company|empresa de tecnologia|university|universidade|company|empresa)"
    r"(\s*[—\-–,]\s*(brazil|brasil))?$",
    re.IGNORECASE,
)


def _looks_like_placeholder(value: str) -> bool:
    return bool(_PLACEHOLDER_RE.match(value.strip()))


def _is_translated_placeholder(en_value: str, pt_value: str) -> bool:
    """Allow en/pt to differ only while both are still unfilled templates."""
    return _looks_like_placeholder(en_value) and _looks_like_placeholder(pt_value)


def consistency_issues() -> list[str]:
    """Factual drift between the language blocks and ME.md.

    The two CONTENT blocks describe the same person, so dates and employers must
    match. They have silently diverged twice: a stale LinkedIn slug, and an English
    education line reading "2021 – Present (expected 2025)" while Portuguese said
    2022/2027. Both went out on real applications.
    """
    issues: list[str] = []
    for stack in list_stacks():
        issues += [f"[{stack}] {msg}" for msg in _content_issues(load_stack(stack))]
    return issues


def _content_issues(content: dict) -> list[str]:
    issues: list[str] = []
    en, pt = content["en"], content["pt"]

    def years(text: str) -> list[str]:
        return re.findall(r"(?:19|20)\d{2}", text)

    if len(en["experience"]) != len(pt["experience"]):
        issues.append("experience entry count differs between en and pt")
    else:
        for a, b in zip(en["experience"], pt["experience"]):
            if years(a["period"]) != years(b["period"]):
                issues.append(f"role period differs: en {a['period']!r} vs pt {b['period']!r}")
            # Employer names are facts, not translations — they must match verbatim.
            if a["company"] != b["company"] and not _is_translated_placeholder(a["company"], b["company"]):
                issues.append(f"employer differs: en {a['company']!r} vs pt {b['company']!r}")

    for label, en_v, pt_v in (
        ("institution", en["education"][0]["institution"], pt["education"][0]["institution"]),
    ):
        if _looks_like_placeholder(en_v) or _looks_like_placeholder(pt_v):
            issues.append(f"{label} still a placeholder: {en_v!r} / {pt_v!r}")

    if len(en["education"]) != len(pt["education"]):
        issues.append("education entry count differs between en and pt")
    else:
        for a, b in zip(en["education"], pt["education"]):
            if years(a["period"]) != years(b["period"]):
                issues.append(f"education period differs: en {a['period']!r} vs pt {b['period']!r}")

    me = Path("ME.md")
    if me.exists():
        me_text = me.read_text()
        for key in ("linkedin", "github", "portfolio", "email"):
            if PROFILE[key] not in me_text:
                issues.append(f"PROFILE[{key}] = {PROFILE[key]!r} is not in ME.md")
        for edu in en["education"]:
            for year in years(edu["period"]):
                if year not in me_text:
                    issues.append(f"education year {year} not found in ME.md")

    return issues


def build(output: Path, lang: str = "en", stack: str = BASE_STACK) -> dict:
    """Render the untailored resume for one stack and language.

    Delegates to the single rendering path so the CLI and the auto-apply pipeline
    can never drift apart visually.
    """
    result = build_with_content(output, load_stack(stack)[lang])
    print(f"PDF written to: {output}  (stack={stack}, lang={lang}, "
          f"pages={result['pages']}, tier={result['tier']})")
    return result


def main() -> None:
    args = sys.argv[1:]
    if "--list" in args:
        print("\n".join(list_stacks()))
        return

    lang = "en"
    if "--pt" in args:
        lang = "pt"
        args.remove("--pt")

    stack = BASE_STACK
    if "--stack" in args:
        i = args.index("--stack")
        if i + 1 >= len(args):
            sys.exit(f"--stack needs a name; available: {', '.join(list_stacks())}")
        stack = args[i + 1]
        del args[i:i + 2]

    out_name = "curriculo.pdf" if lang == "pt" else "resume.pdf"
    out = Path(args[0]) if args else STACKS_DIR / stack / out_name
    build(out, lang, stack)


if __name__ == "__main__":
    main()

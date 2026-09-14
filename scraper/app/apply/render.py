"""Render a tailored resume and score exactly what was rendered.

One-page fitting can *remove* content: at tier 4 `build_with_content` drops the
oldest role's last bullets to make the page fit. Scoring the pre-render dict
would then report coverage for text that is not in the document. Everything that
renders a CV goes through here so the number and the PDF cannot disagree.
"""

import logging
import tempfile
from pathlib import Path

from app.apply import ats

logger = logging.getLogger(__name__)


def effective_content(content: dict, dropped_bullets: list[str]) -> dict:
    """The content as it actually reached the page, with dropped bullets removed."""
    if not dropped_bullets:
        return content
    for dropped in dropped_bullets:
        for role in content.get("experience", []):
            if dropped in role["bullets"]:
                role["bullets"].remove(dropped)
    return content


def render(content: dict, description: str, out: Path) -> dict:
    """Write the PDF at `out`. Reuses resume.build_with_content — the only renderer.

    `_meta` and any other underscore key is stripped: build_with_content walks the
    dict by known keys and an unexpected one is not its problem to survive.
    """
    from resume import build_with_content

    payload = {k: v for k, v in content.items() if not k.startswith("_")}
    highlight = ats.extract_requirements(description or "")
    return build_with_content(out, payload, highlight=highlight)


def render_and_score(job: dict, content: dict, out: Path) -> dict:
    """Render to `out`, replay any fitting drops, then score the result.

    Returns {"content", "fit", "ats", "violations", "over_pruned"} where `content`
    is what the PDF actually says.
    """
    import copy

    from resume import CONTENT

    description = job.get("description") or ""
    working = copy.deepcopy(content)
    fit = render(working, description, out)

    if fit["dropped_bullets"]:
        logger.warning(
            "One-page fit dropped %d bullet(s) for %s: %s",
            len(fit["dropped_bullets"]), job.get("company"), fit["dropped_bullets"],
        )
    if fit["pages"] > 1:
        logger.warning("Resume for %s is %d pages (could not fit)",
                       job.get("company"), fit["pages"])

    working = effective_content(working, fit["dropped_bullets"])
    text = ats.resume_text_of(working)

    return {
        "content": working,
        "fit": fit,
        "ats": ats.score(text, description, job.get("title") or ""),
        "violations": ats.truthfulness_violations(text),
        "over_pruned": ats.over_pruned_requirements(CONTENT, working, description),
    }


def preview(job: dict, content: dict) -> tuple[bytes, dict]:
    """Same as render_and_score but into a temp file, returning the PDF bytes.

    The editor re-renders on every pause in typing; writing those into
    `generated_resumes/` would churn the very file the apply worker may be
    reading. Only an explicit commit writes there.
    """
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "preview.pdf"
        result = render_and_score(job, content, out)
        return out.read_bytes(), result

"""Standard answers for application form fields that aren't in the resume profile.

Loaded from `answers.yml` (git-ignored). Anything missing stays missing: a form
field with no truthful answer aborts the application rather than being guessed.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

from app.config import settings

logger = logging.getLogger(__name__)

_cache: dict[str, Any] | None = None


def load_answers(force: bool = False) -> dict[str, Any]:
    global _cache
    if _cache is not None and not force:
        return _cache

    path = Path(settings.answers_file)
    if not path.exists():
        logger.warning(
            "%s not found — forms needing salary/experience answers will abort. "
            "Copy answers.example.yml to %s to enable them.",
            path, path,
        )
        _cache = {}
        return _cache

    raw = yaml.safe_load(path.read_text()) or {}
    # Drop nulls so "unanswered" and "answered as empty" stay distinguishable.
    _cache = {k: v for k, v in raw.items() if v is not None and v != ""}
    logger.info("Loaded %d answers from %s", len(_cache), path)
    return _cache


def get(key: str, default: Any = None) -> Any:
    return load_answers().get(key, default)


def as_prompt_block() -> str:
    """Answers rendered for the form-mapping prompt. Only known values appear,
    so the model cannot 'fill in' something we never supplied."""
    answers = load_answers()
    if not answers:
        return "(no standard answers configured)"
    return "\n".join(f"{k}: {v}" for k, v in sorted(answers.items()))

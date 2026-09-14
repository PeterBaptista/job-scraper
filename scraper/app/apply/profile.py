"""Single definition of the candidate's profile for LLM prompts.

Previously duplicated in apply.py; kept here so the tailoring prompt and the
apply CLI cannot drift apart.
"""

from pathlib import Path


def profile_block() -> str:
    """ME.md verbatim — the declared source of truth for what is claimable."""
    me = Path("ME.md")
    if me.exists():
        return me.read_text().strip()

    from resume import PROFILE
    return f"Name: {PROFILE['name']}\nEmail: {PROFILE['email']}"

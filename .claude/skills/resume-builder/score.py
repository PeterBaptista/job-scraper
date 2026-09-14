"""Score a resume stack against a job posting with the repo's deterministic ATS.

Run from scraper/:
  uv run python ../.claude/skills/resume-builder/score.py <stack> <job.md> [--pt] [--title "..."]

Prints the ATS score, matched/missing requirements, truthfulness violations
(technologies claimed that ME.md + the clean base do not support) and the same
numbers for `clean`, so a variant can be checked to actually beat the baseline.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from app.apply.ats import resume_text_of, score, truthfulness_violations  # noqa: E402
from resume import BASE_STACK, load_stack  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stack")
    parser.add_argument("job", type=Path)
    parser.add_argument("--pt", action="store_true")
    parser.add_argument("--title", default="")
    args = parser.parse_args()

    lang = "pt" if args.pt else "en"
    description = args.job.read_text()
    title = args.title or description.splitlines()[0].lstrip("# ")

    for stack in dict.fromkeys([args.stack, BASE_STACK]):
        text = resume_text_of(load_stack(stack)[lang])
        result = score(text, description, title)
        violations = truthfulness_violations(text)
        print(f"== {stack} ({lang}) — score {result['score']} (raw {result['raw_score']}, "
              f"{result['requirements']} requirements)")
        print(f"   matched:    {', '.join(result['matched']) or '-'}")
        print(f"   missing:    {', '.join(result['missing']) or '-'}")
        print(f"   off-stack:  {', '.join(result['off_stack']) or '-'}")
        print(f"   UNTRUTHFUL: {', '.join(violations) or 'none'}")


if __name__ == "__main__":
    main()

# Job Application Bot — Setup & Usage

No API key needed. Analysis is done by pasting into Claude Code (this chat).

## Workflow

```
Step 1: uv run python apply.py --fetch
        → prints a prompt with your new jobs

Step 2: paste the prompt here into Claude Code chat
        → Claude analyses fit and returns a JSON array

Step 3: save the JSON to a file (e.g. analysis.json)

Step 4: uv run python apply.py --apply analysis.json
        → generates tailored PDFs + opens Chrome for Easy Apply
```

---

## Prerequisites — LinkedIn cookies

The bot needs your LinkedIn session to click Easy Apply automatically.

**One-time setup:**

1. Install the [EditThisCookie](https://chromewebstore.google.com/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg) Chrome extension (or any cookie exporter).
2. Log in to LinkedIn in Chrome normally.
3. Go to `https://www.linkedin.com`.
4. Open EditThisCookie → Export → copies a JSON array to clipboard.
5. Paste it into `scraper/cookies/linkedin.json`.

The file should look like:
```json
[
  { "name": "li_at", "value": "...", "domain": ".linkedin.com", ... },
  ...
]
```

Cookies expire after a few weeks — if Chrome keeps redirecting to login, re-export and replace the file.

---

## Commands

All commands from `scraper/`:

```bash
# Step 1 — print prompt for Claude Code
uv run python apply.py --fetch
uv run python apply.py --fetch --limit 5   # limit to 5 jobs

# Step 4 — generate PDFs + apply
uv run python apply.py --apply analysis.json
uv run python apply.py --apply analysis.json --dry-run   # PDFs only, no browser
```

---

## Step 2 in detail — talking to Claude Code

After running `--fetch`, copy everything between the `===` lines and paste it here in chat.

Claude will return a JSON array like:

```json
[
  {
    "id": "abc-123",
    "score": 9,
    "should_apply": true,
    "language": "pt",
    "reason": "Strong React/Next.js match, remote-friendly.",
    "tailored_title": "Desenvolvedor Full Stack",
    "tailored_summary": "...",
    "current_role_bullets": ["...", "...", "...", "..."],
    "internship_bullets": ["...", "...", "...", "..."]
  }
]
```

Save that to `analysis.json` (or any filename) and run Step 4.

---

## What happens during Easy Apply

1. Chrome opens the LinkedIn job page (UC mode — behaves like a real browser).
2. The bot clicks **Easy Apply** / **Candidatura simplificada**.
3. It uploads the tailored PDF resume when it finds a file input.
4. It clicks **Next / Próximo** through each step.
5. On the final step it clicks **Submit / Enviar**.
6. If anything fails it falls back to opening the URL in your default browser.

**Watch the first few runs.** LinkedIn Easy Apply forms vary — some ask extra questions (salary expectation, availability, cover letter) that can't be filled automatically. Leave the Chrome window visible so you can intervene.

---

## Tailored PDFs

Each run saves one PDF per job to a temp directory. To keep a copy, use `--dry-run` and note the path printed in the terminal — copy the file before the run finishes.

To generate a standalone tailored resume without going through the full flow, edit `resume.py` directly and run:

```bash
uv run python resume.py        # English
uv run python resume.py --pt   # Portuguese
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `No user found with email …` | Confirm the email in `resume.py → PROFILE["email"]` matches the DB |
| Chrome redirected to LinkedIn login | Re-export cookies → replace `cookies/linkedin.json` |
| Bot stalls on Easy Apply modal | Complete the form manually in the open Chrome window |
| Score always low | The job description may be too short — check that scraping captured the full description |

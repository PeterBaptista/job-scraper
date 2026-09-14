"""
LinkedIn Easy Apply (Candidatura Simplificada) — standalone script

Opens a LinkedIn job URL, clicks Candidatura Simplificada, uploads the
customised resume PDF, and steps through the modal until it submits.

Usage:
  uv run python easy_apply.py <job_url> <pdf_path>

Examples:
  uv run python easy_apply.py https://www.linkedin.com/jobs/view/1234567/ analysis.json
  uv run python easy_apply.py https://www.linkedin.com/jobs/view/1234567/ resume.pdf

Cookies must exist at cookies/linkedin.json (see APPLY.md for how to export them).
"""

import json
import sys
import time
from pathlib import Path

from seleniumbase import SB

from app.config import settings

COOKIES_PATH = Path("cookies/linkedin.json")

# Selectors for the Easy Apply button on the job detail panel
EASY_APPLY_BUTTON_SELECTORS = [
    ".jobs-apply-button--top-card button",
    "button.jobs-apply-button",
]

# Modal step button selectors — tried in priority order each step
STEP_BUTTONS = [
    # Submit / Enviar  (final step)
    ('button[aria-label*="Enviar candidatura"]',    "submit"),
    ('button[aria-label*="Submit application"]',    "submit"),
    # Review / Revisar  (second-to-last step)
    ('button[aria-label*="Revisar"]',               "review"),
    ('button[aria-label*="Review your application"]', "review"),
    # Next / Próximo   (intermediate steps)
    ('button[aria-label*="Continuar"]',             "next"),
    ('button[aria-label*="Próximo"]',               "next"),
    ('button[aria-label*="Next"]',                  "next"),
]

# Selectors for "Alterar currículo" / upload CV file inputs
UPLOAD_SELECTORS = [
    "input[type='file']",
]

# JS: detect which step the modal is currently on (returns button label text)
_MODAL_BUTTONS_JS = """
(() => {
    const modal = document.querySelector('.jobs-easy-apply-modal, [data-test-modal]');
    if (!modal) return [];
    return Array.from(modal.querySelectorAll('button[aria-label]'))
        .map(b => b.getAttribute('aria-label'));
})()
"""

# JS: dismiss the "Deseja sair?" / "Leave?" discard dialog if it appears
_DISMISS_DISCARD_JS = """
(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const discard = btns.find(b =>
        b.innerText.includes('Descartar') || b.innerText.includes('Discard')
    );
    if (discard) { discard.click(); return true; }
    return false;
})()
"""


def _load_cookies(sb: SB) -> None:
    if not COOKIES_PATH.exists():
        print(f"[warn] No cookies at {COOKIES_PATH}. You may be prompted to log in.")
        return

    sb.open("https://www.linkedin.com")
    cookies: list[dict] = json.loads(COOKIES_PATH.read_text())
    injected = 0
    for c in cookies:
        try:
            sb.driver.add_cookie(
                {k: v for k, v in c.items()
                 if k in {"name", "value", "domain", "path", "secure", "httpOnly", "expiry"}}
            )
            injected += 1
        except Exception:
            pass
    print(f"[cookies] Injected {injected} cookies")
    sb.driver.refresh()
    sb.sleep(2)


def _click_easy_apply(sb: SB) -> bool:
    """Click the Candidatura Simplificada button. Returns True if found."""
    for sel in EASY_APPLY_BUTTON_SELECTORS:
        try:
            btn = sb.find_element(sel, timeout=6)
            if btn and btn.is_displayed():
                label = (btn.get_attribute("aria-label") or btn.text or "").lower()
                if any(kw in label for kw in ["simplificada", "easy apply", "candidat"]):
                    btn.click()
                    print(f"[apply] Clicked Easy Apply button")
                    sb.sleep(2)
                    return True
        except Exception:
            continue

    # Fallback: check all buttons on page for the right text
    try:
        result = sb.execute_script("""
            (() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => {
                    const t = (b.innerText + (b.getAttribute('aria-label') || '')).toLowerCase();
                    return t.includes('simplificada') || t.includes('easy apply');
                });
                if (btn) { btn.click(); return true; }
                return false;
            })()
        """)
        if result:
            print("[apply] Clicked Easy Apply button (JS fallback)")
            sb.sleep(2)
            return True
    except Exception:
        pass

    return False


def _try_upload(sb: SB, pdf_path: Path) -> bool:
    """Upload the PDF if a file input is visible in the modal."""
    for sel in UPLOAD_SELECTORS:
        try:
            inputs = sb.find_elements(sel)
            for inp in inputs:
                if inp.is_displayed() or True:  # file inputs are often hidden
                    try:
                        inp.send_keys(str(pdf_path.absolute()))
                        sb.sleep(1.5)
                        print(f"[upload] Uploaded {pdf_path.name}")
                        return True
                    except Exception:
                        continue
        except Exception:
            continue
    return False


def _modal_is_open(sb: SB) -> bool:
    try:
        result = sb.execute_script("""
            return !!(
                document.querySelector('.jobs-easy-apply-modal') ||
                document.querySelector('[data-test-modal]') ||
                document.querySelector('.artdeco-modal--layer-confirmation')
            );
        """)
        return bool(result)
    except Exception:
        return False


def _step(sb: SB, pdf_path: Path) -> str:
    """
    Attempt one modal step. Tries to upload CV, then clicks the highest-priority
    available button. Returns the button type clicked: 'submit', 'review', 'next',
    or 'none' if nothing matched.
    """
    _try_upload(sb, pdf_path)
    sb.sleep(0.5)

    modal_labels: list[str] = sb.execute_script(_MODAL_BUTTONS_JS) or []
    labels_lower = [l.lower() for l in modal_labels]

    for sel, kind in STEP_BUTTONS:
        try:
            btn = sb.find_element(sel, timeout=2)
            if btn and btn.is_displayed() and btn.is_enabled():
                btn.click()
                print(f"[modal] Clicked '{kind}' button")
                sb.sleep(2)
                return kind
        except Exception:
            continue

    # Fallback: scan visible modal buttons by text
    try:
        clicked = sb.execute_script("""
            (() => {
                const modal = document.querySelector(
                    '.jobs-easy-apply-modal, [data-test-modal]'
                );
                if (!modal) return null;
                const priority = [
                    ['enviar', 'submit application'],
                    ['revisar', 'review'],
                    ['continuar', 'próximo', 'next'],
                ];
                for (const [idx, terms] of priority.entries()) {
                    const btn = Array.from(modal.querySelectorAll('button')).find(b => {
                        const t = (b.innerText + (b.getAttribute('aria-label') || '')).toLowerCase();
                        return terms.some(term => t.includes(term)) && !b.disabled;
                    });
                    if (btn) { btn.click(); return idx; }
                }
                return null;
            })()
        """)
        if clicked is not None:
            kinds = ["submit", "review", "next"]
            kind = kinds[clicked]
            print(f"[modal] Clicked '{kind}' (JS fallback)")
            sb.sleep(2)
            return kind
    except Exception:
        pass

    return "none"


def easy_apply(job_url: str, pdf_path: Path) -> bool:
    """
    Full Easy Apply flow. Returns True if successfully submitted.
    Keeps Chrome open for manual intervention if the script stalls.
    """
    pdf_path = pdf_path.resolve()
    if not pdf_path.exists():
        print(f"[error] PDF not found: {pdf_path}")
        return False

    print(f"[start] Job URL : {job_url}")
    print(f"[start] Resume  : {pdf_path}")

    # xvfb keeps real headed Chrome working inside the container (no display).
    with SB(headless=False, headed=True, uc=True, xvfb=settings.browser_xvfb) as sb:
        _load_cookies(sb)

        print(f"[nav] Opening job page …")
        sb.open(job_url)
        sb.sleep(3)

        # wait for the job detail panel to load
        try:
            sb.wait_for_element(".jobs-unified-top-card, .job-details-jobs-unified-top-card__title", timeout=15)
        except Exception:
            print("[warn] Job detail panel slow to load, continuing anyway")

        if not _click_easy_apply(sb):
            print("[error] Easy Apply button not found — is this an Easy Apply job?")
            print("        Keeping Chrome open for 60 s so you can apply manually.")
            sb.sleep(60)
            return False

        # Step through the modal
        submitted = False
        for step_num in range(1, 16):
            if not _modal_is_open(sb):
                print(f"[modal] Modal closed after step {step_num - 1}")
                break

            print(f"[step {step_num}] ", end="", flush=True)
            result = _step(sb, pdf_path)

            if result == "submit":
                submitted = True
                print("[done] Application submitted!")
                sb.sleep(3)
                break

            if result == "none":
                print(f"[warn] No actionable button found on step {step_num}.")
                print("       Keeping Chrome open for 90 s — complete the form manually.")
                sb.sleep(90)
                # Try one more step after the user intervenes
                if _modal_is_open(sb):
                    continue
                break

        if not submitted:
            print("[warn] Did not reach Submit. Check if application was sent.")

        sb.sleep(2)

    return submitted


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    job_url = sys.argv[1]
    pdf_path = Path(sys.argv[2])

    success = easy_apply(job_url, pdf_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

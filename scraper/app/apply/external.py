"""Apply through an employer's own ATS (inhire, Gupy, Greenhouse, Lever, …).

These forms are arbitrary, so the DOM is serialised and an LLM maps fields to
profile values. Anything it cannot answer truthfully — or any wall we must not
cross — aborts with a recorded reason instead of guessing.
"""

import json
import logging
from pathlib import Path

from seleniumbase import SB

from app.apply.answers import as_prompt_block
from app.apply.profile import profile_block
from app.config import settings

logger = logging.getLogger(__name__)


class ApplyAbort(Exception):
    """Raised with a human-readable reason we could not apply."""


# Walls we deliberately never automate. Creating accounts, entering passwords and
# defeating CAPTCHAs are out of bounds regardless of how convenient it would be.
_BLOCKERS_JS = """
(() => {
  const t = (document.body.innerText || '').toLowerCase();
  const has = s => t.includes(s);
  const out = [];
  if (document.querySelector('input[type=password]')) out.push('requires an account password');
  if (document.querySelector('iframe[src*="recaptcha"], iframe[src*="hcaptcha"], .g-recaptcha, .h-captcha'))
      out.push('CAPTCHA present');
  if (has('criar conta') || has('cadastre-se') || has('create an account') || has('sign up'))
      out.push('requires creating an account');
  if ((has('entrar') || has('login') || has('sign in')) && document.querySelectorAll('form').length === 1
      && !document.querySelector('input[type=file]'))
      out.push('login wall');
  return out;
})()
"""

_FORM_JS = """
(() => {
  const vis = el => !!(el.offsetParent || el.getClientRects().length);
  const label = el => {
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l) return l.innerText.trim();
    }
    const wrap = el.closest('div,section,li');
    if (wrap) {
      const l = wrap.querySelector('label');
      if (l) return l.innerText.trim();
    }
    return el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.name || '';
  };
  const out = [];
  document.querySelectorAll('input,select,textarea').forEach((el, i) => {
    const type = (el.type || el.tagName).toLowerCase();
    if (['hidden','submit','button','image'].includes(type)) return;
    if (!vis(el) && type !== 'file') return;
    el.setAttribute('data-af', String(i));
    out.push({
      ref: String(i),
      type,
      label: label(el).slice(0, 120),
      required: el.required || el.getAttribute('aria-required') === 'true',
      options: el.tagName === 'SELECT'
        ? [...el.options].map(o => o.text.trim()).filter(Boolean).slice(0, 40) : [],
    });
  });
  return out;
})()
"""

_SYSTEM = """You map job-application form fields to a candidate's real data.

Rules:
- Only use values present in the candidate profile or standard answers given.
- If a field has no truthful value, return it in "unanswerable" — never invent
  data, never approximate salary, documents, or years of experience.
- For selects, choose EXACTLY one of the provided options.
- Skip file inputs; the resume is uploaded separately.

Return JSON: {"fill": [{"ref": str, "value": str}], "unanswerable": [{"ref": str, "label": str}]}"""


def _map_fields(fields: list[dict]) -> dict:
    from openai import OpenAI

    if not settings.openai_api_key:
        raise ApplyAbort("OPENAI_API_KEY not set — cannot map external form")

    client = OpenAI(api_key=settings.openai_api_key)
    user = (
        f"## Candidate profile\n{profile_block()}\n\n"
        f"## Standard answers\n{as_prompt_block()}\n\n"
        f"## Form fields\n{json.dumps(fields, ensure_ascii=False, indent=1)}"
    )
    resp = client.chat.completions.create(
        model=settings.openai_form_model,
        messages=[{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def apply_external(job_url: str, pdf_path: Path, dry_run: bool = True) -> tuple[bool, str]:
    """Returns (submitted, reason)."""
    pdf_path = pdf_path.resolve()

    with SB(headless=False, headed=True, uc=True, xvfb=settings.browser_xvfb) as sb:
        sb.open(job_url)
        sb.sleep(4)

        blockers = sb.execute_script(_BLOCKERS_JS) or []
        if blockers:
            raise ApplyAbort(f"cannot auto-apply: {'; '.join(blockers)}")

        file_inputs = sb.find_elements("input[type='file']")
        if not file_inputs:
            raise ApplyAbort("no resume upload field found on the page")

        fields = sb.execute_script(_FORM_JS) or []
        if not fields:
            raise ApplyAbort("no form fields detected")

        mapping = _map_fields([f for f in fields if f["type"] != "file"])
        unanswerable = [
            u for u in mapping.get("unanswerable", [])
            if any(f["ref"] == u.get("ref") and f["required"] for f in fields)
        ]
        if unanswerable:
            labels = ", ".join(u.get("label", "?") for u in unanswerable[:4])
            raise ApplyAbort(f"required fields with no truthful answer: {labels}")

        # Upload the resume
        try:
            file_inputs[0].send_keys(str(pdf_path))
            sb.sleep(2)
        except Exception as exc:
            raise ApplyAbort(f"resume upload failed: {exc}") from exc

        filled = 0
        for item in mapping.get("fill", []):
            try:
                sb.execute_script(
                    """
                    (() => {
                      const el = document.querySelector(`[data-af="${arguments[0]}"]`);
                      if (!el) return false;
                      const set = (e, v) => {
                        const proto = e.tagName === 'SELECT'
                          ? window.HTMLSelectElement.prototype
                          : (e.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype
                                                      : window.HTMLInputElement.prototype);
                        const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                        setter.call(e, v);
                        e.dispatchEvent(new Event('input', {bubbles: true}));
                        e.dispatchEvent(new Event('change', {bubbles: true}));
                      };
                      if (el.tagName === 'SELECT') {
                        const opt = [...el.options].find(o => o.text.trim() === arguments[1]);
                        if (opt) { el.value = opt.value; el.dispatchEvent(new Event('change', {bubbles:true})); return true; }
                        return false;
                      }
                      set(el, arguments[1]);
                      return true;
                    })()
                    """,
                    item["ref"], str(item["value"]),
                )
                filled += 1
            except Exception:
                logger.warning("Could not fill field %s", item.get("ref"))

        if dry_run:
            return False, f"DRY RUN — filled {filled} fields and attached the CV, did not submit"

        submitted = sb.execute_script(
            """
            (() => {
              const kw = ['candidatar','enviar','submit','apply','finalizar'];
              const btn = [...document.querySelectorAll('button,input[type=submit]')].find(b => {
                const t = ((b.innerText||'') + (b.value||'')).toLowerCase();
                return kw.some(k => t.includes(k)) && !b.disabled;
              });
              if (btn) { btn.click(); return true; }
              return false;
            })()
            """
        )
        if not submitted:
            raise ApplyAbort("submit button not found")

        sb.sleep(5)
        confirmed = sb.execute_script(
            """
            (() => {
              const t = (document.body.innerText||'').toLowerCase();
              return ['sucesso','recebemos','inscrição feita','application received','thank you',
                      'obrigado'].some(s => t.includes(s));
            })()
            """
        )
        return True, ("submitted and confirmed" if confirmed
                      else "submitted (no confirmation text found — verify manually)")

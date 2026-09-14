"""Score newly scraped jobs, tailor a resume, and request approval in Telegram.

Runs after each scrape. Nothing here submits anything — the only way an
application is sent is a human tapping Approve on the resulting message.
"""

import asyncio
import html
import logging
from functools import partial
from pathlib import Path

from app.apply import ats, render
from app.apply.tailor import build_pdf, tailor
from app.blocklist import is_blocked
from app.config import settings
from app.db.client import (
    get_job,
    get_scheduler_user_id,
    jobs_pending_scoring,
    record_ats,
    upsert_draft,
)
from app.notify.telegram import send_with_buttons

logger = logging.getLogger(__name__)


def is_easy_apply(job: dict) -> bool:
    return "simplificada" in (job.get("note") or "").lower()


async def score_and_request(limit: int | None = None) -> dict:
    """One pass over unscored jobs. Returns a counts summary."""
    if not settings.apply_enabled:
        logger.info("Auto-apply disabled (APPLY_ENABLED=false)")
        return {}

    loop = asyncio.get_running_loop()
    user_id = await loop.run_in_executor(
        None, partial(get_scheduler_user_id, settings.scheduler_user_email or None)
    )
    if not user_id:
        logger.warning("Auto-apply: could not resolve user, skipping pass")
        return {}

    jobs = await loop.run_in_executor(
        None, partial(jobs_pending_scoring, user_id, limit or 10)
    )
    counts = {"scored": 0, "requested": 0, "skipped": 0, "failed": 0}

    for job in jobs:
        counts["scored"] += 1
        try:
            await _handle_one(job, loop, counts)
        except Exception:
            logger.exception("Auto-apply pass failed for job %s", job["id"])
            counts["failed"] += 1
            await loop.run_in_executor(None, partial(
                record_ats, job["id"], score=0, state="failed",
                reason="internal error during scoring/tailoring",
            ))

    logger.info(
        "Apply pass: scored %d, requested %d, skipped %d, failed %d",
        counts["scored"], counts["requested"], counts["skipped"], counts["failed"],
    )
    return counts


async def _handle_one(job: dict, loop, counts: dict) -> None:
    if is_blocked(job.get("company")):
        await loop.run_in_executor(None, partial(
            record_ats, job["id"], score=0, state="skipped",
            reason=f"empresa na blacklist: {job.get('company')}",
        ))
        counts["skipped"] += 1
        return

    # 1. Cheap deterministic gate first — no API spend on obvious misfits.
    prelim = ats.score(_base_resume_text(), job.get("description") or "", job["title"])

    if prelim.get("indeterminate"):
        # Missing data is not evidence of a bad fit; say so precisely.
        await loop.run_in_executor(None, partial(
            record_ats, job["id"], score=0, state="skipped",
            reason=f"cannot score: {prelim['indeterminate_reason']}",
        ))
        counts["skipped"] += 1
        return

    if settings.ats_gate_enabled and prelim["score"] < settings.ats_min_score:
        reason = f"ATS {prelim['score']} < {settings.ats_min_score}"
        if prelim["off_stack"]:
            reason += f" (off-stack: {', '.join(prelim['off_stack'][:3])})"
        await loop.run_in_executor(None, partial(
            record_ats, job["id"], score=prelim["score"], state="skipped", reason=reason,
        ))
        counts["skipped"] += 1
        return

    # 2. Tailor, then re-score the tailored resume.
    content, violations = await loop.run_in_executor(None, partial(tailor, job))
    if content is None:
        await loop.run_in_executor(None, partial(
            record_ats, job["id"], score=prelim["score"], state="skipped",
            reason=f"tailoring could not stay truthful: {', '.join(violations[:5])}",
        ))
        counts["skipped"] += 1
        return

    pdf, fit = await loop.run_in_executor(None, partial(build_pdf, job, content))

    # Score what was actually rendered. If one-page fitting dropped a bullet, the
    # content dict no longer matches the document being sent.
    content = render.effective_content(content, fit["dropped_bullets"])
    final = ats.score(ats.resume_text_of(content), job.get("description") or "", job["title"])

    await loop.run_in_executor(None, partial(
        record_ats, job["id"], score=final["score"], state="pending_approval",
        reason="awaiting Telegram approval", resume_path=str(pdf),
    ))
    await loop.run_in_executor(None, partial(
        _store_draft, job, content, final, str(pdf),
    ))
    await _request_approval(job, final, content, pdf)
    counts["requested"] += 1


async def process_job_id(job_id: str) -> dict:
    """Score + tailor one specific job on demand (Telegram link command, retry)."""
    loop = asyncio.get_running_loop()
    job = await loop.run_in_executor(None, partial(get_job, job_id))
    if not job:
        return {"error": "job not found"}

    counts = {"scored": 1, "requested": 0, "skipped": 0, "failed": 0}
    try:
        await _handle_one(job, loop, counts)
    except Exception:
        logger.exception("On-demand apply pass failed for %s", job_id)
        counts["failed"] += 1
    return counts


async def generate_cv(job_id: str, extra_prompt: str | None = None) -> dict:
    """Tailor + render a CV for one job on demand, then offer the next action.

    Deliberately skips the ATS gate: the reader asked for this specific job, so a
    low score is information to show them, not a reason to refuse.
    """
    loop = asyncio.get_running_loop()
    job = await loop.run_in_executor(None, partial(get_job, job_id))
    if not job:
        return {"error": "vaga não encontrada"}

    content, violations = await loop.run_in_executor(
        None, partial(tailor, job, extra_prompt)
    )
    if content is None:
        reason = f"não consegui gerar sem exagerar: {', '.join(violations[:5])}"
        await loop.run_in_executor(None, partial(
            record_ats, job_id, score=job.get("ats_score") or 0,
            state="skipped", reason=reason,
        ))
        return {"error": reason}

    # Render before scoring: one-page fitting can drop a bullet, and a score taken
    # from the pre-render dict would describe a document that was never sent.
    pdf, fit = await loop.run_in_executor(None, partial(build_pdf, job, content))
    content = render.effective_content(content, fit["dropped_bullets"])
    result = ats.score(ats.resume_text_of(content), job.get("description") or "", job["title"])
    await loop.run_in_executor(None, partial(
        record_ats, job_id, score=result["score"], state="pending_approval",
        reason="CV gerado sob demanda", resume_path=str(pdf),
    ))
    await loop.run_in_executor(None, partial(
        _store_draft, job, content, result, str(pdf), extra_prompt,
    ))

    await _send_cv(job, result, content, pdf, extra_prompt)
    return {"job_id": job_id, "score": result["score"], "pdf": str(pdf)}


def _store_draft(job: dict, content: dict, result: dict, pdf_path: str,
                 extra_prompt: str | None = None) -> None:
    """Keep the tailored dict, not just the PDF, so the dashboard can edit it.

    Failures here must never break the notification: the CV was generated and the
    reader should still hear about it.
    """
    try:
        payload = {k: v for k, v in content.items() if not k.startswith("_")}
        upsert_draft(
            job["id"], job["user_id"], status="ready", content=payload,
            generated_content=payload, meta=content.get("_meta"),
            language=content.get("_meta", {}).get("language", "pt"),
            ats_score=result["score"], ats_detail=result,
            extra_prompt=extra_prompt, pdf_path=pdf_path, pdf_committed=True,
            error=None,
        )
    except Exception:
        logger.exception("Could not persist resume draft for %s", job.get("id"))


def dashboard_button(job: dict) -> dict:
    """Deep link into the editor. Telegram stopped attaching the PDF — a document
    in a chat is final, and the whole point is that a CV should be correctable."""
    return {
        "text": "\u270f\ufe0f Editar CV",
        "url": f"{settings.dashboard_url.rstrip('/')}/jobs/{job['id']}/resume",
    }


async def _send_cv(job: dict, result: dict, content: dict, pdf: Path,
                   extra_prompt: str | None) -> None:
    e = html.escape
    easy = is_easy_apply(job)
    meta = content.get("_meta", {})

    score = result["score"]
    mark = "🎯" if score >= settings.ats_min_score else "⚠️"
    verdict = "" if score >= settings.ats_min_score else "  <b>(baixa compatibilidade)</b>"

    lines = [
        f'📄 <b><a href="{e(job["url"])}">{e(job["title"])}</a></b>',
        f"🏢 {e(job['company'])}",
        f"{mark} ATS <b>{score}</b>/100 · {len(result['matched'])} de {result['requirements']} requisitos{verdict}",
    ]
    if extra_prompt:
        lines.append(f"📝 instrução: <i>{e(extra_prompt[:120])}</i>")
    if result["missing"]:
        lines.append(f"❌ falta: {e(', '.join(result['missing'][:6]))}")
    if meta.get("pruned"):
        lines.append(f"✂️ removido: {e(', '.join(p[:26] for p in meta['pruned'][:3]))}")

    # Easy Apply is the only route this bot can drive end-to-end; for external
    # ATS forms, hand over the link rather than implying one-tap submission.
    if easy:
        lines.append("🟢 <b>Easy Apply</b> — posso enviar por você")
        if settings.apply_dry_run:
            lines.append("<i>DRY RUN — preenche mas não envia</i>")
        buttons = [
            [{"text": "✅ Candidatar", "callback_data": f"apply:{job['id']}"}],
            [{"text": "🔁 Refazer CV", "callback_data": f"gen:{job['id']}"},
             {"text": "🎯 Lacunas", "callback_data": f"gaps:{job['id']}"}],
        ]
    else:
        lines.append("🔗 Candidatura no site da empresa")
        buttons = [
            [{"text": "🌐 Abrir vaga", "url": job["url"]}],
            [{"text": "🔁 Refazer CV", "callback_data": f"gen:{job['id']}"},
             {"text": "🎯 Lacunas", "callback_data": f"gaps:{job['id']}"}],
        ]

    lines.append("✏️ <i>Edite, veja a análise ATS e baixe no dashboard</i>")
    buttons.insert(0, [dashboard_button(job)])
    await send_with_buttons("\n".join(lines), buttons)


def gap_report(job: dict) -> dict:
    """What the posting asks for that the resume doesn't show — the ATS gaps."""
    result = ats.score(_base_resume_text(), job.get("description") or "", job["title"])
    return result


def _base_resume_text() -> str:
    from resume import CONTENT
    return "\n".join(ats.resume_text_of(c) for c in CONTENT.values())


async def _request_approval(job: dict, result: dict, content: dict, pdf: Path) -> None:
    e = html.escape
    route = "Easy Apply" if is_easy_apply(job) else "site externo"
    omitted = content.get("_meta", {}).get("omitted_requirements", [])

    score = result["score"]
    mark = "🎯" if score >= settings.ats_min_score else "⚠️"
    verdict = "" if score >= settings.ats_min_score else "  <b>(baixa compatibilidade)</b>"

    lines = [
        f'<b><a href="{e(job["url"])}">{e(job["title"])}</a></b>',
        f"🏢 {e(job['company'])}",
        f"{mark} ATS <b>{score}</b>/100 · {len(result['matched'])} de {result['requirements']} requisitos{verdict}",
        f"🤖 via {e(route)}",
    ]
    if result["missing"]:
        lines.append(f"❌ falta: {e(', '.join(result['missing'][:6]))}")
    if omitted:
        lines.append(f"🚫 omitido do CV (não possui): {e(', '.join(omitted[:4]))}")
    pruned = content.get("_meta", {}).get("pruned", [])
    if pruned:
        lines.append(f"✂️ removido por não ser relevante: {e(', '.join(p[:30] for p in pruned[:4]))}")
    if settings.apply_dry_run:
        lines.append("\n<i>DRY RUN — vai preencher o formulário mas NÃO enviar</i>")
    lines.append("<i>Candidatar pede uma segunda confirmação antes de enviar.</i>")

    lines.append("✏️ <i>Edite, veja a análise ATS e baixe no dashboard</i>")
    await send_with_buttons(
        "\n".join(lines),
        [
            [dashboard_button(job)],
            [
                {"text": "✅ Candidatar", "callback_data": f"apply:{job['id']}"},
                {"text": "⏭️ Pular", "callback_data": f"skip:{job['id']}"},
            ],
            [{"text": "🎯 Ver lacunas do ATS", "callback_data": f"gaps:{job['id']}"}],
        ],
    )

"""Telegram control surface for the apply pipeline.

Commands (just send them to the bot):
  <linkedin job url>  — pull that posting in, score it, tailor a CV, ask to apply
  /gaps <url|id>      — what the posting wants that your CV doesn't show
  /skill <text>       — record a skill you actually have (updates ME.md)
  /pending            — jobs waiting on your approval
  /help

Submitting requires two taps: Candidatar, then an explicit Confirmar. Nothing
reaches an employer without both.
"""

import asyncio
import json
import logging
import re
from functools import partial

import aio_pika
import httpx
from aio_pika.abc import AbstractChannel

from app.config import settings
from app.db.client import get_job, record_ats
from app.notify.telegram import API_BASE, _is_configured, send_message

logger = logging.getLogger(__name__)

_JOB_URL_RE = re.compile(r"https?://(?:[\w-]+\.)?linkedin\.com/jobs/(?:view|search-results)/\S*", re.I)


async def _api(method: str, payload: dict) -> dict | None:
    url = f"{API_BASE}/bot{settings.telegram_token}/{method}"
    try:
        async with httpx.AsyncClient(timeout=40) as client:
            r = await client.post(url, json=payload)
        if r.status_code != 200:
            logger.error("Telegram %s failed (%s): %s", method, r.status_code, r.text[:300])
            return None
        return r.json()
    except httpx.ReadTimeout:
        return None
    except Exception:
        logger.exception("Telegram %s raised", method)
        return None


async def _enqueue_apply(channel: AbstractChannel, job_id: str) -> None:
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps({"job_id": job_id}).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        ),
        routing_key=settings.apply_queue,
    )


# ---------------------------------------------------------------------------
# Callback buttons
# ---------------------------------------------------------------------------

async def _handle_callback(channel: AbstractChannel, cb: dict) -> None:
    data = cb.get("data") or ""
    cb_id = cb["id"]
    msg = cb.get("message") or {}
    loop = asyncio.get_running_loop()

    action, _, job_id = data.partition(":")
    job = await loop.run_in_executor(None, partial(get_job, job_id)) if job_id else None
    if not job:
        await _api("answerCallbackQuery", {"callback_query_id": cb_id, "text": "Vaga não encontrada"})
        return

    if action in {"gen", "gaps"}:
        pass  # read-only actions stay available regardless of state
    elif job.get("apply_state") in {"applied", "applying"}:
        await _api("answerCallbackQuery", {
            "callback_query_id": cb_id, "text": f"Já processada ({job['apply_state']})"})
        return

    # Step 1 — ask for an explicit second confirmation before anything is sent.
    if action == "apply":
        await _api("answerCallbackQuery", {"callback_query_id": cb_id})
        mode = "DRY RUN (não envia)" if settings.apply_dry_run else "ENVIO REAL"
        await _api("sendMessage", {
            "chat_id": settings.telegram_chat_id,
            "text": (
                f"⚠️ <b>Confirmar candidatura?</b>\n"
                f"{job['company']} — {job['title']}\n"
                f"Modo: <b>{mode}</b>\n\n"
                "Esta ação não pode ser desfeita."
            ),
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": [[
                {"text": "✅ Confirmar envio", "callback_data": f"confirm:{job_id}"},
                {"text": "❌ Cancelar", "callback_data": f"cancel:{job_id}"},
            ]]},
        })
        return

    # Step 2 — the only path that enqueues an application.
    if action == "confirm":
        await loop.run_in_executor(None, partial(
            record_ats, job_id, score=job.get("ats_score") or 0,
            state="applying", reason="confirmed in Telegram (2-step)"))
        await _enqueue_apply(channel, job_id)
        text, note = "Enviando…", "✅ <b>Confirmado</b> — candidatura em andamento"
    elif action in {"skip", "cancel"}:
        await loop.run_in_executor(None, partial(
            record_ats, job_id, score=job.get("ats_score") or 0,
            state="skipped", reason=f"{action} in Telegram"))
        text, note = "Cancelada", "⏭️ <b>Cancelada</b>"
    elif action == "gaps":
        await _api("answerCallbackQuery", {"callback_query_id": cb_id})
        await _send_gaps(job)
        return
    elif action == "gen":
        await _api("answerCallbackQuery", {"callback_query_id": cb_id, "text": "Gerando CV…"})
        from app.apply.pipeline import generate_cv
        result = await generate_cv(job_id)
        if result.get("error"):
            await send_message(f"⚠️ {result['error']}")
        return
    else:
        return

    await _api("answerCallbackQuery", {"callback_query_id": cb_id, "text": text})
    if msg.get("message_id"):
        await _api("editMessageText", {
            "chat_id": settings.telegram_chat_id,
            "message_id": msg["message_id"],
            "text": (msg.get("text", "") + "\n\n" + note),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })


# ---------------------------------------------------------------------------
# Text commands
# ---------------------------------------------------------------------------

_HELP = (
    "<b>Comandos</b>\n"
    "• Mande um <b>link de vaga do LinkedIn</b> — eu analiso, gero o CV e peço aprovação\n"
    "• <code>/gaps &lt;link ou id&gt;</code> — o que a vaga pede e o seu CV não mostra\n"
    "• <code>/skill &lt;texto&gt;</code> — registra algo que você realmente sabe (atualiza o ME.md)\n"
    "• <code>/cv &lt;link ou id&gt; [instruções]</code> — gera o CV, com instruções opcionais\n"
    "• <code>/pending</code> — vagas aguardando aprovação\n\n"
    "Enviar candidatura exige <b>dois toques</b>: Candidatar e depois Confirmar."
)


async def _send_gaps(job: dict) -> None:
    from app.apply.pipeline import gap_report

    loop = asyncio.get_running_loop()
    r = await loop.run_in_executor(None, partial(gap_report, job))

    if r.get("indeterminate"):
        await send_message(f"🤷 Não dá para avaliar: {r['indeterminate_reason']}")
        return

    missing = r["missing"]
    lines = [
        f"🎯 <b>{job['company']} — {job['title'][:60]}</b>",
        f"ATS <b>{r['score']}</b>/100 · {len(r['matched'])} de {r['requirements']} requisitos",
    ]
    if missing:
        lines.append(f"\n❌ <b>Falta no CV ({len(missing)}):</b>\n" + ", ".join(missing[:20]))
        lines.append(
            "\n💡 Se você <b>realmente</b> souber alguma delas, mande:\n"
            f"<code>/skill {missing[0]}</code>\n"
            "Isso entra no ME.md e passa a valer para todos os CVs."
        )
    else:
        lines.append("\n✅ Nenhuma lacuna — o CV cobre tudo que a vaga pede.")
    await send_message("\n".join(lines))


def _append_skill(text: str) -> str:
    """Record a genuinely-held skill in ME.md so tailoring may use it.

    Appended as the last row of the Stack table. Inserting it merely "before
    ## Experience" left an orphan row separated by a blank line, which markdown
    renders as a second broken table.
    """
    from pathlib import Path

    me = Path("ME.md")
    lines = me.read_text().split("\n")
    skill = text.strip()
    row = f"| Extra          | {skill} |"

    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip().startswith("## Stack"))
        # Bound the search to this section: searching to EOF finds the last row of
        # the diversity table further down and appends the skill there.
        end = next(
            (i for i, ln in enumerate(lines[start + 1:], start=start + 1)
             if ln.startswith("## ")),
            len(lines),
        )
        last_row = max(
            i for i, ln in enumerate(lines[start:end], start=start)
            if ln.lstrip().startswith("|")
        )
        lines.insert(last_row + 1, row)
    except (StopIteration, ValueError):
        lines.append(row)

    me.write_text("\n".join(lines))
    return skill


async def _handle_text(channel: AbstractChannel, message: dict) -> None:
    text = (message.get("text") or "").strip()
    if not text:
        return
    loop = asyncio.get_running_loop()

    if text.startswith("/help") or text.startswith("/start"):
        await send_message(_HELP)
        return

    if text.startswith("/skill"):
        skill = text[len("/skill"):].strip()
        if not skill:
            await send_message("Uso: <code>/skill NestJS, Turborepo</code>")
            return
        added = await loop.run_in_executor(None, partial(_append_skill, skill))
        await send_message(
            f"✅ Registrado no ME.md: <b>{added}</b>\n"
            "<i>Só registre o que você realmente sabe — isso vai para CVs enviados a empresas.</i>"
        )
        return

    if text.startswith("/cv"):
        arg = text[len("/cv"):].strip()
        if not arg:
            await send_message(
                "Uso: <code>/cv &lt;link ou id&gt; [instruções extras]</code>\n"
                "Ex.: <code>/cv 4452529315 foque em backend Python e mensageria</code>"
            )
            return
        token, _, extra = arg.partition(" ")
        job = await _resolve_job(token)
        if not job:
            await send_message("Não achei essa vaga. Mande o link ou o id.")
            return
        from app.apply.pipeline import generate_cv
        await send_message("📄 Gerando CV" + (" com suas instruções…" if extra.strip() else "…"))
        result = await generate_cv(job["id"], extra.strip() or None)
        if result.get("error"):
            await send_message(f"⚠️ {result['error']}")
        return

    if text.startswith("/pending"):
        await _send_pending()
        return

    if text.startswith("/gaps"):
        arg = text[len("/gaps"):].strip()
        job = await _resolve_job(arg)
        if not job:
            await send_message("Não achei essa vaga. Mande o link ou o id.")
            return
        await _send_gaps(job)
        return

    match = _JOB_URL_RE.search(text)
    if match:
        await _handle_job_link(match.group(0))
        return

    await send_message(_HELP)


async def _resolve_job(arg: str) -> dict | None:
    from app.apply.intake import ingest_url

    loop = asyncio.get_running_loop()
    if not arg:
        return None
    if _JOB_URL_RE.match(arg):
        result = await ingest_url(arg)
        if result.get("error"):
            return None
        return await loop.run_in_executor(None, partial(get_job, result["job_id"]))
    return await loop.run_in_executor(None, partial(get_job, arg))


async def _handle_job_link(url: str) -> None:
    from app.apply.intake import ingest_url
    from app.apply.pipeline import process_job_id

    await send_message("🔎 Analisando a vaga…")
    result = await ingest_url(url)
    if result.get("error"):
        await send_message(f"⚠️ {result['error']}")
        return

    job_id = result["job_id"]
    if result.get("existing") and result.get("apply_state") in {"applied", "applying"}:
        await send_message(f"ℹ️ Já processada ({result['apply_state']}).")
        return

    counts = await process_job_id(job_id)
    if counts.get("requested"):
        return  # the approval card was already sent
    if counts.get("skipped"):
        job = get_job(job_id)
        await send_message(
            f"⏭️ Não passou no filtro: <i>{job.get('apply_reason')}</i>\n"
            f"Use <code>/gaps {job_id}</code> para ver o que falta."
        )
    elif counts.get("error"):
        await send_message(f"⚠️ {counts['error']}")


async def _send_pending() -> None:
    import psycopg
    from psycopg.rows import dict_row

    def _q():
        with psycopg.connect(settings.database_url, row_factory=dict_row) as c:
            return c.execute(
                "SELECT id, title, company, ats_score FROM job "
                "WHERE apply_state = 'pending_approval' ORDER BY scraped_at DESC LIMIT 10"
            ).fetchall()

    rows = await asyncio.get_running_loop().run_in_executor(None, _q)
    if not rows:
        await send_message("Nenhuma vaga aguardando aprovação.")
        return
    lines = ["<b>Aguardando aprovação</b>"]
    lines += [f"• {r['company']} — {r['title'][:44]} (ATS {r['ats_score']})" for r in rows]
    await send_message("\n".join(lines))


# ---------------------------------------------------------------------------

async def run_approval_bot(channel: AbstractChannel) -> None:
    if not _is_configured():
        logger.warning("Approval bot not started — Telegram not configured")
        return

    logger.info("Approval bot listening (links, /gaps, /skill, 2-step confirm)")
    offset: int | None = None

    while True:
        try:
            payload = {"timeout": 30, "allowed_updates": ["callback_query", "message"]}
            if offset is not None:
                payload["offset"] = offset
            data = await _api("getUpdates", payload)
            if not data or not data.get("ok"):
                await asyncio.sleep(3)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                try:
                    if "callback_query" in update:
                        await _handle_callback(channel, update["callback_query"])
                    elif "message" in update:
                        await _handle_text(channel, update["message"])
                except Exception:
                    logger.exception("Failed handling update %s", update.get("update_id"))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Approval bot loop error — retrying")
            await asyncio.sleep(5)

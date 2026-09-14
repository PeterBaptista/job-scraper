"""Resume API — the dashboard's editor talks to this.

Everything here reuses the existing pipeline pieces: `resume.build_with_content`
stays the only renderer and `app/apply/ats.py` stays the only scorer. Nothing in
this module reimplements either.

Handlers are sync `def`, not `async def`, on purpose. This process also runs the
RabbitMQ consumers, the scheduler and the Telegram long-poll on one event loop;
ReportLab and pypdf are CPU-bound, so an async handler would freeze the bot for
the duration of every keystroke's render. Sync handlers go to the threadpool.
"""

import base64
import copy
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.apply import ats, render
from app.apply.tailor import build_pdf, tailor
from app.config import settings
from app.db.client import get_draft, get_job, record_ats, upsert_draft

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/resume", tags=["resume"])


def _authorize(token: str | None) -> None:
    """Fail closed. A blank configured token disables the API entirely rather
    than accepting every caller — port 8000 is published to the host."""
    if not settings.internal_api_token:
        raise HTTPException(503, "resume API disabled: INTERNAL_API_TOKEN is not set")
    if token != settings.internal_api_token:
        raise HTTPException(401, "invalid internal token")


def _job_or_404(job_id: str) -> dict:
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ContentRequest(BaseModel):
    content: dict[str, Any]


class TailorRequest(BaseModel):
    extra_prompt: str | None = None


class AnalysisResponse(BaseModel):
    """The score always describes `content` — which is post-fitting, so it
    describes the PDF rather than what the editor submitted."""

    content: dict[str, Any]
    ats: dict[str, Any]
    violations: list[str] = Field(default_factory=list)
    over_pruned: list[str] = Field(default_factory=list)
    # Missing terms the profile actually backs, so the UI can distinguish
    # "you have this, it just isn't shown" from "claiming this would be a lie".
    coverable: list[str] = Field(default_factory=list)


class PreviewResponse(AnalysisResponse):
    pdf_base64: str
    fit: dict[str, Any]


class CommitResponse(PreviewResponse):
    resume_path: str



def _coverable(missing: list[str]) -> list[str]:
    """Of the posting's unmet requirements, the ones the candidate genuinely has.

    Same test `tailor()` uses to decide whether another optimisation pass could
    help: present in the truthful corpus, absent from the resume. Adding one of
    these is recovering a fact; adding anything else is inventing one.
    """
    corpus = ats.truthful_corpus()
    return [term for term in missing if ats._norm(term) in corpus]


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


@router.get("/{job_id}/draft")
def read_draft(job_id: str, x_internal_token: str | None = Header(None)) -> dict:
    _authorize(x_internal_token)
    draft = get_draft(job_id)
    if not draft:
        raise HTTPException(404, "no draft for this job")
    return draft


@router.get("/base")
def read_base(lang: str = "pt", x_internal_token: str | None = Header(None)) -> dict:
    """The untailored resume — powers "revert to the base CV"."""
    _authorize(x_internal_token)
    from resume import CONTENT, PROFILE

    if lang not in CONTENT:
        raise HTTPException(400, f"unknown language: {lang}")
    return {"profile": PROFILE, "content": CONTENT[lang]}


@router.get("/{job_id}/gaps")
def read_gaps(job_id: str, x_internal_token: str | None = Header(None)) -> dict:
    """What the posting asks for that the *base* resume doesn't show.

    The difference between this and the draft's own score is exactly what
    tailoring bought — and, for anything that moved the other way, what it lost.
    """
    _authorize(x_internal_token)
    from app.apply.pipeline import gap_report

    return gap_report(_job_or_404(job_id))


# ---------------------------------------------------------------------------
# Score and render
# ---------------------------------------------------------------------------


@router.post("/{job_id}/analyze", response_model=AnalysisResponse)
def analyze(
    job_id: str,
    body: ContentRequest | None = None,
    x_internal_token: str | None = Header(None),
) -> AnalysisResponse:
    """ATS analysis without rendering — cheap enough to run while typing.

    Because nothing is rendered, one-page fitting has not run, so this score can
    be optimistic if the content is long enough to trigger a tier-4 drop. The UI
    labels it provisional until the next preview confirms it.
    """
    _authorize(x_internal_token)
    job = _job_or_404(job_id)

    content = body.content if body and body.content else None
    if content is None:
        draft = get_draft(job_id)
        if not draft or not draft.get("content"):
            raise HTTPException(404, "no content to analyze")
        content = draft["content"]

    from resume import CONTENT

    description = job.get("description") or ""
    text = ats.resume_text_of(content)
    result = ats.score(text, description, job["title"])
    return AnalysisResponse(
        content=content,
        ats=result,
        violations=ats.truthfulness_violations(text),
        over_pruned=ats.over_pruned_requirements(CONTENT, content, description),
        coverable=_coverable(result["missing"]),
    )


@router.post("/{job_id}/preview", response_model=PreviewResponse)
def preview(
    job_id: str,
    body: ContentRequest,
    x_internal_token: str | None = Header(None),
) -> PreviewResponse:
    """Render to a temp file and score the result, in one round trip.

    One endpoint rather than two so the score and the document can never come
    from different content — the guarantee that the ATS number matches the PDF
    depends on both being derived from the same render.
    """
    _authorize(x_internal_token)
    job = _job_or_404(job_id)
    pdf_bytes, result = render.preview(job, body.content)
    return PreviewResponse(
        pdf_base64=base64.b64encode(pdf_bytes).decode(),
        fit=result["fit"],
        content=result["content"],
        ats=result["ats"],
        violations=result["violations"],
        over_pruned=result["over_pruned"],
        coverable=_coverable(result["ats"]["missing"]),
    )


@router.post("/{job_id}/commit", response_model=CommitResponse)
def commit(
    job_id: str,
    body: ContentRequest,
    x_internal_token: str | None = Header(None),
) -> CommitResponse:
    """Write the real PDF and point `job.resume_path` at it.

    This is the only path that writes into `generated_resumes/`, which is what
    keeps Easy Apply working: `app/apply/worker.py` reads that path from disk
    inside this container, so the file has to be written by this process.
    """
    _authorize(x_internal_token)
    job = _job_or_404(job_id)

    content = copy.deepcopy(body.content)
    pdf, fit = build_pdf(job, content)
    content = render.effective_content(content, fit["dropped_bullets"])

    from resume import CONTENT

    description = job.get("description") or ""
    text = ats.resume_text_of(content)
    result = ats.score(text, description, job["title"])
    violations = ats.truthfulness_violations(text)

    record_ats(
        job_id, score=result["score"], state="pending_approval",
        reason="CV editado no dashboard", resume_path=str(pdf),
    )
    upsert_draft(
        job_id, job["user_id"], status="ready", content=content,
        ats_score=result["score"], ats_detail=result,
        pdf_path=str(pdf), pdf_committed=True, error=None,
    )

    return CommitResponse(
        pdf_base64=base64.b64encode(pdf.read_bytes()).decode(),
        fit=fit, content=content, ats=result, violations=violations,
        over_pruned=ats.over_pruned_requirements(CONTENT, content, description),
        coverable=_coverable(result["missing"]),
        resume_path=str(pdf),
    )


# ---------------------------------------------------------------------------
# Save and tailor
# ---------------------------------------------------------------------------


@router.put("/{job_id}/draft")
def save_draft(
    job_id: str,
    body: ContentRequest,
    x_internal_token: str | None = Header(None),
) -> dict:
    """Persist edits without rendering. Autosave calls this; it must be cheap."""
    _authorize(x_internal_token)
    job = _job_or_404(job_id)
    return upsert_draft(job_id, job["user_id"], status="ready",
                        content=body.content, error=None)


@router.post("/{job_id}/tailor", status_code=202)
async def start_tailoring(
    job_id: str,
    body: TailorRequest | None = None,
    x_internal_token: str | None = Header(None),
) -> dict:
    """Kick off tailoring and return immediately.

    `tailor()` is up to `ats_max_passes` sequential OpenAI calls — tens of
    seconds to minutes. The draft row carries the status, so the dashboard polls
    the database the same way it already polls scrape progress, and the poll
    survives a scraper restart in a way an in-memory task registry would not.
    """
    import asyncio

    _authorize(x_internal_token)
    job = _job_or_404(job_id)
    extra_prompt = body.extra_prompt if body else None

    upsert_draft(job_id, job["user_id"], status="tailoring",
                 extra_prompt=extra_prompt, error=None)
    asyncio.create_task(_run_tailoring(job, extra_prompt))
    return {"status": "tailoring", "job_id": job_id}


async def _run_tailoring(job: dict, extra_prompt: str | None) -> None:
    import asyncio
    from functools import partial

    loop = asyncio.get_running_loop()
    job_id, user_id = job["id"], job["user_id"]
    try:
        content, violations = await loop.run_in_executor(
            None, partial(tailor, job, extra_prompt)
        )
        if content is None:
            reason = ", ".join(violations[:5]) or "tailoring failed"
            upsert_draft(job_id, user_id, status="failed", error=reason)
            record_ats(job_id, score=job.get("ats_score") or 0, state="skipped",
                       reason=f"não consegui gerar sem exagerar: {reason}")
            return

        meta = content.get("_meta", {})
        pdf, fit = await loop.run_in_executor(None, partial(build_pdf, job, content))
        content = render.effective_content(content, fit["dropped_bullets"])
        result = ats.score(
            ats.resume_text_of(content), job.get("description") or "", job["title"]
        )

        payload = {k: v for k, v in content.items() if not k.startswith("_")}
        upsert_draft(
            job_id, user_id, status="ready", content=payload,
            generated_content=payload, meta=meta,
            language=meta.get("language", "pt"),
            ats_score=result["score"], ats_detail=result,
            pdf_path=str(pdf), pdf_committed=True, error=None,
        )
        record_ats(job_id, score=result["score"], state="pending_approval",
                   reason="CV gerado — editável no dashboard", resume_path=str(pdf))
    except Exception as exc:
        logger.exception("Tailoring failed for %s", job_id)
        upsert_draft(job_id, user_id, status="failed", error=str(exc)[:500])


@router.post("/{job_id}/reset")
def reset_draft(
    job_id: str,
    lang: str = "",
    x_internal_token: str | None = Header(None),
) -> dict:
    """Revert to the generated version, or to the base CV when `lang` is given."""
    _authorize(x_internal_token)
    job = _job_or_404(job_id)
    draft = get_draft(job_id)

    if lang:
        from resume import CONTENT

        if lang not in CONTENT:
            raise HTTPException(400, f"unknown language: {lang}")
        content = copy.deepcopy(CONTENT[lang])
    else:
        if not draft or not draft.get("generated_content"):
            raise HTTPException(404, "no generated version to revert to")
        content = draft["generated_content"]

    return upsert_draft(job_id, job["user_id"], status="ready",
                        content=content, language=lang or None, error=None)


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


@router.get("/{job_id}/tailor/stream")
async def stream_tailoring(
    job_id: str,
    token: str = Query(""),
    extra_prompt: str = Query(""),
) -> StreamingResponse:
    """Tailor with the model's output streamed to the browser as it is written.

    The token arrives as a query parameter because this is consumed by EventSource
    semantics through a proxying route handler, not a normal JSON fetch. It is the
    same secret and the same check.

    Events: `pass` (which optimisation pass), `delta` (raw JSON text), `done`
    (the validated, rendered, persisted result), `error`. Only `done` is
    authoritative — deltas are unvalidated model output shown for feedback.
    """
    import asyncio
    import json as _json

    _authorize(token)
    job = _job_or_404(job_id)

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def emit(event: str, data) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, (event, data))

    def work() -> None:
        try:
            content, violations = tailor(
                job, extra_prompt or None,
                on_delta=lambda piece: emit("delta", piece),
                on_pass=lambda n: emit("pass", n),
            )
            if content is None:
                reason = ", ".join(violations[:5]) or "tailoring failed"
                upsert_draft(job_id, job["user_id"], status="failed", error=reason)
                emit("error", reason)
                return

            meta = content.get("_meta", {})
            pdf, fit = build_pdf(job, content)
            final = render.effective_content(content, fit["dropped_bullets"])
            result = ats.score(
                ats.resume_text_of(final), job.get("description") or "", job["title"]
            )
            payload = {k: v for k, v in final.items() if not k.startswith("_")}

            upsert_draft(
                job_id, job["user_id"], status="ready", content=payload,
                generated_content=payload, meta=meta,
                language=meta.get("language", "pt"),
                ats_score=result["score"], ats_detail=result,
                pdf_path=str(pdf), pdf_committed=True, error=None,
            )
            record_ats(job_id, score=result["score"], state="pending_approval",
                       reason="CV gerado — editável no dashboard", resume_path=str(pdf))
            emit("done", {
                "content": payload, "meta": meta, "ats": result, "fit": fit,
                "violations": ats.truthfulness_violations(ats.resume_text_of(final)),
            })
        except Exception as exc:
            logger.exception("Streaming tailor failed for %s", job_id)
            upsert_draft(job_id, job["user_id"], status="failed", error=str(exc)[:500])
            emit("error", str(exc)[:300])
        finally:
            emit("__end__", None)

    upsert_draft(job_id, job["user_id"], status="tailoring",
                 extra_prompt=extra_prompt or None, error=None)
    # The OpenAI SDK is synchronous; run it off the loop that also serves the
    # Telegram poll and the RabbitMQ consumers.
    loop.run_in_executor(None, work)

    async def events():
        while True:
            event, data = await queue.get()
            if event == "__end__":
                break
            yield f"event: {event}\ndata: {_json.dumps(data)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

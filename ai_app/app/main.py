"""
FastAPI app for the RDPR (Panchayat Raj) data assistant.
  GET  /, /dashboard   dashboard UI (the entry page): Finance & Accounting, Revenue and HRMS for a FY and zilla
  GET  /api/dashboard  ?fy=2025-26&zilla=Mysuru (both optional): fixed, reviewed read-only summary queries
  GET  /api/options    financial years and zillas for the dashboard filters
  GET  /insights       key insights as KPI cards (GET /api/insights?fy=2025-26)
  GET  /api/mis-report ?fy=&zilla=&kind=current|all&module=revenue|finance|hrms: the dashboard selection as Excel
                       (/api/mis-report/view: the same workbook as an on-screen preview)
  GET  /chat           chat UI (AI mode)
  POST /api/ask        SSE: status (one per real pipeline stage) -> sql (admins only) -> answer_chunk ... -> chart -> table -> done
  POST /api/ask_once   same pipeline, plain JSON (scripts, evaluation)
  GET  /health         liveness, data period, whether the LLM gateway (and the voice services) are configured

VOICE MODE (the hands-free voice agent in AI mode; modelled on the Meghalaya voice agent as integrated into KPCL):
  {"question": ..., "mode": "voice"} on /api/ask(_once) adds spoken_answer (app/spoken.py, built from the verified
  answer with no model call, under the guardrails in app/voice_guard.py) to the response / an early SSE "spoken" event.
  POST /api/voice/transcribe     raw 16 kHz WAV body -> {"text", "heard", "confirm", "rejected", "message"} (qwen3-asr)
  POST /api/voice/speak          {"text", "speed"?} -> audio/wav            (Qwen3-TTS, officer voice)
  POST /api/voice/speak/stream   same body -> audio/pcm s16le mono, rate in X-Audio-Sample-Rate
  GET  /api/voice/filler         {"filler"} -- "Let me check that.", spoken while the answer is worked out
  GET  /api/voice/config         what the page may use (speech in, speech out, streaming, speed)
  GET  /api/voice/health         speech in / speech out reachability (cached two minutes)
Every speak failure is a 503 carrying spoken_text, so the page falls back to the browser's own voice.

The read-only database connection and the LLM client are created once in lifespan and reused. SQL, timings, routes,
entities and error details are shown only when RDPR_SHOW_TECHNICAL_DETAILS=true.
"""
from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import re
from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from app import answer_report, dashboard_data, followup, insights, mis_report, small_talk, spoken, voice, voice_guard
from app.config import settings
from app.dashboard_data import DashboardNotFound, build_dashboard, options
from app.db import get_db, init_db, shutdown_db
from app.guardrails import REFUSALS
from app.llm import init_llm_client, shutdown_llm_client
from app.models import AskRequest, AskResponse
from app.pipeline import answer_question
from app.protection import Protection
from app.semantic_layer import load_semantic_layer, router_index

_STATIC = Path(__file__).resolve().parent / "static"
_TECH = settings.rdpr_show_technical_details
_log = logging.getLogger(__name__)
# The speech-detection model (Silero VAD on ONNX Runtime Web) is served from /static/vendor/vad.
mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("text/javascript", ".mjs")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_llm_client()
    voice.init_voice_client()
    load_semantic_layer()
    router_index()
    # The statewide dashboard and insights are the first pages most people open; build them in the background so the
    # first visitor doesn't wait for the cold full-table queries (the results are cached for an hour).
    warm = asyncio.create_task(_warm_caches())
    warm_voice = asyncio.create_task(_warm_tts_cache())
    yield
    warm.cancel()
    warm_voice.cancel()
    shutdown_db()
    await shutdown_llm_client()
    await voice.shutdown_voice_client()


async def _warm_caches() -> None:
    """Build every FY statewide, every zilla for the default FY and the insights of every FY in the background, so no
    visitor waits for a cold page (each takes milliseconds on the pre-summed mart tables)."""
    try:
        db = get_db()
        await dashboard_data.warm(db)
        for fy in options()["fiscal_years"]:
            await insights.build_insights(db, fy)
        _log.info("caches warm")
    except Exception:  # noqa: BLE001 -- warming is best effort; a real request still builds the page
        _log.exception("cache warm-up failed")


app = FastAPI(title="RDPR Data Assistant", lifespan=lifespan, docs_url="/docs" if _TECH else None, redoc_url=None,
              openapi_url="/openapi.json" if _TECH else None)
class _NoCacheStatic(StaticFiles):
    """Serve the pages' own CSS/JS without browser caching.

    The dashboard and chat are a single-page front end edited in place: with the default validators a browser
    keeps serving an old chat.js or site.css after a redeploy, so the UI looks unchanged until the user knows to
    hard-refresh. These files are small and local, so re-fetching them costs nothing.
    """

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        for header in ("etag", "last-modified"):
            if header in response.headers:
                del response.headers[header]
        return response


app.mount("/static", _NoCacheStatic(directory=_STATIC), name="static")
app.add_middleware(Protection)
# compress JSON, HTML, CSS and JS (the answer stream, text/event-stream, is left alone so it is never buffered)
app.add_middleware(GZipMiddleware, minimum_size=1024)
# At most this many questions are answered at once (each may hold one call to the shared gateway); the rest wait up to
# RDPR_QUEUE_WAIT_SECONDS, then get a polite "busy" answer instead of piling up.
_SLOTS = asyncio.Semaphore(settings.rdpr_max_concurrent_questions)


@app.exception_handler(RequestValidationError)
async def _bad_request(request: Request, exc: RequestValidationError):
    if _TECH:
        return JSONResponse(status_code=422, content={"detail": exc.errors()})
    too_long = any("too_long" in str(e.get("type", "")) for e in exc.errors())
    return JSONResponse(status_code=400, content={"detail": REFUSALS["too_long" if too_long else "empty"]})


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    _log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": REFUSALS["error"]})


@app.get("/health")
async def health():
    period = load_semantic_layer()["data_period"]
    return {"status": "ok", "data_from": period["data_from"], "data_to": period["data_to"],
            "llm_configured": settings.llm_configured, "technical": _TECH,
            "voice": {"speech_in": settings.asr_configured, "speech_out": settings.tts_configured}}


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_ui():
    return (_STATIC / "dashboard.html").read_text(encoding="utf-8")


@app.get("/chat", response_class=HTMLResponse)
async def chat_ui():
    return (_STATIC / "chat.html").read_text(encoding="utf-8")


@app.get("/api/options")
async def options_api():
    return options()


@app.get("/api/dashboard")
async def dashboard_api(fy: str | None = None, zilla: str | None = None):
    """Fixed, reviewed read-only queries (app/dashboard_data.py). An unknown FY or zilla is a 404, never a query."""
    if (fy is not None and len(fy) > 10) or (zilla is not None and len(zilla) > 40):
        return JSONResponse(status_code=404, content={"detail": "Not found."})
    try:
        return await build_dashboard(get_db(), fy, zilla or None)
    except DashboardNotFound as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.get("/insights", response_class=HTMLResponse)
async def insights_ui():
    return (_STATIC / "insights.html").read_text(encoding="utf-8")


@app.get("/api/insights")
async def insights_api(fy: str | None = None):
    """Key insights as KPI cards: every figure from the dashboard's own reviewed queries (app.insights.build_insights)."""
    if _bad(fy, limit=10):
        return _NOT_FOUND
    try:
        return await insights.build_insights(get_db(), fy)
    except DashboardNotFound as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})


async def _mis(fy: str | None, zilla: str | None, kind: str, module: str):
    if _bad(fy, limit=10) or _bad(zilla) or kind not in ("current", "all") or module not in mis_report.MODULES:
        raise DashboardNotFound("Not found.")
    d = await build_dashboard(get_db(), fy, zilla or None)
    return d, mis_report.build_sheets(d, kind, module)


@app.get("/api/mis-report")
async def mis_report_api(fy: str | None = None, zilla: str | None = None, kind: str = "current", module: str = "revenue"):
    """The dashboard's selection as an Excel MIS report, built from the same payload the page shows."""
    try:
        d, sheets = await _mis(fy, zilla, kind, module)
    except DashboardNotFound as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    name = mis_report.file_name(d, kind, module)
    if (failed := mis_report.failed_checks(sheets)):
        return JSONResponse(status_code=409, content={"detail": "This report is under review.", "message":
                            "This report is under review: its integrity checks did not pass (" + "; ".join(failed) + ")."})
    body = await asyncio.to_thread(mis_report.build_xlsx, sheets, name[:-5])
    return Response(content=body, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/mis-report/view")
async def mis_report_view_api(fy: str | None = None, zilla: str | None = None, kind: str = "current", module: str = "revenue"):
    """The same workbook as Excel-style grids for the on-screen preview (report-viewer.js)."""
    try:
        d, sheets = await _mis(fy, zilla, kind, module)
    except DashboardNotFound as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    return mis_report.view(sheets, mis_report.file_name(d, kind, module))


_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_GONE = {"detail": "This report is no longer available. Please ask the question again."}


@app.get("/api/answer-report/{report_id}/view")
async def answer_report_view_api(report_id: str):
    """The same workbook as /api/answer-report/{id}, rendered for the on-screen viewer."""
    kept = answer_report.get(report_id, get_db().version)
    if kept is None:
        return JSONResponse(status_code=404, content=_GONE)
    sheets, name = await answer_report.build(get_db(), kept)
    return JSONResponse(mis_report.view(sheets, name), headers={"Cache-Control": "no-store"})


@app.get("/api/answer-report/{report_id}")
async def answer_report_api(report_id: str):
    """Excel for one answer the server kept (app/answer_report.py). Unknown or expired ids are a 404; an answer whose
    integrity check fails is a 409 'under review', never a wrong file."""
    kept = answer_report.get(report_id, get_db().version)
    if kept is None:
        return JSONResponse(status_code=404, content=_GONE)
    sheets, name = await answer_report.build(get_db(), kept)
    if (failed := mis_report.failed_checks(sheets)):
        return JSONResponse(status_code=409, content={"detail": "This report is under review.",
                                                      "message": "This report is under review: " + "; ".join(failed) + "."})
    body = await asyncio.to_thread(mis_report.build_xlsx, sheets, name[:-5])
    return Response(content=body, media_type=_XLSX, headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


@app.get("/gp")
@app.get("/compare")
async def old_pages():
    """The old GP report card and comparison pages: their figures now live in the dashboard (zilla drill-down) and in AI
    mode (compare / GP questions); the old links land on the dashboard."""
    return RedirectResponse("/dashboard", status_code=307)


_NOT_FOUND = JSONResponse(status_code=404, content={"detail": "Not found."})


def _bad(*values: str | None, limit: int = 40) -> bool:
    return any(v is not None and len(v) > limit for v in values)


@app.get("/api/map")
async def map_api(fy: str | None = None):
    if _bad(fy, limit=10):
        return _NOT_FOUND
    try:
        return await insights.map_data(get_db(), fy)
    except DashboardNotFound as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.get("/api/alerts")
async def alerts_api(fy: str | None = None):
    if _bad(fy, limit=10):
        return _NOT_FOUND
    try:
        return await insights.alerts(get_db(), fy)
    except DashboardNotFound as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.get("/api/gp/search")
async def gp_search_api(q: str = ""):
    return {"results": insights.gp_search(q[:60])}


@app.get("/api/gp/{gp_id}")
async def gp_card_api(gp_id: str, fy: str | None = None):
    if _bad(gp_id, fy, limit=10):
        return _NOT_FOUND
    try:
        return await insights.gp_card(get_db(), gp_id, fy)
    except DashboardNotFound as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.get("/api/compare")
async def compare_api(a: str, b: str, fy: str | None = None):
    if _bad(a, b, fy, limit=40):
        return _NOT_FOUND
    try:
        return await insights.compare(get_db(), a, b, fy)
    except DashboardNotFound as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})


def _asked_as(req: AskRequest) -> str:
    """The whole question a follow-up stands for ("and Hassan?" after a question about Mysuru), else ""."""
    if not req.previous.strip() or len(req.previous) > 1000:     # no previous question, or not one the page keeps
        return ""
    try:
        if small_talk.kind(req.question):
            return ""
        whole = followup.resolve(small_talk.strip_abuse(req.question), small_talk.strip_abuse(req.previous))
    except Exception:  # noqa: BLE001 -- a follow-up that can't be resolved is answered as asked
        _log.exception("follow-up not resolved for %r", req.question[:200])
        return ""
    if whole:
        _log.info("follow-up %r taken as %r", req.question[:200], whole[:300])
    return whole or ""


async def _run(question: str, progress=None, mode: str = "text", asked_as: str = "") -> AskResponse:
    """`asked_as`: the whole question a follow-up stands for; it is what the pipeline answers and the voice reads back."""
    typed, question = question, asked_as or question
    try:
        await asyncio.wait_for(_SLOTS.acquire(), timeout=settings.rdpr_queue_wait_seconds)
    except asyncio.TimeoutError:
        _log.warning("busy: no free slot for %r", question[:200])
        return AskResponse(question=typed, asked_as=asked_as, answerable=False, answer=REFUSALS["busy"])
    try:
        r = await answer_question(question, get_db(), settings.rdpr_max_rows, settings.rdpr_query_timeout_seconds,
                                  progress=progress)
    except Exception:  # noqa: BLE001
        _log.exception("pipeline failed for %r", question[:200])
        return AskResponse(question=typed, asked_as=asked_as, answerable=False, answer=REFUSALS["error"])
    finally:
        _SLOTS.release()
    if r.error:
        _log.warning("answer error for %r: %s", question[:200], r.error)
    report_id = ""
    if answer_report.wants_report(r.route, r.answerable, r.columns, r.rows):
        report_id = answer_report.keep(r.question, r.answer, r.route, r.columns, r.rows, r.chart, r.entities, r.notes, get_db().version)
    said = _spoken_for_voice(r.question or question, r, report_id) if mode == "voice" else ""
    return AskResponse(
        spoken_answer=said, asked_as=asked_as,
        context=bool(r.answerable and r.route.startswith(_DATA_ROUTES) and followup.about_data(r.question)),
        question=typed, answerable=r.answerable, answer=r.answer, route=r.route if _TECH else "",
        sql=r.sql if _TECH else "", columns=r.columns, rows=[list(x) for x in r.rows], truncated=r.truncated,
        table=r.table, chart=r.chart, notes=r.notes, entities=r.entities if _TECH else {},
        timing_ms=r.timing_ms if _TECH else {}, error=r.error if _TECH else "",
        verification=(r.verification + ("; " + " | ".join(r.review_notes) if r.review_notes else "")) if _TECH else "",
        report_id=report_id)


_DATA_ROUTES = ("metric:", "report:", "verified:", "breakdown:", "llm")


def _spoken_for_voice(question: str, r, report_id: str) -> str:
    """What the voice says, under the voice guardrails (app/voice_guard.py), in this order:
      1. a refusal that may come from mishearing -> "I heard: ... Could you say it again?";
      2. a model-written answer the second check did not pass -> only "the answer is on your screen";
      3. any answer from the data -> "For <place>, <period>: " first (unless the answer already says both), then the
         spoken form, whose every figure must be a screen figure with its unit -- otherwise "the figures are on your
         screen" (never an unchecked number)."""
    try:
        again = voice_guard.ask_again(question, r.route)
        if again:
            return again
        if r.route == "llm" and not str(r.verification).startswith(("ok", "fixed")):
            return voice_guard.MODEL_UNCHECKED
        base = spoken.spoken_answer(question, r.answer, r.route, rows=len(r.rows), has_chart=bool(r.chart),
                                    has_report=bool(report_id))
        if not r.route.startswith(_DATA_ROUTES) or not r.answerable:
            return base
        base = voice_guard.add_units(base)
        if not (voice_guard.figures_match_screen(base, r.answer) and voice_guard.figures_have_units(base)):
            _log.warning("spoken figures withheld for %r: %r", question[:200], base[:200])
            base = voice_guard.FIGURES_ON_SCREEN + (" " + spoken.REPORT_NOTE if report_id else "")
        return voice_guard.readback(question, r.answer, base) + base
    except Exception:  # noqa: BLE001 -- the spoken form is best-effort; the screen answer stands
        _log.exception("spoken answer failed for %r", question[:200])
        return voice_guard.FIGURES_ON_SCREEN if r.answerable else "Sorry, I couldn't answer that. Please ask again."


@app.post("/api/ask_once", response_model=AskResponse)
async def ask_once(req: AskRequest):
    return await _run(req.question, mode=req.mode, asked_as=_asked_as(req))


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _chunks(text: str) -> list[str]:
    """Split the answer into word-sized pieces, keeping line breaks, so the page can type it out."""
    return re.findall(r"\n|[^ \n]+ ?| ", text)


@app.post("/api/ask")
async def ask_stream(req: AskRequest):
    async def events():
        stages: asyncio.Queue[str] = asyncio.Queue()
        asked_as = _asked_as(req)
        if asked_as:
            yield _sse("followup", {"asked_as": asked_as})
        task = asyncio.create_task(_run(req.question, progress=stages.put_nowait, mode=req.mode, asked_as=asked_as))
        sent = set()
        while True:
            getter = asyncio.create_task(stages.get())
            finished, _ = await asyncio.wait({task, getter}, return_when=asyncio.FIRST_COMPLETED)
            if getter in finished:
                stage = getter.result()
                if stage not in sent:
                    sent.add(stage)
                    yield _sse("status", {"stage": stage})
                continue
            getter.cancel()
            break
        while not stages.empty():
            stage = stages.get_nowait()
            if stage not in sent:
                sent.add(stage)
                yield _sse("status", {"stage": stage})
        res = task.result()
        if res.spoken_answer:
            # Voice mode: what to say goes first, so the voice can start while the text is still typing out.
            yield _sse("spoken", {"spoken_answer": res.spoken_answer, "answerable": res.answerable})
        if _TECH:
            yield _sse("sql", {"sql": res.sql, "route": res.route})
        yield _sse("status", {"stage": "answering"})
        pieces = _chunks(res.answer)
        # Paced so a short answer reads like typing and a long one still finishes in about two seconds.
        group = max(1, -(-len(pieces) // 80))
        for i in range(0, len(pieces), group):
            yield _sse("answer_chunk", {"text": "".join(pieces[i:i + group])})
            await asyncio.sleep(0.03 if group == 1 else 0.025)
        yield _sse("chart", {"chart": res.chart})
        yield _sse("table", {"table": res.table if res.answerable else None})
        yield _sse("done", {"answerable": res.answerable, "timing_ms": res.timing_ms, "truncated": res.truncated, "report_id": res.report_id,
                            "technical": _TECH, "route": res.route, "verification": res.verification if _TECH else "",
                            "spoken_answer": res.spoken_answer, "asked_as": res.asked_as,
                            "context": res.context})
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ================================================================================================ voice
# Speech in and out around the unchanged pipeline (the Meghalaya voice agent's contract, as integrated into KPCL).

# The speech-to-text prompt. Measured on the KPCL voice stress test (Indian-English voices): a comma list of names made
# the model echo the list on silence and mishear years; one plain paragraph of the places and terms (and nothing about
# how years are spoken) hears names best.
# The context names the subject and its terms, never the places: with the 31 zillas listed, qwen3-asr snapped what it
# heard to a wrong listed name (Belagavi -> "Bagalkot", Dharwad -> "Davanagere", Bengaluru Urban -> "Bangalore Rural",
# Bagepalli -> "Bagalkot"), which is the worst kind of mistake: a confident, real, wrong place. Without the list it
# writes what it hears ("Bilgavi", "Masuru jilla"), and app/spoken.py matches that against the data's own names
# (asking "Did you mean ...?" when unsure). Measured on the spoken stress test (tests/run_voice_stress.py).
ASR_CONTEXT = (
    "Spoken questions in Indian English to the Karnataka Rural Development and Panchayat Raj data assistant, about Gram "
    "Panchayats (GPs), taluks and zillas. Terms: revenue collection, demand, arrears, outstanding balance, collection "
    "percentage, property tax, mobile tower tax, book closure, scheme accounts, receipts, expenditure, Fifteenth "
    "Finance Commission, Swachh Bharat Mission, Bapuji Seva Kendra, staff registrations pending at the EO, elected "
    "members, seats, salary bills, lakh, crore, financial year.")
_PROMPT_WORDS = set(re.findall(r"[a-z]+", ASR_CONTEXT.lower()))
_ECHO_TERMS = [{"arrears"}, {"outstanding"}, {"tower"}, {"closure"}, {"receipts"}, {"expenditure"}, {"fifteenth", "commission"},
               {"swachh", "bharat"}, {"bapuji", "seva", "kendra"}, {"registrations"}, {"elected"}, {"seats"}, {"salary"}]


_PROMPT_SEQ = re.findall(r"[a-z]+", ASR_CONTEXT.lower())
_PROMPT_5GRAMS = {tuple(_PROMPT_SEQ[i:i + 5]) for i in range(len(_PROMPT_SEQ) - 4)}


def _strip_prompt_tail(text: str) -> str:
    """After a question with a long silence behind it, the model can carry on reading its own prompt: "... in FY
    2024-25? Spoken questions in Indian English to the Karnataka ...". Cut the transcript where five words in a row
    of the prompt begin and the rest (10+ words) is almost all prompt. A question may use a few prompt words in a row
    ("staff registrations pending at the EO"), but never runs on through the prompt."""
    toks = list(re.finditer(r"[A-Za-z]+", text or ""))
    low = [t.group(0).lower() for t in toks]
    for i in range(len(low) - 4):
        tail = low[i:]
        if tuple(low[i:i + 5]) in _PROMPT_5GRAMS and len(tail) >= 10 and                 sum(w in _PROMPT_WORDS for w in tail) / len(tail) >= 0.85:
            return text[:toks[i].start()].rstrip(" ,;:-")
    return text


def _is_prompt_echo(text: str) -> bool:
    """On silence or noise the model can return its prompt. A transcript made of the prompt's own words that runs
    through four or more of its distinct terms is that echo, not a question (a question names one or two)."""
    words = re.findall(r"[a-z]+", (text or "").lower())
    if len(words) < 10:
        return False
    in_prompt = sum(w in _PROMPT_WORDS for w in words) / len(words)
    return in_prompt >= 0.85 and sum(bool(g & set(words)) for g in _ECHO_TERMS) >= 4


@app.get("/api/voice/config")
async def voice_config():
    return {"speech_in": settings.asr_configured, "speech_out": settings.tts_configured,
            "stream": settings.tts_configured and settings.tts_stream_enabled,
            "speed": settings.tts_configured and settings.tts_speed_enabled,
            "sample_rate": settings.tts_stream_sample_rate}


def _rejected(kind: str, message: str, heard: str = "") -> dict:
    return {"text": "", "heard": heard, "confirm": None, "rejected": kind, "message": message}


@app.post("/api/voice/transcribe")
async def voice_transcribe(request: Request, language: str = "en", session_id: str = "default", expect: str = ""):
    """One spoken question as a WAV body -> {"text", "heard", "confirm", "rejected", "message"}.
      text      the cleaned question to ask ("" = nothing to ask)
      heard     what the speech model wrote, before clean-up
      confirm   {"prompt", "options": [{"label", "question"}]} when the clean-up was unsure: ask before answering
      rejected  "too_long" | "language" | "duplicate" | "echo" | "no_speech" | "too_short" | null, with "message" to
                say (none for duplicate / echo / no_speech / too_short: those are noise, not a question)
    expect=confirm: the panel is waiting for an answer to "Did you mean ...?", so one word ("Hassan", "yes") is fine;
    expect=bargein: words said over a reply ("stop"); the panel itself ignores fragments and the reply's own echo.
    413 over the byte cap, 503 when speech-to-text is down (the page then offers typing instead)."""
    if not re.fullmatch(r"[a-z]{2,3}", language or ""):
        language = "en"
    session = re.sub(r"[^A-Za-z0-9._:-]", "", session_id)[:64] or "default"
    audio = await request.body()
    if not audio:
        return JSONResponse(status_code=400, content={"detail": "No audio was received."})
    if len(audio) > settings.voice_max_audio_bytes:
        return JSONResponse(status_code=413, content={"detail": "That recording is too long. Please ask one question at a time."})
    secs = voice_guard.wav_seconds(audio)
    if secs is not None and secs > settings.voice_max_seconds:
        return _rejected("too_long", f"That was longer than {int(settings.voice_max_seconds)} seconds. Please ask one short question at a time.")
    voiced = voice_guard.voiced_seconds(audio)
    if voiced is not None and voiced < voice_guard.MIN_VOICED_SECONDS:
        _log.info("transcribe: %.2f s of speech in the recording; not sent to the speech model", voiced)
        return _rejected("no_speech", "")
    hint = ASR_CONTEXT if settings.asr_context_hints_enabled else None
    try:
        raw = await voice.transcribe(audio, "audio.wav", language=language, prompt=hint)
    except voice.VoiceBusy:
        return JSONResponse(status_code=503, headers={"Retry-After": "5"},
                            content={"detail": "The speech service is busy. Please try again in a moment."})
    except voice.VoiceUnavailable as exc:
        _log.warning("transcription failed: %s", exc)
        return JSONResponse(status_code=503, content={"detail": "Speech recognition is unavailable right now."})
    raw = (raw or "").strip()
    if hint:
        whole, raw = raw, _strip_prompt_tail(raw)
        if whole and not raw:
            _log.info("transcribe: dropped an echo of the ASR prompt (no speech)")
            return _rejected("echo", "")
    if hint and _is_prompt_echo(raw):
        _log.info("transcribe: dropped an echo of the ASR prompt (no speech)")
        return _rejected("echo", "")
    if not raw:
        return {"text": "", "heard": "", "confirm": None, "rejected": None, "message": ""}
    if not voice_guard.language_ok(raw):
        return _rejected("language", "I can only take questions in English. Please ask again in English.", raw)
    if len(raw) > settings.voice_max_transcript_chars:
        return _rejected("too_long", "That was a long question. Please ask one thing at a time.", raw)
    cleaned, notes = spoken.clean_transcript_ex(raw)
    if expect not in ("confirm", "bargein") and not followup.is_fragment(cleaned) and voice_guard.too_short(cleaned, voiced, _PROMPT_WORDS | {"fy", "the", "of", "in", "at"}):
        _log.info("transcribe: dropped a fragment that is not a question: %r", raw[:80])
        return _rejected("too_short", "", raw)
    if voice_guard.repeats.seen(session, cleaned):
        return _rejected("duplicate", "", raw)
    confirm = voice_guard.confirmation(cleaned, notes)
    if notes or cleaned.lower() != raw.lower():
        from app.semantic_layer import unknown_names
        voice_guard.record_mishearing({"heard": raw, "cleaned": cleaned, "notes": notes,
                                       "unknown_names": unknown_names(cleaned)})
    return {"text": cleaned, "heard": raw, "confirm": confirm, "rejected": None, "message": ""}


@app.get("/api/voice/health")
async def voice_health(refresh: bool = False):
    """Speech in / speech out reachability (checked at most every two minutes unless refresh=true)."""
    return await voice_guard.speech_health(force=refresh)


_TTS_CACHE: "OrderedDict[tuple, bytes]" = OrderedDict()
_TTS_CACHE_MAX_ITEMS, _TTS_CACHE_MAX_CHARS = 64, 160
_PCM_HEADERS = {"X-Audio-Sample-Rate": str(settings.tts_stream_sample_rate), "X-Audio-Format": "s16le; channels=1",
                "Cache-Control": "no-store", "X-Accel-Buffering": "no"}


def _cache_key(text: str, speed: float | None, streamed: bool):
    if len(text) > _TTS_CACHE_MAX_CHARS:
        return None                                # only short fixed phrases (fillers, apologies) are cached
    return (streamed, text, speed, settings.tts_model, settings.tts_task_type, settings.tts_ref_audio_path,
            settings.rdpr_voice_instructions, settings.tts_language, settings.tts_stream_sample_rate)


def _cache_put(key, audio: bytes) -> None:
    if key is None or not audio:
        return
    _TTS_CACHE[key] = audio
    _TTS_CACHE.move_to_end(key)
    while len(_TTS_CACHE) > _TTS_CACHE_MAX_ITEMS:
        _TTS_CACHE.popitem(last=False)


async def _warm_tts_cache() -> None:
    """Synthesise the filler phrases once at startup (streamed form), so the first one plays at once."""
    if not (settings.tts_configured and settings.tts_stream_enabled):
        return
    for phrase in spoken.FILLERS:
        said = spoken.pronounce(phrase)
        try:
            _cache_put(_cache_key(said, None, True), b"".join([c async for c in voice.stream_speech(said)]))
        except Exception as exc:  # noqa: BLE001 -- best effort; the first request fills it instead
            _log.info("TTS warm-up skipped: %s", exc)
            return


def _speak_input(body: dict) -> tuple[str, float | None] | JSONResponse:
    text = str(body.get("text") or "").strip()
    if not text or len(text) > 2000:
        return JSONResponse(status_code=400, content={"detail": "Nothing to say."})
    speed = body.get("speed")
    try:
        speed = None if speed in (None, "") else min(2.0, max(0.5, float(speed)))
    except (TypeError, ValueError):
        speed = None
    return text, speed


def _unavailable(said: str, detail: str, retry: bool = False) -> JSONResponse:
    return JSONResponse(status_code=503, headers={"Retry-After": "5"} if retry else None,
                        content={"detail": detail, "spoken_text": said})


@app.post("/api/voice/speak")
async def voice_speak(request: Request):
    """Text -> a whole WAV clip in the officer voice. 503 + spoken_text when it can't (the page then uses the
    browser voice with exactly that text)."""
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse(status_code=400, content={"detail": "Nothing to say."})
    parsed = _speak_input(body if isinstance(body, dict) else {})
    if isinstance(parsed, JSONResponse):
        return parsed
    text, speed = parsed
    said = spoken.pronounce(text)
    if not settings.tts_configured:
        return _unavailable(said, "Voice output is not enabled.")
    key = _cache_key(said, speed, False)
    audio = _TTS_CACHE.get(key) if key else None
    if audio is None:
        try:
            audio = await voice.speak(said, speed)
        except voice.VoiceBusy:
            return _unavailable(said, "The speech service is busy.", retry=True)
        except voice.VoiceUnavailable as exc:
            _log.warning("TTS failed: %s", exc)
            return _unavailable(said, "Voice output is unavailable right now.")
        _cache_put(key, audio)
    media = "audio/wav" if audio[:4] == b"RIFF" else "audio/mpeg" if audio[:3] == b"ID3" else "audio/wav"
    return Response(content=audio, media_type=media, headers={"Cache-Control": "no-store"})


@app.post("/api/voice/speak/stream")
async def voice_speak_stream(request: Request):
    """Text -> raw PCM as the model decodes it (first audio ~1 s). The first chunk is awaited before the 200 is
    sent, so any failure the page can still act on is a clean 503 with spoken_text. 404 when streaming is off."""
    if not settings.tts_stream_enabled:
        return JSONResponse(status_code=404, content={"detail": "Streamed voice output is off; use /api/voice/speak."})
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse(status_code=400, content={"detail": "Nothing to say."})
    parsed = _speak_input(body if isinstance(body, dict) else {})
    if isinstance(parsed, JSONResponse):
        return parsed
    text, speed = parsed
    said = spoken.pronounce(text)
    if not settings.tts_configured:
        return _unavailable(said, "Voice output is not enabled.")
    key = _cache_key(said, speed, True)
    cached = _TTS_CACHE.get(key) if key else None
    if cached is not None:
        async def cached_body():
            for i in range(0, len(cached), 16384):
                yield cached[i:i + 16384]
        return StreamingResponse(cached_body(), media_type="audio/pcm", headers=_PCM_HEADERS)
    stream = voice.stream_speech(said, speed)
    try:
        first = await stream.__anext__()
    except StopAsyncIteration:
        return _unavailable(said, "Voice output is unavailable right now.")
    except voice.VoiceBusy:
        return _unavailable(said, "The speech service is busy.", retry=True)
    except voice.VoiceUnavailable as exc:
        _log.warning("TTS stream failed before audio: %s", exc)
        return _unavailable(said, "Voice output is unavailable right now.")

    async def body_iter():
        kept = [first] if key is not None else None
        try:
            yield first
            async for chunk in stream:
                if kept is not None:
                    kept.append(chunk)
                yield chunk
            if kept is not None:
                _cache_put(key, b"".join(kept))          # only a complete clip is cached
        except voice.VoiceUnavailable as exc:
            _log.warning("TTS stream cut short: %s", exc)
        finally:
            try:
                await stream.aclose()                    # frees the gateway slot when the page stops listening
            except RuntimeError:
                pass
    return StreamingResponse(body_iter(), media_type="audio/pcm", headers=_PCM_HEADERS)


_LAST_FILLER: "OrderedDict[str, str]" = OrderedDict()


@app.get("/api/voice/filler")
async def voice_filler(session_id: str = "default"):
    """A short phrase spoken the moment a question is captured, never the same twice in a row per session."""
    sid = re.sub(r"[^A-Za-z0-9._:-]", "", session_id)[:64] or "default"
    last = _LAST_FILLER.get(sid)
    choice = next(f for f in spoken.FILLERS if f != last)
    _LAST_FILLER[sid] = choice
    _LAST_FILLER.move_to_end(sid)
    while len(_LAST_FILLER) > 5000:
        _LAST_FILLER.popitem(last=False)
    return {"filler": choice}

"""
The single request pipeline, shared by the SSE endpoint, the JSON endpoint and the evaluation scripts.
Deterministic routes run first and never call the model; only what is left reaches the one LLM call.

  L0  small talk        the whole message is a greeting / thanks / goodbye / "ok" / abuse     -> friendly fixed reply
                        (app.small_talk); abusive words in a real question are taken out before anything else
  L1  screen            empty / too long / pasted code / injection / writes / personal data   -> fixed refusal
  L2a identity          "who are you", "what can I ask"                                        -> fixed answer
  L2b verified          reviewed SQL (semantic/example_queries.sql) + deterministic writer     -> answer
  L2c glossary          "what is DCB?"                                                         -> plain definition
  L2d knowledge         "what is RDPR?", "tell me about Panchatantra" (knowledge_base.yaml)    -> answer
  L2e capability        needs data that isn't loaded (budgets, audit, MGNREGA ...)             -> honest note
  L1' screen            questions about the system, off-topic                                  -> fixed refusal
  L3  router            entities: zilla / taluk / GP, periods, schemes, metrics, intents (no LLM)
  L3b reports           broad questions (overview, needs attention, compare, situations)      -> reviewed report functions
  L3c breakdown         one measure by month / year / zilla / taluk / head / scheme ...       -> reviewed breakdown
  L4  metric lookup     one metric x one place x one period                                    -> answer from the registry
  L5  prompt            pruned schema + formulas + examples + entities
  L6  LLM               one call -> {answerable, sql, answer_template, chart}
  L7  SQL guard         read-only shape, mart-only, grain guards, NULLS LAST
  L8  execute           read-only file + authorizer + timeout + row cap; one repair round on failure
  L9  result guards     subject mismatch, impossible values, empty result
  L10 answer writer     template fill / narration, units, caveats, table, chart (no second LLM call)
  L11 review            independent second model pass with a deterministic veto
  L12 premise           a figure the question states as fact ("of the ₹500 crore collected ...") is recomputed from
                        the registry; when the data contradicts it the answer opens with the correction (app.premise)
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from app import answer as writer
from app import breakdown, capability, guardrails, knowledge, metric_lookup, premise, reports, review, small_talk, verified_queries
from app.config import settings
from app.db import ReadOnlyDB, RestrictedQueryError
from app.guardrails import REFUSALS
from app.llm import LLMUnavailable, Verdict, generate_query_plan, verify_answer
from app.prompts import build_prompt, coverage_repair_prompt, repair_prompt, verify_repair_prompt
from app.semantic_layer import (data_as_of, definitional_term, extract_entities, is_identity_question,
                                load_semantic_layer, norm, prune_semantic_layer, unknown_names)
from app.sql_safety import UnsafeSQLError, validate_readonly_sql

_log = logging.getLogger(__name__)

IDENTITY_ANSWER = (
    "**I'm the Panchayat Raj data assistant.** I answer questions about Gram Panchayat finance, revenue and staff data for "
    "Karnataka's 31 zillas, 238 taluks and 6,099 GPs from April 2022 to September 2026: book closure and scheme accounts "
    "(Finance & Accounting), demand, collection, arrears and balance by tax and property type (Revenue), and staff, EO approvals, "
    "elected members and salary bills (HRMS), by zilla, taluk, GP, financial year or month.\n\n"
    "Try: \"Which five zillas collected the most revenue in 2025-26?\", \"How many GPs closed all their books in 2024-25?\" or "
    "\"Which taluks have the most staff registrations pending at the EO?\"")


@dataclass
class PipelineResult:
    question: str
    answerable: bool = False
    answer: str = ""
    route: str = ""
    sql: str = ""
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    truncated: bool = False
    table: dict | None = None
    chart: dict | None = None
    notes: list[str] = field(default_factory=list)
    entities: dict = field(default_factory=dict)
    timing_ms: dict = field(default_factory=dict)
    error: str = ""
    verification: str = ""   # model-written answers: ok / fixed / rejected / skipped / off
    review_notes: list[str] = field(default_factory=list)


Progress = Callable[[str], None]


def _noop(_stage: str) -> None:
    return None


def _ms(t0: float) -> float:
    return round((time.monotonic() - t0) * 1000, 1)


def _finish(result: PipelineResult, answer: str, route: str, answerable: bool = True) -> PipelineResult:
    result.answer, result.route, result.answerable = answer, route, answerable
    return result


async def answer_question(question: str, db: ReadOnlyDB, max_rows: int, timeout_seconds: float,
                          progress: Progress | None = None) -> PipelineResult:
    """`progress(stage)` is called as each real stage starts (the SSE endpoint streams them to the page). Money asked
    for "in lakhs" / "in crore" / "in rupees" is converted after the answer is written, deterministically.
    `result.question` is the question as answered: abusive words taken out (app.small_talk)."""
    talk = small_talk.kind(question)
    cleaned = small_talk.strip_abuse(question) if not talk else question
    if talk or (question.strip() and not cleaned.strip()):        # only abusive words: answered as abuse
        talk = talk or "abuse"
        # abuse keeps no question text at all (nothing of it reaches a report, a log line or the voice)
        return PipelineResult(question="" if talk == "abuse" else question, answerable=True,
                              answer=small_talk.REPLIES[talk], route=f"small_talk:{talk}")
    result = await _answer_question(cleaned, db, max_rows, timeout_seconds, progress)
    if result.answerable and result.answer:
        exact = [float(v) for r in (result.rows or [])[:50] for v in r if isinstance(v, (int, float)) and not isinstance(v, bool)]
        result.answer = writer.convert_units(cleaned, result.answer, exact)
        if result.route.startswith(premise.DATA_ROUTES):
            t0 = time.monotonic()
            try:
                correction = await premise.check(cleaned, db, timeout_seconds, result.answer)
            except Exception:  # noqa: BLE001 -- the check is extra; the answer stands without it
                _log.exception("premise check failed for %r", cleaned[:200])
                correction = ""
            if correction:
                result.answer = correction + "\n\n" + result.answer
                result.notes = [correction] + result.notes
            result.timing_ms["premise_ms"] = _ms(t0)
    return result


def _glossary_answer(question: str) -> str | None:
    term = definitional_term(question)
    if term:
        return f"**{term}**: {load_semantic_layer()['glossary'][term]['plain']}"
    q = norm(question).rstrip("?. ")
    for g in knowledge.glossary_extra():
        aliases = [a.lower() for a in g["aliases"]]
        if any(q.endswith(a) and q.split(a)[0].strip() in ("what is", "what is a", "what is the", "what does", "define", "meaning of",
                                                            "who is", "who is a", "what are", "explain", "full form of") for a in aliases):
            return f"**{g['term']}**: {g['plain']}"
    return None


async def _answer_question(question: str, db: ReadOnlyDB, max_rows: int, timeout_seconds: float,
                           progress: Progress | None = None) -> PipelineResult:
    progress = progress or _noop
    progress("understanding")
    result = PipelineResult(question=question)
    t0 = time.monotonic()
    timing = result.timing_ms

    screened = guardrails.screen_question(question)
    if screened in ("empty", "too_long", "code", "injection", "harmful", "read_only", "personal_data"):
        timing["router_ms"] = _ms(t0)
        return _finish(result, REFUSALS[screened], f"refused:{screened}", False)

    if guardrails.office_holder_question(question):
        timing["router_ms"] = _ms(t0)
        return _finish(result, REFUSALS["off_topic"], "refused:off_topic", False)

    if is_identity_question(question) or knowledge_is_help(question):
        timing["router_ms"] = _ms(t0)
        return _finish(result, IDENTITY_ANSWER, "identity")

    vq = verified_queries.match(question)
    if vq is not None:
        progress("querying")
        try:
            qr = await db.run(vq.sql, max_rows=max_rows, timeout_seconds=timeout_seconds)
            timing["db_ms"] = _ms(t0)
            result.sql, result.columns, result.rows, result.truncated = vq.sql, qr.columns, qr.rows, qr.truncated
            result.table = writer.result_table(qr.columns, qr.rows)
            if vq.chart:
                result.chart = writer.build_chart(*vq.chart, qr.columns, qr.rows)
            result.entities = {"verified_query": vq.key}
            text = writer.present(writer.fill_template("", qr.columns, qr.rows, {}))
            result.notes = writer.caveats(vq.sql, qr.columns, qr.rows, extract_entities(question))
            if result.notes:
                text += "\n\n" + " ".join(result.notes)
            timing["fill_ms"] = _ms(t0)
            return _finish(result, text, f"verified:{vq.key}")
        except Exception:  # noqa: BLE001 -- a verified query should never fail; fall through to the model
            _log.exception("verified query %s failed", vq.key)
            result = PipelineResult(question=question)
            timing = result.timing_ms

    if screened != "system" and knowledge.is_pure_definition(question):
        kb = knowledge.primary(question)
        if kb:
            timing["router_ms"] = _ms(t0)
            return _finish(result, kb, "knowledge")

    gloss = _glossary_answer(question)
    if gloss:
        timing["router_ms"] = _ms(t0)
        return _finish(result, gloss, "glossary")

    note = capability.check(question)
    if note:
        timing["router_ms"] = _ms(t0)
        return _finish(result, note, "capability", False)
    kb = knowledge.primary(question) if screened != "system" else None
    if kb:
        timing["router_ms"] = _ms(t0)
        return _finish(result, kb, "knowledge")

    if screened is not None:
        timing["router_ms"] = _ms(t0)
        return _finish(result, REFUSALS[screened], f"refused:{screened}", False)

    entities = extract_entities(question)
    result.entities = entities
    unknown = unknown_names(question)
    if unknown:
        timing["router_ms"] = _ms(t0)
        return _finish(result, f"**I don't recognise {' or '.join(repr(u) for u in unknown)} as a zilla, taluk or GP in this "
                               "data.** Please check the spelling; the 31 zillas include, for example, Bagalkot, Belagavi, Mysuru "
                               "and Tumakuru, and you can write a GP as \"<name> GP in <taluk> taluk\".", "unknown_name", False)
    out_of_range = [p for p in entities.get("periods", []) if p["kind"] == "out_of_range"]
    if out_of_range and len(out_of_range) == len(entities.get("periods", [])):
        timing["router_ms"] = _ms(t0)
        return _finish(result, f"**The data covers April 2022 to {writer.pretty_label(data_as_of())} only, so there is no "
                               f"figure for {out_of_range[0]['label']}.** Financial years 2022-23 to 2026-27 (April-September 2026 "
                               "for the last) are available.", "out_of_range", False)
    timing["router_ms"] = _ms(t0)

    t1 = time.monotonic()
    progress("querying")
    try:
        rep = await reports.report(question, entities, db, timeout_seconds)
    except Exception:  # noqa: BLE001 -- a reviewed report should never fail; fall through to the model
        _log.exception("report failed for %r", question[:200])
        rep = None
    if rep is not None:
        timing["db_ms"] = _ms(t1)
        result.sql, result.columns, result.rows = rep.sql, rep.columns, rep.rows
        result.table, result.chart = rep.table, rep.chart
        result.notes = rep.notes + writer.caveats(rep.sql, rep.columns, rep.rows, entities)
        text = rep.answer + (("\n\n" + " ".join(result.notes)) if result.notes else "")
        return _finish(result, text, f"report:{rep.key}")

    t1 = time.monotonic()
    try:
        bd = await breakdown.breakdown(question, entities, db, timeout_seconds)
    except Exception:  # noqa: BLE001 -- a reviewed breakdown should never fail; fall through
        _log.exception("breakdown failed for %r", question[:200])
        bd = None
    if bd is not None:
        timing["db_ms"] = _ms(t1)
        result.sql, result.columns, result.rows = bd.sql, bd.columns, bd.rows
        result.table, result.chart = bd.table, bd.chart
        result.notes = bd.notes + writer.caveats(bd.sql, bd.columns, bd.rows, entities)
        text = bd.answer + (("\n\n" + " ".join(result.notes)) if result.notes else "")
        return _finish(result, text, f"breakdown:{bd.key}")

    t1 = time.monotonic()
    try:
        ma = await metric_lookup.answer(entities, db, timeout_seconds, question)
    except Exception:  # noqa: BLE001
        _log.exception("metric lookup failed for %r", question[:200])
        ma = None
    if ma is not None:
        timing["db_ms"] = _ms(t1)
        result.sql, result.columns, result.rows = ma.sql, ma.columns, ma.rows
        result.notes = writer.caveats(ma.sql, ma.columns, ma.rows, entities) if ma.final else []
        text = ma.answer + (("\n\n" + " ".join(result.notes)) if result.notes else "")
        return _finish(result, text, f"metric:{ma.metric}", ma.final)

    return await _llm_path(result, question, entities, db, max_rows, timeout_seconds, progress)


def knowledge_is_help(question: str) -> bool:
    return norm(question).rstrip("?. ") in ("help", "what can i ask", "what can you answer", "what questions can i ask",
                                            "sample questions", "example questions")


async def _llm_path(result: PipelineResult, question: str, entities: dict, db: ReadOnlyDB, max_rows: int,
                    timeout_seconds: float, progress: Progress = _noop) -> PipelineResult:
    timing = result.timing_ms
    progress("writing_sql")
    t0 = time.monotonic()
    pruned = prune_semantic_layer(question, entities)
    prompt = build_prompt(question, pruned, entities)
    timing["prompt_ms"] = _ms(t0)
    timing["prompt_tokens_est"] = len(prompt) // 4

    t0 = time.monotonic()
    try:
        try:
            plan = await generate_query_plan(prompt)
        except (ValueError, KeyError) as exc:  # cut off or malformed JSON: retry once, telling the model what went wrong
            _log.warning("unusable plan (%s); retrying once", exc)
            plan = await generate_query_plan(prompt, retry=True)
    except LLMUnavailable:
        timing["llm_ms"] = _ms(t0)
        kb = knowledge.fallback(question)
        return _finish(result, kb, "knowledge_fallback") if kb else _finish(result, REFUSALS["llm_unavailable"], "llm_unavailable", False)
    except Exception as exc:  # noqa: BLE001
        timing["llm_ms"] = _ms(t0)
        _log.exception("LLM call failed for %r", question[:200])
        result.error = f"LLM call failed: {exc}"
        kb = knowledge.fallback(question)
        return _finish(result, kb, "knowledge_fallback") if kb else _finish(result, REFUSALS["llm_unavailable"], "llm_error", False)
    timing["llm_ms"] = _ms(t0)

    if not plan.answerable and guardrails.false_coverage_claim(plan.clarification_message, entities):
        _log.warning("false coverage claim for %r: %s", question[:200], plan.clarification_message[:200])
        t0 = time.monotonic()
        try:
            plan = await generate_query_plan(coverage_repair_prompt(prompt, plan.clarification_message))
        except Exception as exc:  # noqa: BLE001
            result.error = f"coverage repair failed: {exc}"
        timing["coverage_repair_ms"] = _ms(t0)
    if not plan.answerable:
        if guardrails.false_coverage_claim(plan.clarification_message, entities):
            return _finish(result, REFUSALS["not_in_data"], "llm_declined:coverage", False)
        kb = knowledge.fallback(question)
        if kb:
            return _finish(result, kb, "knowledge_fallback")
        return _finish(result, guardrails.safe_refusal(plan.clarification_message), "llm_declined", False)

    first = await _execute_plan(result, question, entities, db, max_rows, timeout_seconds, progress, prompt, plan)
    if isinstance(first, PipelineResult):
        return first
    if not settings.rdpr_verify_answers:
        result.verification = "off"
        return _finish(result, first, "llm")

    verdict = await _review(result, question, entities, first, progress)
    if verdict is None or verdict.ok:
        result.verification = "ok" if verdict else "skipped"
        return _finish(result, first, "llm")

    _log.warning("reviewer rejected the answer to %r: %s", question[:200], verdict.problem)
    result.error = f"reviewer: {verdict.problem}"
    t0 = time.monotonic()
    progress("repairing")
    try:
        plan = await generate_query_plan(verify_repair_prompt(prompt, result.sql, verdict.problem))
    except Exception as exc:  # noqa: BLE001
        _log.warning("repair after review failed for %r: %s", question[:200], exc)
        return _unverified(result)
    result.timing_ms["review_repair_llm_ms"] = _ms(t0)
    if not plan.answerable:
        return _unverified(result)
    second = await _execute_plan(result, question, entities, db, max_rows, timeout_seconds, progress, prompt, plan)
    if isinstance(second, PipelineResult):
        return _unverified(result)
    verdict2 = await _review(result, question, entities, second, progress, attempt=2)
    if verdict2 is not None and not verdict2.ok:
        _log.warning("reviewer rejected the repaired answer to %r: %s", question[:200], verdict2.problem)
        result.error = f"reviewer (after repair): {verdict2.problem}"
        return _unverified(result)
    result.verification = "fixed" if verdict2 else "fixed:second review skipped"
    return _finish(result, second, "llm")


async def _review(result: PipelineResult, question: str, entities: dict, text: str, progress: Progress,
                  attempt: int = 1) -> Verdict | None:
    """The reviewer's verdict, or None if the reviewer could not be reached or replied unusably (fail open: the
    answer has already passed every deterministic guard; the event is logged)."""
    progress("verifying")
    t0 = time.monotonic()
    try:
        verdict, note = await review.review_answer(question, entities, result.sql, result.columns, result.rows, text,
                                                   call=verify_answer)
    except Exception as exc:  # noqa: BLE001
        _log.warning("reviewer unavailable for %r: %s", question[:200], exc)
        return None
    finally:
        result.timing_ms[f"review_ms_{attempt}"] = _ms(t0)
    if note:
        _log.warning("review of %r: %s", question[:200], note)
        result.review_notes.append(note)
    return verdict


def _unverified(result: PipelineResult) -> PipelineResult:
    """Nothing the reviewer doubted is shown: no figure, table or chart."""
    result.verification = "rejected"
    result.columns, result.rows, result.table, result.chart, result.notes = [], [], None, None, []
    return _finish(result, REFUSALS["unverified"], "llm_unverified", False)


async def _execute_plan(result: PipelineResult, question: str, entities: dict, db: ReadOnlyDB, max_rows: int,
                        timeout_seconds: float, progress: Progress, prompt: str, plan) -> str | PipelineResult:
    """Guard, run and write up one plan (with one repair round on a guard or SQL failure). Returns the answer text,
    or a finished refusal."""
    timing = result.timing_ms
    sql, template, chart = plan.sql, plan.answer_template, plan.chart_data
    qr, last_error, blocked = None, "", False
    for attempt in range(2):  # first try + one repair round fed the exact error
        t0 = time.monotonic()
        progress("checking_sql")
        try:
            safe_sql = validate_readonly_sql(sql, entities)
            timing[f"guard_ms_{attempt}"] = _ms(t0)
            result.sql = safe_sql
            t0 = time.monotonic()
            progress("running_query")
            qr = await db.run(safe_sql, max_rows=max_rows, timeout_seconds=timeout_seconds, restricted=True)
            timing[f"db_ms_{attempt}"] = _ms(t0)
            bad = guardrails.implausible_result(qr.columns, qr.rows) or \
                guardrails.count_exceeds_scope(question, entities, qr.columns, qr.rows)
            if bad:
                qr = None
                raise UnsafeSQLError(f"the result is impossible: {bad}; check the formula (ratios are SUM/SUM x 100)")
            break
        except UnsafeSQLError as exc:
            last_error, blocked = f"Rejected by the SQL guard: {exc}", False
        except RestrictedQueryError as exc:
            last_error, blocked = f"Access denied: {exc}. Read only the mart_* views listed in the schema.", True
        except Exception as exc:  # noqa: BLE001 -- SQL error or timeout
            last_error, blocked = str(exc), False
        timing[f"db_ms_{attempt}"] = _ms(t0)
        if attempt == 0:
            t0 = time.monotonic()
            progress("repairing")
            try:
                plan = await generate_query_plan(repair_prompt(prompt, sql, last_error))
            except Exception as exc:  # noqa: BLE001
                timing["repair_llm_ms"] = _ms(t0)
                last_error = f"repair call failed: {exc}"
                break
            timing["repair_llm_ms"] = _ms(t0)
            if not plan.answerable:
                return _finish(result, guardrails.safe_refusal(plan.clarification_message), "llm_declined", False)
            sql, template, chart = plan.sql, plan.answer_template, plan.chart_data

    if qr is None:
        _log.warning("query failed for %r: %s", question[:200], last_error)
        result.error = last_error
        return _finish(result, REFUSALS["not_in_data"], "llm_sql_failed" + (":blocked" if blocked else ""), False)

    if guardrails.subject_mismatch(question, result.sql):
        _log.warning("subject mismatch for %r; SQL %s", question[:200], result.sql)
        return _finish(result, REFUSALS["mismatch"], "llm_mismatch", False)

    t0 = time.monotonic()
    progress("writing_answer")
    result.columns, result.rows, result.truncated = qr.columns, qr.rows, qr.truncated
    result.table = writer.result_table(qr.columns, qr.rows)
    result.chart = None
    if chart:
        result.chart = writer.build_chart(chart.type, chart.label_column, chart.value_column, chart.series_label,
                                          qr.columns, qr.rows)
    text = writer.fill_template(template, qr.columns, qr.rows, entities, preferred=chart.value_column if chart else None)
    text = writer.present(text)
    together = writer.combined_total(question, qr.columns, qr.rows)
    if together:
        text += "\n\n" + together
    result.notes = writer.caveats(result.sql, qr.columns, qr.rows, entities)
    if qr.truncated:
        result.notes.append(f"Only the first {max_rows} rows are shown.")
    if result.notes:
        text += "\n\n" + " ".join(result.notes)
    timing["fill_ms"] = _ms(t0)
    return text

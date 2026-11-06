"""
Second model pass: an independent reviewer checks every model-written answer before it is shown.

The reviewer is the same gateway model, and in live testing a free-form reviewer invents objections. So:

  1. It is given the documentation of the columns the SQL uses, the data rules, the question, the recognised
     entities, the SQL, the result rows and the answer text.
  2. It must name ONE error category: wrong_measure, wrong_scope, wrong_period, wrong_aggregation or
     unsupported_claim. Anything else (style, rounding, wording) counts as ok.
  3. Deterministic veto: a rejection is overruled when the code can prove the claim false --
       wrong_scope      the SQL filters on every zilla / taluk / GP / scheme / revenue head / staff type named;
       wrong_period     the SQL filters on every period named in the question;
       wrong_measure    the SQL uses every column of the registry formula of the measure named in the question;
       wrong_aggregation the result has the shape the question asks for;
       unsupported_claim every figure in the answer comes from the result rows (or a column total).
A rejection that survives the veto gets one repair round in app.pipeline; an answer rejected again is not shown.
"""
from __future__ import annotations

import json
import re

from app import llm
from app.llm import Verdict
from app.prompts import VERIFY_RULES
from app.semantic_layer import load_semantic_layer

CATEGORIES = ("wrong_measure", "wrong_scope", "wrong_period", "wrong_aggregation", "unsupported_claim")
_NUM_RE = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")
_DATE_LIKE_RE = re.compile(r"\b\d{1,2}-[A-Za-z]{3}-\d{4}\b|\b(19|20)\d{2}-\d{2}(-\d{2})?\b|\bFY ?\d{4}-\d{2}\b|\bQ[1-4]\b|"
                           r"\b[A-Za-z]{3}-\d{4}\b|\b(19|20)\d{2}\b")
_RUPEE_RE = re.compile(r"₹\s*(-?\d[\d,]*(?:\.\d+)?)\s*(crore|lakh)?", re.I)


# ---------------------------------------------------------------------------------------------- prompt
def _column_docs(sql: str) -> str:
    """Docs of the mart columns the SQL actually uses, so the reviewer does not guess what a column means."""
    tables = load_semantic_layer()["tables"]
    used_tables = set(re.findall(r"\bmart_\w+", sql or ""))
    words = set(re.findall(r"\b[a-z_][a-z0-9_]*\b", (sql or "").lower()))
    lines = []
    for t in sorted(used_tables):
        info = tables.get(t)
        if not info:
            continue
        lines.append(f"{t} -- {info['grain']}")
        for c, ci in info["columns"].items():
            if c in words:
                unit = f" [{ci['unit']}]" if ci.get("unit") else ""
                lines.append(f"  {c}{unit}: {(ci.get('doc') or '')[:160]}")
    return "\n".join(lines)


def build_prompt(question: str, entities: dict, sql: str, columns: list[str], rows: list[tuple], answer: str) -> str:
    shown = rows[:25]
    table = "\n".join([" | ".join(columns)] + [" | ".join("" if v is None else str(v) for v in r) for r in shown])
    more = f"\n({len(rows) - len(shown)} more rows not shown)" if len(rows) > len(shown) else ""
    return (
        "You review an answer written by another assistant over the Karnataka Panchayat Raj (RDPR) database before a "
        "government official sees it. The SQL author knows the schema below; do not second-guess a view or column that the "
        "documentation shows is right. The answer text is written automatically from the result rows.\n\n"
        + VERIFY_RULES + "\n\n## Columns used by the SQL\n" + _column_docs(sql) + "\n\n"
        "Reject ONLY for one of these clear errors:\n"
        "- wrong_measure: the SQL measures a different thing than the question asks;\n"
        "- wrong_scope: the SQL is for a different zilla / taluk / GP / scheme / revenue head than asked, or leaves part out;\n"
        "- wrong_period: the SQL is for a different financial year or month than asked;\n"
        "- wrong_aggregation: e.g. one row per month when a single total for the period was asked, or a sum of a balance "
        "across years;\n"
        "- unsupported_claim: a figure or claim in the answer text is not in the result rows.\n"
        "Wording, rounding, ordering, lakh / crore formatting, extra detail, style or a missing chart are NEVER errors. "
        "If unsure, the answer is ok.\n\n"
        f"## Question\n{question}\n\n## Entities identified in the question\n{json.dumps(entities, ensure_ascii=False)}\n\n"
        f"## SQL\n{sql}\n\n## Result ({len(rows)} rows)\n{table}{more}\n\n## Answer text\n{answer}\n\n"
        'Reply with ONE JSON object only: {"ok": true, "category": "none", "problem": ""} or '
        '{"ok": false, "category": "<one of: ' + ", ".join(CATEGORIES) + '>", "problem": "<one sentence>"}'
    )


# ---------------------------------------------------------------------------------------------- deterministic facts
def _quoted(sql: str) -> set[str]:
    return {m.upper() for m in re.findall(r"'([^']*)'", sql or "")}


def scope_verified(entities: dict, sql: str) -> bool | None:
    names = [*entities.get("zillas", []), *entities.get("taluks", []), *[g["name"] for g in entities.get("gps", []) if g.get("name")],
             *entities.get("schemes", []), *entities.get("fee_types", []), *entities.get("staff_types", []),
             *entities.get("designations", [])]
    if not names:
        return None
    q = _quoted(sql)
    return all(n.upper() in q for n in names)


def period_verified(entities: dict, sql: str) -> bool | None:
    periods = [p for p in entities.get("periods", []) if p["kind"] != "out_of_range"]
    if not periods:
        return None
    q = _quoted(sql)
    low = (sql or "").lower()
    for p in periods:
        k, v = p["kind"], str(p["value"]).upper()
        if k in ("fy", "month", "date") and v not in q:
            if k == "month" and re.search(r"month_id\s*(=|in|between)\s*\(?\s*" + _month_id(v), low):
                continue
            return False
        if k == "calendar_year" and not (f"'{v}'" in low or v in low):
            return False
    return True


def _month_id(label: str) -> str:
    mon, year = label.split("-")
    mm = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"].index(mon) + 1
    return f"{year}{mm:02d}"


def measure_verified(entities: dict, sql: str) -> bool | None:
    keys = entities.get("metrics", [])
    if not keys:
        return None
    metrics = {m["key"]: m for m in load_semantic_layer()["metrics"]}
    low = (sql or "").lower()
    for k in keys:
        m = metrics.get(k)
        if not m:
            return None
        forms = []
        for group in (m["variants"], m.get("with_fee_type", {}), m.get("with_property_type", {})):
            for v in group.values():
                cols = set(re.findall(r"\b[a-z]+_[a-z0-9_]+\b", v["expr"].lower())) - {"nullif"}
                if cols:
                    forms.append(cols)
        if not any(all(re.search(r"\b" + c + r"\b", low) for c in cols) for cols in forms):
            return False
    return True


def _to_rupees(m: re.Match) -> float:
    return float(m.group(1).replace(",", "")) * {"crore": 1e7, "lakh": 1e5}.get((m.group(2) or "").lower(), 1.0)


def claims_supported(answer: str, question: str, columns: list[str], rows: list[tuple]) -> bool:
    """Every figure in the answer is a result value, a column total, or a number already in the question."""
    values = [float(v) for r in rows for v in r if isinstance(v, (int, float)) and not isinstance(v, bool)]
    totals = [sum(float(r[i]) for r in rows if isinstance(r[i], (int, float)) and not isinstance(r[i], bool))
              for i in range(len(columns))]
    known = values + totals + [float(x.replace(",", "")) for x in _NUM_RE.findall(_DATE_LIKE_RE.sub(" ", question or ""))
                               if x.replace(",", "").replace(".", "").lstrip("-").isdigit()]
    text = answer or ""
    for m in _RUPEE_RE.finditer(text):                      # rupee figures: compare in rupees, whatever lakh / crore wrote them
        rupees = _to_rupees(m)
        tol = max(abs(rupees) * 0.002, 0.006) if m.group(2) is None else max(abs(rupees) * 0.0006, 0.6)
        if not any(abs(rupees - k) <= tol for k in known):
            return False
    text = _RUPEE_RE.sub(" ", text)
    for tok in _NUM_RE.findall(_DATE_LIKE_RE.sub(" ", text)):
        try:
            x = float(tok.replace(",", ""))
        except ValueError:
            continue
        if abs(x) < 10 and float(x).is_integer():
            continue                       # small counts in prose ("3 taluks") are not figures to trace
        if not any(abs(x - k) <= max(abs(k) * 0.002, 0.006) for k in known):
            return False
    return True


def shape_matches(entities: dict, rows: list[tuple]) -> bool:
    """One row for a single-figure question; several rows for a comparison, list, ranking, breakdown or trend."""
    many_asked = bool(set(entities.get("intents", [])) & {"ranking", "comparison", "breakdown", "trend"}) or \
        len([p for p in entities.get("periods", []) if p["kind"] != "out_of_range"]) > 1 or \
        len(entities.get("zillas", [])) + len(entities.get("taluks", [])) > 1
    return len(rows) > 1 if many_asked else len(rows) == 1


def veto(verdict: Verdict, category: str, question: str, entities: dict, sql: str, columns: list[str],
         rows: list[tuple], answer: str) -> str | None:
    """Why a rejection is provably wrong, or None if it stands."""
    if category not in CATEGORIES:
        return "not one of the error categories"
    if category == "wrong_scope" and scope_verified(entities, sql):
        return "the SQL filters on every zilla / taluk / GP / scheme / revenue head / staff type named in the question"
    if category == "wrong_period" and (not entities.get("periods") or period_verified(entities, sql)):
        return ("the question names no period" if not entities.get("periods")
                else "the SQL filters on every period named in the question")
    if category == "wrong_measure" and measure_verified(entities, sql):
        return "the SQL uses the registry formula of the measure named in the question"
    if category == "wrong_aggregation" and shape_matches(entities, rows):
        return "the result has the shape the question asks for (one figure, or one row per item compared or listed)"
    if category == "unsupported_claim" and (len(rows) > 1 or claims_supported(answer, question, columns, rows)):
        return ("a multi-row answer is written from the rows by the deterministic narrator, not by the model"
                if len(rows) > 1 else "every figure in the answer comes from the result row")
    return None


async def review_answer(question: str, entities: dict, sql: str, columns: list[str], rows: list[tuple],
                        answer: str, call=None) -> tuple[Verdict, str]:
    """(verdict after the veto, note). Raises if the reviewer cannot be reached (the caller fails open)."""
    raw = await (call or llm.verify_answer)(build_prompt(question, entities, sql, columns, rows, answer))
    if raw.ok:
        return raw, ""
    category = (raw.category or "").strip().lower()
    reason = veto(raw, category, question, entities, sql, columns, rows, answer)
    if reason:
        return Verdict(True, ""), f"reviewer overruled ({category}: {raw.problem[:160]}) because {reason}"
    return raw, f"{category}: {raw.problem}"

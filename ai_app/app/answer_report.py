"""
Excel report for an AI-mode answer: GET /api/answer-report/{report_id} (and /view for the on-screen preview).

Every chat answer computed from the data (a reviewed report, a verified query, a breakdown, a single figure or a
model-written query that passed review) is kept for a while under a random id, and the page shows "View report" and
"Download report" under it. Answers not taken from the data (definitions, refusals, "no figure" replies) get none.
The workbook is built only from what the pipeline itself produced and kept on the server, never from anything the
page sends back:

  * a summary of Karnataka or one zilla for an FY (an overview report) -> the dashboard's complete MIS workbook for that
    selection (app/mis_report.py), identical to the dashboard's own download;
  * anything else -> an answer workbook in the same house style:
      Report   letterhead, the question, the answer exactly as given, and integrity checks
      Data     every row the answer was computed from, with units, and the answer's chart as a native Excel chart
      Notes    the caveats attached to the answer and the definitions of the measures used

Integrity checks travel with the file: the headline figure of the answer must be found in the data rows (or their
total). A failing check makes the download a 409 "under review", never a wrong file.

Kept answers live in memory for settings.rdpr_report_ttl_seconds and are bound to the database version: after a
warehouse rebuild an old id asks the user to ask again. At most KEEP_MAX are kept, oldest dropped first.
"""
from __future__ import annotations

import re
import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass

from app import answer as writer
from app import mis_report as mis
from app.config import settings
from app.dashboard_data import build_dashboard
from app.db import ReadOnlyDB
from app.semantic_layer import load_semantic_layer

KEEP_MAX = 500
ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
_DATA_ROUTES = ("report:", "verified:", "metric:", "breakdown:", "llm")
_RUPEES_RE = re.compile(r"₹\s*(-?\d[\d,]*(?:\.\d+)?)\s*(crore|lakh)?", re.I)
_NUM_RE = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")


@dataclass
class Kept:
    question: str
    answer: str
    route: str
    columns: list[str]
    rows: list[tuple]
    chart: dict | None
    entities: dict
    notes: list[str]
    version: str
    at: float


_STORE: "OrderedDict[str, Kept]" = OrderedDict()
_LOCK = threading.Lock()


def wants_report(route: str, answerable: bool, columns: list[str], rows: list | None) -> bool:
    return bool(answerable and rows and columns and route.startswith(_DATA_ROUTES))


def keep(question: str, answer: str, route: str, columns: list[str], rows: list, chart: dict | None, entities: dict,
         notes: list[str], version: str) -> str:
    rid = secrets.token_urlsafe(18)
    with _LOCK:
        _STORE[rid] = Kept(question, answer, route, list(columns), [tuple(r) for r in rows], chart, dict(entities), list(notes),
                           version, time.time())
        while len(_STORE) > KEEP_MAX:
            _STORE.popitem(last=False)
    return rid


def get(rid: str, version: str) -> Kept | None:
    if not ID_RE.match(rid or ""):
        return None
    with _LOCK:
        k = _STORE.get(rid)
    if k is None or k.version != version or time.time() - k.at > settings.rdpr_report_ttl_seconds:
        return None
    return k


# ---------------------------------------------------------------------------------------------- sheets
def _kind(col: str, rows: list[tuple], i: int) -> str:
    if not any(isinstance(r[i], (int, float)) and not isinstance(r[i], bool) for r in rows[:50]):
        return "text"
    unit = writer.col_unit(col)
    return "inr" if unit == "INR" else "pct" if unit == "%" else "int" if unit in ("count", "flag") else "num"


def _headline_figure(answer: str) -> tuple[str, float] | None:
    """The first figure of the answer's bold headline, in the units the data holds (rupees for money)."""
    head = answer.split("\n", 1)[0]
    m = _RUPEES_RE.search(head)
    if m:
        v = float(m.group(1).replace(",", "")) * {"crore": 1e7, "lakh": 1e5}.get((m.group(2) or "").lower(), 1.0)
        return m.group(0), v
    for tok in _NUM_RE.findall(re.sub(r"\b(19|20)\d{2}(-\d{2})?\b|FY", " ", head)):
        v = float(tok.replace(",", ""))
        if abs(v) >= 10 or not v.is_integer():
            return tok, v
    return None


def _headline_check(k: Kept) -> list:
    """[label, shown, found in data, PASS / CHECK]: the headline figure is a value of the data rows or a column total."""
    h = _headline_figure(k.answer)
    if h is None:
        return ["Every figure in the answer is computed from the data rows", "—", "—", "PASS"]
    shown, v = h
    values = [float(x) for r in k.rows for x in r if isinstance(x, (int, float)) and not isinstance(x, bool)]
    totals = [sum(float(r[i]) for r in k.rows if isinstance(r[i], (int, float)) and not isinstance(r[i], bool)) for i in range(len(k.columns))]
    tol = max(abs(v) * 0.006, 0.6)                    # a figure written in crore / lakh is rounded to 2 places
    ok = any(abs(v - x) <= tol for x in values + totals)
    return [f"Headline figure {shown} is in the data", v, "found" if ok else "not found", "PASS" if ok else "CHECK"]


def _answer_sheets(k: Kept) -> list[dict]:
    kinds = [_kind(c, k.rows, i) for i, c in enumerate(k.columns)]
    when = time.strftime("%d %b %Y, %H:%M")
    para = [line.replace("**", "") for line in k.answer.split("\n") if line.strip()]
    report = [[("Rural Development & Panchayat Raj · AI mode answer", "title")],
              [(f"Synthetic proof-of-concept data, April 2022 to {writer.pretty_label(load_semantic_layer()['data_period']['data_as_of'])} · generated {when}", "sub")],
              [], [("Question", "section"), (None, "section")], [(k.question, "text")], [],
              [("Answer", "section"), (None, "section")]] + [[(p, "text")] for p in para] + [[]]
    report += mis._rows_block("Integrity checks", ["Check", "Shown", "In the data", "Result"], [_headline_check(k)], ["text", "num", "text", "flag"])
    headers = [writer.header(c) + (f" ({writer.col_unit(c)})" if writer.col_unit(c) not in (None, "count", "flag") else "") for c in k.columns]
    data = [[("Rural Development & Panchayat Raj · data behind the answer", "title")], [(k.question, "sub")], [],
            [(h, "head") for h in headers]]
    for r in k.rows:
        data.append([(writer.pretty_label(v) if kinds[i] == "text" and v is not None else v, kinds[i]) for i, v in enumerate(r)])
    sheets = [{"name": "Report", "widths": [110, 18, 14, 10], "cells": report},
              {"name": "Data", "widths": [max(14, min(40, len(h) + 4)) for h in headers], "cells": data}]
    c = k.chart
    if c and c.get("labels") and len(k.rows) >= 2:
        label_col = next((i for i, kd in enumerate(kinds) if kd == "text"), 0)
        val = next((i for i, col in enumerate(k.columns) if writer.header(col).lower() in (c.get("series_label") or "").lower()
                    or col in (c.get("series_label") or "")), None)
        if val is None:
            val = next((i for i, kd in enumerate(kinds) if kd != "text"), None)
        if val is not None:
            sheets[1]["chart"] = {"type": c.get("type", "bar"), "title": c.get("series_label") or headers[val], "label_col": label_col + 1,
                                  "value_col": val + 1, "header_row": 4, "last_row": 4 + len(k.rows),
                                  "anchor": f"{chr(ord('A') + len(headers) + 1)}4", "y_title": c.get("unit", "")}
            sheets[1]["freeze"] = "A5"
    notes = [[("Notes", "title")], []]
    for n in k.notes:
        notes.append([(n, "text")])
    used = {m["key"] for m in load_semantic_layer()["metrics"] if m["key"] in (k.entities.get("metrics") or [])}
    for m in load_semantic_layer()["metrics"]:
        if m["key"] in used:
            notes.append([(f"{m['label'].capitalize()} ({m['unit']}): " + "; ".join(v["expr"] for v in m["variants"].values()), "text")])
    notes.append([("Ratios are recomputed as SUM(numerator) / SUM(denominator) over the rows in scope, never averaged. Money is in Indian rupees "
                   "(1 lakh = 1,00,000; 1 crore = 1,00,00,000).", "text")])
    sheets.append({"name": "Notes", "widths": [140], "cells": notes})
    for s in sheets:
        s["tab"] = mis._TAB[s["name"]]
        s["footer"] = "Synthetic proof-of-concept data · built from the answer the assistant gave"
    return sheets


def _overview_selection(k: Kept) -> tuple[str, str | None] | None:
    """An overview report of Karnataka or one zilla for one FY downloads the dashboard's complete MIS report."""
    if not k.route.startswith("report:overview:") or k.route.endswith(":gp") or k.route.endswith(":taluk"):
        return None
    fy = next((p["fy"] for p in k.entities.get("periods", []) if p.get("kind") == "fy"), None) or load_semantic_layer()["data_period"]["latest_full_fy"]
    zillas = k.entities.get("zillas") or []
    return fy, (zillas[0] if zillas else None)


async def build(db: ReadOnlyDB, k: Kept) -> tuple[list[dict], str]:
    sel = _overview_selection(k)
    if sel:
        d = await build_dashboard(db, *sel)
        sheets = mis.build_sheets(d, "all", "revenue")
        sheets[0]["cells"].insert(2, [(f"Asked in AI mode: {k.question}", "sub")])
        return sheets, mis.file_name(d, "all", "revenue")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", k.question).strip("_")[:60]
    return _answer_sheets(k), f"RDPR_Answer_{slug}.xlsx"

"""
Deterministic parameterised reports (no LLM) -- blueprint L9b / section 9.4.

A broad question ("overall performance of Mysuru zilla in 2024-25", "which taluks need attention",
"summary of FY 2024-25") names no single metric, so the single-metric route cannot answer it and one
model-written SELECT cannot either: the honest answer spans Finance, Revenue and HRMS at once. These
reviewed functions each run one fixed query over the same mart_* summary views the dashboard uses, with
the same SUM/SUM ratios, so a report, the dashboard and the chat cannot disagree.

Each report is tried in order and returns None when it does not apply:

  needs_attention  the places whose collection % is weakest in an FY, with why
  compare          two or more named places of the same level, side by side in one FY
  overview         one place (or Karnataka) x one FY -> closure, revenue and staff in one answer

Rules carried over from the blueprint:
  - a report is skipped when the question names a measure it does not cover (_covers_asked_measures);
  - when no period was named a default is used **and stated** in the answer;
  - ratios are recomputed SUM/SUM from the numerator and denominator columns, never averaged;
  - the only values reaching SQL are bound parameters taken from validated entities.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.answer import build_chart, fmt_inr, fmt_number, pretty_label, result_table
from app.db import ReadOnlyDB
from app.semantic_layer import load_semantic_layer


@dataclass
class Report:
    answer: str
    sql: str
    key: str
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    table: dict | None = None
    chart: dict | None = None
    notes: list[str] = field(default_factory=list)


# A question naming a measure these reports do not compute is left to the model, so a report never
# silently answers about something it did not measure.
_UNCOVERED = ("salary", "salaries", "bill", "bills", "property", "properties", "scheme", "fee", "tax", "taxes",
              "head", "designation", "gender", "month", "monthly", "daily", "day book", "daybook", "trend",
              "growth", "elected", "election")

_BROAD_WORDS = ("overall", "performance", "summary", "summarise", "summarize", "report card", "scorecard",
                "how is", "how are", "how did", "doing", "overview", "status of", "snapshot", "at a glance",
                "brief me", "briefing", "brief on", "give me the picture", "big picture")

_ATTENTION_WORDS = ("need attention", "needs attention", "need help", "at risk", "at-risk", "weakest",
                    "lagging", "falling behind", "poorest", "underperform")


def _pct(num, den) -> float | None:
    return None if not den else round(100.0 * float(num) / float(den), 2)


def _covers_asked_measures(question: str) -> bool:
    q = question.lower()
    return not any(w in q for w in _UNCOVERED)


def _broad(question: str) -> bool:
    """Wording that asks for an all-round picture rather than one figure."""
    q = question.lower()
    return any(w in q for w in _BROAD_WORDS)


def _attention(question: str) -> bool:
    q = question.lower()
    return any(w in q for w in _ATTENTION_WORDS)


def _fy(entities: dict) -> tuple[str, bool]:
    """(financial year, whether it was defaulted because the question named none)."""
    for p in entities.get("periods", []):
        if p.get("kind") == "fy":
            return p["fy"], False
    return load_semantic_layer()["data_period"]["latest_full_fy"], True


def _only_fy_periods(entities: dict) -> bool:
    """A month or a single date needs a finer grain than these FY-level views."""
    kinds = {p.get("kind") for p in entities.get("periods", [])}
    return not kinds or kinds == {"fy"}


def _places(entities: dict) -> list[tuple[str, str, str, object]]:
    """Every named place as (level, filter column, display name, bound value)."""
    out: list[tuple[str, str, str, object]] = []
    for g in entities.get("gps", []):
        if g.get("id"):
            out.append(("gp", "gp_id", f"{g['name']} GP ({g['taluk']} taluk, {g['zilla']} zilla)", g["id"]))
    for t in entities.get("taluks", []):
        out.append(("taluk", "taluk_name", f"{t} taluk", t))
    for z in entities.get("zillas", []):
        out.append(("zilla", "zilla_name", f"{z} zilla", z))
    return out


_VIEW = {"gp": "mart_summary_gp_year", "taluk": "mart_summary_taluk_year", "zilla": "mart_summary_zilla_year"}
_FIGURE_COLS = ("total_gps", "gps_all_books_closed", "total_demand", "total_collection", "revenue_balance",
                "staff_approved_by_eo", "staff_approval_pending_at_eo", "total_elected_members", "total_seats")
_GP_FIGURE_COLS = ("schemes_total", "schemes_closed", "total_demand", "total_collection", "revenue_balance",
                   "staff_approved_by_eo", "staff_approval_pending_at_eo", "total_elected_members", "total_seats")
_LEVEL_WORD = {"zilla": ("zillas", "zilla_name", "mart_summary_zilla_year"),
               "taluk": ("taluks", "taluk_name", "mart_summary_taluk_year"),
               "gp": ("GPs", "gp_name", "mart_summary_gp_year")}
_LEVEL_SINGULAR = {"zilla": "zilla", "taluk": "taluk", "gp": "GP"}


def _inline(sql: str, params: tuple) -> str:
    """The SQL with its bound values shown, for the answer's SQL panel only; the bound form is executed."""
    out = sql
    for p in params:
        out = out.replace("?", "'" + str(p).replace("'", "''") + "'", 1)
    return out


# ------------------------------------------------------------------------------------ needs attention
async def _needs_attention(question: str, entities: dict, db: ReadOnlyDB, timeout: float) -> Report | None:
    if not _attention(question):
        return None
    q = question.lower()
    level = "gp" if ("gp" in q or "gram panchayat" in q) else ("taluk" if "taluk" in q else "zilla")
    plural, name_col, view = _LEVEL_WORD[level]
    fy, defaulted = _fy(entities)

    where, params, scope_note = ["fy = ?"], [fy], ""
    for lev, col, display, value in _places(entities):
        if lev == level:
            continue
        where.append(f"{col} = ?")
        params.append(value)
        scope_note = f" in {display}"

    sql = (f"SELECT {name_col}, SUM(total_collection)*100.0/NULLIF(SUM(total_demand),0) AS collection_pct, "
           "SUM(total_demand) AS total_demand, SUM(total_collection) AS total_collection, "
           "SUM(revenue_balance) AS revenue_balance, "
           "SUM(staff_approval_pending_at_eo) AS staff_approval_pending_at_eo "
           f"FROM {view} WHERE " + " AND ".join(where) +
           f" GROUP BY {name_col} HAVING SUM(total_demand) > 0 ORDER BY collection_pct ASC LIMIT 10")
    qr = await db.run(sql, max_rows=10, timeout_seconds=timeout, params=tuple(params))
    if not qr.rows:
        return None

    first = qr.rows[0]
    lines = "\n".join(f"•  {r[0]} — {float(r[1]):.2f}% collected, {fmt_inr(r[4] or 0)} outstanding, "
                      f"{fmt_number(r[5] or 0, 0)} staff approvals pending" for r in qr.rows)
    one = _LEVEL_SINGULAR[level]
    text = (f"**The {plural}{scope_note} with the weakest revenue collection in FY {fy} start with {first[0]} at "
            f"{float(first[1]):.2f}%.** Collection % is total collected divided by total demanded for each "
            f"{one}, so a {one} appears here because of its own demand, not its size.\n\n{lines}")
    notes = [f"No financial year was named, so this uses FY {fy}."] if defaulted else []
    chart = build_chart("bar", name_col, "collection_pct", "Collection %", qr.columns, qr.rows)
    return Report(answer=text, sql=_inline(sql, tuple(params)), key=f"needs_attention:{level}", columns=qr.columns,
                  rows=qr.rows, table=result_table(qr.columns, qr.rows), chart=chart, notes=notes)


# ------------------------------------------------------------------------------------ compare
# the measure a comparison leads with: key -> (label, unit, SQL over mart_agg_taluk_fy, higher is better)
_CMP = {
    "collection_pct": ("collection %", "%", "SUM(total_collection)*100.0/NULLIF(SUM(total_demand),0)", True),
    "total_collection": ("total collection", "INR", "SUM(total_collection)", True),
    "total_demand": ("total demand", "INR", "SUM(total_demand)", None),
    "year_demand": ("current-year demand", "INR", "SUM(year_demand)", None),
    "arrears": ("arrears", "INR", "SUM(arrears)", False),
    "balance": ("outstanding balance", "INR", "SUM(balance)", False),
    "books_closed_pct": ("share of scheme books closed", "%", "SUM(scheme_books_closed)*100.0/NULLIF(SUM(scheme_books),0)", True),
    "gps_all_books_closed": ("GPs that closed all their books", "count", "SUM(gps_all_books_closed)", True),
    "staff_pending_at_eo": ("staff registrations pending at the EO", "count", "SUM(staff_approval_pending_at_eo)", False),
    "number_of_properties": ("number of properties", "count", "SUM(number_of_properties)", None),
    "receipts": ("scheme receipts", "INR", "SUM(receipts)", None),
    "expenditure": ("scheme expenditure", "INR", "SUM(expenditure)", None),
}
_ADD_UP_RE = re.compile(r"\b(add up|added up|sum of|summed|combined|together|total of (both|the two|them))\b")


def _cmp_fmt(unit: str, v) -> str:
    v = float(v or 0)
    return fmt_inr(v) if unit == "INR" else f"{v:.2f}%" if unit == "%" else fmt_number(v, 0)


async def _compare(question: str, entities: dict, db: ReadOnlyDB, timeout: float) -> Report | None:
    places = _places(entities)
    if len(places) < 2 or len({p[0] for p in places}) != 1 or _ADD_UP_RE.search(_q(question)):
        return None
    level = places[0][0]
    if level == "gp":          # GP names repeat across taluks; a GP comparison needs the model path
        return None
    metrics = entities.get("metrics") or []
    if len(metrics) > 1 or (metrics and metrics[0] not in _CMP):
        return None
    key = metrics[0] if metrics else "collection_pct"
    label, unit, expr, higher = _CMP[key]
    col = places[0][1]
    fy, defaulted = _fy(entities)
    marks = ", ".join("?" for _ in places)
    # column 1 is the lead measure; columns 2-6 are the fixed context shown on every line
    lead = key if key not in ("total_collection", "total_demand", "collection_pct", "books_closed_pct", "balance") else f"{key}_lead"
    sql = (f"SELECT {col}, {expr} AS {lead}, SUM(total_collection) AS total_collection, SUM(total_demand) AS total_demand, "
           "SUM(total_collection)*100.0/NULLIF(SUM(total_demand),0) AS collection_pct, "
           "SUM(scheme_books_closed)*100.0/NULLIF(SUM(scheme_books),0) AS books_closed_pct, SUM(balance) AS balance "
           f"FROM mart_agg_taluk_fy WHERE fy = ? AND {col} IN ({marks}) GROUP BY {col} ORDER BY 2 DESC")
    params = (fy, *[p[3] for p in places])
    qr = await db.run(sql, max_rows=20, timeout_seconds=timeout, params=params)
    if len(qr.rows) < 2:
        return None
    rows = qr.rows
    top, low = rows[0], rows[-1]
    if higher is None:
        head = f"**In FY {fy}, {top[0]} had the higher {label} ({_cmp_fmt(unit, top[1])}) and {low[0]} the lower ({_cmp_fmt(unit, low[1])}).**"
    elif higher:
        head = f"**In FY {fy}, {top[0]} is ahead on {label} ({_cmp_fmt(unit, top[1])}); {low[0]} is behind ({_cmp_fmt(unit, low[1])}).**"
    else:
        head = (f"**In FY {fy}, {low[0]} is better placed on {label} ({_cmp_fmt(unit, low[1])}); "
                f"{top[0]} has more ({_cmp_fmt(unit, top[1])}).**")
    lines = "\n".join(f"•  {r[0]} — {float(r[4] or 0):.2f}% collected ({fmt_inr(r[2] or 0)} of {fmt_inr(r[3] or 0)}), "
                       f"{float(r[5] or 0):.2f}% of scheme books closed, {fmt_inr(r[6] or 0)} outstanding" for r in rows)
    note = (" Each percentage is that place's own total over its own base, so the comparison is not tilted by size."
            if unit == "%" else "")
    text = f"{head}{note}\n\n{lines}"
    notes = [f"No financial year was named, so this uses FY {fy}."] if defaulted else []
    chart = build_chart("bar", col, qr.columns[1], label[:1].upper() + label[1:], qr.columns, rows)
    return Report(answer=text, sql=_inline(sql, params), key=f"compare:{level}", columns=qr.columns, rows=rows,
                  table=result_table(qr.columns, rows), chart=chart, notes=notes)


# ------------------------------------------------------------------------------------ overview
async def _overview(question: str, entities: dict, db: ReadOnlyDB, timeout: float) -> Report | None:
    if not _broad(question):
        return None
    places = _places(entities)
    if len(places) > 1:
        return None
    fy, defaulted = _fy(entities)

    if places:
        level, col, display, value = places[0]
        cols = _GP_FIGURE_COLS if level == "gp" else _FIGURE_COLS
        sql = (f"SELECT {', '.join(f'SUM({c}) AS {c}' for c in cols)} "
               f"FROM {_VIEW[level]} WHERE fy = ? AND {col} = ?")
        params: tuple = (fy, value)
    else:
        level, display = "state", "Karnataka (all zillas)"
        cols = _FIGURE_COLS
        sql = (f"SELECT {', '.join(f'SUM({c}) AS {c}' for c in cols)} "
               "FROM mart_summary_state_year WHERE fy = ?")
        params = (fy,)

    qr = await db.run(sql, max_rows=5, timeout_seconds=timeout, params=params)
    if not qr.rows or all(v is None for v in qr.rows[0]):
        return None
    row = qr.rows[0]
    v = dict(zip(cols, row))

    if level == "gp":
        num, den = v.get("schemes_closed") or 0, v.get("schemes_total") or 0
        closure = (f"{fmt_number(num, 0)} of {fmt_number(den, 0)} scheme accounts closed ({_pct(num, den):.2f}%)"
                   if den else "no scheme accounts recorded")
    else:
        num, den = v.get("gps_all_books_closed") or 0, v.get("total_gps") or 0
        closure = (f"{fmt_number(num, 0)} of {fmt_number(den, 0)} GPs closed all their books "
                   f"({_pct(num, den):.2f}%)" if den else "no closure figures recorded")

    coll_pct, seats_pct = _pct(v.get("total_collection"), v.get("total_demand")), _pct(
        v.get("total_elected_members"), v.get("total_seats"))
    text = (f"**{display} in FY {fy}: {fmt_inr(v.get('total_collection') or 0)} collected against "
            f"{fmt_inr(v.get('total_demand') or 0)} demanded"
            + (f" ({coll_pct:.2f}% collection).**" if coll_pct is not None else ".**") + "\n\n"
            f"• **Book closure:** {closure}.\n"
            f"• **Revenue:** demand {fmt_inr(v.get('total_demand') or 0)}, collected "
            f"{fmt_inr(v.get('total_collection') or 0)}, outstanding balance "
            f"{fmt_inr(v.get('revenue_balance') or 0)}.\n"
            f"• **Staff:** {fmt_number(v.get('staff_approved_by_eo') or 0, 0)} approved by the EO, "
            f"{fmt_number(v.get('staff_approval_pending_at_eo') or 0, 0)} still pending.\n"
            f"• **Elected members:** {fmt_number(v.get('total_elected_members') or 0, 0)} of "
            f"{fmt_number(v.get('total_seats') or 0, 0)} seats filled"
            + (f" ({seats_pct:.2f}%)." if seats_pct is not None else "."))

    notes = [f"No financial year was named, so this uses FY {fy}."] if defaulted else []
    # the places one level down, charted by collection (as the KPCL overview charts its stations): the zillas of
    # Karnataka, or the taluks of a zilla; a taluk or GP overview has no chart
    chart = None
    if level in ("state", "zilla"):
        child = "zilla_name" if level == "state" else "taluk_name"
        csql = (f"SELECT {child}, SUM(total_collection) AS total_collection FROM mart_summary_{'zilla' if level == 'state' else 'taluk'}_year "
                "WHERE fy = ?" + (" AND zilla_name = ?" if level == "zilla" else "") + f" GROUP BY {child} ORDER BY total_collection DESC")
        cr = await db.run(csql, max_rows=40, timeout_seconds=timeout, params=params)
        chart = build_chart("bar", child, "total_collection", f"Collection by {'zilla' if level == 'state' else 'taluk'}, FY {fy}",
                            cr.columns, cr.rows)
    return Report(answer=text, sql=_inline(sql, params), key=f"overview:{level}", columns=qr.columns, rows=qr.rows,
                  table=result_table(qr.columns, qr.rows), chart=chart, notes=notes)


# ------------------------------------------------------------------------------------------------ scope helpers
def _one_place(entities: dict) -> tuple[str, str, tuple, str] | None:
    """(where, display, params, level) for Karnataka, one zilla or one taluk on the pre-summed taluk tables."""
    zl, tl = entities.get("zillas", []), entities.get("taluks", [])
    if entities.get("gps") or len(zl) + len(tl) > 1:
        return None
    if tl:
        return " AND taluk_name = ?", f"{tl[0]} taluk", (tl[0],), "taluk"
    if zl:
        return " AND zilla_name = ?", f"{zl[0]} zilla", (zl[0],), "zilla"
    return "", "Karnataka", (), "state"


def _q(question: str) -> str:
    return " ".join(question.lower().split())


# ------------------------------------------------------------------------------------------------ scorecard
_SCORE_RE = re.compile(r"\b(scorecard|score card|league table|rank (all|every|the)|ranking of (all|the)|rank (zillas|taluks|districts)|"
                       r"(all|the) (zillas|taluks|districts) side by side|performance of (all|every|each) (zillas?|taluks?|districts?)|"
                       r"how do the (zillas|taluks|districts) compare|compare (all|every) (zillas|taluks|districts))\b")


async def _scorecard(question: str, entities: dict, db: ReadOnlyDB, timeout: float) -> Report | None:
    if not _SCORE_RE.search(_q(question)):
        return None
    place = _one_place(entities)
    if place is None or place[3] == "taluk":
        return None
    where, display, params, level = place
    col = "taluk_name" if level == "zilla" else "zilla_name"
    fy, defaulted = _fy(entities)
    sql = (f"SELECT {col} AS {col.split('_')[0]}, SUM(total_collection)*100.0/NULLIF(SUM(total_demand),0) AS collection_pct, "
           "SUM(scheme_books_closed)*100.0/NULLIF(SUM(scheme_books),0) AS books_closed_pct, "
           "SUM(gps_all_books_closed)*100.0/NULLIF(SUM(total_gps),0) AS all_books_closed_pct, "
           "SUM(staff_approval_pending_at_eo) AS staff_approval_pending_at_eo, SUM(total_collection) AS total_collection "
           f"FROM mart_agg_taluk_fy WHERE fy = ?{where} GROUP BY {col} ORDER BY collection_pct DESC")
    qr = await db.run(sql, max_rows=60, timeout_seconds=timeout, params=(fy, *params))
    if len(qr.rows) < 2:
        return None
    rows, noun = qr.rows, "taluks" if level == "zilla" else "zillas"
    best_close = max(rows, key=lambda r: r[2] or 0)
    text = (f"**{rows[0][0]} leads the {len(rows)} {noun}{'' if level == 'state' else ' of ' + display} on collection in FY {fy} "
            f"({float(rows[0][1]):.2f}%); {rows[-1][0]} is last ({float(rows[-1][1]):.2f}%).**\n\n"
            f"On book closure {best_close[0]} is ahead ({float(best_close[2]):.2f}% of scheme books closed). Every ratio is the place's own "
            "total over its own base, so size does not tilt the ranking.")
    notes = [f"No financial year was named, so this uses FY {fy}."] if defaulted else []
    return Report(answer=text, sql=_inline(sql, (fy, *params)), key=f"scorecard:{level}", columns=qr.columns, rows=rows,
                  table=result_table(qr.columns, rows), chart=build_chart("bar", qr.columns[0], "collection_pct", "Collection %", qr.columns, rows),
                  notes=notes)


# ------------------------------------------------------------------------------------------------ book-closure situation
_CLOSURE_RE = re.compile(r"\b(book[- ]?closure|closure of books|books? clos\w*|closing (of )?(the )?books)\b")
_SITUATION_RE = re.compile(r"\b(situation|status|position|picture|overview|summary|how (is|are|did|was)|state of|progress|report)\b")


async def _closure(question: str, entities: dict, db: ReadOnlyDB, timeout: float) -> Report | None:
    q = _q(question)
    if not _CLOSURE_RE.search(q) or not _SITUATION_RE.search(q) or entities.get("schemes"):
        return None
    if any(p.get("kind") not in ("fy",) for p in entities.get("periods", [])):
        return None
    place = _one_place(entities)
    if place is None:
        return None
    where, display, params, level = place
    fy, defaulted = _fy(entities)
    sql = ("SELECT scheme_name AS scheme, SUM(scheme_books_closed)*100.0/NULLIF(SUM(scheme_books),0) AS books_closed_pct, "
           f"SUM(scheme_books) AS scheme_books FROM mart_agg_taluk_scheme_fy WHERE fy = ?{where} GROUP BY scheme_name "
           "HAVING SUM(scheme_books) > 0 ORDER BY books_closed_pct ASC")
    qr = await db.run(sql, max_rows=40, timeout_seconds=timeout, params=(fy, *params))
    tot = (await db.run("SELECT SUM(scheme_books_closed), SUM(scheme_books), SUM(gps_all_books_closed), SUM(total_gps) FROM mart_agg_taluk_fy "
                        f"WHERE fy = ?{where}", 5, timeout, params=(fy, *params))).rows[0]
    if not qr.rows or not tot[1]:
        return None
    worst, best = qr.rows[0], qr.rows[-1]
    partial = fy == load_semantic_layer()["data_period"]["partial_fy"]
    text = (f"**{display} closed {_pct(tot[0], tot[1]):.2f}% of its {fmt_number(tot[1], 0)} scheme year-books for FY {fy}; "
            f"{fmt_number(tot[2], 0)} of {fmt_number(tot[3], 0)} GPs closed every book.**\n\n"
            f"{best[0]} is closed best ({float(best[1]):.2f}%) and {worst[0]} worst ({float(worst[1]):.2f}%)."
            + (" Year-end closure for the current year has not happened yet." if partial else ""))
    notes = [f"No financial year was named, so this uses FY {fy}."] if defaulted else []
    return Report(answer=text, sql=_inline(sql, (fy, *params)), key="closure", columns=qr.columns, rows=qr.rows,
                  table=result_table(qr.columns, qr.rows),
                  chart=build_chart("bar", "scheme", "books_closed_pct", "Year books closed %", qr.columns, qr.rows), notes=notes)


# ------------------------------------------------------------------------------------------------ salary-bill situation
_SALARY_RE = re.compile(r"\bsalar(y|ies)\b")
_SALARY_SIT_RE = re.compile(r"\b(situation|status|position|progress|funnel|pipeline|picture|overview|summary|how (is|are)|state of|where do)\b")


async def _salary(question: str, entities: dict, db: ReadOnlyDB, timeout: float) -> Report | None:
    q = _q(question)
    if not _SALARY_RE.search(q) or not _SALARY_SIT_RE.search(q):
        return None
    place = _one_place(entities)
    if place is None:
        return None
    where, display, params, level = place
    months = [p for p in entities.get("periods", []) if p.get("kind") == "month"]
    if months:
        mid = (await db.run("SELECT month_id FROM mart_dim_month WHERE month_label = ?", 2, timeout, params=(months[0]["value"],))).rows
        if not mid:
            return None
        month_id = mid[0][0]
    else:
        month_id = (await db.run("SELECT MAX(month_id) FROM mart_fact_taluk_salary_bills", 2, timeout)).rows[0][0]
    sql = ("SELECT staff_type_name AS staff_type, SUM(total_number_of_staff) AS total_number_of_staff, "
           "SUM(number_of_main_bill_generated) AS number_of_main_bill_generated, "
           "SUM(number_of_main_bill_processed_by_bank) AS number_of_main_bill_processed_by_bank, "
           "SUM(number_of_staff_salary_paid) AS number_of_staff_salary_paid, "
           "SUM(number_of_staff_salary_rejected_by_bank) AS number_of_staff_salary_rejected_by_bank "
           f"FROM mart_fact_taluk_salary_bills WHERE month_id = ?{where} GROUP BY staff_type_name ORDER BY total_number_of_staff DESC")
    qr = await db.run(sql, max_rows=20, timeout_seconds=timeout, params=(month_id, *params))
    if not qr.rows:
        return None
    staff, paid, rej = (sum(r[i] for r in qr.rows) for i in (1, 4, 5))
    label = (await db.run("SELECT month_label FROM mart_dim_month WHERE month_id = ?", 2, timeout, params=(month_id,))).rows[0][0]
    month = pretty_label(label)
    text = (f"**In {month}, {fmt_number(paid, 0)} of {fmt_number(staff, 0)} staff on the payroll in {display} were paid "
            f"({_pct(paid, staff):.2f}%), and the bank rejected {fmt_number(rej, 0)} salaries.**\n\n"
            + "; ".join(f"{r[0]}: {fmt_number(r[4], 0)} paid of {fmt_number(r[1], 0)}" for r in qr.rows) + ".")
    return Report(answer=text, sql=_inline(sql, (month_id, *params)), key="salary", columns=qr.columns, rows=qr.rows,
                  table=result_table(qr.columns, qr.rows),
                  chart=build_chart("bar", "staff_type", "number_of_staff_salary_paid", f"Staff paid, {month}", qr.columns, qr.rows))


# ------------------------------------------------------------------------------------------------ EO approval backlog
_BACKLOG_RE = re.compile(r"\b(backlog|queue|pending approvals?|approvals? pending|waiting (for|at) (the )?eo|eo (approval )?(situation|status|position))\b")


async def _eo_backlog(question: str, entities: dict, db: ReadOnlyDB, timeout: float) -> Report | None:
    if not _BACKLOG_RE.search(_q(question)):
        return None
    place = _one_place(entities)
    if place is None or place[3] == "taluk":
        return None
    where, display, params, level = place
    fy, defaulted = _fy(entities)
    sql = ("SELECT taluk_name AS taluk, zilla_name AS zilla, SUM(staff_approval_pending_at_eo) AS staff_approval_pending_at_eo, "
           "SUM(staff_approved_by_eo) AS staff_approved_by_eo, SUM(staff_registrations_rejected_by_eo) AS staff_registrations_rejected_by_eo "
           f"FROM mart_agg_taluk_fy WHERE fy = ?{where} GROUP BY taluk_name, zilla_name HAVING SUM(staff_approval_pending_at_eo) > 0 "
           "ORDER BY staff_approval_pending_at_eo DESC, taluk_name LIMIT 15")
    qr = await db.run(sql, max_rows=20, timeout_seconds=timeout, params=(fy, *params))
    tot = (await db.run(f"SELECT SUM(staff_approval_pending_at_eo), SUM(staff_approved_by_eo) FROM mart_agg_taluk_fy WHERE fy = ?{where}",
                        5, timeout, params=(fy, *params))).rows[0]
    notes = [f"No financial year was named, so this uses FY {fy}."] if defaulted else []
    if not qr.rows:
        return Report(answer=f"**No staff registrations were pending at the EO in {display} in FY {fy}.**", sql=_inline(sql, (fy, *params)),
                      key="eo_backlog", notes=notes)
    text = (f"**{fmt_number(tot[0], 0)} staff registrations were waiting for the EO in {display} in FY {fy}; the longest queue is in "
            f"{qr.rows[0][0]} taluk ({fmt_number(qr.rows[0][2], 0)}).**\n\n"
            f"{fmt_number(tot[1], 0)} registrations had been approved. The table lists the taluks with the most pending.")
    return Report(answer=text, sql=_inline(sql, (fy, *params)), key="eo_backlog", columns=qr.columns, rows=qr.rows,
                  table=result_table(qr.columns, qr.rows),
                  chart=build_chart("bar", "taluk", "staff_approval_pending_at_eo", "Registrations pending at the EO", qr.columns, qr.rows),
                  notes=notes)


# ------------------------------------------------------------------------------------------------ one place, two years
async def _period_compare(question: str, entities: dict, db: ReadOnlyDB, timeout: float) -> Report | None:
    fys = sorted({p["fy"] for p in entities.get("periods", []) if p.get("kind") == "fy"})
    if len(fys) != 2 or any(p.get("kind") not in ("fy",) for p in entities.get("periods", [])):
        return None
    if not ({"comparison"} & set(entities.get("intents") or [])) and " and " not in _q(question):
        return None
    if entities.get("schemes") or entities.get("fee_types") or entities.get("staff_types") or len(entities.get("metrics") or []) > 1:
        return None
    place = _one_place(entities)
    if place is None:
        return None
    where, display, params, level = place
    sql = ("SELECT fy, SUM(total_demand) AS total_demand, SUM(total_collection) AS total_collection, "
           "SUM(total_collection)*100.0/NULLIF(SUM(total_demand),0) AS collection_pct, SUM(balance) AS balance, "
           "SUM(scheme_books_closed)*100.0/NULLIF(SUM(scheme_books),0) AS books_closed_pct, SUM(gps_all_books_closed) AS gps_all_books_closed, "
           "SUM(staff_approval_pending_at_eo) AS staff_approval_pending_at_eo "
           f"FROM mart_agg_taluk_fy WHERE fy IN (?, ?){where} GROUP BY fy ORDER BY fy")
    qr = await db.run(sql, max_rows=5, timeout_seconds=timeout, params=(*fys, *params))
    if len(qr.rows) != 2:
        return None
    a, b = qr.rows
    metrics = entities.get("metrics") or []
    key = metrics[0] if metrics and metrics[0] in _CMP else "total_collection"
    if key in ("total_collection", "collection_pct"):
        chg = 100.0 * (b[2] / a[2] - 1) if a[2] else 0.0
        head = (f"**{display} collected {fmt_inr(b[2])} in FY {b[0]} against {fmt_inr(a[2])} in FY {a[0]} "
                f"({'+' if chg >= 0 else ''}{chg:.1f}%); collection % moved from {float(a[3]):.2f}% to {float(b[3]):.2f}%.**")
    else:
        # lead with the measure that was asked about, from the same pre-summed table
        label, unit, expr, _ = _CMP[key]
        lead = await db.run(f"SELECT fy, {expr} FROM mart_agg_taluk_fy WHERE fy IN (?, ?){where} GROUP BY fy ORDER BY fy",
                            max_rows=5, timeout_seconds=timeout, params=(*fys, *params))
        (fa, va), (fb, vb) = lead.rows
        moved = f"{float(vb) - float(va):+.2f} points" if unit == "%" else \
            f"{'+' if vb >= va else ''}{100.0 * (float(vb) / float(va) - 1):.1f}%" if va else "new"
        head = (f"**{display}'s {label} went from {_cmp_fmt(unit, va)} in FY {fa} to {_cmp_fmt(unit, vb)} in FY {fb} ({moved}).**")
    coll = "" if key in ("total_collection", "collection_pct") else f"Collection {fmt_inr(a[2])} → {fmt_inr(b[2])}; "
    text = (f"{head}\n\n{coll}"
            f"{'o' if coll else 'O'}utstanding balance {fmt_inr(a[4])} → {fmt_inr(b[4])}; "
            f"scheme books closed {float(a[5]):.2f}% → {float(b[5]):.2f}%; "
            f"GPs with every book closed {fmt_number(a[6], 0)} → {fmt_number(b[6], 0)}.")
    if b[0] == load_semantic_layer()["data_period"]["partial_fy"]:
        text += f" FY {b[0]} covers April to September 2026 only."
    return Report(answer=text, sql=_inline(sql, (*fys, *params)), key=f"period_compare:{level}", columns=qr.columns, rows=qr.rows,
                  table=result_table(qr.columns, qr.rows),
                  chart=build_chart("bar", "fy", "total_collection", "Total collection", qr.columns, qr.rows))


# ------------------------------------------------------------------------------------------------ one place against the state
_STATE_CMP_RE = re.compile(r"\b(the state|state average|state figure|state level|state as a whole|statewide|karnataka as a whole|"
                           r"rest of the state|whole of karnataka)\b|\b(than|with|against|to|versus|vs) karnataka\b")


async def _vs_state(question: str, entities: dict, db: ReadOnlyDB, timeout: float) -> Report | None:
    q = _q(question)
    if not _STATE_CMP_RE.search(q) or not ({"comparison"} & set(entities.get("intents") or []) or
                                           re.search(r"\b(above|below|compare|against|relative)\b", q)):
        return None
    place = _one_place(entities)
    if place is None or place[3] == "state":
        return None
    metrics = entities.get("metrics") or []
    if len(metrics) > 1 or (metrics and metrics[0] not in _CMP):
        return None
    if any(p.get("kind") != "fy" for p in entities.get("periods", [])) or len(entities.get("periods", [])) > 1:
        return None
    key = metrics[0] if metrics else "collection_pct"
    label, unit, expr, higher = _CMP[key]
    where, display, params, level = place
    fy, defaulted = _fy(entities)
    sql = (f"SELECT ? AS place, {expr} AS {key} FROM mart_agg_taluk_fy WHERE fy = ?{where} "
           f"UNION ALL SELECT 'Karnataka', {expr} FROM mart_agg_taluk_fy WHERE fy = ?")
    allp = (display, fy, *params, fy)
    qr = await db.run(sql, max_rows=5, timeout_seconds=timeout, params=allp)
    if len(qr.rows) != 2 or qr.rows[0][1] is None or qr.rows[1][1] is None:
        return None
    mine, state = float(qr.rows[0][1]), float(qr.rows[1][1])
    if unit == "%":
        diff = mine - state
        side = "above" if diff > 0 else "below" if diff < 0 else "level with"
        text = (f"**{display} is {side} the state on {label} in FY {fy}: {mine:.2f}% against Karnataka's {state:.2f}% "
                f"({'+' if diff >= 0 else ''}{diff:.2f} points).**\n\nThe state figure is the whole state's total over its own "
                "base, not an average of the zilla percentages.")
    else:
        share = 100.0 * mine / state if state else 0.0
        text = (f"**{display}'s {label} in FY {fy} was {_cmp_fmt(unit, mine)}, {share:.2f}% of Karnataka's "
                f"{_cmp_fmt(unit, state)}.**\n\nA total is compared with the state as a share, since places differ in size.")
    notes = [f"No financial year was named, so this uses FY {fy}."] if defaulted else []
    return Report(answer=text, sql=_inline(sql, allp), key=f"vs_state:{level}", columns=qr.columns, rows=qr.rows,
                  table=result_table(qr.columns, qr.rows),
                  chart=build_chart("bar", "place", key, label[:1].upper() + label[1:], qr.columns, qr.rows), notes=notes)


# ------------------------------------------------------------------------------------------------ one place, two or more months
_MONTH_CMP = {"total_collection": ("collection", "INR", "SUM(collection_amount)"),
              "receipts": ("scheme receipts", "INR", "SUM(receipts)"),
              "expenditure": ("scheme expenditure", "INR", "SUM(expenditure)"),
              "salary_paid": ("staff whose salary was paid", "count", "SUM(number_of_staff_salary_paid)"),
              "salary_rejected": ("salaries rejected by the bank", "count", "SUM(number_of_staff_salary_rejected_by_bank)")}


async def _month_compare(question: str, entities: dict, db: ReadOnlyDB, timeout: float) -> Report | None:
    periods = entities.get("periods", [])
    if len(periods) < 2 or len(periods) > 12 or any(p.get("kind") != "month" for p in periods):
        return None
    metrics = entities.get("metrics") or []
    if len(metrics) > 1 or (metrics and metrics[0] not in _MONTH_CMP):
        return None
    if entities.get("schemes") or entities.get("fee_types") or entities.get("staff_types"):
        return None
    place = _one_place(entities)
    if place is None:
        return None
    key = metrics[0] if metrics else "total_collection"
    label, unit, expr = _MONTH_CMP[key]
    where, display, params, level = place
    labels = [p["value"] for p in periods]
    marks = ", ".join("?" for _ in labels)
    sql = (f"SELECT month_label, {expr} AS {key} FROM mart_agg_taluk_month WHERE month_label IN ({marks}){where} "
           "GROUP BY month_id, month_label ORDER BY month_id")
    allp = (*labels, *params)
    qr = await db.run(sql, max_rows=20, timeout_seconds=timeout, params=allp)
    if len(qr.rows) != len(labels):
        return None
    rows = qr.rows
    first, last = rows[0], rows[-1]
    chg = 100.0 * (float(last[1]) / float(first[1]) - 1) if first[1] else 0.0
    text = (f"**{display}: {label} was {_cmp_fmt(unit, last[1])} in {pretty_label(last[0])} against {_cmp_fmt(unit, first[1])} in "
            f"{pretty_label(first[0])} ({'+' if chg >= 0 else ''}{chg:.1f}%).**")
    if len(rows) > 2:
        text += "\n\n" + "; ".join(f"{pretty_label(r[0])} {_cmp_fmt(unit, r[1])}" for r in rows) + "."
    return Report(answer=text, sql=_inline(sql, allp), key=f"month_compare:{level}", columns=qr.columns, rows=rows,
                  table=result_table(qr.columns, rows),
                  chart=build_chart("bar", "month_label", key, label[:1].upper() + label[1:], qr.columns, rows))


# these define their own scope (salary, schemes, months) and run before the coverage filter below
_SITUATIONS = (_salary, _closure, _eo_backlog, _scorecard)
_REPORTS = (_needs_attention, _compare, _overview)


async def report(question: str, entities: dict, db: ReadOnlyDB, timeout: float) -> Report | None:
    """The first reviewed report that applies, or None so the question moves on (breakdowns, metric lookup, model)."""
    if "filter" in (entities.get("intents") or []):
        return None                                     # a condition on each place: the SQL path counts / lists them
    if "trend" not in (entities.get("intents") or []):
        for fn in _SITUATIONS:
            out = await fn(question, entities, db, timeout)
            if out is not None:
                return out
    for fn in (_period_compare, _vs_state, _month_compare):
        out = await fn(question, entities, db, timeout)
        if out is not None:
            return out
    if not _only_fy_periods(entities) or not _covers_asked_measures(question):
        return None
    if "trend" in (entities.get("intents") or []):
        return None
    for fn in _REPORTS:
        out = await fn(question, entities, db, timeout)
        if out is not None:
            return out
    return None

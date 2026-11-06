"""
Deterministic breakdowns (no LLM) -- blueprint L9b, KPCL's breakdown.py for RDPR.

"<measure> by month / quarter / year / zilla / taluk / revenue head / property category / scheme / staff type",
"top 5 taluks by collection %", "collection for every year", "which zilla has the lowest balance": one measure, laid
out along one dimension, for Karnataka, a zilla or a taluk, read from the pre-summed mart_agg_* tables with the same
SUM/SUM formulas as the dashboard. Every answer is written in the house style -- a bold headline with the point, one
short note, then the chart and the table -- and returns the rows it was computed from.

Returns None (so the question moves on) when it cannot answer exactly: a measure the dimension does not hold, a GP,
two measures, or no dimension word at all.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.answer import build_chart, fmt_inr, fmt_number, pretty_label, result_table
from app.db import ReadOnlyDB
from app.semantic_layer import load_semantic_layer, norm


@dataclass
class Breakdown:
    answer: str
    sql: str
    key: str
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    table: dict | None = None
    chart: dict | None = None
    notes: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ which dimension the question asks for
_DIMS = [
    ("month", r"\b(month[- ]?wise|monthly|by month|each month|every month|month by month|per month|across (the )?months|which month|what month)\b"),
    ("quarter", r"\b(quarter[- ]?wise|quarterly|by quarter|each quarter|per quarter|which quarter)\b"),
    ("fy", r"\b(year[- ]?wise|yearly|by year|each year|every year|each financial year|every financial year|all (the )?(financial )?years|"
           r"over the years|year by year|year on year|trend|since 2022|five years|5 years|which year|which financial year|over time|across (the )?years)\b"),
    ("head", r"\b(by (revenue )?head|revenue[- ]head[- ]?wise|head[- ]?wise|each (revenue )?head|by tax( type)?|tax[- ]?wise|by fee( type)?|"
             r"each tax|which (revenue )?head|which tax|revenue heads)\b"),
    ("property", r"\b(by property( category| type)?|property[- ](category|type)[- ]?wise|each property (category|type)|"
                 r"which property (category|type)|property categories|property types)\b"),
    ("scheme", r"\b(by scheme|scheme[- ]?wise|each scheme(?! (year )?books?)|every scheme(?! (year )?books?)|which scheme|all schemes|per scheme|schemes)\b"),
    ("staff_type", r"\b(by staff type|staff[- ]type[- ]?wise|each staff type|which staff type|staff types)\b"),
    ("designation", r"\b(by designation|designation[- ]?wise|each designation|which designation|designations)\b"),
    ("taluk", r"\b(taluk[- ]?wise|by taluk|each taluk|every taluk|all (the )?taluks|which taluks?|top \d+ taluks|bottom \d+ taluks|taluks)\b"),
    ("zilla", r"\b(zilla[- ]?wise|district[- ]?wise|by zilla|by district|each zilla|every zilla|each district|all (the )?zillas|"
              r"all (the )?districts|which zillas?|which districts?|top \d+ zillas|bottom \d+ zillas|zillas|districts)\b"),
]
_TOP_RE = re.compile(r"\b(top|highest|best|most|largest|biggest|leading|maximum|peak)\b")
_BOTTOM_RE = re.compile(r"\b(bottom|lowest|worst|least|smallest|fewest|minimum|weakest|poorest|lagging)\b")
_N_RE = re.compile(r"\b(?:top|bottom|first|last)\s+(\d{1,2})\b|\b(\d{1,2})\s+(?:zillas|taluks|districts|schemes|months|heads)\b")
_WORDS_N = {"three": 3, "five": 5, "ten": 10, "two": 2, "four": 4, "six": 6, "seven": 7, "eight": 8}


# ------------------------------------------------------------------ measures each table can give: key -> (label, unit, expr)
_FY = {
    "total_collection": ("total collection", "INR", "SUM(total_collection)"),
    "year_demand": ("current-year demand", "INR", "SUM(year_demand)"),
    "total_demand": ("total demand", "INR", "SUM(total_demand)"),
    "arrears": ("arrears", "INR", "SUM(arrears)"),
    "adjustments": ("adjustments", "INR", "SUM(adjustments)"),
    "balance": ("outstanding balance", "INR", "SUM(balance)"),
    "collection_pct": ("collection %", "%", "SUM(total_collection)*100.0/NULLIF(SUM(total_demand),0)"),
    "number_of_properties": ("number of properties", "count", "SUM(number_of_properties)"),
    "books_closed_pct": ("share of scheme books closed", "%", "SUM(scheme_books_closed)*100.0/NULLIF(SUM(scheme_books),0)"),
    "gps_all_books_closed": ("GPs that closed all their books", "count", "SUM(gps_all_books_closed)"),
    "receipts": ("scheme receipts", "INR", "SUM(receipts)"),
    "expenditure": ("scheme expenditure", "INR", "SUM(expenditure)"),
    "staff_pending_at_eo": ("staff registrations pending at the EO", "count", "SUM(staff_approval_pending_at_eo)"),
    "staff_approved_by_eo": ("staff approved by the EO", "count", "SUM(staff_approved_by_eo)"),
    "staff_rejected_by_eo": ("staff registrations rejected by the EO", "count", "SUM(staff_registrations_rejected_by_eo)"),
    "staff_sent_to_eo": ("staff registrations sent to the EO", "count", "SUM(staff_registrations_sent_to_eo)"),
    "elected_members": ("elected members registered", "count", "SUM(total_elected_members)"),
    "total_seats": ("seats in GP bodies", "count", "SUM(total_seats)"),
    "presidents": ("GPs with a President registered", "count", "SUM(total_adhyaksha_president)"),
    "seats_filled_pct": ("seats filled %", "%", "SUM(total_elected_members)*100.0/NULLIF(SUM(total_seats),0)"),
}
_MONTH = {
    "total_collection": ("collection", "INR", "SUM(collection_amount)"),
    "receipts": ("scheme receipts", "INR", "SUM(receipts)"),
    "expenditure": ("scheme expenditure", "INR", "SUM(expenditure)"),
    "closing_balance": ("closing balance of scheme accounts", "INR", "SUM(closing_balance)"),
    "books_closed_pct": ("share of month-end books closed", "%", "SUM(month_books_closed)*100.0/NULLIF(SUM(month_books),0)"),
    "salary_paid": ("staff whose salary was paid", "count", "SUM(number_of_staff_salary_paid)"),
    "salary_rejected": ("salaries rejected by the bank", "count", "SUM(number_of_staff_salary_rejected_by_bank)"),
}
_HEAD = {k: _FY[k] for k in ("total_collection", "year_demand", "total_demand", "arrears", "adjustments", "balance", "collection_pct")}
_PROP = {k: _FY[k] for k in ("total_collection", "total_demand", "balance", "collection_pct", "number_of_properties")}
_SCHEME = {"receipts": _FY["receipts"], "expenditure": _FY["expenditure"], "books_closed_pct": _FY["books_closed_pct"],
           "closing_balance": ("closing balance at the end of the year", "INR", "SUM(closing_balance)")}
_DEFAULT = {"fy": "total_collection", "month": "total_collection", "quarter": "total_collection", "zilla": "collection_pct",
            "taluk": "collection_pct", "head": "total_collection", "property": "total_demand", "scheme": "receipts",
            "staff_type": "staff_active", "designation": "staff_active"}
# measures implied by plain words when the registry found none
_WORD_METRIC = [(r"\bcollection ?%|collection per ?cent(age)?|collection pct|collection rate|collection efficiency|per ?cent(age)? collected",
                 "collection_pct"),
                (r"\bbooks? clos|closure", "books_closed_pct"), (r"\breceipts?\b", "receipts"), (r"\bexpenditure|spending|spent|spend\b", "expenditure"),
                (r"\bbalance|outstanding|dues\b", "balance"), (r"\barrears?\b", "arrears"), (r"\bdemand\b", "total_demand"),
                (r"\bcollect", "total_collection"), (r"\brevenue\b", "total_collection"), (r"\bpending\b", "staff_pending_at_eo"),
                (r"\bsalar(y|ies) (paid|payment)|staff paid\b", "salary_paid"), (r"\brejected by (the )?bank|bank rejection", "salary_rejected"),
                (r"\bseats? filled|elected members", "elected_members"), (r"\bpropert", "number_of_properties"), (r"\bstaff\b", "staff_active")]


def _dimension(q: str) -> str | None:
    for dim, rx in _DIMS:
        if re.search(rx, q):
            return dim
    return None


def _metric(q: str, entities: dict) -> str | None:
    ms = list(entities.get("metrics") or [])
    if "staff_active" in ms and len(ms) > 1:
        ms.remove("staff_active")
    if len(ms) == 1:
        return ms[0]
    if len(ms) > 1:
        return None
    for rx, key in _WORD_METRIC:
        if re.search(rx, q):
            return key
    return None


def _n(q: str) -> int | None:
    m = _N_RE.search(q)
    if m:
        return int(m.group(1) or m.group(2))
    for w, n in _WORDS_N.items():
        if re.search(rf"\b(top|bottom|first|last) {w}\b|\b{w} (zillas|taluks|districts|schemes|months|heads)\b", q):
            return n
    return None


def _fmt(unit: str, v) -> str:
    if v is None:
        return "no data"
    return fmt_inr(v) if unit == "INR" else f"{v:,.2f}%" if unit == "%" else fmt_number(v, 0)


def _inline(sql: str, params: tuple) -> str:
    out = sql
    for p in params:
        out = out.replace("?", "'" + str(p).replace("'", "''") + "'", 1)
    return out


def _scope(entities: dict) -> tuple[str, str, tuple, str] | None:
    """(where-clause, display, params, level) for Karnataka, one zilla or one taluk; None for GPs or several places."""
    zl, tl, gp = entities.get("zillas", []), entities.get("taluks", []), entities.get("gps", [])
    if gp or len(zl) + len(tl) > 1:
        return None
    if tl:
        return " AND taluk_name = ?", f"{tl[0]} taluk", (tl[0],), "taluk"
    if zl:
        return " AND zilla_name = ?", f"{zl[0]} zilla", (zl[0],), "zilla"
    return "", "Karnataka", (), "state"


def _fy(entities: dict) -> tuple[str, bool]:
    for p in entities.get("periods", []):
        if p.get("kind") == "fy":
            return p["fy"], False
        if p.get("kind") == "month" and p.get("fy"):
            return p["fy"], False
    return load_semantic_layer()["data_period"]["latest_full_fy"], True


_LIST_RE = re.compile(r"^\s*(?:please\s+)?(?:list|name|show|give|tell)(?: me)?(?: all| every)?(?: the)? "
                      r"(zillas|districts|taluks|talukas|gps|gram panchayats)\b(?! by| wise)|"
                      r"^\s*(?:what|which) are the (zillas|districts|taluks|talukas|gps|gram panchayats)\b")


async def listing(question: str, entities: dict, db: ReadOnlyDB, timeout: float) -> Breakdown | None:
    """The places themselves (no measure): the zillas, the taluks of a zilla, the GPs of a taluk, with their counts."""
    q = norm(question)
    m = _LIST_RE.search(q)
    if not m or entities.get("metrics") or entities.get("gps"):
        return None
    kind = (m.group(1) or m.group(2)).rstrip("s").replace("district", "zilla").replace("taluka", "taluk").replace("gram panchayat", "gp")
    zl, tl = entities.get("zillas", []), entities.get("taluks", [])
    if len(zl) + len(tl) > 1:
        return None
    if kind == "zilla":
        if zl or tl:
            return None
        sql = ("SELECT zilla_name AS zilla, COUNT(DISTINCT taluk_name) AS taluk_count, COUNT(*) AS gp_count FROM mart_dim_gp "
               "GROUP BY zilla_name ORDER BY zilla_name")
        params, display = (), "Karnataka"
    elif kind == "taluk":
        if tl:
            return None
        sql = ("SELECT taluk_name AS taluk, zilla_name AS zilla, COUNT(*) AS gp_count FROM mart_dim_gp"
               + (" WHERE zilla_name = ?" if zl else "") + " GROUP BY taluk_name, zilla_name ORDER BY zilla_name, taluk_name")
        params, display = ((zl[0],), f"{zl[0]} zilla") if zl else ((), "Karnataka")
    else:
        if not tl:
            return None                                  # 6,099 GPs: only for one taluk
        sql = "SELECT gp_name AS gp, taluk_name AS taluk, zilla_name AS zilla FROM mart_dim_gp WHERE taluk_name = ? ORDER BY gp_name"
        params, display = (tl[0],), f"{tl[0]} taluk"
    qr = await db.run(sql, max_rows=400, timeout_seconds=timeout, params=params)
    rows = [tuple(r) for r in qr.rows]
    if not rows:
        return None
    noun = {"zilla": "zillas", "taluk": "taluks", "gp": "GPs"}[kind]
    names = ", ".join(r[0] for r in rows[:60]) + (" …" if len(rows) > 60 else "")
    extra = ""
    if kind == "zilla":
        extra = f" with {sum(r[1] for r in rows):,} taluks and {sum(r[2] for r in rows):,} GPs"
    elif kind == "taluk":
        extra = f" with {sum(r[2] for r in rows):,} GPs"
    answer = f"**{display} has {len(rows):,} {noun}{extra}.**\n\n{names}."
    chart = build_chart("bar", qr.columns[0], "gp_count", "GPs", qr.columns, rows) if kind != "gp" else None
    return Breakdown(answer=answer, sql=_inline(sql, params), key=f"list:{kind}", columns=qr.columns, rows=rows,
                     table=result_table(qr.columns, rows), chart=chart)


async def breakdown(question: str, entities: dict, db: ReadOnlyDB, timeout: float) -> Breakdown | None:
    q = norm(question)
    if "filter" in (entities.get("intents") or []):
        return None                                     # a condition on each place: the SQL path counts / lists them
    listed = await listing(question, entities, db, timeout)
    if listed is not None:
        return listed
    dim = _dimension(q)
    if dim is None:
        return None
    periods = [p for p in entities.get("periods", []) if p.get("kind") != "out_of_range"]
    if dim != "fy" and any(p.get("kind") in ("date", "calendar_year", "quarter") for p in periods):
        return None
    if len([p for p in periods if p.get("kind") == "fy"]) > 1:
        return None                                     # two FYs side by side: the comparison report / model handles it
    if entities.get("fee_types") or entities.get("property_categories") or entities.get("staff_types") or entities.get("designations"):
        if dim not in ("fy", "month", "zilla", "taluk") or entities.get("staff_types") or entities.get("designations"):
            return None
    metric = _metric(q, entities) or _DEFAULT[dim]
    scope = _scope(entities)
    if scope is None:
        return None
    where, display, sparams, level = scope
    if dim == "taluk" and level == "taluk" or dim == "zilla" and level in ("zilla", "taluk"):
        return None                                      # 'taluks of Badami taluk' makes no sense
    if dim in ("staff_type", "designation") or metric == "staff_active" and dim in ("zilla", "taluk"):
        return await _staff(question, q, dim, metric, where, display, sparams, db, timeout)

    fy, defaulted = _fy(entities)
    scheme = entities.get("schemes") or []
    head = entities.get("fee_types") or []
    if dim in ("fy", "zilla", "taluk"):
        table, measures = ("mart_agg_taluk_fee_type_fy", _HEAD) if head else ("mart_agg_taluk_scheme_fy", _SCHEME) if scheme else ("mart_agg_taluk_fy", _FY)
        if head and metric not in _HEAD or scheme and metric not in _SCHEME:
            return None
        extra, eparams = (" AND fee_type_name = ?", (head[0],)) if head else (" AND scheme_name = ?", (scheme[0],)) if scheme else ("", ())
    elif dim in ("month", "quarter"):
        if scheme or head:
            return None
        table, measures, extra, eparams = "mart_agg_taluk_month", _MONTH, "", ()
    elif dim == "head":
        table, measures, extra, eparams = "mart_agg_taluk_fee_type_fy", _HEAD, "", ()
    elif dim == "property":
        table, measures, extra, eparams = "mart_agg_taluk_property_fy", _PROP, "", ()
    else:
        table, measures, extra, eparams = "mart_agg_taluk_scheme_fy", _SCHEME, "", ()
    if metric not in measures:
        return None
    label, unit, expr = measures[metric]
    if scheme:
        label += f" ({scheme[0]})"
    if head:
        label += f" ({head[0]})"

    group = {"fy": "fy", "month": "month_id, month_label", "quarter": "quarter", "zilla": "zilla_name", "taluk": "taluk_name",
             "head": "fee_type_name", "property": "report_category", "scheme": "scheme_name"}[dim]
    label_col = {"fy": "fy", "month": "month_label", "quarter": "quarter", "zilla": "zilla", "taluk": "taluk", "head": "revenue_head",
                 "property": "property_category", "scheme": "scheme"}[dim]
    sel_label = {"zilla": "zilla_name AS zilla", "taluk": "taluk_name AS taluk", "head": "fee_type_name AS revenue_head",
                 "property": "report_category AS property_category", "scheme": "scheme_name AS scheme", "fy": "fy",
                 "month": "month_label", "quarter": "'Q' || ((fy_month_no + 2) / 3) AS quarter"}[dim]
    period_where, pparams = ("", ()) if dim == "fy" else (" AND fy = ?", (fy,))
    sql = (f"SELECT {sel_label}, {expr} AS value FROM {table} WHERE 1 = 1{period_where}{where}{extra} "
           f"GROUP BY {'fy, quarter' if dim == 'quarter' else group} ORDER BY " + ("month_id" if dim == "month" else "fy" if dim == "fy" else "quarter" if dim == "quarter" else "value DESC"))
    if dim == "quarter":
        sql = (f"SELECT 'Q' || ((fy_month_no + 2) / 3) AS quarter, {expr} AS value FROM {table} WHERE fy = ?{where} "
               "GROUP BY (fy_month_no + 2) / 3 ORDER BY quarter")
        pparams = (fy,)
    params = (*pparams, *sparams, *eparams)
    qr = await db.run(sql, max_rows=400, timeout_seconds=timeout, params=params)
    rows = [r for r in qr.rows if r[1] is not None]
    if len(rows) < 2:
        return None
    columns = [label_col, metric]           # the measure's own column name tells the writer its unit
    rows = [(r[0], r[1]) for r in rows]
    n = _n(q)
    top, bottom = bool(_TOP_RE.search(q)), bool(_BOTTOM_RE.search(q))
    ranked = dim not in ("fy", "month", "quarter")
    if ranked and bottom and not top:
        rows = sorted(rows, key=lambda r: r[1])
    if ranked and n:
        rows = rows[:n]
    answer, notes = _write(dim, label, unit, rows, display, fy, defaulted, top, bottom, ranked, n, entities)
    chart = build_chart("line" if dim in ("fy", "month") and unit == "%" or dim == "fy" else "bar", label_col, columns[1],
                        label[:1].upper() + label[1:], columns, rows)
    return Breakdown(answer=answer, sql=_inline(sql, params), key=f"{dim}:{metric}", columns=columns, rows=rows,
                     table=result_table(columns, rows), chart=chart, notes=notes)


def _write(dim, label, unit, rows, display, fy, defaulted, top, bottom, ranked, n, entities) -> tuple[str, list[str]]:
    f = lambda v: _fmt(unit, v)  # noqa: E731
    noun = {"zilla": "zillas", "taluk": "taluks", "head": "revenue heads", "property": "property categories", "scheme": "schemes",
            "fy": "financial years", "month": "months", "quarter": "quarters"}[dim]
    lbl = lambda x: pretty_label(x) if dim in ("fy", "month") else str(x).replace("_", " ").capitalize() if dim == "property" else x  # noqa: E731
    vals = [r[1] for r in rows]
    hi = max(rows, key=lambda r: r[1])
    lo = min(rows, key=lambda r: r[1])
    additive = unit != "%" and all(v >= 0 for v in vals)
    total = sum(vals)
    where = "" if display == "Karnataka" else f" in {display}"
    when = "" if dim == "fy" else f" in FY {fy}"
    notes = []
    if defaulted and dim != "fy":
        notes.append(f"No financial year was named, so this uses FY {fy}, the latest complete year.")
    if dim in ("fy", "month", "quarter"):
        first, last = rows[0], rows[-1]
        if dim == "fy":
            partial_fy = load_semantic_layer()["data_period"]["partial_fy"]
            full = [r for r in rows if r[0] != partial_fy]
            if len(full) >= 2:                      # compare complete years; the part year is reported on its own
                first, last = full[0], full[-1]
                hi, lo = max(full, key=lambda r: r[1]), min(full, key=lambda r: r[1])
            d = last[1] - first[1]
            chg = (f" ({'+' if d >= 0 else ''}{d:.2f} points)" if unit == "%"
                   else f" ({'+' if d >= 0 else ''}{d / abs(first[1]) * 100:.1f}%)" if first[1] else "")
            head = f"**{label[:1].upper() + label[1:]}{where} went from {f(first[1])} in {lbl(first[0])} to {f(last[1])} in {lbl(last[0])}{chg}.**"
            body = f"It was highest in {lbl(hi[0])} ({f(hi[1])}) and lowest in {lbl(lo[0])} ({f(lo[1])})."
            part = next((r for r in rows if r[0] == partial_fy), None)
            if part:
                body += f" FY {partial_fy} so far (April to September 2026): {f(part[1])}."
        else:
            head = f"**{label[:1].upper() + label[1:]}{where}{when} was highest in {lbl(hi[0])} at {f(hi[1])}, and lowest in {lbl(lo[0])} at {f(lo[1])}.**"
            body = (f"Across the {len(rows)} {noun} it totalled {f(total)} (average {f(total / len(rows))} a {dim})." if additive and unit == "INR" or additive and unit == "count"
                    else f"The average across the {len(rows)} {noun} is {f(sum(vals) / len(vals))}.")
        return head + "\n\n" + body, notes
    # rankings and shares
    lead, tail = (lo, hi) if bottom and not top else (hi, lo)
    word = "lowest" if bottom and not top else "highest"
    if n and n < 50:
        head = f"**The {('bottom' if word == 'lowest' else 'top')} {len(rows)} {noun} by {label}{where}{when} are led by {lbl(lead[0])} at {f(lead[1])}.**"
    else:
        head = f"**{lbl(lead[0])} has the {word} {label}{where}{when}: {f(lead[1])}.**"
    if additive and dim in ("head", "property", "scheme") and total > 0:
        body = f"That is {100 * hi[1] / total:.1f}% of the {f(total)} total across {len(rows)} {noun}; {lbl(lo[0])} is smallest at {f(lo[1])}."
    elif not (n and n < 50):
        body = f"{lbl(tail[0])} is {'highest' if word == 'lowest' else 'lowest'} at {f(tail[1])}, across {len(rows)} {noun}."
    else:
        body = "; ".join(f"{lbl(r[0])} {f(r[1])}" for r in rows[1:6]) + "."
    return head + "\n\n" + body, notes


async def _staff(question: str, q: str, dim: str, metric: str, where: str, display: str, sparams: tuple, db: ReadOnlyDB,
                 timeout: float) -> Breakdown | None:
    if metric not in ("staff_active", "salary_paid", "salary_rejected"):
        return None
    col = {"staff_type": "staff_type_name", "designation": "designation_name", "zilla": "zilla_name", "taluk": "taluk_name"}[dim]
    if dim in ("zilla", "taluk") and metric != "staff_active":
        return None
    if metric == "staff_active":
        sql = (f"SELECT {col} AS {dim}, SUM(staff_count) AS staff_count FROM mart_fact_taluk_staff "
               f"WHERE employment_status = 'Active'{where} GROUP BY {col} ORDER BY staff_count DESC")
        label = "active staff"
    else:
        if dim != "staff_type":
            return None
        last = (await db.run("SELECT MAX(month_label), MAX(month_id) FROM mart_fact_taluk_salary_bills", 5, timeout)).rows[0]
        sql = (f"SELECT staff_type_name AS staff_type, SUM({'number_of_staff_salary_paid' if metric == 'salary_paid' else 'number_of_staff_salary_rejected_by_bank'}) "
               f"AS staff_count FROM mart_fact_taluk_salary_bills WHERE month_id = {int(last[1])}{where} GROUP BY staff_type_name ORDER BY staff_count DESC")
        label = "staff paid" if metric == "salary_paid" else "salaries rejected by the bank"
    qr = await db.run(sql, max_rows=200, timeout_seconds=timeout, params=sparams)
    rows = [tuple(r) for r in qr.rows if r[1]]
    if len(rows) < 2:
        return None
    total = sum(r[1] for r in rows)
    if _BOTTOM_RE.search(q) and not _TOP_RE.search(q):
        rows = sorted(rows, key=lambda r: r[1])
    n = _n(q)
    if n:
        rows = rows[:n]
    where_txt = "" if display == "Karnataka" else f" in {display}"
    most = "fewest" if rows[0][1] < rows[-1][1] else "most"
    answer = (f"**{rows[0][0]} has the {most} {label}{where_txt}: {rows[0][1]:,} of {total:,}.**\n\n"
              f"{len(rows)} {dim.replace('_', ' ')}s shown; " + "; ".join(f"{r[0]} {r[1]:,}" for r in rows[1:5]) + ".")
    cols = [dim, "staff_count"]
    return Breakdown(answer=answer, sql=_inline(sql, sparams), key=f"{dim}:{metric}", columns=cols, rows=rows,
                     table=result_table(cols, rows), chart=build_chart("bar", dim, "staff_count", label[:1].upper() + label[1:], cols, rows))

"""
Deterministic single-figure answers from the metric registry (no LLM).

Handles a question that names exactly ONE metric, at most ONE place (a GP, taluk or zilla, or Karnataka as a whole),
at most ONE financial year or month, and at most one extra filter (revenue head, property category, scheme, staff type,
designation), with no ranking / comparison / breakdown / trend wording. Example: "What was the collection in Mysuru
zilla in FY 2024-25?". Anything else returns None and moves on to the LLM path.

The SQL is assembled from reviewed registry expressions and fixed filters; the only values placed in it are bound
parameters taken from validated entities (names found in the semantic layer, period values), never user text.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.answer import fmt_inr, fmt_number
from app.db import ReadOnlyDB
from app.semantic_layer import load_semantic_layer

# extra-filter entity -> (column in the table, entity key)
_EXTRA = {"fee_types": "fee_type_name", "schemes": "scheme_name", "staff_types": "staff_type_name",
          "designations": "designation_name", "property_categories": "report_category"}


@dataclass
class MetricAnswer:
    answer: str
    sql: str
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    metric: str = ""
    final: bool = True       # False: a clarification, not a figure


def _metric(key: str) -> dict:
    return next(m for m in load_semantic_layer()["metrics"] if m["key"] == key)


def _fmt(unit: str, v) -> str:
    if v is None:
        return "no data"
    v = float(v)
    if unit == "INR":
        return fmt_inr(v)
    if unit == "%":
        return fmt_number(v, 2) + "%"
    return fmt_number(v, 0)


def _inline(sql: str, params: tuple) -> str:
    out = sql
    for p in params:
        out = out.replace("?", "'" + str(p).replace("'", "''") + "'", 1)
    return out


def _place(entities: dict) -> tuple[str, str | None, str, str | None] | None | str:
    """(level, filter column, display, value) | None when no place named | 'many' when more than one."""
    gps, taluks, zillas = entities.get("gps", []), entities.get("taluks", []), entities.get("zillas", [])
    n = len(gps) + len(taluks) + len(zillas)
    if n > 1 and not (len(gps) == 1 and len(taluks) <= 1 and len(zillas) <= 1 and gps[0].get("id")):
        return "many"
    if gps:
        g = gps[0]
        return "gp", "gp_id", f"{g['name']} GP ({g['taluk']} taluk, {g['zilla']} zilla)", g["id"]
    if taluks:
        return "taluk", "taluk_name", f"{taluks[0]} taluk", taluks[0]
    if zillas:
        return "zilla", "zilla_name", f"{zillas[0]} zilla", zillas[0]
    return None


def _default_period(metric: dict, kind: str) -> tuple[dict, str]:
    dp = load_semantic_layer()["data_period"]
    snapshot_hr = any(v["table"] in ("mart_fact_gp_eo_approval", "mart_fact_gp_er_registration") for v in metric["variants"].values())
    if kind == "month":
        return ({"kind": "month", "value": "SEP-2026", "label": "September 2026"},
                "No month was named, so September 2026, the latest month in the data, is used.")
    if snapshot_hr:
        return ({"kind": "fy", "value": dp["partial_fy"], "label": f"FY {dp['partial_fy']} (as at 30 September 2026)"},
                f"No year was named, so FY {dp['partial_fy']} (the current year, as at 30 September 2026) is used.")
    return ({"kind": "fy", "value": dp["latest_full_fy"], "label": f"FY {dp['latest_full_fy']}"},
            f"No year was named, so FY {dp['latest_full_fy']}, the latest complete year, is used.")


_MON = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


async def _calendar_year(m: dict, year: int, entities: dict, db: ReadOnlyDB, timeout: float) -> MetricAnswer | None:
    """'Collection in Mysuru in 2025': a calendar year spans two financial years. A monthly measure is summed January to
    December (and the two FYs are named); a measure kept only by financial year gives both FY figures."""
    place = _place(entities)
    if place == "many" or (place and place[0] == "gp" and m["geo"] == "taluk"):
        return None
    if any(entities.get(k) for k in _EXTRA):
        return None
    scope = place[2] if place else "Karnataka (all zillas)"
    fy_a, fy_b = f"{year - 1}-{str(year)[2:]}", f"{year}-{str(year + 1)[2:]}"
    pwhere, pparams = (f" AND {place[1]} = ?", (place[3],)) if place else ("", ())
    label = m["label"][:1].upper() + m["label"][1:]
    if "month" in m["variants"] and m["kind"] == "sum":
        v = m["variants"]["month"]
        if place and place[1] not in load_semantic_layer()["tables"][v["table"]]["columns"]:
            return None
        months = [f"{mo}-{year}" for mo in _MON]
        marks = ", ".join("?" for _ in months)
        sql = f"SELECT {v['expr']} AS value, COUNT(DISTINCT month_label) AS months FROM {v['table']} WHERE month_label IN ({marks}){pwhere}"
        params = (*months, *pparams)
        qr = await db.run(sql, max_rows=5, timeout_seconds=timeout, params=params)
        value, n = (qr.rows[0] if qr.rows else (None, 0))
        if value is None:
            return None
        span = "January to December" if n == 12 else f"the {n} months of {year} in the data"
        text = (f"**{label} for {scope} in calendar year {year} ({span}) was {_fmt(m['unit'], value)}.**\n\n"
                f"A calendar year spans two financial years: January to March {year} is in FY {fy_a} and April to December "
                f"{year} is in FY {fy_b}. Ask for a financial year (for example FY {fy_b}) for the year figure.")
        return MetricAnswer(text, _inline(sql, params), ["value", "months"], list(qr.rows), m["key"])
    if "fy" not in m["variants"]:
        return None
    v = m["variants"]["fy"]
    if place and place[1] not in load_semantic_layer()["tables"][v["table"]]["columns"]:
        return None
    sql = f"SELECT fy, {v['expr']} AS value FROM {v['table']} WHERE fy IN (?, ?){pwhere}" + \
        (f" AND {v['filter']}" if v.get("filter") else "") + " GROUP BY fy ORDER BY fy"
    params = (fy_a, fy_b, *pparams)
    qr = await db.run(sql, max_rows=5, timeout_seconds=timeout, params=params)
    if not qr.rows:
        return None
    figs = "; ".join(f"FY {r[0]}: {_fmt(m['unit'], r[1])}" for r in qr.rows)
    text = (f"**{year} is a calendar year, but {m['label']} is kept by financial year; for {scope}, {figs}.**\n\n"
            f"January to March {year} falls in FY {fy_a} and April to December {year} in FY {fy_b}. Name the financial year you mean.")
    return MetricAnswer(text, _inline(sql, params), ["fy", "value"], list(qr.rows), m["key"])


async def answer(entities: dict, db: ReadOnlyDB, timeout_seconds: float, question: str = "") -> MetricAnswer | None:
    keys = entities.get("metrics", [])
    if len(keys) != 1:
        return None
    if set(entities.get("intents", [])) & {"ranking", "comparison", "trend", "breakdown", "filter"}:
        return None
    m = _metric(keys[0])
    cal = [p for p in entities.get("periods", []) if p["kind"] == "calendar_year"]
    if cal and len(entities.get("periods", [])) == 1:
        return await _calendar_year(m, int(cal[0]["value"]), entities, db, timeout_seconds)
    periods = [p for p in entities.get("periods", []) if p["kind"] != "out_of_range"]
    if len(periods) > 1 or any(p["kind"] not in ("fy", "month") for p in periods):
        return None

    place = _place(entities)
    if place == "many":
        return None
    # --- GP name problems are answered here, deterministically
    for g in entities.get("gps", []):
        if g.get("not_found_in"):
            return MetricAnswer(f"**There is no GP named {g['name']} in {g['not_found_in']}.** Please check the spelling, or name "
                                "the taluk it belongs to.", "", metric=m["key"], final=False)
        if not g.get("id"):
            opts = "; ".join(f"{c['taluk']} taluk ({c['zilla']} zilla)" for c in g["candidates"][:12])
            return MetricAnswer(f"**There are {len(g['candidates'])} GPs named {g['name']}**: {opts}. Please say which taluk you mean.",
                                "", metric=m["key"], final=False)
    level = place[0] if place else "state"
    if level == "gp" and m["geo"] == "taluk":
        return MetricAnswer(f"**{m['label'].capitalize()} is held at taluk level only, so it cannot be given for a single GP.** "
                            "Name the taluk or zilla instead.", "", metric=m["key"], final=False)

    # --- period -> variant
    notes: list[str] = list(entities.get("place_notes", []))
    kinds = list(m["variants"].keys())
    if m.get("static") or kinds == ["none"]:
        if periods:
            return None
        period, variant_key = None, "none"
    else:
        if periods:
            period = periods[0]
            variant_key = period["kind"]
        else:
            variant_key = "fy" if "fy" in kinds else "month"
            period, note = _default_period(m, variant_key)
            notes.append(note)
        if variant_key not in kinds:
            return None

    # --- extra filters
    extras = {k: entities[k] for k in _EXTRA if entities.get(k)}
    if sum(len(v) for v in extras.values()) > 1 or any(len(v) > 1 for v in extras.values()):
        return None
    variant = m["variants"][variant_key]
    extra_sql, extra_params, extra_label = "", (), ""
    if extras:
        (ekey, evals), = extras.items()
        col, val = _EXTRA[ekey], evals[0]
        if ekey == "fee_types":
            variant = m.get("with_fee_type", {}).get(variant_key)
        elif ekey == "property_categories":
            variant = m.get("with_property_type", {}).get(variant_key)
        else:
            table_cols = load_semantic_layer()["tables"][variant["table"]]["columns"]
            variant = variant if col in table_cols else None
        if variant is None:
            return None
        table_cols = load_semantic_layer()["tables"][variant["table"]]["columns"]
        if col not in table_cols:
            return None
        extra_sql, extra_params = f" AND {col} = ?", (val,)
        extra_label = f" ({val})" if ekey != "property_categories" else f" ({val.replace('_', ' ')} properties)"

    table, expr = variant["table"], variant["expr"]
    where, params = [], []
    if variant.get("filter"):
        where.append(variant["filter"])
    if period:
        where.append("fy = ?" if variant_key == "fy" else "month_label = ?")
        params.append(period["value"])
    if place:
        if place[1] not in load_semantic_layer()["tables"][table]["columns"]:
            return None
        where.append(f"{place[1]} = ?")
        params.append(place[3])
    sql = f"SELECT {expr} AS value FROM {table}" + (" WHERE " + " AND ".join(where) if where else "") + extra_sql
    params = tuple(params) + extra_params
    qr = await db.run(sql, max_rows=5, timeout_seconds=timeout_seconds, params=params)
    value = qr.rows[0][0] if qr.rows else None
    shown_sql = _inline(sql, params)

    scope = place[2] if place else "Karnataka (all zillas)"
    if not place:
        notes.append("No zilla, taluk or GP was named, so this is the figure for the whole of Karnataka.")
    when = f" in {period['label']}" if period else " as at the end of the data (30 September 2026)"
    dp = load_semantic_layer()["data_period"]
    if period and period.get("fy") == dp["partial_fy"] and not period.get("relative"):
        notes.append(f"FY {dp['partial_fy']} is the current year: the data covers April to September 2026 only, so this is the figure so far.")
    if value is None and period and period.get("fy") and period["fy"] < dp["data_from"][:4] + "-":
        text = (f"**The data starts in April 2022 (FY 2022-23), so there is no {m['label']} figure for {scope}{when}.** "
                "Ask for any year from FY 2022-23 to FY 2026-27 (April to September 2026).")
        return MetricAnswer(text, shown_sql, ["value"], list(qr.rows), m["key"], False)
    if value is None or (m["kind"] == "ratio" and value is None):
        text = (f"**No {m['label']} figure exists for {scope}{extra_label}{when}.** The combination may not exist in the data "
                "(for example a scheme that GP does not keep).")
        return MetricAnswer(text + (" " + " ".join(notes) if notes else ""), shown_sql, ["value"], list(qr.rows), m["key"], False)
    label = m["label"][:1].upper() + m["label"][1:]
    text = f"**{label}{extra_label} for {scope}{when} was {_fmt(m['unit'], value)}.**"
    if notes:
        text += "\n\n" + " ".join(notes)
    return MetricAnswer(text, shown_sql, ["value"], list(qr.rows), m["key"])

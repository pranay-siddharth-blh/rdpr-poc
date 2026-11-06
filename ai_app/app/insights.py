"""
Read-only data for the extra pages: the Karnataka map, the GP report card, the zilla comparison and the alerts panel.
Like dashboard_data, everything comes from fixed, reviewed queries over the mart_* views the chatbot also reads
(ratios are SUM/SUM), so these pages cannot disagree with the dashboard or the chat. No person-level data is touched.
"""
from __future__ import annotations

import time

from app.config import settings
from app.dashboard_data import DashboardNotFound, build_dashboard, options
from app.db import ReadOnlyDB
from app.semantic_layer import load_semantic_layer

_CACHE: dict[tuple, tuple[float, object]] = {}
_TTL = 3600.0


async def _rows(db: ReadOnlyDB, sql: str, params: tuple = ()) -> list[tuple]:
    return (await db.run(sql, max_rows=5000, timeout_seconds=settings.rdpr_query_timeout_seconds, params=params)).rows


def _pct(num, den):
    return None if not den else round(100.0 * num / den, 2)


def _cached(db: ReadOnlyDB, key):
    """Cached per database version, so a warehouse rebuild is picked up without a restart."""
    hit = _CACHE.get((db.version, *key))
    return hit[1] if hit and time.time() - hit[0] < _TTL else None


def _store(db: ReadOnlyDB, key, value):
    _CACHE[(db.version, *key)] = (time.time(), value)
    return value


def _check_fy(fy: str | None) -> str:
    opts = options()
    fy = fy or opts["default_fy"]
    if fy not in opts["fiscal_years"]:
        raise DashboardNotFound(f"Unknown financial year {fy!r}")
    return fy


# ------------------------------------------------------------------------------------------------ map
async def map_data(db: ReadOnlyDB, fy: str | None = None) -> dict:
    """One record per zilla with the components of every map metric (the page combines them, so ratios stay SUM/SUM)."""
    fy = _check_fy(fy)
    if (hit := _cached(db, ("map", fy))):
        return hit
    z: dict[str, dict] = {r[0]: {"zilla": r[0], "gps": r[1]} for r in await _rows(db, "SELECT zilla_name, total_gps FROM mart_dim_zilla")}
    for name, coll, dem, bal in await _rows(db, "SELECT zilla_name, SUM(total_collection), SUM(total_demand), SUM(balance) FROM mart_fact_gp_dcb "
                                                "WHERE fy = ? GROUP BY zilla_name", (fy,)):
        z[name].update(collection=coll, demand=dem, balance=bal)
    for name, c, n in await _rows(db, "SELECT zilla_name, SUM(is_closed), COUNT(*) FROM mart_fact_gp_year_closure WHERE fy = ? GROUP BY zilla_name", (fy,)):
        z[name].update(books_closed=c, books=n)
    for name, c in await _rows(db, "SELECT zilla_name, SUM(all_books_closed) FROM mart_summary_gp_year WHERE fy = ? GROUP BY zilla_name", (fy,)):
        z[name].update(gps_all_closed=c)
    for name, p, a in await _rows(db, "SELECT zilla_name, SUM(staff_approval_pending_at_eo), SUM(staff_approved_by_eo) FROM mart_fact_gp_eo_approval "
                                      "WHERE fy = ? GROUP BY zilla_name", (fy,)):
        z[name].update(pending_eo=p, approved_eo=a)
    for name, s in await _rows(db, "SELECT zilla_name, SUM(staff_count) FROM mart_fact_taluk_staff WHERE employment_status = 'Active' GROUP BY zilla_name"):
        z[name].update(active_staff=s)
    out = {"fy": fy, "zillas": list(z.values()), "partial_fy": fy == options()["partial_fy"]}
    return _store(db, ("map", fy), out)


# ------------------------------------------------------------------------------------------------ GP report card
def gp_search(q: str, limit: int = 15) -> list[dict]:
    q = " ".join((q or "").lower().split())
    if len(q) < 2:
        return []
    hits = []
    for g in load_semantic_layer()["entities"]["gps"]:
        n = g["name"].lower()
        if q in n or q in g["taluk"].lower() or q in g["zilla"].lower() and len(q) > 3:
            hits.append((0 if n.startswith(q) else 1 if q in n else 2, n, g))
    hits.sort(key=lambda h: (h[0], h[1], h[2]["taluk"]))
    return [{"id": g["id"], "name": g["name"], "taluk": g["taluk"], "zilla": g["zilla"]} for _, _, g in hits[:limit]]


def _gp_known(gp_id: str) -> dict | None:
    return next((g for g in load_semantic_layer()["entities"]["gps"] if g["id"] == gp_id), None)


async def gp_card(db: ReadOnlyDB, gp_id: str, fy: str | None = None) -> dict:
    g = _gp_known(gp_id)
    if g is None:
        raise DashboardNotFound(f"Unknown GP {gp_id!r}")
    fy = _check_fy(fy)
    if (hit := _cached(db, ("gp", gp_id, fy))):
        return hit
    prof = (await _rows(db, "SELECT gp_id, gp_name, taluk_name, zilla_name, size_class, performance_tier, taluk_assignment, gp_lgd_code "
                            "FROM mart_dim_gp WHERE gp_id = ?", (gp_id,)))[0]
    profile = dict(zip(("gp_id", "name", "taluk", "zilla", "size_class", "performance_tier", "taluk_assignment", "lgd_code"), prof))

    trend = [dict(zip(("fy", "arrears", "year_demand", "total_demand", "total_collection", "adjustments", "balance"), r)) for r in await _rows(
        db, "SELECT fy, arrears, year_demand, total_demand, total_collection, adjustments, balance FROM mart_fact_gp_dcb "
            "WHERE gp_id = ? AND fy >= '2022-23' ORDER BY fy", (gp_id,))]
    for t in trend:
        t["collection_pct"] = _pct(t["total_collection"], t["total_demand"])

    ranks = await _rows(db, """
        WITH r AS (SELECT gp_id, taluk_name, zilla_name, total_collection * 100.0 / NULLIF(total_demand, 0) AS pct
                   FROM mart_fact_gp_dcb WHERE fy = ?),
             k AS (SELECT gp_id, pct,
                          RANK() OVER (ORDER BY pct DESC) AS st_rank, COUNT(*) OVER () AS st_n,
                          RANK() OVER (PARTITION BY taluk_name ORDER BY pct DESC) AS tk_rank, COUNT(*) OVER (PARTITION BY taluk_name) AS tk_n,
                          RANK() OVER (PARTITION BY zilla_name ORDER BY pct DESC) AS zl_rank, COUNT(*) OVER (PARTITION BY zilla_name) AS zl_n
                   FROM r WHERE pct IS NOT NULL)
        SELECT pct, st_rank, st_n, tk_rank, tk_n, zl_rank, zl_n FROM k WHERE gp_id = ?""", (fy, gp_id))
    rank = None
    if ranks:
        p, sr, sn, tr, tn, zr, zn = ranks[0]
        rank = {"collection_pct": round(p, 2), "state": [sr, sn], "zilla": [zr, zn], "taluk": [tr, tn]}
    peers = {}
    for label, where, params in (("taluk", "taluk_name = ?", (fy, profile["taluk"])), ("zilla", "zilla_name = ?", (fy, profile["zilla"])), ("state", "1 = 1", (fy,))):
        c, d = (await _rows(db, f"SELECT SUM(total_collection), SUM(total_demand) FROM mart_fact_gp_dcb WHERE fy = ? AND {where}", params))[0]
        peers[label] = _pct(c, d)

    monthly = [{"month": r[0], "collection": r[1]} for r in await _rows(
        db, "SELECT month_label, SUM(collection_amount) FROM mart_fact_gp_monthly_collection WHERE gp_id = ? AND fy = ? "
            "GROUP BY month_id, month_label ORDER BY month_id", (gp_id, fy))]
    heads = [dict(zip(("head", "collection", "demand"), r)) for r in await _rows(
        db, "SELECT fee_type_name, total_collection, total_demand FROM mart_fact_gp_fee_type WHERE gp_id = ? AND fy = ? "
            "ORDER BY total_collection DESC", (gp_id, fy))]
    books = [{"scheme": r[0], "closed": bool(r[1]), "closed_on": r[2]} for r in await _rows(
        db, "SELECT scheme_name, is_closed, closed_on FROM mart_fact_gp_year_closure WHERE gp_id = ? AND fy = ? ORDER BY scheme_name", (gp_id, fy))]
    closure_months = [{"month": r[0], "closed_pct": _pct(r[1], r[2])} for r in await _rows(
        db, "SELECT month_label, SUM(is_closed), COUNT(*) FROM mart_fact_gp_month_closure WHERE gp_id = ? AND fy = ? "
            "GROUP BY month_id, month_label ORDER BY month_id", (gp_id, fy))]
    money = (await _rows(db, "SELECT SUM(receipts), SUM(expenditure) FROM mart_fact_gp_scheme_financials WHERE gp_id = ? AND fy = ?", (gp_id, fy)))[0]
    last = (await _rows(db, "SELECT MAX(month_id) FROM mart_fact_gp_scheme_financials WHERE gp_id = ? AND fy = ?", (gp_id, fy)))[0][0]
    closing = (await _rows(db, "SELECT month_label, SUM(closing_balance) FROM mart_fact_gp_scheme_financials WHERE gp_id = ? AND month_id = ? "
                               "GROUP BY month_label", (gp_id, last)))[0] if last else (None, None)
    eo = (await _rows(db, "SELECT staff_registrations_sent_to_eo, staff_approved_by_eo, staff_approval_pending_at_eo, staff_registrations_rejected_by_eo, "
                          "snapshot_date FROM mart_fact_gp_eo_approval WHERE gp_id = ? AND fy = ?", (gp_id, fy)))
    er = (await _rows(db, "SELECT total_seats, total_elected_members, total_adhyaksha_president, total_upadhyaksha FROM mart_fact_gp_er_registration "
                          "WHERE gp_id = ? AND fy = ?", (gp_id, fy)))
    props = (await _rows(db, "SELECT number_of_properties, residential, commercial, industrial FROM mart_fact_gp_property_counts WHERE gp_id = ? AND fy = ?", (gp_id, fy)))

    scheme_closed = sum(1 for b in books if b["closed"])
    finance = {"books": books, "books_closed": scheme_closed, "books_total": len(books), "closure_months": closure_months,
               "receipts": money[0], "expenditure": money[1], "closing_balance": closing[1], "closing_month": closing[0]}
    hrms = {"sent_to_eo": eo[0][0] if eo else None, "approved_by_eo": eo[0][1] if eo else None, "pending_at_eo": eo[0][2] if eo else None,
            "rejected_by_eo": eo[0][3] if eo else None, "snapshot_date": eo[0][4] if eo else None,
            "seats": er[0][0] if er else None, "elected_members": er[0][1] if er else None,
            "has_president": bool(er[0][2]) if er else None, "has_vice_president": bool(er[0][3]) if er else None}
    prop = dict(zip(("total", "residential", "commercial", "industrial"), props[0])) if props else {}

    badges = []
    if rank and rank["taluk"][1] >= 5 and rank["taluk"][0] <= max(1, rank["taluk"][1] // 10):
        badges.append({"kind": "good", "key": "badge_top_taluk"})
    if rank and rank["collection_pct"] >= (peers["state"] or 0):
        badges.append({"kind": "good", "key": "badge_above_state"})
    elif rank:
        badges.append({"kind": "warn", "key": "badge_below_state"})
    if finance["books_total"] and scheme_closed == finance["books_total"]:
        badges.append({"kind": "good", "key": "badge_all_closed"})
    if hrms["pending_at_eo"]:
        badges.append({"kind": "warn", "key": "badge_pending_eo"})
    if hrms["has_president"] is False:
        badges.append({"kind": "bad", "key": "badge_no_president"})
    if hrms["seats"] and hrms["elected_members"] == hrms["seats"]:
        badges.append({"kind": "good", "key": "badge_full_house"})
    out = {"fy": fy, "partial_fy": fy == options()["partial_fy"], "profile": profile, "trend": trend, "rank": rank, "peers": peers,
           "monthly_collection": monthly, "by_head": heads, "finance": finance, "hrms": hrms, "properties": prop, "badges": badges,
           "data_as_of": options()["data_as_of"]}
    return _store(db, ("gp", gp_id, fy), out)


# ------------------------------------------------------------------------------------------------ compare two zillas
async def compare(db: ReadOnlyDB, a: str, b: str, fy: str | None = None) -> dict:
    fy = _check_fy(fy)
    if a == b:
        raise DashboardNotFound("Pick two different zillas")
    da, dbb = await build_dashboard(db, fy, a), await build_dashboard(db, fy, b)

    def pick(d: dict) -> dict:
        r, f, h = d["revenue"], d["finance"], d["hrms"]
        gps = d["gps"]
        return {"zilla": d["zilla"], "gps": gps,
                "total_demand": r["total_demand"], "total_collection": r["total_collection"], "collection_pct": r["collection_pct"],
                "balance": r["balance"], "collection_growth_pct": r["collection_growth_pct"],
                "collection_per_gp": r["total_collection"] / gps if gps else None,
                "books_closed_pct": f["books_closed_pct"], "gps_all_closed_pct": f["gps_all_closed_pct"],
                "receipts": f["receipts"], "expenditure": f["expenditure"],
                "active_staff": h["active_staff"], "staff_per_gp": h["active_staff"] / gps if gps else None,
                "pending_at_eo": h["pending_at_eo"], "seats_filled_pct": h["seats_filled_pct"],
                "monthly_collection": d["monthly_collection"], "by_head": d["by_head"], "trend": d["trend"]}
    A, B = pick(da), pick(dbb)
    # who is ahead: (key, label key, higher is better)
    metrics = [("collection_pct", "cmp_collection_pct", True), ("collection_growth_pct", "cmp_growth", True),
               ("collection_per_gp", "cmp_collection_per_gp", True), ("books_closed_pct", "cmp_books_closed", True),
               ("gps_all_closed_pct", "cmp_all_closed", True), ("seats_filled_pct", "cmp_seats_filled", True),
               ("pending_at_eo", "cmp_pending_eo", False)]
    verdicts, wins = [], {a: 0, b: 0}
    for key, label, higher in metrics:
        va, vb = A[key], B[key]
        if va is None or vb is None or va == vb:
            continue
        lead = a if (va > vb) == higher else b
        wins[lead] += 1
        verdicts.append({"metric": label, "key": key, "a": va, "b": vb, "ahead": lead})
    leader = a if wins[a] > wins[b] else b if wins[b] > wins[a] else None
    return {"fy": fy, "partial_fy": da["partial_fy"], "a": A, "b": B, "verdicts": verdicts, "wins": wins, "leader": leader,
            "data_as_of": options()["data_as_of"]}


# ------------------------------------------------------------------------------------------------ alerts
async def alerts(db: ReadOnlyDB, fy: str | None = None) -> dict:
    fy = _check_fy(fy)
    if (hit := _cached(db, ("alerts", fy))):
        return hit
    opts = options()
    partial = fy == opts["partial_fy"]
    fys = opts["fiscal_years"]
    prev_fy = fys[fys.index(fy) - 1] if fys.index(fy) > 0 else None
    items: list[dict] = []

    # 1. GPs collecting under a fifth of their demand
    rows = await _rows(db, "SELECT gp_id, gp_name, taluk_name, zilla_name, total_collection * 100.0 / total_demand AS pct FROM mart_fact_gp_dcb "
                           "WHERE fy = ? AND total_demand > 0 AND total_collection * 5.0 < total_demand ORDER BY pct ASC", (fy,))
    if rows:
        items.append({"id": "low_collection", "severity": "high" if len(rows) > 300 else "medium", "count": len(rows),
                      "unit": "gps", "threshold": 20, "items": [{"label": r[1], "sub": f"{r[2]} · {r[3]}", "value": round(r[4], 1), "fmt": "pct",
                                                                  "link": {"type": "gp", "id": r[0]}} for r in rows[:8]]})
    # 2. taluks with the biggest EO approval backlog
    rows = await _rows(db, "SELECT taluk_name, zilla_name, SUM(staff_approval_pending_at_eo) AS p FROM mart_fact_gp_eo_approval WHERE fy = ? "
                           "GROUP BY taluk_name, zilla_name HAVING p > 0 ORDER BY p DESC", (fy,))
    if rows:
        total = sum(r[2] for r in rows)
        items.append({"id": "eo_backlog", "severity": "high" if total > 200 else "medium", "count": total, "unit": "registrations",
                      "items": [{"label": r[0], "sub": r[1], "value": r[2], "fmt": "int", "link": {"type": "zilla", "name": r[1]}} for r in rows[:8]]})
    # 3. zillas collecting well below the state rate
    rows = await _rows(db, "SELECT zilla_name, SUM(total_collection), SUM(total_demand) FROM mart_fact_gp_dcb WHERE fy = ? GROUP BY zilla_name", (fy,))
    state = _pct(sum(r[1] for r in rows), sum(r[2] for r in rows))
    low = sorted(((r[0], _pct(r[1], r[2])) for r in rows if state and _pct(r[1], r[2]) is not None and _pct(r[1], r[2]) < state - 2.0), key=lambda x: x[1])
    if low:
        items.append({"id": "zilla_lag", "severity": "medium", "count": len(low), "unit": "zillas", "state_pct": state,
                      "items": [{"label": n, "sub": "", "value": v, "fmt": "pct", "link": {"type": "zilla", "name": n}} for n, v in low[:8]]})
    # 4. zillas whose collection fell against the previous FY (only complete years can be compared fairly)
    if prev_fy and not partial:
        cur = {r[0]: r[1] for r in rows}
        prv = {r[0]: r[1] for r in await _rows(db, "SELECT zilla_name, SUM(total_collection) FROM mart_fact_gp_dcb WHERE fy = ? GROUP BY zilla_name", (prev_fy,))}
        falls = sorted(((n, 100.0 * (cur[n] / prv[n] - 1)) for n in cur if prv.get(n) and cur[n] < prv[n]), key=lambda x: x[1])
        if falls:
            items.append({"id": "collection_fall", "severity": "high", "count": len(falls), "unit": "zillas", "prev_fy": prev_fy,
                          "items": [{"label": n, "sub": "", "value": round(v, 1), "fmt": "pct_signed", "link": {"type": "zilla", "name": n}} for n, v in falls[:8]]})
    # 5. months with an unusually high bank rejection rate
    rows = await _rows(db, "SELECT month_label, SUM(number_of_staff_salary_rejected_by_bank), SUM(number_of_staff_salary_paid) FROM mart_fact_taluk_salary_bills "
                           "WHERE fy = ? GROUP BY month_id, month_label ORDER BY month_id", (fy,))
    rates = [(r[0], 100.0 * r[1] / (r[1] + r[2]), r[1]) for r in rows if (r[1] + r[2]) > 0]
    if rates:
        avg = sum(x[1] for x in rates) / len(rates)
        spikes = sorted((x for x in rates if x[1] > 1.5 * avg and x[2] >= 20), key=lambda x: -x[1])
        if spikes:
            items.append({"id": "salary_spike", "severity": "medium", "count": len(spikes), "unit": "months", "avg_pct": round(avg, 2),
                          "items": [{"label": m, "sub": f"{n} rejected", "value": round(p, 2), "fmt": "pct", "link": None} for m, p, n in spikes[:6]]})
    # 6. GPs that closed none of their books for the year (complete years only)
    if not partial:
        rows = await _rows(db, "SELECT zilla_name, COUNT(*) FROM mart_summary_gp_year WHERE fy = ? AND schemes_total > 0 AND schemes_closed = 0 "
                               "GROUP BY zilla_name ORDER BY 2 DESC", (fy,))
        if rows:
            items.append({"id": "no_books_closed", "severity": "medium", "count": sum(r[1] for r in rows), "unit": "gps",
                          "items": [{"label": r[0], "sub": "", "value": r[1], "fmt": "int", "link": {"type": "zilla", "name": r[0]}} for r in rows[:8]]})
    # 7. GPs with no President registered
    rows = await _rows(db, "SELECT gp_id, gp_name, taluk_name, zilla_name FROM mart_fact_gp_er_registration WHERE fy = ? AND total_adhyaksha_president = 0 "
                           "ORDER BY zilla_name, taluk_name, gp_name", (fy,))
    if rows:
        items.append({"id": "no_president", "severity": "high" if len(rows) > 100 else "low", "count": len(rows), "unit": "gps",
                      "items": [{"label": r[1], "sub": f"{r[2]} · {r[3]}", "value": None, "fmt": "", "link": {"type": "gp", "id": r[0]}} for r in rows[:8]]})
    order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda a: (order[a["severity"]], -a["count"]))
    out = {"fy": fy, "partial_fy": partial, "alerts": items, "counts": {s: sum(1 for a in items if a["severity"] == s) for s in order},
           "data_as_of": opts["data_as_of"]}
    return _store(db, ("alerts", fy), out)


# ------------------------------------------------------------------------------------------------ insights page
def _cr(v):
    return None if v is None else round(v / 1e7, 2)


def _chg(cur, prev, pts=False):
    if cur is None or prev is None:
        return None
    if pts:
        return round(cur - prev, 2)
    return round(100.0 * (cur / prev - 1), 2) if prev else None


async def build_insights(db: ReadOnlyDB, fy: str | None = None) -> dict:
    """Key insights for one FY as KPI cards, grouped by module. Every figure is read from build_dashboard (the same
    reviewed queries as the dashboard) or from alerts(); nothing is computed differently here."""
    fy = _check_fy(fy)
    if (hit := _cached(db, ("insights", fy))):
        return hit
    d = await build_dashboard(db, fy, None)
    al = await alerts(db, fy)
    opts = options()
    partial = d["partial_fy"]
    by_fy = {s["fy"]: s for s in d["series"]["by_fy"]}
    cur, prev = by_fy.get(fy, {}), by_fy.get(d["prev_fy"] or "", {})
    upto = [s for s in d["series"]["by_fy"] if s["fy"] <= fy]
    ser = lambda k: [s.get(k) for s in upto]  # noqa: E731
    r, f, h = d["revenue"], d["finance"], d["hrms"]
    cards: list[dict] = []

    def card(group, topic, icon, value, unit, decimals, tone, text, delta=None, delta_unit="%", good_up=True, series=None):
        cards.append({"group": group, "topic": topic, "icon": icon, "value": value, "unit": unit, "decimals": decimals,
                      "tone": tone, "text": text, "delta": None if partial else delta, "delta_unit": delta_unit,
                      "good_up": good_up, "series": series})

    def tone_of(delta, good_up=True):
        if delta is None or partial:
            return "info"
        return "good" if (delta >= 0) == good_up else "bad"

    # ---- Revenue
    dp = _chg(r["collection_pct"], r["prev_collection_pct"], pts=True)
    card("Revenue", "Collection percentage", "gauge", r["collection_pct"], "%", 2, tone_of(dp),
         f"{r['collection_pct']:.2f}% of the total demand of ₹{_cr(r['total_demand']):,.2f} crore was collected in FY {fy}"
         + (f", against {r['prev_collection_pct']:.2f}% in FY {d['prev_fy']}." if r["prev_collection_pct"] is not None and not partial else "."),
         dp, "pts", True, ser("collection_pct"))
    g = r["collection_growth_pct"]
    card("Revenue", "Total collection", "up" if (g or 0) >= 0 else "down", _cr(r["total_collection"]), "₹ cr", 2, tone_of(g),
         f"₹{_cr(r['total_collection']):,.2f} crore collected across {d['gps']:,} GPs"
         + (f"; {abs(g):.1f}% {'more' if g >= 0 else 'less'} than FY {d['prev_fy']}." if g is not None and not partial
            else " (April to September only)." if partial else "."), g, "%", True, [_cr(x) for x in ser("collection")])
    db_ = _chg(cur.get("balance"), prev.get("balance"))
    card("Revenue", "Outstanding balance", "loss", _cr(r["balance"]), "₹ cr", 2, tone_of(db_, good_up=False),
         f"₹{_cr(r['balance']):,.2f} crore was still to be collected at the end of FY {fy}, including arrears carried in from earlier years.",
         db_, "%", False, [_cr(x) for x in ser("balance")])
    lg = d["league"]
    if len(lg) >= 2:
        card("Revenue", "Best zilla by collection %", "trophy", lg[0]["collection_pct"], "%", 2, "good",
             f"{lg[0]['name']} collected {lg[0]['collection_pct']:.2f}% of its demand, the highest of the 31 zillas.")
        card("Revenue", "Weakest zilla by collection %", "alert", lg[-1]["collection_pct"], "%", 2, "bad",
             f"{lg[-1]['name']} collected {lg[-1]['collection_pct']:.2f}% of its demand, the lowest of the 31 zillas.")
    tot = sum(x["collection"] or 0 for x in d["by_head"])
    pt = next((x for x in d["by_head"] if x["head"] == "Property Taxes"), None)
    if pt and tot:
        card("Revenue", "Property tax share of collection", "grid", round(100.0 * pt["collection"] / tot, 2), "%", 1, "info",
             f"Property taxes brought in ₹{_cr(pt['collection']):,.2f} crore of the ₹{_cr(tot):,.2f} crore collected under all five revenue heads.")

    # ---- Finance & Accounting
    ga = f["gps_all_closed_pct"]
    dga = _chg(cur.get("gps_all_closed_pct"), prev.get("gps_all_closed_pct"), pts=True)
    card("Finance & Accounting", "GPs that closed every book", "check", ga, "%", 2,
         "info" if partial else ("good" if (ga or 0) >= 50 else "bad"),
         f"{f['gps_all_closed']:,} of {f['gps']:,} GPs closed the year-end book of every scheme they keep"
         + (" (year-end closure for the current year has not happened yet)." if partial else "."),
         dga, "pts", True, ser("gps_all_closed_pct"))
    dbc = _chg(cur.get("books_closed_pct"), prev.get("books_closed_pct"), pts=True)
    card("Finance & Accounting", "Scheme books closed", "calendar", f["books_closed_pct"], "%", 2, tone_of(dbc),
         f"{f['books_closed_pct']:.2f}% of the {f['scheme_books']:,} scheme year-books were closed for FY {fy}.",
         dbc, "pts", True, ser("books_closed_pct"))
    sch = [s for s in f["by_scheme"] if s["closed_pct"] is not None]
    if sch and not partial:
        low = min(sch, key=lambda s: s["closed_pct"])
        card("Finance & Accounting", "Least-closed scheme book", "alert", low["closed_pct"], "%", 2, "bad",
             f"{low['scheme']} has the lowest year-end closure: {low['closed_pct']:.2f}% of its {low['books']:,} books.")
    if f["receipts"]:
        dr = _chg(cur.get("receipts"), prev.get("receipts"))
        card("Finance & Accounting", "Scheme receipts", "zap", _cr(f["receipts"]), "₹ cr", 2, "info",
             f"GPs received ₹{_cr(f['receipts']):,.2f} crore into their scheme accounts and spent ₹{_cr(f['expenditure']):,.2f} crore "
             f"({100.0 * f['expenditure'] / f['receipts']:.1f}% of receipts).", dr, "%", True, [_cr(x) for x in ser("receipts")])

    # ---- HRMS
    card("HRMS", "Active staff", "power", h["active_staff"], "staff", 0, "info",
         f"{h['active_staff']:,} GP staff are active as at {opts['data_as_of']}, across {len(h['designations'])}+ designations.")
    dpe = _chg(cur.get("pending_eo"), prev.get("pending_eo"))
    card("HRMS", "Registrations pending at the EO", "calendar", h["pending_at_eo"], "", 0,
         "bad" if (h["pending_at_eo"] or 0) > 0 else "good",
         f"{h['pending_at_eo'] or 0:,} staff registrations were waiting for the Executive Officer's approval; "
         f"{h['approved_by_eo'] or 0:,} approved and {h['rejected_by_eo'] or 0:,} rejected.", dpe, "%", False, ser("pending_eo"))
    dsf = _chg(cur.get("seats_filled_pct"), prev.get("seats_filled_pct"), pts=True)
    card("HRMS", "Elected seats filled", "check", h["seats_filled_pct"], "%", 2, "good" if (h["seats_filled_pct"] or 0) >= 95 else "bad",
         f"{h['elected_members'] or 0:,} elected members are registered against {h['seats'] or 0:,} seats in the GP bodies.",
         dsf, "pts", True, ser("seats_filled_pct"))
    if h["salary_month"] and (h["salary_paid_total"] + h["salary_rejected_total"]):
        rate = 100.0 * h["salary_rejected_total"] / (h["salary_paid_total"] + h["salary_rejected_total"])
        card("HRMS", "Salaries rejected by the bank", "alert" if rate > 0.5 else "check", round(rate, 2), "%", 2,
             "bad" if rate > 0.5 else "good",
             f"In {h['salary_month']}, the bank rejected {h['salary_rejected_total']:,} of {h['salary_paid_total'] + h['salary_rejected_total']:,} "
             "salaries processed.")

    # ---- Watch-list (the alerts panel, as cards)
    names = {"low_collection": ("GPs collecting under a fifth of demand", "down"),
             "eo_backlog": ("EO approval backlog", "calendar"),
             "zilla_lag": ("Zillas well below the state collection rate", "loss"),
             "collection_fall": ("Zillas whose collection fell", "down"),
             "salary_spike": ("Months with high salary rejections", "alert"),
             "no_books_closed": ("GPs that closed no book for the year", "alert"),
             "no_president": ("GPs without a President registered", "power")}
    for a in al["alerts"]:
        topic, icon = names.get(a["id"], (a["id"], "alert"))
        first = ", ".join(i["label"] for i in a["items"][:3])
        card("Watch-list", topic, icon, a["count"], {"gps": "GPs", "registrations": "", "zillas": "zillas", "months": "months"}.get(a["unit"], ""),
             0, "bad" if a["severity"] in ("high", "medium") else "info",
             (f"Led by {first}." if first else "") + (f" Previous year compared: FY {a['prev_fy']}." if a.get("prev_fy") else ""))

    summary = {k: sum(1 for c in cards if c["tone"] == k) for k in ("bad", "good", "info")}
    out = {"fy": fy, "prev_fy": d["prev_fy"], "is_partial": partial, "fys": d["fys"], "complete_fys": d["complete_fys"],
           "as_of": opts["data_as_of"], "cards": cards, "summary": summary, "zilla_index": d["zilla_index"]}
    return _store(db, ("insights", fy), out)

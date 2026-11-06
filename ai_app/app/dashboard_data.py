"""
Fixed, reviewed read-only queries behind the dashboard: one function builds every figure and chart of the page for a
financial year and (optionally) one zilla. The dashboard never uses the model, and every figure comes from the mart
the chatbot reads, with the same formulas (ratios are SUM/SUM), so the page and the chat cannot disagree.

Speed: the figures come from the pre-summed taluk tables (mart_agg_taluk_*: a few thousand rows; a zilla or the state
is a SUM over its taluks) and the queries of one page run concurrently on the connection pool, so a page is built in
well under a second. Results are cached per (database version, fy, zilla); every FY is pre-built at start-up.
"""
from __future__ import annotations

import asyncio
import time

from app.config import settings
from app.db import ReadOnlyDB
from app.semantic_layer import load_semantic_layer


class DashboardNotFound(ValueError):
    """Unknown financial year or zilla."""


_CACHE: dict[tuple, tuple[float, dict]] = {}
_TTL = 6 * 3600.0

# Revenue divisions of Karnataka, used only to group the zillas in the dashboard's sidebar and league filter.
DIVISIONS = {
    "Bengaluru": ["Bengaluru Urban", "Bengaluru Rural", "Bengaluru South (Ramanagara)", "Chikkaballapura", "Chitradurga",
                  "Davanagere", "Kolar", "Shivamogga", "Tumakuru"],
    "Mysuru": ["Chamarajanagar", "Chikkamagaluru", "Dakshina Kannada", "Hassan", "Kodagu", "Mandya", "Mysuru", "Udupi"],
    "Belagavi": ["Bagalkot", "Belagavi", "Dharwad", "Gadag", "Haveri", "Uttara Kannada", "Vijayapura"],
    "Kalaburagi": ["Ballari", "Bidar", "Kalaburagi", "Koppal", "Raichur", "Vijayanagara", "Yadgir"],
}
_DIVISION_OF = {z: d for d, zs in DIVISIONS.items() for z in zs}


def options() -> dict:
    ents = load_semantic_layer()["entities"]
    dp = load_semantic_layer()["data_period"]
    return {"fiscal_years": [fy for fy in ents["fiscal_years"]], "default_fy": dp["latest_full_fy"],
            "zillas": [z["name"] for z in sorted(ents["zillas"], key=lambda z: z["name"])], "data_as_of": dp["data_as_of"],
            "partial_fy": dp["partial_fy"]}


async def _rows(db: ReadOnlyDB, sql: str, params: tuple = ()) -> list[tuple]:
    qr = await db.run(sql, max_rows=5000, timeout_seconds=settings.rdpr_query_timeout_seconds, params=params)
    return qr.rows


def _pct(num, den):
    return None if not den or num is None else round(100.0 * num / den, 2)


def _fy_month(month_id: int) -> int:
    """April = 1 ... March = 12."""
    return (month_id % 100 - 4) % 12 + 1


def cached(db: ReadOnlyDB, key: tuple):
    hit = _CACHE.get((db.version, *key))
    return hit[1] if hit and time.time() - hit[0] < _TTL else None


def store(db: ReadOnlyDB, key: tuple, value):
    _CACHE[(db.version, *key)] = (time.time(), value)
    return value


async def build_dashboard(db: ReadOnlyDB, fy: str | None = None, zilla: str | None = None) -> dict:
    opts = options()
    fy = fy or opts["default_fy"]
    if fy not in opts["fiscal_years"]:
        raise DashboardNotFound(f"Unknown financial year {fy!r}")
    if zilla and zilla not in opts["zillas"]:
        raise DashboardNotFound(f"Unknown zilla {zilla!r}")
    if (hit := cached(db, ("dash", fy, zilla or ""))):
        return hit

    z = " AND zilla_name = ?" if zilla else ""
    zp = (zilla,) if zilla else ()
    fys = opts["fiscal_years"]
    prev_fy = fys[fys.index(fy) - 1] if fys.index(fy) > 0 else None
    pf = prev_fy or "-"
    place = "taluk_name" if zilla else "zilla_name"
    q = {
        "dcb": ("SELECT fy, SUM(arrears), SUM(year_demand), SUM(total_demand), SUM(total_collection), SUM(adjustments), SUM(balance), "
                "SUM(scheme_books_closed), SUM(scheme_books), SUM(gps_all_books_closed), SUM(total_gps), SUM(receipts), SUM(expenditure), "
                "SUM(staff_registrations_sent_to_eo), SUM(staff_approved_by_eo), SUM(staff_approval_pending_at_eo), "
                "SUM(staff_registrations_rejected_by_eo), SUM(total_seats), SUM(total_elected_members), SUM(total_adhyaksha_president), "
                f"SUM(number_of_properties) FROM mart_agg_taluk_fy WHERE 1 = 1{z} GROUP BY fy ORDER BY fy", zp),
        "months": ("SELECT fy, month_id, month_label, SUM(collection_amount), SUM(receipts), SUM(expenditure), SUM(closing_balance), "
                   "SUM(month_books_closed), SUM(month_books), SUM(number_of_staff_salary_paid), SUM(number_of_staff_salary_rejected_by_bank), "
                   f"SUM(total_number_of_staff) FROM mart_agg_taluk_month WHERE fy IN (?, ?){z} GROUP BY fy, month_id, month_label ORDER BY month_id",
                   (fy, pf, *zp)),
        "heads": ("SELECT fee_type_name, SUM(total_collection), SUM(total_demand), SUM(balance) FROM mart_agg_taluk_fee_type_fy "
                  f"WHERE fy = ?{z} GROUP BY fee_type_name ORDER BY SUM(total_collection) DESC", (fy, *zp)),
        "league": (f"SELECT {place}, fy, SUM(total_collection), SUM(total_demand), SUM(total_gps), SUM(scheme_books_closed), "
                   "SUM(scheme_books), SUM(gps_all_books_closed), SUM(receipts), SUM(expenditure), SUM(staff_approval_pending_at_eo), "
                   "SUM(staff_approved_by_eo), SUM(total_elected_members), SUM(total_seats) FROM mart_agg_taluk_fy "
                   f"WHERE fy IN (?, ?){z} GROUP BY {place}, fy", (fy, pf, *zp)),
        "prop": ("SELECT report_category, SUM(total_demand), SUM(total_collection), SUM(balance) FROM mart_agg_taluk_property_fy "
                 f"WHERE fy = ?{z} GROUP BY report_category ORDER BY SUM(total_demand) DESC", (fy, *zp)),
        "scheme": ("SELECT scheme_name, SUM(scheme_books_closed), SUM(scheme_books), SUM(receipts), SUM(expenditure) FROM mart_agg_taluk_scheme_fy "
                   f"WHERE fy = ?{z} GROUP BY scheme_name ORDER BY scheme_name", (fy, *zp)),
        "staff": ("SELECT designation_name, staff_type_name, gender, SUM(staff_count) FROM mart_fact_taluk_staff "
                  f"WHERE employment_status = 'Active'{z} GROUP BY designation_name, staff_type_name, gender", zp),
        "salary_last": (f"SELECT MAX(month_id) FROM mart_fact_taluk_salary_bills WHERE fy = ?{z}", (fy, *zp)),
        "watch": ("SELECT gp_id, gp_name, taluk_name, zilla_name, total_collection, total_demand, balance, "
                  f"total_collection * 100.0 / total_demand AS pct FROM mart_fact_gp_dcb WHERE fy = ? AND total_demand > 0{z} "
                  "ORDER BY pct ASC LIMIT 5", (fy, *zp)),
        "watch_n": (f"SELECT COUNT(*) FROM mart_fact_gp_dcb WHERE fy = ? AND total_demand > 0 AND total_collection * 5.0 < total_demand{z}", (fy, *zp)),
        "zillas": ("SELECT zilla_name, total_taluks, total_gps FROM mart_dim_zilla ORDER BY zilla_name", ()),
        "place_staff": (f"SELECT {place}, SUM(staff_count) FROM mart_fact_taluk_staff WHERE employment_status = 'Active'{z} GROUP BY {place}", zp),
    }
    res = dict(zip(q, await asyncio.gather(*(_rows(db, sql, p) for sql, p in q.values()))))
    sal_month = res["salary_last"][0][0]
    funnel_rows = await _rows(
        db, "SELECT staff_type_name, SUM(total_number_of_staff), SUM(number_of_main_bill_generated), SUM(number_of_main_bill_pdo_signed), "
            "SUM(number_of_main_bill_president_signed), SUM(number_of_main_bill_processed_by_bank), SUM(number_of_staff_salary_paid), "
            f"SUM(number_of_staff_salary_rejected_by_bank) FROM mart_fact_taluk_salary_bills WHERE month_id = ?{z} "
            "GROUP BY staff_type_name ORDER BY SUM(total_number_of_staff) DESC", (sal_month, *zp)) if sal_month else []

    # ---------------------------------------------------------------- per-FY series (sparklines, five-year view, KPI deltas)
    keys = ("fy", "arrears", "year_demand", "total_demand", "total_collection", "adjustments", "balance", "scheme_books_closed",
            "scheme_books", "gps_all_closed", "gps", "receipts", "expenditure", "sent_eo", "approved_eo", "pending_eo", "rejected_eo",
            "seats", "members", "presidents", "properties")
    by_fy = {r[0]: dict(zip(keys, r)) for r in res["dcb"]}
    for s in by_fy.values():
        s.update(collection=s["total_collection"], demand=s["total_demand"], collection_pct=_pct(s["total_collection"], s["total_demand"]),
                 books_closed_pct=_pct(s["scheme_books_closed"], s["scheme_books"]), gps_all_closed_pct=_pct(s["gps_all_closed"], s["gps"]),
                 seats_filled_pct=_pct(s["members"], s["seats"]))
    cur, prv = by_fy.get(fy, {}), by_fy.get(prev_fy or "", {})
    g = lambda d, k: d.get(k)  # noqa: E731

    revenue = {"arrears": g(cur, "arrears"), "year_demand": g(cur, "year_demand"), "total_demand": g(cur, "total_demand"),
               "total_collection": g(cur, "total_collection"), "adjustments": g(cur, "adjustments"), "balance": g(cur, "balance"),
               "collection_pct": g(cur, "collection_pct"), "prev_fy": prev_fy, "prev_collection": g(prv, "total_collection"),
               "prev_collection_pct": g(prv, "collection_pct"),
               "collection_growth_pct": round(100.0 * (cur["total_collection"] / prv["total_collection"] - 1), 2)
               if prv.get("total_collection") and cur.get("total_collection") is not None else None}
    trend = [{"fy": f, "total_collection": s["total_collection"], "total_demand": s["total_demand"], "year_demand": s["year_demand"],
              "collection_pct": s["collection_pct"]} for f, s in sorted(by_fy.items()) if f >= "2022-23"]

    # ---------------------------------------------------------------- months of this FY, aligned with the previous FY on the fiscal month
    mcur = {r[1]: r for r in res["months"] if r[0] == fy}
    mprv = {_fy_month(r[1]): r for r in res["months"] if r[0] == prev_fy}
    months, monthly, closure_months, salary_trend = [], [], [], []
    for mid in sorted(mcur):
        r = mcur[mid]
        p = mprv.get(_fy_month(mid))
        months.append({"m": _fy_month(mid), "label": r[2], "collection": r[3], "collection_prev": p[3] if p else None,
                       "receipts": r[4], "receipts_prev": p[4] if p else None, "expenditure": r[5],
                       "paid": r[9], "paid_prev": p[9] if p else None, "staff": r[11], "rejected": r[10]})
        if r[3] is not None:
            monthly.append({"month": r[2], "collection": r[3]})
        if r[8]:
            closure_months.append({"month": r[2], "closed_pct": _pct(r[7], r[8])})
        if r[9] is not None:
            salary_trend.append({"month": r[2], "paid": r[9], "rejected": r[10]})
    money_months = [r for r in (mcur[m] for m in sorted(mcur)) if r[6] is not None]
    closing = (money_months[-1][2], money_months[-1][6]) if money_months else (None, None)
    months = [m for m in months if m["collection"] is not None or m["receipts"] is not None]

    by_head = [{"head": r[0], "collection": r[1], "demand": r[2], "balance": r[3], "collection_pct": _pct(r[1], r[2])} for r in res["heads"]]
    lc = {(r[0], r[1]): r for r in res["league"]}
    place_staff = {r[0]: r[1] for r in res["place_staff"]}
    league = []
    for (name, f), r in lc.items():
        if f != fy:
            continue
        pc = lc.get((name, prev_fy), (None, None, None))[2]
        league.append({"name": name, "collection": r[2], "demand": r[3], "collection_pct": _pct(r[2], r[3]), "gps": r[4],
                       "prev_collection": pc, "balance": (r[3] or 0) - (r[2] or 0),
                       # a part year against a full year is not a like-for-like change, so none is shown for the current FY
                       "yoy": round(100.0 * (r[2] / pc - 1), 2) if pc and r[2] is not None and fy != opts["partial_fy"] else None,
                       "division": None if zilla else _DIVISION_OF.get(name),
                       # Finance and HRMS columns for the module views of the dashboard and the map
                       "books_closed_pct": _pct(r[5], r[6]), "scheme_books": r[6], "gps_all_closed": r[7],
                       "gps_all_closed_pct": _pct(r[7], r[4]), "receipts": r[8], "expenditure": r[9], "pending_at_eo": r[10],
                       "approved_by_eo": r[11], "seats_filled_pct": _pct(r[12], r[13]), "active_staff": place_staff.get(name, 0)})
    league.sort(key=lambda r: -(r["collection_pct"] or 0))
    by_property = [dict(zip(("category", "demand", "collection", "balance"), r)) for r in res["prop"]]

    by_scheme = [{"scheme": r[0], "closed_pct": _pct(r[1], r[2]), "books": r[2]} for r in res["scheme"] if r[2]]
    scheme_money = sorted([{"scheme": r[0], "receipts": r[3], "expenditure": r[4]} for r in res["scheme"]], key=lambda x: -(x["receipts"] or 0))
    finance = {"books_closed_pct": g(cur, "books_closed_pct"), "scheme_books": g(cur, "scheme_books"), "gps_all_closed": g(cur, "gps_all_closed"),
               "gps": g(cur, "gps"), "gps_all_closed_pct": g(cur, "gps_all_closed_pct"), "receipts": g(cur, "receipts"),
               "expenditure": g(cur, "expenditure"), "closing_balance": closing[1], "closing_month": closing[0], "by_scheme": by_scheme,
               "closure_months": closure_months, "scheme_money": scheme_money}

    staff = res["staff"]
    agg = lambda i: sorted(((k, sum(r[3] for r in staff if r[i] == k)) for k in {r[i] for r in staff}), key=lambda x: -x[1])  # noqa: E731
    funnel = [dict(zip(("type", "staff", "bills_generated", "pdo_signed", "president_signed", "bank_processed", "paid", "rejected"), r))
              for r in funnel_rows]
    hrms = {"active_staff": sum(r[3] for r in staff), "sent_to_eo": g(cur, "sent_eo"), "approved_by_eo": g(cur, "approved_eo"),
            "pending_at_eo": g(cur, "pending_eo"), "rejected_by_eo": g(cur, "rejected_eo"), "seats": g(cur, "seats"),
            "elected_members": g(cur, "members"), "seats_filled_pct": g(cur, "seats_filled_pct"), "gps_with_president": g(cur, "presidents"),
            "gps_reporting": g(cur, "gps"),
            "designations": [{"designation": k, "staff": v} for k, v in agg(0)[:10]],
            "staff_types": [{"type": k, "staff": v} for k, v in agg(1)], "gender": dict(agg(2)),
            "salary_month": salary_trend[-1]["month"] if salary_trend else None, "salary_funnel": funnel, "salary_trend": salary_trend,
            "salary_rejected_total": sum(f["rejected"] or 0 for f in funnel), "salary_paid_total": sum(f["paid"] or 0 for f in funnel)}

    zillas = [{"zilla": r[0], "taluks": r[1], "gps": r[2], "division": _DIVISION_OF.get(r[0], "Other")} for r in res["zillas"]]
    gps = next((x["gps"] for x in zillas if x["zilla"] == zilla), None) if zilla else sum(x["gps"] for x in zillas)
    partial = fy == opts["partial_fy"]
    out = {"fy": fy, "zilla": zilla, "scope": zilla or "Karnataka", "gps": gps, "partial_fy": partial,
           "data_as_of": opts["data_as_of"], "revenue": revenue, "trend": trend, "monthly_collection": monthly,
           "by_head": by_head, "league": league, "league_label": "taluk" if zilla else "zilla", "by_property": by_property,
           "finance": finance, "hrms": hrms,
           "observations": _observations(fy, zilla, revenue, finance, hrms, league, "taluk" if zilla else "zilla", partial),
           "fys": fys, "complete_fys": [f for f in fys if f != opts["partial_fy"]], "prev_fy": prev_fy, "months": months,
           "series": {"by_fy": [by_fy.get(f, {"fy": f}) for f in fys]},
           "watch": [dict(zip(("gp_id", "gp", "taluk", "zilla", "collection", "demand", "balance", "pct"), r)) for r in res["watch"]],
           "watch_count": res["watch_n"][0][0], "zilla_index": zillas, "division": _DIVISION_OF.get(zilla) if zilla else None}
    return store(db, ("dash", fy, zilla or ""), out)


async def warm(db: ReadOnlyDB) -> None:
    """Pre-build every FY statewide and every zilla for the default FY, so no visitor waits for a cold page."""
    opts = options()
    for fy in opts["fiscal_years"]:
        await build_dashboard(db, fy, None)
    for z in opts["zillas"]:
        await build_dashboard(db, opts["default_fy"], z)


def _observations(fy, zilla, rev, fin, hrms, league, league_label, partial) -> list[str]:
    out = []
    if rev["collection_pct"] is not None:
        txt = f"{rev['collection_pct']:.1f}% of the total demand was collected in FY {fy}"
        if rev["collection_growth_pct"] is not None:
            txt += f"; collection is {abs(rev['collection_growth_pct']):.1f}% {'higher' if rev['collection_growth_pct'] >= 0 else 'lower'} than FY {rev['prev_fy']}"
        out.append(txt + ".")
    if len(league) >= 2:
        out.append(f"Highest collection percentage by {league_label}: {league[0]['name']} ({league[0]['collection_pct']:.1f}%); "
                   f"lowest: {league[-1]['name']} ({league[-1]['collection_pct']:.1f}%).")
    if fin["gps_all_closed_pct"] is not None:
        out.append(f"{fin['gps_all_closed']:,} of {fin['gps']:,} GPs ({fin['gps_all_closed_pct']:.1f}%) closed every scheme book for the year"
                   + (" (year-end closure for the current year has not happened yet)." if partial else "."))
    if hrms["pending_at_eo"]:
        out.append(f"{hrms['pending_at_eo']:,} staff registrations are still pending at the EO.")
    if hrms["salary_month"] and hrms["salary_rejected_total"]:
        out.append(f"In {_month_name(hrms['salary_month'])}, the bank rejected {hrms['salary_rejected_total']:,} salaries "
                   f"({hrms['salary_rejected_total'] * 100.0 / max(1, hrms['salary_paid_total'] + hrms['salary_rejected_total']):.2f}% of those processed).")
    return out


_MONTHS = {"JAN": "January", "FEB": "February", "MAR": "March", "APR": "April", "MAY": "May", "JUN": "June", "JUL": "July",
           "AUG": "August", "SEP": "September", "OCT": "October", "NOV": "November", "DEC": "December"}


def _month_name(label: str) -> str:
    mon, year = label.split("-")
    return f"{_MONTHS[mon]} {year}"

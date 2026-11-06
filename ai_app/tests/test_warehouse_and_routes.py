"""The staged warehouse build, the pre-summed taluk tables, the reviewed breakdowns and situation reports, and the
per-answer Excel report. Every figure is checked against the GP-level fact tables, not the tables the bot reads."""
import io
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app import dashboard_data
from conftest import run


@pytest.fixture(scope="module")
def raw():
    con = sqlite3.connect(f"file:{settings.db_path.as_posix()}?mode=ro", uri=True)
    yield con
    con.close()


def one(raw, sql, *params):
    return raw.execute(sql, params).fetchone()


# ---------------------------------------------------------------- warehouse ledger
def test_last_build_passed_every_check(raw):
    failed = raw.execute("SELECT name, expected, actual FROM ledger_build_check WHERE status != 'PASS'").fetchall()
    assert not failed, failed
    assert one(raw, "SELECT COUNT(*) FROM ledger_build_check")[0] >= 30
    assert one(raw, "SELECT COUNT(*) FROM ledger_column")[0] > 300          # column lineage was recorded
    assert one(raw, "SELECT COUNT(*) FROM ledger_issue")[0] == 10


def test_every_mart_table_is_a_physical_table(raw):
    kinds = dict(raw.execute("SELECT name, type FROM sqlite_master WHERE name LIKE 'mart_%' AND type IN ('table', 'view')").fetchall())
    assert len(kinds) == 31 and set(kinds.values()) == {"table"}


@pytest.mark.parametrize("fy", ["2022-23", "2023-24", "2024-25", "2025-26", "2026-27"])
def test_pre_summed_taluk_tables_equal_the_gp_facts(raw, fy):
    fy_id = "FY" + fy[2:4] + fy[5:7]
    agg = one(raw, "SELECT SUM(total_demand), SUM(total_collection), SUM(scheme_books_closed), SUM(scheme_books) FROM mart_agg_taluk_fy WHERE fy = ?", fy)
    dcb = one(raw, "SELECT SUM(total_demand), SUM(total_collection) FROM fact_rev_dcb_register WHERE fy_id = ?", fy_id)
    books = one(raw, "SELECT SUM(is_closed), COUNT(*) FROM fact_fin_gp_year_closure WHERE fy_id = ?", fy_id)
    assert abs(agg[0] - dcb[0]) < 1 and abs(agg[1] - dcb[1]) < 1 and (agg[2], agg[3]) == books
    month = one(raw, "SELECT SUM(collection_amount) FROM mart_agg_taluk_month WHERE fy = ?", fy)[0]
    gp_month = one(raw, "SELECT SUM(collection_amount) FROM mart_fact_gp_monthly_collection WHERE fy = ?", fy)[0]
    assert abs(month - gp_month) < 1


# ---------------------------------------------------------------- dashboard speed and every year
@pytest.mark.parametrize("fy", ["2022-23", "2023-24", "2024-25", "2025-26", "2026-27"])
def test_every_year_has_its_own_dashboard(db, raw, fy):
    d = run(dashboard_data.build_dashboard(db, fy))
    fy_id = "FY" + fy[2:4] + fy[5:7]
    coll = one(raw, "SELECT SUM(total_collection) FROM fact_rev_dcb_register WHERE fy_id = ?", fy_id)[0]
    assert d["fy"] == fy and abs(d["revenue"]["total_collection"] - coll) < 1


# ---------------------------------------------------------------- reviewed breakdowns and situation reports
def test_month_breakdown_matches_the_gp_facts(ask, raw):
    r = ask("Collection by month in Mysuru zilla in 2024-25")
    assert r.route == "breakdown:month:total_collection" and len(r.rows) == 12 and r.chart
    top = one(raw, "SELECT month_label, SUM(collection_amount) s FROM mart_fact_gp_monthly_collection "
                   "WHERE fy = '2024-25' AND zilla_name = 'Mysuru' GROUP BY month_label ORDER BY s DESC LIMIT 1")
    assert r.answer.startswith("**") and "₹21.12 crore" in r.answer and abs(top[1] / 1e7 - 21.12) < 0.005


def test_zilla_ranking_is_answered_without_the_model(ask, raw):
    r = ask("Which zilla had the lowest collection percentage in 2025-26?")
    low = one(raw, "SELECT z.zilla_name, SUM(total_collection)*100.0/SUM(total_demand) p FROM fact_rev_dcb_register r JOIN dim_gp g "
                   "USING(gp_id) JOIN dim_zilla z USING(zilla_id) WHERE fy_id = 'FY2526' GROUP BY 1 ORDER BY p LIMIT 1")
    assert r.route.startswith("breakdown:zilla") and f"**{low[0]} " in r.answer and f"{low[1]:.2f}%" in r.answer


def test_scorecard_ranks_every_zilla(ask):
    r = ask("Rank all zillas for FY 2024-25")
    assert r.route == "report:scorecard:state" and len(r.rows) == 31 and r.chart
    pcts = [row[1] for row in r.rows]
    assert pcts == sorted(pcts, reverse=True)


def test_book_closure_situation(ask, raw):
    r = ask("Show me the book closure situation in Mysuru zilla for 2024-25")
    closed, total = one(raw, "SELECT SUM(c.is_closed), COUNT(*) FROM fact_fin_gp_year_closure c JOIN dim_gp g USING(gp_id) "
                             "JOIN dim_zilla z USING(zilla_id) WHERE fy_id = 'FY2425' AND z.zilla_name = 'Mysuru'")
    assert r.route == "report:closure" and f"{100 * closed / total:.2f}%" in r.answer and f"{total:,}" in r.answer


def test_salary_situation_uses_the_latest_month(ask, raw):
    r = ask("What is the salary bill situation?")
    paid, staff = one(raw, "SELECT SUM(number_of_staff_salary_paid), SUM(total_number_of_staff) FROM mart_fact_taluk_salary_bills "
                           "WHERE month_id = (SELECT MAX(month_id) FROM mart_fact_taluk_salary_bills)")
    assert r.route == "report:salary" and f"{paid:,} of {staff:,}" in r.answer
    assert r.answer.count("taluk level") == 1          # the caveat is said once


def test_two_year_comparison_for_one_place(ask):
    r = ask("Compare Mysuru zilla in 2023-24 and 2024-25")
    assert r.route == "report:period_compare:zilla" and [row[0] for row in r.rows] == ["2023-24", "2024-25"]
    assert "₹124.30 crore" in r.answer and "₹109.42 crore" in r.answer


def test_revenue_answers_do_not_carry_the_salary_caveat(ask):
    assert "Salary bills" not in ask("Collection by month in Mysuru zilla in 2024-25").answer


# ---------------------------------------------------------------- per-answer Excel report
def test_answer_report_downloads_with_the_answer_and_data():
    import openpyxl
    from app.main import app
    with TestClient(app) as c:
        j = c.post("/api/ask_once", json={"question": "Collection by month in Mysuru zilla in 2024-25"}).json()
        rid = j["report_id"]
        assert rid
        v = c.get(f"/api/answer-report/{rid}/view")
        assert v.status_code == 200 and [s["name"] for s in v.json()["sheets"]][:2] == ["Report", "Data"]
        x = c.get(f"/api/answer-report/{rid}")
        assert x.status_code == 200 and ".xlsx" in x.headers["content-disposition"]
        wb = openpyxl.load_workbook(io.BytesIO(x.content))
        assert wb.sheetnames[:2] == ["Report", "Data"] and wb["Data"].max_row >= 13
        assert c.get("/api/answer-report/does-not-exist").status_code == 404


# ---------------------------------------------------------------- result guard: a count larger than what exists
def test_a_count_of_places_cannot_exceed_the_places_in_scope():
    from app.guardrails import count_exceeds_scope
    q = "How many taluks in Kalaburagi zilla collected more than 30% of their demand in FY 2024-25?"
    ent = {"zillas": ["Kalaburagi"]}
    assert count_exceeds_scope(q, ent, ["taluks"], [(33,)])          # Kalaburagi has 11 taluks
    assert count_exceeds_scope(q, ent, ["taluks"], [(3,)]) is None
    assert count_exceeds_scope("How many zillas are below 27%?", {}, ["n"], [(40,)])
    assert count_exceeds_scope("How many GPs in Badami taluk had no president?", {"taluks": ["Badami"]}, ["n"], [(2,)]) is None


# ---------------------------------------------------------------- dashboard module views and map: per-place figures
@pytest.mark.parametrize("zilla", [None, "Mysuru"])
def test_league_rows_carry_finance_and_hrms_figures_that_add_up(db, zilla):
    d = run(dashboard_data.build_dashboard(db, "2024-25", zilla))
    rows, f, h = d["league"], d["finance"], d["hrms"]
    assert sum(r["receipts"] for r in rows) == f["receipts"] and sum(r["expenditure"] for r in rows) == f["expenditure"]
    assert sum(r["scheme_books"] for r in rows) == f["scheme_books"] and sum(r["gps_all_closed"] for r in rows) == f["gps_all_closed"]
    assert sum(r["pending_at_eo"] for r in rows) == h["pending_at_eo"] and sum(r["approved_by_eo"] for r in rows) == h["approved_by_eo"]
    assert sum(r["active_staff"] for r in rows) == h["active_staff"]
    assert all(0 <= r["books_closed_pct"] <= 100 and 0 <= r["seats_filled_pct"] <= 100 for r in rows)


def test_every_zilla_outline_on_the_map_is_a_zilla():
    import json
    from pathlib import Path
    geo = json.loads((Path(__file__).resolve().parents[1] / "app" / "static" / "ka_zillas.json").read_text(encoding="utf-8"))
    names = {f["properties"]["name"] for f in geo["features"]}
    zillas = set(dashboard_data.options()["zillas"])
    # every zilla has its own outline, Vijayanagara (formed 2021) included
    assert names == zillas and len(geo["features"]) == 31

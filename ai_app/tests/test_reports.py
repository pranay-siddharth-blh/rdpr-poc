"""
The deterministic report route (app.reports): broad questions must be answered by reviewed code, with figures that
agree with independently written SQL over the base facts -- not with the summary views the reports themselves read.
"""
import pytest

from app import reports
from app.semantic_layer import extract_entities
from conftest import run


def rep(db, question):
    return run(reports.report(question, extract_entities(question), db, 60))


# ---- routing: these questions must NOT reach the model
@pytest.mark.parametrize("question, key", [
    ("Overall performance of Mysuru zilla in 2024-25", "overview:zilla"),
    ("Summary of FY 2024-25", "overview:state"),
    ("How is Karnataka doing overall?", "overview:state"),
    ("Give me a report card for Mysuru zilla", "overview:zilla"),
    ("Which taluks need attention in 2025-26?", "needs_attention:taluk"),
    ("Which GPs are at risk in Bagalkot taluk?", "needs_attention:gp"),
    ("Compare Mysuru and Belagavi in 2024-25", "compare:zilla"),
])
def test_broad_questions_are_answered_deterministically(db, question, key):
    r = rep(db, question)
    assert r is not None, f"{question!r} fell through to the model path"
    assert r.key == key
    assert r.answer.startswith("**")


# ---- these must be left to the model: a report would answer about the wrong measure or grain
@pytest.mark.parametrize("question", [
    "Overall salary bills in Mysuru zilla in 2024-25",        # measure not covered
    "Performance of Mysuru zilla by scheme in 2024-25",       # measure not covered
    "Summary of collection by month in 2024-25",              # month grain
    "Overall performance trend for Mysuru zilla",             # trend intent
    "What was the total collection in Mysuru zilla in FY 2024-25?",   # single metric, not broad
])
def test_out_of_scope_questions_fall_through(db, question):
    assert rep(db, question) is None


# ---- a defaulted period is always stated
def test_default_period_is_stated(db):
    r = rep(db, "Give me a report card for Mysuru zilla")
    assert any("no financial year was named" in n.lower() for n in r.notes)


def test_named_period_is_not_flagged_as_defaulted(db):
    r = rep(db, "Overall performance of Mysuru zilla in 2024-25")
    assert not any("no financial year was named" in n.lower() for n in r.notes)


# ---- figures agree with independent SQL over the base facts
def test_overview_figures_match_the_base_facts(db):
    r = rep(db, "Overall performance of Mysuru zilla in 2024-25")
    independent = run(db.run(
        "SELECT SUM(total_demand), SUM(total_collection), SUM(balance) FROM mart_fact_gp_dcb "
        "WHERE fy = '2024-25' AND zilla_name = 'Mysuru'", max_rows=5, timeout_seconds=60)).rows[0]
    v = dict(zip(r.columns, r.rows[0]))
    assert round(v["total_demand"], 2) == round(independent[0], 2)
    assert round(v["total_collection"], 2) == round(independent[1], 2)
    assert round(v["revenue_balance"], 2) == round(independent[2], 2)
    # the ratio in the text is SUM/SUM of those two figures, not an average of stored percentages
    assert f"{100.0 * independent[1] / independent[0]:.2f}%" in r.answer


def test_state_overview_matches_the_base_facts(db):
    r = rep(db, "Summary of FY 2024-25")
    independent = run(db.run("SELECT SUM(total_demand), SUM(total_collection) FROM mart_fact_gp_dcb "
                             "WHERE fy = '2024-25'", max_rows=5, timeout_seconds=60)).rows[0]
    v = dict(zip(r.columns, r.rows[0]))
    assert round(v["total_demand"], 2) == round(independent[0], 2)
    assert round(v["total_collection"], 2) == round(independent[1], 2)


def test_closure_count_matches_the_base_closure_fact(db):
    r = rep(db, "Summary of FY 2024-25")
    independent = run(db.run(
        "SELECT COUNT(*) FROM (SELECT gp_id, MIN(is_closed) m FROM mart_fact_gp_year_closure "
        "WHERE fy = '2024-25' GROUP BY gp_id) WHERE m = 1", max_rows=5, timeout_seconds=60)).rows[0][0]
    assert dict(zip(r.columns, r.rows[0]))["gps_all_books_closed"] == independent


# ---- ranking correctness
def test_needs_attention_is_ordered_worst_first_and_excludes_zero_demand(db):
    r = rep(db, "Which taluks need attention in 2025-26?")
    pcts = [row[1] for row in r.rows]
    assert pcts == sorted(pcts), "the weakest must come first"
    assert all(row[2] and row[2] > 0 for row in r.rows), "a place with no demand has no meaningful collection %"


def test_needs_attention_respects_a_named_parent_place(db):
    r = rep(db, "Which GPs are at risk in Bagalkot taluk?")
    assert "Bagalkot taluk" in r.answer
    names = {row[0] for row in r.rows}
    inside = {x[0] for x in run(db.run("SELECT gp_name FROM mart_summary_gp_year WHERE taluk_name = 'Bagalkot'",
                                      max_rows=1000, timeout_seconds=60)).rows}
    assert names <= inside, "the report listed GPs from outside the named taluk"


def test_compare_lists_every_named_place(db):
    r = rep(db, "Compare Mysuru and Belagavi in 2024-25")
    assert {row[0] for row in r.rows} == {"Mysuru", "Belagavi"}


# ---- the route is reachable through the whole pipeline, with the right route stamp
def test_pipeline_stamps_the_report_route(ask):
    res = ask("Overall performance of Mysuru zilla in 2024-25")
    assert res.answerable
    assert res.route == "report:overview:zilla"
    assert res.rows and res.sql.startswith("SELECT")
    # a one-row overview needs no table: every figure is already in the text (result_table returns None below 2 rows)
    assert res.table is None


def test_pipeline_returns_a_table_and_chart_for_a_multi_row_report(ask):
    res = ask("Which taluks need attention in 2025-26?")
    assert res.route == "report:needs_attention:taluk"
    assert res.table is not None and res.table["total_rows"] == len(res.rows)
    assert res.chart and res.chart["type"] == "bar"

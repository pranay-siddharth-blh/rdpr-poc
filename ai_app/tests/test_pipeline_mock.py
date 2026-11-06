"""The LLM path with a scripted model: no gateway needed. Checks the guards, the repair round, the reviewer and the writer."""
import pytest

from app import pipeline
from app.llm import Verdict
from app.models import LLMQueryPlan
from conftest import run

QUESTION = "Which taluks in Mysuru zilla had the lowest collection percentage in 2025-26, and what was it?"
NO_PLACE = "Which taluks had the lowest collection percentage?"     # names no place: the code cannot disprove a scope objection
GOOD_SQL = ("SELECT taluk_name AS taluk, ROUND(SUM(total_collection)*100.0/NULLIF(SUM(total_demand),0), 2) AS collection_pct "
            "FROM mart_fact_gp_dcb WHERE fy = '2025-26' AND zilla_name = 'Mysuru' GROUP BY taluk_name "
            "ORDER BY collection_pct ASC LIMIT 3")


class Script:
    """Feeds the pipeline a fixed list of plans (one per model call) and records the prompts it was given."""

    def __init__(self, *plans):
        self.plans, self.prompts = list(plans), []

    async def __call__(self, prompt, retry=False):
        self.prompts.append(prompt)
        return self.plans.pop(0)


def plan(sql, tpl="The lowest is {taluk} at {collection_pct}.", answerable=True, msg=""):
    return LLMQueryPlan(answerable=answerable, sql=sql, answer_template=tpl, clarification_message=msg)


async def _no_breakdown(*args, **kwargs):
    return None


@pytest.fixture
def model(monkeypatch):
    def install(*plans, verdicts=None):
        s = Script(*plans)
        monkeypatch.setattr(pipeline, "generate_query_plan", s)
        # these questions are rankings the reviewed breakdown would answer first; switch it off to exercise the model path
        monkeypatch.setattr(pipeline.breakdown, "breakdown", _no_breakdown)
        monkeypatch.setattr(pipeline.settings, "rdpr_verify_answers", bool(verdicts))
        vs = list(verdicts or [])

        async def fake_verify(prompt):
            return vs.pop(0)
        monkeypatch.setattr(pipeline, "verify_answer", fake_verify)
        return s
    return install


def ask(db, q=QUESTION):
    return run(pipeline.answer_question(q, db, 200, 60))


def test_happy_path_writes_a_deterministic_answer(db, model):
    s = model(plan(GOOD_SQL))
    r = ask(db)
    assert r.route == "llm" and r.answerable and len(r.rows) == 3 and r.table
    assert "NULLS LAST" in r.sql and "%" in r.answer
    assert len(s.prompts) == 1 and "mart_fact_gp_dcb" in s.prompts[0] and "Mysuru" in s.prompts[0]
    assert "fact_hr_staff" not in s.prompts[0] and "staff_name" not in s.prompts[0]      # nothing person-level is ever shown to the model


def test_unsafe_sql_gets_one_repair_round_with_the_exact_error(db, model):
    bad = "SELECT AVG(collection_pct) AS c FROM mart_summary_zilla_year"
    s = model(plan(bad), plan(GOOD_SQL))
    r = ask(db)
    assert r.route == "llm" and len(s.prompts) == 2
    assert "AVG(collection_pct) is wrong" in s.prompts[1]


def test_raw_table_is_blocked_even_if_the_model_insists(db, model):
    evil = "SELECT staff_name AS n FROM fact_hr_staff"
    model(plan(evil), plan(evil))
    r = ask(db)
    assert not r.answerable and r.route.startswith("llm_sql_failed") and not r.rows


def test_model_decline_is_scrubbed(db, model):
    model(plan("", answerable=False, msg="The mart_fact_gp_dcb table has no budget column in the sqlite database."))
    r = ask(db)
    assert not r.answerable and "mart_" not in r.answer and "sqlite" not in r.answer.lower()


def test_impossible_result_is_repaired(db, model):
    bad = "SELECT taluk_name AS taluk, 250 AS collection_pct FROM mart_dim_taluk LIMIT 2"
    s = model(plan(bad), plan(GOOD_SQL))
    r = ask(db)
    assert r.route == "llm" and "must be between 0 and 100" in s.prompts[1]


def test_reviewer_rejection_is_repaired_then_shown(db, model):
    s = model(plan(GOOD_SQL), plan(GOOD_SQL), verdicts=[Verdict(False, "wrong place", "wrong_scope"), Verdict(True)])
    r = ask(db, NO_PLACE)
    assert r.route == "llm" and r.verification == "fixed" and len(s.prompts) == 2


def test_reviewer_rejecting_twice_hides_the_figures(db, model):
    model(plan(GOOD_SQL), plan(GOOD_SQL), verdicts=[Verdict(False, "x", "wrong_scope"), Verdict(False, "x", "wrong_scope")])
    r = ask(db, NO_PLACE)
    assert r.route == "llm_unverified" and not r.rows and not r.table and "second check" in r.answer


def test_reviewer_veto_overrules_a_provably_wrong_objection(db, model):
    # the SQL filters on Mysuru and 2025-26, so a 'wrong_scope' / 'wrong_period' objection is overruled deterministically
    model(plan(GOOD_SQL), verdicts=[Verdict(False, "it is for the wrong district", "wrong_scope")])
    assert ask(db).route == "llm"


def test_subject_mismatch_is_refused(db, model):
    sql = "SELECT zilla_name AS z, SUM(total_collection) AS c FROM mart_fact_gp_dcb WHERE fy = '2025-26' GROUP BY zilla_name"
    model(plan(sql, tpl="{z}"))
    r = ask(db, "How many taluks are there in Mysuru zilla?")
    assert r.route in ("llm_mismatch", "metric:taluk_count")           # the registry may answer it first


def test_position_summed_across_years_is_blocked_then_repaired(db, model):
    wrong = "SELECT SUM(total_demand) AS d FROM mart_fact_gp_dcb WHERE zilla_name = 'Mysuru'"
    right = "SELECT fy, SUM(total_demand) AS d FROM mart_fact_gp_dcb WHERE zilla_name = 'Mysuru' GROUP BY fy ORDER BY fy"
    s = model(plan(wrong), plan(right, tpl="Demand by year."))
    r = ask(db, "Show total demand for Mysuru zilla for all years")
    assert r.route == "llm" and "double counts" in s.prompts[1] and len(r.rows) == 5

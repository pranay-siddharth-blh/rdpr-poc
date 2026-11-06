import pytest

from app.db import RestrictedQueryError
from app.sql_safety import UnsafeSQLError, validate_readonly_sql
from app.verified_queries import example_sql
from conftest import run


def q(db, sql, restricted=True):
    return run(db.run(sql, max_rows=5, timeout_seconds=60, restricted=restricted))


# ---- the database guard (authorizer): only mart_* views may be read at the top level
def test_mart_views_readable(db):
    assert q(db, "SELECT COUNT(*) FROM mart_dim_zilla").rows == [(31,)]
    assert q(db, "SELECT fy FROM mart_summary_state_year ORDER BY fy").rows[0] == ("2022-23",)   # nested views


@pytest.mark.parametrize("sql", [
    "SELECT * FROM fact_hr_staff LIMIT 1",                 # person-level raw table
    "SELECT * FROM dim_gp LIMIT 1",
    "SELECT * FROM stg_flagged_row LIMIT 1",               # build staging and ledger tables are not for the model either
    "SELECT * FROM ledger_issue LIMIT 1",
    "SELECT * FROM sqlite_master",
    "SELECT staff_name FROM fact_hr_staff",
    "WITH x AS (SELECT * FROM fact_hr_staff) SELECT * FROM x",
    "WITH mart_fact_taluk_staff AS (SELECT staff_name FROM fact_hr_staff) SELECT * FROM mart_fact_taluk_staff",   # CTE named like a view
    "SELECT * FROM (SELECT staff_name FROM fact_hr_staff) t",
])
def test_raw_tables_are_denied(db, sql):
    with pytest.raises(RestrictedQueryError):
        q(db, sql)


def test_count_star_through_a_view_only_yields_a_count(db):
    # SQLite reads a view's base table without naming a column for COUNT(*); that can only ever return a number
    assert q(db, "SELECT COUNT(*) FROM mart_dim_gp").rows == [(6099,)]
    with pytest.raises(UnsafeSQLError):
        validate_readonly_sql("SELECT COUNT(*) FROM fact_hr_staff")    # and the SQL guard refuses the name anyway


@pytest.mark.parametrize("sql", ["DELETE FROM dim_zilla", "DROP VIEW mart_dim_zilla", "PRAGMA table_info(dim_gp)",
                                 "ATTACH DATABASE 'x.db' AS x", "CREATE TABLE t(a)"])
def test_writes_and_admin_denied(db, sql):
    with pytest.raises(Exception):
        q(db, sql)
    # and even unrestricted, the file is read-only
    if sql.startswith(("DELETE", "DROP", "CREATE")):
        with pytest.raises(Exception):
            q(db, sql, restricted=False)


# ---- SQL shape guard
@pytest.mark.parametrize("sql, fragment", [
    ("SELECT 1; SELECT 2", "Multiple"),
    ("DELETE FROM mart_dim_zilla", "SELECT"),
    ("SELECT * FROM dim_gp", "not available"),
    ("SELECT '{zilla}' AS z FROM mart_dim_zilla", "placeholder"),
    ("SELECT AVG(collection_pct) AS x FROM mart_summary_zilla_year", "ratio"),
    ("SELECT SUM(total_demand) AS d FROM mart_fact_gp_dcb", "double counts"),                   # position across all FYs
    ("SELECT SUM(closing_balance) AS d FROM mart_fact_gp_scheme_financials WHERE zilla_name = 'Mysuru'", "double counts"),
    ("SELECT g.zilla_name AS z, SUM(d.total_collection) AS c FROM mart_fact_gp_dcb d JOIN mart_fact_gp_year_closure y ON y.gp_id = d.gp_id "
     "GROUP BY g.zilla_name", "combines several fact"),
    ("SELECT SUM(total_collection) AS plf_pct FROM mart_fact_gp_dcb", None),   # not a KPI alias: allowed
    ("SELECT SUM(total_collection) AS collection_pct FROM mart_fact_gp_dcb WHERE fy = '2024-25'", "formula"),
])
def test_sql_guard(sql, fragment):
    if fragment is None:
        validate_readonly_sql(sql)
        return
    with pytest.raises(UnsafeSQLError) as e:
        validate_readonly_sql(sql)
    assert fragment.lower() in str(e.value).lower()


def test_good_sql_passes_and_gets_nulls_last():
    out = validate_readonly_sql("SELECT zilla_name AS z, SUM(total_demand) AS d FROM mart_fact_gp_dcb WHERE fy = '2025-26' "
                                "GROUP BY zilla_name ORDER BY d ASC LIMIT 3;")
    assert "NULLS LAST" in out and out.count("LIMIT") == 1
    # summing a position per FY is fine
    validate_readonly_sql("SELECT fy, SUM(arrears) AS a FROM mart_fact_gp_dcb GROUP BY fy")
    # pre-aggregated sub-queries may be joined
    validate_readonly_sql(example_sql()[10])


def test_unit_copied_into_the_alias_is_rejected_with_a_repair_message():
    """The schema documents units as 'total_collection REAL [INR]'; the model sometimes wrote 'AS total_collection INR',
    which SQLite rejects with a bare 'near "INR": syntax error'. The guard must catch it and say how to fix it."""
    with pytest.raises(UnsafeSQLError) as exc:
        validate_readonly_sql("SELECT zilla_name AS zilla, ROUND(SUM(total_collection), 2) AS total_collection INR "
                              "FROM mart_fact_gp_dcb WHERE fy = '2025-26' GROUP BY zilla_name LIMIT 5")
    assert "one word" in str(exc.value).lower() and "INR" in str(exc.value)


@pytest.mark.parametrize("sql", [
    # a one-word alias followed by a keyword is normal SQL and must still pass
    "SELECT zilla_name AS zilla, SUM(total_collection) AS total FROM mart_fact_gp_dcb WHERE fy = '2025-26' GROUP BY zilla_name",
    "SELECT fy AS fy, SUM(total_collection) AS total FROM mart_fact_gp_dcb GROUP BY fy ORDER BY total DESC",
    "SELECT a.zilla_name AS zilla FROM mart_summary_zilla_year AS a WHERE a.fy = '2024-25'",
    "SELECT SUM(x) AS t FROM (SELECT total_collection AS x FROM mart_fact_gp_dcb WHERE fy = '2024-25') AS sub",
])
def test_valid_aliases_are_not_blocked(sql):
    validate_readonly_sql(sql)


def test_every_reviewed_example_passes_guards_and_runs_restricted(db):
    for n, sql in example_sql().items():
        safe = validate_readonly_sql(sql)
        res = run(db.run(safe, max_rows=300, timeout_seconds=120, restricted=True))
        assert res.rows, f"example {n} returned nothing"

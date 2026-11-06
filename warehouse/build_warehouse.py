"""
RDPR warehouse build: one ordered, resumable pipeline from the module databases to the chatbot's semantic layer.

  L0 sources    src_file (every input file with its SHA-256, loaded or not and why), src_table (row count of every
                source table). The module databases are ATTACHed read-only: they are the raw layer (11 million rows are
                not copied a second time) and are never written (ANALYZE runs on main only).
  L2 staging    stg_quality: every data-quality rule evaluated on the source rows, with the rows it flags in
                stg_flagged_row. Flags describe; they do not delete.
  L3 core       schema_core.sql: the star schema with PKs, FKs and CHECK constraints for the business rules;
                ledger_column records where every source column landed (or why it did not).
  L4 reconcile  Revenue demand statistics tied to the DCB register per GP and FY (and property counts to the
                property-type register), with before / after totals in ledger_reconcile_log and an independent
                re-check in ledger_reconciliation.
  L5 mart       mart.py: physical, indexed tables (dimensions, facts, summaries, pre-summed taluk tables). The only
                layer the AI and the dashboard read.
  L6 semantic   metadata/*.json loaded into semantic_* tables, validated against the real mart (fails on an
                undocumented column, a metric over a missing table, a 'loaded' topic with no rows); row counts and
                date ranges are measured, never typed.
  L7 ledger     ledger_build (stage timings), ledger_issue (known issues with measured figures), ledger_file.
     checks     ledger_build_check: named PASS / FAIL invariants (totals reconcile, golden figures, FK check ...).
                Any FAIL stops the build before the database is published.
     export     semantic/semantic_layer.json + semantic/integrity_manifest.json for the app.

usage:
  python warehouse/build_warehouse.py                 # full build (about 6 minutes), published to DB/rdpr_star.sqlite
  python warehouse/build_warehouse.py --from mart     # rebuild mart and everything after it on the existing database
  python warehouse/build_warehouse.py --only checks   # re-run one stage
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from mart import MART  # noqa: E402

DB = ROOT / "DB" / "rdpr_star.sqlite"
BUILDING = ROOT / "DB" / "rdpr_star.building.sqlite"
META = HERE / "metadata"
SOURCES = {"fa": ROOT / "Finance_Accounting" / "FA_Finance.sqlite", "rv": ROOT / "Revenue" / "RV_Revenue.sqlite",
           "hr": ROOT / "Staged" / "HRMS" / "HRMS.sqlite"}
STAGES = ["sources", "staging", "core", "reconcile", "mart", "semantic", "ledger", "checks", "export"]
FRESH = {"sources", "staging", "core"}          # starting here builds a new file; later stages work on the published one

T0 = time.time()
_TIMINGS: list[tuple[str, float]] = []


def log(msg: str) -> None:
    print(f"[{time.time() - T0:6.1f}s] {msg}", flush=True)


class BuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def attach_sources(con: sqlite3.Connection) -> None:
    have = {r[1] for r in con.execute("PRAGMA database_list")}
    for alias, path in SOURCES.items():
        if alias not in have:
            # read-only by URI, so the build can never write to a source (spaces in the path are percent-encoded)
            con.execute(f"ATTACH DATABASE 'file:{urllib.parse.quote(path.as_posix())}?mode=ro' AS {alias}")


# ------------------------------------------------------------------------------------------------ L0 sources
INPUT_FILES = [
    ("Finance_Accounting/FA_Finance.sqlite", "Finance & Accounting module database", 1, "loaded: every fin_* GP-level table and the shared master"),
    ("Revenue/RV_Revenue.sqlite", "Revenue module database", 1, "loaded: every rev_* table"),
    ("Staged/HRMS/HRMS.sqlite", "HRMS rebuilt on the shared master (scripts/rebuild_hrms_on_master.py)", 1, "loaded: every hr_* table"),
    ("HRMS/GP_Synthetic_Data_2022_2026.xlsx", "original HRMS workbook", 0, "not loaded: GP codes and names differ from the master; Staged/HRMS is its rebuild"),
    ("Finance_Accounting/FA_Master.xlsx", "Finance master workbook", 0, "not loaded: identical, cell by cell, to FA_Finance.sqlite"),
    ("Finance_Accounting/FA_GP_Year_Closure.xlsx", "review copy", 0, "not loaded: identical, cell by cell, to fin_gp_year_closure"),
    ("Finance_Accounting/FA_Taluk_Year_Closure.xlsx", "taluk roll-up", 0, "not loaded: roll-up; rebuilt from GP rows in mart_agg_*"),
    ("Finance_Accounting/FA_Taluk_Month_Closure.xlsx", "taluk roll-up", 0, "not loaded: roll-up whose 'ALL schemes' rows are inconsistent (stg_quality)"),
    ("Finance_Accounting/FA_Taluk_Scheme_Financials.xlsx", "taluk roll-up", 0, "not loaded: roll-up; rebuilt from GP rows in mart_agg_*"),
    ("Finance_Accounting/FA_Taluk_Daybook_All.xlsx", "taluk roll-up", 0, "not loaded: 'ALL schemes' day-book roll-up; the per-scheme table is loaded"),
    ("Revenue/RV_Master.xlsx", "Revenue master workbook", 0, "not loaded: identical to RV_Revenue.sqlite"),
    ("Revenue/RV_DCB_Register.xlsx", "review copy", 0, "not loaded: identical, cell by cell, to rev_dcb_register"),
    ("Revenue/RV_Taxes_Fees.xlsx", "review copy", 0, "not loaded: identical, cell by cell, to rev_taxes_fees"),
    ("Revenue/RV_Demand_Statistics.xlsx", "review copy", 0, "not loaded: identical, cell by cell, to rev_demand_statistics"),
    ("Revenue/RV_Property_Type_Stats.xlsx", "review copy", 0, "not loaded: identical, cell by cell, to rev_property_type_stats"),
    ("Revenue/RV_Rollups.xlsx", "zilla / taluk roll-ups", 0, "not loaded: roll-ups; rebuilt from GP rows"),
    ("Staged/HRMS/HRMS_Data.xlsx", "review copy", 0, "not loaded: identical, cell by cell, to Staged/HRMS/HRMS.sqlite"),
    ("Karnataka_Zilla_Taluk_Master.xlsx", "zilla / taluk list", 0, "not loaded: identical to the Finance master"),
    ("FA_Excel_Blueprint.xlsx", "design notes", 0, "not loaded: documentation"),
]


def stage_sources(con: sqlite3.Connection) -> None:
    con.executescript("""
DROP TABLE IF EXISTS src_file; DROP TABLE IF EXISTS src_table;
CREATE TABLE src_file (file TEXT PRIMARY KEY, role TEXT, loaded INTEGER, bytes INTEGER, sha256 TEXT, note TEXT);
CREATE TABLE src_table (source TEXT, table_name TEXT, row_count INTEGER, PRIMARY KEY (source, table_name));""")
    for rel, role, loaded, note in INPUT_FILES:
        p = ROOT / rel
        if not p.exists():
            raise BuildError(f"input file missing: {rel}")
        con.execute("INSERT INTO src_file VALUES (?,?,?,?,?,?)", (rel, role, loaded, p.stat().st_size, sha256(p), note))
    attach_sources(con)
    for alias in SOURCES:
        for (t,) in con.execute(f"SELECT name FROM {alias}.sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'").fetchall():
            n = con.execute(f'SELECT COUNT(*) FROM {alias}."{t}"').fetchone()[0]
            con.execute("INSERT INTO src_table VALUES (?,?,?)", (alias, t, n))
    con.commit()
    log(f"sources: {len(INPUT_FILES)} files registered with SHA-256, "
        f"{con.execute('SELECT COUNT(*) FROM src_table').fetchone()[0]} source tables counted")


# ------------------------------------------------------------------------------------------------ L2 staging
# (rule, source table, SQL returning the key of every row the rule flags, action taken)
QUALITY = [
    ("scheme_ledger_rounding", "fa.fin_gp_scheme_financials",
     "SELECT fy_label || '|' || month_no || '|' || gp_id || '|' || scheme_id FROM fa.fin_gp_scheme_financials "
     "WHERE closing_balance <> opening_balance + receipts - expenditure",
     "kept: closing balance differs from opening + receipts - expenditure by one rupee (source rounding); core CHECK allows +-1"),
    ("all_scheme_rollup_above_lowest_scheme", "fa.fin_month_closure",
     "SELECT a.fy_label || '|' || a.month_no || '|' || a.taluk_id FROM fa.fin_month_closure a JOIN "
     "(SELECT fy_label, month_no, taluk_id, MIN(gps_closed) m FROM fa.fin_month_closure WHERE scheme_id <> 'ALL' GROUP BY 1, 2, 3) b "
     "USING (fy_label, month_no, taluk_id) WHERE a.scheme_id = 'ALL' AND a.gps_closed > b.m",
     "not loaded: the taluk roll-up is replaced by mart_agg_* built from GP rows"),
    ("demand_statistics_not_tied_to_dcb", "rv.rev_demand_statistics",
     "SELECT a.fy_label || '|' || a.gp_id FROM (SELECT fy_label, gp_id, SUM(total_demand) d FROM rv.rev_demand_statistics GROUP BY 1, 2) a "
     "JOIN rv.rev_dcb_register b USING (fy_label, gp_id) WHERE abs(a.d - b.total_demand) > 0.05",
     "fixed in stage reconcile: rescaled per GP and FY to the DCB register"),
    ("property_counts_not_tied", "rv.rev_demand_statistics",
     "SELECT a.fy_label || '|' || a.gp_id FROM (SELECT fy_label, gp_id, SUM(number_of_properties) n FROM rv.rev_demand_statistics GROUP BY 1, 2) a "
     "JOIN rv.rev_property_type_stats b USING (fy_label, gp_id) WHERE a.n <> b.number_of_properties",
     "fixed in stage reconcile: rescaled per GP and FY to the property-type register"),
    ("staff_never_approved", "hr.hr_staff_register",
     "SELECT staff_id FROM hr.hr_staff_register WHERE employment_status = 'Not Active'",
     "kept: registered but rejected by, or still pending at, the EO; not counted as active staff"),
    ("staff_dates_with_time", "hr.hr_staff_register",
     "SELECT staff_id FROM hr.hr_staff_register WHERE length(date_of_birth) > 10 OR length(date_of_joining) > 10",
     "fixed in stage core: dates stored as YYYY-MM-DD"),
    ("gp_reassigned_taluk", "fa.dim_gp",
     "SELECT gp_id FROM fa.dim_gp WHERE taluk_assignment = 'reassigned'",
     "kept: the GP's LGD code still shows its original taluk; the current taluk is used"),
]


def stage_staging(con: sqlite3.Connection) -> None:
    attach_sources(con)
    con.executescript("""
DROP TABLE IF EXISTS stg_quality; DROP TABLE IF EXISTS stg_flagged_row;
CREATE TABLE stg_quality (rule TEXT PRIMARY KEY, source_table TEXT, checked_rows INTEGER, flagged_rows INTEGER, action TEXT);
CREATE TABLE stg_flagged_row (rule TEXT, source_table TEXT, row_key TEXT);""")
    for rule, table, sql, action in QUALITY:
        keys = [r[0] for r in con.execute(sql)]
        n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        con.execute("INSERT INTO stg_quality VALUES (?,?,?,?,?)", (rule, table, n, len(keys), action))
        con.executemany("INSERT INTO stg_flagged_row VALUES (?,?,?)", [(rule, table, k) for k in keys])
        log(f"staging: {rule}: {len(keys):,} of {n:,} rows flagged")
    con.commit()


# ------------------------------------------------------------------------------------------------ L3 core
CORE_LOAD = [
    ("dim_zilla", "INSERT INTO dim_zilla SELECT zilla_id, zilla_lgd_code, zilla_name FROM fa.dim_zilla", "fa.dim_zilla"),
    ("dim_taluk", "INSERT INTO dim_taluk SELECT taluk_id, taluk_lgd_code, zilla_id, taluk_name, total_gps, gps_source FROM fa.dim_taluk", "fa.dim_taluk"),
    ("dim_gp", "INSERT INTO dim_gp SELECT gp_id, gp_lgd_code, taluk_id, zilla_id, gp_name, taluk_assignment, size_class, performance_tier FROM fa.dim_gp", "fa.dim_gp"),
    ("dim_fy", "INSERT INTO dim_fy SELECT fy_id, fy_label, start_date, end_date, data_through, is_current FROM fa.dim_fy", "fa.dim_fy"),
    ("dim_month", None, None),
    ("dim_date", """INSERT INTO dim_date SELECT date, CAST(substr(date, 1, 4) AS INTEGER) * 100 + CAST(substr(date, 6, 2) AS INTEGER), fy.fy_id,
                    weekday, is_working_day FROM fa.dim_date d JOIN dim_fy fy ON fy.fy_label = d.fy_label""", "fa.dim_date"),
    ("dim_scheme", """INSERT INTO dim_scheme SELECT s.scheme_id, s.scheme_name, s.scheme_category, f1.fy_id, f2.fy_id,
                      CASE WHEN s.scheme_id = 'ALL' THEN 1 ELSE 0 END
                      FROM fa.dim_scheme s LEFT JOIN dim_fy f1 ON f1.fy_label = s.active_from_fy LEFT JOIN dim_fy f2 ON f2.fy_label = s.active_to_fy""", "fa.dim_scheme"),
    ("dim_fee_type", "INSERT INTO dim_fee_type SELECT fee_type_id, fee_type_name FROM rv.dim_fee_type", "rv.dim_fee_type"),
    ("dim_property_type", "INSERT INTO dim_property_type SELECT property_type_id, property_type_name, report_category FROM rv.dim_property_type", "rv.dim_property_type"),
    ("dim_staff_type", "INSERT INTO dim_staff_type SELECT staff_type_code, staff_type_name FROM hr.dim_staff_type", "hr.dim_staff_type"),
    ("dim_designation", """INSERT INTO dim_designation (staff_type_code, report_level, designation_name)
                           SELECT st.staff_type_code, d.report_level, d.designation_name FROM hr.dim_designation d
                           JOIN dim_staff_type st ON st.staff_type_name = d.staff_type_name
                           ORDER BY d.report_level, st.staff_type_code, d.designation_name""", "hr.dim_designation"),
    ("fact_fin_gp_year_closure", """INSERT INTO fact_fin_gp_year_closure SELECT fy.fy_id, s.gp_id, s.scheme_id, s.closed_on, s.is_closed
        FROM fa.fin_gp_year_closure s JOIN dim_fy fy ON fy.fy_label = s.fy_label""", "fa.fin_gp_year_closure"),
    ("fact_fin_gp_month_closure", """INSERT INTO fact_fin_gp_month_closure SELECT m.month_id, s.gp_id, s.scheme_id, s.closed_on, s.is_closed, s.days_after_month_end
        FROM fa.fin_gp_month_closure s JOIN dim_fy fy ON fy.fy_label = s.fy_label JOIN dim_month m ON m.fy_id = fy.fy_id AND m.fy_month_no = s.month_no""",
     "fa.fin_gp_month_closure"),
    ("fact_fin_gp_scheme_financials", """INSERT INTO fact_fin_gp_scheme_financials SELECT m.month_id, s.gp_id, s.scheme_id, s.opening_balance, s.receipts,
        s.expenditure, s.closing_balance FROM fa.fin_gp_scheme_financials s JOIN dim_fy fy ON fy.fy_label = s.fy_label
        JOIN dim_month m ON m.fy_id = fy.fy_id AND m.fy_month_no = s.month_no""", "fa.fin_gp_scheme_financials"),
    ("fact_fin_daybook_closure", """INSERT INTO fact_fin_daybook_closure SELECT date, taluk_id, scheme_id, total_gps, gps_closed, gps_pending, closure_pct
        FROM fa.fin_daybook_closure_scheme""", "fa.fin_daybook_closure_scheme"),
    ("fact_rev_dcb_register", """INSERT INTO fact_rev_dcb_register SELECT fy.fy_id, s.gp_id, arrears, year_demand, total_demand, total_collection, adjustments, balance
        FROM rv.rev_dcb_register s JOIN dim_fy fy ON fy.fy_label = s.fy_label""", "rv.rev_dcb_register"),
    ("fact_rev_taxes_fees", """INSERT INTO fact_rev_taxes_fees SELECT fy.fy_id, s.gp_id, fee_type_id, arrears, year_demand, total_demand, total_collection,
        adjustments, balance FROM rv.rev_taxes_fees s JOIN dim_fy fy ON fy.fy_label = s.fy_label""", "rv.rev_taxes_fees"),
    ("fact_rev_demand_statistics", """INSERT INTO fact_rev_demand_statistics SELECT fy.fy_id, s.gp_id, property_type_id, number_of_properties, arrears,
        year_demand, total_demand, total_collection, adjustments, balance FROM rv.rev_demand_statistics s JOIN dim_fy fy ON fy.fy_label = s.fy_label""",
     "rv.rev_demand_statistics"),
    ("fact_rev_property_type_stats", """INSERT INTO fact_rev_property_type_stats SELECT fy.fy_id, s.gp_id, number_of_properties, agro_based_production_units,
        commercial, community, government, industrial, non_residential, religious, residential, commercial_cum_residential, renewable,
        telecom_tower, other_unclassified FROM rv.rev_property_type_stats s JOIN dim_fy fy ON fy.fy_label = s.fy_label""", "rv.rev_property_type_stats"),
    ("fact_rev_gp_monthly_collection", """INSERT INTO fact_rev_gp_monthly_collection SELECT m.month_id, s.gp_id, s.fee_type_id, s.collection_amount
        FROM rv.rev_gp_monthly_collection s JOIN dim_fy fy ON fy.fy_label = s.fy_label JOIN dim_month m ON m.fy_id = fy.fy_id AND m.fy_month_no = s.month_no""",
     "rv.rev_gp_monthly_collection"),
    ("fact_hr_staff", """INSERT INTO fact_hr_staff SELECT s.staff_id, s.gp_id, s.staff_type_code, d.designation_id, s.staff_name, s.gender,
        substr(s.date_of_birth, 1, 10), substr(s.date_of_joining, 1, 10), substr(s.registration_date, 1, 10), substr(s.eo_rejected_date, 1, 10),
        substr(s.resent_to_eo_date, 1, 10), substr(s.eo_approved_date, 1, 10), s.approval_status, s.monthly_gross_salary_inr,
        s.employment_status, substr(s.exit_date, 1, 10)
        FROM hr.hr_staff_register s JOIN dim_designation d ON d.designation_name = s.designation AND d.staff_type_code = s.staff_type_code
        AND d.report_level = 'GP'""", "hr.hr_staff_register"),
    ("fact_hr_er_registration", """INSERT INTO fact_hr_er_registration SELECT fy.fy_id, s.gp_id, substr(s.snapshot_date, 1, 10), total_seats,
        total_elected_members, total_adhyaksha_president, total_upadhyaksha FROM hr.hr_er_registration s JOIN dim_fy fy ON fy.fy_label = s.fy_label""",
     "hr.hr_er_registration"),
    ("fact_hr_eo_approval", """INSERT INTO fact_hr_eo_approval SELECT fy.fy_id, s.gp_id, substr(s.snapshot_date, 1, 10), staff_registrations_sent_to_eo,
        staff_approved_by_eo, staff_approval_pending_at_eo, staff_registrations_rejected_by_eo, staff_resent_for_approval_to_eo
        FROM hr.hr_eo_approval s JOIN dim_fy fy ON fy.fy_label = s.fy_label""", "hr.hr_eo_approval"),
    ("fact_hr_salary_bills", """INSERT INTO fact_hr_salary_bills SELECT s.calendar_year * 100 + s.calendar_month_no, s.taluk_id, st.staff_type_code,
        total_number_of_staff, number_of_gps_generated_main_bill, number_of_main_bill_generated, number_of_main_bill_pdo_signed,
        number_of_main_bill_president_signed, number_of_main_bill_processed_by_bank, number_of_auxiliary_bill_generated,
        number_of_auxiliary_bill_pdo_signed, number_of_auxiliary_bill_president_signed, number_of_auxiliary_bill_processed_by_bank,
        number_of_staff_salary_paid, number_of_staff_salary_rejected_by_bank
        FROM hr.hr_monthly_salary s JOIN dim_staff_type st ON st.staff_type_name = s.staff_type_name""", "hr.hr_monthly_salary"),
]
# source columns deliberately not carried into core, with the reason (lineage)
NOT_CARRIED = {
    "base_activity": "UNMAPPED (generator-only column)", "demand_multiplier": "UNMAPPED (generator-only column)",
    "taluk_id": "UNMAPPED (repeats dim_gp.taluk_id: facts store gp_id only)", "zilla_id": "UNMAPPED (repeats dim_gp.zilla_id)",
    "zilla_name": "UNMAPPED (name: facts store ids, names live in dimensions)", "taluk_name": "UNMAPPED (name: facts store ids)",
    "gp_name": "UNMAPPED (name: facts store ids)", "fy_label": "UNMAPPED (replaced by fy_id / month_id keys)",
    "month_no": "UNMAPPED (replaced by month_id)", "month_name": "UNMAPPED (in dim_month)",
    "fee_type_name": "UNMAPPED (in dim_fee_type)", "property_type_name": "UNMAPPED (in dim_property_type)",
    "zilla_lgd_code": "UNMAPPED (in dim_zilla)", "taluk_lgd_code": "UNMAPPED (in dim_taluk)", "gp_lgd_code": "UNMAPPED (in dim_gp)",
    "calendar_year": "UNMAPPED (in dim_month)", "calendar_month_no": "UNMAPPED (in dim_month)", "fy_month_no": "UNMAPPED (in dim_month)",
    "staff_type_name": "UNMAPPED (replaced by staff_type_code)", "designation": "UNMAPPED (replaced by designation_id)",
    "number_of_gp": "UNMAPPED (repeats dim_taluk.total_gps)", "active_from_fy": "UNMAPPED (replaced by active_from_fy_id)",
    "active_to_fy": "UNMAPPED (replaced by active_to_fy_id)", "date": "mapped as date_id",
}


def _lineage_recorder(store: dict, target: str):
    def rec(action, arg1, arg2, dbname, _tv):
        if action == sqlite3.SQLITE_READ and dbname in SOURCES and arg2:
            store.setdefault((dbname, arg1, arg2), set()).add(target)
        return sqlite3.SQLITE_OK
    return rec


def stage_core(con: sqlite3.Connection) -> None:
    attach_sources(con)
    con.execute("PRAGMA foreign_keys = OFF")
    con.executescript((HERE / "schema_core.sql").read_text(encoding="utf-8"))
    con.execute("INSERT INTO dim_fy VALUES ('FY2122', '2021-22', '2021-04-01', '2022-03-31', '2022-03-31', 0)")  # HRMS Jan-Mar 2022
    lineage: dict = {}
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for table, sql, src in CORE_LOAD:
        if table == "dim_month":
            rows = []
            for y in range(2022, 2028):
                for m in range(1, 13):
                    if (y, m) > (2027, 3):
                        continue
                    fy_start = y if m >= 4 else y - 1
                    rows.append((y * 100 + m, f"FY{str(fy_start)[2:]}{str(fy_start + 1)[2:]}", (m - 4) % 12 + 1, y, m, names[m - 1]))
            con.executemany("INSERT INTO dim_month VALUES (?,?,?,?,?,?)", rows)
            continue
        con.set_authorizer(_lineage_recorder(lineage, table))
        try:
            con.execute(sql)
        except sqlite3.IntegrityError as exc:
            raise BuildError(f"core: {table} breaks a constraint: {exc}") from exc
        finally:
            con.set_authorizer(None)
        n, s = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], con.execute(f"SELECT COUNT(*) FROM {src}").fetchone()[0]
        if table.startswith("fact_") and n != s:
            raise BuildError(f"core: {table} loaded {n:,} rows from {s:,}")
        log(f"core: {table}: {n:,} rows")
    con.commit()
    idx = ["fact_fin_gp_year_closure(gp_id)", "fact_fin_gp_month_closure(gp_id)", "fact_fin_gp_scheme_financials(gp_id)",
           "fact_fin_daybook_closure(taluk_id)", "fact_rev_dcb_register(gp_id)", "fact_rev_taxes_fees(gp_id)", "fact_rev_demand_statistics(gp_id)",
           "fact_rev_property_type_stats(gp_id)", "fact_rev_gp_monthly_collection(gp_id)", "fact_hr_staff(gp_id)", "fact_hr_er_registration(gp_id)",
           "fact_hr_eo_approval(gp_id)", "fact_hr_salary_bills(taluk_id)", "dim_gp(taluk_id)", "dim_gp(zilla_id)", "dim_taluk(zilla_id)",
           "fact_fin_gp_month_closure(scheme_id)", "fact_fin_gp_year_closure(scheme_id)"]
    for d in idx:
        t, c = d[:-1].split("(")
        con.execute(f"CREATE INDEX IF NOT EXISTS ix_{t}_{c} ON {t}({c})")
    bad = con.execute("PRAGMA main.foreign_key_check").fetchall()
    if bad:
        raise BuildError(f"core: {len(bad)} foreign-key violations, e.g. {bad[:3]}")
    # lineage: every source column -> the core table it landed in, or why not
    con.executescript("DROP TABLE IF EXISTS ledger_column; CREATE TABLE ledger_column (source TEXT, source_table TEXT, column_name TEXT, landed_in TEXT);")
    for alias in SOURCES:
        for (t,) in con.execute(f"SELECT name FROM {alias}.sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'").fetchall():
            for _cid, c, *_ in con.execute(f'PRAGMA {alias}.table_info("{t}")').fetchall():
                hit = lineage.get((alias, t, c))
                if hit:
                    landed = ", ".join(sorted(hit))
                elif not any(src == f"{alias}.{t}" for _, _, src in CORE_LOAD):
                    landed = "NOT LOADED (" + {"fin_year_closure": "taluk roll-up, rebuilt in mart_agg_taluk_fy",
                                               "fin_month_closure": "taluk roll-up with inconsistent ALL rows",
                                               "fin_scheme_financials": "taluk roll-up, rebuilt in mart_agg_*",
                                               "fin_daybook_closure_all": "'ALL schemes' day-book roll-up",
                                               "hr_gp_crosswalk": "audit trail of the HRMS rebuild"}.get(t, "duplicate of the shared master or a report catalogue") + ")"
                else:
                    landed = NOT_CARRIED.get(c, "UNMAPPED (not needed by any core table)")
                con.execute("INSERT INTO ledger_column VALUES (?,?,?,?)", (alias, t, c, landed))
    con.commit()
    log(f"core: schema + CHECK constraints loaded, 0 FK violations, {con.execute('SELECT COUNT(*) FROM ledger_column').fetchone()[0]} source columns traced")


# ------------------------------------------------------------------------------------------------ L4 reconcile
def stage_reconcile(con: sqlite3.Connection) -> None:
    import numpy as np
    import pandas as pd
    con.executescript("""
DROP TABLE IF EXISTS ledger_reconcile_log; DROP TABLE IF EXISTS ledger_reconciliation;
CREATE TABLE ledger_reconcile_log (step TEXT, fy_id TEXT, measure TEXT, before_value REAL, after_value REAL, target_value REAL, detail TEXT);
CREATE TABLE ledger_reconciliation (check_no INTEGER, label TEXT, expected REAL, actual REAL, diff REAL, tolerance REAL, status TEXT);""")
    d = pd.read_sql("SELECT * FROM fact_rev_demand_statistics", con)
    dcb = pd.read_sql("SELECT * FROM fact_rev_dcb_register", con).set_index(["fy_id", "gp_id"])
    pts = pd.read_sql("SELECT fy_id, gp_id, number_of_properties FROM fact_rev_property_type_stats", con).set_index(["fy_id", "gp_id"])
    key = ["fy_id", "gp_id"]
    before = d.groupby("fy_id")[["total_demand", "total_collection", "number_of_properties"]].sum()

    def tie(col, target):
        """Scale col so that per (FY, GP) it sums to the target; the cent-level rounding residual goes to the largest row."""
        s = d.groupby(key)[col].transform("sum")
        tgt = pd.Series(target.reindex(pd.MultiIndex.from_frame(d[key])).values, index=d.index)
        new = (d[col] * np.where(s > 0, tgt / s.replace(0, np.nan), 1)).fillna(0)
        new = new.round(2) if col != "number_of_properties" else new.round(0)
        resid = (tgt - new.groupby([d.fy_id, d.gp_id]).transform("sum")).round(2)
        big = new.groupby([d.fy_id, d.gp_id]).transform("max") == new
        first = big.groupby([d.fy_id, d.gp_id]).cumsum().eq(1) & big
        d[col] = (new + np.where(first, resid, 0)).round(2 if col != "number_of_properties" else 0)
    for col in ["arrears", "year_demand", "total_collection", "adjustments"]:
        tie(col, dcb[col])
    tie("number_of_properties", pts.number_of_properties)
    d["number_of_properties"] = d.number_of_properties.astype(int)
    d["total_demand"] = (d.arrears + d.year_demand).round(2)
    d["balance"] = (d.total_demand - d.total_collection - d.adjustments).round(2)
    cols = ["fy_id", "gp_id", "property_type_id", "number_of_properties", "arrears", "year_demand", "total_demand",
            "total_collection", "adjustments", "balance"]
    con.execute("DELETE FROM fact_rev_demand_statistics")
    con.executemany(f"INSERT INTO fact_rev_demand_statistics VALUES ({','.join('?' * len(cols))})", d[cols].itertuples(index=False, name=None))
    after = d.groupby("fy_id")[["total_demand", "total_collection", "number_of_properties"]].sum()
    tgt = dcb.groupby(level=0)[["total_demand", "total_collection"]].sum().join(pts.groupby(level=0)[["number_of_properties"]].sum())
    for fy in after.index:
        for m in ("total_demand", "total_collection", "number_of_properties"):
            con.execute("INSERT INTO ledger_reconcile_log VALUES (?,?,?,?,?,?,?)",
                        ("tie_demand_statistics", fy, m, float(before.loc[fy, m]), float(after.loc[fy, m]), float(tgt.loc[fy, m]),
                         "rescaled per GP and FY to the DCB register / property-type register; each property type keeps its share"))
    # independent re-check, fresh from the database
    checks = [
        ("demand statistics total_demand = DCB, worst GP-FY", "SELECT MAX(abs(a.v - b.total_demand)) FROM (SELECT fy_id, gp_id, SUM(total_demand) v FROM fact_rev_demand_statistics GROUP BY 1, 2) a JOIN fact_rev_dcb_register b USING (fy_id, gp_id)", 0.05),
        ("demand statistics collection = DCB, worst GP-FY", "SELECT MAX(abs(a.v - b.total_collection)) FROM (SELECT fy_id, gp_id, SUM(total_collection) v FROM fact_rev_demand_statistics GROUP BY 1, 2) a JOIN fact_rev_dcb_register b USING (fy_id, gp_id)", 0.05),
        ("demand statistics balance = DCB, worst GP-FY", "SELECT MAX(abs(a.v - b.balance)) FROM (SELECT fy_id, gp_id, SUM(balance) v FROM fact_rev_demand_statistics GROUP BY 1, 2) a JOIN fact_rev_dcb_register b USING (fy_id, gp_id)", 0.05),
        ("property counts = property-type register, worst GP-FY", "SELECT MAX(abs(a.v - b.number_of_properties)) FROM (SELECT fy_id, gp_id, SUM(number_of_properties) v FROM fact_rev_demand_statistics GROUP BY 1, 2) a JOIN fact_rev_property_type_stats b USING (fy_id, gp_id)", 0.0),
        ("no negative figures after rescaling", "SELECT COUNT(*) FROM fact_rev_demand_statistics WHERE balance < 0 OR total_collection < 0 OR number_of_properties < 0", 0.0),
    ]
    for i, (label, sql, tol) in enumerate(checks, start=1):
        actual = con.execute(sql).fetchone()[0] or 0.0
        con.execute("INSERT INTO ledger_reconciliation VALUES (?,?,?,?,?,?,?)", (i, label, 0.0, actual, actual, tol, "PASS" if actual <= tol else "FAIL"))
    con.commit()
    fails = con.execute("SELECT label FROM ledger_reconciliation WHERE status = 'FAIL'").fetchall()
    if fails:
        raise BuildError(f"reconcile: {fails}")
    log(f"reconcile: demand statistics tied to the DCB register; {len(checks)} independent checks PASS "
        f"(total demand {before.total_demand.sum():,.0f} -> {after.total_demand.sum():,.0f})")


# ------------------------------------------------------------------------------------------------ L5 mart
_TYPE = {"integer": "INTEGER", "real": "REAL", "text": "TEXT", "blob": "BLOB", "null": "TEXT"}


def materialise(con: sqlite3.Connection, name: str, select: str) -> int:
    """CREATE TABLE with a declared type per column (read from the data), then fill it. The SELECT runs once, into a
    temporary table, so an aggregate is never re-computed per column."""
    con.execute("DROP TABLE IF EXISTS temp._m")
    con.execute(f"CREATE TEMP TABLE _m AS {select}")
    cols = [r[1] for r in con.execute("PRAGMA temp.table_info(_m)")]
    types = []
    for c in cols:
        row = con.execute(f'SELECT typeof("{c}") FROM temp._m WHERE "{c}" IS NOT NULL LIMIT 1').fetchone()
        types.append(_TYPE.get(row[0] if row else "null", "TEXT"))
    con.execute(f"CREATE TABLE main.{name} (" + ", ".join(f'"{c}" {t}' for c, t in zip(cols, types)) + ")")
    con.execute(f"INSERT INTO main.{name} SELECT * FROM temp._m")
    con.execute("DROP TABLE temp._m")
    return con.execute(f"SELECT COUNT(*) FROM main.{name}").fetchone()[0]


def stage_mart(con: sqlite3.Connection) -> None:
    for (n, k) in con.execute("SELECT name, type FROM sqlite_master WHERE (type IN ('table', 'view')) AND (name LIKE 'mart\\_%' ESCAPE '\\' OR name LIKE 'vw\\_%' ESCAPE '\\')").fetchall():
        con.execute(f"DROP {k.upper()} {n}")
    con.execute("DROP TABLE IF EXISTS build_notes")
    con.commit()
    for name, select, indexes in MART:
        t = time.time()
        n = materialise(con, name, select)
        for i, cols in enumerate(indexes):
            con.execute(f"CREATE INDEX ix_{name}_{i} ON {name} ({cols})")
        con.commit()
        log(f"mart: {name}: {n:,} rows, {len(indexes)} indexes ({time.time() - t:.1f}s)")
    con.execute("ANALYZE main")
    con.commit()


# ------------------------------------------------------------------------------------------------ L6 semantic
def _load(name: str) -> dict:
    return json.loads((META / name).read_text(encoding="utf-8"))


def measured_figures(con: sqlite3.Connection) -> dict:
    """Figures quoted in metadata text ({placeholders}), measured from the data at build time."""
    q = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
    return {"not_active_staff": f"{q('SELECT COUNT(*) FROM fact_hr_staff WHERE employment_status = ' + chr(39) + 'Not Active' + chr(39)):,}",
            "reassigned_gps": f"{q('SELECT COUNT(*) FROM dim_gp WHERE taluk_assignment = ' + chr(39) + 'reassigned' + chr(39)):,}",
            "bapuji_gps": f"{q('SELECT COUNT(DISTINCT gp_id) FROM fact_fin_gp_year_closure WHERE scheme_id = ' + chr(39) + 'S04' + chr(39)):,}"}


def stage_semantic(con: sqlite3.Connection) -> None:
    docs, metrics, caps = _load("semantic_docs.json"), _load("metric_registry.json")["metrics"], _load("capability_manifest.json")["capabilities"]
    con.executescript("""
DROP TABLE IF EXISTS semantic_table_doc; DROP TABLE IF EXISTS semantic_column_doc; DROP TABLE IF EXISTS semantic_metric;
DROP TABLE IF EXISTS semantic_capability; DROP TABLE IF EXISTS semantic_data_period;
CREATE TABLE semantic_table_doc (table_name TEXT PRIMARY KEY, table_group TEXT, grain TEXT, doc TEXT, row_count INTEGER, date_from TEXT, date_to TEXT);
CREATE TABLE semantic_column_doc (table_name TEXT, column_name TEXT, data_type TEXT, unit TEXT, additive INTEGER, doc TEXT, PRIMARY KEY (table_name, column_name));
CREATE TABLE semantic_metric (metric_key TEXT PRIMARY KEY, label TEXT, unit TEXT, definition TEXT);
CREATE TABLE semantic_capability (topic TEXT PRIMARY KEY, status TEXT, mart_tables TEXT, row_count INTEGER, note TEXT);
CREATE TABLE semantic_data_period (key TEXT PRIMARY KEY, value TEXT);""")
    marts = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'mart\\_%' ESCAPE '\\' ORDER BY name")]
    missing = sorted(set(marts) ^ set(docs["tables"]))
    if missing:
        raise BuildError(f"semantic: mart tables and semantic_docs.json differ: {missing}")
    undocumented = []
    for t in marts:
        info = docs["tables"][t]
        cols = con.execute(f"PRAGMA table_info({t})").fetchall()
        names = [c[1] for c in cols]
        rows = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        dcol = next((c for c in ("date", "month_id", "fy") if c in names), None)
        lo, hi = con.execute(f"SELECT MIN({dcol}), MAX({dcol}) FROM {t}").fetchone() if dcol else (None, None)
        con.execute("INSERT INTO semantic_table_doc VALUES (?,?,?,?,?,?,?)", (t, info["group"], info["grain"], info["doc"], rows,
                                                                            None if lo is None else str(lo), None if hi is None else str(hi)))
        for _cid, c, typ, *_ in cols:
            d = docs["column_overrides"].get(f"{t}.{c}") or docs["common_columns"].get(c)
            if d is None:
                undocumented.append(f"{t}.{c}")
                continue
            con.execute("INSERT INTO semantic_column_doc VALUES (?,?,?,?,?,?)",
                        (t, c, typ or "TEXT", d["unit"], None if d["additive"] is None else int(d["additive"]), d["doc"]))
    if undocumented:
        raise BuildError("semantic: undocumented mart columns (add them to warehouse/metadata/semantic_docs.json):\n  " + "\n  ".join(undocumented))
    for m in metrics:
        for var in [*m["variants"].values(), *m.get("with_fee_type", {}).values(), *m.get("with_property_type", {}).values()]:
            if var["table"] not in marts:
                raise BuildError(f"semantic: metric {m['key']} reads missing table {var['table']}")
            try:
                con.execute(f"SELECT {var['expr']} FROM {var['table']}" + (f" WHERE {var['filter']}" if var.get("filter") else "") + " LIMIT 1").fetchall()
            except sqlite3.Error as exc:
                raise BuildError(f"semantic: metric {m['key']} expression fails: {exc}") from exc
        con.execute("INSERT INTO semantic_metric VALUES (?,?,?,?)", (m["key"], m["label"], m["unit"], json.dumps(m)))
    for cap in caps:
        rows = sum(con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in cap.get("tables", []))
        if cap["status"] == "loaded" and rows == 0:
            raise BuildError(f"semantic: topic {cap['topic']} is marked loaded but its tables are empty")
        if cap["status"] == "not_loaded" and cap.get("tables"):
            raise BuildError(f"semantic: topic {cap['topic']} is not_loaded but lists tables")
        con.execute("INSERT INTO semantic_capability VALUES (?,?,?,?,?)", (cap["topic"], cap["status"], json.dumps(cap.get("tables", [])), rows, cap["note"]))
    period = {"data_from": con.execute("SELECT MIN(date_id) FROM dim_date").fetchone()[0],
              "data_to": con.execute("SELECT MAX(date_id) FROM dim_date").fetchone()[0],
              "data_as_of": con.execute("SELECT MAX(date_id) FROM dim_date").fetchone()[0],
              "latest_full_fy": con.execute("SELECT MAX(fy_label) FROM dim_fy WHERE data_through >= end_date").fetchone()[0],
              "partial_fy": con.execute("SELECT fy_label FROM dim_fy WHERE is_current = 1").fetchone()[0],
              "data_nature": docs["data_period"]["data_nature"]}
    con.executemany("INSERT INTO semantic_data_period VALUES (?,?)", list(period.items()))
    con.commit()
    log(f"semantic: {len(marts)} mart tables and every column documented, {len(metrics)} metrics compile, {len(caps)} capability topics checked")


# ------------------------------------------------------------------------------------------------ L7 ledger
def stage_ledger(con: sqlite3.Connection) -> None:
    con.executescript("""
DROP TABLE IF EXISTS ledger_file; DROP TABLE IF EXISTS ledger_issue;
CREATE TABLE ledger_file AS SELECT * FROM src_file;
CREATE TABLE ledger_issue (id TEXT PRIMARY KEY, title TEXT, status TEXT, caveat TEXT, affects TEXT);
CREATE TABLE IF NOT EXISTS ledger_build (run_at TEXT, stage TEXT, seconds REAL);""")
    figs = measured_figures(con)
    for i in _load("known_issues.json")["issues"]:
        con.execute("INSERT INTO ledger_issue VALUES (?,?,?,?,?)", (i["id"], i["title"], i["status"], i["caveat"].format(**figs), json.dumps(i["affects"])))
    (HERE / "metadata" / "_lineage.json").write_text(json.dumps(
        [dict(zip(("source", "source_table", "column", "landed_in"), r)) for r in con.execute("SELECT * FROM ledger_column ORDER BY 1, 2, 3")],
        indent=1), encoding="utf-8")
    con.commit()
    log(f"ledger: {con.execute('SELECT COUNT(*) FROM ledger_issue').fetchone()[0]} known issues, lineage written to metadata/_lineage.json")


# ------------------------------------------------------------------------------------------------ checks
def stage_checks(con: sqlite3.Connection) -> None:
    con.executescript("DROP TABLE IF EXISTS ledger_build_check; CREATE TABLE ledger_build_check (name TEXT, expected TEXT, actual TEXT, status TEXT);")
    q = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
    checks: list[tuple[str, object, object, bool]] = []

    def eq(name, expected, actual, tol=0.0):
        ok = (abs(float(expected) - float(actual)) <= tol) if isinstance(expected, (int, float)) and actual is not None else expected == actual
        checks.append((name, expected, actual, ok))
    eq("integrity_check", "ok", q("PRAGMA main.integrity_check"))
    eq("foreign_key_check (violations)", 0, len(con.execute("PRAGMA main.foreign_key_check").fetchall()))
    for core, mart in (("fact_rev_dcb_register", "mart_fact_gp_dcb"), ("fact_fin_gp_year_closure", "mart_fact_gp_year_closure"),
                       ("fact_fin_gp_month_closure", "mart_fact_gp_month_closure"), ("fact_fin_gp_scheme_financials", "mart_fact_gp_scheme_financials"),
                       ("fact_rev_gp_monthly_collection", "mart_fact_gp_monthly_collection"), ("fact_hr_salary_bills", "mart_fact_taluk_salary_bills"),
                       ("fact_fin_daybook_closure", "mart_fact_taluk_daybook_closure")):
        eq(f"{mart} rows = {core}", q(f"SELECT COUNT(*) FROM {core}"), q(f"SELECT COUNT(*) FROM {mart}"))
    # every pre-summed table adds up to the GP-level facts (statewide, every FY)
    eq("mart_agg_taluk_fy collection = GP DCB", q("SELECT SUM(total_collection) FROM mart_fact_gp_dcb"), q("SELECT SUM(total_collection) FROM mart_agg_taluk_fy"), 1.0)
    eq("mart_agg_taluk_fy balance = GP DCB", q("SELECT SUM(balance) FROM mart_fact_gp_dcb"), q("SELECT SUM(balance) FROM mart_agg_taluk_fy"), 1.0)
    eq("mart_agg_taluk_month collection = GP monthly", q("SELECT SUM(collection_amount) FROM mart_fact_gp_monthly_collection"), q("SELECT SUM(collection_amount) FROM mart_agg_taluk_month"), 1.0)
    eq("mart_agg_taluk_month receipts = GP scheme money", q("SELECT SUM(receipts) FROM mart_fact_gp_scheme_financials"), q("SELECT SUM(receipts) FROM mart_agg_taluk_month"), 1.0)
    eq("mart_agg_taluk_fy receipts = GP scheme money", q("SELECT SUM(receipts) FROM mart_fact_gp_scheme_financials"), q("SELECT SUM(receipts) FROM mart_agg_taluk_fy"), 1.0)
    eq("mart_agg_taluk_month books closed = GP month closure", q("SELECT SUM(is_closed) FROM mart_fact_gp_month_closure"), q("SELECT SUM(month_books_closed) FROM mart_agg_taluk_month"))
    eq("mart_agg_taluk_fy year books = GP year closure", q("SELECT COUNT(*) FROM mart_fact_gp_year_closure"), q("SELECT SUM(scheme_books) FROM mart_agg_taluk_fy"))
    eq("mart_agg_taluk_fy all-books GPs = summary", q("SELECT SUM(all_books_closed) FROM mart_summary_gp_year"), q("SELECT SUM(gps_all_books_closed) FROM mart_agg_taluk_fy"))
    eq("mart_agg_taluk_fee_type_fy = GP fee types", q("SELECT SUM(total_collection) FROM mart_fact_gp_fee_type"), q("SELECT SUM(total_collection) FROM mart_agg_taluk_fee_type_fy"), 1.0)
    eq("mart_agg_taluk_property_fy = GP property types", q("SELECT SUM(balance) FROM mart_fact_gp_demand_by_property_type"), q("SELECT SUM(balance) FROM mart_agg_taluk_property_fy"), 1.0)
    eq("mart_agg_taluk_scheme_fy receipts = GP scheme money", q("SELECT SUM(receipts) FROM mart_fact_gp_scheme_financials"), q("SELECT SUM(receipts) FROM mart_agg_taluk_scheme_fy"), 1.0)
    eq("mart_agg_taluk_month salaries paid = salary bills", q("SELECT SUM(number_of_staff_salary_paid) FROM mart_fact_taluk_salary_bills"), q("SELECT SUM(number_of_staff_salary_paid) FROM mart_agg_taluk_month"))
    # cross-table: revenue monthly collection = DCB collection per FY; revenue heads add up to the DCB
    eq("monthly collection = DCB collection (all FYs)", q("SELECT SUM(total_collection) FROM mart_fact_gp_dcb"), q("SELECT SUM(collection_amount) FROM mart_fact_gp_monthly_collection"), 1.0)
    eq("revenue heads = DCB collection (all FYs)", q("SELECT SUM(total_collection) FROM mart_fact_gp_dcb"), q("SELECT SUM(total_collection) FROM mart_fact_gp_fee_type"), 1.0)
    eq("reconciliation checks all PASS", 0, q("SELECT COUNT(*) FROM ledger_reconciliation WHERE status <> 'PASS'"))
    # golden figures (reconciled in the handoff against independently written SQL)
    eq("golden: Mysuru FY 2024-25 demand (crore)", 457.57, round(q("SELECT SUM(total_demand) FROM mart_agg_taluk_fy WHERE fy = '2024-25' AND zilla_name = 'Mysuru'") / 1e7, 2))
    eq("golden: Mysuru FY 2024-25 collection (crore)", 124.30, round(q("SELECT SUM(total_collection) FROM mart_agg_taluk_fy WHERE fy = '2024-25' AND zilla_name = 'Mysuru'") / 1e7, 2))
    eq("golden: Karnataka FY 2024-25 collection (crore)", 1905.41, round(q("SELECT SUM(total_collection) FROM mart_agg_taluk_fy WHERE fy = '2024-25'") / 1e7, 2))
    eq("golden: GPs with every book closed FY 2024-25", 393, q("SELECT SUM(gps_all_books_closed) FROM mart_agg_taluk_fy WHERE fy = '2024-25'"))
    eq("golden: Revenue FY 2022-23 monthly collection (crore)", 1425.43, round(q("SELECT SUM(collection_amount) FROM mart_agg_taluk_month WHERE fy = '2022-23'") / 1e7, 2))
    eq("every mart column documented", q("SELECT SUM(n) FROM (SELECT COUNT(*) n FROM pragma_table_list t, pragma_table_info(t.name) WHERE t.name LIKE 'mart\\_%' ESCAPE '\\')"),
       q("SELECT COUNT(*) FROM semantic_column_doc"))
    for name, exp, act, ok in checks:
        con.execute("INSERT INTO ledger_build_check VALUES (?,?,?,?)", (name, str(exp), str(act), "PASS" if ok else "FAIL"))
    con.commit()
    fails = [c for c in checks if not c[3]]
    log(f"checks: {len(checks) - len(fails)} of {len(checks)} PASS")
    if fails:
        raise BuildError("checks failed: " + "; ".join(f"{n} (expected {e}, got {a})" for n, e, a, _ in fails))


# ------------------------------------------------------------------------------------------------ export
def stage_export(_con) -> None:
    subprocess.run([sys.executable, str(ROOT / "semantic" / "build_semantic_layer.py")], check=True)


FUNCS = {"sources": stage_sources, "staging": stage_staging, "core": stage_core, "reconcile": stage_reconcile, "mart": stage_mart,
         "semantic": stage_semantic, "ledger": stage_ledger, "checks": stage_checks, "export": stage_export}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default="sources", choices=STAGES)
    ap.add_argument("--to", dest="end", default="export", choices=STAGES)
    ap.add_argument("--only", choices=STAGES)
    a = ap.parse_args()
    stages = [a.only] if a.only else STAGES[STAGES.index(a.start):STAGES.index(a.end) + 1]
    fresh = stages[0] in FRESH and stages[0] == "sources"
    target = BUILDING if fresh else DB
    if fresh and target.exists():
        target.unlink()
    con = sqlite3.connect(f"file:{urllib.parse.quote(target.as_posix())}", uri=True)
    con.execute("PRAGMA journal_mode = OFF") if fresh else None
    con.execute("PRAGMA synchronous = OFF")
    con.execute("PRAGMA cache_size = -400000")
    con.execute("PRAGMA temp_store = MEMORY")
    try:
        for s in stages:
            if s == "export":
                continue
            t = time.time()
            FUNCS[s](con)
            _TIMINGS.append((s, time.time() - t))
        con.execute("CREATE TABLE IF NOT EXISTS ledger_build (run_at TEXT, stage TEXT, seconds REAL)")
        con.executemany("INSERT INTO ledger_build VALUES (datetime('now'), ?, ?)", [(s, round(x, 1)) for s, x in _TIMINGS])
        con.commit()
        for alias in SOURCES:
            try:
                con.execute(f"DETACH DATABASE {alias}")
            except sqlite3.Error:
                pass
        if fresh:
            con.execute("VACUUM") if os.environ.get("RDPR_VACUUM") else None
    except BuildError as exc:
        con.close()
        log(f"BUILD FAILED: {exc}")
        raise SystemExit(1)
    con.close()
    if fresh:
        if DB.exists():
            backup = DB.with_name("rdpr_star.previous.sqlite")
            shutil.move(DB, backup)
            log(f"previous database kept as {backup.relative_to(ROOT)}")
        shutil.move(BUILDING, DB)
        log(f"published {DB.relative_to(ROOT)} ({DB.stat().st_size / 1e9:.2f} GB)")
    if "export" in stages:
        t = time.time()
        stage_export(None)
        log(f"export: semantic layer and integrity manifest written ({time.time() - t:.1f}s)")
    log("done")


if __name__ == "__main__":
    main()

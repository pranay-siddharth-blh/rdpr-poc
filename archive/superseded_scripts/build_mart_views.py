"""
Adds the chatbot-facing mart_* views to DB/rdpr_star.sqlite (views only: no table or row of the star schema changes).

Why a mart layer: the chatbot's model may read ONLY mart_* objects. Each view is a fact (or summary) with the
names already joined in (gp_name, taluk_name, zilla_name, scheme_name ...) and readable period labels
(fy = '2024-25', month_label = 'APR-2022'), so a question rarely needs a join and cannot reach the raw star tables.
Nothing person-level is exposed: fact_hr_staff (names, dates of birth, individual salaries) has no mart view, only
the counts-by-designation view mart_fact_taluk_staff.

Idempotent: every mart_* view is dropped and re-created. Run after build_star_db.py / post_build_fixes_and_views.py.
usage:  python scripts/build_mart_views.py
"""
import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "DB" / "rdpr_star.sqlite"

# ---- reusable fragments --------------------------------------------------------------------------------------
GP_COLS = "f.gp_id, g.gp_name, g.taluk_id, t.taluk_name, g.zilla_id, z.zilla_name"
GP_JOIN = ("JOIN dim_gp g ON g.gp_id = f.gp_id JOIN dim_taluk t ON t.taluk_id = g.taluk_id "
           "JOIN dim_zilla z ON z.zilla_id = g.zilla_id")
TALUK_COLS = "f.taluk_id, t.taluk_name, t.zilla_id, z.zilla_name"
TALUK_JOIN = "JOIN dim_taluk t ON t.taluk_id = f.taluk_id JOIN dim_zilla z ON z.zilla_id = t.zilla_id"
FY_COL = "fy.fy_label AS fy"
FY_JOIN = "JOIN dim_fy fy ON fy.fy_id = f.fy_id"
MONTH_COLS = "f.month_id, UPPER(m.month_name) || '-' || m.calendar_year AS month_label, fy.fy_label AS fy"
MONTH_JOIN = "JOIN dim_month m ON m.month_id = f.month_id JOIN dim_fy fy ON fy.fy_id = m.fy_id"
SCHEME_COLS = "f.scheme_id, s.scheme_name, s.scheme_category"
SCHEME_JOIN = "JOIN dim_scheme s ON s.scheme_id = f.scheme_id"

V = {}

# ---- dimensions ----------------------------------------------------------------------------------------------
V["mart_dim_zilla"] = """
SELECT z.zilla_id, z.zilla_name, z.zilla_lgd_code,
       (SELECT COUNT(*) FROM dim_taluk t WHERE t.zilla_id = z.zilla_id) AS total_taluks,
       (SELECT COUNT(*) FROM dim_gp g WHERE g.zilla_id = z.zilla_id) AS total_gps
FROM dim_zilla z"""
V["mart_dim_taluk"] = """
SELECT t.taluk_id, t.taluk_name, t.taluk_lgd_code, t.zilla_id, z.zilla_name, t.total_gps
FROM dim_taluk t JOIN dim_zilla z ON z.zilla_id = t.zilla_id"""
V["mart_dim_gp"] = """
SELECT g.gp_id, g.gp_name, g.gp_lgd_code, g.taluk_id, t.taluk_name, g.zilla_id, z.zilla_name,
       g.taluk_assignment, g.size_class, g.performance_tier
FROM dim_gp g JOIN dim_taluk t ON t.taluk_id = g.taluk_id JOIN dim_zilla z ON z.zilla_id = g.zilla_id"""
V["mart_dim_fy"] = """
SELECT fy_label AS fy, fy_id, start_date, end_date, data_through, is_current,
       CASE WHEN data_through >= end_date THEN 1 ELSE 0 END AS is_complete
FROM dim_fy"""
V["mart_dim_month"] = """
SELECT m.month_id, UPPER(m.month_name) || '-' || m.calendar_year AS month_label, fy.fy_label AS fy,
       m.fy_month_no, m.calendar_year, m.calendar_month_no, m.month_name
FROM dim_month m JOIN dim_fy fy ON fy.fy_id = m.fy_id"""
V["mart_dim_scheme"] = """
SELECT s.scheme_id, s.scheme_name, s.scheme_category, a.fy_label AS active_from_fy, b.fy_label AS active_to_fy
FROM dim_scheme s LEFT JOIN dim_fy a ON a.fy_id = s.active_from_fy_id LEFT JOIN dim_fy b ON b.fy_id = s.active_to_fy_id
WHERE s.is_rollup = 0"""
V["mart_dim_fee_type"] = "SELECT fee_type_id, fee_type_name FROM dim_fee_type"
V["mart_dim_property_type"] = "SELECT property_type_id, property_type_name, report_category FROM dim_property_type"
V["mart_dim_staff_type"] = "SELECT staff_type_code, staff_type_name FROM dim_staff_type"

# ---- Finance & Accounting ------------------------------------------------------------------------------------
V["mart_fact_gp_year_closure"] = f"""
SELECT {FY_COL}, {GP_COLS}, {SCHEME_COLS}, f.is_closed, f.closed_on
FROM fact_fin_gp_year_closure f {FY_JOIN} {GP_JOIN} {SCHEME_JOIN}"""
V["mart_fact_gp_month_closure"] = f"""
SELECT {MONTH_COLS}, {GP_COLS}, {SCHEME_COLS}, f.is_closed, f.closed_on, f.days_after_month_end
FROM fact_fin_gp_month_closure f {MONTH_JOIN} {GP_JOIN} {SCHEME_JOIN}"""
V["mart_fact_gp_scheme_financials"] = f"""
SELECT {MONTH_COLS}, {GP_COLS}, {SCHEME_COLS}, f.opening_balance, f.receipts, f.expenditure, f.closing_balance
FROM fact_fin_gp_scheme_financials f {MONTH_JOIN} {GP_JOIN} {SCHEME_JOIN}"""
V["mart_fact_taluk_daybook_closure"] = f"""
SELECT f.date_id AS date, d.month_id, UPPER(m.month_name) || '-' || m.calendar_year AS month_label, fy.fy_label AS fy,
       {TALUK_COLS}, {SCHEME_COLS}, f.total_gps, f.gps_closed, f.gps_pending, f.closure_pct
FROM fact_fin_daybook_closure f JOIN dim_date d ON d.date_id = f.date_id JOIN dim_month m ON m.month_id = d.month_id
JOIN dim_fy fy ON fy.fy_id = d.fy_id {TALUK_JOIN} {SCHEME_JOIN}"""

# ---- Revenue -------------------------------------------------------------------------------------------------
V["mart_fact_gp_dcb"] = f"""
SELECT {FY_COL}, {GP_COLS}, f.arrears, f.year_demand, f.total_demand, f.total_collection, f.adjustments, f.balance
FROM fact_rev_dcb_register f {FY_JOIN} {GP_JOIN}"""
V["mart_fact_gp_fee_type"] = f"""
SELECT {FY_COL}, {GP_COLS}, f.fee_type_id, ft.fee_type_name, f.arrears, f.year_demand, f.total_demand,
       f.total_collection, f.adjustments, f.balance
FROM fact_rev_taxes_fees f {FY_JOIN} {GP_JOIN} JOIN dim_fee_type ft ON ft.fee_type_id = f.fee_type_id"""
V["mart_fact_gp_monthly_collection"] = f"""
SELECT {MONTH_COLS}, {GP_COLS}, f.fee_type_id, ft.fee_type_name, f.collection_amount
FROM fact_rev_gp_monthly_collection f {MONTH_JOIN} {GP_JOIN} JOIN dim_fee_type ft ON ft.fee_type_id = f.fee_type_id"""
V["mart_fact_gp_demand_by_property_type"] = f"""
SELECT {FY_COL}, {GP_COLS}, f.property_type_id, p.property_type_name, p.report_category, f.number_of_properties,
       f.arrears, f.year_demand, f.total_demand, f.total_collection, f.adjustments, f.balance
FROM fact_rev_demand_statistics f {FY_JOIN} {GP_JOIN} JOIN dim_property_type p ON p.property_type_id = f.property_type_id"""
V["mart_fact_gp_property_counts"] = f"""
SELECT {FY_COL}, {GP_COLS}, f.number_of_properties, f.agro_based_production_units, f.commercial, f.community,
       f.government, f.industrial, f.non_residential, f.religious, f.residential, f.commercial_cum_residential,
       f.renewable, f.telecom_tower, f.other_unclassified
FROM fact_rev_property_type_stats f {FY_JOIN} {GP_JOIN}"""

# ---- HRMS (no person-level view) -----------------------------------------------------------------------------
V["mart_fact_gp_eo_approval"] = f"""
SELECT {FY_COL}, {GP_COLS}, f.snapshot_date, f.staff_registrations_sent_to_eo, f.staff_approved_by_eo,
       f.staff_approval_pending_at_eo, f.staff_registrations_rejected_by_eo, f.staff_resent_for_approval_to_eo
FROM fact_hr_eo_approval f {FY_JOIN} {GP_JOIN}"""
V["mart_fact_gp_er_registration"] = f"""
SELECT {FY_COL}, {GP_COLS}, f.snapshot_date, f.total_seats, f.total_elected_members, f.total_adhyaksha_president,
       f.total_upadhyaksha
FROM fact_hr_er_registration f {FY_JOIN} {GP_JOIN}"""
V["mart_fact_taluk_salary_bills"] = f"""
SELECT {MONTH_COLS}, {TALUK_COLS}, f.staff_type_code, st.staff_type_name, f.total_number_of_staff,
       f.number_of_gps_generated_main_bill, f.number_of_main_bill_generated, f.number_of_main_bill_pdo_signed,
       f.number_of_main_bill_president_signed, f.number_of_main_bill_processed_by_bank,
       f.number_of_auxiliary_bill_generated, f.number_of_auxiliary_bill_pdo_signed,
       f.number_of_auxiliary_bill_president_signed, f.number_of_auxiliary_bill_processed_by_bank,
       f.number_of_staff_salary_paid, f.number_of_staff_salary_rejected_by_bank
FROM fact_hr_salary_bills f {MONTH_JOIN} {TALUK_JOIN} JOIN dim_staff_type st ON st.staff_type_code = f.staff_type_code"""
V["mart_fact_taluk_staff"] = """
SELECT g.taluk_id, t.taluk_name, g.zilla_id, z.zilla_name, s.staff_type_code, st.staff_type_name,
       dd.designation_name, s.gender, s.employment_status, s.approval_status,
       COUNT(*) AS staff_count, SUM(s.monthly_gross_salary_inr) AS monthly_gross_salary_inr
FROM fact_hr_staff s JOIN dim_gp g ON g.gp_id = s.gp_id JOIN dim_taluk t ON t.taluk_id = g.taluk_id
JOIN dim_zilla z ON z.zilla_id = g.zilla_id JOIN dim_staff_type st ON st.staff_type_code = s.staff_type_code
JOIN dim_designation dd ON dd.designation_id = s.designation_id
GROUP BY g.taluk_id, t.taluk_name, g.zilla_id, z.zilla_name, s.staff_type_code, st.staff_type_name,
         dd.designation_name, s.gender, s.employment_status, s.approval_status"""

# ---- cross-module summaries (one row per place per FY; each module already aggregated to that grain) ----------
V["mart_summary_gp_year"] = """
SELECT fy.fy_label AS fy, v.gp_id, v.gp_name, v.taluk_id, t.taluk_name, v.zilla_id, z.zilla_name,
       v.schemes_total, v.schemes_closed, v.all_books_closed, v.total_demand, v.total_collection, v.revenue_balance,
       v.collection_pct, v.staff_approved_by_eo, v.staff_approval_pending_at_eo, v.staff_registrations_rejected_by_eo,
       v.total_seats, v.total_elected_members
FROM vw_gp_year_summary v JOIN dim_fy fy ON fy.fy_id = v.fy_id JOIN dim_taluk t ON t.taluk_id = v.taluk_id
JOIN dim_zilla z ON z.zilla_id = v.zilla_id"""
V["mart_summary_taluk_year"] = """
SELECT fy.fy_label AS fy, v.taluk_id, t.taluk_name, t.zilla_id, z.zilla_name, v.total_gps, v.gps_all_books_closed,
       v.all_books_closed_pct, v.scheme_books_closed_pct, v.total_demand, v.total_collection, v.revenue_balance,
       v.collection_pct, v.staff_approved_by_eo, v.staff_approval_pending_at_eo, v.total_elected_members, v.total_seats
FROM vw_taluk_year_summary v JOIN dim_fy fy ON fy.fy_id = v.fy_id JOIN dim_taluk t ON t.taluk_id = v.taluk_id
JOIN dim_zilla z ON z.zilla_id = t.zilla_id"""
V["mart_summary_zilla_year"] = """
SELECT fy.fy_label AS fy, v.zilla_id, z.zilla_name, v.total_gps, v.gps_all_books_closed, v.all_books_closed_pct,
       v.scheme_books_closed_pct, v.total_demand, v.total_collection, v.revenue_balance, v.collection_pct,
       v.staff_approved_by_eo, v.staff_approval_pending_at_eo, v.total_elected_members, v.total_seats
FROM vw_zilla_year_summary v JOIN dim_fy fy ON fy.fy_id = v.fy_id JOIN dim_zilla z ON z.zilla_id = v.zilla_id"""
V["mart_summary_state_year"] = """
SELECT fy, SUM(total_gps) AS total_gps, SUM(gps_all_books_closed) AS gps_all_books_closed,
       ROUND(100.0 * SUM(gps_all_books_closed) / NULLIF(SUM(total_gps), 0), 1) AS all_books_closed_pct,
       SUM(total_demand) AS total_demand, SUM(total_collection) AS total_collection, SUM(revenue_balance) AS revenue_balance,
       ROUND(100.0 * SUM(total_collection) / NULLIF(SUM(total_demand), 0), 1) AS collection_pct,
       SUM(staff_approved_by_eo) AS staff_approved_by_eo, SUM(staff_approval_pending_at_eo) AS staff_approval_pending_at_eo,
       SUM(total_elected_members) AS total_elected_members, SUM(total_seats) AS total_seats
FROM mart_summary_zilla_year GROUP BY fy"""


def main() -> None:
    con = sqlite3.connect(DB)
    old = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='view' AND name LIKE 'mart\\_%' ESCAPE '\\'")]
    for name in old:
        con.execute(f"DROP VIEW {name}")
    for name, sql in V.items():
        con.execute(f"CREATE VIEW {name} AS {sql.strip()}")
    con.commit()
    bad = []
    for name in V:                       # every view must compile and be readable
        try:
            con.execute(f"SELECT * FROM {name} LIMIT 1").fetchall()
        except sqlite3.Error as exc:
            bad.append((name, str(exc)))
    con.execute("INSERT OR REPLACE INTO build_notes VALUES ('mart_views', date('now'), ?)",
                (f"{len(V)} mart_* views for the chatbot (scripts/build_mart_views.py)",))
    con.commit()
    con.close()
    print(f"created {len(V)} mart views ({len(old)} replaced)")
    if bad:
        raise SystemExit(f"views that failed: {bad}")


if __name__ == "__main__":
    main()

"""
RDPR mart layer (L5): the only tables the AI and the dashboard read. Physical tables built from the core layer
(KPCL rule 1: no views over million-row facts), each with one grain, the names already joined in (zilla, taluk,
GP, scheme, revenue head ...), readable periods (fy = '2024-25', month_label = 'APR-2024') and indexes on the
columns questions filter by.

Three kinds of table:
  mart_dim_*      lookups with display helpers (counts of taluks / GPs)
  mart_fact_*     one table per source fact, at the source grain (GP, taluk, day, month, FY)
  mart_agg_*      pre-summed taluk x month / taluk x FY tables: the dashboard, the reports and statewide / zilla
                  questions read these (a zilla or the state is a SUM over its taluks), so every figure is a few
                  thousand rows away instead of millions
  mart_summary_*  Finance + Revenue + HRMS side by side, one row per place and FY

MART is an ordered list of (name, SELECT, indexes); build_warehouse.py materialises each one with typed columns.
"""

GP_COLS = "f.gp_id, g.gp_name, g.taluk_id, t.taluk_name, g.zilla_id, z.zilla_name"
GP_JOIN = ("JOIN dim_gp g ON g.gp_id = f.gp_id JOIN dim_taluk t ON t.taluk_id = g.taluk_id "
           "JOIN dim_zilla z ON z.zilla_id = g.zilla_id")
TALUK_COLS = "f.taluk_id, t.taluk_name, t.zilla_id, z.zilla_name"
TALUK_JOIN = "JOIN dim_taluk t ON t.taluk_id = f.taluk_id JOIN dim_zilla z ON z.zilla_id = t.zilla_id"
FY_COL, FY_JOIN = "fy.fy_label AS fy", "JOIN dim_fy fy ON fy.fy_id = f.fy_id"
MONTH_COLS = "f.month_id, UPPER(m.month_name) || '-' || m.calendar_year AS month_label, fy.fy_label AS fy"
MONTH_JOIN = "JOIN dim_month m ON m.month_id = f.month_id JOIN dim_fy fy ON fy.fy_id = m.fy_id"
SCHEME_COLS, SCHEME_JOIN = "f.scheme_id, s.scheme_name, s.scheme_category", "JOIN dim_scheme s ON s.scheme_id = f.scheme_id"

# GP-level facts are queried by place, period and scheme / head
GP_IDX = ["fy", "zilla_name, fy", "taluk_name, fy", "gp_id"]
MONTH_IDX = ["fy", "month_id", "zilla_name, fy", "taluk_name, fy", "gp_id"]

MART: list[tuple[str, str, list[str]]] = [
    # ---------------------------------------------------------------- dimensions
    ("mart_dim_zilla", """
SELECT z.zilla_id, z.zilla_name, z.zilla_lgd_code,
       (SELECT COUNT(*) FROM dim_taluk t WHERE t.zilla_id = z.zilla_id) AS total_taluks,
       (SELECT COUNT(*) FROM dim_gp g WHERE g.zilla_id = z.zilla_id) AS total_gps
FROM dim_zilla z""", ["zilla_name"]),
    ("mart_dim_taluk", """
SELECT t.taluk_id, t.taluk_name, t.taluk_lgd_code, t.zilla_id, z.zilla_name, t.total_gps
FROM dim_taluk t JOIN dim_zilla z ON z.zilla_id = t.zilla_id""", ["taluk_name", "zilla_name"]),
    ("mart_dim_gp", """
SELECT g.gp_id, g.gp_name, g.gp_lgd_code, g.taluk_id, t.taluk_name, g.zilla_id, z.zilla_name,
       g.taluk_assignment, g.size_class, g.performance_tier
FROM dim_gp g JOIN dim_taluk t ON t.taluk_id = g.taluk_id JOIN dim_zilla z ON z.zilla_id = g.zilla_id""",
     ["gp_name", "taluk_name", "zilla_name"]),
    ("mart_dim_fy", """
SELECT fy_label AS fy, fy_id, start_date, end_date, data_through, is_current,
       CASE WHEN data_through >= end_date THEN 1 ELSE 0 END AS is_complete
FROM dim_fy""", []),
    ("mart_dim_month", """
SELECT m.month_id, UPPER(m.month_name) || '-' || m.calendar_year AS month_label, fy.fy_label AS fy,
       m.fy_month_no, m.calendar_year, m.calendar_month_no, m.month_name
FROM dim_month m JOIN dim_fy fy ON fy.fy_id = m.fy_id""", ["month_label"]),
    ("mart_dim_scheme", """
SELECT s.scheme_id, s.scheme_name, s.scheme_category, a.fy_label AS active_from_fy, b.fy_label AS active_to_fy
FROM dim_scheme s LEFT JOIN dim_fy a ON a.fy_id = s.active_from_fy_id LEFT JOIN dim_fy b ON b.fy_id = s.active_to_fy_id
WHERE s.is_rollup = 0""", []),
    ("mart_dim_fee_type", "SELECT fee_type_id, fee_type_name FROM dim_fee_type", []),
    ("mart_dim_property_type", "SELECT property_type_id, property_type_name, report_category FROM dim_property_type", []),
    ("mart_dim_staff_type", "SELECT staff_type_code, staff_type_name FROM dim_staff_type", []),

    # ---------------------------------------------------------------- Finance & Accounting (GP / taluk grain)
    ("mart_fact_gp_year_closure", f"""
SELECT {FY_COL}, {GP_COLS}, {SCHEME_COLS}, f.is_closed, f.closed_on
FROM fact_fin_gp_year_closure f {FY_JOIN} {GP_JOIN} {SCHEME_JOIN}""", GP_IDX + ["scheme_name, fy"]),
    ("mart_fact_gp_month_closure", f"""
SELECT {MONTH_COLS}, {GP_COLS}, {SCHEME_COLS}, f.is_closed, f.closed_on, f.days_after_month_end
FROM fact_fin_gp_month_closure f {MONTH_JOIN} {GP_JOIN} {SCHEME_JOIN}""", MONTH_IDX + ["scheme_name, fy"]),
    ("mart_fact_gp_scheme_financials", f"""
SELECT {MONTH_COLS}, {GP_COLS}, {SCHEME_COLS}, f.opening_balance, f.receipts, f.expenditure, f.closing_balance
FROM fact_fin_gp_scheme_financials f {MONTH_JOIN} {GP_JOIN} {SCHEME_JOIN}""", MONTH_IDX + ["scheme_name, fy"]),
    ("mart_fact_taluk_daybook_closure", f"""
SELECT f.date_id AS date, d.month_id, UPPER(m.month_name) || '-' || m.calendar_year AS month_label, fy.fy_label AS fy,
       {TALUK_COLS}, {SCHEME_COLS}, f.total_gps, f.gps_closed, f.gps_pending, f.closure_pct
FROM fact_fin_daybook_closure f JOIN dim_date d ON d.date_id = f.date_id JOIN dim_month m ON m.month_id = d.month_id
JOIN dim_fy fy ON fy.fy_id = d.fy_id {TALUK_JOIN} {SCHEME_JOIN}""", ["date", "fy", "zilla_name, date", "taluk_name, date", "scheme_name, date"]),

    # ---------------------------------------------------------------- Revenue (GP grain)
    ("mart_fact_gp_dcb", f"""
SELECT {FY_COL}, {GP_COLS}, f.arrears, f.year_demand, f.total_demand, f.total_collection, f.adjustments, f.balance
FROM fact_rev_dcb_register f {FY_JOIN} {GP_JOIN}""", GP_IDX),
    ("mart_fact_gp_fee_type", f"""
SELECT {FY_COL}, {GP_COLS}, f.fee_type_id, ft.fee_type_name, f.arrears, f.year_demand, f.total_demand,
       f.total_collection, f.adjustments, f.balance
FROM fact_rev_taxes_fees f {FY_JOIN} {GP_JOIN} JOIN dim_fee_type ft ON ft.fee_type_id = f.fee_type_id""", GP_IDX + ["fee_type_name, fy"]),
    ("mart_fact_gp_monthly_collection", f"""
SELECT {MONTH_COLS}, {GP_COLS}, f.fee_type_id, ft.fee_type_name, f.collection_amount
FROM fact_rev_gp_monthly_collection f {MONTH_JOIN} {GP_JOIN} JOIN dim_fee_type ft ON ft.fee_type_id = f.fee_type_id""", MONTH_IDX),
    ("mart_fact_gp_demand_by_property_type", f"""
SELECT {FY_COL}, {GP_COLS}, f.property_type_id, p.property_type_name, p.report_category, f.number_of_properties,
       f.arrears, f.year_demand, f.total_demand, f.total_collection, f.adjustments, f.balance
FROM fact_rev_demand_statistics f {FY_JOIN} {GP_JOIN} JOIN dim_property_type p ON p.property_type_id = f.property_type_id""",
     GP_IDX + ["report_category, fy"]),
    ("mart_fact_gp_property_counts", f"""
SELECT {FY_COL}, {GP_COLS}, f.number_of_properties, f.agro_based_production_units, f.commercial, f.community,
       f.government, f.industrial, f.non_residential, f.religious, f.residential, f.commercial_cum_residential,
       f.renewable, f.telecom_tower, f.other_unclassified
FROM fact_rev_property_type_stats f {FY_JOIN} {GP_JOIN}""", GP_IDX),

    # ---------------------------------------------------------------- HRMS (no person-level table)
    ("mart_fact_gp_eo_approval", f"""
SELECT {FY_COL}, {GP_COLS}, f.snapshot_date, f.staff_registrations_sent_to_eo, f.staff_approved_by_eo,
       f.staff_approval_pending_at_eo, f.staff_registrations_rejected_by_eo, f.staff_resent_for_approval_to_eo
FROM fact_hr_eo_approval f {FY_JOIN} {GP_JOIN}""", GP_IDX),
    ("mart_fact_gp_er_registration", f"""
SELECT {FY_COL}, {GP_COLS}, f.snapshot_date, f.total_seats, f.total_elected_members, f.total_adhyaksha_president,
       f.total_upadhyaksha
FROM fact_hr_er_registration f {FY_JOIN} {GP_JOIN}""", GP_IDX),
    ("mart_fact_taluk_salary_bills", f"""
SELECT {MONTH_COLS}, {TALUK_COLS}, f.staff_type_code, st.staff_type_name, f.total_number_of_staff,
       f.number_of_gps_generated_main_bill, f.number_of_main_bill_generated, f.number_of_main_bill_pdo_signed,
       f.number_of_main_bill_president_signed, f.number_of_main_bill_processed_by_bank,
       f.number_of_auxiliary_bill_generated, f.number_of_auxiliary_bill_pdo_signed,
       f.number_of_auxiliary_bill_president_signed, f.number_of_auxiliary_bill_processed_by_bank,
       f.number_of_staff_salary_paid, f.number_of_staff_salary_rejected_by_bank
FROM fact_hr_salary_bills f {MONTH_JOIN} {TALUK_JOIN} JOIN dim_staff_type st ON st.staff_type_code = f.staff_type_code""",
     ["fy", "month_id", "zilla_name, fy", "taluk_name, fy"]),
    ("mart_fact_taluk_staff", """
SELECT g.taluk_id, t.taluk_name, g.zilla_id, z.zilla_name, s.staff_type_code, st.staff_type_name,
       dd.designation_name, s.gender, s.employment_status, s.approval_status,
       COUNT(*) AS staff_count, SUM(s.monthly_gross_salary_inr) AS monthly_gross_salary_inr
FROM fact_hr_staff s JOIN dim_gp g ON g.gp_id = s.gp_id JOIN dim_taluk t ON t.taluk_id = g.taluk_id
JOIN dim_zilla z ON z.zilla_id = g.zilla_id JOIN dim_staff_type st ON st.staff_type_code = s.staff_type_code
JOIN dim_designation dd ON dd.designation_id = s.designation_id
GROUP BY g.taluk_id, t.taluk_name, g.zilla_id, z.zilla_name, s.staff_type_code, st.staff_type_name,
         dd.designation_name, s.gender, s.employment_status, s.approval_status""", ["zilla_name", "taluk_name", "employment_status"]),

    # ---------------------------------------------------------------- cross-module summaries (one row per place per FY)
    ("mart_summary_gp_year", """
SELECT fy.fy_label AS fy, g.gp_id, g.gp_name, g.taluk_id, t.taluk_name, g.zilla_id, z.zilla_name,
       fin.schemes_total, fin.schemes_closed, fin.all_books_closed,
       r.total_demand, r.total_collection, r.balance AS revenue_balance,
       ROUND(100.0 * r.total_collection / NULLIF(r.total_demand, 0), 1) AS collection_pct,
       eo.staff_approved_by_eo, eo.staff_approval_pending_at_eo, eo.staff_registrations_rejected_by_eo,
       er.total_seats, er.total_elected_members
FROM dim_gp g CROSS JOIN dim_fy fy
JOIN dim_taluk t ON t.taluk_id = g.taluk_id JOIN dim_zilla z ON z.zilla_id = g.zilla_id
LEFT JOIN (SELECT fy_id, gp_id, COUNT(*) AS schemes_total, SUM(is_closed) AS schemes_closed, MIN(is_closed) AS all_books_closed
           FROM fact_fin_gp_year_closure GROUP BY fy_id, gp_id) fin ON fin.fy_id = fy.fy_id AND fin.gp_id = g.gp_id
LEFT JOIN fact_rev_dcb_register r ON r.fy_id = fy.fy_id AND r.gp_id = g.gp_id
LEFT JOIN fact_hr_eo_approval eo ON eo.fy_id = fy.fy_id AND eo.gp_id = g.gp_id
LEFT JOIN fact_hr_er_registration er ON er.fy_id = fy.fy_id AND er.gp_id = g.gp_id
WHERE fy.fy_id <> 'FY2122'""", GP_IDX),
    ("mart_summary_taluk_year", """
SELECT fy, taluk_id, taluk_name, zilla_id, zilla_name, COUNT(*) AS total_gps, SUM(all_books_closed) AS gps_all_books_closed,
       ROUND(100.0 * SUM(all_books_closed) / COUNT(*), 1) AS all_books_closed_pct,
       ROUND(100.0 * SUM(schemes_closed) / SUM(schemes_total), 1) AS scheme_books_closed_pct,
       SUM(total_demand) AS total_demand, SUM(total_collection) AS total_collection, SUM(revenue_balance) AS revenue_balance,
       ROUND(100.0 * SUM(total_collection) / NULLIF(SUM(total_demand), 0), 1) AS collection_pct,
       SUM(staff_approved_by_eo) AS staff_approved_by_eo, SUM(staff_approval_pending_at_eo) AS staff_approval_pending_at_eo,
       SUM(total_elected_members) AS total_elected_members, SUM(total_seats) AS total_seats
FROM mart_summary_gp_year GROUP BY fy, taluk_id, taluk_name, zilla_id, zilla_name""", ["fy", "taluk_name, fy", "zilla_name, fy"]),
    ("mart_summary_zilla_year", """
SELECT fy, zilla_id, zilla_name, COUNT(*) AS total_gps, SUM(all_books_closed) AS gps_all_books_closed,
       ROUND(100.0 * SUM(all_books_closed) / COUNT(*), 1) AS all_books_closed_pct,
       ROUND(100.0 * SUM(schemes_closed) / SUM(schemes_total), 1) AS scheme_books_closed_pct,
       SUM(total_demand) AS total_demand, SUM(total_collection) AS total_collection, SUM(revenue_balance) AS revenue_balance,
       ROUND(100.0 * SUM(total_collection) / NULLIF(SUM(total_demand), 0), 1) AS collection_pct,
       SUM(staff_approved_by_eo) AS staff_approved_by_eo, SUM(staff_approval_pending_at_eo) AS staff_approval_pending_at_eo,
       SUM(total_elected_members) AS total_elected_members, SUM(total_seats) AS total_seats
FROM mart_summary_gp_year GROUP BY fy, zilla_id, zilla_name""", ["fy", "zilla_name, fy"]),
    ("mart_summary_state_year", """
SELECT fy, SUM(total_gps) AS total_gps, SUM(gps_all_books_closed) AS gps_all_books_closed,
       ROUND(100.0 * SUM(gps_all_books_closed) / NULLIF(SUM(total_gps), 0), 1) AS all_books_closed_pct,
       SUM(total_demand) AS total_demand, SUM(total_collection) AS total_collection, SUM(revenue_balance) AS revenue_balance,
       ROUND(100.0 * SUM(total_collection) / NULLIF(SUM(total_demand), 0), 1) AS collection_pct,
       SUM(staff_approved_by_eo) AS staff_approved_by_eo, SUM(staff_approval_pending_at_eo) AS staff_approval_pending_at_eo,
       SUM(total_elected_members) AS total_elected_members, SUM(total_seats) AS total_seats
FROM mart_summary_zilla_year GROUP BY fy""", ["fy"]),

    # ---------------------------------------------------------------- pre-summed taluk tables (dashboard, reports, statewide questions)
    ("mart_agg_taluk_month", """
WITH grid AS (SELECT m.month_id, UPPER(m.month_name) || '-' || m.calendar_year AS month_label, fy.fy_label AS fy, m.fy_month_no,
                     t.taluk_id, t.taluk_name, t.zilla_id, z.zilla_name
              FROM dim_month m JOIN dim_fy fy ON fy.fy_id = m.fy_id CROSS JOIN dim_taluk t JOIN dim_zilla z ON z.zilla_id = t.zilla_id
              WHERE m.month_id <= (SELECT MAX(month_id) FROM fact_hr_salary_bills)),
     coll AS (SELECT f.month_id, g.taluk_id, SUM(f.collection_amount) AS collection_amount
              FROM fact_rev_gp_monthly_collection f JOIN dim_gp g ON g.gp_id = f.gp_id GROUP BY f.month_id, g.taluk_id),
     fin AS (SELECT f.month_id, g.taluk_id, SUM(f.receipts) AS receipts, SUM(f.expenditure) AS expenditure,
                    SUM(f.closing_balance) AS closing_balance
             FROM fact_fin_gp_scheme_financials f JOIN dim_gp g ON g.gp_id = f.gp_id GROUP BY f.month_id, g.taluk_id),
     clo AS (SELECT f.month_id, g.taluk_id, SUM(f.is_closed) AS month_books_closed, COUNT(*) AS month_books
             FROM fact_fin_gp_month_closure f JOIN dim_gp g ON g.gp_id = f.gp_id GROUP BY f.month_id, g.taluk_id),
     sal AS (SELECT month_id, taluk_id, SUM(total_number_of_staff) AS total_number_of_staff,
                    SUM(number_of_staff_salary_paid) AS number_of_staff_salary_paid,
                    SUM(number_of_staff_salary_rejected_by_bank) AS number_of_staff_salary_rejected_by_bank
             FROM fact_hr_salary_bills GROUP BY month_id, taluk_id)
SELECT grid.*, coll.collection_amount, fin.receipts, fin.expenditure, fin.closing_balance, clo.month_books_closed, clo.month_books,
       sal.total_number_of_staff, sal.number_of_staff_salary_paid, sal.number_of_staff_salary_rejected_by_bank
FROM grid LEFT JOIN coll USING (month_id, taluk_id) LEFT JOIN fin USING (month_id, taluk_id)
LEFT JOIN clo USING (month_id, taluk_id) LEFT JOIN sal USING (month_id, taluk_id)""", ["fy", "zilla_name, fy", "taluk_name, fy", "month_id"]),
    ("mart_agg_taluk_fy", """
WITH grid AS (SELECT fy.fy_id, fy.fy_label AS fy, t.taluk_id, t.taluk_name, t.zilla_id, z.zilla_name,
                     (SELECT COUNT(*) FROM dim_gp g WHERE g.taluk_id = t.taluk_id) AS total_gps
              FROM dim_fy fy CROSS JOIN dim_taluk t JOIN dim_zilla z ON z.zilla_id = t.zilla_id WHERE fy.fy_id <> 'FY2122'),
     dcb AS (SELECT f.fy_id, g.taluk_id, SUM(arrears) AS arrears, SUM(year_demand) AS year_demand, SUM(total_demand) AS total_demand,
                    SUM(total_collection) AS total_collection, SUM(adjustments) AS adjustments, SUM(balance) AS balance
             FROM fact_rev_dcb_register f JOIN dim_gp g ON g.gp_id = f.gp_id GROUP BY f.fy_id, g.taluk_id),
     prop AS (SELECT f.fy_id, g.taluk_id, SUM(number_of_properties) AS number_of_properties
              FROM fact_rev_property_type_stats f JOIN dim_gp g ON g.gp_id = f.gp_id GROUP BY f.fy_id, g.taluk_id),
     yc AS (SELECT f.fy_id, g.taluk_id, SUM(is_closed) AS scheme_books_closed, COUNT(*) AS scheme_books
            FROM fact_fin_gp_year_closure f JOIN dim_gp g ON g.gp_id = f.gp_id GROUP BY f.fy_id, g.taluk_id),
     allc AS (SELECT fin.fy_id, g.taluk_id, SUM(fin.all_closed) AS gps_all_books_closed
              FROM (SELECT fy_id, gp_id, MIN(is_closed) AS all_closed FROM fact_fin_gp_year_closure GROUP BY fy_id, gp_id) fin
              JOIN dim_gp g ON g.gp_id = fin.gp_id GROUP BY fin.fy_id, g.taluk_id),
     money AS (SELECT m.fy_id, g.taluk_id, SUM(f.receipts) AS receipts, SUM(f.expenditure) AS expenditure
               FROM fact_fin_gp_scheme_financials f JOIN dim_month m ON m.month_id = f.month_id JOIN dim_gp g ON g.gp_id = f.gp_id
               GROUP BY m.fy_id, g.taluk_id),
     eo AS (SELECT f.fy_id, g.taluk_id, SUM(staff_registrations_sent_to_eo) AS staff_registrations_sent_to_eo,
                   SUM(staff_approved_by_eo) AS staff_approved_by_eo, SUM(staff_approval_pending_at_eo) AS staff_approval_pending_at_eo,
                   SUM(staff_registrations_rejected_by_eo) AS staff_registrations_rejected_by_eo,
                   SUM(staff_resent_for_approval_to_eo) AS staff_resent_for_approval_to_eo
            FROM fact_hr_eo_approval f JOIN dim_gp g ON g.gp_id = f.gp_id GROUP BY f.fy_id, g.taluk_id),
     er AS (SELECT f.fy_id, g.taluk_id, SUM(total_seats) AS total_seats, SUM(total_elected_members) AS total_elected_members,
                   SUM(total_adhyaksha_president) AS total_adhyaksha_president, SUM(total_upadhyaksha) AS total_upadhyaksha
            FROM fact_hr_er_registration f JOIN dim_gp g ON g.gp_id = f.gp_id GROUP BY f.fy_id, g.taluk_id)
SELECT grid.fy, grid.taluk_id, grid.taluk_name, grid.zilla_id, grid.zilla_name, grid.total_gps,
       dcb.arrears, dcb.year_demand, dcb.total_demand, dcb.total_collection, dcb.adjustments, dcb.balance, prop.number_of_properties,
       yc.scheme_books_closed, yc.scheme_books, allc.gps_all_books_closed, money.receipts, money.expenditure,
       eo.staff_registrations_sent_to_eo, eo.staff_approved_by_eo, eo.staff_approval_pending_at_eo,
       eo.staff_registrations_rejected_by_eo, eo.staff_resent_for_approval_to_eo,
       er.total_seats, er.total_elected_members, er.total_adhyaksha_president, er.total_upadhyaksha
FROM grid LEFT JOIN dcb USING (fy_id, taluk_id) LEFT JOIN prop USING (fy_id, taluk_id) LEFT JOIN yc USING (fy_id, taluk_id)
LEFT JOIN allc USING (fy_id, taluk_id) LEFT JOIN money USING (fy_id, taluk_id) LEFT JOIN eo USING (fy_id, taluk_id)
LEFT JOIN er USING (fy_id, taluk_id)""", ["fy", "zilla_name, fy", "taluk_name, fy"]),
    ("mart_agg_taluk_fee_type_fy", """
SELECT fy.fy_label AS fy, t.taluk_id, t.taluk_name, t.zilla_id, z.zilla_name, ft.fee_type_id, ft.fee_type_name,
       SUM(f.arrears) AS arrears, SUM(f.year_demand) AS year_demand, SUM(f.total_demand) AS total_demand,
       SUM(f.total_collection) AS total_collection, SUM(f.adjustments) AS adjustments, SUM(f.balance) AS balance
FROM fact_rev_taxes_fees f JOIN dim_fy fy ON fy.fy_id = f.fy_id JOIN dim_gp g ON g.gp_id = f.gp_id
JOIN dim_taluk t ON t.taluk_id = g.taluk_id JOIN dim_zilla z ON z.zilla_id = t.zilla_id JOIN dim_fee_type ft ON ft.fee_type_id = f.fee_type_id
GROUP BY fy.fy_label, t.taluk_id, t.taluk_name, t.zilla_id, z.zilla_name, ft.fee_type_id, ft.fee_type_name""",
     ["fy", "zilla_name, fy", "taluk_name, fy"]),
    ("mart_agg_taluk_property_fy", """
SELECT fy.fy_label AS fy, t.taluk_id, t.taluk_name, t.zilla_id, z.zilla_name, p.report_category,
       SUM(f.number_of_properties) AS number_of_properties, SUM(f.total_demand) AS total_demand,
       SUM(f.total_collection) AS total_collection, SUM(f.balance) AS balance
FROM fact_rev_demand_statistics f JOIN dim_fy fy ON fy.fy_id = f.fy_id JOIN dim_gp g ON g.gp_id = f.gp_id
JOIN dim_taluk t ON t.taluk_id = g.taluk_id JOIN dim_zilla z ON z.zilla_id = t.zilla_id
JOIN dim_property_type p ON p.property_type_id = f.property_type_id
GROUP BY fy.fy_label, t.taluk_id, t.taluk_name, t.zilla_id, z.zilla_name, p.report_category""", ["fy", "zilla_name, fy", "taluk_name, fy"]),
    ("mart_agg_taluk_scheme_fy", """
WITH yc AS (SELECT f.fy_id, g.taluk_id, f.scheme_id, SUM(f.is_closed) AS scheme_books_closed, COUNT(*) AS scheme_books
            FROM fact_fin_gp_year_closure f JOIN dim_gp g ON g.gp_id = f.gp_id GROUP BY f.fy_id, g.taluk_id, f.scheme_id),
     money AS (SELECT m.fy_id, g.taluk_id, f.scheme_id, SUM(f.receipts) AS receipts, SUM(f.expenditure) AS expenditure
               FROM fact_fin_gp_scheme_financials f JOIN dim_month m ON m.month_id = f.month_id JOIN dim_gp g ON g.gp_id = f.gp_id
               GROUP BY m.fy_id, g.taluk_id, f.scheme_id),
     last AS (SELECT m.fy_id, MAX(f.month_id) AS month_id FROM fact_fin_gp_scheme_financials f JOIN dim_month m ON m.month_id = f.month_id
              GROUP BY m.fy_id),
     clos AS (SELECT last.fy_id, g.taluk_id, f.scheme_id, SUM(f.closing_balance) AS closing_balance
              FROM fact_fin_gp_scheme_financials f JOIN last ON last.month_id = f.month_id JOIN dim_gp g ON g.gp_id = f.gp_id
              GROUP BY last.fy_id, g.taluk_id, f.scheme_id)
SELECT fy.fy_label AS fy, t.taluk_id, t.taluk_name, t.zilla_id, z.zilla_name, s.scheme_id, s.scheme_name, s.scheme_category,
       yc.scheme_books_closed, yc.scheme_books, money.receipts, money.expenditure, clos.closing_balance
FROM money JOIN dim_fy fy ON fy.fy_id = money.fy_id JOIN dim_taluk t ON t.taluk_id = money.taluk_id JOIN dim_zilla z ON z.zilla_id = t.zilla_id
JOIN dim_scheme s ON s.scheme_id = money.scheme_id
LEFT JOIN yc ON yc.fy_id = money.fy_id AND yc.taluk_id = money.taluk_id AND yc.scheme_id = money.scheme_id
LEFT JOIN clos ON clos.fy_id = money.fy_id AND clos.taluk_id = money.taluk_id AND clos.scheme_id = money.scheme_id""",
     ["fy", "zilla_name, fy", "taluk_name, fy"]),
]

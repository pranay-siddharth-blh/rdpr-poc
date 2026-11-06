-- RDPR worked examples: natural-language question -> reviewed SQLite SQL over the mart_* views.
-- Each block starts with "-- N. <question>" and ends with ";". The chatbot prompt includes the blocks most
-- similar to the user's question; build_semantic_layer.py and ai_app/tests run every block against the database.
-- Money is INR. FY labels are text ('2024-25'); month_label is text ('MAR-2026'). Ratios are SUM/SUM.

-- 1. What were the demand, collection and balance for Karnataka in each financial year?
SELECT fy, ROUND(SUM(total_demand), 2) AS total_demand, ROUND(SUM(total_collection), 2) AS total_collection,
       ROUND(SUM(balance), 2) AS balance, ROUND(SUM(total_collection) * 100.0 / NULLIF(SUM(total_demand), 0), 2) AS collection_pct
FROM mart_fact_gp_dcb GROUP BY fy ORDER BY fy;

-- 2. Which five zillas collected the most revenue in FY 2024-25?
SELECT zilla_name AS zilla, ROUND(SUM(total_collection), 2) AS total_collection
FROM mart_fact_gp_dcb WHERE fy = '2024-25' GROUP BY zilla_name ORDER BY total_collection DESC LIMIT 5;

-- 3. Taluk-wise collection percentage in Mysuru zilla for FY 2025-26
SELECT taluk_name AS taluk, ROUND(SUM(total_collection), 2) AS total_collection, ROUND(SUM(total_demand), 2) AS total_demand,
       ROUND(SUM(total_collection) * 100.0 / NULLIF(SUM(total_demand), 0), 2) AS collection_pct
FROM mart_fact_gp_dcb WHERE fy = '2025-26' AND zilla_name = 'Mysuru' GROUP BY taluk_name ORDER BY collection_pct DESC;

-- 4. Revenue collected by revenue head in Belagavi zilla in FY 2024-25
SELECT fee_type_name AS revenue_head, ROUND(SUM(total_collection), 2) AS total_collection
FROM mart_fact_gp_fee_type WHERE fy = '2024-25' AND zilla_name = 'Belagavi' GROUP BY fee_type_name ORDER BY total_collection DESC;

-- 5. Month-wise revenue collection across Karnataka in FY 2024-25
SELECT month_label, ROUND(SUM(collection_amount), 2) AS collection_amount
FROM mart_fact_gp_monthly_collection WHERE fy = '2024-25' GROUP BY month_id, month_label ORDER BY month_id;

-- 6. Property tax collection percentage by zilla in FY 2025-26, lowest first
SELECT zilla_name AS zilla, ROUND(SUM(total_collection) * 100.0 / NULLIF(SUM(total_demand), 0), 2) AS collection_pct
FROM mart_fact_gp_fee_type WHERE fy = '2025-26' AND fee_type_name = 'Property Taxes'
GROUP BY zilla_name ORDER BY collection_pct ASC;

-- 7. Demand and collection by property category across Karnataka in FY 2024-25
SELECT report_category AS property_category, ROUND(SUM(total_demand), 2) AS total_demand, ROUND(SUM(total_collection), 2) AS total_collection,
       ROUND(SUM(total_collection) * 100.0 / NULLIF(SUM(total_demand), 0), 2) AS collection_pct
FROM mart_fact_gp_demand_by_property_type WHERE fy = '2024-25' GROUP BY report_category ORDER BY total_demand DESC;

-- 8. Which five GPs in Badami taluk have the lowest collection percentage in FY 2025-26?
SELECT gp_name AS gp, ROUND(total_collection, 2) AS total_collection, ROUND(total_demand, 2) AS total_demand,
       ROUND(total_collection * 100.0 / NULLIF(total_demand, 0), 2) AS collection_pct
FROM mart_fact_gp_dcb WHERE fy = '2025-26' AND taluk_name = 'Badami' AND total_demand > 0 ORDER BY collection_pct ASC LIMIT 5;

-- 9. How have arrears for Karnataka grown each financial year?
SELECT fy, ROUND(SUM(arrears), 2) AS arrears, ROUND(SUM(year_demand), 2) AS year_demand
FROM mart_fact_gp_dcb GROUP BY fy ORDER BY fy;

-- 10. Compare each zilla's collection in FY 2024-25 with FY 2023-24 and show the growth
SELECT cur.zilla_name AS zilla, ROUND(cur.coll, 2) AS collection_2024_25, ROUND(prev.coll, 2) AS collection_2023_24,
       ROUND((cur.coll / NULLIF(prev.coll, 0) - 1) * 100, 2) AS growth_pct
FROM (SELECT zilla_name, SUM(total_collection) AS coll FROM mart_fact_gp_dcb WHERE fy = '2024-25' GROUP BY zilla_name) cur
JOIN (SELECT zilla_name, SUM(total_collection) AS coll FROM mart_fact_gp_dcb WHERE fy = '2023-24' GROUP BY zilla_name) prev
  ON prev.zilla_name = cur.zilla_name
ORDER BY growth_pct DESC;

-- 11. What percentage of scheme books were closed for the year 2024-25, by zilla?
SELECT zilla_name AS zilla, ROUND(SUM(is_closed) * 100.0 / NULLIF(COUNT(*), 0), 2) AS books_closed_pct
FROM mart_fact_gp_year_closure WHERE fy = '2024-25' GROUP BY zilla_name ORDER BY books_closed_pct DESC;

-- 12. Which GPs in Badami taluk did not close the Fifteen Finance Commission Grants book for FY 2024-25?
SELECT gp_name AS gp FROM mart_fact_gp_year_closure
WHERE fy = '2024-25' AND taluk_name = 'Badami' AND scheme_name = 'Fifteen Finance Commission Grants' AND is_closed = 0 ORDER BY gp_name;

-- 13. Month by month in FY 2025-26, what percentage of Own Resource Funds books were closed?
SELECT month_label, ROUND(SUM(is_closed) * 100.0 / NULLIF(COUNT(*), 0), 2) AS books_closed_pct
FROM mart_fact_gp_month_closure WHERE fy = '2025-26' AND scheme_name = 'Own Resource Funds' GROUP BY month_id, month_label ORDER BY month_id;

-- 14. Which five taluks have the lowest share of GPs that closed all their books in FY 2025-26?
SELECT taluk_name AS taluk, zilla_name AS zilla, gps_all_books_closed, total_gps, all_books_closed_pct
FROM mart_summary_taluk_year WHERE fy = '2025-26' ORDER BY all_books_closed_pct ASC, taluk_name LIMIT 5;

-- 15. Receipts and expenditure of each scheme across Karnataka in FY 2024-25
SELECT scheme_name AS scheme, ROUND(SUM(receipts), 2) AS receipts, ROUND(SUM(expenditure), 2) AS expenditure
FROM mart_fact_gp_scheme_financials WHERE fy = '2024-25' GROUP BY scheme_name ORDER BY receipts DESC;

-- 16. What is the closing balance of each scheme account at the end of the data (September 2026)?
SELECT scheme_name AS scheme, ROUND(SUM(closing_balance), 2) AS closing_balance
FROM mart_fact_gp_scheme_financials WHERE month_label = 'SEP-2026' GROUP BY scheme_name ORDER BY closing_balance DESC;

-- 17. Which five zillas held the highest scheme balances at the end of March 2026?
SELECT zilla_name AS zilla, ROUND(SUM(closing_balance), 2) AS closing_balance
FROM mart_fact_gp_scheme_financials WHERE month_label = 'MAR-2026' GROUP BY zilla_name ORDER BY closing_balance DESC LIMIT 5;

-- 18. On 30 September 2026, what share of GPs in each zilla had closed the Own Resource Funds day book?
SELECT zilla_name AS zilla, SUM(gps_closed) AS gps_closed, SUM(total_gps) AS total_gps,
       ROUND(SUM(gps_closed) * 100.0 / NULLIF(SUM(total_gps), 0), 2) AS closure_pct
FROM mart_fact_taluk_daybook_closure WHERE date = '2026-09-30' AND scheme_name = 'Own Resource Funds'
GROUP BY zilla_name ORDER BY closure_pct DESC;

-- 19. How many active GP staff are there in Badami taluk, by designation?
SELECT designation_name AS designation, SUM(staff_count) AS staff_count
FROM mart_fact_taluk_staff WHERE taluk_name = 'Badami' AND employment_status = 'Active'
GROUP BY designation_name ORDER BY staff_count DESC;

-- 20. How many active staff are there by staff type across Karnataka?
SELECT staff_type_name AS staff_type, SUM(staff_count) AS staff_count
FROM mart_fact_taluk_staff WHERE employment_status = 'Active' GROUP BY staff_type_name ORDER BY staff_count DESC;

-- 21. Which five taluks have the most staff registrations pending at the EO in FY 2025-26?
SELECT taluk_name AS taluk, zilla_name AS zilla, SUM(staff_approval_pending_at_eo) AS pending_at_eo
FROM mart_fact_gp_eo_approval WHERE fy = '2025-26' GROUP BY taluk_name, zilla_name HAVING SUM(staff_approval_pending_at_eo) > 0
ORDER BY pending_at_eo DESC LIMIT 5;

-- 22. Month by month in FY 2025-26, how many staff had their salary rejected by the bank in Belagavi zilla?
SELECT month_label, SUM(number_of_staff_salary_rejected_by_bank) AS salary_rejected_by_bank
FROM mart_fact_taluk_salary_bills WHERE fy = '2025-26' AND zilla_name = 'Belagavi' GROUP BY month_id, month_label ORDER BY month_id;

-- 23. Which GPs in Bagalkot zilla had no President registered in FY 2022-23?
SELECT gp_name AS gp, taluk_name AS taluk FROM mart_fact_gp_er_registration
WHERE fy = '2022-23' AND zilla_name = 'Bagalkot' AND total_adhyaksha_president = 0 ORDER BY taluk_name, gp_name;

-- 24. For each zilla, how many of the seats in GP bodies are filled by elected members in FY 2025-26?
SELECT zilla_name AS zilla, SUM(total_seats) AS total_seats, SUM(total_elected_members) AS elected_members,
       ROUND(SUM(total_elected_members) * 100.0 / NULLIF(SUM(total_seats), 0), 2) AS seats_filled_pct
FROM mart_fact_gp_er_registration WHERE fy = '2025-26' GROUP BY zilla_name ORDER BY seats_filled_pct ASC;

-- 25. Salary bill progress for September 2026 by staff type: generated, signed, bank processed and paid
SELECT staff_type_name AS staff_type, SUM(total_number_of_staff) AS total_staff, SUM(number_of_main_bill_generated) AS main_bills_generated,
       SUM(number_of_main_bill_pdo_signed) AS pdo_signed, SUM(number_of_main_bill_president_signed) AS president_signed,
       SUM(number_of_main_bill_processed_by_bank) AS processed_by_bank, SUM(number_of_staff_salary_paid) AS salary_paid,
       SUM(number_of_staff_salary_rejected_by_bank) AS salary_rejected
FROM mart_fact_taluk_salary_bills WHERE month_label = 'SEP-2026' GROUP BY staff_type_name ORDER BY total_staff DESC;

-- 26. For FY 2024-25, show each zilla's collection percentage, share of GPs that closed all books, and staff pending at the EO
SELECT zilla_name AS zilla, collection_pct, all_books_closed_pct, staff_approval_pending_at_eo
FROM mart_summary_zilla_year WHERE fy = '2024-25' ORDER BY collection_pct DESC;

-- 27. What is the gender split of active staff in each zilla?
SELECT zilla_name AS zilla, SUM(CASE WHEN gender = 'Female' THEN staff_count ELSE 0 END) AS female_staff,
       SUM(CASE WHEN gender = 'Male' THEN staff_count ELSE 0 END) AS male_staff,
       ROUND(SUM(CASE WHEN gender = 'Female' THEN staff_count ELSE 0 END) * 100.0 / NULLIF(SUM(staff_count), 0), 2) AS female_pct
FROM mart_fact_taluk_staff WHERE employment_status = 'Active' GROUP BY zilla_name ORDER BY female_pct DESC;

-- 28. Which ten GPs collected the most revenue in FY 2025-26?
SELECT gp_name AS gp, taluk_name AS taluk, zilla_name AS zilla, ROUND(total_collection, 2) AS total_collection
FROM mart_fact_gp_dcb WHERE fy = '2025-26' ORDER BY total_collection DESC LIMIT 10;

-- 29. How does collection percentage in FY 2025-26 differ by GP size class?
SELECT g.size_class AS size_class, COUNT(*) AS gps, ROUND(SUM(d.total_collection) * 100.0 / NULLIF(SUM(d.total_demand), 0), 2) AS collection_pct
FROM mart_fact_gp_dcb d JOIN mart_dim_gp g ON g.gp_id = d.gp_id WHERE d.fy = '2025-26' GROUP BY g.size_class ORDER BY collection_pct DESC;

-- 30. How many taluks and GPs does each zilla have?
SELECT zilla_name AS zilla, total_taluks, total_gps FROM mart_dim_zilla ORDER BY zilla_name;

-- 31. Which zillas have the highest outstanding balance in FY 2025-26?
SELECT zilla_name AS zilla, ROUND(SUM(balance), 2) AS balance
FROM mart_fact_gp_dcb WHERE fy = '2025-26' GROUP BY zilla_name ORDER BY balance DESC LIMIT 5;

-- 32. Year-on-year growth in revenue collection for Karnataka
SELECT cur.fy AS fy, ROUND(cur.coll, 2) AS total_collection, ROUND((cur.coll / NULLIF(prev.coll, 0) - 1) * 100, 2) AS growth_pct
FROM (SELECT fy, SUM(total_collection) AS coll FROM mart_fact_gp_dcb GROUP BY fy) cur
LEFT JOIN (SELECT fy, SUM(total_collection) AS coll FROM mart_fact_gp_dcb GROUP BY fy) prev
  ON prev.fy = (SELECT MAX(fy) FROM mart_dim_fy WHERE fy < cur.fy AND fy >= '2022-23')
ORDER BY cur.fy;

-- 33. Which GPs in Mysuru zilla collected less than a fifth of their demand in FY 2025-26?
SELECT gp_name AS gp, taluk_name AS taluk, ROUND(total_collection * 100.0 / NULLIF(total_demand, 0), 2) AS collection_pct
FROM mart_fact_gp_dcb WHERE fy = '2025-26' AND zilla_name = 'Mysuru' AND total_demand > 0 AND total_collection * 5.0 < total_demand
ORDER BY collection_pct ASC;

-- 34. How many GPs closed all their books in each financial year?
SELECT fy, SUM(all_books_closed) AS gps_all_books_closed, COUNT(*) AS total_gps
FROM mart_summary_gp_year GROUP BY fy ORDER BY fy;

-- 35. How many GPs closed none of their scheme books in FY 2024-25?
SELECT COUNT(*) AS gps_with_no_book_closed
FROM (SELECT gp_id FROM mart_fact_gp_year_closure WHERE fy = '2024-25' GROUP BY gp_id HAVING SUM(is_closed) = 0);

-- 36. How many GPs in Hassan zilla had no President registered in FY 2025-26?
SELECT COUNT(*) AS gps_without_president
FROM mart_fact_gp_er_registration WHERE fy = '2025-26' AND zilla_name = 'Hassan' AND total_adhyaksha_president = 0;

-- 37. Which GPs in Mysuru zilla collected less than 15% of their demand in FY 2024-25?
SELECT gp_name AS gp, taluk_name AS taluk, ROUND(SUM(total_collection) * 100.0 / NULLIF(SUM(total_demand), 0), 2) AS collection_pct
FROM mart_fact_gp_dcb WHERE fy = '2024-25' AND zilla_name = 'Mysuru'
GROUP BY gp_id, gp_name, taluk_name HAVING SUM(total_collection) * 100.0 / NULLIF(SUM(total_demand), 0) < 15
ORDER BY collection_pct ASC;

-- 38. How many taluks in Belagavi zilla collected more than 28% of their demand in FY 2025-26?
SELECT COUNT(*) AS taluks
FROM (SELECT taluk_name FROM mart_fact_gp_dcb WHERE fy = '2025-26' AND zilla_name = 'Belagavi'
      GROUP BY taluk_name HAVING SUM(total_collection) * 100.0 / NULLIF(SUM(total_demand), 0) > 28);

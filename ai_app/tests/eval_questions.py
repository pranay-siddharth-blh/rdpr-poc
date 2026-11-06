"""
Evaluation bank for the live model run (tests/run_eval.py). Each question has reference SQL whose first-row figures the
chatbot's answer must contain (as text or in its result rows). The questions are phrased so that no deterministic
route (verified query, report, breakdown, metric lookup) takes them, so every one exercises the LLM path: SQL
generation, the SQL guard, the result guards and the reviewer.
"""
QUESTIONS = [
    {"id": 1, "q": "How many GPs in Mysuru zilla collected less than 20% of their total demand in FY 2024-25?",
     "ref": "SELECT COUNT(*) FROM mart_fact_gp_dcb WHERE zilla_name = 'Mysuru' AND fy = '2024-25' AND total_demand > 0 "
            "AND total_collection * 100.0 / total_demand < 20"},
    {"id": 2, "q": "Which GP in Badami taluk had the highest collection percentage in 2024-25, and what was it?",
     "ref": "SELECT ROUND(total_collection * 100.0 / total_demand, 2) FROM mart_fact_gp_dcb WHERE taluk_name = 'Badami' AND fy = '2024-25' "
            "AND total_demand > 0 ORDER BY total_collection * 1.0 / total_demand DESC LIMIT 1"},
    {"id": 3, "q": "How many GPs in Karnataka closed none of their scheme year books in FY 2024-25?",
     "ref": "SELECT COUNT(*) FROM (SELECT gp_id FROM mart_fact_gp_year_closure WHERE fy = '2024-25' GROUP BY gp_id HAVING SUM(is_closed) = 0)"},
    {"id": 4, "q": "Which taluk had the most staff registrations waiting at the EO in FY 2025-26, and how many?",
     "ref": "SELECT SUM(staff_approval_pending_at_eo) s FROM mart_fact_gp_eo_approval WHERE fy = '2025-26' GROUP BY taluk_name ORDER BY s DESC LIMIT 1"},
    {"id": 5, "q": "How many GPs had no president registered in FY 2025-26?",
     "ref": "SELECT COUNT(*) FROM mart_fact_gp_er_registration WHERE fy = '2025-26' AND total_adhyaksha_president = 0"},
    {"id": 6, "q": "Under which scheme did GPs in Mysuru zilla spend the most in FY 2024-25, and how much?",
     "ref": "SELECT SUM(expenditure) s FROM mart_fact_gp_scheme_financials WHERE zilla_name = 'Mysuru' AND fy = '2024-25' "
            "GROUP BY scheme_name ORDER BY s DESC LIMIT 1"},
    {"id": 7, "q": "How many taluks in Kalaburagi zilla collected more than 30% of their demand in FY 2024-25?",
     "ref": "SELECT COUNT(*) FROM (SELECT taluk_name FROM mart_fact_gp_dcb WHERE zilla_name = 'Kalaburagi' AND fy = '2024-25' "
            "GROUP BY taluk_name HAVING SUM(total_collection) * 100.0 / SUM(total_demand) > 30)"},
    {"id": 8, "q": "What is the gap between total demand and total collection for Udupi zilla in FY 2023-24?",
     "ref": "SELECT SUM(total_demand) - SUM(total_collection) FROM mart_fact_gp_dcb WHERE zilla_name = 'Udupi' AND fy = '2023-24'"},
    {"id": 9, "q": "How many GPs in Hassan zilla have more than 5,000 properties in FY 2025-26?",
     "ref": "SELECT COUNT(*) FROM mart_fact_gp_property_counts WHERE zilla_name = 'Hassan' AND fy = '2025-26' AND number_of_properties > 5000"},
    {"id": 10, "q": "What share of all GP seats were filled by elected members in Belagavi zilla in FY 2025-26?",
     "ref": "SELECT ROUND(SUM(total_elected_members) * 100.0 / SUM(total_seats), 2) FROM mart_fact_gp_er_registration "
            "WHERE zilla_name = 'Belagavi' AND fy = '2025-26'"},
    {"id": 11, "q": "Which zilla rejected the largest number of staff registrations at the EO in FY 2024-25, and how many?",
     "ref": "SELECT SUM(staff_registrations_rejected_by_eo) s FROM mart_fact_gp_eo_approval WHERE fy = '2024-25' "
            "GROUP BY zilla_name ORDER BY s DESC LIMIT 1"},
    {"id": 12, "q": "How many GPs in Tumakuru zilla had an outstanding balance above 50 lakh in FY 2025-26?",
     "ref": "SELECT COUNT(*) FROM mart_fact_gp_dcb WHERE zilla_name = 'Tumakuru' AND fy = '2025-26' AND balance > 5000000"},
    {"id": 13, "q": "What was the total mobile tower tax demand across Karnataka in FY 2024-25, and how much of it was collected?",
     "ref": "SELECT SUM(total_demand), SUM(total_collection) FROM mart_fact_gp_fee_type WHERE fee_type_name = 'Mobile Tower Tax' AND fy = '2024-25'"},
    {"id": 14, "q": "How many GPs in Dakshina Kannada closed every scheme book in FY 2025-26?",
     "ref": "SELECT COUNT(*) FROM (SELECT gp_id FROM mart_fact_gp_year_closure WHERE zilla_name = 'Dakshina Kannada' AND fy = '2025-26' "
            "GROUP BY gp_id HAVING MIN(is_closed) = 1)"},
    {"id": 15, "q": "What was the closing balance of all scheme accounts of GPs in Mandya zilla at the end of March 2025?",
     "ref": "SELECT SUM(closing_balance) FROM mart_fact_gp_scheme_financials WHERE zilla_name = 'Mandya' AND month_label = 'MAR-2025'"},
]

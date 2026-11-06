/* English / Kannada interface strings. The chosen language is remembered in the browser. Data values that come from the
   database (scheme names, designations, GP and taluk names) stay as they are; zilla names and months are translated.
   The Kannada wording is machine-written and should be reviewed by a native speaker before official use. */
(function () {
  "use strict";
  const D = {
    en: {
      gov: "Government of Karnataka", skip: "Skip to main content", welcome: "Welcome", lang_switch: "ಕನ್ನಡ",
      site_title: "Rural Development & Panchayat Raj", site_sub: "Government of Karnataka · Gram Panchayat Finance, Revenue and HRMS",
      side_views: "Dashboards", side_pages: "Pages", side_suggested: "Suggested questions", nav_dashboard: "Dashboard", nav_map: "Map", nav_compare: "Compare", nav_gp: "GP Report Card", nav_alerts: "Alerts", nav_ask: "Ask AI",
      fy: "Financial year", zilla: "Zilla", all_karnataka: "All Karnataka", part_year: "part-year", gps: "Gram Panchayats", data_to: "data to",
      ask_cta: "Ask a question in AI mode →", dash_cta: "← Back to the dashboard", dl_report: "Download report", dl_excel: "Excel (.xls)", dl_pdf: "PDF (print)", highlights: "Highlights", loading: "Loading…", failed: "Could not load: ",
      partial_banner: "FY {fy} is part-year: it holds April to September 2026 only, so year totals and year-end book closure are incomplete.",
      sec_overview: "Overview", sec_alerts: "Alerts", sec_map: "Karnataka map", sec_revenue: "Revenue", sec_finance: "Finance & Accounting", sec_hrms: "HRMS",
      sec_revenue_sub: "Demand, collection and balance (DCB)", sec_finance_sub: "Book closure and scheme accounts", sec_hrms_sub: "Staff, EO approvals, elected members and salary bills",
      key_obs: "Key observations",
      k_total_collection: "Total collection", k_collection_pct: "Collection %", k_gps_all_closed: "GPs closed all books", k_active_staff: "Active staff",
      k_total_demand: "Total demand", k_balance: "Outstanding balance", k_books_closed: "Scheme books closed", k_receipts: "Receipts", k_expenditure: "Expenditure",
      k_pending_eo: "Pending at EO", k_elected: "Elected members", k_president: "GPs with a President",
      s_arrears_current: "arrears {a} + current {c}", s_vs: "vs FY {fy}", s_fy_pct: "FY {fy}: {p}", s_adjustments: "adjustments {a}", s_scheme_books: "{n} scheme books",
      s_of_gps: "{p} of {n} GPs", s_all_accounts: "all scheme accounts", s_closing: "closing balance {v}", s_end_of_data: "as at end of data",
      s_approved_rejected: "{a} approved · {r} rejected", s_of_seats: "{p} of {n} seats", s_of_reporting: "of {n} GPs",
      c_trend: "Five-year trend", c_trend_sub: "Total demand and collection by financial year", c_demand: "Total demand", c_collection: "Collection",
      c_monthly: "Monthly collection", c_monthly_sub: "Collected in each month of FY {fy}",
      c_league: "Collection percentage by {by}", c_league_sub: "Collection as % of total demand, highest first",
      c_head: "Collection by revenue head", c_head_sub: "Amount collected", c_prop: "Demand by property category", c_prop_sub: "Total demand and collection",
      c_scheme: "Books closed by scheme", c_scheme_sub: "Share of GP scheme books closed for the year", c_cmonth: "Month-end closure", c_cmonth_sub: "Share of scheme books closed at each month end",
      c_money: "Receipts and expenditure by scheme", c_money_sub: "Financial-year totals", c_desig: "Active staff by designation", c_desig_sub: "Ten largest designations, as at the end of the data",
      c_salary: "Salary bills: paid and rejected", c_salary_sub: "Staff paid and rejected by the bank, each month of FY {fy}", c_stype: "Staff by type", c_stype_sub: "Active staff",
      salaryPaid: "Paid", salaryRejected: "Rejected by bank",
      c_funnel: "Salary bill progress", c_funnel_sub: "Main bill stages by staff type (taluk-level data).",
      f_type: "Staff type", f_staff: "Staff", f_generated: "Bills generated", f_pdo: "PDO signed", f_president: "President signed", f_bank: "Bank processed", f_paid: "Salary paid", f_rejected: "Rejected",
      by_zilla: "zilla", by_taluk: "taluk", paid: "Paid", rejected_bank: "Rejected by bank", books_closed_pct: "Books closed %", receipts: "Receipts", expenditure: "Expenditure", active_staff: "Active staff",
      cr: "cr", lakh: "lakh", crore: "crore",
      o_collected: "{p}% of the total demand was collected in FY {fy}", o_higher: "; collection is {g}% higher than FY {pfy}", o_lower: "; collection is {g}% lower than FY {pfy}",
      o_league: "Highest collection percentage by {by}: {hi} ({hp}%); lowest: {lo} ({lp}%).", o_closed: "{n} of {t} GPs ({p}%) closed every scheme book for the year",
      o_partial: " (year-end closure for the current year has not happened yet).", o_pending: "{n} staff registrations are still pending at the EO.",
      o_rejected: "In {m}, the bank rejected {n} salaries ({p}% of those processed).",
      // map
      map_title: "Karnataka at a glance", map_sub: "Colour each zilla by a measure; click a zilla to filter the dashboard.", map_metric: "Measure",
      m_collection_pct: "Collection %", m_books_closed: "Books closed %", m_pending_eo: "Pending at EO", m_staff: "Active staff", m_collection: "Total collection",
      m_low: "Lower", m_high: "Higher",
      map_combined: "Ballari + Vijayanagara", map_select: "Open this zilla", map_hint: "Hover a zilla for its figures.",
      // alerts
      al_title: "Alerts and watch-list", al_sub: "Places that need attention in FY {fy}", al_none: "No alerts for this year.", al_high: "High", al_medium: "Medium", al_low: "Low",
      al_low_collection: "GPs collecting under 20% of their demand", al_eo_backlog: "Staff registrations pending at the EO", al_zilla_lag: "Zillas collecting well below the state rate",
      al_collection_fall: "Zillas whose collection fell against FY {pfy}", al_salary_spike: "Months with unusually high bank salary rejections",
      al_no_books_closed: "GPs that closed none of their books for the year", al_no_president: "GPs with no President registered",
      al_unit_gps: "GPs", al_unit_registrations: "registrations", al_unit_zillas: "zillas", al_unit_months: "months", al_state_rate: "state rate {p}%", al_avg: "average {p}%",
      al_view: "View", al_partial_skip: "Year-end alerts are not shown for a part-year.",
      // gp card
      gp_title: "GP Report Card", gp_sub: "A one-page profile of any Gram Panchayat", gp_search: "Search a Gram Panchayat (type at least 2 letters)", gp_pick: "Pick a GP to see its report card.",
      gp_print: "Print / save as PDF", gp_csv: "Download CSV", gp_taluk: "Taluk", gp_zilla: "Zilla", gp_size: "Size", gp_tier: "Performance tier", gp_lgd: "LGD code",
      gp_rank_state: "Rank in Karnataka", gp_rank_zilla: "Rank in zilla", gp_rank_taluk: "Rank in taluk", gp_vs_peers: "Collection % against peers", gp_this: "This GP", gp_taluk_avg: "Taluk", gp_zilla_avg: "Zilla", gp_state_avg: "Karnataka",
      gp_trend: "Demand and collection, five years", gp_months: "Collection by month", gp_heads: "Collection by revenue head", gp_books: "Scheme books", gp_closed: "Closed", gp_open: "Open",
      gp_closed_on: "closed on {d}", gp_hr: "People and governance", gp_seats: "Seats", gp_members: "Elected members", gp_president: "President registered", gp_vp: "Vice-President registered",
      gp_sent: "Registrations sent to EO", gp_approved: "Approved by EO", gp_pending: "Pending at EO", gp_rejected: "Rejected by EO", gp_props: "Properties", yes: "Yes", no: "No",
      gp_receipts: "Scheme receipts", gp_expenditure: "Scheme expenditure", gp_closing: "Closing balance", gp_demand: "Total demand", gp_collection: "Collection", gp_balance: "Balance", gp_arrears: "Arrears",
      gp_year_col: "Year", gp_ambiguous: "Several GPs share this name; the taluk is shown after each.", gp_snapshot: "HR figures as at {d}",
      badge_top_taluk: "Top 10% in its taluk", badge_above_state: "Collecting above the state rate", badge_below_state: "Collecting below the state rate", badge_all_closed: "Closed every scheme book",
      badge_pending_eo: "Staff pending at EO", badge_no_president: "No President registered", badge_full_house: "All seats filled",
      // compare
      cmp_title: "Compare two zillas", cmp_sub: "Side by side for one financial year", cmp_a: "Zilla A", cmp_b: "Zilla B", cmp_go: "Compare",
      cmp_summary: "{w} is ahead on {n} of {t} measures.", cmp_tie: "The two are level on the measures compared.", cmp_ahead: "ahead",
      cmp_collection_pct: "Collection %", cmp_growth: "Collection growth vs last year", cmp_collection_per_gp: "Collection per GP", cmp_books_closed: "Books closed %",
      cmp_all_closed: "GPs closed all books %", cmp_seats_filled: "Seats filled %", cmp_pending_eo: "Pending at EO (fewer is better)", cmp_gps: "Gram Panchayats",
      cmp_measure: "Measure", cmp_monthly: "Monthly collection", cmp_heads: "Collection by revenue head", cmp_staff_per_gp: "Staff per GP",
      // chat
      chat_title: "Panchayat Raj Data Assistant", chat_sub: "Ask about Finance & Accounting, Revenue and HRMS in plain language", chat_placeholder: "Ask a question, e.g. Which five zillas collected the most revenue in 2025-26?",
      ask: "Ask", chat_en_only: "The assistant answers in English.",
    },
    kn: {
      gov: "ಕರ್ನಾಟಕ ಸರ್ಕಾರ", skip: "ಮುಖ್ಯ ವಿಷಯಕ್ಕೆ ಹೋಗಿ", welcome: "ಸ್ವಾಗತ", lang_switch: "English",
      site_title: "ಗ್ರಾಮೀಣಾಭಿವೃದ್ಧಿ ಮತ್ತು ಪಂಚಾಯತ್ ರಾಜ್", site_sub: "ಕರ್ನಾಟಕ ಸರ್ಕಾರ · ಗ್ರಾಮ ಪಂಚಾಯತ್ ಹಣಕಾಸು, ಆದಾಯ ಮತ್ತು ಮಾನವ ಸಂಪನ್ಮೂಲ",
      side_views: "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್‌ಗಳು", side_pages: "ಪುಟಗಳು", side_suggested: "ಸೂಚಿತ ಪ್ರಶ್ನೆಗಳು", nav_dashboard: "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್", nav_map: "ನಕ್ಷೆ", nav_compare: "ಹೋಲಿಕೆ", nav_gp: "ಗ್ರಾ.ಪಂ. ವರದಿ ಕಾರ್ಡ್", nav_alerts: "ಎಚ್ಚರಿಕೆಗಳು", nav_ask: "AI ಗೆ ಕೇಳಿ",
      fy: "ಆರ್ಥಿಕ ವರ್ಷ", zilla: "ಜಿಲ್ಲೆ", all_karnataka: "ಇಡೀ ಕರ್ನಾಟಕ", part_year: "ಭಾಗಶಃ ವರ್ಷ", gps: "ಗ್ರಾಮ ಪಂಚಾಯತ್‌ಗಳು", data_to: "ಮಾಹಿತಿ ವರೆಗೆ",
      ask_cta: "AI ಮೋಡ್‌ನಲ್ಲಿ ಪ್ರಶ್ನೆ ಕೇಳಿ →", dash_cta: "← ಡ್ಯಾಶ್‌ಬೋರ್ಡ್‌ಗೆ ಹಿಂತಿರುಗಿ", dl_report: "ವರದಿ ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ", dl_excel: "Excel (.xls)", dl_pdf: "PDF (ಮುದ್ರಣ)", highlights: "ಮುಖ್ಯಾಂಶಗಳು", loading: "ಲೋಡ್ ಆಗುತ್ತಿದೆ…", failed: "ಲೋಡ್ ಮಾಡಲಾಗಲಿಲ್ಲ: ",
      partial_banner: "{fy} ಆರ್ಥಿಕ ವರ್ಷ ಭಾಗಶಃ: ಏಪ್ರಿಲ್‌ನಿಂದ ಸೆಪ್ಟೆಂಬರ್ 2026 ರವರೆಗೆ ಮಾತ್ರ ಇದೆ; ಆದ್ದರಿಂದ ವರ್ಷದ ಒಟ್ಟು ಮೊತ್ತ ಮತ್ತು ವರ್ಷಾಂತ್ಯದ ಲೆಕ್ಕ ಮುಕ್ತಾಯ ಅಪೂರ್ಣ.",
      sec_overview: "ಅವಲೋಕನ", sec_alerts: "ಎಚ್ಚರಿಕೆಗಳು", sec_map: "ಕರ್ನಾಟಕ ನಕ್ಷೆ", sec_revenue: "ಆದಾಯ", sec_finance: "ಹಣಕಾಸು ಮತ್ತು ಲೆಕ್ಕಪತ್ರ", sec_hrms: "ಮಾನವ ಸಂಪನ್ಮೂಲ (HRMS)",
      sec_revenue_sub: "ಬೇಡಿಕೆ, ವಸೂಲಿ ಮತ್ತು ಬಾಕಿ (DCB)", sec_finance_sub: "ಲೆಕ್ಕ ಮುಕ್ತಾಯ ಮತ್ತು ಯೋಜನಾ ಖಾತೆಗಳು", sec_hrms_sub: "ಸಿಬ್ಬಂದಿ, ಇಒ ಅನುಮೋದನೆ, ಚುನಾಯಿತ ಸದಸ್ಯರು ಮತ್ತು ವೇತನ ಬಿಲ್ಲುಗಳು",
      key_obs: "ಪ್ರಮುಖ ಅವಲೋಕನಗಳು",
      k_total_collection: "ಒಟ್ಟು ವಸೂಲಿ", k_collection_pct: "ವಸೂಲಿ %", k_gps_all_closed: "ಎಲ್ಲಾ ಲೆಕ್ಕ ಮುಕ್ತಾಯಗೊಳಿಸಿದ ಗ್ರಾ.ಪಂ.", k_active_staff: "ಸಕ್ರಿಯ ಸಿಬ್ಬಂದಿ",
      k_total_demand: "ಒಟ್ಟು ಬೇಡಿಕೆ", k_balance: "ಬಾಕಿ ಮೊತ್ತ", k_books_closed: "ಮುಕ್ತಾಯಗೊಂಡ ಯೋಜನಾ ಖಾತೆಗಳು", k_receipts: "ಸ್ವೀಕೃತಿಗಳು", k_expenditure: "ವೆಚ್ಚ",
      k_pending_eo: "ಇಒ ಬಳಿ ಬಾಕಿ", k_elected: "ಚುನಾಯಿತ ಸದಸ್ಯರು", k_president: "ಅಧ್ಯಕ್ಷರಿರುವ ಗ್ರಾ.ಪಂ.",
      s_arrears_current: "ಬಾಕಿ {a} + ಈ ವರ್ಷ {c}", s_vs: "{fy} ಕ್ಕೆ ಹೋಲಿಸಿದರೆ", s_fy_pct: "{fy}: {p}", s_adjustments: "ಹೊಂದಾಣಿಕೆ {a}", s_scheme_books: "{n} ಯೋಜನಾ ಖಾತೆಗಳು",
      s_of_gps: "{n} ಗ್ರಾ.ಪಂ.ಗಳಲ್ಲಿ {p}", s_all_accounts: "ಎಲ್ಲಾ ಯೋಜನಾ ಖಾತೆಗಳು", s_closing: "ಮುಕ್ತಾಯ ಶಿಲ್ಕು {v}", s_end_of_data: "ಮಾಹಿತಿಯ ಅಂತ್ಯದಲ್ಲಿ",
      s_approved_rejected: "{a} ಅನುಮೋದನೆ · {r} ತಿರಸ್ಕೃತ", s_of_seats: "{n} ಸ್ಥಾನಗಳಲ್ಲಿ {p}", s_of_reporting: "{n} ಗ್ರಾ.ಪಂ.ಗಳಲ್ಲಿ",
      c_trend: "ಐದು ವರ್ಷಗಳ ಪ್ರವೃತ್ತಿ", c_trend_sub: "ಆರ್ಥಿಕ ವರ್ಷವಾರು ಒಟ್ಟು ಬೇಡಿಕೆ ಮತ್ತು ವಸೂಲಿ", c_demand: "ಒಟ್ಟು ಬೇಡಿಕೆ", c_collection: "ವಸೂಲಿ",
      c_monthly: "ಮಾಸಿಕ ವಸೂಲಿ", c_monthly_sub: "{fy} ವರ್ಷದ ಪ್ರತಿ ತಿಂಗಳ ವಸೂಲಿ",
      c_league: "{by}ವಾರು ವಸೂಲಿ ಶೇಕಡಾ", c_league_sub: "ಒಟ್ಟು ಬೇಡಿಕೆಯ ಶೇಕಡಾವಾರು ವಸೂಲಿ, ಹೆಚ್ಚಿನದು ಮೊದಲು",
      c_head: "ಆದಾಯ ಶೀರ್ಷಿಕೆವಾರು ವಸೂಲಿ", c_head_sub: "ವಸೂಲಾದ ಮೊತ್ತ", c_prop: "ಆಸ್ತಿ ವರ್ಗವಾರು ಬೇಡಿಕೆ", c_prop_sub: "ಒಟ್ಟು ಬೇಡಿಕೆ ಮತ್ತು ವಸೂಲಿ",
      c_scheme: "ಯೋಜನೆವಾರು ಮುಕ್ತಾಯಗೊಂಡ ಖಾತೆಗಳು", c_scheme_sub: "ವರ್ಷಕ್ಕೆ ಮುಕ್ತಾಯಗೊಂಡ ಗ್ರಾ.ಪಂ. ಯೋಜನಾ ಖಾತೆಗಳ ಪಾಲು", c_cmonth: "ತಿಂಗಳಾಂತ್ಯ ಮುಕ್ತಾಯ", c_cmonth_sub: "ಪ್ರತಿ ತಿಂಗಳ ಕೊನೆಯಲ್ಲಿ ಮುಕ್ತಾಯಗೊಂಡ ಖಾತೆಗಳ ಪಾಲು",
      c_money: "ಯೋಜನೆವಾರು ಸ್ವೀಕೃತಿ ಮತ್ತು ವೆಚ್ಚ", c_money_sub: "ಆರ್ಥಿಕ ವರ್ಷದ ಒಟ್ಟು", c_desig: "ಹುದ್ದೆವಾರು ಸಕ್ರಿಯ ಸಿಬ್ಬಂದಿ", c_desig_sub: "ಹತ್ತು ದೊಡ್ಡ ಹುದ್ದೆಗಳು, ಮಾಹಿತಿಯ ಅಂತ್ಯದಲ್ಲಿ",
      c_salary: "ವೇತನ ಬಿಲ್ಲುಗಳು: ಪಾವತಿ ಮತ್ತು ತಿರಸ್ಕೃತ", c_salary_sub: "{fy} ವರ್ಷದ ಪ್ರತಿ ತಿಂಗಳು ಬ್ಯಾಂಕ್ ಪಾವತಿಸಿದ ಮತ್ತು ತಿರಸ್ಕರಿಸಿದ ಸಿಬ್ಬಂದಿ", c_stype: "ವಿಧವಾರು ಸಿಬ್ಬಂದಿ", c_stype_sub: "ಸಕ್ರಿಯ ಸಿಬ್ಬಂದಿ",
      salaryPaid: "ಪಾವತಿ", salaryRejected: "ಬ್ಯಾಂಕ್ ತಿರಸ್ಕೃತ",
      c_funnel: "ವೇತನ ಬಿಲ್ ಪ್ರಗತಿ", c_funnel_sub: "ಸಿಬ್ಬಂದಿ ವಿಧವಾರು ಮುಖ್ಯ ಬಿಲ್ ಹಂತಗಳು (ತಾಲ್ಲೂಕು ಮಟ್ಟದ ಮಾಹಿತಿ).",
      f_type: "ಸಿಬ್ಬಂದಿ ವಿಧ", f_staff: "ಸಿಬ್ಬಂದಿ", f_generated: "ಸೃಜಿತ ಬಿಲ್ಲುಗಳು", f_pdo: "ಪಿಡಿಒ ಸಹಿ", f_president: "ಅಧ್ಯಕ್ಷರ ಸಹಿ", f_bank: "ಬ್ಯಾಂಕ್ ಸಂಸ್ಕರಣೆ", f_paid: "ವೇತನ ಪಾವತಿ", f_rejected: "ತಿರಸ್ಕೃತ",
      by_zilla: "ಜಿಲ್ಲೆ", by_taluk: "ತಾಲ್ಲೂಕು", paid: "ಪಾವತಿ", rejected_bank: "ಬ್ಯಾಂಕ್ ತಿರಸ್ಕೃತ", books_closed_pct: "ಮುಕ್ತಾಯ %", receipts: "ಸ್ವೀಕೃತಿ", expenditure: "ವೆಚ್ಚ", active_staff: "ಸಕ್ರಿಯ ಸಿಬ್ಬಂದಿ",
      cr: "ಕೋ.", lakh: "ಲಕ್ಷ", crore: "ಕೋಟಿ",
      o_collected: "{fy} ರಲ್ಲಿ ಒಟ್ಟು ಬೇಡಿಕೆಯ {p}% ವಸೂಲಾಗಿದೆ", o_higher: "; ವಸೂಲಿ {pfy} ಕ್ಕಿಂತ {g}% ಹೆಚ್ಚು", o_lower: "; ವಸೂಲಿ {pfy} ಕ್ಕಿಂತ {g}% ಕಡಿಮೆ",
      o_league: "{by} ಮಟ್ಟದಲ್ಲಿ ಅತ್ಯಧಿಕ ವಸೂಲಿ ಶೇಕಡಾ: {hi} ({hp}%); ಅತ್ಯಲ್ಪ: {lo} ({lp}%).", o_closed: "{t} ಗ್ರಾ.ಪಂ.ಗಳಲ್ಲಿ {n} ({p}%) ವರ್ಷದ ಎಲ್ಲಾ ಯೋಜನಾ ಖಾತೆಗಳನ್ನು ಮುಕ್ತಾಯಗೊಳಿಸಿವೆ",
      o_partial: " (ಪ್ರಸ್ತುತ ವರ್ಷದ ವರ್ಷಾಂತ್ಯ ಮುಕ್ತಾಯ ಇನ್ನೂ ಆಗಿಲ್ಲ).", o_pending: "{n} ಸಿಬ್ಬಂದಿ ನೋಂದಣಿಗಳು ಇನ್ನೂ ಇಒ ಬಳಿ ಬಾಕಿ ಇವೆ.",
      o_rejected: "{m} ರಲ್ಲಿ ಬ್ಯಾಂಕ್ {n} ವೇತನಗಳನ್ನು ತಿರಸ್ಕರಿಸಿದೆ (ಸಂಸ್ಕರಿಸಿದವುಗಳ {p}%).",
      map_title: "ಒಂದು ನೋಟದಲ್ಲಿ ಕರ್ನಾಟಕ", map_sub: "ಅಳತೆಯ ಆಧಾರದ ಮೇಲೆ ಜಿಲ್ಲೆಗಳಿಗೆ ಬಣ್ಣ ಹಾಕಲಾಗಿದೆ; ಜಿಲ್ಲೆಯ ಮೇಲೆ ಕ್ಲಿಕ್ ಮಾಡಿ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್ ಫಿಲ್ಟರ್ ಮಾಡಿ.", map_metric: "ಅಳತೆ",
      m_collection_pct: "ವಸೂಲಿ %", m_books_closed: "ಮುಕ್ತಾಯಗೊಂಡ ಖಾತೆ %", m_pending_eo: "ಇಒ ಬಳಿ ಬಾಕಿ", m_staff: "ಸಕ್ರಿಯ ಸಿಬ್ಬಂದಿ", m_collection: "ಒಟ್ಟು ವಸೂಲಿ",
      m_low: "ಕಡಿಮೆ", m_high: "ಹೆಚ್ಚು",
      map_combined: "ಬಳ್ಳಾರಿ + ವಿಜಯನಗರ", map_select: "ಈ ಜಿಲ್ಲೆಯನ್ನು ತೆರೆಯಿರಿ", map_hint: "ಅಂಕಿಅಂಶ ನೋಡಲು ಜಿಲ್ಲೆಯ ಮೇಲೆ ಸೂಚಕ ಇರಿಸಿ.",
      al_title: "ಎಚ್ಚರಿಕೆಗಳು ಮತ್ತು ನಿಗಾ ಪಟ್ಟಿ", al_sub: "{fy} ವರ್ಷದಲ್ಲಿ ಗಮನ ಬೇಕಾದ ಸ್ಥಳಗಳು", al_none: "ಈ ವರ್ಷಕ್ಕೆ ಯಾವುದೇ ಎಚ್ಚರಿಕೆಗಳಿಲ್ಲ.", al_high: "ಹೆಚ್ಚು", al_medium: "ಮಧ್ಯಮ", al_low: "ಕಡಿಮೆ",
      al_low_collection: "ಬೇಡಿಕೆಯ 20% ಕ್ಕಿಂತ ಕಡಿಮೆ ವಸೂಲಿ ಮಾಡಿದ ಗ್ರಾ.ಪಂ.ಗಳು", al_eo_backlog: "ಇಒ ಬಳಿ ಬಾಕಿ ಇರುವ ಸಿಬ್ಬಂದಿ ನೋಂದಣಿಗಳು", al_zilla_lag: "ರಾಜ್ಯದ ದರಕ್ಕಿಂತ ಬಹಳ ಕಡಿಮೆ ವಸೂಲಿ ಮಾಡಿದ ಜಿಲ್ಲೆಗಳು",
      al_collection_fall: "{pfy} ಕ್ಕೆ ಹೋಲಿಸಿದರೆ ವಸೂಲಿ ಕುಸಿದ ಜಿಲ್ಲೆಗಳು", al_salary_spike: "ಬ್ಯಾಂಕ್ ವೇತನ ತಿರಸ್ಕಾರ ಅಸಾಮಾನ್ಯವಾಗಿ ಹೆಚ್ಚಿದ ತಿಂಗಳುಗಳು",
      al_no_books_closed: "ವರ್ಷದಲ್ಲಿ ಯಾವುದೇ ಖಾತೆ ಮುಕ್ತಾಯಗೊಳಿಸದ ಗ್ರಾ.ಪಂ.ಗಳು", al_no_president: "ಅಧ್ಯಕ್ಷರ ನೋಂದಣಿ ಇಲ್ಲದ ಗ್ರಾ.ಪಂ.ಗಳು",
      al_unit_gps: "ಗ್ರಾ.ಪಂ.", al_unit_registrations: "ನೋಂದಣಿಗಳು", al_unit_zillas: "ಜಿಲ್ಲೆಗಳು", al_unit_months: "ತಿಂಗಳುಗಳು", al_state_rate: "ರಾಜ್ಯ ದರ {p}%", al_avg: "ಸರಾಸರಿ {p}%",
      al_view: "ನೋಡಿ", al_partial_skip: "ಭಾಗಶಃ ವರ್ಷಕ್ಕೆ ವರ್ಷಾಂತ್ಯದ ಎಚ್ಚರಿಕೆಗಳನ್ನು ತೋರಿಸಲಾಗುವುದಿಲ್ಲ.",
      gp_title: "ಗ್ರಾ.ಪಂ. ವರದಿ ಕಾರ್ಡ್", gp_sub: "ಯಾವುದೇ ಗ್ರಾಮ ಪಂಚಾಯತ್‌ನ ಒಂದು ಪುಟದ ಪರಿಚಯ", gp_search: "ಗ್ರಾಮ ಪಂಚಾಯತ್ ಹುಡುಕಿ (ಕನಿಷ್ಠ 2 ಅಕ್ಷರ ಟೈಪ್ ಮಾಡಿ)", gp_pick: "ವರದಿ ಕಾರ್ಡ್ ನೋಡಲು ಗ್ರಾ.ಪಂ. ಆಯ್ಕೆಮಾಡಿ.",
      gp_print: "ಮುದ್ರಿಸಿ / PDF ಉಳಿಸಿ", gp_csv: "CSV ಡೌನ್‌ಲೋಡ್", gp_taluk: "ತಾಲ್ಲೂಕು", gp_zilla: "ಜಿಲ್ಲೆ", gp_size: "ಗಾತ್ರ", gp_tier: "ಸಾಧನೆಯ ಹಂತ", gp_lgd: "ಎಲ್‌ಜಿಡಿ ಕೋಡ್",
      gp_rank_state: "ಕರ್ನಾಟಕದಲ್ಲಿ ಶ್ರೇಣಿ", gp_rank_zilla: "ಜಿಲ್ಲೆಯಲ್ಲಿ ಶ್ರೇಣಿ", gp_rank_taluk: "ತಾಲ್ಲೂಕಿನಲ್ಲಿ ಶ್ರೇಣಿ", gp_vs_peers: "ಸಮಾನರೊಂದಿಗೆ ವಸೂಲಿ %", gp_this: "ಈ ಗ್ರಾ.ಪಂ.", gp_taluk_avg: "ತಾಲ್ಲೂಕು", gp_zilla_avg: "ಜಿಲ್ಲೆ", gp_state_avg: "ಕರ್ನಾಟಕ",
      gp_trend: "ಐದು ವರ್ಷಗಳ ಬೇಡಿಕೆ ಮತ್ತು ವಸೂಲಿ", gp_months: "ತಿಂಗಳವಾರು ವಸೂಲಿ", gp_heads: "ಆದಾಯ ಶೀರ್ಷಿಕೆವಾರು ವಸೂಲಿ", gp_books: "ಯೋಜನಾ ಖಾತೆಗಳು", gp_closed: "ಮುಕ್ತಾಯ", gp_open: "ಮುಕ್ತಾಯವಾಗಿಲ್ಲ",
      gp_closed_on: "{d} ರಂದು ಮುಕ್ತಾಯ", gp_hr: "ಜನರು ಮತ್ತು ಆಡಳಿತ", gp_seats: "ಸ್ಥಾನಗಳು", gp_members: "ಚುನಾಯಿತ ಸದಸ್ಯರು", gp_president: "ಅಧ್ಯಕ್ಷರ ನೋಂದಣಿ", gp_vp: "ಉಪಾಧ್ಯಕ್ಷರ ನೋಂದಣಿ",
      gp_sent: "ಇಒ ಗೆ ಕಳುಹಿಸಿದ ನೋಂದಣಿಗಳು", gp_approved: "ಇಒ ಅನುಮೋದನೆ", gp_pending: "ಇಒ ಬಳಿ ಬಾಕಿ", gp_rejected: "ಇಒ ತಿರಸ್ಕಾರ", gp_props: "ಆಸ್ತಿಗಳು", yes: "ಹೌದು", no: "ಇಲ್ಲ",
      gp_receipts: "ಯೋಜನಾ ಸ್ವೀಕೃತಿಗಳು", gp_expenditure: "ಯೋಜನಾ ವೆಚ್ಚ", gp_closing: "ಮುಕ್ತಾಯ ಶಿಲ್ಕು", gp_demand: "ಒಟ್ಟು ಬೇಡಿಕೆ", gp_collection: "ವಸೂಲಿ", gp_balance: "ಬಾಕಿ", gp_arrears: "ಹಿಂದಿನ ಬಾಕಿ",
      gp_year_col: "ವರ್ಷ", gp_ambiguous: "ಹಲವು ಗ್ರಾ.ಪಂ.ಗಳು ಈ ಹೆಸರನ್ನು ಹೊಂದಿವೆ; ಪ್ರತಿಯೊಂದರ ನಂತರ ತಾಲ್ಲೂಕು ತೋರಿಸಲಾಗಿದೆ.", gp_snapshot: "ಮಾನವ ಸಂಪನ್ಮೂಲ ಅಂಕಿಅಂಶ {d} ರಂತೆ",
      badge_top_taluk: "ತಾಲ್ಲೂಕಿನಲ್ಲಿ ಮೊದಲ 10%", badge_above_state: "ರಾಜ್ಯ ದರಕ್ಕಿಂತ ಹೆಚ್ಚು ವಸೂಲಿ", badge_below_state: "ರಾಜ್ಯ ದರಕ್ಕಿಂತ ಕಡಿಮೆ ವಸೂಲಿ", badge_all_closed: "ಎಲ್ಲಾ ಯೋಜನಾ ಖಾತೆಗಳು ಮುಕ್ತಾಯ",
      badge_pending_eo: "ಇಒ ಬಳಿ ಸಿಬ್ಬಂದಿ ಬಾಕಿ", badge_no_president: "ಅಧ್ಯಕ್ಷರ ನೋಂದಣಿ ಇಲ್ಲ", badge_full_house: "ಎಲ್ಲಾ ಸ್ಥಾನಗಳು ಭರ್ತಿ",
      cmp_title: "ಎರಡು ಜಿಲ್ಲೆಗಳ ಹೋಲಿಕೆ", cmp_sub: "ಒಂದು ಆರ್ಥಿಕ ವರ್ಷಕ್ಕೆ ಅಕ್ಕಪಕ್ಕ", cmp_a: "ಜಿಲ್ಲೆ ಎ", cmp_b: "ಜಿಲ್ಲೆ ಬಿ", cmp_go: "ಹೋಲಿಸಿ",
      cmp_summary: "{t} ಅಳತೆಗಳಲ್ಲಿ {n} ರಲ್ಲಿ {w} ಮುಂದಿದೆ.", cmp_tie: "ಹೋಲಿಸಿದ ಅಳತೆಗಳಲ್ಲಿ ಎರಡೂ ಸಮಾನವಾಗಿವೆ.", cmp_ahead: "ಮುಂದೆ",
      cmp_collection_pct: "ವಸೂಲಿ %", cmp_growth: "ಕಳೆದ ವರ್ಷಕ್ಕೆ ಹೋಲಿಸಿದ ವಸೂಲಿ ಬೆಳವಣಿಗೆ", cmp_collection_per_gp: "ಪ್ರತಿ ಗ್ರಾ.ಪಂ.ಗೆ ವಸೂಲಿ", cmp_books_closed: "ಮುಕ್ತಾಯಗೊಂಡ ಖಾತೆ %",
      cmp_all_closed: "ಎಲ್ಲಾ ಖಾತೆ ಮುಕ್ತಾಯಗೊಳಿಸಿದ ಗ್ರಾ.ಪಂ. %", cmp_seats_filled: "ಭರ್ತಿಯಾದ ಸ್ಥಾನಗಳು %", cmp_pending_eo: "ಇಒ ಬಳಿ ಬಾಕಿ (ಕಡಿಮೆ ಉತ್ತಮ)", cmp_gps: "ಗ್ರಾಮ ಪಂಚಾಯತ್‌ಗಳು",
      cmp_measure: "ಅಳತೆ", cmp_monthly: "ಮಾಸಿಕ ವಸೂಲಿ", cmp_heads: "ಆದಾಯ ಶೀರ್ಷಿಕೆವಾರು ವಸೂಲಿ", cmp_staff_per_gp: "ಪ್ರತಿ ಗ್ರಾ.ಪಂ.ಗೆ ಸಿಬ್ಬಂದಿ",
      chat_title: "ಪಂಚಾಯತ್ ರಾಜ್ ಮಾಹಿತಿ ಸಹಾಯಕ", chat_sub: "ಹಣಕಾಸು ಮತ್ತು ಲೆಕ್ಕಪತ್ರ, ಆದಾಯ ಮತ್ತು HRMS ಬಗ್ಗೆ ಸರಳ ಭಾಷೆಯಲ್ಲಿ ಕೇಳಿ", chat_placeholder: "ಪ್ರಶ್ನೆ ಕೇಳಿ, ಉದಾ. Which five zillas collected the most revenue in 2025-26?",
      ask: "ಕೇಳಿ", chat_en_only: "ಸಹಾಯಕ ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿ ಉತ್ತರಿಸುತ್ತದೆ.",
    },
  };
  const ZILLA_KN = { "Bagalkot": "ಬಾಗಲಕೋಟೆ", "Ballari": "ಬಳ್ಳಾರಿ", "Belagavi": "ಬೆಳಗಾವಿ", "Bengaluru Rural": "ಬೆಂಗಳೂರು ಗ್ರಾಮಾಂತರ",
    "Bengaluru South (Ramanagara)": "ಬೆಂಗಳೂರು ದಕ್ಷಿಣ (ರಾಮನಗರ)", "Bengaluru Urban": "ಬೆಂಗಳೂರು ನಗರ", "Bidar": "ಬೀದರ್",
    "Chamarajanagar": "ಚಾಮರಾಜನಗರ", "Chikkaballapura": "ಚಿಕ್ಕಬಳ್ಳಾಪುರ", "Chikkamagaluru": "ಚಿಕ್ಕಮಗಳೂರು", "Chitradurga": "ಚಿತ್ರದುರ್ಗ",
    "Dakshina Kannada": "ದಕ್ಷಿಣ ಕನ್ನಡ", "Davanagere": "ದಾವಣಗೆರೆ", "Dharwad": "ಧಾರವಾಡ", "Gadag": "ಗದಗ", "Hassan": "ಹಾಸನ", "Haveri": "ಹಾವೇರಿ",
    "Kalaburagi": "ಕಲಬುರಗಿ", "Kodagu": "ಕೊಡಗು", "Kolar": "ಕೋಲಾರ", "Koppal": "ಕೊಪ್ಪಳ", "Mandya": "ಮಂಡ್ಯ", "Mysuru": "ಮೈಸೂರು", "Raichur": "ರಾಯಚೂರು",
    "Shivamogga": "ಶಿವಮೊಗ್ಗ", "Tumakuru": "ತುಮಕೂರು", "Udupi": "ಉಡುಪಿ", "Uttara Kannada": "ಉತ್ತರ ಕನ್ನಡ", "Vijayanagara": "ವಿಜಯನಗರ",
    "Vijayapura": "ವಿಜಯಪುರ", "Yadgir": "ಯಾದಗಿರಿ", "Karnataka": "ಕರ್ನಾಟಕ" };
  const MON_KN = { Jan: "ಜನ", Feb: "ಫೆಬ್ರ", Mar: "ಮಾರ್ಚ್", Apr: "ಏಪ್ರಿ", May: "ಮೇ", Jun: "ಜೂನ್", Jul: "ಜುಲೈ", Aug: "ಆಗ", Sep: "ಸೆಪ್ಟೆ", Oct: "ಅಕ್ಟೋ", Nov: "ನವೆಂ", Dec: "ಡಿಸೆಂ" };

  let lang = "en";
  try { lang = localStorage.getItem("rdpr_lang") === "kn" ? "kn" : "en"; } catch (e) { /* private window */ }

  function t(key, vars) {
    let s = (D[lang] && D[lang][key]) || D.en[key] || key;
    if (vars) Object.keys(vars).forEach((k) => { s = s.split("{" + k + "}").join(vars[k]); });
    return s;
  }
  const zilla = (n) => (lang === "kn" && ZILLA_KN[n]) || n;
  const month = (label) => {          // 'MAR-2026' -> 'Mar 26' / 'ಮಾರ್ಚ್ 26'
    if (!label) return "";
    const [a, y] = label.split("-"), m = a.charAt(0) + a.slice(1).toLowerCase();
    return (lang === "kn" ? MON_KN[m] || m : m) + " " + y.slice(2);
  };
  const money = (v) => {
    if (v === null || v === undefined) return "–";
    const a = Math.abs(v), f = (x) => x.toLocaleString("en-IN", { maximumFractionDigits: 2 });
    if (a >= 1e7) return "₹" + f(v / 1e7) + " " + (lang === "kn" ? D.kn.crore : "cr");
    if (a >= 1e5) return "₹" + f(v / 1e5) + " " + D[lang].lakh;
    return "₹" + Math.round(v).toLocaleString("en-IN");
  };

  function apply(root) {
    (root || document).querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.getAttribute("data-i18n")); });
    (root || document).querySelectorAll("[data-i18n-ph]").forEach((el) => { el.setAttribute("placeholder", t(el.getAttribute("data-i18n-ph"))); });
    (root || document).querySelectorAll("[data-i18n-title]").forEach((el) => { el.setAttribute("title", t(el.getAttribute("data-i18n-title"))); });
    document.documentElement.lang = lang;
    document.body.classList.toggle("kn", lang === "kn");
  }
  function set(l) {
    lang = l === "kn" ? "kn" : "en";
    try { localStorage.setItem("rdpr_lang", lang); } catch (e) { /* ignore */ }
    apply();
    document.dispatchEvent(new CustomEvent("langchange", { detail: lang }));
    const b = document.getElementById("lang-btn");
    if (b) b.textContent = t("lang_switch");
  }
  function mount() {
    // The language switch lives at the foot of the left sidebar; pages without one keep a row under the header.
    if (!document.getElementById("lang-btn")) {
      const b = document.createElement("a");
      b.href = "#"; b.id = "lang-btn"; b.setAttribute("role", "button");
      b.textContent = t("lang_switch");
      b.addEventListener("click", (e) => { e.preventDefault(); set(lang === "en" ? "kn" : "en"); });
      // top right of the header row, on the same line as the heading
      const host = document.querySelector(".topbar-in") || document.getElementById("side-lang");
      if (host) host.appendChild(b);
    }
    apply();
  }
  window.I18N = { t, zilla, month, money, apply, set, get lang() { return lang; } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount); else mount();
})();

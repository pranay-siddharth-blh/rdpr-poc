-- RDPR core layer (L3): the reviewed star schema. Conformed dimensions shared by Finance & Accounting, Revenue and HRMS,
-- facts at their own grain with composite primary keys = the grain, every link a declared foreign key, and CHECK
-- constraints for the business rules the data must obey (a row that breaks one cannot be loaded).
-- Loaded by warehouse/build_warehouse.py (stage "core"); the AI never reads these tables (only mart_*).

-- ------------------------------------------------------------------ conformed dimensions
CREATE TABLE dim_zilla (
  zilla_id TEXT PRIMARY KEY, zilla_lgd_code INTEGER NOT NULL UNIQUE, zilla_name TEXT NOT NULL UNIQUE);
CREATE TABLE dim_taluk (
  taluk_id TEXT PRIMARY KEY, taluk_lgd_code INTEGER NOT NULL UNIQUE,
  zilla_id TEXT NOT NULL REFERENCES dim_zilla(zilla_id),
  taluk_name TEXT NOT NULL, total_gps INTEGER NOT NULL CHECK (total_gps > 0), gps_source TEXT,
  UNIQUE (zilla_id, taluk_name));
CREATE TABLE dim_gp (
  gp_id TEXT PRIMARY KEY, gp_lgd_code INTEGER NOT NULL UNIQUE,
  taluk_id TEXT NOT NULL REFERENCES dim_taluk(taluk_id),
  zilla_id TEXT NOT NULL REFERENCES dim_zilla(zilla_id),
  gp_name TEXT NOT NULL, taluk_assignment TEXT CHECK (taluk_assignment IN ('portal', 'reassigned')),
  size_class TEXT, performance_tier TEXT);
CREATE TABLE dim_fy (
  fy_id TEXT PRIMARY KEY, fy_label TEXT NOT NULL UNIQUE, start_date TEXT NOT NULL, end_date TEXT NOT NULL,
  data_through TEXT NOT NULL, is_current INTEGER NOT NULL CHECK (is_current IN (0, 1)),
  CHECK (start_date < end_date AND data_through <= end_date));
CREATE TABLE dim_month (
  month_id INTEGER PRIMARY KEY, fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id),
  fy_month_no INTEGER NOT NULL CHECK (fy_month_no BETWEEN 1 AND 12), calendar_year INTEGER NOT NULL,
  calendar_month_no INTEGER NOT NULL CHECK (calendar_month_no BETWEEN 1 AND 12), month_name TEXT NOT NULL,
  UNIQUE (fy_id, fy_month_no));
CREATE TABLE dim_date (
  date_id TEXT PRIMARY KEY, month_id INTEGER NOT NULL REFERENCES dim_month(month_id),
  fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id), weekday TEXT NOT NULL, is_working_day INTEGER NOT NULL CHECK (is_working_day IN (0, 1)));

-- ------------------------------------------------------------------ module dimensions
CREATE TABLE dim_scheme (
  scheme_id TEXT PRIMARY KEY, scheme_name TEXT NOT NULL, scheme_category TEXT NOT NULL,
  active_from_fy_id TEXT REFERENCES dim_fy(fy_id), active_to_fy_id TEXT REFERENCES dim_fy(fy_id),
  is_rollup INTEGER NOT NULL CHECK (is_rollup IN (0, 1)));
CREATE TABLE dim_fee_type (fee_type_id TEXT PRIMARY KEY, fee_type_name TEXT NOT NULL UNIQUE);
CREATE TABLE dim_property_type (
  property_type_id TEXT PRIMARY KEY, property_type_name TEXT NOT NULL UNIQUE, report_category TEXT NOT NULL);
CREATE TABLE dim_staff_type (staff_type_code INTEGER PRIMARY KEY, staff_type_name TEXT NOT NULL UNIQUE);
CREATE TABLE dim_designation (
  designation_id INTEGER PRIMARY KEY, staff_type_code INTEGER NOT NULL REFERENCES dim_staff_type(staff_type_code),
  report_level TEXT NOT NULL, designation_name TEXT NOT NULL,
  UNIQUE (report_level, staff_type_code, designation_name));

-- ------------------------------------------------------------------ Finance & Accounting
CREATE TABLE fact_fin_gp_year_closure (
  fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  scheme_id TEXT NOT NULL REFERENCES dim_scheme(scheme_id), closed_on TEXT REFERENCES dim_date(date_id),
  is_closed INTEGER NOT NULL CHECK (is_closed IN (0, 1)),
  CHECK ((is_closed = 1) = (closed_on IS NOT NULL)),
  PRIMARY KEY (fy_id, gp_id, scheme_id)) WITHOUT ROWID;
CREATE TABLE fact_fin_gp_month_closure (
  month_id INTEGER NOT NULL REFERENCES dim_month(month_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  scheme_id TEXT NOT NULL REFERENCES dim_scheme(scheme_id), closed_on TEXT REFERENCES dim_date(date_id),
  is_closed INTEGER NOT NULL CHECK (is_closed IN (0, 1)), days_after_month_end INTEGER,
  CHECK (is_closed = 1 OR days_after_month_end IS NULL),
  PRIMARY KEY (month_id, gp_id, scheme_id)) WITHOUT ROWID;
CREATE TABLE fact_fin_gp_scheme_financials (
  month_id INTEGER NOT NULL REFERENCES dim_month(month_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  scheme_id TEXT NOT NULL REFERENCES dim_scheme(scheme_id),
  opening_balance INTEGER NOT NULL CHECK (opening_balance >= 0), receipts INTEGER NOT NULL CHECK (receipts >= 0),
  expenditure INTEGER NOT NULL CHECK (expenditure >= 0), closing_balance INTEGER NOT NULL CHECK (closing_balance >= 0),
  -- the ledger identity holds to the rupee (the source rounds each month separately: stg_quality 'scheme_ledger_rounding')
  CHECK (abs(closing_balance - (opening_balance + receipts - expenditure)) <= 1),
  PRIMARY KEY (month_id, gp_id, scheme_id)) WITHOUT ROWID;
CREATE TABLE fact_fin_daybook_closure (
  date_id TEXT NOT NULL REFERENCES dim_date(date_id), taluk_id TEXT NOT NULL REFERENCES dim_taluk(taluk_id),
  scheme_id TEXT NOT NULL REFERENCES dim_scheme(scheme_id),
  total_gps INTEGER NOT NULL, gps_closed INTEGER NOT NULL, gps_pending INTEGER NOT NULL, closure_pct REAL NOT NULL,
  CHECK (gps_closed BETWEEN 0 AND total_gps AND gps_closed + gps_pending = total_gps AND closure_pct BETWEEN 0 AND 100),
  PRIMARY KEY (date_id, taluk_id, scheme_id)) WITHOUT ROWID;

-- ------------------------------------------------------------------ Revenue (demand - collection - balance)
CREATE TABLE fact_rev_dcb_register (
  fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  arrears REAL NOT NULL CHECK (arrears >= 0), year_demand REAL NOT NULL CHECK (year_demand >= 0),
  total_demand REAL NOT NULL, total_collection REAL NOT NULL CHECK (total_collection >= 0),
  adjustments REAL NOT NULL CHECK (adjustments >= 0), balance REAL NOT NULL CHECK (balance >= 0),
  CHECK (abs(total_demand - (arrears + year_demand)) < 0.02),
  CHECK (abs(balance - (total_demand - total_collection - adjustments)) < 0.02),
  PRIMARY KEY (fy_id, gp_id)) WITHOUT ROWID;
CREATE TABLE fact_rev_taxes_fees (
  fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  fee_type_id TEXT NOT NULL REFERENCES dim_fee_type(fee_type_id),
  arrears REAL NOT NULL, year_demand REAL NOT NULL, total_demand REAL NOT NULL, total_collection REAL NOT NULL,
  adjustments REAL NOT NULL, balance REAL NOT NULL,
  CHECK (abs(total_demand - (arrears + year_demand)) < 0.02),
  CHECK (abs(balance - (total_demand - total_collection - adjustments)) < 0.02),
  PRIMARY KEY (fy_id, gp_id, fee_type_id)) WITHOUT ROWID;
CREATE TABLE fact_rev_demand_statistics (
  fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  property_type_id TEXT NOT NULL REFERENCES dim_property_type(property_type_id),
  number_of_properties INTEGER NOT NULL CHECK (number_of_properties >= 0),
  arrears REAL NOT NULL, year_demand REAL NOT NULL, total_demand REAL NOT NULL, total_collection REAL NOT NULL,
  adjustments REAL NOT NULL, balance REAL NOT NULL,
  CHECK (abs(total_demand - (arrears + year_demand)) < 0.02),
  CHECK (abs(balance - (total_demand - total_collection - adjustments)) < 0.02),
  PRIMARY KEY (fy_id, gp_id, property_type_id)) WITHOUT ROWID;
CREATE TABLE fact_rev_property_type_stats (
  fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  number_of_properties INTEGER NOT NULL, agro_based_production_units INTEGER NOT NULL, commercial INTEGER NOT NULL,
  community INTEGER NOT NULL, government INTEGER NOT NULL, industrial INTEGER NOT NULL, non_residential INTEGER NOT NULL,
  religious INTEGER NOT NULL, residential INTEGER NOT NULL, commercial_cum_residential INTEGER NOT NULL,
  renewable INTEGER NOT NULL, telecom_tower INTEGER NOT NULL, other_unclassified INTEGER NOT NULL,
  CHECK (number_of_properties = agro_based_production_units + commercial + community + government + industrial
         + non_residential + religious + residential + commercial_cum_residential + renewable + telecom_tower + other_unclassified),
  PRIMARY KEY (fy_id, gp_id)) WITHOUT ROWID;
CREATE TABLE fact_rev_gp_monthly_collection (
  month_id INTEGER NOT NULL REFERENCES dim_month(month_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  fee_type_id TEXT NOT NULL REFERENCES dim_fee_type(fee_type_id), collection_amount REAL NOT NULL CHECK (collection_amount >= 0),
  PRIMARY KEY (month_id, gp_id, fee_type_id)) WITHOUT ROWID;

-- ------------------------------------------------------------------ HRMS
CREATE TABLE fact_hr_staff (
  staff_id TEXT PRIMARY KEY, gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  staff_type_code INTEGER NOT NULL REFERENCES dim_staff_type(staff_type_code),
  designation_id INTEGER NOT NULL REFERENCES dim_designation(designation_id),
  staff_name TEXT NOT NULL, gender TEXT NOT NULL CHECK (gender IN ('Male', 'Female')),
  date_of_birth TEXT, date_of_joining TEXT, registration_date TEXT,
  eo_rejected_date TEXT, resent_to_eo_date TEXT, eo_approved_date TEXT,
  approval_status TEXT NOT NULL CHECK (approval_status IN ('Approved', 'Pending at EO', 'Rejected')),
  monthly_gross_salary_inr INTEGER NOT NULL CHECK (monthly_gross_salary_inr > 0),
  employment_status TEXT NOT NULL CHECK (employment_status IN ('Active', 'Exited', 'Not Active')), exit_date TEXT,
  CHECK ((employment_status = 'Exited') = (exit_date IS NOT NULL)));
CREATE TABLE fact_hr_er_registration (
  fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id), snapshot_date TEXT NOT NULL,
  total_seats INTEGER NOT NULL, total_elected_members INTEGER NOT NULL, total_adhyaksha_president INTEGER NOT NULL,
  total_upadhyaksha INTEGER NOT NULL,
  CHECK (total_elected_members BETWEEN 0 AND total_seats AND total_adhyaksha_president IN (0, 1) AND total_upadhyaksha IN (0, 1)),
  PRIMARY KEY (fy_id, gp_id)) WITHOUT ROWID;
CREATE TABLE fact_hr_eo_approval (
  fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id), snapshot_date TEXT NOT NULL,
  staff_registrations_sent_to_eo INTEGER NOT NULL CHECK (staff_registrations_sent_to_eo >= 0),
  staff_approved_by_eo INTEGER NOT NULL CHECK (staff_approved_by_eo >= 0),
  staff_approval_pending_at_eo INTEGER NOT NULL CHECK (staff_approval_pending_at_eo >= 0),
  staff_registrations_rejected_by_eo INTEGER NOT NULL CHECK (staff_registrations_rejected_by_eo >= 0),
  staff_resent_for_approval_to_eo INTEGER NOT NULL CHECK (staff_resent_for_approval_to_eo >= 0),
  PRIMARY KEY (fy_id, gp_id)) WITHOUT ROWID;
CREATE TABLE fact_hr_salary_bills (
  month_id INTEGER NOT NULL REFERENCES dim_month(month_id), taluk_id TEXT NOT NULL REFERENCES dim_taluk(taluk_id),
  staff_type_code INTEGER NOT NULL REFERENCES dim_staff_type(staff_type_code),
  total_number_of_staff INTEGER NOT NULL, number_of_gps_generated_main_bill INTEGER NOT NULL,
  number_of_main_bill_generated INTEGER NOT NULL, number_of_main_bill_pdo_signed INTEGER NOT NULL,
  number_of_main_bill_president_signed INTEGER NOT NULL, number_of_main_bill_processed_by_bank INTEGER NOT NULL,
  number_of_auxiliary_bill_generated INTEGER NOT NULL, number_of_auxiliary_bill_pdo_signed INTEGER NOT NULL,
  number_of_auxiliary_bill_president_signed INTEGER NOT NULL, number_of_auxiliary_bill_processed_by_bank INTEGER NOT NULL,
  number_of_staff_salary_paid INTEGER NOT NULL, number_of_staff_salary_rejected_by_bank INTEGER NOT NULL,
  -- the bill funnel only narrows, and nobody is paid or rejected who is not on the payroll
  CHECK (number_of_main_bill_generated >= number_of_main_bill_pdo_signed
         AND number_of_main_bill_pdo_signed >= number_of_main_bill_president_signed
         AND number_of_main_bill_president_signed >= number_of_main_bill_processed_by_bank),
  CHECK (number_of_auxiliary_bill_generated >= number_of_auxiliary_bill_pdo_signed
         AND number_of_auxiliary_bill_pdo_signed >= number_of_auxiliary_bill_president_signed
         AND number_of_auxiliary_bill_president_signed >= number_of_auxiliary_bill_processed_by_bank),
  CHECK (number_of_staff_salary_paid + number_of_staff_salary_rejected_by_bank <= total_number_of_staff),
  PRIMARY KEY (month_id, taluk_id, staff_type_code)) WITHOUT ROWID;

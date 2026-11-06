"""Build the core star-schema database (dimensions + base facts) with declared PK / FK.
Sources: Finance_Accounting/FA_Finance.sqlite, Revenue/RV_Revenue.sqlite, Staged/HRMS/HRMS.sqlite (read only).
Output : DB/rdpr_star.sqlite
"""
import os, sqlite3, time
ROOT = 'c:/Users/Lenovo/Downloads/RDPR POC'
os.chdir(ROOT); os.makedirs('DB', exist_ok=True)
OUT = 'DB/rdpr_star.sqlite'
if os.path.exists(OUT): os.remove(OUT)
c = sqlite3.connect(OUT)
for a, p in (('fa', 'Finance_Accounting/FA_Finance.sqlite'), ('rv', 'Revenue/RV_Revenue.sqlite'), ('hr', 'Staged/HRMS/HRMS.sqlite')):
    c.execute(f"ATTACH DATABASE '{p}' AS {a}")
c.execute('PRAGMA foreign_keys=OFF')
t0 = time.time()
def log(m): print(f'[{time.time()-t0:6.0f}s] {m}', flush=True)

DDL = """
CREATE TABLE dim_zilla (
  zilla_id TEXT PRIMARY KEY, zilla_lgd_code INTEGER NOT NULL UNIQUE, zilla_name TEXT NOT NULL UNIQUE);
CREATE TABLE dim_taluk (
  taluk_id TEXT PRIMARY KEY, taluk_lgd_code INTEGER NOT NULL UNIQUE,
  zilla_id TEXT NOT NULL REFERENCES dim_zilla(zilla_id),
  taluk_name TEXT NOT NULL, total_gps INTEGER NOT NULL, gps_source TEXT,
  UNIQUE (zilla_id, taluk_name));
CREATE TABLE dim_gp (
  gp_id TEXT PRIMARY KEY, gp_lgd_code INTEGER NOT NULL UNIQUE,
  taluk_id TEXT NOT NULL REFERENCES dim_taluk(taluk_id),
  zilla_id TEXT NOT NULL REFERENCES dim_zilla(zilla_id),
  gp_name TEXT NOT NULL, taluk_assignment TEXT, size_class TEXT, performance_tier TEXT);
CREATE TABLE dim_fy (
  fy_id TEXT PRIMARY KEY, fy_label TEXT NOT NULL UNIQUE, start_date TEXT NOT NULL, end_date TEXT NOT NULL,
  data_through TEXT NOT NULL, is_current INTEGER NOT NULL);
CREATE TABLE dim_month (
  month_id INTEGER PRIMARY KEY, fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id),
  fy_month_no INTEGER NOT NULL, calendar_year INTEGER NOT NULL, calendar_month_no INTEGER NOT NULL, month_name TEXT NOT NULL,
  UNIQUE (fy_id, fy_month_no));
CREATE TABLE dim_date (
  date_id TEXT PRIMARY KEY, month_id INTEGER NOT NULL REFERENCES dim_month(month_id),
  fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id), weekday TEXT NOT NULL, is_working_day INTEGER NOT NULL);
CREATE TABLE dim_scheme (
  scheme_id TEXT PRIMARY KEY, scheme_name TEXT NOT NULL, scheme_category TEXT NOT NULL,
  active_from_fy_id TEXT REFERENCES dim_fy(fy_id), active_to_fy_id TEXT REFERENCES dim_fy(fy_id), is_rollup INTEGER NOT NULL);
CREATE TABLE dim_fee_type (fee_type_id TEXT PRIMARY KEY, fee_type_name TEXT NOT NULL UNIQUE);
CREATE TABLE dim_property_type (
  property_type_id TEXT PRIMARY KEY, property_type_name TEXT NOT NULL UNIQUE, report_category TEXT NOT NULL);
CREATE TABLE dim_staff_type (staff_type_code INTEGER PRIMARY KEY, staff_type_name TEXT NOT NULL UNIQUE);
CREATE TABLE dim_designation (
  designation_id INTEGER PRIMARY KEY, staff_type_code INTEGER NOT NULL REFERENCES dim_staff_type(staff_type_code),
  report_level TEXT NOT NULL, designation_name TEXT NOT NULL,
  UNIQUE (report_level, staff_type_code, designation_name));

-- ---------------- Finance ----------------
CREATE TABLE fact_fin_gp_year_closure (
  fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  scheme_id TEXT NOT NULL REFERENCES dim_scheme(scheme_id), closed_on TEXT REFERENCES dim_date(date_id),
  is_closed INTEGER NOT NULL CHECK (is_closed IN (0,1)),
  PRIMARY KEY (fy_id, gp_id, scheme_id)) WITHOUT ROWID;
CREATE TABLE fact_fin_gp_month_closure (
  month_id INTEGER NOT NULL REFERENCES dim_month(month_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  scheme_id TEXT NOT NULL REFERENCES dim_scheme(scheme_id), closed_on TEXT REFERENCES dim_date(date_id),
  is_closed INTEGER NOT NULL CHECK (is_closed IN (0,1)), days_after_month_end INTEGER,
  PRIMARY KEY (month_id, gp_id, scheme_id)) WITHOUT ROWID;
CREATE TABLE fact_fin_gp_scheme_financials (
  month_id INTEGER NOT NULL REFERENCES dim_month(month_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  scheme_id TEXT NOT NULL REFERENCES dim_scheme(scheme_id),
  opening_balance INTEGER NOT NULL, receipts INTEGER NOT NULL, expenditure INTEGER NOT NULL, closing_balance INTEGER NOT NULL,
  PRIMARY KEY (month_id, gp_id, scheme_id)) WITHOUT ROWID;
CREATE TABLE fact_fin_daybook_closure (
  date_id TEXT NOT NULL REFERENCES dim_date(date_id), taluk_id TEXT NOT NULL REFERENCES dim_taluk(taluk_id),
  scheme_id TEXT NOT NULL REFERENCES dim_scheme(scheme_id),
  total_gps INTEGER NOT NULL, gps_closed INTEGER NOT NULL, gps_pending INTEGER NOT NULL, closure_pct REAL NOT NULL,
  PRIMARY KEY (date_id, taluk_id, scheme_id)) WITHOUT ROWID;

-- ---------------- Revenue ----------------
CREATE TABLE fact_rev_dcb_register (
  fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  arrears REAL NOT NULL, year_demand REAL NOT NULL, total_demand REAL NOT NULL, total_collection REAL NOT NULL,
  adjustments REAL NOT NULL, balance REAL NOT NULL,
  PRIMARY KEY (fy_id, gp_id)) WITHOUT ROWID;
CREATE TABLE fact_rev_taxes_fees (
  fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  fee_type_id TEXT NOT NULL REFERENCES dim_fee_type(fee_type_id),
  arrears REAL NOT NULL, year_demand REAL NOT NULL, total_demand REAL NOT NULL, total_collection REAL NOT NULL,
  adjustments REAL NOT NULL, balance REAL NOT NULL,
  PRIMARY KEY (fy_id, gp_id, fee_type_id)) WITHOUT ROWID;
CREATE TABLE fact_rev_demand_statistics (
  fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  property_type_id TEXT NOT NULL REFERENCES dim_property_type(property_type_id), number_of_properties INTEGER NOT NULL,
  arrears REAL NOT NULL, year_demand REAL NOT NULL, total_demand REAL NOT NULL, total_collection REAL NOT NULL,
  adjustments REAL NOT NULL, balance REAL NOT NULL,
  PRIMARY KEY (fy_id, gp_id, property_type_id)) WITHOUT ROWID;
CREATE TABLE fact_rev_property_type_stats (
  fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  number_of_properties INTEGER NOT NULL, agro_based_production_units INTEGER NOT NULL, commercial INTEGER NOT NULL,
  community INTEGER NOT NULL, government INTEGER NOT NULL, industrial INTEGER NOT NULL, non_residential INTEGER NOT NULL,
  religious INTEGER NOT NULL, residential INTEGER NOT NULL, commercial_cum_residential INTEGER NOT NULL,
  renewable INTEGER NOT NULL, telecom_tower INTEGER NOT NULL, other_unclassified INTEGER NOT NULL,
  PRIMARY KEY (fy_id, gp_id)) WITHOUT ROWID;
CREATE TABLE fact_rev_gp_monthly_collection (
  month_id INTEGER NOT NULL REFERENCES dim_month(month_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  fee_type_id TEXT NOT NULL REFERENCES dim_fee_type(fee_type_id), collection_amount REAL NOT NULL,
  PRIMARY KEY (month_id, gp_id, fee_type_id)) WITHOUT ROWID;

-- ---------------- HRMS ----------------
CREATE TABLE fact_hr_staff (
  staff_id TEXT PRIMARY KEY, gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id),
  staff_type_code INTEGER NOT NULL REFERENCES dim_staff_type(staff_type_code),
  designation_id INTEGER NOT NULL REFERENCES dim_designation(designation_id),
  staff_name TEXT NOT NULL, gender TEXT NOT NULL, date_of_birth TEXT, date_of_joining TEXT, registration_date TEXT,
  eo_rejected_date TEXT, resent_to_eo_date TEXT, eo_approved_date TEXT, approval_status TEXT NOT NULL,
  monthly_gross_salary_inr INTEGER NOT NULL, employment_status TEXT NOT NULL, exit_date TEXT);
CREATE TABLE fact_hr_er_registration (
  fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id), snapshot_date TEXT NOT NULL,
  total_seats INTEGER NOT NULL, total_elected_members INTEGER NOT NULL, total_adhyaksha_president INTEGER NOT NULL,
  total_upadhyaksha INTEGER NOT NULL,
  PRIMARY KEY (fy_id, gp_id)) WITHOUT ROWID;
CREATE TABLE fact_hr_eo_approval (
  fy_id TEXT NOT NULL REFERENCES dim_fy(fy_id), gp_id TEXT NOT NULL REFERENCES dim_gp(gp_id), snapshot_date TEXT NOT NULL,
  staff_registrations_sent_to_eo INTEGER NOT NULL, staff_approved_by_eo INTEGER NOT NULL,
  staff_approval_pending_at_eo INTEGER NOT NULL, staff_registrations_rejected_by_eo INTEGER NOT NULL,
  staff_resent_for_approval_to_eo INTEGER NOT NULL,
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
  PRIMARY KEY (month_id, taluk_id, staff_type_code)) WITHOUT ROWID;
"""
c.executescript(DDL); log('schema created')

# ---------- dimensions ----------
c.executescript("""
INSERT INTO dim_zilla SELECT zilla_id, zilla_lgd_code, zilla_name FROM fa.dim_zilla;
INSERT INTO dim_taluk SELECT taluk_id, taluk_lgd_code, zilla_id, taluk_name, total_gps, gps_source FROM fa.dim_taluk;
INSERT INTO dim_gp SELECT gp_id, gp_lgd_code, taluk_id, zilla_id, gp_name, taluk_assignment, size_class, performance_tier FROM fa.dim_gp;
INSERT INTO dim_fy SELECT fy_id, fy_label, start_date, end_date, data_through, is_current FROM fa.dim_fy;
INSERT INTO dim_fy VALUES ('FY2122','2021-22','2021-04-01','2022-03-31','2022-03-31',0);   -- needed for HRMS Jan-Mar 2022
""")
MN = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
rows = []
for y in range(2022, 2028):
    for m in range(1, 13):
        if (y, m) < (2022, 1) or (y, m) > (2027, 3): continue
        fy_start = y if m >= 4 else y - 1
        rows.append((y * 100 + m, f'FY{str(fy_start)[2:]}{str(fy_start+1)[2:]}', (m - 4) % 12 + 1, y, m, MN[m - 1]))
c.executemany('INSERT INTO dim_month VALUES (?,?,?,?,?,?)', rows)
c.executescript("""
INSERT INTO dim_date SELECT date, CAST(substr(date,1,4) AS INTEGER)*100+CAST(substr(date,6,2) AS INTEGER), fy.fy_id, weekday, is_working_day
  FROM fa.dim_date d JOIN dim_fy fy ON fy.fy_label=d.fy_label;
INSERT INTO dim_scheme
  SELECT s.scheme_id, s.scheme_name, s.scheme_category, f1.fy_id, f2.fy_id, CASE WHEN s.scheme_id='ALL' THEN 1 ELSE 0 END
  FROM fa.dim_scheme s LEFT JOIN dim_fy f1 ON f1.fy_label=s.active_from_fy LEFT JOIN dim_fy f2 ON f2.fy_label=s.active_to_fy;
INSERT INTO dim_fee_type SELECT fee_type_id, fee_type_name FROM rv.dim_fee_type;
INSERT INTO dim_property_type SELECT property_type_id, property_type_name, report_category FROM rv.dim_property_type;
INSERT INTO dim_staff_type SELECT staff_type_code, staff_type_name FROM hr.dim_staff_type;
INSERT INTO dim_designation (staff_type_code, report_level, designation_name)
  SELECT st.staff_type_code, d.report_level, d.designation_name FROM hr.dim_designation d
  JOIN dim_staff_type st ON st.staff_type_name=d.staff_type_name ORDER BY d.report_level, st.staff_type_code, d.designation_name;
""")
c.commit(); log('dimensions loaded')

# ---------- facts ----------
FACT = [
('fact_fin_gp_year_closure', """INSERT INTO fact_fin_gp_year_closure SELECT fy.fy_id, s.gp_id, s.scheme_id, s.closed_on, s.is_closed
   FROM fa.fin_gp_year_closure s JOIN dim_fy fy ON fy.fy_label=s.fy_label"""),
('fact_fin_gp_month_closure', """INSERT INTO fact_fin_gp_month_closure SELECT m.month_id, s.gp_id, s.scheme_id, s.closed_on, s.is_closed, s.days_after_month_end
   FROM fa.fin_gp_month_closure s JOIN dim_fy fy ON fy.fy_label=s.fy_label JOIN dim_month m ON m.fy_id=fy.fy_id AND m.fy_month_no=s.month_no"""),
('fact_fin_gp_scheme_financials', """INSERT INTO fact_fin_gp_scheme_financials SELECT m.month_id, s.gp_id, s.scheme_id, s.opening_balance, s.receipts, s.expenditure, s.closing_balance
   FROM fa.fin_gp_scheme_financials s JOIN dim_fy fy ON fy.fy_label=s.fy_label JOIN dim_month m ON m.fy_id=fy.fy_id AND m.fy_month_no=s.month_no"""),
('fact_fin_daybook_closure', """INSERT INTO fact_fin_daybook_closure SELECT date, taluk_id, scheme_id, total_gps, gps_closed, gps_pending, closure_pct
   FROM fa.fin_daybook_closure_scheme"""),
('fact_rev_dcb_register', """INSERT INTO fact_rev_dcb_register SELECT fy.fy_id, s.gp_id, arrears, year_demand, total_demand, total_collection, adjustments, balance
   FROM rv.rev_dcb_register s JOIN dim_fy fy ON fy.fy_label=s.fy_label"""),
('fact_rev_taxes_fees', """INSERT INTO fact_rev_taxes_fees SELECT fy.fy_id, s.gp_id, fee_type_id, arrears, year_demand, total_demand, total_collection, adjustments, balance
   FROM rv.rev_taxes_fees s JOIN dim_fy fy ON fy.fy_label=s.fy_label"""),
('fact_rev_demand_statistics', """INSERT INTO fact_rev_demand_statistics SELECT fy.fy_id, s.gp_id, property_type_id, number_of_properties, arrears, year_demand, total_demand, total_collection, adjustments, balance
   FROM rv.rev_demand_statistics s JOIN dim_fy fy ON fy.fy_label=s.fy_label"""),
('fact_rev_property_type_stats', """INSERT INTO fact_rev_property_type_stats SELECT fy.fy_id, s.gp_id, number_of_properties, agro_based_production_units, commercial, community, government, industrial,
   non_residential, religious, residential, commercial_cum_residential, renewable, telecom_tower, other_unclassified
   FROM rv.rev_property_type_stats s JOIN dim_fy fy ON fy.fy_label=s.fy_label"""),
('fact_rev_gp_monthly_collection', """INSERT INTO fact_rev_gp_monthly_collection SELECT m.month_id, s.gp_id, s.fee_type_id, s.collection_amount
   FROM rv.rev_gp_monthly_collection s JOIN dim_fy fy ON fy.fy_label=s.fy_label JOIN dim_month m ON m.fy_id=fy.fy_id AND m.fy_month_no=s.month_no"""),
('fact_hr_staff', """INSERT INTO fact_hr_staff SELECT s.staff_id, s.gp_id, s.staff_type_code, d.designation_id, s.staff_name, s.gender, s.date_of_birth, s.date_of_joining,
   s.registration_date, s.eo_rejected_date, s.resent_to_eo_date, s.eo_approved_date, s.approval_status, s.monthly_gross_salary_inr, s.employment_status, s.exit_date
   FROM hr.hr_staff_register s JOIN dim_designation d ON d.designation_name=s.designation AND d.staff_type_code=s.staff_type_code AND d.report_level='GP'"""),
('fact_hr_er_registration', """INSERT INTO fact_hr_er_registration SELECT fy.fy_id, s.gp_id, substr(s.snapshot_date,1,10), total_seats, total_elected_members, total_adhyaksha_president, total_upadhyaksha
   FROM hr.hr_er_registration s JOIN dim_fy fy ON fy.fy_label=s.fy_label"""),
('fact_hr_eo_approval', """INSERT INTO fact_hr_eo_approval SELECT fy.fy_id, s.gp_id, substr(s.snapshot_date,1,10), staff_registrations_sent_to_eo, staff_approved_by_eo, staff_approval_pending_at_eo,
   staff_registrations_rejected_by_eo, staff_resent_for_approval_to_eo FROM hr.hr_eo_approval s JOIN dim_fy fy ON fy.fy_label=s.fy_label"""),
('fact_hr_salary_bills', """INSERT INTO fact_hr_salary_bills SELECT s.calendar_year*100+s.calendar_month_no, s.taluk_id, st.staff_type_code, total_number_of_staff, number_of_gps_generated_main_bill,
   number_of_main_bill_generated, number_of_main_bill_pdo_signed, number_of_main_bill_president_signed, number_of_main_bill_processed_by_bank, number_of_auxiliary_bill_generated,
   number_of_auxiliary_bill_pdo_signed, number_of_auxiliary_bill_president_signed, number_of_auxiliary_bill_processed_by_bank, number_of_staff_salary_paid, number_of_staff_salary_rejected_by_bank
   FROM hr.hr_monthly_salary s JOIN dim_staff_type st ON st.staff_type_name=s.staff_type_name"""),
]
SRC = {'fact_fin_gp_year_closure': 'fa.fin_gp_year_closure', 'fact_fin_gp_month_closure': 'fa.fin_gp_month_closure', 'fact_fin_gp_scheme_financials': 'fa.fin_gp_scheme_financials',
       'fact_fin_daybook_closure': 'fa.fin_daybook_closure_scheme', 'fact_rev_dcb_register': 'rv.rev_dcb_register', 'fact_rev_taxes_fees': 'rv.rev_taxes_fees',
       'fact_rev_demand_statistics': 'rv.rev_demand_statistics', 'fact_rev_property_type_stats': 'rv.rev_property_type_stats', 'fact_rev_gp_monthly_collection': 'rv.rev_gp_monthly_collection',
       'fact_hr_staff': 'hr.hr_staff_register', 'fact_hr_er_registration': 'hr.hr_er_registration', 'fact_hr_eo_approval': 'hr.hr_eo_approval', 'fact_hr_salary_bills': 'hr.hr_monthly_salary'}
for name, sql in FACT:
    c.execute(sql); c.commit()
    n = c.execute(f'SELECT count(*) FROM {name}').fetchone()[0]; s = c.execute(f'SELECT count(*) FROM {SRC[name]}').fetchone()[0]
    log(f'{name}: {n:,} rows (source {s:,}) {"OK" if n == s else "<<< ROW LOSS"}')

# ---------- secondary indexes for joins by geography / scheme ----------
IDX = ['fact_fin_gp_year_closure(gp_id)', 'fact_fin_gp_month_closure(gp_id)', 'fact_fin_gp_scheme_financials(gp_id)', 'fact_fin_daybook_closure(taluk_id)',
       'fact_rev_dcb_register(gp_id)', 'fact_rev_taxes_fees(gp_id)', 'fact_rev_demand_statistics(gp_id)', 'fact_rev_property_type_stats(gp_id)', 'fact_rev_gp_monthly_collection(gp_id)',
       'fact_hr_staff(gp_id)', 'fact_hr_er_registration(gp_id)', 'fact_hr_eo_approval(gp_id)', 'fact_hr_salary_bills(taluk_id)', 'dim_gp(taluk_id)', 'dim_gp(zilla_id)', 'dim_taluk(zilla_id)',
       'fact_fin_gp_month_closure(scheme_id)', 'fact_fin_gp_year_closure(scheme_id)']
for i, d in enumerate(IDX):
    t, col = d[:-1].split('(')
    c.execute(f'CREATE INDEX ix_{t}_{col.replace(",","_")} ON {t}({col})')
c.commit(); log('indexes built')
bad = c.execute('PRAGMA foreign_key_check').fetchall()
log(f'foreign_key_check: {len(bad)} violations')
for b in bad[:10]: print(b)
c.execute('ANALYZE'); c.commit(); log('done')

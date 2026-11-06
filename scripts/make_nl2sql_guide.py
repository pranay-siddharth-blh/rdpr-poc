"""Generate docs/NL2SQL_Schema_Guide.md from the live database and EXECUTE every sample question
(a sample is written to the guide only if its SQL runs and returns rows)."""
import sqlite3, time
from pathlib import Path
import pandas as pd
ROOT = str(Path(__file__).resolve().parent.parent)   # RDPR POC/RDPR POC
c = sqlite3.connect(f'{ROOT}/DB/rdpr_star.sqlite')

SAMPLES = [
 ('Finance', 'How many GPs in Badami taluk had closed the Own Resource Funds day book on 15 June 2023?',
  """SELECT f.gps_closed, f.total_gps FROM fact_fin_daybook_closure f JOIN dim_taluk t USING(taluk_id) JOIN dim_scheme s USING(scheme_id)
     WHERE t.taluk_name='Badami' AND s.scheme_name='Own Resource Funds' AND f.date_id='2023-06-15'"""),
 ('Finance', 'Which GPs in Belagavi zilla did not close the March 2025 month book for the 15th Finance Commission?',
  """SELECT g.gp_name, t.taluk_name FROM fact_fin_gp_month_closure f JOIN dim_gp g USING(gp_id) JOIN dim_taluk t USING(taluk_id) JOIN dim_zilla z ON z.zilla_id=g.zilla_id
     JOIN dim_scheme s USING(scheme_id) JOIN dim_month m USING(month_id)
     WHERE z.zilla_name='Belagavi' AND s.scheme_name='Fifteen Finance Commission Grants' AND m.calendar_year=2025 AND m.calendar_month_no=3 AND f.is_closed=0 ORDER BY t.taluk_name, g.gp_name"""),
 ('Finance', 'Which taluks have less than 50% closure of the Statutory Grants (GP Staff Salary) year book for 2024-25?',
  """SELECT t.taluk_name, z.zilla_name, v.closure_pct FROM vw_taluk_year_closure v JOIN dim_taluk t USING(taluk_id) JOIN dim_zilla z USING(zilla_id) JOIN dim_scheme s USING(scheme_id) JOIN dim_fy fy USING(fy_id)
     WHERE fy.fy_label='2024-25' AND s.scheme_name='Statutory Grants (GP Staff Salary)' AND v.closure_pct<50 ORDER BY v.closure_pct"""),
 ('Finance', 'What was the closing balance of the 15th Finance Commission grants in Bagalkot zilla at the end of March 2025?',
  """SELECT v.closing_balance FROM vw_zilla_scheme_financials v JOIN dim_zilla z USING(zilla_id) JOIN dim_scheme s USING(scheme_id)
     WHERE z.zilla_name='Bagalkot' AND s.scheme_name='Fifteen Finance Commission Grants' AND v.month_id=202503"""),
 ('Finance', 'Which scheme has the lowest year-book closure in 2025-26 statewide?',
  """SELECT s.scheme_name, v.closure_pct FROM vw_state_year_closure v JOIN dim_scheme s USING(scheme_id) JOIN dim_fy fy USING(fy_id)
     WHERE fy.fy_label='2025-26' AND s.is_rollup=0 ORDER BY v.closure_pct LIMIT 3"""),
 ('Revenue', 'Top 5 taluks by property tax collection in 2024-25.',
  """SELECT t.taluk_name, z.zilla_name, ROUND(v.total_collection/1e5,1) AS collection_lakh FROM vw_taluk_fee_type v JOIN dim_taluk t USING(taluk_id) JOIN dim_zilla z USING(zilla_id)
     JOIN dim_fee_type ft USING(fee_type_id) JOIN dim_fy fy USING(fy_id) WHERE fy.fy_label='2024-25' AND ft.fee_type_name='Property Taxes' ORDER BY v.total_collection DESC LIMIT 5"""),
 ('Revenue', 'Which zillas have the lowest collection percentage of total demand in 2025-26?',
  """SELECT z.zilla_name, ROUND(100.0*v.total_collection/v.total_demand,1) AS collection_pct FROM vw_zilla_dcb v JOIN dim_zilla z USING(zilla_id) JOIN dim_fy fy USING(fy_id)
     WHERE fy.fy_label='2025-26' ORDER BY collection_pct LIMIT 5"""),
 ('Revenue', 'How many commercial properties are there in each GP of Badami taluk in 2025-26?',
  """SELECT g.gp_name, p.commercial FROM fact_rev_property_type_stats p JOIN dim_gp g USING(gp_id) JOIN dim_taluk t USING(taluk_id) JOIN dim_fy fy USING(fy_id)
     WHERE t.taluk_name='Badami' AND fy.fy_label='2025-26' ORDER BY p.commercial DESC"""),
 ('Revenue', 'Which property types contribute most of the demand in Mysuru zilla in 2024-25?',
  """SELECT pt.property_type_name, ROUND(v.total_demand/1e5,1) AS demand_lakh, v.number_of_properties FROM vw_zilla_demand_by_property_type v JOIN dim_zilla z USING(zilla_id)
     JOIN dim_property_type pt USING(property_type_id) JOIN dim_fy fy USING(fy_id) WHERE z.zilla_name='Mysuru' AND fy.fy_label='2024-25' ORDER BY v.total_demand DESC LIMIT 5"""),
 ('HRMS', 'How many active GP staff are there in Badami taluk, by designation?',
  """SELECT d.designation_name, COUNT(*) AS staff FROM fact_hr_staff s JOIN dim_gp g USING(gp_id) JOIN dim_taluk t USING(taluk_id) JOIN dim_designation d USING(designation_id)
     WHERE t.taluk_name='Badami' AND s.employment_status='Active' GROUP BY d.designation_name ORDER BY staff DESC"""),
 ('HRMS', 'Month by month in 2025, how many staff had salary rejected by the bank in Belagavi taluk?',
  """SELECT m.month_name, SUM(f.number_of_staff_salary_rejected_by_bank) AS rejected FROM fact_hr_salary_bills f JOIN dim_taluk t USING(taluk_id) JOIN dim_month m USING(month_id)
     WHERE t.taluk_name='Belagavi' AND m.calendar_year=2025 GROUP BY m.month_id ORDER BY m.month_id"""),
 ('HRMS', 'Which GPs had no President (Adhyaksha) registered in 2024-25?',
  """SELECT g.gp_name, t.taluk_name FROM fact_hr_er_registration e JOIN dim_gp g USING(gp_id) JOIN dim_taluk t USING(taluk_id) JOIN dim_fy fy USING(fy_id)
     WHERE fy.fy_label='2024-25' AND e.total_adhyaksha_president=0 ORDER BY t.taluk_name LIMIT 10"""),
 ('HRMS', 'Which taluks have the most staff registrations pending at the EO in 2025-26?',
  """SELECT t.taluk_name, v.staff_approval_pending_at_eo FROM vw_taluk_eo_approval v JOIN dim_taluk t USING(taluk_id) JOIN dim_fy fy USING(fy_id)
     WHERE fy.fy_label='2025-26' ORDER BY v.staff_approval_pending_at_eo DESC LIMIT 5"""),
 ('Cross-module', 'For 2024-25, show Badami, Belagavi and Mysuru taluks with book-closure %, revenue collection and staff pending at the EO.',
  """SELECT t.taluk_name, v.all_books_closed_pct, v.scheme_books_closed_pct, ROUND(v.total_collection/1e5,1) AS collection_lakh, v.staff_approval_pending_at_eo
     FROM vw_taluk_year_summary v JOIN dim_taluk t USING(taluk_id) JOIN dim_fy fy USING(fy_id) WHERE fy.fy_label='2024-25' AND t.taluk_name IN ('Badami','Belagavi','Mysuru')"""),
 ('Cross-module', 'List GPs in 2025-26 whose books are not all closed, that still have revenue balance above 50 lakh and staff pending at the EO.',
  """SELECT s.gp_name, t.taluk_name, ROUND(s.revenue_balance/1e5,1) AS balance_lakh, s.staff_approval_pending_at_eo
     FROM vw_gp_year_summary s JOIN dim_taluk t USING(taluk_id) JOIN dim_fy fy USING(fy_id)
     WHERE fy.fy_label='2025-26' AND s.all_books_closed=0 AND s.revenue_balance>5000000 AND s.staff_approval_pending_at_eo>0 ORDER BY s.revenue_balance DESC LIMIT 5"""),
 ('Cross-module', 'Which zillas are in the bottom quarter on both book closure and revenue collection percentage in 2025-26?',
  """WITH r AS (SELECT z.zilla_name, v.scheme_books_closed_pct sc, v.collection_pct cp,
        NTILE(4) OVER (ORDER BY v.scheme_books_closed_pct) q_close, NTILE(4) OVER (ORDER BY v.collection_pct) q_coll
        FROM vw_zilla_year_summary v JOIN dim_zilla z USING(zilla_id) JOIN dim_fy fy USING(fy_id) WHERE fy.fy_label='2025-26')
     SELECT zilla_name, sc AS scheme_books_closed_pct, cp AS collection_pct FROM r WHERE q_close=1 AND q_coll=1"""),
 ('Cross-module', 'In 2024-25, month by month for Bagalkot zilla: Finance receipts, Revenue collection and HRMS staff paid.',
  """WITH fin AS (SELECT f.month_id, SUM(f.receipts) v FROM fact_fin_gp_scheme_financials f JOIN dim_gp g USING(gp_id) JOIN dim_zilla z ON z.zilla_id=g.zilla_id WHERE z.zilla_name='Bagalkot' GROUP BY 1),
     rev AS (SELECT month_id, SUM(collection_amount) v FROM vw_zilla_monthly_collection JOIN dim_zilla z USING(zilla_id) WHERE z.zilla_name='Bagalkot' GROUP BY 1),
     hr AS (SELECT month_id, SUM(number_of_staff_salary_paid) v FROM vw_zilla_salary_bills JOIN dim_zilla z USING(zilla_id) WHERE z.zilla_name='Bagalkot' GROUP BY 1)
     SELECT m.month_name, ROUND(fin.v/1e7,2) AS finance_receipts_cr, ROUND(rev.v/1e7,2) AS revenue_collection_cr, hr.v AS staff_paid
     FROM dim_month m JOIN fin USING(month_id) JOIN rev USING(month_id) JOIN hr USING(month_id) JOIN dim_fy fy USING(fy_id) WHERE fy.fy_label='2024-25' ORDER BY m.month_id"""),
]

def md_table(df):
    cols = list(df.columns)
    rows = ['| ' + ' | '.join(cols) + ' |', '|' + '---|' * len(cols)]
    rows += ['| ' + ' | '.join(str(v) for v in r) + ' |' for r in df.itertuples(index=False)]
    return '\n'.join(rows)

ok = []; bad = []
for mod, q, sql in SAMPLES:
    t = time.time()
    try:
        df = pd.read_sql(sql, c)
        dt = time.time() - t
        (ok if len(df) else bad).append((mod, q, sql, df, dt))
        if not len(df): print('EMPTY :', q)
        else: print(f'ok {dt:5.1f}s {len(df):4d} rows  {q[:80]}')
    except Exception as e:
        bad.append((mod, q, sql, None, 0)); print('ERROR :', q, '->', e)

md = ['# NL-to-SQL Schema Guide', '',
      'Everything an NL-to-SQL layer needs: how the database is organised, how to join across modules, and tested example questions.',
      'Database: `DB/rdpr_star.sqlite` (SQLite). Picture of the core layer: `db_core_star_schema.png`.', '',
      '## 1. Rules for generating SQL', '',
      '1. **Resolve names through dimensions.** Users say "Badami", "Own Resource Funds", "2024-25", "March 2025"; facts store ids. Join `dim_taluk.taluk_name`, `dim_zilla.zilla_name`, `dim_gp.gp_name`, `dim_scheme.scheme_name`, `dim_fy.fy_label`, `dim_month` (`calendar_year` + `calendar_month_no`, or `month_id` = YYYYMM), `dim_date.date_id` (a date string).',
      '2. **Pick the right level.** Zilla / taluk / state totals already exist as `vw_*` views; use them instead of re-aggregating GP-level facts. GP-level questions use the `fact_*` tables.',
      '3. **Cross-module questions: use the summary views** `vw_gp_year_summary`, `vw_taluk_year_summary`, `vw_zilla_year_summary` (one row per GP / taluk / zilla per financial year, combining Finance, Revenue and HRMS), or aggregate each fact to the same grain before joining. Never join two raw facts of different grain directly (rows multiply and totals are wrong).',
      '4. **Financial year vs calendar month.** `fy_id` / `fy_label` is the financial year (Apr-Mar). "March 2025" is `month_id = 202503`, which belongs to FY 2024-25.',
      '5. **"ALL schemes" is a derived measure.** A GP counts as closed for ALL only if every scheme book it has is closed. Closure counts of different schemes cannot be added together. `dim_scheme.is_rollup = 1` marks the `ALL` row; filter `is_rollup = 0` when ranking single schemes.',
      '6. **HRMS salary bills are taluk level only.** They cannot be broken down to GP.',
      '7. **Names are unique within their parent** (a taluk name can repeat across zillas only if the same name exists; check with `dim_zilla`). Use `LIKE` carefully; names are Title Case.', '',
      '## 2. Tables', '']
for kind, pref in (('Dimensions', 'dim_'), ('Facts', 'fact_')):
    md += [f'### {kind}', '', '| Table | Rows | Primary key | Foreign keys |', '|---|---|---|---|']
    for (t,) in c.execute(f"select name from sqlite_master where type='table' and name like '{pref}%' order by name"):
        info = c.execute(f'pragma table_info({t})').fetchall()
        pk = ', '.join(r[1] for r in sorted([r for r in info if r[5]], key=lambda r: r[5]))
        fk = ', '.join(f'{r[3]} -> {r[2]}' for r in c.execute(f'pragma foreign_key_list({t})'))
        n = c.execute(f'select count(*) from {t}').fetchone()[0]
        md.append(f'| `{t}` | {n:,} | {pk} | {fk} |')
    md.append('')
md += ['### Views (read-only roll-ups)', '', '| View | Columns |', '|---|---|']
for (v,) in c.execute("select name from sqlite_master where type='view' order by name"):
    md.append(f'| `{v}` | {", ".join(r[1] for r in c.execute(f"pragma table_info({v})"))} |')
md += ['', '## 3. Tested example questions', '',
       f'{len(ok)} questions below were executed against the database and returned rows. Result previews show the first rows.', '']
cur = None
for mod, q, sql, df, dt in ok:
    if mod != cur: md += [f'### {mod}', '']; cur = mod
    md += [f'**Q: {q}**', '', '```sql', ' '.join(sql.split()).replace(' FROM ', '\nFROM ').replace(' WHERE ', '\nWHERE '), '```',
           f'_{len(df)} row(s), {dt:.1f}s_', '', md_table(df.head(4)), '']
md += ['## 4. Known data caveats (carried from the source data)', '',
       '- **Synthetic data.** All names and numbers are invented; Badami GP names are real, others are fictitious.',
       '- **Day-book vs month-book closure are different measures.** A GP can close its day book on a date without having closed that month\'s book, so daily `gps_closed` can exceed the monthly closed count. This is not an error.',
       '- **Revenue breakdowns now tie to the DCB register** (demand statistics were rescaled per GP and year; see `build_notes`).',
       '- **Reassigned GPs.** 996 GPs moved to new taluks; the first 7 digits of their `gp_lgd_code` still show the original portal taluk. `dim_gp.taluk_assignment = \'reassigned\'` flags them.',
       '- **Current financial year is partial** (data through 30 Sep 2026): FY 2026-27 year-closure is 0% and only 6 months exist.',
       '- **Some GPs lack some schemes**, so scheme closure percentages use different denominators per scheme.']
open(f'{ROOT}/docs/NL2SQL_Schema_Guide.md', 'w', encoding='utf-8').write('\n'.join(md))
print(f'{len(ok)} ok, {len(bad)} failed/empty')

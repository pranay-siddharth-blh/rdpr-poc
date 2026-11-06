"""Run AFTER build_star_db.py.  Adds (1) data-gap fixes, (2) roll-up / summary views to DB/rdpr_star.sqlite.
Safe to re-run: the fixes are skipped if already applied (tracked in table build_notes)."""
import sqlite3, time
import numpy as np, pandas as pd
ROOT = 'c:/Users/Lenovo/Downloads/RDPR POC'
c = sqlite3.connect(f'{ROOT}/DB/rdpr_star.sqlite')
t0 = time.time()
def log(m): print(f'[{time.time()-t0:5.0f}s] {m}', flush=True)
c.execute('CREATE TABLE IF NOT EXISTS build_notes (step TEXT PRIMARY KEY, applied_on TEXT, detail TEXT)')

# ---------------- 1. Revenue: make demand statistics tie to the DCB register ----------------
if not c.execute("select 1 from build_notes where step='rev_demand_stats_tied_to_dcb'").fetchone():
    d = pd.read_sql('select * from fact_rev_demand_statistics', c)
    dcb = pd.read_sql('select * from fact_rev_dcb_register', c).set_index(['fy_id', 'gp_id'])
    pts = pd.read_sql('select fy_id, gp_id, number_of_properties from fact_rev_property_type_stats', c).set_index(['fy_id', 'gp_id'])
    key = ['fy_id', 'gp_id']
    before = d.total_demand.sum()
    def tie(col, target):
        """scale col so per (fy, gp) it sums to target; push the cent-level rounding residual onto the largest row"""
        s = d.groupby(key)[col].transform('sum')
        tgt = pd.Series(target.reindex(pd.MultiIndex.from_frame(d[key])).values, index=d.index)
        new = (d[col] * np.where(s > 0, tgt / s.replace(0, np.nan), 1)).fillna(0)
        new = new.round(2) if col != 'number_of_properties' else new.round(0)
        resid = (tgt - new.groupby([d.fy_id, d.gp_id]).transform('sum')).round(2)
        big = new.groupby([d.fy_id, d.gp_id]).transform('max') == new
        first = big.groupby([d.fy_id, d.gp_id]).cumsum().eq(1) & big
        d[col] = (new + np.where(first, resid, 0)).round(2 if col != 'number_of_properties' else 0)
    for col in ['arrears', 'year_demand', 'total_collection', 'adjustments']: tie(col, dcb[col])
    tie('number_of_properties', pts.number_of_properties)
    d['number_of_properties'] = d.number_of_properties.astype(int)
    d['total_demand'] = (d.arrears + d.year_demand).round(2)
    d['balance'] = (d.total_demand - d.total_collection - d.adjustments).round(2)
    c.execute('CREATE TEMP TABLE _ds AS SELECT * FROM fact_rev_demand_statistics WHERE 0')
    c.executemany('INSERT INTO _ds VALUES (?,?,?,?,?,?,?,?,?,?)', d[['fy_id', 'gp_id', 'property_type_id', 'number_of_properties', 'arrears', 'year_demand', 'total_demand', 'total_collection', 'adjustments', 'balance']].itertuples(index=False, name=None))
    c.execute('CREATE INDEX _ds_ix ON _ds(fy_id, gp_id, property_type_id)')
    c.execute("""UPDATE fact_rev_demand_statistics SET
        number_of_properties=(SELECT number_of_properties FROM _ds x WHERE x.fy_id=fact_rev_demand_statistics.fy_id AND x.gp_id=fact_rev_demand_statistics.gp_id AND x.property_type_id=fact_rev_demand_statistics.property_type_id),
        arrears=(SELECT arrears FROM _ds x WHERE x.fy_id=fact_rev_demand_statistics.fy_id AND x.gp_id=fact_rev_demand_statistics.gp_id AND x.property_type_id=fact_rev_demand_statistics.property_type_id),
        year_demand=(SELECT year_demand FROM _ds x WHERE x.fy_id=fact_rev_demand_statistics.fy_id AND x.gp_id=fact_rev_demand_statistics.gp_id AND x.property_type_id=fact_rev_demand_statistics.property_type_id),
        total_demand=(SELECT total_demand FROM _ds x WHERE x.fy_id=fact_rev_demand_statistics.fy_id AND x.gp_id=fact_rev_demand_statistics.gp_id AND x.property_type_id=fact_rev_demand_statistics.property_type_id),
        total_collection=(SELECT total_collection FROM _ds x WHERE x.fy_id=fact_rev_demand_statistics.fy_id AND x.gp_id=fact_rev_demand_statistics.gp_id AND x.property_type_id=fact_rev_demand_statistics.property_type_id),
        adjustments=(SELECT adjustments FROM _ds x WHERE x.fy_id=fact_rev_demand_statistics.fy_id AND x.gp_id=fact_rev_demand_statistics.gp_id AND x.property_type_id=fact_rev_demand_statistics.property_type_id),
        balance=(SELECT balance FROM _ds x WHERE x.fy_id=fact_rev_demand_statistics.fy_id AND x.gp_id=fact_rev_demand_statistics.gp_id AND x.property_type_id=fact_rev_demand_statistics.property_type_id)""")
    c.execute("INSERT INTO build_notes VALUES ('rev_demand_stats_tied_to_dcb', datetime('now'), ?)",
              (f'demand_statistics DCB columns and property counts rescaled per GP-FY to equal fact_rev_dcb_register / fact_rev_property_type_stats. total_demand before {before:,.0f}, after {d.total_demand.sum():,.0f}',))
    c.commit(); log('Revenue demand statistics tied to DCB register')

# ---------------- 2. views ----------------
VIEWS = {}
# --- Finance: closure (per scheme + derived ALL), month and year, taluk / zilla / state
def closure_view(level, grain):
    fact = 'fact_fin_gp_year_closure' if grain == 'year' else 'fact_fin_gp_month_closure'
    tcol = 'fy_id' if grain == 'year' else 'month_id'
    geo = {'taluk': ('g.taluk_id', 'taluk_id,'), 'zilla': ('g.zilla_id', 'zilla_id,'), 'state': ('', '')}[level]
    gsel = (geo[0] + ' AS ' + geo[0].split('.')[1] + ',') if geo[0] else ''
    ggrp = (geo[0] + ',') if geo[0] else ''
    tail = lambda alias: f'COUNT(*) AS total_gps, SUM({alias}) AS gps_closed, COUNT(*)-SUM({alias}) AS gps_pending, ROUND(100.0*SUM({alias})/COUNT(*),1) AS closure_pct'
    return f"""CREATE VIEW vw_{level}_{grain}_closure AS
 SELECT f.{tcol}, {gsel} f.scheme_id, {tail('f.is_closed')}
   FROM {fact} f JOIN dim_gp g USING(gp_id) GROUP BY f.{tcol}, {ggrp} f.scheme_id
 UNION ALL
 SELECT a.{tcol}, {gsel} 'ALL' AS scheme_id, {tail('a.all_closed')}
   FROM (SELECT {tcol}, gp_id, MIN(is_closed) AS all_closed FROM {fact} GROUP BY {tcol}, gp_id) a JOIN dim_gp g USING(gp_id)
   GROUP BY a.{tcol}{(', ' + geo[0]) if geo[0] else ''}"""
for lv in ('taluk', 'zilla', 'state'):
    for gr in ('year', 'month'): VIEWS[f'vw_{lv}_{gr}_closure'] = closure_view(lv, gr)

def sum_view(name, fact, tcol, keys, measures, level, extra=''):
    geo = {'taluk': 'g.taluk_id', 'zilla': 'g.zilla_id', 'state': ''}[level]
    gcol = geo.split('.')[1] if geo else ''
    sel = ', '.join(([f'f.{tcol}'] + ([f'{geo} AS {gcol}'] if geo else []) + [f'f.{k}' for k in keys]))
    grp = ', '.join(([f'f.{tcol}'] + ([geo] if geo else []) + [f'f.{k}' for k in keys]))
    m = ', '.join(f'SUM(f.{x}) AS {x}' for x in measures)
    join = 'JOIN dim_gp g USING(gp_id)' if (geo and 'gp_id' in fact_cols[fact]) else ''
    return f'CREATE VIEW {name} AS SELECT {sel}, {m} FROM {fact} f {join} GROUP BY {grp}'
fact_cols = {t: [r[1] for r in c.execute(f'pragma table_info({t})')] for (t,) in c.execute("select name from sqlite_master where name like 'fact_%'")}
FIN = ['opening_balance', 'receipts', 'expenditure', 'closing_balance']
DCB = ['arrears', 'year_demand', 'total_demand', 'total_collection', 'adjustments', 'balance']
for lv in ('taluk', 'zilla', 'state'):
    VIEWS[f'vw_{lv}_scheme_financials'] = sum_view(f'vw_{lv}_scheme_financials', 'fact_fin_gp_scheme_financials', 'month_id', ['scheme_id'], FIN, lv)
    VIEWS[f'vw_{lv}_dcb'] = sum_view(f'vw_{lv}_dcb', 'fact_rev_dcb_register', 'fy_id', [], DCB, lv)
    VIEWS[f'vw_{lv}_fee_type'] = sum_view(f'vw_{lv}_fee_type', 'fact_rev_taxes_fees', 'fy_id', ['fee_type_id'], DCB, lv)
    VIEWS[f'vw_{lv}_demand_by_property_type'] = sum_view(f'vw_{lv}_demand_by_property_type', 'fact_rev_demand_statistics', 'fy_id', ['property_type_id'], ['number_of_properties'] + DCB, lv)
    VIEWS[f'vw_{lv}_monthly_collection'] = sum_view(f'vw_{lv}_monthly_collection', 'fact_rev_gp_monthly_collection', 'month_id', ['fee_type_id'], ['collection_amount'], lv)
    VIEWS[f'vw_{lv}_eo_approval'] = sum_view(f'vw_{lv}_eo_approval', 'fact_hr_eo_approval', 'fy_id', [],
        ['staff_registrations_sent_to_eo', 'staff_approved_by_eo', 'staff_approval_pending_at_eo', 'staff_registrations_rejected_by_eo', 'staff_resent_for_approval_to_eo'], lv)
    VIEWS[f'vw_{lv}_er_registration'] = sum_view(f'vw_{lv}_er_registration', 'fact_hr_er_registration', 'fy_id', [],
        ['total_seats', 'total_elected_members', 'total_adhyaksha_president', 'total_upadhyaksha'], lv)
# taluk-level salary bills = fact_hr_salary_bills itself (already taluk grain)
SAL = [c_ for c_ in fact_cols['fact_hr_salary_bills'] if c_.startswith(('total_', 'number_of'))]
VIEWS['vw_zilla_salary_bills'] = f"""CREATE VIEW vw_zilla_salary_bills AS SELECT f.month_id, t.zilla_id, f.staff_type_code, {', '.join(f'SUM(f.{x}) AS {x}' for x in SAL)}
  FROM fact_hr_salary_bills f JOIN dim_taluk t USING(taluk_id) GROUP BY f.month_id, t.zilla_id, f.staff_type_code"""
VIEWS['vw_state_salary_bills'] = f"""CREATE VIEW vw_state_salary_bills AS SELECT month_id, staff_type_code, {', '.join(f'SUM({x}) AS {x}' for x in SAL)}
  FROM fact_hr_salary_bills GROUP BY month_id, staff_type_code"""
VIEWS['vw_taluk_staff_summary'] = """CREATE VIEW vw_taluk_staff_summary AS
 SELECT g.taluk_id, s.staff_type_code, s.employment_status, s.approval_status, COUNT(*) AS staff_count, SUM(s.monthly_gross_salary_inr) AS monthly_gross_salary_inr
 FROM fact_hr_staff s JOIN dim_gp g USING(gp_id) GROUP BY g.taluk_id, s.staff_type_code, s.employment_status, s.approval_status"""
# --- cross-module scorecards: one row per GP / taluk / zilla per financial year
VIEWS['vw_gp_year_summary'] = """CREATE VIEW vw_gp_year_summary AS
 SELECT g.gp_id, g.gp_name, g.taluk_id, g.zilla_id, fy.fy_id,
   fin.schemes_total, fin.schemes_closed, fin.all_books_closed,
   r.total_demand, r.total_collection, r.balance AS revenue_balance,
   ROUND(100.0*r.total_collection/NULLIF(r.total_demand,0),1) AS collection_pct,
   eo.staff_approved_by_eo, eo.staff_approval_pending_at_eo, eo.staff_registrations_rejected_by_eo,
   er.total_seats, er.total_elected_members
 FROM dim_gp g CROSS JOIN dim_fy fy
 LEFT JOIN (SELECT fy_id, gp_id, COUNT(*) schemes_total, SUM(is_closed) schemes_closed, MIN(is_closed) all_books_closed FROM fact_fin_gp_year_closure GROUP BY fy_id, gp_id) fin USING(fy_id, gp_id)
 LEFT JOIN fact_rev_dcb_register r USING(fy_id, gp_id)
 LEFT JOIN fact_hr_eo_approval eo USING(fy_id, gp_id)
 LEFT JOIN fact_hr_er_registration er USING(fy_id, gp_id)
 WHERE fy.fy_id <> 'FY2122'"""
for lv, key, tbl in (('taluk', 'taluk_id', 'dim_taluk'), ('zilla', 'zilla_id', 'dim_zilla')):
    VIEWS[f'vw_{lv}_year_summary'] = f"""CREATE VIEW vw_{lv}_year_summary AS
 SELECT s.{key}, s.fy_id, COUNT(*) AS total_gps, SUM(s.all_books_closed) AS gps_all_books_closed,
   ROUND(100.0*SUM(s.all_books_closed)/COUNT(*),1) AS all_books_closed_pct, ROUND(100.0*SUM(s.schemes_closed)/SUM(s.schemes_total),1) AS scheme_books_closed_pct,
   SUM(s.total_demand) AS total_demand, SUM(s.total_collection) AS total_collection, SUM(s.revenue_balance) AS revenue_balance,
   ROUND(100.0*SUM(s.total_collection)/NULLIF(SUM(s.total_demand),0),1) AS collection_pct,
   SUM(s.staff_approved_by_eo) AS staff_approved_by_eo, SUM(s.staff_approval_pending_at_eo) AS staff_approval_pending_at_eo,
   SUM(s.total_elected_members) AS total_elected_members, SUM(s.total_seats) AS total_seats
 FROM vw_gp_year_summary s GROUP BY s.{key}, s.fy_id"""
for name in list(VIEWS):
    c.execute(f'DROP VIEW IF EXISTS {name}')
for name, sql in VIEWS.items(): c.execute(sql)
c.commit(); log(f'{len(VIEWS)} views created')

# ---------------- 3. checks ----------------
q = lambda s: c.execute(s).fetchone()
print('demand_stats vs DCB (should be ~0):', q("""select round(max(abs(a.td-b.total_demand)),2), round(max(abs(a.tc-b.total_collection)),2), round(max(abs(a.bal-b.balance)),2)
  from (select fy_id,gp_id,sum(total_demand) td,sum(total_collection) tc,sum(balance) bal from fact_rev_demand_statistics group by 1,2) a join fact_rev_dcb_register b using(fy_id,gp_id)"""))
print('property counts vs property_type_stats max diff:', q("""select max(abs(a.n-b.number_of_properties)) from (select fy_id,gp_id,sum(number_of_properties) n from fact_rev_demand_statistics group by 1,2) a join fact_rev_property_type_stats b using(fy_id,gp_id)"""))
print('negative values in demand stats:', q("select count(*) from fact_rev_demand_statistics where balance<0 or number_of_properties<0 or total_collection<0"))
for v in ('vw_state_year_closure', 'vw_zilla_year_summary', 'vw_taluk_year_closure', 'vw_taluk_year_summary'):
    t = time.time(); n = q(f'select count(*) from {v}')[0]; log(f'{v}: {n:,} rows in {time.time()-t:.1f}s')
# ALL <= every single scheme (the earlier inconsistency): must now hold by construction
print('ALL > min(scheme) violations (taluk-year):', q("""select count(*) from vw_taluk_year_closure a join (select fy_id,taluk_id,min(gps_closed) m from vw_taluk_year_closure where scheme_id<>'ALL' group by 1,2) b using(fy_id,taluk_id) where a.scheme_id='ALL' and a.gps_closed>b.m"""))
c.execute('ANALYZE'); c.commit(); log('done')

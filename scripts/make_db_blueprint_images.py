import os, json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

OUT = str(Path(__file__).resolve().parent.parent / 'docs')
os.makedirs(OUT, exist_ok=True)

# key codes: PK, FK, AK (alternate/business key), '' plain.  third item = referenced table or note
T = {}
def add(name, kind, module, grain, rows, cols): T[name] = dict(kind=kind, module=module, grain=grain, rows=rows, cols=cols)

# ---------------- shared conformed dimensions ----------------
add('dim_zilla', 'dim', 'shared', 'one row per zilla (district)', '31',
    [('PK', 'zilla_id', 'Z01..Z31'), ('AK', 'zilla_lgd_code', 'portal/LGD code'), ('', 'zilla_name', '')])
add('dim_taluk', 'dim', 'shared', 'one row per taluk', '238',
    [('PK', 'taluk_id', 'T001..T238'), ('AK', 'taluk_lgd_code', ''), ('FK', 'zilla_id', 'dim_zilla'), ('', 'taluk_name', ''), ('', 'total_gps', 'GPs in taluk'), ('', 'gps_source', '')])
add('dim_gp', 'dim', 'shared', 'one row per Gram Panchayat (the common key of all 3 modules)', '6,099',
    [('PK', 'gp_id', 'G0001..G6099'), ('AK', 'gp_lgd_code', ''), ('FK', 'taluk_id', 'dim_taluk'), ('FK', 'zilla_id', 'dim_zilla (shortcut)'),
     ('', 'gp_name', ''), ('', 'taluk_assignment', 'portal / reassigned'), ('', 'size_class', ''), ('', 'performance_tier', '')])
add('dim_fy', 'dim', 'shared', 'one row per financial year', '6 (5 + FY2021-22 needed by HRMS)',
    [('PK', 'fy_id', 'FY2223..'), ('', 'fy_label', '2022-23'), ('', 'start_date', ''), ('', 'end_date', ''), ('', 'data_through', ''), ('', 'is_current', '')])
add('dim_month', 'dim', 'shared', 'one row per calendar month (NEW: reconciles fiscal vs calendar month)', '63',
    [('PK', 'month_id', 'YYYYMM e.g. 202204'), ('FK', 'fy_id', 'dim_fy'), ('', 'fy_month_no', 'Apr=1 .. Mar=12'), ('', 'calendar_year', ''), ('', 'calendar_month_no', 'Jan=1'), ('', 'month_name', '')])
add('dim_date', 'dim', 'shared', 'one row per calendar day', '1,644',
    [('PK', 'date_id', 'the date'), ('FK', 'month_id', 'dim_month'), ('FK', 'fy_id', 'dim_fy'), ('', 'weekday', ''), ('', 'is_working_day', '')])
# ---------------- module dimensions ----------------
add('dim_scheme', 'dim', 'fin', 'one row per scheme book', '14 (13 + ALL)',
    [('PK', 'scheme_id', 'S01..S13, ALL'), ('', 'scheme_name', ''), ('', 'scheme_category', ''), ('FK', 'active_from_fy_id', 'dim_fy'), ('FK', 'active_to_fy_id', 'dim_fy'), ('', 'is_rollup', 'NEW: 1 for ALL')])
add('dim_report', 'dim', 'shared', 'portal report catalogue (merges Finance 3 + Revenue 4 report types)', '7',
    [('PK', 'report_id', ''), ('', 'module', 'FIN / REV / HR'), ('', 'report_name', '')])
add('dim_fee_type', 'dim', 'rev', 'one row per fee / tax type', '5',
    [('PK', 'fee_type_id', 'F1..F5'), ('', 'fee_type_name', '')])
add('dim_property_type', 'dim', 'rev', 'one row per property type', '30',
    [('PK', 'property_type_id', 'P01..P30'), ('', 'property_type_name', ''), ('', 'report_category', '')])
add('dim_staff_type', 'dim', 'hr', 'one row per staff type', '7',
    [('PK', 'staff_type_code', ''), ('', 'staff_type_name', '')])
add('dim_designation', 'dim', 'hr', 'one row per designation (NEW surrogate key)', '176',
    [('PK', 'designation_id', 'NEW'), ('FK', 'staff_type_code', 'dim_staff_type'), ('', 'report_level', 'State/ZP/TP/GP'), ('', 'designation_name', '')])

# ---------------- Finance facts ----------------
add('fact_fin_gp_year_closure', 'fact', 'fin', 'GP x scheme x FY: year book closed?', '335,226',
    [('PK/FK', 'fy_id', 'dim_fy'), ('PK/FK', 'gp_id', 'dim_gp'), ('PK/FK', 'scheme_id', 'dim_scheme'), ('FK', 'closed_on', 'dim_date'), ('', 'is_closed', 'measure 0/1')])
add('fact_fin_gp_month_closure', 'fact', 'fin', 'GP x scheme x month: month book closed?', '3,656,334',
    [('PK/FK', 'month_id', 'dim_month'), ('PK/FK', 'gp_id', 'dim_gp'), ('PK/FK', 'scheme_id', 'dim_scheme'), ('FK', 'closed_on', 'dim_date'), ('', 'is_closed', 'measure'), ('', 'days_after_month_end', 'measure')])
add('fact_fin_gp_scheme_financials', 'fact', 'fin', 'GP x scheme x month: money flow', '3,656,334',
    [('PK/FK', 'month_id', 'dim_month'), ('PK/FK', 'gp_id', 'dim_gp'), ('PK/FK', 'scheme_id', 'dim_scheme'), ('', 'opening_balance, receipts', 'measures'), ('', 'expenditure, closing_balance', 'measures')])
add('fact_fin_daybook_closure', 'fact', 'fin', 'Taluk x scheme x day: GPs that closed day book', '3,595,884',
    [('PK/FK', 'date_id', 'dim_date'), ('PK/FK', 'taluk_id', 'dim_taluk'), ('PK/FK', 'scheme_id', 'dim_scheme'), ('', 'total_gps, gps_closed', 'measures'), ('', 'gps_pending, closure_pct', 'measures')])
add('agg_fin_taluk_year_closure', 'agg', 'fin', 'DERIVED: taluk x scheme(+ALL) x FY counts', '15,465',
    [('PK/FK', 'fy_id', 'dim_fy'), ('PK/FK', 'taluk_id', 'dim_taluk'), ('PK/FK', 'scheme_id', 'dim_scheme'), ('', 'total_gps, gps_closed, closure_pct', 'measures')])
add('agg_fin_taluk_month_closure', 'agg', 'fin', 'DERIVED: taluk x scheme(+ALL) x month counts', '168,450',
    [('PK/FK', 'month_id', 'dim_month'), ('PK/FK', 'taluk_id', 'dim_taluk'), ('PK/FK', 'scheme_id', 'dim_scheme'), ('', 'total_gps, gps_closed, closure_pct', 'measures')])
add('agg_fin_taluk_scheme_financials', 'agg', 'fin', 'DERIVED: taluk x scheme x month money', '155,598',
    [('PK/FK', 'month_id', 'dim_month'), ('PK/FK', 'taluk_id', 'dim_taluk'), ('PK/FK', 'scheme_id', 'dim_scheme'), ('', 'receipts, expenditure, balances', 'measures')])
add('agg_fin_taluk_daybook_all', 'agg', 'fin', 'DERIVED: taluk x day, all schemes combined', '297,024',
    [('PK/FK', 'date_id', 'dim_date'), ('PK/FK', 'taluk_id', 'dim_taluk'), ('', 'total_gps, gps_closed, closure_pct', 'measures')])

# ---------------- Revenue facts ----------------
add('fact_rev_dcb_register', 'fact', 'rev', 'GP x FY: Demand-Collection-Balance', '30,495',
    [('PK/FK', 'fy_id', 'dim_fy'), ('PK/FK', 'gp_id', 'dim_gp'), ('', 'arrears, year_demand, total_demand', 'measures'), ('', 'total_collection, adjustments, balance', 'measures')])
add('fact_rev_taxes_fees', 'fact', 'rev', 'GP x FY x fee type: DCB split by tax/fee', '132,165',
    [('PK/FK', 'fy_id', 'dim_fy'), ('PK/FK', 'gp_id', 'dim_gp'), ('PK/FK', 'fee_type_id', 'dim_fee_type'), ('', 'arrears ... balance (6 DCB measures)', 'measures')])
add('fact_rev_demand_statistics', 'fact', 'rev', 'GP x FY x property type: DCB + property count', '806,855',
    [('PK/FK', 'fy_id', 'dim_fy'), ('PK/FK', 'gp_id', 'dim_gp'), ('PK/FK', 'property_type_id', 'dim_property_type'), ('', 'number_of_properties + 6 DCB measures', 'measures')])
add('fact_rev_property_type_stats', 'fact', 'rev', 'GP x FY: property counts by category (wide)', '30,495',
    [('PK/FK', 'fy_id', 'dim_fy'), ('PK/FK', 'gp_id', 'dim_gp'), ('', 'number_of_properties + 12 category counts', 'measures')])
add('fact_rev_gp_monthly_collection', 'fact', 'rev', 'GP x month x fee type: collection amount', '1,427,382',
    [('PK/FK', 'month_id', 'dim_month'), ('PK/FK', 'gp_id', 'dim_gp'), ('PK/FK', 'fee_type_id', 'dim_fee_type'), ('', 'collection_amount', 'measure')])

# ---------------- HRMS facts ----------------
add('fact_hr_staff', 'fact', 'hr', 'one row per staff member (register)', '51,187',
    [('PK', 'staff_id', 'KA-GPS-nnnnnn'), ('FK', 'gp_id', 'dim_gp'), ('FK', 'staff_type_code', 'dim_staff_type'), ('FK', 'designation_id', 'dim_designation'),
     ('FK', 'joining / registration / approved / exit dates', 'dim_date'), ('', 'gender, status, monthly_gross_salary_inr', 'attributes + measure')])
add('fact_hr_er_registration', 'fact', 'hr', 'GP x FY snapshot: elected-representative registration', '30,495',
    [('PK/FK', 'fy_id', 'dim_fy'), ('PK/FK', 'gp_id', 'dim_gp'), ('', 'total_seats, total_elected_members', 'measures'), ('', 'president / upadhyaksha registered', 'measures')])
add('fact_hr_eo_approval', 'fact', 'hr', 'GP x FY snapshot: staff registrations at EO', '30,495',
    [('PK/FK', 'fy_id', 'dim_fy'), ('PK/FK', 'gp_id', 'dim_gp'), ('', 'sent, approved, pending, rejected, resent', 'measures')])
add('fact_hr_salary_bills', 'fact', 'hr', 'Taluk x staff type x month: salary bill funnel (TALUK grain only)', '40,698',
    [('PK/FK', 'month_id', 'dim_month'), ('PK/FK', 'taluk_id', 'dim_taluk'), ('PK/FK', 'staff_type_code', 'dim_staff_type'), ('', 'staff, main/aux bills, paid, rejected (14 measures)', 'measures')])

# ---------- foreign-key edges derived from spec ----------
def edges():
    E = []
    for n, t in T.items():
        for k, c, ref in t['cols']:
            if 'FK' in k and ref.split(' ')[0] in T:
                E.append((n, ref.split(' ')[0], c))
        if n == 'fact_hr_staff':
            E.append((n, 'dim_date', 'dates'))
    return E
E = edges()

# ================= IMAGE 1: bus matrix =================
dims = ['dim_fy', 'dim_month', 'dim_date', 'dim_zilla', 'dim_taluk', 'dim_gp', 'dim_scheme', 'dim_fee_type', 'dim_property_type', 'dim_staff_type', 'dim_designation']
facts = [n for n, t in T.items() if t['kind'] in ('fact', 'agg')]
direct = {(a, b) for a, b, _ in E}
def reach(f, d):
    if (f, d) in direct: return 2
    if d in ('dim_taluk', 'dim_zilla') and (f, 'dim_gp') in direct: return 1
    if d == 'dim_zilla' and (f, 'dim_taluk') in direct: return 1
    if d == 'dim_month' and ((f, 'dim_date') in direct): return 1
    if d == 'dim_fy' and ((f, 'dim_month') in direct or (f, 'dim_date') in direct): return 1
    if d == 'dim_designation' and False: return 0
    return 0
colr = {'fin': '#2b6cb0', 'rev': '#2f855a', 'hr': '#c05621', 'shared': '#4a5568'}
fig, ax = plt.subplots(figsize=(17, 11.5))
ax.set_xlim(-9.6, len(dims)); ax.set_ylim(-1.3, len(facts) + 1.6); ax.invert_yaxis(); ax.axis('off')
for j, d in enumerate(dims):
    ax.text(j + 0.5, -0.2, d.replace('dim_', ''), rotation=40, ha='left', va='bottom', fontsize=10, fontweight='bold', color='#1a202c')
ax.text(-9.5, -0.1, 'Fact / aggregate table  (grain)', fontsize=10, fontweight='bold', va='bottom')
for i, f in enumerate(facts):
    c = colr[T[f]['module']]
    ax.add_patch(Rectangle((-9.6, i), len(dims) + 9.6, 1, color=c, alpha=0.06 if i % 2 else 0.12, lw=0))
    ax.text(-9.5, i + 0.5, f, va='center', fontsize=9.5, color=c, fontweight='bold')
    ax.text(-5.6, i + 0.5, T[f]['grain'][:50], va='center', fontsize=7.8, color='#2d3748')
    for j, d in enumerate(dims):
        r = reach(f, d)
        if r == 2: ax.plot(j + 0.5, i + 0.5, 'o', color=c, ms=11)
        elif r == 1: ax.plot(j + 0.5, i + 0.5, 'o', mfc='white', mec=c, ms=9, mew=1.6)
ax.text(-9.5, len(facts) + 0.9, '●  direct foreign key        ○  reachable through the hierarchy (gp -> taluk -> zilla, date -> month -> fy)', fontsize=9.5)
ax.text(-9.5, len(facts) + 1.5, 'Two facts can be compared when they share a dimension: every module shares dim_gp / dim_taluk / dim_zilla and dim_fy / dim_month  =>  cross-module questions work.', fontsize=9.5, color='#2d3748')
ax.set_title('Conformed-dimension (bus) matrix  -  RDPR POC  (blue = Finance, green = Revenue, orange = HRMS)', fontsize=13, fontweight='bold', loc='left')
plt.savefig(f'{OUT}/db_bus_matrix.png', dpi=130, bbox_inches='tight'); plt.close()

# ================= IMAGE 2: ER / star diagram =================
LH = 1.55; W = 56
def height(n): return (len(T[n]['cols']) + 3.6) * LH
pos = {}
def stack(names, x, y0=2, gap=3):
    y = y0
    for n in names:
        pos[n] = (x, y); y += height(n) + gap
    return y
# columns
stack(['fact_fin_gp_year_closure', 'fact_fin_gp_month_closure', 'fact_fin_gp_scheme_financials', 'fact_fin_daybook_closure'], 2)
stack(['agg_fin_taluk_year_closure', 'agg_fin_taluk_month_closure', 'agg_fin_taluk_scheme_financials', 'agg_fin_taluk_daybook_all'], 62)
stack(['dim_scheme', 'dim_date', 'dim_month', 'dim_fy', 'dim_report'], 122)
stack(['dim_zilla', 'dim_taluk', 'dim_gp'], 182, y0=2, gap=6)
stack(['dim_fee_type', 'dim_property_type'], 242)
stack(['fact_rev_dcb_register', 'fact_rev_taxes_fees', 'fact_rev_demand_statistics', 'fact_rev_property_type_stats', 'fact_rev_gp_monthly_collection'], 302)
ybot = 150
for i, n in enumerate(['fact_hr_staff', 'fact_hr_er_registration', 'fact_hr_eo_approval', 'fact_hr_salary_bills']): pos[n] = (2 + i * 60, ybot)
pos['dim_staff_type'] = (262, ybot); pos['dim_designation'] = (262, ybot + 14)
pos['dim_staff_type'] = (242, ybot); pos['dim_designation'] = (302, ybot)
fig, ax = plt.subplots(figsize=(44, 19))
ax.set_xlim(0, 362); ax.set_ylim(185, 0); ax.axis('off')
fill = {'dim': {'shared': '#e2e8f0', 'fin': '#bee3f8', 'rev': '#c6f6d5', 'hr': '#feebc8'}}
def box(n):
    t = T[n]; x, y = pos[n]; h = height(n); c = colr[t['module']]
    ax.add_patch(FancyBboxPatch((x, y), W, h, boxstyle='round,pad=0.0,rounding_size=0.8', fc='white', ec=c, lw=2.2, zorder=3))
    ax.add_patch(Rectangle((x, y), W, LH * 1.35, fc=c if t['kind'] != 'dim' else '#2d3748', ec=c, lw=0, zorder=4))
    ax.text(x + 1, y + LH * 0.68, n + {'dim': '', 'fact': '   [FACT]', 'agg': '   [AGG]'}[t['kind']], color='white', fontsize=11.5, fontweight='bold', va='center', zorder=5)
    ax.text(x + 1, y + LH * 2.2, t['grain'][:66] + '   |  ' + t['rows'] + ' rows', fontsize=7.6, style='italic', color='#4a5568', va='center', zorder=5)
    for i, (k, cn, ref) in enumerate(t['cols']):
        yy = y + LH * (i + 3.4)
        kc = {'PK': '#c53030', 'PK/FK': '#c53030', 'FK': '#2b6cb0', 'AK': '#6b46c1'}.get(k, '#4a5568')
        if k: ax.text(x + 1, yy, k, fontsize=8.6, fontweight='bold', color=kc, va='center', zorder=5)
        ax.text(x + 8, yy, cn, fontsize=8.8, va='center', zorder=5, fontweight='bold' if 'PK' in k else 'normal')
        if ref: ax.text(x + W - 1, yy, ('-> ' + ref) if 'FK' in k else ref, fontsize=7.4, va='center', ha='right', color='#718096', zorder=5)
def anchor(n, side):
    x, y = pos[n]; h = height(n)
    return {'l': (x, y + h / 2), 'r': (x + W, y + h / 2), 't': (x + W / 2, y), 'b': (x + W / 2, y + h)}[side]
for a, b, c in E:
    if a not in pos or b not in pos: continue
    ax_, ay = pos[a]; bx, by = pos[b]
    side_a, side_b = ('r', 'l') if ax_ < bx else ('l', 'r')
    if abs(ax_ - bx) < 5: side_a, side_b = ('b', 't') if ay < by else ('t', 'b')
    p, q = anchor(a, side_a), anchor(b, side_b)
    col = colr[T[a]['module']] if T[a]['module'] != 'shared' else '#718096'
    ax.annotate('', xy=q, xytext=p, arrowprops=dict(arrowstyle='-|>', color=col, lw=1.1, alpha=0.55, shrinkA=0, shrinkB=0), zorder=1)
for n in T: box(n)
ax.text(2, -3, 'RDPR POC  -  Proposed star schema (blueprint, not built yet)', fontsize=26, fontweight='bold', va='bottom')
ax.text(2, 0.3, 'Red = primary key   Blue = foreign key (arrow points to the dimension it joins)   Purple = business/alternate key   Dark header = dimension, coloured header = fact (blue Finance, green Revenue, orange HRMS)   AGG = pre-computed roll-up kept for speed',
        fontsize=12.5, color='#2d3748', va='bottom')
plt.savefig(f'{OUT}/db_star_schema_blueprint.png', dpi=75, bbox_inches='tight'); plt.close()

# ================= markdown spec =================
md = ['# DB Design Blueprint (proposal - NOT built yet)', '',
      'Star schema over three modules (Finance & Accounting, Revenue, HRMS) sharing conformed dimensions.',
      'Images: `db_star_schema_blueprint.png` (tables, columns, keys, links) and `db_bus_matrix.png` (which fact joins which dimension).', '',
      'Legend: **PK** primary key, **FK** foreign key, **AK** business (alternate) key, `PK/FK` = column is part of a composite primary key and also a foreign key.', '']
order = [('Shared conformed dimensions', lambda t: t['kind'] == 'dim' and t['module'] == 'shared'),
         ('Module dimensions', lambda t: t['kind'] == 'dim' and t['module'] != 'shared'),
         ('Finance facts', lambda t: t['kind'] != 'dim' and t['module'] == 'fin'),
         ('Revenue facts', lambda t: t['kind'] != 'dim' and t['module'] == 'rev'),
         ('HRMS facts', lambda t: t['kind'] != 'dim' and t['module'] == 'hr')]
for title, f in order:
    md += [f'## {title}', '']
    for n, t in T.items():
        if not f(t): continue
        md += [f'### {n}  ({t["kind"].upper()})', f'*Grain:* {t["grain"]}  \n*Rows (current data):* {t["rows"]}', '', '| Key | Column | References / note |', '|---|---|---|']
        md += [f'| {k or ""} | {c} | {r} |' for k, c, r in t['cols']]
        md.append('')
open(f'{OUT}/_spec_tables.md', 'w', encoding='utf-8').write('\n'.join(md))
print('ok', len(T), 'tables', len(E), 'fk edges')

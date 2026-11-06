"""Draw the CORE star-schema layer (dimensions + base facts) straight from the built database's own metadata,
so the picture always matches the real PK / FK definitions.  Output: docs/db_core_star_schema.png"""
import sqlite3, os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

ROOT = str(Path(__file__).resolve().parent.parent)   # RDPR POC/RDPR POC
c = sqlite3.connect(f'{ROOT}/DB/rdpr_star.sqlite')
# the core layer only: the warehouse build also writes src_/stg_/ledger_/semantic_ and mart_ tables to the same file
tables = [r[0] for r in c.execute("select name from sqlite_master where type='table' and (name like 'dim\_%' escape '\' or name like 'fact\_%' escape '\') order by name")]
GRAIN = {
 'dim_zilla': ('shared', 'one row per zilla (district)'), 'dim_taluk': ('shared', 'one row per taluk'),
 'dim_gp': ('shared', 'one row per Gram Panchayat - the common key of all 3 modules'),
 'dim_fy': ('shared', 'one row per financial year'), 'dim_month': ('shared', 'one row per month: fiscal + calendar numbering'),
 'dim_date': ('shared', 'one row per calendar day'), 'dim_scheme': ('fin', 'one row per scheme book'),
 'dim_fee_type': ('rev', 'one row per fee / tax type'), 'dim_property_type': ('rev', 'one row per property type'),
 'dim_staff_type': ('hr', 'one row per staff type'), 'dim_designation': ('hr', 'one row per designation'),
 'fact_fin_gp_year_closure': ('fin', 'GP x scheme x FY - year book closed?'), 'fact_fin_gp_month_closure': ('fin', 'GP x scheme x month - month book closed?'),
 'fact_fin_gp_scheme_financials': ('fin', 'GP x scheme x month - money flow'), 'fact_fin_daybook_closure': ('fin', 'taluk x scheme x day - day book closures'),
 'fact_rev_dcb_register': ('rev', 'GP x FY - demand / collection / balance'), 'fact_rev_taxes_fees': ('rev', 'GP x FY x fee type'),
 'fact_rev_demand_statistics': ('rev', 'GP x FY x property type'), 'fact_rev_property_type_stats': ('rev', 'GP x FY - property counts by category'),
 'fact_rev_gp_monthly_collection': ('rev', 'GP x month x fee type - collection'),
 'fact_hr_staff': ('hr', 'one row per staff member'), 'fact_hr_er_registration': ('hr', 'GP x FY - elected-representative registration'),
 'fact_hr_eo_approval': ('hr', 'GP x FY - staff registrations at EO'), 'fact_hr_salary_bills': ('hr', 'taluk x staff type x month (taluk level only)'),
}
COL = {'fin': '#2b6cb0', 'rev': '#2f855a', 'hr': '#c05621', 'shared': '#4a5568'}
meta = {}
edges = []
for t in tables:
    info = c.execute(f'pragma table_info({t})').fetchall()
    fks = {r[3]: r[2] for r in c.execute(f'pragma foreign_key_list({t})').fetchall()}
    n = c.execute(f'select count(*) from {t}').fetchone()[0]
    lines, other = [], []
    for _, name, typ, notnull, d, pk in info:
        if pk or name in fks:
            tag = ('PK/FK' if pk and name in fks else 'PK' if pk else 'FK')
            lines.append((tag, name, '-> ' + fks[name] if name in fks else typ))
        else:
            other.append(name)
    if t.startswith('fact_') and len(other) > 2:
        lines.append(('', f'{len(other)} measures / attributes', ''))
    else:
        lines += [('', o, '') for o in other]
    uniq = [r[2] for r in c.execute(f'pragma index_list({t})').fetchall() if r[2] == 1 and r[3] == 'u']
    for r in c.execute(f'pragma index_list({t})').fetchall():
        if r[3] == 'u':
            cols = [x[2] for x in c.execute(f'pragma index_info({r[1]})')]
            if len(cols) == 1:
                lines = [(('AK' if (l[1] == cols[0] and l[0] == '') else l[0]), l[1], l[2]) for l in lines]
    meta[t] = dict(lines=lines, rows=n, module=GRAIN[t][0], grain=GRAIN[t][1], kind='fact' if t.startswith('fact_') else 'dim')
    for col, ref in fks.items(): edges.append((t, ref, col))

LH, W = 1.55, 58
H = lambda t: (len(meta[t]['lines']) + 3.6) * LH
pos = {}
def stack(names, x, y0=3, gap=3.5):
    y = y0
    for n in names: pos[n] = (x, y); y += H(n) + gap
stack(['fact_fin_gp_year_closure', 'fact_fin_gp_month_closure', 'fact_fin_gp_scheme_financials', 'fact_fin_daybook_closure'], 2)
stack(['dim_scheme', 'dim_date', 'dim_month', 'dim_fy'], 70)
stack(['dim_zilla', 'dim_taluk', 'dim_gp'], 138, gap=7)
stack(['dim_fee_type', 'dim_property_type'], 206)
stack(['fact_rev_dcb_register', 'fact_rev_taxes_fees', 'fact_rev_demand_statistics', 'fact_rev_property_type_stats', 'fact_rev_gp_monthly_collection'], 274, gap=3.5)
yb = 140
for i, n in enumerate(['fact_hr_staff', 'fact_hr_er_registration', 'fact_hr_eo_approval', 'fact_hr_salary_bills']): pos[n] = (2 + i * 68, yb)
pos['dim_staff_type'] = (274, yb); pos['dim_designation'] = (274, yb + 16)

fig, ax = plt.subplots(figsize=(42, 18)); ax.set_xlim(0, 336); ax.set_ylim(172, 0); ax.axis('off')
def anchor(n, s):
    x, y = pos[n]; h = H(n)
    return {'l': (x, y + h / 2), 'r': (x + W, y + h / 2), 't': (x + W / 2, y), 'b': (x + W / 2, y + h)}[s]
for a, b, col in edges:
    ax_, ay = pos[a]; bx, by = pos[b]
    sa, sb = ('r', 'l') if ax_ < bx else ('l', 'r')
    if abs(ax_ - bx) < 5: sa, sb = ('b', 't') if ay < by else ('t', 'b')
    ax.annotate('', xy=anchor(b, sb), xytext=anchor(a, sa), zorder=1,
                arrowprops=dict(arrowstyle='-|>', color=COL[meta[a]['module']] if meta[a]['module'] != 'shared' else '#718096', lw=1.2, alpha=0.55, shrinkA=0, shrinkB=0))
for n, m in meta.items():
    x, y = pos[n]; h = H(n); col = COL[m['module']]
    ax.add_patch(FancyBboxPatch((x, y), W, h, boxstyle='round,pad=0,rounding_size=0.8', fc='white', ec=col, lw=2.2, zorder=3))
    ax.add_patch(Rectangle((x, y), W, LH * 1.4, fc='#2d3748' if m['kind'] == 'dim' else col, ec=col, lw=0, zorder=4))
    ax.text(x + 1, y + LH * 0.7, n + ('   [FACT]' if m['kind'] == 'fact' else ''), color='white', fontsize=12, fontweight='bold', va='center', zorder=5)
    ax.text(x + 1, y + LH * 2.2, f"{m['grain']}   |   {m['rows']:,} rows", fontsize=7.8, style='italic', color='#4a5568', va='center', zorder=5)
    for i, (tag, cn, ref) in enumerate(m['lines']):
        yy = y + LH * (i + 3.4)
        kc = {'PK': '#c53030', 'PK/FK': '#c53030', 'FK': '#2b6cb0', 'AK': '#6b46c1'}.get(tag, '#4a5568')
        if tag: ax.text(x + 1, yy, tag, fontsize=8.8, fontweight='bold', color=kc, va='center', zorder=5)
        ax.text(x + 8.5, yy, cn, fontsize=9, va='center', zorder=5, fontweight='bold' if 'PK' in tag else 'normal')
        if ref: ax.text(x + W - 1, yy, ref, fontsize=7.6, va='center', ha='right', color='#718096', zorder=5)
ax.text(2, -3.5, 'RDPR POC  -  Core star schema (dimensions + base facts)', fontsize=26, fontweight='bold', va='bottom')
ax.text(2, 0.2, 'PK = primary key (composite PKs are the grain)   FK = foreign key, arrow points to the table it joins   AK = unique business key   '
        'Dark header = dimension; blue = Finance fact, green = Revenue fact, orange = HRMS fact.   Cross-module questions join through dim_gp / dim_taluk / dim_zilla and dim_fy / dim_month.',
        fontsize=12, color='#2d3748', va='bottom')
os.makedirs(f'{ROOT}/docs', exist_ok=True)
plt.savefig(f'{ROOT}/docs/db_core_star_schema.png', dpi=75, bbox_inches='tight'); plt.close()
print('image written;', len(meta), 'tables,', len(edges), 'foreign keys')

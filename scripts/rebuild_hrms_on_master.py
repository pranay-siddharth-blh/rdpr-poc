import pandas as pd, numpy as np, re, sqlite3, os
from pathlib import Path
os.chdir(Path(__file__).resolve().parent.parent)   # RDPR POC/RDPR POC
rng = np.random.default_rng(2026)
fa = pd.read_excel('Finance_Accounting/FA_Master.xlsx', sheet_name=None)
gpm, tkm, zlm = fa['dim_gp'], fa['dim_taluk'], fa['dim_zilla']
h = pd.read_excel('HRMS/GP_Synthetic_Data_2022_2026.xlsx', sheet_name=None)
ref = h['Ref_Districts_Taluks']
t2c = ref.set_index('Taluk')['Taluk Code']
norm = lambda s: re.sub(r'[^a-z0-9]', '', str(s).lower())

# ---- GP crosswalk: HRMS GP -> master GP (per taluk)
hg = h['GP_Master'].copy()
assert not hg.set_index(['Taluk', 'Grama_Panchayat']).index.duplicated().any()
rows = []; clones = []
gpm2 = gpm.assign(tc=gpm.taluk_id.map(tkm.set_index('taluk_id').taluk_lgd_code))
for tcode, mg in gpm2.groupby('tc'):
    hr = hg[hg.Taluk_Code == tcode].sort_values('GP_Code')
    mg = mg.sort_values('gp_lgd_code')
    hrn = {norm(r.Grama_Panchayat): r.GP_Code for r in hr.itertuples()}
    pair = {}; used = set()
    for r in mg.itertuples():
        k = norm(r.gp_name)
        if k in hrn and hrn[k] not in used:
            pair[r.gp_id] = (hrn[k], 'name_match'); used.add(hrn[k])
    left_h = [c for c in hr.GP_Code if c not in used]
    for r in [r for r in mg.itertuples() if r.gp_id not in pair]:
        if left_h:
            c = left_h.pop(0); pair[r.gp_id] = (c, 'order_match'); used.add(c)
        else:
            src = hr.GP_Code.iloc[rng.integers(len(hr))]
            pair[r.gp_id] = (src, 'cloned_profile'); clones.append((r.gp_id, src))
    for gid, (c, how) in pair.items(): rows.append((gid, c, how))
    for c in left_h: rows.append((None, c, 'dropped_not_in_master'))
xw = pd.DataFrame(rows, columns=['gp_id', 'hrms_old_gp_code', 'mapping_type'])
xw = xw.merge(hg[['GP_Code', 'Grama_Panchayat']].rename(columns={'GP_Code': 'hrms_old_gp_code', 'Grama_Panchayat': 'hrms_old_gp_name'}), on='hrms_old_gp_code', how='left')
xw = xw.merge(gpm[['gp_id', 'gp_lgd_code', 'gp_name']], on='gp_id', how='left')
xw['gp_lgd_code'] = xw.gp_lgd_code.astype('Int64')
print(xw.mapping_type.value_counts().to_dict(), flush=True)

G = gpm.set_index('gp_id'); T = tkm.set_index('taluk_id'); Z = zlm.set_index('zilla_id')
def geo(df):
    df['taluk_id'] = df.gp_id.map(G.taluk_id); df['zilla_id'] = df.gp_id.map(G.zilla_id)
    df['gp_lgd_code'] = df.gp_id.map(G.gp_lgd_code); df['gp_name'] = df.gp_id.map(G.gp_name)
    df['taluk_lgd_code'] = df.taluk_id.map(T.taluk_lgd_code); df['taluk_name'] = df.taluk_id.map(T.taluk_name)
    df['zilla_lgd_code'] = df.zilla_id.map(Z.zilla_lgd_code); df['zilla_name'] = df.zilla_id.map(Z.zilla_name)
    return df
GEO = ['zilla_id', 'zilla_lgd_code', 'zilla_name', 'taluk_id', 'taluk_lgd_code', 'taluk_name', 'gp_id', 'gp_lgd_code', 'gp_name']
fylab = lambda y: pd.Series(y).astype(int).astype(str) + '-' + ((pd.Series(y).astype(int) + 1) % 100).astype(str).str.zfill(2)

one = xw.dropna(subset=['gp_id'])
old2new = one[one.mapping_type != 'cloned_profile'].set_index('hrms_old_gp_code').gp_id
cl = pd.DataFrame(clones, columns=['gp_id', 'src'])
def remap(df, oldcol):
    base = df.merge(old2new.rename('gp_id'), left_on=oldcol, right_index=True, how='inner')
    ext = df.merge(cl, left_on=oldcol, right_on='src', how='inner').drop(columns='src')
    return pd.concat([base, ext], ignore_index=True), set(ext.gp_id)

# ---- Staff register
s = h['Staff_Register'].drop(columns=['District', 'Taluk', 'Grama_Panchayat'])
S, clone_ids = remap(s, 'GP_Code')
iscl = S.gp_id.isin(clone_ids)
cs = S[iscl].copy(); S = S[~iscl]
nxt = int(s.Staff_ID.str[-6:].astype(int).max()) + 1
cs['Staff_ID'] = ['KA-GPS-%06d' % (nxt + i) for i in range(len(cs))]
for g in ['Male', 'Female']:
    m = cs.Gender == g
    cs.loc[m, 'Staff_Name'] = s[s.Gender == g].Staff_Name.sample(m.sum(), replace=True, random_state=7).values
S = pd.concat([S, cs], ignore_index=True)
S = geo(S).sort_values('gp_lgd_code', kind='stable').reset_index(drop=True)
S = S.drop(columns=['GP_Code', 'Taluk_Code', 'District_Code'], errors='ignore')

# ---- ER / EO
gname2old = hg.set_index(['Taluk', 'Grama_Panchayat']).GP_Code
def key(df):
    df = df.copy()
    df['GP_Code'] = [gname2old[(t, g)] for t, g in zip(df.Taluk, df.Grama_Panchayat)]
    return df.drop(columns=['District', 'Taluk', 'Grama_Panchayat'])
ER = geo(remap(key(h['ER_Registration']), 'GP_Code')[0])
EO = geo(remap(key(h['EO_Approval']), 'GP_Code')[0])
for d in (ER, EO):
    d.drop(columns=['GP_Code'], inplace=True)
    sd = pd.to_datetime(d.Snapshot_Date)
    d['fy_label'] = fylab(np.where(sd.dt.month >= 4, sd.dt.year, sd.dt.year - 1)).values
ER = ER.sort_values(['Year', 'gp_lgd_code']).reset_index(drop=True)
EO = EO.sort_values(['Year', 'gp_lgd_code']).reset_index(drop=True)

# ---- Monthly salary: rescale taluk x staff type counts to the new staff / GP base
ms = h['Monthly_Salary'].copy(); ms['Taluk_Code'] = ms.Taluk.map(t2c)
so = s.copy(); so['Taluk_Code'] = so.GP_Code // 1000
oldn = so.groupby(['Taluk_Code', 'Staff_Type']).size()
newn = S.groupby(['taluk_lgd_code', 'Staff_Type']).size()
oldg = hg.groupby('Taluk_Code').size(); newg = tkm.set_index('taluk_lgd_code').total_gps
idx = pd.MultiIndex.from_arrays([ms.Taluk_Code, ms.Staff_Type])
r = newn.reindex(idx).fillna(0).values / np.maximum(oldn.reindex(idx).fillna(0).values, 1)
rg = (ms.Taluk_Code.map(newg) / ms.Taluk_Code.map(oldg)).values
for c in [c for c in ms.columns if c.startswith(('Number', 'Total'))]:
    f = rg if c == 'Number_of_GPs_Generated_Main_Bill' else r
    ms[c] = np.floor(ms[c].values * f + 1e-9).astype(int)
ms['Number_of_GP'] = ms.Taluk_Code.map(newg).astype(int)
ms['Number_of_GPs_Generated_Main_Bill'] = np.minimum(ms.Number_of_GPs_Generated_Main_Bill, ms.Number_of_GP)
ms['Total_Number_Of_Staff'] = np.maximum(ms.Total_Number_Of_Staff, ms.Number_of_Staff_Salary_Paid + ms.Number_of_Staff_Salary_Rejected_by_Bank)
ms['taluk_id'] = ms.Taluk_Code.map(tkm.set_index('taluk_lgd_code').taluk_id); ms['zilla_id'] = ms.taluk_id.map(T.zilla_id)
ms['taluk_lgd_code'] = ms.Taluk_Code; ms['taluk_name'] = ms.taluk_id.map(T.taluk_name)
ms['zilla_lgd_code'] = ms.zilla_id.map(Z.zilla_lgd_code); ms['zilla_name'] = ms.zilla_id.map(Z.zilla_name)
ms = ms.drop(columns=['District', 'Taluk', 'Taluk_Code'])
ms['fy_label'] = fylab(np.where(ms.Month >= 4, ms.Year, ms.Year - 1)).values
ms['fy_month_no'] = ((ms.Month - 4) % 12) + 1

# ---- naming convention: snake_case; zilla/taluk/gp terminology as in Finance + Revenue
ren = {'Year': 'calendar_year', 'Month': 'calendar_month_no', 'Month_Name': 'month_name', 'Number_of_GP': 'number_of_gp',
       'Number_of_GPs_Generated_Main_Bill': 'number_of_gps_generated_main_bill', 'Staff_Type': 'staff_type_name'}
def snake(df):
    df = df.rename(columns=ren); df.columns = [c.lower() for c in df.columns]; return df
S, ER, EO, ms = [snake(x) for x in (S, ER, EO, ms)]
def order(df, first):
    g = [c for c in GEO if c in df.columns]
    return df[first + g + [c for c in df.columns if c not in first + g]]
S = order(S, ['staff_id']); ER = order(ER, ['fy_label', 'calendar_year', 'snapshot_date']); EO = order(EO, ['fy_label', 'calendar_year', 'snapshot_date'])
ms = order(ms, ['fy_label', 'fy_month_no', 'calendar_year', 'calendar_month_no', 'month_name'])
st = h['Ref_Staff_Types'].rename(columns={'Code': 'staff_type_code', 'Staff Type': 'staff_type_name'})
de = h['Ref_Designations'].rename(columns={'Report Level': 'report_level', 'Staff Type': 'staff_type_name', 'Designation': 'designation_name'})
T_ = {'hr_staff_register': S, 'hr_er_registration': ER, 'hr_eo_approval': EO, 'hr_monthly_salary': ms,
      'dim_staff_type': st, 'dim_designation': de, 'hr_gp_crosswalk': xw}
os.makedirs('Staged/HRMS/csv', exist_ok=True)
for k, v in T_.items(): v.to_csv(f'Staged/HRMS/csv/{k}.csv', index=False)
if os.path.exists('Staged/HRMS/HRMS.sqlite'): os.remove('Staged/HRMS/HRMS.sqlite')
con = sqlite3.connect('Staged/HRMS/HRMS.sqlite')
for k, v in T_.items(): v.to_sql(k, con, index=False)
for k, v in {'dim_zilla': zlm, 'dim_taluk': tkm, 'dim_gp': gpm, 'dim_fy': fa['dim_fy']}.items(): v.to_sql(k, con, index=False)
con.close()
print('db done', {k: v.shape for k, v in T_.items()}, flush=True)
with pd.ExcelWriter('Staged/HRMS/HRMS_Data.xlsx') as w:
    for k, v in T_.items(): v.to_excel(w, sheet_name=k[:31], index=False)
print('xlsx done', flush=True)

# DB Design Blueprint

> **Status: core layer built** in `DB/rdpr_star.sqlite` (see `HANDOFF.md` section 5). The authoritative picture is `db_core_star_schema.png`. The earlier proposal below (29 tables, with `dim_report` and `agg_*` roll-ups) is the longer-term target; differences in the built core: no `dim_report`, no `agg_*` tables yet, and staff dates in `fact_hr_staff` are plain dates.

Star schema over three modules (Finance & Accounting, Revenue, HRMS) sharing conformed dimensions.
Images: `db_star_schema_blueprint.png` (every table, column, key and link) and `db_bus_matrix.png` (which fact joins which dimension).
29 tables: 12 dimensions, 13 facts, 4 pre-computed aggregates.

## Design rules

1. **Star schema.** Facts hold numbers and only ids; dimensions hold names and descriptions. Facts never store names (current files repeat zilla/taluk/gp names in some fact tables - these are dropped).
2. **One geography.** `dim_gp` -> `dim_taluk` -> `dim_zilla`. Every GP-level fact joins `dim_gp`; taluk-level facts join `dim_taluk`. `dim_gp` also carries `zilla_id` as a shortcut.
3. **One time axis.** `dim_fy`, `dim_month` (new, `YYYYMM`, holds both fiscal and calendar month numbers) and `dim_date`. Finance and Revenue use fiscal month (Apr = 1); HRMS uses calendar month - `dim_month` reconciles them.
4. **Every table has a primary key; every link is a foreign key.** Composite keys on facts are the grain (listed per table below).
5. **Naming:** `dim_*`, `fact_<module>_*`, `agg_<module>_*`; ids are `*_id`, official codes are `*_lgd_code`; lower-case snake_case.
6. **Aggregates** (`agg_*`) are derived from GP-level facts, kept only for speed. Zilla and state roll-ups stay as views.

## Answering cross-module questions

All three modules share `dim_gp` / `dim_taluk` / `dim_zilla` and `dim_fy` / `dim_month`. To combine modules, **aggregate each fact to the shared grain first, then join on it** (joining raw facts of different grains multiplies rows and gives wrong totals). Examples:

- GP-year grain `(gp_id, fy_id)`: closure % (Finance) + total collection (Revenue) + staff pending at EO (HRMS).
- Taluk-year grain `(taluk_id, fy_id)`: add salary bills (HRMS, taluk-level only).

Sketch:
```sql
WITH fin AS (SELECT gp_id, fy_id, AVG(is_closed) closure_rate FROM fact_fin_gp_year_closure GROUP BY 1,2),
     rev AS (SELECT gp_id, fy_id, total_collection FROM fact_rev_dcb_register),
     hr  AS (SELECT gp_id, fy_id, staff_approval_pending_at_eo FROM fact_hr_eo_approval)
SELECT g.gp_name, t.taluk_name, f.closure_rate, r.total_collection, h.staff_approval_pending_at_eo
FROM dim_gp g JOIN dim_taluk t USING (taluk_id)
JOIN fin f USING (gp_id) JOIN rev r USING (gp_id, fy_id) JOIN hr h USING (gp_id, fy_id)
WHERE f.fy_id = 'FY2425';
```

## Changes from the current files (all to be applied when building)

| Change | Why |
|---|---|
| Facts use `fy_id` instead of `fy_label` | one proper key to `dim_fy` |
| Facts use `month_id` instead of `month_no` | fiscal vs calendar month confusion |
| Add `dim_month`, `dim_designation`, `dim_report`; add FY 2021-22 to `dim_fy` | missing links |
| Drop names from fact tables and `zilla_name` from `dim_taluk` | no repeated text in facts |
| HRMS monthly salary joins `staff_type_code`, not the name | proper key |
| `dim_scheme.is_rollup` flags the `ALL` row | keeps non-additive rows out of sums |
| Rename tables with `fact_` / `agg_` prefixes | clear roles |
| Declare PK, FK and indexes | none exist in current SQLite files |

## Open decisions

See section 5 of `HANDOFF.md`.

---

# Table specifications (generated from the same source as the image)


### dim_zilla  (DIM)
*Grain:* one row per zilla (district)  
*Rows (current data):* 31

| Key | Column | References / note |
|---|---|---|
| PK | zilla_id | Z01..Z31 |
| AK | zilla_lgd_code | portal/LGD code |
|  | zilla_name |  |

### dim_taluk  (DIM)
*Grain:* one row per taluk  
*Rows (current data):* 238

| Key | Column | References / note |
|---|---|---|
| PK | taluk_id | T001..T238 |
| AK | taluk_lgd_code |  |
| FK | zilla_id | dim_zilla |
|  | taluk_name |  |
|  | total_gps | GPs in taluk |
|  | gps_source |  |

### dim_gp  (DIM)
*Grain:* one row per Gram Panchayat (the common key of all 3 modules)  
*Rows (current data):* 6,099

| Key | Column | References / note |
|---|---|---|
| PK | gp_id | G0001..G6099 |
| AK | gp_lgd_code |  |
| FK | taluk_id | dim_taluk |
| FK | zilla_id | dim_zilla (shortcut) |
|  | gp_name |  |
|  | taluk_assignment | portal / reassigned |
|  | size_class |  |
|  | performance_tier |  |

### dim_fy  (DIM)
*Grain:* one row per financial year  
*Rows (current data):* 6 (5 + FY2021-22 needed by HRMS)

| Key | Column | References / note |
|---|---|---|
| PK | fy_id | FY2223.. |
|  | fy_label | 2022-23 |
|  | start_date |  |
|  | end_date |  |
|  | data_through |  |
|  | is_current |  |

### dim_month  (DIM)
*Grain:* one row per calendar month (NEW: reconciles fiscal vs calendar month)  
*Rows (current data):* 63

| Key | Column | References / note |
|---|---|---|
| PK | month_id | YYYYMM e.g. 202204 |
| FK | fy_id | dim_fy |
|  | fy_month_no | Apr=1 .. Mar=12 |
|  | calendar_year |  |
|  | calendar_month_no | Jan=1 |
|  | month_name |  |

### dim_date  (DIM)
*Grain:* one row per calendar day  
*Rows (current data):* 1,644

| Key | Column | References / note |
|---|---|---|
| PK | date_id | the date |
| FK | month_id | dim_month |
| FK | fy_id | dim_fy |
|  | weekday |  |
|  | is_working_day |  |

### dim_report  (DIM)
*Grain:* portal report catalogue (merges Finance 3 + Revenue 4 report types)  
*Rows (current data):* 7

| Key | Column | References / note |
|---|---|---|
| PK | report_id |  |
|  | module | FIN / REV / HR |
|  | report_name |  |

## Module dimensions

### dim_scheme  (DIM)
*Grain:* one row per scheme book  
*Rows (current data):* 14 (13 + ALL)

| Key | Column | References / note |
|---|---|---|
| PK | scheme_id | S01..S13, ALL |
|  | scheme_name |  |
|  | scheme_category |  |
| FK | active_from_fy_id | dim_fy |
| FK | active_to_fy_id | dim_fy |
|  | is_rollup | NEW: 1 for ALL |

### dim_fee_type  (DIM)
*Grain:* one row per fee / tax type  
*Rows (current data):* 5

| Key | Column | References / note |
|---|---|---|
| PK | fee_type_id | F1..F5 |
|  | fee_type_name |  |

### dim_property_type  (DIM)
*Grain:* one row per property type  
*Rows (current data):* 30

| Key | Column | References / note |
|---|---|---|
| PK | property_type_id | P01..P30 |
|  | property_type_name |  |
|  | report_category |  |

### dim_staff_type  (DIM)
*Grain:* one row per staff type  
*Rows (current data):* 7

| Key | Column | References / note |
|---|---|---|
| PK | staff_type_code |  |
|  | staff_type_name |  |

### dim_designation  (DIM)
*Grain:* one row per designation (NEW surrogate key)  
*Rows (current data):* 176

| Key | Column | References / note |
|---|---|---|
| PK | designation_id | NEW |
| FK | staff_type_code | dim_staff_type |
|  | report_level | State/ZP/TP/GP |
|  | designation_name |  |

## Finance facts

### fact_fin_gp_year_closure  (FACT)
*Grain:* GP x scheme x FY: year book closed?  
*Rows (current data):* 335,226

| Key | Column | References / note |
|---|---|---|
| PK/FK | fy_id | dim_fy |
| PK/FK | gp_id | dim_gp |
| PK/FK | scheme_id | dim_scheme |
| FK | closed_on | dim_date |
|  | is_closed | measure 0/1 |

### fact_fin_gp_month_closure  (FACT)
*Grain:* GP x scheme x month: month book closed?  
*Rows (current data):* 3,656,334

| Key | Column | References / note |
|---|---|---|
| PK/FK | month_id | dim_month |
| PK/FK | gp_id | dim_gp |
| PK/FK | scheme_id | dim_scheme |
| FK | closed_on | dim_date |
|  | is_closed | measure |
|  | days_after_month_end | measure |

### fact_fin_gp_scheme_financials  (FACT)
*Grain:* GP x scheme x month: money flow  
*Rows (current data):* 3,656,334

| Key | Column | References / note |
|---|---|---|
| PK/FK | month_id | dim_month |
| PK/FK | gp_id | dim_gp |
| PK/FK | scheme_id | dim_scheme |
|  | opening_balance, receipts | measures |
|  | expenditure, closing_balance | measures |

### fact_fin_daybook_closure  (FACT)
*Grain:* Taluk x scheme x day: GPs that closed day book  
*Rows (current data):* 3,595,884

| Key | Column | References / note |
|---|---|---|
| PK/FK | date_id | dim_date |
| PK/FK | taluk_id | dim_taluk |
| PK/FK | scheme_id | dim_scheme |
|  | total_gps, gps_closed | measures |
|  | gps_pending, closure_pct | measures |

### agg_fin_taluk_year_closure  (AGG)
*Grain:* DERIVED: taluk x scheme(+ALL) x FY counts  
*Rows (current data):* 15,465

| Key | Column | References / note |
|---|---|---|
| PK/FK | fy_id | dim_fy |
| PK/FK | taluk_id | dim_taluk |
| PK/FK | scheme_id | dim_scheme |
|  | total_gps, gps_closed, closure_pct | measures |

### agg_fin_taluk_month_closure  (AGG)
*Grain:* DERIVED: taluk x scheme(+ALL) x month counts  
*Rows (current data):* 168,450

| Key | Column | References / note |
|---|---|---|
| PK/FK | month_id | dim_month |
| PK/FK | taluk_id | dim_taluk |
| PK/FK | scheme_id | dim_scheme |
|  | total_gps, gps_closed, closure_pct | measures |

### agg_fin_taluk_scheme_financials  (AGG)
*Grain:* DERIVED: taluk x scheme x month money  
*Rows (current data):* 155,598

| Key | Column | References / note |
|---|---|---|
| PK/FK | month_id | dim_month |
| PK/FK | taluk_id | dim_taluk |
| PK/FK | scheme_id | dim_scheme |
|  | receipts, expenditure, balances | measures |

### agg_fin_taluk_daybook_all  (AGG)
*Grain:* DERIVED: taluk x day, all schemes combined  
*Rows (current data):* 297,024

| Key | Column | References / note |
|---|---|---|
| PK/FK | date_id | dim_date |
| PK/FK | taluk_id | dim_taluk |
|  | total_gps, gps_closed, closure_pct | measures |

## Revenue facts

### fact_rev_dcb_register  (FACT)
*Grain:* GP x FY: Demand-Collection-Balance  
*Rows (current data):* 30,495

| Key | Column | References / note |
|---|---|---|
| PK/FK | fy_id | dim_fy |
| PK/FK | gp_id | dim_gp |
|  | arrears, year_demand, total_demand | measures |
|  | total_collection, adjustments, balance | measures |

### fact_rev_taxes_fees  (FACT)
*Grain:* GP x FY x fee type: DCB split by tax/fee  
*Rows (current data):* 132,165

| Key | Column | References / note |
|---|---|---|
| PK/FK | fy_id | dim_fy |
| PK/FK | gp_id | dim_gp |
| PK/FK | fee_type_id | dim_fee_type |
|  | arrears ... balance (6 DCB measures) | measures |

### fact_rev_demand_statistics  (FACT)
*Grain:* GP x FY x property type: DCB + property count  
*Rows (current data):* 806,855

| Key | Column | References / note |
|---|---|---|
| PK/FK | fy_id | dim_fy |
| PK/FK | gp_id | dim_gp |
| PK/FK | property_type_id | dim_property_type |
|  | number_of_properties + 6 DCB measures | measures |

### fact_rev_property_type_stats  (FACT)
*Grain:* GP x FY: property counts by category (wide)  
*Rows (current data):* 30,495

| Key | Column | References / note |
|---|---|---|
| PK/FK | fy_id | dim_fy |
| PK/FK | gp_id | dim_gp |
|  | number_of_properties + 12 category counts | measures |

### fact_rev_gp_monthly_collection  (FACT)
*Grain:* GP x month x fee type: collection amount  
*Rows (current data):* 1,427,382

| Key | Column | References / note |
|---|---|---|
| PK/FK | month_id | dim_month |
| PK/FK | gp_id | dim_gp |
| PK/FK | fee_type_id | dim_fee_type |
|  | collection_amount | measure |

## HRMS facts

### fact_hr_staff  (FACT)
*Grain:* one row per staff member (register)  
*Rows (current data):* 51,187

| Key | Column | References / note |
|---|---|---|
| PK | staff_id | KA-GPS-nnnnnn |
| FK | gp_id | dim_gp |
| FK | staff_type_code | dim_staff_type |
| FK | designation_id | dim_designation |
| FK | joining / registration / approved / exit dates | dim_date |
|  | gender, status, monthly_gross_salary_inr | attributes + measure |

### fact_hr_er_registration  (FACT)
*Grain:* GP x FY snapshot: elected-representative registration  
*Rows (current data):* 30,495

| Key | Column | References / note |
|---|---|---|
| PK/FK | fy_id | dim_fy |
| PK/FK | gp_id | dim_gp |
|  | total_seats, total_elected_members | measures |
|  | president / upadhyaksha registered | measures |

### fact_hr_eo_approval  (FACT)
*Grain:* GP x FY snapshot: staff registrations at EO  
*Rows (current data):* 30,495

| Key | Column | References / note |
|---|---|---|
| PK/FK | fy_id | dim_fy |
| PK/FK | gp_id | dim_gp |
|  | sent, approved, pending, rejected, resent | measures |

### fact_hr_salary_bills  (FACT)
*Grain:* Taluk x staff type x month: salary bill funnel (TALUK grain only)  
*Rows (current data):* 40,698

| Key | Column | References / note |
|---|---|---|
| PK/FK | month_id | dim_month |
| PK/FK | taluk_id | dim_taluk |
| PK/FK | staff_type_code | dim_staff_type |
|  | staff, main/aux bills, paid, rejected (14 measures) | measures |

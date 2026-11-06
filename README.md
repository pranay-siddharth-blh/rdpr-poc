# RDPR Karnataka POC - Synthetic Data for an NL-to-SQL Chatbot

Synthetic data that mirrors the Panchatantra 2.0 (RDPR Karnataka) portal, used to build and test a chatbot that
answers natural-language questions with SQL. Three modules share one geography:

**State > Zilla (31) > Taluk (238) > Gram Panchayat / GP (6,099)**

Period: FY 2022-23 to FY 2026-27 (data runs to 30 Sep 2026). All names and numbers are synthetic.

> Status: the warehouse is built by one staged script (`warehouse/build_warehouse.py`, 30 build checks) into `DB/rdpr_star.sqlite`, with physical `mart_*` tables for the chatbot and dashboard. The app in `ai_app/` serves the dashboard, insights and AI mode with **voice mode** (KPCL layout, RDPR colours) and passed a 318-question live stress test ([STRESS_TEST_QUESTIONS.md](STRESS_TEST_QUESTIONS.md)) and a 896-question spoken stress test, 829 correct ([VOICE_STRESS_TEST_QUESTIONS.md](VOICE_STRESS_TEST_QUESTIONS.md)). Follow-up questions ("and Hassan?", "what about 2023-24?") carry over the previous question: 892 of 892 turns correct in the follow-up stress test ([FOLLOWUP_STRESS_TEST.md](FOLLOWUP_STRESS_TEST.md)).
> Run it: `cd ai_app` then `python -m uvicorn app.main:app --port 8000`, and open http://127.0.0.1:8000/dashboard.
> For the detailed progress log, decisions and open issues see **[HANDOFF.md](HANDOFF.md)**.

## Folder map

| Folder / file | What it is | Made by |
|---|---|---|
| `Finance_Accounting/` | Finance & Accounting module: book-closure (day / month / year) and money flow. `.xlsx` for review, `csv/` full tables, `FA_Finance.sqlite` all tables + roll-up views | Supplied (not changed) |
| `Revenue/` | Revenue module: demand-collection-balance, taxes/fees, property statistics. Same three formats, `RV_Revenue.sqlite` | Supplied (not changed) |
| `HRMS/` | **Original** HRMS workbook (`GP_Synthetic_Data_2022_2026.xlsx`): staff register, ER registration, EO approval, monthly salary bills. Kept untouched for reference | Supplied (not changed) |
| `Staged/HRMS/` | **Corrected HRMS** rebuilt on the shared master (same GPs and spellings as Finance/Revenue). `HRMS_Data.xlsx`, `csv/`, `HRMS.sqlite` | Built in this project |
| `Staged/FA_Master_unchanged.xlsx` | Copy of the Finance master tables used as the reference | Copy |
| `DB/rdpr_star.sqlite` | **The warehouse**: source register, staging flags, the star schema (11 dimensions + 13 facts with CHECK constraints), 31 physical `mart_*` tables, semantic tables and the build ledger | `warehouse/build_warehouse.py` |
| `warehouse/` | The staged build (`build_warehouse.py`), the core DDL (`schema_core.sql`), the mart definitions (`mart.py`) and the metadata JSON (docs, metrics, capabilities, known issues) | Built in this project |
| `semantic/` | `semantic_layer.json` and `integrity_manifest.json` (exported by the build), `example_queries.sql` (38 reviewed examples), `knowledge_base.yaml` | Built in this project |
| `ai_app/` | The FastAPI app: dashboard, insights, AI mode with voice, Excel reports; `tests/` holds 383 tests, the stress test, the spoken stress test, the typed and spoken follow-up stress tests and the LLM eval; `voices/` the officer voice clip | Built in this project |
| `archive/` | Superseded build scripts and the old static pages (not used) | Kept for reference |
| `docs/` | `db_core_star_schema.png` (the built core layer, drawn from the real DB), plus the earlier proposal images and `DB_Design_Blueprint.md` | Built in this project |
| `scripts/` | Python scripts that produced `Staged/HRMS` and the `docs/` images (re-runnable, relative paths) | Built in this project |
| `FA_Excel_Blueprint.xlsx` | Original Finance design notes (README, sheet plan, rules) | Supplied |
| `Karnataka_Zilla_Taluk_Master.xlsx` | Zilla and taluk list (identical to the Finance/Revenue master) | Supplied |

## The shared master (the "single source of truth")

Finance and Revenue already used the **same** dimension tables (verified identical in Excel, CSV and SQLite):
`dim_zilla` (31), `dim_taluk` (238), `dim_gp` (6,099), `dim_fy` (5). HRMS now uses them too.

Naming convention used everywhere:

- Keys: `zilla_id` (Z01..), `taluk_id` (T001..), `gp_id` (G0001..), plus official codes `zilla_lgd_code`, `taluk_lgd_code`, `gp_lgd_code`
- Names in Title Case from the master (for example `Bagalkot`, not `BAGALKOTE`)
- Column names are lower-case snake_case; "district" is always called **zilla**, "Grama Panchayat" is always **gp**
- Financial year label such as `2022-23`; fiscal month number 1 = April. HRMS also keeps the calendar month (`calendar_month_no`, Jan = 1) as a separate column

## What each file format is for

- **`.xlsx`** - easy to open and review; one sheet per financial year. Excel cannot hold the multi-million-row tables, so those exist only as CSV / SQLite.
- **`csv/`** - every table, complete, one file per table. Neutral format to load into any database. Row counts match the SQLite tables exactly.
- **`.sqlite`** - one single-file database per module with all tables plus `vw_*` roll-up views (zilla and state level). Used to test queries and joins quickly. It has **no declared primary keys, foreign keys or indexes** - this is what the DB design step will add.

## Table prefixes

`dim_*` dimension (lookup) - `fin_*` Finance facts - `rev_*` Revenue facts - `hr_*` HRMS facts - `vw_*` roll-up views (SQLite only).
The star database `DB/rdpr_star.sqlite` renames the facts to `fact_fin_*`, `fact_rev_*`, `fact_hr_*` and uses `fy_id` / `month_id` keys (see `docs/DB_Design_Blueprint.md`).

## Where to go next

1. Setting up on another computer: section 2 of [HANDOFF.md](HANDOFF.md) (what to copy, install, `.env`, checks).
2. How it works: sections 5-13 (architecture, warehouse, data model, app, chatbot pipeline, guardrails, voice, API).
3. Known data issues and open items: sections 16-17; reusing this for a new project: section 18.

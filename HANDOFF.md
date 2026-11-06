# RDPR POC: Handoff

**Last updated: 5 October 2026.** This is the single current description of the project:
- what it is;
- how to set it up on another computer and run it;
- how it is built, layer by layer, and how it is tested;
- what was decided, and what is still open;
- how to reuse it to start a similar project.

It is written to stand on its own. You should not need anything outside this folder to follow it, except the model
gateway keys, which are never stored in documents.

- Folder map in brief: [README.md](README.md).
- The reference architecture this follows: [NL2SQL_LAYERED_ARCHITECTURE.md](NL2SQL_LAYERED_ARCHITECTURE.md).

> **Working rule for anyone in this project.** Two folders are **read-only references**:
> - `d:\KPCL POC` (and its copy nested at `RDPR POC/KPCL POC/`);
> - `d:\Meghalaya_voice`.
>
> They may be read at any time for ideas. Copy from them only when the project owner explicitly asks. Never edit, move,
> delete or create anything in them: no caches, logs, test output or `__pycache__`.

---

## Contents

1. [What this is, and status](#1-what-this-is-and-status)
2. [Set it up on another computer](#2-set-it-up-on-another-computer)
3. [Everyday commands](#3-everyday-commands)
4. [Folder map](#4-folder-map)
5. [Architecture, end to end](#5-architecture-end-to-end)
6. [Source data](#6-source-data)
7. [Warehouse build](#7-warehouse-build)
8. [Data model](#8-data-model)
9. [The web app: pages and front end](#9-the-web-app-pages-and-front-end)
10. [The chatbot pipeline](#10-the-chatbot-pipeline)
11. [Guardrails: everything in place](#11-guardrails-everything-in-place)
12. [Voice mode](#12-voice-mode)
13. [API](#13-api)
14. [Testing](#14-testing)
15. [Decisions on record](#15-decisions-on-record)
16. [Known data issues](#16-known-data-issues)
17. [Open items, on hold, and considered-but-not-done](#17-open-items-on-hold-and-considered-but-not-done)
18. [Reusing this for another project](#18-reusing-this-for-another-project)
19. [Change log](#19-change-log)

---

## 1. What this is, and status

This is a proof of concept for the **Rural Development & Panchayat Raj (RDPR) Department, Karnataka**. Three portal
modules of Panchatantra 2.0 are covered: **Revenue**, **Finance & Accounting** and **HRMS**. The data is synthetic.
They are rebuilt into one checked warehouse and served by one web app:
- a **dashboard** with a Karnataka map;
- **insights**;
- **AI mode**: a chatbot that answers questions in plain English with figures, charts, tables and Excel reports. It
  also has **voice mode**: speak a question, hear the answer.

The geography is **Karnataka › 31 zillas › 238 taluks › 6,099 Gram Panchayats (GPs)**. The period runs from April
2022 to September 2026; FY 2026-27 is a part year.

| Area | State |
|---|---|
| Source data | Finance & Accounting, Revenue and HRMS cross-checked. HRMS was rebuilt on the shared GP master (`Staged/HRMS/`) |
| Warehouse | One staged build, `warehouse/build_warehouse.py`, makes `DB/rdpr_star.sqlite` (4.2 GB). **30 of 30** build checks pass |
| Mart | 31 physical `mart_*` tables, including 5 pre-summed taluk tables. This is the only layer the app reads |
| Semantic layer | `semantic/semantic_layer.json`: 31 tables, 25 metrics, 38 reviewed example queries, 23 glossary terms, 10 known issues |
| Dashboard | Karnataka map with all 31 zillas (Karnataka GIS outlines; Vijayanagara drawn on its own). Revenue, Finance and HRMS module boxes. Any year or zilla loads in 4–30 ms |
| AI mode | Answers come from deterministic routes first and the model only as a last resort. Figures are never typed by the model |
| Follow-ups | "and Hassan?", "what about 2023-24?", "and the balance?" carry over the previous question, typed or spoken |
| Guardrails | Input screening, read-only database with an authorizer, checks on the model's SQL and results, a second-opinion reviewer, small talk and abuse handling, the false-premise check, and the voice guards ([§11](#11-guardrails-everything-in-place)) |
| Voice mode | Speech-to-text (qwen3-asr) in and a cloned officer voice (Qwen3-TTS) out. Every spoken figure is checked against the screen |
| Offline tests | **383 pass** |
| Live stress test | **318 / 318** client-style questions correct, on the VPN ([STRESS_TEST_QUESTIONS.md](STRESS_TEST_QUESTIONS.md)) |
| Model-path evaluation | **15 / 15** |
| Follow-up stress test | **892 / 892** turns in 161 conversations, plus 1,316 / 1,316 in two fresh random walks ([FOLLOWUP_STRESS_TEST.md](FOLLOWUP_STRESS_TEST.md)) |
| Spoken stress test | **829 / 896** through the real speech-to-text. Every miss is a mishearing, not a pipeline error ([VOICE_STRESS_TEST_QUESTIONS.md](VOICE_STRESS_TEST_QUESTIONS.md)) |
| Spoken follow-ups | **721 / 790**. All 69 misses pass when typed ([VOICE_FOLLOWUP_STRESS_TEST.md](VOICE_FOLLOWUP_STRESS_TEST.md)) |
| Browser checks (headless Edge) | Voice: 9 / 9 scenarios with a simulated microphone; voice button: 10 / 10 paths. No console or security-policy errors |

---

## 2. Set it up on another computer

### 2.1 What you need

| Need | Detail |
|---|---|
| Operating system | Windows 10 or 11 (built and tested on Windows 11). The app is plain Python and runs anywhere, but the **spoken** stress tests use Windows' Indian-English voices |
| Python | **3.11** (tested on 3.11.9) |
| Disk | About **6 GB**: the warehouse is 4.2 GB, and the sources are 1.4 GB if you want to rebuild |
| Browser | Edge or Chrome. The microphone works only on `http://127.0.0.1` / `localhost` or over HTTPS |
| Network | The **VPN** to reach the internal model gateway: the language model, speech-to-text and speech. Without it, everything deterministic still works ([§2.5](#25-what-works-without-the-vpn)) |
| Keys | The gateway URL and API keys for `ai_app/.env`. Get them from the project owner; they are never in documents or code |

### 2.2 What to copy

| Copy | Size | Why |
|---|---|---|
| `ai_app/` | 23 MB | the app, its tests and the officer voice clip. **Leave out `ai_app/.env`**: make a fresh one, because it holds keys |
| `DB/rdpr_star.sqlite` | 4.2 GB | the warehouse the app reads. Or rebuild it from the sources (about 11 minutes, [§7](#7-warehouse-build)) |
| `semantic/`, `warehouse/` | 1 MB | the semantic layer the app loads, the build, and the metadata |
| `Finance_Accounting/`, `Revenue/`, `Staged/` | 1.4 GB | only to rebuild the warehouse. `HRMS/` (the original, uncorrected HRMS) is kept for reference only |
| `*.md`, `docs/`, `scripts/`, `archive/` | small | documentation, the helper scripts, archived old pages |
| **Not** `KPCL POC/` (500 MB) | | a different project, kept here only as a read-only reference |
| **Not** `__pycache__/`, `*.sqlite-wal` / `-shm` / `-journal` | | rebuilt automatically |

All paths in the code are relative to the project folder (`ai_app/app/config.py`), so the folder can live anywhere.

### 2.3 Install

```
cd "RDPR POC/ai_app"
python -m venv .venv
.venv\Scripts\activate                      # macOS / Linux: source .venv/bin/activate
python -m pip install -r requirements.txt   # fastapi, uvicorn, httpx, pydantic(-settings), PyYAML, openpyxl, numpy, pytest
```

Only the optional tools need more:

| For | Install |
|---|---|
| Rebuilding the warehouse (`warehouse/build_warehouse.py`) and HRMS (`scripts/rebuild_hrms_on_master.py`) | `pip install pandas numpy` |
| Redrawing the map (`scripts/make_ka_zillas_map.py`) | `pip install shapely` |
| The documentation images (`scripts/make_*_image*.py`, `make_nl2sql_guide.py`) | `pip install matplotlib` |
| Browser checks (headless Edge) | `pip install playwright`, then use the installed Edge (`channel="msedge"`); no browser download is needed |
| Spoken stress tests | Windows with the OneCore voices **Microsoft Ravi** and **Microsoft Heera** (English, India): Settings › Time & language › Speech › Add voices |

### 2.4 Configure: `ai_app/.env`

Copy `ai_app/.env.example` to `ai_app/.env` and fill it in. Variable names are the setting names in upper case, with
no prefix.

| Variable | Meaning |
|---|---|
| `SQL_VERIFY_MODEL`, `SQL_VERIFY_BASE_URL`, `SQL_VERIFY_API_KEY` | the language model on the internal OpenAI-compatible gateway (the same names as the KPCL / WB POCs). Empty: no free-form questions, everything else works |
| `AI_MODEL_CA_BUNDLE_PATH` | the gateway's CA certificate. **When empty, the certificate is not verified** (see [§17](#17-open-items-on-hold-and-considered-but-not-done), item G2) |
| `ASR_MODEL` (`qwen3-asr`), `ASR_BASE_URL`, `ASR_API_KEY`, `ASR_CONTEXT_HINTS_ENABLED` | speech-to-text for voice mode |
| `TTS_ENABLED`, `TTS_MODEL`, `TTS_BASE_URL`, `TTS_API_KEY`, `TTS_TASK_TYPE`, `TTS_REF_AUDIO_PATH` (`voices/officer_serena.wav`), `TTS_STREAM_ENABLED` | speech for voice mode, cloning the officer voice clip |
| `RDPR_DB_PATH` | another warehouse file (default `DB/rdpr_star.sqlite`) |
| `RDPR_SHOW_TECHNICAL_DETAILS` | `true` shows SQL, routes, timings and `/docs`. For admins only; keep it `false` for users |
| `RDPR_QUERY_TIMEOUT_SECONDS` (60), `RDPR_MAX_ROWS` (200), `RDPR_RATE_LIMIT_PER_MINUTE` (60 per IP), `RDPR_MAX_CONCURRENT_QUESTIONS` (8), `RDPR_DB_CONNECTIONS` (4), `RDPR_REPORT_TTL_SECONDS` (3 h), `RDPR_VERIFY_ANSWERS` (true), `RDPR_PROMPT_TOKEN_BUDGET` (20,000) | limits and switches; the defaults are shown |
| `VOICE_RATE_LIMIT_PER_MINUTE` (240), `VOICE_MAX_CONCURRENT_CALLS` (4), `VOICE_COLLECT_MISHEARINGS` (false) | voice limits; mishearing collection is off unless the officers consent |

**Never copy, commit or share `.env`.** `.gitignore` excludes it.

### 2.5 What works without the VPN

The dashboard, insights, MIS reports, and the chatbot's deterministic routes all work offline:
- single figures, breakdowns and rankings;
- comparisons and overview reports;
- definitions, follow-ups and small talk;
- guardrails and false-premise corrections.

What needs the gateway:
- **free-form questions** (the model path), for example "how many GPs collected less than 20%". Offline, these get a
  polite "the language model isn't reachable" answer;
- **speech-to-text and the officer voice.** Without them the voice button offers typing instead, and answers are
  spoken in the browser's own voice.

### 2.6 Check the setup

```
cd ai_app
python -m pytest -p no:cacheprovider -q                     # expect 383 passed (about a minute)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Then open http://127.0.0.1:8000/health. It should show `"status":"ok"`, plus `llm_configured` and the voice flags as
true when `.env` is complete. Then open http://127.0.0.1:8000/dashboard, `/insights` and `/chat`.

`python keep_alive.py` (at the project root) pings `/health` every 10 seconds, for hosts that put an idle process to
sleep.

---

## 3. Everyday commands

Run all of these from `ai_app/` unless a path says otherwise.

| Task | Command |
|---|---|
| Run the app | `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` |
| Offline tests | `python -m pytest -p no:cacheprovider -q` |
| Live stress test (318 questions) | `python tests/run_stress.py --local` (in process), or `--url http://127.0.0.1:8000` with the server up |
| Model-path evaluation | `python tests/run_eval.py` |
| Follow-up stress test | server up with `RDPR_RATE_LIMIT_PER_MINUTE=100000`, then `python tests/run_followup_stress.py --url http://127.0.0.1:8000` |
| Spoken stress test (VPN, Windows voices) | `python tests/run_voice_stress.py [--failed] [--only 3,14] [--area GP]` |
| Spoken follow-ups (VPN; after the typed follow-up run) | `python tests/run_voice_followup_stress.py` |
| After editing any CSS / JS | `python scripts/stamp_assets.py` (a test checks the cache-busting stamps) |
| After editing `warehouse/metadata/*` or `semantic/example_queries.sql` | from the project root: `python warehouse/build_warehouse.py --from semantic` (about 3.5 minutes) |
| Full warehouse rebuild | from the project root: `python warehouse/build_warehouse.py` (about 11 minutes) |
| Review collected mishearings | `python tests/review_mishearings.py` |
| Redraw the map | from the project root: `python scripts/make_ka_zillas_map.py <District_Boundaries.gpkg> <Taluk_Boundaries.gpkg>` (the KGIS files, [§9.2](#92-dashboard-dashboard)) |

---

## 4. Folder map

| Path | What it is |
|---|---|
| `Finance_Accounting/`, `Revenue/` | supplied module data (xlsx for review, csv, and one `*.sqlite` each). Not changed |
| `HRMS/` | the **original** HRMS workbook, kept untouched for reference |
| `Staged/HRMS/` | HRMS **rebuilt on the shared master** (`HRMS.sqlite`, csv, xlsx). This is the HRMS the warehouse loads |
| `DB/rdpr_star.sqlite` | the warehouse: sources register, staging flags, star schema, `mart_*`, `semantic_*` and the build ledger |
| `warehouse/` | `build_warehouse.py` (the staged build), `schema_core.sql` (the core DDL), `mart.py` (mart tables), `metadata/*.json` (docs, metrics, capabilities, known issues, lineage) |
| `semantic/` | `semantic_layer.json` and `integrity_manifest.json` (exported by the build), `example_queries.sql` (38 reviewed queries), `knowledge_base.yaml` (RDPR facts), `build_semantic_layer.py` |
| `ai_app/app/` | the FastAPI app ([§10](#10-the-chatbot-pipeline) for each module) |
| `ai_app/app/static/` | pages, scripts and styles. `vendor/` holds Chart.js, the fonts and the speech-detection files; `voice/` is voice mode |
| `ai_app/tests/` | offline tests, the stress, follow-up and spoken test banks and runners, and their reports |
| `ai_app/voices/officer_serena.wav` | the reference clip the officer voice is cloned from |
| `scripts/` | HRMS rebuild, map builder, documentation image builders |
| `docs/` | the core star schema image, the DB design blueprint, sample and test question lists |
| `archive/` | superseded build scripts and old pages, kept but unused |
| `*_TEST*.md` (root) | readable results of each stress test |
| `KPCL POC/` | another project, **read-only reference**, not part of RDPR |

---

## 5. Architecture, end to end

```
Finance_Accounting/FA_Finance.sqlite ─┐
Revenue/RV_Revenue.sqlite ────────────┼─► warehouse/build_warehouse.py ─► DB/rdpr_star.sqlite ─► semantic/semantic_layer.json
Staged/HRMS/HRMS.sqlite ──────────────┘   sources → staging → core →      core star + mart_* +     (+ integrity_manifest.json)
                                          reconcile → mart → semantic →   semantic_* + ledger_*              │
                                          ledger → checks → export                                           ▼
                                                                     ai_app (FastAPI): /dashboard  /insights  /chat (+ voice)
                                                                     read-only connection pool, mart_* only, caches by DB version
```

**Rules that hold everywhere:**
1. The app opens the database **read-only** and may read **only `mart_*` tables**. Model-written SQL is held to this
   by a database authorizer, not just by the prompt.
2. **Every ratio is SUM over SUM**: a place's own total over its own base, never an average of averages.
3. **Positions are never added across time.** Arrears, total demand, balance, closing balance and HR snapshots are
   added across places within one year only. Flows (collection, receipts, expenditure) can be added over time.
4. **The model never types a number the user sees.** It writes SQL and an answer template; code fills the figures
   from the result rows.
5. **Deterministic routes come first.** The model is the last resort, and everything it writes is checked twice
   (rules, then a reviewer with a code veto).

---

## 6. Source data

Three modules share one geography. **Finance and Revenue agreed with each other**: their masters were identical in
xlsx, csv and sqlite. **HRMS did not**:
- 5,873 GPs against 6,099;
- GP codes reused for different villages (0% name match);
- six zilla spellings (BAGALKOTE, DHARWAR ...), upper case throughout;
- calendar months, and names instead of ids.

`scripts/rebuild_hrms_on_master.py` rebuilt HRMS on the shared master into `Staged/HRMS/`, leaving the originals
untouched:
- GPs were matched per taluk (29 by name, 4,867 by order).
- 1,203 master GPs with no HRMS counterpart got staff, elected-member and EO profiles copied from a GP of the same
  taluk.
- 977 HRMS GPs not in the master were dropped.
- Taluk salary summaries were scaled to the new totals, so the funnel rules still hold.
- `hr_gp_crosswalk` records every mapping. Staff went from 49,503 to 51,187.

---

## 7. Warehouse build

```
python warehouse/build_warehouse.py                  # full build, about 11 minutes
python warehouse/build_warehouse.py --from semantic  # metadata / examples changed: works in place, about 3.5 minutes
python warehouse/build_warehouse.py --from mart      # mart definitions changed
python warehouse/build_warehouse.py --only checks    # one stage
```

A full build writes `DB/rdpr_star.building.sqlite` and publishes it to `DB/rdpr_star.sqlite` only if **every** check
passes. The previous file is kept as `rdpr_star.previous.sqlite`; none exists now, and the next full build makes one.
Sources are attached read-only and never written.

| Stage | What it does |
|---|---|
| sources | `src_file`: the 19 inputs with SHA-256, loaded or not and why. `src_table`: row counts |
| staging | `stg_quality`, `stg_flagged_row`: 7 rules that **describe, never delete**. Scheme-ledger ±1 rupee rounding 10,066 rows; demand statistics not tied to the DCB register 30,495; property counts not tied 10,185; ALL-scheme roll-up above the lowest scheme 850; staff never approved 694; reassigned GPs 996; staff dates with a time part 51,187 |
| core | `schema_core.sql`: 11 dimensions and 13 facts with keys, foreign keys and a CHECK for every business rule (DCB total = arrears + demand; the balance identity; closed + pending = total; the salary funnel narrows; paid + rejected ≤ staff; elected members ≤ seats; staff domains; exited ⇔ exit date). `ledger_column` records where all 320 source columns landed |
| reconcile | ties Revenue demand statistics and property counts to the DCB register per GP and FY (`ledger_reconcile_log`, `ledger_reconciliation`) |
| mart | `warehouse/mart.py`: 31 physical, indexed tables ([§8](#8-data-model)) |
| semantic | `warehouse/metadata/*.json` is loaded and validated against the mart. It fails on an undocumented column, a metric over a missing table, or a "loaded" topic with no rows |
| ledger | `ledger_issue` (known issues with measured counts), `metadata/_lineage.json`, `ledger_build` (stage timings) |
| checks | `ledger_build_check`: 30 named invariants. Integrity and FK checks; mart = core row counts; pre-summed tables = GP facts; monthly = DCB collection; every mart column documented; and **golden figures**: Mysuru FY 2024-25 demand ₹457.57 cr and collection ₹124.30 cr; Karnataka FY 2024-25 collection ₹1,905.41 cr; 393 GPs with every book closed; Revenue FY 2022-23 monthly ₹1,425.43 cr |
| export | `semantic/build_semantic_layer.py` writes `semantic_layer.json` and `integrity_manifest.json`. Every example query must return rows |

**After editing anything in `warehouse/metadata/` or `semantic/example_queries.sql`, run `--from semantic`.**
Otherwise `tests/test_integrity.py` fails: it re-hashes the DB, the layer and the examples against the manifest.

---

## 8. Data model

**Core star.**
- Dimensions: `dim_zilla`, `dim_taluk`, `dim_gp`, `dim_fy` (FY 2021-22 to 2026-27; 2021-22 is used only for HRMS
  January–March 2022), `dim_month`, `dim_date`, `dim_scheme`, `dim_fee_type`, `dim_property_type`, `dim_staff_type`
  and `dim_designation`.
- Facts:
  - `fact_fin_*`: day-book closure, GP month closure, GP scheme financials, GP year closure;
  - `fact_rev_*`: DCB register, demand statistics, monthly collection, property-type statistics, taxes and fees;
  - `fact_hr_*`: staff, EO approval, elected-member registration, salary bills.

About 11 million fact rows.

**Mart: the only layer the app reads, 31 tables.**

| Group | Tables |
|---|---|
| Dimensions | `mart_dim_zilla`, `_taluk`, `_gp`, `_fy`, `_month`, `_scheme`, `_fee_type`, `_property_type`, `_staff_type` |
| GP / taluk facts | `mart_fact_gp_dcb`, `_gp_fee_type`, `_gp_monthly_collection`, `_gp_demand_by_property_type`, `_gp_property_counts`, `_gp_year_closure`, `_gp_month_closure`, `_gp_scheme_financials`, `_gp_eo_approval`, `_gp_er_registration`, `mart_fact_taluk_daybook_closure`, `_taluk_salary_bills`, `_taluk_staff` (counts only; no person data) |
| Summaries | `mart_summary_gp_year`, `_taluk_year`, `_zilla_year`, `_state_year` |
| Pre-summed taluk tables | `mart_agg_taluk_fy`, `mart_agg_taluk_month`, `mart_agg_taluk_fee_type_fy`, `mart_agg_taluk_property_fy`, `mart_agg_taluk_scheme_fy` |

Zilla and state figures are sums over taluk rows, so the dashboard, insights and reports never scan GP tables. Salary
bills exist only at taluk level.

**Semantic metadata** (`warehouse/metadata/`):
- `semantic_docs.json`: table and column docs, and the query rules.
- `metric_registry.json`: 25 metrics, each with synonyms (the words people use) and SUM/SUM expressions per period
  kind, revenue head and property category.
- `capability_manifest.json`: what is and is not loaded, for honest "not in this data" answers (budgets, audit,
  MGNREGA, housing / PMAY, demographics, attendance ...).
- `known_issues.json`: [§16](#16-known-data-issues).

---

## 9. The web app: pages and front end

### 9.1 Front-end rules
- All three pages copy the KPCL layout, recoloured to the RDPR wine: `#7b1e34`, deep `#3f0b19`, mid `#962b45`, soft
  `#f8edef`, glow `#b8405c`; gold `#b8892b` / `#e9b949`.
- Labels are in English and Kannada.
- Chart.js 4.5.1, the Noto fonts and the speech-detection files are served from `/static/vendor/`, so the pages work
  without internet.
- The **content-security policy** allows only this server: no inline scripts, no `eval` (only `'wasm-unsafe-eval'`, for
  speech detection).
- After editing any CSS or JS, run `python ai_app/scripts/stamp_assets.py`.

### 9.2 Dashboard (`/dashboard`)

**Module boxes (Revenue, Finance, HRMS).** Clicking one turns the whole page into that module. The choice is kept in
the URL (`?module=finance`), so it survives a reload and the back button.

**The Karnataka map (first card).**
- It draws all 31 zillas, lightly shaded by the module's headline ratio (collection %, scheme books closed %, or seats
  filled %).
- Hovering shows a tooltip and the side panel (value, rank of 31, taluks, GPs, the state figure). Clicking opens that
  zilla.
- The outlines are the **Karnataka GIS (KGIS, kgis.ksrsac.in)** boundaries, from the public-domain copy at
  github.com/samashti/KGIS, simplified for display. `scripts/make_ka_zillas_map.py` builds `ka_zillas.json`.
- KGIS still holds Ballari undivided. So **Vijayanagara** (formed 2021: Hadagali, Hagaribommanahalli, Hosapete,
  Kudligi, Kotturu, Harapanahalli) and the new Ballari are the unions of their KGIS taluks.
- The old 2011 outlines are in `archive/legacy_static/ka_zillas_2011.json`.

**Headline and KPI cards.** A headline card with a five-year sparkline, then five KPI cards for the module.

**Panels per module:**

| Panel | All | Revenue | Finance | HRMS |
|---|---|---|---|---|
| Monthly chart (with the previous FY) | toggle | collection | receipts vs expenditure | salaries paid vs payroll |
| Donut | revenue heads | revenue heads | receipts by scheme | staff by designation |
| Zilla / taluk table (sortable, division filter) | collection | collection | books closed %, receipts, spent | staff, EO approvals, seats filled % |
| GPs collecting the least | ✓ | ✓ | | |
| Salary bills (paid against a 95% mark, bank rejections) | ✓ | | | ✓ |
| Scheme books closed (the **bookshelf**) | ✓ | | ✓ (wide) | |
| Month-end books closed | | | ✓ | |
| Staff registrations at the EO | | | | ✓ |
| Where dues are outstanding | ✓ | ✓ | | |
| Five-year view | collection | collection | receipts + books closed % | approvals + seats filled % |

**Speed.** Any year or zilla loads in 0.01–0.03 s cold and about 4 ms warm. At startup the app pre-loads every year
statewide and every zilla for the default year. The page caches and prefetches, lets only the newest request draw,
and updates charts in place.

**MIS report.** View or download an Excel report of the current selection, or the complete report. It is refused with
409 if a figure check inside the workbook fails.

### 9.3 Insights (`/insights`)
- 18 cards in Revenue, Finance & Accounting, HRMS and Watch-list groups, built from the dashboard's own figures.
- A zilla index.

### 9.4 AI mode (`/chat`)
- 15 suggested questions; answers stream in.
- Bar, line and doughnut charts. A doughnut is offered only for 12 or fewer non-negative, non-ratio values.
- A data table with CSV download.
- **View report / Download report**: Excel with Report, Data (with a native chart) and Notes sheets.
- **"Taking this as: …"** above an answer that was a follow-up.
- **New conversation** clears the follow-up context.
- The round **voice button** beside **Ask** starts voice mode ([§12](#12-voice-mode)). Every press opens the full voice
  panel.
- `/gp` and `/compare` redirect to `/dashboard`.

---

## 10. The chatbot pipeline

`ai_app/app/pipeline.py` is the single request path shared by the page (SSE), the JSON endpoint and every test
runner. Steps L0–L4 are deterministic, and L4 includes the reviewed reports, breakdowns and single-figure lookups. The
model is called only from L5 onwards.

| Layer | Module | What it does |
|---|---|---|
| (before) follow-up | `followup.py` | rewrites "and Hassan?" into the whole question, using the previous question the page sends ([§10.1](#101-follow-up-questions)) |
| L0 small talk | `small_talk.py` | the **whole** message is a greeting, "how are you", thanks, goodbye, "ok" or abuse: a friendly fixed reply. Abuse gets the same calm greeting, is never rebuked or echoed, and keeps no question text. **Abusive words inside a real question are removed** before any layer sees it |
| L1 screen | `guardrails.py` | empty or too long (500 characters), pasted SQL or code, prompt injection, requests to change data, personal data, office holders, questions about the system, off-topic: a fixed reviewed refusal |
| L2 identity, verified | `verified_queries.py` | "who are you" / help; the 38 reviewed example queries |
| L2 glossary, knowledge | `knowledge.py`, `semantic/knowledge_base.yaml` | definitions; RDPR / Panchatantra facts (never names office holders) |
| L2 capability | `capability.py` | data that is not loaded: an honest note |
| L3 router | `semantic_layer.py` | finds zillas, taluks and GPs (with the spellings people use: Mysore, Belgaum, Gulbarga ...), periods (FY, month, calendar year, relative), metrics, heads and schemes, and intents (ranking, comparison, breakdown, trend, **filter**) |
| L4 reports | `reports.py` | overview, needs attention, compare places, scorecard, book-closure / salary / EO-backlog situations, one place over two years, one place against the state, one place over several months |
| L4 breakdowns | `breakdown.py` | one measure by month, quarter, year, zilla, taluk, revenue head, property category, scheme, staff type or designation; top / bottom N; "list the zillas / taluks / GPs" |
| L4 metric lookup | `metric_lookup.py` | one metric × one place × one period, from the registry; calendar years and part-year notes |
| L5–L11 model path | `prompts.py`, `llm.py`, `sql_safety.py`, `db.py`, `answer.py`, `review.py` | a pruned schema prompt; **one** model call returns SQL plus an answer template; the SQL guard; read-only execution; result guards; one repair round; an independent reviewer with a deterministic veto. An answer rejected twice is withheld |
| L12 premise | `premise.py` | a figure the question **states as fact** is recomputed for its own measure, place and period. If the data clearly contradicts it, the answer opens with the correction ([§10.2](#102-false-premises)) |
| writer | `answer.py` | **bold headline with the point**, one short note, then the chart and table. Units ("in lakh / crore / rupees") are converted by code |

Questions with a condition on each place ("how many GPs collected less than 20%") always take the SQL path, never a
total or ranking.

### 10.1 Follow-up questions

The page sends the last question it answered **from the data** as `previous`. A short message made only of places,
periods, measures and heads plus linking words is rewritten into the whole question by putting its parts into the
previous question's slots. Examples: "and Hassan?", "what about 2023-24?", "same for Badami taluk", "and the balance?",
"and mobile tower tax?", "and for Karnataka?". That whole question then goes through **every** layer above, so all the
guards see the full text. No model call is involved.

**Rules:**
- **Without a cue word** ("and", "what about", "same for" ...), a fragment must name no measure, so a short complete
  question is never bent onto the last one.
- **A list of places gains the new one.** "Compare Mysuru and Mandya", then "and Hassan?", compares all three.
- **A GP in a taluk is replaced whole.**
- **After a ranking of places of one kind** ("Top 5 zillas", "Which taluk in Hassan zilla…"), a place of that kind asks
  for that place's own figure ("and Kolar?" gives Kolar's collection). A place of another kind keeps the ranking
  ("and Mandya?" gives the taluks of Mandya).
- **"Current year demand" is a measure**, not the current year.
- **A previous measure named in two pieces** ("How many **staff** registrations were pending **at the EO**") is
  replaced by asking the new measure plainly, for the same place and period.
- **An unknown place is still asked** ("and Atlantis zilla?"), so the answer says it is not in the data.
- **What becomes context.** The server marks an answer `context: true` only when it came from the data and names a
  place, period, measure or head. A definition, a refusal, small talk, or "which taluk is lowest there?" is not
  context.
- **A `previous` longer than 1,000 characters is ignored**, not an error.
- **New conversation** clears the context.

### 10.2 False premises

**Picked up:** a figure stated with a unit.
- rupees (₹, Rs, rupees, crore, lakh);
- percent;
- a count of things ("6,000 GPs", "1.6 crore properties").

**Not premises:**
- thresholds and conditions ("more than 20%", "20% or less", "below 27%");
- list sizes ("top 5", "which 5 zillas");
- years, months and dates;
- ordinals ("15th Finance Commission");
- the percentages in scheme names ("SC/ST Funds 25%");
- bare numbers.

**How it checks:**
- The measure named next to the figure, with a matching unit, is recomputed through the **reviewed single-figure
  lookup**. It is not compared with the answer, which may be about something else.
- A revenue head counts only if it is in the same clause as the figure.
- **Rounding.** Round figures agree within their precision, but at most 5% off (10% after "about"). So "about 6,000
  GPs" matches 6,099, while "₹500 crore" does not match ₹124.30 crore.

**Output:** `**The question says ₹500 crore, but the data shows ₹124.30 crore.**`, then the data sentence. The
question's own answer follows. It is spoken first too. When unsure, nothing is said (precision over recall).

---

## 11. Guardrails: everything in place

| Area | Guard | Where |
|---|---|---|
| **Server** | security headers (no sniffing, no framing, no referrer, COOP), a strict content-security policy, microphone for this site only | `protection.py` |
| | request-size cap (16 KB; 10 MB only for a voice recording); per-IP rate limits (questions and reports 60 a minute; voice calls 240 a minute) | `protection.py`, `config.py` |
| | at most 8 questions answered at once, a 20-second queue, then a polite "busy" | `main.py` |
| | error messages never show internals; `/docs` and technical details hidden unless `RDPR_SHOW_TECHNICAL_DETAILS=true` | `main.py` |
| | answer-report links are random (`secrets.token_urlsafe`), kept 3 h and tied to the DB version; Excel cells are written as text, never formulas | `answer_report.py`, `mis_report.py` |
| **Input** | small talk and abuse (L0); empty, too long, code, injection, data changes, personal data, office holders, the system itself, off-topic (L1); unknown place names; years outside the data | `small_talk.py`, `guardrails.py`, `semantic_layer.py` |
| **Database** | read-only file (`mode=ro`) plus `query_only`; for model SQL an **authorizer** that allows only SELECT and only `mart_*` tables (person-level staff data can never be read) and denies file / extension functions; a time limit; a row cap | `db.py` |
| **Model SQL** | one SELECT / WITH, no write or admin words, no placeholders; place names must exist; **grain guards** (no averaging of ratios; no adding positions across years or months; no joining facts of different grain without pre-aggregating); KPI columns must use their formula; NULLs sorted last | `sql_safety.py` |
| **Results** | impossible values (a percentage over 100, a negative count); a count larger than the places in scope; an answer about the wrong subject; a false "not in the data" claim | `guardrails.py` |
| **Answer** | the model never types figures; internal names and jargon are scrubbed; no sources or web addresses; a second-opinion reviewer (one error category, with a **code veto** that overrules claims it can disprove); one repair round; twice rejected means withheld | `answer.py`, `guardrails.py`, `review.py`, `pipeline.py` |
| | false-premise correction ([§10.2](#102-false-premises)) | `premise.py` |
| **Follow-ups** | the rewritten whole question passes every guard; a hostile `previous` (injection, personal data, code) is refused like any question; an over-long `previous` is ignored | `followup.py`, `main.py` |
| **Voice** | [§12.3](#123-voice-guardrails) | `voice_guard.py`, `spoken.py` |

---

## 12. Voice mode

Voice mode was ported from the Meghalaya voice agent, as integrated into the KPCL voice instance: the same flow and
the same speech-detection files. It is re-themed in wine and re-tuned for zilla, taluk and GP names. The round button
beside **Ask** starts it, and the browser asks once for the microphone. **Every press of the button opens the full
panel** (the orb). The chevron docks it under the chat to read the full answer, and the voice button brings the panel
back.

### 12.1 One turn
1. Browser speech detection (Silero VAD, vendored with checksums, with a loudness fallback).
2. `POST /api/voice/transcribe`: 16 kHz WAV to qwen3-asr, with a terms-only context.
3. **Transcript clean-up** ([§12.4](#124-listening-the-transcript-clean-up)).
4. "I heard: …" for 2 seconds, with **That's not what I said** / **Ask now**. If the clean-up was unsure, a **Did you
   mean …?** choice instead.
5. A short filler ("Let me check that.").
6. The same `/api/ask` as typing, with `mode: "voice"`, so the answer, chart, table and report land in the chat exactly
   as for a typed question.
7. The server sends a `spoken` event **before** the text, and each sentence is streamed as 24 kHz audio from
   `/api/voice/speak/stream`.
8. Listening again. The voice starts about 0.3 seconds after the question is asked.

### 12.2 What is said
`spoken.py` builds this; there is no model call.
- **Content:** the bold headline, plus at most one supporting sentence that adds a new figure. Lists are cut to three,
  and screen-only notes are not read. Long answers end "The full details, and the report, are on your screen."
- **Small talk** has its own short spoken lines.
- **Rupees** are said as "124.3 crore rupees", and big counts as "about 1.63 crore".
- **FY 2024-25** is said as "financial year twenty twenty-four, twenty-five". GP, EO and DCB are said letter by letter.
- **Premise corrections** are said first.

### 12.3 Voice guardrails

| Guard | What it does |
|---|---|
| place and period read-back | "For Mysuru zilla, FY 2024-25: …" unless the answer already says both, so a misheard place is caught by ear |
| figures = screen figures | every spoken number must be a rounding of a number on screen, with its unit. Otherwise "The figures are on your screen." |
| model answers | a free-form answer is spoken only after the second-opinion check passed |
| ask again, not refuse | a misheard name or an off-topic sentence gets "I heard: … Could you say the name again?" |
| noise, fragments, echo | less than 0.35 s of voiced audio is never sent (needs numpy). One-word fragments, the prompt read back by the model, and the assistant's own reply heard through the speakers are dropped. A real follow-up ("and the balance?") is kept |
| repeats, language, length | the same question twice within 4 seconds is answered once; other scripts are refused politely; at most 30 seconds or 300 characters |
| microphone | off when the tab is hidden or after 3 minutes idle; a **Microphone on / off** indicator; barge-in ducks the reply |
| fallbacks | speech-to-text down: "Please type your question instead", with a type box. Speech output down: the browser's own voice |
| security | the CSP adds only `'wasm-unsafe-eval'`; `microphone=(self)`; voice calls have their own rate budget |

### 12.4 Listening: the transcript clean-up
`spoken.clean_transcript_ex` does the following:
- **Spoken years** become FY labels ("F Y twenty twenty four twenty five", "2023 to 2024", and the misheard "2020 to
  2023"). Spelled letters ("G P s") become words. "zila / jilla", "talook", "Babuji Seva", "Panchayat Tantra",
  "areas" (for arrears), "den" (for then) and "An" (for and) are fixed.
- **Names the model runs together are split**: "Masurujilla" → Mysuru zilla, "Neludigp" → Nelludi GP, "Antum guru"
  → and Tumakuru.
- **Names are matched against the data's own names**, scored on sound and spelling together. Each name is compared
  only with names of the kind its anchor word says ("… zilla", "… taluk", "… GP"), across up to three words.
- **A bare name in a follow-up** ("And Mondia.") is matched against both zillas and taluks.
- **A GP said with its taluk** ("Kaniyuru GP in Beltangadi taluk") is matched only against that taluk's GPs.
- **Close, loose, or exact.** A close match is used. A loose one, or one with a near rival, is asked about ("Did you
  mean Davanagere zilla, or Dharwad zilla?"). Ordinary words and correct names are never changed; this is tested over
  all 318 stress-bank questions.
- **Reviewed mishearings** can be added to `app/voice_lexicon.json`, which is empty today. Collection is off unless
  `VOICE_COLLECT_MISHEARINGS=true`.

**Why the speech-to-text context lists no place names.** With the 31 zillas in its context, qwen3-asr snapped what it
heard to a *wrong listed* name (Belagavi → "Bagalkot"). Without them, it writes what it hears and the clean-up finds
the name, or asks. This one change took the spoken test from 727 to 820 of 896.

---

## 13. API

| Endpoint | Purpose |
|---|---|
| `GET /health` | liveness, data period, gateway and voice configured |
| `GET /api/options` | years, zillas, defaults |
| `GET /api/dashboard?fy=&zilla=` | the dashboard payload |
| `GET /api/insights?fy=` | insight cards |
| `GET /api/mis-report?fy=&zilla=&kind=current\|all&module=` and `/view` | the Excel MIS report and its preview |
| `POST /api/ask` (SSE) and `POST /api/ask_once` (JSON) | the chatbot. Body: `{question, mode: "text"\|"voice", previous}`. Reply: `answer`, `answerable`, `chart`, `table`, `rows`, `notes`, `report_id`, `asked_as` (a follow-up's whole question), `context` (may be sent as `previous`), `spoken_answer` (voice). SSE order: `followup` → `status` … → `spoken` → `answer_chunk` … → `chart` → `table` → `done` |
| `GET /api/answer-report/{id}` and `/view` | the Excel report of one answer |
| `GET /api/map`, `/api/alerts`, `/api/gp/search`, `/api/gp/{id}`, `/api/compare` | older JSON endpoints, still served but unused by the pages |
| `GET /api/voice/config`, `/api/voice/health` | what voice can do; speech in / out reachability |
| `POST /api/voice/transcribe?session_id=&expect=` | WAV in → `{text, heard, confirm, rejected, message}` |
| `POST /api/voice/speak` and `/speak/stream` | WAV, or 24 kHz PCM streamed; 503 with `spoken_text` so the browser can say it itself |
| `GET /api/voice/filler` | a short "looking it up" phrase |

---

## 14. Testing

### 14.1 Suites

| Suite | Command (in `ai_app`) | Result |
|---|---|---|
| Offline tests | `python -m pytest -p no:cacheprovider -q` | **383 passed**: voice 145, small talk and false premises 52, follow-ups and their spoken clean-up 52, DB and SQL guards 33, warehouse / routes / map 24, reports 22, answers 14, insights 13, semantic and router 11, model path with a scripted model 10, dashboard and API 4, integrity 3 |
| Live stress test | `python tests/run_stress.py --local` | **318 / 318** (VPN) |
| Model-path evaluation | `python tests/run_eval.py` | **15 / 15** |
| Follow-up stress test | `python tests/run_followup_stress.py --url …` (server up) | **892 / 892** turns, 161 / 161 conversations; fresh walks `FOLLOWUP_SEED=1` / `2` with `--area Random`: 660 / 660 and 656 / 656 |
| Spoken stress test | `python tests/run_voice_stress.py` (VPN, Windows voices) | **829 / 896** |
| Spoken follow-ups | `python tests/run_voice_followup_stress.py` (VPN) | **721 / 790** |
| Browser | headless Edge with Playwright and a simulated microphone (`--use-fake-ui-for-media-stream --use-fake-device-for-media-stream`). The scripts were one-off and are not kept in the project; recreate them from these results if needed | voice 9 / 9 scenarios, voice button 10 / 10 paths, map and chat checks; no console or CSP errors |

Offline tests need the warehouse but not the gateway; the model is replaced by a scripted one. The stress and
follow-up runs use the real gateway for the questions that need the model.

### 14.2 How answers are checked
- **Expected figures are recomputed independently.** Every expected figure comes from the GP-level `fact_*` core
  tables, by SQL written separately from the chatbot. It never comes from the `mart_agg_*` tables the chatbot reads.
  A figure must appear in the answer, at any reasonable rounding, in rupees, lakh or crore.
- **The stress bank** (`tests/stress_bank.py`, 318 questions) covers:
  - every zilla, plus a taluk and a GP from each zilla;
  - every FY and module;
  - breakdowns and charts, comparisons and unit conversions;
  - spellings and time edge cases;
  - 20 client-style broad questions;
  - definitions, capability limits, and 38 guardrail cases.
- **The follow-up bank** (`tests/followup_bank.py`, 161 conversations, 892 turns) has two parts:
  - **a seeded random walk:** 120 conversations of 4–7 turns, each changing the place, period, measure, head or two at
    once, in a dozen phrasings;
  - **41 hand-written conversations:** every zilla, every taluk and GP, levels, rankings, comparisons, heads, schemes,
    whole questions that must not be rewritten, definitions, guardrails, unknown places, out-of-range years, a hostile
    or over-long `previous`, voice mode and the SSE stream.

  The runner keeps context exactly as the page does.
- **Spoken tests** speak each question in two Indian-English voices:
  - **Ravi** says "F Y twenty twenty four twenty five", "G P";
  - **Heera** says "financial year twenty twenty four to twenty twenty five", "gram panchayat".

  Each spoken question then goes through the real speech-to-text. A "Did you mean" is answered with the option the
  speaker meant. **Every miss is re-asked as typed text**, which separates hearing errors from answering errors; all
  current misses are hearing errors.
- **The integrity test** re-hashes the DB, the semantic layer and the examples, which proves the app never changed what
  it reads.

### 14.3 Rules
- Run the offline tests after any change.
- Run the stress test after changing routing, metrics or the writer.
- Run the follow-up test after changing `followup.py`, `semantic_layer.py` or `small_talk.py`.
- Run the spoken tests after changing `spoken.py` or `voice_guard.py`. Compare against the previous report: the total
  can hide a question that newly fails.
- A test runner overwrites its report and `*.md` page. A run made off the VPN makes the model-path questions fail, so
  re-run on the VPN before relying on the numbers.

---

## 15. Decisions on record

1. **SQLite for the POC.** The sources are SQLite; the DDL is standard and ports to PostgreSQL.
2. **The mart is physical tables, not views**, with pre-summed taluk tables. Zilla and state figures are sums over
   taluks.
3. **The app reads only `mart_*`**, through a read-only connection with an authorizer. Nothing person-level is
   exposed: staff names, dates of birth and individual salaries never leave the core table.
4. **Finance "ALL schemes" roll-up rows are not loaded**, because they were inconsistent. `dim_scheme` keeps an `ALL`
   row flagged `is_rollup`.
5. **Revenue demand statistics and property counts were tied to the DCB register** in the build (KI-10). The data
   flags stay in staging.
6. **Salary bills stay at taluk level** (KI-04).
7. **The map uses the KGIS outlines.** Vijayanagara and Ballari are built from their KGIS taluks, not drawn with an
   invented boundary.
8. **Old pages, scripts and build predecessors are archived** (`archive/`), not deleted. The exceptions are the old
   pre-warehouse database and the unused `semantic/sources/`, which were deleted on 5 October.
9. **Voice answers are built from the verified answer by code**, not re-worded by a model. There is no second round
   trip, and no new figure can appear in speech.
10. **The speech-to-text context carries the subject and its terms, never the place names.**
11. **Follow-ups are rewritten into whole questions by code** from the page's previous question. There is no
    server-side session and no model call, so every guard sees the full question and the officer sees what was
    answered.
12. **Small talk and abuse get only friendly, reviewed replies.** Abuse is never echoed or rebuked. A rude but real
    question is answered normally, with its abusive words removed before any layer sees it.
13. **A stated figure is checked against the data's own figure for that measure**, not against the answer. When
    unsure, nothing is said.
14. **The voice button always opens the full voice panel.** Docking is only for reading during the current session.

---

## 16. Known data issues

These are shown to users as caveats; the source is `warehouse/metadata/known_issues.json`.

| Id | Issue | Status |
|---|---|---|
| KI-01 | Synthetic proof-of-concept data, not official records | accepted |
| KI-02 | FY 2026-27 covers April to September 2026; year-end book closure has not happened | accepted |
| KI-03 | Day-book closure (daily, taluk) and month-end closure (GP) can disagree | accepted |
| KI-04 | Salary bills are held at taluk level only | accepted |
| KI-05 | Salary-bill months start January 2022 (FY 2021-22); Finance and Revenue start April 2022 | accepted |
| KI-06 | 996 GPs sit in a different taluk from the one their LGD code shows (taluks reorganised) | accepted |
| KI-07 | Some GP staff profiles were copied from a neighbouring GP of the same taluk (HRMS rebuild) | accepted |
| KI-08 | 694 registered staff are "Not Active" (rejected by, or pending at, the EO) and not counted as active | accepted |
| KI-09 | Not every GP keeps every scheme account (Bapuji Seva Kendra in 3,656 GPs), so scheme-wise GP counts differ | accepted |
| KI-10 | Property-type figures were rescaled at build time to add up to the DCB register | fixed |

Cosmetic issues also noted:
- GP names mix "K.Junipeth" and "K. Gollahalli" punctuation;
- the generator-only columns `size_class` and `performance_tier` remain in `dim_gp`.

---

## 17. Open items, on hold, and considered-but-not-done

**On hold (by the owner's decision):**
- **Kannada answers.** Labels are translated, but zilla names, chart text and chatbot answers are English.
- **Real officers' recordings.** With consent, they will show which names need reviewed entries in
  `app/voice_lexicon.json`.

**Known limits:**
- **Pronouns aren't resolved in follow-ups.** "Which taluk is lowest **there**?" is answered as asked.
- **A count used as a filter** ("With 1 crore properties in Karnataka, what is the demand?") can make the model refuse.
  A refusal has no figure to correct, so the premise check stays silent.
- **The "I heard" window is deliberate.** It lasts 2 seconds, so a misheard place is caught before it is answered;
  "Ask now" skips it.

**Guardrails considered on 5 October and not implemented (the owner chose C1 and B1 only).** They are kept here so a
later phase can pick them up:

| Code | Guardrail | Why it was proposed |
|---|---|---|
| G1 | the speech endpoint should speak only text the server produced | `/api/voice/speak` reads out any text up to 2,000 characters in the cloned officer voice |
| G2 | always verify the gateway's TLS certificate | with no `AI_MODEL_CA_BUNDLE_PATH`, verification is off |
| G3 | normalise Unicode (zero-width, full-width, bidirectional characters) before screening | such variants of "ignore previous instructions" are not classed as injection (they are refused only by another rule) |
| G4 | trusted-proxy client IP | behind a proxy, every user shares one IP for rate limiting |
| A1–A4 | login; roles and place scope (a zilla officer sees only that zilla); an audit trail; admin / metrics gate | no authentication today; Meghalaya has all four (`auth.py`, `security.py`, `deps.py`, `conversation_store.py`) |
| C2 | ask instead of assuming for risky defaults | today a missing year or place is filled in and disclosed |
| C3 | split or refuse compound questions | "Mysuru collection? Also tell me a joke" is not refused |
| C4 | expire the follow-up context after idle time | the context lives in the page until New conversation |
| P1 | scan result rows for personal data before showing, speaking or exporting | defence in depth on top of the mart-only authorizer |
| P2 | log files with rotation and retention, and no secrets | logging goes to the console only |
| B2–B6 | request IDs on errors; HSTS and CORS for production; a daily per-user quota; removing the unused old endpoints; logging prompt sizes | Meghalaya has B2, B3 and B6 |

---

## 18. Reusing this for another project

This POC is the third in a line: WB, KPCL, then RDPR. Most of it is generic.

### 18.1 Generic and reusable as is
- **The staged warehouse pattern** (`build_warehouse.py`):
  - **stages:** sources (hashed) → staging (flags; never delete) → core (keys and CHECK constraints for business
    rules) → reconcile → physical mart → validated semantic metadata → ledger → named checks with golden figures →
    export;
  - **publishing:** a new build goes live only if every check passes.
- **The semantic contract.** `metric_registry.json` holds metrics with synonyms and SUM/SUM expressions;
  `semantic_docs.json` documents tables and columns; `capability_manifest.json` lists what is not loaded;
  `known_issues.json` holds the caveats. The build refuses undocumented columns.
- **The pipeline shape** (`pipeline.py`): deterministic routes first, with one model call and a repair round only as
  the last resort.
- **Generic guard modules:** `guardrails.py`, `sql_safety.py`, `db.py` (authorizer), `review.py` (reviewer with a code
  veto), `protection.py`, `small_talk.py`, `premise.py` and `followup.py`.
- **The answer writer:** a bold headline, the model never typing figures, unit conversion, Excel reports with checks.
- **Voice mode** (`static/voice/`, `voice.py`, `voice_guard.py`, `spoken.py`): the turn flow, the read-back, the
  figure checks and the fallbacks are domain-free. The name matching needs the new domain's names, and the
  pronunciation rules need its units and acronyms.
- **Test method:**
  - a question bank whose expected figures come from **independent** SQL on the base facts;
  - a follow-up bank with a seeded random walk;
  - spoken tests that re-ask each miss as text;
  - an integrity hash test;
  - headless-Edge checks with a simulated microphone.

### 18.2 Domain-specific (rewrite for a new project)
- **The data:** the sources, `schema_core.sql`, `mart.py`, `warehouse/metadata/*.json`, `semantic/example_queries.sql`
  and `knowledge_base.yaml`.
- **The vocabulary:** the domain vocabulary in `semantic_layer.py` (place hierarchy, period rules), the RDPR wording in
  `guardrails.py` / `small_talk.py`, the domain reports in `reports.py` and `breakdown.py`, and the dashboard panels.
- **Voice details:** the voice clip, the speech-to-text context paragraph (terms, never names), and the mishearing
  rules in `spoken.py`.

### 18.3 Recipe for a new project
1. **Profile and reconcile the sources first.** Find the shared master; rebuild any module that disagrees with it.
2. **Write the core DDL**, with a CHECK for every business rule, and the staging rules. Get the build's checks green,
   golden figures included.
3. **Build the mart** for the questions people ask, with pre-summed tables for the dashboard.
4. **Fill the metadata:** docs, a metric registry with synonyms, capabilities, known issues and 30–40 reviewed example
   queries.
5. **Copy `ai_app/`** and change the vocabulary, reports, breakdowns and the dashboard.
6. **Write the stress bank** with independent expected SQL, and iterate until it is 100%. Then write the follow-up
   bank.
7. **Add voice last.** Re-tune the speech-to-text context and the name matching, and run the spoken tests.

### 18.4 Lessons learned
- **Physical, pre-summed marts** took the dashboard from about 12 seconds to 4–30 ms.
- **Never average a ratio or add a position across time.** Guard it in the SQL checker; don't trust the prompt alone.
- **A reviewer model invents objections.** Make it name one error category, and let code overrule what it can
  disprove.
- **Don't list proper names in the speech-to-text context.** It snaps to a confident wrong name; let the clean-up
  match, or ask.
- **Precision over recall** for anything that changes an answer (follow-up rewriting, premise corrections, name
  fixes). When unsure, ask or stay silent.
- **Test from independent SQL, and re-run on unseen random seeds,** so the code is not tuned to its own tests.
- **Compare spoken results per question, not only the total.** A shift in the total can hide a regression.
- **Keep heavy imports at module level, or list them in requirements.** numpy was imported inside a function, and a
  missing install would have silently switched off a voice guard. It is now in `requirements.txt`.

---

## 19. Change log

| Date | Change |
|---|---|
| 2026-10-01 | Data compared; HRMS rebuilt on the shared master; core star database built |
| 2026-10-02 | AI layer audited against the NL2SQL blueprint; reviewed reports and the integrity test added |
| 2026-10-03 | KPCL front end copied (dashboard, insights, AI mode, charts) in the RDPR wine colour |
| 2026-10-03 | Rebuilt to the KPCL standard: staged warehouse with checks and lineage; physical and pre-summed marts; dashboard about 100× faster; situation reports, breakdowns, Excel answer reports, vendored assets; stress test 318 / 318 |
| 2026-10-03 | Dashboard: Karnataka map as the first card, the Revenue / Finance / HRMS module boxes, and the bookshelf for scheme books closed |
| 2026-10-03 | Voice mode added (from Meghalaya / KPCL): guardrails, the wine panel, spoken answers; spoken stress test 727 → 826 / 896; 9 / 9 browser scenarios |
| 2026-10-05 | Deleted the old pre-warehouse database (0.9 GB) and the unused `semantic/sources/`. Typed "collection percent / pct / per cent" now means the percentage. Map redrawn from KGIS with all 31 zillas, Vijayanagara on its own. Follow-up questions carried over, typed and spoken |
| 2026-10-05 | Follow-up stress tests: typed 892 / 892; two fresh walks 1,316 / 1,316; spoken 721 / 790, every miss a mishearing; main spoken test 826 → 829 / 896. Fixes they found: head / scheme / property / staff-type swaps, "current year demand", two-piece measures, rankings then one place, unknown places, the `context` flag, a long `previous`. Spoken clean-up: bare names in follow-ups, "an" / "den" / "areas", glued "and" / "GP", a GP matched within the taluk said with it. 318 / 318 on the VPN |
| 2026-10-05 | Guardrail survey (KPCL and Meghalaya read for reference). Implemented **C1** (false-premise check, `app/premise.py`) and **B1** (small talk and abuse, `app/small_talk.py`); 383 offline tests, 318 / 318 stress, 892 / 892 follow-up turns |
| 2026-10-05 | The voice button always opens the full voice panel: never reopens docked, and expands a docked panel; checked in Edge, 10 / 10 paths |
| 2026-10-05 | HANDOFF rewritten for setup on another computer and reuse in a new project; `numpy` added to `ai_app/requirements.txt` (it was imported but not listed) |

# RDPR Data Assistant — Test Question Bank

Questions for testing the Panchayat Raj Data Assistant, covering **Revenue**, **Finance & Accounting** and **HRMS**.

Every question below was run against the live assistant on 2 October 2026 and returned the result shown. The last
section is different: those questions *should* be refused, because the warehouse does not hold that data.

**How to use:** paste a question into the chat page (`/chat`), or click it in the Suggested questions sidebar where listed.
Figures come from the synthetic POC dataset covering April 2022 – September 2026 (FY 2022-23 to FY 2026-27).

| | |
|---|---|
| Questions tested | 49 |
| Answered | 45 |
| Correctly refused | 4 |

**How answers are produced.** Most questions never reach the language model: they are answered by reviewed code
(a single-metric lookup, a reviewed query, or a multi-module report), so they return the same figure every time.
Only the rest go to the model, which writes SQL that is then checked by the query guard before it runs.

---

## Revenue — totals and single figures

| # | Question | Answered by |
|---|---|---|
| 1 | What was the total collection in Mysuru zilla in 2024-25? | single figure, answered by code |
| 2 | What is the total outstanding balance for Karnataka in 2024-25? | single figure, answered by code |
| 3 | What was the collection percentage in Bagalkot taluk in 2025-26? | single figure, answered by code |
| 4 | What were the arrears for Karnataka in 2024-25? | single figure, answered by code |
| 5 | What was the current-year demand in Belagavi zilla in 2024-25? | single figure, answered by code |
| 6 | What is the total outstanding balance for Karnataka in 2024-25, in lakhs? | single figure, answered by code |
| 7 | How many properties are there in Mysuru zilla in 2024-25? | single figure, answered by code |

## Revenue — rankings and comparisons

| # | Question | Answered by |
|---|---|---|
| 1 | Which five zillas collected the most revenue in 2025-26? | written by the model, then checked |
| 2 | Which zilla had the lowest collection percentage in 2025-26? | written by the model, then checked |
| 3 | Which zillas have the highest outstanding balance in 2025-26? | reviewed SQL, identical every time |
| 4 | Which ten GPs collected the most revenue in 2025-26? | reviewed SQL, identical every time |
| 5 | Which five GPs in Badami taluk have the lowest collection percentage in 2025-26? | reviewed SQL, identical every time |
| 6 | Compare Mysuru and Belagavi in 2024-25 | multi-module report, answered by code |

## Revenue — breakdowns and trends

| # | Question | Answered by |
|---|---|---|
| 1 | What were the demand, collection and balance for Karnataka in each financial year? | reviewed SQL, identical every time |
| 2 | Taluk-wise collection percentage in Mysuru zilla for 2025-26 | reviewed SQL, identical every time |
| 3 | Revenue collected by revenue head in Belagavi zilla in 2024-25 | reviewed SQL, identical every time |
| 4 | Month-wise revenue collection across Karnataka in 2024-25 | reviewed SQL, identical every time |
| 5 | Demand and collection by property category across Karnataka in 2024-25 | reviewed SQL, identical every time |
| 6 | How have arrears for Karnataka grown each financial year? | reviewed SQL, identical every time |

## Finance & Accounting

| # | Question | Answered by |
|---|---|---|
| 1 | How many GPs closed all their books in 2024-25? | single figure, answered by code |
| 2 | What percentage of scheme books were closed for 2024-25, by zilla? | reviewed SQL, identical every time |
| 3 | Receipts and expenditure of each scheme across Karnataka in 2024-25 | reviewed SQL, identical every time |
| 4 | Which five taluks have the lowest share of GPs that closed all their books in 2025-26? | reviewed SQL, identical every time |
| 5 | How many GPs closed all their books in each financial year? | reviewed SQL, identical every time |
| 6 | What were the scheme receipts for Mysuru zilla in 2024-25? | single figure, answered by code |
| 7 | What was the expenditure in Belagavi zilla in 2024-25? | single figure, answered by code |

## HRMS

| # | Question | Answered by |
|---|---|---|
| 1 | How many active GP staff are there in Badami taluk, by designation? | reviewed SQL, identical every time |
| 2 | How many active staff are there by staff type across Karnataka? | reviewed SQL, identical every time |
| 3 | Which five taluks have the most staff registrations pending at the EO in 2025-26? | reviewed SQL, identical every time |
| 4 | Which GPs in Bagalkot zilla had no President registered in 2022-23? | reviewed SQL, identical every time |
| 5 | How many staff are approved by the EO in Mysuru zilla in 2024-25? | written by the model, then checked |
| 6 | How many staff registrations are pending at the EO in Mysuru zilla in 2024-25? | written by the model, then checked |
| 7 | What is the gender split of active staff in each zilla? | reviewed SQL, identical every time |
| 8 | For each zilla, how many of the seats in GP bodies are filled by elected members in 2025-26? | reviewed SQL, identical every time |

## Cross-module reports

| # | Question | Answered by |
|---|---|---|
| 1 | Overall performance of Mysuru zilla in 2024-25 | multi-module report, answered by code |
| 2 | Summary of FY 2024-25 | multi-module report, answered by code |
| 3 | Overall performance of Karnataka in 2024-25 | multi-module report, answered by code |
| 4 | Which taluks need attention in 2025-26? | multi-module report, answered by code |
| 5 | Which GPs are at risk in Bagalkot taluk? | multi-module report, answered by code |

## Reference / counts

| # | Question | Answered by |
|---|---|---|
| 1 | How many taluks and GPs does each zilla have? | reviewed SQL, identical every time |
| 2 | How many GPs are there in Mysuru zilla? | single figure, answered by code |

## Definitions

| # | Question | Answered by |
|---|---|---|
| 1 | What is DCB? | definition |
| 2 | What is RDPR? | reference answer |
| 3 | What is Panchatantra 2.0? | reference answer |
| 4 | What can I ask? | about the assistant |

## Should be refused (data not held)

These ask for data the system does not hold. A correct result is a clear refusal naming what is missing —
never a guess and never an empty table.

| # | Question | Expected |
|---|---|---|
| 1 | What is the budget allocation for Mysuru zilla? | Refused — data not loaded |
| 2 | Show me the MGNREGA job cards in Badami taluk | Refused — data not loaded |
| 3 | What is the population of Mysuru zilla? | Refused — data not loaded |
| 4 | Show me the audit paragraphs for 2024-25 | Refused — data not loaded |

---

## Varying the questions

Each question above is a template. Swap in any of these and it should still work:

- **Zilla** (31) — Mysuru, Belagavi, Bagalkot, Ballari, Tumakuru, Dakshina Kannada, Bengaluru Urban …
- **Taluk** (238) — Badami, Bagalkot, Hungund, Ilkal …  *(name the taluk, e.g. "in Badami taluk")*
- **GP** (6,099) — write it as "<name> GP in <taluk> taluk", since GP names repeat across taluks
- **Financial year** — 2022-23, 2023-24, 2024-25, 2025-26, 2026-27 *(2026-27 is part-year: April–September 2026)*
- **Units** — add "in lakhs" or "in crore" to any money question

## What to check in an answer

1. The figure matches the dashboard for the same zilla and year — both read the same queries.
2. Percentages are computed as total ÷ total, not an average of percentages.
3. A named period and place appear in the answer, so you can see what was actually measured.
4. Where a caveat applies (part-year FY 2026-27, taluk-level salary data), it is stated.
5. Open **SQL** under any model-written answer to see exactly what was run.

## Known limits worth testing

- **Salary bills are taluk-level only** — a GP-level salary question cannot be answered.
- **FY 2026-27 is part-year** (April–September 2026), so its year totals are incomplete.
- **Day-book and month-end closure come from separate tables** and can differ for the same taluk and month.
- Questions needing the model require the VPN; single figures, reviewed queries, reports and definitions work without it.

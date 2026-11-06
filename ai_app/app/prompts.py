"""
Builds the single prompt sent to the model per question, within a token budget (the gateway model has a 32k context;
the prompt is kept to settings.rdpr_prompt_token_budget, estimated at 4 characters per token):

  1. fixed instructions (RDPR rules, output contract);
  2. the schema of only the mart views relevant to the question (from the semantic layer, with grain, units and column
     docs) -- never the raw dim_* / fact_* tables, which the model may not read anyway;
  3. the formulas of the metrics named in the question, the glossary terms used, the always-on rules;
  4. the worked examples most similar to the question;
  5. the verified entities (zilla / taluk / GP names, periods, schemes ...) extracted deterministically.
If the budget is exceeded, examples are dropped first, then column docs are shortened.
"""
from __future__ import annotations

import json
import re

from app.config import settings
from app.semantic_layer import norm
from app.verified_queries import example_questions, example_sql

SYSTEM_INSTRUCTIONS = """\
You write SQL for a read-only question-answering assistant over the Karnataka Rural Development and Panchayat Raj \
(RDPR) data: Finance & Accounting (book closure, scheme receipts and expenditure), Revenue (demand, collection, arrears, \
balance by tax and property type) and HRMS (staff, EO approvals, elected members, salary bills) for 6,099 Gram \
Panchayats (GPs) in 238 taluks and 31 zillas, April 2022 to 30 September 2026, stored in SQLite. The data is a \
synthetic POC dataset that mirrors the Panchatantra 2.0 portal.

You get ONE turn. Return a single JSON object with:
  answerable       true, or false when the question can't be answered correctly from these views;
  sql              ONE read-only SQLite SELECT (or WITH ... SELECT) over the mart_* views below. Every value baked in
                   as a literal; give EVERY selected column an alias with AS. An alias is ONE snake_case word
                   (AS total_collection). The unit shown in square brackets in the schema below, e.g. [INR], is
                   documentation only: never write it into the SQL, the alias or the ORDER BY;
  answer_template  one or two plain sentences answering the question, with {alias} placeholders that Python fills
                   from your query's FIRST row after running it (you will NOT see the result). Only use aliases from
                   your SELECT or keys from the entities block. Never put numbers you guessed in it;
  clarification_message  only when answerable is false: one short sentence about what the data lacks;
  chart_data       null, or {"type": "bar"|"line", "label_column": alias, "value_column": alias, "series_label": text}
                   for multi-row comparisons ("bar") or trends over time ("line").

Hard rules (breaking one makes the answer wrong):
- Only mart_* views and only columns listed below. SQLite dialect: no FROM dual, no ILIKE, date maths with date() / \
strftime(); integer division truncates, so multiply by 1.0 first.
- Ratios are always SUM(numerator)*100.0/SUM(denominator) over the rows in scope (formulas below). Never AVG or SUM a \
stored *_pct column across rows. Never add arrears, total_demand, balance, closing balance or HR snapshot counts across \
financial years or months.
- Use one fact at the grain of the question; never join two facts directly (rows multiply). To compare figures from \
different facts, aggregate each in its own GROUP BY sub-query at the join grain, or use a mart_summary_* view.
- Zilla, taluk, GP and scheme names, fy ('2025-26'), month_label ('MAR-2026') and dates must be exactly as in the \
entities block or the schema. For one GP also filter taluk_name, because GP names repeat.
- 'Now', 'currently', 'latest' mean the end of the data, 30-Sep-2026 (FY 2026-27 is only April-September 2026). \
'Last year' means FY 2025-26.
- Rankings: exclude NULLs and use ORDER BY ... LIMIT. Return one row per entity unless a breakdown or trend is asked.
- Money is INR; return INR (rounded to 2 places), not crore, unless asked. Never return names or salaries of individual people.
- If the question needs data not listed below (budgets, audit, MGNREGA works, population, grievances, taxpayer-level \
records, daily collection, salary bills by GP), set answerable=false. Never answer from general knowledge.
"""

_GEO_PERIOD_COLS = {"fy", "month_id", "month_label", "gp_id", "gp_name", "taluk_id", "taluk_name", "zilla_id", "zilla_name",
                    "scheme_id", "fee_type_id", "property_type_id", "staff_type_code"}


def _approx_tokens(text: str) -> int:
    return len(text) // 4


def schema_block(tables: dict, full_docs: bool = True) -> str:
    lines = []
    for name, t in tables.items():
        lines.append(f"TABLE {name}  -- grain: {t['grain']}. {t['doc'] if full_docs else ''}".rstrip())
        for c, info in t["columns"].items():
            unit = f" [{info['unit']}]" if info.get("unit") else ""
            doc = f" -- {info['doc']}" if full_docs and info.get("doc") and c not in _GEO_PERIOD_COLS else ""
            lines.append(f"  {c} {info['type']}{unit}{doc}")
        lines.append("")
    return "\n".join(lines)


def metrics_block(metrics: list[dict]) -> str:
    lines = []
    for m in metrics:
        forms = [f"{v['expr']} from {v['table']}" + (f" WHERE {v['filter']}" if v.get("filter") else "") + f" (by {p})"
                 for p, v in m["variants"].items()]
        lines.append(f"- {m['label']} [{m['unit']}]: " + "; ".join(forms))
    return "\n".join(lines)


_WORD_RE = re.compile(r"[a-z0-9]+")
_STOP = {"the", "of", "in", "and", "a", "an", "is", "are", "how", "many", "what", "which", "for", "to", "on", "by",
         "with", "was", "were", "did", "does", "do", "from", "that", "have", "has", "per", "or", "as", "at", "be", "it"}


def select_examples(question: str, limit: int) -> list[tuple[str, str]]:
    q = {w for w in _WORD_RE.findall(norm(question)) if w not in _STOP}
    questions, sqls = example_questions(), example_sql()
    scored = []
    for n, text in questions.items():
        words = set(_WORD_RE.findall((text + " " + sqls[n]).lower().replace("_", " ")))
        scored.append((len(q & words), -n, n))
    keep = sorted(n for _, _, n in sorted(scored, reverse=True)[:limit])
    return [(questions[n], sqls[n]) for n in keep]


_AMOUNT_RE = re.compile(r"(?:₹|rs\.?\s*)?(\d+(?:\.\d+)?)\s*(lakhs?|lacs?|crores?|cr)\b", re.IGNORECASE)


def annotate_amounts(question: str) -> str:
    """'above 50 lakh' -> 'above 50 lakh [= 5000000 rupees]': every money column is in rupees, and a model converting
    lakh and crore itself sometimes drops a zero."""
    def add(m: re.Match) -> str:
        v = float(m.group(1)) * (1e5 if m.group(2).lower().startswith(("lakh", "lac")) else 1e7)
        return f"{m.group(0)} [= {v:.0f} rupees]"
    return _AMOUNT_RE.sub(add, question)


def build_prompt(question: str, pruned: dict, entities: dict, max_examples: int = 6) -> str:
    budget = settings.rdpr_prompt_token_budget
    ent = {k: v for k, v in entities.items() if k not in ("intents", "place_notes")}
    ent["data_as_of"] = pruned["data_period"]["data_as_of"]
    for full_docs, n_examples in ((True, max_examples), (True, 3), (False, 3), (False, 0)):
        parts = [
            SYSTEM_INSTRUCTIONS,
            "\n## Columns every GP-level view carries (not repeated in each table)\n"
            "fy (text '2025-26'), month_id (YYYYMM), month_label ('MAR-2026'), gp_id, gp_name, taluk_id, taluk_name, "
            "zilla_id, zilla_name, scheme_id, scheme_name, fee_type_name, property_type_name, staff_type_name.\n",
            "\n## Views you may query (SQLite)\n" + schema_block(pruned["tables"], full_docs),
        ]
        if pruned["metrics"]:
            parts.append("\n## Metric formulas (use exactly these)\n" + metrics_block(pruned["metrics"]))
        parts.append("\n## Rules for this data\n" + "\n".join(f"- {r}" for r in pruned["rules"]))
        if pruned["glossary"]:
            parts.append("\n## Terms in the question\n" + "\n".join(f"- {k}: {v}" for k, v in pruned["glossary"].items()))
        if n_examples:
            ex = select_examples(question, n_examples)
            parts.append("\n## Worked examples (reviewed SQL for similar questions)\n" +
                         "\n\n".join(f"-- Q: {q}\n{s};" for q, s in ex))
        parts.append("\n## Entities already identified in the question (verified names; the question may name more)\n"
                     + json.dumps(ent, ensure_ascii=False))
        parts.append(f"\n## Question\n{annotate_amounts(question)}\n")
        prompt = "".join(parts)
        if _approx_tokens(prompt) <= budget:
            return prompt
    return prompt


def coverage_repair_prompt(prompt: str, refusal: str) -> str:
    """The model declined by claiming a period is outside the data when it is not."""
    return (prompt + "\n\n## Your previous answer was wrong\nYou declined with: \"" + refusal[:400] + "\"\n"
            "That is not true. Finance and Revenue have every month from April 2022 to September 2026 (FY 2022-23 to "
            "FY 2026-27, the last one partial), and salary bills start in January 2022. Return answerable=true with SQL that "
            "answers the question, unless it truly needs data that is not in the schema above.\n")


def repair_prompt(prompt: str, bad_sql: str, error: str) -> str:
    return (prompt + "\n\n## Your previous answer failed\nThe SQL you returned was:\n```sql\n" + bad_sql + "\n```\n"
            "It was rejected or failed with:\n" + error + "\n\nReturn a corrected JSON object (same keys) whose SQL fixes "
            "exactly this problem. Check every view and column name against the schema above.\n")


# ---------------------------------------------------------------------------------------------- answer verification
VERIFY_RULES = """Facts about the data (use them to judge):
- Geography: Karnataka = 31 zillas (districts) > 238 taluks > 6,099 GPs. 'The state' means all of them; a filter on a zilla
  or taluk the question did not name is an error. GP names repeat across taluks.
- Data runs April 2022 to 30-Sep-2026. fy is text like '2025-26' (April-March); FY 2026-27 is April-September 2026 only.
  'Now' means 30-Sep-2026. 'Last year' means FY 2025-26. month_label is text like 'MAR-2026'.
- Collection % = SUM(total_collection)*100/SUM(total_demand). Books closed % = SUM(is_closed)*100/COUNT(*).
  Seats filled % = SUM(total_elected_members)*100/SUM(total_seats). Ratios are recomputed from sums, never averaged.
- Arrears, total_demand, balance, closing balances and HR snapshot counts are positions: never added across FYs or months.
  year_demand, total_collection, adjustments, receipts and expenditure are flows and may be added.
- Money is INR (1 lakh = 100,000; 1 crore = 10,000,000). Salary bills exist at taluk level only.
- Active staff = employment_status 'Active' in the staff-by-designation view."""


def verify_repair_prompt(prompt: str, bad_sql: str, problem: str) -> str:
    return (prompt + "\n\n## A reviewer rejected your previous answer\nThe SQL you returned was:\n```sql\n" + bad_sql +
            "\n```\nThe reviewer found: " + problem + "\n\nReturn a corrected JSON object (same keys) that fixes exactly "
            "this problem. If the reviewer is wrong, return the same SQL again.\n")

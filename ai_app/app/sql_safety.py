"""
Checks on model-written SQL before it reaches the database. Two kinds, both fail closed (a query that can't be shown
safe is refused, and its error goes back to the model for one repair attempt):

  1. Read-only shape: one SELECT / WITH statement, no write or admin keyword, no unresolved {placeholder}, only
     mart_* views (the authorizer in app.db enforces this again at compile time; this check exists to give the model a
     clear repair message).
  2. RDPR grain guards -- the ways a clean-looking query silently returns a wrong number on this data:
       a. averaging or summing a stored ratio (collection_pct, closure_pct ...) instead of SUM(num)/SUM(den);
       b. adding a cumulative or snapshot column (arrears, total_demand, balance, closing balance, HR snapshot counts)
          across financial years or months: they are positions, not flows;
       c. joining two facts of different grain without pre-aggregating each in its own GROUP BY sub-query: the join
          repeats rows and double counts;
       d. a column named after a KPI (collection_pct, books_closed_pct ...) that is not computed with its formula.
The rewrite _nulls_last() then makes ascending sorts put missing values last (SQLite sorts NULL first).
"""
from __future__ import annotations

import re

from app.semantic_layer import load_semantic_layer

_FORBIDDEN = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "ATTACH", "DETACH", "PRAGMA",
              "VACUUM", "REINDEX", "ANALYZE", "GRANT", "REVOKE", "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE"]
_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(_FORBIDDEN) + r")\b|\bREPLACE\s+INTO\b|\bRECURSIVE\b", re.IGNORECASE)
_START_RE = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}")
_TABLE_REF_RE = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w]*)\s*(\()?", re.IGNORECASE)
_CTE_RE = re.compile(r"(?:\bWITH\b|,)\s*([A-Za-z_]\w*)\s*(?:\([^)]*\))?\s+AS\s*(?:NOT\s+)?(?:MATERIALIZED\s+)?\(", re.IGNORECASE)
_AGG_COL_RE = re.compile(r"\b(AVG|SUM|TOTAL)\s*\(\s*(?:DISTINCT\s+)?(?:[A-Za-z_]\w*\.)?([A-Za-z_]\w*)\s*\)", re.IGNORECASE)
_TABLE_FUNCTIONS = {"json_each", "json_tree"}
_PERIOD_COLS = ("fy", "month_label", "month_id", "date")


class UnsafeSQLError(ValueError):
    """The SQL is not a safe / correct query for this data. The message is written for the model's repair turn."""


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    return re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)


def _strip_strings(sql: str) -> str:
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def validate_readonly_sql(sql: str, entities: dict | None = None) -> str:
    """Return the cleaned SQL (execute that, not the input) or raise UnsafeSQLError."""
    if not sql or not sql.strip():
        raise UnsafeSQLError("Empty SQL.")
    cleaned = _strip_comments(sql).strip().rstrip(";").strip()
    code = _strip_strings(cleaned)
    if ";" in code:
        raise UnsafeSQLError("Multiple statements are not allowed; return one SELECT.")
    if not _START_RE.match(code):
        raise UnsafeSQLError("Only a single SELECT (or WITH ... SELECT) statement is allowed.")
    m = _PLACEHOLDER_RE.search(cleaned)
    if m:
        raise UnsafeSQLError(f"The SQL contains the template placeholder {m.group(0)}; put the literal value in the SQL. "
                             "Curly-brace placeholders belong only in answer_template.")
    m = _FORBIDDEN_RE.search(code)
    if m:
        raise UnsafeSQLError(f"Forbidden keyword in SQL: {m.group(0)!r}. Only read-only SELECT queries are allowed.")
    ctes = {c.lower() for c in _CTE_RE.findall(code)}
    layer = load_semantic_layer()
    for name, paren in _TABLE_REF_RE.findall(code):
        low = name.lower()
        if low in ctes or (paren and low in _TABLE_FUNCTIONS) or low == "select":
            continue
        if low not in layer["tables"]:
            raise UnsafeSQLError(f"Table {name!r} is not available. Use only the mart_* views listed in the schema.")
    check_alias_words(code)
    check_place_names(cleaned, layer)
    check_grain(code, layer)
    check_kpi_formulas(code)
    return _nulls_last(cleaned)


_PLACE_FILTER_RE = re.compile(r"\b(zilla_name|taluk_name|gp_name)\s*(=|==|LIKE|IN\s*\()\s*((?:'[^']*'\s*,?\s*)+)", re.IGNORECASE)


def check_place_names(sql: str, layer: dict) -> None:
    """A filter on a place that is not in the data returns nothing and reads as 'no data'. The usual case is
    zilla_name = 'Karnataka': the state is every row, so it needs no place filter at all."""
    ents = layer["entities"]
    known = {"zilla_name": {z["name"].lower() for z in ents["zillas"]},
             "taluk_name": {t["name"].lower() for t in ents["taluks"]},
             "gp_name": {g["name"].lower() for g in ents["gps"]}}
    for m in _PLACE_FILTER_RE.finditer(sql):
        col = m.group(1).lower()
        if m.group(2).upper() == "LIKE":
            continue
        for lit in re.findall(r"'([^']*)'", m.group(3)):
            if lit.lower() not in known[col]:
                hint = (" Karnataka is the whole state: for a state-wide figure put no zilla / taluk / GP filter at all."
                        if lit.lower() in ("karnataka", "state", "all") else " Use a name exactly as listed in the entities.")
                raise UnsafeSQLError(f"{lit!r} is not a {col.split('_')[0]} in this data.{hint}")


# The schema documents units in brackets ("total_collection REAL [INR]"); a model sometimes copies the unit into the
# alias ("AS total_collection INR"), which is a syntax error. Catch it here so the repair turn gets a clear reason
# rather than a bare "near INR: syntax error" from the engine.
_BAD_ALIAS_RE = re.compile(r"\bAS\s+([A-Za-z_]\w*)\s+([A-Za-z_]\w*)", re.IGNORECASE)
_ALIAS_FOLLOWERS = {"from", "where", "group", "order", "having", "limit", "offset", "union", "except", "intersect",
                    "join", "inner", "left", "right", "full", "cross", "on", "and", "or", "as", "when", "then",
                    "else", "end", "asc", "desc", "nulls", "window", "over", "returning"}


def check_alias_words(code: str) -> None:
    for m in _BAD_ALIAS_RE.finditer(code):
        alias, nxt = m.group(1), m.group(2)
        if nxt.lower() in _ALIAS_FOLLOWERS:
            continue
        raise UnsafeSQLError(
            f"'AS {alias} {nxt}' is not a valid alias: an alias must be ONE word. The unit in square brackets in the "
            f"schema (for example [INR]) is documentation, not part of the name -- write 'AS {alias}' and leave the "
            "unit out of the SQL, the alias and the ORDER BY.")


# ---------------------------------------------------------------------------------------------- grain guards
def _tables_in(code: str) -> list[str]:
    return [n.lower() for n, _ in _TABLE_REF_RE.findall(code) if n.lower().startswith("mart_")]


def _has_period_restriction(code: str) -> bool:
    low = code.lower()
    if re.search(r"\b(fy|month_label|month_id|date)\s*(=|in\b|between\b)", low):
        return True
    m = re.search(r"\bgroup\s+by\b(.*?)(\border\b|\bhaving\b|\blimit\b|\)|$)", low, re.DOTALL)
    if not m:
        return False
    return any(re.search(r"\b" + p + r"\b", m.group(1)) for p in _PERIOD_COLS)


def check_grain(code: str, layer: dict) -> None:
    no_avg = set(layer["non_averageable_columns"])
    no_sum = set(layer["non_summable_columns"])
    for fn, col in _AGG_COL_RE.findall(code):
        fn_u, col_l = fn.upper(), col.lower()
        if fn_u == "AVG" and col_l in no_avg or fn_u in ("SUM", "TOTAL") and col_l in no_sum:
            raise UnsafeSQLError(
                f"{fn_u}({col}) is wrong on this data: {col} is a stored ratio, so averaging or adding it across rows gives a "
                "wrong figure. Compute it as SUM(numerator)/SUM(denominator) over the rows in scope, e.g. collection % = "
                "SUM(total_collection)*100.0/SUM(total_demand), year closure % = SUM(is_closed)*100.0/COUNT(*), day-book "
                "closure % = SUM(gps_closed)*100.0/SUM(total_gps) for one day. A stored pct may be read as-is only for one row.")
    tables = list(dict.fromkeys(_tables_in(code)))
    # b. positions added across periods
    for t in tables:
        cols = layer["tables"][t]["columns"]
        if not any(p in cols for p in _PERIOD_COLS):
            continue
        for fn, col in _AGG_COL_RE.findall(code):
            info = cols.get(col.lower())
            if fn.upper() in ("SUM", "TOTAL") and info and info.get("additive") is False and info.get("unit") in ("INR", "count") \
                    and not _has_period_restriction(code):
                raise UnsafeSQLError(
                    f"SUM({col}) adds a cumulative or snapshot figure across periods ({col} is a position, not a flow), which "
                    "double counts. Restrict to ONE financial year or month (fy = '2025-26' / month_label = 'MAR-2026'), or "
                    "GROUP BY fy / month_label so each period is its own row. (year_demand, total_collection, receipts and "
                    "expenditure are flows and may be added across periods.)")
    # c. facts of different grain joined without pre-aggregation
    facts = [t for t in tables if layer["tables"][t]["group"] not in ("dimension",)]
    if len(set(facts)) > 1 and not re.search(r"\bunion\b", code, re.IGNORECASE):
        for m in _TABLE_REF_RE.finditer(code):
            name = m.group(1).lower()
            if name not in set(facts):
                continue
            span = _enclosing_parens(code, m.start())
            if span is None or not re.search(r"\bgroup\s+by\b", code[span[0]:span[1]], re.IGNORECASE):
                raise UnsafeSQLError(
                    "The query combines several fact views (" + ", ".join(sorted(set(facts))) + ") without aggregating each one "
                    "first; a join repeats rows and double counts. Put each fact in its own GROUP BY sub-query at the grain you "
                    "join on (for example per zilla and fy), or use a mart_summary_* view, which already combines the modules.")


def _enclosing_parens(code: str, pos: int) -> tuple[int, int] | None:
    depth, i = 0, pos
    while i >= 0:
        if code[i] == ")":
            depth += 1
        elif code[i] == "(":
            if depth == 0:
                break
            depth -= 1
        i -= 1
    if i < 0:
        return None
    depth, j = 0, i + 1
    while j < len(code):
        if code[j] == "(":
            depth += 1
        elif code[j] == ")":
            if depth == 0:
                return i, j
            depth -= 1
        j += 1
    return i, len(code)


# A column the model names after a KPI must be computed with that KPI's formula.
# alias -> alternatives; each alternative lists the columns that formula needs (all of them).
_KPI_ALIASES = {
    "collection_pct": [("total_collection", "total_demand")], "collection_percentage": [("total_collection", "total_demand")],
    "books_closed_pct": [("is_closed",)], "closure_pct": [("is_closed",), ("gps_closed", "total_gps")],
    "seats_filled_pct": [("total_elected_members", "total_seats")],
}


def _select_expression(code: str, alias_pos: int) -> str:
    """The expression that ends right before 'AS <alias>' (walk back to the comma / SELECT at depth 0)."""
    depth, i = 0, alias_pos - 1
    while i >= 0:
        ch = code[i]
        if ch == ")":
            depth += 1
        elif ch == "(":
            if depth == 0:
                break
            depth -= 1
        elif ch == "," and depth == 0:
            break
        elif depth == 0 and re.match(r"(?i)select\b", code[i:i + 7]) and (i == 0 or not code[i - 1].isalnum()):
            i += 6
            break
        i -= 1
    return code[i + 1:alias_pos]


def check_kpi_formulas(code: str) -> None:
    for m in re.finditer(r"\bAS\s+([A-Za-z_]\w*)", code, re.IGNORECASE):
        need = _KPI_ALIASES.get(m.group(1).lower())
        if not need:
            continue
        expr = _select_expression(code, m.start())
        if "(" not in expr:  # a bare column read (e.g. collection_pct AS collection_pct) or a CTE alias carried through
            continue
        if not any(all(re.search(r"\b" + c + r"\b", expr) for c in alt) for alt in need) \
                and not re.search(r"\b" + m.group(1) + r"\b", expr):
            raise UnsafeSQLError(
                f"The column {m.group(1)} is not computed with its formula (it must use {' and '.join(need[0])}). Use "
                "collection % = SUM(total_collection)*100.0/SUM(total_demand); books closed % = SUM(is_closed)*100.0/COUNT(*).")


# ---------------------------------------------------------------------------------------------- NULLS LAST
_ORDER_BY_RE = re.compile(r"\bORDER\s+BY\b", re.IGNORECASE)
_ORDER_END_RE = re.compile(r"\b(LIMIT|OFFSET|UNION|EXCEPT|INTERSECT|WINDOW)\b", re.IGNORECASE)


def _nulls_last(sql: str) -> str:
    """Every ascending ORDER BY term gets NULLS LAST, so 'lowest' never names a row that has no figure."""
    out, pos = [], 0
    for m in _ORDER_BY_RE.finditer(sql):
        if m.start() < pos:
            continue
        start = i = m.end()
        depth = 0
        while i < len(sql):
            ch = sql[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    break
                depth -= 1
            elif ch == ";" and depth == 0:
                break
            elif depth == 0 and _ORDER_END_RE.match(sql, i) and (i == 0 or not (sql[i - 1].isalnum() or sql[i - 1] == "_")):
                break
            i += 1
        terms, depth, cur = [], 0, ""
        for ch in sql[start:i]:
            depth += ch == "("
            depth -= ch == ")"
            if ch == "," and depth == 0:
                terms.append(cur)
                cur = ""
            else:
                cur += ch
        terms.append(cur)
        fixed = []
        for t in terms:
            body = t.rstrip()
            if body and not re.search(r"\bNULLS\b", body, re.I) and not re.search(r"\bDESC$", body, re.I):
                body += " NULLS LAST"
            fixed.append(body + t[len(t.rstrip()):])
        out.append(sql[pos:start] + ",".join(fixed))
        pos = i
    return "".join(out) + sql[pos:]

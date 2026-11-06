"""
Verified query library: the reviewed SQL blocks of semantic/example_queries.sql. Even at temperature 0 a model can
return different SQL for the same question; a verified answer is identical every time.

Matching is deliberately conservative: the normalised question must be very close to a registered phrasing AND carry
exactly the same entity tokens (zilla / taluk / GP names, financial years, months, schemes, revenue heads), AND ask in
the same direction (highest vs lowest). "Mysuru" never matches the Belagavi entry; "2023-24" never matches "2024-25".
The result is written by the generic deterministic writer (app.answer), the same one the model path uses.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from functools import lru_cache

from app.config import EXAMPLE_QUERIES_PATH
from app.semantic_layer import extract_entities, norm

_THRESHOLD = 0.92
_DIRECTION_RE = re.compile(r"\b(highest|most|top|best|largest|maximum|lowest|least|bottom|worst|smallest|minimum|fewest)\b")


@lru_cache(maxsize=1)
def example_sql() -> dict[int, str]:
    text = EXAMPLE_QUERIES_PATH.read_text(encoding="utf-8")
    out = {}
    for block in re.split(r"\n(?=-- \d+\. )", text):
        m = re.match(r"-- (\d+)\. (.*)\n", block)
        if m:
            out[int(m.group(1))] = block[m.end():].strip().rstrip(";").strip()
    return out


@lru_cache(maxsize=1)
def example_questions() -> dict[int, str]:
    text = EXAMPLE_QUERIES_PATH.read_text(encoding="utf-8")
    return {int(n): q.strip() for n, q in re.findall(r"^-- (\d+)\. (.*)$", text, re.M)}


# The chart each reviewed answer carries (as on KPCL): example number -> (type, label column, value column, title).
# The figures are always the query's own rows; a doughnut is offered by the page for a bar of additive parts.
CHARTS: dict[int, tuple[str, str, str, str]] = {
    1: ("line", "fy", "total_collection", "Total collection"),
    2: ("bar", "zilla", "total_collection", "Total collection"),
    3: ("bar", "taluk", "collection_pct", "Collection %"),
    4: ("bar", "revenue_head", "total_collection", "Collection by revenue head"),
    5: ("bar", "month_label", "collection_amount", "Monthly collection"),
    6: ("bar", "zilla", "collection_pct", "Property tax collection %"),
    7: ("bar", "property_category", "total_demand", "Demand by property category"),
    8: ("bar", "gp", "collection_pct", "Collection %"),
    9: ("line", "fy", "arrears", "Arrears"),
    10: ("bar", "zilla", "growth_pct", "Growth in collection %"),
    11: ("bar", "zilla", "books_closed_pct", "Scheme books closed %"),
    13: ("line", "month_label", "books_closed_pct", "Own Resource Funds books closed %"),
    14: ("bar", "taluk", "all_books_closed_pct", "GPs that closed all books %"),
    15: ("bar", "scheme", "receipts", "Receipts by scheme"),
    16: ("bar", "scheme", "closing_balance", "Closing balance by scheme"),
    17: ("bar", "zilla", "closing_balance", "Scheme balances, March 2026"),
    18: ("bar", "zilla", "closure_pct", "Day-book closure %"),
    19: ("bar", "designation", "staff_count", "Active staff by designation"),
    20: ("bar", "staff_type", "staff_count", "Active staff by staff type"),
    21: ("bar", "taluk", "pending_at_eo", "Registrations pending at the EO"),
    22: ("line", "month_label", "salary_rejected_by_bank", "Salaries rejected by the bank"),
    24: ("bar", "zilla", "seats_filled_pct", "Seats filled %"),
    25: ("bar", "staff_type", "salary_paid", "Staff paid, September 2026"),
    26: ("bar", "zilla", "collection_pct", "Collection %"),
    27: ("bar", "zilla", "female_pct", "Women among active staff %"),
    28: ("bar", "gp", "total_collection", "Total collection"),
    29: ("bar", "size_class", "collection_pct", "Collection % by GP size"),
    30: ("bar", "zilla", "total_gps", "GPs per zilla"),
    31: ("bar", "zilla", "balance", "Outstanding balance"),
    32: ("line", "fy", "total_collection", "Total collection"),
    33: ("bar", "gp", "collection_pct", "Collection %"),
    34: ("line", "fy", "gps_all_books_closed", "GPs that closed all books"),
}


@dataclass(frozen=True)
class VerifiedQuery:
    key: str
    example_no: int

    @property
    def sql(self) -> str:
        return example_sql()[self.example_no]

    @property
    def chart(self) -> tuple[str, str, str, str] | None:
        return CHARTS.get(self.example_no)


def _tokens(question: str) -> tuple:
    e = extract_entities(question)
    periods = tuple(sorted(p["value"] for p in e.get("periods", [])))
    places = tuple(sorted([*e.get("zillas", []), *e.get("taluks", []), *[g["name"] for g in e.get("gps", [])]]))
    other = tuple(sorted([*e.get("schemes", []), *e.get("fee_types", []), *e.get("staff_types", []), *e.get("designations", [])]))
    direction = tuple(sorted(set(_DIRECTION_RE.findall(norm(question)))))
    return periods, places, other, direction


def _clean(q: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", norm(q)).strip()


@lru_cache(maxsize=1)
def _registry() -> list[tuple[int, str, tuple]]:
    return [(n, _clean(q), _tokens(q)) for n, q in example_questions().items()]


def match(question: str) -> VerifiedQuery | None:
    cq = _clean(question)
    if not cq:
        return None
    tokens = None
    best = None
    for n, text, tok in _registry():
        ratio = difflib.SequenceMatcher(None, cq, text).ratio()
        if ratio >= _THRESHOLD and (best is None or ratio > best[0]):
            best = (ratio, n, tok)
    if best is None:
        return None
    tokens = _tokens(question)
    return VerifiedQuery(f"example_{best[1]}", best[1]) if tokens == best[2] else None

"""
False premises in a data question (guardrail C1). A question can state a figure as already true and ask about something
else: "Of the ₹500 crore collected in Mysuru zilla in FY 2024-25, how much was property tax?", "Mysuru's collection is
30%, so what is the balance?", "Is Hassan's total demand 200 crore?". Answering the rest as if the stated figure held
would read as the assistant endorsing a wrong number, so when the data contradicts the stated figure the answer opens
with the correction:

    **The question says ₹500 crore, but the data shows ₹124.30 crore.** Total collection for Mysuru zilla in FY 2024-25
    was ₹124.30 crore. The answer below is from the data.

How (deterministic, no model call; precision over recall -- when unsure it stays silent):
  1. extract: a number stated with a unit -- rupees (₹ / Rs / rupees / crore / lakh), percent, or a count of things
     ("6,000 GPs", "1.6 crore properties"). Not a premise: thresholds and conditions ("more than 20%", "20% or less",
     "below 27%", "top 5", "which 5 zillas"), years, months and dates, ordinals ("15th Finance Commission"), the
     percentages in scheme names ("SC/ST Funds 25%"), bare numbers;
  2. measure: the registry measure named next to the number ("collected", "collection rate", "arrears", "properties",
     "GPs" ...) whose unit matches the number's; none -> no check;
  3. recompute that measure on its own, through the reviewed single-figure lookup (app.metric_lookup), for the place,
     period and revenue head / scheme of the question -- not from the answer, which may be about something else;
  4. compare at the precision stated ("about 6,000 GPs" matches 6,099; "₹120 crore" matches ₹124.30 crore; "30%" does
     not match 27.17%). Only a figure that is clearly off is corrected.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app import metric_lookup
from app.db import ReadOnlyDB
from app.followup import _canon, _dims, _periods
from app.semantic_layer import extract_entities, router_index

DATA_ROUTES = ("metric:", "report:", "verified:", "breakdown:", "llm")

_NUM = re.compile(r"(?<![\w.])(₹\s*|rs\.?\s*|inr\s*)?(\d[\d,]*(?:\.\d+)?)(\s*(?:crores?|cr|lakhs?|lacs?|lac|thousand)\b)?"
                  r"(\s*(?:%|percent\b|per cent\b|rupees\b|rs\b))?", re.I)
_SCALE = {"crore": (1e7, "crore"), "crores": (1e7, "crore"), "cr": (1e7, "crore"), "lakh": (1e5, "lakh"),
          "lakhs": (1e5, "lakh"), "lacs": (1e5, "lakh"), "lac": (1e5, "lakh"), "thousand": (1e3, "thousand")}
# things counted -> the registry measure that counts them
_COUNT_NOUNS = [(r"gps|gram panchayats?|grama panchayats?|panchayats", "gp_count"), (r"taluks?", "taluk_count"),
                (r"staff|employees|workers", "staff_active"), (r"properties|property", "number_of_properties"),
                (r"elected members|members", "elected_members"), (r"seats", "total_seats"),
                (r"presidents|adhyakshas", "presidents")]
_COUNT_RE = re.compile(r"^\s*(?:active\s+)?(" + "|".join(p for p, _ in _COUNT_NOUNS) + r")\b", re.I)
_BEFORE_NOT = re.compile(r"(?:\b(?:more|less|fewer|greater|higher|lower|bigger|smaller)\s+than|\b(?:above|below|over|under|"
                         r"exceeding|exceeds?|exceeded|beyond|within|upto|up to|at least|at most|atleast|between|and|or|top|"
                         r"bottom|first|last|best|worst|least|minimum|maximum|min|max|than|from|to|by|per|which|what|show|"
                         r"list|give|name|any|threshold|limit|cut ?off|target|goal|crossed?|reach(?:ed)?)|[<>=≤≥])\s*$", re.I)
_AFTER_NOT = re.compile(r"^\s*(?:(?:or|and)\s+(?:less|more|below|above|fewer|lower|higher|under|over|beyond)\b|\+|plus\b|"
                        r"(?:st|nd|rd|th)\b)", re.I)
_HEDGE = re.compile(r"\b(?:about|around|approximately|approx|roughly|nearly|almost|close to|some|~)\s*$", re.I)
_UNIT_OF_KIND = {"INR": "INR", "%": "%", "count": "count"}


@dataclass
class Premise:
    said: str          # as it should be written back ("₹500 crore", "30%", "6,000 GPs")
    value: float       # in the measure's own unit (rupees, percent, a count)
    kind: str          # "INR" | "%" | "count"
    tol: float         # how far the data may be from it and still agree
    start: int
    end: int
    metric: str = ""   # registry measure, set by _measure
    counted: str = ""  # for a count, the measure of the things counted ("GPs" -> gp_count)


def _precision(num: str, kind: str) -> float:
    """The step of the number as written: 124.3 -> 0.1; 500 -> 100 (a round figure); 30% -> 1 (percents are exact)."""
    digits = num.replace(",", "")
    if "." in digits:
        return 10 ** -len(digits.split(".")[1])
    if kind == "%":
        return 1.0
    stripped = digits.rstrip("0")
    return 10 ** (len(digits) - len(stripped)) if stripped else 1.0


def extract(question: str) -> list[Premise]:
    text = _canon(question)
    low = text.lower()
    skip = _periods(low, []) + [(a, b) for _, a, b in _dims(low, [])]
    out: list[Premise] = []
    for m in _NUM.finditer(text):
        a, b = m.span()
        if any(a < y and x < b for x, y in skip):
            continue
        before, after = low[:a], low[b:]
        if _BEFORE_NOT.search(before) or _AFTER_NOT.match(after):
            continue
        if m.end(2) < len(text) and text[m.end(2):m.end(2) + 1].isalpha() and not m.group(3):
            continue                                            # "15th", "2nd", "3rd"
        num = m.group(2)
        n = float(num.replace(",", ""))
        scale_word = (m.group(3) or "").strip().lower()
        unit = (m.group(4) or "").strip().lower()
        mult, scale = _SCALE.get(scale_word, (1.0, ""))
        cnt = _COUNT_RE.match(after)
        counted = ""
        if unit in ("%", "percent", "per cent"):
            kind, value, said = "%", n, f"{num}%"
        elif cnt and not m.group(1):
            if mult == 1.0 and n < 50:
                continue                                        # "5 zillas", "10 GPs": a list size, not a claim
            noun = text[m.end() + cnt.start(1):m.end() + cnt.end(1)]
            kind, value, said = "count", n * mult, f"{num}{(' ' + scale) if scale else ''} {noun}"
            counted = next((k for pat, k in _COUNT_NOUNS if re.fullmatch(pat, cnt.group(1).lower())), "")
            b = m.end() + cnt.end()
        elif m.group(1) or scale or unit in ("rupees", "rs"):
            kind, value, said = "INR", n * mult, f"₹{num}{(' ' + scale) if scale else ''}"
        else:
            continue                                            # a bare number: no unit, nothing to check it as
        if n == 0:
            continue
        # agree within the precision written (a round "₹120 crore" or "6,000 GPs" is an approximation), but never more
        # than 5% off (10% after "about", "around", "nearly" ...), and always within half a percent
        hedged = bool(_HEDGE.search(before))
        tol = 0.5 * _precision(num, kind) * (mult if kind != "%" else 1.0)
        if kind != "%":
            tol = max(min(tol, abs(value) * (0.10 if hedged else 0.05)), abs(value) * 0.005)
        elif hedged:
            tol = max(tol, 2.0)
        out.append(Premise(said, value, kind, tol, a, b, counted=counted))
    return out


def _measure(question: str, p: Premise) -> str:
    """The registry measure named next to the figure, with the same kind of unit; "" when none."""
    low = _canon(question).lower()
    lo, hi = max(0, p.start - 60), min(len(low), p.end + 60)
    units = {m["key"]: m["unit"] for m in _layer_metrics()}
    best, dist = "", 1e9
    for syn, key in router_index().metric_synonyms:
        for m in re.finditer(r"(?<![a-z0-9])" + re.escape(syn) + r"(?![a-z0-9])", low[lo:hi]):
            s, e = lo + m.start(), lo + m.end()
            if p.start <= s < p.end:
                continue
            k = key
            if p.kind == "%" and units.get(k) == "INR" and k == "total_collection":
                k = "collection_pct"                            # "collection is 30%" is the collection percentage
            if units.get(k) != p.kind:
                continue
            d = min(abs(s - p.end), abs(p.start - e))
            if d < dist:
                best, dist = k, d
    if p.kind == "count" and p.counted:
        # "6,000 GPs" counts GPs -- unless the claim itself goes on "... closed all their books" right after the noun
        after = low[p.end:p.end + 25]
        claims = best in ("gps_all_books_closed", "presidents") and re.match(r"\s*(?:have|had|has|with|that)?\s*"
                                                                              r"(?:closed|registered|president)", after)
        best = best if claims else p.counted
    return best


def _layer_metrics() -> list[dict]:
    from app.semantic_layer import load_semantic_layer
    return load_semantic_layer()["metrics"]


_FIGURE = re.compile(r"₹[\d,]+(?:\.\d+)?(?: crore| lakh)?|[\d,]+(?:\.\d+)?%|\d[\d,]*(?:\.\d+)?")


async def check(question: str, db: ReadOnlyDB, timeout_seconds: float, answer: str = "") -> str:
    """The correction to lead the answer with ("" when every stated figure agrees with the data, or none is stated).
    `answer` is the answer about to be shown: a data sentence it already opens with is not repeated."""
    premises = extract(question)
    if not premises:
        return ""
    base = extract_entities(question)
    low = _canon(question).lower()
    dim_spans = _dims(low, [])
    lines = []
    for p in premises[:2]:
        p.metric = _measure(question, p)
        if not p.metric:
            continue
        ents = {k: v for k, v in base.items() if k not in ("metrics", "intents")}
        ents["metrics"], ents["intents"] = [p.metric], []
        if next((m for m in _layer_metrics() if m["key"] == p.metric), {}).get("static"):
            ents["periods"] = []                                # the number of GPs / taluks does not change by year
        # a revenue head / scheme counts only when it is named next to the figure ("₹500 crore collected" is all heads,
        # even if the question goes on to ask about property tax)
        def same_clause(a: int, b: int) -> bool:
            gap = low[p.end:a] if a >= p.end else low[b:p.start]
            return len(gap) < 30 and not re.search(r"[;,?.]|\b(?:how|what|which|of it|of that)\b", gap)
        near = any(same_clause(a, b) for _, a, b in dim_spans)
        if not near:
            for k in ("fee_types", "schemes", "property_categories", "staff_types", "designations"):
                ents.pop(k, None)
        try:
            ma = await metric_lookup.answer(ents, db, timeout_seconds)
        except Exception:  # noqa: BLE001 -- a check that can't run stays silent
            continue
        if not ma or not ma.final or ma.metric != p.metric or not ma.rows or ma.rows[0][0] is None:
            continue
        value = float(ma.rows[0][0])
        if abs(value - p.value) <= p.tol:
            continue
        head = re.match(r"\s*\*\*(.+?)\*\*", ma.answer or "", re.S)
        if not head:
            continue
        sentence = head.group(1).strip()
        figs = _FIGURE.findall(sentence.split(" was ")[-1]) if " was " in sentence else []
        if not figs:
            continue
        lines.append((p.said, figs[-1], sentence))
    if not lines:
        return ""
    said = " and ".join(s for s, _, _ in lines)
    shows = " and ".join(f for _, f, _ in lines)
    head = f"**The question says {said}, but the data shows {shows}.**"
    shown = re.match(r"\s*\*\*(.+?)\*\*", answer or "", re.S)
    detail = [s if s.endswith(".") else s + "." for _, _, s in lines if not (shown and s.rstrip(".") == shown.group(1).strip().rstrip("."))]
    if not detail:
        return head                                             # the answer itself is that figure: lead with the correction only
    return f"{head} {' '.join(detail)} The answer below is from the data."

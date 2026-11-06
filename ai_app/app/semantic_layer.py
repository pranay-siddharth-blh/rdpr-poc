"""
Loads semantic/semantic_layer.json (read-only) and turns a question into entities with plain regex / dictionary
matching -- no LLM, no embeddings, no database call -- so this step is never a latency source. The entities feed
the metric lookup, the prompt (as verified names), the SQL guards and the answer writer.

Entities (all optional):
  zillas [names], taluks [names], gps [{id, name, taluk, zilla}], place_notes [str],
  schemes [names], fee_types [names], property_categories [keys], staff_types [names], designations [names],
  periods [{kind, value, fy, label, relative}], metrics [keys], intents [ranking, comparison, breakdown, trend],
  scope ('state' for Karnataka-wide questions), as_of
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache

from app.config import SEMANTIC_LAYER_PATH

_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_MONTH_WORD = (r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
               r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
_FULL_MONTH = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
               "november", "december"]


@lru_cache(maxsize=1)
def load_semantic_layer() -> dict:
    return json.loads(SEMANTIC_LAYER_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def column_info() -> dict[str, dict]:
    """Column name -> {unit, additive, doc} merged over all mart tables (first definition wins)."""
    out: dict[str, dict] = {}
    for t in load_semantic_layer()["tables"].values():
        for c, info in t["columns"].items():
            out.setdefault(c, info)
    return out


def data_as_of() -> str:
    return load_semantic_layer()["data_period"]["data_as_of"]


def norm(text: str) -> str:
    """Lower case, curly quotes straightened, runs of spaces collapsed; hyphens kept."""
    s = (text or "").lower().replace("’", "'").replace("–", "-").replace("—", "-")
    return " ".join(s.split())


def _word_re(phrase: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])")


# ---------------------------------------------------------------------------------------------- router index
@dataclass
class RouterIndex:
    zillas: dict[str, list[str]] = field(default_factory=dict)      # name -> [lower-case names / aliases], longest first
    taluks: dict[str, list[str]] = field(default_factory=dict)
    taluk_zilla: dict[str, str] = field(default_factory=dict)
    gp_names: dict[str, list[dict]] = field(default_factory=dict)   # lower-case gp name -> [{id, name, taluk, zilla}]
    gp_max_words: int = 1
    schemes: dict[str, list[str]] = field(default_factory=dict)     # scheme name -> aliases
    fee_types: dict[str, list[str]] = field(default_factory=dict)
    property_categories: dict[str, list[str]] = field(default_factory=dict)
    staff_types: dict[str, list[str]] = field(default_factory=dict)
    designations: dict[str, str] = field(default_factory=dict)      # lower-case -> name
    fiscal_years: set[str] = field(default_factory=set)
    month_labels: set[str] = field(default_factory=set)
    metric_synonyms: list[tuple[str, str]] = field(default_factory=list)  # (synonym, metric key), longest first
    date_from: str = ""
    date_to: str = ""


@lru_cache(maxsize=1)
def router_index() -> RouterIndex:
    layer = load_semantic_layer()
    ents = layer["entities"]
    idx = RouterIndex()
    for z in ents["zillas"]:
        names = {z["name"].lower(), *[a.lower() for a in ents["zilla_aliases"].get(z["name"], [])]}
        idx.zillas[z["name"]] = sorted(names, key=len, reverse=True)
    for t in ents["taluks"]:
        idx.taluks[t["name"]] = [t["name"].lower()]
        idx.taluk_zilla[t["name"]] = t["zilla"]
    for g in ents["gps"]:
        idx.gp_names.setdefault(g["name"].lower(), []).append(g)
    idx.gp_max_words = max(len(n.split()) for n in idx.gp_names)
    for s in ents["schemes"]:
        names = {s["name"].lower(), *ents["scheme_aliases"].get(s["id"], [])}
        idx.schemes[s["name"]] = sorted(names, key=len, reverse=True)
    for f in ents["fee_types"]:
        names = {f["name"].lower(), *ents["fee_type_aliases"].get(f["id"], [])}
        idx.fee_types[f["name"]] = sorted(names, key=len, reverse=True)
    idx.property_categories = {k: sorted(v, key=len, reverse=True) for k, v in ents["property_category_aliases"].items()}
    for s in ents["staff_types"]:
        names = {s["name"].lower(), *ents["staff_type_aliases"].get(str(s["code"]), [])}
        idx.staff_types[s["name"]] = sorted(names, key=len, reverse=True)
    idx.designations = {d.lower(): d for d in ents["designations"]}
    idx.fiscal_years = set(ents["all_fiscal_years"])
    idx.month_labels = set(ents["month_labels"])
    syn = [(s.lower(), m["key"]) for m in layer["metrics"] for s in m["synonyms"]]
    idx.metric_synonyms = sorted(syn, key=lambda x: len(x[0]), reverse=True)
    idx.date_from = layer["data_period"]["data_from"]
    idx.date_to = layer["data_period"]["data_to"]
    return idx


# ---------------------------------------------------------------------------------------------- periods
def fy_label(start_year: int) -> str:
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def month_label(year: int, month: int) -> str:
    return f"{_MONTHS[month - 1].upper()}-{year}"


def _fy_of(year: int, month: int) -> str:
    return fy_label(year if month >= 4 else year - 1)


_FY_PATTERNS = [
    re.compile(r"(?<![\d-])(?:fy|f\.y\.?|financial year|fiscal year)?\s*'?(20\d\d)\s*[-/–]\s*(20\d\d|\d\d)(?![\d])"),
    re.compile(r"\bfy\s?(\d\d)(\d\d)\b"),
    re.compile(r"\bfy\s?'?(\d\d)\s*[-/–]\s*(\d\d)\b"),
]
_MONTH_YEAR = re.compile(r"(?<![a-z0-9])" + _MONTH_WORD + r"\.?[\s,'-]*((?:20)?\d\d)(?![\d])")
_DAY_MONTH_YEAR = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?[\s-]+" + _MONTH_WORD + r"[a-z]*\.?[\s,-]+(20\d\d)\b")
_ISO_DATE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")
_CALENDAR_YEAR = re.compile(r"(?<![\d-])(20\d\d)(?![\d-])")
_QUARTER = re.compile(r"\bq([1-4])\b")


def _month_no(word: str) -> int:
    return _MONTHS.index(word[:3]) + 1


def extract_periods(q: str) -> list[dict]:
    """Periods named in the (normalised) question: FY, month, day, quarter, calendar year, relative words."""
    idx = router_index()
    periods: list[dict] = []
    taken: list[tuple[int, int]] = []

    def free(span):
        return not any(span[0] < b and a < span[1] for a, b in taken)

    for pat in _FY_PATTERNS:
        for m in pat.finditer(q):
            if not free(m.span()):
                continue
            if pat is _FY_PATTERNS[0]:
                y1, y2 = int(m.group(1)), int(m.group(2)) % 100
                ok = (y1 + 1) % 100 == y2
            else:
                y1, y2 = 2000 + int(m.group(1)), int(m.group(2))
                ok = (y1 + 1) % 100 == y2
            if not ok:
                continue
            label = fy_label(y1)
            kind = "fy" if label in idx.fiscal_years else "out_of_range"
            periods.append({"kind": kind, "value": label, "fy": label, "label": f"FY {label}", "relative": False})
            taken.append(m.span())
    for m in _ISO_DATE.finditer(q):
        if free(m.span()):
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                dt.date(y, mo, d)
            except ValueError:
                continue
            periods.append(_date_period(y, mo, d))
            taken.append(m.span())
    for m in _DAY_MONTH_YEAR.finditer(q):
        if free(m.span()):
            try:
                dt.date(int(m.group(3)), _month_no(m.group(2)), int(m.group(1)))
            except ValueError:
                continue
            periods.append(_date_period(int(m.group(3)), _month_no(m.group(2)), int(m.group(1))))
            taken.append(m.span())
    for m in _MONTH_YEAR.finditer(q):
        if not free(m.span()):
            continue
        yr = m.group(2)
        year = int(yr) if len(yr) == 4 else 2000 + int(yr)
        mo = _month_no(m.group(1))
        label = month_label(year, mo)
        kind = "month" if label in idx.month_labels else "out_of_range"
        periods.append({"kind": kind, "value": label, "fy": _fy_of(year, mo), "label": f"{_FULL_MONTH[mo - 1].title()} {year}",
                        "relative": False})
        taken.append(m.span())
    for m in _CALENDAR_YEAR.finditer(q):
        if free(m.span()):
            y = int(m.group(1))
            kind = "calendar_year" if 2022 <= y <= 2026 else "out_of_range"
            periods.append({"kind": kind, "value": str(y), "fy": "", "label": str(y), "relative": False})
            taken.append(m.span())
    for m in _QUARTER.finditer(q):
        if free(m.span()):
            periods.append({"kind": "quarter", "value": f"Q{m.group(1)}", "fy": "", "label": f"Q{m.group(1)}", "relative": False})
    if not any(p["kind"] in ("fy", "month", "date", "calendar_year", "out_of_range") for p in periods):
        dp = load_semantic_layer()["data_period"]
        if re.search(r"\b(last|previous|prior) (financial |fiscal )?(year|fy)\b", q):
            periods.append({"kind": "fy", "value": dp["latest_full_fy"], "fy": dp["latest_full_fy"],
                            "label": f"FY {dp['latest_full_fy']}", "relative": True})
        elif re.search(r"\b(this|current) (financial |fiscal )?(year|fy)\b|\bcurrently\b|\bso far this year\b", q):
            periods.append({"kind": "fy", "value": dp["partial_fy"], "fy": dp["partial_fy"],
                            "label": f"FY {dp['partial_fy']} (April to September 2026)", "relative": True})
        elif re.search(r"\blast month\b|\bprevious month\b", q):
            periods.append({"kind": "month", "value": "AUG-2026", "fy": "2026-27", "label": "August 2026", "relative": True})
        elif re.search(r"\bthis month\b|\bcurrent month\b", q):
            periods.append({"kind": "month", "value": "SEP-2026", "fy": "2026-27", "label": "September 2026", "relative": True})
    return periods


def _date_period(y: int, mo: int, d: int) -> dict:
    iso = f"{y}-{mo:02d}-{d:02d}"
    idx = router_index()
    kind = "date" if idx.date_from <= iso <= idx.date_to else "out_of_range"
    return {"kind": kind, "value": iso, "fy": _fy_of(y, mo), "label": f"{d:02d}-{_MONTHS[mo - 1].title()}-{y}", "relative": False}


# ---------------------------------------------------------------------------------------------- entity extraction
_RANKING_RE = re.compile(r"\b(top|highest|lowest|most|least|best|worst|bottom|rank\w*|largest|smallest|biggest|maximum|minimum|"
                         r"leading|lagging|fewest|greatest|which (?:zilla|taluk|gp|gram panchayat|district)s?)\b")
_COMPARE_RE = re.compile(r"\b(compare\w*|versus|vs\.?|difference|growth|grew|increase\w*|decrease\w*|change|than|"
                         r"year[- ]on[- ]year|yoy|improv\w*|declin\w*|dropp\w*|rose|fell)\b")
_BREAKDOWN_RE = re.compile(r"\b(by|wise|each|every|per|split|breakdown|break down|across|list|all (?:the )?(?:zillas|taluks|gps|schemes))\b")
_TREND_RE = re.compile(r"\b(trend|month[- ]by[- ]month|month[- ]wise|monthly|over time|each month|year[- ]by[- ]year|"
                       r"year[- ]wise|yearly|every month|every year|each (?:financial )?year|all (?:the )?(?:financial )?years|"
                       r"over the years|across (?:the )?years|each fy|every fy|since 20\d\d)\b")
# "how many GPs collected less than 20%", "GPs with no president", "taluks above 30%": a condition on each place. No
# reviewed route answers that (they give totals and rankings), so such a question always goes to the SQL path.
_THRESHOLD_RE = re.compile(r"\b(more|less|fewer|greater|higher|lower|bigger|smaller) than\s+(₹\s*|rs\.?\s*)?\d|"
                           r"\b(above|below|over|under|at least|at most|exceed\w*|upto|up to)\s+(₹\s*|rs\.?\s*)?\d")
_NEGATION_RE = re.compile(r"\b(no|none of( their| the)?|not|without|zero|never|nil)\b")
_PLACE_COUNT_RE = re.compile(r"\bhow many (gps|gram panchayats|grama panchayats|taluks|zillas|districts)\b|"
                             r"\b(which|list( the| all)?|show( me)?( the| all)?) (gps|gram panchayats|taluks|zillas|districts) "
                             r"(have|had|has|with|where|whose|that|did|collected|closed)\b")


def is_filter_question(q: str) -> bool:
    q = norm(q)
    if _THRESHOLD_RE.search(q):
        return True
    return bool(_PLACE_COUNT_RE.search(q) and _NEGATION_RE.search(q))


# plain wording that names a measure without one of its registry synonyms (used only when no synonym matched)
_WORD_METRICS = [
    (re.compile(r"\bclosed (every|each|all) (scheme |year |scheme year )?books?\b"), "gps_all_books_closed"),
    (re.compile(r"\bbooks?\b.{0,40}\bclos(e|ed|ing|ure)\b|\bclos(e|ed)\b.{0,30}\bbooks?\b"), "books_closed_pct"),
    (re.compile(r"\bbank\b.{0,30}\breject|\breject\w*\b.{0,30}\bbank\b"), "salary_rejected"),
    (re.compile(r"\breject\w*\b.{0,50}\b(eo|executive officer)\b"), "staff_rejected_by_eo"),
    (re.compile(r"\b(pending|waiting|awaiting)\b.{0,50}\b(eo|executive officer)\b"), "staff_pending_at_eo"),
    (re.compile(r"\bapprov\w*\b.{0,50}\b(eo|executive officer)\b"), "staff_approved_by_eo"),
    (re.compile(r"\bspend(s|ing)?\b"), "expenditure"),
    (re.compile(r"\b(paid|pay|payment)\b.{0,20}\bsalar(y|ies)\b|\bsalar(y|ies)\b.{0,20}\bpaid\b"), "salary_paid"),
    (re.compile(r"\b(have|has|with) an? (president|adhyaksha)\b|\bpresidents?\b.{0,15}\bregistered\b"), "presidents"),
    (re.compile(r"\bsalary bills?\b"), "salary_paid"),
    (re.compile(r"\bcollect(s|ed|ing)?\b"), "total_collection"),
]
# "across Karnataka", "for all GPs": the whole state, not a breakdown by place
_STATE_SPAN_RE = re.compile(r"\b(?:across|in|for|of|over) (?:the )?(?:karnataka|state|whole state|entire state)\b|"
                            r"\b(?:for|of|across|in) all (?:the )?(?:gps|gram panchayats)\b|"
                            r"\b(?:approved|rejected|processed|signed|sent|generated|paid|raised|kept|held) by (?:the )?\w+")
_STATE_RE = re.compile(r"\b(karnataka|statewide|state[- ]wide|the state|across the state|in the state|whole state|entire state|"
                       r"overall|all zillas|all districts|all gps|all gram panchayats|all taluks)\b")
_PLACE_HINT_RE = {
    "taluk": re.compile(r"^\s*(?:taluk|taluka|taluk panchayat|tp)\b"),
    "zilla": re.compile(r"^\s*(?:zilla|zilla panchayat|district|zp)\b"),
}
_GP_KEYWORD_RE = re.compile(r"\b(gps?|gram panchayats?|grama panchayats?|gram panchayaths?|village panchayats?)\b")
_NAME_STOP = {"which", "what", "how", "the", "of", "in", "for", "and", "all", "each", "every", "any", "top", "by", "a",
              "an", "to", "from", "at", "is", "are", "was", "were", "show", "list", "give", "me", "my"}


def _find_names(q: str, table: dict[str, list[str]]) -> list[tuple[str, int, int]]:
    """(canonical, start, end) for every name / alias found, longest first, non-overlapping."""
    cands = []
    for canon, names in table.items():
        for n in names:
            for m in _word_re(n).finditer(q):
                cands.append((canon, m.start(), m.end()))
    cands.sort(key=lambda c: (c[1] - c[2], c[1]))   # longest span first
    taken, out = [], []
    for canon, a, b in cands:
        if any(a < y and x < b for x, y in taken):
            continue
        taken.append((a, b))
        out.append((canon, a, b))
    return sorted(out, key=lambda c: c[1])


def _extract_gps(q: str, idx: RouterIndex, claimed: list[tuple[int, int]]) -> list[dict]:
    """A GP is named next to a 'GP' / 'gram panchayat' word (before or after, up to the longest GP name)."""
    found: list[dict] = []
    words = [(m.group(), m.start(), m.end()) for m in re.finditer(r"[a-z0-9'.-]+", q)]
    for kw in _GP_KEYWORD_RE.finditer(q):
        k_start, k_end = kw.span()
        # words just before the keyword ("badami gp") then just after ("gp badami")
        before = [w for w in words if w[2] <= k_start][-idx.gp_max_words:]
        after = [w for w in words if w[1] >= k_end][: idx.gp_max_words]
        best = None
        for n in range(len(before), 0, -1):
            cand = " ".join(w[0] for w in before[-n:])
            if cand in idx.gp_names and cand not in _NAME_STOP:
                best = (cand, before[-n][1], before[-1][2])
                break
        if best is None:
            for n in range(len(after), 0, -1):
                cand = " ".join(w[0] for w in after[:n])
                if cand in idx.gp_names and cand not in _NAME_STOP:
                    best = (cand, after[0][1], after[n - 1][2])
                    break
        if best:
            found.append({"phrase": best[0], "span": best[1:], "matches": idx.gp_names[best[0]]})
    out: list[dict] = []
    for f in found:
        claimed.append(f["span"])
        out.append(f)
    return out


def extract_entities(question: str) -> dict:
    q = norm(question)
    idx = router_index()
    ent: dict = {}
    claimed: list[tuple[int, int]] = []

    # --- places: zilla, taluk (a name found in both lists needs a hint word after it), GP
    zl = _find_names(q, idx.zillas)
    tl = _find_names(q, idx.taluks)
    gp_hits = _extract_gps(q, idx, claimed)
    zillas, taluks, notes = [], [], []
    taluk_spans = {(a, b): c for c, a, b in tl}
    for canon, a, b in zl:
        hint = "zilla" if _PLACE_HINT_RE["zilla"].match(q[b:]) or re.search(r"(?:zilla|district)\s+$", q[:a]) else ""
        t_here = next((c for (x, y), c in taluk_spans.items() if x < b and a < y), None)
        if t_here and not hint:
            if _PLACE_HINT_RE["taluk"].match(q[b:]) or re.search(r"taluk\s+(?:of\s+)?$", q[:a]):
                taluks.append(t_here)
            else:
                zillas.append(canon)
                notes.append(f"'{canon}' is both a zilla and a taluk; treated as the zilla (say '{canon} taluk' for the taluk).")
        else:
            zillas.append(canon)
        claimed.append((a, b))
    for canon, a, b in tl:
        if any(a < y and x < b for x, y in claimed):
            continue
        taluks.append(canon)
        claimed.append((a, b))
    ent["zillas"] = list(dict.fromkeys(zillas))
    ent["taluks"] = list(dict.fromkeys(taluks))
    if gp_hits:
        gps = []
        for h in gp_hits:
            matches = h["matches"]
            missing_in = ""
            if ent["taluks"]:
                narrowed = [m for m in matches if m["taluk"] in ent["taluks"]]
                if narrowed:
                    matches = narrowed
                else:
                    missing_in = f"{ent['taluks'][0]} taluk"
            if not missing_in and ent["zillas"]:
                narrowed = [m for m in matches if m["zilla"] in ent["zillas"]]
                if narrowed:
                    matches = narrowed
                else:
                    missing_in = f"{ent['zillas'][0]} zilla"
            if missing_in:
                gps.append({"id": "", "name": matches[0]["name"], "taluk": "", "zilla": "", "not_found_in": missing_in})
                continue
            if len(matches) == 1:
                m = matches[0]
                gps.append({"id": m["id"], "name": m["name"], "taluk": m["taluk"], "zilla": m["zilla"]})
            else:
                gps.append({"id": "", "name": matches[0]["name"], "taluk": "", "zilla": "",
                            "candidates": [{"id": m["id"], "taluk": m["taluk"], "zilla": m["zilla"]} for m in matches]})
        ent["gps"] = gps
    else:
        ent["gps"] = []
    ent["place_notes"] = notes

    # --- other dimensions
    ent["schemes"] = list(dict.fromkeys(c for c, _, _ in _find_names(q, idx.schemes)))
    ent["fee_types"] = list(dict.fromkeys(c for c, _, _ in _find_names(q, idx.fee_types)))
    ent["property_categories"] = list(dict.fromkeys(c for c, _, _ in _find_names(q, idx.property_categories)))
    ent["staff_types"] = list(dict.fromkeys(c for c, _, _ in _find_names(q, idx.staff_types)))
    if ent["staff_types"] == ["GP Staff"] and not re.search(r"\btypes?\b|category|class", q):
        ent["staff_types"] = []     # "active GP staff" means the staff of GPs, not the 'GP Staff' type
    desigs = []
    for low, name in sorted(idx.designations.items(), key=lambda kv: len(kv[0]), reverse=True):
        if _word_re(low).search(q) and not any(low in d.lower() for d in desigs):
            desigs.append(name)
    ent["designations"] = desigs
    ent["periods"] = extract_periods(q)

    # --- metrics: longest synonym wins; a shorter synonym inside an already matched span is ignored
    spans, metrics = [], []
    for syn, key in idx.metric_synonyms:
        for m in _word_re(syn).finditer(q):
            if any(m.start() < b and a < m.end() for a, b in spans):
                continue
            spans.append((m.start(), m.end()))
            if key not in metrics:
                metrics.append(key)
    if not metrics or set(metrics) <= {"gp_count", "staff_active"}:
        for rx, key in _WORD_METRICS:
            if rx.search(q) and not (metrics and key == "total_collection"):
                metrics.append(key)
                break
    if "staff_active" in metrics and len(metrics) > 1 and (
            any(k.startswith(("staff_", "salary_")) and k != "staff_active" for k in metrics)
            or not re.search(r"\b(active staff|headcount|how many staff|number of staff|staff strength|staff count)\b", q)):
        metrics.remove("staff_active")
    # "demand on residential properties": the category is a filter, not a count of properties
    if "number_of_properties" in metrics and len(metrics) > 1 and ent.get("property_categories") and \
            not re.search(r"\b(how many|number of|count of)\b", q):
        metrics.remove("number_of_properties")
    # "how many GPs have a president": the count is of the specific measure, not of GPs
    if "gp_count" in metrics and any(k in ("presidents", "gps_all_books_closed") for k in metrics):
        metrics.remove("gp_count")
    ent["metrics"] = metrics

    intents = []
    qi = _STATE_SPAN_RE.sub(" ", q)
    for name, rx in (("ranking", _RANKING_RE), ("comparison", _COMPARE_RE), ("breakdown", _BREAKDOWN_RE), ("trend", _TREND_RE)):
        if rx.search(qi):
            intents.append(name)
    if is_filter_question(q):
        intents.append("filter")
    ent["intents"] = intents
    if _STATE_RE.search(q):
        ent["scope"] = "state"
    ent["as_of"] = data_as_of()
    return {k: v for k, v in ent.items() if v or k in ("as_of",)}


_UNKNOWN_PLACE_RE = re.compile(r"\b([a-z][a-z'.-]*(?:\s+[a-z][a-z'.-]*){0,2})\s+(taluk|taluka|zilla|district)\b")
_UNKNOWN_GP_RE = re.compile(r"\b(?:of|in|for|at)\s+([a-z][a-z'.-]*(?:\s+[a-z][a-z'.-]*){0,2})\s+(?:gp|gram panchayat|grama panchayat)\b")
_GENERIC_BEFORE = {"which", "what", "each", "every", "all", "the", "a", "an", "any", "per", "by", "of", "in", "for", "my",
                   "and", "or", "that", "this", "these", "those", "same", "other", "another", "whole", "entire", "total",
                   "number", "count", "many", "how", "show", "list", "give", "me", "with", "no", "has", "have", "had",
                   "are", "is", "was", "were", "to", "from", "at", "on", "than", "their", "its", "his", "her", "our",
                   "karnataka", "state", "top", "highest", "lowest", "most", "least", "best", "worst", "bottom", "first",
                   "last", "next", "single", "individual", "larger", "smaller", "small", "large", "medium", "new", "old",
                   "taluk", "zilla", "district", "gp", "and", "between", "under", "within", "across", "name", "names",
                   "active", "inactive", "exited", "staff", "registered", "elected", "approved", "pending", "rejected"}


def unknown_names(question: str) -> list[str]:
    """Names written as '<name> taluk / zilla / district' or 'of <name> GP' that are not in the data."""
    q = norm(question)
    idx = router_index()
    known = {n for names in idx.zillas.values() for n in names} | {n for names in idx.taluks.values() for n in names}
    out = []
    for m in _UNKNOWN_PLACE_RE.finditer(q):
        words = m.group(1).split()
        last_generic = max((i for i, w in enumerate(words) if w in _GENERIC_BEFORE), default=-1)
        words = words[last_generic + 1:]
        if not words or re.fullmatch(r"(20\d\d|fy|q[1-4])", " ".join(words)):
            continue
        if any(" ".join(words[i:]) in known for i in range(len(words))):
            continue
        out.append(" ".join(words).title())
    for m in _UNKNOWN_GP_RE.finditer(q):
        words = m.group(1).split()
        if any(w in _GENERIC_BEFORE for w in words) or any(" ".join(words[i:]) in idx.gp_names for i in range(len(words))):
            continue
        out.append(" ".join(words).title())
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------------------------------------- glossary / identity
_DEFINITION_RE = re.compile(r"^\s*(?:what\s+(?:is|are|does|do)|what's|whats|define|meaning of|explain|full form of|expand)\s+"
                            r"(?:the\s+|an?\s+)?(?:meaning of\s+)?(?:term\s+)?(.+?)\s*(?:mean|stand for)?\s*\??\s*$")
_IDENTITY_RE = re.compile(r"\b(who are you|what are you|what can you do|what do you do|introduce yourself|help me|"
                          r"what can i ask|how can you help|your name)\b")


def is_identity_question(question: str) -> bool:
    return bool(_IDENTITY_RE.search(norm(question)))


def definitional_term(question: str) -> str | None:
    q = norm(question).rstrip("?. ")
    m = _DEFINITION_RE.match(q)
    if not m:
        return None
    subject = m.group(1).strip()
    for term, g in load_semantic_layer()["glossary"].items():
        if subject in [a.lower() for a in g["aliases"]] or subject == term.lower():
            return term
    return None


# ---------------------------------------------------------------------------------------------- pruning for the prompt
_MODULE_WORDS = {
    "finance": r"clos\w*|books?|scheme|receipts?|expenditure|spen[dt]\w*|expens\w*|balance|day ?book|account|grants?|fund\w*|finance|accounting|ledger|financial",
    "revenue": r"demand|collect\w*|arrears?|tax\w*|fees?|dcb|propert\w*|revenue|dues|outstanding|adjust\w*|recover\w*|mobile tower",
    "hrms": r"staff|eo\b|executive officer|salar\w*|bills?|president|adhyaksha|upadhyaksha|seats?|elected|members?|designation|"
            r"employees?|registr\w*|approv\w*|pending|reject\w*|hrms|paid|payroll|pdo|librarian",
}


def modules_in(question: str, entities: dict) -> set[str]:
    q = norm(question)
    mods = {m for m, rx in _MODULE_WORDS.items() if re.search(r"\b(" + rx + r")", q)}
    layer = load_semantic_layer()
    for key in entities.get("metrics", []):
        m = next((x for x in layer["metrics"] if x["key"] == key), None)
        if m:
            tbl = next(iter(m["variants"].values()))["table"]
            mods.add(layer["tables"][tbl]["group"] if layer["tables"][tbl]["group"] in _MODULE_WORDS else "")
    mods.discard("")
    if entities.get("schemes"):
        mods.add("finance")
    if entities.get("fee_types") or entities.get("property_categories"):
        mods.add("revenue")
    if entities.get("staff_types") or entities.get("designations"):
        mods.add("hrms")
    return mods


def prune_semantic_layer(question: str, entities: dict) -> dict:
    """The slice of the layer the prompt needs: tables of the modules the question touches (all modules when it names
    none), the summary views, the dimensions needed for names, the metric formulas named, glossary terms used."""
    layer = load_semantic_layer()
    mods = modules_in(question, entities) or set(_MODULE_WORDS)
    cross = len(mods) > 1
    keep = {}
    for name, t in layer["tables"].items():
        g = t["group"]
        if g in mods or g == "summary" and (cross or len(mods) == len(_MODULE_WORDS)) or name == "mart_dim_gp" \
                or (g == "dimension" and name in ("mart_dim_scheme", "mart_dim_fee_type", "mart_dim_property_type",
                                                  "mart_dim_staff_type", "mart_dim_fy", "mart_dim_month", "mart_dim_zilla")
                    and name_needed(name, mods, entities)):
            keep[name] = t
    if not any(layer["tables"][n]["group"] == "summary" for n in keep):
        keep["mart_summary_zilla_year"] = layer["tables"]["mart_summary_zilla_year"]
    q = norm(question)
    gloss = {k: v["plain"] for k, v in layer["glossary"].items() if any(_word_re(a).search(q) for a in v["aliases"])}
    metrics = [m for m in layer["metrics"] if m["key"] in entities.get("metrics", [])]
    return {"tables": keep, "metrics": metrics, "glossary": gloss, "rules": layer["rules"],
            "data_period": layer["data_period"], "caveats": layer["caveats"]}


def name_needed(table: str, mods: set[str], entities: dict) -> bool:
    return table in ("mart_dim_fy", "mart_dim_month", "mart_dim_zilla") or \
        (table == "mart_dim_scheme" and "finance" in mods) or \
        (table in ("mart_dim_fee_type", "mart_dim_property_type") and "revenue" in mods) or \
        (table == "mart_dim_staff_type" and "hrms" in mods)

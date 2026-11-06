"""
Follow-up questions. After "What was the total collection of Mysuru zilla in FY 2024-25?" an officer asks "and Hassan?",
"what about 2023-24?", "same for Badami taluk", "and the balance?" or "and mobile tower tax?". The page sends the last question it had answered
with the new one; resolve() rewrites a follow-up into a whole question by putting its place, period or measure in place
of the previous question's, and that whole question then goes through the unchanged pipeline (every screen and guard
applies to it, and the page shows "Taking this as: ..."). Deterministic, no model call; typed and spoken alike.

A follow-up is short and made only of places, periods, measures and the other things a question can be about
(revenue head, scheme, property category, staff type) plus linking words ("and", "what about", "same for",
"the", "in" ...). Without a cue word ("and", "what about" ...) it must also name no measure ("Hassan?", "2023-24?"), so a
short complete question ("Mysuru collection 2024-25") is never bent onto the previous one. When the new part cannot be
placed cleanly (one period now and two before, a measure before that is not a registry phrase) nothing is rewritten:
the question is answered as asked.
"""
from __future__ import annotations

import re

from app.semantic_layer import (_CALENDAR_YEAR, _DAY_MONTH_YEAR, _FY_PATTERNS, _ISO_DATE, _MONTH_YEAR, _QUARTER,
                                _extract_gps, _find_names, _word_re, router_index, unknown_names)

MAX_WORDS = 12
# "an": how speech-to-text often writes a spoken "and" ("An outstanding balance.")
_CUE_RE = re.compile(r"^(?:(?:ok|okay|so|now|then|also)[\s,]+)*(?:and|an|what about|how about|what of|same|the same|now|also|then|"
                     r"for|in)\b")
_FILLER = {"thanks", "thank", "you", "great", "nice", "good", "and", "an", "what", "about", "how", "of", "for", "in", "the", "same", "now", "then", "also", "ok", "okay", "so",
           "please", "instead", "there", "too", "as", "well", "with", "on", "at", "by", "to", "is", "it", "its", "was",
           "were", "that", "'s", "s", "zilla", "zillas", "district", "districts", "taluk", "taluks", "taluka", "gp", "gps",
           "gram", "grama", "panchayat", "panchayats", "fy", "financial", "fiscal", "year"}
_KIND_AFTER = re.compile(r"\s+(?:zilla panchayat|zillas?|districts?|taluk panchayat|talukas?|taluks?|grama? panchayats?|gps?)\b")
_KIND_BEFORE = re.compile(r"\b(?:zilla|district|taluka?|gp|grama? panchayat)\s+(?:of\s+)?$")
_TALUK_HINT = re.compile(r"^\s*(?:taluk|taluka|taluk panchayat|tp)\b")
_STATE_RE = re.compile(r"\b(?:karnataka|statewide|state[- ]wide|the (?:whole |entire )?state|all (?:the )?zillas)\b")
_RELATIVE_RE = re.compile(r"\b(?:last|previous|prior|this|current) (?:financial |fiscal )?(?:year|fy|month)\b|\bcurrently\b")
_CONNECT_BEFORE = re.compile(r"(?:\s*,\s*|\s+(?:in|of|under|from|for)\s+)$")
_BARE_FY = re.compile(r"^'?20\d\d\s*[-/]\s*(?:20)?\d\d$")
# a question that ranks or lists places of one kind: a follow-up naming one such place asks for that place's own figure
_GROUPED = {"zilla": re.compile(r"\b(?:zillas|districts|zilla[- ]wise|district[- ]wise|which (?:zilla|district)|by (?:zilla|district))\b"),
            "taluk": re.compile(r"\b(?:taluks|taluk[- ]wise|which taluk|by taluk)\b"),
            "gp": re.compile(r"\b(?:gps|gram panchayats|gp[- ]wise|which gp|by gp)\b")}


def _canon(text: str) -> str:
    """Spaces collapsed, curly quotes and dashes straightened: same length as its lower case, so spans line up."""
    s = (text or "").replace("’", "'").replace("–", "-").replace("—", "-")
    return " ".join(s.split())


def _free(span: tuple[int, int], taken: list[tuple[int, int]]) -> bool:
    return not any(span[0] < b and a < span[1] for a, b in taken)


def _places(low: str) -> list[tuple[str, str, int, int]]:
    """(kind, canonical name, start, end) per place, the kind words around it included ("district of Mysuru")."""
    idx = router_index()
    claimed: list[tuple[int, int]] = []
    found = [("gp", g["phrase"], *g["span"]) for g in _extract_gps(low, idx, claimed)]
    taluk_spans = [(a, b) for _, a, b in _find_names(low, idx.taluks)]
    for canon, a, b in _find_names(low, idx.zillas):
        if not _free((a, b), claimed):
            continue
        both = not _free((a, b), taluk_spans)
        found.append(("taluk" if both and _TALUK_HINT.match(low[b:]) else "zilla", canon, a, b))
        claimed.append((a, b))
    for canon, a, b in _find_names(low, idx.taluks):
        if _free((a, b), claimed):
            found.append(("taluk", canon, a, b))
            claimed.append((a, b))
    for m in _STATE_RE.finditer(low):
        if _free(m.span(), claimed):
            found.append(("state", "Karnataka", *m.span()))
            claimed.append(m.span())
    out = []
    for kind, canon, a, b in sorted(found, key=lambda f: f[2]):
        if kind != "state":
            m = _KIND_AFTER.match(low, b)
            b = m.end() if m else b
            m = _KIND_BEFORE.search(low[:a])
            a = m.start() if m else a
        out.append((kind, canon, a, b))
    return out


def _periods(low: str, taken: list[tuple[int, int]]) -> list[tuple[int, int]]:
    taken = list(taken)
    out = []
    for pat in (*_FY_PATTERNS, _ISO_DATE, _DAY_MONTH_YEAR, _MONTH_YEAR, _CALENDAR_YEAR, _QUARTER, _RELATIVE_RE):
        for m in pat.finditer(low):
            a, b = m.span()
            while a < b and low[a] == " ":
                a += 1
            if _free((a, b), taken):
                out.append((a, b))
                taken.append((a, b))
    return sorted(out)


def _metrics(low: str, taken: list[tuple[int, int]]) -> list[tuple[int, int]]:
    taken = list(taken)
    out = []
    for syn, _key in router_index().metric_synonyms:
        for m in _word_re(syn).finditer(low):
            if _free(m.span(), taken):
                out.append(m.span())
                taken.append(m.span())
    return sorted(out)


_DIMS = ("schemes", "fee_types", "property_categories", "staff_types")


def _dims(low: str, taken: list[tuple[int, int]]) -> list[tuple[str, int, int]]:
    """(kind, start, end) of every revenue head, scheme, property category and staff type named."""
    idx = router_index()
    taken = list(taken)
    out = []
    for kind in _DIMS:
        for _canon, a, b in _find_names(low, getattr(idx, kind)):
            if _free((a, b), taken):
                out.append((kind, a, b))
                taken.append((a, b))
    return sorted(out, key=lambda d: d[1])


def _parts(text: str):
    low = text.lower()
    places = _places(low)
    taken = [(a, b) for _, _, a, b in places]
    # "current year demand" is a measure, not the current year
    yearly = [(a, b) for a, b in _metrics(low, taken) if "year" in low[a:b]]
    periods = _periods(low, taken + yearly)
    dims = _dims(low, taken + periods)
    metrics = _metrics(low, taken + periods + [(a, b) for _, a, b in dims])
    return low, places, periods, dims, metrics


def is_fragment(question: str) -> bool:
    """A short follow-up made only of places, periods, measures and linking words, opened by a cue word ("and
    Hassan?", "what about the balance?"). Used by voice mode so that such a turn is not dropped as a fragment."""
    text = _canon(question).rstrip(" ?.!")
    low, places, periods, dims, metrics = _parts(text)
    return bool(_CUE_RE.match(low)) and _only_fillers(low, places, periods, dims, metrics) and         bool(places or periods or dims or metrics)


def _only_fillers(low: str, places, periods, dims, metrics) -> bool:
    if len(low.split()) > MAX_WORDS:
        return False
    rest = list(low)
    for a, b in [(a, b) for _, _, a, b in places] + periods + [(a, b) for _, a, b in dims] + metrics:
        rest[a:b] = " " * (b - a)
    return all(w in _FILLER for w in re.findall(r"[a-z0-9']+", "".join(rest)))


def _place_phrase(places) -> str:
    """The new place(s) as the router reads them best: "Hassan zilla", "Badami taluk", "Nelludi GP in Kundapura taluk"."""
    if len(places) == 1:
        kind, canon, _, _ = places[0]
        if kind == "zilla":
            return f"{canon} zilla"
        if kind == "taluk":
            return f"{canon} taluk"
        if kind == "state":
            return "Karnataka"
    return ""


def about_data(question: str) -> bool:
    """The question names a place, period, measure or head, so a follow-up can build on it."""
    _, places, periods, dims, metrics = _parts(_canon(question).rstrip(" ?.!"))
    return bool(places or periods or dims or metrics)


def _plain(new: str, body: str, places, periods, dims, metrics, pplaces, pperiods, pdims, pmetrics) -> str | None:
    """"What was the <measure> of <place> in <period> for <head>?" from the new parts, else the previous ones."""
    if metrics:
        measure = new[metrics[0][0]:metrics[-1][1]]
    elif pmetrics:
        measure = body[pmetrics[0][0]:pmetrics[-1][1]]
    else:
        return None
    if places:
        place = _place_phrase(places) or new[places[0][2]:places[-1][3]]
    else:
        place = body[pplaces[0][2]:pplaces[-1][3]] if pplaces else ""
    when = [new[a:b] for a, b in periods] or [body[a:b] for a, b in pperiods]
    when = ["FY " + w if _BARE_FY.match(w) else w for w in when]
    heads = [new[a:b] for _, a, b in dims] or [body[a:b] for _, a, b in pdims]
    out = f"What was the {measure}" + (f" of {place}" if place else "") + (f" in {' and '.join(when)}" if when else "") +         (f" for {' and '.join(heads)}" if heads else "") + "?"
    return out[0].upper() + out[1:]


def resolve(question: str, previous: str) -> str | None:
    """The whole question a follow-up stands for, or None when `question` is not a follow-up of `previous`."""
    prev, new = _canon(previous), _canon(question)
    if not prev or not new or prev.lower() == new.lower():
        return None
    new = new.rstrip(" ?.!")
    low, places, periods, dims, metrics = _parts(new)
    if not places:
        # a place the data does not have ("and Atlantis zilla?"): asked anyway, so the answer says it is not known
        for name in unknown_names(new):
            a = low.find(name.lower())
            if a >= 0:
                m = _KIND_AFTER.match(low, a + len(name))
                places.append(("unknown", name, a, m.end() if m else a + len(name)))
    if not (places or periods or dims or metrics) or not _only_fillers(low, places, periods, dims, metrics):
        return None
    if (metrics or dims) and not _CUE_RE.match(low):
        return None

    body = prev.rstrip(" ?.!")
    end_mark = prev[len(body):].strip() or "?"
    plow, pplaces, pperiods, pdims, pmetrics = _parts(body)
    if not (pplaces or pperiods or pdims or pmetrics):
        return None                     # the previous question was not about the data ("What is DCB?")
    edits: list[tuple[int, int, str]] = []
    tail = ""

    if places:
        phrase = _place_phrase(places) or new[places[0][2]:places[-1][3]]
        same_kind_list = len(pplaces) > 1 and len({k for k, *_ in pplaces}) == 1 and places[0][0] == pplaces[0][0]
        if len(places) == 1 and places[0][0] in _GROUPED and _GROUPED[places[0][0]].search(plow) and not same_kind_list:
            # "Top 5 zillas by collection" -> "and Kolar?": Kolar's own collection, not a ranking inside Kolar
            return _plain(new, body, places, periods, dims, metrics, pplaces, pperiods, pdims, pmetrics)
        if not pplaces:
            tail += " in " + phrase
        elif len(pplaces) > 1 and len({k for k, *_ in pplaces}) == 1 and places[0][0] == pplaces[0][0]:
            # a list of places of one kind ("compare Mysuru and Mandya"): the new one joins the list
            (_, _, a1, b1), (_, _, a2, b2) = pplaces[-2], pplaces[-1]
            if re.fullmatch(r"\s+and\s+", body[b1:a2]):
                edits.append((b1, a2, ", "))
            edits.append((b2, b2, " and " + phrase))
        else:
            # one place, or a chain (GP in taluk in zilla): the new place takes the first one's slot, the rest go
            _, _, a0, b0 = pplaces[0]
            edits.append((a0, b0, phrase))
            for _, _, a, b in pplaces[1:]:
                m = _CONNECT_BEFORE.search(body[:a])
                edits.append((m.start() if m else a, b, ""))

    if periods:
        said = [new[a:b] for a, b in periods]
        said = ["FY " + s if _BARE_FY.match(s) else s for s in said]
        if not pperiods:
            tail += " in " + " and ".join(said)
        elif len(pperiods) == len(said):
            edits += [(a, b, s) for (a, b), s in zip(pperiods, said)]
        elif len(pperiods) == 1:
            edits.append((*pperiods[0], " and ".join(said)))
        else:
            return None

    for kind in {k for k, _, _ in dims}:
        said = [new[a:b] for k, a, b in dims if k == kind]
        before = [(a, b) for k, a, b in pdims if k == kind]
        if not before:
            tail += " for " + " and ".join(said)
        elif len(before) == 1:
            edits.append((*before[0], " and ".join(said)))
        else:
            return None

    if metrics:
        if len(pmetrics) != 1:
            # the previous measure is not one phrase ("How many staff registrations were pending at the EO"): ask the
            # new measure plainly, for the place, period and head the conversation is about
            return _plain(new, body, places, periods, dims, metrics, pplaces, pperiods, pdims, pmetrics)
        edits.append((*pmetrics[0], new[metrics[0][0]:metrics[-1][1]]))

    out = body
    for a, b, text in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        out = out[:a] + text + out[b:]
    out = " ".join((out + tail).split()) + end_mark
    return out[0].upper() + out[1:]

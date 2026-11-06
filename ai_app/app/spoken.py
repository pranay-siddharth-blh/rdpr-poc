"""
What the voice says, and how a spoken question is cleaned up. No model call anywhere in this module.

  spoken_answer(question, answer, route)  -> 1-2 sentences for the ear (also the caption in the voice panel), built from
                                             the answer the pipeline already wrote and verified
  pronounce(text)                         -> the same text made speakable for TTS: FY / months / dates read naturally,
                                             acronyms spelled out (GP -> "G P", EO -> "E O"), rupees and percent in words
  clean_transcript(text)                  -> speech-to-text output -> the question the pipeline expects

Why deterministic (as in the KPCL voice instance, not a model rewrite as in the Meghalaya agent): every RDPR answer is
written by reviewed code from the query result, with a bold headline that already states the answer. Re-wording it
with a model would add a second round trip (1-3 s of silence) and a chance of a wrong spoken figure (the Meghalaya
model once said "3.06 lakh" for 30.6 lakh and needed a number guard). Here every spoken figure is the screen figure,
rounded the way an officer says it, and app/voice_guard.py checks that before anything is said.

Rules: the answer first (the headline); at most one supporting sentence that adds a new figure; lists cut to three
items; screen-only notes ("No year was named ...", caveats, "in the table") are not read; a long answer ends with
"The full details are on your screen."
"""
from __future__ import annotations

import re
from contextvars import ContextVar
from functools import lru_cache

MONTHS = {"jan": "January", "feb": "February", "mar": "March", "apr": "April", "may": "May", "jun": "June",
          "jul": "July", "aug": "August", "sep": "September", "oct": "October", "nov": "November", "dec": "December"}
_MONTH_LIST = list(MONTHS.values())

IDENTITY = ("I'm the Panchayat Raj data assistant. Ask me about any zilla, taluk or Gram Panchayat: revenue collection, "
            "book closure, scheme accounts, staff or salary bills, from April 2022 to September 2026.")
SCREEN_NOTE = "The full details are on your screen."
REPORT_NOTE = "The full details, and the report, are on your screen."
FILLERS = ["Let me check that.", "One moment, I'm pulling up the figures.", "Checking the records now."]

# Sentences that only make sense on screen, or that are caveats the officer can read there.
_SCREEN_ONLY = re.compile(
    r"\b(table below|in the table|below\b|chart|scroll|click|download|CSV|View report|"
    r"No (?:financial )?year was named|No zilla, taluk or GP was named|No month was named|"
    r"own total over its own base|not tilted by size|does not tilt|not affected by how many|"
    r"held at taluk level only|Salary-bill months run|Not Active'|synthetic|not official|"
    r"the latest complete year, is used|is used\.|Please check the spelling|you can write a GP)", re.I)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9'\"(₹•])")
_NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})+,\d{3}|\d+)(\.\d+)?(?![\w])")


def _plain(text: str) -> str:
    """Markdown and list marks out; whitespace collapsed."""
    t = re.sub(r"\*\*|__|`", "", text or "")
    t = re.sub(r"^\s*[•\-*]\s+", "", t, flags=re.M)
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text.strip()) if s.strip()]


def _dates(text: str) -> str:
    """30-Sep-2026 -> 30 September 2026;  2026-09-30 -> 30 September 2026;  MAR-2025 / Mar 2025 -> March 2025."""
    text = re.sub(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b",
                  lambda m: f"{int(m.group(3))} {_MONTH_LIST[int(m.group(2)) - 1]} {m.group(1)}"
                  if 1 <= int(m.group(2)) <= 12 else m.group(0), text)
    text = re.sub(r"\b(\d{1,2})-([A-Za-z]{3})-(\d{4})\b",
                  lambda m: f"{int(m.group(1))} {MONTHS.get(m.group(2).lower(), m.group(2))} {m.group(3)}", text)
    return re.sub(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?[- ](\d{4})\b",
                  lambda m: f"{MONTHS[m.group(1).lower()[:3]]} {m.group(2)}", text, flags=re.I)


def _trim(v: float, places: int) -> str:
    s = f"{v:,.{places}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def _count_words(v: float) -> str:
    """A big count the way an officer says it: 16,301,364 -> about 1.63 crore; 6,41,900 -> about 6.42 lakh."""
    if v >= 1e7:
        return f"about {_trim(v / 1e7, 2)} crore"
    if v >= 1e5:
        return f"about {_trim(v / 1e5, 2)} lakh"
    return _trim(v, 2)


# ₹124.30 crore / ₹11.85 lakh / ₹30,993 / ₹1,905.41 cr
_RUPEE = re.compile(r"₹\s?(\d[\d,]*(?:\.\d+)?)\s*(crore|cr\b|lakh)?", re.I)
# a bare big number (not part of a rupee figure or a date): 16,301,364 / 6,41,900
_BIG = re.compile(r"(?<![\w.,₹])(\d{1,3}(?:,\d{3}){2,}|\d{1,2}(?:,\d{2}){2,},\d{3})(\.\d+)?(?![\w,]|\.\d)")


def _speak_figures(text: str) -> str:
    """Rupees said as rupees, big counts said in lakh / crore, percent as a word. Only the last decimals change."""
    def rupee(m):
        v = float(m.group(1).replace(",", ""))
        scale = (m.group(2) or "").lower()
        if scale in ("crore", "cr"):
            return f"{_trim(v, 2)} crore rupees"
        if scale == "lakh":
            return f"{_trim(v, 2)} lakh rupees"
        if v >= 1e5:
            return _count_words(v) + " rupees"
        return f"{_trim(v, 2)} rupees"
    text = _RUPEE.sub(rupee, text)
    text = _BIG.sub(lambda m: _count_words(float((m.group(1) + (m.group(2) or "")).replace(",", ""))), text)
    text = re.sub(r"(\d)\s*%", r"\1 percent", text)
    return text


def _parentheses(text: str) -> str:
    """'(GP)' / '(%)' dropped; '(Badami taluk, Bagalkot zilla)' and '(+13.6%)' become comma clauses."""
    text = re.sub(r"\s*\((?:[A-Z]{1,5}|%)\)", "", text)
    return re.sub(r"\s*\(([^()]*)\)", r", \1,", text)


def _clean(sentence: str) -> str:
    s = _dates(_plain(sentence))
    s = re.sub(r"\s*→\s*", " to ", s)
    s = re.sub(r"\s+[—–]\s+", ", ", s)
    s = _parentheses(s)
    s = re.sub(r"'([A-Z][\w-]*)'", r"\1", s)
    s = re.sub(r"(?<=[a-z]) %", " percentage", s)                # "collection %" -> "collection percentage"
    s = re.sub(r"(?<![\w])\+(?=\d)", "up ", s)                  # "+13.6%" -> "up 13.6 percent"
    s = _speak_figures(s)
    s = re.sub(r"\s+([,.;:])", r"\1", s)
    s = re.sub(r",\s*(?=[,.;:!?])", "", s)                       # ", ." / ", ," left by the bracket rules
    s = re.sub(r"\s{2,}", " ", s).strip().rstrip(",;:")
    if s and s[-1] not in ".!?":
        s += "."
    return s


def _paragraphs(answer: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", answer or "") if p.strip()]


def _bullets(answer: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"^\s*[•\-]\s+(.+)$", answer or "", re.M)]


def _headline(answer: str) -> str:
    m = re.match(r"\s*\*\*(.+?)\*\*", answer or "", re.S)
    return m.group(1).strip() if m else ""


def _years_out(text: str) -> str:
    return re.sub(r"\b(?:FY ?)?(?:19|20)\d{2}(?:-\d{2})?\b|\b\d{1,2}[- ](?:[A-Za-z]{3,9})[- ]\d{4}\b|"
                  r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}\b", " ", text)


def _numbers(text: str) -> set[str]:
    return {a + b for a, b in _NUM.findall(_years_out(text))}


def _list_sentence(items: list[str], head: str) -> str:
    """Up to three list items; if the headline already named the first one, continue with 'followed by'."""
    items = [_plain(i).rstrip(".") for i in items]
    first_name = re.split(r"\s*[—–:]\s*|,", items[0])[0].strip()
    lead = ""
    if first_name and first_name.lower() in head.lower() and len(items) > 1:
        items, lead = items[1:3], "Followed by "
    else:
        items = items[:3]
    # one clause per item: "Hassan — 28.69% collected (₹43.51 crore of ...), 69.25% ..." -> "Hassan, 28.69% collected"
    items = [re.split(r"\s*\(|,\s(?=\d)", re.sub(r"\s*[—–]\s*", ", ", i))[0] for i in items]
    body = items[0] if len(items) == 1 else ", ".join(items[:-1]) + (" and " if lead else ", and ") + items[-1]
    return lead + body


_HEADLINE_ONLY = ("capability", "unknown_name", "llm_unavailable", "llm_error", "llm_declined", "llm_sql_failed",
                  "llm_mismatch", "llm_unverified")


def spoken_answer(question: str, answer: str, route: str, *, rows: int = 0, has_chart: bool = False,
                  has_report: bool = False) -> str:
    """1-2 sentences to say for `answer` (already verified and shown on screen)."""
    if route == "identity":
        return IDENTITY
    if route.startswith("small_talk:"):
        from app.small_talk import SPOKEN
        return SPOKEN.get(route.split(":", 1)[1], SPOKEN["greeting"])
    if not answer:
        return "Sorry, I couldn't answer that just now. Please ask again."
    head = _headline(answer)
    rest = re.sub(r"^\*\*\s*", "", answer[answer.find(head) + len(head):]) if head else answer
    if route == "glossary":                                       # "**DCB**: Demand, Collection and Balance register: ..."
        term, _, defn = _plain(answer).partition(":")
        first = re.split(r"(?<=[a-z\)]):\s|(?<=[.!?])\s", defn.strip())[0] if defn.strip() else term
        return _clean(f"{term.strip()} stands for {first}")
    if route in ("llm_unavailable", "llm_error"):
        return ("That question needs the language model, which isn't reachable right now. Single figures, "
                "definitions and the standard reports still work, so please try one of those, or ask again shortly.")
    if route == "unknown_name":
        return _clean(head) + " Please say the zilla, taluk or G P name again."
    is_sentence = bool(head) and head[-1] in ".!?"
    spoken: list[str] = []
    if head and head.endswith(":"):                              # a headline introducing bullets
        spoken.append(_clean(head.rstrip(":") + "."))
        spoken += [_clean(b) for b in _bullets(answer)[:2]]
    elif is_sentence:
        spoken.append(_clean(head))
    else:                                                        # a title (knowledge) or no bold headline
        paras = [p for p in _paragraphs(rest if head else answer) if not p.lstrip().startswith(("•", "-"))]
        if head and paras and rest.lstrip().startswith(":"):     # "**There are 2 GPs named Kota**: ..." is one sentence
            paras[0] = head + paras[0].lstrip()
        sents = [s for p in paras for s in _sentences(_plain(p)) if not _SCREEN_ONLY.search(s)]
        spoken += [_clean(s) for s in sents[:2]]
    if route.startswith(_HEADLINE_ONLY) or route.startswith("refused"):
        spoken = spoken[:1] if is_sentence else spoken[:2]
        if route == "capability":
            spoken.append("I can tell you about revenue collection, book closure, scheme accounts, staff and salary bills.")
    elif len(spoken) == 1 and is_sentence and len(_numbers(head)) < 3:
        # One supporting sentence (or up to three list items) that adds a figure the headline doesn't have.
        bl = _bullets(answer)
        head_nums = _numbers(head)
        names = [re.split(r"\s*[—–:·]\s*|,", _plain(b))[0].strip().lower() for b in bl]
        already = sum(1 for n in names[:3] if n and n in head.lower())
        busy_items = any(len(_numbers(re.split(r"\s*\(", _plain(b))[0])) > 2 for b in bl[:3])
        if bl and 2 <= len(bl) <= 12 and already < 2 and not busy_items and not _SCREEN_ONLY.search(bl[0]):
            spoken.append(_clean(_list_sentence(bl, head)))
        else:
            for p in _paragraphs(rest):
                if p.lstrip().startswith(("•", "-")):
                    continue
                for s in _sentences(_plain(p)):
                    nums = _numbers(s)
                    if _SCREEN_ONLY.search(s) or not nums or nums & head_nums or len(nums) > 4:
                        continue
                    spoken.append(_clean(s))
                    break
                if len(spoken) > 1:
                    break
    text = re.sub(r"\s*\n\s*", ". ", " ".join(spoken))
    text = re.sub(r"\.\s*\.", ".", text)
    if len(text.split()) > 70:                                   # keep it to what the ear can hold
        text = spoken[0]
    more_on_screen = rows > 1 or has_chart or (route in ("knowledge", "knowledge_fallback")
                                               and len(_plain(answer).split()) > len(text.split()) + 25)
    if more_on_screen:
        text += " " + (REPORT_NOTE if has_report else SCREEN_NOTE)
    return text.strip()


# ================================================================================================ transcripts
# What the clean-up was unsure about, for the "Did you mean ...?" confirmation (app/voice_guard.confirmation).
# Each note: {"kind": "name" | "year", "span": text in the cleaned question, "options": [most likely, other]}.
_NOTES: ContextVar[list | None] = ContextVar("voice_clean_notes", default=None)


def _note(kind: str, span: str, options: list[str]) -> None:
    notes = _NOTES.get()
    if notes is not None and len({o.lower() for o in options}) > 1:
        notes.append({"kind": kind, "span": span, "options": options})


_SPELLED = re.compile(r"\b(?:[A-Za-z][.\s]\s*){1,5}[A-Za-z]\b\.?")
_W1 = {w: i for i, w in enumerate(["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                                    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
                                    "eighteen", "nineteen"])}
_W10 = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_TWO = r"(?:(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[\s-]+(?:one|two|three|four|five|six|seven|eight|nine))?|" \
       r"ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)"


def _two_digits(words: str) -> int:
    parts = re.split(r"[\s-]+", words.lower().strip())
    return sum(_W10.get(p, 0) + _W1.get(p, 0) for p in parts)


def _spoken_years(t: str) -> str:
    """'two thousand and twenty three twenty four' / 'twenty twenty-three, twenty-four' / '2023 24' -> '2023-24'."""
    t = re.sub(rf"\btwo thousand(?: and)?[\s-]+({_TWO})\b", lambda m: str(2000 + _two_digits(m.group(1))), t, flags=re.I)
    t = re.sub(rf"\btwenty[\s-]+({_TWO})\b", lambda m: str(2000 + _two_digits(m.group(1))), t, flags=re.I)
    t = re.sub(rf"\b(20\d\d)[\s,]*(?:to|-|and)?[\s,]*({_TWO})\b", lambda m: f"{m.group(1)}-{_two_digits(m.group(2)):02d}", t,
               flags=re.I)
    t = re.sub(r"\b(20\d\d)\s*(?:to|-|/)?\s*(20)?(\d\d)\b(?!-)",
               lambda m: f"{m.group(1)}-{m.group(3)}" if int(m.group(3)) == (int(m.group(1)) + 1) % 100 else m.group(0), t)
    return t


def _phon(word: str) -> str:
    """A rough sound key for Indian place names as speech-to-text spells them: Belagavi / Belgavi, Davanagere /
    Davangere, Chikkamagaluru / Chikmagalur, Shivamogga / Shimoga-ish spellings collapse to near-identical keys."""
    s = word.lower()
    s = "i" + s[1:] if s.startswith("e") else s                  # Ekanahalli / Ikanahalli
    for a, b in (("th", "t"), ("dh", "d"), ("bh", "b"), ("gh", "g"), ("kh", "k"), ("sh", "s"), ("ph", "f"),
                 ("ck", "k"), ("ch", "\0"), ("c", "k"), ("\0", "ch"), ("w", "v"), ("z", "j"), ("ee", "i"), ("oo", "u"),
                 ("y", "i"), ("q", "k")):
        s = s.replace(a, b)                                     # "c" is a "k" in these names: "Cotaker" ~ Kotekar
    s = s.replace("h", "")
    return re.sub(r"(.)\1+", r"\1", s)


def _score(heard: str, name: str) -> float:
    """How alike a heard word and a real name are: the mean of the sound-key and the spelling similarity. The sound key
    alone over-rewards a dropped first letter ("Ekanahalli" is nearer "Kannali" than "Ikanahalli" by sound alone)."""
    import difflib
    a, b = heard.lower(), name.lower()
    return (difflib.SequenceMatcher(None, _phon(a), _phon(b)).ratio() + difflib.SequenceMatcher(None, a, b).ratio()) / 2


# Words that are never place names, so they are never "corrected" (the questions' own vocabulary).
_ORDINARY = set("""what was the how much many did does do in of for and to from by at on with which who when where is are
were was what's whats show give tell list all every each about me please compare between versus vs best worst highest
lowest top bottom trend monthly yearly annual average total overall report summary overview performance situation status
position picture scorecard rank ranking need attention lagging improve improved collection collections collected collect
demand demanded arrears arrear balance outstanding dues adjustment adjustments revenue tax taxes property properties fee
fees head heads mobile tower application residential commercial industrial religious government community number count
percentage percent rate efficiency book books closed closure close closing month year years financial fiscal quarter
scheme schemes receipts received expenditure spent spend spending account accounts grant grants fund funds staff
employees salary salaries bill bills paid payroll bank rejected registrations registration pending approved approval
approvals executive officer president presidents elected members member seats seat gram panchayat panchayats panchayath
zilla zillas district districts taluk taluks taluka state karnataka india rural development department data assistant
january february march april may june july august september october november december now today latest last current
currently this previous next first second third fourth crore lakh lakhs thousand rupees designation designations type
types category categories active inactive library librarian worker workers rehabilitation clerk operator water operator
collector cleaners attendant peon swachh bharat mission finance commission fifteenth fourteenth own resource resources
bapuji seva kendra statutory escrow village supply sanitation committee chief minister grama vikasa disabled physically
funds division urban rural south north complete completed full whole entire""".split())


@lru_cache(maxsize=1)
def _name_vocab() -> dict[str, str]:
    """Sound key -> the spelling the router knows, for every word of every zilla (and its aliases) and taluk name."""
    from app.semantic_layer import router_index
    ix = router_index()
    out: dict[str, str] = {}
    for aliases in list(ix.zillas.values()) + list(ix.taluks.values()):
        for alias in aliases:
            for w in re.findall(r"[a-z]+", alias.lower()):
                if len(w) >= 4 and w not in _ORDINARY:
                    out.setdefault(_phon(w), w)
    return out


def _place_of(word: str) -> str:
    from app.voice_guard import place_label
    return place_label(word)


def _ranked(heard: str, names) -> list[tuple[float, str]]:
    return sorted(((_score(heard, n), n) for n in names), reverse=True)


def _fix_names(t: str) -> str:
    """Respell zilla and taluk names the way the data knows them: 'Belgavi' -> 'belagavi', 'Davangere' ->
    'davanagere'. Exact sound-key match for any word; a close match (score >= 0.8, see _score) only for words of 5+
    letters that are not ordinary question words, and below 0.9 the officer is asked "Did you mean ...?" with the
    runner-up. GP names are matched only when the speaker says "GP" (see _anchored)."""
    vocab = _name_vocab()
    known = set(vocab.values())
    _anchor_names()
    names_any = set(_SPELLINGS["taluk"]) | set(_SPELLINGS["zilla"])
    gp_names = set(_SPELLINGS["gp"])
    words = re.findall(r"[A-Za-z]+|[^A-Za-z]+", t)
    out, i = [], 0
    while i < len(words):
        w = words[i]
        said_as_gp = w.lower() in gp_names and re.match(r"\s*(?:GPs?|gram|grama)\b", "".join(words[i + 1:i + 3]), re.I)
        if not w.isalpha() or len(w) < 4 or w.lower() in _ORDINARY or w.lower() in known or w.lower() in names_any or said_as_gp:
            out.append(w)
            i += 1
            continue
        # a name split in two by the transcriber: "Chikka magaluru", "Dakshina Kanada", "Kalbure Ragi"
        if i + 2 < len(words) and words[i + 1] == " " and words[i + 2].isalpha() and words[i + 2].lower() not in _ORDINARY:
            pair = w + words[i + 2]
            joined = _phon(pair)
            if joined in vocab:
                out.append(vocab[joined])
                i += 3
                continue
            top = _ranked(pair, known)[:2]
            if len(pair) >= 8 and top[0][0] >= 0.86 and _score(w, top[0][1]) < top[0][0]:
                out.append(top[0][1])
                if top[0][0] < 0.92 and top[1][0] >= 0.75 and _place_of(top[1][1]) != _place_of(top[0][1]):
                    _note("name", top[0][1], [top[0][1], top[1][1]])
                i += 3
                continue
        key = _phon(w)
        if key in vocab:
            out.append(vocab[key])
        elif len(w) >= 5:
            top = _ranked(w, known)
            score, best = top[0]
            if score >= 0.8:
                out.append(best)
                other = next((n for s, n in top[1:] if _place_of(n) != _place_of(best)), None)
                if other and score < 0.9 and _score(w, other) >= (0.55 if score < 0.8 else max(0.62, score - 0.08)):
                    _note("name", best, [best, other])
            else:
                out.append(w)
        else:
            out.append(w)
        i += 1
    return "".join(out)


def _repair_merged_years(t: str) -> str:
    """Speech-to-text merges "twenty twenty-three twenty-four" into "2020 to 24" / "2020-2024" / "2020-24", and
    "twenty twenty-two twenty-three" into "2020 even 23". The second year survives, so the FY is (second - 1)-(second).
    Applied only right after FY / financial year / fiscal year, or with the tell-tale "even" (a real range such as
    "from 2022 to 2024" is never touched)."""
    def fy(prefix: str, b: int) -> str:
        # The other reading, FY 2020-21, is before this data starts (April 2022), so there is nothing to confirm; the
        # place and year are read back with the answer.
        return f"{prefix}20{b - 1:02d}-{b:02d}"
    t = re.sub(r"\b((?:FY|financial year|fiscal year)\s*)2020\s*(?:to|-|–|even|and)\s*(?:20)?(2[2-7])\b(?!-)",
               lambda m: fy(m.group(1), int(m.group(2))), t, flags=re.I)
    t = re.sub(r"\b2020\s+even\s+(?:20)?(2[2-7])\b", lambda m: fy("", int(m.group(1))), t, flags=re.I)

    # Without "FY": "in twenty twenty-two twenty-three" heard as "in 2020 to 2023" (the "two" became "to"). Left alone
    # after "from" / "between" (a real range), unless a second year follows ("from 2020 to 2023 to 2025-26").
    def bare(m):
        before = t[:m.start()].rstrip().lower()
        after = t[m.end():]
        if re.search(r"\b(?:from|between|since)$", before) and not re.match(r"\s+(?:to|and)\s+20\d\d", after):
            return m.group(0)
        return fy("", int(m.group(1)))
    return re.sub(r"\b2020\s*(?:to|-|–)\s*(?:20)?(2[3-7])\b(?![-\d])", bare, t, flags=re.I)


# Mis-hearings of ordinary question words (Indian-English speakers, qwen3-asr), and the spoken forms of terms.
_PHRASES = [
    (r"\bgram(?:a|ma|me)?\s*panchay(?:at|ath|aat|et|it)s\b", "gram panchayats"),
    (r"\bgram(?:a|ma|me)?\s*panchay(?:at|ath|aat|et|it)\b", "gram panchayat"),
    (r"\bgrampanchayat\b", "gram panchayat"),
    (r"\b(?:zila|zilah|zillah|jilla|jila|zilha|zella|zillas?h)\b", "zilla"),
    (r"\b(?:zilas|jillas|jilas|zillahs)\b", "zillas"),
    (r"\b(?:talook|taluq|talukh|taaluk|thaluk|taluka|talluk)\b", "taluk"),
    (r"\b(?:talooks|taluqs|talukas|thaluks)\b", "taluks"),
    (r"\bper\s*cent\b", "percent"),
    (r"\b(?:lakhs|lacs|lac|laks)\b", "lakh"),
    (r"\bcrores\b", "crore"),
    (r"\b(?:executive\s+officer|e\.\s?o\.?)(?=\s|$|[?.,])", "EO"),
    (r"\bat\s+the\s+e\s?o\b", "at the EO"),
    (r"\bbook\s?closer\b", "book closure"),
    (r"\bbooks?\s+closer\b", "books closure"),
    (r"\bsalary\s+bill?s?\b", "salary bills"),
    (r"\bsalaries\s+bills?\b", "salary bills"),
    (r"\b(?:the\s+)?(first|second|third|fourth)\s+quarter\b", lambda m: "Q" + str(["first", "second", "third", "fourth"].index(m.group(1).lower()) + 1)),
    (r"\bquarter\s+(one|two|three|four|[1-4])\b", lambda m: "Q" + {"one": "1", "two": "2", "three": "3", "four": "4"}.get(m.group(1).lower(), m.group(1))),
    (r"\b(?:fifteenth|15th)\s+finance\s+commission\b", "Fifteen Finance Commission"),
    (r"\b(?:fourteenth|14th)\s+finance\s+commission\b", "Fourteen Finance Commission"),
    (r"\bswatch\s+bharat\b", "Swachh Bharat"),
    (r"\bmobile\s+towers?\s+tax\b", "mobile tower tax"),
    (r"\b(financial|fiscal)\s+year\s+(\d{2})\b(?![-\d])", r"FY\2"),
    (r"\b(?:financial|fiscal)\s+year\s+(20\d{2})\b(?![-\d])", r"FY \1"),
    (r"\bbangalore\b", "Bengaluru"),
    (r"\bba[bp]u?j(?:i|ee|y)\s+seva\b", "Bapuji Seva"),
    (r"\bquartal\b", "quarter"),
    (r"\b(?:panchayat\s*(?:tantra|untra|antra|tendra)|panchayatendra|pancha\s+tantra)\b", "Panchatantra"),
    (r"\b(?:m\.?\s?g\.?\s?n\.?\s?r\.?\s?e\.?\s?g\.?\s?a|m\.?\s?g\.?\s?n\.?\s?rega|mgn\s?rega|m\s?n\s?rega|mnrega)\b", "MGNREGA"),
    (r"(?<![\d.])(?<![\d.] )\bpercent\b(?!\s*age)", "percentage"),           # "collection percent Mandya" (no figure)
    (r"\bden(?=\s*[.?!]*\s*$)", "then"),                                     # "And Arkalgud taluk den."
    (r"\b(the|and|total)\s+areas\b(?=\s+(?:of|in|for)\b)", r"\1 arrears"),    # "What was the areas of Davanagere ..."
]


def _lexicon() -> dict[str, str]:
    """Place names as speech-to-text spells them -> the name the data knows: app/voice_lexicon.json, validated at load
    by app/voice_guard.lexicon() (an entry can never turn one real place into another)."""
    from app.voice_guard import lexicon
    return lexicon()["mishearings"]


_ORDINAL_DAYS = {w: i for i, w in enumerate(
    "zeroth first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth "
    "fifteenth sixteenth seventeenth eighteenth nineteenth twentieth".split())}
_ORDINAL_DAYS.update({"thirtieth": 30})
_MONTH_RE = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
_ORD_WORD = r"((?:twenty|thirty)[\s-]?)?(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|" \
            r"thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth|thirtieth|\d{1,2}(?:st|nd|rd|th))"


def _ordinal_day(tens: str | None, word: str) -> int:
    if word[:1].isdigit():
        return int(re.sub(r"\D", "", word))
    return (20 if tens and tens.lower().startswith("twenty") else 30 if tens else 0) + _ORDINAL_DAYS[word.lower()]


def _spoken_dates(t: str) -> str:
    """'twenty sixth January 2025' / 'January twenty-sixth, 2025' / 'June 1st 2023' -> '26 January 2025'."""
    t = re.sub(rf"\b{_ORD_WORD}\s+(?:of\s+)?{_MONTH_RE},?\s+(\d{{4}})\b",
               lambda m: f"{_ordinal_day(m.group(1), m.group(2))} {m.group(3)} {m.group(4)}", t, flags=re.I)
    return re.sub(rf"\b{_MONTH_RE}\s+(?:the\s+)?{_ORD_WORD},?\s+(\d{{4}})\b",
                  lambda m: f"{_ordinal_day(m.group(2), m.group(3))} {m.group(1)} {m.group(4)}", t, flags=re.I)


@lru_cache(maxsize=1)
def _anchor_names() -> list[tuple[re.Pattern, dict[str, str], str]]:
    """(anchor, {sound key: name}, kind): a word right before "zilla" / "district" can only be a zilla, before "taluk"
    only a taluk, before "GP" / "gram panchayat" only a GP. Built from the data's own names. _SPELLINGS[kind] holds
    every spelling (aliases, and multi-word names joined: "kithanahalli") -> name, for the scored match."""
    from app.semantic_layer import load_semantic_layer, router_index
    ix = router_index()
    ents = load_semantic_layer()["entities"]
    zillas = {}
    for name, aliases in ix.zillas.items():
        for a in [name.lower(), *aliases]:
            short = name.split(" (")[0]
            if " " not in a:
                zillas.setdefault(_phon(a), short)
            _SPELLINGS["zilla"].setdefault(a.replace(" ", ""), short if " " not in a or a in short.lower() else a.title())
    taluks = {}
    for name, aliases in ix.taluks.items():
        for a in [name.lower(), *aliases]:
            if " " not in a and a not in _ORDINARY:
                taluks.setdefault(_phon(a), name)
            if a not in _ORDINARY:
                _SPELLINGS["taluk"].setdefault(a.replace(" ", ""), name)
    gps = {}
    for g in ents["gps"]:
        n = g["name"]
        if " " not in n and len(n) >= 4:
            gps.setdefault(_phon(n), n)
        if len(n) >= 4 and n.lower() not in _ORDINARY:
            _SPELLINGS["gp"].setdefault(n.lower().replace(" ", ""), n)
    span = r"\b((?:[A-Za-z]+\s+){0,2}[A-Za-z]+)\s+"
    return [(re.compile(span + r"(?=(?:zilla|district|zilla panchayat)\b)", re.I), zillas, "zilla"),
            (re.compile(span + r"(?=(?:taluk|taluka)\b)", re.I), taluks, "taluk"),
            (re.compile(span + r"(?=(?:GP|gram panchayat|grama panchayat)\b)", re.I), gps, "gp")]


_GLUED_ZILLA = re.compile(r"\b([A-Za-z]{3,}?)((?:z|j|g|ch|l|s|v)?il{1,2}a)('?s)?\b", re.I)
_GLUED_TALUK = re.compile(r"\b([A-Za-z]{3,}?)(?:t|th|k)?a{0,2}\s*[?.,]?\s*(?:l+u+ke?|l+o+ke?|l+o+o+k|ta+lu+k)\b", re.I)
_GLUED_GP = re.compile(r"\b([A-Za-z]{3,}?)gram(?=\s+panchay)", re.I)


def _unglue(t: str) -> str:
    """The speech model sometimes runs a name into the word after it: "Masurujilla", "Ramangarajilla", "Badamitaaluk",
    "Kampleta luk", "Kaniyurugram Panchayat". Split it off again, but only when the front part sounds like a real name
    of that kind (score >= 0.7), so "gorilla" or "data look" are never touched."""
    _anchor_names()

    def like(stem: str, kind: str) -> bool:
        return stem.lower() not in _ORDINARY and _best_names(stem, kind, 1)[0][0] >= 0.7

    def z(m):
        # a stem that sounds like a zilla, or any stem before an unmistakable "zilla" / "jilla": split, so an unknown
        # name ("Sandjilla") reaches the router as "Sand zilla" and is asked about, never read as the whole state
        plain_suffix = m.group(2).lower() in ("zilla", "jilla", "zila", "jila")
        if (plain_suffix and m.group(1).lower() not in _ORDINARY) or like(m.group(1), "zilla"):
            return f"{m.group(1)} zilla" + ("'s" if m.group(3) else "")
        return m.group(0)

    def tk(m):
        return f"{m.group(1)} taluk" if like(m.group(1), "taluk") else m.group(0)
    t = _GLUED_ZILLA.sub(z, t)
    t = _GLUED_TALUK.sub(tk, t)
    t = _GLUED_GP.sub(lambda m: f"{m.group(1)} gram" if m.group(1).lower() not in _ORDINARY else m.group(0), t)
    return _GLUED_GP_LETTERS.sub(lambda m: f"{m.group(1)} GP" if m.group(1).lower() not in _ORDINARY else m.group(0), t)


_GLUED_GP_LETTERS = re.compile(r"\b([A-Za-z]{4,}?)gp\b", re.I)                # "Neludigp" -> "Neludi GP"
_GLUED_AND = re.compile(r"^(\s*)(?:and|an)([A-Za-z]{3,})(\s+[A-Za-z]+)?\b", re.I)


def _unglue_and(t: str) -> str:
    """A follow-up's "and" run into the name after it: "Antum guru." (and Tumakuru), "Andavad" (and Dharwad). Split
    off only when what is left sounds like a zilla or taluk (score >= 0.7, alone or joined with the next word)."""
    m = _GLUED_AND.match(t)
    first = (m.group(0).split() or [""])[0].lower() if m else ""
    if not m or first in _ORDINARY:
        return t
    _anchor_names()
    if any(first in _SPELLINGS[k] for k in _SPELLINGS):
        return t                                                 # a real name that starts with "an": Anekal, Annigeri
    whole = max(_best_names(first, k, 1)[0][0] for k in ("zilla", "taluk"))
    tries = [(m.group(2), m.end(2))] + ([(m.group(2) + m.group(3).strip(), m.end(3))] if m.group(3) else [])
    best = (whole, None, 0)                                      # split only when that sounds clearly more like a name
    for heard, end in tries:
        for kind in ("zilla", "taluk"):
            sc, name = _best_names(heard, kind, 1)[0]
            if sc >= 0.7 and sc > best[0] + 0.05:
                best = (sc, name, end)
    return t if best[1] is None else f"{m.group(1)}And {best[1]}{t[best[2]:]}"


def _gp_in_taluk(t: str) -> str:
    """"<GP> GP in <taluk> taluk": the GP can only be one of that taluk's GPs, so a misheard GP name is matched against
    those alone ("Kaniyuru GP in Beltangadi taluk" -> Kaniyooru, though a Kaniyuru exists elsewhere). Close (>= 0.65,
    clear of the runner-up): replaced; looser (>= 0.55): the two best are offered ("Did you mean ...?")."""
    from app.semantic_layer import router_index
    ix = router_index()
    taluks = {n.lower(): n for n in ix.taluks}

    def sub(m):
        taluk = taluks.get(m.group(3).strip().lower())
        if not taluk:
            return m.group(0)
        # the name is the words just before "GP", back to the first ordinary word ("... at the EO in | Kunduru GP")
        allw = m.group(1).split()
        words = []
        for w in reversed(allw):
            if w.lower() in _SPAN_LEAD or (words and w.lower() in _ORDINARY) or w.upper() in _KNOWN_ACRONYMS:
                break
            words.insert(0, w)
        if not words:
            return m.group(0)
        lead = m.group(1)[:len(m.group(1)) - len(" ".join(words))]
        here = {n: g[0]["name"] for n, gs in ix.gp_names.items() for g in [[x for x in gs if x["taluk"] == taluk]] if g}
        heard = "".join(words).lower()
        if " ".join(words).lower() in here or not here:
            return m.group(0)
        ranked = sorted(((_score(heard, n.replace(" ", "")), name) for n, name in here.items()), reverse=True)
        (s1, n1), (s2, n2) = ranked[0], ranked[1] if len(ranked) > 1 else (0.0, "")
        if s1 >= 0.65 and s1 - s2 >= 0.05:
            return f"{lead}{n1} {m.group(2)} in {taluk} taluk"
        if s1 >= 0.55 and n2:
            _note("name", " ".join(words), [n1, n2])
        return m.group(0)
    return _GP_IN_TALUK.sub(sub, t)


_GP_IN_TALUK = re.compile(r"\b((?:[A-Za-z]+\s+){0,3}[A-Za-z]+)\s+(GP|gram panchayat|grama panchayat)\s+in\s+([A-Za-z][A-Za-z ]*?)\s+taluk\b", re.I)


_SPELLINGS: dict[str, dict[str, str]] = {"zilla": {}, "taluk": {}, "gp": {}}


def _best_names(heard: str, kind: str, n: int = 2) -> list[tuple[float, str]]:
    """The n best (score, name) of a kind for a heard word (or joined words), distinct names."""
    spell = _SPELLINGS[kind]
    ranked = sorted(((_score(heard, s), name) for s, name in spell.items()), reverse=True)
    out, seen = [], set()
    for sc, name in ranked:
        if name not in seen:
            seen.add(name)
            out.append((sc, name))
            if len(out) == n:
                break
    return out


_SPAN_LEAD = {"of", "the", "in", "for", "at", "and", "an", "to", "from", "by", "on", "with", "is", "was", "what", "how", "much",
              "many", "did", "does", "do", "which", "vs", "versus", "compare", "show", "me", "give", "all", "total",
              "collection", "demand", "balance", "percentage", "outstanding", "arrears", "staff"}


def _anchored(t: str) -> str:
    """The words right before an anchor are matched only against names of that kind, so a looser match is safe:
    "Hasan zilla" -> Hassan, "Badaami taluk" -> Badami, "Jummanakati GP" -> Jummanakatti, "Nellu D gram panchayat"
    -> Nelludi (a name the speech model split). Scored on sound and spelling (_score). Close enough (zilla / taluk
    0.7, GP 0.78): replaced, and below 0.88 the officer confirms between the two best. Loose (0.6 up to that): not
    replaced, but the two best are offered ("Did you mean ...?"). Exact names and ordinary words are left alone."""
    for pat, keys, kind in _anchor_names():
        spell = _SPELLINGS[kind]
        need = 0.78 if kind == "gp" else 0.7                    # 6,099 GP names: stay stricter

        def sub(m):
            words = m.group(1).split()
            last_exact = words[-1].lower() in spell
            if words[-1].lower() in _ORDINARY and len(words) == 1:
                return m.group(0)
            best = None                                          # (score, start, name, runner-up, its score)
            for start in range(len(words) - 1, -1, -1):
                part = words[start:]
                if part[0].lower() in _SPAN_LEAD or (start < len(words) - 1 and part[0].lower() in _ORDINARY):
                    break
                heard = "".join(part)
                if len(heard) < 4 or (len(part) == 1 and heard.lower() in _ORDINARY):
                    continue
                if heard.lower() in spell and (len(part) > 1 or not last_exact or best is None):
                    if len(part) == 1:
                        best = (1.0, start, spell[heard.lower()], None, 0)
                        continue
                    return " ".join(words[:start] + [spell[heard.lower()]]) + " "
                if len(part) == 1 and _phon(heard) in keys:
                    best = (1.0, start, keys[_phon(heard)], None, 0)
                    continue
                top = _best_names(heard, kind)
                bonus = 0.0 if len(part) == 1 else 0.005         # on a tie the longer (joined) reading wins
                cand = (top[0][0] + bonus, start, top[0][1], top[1][1] if len(top) > 1 else None, top[1][0] if len(top) > 1 else 0)
                # a real short name ("Palli", "Shahpur") gives way only to a clearly better longer one
                if best is None or (cand[0] > best[0] if best[0] < 1.0 else cand[0] >= need + 0.02):
                    best = cand
            if best is None or best[0] < 0.6:
                return m.group(0)
            if best[0] >= 1.0:
                return " ".join(words[:best[1]] + [best[2]]) + " "
            score, start, name, other, other_score = best
            span = " ".join(words[start:])
            if score >= need:
                # ask when a real alternative is close, and always when the match itself is loose
                if score < 0.88 and other and other_score >= (0.55 if score < 0.8 else max(0.6, score - 0.08)):
                    _note("name", name, [name, other])
                return " ".join(words[:start] + [name]) + " "
            if other:                                            # loose: ask, don't guess
                _note("name", span, [name, other])
            return m.group(0)
        t = pat.sub(sub, t)
    return t


_FOLLOW_CUE = re.compile(r"^\s*(?:(?:ok|okay|so|now|then|also)[\s,]+)*(?:and|an|what about|how about|same for|now)\b", re.I)
_KIND_NEXT = re.compile(r"\s*(?:zillas?|districts?|taluks?|talukas?|gps?|grama?|panchayats?)\b", re.I)
_NOT_A_NAME = {"then", "also", "okay", "about", "same", "instead", "there", "well", "please", "that", "this", "those"}


def _follow_up_name(t: str) -> str:
    """A spoken follow-up names a place without "zilla" or "taluk" after it ("And Mondia." for "and Mandya?", "And book
    closure of Hawari." for Haveri), so nothing anchors the match. In a short follow-up (it opens with "and", "what
    about" ...) each run of one or two words that are neither question words nor known names is matched against the
    zillas and the taluks, and the kind word of the closer one is added, so _anchored then treats it like any anchored
    name: replaced when close, asked about when unsure, and an unknown name reaches the answer as "<name> zilla" (asked
    again, never answered for the whole state)."""
    if not _FOLLOW_CUE.match(t) or len(t.split()) > 10:
        return t
    _anchor_names()
    known = set(_SPELLINGS["zilla"]) | set(_SPELLINGS["taluk"]) | set(_SPELLINGS["gp"])

    def candidate(w: str) -> bool:
        lw = w.lower()
        return len(lw) >= 4 and lw not in _ORDINARY and lw not in _NOT_A_NAME and lw not in known

    toks = list(re.finditer(r"[A-Za-z]+", t))
    inserts = []
    i = 0
    while i < len(toks):
        if not candidate(toks[i].group(0)) or i == 0:
            i += 1
            continue
        j = i + 1 if i + 1 < len(toks) and candidate(toks[i + 1].group(0)) and t[toks[i].end():toks[i + 1].start()] == " " else i
        end = toks[j].end()
        if not _KIND_NEXT.match(t, end):
            heard = "".join(x.group(0) for x in toks[i:j + 1]).lower()
            z, tk = _best_names(heard, "zilla", 1)[0], _best_names(heard, "taluk", 1)[0]
            if max(z[0], tk[0]) >= 0.6:
                inserts.append((end, " zilla" if z[0] >= tk[0] else " taluk"))
        i = j + 1
    for pos, word in reversed(inserts):
        t = t[:pos] + word + t[pos:]
    return t


def _confusable_and_years(t: str) -> None:
    """Notes for a known confusable name heard on its own, and a single ambiguous year (FY 2024)."""
    from app.voice_guard import lexicon
    for c in lexicon()["confusable"]:
        unless = "|".join(map(re.escape, c.get("unless_followed_by", [])))
        for h in c["heard"]:
            m = re.search(rf"\b{re.escape(h)}\b(?!\s+(?:{unless})\b)" if unless else rf"\b{re.escape(h)}\b", t, re.I)
            if m:
                _note("name", m.group(0), list(c["options"]))
                return
    m = re.search(r"\bFY\s?(?:20)?(\d{2})\b(?![-\d])", t)
    if m and 23 <= int(m.group(1)) <= 27:
        yy = int(m.group(1))
        _note("year", m.group(0), [f"FY 20{yy - 1:02d}-{yy:02d}", f"FY 20{yy:02d}-{yy + 1:02d}"])


def clean_transcript_ex(text: str) -> tuple[str, list[dict]]:
    """clean_transcript plus what it was unsure about (see _note)."""
    token = _NOTES.set([])
    try:
        cleaned = clean_transcript(text)
        _confusable_and_years(cleaned)
        notes = _NOTES.get() or []
    finally:
        _NOTES.reset(token)
    return cleaned, notes


_KNOWN_ACRONYMS = {"GP", "GPS", "EO", "DCB", "PDO", "FY", "HRMS", "RDPR", "MIS", "SBM", "RGSA", "VWSC", "LGD", "ZP", "TP",
                   "SC", "ST", "ESCROW", "MGNREGA", "PMAY"}


def clean_transcript(text: str) -> str:
    """Speech-to-text output -> the question the pipeline expects. 'G.P.' / 'g p' -> 'GP'; spoken financial years ->
    '2023-24'; 'zila' -> 'zilla'; misheard zilla / taluk / GP names -> the data's names. Anything else is left as heard."""
    t = (text or "").strip()
    if not t:
        return ""
    t = _spoken_years(t)
    t = _repair_merged_years(t)
    t = _spoken_dates(t)
    for pat, rep in _PHRASES:
        t = re.sub(pat, rep, t, flags=re.I)

    def join(m):
        letters = re.sub(r"[^A-Za-z]", "", m.group(0)).upper()
        if letters in _KNOWN_ACRONYMS and len(letters) >= 2:
            return "GPs" if letters == "GPS" else letters
        return m.group(0)
    t = _SPELLED.sub(join, t)
    lex = _lexicon()
    t = re.sub(r"\b[A-Za-z]+\b", lambda m: lex.get(m.group(0).lower(), m.group(0)), t)
    t = _unglue(t)
    for pat, rep in _PHRASES[:6]:                               # "Masuru jilla" -> "Masuru zilla" after the split
        t = re.sub(pat, rep, t, flags=re.I)
    t = _unglue_and(t)
    t = _follow_up_name(t)
    t = _anchored(t)
    t = _gp_in_taluk(t)
    # "FY23-24", "FY 23 24", "financial year 23-24" -> "FY 2023-24" (only consecutive years)
    t = re.sub(r"\b(F\.?\s?Y\.?|financial year|fiscal year)\s*'?(\d{2})\s*(?:-|to|/|\s)\s*(\d{2})\b(?!-)",
               lambda m: (f"FY 20{m.group(2)}-{m.group(3)}" if int(m.group(3)) == (int(m.group(2)) + 1) % 100
                          else m.group(0)), t, flags=re.I)
    t = re.sub(r"\bF\.\s?Y\.?(?=\s|$)", "FY", t)
    t = _fix_names(t)
    return re.sub(r"\s{2,}", " ", t).strip()


# ================================================================================================ pronunciation
# Acronyms spelled out for TTS ("G P", "E O"); plural forms keep a spoken "s".
_SPELL_OUT = ["RDPR", "HRMS", "DCB", "PDO", "MIS", "LGD", "RGSA", "VWSC", "SBM", "GP", "EO", "ZP", "TP", "CSV", "AI", "SC", "ST"]
_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
         "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def _two(n: int) -> str:
    return _ONES[n] if n < 20 else _TENS[n // 10] + (f"-{_ONES[n % 10]}" if n % 10 else "")


def _year(y: int) -> str:
    """2024 -> twenty twenty-four; 2005 -> two thousand five."""
    if 2000 <= y <= 2009:
        return "two thousand" + (f" {_ONES[y - 2000]}" if y > 2000 else "")
    return f"{_two(y // 100)} {_two(y % 100)}"


def pronounce(text: str) -> str:
    """Make spoken text TTS-safe. Applied by /api/voice/speak* just before synthesis."""
    t = _dates(text)
    t = re.sub(r"\bFY\s*(\d{4})-(\d{2})\b",
               lambda m: f"financial year {_year(int(m.group(1)))}, {_two(int(m.group(2)))}", t)
    t = re.sub(r"(?<![\d,])\b(\d{4})-(\d{2})\b(?![\d-])", lambda m: f"{_year(int(m.group(1)))}, {_two(int(m.group(2)))}", t)
    t = re.sub(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})\b",
               lambda m: f"{m.group(1)} {_year(int(m.group(2)))}", t)
    t = re.sub(r"\bQ([1-4])\b", lambda m: "quarter " + _ONES[int(m.group(1))], t)
    # a year on its own: "calendar year 2025", "in 2024", "since 2022" (never a count such as "2,025 GPs")
    t = re.sub(r"\b(year|in|since|of|from|until|to|before|after)\s+((?:19|20)\d{2})\b(?![-\d]|[,.]\d)",
               lambda m: f"{m.group(1)} {_year(int(m.group(2)))}", t)
    t = _speak_figures(t) if "₹" in t or "%" in t else t
    t = re.sub(r"\bSC\s*/\s*ST\b", "S C and S T", t)
    t = re.sub(r"\bSBM-G\b", "S B M Gramin", t)
    t = re.sub(r"\b15th FC\b", "fifteenth Finance Commission", t)
    t = re.sub(r"\b14th FC\b", "fourteenth Finance Commission", t)
    for a in _SPELL_OUT:
        t = re.sub(rf"\b{a}s\b", " ".join(a) + "s", t)
        t = re.sub(rf"\b{a}\b", " ".join(a), t)
    t = t.replace("&", " and ")
    t = re.sub(r"\s/\s", " or ", t)
    t = re.sub(r"\s*→\s*", " to ", t)
    return re.sub(r"\s{2,}", " ", t).strip()

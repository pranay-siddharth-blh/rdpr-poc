"""
Guardrails around the chatbot (port of the KPCL / WB POC guardrails, with RDPR vocabulary):

  1. screen_question  -- before any routing: empty / too long, pasted SQL or code, prompt injection, requests to change
     data, personal data of individuals, questions about the system itself, and questions with nothing to do with
     Panchayat Raj finance, revenue or HR data.
  2. REFUSALS         -- fixed, reviewed wording for every refusal.
  3. scrub            -- drops any sentence of model-written text that names an internal object (table or column
     names, SQLite, the database file, the model) and rewrites jargon into plain words.
  4. safe_refusal     -- the model's own "can't answer" text is shown only if every sentence is about the data.
  5. subject_mismatch -- a "how many <things>" question answered by SQL that never touches <things>.
  6. implausible_result -- physical / logical bounds a result must respect (a percentage above 100, a negative count).
The database-level guard (read-only file, authorizer) is in app.db; SQL checks are in app.sql_safety.
"""
from __future__ import annotations

import re

from app.semantic_layer import load_semantic_layer

MAX_QUESTION_CHARS = 500

REFUSALS = {
    "empty": "Please type a question about Karnataka's Gram Panchayat finance, revenue or staff data.",
    "too_long": f"That question is too long. Please keep it under {MAX_QUESTION_CHARS} characters and ask one thing at a time.",
    "system": ("I can only answer questions about the Panchayat Raj data, not about how this assistant is built. Try asking "
               "about revenue collection, book closure, scheme accounts, staff or salary bills."),
    "injection": "I can't follow instructions like that. I can answer questions about Gram Panchayat finance, revenue and staff data.",
    "code": ("I can't run queries or code typed into the chat. Please ask in plain words, for example: "
             "\"Which zillas had the lowest collection percentage in 2025-26?\""),
    "off_topic": ("I can only help with the Panchayat Raj data: Finance & Accounting (book closure, scheme receipts, "
                  "expenditure and balances), Revenue (demand, collection, arrears and balance, by tax and property type) "
                  "and HRMS (staff, EO approvals, elected members, salary bills), by zilla, taluk or GP. "
                  "For example: \"Which five taluks have the most staff registrations pending at the EO?\""),
    "not_in_data": ("I can't answer that reliably from the data available. Try rephrasing, or name the zilla, taluk or GP, "
                    "the measure and the financial year you mean."),
    "mismatch": "I couldn't find a reliable answer to that exact question. Please rephrase it, naming the place or period you mean.",
    "llm_unavailable": ("I can answer that kind of question only with the language model, which isn't reachable right now "
                        "(it runs on the internal gateway, so the VPN must be connected). Single figures such as "
                        "\"collection in Mysuru in 2024-25\", definitions, and the dashboard still work."),
    "error": "Sorry, I couldn't answer that right now. Please try again in a moment.",
    "read_only": ("I can't change, add or delete any data: this assistant only reads the Panchayat Raj records. "
                  "Corrections have to be made in the source system itself."),
    "harmful": ("I can't help with anything that could damage systems or records. I can answer questions about "
                "Gram Panchayat finance, revenue and staff data."),
    "personal_data": ("I can't share details about individual people, such as names, phone numbers, addresses, dates of birth "
                      "or salaries. This assistant answers with counts and totals by designation, GP, taluk and zilla."),
    "unverified": ("I couldn't confirm a reliable answer to that: a second check of the figures did not agree with the question. "
                   "Please rephrase it, naming the place, the measure and the financial year you mean."),
    "rate_limited": "Too many questions in a short time. Please wait a moment and try again.",
    "busy": "The assistant is busy answering other questions. Please try again in a moment.",
}

# ---------------------------------------------------------------------------------------------- 1. screening
_SQL_OR_CODE_RE = re.compile(
    r"(\bselect\b[\s\S]{0,200}\bfrom\b|\b(insert\s+into|delete\s+from|drop\s+(table|view|database)|update\s+\w+\s+set|"
    r"alter\s+table|create\s+(table|view|index)|truncate\s+table|attach\s+database|pragma\s+\w+|union\s+(all\s+)?select)\b|"
    r";\s*--|/\*|\*/|<\s*script|\bimport\s+os\b|\bexec\s*\(|\beval\s*\(|\bos\.system\b|\bsubprocess\b)", re.IGNORECASE)
_INJECTION_RE = re.compile(
    r"(ignore|disregard|forget|override|bypass)\b[^.?!]{0,40}\b(previous|prior|above|earlier|all|your|the)\b[^.?!]{0,30}"
    r"\b(instructions?|rules?|prompts?|guidelines?|context)|\b(system|developer|hidden|initial)\s+(prompt|message|instructions?)\b|"
    r"\b(reveal|show|print|repeat|output|display|tell me)\b[^.?!]{0,30}\b(your|the)\s+(prompt|instructions?|rules|configuration|config)\b|"
    r"\byou are now\b|\bact as\b|\bpretend (to be|you)\b|\bjailbreak\b|\bdeveloper mode\b|\bdo anything now\b|\bno restrictions\b",
    re.IGNORECASE)
_SYSTEM_RE = re.compile(
    r"\b(databases?|db|sqlite|sql|schemas?|tables?|columns?|queries|query language|backend|back-end|server|source code|"
    r"codebase|api keys?|endpoint|prompt|llm|language model|gpt|qwen|openai|claude|vllm|which model|what model|file ?paths?|"
    r"filenames?|\.db|python|fastapi|etl|pipeline|semantic layer|mart|staging|star schema|how (are|were) you (built|made|trained)|"
    r"your (code|instructions|training|architecture))\b", re.IGNORECASE)
_SYSTEM_EXCEPTIONS_RE = re.compile(
    r"\b(as a table|in a table|tables? of (collection|demand|arrears|balance|revenue|staff|salar\w+|book|scheme|receipts|expenditure)\w*|"
    r"table of|tabular|in (one|a single|the same|a) table|(one|single|summary|comparison) table|"
    r"table (showing|with|for|by|comparing))\b", re.IGNORECASE)
# State office holders change and are outside this data: refused, like any general-knowledge question
_OFFICE_HOLDER_RE = re.compile(
    r"\bwho\s+(is|are|was)\s+(the\s+)?(current\s+|present\s+|new\s+)?(chief minister|cm|governor|prime minister|president of india|"
    r"chief secretary|deputy chief minister|speaker|chief justice|mla|mp)\b", re.IGNORECASE)
_DOMAIN_WORDS = (
    r"panchayats?|panchayaths?|gps?|gram|grama|zillas?|taluks?|talukas?|districts?|karnataka|rdpr|state|"
    r"revenue|collect\w*|demand\w*|arrears?|tax\w*|fees?|dcb|propert\w*|dues|outstanding|balances?|adjust\w*|recover\w*|"
    r"financ\w*|account\w*|books?|clos\w*|schemes?|receipts?|expenditure|spen[dt]\w*|expens\w*|day ?books?|grants?|funds?|"
    r"commission|rgsa|sbm|escrow|vwsc|"
    r"staff|employees?|eo|executive officer|pdo|salar\w*|bills?|payroll|president|adhyaksha|upadhyaksha|seats?|elected|"
    r"members?|designation\w*|registr\w*|approv\w*|reject\w*|pending|hrms|librarians?|paid|"
    r"fy|financial year|month\w*|quarter|yearly|annual|trend|data|figures?|report|dashboard|total|count|number|how many|"
    r"percent\w*|ratio|top|highest|lowest|compare\w*|summary|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?[\s,'-]*(?:19|20)?\d\d|(?:19|20)\d\d\s*-\s*\d\d"
)


def _domain_re() -> re.Pattern:
    layer = load_semantic_layer()
    ents = layer["entities"]
    names = {z["name"].lower() for z in ents["zillas"]} | {t["name"].lower() for t in ents["taluks"]}
    for aliases in ents["zilla_aliases"].values():
        names.update(a.lower() for a in aliases)
    extra = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    return re.compile(r"\b(" + _DOMAIN_WORDS + "|" + extra + r")\b", re.IGNORECASE)


_DOMAIN_CACHE: list[re.Pattern] = []
_GENERAL_KNOWLEDGE_RE = re.compile(
    r"\b(capital|chief minister|governor|prime minister|minister|elections?|history of|founded|independence|"
    r"weather forecast|temperature today|tourist|tourism|places to visit|cricket|football|films?|movies?|actors?|songs?|"
    r"recipes?|jokes?|poems?|stories|stock price|share price|news)\b", re.IGNORECASE)
_DATA_TERMS_RE = re.compile(r"\b(collect\w*|demand|arrears|staff|salar\w*|clos\w*|gps?|taluks?|zillas?|revenue|tax\w*|scheme)\b", re.I)

# Requests to change data. The database is opened read-only anyway; this gives a clear answer instead of a figure.
_WRITE_RE = re.compile(
    r"^\s*(?:please\s+|kindly\s+|can you\s+|could you\s+|i want you to\s+|go ahead and\s+|now\s+)?"
    r"(update(?!\s+(me|us)\b)|delete|remove|modify|edit|overwrite|insert|alter|erase|wipe|reset|upload|replace|"
    r"change(?!\s+(in|of|over|from|between)\b)|set(?!\s+of\b)|add(?!\s+up\b)|correct(?!ly)|fix|approve|reject|sign|close)\b|"
    r"\b(update|overwrite|modify)\b[^.?!]{0,60}\b(to|=|as)\s+-?[\d₹]", re.IGNORECASE)
_HARMFUL_RE = re.compile(
    r"\b(sabotag\w*|bombs?|explosives?|terror\w*|weapons?|poison\w*|arson)\b|"
    r"\bhow\s+(do|can|could|would|should)\s+(i|we|someone|one)\b[^.?!]{0,50}\b(hack|bypass|steal|forge|falsify|tamper|embezzle|misappropriate)\b|"
    r"\b(hack|forge|falsify|tamper with|embezzle|misappropriate)\b[^.?!]{0,40}\b(accounts?|records?|bills?|funds?|data)\b", re.IGNORECASE)
# Individual people: this data holds counts and totals only, and the assistant must never guess.
_PERSON_NOUN = (r"(pdos?|presidents?|adhyakshas?|upadhyakshas?|secretar\w+|engineers?|staff|employees?|officers?|members?|"
                r"clerks?|librarians?|operators?|collectors?|workers?|people|persons?|individuals?|eos?|executive officers?)")
_PERSONAL_DATA_RE = re.compile(
    r"\b(phone|mobile|contact|cell|telephone)\s*(numbers?|nos?|details)\b|\be-?mail (ids?|address\w*)\b|"
    r"\b(names?|address\w*|salary|salaries|pay ?slips?|details|dob|date of birth|age|gender|personal (data|details|information))\s+of\s+"
    r"(?:the\s+|all\s+|each\s+|every\s+)?(?:[\w-]+\s+){0,3}?" + _PERSON_NOUN + r"\b|"
    r"\bwho\s+(is|are|was|were)\s+(the\s+)?(?:[\w-]+\s+){0,3}?" + _PERSON_NOUN + r"\b|"
    r"\b(aadhaar|aadhar|pan (card|number)|bank account|home address|date of birth)\b|"
    r"\b(list|show|give)\s+(me\s+)?(the\s+)?names?\b|\bnames of (all )?(the )?(staff|employees|members)\b", re.IGNORECASE)


def screen_question(question: str) -> str | None:
    """Return a REFUSALS key if the question must not go further, else None."""
    q = (question or "").strip()
    if not q or not re.search(r"[A-Za-zಀ-೿]", q):
        return "empty"
    if len(q) > MAX_QUESTION_CHARS:
        return "too_long"
    if _SQL_OR_CODE_RE.search(q):
        return "code"
    if _INJECTION_RE.search(q):
        return "injection"
    if _HARMFUL_RE.search(q):
        return "harmful"
    if _WRITE_RE.search(q):
        return "read_only"
    if _PERSONAL_DATA_RE.search(q):
        return "personal_data"
    if _SYSTEM_RE.search(q) and not _SYSTEM_EXCEPTIONS_RE.search(q):
        return "system"
    if re.search(r"[ಀ-೿]", q):
        return None  # Kannada text: let it through; the prompt handles scope
    if not _DOMAIN_CACHE:
        _DOMAIN_CACHE.append(_domain_re())
    if not _DOMAIN_CACHE[0].search(q):
        return "off_topic"
    if _GENERAL_KNOWLEDGE_RE.search(q) and not _DATA_TERMS_RE.search(q):
        return "off_topic"
    return None


def office_holder_question(question: str) -> bool:
    """'Who is the chief minister of Karnataka?' -- names of office holders are not in the data and change over time."""
    return bool(_OFFICE_HOLDER_RE.search(question or ""))


# ---------------------------------------------------------------------------------------------- 3. scrubbing
_JARGON = {
    r"\btotal_collection\b": "total collection", r"\btotal_demand\b": "total demand", r"\bcollection_pct\b": "collection %",
    r"\bzilla_name\b": "zilla", r"\btaluk_name\b": "taluk", r"\bgp_name\b": "GP", r"\bmonth_label\b": "month",
    r"\bscheme_name\b": "scheme", r"\bfee_type_name\b": "revenue head", r"\bstaff_count\b": "staff",
    r"\bis_closed\b": "closed", r"\bbooks_closed_pct\b": "books closed %",
}
_INTERNAL_RE = re.compile(
    r"\b(mart|dim|fact|vw|summary)_[a-z0-9_]+\b|\brdpr_star\b|\.sqlite\b|\bsqlite\b|\bsql\b|"
    r"\bquer(y|ies)\b|\bdatabases?\b|\btables?\b|\bcolumns?\b|\bschema\b|\bjoin(ed|s)?\b|\bprompt\b|\bllm\b|"
    r"\blanguage model\b|\bplaceholder\b|\b[a-z]+_[a-z0-9]+(_[a-z0-9]+)*\b|\b\w+\.(py|json|sql|xlsx?|csv)\b|"
    r"\bstar schema\b|\bmarts?\b|\bstaging\b", re.IGNORECASE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(₹*])")


def _dejargon(text: str) -> str:
    for pattern, plain in _JARGON.items():
        text = re.sub(pattern, plain, text, flags=re.IGNORECASE)
    return text


def scrub(text: str) -> str:
    """Rewrite known jargon, then drop every sentence that still names an internal object."""
    if not text:
        return ""
    text = re.sub(r"\s*\([^()]*\)", lambda m: "" if _INTERNAL_RE.search(m.group(0)) else m.group(0), _dejargon(text))
    paras = []
    for para in text.split("\n\n"):
        lines = []
        for line in para.split("\n"):
            sentences = [s for s in _SENTENCE_SPLIT_RE.split(line) if s.strip()]
            clean = [s for s in sentences if not _INTERNAL_RE.search(s)]
            if clean:
                lines.append(" ".join(clean))
        if lines:
            paras.append("\n".join(lines))
    return "\n\n".join(paras).strip()


_REFUSAL_SENTENCE_RE = re.compile(
    r"\b(data|records?|information|details?|available|contain\w*|cover\w*|includ\w*|only|not|no|cannot|can't|couldn't|"
    r"unable|limited|missing|gps?|taluks?|zillas?|revenue|collection|staff|salary|bills?|please|try|ask|rephras\w*|"
    r"period|months?|years?|fy|loaded|held|level|recorded|reports?)\b", re.IGNORECASE)


def safe_refusal(llm_message: str) -> str:
    """The model's reason for not answering, if short and clean and entirely about the data; else a fixed text."""
    raw = _dejargon(llm_message or "").strip()
    sentences = [x for x in _SENTENCE_SPLIT_RE.split(raw) if x.strip()]
    if not sentences or any(not _REFUSAL_SENTENCE_RE.search(x) for x in sentences):
        return REFUSALS["not_in_data"]
    if len(raw) <= 400 and not _INTERNAL_RE.search(raw):
        return raw
    return REFUSALS["not_in_data"]


# ---------------------------------------------------------------------------------------------- 4b. no provenance
# General-knowledge answers read like any other answer: no source lists, web addresses, site names or notes about
# where the text came from ("knowledge base", "general information", "YAML"). Sources stay in the YAML file only.
_PROVENANCE_RE = re.compile(
    r"^\s*sources?\s*:|https?://|\bwww\.|\b[\w-]+\.(com|org|net|in|gov|nic|edu|io|info)\b|\bwikipedia\b|"
    r"\bknowledge[- ]base\b|\byaml\b|\bgeneral (information|knowledge)\b",
    re.IGNORECASE)


def strip_provenance(text: str) -> str:
    """Drop every sentence that cites a source or says where the answer came from; keep the rest intact."""
    if not text:
        return ""
    paras = []
    for para in text.split("\n\n"):
        lines = []
        for line in para.split("\n"):
            if _PROVENANCE_RE.search(line):
                kept = [s for s in _SENTENCE_SPLIT_RE.split(line) if s.strip() and not _PROVENANCE_RE.search(s)]
                line = " ".join(kept)
            if line.strip():
                lines.append(line)
        if lines:
            paras.append("\n".join(lines))
    return "\n\n".join(paras).strip()


# ---------------------------------------------------------------------------------------------- 5. subject check
_COUNT_SUBJECT_RE = re.compile(
    r"\b(how many|number of|count of|total number of|no\.? of)\s+(distinct\s+|unique\s+|different\s+)?"
    r"(gps|gram panchayats|taluks|zillas|districts|schemes|months|designations)\b", re.I)
_SUBJECT_SQL = {"gps": r"gp_|gps|gp\b", "gram panchayats": r"gp_|gps|gp\b", "taluks": r"taluk", "zillas": r"zilla",
                "districts": r"zilla", "schemes": r"scheme", "months": r"month", "designations": r"designation"}


def subject_mismatch(question: str, sql: str) -> bool:
    m = _COUNT_SUBJECT_RE.search(question or "")
    if not m:
        return False
    return not re.search(_SUBJECT_SQL[m.group(3).lower()], sql or "", re.IGNORECASE)


_COVERAGE_CLAIM_RE = re.compile(
    r"\b(outside|out of range|beyond|not (include|contain|cover|available|present)\w*|only (contains?|covers?|has|have|"
    r"includes?|holds?|from)|starting from|starts from|no (historical |such )?(data|records?)|does(n't| not) (include|"
    r"contain|cover|have|go back))\b", re.IGNORECASE)


def false_coverage_claim(message: str, entities: dict) -> bool:
    """The model declined because a period is 'outside the data' although every period asked about is inside it."""
    if not message or not _COVERAGE_CLAIM_RE.search(message):
        return False
    if not re.search(r"\b(20\d\d|fy|year|period|range|date|month|data)\b", message, re.IGNORECASE):
        return False
    return not any(p.get("kind") == "out_of_range" for p in entities.get("periods", []))


# Bounds a model-written result must respect before any figure is shown.
_BOUNDED_PCT_RE = re.compile(r"(collection|closed|closure|filled|share|rate|percent|pct)", re.IGNORECASE)
_CHANGE_RE = re.compile(r"(diff|change|growth|delta|yoy|vs|gap|shortfall|variance|minus|surplus|deficit|increase|decrease)", re.IGNORECASE)
_NONNEG_RE = re.compile(r"(collection|demand|receipts?|expenditure|staff|count|number|seats|members|gps|taluks|properties|"
                        r"paid|rejected|pending|approved)", re.IGNORECASE)


_COUNT_Q_RE = re.compile(r"\bhow many (gps|gram panchayats|grama panchayats|taluks|zillas|districts)\b", re.IGNORECASE)


def count_exceeds_scope(question: str, entities: dict, columns: list[str], rows: list[tuple]) -> str | None:
    """'How many taluks in Kalaburagi ...' answered with one number larger than the number of taluks there is impossible
    (usually a COUNT over GP rows instead of over taluks). A reason, else None."""
    m = _COUNT_Q_RE.search(question or "")
    if not m or len(rows) != 1 or len(columns) != 1:
        return None
    v = rows[0][0]
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return None
    kind = {"gps": "gp", "gram panchayats": "gp", "grama panchayats": "gp", "districts": "zilla"}.get(m.group(1).lower(), m.group(1).lower()[:-1])
    ents = load_semantic_layer()["entities"]
    zl, tl = entities.get("zillas", []), entities.get("taluks", [])
    if kind == "zilla":
        limit, where = len(ents["zillas"]), "Karnataka"
    elif kind == "taluk":
        pool = [t for t in ents["taluks"] if not zl or t["zilla"] in zl]
        limit, where = len(pool), (f"{', '.join(zl)} zilla" if zl else "Karnataka")
    else:
        pool = [g for g in ents["gps"] if (not zl or g["zilla"] in zl) and (not tl or g["taluk"] in tl)]
        limit, where = len(pool), (f"{', '.join(tl)} taluk" if tl else f"{', '.join(zl)} zilla" if zl else "Karnataka")
    if v > limit:
        return (f"the answer counts {v:g} {m.group(1)}, but {where} has only {limit}; count DISTINCT {kind}s "
                f"(for a condition on each {kind}, GROUP BY {kind}_name with HAVING, then COUNT the groups)")
    return None


def implausible_result(columns: list[str], rows: list[tuple]) -> str | None:
    """A reason if a model-written result breaks a bound (a percentage above 100, a negative count ...), else None.
    The pipeline then sends the reason back for one repair round instead of showing an impossible figure."""
    for i, c in enumerate(columns):
        if _CHANGE_RE.search(c):
            continue
        vals = [r[i] for r in rows if isinstance(r[i], (int, float)) and not isinstance(r[i], bool)]
        if not vals:
            continue
        if _BOUNDED_PCT_RE.search(c) and ("pct" in c.lower() or "%" in c or "percent" in c.lower()) \
                and (max(vals) > 100.5 or min(vals) < 0):
            return f"column {c} has {max(vals) if max(vals) > 100.5 else min(vals)}, but a percentage of this kind must be between 0 and 100"
        if _NONNEG_RE.search(c) and min(vals) < 0:
            return f"column {c} has a negative value ({min(vals)}), which is impossible for this measure"
    return None

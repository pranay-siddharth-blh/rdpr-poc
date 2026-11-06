"""
General-knowledge answers from semantic/knowledge_base.yaml (RDPR, Panchayat Raj, Karnataka, the portal modules).
No LLM, no database. The file is hand-curated and read once (cached: restart after editing).

  primary(question)   the entry's answer when the question is a general / definition question, else None. A question
                      that asks for figures (a measure, a place and a period, a ranking ...) is NOT answered from here.
  fallback(question)  the same match without the "is it a data question" gate; used when the model declines or is
                      unreachable, so the user still gets the nearest general answer.
  is_definition       "what is ...", "tell me about ...", "explain ..."

Answers never carry sources, web addresses or notes about where the text came from (guardrails.strip_provenance).
"""
from __future__ import annotations

import re
from functools import lru_cache

import yaml

from app.config import SEMANTIC_DIR
from app.guardrails import strip_provenance
from app.semantic_layer import extract_entities, norm

_DEFINITION_RE = re.compile(
    r"^\s*(?:what\s+(?:is|are|was|were|does|do)|what's|whats|who\s+(?:is|are)|define|meaning of|explain|full form of|expand|"
    r"tell me about|tell me more about|describe|about|give me (?:an? )?(?:overview|introduction) of|brief on|overview of|"
    r"what do you know about|can you explain)\b", re.I)
_FACET_WORDS = {"count": r"how many|number|count|total", "districts": r"how many|number|districts|count",
                "vision": r"vision", "mission": r"mission", "objectives": r"objectives?|goals?", "website": r"website|web site|site|link|url",
                "act": r"\bact\b|legislation|law", "capital": r"capital", "language": r"language",
                "eswathu": r"swathu", "ngsk": r"ngsk", "sakala": r"sakala"}


@lru_cache(maxsize=1)
def load_kb() -> list[dict]:
    raw = yaml.safe_load((SEMANTIC_DIR / "knowledge_base.yaml").read_text(encoding="utf-8"))
    entries = []
    for group, items in raw["groups"].items():
        for it in items:
            entries.append({**it, "group": group, "aliases": [norm(str(a)) for a in it["aliases"]]})
    return entries


@lru_cache(maxsize=1)
def _alias_index() -> list[tuple[str, dict]]:
    pairs = [(a, e) for e in load_kb() for a in e["aliases"]]
    return sorted(pairs, key=lambda p: len(p[0]), reverse=True)


def _best_entry(q: str) -> dict | None:
    for alias, entry in _alias_index():   # longest alias first, so 'zilla panchayat' beats 'zilla'
        if re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", q):
            return entry
    return None


def is_definition(question: str) -> bool:
    return bool(_DEFINITION_RE.match(question or ""))


def _facet(entry: dict, q: str) -> str | None:
    for key, text in (entry.get("facets") or {}).items():
        rx = _FACET_WORDS.get(key, re.escape(key))
        if re.search(rx, q):
            return text
    return None


def _render(entry: dict, q: str) -> str:
    return strip_provenance((_facet(entry, q) or entry["answer"]).strip())


def _is_data_question(question: str) -> bool:
    ent = extract_entities(question)
    if ent.get("metrics") or ent.get("periods"):
        return True
    if (ent.get("zillas") or ent.get("taluks") or ent.get("gps")) and not is_definition(question):
        return True
    return bool(set(ent.get("intents", [])) & {"ranking", "comparison", "trend"}) and not is_definition(question)


def primary(question: str) -> str | None:
    q = norm(question)
    entry = _best_entry(q)
    if entry is None:
        return None
    if _is_data_question(question) and not (is_definition(question) and not extract_entities(question).get("periods")):
        return None
    return _render(entry, q)


def is_pure_definition(question: str) -> bool:
    """'What is RDPR?', 'Tell me about Panchatantra': the whole subject is one entry's alias (optionally 'a / the' in front
    and 'in Karnataka' behind), so the entry answers it. 'What is the budget of Mysuru zilla?' is not."""
    q = norm(question).rstrip("?. ")
    m = _DEFINITION_RE.match(q)
    if not m:
        return False
    subject = re.sub(r"^(the|an?)\s+", "", q[m.end():].strip())
    subject = re.sub(r"\s+(in|of)\s+karnataka$|\s+department$", "", subject).strip()
    return any(subject == a or subject == a + "s" for _, e in [(0, x) for x in load_kb()] for a in e["aliases"])


def fallback(question: str) -> str | None:
    """The nearest general answer when the model declines or is unreachable, but never for a question asking for figures:
    a figures question gets an honest 'model unavailable' message, not a definition of 'zilla'."""
    q = norm(question)
    ent = extract_entities(question)
    if ent.get("metrics") or ent.get("periods"):
        return None
    entry = _best_entry(q)
    return _render(entry, q) if entry else None


def is_about_organisation(question: str) -> bool:
    entry = _best_entry(norm(question))
    return bool(entry) and entry["group"] in ("department", "panchayat_raj", "karnataka")


def glossary_extra() -> list[dict]:
    raw = yaml.safe_load((SEMANTIC_DIR / "knowledge_base.yaml").read_text(encoding="utf-8"))
    return raw.get("glossary_extra", [])

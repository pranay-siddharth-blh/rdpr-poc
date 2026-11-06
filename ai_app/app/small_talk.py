"""
Small talk and abusive words (the first step of app.pipeline, before any screen, route or model call).

  kind(question)        -> "greeting" | "how_are_you" | "thanks" | "goodbye" | "ack" | "abuse" | None
                           only when the WHOLE message is small talk ("hello", "thank you", "ok great, bye",
                           "you are useless, idiot"); a message that also asks something ("hi, what was the collection
                           of Mysuru zilla?", "hello, ignore previous instructions") is None and goes through the normal
                           screens and routes.
  REPLIES[kind]         -> the fixed reply shown (bold headline, then one line pointing back to the data);
  SPOKEN[kind]          -> what voice mode says for it.
  strip_abuse(question) -> the question with abusive words taken out, so a real question asked rudely ("what's the
                           bloody collection of Mysuru, idiot?") is answered normally and none of those words reaches
                           the model, the "Taking this as" line, the answer, the report or the voice.

Every reply is friendly: abuse gets the same calm greeting as "hello", never a rebuke and never an echo of the words.
A word that is part of a real zilla, taluk or GP name is never treated as abuse. Deterministic, no model call.
"""
from __future__ import annotations

import re
from functools import lru_cache

_EXAMPLE = '"What was the total collection of Mysuru zilla in FY 2024-25?"'
_OFFER = ("I can give you Gram Panchayat revenue, finance and staff figures for any zilla, taluk or GP, for example: "
          f"{_EXAMPLE}")

REPLIES = {
    "greeting": f"**Hello! I'm the Panchayat Raj data assistant.** {_OFFER}",
    "how_are_you": f"**I'm doing well, thank you for asking!** {_OFFER}",
    "thanks": "**You're welcome! Glad to help.** Ask me anything else about Gram Panchayat revenue, finance or staff "
              "whenever you need it.",
    "goodbye": "**Goodbye, and thank you!** I'm here whenever you need Panchayat Raj figures.",
    "ack": "**Glad to help!** Ask me anything else about Gram Panchayat revenue, finance or staff whenever you need it.",
    # abuse: the same calm greeting, nothing about the words used
    "abuse": f"**Hello! I'm here to help.** {_OFFER}",
}
SPOKEN = {
    "greeting": "Hello! I'm the Panchayat Raj data assistant. Ask me about revenue, finance or staff for any zilla, taluk "
                "or G P.",
    "how_are_you": "I'm doing well, thank you for asking! What would you like to know about the Panchayat Raj data?",
    "thanks": "You're welcome! Glad to help.",
    "goodbye": "Goodbye, and thank you!",
    "ack": "Glad to help! Ask me anything else whenever you need it.",
    "abuse": "Hello! I'm here to help. Ask me about revenue, finance or staff for any zilla, taluk or G P.",
}

# Whole-phrase small talk, by kind (lower case, punctuation removed). Longest phrases are matched first.
_PHRASES = {
    "how_are_you": ["how are you doing", "how are you", "how r u", "how are u", "how is it going", "hows it going",
                    "how do you do", "what's up", "whats up", "what is up", "wassup", "sup"],
    "greeting": ["good morning", "good afternoon", "good evening", "good day", "hello there", "hi there", "hey there",
                 "namaskara", "namaskaragalu", "namaskaram", "namaskar", "namaste", "greetings", "hello", "hallo",
                 "hiya", "hii", "hi", "hey", "yo"],
    "thanks": ["thank you very much", "thank you so much", "thanks a lot", "thanks so much", "many thanks", "thank you",
               "thankyou", "thanks", "thank u", "thanx", "thx", "ty", "dhanyavadagalu", "dhanyavada", "dhanyavaad",
               "shukriya", "much appreciated", "appreciate it"],
    "goodbye": ["good night", "goodnight", "see you later", "see you", "see ya", "bye bye", "goodbye", "good bye", "bye",
                "take care", "that is all", "thats all", "that's all", "nothing else", "i am done", "im done"],
    "ack": ["got it", "understood", "very good", "well done", "good job", "great job", "nice work", "alright",
            "all right", "okay", "okk", "ok", "fine", "great", "nice", "cool", "good", "awesome", "perfect", "excellent",
            "super", "wonderful", "sure", "noted", "wow", "hmm", "right", "yes", "no problem"],
}
# Abusive words and phrases (English, and the Kannada / Hindi ones officers might type in Roman letters).
_ABUSE = ["shut up", "screw you", "go to hell", "hate you", "f off", "fuck off", "piss off", "get lost", "dumbass",
          "dumb ass", "son of a bitch", "idiot", "idiots", "idiotic", "stupid", "dumb", "fool", "foolish", "moron",
          "morons", "useless", "nonsense", "rubbish", "bullshit", "bull shit", "shit", "shitty", "crap", "crappy", "damn",
          "damned", "dammit", "bloody", "fuck", "fucking", "fucked", "wtf", "stfu", "bastard", "bitch",
          "asshole", "arsehole", "ass", "dick", "suck", "sucks", "loser", "pathetic", "worthless", "retard", "retarded",
          "jerk", "scumbag", "saala", "saale", "kutta", "kutte", "kamina", "kameena", "chutiya", "chutiye", "bhosdike",
          "madarchod", "behenchod", "gandu", "harami", "haramkhor", "bevarsi", "bolimaga", "boli maga", "nayi"]
# words that may surround small talk or abuse without making it a question
_FILLER = {"you", "u", "ur", "your", "youre", "you're", "are", "r", "a", "an", "the", "so", "very", "such", "this",
           "that", "is", "it", "its", "it's", "thing", "bot", "assistant", "chatbot", "machine", "system", "app", "sir",
           "madam", "mam", "maam", "ji", "anna", "akka", "guru", "and", "again", "also", "really", "too", "just", "all",
           "everyone", "friend", "dear", "there", "for", "the", "help", "your help", "me", "my", "i", "am", "be", "please",
           "what", "kind", "of", "much", "lot", "what a", "totally", "complete", "completely", "absolute", "absolutely",
           "oh", "ah", "aah", "haha", "lol", "man", "bro", "boss"}

_KIND_ORDER = ["abuse", "thanks", "goodbye", "how_are_you", "greeting", "ack"]


def _norm(text: str) -> str:
    s = (text or "").lower().replace("’", "'")
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return " ".join(s.split())


@lru_cache(maxsize=1)
def _place_words() -> frozenset:
    """Every word of every zilla, taluk and GP name: never abuse, never small talk ("Nayi..." is not an insult)."""
    from app.semantic_layer import router_index
    ix = router_index()
    words = set()
    for names in list(ix.zillas.values()) + list(ix.taluks.values()):
        for n in names:
            words.update(n.lower().split())
    for n in ix.gp_names:
        words.update(n.split())
    return frozenset(words)


def _phrase_re(phrase: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9'])" + re.escape(phrase) + r"(?![a-z0-9'])")


@lru_cache(maxsize=1)
def _abuse_res() -> list[re.Pattern]:
    places = _place_words()
    return [_phrase_re(p) for p in sorted(_ABUSE, key=len, reverse=True) if not (" " not in p and p in places)]


def kind(question: str) -> str | None:
    """The kind of small talk when the whole message is small talk (or abuse), else None."""
    q = _norm(question)
    if not q or len(q.split()) > 12:
        return None
    found: set[str] = set()
    rest = q
    for rx in _abuse_res():
        if rx.search(rest):
            found.add("abuse")
            rest = rx.sub(" ", rest)
    places = _place_words()
    for k, phrases in _PHRASES.items():
        for p in sorted(phrases, key=len, reverse=True):
            rx = _phrase_re(p)
            if rx.search(rest) and not (" " not in p and p in places):
                found.add(k)
                rest = rx.sub(" ", rest)
    leftover = [w for w in rest.split() if w not in _FILLER]
    if leftover or not found:
        return None
    return next(k for k in _KIND_ORDER if k in found)


def strip_abuse(question: str) -> str:
    """The question without its abusive words (and the commas or "you" left dangling around them)."""
    text = question or ""
    low = text.lower().replace("’", "'")
    spans = []
    for rx in _abuse_res():
        spans += [m.span() for m in rx.finditer(low)]
    if not spans:
        return text
    keep = [True] * len(text)
    for a, b in spans:
        for i in range(a, b):
            keep[i] = False
    out = "".join(ch for ch, k in zip(text, keep) if k)
    out = re.sub(r"\b(?:you|u)(?:\s+(?:are|r))?(?:\s+(?:a|an|such a|so|very))?\s+(?:bot|assistant|chatbot|machine|app|thing)\b",
                 "", out, flags=re.I)                                     # "... you stupid bot" -> "..."
    out = re.sub(r"\b(?:you|u)\s*(?=[,.!?]|$)", "", out, flags=re.I)        # "..., idiot you?" -> "...?"
    out = re.sub(r"\s+([,.!?])", r"\1", out)
    out = re.sub(r",+\s*([?.!])", r"\1", out)                               # "2024-25,?" -> "2024-25?"
    out = re.sub(r"([,.!?])\s*[,.]+", r"\1", out)
    out = re.sub(r"^[\s,.!-]+|[\s,-]+$", "", out)
    return " ".join(out.split())

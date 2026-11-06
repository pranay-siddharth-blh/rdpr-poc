"""
Voice guardrails. Everything here sits around the unchanged question pipeline (ported from the KPCL voice instance,
which built them on the Meghalaya voice agent, and adapted to RDPR's places, periods and units):

  transcript checks   language (English / Kannada script only), length (seconds of audio, characters of text),
                      recordings without real speech (fan, typing, a cough, a chime), fragments, repeats (the same
                      question twice within a few seconds from one session), the misheard-names list
                      (voice_lexicon.json, validated), and the "Did you mean ...?" confirmation for anything the clean-up
                      was unsure about (a loose name match, a repaired year, a single ambiguous year)
  spoken answer rules read back the place and period first; ask again (with what was heard) instead of a flat refusal;
                      speak a model-written answer only if the second check passed; every spoken figure must be a screen
                      figure and carry its unit, or the voice says "the figures are on your screen" instead
  health              the speech services, checked at most every two minutes
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import re
import struct
import time
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

import httpx

from app.config import AI_DIR, settings

_log = logging.getLogger(__name__)
LEXICON_PATH = Path(__file__).resolve().parent / "voice_lexicon.json"
MISHEARINGS_LOG = AI_DIR / "logs" / "voice_mishearings.jsonl"


# ================================================================================================ misheard names
@lru_cache(maxsize=1)
def _place_words() -> set[str]:
    """Every word of every zilla name / alias and taluk name (what a lexicon entry may mean, and may never be)."""
    from app.semantic_layer import router_index
    ix = router_index()
    return {w for aliases in list(ix.zillas.values()) + list(ix.taluks.values()) for a in aliases
            for w in re.findall(r"[a-z]+", a.lower())}


@lru_cache(maxsize=1)
def lexicon() -> dict:
    """{'mishearings': {heard: means}, 'confusable': [...], 'rejected': [(entry, why)]} -- invalid entries are dropped
    (and listed), so a careless addition can never turn a real place name into another one."""
    from app.spoken import _ORDINARY, _name_vocab, _phon
    raw = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
    vocab = _name_vocab()                              # sound key -> name word the data knows
    known = _place_words() - _ORDINARY
    out, rejected = {}, []
    for e in raw.get("mishearings", []):
        heard, means = str(e.get("heard", "")).strip().lower(), str(e.get("means", "")).strip()
        why = None
        if not re.fullmatch(r"[a-z]{3,30}", heard):
            why = "heard must be one word of letters"
        elif heard in known or _phon(heard) in vocab:
            why = "heard is (or sounds exactly like) a real zilla or taluk name"
        elif heard in _ORDINARY:
            why = "heard is an ordinary question word"
        elif not means or means.split()[0].lower() not in _place_words():
            why = "means is not a name the data knows"
        elif not e.get("reviewed_by"):
            why = "not reviewed"
        if why:
            rejected.append((e, why))
            _log.warning("voice_lexicon.json: ignoring %r -> %r: %s", heard, means, why)
            continue
        out[heard] = means
    confusable = [c for c in raw.get("confusable", []) if c.get("reviewed_by")]
    return {"mishearings": out, "confusable": confusable, "rejected": rejected}


def record_mishearing(entry: dict) -> None:
    """Text only (never audio), and only when VOICE_COLLECT_MISHEARINGS is on (with the officers' consent)."""
    if not settings.voice_collect_mishearings:
        return
    try:
        MISHEARINGS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with MISHEARINGS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **entry}, ensure_ascii=False) + "\n")
    except OSError as exc:
        _log.warning("could not record a mishearing: %s", exc)


# ================================================================================================ transcript checks
def wav_seconds(audio: bytes) -> float | None:
    """Duration of a PCM WAV from its header (None if it isn't one)."""
    if len(audio) < 44 or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        return None
    pos, rate, block = 12, None, None
    while pos + 8 <= len(audio):
        cid, size = audio[pos:pos + 4], struct.unpack("<I", audio[pos + 4:pos + 8])[0]
        if cid == b"fmt " and pos + 24 <= len(audio):
            _fmt, _ch, rate, _bps, block = struct.unpack("<HHIIH", audio[pos + 8:pos + 22])
        elif cid == b"data":
            n = min(size, len(audio) - pos - 8)
            return n / (rate * block) if rate and block else None
        pos += 8 + size + (size & 1)
    return None


_OTHER_SCRIPT = re.compile(r"[^\x00-\u024f\u0c80-\u0cff\u2000-\u206f\u20b9\s\d.,'\u2019\"?!:;()\-\u2013/%&]")


def voiced_seconds(audio: bytes) -> float | None:
    """Seconds of a 16-bit PCM WAV clearly louder than its own background (20 ms frames over 2.5x the quietest tenth,
    and over an absolute floor). Office noise, a fan, a chime or a key press stays well under 0.35 s; a spoken question
    is over a second. None if the body is not a PCM WAV (then the speech model decides alone)."""
    try:
        import wave
        import numpy as np
        with wave.open(io.BytesIO(audio)) as w:
            if w.getsampwidth() != 2:
                return None
            rate, ch, raw = w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())
        x = np.frombuffer(raw[: len(raw) // (2 * ch) * 2 * ch], dtype="<i2").astype(np.float32) / 32768.0
        if ch > 1:
            x = x.reshape(-1, ch).mean(axis=1)
        n = max(1, int(rate * 0.02))
        frames = x[: len(x) // n * n].reshape(-1, n)
        if not len(frames):
            return 0.0
        rms = np.sqrt((frames ** 2).mean(axis=1))
        floor = float(np.percentile(rms, 10))
        return float((rms > max(2.5 * floor, 0.006)).sum() * n / rate)
    except Exception:  # noqa: BLE001
        return None


MIN_VOICED_SECONDS = 0.35


def too_short(cleaned: str, voiced: float | None, context_words: set[str]) -> bool:
    """A transcript that is not a question: one word ("GP", "Mysuru"), or two or three words that are all from the
    speech model's own hint paragraph out of under a second of speech -- what the model writes for noise."""
    words = re.findall(r"[a-z0-9']+", cleaned.lower())
    if len(words) <= 1:
        return True
    return len(words) <= 3 and voiced is not None and voiced < 1.0 and all(w in context_words for w in words)


def language_ok(text: str) -> bool:
    """English (Latin script) or Kannada script. A transcript mostly in another script (the model hearing noise as
    Chinese, or a question in another language) is dropped and the officer told so."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    other = len(_OTHER_SCRIPT.findall("".join(letters)))
    return other / len(letters) < 0.3


class RepeatGuard:
    """The same question from the same session within `window` seconds is a double-send or an echo: answer once."""

    def __init__(self, window: float = 4.0, max_sessions: int = 5000):
        self.window, self.max = window, max_sessions
        self.last: OrderedDict[str, tuple[str, float]] = OrderedDict()

    def seen(self, session: str, text: str) -> bool:
        key = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
        now = time.monotonic()
        prev = self.last.get(session)
        self.last[session] = (key, now)
        self.last.move_to_end(session)
        while len(self.last) > self.max:
            self.last.popitem(last=False)
        return bool(key) and prev is not None and prev[0] == key and now - prev[1] < self.window


repeats = RepeatGuard()


# ================================================================================================ "Did you mean ...?"
@lru_cache(maxsize=1)
def _word_to_place() -> dict[str, str]:
    """A zilla / taluk / GP name (or alias) -> how to say that place in a question ("Hassan zilla", "Badami taluk")."""
    from app.semantic_layer import load_semantic_layer, router_index
    ix = router_index()
    out: dict[str, str] = {}
    for name, aliases in ix.zillas.items():
        for a in [name.lower(), *aliases]:
            out.setdefault(a, f"{name} zilla")
    for name, aliases in ix.taluks.items():
        for a in [name.lower(), *aliases]:
            out.setdefault(a, f"{name} taluk")
    for g in load_semantic_layer()["entities"]["gps"]:
        out.setdefault(g["name"].lower(), f"{g['name']} GP")
    return out


def place_label(word: str) -> str:
    return _word_to_place().get(word.lower(), word)


def confirmation(cleaned: str, notes: list[dict]) -> dict | None:
    """The one question to ask before answering, from the clean-up's notes: {'prompt', 'reason', 'options': [{'label',
    'question'}]}, the most likely option first. None when nothing was uncertain."""
    for n in notes:
        span = n.get("span", "")
        if not span or not re.search(rf"(?<![\w-]){re.escape(span)}(?![\w-])", cleaned, re.I):
            continue
        options, seen = [], set()
        for opt in n["options"]:
            label = place_label(opt) if n["kind"] == "name" else (opt if opt.upper().startswith("FY") else f"FY {opt}")
            if label.lower() in seen:
                continue
            seen.add(label.lower())
            q = cleaned if opt.lower() == span.lower() else re.sub(rf"(?<![\w-]){re.escape(span)}(?![\w-])", opt, cleaned,
                                                                   count=1, flags=re.I)
            options.append({"label": label, "question": q})
        if len(options) >= 2:
            return {"prompt": f"Did you mean {options[0]['label']}, or {options[1]['label']}?", "reason": n["kind"],
                    "options": options[:2]}
    return None


# ================================================================================================ spoken answer rules
def readback(question: str, answer: str, spoken: str = "") -> str:
    """'For Hassan zilla, FY 2024-25: ' -- the place and period the answer is about, said first so a misheard place or
    year is caught by ear. Empty when the question names neither, or when the spoken answer already says both."""
    from app.semantic_layer import extract_entities
    e = extract_entities(question)
    places: list[str] = []
    places += [f"{g['name']} GP" for g in (e.get("gps") or [])[:2] if isinstance(g, dict) and g.get("name")]
    places += [f"{t} taluk" for t in (e.get("taluks") or [])[:2]]
    places += [f"{z} zilla" for z in (e.get("zillas") or [])[:2]]
    if not places and e.get("scope") == "state":
        places.append("all of Karnataka")
    period = ""
    ps = [p for p in e.get("periods", []) if p.get("kind") != "out_of_range"]
    if ps:
        period = " and ".join(re.sub(r"\s*\(April to September 2026\)", ", so far", p["label"]) for p in ps[:2])
    else:
        m = re.search(r"No (?:financial )?year was named, so (?:this uses )?(FY \d{4}-\d{2})", answer or "")
        if m:
            period = f"{m.group(1)}, the latest full year"
    from app.spoken import _dates
    period = _dates(period)
    if not places and not period:
        return ""
    # Already said: the headline names every place and the period ("Total collection for Hassan zilla in FY 2024-25
    # was ..."), so a read-back would only repeat it.
    said = (spoken or "").lower()
    base = lambda p: re.sub(r"\s+(?:zilla|taluk|GP)$", "", p.split(" (")[0]).lower()  # noqa: E731
    places_said = all((("karnataka" in said or "zillas" in said) if p == "all of Karnataka" else base(p) in said)
                      for p in places)
    periods_said = all(p.split(",")[0].strip().lower() in said for p in period.split(" and ")) if period else True
    if said and places_said and periods_said:
        return ""
    if not places:
        return f"For {period}: "
    place = " and ".join(places)
    return f"For {place}, {period}: " if period else f"For {place}: "


ASK_AGAIN_ROUTES = ("unknown_name", "llm_unverified", "llm_sql_failed", "llm_declined", "llm_mismatch",
                    "refused:off_topic", "refused:empty")


def ask_again(question: str, route: str) -> str | None:
    """Instead of a flat refusal: say what was heard and ask once more."""
    if not route.startswith(ASK_AGAIN_ROUTES):
        return None
    heard = re.sub(r"\s+", " ", question).strip().rstrip("?.!")[:160]
    if route.startswith("unknown_name"):
        return f"I heard: {heard}. I don't recognise that zilla, taluk or G P. Could you say the name again?"
    if route.startswith("refused:"):
        return (f"I heard: {heard}. That doesn't sound like a question about the Panchayat Raj data. "
                "Could you say it again?")
    return f"I heard: {heard}. I couldn't confirm an answer to that. Could you say it again, with the place and the year?"


MODEL_UNCHECKED = "The answer is on your screen. I couldn't double-check it, so I won't read it out; please check it there."
FIGURES_ON_SCREEN = "The figures are on your screen."

_SPOKEN_NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})+,\d{3}|\d+)(?:\.(\d+))?\s*(crore|lakh)?")
_DATEY = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b|\b(?:FY ?)?(?:19|20)\d{2}(?:-\d{2})?\b|\b\d{1,2} (?:January|February|March|April|"
                    r"May|June|July|August|September|October|November|December)\b|\b(?:January|February|March|April|May|June|"
                    r"July|August|September|October|November|December) \d{1,2}\b|\b\d{1,2}-[A-Za-z]{3}-\d{4}\b|\bQ[1-4]\b|"
                    r"\b(?:14th|15th|fourteen|fifteen)\b|\b(?:31|238|6,099) (?:zillas|taluks|GPs)\b")
# what a figure's unit may be, right after it
_UNIT_AFTER = re.compile(
    r"^\s*(?:percent|per cent|points|crore|lakh|thousand|rupees|%|GPs?|gram panchayats?|zillas?|taluks?|staff|"
    r"registrations?|seats?|members?|properties|property|books?|year-books?|scheme year-books|schemes?|salaries|salary|"
    r"bills?|months?|years?|days?|accounts?|GP staff|presidents?|households|people|times|approvals?|librarians?|"
    r"workers?|officers?|employees|of\s+[\d,]+|out of)\b", re.I)
# What a whole number can count; named earlier in the sentence, it names the figure ("GPs that closed ... was 20").
_COUNTED = re.compile(r"\b(?:GPs?|gram panchayats?|zillas?|taluks?|staff|registrations?|seats?|members?|properties|books?|"
                      r"year-books|schemes?|salaries|bills?|presidents?|approvals?|employees|count|number)\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _values(text: str, scaled: bool) -> list[float]:
    out = []
    for w, f, scale in _SPOKEN_NUM.findall(_DATEY.sub(" ", text)):
        v = float(w.replace(",", "") + ("." + f if f else ""))
        out.append(v * ({"crore": 1e7, "lakh": 1e5}.get(scale, 1) if scaled else 1))
    return out


def figures_match_screen(spoken: str, answer: str) -> bool:
    """Every figure the voice says is a figure on the screen (rounded as said; lakh / crore compared both ways)."""
    screen = _values(answer, scaled=False) + _values(answer, scaled=True)
    return all(any(abs(v - x) <= max(0.0051 * abs(x), 0.5) for x in screen) for v in _values(spoken, scaled=True))


def _masked(text: str) -> str:
    """Dates, years and the like blanked out (same length, so positions still line up)."""
    return _DATEY.sub(lambda m: " " * len(m.group()), text)


def _unit_follows(masked: str, m: re.Match) -> bool:
    tail = masked[m.end():m.end() + 60]
    if m.group(3):
        return True
    tail = re.sub(r"^\s*(?:about|nearly|around|over|under|more than|less than|of the|of|the)\s+", " ", tail)
    return bool(_UNIT_AFTER.match(tail) or re.match(r"^\s*(?:[\w,.'-]+\s+){0,3}(?:GPs|staff|registrations|seats|members|"
                                                     r"properties|books|year-books|schemes|salaries|bills|months|"
                                                     r"years|zillas|taluks|presidents|accounts)\b", tail, re.I))


def add_units(spoken: str) -> str:
    """No measure in RDPR is kept in an unstated unit (rupees and percent are always written), so nothing is added;
    kept as the hook the voice pipeline calls, like the KPCL instance's heat-rate / frequency rule."""
    return spoken


def figures_have_units(spoken: str) -> bool:
    """No figure the listener can't place: each has its unit after it, or is a whole-number count of something the same
    sentence has already named ('GPs that closed all their books ... was 20'). A bare decimal never passes."""
    for sent in _SENTENCE.split(spoken):
        masked = _masked(sent)
        for m in _SPOKEN_NUM.finditer(masked):
            if _unit_follows(masked, m):
                continue
            if not m.group(2) and _COUNTED.search(sent[:m.start()]):
                continue
            return False
    return True


# ================================================================================================ health
_health: dict = {"at": 0.0, "value": None}
_health_lock = asyncio.Lock()


async def speech_health(force: bool = False) -> dict:
    """{'speech_in': {'ok', 'detail'}, 'speech_out': {...}, 'checked': iso}. Speech in: the model list (no audio, no GPU
    work); speech out: one short word, first audio only. Cached for two minutes."""
    async with _health_lock:
        if not force and _health["value"] and time.monotonic() - _health["at"] < 120:
            return _health["value"]

        async def probe(enabled: bool, base: str, key: str, model: str) -> dict:
            if not enabled:
                return {"ok": False, "detail": "not configured"}
            try:
                async with httpx.AsyncClient(verify=settings.ai_model_ca_bundle_path or False, timeout=6) as c:
                    r = await c.get(f"{base.rstrip('/')}/models", headers={"Authorization": f"Bearer {key}"})
                if r.status_code != 200:
                    return {"ok": False, "detail": f"gateway answered {r.status_code}"}
                ids = [m.get("id") for m in (r.json().get("data") or []) if isinstance(m, dict)]
                return {"ok": True, "detail": "ready" if model in ids or not ids else f"{model} not listed; gateway reachable"}
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "detail": f"unreachable ({type(exc).__name__})"}

        async def probe_tts() -> dict:
            """The voice key may not list models, so ask for one short word and stop at the first audio."""
            if not settings.tts_configured:
                return {"ok": False, "detail": "not configured"}
            from app import voice
            stream = voice.stream_speech("OK.")
            try:
                await asyncio.wait_for(stream.__anext__(), timeout=10)
                return {"ok": True, "detail": "ready"}
            except voice.VoiceBusy:
                return {"ok": True, "detail": "busy"}
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "detail": f"unavailable ({type(exc).__name__})"}
            finally:
                try:
                    await stream.aclose()
                except Exception:  # noqa: BLE001
                    pass

        speech_in, speech_out = await asyncio.gather(
            probe(settings.asr_configured, settings.asr_base_url, settings.asr_api_key, settings.asr_model), probe_tts())
        value = {"speech_in": speech_in, "speech_out": speech_out, "checked": time.strftime("%Y-%m-%dT%H:%M:%S")}
        _health.update(at=time.monotonic(), value=value)
        return value

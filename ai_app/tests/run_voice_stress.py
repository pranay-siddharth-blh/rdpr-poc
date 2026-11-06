"""
Voice stress test: every speakable stress-bank question plus a generated bank (every zilla by the name people actually
say -- Mysore, Belgaum, Gulbarga, Shimoga ... --, every bank taluk, a further GP from every zilla, months, revenue
heads, EO approvals and book closure) is SPOKEN by the Windows Indian-English voices Ravi and Heera, sent through the
real speech-to-text (/api/voice/transcribe -> qwen3-asr on the gateway, VPN needed) and then through this app's voice
pipeline (/api/ask_once with mode "voice"), in-process, so the per-IP rate limits don't throttle the run.

Each spoken question is checked exactly like the typed stress test (expected figures recomputed from the warehouse by
independent SQL on the GP-level fact tables) and, for single-figure answers, the spoken answer must carry that figure
(as said: "124.3 crore rupees", "about 1.63 crore", "29.22 percent"). A failure is re-asked as typed text: if the typed
question passes, the problem is the voice layer (hearing / clean-up); if it fails too, it is the pipeline.

Two speaking styles per question:
  A  Ravi (Indian English, male):    letters ("G P", "E O"), "F Y twenty twenty four twenty five", "Bengaluru South"
  B  Heera (Indian English, female): words ("gram panchayat", "executive officer"),
                                     "financial year twenty twenty four to twenty twenty five", "Ramanagara"

usage (from ai_app):  python tests/run_voice_stress.py [--only 4,136] [--failed] [--limit N] [--workers 4]
Writes tests/voice_stress_report.json and ../VOICE_STRESS_TEST_QUESTIONS.md.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

os.environ["RDPR_RATE_LIMIT_PER_MINUTE"] = "100000"
os.environ["VOICE_RATE_LIMIT_PER_MINUTE"] = "100000"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import httpx  # noqa: E402

from run_stress import check, close, numbers  # noqa: E402  (same checks as the typed stress test)
from stress_bank import (BANK, BOLD, FYS, GPS, NI, PCT, TALUKS, ZILLAS, N, all_closed, dcb, eo, fees, gp,  # noqa: E402
                         month, t, z)

ROOT = HERE.parents[1]
DB = ROOT / "DB" / "rdpr_star.sqlite"
WAVS = Path(os.environ.get("VOICE_WAV_DIR", str(Path(os.environ.get("TEMP", HERE)) / "rdpr_voice_wavs")))
REPORT = HERE / "voice_stress_report.json"
MD = ROOT / "VOICE_STRESS_TEST_QUESTIONS.md"


def unspeakable(q: str) -> bool:
    """Typed-only cases: SQL, symbols and keyboard mashing that nobody speaks (still covered by the typed stress test)."""
    return bool(re.search(r"\*|;|DROP TABLE|asdfghjkl|^\W+$|@", q))


# ------------------------------------------------------------------ how a person says a written question
ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
        "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def two(n: int) -> str:
    return ONES[n] if n < 20 else TENS[n // 10] + (f"-{ONES[n % 10]}" if n % 10 else "")


def year(y: int) -> str:
    return ("two thousand" + (f" {ONES[y - 2000]}" if y > 2000 else "")) if 2000 <= y <= 2009 else f"{two(y // 100)} {two(y % 100)}"


def fy_words(y1: int, y2: int, style: str) -> str:
    return f"{year(y1)} {two(y2 % 100)}" if style == "A" else f"{year(y1)} to {year(2000 + y2 % 100)}"


LETTERS_A = {"GPs": "G Ps", "GP": "G P", "EO": "E O", "DCB": "D C B", "PDOs": "P D Os", "PDO": "P D O", "PMAY": "P M A Y",
             "IPL": "I P L", "API": "A P I", "LLM": "L L M", "SBM": "S B M", "MGNREGA": "M G N REGA", "HRMS": "H R M S"}
WORDS_B = {"GPs": "gram panchayats", "GP": "gram panchayat", "EO": "executive officer", "DCB": "D C B", "PDOs": "P D Os",
           "PDO": "P D O", "PMAY": "P M A Y", "IPL": "I P L", "API": "A P I", "LLM": "L L M", "SBM": "S B M",
           "MGNREGA": "M G N REGA", "HRMS": "H R M S"}


def speakify(q: str, style: str) -> str:
    s = q.lower() if q.isupper() else q
    s = s.replace("Bengaluru South (Ramanagara)", "Bengaluru South" if style == "A" else "Ramanagara")
    s = re.sub(r"\b(?:FY|fy)\s*(\d{4})-(\d{2,4})\b",
               lambda m: ("F Y " if style == "A" else "financial year ") + fy_words(int(m.group(1)), int(m.group(2)), style), s)
    s = re.sub(r"\b(?:FY|fy)\s*(\d{2})-(\d{2})\b",
               lambda m: ("F Y " if style == "A" else "financial year ") + fy_words(2000 + int(m.group(1)), int(m.group(2)), style), s)
    s = re.sub(r"\b(\d{4})-(\d{2,4})\b", lambda m: fy_words(int(m.group(1)), int(m.group(2)), style), s)
    s = re.sub(r"\b(\d{1,2}) (" + "|".join(MONTHS) + r") (\d{4})\b",
               lambda m: f"{m.group(2)} {m.group(1)}, {year(int(m.group(3)))}" if style == "B"
               else f"{m.group(1)} {m.group(2)} {year(int(m.group(3)))}", s)
    s = re.sub(r"\b(" + "|".join(MONTHS) + r") (\d{4})\b", lambda m: f"{m.group(1)} {year(int(m.group(2)))}", s)
    s = re.sub(r"\b(calendar year|in|the) (\d{4})\b", lambda m: f"{m.group(1)} {year(int(m.group(2)))}", s)
    s = re.sub(r"\bQ([1-4])\b", lambda m: f"quarter {ONES[int(m.group(1))]}" if style == "A"
               else f"the {['', 'first', 'second', 'third', 'fourth'][int(m.group(1))]} quarter", s)
    for a, b in (LETTERS_A if style == "A" else WORDS_B).items():
        s = re.sub(rf"\b{a}\b", b, s)
    for a, b in (("%", " percent"), ("&", " and "), ("zilla-wise", "zilla wise"), ("taluk-wise", "taluk wise"),
                 ("month-wise", "month wise"), ("year-wise", "year wise"), ("current-year", "current year")):
        s = s.replace(a, b)
    return re.sub(r"\s{2,}", " ", s).strip()


# ------------------------------------------------------------------ generated bank
SPOKEN_ZILLA = {   # what people say -> warehouse name
    "Bagalkote": "Bagalkot", "Bellary": "Ballari", "Belgaum": "Belagavi", "Bangalore Rural": "Bengaluru Rural",
    "Ramanagara": "Bengaluru South (Ramanagara)", "Bangalore Urban": "Bengaluru Urban", "Bidar": "Bidar",
    "Chamrajnagar": "Chamarajanagar", "Chikballapur": "Chikkaballapura", "Chikmagalur": "Chikkamagaluru",
    "Chitradurga": "Chitradurga", "Dakshina Kannada": "Dakshina Kannada", "Davangere": "Davanagere", "Dharwad": "Dharwad",
    "Gadag": "Gadag", "Hassan": "Hassan", "Haveri": "Haveri", "Gulbarga": "Kalaburagi", "Kodagu": "Kodagu", "Kolar": "Kolar",
    "Koppal": "Koppal", "Mandya": "Mandya", "Mysore": "Mysuru", "Raichur": "Raichur", "Shimoga": "Shivamogga",
    "Tumkur": "Tumakuru", "Udupi": "Udupi", "Uttara Kannada": "Uttara Kannada", "Vijayanagara": "Vijayanagara",
    "Bijapur": "Vijayapura", "Yadgiri": "Yadgir",
}
_MONTH_IDS = [202205, 202209, 202301, 202306, 202311, 202402, 202407, 202412, 202503, 202508, 202601, 202606, 202609]


def extra_gps(conn) -> list[tuple[str, str]]:
    """One more GP from every zilla, beyond the bank's: a name unique in the state (no taluk needed to say which)."""
    rows = conn.execute(
        "SELECT z.zilla_name, g.gp_name FROM dim_gp g JOIN dim_zilla z USING (zilla_id) "
        "WHERE g.gp_name IN (SELECT gp_name FROM dim_gp GROUP BY gp_name HAVING COUNT(*) = 1) ORDER BY z.zilla_name, g.gp_id").fetchall()
    taken = {g for g, _ in GPS}
    by_zilla: dict[str, list[str]] = {}
    for zn, gn in rows:
        if gn not in taken and re.fullmatch(r"[A-Za-z ]{4,22}", gn):
            by_zilla.setdefault(zn, []).append(gn)
    return [(zn, names[len(names) // 3]) for zn, names in sorted(by_zilla.items())]


def generated(conn) -> list[dict]:
    out, n = [], 1000

    def add(area, q, *checks):
        nonlocal n
        n += 1
        out.append({"id": n, "area": area, "q": q, "checks": list(checks)})

    for i, (said, zn) in enumerate(SPOKEN_ZILLA.items()):
        fy = FYS[i % len(FYS)]
        if i % 2 == 0:
            add("Voice · zilla name", f"What was the total collection of {said} district in FY {fy}?",
                NI(dcb("SUM(f.total_collection)", fy, z(zn))))
        else:
            add("Voice · zilla name", f"Collection percentage of {said} in {fy}", N(dcb(PCT, fy, z(zn))))
        mid = _MONTH_IDS[i % len(_MONTH_IDS)]
        add("Voice · month", f"What was the collection in {said} zilla in {MONTHS[mid % 100 - 1]} {mid // 100}?",
            NI(month("SUM(f.collection_amount)", mid, z(zn))))
    for i, (tn, _zn) in enumerate(TALUKS):
        fy = FYS[(i + 3) % len(FYS)]
        add("Voice · taluk", f"What was the total collection of {tn} taluk in FY {fy}?", NI(dcb("SUM(f.total_collection)", fy, t(tn))))
    for i, (_zn, gn) in enumerate(extra_gps(conn)):
        fy = FYS[(i + 1) % len(FYS)]
        if i % 2:
            add("Voice · GP", f"Collection percentage of {gn} gram panchayat in FY {fy}", N(dcb(PCT, fy, gp(gn))))
        else:
            add("Voice · GP", f"What was the total collection of {gn} GP in FY {fy}?", NI(dcb("SUM(f.total_collection)", fy, gp(gn))))
    for fee, word, zn, fy in (("Property Taxes", "property tax", "Mandya", "2023-24"), ("Mobile Tower Tax", "mobile tower tax", "Kolar", "2024-25"),
                              ("Application Fees", "application fees", "Tumakuru", "2025-26"), ("Property Taxes", "property tax", "Bidar", "2022-23")):
        add("Voice · revenue head", f"How much {word} was collected in {zn} zilla in FY {fy}?",
            NI(fees("SUM(f.total_collection)", fy, fee, z(zn))))
    for zn, fy in (("Hassan", "2025-26"), ("Raichur", "2024-25"), ("Udupi", "2023-24")):
        add("Voice · EO", f"How many staff registrations were pending at the EO in {zn} zilla in FY {fy}?",
            N(eo("SUM(f.staff_approval_pending_at_eo)", fy, z(zn))))
    for zn, fy in (("Chitradurga", "2024-25"), ("Gadag", "2023-24"), ("Koppal", "2025-26")):
        add("Voice · book closure", f"How many GPs closed all their books in {zn} zilla in FY {fy}?", N(all_closed(fy, z(zn))))
    add("Voice · state", "What was the collection percentage across Karnataka in FY 2023-24?", N(dcb(PCT, "2023-24")), BOLD)
    return out


# ------------------------------------------------------------------ running
NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{2,3})+|\d+)(?:\.(\d+))?\s*(crore|lakh)?")


def spoken_has(spoken: str, expected: float) -> bool:
    """The figure is in what the voice says, at the precision it is said ("about 1.63 crore" for 16,301,364)."""
    for w, f, scale in NUM.findall(spoken or ""):
        unit = {"crore": 1e7, "lakh": 1e5}.get(scale, 1)
        v = float(w.replace(",", "") + ("." + f if f else "")) * unit
        step = 10 ** -len(f) * unit if f else unit                  # the precision it was said at
        if abs(v - expected) <= max(abs(expected) * 0.006, step * 0.51):
            return True
    return False


def make_wavs(trials: list[dict]) -> None:
    WAVS.mkdir(parents=True, exist_ok=True)
    todo = [{"path": tr["wav"], "voice": tr["voice"], "text": tr["said"]} for tr in trials if not Path(tr["wav"]).exists()]
    if not todo:
        return
    lst = WAVS / "phrases.json"
    lst.write_text(json.dumps(todo), encoding="utf-8")
    print(f"speaking {len(todo)} questions to WAV ...", flush=True)
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HERE / "make_wavs.ps1"), "-List", str(lst)],
                   check=True)


_GENERIC = {"zilla", "taluk", "district", "gram", "panchayat", "division"}


def pick_option(options: list[dict], meant: str) -> int:
    """Which 'Did you mean ...?' option the speaker meant (the same word match as the panel's spoken reply)."""
    tx = " " + re.sub(r"[^a-z0-9-]+", " ", meant.lower()) + " "
    meant_years = set(re.findall(r"(?:19|20)(\d{2})-(\d{2})", meant))

    def score(o: dict) -> int:
        words = [w for w in re.findall(r"[a-z]{4,}", o["label"].lower()) if w not in _GENERIC]
        years = set(re.findall(r"(?:19|20)(\d{2})-(\d{2})", o["label"]))
        return sum(f" {w} " in tx for w in words) + 2 * len(years & meant_years)
    scores = [score(o) for o in options]
    return scores.index(max(scores))


async def run_trial(client, conn, tr: dict, sem: asyncio.Semaphore) -> dict:
    async with sem:
        t0 = time.time()
        audio = Path(tr["wav"]).read_bytes()
        r = await client.post(f"/api/voice/transcribe?session_id=t{tr['item']['id']}{tr['style']}", content=audio,
                              headers={"content-type": "audio/wav"})
        body = r.json() if r.status_code == 200 else {}
        heard = body.get("text", "") if r.status_code == 200 else f"!!! transcribe {r.status_code}"
        if body.get("rejected"):
            heard = f"!!! rejected {body['rejected']}: {body.get('heard', '')}"
        conf = body.get("confirm") or {}
        confirm, question = conf.get("prompt", ""), body.get("text", "")
        if conf.get("options"):                       # the officer taps the option they meant, as on the voice panel
            i = pick_option(conf["options"], tr["item"]["q"])
            question = conf["options"][i]["question"]
            confirm += f" -> {conf['options'][i]['label']}"
        a = await client.post("/api/ask_once", json={"question": question or "(silence)", "mode": "voice"})
        ans = a.json() if a.headers.get("content-type", "").startswith("application/json") else {"answer": a.text}
        if a.status_code >= 400:
            ans = {"answer": str(ans.get("detail", "")), "answerable": False}
        problems, expected = check(tr["item"], ans, conn)
        num_checks = [c for c in tr["item"]["checks"] if c[0] == "num"]
        if not problems and len(num_checks) == 1 and len(ans.get("rows") or []) <= 1 and ans.get("spoken_answer"):
            row = conn.execute(num_checks[0][1]).fetchone()
            head = re.match(r"\s*\*\*(.+?)\*\*", ans.get("answer") or "", re.S)
            in_head = head and any(close(numbers({"answer": head.group(1)}), float(v))
                                   for f in (num_checks[0][2] or (list,)) for v in f(row))
            # the expected figure is the headline's figure (not a total behind a growth rate): it must be said
            if row and len(row) == 1 and row[0] is not None and in_head and not spoken_has(ans["spoken_answer"], float(row[0])):
                problems.append(f"spoken answer lacks {row[0]:,.3f}")
        if not problems and ans.get("answerable") is not False and not (ans.get("spoken_answer") or "").strip():
            problems.append("no spoken answer")
        out = {"id": tr["item"]["id"], "style": tr["style"], "voice": tr["voice"], "area": tr["item"]["area"], "q": tr["item"]["q"],
               "said": tr["said"], "asr": body.get("heard", ""), "heard": heard, "asked": question, "expected": expected, "problems": problems,
               "answer": (ans.get("answer") or "")[:400], "spoken": ans.get("spoken_answer", ""), "route": ans.get("route", ""),
               "confirm": confirm, "status": "PASS" if not problems else "FAIL", "secs": round(time.time() - t0, 2)}
        if problems:                                  # is it the voice layer or the pipeline?
            typed = (await client.post("/api/ask_once", json={"question": tr["item"]["q"]}))
            typed = typed.json() if typed.status_code < 400 else {"answer": str(typed.json().get("detail", "")), "answerable": False}
            tp, _ = check(tr["item"], typed, conn)
            out["typed_status"] = "PASS" if not tp else "FAIL"
        print(f"{out['status']} {out['id']}{tr['style']} [{out['area']}] heard: {heard[:110]}" + (f"  [confirmed: {confirm}]" if confirm else "")
              + ("" if not problems else f"  <-- {problems} (typed: {out['typed_status']})\n      spoken: {out['spoken'][:200]}"), flush=True)
        return out


async def main_async(a) -> None:
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    items = [b for b in BANK if not unspeakable(b["q"])] + generated(conn)
    if a.only:
        keep = {int(x) for x in a.only.split(",")}
        items = [b for b in items if b["id"] in keep]
    if a.area:
        items = [b for b in items if b["area"].lower().startswith(a.area.lower())]
    prev = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {"results": {}}
    trials = []
    for b in items:
        for style, voice in (("A", "Ravi"), ("B", "Heera")):
            key = f"{b['id']}{style}"
            if a.failed and prev["results"].get(key, {}).get("status") == "PASS" and prev["results"][key].get("q") == b["q"]:
                continue
            said = speakify(b["q"], style)
            trials.append({"item": b, "style": style, "voice": voice, "said": said,
                           "wav": str(WAVS / f"{key}_{voice}_{hashlib.md5(said.encode()).hexdigest()[:10]}.wav")})
    if a.limit:
        trials = trials[: a.limit]
    make_wavs(trials)
    if a.wavs_only:
        return
    from app.main import app
    sem = asyncio.Semaphore(a.workers)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://voice", timeout=300) as client:
            results = await asyncio.gather(*(run_trial(client, conn, tr, sem) for tr in trials))
    merged = prev["results"] if (a.failed or a.only or a.area) else {}
    merged.update({f"{r['id']}{r['style']}": r for r in results})
    valid = {f"{b['id']}{s}" for b in [b for b in BANK if not unspeakable(b["q"])] + generated(conn) for s in "AB"}
    merged = {k: v for k, v in merged.items() if k in valid}
    passed = sum(r["status"] == "PASS" for r in merged.values())
    REPORT.write_text(json.dumps({"passed": passed, "total": len(merged), "results": merged}, indent=1, ensure_ascii=False),
                      encoding="utf-8")
    write_md(merged)
    print(f"\n{passed}/{len(merged)} spoken questions passed (this run: {sum(r['status'] == 'PASS' for r in results)}/{len(results)})")


def write_md(res: dict) -> None:
    rows = sorted(res.values(), key=lambda r: (r["id"], r["style"]))
    passed = sum(r["status"] == "PASS" for r in rows)
    cell = lambda s: str(s).replace("|", "/").replace("\n", " ")  # noqa: E731
    lines = ["# Voice stress test (spoken questions)", "",
             f"**{passed} of {len(rows)} spoken questions answered correctly** ({time.strftime('%d %B %Y')}). Each question was "
             "spoken by a Windows Indian-English voice (A: Ravi, letters and short year forms; B: Heera, words and long-form "
             "years), heard by the real speech-to-text (qwen3-asr), cleaned up and answered by the voice pipeline. Where the "
             "assistant asked \"Did you mean ...?\", the option the speaker meant was tapped, as on the voice panel. Expected "
             "figures are recomputed from the warehouse's GP-level fact tables; a single figure must also be in what the voice "
             "says. Re-run: `python tests/run_voice_stress.py` in `ai_app` (VPN needed).", "",
             "| # | Area | Spoken | Heard | Expected | Result |", "|---|---|---|---|---|---|"]
    for r in rows:
        res_txt = r["status"] if r["status"] == "PASS" else f"FAIL: {'; '.join(r['problems'])} (typed: {r.get('typed_status', '?')})"
        if r.get("confirm"):
            res_txt += f" (confirmed: {r['confirm']})"
        lines.append(f"| {r['id']}{r['style']} | {cell(r['area'])} | {cell(r['said'])} | {cell(r['heard'])} | "
                     f"{cell(', '.join(r['expected']))} | {cell(res_txt)} |")
    MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--area", default="")
    ap.add_argument("--failed", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--wavs-only", action="store_true")
    asyncio.run(main_async(ap.parse_args()))

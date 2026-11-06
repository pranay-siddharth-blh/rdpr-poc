"""
Spoken follow-up stress test: the follow-up conversations of tests/followup_bank.py SPOKEN by the Windows Indian-English
voices Ravi (style A: "F Y twenty twenty four twenty five", "G P") and Heera (style B: "financial year twenty twenty four
to twenty twenty five", "gram panchayat"), sent through the real speech-to-text (/api/voice/transcribe -> qwen3-asr, VPN
needed) and then asked in voice mode with the previous question the page holds at that point, in-process.

Each turn is played on its own: the `previous` it is asked with is the one the typed run sent at that turn
(tests/followup_stress_report.json, run tests/run_followup_stress.py first), so one mishearing does not throw the rest
of a conversation off. Checks: the spoken follow-up is not dropped as a fragment, it is taken as a follow-up when it
should be, the figures (recomputed from the warehouse), the spoken answer naming the place and saying the figure. A
failure is re-asked as typed text: a typed pass means the miss is in hearing, not in following up.

usage (from ai_app):  python tests/run_voice_followup_stress.py [--random 30] [--workers 6] [--only 3,17]
Writes tests/voice_followup_stress_report.json and ../VOICE_FOLLOWUP_STRESS_TEST.md.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

os.environ["RDPR_RATE_LIMIT_PER_MINUTE"] = "100000"
os.environ["VOICE_RATE_LIMIT_PER_MINUTE"] = "100000"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import httpx  # noqa: E402

from followup_bank import CONVERSATIONS  # noqa: E402
from run_stress import check, close, numbers  # noqa: E402
from run_voice_stress import WAVS, make_wavs, pick_option, speakify, spoken_has, unspeakable  # noqa: E402

ROOT = HERE.parents[1]
DB = ROOT / "DB" / "rdpr_star.sqlite"
TYPED = HERE / "followup_stress_report.json"
REPORT = HERE / "voice_followup_stress_report.json"
MD = ROOT / "VOICE_FOLLOWUP_STRESS_TEST.md"


def place_word(tn: dict) -> str:
    """The place the spoken answer must name ("bengaluru south": the voice leaves out the bracketed old name)."""
    return next((g.split("|")[0].split(" (")[0] for k, *rest in tn["checks"] if k == "text" for g in rest[0]), "")


async def run_trial(client, conn, tr: dict, sem: asyncio.Semaphore) -> dict:
    tn = tr["turn"]
    async with sem:
        t0 = time.time()
        r = await client.post(f"/api/voice/transcribe?session_id=f{tr['key']}", content=Path(tr["wav"]).read_bytes(),
                              headers={"content-type": "audio/wav"})
        body = r.json() if r.status_code == 200 else {}
        question, conf, problems = body.get("text", ""), body.get("confirm") or {}, []
        if body.get("rejected"):
            problems.append(f"dropped by the voice guard ({body['rejected']})")
        if conf.get("options"):                       # the officer taps the option they meant
            i = pick_option(conf["options"], tn["q"])
            question = conf["options"][i]["question"]
        payload = {"question": question or "(silence)", "mode": "voice", **({"previous": tr["previous"]} if tr["previous"] else {})}
        a = await client.post("/api/ask_once", json=payload)
        ans = a.json() if a.status_code < 400 else {"answer": f"!!! HTTP {a.status_code}", "answerable": None}
        p2, expected = check(tn, ans, conn)
        problems += p2
        asked = ans.get("asked_as") or ""
        if tn["follow"] is True and not asked:
            problems.append("not taken as a follow-up")
        if tn["follow"] is False and asked:
            problems.append(f"wrongly taken as a follow-up: {asked!r}")
        said = (ans.get("spoken_answer") or "").lower()
        if ans.get("answerable") and not problems:
            name = place_word(tn)
            if not said:
                problems.append("no spoken answer")
            elif name and name not in said:
                problems.append(f"spoken answer does not name {name!r}")
            nums = [c for c in tn["checks"] if c[0] == "num"]
            head = re.match(r"\s*\*\*(.+?)\*\*", ans.get("answer") or "", re.S)
            if len(nums) == 1 and head and said:
                row = conn.execute(nums[0][1]).fetchone()
                if row and len(row) == 1 and row[0] is not None and any(
                        close(numbers({"answer": head.group(1)}), float(v)) for f in (nums[0][2] or (list,)) for v in f(row)) \
                        and not spoken_has(said, float(row[0])):
                    problems.append(f"spoken answer lacks {row[0]:,.3f}")
        out = {"key": tr["key"], "conv": tr["conv"], "turn": tr["n"], "voice": tr["voice"], "q": tn["q"], "said": tr["said"],
               "asr": body.get("heard", ""), "heard": question, "previous": tr["previous"], "asked_as": asked,
               "problems": problems, "expected": expected, "answer": (ans.get("answer") or "")[:300], "spoken": ans.get("spoken_answer", ""),
               "status": "PASS" if not problems else "FAIL", "secs": round(time.time() - t0, 2)}
        if problems:                                  # hearing, or following up?
            typed = await client.post("/api/ask_once", json={"question": tn["q"], **({"previous": tr["previous"]} if tr["previous"] else {})})
            tp, _ = check(tn, typed.json() if typed.status_code < 400 else {"answer": "", "answerable": None}, conn)
            out["typed_status"] = "PASS" if not tp else "FAIL"
        print(f"{out['status']} {tr['key']} heard: {question[:100]!r}" + (f" -> {asked[:90]!r}" if asked else "")
              + ("" if not problems else f"\n      <-- {problems} (typed: {out['typed_status']})  said: {tr['said']!r}"), flush=True)
        return out


async def main_async(a) -> None:
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    typed = {c["id"]: c for c in json.loads(TYPED.read_text(encoding="utf-8"))["results"]}
    walks = [c for c in CONVERSATIONS if c["area"] == "Random walk"][: a.random]
    convs = walks + [c for c in CONVERSATIONS if c["area"] != "Random walk"]
    if a.only:
        keep = {int(x) for x in a.only.split(",")}
        convs = [c for c in convs if c["id"] in keep]
    trials = []
    for c in convs:
        rows = typed[c["id"]]["turns"]
        for n, (tn, row) in enumerate(zip(c["turns"], rows), 1):
            if "previous" in tn or unspeakable(tn["q"]) or row["q"] != tn["q"] or len(tn["q"].split()) == 1:
                continue                              # typed-only: a client's own `previous`, symbols, one word ("balance?",
                                                      # which the voice drops as a fragment by design)
            for style, voice in (("A", "Ravi"), ("B", "Heera")):
                said = speakify(tn["q"], style)
                key = f"{c['id']}.{n}{style}"
                trials.append({"key": key, "conv": c["id"], "n": n, "turn": tn, "voice": voice, "said": said, "previous": row["previous"],
                               "wav": str(WAVS / f"fu{key}_{voice}_{hashlib.md5(said.encode()).hexdigest()[:10]}.wav")})
    make_wavs(trials)
    from app.main import app
    sem = asyncio.Semaphore(a.workers)
    t0 = time.time()
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://voice", timeout=300) as client:
            results = await asyncio.gather(*(run_trial(client, conn, tr, sem) for tr in trials))
    passed = sum(r["status"] == "PASS" for r in results)
    fails = [r for r in results if r["status"] != "PASS"]
    hearing = sum(r.get("typed_status") == "PASS" for r in fails)
    summary = {"turns": len(results), "passed": passed, "failed": len(fails), "failed_but_typed_passes": hearing,
               "dropped_as_fragment": sum(any("dropped" in p for p in r["problems"]) for r in results),
               "seconds": round(time.time() - t0, 1)}
    print(f"\n{passed}/{len(results)} spoken follow-up turns passed; of the {len(fails)} misses, {hearing} pass when typed "
          f"(hearing errors); {summary['dropped_as_fragment']} dropped as fragments; {summary['seconds']} s")
    if a.only:
        return
    REPORT.write_text(json.dumps({"summary": summary, "results": results}, indent=1, ensure_ascii=False), encoding="utf-8")
    out = ["# Spoken follow-up stress test\n",
           f"**{passed} of {len(results)} spoken turns correct** ({time.strftime('%d %B %Y')}); of the {len(fails)} misses, "
           f"{hearing} pass when the same turn is typed (the speech was misheard, not the follow-up mishandled). "
           f"{summary['dropped_as_fragment']} spoken follow-ups were dropped as fragments.\n",
           "Each turn of the follow-up conversations (`ai_app/tests/followup_bank.py`) is spoken by the Windows voices Ravi "
           "(A) and Heera (B), transcribed by the real speech-to-text and asked in voice mode with the previous question the "
           "page holds at that turn. Re-run: `python tests/run_voice_followup_stress.py` in `ai_app` (VPN).\n",
           "| Turn | Said | Heard | Taken as | Result |", "|---|---|---|---|---|"]
    for r in results:
        res = r["status"] if r["status"] == "PASS" else "FAIL: " + "; ".join(r["problems"]).replace("|", "/") + \
            (f" (typed: {r.get('typed_status')})" if r.get("typed_status") else "")
        out.append(f"| {r['key']} | {r['said'].replace('|', '/')} | {r['heard'].replace('|', '/')} | "
                   f"{(r['asked_as'] or '—').replace('|', '/')} | {res} |")
    MD.write_text("\n".join(out) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--random", type=int, default=30, help="how many random-walk conversations to speak")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--only", default="")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()

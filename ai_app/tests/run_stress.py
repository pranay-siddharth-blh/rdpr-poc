"""
Live stress test: asks every question in tests/stress_bank.py and checks the answers against figures recomputed from
the warehouse (read-only, GP-level fact tables). Writes tests/stress_report.json and ../STRESS_TEST_QUESTIONS.md.

Usage (server running):  python tests/run_stress.py [--url http://127.0.0.1:8000] [--only 3,17,40] [--failed] [--workers 4]
In-process (no server):  python tests/run_stress.py --local [--failed] [--area Breakdown]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from stress_bank import BANK  # noqa: E402

ROOT = HERE.parents[1]                      # RDPR POC/RDPR POC
DB = ROOT / "DB" / "rdpr_star.sqlite"
REPORT = HERE / "stress_report.json"
MD = ROOT / "STRESS_TEST_QUESTIONS.md"
REFUSAL_WORDS = ("I can't", "I can only", "I couldn't", "isn't reachable", "couldn't answer", "!!!", "N/A")
NUM_RE = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")


def numbers(ans: dict) -> list[float]:
    out = []
    for m in NUM_RE.finditer(ans.get("answer") or ""):
        try:
            out.append(float(m.group(0).replace(",", "")))
        except ValueError:
            pass
    for row in ans.get("rows") or []:
        for v in row:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append(float(v))
            elif isinstance(v, str):
                try:
                    out.append(float(v.replace(",", "")))
                except ValueError:
                    pass
    return out


def close(found: list[float], exp: float) -> bool:
    tol = max(abs(exp) * 0.0015, 0.051 if abs(exp) < 1000 else 0.51)
    return any(abs(f - exp) <= tol for f in found)


def fmt(v) -> str:
    return f"{v:,.3f}".rstrip("0").rstrip(".") if isinstance(v, float) else f"{v:,}" if isinstance(v, int) else str(v)


def check(item: dict, ans: dict, conn) -> tuple[list[str], list[str]]:
    """Returns (problems, expected-description)."""
    problems, expected = [], []
    text = (ans.get("answer") or "")
    low = text.lower()
    answerable = ans.get("answerable")
    found = numbers(ans)
    for c in item["checks"]:
        kind = c[0]
        if kind == "num":
            row = conn.execute(c[1]).fetchone()
            if row is None or any(v is None for v in row):
                problems.append(f"check query returned no value ({row})")
                continue
            sets = [list(f(row)) for f in c[2]] if c[2] else [list(row)]
            expected.append(" or ".join(", ".join(fmt(v) for v in s) for s in sets))
            if not any(all(close(found, float(v)) for v in s) for s in sets):
                problems.append(f"missing figure {expected[-1]}")
            if answerable is False:
                problems.append("refused")
        elif kind in ("text", "note"):
            for g in c[1]:
                expected.append(g.replace("|", " / "))
                if not any(a in low for a in g.split("|")):
                    problems.append(f"missing text {g!r}")
            if kind == "text" and answerable is False:
                problems.append("refused")
        elif kind == "refuse":
            expected.append("refused")
            if answerable is not False:
                problems.append("not refused")
        elif kind == "answer":
            expected.append("answered")
            if answerable is False or any(w in text for w in REFUSAL_WORDS) or not text.strip():
                problems.append("not answered")
        elif kind == "chart":
            expected.append("chart")
            if not ans.get("chart"):
                problems.append("no chart")
        elif kind == "bold":
            expected.append("bold headline")
            if not text.lstrip().startswith("**"):
                problems.append("no bold headline")
    return problems, list(dict.fromkeys(expected))


_PACE = threading.Lock()
_LAST = [0.0]


def ask_http(url: str, q: str, gap: float) -> tuple[dict, float]:
    with _PACE:
        wait = _LAST[0] + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _LAST[0] = time.time()
    t0 = time.time()
    req = urllib.request.Request(url + "/api/ask_once", json.dumps({"question": q}).encode(), {"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=300)), time.time() - t0
    except urllib.error.HTTPError as exc:        # guardrail answers with a 4xx status still carry a message
        try:
            body = json.loads(exc.read() or b"{}")
        except ValueError:
            body = {}
        return {"answer": str(body.get("detail", "")), "answerable": False, "http_status": exc.code}, time.time() - t0
    except Exception as exc:  # noqa: BLE001
        return {"answer": f"!!! request failed: {exc}", "answerable": None}, time.time() - t0


def ask_local(items: list[dict], workers: int) -> list[tuple[dict, float]]:
    from app.config import settings
    from app.db import ReadOnlyDB
    from app.llm import init_llm_client, shutdown_llm_client
    from app.pipeline import answer_question
    db = ReadOnlyDB(settings.db_path)

    async def go():
        init_llm_client()                      # the server does this in its lifespan
        sem = asyncio.Semaphore(workers)

        async def one(q):
            async with sem:
                t0 = time.time()
                try:
                    r = await asyncio.wait_for(answer_question(q, db, settings.rdpr_max_rows, settings.rdpr_query_timeout_seconds), 300)
                    d = {"answer": r.answer, "answerable": r.answerable, "rows": r.rows, "chart": r.chart, "route": r.route}
                except Exception as exc:  # noqa: BLE001
                    d = {"answer": f"!!! {type(exc).__name__}: {exc}", "answerable": None}
                return d, time.time() - t0
        try:
            return await asyncio.gather(*(one(i["q"]) for i in items))
        finally:
            await shutdown_llm_client()
    try:
        return asyncio.run(go())
    finally:
        db.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--only", default="")
    ap.add_argument("--area", default="")
    ap.add_argument("--failed", action="store_true")
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--gap", type=float, default=1.05, help="seconds between questions (the server allows 60 a minute per client)")
    a = ap.parse_args()
    items = BANK
    prev = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {"results": {}}
    if a.only:
        ids = {int(x) for x in a.only.split(",")}
        items = [i for i in BANK if i["id"] in ids]
    elif a.failed:
        items = [i for i in BANK if prev["results"].get(str(i["id"]), {}).get("status") != "PASS"
                 or prev["results"].get(str(i["id"]), {}).get("q") != i["q"]]
    if a.area:
        items = [i for i in items if i["area"].lower().startswith(a.area.lower())]
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    if a.local:
        answers = ask_local(items, a.workers)
    else:
        with ThreadPoolExecutor(a.workers) as ex:
            answers = list(ex.map(lambda i: ask_http(a.url, i["q"], a.gap), items))
    results = {k: v for k, v in prev["results"].items() if int(k) <= len(BANK)}
    for item, (ans, secs) in zip(items, answers):
        problems, expected = check(item, ans, conn)
        status = "PASS" if not problems else "FAIL"
        results[str(item["id"])] = {"status": status, "q": item["q"], "area": item["area"], "expected": expected,
                                    "problems": problems, "answer": ans.get("answer", ""), "route": ans.get("route", ""),
                                    "secs": round(secs, 2)}
        print(f"{status} {item['id']:3d} [{item['area']}] {item['q']}" + ("" if not problems else
              f"\n      {problems}  route={ans.get('route', '')}\n      -> {ans.get('answer', '')[:300]!r}"), flush=True)
    passed = sum(1 for i in BANK if results.get(str(i["id"]), {}).get("status") == "PASS" and results[str(i["id"])].get("q") == i["q"])
    REPORT.write_text(json.dumps({"passed": passed, "total": len(BANK), "results": results}, indent=1, ensure_ascii=False), encoding="utf-8")
    write_md(results, passed)
    print(f"\n{passed}/{len(BANK)} passed (this run: {sum(1 for i in items if results[str(i['id'])]['status'] == 'PASS')}/{len(items)})")


def write_md(results: dict, passed: int):
    lines = ["# Stress-test questions (live)", "",
             f"**{passed} of {len(BANK)} answered correctly** ({time.strftime('%d %B %Y')}). Every expected figure is recomputed "
             "from the warehouse by a query written independently of the chatbot's own SQL (from the GP-level `fact_*` core "
             "tables, never the `mart_agg_*` tables the chatbot reads) and must appear in the answer; breakdown and "
             "comparison questions must also carry a chart, and reviewed answers must open with a bold headline. "
             "Re-run with the server up: `python tests/run_stress.py` in `ai_app` (or `--local` without a server).", ""]
    area = None
    for item in BANK:
        r = results.get(str(item["id"]), {})
        if item["area"].split(" ·")[0] != area:
            area = item["area"].split(" ·")[0]
            lines += ["", f"## {area}", "", "| # | Question | Expected | Result |", "|---|---|---|---|"]
        exp = "; ".join(r.get("expected", [])).replace("|", "/") or "—"
        lines.append(f"| {item['id']} | {item['q'].replace('|', '/')} | {exp} | {r.get('status', 'not run')} |")
    MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

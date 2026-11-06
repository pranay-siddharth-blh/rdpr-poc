"""
Live evaluation of the LLM path through the real pipeline and the real gateway (in-process, no server needed): every
question in eval_questions.py is asked, and the figures of its reference SQL's first row must appear in the answer
text or in the returned rows (same matching as run_stress.py). Writes tests/eval_report.json and prints a summary.

run from ai_app:   python tests/run_eval.py [--ids 1,5]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from app.config import settings  # noqa: E402
from app.db import ReadOnlyDB  # noqa: E402
from app.llm import init_llm_client, shutdown_llm_client  # noqa: E402
from app.pipeline import answer_question  # noqa: E402
from eval_questions import QUESTIONS  # noqa: E402
from run_stress import close, fmt, numbers  # noqa: E402

REPORT = HERE / "eval_report.json"


async def run(items: list[dict]) -> list[dict]:
    db = ReadOnlyDB(settings.db_path)
    init_llm_client()
    out = []
    try:
        for item in items:
            ref = (await db.run(item["ref"], max_rows=1, timeout_seconds=60)).rows
            expected = [float(v) for v in ref[0]] if ref else []
            t0 = time.time()
            r = await answer_question(item["q"], db, settings.rdpr_max_rows, settings.rdpr_query_timeout_seconds)
            found = numbers({"answer": r.answer, "rows": r.rows})
            missing = [fmt(v) for v in expected if not close(found, v)]
            ok = bool(expected) and not missing and r.answerable
            out.append({"id": item["id"], "q": item["q"], "status": "PASS" if ok else "FAIL", "route": r.route,
                        "expected": [fmt(v) for v in expected], "missing": missing, "answer": r.answer,
                        "secs": round(time.time() - t0, 1)})
            print(f"{'PASS' if ok else 'FAIL'} {item['id']:2d} [{r.route}] {item['q']}"
                  + ("" if ok else f"\n      missing {missing}\n      -> {r.answer[:300]!r}"), flush=True)
    finally:
        await shutdown_llm_client()
        db.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    a = ap.parse_args()
    items = [q for q in QUESTIONS if not a.ids or q["id"] in {int(x) for x in a.ids.split(",")}]
    if not settings.llm_configured:
        sys.exit("The model gateway is not configured in ai_app/.env; this evaluation needs it.")
    results = asyncio.run(run(items))
    passed = sum(r["status"] == "PASS" for r in results)
    REPORT.write_text(json.dumps({"passed": passed, "total": len(results), "results": results}, indent=1, ensure_ascii=False),
                      encoding="utf-8")
    print(f"\n{passed}/{len(results)} passed")


if __name__ == "__main__":
    main()

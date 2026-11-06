"""
Capability check (no LLM, no SQL): a question that needs data this assistant does not hold -- budgets, audit, MGNREGA
and works, population, grievances, individual taxpayer records, daily collection -- gets the reviewed note from the
capability manifest instead of a guessed or empty answer.
"""
from __future__ import annotations

import re

from app.semantic_layer import load_semantic_layer, norm


def _loaded_summary() -> str:
    topics = [c for c in load_semantic_layer()["capabilities"] if c["status"] == "loaded"]
    names = {"finance_closure": "book closure by scheme", "finance_accounts": "scheme receipts, expenditure and balances",
             "revenue": "demand, collection, arrears and balance", "hrms": "staff, EO approvals, elected members and salary bills"}
    return ", ".join(names.get(t["topic"], t["topic"]) for t in topics)


def check(question: str) -> str | None:
    q = norm(question)
    for cap in (c for c in load_semantic_layer()["capabilities"] if c["status"] == "not_loaded"):
        for kw in cap.get("keywords", []):
            if re.search(r"(?<![a-z0-9])" + re.escape(kw.lower()) + r"(?![a-z0-9])", q):
                return _note(cap)
    return None


def _note(cap: dict) -> str:
    return (f"**{cap['note']}**\n\nWhat this data does cover, for every Gram Panchayat, taluk and zilla from April 2022 to "
            f"September 2026: {_loaded_summary()}.")

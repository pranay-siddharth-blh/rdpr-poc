import asyncio
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.dashboard_data import DashboardNotFound, build_dashboard
from conftest import run


@pytest.fixture(scope="module")
def raw():
    c = sqlite3.connect(f"file:{settings.db_path.as_posix()}?mode=ro", uri=True)
    yield c
    c.close()


def test_dashboard_matches_raw_tables(db, raw):
    d = run(build_dashboard(db, "2024-25"))
    c, dem = raw.execute("SELECT SUM(total_collection), SUM(total_demand) FROM fact_rev_dcb_register WHERE fy_id = 'FY2425'").fetchone()
    assert abs(d["revenue"]["total_collection"] - c) < 1 and d["revenue"]["collection_pct"] == round(100 * c / dem, 2)
    assert d["gps"] == 6099 and d["partial_fy"] is False
    # internal consistency: months add up to the year, heads add up to the year, zillas add up to the state
    assert abs(sum(m["collection"] for m in d["monthly_collection"]) - c) < 1
    assert abs(sum(h["collection"] for h in d["by_head"]) - c) < 1
    assert abs(sum(z["collection"] for z in d["league"]) - c) < 1 and len(d["league"]) == 31
    assert d["hrms"]["active_staff"] == raw.execute("SELECT COUNT(*) FROM fact_hr_staff WHERE employment_status = 'Active'").fetchone()[0]


def test_zilla_selection_and_part_year(db):
    d = run(build_dashboard(db, "2026-27", "Mysuru"))
    assert d["partial_fy"] and d["league_label"] == "taluk" and d["gps"] == 268
    assert d["finance"]["gps_all_closed"] == 0                  # year-end closure has not happened in the part year


def test_unknown_selection_is_rejected(db):
    for fy, z in (("1999-00", None), ("2024-25", "Atlantis")):
        with pytest.raises(DashboardNotFound):
            run(build_dashboard(db, fy, z))


def test_api_pages_security_headers_and_stream():
    from app.main import app
    with TestClient(app) as c:
        for path in ("/", "/chat", "/dashboard", "/insights", "/health", "/api/options", "/static/vendor/chart.umd.min.js",
                     "/static/vendor/fonts.css"):
            assert c.get(path).status_code == 200, path
        r = c.get("/")
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"] and "unsafe-inline'" not in \
            r.headers["content-security-policy"].split("script-src")[1].split(";")[0]
        assert "<script>" not in r.text                                    # no inline scripts: the CSP forbids them
        assert c.get("/api/dashboard?fy=1999-00").status_code == 404
        assert c.get("/docs").status_code == 404                           # technical pages are off by default
        r = c.post("/api/ask_once", json={"question": "What was the total collection in Mysuru zilla in FY 2024-25?"})
        j = r.json()
        assert r.status_code == 200 and j["answerable"] and "₹124.30 crore" in j["answer"] and not j["sql"] and not j["route"]
        e = c.post("/api/ask_once", json={"question": "  "}).json()
        assert e["answerable"] is False and "Please type a question" in e["answer"]
        assert c.post("/api/ask_once", json={"question": "x" * 5000}).status_code == 400
        with c.stream("POST", "/api/ask", json={"question": "What is DCB?"}) as s:
            body = "".join(s.iter_text())
        assert "event: status" in body and "event: answer_chunk" in body and body.rstrip().endswith("}")
        assert "event: done" in body

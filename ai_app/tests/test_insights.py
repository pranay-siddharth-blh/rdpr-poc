import json
import re
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import insights
from app.config import settings
from app.dashboard_data import DashboardNotFound
from conftest import run

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


@pytest.fixture(scope="module")
def raw():
    c = sqlite3.connect(f"file:{settings.db_path.as_posix()}?mode=ro", uri=True)
    yield c
    c.close()


# ---------------------------------------------------------------- map
def test_map_components_add_up_to_the_state(db, raw):
    m = run(insights.map_data(db, "2025-26"))
    assert len(m["zillas"]) == 31
    coll, dem = raw.execute("SELECT SUM(total_collection), SUM(total_demand) FROM fact_rev_dcb_register WHERE fy_id = 'FY2526'").fetchone()
    assert abs(sum(z["collection"] for z in m["zillas"]) - coll) < 1 and abs(sum(z["demand"] for z in m["zillas"]) - dem) < 1
    assert sum(z["gps"] for z in m["zillas"]) == 6099
    assert sum(z["active_staff"] for z in m["zillas"]) == raw.execute("SELECT COUNT(*) FROM fact_hr_staff WHERE employment_status = 'Active'").fetchone()[0]


# ---------------------------------------------------------------- GP report card
def test_gp_search_and_card_match_raw_tables(db, raw):
    assert any(r["id"] == "G4938" for r in insights.gp_search("siddapura") if r["taluk"] == "Madhugiri")
    assert insights.gp_search("a") == []
    d = run(insights.gp_card(db, "G4938", "2025-26"))
    c, dem = raw.execute("SELECT total_collection, total_demand FROM fact_rev_dcb_register WHERE fy_id = 'FY2526' AND gp_id = 'G4938'").fetchone()
    cur = next(t for t in d["trend"] if t["fy"] == "2025-26")
    assert abs(cur["total_collection"] - c) < 0.01 and cur["collection_pct"] == round(100 * c / dem, 2)
    assert len(d["trend"]) == 5 and d["rank"]["state"][1] == 6099 and 1 <= d["rank"]["taluk"][0] <= d["rank"]["taluk"][1]
    closed, total = raw.execute("SELECT SUM(is_closed), COUNT(*) FROM fact_fin_gp_year_closure WHERE fy_id = 'FY2526' AND gp_id = 'G4938'").fetchone()
    assert (d["finance"]["books_closed"], d["finance"]["books_total"]) == (closed, total)
    assert abs(sum(m["collection"] for m in d["monthly_collection"]) - c) < 0.5
    # taluk peers are SUM/SUM over the taluk's GPs
    tc, td = raw.execute("SELECT SUM(total_collection), SUM(total_demand) FROM fact_rev_dcb_register r JOIN dim_gp g USING(gp_id) "
                         "WHERE r.fy_id = 'FY2526' AND g.taluk_id = (SELECT taluk_id FROM dim_gp WHERE gp_id = 'G4938')").fetchone()
    assert d["peers"]["taluk"] == round(100 * tc / td, 2)
    # nothing person-level in the card
    assert "staff_name" not in json.dumps(d) and "date_of_birth" not in json.dumps(d)


def test_unknown_gp_and_fy(db):
    for gp, fy in (("G9999", None), ("G0001", "1999-00")):
        with pytest.raises(DashboardNotFound):
            run(insights.gp_card(db, gp, fy))


# ---------------------------------------------------------------- compare
def test_compare_two_zillas(db):
    c = run(insights.compare(db, "Mysuru", "Hassan", "2025-26"))
    assert c["a"]["zilla"] == "Mysuru" and c["b"]["zilla"] == "Hassan"
    assert sum(c["wins"].values()) == len(c["verdicts"])
    for v in c["verdicts"]:
        better_high = v["metric"] != "cmp_pending_eo"
        assert v["ahead"] == (c["a"]["zilla"] if (v["a"] > v["b"]) == better_high else c["b"]["zilla"])
    with pytest.raises(DashboardNotFound):
        run(insights.compare(db, "Mysuru", "Mysuru", "2025-26"))


# ---------------------------------------------------------------- alerts
def test_alerts_are_consistent_with_the_data(db, raw):
    a = run(insights.alerts(db, "2025-26"))
    low = next(x for x in a["alerts"] if x["id"] == "low_collection")
    gold = raw.execute("SELECT COUNT(*) FROM fact_rev_dcb_register WHERE fy_id = 'FY2526' AND total_demand > 0 AND total_collection * 5.0 < total_demand").fetchone()[0]
    assert low["count"] == gold and all(i["value"] < 20 for i in low["items"])
    eo = next(x for x in a["alerts"] if x["id"] == "eo_backlog")
    assert eo["count"] == raw.execute("SELECT SUM(staff_approval_pending_at_eo) FROM fact_hr_eo_approval WHERE fy_id = 'FY2526'").fetchone()[0]
    assert a["counts"]["high"] + a["counts"]["medium"] + a["counts"]["low"] == len(a["alerts"])
    # part-year: year-end alerts are not raised
    p = run(insights.alerts(db, "2026-27"))
    assert p["partial_fy"] and not any(x["id"] in ("no_books_closed", "collection_fall") for x in p["alerts"])


# ---------------------------------------------------------------- HTTP + front-end wiring
def test_new_pages_and_endpoints():
    from app.main import app
    with TestClient(app) as c:
        for path in ("/api/map?fy=2025-26", "/api/alerts?fy=2025-26", "/api/gp/search?q=siddap", "/api/gp/G0001?fy=2024-25",
                     "/api/compare?a=Mysuru&b=Hassan&fy=2025-26"):
            assert c.get(path).status_code == 200, path
        for old in ("/gp", "/compare"):          # the old pages were folded into the dashboard
            r = c.get(old, follow_redirects=False)
            assert r.status_code == 307 and r.headers["location"] == "/dashboard", old
        assert c.get("/api/gp/G9999").status_code == 404
        assert c.get("/api/compare?a=Mysuru&b=Atlantis").status_code == 404
        assert c.get("/api/alerts?fy=1999-00").status_code == 404


def test_every_page_references_existing_assets_and_nothing_from_a_cdn():
    """Chart.js and the fonts are served from /static/vendor, so the pages work on networks that block CDNs."""
    for f in STATIC.glob("*.html"):
        h = f.read_text(encoding="utf-8")
        for ref in re.findall(r'(?:src|href)="/static/([^"]+)"', h):
            # asset URLs carry a ?v=<hash> cache buster; the file on disk is the part before it
            assert (STATIC / ref.split("?")[0]).exists(), (f.name, ref)
        assert "https://" not in re.sub(r"<a [^>]+>", "", h), f.name
    fonts = (STATIC / "vendor" / "fonts.css").read_text(encoding="utf-8")
    for ref in re.findall(r"url\(/static/(vendor/fonts/[^)]+)\)", fonts):
        assert (STATIC / ref).exists(), ref


@pytest.mark.parametrize("page, script", [("dashboard.html", "dashboard.js"), ("insights.html", "insights.js"), ("chat.html", "chat.js")])
def test_kpcl_layout_pages_translate_every_label(page, script):
    """The dashboard, insights and AI mode pages (KPCL layout) each carry an English and a Kannada label table; every
    data-i18n key on the page must exist in both."""
    h = (STATIC / page).read_text(encoding="utf-8")
    js = (STATIC / script).read_text(encoding="utf-8")
    en = js[js.index("  en: {"):js.index("  kn: {")]
    kn = js[js.index("  kn: {"):js.index("};", js.index("  kn: {"))]
    keys = lambda block: set(re.findall(r"(?:^\s*|[,{]\s*)([A-Za-z][A-Za-z0-9]*):\s", block, re.M))
    used = set(re.findall(r'data-i18n(?:-html|-placeholder)?="([A-Za-z0-9]+)"', h))
    assert used and not (used - keys(en)), sorted(used - keys(en))
    assert not (used - keys(kn)), sorted(used - keys(kn))
    assert "<script>" not in h and "#072577" not in h + js, "no inline script, and no KPCL navy left"


def test_insights_cards_come_from_the_dashboard_figures(db):
    from app.dashboard_data import build_dashboard
    ins = run(insights.build_insights(db, "2025-26"))
    d = run(build_dashboard(db, "2025-26"))
    card = {c["topic"]: c for c in ins["cards"]}
    assert card["Collection percentage"]["value"] == d["revenue"]["collection_pct"]
    assert card["Total collection"]["value"] == round(d["revenue"]["total_collection"] / 1e7, 2)
    assert card["Registrations pending at the EO"]["value"] == d["hrms"]["pending_at_eo"]
    assert sum(ins["summary"].values()) == len(ins["cards"]) and len(ins["zilla_index"]) == 31
    # a part year gets no year-on-year change and no good / bad verdict from one
    p = run(insights.build_insights(db, "2026-27"))
    assert all(c["delta"] is None for c in p["cards"])


def test_mis_report_download_and_preview_match_the_dashboard():
    import io
    import openpyxl
    from app.main import app
    with TestClient(app) as c:
        r = c.get("/api/mis-report?fy=2024-25&zilla=Mysuru&kind=all")
        assert r.status_code == 200 and "RDPR_MIS_Complete_Mysuru_FY2024-25.xlsx" in r.headers["content-disposition"]
        wb = openpyxl.load_workbook(io.BytesIO(r.content))
        assert wb.sheetnames == ["Summary", "Revenue", "Finance & Accounting", "HRMS"]
        d = c.get("/api/dashboard?fy=2024-25&zilla=Mysuru").json()
        cells = {row[0]: row[1] for row in wb["Summary"].iter_rows(values_only=True) if row and row[0]}
        assert abs(cells["Total collection"] - d["revenue"]["total_collection"]) < 0.01
        assert "CHECK" not in [row[3] for row in wb["Summary"].iter_rows(values_only=True) if len(row) > 3]
        v = c.get("/api/mis-report/view?fy=2024-25&kind=current&module=hrms").json()
        assert [s["name"] for s in v["sheets"]] == ["Summary", "HRMS"] and "xv-grid" in v["sheets"][0]["html"]
        for bad in ("/api/mis-report?fy=1999-00", "/api/mis-report?kind=x", "/api/mis-report?module=x", "/api/insights?fy=1999-00"):
            assert c.get(bad).status_code == 404, bad
        assert c.get("/insights").status_code == 200


def test_asset_version_stamps_match_the_files_on_disk():
    """Every /static/*.js|css reference carries ?v=<sha256[:8]> of that file.

    The stamp is what makes a browser fetch a changed script instead of reusing its cached copy: a stale stamp
    means an edit silently does not reach the page. Re-stamp the pages after changing any asset.
    """
    import hashlib
    stale = []
    for f in STATIC.glob("*.html"):
        for ref in re.findall(r'(?:src|href)="/static/([^"?]+\.(?:js|css))\?v=([0-9a-f]+)"', f.read_text(encoding="utf-8")):
            path, stamp = STATIC / ref[0], ref[1]
            actual = hashlib.sha256(path.read_bytes()).hexdigest()[:len(stamp)]
            if actual != stamp:
                stale.append(f"{f.name} -> {ref[0]}: page says {stamp}, file is {actual}")
    assert not stale, "stale cache-busting stamps:\n  " + "\n  ".join(stale)

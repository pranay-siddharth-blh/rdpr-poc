"""
MIS report: the dashboard's selection (FY, zilla) as an Excel workbook, and the same cells as an on-screen preview.

Both the .xlsx and the preview are drawn from one list of sheets built here from build_dashboard(), the payload the
dashboard page itself shows, so the download, the preview and the screen cannot disagree. Every sheet ends with
integrity checks (parts add up to the whole) that travel with the file.

  kind = "current"  Summary + the module shown on screen (revenue / finance / hrms)
  kind = "all"      Summary + Revenue + Finance & Accounting + HRMS
"""
from __future__ import annotations

import html
from io import BytesIO

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

WINE, WINE_DEEP, GOLD, GOLD_SOFT, LINE = "7B1E34", "3F0B19", "B8892B", "F7F1E3", "E4D3AB"
MODULES = ("revenue", "finance", "hrms")
_TAB = {"Summary": WINE, "Revenue": "C25B74", "Finance & Accounting": GOLD, "HRMS": "1F9D57", "Report": WINE, "Data": "C25B74", "Notes": GOLD}
_FMT = {"inr": "#,##0", "pct": '0.00"%"', "int": "#,##0", "cr": '#,##0.00" cr"'}


def _rows_block(title: str, head: list[str], rows: list[list], kinds: list[str]) -> list[list]:
    out = [[(title, "section")] + [(None, "section")] * (len(head) - 1), [(h, "head") for h in head]]
    for r in rows:
        out.append([(v, k) for v, k in zip(r, kinds)])
    out.append([])
    return out


def _scope(d: dict) -> str:
    part = " (part-year: April to September 2026)" if d["partial_fy"] else ""
    return f"{d['zilla'] + ' zilla' if d['zilla'] else 'Karnataka (all zillas)'} · FY {d['fy']}{part} · {d['gps']:,} GPs · data to {d['data_as_of']}"


def _check(label: str, a, b, tol: float = 1.0) -> list:
    ok = a is not None and b is not None and abs(a - b) <= tol
    return [label, a, b, "PASS" if ok else "CHECK"]


def _summary(d: dict) -> dict:
    r, f, h = d["revenue"], d["finance"], d["hrms"]
    rows = [["Total demand (arrears + current)", r["total_demand"], "₹"], ["Total collection", r["total_collection"], "₹"],
            ["Collection %", r["collection_pct"], "%"], ["Outstanding balance", r["balance"], "₹"],
            ["GPs that closed every book", f["gps_all_closed"], "GPs"], ["GPs that closed every book %", f["gps_all_closed_pct"], "%"],
            ["Scheme books closed %", f["books_closed_pct"], "%"], ["Scheme receipts", f["receipts"], "₹"],
            ["Scheme expenditure", f["expenditure"], "₹"], ["Active staff", h["active_staff"], "staff"],
            ["Staff registrations pending at the EO", h["pending_at_eo"], "registrations"], ["Elected seats filled %", h["seats_filled_pct"], "%"]]
    kinds = [["text", "inr" if u == "₹" else "pct" if u == "%" else "int", "text"] for _, _, u in rows]
    body = [[("Measure", "head"), ("Value", "head"), ("Unit", "head")]] + [[(a, k[0]), (b, k[1]), (c, k[2])] for (a, b, c), k in zip(rows, kinds)]
    checks = [_check("Months add up to the year's collection", sum(m["collection"] or 0 for m in d["monthly_collection"]), r["total_collection"]),
              _check("Revenue heads add up to the year's collection", sum(x["collection"] or 0 for x in d["by_head"]), r["total_collection"]),
              _check(f"{d['league_label'].title()}s add up to the total collection", sum(x["collection"] or 0 for x in d["league"]), r["total_collection"])]
    cells = [[("Key figures", "section"), (None, "section"), (None, "section")]] + body + [[]]
    cells += _rows_block("Integrity checks", ["Check", "Parts", "Whole", "Result"], checks, ["text", "inr", "inr", "flag"])
    return {"name": "Summary", "widths": [46, 22, 22, 12], "cells": cells}


def _revenue(d: dict) -> dict:
    cells = []
    cells += _rows_block("Five-year trend", ["Financial year", "Total demand (₹)", "Total collection (₹)", "Collection %"],
                         [[t["fy"], t["total_demand"], t["total_collection"], t["collection_pct"]] for t in d["trend"]],
                         ["text", "inr", "inr", "pct"])
    cells += _rows_block(f"Monthly collection, FY {d['fy']}" + (f" against FY {d['prev_fy']}" if d.get("prev_fy") else ""),
                         ["Month", f"FY {d['fy']} (₹)", f"FY {d.get('prev_fy') or '-'} (₹)"],
                         [[m["label"], m["collection"], m["collection_prev"]] for m in d["months"]], ["text", "inr", "inr"])
    cells += _rows_block("By revenue head", ["Revenue head", "Demand (₹)", "Collection (₹)", "Balance (₹)", "Collection %"],
                         [[x["head"], x["demand"], x["collection"], x.get("balance"), x["collection_pct"]] for x in d["by_head"]],
                         ["text", "inr", "inr", "inr", "pct"])
    cells += _rows_block("By property category", ["Property category", "Demand (₹)", "Collection (₹)", "Balance (₹)"],
                         [[str(x["category"]).replace("_", " "), x["demand"], x["collection"], x.get("balance")] for x in d["by_property"]],
                         ["text", "inr", "inr", "inr"])
    cells += _rows_block(f"By {d['league_label']}", [d["league_label"].title(), "GPs", "Demand (₹)", "Collection (₹)", "Collection %", "Change on last year %"],
                         [[x["name"], x.get("gps"), x["demand"], x["collection"], x["collection_pct"], x.get("yoy")] for x in d["league"]],
                         ["text", "int", "inr", "inr", "pct", "pct"])
    return {"name": "Revenue", "widths": [34, 20, 22, 22, 18, 20], "cells": cells}


def _finance(d: dict) -> dict:
    f = d["finance"]
    cells = []
    cells += _rows_block("Year-end book closure by scheme", ["Scheme", "Books (GPs keeping it)", "Closed %"],
                         [[x["scheme"], x["books"], x["closed_pct"]] for x in f["by_scheme"]], ["text", "int", "pct"])
    cells += _rows_block("Month-end book closure", ["Month", "Books closed %"],
                         [[m["month"], m["closed_pct"]] for m in f["closure_months"]], ["text", "pct"])
    cells += _rows_block("Receipts and expenditure by scheme", ["Scheme", "Receipts (₹)", "Expenditure (₹)"],
                         [[x["scheme"], x["receipts"], x["expenditure"]] for x in f["scheme_money"]], ["text", "inr", "inr"])
    cells += _rows_block("Receipts and expenditure by month", ["Month", "Receipts (₹)", "Expenditure (₹)", f"Receipts FY {d.get('prev_fy') or '-'} (₹)"],
                         [[m["label"], m["receipts"], m["expenditure"], m["receipts_prev"]] for m in d["months"]], ["text", "inr", "inr", "inr"])
    cells += _rows_block("Integrity checks", ["Check", "Parts", "Whole", "Result"],
                         [_check("Schemes add up to the year's receipts", sum(x["receipts"] or 0 for x in f["scheme_money"]), f["receipts"]),
                          _check("Months add up to the year's receipts", sum(m["receipts"] or 0 for m in d["months"]), f["receipts"])],
                         ["text", "inr", "inr", "flag"])
    return {"name": "Finance & Accounting", "widths": [46, 22, 20, 24], "cells": cells}


def _hrms(d: dict) -> dict:
    h = d["hrms"]
    cells = []
    cells += _rows_block("Staff and approvals", ["Measure", "Value"],
                         [["Active staff", h["active_staff"]], ["Registrations sent to the EO", h["sent_to_eo"]],
                          ["Approved by the EO", h["approved_by_eo"]], ["Pending at the EO", h["pending_at_eo"]],
                          ["Rejected by the EO", h["rejected_by_eo"]], ["Seats in GP bodies", h["seats"]],
                          ["Elected members registered", h["elected_members"]], ["GPs with a President", h["gps_with_president"]]],
                         ["text", "int"])
    cells += _rows_block("Active staff by designation (top 10)", ["Designation", "Active staff"],
                         [[x["designation"], x["staff"]] for x in h["designations"]], ["text", "int"])
    cells += _rows_block("Active staff by staff type", ["Staff type", "Active staff"], [[x["type"], x["staff"]] for x in h["staff_types"]], ["text", "int"])
    cells += _rows_block(f"Salary bill progress, {h['salary_month'] or '-'}",
                         ["Staff type", "Staff", "Bills generated", "PDO signed", "President signed", "Bank processed", "Paid", "Rejected"],
                         [[x["type"], x["staff"], x["bills_generated"], x["pdo_signed"], x["president_signed"], x["bank_processed"], x["paid"], x["rejected"]]
                          for x in h["salary_funnel"]], ["text"] + ["int"] * 7)
    cells += _rows_block("Salaries by month", ["Month", "Staff paid", "Rejected by bank", "Staff on payroll"],
                         [[m["label"], m["paid"], m["rejected"], m["staff"]] for m in d["months"]], ["text", "int", "int", "int"])
    return {"name": "HRMS", "widths": [40, 14, 16, 14, 16, 16, 12, 12], "cells": cells}


def build_sheets(d: dict, kind: str, module: str) -> list[dict]:
    parts = {"revenue": _revenue, "finance": _finance, "hrms": _hrms}
    mods = MODULES if kind == "all" else (module if module in MODULES else "revenue",)
    sheets = [_summary(d)] + [parts[m](d) for m in mods]
    for s in sheets:
        head = [[(f"Rural Development & Panchayat Raj · MIS report · {s['name']}", "title")], [(_scope(d), "sub")], []]
        s["cells"] = head + s["cells"]
        s["tab"] = _TAB[s["name"]]
        s["footer"] = "Synthetic proof-of-concept data · figures match the dashboard for the same FY and zilla"
    return sheets


def file_name(d: dict, kind: str, module: str) -> str:
    scope = (d["zilla"] or "Karnataka").replace(" ", "_").replace("(", "").replace(")", "")
    what = "Complete" if kind == "all" else {"revenue": "Revenue", "finance": "Finance", "hrms": "HRMS"}.get(module, "Revenue")
    return f"RDPR_MIS_{what}_{scope}_FY{d['fy']}.xlsx"


# ---------------------------------------------------------------------------------------------- Excel
_THIN = Side(style="thin", color="E6DCDF")


def build_xlsx(sheets: list[dict], title: str) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for s in sheets:
        ws = wb.create_sheet(s["name"][:31])
        ws.sheet_properties.tabColor = s["tab"]
        ws.sheet_view.showGridLines = False
        for i, w in enumerate(s["widths"], start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
        for r, row in enumerate(s["cells"], start=1):
            for c, (v, k) in enumerate(row, start=1):
                cell = ws.cell(row=r, column=c)
                if v is not None:
                    cell.value = v
                    if isinstance(v, str):
                        cell.data_type = "s"           # never a formula, whatever the text starts with
                if k in _FMT and isinstance(v, (int, float)):
                    cell.number_format = _FMT[k]
                if k == "title":
                    cell.font = Font(bold=True, size=14, color=WINE)
                elif k == "sub":
                    cell.font = Font(italic=True, size=10, color="5F6B7D")
                elif k == "section":
                    cell.font = Font(bold=True, color="FFFFFF")
                    cell.fill = PatternFill("solid", fgColor=WINE)
                elif k == "head":
                    cell.font = Font(bold=True, color=WINE_DEEP)
                    cell.fill = PatternFill("solid", fgColor=GOLD_SOFT)
                    cell.border = Border(bottom=Side(style="thin", color=LINE))
                    cell.alignment = Alignment(wrap_text=True, vertical="center")
                elif k == "flag":
                    cell.font = Font(bold=True, color="1F9D57" if v == "PASS" else "C8372D")
                elif k:
                    cell.border = Border(bottom=_THIN)
        ws.freeze_panes = s.get("freeze", "A4")
        ws.oddFooter.center.text = s["footer"]
        ch = s.get("chart")
        if ch:
            c = (LineChart if ch["type"] == "line" else BarChart)()
            c.title, c.height, c.width = ch["title"], 9, 18
            c.y_axis.title = ch.get("y_title", "")
            c.add_data(Reference(ws, min_col=ch["value_col"], min_row=ch["header_row"], max_row=ch["last_row"]), titles_from_data=True)
            c.set_categories(Reference(ws, min_col=ch["label_col"], min_row=ch["header_row"] + 1, max_row=ch["last_row"]))
            c.legend = None
            ws.add_chart(c, ch.get("anchor", "H4"))
    wb.properties.title = title
    wb.properties.creator = "RDPR Data Assistant"
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------------------------- preview
def _show(v, k) -> str:
    if v is None:
        return ""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if k == "pct":
            return f"{v:,.2f}%"
        return f"{v:,.0f}" if k in ("inr", "int") else f"{v:,.2f}"
    return str(v)


def view(sheets: list[dict], name: str) -> dict:
    """The sheets as Excel-style HTML grids (column letters, row numbers) for report-viewer.js."""
    out = []
    for s in sheets:
        ncol = max(len(s["widths"]), max((len(r) for r in s["cells"]), default=0))
        px = [int((s["widths"][i] if i < len(s["widths"]) else 12) * 7 + 5) for i in range(ncol)]
        parts = ['<table class="xv-grid nogrid"><colgroup><col style="width:40px">'
                 + "".join(f'<col style="width:{w}px">' for w in px) + "</colgroup>",
                 '<thead><tr><th class="xv-corner"></th>' + "".join(f"<th>{get_column_letter(i + 1)}</th>" for i in range(ncol)) + "</tr></thead><tbody>"]
        for r, row in enumerate(s["cells"], start=1):
            tds = []
            for c in range(ncol):
                v, k = row[c] if c < len(row) else (None, "")
                style = {"title": "font-weight:700;font-size:17px;color:#7b1e34",
                         "sub": "font-style:italic;color:#5f6b7d",
                         "section": "background:#7b1e34;color:#fff;font-weight:700",
                         "head": "background:#f7f1e3;color:#3f0b19;font-weight:700;border-bottom:1px solid #e4d3ab",
                         "flag": f"font-weight:700;color:{'#1f9d57' if v == 'PASS' else '#c8372d'}"}.get(k, "border-bottom:1px solid #eee6e8" if k else "")
                align = ";text-align:right" if isinstance(v, (int, float)) and not isinstance(v, bool) else ""
                tds.append(f'<td style="{style}{align}">{html.escape(_show(v, k))}</td>')
            parts.append(f'<tr class="{"xv-sticky" if r == 3 else ""}"><th class="xv-row">{r}</th>{"".join(tds)}</tr>')
        parts.append("</tbody></table>")
        charts = []
        ch = s.get("chart")
        if ch:
            rows = s["cells"][ch["header_row"]:ch["last_row"]]
            charts.append({"left": 40 + sum(px) + 20, "top": 30, "width": 560, "height": 300, "title": ch["title"], "y_title": ch.get("y_title", ""),
                           "legend": False, "labels": [str(r[ch["label_col"] - 1][0]) for r in rows],
                           "datasets": [{"type": "line" if ch["type"] == "line" else "bar", "label": ch["title"],
                                         "data": [r[ch["value_col"] - 1][0] for r in rows], "color": "#7b1e34"}]})
        out.append({"name": s["name"], "tab_color": "#" + s["tab"], "width": 40 + sum(px) + (620 if ch else 0),
                    "height": max(22 + 21 * len(s["cells"]) + 40, 360 if ch else 0),
                    "html": "".join(parts), "charts": charts, "footer": s["footer"]})
    return {"name": name, "sheets": out}


def failed_checks(sheets: list[dict]) -> list[str]:
    """Integrity checks that did not pass: the report is then 'under review' (HTTP 409), never a wrong file."""
    out = []
    for s in sheets:
        for row in s["cells"]:
            if row and len(row) >= 4 and row[3] == ("CHECK", "flag"):
                out.append(f"{s['name']}: {row[0][0]}")
    return out

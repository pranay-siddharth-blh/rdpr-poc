/* MIS report downloads: a "Download report" control on the Revenue, Finance & Accounting and HRMS section
   headers, each offering Excel and PDF, for whatever zilla/FY the dashboard filter is currently set to.

   Nothing here queries the database again: every figure is read straight out of window.RDPR.data, the same
   payload the on-screen charts and KPI tiles were drawn from (dashboard.js sets it after each /api/dashboard
   call), so an exported report can never disagree with what is on the page when it was downloaded.

   Excel: written as an HTML table with an .xls extension, which Excel opens natively and keeps numbers as
   numbers. PDF: the browser's own print-to-PDF, over a dedicated print-only view built from the same data
   (not a screenshot of the charts), so the PDF is exact figures, not an image of a chart axis. */
(function () {
  "use strict";

  const inr = (v) => (v === null || v === undefined ? "" : Math.round(Number(v)).toLocaleString("en-IN"));
  const pct = (v) => (v === null || v === undefined ? "" : Number(v).toFixed(2) + "%");

  // one definition per module: its on-screen KPI figures plus its breakdown tables, each [title, head, rows]
  function moduleTables(mod, d) {
    const r = d.revenue || {}, f = d.finance || {}, h = d.hrms || {};
    if (mod === "revenue") {
      return [
        ["Revenue - summary", ["Measure", "Value"], [
          ["Arrears brought forward", inr(r.arrears)], ["Demand raised this year", inr(r.year_demand)],
          ["Total demand", inr(r.total_demand)], ["Total collection", inr(r.total_collection)],
          ["Collection %", pct(r.collection_pct)], ["Adjustments", inr(r.adjustments)],
          ["Outstanding balance", inr(r.balance)],
        ]],
        ["Collection trend by year", ["Financial year", "Total demand", "Total collection", "Collection %"],
          (d.trend || []).map((x) => [x.fy, inr(x.total_demand), inr(x.total_collection), pct(x.collection_pct)])],
        ["Monthly collection", ["Month", "Collection"],
          (d.monthly_collection || []).map((m) => [m.month, inr(m.collection)])],
        ["Collection by " + (d.league_label || "zilla"), [d.league_label === "taluk" ? "Taluk" : "Zilla", "Collection %"],
          (d.league || []).map((x) => [x.name, pct(x.collection_pct)])],
        ["Collection by revenue head", ["Revenue head", "Collection"],
          (d.by_head || []).map((x) => [x.head, inr(x.collection)])],
        ["Demand and collection by property category", ["Property category", "Demand", "Collection"],
          (d.by_property || []).map((x) => [String(x.category).replace(/_/g, " "), inr(x.demand), inr(x.collection)])],
      ];
    }
    if (mod === "finance") {
      return [
        ["Finance & Accounting - summary", ["Measure", "Value"], [
          ["GPs that closed all books", (f.gps_all_closed ?? "") + " of " + (f.gps ?? "")],
          ["GPs that closed all books %", pct(f.gps_all_closed_pct)],
          ["Scheme books closed %", pct(f.books_closed_pct)],
          ["Receipts", inr(f.receipts)], ["Expenditure", inr(f.expenditure)],
          ["Closing balance", inr(f.closing_balance)], ["As of", f.closing_month || ""],
        ]],
        ["Book closure % by scheme", ["Scheme", "Books closed %"],
          (f.by_scheme || []).map((x) => [x.scheme, pct(x.closed_pct)])],
        ["Book closure % by month", ["Month", "Books closed %"],
          (f.closure_months || []).map((m) => [m.month, pct(m.closed_pct)])],
        ["Receipts and expenditure by scheme", ["Scheme", "Receipts", "Expenditure"],
          (f.scheme_money || []).map((x) => [x.scheme, inr(x.receipts), inr(x.expenditure)])],
      ];
    }
    // hrms
    return [
      ["HRMS - summary", ["Measure", "Value"], [
        ["Active staff", inr(h.active_staff)], ["Sent to EO", inr(h.sent_to_eo)],
        ["Approved by EO", inr(h.approved_by_eo)], ["Pending at EO", inr(h.pending_at_eo)],
        ["Rejected by EO", inr(h.rejected_by_eo)],
        ["Elected members", (h.elected_members ?? "") + " of " + (h.seats ?? "")],
        ["Seats filled %", pct(h.seats_filled_pct)],
        ["GPs with a President", (h.gps_with_president ?? "") + " of " + (h.gps_reporting ?? "")],
      ]],
      ["Active staff by designation", ["Designation", "Active staff"],
        (h.designations || []).map((x) => [x.designation, inr(x.staff)])],
      ["Active staff by staff type", ["Staff type", "Active staff"],
        (h.staff_types || []).map((x) => [x.type, inr(x.staff)])],
      ["Salary bills by month", ["Month", "Paid", "Rejected by bank"],
        (h.salary_trend || []).map((m) => [m.month, inr(m.paid), inr(m.rejected)])],
    ];
  }

  const MOD_LABEL = { revenue: "Revenue", finance: "Finance & Accounting", hrms: "HRMS" };

  function scopeLine(d) {
    return (d.zilla ? d.zilla + " zilla" : "Karnataka (all zillas)") + " - FY " + d.fy +
      " . " + (d.gps ?? "") + " Gram Panchayats . data to " + d.data_as_of +
      (d.partial_fy ? " (part-year)" : "");
  }

  // ---------------------------------------------------------------------------------------------- Excel
  function excelDownload(mods) {
    const d = window.RDPR && window.RDPR.data;
    if (!d) return;
    const esc = (s) => String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const sheets = mods.map((mod) => {
      const rows = [["Rural Development & Panchayat Raj - " + MOD_LABEL[mod] + " MIS report"], [scopeLine(d)], []];
      moduleTables(mod, d).forEach(([title, head, body]) => {
        rows.push([title]);
        rows.push(head);
        body.forEach((r) => rows.push(r));
        rows.push([]);
      });
      const tbody = rows.map((r) => "<tr>" + r.map((c) => "<td>" + esc(c) + "</td>").join("") + "</tr>").join("");
      return "<table border=\"1\">" + tbody + "</table>";
    });
    // one HTML file, multiple <table>s: a single-module export is just one table, a full export several in
    // sequence. No library, no server round trip, and numbers stay numbers rather than becoming text cells.
    const html = "<html xmlns:x=\"urn:schemas-microsoft-com:office:excel\"><head><meta charset=\"utf-8\">" +
      "<style>table{border-collapse:collapse;margin-bottom:24px}td{padding:4px 8px}</style></head><body>" +
      sheets.join("<br><br>") + "</body></html>";
    const a = document.createElement("a");
    const zilla = (d.zilla || "karnataka").replace(/[^A-Za-z0-9]+/g, "-").toLowerCase();
    const name = mods.length === 1 ? mods[0] : "full";
    a.href = URL.createObjectURL(new Blob(["﻿" + html], { type: "application/vnd.ms-excel" }));
    a.download = "rdpr-mis-" + name + "-" + zilla + "-" + d.fy + ".xls";
    document.body.appendChild(a); a.click(); a.remove();
  }

  // ---------------------------------------------------------------------------------------------- PDF (print)
  function pdfDownload(mods) {
    const d = window.RDPR && window.RDPR.data;
    if (!d) return;
    const esc = (s) => String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const sections = mods.map((mod) => {
      const tables = moduleTables(mod, d).map(([title, head, body]) =>
        "<h3>" + esc(title) + "</h3><table><thead><tr>" +
        head.map((hd) => "<th>" + esc(hd) + "</th>").join("") + "</tr></thead><tbody>" +
        body.map((r) => "<tr>" + r.map((c) => "<td>" + esc(c) + "</td>").join("") + "</tr>").join("") +
        "</tbody></table>").join("");
      return "<section><h2>" + esc(MOD_LABEL[mod]) + "</h2>" + tables + "</section>";
    }).join("");
    const win = window.open("", "_blank");
    if (!win) { alert("Please allow pop-ups to print this report."); return; }
    win.document.write(
      "<!doctype html><html><head><meta charset='utf-8'><title>RDPR MIS report</title><style>" +
      "body{font:14px/1.5 Inter,Arial,sans-serif;color:#121f29;margin:24px}" +
      "h1{font-size:20px;margin:0 0 4px}h2{font-size:17px;color:#072577;margin:28px 0 6px;" +
      "border-bottom:2px solid #e54825;padding-bottom:4px}" +
      "h3{font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:#6b6c70;margin:16px 0 6px}" +
      "table{width:100%;border-collapse:collapse;margin-bottom:10px;font-size:13px}" +
      "th,td{border:1px solid #dde1ea;padding:5px 8px;text-align:left}th{background:#f3f4f7}" +
      "td:last-child,th:last-child{text-align:right}.meta{color:#6b6c70;margin-bottom:18px}" +
      "@media print{button{display:none}}</style></head><body>" +
      "<h1>Rural Development &amp; Panchayat Raj - MIS report</h1>" +
      "<div class='meta'>" + esc(scopeLine(d)) + "</div>" + sections +
      "<script>window.onload=function(){setTimeout(function(){window.print()},200)}</script>" +
      "</body></html>");
    win.document.close();
  }

  // ---------------------------------------------------------------------------------------------- UI
  function buildMenu(host, mods) {
    host.innerHTML =
      "<button type=\"button\" class=\"mis-btn\" data-i18n=\"dl_report\">Download report</button>" +
      "<div class=\"mis-menu\" hidden>" +
      "<button type=\"button\" data-fmt=\"xls\" data-i18n=\"dl_excel\">Excel (.xls)</button>" +
      "<button type=\"button\" data-fmt=\"pdf\" data-i18n=\"dl_pdf\">PDF (print)</button>" +
      "</div>";
    I18N.apply(host);
    const btn = host.querySelector(".mis-btn"), menu = host.querySelector(".mis-menu");
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      document.querySelectorAll(".mis-menu").forEach((m) => { if (m !== menu) m.hidden = true; });
      menu.hidden = !menu.hidden;
    });
    menu.querySelectorAll("button").forEach((b) => {
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        menu.hidden = true;
        if (b.dataset.fmt === "xls") excelDownload(mods); else pdfDownload(mods);
      });
    });
  }

  function init() {
    document.querySelectorAll(".mis-dl").forEach((host) => {
      const mod = host.getAttribute("data-mod");
      buildMenu(host, [mod]);
    });
    document.addEventListener("click", () => document.querySelectorAll(".mis-menu").forEach((m) => { m.hidden = true; }));
    document.addEventListener("langchange", () => {
      document.querySelectorAll(".mis-dl").forEach((host) => buildMenu(host, [host.getAttribute("data-mod")]));
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();

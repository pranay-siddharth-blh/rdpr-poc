/* Zilla report: clicking a zilla on the map (or an alert chip) opens a Revenue + Finance & Accounting + HRMS
   summary for that zilla, with an Excel download.

   Every figure comes from /api/dashboard?fy=&zilla=, the same reviewed queries the dashboard sections use, so the
   report cannot disagree with the rest of the page or with the chat. Nothing here recomputes a ratio. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  let state = { zilla: "", fy: "", data: null };

  const inr = (v) => (v === null || v === undefined ? "–" : I18N.money(Number(v)));
  const num = (v) => (v === null || v === undefined ? "–" : Math.round(Number(v)).toLocaleString("en-IN"));
  const pct = (v) => (v === null || v === undefined ? "–" : Number(v).toFixed(2) + "%");

  /* [label, value for the screen, raw value for the spreadsheet] */
  function blocks(d) {
    const r = d.revenue || {}, f = d.finance || {}, h = d.hrms || {};
    return [
      ["Revenue", [
        ["Arrears brought forward", inr(r.arrears), r.arrears],
        ["Demand raised this year", inr(r.year_demand), r.year_demand],
        ["Total demand", inr(r.total_demand), r.total_demand],
        ["Total collection", inr(r.total_collection), r.total_collection],
        ["Collection %", pct(r.collection_pct), r.collection_pct],
        ["Outstanding balance", inr(r.balance), r.balance],
      ]],
      ["Finance & Accounting", [
        ["GPs that closed all books", num(f.gps_all_closed) + " of " + num(f.gps), f.gps_all_closed],
        ["GPs that closed all books %", pct(f.gps_all_closed_pct), f.gps_all_closed_pct],
        ["Scheme books closed %", pct(f.books_closed_pct), f.books_closed_pct],
        ["Receipts", inr(f.receipts), f.receipts],
        ["Expenditure", inr(f.expenditure), f.expenditure],
        ["Closing balance", inr(f.closing_balance), f.closing_balance],
      ]],
      ["HRMS", [
        ["Active staff", num(h.active_staff), h.active_staff],
        ["Approved by the EO", num(h.approved_by_eo), h.approved_by_eo],
        ["Pending at the EO", num(h.pending_at_eo), h.pending_at_eo],
        ["Rejected by the EO", num(h.rejected_by_eo), h.rejected_by_eo],
        ["Elected members", num(h.elected_members) + " of " + num(h.seats), h.elected_members],
        ["Seats filled %", pct(h.seats_filled_pct), h.seats_filled_pct],
      ]],
    ];
  }

  function render() {
    const d = state.data;
    $("zrep-title").textContent = state.zilla + " — " + state.fy;
    $("zrep-sub").textContent = num(d.gps) + " Gram Panchayats · data to " + d.data_as_of +
      (d.partial_fy ? " · part-year" : "");
    $("zrep-body").innerHTML = blocks(d).map(([name, rows]) =>
      '<div class="zcol"><h4>' + name + "</h4><table class=\"ztab\"><tbody>" +
      rows.map(([k, v]) => "<tr><th>" + k + "</th><td>" + v + "</td></tr>").join("") +
      "</tbody></table></div>").join("");
    $("zreport").hidden = false;
  }

  /* Excel: an .xls workbook written as HTML, which Excel opens natively. No library, no server round-trip, and
     the numbers stay numbers (text/plain cells would arrive as text). */
  function excel() {
    const d = state.data;
    const esc = (s) => String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const rows = [
      ["Rural Development & Panchayat Raj — Zilla report"],
      ["Zilla", state.zilla], ["Financial year", state.fy],
      ["Gram Panchayats", d.gps], ["Data to", d.data_as_of], [],
    ];
    blocks(d).forEach(([name, items]) => {
      rows.push([name]);
      rows.push(["Measure", "Value"]);
      items.forEach(([k, , raw]) => rows.push([k, raw === null || raw === undefined ? "" : raw]));
      rows.push([]);
    });
    const body = rows.map((r) => "<tr>" + r.map((c) =>
      (typeof c === "number" ? '<td style="mso-number-format:\\@">' : "<td>") + esc(c) + "</td>").join("") + "</tr>").join("");
    const html = '<html xmlns:x="urn:schemas-microsoft-com:office:excel"><head><meta charset="utf-8">' +
      "<style>th,td{border:1px solid #ccc;padding:4px}</style></head><body><table>" + body + "</table></body></html>";
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + html], { type: "application/vnd.ms-excel" }));
    a.download = "rdpr-" + state.zilla.replace(/[^A-Za-z0-9]+/g, "-").toLowerCase() + "-" + state.fy + ".xls";
    document.body.appendChild(a); a.click(); a.remove();
  }

  async function open(zilla, fy) {
    if (!zilla) { $("zreport").hidden = true; return; }
    state.zilla = zilla;
    state.fy = fy || ($("fy") && $("fy").value) || "";
    try {
      const url = "/api/dashboard?fy=" + encodeURIComponent(state.fy) + "&zilla=" + encodeURIComponent(zilla);
      state.data = await (await fetch(url)).json();
      render();
      $("zreport").scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (e) {
      console.error("zilla report failed", e);
    }
  }

  function init() {
    if (!$("zreport")) return;
    // the map and the alerts panel both announce a zilla this way
    document.addEventListener("selectzilla", (e) => open(e.detail, $("fy") && $("fy").value));
    document.addEventListener("dashchange", (e) => { if (state.zilla && e.detail && e.detail.fy !== state.fy) open(state.zilla, e.detail.fy); });
    $("zrep-close").addEventListener("click", () => { $("zreport").hidden = true; });
    $("zrep-xls").addEventListener("click", excel);
    $("zrep-open").addEventListener("click", () => {
      // the dashboard filter is already on this zilla; show the full Revenue view
      location.hash = "revenue";
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();

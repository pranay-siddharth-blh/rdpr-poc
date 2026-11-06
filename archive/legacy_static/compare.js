/* Side-by-side comparison of two zillas for one financial year (from /api/compare). */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const { C, num, pct, inr } = VIZ;
  const t = I18N.t;
  const st = { opts: null, data: null };
  const qs = new URLSearchParams(location.search);

  function fillSelects() {
    const o = st.opts, keep = { za: $("za").value || qs.get("a") || "Mysuru", zb: $("zb").value || qs.get("b") || "Hassan", fy: $("fy").value || qs.get("fy") || o.default_fy };
    ["za", "zb"].forEach((id) => { $(id).innerHTML = o.zillas.map((z) => `<option value="${z}"${z === keep[id] ? " selected" : ""}>${I18N.zilla(z)}</option>`).join(""); });
    $("fy").innerHTML = o.fiscal_years.map((y) => `<option value="${y}"${y === keep.fy ? " selected" : ""}>${y}${y === o.partial_fy ? " (" + t("part_year") + ")" : ""}</option>`).join("");
  }

  function cell(v, kind) {
    if (v === null || v === undefined) return "–";
    return kind === "pct" ? pct(v) : kind === "inr" ? inr(v) : kind === "num1" ? Number(v).toFixed(1) : num(v);
  }

  function render() {
    const d = st.data;
    if (!d) return;
    const A = d.a, B = d.b, za = I18N.zilla(A.zilla), zb = I18N.zilla(B.zilla), lead = d.leader;
    const total = d.verdicts.length, wins = lead ? d.wins[lead] : 0;
    const head = lead ? `${t("cmp_summary", { w: I18N.zilla(lead), n: wins, t: total })}` : t("cmp_tie");
    // rows: [label, key, kind, higherIsBetter]
    const rows = [["cmp_gps", "gps", "num", null], ["k_total_demand", "total_demand", "inr", null], ["k_total_collection", "total_collection", "inr", true],
      ["cmp_collection_pct", "collection_pct", "pct", true], ["cmp_growth", "collection_growth_pct", "pct", true], ["cmp_collection_per_gp", "collection_per_gp", "inr", true],
      ["k_balance", "balance", "inr", false], ["cmp_books_closed", "books_closed_pct", "pct", true], ["cmp_all_closed", "gps_all_closed_pct", "pct", true],
      ["k_receipts", "receipts", "inr", null], ["k_expenditure", "expenditure", "inr", null], ["k_active_staff", "active_staff", "num", null],
      ["cmp_staff_per_gp", "staff_per_gp", "num1", null], ["cmp_pending_eo", "pending_at_eo", "num", false], ["cmp_seats_filled", "seats_filled_pct", "pct", true]];
    const won = Object.fromEntries(d.verdicts.map((v) => [v.key, v.ahead]));
    $("out").innerHTML = `
      <div class="verdict"><div><h2>${za} <span style="opacity:.6">vs</span> ${zb}</h2><div class="sub">FY ${d.fy}${d.partial_fy ? " (" + t("part_year") + ")" : ""} · ${head}</div></div>
        <div class="score"><div>${d.wins[A.zilla]}<small>${za}</small></div><span class="sep">:</span><div>${d.wins[B.zilla]}<small>${zb}</small></div></div></div>
      <div class="card" style="margin-top:14px"><div class="scroll"><table class="cmp"><tr><th>${t("cmp_measure")}</th><th>${za}</th><th>${zb}</th></tr>
        ${rows.map(([l, k, kind]) => `<tr><td>${t(l)}</td><td class="${won[k] === A.zilla ? "win" : ""}">${cell(A[k], kind)}</td><td class="${won[k] === B.zilla ? "win" : ""}">${cell(B[k], kind)}</td></tr>`).join("")}</table></div></div>
      <div class="grid wide">
        <div class="card chart-card"><h3>${t("c_trend")}</h3><div class="sub">${t("c_collection")}</div><div class="chart-box"><canvas id="x-trend"></canvas></div></div>
        <div class="card chart-card"><h3>${t("cmp_monthly")}</h3><div class="sub">FY ${d.fy}</div><div class="chart-box"><canvas id="x-month"></canvas></div></div>
        <div class="card chart-card"><h3>${t("cmp_heads")}</h3><div class="sub">FY ${d.fy}</div><div class="chart-box"><canvas id="x-head"></canvas></div></div>
        <div class="card chart-card"><h3>${t("k_collection_pct")}</h3><div class="sub">${t("c_trend_sub")}</div><div class="chart-box"><canvas id="x-pct"></canvas></div></div>
      </div>`;
    const colA = C.navy, colB = C.gold;
    VIZ.bar("x-trend", A.trend.map((x) => x.fy), [{ label: za, data: A.trend.map((x) => x.total_collection), backgroundColor: colA }, { label: zb, data: B.trend.map((x) => x.total_collection), backgroundColor: colB }], { fmt: inr });
    VIZ.line("x-month", A.monthly_collection.map((m) => I18N.month(m.month)), [{ label: za, data: A.monthly_collection.map((m) => m.collection), borderColor: colA, backgroundColor: colA },
      { label: zb, data: B.monthly_collection.map((m) => m.collection), borderColor: colB, backgroundColor: colB }], { fmt: inr });
    const heads = [...new Set([...A.by_head, ...B.by_head].map((x) => x.head))];
    const pick = (X, h) => (X.by_head.find((x) => x.head === h) || {}).collection || 0;
    VIZ.bar("x-head", heads, [{ label: za, data: heads.map((h) => pick(A, h)), backgroundColor: colA }, { label: zb, data: heads.map((h) => pick(B, h)), backgroundColor: colB }], { fmt: inr });
    VIZ.line("x-pct", A.trend.map((x) => x.fy), [{ label: za, data: A.trend.map((x) => x.collection_pct), borderColor: colA, backgroundColor: colA },
      { label: zb, data: B.trend.map((x) => x.collection_pct), borderColor: colB, backgroundColor: colB }], { fmt: (v) => v + "%" });
  }

  async function go() {
    const a = $("za").value, b = $("zb").value, fy = $("fy").value;
    if (a === b) { $("out").innerHTML = `<div class="card muted">${I18N.zilla(a)} = ${I18N.zilla(b)}</div>`; return; }
    $("out").innerHTML = `<div class="card muted">${t("loading")}</div>`;
    const res = await fetch(`/api/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}&fy=${encodeURIComponent(fy)}`);
    if (!res.ok) { $("out").innerHTML = `<div class="card muted">${t("failed")}${(await res.json()).detail}</div>`; return; }
    st.data = await res.json();
    history.replaceState(null, "", `/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}&fy=${fy}`);
    render();
  }

  async function init() {
    st.opts = await (await fetch("/api/options")).json();
    fillSelects();
    $("go").addEventListener("click", go);
    ["za", "zb", "fy"].forEach((id) => $(id).addEventListener("change", go));
    document.addEventListener("langchange", () => { fillSelects(); render(); });
    go();
  }
  init();
})();

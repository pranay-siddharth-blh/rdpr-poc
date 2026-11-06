/* GP report card: search a Gram Panchayat, then render its one-page profile from /api/gp/{id}. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const { C, num, pct, inr } = VIZ;
  const t = I18N.t;
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const st = { id: new URLSearchParams(location.search).get("id") || "", fy: null, data: null, opts: null };
  let timer = null;

  async function search(q) {
    const box = $("results");
    if (q.trim().length < 2) { box.hidden = true; return; }
    const res = await (await fetch("/api/gp/search?q=" + encodeURIComponent(q))).json();
    box.innerHTML = res.results.map((g) => `<button type="button" data-id="${g.id}">${esc(g.name)} <small>${esc(g.taluk)} · ${esc(I18N.zilla(g.zilla))}</small></button>`).join("") ||
      `<div class="muted" style="padding:10px">–</div>`;
    box.hidden = false;
    box.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { box.hidden = true; $("search").value = ""; open(b.getAttribute("data-id")); }));
  }

  function rankTile(label, r) {
    if (!r) return "";
    const [pos, n] = r;
    const where = n > 1 ? ((pos - 1) / (n - 1)) * 100 : 0;
    return `<div class="rank"><div class="l">${label}</div><div class="v">${num(pos)} <small>/ ${num(n)}</small></div><div class="track" aria-hidden="true"><i style="left:${100 - where}%"></i></div></div>`;
  }

  function render() {
    const d = st.data;
    if (!d) return;
    const p = d.profile, f = d.finance, h = d.hrms, cur = d.trend.find((x) => x.fy === d.fy) || {};
    $("empty").hidden = true; $("card").hidden = false; $("print").hidden = false; $("csv").hidden = false;
    const badges = d.badges.map((b) => `<span class="badge ${b.kind}">${t(b.key)}</span>`).join("");
    $("card").innerHTML = `
      <div class="card"><div class="gp-head"><div>
        <h2>${esc(p.name)} <small class="muted">GP</small></h2>
        <div class="where">${t("gp_taluk")}: <b>${esc(p.taluk)}</b> · ${t("gp_zilla")}: <a href="/?zilla=${encodeURIComponent(p.zilla)}&fy=${d.fy}">${esc(I18N.zilla(p.zilla))}</a> · FY ${d.fy}${d.partial_fy ? " (" + t("part_year") + ")" : ""}</div>
        <div class="pro"><span>${t("gp_size")}: <b>${esc(p.size_class)}</b></span><span>${t("gp_tier")}: <b>${esc(p.performance_tier)}</b></span><span>${t("gp_lgd")}: <b>${esc(p.lgd_code)}</b></span><span>ID: <b>${esc(p.gp_id)}</b></span></div>
      </div><div>${badges}</div></div></div>
      <div class="kpis" style="margin-top:14px">
        <div class="kpi"><div class="l">${t("gp_collection")}</div><div class="v">${inr(cur.total_collection)}</div><div class="s">${t("gp_demand")} ${inr(cur.total_demand)}</div></div>
        <div class="kpi"><div class="l">${t("k_collection_pct")}</div><div class="v">${pct(cur.collection_pct)}</div><div class="s">${t("gp_state_avg")} ${pct(d.peers.state)}</div></div>
        <div class="kpi"><div class="l">${t("gp_balance")}</div><div class="v">${inr(cur.balance)}</div><div class="s">${t("gp_arrears")} ${inr(cur.arrears)}</div></div>
        <div class="kpi"><div class="l">${t("k_books_closed")}</div><div class="v">${f.books_closed} / ${f.books_total}</div><div class="s">${t("gp_receipts")} ${inr(f.receipts)}</div></div>
        <div class="kpi"><div class="l">${t("gp_members")}</div><div class="v">${h.elected_members ?? "–"} / ${h.seats ?? "–"}</div><div class="s">${t("gp_pending")}: ${h.pending_at_eo ?? "–"}</div></div>
      </div>
      <div class="ranks">${rankTile(t("gp_rank_taluk"), d.rank && d.rank.taluk)}${rankTile(t("gp_rank_zilla"), d.rank && d.rank.zilla)}${rankTile(t("gp_rank_state"), d.rank && d.rank.state)}</div>
      <div class="two">
        <div class="card chart-card"><h3>${t("gp_vs_peers")}</h3><div class="chart-box"><canvas id="g-peers"></canvas></div></div>
        <div class="card chart-card"><h3>${t("gp_trend")}</h3><div class="chart-box"><canvas id="g-trend"></canvas></div></div>
        <div class="card chart-card"><h3>${t("gp_months")}</h3><div class="chart-box"><canvas id="g-months"></canvas></div></div>
        <div class="card chart-card"><h3>${t("gp_heads")}</h3><div class="chart-box"><canvas id="g-heads"></canvas></div></div>
      </div>
      <div class="two">
        <div class="card"><h3>${t("gp_books")}</h3><table class="kv">${f.books.map((b) => `<tr><td>${esc(b.scheme)}</td><td class="${b.closed ? "st-ok" : "st-no"}">${b.closed ? "✔ " + t("gp_closed") : "✖ " + t("gp_open")}</td></tr>`).join("")}</table>
          <table class="kv" style="margin-top:10px"><tr><td>${t("gp_receipts")}</td><td>${inr(f.receipts)}</td></tr><tr><td>${t("gp_expenditure")}</td><td>${inr(f.expenditure)}</td></tr><tr><td>${t("gp_closing")}${f.closing_month ? " (" + I18N.month(f.closing_month) + ")" : ""}</td><td>${inr(f.closing_balance)}</td></tr></table></div>
        <div class="card"><h3>${t("gp_hr")}</h3><table class="kv">
          <tr><td>${t("gp_seats")}</td><td>${num(h.seats)}</td></tr><tr><td>${t("gp_members")}</td><td>${num(h.elected_members)}</td></tr>
          <tr><td>${t("gp_president")}</td><td class="${h.has_president ? "st-ok" : "st-no"}">${h.has_president ? t("yes") : t("no")}</td></tr>
          <tr><td>${t("gp_vp")}</td><td class="${h.has_vice_president ? "st-ok" : "st-no"}">${h.has_vice_president ? t("yes") : t("no")}</td></tr>
          <tr><td>${t("gp_sent")}</td><td>${num(h.sent_to_eo)}</td></tr><tr><td>${t("gp_approved")}</td><td>${num(h.approved_by_eo)}</td></tr>
          <tr><td>${t("gp_pending")}</td><td>${num(h.pending_at_eo)}</td></tr><tr><td>${t("gp_rejected")}</td><td>${num(h.rejected_by_eo)}</td></tr>
          ${d.properties.total != null ? `<tr><td>${t("gp_props")}</td><td>${num(d.properties.total)}</td></tr>` : ""}</table>
          <div class="muted" style="font-size:12px;margin-top:6px">${h.snapshot_date ? t("gp_snapshot", { d: h.snapshot_date }) : ""}</div></div>
      </div>
      <div class="card" style="margin-top:14px"><h3>${t("gp_trend")}</h3><div class="scroll"><table class="t"><tr><th>${t("gp_year_col")}</th><th class="n">${t("gp_arrears")}</th><th class="n">${t("gp_demand")}</th><th class="n">${t("gp_collection")}</th><th class="n">${t("k_collection_pct")}</th><th class="n">${t("gp_balance")}</th></tr>
        ${d.trend.map((x) => `<tr><td>${x.fy}</td><td class="n">${inr(x.arrears)}</td><td class="n">${inr(x.total_demand)}</td><td class="n">${inr(x.total_collection)}</td><td class="n">${pct(x.collection_pct)}</td><td class="n">${inr(x.balance)}</td></tr>`).join("")}</table></div></div>
      <div class="print-foot">${d.data_as_of}</div>`;

    const peers = [[t("gp_this"), d.rank && d.rank.collection_pct], [t("gp_taluk_avg"), d.peers.taluk], [t("gp_zilla_avg"), d.peers.zilla], [t("gp_state_avg"), d.peers.state]];
    VIZ.bar("g-peers", peers.map((x) => x[0]), [{ label: t("k_collection_pct"), data: peers.map((x) => x[1]), backgroundColor: [C.gold, C.navy, C.violet, C.grey] }], { fmt: (v) => v + "%" });
    VIZ.bar("g-trend", d.trend.map((x) => x.fy), [{ label: t("c_demand"), data: d.trend.map((x) => x.total_demand), backgroundColor: C.grey }, { label: t("c_collection"), data: d.trend.map((x) => x.total_collection), backgroundColor: C.navy }], { fmt: inr });
    VIZ.line("g-months", d.monthly_collection.map((m) => I18N.month(m.month)), [{ label: t("c_collection"), data: d.monthly_collection.map((m) => m.collection), borderColor: C.gold, backgroundColor: "rgba(229,72,37,.12)", fill: true }], { fmt: inr });
    VIZ.bar("g-heads", d.by_head.map((x) => x.head), [{ label: t("c_collection"), data: d.by_head.map((x) => x.collection), backgroundColor: C.violet }], { fmt: inr });
    document.title = p.name + " · " + t("gp_title");
  }

  async function open(id) {
    st.id = id;
    const res = await fetch(`/api/gp/${encodeURIComponent(id)}?fy=${encodeURIComponent(st.fy)}`);
    if (!res.ok) { $("card").hidden = true; $("empty").hidden = false; return; }
    st.data = await res.json();
    history.replaceState(null, "", `/gp?id=${encodeURIComponent(id)}&fy=${st.fy}`);
    render();
  }

  function csv() {
    const d = st.data, q = (s) => { s = String(s ?? "").replace(/"/g, '""'); return /^[=+\-@]/.test(s) ? `"'${s}"` : `"${s}"`; };
    const rows = [["GP", d.profile.name], ["Taluk", d.profile.taluk], ["Zilla", d.profile.zilla], ["FY", d.fy], [],
      ["Year", "Arrears", "Total demand", "Total collection", "Collection %", "Balance"],
      ...d.trend.map((x) => [x.fy, x.arrears, x.total_demand, x.total_collection, x.collection_pct, x.balance])];
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + rows.map((r) => r.map(q).join(",")).join("\n")], { type: "text/csv" }));
    a.download = `gp-${d.profile.gp_id}-${d.fy}.csv`;
    a.click();
  }

  async function init() {
    st.opts = await (await fetch("/api/options")).json();
    const qfy = new URLSearchParams(location.search).get("fy");
    st.fy = st.opts.fiscal_years.includes(qfy) ? qfy : st.opts.default_fy;
    $("fy").innerHTML = st.opts.fiscal_years.map((y) => `<option value="${y}"${y === st.fy ? " selected" : ""}>${y}${y === st.opts.partial_fy ? " (" + t("part_year") + ")" : ""}</option>`).join("");
    $("fy").addEventListener("change", () => { st.fy = $("fy").value; if (st.id) open(st.id); });
    $("search").addEventListener("input", (e) => { clearTimeout(timer); const v = e.target.value; timer = setTimeout(() => search(v), 180); });
    document.addEventListener("click", (e) => { if (!e.target.closest(".searchbox")) $("results").hidden = true; });
    $("print").addEventListener("click", () => window.print());
    $("csv").addEventListener("click", csv);
    document.addEventListener("langchange", render);
    if (st.id) open(st.id);
  }
  init();
})();

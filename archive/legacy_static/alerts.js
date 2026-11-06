/* Alerts and watch-list: places that need attention for the selected financial year (from /api/alerts). */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const t = I18N.t;
  let data = null, fy = null;

  const fmt = (it) => {
    if (it.value === null || it.value === undefined) return "";
    if (it.fmt === "pct") return VIZ.pct(it.value);
    if (it.fmt === "pct_signed") return (it.value > 0 ? "+" : "") + it.value.toFixed(1) + "%";
    return VIZ.num(it.value);
  };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function titleOf(a) { return t("al_" + a.id, { pfy: a.prev_fy || "" }); }
  function extra(a) {
    if (a.state_pct != null) return " · " + t("al_state_rate", { p: a.state_pct });
    if (a.avg_pct != null) return " · " + t("al_avg", { p: a.avg_pct });
    return "";
  }
  function row(it) {
    const label = it.link && it.link.type === "zilla" ? I18N.zilla(it.label) : it.label;
    const sub = it.sub ? `<span class="muted"> ${esc(it.sub)}</span>` : "";
    const val = `<b>${fmt(it)}</b>`;
    if (!it.link) return `<li><span>${esc(label)}${sub}</span>${val}</li>`;
    const attr = it.link.type === "gp" ? `href="/gp?id=${encodeURIComponent(it.link.id)}"` : `href="#" data-zilla="${esc(it.link.name)}"`;
    return `<li><a ${attr}>${esc(label)}</a>${sub}${val}</li>`;
  }

  function render() {
    if (!data) return;
    $("al-sub").textContent = t("al_sub", { fy: data.fy });
    const body = $("alerts-body");
    if (!data.alerts.length) { body.innerHTML = `<div class="card muted">${t("al_none")}</div>`; return; }
    const sums = ["high", "medium", "low"].filter((s) => data.counts[s]).map((s) => `<span class="sev ${s}">${t("al_" + s)} · ${data.counts[s]}</span>`).join(" ");
    body.innerHTML = `<div class="al-sum">${sums}${data.partial_fy ? `<span class="muted"> ${t("al_partial_skip")}</span>` : ""}</div>` +
      `<div class="al-grid">` + data.alerts.map((a) => `<div class="card al-card ${a.severity}">
        <div class="al-top"><span class="sev ${a.severity}">${t("al_" + a.severity)}</span><span class="al-count">${VIZ.num(a.count)} <small>${t("al_unit_" + a.unit)}</small></span></div>
        <h3>${titleOf(a)}<small class="muted">${extra(a)}</small></h3>
        <ul class="al-list">${a.items.map(row).join("")}</ul></div>`).join("") + `</div>`;
    body.querySelectorAll("a[data-zilla]").forEach((el) => el.addEventListener("click", (e) => {
      e.preventDefault();
      document.dispatchEvent(new CustomEvent("selectzilla", { detail: el.getAttribute("data-zilla") }));
    }));
  }

  async function load(newFy) {
    fy = newFy;
    try {
      const res = await fetch("/api/alerts?fy=" + encodeURIComponent(fy));
      if (!res.ok) throw new Error("alerts");
      data = await res.json();
      render();
    } catch (e) {
      $("alerts-body").innerHTML = `<div class="card muted">${t("failed")}${e.message}</div>`;
    }
  }
  document.addEventListener("dashchange", (e) => { if (e.detail.fy !== fy) load(e.detail.fy); });
  document.addEventListener("langchange", render);
})();

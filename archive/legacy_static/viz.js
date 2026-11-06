/* Shared chart helpers (Chart.js) and number formats for the dashboard, GP report card and comparison pages. */
(function () {
  "use strict";
  // official RDPR website palette: navy #072577, orange-red #e54825, red #d82221, indigo #5758bb, teal #0f7291, amber #e0a10b
  const C = { navy: "#072577", gold: "#e54825", green: "#2e8b57", red: "#d82221", teal: "#0f7291", violet: "#5758bb", amber: "#e0a10b", grey: "#a9b0bf" };
  const charts = {};
  const num = (v) => (v === null || v === undefined ? "–" : Math.round(v).toLocaleString("en-IN"));
  const pct = (v, d) => (v === null || v === undefined ? "–" : Number(v).toFixed(d === undefined ? 1 : d) + "%");
  const inr = (v) => I18N.money(v);

  function draw(id, config) {
    const el = document.getElementById(id);
    if (!el) return;
    if (charts[id]) charts[id].destroy();
    config.options = Object.assign({ responsive: true, maintainAspectRatio: false, animation: { duration: 350 } }, config.options || {});
    Chart.defaults.color = getComputedStyle(document.documentElement).getPropertyValue("--muted").trim() || "#6b6c70";
    Chart.defaults.font.family = I18N.lang === "kn" ? '"Noto Sans Kannada", Inter, sans-serif' : "Inter, system-ui, sans-serif";
    charts[id] = new Chart(el.getContext("2d"), config);
  }
  function bar(id, labels, sets, opts) {
    opts = opts || {};
    const f = opts.fmt || ((v) => v);
    const axis = { ticks: { callback: (v) => f(v) } };
    draw(id, { type: "bar", data: { labels, datasets: sets.map((s) => Object.assign({ borderRadius: 3 }, s)) },
      options: { indexAxis: opts.horizontal ? "y" : "x", plugins: { legend: { display: sets.length > 1 },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${f(c.parsed[opts.horizontal ? "x" : "y"])}` } } },
        scales: opts.horizontal ? { x: axis } : { y: axis } } });
  }
  function line(id, labels, sets, opts) {
    opts = opts || {};
    const f = opts.fmt || ((v) => v);
    draw(id, { type: "line", data: { labels, datasets: sets.map((s) => Object.assign({ tension: 0.25, pointRadius: 3, fill: false }, s)) },
      options: { plugins: { legend: { display: sets.length > 1 }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${f(c.parsed.y)}` } } },
        scales: { y: Object.assign({ ticks: { callback: (v) => f(v) } }, opts.y || {}) } } });
  }
  /* A chart drawn inside a hidden section has no size, so it stays blank when that section is shown.
     The sidebar calls this after switching view to make every live chart measure its box again. */
  function resizeAll() {
    Object.values(charts).forEach((c) => { try { c.resize(); } catch (e) { /* chart already destroyed */ } });
  }
  window.VIZ = { C, num, pct, inr, draw, bar, line, resizeAll };
})();

/* Karnataka choropleth: district outlines from /static/ka_districts.json coloured by a measure from /api/map.
   The outlines are the 2011 districts; Vijayanagara (formed 2021) lies inside Ballari, so that outline shows the two together.
   Ratios are recomputed from components (SUM / SUM) whenever zillas are combined. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const t = I18N.t;
  const W = 600, H = 700, PAD = 12;
  const METRICS = {
    collection_pct: { key: "m_collection_pct", hi: "good", f: (r) => (r.demand ? (100 * r.collection) / r.demand : null), fmt: (v) => v.toFixed(1) + "%" },
    books_closed: { key: "m_books_closed", hi: "good", f: (r) => (r.books ? (100 * r.books_closed) / r.books : null), fmt: (v) => v.toFixed(1) + "%" },
    pending_eo: { key: "m_pending_eo", hi: "bad", f: (r) => r.pending_eo, fmt: (v) => VIZ.num(v) },
    staff: { key: "m_staff", hi: "good", f: (r) => r.active_staff, fmt: (v) => VIZ.num(v) },
    collection: { key: "m_collection", hi: "good", f: (r) => r.collection, fmt: (v) => VIZ.inr(v) },
  };
  let geo = null, map = null, fy = null, metric = "collection_pct", bbox = null;

  function project(lon, lat) {
    return [PAD + (lon - bbox.minLon) * bbox.k * Math.cos((bbox.midLat * Math.PI) / 180), PAD + (bbox.maxLat - lat) * bbox.k];
  }
  function pathOf(geom) {
    const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates;
    return polys.map((poly) => poly.map((ring) => "M" + ring.map((p) => project(p[0], p[1]).map((n) => n.toFixed(1)).join(",")).join("L") + "Z").join("")).join("");
  }
  function computeBox() {
    let minLon = 1e9, maxLon = -1e9, minLat = 1e9, maxLat = -1e9;
    geo.features.forEach((f) => (f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates).forEach((poly) => poly[0].forEach((p) => {
      minLon = Math.min(minLon, p[0]); maxLon = Math.max(maxLon, p[0]); minLat = Math.min(minLat, p[1]); maxLat = Math.max(maxLat, p[1]);
    })));
    const midLat = (minLat + maxLat) / 2, kx = (W - 2 * PAD) / ((maxLon - minLon) * Math.cos((midLat * Math.PI) / 180)), ky = (H - 2 * PAD) / (maxLat - minLat);
    bbox = { minLon, maxLat, midLat, k: Math.min(kx, ky) };
  }
  const byName = () => Object.fromEntries(map.zillas.map((z) => [z.zilla, z]));
  function combine(names) {
    const zs = byName(), out = {};
    names.forEach((n) => { const z = zs[n]; if (z) Object.keys(z).forEach((k) => { if (typeof z[k] === "number") out[k] = (out[k] || 0) + z[k]; }); });
    return out;
  }
  const members = (outline) => (outline === "Ballari" ? ["Ballari", "Vijayanagara"] : [outline]);

  function scale(values, goodHigh) {
    const lo = Math.min(...values), hi = Math.max(...values);
    const from = goodHigh ? [232, 236, 248] : [255, 243, 230], to = goodHigh ? [7, 37, 119] : [216, 34, 33];
    return { lo, hi, at: (v) => { const x = hi === lo ? 0.5 : (v - lo) / (hi - lo); return "rgb(" + from.map((c, i) => Math.round(c + (to[i] - c) * x)).join(",") + ")"; },
      css: `linear-gradient(90deg, rgb(${from.join(",")}), rgb(${to.join(",")}))` };
  }

  function render() {
    if (!geo || !map) return;
    const M = METRICS[metric], svg = $("ka-map");
    const vals = geo.features.map((f) => M.f(combine(members(f.properties.name)))).filter((v) => v !== null && v !== undefined);
    const sc = scale(vals, M.hi === "good");
    $("lg-lo").textContent = t("m_low") + " " + M.fmt(sc.lo);
    $("lg-hi").textContent = M.fmt(sc.hi) + " " + t("m_high");
    $("lg-bar").style.background = sc.css;
    svg.innerHTML = geo.features.map((f) => {
      const n = f.properties.name, v = M.f(combine(members(n)));
      return `<path d="${pathOf(f.geometry)}" data-z="${n}" fill="${v === null ? "#ddd" : sc.at(v)}" stroke="#fff" stroke-width="1.2" tabindex="0" role="button" aria-label="${I18N.zilla(n)}"></path>`;
    }).join("");
    svg.querySelectorAll("path").forEach((p) => {
      const n = p.getAttribute("data-z");
      p.addEventListener("mousemove", (e) => tip(e, n));
      p.addEventListener("focus", () => tipAt(n, p));
      p.addEventListener("mouseleave", () => ($("map-tip").hidden = true));
      p.addEventListener("click", () => pick(n));
      p.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(n); } });
    });
    // accessible list of all 31 zillas (Vijayanagara has no outline of its own)
    const rows = map.zillas.map((z) => ({ name: z.zilla, v: M.f(z) })).sort((a, b) => (b.v ?? -1) - (a.v ?? -1));
    $("map-chips").innerHTML = rows.map((r) => `<button type="button" data-z="${r.name}"><i style="background:${r.v === null ? "#ddd" : sc.at(r.v)}"></i>${I18N.zilla(r.name)}<b>${r.v === null ? "–" : M.fmt(r.v)}</b></button>`).join("");
    $("map-chips").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => pick(b.getAttribute("data-z"))));
  }
  function tipHtml(outline) {
    const M = METRICS[metric], names = members(outline);
    const lines = names.map((n) => { const z = byName()[n]; const v = z ? M.f(z) : null; return `<div><b>${I18N.zilla(n)}</b>: ${v === null ? "–" : M.fmt(v)}</div>`; }).join("");
    return (names.length > 1 ? `<div class="muted">${t("map_combined")}</div>` : "") + lines + `<div class="muted">${t("map_select")}</div>`;
  }
  function tip(e, n) {
    const box = $("map-tip"), r = $("ka-map").getBoundingClientRect();
    box.innerHTML = tipHtml(n); box.hidden = false;
    box.style.left = Math.min(e.clientX - r.left + 14, r.width - 190) + "px"; box.style.top = e.clientY - r.top + 14 + "px";
  }
  function tipAt(n, el) {
    const box = $("map-tip"), r = $("ka-map").getBoundingClientRect(), b = el.getBoundingClientRect();
    box.innerHTML = tipHtml(n); box.hidden = false; box.style.left = b.left - r.left + b.width / 2 + "px"; box.style.top = b.top - r.top + b.height / 2 + "px";
  }
  function pick(name) { document.dispatchEvent(new CustomEvent("selectzilla", { detail: name })); }

  function fillMetrics() {
    $("map-metric").innerHTML = Object.keys(METRICS).map((k) => `<option value="${k}"${k === metric ? " selected" : ""}>${t(METRICS[k].key)}</option>`).join("");
  }
  async function loadMap(newFy) {
    fy = newFy;
    try { map = await (await fetch("/api/map?fy=" + encodeURIComponent(fy))).json(); render(); } catch (e) { /* keep the page usable */ }
  }
  async function init() {
    fillMetrics();
    $("map-metric").addEventListener("change", () => { metric = $("map-metric").value; render(); });
    geo = await (await fetch("/static/ka_districts.json")).json();
    computeBox();
    render();
  }
  document.addEventListener("dashchange", (e) => { if (e.detail.fy !== fy) loadMap(e.detail.fy); });
  document.addEventListener("langchange", () => { fillMetrics(); render(); });
  init();
})();

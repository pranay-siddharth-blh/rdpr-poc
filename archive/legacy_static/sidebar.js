/* Left sidebar: switches the dashboard between its module views (Overview, Revenue, Finance, HRMS) instead of
   making the user scroll one long page, mirrors the page links, and holds the language switch.

   The sections already exist in dashboard.html and are filled by dashboard.js; this only controls which one is
   on screen, so every figure still comes from the same reviewed queries. */
(function () {
  "use strict";
  // view -> the sections shown for it. Each sidebar entry is its own view, so nothing needs scrolling to reach.
  const VIEWS = { overview: ["overview"], revenue: ["revenue"], finance: ["finance"], hrms: ["hrms"],
                  map: ["map"], alerts: ["alerts"] };

  function show(view) {
    const want = VIEWS[view] || VIEWS.overview;
    Object.values(VIEWS).flat().forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.hidden = !want.includes(id);
    });
    document.querySelectorAll(".side-a").forEach((a) => a.classList.toggle("on", a.getAttribute("data-view") === view));
    try { sessionStorage.setItem("rdpr_view", view); } catch (e) { /* private window */ }
    // a chart drawn while its section was hidden has no size: make them all measure again
    if (window.VIZ && VIZ.resizeAll) requestAnimationFrame(VIZ.resizeAll);
  }

  function current() {
    const h = (location.hash || "").replace("#", "");
    if (VIEWS[h]) return h;
    for (const [v, ids] of Object.entries(VIEWS)) if (ids.includes(h)) return v;
    try { const s = sessionStorage.getItem("rdpr_view"); if (VIEWS[s]) return s; } catch (e) { /* ignore */ }
    return "overview";
  }

  function mount() {
    if (!document.getElementById("side")) return;
    // only entries with a data-view switch the dashboard in place; the rest (e.g. Compare) are ordinary page links
    document.querySelectorAll(".side-a[data-view]").forEach((a) => {
      a.addEventListener("click", (e) => { e.preventDefault(); const v = a.getAttribute("data-view"); location.hash = v; show(v); });
    });
    window.addEventListener("hashchange", () => show(current()));
    show(current());
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount); else mount();
})();

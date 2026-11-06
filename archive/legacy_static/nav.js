/* Shared header navigation: one list of pages, translated, with the current page highlighted. */
(function () {
  "use strict";
  const PAGES = [["dashboard", "/", "nav_dashboard"], ["map", "/#map", "nav_map"], ["compare", "/compare", "nav_compare"],
                 ["gp", "/gp", "nav_gp"], ["alerts", "/#alerts", "nav_alerts"], ["chat", "/chat", "nav_ask"]];
  function render() {
    // The header nav (#nav) on pages that have one, and the left sidebar's Pages group (#side-nav) on pages that do.
    const nav = document.getElementById("nav");
    const side = document.getElementById("side-nav");
    const active = (nav && nav.getAttribute("data-active")) || document.body.getAttribute("data-page") || "";
    const html = (pages) => pages.map(([k, href, key]) =>
      `<a href="${href}"${k === active ? ' class="on"' : ""}>${I18N.t(key)}</a>`).join("");
    if (nav) nav.innerHTML = html(PAGES);
    if (side) {
      // On the dashboard, Map, Alerts and Compare are already quick links in the group above, so the Pages
      // group lists only the rest. Other pages list every page except themselves.
      const covered = document.body.getAttribute("data-page") === "dashboard"
        ? new Set(["dashboard", "map", "alerts", "compare"]) : new Set(["dashboard"]);
      side.innerHTML = html(PAGES.filter(([k]) => !covered.has(k)));
    }
    const title = document.querySelector("[data-site-title]");
    if (title) { title.textContent = I18N.t(title.getAttribute("data-site-title")); }
  }
  document.addEventListener("langchange", render);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", render); else render();
})();

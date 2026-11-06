/* Welcome popup, like the one on rdpr.karnataka.gov.in: opens when the home page loads, centred, round grey close
   button, closes by itself after a few seconds. Content comes from /static/popup.json so it can be edited without code. */
(function () {
  "use strict";
  const back = document.getElementById("welcome");
  const body = document.getElementById("welcome-body");
  if (!back || !body) return;
  let timer = null;
  let cfg = null;
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function close() {
    back.classList.remove("open");
    clearTimeout(timer);
    document.removeEventListener("keydown", onKey);
    try { sessionStorage.setItem("rdpr_welcome_seen", "1"); } catch (e) { /* private window */ }
  }
  function onKey(e) { if (e.key === "Escape") close(); }

  function build(c) {
    const banner = c.image
      ? `<img src="${esc(c.image)}" alt="" style="width:100%;display:block;border-radius:12px 12px 0 0">`
      : `<div style="background:linear-gradient(120deg,#072577 0%,#5758bb 70%,#2c2c54 120%);color:#fff;padding:28px 28px 22px;border-radius:7px 7px 0 0;position:relative;overflow:hidden">
           <svg viewBox="0 0 200 120" aria-hidden="true" style="position:absolute;right:-10px;bottom:-14px;width:230px;opacity:.22"><path d="M10 110V60l90-50 90 50v50h-40V78H50v32z" fill="#fff"/><circle cx="100" cy="46" r="10" fill="#e54825"/></svg>
           <div style="font:600 12px Inter,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:#ffd7c9">${esc(c.kicker || "")}</div>
           <h2 id="w-title" style="color:#fff;font-size:26px;margin:8px 0 8px;max-width:560px">${esc(c.title)}</h2>
           <p style="margin:0;max-width:560px;color:#e6ebff">${esc(c.text)}</p>
         </div>`;
    const tiles = (c.tiles || []).map((t) =>
      `<div style="flex:1 1 190px;border:1px solid var(--line);border-top:3px solid var(--gold);border-radius:8px;padding:12px 14px;background:var(--card)">
         <div style="font:700 22px Montserrat,sans-serif;color:var(--gold)">${esc(t.icon)}</div>
         <div style="font:600 14px Montserrat,sans-serif;color:var(--navy);margin:2px 0">${esc(t.title)}</div>
         <div class="muted" style="font-size:13px">${esc(t.text)}</div></div>`).join("");
    const facts = (c.facts || []).map((f) => `<span class="pill">${esc(f)}</span>`).join(" ");
    const tries = (c.try || []).map((q) => `<a href="/chat?q=${encodeURIComponent(q)}" style="display:block;margin:3px 0;font-size:13px">&ldquo;${esc(q)}&rdquo;</a>`).join("");
    const btns = (c.buttons || []).map((b, i) => {
      const base = "padding:10px 18px;border-radius:7px;font:600 14px Inter,sans-serif;cursor:pointer;text-decoration:none;display:inline-block;";
      const style = b.style === "primary" ? "background:var(--navy);color:#fff;border:1px solid var(--navy);" : "background:transparent;color:var(--navy);border:1px solid var(--navy);";
      return b.href ? `<a href="${esc(b.href)}" style="${base}${style}">${esc(b.label)}</a>` : `<button type="button" data-close="1" style="${base}${style}">${esc(b.label)}</button>`;
    }).join(" ");
    body.innerHTML =
      `<button type="button" class="x" aria-label="Close" data-close="1">&times;</button>${banner}
       <div style="padding:18px 24px 6px"><div style="display:flex;gap:12px;flex-wrap:wrap">${tiles}</div>
       <div style="margin:14px 0 6px">${facts}</div>
       ${tries ? `<div style="margin-top:12px"><div class="muted" style="font-size:12px;text-transform:uppercase;letter-spacing:.05em">Try asking</div>${tries}</div>` : ""}
       <div style="margin:16px 0 14px;display:flex;gap:10px;flex-wrap:wrap">${btns}</div></div>
       <div class="bar run" style="--secs:${c.auto_close_seconds || 20}s"></div>`;
    body.querySelectorAll("[data-close]").forEach((el) => el.addEventListener("click", close));
  }

  function open() {
    build(cfg);
    back.classList.add("open");
    document.addEventListener("keydown", onKey);
    clearTimeout(timer);
    if (cfg.auto_close_seconds) timer = setTimeout(close, cfg.auto_close_seconds * 1000);
    const first = body.querySelector("button, a");
    if (first) first.focus();
  }

  back.addEventListener("click", (e) => { if (e.target === back) close(); });
  const again = document.getElementById("reopen-welcome");
  if (again) again.addEventListener("click", (e) => { e.preventDefault(); if (cfg) open(); });

  fetch("/static/popup.json").then((r) => r.json()).then((c) => {
    cfg = c;
    let seen = false;
    try { seen = c.show_once_per_session && sessionStorage.getItem("rdpr_welcome_seen") === "1"; } catch (e) { /* ignore */ }
    if (c.enabled && !seen) open();
  }).catch(() => { /* no popup file: nothing to show */ });
})();

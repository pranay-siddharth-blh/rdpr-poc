// dashboard.html: page script (served from a file so the security policy allows no inline scripts).
// Layout and behaviour follow the KPCL Generation Dashboard; every figure comes from /api/dashboard (app/dashboard_data.py),
// the same reviewed, read-only queries the chat's reports use.
// ------------------------------------------------------------------ labels (the figures come from the server)
const I18N = {
  en: { govLine1: 'Government of Karnataka', govLine2: 'Rural Development & Panchayat Raj Department',
    appBar: '<b>Panchatantra 2.0 · Gram Panchayat MIS</b><span class="extra"><span class="sep">|</span>Dashboard<span class="sep">|</span>April 2022 – September 2026</span>',
    aiBadge: 'AI MODE', menu: 'Menu', navDash: 'Dashboard', navChat: 'Ask the assistant', navInsights: 'Insights', goInsights: 'Opening Insights', allZillas: 'All zillas', askAi: 'Ask AI about this',
    revenueTitle: 'Monthly collection', financeTitle: 'Monthly scheme receipts', hrmsTitle: 'Monthly salaries paid',
    grainRevenue: 'Revenue', grainFinance: 'Finance', grainHrms: 'HRMS', gsBest: 'Best', gsLow: 'Weakest', gsAvg: 'Average',
    mixTitle: 'Collection by revenue head', ptShare: 'property tax', zillasTitle: 'Zillas', taluksTitle: 'Taluks',
    leagueHint: 'Click a zilla for its own dashboard', outTitle: 'GPs collecting the least', coalTitle: 'Salary bills',
    resTitle: 'Scheme books closed', lossTitle: 'Where dues are outstanding', division: 'division',
    footNote: 'Figures come from fixed, read-only queries on the Panchatantra 2.0 Finance & Accounting, Revenue and HRMS data. Synthetic proof-of-concept data, not official records.',
    misReport: 'MIS report', misView: 'View', misFor: 'Excel MIS report for', misOnScreen: 'As on screen', misComplete: 'Complete report', misCompleteSub: 'Revenue, Finance & Accounting and HRMS sheets together', misFoot: 'Figures match this dashboard. Includes summary, revenue, book closure, scheme money, staff and salary tables, and integrity checks.', misBusy: 'Preparing your MIS report…', misDone: 'MIS report downloaded', misFail: 'The MIS report could not be prepared. Please try again.',
    overview: 'Karnataka at a glance', dashboard: 'Dashboard', zillaDash: 'Zilla dashboard', groups: 'Zillas',
    modRevenue: 'Revenue', modFinance: 'Finance', modHrms: 'HRMS', mapTitle: 'Karnataka map', mapHint: 'Hover a zilla for its name · click it for its dashboard',
    closureTitle: 'Month-end books closed', eoTitle: 'Staff registrations at the EO' },
  kn: { govLine1: 'ಕರ್ನಾಟಕ ಸರ್ಕಾರ', govLine2: 'ಗ್ರಾಮೀಣಾಭಿವೃದ್ಧಿ ಮತ್ತು ಪಂಚಾಯತ್ ರಾಜ್ ಇಲಾಖೆ',
    appBar: '<b>ಪಂಚತಂತ್ರ 2.0 · ಗ್ರಾಮ ಪಂಚಾಯಿತಿ MIS</b><span class="extra"><span class="sep">|</span>ಡ್ಯಾಶ್‌ಬೋರ್ಡ್<span class="sep">|</span>ಏಪ್ರಿಲ್ 2022 – ಸೆಪ್ಟೆಂಬರ್ 2026</span>',
    aiBadge: 'AI ಮೋಡ್', menu: 'ಮೆನು', navDash: 'ಡ್ಯಾಶ್‌ಬೋರ್ಡ್', navChat: 'ಸಹಾಯಕನನ್ನು ಕೇಳಿ', navInsights: 'ಒಳನೋಟಗಳು', goInsights: 'ಒಳನೋಟಗಳನ್ನು ತೆರೆಯಲಾಗುತ್ತಿದೆ', allZillas: 'ಎಲ್ಲಾ ಜಿಲ್ಲೆಗಳು', askAi: 'AI ಅನ್ನು ಕೇಳಿ',
    revenueTitle: 'ಮಾಸಿಕ ವಸೂಲಿ', financeTitle: 'ಮಾಸಿಕ ಯೋಜನಾ ಸ್ವೀಕೃತಿಗಳು', hrmsTitle: 'ಮಾಸಿಕ ವೇತನ ಪಾವತಿ',
    grainRevenue: 'ಕಂದಾಯ', grainFinance: 'ಹಣಕಾಸು', grainHrms: 'HRMS', gsBest: 'ಗರಿಷ್ಠ', gsLow: 'ಕನಿಷ್ಠ', gsAvg: 'ಸರಾಸರಿ',
    mixTitle: 'ಆದಾಯ ಶೀರ್ಷಿಕೆವಾರು ವಸೂಲಿ', ptShare: 'ಆಸ್ತಿ ತೆರಿಗೆ', zillasTitle: 'ಜಿಲ್ಲೆಗಳು', taluksTitle: 'ತಾಲ್ಲೂಕುಗಳು',
    leagueHint: 'ಜಿಲ್ಲೆಯ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್‌ಗಾಗಿ ಕ್ಲಿಕ್ ಮಾಡಿ', outTitle: 'ಕಡಿಮೆ ವಸೂಲಿ ಮಾಡಿದ ಗ್ರಾ.ಪಂ.ಗಳು', coalTitle: 'ವೇತನ ಬಿಲ್‌ಗಳು',
    resTitle: 'ಮುಚ್ಚಿದ ಯೋಜನಾ ಪುಸ್ತಕಗಳು', lossTitle: 'ಬಾಕಿ ಎಲ್ಲಿದೆ', division: 'ವಿಭಾಗ',
    footNote: 'ಅಂಕಿಅಂಶಗಳು ಸ್ಥಿರ, ಓದಲು-ಮಾತ್ರ ಪ್ರಶ್ನೆಗಳಿಂದ ಬರುತ್ತವೆ. ಪ್ರಾಯೋಗಿಕ (ಕೃತಕ) ದತ್ತಾಂಶ, ಅಧಿಕೃತ ದಾಖಲೆಗಳಲ್ಲ.',
    misReport: 'MIS ವರದಿ', misView: 'ವೀಕ್ಷಿಸಿ', misFor: 'Excel MIS ವರದಿ', misOnScreen: 'ಪರದೆಯಲ್ಲಿ ಕಾಣುವಂತೆ', misComplete: 'ಪೂರ್ಣ ವರದಿ', misCompleteSub: 'ಕಂದಾಯ, ಹಣಕಾಸು ಮತ್ತು HRMS ಹಾಳೆಗಳು ಒಟ್ಟಿಗೆ', misFoot: 'ಅಂಕಿಅಂಶಗಳು ಈ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್‌ಗೆ ಹೊಂದುತ್ತವೆ. ವರದಿ ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿದೆ.', misBusy: 'ವರದಿ ಸಿದ್ಧಪಡಿಸಲಾಗುತ್ತಿದೆ…', misDone: 'MIS ವರದಿ ಡೌನ್‌ಲೋಡ್ ಆಗಿದೆ', misFail: 'ವರದಿ ಸಿದ್ಧಪಡಿಸಲಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
    overview: 'ಕರ್ನಾಟಕ ಒಂದು ನೋಟದಲ್ಲಿ', dashboard: 'ಡ್ಯಾಶ್‌ಬೋರ್ಡ್', zillaDash: 'ಜಿಲ್ಲಾ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್', groups: 'ಜಿಲ್ಲೆಗಳು',
    modRevenue: 'ಕಂದಾಯ', modFinance: 'ಹಣಕಾಸು', modHrms: 'HRMS', mapTitle: 'ಕರ್ನಾಟಕ ನಕ್ಷೆ', mapHint: 'ಹೆಸರಿಗಾಗಿ ಜಿಲ್ಲೆಯ ಮೇಲೆ ಸುಳಿದಾಡಿ · ಅದರ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್‌ಗಾಗಿ ಕ್ಲಿಕ್ ಮಾಡಿ',
    closureTitle: 'ತಿಂಗಳಾಂತ್ಯದಲ್ಲಿ ಮುಚ್ಚಿದ ಪುಸ್ತಕಗಳು', eoTitle: 'EO ಬಳಿ ಸಿಬ್ಬಂದಿ ನೋಂದಣಿಗಳು' },
};
let lang = 'en';
const t = k => I18N[lang][k] ?? I18N.en[k];

// Revenue divisions group the zillas in the sidebar and the league filter (as station categories do on KPCL).
const DIV = {
  Bengaluru: { label: 'Bengaluru division', color: '#7b1e34' }, Mysuru: { label: 'Mysuru division', color: '#c25b74' },
  Belagavi: { label: 'Belagavi division', color: '#b8892b' }, Kalaburagi: { label: 'Kalaburagi division', color: '#2a9d8f' },
};
const divOf = c => DIV[c] || { label: c || '—', color: '#7a8699' };
const HEAD_COLORS = ['#7b1e34', '#c25b74', '#b8892b', '#e9b949', '#2a9d8f', '#8c4a5a', '#e5a3b3'];

// ------------------------------------------------------------------ helpers
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = (v, d = 1) => v == null ? '—' : Number(v).toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d });
const cr = v => v == null ? null : v / 1e7;                                   // rupees -> crore
const lakh = v => v == null ? '—' : '₹' + num(v / 1e5, 2) + ' lakh';
const rupees = v => v == null ? '—' : Math.abs(v) >= 1e7 ? '₹' + num(v / 1e7, 2) + ' cr' : lakh(v);
const MON3 = 'JanFebMarAprMayJunJulAugSepOctNovDec';
const pretty = d => { if (!d) return '—'; const [y, m, dd] = d.slice(0, 10).split('-'); return `${dd}-${MON3.slice((m - 1) * 3, m * 3)}-${y}`; };
const monthName = l => l ? l.charAt(0) + l.slice(1, 3).toLowerCase() + ' ' + l.slice(-4) : '';      // 'APR-2025' -> 'Apr 2025'
const monShort = l => l ? l.charAt(0) + l.slice(1, 3).toLowerCase() : '';
const title = s => String(s || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
// Counts a figure up to its value. On a later switch (another year, zilla or module) it counts from the figure already
// on screen to the new one, so numbers glide instead of dropping to zero; a newer count cancels an older one.
function countUp(el, to, d = 1, ms = 1100){
  const tok = (el.__count = (el.__count || 0) + 1);
  if (to == null){ el.textContent = '—'; el.__v = null; return; }
  const from = el.__v == null ? 0 : el.__v;
  el.__v = to;
  if (reduced || from === to){ el.textContent = num(to, d); return; }
  const t0 = performance.now();
  const step = now => { if (el.__count !== tok) return;
    const p = Math.min(1, (now - t0) / ms), e = 1 - Math.pow(1 - p, 3);
    el.textContent = num(from + (to - from) * e, d); if (p < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}
function delta(cur, prev, { unit = '%', pts = false, goodUp = true, d = 1 } = {}){
  if (cur == null || prev == null) return '';
  const diff = pts ? cur - prev : (prev ? (cur - prev) / prev * 100 : null);
  if (diff == null) return '';
  const up = diff >= 0, good = goodUp ? up : !up, cls = Math.abs(diff) < 0.05 ? 'flat' : good ? 'up' : 'down';
  return `<span class="chip ${cls}">${up ? '▲' : '▼'} ${num(Math.abs(diff), d)}${pts ? ' pts' : unit}</span>`;
}
// collection % against the state (or zilla) rate: at or above is good, within 2 points is close, else behind
const pctClass = (a, ref) => a == null || ref == null ? '' : a >= ref ? 'pct-good' : a >= ref - 2 ? 'pct-warn' : 'pct-bad';
const pctColor = (a, ref) => a == null || ref == null ? '#e0d2d6' : a >= ref ? '#1f9d57' : a >= ref - 2 ? '#c98a00' : '#c8372d';

const charts = {};
// A chart that already exists is updated in place (its bars and lines glide to the new values) instead of being torn
// down and drawn again; only a change of chart type or plugins rebuilds it.
function chart(id, cfg){
  if (!window.Chart) return null;
  const c = charts[id];
  if (c && c.canvas !== $(id)){ c.destroy(); delete charts[id]; return chart(id, cfg); }   // its canvas was replaced
  if (c && c.config.type === cfg.type && !(cfg.plugins || []).length && c.data.datasets.length === cfg.data.datasets.length){
    c.data.labels = cfg.data.labels;
    cfg.data.datasets.forEach((ds, i) => Object.assign(c.data.datasets[i], ds));
    c.options = cfg.options;
    c.update();
    return c;
  }
  if (c) c.destroy();
  charts[id] = new Chart($(id).getContext('2d'), cfg);
  return charts[id];
}
const FONT = { family: 'Noto Sans', size: 11 };
function spark(id, values, color, fillTop){
  const cv = $(id); if (!cv || !window.Chart) return;
  const ctx = cv.getContext('2d'); const g = ctx.createLinearGradient(0, 0, 0, cv.clientHeight || 60);
  g.addColorStop(0, fillTop); g.addColorStop(1, 'rgba(255,255,255,0)');
  chart(id, { type: 'line', data: { labels: values.map((_, i) => i), datasets: [{ data: values, borderColor: color, backgroundColor: g, fill: true,
    borderWidth: 2, tension: .35, pointRadius: values.map((_, i) => i === values.length - 1 ? 3 : 0), pointBackgroundColor: color }] },
    options: { responsive: true, maintainAspectRatio: false, animation: { duration: reduced ? 0 : 900 }, plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false } } } });
}

// ------------------------------------------------------------------ state
let DATA = null, FY = null, ZILLA = null, FILTER = 'ALL', SORT = { key: 'collection', dir: -1 };
// The module boxes beside the year select: null shows every module; 'revenue' / 'finance' / 'hrms' turns the whole
// page (headline, KPIs, charts, table, map) into that module, and the choice stays while the year or zilla changes.
const MODULES = ['revenue', 'finance', 'hrms'];
const MOD_NAME = { revenue: 'Revenue', finance: 'Finance & Accounting', hrms: 'HRMS' };
let MODULE = null;
const sortDefault = () => ({ key: { finance: 'books_closed_pct', hrms: 'active_staff' }[MODULE] || 'collection', dir: -1 });

// Every selection is fetched once and kept for the visit; after the first page the other years are fetched in the
// background, so switching year or going back is instant. Only the newest request may paint the page (a slow answer
// to an earlier click can never overwrite a later one), and a loading bar shows while a request is out.
const PAGE_CACHE = new Map();
let SEQ = 0, CTRL = null;
const keyOf = (fy, z) => `${fy || ''}|${z || ''}`;
async function fetchPage(fy, z, signal){
  const k = keyOf(fy, z);
  if (PAGE_CACHE.has(k)) return PAGE_CACHE.get(k);
  const qs = new URLSearchParams(); if (fy) qs.set('fy', fy); if (z) qs.set('zilla', z);
  const r = await fetch('/api/dashboard?' + qs.toString(), { signal });
  if (r.status === 404){ const b = await r.json().catch(() => ({})); throw new Error(b.detail || 'Not found'); }
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const d = await r.json();
  PAGE_CACHE.set(keyOf(d.fy, d.zilla), d); if (!fy) PAGE_CACHE.set(k, d);
  return d;
}
let PREFETCHED = false;
function prefetch(){
  if (PREFETCHED || !DATA) return; PREFETCHED = true;
  const idle = window.requestIdleCallback || (f => setTimeout(f, 400));
  idle(async () => { for (const f of DATA.fys){ try { await fetchPage(f, ZILLA); } catch (_e) { /* best effort */ } } });
}

// The first paint waits for the page's fonts (they are preloaded and usually come from the cache at once; never more
// than 1.2 s), so text never re-flows in front of the user and the cards do not change height as the fonts arrive.
const FONTS_READY = document.fonts && document.fonts.load
  ? Promise.race([Promise.all(['400 1em "Noto Sans"', '600 1em "Noto Sans"', '700 1em "Noto Sans"', '600 1em "Noto Serif"', '700 1em "Noto Serif"']
      .map(f => document.fonts.load(f))).catch(() => {}), new Promise(r => setTimeout(r, 1200))])
  : Promise.resolve();
async function load(pushState = true){
  $('error').hidden = true;
  const seq = ++SEQ;
  if (CTRL) CTRL.abort();
  CTRL = new AbortController();
  const cachedNow = PAGE_CACHE.has(keyOf(FY, ZILLA));
  if (!cachedNow) document.body.classList.add('is-loading');
  try {
    const d = await fetchPage(FY, ZILLA, CTRL.signal);
    if (!DATA) await FONTS_READY;
    if (seq !== SEQ) return;                          // a newer selection is already on its way
    DATA = d; FY = DATA.fy;
    if (pushState) pushUrl();
    render();
    $('skeleton').hidden = true; $('body').hidden = false;
    prefetch();
  } catch (e) {
    if (e && e.name === 'AbortError') return;
    if (window.console) console.error(e);
    $('skeleton').hidden = true;
    $('error').textContent = 'The dashboard could not be loaded. ' + (e.message || ''); $('error').hidden = false;
    if (ZILLA){ ZILLA = null; }
  } finally {
    if (seq === SEQ) document.body.classList.remove('is-loading');
  }
}

function pushUrl(){
  const u = new URL(location); u.search = '';
  if (DATA && FY !== DATA.complete_fys.at(-1)) u.searchParams.set('fy', FY);
  if (ZILLA) u.searchParams.set('zilla', ZILLA);
  if (MODULE) u.searchParams.set('module', MODULE);
  history.pushState({ fy: FY, zilla: ZILLA, module: MODULE }, '', u);
}

// ------------------------------------------------------------------ render
const seriesOf = k => (DATA.series.by_fy || []).filter(x => x.fy <= DATA.fy).map(x => x[k] == null ? null : x[k]);
const show = (id, on) => { $(id).hidden = !on; };
// a row of panels takes as many columns as it has visible panels
function fit(id){ const row = $(id); row.dataset.n = [...row.children].filter(c => !c.hidden).length; }
function render(){
  if (!$('zillaNav').children.length) renderZillaNav();
  const d = DATA, z = d.zilla, M = MODULE;
  const zi = z ? d.zilla_index.find(x => x.zilla === z) : null;
  // heading
  $('eyebrow').textContent = (z ? t('zillaDash') + ' · ' + divOf(d.division).label : t('dashboard')) + (M ? ' · ' + MOD_NAME[M] : '');
  $('title').innerHTML = esc(z ? z + ' zilla' : t('overview')) + (M ? `<span class="mod-tag">${esc(t('mod' + M.charAt(0).toUpperCase() + M.slice(1)))} only</span>` : '');
  $('modules').classList.toggle('has-on', !!M);
  $('modules').querySelectorAll('.mod').forEach(b => { const on = b.dataset.m === M; b.setAttribute('aria-pressed', on);
    b.title = on ? 'Showing only ' + MOD_NAME[b.dataset.m] + ' · click again to show every module' : 'Show only ' + MOD_NAME[b.dataset.m]; });
  $('subline').innerHTML = `FY <b>${esc(d.fy)}</b>${d.partial_fy ? ' (April to September only)' : ''}${d.prev_fy && !d.partial_fy ? ' · compared with FY ' + esc(d.prev_fy) : ''} · data to <b>${pretty(d.data_as_of)}</b>`
    + (zi ? ` · ${zi.taluks} taluks · ${num(zi.gps, 0)} GPs` : ` · 31 zillas · 238 taluks · ${num(d.gps, 0)} GPs`);
  $('backBtn').hidden = !z;
  $('fySelect').innerHTML = d.fys.slice().reverse().map(f => `<option value="${esc(f)}" ${f === d.fy ? 'selected' : ''}>FY ${esc(f)}${d.complete_fys.includes(f) ? '' : ' (part)'}</option>`).join('');
  document.querySelectorAll('.st-item').forEach(b => b.classList.toggle('active', b.dataset.z === z));
  $('navOverview').classList.toggle('active', !z);

  renderBig();
  $('mapAsof').textContent = `FY ${d.fy}`;
  renderMap();
  renderKpis();
  renderMonthly();
  renderMix(); renderLeague();
  // the panels each module shows (null = every module)
  const on = m => !M || M === m;
  show('outPanel', on('revenue')); show('coalPanel', on('hrms')); show('resPanel', on('finance'));
  show('closurePanel', M === 'finance'); show('eoPanel', M === 'hrms'); show('duesPanel', on('revenue'));
  if (on('revenue')){ renderOut(); renderDues(); }
  if (on('hrms')) renderSalary();
  if (on('finance')) renderSchemes();
  if (M === 'finance') renderClosure();
  if (M === 'hrms') renderEo();
  renderTrend();
  fit('row3'); fit('row4');
  $('asof1').textContent = 'FY ' + d.fy;
  $('asof2').textContent = d.hrms.salary_month ? 'As on ' + monthName(d.hrms.salary_month) : 'FY ' + d.fy;
  $('asof3').textContent = 'Year books · FY ' + d.fy;
  $('asof4').textContent = 'FY ' + d.fy;
  $('asof5').textContent = 'FY ' + d.fy;
}

// The wine headline card: total collection, scheme receipts or active staff, by module.
function renderBig(){
  const d = DATA, r = d.revenue, f = d.finance, h = d.hrms, M = MODULE;
  const prevOf = k => { const p = (d.series.by_fy || []).find(x => x.fy === d.prev_fy); return p ? p[k] : null; };
  if (M === 'finance'){
    $('bigLabel').textContent = `Scheme receipts · FY ${d.fy}`; $('bigUnit').textContent = '₹ cr';
    countUp($('bigVal'), cr(f.receipts), 2, 1300);
    const spent = f.receipts ? f.expenditure / f.receipts * 100 : null;
    $('bigRow').innerHTML = (d.partial_fy ? '' : delta(f.receipts, prevOf('receipts'), { d: 1 }))
      + `<span>₹${num(cr(f.expenditure), 2)} cr spent (${num(spent, 1)}% of receipts)</span>`;
    spark('bigSpark', seriesOf('receipts').map(cr), '#e9b949', 'rgba(233,185,73,.35)');
  } else if (M === 'hrms'){
    $('bigLabel').textContent = `Active staff · as on ${pretty(d.data_as_of)}`; $('bigUnit').textContent = 'staff';
    countUp($('bigVal'), h.active_staff, 0, 1300);
    $('bigRow').innerHTML = `<span>${num(h.approved_by_eo, 0)} approved by the EO in FY ${esc(d.fy)} · ${num(h.pending_at_eo, 0)} pending</span>`;
    spark('bigSpark', seriesOf('approved_eo'), '#e9b949', 'rgba(233,185,73,.35)');
  } else {
    $('bigLabel').textContent = `Total collection · FY ${d.fy}`; $('bigUnit').textContent = '₹ cr';
    countUp($('bigVal'), cr(r.total_collection), 2, 1300);
    $('bigRow').innerHTML = (d.partial_fy ? '' : delta(r.total_collection, r.prev_collection, { d: 1 }))
      + (r.prev_fy ? `<span>FY ${esc(r.prev_fy)}: ₹${num(cr(r.prev_collection), 2)} cr</span>` : '');
    spark('bigSpark', seriesOf('collection').map(cr), '#e9b949', 'rgba(233,185,73,.35)');
  }
  // three supporting figures of the module along the bottom of the card
  const st = (l, v, s) => `<div><span>${esc(l)}</span><b>${v}</b><small>${s}</small></div>`;
  const crTxt = v => v == null ? '—' : '₹' + num(cr(v), 2) + ' cr';
  let stats;
  if (M === 'finance'){
    stats = [st('Expenditure', crTxt(f.expenditure), `FY ${esc(d.fy)}`), st('Closing balance', crTxt(f.closing_balance), f.closing_month ? 'end of ' + esc(monthName(f.closing_month)) : '—'),
      st('Books closed', pctTxt(f.books_closed_pct), `${num(f.scheme_books, 0)} year-books`)];
  } else if (M === 'hrms'){
    const payroll = (h.salary_funnel || []).reduce((a, b) => a + (b.staff || 0), 0);
    stats = [st('Seats filled', pctTxt(h.seats_filled_pct), `${num(h.elected_members, 0)} members`), st('Salaries paid', num(h.salary_paid_total, 0),
      h.salary_month ? `of ${num(payroll, 0)} · ${esc(monthName(h.salary_month))}` : '—'), st('Bank rejected', num(h.salary_rejected_total, 0), 'salaries, latest month')];
  } else {
    stats = [st('Total demand', crTxt(r.total_demand), `FY ${esc(d.fy)}`), st('Outstanding', crTxt(r.balance), 'still to collect'),
      st('Collection rate', pctTxt(r.collection_pct), `${num(d.watch_count, 0)} GPs under 20%`)];
  }
  $('bigStats').innerHTML = stats.join('');
}

function kpiCard({ title, value, d = 1, unit = '', foot = '', accent = '#7b1e34', soft = '#f8edef', icon, spark: sp, alert = false, ring = null, i = 0 }){
  const id = 'kpiSp' + i;                 // a fixed id per slot, so a switch updates the sparkline in place
  const ringSvg = ring != null ? (() => { const r = 26, c = 2 * Math.PI * r, p = Math.max(0, Math.min(1, ring / 100));
    return `<svg viewBox="0 0 64 64"><circle cx="32" cy="32" r="${r}" fill="none" stroke="#f8edef" stroke-width="7"/>
      <circle cx="32" cy="32" r="${r}" fill="none" stroke="${accent}" stroke-width="7" stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${c}"
      style="transition:stroke-dashoffset 1.2s cubic-bezier(.2,.8,.2,1)" data-to="${c * (1 - p)}"/></svg>`; })() : '';
  const v = `<div class="v"><span data-count="${value ?? ''}" data-d="${d}">—</span><small>${esc(unit)}</small></div>`;
  return `<div class="kpi${alert ? ' alert' : ''}" style="--accent:${accent};--accent-soft:${soft};animation-delay:${i * 60}ms">
    <div class="top"><span class="ico"><svg viewBox="0 0 24 24">${icon}</svg></span><span class="t">${esc(title)}</span></div>
    ${ring != null ? `<div class="ring">${ringSvg}${v}</div>` : v}
    <div class="foot">${foot}</div>${sp ? `<div class="spark"><canvas id="${id}" data-spark='${JSON.stringify(sp)}'></canvas></div>` : ''}</div>`;
}
const IC = {
  gauge: '<path d="M12 14l4-4"/><path d="M3.3 17a9 9 0 1 1 17.4 0"/><circle cx="12" cy="14" r="1.2"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z"/><path d="M4 19.5V21h16"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>',
  people: '<circle cx="9" cy="8" r="3.2"/><path d="M3 20a6 6 0 0 1 12 0"/><circle cx="17" cy="9" r="2.5"/><path d="M15.5 14.2A5 5 0 0 1 21 19"/>',
  coins: '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/><path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/>',
  stack: '<path d="M3 7l9-4 9 4-9 4z"/><path d="M3 12l9 4 9-4"/><path d="M3 17l9 4 9-4"/>',
  alertTri: '<path d="M12 3l10 18H2z"/><path d="M12 10v5"/><circle cx="12" cy="18" r=".6"/>',
  wallet: '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18"/><circle cx="16.5" cy="14.5" r="1.2"/>',
  check: '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.6 2.6L16 9.5"/>',
  cross: '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
  seat: '<path d="M6 20v-4h12v4"/><path d="M7 16V8a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v8"/>',
  pay: '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M6 10v4M18 10v4"/>',
};
function renderKpis(){
  const d = DATA, r = d.revenue, f = d.finance, h = d.hrms, M = MODULE;
  const prevOf = k => { const p = (d.series.by_fy || []).find(x => x.fy === d.prev_fy); return p ? p[k] : null; };
  const showPrev = d.prev_fy && !d.partial_fy;
  const allPct = f.gps_all_closed_pct, allAcc = allPct == null ? '#7a8699' : allPct >= 50 ? '#1f9d57' : allPct >= 20 ? '#c98a00' : '#c8372d';
  const crs = k => seriesOf(k).map(cr);
  const C = {
    collectionPct: { title: 'Collection percentage', value: r.collection_pct, d: 2, unit: '%', icon: IC.gauge,
      foot: (showPrev ? delta(r.collection_pct, r.prev_collection_pct, { pts: true, d: 2 }) + `FY ${d.prev_fy}: ${num(r.prev_collection_pct, 2)}%` : `of ₹${num(cr(r.total_demand), 2)} cr demand`),
      spark: seriesOf('collection_pct') },
    allClosed: { title: 'GPs that closed every book', value: allPct, d: 1, unit: '%', icon: IC.target, ring: allPct || 0, accent: allAcc, soft: '#faf6f7',
      foot: `${num(f.gps_all_closed, 0)} of ${num(f.gps, 0)} GPs` + (d.partial_fy ? ' · year-end not reached' : '') },
    booksClosed: { title: 'Scheme books closed', value: f.books_closed_pct, d: 2, unit: '%', icon: IC.book, accent: '#8e6819', soft: '#f7f1e3',
      foot: (showPrev ? delta(f.books_closed_pct, prevOf('books_closed_pct'), { pts: true, d: 2 }) : '') + `${num(f.scheme_books, 0)} year-books`, spark: seriesOf('books_closed_pct') },
    pending: { title: 'Registrations pending at the EO', value: h.pending_at_eo, d: 0, unit: '', icon: IC.clock, alert: (h.pending_at_eo || 0) > 0,
      accent: h.pending_at_eo ? '#c8372d' : '#1f9d57', soft: h.pending_at_eo ? '#fcebea' : '#e5f5ec',
      foot: `${num(h.approved_by_eo, 0)} approved · ${num(h.rejected_by_eo, 0)} rejected · FY ${d.fy}` },
    active: { title: 'Active staff', value: h.active_staff, d: 0, unit: 'staff', icon: IC.people, accent: '#c25b74', soft: '#fbe9ee',
      foot: `seats filled ${num(h.seats_filled_pct, 2)}% · as on ${pretty(d.data_as_of)}` },
  };
  let cards;
  if (M === 'revenue'){
    cards = [C.collectionPct,
      { title: 'Total demand', value: cr(r.total_demand), d: 2, unit: '₹ cr', icon: IC.stack, accent: '#962b45', soft: '#f8edef',
        foot: `₹${num(cr(r.arrears), 2)} cr arrears + ₹${num(cr(r.year_demand), 2)} cr this year`, spark: crs('total_demand') },
      { title: 'Outstanding balance', value: cr(r.balance), d: 2, unit: '₹ cr', icon: IC.wallet, accent: '#c8372d', soft: '#fcebea',
        foot: (showPrev ? delta(r.balance, prevOf('balance'), { d: 1, goodUp: false }) : '') + `after ₹${num(cr(r.adjustments), 2)} cr adjustments`, spark: crs('balance') },
      { title: 'Arrears brought forward', value: cr(r.arrears), d: 2, unit: '₹ cr', icon: IC.clock, accent: '#8e6819', soft: '#f7f1e3',
        foot: `${num(r.total_demand ? r.arrears / r.total_demand * 100 : null, 1)}% of the total demand`, spark: crs('arrears') },
      { title: 'GPs collecting under a fifth', value: d.watch_count, d: 0, unit: 'GPs', icon: IC.alertTri, alert: (d.watch_count || 0) > 0,
        accent: '#c8372d', soft: '#fcebea', foot: `of ${num(d.gps, 0)} GPs collected under 20% of their demand` }];
  } else if (M === 'finance'){
    const spent = f.receipts ? f.expenditure / f.receipts * 100 : null;
    const cm = (f.closure_months || []).at(-1);
    cards = [C.booksClosed, C.allClosed,
      { title: 'Scheme expenditure', value: cr(f.expenditure), d: 2, unit: '₹ cr', icon: IC.coins, accent: '#962b45', soft: '#f8edef',
        foot: `${num(spent, 1)}% of ₹${num(cr(f.receipts), 2)} cr receipts`, spark: crs('expenditure') },
      { title: 'Closing balance', value: cr(f.closing_balance), d: 2, unit: '₹ cr', icon: IC.wallet, accent: '#2a9d8f', soft: '#e3f4f2',
        foot: f.closing_month ? `in scheme accounts at the end of ${monthName(f.closing_month)}` : '—' },
      { title: 'Month-end books closed', value: cm ? cm.closed_pct : null, d: 2, unit: '%', icon: IC.check, accent: '#7b1e34', soft: '#f8edef',
        foot: cm ? `${monthName(cm.month)} month books` : '—', spark: (f.closure_months || []).map(x => x.closed_pct) }];
  } else if (M === 'hrms'){
    const payroll = (h.salary_funnel || []).reduce((a, b) => a + (b.staff || 0), 0);
    const paidPct = payroll ? h.salary_paid_total / payroll * 100 : null;
    cards = [C.pending,
      { title: 'Approved by the EO', value: h.approved_by_eo, d: 0, unit: '', icon: IC.check, accent: '#1f9d57', soft: '#e5f5ec',
        foot: `${num(h.sent_to_eo, 0)} sent to the EO · FY ${d.fy}`, spark: seriesOf('approved_eo') },
      { title: 'Rejected by the EO', value: h.rejected_by_eo, d: 0, unit: '', icon: IC.cross, accent: '#c98a00', soft: '#fdf3dc',
        foot: `registrations rejected · FY ${d.fy}`, spark: seriesOf('rejected_eo') },
      { title: 'Seats filled', value: h.seats_filled_pct, d: 2, unit: '%', icon: IC.seat, ring: h.seats_filled_pct || 0, accent: '#7b1e34', soft: '#faf6f7',
        foot: `${num(h.elected_members, 0)} of ${num(h.seats, 0)} seats · ${num(h.gps_with_president, 0)} GPs with a President` },
      { title: 'Salaries paid', value: paidPct, d: 1, unit: '%', icon: IC.pay, accent: '#2a9d8f', soft: '#e3f4f2',
        foot: h.salary_month ? `${num(h.salary_paid_total, 0)} of ${num(payroll, 0)} on the payroll · ${monthName(h.salary_month)}` : '—' }];
  } else {
    cards = [C.collectionPct, C.allClosed, C.booksClosed, C.pending, C.active];
  }
  const box = $('kpis'), sig = cards.map(c => c.title + (c.ring != null ? '◯' : '') + (c.spark ? '~' : '')).join('|');
  if (box.dataset.sig === sig){
    // the same cards (another year or zilla): update them where they stand, so nothing on the page moves
    cards.forEach((c, i) => {
      const el = box.children[i], acc = c.accent || '#7b1e34';
      el.style.setProperty('--accent', acc); el.style.setProperty('--accent-soft', c.soft || '#f8edef');
      el.classList.toggle('alert', !!c.alert);
      const v = el.querySelector('[data-count]'); countUp(v, c.value == null ? null : Number(c.value), c.d ?? 1);
      el.querySelector('.v small').textContent = c.unit || '';
      el.querySelector('.foot').innerHTML = c.foot || '';
      const ring = el.querySelector('circle[data-to]');
      if (ring){ const r = 26, circ = 2 * Math.PI * r, pr = Math.max(0, Math.min(1, (c.ring || 0) / 100));
        ring.setAttribute('stroke', acc); ring.style.strokeDashoffset = circ * (1 - pr); }
      if (c.spark) spark('kpiSp' + i, c.spark, acc, acc + '33');
    });
    return;
  }
  // a different set of cards (first visit or another module): build them, retiring the old sparklines
  Object.keys(charts).filter(k => k.startsWith('kpiSp')).forEach(k => { charts[k].destroy(); delete charts[k]; });
  box.dataset.sig = sig;
  box.dataset.n = cards.length;
  box.innerHTML = cards.map((c, i) => kpiCard({ ...c, i })).join('');
  box.querySelectorAll('[data-count]').forEach(el => { const v = el.dataset.count; if (v === '') el.textContent = '—'; else countUp(el, Number(v), Number(el.dataset.d)); });
  requestAnimationFrame(() => box.querySelectorAll('circle[data-to]').forEach(c => c.style.strokeDashoffset = c.dataset.to));
  box.querySelectorAll('canvas[data-spark]').forEach(cv => {
    const acc = getComputedStyle(cv.closest('.kpi')).getPropertyValue('--accent').trim() || '#7b1e34';
    spark(cv.id, JSON.parse(cv.dataset.spark), acc, acc + '33');
  });
}

// Month-by-month panel: Revenue (collection), Finance (scheme receipts against expenditure) or HRMS (salaries paid
// against staff on the payroll), for the same scope and FY, with the previous FY alongside. The choice is kept.
let GRAIN = (() => { try { const g = localStorage.getItem('rdpr-module'); return ['revenue', 'finance', 'hrms'].includes(g) ? g : 'revenue'; } catch (_e) { return 'revenue'; } })();
const MOD = {
  revenue: { cur: 'collection', prev: 'collection_prev', third: null, money: true, label: 'Collection' },
  finance: { cur: 'receipts', prev: 'receipts_prev', third: 'expenditure', thirdLabel: 'Expenditure', money: true, label: 'Receipts' },
  hrms: { cur: 'paid', prev: 'paid_prev', third: 'staff', thirdLabel: 'Staff on payroll', money: false, label: 'Staff paid' },
};
function setGrain(g){
  GRAIN = g;
  try { localStorage.setItem('rdpr-module', g); } catch (_e) {}
  renderMonthly();
}
const grainNow = () => MODULE || GRAIN;              // a chosen module fixes the monthly panel to that module
function renderMonthly(){
  const d = DATA, g = grainNow(), m = MOD[g];
  const tog = $('grainToggle'), btns = [...tog.querySelectorAll('button')];
  tog.hidden = !!MODULE;
  btns.forEach((b, i) => { const on = b.dataset.g === g; b.setAttribute('aria-selected', on); b.classList.toggle('on', on); if (on) tog.style.setProperty('--i', i); });
  btns.forEach(b => b.onclick = () => { if (b.dataset.g !== GRAIN) setGrain(b.dataset.g); });
  $('genTitle').textContent = t(g + 'Title');
  updateMis();
  const rows = d.months || [];
  const val = (x, k) => x[k] == null ? null : (m.money ? cr(x[k]) : x[k]);
  const hasPrev = !!d.prev_fy && rows.some(x => x[m.prev] != null);
  $('monthlyHint').textContent = `FY ${d.fy}` + (hasPrev ? ` against FY ${d.prev_fy}` : '') + (m.money ? ' · ₹ crore' : '');
  $('monthlyLegend').innerHTML = `<span><i style="background:#962b45"></i>FY ${esc(d.fy)}</span>`
    + (hasPrev ? `<span><i style="background:#e9b949"></i>FY ${esc(d.prev_fy)}</span>` : '')
    + (m.third ? `<span><i style="background:#c8372d;height:2px"></i>${esc(m.thirdLabel)}</span>` : `<span class="lg-note">Revenue is collected all year; arrears carry over</span>`);
  const empty = !rows.length || rows.every(x => !x[m.cur]);
  $('genEmpty').hidden = !empty;
  $('genEmpty').textContent = `No ${m.label.toLowerCase()} is recorded ${d.zilla ? 'for ' + d.zilla + ' ' : ''}in FY ${d.fy}.`;
  $('grainStats').innerHTML = empty ? '' : grainStats(rows.map(x => ({ label: x.label, v: val(x, m.cur) })), m);
  if (!window.Chart) return;
  if (empty){ if (charts.monthlyChart){ charts.monthlyChart.destroy(); delete charts.monthlyChart; } return; }
  const ctx = $('monthlyChart').getContext('2d');
  const grad = ctx.createLinearGradient(0, 0, 0, 280); grad.addColorStop(0, '#b8405c'); grad.addColorStop(1, '#7b1e34');
  const cur = { type: 'bar', label: 'FY ' + d.fy, data: rows.map(x => val(x, m.cur)), backgroundColor: grad, borderRadius: 6, maxBarThickness: 34, order: 3 };
  const prev = hasPrev ? [{ type: 'line', label: 'FY ' + d.prev_fy, data: rows.map(x => val(x, m.prev)), borderColor: '#e9b949', backgroundColor: '#e9b949',
    borderWidth: 2.2, pointRadius: 3, pointHoverRadius: 4, tension: .35, order: 1 }] : [];
  const third = m.third ? [{ type: 'line', label: m.thirdLabel, data: rows.map(x => val(x, m.third)), borderColor: '#c8372d', borderDash: [6, 4],
    borderWidth: 2, pointRadius: 0, tension: .2, order: 2 }] : [];
  const fmt = v => m.money ? '₹' + num(v, 2) + ' cr' : num(v, 0);
  chart('monthlyChart', { data: { labels: rows.map(x => monShort(x.label)), datasets: [cur, ...prev, ...third] },
    options: { responsive: true, maintainAspectRatio: false, animation: { duration: reduced ? 0 : 700 }, interaction: { mode: 'index', intersect: false },
      plugins: { legend: { display: false },
        tooltip: { backgroundColor: '#3f0b19', padding: 10, cornerRadius: 8,
          callbacks: { title: items => monthName(rows[items[0].dataIndex].label), label: x => ` ${x.dataset.label}: ${fmt(x.raw)}` } } },
      scales: { x: { grid: { display: false }, ticks: { color: '#5f6b7d', font: FONT, autoSkip: true, maxRotation: 0 } },
                y: { beginAtZero: true, grid: { color: 'rgba(123,30,52,.07)' }, border: { display: false },
                     ticks: { color: '#5f6b7d', font: FONT, callback: v => num(v, 0) }, title: { display: true, text: m.money ? '₹ crore' : 'staff', color: '#5f6b7d', font: FONT } } } } });
}
function grainStats(pts, m){
  const pool = pts.filter(x => x.v != null);
  if (!pool.length) return '';
  const best = pool.reduce((a, b) => (b.v > a.v ? b : a)), low = pool.reduce((a, b) => (b.v < a.v ? b : a));
  const avg = pool.reduce((a, b) => a + b.v, 0) / pool.length;
  const f = v => m.money ? '₹' + num(v, 2) + ' cr' : num(v, 0);
  return `<span class="gs up">▲ ${esc(t('gsBest'))} <b>${esc(monthName(best.label))}</b> ${f(best.v)}</span>`
    + `<span class="gs down">▼ ${esc(t('gsLow'))} <b>${esc(monthName(low.label))}</b> ${f(low.v)}</span>`
    + `<span class="gs">${esc(t('gsAvg'))} <b>${f(avg)}/month</b></span>`;
}

// Side panel of the monthly chart: a donut of how the module's total splits. Revenue (and every module): collection by
// revenue head; Finance: scheme receipts by scheme; HRMS: active staff by designation.
function renderMix(){
  const d = DATA, M = MODULE;
  let items, money = true, title, centerLbl, centerOf;
  if (M === 'finance'){
    const s = (d.finance.scheme_money || []).filter(x => x.receipts);
    const top = s.slice(0, 6), rest = s.slice(6).reduce((a, b) => a + (b.receipts || 0), 0);
    items = top.map(x => ({ name: SHORT[x.scheme] || x.scheme, full: x.scheme, v: x.receipts })).concat(rest ? [{ name: 'Other schemes', full: 'Other schemes', v: rest }] : []);
    title = 'Scheme receipts by scheme'; centerLbl = 'largest scheme'; centerOf = list => list[0];
  } else if (M === 'hrms'){
    const s = d.hrms.designations || [];
    const top = s.slice(0, 6), rest = s.slice(6).reduce((a, b) => a + (b.staff || 0), 0);
    items = top.map(x => ({ name: x.designation, full: x.designation, v: x.staff })).concat(rest ? [{ name: 'Other designations', full: 'Other designations', v: rest }] : []);
    money = false; title = 'Active staff by designation'; centerLbl = 'largest group'; centerOf = list => list[0];
  } else {
    items = d.by_head.map(x => ({ name: x.head, full: x.head, v: x.collection }));
    title = t('mixTitle'); centerLbl = t('ptShare'); centerOf = list => list.find(x => x.full === 'Property Taxes');
  }
  const total = items.reduce((a, b) => a + (b.v || 0), 0);
  $('mixTitle').textContent = title; $('mixCenterLbl').textContent = centerLbl;
  $('mixHint').textContent = M === 'hrms' ? 'as on ' + pretty(d.data_as_of) : 'FY ' + d.fy;
  const c = centerOf(items);
  $('mixCenter').textContent = num(total && c ? c.v / total * 100 : null, 0) + '%';
  const fmtV = v => money ? '₹' + num(cr(v), 2) + ' cr' : num(v, 0) + ' staff';
  $('mixList').innerHTML = items.map((x, i) => `<div class="mix-row" title="${esc(x.full)}"><i style="background:${HEAD_COLORS[i % HEAD_COLORS.length]}"></i><span class="nm">${esc(x.name)}</span>
    <span class="pc">${num(total ? x.v / total * 100 : null, 1)}%</span><span class="mu">${fmtV(x.v)}</span></div>`).join('');
  chart('mixChart', { type: 'doughnut', data: { labels: items.map(x => x.name), datasets: [{ data: items.map(x => x.v), backgroundColor: items.map((_, i) => HEAD_COLORS[i % HEAD_COLORS.length]), borderColor: '#fff', borderWidth: 3, hoverOffset: 8 }] },
    options: { cutout: '68%', responsive: true, maintainAspectRatio: false, animation: { duration: reduced ? 0 : 900 },
      plugins: { legend: { display: false }, tooltip: { backgroundColor: '#3f0b19', callbacks: { label: x => ` ${x.label}: ${fmtV(x.raw)} (${num(x.raw / total * 100, 1)}%)` } } } } });
}

function renderLeague(){
  const d = DATA, isState = !d.zilla, ref = d.revenue.collection_pct;
  $('leagueTitle').textContent = isState ? t('zillasTitle') : t('taluksTitle');
  $('leagueHint').textContent = isState ? t('leagueHint') : `Taluks of ${d.zilla} zilla · FY ${d.fy}`;
  const divs = isState ? Object.keys(DIV) : [];
  $('filters').innerHTML = isState ? ['ALL', ...divs].map(c => `<button type="button" data-c="${esc(c)}" aria-pressed="${c === FILTER}">${c === 'ALL' ? 'All' : esc(c)}</button>`).join('') : '';
  $('filters').querySelectorAll('button').forEach(b => b.onclick = () => { FILTER = b.dataset.c; renderLeague(); });
  const M = MODULE, place = isState ? 'Zilla' : 'Taluk';
  // [key, header, numeric, cell]; the last column of each module is its ratio against the state (or zilla) rate
  const color = s => isState ? divOf(s.division).color : '#962b45';
  let rows = d.league.filter(s => !isState || FILTER === 'ALL' || s.division === FILTER);
  const mx = k => Math.max(...rows.map(s => s[k] || 0), 1);
  const barCell = (s, k, money) => `<span class="bar" style="width:90px"><b style="width:${(s[k] || 0) / mx(k) * 100}%;background:${color(s)}"></b></span>${money ? num(cr(s[k]), 2) : num(s[k], 0)}`;
  const pctCell = (s, k, refV) => { const maxP = Math.max(...rows.map(x => x[k] || 0), refV || 0, 1) * 1.1;
    return `<span class="bar"><b style="width:${Math.min(100, (s[k] || 0) / maxP * 100)}%;background:${pctColor(s[k], refV)}"></b><span class="mark" style="left:${(refV || 0) / maxP * 100}%" title="${isState ? 'Karnataka' : d.zilla} ${num(refV, 2)}%"></span></span><span class="${pctClass(s[k], refV)}">${s[k] == null ? '—' : num(s[k], 2) + '%'}</span>`; };
  let cols, sub;
  if (M === 'finance'){
    const refB = d.finance.books_closed_pct;
    cols = [['gps', 'GPs', s => num(s.gps, 0)], ['receipts', 'Receipts (₹ cr)', s => barCell(s, 'receipts', true)],
      ['expenditure', 'Spent (₹ cr)', s => num(cr(s.expenditure), 2)], ['gps_all_closed', 'GPs all books closed', s => num(s.gps_all_closed, 0)],
      ['books_closed_pct', 'Books closed %', s => pctCell(s, 'books_closed_pct', refB)]];
    sub = s => `${num(s.scheme_books, 0)} scheme year-books`;
  } else if (M === 'hrms'){
    const refS = d.hrms.seats_filled_pct;
    cols = [['gps', 'GPs', s => num(s.gps, 0)], ['active_staff', 'Active staff', s => barCell(s, 'active_staff', false)],
      ['approved_by_eo', 'Approved by EO', s => num(s.approved_by_eo, 0)],
      ['pending_at_eo', 'Pending at EO', s => s.pending_at_eo ? `<span class="badge-out">${num(s.pending_at_eo, 0)}</span>` : '0'],
      ['seats_filled_pct', 'Seats filled %', s => pctCell(s, 'seats_filled_pct', refS)]];
    sub = s => `${num(s.active_staff, 0)} active staff`;
  } else {
    cols = [['gps', 'GPs', s => num(s.gps, 0)], ['demand', 'Demand (₹ cr)', s => num(cr(s.demand), 2)],
      ['collection', 'Collection (₹ cr)', s => barCell(s, 'collection', true)],
      ['yoy', 'vs last year', s => s.yoy == null ? '—' : `<span class="yoy ${s.yoy >= 0 ? 'up' : 'down'}">${s.yoy >= 0 ? '▲' : '▼'} ${num(Math.abs(s.yoy), 1)}%</span>`],
      ['collection_pct', 'Collection %', s => pctCell(s, 'collection_pct', ref)]];
    sub = s => `₹${num(cr(s.balance), 2)} cr outstanding`;
  }
  if (!cols.some(c => c[0] === SORT.key) && SORT.key !== 'name') SORT = sortDefault();
  rows = rows.slice().sort((a, b) => { const x = a[SORT.key], y = b[SORT.key];
    if (x == null) return 1; if (y == null) return -1; return (typeof x === 'string' ? x.localeCompare(y) : x - y) * SORT.dir; });
  const head = [['name', place, false], ...cols.map(c => [c[0], c[1], true])];
  $('league').innerHTML = `<thead><tr>${head.map(([k, l, n]) => `<th class="${n ? 'num' : ''}" data-k="${k}">${l}${SORT.key === k ? `<span class="arr">${SORT.dir < 0 ? '▼' : '▲'}</span>` : ''}</th>`).join('')}</tr></thead><tbody>`
    + rows.map(s => `<tr data-z="${esc(s.name)}" class="${isState ? '' : 'static'}">
      <td><div class="stn"><i style="background:${color(s)}"></i><div><b>${esc(s.name)}</b><span class="nm">${isState ? esc(divOf(s.division).label) : esc(d.zilla) + ' zilla'} · ${sub(s)}</span></div></div></td>
      ${cols.map(c => `<td class="num">${c[2](s)}</td>`).join('')}
    </tr>`).join('') + '</tbody>';
  $('league').querySelectorAll('th').forEach(th => th.onclick = () => { const k = th.dataset.k; SORT = { key: k, dir: SORT.key === k ? -SORT.dir : (k === 'name' ? 1 : -1) }; renderLeague(); });
  if (isState) $('league').querySelectorAll('tbody tr').forEach(tr => tr.onclick = () => openZilla(tr.dataset.z));
}

function renderOut(){
  const d = DATA, list = d.watch || [];
  $('outList').innerHTML = list.length ? list.map(u => `<div class="out-item"><div class="days"><b>${num(u.pct, 1)}%</b><span>collected</span></div>
      <div><div class="u">${esc(u.gp)} · ${esc(u.taluk)}</div><div class="d">${lakh(u.collection)} of ${lakh(u.demand)} demand collected<br>${lakh(u.balance)} still outstanding · ${esc(u.zilla)} zilla</div></div></div>`).join('')
      + `<div class="coal-row"><div class="sub">${num(d.watch_count, 0)} GPs ${d.zilla ? 'in ' + esc(d.zilla) + ' ' : ''}collected under a fifth of their demand in FY ${esc(d.fy)}.</div></div>`
    : '<div class="all-good">✓ Every GP collected part of its demand.</div>';
}

// Salary bills (taluk level): share of each staff type's payroll paid in the latest month, against a 95% marker,
// and the month-by-month count of salaries the bank rejected.
function renderSalary(){
  const h = DATA.hrms, list = (h.salary_funnel || []).filter(x => x.staff).slice(0, 4);
  $('coalPanel').hidden = !list.length;
  if (!list.length) return;
  const NORM = 95;
  $('coalList').innerHTML = list.map(x => { const p = x.staff ? x.paid / x.staff * 100 : 0, below = p < NORM;
    return `<div class="coal-row"><div class="top"><b>${esc(x.type)}</b><span style="color:var(--faint);font-size:.7rem">${num(x.staff, 0)} on payroll</span>
      <span class="days" style="color:${below ? 'var(--bad)' : 'var(--good)'}">${num(p, 1)} <small>% paid</small></span></div>
      <div class="gauge"><b style="width:0;background:${below ? 'linear-gradient(90deg,#c8372d,#f07a5f)' : 'linear-gradient(90deg,#1f9d57,#46d38a)'}" data-w="${Math.min(100, p)}"></b>
      <span class="norm" style="left:${NORM}%"></span></div>
      <div class="sub">${num(x.rejected, 0)} rejected by the bank · ${below ? 'below' : 'at or above'} the ${NORM}% mark</div></div>`; }).join('');
  requestAnimationFrame(() => document.querySelectorAll('#coalList .gauge b').forEach(b => b.style.width = b.dataset.w + '%'));
  const tr = h.salary_trend || [];
  const avg = tr.length ? tr.reduce((a, b) => a + (b.rejected || 0), 0) / tr.length : 0;
  chart('coalChart', { type: 'line', data: { labels: tr.map(x => monShort(x.month)), datasets: [
      { label: 'Salaries rejected by the bank', data: tr.map(x => x.rejected), borderColor: '#7b1e34', backgroundColor: 'rgba(123,30,52,.1)', fill: true, tension: .35, pointRadius: 2, borderWidth: 2 },
      { label: 'Average', data: tr.map(() => Math.round(avg)), borderColor: '#c8372d', borderDash: [5, 4], pointRadius: 0, borderWidth: 1.5 } ] },
    options: { responsive: true, maintainAspectRatio: false, animation: { duration: reduced ? 0 : 700 }, plugins: { legend: { display: false }, tooltip: { backgroundColor: '#3f0b19' } },
      scales: { x: { grid: { display: false }, ticks: { color: '#8a94a6', font: { family: 'Noto Sans', size: 10 } } }, y: { grid: { color: 'rgba(123,30,52,.06)' }, ticks: { color: '#8a94a6', font: { family: 'Noto Sans', size: 10 } } } } } });
}

// Scheme books: a bookshelf per scheme account. Ten spines stand for the scheme's year-books (each a tenth); as many
// as the share closed fill in wine, the last one partly, so a glance along the shelves compares the schemes.
const SHORT = { 'Rashtriya Gram Swaraj Abhiyan': 'RGSA', 'Library Account': 'Library', 'Statutory Grants (GP Staff Salary)': 'Staff salary grant',
  'Bapuji Seva Kendra': 'Bapuji Seva Kendra', 'SC/ST Funds 25%': 'SC/ST 25%', 'Physically Disabled 3%': 'Disabled 3%',
  'Chief Minister Grama Vikasa': 'CM Grama Vikasa', 'Statutory Grants (ESCROW)': 'ESCROW', 'Village Water Supply and Sanitation Committee': 'VWSC',
  'Swachh Bharat Mission-Gramin': 'SBM-G', 'Own Resource Funds': 'Own resources', 'Fourteen Finance Commission Grants': '14th FC', 'Fifteen Finance Commission Grants': '15th FC' };
function renderSchemes(){
  const s = (DATA.finance.by_scheme || []).filter(x => x.books).sort((a, b) => (b.closed_pct || 0) - (a.closed_pct || 0));
  $('resPanel').hidden = !s.length;
  if (!s.length) return;
  const avg = DATA.finance.books_closed_pct;
  $('shelfKey').innerHTML = `<span><i class="c"></i>closed</span><span><i class="o"></i>still open</span><span>each book is a tenth of the year-books · all schemes ${num(avg, 1)}%</span>`;
  $('shelves').classList.toggle('wide', MODULE === 'finance');
  $('shelves').innerHTML = s.map((x, i) => {
    const p = Math.max(0, Math.min(100, x.closed_pct || 0));
    const spines = Array.from({ length: 10 }, (_, k) => { const fill = Math.max(0, Math.min(1, (p - k * 10) / 10));
      return `<span class="spine"><b data-h="${Math.round(fill * 100)}" style="transition-delay:${reduced ? 0 : k * 45 + i * 25}ms"></b></span>`; }).join('');
    return `<div class="shelf-row" title="${esc(x.scheme)}: ${num(x.closed_pct, 2)}% of ${num(x.books, 0)} year-books closed">
      <div class="nm"><b>${esc(SHORT[x.scheme] || x.scheme)}</b><small>${num(x.books, 0)} GPs keep it</small></div>
      <div class="shelf">${spines}</div><div class="pc${avg != null && p < avg - 5 ? ' lo' : ''}">${num(x.closed_pct, 0)}%</div></div>`; }).join('');
  requestAnimationFrame(() => setTimeout(() => document.querySelectorAll('#shelves .spine b').forEach(b => b.style.height = b.dataset.h + '%'), 60));
}

// Finance only: the share of GP month books closed at each month end of the year.
function renderClosure(){
  const cm = DATA.finance.closure_months || [], last = cm.at(-1);
  $('closureNow').innerHTML = last ? `<b>${num(last.closed_pct, 1)}%</b><span>of GP month books closed for ${esc(monthName(last.month))}</span>` : '<span>No month books recorded.</span>';
  if (!window.Chart) return;
  chart('closureChart', { type: 'line', data: { labels: cm.map(x => monShort(x.month)), datasets: [
      { label: 'Month books closed %', data: cm.map(x => x.closed_pct), borderColor: '#7b1e34', backgroundColor: 'rgba(123,30,52,.12)', fill: true, tension: .35, pointRadius: 3, borderWidth: 2.2 }] },
    options: { responsive: true, maintainAspectRatio: false, animation: { duration: reduced ? 0 : 700 },
      plugins: { legend: { display: false }, tooltip: { backgroundColor: '#3f0b19', callbacks: { title: i => monthName(cm[i[0].dataIndex].month), label: x => ` ${num(x.raw, 2)}% closed` } } },
      scales: { x: { grid: { display: false }, ticks: { color: '#8a94a6', font: FONT } },
                y: { min: 0, max: 100, grid: { color: 'rgba(123,30,52,.06)' }, ticks: { color: '#8a94a6', font: FONT, callback: v => v + '%' } } } } });
}

// HRMS only: where this year's staff registrations stand with the EO, and the GP bodies with a President.
function renderEo(){
  const h = DATA.hrms, tot = (h.approved_by_eo || 0) + (h.rejected_by_eo || 0) + (h.pending_at_eo || 0);
  const rows = [['Approved by the EO', h.approved_by_eo, tot, 'linear-gradient(90deg,#1f9d57,#46d38a)'],
    ['Rejected by the EO', h.rejected_by_eo, tot, 'linear-gradient(90deg,#c98a00,#e9b949)'],
    ['Waiting at the EO', h.pending_at_eo, tot, 'linear-gradient(90deg,#c8372d,#f07a5f)'],
    ['GPs with a President', h.gps_with_president, h.gps_reporting, 'linear-gradient(90deg,#7b1e34,#b8405c)']];
  $('eoList').innerHTML = rows.map(([l, v, of, bg]) => `<div class="eo-row"><div class="top"><b>${esc(l)}</b><span>${num(v, 0)}</span></div>
      <div class="track"><b style="background:${bg}" data-w="${of ? Math.max(v ? 1 : 0, v / of * 100) : 0}"></b></div>
      <div class="sub">${num(of ? v / of * 100 : null, 1)}% of ${num(of, 0)} ${l.startsWith('GPs') ? 'GPs reporting' : 'registrations decided or waiting'}</div></div>`).join('')
    + `<div class="coal-row"><div class="sub">${num(h.sent_to_eo, 0)} registrations were sent to the EO in FY ${esc(DATA.fy)}.</div></div>`;
  requestAnimationFrame(() => document.querySelectorAll('#eoList .track b').forEach(b => b.style.width = b.dataset.w + '%'));
}

function renderDues(){
  const l = (DATA.by_property || []).filter(x => x.balance > 0).sort((a, b) => b.balance - a.balance).slice(0, 8);
  const max = Math.max(...l.map(x => x.balance || 0), 1), total = (DATA.by_property || []).reduce((a, b) => a + (b.balance || 0), 0);
  $('lossHint').textContent = l.length ? `FY ${DATA.fy} · by property category, ₹${num(cr(total), 2)} cr in all` : `FY ${DATA.fy}`;
  $('lossList').innerHTML = l.length ? l.map((x, i) => `<div class="loss-row"><span class="nm" title="${esc(title(x.category))}">${esc(title(x.category))}</span>
      <span class="track"><b class="${i === 0 ? 'outage' : ''}" style="width:0" data-w="${x.balance / max * 100}"></b></span><span class="mu">₹${num(cr(x.balance), 2)} cr</span></div>`).join('')
    : '<div class="all-good">No outstanding dues recorded for this period.</div>';
  requestAnimationFrame(() => document.querySelectorAll('#lossList .track b').forEach(b => b.style.width = b.dataset.w + '%'));
}

// Five-year view, by module: the module's money or count as bars, its headline ratio as the line.
const TREND = {
  revenue: { bar: 'collection', barLabel: 'Collection (₹ cr)', money: true, line: 'collection_pct', lineLabel: 'Collection %',
             hint: 'Collection (₹ crore) and collection % by financial year' },
  finance: { bar: 'receipts', barLabel: 'Scheme receipts (₹ cr)', money: true, line: 'books_closed_pct', lineLabel: 'Scheme books closed %',
             hint: 'Scheme receipts (₹ crore) and the share of year-books closed by financial year' },
  hrms: { bar: 'approved_eo', barLabel: 'Registrations approved by the EO', money: false, line: 'seats_filled_pct', lineLabel: 'Seats filled %',
          hint: 'Staff registrations approved by the EO and the share of GP seats filled by financial year' },
};
function renderTrend(){
  const d = DATA, T = TREND[MODULE || 'revenue'], s = (d.series.by_fy || []).filter(x => x[T.bar] != null);
  $('trendTitle').textContent = 'Five-year view';
  $('trendHint').textContent = T.hint;
  if (!window.Chart) return;
  const labels = s.map(x => x.fy), pcts = s.map(x => x[T.line]);
  chart('trendChart', { data: { labels, datasets: [
      { type: 'bar', label: T.barLabel, data: s.map(x => T.money ? cr(x[T.bar]) : x[T.bar]), backgroundColor: labels.map(f => f === d.fy ? '#e9b949' : 'rgba(123,30,52,.75)'), borderRadius: 5, maxBarThickness: 30, yAxisID: 'y' },
      { type: 'line', label: T.lineLabel, data: pcts, borderColor: '#c25b74', backgroundColor: '#c25b74', borderWidth: 2.5, pointRadius: 3, tension: .35, yAxisID: 'y1' } ] },
    options: { responsive: true, maintainAspectRatio: false, animation: { duration: reduced ? 0 : 800 }, interaction: { mode: 'index', intersect: false },
      plugins: { legend: { labels: { color: '#5f6b7d', font: FONT, boxWidth: 12 } }, tooltip: { backgroundColor: '#3f0b19' } },
      scales: { x: { grid: { display: false }, ticks: { color: '#5f6b7d', font: FONT } },
                y: { beginAtZero: true, grid: { color: 'rgba(123,30,52,.06)' }, border: { display: false }, ticks: { color: '#5f6b7d', font: FONT, callback: v => num(v, 0) } },
                y1: { position: 'right', min: 0, max: Math.min(100, Math.ceil((Math.max(...pcts.filter(v => v != null), 10) + 10) / 10) * 10), grid: { display: false }, border: { display: false }, ticks: { color: '#c25b74', font: FONT, callback: v => v + '%' } } } } });
}

// ------------------------------------------------------------------ MIS report (Excel): the current selection, downloaded
// The workbook is built on the server from the same payload as this page (app/mis_report.py), for the FY and zilla
// selected now and the module shown in the monthly panel ("As on screen"), or with every module ("Complete report").
const GRAIN_NAME = { revenue: 'Revenue', finance: 'Finance & Accounting', hrms: 'HRMS' };
function misScopeText(){ const d = DATA; return d ? `${d.zilla ? d.zilla + ' zilla' : 'Karnataka · all zillas'} · FY ${d.fy}` : '—'; }
function updateMis(){
  const ready = !!DATA;
  $('misBtn').disabled = !ready || $('misBtn').classList.contains('busy');
  $('misView').disabled = !ready;
  $('misView').title = ready ? `View the ${GRAIN_NAME[grainNow()]} MIS report for ${misScopeText()} before downloading it` : '';
  $('misScope').textContent = misScopeText();
  $('misOnScreenSub').textContent = ready ? `Summary and ${GRAIN_NAME[grainNow()]} sheets, ${DATA.zilla ? 'taluk' : 'zilla'} table, integrity checks` : '—';
  $('misBtn').title = ready ? `Download the ${GRAIN_NAME[grainNow()]} MIS report for ${misScopeText()}` : '';
}
let toastTimer = null;
function toast(msg, err = false){
  const el = $('toast'); $('toastMsg').textContent = msg; el.classList.toggle('err', err); el.firstElementChild.textContent = err ? '!' : '✓';
  el.classList.add('on'); clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('on'), err ? 5000 : 3200);
}
function setMisMenu(open){ $('misMenu').hidden = !open; $('misMore').setAttribute('aria-expanded', open); }
function misQuery(kind){
  const qs = new URLSearchParams({ fy: DATA.fy, kind: kind === 'all' ? 'all' : 'current', module: grainNow() }); if (DATA.zilla) qs.set('zilla', DATA.zilla);
  return qs.toString();
}
// View: the same workbook in the on-screen viewer, with its own Download button (report-viewer.js)
function viewMis(kind, opener){
  if (!DATA || !window.ReportViewer) return;
  setMisMenu(false);
  ReportViewer.open({ viewUrl: '/api/mis-report/view?' + misQuery(kind), opener, onDownload: () => downloadMis(kind, true) });
}
async function downloadMis(kind, fromViewer = false){
  if (!DATA) return;
  const btn = $('misBtn');
  setMisMenu(false); btn.classList.add('busy'); btn.disabled = true; if (!fromViewer) toast(t('misBusy'));
  try {
    const r = await fetch('/api/mis-report?' + misQuery(kind));
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const blob = await r.blob();
    const m = /filename="?([^";]+)"?/.exec(r.headers.get('Content-Disposition') || '');
    const name = m ? m[1] : `RDPR_MIS_FY${DATA.fy}.xlsx`;
    const url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
    toast(`${t('misDone')} · ${name}`);
  } catch (e) {
    if (window.console) console.error(e);
    toast(t('misFail'), true);
    if (fromViewer) throw e;
  } finally { btn.classList.remove('busy'); updateMis(); }
}
$('misBtn').onclick = () => downloadMis('current');
$('misMore').onclick = e => { e.stopPropagation(); setMisMenu($('misMenu').hidden); };
document.querySelectorAll('.mis-opt').forEach(b => b.onclick = () => downloadMis(b.dataset.kind));
document.querySelectorAll('.mis-opt-view').forEach(b => b.onclick = () => viewMis(b.dataset.kind, $('misView')));
$('misView').onclick = () => viewMis('current', $('misView'));
document.addEventListener('click', e => { if (!$('mis').contains(e.target)) setMisMenu(false); });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('misMenu').hidden){ setMisMenu(false); $('misMore').focus(); } });

// ------------------------------------------------------------------ zilla navigation (sidebar) + drill-down
function renderZillaNav(){
  const idx = DATA ? DATA.zilla_index : [];
  const groups = {}; idx.forEach(s => (groups[s.division] = groups[s.division] || []).push(s));
  $('zillaNav').innerHTML = Object.keys(DIV).filter(c => groups[c]).map(c => `<div class="side-group"><h3>${esc(divOf(c).label)}</h3>`
    + groups[c].map(s => `<button type="button" class="st-item" data-z="${esc(s.zilla)}" title="${esc(s.zilla)} · ${s.taluks} taluks · ${s.gps} GPs"><i style="background:${divOf(c).color}"></i>
        <span class="k">${esc(s.zilla)}</span><span class="n">${num(s.gps, 0)} GPs</span></button>`).join('') + '</div>').join('');
  $('zillaNav').querySelectorAll('.st-item').forEach(b => b.onclick = () => { document.body.classList.remove('sidebar-open'); openZilla(b.dataset.z); });
}
function openZilla(key){ ZILLA = key === ZILLA ? null : key; FILTER = 'ALL'; PREFETCHED = false; $('main').scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' }); load(); }
// the map always opens the zilla clicked (it never toggles back, unlike a second click in the sidebar)
function goZilla(key){ if (key === ZILLA) return; ZILLA = key; FILTER = 'ALL'; PREFETCHED = false; $('main').scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' }); load(); }
$('backBtn').onclick = () => { ZILLA = null; load(); };
$('navOverview').onclick = e => { e.preventDefault(); document.body.classList.remove('sidebar-open'); ZILLA = null; load(); };
$('fySelect').onchange = e => { FY = e.target.value; load(); };
const moduleOf = v => MODULES.includes(v) ? v : null;
function setModule(m){ MODULE = m; SORT = sortDefault(); if (DATA){ pushUrl(); render(); } }
document.querySelectorAll('#modules .mod').forEach(b => b.onclick = () => setModule(MODULE === b.dataset.m ? null : b.dataset.m));
window.addEventListener('popstate', () => { const p = new URLSearchParams(location.search); FY = p.get('fy'); ZILLA = p.get('zilla'); MODULE = moduleOf(p.get('module')); SORT = sortDefault(); load(false); });

// ------------------------------------------------------------------ Karnataka map (first card of the dashboard)
// Zilla outlines from /static/ka_zillas.json (KGIS boundaries simplified for display, all 31 zillas including
// Vijayanagara; built by scripts/make_ka_zillas_map.py). Each zilla is shaded lightly by the module's headline ratio; hovering
// names it and turns it wine; clicking opens that zilla's dashboard, exactly as the sidebar does.
const MAP_METRIC = {
  revenue: { k: 'collection_pct', label: 'Collection %', short: 'collected', state: d => d.revenue.collection_pct },
  finance: { k: 'books_closed_pct', label: 'Scheme books closed %', short: 'books closed', state: d => d.finance.books_closed_pct },
  hrms: { k: 'seats_filled_pct', label: 'Seats filled %', short: 'seats filled', state: d => d.hrms.seats_filled_pct },
};
const LO_RGB = [249, 236, 239], HI_RGB = [214, 132, 153];
let GEO = null, GEO_LOADING = null, MAPROWS = [], MAPBY = {};
function projectGeo(g){
  const polys = f => f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
  let minLon = 1e9, maxLon = -1e9, minLat = 1e9, maxLat = -1e9;
  g.features.forEach(f => polys(f).forEach(poly => poly[0].forEach(([x, y]) => {
    minLon = Math.min(minLon, x); maxLon = Math.max(maxLon, x); minLat = Math.min(minLat, y); maxLat = Math.max(maxLat, y); })));
  const PAD = 6, cos = Math.cos((minLat + maxLat) / 2 * Math.PI / 180), k = 640 / (maxLat - minLat);
  const P = ([x, y]) => [(PAD + (x - minLon) * cos * k).toFixed(1), (PAD + (maxLat - y) * k).toFixed(1)];
  const paths = g.features.map(f => ({ name: f.properties.name,
    d: polys(f).map(poly => poly.map(ring => 'M' + ring.map(p => P(p).join(',')).join('L') + 'Z').join('')).join('') }));
  return { paths, viewBox: `0 0 ${(2 * PAD + (maxLon - minLon) * cos * k).toFixed(0)} ${(2 * PAD + (maxLat - minLat) * k).toFixed(0)}` };
}
function loadGeo(){
  if (GEO) return Promise.resolve(GEO);
  if (!GEO_LOADING) GEO_LOADING = fetch('/static/ka_zillas.json').then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(g => (GEO = projectGeo(g))).catch(e => { GEO_LOADING = null; throw e; });
  return GEO_LOADING;
}
const mapMetric = () => MAP_METRIC[MODULE || 'revenue'];
const pctTxt = v => v == null ? '—' : num(v, 2) + '%';
function rankOf(name){
  const k = mapMetric().k, sorted = MAPROWS.filter(r => r[k] != null).slice().sort((a, b) => b[k] - a[k]);
  const i = sorted.findIndex(r => r.name === name); return i < 0 ? null : [i + 1, sorted.length];
}
async function renderMap(){
  let geo;
  try { geo = await loadGeo(); } catch (_e) { $('mapCard').hidden = true; return; }
  const d = DATA, mm = mapMetric();
  // the map is always of the zillas: on a zilla's page it uses the statewide page of the same year (cached / prefetched)
  let rows = d.zilla ? (PAGE_CACHE.get(keyOf(d.fy, null)) || {}).league : d.league;
  if (!rows){ rows = []; fetchPage(d.fy, null).then(() => { if (DATA && DATA.fy === d.fy) renderMap(); }).catch(() => {}); }
  MAPROWS = rows; MAPBY = Object.fromEntries(rows.map(r => [r.name, r]));
  const vals = rows.map(r => r[mm.k]).filter(v => v != null), lo = Math.min(...vals), hi = Math.max(...vals);
  const shade = v => { if (v == null) return '#efe6e8'; const x = hi === lo ? .5 : (v - lo) / (hi - lo);
    return 'rgb(' + LO_RGB.map((c, i) => Math.round(c + (HI_RGB[i] - c) * x)).join(',') + ')'; };
  const svg = $('kaMap');
  // the outlines are drawn once; a later year, zilla or module only recolours them (the fill eases), so nothing flashes
  if (!svg.dataset.built){
    svg.setAttribute('viewBox', geo.viewBox);
    svg.innerHTML = geo.paths.map(p => `<path d="${p.d}" data-z="${esc(p.name)}" tabindex="0" role="button" aria-label="${esc(p.name)}: open the dashboard"></path>`).join('');
    svg.querySelectorAll('path').forEach(p => {
      const n = p.dataset.z;
      p.addEventListener('mouseenter', () => mapInfo(n));
      p.addEventListener('mousemove', e => mapTip(n, e));
      p.addEventListener('mouseleave', () => { $('mapTip').hidden = true; mapInfo(null); });
      p.addEventListener('focus', () => mapInfo(n));
      p.addEventListener('blur', () => mapInfo(null));
      p.addEventListener('click', () => goZilla(n));
      p.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); goZilla(n); } });
    });
    svg.dataset.built = '1';
  }
  svg.querySelectorAll('path').forEach(p => {
    const sel = p.dataset.z === d.zilla;
    p.style.fill = shade((MAPBY[p.dataset.z] || {})[mm.k]);
    p.classList.toggle('sel', sel);
    if (sel) svg.appendChild(p);                  // the open zilla is drawn last, so its gold edge is on top
  });
  $('mapAsof').textContent = `FY ${d.fy}`;
  mapInfo(null, { lo, hi });
}
let LEG = { lo: null, hi: null };
function mapTip(n, e){
  const tip = $('mapTip'), r = $('mapStage').getBoundingClientRect(), mm = mapMetric();
  tip.innerHTML = `<b>${esc(n)}</b><span>${mm.label}: ${pctTxt((MAPBY[n] || {})[mm.k])}</span>`;
  tip.hidden = false;
  const x = e.clientX - r.left, y = e.clientY - r.top;
  tip.style.left = x + 'px'; tip.style.top = y + 'px';
  tip.style.transform = `translate(${x > r.width - 190 ? 'calc(-100% - 12px)' : '12px'}, ${y > r.height - 70 ? 'calc(-100% - 12px)' : '12px'})`;
}
// The panel beside the map: the zilla under the pointer, else the zilla open now, else Karnataka with the zillas at
// both ends of the module's ratio.
function mapInfo(hover, legend){
  if (legend) LEG = legend;
  const d = DATA, mm = mapMetric(), box = $('mapInfo');
  const legendHtml = `<div class="map-legend"><div class="bar-l" style="background:linear-gradient(90deg,rgb(${LO_RGB}),rgb(${HI_RGB}))"></div>
    <div class="ends"><span>${pctTxt(isFinite(LEG.lo) ? LEG.lo : null)}</span><span>${esc(mm.label)}</span><span>${pctTxt(isFinite(LEG.hi) ? LEG.hi : null)}</span></div>
    <div class="map-note">Outlines: KGIS, simplified for display; not an authoritative boundary.</div></div>`;
  const zillaHtml = (z, hovering) => {
    const r = MAPBY[z] || {}, zi = (d.zilla_index || []).find(x => x.zilla === z) || {}, rk = rankOf(z);
    return `<div class="mi-k">${hovering ? 'Zilla' : 'Showing'} · ${esc(divOf(zi.division || r.division).label)}</div>
      <div class="mi-name">${esc(z)}</div>
      <div class="mi-val">${pctTxt(r[mm.k])}<small>${esc(mm.short)}</small></div>
      <div class="mi-sub">${rk ? `Rank ${rk[0]} of ${rk[1]} zillas · ` : ''}${num(zi.taluks, 0)} taluks · ${num(zi.gps, 0)} GPs</div>
      ${stateTxt()}`;
  };
  // the statewide figure: this page when it is the state's, else the statewide page of the same year if it is loaded
  const stateTxt = () => { const st = d.zilla ? PAGE_CACHE.get(keyOf(d.fy, null)) : d;
    return st ? `<div class="mi-sub">Karnataka: ${pctTxt(mm.state(st))}</div>` : ''; };
  let html;
  if (hover){
    html = zillaHtml(hover, true)
      + (hover === d.zilla ? '<div class="mi-sub"><b>This dashboard is open now.</b></div>' : '<div class="mi-sub">Click to open its dashboard.</div>');
  } else if (d.zilla){
    html = zillaHtml(d.zilla, false) + `<button type="button" class="map-open" id="mapBack">← Back to Karnataka</button>`;
  } else {
    const k = mm.k, sorted = MAPROWS.filter(r => r[k] != null).slice().sort((a, b) => b[k] - a[k]);
    const item = r => `<button type="button" data-z="${esc(r.name)}"><b>${esc(r.name)}</b><em>${pctTxt(r[k])}</em></button>`;
    html = `<div class="mi-k">Karnataka · FY ${esc(d.fy)}</div>
      <div class="mi-val">${pctTxt(mm.state(d))}<small>${esc(mm.short)}</small></div>
      <div class="mi-sub">${num(MAPROWS.length, 0)} zillas · hover the map for one, click to open it</div>
      <div class="mi-rank"><div class="mi-k" style="color:var(--good)">Highest</div>${sorted.slice(0, 3).map(item).join('')}
        <div class="mi-k" style="color:var(--bad);margin-top:4px">Lowest</div>${sorted.slice(-3).reverse().map(item).join('')}</div>`;
  }
  box.innerHTML = html + legendHtml;
  box.querySelectorAll('.mi-rank button').forEach(b => {
    b.onclick = () => goZilla(b.dataset.z);
    const path = () => $('kaMap').querySelector(`path[data-z="${CSS.escape(b.dataset.z)}"]`);
    b.onmouseenter = () => { const p = path(); if (p) p.classList.add('hot'); };
    b.onmouseleave = () => { const p = path(); if (p) p.classList.remove('hot'); };
  });
  const back = $('mapBack'); if (back) back.onclick = () => { ZILLA = null; load(); };
}

// ------------------------------------------------------------------ AI mode transition
document.querySelectorAll('.ai-link').forEach(a => a.addEventListener('click', e => {
  e.preventDefault();
  const ov = $('overlay'); $('overlayTitle').textContent = lang === 'kn' ? 'AI ಮೋಡ್' : 'Entering AI Mode'; $('overlaySub').textContent = lang === 'kn' ? 'ಪಂಚಾಯತ್ ರಾಜ್ ದತ್ತಾಂಶ ಸಹಾಯಕ' : 'Panchayat Raj Data Assistant';
  ov.classList.remove('off');
  try { sessionStorage.setItem('rdpr-splash', '1'); } catch (_e) {}
  setTimeout(() => { location.href = a.getAttribute('href'); }, reduced ? 120 : 900);
}));

// Page links (Insights): the same logo transition as AI mode, then the real navigation.
document.querySelectorAll('.page-link').forEach(a => a.addEventListener('click', e => {
  e.preventDefault();
  const ov = $('overlay');
  $('overlayTitle').textContent = t(a.dataset.label); $('overlaySub').textContent = 'RDPR · Panchatantra 2.0';
  ov.classList.remove('off');
  try { sessionStorage.setItem('rdpr-splash', '1'); } catch (_e) {}
  setTimeout(() => { location.href = a.getAttribute('href'); }, reduced ? 120 : 900);
}));

// ------------------------------------------------------------------ language + drawer
function applyLang(l){
  lang = l; document.documentElement.lang = l;
  document.querySelectorAll('[data-i18n]').forEach(el => el.textContent = t(el.dataset.i18n));
  document.querySelectorAll('[data-i18n-html]').forEach(el => el.innerHTML = t(el.dataset.i18nHtml));
  $('langEn').setAttribute('aria-pressed', l === 'en'); $('langKn').setAttribute('aria-pressed', l === 'kn');
  try { localStorage.setItem('rdpr-lang', l); } catch (_e) {}
  if (DATA) render();
}
$('langEn').onclick = () => applyLang('en'); $('langKn').onclick = () => applyLang('kn');
$('sidebarToggle').onclick = () => document.body.classList.toggle('sidebar-open');
$('drawerBackdrop').onclick = () => document.body.classList.remove('sidebar-open');

// ------------------------------------------------------------------ start
(function(){
  let seen = null; try { seen = sessionStorage.getItem('rdpr-splash'); } catch (_e) {}
  const ov = $('overlay');
  if (seen){ ov.classList.add('off'); } else { try { sessionStorage.setItem('rdpr-splash', '1'); } catch (_e) {} setTimeout(() => ov.classList.add('off'), reduced ? 150 : 1300); }
})();
let savedLang = null; try { savedLang = localStorage.getItem('rdpr-lang'); } catch (_e) {}
applyLang(savedLang === 'kn' ? 'kn' : 'en');
{ const p = new URLSearchParams(location.search); FY = p.get('fy'); ZILLA = p.get('zilla'); MODULE = moduleOf(p.get('module')); SORT = sortDefault(); }
load(false);

// chat.html: page script (served from a file so the security policy allows no inline scripts).
// Layout and behaviour follow the KPCL Generation Assistant (AI mode, without voice). Questions go to /api/ask and the
// server streams: status (one per real pipeline stage) -> answer_chunk ... -> chart -> table -> done.
// ------------------------------------------------------------------ strings
// The language switch translates the page's own labels. Questions go to the server in English and answers come
// back in English (the semantic layer and the answer writer are English-only).
const I18N = {
  en: {
    splashTitle: 'Panchayat Raj Data Assistant', splashSub: 'Entering AI mode',
    govLine1: 'Government of Karnataka', govLine2: 'Rural Development & Panchayat Raj Department',
    appBar: '<b>Panchatantra 2.0 · Gram Panchayat MIS</b><span class="extra"><span class="sep">|</span>Finance · Revenue · HRMS<span class="sep">|</span>April 2022 – September 2026</span>',
    aiBadge: 'AI MODE', menu: 'Menu', newChat: 'New conversation', dashLink: 'Dashboard', dashSub: 'KPIs · zillas · insights', goDash: 'Opening the dashboard',
    groups: ['Revenue', 'Finance & Accounting', 'HRMS', 'Reports and reference'],
    placeholder: 'Ask about collection, arrears, book closure, scheme accounts, staff, salary bills…', send: 'Ask',
    footnote: 'Every figure comes from a checked, read-only query on the Panchatantra 2.0 Finance, Revenue and HRMS data.',
    eyebrow: 'Rural Development & Panchayat Raj Department',
    welcomeTitle: 'Panchayat Raj Data Assistant',
    cardsLabel: 'Suggested questions',
    modelReady: 'Model ready', modelOffline: 'Offline mode', modelDown: 'Server unreachable', modelChecking: '',
    stages: { understanding: 'Reading the question', querying: 'Looking up the figures', writing_sql: 'Drafting the query',
              checking_sql: 'Checking the query', running_query: 'Running the query', repairing: 'Correcting the query',
              writing_answer: 'Preparing the answer', verifying: 'Double-checking the answer', answering: 'Writing the answer' },
    elapsed: s => s + ' s', answeredIn: s => 'Answered in ' + s + ' s', spokenQuestion: 'Asked by voice', askedAs: 'Taking this as:',
    notAnswerable: 'Not answered from the data', truncated: 'Results truncated', copy: 'Copy', copied: 'Copied', dlReport: 'Download report', viewReport: 'View report', viewReportTitle: 'View this report before downloading it', dlReportBusy: 'Preparing report…', dlReportDone: 'Report downloaded', dlReportFail: 'Report unavailable, please ask again', dlReportReview: 'Under review', dlReportTitle: 'Download this answer as an Excel report',
    dataTable: n => 'Data table · ' + n + ' rows', firstRows: n => 'Showing the first ' + n + ' rows.', csv: 'Download CSV',
    technical: 'Technical details (SQL, route and timing)', noText: '(no answer text received)',
    timedOut: 'This is taking longer than expected. Please try again in a moment.',
    failed: 'Sorry, I couldn\'t answer that right now. Please try again in a moment.', partial: 'Partial answer received:',
    chartBar: 'Bar', chartLine: 'Line', chartDoughnut: 'Doughnut',
  },
  kn: {
    splashTitle: 'ಪಂಚಾಯತ್ ರಾಜ್ ದತ್ತಾಂಶ ಸಹಾಯಕ', splashSub: 'AI ಮೋಡ್ ಪ್ರವೇಶಿಸಲಾಗುತ್ತಿದೆ',
    govLine1: 'ಕರ್ನಾಟಕ ಸರ್ಕಾರ', govLine2: 'ಗ್ರಾಮೀಣಾಭಿವೃದ್ಧಿ ಮತ್ತು ಪಂಚಾಯತ್ ರಾಜ್ ಇಲಾಖೆ',
    appBar: '<b>ಪಂಚತಂತ್ರ 2.0 · ಗ್ರಾಮ ಪಂಚಾಯಿತಿ MIS</b><span class="extra"><span class="sep">|</span>ಹಣಕಾಸು · ಕಂದಾಯ · HRMS<span class="sep">|</span>ಏಪ್ರಿಲ್ 2022 – ಸೆಪ್ಟೆಂಬರ್ 2026</span>',
    aiBadge: 'AI ಮೋಡ್', menu: 'ಮೆನು', newChat: 'ಹೊಸ ಸಂಭಾಷಣೆ', dashLink: 'ಡ್ಯಾಶ್‌ಬೋರ್ಡ್', dashSub: 'ಸೂಚಕಗಳು · ಜಿಲ್ಲೆಗಳು · ಒಳನೋಟಗಳು', goDash: 'ಡ್ಯಾಶ್‌ಬೋರ್ಡ್ ತೆರೆಯಲಾಗುತ್ತಿದೆ',
    groups: ['ಕಂದಾಯ', 'ಹಣಕಾಸು ಮತ್ತು ಲೆಕ್ಕಪತ್ರ', 'HRMS', 'ವರದಿಗಳು ಮತ್ತು ಉಲ್ಲೇಖ'],
    placeholder: 'ವಸೂಲಿ, ಬಾಕಿ, ಪುಸ್ತಕ ಮುಕ್ತಾಯ, ಸಿಬ್ಬಂದಿ, ವೇತನದ ಬಗ್ಗೆ ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿ ಕೇಳಿ…', send: 'ಕೇಳಿ',
    footnote: 'ಪ್ರತಿ ಅಂಕಿಅಂಶವೂ ಪರಿಶೀಲಿಸಿದ, ಓದಲು-ಮಾತ್ರ ಪ್ರಶ್ನೆಯಿಂದ ಬರುತ್ತದೆ. ಉತ್ತರಗಳು ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿ ಇರುತ್ತವೆ.',
    eyebrow: 'ಗ್ರಾಮೀಣಾಭಿವೃದ್ಧಿ ಮತ್ತು ಪಂಚಾಯತ್ ರಾಜ್ ಇಲಾಖೆ',
    welcomeTitle: 'ಪಂಚಾಯತ್ ರಾಜ್ ದತ್ತಾಂಶ ಸಹಾಯಕ',
    cardsLabel: 'ಸೂಚಿತ ಪ್ರಶ್ನೆಗಳು',
    modelReady: 'ಮಾದರಿ ಸಿದ್ಧ', modelOffline: 'ಆಫ್‌ಲೈನ್ ಮೋಡ್', modelDown: 'ಸರ್ವರ್ ತಲುಪಲಾಗುತ್ತಿಲ್ಲ', modelChecking: '',
    stages: { understanding: 'ಪ್ರಶ್ನೆ ಓದಲಾಗುತ್ತಿದೆ', querying: 'ಅಂಕಿಅಂಶಗಳನ್ನು ಹುಡುಕಲಾಗುತ್ತಿದೆ', writing_sql: 'ಪ್ರಶ್ನೆ ರಚಿಸಲಾಗುತ್ತಿದೆ',
              checking_sql: 'ಪ್ರಶ್ನೆ ಪರಿಶೀಲಿಸಲಾಗುತ್ತಿದೆ', running_query: 'ಪ್ರಶ್ನೆ ನಡೆಸಲಾಗುತ್ತಿದೆ', repairing: 'ಪ್ರಶ್ನೆ ಸರಿಪಡಿಸಲಾಗುತ್ತಿದೆ',
              writing_answer: 'ಉತ್ತರ ಸಿದ್ಧಪಡಿಸಲಾಗುತ್ತಿದೆ', verifying: 'ಉತ್ತರವನ್ನು ಮರುಪರಿಶೀಲಿಸಲಾಗುತ್ತಿದೆ', answering: 'ಉತ್ತರ ಬರೆಯಲಾಗುತ್ತಿದೆ' },
    elapsed: s => s + ' ಸೆ', answeredIn: s => s + ' ಸೆ ನಲ್ಲಿ ಉತ್ತರಿಸಲಾಗಿದೆ', spokenQuestion: 'ಧ್ವನಿಯ ಮೂಲಕ ಕೇಳಲಾಗಿದೆ', askedAs: 'ಇದನ್ನು ಹೀಗೆ ತೆಗೆದುಕೊಳ್ಳಲಾಗಿದೆ:',
    notAnswerable: 'ದತ್ತಾಂಶದಿಂದ ಉತ್ತರಿಸಲಾಗಿಲ್ಲ', truncated: 'ಫಲಿತಾಂಶಗಳನ್ನು ಮೊಟಕುಗೊಳಿಸಲಾಗಿದೆ', copy: 'ನಕಲಿಸಿ', copied: 'ನಕಲಿಸಲಾಗಿದೆ', dlReport: 'ವರದಿ ಡೌನ್‌ಲೋಡ್', viewReport: 'ವರದಿ ವೀಕ್ಷಿಸಿ', viewReportTitle: 'ಡೌನ್‌ಲೋಡ್ ಮಾಡುವ ಮೊದಲು ವರದಿಯನ್ನು ನೋಡಿ', dlReportBusy: 'ವರದಿ ಸಿದ್ಧವಾಗುತ್ತಿದೆ…', dlReportDone: 'ವರದಿ ಡೌನ್‌ಲೋಡ್ ಆಗಿದೆ', dlReportFail: 'ವರದಿ ಲಭ್ಯವಿಲ್ಲ, ಮತ್ತೆ ಕೇಳಿ', dlReportReview: 'ಪರಿಶೀಲನೆಯಲ್ಲಿದೆ', dlReportTitle: 'ಈ ಉತ್ತರವನ್ನು Excel ವರದಿಯಾಗಿ ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ',
    dataTable: n => 'ದತ್ತಾಂಶ ಕೋಷ್ಟಕ · ' + n + ' ಸಾಲುಗಳು', firstRows: n => 'ಮೊದಲ ' + n + ' ಸಾಲುಗಳನ್ನು ತೋರಿಸಲಾಗಿದೆ.', csv: 'CSV ಡೌನ್‌ಲೋಡ್',
    technical: 'ತಾಂತ್ರಿಕ ವಿವರಗಳು (SQL ಮತ್ತು ಸಮಯ)', noText: '(ಯಾವುದೇ ಉತ್ತರ ಪಠ್ಯ ಬಂದಿಲ್ಲ)',
    timedOut: 'ನಿರೀಕ್ಷೆಗಿಂತ ಹೆಚ್ಚು ಸಮಯ ತೆಗೆದುಕೊಳ್ಳುತ್ತಿದೆ. ಸ್ವಲ್ಪ ಸಮಯದ ನಂತರ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
    failed: 'ಕ್ಷಮಿಸಿ, ಈಗ ಉತ್ತರಿಸಲಾಗಲಿಲ್ಲ. ಸ್ವಲ್ಪ ಸಮಯದ ನಂತರ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.', partial: 'ಭಾಗಶಃ ಉತ್ತರ:',
    chartBar: 'ಪಟ್ಟಿ', chartLine: 'ರೇಖೆ', chartDoughnut: 'ವೃತ್ತ',
  },
};
let lang = 'en';
const t = (k, v) => { const e = I18N[lang][k]; return typeof e === 'function' ? e(v) : e; };

// ------------------------------------------------------------------ questions
// One list feeds the sidebar (grouped) and the six welcome cards. The English question is what is sent. Every one of
// them has been answered by the live assistant; keep that true when editing.
const ICONS = {
  gauge: '<path d="M12 14l4-4"/><path d="M3.3 17a9 9 0 1 1 17.4 0"/><circle cx="12" cy="14" r="1.2"/>',
  line: '<path d="M3 3v18h18"/><path d="M7 15l4-5 3 3 5-7"/>',
  bars: '<path d="M3 3v18h18"/><path d="M8 17v-5M13 17V8M18 17V5"/>',
  calendar: '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  down: '<path d="M3 7l6 6 4-4 8 8"/><path d="M21 11v6h-6"/>',
  people: '<circle cx="9" cy="8" r="3.2"/><path d="M3 20a6 6 0 0 1 12 0"/><circle cx="17" cy="9" r="2.5"/><path d="M15.5 14.2A5 5 0 0 1 21 19"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>',
  book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z"/><path d="M4 19.5V21h16"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/>',
  alert: '<path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17h.01"/>',
};
const QUESTIONS = [
  { g: 0, q: 'Which five zillas collected the most revenue in FY 2024-25?', en: 'Top zillas by revenue collected', kn: 'ಹೆಚ್ಚು ವಸೂಲಿ ಮಾಡಿದ ಜಿಲ್ಲೆಗಳು', i: 'bars', card: 1 },
  { g: 0, q: 'What was the collection percentage in Mysuru zilla in 2024-25?', en: 'Collection percentage of a zilla', kn: 'ಜಿಲ್ಲೆಯ ವಸೂಲಿ ಶೇಕಡಾವಾರು', i: 'gauge', card: 2 },
  { g: 0, q: 'Month-wise revenue collection across Karnataka in FY 2024-25', en: 'Collection, month by month', kn: 'ತಿಂಗಳವಾರು ವಸೂಲಿ', i: 'line', card: 3 },
  { g: 0, q: 'What is the total outstanding balance for Karnataka in 2024-25?', en: 'Outstanding balance', kn: 'ಬಾಕಿ ಮೊತ್ತ', i: 'down' },
  { g: 0, q: 'Which five GPs in Badami taluk have the lowest collection percentage in FY 2025-26?', en: 'GPs collecting the least', kn: 'ಕಡಿಮೆ ವಸೂಲಿ ಗ್ರಾ.ಪಂ.ಗಳು', i: 'alert' },
  { g: 1, q: 'How many GPs closed all their books in 2024-25?', en: 'GPs that closed every book', kn: 'ಎಲ್ಲಾ ಪುಸ್ತಕ ಮುಚ್ಚಿದ ಗ್ರಾ.ಪಂ.ಗಳು', i: 'book', card: 4 },
  { g: 1, q: 'What percentage of scheme books were closed for 2024-25, by zilla?', en: 'Book closure by zilla', kn: 'ಜಿಲ್ಲಾವಾರು ಪುಸ್ತಕ ಮುಕ್ತಾಯ', i: 'bars' },
  { g: 1, q: 'Receipts and expenditure of each scheme across Karnataka in 2024-25', en: 'Scheme receipts and expenditure', kn: 'ಯೋಜನಾ ಸ್ವೀಕೃತಿ ಮತ್ತು ವೆಚ್ಚ', i: 'calendar' },
  { g: 2, q: 'How many active GP staff are there in Badami taluk, by designation?', en: 'Staff by designation', kn: 'ಹುದ್ದೆವಾರು ಸಿಬ್ಬಂದಿ', i: 'people', card: 5 },
  { g: 2, q: 'Which five taluks have the most staff registrations pending at the EO in 2025-26?', en: 'Approvals pending at the EO', kn: 'EO ಬಳಿ ಬಾಕಿ ಅನುಮೋದನೆಗಳು', i: 'clock' },
  { g: 2, q: 'Which GPs in Bagalkot zilla had no President registered in 2022-23?', en: 'GPs without a President', kn: 'ಅಧ್ಯಕ್ಷರಿಲ್ಲದ ಗ್ರಾ.ಪಂ.ಗಳು', i: 'alert' },
  { g: 3, q: 'Overall performance of Mysuru zilla in 2024-25', en: 'A zilla across all three modules', kn: 'ಮೂರೂ ವಿಭಾಗಗಳಲ್ಲಿ ಜಿಲ್ಲೆ', i: 'target', card: 6 },
  { g: 3, q: 'Which taluks need attention in 2025-26?', en: 'Taluks that need attention', kn: 'ಗಮನ ಬೇಕಾದ ತಾಲ್ಲೂಕುಗಳು', i: 'alert' },
  { g: 3, q: 'What is DCB?', en: 'Explain a term', kn: 'ಪದದ ವಿವರಣೆ', i: 'book' },
  { g: 3, q: 'What was the balance of Xyzpur taluk in 2024-25?', en: 'Safeguard: an unknown place', kn: 'ಸುರಕ್ಷತೆ: ಅಜ್ಞಾತ ಸ್ಥಳ', i: 'shield' },
];
const svg = name => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[name]}</svg>`;

// ------------------------------------------------------------------ elements
const chat = document.getElementById('chat');
const scroller = document.getElementById('chatScroll');
const box = document.getElementById('box');
const sendBtn = document.getElementById('send');
const govBrand = document.getElementById('govBrand');
let busy = false;

const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const nearBottom = () => scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 160;
const REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
// smooth for a new message and the finished answer; instant while text streams in, so it never lags behind
const toBottom = (force, smooth) => { if (force || nearBottom()) scroller.scrollTo({ top: scroller.scrollHeight, behavior: smooth && !REDUCED ? 'smooth' : 'auto' }); };

// Answers are plain text. Markup allowed: **bold**, blank-line paragraphs, and lines starting with "•" as a list.
// Everything is escaped first, so nothing in an answer can inject HTML.
function formatAnswer(text){
  const bold = s => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  return String(text).replace(/^\s+/, '').split(/\n{2,}/).map(block => {
    let html = '', list = [], para = [];
    const flushList = () => { if (list.length){ html += '<ul>' + list.map(l => '<li>' + bold(l) + '</li>').join('') + '</ul>'; list = []; } };
    const flushPara = () => { if (para.length){ html += '<p>' + para.map(bold).join('<br>') + '</p>'; para = []; } };
    block.split('\n').forEach(l => {
      const m = l.match(/^\s*[•\-]\s+(.*)$/);
      if (m){ flushPara(); list.push(m[1]); } else if (l.trim() || para.length){ flushList(); para.push(l); }
    });
    flushPara(); flushList();
    return html;
  }).join('');
}

// ------------------------------------------------------------------ sidebar + welcome
function renderSidebar(){
  const host = document.getElementById('sideGroups'); host.innerHTML = '';
  t('groups').forEach((name, gi) => {
    const g = document.createElement('div'); g.className = 'side-group';
    g.innerHTML = `<h3>${esc(name)}</h3><div class="side-list"></div>`;
    QUESTIONS.filter(x => x.g === gi).forEach(x => {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'side-item'; b.title = x[lang];
      b.innerHTML = svg(x.i) + `<span>${esc(x.q)}</span>`;
      b.onclick = () => { document.body.classList.remove('sidebar-open'); ask(x.q); };
      g.lastElementChild.appendChild(b);
    });
    host.appendChild(g);
  });
}
function renderWelcome(){
  chat.innerHTML = '';
  const w = document.createElement('div'); w.className = 'welcome'; w.id = 'welcome';
  w.innerHTML = `<div class="eyebrow">${esc(t('eyebrow'))}</div><h2>${esc(t('welcomeTitle'))}</h2>
    <div class="ornament"><i></i><b></b><i></i></div>
    <div class="cards-label">${esc(t('cardsLabel'))}</div><div class="welcome-cards"></div>`;
  const cards = w.querySelector('.welcome-cards');
  QUESTIONS.filter(x => x.card).sort((a, b) => a.card - b.card).forEach(x => {
    const b = document.createElement('button'); b.type = 'button'; b.className = 'welcome-card';
    b.innerHTML = `<span class="top">${svg(x.i)}<span class="title">${esc(x[lang])}</span></span><span class="q">${esc(x.q)}</span>`;
    b.onclick = () => ask(x.q);
    cards.appendChild(b);
  });
  chat.appendChild(w);
}

// ------------------------------------------------------------------ messages
function addMessage(who){
  const m = document.createElement('div'); m.className = 'msg ' + who;
  const av = document.createElement('div'); av.className = 'av';
  av.innerHTML = who === 'bot' ? '<img src="/static/rdpr-mark.svg" alt="">'
    : '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>';
  const b = document.createElement('div'); b.className = 'bubble';
  m.append(av, b); chat.appendChild(m); toBottom(true, true);
  return b;
}

function renderTable(host, table){
  if (!table || !Array.isArray(table.rows) || table.rows.length < 2) return;
  const d = document.createElement('details'); d.className = 'panel reveal';
  const s = document.createElement('summary');
  s.innerHTML = `<span>${esc(t('dataTable', Number(table.total_rows).toLocaleString('en-IN')))}</span>`;
  const csv = document.createElement('span'); csv.className = 'pill pill-btn csv'; csv.setAttribute('role', 'button'); csv.tabIndex = 0;
  csv.innerHTML = '<svg viewBox="0 0 24 24"><path d="M12 3v12"/><path d="M7 10l5 5 5-5"/><path d="M5 21h14"/></svg>' + esc(t('csv'));
  const dl = e => {
    e.preventDefault(); e.stopPropagation();
    // text a spreadsheet would read as a formula (=, +, -, @, tab, CR) is written as text with a leading apostrophe;
    // plain numbers such as -4.2% or +1.4% stay numbers
    const safe = v => { const s = String(v ?? ''); return /^[=+\-@\t\r]/.test(s) && !/^[+-]?[\d,]*\.?\d+%?$/.test(s) ? "'" + s : s; };
    const q = v => '"' + safe(v).replace(/"/g, '""') + '"';
    const text = [table.headers.map(q).join(',')].concat(table.rows.map(r => r.map(q).join(','))).join('\r\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['﻿' + text], { type: 'text/csv;charset=utf-8' }));
    a.download = 'rdpr-answer.csv'; document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  };
  csv.onclick = dl; csv.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') dl(e); };
  s.appendChild(csv); d.appendChild(s);
  const wrap = document.createElement('div'); wrap.className = 'table-wrap';
  const num = i => table.kinds[i] === 'number';
  let h = '<table><thead><tr>' + table.headers.map((x, i) => `<th class="${num(i) ? 'num' : ''}">${esc(x)}</th>`).join('') + '</tr></thead><tbody>';
  table.rows.forEach(r => { h += '<tr>' + r.map((v, i) => `<td class="${num(i) ? 'num' : ''}">${esc(v === '' || v == null ? '—' : v)}</td>`).join('') + '</tr>'; });
  wrap.innerHTML = h + '</tbody></table>'; d.appendChild(wrap);
  if (table.total_rows > table.rows.length){
    const n = document.createElement('div'); n.className = 'note'; n.textContent = t('firstRows', table.rows.length.toLocaleString('en-IN'));
    d.appendChild(n);
  }
  host.appendChild(d);
}

// ------------------------------------------------------------------ charts
// Chart data is built by the server from the query result (never by the model). Chart.js when it loads; a
// small SVG renderer otherwise, so charts still appear on a network without the CDN.
const PALETTE = ['#7b1e34', '#b8892b', '#8c4a5a', '#d9899d', '#8e6819', '#5f6b7d', '#5c1426', '#d6b56b', '#6e2236', '#e0b3be', '#6d5412', '#9aa4b5'];
const fmtNum = v => v == null ? 'no data' : Number(v).toLocaleString('en-IN', { maximumFractionDigits: 3 });

// The reviewed reports send {labels, datasets:[{label, data}]}; the model path sends {labels, values, series_label, unit}.
function normaliseChart(c){
  if (!c) return null;
  if (!Array.isArray(c.values) && Array.isArray(c.datasets) && c.datasets.length){
    const ds = c.datasets[0];
    return { type: c.type || 'bar', labels: c.labels, values: ds.data, series_label: ds.label || '', unit: /%/.test(ds.label || '') ? '%' : (c.unit || '') };
  }
  return c;
}

function renderChart(host, c){
  c = normaliseChart(c);
  if (!c || !Array.isArray(c.values) || c.values.length < 2) return;
  const card = document.createElement('div'); card.className = 'chart-card reveal';
  const head = document.createElement('div'); head.className = 'chart-head';
  const title = document.createElement('div'); title.className = 'chart-title';
  title.textContent = (c.series_label || '') + (c.unit && !(c.series_label || '').includes(c.unit) ? ' (' + c.unit + ')' : '');
  const tog = document.createElement('div'); tog.className = 'chart-toggle'; tog.setAttribute('role', 'group');
  const canvasWrap = document.createElement('div'); canvasWrap.className = 'chart-canvas';
  head.append(title, tog); card.append(head, canvasWrap); host.appendChild(card);

  // A doughnut shows parts of a whole, so only for additive quantities (rupees, counts), never for
  // percentages or rates.
  const allPos = c.values.every(v => v == null || v >= 0);
  const ratio = /%|\/|per |factor|rate|ratio|average|avg|pct/i.test((c.unit || '') + ' ' + (c.series_label || ''));
  const types = ['bar', 'line'].concat(allPos && !ratio && c.type === 'bar' && c.values.length <= 12 ? ['doughnut'] : []);

  // Bar and line are one chart with two series over the same axes: switching morphs it in place (the bars sink into
  // the axis while the line rises out of it, point by point) instead of tearing the chart down. The doughnut has no
  // axes, so switching to or from it crossfades into a freshly drawn chart that sweeps round.
  const reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const ink = '#5f6b7d', font = { family: 'Noto Sans', size: 11 };
  const unitTxt = c.unit ? ' ' + c.unit : '';
  const total = c.values.reduce((a, v) => a + (v || 0), 0);
  let inst = null, kind = null;
  const stagger = (ctx, step) => reduced || ctx.type !== 'data' ? 0 : ctx.dataIndex * step;
  const tooltip = dough => ({ backgroundColor: '#3f0b19', padding: 10, cornerRadius: 8, caretSize: 6, displayColors: dough,
    titleFont: { family: 'Noto Sans', weight: '600' }, bodyFont: { family: 'Noto Sans' },
    callbacks: { label: x => ' ' + (dough ? x.label : (c.series_label || '')) + ': ' + fmtNum(x.raw) + unitTxt
      + (dough && total ? '  (' + (x.raw / total * 100).toFixed(1) + '%)' : '') } });
  // a soft guide line under the pointer on the bar / line chart
  const guide = { id: 'guide', afterDatasetsDraw(ch){
    const a = ch.tooltip && ch.tooltip.getActiveElements(); if (!a || !a.length) return;
    const x = a[0].element.x, { top, bottom } = ch.chartArea, g = ch.ctx;
    g.save(); g.strokeStyle = 'rgba(123,30,52,.28)'; g.setLineDash([4, 4]); g.lineWidth = 1;
    g.beginPath(); g.moveTo(x, top); g.lineTo(x, bottom); g.stroke(); g.restore(); } };
  // the doughnut's centre: the total, or the slice under the pointer
  const centre = { id: 'centre', afterDraw(ch){
    const a = ch.getActiveElements(), g = ch.ctx;
    const meta = ch.getDatasetMeta(0), arc = meta.data[0]; if (!arc) return;
    const cx = arc.x, cy = arc.y;
    const i = a.length ? a[0].index : -1;
    const big = i >= 0 ? (total ? (c.values[i] / total * 100).toFixed(1) + '%' : fmtNum(c.values[i])) : fmtNum(total);
    const small = i >= 0 ? String(c.labels[i]).slice(0, 18) : 'Total' + unitTxt;
    g.save(); g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillStyle = '#7b1e34'; g.font = '600 17px "Noto Serif", serif'; g.fillText(big, cx, cy - 7);
    g.fillStyle = ink; g.font = '11px "Noto Sans", sans-serif'; g.fillText(small, cx, cy + 12);
    g.restore(); } };

  const layer = () => { const l = document.createElement('div'); l.className = 'chart-layer'; const cv = document.createElement('canvas');
    l.appendChild(cv); canvasWrap.appendChild(l); return [l, cv]; };
  const buildCartesian = (cv, type) => {
    const ctx = cv.getContext('2d'), h = canvasWrap.clientHeight || 250;
    const barGrad = ctx.createLinearGradient(0, 0, 0, h); barGrad.addColorStop(0, '#a8344f'); barGrad.addColorStop(1, '#7b1e34');
    const barHover = ctx.createLinearGradient(0, 0, 0, h); barHover.addColorStop(0, '#c24e6a'); barHover.addColorStop(1, '#962b45');
    const areaGrad = ctx.createLinearGradient(0, 0, 0, h); areaGrad.addColorStop(0, 'rgba(123,30,52,.20)'); areaGrad.addColorStop(1, 'rgba(123,30,52,0)');
    const cfg = {
      type: 'bar',
      data: { labels: c.labels, datasets: [
        { type: 'bar', label: c.series_label || '', data: c.values.slice(), order: 2,
          backgroundColor: c.values.map(v => v == null ? '#e3d7da' : barGrad), hoverBackgroundColor: barHover,
          borderWidth: 0, borderRadius: 5, borderSkipped: 'bottom', maxBarThickness: 44, minBarLength: 3 },
        { type: 'line', label: c.series_label || '', data: c.values.slice(), order: 1,
          borderColor: '#7b1e34', backgroundColor: areaGrad, borderWidth: 2.2, fill: true, tension: .32, spanGaps: true,
          pointBackgroundColor: '#b8892b', pointBorderColor: '#fff', pointBorderWidth: 1.5, pointRadius: 3.5,
          pointHoverRadius: 7, pointHoverBackgroundColor: '#7b1e34', pointHoverBorderWidth: 2 } ] },
      options: {
        responsive: true, maintainAspectRatio: false,
        // first draw: the bars (or points) rise one after another, left to right
        animation: { duration: reduced ? 0 : 750, easing: 'easeOutQuart', delay: ctx => ctx.mode === 'default' ? stagger(ctx, 26) : 0 },
        transitions: { active: { animation: { duration: reduced ? 0 : 180 } } },
        interaction: { mode: 'index', intersect: false },
        // only the series on show answers the pointer
        plugins: { legend: { display: false }, tooltip: { ...tooltip(false), filter: item => item.datasetIndex === ch.$on } },
        scales: {
          x: { ticks: { color: ink, maxRotation: 45, autoSkip: true, font }, grid: { display: false }, border: { color: '#e0d2d6' } },
          y: { beginAtZero: true, ticks: { color: ink, font, callback: v => Number(v).toLocaleString('en-IN') }, border: { display: false },
               grid: { color: 'rgba(123,30,52,.07)' }, title: { display: !!c.unit, text: c.unit || '', color: ink, font } },
        },
      },
      plugins: [guide],
    };
    // the series not on show starts flat on the zero line and invisible, ready to rise
    const on = type === 'line' ? 1 : 0;
    seriesLook(cfg, on, false);
    const ch = new Chart(ctx, cfg);
    ch.$on = on;
    return ch;
  };
  // One series rests on the zero line (data 0, no colour, no points); the other carries the values. Switching swaps
  // them in a single update, so the outgoing series sinks while the incoming one rises, point by point.
  const seriesLook = (ch, on, animate) => {
    const [bar, line] = ch.data.datasets;
    bar.data = on === 0 ? c.values.slice() : c.values.map(() => 0);
    line.data = on === 1 ? c.values.slice() : c.values.map(() => 0);
    bar.minBarLength = on === 0 ? 3 : 0;
    line.borderColor = on === 1 ? '#7b1e34' : 'rgba(123,30,52,0)';
    line.pointRadius = on === 1 ? 3.5 : 0;
    line.pointBorderWidth = on === 1 ? 1.5 : 0;
    line.pointHoverRadius = on === 1 ? 7 : 0;
    line.pointHoverBorderWidth = on === 1 ? 2 : 0;
    line.fill = on === 1;
    ch.$on = on;
    if (animate) ch.update();
  };
  const buildDoughnut = cv => new Chart(cv.getContext('2d'), {
    type: 'doughnut',
    data: { labels: c.labels, datasets: [{ data: c.values, backgroundColor: c.labels.map((_, i) => PALETTE[i % PALETTE.length]),
      borderColor: '#fff', borderWidth: 2, hoverOffset: 10, hoverBorderColor: '#fff' }] },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '60%', layout: { padding: 6 },
      animation: { duration: reduced ? 0 : 900, easing: 'easeOutQuart', animateRotate: true, animateScale: true },
      interaction: { mode: 'nearest', intersect: true },
      plugins: { legend: { display: true, position: 'right', labels: { color: ink, boxWidth: 10, usePointStyle: true, pointStyle: 'rectRounded', font } },
                 tooltip: tooltip(true) },
    },
    plugins: [centre],
  });
  // swap in a new chart on its own layer; the old one fades out underneath, then is destroyed
  const crossfade = build => {
    const old = canvasWrap.querySelector('.chart-layer.on'), oldInst = inst;
    const [l, cv] = layer();
    inst = build(cv);
    requestAnimationFrame(() => l.classList.add('on'));
    if (old){ old.classList.remove('on'); old.classList.add('off');
      setTimeout(() => { if (oldInst) oldInst.destroy(); old.remove(); }, reduced ? 0 : 420); }
  };
  const morph = type => { const on = type === 'line' ? 1 : 0; if (inst.$on !== on) seriesLook(inst, on, true); };
  const draw = type => {
    if (!window.Chart){ canvasWrap.innerHTML = svgChart(c, type === 'line' ? 'line' : 'bar'); return; }
    const want = type === 'doughnut' ? 'doughnut' : 'cartesian';
    if (inst && kind === 'cartesian' && want === 'cartesian'){ morph(type); return; }
    kind = want;
    crossfade(cv => want === 'doughnut' ? buildDoughnut(cv) : buildCartesian(cv, type));
  };

  // the toggle: a wine thumb slides to the chosen button
  const thumb = document.createElement('span'); thumb.className = 'thumb'; thumb.setAttribute('aria-hidden', 'true'); tog.appendChild(thumb);
  const place = b => { thumb.style.width = b.offsetWidth + 'px'; thumb.style.transform = `translateX(${b.offsetLeft}px)`; };
  const initial = types.includes(c.type) ? c.type : 'bar';
  types.forEach(ty => {
    const b = document.createElement('button'); b.type = 'button';
    b.textContent = t('chart' + ty[0].toUpperCase() + ty.slice(1));
    b.setAttribute('aria-pressed', ty === initial ? 'true' : 'false');
    b.onclick = () => {
      if (b.getAttribute('aria-pressed') === 'true') return;
      tog.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', 'false')); b.setAttribute('aria-pressed', 'true');
      place(b); draw(ty);
    };
    tog.appendChild(b);
  });
  requestAnimationFrame(() => { const on = tog.querySelector('button[aria-pressed="true"]'); if (on){ tog.classList.add('no-anim'); place(on);
    requestAnimationFrame(() => tog.classList.remove('no-anim')); } });
  draw(initial);
}

function svgChart(c, type){
  const n = c.labels.length, W = 820, H = 250, L = 60, B = 56, T = 12, R = 10, pw = W - L - R, ph = H - T - B;
  const vals = c.values.map(v => v == null ? 0 : v);
  const mx = Math.max(...vals, 0), mn = Math.min(0, ...vals);
  const p = Math.pow(10, Math.floor(Math.log10(Math.max(Math.abs(mx), 1e-9)))), max = mx > 0 ? Math.ceil(mx / p) * p : 1;
  const y = v => T + ph - (v - mn) / ((max - mn) || 1) * ph, step = pw / n;
  let s = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${esc(c.series_label || '')}">`;
  for (let i = 0; i <= 4; i++){ const v = mn + (max - mn) * i / 4, yy = y(v);
    s += `<line x1="${L}" x2="${W - R}" y1="${yy}" y2="${yy}" stroke="#7b1e34" opacity=".07"/><text x="${L - 6}" y="${yy + 4}" text-anchor="end">${fmtNum(v)}</text>`; }
  if (type === 'line'){
    s += `<polyline fill="none" stroke="#7b1e34" stroke-width="2" points="${vals.map((v, i) => (L + step * i + step / 2) + ',' + y(v)).join(' ')}"/>`;
    vals.forEach((v, i) => s += `<circle cx="${L + step * i + step / 2}" cy="${y(v)}" r="3.5" fill="#b8892b" stroke="#fff"><title>${esc(c.labels[i])}: ${fmtNum(c.values[i])}</title></circle>`);
  } else {
    vals.forEach((v, i) => { const bw = Math.max(2, Math.min(44, step * .7)), x = L + step * i + (step - bw) / 2;
      s += `<rect x="${x}" y="${y(Math.max(v, 0))}" width="${bw}" height="${Math.abs(y(v) - y(0))}" rx="3" fill="${c.values[i] == null ? '#e3d7da' : '#962b45'}"><title>${esc(c.labels[i])}: ${fmtNum(c.values[i])}</title></rect>`; });
  }
  const every = Math.ceil(n / 14);
  c.labels.forEach((l, i) => { if (i % every) return;
    s += `<text transform="translate(${L + step * i + step / 2},${T + ph + 12}) rotate(35)">${esc(String(l).slice(0, 16))}</text>`; });
  return s + '</svg>';
}

// ------------------------------------------------------------------ "View report" / "Download report" (Excel)
// Shown when the answer came from the data. The server kept that answer under report_id and builds the workbook from
// it (an overview of Karnataka or a zilla downloads the dashboard's complete MIS report).
function viewButton(id){
  const b = document.createElement('button'); b.type = 'button'; b.className = 'pill pill-btn view-btn'; b.title = t('viewReportTitle');
  b.innerHTML = '<svg viewBox="0 0 24 24"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>' + esc(t('viewReport'));
  b.onclick = () => window.ReportViewer && ReportViewer.open({ viewUrl: '/api/answer-report/' + encodeURIComponent(id) + '/view', opener: b,
    onDownload: () => downloadReport(id) });
  return b;
}

// the Excel file for a kept answer; resolves when the browser has been handed the file
async function downloadReport(id){
  const r = await fetch('/api/answer-report/' + encodeURIComponent(id));
  if (r.status === 409){ const b = await r.json().catch(() => ({})); const e = new Error('under review'); e.review = b.message || ''; throw e; }
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const blob = await r.blob();
  const m = /filename="?([^";]+)"?/.exec(r.headers.get('Content-Disposition') || '');
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = m ? m[1] : 'RDPR_Report.xlsx';
  document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 4000);
}

function reportButton(id){
  const b = document.createElement('button'); b.type = 'button'; b.className = 'pill pill-btn report-btn'; b.title = t('dlReportTitle');
  const ic = '<svg viewBox="0 0 24 24"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M12 11v6"/><path d="M9.5 14.5 12 17l2.5-2.5"/></svg>';
  const spin = '<svg viewBox="0 0 24 24"><path d="M21 12a9 9 0 1 1-6.2-8.6"/></svg>';
  const label = (icon, text, xl) => { b.innerHTML = icon + esc(text) + (xl ? '<span class="xl">XLSX</span>' : ''); };
  label(ic, t('dlReport'), true);
  let busy = false;
  b.onclick = async () => {
    if (busy) return; busy = true;
    b.classList.remove('fail'); b.classList.add('busy'); label(spin, t('dlReportBusy'));
    try {
      await downloadReport(id);
      b.classList.remove('busy'); label(ic, t('dlReportDone'), true);
      setTimeout(() => label(ic, t('dlReport'), true), 2200);
    } catch (e) {
      if (window.console) console.error(e);
      b.classList.remove('busy'); b.classList.add('fail');
      if (e && e.review){ label(ic, t('dlReportReview')); b.title = e.review; } else label(ic, t('dlReportFail'));
    } finally { busy = false; }
  };
  return b;
}

// ------------------------------------------------------------------ meta row
function renderMeta(bubble, done, sql, secs, answerText){
  const meta = document.createElement('div'); meta.className = 'meta reveal';
  if (done && done.answerable === false){
    bubble.classList.add('refused');
    const p = document.createElement('span'); p.className = 'pill nf'; p.textContent = t('notAnswerable'); meta.appendChild(p);
  }
  if (done && done.truncated){ const p = document.createElement('span'); p.className = 'pill trunc'; p.textContent = t('truncated'); meta.appendChild(p); }
  const time = document.createElement('span'); time.textContent = t('answeredIn', secs); meta.appendChild(time);
  const sp = document.createElement('span'); sp.className = 'spacer'; meta.appendChild(sp);
  if (done && done.report_id){ meta.append(viewButton(done.report_id), reportButton(done.report_id)); }
  if (answerText){
    const cp = document.createElement('button'); cp.type = 'button'; cp.className = 'pill pill-btn';
    const ic = '<svg viewBox="0 0 24 24"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>';
    cp.innerHTML = ic + esc(t('copy'));
    cp.onclick = async () => {
      try { await navigator.clipboard.writeText(answerText.replace(/\*\*/g, '')); cp.innerHTML = ic + esc(t('copied'));
            setTimeout(() => { cp.innerHTML = ic + esc(t('copy')); }, 1400); } catch (_e) { /* clipboard blocked */ }
    };
    meta.appendChild(cp);
  }
  bubble.appendChild(meta);
  // SQL, route and timings: only when the server runs with RDPR_SHOW_TECHNICAL_DETAILS=true.
  if (done && done.technical && (sql || done.timing_ms)){
    const d = document.createElement('details'); d.className = 'panel';
    d.innerHTML = `<summary>${esc(t('technical'))}</summary>`;
    const tm = done.timing_ms || {};
    const parts = Object.keys(tm).map(k => k.replace(/_ms$/, '') + ': ' + tm[k] + 'ms');
    if (parts.length){ const x = document.createElement('div'); x.className = 'timing'; x.textContent = (done.route ? 'route: ' + done.route + ' · ' : '') + parts.join(' · '); d.appendChild(x); }
    if (sql){ const pre = document.createElement('pre'); pre.textContent = sql; d.appendChild(pre); }
    bubble.appendChild(d);
  }
}

// ------------------------------------------------------------------ ask (SSE)
// The server streams: status (one per real pipeline stage) -> [spoken, voice mode] -> answer_chunk ... -> chart -> table
// -> done. Voice mode: ask(text, { mode: 'voice' }) resolves as soon as the spoken form arrives ({ spoken_answer,
// answerable }), so the voice can start while the text is still typing out; null when nothing was answered.
const CLIENT_TIMEOUT_MS = 200000;   // the gateway's own timeout is 180 s
// The last question that was answered (as the server took it), sent with the next one so a follow-up ("and Hassan?",
// "what about 2023-24?") is answered as the whole question it stands for (app/followup.py). Cleared by New conversation.
let lastAsked = '';

function ask(text, opts){
  let settle = null;
  const settled = new Promise(r => { settle = r; });
  askRun(text, opts || {}, settle);
  return settled;
}

async function askRun(text, opts, settleFn){
  const voiceTurn = opts.mode === 'voice';
  let settle = settleFn;
  const resolveOnce = v => { if (settle){ const f = settle; settle = null; f(v); } };
  text = (text || '').trim();
  if (!text || busy){ resolveOnce(null); return; }
  busy = true; sendBtn.disabled = true;
  const w = document.getElementById('welcome'); if (w) w.remove();
  const ub = addMessage('user'); ub.textContent = text; if (!voiceTurn) box.value = '';
  if (voiceTurn){ ub.classList.add('voice-q'); ub.title = t('spokenQuestion'); }

  const bot = addMessage('bot');
  const progress = document.createElement('div'); progress.className = 'progress';
  progress.innerHTML = '<div class="progress-bar"></div><div class="progress-row"><div class="stages"></div><div class="elapsed"></div></div>';
  const stagesEl = progress.querySelector('.stages'), elapsedEl = progress.querySelector('.elapsed');
  const answerEl = document.createElement('div'); answerEl.className = 'answer';
  bot.append(progress, answerEl);
  govBrand.classList.add('thinking');

  const t0 = performance.now();
  const secs = () => ((performance.now() - t0) / 1000).toFixed(1);
  const tick = setInterval(() => { elapsedEl.textContent = t('elapsed', Math.floor((performance.now() - t0) / 1000)); }, 500);
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), CLIENT_TIMEOUT_MS);
  let acc = '', sql = '', done = null, table = null, chartData = null, streaming = false;

  const showStage = stage => {
    const label = (t('stages') || {})[stage]; if (!label) return;
    stagesEl.querySelectorAll('.stage.now').forEach(s => { s.classList.remove('now'); s.classList.add('done'); });
    const s = document.createElement('span'); s.className = 'stage now'; s.innerHTML = '<i></i>'; s.appendChild(document.createTextNode(label));
    stagesEl.appendChild(s); toBottom();
  };
  const endProgress = () => {
    clearInterval(tick);
    if (progress.isConnected) progress.remove();
    govBrand.classList.remove('thinking');
  };

  const frame = f => {
    let ev = '', data = '';
    f.split('\n').forEach(l => { if (l.startsWith('event:')) ev = l.slice(6).trim(); else if (l.startsWith('data:')) data += l.slice(5).trim(); });
    if (!ev || !data) return;
    let d; try { d = JSON.parse(data); } catch (_e) { return; }
    if (ev === 'status'){ if (d.stage !== 'answering') showStage(d.stage); }
    else if (ev === 'followup' && d.asked_as){
      const note = document.createElement('div'); note.className = 'asked-as';
      note.textContent = t('askedAs') + ' '; const b = document.createElement('b'); b.textContent = d.asked_as; note.appendChild(b);
      bot.insertBefore(note, progress); toBottom();
    }
    else if (ev === 'sql') sql = d.sql || '';
    else if (ev === 'answer_chunk'){
      if (!streaming){ streaming = true; endProgress(); answerEl.classList.add('streaming'); }
      acc += d.text; answerEl.innerHTML = formatAnswer(acc); toBottom();
    }
    else if (ev === 'chart') chartData = d.chart;
    else if (ev === 'table') table = d.table;
    else if (ev === 'done') done = d;
    else if (ev === 'spoken') resolveOnce({ spoken_answer: d.spoken_answer || '', answerable: d.answerable });
  };

  try {
    const r = await fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify(Object.assign({ question: text }, voiceTurn ? { mode: 'voice' } : {}, lastAsked ? { previous: lastAsked } : {})),
                                        signal: ctrl.signal });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const reader = r.body.getReader(), dec = new TextDecoder(); let buf = '';
    while (true){
      const { value, done: end } = await reader.read(); if (end) break;
      buf += dec.decode(value, { stream: true });
      let i; while ((i = buf.indexOf('\n\n')) >= 0){ frame(buf.slice(0, i)); buf = buf.slice(i + 2); }
    }
    buf += dec.decode(); if (buf.trim()) frame(buf);
    clearTimeout(timer); endProgress();
    answerEl.classList.remove('streaming');
    if (!acc) answerEl.textContent = t('noText'); else answerEl.innerHTML = formatAnswer(acc);
    renderChart(bot, chartData);
    renderTable(bot, table);
    renderMeta(bot, done, sql, secs(), acc.trim());
    bot.classList.add('settled');
    if (done && done.context) lastAsked = done.asked_as || text;   // only answers from the data; a refusal or a definition keeps the earlier context
    resolveOnce(acc ? { spoken_answer: (done && done.spoken_answer) || '', answer: acc, answerable: done ? done.answerable : true } : null);
  } catch (e) {
    clearTimeout(timer); endProgress();
    answerEl.classList.remove('streaming');
    if (window.console) console.error(e);   // never show raw error text to users
    bot.classList.add('err');
    answerEl.innerHTML = formatAnswer((e && e.name === 'AbortError' ? t('timedOut') : t('failed')) + (acc ? '\n\n' + t('partial') + '\n' + acc : ''));
  }
  resolveOnce(null);
  requestAnimationFrame(() => toBottom(false, true));
  busy = false; sendBtn.disabled = false; if (!voiceTurn) box.focus();
}

// ------------------------------------------------------------------ model status (kept quiet, in the footnote)
let status = 'checking';
function renderStatus(){
  const el = document.getElementById('modelStatus');
  el.className = 'model-status' + (status === 'ready' ? ' ok' : status === 'offline' ? ' off' : status === 'down' ? ' bad' : '');
  document.getElementById('modelStatusText').textContent =
    t({ ready: 'modelReady', offline: 'modelOffline', down: 'modelDown', checking: 'modelChecking' }[status]);
}
fetch('/health').then(r => r.json()).then(h => { status = h.llm_configured ? 'ready' : 'offline'; renderStatus(); })
  .catch(() => { status = 'down'; renderStatus(); });

// ------------------------------------------------------------------ language
function save(k, v){ try { localStorage.setItem(k, v); } catch (_e) {} }
function load(k){ try { return localStorage.getItem(k); } catch (_e) { return null; } }
function applyLang(l){
  lang = l; document.documentElement.lang = l;
  document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll('[data-i18n-html]').forEach(el => { el.innerHTML = t(el.dataset.i18nHtml); });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => { el.placeholder = t(el.dataset.i18nPlaceholder); });
  document.getElementById('langEn').setAttribute('aria-pressed', l === 'en' ? 'true' : 'false');
  document.getElementById('langKn').setAttribute('aria-pressed', l === 'kn' ? 'true' : 'false');
  renderStatus(); renderSidebar();
  if (document.getElementById('welcome')) renderWelcome();
  save('rdpr-lang', l);
}
document.getElementById('langEn').onclick = () => applyLang('en');
document.getElementById('langKn').onclick = () => applyLang('kn');

// ------------------------------------------------------------------ wiring
sendBtn.onclick = () => ask(box.value);
box.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.isComposing) ask(box.value); });
document.addEventListener('keydown', e => {
  if (e.key === '/' && document.activeElement !== box && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)){ e.preventDefault(); box.focus(); }
});
document.getElementById('dashLink').addEventListener('click', e => {
  e.preventDefault();
  const href = e.currentTarget.getAttribute('href');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const ov = document.createElement('div'); ov.className = 'go-overlay';
  ov.innerHTML = '<div class="splash-logos"><span class="splash-halo"><img src="/static/emblem.png" alt=""></span>'
    + '<span class="splash-halo"><img src="/static/rdpr-mark.svg" alt=""></span></div>'
    + '<div class="splash-text"><b></b><small>RDPR · Panchatantra 2.0</small></div>';
  ov.querySelector('b').textContent = t('goDash');
  document.body.appendChild(ov);
  try { sessionStorage.setItem('rdpr-splash', '1'); } catch (_e) {}
  setTimeout(() => { location.href = href; }, reduced ? 100 : 750);
});
document.getElementById('newchat').onclick = () => { if (busy) return; lastAsked = ''; renderWelcome(); document.body.classList.remove('sidebar-open'); box.focus(); };
document.getElementById('sidebarToggle').onclick = () => document.body.classList.toggle('sidebar-open');
document.getElementById('drawerBackdrop').onclick = () => document.body.classList.remove('sidebar-open');

// Splash plays once per browser session.
(function(){
  const sp = document.getElementById('splash');
  let seen = null; try { seen = sessionStorage.getItem('rdpr-splash'); } catch (_e) {}
  if (seen){ sp.remove(); return; }
  try { sessionStorage.setItem('rdpr-splash', '1'); } catch (_e) {}
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  setTimeout(() => { sp.classList.add('gone'); setTimeout(() => sp.remove(), 550); }, reduced ? 200 : 1400);
})();

renderWelcome();
applyLang(load('rdpr-lang') === 'kn' ? 'kn' : 'en');
// ?q=... (links from the dashboard) asks straight away
{ const pre = new URLSearchParams(location.search).get('q'); if (pre) ask(pre.slice(0, 500)); }
box.focus();

// Voice mode: the voice panel (voice/voice-ui.js) asks through the same ask() as typing, so every spoken answer is
// rendered, charted, tabled and downloadable exactly like a typed one.
window.RDPRChat = { ask, isBusy: () => busy, lang: () => lang };
window.dispatchEvent(new Event('rdprchat:ready'));

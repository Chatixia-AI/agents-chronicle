/* Chronicle dashboard: vanilla JS, no build step. */
"use strict";

// =====================================================================================
// DOM helpers (all untrusted text goes through textContent)
// =====================================================================================
const $ = (sel, root = document) => root.querySelector(sel);
const SVGNS = "http://www.w3.org/2000/svg";

function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  setAttrs(e, attrs);
  append(e, kids);
  return e;
}
function s(tag, attrs, ...kids) {
  const e = document.createElementNS(SVGNS, tag);
  setAttrs(e, attrs);
  append(e, kids);
  return e;
}
function setAttrs(e, attrs) {
  if (!attrs) return;
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") e.setAttribute("class", v);
    else if (k === "style" && typeof v === "object") Object.assign(e.style, v);
    else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
    else if (k === "html") e.innerHTML = v; // only for output of our own escaping renderers
    else if (k === "text") e.textContent = v;
    else e.setAttribute(k, v === true ? "" : v);
  }
}
function append(e, kids) {
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false || kid === "") continue;
    e.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
}
function safeUrl(u) { return /^https?:\/\//i.test(String(u || "")) ? String(u) : null; }
function extLink(url, label) {
  const u = safeUrl(url);
  return u ? h("a", { href: u, target: "_blank", rel: "noopener" }, label) : h("span", null, label);
}
function escapeHtml(t) {
  return String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// =====================================================================================
// Icons: 24px stroke glyphs drawn in currentColor (strings are path data; [tag, attrs] for other shapes)
// =====================================================================================
const C10 = ["circle", { cx: 12, cy: 12, r: 10 }];
const ICONS = {
  overview: [["rect", { x: 3, y: 3, width: 7, height: 9, rx: 1.5 }], ["rect", { x: 14, y: 3, width: 7, height: 5, rx: 1.5 }],
    ["rect", { x: 14, y: 12, width: 7, height: 9, rx: 1.5 }], ["rect", { x: 3, y: 16, width: 7, height: 5, rx: 1.5 }]],
  sessions: ["M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"],
  prompts: ["M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z", "M8 8h8", "M8 12h5"],
  knowledge: ["M2 4h6a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2z", "M22 4h-6a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h7z"],
  projects: ["M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"],
  glossary: ["M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20", "m8 13 4-7 4 7", "M9.1 11h5.8"],
  home: ["m3 10 9-7 9 7v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z", "M9 22V12h6v10"],
  settings: ["M4 21v-7", "M4 10V3", "M12 21v-9", "M12 8V3", "M20 21v-5", "M20 12V3", "M1 14h6", "M9 8h6", "M17 16h6"],
  sidebar: [["rect", { x: 3, y: 3, width: 18, height: 18, rx: 3 }], "M9 3v18"],
  left: ["m15 18-6-6 6-6"],
  right: ["m9 18 6-6-6-6"],
  outline: ["M8 6h13", "M8 12h13", "M8 18h13", "M3 6h.01", "M3 12h.01", "M3 18h.01"],
  appearance: [C10, ["path", { d: "M12 2a10 10 0 0 0 0 20z", class: "solid" }]],
  map: ["m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3z", "M9 3v15", "M15 6v15"],
  playbook: [C10, "m16.24 7.76-2.12 6.36-6.36 2.12 2.12-6.36z"],
  reviews: [["rect", { x: 3, y: 4, width: 18, height: 18, rx: 2 }], "M16 2v4", "M8 2v4", "M3 10h18", "m9 16 2 2 4-4"],
  sources: ["M12 22v-5", "M9 8V2", "M15 8V2", "M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8z"],
  status: ["M22 12h-4l-3 9L9 3l-3 9H2"],
  search: [["circle", { cx: 11, cy: 11, r: 7 }], "m21 21-4.3-4.3"],
  sync: ["M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8", "M3 3v5h5", "M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16", "M16 16h5v5"],
  moon: ["M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z"],
  sun: [["circle", { cx: 12, cy: 12, r: 4 }], "M12 2v2", "M12 20v2", "m4.93 4.93 1.41 1.41", "m17.66 17.66 1.41 1.41", "M2 12h2", "M20 12h2", "m6.34 17.66-1.41 1.41", "m19.07 4.93-1.41 1.41"],
  clock: [["circle", { cx: 12, cy: 12, r: 9 }], "M12 7v5l3 2"],
  zap: ["M13 2 3 14h9l-1 8 10-12h-9z"],
  tokens: ["M4 9h16", "M4 15h16", "M10 3 8 21", "M16 3l-2 18"],
  cost: ["M12 2v20", "M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"],
  diff: ["M12 3v12", "M6 9h12", "M6 21h12"],
  sparkles: ["M12 3l1.7 4.6L18.3 9.3l-4.6 1.7L12 15.6l-1.7-4.6L5.7 9.3l4.6-1.7z", "M19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"],
  pin: ["M12 17v5", "M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"],
  x: ["M18 6 6 18", "m6 6 12 12"],
  download: ["M12 3v12", "m7 10 5 5 5-5", "M5 21h14"],
  arrow: ["M5 12h14", "m12 5 7 7-7 7"],
  branch: ["M6 3v12", ["circle", { cx: 18, cy: 6, r: 3 }], ["circle", { cx: 6, cy: 18, r: 3 }], "M18 9a9 9 0 0 1-9 9"],
  flame: ["M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.07-2.14-.22-4.05 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.15.43-2.29 1-3a2.5 2.5 0 0 0 2.5 2.5z"],
  calendar: [["rect", { x: 3, y: 4, width: 18, height: 18, rx: 2 }], "M16 2v4", "M8 2v4", "M3 10h18"],
  dot: [["circle", { cx: 12, cy: 12, r: 3 }]],
  // knowledge kinds
  fix: ["M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"],
  gotcha: ["m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3", "M12 9v4", "M12 17h.01"],
  learning: ["M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5", "M9 18h6", "M10 22h4"],
  decision: ["M12 3v3", "M12 13v8", "M5 6h11l3 3.5-3 3.5H5z"],
  pattern: ["M8.3 10a.7.7 0 0 1-.63-1.02l3.7-6a.7.7 0 0 1 1.26 0l3.7 6A.7.7 0 0 1 15.7 10z", ["rect", { x: 3, y: 14, width: 7, height: 7, rx: 1 }], ["circle", { cx: 17.5, cy: 17.5, r: 3.5 }]],
  command: ["m4 17 6-6-6-6", "M12 19h8"],
  fact: [C10, "M12 16v-4", "M12 8h.01"],
  preference: [["circle", { cx: 12, cy: 8, r: 4 }], "M5 21a7 7 0 0 1 14 0"],
  reference: ["M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71", "M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"],
  todo: [["rect", { x: 3, y: 3, width: 18, height: 18, rx: 2 }], "m9 12 2 2 4-4"],
  // outcomes and analysis states
  completed: [C10, "m9 12 2 2 4-4"],
  partial: [C10, ["path", { d: "M12 2a10 10 0 0 1 0 20z", class: "solid" }]],
  blocked: [C10, "m4.9 4.9 14.2 14.2"],
  abandoned: [C10, "m15 9-6 6", "m9 9 6 6"],
  exploratory: [C10, "m16.24 7.76-2.12 6.36-6.36 2.12 2.12-6.36z"],
  unclear: [C10, "M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3", "M12 17h.01"],
  history: ["M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8", "M3 3v5h5", "M12 7v5l4 2"],
  queued: [C10, "M12 6v6l4 2"],
  pause: ["M9 5v14", "M15 5v14"],
  running: ["M21 12a9 9 0 1 1-6.22-8.56"],
  skipped: [C10, "M8 12h8"],
  // glossary categories
  file: ["M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z", "M14 2v6h6"],
  concept: ["M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5", "M9 18h6", "M10 22h4"],
  component: ["M8.3 10a.7.7 0 0 1-.63-1.02l3.7-6a.7.7 0 0 1 1.26 0l3.7 6A.7.7 0 0 1 15.7 10z", ["rect", { x: 3, y: 14, width: 7, height: 7, rx: 1 }], ["circle", { cx: 17.5, cy: 17.5, r: 3.5 }]],
  data: [["ellipse", { cx: 12, cy: 5, rx: 9, ry: 3 }], "M3 5v14a9 3 0 0 0 18 0V5", "M3 12a9 3 0 0 0 18 0"],
  domain: [C10, "M2 12h20", "M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"],
  tool: ["M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"],
  library: ["M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z", "M3.3 7 12 12l8.7-5", "M12 22V12"],
  system: [["rect", { x: 5, y: 5, width: 14, height: 14, rx: 2 }], ["rect", { x: 9, y: 9, width: 6, height: 6, rx: 1 }], "M9 2v3", "M15 2v3", "M9 19v3", "M15 19v3", "M2 9h3", "M2 15h3", "M19 9h3", "M19 15h3"],
  platform: ["m12 2 10 5-10 5L2 7z", "m2 17 10 5 10-5", "m2 12 10 5 10-5"],
  organization: [["rect", { x: 4, y: 2, width: 16, height: 20, rx: 2 }], "M9 22v-4h6v4", "M8 6h.01", "M12 6h.01", "M16 6h.01", "M8 10h.01", "M12 10h.01", "M16 10h.01", "M8 14h.01", "M12 14h.01", "M16 14h.01"],
  service: [["rect", { x: 2, y: 3, width: 20, height: 8, rx: 2 }], ["rect", { x: 2, y: 13, width: 20, height: 8, rx: 2 }], "M6 7h.01", "M6 17h.01"],
  acronym: ["M4 7V4h16v3", "M9 20h6", "M12 4v16"],
};
ICONS.person = ICONS.preference;
ICONS.other = ICONS.dot;
function icon(name, cls = "") {
  return s("svg", { class: `icon ${cls}`, viewBox: "0 0 24 24", "aria-hidden": "true" },
    (ICONS[name] || ICONS.dot).map((p) => (typeof p === "string" ? s("path", { d: p }) : s(p[0], p[1]))));
}

// =====================================================================================
// Formatting
// =====================================================================================
const nf = new Intl.NumberFormat();
function fmtNum(n) { return n == null ? "–" : nf.format(Math.round(n)); }
function fmtCompact(n) {
  if (n == null || isNaN(n)) return "–";
  const a = Math.abs(n);
  const f = (v, u) => (v >= 100 ? v.toFixed(0) : v >= 10 ? v.toFixed(1).replace(/\.0$/, "") : v.toFixed(1).replace(/\.0$/, "")) + u;
  if (a >= 1e9) return f(n / 1e9, "B");
  if (a >= 1e6) return f(n / 1e6, "M");
  if (a >= 1e3) return f(n / 1e3, "k");
  return String(Math.round(n));
}
function fmtCost(v) {
  if (v == null) return "–";
  if (v >= 1000) return "$" + nf.format(Math.round(v));
  if (v >= 100) return "$" + v.toFixed(0);
  return "$" + v.toFixed(2);
}
function fmtDur(sec) {
  if (sec == null) return "–";
  sec = Math.round(sec);
  if (sec < 60) return sec + "s";
  const m = Math.floor(sec / 60), hh = Math.floor(m / 60), d = Math.floor(hh / 24);
  if (d >= 1) return `${d}d ${hh % 24}h`;
  if (hh >= 1) return `${hh}h ${String(m % 60).padStart(2, "0")}m`;
  return `${m}m`;
}
function fmtHours(sec) { if (sec == null) return "–"; const hrs = sec / 3600; return `${hrs >= 10 ? Math.round(hrs) : Math.round(hrs * 10) / 10}h`; }
const dateFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });
const dateYFmt = new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" });
const dtFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
const timeFmt = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });
const wdFmt = new Intl.DateTimeFormat(undefined, { weekday: "short", month: "short", day: "numeric", year: "numeric" });
function d(ts) { return ts ? new Date(ts) : null; }
function fmtDate(ts) { return ts ? dateFmt.format(d(ts)) : "–"; }
function fmtDateY(ts) { return ts ? dateYFmt.format(d(ts)) : "–"; }
function fmtDT(ts) { return ts ? dtFmt.format(d(ts)) : "–"; }
function fmtTime(ts) { return ts ? timeFmt.format(d(ts)) : ""; }
function ago(ts) {
  if (!ts) return "never";
  const sec = (Date.now() - new Date(ts).getTime()) / 1000;
  if (sec < 60) return "just now";
  if (sec < 3600) return Math.round(sec / 60) + " min ago";
  if (sec < 86400) return Math.round(sec / 3600) + " h ago";
  return Math.round(sec / 86400) + " d ago";
}
function localDate(ts) { // YYYY-MM-DD in local time
  const x = new Date(ts);
  return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
}
function shortPath(p, root) {
  if (!p) return "";
  if (root && p.startsWith(root.replace(/\/$/, "") + "/")) return p.slice(root.replace(/\/$/, "").length + 1);
  return p.replace(/^\/Users\/[^/]+/, "~");
}

const KIND = {
  fix: "Fix", gotcha: "Gotcha", learning: "Learning", decision: "Decision", pattern: "Pattern",
  command: "Command", fact: "Fact", preference: "Preference", reference: "Reference", todo: "Todo",
};
function kindPlural(k) { const l = kindLabel(k); return /(x|s|ch|sh)$/.test(l) ? `${l}es` : `${l}s`; }
function kindLabel(k) { return KIND[k] || k || "Note"; }
function kindChip(k) { return h("span", { class: "kind-chip" }, icon(KIND[k] ? k : "dot"), kindLabel(k)); }
function catBadge(c) { return h("span", { class: "badge cat" }, icon(ICONS[c] && c !== "x" ? c : "dot"), c || "other"); }
// outcome -> [status class, label]; status colors always travel with an icon and a label
const OUTCOME = {
  completed: ["good", "Completed"], partial: ["warning", "Partial"], blocked: ["critical", "Blocked"],
  abandoned: ["serious", "Abandoned"], exploratory: ["accent", "Exploratory"], unclear: ["", "Unclear"],
};
const STATUS_LABEL = {
  pending: "queued", stale: "needs re-analysis", running: "analyzing…", error: "analysis failed", skipped: "skipped", done: "analyzed",
};
const STATUS_ICON = { pending: "queued", stale: "queued", running: "running", error: "gotcha", skipped: "skipped", done: "completed" };

const AGENTS = { claude: "Claude Code", codex: "Codex", copilot: "GitHub Copilot", bob: "IBM Bob", "claude-ai": "Claude.ai", chatgpt: "ChatGPT" };
const AGENT_SHORT = { claude: "Claude", codex: "Codex", copilot: "Copilot", bob: "Bob", "claude-ai": "Claude.ai", chatgpt: "ChatGPT" };
function agentShort(a) { return AGENT_SHORT[a] || a || "Claude"; }
function agentName(a) { return AGENTS[a] || "Claude Code"; }
function agentTag(a, title) { return a && a !== "claude" ? h("span", { class: `agent-tag a-${a}`, title: title || `${agentName(a)} session` }, agentShort(a)) : null; }

function outcomeBadge(outcome, status, source) {
  if (source === "history") return h("span", { class: "badge", title: "Recovered from prompt history; transcript was deleted before Chronicle" }, icon("history"), "history");
  if (outcome && OUTCOME[outcome]) {
    const [cls, label] = OUTCOME[outcome];
    return h("span", { class: `badge ${cls}` }, icon(outcome), label);
  }
  const cls = status === "error" ? "critical" : status === "running" ? "accent" : "";
  return h("span", { class: `badge ${cls}` }, icon(STATUS_ICON[status] || "dot", status === "running" ? "spin" : ""), STATUS_LABEL[status] || status || "–");
}
function confidenceMeter(level) { // three steps; the fill is the accent, the track a lighter step of it
  const n = { high: 3, medium: 2, low: 1 }[level] || 0;
  return n ? h("span", { class: "meter", title: `${level} confidence`, "aria-label": `${level} confidence` },
    [1, 2, 3].map((i) => h("i", { class: i <= n ? "on" : "" }))) : null;
}

// =====================================================================================
// Markdown (escape first, then a small safe subset)
// =====================================================================================
function mdInline(t) {
  const codes = [];
  t = t.replace(/`([^`\n]+)`/g, (m, c) => { codes.push(`<code>${c}</code>`); return `\u0001${codes.length - 1}\u0001`; });
  t = t.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, "$1<em>$2</em>");
  t = t.replace(/\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  t = t.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
  t = t.replace(/&lt;sub&gt;(.*?)&lt;\/sub&gt;/g, '<span class="muted">$1</span>');
  return t.replace(/\u0001(\d+)\u0001/g, (m, i) => codes[+i]);
}
function md(src) {
  if (!src) return "";
  const blocks = [];
  let text = escapeHtml(src).replace(/```[\w+-]*[^\S\n]*\n?([\s\S]*?)```/g, (m, code) => {
    blocks.push(`<pre><code>${code.replace(/\n$/, "")}</code></pre>`);
    return `\n\u0000${blocks.length - 1}\u0000\n`;
  });
  const out = [];
  let list = null, para = [], table = null;
  const flushPara = () => { if (para.length) { out.push(`<p>${mdInline(para.join("<br>"))}</p>`); para = []; } };
  const flushList = () => { if (list) { out.push(`<${list.type}>${list.items.map((i) => `<li>${mdInline(i)}</li>`).join("")}</${list.type}>`); list = null; } };
  const flushTable = () => {
    if (table) {
      const rows = table.filter((r) => !/^\s*\|?\s*:?-{2,}/.test(r));
      out.push("<table>" + rows.map((r, i) => "<tr>" + r.replace(/^\s*\|/, "").replace(/\|\s*$/, "").split("|")
        .map((c) => (i === 0 ? `<th>${mdInline(c.trim())}</th>` : `<td>${mdInline(c.trim())}</td>`)).join("") + "</tr>").join("") + "</table>");
      table = null;
    }
  };
  for (const line of text.split("\n")) {
    let m;
    if (/^\u0000\d+\u0000$/.test(line.trim())) { flushPara(); flushList(); flushTable(); out.push(line.trim()); continue; }
    if (/^\s*\|.*\|\s*$/.test(line)) { flushPara(); flushList(); (table ||= []).push(line); continue; }
    flushTable();
    if ((m = line.match(/^(#{1,4})\s+(.*)/))) { flushPara(); flushList(); out.push(`<h4>${mdInline(m[2])}</h4>`); continue; }
    if ((m = line.match(/^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?(.*)/))) {
      flushPara();
      const type = /^\s*\d/.test(line) ? "ol" : "ul";
      if (!list || list.type !== type) { flushList(); list = { type, items: [] }; }
      list.items.push(m[1]);
      continue;
    }
    if ((m = line.match(/^&gt;\s?(.*)/))) { flushPara(); flushList(); out.push(`<blockquote>${mdInline(m[1])}</blockquote>`); continue; }
    if (!line.trim()) { flushPara(); flushList(); continue; }
    if (list && /^\s{2,}\S/.test(line)) { list.items[list.items.length - 1] += " " + line.trim(); continue; }
    flushList();
    para.push(line);
  }
  flushPara(); flushList(); flushTable();
  return out.join("").replace(/\u0000(\d+)\u0000/g, (m, i) => blocks[+i]);
}
function mdEl(src, cls = "") { return h("div", { class: `md gloss ${cls}`, html: md(src) }); }
function snippetEl(text) { // server marks matches with «»
  return h("span", { html: escapeHtml(text).replace(/«(.*?)»/g, "<mark>$1</mark>") });
}

// =====================================================================================
// API
// =====================================================================================
async function api(path, params) {
  const url = new URL(path, location.origin);
  if (params) for (const [k, v] of Object.entries(params)) if (v != null && v !== "") url.searchParams.set(k, v);
  const res = await fetch(url);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || res.statusText);
  return res.json();
}
async function post(path, body) {
  const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json", "X-Chronicle": "1" }, body: JSON.stringify(body || {}) });
  return res.json();
}
let toastTimer;
function toast(msg, ms = 3500) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), ms);
}

// =====================================================================================
// Tooltip (values lead, labels follow)
// =====================================================================================
const tip = () => $("#tooltip");
function showTip(evt, value, label, extra) {
  const t = tip();
  t.replaceChildren(...[ // replaceChildren would print a null as the text "null"
    h("div", { class: "tt-value" }, value),
    label ? h("div", { class: "tt-label" }, label) : null,
    extra ? h("div", { class: "tt-label" }, extra) : null,
  ].filter(Boolean));
  t.hidden = false;
  moveTip(evt);
}
function moveTip(evt) {
  const t = tip();
  const pad = 14, r = t.getBoundingClientRect();
  let x = evt.clientX + pad, y = evt.clientY + pad;
  if (x + r.width > innerWidth - 8) x = evt.clientX - r.width - pad;
  if (y + r.height > innerHeight - 8) y = evt.clientY - r.height - pad;
  t.style.left = x + "px";
  t.style.top = y + "px";
}
function hideTip() { tip().hidden = true; }
function hoverable(node, getContent, { focusable = true } = {}) {
  node.addEventListener("pointerenter", (e) => { const [v, l, x] = getContent(); showTip(e, v, l, x); node.classList.add("hover"); });
  node.addEventListener("pointermove", moveTip);
  node.addEventListener("pointerleave", () => { hideTip(); node.classList.remove("hover"); });
  if (!focusable) return; // inside a link or row that is itself focusable
  node.setAttribute("tabindex", "0");
  node.addEventListener("focus", () => { const r = node.getBoundingClientRect(); const [v, l, x] = getContent(); showTip({ clientX: r.right, clientY: r.top }, v, l, x); });
  node.addEventListener("blur", hideTip);
}

// =====================================================================================
// Charts
// =====================================================================================
function niceTicks(max, count = 4) {
  if (!max || max <= 0) return [0, 1];
  const raw = max / count, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((st) => st >= raw) || raw;
  const ticks = [];
  for (let v = 0; v <= max + step * 0.001; v += step) ticks.push(v);
  if (ticks[ticks.length - 1] < max) ticks.push(ticks[ticks.length - 1] + step);
  return ticks;
}
function barPath(x, y, w, hgt, r) {
  if (hgt <= 0) return "";
  r = Math.min(r, w / 2, hgt);
  return `M${x},${y + hgt}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + hgt}Z`;
}
function responsive(container, draw) {
  let last = 0;
  const run = () => { const w = container.clientWidth; if (w && Math.abs(w - last) > 2) { last = w; container.replaceChildren(); draw(w); } };
  const ro = new ResizeObserver(() => requestAnimationFrame(run));
  ro.observe(container);
  requestAnimationFrame(run);
}

// A chart card: title, hint, optional tools, and a table-view twin.
function chartCard(title, hint, drawFn, table, tools = [], iconName = null) {
  const body = h("div", { class: "chart" });
  const tableBox = h("div", { class: "table-scroll", hidden: true });
  let showingTable = false;
  const toggle = h("button", { class: "link-btn", type: "button", onclick: () => {
    showingTable = !showingTable;
    toggle.textContent = showingTable ? "Chart" : "Table";
    body.hidden = showingTable;
    tableBox.hidden = !showingTable;
    if (showingTable && !tableBox.firstChild) tableBox.append(renderTable(typeof table === "function" ? table() : table));
  } }, "Table");
  const card = h("section", { class: "card" },
    h("div", { class: "card-head" }, h("div", null, h("div", { class: "card-title" }, iconName ? icon(iconName) : null, h("h2", null, title)), hint ? h("div", { class: "hint" }, hint) : null),
      h("div", { class: "tools" }, tools, table ? toggle : null)),
    body, tableBox);
  responsive(body, (w) => drawFn(body, w));
  return card;
}
function renderTable(spec) {
  return h("table", { class: "table-view" },
    h("thead", null, h("tr", null, spec.columns.map((c, i) => h("th", { class: spec.num?.[i] ? "num" : "" }, c)))),
    h("tbody", null, spec.rows.map((r) => h("tr", null, r.map((c, i) => h("td", { class: spec.num?.[i] ? "num" : "" }, c))))));
}

function columnChart(container, width, data, { value, fmt, label, height = 210, avg = 0, name = "Daily", unit = 1 }) {
  const m = { l: 44, r: 8, t: 10, b: 24 };
  const iw = width - m.l - m.r, ih = height - m.t - m.b;
  const vals = data.map(value);
  const max = Math.max(0, ...vals);
  const ticks = niceTicks(max / unit).map((t) => t * unit);
  const top = ticks[ticks.length - 1] || 1;
  const band = iw / Math.max(data.length, 1);
  const bw = Math.max(2, Math.min(24, band - 2));
  const svg = s("svg", { width, height, viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "column chart" });
  const g = s("g", { transform: `translate(${m.l},${m.t})` });
  svg.append(g);
  for (const t of ticks) {
    const y = ih - (t / top) * ih;
    g.append(s("line", { class: t === 0 ? "baseline" : "gridline", x1: 0, x2: iw, y1: Math.round(y) + 0.5, y2: Math.round(y) + 0.5 }));
    g.append(s("text", { class: "axis tick-num chart-label", x: -8, y: y + 3.5, "text-anchor": "end" }, fmt(t)));
  }
  // trailing moving average, same unit and axis as the bars
  const means = avg ? vals.map((_, i) => { const win = vals.slice(Math.max(0, i - avg + 1), i + 1); return win.reduce((a, b) => a + b, 0) / win.length; }) : null;
  const every = Math.max(1, Math.ceil(data.length / Math.max(2, Math.floor(iw / 70))));
  data.forEach((dd, i) => {
    const v = vals[i], x = i * band + (band - bw) / 2, bh = (v / top) * ih;
    if (bh > 0) g.append(s("path", { class: "bar", d: barPath(x, ih - bh, bw, Math.max(bh, 1), 4) }));
    if (i % every === 0) g.append(s("text", { class: "chart-label", x: i * band + band / 2, y: ih + 16, "text-anchor": "middle" }, fmtDate(dd.date + "T12:00:00")));
  });
  if (means && data.length > avg) {
    g.append(s("path", { class: "avg-line", d: "M" + means.map((v, i) => `${(i * band + band / 2).toFixed(1)},${(ih - (v / top) * ih).toFixed(1)}`).join("L") }));
    container.append(legendKey([["accent", name], ["line", `${avg}-day average`]]));
  }
  data.forEach((dd, i) => {
    const hit = s("rect", { class: "hit", x: i * band, y: 0, width: band, height: ih });
    hoverable(hit, () => [fmt(vals[i]), label(dd), means ? `${avg}-day average ${fmt(means[i])}` : null]);
    g.append(hit);
  });
  container.append(svg);
}

function heatColor(level) { return `var(--seq-${level})`; }

function calendarHeatmap(container, width, rows) {
  const byDate = Object.fromEntries(rows.map((r) => [r.date, r]));
  const today = new Date(); today.setHours(12, 0, 0, 0);
  const first = rows.length ? new Date(rows[0].date + "T12:00:00") : today;
  const active = new Set(rows.filter((r) => r.sessions).map((r) => r.date));
  let longest = 0, run = 0;
  for (const d = new Date(first); d <= today; d.setDate(d.getDate() + 1)) {
    run = active.has(localDate(d)) ? run + 1 : 0;
    longest = Math.max(longest, run);
  }
  let streak = 0;
  const back = new Date(today);
  if (!active.has(localDate(back))) back.setDate(back.getDate() - 1); // today's first session may still be ahead
  while (active.has(localDate(back))) { streak++; back.setDate(back.getDate() - 1); }
  const busiest = rows.reduce((b, r) => ((r.active_s || 0) > (b?.active_s || 0) ? r : b), null);
  const side = width >= 560 ? 190 : 0;
  const left = 30, topPad = 16, gap = 3, gridW = width - side;
  const dataWeeks = Math.ceil((today - first) / (7 * 86400000)) + 1;
  const weeks = Math.max(1, Math.min(53, Math.floor((gridW - left) / (10 + gap)), Math.max(dataWeeks, 18)));
  const start = new Date(today); start.setDate(start.getDate() - start.getDay() - (weeks - 1) * 7);
  const cell = Math.max(9, Math.min(20, Math.floor((gridW - left) / weeks) - gap));
  const step = cell + gap;
  const height = topPad + 7 * step + 4, svgW = left + weeks * step;
  const svg = s("svg", { width: svgW, height, viewBox: `0 0 ${svgW} ${height}`, role: "img", "aria-label": "activity calendar" });
  const days = (n) => `${n} day${n === 1 ? "" : "s"}`;
  const stats = h("div", { class: "cal-stats" },
    fact("current streak", days(streak)), fact("longest streak", days(longest)), fact("active days this year", fmtNum(active.size)),
    busiest?.active_s ? fact("busiest day", `${fmtDate(busiest.date + "T12:00:00")} · ${fmtDur(busiest.active_s)}`) : null);
  const thresholds = [1, 15 * 60, 30 * 60, 3600, 2 * 3600, 4 * 3600];
  ["Mon", "Wed", "Fri"].forEach((lbl, i) => svg.append(s("text", { class: "chart-label", x: 0, y: topPad + (1 + i * 2) * step + cell - 2 }, lbl)));
  let lastMonth = -1;
  for (let w = 0; w < weeks; w++) {
    for (let dow = 0; dow < 7; dow++) {
      const day = new Date(start); day.setDate(start.getDate() + w * 7 + dow);
      if (day > today) continue;
      const key = localDate(day), r = byDate[key];
      const activeS = r ? r.active_s || 0 : 0;
      let level = 0;
      thresholds.forEach((t, i) => { if (activeS >= t) level = i + 1; });
      if (r && r.sessions && level === 0) level = 1;
      const rect = s("rect", { class: "cell", x: left + w * step, y: topPad + dow * step, width: cell, height: cell, rx: cell > 12 ? 3 : 2, fill: heatColor(level) });
      hoverable(rect, () => [r ? `${fmtDur(activeS)} active` : "No sessions", wdFmt.format(day), r ? `${r.sessions} session${r.sessions === 1 ? "" : "s"} · ${r.prompts || 0} prompts` : null]);
      rect.addEventListener("click", () => r && go(`#/sessions?day=${key}`));
      svg.append(rect);
      if (dow === 0 && day.getMonth() !== lastMonth && day.getDate() <= 7) {
        lastMonth = day.getMonth();
        svg.append(s("text", { class: "chart-label", x: left + w * step, y: 10 }, day.toLocaleString(undefined, { month: "short" })));
      }
    }
  }
  container.append(h("div", { class: "cal-wrap" },
    h("div", null, svg, scaleLegend(["none", "<15m", "15–30m", "30m–1h", "1–2h", "2–4h", "4h+"])), stats));
}
function scaleLegend(labels) {
  return h("div", { class: "scale-legend" }, "Less", labels.map((l, i) => h("i", { style: { background: heatColor(i) }, title: l })), "More");
}

function hourGrid(container, width, rows) {
  const counts = {}; let max = 0;
  rows.forEach((r) => { counts[`${r.dow}-${r.hour}`] = r.n; max = Math.max(max, r.n); });
  const left = 34, topPad = 4, bottom = 18, gap = 2;
  const cell = Math.max(8, Math.min(24, Math.floor((width - left) / 24) - gap));
  const step = cell + gap, height = topPad + 7 * step + bottom;
  const svg = s("svg", { width, height, viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "activity by hour of week" });
  const order = [1, 2, 3, 4, 5, 6, 0], names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  order.forEach((dow, row) => {
    svg.append(s("text", { class: "chart-label", x: 0, y: topPad + row * step + cell - 3 }, names[row]));
    for (let hr = 0; hr < 24; hr++) {
      const n = counts[`${dow}-${hr}`] || 0;
      const level = n === 0 ? 0 : Math.min(6, 1 + Math.floor((n / (max || 1)) * 5.999));
      const rect = s("rect", { class: "cell", x: left + hr * step, y: topPad + row * step, width: cell, height: cell, rx: 2, fill: heatColor(level) });
      hoverable(rect, () => [`${n} prompt${n === 1 ? "" : "s"}`, `${names[row]} ${String(hr).padStart(2, "0")}:00–${String((hr + 1) % 24).padStart(2, "0")}:00`]);
      svg.append(rect);
    }
  });
  for (let hr = 0; hr < 24; hr += 3) svg.append(s("text", { class: "chart-label", x: left + hr * step, y: height - 4 }, String(hr).padStart(2, "0")));
  const peak = rows.reduce((b, r) => (r.n > (b?.n || 0) ? r : b), null);
  const dayName = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  container.append(svg, h("div", { class: "chart-foot" }, scaleLegend(["0", "", "", "", "", "", "max"]),
    peak ? h("span", { class: "chart-note" }, "Busiest hour: ", h("b", null, `${dayName[peak.dow]} ${String(peak.hour).padStart(2, "0")}:00`), ` · ${fmtNum(peak.n)} prompts`) : null));
}

// Horizontal bars; `part` splits each bar's end into a second (critical) segment, e.g. failed calls
function hbars(items, { label, value, fmt, href, sub, max, part, lead } = {}) {
  const top = max ?? Math.max(0, ...items.map(value));
  if (!items.length) return h("div", { class: "empty" }, "No data");
  return h("div", { class: "hbars" }, items.map((it) => {
    const v = value(it), p = part ? Math.min(part(it) || 0, v) : 0;
    const text = label(it);
    const name = href ? h("a", { class: "name", href: href(it), title: text }, lead ? lead(it) : null, text) : h("span", { class: "name", title: text }, lead ? lead(it) : null, text);
    const pct = (n) => (top ? (n / top) * 100 : 0);
    const row = h("div", { class: "hbar" }, name,
      h("div", { class: "track" }, h("div", { class: `fill ${p ? "has-part" : ""}`, style: { width: `${Math.max(0.5, pct(v - p))}%` } }),
        p ? h("div", { class: "fill part", style: { width: `${pct(p)}%` } }) : null),
      h("span", { class: "val" }, fmt(v), sub ? h("span", { class: "muted" }, " ", sub(it)) : null));
    return row;
  }));
}

// Trend sparkline: the de-emphasis hue for the line, the accent for the current period (last point)
function sparkEl(values, { height = 30 } = {}) {
  const box = h("div", { class: "spark", style: { height: `${height}px` } });
  if (!values.length || values.every((v) => !v)) return box;
  responsive(box, (w) => {
    const max = Math.max(...values), n = values.length, pad = 4;
    const x = (i) => (n === 1 ? w / 2 : pad + (i / (n - 1)) * (w - 2 * pad));
    const y = (v) => height - 4 - (max ? (v / max) * (height - 10) : 0);
    const pts = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
    box.append(s("svg", { width: w, height, viewBox: `0 0 ${w} ${height}`, "aria-hidden": "true" },
      s("path", { class: "spark-area", d: `M${x(0).toFixed(1)},${height}L${pts.join("L")}L${x(n - 1).toFixed(1)},${height}Z` }),
      s("path", { class: "spark-line", d: "M" + pts.join("L") }),
      s("circle", { class: "spark-dot", cx: x(n - 1), cy: y(values[n - 1]), r: 3.5 })));
  });
  return box;
}

function contextChart(container, width, calls, markers) {
  const main = calls.filter((c) => !c.agent_id);
  if (main.length < 2) { container.append(h("div", { class: "empty" }, "Not enough API calls to chart")); return; }
  const m = { l: 46, r: 12, t: 16, b: 24 }, height = 210;
  const iw = width - m.l - m.r, ih = height - m.t - m.b;
  const ctx = main.map((c) => (c.input_tokens || 0) + (c.cache_read_tokens || 0) + (c.cache_write_tokens || 0));
  const ticks = niceTicks(Math.max(...ctx));
  const top = ticks[ticks.length - 1] || 1;
  const x = (i) => (i / (main.length - 1)) * iw, y = (v) => ih - (v / top) * ih;
  const svg = s("svg", { width, height, viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "context window per API call" });
  const g = s("g", { transform: `translate(${m.l},${m.t})` });
  svg.append(g);
  for (const t of ticks) {
    g.append(s("line", { class: t === 0 ? "baseline" : "gridline", x1: 0, x2: iw, y1: Math.round(y(t)) + 0.5, y2: Math.round(y(t)) + 0.5 }));
    g.append(s("text", { class: "chart-label tick-num", x: -8, y: y(t) + 3.5, "text-anchor": "end" }, fmtCompact(t)));
  }
  const idxAt = (ts) => { const i = main.findIndex((c) => c.ts >= ts); return i === -1 ? main.length - 1 : i; };
  (markers || []).filter((mk) => mk.kind === "compact").forEach((mk) => {
    const xi = x(idxAt(mk.ts));
    g.append(s("line", { class: "marker-line", x1: xi, x2: xi, y1: -6, y2: ih }));
    g.append(s("text", { class: "marker-label", x: xi + 3, y: -4 }, "compacted"));
  });
  (markers || []).filter((mk) => mk.kind === "prompt").forEach((mk) => {
    const xi = x(idxAt(mk.ts));
    g.append(s("line", { class: "baseline", x1: xi, x2: xi, y1: ih, y2: ih + 5 }));
  });
  const linePts = ctx.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
  g.append(s("path", { class: "area", d: `M0,${ih}L${linePts.join("L")}L${iw},${ih}Z` }));
  g.append(s("path", { class: "line", d: "M" + linePts.join("L") }));
  const peak = ctx.indexOf(Math.max(...ctx));
  const compactXs = (markers || []).filter((mk) => mk.kind === "compact").map((mk) => x(idxAt(mk.ts)));
  const px = x(peak), crowded = compactXs.some((cx) => Math.abs(cx - px) < 90) || y(ctx[peak]) < 14;
  // beside the peak when a compaction label sits above it, otherwise just above
  g.append(s("text", { class: "chart-label peak-label", x: crowded ? Math.max(px - 8, 70) : Math.min(px, iw - 60), y: crowded ? y(ctx[peak]) + 14 : y(ctx[peak]) - 6,
    "text-anchor": crowded ? "end" : "start" }, `peak ${fmtCompact(ctx[peak])}`));
  g.append(s("text", { class: "chart-label", x: 0, y: ih + 17 }, fmtTime(main[0].ts)));
  g.append(s("text", { class: "chart-label", x: iw, y: ih + 17, "text-anchor": "end" }, fmtTime(main[main.length - 1].ts)));
  g.append(s("text", { class: "chart-label", x: iw / 2, y: ih + 17, "text-anchor": "middle" }, `${main.length} API calls · ticks mark prompts`));
  const cross = s("line", { class: "crosshair", y1: 0, y2: ih, visibility: "hidden" });
  const dot = s("circle", { class: "dot", r: 4, visibility: "hidden" });
  g.append(cross, dot);
  const overlay = s("rect", { class: "hit", x: 0, y: 0, width: iw, height: ih });
  overlay.addEventListener("pointermove", (e) => {
    const r = overlay.getBoundingClientRect();
    const i = Math.max(0, Math.min(main.length - 1, Math.round(((e.clientX - r.left) / r.width) * (main.length - 1))));
    const c = main[i];
    cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
    dot.setAttribute("cx", x(i)); dot.setAttribute("cy", y(ctx[i])); dot.setAttribute("visibility", "visible");
    showTip(e, `${fmtCompact(ctx[i])} context tokens`, `Call ${i + 1} · ${fmtDT(c.ts)} · ${c.model || ""}`,
      `output ${fmtCompact(c.output_tokens)} · cache read ${fmtCompact(c.cache_read_tokens)} · ${fmtCost(c.cost_usd)}`);
  });
  overlay.addEventListener("pointerleave", () => { hideTip(); cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); });
  g.append(overlay);
  container.append(svg);
}

// =====================================================================================
// Router
// =====================================================================================
const routes = [];
function route(pattern, view) { routes.push([pattern, view]); }
function go(hash) { if (location.hash === hash) render(); else location.hash = hash; }
function parseHash() {
  const raw = location.hash.slice(1) || "/";
  const [path, qs] = raw.split("?");
  return { path, params: Object.fromEntries(new URLSearchParams(qs || "")) };
}
function setParams(params) {
  const { path } = parseHash();
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== "")).toString();
  history.replaceState(null, "", `#${path}${qs ? "?" + qs : ""}`);
  lastHash = location.hash;
  const now = parseHash();
  markSidebar(now.path, now.params);
  if (!/^\/(session\/|project$)/.test(path)) setCrumbs(defaultCrumbs(now.path, now.params)); // those pages name themselves
}
let renderSeq = 0;
async function render() {
  const { path, params } = parseHash();
  const app = $("#app");
  const seq = ++renderSeq;
  updateShell(path, params);
  for (const [pattern, view] of routes) {
    const m = path.match(pattern);
    if (!m) continue;
    app.classList.add("loading");
    try {
      const [node] = await Promise.all([view(params, ...m.slice(1).map(decodeURIComponent)), loadGlossary()]);
      if (seq !== renderSeq) return;
      app.replaceChildren(node);
      app.querySelectorAll(".gloss").forEach((el) => glossify(el));
    } catch (err) {
      if (seq !== renderSeq) return;
      app.replaceChildren(h("div", { class: "card empty" }, `Could not load: ${err.message}`));
    } finally {
      if (seq === renderSeq) app.classList.remove("loading");
    }
    hideTip();
    return;
  }
  app.replaceChildren(h("div", { class: "card empty" }, "Not found"));
}
function navKey(path) {
  if (path.startsWith("/session")) return "sessions";
  if (path.startsWith("/project")) return "projects";
  if (path.startsWith("/knowledge")) return "knowledge";
  if (path.startsWith("/status")) return "status";
  if (path.startsWith("/reviews")) return "reviews";
  if (path.startsWith("/sources")) return "sources";
  if (path.startsWith("/glossary")) return "glossary";
  if (path.startsWith("/map")) return "map";
  if (path.startsWith("/appearance")) return "appearance";
  if (path.startsWith("/search")) return "search";
  if (path === "/" || path === "") return "overview";
  return "";
}

let projectsCache = null;
async function projectOptions(selected) {
  projectsCache ||= await api("/api/projects");
  return [h("option", { value: "" }, "All projects"),
    ...projectsCache.map((p) => h("option", { value: p.project_path, selected: p.project_path === selected }, p.label))];
}
function segControl(options, value, onChange) {
  return h("div", { class: "seg", role: "group" }, options.map(([v, label]) =>
    h("button", { type: "button", class: v === value ? "on" : "", "aria-pressed": String(v === value), onclick: () => onChange(v) }, label)));
}

// Cards/List switch of the list pages; each page remembers its layout in this browser
const viewModes = {};
function viewMode(page, fallback) {
  if (!(page in viewModes)) {
    let saved = null;
    try { saved = localStorage.getItem(`chronicle.view.${page}`); } catch { /* storage blocked: use the default */ }
    viewModes[page] = saved === "cards" || saved === "list" ? saved : fallback;
  }
  return viewModes[page];
}
function viewToggle(page, mode) {
  const icon = (rects) => s("svg", { viewBox: "0 0 16 16", "aria-hidden": "true" },
    rects.map(([x, y, w, ht]) => s("rect", { x, y, width: w, height: ht, rx: 1.2 })));
  const seg = segControl([
    ["cards", [icon([[1.5, 1.5, 5.5, 5.5], [9, 1.5, 5.5, 5.5], [1.5, 9, 5.5, 5.5], [9, 9, 5.5, 5.5]]), "Cards"]],
    ["list", [icon([[1.5, 2.2, 13, 1.8], [1.5, 7.1, 13, 1.8], [1.5, 12, 13, 1.8]]), "List"]],
  ], mode, (v) => {
    if (v === mode) return;
    viewModes[page] = v;
    try { localStorage.setItem(`chronicle.view.${page}`, v); } catch { /* remembered for this tab only */ }
    render();
  });
  seg.classList.add("view-toggle");
  seg.setAttribute("aria-label", "Layout");
  return seg;
}

// A table sorted in the browser. cols: { key, label, num, desc, value(item) } (no value: not sortable; desc: sort
// descending on first click); row(item) returns the item's <tr> (or [] to skip it); group splits the default order.
function localTable(items, cols, row, { sort = null, order = "asc", group = null, empty = "Nothing matches", cls = "" } = {}) {
  const state = { sort, order };
  const thead = h("thead"), tbody = h("tbody");
  function draw() {
    const col = cols.find((c) => c.key === state.sort && c.value);
    const dir = state.order === "asc" ? 1 : -1;
    const list = !col ? items : [...items].sort((a, b) => {
      const va = col.value(a), vb = col.value(b);
      if (va == null || vb == null || va === "" || vb === "") return (va == null || va === "") - (vb == null || vb === ""); // blanks last
      return (typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb))) * dir;
    });
    thead.replaceChildren(h("tr", null, cols.map((c) => {
      const th = h("th", { class: `${c.value ? "sortable" : ""} ${c.num ? "num" : ""}`, "aria-sort": c.key === state.sort ? (state.order === "asc" ? "ascending" : "descending") : null },
        c.label, c.key === state.sort ? h("span", { class: "arrow" }, state.order === "asc" ? " ↑" : " ↓") : null);
      if (c.value) th.addEventListener("click", () => {
        state.order = state.sort === c.key ? (state.order === "asc" ? "desc" : "asc") : (c.desc ? "desc" : "asc");
        state.sort = c.key;
        draw();
      });
      return th;
    })));
    const rows = [];
    let current;
    for (const item of list) {
      const tr = row(item);
      if (Array.isArray(tr) && !tr.length) continue;
      if (group && (!state.sort || state.sort === group.key)) {
        const g = group.of(item);
        if (g !== current) rows.push(h("tr", { class: "group-row", id: group.id ? group.id(g) : null }, h("th", { colspan: cols.length }, (current = g))));
      }
      rows.push(tr);
    }
    tbody.replaceChildren(...(rows.length ? rows : [h("tr", null, h("td", { colspan: cols.length, class: "empty" }, empty))]));
  }
  draw();
  return h("div", { class: "table-wrap" }, h("table", { class: `data list-table ${cls}` }, thead, tbody));
}

// A table row that opens a detail row under it (click, Enter or Space)
function expandable(tr, colspan, detail, { indent = 0 } = {}) {
  let open = null;
  const toggle = () => {
    if (open) { open.remove(); open = null; }
    else {
      open = h("tr", { class: "detail-row" }, indent ? h("td", { colspan: indent }) : null, h("td", { colspan: colspan - indent }, detail()));
      tr.after(open);
      open.querySelectorAll(".gloss").forEach((el) => glossify(el));
    }
    tr.classList.toggle("open", !!open);
    tr.setAttribute("aria-expanded", String(!!open));
  };
  tr.classList.add("row-link");
  tr.tabIndex = 0;
  tr.setAttribute("aria-expanded", "false");
  tr.addEventListener("click", (e) => { if (!e.target.closest("a, button, .gterm")) toggle(); });
  tr.addEventListener("keydown", (e) => { if ((e.key === "Enter" || e.key === " ") && e.target === tr) { e.preventDefault(); toggle(); } });
  tr.closeDetail = () => { if (open) toggle(); };
  return tr;
}
function plainText(src) { // one-line excerpt of markdown
  return String(src || "").replace(/```[\s\S]*?```/g, " ").replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/^\s{0,3}(?:#{1,6}|>|[-*+]|\d+\.)\s+/gm, "").replace(/\*\*|__|`/g, "").replace(/\s+/g, " ").trim();
}
function tile(label, value, { delta, spark, title, iconName } = {}) {
  return h("div", { class: "tile", title },
    h("div", { class: "label" }, iconName ? icon(iconName) : null, label),
    h("div", { class: "value" }, value),
    h("div", { class: "foot" }, delta != null ? h("span", { class: "delta" }, delta) : h("span")),
    spark || null);
}
function fact(label, value) { return h("div", { class: "fact" }, h("b", null, value), h("span", null, label)); }
function fmtRate(v) { return v >= 100 ? fmtCompact(v) : v >= 10 ? v.toFixed(0) : v >= 1 ? v.toFixed(1) : v ? v.toFixed(2) : "0"; }
function pctText(part, whole) { return whole ? `${((part / whole) * 100).toFixed(part / whole < 0.1 ? 1 : 0)}%` : "–"; }
function cardHead(title, { iconName, hint, tools } = {}) {
  return h("div", { class: "card-head" },
    h("div", { class: "card-title" }, iconName ? icon(iconName) : null, h("h2", null, title)),
    hint || tools ? h("div", { class: "tools" }, hint ? (typeof hint === "string" ? h("span", { class: "hint" }, hint) : hint) : null, tools || null) : null);
}
function legendKey(items) { // [[swatch class, label]]; identity never rides on color alone
  return h("span", { class: "mini-legend" }, items.map(([cls, label]) => h("span", null, h("i", { class: `sw ${cls}` }), label)));
}
function deltaText(cur, prev, days) {
  if (prev == null || !prev) return cur ? `new vs prior ${days}d` : null;
  const pct = ((cur - prev) / prev) * 100;
  if (!isFinite(pct)) return null;
  return `${pct >= 0 ? "▲" : "▼"} ${Math.abs(pct).toFixed(0)}% vs prior ${days}d`;
}

// =====================================================================================
// Overview
// =====================================================================================
route(/^\/?$/, async (params) => {
  const days = params.days || "90", project = params.project || "", agent = params.agent || "";
  const metric = params.metric || "active_s";
  const data = await api("/api/overview", { days, project, agent });
  const t = data.totals, p = data.previous || {};
  const update = (patch) => { setParams({ days, project, agent, metric, ...patch }); render(); };
  // fill missing days so the time axis is honest
  const daily = fillDays(data.daily, days === "all" ? null : +days);
  // a delta only means something when recording covered the whole prior period; otherwise show a daily rate
  const DAY = 86400000, firstAt = t.first_at ? new Date(t.first_at).getTime() : Date.now();
  const spanDays = Math.max(1, Math.min(days === "all" ? Infinity : +days, Math.ceil((Date.now() - firstAt) / DAY)));
  const fullPrior = days !== "all" && firstAt <= Date.now() - 2 * +days * DAY;
  const second = (cur, prev, f) => (fullPrior ? deltaText(cur, prev, days) : `${f(cur / spanDays)} a day`);
  const sparkOf = (key) => sparkEl(bucket(daily.map((x) => x[key] || 0), 12));
  const activeDays = daily.filter((x) => (x.active_s || 0) > 0 || x.sessions).length;
  let longest = 0, run = 0;
  for (const x of daily) { run = (x.active_s || 0) > 0 || x.sessions ? run + 1 : 0; longest = Math.max(longest, run); }
  const periodName = days === "all" ? "all time" : `the last ${days} days`;
  const hero = h("div", { class: "tile hero", title: "Active time: the sum of gaps under 15 minutes between events" },
    h("div", { class: "label" }, icon("clock"), "Active time"),
    h("div", { class: "value" }, fmtHours(t.active_s)),
    h("div", { class: "hero-sub" }, `across ${fmtNum(t.sessions)} sessions in ${fmtNum(t.projects)} projects, ${periodName}`),
    h("div", { class: "hero-facts" },
      fact("active days", `${fmtNum(activeDays)} of ${fmtNum(Math.min(daily.length, spanDays))}`),
      fact("per active day", activeDays ? fmtDur(t.active_s / activeDays) : "–"),
      fact("longest run", `${longest} day${longest === 1 ? "" : "s"}`)),
    sparkEl(bucket(daily.map((x) => x.active_s || 0), 24), { height: 46 }));
  const tiles = h("div", { class: "kpis" }, hero,
    tile("Sessions", fmtNum(t.sessions), { iconName: "sessions", delta: second(t.sessions, p.sessions, fmtRate), spark: sparkOf("sessions") }),
    tile("Prompts", fmtNum(t.prompts), { iconName: "prompts", delta: second(t.prompts, p.prompts, fmtRate), spark: sparkOf("prompts") }),
    tile("Tool calls", fmtCompact(t.tool_calls), { iconName: "zap", delta: `${fmtNum(t.tool_errors)} failed · ${pctText(t.tool_errors, t.tool_calls)}`, spark: sparkOf("tool_calls") }),
    tile("Lines changed", `+${fmtCompact(t.lines_added)}`, { iconName: "diff", delta: `−${fmtCompact(t.lines_removed)} removed`, spark: sparkOf("lines_added") }),
    tile("Tokens", fmtCompact(t.tokens), { iconName: "tokens", delta: second(t.tokens, p.tokens, fmtCompact), spark: sparkOf("tokens"), title: "Input + output + cache read + cache write" }),
    tile("Est. API cost", fmtCost(t.cost), { iconName: "cost", delta: second(t.cost, p.cost, fmtCost), spark: sparkOf("cost"), title: "API list-price equivalent; subscriptions are billed differently. Newer GPT models are estimated at GPT-5 rates." }),
    tile("Knowledge", fmtNum(t.knowledge), { iconName: "sparkles", delta: `${fmtNum(t.analyzed)} sessions analyzed` }),
    tile("Projects", fmtNum(t.projects), { iconName: "projects", delta: data.projects[0] ? `most time: ${data.projects[0].label}` : null }));
  const metrics = {
    sessions: ["Sessions", (x) => x.sessions, fmtNum],
    active_s: ["Active time", (x) => x.active_s, fmtHours, 3600],
    tokens: ["Tokens", (x) => x.tokens, fmtCompact],
    cost: ["Est. cost", (x) => x.cost, fmtCost],
  };
  const [mLabel, mValue, mFmt, mUnit] = metrics[metric] || metrics.active_s;
  const dailyCard = chartCard(`Daily ${mLabel.toLowerCase()}`, days === "all" ? "All time" : `Last ${days} days`,
    (el, w) => columnChart(el, w, daily, { value: (x) => mValue(x) || 0, fmt: mFmt, label: (x) => wdFmt.format(new Date(x.date + "T12:00:00")), avg: daily.length >= 21 ? 7 : 0, name: `Daily ${mLabel.toLowerCase()}`, height: 320, unit: mUnit || 1 }),
    () => ({ columns: ["Date", mLabel], num: [false, true], rows: daily.filter((x) => mValue(x)).map((x) => [x.date, mFmt(mValue(x))]) }),
    [segControl(Object.entries(metrics).map(([k, v]) => [k, v[0]]), metric, (v) => update({ metric: v }))], "status");
  const outcomesCard = h("section", { class: "card" }, cardHead("Outcomes", { iconName: "completed", hint: "from session analysis" }),
    outcomeBreakdown(data.outcomes),
    data.work_types.length ? [h("div", { class: "subhead" }, "Work types"),
      hbars(data.work_types.slice(0, 6).map(([w, n]) => ({ w, n })), { label: (x) => x.w, value: (x) => x.n, fmt: fmtNum })] : null);
  const cal = chartCard("Activity calendar", "Active time per day · click a day to see its sessions",
    (el, w) => calendarHeatmap(el, w, data.calendar),
    () => ({ columns: ["Date", "Sessions", "Prompts", "Active"], num: [false, true, true, true], rows: data.calendar.map((r) => [r.date, r.sessions, r.prompts || 0, fmtDur(r.active_s)]) }),
    [], "calendar");
  const hours = chartCard("When you work", "Prompts by weekday and hour, local time",
    (el, w) => hourGrid(el, w, data.hours),
    () => ({ columns: ["Weekday", "Hour", "Prompts"], num: [false, true, true], rows: data.hours.map((r) => [["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][r.dow], r.hour, r.n]) }),
    [], "clock");
  const projCard = h("section", { class: "card" }, cardHead("Projects", { iconName: "projects", hint: "by active time · sessions" }),
    hbars(data.projects, { label: (x) => x.label, value: (x) => x.active_s || 0, fmt: fmtDur, href: (x) => `#/project?path=${encodeURIComponent(x.project_path)}`, sub: (x) => `· ${x.sessions}` }));
  const toolCard = h("section", { class: "card" }, cardHead("Tools", { iconName: "zap", hint: legendKey([["accent", "calls"], ["critical", "failed"]]) }),
    hbars(groupMcp(data.tools).slice(0, 12), { label: (x) => x.name, value: (x) => x.n, fmt: fmtCompact, part: (x) => x.errors || 0, sub: (x) => (x.errors ? `(${fmtCompact(x.errors)})` : "") }));
  const modelCard = h("section", { class: "card" }, cardHead("Models", { iconName: "system", hint: "est. API cost · tokens" }),
    hbars(data.models, { label: (x) => x.model, value: (x) => x.cost || 0, fmt: fmtCost, sub: (x) => `· ${fmtCompact(x.tokens)}` }),
    data.agents && data.agents.length > 1 && !agent ? [h("div", { class: "subhead" }, "Agents"),
      hbars(data.agents, { label: (x) => agentName(x.agent), value: (x) => x.active_s || 0, fmt: fmtDur, href: (x) => `#/?agent=${x.agent}`, sub: (x) => `· ${x.sessions} sessions` })] : null);
  const recent = h("section", { class: "card" }, cardHead("Recent sessions", { iconName: "sessions", tools: h("a", { href: "#/sessions", class: "hint link-arrow" }, "All sessions", icon("arrow")) }),
    sessionList(data.recent));
  const know = h("section", { class: "card" }, cardHead("Latest knowledge", { iconName: "knowledge", tools: h("a", { href: "#/knowledge", class: "hint link-arrow" }, "Browse", icon("arrow")) }),
    knowledgeList(data.knowledge.slice(0, 8)));
  const since = t.first_at ? `since ${fmtDateY(t.first_at)}` : "";
  return h("div", null,
    h("div", { class: "page-head" }, h("div", null, h("h1", null, "Home"),
      h("div", { class: "sub" }, `${fmtNum(t.sessions)} sessions across ${fmtNum(t.projects)} projects ${since}`)),
      h("div", { class: "head-actions" },
        segControl([["7", "7d"], ["30", "30d"], ["90", "90d"], ["180", "180d"], ["all", "All"]], days, (v) => update({ days: v })),
        segControl([["", "All agents"], ...Object.keys(AGENTS).filter((a) => a === agent || (data.agents || []).some((x) => x.agent === a))
          .map((a) => [a, agentName(a)])], agent, (v) => update({ agent: v })),
        h("select", { "aria-label": "Project", onchange: (e) => update({ project: e.target.value }) }, await projectOptions(project)))),
    tiles,
    h("div", { class: "grid cols-main section-gap" }, dailyCard, outcomesCard),
    h("div", { class: "grid cols-2 section-gap" }, cal, hours),
    h("div", { class: "grid cols-3 section-gap" }, projCard, toolCard, modelCard),
    h("div", { class: "grid cols-2 section-gap" }, recent, know));
});

function groupMcp(tools) {
  const out = {};
  for (const t of tools) {
    const m = t.name.match(/^mcp__(.+?)__/);
    const name = m ? `MCP: ${m[1].replace(/^claude_ai_/, "")}` : t.name;
    const g = (out[name] ||= { name, n: 0, errors: 0 });
    g.n += t.n;
    g.errors += t.errors || 0;
  }
  return Object.values(out).sort((a, b) => b.n - a.n);
}

function fillDays(daily, days) {
  if (!daily.length) return [];
  const map = Object.fromEntries(daily.map((x) => [x.date, x]));
  const end = new Date(); end.setHours(12, 0, 0, 0);
  const start = days ? new Date(end.getTime() - (days - 1) * 86400000) : new Date(daily[0].date + "T12:00:00");
  const out = [];
  for (let t = new Date(start); t <= end; t.setDate(t.getDate() + 1)) {
    const key = localDate(t);
    out.push(map[key] || { date: key, sessions: 0, prompts: 0, active_s: 0, tokens: 0, cost: 0, tool_calls: 0, lines_added: 0 });
  }
  return out;
}
function bucket(values, n) {
  if (values.length <= n) return values;
  const size = values.length / n, out = [];
  for (let i = 0; i < n; i++) out.push(values.slice(Math.floor(i * size), Math.floor((i + 1) * size)).reduce((a, b) => a + b, 0));
  return out;
}

function outcomeOf(x) { // -> [status class, icon, label] for a session row
  if (x.source === "history") return ["", "history", "history"];
  if (x.outcome && OUTCOME[x.outcome]) return [OUTCOME[x.outcome][0], x.outcome, OUTCOME[x.outcome][1]];
  return [x.analysis_status === "error" ? "critical" : "", STATUS_ICON[x.analysis_status] || "dot", STATUS_LABEL[x.analysis_status] || "–"];
}
function sessionList(items) {
  if (!items.length) return h("div", { class: "empty" }, "No sessions yet");
  return h("div", { class: "session-list" }, items.map((x) => {
    const [cls, ic, label] = outcomeOf(x);
    return h("a", { class: "session-item", href: `#/session/${x.id}` },
      h("span", { class: `status-icon ${cls}`, title: label }, icon(ic), h("span", { class: "sr-only" }, label)),
      h("div", { style: { minWidth: 0 } }, h("div", { class: "t" }, x.title || "(untitled)", agentTag(x.agent)),
        h("div", { class: "m" }, `${x.project_name || "–"} · ${ago(x.started_at)} · ${fmtDur(x.active_s)} active · ${x.n_prompts} prompt${x.n_prompts === 1 ? "" : "s"}`)),
      h("div", { class: "r" }, fmtCost(x.est_cost_usd)));
  }));
}
function knowledgeList(items) {
  if (!items.length) return h("div", { class: "empty" }, "No analyzed knowledge yet. Sessions are analyzed automatically once idle.");
  return h("div", { class: "session-list" }, items.map((k) => h("a", { class: "session-item", href: `#/knowledge?q=${encodeURIComponent(k.title.slice(0, 60))}` },
    h("span", { class: "kind-icon", title: kindLabel(k.kind) }, icon(KIND[k.kind] ? k.kind : "dot")),
    h("div", { style: { minWidth: 0 } }, h("div", { class: "t" }, k.title),
      h("div", { class: "m" }, [kindLabel(k.kind), k.scope === "global" ? "global" : k.project_name, ago(k.created_at)].filter(Boolean).join(" · "))),
    h("div", { class: "r" }, confidenceMeter(k.confidence)))));
}
const OUTCOME_ORDER = ["completed", "partial", "exploratory", "blocked", "abandoned", "unclear", "not analyzed"];
function outcomeBreakdown(outcomes) {
  const total = outcomes.reduce((a, o) => a + o.n, 0);
  if (!total) return h("div", { class: "empty" }, "No sessions yet");
  const rank = (o) => { const i = OUTCOME_ORDER.indexOf(o.outcome); return i < 0 ? 99 : i; };
  const items = [...outcomes].sort((a, b) => rank(a) - rank(b));
  const cls = (o) => (OUTCOME[o] ? OUTCOME[o][0] || "neutral" : "none");
  const label = (o) => (OUTCOME[o] ? OUTCOME[o][1] : o === "not analyzed" ? "Not analyzed" : o);
  const href = (o) => `#/sessions?outcome=${o === "not analyzed" ? "none" : o}`;
  const pct = (n) => `${Math.round((n / total) * 100)}%`;
  return h("div", { class: "outcomes" },
    h("div", { class: "stackbar", role: "img", "aria-label": items.map((o) => `${label(o.outcome)}: ${o.n}`).join(", ") },
      items.map((o) => {
        const seg = h("a", { class: `seg s-${cls(o.outcome)}`, href: href(o.outcome), style: { flexGrow: String(o.n) }, "aria-label": `${label(o.outcome)}: ${o.n}` });
        hoverable(seg, () => [`${fmtNum(o.n)} sessions · ${pct(o.n)}`, label(o.outcome)]);
        return seg;
      })),
    h("div", { class: "legend-list" }, items.map((o) => h("a", { class: `legend-row s-${cls(o.outcome)}`, href: href(o.outcome) },
      icon(OUTCOME[o.outcome] ? o.outcome : o.outcome === "not analyzed" ? "queued" : "dot"),
      h("span", { class: "lname" }, label(o.outcome)), h("span", { class: "lval" }, fmtNum(o.n)), h("span", { class: "lpct" }, pct(o.n))))));
}

// =====================================================================================
// Sessions list
// =====================================================================================
route(/^\/sessions$/, async (params) => {
  const state = { q: params.q || "", project: params.project || "", outcome: params.outcome || "", status: params.status || "",
    days: params.days || "", sort: params.sort || "started_at", order: params.order || "desc", day: params.day || "",
    agent: params.agent || "" };
  const mode = viewMode("sessions", "list");
  let offset = 0, scale = null, total = 0;
  // ---- selection (list view): pick sessions, then analyze them in one go
  const picked = new Set(), boxes = new Map(); // id -> checkbox of a loaded row
  let lastPick = null;
  const selBar = h("div", { class: "sel-bar", hidden: true });
  const headBox = h("input", { type: "checkbox", "aria-label": "Select all loaded sessions", onclick: (e) => {
    for (const [id, b] of boxes) if (!b.disabled) { b.checked = e.target.checked; b.closest("tr").classList.toggle("picked", b.checked); e.target.checked ? picked.add(id) : picked.delete(id); }
    drawSel();
  } });
  const setPick = (id, on) => {
    on ? picked.add(id) : picked.delete(id);
    const b = boxes.get(id);
    if (b) { b.checked = on; b.closest("tr")?.classList.toggle("picked", on); }
  };
  const pick = (x, tr) => {
    const b = h("input", { type: "checkbox", "aria-label": `Select ${x.title || "session"}`, checked: picked.has(x.id),
      onclick: (e) => {
        e.stopPropagation();
        if (e.shiftKey && lastPick) { // shift-click: the range from the last box clicked
          const ids = [...boxes.keys()], a = ids.indexOf(lastPick), z = ids.indexOf(x.id);
          if (a >= 0 && z >= 0) ids.slice(Math.min(a, z), Math.max(a, z) + 1).forEach((id) => { if (!boxes.get(id).disabled) setPick(id, e.target.checked); });
        }
        setPick(x.id, e.target.checked);
        lastPick = x.id;
        drawSel();
      } });
    tr.classList.toggle("picked", picked.has(x.id));
    boxes.set(x.id, b);
    return b;
  };
  async function pickAllMatching() {
    const r = await api("/api/sessions", { ...state, ids_only: 1 });
    r.ids.forEach((id) => setPick(id, true));
    drawSel();
  }
  function drawSel() {
    const n = picked.size;
    const loaded = [...boxes.values()].filter((b) => !b.disabled);
    headBox.checked = n > 0 && loaded.every((b) => b.checked);
    headBox.indeterminate = n > 0 && !headBox.checked;
    selBar.hidden = !n;
    if (!n) return;
    const analyze = h("button", { class: "btn primary small", type: "button", onclick: async () => {
      if (n > 25 && !confirm(`Analyze ${n} sessions now? Each one is a Claude call on your Claude Code login.`)) return;
      analyze.disabled = true; analyze.textContent = "Starting…";
      const r = await post("/api/sessions/analyze", { ids: [...picked] });
      if (!r.started) { toast(r.error || "Could not start"); analyze.disabled = false; drawSel(); return; }
      toast(`Analyzing ${fmtNum(r.count)} session${r.count === 1 ? "" : "s"}; the status bar shows progress` +
        (r.dropped ? ` (${fmtNum(r.dropped)} history-only left out: nothing to analyze)` : ""), 7000);
      [...picked].forEach((id) => setPick(id, false));
      drawSel();
      watchJob("analyze:selection");
    } }, `Analyze ${fmtNum(n)}`);
    selBar.replaceChildren(...[ // replaceChildren would print a null as the text "null"
      h("span", { class: "sel-count" }, `${fmtNum(n)} selected`),
      total > n ? h("button", { class: "text-link", type: "button", onclick: pickAllMatching }, `Select all ${fmtNum(total)} matching`) : null,
      h("span", { class: "sel-spacer" }),
      h("button", { class: "btn small", type: "button", onclick: () => { [...picked].forEach((id) => setPick(id, false)); drawSel(); } }, "Clear"),
      exportMenu(() => [...picked], { small: true, up: true }),
      analyze].filter(Boolean));
  }
  const tbody = h("tbody");
  const cards = h("div", { class: "scard-grid" });
  const countEl = h("span", { class: "sub" });
  const moreBtn = h("button", { class: "btn", type: "button", onclick: () => load(true) }, "Load more");
  async function load(more) {
    if (!more) { offset = 0; tbody.replaceChildren(); cards.replaceChildren(); boxes.clear(); picked.clear(); lastPick = null; drawSel(); }
    const q = { ...state, limit: 60, offset };
    if (state.day) {
      const start = new Date(state.day + "T00:00:00");
      q.days = "";
      q.since = start.toISOString();
      q.until = new Date(start.getTime() + 86400000).toISOString();
    }
    const data = await api("/api/sessions", q);
    if (!more) scale = { active: Math.max(1, ...data.items.map((x) => x.active_s || 0)), tokens: Math.max(1, ...data.items.map((x) => x.tokens || 0)),
      cost: Math.max(0.01, ...data.items.map((x) => x.est_cost_usd || 0)) }; // bars compare rows within the first page
    data.items.forEach((x) => (mode === "list" ? tbody.append(sessionRow(x, scale, pick)) : cards.append(sessionCard(x))));
    offset += data.items.length;
    total = data.total;
    drawSel();
    countEl.textContent = state.day ? `${fmtNum(data.total)} sessions on ${fmtDateY(state.day + "T12:00:00")}` : `${fmtNum(data.total)} sessions`;
    moreBtn.hidden = offset >= data.total;
    if (!data.total) {
      if (mode === "list") tbody.append(h("tr", null, h("td", { colspan: 10, class: "empty" }, "No sessions match")));
      else cards.append(h("div", { class: "card empty" }, "No sessions match"));
    }
  }
  const sorts = [["started_at:desc", "Newest first"], ["started_at:asc", "Oldest first"], ["active_s:desc", "Most active time"],
    ["tokens:desc", "Most tokens"], ["est_cost_usd:desc", "Highest est. cost"], ["n_tool_calls:desc", "Most tool calls"],
    ["n_prompts:desc", "Most prompts"], ["title:asc", "Title A–Z"]];
  const sortNow = `${state.sort}:${state.order}`;
  const sortSel = mode === "cards" ? h("select", { "aria-label": "Sort sessions", onchange: (e) => { [state.sort, state.order] = e.target.value.split(":"); refresh(); } },
    (sorts.some(([v]) => v === sortNow) ? sorts : [[sortNow, "Custom order"], ...sorts]).map(([v, l]) => h("option", { value: v, selected: v === sortNow }, l))) : null;
  const refresh = () => { setParams(state); load(false); };
  let debounce;
  const search = h("input", { class: "input", type: "search", placeholder: "Search titles, summaries and transcripts…", value: state.q, style: { minWidth: "300px" },
    oninput: (e) => { clearTimeout(debounce); debounce = setTimeout(() => { state.q = e.target.value; refresh(); }, 300); } });
  const sel = (key, opts) => h("select", { onchange: (e) => { state[key] = e.target.value; refresh(); } },
    opts.map(([v, l]) => h("option", { value: v, selected: state[key] === v }, l)));
  const cols = [["started_at", "Started"], ["title", "Session"], ["project_name", "Project"], ["n_prompts", "Prompts", 1], ["n_tool_calls", "Tools", 1],
    ["active_s", "Active", 1], ["tokens", "Tokens", 1], ["est_cost_usd", "Est. cost", 1], [null, "Outcome"]];
  const thead = h("thead", null, h("tr", null, h("th", { class: "pick" }, headBox), cols.map(([key, label, num]) => {
    const th = h("th", { class: `${key ? "sortable" : ""} ${num ? "num" : ""}` }, label, key === state.sort ? h("span", { class: "arrow" }, state.order === "asc" ? " ↑" : " ↓") : null);
    if (key) th.addEventListener("click", () => { state.order = state.sort === key && state.order === "desc" ? "asc" : "desc"; state.sort = key; setParams(state); render(); });
    return th;
  })));
  await load(false);
  return h("div", null,
    h("div", { class: "page-head" }, h("div", null, h("h1", null, "Sessions"), countEl), viewToggle("sessions", mode)),
    h("div", { class: "filters" }, search,
      h("select", { onchange: (e) => { state.project = e.target.value; refresh(); } }, await projectOptions(state.project)),
      sel("outcome", [["", "Any outcome"], ["completed", "Completed"], ["partial", "Partial"], ["blocked", "Blocked"], ["abandoned", "Abandoned"], ["exploratory", "Exploratory"], ["unclear", "Unclear"], ["none", "Not analyzed"]]),
      sel("status", [["", "Any status"], ["done", "Analyzed"], ["pending", "Queued"], ["stale", "Needs re-analysis"], ["error", "Failed"], ["skipped", "Skipped"]]),
      sel("agent", [["", "All agents"], ...Object.entries(AGENTS)]),
      sel("days", [["", "All time"], ["7", "Last 7 days"], ["30", "Last 30 days"], ["90", "Last 90 days"]]),
      sortSel,
      state.day ? h("button", { class: "chip on", type: "button", title: "Clear the day filter", onclick: () => { state.day = ""; refresh(); } }, icon("calendar"), state.day, icon("x")) : null),
    mode === "list" ? h("section", { class: "card flush" }, h("div", { class: "table-wrap" }, h("table", { class: "data" }, thead, tbody))) : cards,
    h("div", { class: "load-more" }, moreBtn),
    mode === "list" ? selBar : null);
});

function sessionCard(x) {
  const [cls] = outcomeOf(x);
  const stat = (ic, value, label, title) => h("span", { title }, icon(ic), h("b", null, value), label ? ` ${label}` : null);
  return h("a", { class: `card scard o-${cls || "neutral"}`, href: `#/session/${x.id}` },
    h("div", { class: "scard-head" },
      h("div", { class: "t" }, x.title || "(untitled)", agentTag(x.agent),
        x.source === "codex-import" ? h("span", { class: "agent-tag", title: "Claude Code deleted this transcript; recovered from Codex's copy" }, "recovered") : null),
      outcomeBadge(x.outcome, x.analysis_status, x.source)),
    h("div", { class: "m" }, `${x.project_name || "–"} · ${fmtDT(x.started_at)} · ${fmtDur(x.active_s)} active`),
    x.summary ? h("div", { class: "s" }, x.summary) : null,
    x.tags?.length ? h("div", { class: "ktags" }, x.tags.slice(0, 5).map((t) => h("span", { class: "tag" }, t))) : null,
    h("div", { class: "scard-stats" },
      stat("prompts", fmtNum(x.n_prompts), x.n_prompts === 1 ? "prompt" : "prompts"),
      stat("zap", fmtNum(x.n_tool_calls), x.n_tool_errors ? `(${fmtNum(x.n_tool_errors)} failed)` : "calls", "Tool calls"),
      stat("tokens", fmtCompact(x.tokens), null, "Tokens"),
      stat("cost", fmtCost(x.est_cost_usd).replace(/^\$/, ""), null, "Estimated API cost")));
}

function barCell(text, v, max) { // a number with a small magnitude bar under it
  return h("td", { class: "num" }, text, max ? h("div", { class: "cellbar", "aria-hidden": "true" }, h("i", { style: { width: `${Math.min(100, ((v || 0) / max) * 100)}%` } })) : null);
}
// ------------------------------------------------------------------ export: one session or a selection, as files
const RAW_SOURCES = ["transcript", "codex-import", "codex-cloud"]; // sessions with an original transcript of their own
const EXPORT_FORMATS = [["md", "Markdown", "Summary, knowledge and the conversation"], ["json", "JSON", "The full record, every event included"],
  ["raw", "Original transcript", "The agent's own file, as archived (not redacted)"]];
async function downloadExport(ids, fmt) {
  const qs = new URLSearchParams({ ids: ids.join(","), format: fmt }).toString();
  let r;
  try { r = await api(`/api/export?${qs}&check=1`); } catch (e) { toast(e.message, 7000); return; }
  const a = h("a", { href: `/api/export?${qs}`, download: "" });
  document.body.append(a); a.click(); a.remove();
  toast(r.count === 1 ? "Exporting the session…" : `Exporting ${fmtNum(r.count)} sessions as a .zip…` +
    (r.without_original ? ` ${fmtNum(r.without_original)} without an original transcript are listed in its index.md.` : ""), 6000);
}
function exportMenu(getIds, { raw = true, small = false, up = false } = {}) {
  const menu = h("details", { class: `menu${up ? " up" : ""}` },
    h("summary", { class: `btn${small ? " small" : ""}`, title: "Download as files" }, icon("download"), "Export"),
    h("div", { class: "menu-list", role: "menu" }, EXPORT_FORMATS.map(([fmt, label, hint]) => h("button", { type: "button", role: "menuitem",
      disabled: fmt === "raw" && !raw, title: fmt === "raw" && !raw ? "claude.ai chats share one export file; prompt-history sessions have none" : "",
      onclick: () => { menu.open = false; downloadExport(getIds(), fmt); } }, h("b", null, label), h("span", null, hint)))));
  return menu;
}
document.addEventListener("mousedown", (e) => { document.querySelectorAll("details.menu[open]").forEach((d) => { if (!d.contains(e.target)) d.open = false; }); });

function sessionRow(x, scale = null, pick = null) {
  const tr = h("tr", { class: "row-link", onclick: (e) => { if (!e.target.closest("a, .pick")) go(`#/session/${x.id}`); } },
    pick ? h("td", { class: "pick" }) : null,
    h("td", { class: "nowrap" }, h("div", null, fmtDT(x.started_at)), h("div", { class: "muted small" }, ago(x.started_at))),
    h("td", { class: "title-cell" }, h("div", { class: "t" }, x.title || "(untitled)", agentTag(x.agent),
      x.source === "codex-import" ? h("span", { class: "agent-tag", title: "Claude Code deleted this transcript; recovered from Codex's copy" }, "recovered") : null),
      x.summary ? h("div", { class: "s" }, x.summary) : null,
      x.tags?.length ? h("div", null, x.tags.slice(0, 6).map((t) => h("span", { class: "tag" }, t))) : null),
    h("td", null, h("a", { class: "proj", href: `#/project?path=${encodeURIComponent(x.project_path || "")}` }, x.project_name || "–")),
    h("td", { class: "num" }, fmtNum(x.n_prompts)),
    h("td", { class: "num" }, fmtNum(x.n_tool_calls), x.n_tool_errors ? h("div", { class: "muted" }, `${x.n_tool_errors} failed`) : null),
    barCell(fmtDur(x.active_s), x.active_s, scale?.active),
    barCell(fmtCompact(x.tokens), x.tokens, scale?.tokens),
    barCell(fmtCost(x.est_cost_usd), x.est_cost_usd, scale?.cost),
    h("td", null, outcomeBadge(x.outcome, x.analysis_status, x.source)));
  if (pick) tr.firstChild.append(pick(x, tr));
  return tr;
}

// =====================================================================================
// Session detail
// =====================================================================================
route(/^\/session\/([\w-]+)$/, async (params, id) => {
  const token = renderSeq;
  const sx = await api(`/api/sessions/${id}`);
  const analyzing = h("button", { class: "btn primary", type: "button", onclick: async () => {
    analyzing.disabled = true;
    analyzing.textContent = "Analyzing…";
    const r = await post(`/api/sessions/${sx.id}/analyze`);
    toast(r.started ? "Analysis started (via headless Claude Code). This page refreshes when it finishes." : "Analysis already running");
    watchJob(`analyze:${sx.id}`);
  } }, sx.analysis_status === "done" ? "Re-analyze" : "Analyze now");
  if (sx.source === "history") analyzing.hidden = true;
  const head = h("div", { class: "session-head" },
    h("div", { style: { minWidth: 0, flex: "1 1 320px" } },
      h("h1", null, sx.title || "(untitled session)"),
      h("div", { class: "meta" },
        h("span", null, "Project ", h("a", { href: `#/project?path=${encodeURIComponent(sx.project_path || "")}` }, h("b", null, sx.project_name || "–"))),
        h("span", null, `${fmtDT(sx.started_at)} → ${fmtDT(sx.ended_at)}`),
        h("span", null, h("b", null, fmtDur(sx.active_s)), " active · ", fmtDur(sx.duration_s), " wall"),
        sx.git_branch ? h("span", null, "branch ", h("code", null, sx.git_branch)) : null,
        sx.primary_model ? h("span", null, h("code", null, sx.primary_model)) : null,
        sx.cc_version ? h("span", { class: "muted" }, `${agentName(sx.agent)} ${sx.cc_version}`) : null,
        sx.source_present === 0 && sx.source !== "history" ? h("span", { class: "badge", title: "The agent deleted the original; Chronicle's archive keeps it" }, "original deleted · archived") : null,
        sx.source === "codex-import" ? h("span", { class: "badge accent", title: "Claude Code deleted this transcript; Chronicle recovered it from the copy Codex Desktop imported" }, h("span", { class: "sdot" }), "recovered via Codex") : null)),
    h("div", { style: { display: "flex", gap: "8px", alignItems: "center" } }, outcomeBadge(sx.outcome, sx.analysis_status, sx.source),
      exportMenu(() => [sx.id], { raw: RAW_SOURCES.includes(sx.source) }), analyzing));
  setCrumbs([["Sessions", "#/sessions"], [sx.project_name || "–", `#/project?path=${encodeURIComponent(sx.project_path || "")}`], [sx.title || "(untitled session)"]], token);
  const sfact = (label, value, note, bad) => h("div", { class: "sfact" }, h("b", null, value), h("span", null, label, note ? h("small", { class: bad ? "bad" : "" }, ` · ${note}`) : null));
  const tiles = h("div", { class: "sfacts" },
    sfact("Active", fmtDur(sx.active_s)),
    sfact("Prompts", fmtNum(sx.n_prompts), sx.n_interrupts ? `${sx.n_interrupts} interrupt${sx.n_interrupts === 1 ? "" : "s"}` : null),
    sfact("Tool calls", fmtNum(sx.n_tool_calls), sx.n_tool_errors ? `${fmtNum(sx.n_tool_errors)} failed` : null, true),
    sfact("Tokens", fmtCompact(sx.total_tokens), sx.sub_tokens ? `${fmtCompact(sx.sub_tokens)} subagents` : null),
    sfact("Est. API cost", fmtCost(sx.est_cost_usd)),
    sfact("Lines", `+${fmtCompact(sx.lines_added)} −${fmtCompact(sx.lines_removed)}`, `${sx.n_files} files`),
    sfact("Peak context", fmtCompact(sx.peak_context), sx.n_compactions ? `${sx.n_compactions} compaction${sx.n_compactions === 1 ? "" : "s"}` : null),
    sx.n_subagents ? sfact("Subagents", fmtNum(sx.n_subagents)) : null);
  // summary
  const summary = h("section", { class: "card summary-card" }, h("div", { class: "card-head" }, h("h2", null, "Summary"),
    sx.analyzed_at ? h("span", { class: "hint" }, `analyzed ${ago(sx.analyzed_at)} · ${sx.analysis_model || ""}`) : null));
  if (sx.summary) {
    const kv = h("dl", { class: "kv" });
    if (sx.goal) kv.append(h("dt", null, "Goal"), h("dd", null, sx.goal));
    if (sx.outcome_note) kv.append(h("dt", null, "Outcome"), h("dd", null, sx.outcome_note));
    if (sx.work_types?.length) kv.append(h("dt", null, "Work"), h("dd", null, sx.work_types.join(", ")));
    if (sx.sentiment && sx.sentiment !== "unclear") kv.append(h("dt", null, "Mood"), h("dd", null, sx.sentiment));
    if (sx.tags?.length) kv.append(h("dt", null, "Tags"), h("dd", null, sx.tags.map((t) => h("span", { class: "tag" }, t))));
    summary.append(kv);
    if (sx.highlights?.length) summary.append(h("div", { class: "subhead" }, "Highlights"), h("ul", { class: "bullets" }, sx.highlights.map((x) => h("li", null, x))));
    if (sx.open_threads?.length) summary.append(h("div", { class: "subhead" }, "Open threads"), h("ul", { class: "checklist" }, sx.open_threads.map((x) => h("li", null, x))));
    if (sx.friction?.length) summary.append(h("div", { class: "subhead" }, "Friction"), h("ul", { class: "bullets" }, sx.friction.map((f) => h("li", null, h("b", null, f.kind), ": ", f.note))));
  } else {
    const reason = sx.source === "history" ? "Only prompts survive for this session (recovered from Claude Code's prompt history)."
      : `Not analyzed yet (${STATUS_LABEL[sx.analysis_status] || sx.analysis_status}${sx.analysis_reason ? ": " + sx.analysis_reason : ""}).`;
    summary.append(h("div", { class: "muted" }, reason), sx.first_prompt ? h("div", { class: "subhead" }, "First prompt") : null,
      sx.first_prompt ? h("div", { style: { whiteSpace: "pre-wrap" } }, sx.first_prompt.slice(0, 1200)) : null);
  }
  const knowledge = sx.knowledge.length ? h("section", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, `Knowledge (${sx.knowledge.length})`)),
    h("div", { class: "grid" }, sx.knowledge.map((k) => { const c = knowledgeCard(k, { hideSession: true }); c.id = `k-${k.id}`; return c; }))) : null;
  const ctxCard = chartCard("Context window", "Tokens in context per API call (main thread)",
    (el, w) => contextChart(el, w, sx.api_calls, sx.markers),
    () => ({ columns: ["#", "Time", "Model", "Context", "Output", "Cost"], num: [true, false, false, true, true, true],
      rows: sx.api_calls.filter((c) => !c.agent_id).map((c, i) => [i + 1, fmtDT(c.ts), c.model || "", fmtNum(c.input_tokens + c.cache_read_tokens + c.cache_write_tokens), fmtNum(c.output_tokens), fmtCost(c.cost_usd)]) }));
  const toolsCard = h("section", { class: "card" }, cardHead("Tools", { iconName: "zap", hint: legendKey([["accent", "calls"], ["critical", "failed"]]) }),
    hbars(sx.tool_stats.slice(0, 12), { label: (x) => x.name.replace(/^mcp__/, "mcp:"), value: (x) => x.n, fmt: fmtNum, part: (x) => x.errors || 0, sub: (x) => (x.errors ? `(${x.errors})` : "") }));
  const changed = sx.files.filter((f) => f.edits || f.writes);
  const filesCard = h("section", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, "Files"), h("span", { class: "hint" }, `${changed.length} changed · ${sx.files.length} touched`)),
    sx.files.length ? h("div", { class: "table-scroll" }, h("table", { class: "table-view" },
      h("thead", null, h("tr", null, h("th", null, "File"), h("th", { class: "num" }, "Reads"), h("th", { class: "num" }, "Edits"), h("th", { class: "num" }, "Lines"))),
      h("tbody", null, sx.files.slice(0, 60).map((f) => h("tr", null, h("td", { class: "mono", title: f.path, style: { fontSize: "12px" } }, shortPath(f.path, sx.project_path)),
        h("td", { class: "num" }, f.reads || ""), h("td", { class: "num" }, (f.edits + f.writes) || ""),
        h("td", { class: "num" }, f.lines_added || f.lines_removed ? `+${f.lines_added}/−${f.lines_removed}` : "")))))) : h("div", { class: "empty" }, "No files"));
  const extras = [];
  if (sx.subagents.length) extras.push(h("div", { class: "subhead" }, "Subagents"), h("div", { class: "table-scroll" }, h("table", { class: "table-view" },
    h("tbody", null, sx.subagents.map((a) => h("tr", null, h("td", null, h("b", null, a.agent_type || "agent"), " ", a.description || a.agent_id),
      h("td", { class: "num" }, `${a.n_tool_calls} tools`), h("td", { class: "num" }, fmtCost(a.est_cost_usd))))))));
  if (sx.prs.length) extras.push(h("div", { class: "subhead" }, "Pull requests"), h("ul", { class: "bullets" }, sx.prs.map((p) => h("li", null, extLink(p.url, `${p.repo}#${p.number}`)))));
  if (sx.artifacts.length) extras.push(h("div", { class: "subhead" }, "Artifacts"), h("ul", { class: "bullets" }, sx.artifacts.map((a) => h("li", null, extLink(a.url, a.title || a.url)))));
  if (sx.workflows.length) extras.push(h("div", { class: "subhead" }, "Workflows"), h("ul", { class: "bullets" }, sx.workflows.map((w) => h("li", null, h("b", null, w.name || w.id), ` · ${w.status || ""} · ${w.agents || 0} agents · ${fmtCompact(w.tokens)} tokens`, w.summary ? h("div", { class: "muted" }, w.summary) : null))));
  const chipsOf = (obj, label) => Object.keys(obj || {}).length ? [h("div", { class: "subhead" }, label), h("div", null, Object.entries(obj).map(([k, v]) => h("span", { class: "tag" }, `${k}${v > 1 ? " ×" + v : ""}`)))] : [];
  extras.push(...chipsOf(sx.skills, "Skills"), ...chipsOf(sx.mcp, "MCP servers"), ...chipsOf(sx.commands, "Slash commands"));
  if (sx.analyses.length) extras.push(h("div", { class: "subhead" }, "Analysis runs"), h("ul", { class: "bullets" }, sx.analyses.map((a) =>
    h("li", null, `${fmtDT(a.started_at)} · ${a.kind} · ${a.status}${a.cost_usd != null ? " · " + fmtCost(a.cost_usd) : ""}${a.model ? " · " + a.model : ""}`, a.error ? h("div", { class: "muted" }, a.error.slice(0, 200)) : null))));
  const extrasCard = extras.length ? h("section", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, "Context")), extras) : null;
  // outline: the prompts as they load, and the files that changed
  const promptList = h("ol", { class: "ol-prompts" });
  const outline = h("aside", { class: "s-outline", "aria-label": "Session outline" },
    sx.n_prompts ? [h("h4", null, "Prompts"), promptList] : null, // none: a Codex Cloud task, say; the list would say "Loading…" forever
    changed.length ? [h("h4", null, "Files changed"), h("div", { class: "ol-files" }, changed.slice(0, 12).map((f) =>
      h("div", { title: f.path }, h("span", null, f.path.split("/").pop()), f.lines_added || f.lines_removed ? h("em", null, `+${fmtCompact(f.lines_added)}`) : null)),
      changed.length > 12 ? h("div", { class: "muted" }, `and ${changed.length - 12} more`) : null)] : null);
  const tabs = { transcript: null, details: null };
  const showTab = (name, record = true) => {
    for (const [k, el] of Object.entries(tabs)) el.hidden = k !== name;
    tabBar.querySelectorAll("button").forEach((b) => { const on = b.dataset.tab === name; b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); });
    if (record) setParams({ ...params, tab: name === "details" ? "details" : "" });
  };
  const onPrompt = (ev, target) => {
    if (!ev) { promptList.replaceChildren(); return; }
    const li = h("li", { "data-seq": ev.seq, tabindex: 0, role: "link", onclick: () => { showTab("transcript"); target.scrollIntoView({ block: "start", behavior: "smooth" }); },
      onkeydown: (e) => { if (e.key === "Enter") li.click(); } }, h("span", null, (ev.text || "").replace(/\s+/g, " ").slice(0, 120)), h("small", null, fmtTime(ev.ts)));
    li.target = target;
    const after = [...promptList.children].find((x) => +x.dataset.seq > ev.seq);
    promptList.insertBefore(li, after || null);
  };
  const transcript = transcriptCard(sx, params.seq ? +params.seq : null, params.agent || "", onPrompt);
  tabs.transcript = transcript;
  tabs.details = h("div", { class: "grid cols-main" },
    h("div", { class: "grid", style: { alignContent: "start" } }, summary, knowledge),
    h("div", { class: "grid", style: { alignContent: "start" } }, ctxCard, toolsCard, filesCard, extrasCard));
  const tabBar = h("div", { class: "seg s-tabs", role: "group", "aria-label": "Session view" },
    h("button", { type: "button", "data-tab": "transcript", onclick: () => showTab("transcript") }, "Transcript"),
    h("button", { type: "button", "data-tab": "details", onclick: () => showTab("details") }, "Details"));
  const outlineBtn = h("button", { type: "button", class: `chip ol-toggle ${sessionOutline ? "on" : ""}`, "aria-pressed": String(sessionOutline), title: "Show the prompts and files beside the transcript",
    onclick: () => {
      sessionOutline = !sessionOutline;
      try { localStorage.setItem("chronicle.outline", sessionOutline ? "1" : "0"); } catch (e) { /* this tab only */ }
      outlineBtn.classList.toggle("on", sessionOutline); outlineBtn.setAttribute("aria-pressed", String(sessionOutline));
      page.classList.toggle("with-outline", sessionOutline);
    } }, icon("outline"), "Outline");
  const kchips = sx.knowledge.length ? h("div", { class: "s-kchips" }, sx.knowledge.slice(0, 8).map((k) =>
    h("button", { type: "button", class: `s-kchip k-${k.kind}`, title: `${kindLabel(k.kind)}: ${k.title}`, onclick: () => {
      showTab("details");
      const card = document.getElementById(`k-${k.id}`);
      if (card) { card.scrollIntoView({ block: "center", behavior: "smooth" }); card.classList.add("flash"); setTimeout(() => card.classList.remove("flash"), 1600); }
    } }, icon(KIND[k.kind] ? k.kind : "dot"), h("span", null, k.title))),
    sx.knowledge.length > 8 ? h("button", { type: "button", class: "s-kchip more", onclick: () => showTab("details") }, `+${sx.knowledge.length - 8} more`) : null) : null;
  const page = h("div", { class: `session-page ${sessionOutline ? "with-outline" : ""}` },
    h("div", { class: "s-main" }, head, tiles,
      sx.summary ? h("p", { class: "s-summary gloss" }, sx.summary) : null, kchips,
      h("div", { class: "s-tabbar" }, tabBar, outlineBtn),
      tabs.transcript, tabs.details),
    outline);
  showTab(params.tab === "details" ? "details" : "transcript", false);
  trackOutline(promptList);
  return page;
});
let sessionOutline = (() => { try { return localStorage.getItem("chronicle.outline") !== "0"; } catch (e) { return true; } })();
function trackOutline(list) { // mark the prompt currently at the top of the transcript
  const scroller = $("#app");
  let raf = 0;
  const onScroll = () => {
    if (!list.isConnected) { if (list.seen) scroller.removeEventListener("scroll", onScroll); return; } // gone, or not mounted yet
    list.seen = true;
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      const top = scroller.getBoundingClientRect().top + 90;
      let current = null;
      for (const li of list.children) {
        const el = li.target;
        if (!el?.offsetParent) continue;
        if (el.getBoundingClientRect().top <= top) current = li; else break;
      }
      for (const li of list.children) li.classList.toggle("on", li === current);
    });
  };
  scroller.addEventListener("scroll", onScroll, { passive: true });
}

function transcriptCard(sx, focusSeq, agent, onPrompt = null) {
  const assistant = agentShort(sx.agent);
  const state = { agent, kinds: new Set(["prompt", "text", "tool", "system", "command"]), offset: 0, start: 0, total: 0 };
  const list = h("div", { class: "transcript" });
  let sink = list; // where renderEvent draws: the list, or a holder for earlier events that are then put in front
  const more = h("button", { class: "btn", type: "button", onclick: () => load(true) }, "Load more");
  const earlier = h("button", { class: "btn", type: "button", hidden: true, onclick: () => loadEarlier() }, "Load earlier");
  const info = h("span", { class: "hint" });
  const kindMap = { prompt: ["prompt", "attachment"], text: ["text"], tool: ["tool_use", "tool_result"], thinking: ["thinking"],
    system: ["compact", "interrupt", "api_error", "notice", "notification", "compact_summary", "meta", "command_output", "bash_output"], command: ["command", "bash_input"] };
  let toolBlock = null, toolRows = {};
  async function load(append) {
    if (!append) { state.offset = 0; list.replaceChildren(); toolBlock = null; toolRows = {}; if (state.kinds.has("prompt")) onPrompt?.(null); }
    const kinds = [...state.kinds].flatMap((k) => kindMap[k]).join(",");
    const params = { agent: state.agent, kinds, limit: 400, offset: state.offset };
    if (focusSeq != null && !append) params.around = focusSeq;
    const data = await api(`/api/sessions/${sx.id}/events`, params);
    if (!append) state.start = data.offset; // a deep link (?seq=) starts part-way through
    state.offset = data.offset + data.items.length;
    state.total = data.total;
    for (const ev of data.items) renderEvent(ev);
    syncControls();
    if (focusSeq != null && !append) {
      const target = list.querySelector(`[data-seq="${focusSeq}"]`);
      if (target) { target.classList.add("highlight"); setTimeout(() => target.scrollIntoView({ block: "center" }), 60); }
      focusSeq = null;
    }
  }
  function syncControls() {
    more.hidden = state.offset >= state.total;
    earlier.hidden = state.start <= 0;
    earlier.textContent = `Load ${fmtNum(Math.min(400, state.start))} earlier`;
    info.textContent = `${fmtNum(state.offset - state.start)} of ${fmtNum(state.total)} events`;
    if (expand.classList.contains("on")) list.querySelectorAll("details.tool-row").forEach((d) => (d.open = true));
  }
  async function loadEarlier() {
    const from = Math.max(0, state.start - 400);
    const kinds = [...state.kinds].flatMap((k) => kindMap[k]).join(",");
    const data = await api(`/api/sessions/${sx.id}/events`, { agent: state.agent, kinds, limit: state.start - from, offset: from });
    const holder = h("div");
    const keep = toolBlock;
    sink = holder; toolBlock = null;
    for (const ev of data.items) renderEvent(ev);
    sink = list; toolBlock = keep;
    const anchor = list.firstElementChild, before = anchor?.getBoundingClientRect().top;
    list.prepend(...holder.childNodes);
    if (anchor) $("#app").scrollTop += anchor.getBoundingClientRect().top - before; // keep your place
    state.start = from;
    syncControls();
  }
  function renderEvent(ev) {
    if (ev.kind === "tool_use") {
      if (!toolBlock) { toolBlock = h("div", { class: "tools-block" }); sink.append(toolBlock); }
      const row = h("details", { class: "tool-row", "data-seq": ev.seq },
        h("summary", null, h("span", { class: "ticon" }, "•"), h("span", { class: "tname" }, (ev.tool_name || "tool").replace(/^mcp__/, "mcp:")),
          h("span", { class: "tsum", title: ev.text }, ev.text.includes(": ") ? ev.text.split(": ").slice(1).join(": ") : ""),
          h("span", { class: "tstat" }, fmtTime(ev.ts))));
      const detail = h("div", { class: "tdetail" });
      if (ev.meta?.input) detail.append(h("div", { class: "plabel" }, "Input"), h("pre", null, prettyJson(ev.meta.input)));
      row.append(detail);
      toolBlock.append(row);
      if (ev.tool_use_id) toolRows[ev.tool_use_id] = row;
      return;
    }
    if (ev.kind === "tool_result") {
      const row = ev.tool_use_id && toolRows[ev.tool_use_id];
      const body = [h("div", { class: "plabel" }, ev.is_error ? "Error" : "Result"), h("pre", null, ev.text || "(empty)")];
      if (row) {
        row.querySelector(".ticon").textContent = ev.is_error ? "✗" : "✓";
        if (ev.is_error) row.classList.add("err");
        row.querySelector(".tdetail").append(...body);
      } else {
        if (!toolBlock) { toolBlock = h("div", { class: "tools-block" }); sink.append(toolBlock); }
        toolBlock.append(h("details", { class: `tool-row ${ev.is_error ? "err" : ""}`, "data-seq": ev.seq },
          h("summary", null, h("span", { class: "ticon" }, ev.is_error ? "✗" : "✓"), h("span", { class: "tname" }, ev.tool_name || "result"), h("span", { class: "tsum" }, (ev.text || "").slice(0, 160)), h("span", { class: "tstat" }, fmtTime(ev.ts))),
          h("div", { class: "tdetail" }, body)));
      }
      return;
    }
    toolBlock = null;
    let node;
    const who = (label, extra) => h("div", { class: "who" }, h("b", null, label), h("span", null, fmtDT(ev.ts)), extra || null);
    switch (ev.kind) {
      case "prompt":
        node = h("div", { class: "msg user", "data-seq": ev.seq }, who(ev.meta?.subagent ? "Task prompt" : "You", ev.meta?.queued ? h("span", { class: "tag" }, `queued while ${assistant} worked`) : null),
          h("div", { class: "body" }, ev.text));
        if (onPrompt && !ev.meta?.subagent && !state.agent) onPrompt(ev, node);
        break;
      case "text":
        node = h("div", { class: "msg assistant", "data-seq": ev.seq }, who(assistant, [ev.meta?.model ? h("span", { class: "muted" }, ev.meta.model) : null, ev.meta?.phase === "commentary" ? h("span", { class: "tag" }, "progress") : null]), mdEl(ev.text));
        break;
      case "thinking":
        node = h("div", { class: "msg thinking", "data-seq": ev.seq }, who("Thinking"), h("div", { style: { whiteSpace: "pre-wrap" } }, ev.text));
        break;
      case "command": case "bash_input":
        node = h("div", { class: "msg user", "data-seq": ev.seq }, who(ev.kind === "command" ? "Command" : "Shell"), h("code", null, ev.text));
        break;
      default:
        node = h("div", { class: "msg system", "data-seq": ev.seq }, h("b", null, ev.kind.replace(/_/g, " ")), " · ", fmtTime(ev.ts), " — ", (ev.text || "").slice(0, 600));
    }
    sink.append(node);
    if (ev.kind === "text" || ev.kind === "prompt") glossify(node, 4);
  }
  const chip = (key, label) => {
    const c = h("button", { type: "button", class: `chip ${state.kinds.has(key) ? "on" : ""}`, "aria-pressed": String(state.kinds.has(key)), onclick: () => {
      state.kinds.has(key) ? state.kinds.delete(key) : state.kinds.add(key);
      c.classList.toggle("on");
      c.setAttribute("aria-pressed", String(state.kinds.has(key)));
      load(false);
    } }, label);
    return c;
  };
  const agentSel = h("select", { onchange: (e) => { state.agent = e.target.value; load(false); } },
    sx.agents.map((a) => h("option", { value: a.agent_id, selected: a.agent_id === state.agent }, a.label.slice(0, 90))));
  const expand = h("button", { class: "chip", type: "button", "aria-pressed": "false", onclick: () => {
    const open = !expand.classList.contains("on");
    expand.classList.toggle("on", open);
    expand.setAttribute("aria-pressed", String(open));
    list.querySelectorAll("details.tool-row").forEach((d) => (d.open = open));
  } }, "Expand tools");
  load(false);
  return h("section", { class: "transcript-pane" },
    h("div", { class: "transcript-controls" }, sx.agents.length > 1 ? agentSel : null,
      chip("prompt", "Prompts"), chip("text", assistant), chip("tool", "Tool calls"), chip("command", "Commands"), chip("system", "System"), chip("thinking", "Thinking"), expand,
      h("span", { class: "spacer" }), info),
    h("div", { class: "load-more earlier" }, earlier), list, h("div", { class: "load-more" }, more));
}
function prettyJson(text) {
  try { return JSON.stringify(JSON.parse(text), null, 2); } catch (e) { return text; }
}

// =====================================================================================
// Knowledge
// =====================================================================================
function knowledgeCard(k, { compact = false, hideSession = false } = {}) {
  const body = mdEl(k.body || "", `kbody ${compact ? "clamp" : ""}`);
  const card = h("article", { class: `kcard ${k.pinned ? "pinned" : ""}` },
    h("div", { class: "khead" }, kindChip(k.kind),
      h("span", { class: "kmeta" },
        k.scope === "global" ? h("span", { class: "scope-tag", title: "Applies across projects" }, icon("domain"), "global") : null,
        k.source === "memory" ? h("span", { class: "scope-tag", title: "Imported from the agent's own memory notes" }, icon("knowledge"), `${agentShort(k.agent)} memory`) : null,
        confidenceMeter(k.confidence))),
    h("div", { class: "ktitle" }, k.title), body,
    k.tags?.length ? h("div", { class: "ktags" }, k.tags.slice(0, 6).map((t) => h("span", { class: "tag" }, t))) : null);
  if (compact && (k.body || "").length > 380) {
    const more = h("button", { class: "link-btn more-btn", type: "button", onclick: () => { body.classList.toggle("clamp"); more.textContent = body.classList.contains("clamp") ? "More" : "Less"; } }, "More");
    card.append(more);
  }
  card.append(h("div", { class: "kfoot" },
    h("span", { class: "kfoot-meta" },
      k.project_name ? h("span", { class: "meta-item", title: k.project_path || "" }, icon("projects"), k.project_name) : null,
      !hideSession && k.session_id ? h("a", { class: "meta-item session-link", href: `#/session/${k.session_id}`, title: k.session_title || "" }, icon("sessions"), h("span", { class: "ellipsis" }, k.session_title || "session")) : null,
      k.created_at ? h("span", { class: "meta-item" }, fmtDate(k.created_at)) : null),
    knowledgeActions(k, card, () => card.remove())));
  return card;
}
function knowledgeActions(k, node, onDismiss) {
  const pin = h("button", { type: "button", title: k.pinned ? "Unpin" : "Pin (always kept in syntheses)", "aria-pressed": String(!!k.pinned), onclick: async () => {
    await post(`/api/knowledge/${k.id}`, { pinned: !k.pinned });
    k.pinned = !k.pinned;
    node.classList.toggle("pinned", k.pinned);
    pin.title = k.pinned ? "Unpin" : "Pin (always kept in syntheses)";
    pin.setAttribute("aria-pressed", String(k.pinned));
    toast(k.pinned ? "Pinned" : "Unpinned");
  } }, icon("pin"));
  return h("div", { class: "kactions" }, pin,
    h("button", { type: "button", title: "Dismiss (hide and exclude from knowledge bases)", onclick: async () => {
      await post(`/api/knowledge/${k.id}`, { status: "dismissed" });
      k.dismissed = true;
      onDismiss();
      toast("Dismissed");
    } }, icon("x")));
}
function knowledgeTable(items) {
  const scopeOf = (k) => (k.scope === "global" ? "global" : k.project_name || "");
  const cols = [
    { key: "kind", label: "Kind", value: (k) => kindLabel(k.kind) },
    { key: "title", label: "Knowledge", value: (k) => k.title },
    { key: "project", label: "Project", value: scopeOf },
    { key: "session", label: "From" },
    { key: "confidence", label: "Confidence", value: (k) => ({ high: 0, medium: 1, low: 2 })[k.confidence] ?? 3 },
    { key: "created", label: "Added", desc: true, value: (k) => k.created_at },
    { key: "actions", label: "" },
  ];
  const row = (k) => {
    if (k.dismissed) return [];
    const tr = h("tr", { class: k.pinned ? "pinned" : "" },
      h("td", { class: "nowrap kind-cell" }, icon(KIND[k.kind] ? k.kind : "dot"), kindLabel(k.kind)),
      h("td", { class: "title-cell" }, h("div", { class: "t" }, k.title), k.body ? h("div", { class: "s" }, plainText(k.body)) : null),
      h("td", { class: "nowrap" }, scopeOf(k) || "–"),
      h("td", { class: "from-cell" }, k.session_id ? h("a", { href: `#/session/${k.session_id}` }, (k.session_title || "session").slice(0, 44))
        : h("span", { class: "muted" }, k.source === "memory" ? `${agentShort(k.agent)} memory` : "–")),
      h("td", { class: "nowrap" }, confidenceMeter(k.confidence) || h("span", { class: "muted" }, "–")),
      h("td", { class: "nowrap" }, fmtDate(k.created_at)));
    tr.append(h("td", { class: "actions-cell" }, knowledgeActions(k, tr, () => { tr.closeDetail(); tr.remove(); })));
    return expandable(tr, cols.length, () => [mdEl(k.body || "", "kbody"),
      k.tags?.length ? h("div", { style: { marginTop: "6px" } }, k.tags.map((t) => h("span", { class: "tag" }, t))) : null], { indent: 1 });
  };
  return localTable(items, cols, row, { empty: "No knowledge matches", cls: "knowledge-table" });
}

route(/^\/knowledge$/, async (params) => {
  const state = { q: params.q || "", kind: params.kind || "", project: params.project || "", source: params.source || "" };
  const mode = viewMode("knowledge", "cards");
  const box = h("div");
  const count = h("span", { class: "sub" });
  const chipsBox = h("div", { class: "filters", style: { marginBottom: "14px" } });
  let loaded = false;
  async function load() {
    const data = await api("/api/knowledge", { ...state, limit: 400 });
    box.replaceChildren(mode === "list" ? h("section", { class: "card flush" }, knowledgeTable(data.items))
      : data.items.length ? h("div", { class: "kgrid" }, data.items.map((k) => knowledgeCard(k, { compact: true })))
      : h("div", { class: "card empty" }, "No knowledge matches"));
    if (loaded) box.querySelectorAll(".gloss").forEach((el) => glossify(el)); // the first render is glossified by render()
    loaded = true;
    count.textContent = `${fmtNum(data.items.length)} items`;
    const total = Object.values(data.counts).reduce((a, b) => a + b, 0);
    chipsBox.replaceChildren(
      h("button", { type: "button", class: `chip ${!state.kind ? "on" : ""}`, onclick: () => { state.kind = ""; refresh(); } }, "All", h("span", { class: "count" }, total)),
      ...Object.entries(KIND).filter(([k]) => data.counts[k]).map(([k, label]) =>
        h("button", { type: "button", class: `chip ${state.kind === k ? "on" : ""}`, onclick: () => { state.kind = k; refresh(); } }, icon(k), label, h("span", { class: "count" }, data.counts[k]))));
  }
  const refresh = () => { setParams(state); load(); };
  let debounce;
  await load();
  return h("div", null,
    h("div", { class: "page-head" }, h("div", null, h("h1", null, "Knowledge"), count),
      h("div", { class: "head-actions" }, viewToggle("knowledge", mode), h("a", { class: "btn", href: `#/project?path=${encodeURIComponent("__global__")}` }, "Global playbook"))),
    h("div", { class: "filters" },
      h("input", { class: "input", type: "search", placeholder: "Search knowledge…", value: state.q, style: { minWidth: "280px" },
        oninput: (e) => { clearTimeout(debounce); debounce = setTimeout(() => { state.q = e.target.value; refresh(); }, 250); } }),
      h("select", { onchange: (e) => { state.project = e.target.value; refresh(); } }, await projectOptions(state.project)),
      h("select", { onchange: (e) => { state.source = e.target.value; refresh(); } },
        [["", "All sources"], ["analysis", "Extracted from sessions"], ["memory", "Agent memory files"]].map(([v, l]) => h("option", { value: v, selected: state.source === v }, l)))),
    chipsBox, box);
});

// =====================================================================================
// Projects
// =====================================================================================
route(/^\/projects$/, async () => {
  const projects = await api("/api/projects");
  projectsCache = projects;
  const mode = viewMode("projects", "cards");
  const href = (p) => `#/project?path=${encodeURIComponent(p.project_path || "")}`;
  const listView = () => h("section", { class: "card flush" }, localTable(projects, [
    { key: "label", label: "Project", value: (p) => p.label },
    { key: "sessions", label: "Sessions", num: true, desc: true, value: (p) => p.sessions },
    { key: "active", label: "Active", num: true, desc: true, value: (p) => p.active_s },
    { key: "knowledge", label: "Knowledge", num: true, desc: true, value: (p) => p.knowledge },
    { key: "cost", label: "Est. cost", num: true, desc: true, value: (p) => p.cost },
    { key: "last", label: "Last session", desc: true, value: (p) => p.last },
    { key: "kb", label: "Knowledge base", desc: true, value: (p) => p.kb_updated },
  ], (p) => h("tr", { class: "row-link", onclick: (e) => { if (!e.target.closest("a")) go(href(p)); } },
    h("td", { class: "title-cell" }, h("div", { class: "t" }, h("a", { href: href(p), class: "plain" }, p.label)),
      h("div", { class: "s", title: p.project_path }, shortPath(p.project_path), p.exists ? "" : " (not on disk)")),
    h("td", { class: "num" }, fmtNum(p.sessions)),
    h("td", { class: "num" }, fmtDur(p.active_s)),
    h("td", { class: "num" }, fmtNum(p.knowledge)),
    h("td", { class: "num" }, fmtCost(p.cost)),
    h("td", { class: "nowrap" }, fmtDate(p.last)),
    h("td", { class: "nowrap muted" }, p.kb_updated ? `updated ${ago(p.kb_updated)}` : "none yet")), { empty: "No projects yet", cls: "projects-table" }));
  return h("div", null,
    h("div", { class: "page-head" }, h("div", null, h("h1", null, "Projects"), h("div", { class: "sub" }, `${projects.length} projects`)),
      h("div", { class: "head-actions" }, viewToggle("projects", mode), h("a", { class: "btn", href: `#/project?path=${encodeURIComponent("__global__")}` }, "Global playbook"))),
    mode === "list" ? listView() : h("div", { class: "proj-cards" }, projects.map((p) => projectCard(p, href(p)))));
});

function weeklyBars(values) { // active time per week, oldest first; hover for the week
  const box = h("div", { class: "wbars", role: "img", "aria-label": "Active time per week, last 12 weeks" });
  const max = Math.max(0, ...values);
  values.forEach((v, i) => {
    const start = new Date(Date.now() - ((values.length - 1 - i) * 7 + 6) * 86400000);
    const bar = h("i", { class: v ? "" : "zero", style: v ? { height: `${Math.max(10, (v / max) * 100)}%` } : null });
    hoverable(bar, () => [v ? `${fmtDur(v)} active` : "No sessions", `Week of ${fmtDate(start.toISOString())}`], { focusable: false });
    box.append(bar);
  });
  return box;
}
function miniOutcomes(outs) { // thin stacked status bar + the top labels in words
  const entries = OUTCOME_ORDER.filter((o) => outs[o]).map((o) => [o, outs[o]]);
  const total = entries.reduce((a, [, n]) => a + n, 0);
  if (!total) return null;
  const cls = (o) => (OUTCOME[o] ? OUTCOME[o][0] || "neutral" : "none");
  const label = (o) => (OUTCOME[o] ? OUTCOME[o][1].toLowerCase() : "not analyzed");
  return h("div", { class: "mini-outcomes" },
    h("div", { class: "stackbar thin", "aria-hidden": "true" }, entries.map(([o, n]) => h("span", { class: `seg s-${cls(o)}`, style: { flexGrow: String(n) } }))),
    h("div", { class: "mo-text" }, entries.slice(0, 3).map(([o, n]) => h("span", { class: `s-${cls(o)}` }, icon(OUTCOME[o] ? o : "queued"), `${n} ${label(o)}`))));
}
function projectCard(p, href) {
  return h("a", { class: "card proj-card", href },
    h("div", { class: "pc-head" },
      h("div", { style: { minWidth: 0 } },
        h("div", { class: "pname" }, p.label, Object.entries(p.agents || {}).filter(([a]) => a !== "claude").map(([a, n]) => agentTag(a, `${n} ${agentName(a)} session${n === 1 ? "" : "s"}`))),
        h("div", { class: "ppath", title: p.project_path }, shortPath(p.project_path), p.exists ? "" : " · not on disk")),
      p.kb_updated ? h("span", { class: "badge", title: `Knowledge base updated ${fmtDT(p.kb_updated)}` }, icon("knowledge"), "KB")
        : h("span", { class: "badge muted-badge", title: "No knowledge base yet" }, "no KB")),
    weeklyBars(p.weekly || []),
    h("div", { class: "pstats" },
      h("span", { title: "Sessions" }, icon("sessions"), h("b", null, fmtNum(p.sessions))),
      h("span", { title: "Active time" }, icon("clock"), h("b", null, fmtDur(p.active_s))),
      h("span", { title: "Knowledge items" }, icon("sparkles"), h("b", null, fmtNum(p.knowledge))),
      h("span", { title: "Estimated API cost" }, icon("cost"), h("b", null, fmtCost(p.cost)))),
    miniOutcomes(p.outcomes || {}),
    h("div", { class: "pfoot" }, `Last session ${ago(p.last)}`, h("span", { class: "muted" }, "12 weeks")));
}

route(/^\/project$/, async (params) => {
  const path = params.path || "";
  const token = renderSeq;
  const p = await api("/api/project", { path });
  const isGlobal = path === "__global__";
  setCrumbs(isGlobal ? [["Knowledge", "#/knowledge"], ["Global playbook"]] : [["Projects", "#/projects"], [p.label || shortPath(path)]], token);
  const synth = h("button", { class: "btn primary", type: "button", onclick: async () => {
    synth.disabled = true; synth.textContent = "Synthesizing…";
    const r = await post("/api/synthesize", { path });
    toast(r.started ? "Synthesizing the knowledge base with Claude Code…" : "Already running");
    watchJob(`synthesize:${path}`);
  } }, p.kb ? "Re-synthesize" : "Synthesize now");
  const kbCard = h("section", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, isGlobal ? "Playbook" : "Knowledge base"),
    p.kb ? h("span", { class: "hint" }, `updated ${ago(p.kb.updated_at)} · ${p.kb.n_items} items · ${p.kb.model || ""}`) : null));
  if (p.kb) {
    const data = JSON.parse(p.kb.kb_json || "{}");
    const kIndex = Object.fromEntries((p.knowledge || []).map((k) => [k.id, k]));
    if (data.overview) kbCard.append(mdEl(data.overview));
    for (const sec of data.sections || []) {
      if (!sec.items?.length) continue;
      kbCard.append(h("div", { class: "kb-section" }, h("h3", null, sec.title),
        h("ul", null, sec.items.map((it) => h("li", null, h("span", { html: mdInline(escapeHtml(it.text || "")) }),
          it.sources?.length ? h("span", { class: "src-link" }, "[", it.sources.slice(0, 5).map((id, i) => [i ? ", " : "",
            kIndex[id]?.session_id ? h("a", { href: `#/session/${kIndex[id].session_id}`, title: kIndex[id].title }, `k${id}`) : `k${id}`]), "]") : null)))));
    }
  } else {
    kbCard.append(h("div", { class: "empty" }, "No synthesized knowledge base yet. It is built automatically once a few sessions have been analyzed, or synthesize it now."));
  }
  if (isGlobal) {
    return h("div", null, h("div", { class: "page-head" }, h("div", null, h("h1", null, "Global playbook"),
      h("div", { class: "sub" }, "Cross-project learnings and your working preferences, distilled from every session")), synth), kbCard);
  }
  const st = p.stats;
  const tiles = h("div", { class: "tiles" },
    tile("Sessions", fmtNum(st.sessions), { iconName: "sessions" }), tile("Active time", fmtDur(st.active_s), { iconName: "clock" }),
    tile("Prompts", fmtNum(st.prompts), { iconName: "prompts" }), tile("Tokens", fmtCompact(st.tokens), { iconName: "tokens" }),
    tile("Est. API cost", fmtCost(st.cost), { iconName: "cost" }), tile("Lines", `+${fmtCompact(st.lines_added)}`, { iconName: "diff", delta: `−${fmtCompact(st.lines_removed)}` }));
  const filesCard = h("section", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, "Most edited files")),
    hbars(p.files, { label: (f) => shortPath(f.path, path), value: (f) => f.edits, fmt: fmtNum, sub: (f) => `· +${fmtCompact(f.added)}/−${fmtCompact(f.removed)}` }));
  const sessions = h("section", { class: "card", style: { padding: "4px 6px" } }, h("div", { class: "table-wrap" }, h("table", { class: "data" },
    h("thead", null, h("tr", null, ["Started", "Session", "Project", "Prompts", "Tools", "Active", "Tokens", "Est. cost", "Outcome"].map((c, i) => h("th", { class: i >= 3 && i <= 7 ? "num" : "" }, c)))),
    h("tbody", null, p.sessions.map(sessionRow)))));
  return h("div", null,
    h("div", { class: "page-head" }, h("div", null, h("div", { class: "muted", style: { fontSize: "12.5px" } }, h("a", { href: "#/projects" }, "Projects"), " / "),
      h("h1", null, p.label), h("div", { class: "sub mono", style: { fontSize: "12px" } }, path, ` · ${fmtDateY(st.first)} – ${fmtDateY(st.last)}`)), synth),
    tiles,
    h("div", { class: "grid cols-main section-gap" }, kbCard, h("div", { class: "grid", style: { alignContent: "start" } }, filesCard)),
    p.glossary && p.glossary.length ? [
      h("h2", { style: { margin: "22px 0 10px" } }, `Glossary (${p.glossary.length})`, " ",
        h("a", { class: "hint", style: { fontSize: "12.5px", fontWeight: 400 }, href: `#/glossary?project=${encodeURIComponent(path)}` }, "open →")),
      h("section", { class: "card" }, h("dl", { class: "kv", style: { marginTop: 0 } }, p.glossary.map((g) => [
        h("dt", null, h("a", { href: `#/glossary?term=${encodeURIComponent(g.term)}` }, g.term)),
        h("dd", null, g.definition, g.context ? h("div", { class: "muted" }, g.context) : null)])))] : null,
    h("h2", { class: "section-gap", style: { margin: "22px 0 10px" } }, `Knowledge (${p.knowledge.length})`),
    h("div", { class: "kgrid" }, p.knowledge.map((k) => knowledgeCard(k, { compact: true }))),
    h("h2", { style: { margin: "22px 0 10px" } }, `Sessions (${p.sessions.length})`), sessions);
});

// =====================================================================================
// Search
// =====================================================================================
route(/^\/search$/, async (params) => {
  const q = params.q || "";
  const box = h("form", { class: "search-form", role: "search", onsubmit: (e) => { e.preventDefault(); const v = e.target.q.value.trim(); if (v) go(`#/search?q=${encodeURIComponent(v)}`); } },
    icon("search"), h("input", { class: "input", type: "search", name: "q", value: q, placeholder: "Search transcripts and knowledge", "aria-label": "Search transcripts and knowledge", autocomplete: "off" }));
  if (!q.trim()) return h("div", null, h("div", { class: "page-head" }, h("div", null, h("h1", null, "Search"),
    h("div", { class: "sub" }, "Trigram search matches any 3+ character substring, in any language. ⌘K jumps straight to a session, term or page."))), box);
  const data = await api("/api/search", { q });
  const total = data.sessions.length + data.knowledge.length + data.events.length;
  return h("div", null,
    h("div", { class: "page-head" }, h("div", null, h("h1", null, `Search: ${q}`), h("div", { class: "sub" }, total ? `${data.knowledge.length} knowledge items · ${data.sessions.length} sessions · ${data.events.length} transcript hits` : "No results"))),
    box,
    h("div", { class: "grid cols-2" },
      h("section", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, "Sessions")),
        data.sessions.length ? data.sessions.map((sx) => h("div", { class: "search-hit" },
          h("a", { href: `#/session/${sx.session_id}` }, h("b", null, sx.title || "(untitled)")),
          h("span", { class: "muted" }, ` · ${sx.project_name || ""} · ${fmtDate(sx.started_at)} · ${sx.hits} hits`),
          sx.snippets.map((sn) => h("div", { class: "snip" }, h("span", { class: "muted" }, `${sn.kind}: `), sn.seq != null ? h("a", { href: `#/session/${sx.session_id}?seq=${sn.seq}${sn.agent_id ? "&agent=" + sn.agent_id : ""}`, style: { color: "inherit" } }, snippetEl(sn.text)) : snippetEl(sn.text))))) : h("div", { class: "empty" }, "No sessions")),
      h("section", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, "Knowledge")),
        data.knowledge.length ? h("div", { class: "grid" }, data.knowledge.map((k) => knowledgeCard(k, { compact: true }))) : h("div", { class: "empty" }, "No knowledge"))),
    h("section", { class: "card section-gap" }, h("div", { class: "card-head" }, h("h2", null, "Transcript hits")),
      data.events.length ? data.events.map((e) => h("div", { class: "search-hit" },
        h("a", { href: `#/session/${e.session_id}?seq=${e.seq}${e.agent_id ? "&agent=" + e.agent_id : ""}` }, e.title || e.session_id.slice(0, 8)),
        h("span", { class: "muted" }, ` · ${e.kind}${e.tool_name ? " " + e.tool_name : ""} · ${e.project_name || ""} · ${fmtDT(e.ts)}`),
        h("div", { class: "snip" }, snippetEl(e.snippet)))) : h("div", { class: "empty" }, "No transcript hits")));
});

// =====================================================================================
// Glossary: term linking everywhere + the A–Z page
// =====================================================================================
let glossaryTerms = null, glossaryRes = [], glossaryIndex = {}, glossaryLoaded = 0;
const escRe = (t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
async function loadGlossary(force) {
  if (glossaryTerms && !force && Date.now() - glossaryLoaded < 300000) return;
  try { glossaryTerms = await api("/api/glossary/terms"); } catch (e) { glossaryTerms = []; }
  glossaryLoaded = Date.now();
  glossaryIndex = {};
  const insensitive = [], sensitive = [];
  const cjk = /[぀-ヿ㐀-鿿가-힯]/;
  for (const t of glossaryTerms) {
    for (const name of [t.term, ...(t.aliases || [])]) {
      if (!name || name.length < 3) continue;
      if (/^[a-z]+$/.test(name)) continue; // plain lowercase words ("derived", "node") would underline ordinary prose
      if (name !== t.term) { // an alias that is just a broader word of the term ("Azure" for "Azure OpenAI") misleads
        const inside = new RegExp(`(^|[^\\p{L}\\p{N}])${escRe(name.toLowerCase())}([^\\p{L}\\p{N}]|$)`, "u");
        if (name.length < t.term.length && inside.test(t.term.toLowerCase())) continue;
      }
      if (glossaryIndex[name]) continue;
      glossaryIndex[name] = t;
      glossaryIndex[name.toLowerCase()] ||= t;
      const isCjk = cjk.test(name);
      const pattern = isCjk ? escRe(name) : `(?<![\\p{L}\\p{N}_])${escRe(name)}(?![\\p{L}\\p{N}_])`;
      // single words match as written (so "Storage" never underlines "storage"); phrases and identifiers ignore case
      (!isCjk && /^[\p{L}\p{N}]+$/u.test(name) ? sensitive : insensitive).push([name.length, pattern]);
    }
  }
  const build = (alts, flags) => {
    alts.sort((a, b) => b[0] - a[0]);
    return alts.length ? new RegExp(alts.map((a) => a[1]).join("|"), flags) : null;
  };
  glossaryRes = [build(insensitive, "giu"), build(sensitive, "gu")].filter(Boolean);
}
function glossify(root, max = 12) {
  if (!glossaryRes.length || !root) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.parentElement.closest("code, pre, a, button, select, input, textarea, .gterm, .who, .kfoot, .tag")
      ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  const seen = new Set();
  let count = 0;
  for (const node of nodes) {
    if (count >= max) break;
    const text = node.nodeValue;
    const found = [];
    for (const re of glossaryRes) {
      re.lastIndex = 0;
      let m;
      while ((m = re.exec(text))) found.push({ index: m.index, text: m[0] });
    }
    if (!found.length) continue;
    found.sort((a, b) => a.index - b.index || b.text.length - a.text.length);
    let last = 0, frag = null;
    for (const f of found) {
      if (count >= max || f.index < last) continue; // overlaps an earlier, longer match
      const entry = glossaryIndex[f.text] || glossaryIndex[f.text.toLowerCase()];
      if (!entry || seen.has(entry.term)) continue;
      seen.add(entry.term);
      count++;
      frag ||= document.createDocumentFragment();
      frag.append(text.slice(last, f.index));
      const span = h("span", { class: "gterm", role: "link", onclick: (e) => { e.stopPropagation(); go(`#/glossary?term=${encodeURIComponent(entry.term)}`); } }, f.text);
      hoverable(span, () => [entry.term, entry.definition, entry.category]);
      frag.append(span);
      last = f.index + f.text.length;
    }
    if (frag) { frag.append(text.slice(last)); node.replaceWith(frag); }
  }
}

route(/^\/glossary$/, async (params) => {
  const state = { q: params.q || "", project: params.project || "", category: params.category || "" };
  const data = await api("/api/glossary", state);
  const refresh = () => { setParams({ ...state }); render(); };
  const rebuild = h("button", { class: "btn", type: "button", onclick: async () => {
    rebuild.disabled = true;
    const r = await post("/api/glossary/rebuild", { path: state.project || "" });
    toast(r.started ? "Claude is rebuilding the glossary…" : "Already running");
    watchJob(`glossary:${state.project || "all"}`);
  } }, state.project ? "Rebuild this project's glossary" : "Rebuild glossary");
  let debounce;
  const mode = viewMode("glossary", "cards");
  const letterOf = (e) => (e.term[0] && /\p{L}/u.test(e.term[0]) ? e.term[0].toUpperCase() : "#");
  const groups = {};
  for (const e of data.items) (groups[letterOf(e)] ||= []).push(e);
  const letters = Object.keys(groups).sort((a, b) => (a === "#") - (b === "#") || a.localeCompare(b));
  const usage = (e) => e.usage.some((u) => u.context) ? h("ul", { class: "gusage" }, e.usage.filter((u) => u.context).map((u) =>
    h("li", null, u.project_path === "__global__" ? h("b", null, "Everywhere") : h("a", { href: `#/project?path=${encodeURIComponent(u.project_path)}` }, h("b", null, String(u.project_name || "").startsWith("/") ? shortPath(u.project_name) : u.project_name)), ": ", u.context))) : null;
  const related = (e) => e.related.length ? h("div", { style: { marginTop: "8px" } }, e.related.map((r) =>
    h("a", { class: "tag", href: `#/glossary?term=${encodeURIComponent(r)}` }, r))) : null;
  const foot = (e) => h("div", { class: "gfoot" },
    e.n_sessions ? h("span", null, `${e.n_sessions} session${e.n_sessions === 1 ? "" : "s"} · ${fmtCompact(e.n_mentions)} mentions · ${fmtDate(e.first_seen)} → ${fmtDate(e.last_seen)}`) : h("span", null, "not mentioned verbatim in transcripts"),
    e.top_sessions.slice(0, 3).map((t) => h("a", { href: `#/session/${t.id}` }, (t.title || t.id.slice(0, 8)).slice(0, 48))),
    e.n_sessions ? h("a", { href: `#/search?q=${encodeURIComponent(e.term)}` }, "all mentions →") : null,
    h("a", { href: `#/map?term=${encodeURIComponent(e.term)}${MAP_HIDDEN.has(e.category) ? "&all=1" : ""}` }, "on the map →"));
  const card = (e) => h("article", { class: "card gcard", id: `g-${slugId(e.term)}` },
    h("div", { class: "ghead" },
      h("div", { class: "gname" }, h("div", { class: "gterm-title" }, e.term), e.aliases.length ? h("div", { class: "galiases" }, `also ${e.aliases.join(", ")}`) : null),
      catBadge(e.category)),
    h("div", { class: "gdef" }, e.definition || ""), usage(e), related(e), foot(e));
  const listView = () => h("section", { class: "card flush" }, localTable(data.items, [
    { key: "term", label: "Term", value: (e) => (letterOf(e) === "#" ? "￿" : "") + e.term.toLowerCase() }, // symbols last, as in the A–Z bar
    { key: "category", label: "Category", value: (e) => e.category || "other" },
    { key: "definition", label: "Definition" },
    { key: "sessions", label: "Sessions", num: true, desc: true, value: (e) => e.n_sessions || 0 },
    { key: "mentions", label: "Mentions", num: true, desc: true, value: (e) => e.n_mentions || 0 },
    { key: "last", label: "Last seen", desc: true, value: (e) => e.last_seen },
  ], (e) => expandable(h("tr", { class: "grow", id: `g-${slugId(e.term)}` },
    h("td", { class: "term-cell" }, h("div", { class: "gterm-title" }, e.term), e.aliases.length ? h("div", { class: "s" }, `also ${e.aliases.join(", ")}`) : null),
    h("td", null, catBadge(e.category)),
    h("td", { class: "def-cell" }, e.definition || ""),
    h("td", { class: "num" }, e.n_sessions ? fmtNum(e.n_sessions) : "–"),
    h("td", { class: "num" }, e.n_mentions ? fmtCompact(e.n_mentions) : "–"),
    h("td", { class: "nowrap" }, e.last_seen ? fmtDate(e.last_seen) : "–")), 6, () => [usage(e), related(e), foot(e)]),
  { sort: "term", group: { key: "term", of: letterOf, id: (l) => `gl-${l}` }, empty: "No terms match.", cls: "glossary-table" }));
  const page = h("div", null,
    h("div", { class: "page-head" }, h("div", null, h("h1", null, "Glossary"),
      h("div", { class: "sub" }, data.total ? `${fmtNum(data.items.length)} of ${fmtNum(data.total)} terms from your sessions. Hover underlined terms anywhere in Chronicle.` : "No glossary yet")),
      h("div", { class: "head-actions" }, viewToggle("glossary", mode), rebuild)),
    h("div", { class: "filters" },
      h("input", { class: "input", type: "search", placeholder: "Search terms and definitions…", value: state.q, style: { minWidth: "280px" },
        oninput: (e) => { clearTimeout(debounce); debounce = setTimeout(() => { state.q = e.target.value; refresh(); }, 300); } }),
      h("select", { onchange: (e) => { state.project = e.target.value; refresh(); } }, await projectOptions(state.project))),
    h("div", { class: "filters" },
      h("button", { type: "button", class: `chip ${!state.category ? "on" : ""}`, onclick: () => { state.category = ""; refresh(); } }, "All", h("span", { class: "count" }, data.total)),
      Object.entries(data.counts).sort((a, b) => b[1] - a[1]).map(([c, n]) =>
        h("button", { type: "button", class: `chip ${state.category === c ? "on" : ""}`, onclick: () => { state.category = c; refresh(); } }, icon(ICONS[c] ? c : "dot"), c, h("span", { class: "count" }, n)))),
    letters.length > 3 ? h("div", { class: "letters" }, letters.map((l) => h("a", { href: "#", onclick: (ev) => { ev.preventDefault(); document.getElementById(`gl-${l}`)?.scrollIntoView({ behavior: "smooth" }); } }, l))) : null,
    !data.items.length ? h("div", { class: "card empty" }, data.total ? "No terms match." : "The glossary is built by Claude from your knowledge items. Click Rebuild glossary to create it now.")
      : mode === "list" ? listView()
      : letters.map((l) => [h("h2", { class: "gletter", id: `gl-${l}` }, l), h("div", { class: "ggrid" }, groups[l].map(card))]));
  if (params.term) {
    setTimeout(() => {
      const target = document.getElementById(`g-${slugId(params.term)}`) ||
        [...document.querySelectorAll(".gcard, .grow")].find((c) => c.querySelector(".gterm-title").textContent.toLowerCase() === params.term.toLowerCase());
      if (!target) return;
      target.classList.add("focus");
      if (target.classList.contains("grow")) target.click(); // open its details
      target.scrollIntoView({ block: "center" });
    }, 50);
  }
  return page;
});
function slugId(t) { return String(t).toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "-"); }

// =====================================================================================
// Map: the glossary as a collapsible mindmap, grouped by any stack of levels (project, category, theme, agent)
// =====================================================================================
// Branch colour follows the category (fixed slots, never by rank); smaller categories share a neutral, and
// project/agent levels are neutral. Every node is labelled, so colour is never the only cue; the Glossary list is
// the table view. Terms open into the knowledge items they were distilled from and the sessions that mention them.
const MAP_HUES = { concept: 1, component: 2, tool: 3, data: 4, domain: 5, library: 6, system: 7, platform: 8 };
const MAP_HIDDEN = new Set(["file", "command"]); // hundreds of paths and commands would drown the rest
const MAP_DIMS = ["category", "theme", "project", "agent"];
const MAP_DIM_NAMES = { project: "Project", category: "Category", theme: "Theme", agent: "Agent" };
const MAP_PLURAL = { root: "branches", project: "projects", category: "categories", theme: "themes", agent: "agents", term: "terms", kitem: "items", session: "sessions" };
const MAP_PRESETS = [["category", "theme"], ["project", "category", "theme"], ["category", "project"], ["agent", "category", "theme"]];
const MAP_CAP = { root: 12, project: 10, category: 10, theme: 10, agent: 10, term: 10 }; // the rest is browsed in the side panel
const MAP_BOX = { root: 36, project: 30, agent: 30, category: 28, theme: 26, term: 22, kitem: 22, session: 22, more: 24 }; // node heights
const MAP_PITCH = { root: 46, project: 40, agent: 40, category: 38, theme: 34, term: 26, kitem: 26, session: 26, more: 32 }; // per leaf row
const MAP_GAP = 52, MAP_GROUP_GAP = 10, MAP_KNOB = 8, MAP_SEP = "\u0001";
const mapColor = (cat) => (MAP_HUES[cat] ? `var(--series-${MAP_HUES[cat]})` : "var(--muted)");
const mapDot = (t) => (t.n_sessions >= 5 ? 5 : t.n_sessions >= 2 ? 4 : 3); // dot radius: how much it was discussed
const mapNeutral = (kind) => kind === "project" || kind === "agent" || kind === "root";
const mapState = { open: new Set(["root"]), pinned: new Set(), view: null }; // survives re-renders in this tab
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

function mapLevels(params, data) {
  if (params.levels != null) {
    const picked = [...new Set(String(params.levels).split(",").filter((d) => MAP_DIMS.includes(d)))];
    if (picked.length) return picked;
  }
  if (params.by === "project") return ["project", "category", "theme"]; // links from before levels existed
  return Object.keys(data.themes || {}).length ? ["category", "theme"] : ["category"];
}

function mapTree(data, levels, withHidden, projectName) {
  const terms = data.terms.filter((t) => withHidden || !MAP_HIDDEN.has(t.category))
    .sort((a, b) => b.n_sessions - a.n_sessions || a.term.localeCompare(b.term));
  const DIMS = {
    project: { values: (t) => t.projects.map((u) => u.path), label: projectName },
    category: { values: (t) => [t.category], label: (v) => v, cat: (v) => v },
    theme: { values: (t) => [t.theme ? `${t.category}${MAP_SEP}${t.theme}` : null], label: (v) => v.split(MAP_SEP)[1], cat: (v) => v.split(MAP_SEP)[0] },
    agent: { values: (t) => (t.agents.length ? t.agents : ["unknown"]), label: (v) => (v === "unknown" ? "No linked sessions" : agentName(v)) },
  };
  const termNode = (t, prefix) => {
    const id = `${prefix}/t:${t.id}`;
    const ks = t.knowledge.map((k) => data.knowledge[k]).filter(Boolean);
    return { id, kind: "term", label: t.term, cat: t.category, term: t, children: [
      ...ks.map((k) => ({ id: `${id}/k:${k.id}`, kind: "kitem", label: k.title, cat: t.category, k, children: [] })),
      ...t.sessions.map((s) => ({ id: `${id}/s:${s.id}`, kind: "session", label: s.title || s.id.slice(0, 8), cat: t.category, session: s, children: [] })),
    ] };
  };
  function build(list, dims, prefix, cat) {
    if (!dims.length) return list.map((t) => termNode(t, prefix));
    const [dim, ...rest] = dims, D = DIMS[dim];
    const buckets = new Map();
    for (const t of list) for (const v of new Set(D.values(t))) { if (!buckets.has(v)) buckets.set(v, []); buckets.get(v).push(t); }
    if (buckets.size === 1 && buckets.has(null)) return build(list, rest, prefix, cat); // nothing to group by here
    return [...buckets]
      .sort(([va, a], [vb, b]) => (va === null) - (vb === null) || b.length - a.length || String(va).localeCompare(String(vb)))
      .map(([v, ts]) => {
        const id = `${prefix}/${dim}:${v}`;
        const own = v !== null && D.cat ? D.cat(v) : cat;
        return { id, kind: dim, value: v, label: v === null ? "Not grouped yet" : D.label(v), cat: mapNeutral(dim) ? undefined : own,
          count: ts.length, terms: ts, children: build(ts, rest, id, own) };
      });
  }
  const root = { id: "root", kind: "root", label: "Your work", count: terms.length, terms, children: build(terms, levels, "root", undefined) };
  (function link(n, parent) { n.parent = parent; n.children.forEach((c) => link(c, n)); })(root, null);
  return root;
}

function mapKids(n) {
  if (!mapState.open.has(n.id) || !n.children.length) return [];
  const cap = MAP_CAP[n.kind];
  if (!cap || n.children.length <= cap + 1) return n.children;
  // the most discussed first (a term: its first knowledge items and sessions), plus anything picked or searched for
  const quota = n.kind === "term" ? { kitem: 6, session: 4 } : null, used = { kitem: 0, session: 0 };
  const shown = n.children.filter((c, i) => mapState.pinned.has(c.id) || (quota ? used[c.kind]++ < quota[c.kind] : i < cap));
  const rest = n.children.length - shown.length;
  return rest ? [...shown, { id: `${n.id}/+more`, kind: "more", label: `+${rest} more`, cat: n.cat, of: n, parent: n, children: [] }] : shown;
}

let mapCtx;
function mapMeasure(n) { // node width; also sets the label text shown
  mapCtx ||= document.createElement("canvas").getContext("2d");
  const font = getComputedStyle(document.body).fontFamily;
  const text = (t, size, weight = 400) => { mapCtx.font = `${weight} ${size}px ${font}`; return mapCtx.measureText(t).width; };
  const max = n.kind === "kitem" || n.kind === "session" ? 58 : 44;
  n.text = n.label.length > max ? n.label.slice(0, max - 2) + "…" : n.label;
  n.countText = n.kind === "session" ? fmtDate(n.session.started_at) : n.count != null && n.kind !== "term" ? fmtNum(n.count) : "";
  const count = n.countText ? text(n.countText, 12) + 7 : 0;
  const w = n.kind === "root" ? 18 + text(n.text, 15, 600) + count + 18
    : n.kind === "project" || n.kind === "agent" ? 12 + text(n.text, 13.5, 600) + count + 14
    : n.kind === "category" ? 31 + text(n.text, 13, 500) + count + 14
    : n.kind === "theme" ? 22 + text(n.text, 13, 500) + count + 13
    : n.kind === "more" ? 11 + text(n.text, 12.5) + 11
    : n.kind === "kitem" || n.kind === "session" ? 22 + text(n.text, 12.5) + count + 6
    : 17 + text(n.text, 13, n.term.n_sessions >= 5 ? 500 : 400) + 7;
  return Math.ceil(w + (n.children.length ? MAP_KNOB : 0)); // the +/− knob sits on the right edge: keep it clear of the count
}

function mapLayout(root) {
  let y = 0, lastParent = null;
  const nodes = [], links = [];
  (function walk(n, x) {
    n.x = x;
    n.w = mapMeasure(n);
    const kids = mapKids(n);
    if (!kids.length) {
      if (lastParent && n.parent !== lastParent) y += MAP_GROUP_GAP;
      lastParent = n.parent;
      n.y = y + MAP_PITCH[n.kind] / 2;
      y += MAP_PITCH[n.kind];
    } else {
      kids.forEach((k) => { k.parent = n; walk(k, x + n.w + MAP_GAP); links.push([n, k]); });
      n.y = (kids[0].y + kids[kids.length - 1].y) / 2;
    }
    nodes.push(n);
  })(root, 0);
  return { nodes, links };
}

function mapLinkPath(p, c) { // a rounded bracket: out of the parent's knob, down a shared spine, into the child
  const x1 = p.x + p.w + MAP_KNOB, xs = c.x - 22, dy = c.y - p.y;
  if (Math.abs(dy) < 0.5) return `M${x1},${p.y}H${c.x}`;
  const sg = Math.sign(dy), r = Math.min(10, Math.abs(dy) / 2);
  return `M${x1},${p.y}H${xs - r}Q${xs},${p.y} ${xs},${p.y + sg * r}V${c.y - sg * r}Q${xs},${c.y} ${xs + r},${c.y}H${c.x}`;
}

function mapFindTerm(terms, q) {
  const s = q.trim().toLowerCase();
  if (!s) return null;
  const names = (t) => [t.term, ...t.aliases].map((x) => x.toLowerCase());
  return terms.find((t) => names(t).includes(s)) || terms.find((t) => names(t).some((x) => x.startsWith(s)))
    || terms.find((t) => names(t).some((x) => x.includes(s)));
}

const MAP_TOOL_ICONS = {
  fit: "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5",
  collapse: "M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5",
};

route(/^\/map$/, async (params) => {
  const withHidden = params.all === "1";
  const data = await api("/api/map");
  const levels = mapLevels(params, data);
  const projectsByPath = Object.fromEntries(data.projects.map((p) => [p.path, p]));
  const projectName = (path) => (path === "__global__" ? "Everywhere" : projectsByPath[path]?.label || shortPath(path));
  const tree = mapTree(data, levels, withHidden, projectName);
  const shown = tree.terms;
  const realProjects = (t) => new Set(t.projects.map((u) => u.path).filter((p) => p !== "__global__")).size;
  const themeOf = (cat, name) => (data.themes[cat] || []).find((t) => t.name === name);
  const urlState = (extra = {}) => ({ levels: levels.join(","), all: withHidden ? "1" : "", ...extra });
  const refresh = (changes) => { setParams(urlState(changes)); render(); };

  const svg = s("svg", { class: "mm-svg", role: "tree", "aria-label": "Mindmap of glossary terms" });
  const viewG = s("g"), linkG = s("g", { class: "mm-links" }), nodeG = s("g", { class: "mm-nodes" });
  viewG.append(linkG, nodeG);
  svg.append(viewG);
  const box = h("div", { class: "mm-canvas" }, svg);
  const aside = h("aside", { class: "mm-detail" });
  let layout = null, selected = null, seen = null;
  const viewKey = `${levels.join(",")}|${withHidden}`;
  const view = mapState.view && mapState.view.key === viewKey ? mapState.view : (mapState.view = { key: viewKey, k: 1, tx: 32, ty: 0, placed: false });
  const applyView = () => {
    viewG.setAttribute("transform", `translate(${view.tx},${view.ty}) scale(${view.k})`);
    box.style.backgroundSize = `${22 * view.k}px ${22 * view.k}px`; // the dot grid moves with the map
    box.style.backgroundPosition = `${view.tx}px ${view.ty}px`;
  };

  // ------------------------------------------------------------------ drawing
  function draw() {
    layout = mapLayout(tree);
    const fresh = (n) => seen && !seen.has(n.id);
    linkG.replaceChildren(...layout.links.map(([p, c]) => {
      const leaf = c.kind === "kitem" || c.kind === "session";
      const path = s("path", { d: mapLinkPath(p, c), class: `${mapNeutral(c.kind) ? "neutral" : leaf ? "leaf" : ""}${fresh(c) ? " enter" : ""}` });
      if (c.cat && !mapNeutral(c.kind)) path.style.setProperty("--c", mapColor(c.cat));
      return path;
    }));
    nodeG.replaceChildren(...layout.nodes.map((n) => nodeEl(n, fresh(n))));
    seen = new Set(layout.nodes.map((n) => n.id));
    applyView();
  }

  function nodeEl(n, isNew) {
    const hasKids = n.children.length > 0, open = mapState.open.has(n.id) && hasKids;
    const hgt = MAP_BOX[n.kind];
    const g = s("g", { class: `mm-node ${n.kind}${n.value === null ? " ungrouped" : ""}${selected === n.id ? " sel" : ""}${isNew ? " enter" : ""}`,
      transform: `translate(${n.x},${n.y})`, role: "treeitem", tabindex: "0", "aria-label": n.label,
      "aria-expanded": hasKids ? String(open) : null, "aria-selected": selected === n.id ? "true" : null });
    if (n.cat) g.style.setProperty("--c", mapColor(n.cat));
    const flat = ["term", "kitem", "session"].includes(n.kind);
    const rx = n.kind === "root" ? hgt / 2 : flat ? 6 : 8;
    g.append(s("rect", { class: "mm-box", x: flat ? -6 : 0, y: -hgt / 2, width: n.w + (flat ? 8 : 0), height: hgt, rx }));
    const base = n.kind === "root" ? 5.5 : 4.5;
    const glyph = (name, x, size) => {
      const ic = icon(ICONS[name] ? name : "dot", "mm-icon");
      setAttrs(ic, { x, y: -size / 2, width: size, height: size });
      return ic;
    };
    if (n.kind === "category") g.append(glyph(n.cat, 10, 14));
    if (n.kind === "theme") g.append(s("circle", { class: "mm-tdot", cx: 11, cy: 0, r: 4 }));
    if (n.kind === "term") g.append(s("circle", { class: "mm-dot", cx: 6, cy: 0, r: mapDot(n.term) }));
    if (n.kind === "kitem") g.append(glyph(KIND[n.k.kind] ? n.k.kind : "dot", 0, 14));
    if (n.kind === "session") g.append(glyph("sessions", 0, 14));
    const tx = { root: 18, project: 12, agent: 12, category: 31, theme: 22, more: 11, term: 17, kitem: 20, session: 20 }[n.kind];
    g.append(s("text", { x: tx, y: base, class: n.kind === "term" && n.term.n_sessions >= 5 ? "strong" : "" },
      n.text, n.countText ? s("tspan", { class: "mm-count", dx: 7 }, n.countText) : null));
    if (hasKids) {
      g.append(s("g", { class: "mm-knob", transform: `translate(${n.w},0)` },
        s("circle", { r: MAP_KNOB }), s("path", { d: open ? "M-3.5,0H3.5" : "M-3.5,0H3.5M0,-3.5V3.5" })));
    }
    g.append(s("rect", { class: "mm-hit", x: -6, y: -hgt / 2 - 2, width: n.w + (hasKids ? MAP_KNOB + 8 : 10), height: hgt + 4 }));
    hoverable(g, () => tipFor(n, open), { focusable: false });
    g.addEventListener("click", (e) => { if (!dragMoved) activate(n); e.stopPropagation(); });
    g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activate(n); } });
    return g;
  }
  function tipFor(n, open) {
    const act = n.children.length ? ` · click to ${open ? "close" : "open"}` : "";
    if (n.kind === "term") {
      const t = n.term;
      return [t.term, t.definition, `${t.category}${t.theme ? ` · ${t.theme}` : ""} · ${t.n_sessions ? `${t.n_sessions} session${t.n_sessions === 1 ? "" : "s"}` : "not mentioned verbatim"}`];
    }
    if (n.kind === "more") return [n.label, "Browse and filter them in the side panel"];
    if (n.kind === "theme") return [n.label, themeOf(n.cat, n.label)?.description || "", `${fmtNum(n.count)} terms${act}`];
    if (n.kind === "kitem") return [n.k.title, `${kindLabel(n.k.kind)} · ${agentName(n.k.agent)}`];
    if (n.kind === "session") return [n.label, `${fmtDate(n.session.started_at)} · ${agentName(n.session.agent)} · ${projectName(n.session.project_path)}`];
    if (n.kind === "project") {
      const p = projectsByPath[n.value];
      return [n.label, `${fmtNum(n.count)} terms${p?.sessions ? ` · ${fmtNum(p.sessions)} sessions` : ""}${act}`];
    }
    return [n.label, `${fmtNum(n.count)} terms${act}`];
  }

  // ------------------------------------------------------------------ camera
  let anim = 0;
  function animateTo(k, tx, ty) {
    const id = ++anim, from = { k: view.k, tx: view.tx, ty: view.ty }, t0 = performance.now(), ms = reducedMotion() ? 0 : 320;
    const step = (now) => {
      if (id !== anim) return; // the user took over
      const p = ms ? Math.min(1, (now - t0) / ms) : 1, e = 1 - Math.pow(1 - p, 3);
      view.k = from.k + (k - from.k) * e;
      view.tx = from.tx + (tx - from.tx) * e;
      view.ty = from.ty + (ty - from.ty) * e;
      applyView();
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
  function ensureVisible(n) { // after opening a branch, glide just enough to show it
    const sub = [];
    (function walk(m) { sub.push(m); mapKids(m).forEach(walk); })(n);
    const W = box.clientWidth, H = box.clientHeight, pad = 28, k = view.k;
    const minY = Math.min(...sub.map((m) => m.y - 20)), maxY = Math.max(...sub.map((m) => m.y + 20));
    const maxX = Math.max(...sub.map((m) => m.x + m.w + 24));
    let { tx, ty } = view;
    if ((maxY - minY) * k > H - 2 * pad) ty = H / 2 - n.y * k;
    else if (ty + maxY * k > H - pad) ty = H - pad - maxY * k;
    else if (ty + minY * k < pad) ty = pad - minY * k;
    const over = tx + maxX * k - (W - pad);
    if (over > 0) tx -= Math.min(over, tx + n.x * k - pad);
    if (tx !== view.tx || ty !== view.ty) animateTo(k, tx, ty);
  }
  function centerOn(n) { animateTo(view.k, box.clientWidth * 0.4 - (n.x + n.w / 2) * view.k, box.clientHeight / 2 - n.y * view.k); }
  function fit() {
    if (!layout) return;
    const xs = layout.nodes.map((n) => n.x + n.w + 20), ys = layout.nodes.map((n) => n.y);
    const w = Math.max(...xs) + 24, top = Math.min(...ys) - 30, hgt = Math.max(...ys) - top + 30;
    const k = Math.max(0.25, Math.min(1.2, (box.clientWidth - 48) / w, (box.clientHeight - 90) / hgt));
    animateTo(k, 28, 30 + (box.clientHeight - 30 - hgt * k) / 2 - top * k);
  }
  function zoom(f, cx = box.clientWidth / 2, cy = box.clientHeight / 2) {
    anim++;
    const k = Math.max(0.2, Math.min(2.5, view.k * f));
    view.tx = cx - (cx - view.tx) * (k / view.k);
    view.ty = cy - (cy - view.ty) * (k / view.k);
    view.k = k;
    applyView();
  }

  // ------------------------------------------------------------------ interaction
  function activate(n) {
    if (n.kind === "more") { selected = n.id; draw(); showMore(n); return; }
    const opening = n.children.length && !mapState.open.has(n.id);
    if (n.children.length) {
      const before = n.y;
      mapState.open.has(n.id) ? mapState.open.delete(n.id) : mapState.open.add(n.id);
      selected = n.id;
      draw();
      anim++;
      view.ty += (before - n.y) * view.k; // the clicked node stays under the pointer while the tree re-flows
      applyView();
      if (opening) ensureVisible(n);
    }
    select(n);
  }
  function select(n) {
    selected = n.id;
    draw();
    showDetail(n);
    setParams(urlState({ term: n.kind === "term" ? n.term.term : "" }));
  }
  function openPath(node) { // open every ancestor, pinning the node wherever a branch is capped
    for (let c = node, p = node.parent; p; c = p, p = p.parent) {
      mapState.open.add(p.id);
      if (MAP_CAP[p.kind] && p.children.indexOf(c) >= MAP_CAP[p.kind]) mapState.pinned.add(c.id);
    }
  }
  function reveal(t) { // a term's first place in the tree: open the path to it, centre and select it
    let node = null;
    (function find(n) { if (!node) { if (n.kind === "term" && n.term.id === t.id) node = n; else n.children.forEach(find); } })(tree);
    if (!node) { toast(`${t.term} is hidden by the current filter`); return; }
    openPath(node);
    select(node);
    centerOn(node);
  }
  function jumpTo(node) { openPath(node); mapState.open.add(node.id); select(node); ensureVisible(node); }

  // pan with drag or two-finger scroll, zoom with pinch / ctrl+wheel
  let drag = null, dragMoved = false;
  svg.addEventListener("pointerdown", (e) => { drag = { x: e.clientX, y: e.clientY, tx: view.tx, ty: view.ty }; dragMoved = false; });
  svg.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!dragMoved && Math.hypot(dx, dy) < 4) return;
    if (!dragMoved) { dragMoved = true; anim++; svg.setPointerCapture(e.pointerId); box.classList.add("dragging"); hideTip(); }
    view.tx = drag.tx + dx;
    view.ty = drag.ty + dy;
    applyView();
  });
  const endDrag = () => { drag = null; box.classList.remove("dragging"); setTimeout(() => (dragMoved = false)); };
  svg.addEventListener("pointerup", endDrag);
  svg.addEventListener("pointercancel", endDrag);
  svg.addEventListener("wheel", (e) => {
    e.preventDefault();
    anim++;
    const r = svg.getBoundingClientRect();
    if (e.ctrlKey || e.metaKey) zoom(Math.exp(-e.deltaY * 0.01), e.clientX - r.left, e.clientY - r.top);
    else { view.tx -= e.deltaX; view.ty -= e.deltaY; applyView(); }
  }, { passive: false });

  // ------------------------------------------------------------------ details
  const termChip = (t) => {
    const b = h("button", { type: "button", class: "mm-tchip", onclick: () => reveal(t), title: t.definition || "" },
      h("i", { class: "mm-cdot" }), t.term);
    b.style.setProperty("--c", mapColor(t.category));
    return b;
  };
  const relatedChip = (name) => {
    const t = mapFindTerm(shown, name);
    return t ? termChip(t) : h("span", { class: "mm-tchip off", title: "hidden by the current filter" }, name);
  };
  const catLabel = (cat) => {
    const e = h("span", { class: "mm-cat" }, icon(ICONS[cat] ? cat : "dot"), cat);
    e.style.setProperty("--c", mapColor(cat));
    return e;
  };
  const neutralLabel = (iconName, text) => h("span", { class: "mm-cat neutral" }, icon(iconName), text);
  const chipsOf = (terms, n = 16) => h("div", { class: "mm-chips" }, terms.slice(0, n).map(termChip));
  const closeBtn = () => h("button", { class: "icon-btn mm-close", type: "button", "aria-label": "Close details",
    onclick: () => { selected = null; draw(); aside.replaceChildren(...overview()); setParams(urlState()); } }, icon("x"));
  const where = (n) => { // "in concept › Auth & identity" for the groups above a node
    const trail = [];
    for (let p = n.parent; p && p.kind !== "root"; p = p.parent) trail.unshift(p.label);
    return trail.length ? `In ${trail.join(" › ")}. ` : "";
  };
  function showDetail(n) {
    let body;
    if (n.kind === "term") {
      const t = n.term;
      const ks = t.knowledge.map((id) => data.knowledge[id]).filter(Boolean);
      body = [
        catLabel(t.category), t.theme ? h("span", { class: "mm-theme-tag" }, t.theme) : null,
        h("h3", null, t.term),
        t.aliases.length ? h("div", { class: "mm-aliases" }, `also ${t.aliases.slice(0, 4).join(", ")}${t.aliases.length > 4 ? ` +${t.aliases.length - 4} more` : ""}`) : null,
        h("p", { class: "mm-def gloss" }, t.definition || ""),
        h("div", { class: "mm-stats" },
          t.n_sessions ? [h("span", null, h("b", null, fmtNum(t.n_sessions)), ` session${t.n_sessions === 1 ? "" : "s"}`),
            h("span", null, h("b", null, fmtCompact(t.n_mentions)), " mentions"),
            h("span", null, `${fmtDate(t.first_seen)} → ${fmtDate(t.last_seen)}`)] : h("span", null, "not mentioned verbatim in transcripts"),
          t.agents.length ? h("span", null, t.agents.map(agentName).join(", ")) : null),
        t.projects.length ? [h("h4", null, "Where it is used"), h("div", { class: "mm-uses" }, t.projects.map((u) => h("div", { class: "mm-use" },
          u.path === "__global__" ? h("b", null, "Everywhere") : h("a", { href: `#/project?path=${encodeURIComponent(u.path)}` }, projectName(u.path)),
          u.context ? h("div", { class: "gloss" }, u.context) : null)))] : null,
        t.related.length ? [h("h4", null, "Related"), h("div", { class: "mm-chips" }, t.related.map(relatedChip))] : null,
        ks.length ? [h("h4", null, `Learned from · ${ks.length}`), h("ul", { class: "mm-klist" }, ks.slice(0, 8).map((k) => h("li", null, kindChip(k.kind),
          k.session_id ? h("a", { href: `#/session/${k.session_id}` }, k.title) : h("span", null, k.title)))),
          ks.length > 8 ? h("a", { class: "mm-more", href: `#/knowledge?q=${encodeURIComponent(t.term)}` }, `${ks.length - 8} more in Knowledge →`) : null] : null,
        t.sessions.length ? [h("h4", null, "Mentioned most in"), h("ul", { class: "mm-klist" }, t.sessions.map((x) => h("li", null,
          h("span", { class: "mm-date" }, fmtDate(x.started_at)), h("a", { href: `#/session/${x.id}` }, x.title || x.id.slice(0, 8)))))] : null,
        h("div", { class: "mm-links-row" },
          h("a", { class: "btn small", href: `#/glossary?term=${encodeURIComponent(t.term)}` }, "Glossary entry"),
          t.n_sessions ? h("a", { class: "btn small", href: `#/search?q=${encodeURIComponent(t.term)}` }, "All mentions") : null),
      ];
    } else if (n.kind === "project") {
      const p = projectsByPath[n.value] || { path: n.value, label: n.label, knowledge: {} };
      const kinds = Object.entries(p.knowledge || {}).sort((a, b) => b[1] - a[1]);
      body = [
        neutralLabel("projects", p.path === "__global__" ? "cross-project" : "project"),
        h("h3", null, n.label),
        h("p", { class: "mm-def" }, where(n) + (p.path === "__global__" ? "Terms Claude found across all your projects." : "")),
        h("div", { class: "hero-facts" }, p.sessions ? [fact("sessions", fmtNum(p.sessions)), fact("active", fmtHours(p.active_s)), fact("last session", fmtDate(p.last))] : null, fact("terms", fmtNum(n.count))),
        kinds.length ? [h("h4", null, "Knowledge"), h("div", { class: "mm-chips" }, kinds.map(([k, c]) => h("span", { class: "kind-chip" }, icon(KIND[k] ? k : "dot"), `${kindLabel(k)} ${c}`)))] : null,
        h("h4", null, "Most discussed here"), chipsOf(n.terms, 12),
        p.path !== "__global__" ? h("div", { class: "mm-links-row" }, h("a", { class: "btn small", href: `#/project?path=${encodeURIComponent(p.path)}` }, "Open project")) : null,
      ];
    } else if (n.kind === "category") {
      const themes = (data.themes[n.cat] || []);
      const themeKids = n.children.filter((c) => c.kind === "theme");
      body = [
        catLabel(n.cat),
        h("h3", null, `${fmtNum(n.count)} ${n.cat} terms`),
        h("p", { class: "mm-def" }, where(n) + "Most discussed first."),
        themes.length ? [h("h4", null, `Themes · ${themes.length}`), h("div", { class: "mm-themes" }, themes.map((th) => {
          const kid = themeKids.find((c) => c.label === th.name);
          return h(kid ? "button" : "div", { class: "mm-theme", type: kid ? "button" : null, onclick: kid ? () => jumpTo(kid) : null },
            h("span", { class: "mm-theme-name" }, th.name, h("span", { class: "mm-count-inline" }, kid ? fmtNum(kid.count) : fmtNum(th.n_terms))),
            th.description ? h("span", { class: "mm-theme-desc" }, th.description) : null);
        }))] : null,
        h("h4", null, "Most discussed"), chipsOf(n.terms),
        h("div", { class: "mm-links-row" }, h("a", { class: "btn small", href: `#/glossary?category=${encodeURIComponent(n.cat)}` }, "Show as a list")),
      ];
    } else if (n.kind === "theme") {
      const th = n.value !== null ? themeOf(n.cat, n.label) : null;
      body = [
        catLabel(n.cat),
        h("h3", null, n.label),
        h("p", { class: "mm-def" }, n.value === null ? "Terms added since Claude last grouped this category; they are grouped on the next run." : th?.description || ""),
        h("p", { class: "mm-def muted" }, `${where(n)}${fmtNum(n.count)} terms, most discussed first.`),
        chipsOf(n.terms, 24),
      ];
    } else if (n.kind === "agent") {
      body = [
        neutralLabel("sessions", "agent"),
        h("h3", null, n.label),
        h("p", { class: "mm-def" }, `${where(n)}${fmtNum(n.count)} terms learned from ${n.label} sessions.`),
        h("h4", null, "Most discussed"), chipsOf(n.terms),
      ];
    } else if (n.kind === "kitem") {
      const k = n.k;
      body = [
        kindChip(k.kind),
        h("h3", null, k.title),
        h("p", { class: "mm-def gloss" }, k.body || ""),
        h("div", { class: "mm-stats" }, h("span", null, projectName(k.project_path)), h("span", null, agentName(k.agent)),
          h("span", null, `about ${n.parent.label}`)),
        h("div", { class: "mm-links-row" },
          k.session_id ? h("a", { class: "btn small", href: `#/session/${k.session_id}` }, "Open session") : null,
          h("a", { class: "btn small", href: `#/knowledge?q=${encodeURIComponent(k.title)}` }, "In Knowledge")),
      ];
    } else if (n.kind === "session") {
      const x = n.session;
      body = [
        neutralLabel("sessions", "session"),
        h("h3", null, x.title || x.id.slice(0, 8)),
        h("div", { class: "mm-stats" }, h("span", null, fmtDT(x.started_at)), h("span", null, agentName(x.agent)), h("span", null, projectName(x.project_path))),
        h("p", { class: "mm-def muted" }, `One of the sessions that mention ${n.parent.label} most.`),
        h("div", { class: "mm-links-row" }, h("a", { class: "btn small", href: `#/session/${x.id}` }, "Open session")),
      ];
    } else {
      aside.replaceChildren(...overview());
      return;
    }
    aside.replaceChildren(closeBtn(), ...[body].flat(Infinity).filter(Boolean));
    aside.scrollTop = 0;
    aside.querySelectorAll(".gloss").forEach((el) => glossify(el)); // not the heading: it is the term itself
  }
  function showMore(more) { // the rest of a big branch, as a filterable list; picking one pins it onto the map
    const parent = more.of, drawn = new Set(mapKids(parent));
    const hidden = parent.children.filter((c) => !drawn.has(c));
    const what = MAP_PLURAL[hidden[0]?.kind] || "items";
    const sub = (c) => c.kind === "term" ? (c.term.n_sessions ? `${fmtNum(c.term.n_sessions)} sess.` : "")
      : c.kind === "kitem" ? kindLabel(c.k.kind) : c.kind === "session" ? fmtDate(c.session.started_at) : `${fmtNum(c.count)} terms`;
    const hay = (c) => [c.label, ...(c.term ? [...c.term.aliases, c.term.definition || ""] : []), c.k?.body || ""].join(" ").toLowerCase();
    const pick = (c) => {
      mapState.pinned.add(c.id);
      if (c.children.length && c.kind !== "term") mapState.open.add(c.id);
      select(c);
      if (c.kind === "term") centerOn(c); else ensureVisible(c);
    };
    const list = h("ul", { class: "mm-pick" });
    const fill = (q) => {
      const words = q.toLowerCase().split(/\s+/).filter(Boolean);
      const named = (c) => words.every((w) => [c.label, ...(c.term?.aliases || [])].join(" ").toLowerCase().includes(w));
      const rows = hidden.filter((c) => words.every((w) => hay(c).includes(w)))
        .sort((a, b) => named(b) - named(a)); // name matches before definition matches (stable: most discussed first)
      list.replaceChildren(...rows.map((c) => {
        const b = h("button", { type: "button", onclick: () => pick(c), title: c.term?.definition || "" },
          h("i", { class: "mm-cdot" }), h("span", { class: "mm-pick-label" }, c.label), h("span", { class: "mm-pick-sub" }, sub(c)));
        if (c.cat && !mapNeutral(c.kind)) b.style.setProperty("--c", mapColor(c.cat));
        return h("li", null, b);
      }));
      if (!rows.length) list.append(h("li", { class: "mm-pick-none" }, "Nothing matches."));
    };
    const filter = h("input", { class: "input mm-pick-filter", type: "search", placeholder: `Filter ${hidden.length} ${what}…`,
      oninput: (e) => fill(e.target.value),
      onkeydown: (e) => { if (e.key === "Enter") list.querySelector("button")?.click(); } });
    fill("");
    aside.replaceChildren(closeBtn(),
      parent.cat && !mapNeutral(parent.kind) ? catLabel(parent.cat) : neutralLabel("projects", MAP_PLURAL[parent.kind] || "branch"),
      h("h3", null, `${fmtNum(hidden.length)} more ${what}`),
      h("p", { class: "mm-def" }, `${parent.kind === "root" ? "" : `In ${parent.label}. `}Most discussed first; pick one to add it to the map.`),
      filter, list);
    aside.scrollTop = 0;
    filter.focus({ preventScroll: true });
  }
  function themesNote() {
    const due = (data.themes_due || []).filter((c) => withHidden || !MAP_HIDDEN.has(c));
    const have = Object.keys(data.themes || {}).length > 0;
    if (!due.length) return have && !levels.includes("theme")
      ? h("p", { class: "mm-tip" }, "Claude has grouped the big categories into themes: add a Theme level to see them.") : null;
    const btn = h("button", { type: "button", class: "btn small primary", onclick: async () => {
      btn.disabled = true;
      const r = await post("/api/map/themes", {});
      toast(r.started ? "Claude is grouping categories into themes…" : "Already running");
      watchJob("themes");
    } }, have ? "Regroup with Claude" : "Group with Claude");
    return h("div", { class: "mm-note" },
      h("b", null, have ? `${due.length} categor${due.length === 1 ? "y has" : "ies have"} changed since grouping` : "Group big categories into themes"),
      h("p", null, `Claude splits each category with 25+ terms into named themes, so no branch is a long list. One call per category (${due.join(", ")}).`),
      btn);
  }
  function overview() {
    const sharedTerms = shown.filter((t) => realProjects(t) > 1).sort((a, b) => realProjects(b) - realProjects(a) || b.n_sessions - a.n_sessions).slice(0, 10);
    const cats = new Set(shown.map((t) => t.category)).size;
    const presetLabel = (p) => p.map((d) => MAP_DIM_NAMES[d]).join(" › ");
    return [
      h("h3", null, "Your map"),
      h("div", { class: "hero-facts" }, fact("terms", fmtNum(tree.count)), fact("projects", fmtNum(data.projects.filter((p) => p.path !== "__global__").length)),
        fact("categories", fmtNum(cats)), fact("themes", fmtNum(Object.values(data.themes || {}).reduce((a, l) => a + l.length, 0)))),
      themesNote(),
      h("h4", null, "Views"), h("div", { class: "mm-chips" }, MAP_PRESETS.map((p) => h("button", { type: "button",
        class: `mm-tchip preset${p.join(",") === levels.join(",") ? " on" : ""}`, onclick: () => refresh({ levels: p.join(","), term: "" }) }, presetLabel(p)))),
      sharedTerms.length ? [h("h4", null, "Shared by the most projects"), chipsOf(sharedTerms, 10)] : null,
      h("h4", null, "Most discussed"), chipsOf(shown, 10),
      h("p", { class: "mm-tip" }, "Click a node to open it; terms open into the knowledge and sessions behind them. Drag or scroll to move; pinch or ⌘-scroll to zoom.",
        withHidden ? null : " File names and commands are hidden."),
    ].flat(Infinity).filter(Boolean);
  }
  aside.append(...overview());

  // ------------------------------------------------------------------ page
  function levelBar() {
    const set = (next) => refresh({ levels: next.join(","), term: "" });
    const choose = (value, i) => h("select", { class: "mm-level", "aria-label": `Level ${i + 1}`, onchange: (e) => {
      const next = [...levels];
      if (e.target.value) next[i] = e.target.value; else next.splice(i, 1);
      set(next);
    } }, MAP_DIMS.filter((d) => d === value || !levels.includes(d)).map((d) => h("option", { value: d, selected: d === value }, MAP_DIM_NAMES[d])),
      levels.length > 1 ? h("option", { value: "" }, "Remove") : null);
    const spare = MAP_DIMS.filter((d) => !levels.includes(d));
    return h("div", { class: "mm-levels" }, h("span", { class: "mm-levels-label" }, "Group by"),
      levels.map((d, i) => [i ? h("span", { class: "mm-sep" }, "›") : null, choose(d, i)]),
      spare.length ? h("select", { class: "mm-level add", "aria-label": "Add a level", onchange: (e) => e.target.value && set([...levels, e.target.value]) },
        h("option", { value: "", selected: true }, "+ level"), spare.map((d) => h("option", { value: d }, MAP_DIM_NAMES[d]))) : null,
      h("span", { class: "mm-sep" }, "›"), h("span", { class: "mm-levels-end" }, "terms"));
  }
  const search = h("input", { class: "input mm-search", type: "search", placeholder: "Find a term…", list: "mm-terms",
    onchange: (e) => { const t = mapFindTerm(shown, e.target.value); if (t) { reveal(t); e.target.value = ""; } else if (e.target.value) toast("No such term"); } });
  const datalist = h("datalist", { id: "mm-terms" }, shown.map((t) => h("option", { value: t.term })));
  const toolBtn = (label, content, onclick) => h("button", { type: "button", title: label, "aria-label": label, onclick }, content);
  const toolIcon = (d) => s("svg", { viewBox: "0 0 24 24", class: "icon", "aria-hidden": "true" }, s("path", { d }));
  const legend = h("div", { class: "mm-legend" },
    [...Object.keys(MAP_HUES), "other"].map((c) => { const e = h("span", null, h("i", { class: "mm-cdot" }), c); e.style.setProperty("--c", mapColor(c)); return e; }),
    h("span", { class: "mm-sizes", title: "Dot size: sessions that mention the term" }, h("i", { class: "d1" }), h("i", { class: "d2" }), h("i", { class: "d3" }), "sessions"));
  const tools = h("div", { class: "mm-tools" },
    toolBtn("Zoom out", "−", () => zoom(1 / 1.25)), toolBtn("Zoom in", "+", () => zoom(1.25)),
    toolBtn("Fit to screen", toolIcon(MAP_TOOL_ICONS.fit), fit),
    toolBtn("Collapse all", toolIcon(MAP_TOOL_ICONS.collapse), () => { mapState.open = new Set(["root"]); mapState.pinned.clear(); selected = null; draw(); fit(); aside.replaceChildren(...overview()); }));
  box.append(levelBar(), legend, tools);
  const page = h("div", { class: "mm-page" },
    h("div", { class: "page-head" },
      h("div", null, h("h1", null, "Map"),
        h("div", { class: "sub" }, data.terms.length ? `Your glossary as a mindmap: ${fmtNum(tree.count)} terms across ${fmtNum(data.projects.filter((p) => p.path !== "__global__").length)} projects.` : "No glossary yet")),
      h("div", { class: "head-actions" },
        h("button", { type: "button", class: `chip ${withHidden ? "on" : ""}`, "aria-pressed": String(withHidden), onclick: () => refresh({ all: withHidden ? "" : "1" }) }, "Files & commands"),
        search, datalist,
        h("a", { class: "btn", href: "#/glossary" }, "Glossary list"))),
    !data.terms.length ? h("div", { class: "card empty" }, "The map is drawn from the glossary. Build it on the Glossary page first.")
      : h("section", { class: "card flush mm-card" }, box, aside));

  if (data.terms.length) {
    const ro = new ResizeObserver(() => {
      if (!box.clientWidth) return;
      if (!view.placed) { view.placed = true; draw(); view.tx = 32; view.ty = box.clientHeight / 2 - tree.y; applyView(); }
      else draw();
      if (params.term && !selected) { const t = mapFindTerm(shown, params.term); if (t) reveal(t); }
    });
    ro.observe(box);
  }
  return page;
});

// =====================================================================================
// Sources: which agents are connected
// =====================================================================================
const srcOpen = new Set(); // rows the user opened; kept across re-renders (connect, disconnect, import)
let srcTouched = false;
function srcRow(key, summary, body, { open = false } = {}) { // one expandable row of a Sources list
  const d = h("details", { class: "src-row", open: srcTouched ? srcOpen.has(key) : open },
    h("summary", null, h("span", { class: "chev", "aria-hidden": "true" }, "›"), summary), h("div", { class: "src-body" }, body));
  if (!srcTouched && open) srcOpen.add(key);
  d.addEventListener("toggle", () => { srcTouched = true; if (d.open) srcOpen.add(key); else srcOpen.delete(key); });
  return d;
}
const inSummary = (fn) => (e) => { e.preventDefault(); e.stopPropagation(); fn(e); }; // a button in a row's summary does not toggle it
route(/^\/sources$/, async () => {
  const [sources, clients, imports] = await Promise.all([api("/api/connectors"), api("/api/mcp-clients"), api("/api/imports")]);
  const formats = Object.entries(imports).map(([key, f]) => ({ key, ...f }));
  const lastOf = (f) => f.last_import;
  const picker = h("input", { type: "file", accept: ".zip,.json,application/zip", hidden: true, onchange: async () => {
    const file = picker.files[0];
    if (!file) return;
    importBtn.disabled = true; importBtn.textContent = `Uploading ${fmtCompact(file.size)}B…`;
    const res = await fetch("/api/import", { method: "POST", headers: { "X-Chronicle": "1", "Content-Type": "application/octet-stream", "X-Filename": encodeURIComponent(file.name) }, body: file });
    const r = await res.json().catch(() => ({}));
    importBtn.disabled = false; importBtn.textContent = "Import export…"; picker.value = "";
    if (!r.started) { toast(r.error || "An import is already running"); return; }
    toast("Importing chats…", 5000);
    watchJob("import");
  } });
  const importBtn = h("button", { class: "btn primary small", type: "button", onclick: () => picker.click() }, "Import export…");
  const stat = (n, label) => h("span", null, h("b", null, typeof n === "number" ? fmtNum(n) : n), ` ${label}`);
  const badge = (cls, text) => h("span", { class: `badge ${cls}` }, h("span", { class: "sdot" }), text);

  // ---- coding agents
  const agentRow = (c) => {
    const issues = c.checks.filter((k) => k.ok === false && !k.optional);
    const state = c.connected ? (issues.length ? ["warning", `${issues.length} issue${issues.length === 1 ? "" : "s"}`] : ["good", "Connected"])
      : c.detected ? ["warning", "Not connected"] : ["", "Not installed"];
    const connect = async (e) => {
      e.target.disabled = true; e.target.textContent = "Connecting…";
      const r = await post(`/api/connectors/${c.name}/connect`);
      toast((r.actions || [r.error]).join(" · ") + (r.sync_started ? " · syncing now" : ""), 7000);
      if (r.sync_started) watchJob("sync");
      render();
    };
    const action = c.connected
      ? h("button", { class: "btn small danger", type: "button", onclick: async (e) => {
          if (!confirm(`Stop recording ${c.label}? Recorded sessions stay in the vault.`)) return;
          e.target.disabled = true;
          const r = await post(`/api/connectors/${c.name}/disconnect`);
          toast((r.actions || [r.error]).join(" · "), 6000);
          render();
        } }, "Disconnect")
      : h("button", { class: "btn small primary", type: "button", disabled: !c.detected, onclick: connect }, `Connect ${c.label}`);
    const summary = [
      h("span", { class: `src-dot a-${c.name}`, "aria-hidden": "true" }),
      h("span", { class: "src-title" }, h("b", null, c.label), h("small", null, [c.vendor, c.version].filter(Boolean).join(" · "))),
      h("span", { class: "src-sum" }, c.connected || c.recorded.sessions
        ? [stat(c.recorded.sessions, "recorded"), h("span", null, "last ", h("b", null, c.recorded.last_session ? ago(c.recorded.last_session) : "never"))]
        : h("span", null, c.detected ? "found on this Mac" : "")),
      !c.connected && c.detected ? h("button", { class: "btn small primary", type: "button", onclick: inSummary(connect) }, "Connect") : badge(state[0], state[1])];
    const body = [
      h("div", { class: "src-stats" },
        stat(c.on_disk, c.on_disk_label || "on disk"), stat(c.recorded.sessions, "recorded"), stat(c.recorded.analyzed, "analyzed"),
        c.recovered ? stat(c.recovered, c.name === "codex" ? "Claude sessions recovered" : "recovered") : null,
        c.binary ? h("span", { class: "muted" }, shortPath(c.binary)) : null),
      h("div", { class: "checks" }, c.checks.map((k) => h("div", { class: "check" },
        h("span", { class: `mark ${k.ok ? "ok" : k.ok === null || k.optional ? "na" : "no"}` }, k.ok ? "✓" : k.ok === null || k.optional ? "–" : "✗"),
        h("div", null, h("div", null, k.label), h("div", { class: "d" }, k.detail))))),
      c.notes.length ? h("div", { class: "src-note" }, c.notes.join(" · ")) : null,
      h("div", { class: "src-foot" }, h("span", { class: "muted" }, `Recording: ${c.recording}`),
        h("div", { class: "src-actions" }, c.recorded.sessions ? h("a", { class: "btn small", href: `#/sessions?agent=${c.agent || c.name}` }, "Sessions") : null, action))];
    return srcRow(`agent:${c.name}`, summary, body, { open: issues.length > 0 && c.connected });
  };
  const connected = sources.filter((c) => c.connected).length;

  // ---- chat exports
  const HOW = { "claude-ai": "claude.ai › Settings › Privacy › Export data", chatgpt: "ChatGPT › Settings › Data controls › Export data" };
  const formatRow = (f) => {
    const last = lastOf(f);
    const summary = [
      h("span", { class: `src-dot a-${f.agent}`, "aria-hidden": "true" }),
      h("span", { class: "src-title" }, h("b", null, f.label), h("small", null, "from a data export")),
      h("span", { class: "src-sum" }, f.sessions ? [stat(f.sessions, "chats"), h("span", null, "imported ", h("b", null, last ? ago(last.at) : "never"))] : h("span", null, "nothing imported yet")),
      f.sessions ? badge("good", "Imported") : badge("", "Not imported")];
    const body = [
      h("div", { class: "src-stats" }, stat(f.sessions, "chats"), stat(f.analyzed, "analyzed"),
        last ? h("span", { class: "muted" }, `last: ${last.file}, ${fmtNum(last.new)} new, ${fmtNum(last.updated)} updated`) : null),
      h("div", { class: "src-note" }, "Export from ", h("b", null, HOW[f.agent] || f.label), "; the email's link downloads a .zip to import here or with ",
        h("code", null, "chronicle import <zip>"), ". Import newer exports any time: only new and changed chats are added."),
      h("div", { class: "src-foot" }, h("span", { class: "muted" }, "Not analyzed automatically: tick the chats to analyze in the Sessions list and choose Analyze."),
        h("div", { class: "src-actions" }, f.sessions ? h("a", { class: "btn small", href: `#/sessions?agent=${f.agent}` }, "Sessions") : null,
          f.sessions > f.analyzed ? h("a", { class: "btn small primary", href: `#/sessions?agent=${f.agent}&status=skipped` }, "Pick chats to analyze") : null))];
    return srcRow(`chat:${f.key}`, summary, body);
  };

  // ---- other MCP clients: nothing to expand, one line each
  const clientRow = (c) => {
    const btn = h("button", { class: `btn small${c.registered ? "" : " primary"}`, type: "button", disabled: !c.registered && !c.detected,
      onclick: async () => {
        btn.disabled = true;
        const r = await post(`/api/connectors/${c.name}/${c.registered ? "disconnect" : "connect"}`);
        toast((r.actions || [r.error]).join(" · "), 7000);
        render();
      } }, c.registered ? "Remove" : "Add");
    const state = c.registered ? ["good", "Added"] : c.detected ? ["", "Detected"] : ["", "Not installed"];
    return h("div", { class: "src-row flat" }, h("div", { class: "src-line" },
      h("span", { class: "chev", "aria-hidden": "true" }), h("span", { "aria-hidden": "true" }),
      h("span", { class: "src-title" }, h("b", null, c.label), h("small", null, `${c.vendor} · ${shortPath(c.config)}`)),
      badge(state[0], state[1]), btn));
  };

  const section = (title, hint, tools, rows) => h("section", { class: "card src-list" },
    h("div", { class: "src-list-head" }, h("div", null, h("h2", null, title), hint ? h("div", { class: "muted" }, hint) : null), tools), rows);
  return h("div", { class: "narrow-page wide" },
    h("div", { class: "page-head" }, h("div", null, h("h1", null, "Sources"),
      h("div", { class: "sub" }, "The coding agents Chronicle records. Connecting starts archiving and analyzing their sessions and gives the agent Chronicle's MCP tools."))),
    section("Coding agents", `${connected} of ${sources.length} connected · click a row for its checks`, null, sources.map(agentRow)),
    section("Chat exports", "Chats on claude.ai and chatgpt.com are not stored on your Mac, so they come in from a data export.",
      h("div", { class: "src-actions" }, importBtn, picker), formats.map(formatRow)),
    section("Other MCP clients", ["Not recorded; they get Chronicle's MCP server to search your sessions and knowledge. For any other client, ",
      h("code", null, "chronicle mcp --print-config"), " prints an entry to paste."], null, clients.map(clientRow)));
});

// =====================================================================================
// Weekly reviews
// =====================================================================================
route(/^\/reviews$/, async () => {
  const data = await api("/api/reviews");
  const btn = (label, week) => {
    const b = h("button", { class: "btn", type: "button", onclick: async () => {
      b.disabled = true;
      const r = await post("/api/review", { week });
      toast(r.started ? "Claude is writing the review…" : "Already running");
      watchJob(`review:${week || "last"}`);
    } }, label);
    return b;
  };
  const cards = data.items.map((r, i) => {
    const body = mdEl(r.markdown);
    const card = h("section", { class: "card section-gap" }, body);
    if (i > 0) {
      body.style.maxHeight = "220px"; body.style.overflow = "hidden";
      body.style.webkitMaskImage = body.style.maskImage = "linear-gradient(to bottom, #000 60%, transparent)";
      const more = h("button", { class: "link-btn", type: "button", onclick: () => { body.style.maxHeight = ""; body.style.webkitMaskImage = body.style.maskImage = ""; more.remove(); } }, "Read full review");
      card.append(more);
    }
    return card;
  });
  return h("div", null,
    h("div", { class: "page-head" }, h("div", null, h("h1", null, "Weekly reviews"),
      h("div", { class: "sub" }, data.auto_ready ? `Review of ${data.last_week} will be written on the next background run`
        : `Written automatically once a week's sessions are analyzed (${data.last_week}: ${data.auto_note})`)),
      h("div", { style: { display: "flex", gap: "8px" } }, btn(`Write ${data.last_week}`, data.last_week), btn("This week so far", data.current_week))),
    cards.length ? cards : h("div", { class: "card empty" }, "No reviews yet."));
});

// =====================================================================================
// Status
// =====================================================================================
function updatesCard() {
  const box = h("section", { class: "card", id: "updates" }, h("div", { class: "card-head" }, h("h2", null, "Updates")), h("div", { class: "muted" }, "Loading…"));
  const draw = (u) => {
    const online = !u.source && u.kind !== "source"; // PyPI installs and the app compare against the latest release
    box.classList.toggle("update-ready", !!u.available);
    const state = u.error ? h("div", { style: { color: "var(--critical-ink)" } }, u.error)
      : u.available ? h("div", { class: "upd-headline" }, icon("sync"), h("b", null, u.local ? checkoutHeadline(u) : `Chronicle ${u.latest} is available`),
        u.notes_url ? h("a", { href: u.notes_url, target: "_blank", rel: "noopener" }, "What's new") : null)
      : online && !u.checked_at ? h("div", { class: "muted" }, u.check_daily ? "Checking pypi.org for the latest version…" : "Not checked yet. Checking asks pypi.org for the latest version.")
      : online ? h("div", null, `You're on the latest version (checked ${ago(new Date(u.checked_at * 1000).toISOString())})`) : null;
    const check = online ? h("button", { class: "btn", type: "button", onclick: async () => {
      check.disabled = true; check.textContent = "Checking…";
      const r = await post("/api/update/check");
      draw(r);
      pollStatus(); // the status bar and the notification pick up what the check found
    } }, "Check for updates") : null;
    const label = u.local ? "Reinstall from checkout" : u.source ? "Reinstall" : `Update to ${u.latest}`;
    const run = u.can_update && (u.available || u.source) ? h("button", { class: `btn${u.available ? " primary" : ""}`, type: "button", onclick: async () => {
      run.disabled = true; run.textContent = "Updating…";
      const r = await post("/api/update");
      if (!r.started) { toast(r.error || "An update is already running"); run.disabled = false; run.textContent = label; return; }
      try { sessionStorage.setItem("chronicle-updating", u.current); } catch (e) { /* private mode */ }
      toast(u.restartable ? "Updating Chronicle; the dashboard restarts when it is done" : "Updating Chronicle…", 6000);
      watchJob("update");
    } }, label) : null;
    const daily = online ? h("button", { class: "switch", type: "button", role: "switch", "aria-checked": String(!!u.check_daily),
      "aria-label": "Check for updates daily", onclick: async () => {
        daily.disabled = true;
        const r = await post("/api/update/daily", { on: !u.check_daily });
        if (r.error) { toast(r.error); daily.disabled = false; return; }
        draw(r);
        if (r.check_daily && !r.checked_at) setTimeout(async () => { draw(await api("/api/update")); pollStatus(); }, 4000); // the first check runs now
      } }) : null;
    const download = u.kind === "app" && u.available ? h("a", { class: "btn primary", href: u.releases_url, target: "_blank", rel: "noopener" }, `Download ${u.latest}`) : null;
    box.replaceChildren(h("div", { class: "card-head" }, h("h2", null, "Updates"), h("div", { class: "tools" }, check, run, download)),
      h("div", { class: "status-list" },
        h("div", null, `Chronicle ${u.current} · ${u.method}`, u.installed_at ? h("span", { class: "muted" }, ` · installed ${ago(new Date(u.installed_at * 1000).toISOString())}`) : null),
        state,
        u.changes ? changesList(u.changes) : null,
        u.note ? h("div", { class: "muted" }, u.note) : null,
        daily ? h("div", { class: "set-row upd-daily" }, h("div", null, h("b", null, "Check for updates daily"),
          h("div", { class: "muted" }, "Asks pypi.org for the latest version number once a day while Chronicle is open. Sends nothing about you.")), daily) : null,
        u.command && (u.available || u.source) ? h("div", { class: "muted" }, "Runs ", h("span", { class: "codeline" }, u.command),
          u.restartable ? ", then restarts the dashboard." : ". Quit and reopen Chronicle afterwards.") : null));
    if (parseHash().params.focus === "updates") { // from the notification or the status bar: show this card, once
      setParams({});
      requestAnimationFrame(() => box.scrollIntoView({ block: "nearest", behavior: "smooth" }));
      box.classList.add("flash");
    }
  };
  api("/api/update").then(draw).catch((e) => box.replaceChildren(h("div", { class: "card-head" }, h("h2", null, "Updates")), h("div", { style: { color: "var(--critical-ink)" } }, e.message)));
  return box;
}
function checkoutHeadline(u) { // a checkout's version number often stays put while its code moves on
  const n = u.changes?.commits?.length || 0;
  if (u.latest && u.latest !== u.current) return `Your checkout is at ${u.latest}; this install is ${u.current}`;
  return n ? `Your checkout has ${n}${n >= 30 ? "+" : ""} new commit${n === 1 ? "" : "s"} since this install` : "Your checkout's files have changed since this install";
}
const commitRow = (x) => h("li", null, h("code", null, x.sha), h("span", { title: x.subject }, x.subject), h("span", { class: "muted" }, ago(new Date(x.at * 1000).toISOString())));
function changesList(c) { // what a checkout reinstall brings in: commits since the install, then the changed files
  const files = c.files || [], commits = c.commits || [];
  const shown = files.slice(0, 12);
  return h("div", { class: "upd-changes" },
    commits.length ? [h("div", { class: "subhead" }, "Commits"),
      h("ul", { class: "upd-commits" }, commits.slice(0, 8).map(commitRow)),
      commits.length > 8 ? h("details", null, h("summary", null, `Show ${commits.length - 8} more`), h("ul", { class: "upd-commits" }, commits.slice(8).map(commitRow))) : null] : null,
    files.length ? h("details", { open: !commits.length }, h("summary", null, `${files.length} changed file${files.length === 1 ? "" : "s"}${commits.length ? "" : " (not committed yet)"}`),
      h("ul", { class: "upd-files" }, shown.map((f) => h("li", null, h("span", { class: "codeline" }, f))),
        files.length > shown.length ? h("li", { class: "muted" }, `and ${files.length - shown.length} more`) : null)) : null);
}
route(/^\/status$/, async () => {
  const st = await api("/api/status");
  const row = (ok, label, detail) => h("div", { class: "status-row" }, h("span", { class: ok ? "ok" : "no" }, ok ? "✓" : "✗"), h("span", null, label), detail ? h("span", { class: "muted" }, detail) : null);
  const counts = st.counts || {};
  return h("div", null,
    h("div", { class: "page-head" }, h("div", null, h("h1", null, "Status"), h("div", { class: "sub" }, `Chronicle ${st.version} · last sync ${ago(st.last_sync)}`))),
    h("div", { class: "grid cols-2" },
      h("section", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, "Recording")),
        h("div", { class: "status-list" },
          row(st.hooks?.SessionEnd, "SessionEnd hook", "archives + ingests each session as it ends"),
          row(st.launchd?.loaded, "Background agent (launchd)", st.launchd?.loaded ? `runs every 15 min · ${st.launchd.runs || 0} runs · last exit ${st.launchd.last_exit ?? "-"}` : "not loaded"),
          row(st.mcp, "MCP server registered", "Claude Code can search this vault"),
          row(!!st.hooks?.SessionStart, "SessionStart knowledge injection", "optional: chronicle install --inject-context")),
        h("div", { class: "subhead" }, "Storage"),
        h("div", null, h("span", { class: "codeline" }, st.archive_dir), " raw transcripts (kept forever, gzip)"),
        h("div", { style: { marginTop: "6px" } }, h("span", { class: "codeline" }, st.notes_dir), " Markdown vault"),
        h("div", { class: "muted", style: { marginTop: "6px" } }, `Database ${fmtCompact(st.db_size)}B`)),
      h("section", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, "Analysis")),
        h("div", { class: "status-list" },
          h("div", null, `Model `, h("code", null, st.config.model), ` · auto ${st.config.auto ? "on" : "off"} · backfill ${st.config.backfill ? "on" : "off"} · ${st.config.max_per_run} per run`),
          h("div", null, `${fmtNum(st.pending.ready)} ready now · ${fmtNum(st.pending.queued)} queued/stale · spent ${fmtCost(st.analysis_cost)} (API-equivalent)`),
          st.paused_until ? h("div", null, `Paused until ${fmtDT(st.paused_until)} (usage limit)`) : null,
          h("div", null, Object.entries(counts).map(([k, v]) => h("span", { class: "tag" }, `${STATUS_LABEL[k] || k}: ${v}`)))),
        st.errors.length ? [h("div", { class: "subhead" }, "Recent failures"), h("ul", { class: "bullets" }, st.errors.map((e) => h("li", null, h("a", { href: `#/session/${e.id}` }, e.title || e.id.slice(0, 8)), h("div", { class: "muted" }, (e.analysis_reason || "").slice(0, 200)))))] : null),
      updatesCard()));
});

// =====================================================================================
// Appearance: theme and transparency, remembered in this browser
// =====================================================================================
route(/^\/appearance$/, async () => {
  const root = document.documentElement;
  const theme = root.dataset.theme || "system";
  const setTheme = (v) => {
    if (v === "system") delete root.dataset.theme; else root.dataset.theme = v;
    try { v === "system" ? localStorage.removeItem("chronicle-theme") : localStorage.setItem("chronicle-theme", v); } catch (e) { /* private mode */ }
    themeChanged();
    render();
  };
  const solid = root.classList.contains("solid");
  const sw = h("button", { class: "switch", type: "button", role: "switch", "aria-checked": String(solid), "aria-label": "Reduce transparency", onclick: () => {
    const on = !root.classList.contains("solid");
    root.classList.toggle("solid", on);
    try { localStorage.setItem("chronicle-solid", on ? "1" : "0"); } catch (e) { /* private mode */ }
    sw.setAttribute("aria-checked", String(on));
  } });
  const row = (label, hint, control) => h("div", { class: "set-row" }, h("div", null, h("b", null, label), hint ? h("div", { class: "muted" }, hint) : null), control);
  return h("div", { class: "narrow-page" },
    h("div", { class: "page-head" }, h("div", null, h("h1", null, "Appearance"), h("div", { class: "sub" }, "Saved in this browser (and in the app window)."))),
    h("section", { class: "card set-card" },
      row("Theme", "System follows your Mac's light or dark setting.",
        segControl([["system", "System"], ["light", "Light"], ["dark", "Dark"]], theme, setTheme)),
      row("Reduce transparency", root.classList.contains("os-solid")
        ? "Reduce Transparency is on in macOS accessibility settings, so glass is already off."
        : "Makes the sidebar, toolbar and search solid instead of translucent.", sw),
      row("Sidebar", "⌘B shows or hides it. Clicking a section in the rail also brings it back.",
        h("button", { class: "btn", type: "button", onclick: toggleSidebar }, "Toggle sidebar"))));
});

// =====================================================================================
// Shell: rail, section sidebar, toolbar, status bar, command palette
// =====================================================================================
const SECTIONS = [
  { key: "home", label: "Home", href: "#/" },
  { key: "sessions", label: "Sessions", href: "#/sessions" },
  { key: "knowledge", label: "Knowledge", href: "#/knowledge" },
  { key: "projects", label: "Projects", href: "#/projects" },
  { key: "settings", label: "Settings", href: "#/status" },
];
const SECTION_OF = { overview: "home", sessions: "sessions", knowledge: "knowledge", glossary: "knowledge", map: "knowledge", reviews: "knowledge",
  projects: "projects", status: "settings", sources: "settings", appearance: "settings" };
const PAGE_LABEL = { glossary: "Glossary", map: "Map", reviews: "Weekly reviews", status: "Status", sources: "Sources", appearance: "Appearance" };
let shellSection = null, lastPath = null, lastHash = null, sbSeq = 0;

function sectionOf(path, params) {
  const key = navKey(path);
  if (key === "projects" && params.path === "__global__") return "knowledge"; // the global playbook is knowledge, not a project
  if (path.startsWith("/session/") && shellSection === "home") return "home"; // opened from Home's list: keep that list
  return SECTION_OF[key] || null; // search and unknown pages: no section lit, the sidebar stays as it was
}
function sectionLink(key) { const sx = SECTIONS.find((x) => x.key === key); return sx ? [sx.label, sx.href] : ["Chronicle", "#/"]; }
function setCrumbs(items, token = renderSeq) { // [[label, href?], ...]; the last is the current page
  if (token !== renderSeq) return; // a view that finished after the user moved on
  const page = items.length ? items[items.length - 1][0] : "";
  document.title = page && page !== "Home" ? `${page} — Chronicle` : "Chronicle";
  $("#crumbs").replaceChildren(...items.flatMap(([label, href], i) => [
    i ? h("span", { class: "sep" }, "›") : null,
    href && i < items.length - 1 ? h("a", { href }, label) : h("b", { title: label }, label)]).filter(Boolean));
}
function defaultCrumbs(path, params) {
  const key = navKey(path), section = sectionOf(path, params);
  if (key === "overview") return [["Home"]];
  if (key === "knowledge") return params.kind ? [sectionLink("knowledge"), [kindPlural(params.kind)]] : [["Knowledge"]];
  if (key === "projects" && path === "/projects") return [["Projects"]];
  if (key === "sessions" && path === "/sessions") return [["Sessions"]];
  if (path === "/search") return [["Search"], ...(params.q ? [[params.q]] : [])];
  if (!section) return [["Not found"]];
  if (PAGE_LABEL[key]) return [sectionLink(section), [PAGE_LABEL[key]]];
  return [sectionLink(section)];
}

function renderRail() {
  const rail = $("#rail");
  const link = (sx) => h("a", { href: sx.href, "data-section": sx.key, title: sx.label, "aria-label": sx.label,
    onclick: () => { if (document.documentElement.classList.contains("no-sidebar")) toggleSidebar(); } }, icon(sx.key === "home" ? "home" : sx.key));
  rail.replaceChildren(...SECTIONS.slice(0, 4).map(link), h("div", { class: "spacer" }), link(SECTIONS[4]));
}

// ------------------------------------------------------------------ sidebar
const sbState = { q: "", agent: "", offset: 0, total: 0, projectQ: "" };
function sbRow(label, href, iconName, count, match) {
  return h("a", { class: "sb-row", href, title: label, "data-route": match[0], "data-key": match[1] || "", "data-val": match[2] ?? "" },
    iconName ? icon(iconName) : null, h("span", null, label), count != null ? h("em", null, fmtNum(count)) : null);
}
function markSidebar(path, params) {
  document.querySelectorAll("#sidebar [data-route]").forEach((a) => {
    const on = a.dataset.route === path && (!a.dataset.key || (params[a.dataset.key] || "") === a.dataset.val);
    a.classList.toggle("on", on);
    if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
}
function dayGroup(ts) {
  const d0 = new Date(); d0.setHours(0, 0, 0, 0);
  const t = new Date(ts).getTime(), day = 86400000;
  if (t >= d0.getTime()) return "Today";
  if (t >= d0.getTime() - day) return "Yesterday";
  if (t >= d0.getTime() - 7 * day) return "Previous 7 days";
  if (t >= d0.getTime() - 30 * day) return "Previous 30 days";
  return new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(new Date(ts));
}
async function sessionsSidebar(box, title) {
  const list = h("div", { class: "sb-scroll" });
  const count = h("span");
  const more = h("button", { class: "sb-more", type: "button", onclick: () => load(true) }, "Show more");
  let lastGroup = null, debounce, loadSeq = 0;
  async function load(append) {
    const mine = ++loadSeq; // a newer filter or page wins; older responses are dropped
    const offset = append ? sbState.offset : 0;
    const data = await api("/api/sessions", { q: sbState.q, agent: sbState.agent, sort: "ended_at", limit: 60, offset });
    if (mine !== loadSeq) return;
    if (!append) { list.replaceChildren(); lastGroup = null; sbState.offset = 0; }
    more.remove();
    for (const x of data.items) {
      const g = dayGroup(x.ended_at || x.started_at); // by last activity, so a long-running live session stays under Today
      if (g !== lastGroup) { lastGroup = g; list.append(h("div", { class: "sb-group" }, g)); }
      const [cls, , label] = outcomeOf(x);
      list.append(h("a", { class: `sb-item s-${cls || "none"}`, href: `#/session/${x.id}`, "data-route": `/session/${x.id}`, title: x.title || "(untitled session)" },
        h("span", { class: "odot", title: label }), h("b", null, x.title || "(untitled session)"),
        h("small", null, [x.project_name, agentShort(x.agent), x.active_s ? fmtDur(x.active_s) : null].filter(Boolean).join(" · "))));
    }
    if (!data.items.length && !append) list.append(h("div", { class: "sb-empty" }, "No sessions match"));
    sbState.offset += data.items.length;
    sbState.total = data.total;
    count.textContent = fmtNum(data.total);
    if (sbState.offset < data.total) list.append(more);
    const { path, params } = parseHash();
    markSidebar(path, params);
  }
  const input = h("input", { type: "search", placeholder: "Filter sessions", value: sbState.q, "aria-label": "Filter sessions", autocomplete: "off",
    oninput: (e) => { clearTimeout(debounce); debounce = setTimeout(() => { sbState.q = e.target.value.trim(); load(false); }, 250); } });
  const chips = h("div", { class: "sb-chips" }, [["", "All"], ...Object.entries(AGENT_SHORT)].map(([v, l]) =>
    h("button", { type: "button", class: sbState.agent === v ? "on" : "", "aria-pressed": String(sbState.agent === v), onclick: (e) => {
      sbState.agent = v;
      chips.querySelectorAll("button").forEach((b) => { b.classList.toggle("on", b === e.currentTarget); b.setAttribute("aria-pressed", String(b === e.currentTarget)); });
      load(false);
    } }, l)));
  box.replaceChildren(h("div", { class: "sb-head" }, h("h2", null, title), count),
    h("label", { class: "sb-filter" }, icon("search"), input), chips, list);
  await load(false);
}
async function knowledgeSidebar(box) {
  const data = await api("/api/knowledge", { limit: 1 });
  const total = Object.values(data.counts).reduce((a, b) => a + b, 0);
  box.replaceChildren(h("div", { class: "sb-head" }, h("h2", null, "Knowledge"), h("span", null, fmtNum(total))),
    h("div", { class: "sb-scroll" },
      sbRow("All knowledge", "#/knowledge", "knowledge", total, ["/knowledge", "kind", ""]),
      h("div", { class: "sb-group" }, "Kinds"),
      Object.keys(KIND).filter((k) => data.counts[k]).map((k) => sbRow(kindPlural(k), `#/knowledge?kind=${k}`, k, data.counts[k], ["/knowledge", "kind", k])),
      h("div", { class: "sb-group" }, "Explore"),
      sbRow("Glossary", "#/glossary", "glossary", glossaryTerms?.length || null, ["/glossary"]),
      sbRow("Map", "#/map", "map", null, ["/map"]),
      sbRow("Global playbook", `#/project?path=${encodeURIComponent("__global__")}`, "playbook", null, ["/project", "path", "__global__"]),
      sbRow("Weekly reviews", "#/reviews", "reviews", null, ["/reviews"])));
}
async function projectsSidebar(box) {
  projectsCache ||= await api("/api/projects");
  const list = h("div", { class: "sb-scroll" });
  const draw = () => {
    const q = sbState.projectQ.toLowerCase();
    const shown = projectsCache.filter((p) => !q || p.label.toLowerCase().includes(q) || (p.project_path || "").toLowerCase().includes(q));
    list.replaceChildren(sbRow("All projects", "#/projects", "overview", projectsCache.length, ["/projects"]),
      h("div", { class: "sb-group" }, "Most recent first"),
      ...shown.map((p) => sbRow(p.label, `#/project?path=${encodeURIComponent(p.project_path || "")}`, "projects", p.sessions, ["/project", "path", p.project_path || ""])),
      shown.length ? null : h("div", { class: "sb-empty" }, "No projects match"));
    const { path, params } = parseHash();
    markSidebar(path, params);
  };
  box.replaceChildren(h("div", { class: "sb-head" }, h("h2", null, "Projects"), h("span", null, fmtNum(projectsCache.length))),
    h("label", { class: "sb-filter" }, icon("search"), h("input", { type: "search", placeholder: "Filter projects", value: sbState.projectQ, "aria-label": "Filter projects",
      oninput: (e) => { sbState.projectQ = e.target.value; draw(); } })), list);
  draw();
}
function settingsSidebar(box) {
  box.replaceChildren(h("div", { class: "sb-head" }, h("h2", null, "Settings")),
    h("div", { class: "sb-scroll" },
      sbRow("Status", "#/status", "status", null, ["/status"]),
      sbRow("Sources", "#/sources", "sources", null, ["/sources"]),
      sbRow("Appearance", "#/appearance", "appearance", null, ["/appearance"])));
}
async function buildSidebar(section) {
  const mine = ++sbSeq;
  const box = h("div", { class: "sb-body" }); // drawn off-screen, swapped in only if still wanted
  try {
    if (section === "home") await sessionsSidebar(box, "Recent sessions");
    else if (section === "sessions") await sessionsSidebar(box, "Sessions");
    else if (section === "knowledge") await knowledgeSidebar(box);
    else if (section === "projects") await projectsSidebar(box);
    else settingsSidebar(box);
  } catch (e) {
    box.replaceChildren(h("div", { class: "sb-empty" }, `Could not load: ${e.message}`));
  }
  if (mine !== sbSeq) return;
  $("#sidebar").setAttribute("aria-label", `${SECTIONS.find((x) => x.key === section).label} navigation`);
  $("#sidebar").replaceChildren(box);
  const { path, params } = parseHash();
  markSidebar(path, params);
}
function toggleSidebar() {
  const root = document.documentElement;
  if (matchMedia("(max-width: 860px)").matches) root.classList.toggle("show-sidebar");
  else {
    const hidden = root.classList.toggle("no-sidebar");
    try { localStorage.setItem("chronicle-sidebar", hidden ? "0" : "1"); } catch (e) { /* private mode */ }
  }
  sidebarExpanded();
}
function sidebarExpanded() {
  const root = document.documentElement;
  const open = matchMedia("(max-width: 860px)").matches ? root.classList.contains("show-sidebar") : !root.classList.contains("no-sidebar");
  $("#sidebar-btn").setAttribute("aria-expanded", String(open));
}
function updateShell(path, params) {
  const section = sectionOf(path, params);
  document.querySelectorAll("#rail a").forEach((a) => {
    const on = a.dataset.section === section;
    a.classList.toggle("on", on);
    if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  if (section && section !== shellSection) { shellSection = section; buildSidebar(section); }
  markSidebar(path, params);
  setCrumbs(defaultCrumbs(path, params));
  if (path !== lastPath) { $("#app").scrollTop = 0; lastPath = path; }
  if (location.hash !== lastHash) { // navigation, not a refresh after a background job
    lastHash = location.hash;
    document.documentElement.classList.remove("show-sidebar");
    sidebarExpanded();
    closePalette();
  }
}

// ------------------------------------------------------------------ command palette (⌘K, ⌘P, ⌘⇧P or /)
const pal = { sel: 0, items: [], seq: 0, open: false, timer: 0, query: "" };
function paletteCommands() {
  const dark = isDark();
  const nav = (label, href, iconName, hint = "") => ({ group: "Go to", label, hint, icon: iconName, run: () => go(href) });
  return [
    nav("Home", "#/", "home"), nav("Sessions", "#/sessions", "sessions"), nav("Knowledge", "#/knowledge", "knowledge"),
    nav("Glossary", "#/glossary", "glossary"), nav("Map", "#/map", "map"), nav("Projects", "#/projects", "projects"),
    nav("Global playbook", `#/project?path=${encodeURIComponent("__global__")}`, "playbook"), nav("Weekly reviews", "#/reviews", "reviews"),
    nav("Status", "#/status", "status"), nav("Sources", "#/sources", "sources"), nav("Appearance", "#/appearance", "appearance"),
    { group: "Commands", label: "Sync now", icon: "sync", hint: "", run: syncNow },
    { group: "Commands", label: "Toggle sidebar", icon: "sidebar", hint: "⌘B", run: toggleSidebar },
    { group: "Commands", label: dark ? "Switch to light theme" : "Switch to dark theme", icon: dark ? "sun" : "moon", hint: "", run: flipTheme },
    { group: "Commands", label: "Group glossary themes with Claude", icon: "sparkles", hint: "uses Claude", run: async () => {
      const r = await post("/api/map/themes");
      toast(r.started ? "Claude is grouping the glossary into themes…" : "Already running");
      watchJob("themes");
    } },
    { group: "Commands", label: "Rebuild the glossary", icon: "glossary", hint: "uses Claude", run: async () => {
      const r = await post("/api/glossary/rebuild", { path: "" });
      toast(r.started ? "Claude is rebuilding the glossary…" : "Already running");
      watchJob("glossary:all");
    } },
  ];
}
async function paletteSearch(q) {
  const lq = q.toLowerCase();
  const out = [];
  const [sessions, knowledge] = await Promise.all([
    api("/api/sessions", { q, limit: 6 }).catch(() => ({ items: [] })),
    api("/api/knowledge", { q, limit: 6 }).catch(() => ({ items: [] })),
    projectsCache ? null : api("/api/projects").then((p) => { projectsCache = p; }).catch(() => {}),
  ]);
  for (const x of sessions.items) out.push({ group: "Sessions", label: x.title || "(untitled session)", icon: "sessions",
    hint: [x.project_name, fmtDate(x.started_at)].filter(Boolean).join(" · "), run: () => go(`#/session/${x.id}`) });
  for (const k of knowledge.items) out.push({ group: "Knowledge", label: k.title, icon: KIND[k.kind] ? k.kind : "knowledge",
    hint: [kindLabel(k.kind), k.project_name].filter(Boolean).join(" · "), run: () => go(`#/knowledge?q=${encodeURIComponent(k.title)}`) });
  for (const p of (projectsCache || []).filter((p) => p.label.toLowerCase().includes(lq)).slice(0, 5)) out.push({ group: "Projects", label: p.label, icon: "projects",
    hint: `${fmtNum(p.sessions)} sessions`, run: () => go(`#/project?path=${encodeURIComponent(p.project_path || "")}`) });
  const terms = (glossaryTerms || []).filter((t) => t.term.toLowerCase().includes(lq) || (t.aliases || []).some((a) => a.toLowerCase().includes(lq)))
    .sort((a, b) => (b.term.toLowerCase().startsWith(lq) - a.term.toLowerCase().startsWith(lq)) || a.term.length - b.term.length).slice(0, 5);
  for (const t of terms) out.push({ group: "Glossary", label: t.term, icon: ICONS[t.category] ? t.category : "glossary", hint: t.category || "",
    run: () => go(`#/glossary?term=${encodeURIComponent(t.term)}`) });
  return out;
}
function drawPalette() {
  const list = $("#pal-list");
  if (!list) return;
  let group = null;
  list.replaceChildren(...pal.items.flatMap((x, i) => {
    const head = x.group !== group ? h("div", { class: "pal-group" }, (group = x.group)) : null;
    return [head, h("div", { class: `pal-item ${i === pal.sel ? "on" : ""}`, role: "option", "aria-selected": String(i === pal.sel), "data-i": i },
      icon(x.icon), h("span", null, x.label), x.hint ? h("small", null, x.hint) : null)].filter(Boolean);
  }));
  if (!pal.items.length) list.append(h("div", { class: "pal-empty" }, "Nothing matches"));
  list.querySelector(".pal-item.on")?.scrollIntoView({ block: "nearest" });
}
function searchItem(q) {
  return { group: "Search", label: `Search transcripts and knowledge for “${q}”`, icon: "search", hint: "↵", run: () => go(`#/search?q=${encodeURIComponent(q)}`) };
}
async function refreshPalette(q) {
  clearTimeout(pal.timer);
  const seq = ++pal.seq, query = q.trim(), lq = query.toLowerCase();
  pal.query = q;
  const cmds = paletteCommands().filter((c) => !lq || c.label.toLowerCase().includes(lq) || c.group.toLowerCase().includes(lq));
  pal.items = lq ? [...cmds, searchItem(query)] : cmds; pal.sel = 0; drawPalette();
  if (lq.length < 2) return;
  const found = await paletteSearch(query);
  if (seq !== pal.seq) return;
  pal.items = [...cmds, ...found, searchItem(query)]; drawPalette();
}
function openPalette() {
  if (pal.open) return;
  pal.open = true;
  const box = $("#palette");
  const input = h("input", { id: "pal-q", type: "text", placeholder: "Search sessions, knowledge, terms and commands", autocomplete: "off", spellcheck: "false",
    "aria-label": "Search or run a command", role: "combobox", "aria-controls": "pal-list", "aria-expanded": "true",
    oninput: (e) => { clearTimeout(pal.timer); const v = e.target.value; pal.timer = setTimeout(() => refreshPalette(v), 140); },
    onkeydown: (e) => {
      if (e.key === "ArrowDown") { pal.sel = Math.min(pal.sel + 1, pal.items.length - 1); drawPalette(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { pal.sel = Math.max(pal.sel - 1, 0); drawPalette(); e.preventDefault(); }
      else if (e.key === "Enter") {
        e.preventDefault();
        if (e.target.value !== pal.query) refreshPalette(e.target.value); // typed faster than the debounce
        runPaletteItem(pal.items[pal.sel]);
      }
    } });
  const list = h("div", { class: "pal-list", id: "pal-list", role: "listbox",
    onclick: (e) => { const it = e.target.closest(".pal-item"); if (it) runPaletteItem(pal.items[+it.dataset.i]); },
    onmousemove: (e) => { const it = e.target.closest(".pal-item"); if (it && +it.dataset.i !== pal.sel) { pal.sel = +it.dataset.i; drawPalette(); } } });
  pal.returnFocus = document.activeElement;
  box.replaceChildren(h("div", { class: "pal", role: "dialog", "aria-modal": "true", "aria-label": "Search or jump to" },
    h("div", { class: "pal-in" }, icon("search"), input, h("kbd", null, "esc")), list,
    h("div", { class: "pal-foot" }, h("span", null, h("kbd", null, "↑"), " ", h("kbd", null, "↓"), " move"), h("span", null, h("kbd", null, "↵"), " open"),
      h("span", null, h("kbd", null, "⌘K"), " ", h("kbd", null, "⌘P"), " ", h("kbd", null, "/"), " open this"))));
  box.hidden = false;
  box.onmousedown = (e) => { if (e.target === box) closePalette(); };
  refreshPalette("");
  input.focus();
}
function closePalette() {
  if (!pal.open) return;
  pal.open = false; pal.seq++; clearTimeout(pal.timer);
  $("#palette").hidden = true;
  $("#palette").replaceChildren();
  if (pal.returnFocus?.isConnected) pal.returnFocus.focus({ preventScroll: true });
}
function runPaletteItem(x) { if (!x) return; closePalette(); x.run(); }

// ------------------------------------------------------------------ jobs, status bar, theme
let watched = new Set(), pollTimer, uiBuild = null;
function watchJob(name) { watched.add(name); pollStatus(); }
async function pollStatus() {
  clearTimeout(pollTimer);
  let busy = false;
  try {
    const st = await api("/api/jobs");
    if (uiBuild && st.ui_build && st.ui_build !== uiBuild) { location.reload(); return; } // upgraded under us
    uiBuild ||= st.ui_build;
    const jobs = st.jobs || {};
    const running = Object.entries(jobs).filter(([, j]) => j.state === "running");
    busy = running.length > 0;
    const paused = st.paused_until && st.paused_until > new Date().toISOString();
    const pill = $("#status-pill");
    pill.className = busy ? "busy" : paused ? "warn" : "";
    pill.replaceChildren(h("span", { class: "dot" }), busy ? (running[0][1].message || running[0][0]) : paused ? `Analysis paused until ${fmtTime(st.paused_until)}` : "Up to date");
    const waiting = (st.pending.ready || 0) + (st.pending.queued || 0);
    $("#status-queue").textContent = waiting ? `${fmtNum(waiting)} session${waiting === 1 ? "" : "s"} queued for analysis` : "";
    $("#status-sync").textContent = st.last_sync ? `Synced ${ago(st.last_sync)}` : "Not synced yet";
    $("#status-version").textContent = st.version ? `Chronicle ${st.version}` : "";
    showUpdate(st.update, st.version);
    for (const name of [...watched]) {
      const j = jobs[name];
      if (j && j.state !== "running") {
        watched.delete(name);
        toast(j.state === "done" ? `Done: ${String(j.result || name).slice(0, 160)}` : `Failed: ${String(j.result).slice(0, 200)}`, 6000);
        if (name === "sync" || name === "import" || name.startsWith("glossary")) { shellSection = null; projectsCache = null; } // the sidebar's lists and counts may have changed
        render();
      }
    }
  } catch (e) { /* server restarting */ }
  pollTimer = setTimeout(pollStatus, busy || watched.size || !$("#activity").hidden ? 2500 : 20000);
}

// ------------------------------------------------------------------ activity panel (click the status bar)
let lastStatus = null;
function jobLabel(name) {
  const [kind, arg] = name.split(/:(.*)/);
  const tail = (p) => (p || "").replace(/\/+$/, "").split("/").pop();
  return {
    sync: "Sync", import: "Importing chats", update: "Updating Chronicle", themes: "Grouping glossary themes",
    analyze: arg === "selection" ? "Analyzing selected sessions" : `Analyzing session ${(arg || "").slice(0, 8)}`,
    glossary: arg ? `Glossary: ${tail(arg)}` : "Glossary", review: "Weekly review",
    synthesize: arg === "__global__" ? "Global playbook" : `Knowledge base: ${tail(arg)}`,
  }[kind] || name;
}
function fmtSecs(s) {
  s = Math.max(0, Math.round(s));
  return s < 60 ? `${s}s` : s < 3600 ? `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s` : `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}
function toggleActivity(force) {
  const box = $("#activity");
  const open = force ?? box.hidden;
  box.hidden = !open;
  $("#status-pill").setAttribute("aria-expanded", String(open));
  if (open) { if (lastStatus) drawActivity(lastStatus); pollStatus(); }
}
function drawActivity(st) {
  const box = $("#activity");
  const now = Date.now() / 1000;
  const jobs = Object.entries(st.jobs || {});
  const running = jobs.filter(([, j]) => j.state === "running").sort((a, b) => a[1].started - b[1].started);
  const recent = jobs.filter(([, j]) => j.state !== "running" && now - (j.finished || 0) < 6 * 3600)
    .sort((a, b) => b[1].finished - a[1].finished).slice(0, 6);
  const runRow = ([name, j]) => {
    const elapsed = now - j.started;
    const frac = j.total ? j.done / j.total : null;
    const left = frac && j.done ? (elapsed / j.done) * (j.total - j.done) : null;
    return h("div", { class: "act-job" },
      h("div", { class: "act-top" }, h("b", null, jobLabel(name)),
        h("span", { class: "muted" }, j.total ? `${fmtNum(j.done)} of ${fmtNum(j.total)}` : fmtSecs(elapsed))),
      h("div", { class: `act-bar${frac == null ? " indeterminate" : ""}`, role: "progressbar", "aria-label": jobLabel(name),
        ...(frac == null ? {} : { "aria-valuemin": "0", "aria-valuemax": String(j.total), "aria-valuenow": String(j.done) }) },
        h("i", { style: frac == null ? {} : { width: `${Math.max(2, frac * 100)}%` } })),
      h("div", { class: "act-msg muted" }, [j.message || "starting…", j.total ? fmtSecs(elapsed) + " so far" : null,
        left && j.done >= 2 ? `about ${fmtSecs(left)} left` : null].filter(Boolean).join(" · ")));
  };
  const doneRow = ([name, j]) => h("div", { class: "act-done" },
    h("span", { class: `act-mark ${j.state === "done" ? "ok" : "no"}` }, j.state === "done" ? "✓" : "✗"),
    h("div", null, h("div", null, h("b", null, jobLabel(name)), h("span", { class: "muted" }, ` · ${ago(new Date(j.finished * 1000).toISOString())}`)),
      h("div", { class: "act-msg muted" }, String(j.result || (j.state === "done" ? "done" : "failed")).slice(0, 220))));
  const waiting = (st.pending?.ready || 0) + (st.pending?.queued || 0);
  const paused = st.paused_until && st.paused_until > new Date().toISOString();
  const queue = paused ? `Analysis paused until ${fmtTime(st.paused_until)} (Claude usage limit); it resumes by itself.`
    : !waiting ? "Nothing waiting for analysis."
    : `${fmtNum(waiting)} session${waiting === 1 ? "" : "s"} waiting for analysis` + (st.analysis?.auto ? `; the background agent analyzes up to ${st.analysis.max_per_run} every 15 minutes.` : "; automatic analysis is off.");
  box.replaceChildren(...[
    h("div", { class: "act-head" }, h("b", null, "Activity"),
      h("button", { class: "un-close", type: "button", "aria-label": "Close", onclick: () => toggleActivity(false) }, "×")),
    h("div", { class: "act-section" }, running.length ? running.map(runRow) : h("div", { class: "muted act-idle" }, "Nothing running right now.")),
    h("div", { class: `act-queue${paused ? " warn" : ""}` }, icon(paused ? "pause" : "queued"), h("span", null, queue)),
    recent.length ? h("div", { class: "act-section" }, h("div", { class: "subhead" }, "Recent"), recent.map(doneRow)) : null,
    h("div", { class: "act-foot" },
      h("span", { class: "muted" }, st.last_sync ? `Synced ${ago(st.last_sync)}` : "Not synced yet"),
      h("span", null, h("button", { class: "btn small", type: "button", onclick: () => { toggleActivity(false); go("#/status"); } }, "Status"), " ",
        h("button", { class: "btn small primary", type: "button", disabled: running.some(([n]) => n === "sync"), onclick: syncNow }, "Sync now"))),
  ].filter(Boolean));
}
// an update on offer: a chip in the status bar, a dot on Settings, and once per update a notification card
function showUpdate(u, version) {
  const upd = $("#status-update");
  upd.hidden = !u;
  document.documentElement.classList.toggle("has-update", !!u);
  if (u) { upd.replaceChildren(h("span", { class: "dot" }), u.to === "build" ? "Update available" : `Update to ${u.to}`); upd.title = "Open Status to update Chronicle"; }
  let from = null;
  try { from = sessionStorage.getItem("chronicle-updating"); } catch (e) { /* private mode */ }
  if (from && !u) { // back after an update ran: say so once
    try { sessionStorage.removeItem("chronicle-updating"); } catch (e) { /* private mode */ }
    toast(version && version !== from ? `Chronicle updated to ${version}` : "Chronicle updated", 6000);
  }
  let seen = null;
  try { seen = localStorage.getItem("chronicle-update-seen"); } catch (e) { /* private mode */ }
  const card = $("#update-note");
  if (!u || seen === u.key || from) { card.hidden = true; return; }
  if (!card.hidden && card.dataset.key === u.key) return;
  const dismiss = () => { try { localStorage.setItem("chronicle-update-seen", u.key); } catch (e) { /* private mode */ } card.hidden = true; };
  card.dataset.key = u.key;
  card.replaceChildren(
    h("div", { class: "un-icon" }, icon("sync")),
    h("div", { class: "un-body" },
      h("b", null, u.to === "build" ? "Your checkout has new changes" : `Chronicle ${u.to} is available`),
      h("div", null, u.to === "build" ? "Reinstall to run them in the dashboard." : `You're on ${version}. Update from Settings › Status.`),
      h("div", { class: "un-actions" },
        h("button", { class: "btn primary small", type: "button", onclick: () => { dismiss(); go("#/status?focus=updates"); } }, "View update"),
        h("button", { class: "btn small", type: "button", onclick: dismiss }, "Later"))),
    h("button", { class: "un-close", type: "button", "aria-label": "Dismiss", onclick: dismiss }, "×"));
  card.hidden = false;
}
async function syncNow() {
  const r = await post("/api/sync");
  toast(r.started ? "Syncing transcripts and processing the queue…" : "A sync is already running");
  watchJob("sync");
}
function isDark() {
  const root = document.documentElement;
  return root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
}
function themeChanged() {
  const dark = isDark();
  $("#theme-btn").replaceChildren(icon(dark ? "sun" : "moon"));
  $("#theme-btn").title = dark ? "Switch to light theme" : "Switch to dark theme";
  // the app window's native glass follows the page's theme, not only the system's
  try { window.pywebview?.api?.set_appearance?.(document.documentElement.dataset.theme || "system"); } catch (e) { /* not in the app */ }
}
function flipTheme() {
  const root = document.documentElement;
  root.dataset.theme = isDark() ? "light" : "dark";
  try { localStorage.setItem("chronicle-theme", root.dataset.theme); } catch (e) { /* private mode */ }
  themeChanged();
  if (parseHash().path === "/appearance") render();
}

renderRail();
$("#sidebar-btn").append(icon("sidebar"));
$("#back-btn").append(icon("left"));
$("#fwd-btn").append(icon("right"));
$("#search-pill").prepend(icon("search"));
$("#sync-btn").prepend(icon("sync"));
$("#sidebar-btn").addEventListener("click", toggleSidebar);
$("#sidebar-btn").setAttribute("aria-controls", "sidebar");
sidebarExpanded();
matchMedia("(max-width: 860px)").addEventListener?.("change", sidebarExpanded);
$("#back-btn").addEventListener("click", () => history.back());
$("#fwd-btn").addEventListener("click", () => history.forward());
$("#search-pill").addEventListener("click", openPalette);
$("#sync-btn").addEventListener("click", syncNow);
$("#status-pill").addEventListener("click", () => toggleActivity());
$("#status-pill").setAttribute("aria-haspopup", "dialog");
$("#status-pill").setAttribute("aria-expanded", "false");
$("#status-pill").title = "Background work: click for progress";
document.addEventListener("mousedown", (e) => { if (!$("#activity").hidden && !e.target.closest("#activity, #status-pill")) toggleActivity(false); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#activity").hidden) toggleActivity(false); });
$("#status-update").addEventListener("click", () => go("#/status?focus=updates"));
$("#theme-btn").addEventListener("click", flipTheme);
themeChanged();
    lastStatus = st;
    if (!$("#activity").hidden) drawActivity(st);
matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", themeChanged);
window.addEventListener("pywebviewready", themeChanged);
document.addEventListener("mousedown", (e) => { // the narrow-window sidebar floats over the page; a click elsewhere closes it
  if (document.documentElement.classList.contains("show-sidebar") && !e.target.closest("#sidebar, #rail, #sidebar-btn")) document.documentElement.classList.remove("show-sidebar");
});
// the app window has no title bar: its toolbar and title strip move the window (double-click zooms it)
document.addEventListener("mousedown", (e) => {
  const api = window.pywebview?.api;
  if (!api?.start_drag || e.button !== 0 || !e.target.closest(".drag-region")) return;
  if (e.target.closest("a, button, input, select, textarea, label, kbd")) return;
  e.preventDefault();
  if (e.detail === 2) api.title_double_click(); else api.start_drag();
});
const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
document.addEventListener("keydown", (e) => {
  const mod = IS_MAC ? e.metaKey : e.ctrlKey, key = e.key.toLowerCase();
  const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName) || document.activeElement?.isContentEditable;
  if (mod && !e.altKey && (key === "k" || key === "p")) { e.preventDefault(); pal.open ? closePalette() : openPalette(); }
  else if (mod && !e.shiftKey && !e.altKey && key === "b") { e.preventDefault(); toggleSidebar(); }
  else if (e.key === "Escape" && pal.open) { e.preventDefault(); closePalette(); }
  else if (e.key === "Escape" && document.documentElement.classList.contains("show-sidebar")) document.documentElement.classList.remove("show-sidebar");
  else if (e.key === "/" && !mod && !typing && !pal.open) { e.preventDefault(); openPalette(); }
});
window.addEventListener("hashchange", render);
render();
pollStatus();

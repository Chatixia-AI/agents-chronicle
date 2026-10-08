// Runs in <head>, before the first paint: the app window's look, the UI language, the theme and the sidebar as
// they were. Its own file, not inline, so the page's Content-Security-Policy can allow scripts from 'self' only.
(function () {
  var root = document.documentElement, q = new URLSearchParams(location.search);
  // the macOS app loads ?app=mac: the page goes transparent over the window's native vibrancy
  if (q.get("app") === "mac") root.classList.add("in-app");
  if (q.get("reduce") === "1") root.classList.add("os-solid");
  // the UI language, resolved as i18n.js does: set before the first paint
  var lang = /^ja\b/i.test((navigator.languages && navigator.languages[0]) || navigator.language || "") ? "ja" : "en";
  try { var l = localStorage.getItem("chronicle-lang"); if (l === "en" || l === "ja") lang = l; } catch (e) {}
  root.lang = lang;
  try {
    var t = localStorage.getItem("chronicle-theme"); if (t) root.dataset.theme = t;
    if (localStorage.getItem("chronicle-sidebar") === "0") root.classList.add("no-sidebar");
  } catch (e) {}
})();

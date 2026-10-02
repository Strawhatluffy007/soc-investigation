// Applies the saved or system colour theme before the page paints (no flash).
// Loaded in <head>; app.js wires the toggle button.
(function () {
  let saved = null;
  try { saved = localStorage.getItem("theme"); } catch (_) { /* storage blocked */ }
  const sys = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  document.documentElement.dataset.theme = saved === "light" || saved === "dark" ? saved : sys;
})();

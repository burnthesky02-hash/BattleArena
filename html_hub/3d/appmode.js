/* appmode.js -- makes a game page behave like a game window instead of a web page: no right-click menu, no zoom,
   no page scrolling from arrow keys / Space, no back/forward gestures, no text or image dragging. Included by the
   hub, battle, overworld and heroes pages; skipped on the map builders. */
(function () {
  "use strict";
  if (window.__appmode || /builder/.test(location.pathname)) return; window.__appmode = true;
  var st = document.createElement("style");
  st.textContent = "html,body{overscroll-behavior:none}img{-webkit-user-drag:none}#scene,#scene *,canvas{-webkit-user-select:none;user-select:none}";
  (document.head || document.documentElement).appendChild(st);
  var typing = function (t) { return t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable); };
  document.addEventListener("contextmenu", function (e) { if (!typing(e.target)) e.preventDefault(); });
  document.addEventListener("mousedown", function (e) { if (e.button === 1) e.preventDefault(); });                 // middle-click auto-scroll
  window.addEventListener("wheel", function (e) { if (e.ctrlKey) e.preventDefault(); }, { passive: false });         // ctrl + wheel zoom
  window.addEventListener("keydown", function (e) {
    var k = e.key;
    if ((e.ctrlKey || e.metaKey) && (k === "+" || k === "-" || k === "=" || k === "_" || k === "0")) { e.preventDefault(); return; }
    if (e.altKey && (k === "ArrowLeft" || k === "ArrowRight")) { e.preventDefault(); return; }                          // history back/forward
    if (typing(e.target)) return;
    if (k === "Backspace") e.preventDefault();
    var t = e.target, free = !t || t === document.body || t === document.documentElement || t.tagName === "CANVAS" || (t.closest && t.closest("#scene"));
    if (free && (k === " " || k.indexOf("Arrow") === 0 || k === "PageUp" || k === "PageDown")) e.preventDefault();       // no page scrolling
  }, true);
})();

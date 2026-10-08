/* fishing.js -- the fishing mini-game that runs inside a hub3d scene (html_hub/3d/fish_pier.json, fish_pond.json).

   hub3d.js loads this file when a scene has a `fishing` block and calls Fishing.enter(fx); everything after that is here:
     cast -> bite -> reel fight, drawn on a 2D canvas laid over the 3D view (world points are projected with the scene camera),
     plus the tackle shop (rods + bait) and the fish log as DOM panels. The rules and results (what bites, what you get, the log,
     prices) live on the server: game/fishing.py via /api/fishing.

   scene.fishing = { spot: "pier"|"pond", stand: {x, z}, waterY, maxAim }   (see make_fishing.py)
   Actions (hub3d.js passes them in): {type:"fishing", op:"start"|"shop"|"log"}.
   Controls: the MOUSE moves the cast marker over the water (A/D/W/S fine-tune); click or SPACE casts there - hold SPACE (or the mouse button) to cast at the marker - SPACE when the float dives to set the hook -
   hold SPACE to reel, let go when the line glows red, A/D to steer against a run - T tackle - L log - Esc pack up. */
(function () {
  "use strict";
  const F = window.Fishing = { active: false, panel: false, inScene: false };
  let H = null, cfg = null, root = null, cv = null, g = null, panelEl = null, btnEl = null;
  let V = null;                                   // the last /api/fishing view (rod, bait, casts, species, shop)
  let clock = 0, dpr = 1, cssW = 0, cssH = 0;
  const input = { left: false, right: false, up: false, down: false, hold: false, mx: null, my: null, mouseT: -9 };
  const st = { s: "idle", t: 0, aim: 0, power: 0, lastDist: 14, dist: 14, ticket: null, catchInfo: null, msg: "", msgT: 0, pending: null,
    bobber: null, ripples: [], drops: [], castFrom: null, cast: null, wait: null, bite: null, f: null, card: null, tip: null, spent: false };
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v)), lerp = (a, b, t) => a + (b - a) * t, rnd = (a, b) => a + Math.random() * (b - a);
  const RARITY_COL = { common: "#c9d2d8", uncommon: "#7fe08a", rare: "#6db7ff", legendary: "#ffcf4a" };
  const ZONE_COL = { near: "#7ad1c0", mid: "#e6c75a", far: "#e98a5a" };

  /* ---------------------------------------------------------------- sound (tiny synth, no asset files) */
  let ac = null;
  function actx() { try { if (!ac) ac = new (window.AudioContext || window.webkitAudioContext)(); if (ac.state === "suspended") ac.resume(); } catch (e) { ac = null; } return ac; }
  function vol() { try { return H && H.sfxVol ? H.sfxVol() : 0.7; } catch (e) { return 0.7; } }
  function tone(f0, f1, dur, type, v) {
    const a = actx(); if (!a) return; const o = a.createOscillator(), gn = a.createGain(), t = a.currentTime;
    o.type = type || "sine"; o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(Math.max(20, f1 || f0), t + dur);
    gn.gain.setValueAtTime(0.0001, t); gn.gain.exponentialRampToValueAtTime(Math.max(0.0002, (v || 0.2) * vol()), t + 0.012); gn.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(gn); gn.connect(a.destination); o.start(t); o.stop(t + dur + 0.03);
  }
  function noise(dur, v, lo) {
    const a = actx(); if (!a) return; const n = Math.floor(a.sampleRate * dur), b = a.createBuffer(1, n, a.sampleRate), d = b.getChannelData(0);
    for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / n, 2);
    const s = a.createBufferSource(), gn = a.createGain(), fl = a.createBiquadFilter(); s.buffer = b; fl.type = "lowpass"; fl.frequency.value = lo || 2200; gn.gain.value = (v || 0.25) * vol();
    s.connect(fl); fl.connect(gn); gn.connect(a.destination); s.start();
  }
  const SND = {
    splash: () => { noise(0.35, 0.3, 1800); tone(300, 90, 0.2, "sine", 0.12); },
    whoosh: () => noise(0.22, 0.12, 5000),
    nibble: () => tone(520, 480, 0.06, "sine", 0.08),
    bite: () => { tone(880, 1320, 0.14, "square", 0.16); setTimeout(() => tone(1320, 1760, 0.16, "square", 0.14), 110); },
    hook: () => { tone(300, 600, 0.12, "triangle", 0.2); noise(0.12, 0.2, 3000); },
    click: () => tone(1500, 900, 0.025, "square", 0.05),
    warn: () => tone(180, 140, 0.12, "sawtooth", 0.14),
    snap: () => { noise(0.25, 0.35, 6000); tone(900, 120, 0.22, "sawtooth", 0.2); },
    win: () => { [523, 659, 784, 1047].forEach((f, i) => setTimeout(() => tone(f, f, 0.16, "triangle", 0.22), i * 90)); },
    lose: () => { tone(300, 150, 0.35, "triangle", 0.18); },
    rare: () => { [784, 988, 1175, 1568, 1976].forEach((f, i) => setTimeout(() => tone(f, f, 0.2, "sine", 0.22), i * 80)); },
    coin: () => { tone(1200, 1600, 0.08, "square", 0.1); setTimeout(() => tone(1600, 2000, 0.12, "square", 0.1), 70); },
  };

  /* ---------------------------------------------------------------- server */
  async function api(path, body) {
    try {
      const r = await fetch(path, body === undefined ? { cache: "no-store" } : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      return await r.json();
    } catch (e) { return { ok: false, message: "The line went slack. (Could not reach the game server.)" }; }
  }
  async function loadView() { const v = await api("/api/fishing?spot=" + encodeURIComponent(cfg ? cfg.spot : "pier")); if (v && v.ok) V = v; return V; }
  function refreshHub() { try { H && H.refresh && H.refresh(); } catch (e) {} }

  /* ---------------------------------------------------------------- UI shell */
  function css() {
    if (document.getElementById("fish-css")) return;
    const s = document.createElement("style"); s.id = "fish-css";
    s.textContent = `
      #fish-root { position:absolute; inset:0; z-index:9; display:none; user-select:none; -webkit-user-select:none; touch-action:none; cursor:crosshair; }
      #fish-root.on { display:block; }
      body.fishing-on .h3d-hint, body.fishing-on .h3d-quest { display:none !important; }
      #fish-cv { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; }
      #fish-btns { position:absolute; right:16px; top:64px; display:flex; flex-direction:column; gap:6px; z-index:2; }
      #fish-btns button, .fp-btn { font:600 13px/1 Georgia,serif; letter-spacing:.04em; color:#f6efd8; background:linear-gradient(#3a3550,#25213a); border:1px solid #d7b45a; border-radius:5px; padding:8px 12px; cursor:pointer; }
      #fish-btns button:hover, .fp-btn:hover:not(:disabled) { background:linear-gradient(#4b4568,#312b4c); }
      .fp-btn:disabled { opacity:.45; cursor:default; }
      #fish-panel { position:fixed; inset:0; z-index:60; display:none; align-items:center; justify-content:center; background:rgba(5,6,14,.62); font-family:Georgia,serif; color:#f6efd8; }
      #fish-panel.on { display:flex; }
      #fish-panel .fp-win { width:min(880px,94vw); max-height:88vh; display:flex; flex-direction:column; background:linear-gradient(#1b1a30,#12111f); border:2px solid #d7b45a; border-radius:10px; box-shadow:0 10px 50px #000c; }
      .fp-head { display:flex; align-items:center; gap:14px; padding:12px 18px; border-bottom:1px solid #d7b45a55; }
      .fp-head h2 { margin:0; font-size:20px; letter-spacing:.06em; color:#ffd77a; flex:1; }
      .fp-gold { font-weight:700; color:#ffe9a8; } .fp-gold i { font-style:normal; color:#8fd6ff; margin-left:12px; }
      .fp-tabs { display:flex; gap:4px; padding:10px 18px 0; }
      .fp-tab { padding:8px 16px; border:1px solid #d7b45a66; border-bottom:none; border-radius:6px 6px 0 0; background:#201e36; color:#cfc7ad; cursor:pointer; font-weight:700; }
      .fp-tab.on { background:#2e2a4d; color:#ffd77a; border-color:#d7b45a; }
      .fp-body { padding:14px 18px 6px; overflow:auto; border-top:1px solid #d7b45a66; flex:1; background:#2e2a4d33; }
      .fp-row { display:flex; align-items:center; gap:14px; padding:10px 12px; margin-bottom:8px; border:1px solid #ffffff1c; border-radius:8px; background:#ffffff08; }
      .fp-row.eq { border-color:#7fe08a; background:#7fe08a12; }
      .fp-row .nm { font-weight:700; font-size:16px; } .fp-row .ds { font-size:12.5px; color:#bfb8a0; margin-top:2px; }
      .fp-row .info { flex:1; min-width:0; } .fp-row .act { display:flex; gap:6px; align-items:center; }
      .fp-stats { display:grid; grid-template-columns:repeat(4,64px); gap:4px 8px; margin-top:6px; font-size:11px; color:#a9a38d; }
      .fp-bar { height:5px; background:#ffffff1a; border-radius:3px; overflow:hidden; margin-top:2px; } .fp-bar u { display:block; height:100%; background:#d7b45a; }
      .fp-price { color:#ffe9a8; font-weight:700; min-width:64px; text-align:right; }
      .fp-note { font-size:12.5px; color:#bfb8a0; margin:2px 0 10px; }
      .fp-msg { padding:8px 18px; min-height:20px; font-size:13.5px; color:#ffe9a8; }
      .fp-foot { display:flex; justify-content:space-between; align-items:center; padding:10px 18px 14px; border-top:1px solid #d7b45a44; font-size:12.5px; color:#a9a38d; }
      .fp-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(190px,1fr)); gap:10px; }
      .fp-card { border:1px solid #ffffff22; border-radius:8px; padding:8px 10px 10px; background:#ffffff08; position:relative; }
      .fp-card canvas { display:block; margin:0 auto 4px; }
      .fp-card.un { opacity:.6; } .fp-card .nm { font-weight:700; font-size:14px; } .fp-card .mt { font-size:11.5px; color:#a9a38d; margin-top:2px; line-height:1.35; }
      .fp-card .zn { position:absolute; right:8px; top:6px; font-size:10.5px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; }
      .fp-sum { margin-bottom:10px; font-size:14px; color:#ffe9a8; }
    `;
    document.head.appendChild(s);
  }
  function ensureUi() {
    css();
    const host = document.getElementById("scene") || document.body;
    if (!root) {
      root = document.createElement("div"); root.id = "fish-root";
      cv = document.createElement("canvas"); cv.id = "fish-cv"; root.appendChild(cv); g = cv.getContext("2d");
      btnEl = document.createElement("div"); btnEl.id = "fish-btns";
      btnEl.innerHTML = '<button data-b="tackle">Tackle (T)</button><button data-b="log">Fish log (L)</button><button data-b="quit">Pack up (Esc)</button>';
      root.appendChild(btnEl);
      btnEl.addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; e.stopPropagation(); const k = b.getAttribute("data-b"); if (k === "tackle") openPanel("rods"); else if (k === "log") openPanel("log"); else packUp(); });
      // the overlay owns the mouse while fishing: nothing may reach the 3D view's own drag / click-to-move / zoom handlers
      for (const ev of ["pointerdown", "pointerup", "wheel", "click", "contextmenu"]) root.addEventListener(ev, (e) => { e.stopPropagation(); if (ev === "wheel" || ev === "contextmenu") e.preventDefault(); });
      root.addEventListener("pointerdown", (e) => { if (e.target.closest("button") || e.button !== 0) return; pressDown(); try { root.setPointerCapture(e.pointerId); } catch (x) {} });
      root.addEventListener("pointerup", (e) => { if (e.button === 0) pressUp(); });
      root.addEventListener("pointermove", (e) => { const r = root.getBoundingClientRect(); input.mx = e.clientX - r.left; input.my = e.clientY - r.top; input.mouseT = clock; });
    }
    if (root.parentNode !== host) host.appendChild(root);
    if (!panelEl) {
      panelEl = document.createElement("div"); panelEl.id = "fish-panel"; document.body.appendChild(panelEl);
      panelEl.addEventListener("pointerdown", (e) => e.stopPropagation());
      panelEl.addEventListener("click", (e) => onPanelClick(e));
    }
  }

  /* ---------------------------------------------------------------- lifecycle */
  F.enter = function (fx) {
    H = fx; const S = H.S(); cfg = S && S.def && S.def.fishing; if (!cfg) return;
    F.inScene = true; ensureUi(); loadView();
    setTimeout(() => { if (F.inScene && !F.active && cfg) start(); }, 350);
    if (!window.__fishKeys) { window.__fishKeys = true; window.addEventListener("keydown", onKey, true); window.addEventListener("keyup", onKeyUp, true); window.addEventListener("blur", () => { input.hold = false; input.left = input.right = false; }); }
  };
  F.leave = function () { if (F.active) stop(true); F.inScene = false; cfg = null; closePanel(true); if (root) root.classList.remove("on"); };
  F.locked = () => F.active || F.panel;
  /* action dispatcher used by hub3d.js: done() resumes the script that called us */
  F.run = function (a, done) {
    if (!cfg) { done && done(); return; }
    if (a.op === "start") { start(); done && done(); }
    else if (a.op === "shop") openPanel("rods", { shop: true, done });
    else if (a.op === "log") openPanel("log", { done });
    else done && done();
  };

  function start() {
    if (F.active || !H) return;
    const S = H.S(), p = S.player, cam = H.cam;
    F.active = true; ensureUi(); root.classList.add("on"); document.body.classList.add("fishing-on");
    p.x = cfg.stand.x; p.z = cfg.stand.z; p.face = "north"; p.moving = false; p.target = null; p.path = null; p.wantNpc = null; p.t = 0; S.active = null; S.activeEv = null;
    st.prevCam = { free: cam.free, yaw: cam.goalYaw, pitch: cam.goalPitch, dist: cam.goalDist };
    cam.free = true; cam.tx = p.x; cam.tz = p.z - (cfg.look || 7); cam.ty = H.gh(p.x, p.z); cam.goalYaw = 0; cam.goalPitch = cfg.pitch || 24; cam.goalDist = cfg.dist || 19;
    setState("aim"); st.aim = 0; st.msg = ""; st.dist = st.lastDist = clamp(st.lastDist, 5, 14);
    loadView();
  }
  function stop(silent) {
    if (!F.active) return;
    if (st.ticket && ["wait", "bite", "fight"].includes(st.s)) { api("/api/fishing/result", { ticket: st.ticket, outcome: "lost" }); }
    st.ticket = null; F.active = false; if (root) root.classList.remove("on"); document.body.classList.remove("fishing-on"); input.hold = false;
    if (H && st.prevCam) { const cam = H.cam; cam.free = st.prevCam.free; cam.goalYaw = st.prevCam.yaw; cam.goalPitch = st.prevCam.pitch; cam.goalDist = st.prevCam.dist; }
    st.bobber = null; st.ripples = []; st.drops = []; setState("idle");
    if (!silent) refreshHub();
  }
  function packUp() { stop(true); if (H && H.leave) H.leave(); }
  function setState(s) { st.s = s; st.t = 0; }
  function say(msg, t) { st.msg = msg; st.msgT = t || 3.2; }

  /* ---------------------------------------------------------------- input */
  function pressDown() {
    input.hold = true; actx();
    if (st.s === "aim" && !st.pending) { setState("charge"); st.power = 0; }
    else if (st.s === "bite") hookSet();
    else if (st.s === "wait") reelEarly();
    else if (st.s === "result" && st.t > 0.5) { closeCard(); }
  }
  function pressUp() {
    input.hold = false;
    if (st.s === "charge") doCast();
  }
  function onKey(e) {
    if (!F.inScene) return;
    const k = e.key.toLowerCase();
    if (F.panel) {
      if (k === "escape" || k === "enter" || k === "e") { e.preventDefault(); e.stopImmediatePropagation(); if (k === "escape" || !e.repeat) closePanel(); }
      return;
    }
    if (!F.active) return;
    e.stopImmediatePropagation();
    if (k === "escape") { e.preventDefault(); if (!e.repeat) packUp(); return; }
    if (k === "t") { e.preventDefault(); if (!e.repeat && ["aim", "result", "idle"].includes(st.s)) openPanel("rods"); return; }
    if (k === "l") { e.preventDefault(); if (!e.repeat && ["aim", "result", "idle"].includes(st.s)) openPanel("log"); return; }
    if (k === "a" || k === "arrowleft") { input.left = true; e.preventDefault(); }
    else if (k === "d" || k === "arrowright") { input.right = true; e.preventDefault(); }
    else if (k === " " || k === "enter" || k === "e") { e.preventDefault(); if (!e.repeat) pressDown(); }
  }
  function onKeyUp(e) {
    if (!F.inScene || (!F.active && !F.panel)) return;
    const k = e.key.toLowerCase();
    if (k === "a" || k === "arrowleft") input.left = false; else if (k === "d" || k === "arrowright") input.right = false;
    else if (k === " " || k === "enter" || k === "e") { if (F.active) { e.stopImmediatePropagation(); pressUp(); } }
    if (F.active) e.stopImmediatePropagation();
  }

  /* ---------------------------------------------------------------- geometry helpers */
  function stand() { const S = H.S(); return { x: cfg.stand.x, z: cfg.stand.z, y: H.gh(cfg.stand.x, cfg.stand.z) }; }
  function tipWorld() { const s = stand(); return [s.x + 0.55, s.y + 3.1, s.z - 2.3]; }
  function handWorld() { const s = stand(); return [s.x + 0.32, s.y + 1.25, s.z - 0.35]; }
  function targetAt(aim, dist) { const s = stand(), a = aim; return [s.x + Math.sin(a) * dist, cfg.waterY, s.z - Math.cos(a) * dist]; }
  function P(w) { const p = H.project(w), k = cssW / (H.cam.w || cssW); return { x: p.x * k, y: p.y * k, w: p.w }; }
  function pxPerM(w) { const a = P(w), b = P([w[0] + 1, w[1], w[2]]); return Math.abs(b.x - a.x) || 1; }
  function ellipseAt(w, r) { const a = P(w), b = P([w[0] + r, w[1], w[2]]), c = P([w[0], w[1], w[2] - r]); return { x: a.x, y: a.y, rx: Math.abs(b.x - a.x), ry: Math.abs(c.y - a.y) }; }

  /* ---------------------------------------------------------------- the cast */
  const CAST_MIN = 5;
  // The mouse steers the cast ANGLE: solve for the aim that puts the marker under the mouse horizontally (distance comes from the charge).
  function curDist() { const reach = V ? V.rod.reach : 14; return st.s === "charge" ? CAST_MIN + st.power * (reach - CAST_MIN) : st.lastDist; }
  function aimFromMouse() {
    if (input.mx === null || !H) return;
    const maxA = cfg.maxAim || 0.7, d = curDist(); let a = st.aim;
    for (let it = 0; it < 5; it++) {
      const p0 = P(targetAt(a, d)); if (p0.w <= 0) return;
      const ex = input.mx - p0.x; if (Math.abs(ex) < 0.5) break;
      const pa = P(targetAt(a + 0.02, d)), j = (pa.x - p0.x) / 0.02; if (Math.abs(j) < 1e-3) return;
      a = clamp(a + clamp(ex / j, -0.3, 0.3), -maxA, maxA);
    }
    st.aim = a;
  }
  function doCast() {
    const reach = V ? V.rod.reach : 14, d = CAST_MIN + st.power * (reach - CAST_MIN);
    st.dist = st.lastDist = d; const tgt = targetAt(st.aim, d);
    st.cast = { from: tipWorld(), to: tgt, t: 0, dur: 0.55 + d * 0.012 };
    st.bobber = { x: tgt[0], z: tgt[2], y: cfg.waterY, dip: 0, sunk: 0 };
    setState("cast"); st.pending = api("/api/fishing/cast", { spot: cfg.spot, dist: d }); SND.whoosh();
    st.pending.then((r) => { st.pending = { r }; });
  }
  function stepCast(dt) {
    const c = st.cast; c.t += dt / c.dur;
    if (c.t >= 1 && !st.splashed) { st.splashed = true; splash(st.bobber.x, st.bobber.z, 1.2); SND.splash(); }
    if (c.t >= 1 && st.pending && st.pending.r) {
      const r = st.pending.r; st.pending = null; st.splashed = false;
      if (!r.ok) { say(r.message || "Nothing happens.", 4); st.bobber = null; if (r.casts && V) V.casts = r.casts; setState("aim"); return; }
      if (V) { V.casts = r.casts; V.bait = r.bait; V.baits = r.baits; V.baitName = (V.baitShop.find((b) => b.id === r.bait) || {}).name || "Bare Hook"; }
      if (r.note) say(r.note, 3.5);
      st.ticket = r.ticket; st.catchInfo = r.catch; st.zone = r.zone;
      const n = Math.max(0, Math.floor((r.delay - 1.5) / 2.3));
      st.wait = { delay: r.delay, window: r.window, nibbles: Array.from({ length: n }, () => rnd(0.8, r.delay - 1.9)).sort((a, b) => a - b), done: 0, rip: 0 };
      setState("wait");
    }
  }
  function splash(x, z, s) {
    st.ripples.push({ x, z, t: 0, life: 1.6 * s, r: 2.2 * s });
    for (let i = 0; i < 9 * s; i++) { const a = rnd(0, 6.28), v = rnd(1.2, 3.2); st.drops.push({ x, y: cfg.waterY, z, vx: Math.cos(a) * v * 0.5, vy: rnd(2.5, 5) * s, vz: Math.sin(a) * v * 0.5, t: 0 }); }
  }
  function stepWait(dt) {
    const w = st.wait, b = st.bobber; w.t = (w.t || 0) + dt;
    b.bob = Math.sin(clock * 2.2) * 0.04;
    w.rip += dt; if (w.rip > 1.7) { w.rip = 0; st.ripples.push({ x: b.x, z: b.z, t: 0, life: 1.8, r: 0.9 }); }
    if (w.done < w.nibbles.length && w.t >= w.nibbles[w.done]) { w.done++; b.dip = 1; st.ripples.push({ x: b.x, z: b.z, t: 0, life: 1.3, r: 1.3 }); SND.nibble(); }
    b.dip = Math.max(0, b.dip - dt * 2.2);
    if (w.t >= w.delay) startBite();
  }
  function startBite() {
    st.bite = { t: 0, win: st.wait.window * 0.8 }; setState("bite"); st.bobber.dip = 0; SND.bite();
    st.ripples.push({ x: st.bobber.x, z: st.bobber.z, t: 0, life: 1.4, r: 2.0 });
  }
  function reelEarly() {
    api("/api/fishing/result", { ticket: st.ticket, outcome: "lost" }); st.ticket = null; st.bobber = null; say("You reel the line in. Patience pays.", 2.6); setState("aim");
  }
  function hookSet() {
    SND.hook(); const c = st.catchInfo || {}, kg = c.kg || 0, sizeF = clamp(Math.log10(1 + kg) / 2.2, 0, 1);
    const s = stand(), tgt = [st.bobber.x, st.bobber.z];
    st.f = { dist: 1, tension: 0.4, surge: false, tNext: rnd(0.9, 1.6), dir: Math.random() < 0.5 ? -1 : 1, over: 0, slack: 0, sizeF, speed: 0.30 - 0.12 * sizeF, fight: clamp(c.fight == null ? 0.5 : c.fight, 0.05, 1),
      flip: 9, steer: false, ax: s.x, az: s.z, tx: tgt[0], tz: tgt[1], lat: 0, ripT: 0, warned: false };
    splash(st.bobber.x, st.bobber.z, 1.0); setState("fight");
  }
  function stepBite(dt) {
    const b = st.bite; b.t += dt; st.bobber.sunk = Math.min(1, b.t * 7) * 0.9;
    if (Math.floor(b.t * 5) !== Math.floor((b.t - dt) * 5)) st.ripples.push({ x: st.bobber.x, z: st.bobber.z, t: 0, life: 0.9, r: 1.0 });
    if (b.t > b.win) { api("/api/fishing/result", { ticket: st.ticket, outcome: "lost" }); st.ticket = null; st.bobber = null; SND.lose(); say("It got away. Strike faster when the float dives!", 3.4); setState("aim"); }
  }

  /* ---------------------------------------------------------------- the reel fight */
  function stepFight(dt) {
    const f = st.f, rod = V.rod; f.tNext -= dt;
    if (f.tNext <= 0) {
      f.surge = !f.surge;
      if (f.surge) { f.tNext = rnd(1.0, 1.7) * (0.6 + 0.6 * f.fight); f.dir = Math.random() < 0.5 ? -1 : 1; f.flip = f.fight > 0.5 ? 0.55 : 9; SND.warn(); f.warned = true; }
      else f.tNext = rnd(1.0, 2.0) / (0.6 + f.fight);
    }
    if (f.surge) { f.flip -= dt; if (f.flip <= 0) { f.dir = -f.dir; f.flip = 9; SND.warn(); } }   // strong fish change direction mid-run
    let pull = f.surge ? 0.3 + 0.75 * f.fight + 0.22 * f.sizeF : 0.07 + 0.2 * f.fight + 0.14 * f.sizeF;
    f.steer = f.surge && (f.dir < 0 ? input.right : input.left);
    if (f.steer) pull *= 0.62; else if (f.surge) pull *= 1.1;
    if (input.hold) {
      f.tension += (0.41 + 1.25 * pull) * rod.stress * dt;
      const eff = f.tension < 0.25 ? 0.5 : (f.tension > 0.8 ? 0.5 : 1);
      f.dist -= f.speed * rod.power * eff * (1 - 0.65 * pull) * dt;
      if (f.surge && !f.steer) f.dist += 0.05 * pull * dt;                       // an unanswered run takes line back
    } else {
      f.tension += pull * 0.5 * rod.stress * dt - 0.85 * dt;
      f.dist += pull * 0.09 * dt;
    }
    f.tension = clamp(f.tension, 0, 1.08); f.dist = clamp(f.dist, 0, 1);
    // snap / slack
    if (f.tension >= 1) { f.over += dt; if (f.over > rod.tolerance * 0.87) return loseFish(true); } else f.over = Math.max(0, f.over - dt * 2);
    if (f.tension < 0.06) { f.slack += dt; if (f.slack > 1.5) return loseFish(false); } else f.slack = 0;
    // fish position for drawing: along the line to the player, swinging sideways during a run
    f.lat = lerp(f.lat, f.surge ? f.dir * 3.2 * f.dist : Math.sin(clock * 1.7) * 0.5 * f.dist, 1 - Math.pow(0.02, dt));
    f.ripT -= dt; if (f.ripT <= 0) { f.ripT = f.surge ? 0.16 : 0.5; const p = fishPos(); st.ripples.push({ x: p[0], z: p[2], t: 0, life: 0.9, r: f.surge ? 1.4 : 0.8 }); if (f.surge && Math.random() < 0.5) splash(p[0], p[2], 0.45); }
    if (Math.floor(clock * 14) !== Math.floor((clock - dt) * 14) && input.hold) SND.click();
    if (f.dist <= 0) landFish();
  }
  function fishPos() {
    const f = st.f, x = lerp(f.ax, f.tx, f.dist), z = lerp(f.az, f.tz, f.dist), dx = f.tx - f.ax, dz = f.tz - f.az, l = Math.hypot(dx, dz) || 1;
    return [x + (-dz / l) * f.lat, cfg.waterY, z + (dx / l) * f.lat];
  }
  function loseFish(snapped) {
    api("/api/fishing/result", { ticket: st.ticket, outcome: "lost" }); st.ticket = null; st.bobber = null;
    if (snapped) { SND.snap(); say("SNAP! The line broke. Ease off before it goes red.", 4); } else { SND.lose(); say("Too slack — the hook fell out. Keep a little tension on it.", 4); }
    setState("aim");
  }
  async function landFish() {
    const t = st.ticket; st.ticket = null; setState("landing");
    const r = await api("/api/fishing/result", { ticket: t, outcome: "landed" });
    if (!r || !r.ok || !r.landed) { say((r && r.message) || "It slipped the hook at the last second!", 3.5); st.bobber = null; setState("aim"); return; }
    st.card = r; st.bobber = null; setState("result"); refreshHub();
    if (r.newSpecies || r.rarity === "rare" || r.rarity === "legendary") SND.rare(); else SND.win();
    if (r.value) setTimeout(() => SND.coin(), 300);
    loadView();
  }
  function closeCard() { st.card = null; setState("aim"); }

  /* ---------------------------------------------------------------- per-frame (called by hub3d.js after the camera update) */
  F.update = function (dt) {
    if (!F.active || !H || !cfg) return;
    { const c = H.cam; c.goalYaw = 0; c.goalPitch = cfg.pitch || 24; c.goalDist = cfg.dist || 19; }
    clock += dt; st.t += dt; if (st.msgT > 0) st.msgT -= dt;
    if (F.panel) { draw(); return; }
    const sp = 1.3;
    if (st.s === "aim" || st.s === "charge") {
      if (input.left) st.aim -= sp * dt; if (input.right) st.aim += sp * dt;
      if (!input.left && !input.right && input.mx !== null) aimFromMouse();
      st.aim = clamp(st.aim, -(cfg.maxAim || 0.7), cfg.maxAim || 0.7);
    }
    if (st.s === "charge") { const tt = (st.t % 2.0) / 1.0; st.power = tt < 1 ? tt : 2 - tt; if (Math.floor(st.t * 18) !== Math.floor((st.t - dt) * 18)) SND.click(); }
    else if (st.s === "cast") stepCast(dt);
    else if (st.s === "wait") stepWait(dt);
    else if (st.s === "bite") stepBite(dt);
    else if (st.s === "fight") stepFight(dt);
    for (const r of st.ripples) r.t += dt; st.ripples = st.ripples.filter((r) => r.t < r.life);
    for (const d of st.drops) { d.t += dt; d.vy -= 11 * dt; d.x += d.vx * dt; d.z += d.vz * dt; d.y += d.vy * dt; } st.drops = st.drops.filter((d) => d.y > cfg.waterY - 0.05 && d.t < 1.5);
    draw();
  };

  /* ---------------------------------------------------------------- drawing */
  function fit() {
    const r = root.getBoundingClientRect(); dpr = Math.min(2, window.devicePixelRatio || 1);
    if (Math.abs(r.width - cssW) > 0.5 || Math.abs(r.height - cssH) > 0.5 || cv.width !== Math.round(r.width * dpr)) {
      cssW = r.width; cssH = r.height; cv.width = Math.round(cssW * dpr); cv.height = Math.round(cssH * dpr);
    }
    g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, cssW, cssH);
  }
  function txt(s, x, y, size, col, align, bold) {
    g.font = (bold === false ? "" : "700 ") + size + "px Georgia, serif"; g.textAlign = align || "center"; g.textBaseline = "middle";
    g.lineWidth = Math.max(3, size / 5); g.strokeStyle = "rgba(10,8,22,.85)"; g.lineJoin = "round"; g.strokeText(s, x, y); g.fillStyle = col || "#f6efd8"; g.fillText(s, x, y);
  }
  function rrect(x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
  function draw() {
    fit(); const u = clamp(cssH / 800, 0.7, 1.35);
    const sd = st.s;
    drawWater(u);
    drawRodAndLine(u);
    if (sd === "aim" || sd === "charge") drawReticle(u);
    if (sd === "charge") drawPower(u);
    
    if (sd === "bite") drawBiteMark(u);
    if (sd === "fight") drawFight(u);
    drawHud(u);
    if (sd === "result" && st.card) drawCard(u);
  }
  function drawWater(u) {
    // ripples on the water plane
    g.save(); g.lineWidth = Math.max(1.5, 2 * u);
    for (const r of st.ripples) {
      const k = r.t / r.life, e = ellipseAt([r.x, cfg.waterY, r.z], r.r * (0.25 + k)); if (e.rx < 1) continue;
      g.strokeStyle = "rgba(235,248,255," + (0.65 * (1 - k)).toFixed(3) + ")"; g.beginPath(); g.ellipse(e.x, e.y, e.rx, Math.max(1.5, e.ry), 0, 0, 6.283); g.stroke();
    }
    // the fish's shadow gliding in before the bite / thrashing during the fight
    let sh = null;
    if (st.s === "wait" && st.wait && st.wait.t > st.wait.delay - 1.8) { const k = clamp((st.wait.t - (st.wait.delay - 1.8)) / 1.7, 0, 1), ang = (st.wait.delay * 7.3) % 6.28, dd = 5 * (1 - k * k) + 0.4; sh = [st.bobber.x + Math.cos(ang) * dd, st.bobber.z + Math.sin(ang) * dd, k]; }
    else if (st.s === "bite") sh = [st.bobber.x + Math.sin(clock * 9) * 0.25, st.bobber.z, 1];
    else if (st.s === "fight") { const p = fishPos(); sh = [p[0], p[2], 1]; }
    if (sh && st.catchInfo) {
      const kg = st.catchInfo.kg || 0, len = st.catchInfo.kind === "fish" ? clamp(0.35 + Math.pow(kg, 0.38) * 0.35, 0.3, 3.4) : 0.5;
      const e = ellipseAt([sh[0], cfg.waterY, sh[1]], len), a = P([sh[0], cfg.waterY, sh[1]]); if (e.rx > 1 && a.w > 0) {
        g.fillStyle = "rgba(8,22,34," + (0.5 * sh[2]).toFixed(3) + ")"; g.beginPath(); g.ellipse(e.x, e.y, e.rx, Math.max(2, e.ry * 0.38), st.s === "fight" ? Math.sin(clock * 7) * 0.2 : 0.1, 0, 6.283); g.fill();
        g.beginPath(); const tx = e.x - e.rx * 1.05 * Math.sign(Math.sin(sh[0] * 3.1 + 0.5) || 1); g.moveTo(tx, e.y); g.lineTo(tx - e.rx * 0.45 * Math.sign(tx - e.x || 1), e.y - e.ry * 0.5); g.lineTo(tx - e.rx * 0.45 * Math.sign(tx - e.x || 1), e.y + e.ry * 0.5); g.closePath(); g.fill();
      }
    }
    // bobber
    if (st.bobber && st.s !== "cast" && st.s !== "fight" && st.s !== "landing") {
      const b = st.bobber, dip = Math.max(b.dip * 0.18, b.sunk * 0.45), pos = [b.x, cfg.waterY + (b.bob || 0) - dip, b.z], p = P(pos); if (p.w > 0) drawBobber(p, pxPerM(pos), dip > 0.1);
    }
    if (st.s === "cast" && st.cast) { const c = st.cast, k = clamp(c.t, 0, 1), arc = 2.2 + Math.hypot(c.to[0] - c.from[0], c.to[2] - c.from[2]) * 0.1; const pos = [lerp(c.from[0], c.to[0], k), lerp(c.from[1], c.to[1], k) + Math.sin(k * Math.PI) * arc, lerp(c.from[2], c.to[2], k)]; const p = P(pos); drawBobber(p, pxPerM(pos), false); st.castPos = pos; }
    // water drops
    g.fillStyle = "rgba(240,250,255,.85)";
    for (const d of st.drops) { const p = P([d.x, d.y, d.z]); if (p.w <= 0) continue; const s = Math.max(1.5, pxPerM([d.x, d.y, d.z]) * 0.07); g.beginPath(); g.arc(p.x, p.y, s, 0, 6.283); g.fill(); }
    g.restore();
  }
  function drawBobber(p, ppm, diving) {
    const r = Math.max(4, ppm * 0.17);
    g.save(); g.translate(p.x, p.y);
    g.fillStyle = "rgba(0,0,0,.25)"; g.beginPath(); g.ellipse(0, r * 0.45, r * 1.2, r * 0.4, 0, 0, 6.283); g.fill();
    g.fillStyle = "#f4f1e6"; g.beginPath(); g.arc(0, 0, r, 0, 6.283); g.fill();
    g.fillStyle = "#e1352c"; g.beginPath(); g.arc(0, 0, r, Math.PI, 0); g.fill();
    g.strokeStyle = "#222"; g.lineWidth = Math.max(1, r * 0.18); g.beginPath(); g.arc(0, 0, r, 0, 6.283); g.stroke();
    g.fillStyle = "#222"; g.fillRect(-r * 0.08, -r * 1.7, r * 0.16, r * 0.8);
    g.restore();
  }
  function drawRodAndLine(u) {
    const hw = handWorld(), tw = tipWorld(), h = P(hw), t0 = P(tw); if (h.w <= 0 || t0.w <= 0) return;
    let target = null, tension = 0.5, bend = 0.3;
    if (st.s === "cast" && st.castPos) { target = P(st.castPos); tension = 0.1; bend = 0.1; }
    else if (st.bobber && ["wait", "bite"].includes(st.s)) { target = P([st.bobber.x, cfg.waterY + (st.bobber.bob || 0), st.bobber.z]); tension = st.s === "bite" ? 0.55 : 0.2; bend = st.s === "bite" ? 0.55 + Math.sin(clock * 40) * 0.1 : 0.15; }
    else if (st.s === "fight" && st.f) { const fp = fishPos(); target = P(fp); tension = st.f.tension; bend = 0.35 + st.f.tension * 0.65; }
    // rod: a springy curve from the hand to the tip, bowing toward the line
    const dirx = target ? Math.sign(target.x - t0.x) || 0 : 0, mid = { x: (h.x + t0.x) / 2, y: (h.y + t0.y) / 2 };
    const cx = mid.x + dirx * 16 * u * bend + 2 * u, cy = mid.y + 10 * u * bend;
    const tip = { x: t0.x + dirx * 14 * u * bend, y: t0.y + 12 * u * bend };
    g.save(); g.lineCap = "round";
    g.strokeStyle = "#2a1c10"; g.lineWidth = 5.5 * u; g.beginPath(); g.moveTo(h.x, h.y); g.quadraticCurveTo(cx, cy, tip.x, tip.y); g.stroke();
    g.strokeStyle = "#b9824a"; g.lineWidth = 3.2 * u; g.beginPath(); g.moveTo(h.x, h.y); g.quadraticCurveTo(cx, cy, tip.x, tip.y); g.stroke();
    if (target && target.w > 0) {
      const len = Math.hypot(target.x - tip.x, target.y - tip.y), sag = (1 - clamp(tension, 0, 1)) * len * 0.12 + 3;
      let col = "rgba(245,245,235,.92)";
      if (st.s === "fight" && st.f) { const k = clamp((st.f.tension - 0.7) / 0.3, 0, 1); col = "rgb(255," + Math.round(245 - 200 * k) + "," + Math.round(235 - 200 * k) + ")"; g.shadowColor = k > 0.2 ? "rgba(255,70,50," + k + ")" : "transparent"; g.shadowBlur = 12 * k; }
      g.strokeStyle = col; g.lineWidth = Math.max(1.2, 1.6 * u); g.beginPath(); g.moveTo(tip.x, tip.y); g.quadraticCurveTo((tip.x + target.x) / 2, (tip.y + target.y) / 2 + sag, target.x, target.y); g.stroke();
    }
    g.restore();
  }
  function drawReticle(u) {
    const reach = V ? V.rod.reach : 14, d = st.s === "charge" ? 5 + st.power * (reach - 5) : st.lastDist, w = targetAt(st.aim, d), e = ellipseAt(w, 1.0), a = P(w); if (a.w <= 0) return;
    const zone = d < 10 ? "near" : d < 18 ? "mid" : "far", col = ZONE_COL[zone];
    g.save(); g.strokeStyle = col; g.lineWidth = 2.5 * u; g.setLineDash([6 * u, 5 * u]); g.lineDashOffset = -clock * 14;
    g.beginPath(); g.ellipse(e.x, e.y, e.rx, Math.max(3, e.ry), 0, 0, 6.283); g.stroke(); g.setLineDash([]);
    g.beginPath(); g.ellipse(e.x, e.y, e.rx * 0.35, Math.max(1.5, e.ry * 0.35), 0, 0, 6.283); g.stroke();
    g.restore(); txt(zone + " water · " + d.toFixed(0) + " m", e.x, e.y - Math.max(18 * u, e.ry + 12 * u), 14 * u, col);
  }
  function drawPower(u) {
    const reach = V ? V.rod.reach : 14, w = 360 * u, h = 22 * u, x = cssW / 2 - w / 2, y = cssH - 118 * u;
    g.save(); g.fillStyle = "rgba(12,10,26,.82)"; rrect(x - 6, y - 6, w + 12, h + 12, 8); g.fill(); g.strokeStyle = "#d7b45a"; g.lineWidth = 1.5; g.stroke();
    const seg = (d0, d1, col) => { const a = clamp((d0 - 5) / (reach - 5), 0, 1), b = clamp((d1 - 5) / (reach - 5), 0, 1); if (b <= a) return; g.fillStyle = col; g.fillRect(x + a * w, y, (b - a) * w, h); };
    seg(5, 10, "#2f7f72"); seg(10, 18, "#9c8a2e"); seg(18, 99, "#a4553a");
    g.fillStyle = "rgba(255,255,255,.18)"; g.fillRect(x, y, w * st.power, h);
    const mx = x + st.power * w; g.fillStyle = "#fff"; g.fillRect(mx - 2, y - 5, 4, h + 10);
    g.restore();
    if (reach < 18) txt("Far water is out of reach — a longer rod would get you there", cssW / 2, y - 16 * u, 12.5 * u, "#e9a58f", "center", false);
  }
  function drawBiteMark(u) {
    const b = st.bobber; if (!b) return; const p = P([b.x, cfg.waterY + 1.4, b.z]); if (p.w <= 0) return; const k = st.bite.t, pulse = 1 + Math.sin(k * 24) * 0.12;
    g.save(); g.translate(p.x, p.y - 8 * u); g.scale(pulse, pulse); g.fillStyle = "#ffd23a"; g.strokeStyle = "#7a2b00"; g.lineWidth = 3 * u; g.beginPath(); g.arc(0, 0, 21 * u, 0, 6.283); g.fill(); g.stroke();
    g.fillStyle = "#b0200e"; g.font = "900 " + 28 * u + "px Georgia"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("!", 0, 2 * u); g.restore();
    const left = clamp(1 - st.bite.t / st.bite.win, 0, 1); g.fillStyle = "rgba(0,0,0,.5)"; g.fillRect(p.x - 30 * u, p.y + 22 * u, 60 * u, 6 * u); g.fillStyle = "#ffd23a"; g.fillRect(p.x - 30 * u, p.y + 22 * u, 60 * u * left, 6 * u);
  }
  function drawFight(u) {
    const f = st.f, x = 54 * u, h = 300 * u, w = 30 * u, y = cssH / 2 - h / 2 + 30 * u;
    g.save(); g.fillStyle = "rgba(12,10,26,.82)"; rrect(x - 12, y - 30 * u, w + 24, h + 44 * u, 10); g.fill(); g.strokeStyle = "#d7b45a"; g.lineWidth = 1.5; g.stroke();
    const band = (a, b, col) => { g.fillStyle = col; g.fillRect(x, y + h * (1 - b), w, h * (b - a)); };
    band(0, 0.12, "#3a5f9a"); band(0.12, 0.28, "#3d7f9a"); band(0.28, 0.72, "#3a9a5a"); band(0.72, 0.88, "#d69a2c"); band(0.88, 1.0, "#d2402e");
    g.fillStyle = "rgba(0,0,0,.35)"; g.fillRect(x, y, w, h * (1 - clamp(f.tension, 0, 1)));
    const my = y + h * (1 - clamp(f.tension, 0, 1)); g.fillStyle = "#fff"; g.strokeStyle = "#000"; g.lineWidth = 2; g.beginPath(); g.moveTo(x - 9, my - 7 * u); g.lineTo(x + 2, my); g.lineTo(x - 9, my + 7 * u); g.closePath(); g.fill(); g.stroke();
    g.fillRect(x - 2, my - 1.5, w + 4, 3);
    g.restore(); txt("LINE", x + w / 2, y - 16 * u, 13 * u, "#ffe9a8");
    // distance bar
    const bw = 340 * u, bx = cssW / 2 - bw / 2, by = 54 * u;
    g.fillStyle = "rgba(12,10,26,.82)"; rrect(bx - 8, by - 12 * u, bw + 16, 34 * u, 8); g.fill(); g.strokeStyle = "#d7b45a"; g.lineWidth = 1.5; g.stroke();
    g.fillStyle = "#2c3555"; g.fillRect(bx, by, bw, 12 * u); g.fillStyle = "#7fd0ff"; g.fillRect(bx, by, bw * (1 - f.dist), 12 * u);
    txt("Reel it in", cssW / 2, by - 24 * u, 13 * u, "#ffe9a8");
    const kg = (st.catchInfo && st.catchInfo.kg) || 0, big = kg > 25 ? "Something huge!" : kg > 6 ? "It's a big one!" : "It's fighting!";
    if (f.surge) {
      const flash = Math.sin(clock * 16) > 0 ? "#ff6a4a" : "#ffd0c0"; txt("IT'S RUNNING  " + (f.dir < 0 ? "◀" : "▶"), cssW / 2, cssH * 0.3, 26 * u, flash);
      txt("ease off the reel  ·  steer " + (f.dir < 0 ? "▶" : "◀") + " to calm it", cssW / 2, cssH * 0.3 + 28 * u, 14 * u, f.steer ? "#9dffb0" : "#ffe9a8");
    } else txt(big, cssW / 2, cssH * 0.3, 20 * u, "#ffe9a8");
    if (f.tension > 0.88) txt("LINE STRAINING!", x + w / 2, y + h + 22 * u, 12 * u, "#ff7a60");
    if (f.tension < 0.1 && f.slack > 0.3) txt("slack…", x + w / 2, y + h + 22 * u, 12 * u, "#8fc6ff");
  }
  function drawHud(u) {
    const casts = V && V.casts ? V.casts : null, rod = V ? V.rod.name : "", bait = V ? V.baitName : "";
    const bn = V && V.bait && V.bait !== "none" && V.baits ? " ×" + (V.baits[V.bait] || 0) : "";
    g.save(); g.fillStyle = "rgba(12,10,26,.72)"; rrect(16, 16, 260 * u, 78 * u, 8); g.fill(); g.strokeStyle = "#d7b45a99"; g.lineWidth = 1.2; g.stroke(); g.restore();
    txt(cfg.title || (V && V.spotName) || "Fishing", 28, 34 * u, 15 * u, "#ffd77a", "left");
    txt(rod, 28, 54 * u, 13 * u, "#f6efd8", "left", false); txt("Bait: " + bait + bn, 28, 72 * u, 13 * u, "#f6efd8", "left", false);
    if (casts) txt("Casts " + casts.left + "/" + casts.max, 262 * u, 54 * u, 13 * u, casts.left > 0 ? "#9be7ff" : "#ff9c8a", "right");
    if (V && V.total) txt("Log " + V.caughtCount + "/" + V.total, 262 * u, 72 * u, 13 * u, "#ffe9a8", "right");
    const hints = { aim: "Mouse aims  ·  hold click / SPACE to charge, release to cast  ·  T tackle  ·  L log", charge: "Release to cast", cast: "", wait: "Wait for the float to dive…   (SPACE reels in)", bite: "SPACE — NOW!",
      fight: "Hold SPACE to reel  ·  let go when the line glows red  ·  A / D steer a run", landing: "", result: "SPACE to continue", idle: "" };
    const hint = hints[st.s]; if (hint) txt(hint, cssW / 2, cssH - 30 * u, 15 * u, "#f6efd8");
    if (st.msgT > 0 && st.msg) txt(st.msg, cssW / 2, cssH - 62 * u, 16 * u, "#ffe9a8");
    if (casts && casts.left <= 0 && (st.s === "aim")) txt("Out of casts — the fish need a minute (next in " + Math.ceil(casts.next) + " s)", cssW / 2, cssH - 94 * u, 14 * u, "#ff9c8a");
    btnEl.style.display = ["aim", "result", "idle"].includes(st.s) ? "flex" : "none";
  }
  function drawFishShape(c, x, y, len, col, flip, dark) {
    c.save(); c.translate(x, y); if (flip) c.scale(-1, 1);
    const h = len * 0.36;
    c.fillStyle = dark ? "#1d1b2d" : col; c.beginPath(); c.moveTo(len * 0.5, 0);
    c.bezierCurveTo(len * 0.3, -h * 1.1, -len * 0.2, -h * 1.0, -len * 0.38, -h * 0.12); c.lineTo(-len * 0.55, -h * 0.75); c.lineTo(-len * 0.5, 0); c.lineTo(-len * 0.55, h * 0.75); c.lineTo(-len * 0.38, h * 0.12);
    c.bezierCurveTo(-len * 0.2, h * 0.95, len * 0.3, h * 1.05, len * 0.5, 0); c.closePath(); c.fill();
    if (!dark) {
      c.fillStyle = "rgba(255,255,255,.22)"; c.beginPath(); c.ellipse(len * 0.02, h * 0.28, len * 0.34, h * 0.32, 0, 0, 6.283); c.fill();
      c.fillStyle = "rgba(0,0,0,.2)"; c.beginPath(); c.moveTo(-len * 0.05, -h * 0.9); c.lineTo(len * 0.12, -h * 1.35); c.lineTo(len * 0.2, -h * 0.85); c.closePath(); c.fill();
      c.fillStyle = "#fff"; c.beginPath(); c.arc(len * 0.3, -h * 0.18, len * 0.04, 0, 6.283); c.fill(); c.fillStyle = "#111"; c.beginPath(); c.arc(len * 0.31, -h * 0.18, len * 0.02, 0, 6.283); c.fill();
    }
    c.restore();
  }
  function drawCard(u) {
    const r = st.card, w = Math.min(460 * u, cssW - 30), h = 330 * u, x = cssW / 2 - w / 2, y = cssH / 2 - h / 2 - 20 * u, col = RARITY_COL[r.rarity] || "#fff", k = clamp(st.t / 0.25, 0, 1);
    g.save(); g.globalAlpha = k; g.translate(0, (1 - k) * 18);
    g.fillStyle = "rgba(14,12,30,.94)"; rrect(x, y, w, h, 14); g.fill(); g.strokeStyle = col; g.lineWidth = 3; g.stroke();
    const glow = g.createRadialGradient(cssW / 2, y + 100 * u, 10, cssW / 2, y + 100 * u, 150 * u); glow.addColorStop(0, col + "55"); glow.addColorStop(1, col + "00"); g.fillStyle = glow; g.fillRect(x, y, w, 220 * u);
    if (r.kind === "fish") drawFishShape(g, cssW / 2, y + 98 * u, clamp(80 + Math.pow(r.kg, 0.35) * 40, 110, 250) * u, r.color, false, false);
    else if (r.kind === "treasure") { g.fillStyle = "#c18a38"; rrect(cssW / 2 - 40 * u, y + 70 * u, 80 * u, 56 * u, 8); g.fill(); g.fillStyle = "#e7c15a"; g.fillRect(cssW / 2 - 40 * u, y + 90 * u, 80 * u, 8 * u); g.fillStyle = "#2a1a08"; g.fillRect(cssW / 2 - 6 * u, y + 88 * u, 12 * u, 14 * u); }
    else { g.fillStyle = "#6f7a5a"; g.beginPath(); g.ellipse(cssW / 2, y + 100 * u, 60 * u, 22 * u, 0.2, 0, 6.283); g.fill(); }
    g.restore(); g.save(); g.globalAlpha = k;
    let yy = y + 172 * u;
    if (r.newSpecies) txt("★ NEW SPECIES ★", cssW / 2, y + 28 * u, 17 * u, "#ffd77a");
    else if (r.kind === "fish") txt(r.rarity.toUpperCase(), cssW / 2, y + 28 * u, 13 * u, col);
    txt(r.name, cssW / 2, yy, 25 * u, "#fff7e0"); yy += 28 * u;
    if (r.kind === "fish") { txt(r.size + " · " + r.kg.toFixed(2) + " kg" + (r.record ? "  ·  new personal best!" : ""), cssW / 2, yy, 15 * u, "#cfe8ff", "center", false); yy += 24 * u; }
    if (r.text) { txt(r.text, cssW / 2, yy, 13 * u, "#bfb8a0", "center", false); yy += 22 * u; }
    const bits = []; if (r.value) bits.push("+" + r.value + " gold"); if (r.bonus) bits.push("first-catch bonus +" + r.bonus); if (r.setBonus) bits.push("collection complete! +" + r.setBonus + " gems"); if (r.gems && r.kind === "treasure") bits.push("+" + r.gems + " gems");
    for (const k2 in (r.items || {})) bits.push("+" + r.items[k2] + " " + k2.replace(/_/g, " "));
    if (bits.length) txt(bits.join("   ·   "), cssW / 2, yy, 14 * u, "#ffe9a8");
    g.restore();
  }

  /* ---------------------------------------------------------------- panels: tackle (rods + bait) and the fish log */
  let ptab = "rods", pmsg = "", popts = {};
  function openPanel(tab, opts) {
    if (!cfg) { opts && opts.done && opts.done(); return; }
    popts = opts || {}; ptab = tab; pmsg = ""; F.panel = true; input.hold = false; input.left = input.right = false; ensureUi(); panelEl.classList.add("on"); renderPanel();
    loadView().then(() => { if (F.panel) renderPanel(); });
  }
  function closePanel(silent) {
    if (!F.panel) return; F.panel = false; if (panelEl) panelEl.classList.remove("on"); const d = popts.done; popts = {}; refreshHub();
    if (!silent && d) setTimeout(d, 0);
  }
  function bar(v, max) { return '<div class="fp-bar"><u style="width:' + Math.round(100 * clamp(v / max, 0, 1)) + '%"></u></div>'; }
  function renderPanel() {
    if (!panelEl) return; const v = V; if (!v) { panelEl.innerHTML = '<div class="fp-win"><div class="fp-body">Loading…</div></div>'; return; }
    const shop = !!popts.shop;
    let body = "";
    if (ptab === "rods") {
      body += '<div class="fp-note">' + (shop ? v.seller + ': "The right rod changes what you can land — longer casts reach the deep water, a softer drag forgives mistakes."' : "Rods you own. Visit " + v.seller + " at the shore to buy more.") + "</div>";
      for (const r of v.rods) {
        const forg = 1 / r.stress;
        body += '<div class="fp-row' + (r.equipped ? " eq" : "") + '"><div class="info"><div class="nm">' + r.name + (r.equipped ? '  <span style="color:#7fe08a;font-size:12px">equipped</span>' : "") + '</div><div class="ds">' + r.desc + "</div>" +
          '<div class="fp-stats"><div>Reach ' + r.reach + " m" + bar(r.reach, 33) + "</div><div>Power" + bar(r.power, 1.5) + "</div><div>Forgiving" + bar(forg, 1.65) + "</div><div>Luck" + bar(r.luck, 0.25) + "</div></div></div>" +
          '<div class="act">' + (r.owned ? (r.equipped ? "" : '<button class="fp-btn" data-act="equip-rod" data-id="' + r.id + '">Equip</button>') : (shop ? '<span class="fp-price">' + r.cost + ' g</span><button class="fp-btn" data-act="buy-rod" data-id="' + r.id + '"' + (v.money < r.cost ? " disabled" : "") + ">Buy</button>" : '<span class="fp-price">' + r.cost + " g</span>")) + "</div></div>";
      }
    } else if (ptab === "bait") {
      body += '<div class="fp-note">Bait is used up one per cast. Different bait draws different fish' + (shop ? "" : " — visit " + v.seller + " to restock") + ".</div>";
      const own = (id) => (v.baits && v.baits[id]) || 0;
      body += '<div class="fp-row' + (v.bait === "none" ? " eq" : "") + '"><div class="info"><div class="nm">Bare Hook</div><div class="ds">No bait. Fish are not impressed.</div></div><div class="act">' + (v.bait === "none" ? "" : '<button class="fp-btn" data-act="equip-bait" data-id="none">Use</button>') + "</div></div>";
      const shelf = v.baitShop.slice(); for (const id in (v.baits || {})) if (!shelf.find((b) => b.id === id)) shelf.push({ id, name: id, desc: "", cost: 0, pack: 0, have: own(id) });
      for (const b of shelf) {
        body += '<div class="fp-row' + (v.bait === b.id ? " eq" : "") + '"><div class="info"><div class="nm">' + b.name + '  <span style="color:#9be7ff;font-size:12px">you have ' + own(b.id) + "</span></div><div class=\"ds\">" + (b.desc || "") + "</div></div>" +
          '<div class="act">' + (shop && b.cost ? '<span class="fp-price">' + b.cost + " g<br><small>×" + b.pack + "</small></span><button class=\"fp-btn\" data-act=\"buy-bait\" data-id=\"" + b.id + "\"" + (v.money < b.cost ? " disabled" : "") + ">Buy</button>" : "") +
          (own(b.id) > 0 && v.bait !== b.id ? '<button class="fp-btn" data-act="equip-bait" data-id="' + b.id + '">Use</button>' : "") + "</div></div>";
      }
    } else {
      body += '<div class="fp-sum">' + v.spotName + " — " + v.caughtCount + " of " + v.total + " species" + (v.setDone ? "  ★ collection complete" : "  ·  complete the set for a bonus of 5 gems") + "</div>";
      body += '<div class="fp-grid">';
      for (const s of v.species) {
        body += '<div class="fp-card' + (s.caught ? "" : " un") + '"><span class="zn" style="color:' + ZONE_COL[s.zone] + '">' + s.zone + '</span><canvas width="150" height="56" data-fish="' + s.id + '" data-col="' + s.color + '" data-c="' + (s.caught ? 1 : 0) + '"></canvas><div class="nm" style="color:' + (s.caught ? RARITY_COL[s.rarity] : "#8b87a0") + '">' + s.name + "</div>" +
          '<div class="mt">' + (s.caught ? "Caught ×" + s.count + " · best " + s.best + " kg<br>" + s.note : "Not caught yet.") + "</div></div>";
      }
      body += "</div>";
    }
    panelEl.innerHTML = '<div class="fp-win"><div class="fp-head"><h2>' + (shop ? v.seller + "'s Tackle" : "Tackle & Log") + '</h2><div class="fp-gold">' + v.money + ' gold<i>' + v.gems + ' gems</i></div></div>' +
      '<div class="fp-tabs"><div class="fp-tab' + (ptab === "rods" ? " on" : "") + '" data-tab="rods">Rods</div><div class="fp-tab' + (ptab === "bait" ? " on" : "") + '" data-tab="bait">Bait</div><div class="fp-tab' + (ptab === "log" ? " on" : "") + '" data-tab="log">Fish log</div></div>' +
      '<div class="fp-body">' + body + '</div><div class="fp-msg">' + (pmsg || "") + '</div><div class="fp-foot"><span>Esc / Enter to close</span><button class="fp-btn" data-act="close">Close</button></div></div>';
    panelEl.querySelectorAll("canvas[data-fish]").forEach((c) => { const cx = c.getContext("2d"); drawFishShape(cx, 75, 28, 100, c.getAttribute("data-col"), false, c.getAttribute("data-c") !== "1"); });
  }
  async function onPanelClick(e) {
    e.stopPropagation(); const tab = e.target.closest("[data-tab]"); if (tab) { ptab = tab.getAttribute("data-tab"); pmsg = ""; renderPanel(); return; }
    const b = e.target.closest("[data-act]"); if (!b || b.disabled) return; const act = b.getAttribute("data-act"), id = b.getAttribute("data-id"); let r = null;
    if (act === "close") { closePanel(); return; }
    if (act === "buy-rod") r = await api("/api/fishing/buy", { spot: cfg.spot, kind: "rod", id });
    else if (act === "buy-bait") r = await api("/api/fishing/buy", { spot: cfg.spot, kind: "bait", id, packs: 1 });
    else if (act === "equip-rod") r = await api("/api/fishing/equip", { spot: cfg.spot, kind: "rod", id });
    else if (act === "equip-bait") r = await api("/api/fishing/equip", { spot: cfg.spot, kind: "bait", id });
    if (r) { pmsg = r.message || ""; if (r.view && r.view.ok) V = r.view; else await loadView(); if (r.ok) { SND.coin(); refreshHub(); } renderPanel(); }
  }

  /* debug / test hook */
  F._t = { st, input, get V() { return V; }, set V(v) { V = v; }, get cfg() { return cfg; }, setCfg(c) { cfg = c; }, setH(h) { H = h; }, start, stop, openPanel, closePanel, stepFight, hookSet, setState, ensureUi, api };
})();

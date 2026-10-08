/* EnvFX: screen-space weather / ambient particles drawn on a transparent 2D canvas above the 3D view.
   Shared by the hub, the battle arenas and the scene editor.
   scene.fx = [{ type, amount: 0..1 (default .5), speed: 1, wind: 0, color: "#hex" }]
   types: rain, snow, embers, dust, fireflies, leaves, lightning                                              */
(function () {
  "use strict";
  const TAU = Math.PI * 2, R = Math.random;
  const hexRGB = (s, d) => { if (typeof s !== "string" || !/^#?[0-9a-f]{3,6}$/i.test(s)) return d; s = s.replace("#", ""); if (s.length === 3) s = s.replace(/./g, "$&$&"); return [0, 2, 4].map((i) => parseInt(s.substr(i, 2), 16)); };
  const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
  let glowSprite = null, density = 1; const insts = new Set();   // density: the Settings 'Weather & particles' slider (0..1)
  function glow() {
    if (glowSprite) return glowSprite; const c = document.createElement("canvas"); c.width = c.height = 64; const g = c.getContext("2d"), r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    r.addColorStop(0, "rgba(255,255,255,1)"); r.addColorStop(0.25, "rgba(255,255,255,.55)"); r.addColorStop(1, "rgba(255,255,255,0)"); g.fillStyle = r; g.fillRect(0, 0, 64, 64); return (glowSprite = c);
  }
  const BASE = { rain: 320, snow: 170, embers: 90, dust: 70, fireflies: 26, leaves: 26 };
  const DEF_COL = { rain: [175, 195, 225], snow: [255, 255, 255], embers: [255, 140, 50], dust: [255, 240, 210], fireflies: [220, 255, 120], leaves: [190, 120, 50] };
  const LEAF = [[190, 120, 50], [150, 90, 40], [210, 160, 60], [120, 110, 50]];

  function spawn(e, W, H, first) {
    const k = e.type, sp = e.speed;
    if (k === "rain") return { x: R() * (W + 200) - 100, y: first ? R() * H : -R() * 80, v: (800 + R() * 500) * sp, len: 12 + R() * 16, a: 0.25 + R() * 0.3 };
    if (k === "snow") return { x: R() * W, y: first ? R() * H : -10, v: (35 + R() * 55) * sp, r: 1.2 + R() * 2.4, ph: R() * TAU, a: 0.5 + R() * 0.45 };
    if (k === "embers") return { x: R() * W, y: first ? H * (0.3 + R() * 0.7) : H + 10, v: (35 + R() * 90) * sp, r: 0.9 + R() * 2.2, ph: R() * TAU, life: 0, max: 3 + R() * 5 };
    if (k === "dust") return { x: R() * W, y: R() * H, vx: (R() - 0.5) * 14 * sp, vy: (R() - 0.5) * 8 * sp, r: 0.8 + R() * 1.6, ph: R() * TAU, a: 0.15 + R() * 0.25 };
    if (k === "fireflies") return { x: R() * W, y: H * (0.35 + R() * 0.6), ang: R() * TAU, v: (14 + R() * 26) * sp, ph: R() * TAU, r: 5 + R() * 5 };
    if (k === "leaves") return { x: R() * (W + 200) - 100, y: first ? R() * H : -20, v: (40 + R() * 50) * sp, ph: R() * TAU, rot: R() * TAU, vr: (R() - 0.5) * 3, s: 4 + R() * 4, c: LEAF[(R() * LEAF.length) | 0] };
    return {};
  }

  function create(parent, after) {
    const cv = document.createElement("canvas"); cv.className = "envfx"; cv.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none;display:block";
    if (after && after.parentNode === parent) parent.insertBefore(cv, after.nextSibling); else parent.appendChild(cv);
    const g = cv.getContext("2d");
    let W = 1, H = 1, effects = [], vis = true, raf = 0, last = 0, t = 0, flash = { a: 0, next: 4, seq: [] }, dead = false, lastDraw = true;
    function size() { const r = cv.getBoundingClientRect(), w = Math.max(1, Math.round(r.width)), h = Math.max(1, Math.round(r.height)); if (w !== W || h !== H || cv.width !== w) { W = cv.width = w; H = cv.height = h; effects.forEach((e) => fill(e)); } }
    function fill(e) { if (e.type === "lightning") return; const n = Math.max(0, Math.round(BASE[e.type] * e.amount * density * (W * H) / (1280 * 720))); e.p = []; for (let i = 0; i < Math.min(n, 1500); i++) e.p.push(spawn(e, W, H, true)); }
    function set(list) {
      effects = (Array.isArray(list) ? list : []).filter((e) => e && typeof e.type === "string" && (BASE[e.type] || e.type === "lightning")).map((e) => ({ type: e.type, amount: Math.max(0, Math.min(1, e.amount == null ? 0.5 : +e.amount)), speed: e.speed > 0 ? +e.speed : 1, wind: +e.wind || 0, col: hexRGB(e.color, DEF_COL[e.type]), custom: !!e.color }));
      size(); effects.forEach(fill); flash = { a: 0, next: 2 + R() * 4, seq: [] };
    }
    function step(e, dt) {
      const p = e.p; if (!p) return;
      for (let i = 0; i < p.length; i++) {
        const q = p[i];
        if (e.type === "rain") { q.y += q.v * dt; q.x += (60 + e.wind * 340) * dt; if (q.y > H) Object.assign(q, spawn(e, W, H, false)); if (q.x > W + 100) q.x -= W + 200; if (q.x < -100) q.x += W + 200; }
        else if (e.type === "snow") { q.y += q.v * dt; q.ph += dt; q.x += (Math.sin(q.ph * 1.3) * 18 + e.wind * 80) * dt; if (q.y > H + 6) Object.assign(q, spawn(e, W, H, false)); if (q.x > W + 10) q.x = -10; if (q.x < -10) q.x = W + 10; }
        else if (e.type === "embers") { q.y -= q.v * dt; q.ph += dt * 2; q.x += (Math.sin(q.ph) * 22 + e.wind * 90) * dt; q.life += dt; if (q.life > q.max || q.y < -10) Object.assign(q, spawn(e, W, H, false)); }
        else if (e.type === "dust") { q.x += (q.vx + e.wind * 40) * dt; q.y += q.vy * dt; q.ph += dt * 0.8; if (q.x < -5) q.x = W + 5; if (q.x > W + 5) q.x = -5; if (q.y < -5) q.y = H + 5; if (q.y > H + 5) q.y = -5; }
        else if (e.type === "fireflies") { q.ang += (R() - 0.5) * 3 * dt; q.x += Math.cos(q.ang) * q.v * dt + e.wind * 20 * dt; q.y += Math.sin(q.ang) * q.v * 0.6 * dt; q.ph += dt * 2.2; if (q.x < 0) q.x = W; if (q.x > W) q.x = 0; if (q.y < H * 0.3) q.ang = Math.abs(q.ang); if (q.y > H) q.y = H * 0.3; }
        else if (e.type === "leaves") { q.y += q.v * dt; q.ph += dt * 1.5; q.x += (Math.sin(q.ph) * 40 + 30 + e.wind * 150) * dt; q.rot += q.vr * dt; if (q.y > H + 10) Object.assign(q, spawn(e, W, H, false)); if (q.x > W + 20) q.x = -20; if (q.x < -20) q.x = W + 20; }
      }
    }
    function drawE(e) {
      const p = e.p, c = e.col; if (!p) return;
      if (e.type === "rain") { g.lineWidth = 1.2; g.lineCap = "round"; const sx = (60 + e.wind * 340) / 900; for (const q of p) { g.strokeStyle = rgba(c, q.a); g.beginPath(); g.moveTo(q.x, q.y); g.lineTo(q.x + q.len * sx, q.y + q.len); g.stroke(); } }
      else if (e.type === "snow") { for (const q of p) { g.fillStyle = rgba(c, q.a); g.beginPath(); g.arc(q.x, q.y, q.r, 0, TAU); g.fill(); } }
      else if (e.type === "dust") { for (const q of p) { g.fillStyle = rgba(c, q.a * (0.6 + 0.4 * Math.sin(q.ph))); g.beginPath(); g.arc(q.x, q.y, q.r, 0, TAU); g.fill(); } }
      else if (e.type === "leaves") { for (const q of p) { g.save(); g.translate(q.x, q.y); g.rotate(q.rot); g.fillStyle = rgba(e.custom ? c : q.c, 0.9); g.beginPath(); g.ellipse(0, 0, q.s, q.s * 0.45, 0, 0, TAU); g.fill(); g.restore(); } }
      else if (e.type === "embers" || e.type === "fireflies") {
        g.globalCompositeOperation = "lighter"; const gs = glow();
        for (const q of p) {
          if (e.type === "embers") { const f = Math.max(0, 1 - q.life / q.max) * (0.65 + 0.35 * Math.sin(q.ph * 3)), r = q.r * 4; g.globalAlpha = Math.min(1, f); g.drawImage(tint(gs, c), q.x - r, q.y - r, r * 2, r * 2); }
          else { const f = Math.max(0, Math.sin(q.ph)) ** 2, r = q.r * 2.2; g.globalAlpha = 0.15 + 0.85 * f; g.drawImage(tint(gs, c), q.x - r, q.y - r, r * 2, r * 2); }
        }
        g.globalAlpha = 1; g.globalCompositeOperation = "source-over";
      }
    }
    const tintCache = new Map();
    function tint(src, c) { const k = c.join(","); let t = tintCache.get(k); if (t) return t; t = document.createElement("canvas"); t.width = t.height = 64; const x = t.getContext("2d"); x.drawImage(src, 0, 0); x.globalCompositeOperation = "source-in"; x.fillStyle = rgba(c, 1); x.fillRect(0, 0, 64, 64); tintCache.set(k, t); return t; }
    function lightning(e, dt) {
      flash.next -= dt; if (flash.next <= 0) { flash.seq = [1, 0.1, 0.8, 0.05, 0.45]; flash.i = 0; flash.t = 0; flash.next = (3 + R() * 9) / (0.4 + e.amount) / e.speed; }
      if (flash.seq.length) { flash.t += dt; const step = 0.06, i = Math.floor(flash.t / step); if (i >= flash.seq.length) { flash.seq = []; flash.a = 0; } else flash.a = flash.seq[i] * (0.25 + 0.4 * e.amount); }
    }
    function frame(now) {
      if (dead) return; raf = requestAnimationFrame(frame);
      const dt = Math.min(0.05, last ? (now - last) / 1000 : 0.016); last = now; t += dt;
      if (!vis || !effects.length) { if (lastDraw) { g.clearRect(0, 0, W, H); lastDraw = false; } return; }
      if (cv.clientWidth !== W || cv.clientHeight !== H) size();
      lastDraw = true; g.clearRect(0, 0, W, H);
      flash.a = 0;
      for (const e of effects) { if (e.type === "lightning") { if (density > 0.05) lightning(e, dt); continue; } step(e, dt); drawE(e); }
      if (flash.a > 0.01) { g.fillStyle = `rgba(215,225,255,${flash.a})`; g.fillRect(0, 0, W, H); }
    }
    raf = requestAnimationFrame(frame);
    const refill = () => effects.forEach(fill); insts.add(refill);
    return { set, setVisible(v) { vis = !!v; }, destroy() { dead = true; insts.delete(refill); cancelAnimationFrame(raf); cv.remove(); }, canvas: cv, get count() { return effects.length; } };
  }
  function setDensity(v) { v = Math.max(0, Math.min(1, +v)); if (!(v >= 0) || v === density) return; density = v; insts.forEach((f) => f()); }
  window.EnvFX = { create, setDensity, TYPES: ["rain", "snow", "embers", "dust", "fireflies", "leaves", "lightning"] };
})();

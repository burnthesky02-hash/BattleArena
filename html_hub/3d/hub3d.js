/* hub3d.js -- the Colosseum hub as a walkable 3D plaza.

   Loaded by html_hub/index.html (after /battle/battlemap.js, the GLB parser). The hub page keeps all of its
   own logic (currencies, party, ladder, navigation, tutorial, debug); this file only adds:
     - a WebGL canvas behind the DOM: Kenney GLB pieces for the town (see plaza.json), sprite billboards for the
       player (4-direction walk cycle) and the NPCs (idle sheets), blob shadows, floor glyph decals;
     - walking (WASD / arrows, click-to-move), collision, an auto-follow camera (swings behind the direction of travel; drag only tilts) and wheel zoom;
     - NPC interaction (E / Enter / Space, or click). Each NPC just triggers the hub's existing [data-action] control.
   Hub3D.init({ activate(action), sfx(url), SFX }) is called once by the page; Hub3D.onState(state) on every refresh.
   `?view=2d|3d` and localStorage `hubView` choose the view; if WebGL fails the page stays in its 2D layout. */
(function () {
  "use strict";

  const H3 = window.Hub3D = { on: false, ready: false, failed: false };
  const BASE = "/hub3d/";
  let O = null, gl = null, canvas = null, ui = null, sceneEl = null;
  let sprog = null, mprog = null, quadBuf = null, maxTex = 4096, idxUint = false, aniso = null;
  const SU = {}, MU = {}, TEX = {};
  let S = null;                                 // loaded scene: { def, items[], npcs[], sprites, colliders }
  let state = null, lastT = 0, clock = 0;
  const keys = {};
  let hudEls = {};

  /* ---------- math ---------- */
  const V = {
    sub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]], add: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]],
    mul: (a, s) => [a[0] * s, a[1] * s, a[2] * s], dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
    cross: (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]],
    norm: (a) => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; },
  };
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  function perspective(fovy, aspect, n, f) { const t = 1 / Math.tan(fovy / 2); return [t / aspect, 0, 0, 0, 0, t, 0, 0, 0, 0, (f + n) / (n - f), -1, 0, 0, 2 * f * n / (n - f), 0]; }
  function lookAt(e, c, up) {
    const z = V.norm(V.sub(e, c)), x = V.norm(V.cross(up, z)), y = V.cross(z, x);
    return { m: [x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0, -V.dot(x, e), -V.dot(y, e), -V.dot(z, e), 1], x, y, z };
  }
  function mul4(a, b) { const o = new Array(16); for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) o[c * 4 + r] = a[r] * b[c * 4] + a[4 + r] * b[c * 4 + 1] + a[8 + r] * b[c * 4 + 2] + a[12 + r] * b[c * 4 + 3]; return o; }

  /* ---------- camera ---------- */
  const cam = { yaw: 0, pitch: 33, dist: 29, fov: 34, tx: 0, tz: 8, goalYaw: 0, goalPitch: 33, goalDist: 29, vp: null, pos: [0, 10, 30], fwd: [0, 0, -1], camX: [1, 0, 0], camY: [0, 1, 0], camZ: [0, 0, 1], w: 1, h: 1, aspect: 1, free: false };
  /* ---------- terrain: scene.terrain = {x0, z0, cell, nx, nz, scale, data: base64 int16-LE heights / scale}; gh(x, z) = ground height (0 when flat) ---------- */
  function decodeTerrain(T) {
    if (!T || !T.data) return null;
    const bin = atob(T.data), n = bin.length >> 1, h = new Float32Array(n), sc = T.scale || 100;
    for (let i = 0; i < n; i++) { let v = bin.charCodeAt(2 * i) | (bin.charCodeAt(2 * i + 1) << 8); if (v & 0x8000) v -= 0x10000; h[i] = v / sc; }
    return { x0: T.x0, z0: T.z0, cell: T.cell, nx: T.nx, nz: T.nz, h };
  }
  function gh(x, z) {
    const T = S && S.terrain; if (!T) return 0;
    let fx = (x - T.x0) / T.cell, fz = (z - T.z0) / T.cell;
    fx = Math.max(0, Math.min(T.nx - 1.001, fx)); fz = Math.max(0, Math.min(T.nz - 1.001, fz));
    const i = Math.floor(fx), j = Math.floor(fz), u = fx - i, v = fz - j, h = T.h, o = j * T.nx + i;
    return (h[o] * (1 - u) + h[o + 1] * u) * (1 - v) + (h[o + T.nx] * (1 - u) + h[o + T.nx + 1] * u) * v;
  }
  function affInv(m) {                                   // inverse of a column-major affine 4x4 (rotation/scale + translation)
    const a = m[0], b = m[4], c = m[8], d = m[1], e = m[5], f = m[9], g = m[2], h = m[6], i = m[10];
    const A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g, det = a * A + b * B + c * C;
    if (Math.abs(det) < 1e-12) return null;
    const k = 1 / det, r = [A * k, (c * h - b * i) * k, (b * f - c * e) * k, B * k, (a * i - c * g) * k, (c * d - a * f) * k, C * k, (b * g - a * h) * k, (a * e - b * d) * k];   // row-major 3x3
    return { r, t: [-(r[0] * m[12] + r[1] * m[13] + r[2] * m[14]), -(r[3] * m[12] + r[4] * m[13] + r[5] * m[14]), -(r[6] * m[12] + r[7] * m[13] + r[8] * m[14])] };
  }
  /* camera collision: scale the camera's offset from the hero's head (angle unchanged) so a wall-sized collider between them is not crossed.
     Returns the fraction 0..1 of the full offset that is free. */
  const CAM_MIN = 0.7, CAM_WALL_H = 6, CAM_MARGIN = 0.55;
  function slab(o, d, lo, hi, mg) {                           // entry parameter (0..1) of a ray into a box grown by mg, or Infinity when it misses; 0 when it starts inside
    let t0 = 0, t1 = 1;
    for (let k = 0; k < 3; k++) {
      const l = lo[k] - mg, h = hi[k] + mg;
      if (Math.abs(d[k]) < 1e-9) { if (o[k] < l || o[k] > h) return Infinity; continue; }
      let a = (l - o[k]) / d[k], b = (h - o[k]) / d[k]; if (a > b) { const q = a; a = b; b = q; }
      t0 = Math.max(t0, a); t1 = Math.min(t1, b); if (t0 > t1) return Infinity;
    }
    return t0;
  }
  function boxHit(o, d, lo, hi, mg) {                         // like slab, but a hero standing within the margin (not inside the solid) gets 0 = zoom all the way in; inside the solid = ignore
    const t = slab(o, d, lo, hi, mg);
    if (t === Infinity || t > 0.02) return t;
    return inBox(o, lo, hi) ? Infinity : 0;
  }
  function inBox(o, lo, hi) { return o[0] > lo[0] && o[0] < hi[0] && o[1] > lo[1] && o[1] < hi[1] && o[2] > lo[2] && o[2] < hi[2]; }
  /* camera collision: scale the camera's offset from the hero's head (angle unchanged) so a wall between them is not crossed.
     Returns the fraction 0..1 of the full offset that is free. */
  function camLimit(eye, c0) {
    if (!S || cam.free || camOff()) return 1;
    const dv = [c0[0] - eye[0], c0[1] - eye[1], c0[2] - eye[2]], L = Math.hypot(dv[0], dv[1], dv[2]), base = cam.ty || 0;
    if (L < 1e-3) return 1;
    let best = 1;
    for (const c of S.colliders || []) {
      if (c.maxX === undefined || Math.max(c.maxX - c.minX, c.maxZ - c.minZ) < 3.5) continue;     // crates, barrels, pillars: the camera sees over them
      const t = boxHit(eye, dv, [c.minX, -1e4, c.minZ], [c.maxX, 1e4, c.maxZ], CAM_MARGIN);
      if (t === Infinity || eye[1] + dv[1] * t > base + CAM_WALL_H) continue;
      if (t < best) best = t;
    }
    for (const it of S.items) {                                          // solid pieces (wall blocks, houses, rocks): the oriented bounding box of each mesh
      if (!it.inv || it.mode !== 0 || it.inside) continue;
      if (it.top - it.bot < 2.2 || it.bot > 2.5 || Math.max(it.hi[0] - it.lo[0], it.hi[2] - it.lo[2]) * it.sc < 2.4) continue;   // floors, props, trunks, railings
      if (Math.hypot(it.center[0] - eye[0], it.center[2] - eye[2]) - it.rad * 1.5 > L) continue;
      const r = it.inv.r, t = it.inv.t;
      const o = [r[0] * eye[0] + r[1] * eye[1] + r[2] * eye[2] + t[0], r[3] * eye[0] + r[4] * eye[1] + r[5] * eye[2] + t[1], r[6] * eye[0] + r[7] * eye[1] + r[8] * eye[2] + t[2]];
      const d = [r[0] * dv[0] + r[1] * dv[1] + r[2] * dv[2], r[3] * dv[0] + r[4] * dv[1] + r[5] * dv[2], r[6] * dv[0] + r[7] * dv[1] + r[8] * dv[2]];
      const tt = boxHit(o, d, it.lo, it.hi, CAM_MARGIN / it.sc);
      if (tt === Infinity || eye[1] + dv[1] * tt > it.top) continue;     // misses, or the line clears the top
      if (tt < best) best = tt;
    }
    return Math.max(CAM_MIN / L, Math.min(1, best));
  }
  function camOff() { try { return localStorage.getItem("h3dCamAuto") !== "1"; } catch (e) { return true; } }   // wall auto-zoom is OFF (manual camera); set localStorage h3dCamAuto = "1" to try it again

  function updateCamera(dt, instant) {
    const k = instant ? 1 : 1 - Math.pow(0.0008, dt), k2 = instant ? 1 : 1 - Math.pow(0.05, dt);
    cam.yaw = lerp(cam.yaw, cam.goalYaw, k); cam.pitch = lerp(cam.pitch, cam.goalPitch, k); cam.dist = lerp(cam.dist, cam.goalDist * Math.max(1, 1.5 / cam.aspect), k2);
    if (!cam.free && S) { cam.tx = lerp(cam.tx, S.player.x, k2); cam.tz = lerp(cam.tz, S.player.z + 1.5, k2); cam.ty = instant || cam.ty === undefined ? gh(S.player.x, S.player.z) : lerp(cam.ty, gh(S.player.x, S.player.z), k2); }
    const ya = cam.yaw * Math.PI / 180, target = [cam.tx, 1.6 + (cam.ty || 0), cam.tz];
    let pi = cam.pitch * Math.PI / 180;
    if (cam.eff !== undefined && cam.eff < 6) { const kk = Math.max(0, Math.min(1, (6 - cam.eff) / 4.5)); pi += (8 * Math.PI / 180 - pi) * kk * kk * (3 - 2 * kk); }   // close in: level the view out, like first person
    const full = V.add(target, [Math.sin(ya) * Math.cos(pi) * cam.dist, Math.sin(pi) * cam.dist, Math.cos(ya) * Math.cos(pi) * cam.dist]);
    /* auto zoom: keep the angle, pull the whole offset in toward the hero's head when a wall is in the way (down to first person) */
    const eye = S && !cam.free ? [S.player.x, 1.6 + (cam.ty || 0), S.player.z] : target, fw = camLimit(eye, full);
    cam.lim = instant || cam.lim === undefined ? fw : (fw < cam.lim ? lerp(cam.lim, fw, 1 - Math.pow(0.0001, dt)) : lerp(cam.lim, fw, 1 - Math.pow(0.12, dt)));
    const pos = cam.lim >= 0.999 ? full : V.add(eye, V.mul(V.sub(full, eye), cam.lim));
    cam.eff = V.len ? V.len(V.sub(pos, eye)) : cam.dist * cam.lim;
    if (cam.lim < 0.999) { target[0] = eye[0] + (target[0] - eye[0]) * cam.lim; target[2] = eye[2] + (target[2] - eye[2]) * cam.lim; }
    const L = lookAt(pos, target, [0, 1, 0]);
    cam.pos = pos; cam.camX = L.x; cam.camY = L.y; cam.camZ = L.z; cam.fwd = V.mul(L.z, -1);
    cam.vp = mul4(perspective(cam.fov * Math.PI / 180, cam.aspect, 0.5, 220), L.m);
  }
  function project(p) {
    const m = cam.vp, x = p[0], y = p[1], z = p[2];
    const cx = m[0] * x + m[4] * y + m[8] * z + m[12], cy = m[1] * x + m[5] * y + m[9] * z + m[13], cw = m[3] * x + m[7] * y + m[11] * z + m[15];
    return { x: (cx / cw * 0.5 + 0.5) * cam.w, y: (1 - (cy / cw * 0.5 + 0.5)) * cam.h, w: cw };
  }
  function groundAt(sx, sy) {                    // screen px -> point on the y=0 plane (or null)
    const t = Math.tan(cam.fov * Math.PI / 360), nx = (sx / cam.w * 2 - 1) * t * cam.aspect, ny = (1 - sy / cam.h * 2) * t;
    const d = V.norm(V.add(V.add(V.mul(cam.camX, nx), V.mul(cam.camY, ny)), V.mul(cam.camZ, -1)));
    if (d[1] > -0.01) return null;
    let h = 0, px = 0, pz = 0;
    for (let k = 0; k < 5; k++) { const s = (h - cam.pos[1]) / d[1]; px = cam.pos[0] + d[0] * s; pz = cam.pos[2] + d[2] * s; h = gh(px, pz); }
    return { x: px, z: pz };
  }

  /* ---------- GL: sprite billboards ---------- */
  const SVS = `
attribute vec2 a; uniform mat4 u_vp; uniform vec3 u_o, u_r, u_u; uniform vec2 u_size, u_anchor; varying vec2 v_uv;
void main(){ vec2 p = (a - u_anchor) * u_size; gl_Position = u_vp * vec4(u_o + u_r * p.x + u_u * p.y, 1.0); v_uv = a; }`;
  const SFS = `
precision mediump float; uniform sampler2D u_tex; uniform vec4 u_rect; uniform float u_flip; uniform vec4 u_tint; uniform vec3 u_fogc; uniform vec2 u_fogr; uniform float u_fogd;
varying vec2 v_uv;
void main(){
  vec2 uv = v_uv; if (u_flip > .5) uv.x = 1.0 - uv.x;
  vec2 t = u_rect.xy + vec2(uv.x, 1.0 - uv.y) * u_rect.zw;
  vec4 c = texture2D(u_tex, t);
  c.rgb *= u_tint.rgb;
  float f = clamp((u_fogd - u_fogr.x) / (u_fogr.y - u_fogr.x), 0.0, 1.0) * 0.8;
  c.rgb = mix(c.rgb, u_fogc * c.a, f);
  gl_FragColor = c * u_tint.a;
}`;
  /* ---------- GL: lit meshes ---------- */
  const MVS = `
attribute vec3 p; attribute vec3 n; attribute vec2 t; attribute vec4 c;
uniform mat4 u_vp; uniform mat4 u_model; varying vec3 v_n; varying vec2 v_t; varying vec4 v_c; varying float v_d;
void main(){ gl_Position = u_vp * (u_model * vec4(p, 1.0)); v_n = mat3(u_model) * n; v_t = t; v_c = c; v_d = gl_Position.w; }`;
  const MFS = `
precision mediump float;
uniform sampler2D u_tex; uniform vec4 u_color; uniform vec3 u_emis; uniform float u_cut, u_unlit, u_mode;
uniform vec3 u_ldir, u_lcol, u_amb, u_fogc; uniform vec2 u_fogr;
varying vec3 v_n; varying vec2 v_t; varying vec4 v_c; varying float v_d;
void main(){
  vec4 base = texture2D(u_tex, v_t) * u_color * v_c;
  if (u_mode > 0.5 && u_mode < 1.5 && base.a < u_cut) discard;
  vec3 N = normalize(v_n); if (!gl_FrontFacing) N = -N;
  float ndl = max(dot(N, -u_ldir), 0.0), hemi = N.y * 0.5 + 0.5;
  vec3 col = u_unlit > 0.5 ? base.rgb : base.rgb * (u_amb * (0.6 + 0.4 * hemi) + u_lcol * ndl) + u_emis;
  col = mix(col, u_fogc, clamp((v_d - u_fogr.x) / (u_fogr.y - u_fogr.x), 0.0, 1.0));
  float a = u_mode > 1.5 ? base.a : 1.0;
  gl_FragColor = vec4(col * a, a);
}`;
  function mkShader(type, src) { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; }
  function mkProg(vs, fs, attrs) {
    const p = gl.createProgram(); gl.attachShader(p, mkShader(gl.VERTEX_SHADER, vs)); gl.attachShader(p, mkShader(gl.FRAGMENT_SHADER, fs));
    attrs.forEach((n, i) => gl.bindAttribLocation(p, i, n)); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    return p;
  }
  function useSprite() { gl.useProgram(sprog); gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf); gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0); for (let i = 1; i < 4; i++) gl.disableVertexAttribArray(i); }
  function useMesh() { gl.useProgram(mprog); for (let i = 0; i < 4; i++) gl.enableVertexAttribArray(i); }

  function makeTexture(source, opts) {
    const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source);
    const w = source.width || source.naturalWidth, h = source.height || source.naturalHeight, pot = !(w & (w - 1)) && !(h & (h - 1));
    const rep = opts && opts.repeat && pot, mip = opts && opts.mip && pot;
    if (mip) gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, rep ? gl.REPEAT : gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, rep ? gl.REPEAT : gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, mip ? gl.LINEAR_MIPMAP_LINEAR : gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    if (mip && aniso) gl.texParameterf(gl.TEXTURE_2D, aniso.TEXTURE_MAX_ANISOTROPY_EXT, Math.min(8, gl.getParameter(aniso.MAX_TEXTURE_MAX_ANISOTROPY_EXT)));
    return t;
  }
  function canvasTex(w, h, draw, opts) { const c = document.createElement("canvas"); c.width = w; c.height = h; draw(c.getContext("2d"), w, h); return makeTexture(c, opts); }
  const BLEND_N = () => gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA), BLEND_ADD = () => gl.blendFunc(gl.ONE, gl.ONE);

  function drawQuad(o) {
    gl.uniform3fv(SU.u_o, o.origin); gl.uniform3fv(SU.u_r, o.right); gl.uniform3fv(SU.u_u, o.up);
    gl.uniform2f(SU.u_size, o.w, o.h); gl.uniform2f(SU.u_anchor, o.ax === undefined ? 0.5 : o.ax, o.ay === undefined ? 0 : o.ay);
    gl.bindTexture(gl.TEXTURE_2D, o.tex);
    const r = o.rect || [0, 0, 1, 1]; gl.uniform4f(SU.u_rect, r[0], r[1], r[2], r[3]);
    gl.uniform1f(SU.u_flip, o.flip ? 1 : 0);
    const t = o.tint || [1, 1, 1, 1]; gl.uniform4f(SU.u_tint, t[0], t[1], t[2], t[3]);
    gl.uniform1f(SU.u_fogd, o.fogd === undefined ? 0 : o.fogd);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  function buildTextures() {
    TEX.white = canvasTex(4, 4, (g, w, h) => { g.fillStyle = "#fff"; g.fillRect(0, 0, w, h); });
    TEX.shadow = canvasTex(128, 128, (g, w, h) => { const r = g.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2); r.addColorStop(0, "rgba(0,0,0,.7)"); r.addColorStop(0.6, "rgba(0,0,0,.3)"); r.addColorStop(1, "rgba(0,0,0,0)"); g.fillStyle = r; g.fillRect(0, 0, w, h); });
    TEX.ring = canvasTex(256, 256, (g, w, h) => {
      g.strokeStyle = "#fff"; g.lineWidth = 8; g.beginPath(); g.arc(w / 2, h / 2, w / 2 - 14, 0, 7); g.stroke();
      g.strokeStyle = "rgba(255,255,255,.3)"; g.lineWidth = 22; g.beginPath(); g.arc(w / 2, h / 2, w / 2 - 18, 0, 7); g.stroke();
    });
    TEX.glow = canvasTex(128, 128, (g, w, h) => { const r = g.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2); r.addColorStop(0, "rgba(255,255,255,.9)"); r.addColorStop(1, "rgba(255,255,255,0)"); g.fillStyle = r; g.fillRect(0, 0, w, h); });
    TEX.sky = canvasTex(4, 256, (g, w, h) => {
      const r = g.createLinearGradient(0, 0, 0, h);
      r.addColorStop(0, "#14103a"); r.addColorStop(0.45, "#3a2a6a"); r.addColorStop(0.72, "#b0507a"); r.addColorStop(0.9, "#f09a6a"); r.addColorStop(1, "#ffd08a");
      g.fillStyle = r; g.fillRect(0, 0, w, h);
    });
    // summoning-circle glyphs (additive floor decal)
    TEX.glyph = canvasTex(512, 512, (g, w, h) => {
      const c = w / 2; g.translate(c, c); g.lineCap = "round";
      g.shadowColor = "#b58cff"; g.shadowBlur = 14; g.strokeStyle = "#e4d4ff";
      [[236, 5], [214, 2.5], [150, 3], [96, 2]].forEach(([r, lw]) => { g.lineWidth = lw; g.beginPath(); g.arc(0, 0, r, 0, 7); g.stroke(); });
      g.lineWidth = 3; g.beginPath(); for (let i = 0; i < 6; i++) { const a = i * Math.PI / 3 - Math.PI / 2; g.lineTo(Math.cos(a) * 150, Math.sin(a) * 150); } g.closePath(); g.stroke();
      g.beginPath(); for (let i = 0; i < 6; i++) { const a = i * Math.PI / 3 + Math.PI / 6; g.lineTo(Math.cos(a) * 150, Math.sin(a) * 150); } g.closePath(); g.stroke();
      g.lineWidth = 3;
      for (let i = 0; i < 24; i++) { const a = i / 24 * Math.PI * 2; g.save(); g.rotate(a); g.beginPath(); g.moveTo(0, -226); g.lineTo(0, -(i % 2 ? 238 : 250)); g.stroke(); if (i % 2 === 0) { g.beginPath(); g.moveTo(-9, -190); g.lineTo(0, -202); g.lineTo(9, -190); g.stroke(); } g.restore(); }
    });
  }

  /* ---------- GLB pieces ---------- */
  const modelCache = new Map(), imageCache = new Map();
  function uploadObject(o) {
    const vc = o.positions.length / 3, data = new Float32Array(vc * 12);
    for (let i = 0; i < vc; i++) { data.set(o.positions.subarray(i * 3, i * 3 + 3), i * 12); data.set(o.normals.subarray(i * 3, i * 3 + 3), i * 12 + 3); data.set(o.uvs.subarray(i * 2, i * 2 + 2), i * 12 + 6); data.set(o.colors.subarray(i * 4, i * 4 + 4), i * 12 + 8); }
    const vbo = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, vbo); gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    let idx = o.indices, itype = gl.UNSIGNED_SHORT;
    if (vc > 65535) { if (!idxUint) return null; itype = gl.UNSIGNED_INT; } else idx = Uint16Array.from(idx);
    const ibo = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ibo); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, idx, gl.STATIC_DRAW);
    return { vbo, ibo, count: idx.length, itype };
  }
  function meshTexture(im, baseUrl) {
    const key = im.uri ? new URL(im.uri, baseUrl).href : null;
    if (key && imageCache.has(key)) return imageCache.get(key);
    const pr = (async () => {
      let blob;
      if (im.bytes) blob = new Blob([im.bytes], { type: im.mime }); else { const r = await fetch(key); if (!r.ok) throw new Error("texture " + im.uri); blob = await r.blob(); }
      const bmp = await createImageBitmap(blob, { premultiplyAlpha: "none", colorSpaceConversion: "none" });
      const pot = (v) => Math.min(maxTex, 2048, 1 << Math.max(0, Math.round(Math.log2(Math.max(1, v)))));
      const cv = document.createElement("canvas"); cv.width = pot(bmp.width); cv.height = pot(bmp.height); cv.getContext("2d").drawImage(bmp, 0, 0, cv.width, cv.height);
      gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
      const t = makeTexture(cv, { repeat: true, mip: true });
      gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
      return t;
    })();
    if (key) imageCache.set(key, pr);
    return pr;
  }
  function loadModel(url) {
    if (modelCache.has(url)) return modelCache.get(url);
    const pr = (async () => {
      const r = await fetch(encodeURI(url)); if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
      const parsed = window.B3DMap.parse(await r.arrayBuffer());
      const base = new URL(encodeURI(url), location.href);
      const texs = await Promise.all(parsed.images.map((im) => meshTexture(im, base).catch(() => null)));
      return { parsed, texs, gpu: parsed.objects.map((o) => { const g = uploadObject(o); return g ? { g, o } : null; }).filter(Boolean) };
    })();
    modelCache.set(url, pr); return pr;
  }
  function trs(x, y, z, rotDeg, s) { const a = rotDeg * Math.PI / 360; return window.B3DMap.mat4TRS([x, y, z], [0, Math.sin(a), 0, Math.cos(a)], [s, s, s]); }

  /* ---------- scene ---------- */
  function loadImage(url) { return new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = () => rej(new Error(url)); im.src = url; }); }

  /* ---------- sky / environment ----------
     scene.sky: omitted = built-in dusk gradient | "painted" | [r,g,b] | {type:"color",color:[r,g,b]}
                | {type:"gradient",stops:[[0,"#hex"],...]}  (0 = top of the sky, 1 = horizon)
                | {type:"image",url:"/assets/Backgrounds/x.webp"} */
  const PAINTED_URL = "/assets/Artwork/Background.webp";
  const hexRGB = (s) => { s = String(s || "#000").replace("#", ""); if (s.length === 3) s = s.replace(/./g, "$&$&"); return [0, 2, 4].map((i) => (parseInt(s.substr(i, 2), 16) || 0) / 255); };
  async function buildSky(sky) {
    try {
      if (Array.isArray(sky)) sky = { type: "color", color: sky };
      if (sky === "painted") sky = { type: "image", url: PAINTED_URL };
      if (!sky || typeof sky !== "object") return null;
      if (sky.type === "color") return { kind: "color", clear: (sky.color || [0.1, 0.08, 0.2]).slice(0, 3) };
      if (sky.type === "gradient" && Array.isArray(sky.stops) && sky.stops.length) {
        const st = sky.stops.map((s) => [Math.max(0, Math.min(1, +s[0] || 0)), s[1]]).sort((a, b) => a[0] - b[0]);
        return { kind: "gradient", clear: hexRGB(st[st.length - 1][1]), tex: canvasTex(4, 256, (g, w, h) => { const r = g.createLinearGradient(0, 0, 0, h); st.forEach(([p, c]) => r.addColorStop(p, c)); g.fillStyle = r; g.fillRect(0, 0, w, h); }) };
      }
      if (sky.type === "layers" && Array.isArray(sky.layers)) {
        const base = sky.base ? await buildSky(sky.base) : null, layers = [];
        for (const d of sky.layers.slice(0, 12)) { if (!d || !d.url) continue; try { const im = await loadImage(encodeURI(d.url)); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true); layers.push({ def: d, tex: makeTexture(im, {}), aspect: im.naturalWidth / im.naturalHeight }); } catch (e) { console.warn("[H3D] sky layer failed:", d.url); } }
        return { kind: "layers", clear: base ? base.clear : [0.12, 0.08, 0.22], base, layers };
      }
      if (sky.type === "image" && sky.url) {
        const im = await loadImage(encodeURI(sky.url)); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
        return { kind: "image", clear: [0.05, 0.04, 0.1], tex: makeTexture(im, {}), aspect: im.naturalWidth / im.naturalHeight };
      }
    } catch (e) { console.warn("[H3D] sky failed, using the default:", e); }
    return null;
  }
  /* a piece's 7th element: "key" = hide once set, "!key" = show once set, "H:<spec>" / "S:<spec>" = hide / show when a flag spec holds (see has()) */
  function pieceVis(v) {
    if (v.slice(0, 2) === "H:") return { hideIf: v.slice(2) };
    if (v.slice(0, 2) === "S:") return { showIf: v.slice(2) };
    return v[0] === "!" ? { showIf: v.slice(1) } : { hideIf: v };
  }
  async function loadScene(name, onProgress) {
    const def = await (await fetch(BASE + name + ".json", { cache: "no-store" })).json();
    const kit = def.kit || "";
    const sheets = await (await fetch(BASE + "sprites.json", { cache: "no-store" })).json();
    // pieces: [model, x, z, rotY, y, scale]
    const names = [...new Set(def.pieces.map((p) => p[0]))];
    let done = 0;
    const models = {};
    await Promise.all(names.map(async (n) => { models[n] = await loadModel(kit + n + ".glb"); onProgress && onProgress(++done / (names.length + 1)); }));
    const T = def.tile || 4, items = [], cleared = getCleared();
    for (const p of def.pieces) {
      let ins = null;                                   // "I:x0,z0,x1,z1" = hidden while the player stands inside that rectangle (roofs of enterable buildings)
      if (typeof p[6] === "string" && p[6].slice(0, 2) === "I:") ins = p[6].slice(2).split(",").map(Number);
      else if (p[6] && !visible(pieceVis(p[6]), cleared)) continue;
      const [name, x, z, rot, y, sc] = p, mdl = models[name], s = sc === undefined || sc === null ? T : sc, mm = trs(x, y || 0, z, rot || 0, s);
      for (const { g, o } of mdl.gpu) {
        const lo = o.min, hi = o.max, cx = (lo[0] + hi[0]) / 2, cz = (lo[2] + hi[2]) / 2;
        const c = [mm[0] * cx + mm[8] * cz + mm[12], (lo[1] + hi[1]) / 2 * s + (y || 0), mm[2] * cx + mm[10] * cz + mm[14]];
        const m = o.material;
        items.push({ g, mat: m, inside: ins, model: new Float32Array(mm), lo, hi, sc: s, inv: affInv(mm), bot: lo[1] * s + (y || 0), center: c, top: hi[1] * s + (y || 0), rad: Math.max(hi[0] - lo[0], hi[2] - lo[2]) * s / 2,
          tex: m.image >= 0 ? mdl.texs[m.image] : null, mode: m.alphaMode === "BLEND" ? 2 : m.alphaMode === "MASK" ? 1 : 0 });
      }
    }
    // sprite textures
    const wanted = new Set(); Object.values(sheets.walk).forEach((w) => wanted.add(w.file));
    (def.npcs || []).forEach((n) => { if (n.sprite && sheets.npcs[n.sprite]) wanted.add(sheets.npcs[n.sprite].file); });
    const stex = {};
    await Promise.all([...wanted].map(async (f) => { const im = await loadImage(BASE + f); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true); stex[f] = makeTexture(im, {}); }));
    onProgress && onProgress(1);
    const npcs = (def.npcs || []).filter((n) => visible(n, cleared)).map((n) => Object.assign({ radius: 1.1, h: 2.3, phase: Math.random() * 10, bossTex: null }, n, { sheet: n.sprite ? sheets.npcs[n.sprite] : null }));
    // Static art for hostile NPCs: html_hub/3d/stills.json maps scene -> { npcId: "Bosses/.../Art.png" } (under /assets/).
    // The image is cropped to its visible bounds and drawn as an upright billboard, like the Colosseum boss card.
    try {
      const stills = await (await fetch(BASE + "stills.json", { cache: "no-store" })).json();
      const mine = (stills && stills[name]) || {};
      await Promise.all(npcs.map(async (n) => {
        const path = n.still || mine[n.id]; if (!path) return;
        try {
          const im = await loadImage("/assets/" + path);
          const c = document.createElement("canvas"); c.width = im.naturalWidth; c.height = im.naturalHeight;
          const g2 = c.getContext("2d", { willReadFrequently: true }); g2.drawImage(im, 0, 0);
          const d = g2.getImageData(0, 0, c.width, c.height).data; let x0 = c.width, y0 = c.height, x1 = -1, y1 = -1;
          for (let y = 0; y < c.height; y++) for (let x = 0; x < c.width; x++) if (d[(y * c.width + x) * 4 + 3] > 24) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
          if (x1 < x0) return;
          const bw = x1 - x0 + 1, bh = y1 - y0 + 1, c2 = document.createElement("canvas"); c2.width = bw; c2.height = bh;
          c2.getContext("2d").drawImage(c, x0, y0, bw, bh, 0, 0, bw, bh);
          gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
          n.bossTex = { tex: makeTexture(c2, {}), aspect: bw / bh }; n.still = path;
        } catch (e) { /* art missing: keep the walking sprite */ }
      }));
    } catch (e) { /* no stills.json */ }
    const colliders = (def.colliders || []).filter((c) => visible(c, cleared)).map((c) => ({ minX: c.x - c.w / 2, maxX: c.x + c.w / 2, minZ: c.z - c.d / 2, maxZ: c.z + c.d / 2 }));
    const events = (def.events || []).filter((e) => visible(e, cleared)).map((e) => Object.assign({ w: 3, d: 3, trigger: "touch", inside: false, done: false }, e));
    const skyInfo = await buildSky(def.sky);
    return { name, def, skyInfo, items, npcs, events, sheets, stex, colliders, terrain: decodeTerrain(def.terrain), bounds: def.bounds || { minX: -24, maxX: 24, minZ: -16, maxZ: 16 },
      player: { x: def.spawn ? def.spawn.x : 0, z: def.spawn ? def.spawn.z : 8, face: "south", moving: false, t: 0, target: null, wantNpc: null, h: def.playerHeight || 2.3 } };
  }

  /* ---------- drawing ---------- */
  function drawMap() {
    const d = S.def, L = d.light || {}, F = d.fog || {};
    useMesh(); gl.uniformMatrix4fv(MU.u_vp, false, cam.vp); gl.uniform1i(MU.u_tex, 0);
    const ld = V.norm(L.dir || [-0.5, -1, -0.35]), lc = L.color || [1, 0.9, 0.75], am = L.ambient || [0.55, 0.5, 0.62], fc = F.color || [0.4, 0.28, 0.4];
    gl.uniform3f(MU.u_ldir, ld[0], ld[1], ld[2]); gl.uniform3f(MU.u_lcol, lc[0], lc[1], lc[2]); gl.uniform3f(MU.u_amb, am[0], am[1], am[2]);
    gl.uniform3f(MU.u_fogc, fc[0], fc[1], fc[2]); gl.uniform2f(MU.u_fogr, F.near === undefined ? 70 : F.near, F.far === undefined ? 190 : F.far);
    gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL); gl.depthMask(true);
    const opaque = [], blend = [];
    const pp = S.player;
    for (const it of S.items) {
      if (it.inside && pp.x > it.inside[0] && pp.x < it.inside[2] && pp.z > it.inside[1] && pp.z < it.inside[3]) continue;
      (it.mode === 2 ? blend : opaque).push(it);
    }
    const draw = (it) => {
      const g = it.g, m = it.mat;
      gl.bindBuffer(gl.ARRAY_BUFFER, g.vbo);
      gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 48, 0); gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 48, 12); gl.vertexAttribPointer(2, 2, gl.FLOAT, false, 48, 24); gl.vertexAttribPointer(3, 4, gl.FLOAT, false, 48, 32);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, g.ibo);
      gl.uniformMatrix4fv(MU.u_model, false, it.model);
      gl.uniform4f(MU.u_color, m.color[0], m.color[1], m.color[2], m.color[3]); gl.uniform3f(MU.u_emis, m.emissive[0], m.emissive[1], m.emissive[2]);
      gl.uniform1f(MU.u_cut, m.cutoff); gl.uniform1f(MU.u_unlit, m.unlit ? 1 : 0); gl.uniform1f(MU.u_mode, it.mode);
      gl.bindTexture(gl.TEXTURE_2D, it.tex || TEX.white);
      gl.drawElements(gl.TRIANGLES, g.count, g.itype, 0);
    };
    BLEND_N(); opaque.forEach(draw);
    if (blend.length) { gl.depthMask(false); blend.forEach(draw); }
    useSprite(); gl.uniformMatrix4fv(SU.u_vp, false, cam.vp);
  }

  function drawSky() {
    const dist = 150, vh = 2 * dist * Math.tan(cam.fov * Math.PI / 360), vw = vh * cam.aspect;
    let sk = S.skyInfo; const center = V.add(cam.pos, V.mul(cam.fwd, dist)); BLEND_N();
    const layers = sk && sk.kind === "layers" ? sk : null; if (layers) sk = layers.base;
    if (!sk) {                                                   // built-in dusk
      const hor = -cam.pitch * 0.012 * vh;                         // horizon glides with the camera pitch
      drawQuad({ tex: TEX.sky, origin: V.add(center, V.mul(cam.camY, hor + vh * 0.12)), right: cam.camX, up: cam.camY, w: vw * 1.2, h: vh * 2.2, ax: 0.5, ay: 0.5, fogd: 0 });
    } else if (sk.kind !== "color") {
      let w, h; if (sk.kind === "image") { w = Math.max(vw * 1.12, vh * 1.12 * sk.aspect); h = w / sk.aspect; } else { w = vw * 1.2; h = vh * 1.5; }
      const room = Math.max(0, (h - vh) / 2 * 0.92), lift = Math.max(-room, Math.min(room, -cam.pitch * 0.012 * vh));
      drawQuad({ tex: sk.tex, origin: V.add(center, V.mul(cam.camY, lift)), right: cam.camX, up: cam.camY, w, h, ax: 0.5, ay: 0.5, fogd: 0 });
    }
    if (layers) drawSkyLayers(layers, dist, cam.yaw, cam.pitch);
  }

  /* parallax sky layers: {url, parallax (yaw factor, .3), drift (screen widths/sec), y (centre, 0=top 1=bottom), height (of view), alpha, tint [r,g,b], pulse, period, tile} */
  function drawSkyLayers(sk, dist, yaw, pitch) {
    const vh = 2 * dist * Math.tan(cam.fov * Math.PI / 360), vw = vh * cam.aspect, center = V.add(cam.pos, V.mul(cam.fwd, dist)), t = performance.now() / 1000;
    BLEND_N();
    for (const L of sk.layers) {
      const d = L.def, par = d.parallax == null ? 0.3 : +d.parallax, hh = (d.height == null ? 0.35 : +d.height) * vh, ww = hh * L.aspect, yc = d.y == null ? 0.35 : +d.y;
      const shift = (-yaw * 0.0009 * par + (d.drift || 0) * t) * vw, lift = Math.max(-vh * 0.2, Math.min(vh * 0.2, -pitch * 0.012 * vh * (0.4 + par)));
      const pulse = d.pulse ? 1 - d.pulse * (0.5 + 0.5 * Math.sin(t * 6.2832 / (d.period || 6))) : 1, a = (d.alpha == null ? 1 : +d.alpha) * pulse, tn = d.tint || [1, 1, 1];
      const o = V.add(center, V.mul(cam.camY, vh * (0.5 - yc) + lift));
      const tile = d.tile !== false, base = tile ? ((shift % ww) + ww) % ww : shift, k0 = Math.floor((-vw * 0.62 - base) / ww), n = tile ? Math.ceil(vw * 1.24 / ww) + 2 : 1;
      for (let i = 0; i < n; i++) {
        const cx = tile ? base + (k0 + i) * ww : base;
        drawQuad({ tex: L.tex, origin: V.add(o, V.mul(cam.camX, cx)), right: cam.camX, up: cam.camY, w: ww, h: hh, ax: 0.5, ay: 0.5, tint: [tn[0], tn[1], tn[2], a], fogd: 0 });
      }
    }
  }

  const SPR_H = (s, def) => s.h || def;
  function spriteQuad(sheet, h) {
    const k = h / sheet.refH;
    return { w: sheet.cw * k, h: sheet.ch * k, ax: sheet.footX / sheet.cw, ay: 1 - sheet.footY / sheet.ch };
  }
  function drawSpriteFrame(texKey, sheet, frame, wx, wz, h, flip, tint) {
    const q = spriteQuad(sheet, h), col = frame % sheet.cols, row = Math.floor(frame / sheet.cols);
    const right = V.norm([cam.camX[0], 0, cam.camX[2]]);
    drawQuad({ tex: S.stex[texKey], origin: [wx, gh(wx, wz), wz], right, up: [0, 1, 0], w: q.w, h: q.h, ax: flip ? 1 - q.ax : q.ax, ay: q.ay, flip,
      rect: [col / sheet.cols, row / sheet.rows, 1 / sheet.cols, 1 / sheet.rows], tint: tint || [1, 1, 1, 1], fogd: Math.hypot(wx - cam.pos[0], wz - cam.pos[2]) });
  }

  let fx = null;
  function syncFx() {
    if (!window.EnvFX) return;
    if (!fx) fx = EnvFX.create(sceneEl, canvas);
    if (S && !S.fxDone) { S.fxDone = true; fx.set(S.def.fx); }
    fx.setVisible(H3.on);
  }
  function render(now) {
    syncFx();
    const ck = S.skyInfo ? S.skyInfo.clear : [0.12, 0.08, 0.22];
    gl.depthMask(true); gl.clearColor(ck[0], ck[1], ck[2], 1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    useSprite(); gl.uniformMatrix4fv(SU.u_vp, false, cam.vp);
    const F = S.def.fog || {}, fc = F.color || [0.4, 0.28, 0.4];
    gl.uniform3f(SU.u_fogc, fc[0], fc[1], fc[2]); gl.uniform2f(SU.u_fogr, F.near === undefined ? 70 : F.near, F.far === undefined ? 190 : F.far);
    gl.disable(gl.DEPTH_TEST); drawSky();
    drawMap();
    gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL); gl.depthMask(false);

    // floor decals: glyph circles (additive, slowly turning) and soft light pools
    BLEND_ADD();
    if (S._decFor !== S.def) { S._decFor = S.def; const cl = getCleared(); S._dec = (S.def.decals || []).filter((d) => visible(d, cl)); }
    for (const dc of S._dec) {
      const a = (dc.spin ? clock * dc.spin : 0) * Math.PI / 180, c = Math.cos(a), s = Math.sin(a), pulse = 0.8 + 0.2 * Math.sin(clock * 2 + dc.x);
      const col = dc.color || [0.7, 0.55, 1, 1];
      drawQuad({ tex: dc.type === "glow" ? TEX.glow : TEX.glyph, origin: [dc.x, gh(dc.x, dc.z) + 0.06, dc.z], right: [c, 0, s], up: [-s, 0, c],
        w: dc.r * 2, h: dc.r * 2, ax: 0.5, ay: 0.5, tint: [col[0] * pulse, col[1] * pulse, col[2] * pulse, 1] });
    }
    BLEND_N();
    // active NPC ring
    const act = S.active;
    // shadows
    const actors = [{ x: S.player.x, z: S.player.z, w: 1.6 }].concat(S.npcs.map((n) => ({ x: n.x, z: n.z, w: (n.h || 2.3) * 0.7 })));
    for (const a of actors) drawQuad({ tex: TEX.shadow, origin: [a.x, gh(a.x, a.z) + 0.04, a.z], right: [1, 0, 0], up: [0, 0, -1], w: a.w, h: a.w * 0.55, ax: 0.5, ay: 0.5 });
    if (act) { BLEND_ADD(); const p = 0.7 + 0.3 * Math.sin(clock * 6); drawQuad({ tex: TEX.ring, origin: [act.x, gh(act.x, act.z) + 0.08, act.z], right: [1, 0, 0], up: [0, 0, -1], w: 2.6, h: 2.6, ax: 0.5, ay: 0.5, tint: [1, 0.85, 0.4, p] }); BLEND_N(); }
    if (S.player.target) { BLEND_ADD(); const p = 0.6 + 0.4 * Math.sin(clock * 8); drawQuad({ tex: TEX.ring, origin: [S.player.target.x, gh(S.player.target.x, S.player.target.z) + 0.08, S.player.target.z], right: [1, 0, 0], up: [0, 0, -1], w: 1.1, h: 1.1, ax: 0.5, ay: 0.5, tint: [0.6, 0.9, 1, p] }); BLEND_N(); }

    // sprites, farthest first
    const right = V.norm([cam.camX[0], 0, cam.camX[2]]);
    const list = [];
    const pl = S.player;
    list.push({ k: "player", x: pl.x, z: pl.z });
    for (const n of S.npcs) list.push({ k: "npc", n, x: n.x, z: n.z });
    list.forEach((o) => { o.d = (o.x - cam.pos[0]) * cam.fwd[0] + (o.z - cam.pos[2]) * cam.fwd[2]; });
    list.sort((a, b) => b.d - a.d);
    for (const o of list) {
      if (o.k === "player") {
        const dirKey = pl.face, sh = S.sheets.walk[dirKey], frame = pl.moving ? Math.floor(pl.t * 11) % sh.count : 0;
        const fade = cam.eff !== undefined && cam.eff < 4.5 ? Math.max(0, Math.min(1, (cam.eff - 1.6) / 2.6)) : 1;   // close-up: the hero fades out, first person at the end
        if (fade > 0.02) drawSpriteFrame(sh.file, sh, frame, pl.x, pl.z, pl.h, false, fade < 1 ? [1, 1, 1, fade] : null);
      } else {
        const n = o.n;
        if (n.bossTex) {
          const bt = n.bossTex, h = n.h, w = h * bt.aspect, tint = n.locked ? [0.35, 0.35, 0.42, 1] : [1, 1, 1, 1];
          drawQuad({ tex: bt.tex, origin: [n.x, gh(n.x, n.z) + (n.base || 0), n.z], right, up: [0, 1, 0], w, h, ax: 0.5, ay: 0, tint, fogd: o.d });
        } else if (n.sheet) {
          const toP = (S.player.x - n.x) * right[0] + (S.player.z - n.z) * right[2];
          const faceRight = Math.abs(toP) < 0.3 ? !n.faceLeft : toP > 0;
          const frame = Math.floor((clock + n.phase) * 8) % n.sheet.count;
          drawSpriteFrame(n.sheet.file, n.sheet, frame, n.x, n.z, n.h, !faceRight, n.tint ? [n.tint[0], n.tint[1], n.tint[2], 1] : null);
        }
      }
    }
  }

  /* ---------- player movement & interaction ---------- */
  function noclipOn() { try { return localStorage.getItem("h3dNoclip") === "1"; } catch (e) { return false; } }   // debug menu: walk through walls
  function blocked(x, z, r) {
    if (noclipOn()) return false;
    const b = S.bounds;
    if (x < b.minX + r || x > b.maxX - r || z < b.minZ + r || z > b.maxZ - r) return true;
    for (const c of S.colliders) if (x > c.minX - r && x < c.maxX + r && z > c.minZ - r && z < c.maxZ + r) return true;
    for (const n of S.npcs) if (!n.noBlock && Math.hypot(x - n.x, z - n.z) < r + (n.radius || 1) * 0.6) return true;
    return false;
  }
  /* ---------- click-to-move pathfinding: grid A* around colliders, string-pulled into a few straight legs ---------- */
  const PF = { cell: 0.75, maxExpand: 60000, rad: 0.7 };
  function pfClear(x0, z0, x1, z1) {                       // straight walk possible? (sampled with a slightly fat body)
    const d = Math.hypot(x1 - x0, z1 - z0), n = Math.max(1, Math.ceil(d / 0.3));
    for (let i = 1; i <= n; i++) { const t = i / n; if (blocked(x0 + (x1 - x0) * t, z0 + (z1 - z0) * t, PF.rad)) return false; }
    return true;
  }
  function findPath(sx, sz, gx, gz) {                      // -> {pts:[{x,z},...], goal:{x,z}}; pts excludes the start and ends at (a reachable stand-in for) the goal
    const b = S.bounds, c = PF.cell, nx = Math.ceil((b.maxX - b.minX) / c), nz = Math.ceil((b.maxZ - b.minZ) / c);
    const cx = (i) => b.minX + (i + 0.5) * c, cz = (j) => b.minZ + (j + 0.5) * c;
    const ci = (x) => Math.max(0, Math.min(nx - 1, Math.floor((x - b.minX) / c))), cj = (z) => Math.max(0, Math.min(nz - 1, Math.floor((z - b.minZ) / c)));
    const memo = new Map();
    const walk = (i, j) => { if (i < 0 || j < 0 || i >= nx || j >= nz) return false; const k = j * nx + i; let v = memo.get(k); if (v === undefined) { v = !blocked(cx(i), cz(j), PF.rad); memo.set(k, v); } return v; };
    const nearest = (x, z, maxR) => {                       // closest walkable cell to a point (spiral)
      const i0 = ci(x), j0 = cj(z); if (walk(i0, j0)) return [i0, j0];
      for (let r = 1; r <= maxR; r++) {
        let best = null, bd = 1e9;
        for (let di = -r; di <= r; di++) for (let dj = -r; dj <= r; dj++) { if (Math.max(Math.abs(di), Math.abs(dj)) !== r) continue; if (walk(i0 + di, j0 + dj)) { const d = Math.hypot(cx(i0 + di) - x, cz(j0 + dj) - z); if (d < bd) { bd = d; best = [i0 + di, j0 + dj]; } } }
        if (best) return best;
      }
      return null;
    };
    const st = nearest(sx, sz, 6), gl = nearest(gx, gz, 14);
    if (!st || !gl) return null;
    const goalXZ = { x: gx, z: gz };
    if (!blocked(gx, gz, PF.rad) && pfClear(sx, sz, gx, gz)) return { pts: [goalXZ], goal: goalXZ };      // open ground: just walk
    const gI = gl[0], gJ = gl[1], h = (i, j) => Math.hypot(i - gI, j - gJ);
    const g = new Map(), from = new Map(), closed = new Set(), heap = [];
    const push = (f, k) => { heap.push([f, k]); let i = heap.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (heap[p][0] <= heap[i][0]) break; [heap[p], heap[i]] = [heap[i], heap[p]]; i = p; } };
    const pop = () => { const top = heap[0], last = heap.pop(); if (heap.length) { heap[0] = last; let i = 0; for (;;) { let l = 2 * i + 1, r = l + 1, m = i; if (l < heap.length && heap[l][0] < heap[m][0]) m = l; if (r < heap.length && heap[r][0] < heap[m][0]) m = r; if (m === i) break; [heap[m], heap[i]] = [heap[i], heap[m]]; i = m; } } return top; };
    const sk = st[1] * nx + st[0], gk = gJ * nx + gI;
    g.set(sk, 0); push(h(st[0], st[1]), sk);
    let bestK = sk, bestH = h(st[0], st[1]), n = 0, found = false;
    const DIRS = [[1, 0, 1], [-1, 0, 1], [0, 1, 1], [0, -1, 1], [1, 1, 1.4142], [1, -1, 1.4142], [-1, 1, 1.4142], [-1, -1, 1.4142]];
    while (heap.length && n++ < PF.maxExpand) {
      const [, k] = pop(); if (closed.has(k)) continue; closed.add(k);
      if (k === gk) { found = true; bestK = k; break; }
      const i = k % nx, j = (k - i) / nx, hh = h(i, j); if (hh < bestH) { bestH = hh; bestK = k; }
      for (const [di, dj, w] of DIRS) {
        const ni = i + di, nj = j + dj; if (!walk(ni, nj)) continue;
        if (di && dj && (!walk(i + di, j) || !walk(i, j + dj))) continue;          // no cutting corners
        const nk = nj * nx + ni, ng = g.get(k) + w; if (closed.has(nk) || (g.has(nk) && g.get(nk) <= ng)) continue;
        g.set(nk, ng); from.set(nk, k); push(ng + h(ni, nj), nk);
      }
    }
    const cells = []; for (let k = bestK; k !== undefined; k = from.get(k)) { const i = k % nx; cells.push({ x: cx(i), z: cz((k - i) / nx) }); if (k === sk) break; }
    cells.reverse();                                        // start .. goal(or closest reachable)
    const end = found && !blocked(gx, gz, PF.rad) ? goalXZ : cells[cells.length - 1];
    if (found && end === goalXZ) cells[cells.length - 1] = goalXZ;
    // string pulling: from each anchor, jump to the farthest later cell that is in a clear straight line
    const pts = []; let ax = sx, az = sz, idx = 0;
    while (idx < cells.length) {
      let far = idx; for (let q = cells.length - 1; q > idx; q--) if (pfClear(ax, az, cells[q].x, cells[q].z)) { far = q; break; }
      pts.push({ x: cells[far].x, z: cells[far].z }); ax = cells[far].x; az = cells[far].z; idx = far + 1;
    }
    return { pts, goal: pts[pts.length - 1], partial: !found };
  }
  function setGoal(x, z, npc) {                              // walk to (x, z), routing around walls; falls back to a straight line when nothing is found
    const p = S.player, b = S.bounds; x = clamp(x, b.minX + 1, b.maxX - 1); z = clamp(z, b.minZ + 1, b.maxZ - 1);
    p.wantNpc = npc || null; p.replans = 0; p.path = null;
    if (noclipOn()) { p.target = { x, z }; return; }
    let r = null; try { r = findPath(p.x, p.z, x, z); } catch (e) { r = null; }
    if (!r || !r.pts.length) { p.target = { x, z }; return; }
    p.target = { x: r.pts[r.pts.length - 1].x, z: r.pts[r.pts.length - 1].z, want: { x, z } };
    p.path = r.pts.slice(0, -1);
  }
  function stepPlayer(dt) {
    const p = S.player, R = 0.55;
    let mx = 0, mz = 0;
    const f = [-Math.sin(cam.yaw * Math.PI / 180), -Math.cos(cam.yaw * Math.PI / 180)], r = [Math.cos(cam.yaw * Math.PI / 180), -Math.sin(cam.yaw * Math.PI / 180)];
    const k = (n) => keys[n] ? 1 : 0;
    const ix = k("d") + k("arrowright") - k("a") - k("arrowleft"), iy = k("w") + k("arrowup") - k("s") - k("arrowdown");
    if (ix || iy) { mx = f[0] * iy + r[0] * ix; mz = f[1] * iy + r[1] * ix; p.target = null; p.path = null; p.wantNpc = null; }
    else if (p.target) {
      while (p.path && p.path.length && Math.hypot(p.path[0].x - p.x, p.path[0].z - p.z) < 0.5) p.path.shift();     // reached a waypoint
      const wp = p.path && p.path.length ? p.path[0] : p.target;
      const dx = wp.x - p.x, dz = wp.z - p.z, d = Math.hypot(dx, dz);
      if (wp === p.target && d < 0.25) { p.target = null; p.path = null; if (p.wantNpc) { const n = p.wantNpc; p.wantNpc = null; interact(n); } } else { mx = dx / d; mz = dz / d; }
    }
    const len = Math.hypot(mx, mz);
    p.moving = len > 0.01;
    if (p.moving) {
      mx /= len; mz /= len;
      const sp = (keys.shift ? 11 : 7) * dt;
      const nx = p.x + mx * sp, nz = p.z + mz * sp, ox = p.x, oz = p.z;
      let moved = false;
      if (!blocked(nx, nz, R)) { p.x = nx; p.z = nz; moved = true; }
      else if (!blocked(nx, p.z, R)) { p.x = nx; moved = true; }
      else if (!blocked(p.x, nz, R)) { p.z = nz; moved = true; }
      if (moved) encounterStep(Math.hypot(p.x - ox, p.z - oz));
      if (moved && !cam.free && !(iy < 0)) {                               // auto-follow: swing the camera round behind the direction of travel (no manual yaw)
        const want = Math.atan2(-mx, -mz) * 180 / Math.PI, d = ((want - cam.goalYaw) % 360 + 540) % 360 - 180, lim = 115 * dt;
        cam.goalYaw += Math.max(-lim, Math.min(lim, d * 2.0 * dt));
      }
      if (!moved && p.target && !keys.shift && (p.replans || 0) < 4) {             // wedged on something: plan again from here
        p.replans = (p.replans || 0) + 1; const goal = p.target.want || p.target, nw = p.wantNpc, rp = p.replans; setGoal(goal.x, goal.z, nw); p.replans = rp;
        if (p.target && p.path && p.path.length) moved = true;
      }
      if (!moved) { p.moving = false; if (p.target) { p.target = null; p.path = null; if (p.wantNpc) { const n = p.wantNpc; p.wantNpc = null; if (Math.hypot(n.x - p.x, n.z - p.z) < 6) interact(n); } } }
      // facing as seen on screen
      const sx = mx * cam.camX[0] + mz * cam.camX[2];                      // + = screen right
      const sz = mx * cam.fwd[0] + mz * cam.fwd[2];                         // + = away from camera (screen up)
      p.face = Math.abs(sx) > Math.abs(sz) ? (sx > 0 ? "east" : "west") : (sz > 0 ? "north" : "south");
      p.t += dt;
    } else p.t = 0;
    // nearest NPC in reach
    let best = null, bd = 1e9;
    for (const n of S.npcs) { const d = Math.hypot(n.x - p.x, n.z - p.z); if (d < (n.reach || 4.6) && d < bd) { best = n; bd = d; } }
    S.active = best;
    stepEvents();
  }
  function interact(n) {
    if (!n) return;
    if (n.actions && n.actions.length) { if (O && O.sfx && O.SFX) O.sfx(O.SFX.confirm); runActions(n); return; }
    if (!n.action) return;
    if (O && O.sfx && O.SFX) O.sfx(O.SFX.confirm);
    savePos(); O.activate(n.action);
  }
  /* ---------- scene events (made in /builder3d): trigger zones + NPC scripts ----------
     An event or NPC owns `actions`: [{type:"say",who,text} | {type:"warp",scene,x,z} | {type:"hub",action}], run in order.
     "say" waits for E / Enter / Space / a click; "warp" loads another scene; "hub" presses one of the hub's own controls. */
  let script = null, sayEl = null;
  const scriptActive = () => !!script;
  function runActions(owner) {
    if (script || !owner || !owner.actions || !owner.actions.length) return;
    script = { owner, queue: owner.actions.slice(), waiting: false }; if (owner.once) owner.done = true; stepScript();
  }
  /* conditions shared by actions and autorun entries: if / unless = flags, minRank = the player's ladder rank (a number, or the
     name of a scene key such as "freeRank") */
  const rankOf = () => (state && state.ladder && state.ladder.rank) || 0;
  function minRankOf(e) { let m = e.minRank; if (typeof m === "string") m = S && S.def ? S.def[m] : 0; return +m || 0; }
  /* flag specs: "key" (set), or a comma list "a,!b,c" = every term must hold ("!x" = x is not set). Used by if / unless / showIf / hideIf. */
  function has(c, spec) { if (!spec) return true; return String(spec).split(",").every((t) => { t = t.trim(); return !t || (t[0] === "!" ? !c.has(t.slice(1)) : c.has(t)); }); }
  function condOk(e, c) { return !((e.if && !has(c, e.if)) || (e.unless && has(c, e.unless)) || (minRankOf(e) && rankOf() < minRankOf(e))); }
  let autorunPending = false;
  function endScript(noRefresh) {
    const dirty = script && script.dirty; if (script && script.cineRun) cineEnd(script.toBattle); if (script && script.musicChanged && !script.toBattle) applySceneMusic(); script = null; if (sayEl) sayEl.style.display = "none";
    renderQuest();
    if (dirty && !noRefresh && S && S.name) switchScene(S.name, S.player.x, S.player.z, true);   // a flag changed: re-filter npcs / pieces
  }

  /* ---------- cutscenes ----------
     Timed, camera-directed sequences made of ordinary script actions. A script that runs {type:"cine"} gets letterbox bars, the HUD is
     hidden, a Skip button / Esc skips to the end, and when the script ends the camera goes back to following the hero.
       cine  {on}                          bars + hidden HUD (on:false to leave early)
       fade  {to:"black"|"clear", t, wait} fade the screen
       wait  {t}
       title {text, sub, t}                a big title card
       cam   {x, z, yaw, pitch, dist, t, wait}   move the free camera (x,z = the point it looks at; omitted values stay put)
       follow {t}                          hand the camera back to the hero
       walk  {who:"player"|npc name/id, x, z, speed, face}   walk there (blocking)
       face  {who, dir}                    north | south | east | west
       music {url, intro, volume}          switch the music for the cutscene (the scene's own music returns when the script ends); {restore:true} brings it back at once
       say   {who:null}                    narration: no name plate (who:"" inside an npc script falls back to that npc's name)
     plus the usual say / flag / warp / battle ... A scene entry in `autorun` may carry cine:true to start on a black screen at once. */
  const cine = { on: false, tasks: [], els: null };
  const ease = (p) => p * p * (3 - 2 * p);
  function cineEls() {
    if (cine.els && cine.els.bars.parentNode === sceneEl) return cine.els;
    const mk = (id, css, html) => { const e = document.createElement("div"); e.id = id; e.style.cssText = css; if (html) e.innerHTML = html; sceneEl.appendChild(e); return e; };
    cine.els = {
      bars: mk("h3d-bars", "position:absolute;inset:0;z-index:2;pointer-events:none;display:none", '<i class="cb-top"></i><i class="cb-bot"></i>'),
      fade: mk("h3d-cfade", "position:absolute;inset:0;z-index:5;pointer-events:none;background:#000;opacity:0"),
      title: mk("h3d-ctitle", "position:absolute;inset:0;z-index:6;pointer-events:none;display:none;opacity:0", '<b></b><span></span>'),
      skip: mk("h3d-cskip", "position:absolute;right:22px;bottom:16px;z-index:7;display:none", "Skip &#9654;&#9654;"),
    };
    cine.els.skip.addEventListener("click", (e) => { e.stopPropagation(); skipCine(); });
    return cine.els;
  }
  function cineUi(on) {
    const E = cineEls(); cine.on = on; document.body.classList.toggle("h3d-cine", on);
    E.bars.style.display = on ? "block" : "none"; E.skip.style.display = on ? "block" : "none";
  }
  function setFade(to, t) {
    const E = cineEls(); E.fade.style.transition = t > 0 ? "opacity " + t + "s linear" : "none";
    void E.fade.offsetWidth; E.fade.style.opacity = to;
  }
  function dropCamTasks() { cine.tasks = cine.tasks.filter((k) => !k.cam); }                 // a new camera move replaces any move still running
  function cineWait(dur, fn, end, isCam) {
    const sc = script; sc.waiting = true; sc.lock = true;
    cine.tasks.push({ cam: !!isCam, t: 0, dur: Math.max(0.01, dur), fn, done: () => { if (end) end(); if (script === sc) { sc.lock = false; sc.waiting = false; stepScript(); } } });
  }
  function stepCine(dt) {
    if (!cine.tasks.length) return;
    for (const k of cine.tasks.slice()) {
      k.t += dt; const p = Math.min(1, k.t / k.dur); if (k.fn) k.fn(p, dt);
      if (p >= 1) { const i = cine.tasks.indexOf(k); if (i >= 0) cine.tasks.splice(i, 1); if (k.done) k.done(); }
    }
  }
  function cineEntity(who) { return !who || who === "player" ? S.player : (S.npcs.find((n) => n.id === who || n.name === who) || null); }
  function showTitle(text, sub, on) {
    const E = cineEls(), el = E.title; el.querySelector("b").textContent = text || ""; el.querySelector("span").textContent = sub || "";
    if (on) { el.style.display = "flex"; void el.offsetWidth; el.style.opacity = 1; } else { el.style.opacity = 0; setTimeout(() => { if (el.style.opacity === "0") el.style.display = "none"; }, 900); }
  }
  /* returns true when the action started something that blocks the script until it finishes */
  function doCine(a) {
    const sk = !!script.skip, t = a.t == null ? 1 : +a.t;
    if (a.type === "music") { script.musicChanged = true; if (a.restore || !a.url) applySceneMusic(); else { try { if (O && O.music) O.music({ url: a.url, intro: a.intro, volume: a.volume }); } catch (e) {} } return false; }
    if (a.type === "cine") { script.cineRun = true; cineUi(a.on !== false); return false; }
    if (a.type === "wait") { if (!sk) { cineWait(t); return true; } return false; }
    if (a.type === "fade") { setFade(a.to === "black" ? 1 : 0, sk ? 0 : t); if (!sk && a.wait !== false && t > 0) { cineWait(t); return true; } return false; }
    if (a.type === "title") {
      if (sk) return false;
      showTitle(a.text, a.sub, true); cineWait(a.t == null ? 3.5 : a.t, null, () => showTitle("", "", false)); return true;
    }
    if (a.type === "face") { const e = cineEntity(a.who); if (e && a.dir) { if (e === S.player) e.face = a.dir; else e.faceLeft = a.dir === "west"; } return false; }
    if (a.type === "cam") {
      cam.free = true; dropCamTasks();
      const to = { x: a.x != null ? a.x : cam.tx, z: a.z != null ? a.z : cam.tz, yaw: a.yaw != null ? a.yaw : cam.goalYaw, pitch: a.pitch != null ? a.pitch : cam.goalPitch, dist: a.dist != null ? a.dist : cam.goalDist };
      const fr = { x: cam.tx, z: cam.tz, ty: cam.ty || 0, yaw: cam.goalYaw, pitch: cam.goalPitch, dist: cam.goalDist }, ty1 = gh(to.x, to.z);
      const apply = (e) => { cam.tx = fr.x + (to.x - fr.x) * e; cam.tz = fr.z + (to.z - fr.z) * e; cam.ty = fr.ty + (ty1 - fr.ty) * e; cam.goalYaw = fr.yaw + (to.yaw - fr.yaw) * e; cam.goalPitch = fr.pitch + (to.pitch - fr.pitch) * e; cam.goalDist = fr.dist + (to.dist - fr.dist) * e; };
      if (sk || t <= 0) { apply(1); if (sk) { cam.yaw = cam.goalYaw; cam.pitch = cam.goalPitch; } return false; }
      if (a.wait === false) { cine.tasks.push({ cam: true, t: 0, dur: t, fn: (p) => apply(ease(p)), done: null }); return false; }
      cineWait(t, (p) => apply(ease(p)), null, true); return true;
    }
    if (a.type === "follow") { dropCamTasks(); cam.free = false; sceneCam(); if (!sk && a.wait !== false && t > 0) { cineWait(t); return true; } return false; }
    if (a.type === "walk") {
      const e = cineEntity(a.who); if (!e) return false;
      const x1 = a.x, z1 = a.z, x0 = e.x, z0 = e.z, d = Math.hypot(x1 - x0, z1 - z0), isP = e === S.player;
      if (sk || d < 0.05) { e.x = x1; e.z = z1; if (isP) { e.moving = false; if (a.face) e.face = a.face; } return false; }
      const dur = d / (a.speed || 3.6), dx = (x1 - x0) / d, dz = (z1 - z0) / d;
      if (isP) {                                     // facing as seen on screen, like normal movement
        const sx = dx * cam.camX[0] + dz * cam.camX[2], sz = dx * cam.fwd[0] + dz * cam.fwd[2];
        e.face = Math.abs(sx) > Math.abs(sz) ? (sx > 0 ? "east" : "west") : (sz > 0 ? "north" : "south");
      } else e.faceLeft = dx < 0;
      cineWait(dur, (p, dt) => { e.x = x0 + (x1 - x0) * p; e.z = z0 + (z1 - z0) * p; if (isP) { e.moving = true; e.t += dt; } },
        () => { if (isP) { e.moving = false; e.t = 0; if (a.face) e.face = a.face; } });
      return true;
    }
    return false;
  }
  const CINE_TYPES = new Set(["music", "cine", "wait", "fade", "title", "face", "cam", "follow", "walk"]);
  function skipCine() {
    if (!script || !script.cineRun || script.skip) return;
    script.skip = true; cine.tasks.length = 0; script.lock = false; script.waiting = false; S.player.moving = false; S.player.t = 0;
    if (sayEl) sayEl.style.display = "none"; showTitle("", "", false); stepScript();
  }
  function cineEnd(keepFade) {                                   // keepFade: leaving for a battle, so a black screen stays up until the page changes
    cine.tasks.length = 0;
    if (cine.on) { cineUi(false); cam.free = false; sceneCam(); }
    if (!keepFade) setFade(0, 0.9);
    showTitle("", "", false);
  }
  function stepScript() {
    while (script && script.queue.length) {
      const a = script.queue.shift();
      if (!condOk(a, getCleared())) continue;                                                              // conditional step
      if (CINE_TYPES.has(a.type)) { if (doCine(a)) return; continue; }
      if (a.type === "say" && script.skip) continue;
      if (a.type === "say") {
        script.waiting = true; showSay(a.who === null ? "" : (a.who || (script.owner.name || "")), a.text || "", a.portrait || (script.owner && script.owner.portrait));
        return;
      }
      if (a.type === "hub") { if (a.action && O) { savePos(); O.activate(a.action); } continue; }
      if (a.type === "warp") { endScript(true); switchScene(a.scene, a.x, a.z); return; }
      if (a.type === "tp") { const pl = S.player; pl.x = a.x; pl.z = a.z; pl.target = null; pl.wantNpc = null; primeEvents(); cam.tx = pl.x; cam.tz = pl.z + 1.5; updateCamera(0.016, true); if (a.fade !== false) flashOff(); continue; }   // same-scene teleport (fades the flash back out)
      if (a.type === "battle") { script.toBattle = true; endScript(true); startBattle(a); return; }
      if (a.type === "flag") { const c = getCleared(); c.add(a.key); setCleared(c); script.dirty = true; continue; }
      if (a.type === "flash") { script.waiting = true; script.lock = true; flashOn(); const sc = script; setTimeout(() => { sc.lock = false; sc.waiting = false; if (script === sc) stepScript(); }, 1300); return; }
      if (a.type === "rest") { script.waiting = true; restParty(); return; }
      if (a.type === "chest") { script.waiting = true; restParty("/api/story/chest", { loot: a.loot || {}, text: a.text || "" }); return; }
      if (a.type === "game") { script.waiting = true; restParty("/api/story/game", { game: a.game, stake: a.stake || 0 }); return; }   // fish | dice (server rolls it)
      if (a.type === "recruit") { script.waiting = true; restParty("/api/story/recruit", { name: a.name }); return; }
      if (a.type === "pass_time") { script.waiting = true; restParty("/api/story/pass_time"); return; }
      if (a.type === "reset_progress") { resetCleared(a.prefix || ""); continue; }
      if (a.type === "unflag") { const c = getCleared(); if (a.key) c.delete(a.key); if (a.prefix) for (const k of [...c]) if (k.indexOf(a.prefix) === 0) c.delete(k); setCleared(c); script.dirty = true; continue; }
    }
    endScript();
  }
  /* ---------- fights and progress ----------
     {type:"battle", key, boss}: starts a real battle through the hub server (boss = a WORLD_BOSSES id, empty = a wild
     encounter) and returns here afterwards; a win comes back as ?cleared=<key>, stored in localStorage so that
     npcs / events / colliders / pieces with hideIf:"<key>" disappear, and showIf:"<key>" appear. */
  const CLEAR_KEY = "h3dCleared";
  function getCleared() { try { return new Set(JSON.parse(localStorage.getItem(CLEAR_KEY) || "[]")); } catch (e) { return new Set(); } }
  function setCleared(set) { try { localStorage.setItem(CLEAR_KEY, JSON.stringify([...set])); } catch (e) {} syncSlave(set); }
  // The server decides solo-vs-party Colosseum fights, so tell it whether the hero is currently a slave
  // (taken to the Pit, not yet freed). Story flags live only in this browser.
  let lastSlave = null;
  function syncSlave(set) {
    const cl = set || getCleared(), slave = cl.has("st_done") && !cl.has("st_free");
    if (slave === lastSlave) return;
    lastSlave = slave;
    try { fetch("/api/story/slave", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ slave }) }).catch(() => { lastSlave = null; }); } catch (e) { lastSlave = null; }
  }
  syncSlave();
  function resetCleared(prefix) { const c = getCleared(); for (const k of [...c]) if (!prefix || k.indexOf(prefix) === 0) c.delete(k); setCleared(c); if (S && S.name) switchScene(S.name, S.def.spawn ? S.def.spawn.x : 0, S.def.spawn ? S.def.spawn.z : 0, true); }
  const visible = (o, c) => (!o.hideIf || !has(c, o.hideIf)) && (!o.showIf || has(c, o.showIf));
  function say(who, text) { script = { owner: { name: who }, queue: [{ type: "say", who, text }], waiting: false }; stepScript(); }
  async function startBattle(a) {
    if (!(state && ((state.story_party || state.party) || []).length)) { setFade(0, 0.4); say("", "You have no story heroes to fight with."); return; }
    try { await fetch("/api/world/hub_battle", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ boss_id: a.boss || "", level: Array.isArray(a.level) ? 0 : (a.level || 0), level_min: Array.isArray(a.level) ? a.level[0] : (a.level_min || 0), level_max: Array.isArray(a.level) ? a.level[1] : (a.level_max || 0), pool: a.pool || [], level_rel: a.level_rel || null, elite: a.elite || 0 }) }); }
    catch (e) { setFade(0, 0.4); say("", "The battle server could not be reached."); return; }
    savePos();
    location.href = "/battle?return=hub3d&scene=" + encodeURIComponent(S.name || "olympus") + (a.key ? "&key=" + encodeURIComponent(a.key) : "") + (S.def && S.def.restart ? "&restart=" + encodeURIComponent(S.def.restart) : "");
  }
  async function restParty(url, body) {
    let text = "You rest a while.";
    try { const r = await (await fetch(url || "/api/menu/rest", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) })).json(); if (r && r.message) text = r.message; if (O && O.refresh) O.refresh(); } catch (e) { text = "You try to rest, but nothing happens."; }
    if (O && O.sfx && O.SFX) O.sfx(O.SFX.confirm);
    showSay("", text);
  }
  /* ---------- story: objective line, screen flash, scene autorun ---------- */
  function storyObjective() {
    const c = getCleared();
    if (S && S.def && Array.isArray(S.def.objectives)) { for (const o of S.def.objectives) if (condOk(o, c)) return o.text || ""; }   // scene.objectives = [{if, unless, text}], first match wins
    if (S && S.name === "vault") return c.has("vt_boss") ? "The Warden has fallen. Take the lift back up to Outpost Kestrel."
      : c.has("vt_g3") ? "The north sector is cleared. The sealed door to the Warden's core is open."
      : c.has("vt_g2") ? "Cross the north walkways and defeat the Rift Colossus. The Warden's core lies beyond."
      : c.has("vt_g1") ? "The east gate is open. Reach the Phase Stalker at the end of the east maze."
      : "Fight through the floating maze. Take the west walkway and defeat the Vault Sentinel to open the next gate.";
    if (c.has("st_space")) {
      if (!S || S.name !== "asteroid") return "";
      if (!c.has("st_met")) return "Speak with Captain Rhea.";
      if (!c.has("st_lyra")) return "Find Lyra, the rift scholar Captain Rhea told you about (the mess hall, west of the pad).";
      if (!c.has("vt_boss")) return "Lyra's compass points beneath the base. Take the hatch west of the landing pad and clear the Shard Vault.";
      if (c.has("rc_end")) return "The Harbinger is gone and the rift is quiet. Rest at Outpost Kestrel.";
      if (S.name === "asteroid") return "A new coordinate has resolved on the rift console. Step into the rift gate east of the pad.";
      return "The Shard Vault is silent. Report to Captain Rhea: the trail leads further than this base.";
    }
    if (c.has("st_siege")) return "Defend the Colosseum!";
    if (c.has("st_free")) return "You are free! Leave through the main gate and take the ferry home to Paradise Island.";
    if (c.has("st_done")) {
      const fr = (S && S.def && S.def.freeRank) || 3, r = rankOf();
      return S && S.name === "prison" ? `You are a slave of the Colosseum. Fight for the Overseer until you rise past Rank ${fr - 1} to win your freedom` + (r ? ` (you are Rank ${r}).` : ".") : "";
    }
    if (!c.has("st_quest")) return "Speak with Elder Mahina in the village.";
    if (!c.has("st_found")) return "Find the missing villager, Lani, in the Hollow Cave (north of the village).";
    if (!c.has("st_attack")) return "Leave the crypt.";
    return "Defend the village!";
  }
  /* ---------- quest registry: html_hub/3d/quests.json (made by make_quests.py) ----------
     { quests: [{id, kind:"main"|"side", title, giver, where, summary, accept, ready, done, steps:[{if, unless, text, count}]}],
       marks:  { "scene/npcId": "main!" | "main?" | "side!" | "side?" | "later" | [{if, unless, mark}] } }
     A quest is in the log once its `accept` flag is set and stays (as Completed) once `done` is set. The step list gives the
     current objective (first match). Tracking: every quest is tracked unless its id is in localStorage "h3dUntracked"; the HUD lists
     only tracked quests. The Esc-menu "Quests" screen reads/changes this through Hub3D.quests() / Hub3D.setTracked(). */
  let questDb = null;
  const UNT_KEY = "h3dUntracked";
  function getUntracked() { try { return new Set(JSON.parse(localStorage.getItem(UNT_KEY) || "[]")); } catch (e) { return new Set(); } }
  function loadQuests() {
    if (questDb === null) {
      questDb = { quests: [], marks: {} };
      fetch(BASE + "quests.json", { cache: "no-store" }).then((r) => r.json()).then((j) => {
        questDb = { quests: (j && j.quests) || [], marks: (j && j.marks) || {} };
        updateMarks(); renderQuest();
      }).catch(() => {});
    }
    return questDb;
  }
  /* the log: one view per quest the player has taken -> {id, kind, title, giver, where, summary, status:"active"|"ready"|"done", text, count:[n,m]|null, tracked} */
  function questViews() {
    const db = loadQuests(), c = getCleared(), unt = getUntracked(), out = [];
    for (const q of db.quests) {
      const done = !!q.done && c.has(q.done);
      if (!done && !(q.accept && c.has(q.accept))) continue;
      const step = (q.steps || []).find((st) => condOk(st, c));
      let count = null; if (step && step.count && step.count.length) count = [step.count.filter((k) => c.has(k)).length, step.count.length];
      out.push({ id: q.id, kind: q.kind, title: q.title, giver: q.giver || "", where: q.where || "", summary: q.summary || "",
        status: done ? "done" : (q.ready && has(c, q.ready) ? "ready" : "active"), text: done ? "" : (step ? step.text : q.summary || ""), count, tracked: !unt.has(q.id) });
    }
    return out;
  }
  function setTracked(id, on) {
    const u = getUntracked(); if (on) u.delete(id); else u.add(id);
    try { localStorage.setItem(UNT_KEY, JSON.stringify([...u])); } catch (e) {}
    renderQuest();
  }
  function sideLines() {
    const out = [];
    for (const v of questViews()) {
      if (v.kind !== "side" || v.status === "done" || !v.tracked) continue;
      out.push(v.text + (v.count ? " (" + v.count[0] + "/" + v.count[1] + ")" : ""));
    }
    return out;
  }
  function renderQuest() {
    if (!hudEls.quest) return;
    const views = questViews();
    let t = (S && S.def && S.def.story) ? storyObjective() : "";
    const mains = views.filter((v) => v.kind === "main" && v.status !== "done");
    if (mains.length && mains.every((v) => !v.tracked)) t = "";                  // the player untracked the main quest
    const side = sideLines();
    hudEls.quest.style.display = (t || side.length) ? "block" : "none";
    hudEls.quest.innerHTML = t ? "<b>QUEST</b><span></span>" : ""; if (t) hudEls.quest.lastChild.textContent = t;
    if (side.length) {
      const h = document.createElement("b"); h.textContent = "SIDE"; h.style.display = "block"; h.style.marginTop = t ? "8px" : "0"; hudEls.quest.appendChild(h);
      for (const line of side.slice(0, 5).concat(side.length > 5 ? ["+" + (side.length - 5) + " more (see the quest log)"] : [])) { const d = document.createElement("span"); d.style.display = "block"; d.textContent = "\u2022 " + line; hudEls.quest.appendChild(d); }
    }
    updateMarks();
  }
  /* ---------- NPC marks: a symbol next to the name (and a bobbing ! / ? over quest givers) ----------
     [glyph, background, text colour]. Quest marks: gold = main story, blue = side quest, grey = a quest that is not open yet;
     "!" = a quest to take, "?" = come back / talk to move it on. Everything else is picked from what the NPC does. */
  const MARKS = {
    "main!": ["!", "#ffd23f", "#2a1d00", "Main quest"], "main?": ["?", "#ffd23f", "#2a1d00", "Main quest: talk to continue"],
    "side!": ["!", "#4fb3ff", "#04223a", "Side quest"], "side?": ["?", "#4fb3ff", "#04223a", "Side quest: turn in"],
    later: ["!", "#8b909c", "#1d1f26", "A quest that is not open yet"],
    shop: ["$", "#43c06a", "#06210f", "Shop"], heroes: ["\u2692", "#ff9d42", "#2a1200", "Gear and skills"], summon: ["\u2726", "#b98bff", "#1b0a33", "Summoning"],
    battle: ["\u2694", "#e0455a", "#ffffff", "Practice battles"], ladder: ["\u265B", "#e8c766", "#2a1d00", "Ladder"], travel: ["\u27A4", "#58d6c9", "#04201d", "Travel"],
    save: ["\u270E", "#d8d2c0", "#2a2418", "Save"], rest: ["\u263E", "#7fd3ff", "#06202e", "Rest"], dice: ["\u2684", "#f4f1e8", "#222222", "Dice"],
    foe: ["\u2694", "#e0455a", "#ffffff", "Enemy"], elite: ["\u2605", "#b04bd8", "#ffffff", "Elite enemy"], boss: ["\u2620", "#c0182d", "#ffffff", "Boss"],
  };
  const QUEST_MARKS = { "main!": 1, "main?": 1, "side!": 1, "side?": 1, later: 1 };
  H3.markLegend = () => Object.keys(MARKS).map((k) => ({ key: k, glyph: MARKS[k][0], bg: MARKS[k][1], fg: MARKS[k][2], label: MARKS[k][3] }));
  function autoMark(n) {
    const acts = n.actions || [], types = acts.map((a) => a.type);
    switch (n.action) {
      case "shop": return "shop"; case "heroes": return "heroes"; case "summon": return "summon"; case "battle": return "battle";
      case "ladder": return "ladder"; case "world": return "travel"; case "save_and_quit": case "save": return "save"; case "challenge": return "boss";
    }
    const b = acts.find((a) => a.type === "battle");
    if (b) return b.boss ? "boss" : b.elite ? "elite" : "foe";
    if (acts.some((a) => a.type === "game")) return "dice";
    if (types.includes("rest")) return "rest";
    return "";
  }
  function markOf(n) {
    const spec = loadQuests().marks[(S && S.name) + "/" + n.id];
    if (typeof spec === "string") return spec;
    if (Array.isArray(spec)) { const c = getCleared(), m = spec.find((e) => condOk(e, c)); if (m) return m.mark; }
    return autoMark(n);
  }
  function updateMarks() {
    if (!S || !S.npcs) return;
    for (const n of S.npcs) {
      if (!n.mk) continue;
      const key = markOf(n), m = MARKS[key];
      n.markKey = key; n.markColor = m ? m[1] : "";
      n.mk.style.display = m ? "inline-block" : "none";
      if (m) { n.mk.textContent = m[0]; n.mk.style.background = m[1]; n.mk.style.color = m[2]; n.mk.title = m[3]; }
      const q = QUEST_MARKS[key] ? m : null;
      n.qm.style.display = "none"; n.qmOn = !!q;
      if (q) { n.qm.textContent = q[0]; n.qm.style.background = q[1]; n.qm.style.color = q[2]; n.qm.style.boxShadow = "0 0 12px " + q[1]; }
    }
  }
  function flashOn() {
    let f = document.getElementById("h3d-flash");
    if (!f) { f = document.createElement("div"); f.id = "h3d-flash"; f.style.cssText = "position:fixed;inset:0;z-index:80;pointer-events:none;opacity:0;transition:opacity 1.1s;background:radial-gradient(circle at 50% 45%,#fff 0%,#d9b8ff 40%,#5a2a9a 100%)"; document.body.appendChild(f); }
    f.style.transition = "opacity 1.1s"; requestAnimationFrame(() => { f.style.opacity = "1"; });
  }
  function flashOff() { const f = document.getElementById("h3d-flash"); if (f && f.style.opacity !== "0") { f.style.transition = "opacity 1.6s"; setTimeout(() => { f.style.opacity = "0"; }, 250); } }
  /* scene.autorun = [{if, unless, actions}]: the first entry whose flags match plays when the scene finishes loading
     (intro text, the cutscenes that follow a battle). Each one sets a flag so it only plays once. */
  function runAutorun() {
    flashOff(); renderQuest();
    if (script || !S || !S.def || !S.def.autorun) return;
    const c = getCleared();
    if (!state && S.def.autorun.some((e) => e.minRank)) { autorunPending = true; return; }                 // rank checks need the hub state first
    for (const e of S.def.autorun) {
      if (!condOk(e, c)) continue;
      if (e.cine) { cineUi(true); setFade(1, 0); }                                                       // start behind a black screen, no glimpse of the scene
      setTimeout(() => { if (!script && S && !S.switching) runActions({ name: "", actions: e.actions }); else if (e.cine) cineEnd(); }, e.cine ? 450 : 700); return;
    }
  }
  /* Where the player stood when they left for a battle / shop / heroes page, so coming back puts them there
     instead of at the scene's spawn point. Per tab (sessionStorage), read once on the next load. */
  const POS_KEY = "h3dPos";
  function savePos() { try { if (S && S.name) sessionStorage.setItem(POS_KEY, JSON.stringify({ scene: S.name, x: S.player.x, z: S.player.z, face: S.player.face, yaw: cam.goalYaw, pitch: cam.goalPitch, dist: cam.goalDist })); } catch (e) {} }
  /* Random encounters: scene.encounters = {rate, level:[lo,hi], pool:[enemy ids], zones:[{x,z,w,d}]}. Walking inside a zone
     counts distance; every ~rate units an ambush starts a wild fight at a level rolled from the range. */
  function encounterStep(dist) {
    const enc = S.def && S.def.encounters; if (!enc || script || S.switching || modalOpen() || !(state && ((state.story_party || state.party) || []).length)) return;
    const p = S.player, zs = enc.zones;
    let zone = null;
    if (zs && zs.length) { zone = zs.find((z) => Math.abs(p.x - z.x) <= z.w / 2 && Math.abs(p.z - z.z) <= z.d / 2); if (!zone) return; }
    if (zone && zone.safe) return;                                                                          // zone.safe: no ambushes here (camps)
    const rate = (zone && zone.rate) || enc.rate || 100;
    if (S.encNext == null) S.encNext = rate * (0.8 + Math.random() * 0.8);
    S.encDist = (S.encDist || 0) + dist;
    if (S.encDist < S.encNext) return;
    S.encDist = 0; S.encNext = rate * (0.6 + Math.random() * 0.8); p.target = null; p.wantNpc = null;
    for (const k in keys) keys[k] = false;
    const lv = enc.level || [1, 1], zlv = zone && zone.level, rel = (zone && zone.level_rel) || enc.level_rel || null;   // a zone may set an absolute level range [lo, hi]
    script = { owner: { name: "" }, queue: [{ type: "say", who: "", text: enc.text || "Something stirs in the dark... monsters attack!" }, { type: "battle", key: "", boss: "", level: zlv || (rel ? 0 : lv), level_rel: zlv ? null : rel, pool: (zone && zone.pool) || enc.pool || [] }], waiting: false };
    stepScript();
  }
  function advanceScript() { if (script && script.waiting && !script.lock) { script.waiting = false; if (O && O.sfx && O.SFX) O.sfx(O.SFX.confirm); stepScript(); } }
  function primeEvents() { const p = S.player; for (const e of (S.events || [])) e.inside = Math.abs(p.x - e.x) <= e.w / 2 && Math.abs(p.z - e.z) <= e.d / 2; }
  function stepEvents() {
    const p = S.player; S.activeEv = null;
    for (const e of (S.events || [])) {
      const inside = Math.abs(p.x - e.x) <= e.w / 2 && Math.abs(p.z - e.z) <= e.d / 2;
      if (e.trigger === "talk") { if (inside && !(e.once && e.done)) S.activeEv = e; }
      else if (inside && !e.inside && !(e.once && e.done) && !script) runActions(e);
      e.inside = inside;
    }
  }
  // The Colosseum title + rank/renown panel only belong in the Colosseum scenes (scene.colosseum in the 3D editor overrides)
  function applyColosseumUI() {
    try {
      const name = S && S.name, def = S && S.def;
      const colo = def && typeof def.colosseum === "boolean" ? def.colosseum : (name === "olympus" || name === "prison");
      document.body.classList.toggle("h3d-nocolo", !colo);
    } catch (e) {}
  }
  function applySceneMusic() { applyColosseumUI(); try { if (O && O.music) O.music(S && S.def && S.def.music ? S.def.music : null); } catch (e) {} }   // scene.music = {url, intro?} set in the 3D editor
  function sceneCam() {                                   // scene.camera = {pitch, dist}: a per-scene default tilt / zoom, applied when the scene changes
    if (!S || cam.free || cam.forScene === S.name) return; cam.forScene = S.name;
    const c = (S.def && S.def.camera) || {}; cam.goalPitch = c.pitch || 33; cam.goalDist = c.dist || 29;
  }
  async function switchScene(name, x, z, force) {
    if (S && S.switching) return; if (S) S.switching = true;
    const old = S, refresh = !!(force && old && old.name === name);          // same-scene refresh after a flag changed: no loading screen
    if (hudEls.load && !refresh) { hudEls.load.textContent = "Loading…"; hudEls.load.classList.remove("done"); }
    try {
      const loaded = await loadScene(name, null);
      if (ui && ui.parentNode) ui.parentNode.removeChild(ui);
      S = loaded; S.player.face = old ? old.player.face : "south"; sceneCam();
      if (old) { try { Object.values(old.stex || {}).forEach((t) => gl.deleteTexture(t)); if (old.skyInfo && old.skyInfo.tex) gl.deleteTexture(old.skyInfo.tex); } catch (e) {} }
      if (x != null) S.player.x = x; if (z != null) S.player.z = z;
      primeEvents(); buildDom(); sayEl = null; buildSayBox(); cam.free = false; cam.tx = S.player.x; cam.tz = S.player.z + 1.5; updateCamera(0.016, true);
      if (state) H3.onState(state); hudEls.load.classList.add("done"); applySceneMusic(); try { O && O.refresh && O.refresh(); } catch (e) {} runAutorun();
    } catch (err) { console.warn("[Hub3D] warp failed:", err); flashOff(); if (old) old.switching = false; if (hudEls.load) { hudEls.load.textContent = "Could not load scene: " + name; setTimeout(() => hudEls.load.classList.add("done"), 1500); } }
  }
  /* Dialogue box: a big framed panel with a speaker name plate and, for heroes / important NPCs, a portrait frame.
     Portrait = action.portrait or npc.portrait (a name, or a path under /assets/), else /assets/Portraits/<speaker>.webp when that file exists. */
  const noPortrait = new Set();
  function portraitUrl(who, p) {
    if (p) return /[\/.]/.test(p) ? (p[0] === "/" ? p : "/assets/" + p) : "/assets/Portraits/" + encodeURIComponent(p) + ".webp";
    if (!who || noPortrait.has(who)) return "";
    return "/assets/Portraits/" + encodeURIComponent(who) + ".webp";
  }
  function showSay(who, text, portrait) {
    if (!sayEl) return;
    sayEl.querySelector(".s-who").textContent = who || ""; sayEl.querySelector(".s-text").textContent = text || "";
    const img = sayEl.querySelector(".s-pic img"), url = portraitUrl(who, portrait);
    sayEl.classList.remove("has-pic"); img.removeAttribute("src");
    if (url) {
      img.onload = () => { if (img.getAttribute("src") === url) sayEl.classList.add("has-pic"); };
      img.onerror = () => { noPortrait.add(who); img.removeAttribute("src"); sayEl.classList.remove("has-pic"); };
      img.src = url;
    }
    sayEl.style.animation = "none"; void sayEl.offsetWidth; sayEl.style.animation = "";     // replay the pop-in for every line
    sayEl.style.display = "block";
  }
  function buildSayBox() {
    sayEl = document.createElement("div"); sayEl.className = "h3d-say"; sayEl.innerHTML = '<div class="s-pic"><img alt=""></div><div class="s-who"></div><div class="s-text"></div><div class="s-go">&#9654; [E] / click to continue</div>';
    sayEl.addEventListener("click", (e) => { e.stopPropagation(); advanceScript(); }); ui.appendChild(sayEl);
    hudEls.evhint = document.createElement("div"); hudEls.evhint.className = "h3d-evhint"; ui.appendChild(hudEls.evhint);
  }
  function modalOpen() {
    const a = document.getElementById("tut-overlay"), b = document.getElementById("dbg-modal");
    return !!((a && a.classList.contains("open")) || (b && b.classList.contains("open")) || (window.JrpgMenu && JrpgMenu.isOpen()));
  }
  /* The Esc menu may open only when nothing else is going on: no dialogue / event script, no scene change or loading
     screen, no tutorial or debug modal. */
  H3.pos = () => (S && S.player ? { scene: S.name, x: S.player.x, z: S.player.z } : null);   // test / debug hook
  H3.canOpenMenu = function () {
    if (!H3.on || !S || script || S.switching || modalOpen()) return false;
    return !(hudEls.load && !hudEls.load.classList.contains("done"));
  };

  /* ---------- NPC text / DOM ---------- */
  function npcLine(n) {
    const s = state || {}, l = s.ladder || {};
    switch (n.id) {
      case "battle": return { text: (s.party && s.party.length) ? `Your party of ${s.party.length} is ready. Pick your fight?` : "No party yet. Let's pick your fighters first.", btn: "Enter Battle" };
      case "ladder": return { text: l.rank ? `Rank ${l.rank} · ${l.rank_name || ""}. ${l.renown || 0}${l.gate ? " / " + l.gate : ""} renown. Win streaks pay more, but cash out wisely.` : "Back-to-back fights, bigger rewards.", btn: "Ladder Mode" };
      case "boss": return l.next_boss ? { text: l.unlocked ? `${l.next_boss.name} awaits. Are you ready?` : `${l.next_boss.name} is beyond you for now. Need ${(l.gate || 0) - (l.renown || 0)} more renown.`, btn: l.unlocked ? "Challenge " + l.next_boss.name : "Locked" } : { text: "No challengers remain. More soon.", btn: "" };
      case "heroes": return { text: s.heroes_need_attention ? "Some of your heroes are ready to grow. Come, let's look at them." : "Your heroes, their gear and their skills.", btn: "Heroes" };
      case "shop": return { text: "Fresh stock! Gear, potions, anything a gladiator needs.", btn: "Shop" };
      case "summon": return { text: "The circle hums. Spend a ticket, a gem or a shard and see who answers.", btn: "Summon" };
      case "world": return { text: "Beyond these walls, a whole world. Shall we go?", btn: "World Map" };
      case "save": return { text: "I'll write your deeds into the record.", btn: "Save" };
    }
    return { text: n.line || "", btn: (n.actions && n.actions.length) ? "Talk" : (n.action ? n.name : "") };
  }

  /* ---------- minimap: M cycles local (rotating) / whole map / off. Scenes with def.minimap get fog-of-war. ---------- */
  const MM = { scene: null, mode: 0, cv: null, ctx: null, saved: 0 };
  try { MM.mode = +localStorage.getItem("h3dMapMode") || 0; } catch (e) {}
  function mmBuild() {
    const def = S.def, b = S.bounds, mp = def.minimap;
    MM.scene = S; MM.fog = !!mp; MM.cell = mp ? mp.cell : 4;
    MM.ox = b.minX; MM.oz = b.minZ; MM.w = b.maxX - b.minX; MM.h = b.maxZ - b.minZ;
    MM.bs = Math.min(2, 2048 / Math.max(MM.w, MM.h));
    const mk = () => { const c = document.createElement("canvas"); c.width = Math.ceil(MM.w * MM.bs); c.height = Math.ceil(MM.h * MM.bs); return c; };
    const base = mk(), g = base.getContext("2d"), P = (x, z, w, d, col) => { g.fillStyle = col; g.fillRect((x - MM.ox) * MM.bs, (z - MM.oz) * MM.bs, Math.ceil(w * MM.bs) + 0.5, Math.ceil(d * MM.bs) + 0.5); };
    if (mp) { for (const r of mp.rects) P(r[0], r[1], r[2], r[3], "#7d7388"); for (const r of mp.water || []) P(r[0], r[1], r[2], r[3], "#3a6aa8"); }
    else {
      P(b.minX, b.minZ, MM.w, MM.h, "#5d566c");
      for (const c of S.colliders || []) if (c.maxX !== undefined) P(c.minX, c.minZ, c.maxX - c.minX, c.maxZ - c.minZ, "#2a2535");
    }
    MM.base = base;
    if (MM.fog) {
      MM.gw = Math.ceil(MM.w / MM.cell); MM.gh = Math.ceil(MM.h / MM.cell); MM.seen = new Uint8Array(MM.gw * MM.gh); MM.shown = mk(); MM.key = "h3dSeen_" + S.name;
      try { const raw = atob(localStorage.getItem(MM.key) || ""); for (let i = 0; i < MM.seen.length; i++) { const by = raw.charCodeAt(i >> 3) || 0; if (by >> (i & 7) & 1) { MM.seen[i] = 1; mmShow(i % MM.gw, (i / MM.gw) | 0); } } } catch (e) {}
    }
  }
  function mmShow(ci, cj) {
    const s = MM.cell * MM.bs, x = ci * s, y = cj * s; MM.shown.getContext("2d").drawImage(MM.base, x, y, s, s, x, y, s, s);
  }
  function mmReveal() {
    const p = S.player, R = 22, c = MM.cell; let n = 0;
    for (let cj = Math.max(0, Math.floor((p.z - R - MM.oz) / c)); cj <= Math.min(MM.gh - 1, Math.floor((p.z + R - MM.oz) / c)); cj++)
      for (let ci = Math.max(0, Math.floor((p.x - R - MM.ox) / c)); ci <= Math.min(MM.gw - 1, Math.floor((p.x + R - MM.ox) / c)); ci++) {
        const i = cj * MM.gw + ci; if (MM.seen[i]) continue;
        if (Math.hypot(MM.ox + (ci + .5) * c - p.x, MM.oz + (cj + .5) * c - p.z) > R) continue;
        MM.seen[i] = 1; mmShow(ci, cj); n++;
      }
    if (n) MM.dirty = true;
    if (MM.dirty && performance.now() - MM.saved > 2000) {
      MM.saved = performance.now(); MM.dirty = false;
      try { const by = new Uint8Array(Math.ceil(MM.seen.length / 8)); for (let i = 0; i < MM.seen.length; i++) if (MM.seen[i]) by[i >> 3] |= 1 << (i & 7); let st = ""; for (let i = 0; i < by.length; i++) st += String.fromCharCode(by[i]); localStorage.setItem(MM.key, btoa(st)); } catch (e) {}
    }
  }
  function mmToggle() { MM.mode = (MM.mode + 1) % 3; try { localStorage.setItem("h3dMapMode", MM.mode); } catch (e) {} }
  function mmDraw() {
    if (!ui) return;
    if (!MM.cv || !ui.contains(MM.cv)) { MM.cv = document.createElement("canvas"); MM.cv.className = "h3d-map"; ui.appendChild(MM.cv); MM.ctx = MM.cv.getContext("2d"); }
    const cv = MM.cv;
    if (MM.mode === 2 || !S) { cv.style.display = "none"; return; }
    if (MM.scene !== S) mmBuild();
    if (MM.fog) mmReveal();
    const big = MM.mode === 1, dpr = Math.min(2, window.devicePixelRatio || 1), size = big ? Math.max(200, Math.min(480, innerHeight - 170, innerWidth - 40)) : 176;
    if (cv.width !== Math.round(size * dpr)) { cv.width = cv.height = Math.round(size * dpr); cv.style.width = cv.style.height = size + "px"; }
    cv.style.display = "block"; cv.style.borderRadius = big ? "14px" : "50%";
    const g = MM.ctx, p = S.player, src = MM.fog ? MM.shown : MM.base, yaw = cam.yaw * Math.PI / 180;
    g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, size, size); g.fillStyle = "rgba(10,8,18,.82)"; g.fillRect(0, 0, size, size);
    g.save();
    let z, cx, cz;
    if (big) { z = Math.min(size / MM.w, size / MM.h) * 0.94; cx = MM.ox + MM.w / 2; cz = MM.oz + MM.h / 2; g.translate(size / 2, size / 2); }
    else { z = 2; cx = p.x; cz = p.z; g.translate(size / 2, size / 2); g.rotate(yaw); }
    g.scale(z, z); g.translate(-cx, -cz);
    g.imageSmoothingEnabled = true; g.drawImage(src, MM.ox, MM.oz, MM.w, MM.h);
    const vis = (x, zz) => !MM.fog || (MM.seen[Math.min(MM.gh - 1, Math.max(0, Math.floor((zz - MM.oz) / MM.cell))) * MM.gw + Math.min(MM.gw - 1, Math.max(0, Math.floor((x - MM.ox) / MM.cell)))] === 1);
    const r = 3.2 / z * (big ? 1.2 : 1) * (z > 1 ? 1 : 1.2);
    for (const e of S.events || []) {
      const warp = (e.actions || []).some((a) => a.type === "warp"), chest = e.name === "Treasure chest";
      if (!(warp || chest) || !vis(e.x, e.z)) continue;
      g.fillStyle = chest ? "#f0c24a" : "#5fe08a"; g.fillRect(e.x - r * .7, e.z - r * .7, r * 1.4, r * 1.4);
    }
    for (const n of S.npcs || []) { if (!vis(n.x, n.z)) continue; g.fillStyle = (QUEST_MARKS[n.markKey] && n.markColor) || "#ffe27a"; g.beginPath(); g.arc(n.x, n.z, r * .8, 0, 7); g.fill(); }
    g.save(); g.translate(p.x, p.z); g.rotate(big ? yaw : -yaw); g.fillStyle = "#ff5a6e"; g.strokeStyle = "#fff"; g.lineWidth = 0.35 / z * 2;
    g.beginPath(); g.moveTo(0, -r * 1.7); g.lineTo(r * 1.1, r * 1.1); g.lineTo(0, r * .5); g.lineTo(-r * 1.1, r * 1.1); g.closePath(); g.fill(); g.stroke(); g.restore();
    g.restore();
    g.lineWidth = 3; g.strokeStyle = "rgba(232,199,102,.75)";
    if (big) { g.strokeRect(1.5, 1.5, size - 3, size - 3); } else { g.beginPath(); g.arc(size / 2, size / 2, size / 2 - 1.5, 0, 7); g.stroke(); }
  }
  function buildDom() {
    ui = document.createElement("div"); ui.id = "h3d-ui"; sceneEl.appendChild(ui);
    const mk = (cls, parent) => { const e = document.createElement("div"); e.className = cls; (parent || ui).appendChild(e); return e; };
    S.npcs.forEach((n) => {
      n.el = mk("h3d-npc"); n.hit = mk("h3d-hit", n.el); n.tag = mk("h3d-tag", n.el); n.mk = document.createElement("i"); n.mk.className = "h3d-mk"; n.tag.appendChild(n.mk); n.tagName = document.createElement("span"); n.tagName.textContent = n.name; n.tag.appendChild(n.tagName); n.alert = mk("h3d-alert", n.el); n.alert.textContent = "!"; n.qm = mk("h3d-qm", n.el);
      n.bub = mk("h3d-bubble", n.el);
      n.bub.innerHTML = '<div class="b-name"></div><div class="b-text"></div><div class="b-btn"></div>';
      n.hit.addEventListener("click", (e) => { e.stopPropagation(); clickNpc(n); });
      n.hit.addEventListener("mouseenter", () => { n.hover = true; }); n.hit.addEventListener("mouseleave", () => { n.hover = false; });
    });
    S.labels = (S.def.labels || []).map((l) => { const e = mk("h3d-label"); e.textContent = l.text; return Object.assign({ el: e, h: 6 }, l); });
    hudEls.hint = mk("h3d-hint"); hudEls.hint.textContent = "WASD / arrows move  ·  Shift run  ·  E talk  ·  click the ground or an NPC  ·  M map  ·  drag to tilt  ·  wheel zoom";
    hudEls.load = mk("h3d-loading"); hudEls.load.textContent = "Loading the plaza…";
    hudEls.quest = mk("h3d-quest");
    hudEls.rank = mk("h3d-rank"); hudEls.rank.innerHTML = '<b></b><span></span><i><u></u></i>';
    updateMarks();
  }
  function clickNpc(n) {
    if (modalOpen()) return;
    if (Math.hypot(n.x - S.player.x, n.z - S.player.z) < (n.reach || 4.6)) { interact(n); return; }
    // walk to a spot in front of them (towards the camera side), then talk
    const dx = S.player.x - n.x, dz = S.player.z - n.z, d = Math.hypot(dx, dz) || 1, stop = Math.min(d, 3.0);
    setGoal(n.x + dx / d * stop, n.z + dz / d * stop, n);
  }
  function syncDom() {
    const showN = S.active;
    if (hudEls.evhint) { const ev = S.activeEv; hudEls.evhint.style.display = ev && !script ? "block" : "none"; if (ev) hudEls.evhint.textContent = "[E] " + (ev.prompt || ev.name || "Interact"); }
    for (const l of S.labels || []) {
      const p = project([l.x, l.h + gh(l.x, l.z), l.z]), dx = l.x - S.player.x, dz = l.z - S.player.z, far = dx * dx + dz * dz > (l.range || 70) * (l.range || 70);
      const show = p.w > 0 && !far && p.x > -80 && p.x < cam.w + 80 && p.y > -30 && p.y < cam.h + 30 && (!l.showIf || has(getCleared(), l.showIf));
      l.el.style.display = show ? "block" : "none"; if (show) { l.el.style.left = p.x + "px"; l.el.style.top = p.y + "px"; }
    }
    for (const n of S.npcs) {
      const gy = gh(n.x, n.z), foot = project([n.x, gy + (n.base || 0), n.z]), head = project([n.x, gy + (n.base || 0) + n.h, n.z]);
      const hh = Math.max(20, foot.y - head.y), hw = hh * (n.bossTex ? n.bossTex.aspect : (n.sheet ? Math.min(n.sheet.cw / n.sheet.refH, 1) : 0.5)) * 0.9;
      n.el.style.left = foot.x + "px"; n.el.style.top = foot.y + "px"; n.el.style.zIndex = String(10 + Math.round(foot.y));
      n.hit.style.width = hw + "px"; n.hit.style.height = hh + "px"; n.hit.style.cursor = "pointer";
      n.tag.style.top = (-hh - 4) + "px"; n.alert.style.top = (-hh - 40) + "px"; n.qm.style.top = (-hh - 40) + "px";
      n.tag.classList.toggle("on", n === showN || n.hover);
      const line = npcLine(n);
      n.alert.style.display = n.alertOn ? "block" : "none";
      n.qm.style.display = n.qmOn && !n.alertOn ? "block" : "none";
      const open = n === showN && !modalOpen();
      n.bub.style.display = open ? "block" : "none";
      if (open) {
        n.bub.style.top = (-hh - 14) + "px";
        n.bub.querySelector(".b-name").textContent = n.title ? `${n.name} · ${n.title}` : n.name;
        n.bub.querySelector(".b-text").textContent = line.text;
        const b = n.bub.querySelector(".b-btn"); b.textContent = line.btn ? `[E] ${line.btn}` : ""; b.style.display = line.btn ? "block" : "none";
      }
    }
  }

  /* ---------- state from the hub ---------- */
  H3.quests = questViews; H3.setTracked = setTracked;
  H3.isStory = () => !!(S && S.def && S.def.story);   // story scene: the hub shows the story party, not the Colosseum one
  H3.onState = function (s) {
    state = s;
    if (!S) return;
    if (autorunPending) { autorunPending = false; runAutorun(); }
    renderQuest();
    const l = s.ladder || {};
    S.npcs.forEach((n) => {
      if (n.id === "heroes") n.alertOn = !!s.heroes_need_attention;
      if (n.id === "boss") {
        n.alertOn = !!(l.unlocked && l.next_boss); n.locked = !l.unlocked;
        const url = l.next_boss && l.next_boss.portrait;
        if (url && n.bossUrl !== url) {
          n.bossUrl = url;
          loadImage(url).then((im) => { gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true); n.bossTex = { tex: makeTexture(im, {}), aspect: im.naturalWidth / im.naturalHeight }; }).catch(() => {});
        }
        if (!url) n.bossTex = null;
      }
    });
    updateRank();
  };
  function updateRank() {
    if (!hudEls.rank || !state || !state.ladder) return;
    const l = state.ladder, e = hudEls.rank;
    e.querySelector("b").textContent = "RANK " + l.rank + (l.rank_name ? " · " + l.rank_name.toUpperCase() : "");
    e.querySelector("span").textContent = l.next_boss ? `${l.renown} / ${l.gate} renown` : `${l.renown} renown`;
    e.querySelector("u").style.width = (l.next_boss ? clamp(100 * l.renown / l.gate, 0, 100) : 100) + "%";
  }

  /* ---------- view toggle & UI ---------- */
  function css() {
    const st = document.createElement("style");
    st.textContent = `
      #h3d-canvas { position:absolute; inset:0; width:100%; height:100%; display:none; z-index:0; outline:none; }
      #h3d-ui { position:absolute; inset:0; z-index:3; pointer-events:none; overflow:hidden; display:none; }
      body.h3d #h3d-canvas, body.h3d #h3d-ui { display:block; }
      body.h3d #scene::before { display:none; }
      body.h3d #rail-left, body.h3d #rail-right, body.h3d #navbar, body.h3d #ladder, body.h3d #bench-note { display:none !important; }
      body.h3d #party-row { position:absolute; left:14px; bottom:14px; z-index:4; padding:0; gap:8px; transform:scale(.6); transform-origin:left bottom; flex:none; pointer-events:none; }
      body.h3d #topbar { z-index:5; pointer-events:none; } body.h3d #currencies { pointer-events:auto; }
      #h3d-bar { position:absolute; bottom:18px; right:70px; z-index:6; display:flex; gap:6px; }
      #h3d-bar button { background:var(--panel-bg); color:var(--dim); border:1px solid var(--panel-border); border-radius:999px; padding:4px 12px; font-size:12px; cursor:pointer; }
      #h3d-bar button:hover { color:#fff; border-color:var(--gold); }
      .h3d-npc { position:absolute; width:0; height:0; }
      .h3d-hit { position:absolute; transform:translate(-50%,-100%); pointer-events:auto; }
      .h3d-label { display:none; position:absolute; transform:translate(-50%,-50%); white-space:nowrap; font-size:13px; font-weight:700; letter-spacing:.03em; color:#f6efd8; padding:3px 11px; background:rgba(40,28,18,.72); border:1px solid rgba(232,199,102,.35); text-shadow:0 1px 2px #000; pointer-events:none; z-index:2; }
      .h3d-tag { position:absolute; transform:translate(-50%,-100%); white-space:nowrap; font-size:12px; font-weight:700; letter-spacing:.04em; color:#f1ecdd; padding:2px 9px;
        background:rgba(18,16,28,.62); border:1px solid rgba(232,199,102,.25); border-radius:999px; text-shadow:0 1px 3px #000; opacity:.8; pointer-events:none; transition:opacity .15s, border-color .15s; }
      .h3d-tag.on { opacity:1; border-color:var(--gold); color:var(--gold); }
      .h3d-alert { display:none; position:absolute; transform:translate(-50%,-100%); width:24px; height:24px; line-height:24px; text-align:center; border-radius:50%; background:#e0455a; color:#fff;
        font-weight:800; box-shadow:0 0 12px rgba(224,69,90,.8); pointer-events:none; animation:h3d-bob 1s ease-in-out infinite alternate; }
      .h3d-mk { display:none; min-width:15px; height:15px; line-height:15px; margin-right:6px; padding:0 2px; text-align:center; border-radius:50%; font-style:normal; font-size:11px; font-weight:900; vertical-align:1px; text-shadow:none; box-sizing:border-box; }
      .h3d-qm { display:none; position:absolute; transform:translate(-50%,-100%); width:26px; height:26px; line-height:26px; text-align:center; border-radius:50%; font-weight:900; font-size:17px; border:2px solid rgba(0,0,0,.55);
        pointer-events:none; animation:h3d-bob 1s ease-in-out infinite alternate; }
      @keyframes h3d-bob { from { margin-top:0; } to { margin-top:-6px; } }
      .h3d-bubble { display:none; position:absolute; transform:translate(-50%,-100%); width:250px; padding:10px 14px 11px; border-radius:14px; pointer-events:none;
        background:rgba(18,16,28,.9); border:1px solid var(--gold); box-shadow:0 6px 24px rgba(0,0,0,.55); }
      .h3d-bubble::after { content:""; position:absolute; left:50%; bottom:-7px; width:12px; height:12px; background:rgba(18,16,28,.95); border-right:1px solid var(--gold); border-bottom:1px solid var(--gold); transform:translateX(-50%) rotate(45deg); }
      .b-name { font-size:12px; font-weight:800; letter-spacing:.06em; color:var(--gold); text-transform:uppercase; }
      .b-text { font-size:13px; line-height:1.4; margin:4px 0 8px; color:var(--text); }
      .b-btn { display:inline-block; font-size:12px; font-weight:800; padding:5px 12px; border-radius:9px; color:#241a05; background:linear-gradient(180deg,#e8c766,#b8892c); }
      .h3d-map { position:absolute; right:20px; bottom:70px; pointer-events:none; box-shadow:0 4px 18px rgba(0,0,0,.6); display:none; }
      .h3d-hint { position:absolute; left:50%; bottom:12px; transform:translateX(-50%); font-size:11px; color:var(--dim); background:rgba(18,16,28,.55); padding:4px 12px; border-radius:999px; white-space:nowrap; }
      .h3d-loading { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:18px; letter-spacing:.1em; color:var(--gold); background:rgba(10,9,16,.85); transition:opacity .5s; pointer-events:none; }
      .h3d-loading.done { opacity:0; }
      body.h3d-nocolo .h3d-rank, body.h3d-nocolo #title-block { display:none !important; }
      .h3d-rank { position:absolute; left:22px; top:92px; width:210px; padding:7px 12px 9px; border-radius:12px; background:var(--panel-bg); border:1px solid var(--panel-border); pointer-events:none; }
      .h3d-quest { position:absolute; left:22px; top:166px; width:210px; padding:7px 12px 9px; border-radius:12px; background:var(--panel-bg); border:1px solid var(--panel-border); pointer-events:none; display:none; }
      .h3d-quest b { display:block; font-size:11px; letter-spacing:.12em; color:var(--gold); } .h3d-quest span { font-size:12px; color:#f0ead0; line-height:1.35; }
      .h3d-rank b { display:block; font-size:11px; letter-spacing:.12em; color:var(--gold); } .h3d-rank span { font-size:11px; color:var(--dim); }
      .h3d-rank i { display:block; height:6px; border-radius:3px; background:rgba(255,255,255,.12); margin-top:5px; overflow:hidden; } .h3d-rank u { display:block; height:100%; width:0; background:linear-gradient(90deg,#8a6a1a,#e8c766); transition:width .5s; }
      #h3d-bars i { position:absolute; left:0; right:0; height:0; background:#000; transition:height 1.1s ease; display:block; } #h3d-bars .cb-top { top:0; } #h3d-bars .cb-bot { bottom:0; }
      body.h3d-cine #h3d-bars i { height:11vh; }
      body.h3d-cine .h3d-tag, body.h3d-cine .h3d-alert, body.h3d-cine .h3d-qm, body.h3d-cine .h3d-bubble, body.h3d-cine .h3d-hint, body.h3d-cine .h3d-quest, body.h3d-cine .h3d-map, body.h3d-cine .h3d-rank,
      body.h3d-cine .h3d-label, body.h3d-cine .h3d-hit, body.h3d-cine .h3d-evhint, body.h3d-cine #h3d-bar { display:none !important; }
      body.h3d-cine .h3d-say { bottom:calc(11vh + 22px); }
      #h3d-ctitle { align-items:center; justify-content:center; flex-direction:column; text-align:center; transition:opacity .9s ease; }
      #h3d-ctitle b { font-size:clamp(34px,7vw,84px); letter-spacing:.22em; font-weight:900; color:#f2d67e; text-shadow:0 0 28px rgba(232,199,102,.55), 0 4px 0 #6b4a10, 0 8px 22px rgba(0,0,0,.8); padding-left:.22em; }
      #h3d-ctitle span { margin-top:14px; font-size:clamp(13px,2vw,20px); letter-spacing:.38em; text-transform:uppercase; color:#e9dcc0; text-shadow:0 2px 8px #000; }
      #h3d-cskip { padding:6px 16px; border-radius:999px; font-size:12px; font-weight:800; letter-spacing:.08em; color:#e9dcc0; background:rgba(0,0,0,.55); border:1px solid rgba(232,199,102,.6); cursor:pointer; user-select:none; }
      #h3d-cskip:hover { background:rgba(232,199,102,.25); }
      .h3d-say { display:none; box-sizing:border-box; position:absolute; left:50%; bottom:46px; transform:translateX(-50%); width:min(780px,94vw); min-height:112px; padding:30px 28px 30px; border-radius:16px; pointer-events:auto; cursor:pointer; z-index:8;
        background:linear-gradient(180deg,rgba(34,28,52,.98),rgba(12,10,22,.98)); border:2px solid var(--gold);
        box-shadow:0 0 0 3px rgba(0,0,0,.65), 0 0 0 5px rgba(232,199,102,.35), 0 14px 44px rgba(0,0,0,.75), 0 0 36px rgba(232,199,102,.18); animation:h3d-say-in .18s ease-out; }
      @keyframes h3d-say-in { from { opacity:0; transform:translateX(-50%) translateY(14px); } to { opacity:1; transform:translateX(-50%); } }
      .h3d-say.has-pic { padding-left:176px; }
      .s-pic { display:none; position:absolute; left:20px; bottom:14px; width:140px; height:176px; border-radius:12px; overflow:hidden; border:2px solid var(--gold);
        background:#120f1c; box-shadow:0 0 0 3px rgba(0,0,0,.7), 0 8px 24px rgba(0,0,0,.7); }
      .h3d-say.has-pic .s-pic { display:block; } .s-pic img { width:100%; height:100%; object-fit:cover; object-position:top center; display:block; }
      .s-who { position:absolute; left:26px; top:-15px; padding:4px 18px 5px; border-radius:9px; font-size:14px; font-weight:800; letter-spacing:.09em; color:#241a05; text-transform:uppercase;
        background:linear-gradient(180deg,#f2d67e,#b8892c); box-shadow:0 3px 12px rgba(0,0,0,.6); } .s-who:empty { display:none; }
      .h3d-say.has-pic .s-who { left:176px; }
      .s-text { font-size:18px; line-height:1.55; margin:0; color:#fff; white-space:pre-wrap; text-shadow:0 1px 2px rgba(0,0,0,.6); }
      .s-go { position:absolute; right:20px; bottom:8px; font-size:12px; color:var(--gold); animation:h3d-blink 1.2s ease-in-out infinite; }
      @keyframes h3d-blink { 50% { opacity:.35; } }
      .h3d-evhint { display:none; position:absolute; left:50%; bottom:46px; transform:translateX(-50%); font-size:13px; font-weight:700; color:#241a05; background:linear-gradient(180deg,#e8c766,#b8892c); padding:6px 16px; border-radius:999px; box-shadow:0 4px 16px rgba(0,0,0,.5); pointer-events:none; }
      #h3d-vignette { position:absolute; inset:0; pointer-events:none; z-index:1; background:radial-gradient(ellipse at 50% 55%, rgba(0,0,0,0) 55%, rgba(6,3,14,.5) 100%); display:none; }
      body.h3d #h3d-vignette { display:block; }`;
    document.head.appendChild(st);
    const bar = document.createElement("div"); bar.id = "h3d-bar";
    H3.btn = document.createElement("button"); H3.btn.type = "button"; H3.btn.addEventListener("click", (e) => { H3.setOn(!H3.on); H3.btn.blur(); e.stopPropagation(); });
    bar.appendChild(H3.btn); sceneEl.appendChild(bar);
    const vg = document.createElement("div"); vg.id = "h3d-vignette"; sceneEl.insertBefore(vg, sceneEl.firstChild);
  }
  function resize() {
    if (!canvas) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    cam.w = sceneEl.clientWidth || window.innerWidth; cam.h = sceneEl.clientHeight || window.innerHeight;
    canvas.width = Math.round(cam.w * dpr); canvas.height = Math.round(cam.h * dpr); cam.aspect = cam.w / cam.h;
    gl.viewport(0, 0, canvas.width, canvas.height);
  }
  H3.setOn = function (on) {
    on = !!on && !H3.failed && H3.ready;
    H3.on = on; lastT = 0; if (fx) fx.setVisible(on);
    document.body.classList.toggle("h3d", on);
    if (H3.btn) H3.btn.textContent = on ? "View: 3D plaza" : "View: 2D menu";
    try { localStorage.setItem("hubView", on ? "3d" : "2d"); } catch (e) {}
    if (on) { resize(); if (S) updateCamera(0.016, true); canvas.focus && canvas.focus(); }
  };

  function frame(now) {
    requestAnimationFrame(frame);
    if (!H3.on || !S) return;
    const dt = Math.min(0.05, Math.max(0.001, (now - (lastT || now - 16)) / 1000)); lastT = now; clock += dt;
    stepCine(dt);
    if (!modalOpen() && !scriptActive()) stepPlayer(dt); else if (!(script && script.cineRun && S.player.moving)) S.player.moving = false;
    updateCamera(dt, false);
    render(now); syncDom(); try { mmDraw(); } catch (e) { if (!MM.err) { MM.err = 1; console.warn('[Hub3D] minimap:', e); } }
  }
  function bindInput() {
    window.addEventListener("keydown", (e) => {
      if (!H3.on || modalOpen()) return;
      if (script) { if (e.key === "Escape") { e.preventDefault(); skipCine(); return; } if (e.key === "e" || e.key === "E" || e.key === "Enter" || e.key === " ") { e.preventDefault(); if (!e.repeat) advanceScript(); } return; }
      if (e.target && /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
      const k = e.key.toLowerCase();
      if (k === "m" && !e.repeat) { mmToggle(); return; }
      if (["w", "a", "s", "d", "arrowup", "arrowdown", "arrowleft", "arrowright", "shift"].includes(k)) { keys[k] = true; if (k.startsWith("arrow")) e.preventDefault(); }
      if ((k === "e" || k === "enter" || k === " ") && S && S.active && !e.repeat) { e.preventDefault(); interact(S.active); }
      else if ((k === "e" || k === "enter" || k === " ") && S && S.activeEv && !e.repeat) { e.preventDefault(); runActions(S.activeEv); }
    });
    window.addEventListener("keyup", (e) => { keys[e.key.toLowerCase()] = false; });
    window.addEventListener("blur", () => { for (const k in keys) keys[k] = false; });
    let drag = null;
    const host = ui;
    sceneEl.addEventListener("pointerdown", (e) => { if (!H3.on || e.target.closest(".h3d-hit, .h3d-say, button, .currency-pill, #tut-overlay, #dbg-modal, .debug")) return; drag = { x: e.clientX, y: e.clientY, yaw: cam.goalYaw, pitch: cam.goalPitch, moved: false, id: e.pointerId }; });
    window.addEventListener("pointermove", (e) => {
      if (!drag || script) return; const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 6) drag.moved = true;
      if (drag.moved) { cam.goalPitch = clamp(drag.pitch + dy * 0.15, 14, 62); }
    });
    window.addEventListener("pointerup", (e) => {
      if (!drag) return; const d = drag; drag = null;
      if (d.moved || !H3.on || modalOpen() || script) return;
      const r = sceneEl.getBoundingClientRect(), g = groundAt(e.clientX - r.left, e.clientY - r.top);
      if (g) setGoal(g.x, g.z, null);
    });
    sceneEl.addEventListener("wheel", (e) => { if (!H3.on || modalOpen() || script) return; e.preventDefault(); cam.goalDist = clamp(cam.goalDist * (1 + Math.sign(e.deltaY) * 0.08), 12, 48); }, { passive: false });
    window.addEventListener("resize", resize);
  }

  /* ---------- init ---------- */
  H3.init = async function (opts) {
    O = opts; sceneEl = document.getElementById("scene");
    const q = new URLSearchParams(location.search);
    { const c = getCleared();       // the opening cutscene: ?intro=1 replays it; saves that already progressed never see it
      if (q.get("intro")) { c.delete("st_intro"); setCleared(c); }
      else if (!c.has("st_intro") && [...c].some((k) => /^(fq_|dg_|st_|vt_)/.test(k))) { c.add("st_intro"); setCleared(c); } }
    if (q.get("cleared")) { const c = getCleared(); c.add(q.get("cleared")); setCleared(c); try { const u = new URL(location.href); u.searchParams.delete("cleared"); history.replaceState(null, "", u); } catch (e) {} }
    css();
    try {
      if (!window.B3DMap) throw new Error("battlemap.js not loaded");
      canvas = document.createElement("canvas"); canvas.id = "h3d-canvas"; canvas.tabIndex = -1;
      gl = canvas.getContext("webgl", { antialias: true, alpha: false, premultipliedAlpha: false });
      if (!gl) throw new Error("WebGL unavailable");
      sprog = mkProg(SVS, SFS, ["a"]); mprog = mkProg(MVS, MFS, ["p", "n", "t", "c"]);
      ["u_vp", "u_o", "u_r", "u_u", "u_size", "u_anchor", "u_tex", "u_rect", "u_flip", "u_tint", "u_fogc", "u_fogr", "u_fogd"].forEach((n) => { SU[n] = gl.getUniformLocation(sprog, n); });
      ["u_vp", "u_model", "u_tex", "u_color", "u_emis", "u_cut", "u_unlit", "u_mode", "u_ldir", "u_lcol", "u_amb", "u_fogc", "u_fogr"].forEach((n) => { MU[n] = gl.getUniformLocation(mprog, n); });
      quadBuf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]), gl.STATIC_DRAW);
      gl.enable(gl.BLEND); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true); gl.activeTexture(gl.TEXTURE0);
      gl.useProgram(sprog); gl.uniform1i(SU.u_tex, 0);
      maxTex = Math.min(8192, gl.getParameter(gl.MAX_TEXTURE_SIZE) || 4096);
      idxUint = !!gl.getExtension("OES_element_index_uint"); aniso = gl.getExtension("EXT_texture_filter_anisotropic");
      buildTextures(); useSprite();
    } catch (err) { console.warn("[Hub3D] 3D plaza unavailable, staying in 2D:", err); H3.failed = true; return; }
    sceneEl.insertBefore(canvas, sceneEl.firstChild);
    if (!window.EnvFX) { const s = document.createElement("script"); s.src = "/hub3d/envfx.js"; document.head.appendChild(s); }
    H3.ready = true; resize();
    try {
      let back = null; try { back = JSON.parse(sessionStorage.getItem(POS_KEY) || "null"); sessionStorage.removeItem(POS_KEY); } catch (e) {}
      if (q.get("restart")) {                      // "Restart Dungeon" after a defeat: wipe that dungeon's progress, heal, start at the entrance
        resetCleared(q.get("restart")); back = null;
        try { await fetch("/api/menu/rest", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }); } catch (e) {}
        try { const u = new URL(location.href); u.searchParams.delete("restart"); history.replaceState(null, "", u); } catch (e) {}
      }
      const sceneName = q.get("scene") || (back && back.scene) || (((cl) => cl.has("st_space") ? "asteroid" : cl.has("st_free") ? "olympus" : cl.has("st_done") ? "prison" : "island")(getCleared()));
      S = null;
      const loaded = await loadScene(sceneName, null);
      S = loaded; sceneCam(); buildDom(); buildSayBox(); bindInput(); applySceneMusic();
      if (q.get("cam")) { const c = q.get("cam").split(",").map(Number); cam.free = true; cam.tx = c[0]; cam.tz = c[1]; cam.goalYaw = c[2] || 0; cam.goalPitch = c[3] || 30; cam.goalDist = c[4] || 25; }
      if (back && back.scene === sceneName && !q.get("at") && isFinite(back.x) && isFinite(back.z)) { S.player.x = back.x; S.player.z = back.z; if (back.face) S.player.face = back.face; if (!cam.free && isFinite(back.yaw)) { cam.goalYaw = back.yaw; if (isFinite(back.pitch)) cam.goalPitch = back.pitch; if (isFinite(back.dist)) cam.goalDist = back.dist; } }
      if (q.get("at")) { const c = q.get("at").split(",").map(Number); S.player.x = c[0]; S.player.z = c[1]; }
      primeEvents();
      if (!cam.free) { cam.tx = S.player.x; cam.tz = S.player.z + 1.5; }
      updateCamera(0.016, true);
      if (state) H3.onState(state);
      hudEls.load.classList.add("done"); runAutorun();
    } catch (err) { console.warn("[Hub3D] could not build the plaza:", err); H3.failed = true; H3.ready = false; document.body.classList.remove("h3d"); if (hudEls.load) hudEls.load.textContent = "Plaza failed: " + (err && err.message || err); return; }
    requestAnimationFrame(frame);
    let saved = null; try { saved = localStorage.getItem("hubView"); } catch (e) {}
    const want = q.get("view") === "2d" || q.get("view") === "3d" ? q.get("view") : (saved || "3d");
    H3.setOn(want !== "2d");
  };
  H3.debug = { cam, setGoal, findPath, walkN: (n) => { for (let i = 0; i < n; i++) stepPlayer(0.05); }, camStep: (n) => { for (let i = 0; i < n; i++) updateCamera(0.05); }, project, groundAt, scene: () => S, say, interact: (id) => { const n = S.npcs.find((q) => q.id === id); if (n) interact(n); }, cineStep: (sec) => { for (let t = 0; t < sec; t += 0.05) stepCine(0.05); } };
})();

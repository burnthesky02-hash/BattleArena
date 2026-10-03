/* hub3d.js -- the Colosseum hub as a walkable 3D plaza.

   Loaded by html_hub/index.html (after /battle/battlemap.js, the GLB parser). The hub page keeps all of its
   own logic (currencies, party, ladder, navigation, tutorial, debug); this file only adds:
     - a WebGL canvas behind the DOM: Kenney GLB pieces for the town (see plaza.json), sprite billboards for the
       player (4-direction walk cycle) and the NPCs (idle sheets), blob shadows, floor glyph decals;
     - walking (WASD / arrows, click-to-move), collision, a follow camera with drag-orbit and wheel zoom;
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
  function updateCamera(dt, instant) {
    const k = instant ? 1 : 1 - Math.pow(0.0008, dt), k2 = instant ? 1 : 1 - Math.pow(0.05, dt);
    cam.yaw = lerp(cam.yaw, cam.goalYaw, k); cam.pitch = lerp(cam.pitch, cam.goalPitch, k); cam.dist = lerp(cam.dist, cam.goalDist * Math.max(1, 1.5 / cam.aspect), k2);
    if (!cam.free && S) { cam.tx = lerp(cam.tx, S.player.x, k2); cam.tz = lerp(cam.tz, S.player.z + 1.5, k2); }
    const ya = cam.yaw * Math.PI / 180, pi = cam.pitch * Math.PI / 180, target = [cam.tx, 1.6, cam.tz];
    const pos = V.add(target, [Math.sin(ya) * Math.cos(pi) * cam.dist, Math.sin(pi) * cam.dist, Math.cos(ya) * Math.cos(pi) * cam.dist]);
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
    const s = -cam.pos[1] / d[1];
    return { x: cam.pos[0] + d[0] * s, z: cam.pos[2] + d[2] * s };
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
      if (p[6] && !visible({ hideIf: p[6][0] === "!" ? null : p[6], showIf: p[6][0] === "!" ? p[6].slice(1) : null }, cleared)) continue;
      const [name, x, z, rot, y, sc] = p, mdl = models[name], s = sc === undefined || sc === null ? T : sc, mm = trs(x, y || 0, z, rot || 0, s);
      for (const { g, o } of mdl.gpu) {
        const lo = o.min, hi = o.max, cx = (lo[0] + hi[0]) / 2, cz = (lo[2] + hi[2]) / 2;
        const c = [mm[0] * cx + mm[8] * cz + mm[12], (lo[1] + hi[1]) / 2 * s + (y || 0), mm[2] * cx + mm[10] * cz + mm[14]];
        const m = o.material;
        items.push({ g, mat: m, model: new Float32Array(mm), center: c, top: hi[1] * s + (y || 0), rad: Math.max(hi[0] - lo[0], hi[2] - lo[2]) * s / 2,
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
    const colliders = (def.colliders || []).filter((c) => visible(c, cleared)).map((c) => ({ minX: c.x - c.w / 2, maxX: c.x + c.w / 2, minZ: c.z - c.d / 2, maxZ: c.z + c.d / 2 }));
    const events = (def.events || []).filter((e) => visible(e, cleared)).map((e) => Object.assign({ w: 3, d: 3, trigger: "touch", inside: false, done: false }, e));
    const skyInfo = await buildSky(def.sky);
    return { name, def, skyInfo, items, npcs, events, sheets, stex, colliders, bounds: def.bounds || { minX: -24, maxX: 24, minZ: -16, maxZ: 16 },
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
    // Tall pieces standing between the camera and the player fade out (skipped) so the hero is never hidden behind a wall or tree.
    const p3 = [S.player.x, 1.2, S.player.z], cp = V.sub(p3, cam.pos), cl = Math.hypot(cp[0], cp[1], cp[2]) || 1, cd = V.mul(cp, 1 / cl);
    const opaque = [], blend = [];
    for (const it of S.items) {
      if (it.top > 2.2) {
        const w = V.sub(it.center, cam.pos), t = V.dot(w, cd);
        if (t > 1 && t < cl - 0.5) { const q = V.sub(w, V.mul(cd, t)); if (Math.hypot(q[0], q[1], q[2]) < it.rad + 1.6 && it.center[1] > 0) continue; }
      }
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
    drawQuad({ tex: S.stex[texKey], origin: [wx, 0, wz], right, up: [0, 1, 0], w: q.w, h: q.h, ax: flip ? 1 - q.ax : q.ax, ay: q.ay, flip,
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
    if (S._decFor !== S.def) { S._decFor = S.def; const cl = getCleared(); S._dec = (S.def.decals || []).filter((d) => (!d.hideIf || !cl.has(d.hideIf)) && (!d.showIf || cl.has(d.showIf))); }
    for (const dc of S._dec) {
      const a = (dc.spin ? clock * dc.spin : 0) * Math.PI / 180, c = Math.cos(a), s = Math.sin(a), pulse = 0.8 + 0.2 * Math.sin(clock * 2 + dc.x);
      const col = dc.color || [0.7, 0.55, 1, 1];
      drawQuad({ tex: dc.type === "glow" ? TEX.glow : TEX.glyph, origin: [dc.x, 0.06, dc.z], right: [c, 0, s], up: [-s, 0, c],
        w: dc.r * 2, h: dc.r * 2, ax: 0.5, ay: 0.5, tint: [col[0] * pulse, col[1] * pulse, col[2] * pulse, 1] });
    }
    BLEND_N();
    // active NPC ring
    const act = S.active;
    // shadows
    const actors = [{ x: S.player.x, z: S.player.z, w: 1.6 }].concat(S.npcs.map((n) => ({ x: n.x, z: n.z, w: (n.h || 2.3) * 0.7 })));
    for (const a of actors) drawQuad({ tex: TEX.shadow, origin: [a.x, 0.04, a.z], right: [1, 0, 0], up: [0, 0, -1], w: a.w, h: a.w * 0.55, ax: 0.5, ay: 0.5 });
    if (act) { BLEND_ADD(); const p = 0.7 + 0.3 * Math.sin(clock * 6); drawQuad({ tex: TEX.ring, origin: [act.x, 0.08, act.z], right: [1, 0, 0], up: [0, 0, -1], w: 2.6, h: 2.6, ax: 0.5, ay: 0.5, tint: [1, 0.85, 0.4, p] }); BLEND_N(); }
    if (S.player.target) { BLEND_ADD(); const p = 0.6 + 0.4 * Math.sin(clock * 8); drawQuad({ tex: TEX.ring, origin: [S.player.target.x, 0.08, S.player.target.z], right: [1, 0, 0], up: [0, 0, -1], w: 1.1, h: 1.1, ax: 0.5, ay: 0.5, tint: [0.6, 0.9, 1, p] }); BLEND_N(); }

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
        drawSpriteFrame(sh.file, sh, frame, pl.x, pl.z, pl.h, false);
      } else {
        const n = o.n;
        if (n.bossTex) {
          const bt = n.bossTex, h = n.h, w = h * bt.aspect, tint = n.locked ? [0.35, 0.35, 0.42, 1] : [1, 1, 1, 1];
          drawQuad({ tex: bt.tex, origin: [n.x, n.base || 0, n.z], right, up: [0, 1, 0], w, h, ax: 0.5, ay: 0, tint, fogd: o.d });
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
  function stepPlayer(dt) {
    const p = S.player, R = 0.55;
    let mx = 0, mz = 0;
    const f = [-Math.sin(cam.yaw * Math.PI / 180), -Math.cos(cam.yaw * Math.PI / 180)], r = [Math.cos(cam.yaw * Math.PI / 180), -Math.sin(cam.yaw * Math.PI / 180)];
    const k = (n) => keys[n] ? 1 : 0;
    const ix = k("d") + k("arrowright") - k("a") - k("arrowleft"), iy = k("w") + k("arrowup") - k("s") - k("arrowdown");
    if (ix || iy) { mx = f[0] * iy + r[0] * ix; mz = f[1] * iy + r[1] * ix; p.target = null; p.wantNpc = null; }
    else if (p.target) {
      const dx = p.target.x - p.x, dz = p.target.z - p.z, d = Math.hypot(dx, dz);
      if (d < 0.25) { p.target = null; if (p.wantNpc) { const n = p.wantNpc; p.wantNpc = null; interact(n); } } else { mx = dx / d; mz = dz / d; }
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
      if (!moved) { p.moving = false; if (p.target) { p.target = null; if (p.wantNpc) { const n = p.wantNpc; p.wantNpc = null; if (Math.hypot(n.x - p.x, n.z - p.z) < 6) interact(n); } } }
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
  function condOk(e, c) { return !((e.if && !c.has(e.if)) || (e.unless && c.has(e.unless)) || (minRankOf(e) && rankOf() < minRankOf(e))); }
  let autorunPending = false;
  function endScript(noRefresh) {
    const dirty = script && script.dirty; script = null; if (sayEl) sayEl.style.display = "none";
    renderQuest();
    if (dirty && !noRefresh && S && S.name) switchScene(S.name, S.player.x, S.player.z, true);   // a flag changed: re-filter npcs / pieces
  }
  function stepScript() {
    while (script && script.queue.length) {
      const a = script.queue.shift();
      if (!condOk(a, getCleared())) continue;                                                              // conditional step
      if (a.type === "say") {
        script.waiting = true; sayEl.querySelector(".s-who").textContent = a.who || (script.owner.name || ""); sayEl.querySelector(".s-text").textContent = a.text || "";
        sayEl.style.display = "block"; return;
      }
      if (a.type === "hub") { if (a.action && O) { savePos(); O.activate(a.action); } continue; }
      if (a.type === "warp") { endScript(true); switchScene(a.scene, a.x, a.z); return; }
      if (a.type === "tp") { const pl = S.player; pl.x = a.x; pl.z = a.z; pl.target = null; pl.wantNpc = null; primeEvents(); cam.tx = pl.x; cam.tz = pl.z + 1.5; updateCamera(0.016, true); if (a.fade !== false) flashOff(); continue; }   // same-scene teleport (fades the flash back out)
      if (a.type === "battle") { endScript(true); startBattle(a); return; }
      if (a.type === "flag") { const c = getCleared(); c.add(a.key); setCleared(c); script.dirty = true; continue; }
      if (a.type === "flash") { script.waiting = true; script.lock = true; flashOn(); const sc = script; setTimeout(() => { sc.lock = false; sc.waiting = false; if (script === sc) stepScript(); }, 1300); return; }
      if (a.type === "rest") { script.waiting = true; restParty(); return; }
      if (a.type === "chest") { script.waiting = true; restParty("/api/story/chest", { loot: a.loot || {} }); return; }
      if (a.type === "recruit") { script.waiting = true; restParty("/api/story/recruit", { name: a.name }); return; }
      if (a.type === "pass_time") { script.waiting = true; restParty("/api/story/pass_time"); return; }
      if (a.type === "reset_progress") { resetCleared(a.prefix || ""); continue; }
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
  const visible = (o, c) => (!o.hideIf || !c.has(o.hideIf)) && (!o.showIf || c.has(o.showIf));
  function say(who, text) { script = { owner: { name: who }, queue: [{ type: "say", who, text }], waiting: false }; stepScript(); }
  async function startBattle(a) {
    if (!(state && ((state.story_party || state.party) || []).length)) { say("", "You have no story heroes to fight with."); return; }
    try { await fetch("/api/world/hub_battle", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ boss_id: a.boss || "", level: Array.isArray(a.level) ? 0 : (a.level || 0), level_min: Array.isArray(a.level) ? a.level[0] : (a.level_min || 0), level_max: Array.isArray(a.level) ? a.level[1] : (a.level_max || 0), pool: a.pool || [], level_rel: a.level_rel || null }) }); }
    catch (e) { say("", "The battle server could not be reached."); return; }
    savePos();
    location.href = "/battle?return=hub3d&scene=" + encodeURIComponent(S.name || "olympus") + (a.key ? "&key=" + encodeURIComponent(a.key) : "") + (S.def && S.def.restart ? "&restart=" + encodeURIComponent(S.def.restart) : "");
  }
  async function restParty(url, body) {
    let text = "You rest a while.";
    try { const r = await (await fetch(url || "/api/menu/rest", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) })).json(); if (r && r.message) text = r.message; if (O && O.refresh) O.refresh(); } catch (e) { text = "You try to rest, but nothing happens."; }
    if (O && O.sfx && O.SFX) O.sfx(O.SFX.confirm);
    sayEl.querySelector(".s-who").textContent = ""; sayEl.querySelector(".s-text").textContent = text; sayEl.style.display = "block";
  }
  /* ---------- story: objective line, screen flash, scene autorun ---------- */
  function storyObjective() {
    const c = getCleared();
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
      return "The Shard Vault is silent. Report to Captain Rhea: the trail leads further than this base.";
    }
    if (c.has("st_siege")) return "Defend the Colosseum!";
    if (c.has("st_free")) return "You are free! Leave through the main gate and take the ferry home to Paradise Island.";
    if (c.has("st_done")) {
      const fr = (S && S.def && S.def.freeRank) || 3, r = rankOf();
      return S && S.name === "prison" ? `You are a slave of the Colosseum. Fight for the Overseer until you rise past Rank ${fr - 1} to win your freedom` + (r ? ` (you are Rank ${r}).` : ".") : "";
    }
    if (!c.has("st_quest")) return "Speak with Elder Mahina in the village.";
    if (!c.has("st_found")) return "Find the missing villager, Lani, in the Hollow Crypt (north of the village).";
    if (!c.has("st_attack")) return "Leave the crypt.";
    return "Defend the village!";
  }
  function renderQuest() {
    if (!hudEls.quest) return;
    const t = (S && S.def && S.def.story) ? storyObjective() : "";
    hudEls.quest.style.display = t ? "block" : "none"; hudEls.quest.innerHTML = t ? "<b>QUEST</b><span></span>" : ""; if (t) hudEls.quest.lastChild.textContent = t;
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
      setTimeout(() => { if (!script && S && !S.switching) runActions({ name: "", actions: e.actions }); }, 700); return;
    }
  }
  /* Where the player stood when they left for a battle / shop / heroes page, so coming back puts them there
     instead of at the scene's spawn point. Per tab (sessionStorage), read once on the next load. */
  const POS_KEY = "h3dPos";
  function savePos() { try { if (S && S.name) sessionStorage.setItem(POS_KEY, JSON.stringify({ scene: S.name, x: S.player.x, z: S.player.z, face: S.player.face })); } catch (e) {} }
  /* Random encounters: scene.encounters = {rate, level:[lo,hi], pool:[enemy ids], zones:[{x,z,w,d}]}. Walking inside a zone
     counts distance; every ~rate units an ambush starts a wild fight at a level rolled from the range. */
  function encounterStep(dist) {
    const enc = S.def && S.def.encounters; if (!enc || script || S.switching || modalOpen() || !(state && ((state.story_party || state.party) || []).length)) return;
    const p = S.player, zs = enc.zones;
    let zone = null;
    if (zs && zs.length) { zone = zs.find((z) => Math.abs(p.x - z.x) <= z.w / 2 && Math.abs(p.z - z.z) <= z.d / 2); if (!zone) return; }
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
  function applySceneMusic() { try { if (O && O.music) O.music(S && S.def && S.def.music ? S.def.music : null); } catch (e) {} }   // scene.music = {url, intro?} set in the 3D editor
  async function switchScene(name, x, z, force) {
    if (S && S.switching) return; if (S) S.switching = true;
    const old = S; if (hudEls.load) { hudEls.load.textContent = "Loading…"; hudEls.load.classList.remove("done"); }
    try {
      const loaded = await loadScene(name, null);
      if (ui && ui.parentNode) ui.parentNode.removeChild(ui);
      S = loaded; S.player.face = old ? old.player.face : "south";
      if (x != null) S.player.x = x; if (z != null) S.player.z = z;
      primeEvents(); buildDom(); sayEl = null; buildSayBox(); cam.free = false; cam.tx = S.player.x; cam.tz = S.player.z + 1.5; updateCamera(0.016, true);
      if (state) H3.onState(state); hudEls.load.classList.add("done"); applySceneMusic(); try { O && O.refresh && O.refresh(); } catch (e) {} runAutorun();
    } catch (err) { console.warn("[Hub3D] warp failed:", err); flashOff(); if (old) old.switching = false; if (hudEls.load) { hudEls.load.textContent = "Could not load scene: " + name; setTimeout(() => hudEls.load.classList.add("done"), 1500); } }
  }
  function buildSayBox() {
    sayEl = document.createElement("div"); sayEl.className = "h3d-say"; sayEl.innerHTML = '<div class="s-who"></div><div class="s-text"></div><div class="s-go">[E] continue</div>';
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
  function buildDom() {
    ui = document.createElement("div"); ui.id = "h3d-ui"; sceneEl.appendChild(ui);
    const mk = (cls, parent) => { const e = document.createElement("div"); e.className = cls; (parent || ui).appendChild(e); return e; };
    S.npcs.forEach((n) => {
      n.el = mk("h3d-npc"); n.hit = mk("h3d-hit", n.el); n.tag = mk("h3d-tag", n.el); n.tag.textContent = n.name; n.alert = mk("h3d-alert", n.el); n.alert.textContent = "!";
      n.bub = mk("h3d-bubble", n.el);
      n.bub.innerHTML = '<div class="b-name"></div><div class="b-text"></div><div class="b-btn"></div>';
      n.hit.addEventListener("click", (e) => { e.stopPropagation(); clickNpc(n); });
      n.hit.addEventListener("mouseenter", () => { n.hover = true; }); n.hit.addEventListener("mouseleave", () => { n.hover = false; });
    });
    hudEls.hint = mk("h3d-hint"); hudEls.hint.textContent = "WASD / arrows move  ·  Shift run  ·  E talk  ·  click the ground or an NPC  ·  drag to turn  ·  wheel zoom";
    hudEls.load = mk("h3d-loading"); hudEls.load.textContent = "Loading the plaza…";
    hudEls.quest = mk("h3d-quest");
    hudEls.rank = mk("h3d-rank"); hudEls.rank.innerHTML = '<b></b><span></span><i><u></u></i>';
  }
  function clickNpc(n) {
    if (modalOpen()) return;
    if (Math.hypot(n.x - S.player.x, n.z - S.player.z) < (n.reach || 4.6)) { interact(n); return; }
    // walk to a spot in front of them (towards the camera side), then talk
    const dx = S.player.x - n.x, dz = S.player.z - n.z, d = Math.hypot(dx, dz) || 1, stop = Math.min(d, 3.0);
    S.player.target = { x: n.x + dx / d * stop, z: n.z + dz / d * stop }; S.player.wantNpc = n;
  }
  function syncDom() {
    const showN = S.active;
    if (hudEls.evhint) { const ev = S.activeEv; hudEls.evhint.style.display = ev && !script ? "block" : "none"; if (ev) hudEls.evhint.textContent = "[E] " + (ev.prompt || ev.name || "Interact"); }
    for (const n of S.npcs) {
      const foot = project([n.x, n.base || 0, n.z]), head = project([n.x, (n.base || 0) + n.h, n.z]);
      const hh = Math.max(20, foot.y - head.y), hw = hh * (n.bossTex ? n.bossTex.aspect : (n.sheet ? Math.min(n.sheet.cw / n.sheet.refH, 1) : 0.5)) * 0.9;
      n.el.style.left = foot.x + "px"; n.el.style.top = foot.y + "px"; n.el.style.zIndex = String(10 + Math.round(foot.y));
      n.hit.style.width = hw + "px"; n.hit.style.height = hh + "px"; n.hit.style.cursor = "pointer";
      n.tag.style.top = (-hh - 4) + "px"; n.alert.style.top = (-hh - 40) + "px";
      n.tag.classList.toggle("on", n === showN || n.hover);
      const line = npcLine(n);
      n.alert.style.display = n.alertOn ? "block" : "none";
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
      .h3d-tag { position:absolute; transform:translate(-50%,-100%); white-space:nowrap; font-size:12px; font-weight:700; letter-spacing:.04em; color:#f1ecdd; padding:2px 9px;
        background:rgba(18,16,28,.62); border:1px solid rgba(232,199,102,.25); border-radius:999px; text-shadow:0 1px 3px #000; opacity:.8; pointer-events:none; transition:opacity .15s, border-color .15s; }
      .h3d-tag.on { opacity:1; border-color:var(--gold); color:var(--gold); }
      .h3d-alert { display:none; position:absolute; transform:translate(-50%,-100%); width:24px; height:24px; line-height:24px; text-align:center; border-radius:50%; background:#e0455a; color:#fff;
        font-weight:800; box-shadow:0 0 12px rgba(224,69,90,.8); pointer-events:none; animation:h3d-bob 1s ease-in-out infinite alternate; }
      @keyframes h3d-bob { from { margin-top:0; } to { margin-top:-6px; } }
      .h3d-bubble { display:none; position:absolute; transform:translate(-50%,-100%); width:250px; padding:10px 14px 11px; border-radius:14px; pointer-events:none;
        background:rgba(18,16,28,.9); border:1px solid var(--gold); box-shadow:0 6px 24px rgba(0,0,0,.55); }
      .h3d-bubble::after { content:""; position:absolute; left:50%; bottom:-7px; width:12px; height:12px; background:rgba(18,16,28,.95); border-right:1px solid var(--gold); border-bottom:1px solid var(--gold); transform:translateX(-50%) rotate(45deg); }
      .b-name { font-size:12px; font-weight:800; letter-spacing:.06em; color:var(--gold); text-transform:uppercase; }
      .b-text { font-size:13px; line-height:1.4; margin:4px 0 8px; color:var(--text); }
      .b-btn { display:inline-block; font-size:12px; font-weight:800; padding:5px 12px; border-radius:9px; color:#241a05; background:linear-gradient(180deg,#e8c766,#b8892c); }
      .h3d-hint { position:absolute; left:50%; bottom:12px; transform:translateX(-50%); font-size:11px; color:var(--dim); background:rgba(18,16,28,.55); padding:4px 12px; border-radius:999px; white-space:nowrap; }
      .h3d-loading { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:18px; letter-spacing:.1em; color:var(--gold); background:rgba(10,9,16,.85); transition:opacity .5s; pointer-events:none; }
      .h3d-loading.done { opacity:0; }
      .h3d-rank { position:absolute; left:22px; top:92px; width:210px; padding:7px 12px 9px; border-radius:12px; background:var(--panel-bg); border:1px solid var(--panel-border); pointer-events:none; }
      .h3d-quest { position:absolute; left:22px; top:166px; width:210px; padding:7px 12px 9px; border-radius:12px; background:var(--panel-bg); border:1px solid var(--panel-border); pointer-events:none; display:none; }
      .h3d-quest b { display:block; font-size:11px; letter-spacing:.12em; color:var(--gold); } .h3d-quest span { font-size:12px; color:#f0ead0; line-height:1.35; }
      .h3d-rank b { display:block; font-size:11px; letter-spacing:.12em; color:var(--gold); } .h3d-rank span { font-size:11px; color:var(--dim); }
      .h3d-rank i { display:block; height:6px; border-radius:3px; background:rgba(255,255,255,.12); margin-top:5px; overflow:hidden; } .h3d-rank u { display:block; height:100%; width:0; background:linear-gradient(90deg,#8a6a1a,#e8c766); transition:width .5s; }
      .h3d-say { display:none; position:absolute; left:50%; bottom:64px; transform:translateX(-50%); width:min(620px,86vw); padding:12px 18px 14px; border-radius:14px; pointer-events:auto; cursor:pointer; z-index:8;
        background:rgba(18,16,28,.94); border:1px solid var(--gold); box-shadow:0 8px 30px rgba(0,0,0,.6); }
      .s-who { font-size:12px; font-weight:800; letter-spacing:.07em; color:var(--gold); text-transform:uppercase; } .s-who:empty { display:none; }
      .s-text { font-size:15px; line-height:1.5; margin:5px 0 8px; color:var(--text); white-space:pre-wrap; } .s-go { font-size:11px; color:var(--dim); text-align:right; }
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
    if (!modalOpen() && !scriptActive()) stepPlayer(dt); else S.player.moving = false;
    updateCamera(dt, false);
    render(now); syncDom();
  }
  function bindInput() {
    window.addEventListener("keydown", (e) => {
      if (!H3.on || modalOpen()) return;
      if (script) { if (e.key === "e" || e.key === "E" || e.key === "Enter" || e.key === " ") { e.preventDefault(); if (!e.repeat) advanceScript(); } return; }
      if (e.target && /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
      const k = e.key.toLowerCase();
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
      if (!drag) return; const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 6) drag.moved = true;
      if (drag.moved) { cam.goalYaw = clamp(drag.yaw - dx * 0.25, -80, 80); cam.goalPitch = clamp(drag.pitch + dy * 0.15, 14, 62); }
    });
    window.addEventListener("pointerup", (e) => {
      if (!drag) return; const d = drag; drag = null;
      if (d.moved || !H3.on || modalOpen() || script) return;
      const r = sceneEl.getBoundingClientRect(), g = groundAt(e.clientX - r.left, e.clientY - r.top);
      if (g) { const b = S.bounds; S.player.target = { x: clamp(g.x, b.minX + 1, b.maxX - 1), z: clamp(g.z, b.minZ + 1, b.maxZ - 1) }; S.player.wantNpc = null; }
    });
    sceneEl.addEventListener("wheel", (e) => { if (!H3.on || modalOpen()) return; e.preventDefault(); cam.goalDist = clamp(cam.goalDist * (1 + Math.sign(e.deltaY) * 0.08), 12, 48); }, { passive: false });
    window.addEventListener("resize", resize);
  }

  /* ---------- init ---------- */
  H3.init = async function (opts) {
    O = opts; sceneEl = document.getElementById("scene");
    const q = new URLSearchParams(location.search);
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
      S = loaded; buildDom(); buildSayBox(); bindInput(); applySceneMusic();
      if (q.get("cam")) { const c = q.get("cam").split(",").map(Number); cam.free = true; cam.tx = c[0]; cam.tz = c[1]; cam.goalYaw = c[2] || 0; cam.goalPitch = c[3] || 30; cam.goalDist = c[4] || 25; }
      if (back && back.scene === sceneName && !q.get("at") && isFinite(back.x) && isFinite(back.z)) { S.player.x = back.x; S.player.z = back.z; if (back.face) S.player.face = back.face; }
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
  H3.debug = { cam, project, groundAt, scene: () => S };
})();

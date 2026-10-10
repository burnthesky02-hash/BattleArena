/* =====================================================================
   Battle Arena -- 2.5D battle view  (html_battle/battle3d.js)

   A render layer for the real battle page. The page's own 2D logic is untouched: SpriteView still
   tweens x/y in a logical "virtual pixel" space (animateMelee, tweenPosition, homeX/homeY ...), the
   WebSocket flow, targeting and the HUD all run as before. This file only changes what is DRAWN:

     * the combatants are drawn by a raw-WebGL scene (perspective camera, upright billboards, shadows,
       arena floor, backdrop) onto a canvas that sits UNDER the page's DOM overlays;
     * each SpriteView's DOM anchor is moved to the projected screen position every frame, so the
       existing nameplates, status icons, click-to-target hit boxes and hover highlights keep working;
     * the 2D FX / floating numbers / callouts keep playing as DOM, but they are positioned through
       B3D.screenPt() and scaled through B3D.persp(), so they land on the 3D sprites.

   index.html calls B3D.init({...}) once, right before connect(). B3D.setOn(false) (the "2D" button)
   restores the original 2D drawing at any time.
   ===================================================================== */
(function () {
  "use strict";

  const PX = 70;                        // virtual pixels per world unit (x/PX = world x, y/PX = world z)
  const COLS = 6, ROWS = 6;
  const MID = 350;                      // virtual-px distance of each side's middle row from arena centre

  const B3D = window.B3D = { on: false, ready: false, failed: false, actionCam: true };
  let C = null;                         // context handed over by index.html
  let gl = null, canvas = null, vignette = null, stageEl = null;
  let prog = null, quadBuf = null;
  const U = {};
  const TEX = {};
  const texCache = new WeakMap();
  let bgTex = null, maxTex = 4096;
  let lastT = 0;
  let drag = null;

  /* ---------- math ---------- */
  const V = {
    sub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]],
    add: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]],
    mul: (a, s) => [a[0] * s, a[1] * s, a[2] * s],
    dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
    cross: (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]],
    norm: (a) => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; },
  };
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const rand = (a, b) => a + Math.random() * (b - a);
  function perspective(fovy, aspect, n, f) {
    const t = 1 / Math.tan(fovy / 2);
    return [t / aspect, 0, 0, 0, 0, t, 0, 0, 0, 0, (f + n) / (n - f), -1, 0, 0, 2 * f * n / (n - f), 0];
  }
  function lookAt(e, c, up) {
    const z = V.norm(V.sub(e, c)), x = V.norm(V.cross(up, z)), y = V.cross(z, x);
    return { m: [x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0, -V.dot(x, e), -V.dot(y, e), -V.dot(z, e), 1], x, y, z };
  }
  function mul4(a, b) {
    const o = new Array(16);
    for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++)
      o[c * 4 + r] = a[r] * b[c * 4] + a[4 + r] * b[c * 4 + 1] + a[8 + r] * b[c * 4 + 2] + a[12 + r] * b[c * 4 + 3];
    return o;
  }

  /* ---------- camera ---------- */
  const PRESETS = {
    "Side":          { yaw: 0,   pitch: 13, dist: 29, fov: 27, tx: 0,    ty: 1.4 },
    "3/4 view":      { yaw: -14, pitch: 17, dist: 28, fov: 27, tx: 0,    ty: 1.3 },
    "Over shoulder": { yaw: 12,  pitch: 12, dist: 27, fov: 30, tx: -0.8, ty: 1.4 },
    "High":          { yaw: -10, pitch: 36, dist: 29, fov: 27, tx: 0,    ty: 0.6 },
  };
  const PRESET_NAMES = Object.keys(PRESETS);
  let presetName = "Over shoulder";
  const cam = {
    yaw: -14, pitch: 17, dist: 28, fov: 27, tx: 0, ty: 1.3, tz: 0,
    vp: null, pos: [0, 0, 30], right: [1, 0, 0], fwd: [0, 0, -1], camX: [1, 0, 0], camY: [0, 1, 0],
    w: 1, h: 1, aspect: 1, g: { yaw: -14, pitch: 17, dist: 28, fov: 27, tx: 0, ty: 1.3, tz: 0 },
    focus: { x: 0, z: 0, push: 0 },
  };
  function setPreset(name) {
    if (!PRESETS[name]) name = "Over shoulder";
    presetName = name;
    Object.assign(cam.g, PRESETS[name]); cam.g.tz = 0;
    try { localStorage.setItem("battleCam2", name); } catch (e) {}
    refreshButtons();
  }
  function updateCamera(dt) {
    const k = 1 - Math.pow(0.0015, dt), k2 = 1 - Math.pow(0.02, dt);
    const act = B3D.actionCam ? cam.focus.push : 0;
    const fit = Math.max(1, 1.7 / cam.aspect);            // narrow windows pull back so both sides stay in frame
    const goalDist = cam.g.dist * fit * (1 - 0.26 * act);
    cam.yaw = lerp(cam.yaw, cam.g.yaw, k); cam.pitch = lerp(cam.pitch, cam.g.pitch, k); cam.fov = lerp(cam.fov, cam.g.fov, k);
    cam.dist = lerp(cam.dist, goalDist, k2);
    cam.tx = lerp(cam.tx, cam.g.tx + cam.focus.x * act * 0.6, k2);
    cam.tz = lerp(cam.tz, cam.g.tz + cam.focus.z * act * 0.6, k2);
    cam.ty = lerp(cam.ty, cam.g.ty, k);
    const ya = cam.yaw * Math.PI / 180, pi = cam.pitch * Math.PI / 180;
    const target = [cam.tx, cam.ty, cam.tz];
    const pos = V.add(target, [Math.sin(ya) * Math.cos(pi) * cam.dist, Math.sin(pi) * cam.dist, Math.cos(ya) * Math.cos(pi) * cam.dist]);
    const L = lookAt(pos, target, [0, 1, 0]);
    cam.pos = pos; cam.right = V.norm([L.x[0], 0, L.x[2]]); cam.camX = L.x; cam.camY = L.y; cam.fwd = V.mul(L.z, -1);
    cam.vp = mul4(perspective(cam.fov * Math.PI / 180, cam.aspect, 0.5, 160), L.m);
  }
  function project(p) {
    const m = cam.vp;
    if (!m) return { x: cam.w / 2, y: cam.h / 2, w: 1 };
    const x = p[0], y = p[1], z = p[2];
    const cx = m[0] * x + m[4] * y + m[8] * z + m[12], cy = m[1] * x + m[5] * y + m[9] * z + m[13], cw = m[3] * x + m[7] * y + m[11] * z + m[15];
    return { x: (cx / cw * 0.5 + 0.5) * cam.w, y: (1 - (cy / cw * 0.5 + 0.5)) * cam.h, w: cw };
  }

  /* ---------- GL ---------- */
  const VS = `
attribute vec2 a;
uniform mat4 u_vp; uniform vec3 u_o, u_r, u_u; uniform vec2 u_size, u_anchor;
varying vec2 v_uv;
void main(){
  vec2 p = (a - u_anchor) * u_size;
  gl_Position = u_vp * vec4(u_o + u_r * p.x + u_u * p.y, 1.0);
  v_uv = a;
}`;
  const FS = `
precision mediump float;
uniform sampler2D u_tex; uniform vec4 u_rect; uniform vec2 u_eps;
uniform float u_flip; uniform vec4 u_tint;
varying vec2 v_uv;
void main(){
  vec2 uv = v_uv; if (u_flip > .5) uv.x = 1.0 - uv.x;
  vec2 t = u_rect.xy + vec2(uv.x, 1.0 - uv.y) * u_rect.zw;
  t = clamp(t, u_rect.xy + u_eps, u_rect.xy + u_rect.zw - u_eps);
  vec4 c = texture2D(u_tex, t);
  c.rgb *= u_tint.rgb;
  gl_FragColor = c * u_tint.a;
}`;
  function mkShader(type, src) {
    const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  }
  function makeTexture(source) {
    const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    return t;
  }
  // Sprite sheets can be bigger than the GPU's max texture size (boss sheets) -- shrink those on upload.
  function texFor(img) {
    if (!img || !img.complete || !img.naturalWidth) return null;
    let t = texCache.get(img);
    if (t) return t;
    let src = img;
    const big = Math.max(img.naturalWidth, img.naturalHeight);
    if (big > maxTex) {
      const k = maxTex / big, c = document.createElement("canvas");
      c.width = Math.floor(img.naturalWidth * k); c.height = Math.floor(img.naturalHeight * k);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      src = c;
    }
    t = makeTexture(src);
    texCache.set(img, t);
    return t;
  }
  function canvasTex(w, h, draw) {
    const c = document.createElement("canvas"); c.width = w; c.height = h;
    draw(c.getContext("2d"), w, h);
    return makeTexture(c);
  }
  const BLEND_NORMAL = () => gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  const BLEND_ADD = () => gl.blendFunc(gl.ONE, gl.ONE);

  function drawQuad(o) {
    gl.uniform3fv(U.u_o, o.origin); gl.uniform3fv(U.u_r, o.right); gl.uniform3fv(U.u_u, o.up);
    gl.uniform2f(U.u_size, o.w, o.h); gl.uniform2f(U.u_anchor, o.ax === undefined ? 0.5 : o.ax, o.ay === undefined ? 0 : o.ay);
    gl.bindTexture(gl.TEXTURE_2D, o.tex);
    const r = o.rect || [0, 0, 1, 1]; gl.uniform4f(U.u_rect, r[0], r[1], r[2], r[3]);
    gl.uniform2f(U.u_eps, o.epsx || 0, o.epsy || 0);
    gl.uniform1f(U.u_flip, o.flip ? 1 : 0);
    const t = o.tint || [1, 1, 1, 1]; gl.uniform4f(U.u_tint, t[0], t[1], t[2], t[3]);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  function buildTextures() {
    TEX.white = canvasTex(4, 4, (g, w, h) => { g.fillStyle = "#fff"; g.fillRect(0, 0, w, h); });
    TEX.shadow = canvasTex(128, 128, (g, w, h) => {
      const r = g.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2);
      r.addColorStop(0, "rgba(0,0,0,.75)"); r.addColorStop(0.6, "rgba(0,0,0,.35)"); r.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = r; g.fillRect(0, 0, w, h);
    });
    TEX.ring = canvasTex(256, 256, (g, w, h) => {
      g.strokeStyle = "rgba(255,255,255,1)"; g.lineWidth = 10; g.beginPath(); g.arc(w / 2, h / 2, w / 2 - 14, 0, 7); g.stroke();
      g.strokeStyle = "rgba(255,255,255,.35)"; g.lineWidth = 22; g.beginPath(); g.arc(w / 2, h / 2, w / 2 - 18, 0, 7); g.stroke();
    });
    // Arena platform: stone disc in the backdrop's purple/cream palette with a soft edge.
    TEX.disc = canvasTex(1024, 1024, (g, w, h) => {
      const cx = w / 2, cy = h / 2, R = w / 2 - 2;
      g.save(); g.beginPath(); g.arc(cx, cy, R, 0, 7); g.clip();
      let r = g.createRadialGradient(cx, cy, 0, cx, cy, R);
      r.addColorStop(0, "#d9cfb4"); r.addColorStop(0.38, "#c2b79b"); r.addColorStop(0.42, "#4a3d70"); r.addColorStop(0.8, "#2c2447"); r.addColorStop(1, "#181230");
      g.fillStyle = r; g.fillRect(0, 0, w, h);
      g.strokeStyle = "rgba(20,12,40,.55)"; g.lineWidth = 3;
      for (let i = 0; i < 24; i++) { const a = i / 24 * Math.PI * 2; g.beginPath(); g.moveTo(cx + Math.cos(a) * R * 0.14, cy + Math.sin(a) * R * 0.14); g.lineTo(cx + Math.cos(a) * R, cy + Math.sin(a) * R); g.stroke(); }
      [0.14, 0.26, 0.40, 0.62, 0.80, 0.93].forEach((k, i) => {
        g.lineWidth = i === 2 ? 10 : 4; g.strokeStyle = i === 2 ? "rgba(20,12,40,.8)" : "rgba(10,6,24,.55)";
        g.beginPath(); g.arc(cx, cy, R * k, 0, 7); g.stroke();
      });
      g.shadowColor = "#a066ff"; g.shadowBlur = 26; g.strokeStyle = "#c79bff"; g.lineWidth = 6; g.beginPath(); g.arc(cx, cy, R * 0.87, 0, 7); g.stroke(); g.shadowBlur = 0;
      g.lineWidth = 2; g.strokeStyle = "rgba(10,6,24,.35)";
      for (let i = 0; i < 70; i++) {
        let x = rand(0, w), y = rand(0, h); g.beginPath(); g.moveTo(x, y);
        for (let k = 0; k < 5; k++) { x += rand(-40, 40); y += rand(-40, 40); g.lineTo(x, y); } g.stroke();
      }
      for (let i = 0; i < 5000; i++) { g.fillStyle = `rgba(${Math.random() < 0.5 ? 255 : 0},${Math.random() < 0.5 ? 255 : 0},${Math.random() < 0.5 ? 255 : 0},.035)`; g.fillRect(rand(0, w), rand(0, h), 2, 2); }
      g.restore();
      g.globalCompositeOperation = "destination-in";
      const m = g.createRadialGradient(cx, cy, R * 0.9, cx, cy, R); m.addColorStop(0, "rgba(0,0,0,1)"); m.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = m; g.fillRect(0, 0, w, h);
    });
  }


  /* ---------- 3D map: GLB models rendered under the sprites (see battlemap.js for the parser) ---------- */
  const MAP_URL = "/battle/maps/";
  const MVS = `
attribute vec3 p; attribute vec3 n; attribute vec2 t; attribute vec4 c;
uniform mat4 u_vp; uniform mat4 u_model;
varying vec3 v_n; varying vec2 v_t; varying vec4 v_c; varying float v_d;
void main(){
  gl_Position = u_vp * (u_model * vec4(p, 1.0));
  v_n = mat3(u_model) * n; v_t = t; v_c = c; v_d = gl_Position.w;
}`;
  const MFS = `
precision mediump float;
uniform sampler2D u_tex; uniform vec4 u_color; uniform vec3 u_emis;
uniform float u_cut, u_unlit, u_mode;
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
  let mprog = null, idxUint = false, anisoExt = null;
  const MU = {};
  const modelCache = new Map();
  let mapList = [], mapId = "painted", curMap = null, mapToken = 0, mapErr = null;

  function initMeshProgram() {
    mprog = gl.createProgram();
    gl.attachShader(mprog, mkShader(gl.VERTEX_SHADER, MVS)); gl.attachShader(mprog, mkShader(gl.FRAGMENT_SHADER, MFS));
    ["p", "n", "t", "c"].forEach((n, i) => gl.bindAttribLocation(mprog, i, n));
    gl.linkProgram(mprog);
    if (!gl.getProgramParameter(mprog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(mprog));
    ["u_vp", "u_model", "u_tex", "u_color", "u_emis", "u_cut", "u_unlit", "u_mode", "u_ldir", "u_lcol", "u_amb", "u_fogc", "u_fogr"].forEach((n) => { MU[n] = gl.getUniformLocation(mprog, n); });
    idxUint = !!gl.getExtension("OES_element_index_uint");
    anisoExt = gl.getExtension("EXT_texture_filter_anisotropic");
  }
  function useSprite() {
    gl.useProgram(prog);
    gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    for (let i = 1; i < 4; i++) gl.disableVertexAttribArray(i);
  }
  function useMesh() {
    gl.useProgram(mprog);
    for (let i = 0; i < 4; i++) gl.enableVertexAttribArray(i);
  }

  function uploadObject(o) {
    const vc = o.positions.length / 3, data = new Float32Array(vc * 12);
    for (let i = 0; i < vc; i++) {
      data.set(o.positions.subarray(i * 3, i * 3 + 3), i * 12); data.set(o.normals.subarray(i * 3, i * 3 + 3), i * 12 + 3);
      data.set(o.uvs.subarray(i * 2, i * 2 + 2), i * 12 + 6); data.set(o.colors.subarray(i * 4, i * 4 + 4), i * 12 + 8);
    }
    const vbo = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, vbo); gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    let idx = o.indices, itype = gl.UNSIGNED_SHORT;
    if (vc > 65535) { if (!idxUint) return null; itype = gl.UNSIGNED_INT; } else idx = Uint16Array.from(idx);
    const ibo = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ibo); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, idx, gl.STATIC_DRAW);
    return { vbo, ibo, count: idx.length, itype };
  }
  async function makeMapTexture(im, baseUrl) {
    let blob;
    if (im.bytes) blob = new Blob([im.bytes], { type: im.mime });
    else { const r = await fetch(new URL(im.uri, baseUrl)); if (!r.ok) throw new Error("texture " + im.uri); blob = await r.blob(); }
    const bmp = await createImageBitmap(blob, { premultiplyAlpha: "none", colorSpaceConversion: "none" });
    const pot = (v) => Math.min(maxTex, 2048, 1 << Math.max(0, Math.round(Math.log2(Math.max(1, v)))));
    const cv = document.createElement("canvas"); cv.width = pot(bmp.width); cv.height = pot(bmp.height);
    cv.getContext("2d").drawImage(bmp, 0, 0, cv.width, cv.height);
    const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, cv);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
    gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    if (anisoExt) gl.texParameterf(gl.TEXTURE_2D, anisoExt.TEXTURE_MAX_ANISOTROPY_EXT, Math.min(8, gl.getParameter(anisoExt.MAX_TEXTURE_MAX_ANISOTROPY_EXT)));
    return t;
  }
  function loadModel(file) {
    if (modelCache.has(file)) return modelCache.get(file);
    const url = file.startsWith("/") ? encodeURI(file) : MAP_URL + encodeURI(file);     // "/..." = absolute URL (e.g. the Assets folder)
    const pr = (async () => {
      const r = await fetch(url); if (!r.ok) throw new Error(`${file}: HTTP ${r.status}`);
      const parsed = window.B3DMap.parse(await r.arrayBuffer());
      const texs = await Promise.all(parsed.images.map((im) => makeMapTexture(im, new URL(url, location.href)).catch((e) => { console.warn("[B3D] texture failed", e); return null; })));
      const gpu = parsed.objects.map((o) => { const g = uploadObject(o); return g ? { g, o } : null; }).filter(Boolean);
      return { parsed, texs, gpu };
    })();
    modelCache.set(file, pr);
    pr.catch(() => modelCache.delete(file));
    return pr;
  }
  function instMatrix(scale, rotYdeg, pos) {
    const a = rotYdeg * Math.PI / 360;
    return window.B3DMap.mat4TRS(pos, [0, Math.sin(a), 0, Math.cos(a)], [scale, scale, scale]);
  }
  function xfm(m, p) { return [m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12], m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13], m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14]]; }

  async function buildMap(id) {
    const token = ++mapToken;
    const def = await (await fetch(`${MAP_URL}${id}.json`)).json();
    const placements = [{ model: def.model, pos: def.offset || [0, 0, 0], rotY: def.rotY || 0, scale: def.scale || 1 }].concat(def.props || []);
    const items = [];
    for (const pl of placements) {
      const mdl = await loadModel(pl.model);
      const mm = instMatrix(pl.scale || 1, pl.rotY || 0, pl.pos || [0, 0, 0]);
      for (const { g, o } of mdl.gpu) {
        const lo = o.min, hi = o.max, c = xfm(mm, [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2]);
        const topY = xfm(mm, [0, hi[1], 0])[1];
        const mat = o.material;
        items.push({ g, mat, model: new Float32Array(mm), center: c, flat: topY < 0.7, tex: mat.image >= 0 ? mdl.texs[mat.image] : null,
          mode: mat.alphaMode === "BLEND" ? 2 : mat.alphaMode === "MASK" ? 1 : 0 });
      }
    }
    if (token !== mapToken) return null;
    return { id, def, items };
  }

  function drawMap() {
    if (!curMap) return false;
    const d = curMap.def, L = d.light || {}, F = d.fog || {};
    useMesh();
    gl.uniformMatrix4fv(MU.u_vp, false, cam.vp);
    gl.uniform1i(MU.u_tex, 0);
    const ld = V.norm(L.dir || [-0.45, -1, -0.35]), lc = L.color || [1, 0.93, 0.82], am = L.ambient || [0.5, 0.5, 0.6], fc = F.color || [0.1, 0.08, 0.2];
    gl.uniform3f(MU.u_ldir, ld[0], ld[1], ld[2]); gl.uniform3f(MU.u_lcol, lc[0], lc[1], lc[2]); gl.uniform3f(MU.u_amb, am[0], am[1], am[2]);
    gl.uniform3f(MU.u_fogc, fc[0], fc[1], fc[2]); gl.uniform2f(MU.u_fogr, F.near === undefined ? 1e5 : F.near, F.far === undefined ? 2e5 : F.far);
    gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL); gl.depthMask(true);
    // Tall pieces between the camera and the middle of the arena (the near stands/walls) are skipped so they never block the view.
    const tx = cam.tx, tz = cam.tz, dx = cam.pos[0] - tx, dz = cam.pos[2] - tz, dl = Math.hypot(dx, dz) || 1, cullD = d.cullNearCamera;
    const opaque = [], blend = [];
    for (const it of curMap.items) {
      if (cullD && !it.flat && ((it.center[0] - tx) * dx + (it.center[2] - tz) * dz) / dl > cullD) continue;
      (it.mode === 2 ? blend : opaque).push(it);
    }
    const draw = (it) => {
      const g = it.g, m = it.mat;
      gl.bindBuffer(gl.ARRAY_BUFFER, g.vbo);
      gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 48, 0); gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 48, 12);
      gl.vertexAttribPointer(2, 2, gl.FLOAT, false, 48, 24); gl.vertexAttribPointer(3, 4, gl.FLOAT, false, 48, 32);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, g.ibo);
      gl.uniformMatrix4fv(MU.u_model, false, it.model);
      gl.uniform4f(MU.u_color, m.color[0], m.color[1], m.color[2], m.color[3]);
      gl.uniform3f(MU.u_emis, m.emissive[0], m.emissive[1], m.emissive[2]);
      gl.uniform1f(MU.u_cut, m.cutoff); gl.uniform1f(MU.u_unlit, m.unlit ? 1 : 0); gl.uniform1f(MU.u_mode, it.mode);
      gl.bindTexture(gl.TEXTURE_2D, it.tex || TEX.white);
      gl.drawElements(gl.TRIANGLES, g.count, g.itype, 0);
    };
    BLEND_NORMAL();
    opaque.forEach(draw);
    if (blend.length) {
      gl.depthMask(false);
      blend.sort((a, b) => V.dot(V.sub(b.center, cam.pos), cam.fwd) - V.dot(V.sub(a.center, cam.pos), cam.fwd));
      blend.forEach(draw);
    }
    useSprite();
    gl.uniformMatrix4fv(U.u_vp, false, cam.vp);
    return true;
  }

  B3D.setMap = function (id, auto) {
    if (!B3D.ready) return;
    if (id !== "painted" && !mapList.some((m) => m.id === id)) id = "painted";
    mapId = id; mapErr = null;
    if (!auto) { try { localStorage.setItem("battleMap", id); } catch (e) {} }     // a scene's own arena is not remembered as the user's pick
    refreshButtons();
    if (id === "painted") { curMap = null; mapToken++; return; }
    buildMap(id).then((m) => { if (m && mapId === id) curMap = m; })
      .catch((e) => { console.warn("[B3D] map failed, using the painted arena:", e); curMap = null; mapErr = { id, msg: String(e && e.message || e) }; mapId = "painted"; refreshButtons(); });
  };
  async function loadMapList(rescan) {
    try {
      if (!window.B3DMap) return;
      const r = await fetch(MAP_URL + "index.json", { cache: "no-store" }); if (!r.ok) return;
      const j = await r.json(); mapList = (j.maps || []).filter((m) => m && m.id);
    } catch (e) { return; }
    refreshButtons();
    if (rescan) return;
    let want = null, auto = false;
    try {
      const q = new URLSearchParams(location.search); want = q.get("map");
      if (!want) {       // a fight that started in a 3D scene (?scene=island / forest / dungeon) uses that scene's own arena, if one lists it in `scenes`
        const sc = q.get("scene"), sm = sc && mapList.find((m) => Array.isArray(m.scenes) && m.scenes.includes(sc));
        if (sm) { want = sm.id; auto = true; }
      }
      if (!want) want = localStorage.getItem("battleMap");
    } catch (e) {}
    if (want && want !== "painted") B3D.setMap(want, auto);
  }
  B3D.mapInfo = () => ({ id: mapId, ready: !!curMap, list: mapList });

  /* graphics settings from the hub's Esc menu (localStorage "rpgSettings"): render resolution, shadows, brightness, particle density */
  const G = { res: 1, shadows: true, bright: 1, fx: 1 };
  function gfxApply(s) {
    if (!s) return;
    const num = (v, lo, hi, d) => (typeof v === "number" && isFinite(v) ? Math.max(lo, Math.min(hi, v)) : d);
    G.res = num(s.res, 0.4, 2, 1); G.bright = num(s.bright, 0.5, 1.5, 1); G.fx = num(s.fx, 0, 1, 1); G.shadows = s.shadows !== false;
    if (canvas) { canvas.style.filter = G.bright === 1 ? "" : "brightness(" + G.bright + ")"; if (gl) resize(); }
    if (window.EnvFX && EnvFX.setDensity) EnvFX.setDensity(G.fx);
  }
  const gfxReload = () => { try { gfxApply(JSON.parse(localStorage.getItem("rpgSettings") || "null")); } catch (e) {} };
  gfxReload(); window.addEventListener("storage", (ev) => { if (ev.key === "rpgSettings") gfxReload(); });

  function resize() {
    if (!canvas) return;
    const dpr = Math.max(0.35, Math.min(window.devicePixelRatio || 1, 2) * G.res);
    cam.w = window.innerWidth; cam.h = window.innerHeight;
    canvas.width = Math.round(cam.w * dpr); canvas.height = Math.round(cam.h * dpr);
    cam.aspect = cam.w / cam.h;
    gl.viewport(0, 0, canvas.width, canvas.height);
  }

  /* ---------- per-sprite geometry (mirrors SpriteView.tick's sizing so 3D matches 2D proportions) ---------- */
  function geom(s) { return { wx: s.x / PX, wz: s.y / PX, H: C.SPRITE_H * s.hScale }; }   // H in virtual px

  function quadFor(s, img) {
    const frameW = img.naturalWidth / COLS, frameH = img.naturalHeight / ROWS;
    const H = C.SPRITE_H * s.hScale;
    const bossCfg = s.poseCfg && s.poseCfg[s.pose];
    const heroCfg = C.NAMED_POSE_CFG[s.name] && C.NAMED_POSE_CFG[s.name][s.pose];
    const ref = (bossCfg && bossCfg.ref_h) ? bossCfg : (heroCfg && heroCfg.ref_h ? heroCfg : null);
    if (ref) {
      // Calibrated pose: scale from the character's own measured height and pin by its feet. (The 2D hero
      // branch crops the padding away; in 3D the padding is simply transparent, so no crop is needed.)
      const k = H / ref.ref_h;
      return { w: frameW * k, h: frameH * k, ax: ref.foot[0] / frameW, ay: 1 - ref.foot[1] / frameH, frameW, frameH };
    }
    return { w: H * (frameW / frameH), h: H, ax: 0.5, ay: 0, frameW, frameH };
  }

  /* scene.sky: "painted" (default) | [r,g,b] | {type:"color"|"gradient"|"image",...} -- see hub3d.js */
  const skyCache = new Map();
  const hexRGB = (s) => { s = String(s || "#000").replace("#", ""); if (s.length === 3) s = s.replace(/./g, "$&$&"); return [0, 2, 4].map((i) => (parseInt(s.substr(i, 2), 16) || 0) / 255); };
  function skyFor(sky) {
    if (Array.isArray(sky)) return { kind: "color", clear: sky.slice(0, 3) };
    if (!sky || typeof sky !== "object") return null;                               // "painted"
    const key = JSON.stringify(sky); if (skyCache.has(key)) return skyCache.get(key);
    let info = null;
    if (sky.type === "color") info = { kind: "color", clear: (sky.color || [0.1, 0.08, 0.2]).slice(0, 3) };
    else if (sky.type === "gradient" && Array.isArray(sky.stops) && sky.stops.length) {
      const st = sky.stops.map((s) => [Math.max(0, Math.min(1, +s[0] || 0)), s[1]]).sort((a, b) => a[0] - b[0]);
      info = { kind: "gradient", clear: hexRGB(st[st.length - 1][1]), tex: canvasTex(4, 256, (g, w, h) => { const r = g.createLinearGradient(0, 0, 0, h); st.forEach(([p, c]) => r.addColorStop(p, c)); g.fillStyle = r; g.fillRect(0, 0, w, h); }) };
    } else if (sky.type === "layers" && Array.isArray(sky.layers)) {
      const base = sky.base ? skyFor(sky.base) : null; info = { kind: "layers", clear: base ? base.clear : [0.03, 0.02, 0.06], base, layers: [], pending: 0 };
      for (const d of sky.layers.slice(0, 12)) { if (!d || !d.url) continue; info.pending++; const im = new Image(); im.onload = () => { info.layers.push({ def: d, tex: makeTexture(im), aspect: im.naturalWidth / im.naturalHeight, order: sky.layers.indexOf(d) }); info.layers.sort((x, y) => x.order - y.order); info.pending--; }; im.onerror = () => { info.pending--; }; im.src = encodeURI(d.url); }
    } else if (sky.type === "image" && sky.url) {
      info = { kind: "loading", clear: [0.05, 0.04, 0.1] }; const im = new Image();
      im.onload = () => { skyCache.set(key, { kind: "image", clear: [0.05, 0.04, 0.1], tex: makeTexture(im), aspect: im.naturalWidth / im.naturalHeight }); };
      im.onerror = () => { skyCache.set(key, null); }; im.src = encodeURI(sky.url);
    }
    skyCache.set(key, info); return info;
  }
  function drawCustomSky(sk) {
    if (sk.kind === "layers") { const bs = sk.base && sk.base.kind !== "loading" ? sk.base : null; if (bs) drawCustomSky(bs); else if (!sk.base) drawBackdrop(); drawSkyLayers(sk); return; }
    if (!sk.tex) return;
    const dist = 70, vh = 2 * dist * Math.tan(cam.fov * Math.PI / 360), vw = vh * cam.aspect, center = V.add(cam.pos, V.mul(cam.fwd, dist));
    let w, h; if (sk.kind === "image") { w = Math.max(vw * 1.16, vh * 1.16 * sk.aspect); h = w / sk.aspect; } else { w = vw * 1.2; h = vh * 1.5; }
    const rx = Math.max(0, (w - vw) / 2 * 0.9), ry = Math.max(0, (h - vh) / 2 * 0.9);
    const par = clamp(-cam.yaw * 0.018 * (vw / 20), -rx, rx), lift = clamp(-cam.pitch * 0.012 * vh, -ry, ry);
    BLEND_NORMAL();
    drawQuad({ tex: sk.tex, origin: V.add(V.add(center, V.mul(cam.camX, par)), V.mul(cam.camY, lift)), right: cam.camX, up: cam.camY, w, h, ax: 0.5, ay: 0.5 });
  }
  function drawSkyLayers(sk) {
    const dist = 70, vh = 2 * dist * Math.tan(cam.fov * Math.PI / 360), vw = vh * cam.aspect, center = V.add(cam.pos, V.mul(cam.fwd, dist)), t = performance.now() / 1000;
    BLEND_NORMAL();
    for (const L of sk.layers) {
      const d = L.def, par = d.parallax == null ? 0.3 : +d.parallax, hh = (d.height == null ? 0.35 : +d.height) * vh, ww = hh * L.aspect, yc = d.y == null ? 0.35 : +d.y;
      const shift = (-cam.yaw * 0.0009 * par + (d.drift || 0) * t) * vw, lift = clamp(-cam.pitch * 0.012 * vh * (0.4 + par), -vh * 0.2, vh * 0.2);
      const pulse = d.pulse ? 1 - d.pulse * (0.5 + 0.5 * Math.sin(t * 6.2832 / (d.period || 6))) : 1, a = (d.alpha == null ? 1 : +d.alpha) * pulse, tn = d.tint || [1, 1, 1];
      const o = V.add(center, V.mul(cam.camY, vh * (0.5 - yc) + lift));
      const tile = d.tile !== false, base = tile ? ((shift % ww) + ww) % ww : shift, k0 = Math.floor((-vw * 0.62 - base) / ww), n = tile ? Math.ceil(vw * 1.24 / ww) + 2 : 1;
      for (let i = 0; i < n; i++) drawQuad({ tex: L.tex, origin: V.add(o, V.mul(cam.camX, tile ? base + (k0 + i) * ww : base)), right: cam.camX, up: cam.camY, w: ww, h: hh, ax: 0.5, ay: 0.5, tint: [tn[0], tn[1], tn[2], a] });
    }
  }
  function drawBackdrop() {
    const dist = 70, vh = 2 * dist * Math.tan(cam.fov * Math.PI / 360), vw = vh * cam.aspect;
    const scale = Math.max(vw * 1.14, vh * 1.14);
    const center = V.add(cam.pos, V.mul(cam.fwd, dist));
    const par = -cam.yaw * 0.018 * (vw / 20), lift = -cam.pitch * 0.012 * vh;
    const o = V.add(V.add(center, V.mul(cam.camX, par)), V.mul(cam.camY, -0.06 * scale + lift));
    BLEND_NORMAL();
    drawQuad({ tex: bgTex || TEX.white, origin: o, right: cam.camX, up: cam.camY, w: scale, h: scale, ax: 0.5, ay: 0.5, tint: bgTex ? [0.95, 0.95, 1, 1] : [0.12, 0.08, 0.22, 1] });
  }

  function drawFloor(sprites, now, hasMap) {
    BLEND_NORMAL();
    if (!hasMap) drawQuad({ tex: TEX.disc, origin: [0, 0, 0], right: [1, 0, 0], up: [0, 0, -1], w: 24, h: 24, ax: 0.5, ay: 0.5, tint: [1, 1, 1, 1] });
    // targeting / status rings on the floor
    const pulse = 0.75 + 0.25 * Math.sin(now / 1000 * 6);
    BLEND_ADD();
    for (const s of sprites) {
      const cl = s.anchor.classList, g = geom(s), r = g.H / PX * 0.62;
      if (cl.contains("targetable")) {
        const hot = cl.contains("hl") || s.anchor.matches(":hover");
        drawQuad({ tex: TEX.ring, origin: [g.wx, 0.04, g.wz], right: [1, 0, 0], up: [0, 0, -1], w: r * 1.5, h: r * 1.5, ax: 0.5, ay: 0.5, tint: hot ? [1, 0.45, 0.35, 1] : [0.9, 0.8, 0.4, pulse * 0.8] });
      }
      if (cl.contains("marked")) drawQuad({ tex: TEX.ring, origin: [g.wx, 0.05, g.wz], right: [1, 0, 0], up: [0, 0, -1], w: r * 1.2, h: r * 1.2, ax: 0.5, ay: 0.5, tint: [1, 0.2, 0.2, pulse * 0.9] });
      if (cl.contains("bulwark")) drawQuad({ tex: TEX.ring, origin: [g.wx, 0.05, g.wz], right: [1, 0, 0], up: [0, 0, -1], w: r * 1.3, h: r * 1.3, ax: 0.5, ay: 0.5, tint: [0.4, 0.7, 1, pulse * 0.8] });
    }
  }

  let fx = null, fxFor = undefined;
  function syncFx() {
    if (!window.EnvFX) return;
    if (!fx) { fx = EnvFX.create(stageEl, canvas); if (EnvFX.setDensity) EnvFX.setDensity(G.fx); }
    if (fxFor !== curMap) { fxFor = curMap; fx.set(curMap ? curMap.def.fx : null); }
    fx.setVisible(B3D.on);
  }
  function render(now) {
    syncFx();
    const sprites = [...C.sprites.values()];
    let sk = curMap ? skyFor(curMap.def.sky) : null;                 // null = the painted backdrop
    if (sk && sk.kind === "loading") sk = { kind: "color", clear: sk.clear };
    const ck = sk ? sk.clear : [0.03, 0.02, 0.06];
    gl.depthMask(true);
    gl.clearColor(ck[0], ck[1], ck[2], 1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    useSprite();
    gl.uniformMatrix4fv(U.u_vp, false, cam.vp);
    gl.disable(gl.DEPTH_TEST);
    if (!sk) drawBackdrop(); else drawCustomSky(sk);
    const hasMap = drawMap();
    gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL); gl.depthMask(false);      // sprites/decals are occluded by the map but never write depth
    drawFloor(sprites, now, hasMap);

    // blob shadows
    BLEND_NORMAL();
    if (G.shadows) for (const s of sprites) {
      const g = geom(s), hw = g.H / PX, ko = s.anchor.classList.contains("ko");
      drawQuad({ tex: TEX.shadow, origin: [g.wx, 0.02, g.wz], right: [1, 0, 0], up: [0, 0, -1], w: hw * 0.85, h: hw * 0.42, ax: 0.5, ay: 0.5, tint: [1, 1, 1, ko ? 0.5 : 1] });
    }

    // sprites, farthest first
    const info = sprites.map((s) => {
      const g = geom(s);
      return { s, g, depth: V.dot(V.sub([g.wx, 0, g.wz], cam.pos), cam.fwd) };
    }).sort((a, b) => b.depth - a.depth);

    BLEND_NORMAL();
    for (const it of info) {
      const s = it.s, g = it.g;
      const img = s.sheets[s.pose], tex = texFor(img);
      if (!tex) continue;
      let q = null, rect, epsx = 0.5 / img.naturalWidth, epsy = 0.5 / img.naturalHeight;
      if (s.staticCfg) {
        // Single still image (see SpriteView.tick): draw only its visible bounds, feet on the ground.
        const bb = C.staticBounds(img), kk = (C.SPRITE_H * s.hScale) / bb.h, iw = img.naturalWidth, ih = img.naturalHeight;
        q = { w: bb.w * kk, h: bb.h * kk, ax: 0.5, ay: 0 };
        rect = [bb.x / iw, bb.y / ih, bb.w / iw, bb.h / ih];
      } else {
        q = quadFor(s, img);
        rect = [(s.frame % COLS) / COLS, Math.floor(s.frame / COLS) / ROWS, 1 / COLS, 1 / ROWS];
      }
      const hcf = C.NAMED_POSE_CFG[s.name] && C.NAMED_POSE_CFG[s.name][s.pose];
      const flipOpt = !!((s.staticCfg || s.bossCfg) && (s.staticCfg || s.bossCfg).native_left) || !!(hcf && hcf.native_left);
      const flipped = (s.facingRight === flipOpt);        // same rule as the 2D mirror: sheets are drawn facing right
      const cl = s.anchor.classList;
      let tint = [1, 1, 1, 1];
      if (cl.contains("ko")) tint = [0.5, 0.5, 0.55, 0.5];
      else if (cl.contains("enraged")) { const e = 0.8 + 0.2 * Math.sin(now / 1000 * 7); tint = [1, e, e, 1]; }
      if ((cl.contains("hl") || (cl.contains("targetable") && s.anchor.matches(":hover"))) && !cl.contains("ko")) tint = [tint[0] * 1.25, tint[1] * 1.2, tint[2] * 1.0, tint[3]];
      drawQuad({
        tex, origin: [g.wx, 0, g.wz], right: cam.right, up: [0, 1, 0],
        w: q.w / PX, h: q.h / PX, ax: flipped ? 1 - q.ax : q.ax, ay: q.ay, flip: flipped,
        rect, epsx, epsy, tint,
      });
    }
    return info;
  }

  /* Move every sprite's DOM anchor (hit box, nameplate, status icons) onto its projected screen position. */
  function syncDom(info) {
    info.forEach((it, rank) => {
      const s = it.s, g = it.g;
      const a = project([g.wx, 0, g.wz]), b = project([g.wx, g.H / PX, g.wz]);
      const hs = Math.max(8, a.y - b.y);
      const img = s.sheets[s.pose];
      const aspect = img && img.naturalWidth ? (img.naturalWidth / COLS) / (img.naturalHeight / ROWS) : 0.8;
      const hw = hs * Math.min(aspect, 1) * 0.6;
      s.anchor.style.left = `${a.x}px`;
      s.anchor.style.top = `${a.y}px`;
      s.anchor.style.zIndex = String(340 + rank);
      const fe = s.frameEl;
      fe.style.backgroundImage = "none";
      fe.style.width = `${hw}px`; fe.style.height = `${hs}px`;
      fe.style.transform = "translate(-50%, -100%)";
      s.nameplate.style.top = `${-hs - 30}px`;
    });
  }

  /* Action camera: whoever is currently away from their home slot (a melee run-in) pulls the camera in. */
  function updateActionFocus() {
    let push = 0, fx = 0, fz = 0;
    for (const s of C.sprites.values()) {
      const d = Math.hypot(s.x - s.homeX, s.y - s.homeY);
      if (d > 12) { const p = Math.min(1, d / 160) * 0.8; if (p > push) { push = p; fx = s.x / PX * 0.5; fz = s.y / PX * 0.5; } }
    }
    cam.focus.push = push; cam.focus.x = fx; cam.focus.z = fz;
  }

  /* ---------- public API ---------- */
  B3D.frame = function (now) {
    if (!B3D.on || !B3D.ready) return;
    const dt = Math.min(0.05, Math.max(0.001, (now - (lastT || now - 16)) / 1000)); lastT = now;
    updateActionFocus();
    updateCamera(dt);
    const info = render(now);
    syncDom(info);
  };

  // dev helper: world (x, z) on the ground plane under a screen point
  B3D.groundAt = function (sx, sy) {
    const m = cam.vp; if (!m) return null;
    const nx = sx / cam.w * 2 - 1, ny = 1 - sy / cam.h * 2;
    // invert by sampling: solve ground point whose projection matches (Newton on 2 vars)
    let x = 0, z = 0;
    for (let i = 0; i < 40; i++) {
      const p = project([x, 0, z]), e = 0.01;
      const px = project([x + e, 0, z]), pz = project([x, 0, z + e]);
      const dx = sx - p.x, dy = sy - p.y;
      const a = (px.x - p.x) / e, b = (pz.x - p.x) / e, c = (px.y - p.y) / e, d = (pz.y - p.y) / e;
      const det = a * d - b * c; if (Math.abs(det) < 1e-9) break;
      x += (dx * d - b * dy) / det; z += (a * dy - c * dx) / det;
    }
    return { x, z };
  };

  B3D.screenPt = function (s, frac) {
    const g = geom(s);
    const p = project([g.wx, (frac === undefined ? 0.5 : frac) * g.H / PX, g.wz]);
    return { x: p.x, y: p.y };
  };
  // Screen pixels per virtual pixel at this sprite's depth -- used to size DOM effects like 3D objects.
  B3D.persp = function (s) {
    const g = geom(s), a = project([g.wx, 0, g.wz]), b = project([g.wx, g.H / PX, g.wz]);
    return Math.max(0.2, (a.y - b.y) / g.H);
  };

  // Formation layout in virtual px: same grid as the 2D columnLayout (depth runs along x, the two slots of a row
  // spread along y), but centred on the arena and independent of the window size.
  B3D.layout = function (combatants, facingRight) {
    const inset = facingRight ? 1 : -1, side = facingRight ? -1 : 1;
    const byRow = { front: [], middle: [], rear: [] };
    combatants.forEach((c) => {
      const row = Object.prototype.hasOwnProperty.call(byRow, c.formation) ? c.formation : "middle";
      byRow[row].push(c);
    });
    // 3D formation: keep the front/middle/rear depth along x, but give EVERY fighter on a side its own
    // depth lane (z) so they form a diagonal line toward the camera and nobody stands directly behind
    // anybody else (the 2D grid stacks two fighters per row, which hides one behind the other in 3D).
    // Enemy side: a spread-out diagonal (front row first). Hero side: its own diagonal, running from the
    // nearest lane (front, close to the camera, near the arena centre) out to the far-right lane.
    const ordered = [];
    ["front", "middle", "rear"].forEach((row) => byRow[row].forEach((c) => ordered.push(c)));
    const n = ordered.length, GAP = 185, DX = 150;
    const slots = new Map();
    ordered.forEach((c, k) => {
      let x, y;
      if (facingRight) {                                   // enemies (left side of the screen)
        x = side * (MID + (k - (n - 1) / 2) * DX - 10);
        y = (k - (n - 1) / 2) * GAP;
      } else {                                             // heroes: 4 fixed lanes, centred when fewer than 4
        const t = (k + (4 - n) / 2) / 3;
        x = (0.87 + 4.42 * t) * PX + 130;
        y = (7.24 - 9.74 * t) * PX + 55;
      }
      slots.set(c, { x, y, z: Math.round(y) });
    });
    return combatants.map((c) => slots.get(c));
  };

  B3D.setOn = function (on) {
    if (!B3D.ready) return;
    on = !!on && !B3D.failed;
    B3D.on = on; lastT = 0; if (fx) fx.setVisible(on);
    canvas.style.display = on ? "block" : "none";
    vignette.style.display = on ? "block" : "none";
    stageEl.classList.toggle("b3d", on);
    try { localStorage.setItem("battleView", on ? "3d" : "2d"); } catch (e) {}
    if (!on) {
      for (const s of C.sprites.values()) {
        s.nameplate.style.top = `${-C.SPRITE_H * s.hScale - 30}px`;
        s.frameEl.style.transform = ""; s.frameEl.style.backgroundImage = "";
      }
    }
    C.relayout();
    refreshButtons();
  };

  /* ---------- controls ---------- */
  let btnView, btnCam, btnAct, btnMap;
  function refreshButtons() {
    if (!btnView) return;
    btnView.textContent = B3D.on ? "View: 3D" : "View: 2D";
    btnCam.style.display = btnAct.style.display = B3D.on ? "" : "none";
    btnMap.style.display = B3D.on && mapList.length ? "" : "none";
    const mi = mapList.find((m) => m.id === mapId);
    btnMap.textContent = mapErr ? ("Map failed: " + mapErr.msg.slice(0, 60)) : ("Map: " + (mi ? (mi.name || mi.id) : "Painted"));
    btnMap.title = mapErr ? ("Could not load " + mapErr.id + ". If this says HTTP 404, restart the game server so it serves Assets/3D.") : "";
    btnCam.textContent = "Cam: " + presetName;
    btnAct.textContent = "Action cam: " + (B3D.actionCam ? "on" : "off");
    btnAct.classList.toggle("on", B3D.actionCam);
  }
  function buildUi() {
    const st = document.createElement("style");
    st.textContent = `
      #b3d-canvas { position:absolute; inset:0; width:100%; height:100%; display:none; z-index:0; }
      #b3d-vignette { position:absolute; inset:0; pointer-events:none; display:none; z-index:0;
        background: radial-gradient(ellipse at 50% 55%, rgba(0,0,0,0) 55%, rgba(4,2,12,.5) 100%); }
      body:not(.dbgmode) #b3d-bar { display:none !important; }      /* View / Cam / Map / Action cam buttons are debug-only */
      #b3d-bar { position:absolute; top:6px; left:calc(50% - 150px); transform:translateX(-100%); z-index:21; display:flex; gap:6px; }
      #b3d-bar button { background: var(--panel-bg, rgba(14,12,26,.8)); color: var(--text-dim, #9a93c0);
        border:1px solid var(--panel-border, rgba(190,160,255,.35)); border-radius:999px; padding:4px 12px; font-size:12px; cursor:pointer; white-space:nowrap; }
      #b3d-bar button:hover { color:#fff; }
      #b3d-bar button.on { background: var(--accent, #6d4cff); color:#fff; }
      .b3d .sprite-anchor { transition:none !important; }
      .b3d .sprite-frame { filter:none !important; animation:none !important; }`;
    document.head.appendChild(st);
    const bar = document.createElement("div"); bar.id = "b3d-bar";
    const mk = (fn) => { const b = document.createElement("button"); b.type = "button"; b.addEventListener("click", (e) => { fn(); b.blur(); e.stopPropagation(); }); bar.appendChild(b); return b; };
    btnView = mk(() => B3D.setOn(!B3D.on));
    btnCam = mk(() => setPreset(PRESET_NAMES[(PRESET_NAMES.indexOf(presetName) + 1) % PRESET_NAMES.length]));
    btnMap = mk(async () => { await loadMapList(true); const ids = ["painted"].concat(mapList.map((m) => m.id)); B3D.setMap(ids[(ids.indexOf(mapId) + 1) % ids.length]); });
    btnAct = mk(() => { B3D.actionCam = !B3D.actionCam; try { localStorage.setItem("battleAction", B3D.actionCam ? "1" : "0"); } catch (e) {} refreshButtons(); });
    stageEl.appendChild(bar);
  }
  function bindInput() {
    canvas.addEventListener("pointerdown", (e) => { drag = { x: e.clientX, y: e.clientY, moved: false, yaw: cam.g.yaw, pitch: cam.g.pitch }; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener("pointermove", (e) => {
      if (!drag) return;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 5) drag.moved = true;
      if (drag.moved) { cam.g.yaw = clamp(drag.yaw - dx * 0.25, -70, 70); cam.g.pitch = clamp(drag.pitch + dy * 0.18, 2, 60); canvas.style.cursor = "grabbing"; }
    });
    canvas.addEventListener("pointerup", () => { drag = null; canvas.style.cursor = ""; });
    canvas.addEventListener("wheel", (e) => { e.preventDefault(); cam.g.dist = clamp(cam.g.dist * (1 + Math.sign(e.deltaY) * 0.08), 14, 50); }, { passive: false });
    window.addEventListener("resize", resize);
  }

  /* ---------- init (called once by index.html, right before connect()) ---------- */
  B3D.init = function (ctx) {
    C = ctx;
    stageEl = document.getElementById("stage");
    try {
      canvas = document.createElement("canvas"); canvas.id = "b3d-canvas";
      gl = canvas.getContext("webgl", { antialias: true, alpha: false, premultipliedAlpha: false });
      if (!gl) throw new Error("WebGL unavailable");
      prog = gl.createProgram();
      gl.attachShader(prog, mkShader(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, mkShader(gl.FRAGMENT_SHADER, FS));
      gl.bindAttribLocation(prog, 0, "a");
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
      gl.useProgram(prog);
      ["u_vp", "u_o", "u_r", "u_u", "u_size", "u_anchor", "u_tex", "u_rect", "u_eps", "u_flip", "u_tint"].forEach((n) => { U[n] = gl.getUniformLocation(prog, n); });
      quadBuf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]), gl.STATIC_DRAW);
      const aLoc = gl.getAttribLocation(prog, "a"); gl.enableVertexAttribArray(aLoc); gl.vertexAttribPointer(aLoc, 2, gl.FLOAT, false, 0, 0);
      gl.disable(gl.DEPTH_TEST); gl.enable(gl.BLEND); gl.clearDepth(1);
      gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
      gl.activeTexture(gl.TEXTURE0); gl.uniform1i(U.u_tex, 0);
      maxTex = Math.min(8192, gl.getParameter(gl.MAX_TEXTURE_SIZE) || 4096);
      buildTextures();
      initMeshProgram(); useSprite();
    } catch (err) {
      console.warn("[B3D] 3D view unavailable, staying in 2D:", err);
      B3D.failed = true; B3D.ready = false; B3D.on = false;
      return;
    }
    stageEl.insertBefore(canvas, stageEl.firstChild);
    if (!window.EnvFX) { const s = document.createElement("script"); s.src = "/hub3d/envfx.js"; document.head.appendChild(s); }
    vignette = document.createElement("div"); vignette.id = "b3d-vignette";
    stageEl.insertBefore(vignette, canvas.nextSibling);
    B3D.ready = true;
    buildUi(); bindInput(); resize();

    let saved = null, savedCam = null, savedAct = null;
    try { saved = localStorage.getItem("battleView"); savedCam = localStorage.getItem("battleCam2"); savedAct = localStorage.getItem("battleAction"); } catch (e) {}
    const q = new URLSearchParams(location.search).get("view");
    if (savedAct !== null) B3D.actionCam = savedAct !== "0";
    setPreset(savedCam && PRESETS[savedCam] ? savedCam : "Over shoulder");
    Object.assign(cam, PRESETS[presetName]); cam.tz = 0;
    updateCamera(0.016);                                   // so screenPt() works before the first frame
    const want = (q === "2d" || q === "3d") ? q : (saved || "3d");
    B3D.setOn(want !== "2d");
    // load the backdrop painting in the background; until it arrives the scene shows a flat purple
    const bg = new Image();
    bg.onload = () => { bgTex = makeTexture(bg); };
    bg.src = "/assets/Artwork/Background.webp";
    loadMapList();
  };
})();

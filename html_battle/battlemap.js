/* battlemap.js -- GLB (binary glTF 2.0) parser for the 3D battle arena maps.

   Pure data, no WebGL: parse(arrayBuffer) -> { objects, images, bounds }.
     objects[]  one per mesh primitive, node transforms already baked into model space (glTF is Y-up, metres):
                { name, positions:Float32Array, normals:Float32Array, uvs:Float32Array, colors:Float32Array (rgba),
                  indices:Uint32Array, material:{ color:[r,g,b,a], image:int|-1, emissive:[r,g,b], alphaMode, cutoff,
                  doubleSided, unlit }, min:[x,y,z], max:[x,y,z] }
     images[]   { bytes:Uint8Array, mime } for embedded images, or { uri } for external ones.
   Supported: triangle meshes, node hierarchies (matrix or TRS), baseColor factor/texture, COLOR_0, emissive,
   alphaMode, doubleSided, KHR_materials_unlit, KHR_materials_emissive_strength.
   Not supported (throws a readable error): Draco / meshopt compression, sparse accessors. Skins and animation are ignored.
   Also loadable from node (module.exports) so it can be unit-tested. */
(function (root) {
  "use strict";

  const COMP = { 5120: [1, Int8Array, 127], 5121: [1, Uint8Array, 255], 5122: [2, Int16Array, 32767], 5123: [2, Uint16Array, 65535], 5125: [4, Uint32Array, 0], 5126: [4, Float32Array, 0] };
  const NCOMP = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT2: 4, MAT3: 9, MAT4: 16 };

  function mat4Identity() { return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]; }
  function mat4Mul(a, b) {                                   // column-major: a * b
    const o = new Array(16);
    for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++)
      o[c * 4 + r] = a[r] * b[c * 4] + a[4 + r] * b[c * 4 + 1] + a[8 + r] * b[c * 4 + 2] + a[12 + r] * b[c * 4 + 3];
    return o;
  }
  function mat4TRS(t, q, s) {
    const [x, y, z, w] = q, x2 = x + x, y2 = y + y, z2 = z + z;
    const xx = x * x2, xy = x * y2, xz = x * z2, yy = y * y2, yz = y * z2, zz = z * z2, wx = w * x2, wy = w * y2, wz = w * z2;
    return [
      (1 - (yy + zz)) * s[0], (xy + wz) * s[0], (xz - wy) * s[0], 0,
      (xy - wz) * s[1], (1 - (xx + zz)) * s[1], (yz + wx) * s[1], 0,
      (xz + wy) * s[2], (yz - wx) * s[2], (1 - (xx + yy)) * s[2], 0,
      t[0], t[1], t[2], 1];
  }
  // inverse-transpose of the upper 3x3 (for normals)
  function normalMat(m) {
    const a = m[0], b = m[1], c = m[2], d = m[4], e = m[5], f = m[6], g = m[8], h = m[9], i = m[10];
    const A = e * i - f * h, B = -(d * i - f * g), Cc = d * h - e * g;
    const det = a * A + b * B + c * Cc || 1, id = 1 / det;
    return [
      A * id, B * id, Cc * id,
      -(b * i - c * h) * id, (a * i - c * g) * id, -(a * h - b * g) * id,
      (b * f - c * e) * id, -(a * f - c * d) * id, (a * e - b * d) * id];
  }

  function parse(buf) {
    const dv = new DataView(buf);
    if (dv.byteLength < 20 || dv.getUint32(0, true) !== 0x46546c67) throw new Error("Not a GLB file (bad magic). Export as .glb (binary glTF).");
    if (dv.getUint32(4, true) !== 2) throw new Error("Only glTF 2.0 is supported.");
    let off = 12, json = null, bin = null;
    while (off + 8 <= dv.byteLength) {
      const len = dv.getUint32(off, true), type = dv.getUint32(off + 4, true);
      const start = off + 8;
      if (type === 0x4e4f534a) json = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, start, len)));
      else if (type === 0x004e4942 && !bin) bin = new Uint8Array(buf, start, len);
      off = start + len;         // chunk lengths are already 4-aligned in valid files
    }
    if (!json) throw new Error("GLB has no JSON chunk.");
    const req = json.extensionsRequired || [];
    for (const r of req) {
      if (r === "KHR_draco_mesh_compression" || r === "EXT_meshopt_compression" || r === "KHR_mesh_quantization")
        throw new Error(`GLB uses ${r}; re-export without compression.`);
    }

    function viewBytes(viewIdx) {
      const v = json.bufferViews[viewIdx];
      if (v.buffer !== 0 || !bin) throw new Error("Only GLBs with a single embedded buffer are supported.");
      return { bytes: bin, off: v.byteOffset || 0, len: v.byteLength, stride: v.byteStride || 0 };
    }
    // Read an accessor into a typed array (floats for attributes, Uint32 for indices).
    function readAccessor(idx, asFloat) {
      const a = json.accessors[idx];
      if (a.sparse) throw new Error("Sparse accessors are not supported.");
      const [csz, Arr, normDiv] = COMP[a.componentType];
      const n = NCOMP[a.type], count = a.count;
      const out = asFloat ? new Float32Array(count * n) : new Uint32Array(count * n);
      if (a.bufferView === undefined) return out;                       // all zeros
      const v = viewBytes(a.bufferView);
      const base = v.bytes.byteOffset + v.off + (a.byteOffset || 0);
      const stride = v.stride || csz * n;
      const dvb = new DataView(v.bytes.buffer);
      const get = a.componentType === 5126 ? (o) => dvb.getFloat32(o, true)
        : a.componentType === 5125 ? (o) => dvb.getUint32(o, true)
        : a.componentType === 5123 ? (o) => dvb.getUint16(o, true)
        : a.componentType === 5122 ? (o) => dvb.getInt16(o, true)
        : a.componentType === 5121 ? (o) => dvb.getUint8(o)
        : (o) => dvb.getInt8(o);
      const norm = asFloat && a.normalized && normDiv > 0;
      for (let i = 0; i < count; i++)
        for (let k = 0; k < n; k++) {
          let val = get(base + i * stride + k * csz);
          if (norm) val = Math.max(val / normDiv, -1);
          out[i * n + k] = val;
        }
      return out;
    }

    // images
    const images = (json.images || []).map((im) => {
      if (im.bufferView !== undefined) {
        const v = viewBytes(im.bufferView);
        return { bytes: new Uint8Array(v.bytes.buffer, v.bytes.byteOffset + v.off, v.len), mime: im.mimeType || "image/png" };
      }
      if (im.uri && im.uri.startsWith("data:")) {
        const m = /^data:([^;,]+)(;base64)?,(.*)$/.exec(im.uri);
        const raw = m[2] ? atob(m[3]) : decodeURIComponent(m[3]);
        const bytes = new Uint8Array(raw.length); for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
        return { bytes, mime: m[1] };
      }
      return { uri: im.uri };
    });

    function material(idx) {
      const m = idx === undefined ? {} : (json.materials[idx] || {});
      const pbr = m.pbrMetallicRoughness || {};
      const tex = pbr.baseColorTexture;
      let image = -1;
      if (tex && json.textures && json.textures[tex.index]) { const s = json.textures[tex.index].source; if (s !== undefined) image = s; }
      const ext = m.extensions || {};
      const es = ext.KHR_materials_emissive_strength ? ext.KHR_materials_emissive_strength.emissiveStrength : 1;
      return {
        color: pbr.baseColorFactor || [1, 1, 1, 1], image,
        emissive: (m.emissiveFactor || [0, 0, 0]).map((c) => c * es),
        alphaMode: m.alphaMode || "OPAQUE", cutoff: m.alphaCutoff === undefined ? 0.5 : m.alphaCutoff,
        doubleSided: !!m.doubleSided, unlit: !!ext.KHR_materials_unlit,
      };
    }

    const objects = [];
    const bmin = [Infinity, Infinity, Infinity], bmax = [-Infinity, -Infinity, -Infinity];

    function addMesh(meshIdx, world, nodeName) {
      const mesh = json.meshes[meshIdx], nm = normalMat(world);
      mesh.primitives.forEach((prim, pi) => {
        if ((prim.mode === undefined ? 4 : prim.mode) !== 4) return;      // triangles only
        if (prim.attributes.POSITION === undefined) return;
        const pos = readAccessor(prim.attributes.POSITION, true), vc = pos.length / 3;
        let nrm = prim.attributes.NORMAL !== undefined ? readAccessor(prim.attributes.NORMAL, true) : null;
        const uv = prim.attributes.TEXCOORD_0 !== undefined ? readAccessor(prim.attributes.TEXCOORD_0, true) : new Float32Array(vc * 2);
        let col = null;
        if (prim.attributes.COLOR_0 !== undefined) {
          const ca = json.accessors[prim.attributes.COLOR_0], raw = readAccessor(prim.attributes.COLOR_0, true);
          col = new Float32Array(vc * 4);
          const n = NCOMP[ca.type];
          for (let i = 0; i < vc; i++) { col[i * 4] = raw[i * n]; col[i * 4 + 1] = raw[i * n + 1]; col[i * 4 + 2] = raw[i * n + 2]; col[i * 4 + 3] = n === 4 ? raw[i * n + 3] : 1; }
        } else { col = new Float32Array(vc * 4).fill(1); }
        let idx;
        if (prim.indices !== undefined) idx = readAccessor(prim.indices, false);
        else { idx = new Uint32Array(vc); for (let i = 0; i < vc; i++) idx[i] = i; }
        if (!nrm) {                                                         // flat-ish fallback: accumulate face normals
          nrm = new Float32Array(vc * 3);
          for (let t = 0; t + 2 < idx.length; t += 3) {
            const a = idx[t] * 3, b = idx[t + 1] * 3, c = idx[t + 2] * 3;
            const ux = pos[b] - pos[a], uy = pos[b + 1] - pos[a + 1], uz = pos[b + 2] - pos[a + 2];
            const vx = pos[c] - pos[a], vy = pos[c + 1] - pos[a + 1], vz = pos[c + 2] - pos[a + 2];
            const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
            for (const o of [a, b, c]) { nrm[o] += nx; nrm[o + 1] += ny; nrm[o + 2] += nz; }
          }
        }
        // bake the node transform into the vertices
        const P = new Float32Array(vc * 3), N = new Float32Array(vc * 3);
        const mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity];
        for (let i = 0; i < vc; i++) {
          const x = pos[i * 3], y = pos[i * 3 + 1], z = pos[i * 3 + 2];
          const px = world[0] * x + world[4] * y + world[8] * z + world[12];
          const py = world[1] * x + world[5] * y + world[9] * z + world[13];
          const pz = world[2] * x + world[6] * y + world[10] * z + world[14];
          P[i * 3] = px; P[i * 3 + 1] = py; P[i * 3 + 2] = pz;
          const nx = nrm[i * 3], ny = nrm[i * 3 + 1], nz = nrm[i * 3 + 2];
          let qx = nm[0] * nx + nm[3] * ny + nm[6] * nz, qy = nm[1] * nx + nm[4] * ny + nm[7] * nz, qz = nm[2] * nx + nm[5] * ny + nm[8] * nz;
          const l = Math.hypot(qx, qy, qz) || 1; N[i * 3] = qx / l; N[i * 3 + 1] = qy / l; N[i * 3 + 2] = qz / l;
          if (px < mn[0]) mn[0] = px; if (py < mn[1]) mn[1] = py; if (pz < mn[2]) mn[2] = pz;
          if (px > mx[0]) mx[0] = px; if (py > mx[1]) mx[1] = py; if (pz > mx[2]) mx[2] = pz;
        }
        // a negative-determinant transform flips winding
        const det = world[0] * (world[5] * world[10] - world[6] * world[9]) - world[4] * (world[1] * world[10] - world[2] * world[9]) + world[8] * (world[1] * world[6] - world[2] * world[5]);
        if (det < 0) for (let t = 0; t + 2 < idx.length; t += 3) { const tmp = idx[t + 1]; idx[t + 1] = idx[t + 2]; idx[t + 2] = tmp; }
        for (let k = 0; k < 3; k++) { bmin[k] = Math.min(bmin[k], mn[k]); bmax[k] = Math.max(bmax[k], mx[k]); }
        objects.push({ name: (nodeName || mesh.name || "mesh") + (mesh.primitives.length > 1 ? "." + pi : ""), positions: P, normals: N, uvs: uv, colors: col, indices: idx, material: material(prim.material), min: mn, max: mx });
      });
    }

    function walk(ni, parent) {
      const n = json.nodes[ni];
      const local = n.matrix ? n.matrix.slice() : mat4TRS(n.translation || [0, 0, 0], n.rotation || [0, 0, 0, 1], n.scale || [1, 1, 1]);
      const world = mat4Mul(parent, local);
      if (n.mesh !== undefined) addMesh(n.mesh, world, n.name);
      (n.children || []).forEach((c) => walk(c, world));
    }
    const scene = (json.scenes && json.scenes[json.scene || 0]);
    const roots = scene && scene.nodes ? scene.nodes : (json.nodes || []).map((_, i) => i);
    roots.forEach((r) => walk(r, mat4Identity()));
    if (!objects.length) throw new Error("GLB contains no triangle meshes.");
    return { objects, images, bounds: { min: bmin, max: bmax } };
  }

  const api = { parse, mat4Mul, mat4TRS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.B3DMap = api;
})(typeof window !== "undefined" ? window : globalThis);

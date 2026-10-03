"""Tiny GLB writer + procedural texture helpers shared by gen_island_meshes.py and gen_dungeon_meshes.py (numpy + Pillow only).
Single mesh, single material per file. Textured meshes need TEXCOORD_0 + an encoded image (the 3D builder ignores vertex colours)."""
import io, json, struct
import numpy as np
from PIL import Image

def encode(arr, fmt='JPEG', q=86):
    im = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)); b = io.BytesIO()
    im.save(b, fmt, **({'quality': q} if fmt == 'JPEG' else {})); return b.getvalue(), ('image/jpeg' if fmt == 'JPEG' else 'image/png')

def write_glb(path, pos, nrm, idx, name, uv=None, img=None, mime='image/jpeg', col=None, color=(1, 1, 1, 1), emissive=None,
              alpha='OPAQUE', cutoff=0.5, unlit=False, double=False, repeat=True, extra_pos=None):
    pos = np.asarray(pos, np.float32); nrm = np.asarray(nrm, np.float32); idx = np.asarray(idx, np.uint32).ravel()
    if extra_pos is not None:       # unreferenced vertices that only widen the bounding box (keeps big meshes from fading, see hub3d.js)
        pos = np.concatenate([pos, np.asarray(extra_pos, np.float32)]); nrm = np.concatenate([nrm, np.tile([0, 1, 0], (len(extra_pos), 1)).astype(np.float32)])
        if uv is not None: uv = np.concatenate([uv, np.zeros((len(extra_pos), 2), np.float32)])
    out = bytearray(); bvs = []; accs = []
    def add(arr, target, **kw):
        data = arr.tobytes()
        while len(out) % 4: out.append(0)
        bvs.append(dict(buffer=0, byteOffset=len(out), byteLength=len(data), target=target)); out.extend(data)
        accs.append(dict(bufferView=len(bvs) - 1, **kw)); return len(accs) - 1
    attrs = {}
    attrs['POSITION'] = add(pos, 34962, componentType=5126, count=len(pos), type='VEC3', min=pos.min(0).tolist(), max=pos.max(0).tolist())
    attrs['NORMAL'] = add(nrm, 34962, componentType=5126, count=len(nrm), type='VEC3')
    if uv is not None: attrs['TEXCOORD_0'] = add(np.asarray(uv, np.float32), 34962, componentType=5126, count=len(uv), type='VEC2')
    if col is not None: attrs['COLOR_0'] = add(np.asarray(col, np.float32), 34962, componentType=5126, count=len(col), type='VEC4')
    img_bv = None
    if img is not None:
        while len(out) % 4: out.append(0)
        bvs.append(dict(buffer=0, byteOffset=len(out), byteLength=len(img))); out.extend(img); img_bv = len(bvs) - 1
    ii = add(idx.astype('<u4'), 34963, componentType=5125, count=idx.size, type='SCALAR')
    pbr = dict(baseColorFactor=list(color), metallicFactor=0, roughnessFactor=1)
    if img is not None: pbr['baseColorTexture'] = {'index': 0}
    mat = dict(name=name, pbrMetallicRoughness=pbr, alphaMode=alpha, doubleSided=double)
    if alpha == 'MASK': mat['alphaCutoff'] = cutoff
    if emissive: mat['emissiveFactor'] = list(emissive)
    g = dict(asset=dict(version='2.0', generator='island-dungeon-gen'), scene=0, scenes=[dict(nodes=[0])], nodes=[dict(name=name, mesh=0)],
             meshes=[dict(name=name, primitives=[dict(attributes=attrs, indices=ii, material=0, mode=4)])], materials=[mat],
             accessors=accs, bufferViews=bvs, buffers=[dict(byteLength=len(out))])
    if unlit: g['extensionsUsed'] = ['KHR_materials_unlit']; mat['extensions'] = {'KHR_materials_unlit': {}}
    if img is not None:
        w = 10497 if repeat else 33071
        g['images'] = [dict(bufferView=img_bv, mimeType=mime)]; g['textures'] = [dict(source=0, sampler=0)]
        g['samplers'] = [dict(magFilter=9729, minFilter=9987, wrapS=w, wrapT=w)]
    js = json.dumps(g, separators=(',', ':')).encode()
    while len(js) % 4: js += b' '
    open(path, 'wb').write(struct.pack('<III', 0x46546C67, 2, 28 + len(js) + len(out)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(out), 0x004E4942) + bytes(out))

def normals(pos, idx):
    pos = np.asarray(pos, np.float64); idx = np.asarray(idx).reshape(-1, 3); n = np.zeros_like(pos)
    fn = np.cross(pos[idx[:, 1]] - pos[idx[:, 0]], pos[idx[:, 2]] - pos[idx[:, 0]])
    for k in range(3): np.add.at(n, idx[:, k], fn)
    l = np.linalg.norm(n, axis=1, keepdims=True); l[l == 0] = 1; return (n / l).astype(np.float32)

def fnoise(n, beta=1.5, seed=0):
    """Seamlessly tiling 1/f^beta noise in 0..1 (FFT filtered white noise)."""
    r = np.random.default_rng(seed); w = r.normal(size=(n, n)); f = np.fft.fftfreq(n); fx, fy = np.meshgrid(f, f); fr = np.hypot(fx, fy); fr[0, 0] = 1
    a = np.real(np.fft.ifft2(np.fft.fft2(w) / fr ** (beta / 2 + 0.5))); a -= a.min(); return a / a.max()

def vnoise3(p, seed, freq):
    """3D value noise for displacement, p: (N,3) -> (N,) in 0..1."""
    r = np.random.default_rng(seed); G = r.random((17, 17, 17)); q = np.asarray(p, np.float64) * freq; q = q % 16
    i = q.astype(int); f = q - i; f = f * f * (3 - 2 * f); out = 0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out = out + w * G[(i[:, 0] + dx) % 17, (i[:, 1] + dy) % 17, (i[:, 2] + dz) % 17]
    return out

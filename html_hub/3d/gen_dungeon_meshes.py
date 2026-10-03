"""Procedural dungeon kit -> Assets/3D/Dungeon/ (SM_dg_*.glb): wall cube, flagstone floor, portcullis gate, pillar, brazier + flame, crystal,
water, tablet, sarcophagus, dais, throne.  Textured with generated seamless stone (the 3D builder ignores vertex colours).   Run: python gen_dungeon_meshes.py [outdir]"""
import os, sys
import numpy as np
from glbkit import write_glb, encode, normals, fnoise
OUT = sys.argv[1] if len(sys.argv) > 1 else '.'; os.makedirs(OUT, exist_ok=True)

def brick(n=512, rows=4, cols=4, seed=1, base=(0.42, 0.42, 0.46), moss=True):
    r = np.random.default_rng(seed); g = fnoise(n, 1.6, seed); g2 = fnoise(n, 2.4, seed + 3); im = np.zeros((n, n, 3), np.float32)
    bh = n // rows; bw = n // cols
    for j in range(rows):
        off = (bw // 2) if j % 2 else 0
        for i in range(cols + 1):
            x0 = (i * bw - off); tint = 0.78 + 0.4 * r.random(); warm = 1 + 0.06 * (r.random() - .5)
            for xs in (x0, x0 - n):                      # wrap so the texture tiles
                a, b = max(xs, 0), min(xs + bw, n)
                if b > a: im[j * bh:(j + 1) * bh, a:b] = np.array(base) * tint * np.array([warm, 1, 2 - warm])
    v = 0.75 + 0.5 * g + 0.2 * (g2 - 0.5); im *= v[..., None]
    for j in range(rows): im[j * bh:j * bh + 4] *= 0.35                       # mortar, horizontal
    for j in range(rows):
        off = (bw // 2) if j % 2 else 0
        for i in range(cols + 1):
            x = (i * bw - off) % n; im[j * bh:(j + 1) * bh, x:x + 4] *= 0.35
    if moss: m = np.clip((fnoise(n, 1.2, seed + 9) - 0.62) * 4, 0, 1)[..., None]; im = im * (1 - m * .55) + m * np.array([0.12, 0.22, 0.10]) * .8
    return np.clip(im, 0, 1)

def flags(n=512, seed=2):
    im = brick(n, 2, 2, seed, (0.36, 0.36, 0.40), False); r = np.random.default_rng(seed)
    im *= 0.9; edge = 6
    for k in (0, n // 2): im[k:k + edge] *= 0.45; im[:, k:k + edge] *= 0.45
    return np.clip(im, 0, 1)

def box(w, h, d, tile=4.0, y0=0.0, tx=None):
    """axis-aligned box, base at y0, centred on x/z; UVs repeat every `tile` metres."""
    hx, hz = w / 2, d / 2; y1 = y0 + h; P = []; N = []; U = []; I = []
    faces = [((hx, y0, hz), (hx, y0, -hz), (hx, y1, -hz), (hx, y1, hz), (1, 0, 0), d, h), ((-hx, y0, -hz), (-hx, y0, hz), (-hx, y1, hz), (-hx, y1, -hz), (-1, 0, 0), d, h),
             ((-hx, y0, hz), (hx, y0, hz), (hx, y1, hz), (-hx, y1, hz), (0, 0, 1), w, h), ((hx, y0, -hz), (-hx, y0, -hz), (-hx, y1, -hz), (hx, y1, -hz), (0, 0, -1), w, h),
             ((-hx, y1, hz), (hx, y1, hz), (hx, y1, -hz), (-hx, y1, -hz), (0, 1, 0), w, d), ((-hx, y0, -hz), (hx, y0, -hz), (hx, y0, hz), (-hx, y0, hz), (0, -1, 0), w, d)]
    pos = []; nrm = []; uv = []; idx = []
    for a, b, c, e, nn, uw, uh in faces:
        o = len(pos); pos += [a, b, c, e]; nrm += [nn] * 4; uv += [(0, 0), (uw / tile, 0), (uw / tile, uh / tile), (0, uh / tile)]; idx += [(o, o + 1, o + 2), (o, o + 2, o + 3)]
    return np.array(pos, np.float32), np.array(nrm, np.float32), np.array(uv, np.float32), np.array(idx, np.uint32)

def merge(meshes):
    P, N, U, I, o = [], [], [], [], 0
    for p, n, u, i in meshes: P.append(p); N.append(n); U.append(u); I.append(i + o); o += len(p)
    return np.concatenate(P), np.concatenate(N), np.concatenate(U), np.concatenate(I)

def shift(m, dx=0, dy=0, dz=0): p, n, u, i = m; return p + np.array([dx, dy, dz], np.float32), n, u, i

BR = encode(brick(512, 4, 4, 1))[0]; BR2 = encode(brick(512, 4, 4, 5, (0.34, 0.35, 0.40)))[0]; FL = encode(flags())[0]
def save(name, m, img, **kw): write_glb(os.path.join(OUT, name + '.glb'), m[0], m[1], m[3], name, uv=m[2], img=img, **kw)

save('SM_dg_wall', box(4.0, 4.2, 4.0, 4.0), BR)                                        # one full 4 x 4 m wall cell
save('SM_dg_pillar', box(1.2, 4.2, 1.2, 2.0), BR2)
save('SM_dg_block', box(1.0, 1.0, 1.0, 2.0), BR2)
# floor cell: unit plane at y=0.02, 2 x 2 flagstones; place with scale 4
hw = .5; save('SM_dg_floor', (np.array([[-hw, .02, -hw], [hw, .02, -hw], [hw, .02, hw], [-hw, .02, hw]], np.float32), np.tile([0, 1, 0], (4, 1)).astype(np.float32),
                              np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32), np.array([(0, 3, 1), (1, 3, 2)], np.uint32)), FL)
# water: translucent plane, scale to size
def water_tex():
    n = 256; a = fnoise(n, 1.8, 4); b = fnoise(n, 2.6, 6); v = 0.55 + 0.5 * a + 0.2 * b
    im = np.stack([0.08 * v, 0.30 * v, 0.46 * v], -1); return np.clip(im, 0, 1)
save('SM_dg_water', (np.array([[-hw, .08, -hw], [hw, .08, -hw], [hw, .08, hw], [-hw, .08, hw]], np.float32), np.tile([0, 1, 0], (4, 1)).astype(np.float32),
                     np.array([[0, 0], [2, 0], [2, 2], [0, 2]], np.float32), np.array([(0, 3, 1), (1, 3, 2)], np.uint32)), encode(water_tex())[0], color=(1, 1, 1, 0.72), alpha='BLEND', double=True)
# portcullis gate (alpha-cut bars), 4 wide x 3.9 tall, double sided
def bars():
    n = 256; im = np.zeros((n, n, 4), np.float32)
    for k in range(6): x = int((k + 0.5) * n / 6); im[:, x - 7:x + 7] = (0.20, 0.19, 0.20, 1)
    for y in (24, 124, 224): im[y - 8:y + 8, :] = (0.22, 0.21, 0.22, 1)
    im[:, :, :3] *= (0.8 + 0.3 * fnoise(n, 1.5, 3))[..., None]; return im
gp = np.array([[-2, 0, 0], [2, 0, 0], [2, 3.9, 0], [-2, 3.9, 0]], np.float32)
from PIL import Image
import io
def png_rgba(arr):
    b = io.BytesIO(); Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), 'RGBA').save(b, 'PNG'); return b.getvalue()
write_glb(os.path.join(OUT, 'SM_dg_gate.glb'), gp, np.tile([0, 0, 1], (4, 1)), [(0, 1, 2), (0, 2, 3)], 'SM_dg_gate', uv=np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32),
          img=png_rgba(bars()), mime='image/png', alpha='MASK', cutoff=0.5, double=True, repeat=False)
# brazier: a stone stand and bowl; flame is a separate unlit piece
stand = merge([box(0.9, 0.25, 0.9, 1.0), shift(box(0.4, 0.9, 0.4, 1.0), 0, 0.25, 0), shift(box(1.1, 0.35, 1.1, 1.0), 0, 1.15, 0)])
save('SM_dg_brazier', stand, BR2)
fp = np.array([(0, 0.9, 0), (0.45, 0, 0), (0, 0, 0.45), (-0.45, 0, 0), (0, 0, -0.45), (0, 1.0, 0)], np.float32)   # octahedron-ish flame
fi = np.array([(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1)], np.uint32); fp = np.array([(0, 1.0, 0), (0.45, 0, 0), (0, 0, 0.45), (-0.45, 0, 0), (0, 0, -0.45)], np.float32)
write_glb(os.path.join(OUT, 'SM_dg_flame.glb'), fp, normals(fp, fi) , fi, 'SM_dg_flame', color=(1.0, 0.55, 0.15, 1), emissive=(1.0, 0.5, 0.1), unlit=True, double=True)
# crystal cluster (cyan, emissive)
cp = []; ci = []
for k, (ox, oz, s, lean) in enumerate(((0, 0, 1.0, 0), (0.5, 0.2, 0.65, .2), (-0.45, 0.25, 0.75, -.2), (0.1, -0.5, 0.55, .1))):
    o = len(cp); h = 1.8 * s; w = 0.28 * s
    cp += [(ox + lean * h, h, oz), (ox + w, 0, oz), (ox, 0, oz + w), (ox - w, 0, oz), (ox, 0, oz - w)]; ci += [(o, o + 1, o + 2), (o, o + 2, o + 3), (o, o + 3, o + 4), (o, o + 4, o + 1)]
cp = np.array(cp, np.float32); ci = np.array(ci, np.uint32)
write_glb(os.path.join(OUT, 'SM_dg_crystal.glb'), cp, normals(cp, ci), ci, 'SM_dg_crystal', color=(0.35, 0.8, 1.0, 1), emissive=(0.2, 0.6, 0.9), double=True)
# lore tablet and sarcophagus
save('SM_dg_tablet', merge([box(1.5, 2.0, 0.3, 1.5), shift(box(2.0, 0.3, 0.7, 1.5), 0, 0, 0)]), BR2)
save('SM_dg_sarcophagus', merge([box(1.5, 0.8, 3.0, 2.0), shift(box(1.3, 0.3, 2.8, 2.0), 0, 0.8, 0)]), BR2)
# dais and throne for the boss hall (placed at the hall's north end, facing +z)
dais = merge([box(14, 0.5, 8, 4.0), shift(box(10, 0.5, 5.5, 4.0), 0, 0.5, -0.4), shift(box(6, 0.5, 3.2, 4.0), 0, 1.0, -0.8)])
save('SM_dg_dais', dais, BR)
throne = merge([box(2.4, 1.0, 2.0, 2.0), shift(box(2.4, 3.6, 0.5, 2.0), 0, 0, -1.0), shift(box(0.5, 2.0, 1.8, 2.0), -1.2, 0, 0), shift(box(0.5, 2.0, 1.8, 2.0), 1.2, 0, 0)])
save('SM_dg_throne', throne, BR2)
print('ok', sorted(os.listdir(OUT)))

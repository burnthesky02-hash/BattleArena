"""Generates SM_dw_step.glb: one stone stair tread (4 m wide, 1 m deep, top at y=0, a 1.2 m skirt below so a row of them on a slope reads as a flight of steps).
Run: python gen_steps.py [outdir]   (needs glbkit.py, numpy, Pillow)"""
import os, sys
import numpy as np
from glbkit import write_glb, encode, fnoise
class Mesh:
    def __init__(s, sc=3.0):
        s.P, s.N, s.UV, s.I = [], [], [], []; s.sc = sc

    def uvf(s, q, n):
        a = np.abs(n)
        if a[1] >= a[0] and a[1] >= a[2]: return (q[0] / s.sc, q[2] / s.sc)
        if a[0] >= a[2]: return (q[2] / s.sc, q[1] / s.sc)
        return (q[0] / s.sc, q[1] / s.sc)

    def quad(s, p, hint, uvs=None):
        p = np.array(p, float); n = np.cross(p[1] - p[0], p[3] - p[0]); l = np.linalg.norm(n)
        if l < 1e-9: return
        n /= l
        if uvs is not None: uvs = list(uvs)
        if np.dot(n, hint) < 0:
            p = p[::-1]; n = -n
            if uvs is not None: uvs = uvs[::-1]
        b = len(s.P)
        for k, q in enumerate(p):
            s.P.append(q); s.N.append(n); s.UV.append(uvs[k] if uvs is not None else s.uvf(q, n))
        s.I += [b, b + 1, b + 2, b, b + 2, b + 3]

    def box(s, cx, cy, cz, sx, sy, sz):
        x0, x1, y0, y1, z0, z1 = cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, cz - sz / 2, cz + sz / 2
        s.quad([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0)); s.quad([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0))
        s.quad([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)); s.quad([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], (-1, 0, 0))
        s.quad([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)); s.quad([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1))

    def arrays(s):
        return np.array(s.P, np.float32), np.array(s.N, np.float32), np.array(s.I, np.uint32), np.array(s.UV, np.float32)


def stone_tex(seed=4, tint=(0.62, 0.59, 0.54)):
    """seamless masonry: staggered courses of blocks, dark mortar, weathering and a little moss"""
    n = 512; r = np.random.default_rng(seed); im = np.zeros((n, n, 3), np.float32); ch = 32
    for row in range(n // ch):
        x = -r.integers(0, 60); y0 = row * ch
        while x < n:
            bw = int(r.integers(54, 104)); t = 0.78 + 0.34 * r.random()
            col = np.array(tint) * t * (0.96 + 0.08 * r.random(3))
            xa, xb = max(x, 0), min(x + bw, n); im[y0:y0 + ch, xa:xb] = col
            if x >= 0: im[y0:y0 + ch, x:x + 2] = np.array(tint) * 0.32
            x += bw
        im[y0:y0 + 2, :] = np.array(tint) * 0.32
    # wrap-around: blocks that ran off the right edge restart on the left, so patch the seam with the leftmost colour
    im[:, 0:2] = np.array(tint) * 0.32
    wth = fnoise(n, 1.6, seed + 3); w2 = fnoise(n, 2.6, seed + 4)
    im = im * (0.80 + 0.38 * wth[..., None]) * (0.92 + 0.16 * w2[..., None])
    moss = np.clip((fnoise(n, 1.4, seed + 5) - 0.66) * 5, 0, 1)[..., None] * np.array([0.14, 0.26, 0.10])
    return np.clip(im * (1 - moss.sum(-1, keepdims=True) * 0.5) + moss * 0.8, 0, 1)


STONE = encode(stone_tex(seed=7, tint=(0.66, 0.62, 0.56)))[0]
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
M = Mesh(1.6)
M.box(0, -0.6, 0, 4.0, 1.2, 1.0)
p, n, i, uv = M.arrays()
write_glb(os.path.join(OUT, 'SM_dw_step.glb'), p, n, i, 'SM_dw_step', uv=uv, img=STONE, repeat=True)
print('SM_dw_step.glb written')

"""Procedural meshes for the Whispering Wood -> Assets/3D/Paradise/ :  SM_forest_ground (a mossy forest floor with dirt trails, clearings and a pond,
colours baked into a texture) and SM_waterfall (a streaked, unlit sheet of falling water).   Run: python gen_forest_meshes.py [outdir]"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glbkit import write_glb, encode, normals, fnoise, vnoise3
from forestmap import TRAILS, CLEAR, POND, FALL, TRAIL_HW, dist_trails
OUT = sys.argv[1] if len(sys.argv) > 1 else '.'
os.makedirs(OUT, exist_ok=True)

def vn2(X, Z, s, seed):
    p = np.stack([X / s, np.zeros_like(X), Z / s], -1).reshape(-1, 3); return vnoise3(p, seed, 1.0).reshape(X.shape)

def colour(X, Z):
    n1 = vn2(X, Z, 6.0, 5)[..., None]; n2 = vn2(X, Z, 1.3, 9)[..., None]; n3 = vn2(X, Z, 16.0, 12)[..., None]
    moss = np.array([0.20, 0.34, 0.15]); leaf = np.array([0.30, 0.27, 0.13]); dark = np.array([0.11, 0.21, 0.11]); dirt = np.array([0.45, 0.35, 0.22]); wet = np.array([0.30, 0.26, 0.18])
    base = moss * (0.75 + 0.5 * n1) * (0.9 + 0.2 * n2)
    base = base * (1 - 0.5 * (n3 > 0.55)) + dark * 0.5 * (n3 > 0.55)                                           # shady patches
    base = base * (1 - 0.35 * (n2 > 0.62)) + leaf * 0.35 * (n2 > 0.62)                                           # fallen leaves
    d = dist_trails(X, Z); w = np.clip((TRAIL_HW + 0.6 - d) / 1.5, 0, 1)[..., None]
    base = base * (1 - w) + dirt * (0.85 + 0.25 * n2) * w                                                       # trails
    for k, (cx, cz, r) in CLEAR.items():
        c = np.clip((r - 1.2 - np.hypot(X - cx, Z - cz)) / 2.5, 0, 1)[..., None]
        tone = {'camp': wet, 'head': dirt}.get(k, None)
        if tone is not None: base = base * (1 - c * .85) + tone * (0.85 + 0.25 * n2) * c * .85                    # trampled earth in camps
        else: base = base * (1 - c * .45) + (moss * 1.25) * (0.9 + 0.25 * n2) * c * .45                          # brighter grass in the other glades
    pr = np.hypot(X - POND[0], Z - POND[1])
    base = np.where((pr < POND[2] + 0.6)[..., None], np.array([0.16, 0.38, 0.45]) * (0.9 + 0.2 * n2), base)       # the pond
    base = np.where((pr < POND[2] + 1.6)[..., None] & (pr >= POND[2] + 0.6)[..., None], wet, base)                  # its muddy bank
    return base

def grid(n, ext, cx, cz):
    xs = np.linspace(-ext, ext, n + 1) + cx; zs = np.linspace(-ext, ext, n + 1) + cz; X, Z = np.meshgrid(xs, zs)
    pos = np.stack([X, np.zeros_like(X) - 0.0, Z], -1).reshape(-1, 3).astype(np.float32); idx = []
    for r in range(n):
        for c in range(n):
            a = r * (n + 1) + c; b = a + 1; d = a + n + 1; e = d + 1; idx += [(a, d, b), (b, d, e)]
    idx = np.array(idx, np.uint32); nrm = normals(pos, idx); nrm[nrm[:, 1] < 0] *= -1
    uv = np.stack([(pos[:, 0] - cx + ext) / (2 * ext), (pos[:, 2] - cz + ext) / (2 * ext)], -1)
    return pos, nrm, idx, uv

EXT, CX, CZ = 85.0, 0.0, -7.0
xs = np.linspace(-EXT, EXT, 2048) + CX; zs = np.linspace(-EXT, EXT, 2048) + CZ; X, Z = np.meshgrid(xs, zs)
img = encode(np.clip(colour(X, Z), 0, 1), 'JPEG', 82)[0]
p, n, i, uv = grid(8, EXT, CX, CZ)
write_glb(os.path.join(OUT, 'SM_forest_ground.glb'), p, n, i, 'SM_forest_ground', uv=uv, img=img, repeat=False)

# ---- waterfall sheet (3.6 m wide, 9 m tall), vertical streaks of white on blue, unlit
W, H = 3.6, 9.0
yy = np.linspace(0, 1, 256)[:, None]; xx = np.linspace(0, 1, 128)[None, :]
r = np.random.default_rng(4); streak = np.zeros((256, 128))
for k in range(26):
    x0 = r.random(); w = 0.01 + 0.03 * r.random(); sp = 0.5 + r.random()
    streak += np.exp(-((xx - x0) / w) ** 2) * (0.5 + 0.5 * np.sin(yy * (14 + 20 * r.random()) * sp + r.random() * 6))
streak = np.clip(streak * 0.5, 0, 1)
tex = np.zeros((256, 128, 3)); tex[:] = np.array([0.30, 0.62, 0.82]); tex = tex * (1 - streak[..., None]) + np.array([0.92, 0.98, 1.0]) * streak[..., None]
tex[-40:] = tex[-40:] * (1 - np.linspace(0, 1, 40)[:, None, None]) + np.array([0.95, 0.98, 1.0]) * np.linspace(0, 1, 40)[:, None, None]    # foam at the bottom
pos = np.array([[-W / 2, 0, 0], [W / 2, 0, 0], [W / 2, H, 0], [-W / 2, H, 0]], np.float32); nrm = np.tile([0, 0, 1], (4, 1)).astype(np.float32)
write_glb(os.path.join(OUT, 'SM_waterfall.glb'), pos, nrm, [(0, 1, 2), (0, 2, 3)], 'SM_waterfall', uv=np.array([[0, 1], [1, 1], [1, 0], [0, 0]], np.float32),
          img=encode(tex)[0], unlit=True, double=True, repeat=False)
print('ok')

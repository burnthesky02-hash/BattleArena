"""Mesh + texture helpers for gen_colosseum_meshes.py (numpy + Pillow). Flat-shaded quads with explicit normals; winding is fixed from the normal hint."""
import math, numpy as np
from PIL import Image, ImageDraw, ImageFilter
from glbkit import write_glb, encode, fnoise

class Mesh:
    def __init__(self): self.P, self.N, self.UV, self.I = [], [], [], []
    def _v(self, p, n, uv): self.P.append(p); self.N.append(n); self.UV.append(uv); return len(self.P) - 1
    def tri(self, p0, p1, p2, n, uv0=(0, 0), uv1=(0, 0), uv2=(0, 0)):
        p = [np.asarray(q, np.float64) for q in (p0, p1, p2)]; n = np.asarray(n, np.float64); l = np.linalg.norm(n); n = n / l if l else np.array([0, 1, 0.])
        g = np.cross(p[1] - p[0], p[2] - p[0]); a, b, c = (self._v(p[i].tolist(), n.tolist(), uv) for i, uv in enumerate((uv0, uv1, uv2)))
        self.I += [a, b, c] if np.dot(g, n) >= 0 else [a, c, b]
    def quad(self, p0, p1, p2, p3, n, uv0=(0, 0), uv1=(1, 0), uv2=(1, 1), uv3=(0, 1)):
        self.tri(p0, p1, p2, n, uv0, uv1, uv2); self.tri(p0, p2, p3, n, uv0, uv2, uv3)
    def arrays(self): return np.array(self.P, np.float32), np.array(self.N, np.float32), np.array(self.I, np.uint32), np.array(self.UV, np.float32)

def box(m, c, s, uvf, faces="all"):
    """axis-aligned box centre c size s; uvf(p, n) -> uv for a vertex"""
    cx, cy, cz = c; sx, sy, sz = s[0] / 2, s[1] / 2, s[2] / 2
    F = {"+x": ([(1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1)], (1, 0, 0)), "-x": ([(-1, -1, -1), (-1, 1, -1), (-1, 1, 1), (-1, -1, 1)], (-1, 0, 0)),
         "+y": ([(-1, 1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1)], (0, 1, 0)), "-y": ([(-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)], (0, -1, 0)),
         "+z": ([(-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)], (0, 0, 1)), "-z": ([(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1)], (0, 0, -1))}
    for k, (cs, n) in F.items():
        if faces != "all" and k not in faces: continue
        pts = [(cx + a * sx, cy + b * sy, cz + c_ * sz) for a, b, c_ in cs]; m.quad(*pts, n, *[uvf(p, n) for p in pts])

def lathe(m, prof, seg, uvf, cx=0, cy=0, cz=0, closed_top=False):
    """surface of revolution; prof = [(r, y), ...] bottom to top, normals from the profile tangent (outward = to the right of travel)"""
    for i in range(len(prof) - 1):
        (r0, y0), (r1, y1) = prof[i], prof[i + 1]; dr, dy = r1 - r0, y1 - y0; L = math.hypot(dr, dy) or 1; nr, ny = dy / L, -dr / L
        for s in range(seg):
            a0, a1 = 2 * math.pi * s / seg, 2 * math.pi * (s + 1) / seg
            def P(r, y, a): return (cx + r * math.cos(a), cy + y, cz + r * math.sin(a))
            pts = [P(r0, y0, a0), P(r0, y0, a1), P(r1, y1, a1), P(r1, y1, a0)]
            nm = ((nr * math.cos((a0 + a1) / 2)), ny, (nr * math.sin((a0 + a1) / 2)))
            m.quad(*pts, nm, *[uvf(p, nm) for p in pts])

def smooth(m):                                    # average normals of coincident vertices (for round things like the statue)
    P = np.array(m.P); N = np.array(m.N); key = [tuple(np.round(p, 3)) for p in P]; acc = {}
    for k, n in zip(key, N): acc[k] = acc.get(k, 0) + n
    for i, k in enumerate(key): v = acc[k]; l = np.linalg.norm(v); m.N[i] = (v / l).tolist() if l else m.N[i]

def stone_tex(seed=1, size=1024, tile_m=6.0, course=0.5, base=(0.93, 0.89, 0.80), joint=0.80, var=0.05, grain=0.05, warm=0.0):
    """travertine ashlar: courses of `course` m, random block lengths, darker joints, soft weathering; tile_m metres per texture repeat"""
    r = np.random.default_rng(seed); px = size / tile_m; img = np.ones((size, size, 3)) * np.array(base)
    n_c = int(round(tile_m / course)); ch = size / n_c; jw = max(1.5, 0.03 * px)
    lines = np.zeros((size, size))
    for c in range(n_c):
        y0 = int(c * ch); y1 = int((c + 1) * ch); x = -r.random() * 1.6 * px
        while x < size:
            L = (0.9 + r.random() * 1.3) * px; xe = x + L
            sh = 1 + (r.random() - 0.5) * 2 * var; img[y0:y1, max(0, int(x)):min(size, int(xe))] *= sh
            xi = int(x) % size; lines[y0:y1, xi:xi + int(jw)] = 1; x = xe
        lines[y0:y0 + int(jw), :] = 1
    lines = np.array(Image.fromarray((lines * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))) / 255.0
    n1 = fnoise(size, 1.8, seed + 1); n2 = fnoise(size, 0.9, seed + 2)
    img *= (1 - grain + grain * 2 * n2)[..., None] * (0.96 + 0.08 * n1)[..., None]
    img = img * (1 - (1 - joint) * lines[..., None])
    img[..., 2] *= 1 - warm * 0.1
    return np.clip(img, 0, 1)

def marble_tex(seed=3, size=512, base=(0.95, 0.94, 0.92)):
    n1 = fnoise(size, 2.2, seed); n2 = fnoise(size, 1.1, seed + 1); v = np.abs(np.sin((np.arange(size)[None, :] * 0.02 + n1 * 14))) ** 14
    img = np.ones((size, size, 3)) * np.array(base) * (0.96 + 0.06 * n2[..., None]); img *= (1 - 0.10 * v[..., None]); return np.clip(img, 0, 1)

def paving_tex(seed=5, size=1024, tile_m=20.0, sw=4.0, sd=2.5, base=(0.86, 0.84, 0.80)):
    """big pale slabs in running bond; tile_m x tile_m metres, seamless (sw divides tile_m, sd divides tile_m)"""
    r = np.random.default_rng(seed); px = size / tile_m; img = np.ones((size, size, 3)) * np.array(base)
    rows = int(round(tile_m / sd)); cols = int(round(tile_m / sw)); jw = max(2, int(0.05 * px)); lines = np.zeros((size, size))
    for j in range(rows):
        y0, y1 = int(j * sd * px), int((j + 1) * sd * px); off = (sw / 2 if j % 2 else 0) * px
        for i in range(cols + 1):
            x0 = int(i * sw * px - off); x1 = int((i + 1) * sw * px - off); sh = 1 + (r.random() - 0.5) * 0.10; tint = np.array([1 + (r.random() - 0.5) * 0.012, 1, 1 + (r.random() - 0.5) * 0.015])
            for xs in (0, -size, size):
                a, b = max(0, x0 + xs), min(size, x1 + xs)
                if b > a: img[y0:y1, a:b] *= (sh * tint)
            lines[y0:y1, x0 % size:x0 % size + jw] = 1
        lines[y0:y0 + jw, :] = 1
    lines = np.array(Image.fromarray((lines * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.9))) / 255.0
    n1 = fnoise(size, 1.6, seed + 1); n2 = fnoise(size, 0.8, seed + 2)
    img *= (0.94 + 0.12 * n1[..., None]) * (0.97 + 0.06 * n2[..., None]); img = img * (1 - 0.34 * lines[..., None]); return np.clip(img, 0, 1)

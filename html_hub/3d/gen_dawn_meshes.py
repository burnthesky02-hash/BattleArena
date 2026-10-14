"""Procedural pieces Dawnwatch needs that the kits lack -> Assets/3D/Generated/ :
 SM_dw_ground (the valley heightmap, colours baked into a texture), SM_dw_river (animated by the engine's water shader because of its name),
 SM_dw_bridge (3-arch stone bridge, deck top at local y 0, centred on x 0 / z 0, runs along z), SM_dw_portal_frame (stone pointed-arch gate),
 SM_dw_portal_glow (the glowing gate disc) + SM_dw_portal_beam (the light column), SM_dw_banner (navy banner with a silver emblem), SM_dw_clock (a clock face).
Run: python gen_dawn_meshes.py [outdir]     (needs glbkit.py, dawnheight.py, numpy, scipy, Pillow)"""
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw
from glbkit import write_glb, encode, normals, fnoise, vnoise3
import dawnheight as DH

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
os.makedirs(OUT, exist_ok=True)
smooth = DH.smooth


def vn2(X, Z, s, seed):
    return DH.vn2(X, Z, s, seed)


# ------------------------------------------------------------------------------------------------ ground colours
ROAD = DH.ROAD


def dist_to_roads(X, Z):
    best = np.full(X.shape, 1e9)
    for pl in ROAD:
        for (x0, z0), (x1, z1) in zip(pl[:-1], pl[1:]):
            dx, dz = x1 - x0, z1 - z0
            t = np.clip(((X - x0) * dx + (Z - z0) * dz) / (dx * dx + dz * dz), 0, 1)
            best = np.minimum(best, np.hypot(X - (x0 + t * dx), Z - (z0 + t * dz)))
    return best


def cobble(X, Z):
    """staggered cobbles: (X, Z) -> brightness factor with dark mortar joints"""
    row = np.floor(Z / 0.62); u = X / 0.95 + 0.5 * (row % 2); cell = np.floor(u)
    fu = u - cell; fv = Z / 0.62 - row
    hsh = np.abs(np.sin(cell * 12.9898 + row * 78.233) * 43758.5453) % 1.0
    return np.where((fu < 0.10) | (fv < 0.13), 0.62, 0.90 + 0.20 * hsh)[..., None]


_HB = None


def gb(X, Z):
    global _HB
    if _HB is None:
        from scipy.ndimage import gaussian_filter
        _HB = gaussian_filter(DH.hgrid(), 2.2, mode="nearest")
    from scipy.ndimage import map_coordinates
    return map_coordinates(_HB, [(np.asarray(Z) - DH.GZ0) / DH.CELL, (np.asarray(X) - DH.GX0) / DH.CELL], order=1, mode="nearest")


def ground_colour(X, Z):
    h0 = DH.gy_many(X, Z)
    gxs = gb(X + 1.5, Z) - gb(X - 1.5, Z); gzs = gb(X, Z + 1.5) - gb(X, Z - 1.5); sl = np.hypot(gxs, gzs) / 3.0              # slopes from a blurred heightmap (no 1 m cell speckle)
    n1 = vn2(X, Z, 5.0, 5)[..., None]; n2 = vn2(X, Z, 1.4, 9)[..., None]; n3 = vn2(X, Z, 14.0, 12)[..., None]; n4 = vn2(X, Z, 40.0, 14)[..., None]
    grass = np.array([0.36, 0.52, 0.22]); lush = np.array([0.20, 0.38, 0.15]); dry = np.array([0.52, 0.55, 0.28]); path = np.array([0.66, 0.55, 0.38])
    cob = np.array([0.62, 0.59, 0.54]); rock = np.array([0.55, 0.50, 0.43]); mud = np.array([0.40, 0.33, 0.22]); snow = np.array([0.93, 0.95, 0.98]); pine = np.array([0.12, 0.26, 0.13])
    base = grass * (0.80 + 0.40 * n1)
    base = base * (1 - 0.45 * (n3 > 0.58)) + lush * 0.45 * (n3 > 0.58)                                             # darker patches of long grass
    base = base * (1 - 0.35 * np.clip((n4 - 0.55) * 4, 0, 1)) + dry * 0.35 * np.clip((n4 - 0.55) * 4, 0, 1)        # dry meadow
    hi = np.clip((h0 - 14) / 26, 0, 1)[..., None]
    base = base * (1 - hi * 0.55) + pine * (0.8 + 0.4 * n3) * hi * 0.55                                            # conifer-dark foothills
    d = dist_to_roads(X, Z); w = np.clip((1.9 + 0.35 - d) / 1.2, 0, 1)[..., None]                                   # roads: dirt with a cobbled core
    wc = np.clip((1.0 - d) / 0.8, 0, 1)[..., None]
    base = base * (1 - w) + (path * (0.9 + 0.2 * n2) * (1 - wc) + cob * cobble(X, Z) * wc) * w
    # paved squares: the market plaza (rings round the fountain), the keep apron, aprons by the chapel and library, the gate court
    def rr(cx, cz, hx, hz, soft=0.04):
        r = (np.abs(X - cx) / hx) ** 8 + (np.abs(Z - cz) / hz) ** 8
        return np.clip((1.0 - r) / soft, 0, 1)[..., None]
    rf = np.hypot(X - 0, (Z - 30) * 1.0)
    ring = (0.92 + 0.10 * np.sin(rf[..., None] * 3.2)) * (0.94 + 0.12 * n2) * cobble(X, Z)
    for k, (cx, cz, hx, hz) in enumerate(DH.PAVED):
        c = rr(cx, cz, hx, hz)
        base = base * (1 - c) + cob * (ring if k == 0 else cobble(X, Z)) * c
    for cx, cz, rx, rz in ((0, 30, 4.4, 4.4),):                                                                    # fountain basin paving
        r = np.hypot((X - cx) / rx, (Z - cz) / rz); c = np.clip((1.0 - r) / 0.15, 0, 1)[..., None]; base = base * (1 - c) + cob * 0.82 * c
    # the river: mud and stone at the water, a masonry quay where the bank is steep
    rd, rw = DH.river_dist(X, Z); nearr = np.clip((rw + 3.2 - rd) / 3.0, 0, 1)[..., None]
    wet = np.clip((0.55 - h0) / 0.9, 0, 1)[..., None]
    base = base * (1 - nearr * 0.55) + mud * (0.85 + 0.3 * n2) * nearr * 0.55
    base = base * (1 - wet * 0.8) + np.array([0.30, 0.28, 0.24]) * wet * 0.8
    quay = (nearr[..., 0] > 0.1) & (sl > 0.45)
    course = (0.86 + 0.16 * np.sin(h0 * 7.0 + 1.0))[..., None] * (0.92 + 0.14 * n2)
    base = np.where(quay[..., None], np.array([0.60, 0.58, 0.54]) * course, base)
    # the grand stair (treads across the ramp) and the retaining walls of the step between plaza and keep terrace
    lh = DH.RAMP_LH - 4.5 * DH.smooth((np.abs(X) - 12.0) / 12.0)
    inr = ((np.abs(Z - DH.RAMP_Z) < lh + 0.5) & (np.abs(X) < 11.0))
    tread = (0.5 + 0.5 * np.sin(Z * 2 * np.pi / 1.1))[..., None]
    stairc = cob * (0.80 + 0.28 * tread) * (0.94 + 0.12 * n2)
    wallc = np.array([0.58, 0.55, 0.50]) * (0.84 + 0.18 * np.sin(h0[..., None] * 6.5)) * (0.94 + 0.12 * n2)
    ret = ((Z > -14) & (Z < 14) & (np.abs(X) < 52) & (h0 > 3.3) & (h0 < 9.7)) & ~inr
    rs = (np.clip((sl - 0.30) / 0.15, 0, 1) * ret)[..., None]
    base = base * (1 - rs * 0.9) + wallc * rs * 0.9
    sm = (inr * np.clip((np.abs(Z - DH.RAMP_Z) - 0) < 99, 0, 1))[..., None].astype(float)
    base = base * (1 - sm) + stairc * sm
    # steep ground shows rock in strata; ledges and the heights are bare stone with pines on the flatter shelves
    strata = (0.90 + 0.12 * np.sin(h0 * 0.9 + 6.0 * n3[..., 0] + 4.0 * n4[..., 0]))[..., None] * (np.array([1.0, 0.95, 0.88]) * (1 - 0.5 * n4) + np.array([0.9, 0.95, 1.0]) * 0.5 * n4)
    rk = np.clip((sl - 0.8) / 0.6, 0, 1)[..., None] * (h0[..., None] > 4.0)
    base = base * (1 - rk * 0.92) + rock * strata * (0.75 + 0.5 * n1) * rk * 0.92
    alt = np.clip((h0 - 46) / 20, 0, 1)[..., None]
    base = base * (1 - alt * 0.6) + rock * (0.85 + 0.35 * n2) * alt * 0.6
    sn = (np.clip((h0 - 74 + 6 * (n3[..., 0] - 0.5)) / 12, 0, 1) * np.clip(1.25 - sl, 0.25, 1))[..., None]
    base = base * (1 - sn) + snow * (0.92 + 0.1 * n2) * sn
    lit = np.clip(0.90 + 0.55 * (gxs * 0.5 + gzs * 0.45), 0.60, 1.18)[..., None]                                    # baked relief shading (sun from the north-west)
    return np.clip(base * (0.93 + 0.14 * n2) * lit, 0, 1)


def water_colour(X, Z):
    h0 = DH.gy_many(X, Z); depth = np.clip(DH.WATER_Y - h0, 0, 3.0)[..., None]
    n = vn2(X, Z, 3.0, 22)[..., None]
    shallow = np.array([0.34, 0.66, 0.64]); mid = np.array([0.15, 0.46, 0.62]); deep = np.array([0.06, 0.27, 0.50])
    t = np.clip(depth / 1.6, 0, 1); c = shallow * (1 - t) + mid * t
    t2 = np.clip((depth - 1.4) / 1.6, 0, 1); c = c * (1 - t2) + deep * t2
    foam = np.clip((0.22 - depth) / 0.22, 0, 1) * (0.5 + 0.5 * n)
    return np.clip(c * (0.94 + 0.12 * n) + foam * 0.55, 0, 1)


def terrain_mesh():
    xs = DH.GX0 + np.arange(DH.GNX) * DH.CELL; zs = DH.GZ0 + np.arange(DH.GNZ) * DH.CELL; X, Z = np.meshgrid(xs, zs); Y = DH.hgrid()
    pos = np.stack([X, Y, Z], -1).reshape(-1, 3).astype(np.float32); W = DH.GNX; idx = []
    for r in range(DH.GNZ - 1):
        for c in range(W - 1):
            a = r * W + c; b = a + 1; d = a + W; e = d + 1; idx += [(a, d, b), (b, d, e)] if (r + c) % 2 == 0 else [(a, d, e), (a, e, b)]
    idx = np.array(idx, np.uint32); nrm = normals(pos, idx); nrm[nrm[:, 1] < 0] *= -1
    uv = np.stack([(pos[:, 0] - DH.GX0) / ((W - 1) * DH.CELL), (pos[:, 2] - DH.GZ0) / ((DH.GNZ - 1) * DH.CELL)], -1)
    return pos, nrm, idx, uv


def bake_rect(cfn, px_w, px_h, q=84):
    xs = np.linspace(DH.GX0, DH.GX0 + (DH.GNX - 1) * DH.CELL, px_w); zs = np.linspace(DH.GZ0, DH.GZ0 + (DH.GNZ - 1) * DH.CELL, px_h); X, Z = np.meshgrid(xs, zs)
    rows = [cfn(X[i:i + 200], Z[i:i + 200]) for i in range(0, px_h, 200)]                                           # in slabs: the colour maths is memory hungry
    return encode(np.concatenate(rows), 'JPEG', q)[0]


def river_mesh():
    """the water surface: only the quads near the channel (the ground hides the rest), flat at WATER_Y"""
    xs = DH.GX0 + np.arange(DH.GNX) * DH.CELL; zs = DH.GZ0 + np.arange(DH.GNZ) * DH.CELL; X, Z = np.meshgrid(xs, zs)
    d, w = DH.river_dist(X, Z); keep = d < w + 3.2
    W = DH.GNX; idx = []
    for r in range(DH.GNZ - 1):
        for c in range(W - 1):
            if keep[r, c] or keep[r + 1, c] or keep[r, c + 1] or keep[r + 1, c + 1]:
                a = r * W + c; b = a + 1; dd = a + W; e = dd + 1; idx += [(a, dd, b), (b, dd, e)]
    idx = np.array(idx, np.uint32)
    pos = np.stack([X, np.full(X.shape, DH.WATER_Y), Z], -1).reshape(-1, 3).astype(np.float32)
    nrm = np.tile(np.array([0, 1, 0], np.float32), (len(pos), 1))
    uv = np.stack([(pos[:, 0] - DH.GX0) / ((W - 1) * DH.CELL), (pos[:, 2] - DH.GZ0) / ((DH.GNZ - 1) * DH.CELL)], -1)
    return pos, nrm, idx, uv


# ------------------------------------------------------------------------------------------------ small mesh builder (flat shaded)
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


STONE = encode(stone_tex())[0]

# ------------------------------------------------------------------------------------------------ ground + river
print("ground ..."); p, n, i, uv = terrain_mesh()
write_glb(os.path.join(OUT, 'SM_dw_ground.glb'), p, n, i, 'SM_dw_ground', uv=uv, img=bake_rect(ground_colour, 4096, 4352, 80), repeat=False)
print("river ..."); p, n, i, uv = river_mesh()
write_glb(os.path.join(OUT, 'SM_dw_river.glb'), p, n, i, 'SM_dw_river', uv=uv, img=bake_rect(water_colour, 2048, 2176, 86), repeat=False)

# ------------------------------------------------------------------------------------------------ the bridge
BL = 19.5; HW = 3.7; SPRING = -2.2; RY = 1.3; PIER_BOT = -6.6
SEG = [("p", 0.55), ("a", 5.4), ("p", 1.1), ("a", 5.4), ("p", 1.1), ("a", 5.4), ("p", 0.55)]
M = Mesh(3.0)
prof = []                                                                                  # bottom profile (z, y), non-decreasing in z
arches = []
z = -BL / 2
for kind, wd in SEG:
    if kind == "p":
        prof += [(z, SPRING), (z, PIER_BOT), (z + wd, PIER_BOT), (z + wd, SPRING)]
        M.quad([(-HW + 0.2, PIER_BOT, z), (HW - 0.2, PIER_BOT, z), (HW - 0.2, SPRING, z), (-HW + 0.2, SPRING, z)], (0, 0, -1)) if False else None
    else:
        zc = z + wd / 2; arches.append((zc, wd / 2))
        for t in np.linspace(math.pi, 0, 25)[1:-1]: prof.append((zc + (wd / 2) * math.cos(t), SPRING + RY * math.sin(t)))
    z += wd
for sgn in (-1, 1):                                                                        # the two side faces, as a strip between the profile and the deck line
    x = sgn * HW
    for (za, ya), (zb, yb) in zip(prof[:-1], prof[1:]):
        if abs(zb - za) < 1e-6: continue
        M.quad([(x, ya, za), (x, yb, zb), (x, 0.0, zb), (x, 0.0, za)], (sgn, 0, 0))
for zc, rx in arches:                                                                      # arch undersides
    ts = np.linspace(math.pi, 0, 25)
    for t0, t1 in zip(ts[:-1], ts[1:]):
        a0 = (zc + rx * math.cos(t0), SPRING + RY * math.sin(t0)); a1 = (zc + rx * math.cos(t1), SPRING + RY * math.sin(t1))
        M.quad([(-HW, a0[1], a0[0]), (HW, a0[1], a0[0]), (HW, a1[1], a1[0]), (-HW, a1[1], a1[0])], (0, -1, 0))
z = -BL / 2
for kind, wd in SEG:                                                                       # pier faces under the springline
    if kind == "p":
        for zz, hz in ((z, -1), (z + wd, 1)):
            if 1e-6 < abs(zz + BL / 2) < BL - 1e-6: M.quad([(-HW, PIER_BOT, zz), (HW, PIER_BOT, zz), (HW, SPRING, zz), (-HW, SPRING, zz)], (0, 0, hz))
    z += wd
M.quad([(-HW, 0, -BL / 2), (HW, 0, -BL / 2), (HW, 0, BL / 2), (-HW, 0, BL / 2)], (0, 1, 0), uvs=[(-HW / 3, -BL / 6), (HW / 3, -BL / 6), (HW / 3, BL / 6), (-HW / 3, BL / 6)])
for sgn in (-1, 1):                                                                        # parapets with a coping, and a pillar at each end
    M.box(sgn * (HW - 0.3), 0.52, 0, 0.6, 1.04, BL); M.box(sgn * (HW - 0.3), 1.14, 0, 0.84, 0.18, BL)
    for zz in (-BL / 2 + 0.45, BL / 2 - 0.45): M.box(sgn * (HW - 0.3), 0.8, zz, 0.9, 1.6, 0.9); M.box(sgn * (HW - 0.3), 1.7, zz, 1.1, 0.16, 1.1)
    for zc, rx in arches[:2]:                                                              # a stone refuge over each pier between the arches
        pass
p, n, i, uv = M.arrays(); write_glb(os.path.join(OUT, 'SM_dw_bridge.glb'), p, n, i, 'SM_dw_bridge', uv=uv, img=STONE, repeat=True)

# ------------------------------------------------------------------------------------------------ the portal gate: stone frame, glowing disc, light beam
PA_, PHS, NARC = 3.5, 5.9, 20                                                              # half opening, springline, samples per arc


def pointed(a, hs, off=0.0):
    """outline of a pointed (equilateral) arch, base at y 0: left base -> left arc -> apex -> right arc -> right base"""
    R = 2 * a; pts = [(-a - off, 0.0), (-a - off, hs)]
    c = (a, hs)
    for t in np.linspace(math.pi, math.pi - math.pi / 3, NARC)[1:]: pts.append((c[0] + R * math.cos(t), c[1] + R * math.sin(t)))
    c = (-a, hs)
    for t in np.linspace(math.pi / 3, 0, NARC)[1:-1]: pts.append((c[0] + R * math.cos(t), c[1] + R * math.sin(t)))
    pts.append((a + off, hs)); pts.append((a + off, 0.0))
    return pts


def pointed_pair(a, hs, w):
    inner = pointed(a, hs); outer = pointed(a + w, hs + 0.2); return inner, outer


F = Mesh(3.5); D2 = 0.9
inner, outer = pointed_pair(PA_, PHS, 1.5)
for k in range(len(inner) - 1):
    for (zz, hz) in ((D2, 1), (-D2, -1)):                                                  # front / back rings
        F.quad([(inner[k][0], inner[k][1], zz), (outer[k][0], outer[k][1], zz), (outer[k + 1][0], outer[k + 1][1], zz), (inner[k + 1][0], inner[k + 1][1], zz)], (0, 0, hz))
    F.quad([(inner[k][0], inner[k][1], -D2), (inner[k][0], inner[k][1], D2), (inner[k + 1][0], inner[k + 1][1], D2), (inner[k + 1][0], inner[k + 1][1], -D2)],
           (-(inner[k][0] + inner[k + 1][0]) / 2, 2.0 - (inner[k][1] + inner[k + 1][1]) / 2, 0))        # the reveal faces inwards
    F.quad([(outer[k][0], outer[k][1], -D2), (outer[k][0], outer[k][1], D2), (outer[k + 1][0], outer[k + 1][1], D2), (outer[k + 1][0], outer[k + 1][1], -D2)],
           ((outer[k][0] + outer[k + 1][0]) / 2, (outer[k][1] + outer[k + 1][1]) / 2 - 2.0, 0))
for sgn in (-1, 1):                                                                        # buttress piers at the foot, and a plinth
    F.box(sgn * (PA_ + 2.5), 1.2, 0, 1.8, 2.4, 2.6); F.box(sgn * (PA_ + 2.5), 2.6, 0, 2.2, 0.4, 3.0)
F.box(0, -0.1, 0, 2 * PA_ + 7.0, 0.5, 3.4)
p, n, i, uv = F.arrays(); write_glb(os.path.join(OUT, 'SM_dw_portal_frame.glb'), p, n, i, 'SM_dw_portal_frame', uv=uv, img=STONE, repeat=True)


def swirl_tex(sz=512):
    y, x = np.mgrid[0:sz, 0:sz] / (sz - 1.0); cx, cy = x - 0.5, y - 0.5; r = np.hypot(cx, cy * 0.6) * 2; a = np.arctan2(cy, cx)
    sw = 0.5 + 0.5 * np.sin(a * 3 + r * 14 + 2.0 * fnoise(sz, 1.8, 7)); sw2 = 0.5 + 0.5 * np.sin(a * 5 - r * 9 + 6 * fnoise(sz, 2.2, 8))
    core = np.clip(1 - r * 1.05, 0, 1) ** 1.6
    c0 = np.array([0.22, 0.45, 1.0]); c1 = np.array([0.55, 0.82, 1.0]); c2 = np.array([0.72, 0.55, 1.0])
    col = c0 * (0.6 + 0.4 * sw[..., None]) + c1 * core[..., None] * 0.9 + c2 * (sw2 * (1 - core))[..., None] * 0.35
    a_ = np.clip(0.38 + 0.5 * sw * (1 - r * 0.4) + core * 0.4, 0, 1) * np.clip((1.0 - r) * 5, 0, 1)
    return np.concatenate([np.clip(col, 0, 1) * a_[..., None], a_[..., None]], -1)


SW, _ = encode(swirl_tex(), 'PNG')
G = Mesh(1.0)
ring = pointed(PA_ - 0.02, PHS)
# fan from the centre of the opening, UVs spanning the opening's bounding box
cy = 5.8; ctr = (0.0, cy); P0 = [(ctr[0], ctr[1])] + ring; uvs = [(0.5 + (px / (2 * PA_ + 0.1)), 0.5 - (py - cy) / (PHS + 6.2)) for px, py in P0]
pos = np.array([(px, py, 0.0) for px, py in P0], np.float32); nrm = np.tile([0, 0, 1.0], (len(pos), 1)).astype(np.float32)
idx = []
for k in range(1, len(P0) - 1): idx += [0, k, k + 1]
write_glb(os.path.join(OUT, 'SM_dw_portal_glow.glb'), pos, nrm, idx, 'SM_dw_portal_glow', uv=np.array(uvs, np.float32), img=SW, mime='image/png', alpha='BLEND', unlit=True, double=True, repeat=False)


def beam_tex(h=512, w=64):
    y, x = np.mgrid[0:h, 0:w]; u = np.abs(x / (w - 1.0) - 0.5) * 2; v = y / (h - 1.0)
    a = np.clip(1 - u, 0, 1) ** 2.2 * np.clip(1 - v, 0, 1) ** 1.4 * 0.9
    col = np.stack([0.55 + 0 * a, 0.78 + 0 * a, np.ones_like(a)], -1)
    return np.concatenate([col * a[..., None], a[..., None]], -1)


BM, _ = encode(beam_tex(), 'PNG')
H_B, W_B = 70.0, 3.4
quads = []; uv = []; ix = []
for rot in (0, math.pi / 2):                                                               # two crossed planes
    c, s = math.cos(rot), math.sin(rot)
    base = len(quads)
    for (lx, ly, u, v) in ((-W_B / 2, 0, 0, 1), (W_B / 2, 0, 1, 1), (W_B / 2, H_B, 1, 0), (-W_B / 2, H_B, 0, 0)):
        quads.append((lx * c, ly, lx * s)); uv.append((u, v))
    ix += [base, base + 1, base + 2, base, base + 2, base + 3]
write_glb(os.path.join(OUT, 'SM_dw_portal_beam.glb'), np.array(quads, np.float32), np.tile([0, 0, 1.0], (len(quads), 1)).astype(np.float32), ix, 'SM_dw_portal_beam',
          uv=np.array(uv, np.float32), img=BM, mime='image/png', alpha='BLEND', unlit=True, double=True, repeat=False)

# ------------------------------------------------------------------------------------------------ banner + clock face
def banner_tex(W=192, H=512):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W - 1, 27], fill=(92, 62, 38, 255)); d.rectangle([0, 0, W - 1, 6], fill=(124, 86, 52, 255))               # the carrying bar
    cloth = [(24, 28), (W - 24, 28), (W - 24, H - 8), (W // 2, H - 86), (24, H - 8)]
    d.polygon(cloth, fill=(22, 34, 82, 255))
    d.line([(30, 34), (W - 30, 34), (W - 30, H - 24), (W // 2, H - 98), (30, H - 24), (30, 34)], fill=(190, 200, 222, 255), width=3)       # silver border
    cx, cy = W // 2, 190
    d.ellipse([cx - 52, cy - 52, cx + 52, cy + 52], outline=(210, 220, 240, 255), width=4)
    for k in range(8):                                                                                                               # compass star
        a = k * math.pi / 4; r = 66 if k % 2 == 0 else 38
        d.polygon([(cx + 10 * math.cos(a + 1.57), cy + 10 * math.sin(a + 1.57)), (cx + r * math.cos(a), cy + r * math.sin(a)), (cx + 10 * math.cos(a - 1.57), cy + 10 * math.sin(a - 1.57))], fill=(200, 212, 236, 255))
    d.rectangle([cx - 4, cy - 100, cx + 4, cy + 120], fill=(226, 232, 246, 255)); d.polygon([(cx - 8, cy - 100), (cx + 8, cy - 100), (cx, cy - 124)], fill=(226, 232, 246, 255))   # the sword
    d.rectangle([cx - 24, cy + 70, cx + 24, cy + 78], fill=(226, 232, 246, 255))
    return np.asarray(im, np.float32) / 255.0


BN, _ = encode(banner_tex(), 'PNG')
BW, BH = 1.5, 4.0
pos = np.array([(-BW / 2, 0, 0), (BW / 2, 0, 0), (BW / 2, BH, 0), (-BW / 2, BH, 0)], np.float32)
write_glb(os.path.join(OUT, 'SM_dw_banner.glb'), pos, np.tile([0, 0, 1.0], (4, 1)).astype(np.float32), [0, 1, 2, 0, 2, 3], 'SM_dw_banner',
          uv=np.array([(0, 1), (1, 1), (1, 0), (0, 0)], np.float32), img=BN, mime='image/png', alpha='MASK', cutoff=0.5, double=True, repeat=False)


def clock_tex(S_=256):
    im = Image.new('RGB', (S_, S_), (60, 44, 30)); d = ImageDraw.Draw(im); c = S_ // 2
    d.ellipse([4, 4, S_ - 4, S_ - 4], fill=(176, 140, 70)); d.ellipse([16, 16, S_ - 16, S_ - 16], fill=(238, 230, 208))
    for k in range(12):
        a = k * math.pi / 6; r0, r1 = (c - 34, c - 20) if k % 3 else (c - 40, c - 20)
        d.line([(c + r0 * math.sin(a), c - r0 * math.cos(a)), (c + r1 * math.sin(a), c - r1 * math.cos(a))], fill=(40, 34, 30), width=5 if k % 3 == 0 else 3)
    d.line([(c, c), (c + 56 * math.sin(math.radians(305)), c - 56 * math.cos(math.radians(305)))], fill=(30, 26, 24), width=9)           # hour
    d.line([(c, c), (c + 84 * math.sin(math.radians(60)), c - 84 * math.cos(math.radians(60)))], fill=(30, 26, 24), width=6)            # minute
    d.ellipse([c - 8, c - 8, c + 8, c + 8], fill=(176, 140, 70))
    return np.asarray(im, np.float32) / 255.0


CK, _ = encode(clock_tex())
R = 1.0; N_ = 40; pts = [(0, 0, 0)] + [(R * math.cos(2 * math.pi * k / N_), R * math.sin(2 * math.pi * k / N_), 0) for k in range(N_)]
ix = []
for k in range(1, N_ + 1): ix += [0, k, k % N_ + 1]
write_glb(os.path.join(OUT, 'SM_dw_clock.glb'), np.array(pts, np.float32), np.tile([0, 0, 1.0], (len(pts), 1)).astype(np.float32), ix, 'SM_dw_clock',
          uv=np.array([(0.5 + p[0] / 2, 0.5 - p[1] / 2) for p in pts], np.float32), img=CK, double=True, repeat=False)
print("ok")

# ------------------------------------------------------------------------------------------------ the town gate's door: double plank doors with iron bands in the pointed arch opening (the gate is shut)
def door_tex(sz=512):
    r = np.random.default_rng(9); im = np.zeros((sz, sz, 3), np.float32)
    pw = sz // 12
    for k in range(12):
        t = 0.75 + 0.35 * r.random(); col = np.array([0.36, 0.24, 0.13]) * t
        im[:, k * pw:(k + 1) * pw] = col; im[:, k * pw:k * pw + 3] = col * 0.45
    grain = fnoise(sz, 5.0, 21); im *= (0.82 + 0.3 * grain[..., None])
    for y0 in (int(sz * 0.18), int(sz * 0.52), int(sz * 0.82)):                                # iron bands
        im[y0:y0 + int(sz * 0.07), :] = np.array([0.16, 0.16, 0.18]) * (0.85 + 0.3 * grain[y0:y0 + int(sz * 0.07), :, None])
        for x0 in range(pw // 2, sz, pw): im[y0 + int(sz * 0.03):y0 + int(sz * 0.04), x0 - 2:x0 + 3] = 0.42            # rivets
    im[:, sz // 2 - 3:sz // 2 + 3] = np.array([0.08, 0.06, 0.05])                               # the seam between the leaves
    return np.clip(im, 0, 1)


DOOR = encode(door_tex())[0]
ring = pointed(PA_ + 0.05, PHS)
ctr = (0.0, 0.0); P0 = [(0.0, PHS * 0.5)] + ring
ymax = max(py for px, py in ring)
uvs = [(0.5 + px / (2 * PA_ + 0.2), 1.0 - py / ymax) for px, py in P0]
pos = np.array([(px, py, 0.25) for px, py in P0], np.float32); nrm = np.tile([0, 0, 1.0], (len(pos), 1)).astype(np.float32)
idx = []
for k in range(1, len(P0) - 1): idx += [0, k, k + 1]
write_glb(os.path.join(OUT, 'SM_dw_gate_door.glb'), pos, nrm, idx, 'SM_dw_gate_door', uv=np.array(uvs, np.float32), img=DOOR, repeat=False, double=True)
print("gate door ok")

"""Procedural pieces the island needs that the Paradise kit lacks -> Assets/3D/Paradise/ :
 SM_island_ground (the big island, colours baked into a texture), SM_ocean, SM_floor_wood, SM_cave_mountain + SM_cave_inner (rocky
 headland with a tunnel mouth facing +z; origin at the mouth, base at y=0), SM_dg_rock (a rubble boulder).   Run: python gen_island_meshes.py [outdir]"""
import io, os, sys
import numpy as np
from PIL import Image
from glbkit import write_glb, encode, normals, fnoise, vnoise3
from islandshape import q_of, CX, CZ, RX, RZ, FLAT
OUT = sys.argv[1] if len(sys.argv) > 1 else '.'
os.makedirs(OUT, exist_ok=True)

def vn2(X, Z, s, seed):
    p = np.stack([X / s, np.zeros_like(X), Z / s], -1).reshape(-1, 3); return vnoise3(p, seed, 1.0).reshape(X.shape)

def height(X, Z):
    q = q_of(X, Z); return np.where(q < FLAT, 0.0, np.where(q < 1.0, -(q - FLAT) / (1 - FLAT) * 1.4, -1.4 - (q - 1.0) * 30))

def colour(X, Z):
    q = q_of(X, Z); n1 = vn2(X, Z, 5.0, 5)[..., None]; n2 = vn2(X, Z, 1.4, 9)[..., None]; n3 = vn2(X, Z, 14.0, 12)[..., None]
    dry = np.array([0.72, 0.62, 0.42]); grass = np.array([0.34, 0.54, 0.20]); lush = np.array([0.22, 0.42, 0.16]); sand = np.array([0.80, 0.70, 0.48])
    wet = np.array([0.60, 0.53, 0.37]); stone = np.array([0.60, 0.57, 0.50]); rock = np.array([0.42, 0.40, 0.37]); path = np.array([0.66, 0.56, 0.40])
    g = grass * (0.8 + 0.4 * n1)
    base = dry * (1 - n1 * .55) + g * (n1 * .55)                                   # patchy lawn on sandy ground
    forest = np.clip((np.abs(X) - 26) / 10, 0, 1) * np.clip((q_of(X, Z) < .86) * 1.0, 0, 1)
    forest = np.maximum(forest, np.clip((-(Z + 30)) / 14, 0, 1) * 0.8)              # jungle toward the east, west and north
    base = base * (1 - forest[..., None] * .75) + lush * (0.75 + 0.5 * n3) * (forest[..., None] * .75)
    r0 = np.hypot(X, Z + 1.0); base = np.where((r0 < 12)[..., None], dry * (0.95 + 0.1 * n2), base)      # swept plaza
    sx = 2.0 * np.sin(Z / 9.0); road = (np.abs(X - sx) < 2.3) & (Z < 12) & (Z > -46)                    # ancient road north to the cave
    base = np.where(road[..., None], path * (0.92 + 0.16 * n2), base)
    road2 = (np.abs(X) < 3.0) & (Z >= 10) & (Z < 24); base = np.where(road2[..., None], path * (0.92 + 0.16 * n2), base)     # plaza -> dock
    for cx, cz, rr in ((0, -38, 13), (31, -29, 10), (-31, -33, 9)):                                    # ruin forecourts: dusty stone
        d = np.hypot(X - cx, Z - cz) / rr; base = np.where((d < 1)[..., None], stone * (0.85 + 0.25 * n2) * (1 - 0.15 * d[..., None]) + base * 0.0, base)
    mt = np.clip((-(Z + 42)) / 6, 0, 1) * (np.abs(X) < 44); base = base * (1 - mt[..., None] * .8) + rock * (0.8 + 0.4 * n2) * mt[..., None] * .8      # rocky ground at the headland
    base = np.where((q >= 0.80)[..., None], base * (1 - np.clip((q - .8) / .08, 0, 1)[..., None]) + sand * (0.9 + 0.1 * n2) * np.clip((q - .8) / .08, 0, 1)[..., None], base)
    base = np.where((q >= 0.97)[..., None], wet, base)
    base = np.where((q >= 1.05)[..., None], np.array([0.35, 0.58, 0.55]), base)
    return base * (0.93 + 0.14 * n2)

def ocean_col(X, Z):
    R = np.hypot(X - CX, Z - CZ); near = np.array([0.22, 0.7, 0.7]); mid = np.array([0.06, 0.45, 0.62]); far = np.array([0.03, 0.27, 0.5])
    q = q_of(X, Z); t1 = np.clip((q - 1.0) / 0.5, 0, 1)[..., None]; t2 = np.clip((R - 90) / 150, 0, 1)[..., None]
    w = 0.04 * (vn2(X, Z, 6.0, 2)[..., None] - 0.5)
    b = near * (1 - t1) + mid * t1; b = b * (1 - t2) + far * t2 + w; return b

def grid_mesh(n, ext, hfn, cz):
    xs = np.linspace(-ext, ext, n + 1); zs = np.linspace(-ext, ext, n + 1) + cz; X, Z = np.meshgrid(xs, zs); Y = hfn(X, Z)
    pos = np.stack([X, Y, Z], -1).reshape(-1, 3); idx = []
    for r in range(n):
        for c in range(n):
            a = r * (n + 1) + c; b = a + 1; d = a + n + 1; e = d + 1; idx += [(a, d, b), (b, d, e)]
    idx = np.array(idx, np.uint32); nrm = normals(pos, idx); nrm[nrm[:, 1] < 0] *= -1
    uv = np.stack([(pos[:, 0] + ext) / (2 * ext), (pos[:, 2] - cz + ext) / (2 * ext)], -1)
    return pos, nrm, idx, uv

def bake(cfn, ext, cz, px, q=84):
    xs = np.linspace(-ext, ext, px); zs = np.linspace(-ext, ext, px) + cz; X, Z = np.meshgrid(xs, zs); return encode(cfn(X, Z), 'JPEG', q)[0]

EXT = 100.0
p, n, i, uv = grid_mesh(220, EXT, height, CZ)
write_glb(os.path.join(OUT, 'SM_island_ground.glb'), p, n, i, 'SM_island_ground', uv=uv, img=bake(colour, EXT, CZ, 2048, 82), repeat=False)
p, n, i, uv = grid_mesh(50, 300, lambda X, Z: np.zeros_like(X) - 0.9, CZ)
write_glb(os.path.join(OUT, 'SM_ocean.glb'), p, n, i, 'SM_ocean', uv=uv, img=bake(ocean_col, 300, CZ, 768), repeat=False)

# ---- plank floor for the houses (same as before)
def floor_tex():
    r = np.random.default_rng(8); im = np.zeros((512, 512, 3), np.float32)
    for k in range(8):
        base = np.array([0.55, 0.38, 0.22]) * (0.82 + 0.3 * r.random()); yy = np.arange(512)[:, None]
        grain = 0.9 + 0.1 * np.sin(yy * 0.35 + r.random() * 6 + np.arange(64)[None, :] * 0.2); im[:, k * 64:(k + 1) * 64] = base * grain[..., None]; im[:, k * 64:k * 64 + 2] *= 0.55
    return encode(im)[0]
hw = 0.5; pos = np.array([[-hw, .06, -hw], [hw, .06, -hw], [hw, .06, hw], [-hw, .06, hw]], np.float32)
write_glb(os.path.join(OUT, 'SM_floor_wood.glb'), pos, np.tile([0, 1, 0], (4, 1)), [(0, 3, 1), (1, 3, 2)], 'SM_floor_wood', uv=np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32), img=floor_tex())

# ---- rock texture (seamless) + dark cave texture
def rock_tex(seed, dark):
    n = 512; a = fnoise(n, 1.3, seed); b = fnoise(n, 2.4, seed + 1); c = fnoise(n, 1.0, seed + 2)
    crack = np.clip(1 - np.abs(c - 0.5) * 18, 0, 1) ** 2
    base = (np.array([0.50, 0.47, 0.42]) if not dark else np.array([0.20, 0.20, 0.23]))
    v = (0.55 + 0.6 * a + 0.25 * (b - 0.5)) * (1 - 0.55 * crack)
    moss = np.clip((a - 0.62) * 4, 0, 1)[..., None] * (np.array([0.20, 0.34, 0.14]) if not dark else np.array([0.08, 0.14, 0.12]))
    return np.clip(base * v[..., None] * (1 - moss.sum(-1, keepdims=True) * 0.6) + moss * v[..., None], 0, 1)
ROCK = encode(rock_tex(3, False))[0]; DARK = encode(rock_tex(9, True))[0]

def blob(c, r, seed, amp=0.30, freq=0.22, nu=40, nv=26, floor=-1.2):
    u = np.linspace(0, 2 * np.pi, nu + 1)[:-1]; v = np.linspace(0, np.pi, nv)
    U, V = np.meshgrid(u, v); d = np.stack([np.sin(V) * np.cos(U), np.cos(V), np.sin(V) * np.sin(U)], -1).reshape(-1, 3)
    c = np.array(c, float); r = np.array(r, float); p0 = c + d * r
    k = 1 + amp * (vnoise3(p0, seed, freq) - 0.5) * 2 + 0.5 * amp * (vnoise3(p0, seed + 7, freq * 3) - 0.5) * 2
    p = c + d * r * k[:, None]; p[:, 1] = np.maximum(p[:, 1], floor)
    idx = []
    for j in range(nv - 1):
        for i in range(nu):
            a = j * nu + i; b = j * nu + (i + 1) % nu; e = (j + 1) * nu + i; f = (j + 1) * nu + (i + 1) % nu; idx += [(a, e, b), (b, e, f)]
    idx = np.array(idx); fn = np.cross(p[idx[:, 1]] - p[idx[:, 0]], p[idx[:, 2]] - p[idx[:, 0]]); cen = p[idx].mean(1) - c
    flip = (fn * cen).sum(1) < 0; idx[flip] = idx[flip][:, [0, 2, 1]]; return p.astype(np.float32), idx

def merge(parts):
    P, I, o = [], [], 0
    for p, i in parts: P.append(p); I.append(i + o); o += len(p)
    return np.concatenate(P), np.concatenate(I)

def box_uv(pos, nrm, scale):
    """triplanar-ish UVs: each vertex projects along its dominant normal axis (rock has no obvious direction, so seams are fine)."""
    ax = np.abs(nrm); top = (ax[:, 1] >= ax[:, 0]) & (ax[:, 1] >= ax[:, 2]); xs = (ax[:, 0] >= ax[:, 2]) & ~top
    u = np.where(top, pos[:, 0], np.where(xs, pos[:, 2], pos[:, 0])); v = np.where(top, pos[:, 2], pos[:, 1]); return np.stack([u, v], -1) / scale

# ---- the cave mountain (outer rock) -----------------------------------------------------------------------------------------
B = [((-10.4, 5.5, -5), (7, 6, 7)), ((10.4, 5.5, -5), (7, 6, 7)), ((-20, 6, -6), (9, 7, 8)), ((21, 6, -7), (9, 8, 9)), ((-30, 5, -8), (9, 6, 9)), ((30, 5, -8), (9, 6, 9)),
     ((0, 8.8, -5), (8.5, 4.4, 6)), ((0, 12, -12), (20, 9, 11)), ((-14, 12, -12), (12, 8, 9)), ((14, 12, -12), (12, 8, 9)),
     ((0, 7, -20), (30, 9, 9)), ((-20, 6, -16), (10, 7, 10)), ((20, 6, -16), (10, 7, 10)), ((0, 17, -15), (12, 6, 8)),
     ((-3.7, 4.0, 0.6), (1.7, 1.5, 1.6)), ((3.7, 4.0, 0.6), (1.7, 1.5, 1.6)),
     ((-5.6, 3.0, -1.2), (2.6, 3.4, 3.6)), ((5.6, 3.0, -1.2), (2.6, 3.4, 3.6)), ((-7.5, 2.2, 1.0), (2.2, 2.4, 2.4)), ((7.5, 2.2, 1.0), (2.2, 2.4, 2.4))]
parts = [blob(c, r, 11 + k * 5) for k, (c, r) in enumerate(B)]
pos, idx = merge(parts); nrm = normals(pos, idx)
write_glb(os.path.join(OUT, 'SM_cave_mountain.glb'), pos, nrm, idx, 'SM_cave_mountain', uv=box_uv(pos, nrm, 7.0), img=ROCK)

# ---- tunnel interior: side walls, ceiling, floor, back wall, in dark rock (origin = mouth, x +-3, y 0..4.8, z +1.5 .. -10)
Q = []; UV = []; NR = []; IX = []
def quad(p0, p1, p2, p3, hint, w, h):
    p = np.array([p0, p1, p2, p3], np.float32); n = np.cross(p[1] - p[0], p[3] - p[0]); n /= np.linalg.norm(n)
    if np.dot(n, hint) < 0: p = p[[0, 3, 2, 1]]; n = -n
    o = sum(len(a) for a in Q); Q.append(p); NR.append(np.tile(n, (4, 1))); UV.append(np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float32) / 4.0); IX.append(np.array([(0, 1, 2), (0, 2, 3)]) + o)
Z0, Z1, H, W = 0.3, -10.0, 4.8, 3.0
quad((-W, 0, Z0), (-W, 0, Z1), (-W, H, Z1), (-W, H, Z0), (1, 0, 0), Z0 - Z1, H)
quad((W, 0, Z0), (W, 0, Z1), (W, H, Z1), (W, H, Z0), (-1, 0, 0), Z0 - Z1, H)
quad((-W, H, Z0), (W, H, Z0), (W, H, Z1), (-W, H, Z1), (0, -1, 0), 2 * W, Z0 - Z1)
quad((-W, 0.04, Z0), (W, 0.04, Z0), (W, 0.04, Z1), (-W, 0.04, Z1), (0, 1, 0), 2 * W, Z0 - Z1)
quad((-W, 0, Z1), (W, 0, Z1), (W, H, Z1), (-W, H, Z1), (0, 0, 1), 2 * W, H)
write_glb(os.path.join(OUT, 'SM_cave_inner.glb'), np.concatenate(Q), np.concatenate(NR), np.concatenate(IX), 'SM_cave_inner', uv=np.concatenate(UV), img=DARK,
          extra_pos=[(0, 0, -34)] * 3)

# ---- rubble boulder
p, i = blob((0, 0.6, 0), (1.2, 0.9, 1.0), 77, amp=0.25, freq=0.9, nu=24, nv=16, floor=0.0); nr = normals(p, i)
write_glb(os.path.join(OUT, 'SM_dg_rock.glb'), p, nr, i, 'SM_dg_rock', uv=box_uv(p, nr, 2.5), img=ROCK)
print('ok')

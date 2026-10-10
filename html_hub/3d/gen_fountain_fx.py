"""Animated water for Assets/3D/Generated/Fountain.glb (the two-tier plaza fountain on Paradise Island).

Writes two GLBs in the fountain's own model space (x/z centred, y -0.28..0.28, 1 unit across), so give both pieces the SAME
[x, z, rotY, y, scale] as the Fountain piece in the scene and they line up:
  FountainFX_surface.glb  the lower basin water and the upper bowl water (opaque; hub3d.js kind 4: small ripples, rings and foam)
  FountainFX_jets.glb     the centre jet, the arching sprays and the overflow curtain (alpha-blended; hub3d.js kind 3: flowing streaks)
hub3d.js picks the animation from the "FountainFX" model name (waterKind), so keep the names.

Vertex colours carry shader data (hub3d.js ignores them for water otherwise):
  surface:  r = radius (0..1 of the disc) of the first splash ring, g = radius of the second ring (-1 = none)
  jets:     r = opacity, g = streak lanes around the tube (<1.5 = a solid sheet), b = flow speed
Run:  python3 gen_fountain_fx.py <out_dir>
"""
import sys, os
import numpy as np
from glbkit import write_glb, normals

BASIN_Y, BASIN_R = -0.085, 0.402        # lower basin: floor -0.131, rim top -0.056, inner wall r 0.405
BOWL_Y, BOWL_R = 0.262, 0.162           # upper cup: flat plate at 0.248, lip top 0.278, inner lip r ~0.16
CURTAIN_R = 0.236                       # the cup's outer lip; the overflow falls from here into the basin
JET_TOP = 0.462


def disc(y, R, r_in, rings, segs, foam1, foam2):
    pos, uv, col = [], [], []
    for i in range(rings + 1):
        rn = r_in / R + (1 - r_in / R) * i / rings
        for k in range(segs + 1):
            a = 2 * np.pi * k / segs
            pos.append((R * rn * np.cos(a), y, R * rn * np.sin(a)))
            uv.append((0.5 + 0.5 * rn * np.cos(a), 0.5 + 0.5 * rn * np.sin(a)))
            col.append((foam1, foam2, 0, 1))
    idx = []
    for i in range(rings):
        for k in range(segs):
            a = i * (segs + 1) + k; b = a + segs + 1
            idx += [a, a + 1, b, a + 1, b + 1, b]          # CCW seen from above (+y normal)
    return np.array(pos, np.float32), np.array(uv, np.float32), np.array(col, np.float32), np.array(idx, np.uint32)


def tube(path, radii, sides, color, v0=0.0, v1=1.0, uvscale=1.0):
    """Tapered tube along a polyline; v runs along the length (v0 at the first point)."""
    path = np.asarray(path, np.float64); n = len(path)
    pos, uv, col = [], [], []
    for i in range(n):
        t = path[min(i + 1, n - 1)] - path[max(i - 1, 0)]; t /= np.linalg.norm(t)
        ref = np.array([0, 1, 0]) if abs(t[1]) < 0.9 else np.array([1, 0, 0])
        u = np.cross(t, ref); u /= np.linalg.norm(u); w = np.cross(t, u)
        for k in range(sides + 1):
            a = 2 * np.pi * k / sides
            pos.append(path[i] + radii[i] * (np.cos(a) * u + np.sin(a) * w)); uv.append((k / sides * uvscale, v0 + (v1 - v0) * i / (n - 1))); col.append(color)
    idx = []
    for i in range(n - 1):
        for k in range(sides):
            a = i * (sides + 1) + k; b = a + sides + 1
            idx += [a, b, a + 1, a + 1, b, b + 1]
    return np.array(pos, np.float32), np.array(uv, np.float32), np.array(col, np.float32), np.array(idx, np.uint32)


def merge(parts):
    P, U, C, I, off = [], [], [], [], 0
    for p, u, c, i in parts:
        P.append(p); U.append(u); C.append(c); I.append(i + off); off += len(p)
    return np.concatenate(P), np.concatenate(U), np.concatenate(C), np.concatenate(I)


def main(out):
    os.makedirs(out, exist_ok=True)
    # ---- surfaces ----
    low = disc(BASIN_Y, BASIN_R, 0.11, 26, 72, CURTAIN_R / BASIN_R, -1.0)
    up = disc(BOWL_Y, BOWL_R, 0.0, 14, 56, 0.0, 0.84)
    P, U, C, I = merge([low, up])
    N = np.tile([0, 1, 0], (len(P), 1)).astype(np.float32)
    write_glb(os.path.join(out, 'FountainFX_surface.glb'), P, N, I, 'FountainFX_surface', uv=U, col=C, color=(0.16, 0.5, 0.58, 1), double=True)

    # ---- jets ----
    parts = []
    # centre column (thicker at the base, bursting open at the top)
    ys = np.linspace(BOWL_Y, JET_TOP, 14)
    parts.append(tube([(0, y, 0) for y in ys], np.linspace(0.0085, 0.0050, 14), 10, (0.92, 1.0, 5.0, 1), 0.0, 1.0))
    # arching sprays that rise out of the column top and fall into the cup
    rng = np.random.default_rng(7); NA = 16
    for j in range(NA):
        ang = 2 * np.pi * (j + 0.35 * rng.random()) / NA; land = 0.115 + 0.035 * rng.random()
        apex = JET_TOP + 0.02 * rng.random(); ts = np.linspace(0, 1, 16)
        r = land * (ts ** 0.9)
        y = (JET_TOP - 0.03) + (apex - JET_TOP + 0.03) * 4 * ts * (1 - ts) - ((JET_TOP - 0.03) - BOWL_Y - 0.004) * ts ** 2
        path = [(rr * np.cos(ang), yy, rr * np.sin(ang)) for rr, yy in zip(r, y)]
        parts.append(tube(path, np.linspace(0.0052, 0.0034, 16), 6, (0.88, 1.0, 4.0 + 1.5 * rng.random(), 1), 0.0, 1.0))
    # overflow curtain: a thin cylindrical sheet from the cup lip into the basin, broken into streams by the shader
    segs, rows = 120, 6
    pos, uv, col, idx = [], [], [], []
    for i in range(rows + 1):
        t = i / rows; yy = 0.252 - (0.252 - (BASIN_Y - 0.004)) * t; rr = CURTAIN_R + 0.014 * t ** 1.6
        for k in range(segs + 1):
            a = 2 * np.pi * k / segs; pos.append((rr * np.cos(a), yy, rr * np.sin(a))); uv.append((k / segs, t)); col.append((0.78, 70.0, 1.5, 1))
    for i in range(rows):
        for k in range(segs):
            a = i * (segs + 1) + k; b = a + segs + 1
            idx += [a, b, a + 1, a + 1, b, b + 1]
    parts.append((np.array(pos, np.float32), np.array(uv, np.float32), np.array(col, np.float32), np.array(idx, np.uint32)))
    P, U, C, I = merge(parts)
    Nn = normals(P, I)
    write_glb(os.path.join(out, 'FountainFX_jets.glb'), P, Nn, I, 'FountainFX_jets', uv=U, col=C, color=(0.62, 0.84, 0.95, 0.4), alpha='BLEND', double=True)
    print('wrote', out)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')

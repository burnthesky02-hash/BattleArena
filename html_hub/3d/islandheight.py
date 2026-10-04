"""Terrain of Paradise Island, shared by gen_island_meshes.py (ground mesh + colours) and make_island.py (y of every prop, `terrain` block of island.json).
World axes: x east, z south.  Rolling hills that climb from the harbour (sea level, south) to the cave plateau (north); every building / plaza stands on a
flat PAD that blends into the hills.  H(X, Z) -> metres above the old sea-level plane (the ocean sits at y = -0.9)."""
import base64
import numpy as np
from glbkit import vnoise3
from islandshape import q_of

GX0, GZ0, CELL, GNX, GNZ = -80.0, -90.0, 1.0, 161, 141          # heightmap grid used by the engine and by the ground mesh (x -80..80, z -90..50)

# (cx, cz, rx, rz, blend, height)   flat pads: inside the ellipse the ground is exactly `height`, then it blends out over `blend` metres
PADS = [
    (0.0, 2.0, 10.5, 10.5, 10.0, 1.6),        # plaza
    (0.0, 20.0, 6.0, 3.5, 7.0, 0.35),        # harbour approach / ferry pier
    (-23.0, 21.0, 6.0, 3.0, 7.0, 0.35),      # west pier
    (-14.6, -15.5, 13.0, 9.5, 11.0, 4.6),    # tavern + annex
    (18.4, -24.0, 13.0, 12.0, 17.0, 9.5),    # mayor's hill (the big house)
    (31.0, 6.4, 8.5, 8.5, 10.0, 3.0),        # blacksmith
    (13.0, 16.5, 8.5, 7.5, 7.0, 0.9),        # item shop
    (-24.0, 11.5, 7.5, 7.0, 7.0, 0.7),       # harbourmaster's lodge
    (-23.5, -13.0, 8.5, 8.0, 11.0, 5.0),     # barn
    (-41.0, -10.0, 11.5, 9.5, 11.0, 5.6),    # field
    (41.0, -19.0, 10.5, 10.5, 12.0, 7.5),    # fountain terrace
    (0.0, -49.0, 40.0, 11.0, 14.0, 11.5),     # cave plateau (the mountain mesh sits on it)
    (-40.5, -44.0, 9.0, 8.0, 12.0, 9.0),     # forest gate
    (27.0, 16.0, 6.0, 5.0, 6.0, 0.4),        # east beach
]


def vn2(X, Z, s, seed):
    p = np.stack([X / s, np.zeros_like(X), Z / s], -1).reshape(-1, 3); return vnoise3(p, seed, 1.0).reshape(X.shape)


def smooth(t): t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)


def H(X, Z):
    X = np.asarray(X, float); Z = np.asarray(Z, float)
    q = q_of(X, Z)
    rise = smooth((-Z - 6) / 52.0) * 9.0                                                  # the land climbs towards the north
    h = 1.1 + rise + 11.0 * (vn2(X, Z, 30.0, 31) - 0.5) + 2.0 * (vn2(X, Z, 10.0, 41) - 0.5) + 0.5 * (vn2(X, Z, 3.5, 51) - 0.5)
    h = h * smooth((0.96 - q) / 0.3)                                                      # hills die out before the shore
    for cx, cz, rx, rz, bl, hh in PADS:
        d = np.hypot((X - cx) / rx, (Z - cz) / rz)                                        # 1 = pad edge
        edge = np.hypot((X - cx) / (rx + bl), (Z - cz) / (rz + bl))                       # 1 = outer blend edge
        w = np.where(d <= 1.0, 1.0, smooth((1.0 - edge) / np.maximum(1.0 - (rx / (rx + bl)), 1e-3)))
        h = h * (1 - w) + hh * w
    shore = smooth((q - 0.80) / 0.12)                                                     # beach profile: ~0.4 m at q=.88, under water by q~.95
    tgt = 0.45 - np.clip((q - 0.88) / 0.12, 0, None) * 1.9
    h = h * (1 - shore) + tgt * shore
    return np.where(q > 1.0, np.minimum(h, -1.4 - (q - 1.0) * 30), h)


def grid():
    xs = GX0 + np.arange(GNX) * CELL; zs = GZ0 + np.arange(GNZ) * CELL
    return np.meshgrid(xs, zs)                                                            # shapes (GNZ, GNX)


_HG = None
def hgrid():
    """the heightmap actually used everywhere: H on the grid, lightly blurred so slopes stay walkable (pad centres stay flat)"""
    global _HG
    if _HG is None:
        from scipy.ndimage import gaussian_filter
        h = H(*grid()); _HG = np.round(gaussian_filter(h, 1.6, mode="nearest") * 100) / 100
    return _HG


def terrain_json():
    data = np.round(hgrid() * 100).astype('<i2')
    return dict(x0=GX0, z0=GZ0, cell=CELL, nx=GNX, nz=GNZ, scale=100, data=base64.b64encode(data.tobytes()).decode())


def gy_many(X, Z):
    from scipy.ndimage import map_coordinates
    return map_coordinates(hgrid(), [(np.asarray(Z) - GZ0) / CELL, (np.asarray(X) - GX0) / CELL], order=1, mode="nearest")


def gy(x, z):
    """bilinear sample of the same grid the engine uses (so props sit exactly on the rendered ground)"""
    return float(gy_many(np.array([x], float), np.array([z], float))[0])


if __name__ == "__main__":
    X, Z = grid(); h = hgrid()
    print("min", h.min(), "max", h.max(), "land max", h[q_of(X, Z) < .9].max())
    gxx, gzz = np.gradient(h, CELL); sl = np.hypot(gxx, gzz); m = q_of(X, Z) < 0.86
    print("slope p50/p95/max on land", np.percentile(sl[m], 50), np.percentile(sl[m], 95), sl[m].max())
    for nm, (x, z) in dict(plaza=(0, 2), tavern=(-10.6, -13.5), mayor=(18.4, -24), cave=(0, -43), forest=(-40, -45), pier=(0, 26), spawn=(0, 22.5)).items(): print(nm, round(gy(x, z), 2))

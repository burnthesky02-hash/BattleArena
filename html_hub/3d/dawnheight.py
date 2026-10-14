"""Terrain of Dawnwatch (scene `strange`), shared by gen_dawn_meshes.py (ground + river meshes, baked colours) and make_dawnwatch.py (y of every prop,
the `terrain` block, river colliders).  World axes: x east, z south.

Fourth layout (cliff-side town, after the Eldergate reference): the valley is a canyon that opens south onto the river and a bay.
  * the MARKET PLAZA is the lowest level (y 3.0), a wide flat floor, z 10..56;
  * a grand STAIR (a ramp painted as treads) climbs 7 m at the north end of the plaza (z -4..10) to the KEEP TERRACE (y 10.0), where the keep and
    the Eldergate arch stand against the mountain; elsewhere that step is a stone retaining wall;
  * behind and beside the terraces the canyon walls rise in rock LEDGES (flat shelves between steep faces) to 60-90 m;
  * the river runs west-east at z 64 (the bank is quay and road) and opens into a bay to the south-west.
H(X, Z) -> metres.  Run `python dawnheight.py` for sanity numbers."""
import base64
import numpy as np
from glbkit import vnoise3

GX0, GZ0, CELL, GNX, GNZ = -150.0, -190.0, 1.0, 301, 321     # heightmap grid: x -150..150, z -190..130 (the playable floor is x +-46, z -37..90)
WATER_Y = -0.25                                                  # river surface
BED = -2.6
BASE = 3.0                                                       # plaza / bank level
K_Y = 10.0                                                       # keep terrace level
RAMP_Z, RAMP_LH = 3.0, 7.0                                       # the grand stair: centre z and half length at the middle (z -4..10)
FLAT_X, KEEP_X = 47.0, 36.0                                      # half width of the flat plaza floor / of the keep terrace

# (x, z, half-width in metres): the river, west to east; it opens into a bay in the south-west
RIVER = [(-152, 82, 34.0), (-112, 80, 30.0), (-80, 76, 20.0), (-56, 68, 9.0), (-44, 65, 7.2), (-24, 64, 7.0), (0, 64, 7.0), (32, 64, 6.6), (70, 64, 6.4), (110, 63, 6.6), (152, 60, 7.0)]
RIVER_Z = 64.0
BRIDGES = [0.0]                                                  # x of the bridge

PADS = []
SHELF_D, SHELF_H = [], []

# flagstone / cobbled areas painted on the ground: (cx, cz, half-x, half-z)  [rounded rectangles]; the first is the market plaza (rings round the fountain)
PAVED = [(0, 32.5, 38, 22.5), (0, -14.0, 31, 12.5)]

# centre lines of the dirt / cobbled roads (x, z)
ROAD = [
    [(-62, 53.5), (-30, 53.5), (0, 53.5), (30, 53.5), (62, 53.5)],                           # the quay street along the north bank
    [(-62, 78.0), (-30, 78.0), (0, 78.0), (30, 78.0), (62, 78.0)],                           # the south road
    [(0, 53.5), (0, 50)], [(0, 74), (0, 78)],                                                # bridge landings
]


def vn2(X, Z, s, seed):
    p = np.stack([X / s, np.zeros_like(X), Z / s], -1).reshape(-1, 3)
    return vnoise3(p, seed, 1.0).reshape(X.shape)


def smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def river_dist(X, Z):
    """(distance to the river centreline, half-width there)"""
    X = np.asarray(X, float); Z = np.asarray(Z, float)
    best = np.full(X.shape, 1e9); wid = np.zeros(X.shape)
    for (x0, z0, w0), (x1, z1, w1) in zip(RIVER[:-1], RIVER[1:]):
        dx, dz = x1 - x0, z1 - z0
        t = np.clip(((X - x0) * dx + (Z - z0) * dz) / (dx * dx + dz * dz), 0, 1)
        d = np.hypot(X - (x0 + t * dx), Z - (z0 + t * dz))
        m = d < best
        best = np.where(m, d, best); wid = np.where(m, w0 + (w1 - w0) * t, wid)
    return best, wid


def ramp(X, Z):
    """0 on the plaza floor, 1 on the keep terrace: the grand stair in the middle (long, gentle), a short steep retaining wall at the sides"""
    lh = RAMP_LH - 4.5 * smooth((np.abs(X) - 12.0) / 12.0)
    return smooth((RAMP_Z - Z) / (2 * lh) + 0.5)


def base(X, Z):
    """the natural land, before the river carve"""
    X = np.asarray(X, float); Z = np.asarray(Z, float)
    h = BASE + (K_Y - BASE) * ramp(X, Z)
    Xw = X + 9.0 * (vn2(X, Z, 34.0, 91) - 0.5) * 2 + 3.0 * (vn2(X, Z, 12.0, 92) - 0.5) * 2         # warp the cliff lines so the canyon is not a box
    Zw = Z + 9.0 * (vn2(X, Z, 34.0, 93) - 0.5) * 2 + 3.0 * (vn2(X, Z, 12.0, 94) - 0.5) * 2
    ax = np.abs(Xw)
    n_r = 1.0 - np.abs(2 * vn2(X, Z, 22.0, 61) - 1)                                        # ridged noise for the cliffs
    n2 = 1.0 - np.abs(2 * vn2(X, Z, 26.0, 71) - 1)
    n3 = vn2(X, Z, 9.0, 83)
    ex = FLAT_X - (FLAT_X - KEEP_X) * smooth((RAMP_Z - 2.0 - Zw) / 10.0)                  # the walls start at the plaza edge, nearer in beside the keep terrace
    fs = 1.0 - 0.75 * smooth((Zw - 46.0) / 16.0)                                           # the walls ease off towards the river
    wx = smooth((ax - ex) / 30.0) * (26.0 + 14.0 * n2) * fs
    wz = smooth((-Zw - 42.0) / 40.0) * (58.0 + 20.0 * n_r)
    w = wx + wz
    u = (w + (n3 - 0.5) * 9.0) / (8.0 + 3.0 * n2)                                                       # rock ledges: flat shelves, steep faces
    k = np.floor(u); f = u - k
    wq = (8.0 + 3.0 * n2) * (k + smooth((f - 0.60) / 0.40))
    h = h + np.where(w > 2.0, wq * smooth(w / 3.0), w)
    h = h + smooth((Z - 94.0) / 14.0) * (16.0 + 12.0 * n_r)                                # the southern rim
    return h


def H(X, Z):
    h = base(X, Z)
    d, w = river_dist(X, Z)                                                                # carve the river valley last
    c = smooth((w + 1.6 - d) / 2.6)
    return h * (1 - c) + BED * c


_HG = None


def grid():
    xs = GX0 + np.arange(GNX) * CELL; zs = GZ0 + np.arange(GNZ) * CELL
    return np.meshgrid(xs, zs)                                                             # shapes (GNZ, GNX)


def hgrid():
    """the heightmap the engine uses and the ground mesh is built from (lightly blurred so slopes stay walkable)"""
    global _HG
    if _HG is None:
        from scipy.ndimage import gaussian_filter
        h = H(*grid()); _HG = np.round(gaussian_filter(h, 0.7, mode="nearest") * 100) / 100
    return _HG


def terrain_json():
    data = np.round(hgrid() * 100).astype('<i2')
    return dict(x0=GX0, z0=GZ0, cell=CELL, nx=GNX, nz=GNZ, scale=100, data=base64.b64encode(data.tobytes()).decode())


def gy_many(X, Z):
    from scipy.ndimage import map_coordinates
    return map_coordinates(hgrid(), [(np.asarray(Z) - GZ0) / CELL, (np.asarray(X) - GX0) / CELL], order=1, mode="nearest")


def gy(x, z):
    return float(gy_many(np.array([x], float), np.array([z], float))[0])


if __name__ == "__main__":
    h = hgrid(); print("min", h.min(), "max", h.max())
    for nm, (x, z) in dict(spawn=(0, 50), plaza=(0, 30), stair_mid=(0, 3), keep=(0, -22), fore=(0, -12), rear=(0, -36), keep_w=(-30, -10), plaza_w=(-44, 30), bridge=(0, 55), s_bank=(0, 78)).items():
        print(nm, round(gy(x, z), 2))
    gxx, gzz = np.gradient(h, CELL); sl = np.hypot(gxx, gzz)
    X, Z = grid(); m = (np.abs(X) < 46) & (Z > -37) & (Z < 90)
    print("slope p50/p90/p99/max (floor)", np.percentile(sl[m], [50, 90, 99]), sl[m].max())

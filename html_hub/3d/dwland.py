"""The landscape of Dawnwatch, as sculpted by hand in the 3D editor (dw_land.json = the editor's strange.json: terrain heights + painted splat map + the pieces the
editor placed: the lake planes, the bridge segments, the citadel's round forecourt).  This module loads it and adds the one thing the sculpt lacked: a grand ramp up to the
citadel plateau.  gy()/gy_many() answer heights for the scene generator; terrain_json() returns the terrain block (heights with the ramp, the editor's `base`, the paint
with the ramp painted as stone).  Nothing else of the sculpt is changed."""
import base64, json, os
import numpy as np
from scipy.ndimage import map_coordinates

HERE = os.path.dirname(os.path.abspath(__file__))
LAND = json.load(open(os.path.join(HERE, "dw_land.json"), encoding="utf-8"))
T0 = LAND["terrain"]
GX0, GZ0, CELL, GNX, GNZ = T0["x0"], T0["z0"], T0["cell"], T0["nx"], T0["nz"]
SC = T0["scale"]
H0 = np.frombuffer(base64.b64decode(T0["data"]), "<i2").reshape(GNZ, GNX).astype(float) / SC
H = H0.copy()
WATER_Y = 27.0                                       # the editor's lake plane

# the grand ramp: (x, z) waypoints, the height is interpolated along the arc from the first terrain height to the last; half width; side slope (m of drop per m)
RAMPS = [dict(pts=[(-52, -70.5, 61.0), (-30, -70.5), (-8, -70.5), (6, -70.5, 85.3)], hw=3.6, slope=2.6, stairs=True),
         # stairs from the market floor up to the three shelves round the plaza: (x, z, height) ends, half width
         dict(pts=[(14, -21, 32.0), (14, -35, 39.0)], hw=2.0, slope=2.6, stairs=True),
         dict(pts=[(-2, -21, 32.0), (-2, -33, 39.0)], hw=1.4, slope=2.6, stairs=True),
         dict(pts=[(30, -21, 32.0), (30, -33, 39.0)], hw=1.4, slope=2.6, stairs=True),
         dict(pts=[(-3, 2, 32.0), (-13, 2, 38.0)], hw=1.8, slope=2.6, stairs=True),
         dict(pts=[(31, 2, 32.0), (41, 2, 38.0)], hw=1.8, slope=2.6, stairs=True)]

# raised shelves round the market basin (x0, x1, z0, z1, top height): a cliff face of about 3:1 on the plaza side, the existing walls behind
TERRACES = [dict(x0=-18.0, x1=47.0, z0=-49.5, z1=-27.0, h=39.0),
            dict(x0=-19.0, x1=-7.0, z0=-27.0, z1=26.0, h=38.0),
            dict(x0=35.0, x1=46.0, z0=-27.0, z1=26.0, h=38.0)]


def grid():
    xs = GX0 + np.arange(GNX) * CELL; zs = GZ0 + np.arange(GNZ) * CELL
    return np.meshgrid(xs, zs)


def _carve(r):
    X, Z = grid()
    pts = r["pts"]; xz = np.array([(p[0], p[1]) for p in pts]); seg = np.hypot(*np.diff(xz, axis=0).T); arc = np.concatenate([[0], np.cumsum(seg)])
    h_a = pts[0][2]; h_b = pts[-1][2]
    best = np.full(X.shape, 1e9); s_at = np.zeros(X.shape)
    for k in range(len(pts) - 1):
        (x0, z0), (x1, z1) = xz[k], xz[k + 1]
        dx, dz = x1 - x0, z1 - z0
        t = np.clip(((X - x0) * dx + (Z - z0) * dz) / (dx * dx + dz * dz), 0, 1)
        d = np.hypot(X - (x0 + t * dx), Z - (z0 + t * dz)); m = d < best
        best = np.where(m, d, best); s_at = np.where(m, arc[k] + t * seg[k], s_at)
    road_h = h_a + (h_b - h_a) * s_at / arc[-1]
    off = np.maximum(best - r["hw"], 0.0)
    out = np.where(road_h >= H, np.maximum(H, road_h - r["slope"] * off), np.minimum(H, road_h + 4.0 * off))
    core = best <= r["hw"] + 0.5
    return np.where(best < r["hw"] + 30, np.where(core, road_h, out), H), best <= r["hw"] + 1.5, best < r["hw"] + 32


def _raise(t):
    X, Z = grid()
    dx = np.maximum(np.maximum(t["x0"] - X, X - t["x1"]), 0); dz = np.maximum(np.maximum(t["z0"] - Z, Z - t["z1"]), 0)
    d = np.hypot(dx, dz)
    return np.maximum(H, t["h"] - 3.2 * d), d < (t["h"] - 31.0) / 3.2 + 3


TERR_NEAR = np.zeros(H.shape, bool)
for _t in TERRACES:
    H, _n = _raise(_t); TERR_NEAR |= _n
from scipy.ndimage import gaussian_filter as _gf
H = np.where(TERR_NEAR & (np.abs(H - H0) > 0.01), _gf(H, 0.7), H)
H_T = H.copy()                                                  # the sculpt plus the shelves, before the stairs are cut
TERR_CHANGED = np.abs(H_T - H0) > 0.05

ROAD_MASK = np.zeros(H.shape, bool); NEAR = np.zeros(H.shape, bool)
for _r in RAMPS:
    H, _m, _n = _carve(_r); ROAD_MASK |= _m; NEAR |= _n
from scipy.ndimage import gaussian_filter
_Hs = gaussian_filter(H, 0.8)
H = np.where(NEAR & (np.abs(H - H_T) > 0.01), _Hs, H)         # soften only where the ramp or stairs changed the ground
CARVED = np.abs(H - H_T) > 0.25                             # what the stairs and the ramp changed


def gy_many(X, Z):
    return map_coordinates(H, [(np.asarray(Z, float) - GZ0) / CELL, (np.asarray(X, float) - GX0) / CELL], order=1, mode="nearest")


def gy(x, z):
    return float(gy_many(np.array([x], float), np.array([z], float))[0])


def carved(x, z, r=3.0):
    """True if the ramp work touched the ground within r metres"""
    i0 = int((z - r - GZ0) / CELL); i1 = int((z + r - GZ0) / CELL) + 1; j0 = int((x - r - GX0) / CELL); j1 = int((x + r - GX0) / CELL) + 1
    return bool(CARVED[max(i0, 0):i1, max(j0, 0):j1].any())


# ---- the splat map (RGBA = grass_lush, dirt_pixel, cave_dirt, stone) : decode, paint, encode
def paint_image():
    P = T0["paint"]; res = P["res"]; w = (GNX - 1) * res; hh = (GNZ - 1) * res
    arr = np.frombuffer(base64.b64decode(P["data"]), np.uint8).reshape(-1, 5)
    px = np.repeat(arr[:, 1:], arr[:, 0].astype(int), axis=0)[: w * hh]
    return px.reshape(hh, w, 4).copy(), res


def paint_encode(img):
    flat = img.reshape(-1, 4); out = bytearray()
    change = np.any(flat[1:] != flat[:-1], axis=1); starts = np.concatenate([[0], np.nonzero(change)[0] + 1]); ends = np.concatenate([starts[1:], [len(flat)]])
    for s, e in zip(starts, ends):
        n = e - s; px = flat[s]
        while n > 0:
            c = min(n, 255); out += bytes([c, px[0], px[1], px[2], px[3]]); n -= c
    return base64.b64encode(bytes(out)).decode()


def terrain_json(img=None):
    """img: an already repainted splat map (from paint_image()), or None for the editor's paint"""
    t = dict(T0)
    t["data"] = base64.b64encode(np.round(H * SC).astype("<i2").tobytes()).decode()
    res = T0["paint"]["res"]
    if img is None: img, res = paint_image()
    else: img = img.copy()
    ys, xs = np.nonzero(np.kron(ROAD_MASK, np.ones((res, res), bool)))
    img[ys, xs] = (0, 0, 0, 255)                                                      # the ramp is stone
    t["paint"] = dict(T0["paint"], data=paint_encode(img))
    return t


if __name__ == "__main__":
    print("carved cells", int(CARVED.sum()), "max change", float(np.abs(H - H0).max()))
    for k in (-52, -40, -20, -6, 6): print(k, round(gy(k, -70.5), 1), round(float(H0[int(-70.5 - GZ0), int(k - GX0)]), 1))

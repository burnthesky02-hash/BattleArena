"""Layout of the Whispering Wood (scene `forest`), shared by gen_forest_meshes.py (ground colours) and make_forest.py (placement, collision).
World axes: x east, z south. Trails are polylines (x, z); clearings are circles (x, z, r).  Walkable = near a trail or inside a clearing; everything else is solid forest."""
import numpy as np

TRAILS = {
    "main":  [(0, 62), (0, 52), (-10, 43), (-20, 33), (-19, 21), (-9, 10), (2, 3), (12, 0)],
    "north": [(12, 0), (4, -9), (-2, -19), (-10, -29), (-13, -39), (-14, -49), (-14, -62)],
    "east":  [(12, 0), (24, -3), (36, -12), (40, -26), (36, -38), (30, -48)],
    "b1":    [(-20, 33), (-34, 29), (-48, 24), (-58, 16)],
    "b2":    [(-19, 21), (-33, 12), (-47, 1), (-57, -12)],
    "b3":    [(24, -3), (38, 6), (50, 16), (58, 26)],
    "b4":    [(-10, -29), (-26, -33), (-40, -39), (-52, -48)],
    "b5":    [(36, -12), (50, -16), (60, -8)],
}
CLEAR = {"head": (0, 56, 11), "pool": (12, 0, 10), "camp": (30, -48, 12.5), "grove": (-14, -63, 13.5), "look": (-58, 16, 6.5),
         "giant": (-57, -12, 6.5), "spider": (58, 26, 7.0), "cache": (-52, -48, 6.5), "glade": (60, -8, 6.5)}
POND = (13.8, -3.4, 3.8)                 # the pool under the waterfall (solid)
FALL = (13.0, -11.0)                      # foot of the waterfall (on the cliff north of the pool)
TRAIL_HW = 1.9                            # dirt half-width (visual)
WALK_HW = 3.4                             # walkable half-width of a trail
BOUNDS = dict(minX=-74, maxX=74, minZ=-80, maxZ=66)

def _seg_dist(X, Z, x0, z0, x1, z1):
    dx, dz = x1 - x0, z1 - z0; L2 = dx * dx + dz * dz
    t = np.clip(((X - x0) * dx + (Z - z0) * dz) / L2, 0, 1)
    return np.hypot(X - (x0 + t * dx), Z - (z0 + t * dz))

def dist_trails(X, Z):
    X = np.asarray(X, float); Z = np.asarray(Z, float); best = np.full(np.shape(X), 1e9)
    for pts in TRAILS.values():
        for (x0, z0), (x1, z1) in zip(pts, pts[1:]): best = np.minimum(best, _seg_dist(X, Z, x0, z0, x1, z1))
    return best

def dist_walk(X, Z):
    """signed distance to the walkable area: <= 0 inside it."""
    X = np.asarray(X, float); Z = np.asarray(Z, float); d = dist_trails(X, Z) - WALK_HW
    for (cx, cz, r) in CLEAR.values(): d = np.minimum(d, np.hypot(X - cx, Z - cz) - r)
    return d

def walkable(X, Z):
    X = np.asarray(X, float); Z = np.asarray(Z, float)
    ok = dist_walk(X, Z) <= 0
    ok &= np.hypot(X - POND[0], Z - POND[1]) > POND[2]
    return ok

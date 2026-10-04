"""Layout shared by gen_island_meshes.py (ground colours) and make_island.py (placement): winding dirt paths, plaza, farm, terrace.
World axes: x east, z south. Paths are polylines (x, z) of half-width HW metres."""
import numpy as np
PATHS = {
 "dock":   [(0, 27), (0, 18), (0, 8)],
 "cave":   [(0, 0), (0, -5), (9, -11), (11, -18), (2, -23), (-6, -27), (-4, -33), (2, -38), (0, -43)],
 "west":   [(-5, 1), (-14, 3), (-22, 4), (-28, 0), (-31, -6)],
 "tavern": [(-14, 3), (-12, -4), (-12.6, -8)],
 "east":   [(5, 1), (14, 3), (22, 6), (26, 5)],
 "mayor":  [(9, -11), (14, -14), (19.4, -15.6)],
 "fount":  [(22, 6), (24, -2), (30, -9), (38, -13), (41, -15)],
 "shop":   [(0, 10), (6, 11.5), (12, 11.2), (14.4, 10.9)],
 "harbor": [(-4, 14), (-12, 17), (-19, 19.5), (-23, 21)],
 "forest": [(-6, -27), (-16, -31), (-26, -36), (-34, -41), (-40, -44)],
 "farm":   [(-31, -6), (-31, -12)],
 "lodge":  [(-21, 20.5), (-25.5, 17.6)],
}
HW = 1.9
PLAZA = (0.0, 2.0, 9.0)                 # cobbled square: cx, cz, radius
FARM = (-41.0, -10.0, 9.0, 7.0)         # tilled field rectangle: cx, cz, half-w, half-d
TERRACE = (41.0, -19.0, 8.5)            # stone terrace + fountain on the eastern headland
MOUNTAIN_Z = -46.0
def dist_to_paths(X, Z, names=None):
    best = np.full(np.shape(X), 1e9)
    for k, pts in PATHS.items():
        if names and k not in names: continue
        for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
            dx, dz = x1 - x0, z1 - z0; L2 = dx * dx + dz * dz
            t = np.clip(((X - x0) * dx + (Z - z0) * dz) / L2, 0, 1)
            best = np.minimum(best, np.hypot(X - (x0 + t * dx), Z - (z0 + t * dz)))
    return best
def path_pts(step=2.0):
    out = []
    for pts in PATHS.values():
        for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
            n = max(1, int(np.hypot(x1 - x0, z1 - z0) / step))
            for i in range(n + 1): out.append((x0 + (x1 - x0) * i / n, z0 + (z1 - z0) * i / n))
    return out

"""Builds html_hub/3d/strange.json for the terrain-only pass: the ground and water meshes from gen_dawn_meshes.py on the dawnheight.py heightmap, nothing else.
Colliders are generated from the heightmap: water and ground steeper than SLOPE_MAX cannot be walked.  The settings (sky, light, music) come from the previous scene."""
import json, os, sys
import numpy as np
import dawnheight as DH

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else HERE
prev = json.load(open(os.path.join(OUT, "strange_v4.json"), encoding="utf-8"))
SLOPE_MAX = 1.5
CELLS = 2.0
BOUNDS = dict(minX=-122, maxX=122, minZ=-140, maxZ=124)
GEN = "/assets/3D/Generated/"

h = DH.hgrid(); gx, gz = np.gradient(h, DH.CELL); sl = np.hypot(gx, gz)
from scipy.ndimage import maximum_filter
sl = maximum_filter(sl, size=3)
cols = []
for zc in np.arange(BOUNDS["minZ"], BOUNDS["maxZ"] + 0.1, CELLS):
    run = None
    for xc in np.arange(BOUNDS["minX"], BOUNDS["maxX"] + CELLS, CELLS):
        i = int(round((zc - DH.GZ0) / DH.CELL)); j = int(round((xc - DH.GX0) / DH.CELL))
        blocked = h[i, j] < -0.6 or sl[i, j] > SLOPE_MAX
        if blocked and run is None: run = [xc, xc]
        elif blocked: run[1] = xc
        if (not blocked or xc >= BOUNDS["maxX"]) and run is not None:
            cols.append({"x": round((run[0] + run[1]) / 2, 2), "z": round(zc, 2), "w": round(run[1] - run[0] + CELLS, 2), "d": CELLS + 0.2}); run = None

sx, sz = DH.U(490, 290)
scene = {k: prev[k] for k in ("story", "restart", "name", "kit", "tile", "music", "playerHeight", "light", "sky", "fx")}
scene.update(autorun=[], objectives=[], npcs=[], events=[], decals=[], walk=[],
             pieces=[[GEN + "SM_dw_ground", 0, 0, 0, 0, 1], [GEN + "SM_dw_river", 0, 0, 0, 0, 1]],
             colliders=cols, terrain=DH.terrain_json(), spawn={"x": round(sx, 1), "z": round(sz, 1)}, bounds=BOUNDS,
             camera={"pitch": 28, "dist": 46}, fog={"color": [0.72, 0.82, 0.92], "near": 160, "far": 420},
             encounters={"rate": 0, "level": [22, 26], "pool": ["stone_gargoyle"], "zones": [{"x": 0, "z": 0, "w": 400, "d": 400, "safe": True}], "text": ""})
with open(os.path.join(OUT, "strange.json"), "w", encoding="utf-8", newline="") as f:
    json.dump(scene, f, ensure_ascii=False, separators=(",", ":"))
print("strange.json terrain only:", len(cols), "colliders, spawn", scene["spawn"])

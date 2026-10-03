"""Builds maps/kenney_arena.json -- a walled courtyard arena from the Kenney Retro Fantasy Kit (CC0).
Kit pieces are 1x1x1 unit tiles; everything here is scaled by S so a wall is ~4 world units tall
(heroes are ~3.5 units tall). Run: python make_kenney_arena.py   (writes ./maps/kenney_arena.json)
"""
import json, os, random
random.seed(11)
S = 4.0
KIT = "/assets/3D/kenney_retro-fantasy-kit/Models/GLB format/"
props = []
def put(name, x, z, rot=0, y=0.0, scale=S):
    props.append({"model": KIT + name + ".glb", "pos": [x, y, z], "rotY": rot, "scale": scale})

XS = [-10, -6, -2, 2, 6, 10]          # floor columns (x -12..12)
ZS = [-6, -2, 2, 6, 10]               # floor rows    (z -8..12)
for x in XS:
    for z in ZS:
        put("floor-flat", x, z, 0)

BACK, FRONT, LEFT, RIGHT = -10, 14, -14, 14
# back wall (faces +z toward the arena), gate in the middle
for i, x in enumerate(range(-10, 11, 4)):
    kind = "wall-fortified-gate" if x == 2 else ("wall-fortified-window" if i % 2 else "wall-fortified")
    put(kind, x, BACK, 0)
# side walls
for z in range(-6, 11, 4):
    put("wall-fortified-window" if (z // 4) % 2 else "wall-fortified", LEFT, z, 90)
    put("wall-fortified-window" if (z // 4) % 2 else "wall-fortified", RIGHT, z, 270)
# front wall (camera side; hidden automatically by near-camera culling, visible when you orbit round)
for x in range(-10, 11, 4):
    put("wall-fortified", x, FRONT, 180)
# battlements along the top of every wall piece (sit on the outer edge)
for x in range(-10, 11, 4):
    put("battlement", x, BACK, 0, y=S); put("battlement", x, FRONT, 180, y=S)
for z in range(-6, 11, 4):
    put("battlement", LEFT, z, 90, y=S); put("battlement", RIGHT, z, 270, y=S)
# corner towers
for cx, cz in ((LEFT, BACK), (RIGHT, BACK), (LEFT, FRONT), (RIGHT, FRONT)):
    put("tower-base", cx, cz, 0)
    put("tower-top", cx, cz, 0, y=S * 1.0)
# columns along the back wall
for x in (-9, -3, 3, 9):
    put("column", x, BACK + 2.4, 0)
# clutter, kept out of the combat field (|x|<=10, z -4..10)
put("barrels", -11.3, -7.0, 20); put("barrels", 11.2, 11.2, 200)
put("detail-crate", 11.0, -7.2, 15); put("detail-crate-small", 11.2, -5.6, 40); put("detail-crate", -11.0, 11.3, 70)
put("detail-barrel", -11.6, -5.2, 0)
# trees outside the walls for depth
for x, z in ((-19, -14), (-8, -17), (9, -16), (20, -12), (-21, 4), (22, 6)):
    put("tree-large", x, z, random.choice((0, 90, 180)), scale=S * 1.2)

data = {
    "name": "Kenney Courtyard",
    "model": "floor-flat.glb",                    # unused placeholder, replaced below
    "scale": 1, "offset": [0, 0, 0], "rotY": 0,
    "props": props,
    "light": {"dir": [-0.5, -1, -0.45], "color": [1.0, 0.92, 0.80], "ambient": [0.58, 0.56, 0.66]},
    "fog": {"color": [0.12, 0.09, 0.22], "near": 45, "far": 110},
    "sky": "painted", "cullNearCamera": 8,
}
# the first placement is the "main" model; use the first floor tile for it so nothing is drawn twice
first = props.pop(0)
data["model"] = first["model"]; data["offset"] = first["pos"]; data["rotY"] = first["rotY"]; data["scale"] = first["scale"]
os.makedirs("maps", exist_ok=True)
json.dump(data, open("maps/kenney_arena.json", "w"), indent=1)
print("pieces:", len(props) + 1)

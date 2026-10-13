"""One-off: rebuild the Hollow Cave walls in html_hub/3d/dungeon.json as long stretched blocks that follow the cave outline (see cave_walls.py).

Reads the walkable floor cells from the floor_*.glb chunks the scene uses, drops the old per-cell wall blocks (the ones make_cave.py generated;
hand-placed pieces are left alone), adds the new blocks and gives the three rockfall doors the same wall height.
The first run saves the original scene as dungeon.pre_stretchwalls.json and every run starts again from that file, so it can be re-run after
changing the settings at the top of cave_walls.py.  (Edits made to dungeon.json in the editor after the first run would be replaced.)
Usage: python restretch_cave_walls.py"""
import json, os, shutil, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cave_walls as cw

WALL = "/assets/3D/CaveCamp/SM_cv_wall_rock"
ASSET = os.path.normpath(os.path.join(HERE, "..", "..", "Assets", "3D", "CaveCamp"))
scene = os.path.join(HERE, "dungeon.json")
backup = os.path.join(HERE, "dungeon.pre_stretchwalls.json")
if not os.path.exists(backup):
    shutil.copyfile(scene, backup)
d = json.load(open(backup))
P = d["pieces"]


def floor_cells(names):
    cells = set()
    for n in names:
        if n == "floor_lake": continue                        # water surface; floor_lakebed already covers the same cells
        b = open(os.path.join(ASSET, n + ".glb"), "rb").read()
        jl = struct.unpack("<I", b[12:16])[0]; js = json.loads(b[20:20 + jl]); bin0 = 20 + jl + 8
        for m in js["meshes"]:
            for pr in m["primitives"]:
                a = js["accessors"][pr["attributes"]["POSITION"]]; bv = js["bufferViews"][a["bufferView"]]
                off = bin0 + bv.get("byteOffset", 0) + a.get("byteOffset", 0)
                v = struct.unpack("<%df" % (a["count"] * 3), b[off:off + a["count"] * 12])
                for q in range(0, a["count"], 4):                 # four corners per 4 m floor quad
                    cx = sum(v[3 * (q + t)] for t in range(4)) / 4; cz = sum(v[3 * (q + t) + 2] for t in range(4)) / 4
                    cells.add((int(round(cx / 4)), int(round(cz / 4))))
    return cells


def old_main(p):
    """a block make_cave.py generated per wall cell: no hide key, uniform xz scale 1.05..1.4, height 0.85..1.84, small jitter around a cell centre"""
    if p[0] != WALL or len(p) > 6 or not isinstance(p[5], list): return False
    sx, sy, sz = p[5]
    return sx == sz and 1.04 <= sx <= 1.5 and 0.8 <= sy <= 1.9 and abs(p[1] - 4 * round(p[1] / 4)) <= 0.7 and abs(p[2] - 4 * round(p[2] / 4)) <= 0.7


def old_rim(p):
    """the taller rim block (1 cell in 7) on an exact cell centre"""
    return p[0] == WALL and len(p) <= 6 and p[5] == [1.0, 1.5, 1.0] and p[1] % 4 == 0 and p[2] % 4 == 0


names = sorted({p[0].split("/")[-1] for p in P if "/floor_" in p[0]})
F = floor_cells(names)
new = [[WALL, x, z, rot, -cw.SINK, sc] for x, z, rot, sc in cw.pieces(F)]
out, placed, removed = [], False, 0
for p in P:
    if old_main(p) or old_rim(p):
        removed += 1
        if not placed:
            out.extend(new); placed = True
        continue
    if p[0] == WALL and len(p) > 6:                           # the rockfall doors: same height as the walls around them
        p = list(p); p[5] = [1.2, cw.HEIGHT, 1.2]; p[4] = -cw.SINK
    out.append(p)
import cave_props; cave_props.apply(out)                # prop sizes + upright stalagmites (cave_props.py)
d["pieces"] = out
import cave_secrets                                       # the two secret rooms (cave_secrets.py): lever vault + glyph-seal tomb
cave_secrets.apply(d, F, ASSET, open(os.path.join(ASSET, "tex_floor_cave.jpg"), "rb").read())
json.dump(d, open(scene, "w"), separators=(",", ":"))
print("floor cells %d | old wall blocks removed %d | new wall blocks %d | total pieces %d -> %d" % (len(F), removed, len(new), len(P), len(out)))

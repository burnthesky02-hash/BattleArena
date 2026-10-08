"""Thins the Whispering Wood's Tree_01 forest in place (visual-only trees; the tree walls are separate colliders).

Greedy random-sequential thinning with a minimum spacing that grows with distance from the walkable area (forest.json minimap rects),
so the corridor walls stay thick and the unreachable depths get sparse. Idempotent: the untouched scene is kept once as
forest.pre_thin.json and every run starts from it.   Run:  python thin_forest.py [near mid far]   (spacings in metres, default 2.8 3.6 5.0)
"""
import json
import math
import os
import random
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "forest.json")
BAK = os.path.join(HERE, "forest.pre_thin.json")
NEAR, MID, FAR = (float(a) for a in sys.argv[1:4]) if len(sys.argv) >= 4 else (2.8, 3.6, 5.0)

if not os.path.exists(BAK):
    shutil.copyfile(SRC, BAK)
raw = open(BAK, encoding="utf-8", newline="").read()
d = json.loads(raw)
rects = d["minimap"]["rects"]


def dist_walk(x, z):
    best = 1e9
    for rx, rz, rw, rd in rects:
        dx = max(rx - x, 0, x - (rx + rw)); dz = max(rz - z, 0, z - (rz + rd))
        best = min(best, math.hypot(dx, dz))
    return best


trees = [p for p in d["pieces"] if p[0].endswith("Tree_01")]
rnd = random.Random(1337)
order = list(range(len(trees)))
rnd.shuffle(order)
dm = [dist_walk(t[1], t[2]) for t in trees]
spacing = [NEAR if v < 6 else MID if v < 14 else FAR for v in dm]
cell = 6.0
grid = {}
keep = set()
for i in order:
    x, z, s = trees[i][1], trees[i][2], spacing[i]
    gx, gz = int(x // cell), int(z // cell)
    ok = True
    for a in (-1, 0, 1):
        for b in (-1, 0, 1):
            for j in grid.get((gx + a, gz + b), ()):
                if math.hypot(trees[j][1] - x, trees[j][2] - z) < s:
                    ok = False
                    break
            if not ok:
                break
        if not ok:
            break
    if ok:
        keep.add(i)
        grid.setdefault((gx, gz), []).append(i)
gone = {id(trees[i]) for i in range(len(trees)) if i not in keep}
d["pieces"] = [p for p in d["pieces"] if id(p) not in gone]
out = json.dumps(d, ensure_ascii=False, indent=1).replace("\n", "\r\n") + ("\r\n" if raw.endswith("\n") else "")
open(SRC, "w", encoding="utf-8", newline="").write(out)
print("trees %d -> %d (%.0f%%); spacing near/mid/far = %s/%s/%s" % (len(trees), len(keep), 100.0 * len(keep) / len(trees), NEAR, MID, FAR))

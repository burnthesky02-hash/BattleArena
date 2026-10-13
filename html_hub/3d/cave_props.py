"""Hollow Cave props: proportions and orientation fixes, applied to the finished piece list (used by make_cave.py and restretch_cave_walls.py).

* The hero is 2.4 m tall but the props are modelled at real-world size (a barrel is 0.7 m, a crate 0.4 m), so they looked tiny. Props are scaled up (PROP).
* SM_stalactic_0N.glb are ceiling stalactites (wide end up, point down). Standing on the floor they were upside down, so the cave uses
  SM_stalagmite_0N.glb instead: the same meshes turned 180 degrees about X (made with flipglb.py).
"""
import math

PROP = {"SM_barrel": 1.5, "SM_crate": 1.5, "SM_crate_group": 1.5, "SM_table_01": 1.5, "SM_table_chairs": 1.5, "SM_bed": 1.5, "SM_bag": 1.5,
        "SM_tent": 1.5, "SM_beam": 1.5, "SM_chair": 1.5, "SM_dg_brazier": 1.3}


def _mul(sc, k):
    return [round(v * k, 3) for v in sc] if isinstance(sc, list) else round(sc * k, 3)


def _key(name):
    for k in sorted(PROP, key=len, reverse=True):
        if name.startswith(k): return k
    return None


def apply(P):
    nm = lambda p: p[0].split("/")[-1]
    props = [p for p in P if _key(nm(p))]
    for p in P:                                              # stalactites -> stalagmites (flipped meshes)
        n = nm(p)
        if n.startswith("SM_stalactic_"): p[0] = p[0].replace("SM_stalactic_", "SM_stalagmite_")
    def under(p):                                            # the prop (if any) this piece sits on
        for q in props:
            if q is not p and p[4] > 0.05 and math.hypot(q[1] - p[1], q[2] - p[2]) < 1.0: return q
    riders = []
    for p in P:
        n = nm(p)
        if n.startswith("SM_paper") or n.startswith("SM_cv_flame"):
            q = under(p)
            if q is not None and (n.startswith("SM_paper") or p[4] >= 1.5): riders.append((p, _key(nm(q))))
    done = set()
    for p, k in riders:                                      # papers on tables, flames on braziers: move up with the thing they sit on
        p[4] = round(p[4] * PROP[k], 3); p[5] = _mul(p[5], PROP[k]); done.add(id(p))
    for p in props:
        k = _key(nm(p)); p[5] = _mul(p[5], PROP[k])
    return P

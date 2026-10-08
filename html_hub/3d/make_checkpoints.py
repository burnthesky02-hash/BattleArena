"""Save points for the long dungeons + the Colosseum-town rest stall (the defeat screen's "Return to the Inn").

Patches the *existing* scene JSONs in place (dungeon, reach, vault, outside); never regenerates them. Idempotent: every event / npc
this adds has an id starting with "cp_", and the pieces, colliders and glow decals around a camp are found again by position and
stripped before the camp is rebuilt, so running it twice gives the same file.

Run:  python make_checkpoints.py [scene ...]        (default: dungeon reach vault outside)

What a save point is: an event whose actions are  say -> {"type":"checkpoint"} -> {"type":"rest"}.  `checkpoint` (hub3d.js) stores
where the party stands and sets the flag "<restart prefix>cp" (dg_cp / rc_cp / vt_cp), so Restart Dungeon and the Waking stone drop
it. The existing rest spots (dg_rest1/2, rc_rest/rc_rest2, vt_rest) are converted in place; new ones are placed on the main route
at the nearest floor spot with clear ground (and clear of every event / npc) to the spots listed in CAMPS below.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ALL = ["dungeon", "reach", "vault", "outside"]

FIRE_SAY = "You settle by the fire and feed it a few sticks. Warmth soaks into tired limbs. This is now your save point: if the cave beats you, you will wake here."
CRYSTAL_SAY = "Soft light settles over the party. Wounds close and breath comes easy. The crystal hums and remembers this place: it is now your save point."

# scene -> kind, new camps (id suffix, label, wanted x, z); existing rest events converted in place
CAMPS = {
    "dungeon": ("fire", [("ga", "Campfire", -24, -160), ("cv", "Campfire", -4, -396), ("sh", "Campfire", -30, -578),
                         ("cr", "Campfire", 64, -704), ("an", "Campfire", 32, -800)],
                ["dg_rest1", "dg_rest2"]),
    "reach": ("crystal", [("a", "Rest crystal", 14, -80), ("b", "Rest crystal", 12, -240)], ["rc_rest", "rc_rest2"]),
    "vault": ("crystal", [("a", "Rest crystal", 6, -100), ("b", "Rest crystal", 36, -224)], ["vt_rest"]),
}


def load(name):
    p = os.path.join(HERE, name + ".json")
    raw = open(p, encoding="utf-8", newline="").read()
    return p, raw, json.loads(raw)


def save(p, raw, d):
    if raw.startswith("{\r\n") or raw.startswith("{\n"):
        out = json.dumps(d, ensure_ascii=False, indent=1)
        if raw.startswith("{\r\n"):
            out = out.replace("\n", "\r\n")
        if raw.endswith("\n"):
            out += "\r\n" if raw.startswith("{\r\n") else "\n"
    else:
        out = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(out)


def strip_camp(d, x, z):
    """drop the pieces / colliders / decals of an earlier cp_ camp whose fire is at (x, z)"""
    near = lambda a, b, r: abs(a - x) <= r and abs(b - z) <= r
    d["pieces"] = [q for q in d["pieces"] if not (near(q[1], q[2], 3.6) and ("CaveCamp" in q[0] or "SM_dg_crystal" in q[0]))]
    d["colliders"] = [c for c in d["colliders"] if not (near(c["x"], c["z"], 0.2) and c["w"] in (1.2, 2.2))]
    d["decals"] = [c for c in d["decals"] if not (c.get("cp") and abs(c["x"] - x) <= 3 and abs(c["z"] - z) <= 3)]


def floor_fn(d, kind):
    mm = d.get("minimap")
    if mm and mm.get("rects"):
        rects = mm["rects"]
        return lambda x, z: any(r[0] <= x <= r[0] + r[2] and r[1] <= z <= r[1] + r[3] for r in rects)
    fl = [(q[1], q[2]) for q in d["pieces"] if "floor" in q[0].lower()]
    grid = {}
    for fx, fz in fl:
        grid.setdefault((int(fx // 8), int(fz // 8)), []).append((fx, fz))

    def f(x, z):
        gx, gz = int(x // 8), int(z // 8)
        return any(abs(a - x) <= 4.2 and abs(b - z) <= 4.2 for i in (-1, 0, 1) for j in (-1, 0, 1) for a, b in grid.get((gx + i, gz + j), []))
    return f


def find_spot(d, kind, wx, wz, taken):
    """nearest spot to (wx, wz): floor under the camp and its event box, no collider within 3, no event / npc within 6 of the fire"""
    floor = floor_fn(d, kind)
    spots = [(e["x"], e["z"]) for e in d["events"]] + [(n["x"], n["z"]) for n in d["npcs"]] + taken
    best = None
    for dx in range(-30, 31, 1):
        for dz in range(-30, 31, 1):
            x, z = wx + dx, wz + dz
            r = math.hypot(dx, dz)
            if best and r >= best[0]:
                continue
            if not all(floor(x + a, z + b) for a in (-2, 0, 2) for b in (-2, 0, 2, 3.6)):
                continue
            if any(abs(c["x"] - x) < c["w"] / 2 + 3 and abs(c["z"] - z) < c["d"] / 2 + 3 for c in d["colliders"]):
                continue
            if any(abs(c["x"] - x) < c["w"] / 2 + 3 and abs(c["z"] - (z + 1.8)) < c["d"] / 2 + 3 for c in d["colliders"]):
                continue
            if any(math.hypot(ex - x, ez - z) < 6 for ex, ez in spots):
                continue
            best = (r, x, z)
    return (best[1], best[2]) if best else None


def fire_items(d, x, z):
    """copy of the dungeon's K1 campfire (dg_rest1) moved to (x, z)"""
    ox, oz = 48.0, -86.0
    pcs = [q for q in d["pieces"] if "CaveCamp" in q[0] and abs(q[1] - ox) < 3.6 and abs(q[2] - oz) < 3.6]
    pieces = [[q[0], round(q[1] - ox + x, 3), round(q[2] - oz + z, 3)] + q[3:] for q in pcs]
    cols = [{"x": x, "z": z, "w": 2.2, "d": 2.2}]
    decals = [{"type": "glow", "x": x, "z": z, "r": 13, "color": [1, 0.62, 0.25, 0.85]}, {"type": "glow", "x": x, "z": z, "r": 6, "color": [1, 0.8, 0.45, 0.8]}]
    return pieces, cols, decals


def crystal_items(x, z):
    return ([["/assets/3D/Dungeon/SM_dg_crystal", x, z, 40, 0, 1.2]], [{"x": x, "z": z, "w": 1.2, "d": 1.2}],
            [{"type": "glow", "x": x + 2, "z": z + 1.5, "r": 8, "color": [1, 0.8, 0.4, 0.22]}, {"type": "glow", "x": x, "z": z, "r": 7, "color": [0.4, 0.85, 1, 0.26]}])


def save_actions(kind):
    return [{"type": "say", "who": "", "text": FIRE_SAY if kind == "fire" else CRYSTAL_SAY}, {"type": "checkpoint"}, {"type": "rest"}]


def patch_dungeon_like(name):
    kind, camps, existing = CAMPS[name]
    p, raw, d = load(name)
    # undo an earlier run
    for e in [e for e in d["events"] if e["id"].startswith("cp_")]:
        strip_camp(d, e["x"], e["z"] - (3.3 if kind == "fire" else 1.4))
    d["events"] = [e for e in d["events"] if not e["id"].startswith("cp_")]
    zones = (d.get("encounters") or {}).get("zones")
    if zones is not None:
        zones[:] = [z for z in zones if not z.get("cp")]
    # convert the original rest spots
    for e in d["events"]:
        if e["id"] in existing:
            e["actions"] = save_actions(kind)
            e["prompt"] = "Rest and save at the fire" if kind == "fire" else "Rest and save at the crystal"
            e["name"] = "Campfire" if kind == "fire" else "Rest crystal"
    taken = [(e["x"], e["z"] - (3.3 if kind == "fire" else 1.4)) for e in d["events"] if e["id"] in existing]
    for sfx, label, wx, wz in camps:
        spot = find_spot(d, kind, wx, wz, taken)
        if not spot:
            print("  !! no free spot near", wx, wz, "- skipped", sfx)
            continue
        x, z = spot
        taken.append((x, z))
        pcs, cols, decals = fire_items(d, x, z) if kind == "fire" else crystal_items(x, z)
        for dc in decals:
            dc["cp"] = 1
        d["pieces"] += pcs
        d["colliders"] += cols
        d["decals"] += decals
        ev = {"id": "cp_%s_%s" % (name[:2], sfx), "name": label, "x": x, "z": z + (3.3 if kind == "fire" else 1.4),
              "w": 6 if kind == "fire" else 3, "d": 3.4 if kind == "fire" else 2.4, "trigger": "talk",
              "prompt": "Rest and save at the fire" if kind == "fire" else "Rest and save at the crystal", "actions": save_actions(kind)}
        d["events"].append(ev)
        if zones is not None:       # no ambushes at the camp (zones are matched first-wins, so these go in front)
            zones.insert(0, {"x": x, "z": z + 1, "w": 22, "d": 22, "safe": True, "cp": 1})
        print("  %s: %s at (%.1f, %.1f) [wanted %d, %d]" % (name, ev["id"], x, z, wx, wz))
    save(p, raw, d)


def patch_outside():
    p, raw, d = load("outside")
    d["npcs"] = [n for n in d["npcs"] if not n["id"].startswith("cp_")]
    d["npcs"].append({"id": "cp_inn_brea", "name": "Brea", "title": "Rest stall", "sprite": "Yulia", "x": -16.6, "z": -14, "h": 2.4, "tint": [1.1, 1, 0.9, 1],
                      "actions": [{"type": "say", "who": "Brea", "text": "Bruised? Everyone is, coming out of that gate. There is a pallet behind the awning, and the soup is hot. No charge for a fighter."},
                                  {"type": "rest"}]})
    print("  outside: cp_inn_brea at (-16.6, -14)")
    save(p, raw, d)


if __name__ == "__main__":
    for s in (sys.argv[1:] or ALL):
        print(s)
        if s == "outside":
            patch_outside()
        else:
            patch_dungeon_like(s)

"""Builds html_hub/3d/dungeon.json: the Hollow Cave under the island (claude/hollow-cave-dungeon.md). v2: a big winding cave, ~20 min to clear.
Kit: Assets/3D/CaveCamp (converted Cave_Camp meshes, see convert_cavecamp.py; procedural rock walls / water / flames / gems from gen_cave_meshes.py)
plus a few Dungeon-kit props (braziers, tablets, dais) and Kenney crates for the chests. Floors and the lake are merged into chunk GLBs written next to the kit.
Layout on a 4 m cell grid (cell i,j is centred at x=4i, z=4j; north = -z). A mostly linear route with lots of dead-end spurs:
  Entrance -> Smugglers' Camp (shop, heroes, rest) -> Gallery (puzzle 1: light the four braziers in the smugglers' order, opens the rockfall)
  -> Grotto lake (puzzle 2: three winch gems wake the causeway) -> Crystal Cavern -> Miners' Camp (three note galleries)
  -> Sigil Hall (puzzle 3: set three crystals to the colours from the notes) -> Crypt -> Antechamber (door opens when the three Seal Keepers are down) -> Sovereign's hall.
Flags: dg_* are reset by the waking stone / restart (puzzle state, guardians, boss); chests are dc_* and stay opened.
Run:  python make_cave.py [outdir]   (writes dungeon.json to outdir and the floor/lake chunks into ../../Assets/3D/CaveCamp). Re-running overwrites hand edits made in /builder3d."""
import json, math, os, random, struct, sys
from collections import deque
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glbkit import write_glb
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
HERE = os.path.dirname(os.path.abspath(__file__))
ASSET = os.path.normpath(os.path.join(HERE, "..", "..", "Assets", "3D", "CaveCamp"))
CC, DG = "/assets/3D/CaveCamp/", "/assets/3D/Dungeon/"
KEN = "/assets/3D/kenney_retro-fantasy-kit/Models/GLB format/"
CS = 4.0
rng = random.Random(8841)
P, COL, DEC, NP, EV = [], [], [], [], []
SIZES = json.load(open(os.path.join(ASSET, "sizes.json")))
def put(n, x, z, rot=0, y=0, sc=1, hide=None, pre=CC):
    p = [pre + n, round(x, 3), round(z, 3), rot, round(y, 3), sc]
    if hide: p.append(hide)
    P.append(p)
def block(x, z, w, d, hide=None):
    c = {"x": round(x, 3), "z": round(z, 3), "w": round(w, 3), "d": round(d, 3)}
    if hide: c["hideIf"] = hide
    COL.append(c)
def glow(x, z, r, c, **kw): DEC.append(dict(type="glow", x=round(x, 2), z=round(z, 2), r=r, color=c, **kw))
TORCH, ICE, VIO, GOLD = [1, .62, .25, .85], [.35, .75, 1, .8], [.7, .42, 1, .5], [1, .8, .3, .7]
def X(i): return i * CS

# ------------------------------------------------------------------ floor plan
F = {}                                     # (i,j) -> tag
LAKE = set()
R = {}                                     # name -> (i0,j0,i1,j1,kind)
def room(name, i0, j0, i1, j1, kind="room"):
    R[name] = (i0, j0, i1, j1, kind)
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1): F[(i, j)] = name
def rc(name):                              # world centre + size of a room
    i0, j0, i1, j1, _ = R[name]
    return dict(x=X((i0 + i1) / 2), z=X((j0 + j1) / 2), w=(i1 - i0 + 1) * CS, d=(j1 - j0 + 1) * CS, x0=X(i0) - 2, x1=X(i1) + 2, z0=X(j0) - 2, z1=X(j1) + 2)
room("E", -4, -5, 4, 0)
room("c1", -1, -9, 1, -6, "corr")
room("K1", -8, -19, 8, -10)
room("k1w", -14, -15, -9, -14, "corr"); room("S1", -20, -19, -15, -10)
room("k1e", 9, -15, 14, -14, "corr"); room("S2", 15, -19, 20, -10)
room("c2", -1, -26, 1, -20, "corr")
room("GA", -11, -38, 11, -27)
room("gaw", -18, -33, -12, -32, "corr"); room("GW", -25, -37, -19, -28)
room("gae", 12, -33, 18, -32, "corr"); room("GE", 19, -37, 25, -28)
room("c3", -1, -46, 1, -39, "corr")
room("GR", -14, -66, 14, -47)
for i in range(-14, 15):
    for j in range(-61, -52): LAKE.add((i, j))
room("grw", -20, -51, -15, -50, "corr"); room("RW", -27, -55, -21, -46)
room("gre", 15, -51, 20, -50, "corr"); room("RE", 21, -55, 27, -46)
room("c4", -1, -73, 1, -67, "corr")
room("CV", -10, -87, 10, -74)
room("cvw", -17, -82, -11, -81, "corr"); room("CW", -24, -86, -18, -77)
room("cve", 11, -82, 17, -81, "corr"); room("CE", 18, -86, 24, -77)
room("c5", -1, -94, 1, -88, "corr")
room("K2", -8, -108, 8, -95)
room("k2w", -14, -103, -9, -102, "corr"); room("MW", -21, -107, -15, -98)
room("k2e", 9, -103, 14, -102, "corr"); room("ME", 15, -107, 21, -98)
room("c6", -1, -117, 1, -109, "corr")
room("k6", -7, -114, -2, -113, "corr"); room("MS", -14, -116, -8, -110)
room("SH", -8, -130, 8, -118)
room("c7", -1, -137, 1, -131, "corr")
room("CR", -12, -158, 12, -138)
room("crw", -18, -150, -13, -149, "corr"); room("PW", -25, -154, -19, -145)
room("cre", 13, -150, 18, -149, "corr"); room("PE", 19, -154, 25, -145)
room("c8", -1, -164, 1, -159, "corr")
room("AN", -5, -172, 5, -165)
room("c9", -1, -176, 1, -173, "corr")
room("BH", -10, -194, 10, -177)
room("h1", 21, -15, 40, -14, "corr"); room("A1", 41, -19, 46, -10)          # long hall east of the camp's east stash -> winch gem 2
room("h2", -45, -33, -26, -32, "corr"); room("A2", -51, -37, -46, -28)      # long hall west of the Gallery's west room -> winch gem 1
room("h3", 28, -51, 47, -50, "corr"); room("A3", 48, -55, 53, -46)          # long hall east of the Grotto's east room -> winch gem 3
SPAWN = (0, -4.0)
GATE_A, GATE_S, GATE_B = -41, -134, -174       # rows of the three doors (all across cols -1..1)
BRIDGE = (-1, 1)                                # lane columns of the causeway
assert not (set(F) & set()), "overlap check below"
# nothing may touch unintentionally: every room tag must keep its own cells (rooms were written in order, later overwrite earlier)
for name, (i0, j0, i1, j1, _) in R.items():
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1): assert F[(i, j)] == name, ("rooms overlap", name, (i, j), F[(i, j)])
# a floor cell that touches another room's cell by edge is fine only along the intended joints; check that every room touches exactly the expected neighbours
JOINTS = {("E", "c1"), ("c1", "K1"), ("K1", "k1w"), ("k1w", "S1"), ("K1", "k1e"), ("k1e", "S2"), ("K1", "c2"), ("c2", "GA"), ("GA", "gaw"), ("gaw", "GW"), ("GA", "gae"), ("gae", "GE"), ("GA", "c3"),
          ("c3", "GR"), ("GR", "grw"), ("grw", "RW"), ("GR", "gre"), ("gre", "RE"), ("GR", "c4"), ("c4", "CV"), ("CV", "cvw"), ("cvw", "CW"), ("CV", "cve"), ("cve", "CE"), ("CV", "c5"), ("c5", "K2"),
          ("K2", "k2w"), ("k2w", "MW"), ("K2", "k2e"), ("k2e", "ME"), ("K2", "c6"), ("c6", "k6"), ("k6", "MS"), ("c6", "SH"), ("SH", "c7"), ("c7", "CR"), ("CR", "crw"), ("crw", "PW"),
          ("CR", "cre"), ("cre", "PE"), ("S2", "h1"), ("h1", "A1"), ("GW", "h2"), ("h2", "A2"), ("RE", "h3"), ("h3", "A3"), ("CR", "c8"), ("c8", "AN"), ("AN", "c9"), ("c9", "BH")}
touch = set()
for (i, j), t in F.items():
    for n in ((i + 1, j), (i, j + 1)):
        if n in F and F[n] != t: touch.add(tuple(sorted((t, F[n]))))
assert touch == {tuple(sorted(j)) for j in JOINTS}, (touch ^ {tuple(sorted(j)) for j in JOINTS})

# ---- organic edges: chamfer the corners of every room and push a few lobes out of its sides (only where no other room is within a cell)
crg = random.Random(77)
def foreign_near(c, tag):
    return any(F.get((c[0] + a, c[1] + b), tag) != tag for a in (-1, 0, 1) for b in (-1, 0, 1))
for name, (i0, j0, i1, j1, kind) in list(R.items()):
    if kind != "room" or name == "GR": continue
    w, h = i1 - i0 + 1, j1 - j0 + 1
    k = 3 if min(w, h) >= 12 else 2
    for (ci, cj, si, sj) in ((i0, j0, 1, 1), (i1, j0, -1, 1), (i0, j1, 1, -1), (i1, j1, -1, -1)):
        kk = crg.choice([k, k - 1]) if k > 1 else 1
        for a in range(kk):
            for b in range(kk - a): F.pop((ci + si * a, cj + sj * b), None)
    for side in ("n", "s", "w", "e"):
        if (w if side in "ns" else h) < 9: continue
        for _ in range(crg.choice([1, 2])):
            ln = crg.randint(3, min(7, (w if side in "ns" else h) - 4)); dp = crg.choice([1, 1, 2])
            st = crg.randint(2, (w if side in "ns" else h) - ln - 2)
            for a in range(ln):
                for b in range(1, dp + 1):
                    c = {"n": (i0 + st + a, j0 - b), "s": (i0 + st + a, j1 + b), "w": (i0 - b, j0 + st + a), "e": (i1 + b, j0 + st + a)}[side]
                    back = {"n": (c[0], c[1] + 1), "s": (c[0], c[1] - 1), "w": (c[0] + 1, c[1]), "e": (c[0] - 1, c[1])}[side]
                    if back not in F or c in F or foreign_near(c, name) or any((c[0] + p, c[1] + q) in F and F[(c[0] + p, c[1] + q)] != name for p in (-2, -1, 0, 1, 2) for q in (-2, -1, 0, 1, 2)): break
                    F[c] = name
touch2 = set()
for (i, j), t in F.items():
    for n in ((i + 1, j), (i, j + 1)):
        if n in F and F[n] != t: touch2.add(tuple(sorted((t, F[n]))))
assert touch2 == touch, touch2 ^ touch

# ------------------------------------------------------------------ walls, fence, floor chunks
blocked = set()
for (i, j) in F:
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            if (i + di, j + dj) not in F: blocked.add((i + di, j + dj))
wallc = {c for c in blocked if any((c[0] + di, c[1] + dj) in F for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
GATE_CELLS = {(i, j) for j in (GATE_A, GATE_S, GATE_B) for i in (-1, 0, 1)}
for c in sorted(wallc):
    h = (c[0] * 73856093 ^ c[1] * 19349663) & 0xFFFF
    put("SM_cv_wall_" + "abc"[h % 3], X(c[0]), X(c[1]), (0, 90, 180, 270)[(h >> 4) % 4], 0, 1.0 + ((h >> 8) % 5) * .04)
rows = {}
for (i, j) in blocked: rows.setdefault(j, []).append(i)
for j, xs in rows.items():
    xs.sort(); s = prev = xs[0]
    for x in xs[1:] + [None]:
        if x is None or x != prev + 1:
            block(X((s + prev) / 2), X(j), (prev - s + 1) * CS, CS); s = x
        if x is not None: prev = x
def glb_image(path):
    b = open(path, "rb").read(); jl = struct.unpack("<I", b[12:16])[0]; js = json.loads(b[20:20 + jl]); bl = struct.unpack("<I", b[20 + jl:24 + jl])[0]
    bin0 = 20 + jl + 8; bv = js["bufferViews"][js["images"][0]["bufferView"]]
    return b[bin0 + bv["byteOffset"]: bin0 + bv["byteOffset"] + bv["byteLength"]]
FLOOR_IMG = open(os.path.join(ASSET, "tex_floor.jpg"), "rb").read()
WATER_IMG = glb_image(os.path.join(ASSET, "SM_cv_water.glb"))
def quads(cells, y, uvs):
    pos, uv, idx = [], [], []
    for (i, j) in sorted(cells):
        x0, x1, z0, z1 = X(i) - 2, X(i) + 2, X(j) - 2, X(j) + 2; o = len(pos)
        pos += [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]; uv += [(x0 / uvs, z0 / uvs), (x1 / uvs, z0 / uvs), (x1 / uvs, z1 / uvs), (x0 / uvs, z1 / uvs)]
        idx += [(o, o + 3, o + 1), (o + 1, o + 3, o + 2)]
    return np.array(pos, np.float32), np.tile([0, 1, 0], (len(pos), 1)).astype(np.float32), np.array(uv, np.float32), idx
os.makedirs(ASSET, exist_ok=True)
for fn in os.listdir(ASSET):
    if fn.startswith("floor_") and fn.endswith(".glb"): os.remove(os.path.join(ASSET, fn))
chunks = {}
for c in F:
    if c not in LAKE: chunks.setdefault((c[0] // 16, c[1] // 16), []).append(c)
for (ci, cj), cells in sorted(chunks.items()):
    p, n, uv, idx = quads(cells, 0.0, 6.0); nm = "floor_%d_%d" % (ci, cj)
    write_glb(os.path.join(ASSET, nm + ".glb"), p, n, idx, nm, uv=uv, img=FLOOR_IMG, color=(.6, .56, .54, 1))
    put(nm, 0, 0, 0, 0, 1)
p, n, uv, idx = quads(LAKE, -1.5, 6.0)
write_glb(os.path.join(ASSET, "floor_lakebed.glb"), p, n, idx, "floor_lakebed", uv=uv, img=FLOOR_IMG, color=(.28, .4, .5, 1)); put("floor_lakebed", 0, 0, 0, 0, 1)
p, n, uv, idx = quads(LAKE, -0.35, 2.0)
write_glb(os.path.join(ASSET, "floor_lake.glb"), p, n, idx, "floor_lake", uv=uv, img=WATER_IMG, color=(1, 1, 1, .78), alpha="BLEND", double=True); put("floor_lake", 0, 0, 0, 0, 1)
# the lake itself is impassable except on the causeway lane
lk = rc("GR"); lz0, lz1 = X(-61) - 2, X(-53) + 2
LX0, LX1 = X(-14) - 2, X(14) + 2
block((LX0 - 4.8) / 2, (lz0 + lz1) / 2, -4.8 - LX0, lz1 - lz0)
block((4.8 + LX1) / 2, (lz0 + lz1) / 2, LX1 - 4.8, lz1 - lz0)
BR_SPEC = "dg_pb_1,dg_pb_2,dg_pb_3"
block(0, (lz0 + lz1) / 2, 9.6, lz1 - lz0, BR_SPEC)
for j in range(-61, -52):
    for px in (-2.25, 2.25): put("SM_floor_plank_01", px, X(j), 0, 0.08, 1.05, "S:" + BR_SPEC)

# ------------------------------------------------------------------ props
OCC = []                                   # reserved circles (x, z, r) so scatter never blocks an event or NPC
def reserve(x, z, r=3.2): OCC.append((x, z, r))
def free(x, z, r=1.0): return all(math.hypot(x - a, z - b) > rr + r for a, b, rr in OCC)
def box_prop(n, x, z, rot=0, y=0, sc=1.0, hide=None, coll=True, shrink=.9):
    s = SIZES[n]; put(n, x, z, rot, y, sc, hide)
    if coll: w, d = (s[0], s[2]) if rot % 180 == 0 else (s[2], s[0]); block(x, z, max(.5, w * sc * shrink), max(.5, d * sc * shrink), hide)
def brazier(x, z, rad=7.0, col=TORCH):
    put("SM_dg_brazier", x, z, 0, 0, 1.0, pre=DG); put("SM_cv_flame_gold", x, z, 0, 1.55, 1.0); block(x, z, 1.1, 1.1); glow(x, z, rad, col); reserve(x, z, 1.5)
def tablet(key, name, x, z, rot, text, who="Carved Tablet", ex=0, ez=1.9):
    put("SM_dg_tablet", x, z, rot, 0, 1.0, pre=DG); block(x, z, 1.6 if rot % 180 == 0 else .5, .5 if rot % 180 == 0 else 1.6)
    EV.append(dict(id=key, name=name, x=round(x + ex, 2), z=round(z + ez, 2), w=3.4, d=2.6, trigger="talk", prompt="Read the tablet", actions=[dict(type="say", who=who, text=text)])); reserve(x + ex, z + ez, 2)
def note(key, name, x, z, text, who="Torn page", table=True):
    if table: box_prop("SM_table_01", x, z, 0)
    put("SM_paper_02", x - .3, z, 20, .72, 1.6); put("SM_paper_03", x + .35, z + .1, -30, .72, 1.6)
    EV.append(dict(id=key, name=name, x=round(x, 2), z=round(z + 1.5, 2), w=3.6, d=2.8, trigger="talk", prompt="Read the page", actions=[dict(type="say", who=who, text=text)])); reserve(x, z + 1.5, 2.2)
ENAME = {"blue": "Tide Ember", "red": "Hearth Ember", "gold": "Sun Ember", "green": "Moss Ember"}
def ember(col, x, z, where_text):
    put("SM_rock_01", x, z, rng.choice([0, 90]), 0, 1.1); put("SM_cv_gem_" + col, x, z, 0, .95, 1.6, "dg_pi_" + col); block(x, z, 1.2, 1.2)
    glow(x, z, 7, {"blue": [.35, .65, 1, .7], "red": [1, .4, .2, .7], "gold": [1, .8, .3, .7], "green": [.35, 1, .55, .7]}[col], hideIf="dg_pi_" + col)
    EV.append(dict(id="dg_pi_ev_" + col, name=ENAME[col], x=round(x, 2), z=round(z + 2.0, 2), w=3.4, d=2.8, trigger="talk", prompt="Take the " + ENAME[col], hideIf="dg_pi_" + col,
                   actions=[dict(type="say", who="", text=where_text + " You take the %s. It is warm, and it hums faintly." % ENAME[col]), dict(type="flag", key="dg_pi_" + col)]))
    reserve(x, z + 2.0, 2.4)
def npc(**kw): kw.setdefault("h", 2.4); kw.setdefault("reach", 4.6); NP.append(kw); reserve(kw["x"], kw["z"], 2)
LOOT_ITEMS = {1: ["potion", "antidote", "potion"], 2: ["potion", "hi_potion", "ether", "antidote"], 3: ["hi_potion", "ether", "phoenix_down", "hi_potion"]}
RARE_EQ = ["knights_blade", "falcon_saber", "war_hatchet", "bearded_cleaver", "chapel_mace", "twinfang_daggers", "serrated_kris", "longshot_bow", "hawkeye_recurve", "crystal_staff", "emberwood_staff", "moonlit_wand",
           "chorister_wand", "tome_of_mending", "gilded_hymnal", "bulwark_shield", "parrying_buckler", "swift_quiver", "crystal_focus", "armor_light_rare", "armor_medium_rare", "armor_heavy_rare",
           "helm_light_rare", "helm_medium_rare", "helm_heavy_rare", "boots_light_rare", "boots_medium_rare", "boots_heavy_rare", "sages_ring", "gladiators_signet", "ring_of_swift_feet"]
EPIC_EQ = ["warshard", "blade_of_the_underdog", "aegis_mace", "nightfall_fang", "stormcaller_bow", "staff_of_the_tempest", "wand_of_the_faithful", "aegis_shield", "windrunner_quiver", "band_of_vigor", "talisman_of_the_veteran"]
def make_loot(tier, rg):
    r = rg.random(); loot = {}; gold = {1: (90, 260), 2: (200, 480), 3: (380, 800)}[tier]
    if r < .40: loot["gold"] = rg.randrange(gold[0], gold[1], 10)
    elif r < .66:
        loot["items"] = {rg.choice(LOOT_ITEMS[tier]): rg.randint(2, 4)}
        if rg.random() < .5: loot["items"][rg.choice(LOOT_ITEMS[tier])] = rg.randint(1, 3)
        loot["gold"] = rg.randrange(gold[0] // 3, gold[1] // 3, 10)
    elif r < .82: loot["gems"] = rg.randint(*{1: (3, 8), 2: (6, 14), 3: (12, 26)}[tier]); loot["gold"] = rg.randrange(gold[0] // 3, gold[1] // 3, 10)
    else:
        loot["equipment"] = [rg.choice(EPIC_EQ if (tier == 3 and rg.random() < .3) else RARE_EQ)]; loot["shards"] = rg.randint(2, 8) * tier
    return loot
CHESTS = []
def chest(x, z, tier, rot=None):
    key = "dc_%d" % (len(CHESTS) + 1); rot = rng.choice([0, 90, 180, 270]) if rot is None else rot; CHESTS.append((key, x, z, tier))
    put("detail-crate", x, z, rot, 0, 5.0, key, pre=KEN); put("detail-crate-small", x, z, rot, 0, 5.0, "!" + key, pre=KEN); block(x, z, 1.6, 1.6)
    EV.append(dict(id=key, name="Treasure chest", x=round(x, 2), z=round(z, 2), w=4.2, d=4.2, trigger="talk", prompt="Open the chest", hideIf=key,
                   actions=[dict(type="flag", key=key), dict(type="chest", loot=make_loot(tier, rng))])); reserve(x, z, 2.4)

# ---- doors (a rockfall of rock blocks + rubble that vanishes when the way opens)
def rockfall(row, key, glowcol=None):
    z = X(row)
    for i in (-1, 0, 1):
        put("SM_cv_wall_" + "abc"[(i + 1) % 3], X(i), z, 90 * (i + 1), 0, 1.0, key, pre=CC)
    block(0, z, 12, 4, key)
    for dx, nm in ((-4.3, "SM_rock_02"), (3.6, "SM_rock_03"), (0.4, "SM_rock_01")): put(nm, dx, z + 2.6, rng.choice([0, 90, 180]), 0, 1.4, key)
    if glowcol: DEC.append(dict(type="glyph", x=0, z=round(z + 2.4, 2), r=4.0, spin=20, color=glowcol, hideIf=key))

# ------------------------------------------------------------------ 1. Entrance
e = rc("E")
for sx in (-1, 1): brazier(sx * 13.5, -17.5, 8)
brazier(-13.5, -2.5, 6); brazier(13.5, -2.5, 6)
tablet("dg_entry_tablet", "Entrance tablet", -9, -19, 0, "THE HOLLOW CAVE. BENEATH ITS FLOORS THE COURT OF THE DROWNED SOVEREIGN WAS LAID TO REST. THOSE WHO DISTURB IT WILL BE MET IN KIND.")
put("SM_dg_block", 9.2, -6.5, 0, 0, 1.1, pre=DG); block(9.2, -6.5, 1.2, 1.2); glow(9.2, -6.5, 6, ICE)
EV.append(dict(id="dg_altar", name="Waking stone", x=9.2, z=-5.0, w=3.0, d=2.4, trigger="talk", prompt="Touch the stone",
               actions=[dict(type="say", who="Waking Stone", text="The stone is warm. You feel the cave stir: every guardian you felled stands again, every lamp goes dark, and the sealed ways close behind you."),
                        dict(type="reset_progress", prefix="dg_")])); reserve(9.2, -5.0, 2)
EV.append(dict(id="dg_exit", name="Back to the island", x=0, z=0.6, w=8, d=2.2, trigger="touch", once=False, actions=[dict(type="warp", scene="island", x=0, z=-39.5)]))
for sx in (-1, 1): box_prop("SM_barrel_02", sx * 6.5, -17.8, 0); box_prop("SM_crate_01", sx * 5.6, -16.8, 20)
glow(0, -10, 12, [.5, .6, .8, .22])
reserve(0, -4, 3); reserve(0, 0, 6)

# ------------------------------------------------------------------ 2. Smugglers' Camp (K1)
def campfire(x, z, key):
    for k in range(7):
        a = k / 7 * math.tau; put("SM_small_rock_0%d" % (1 + k % 2), x + math.cos(a) * 1.15, z + math.sin(a) * 1.15, k * 50, 0, 3.4)
    put("SM_cv_flame_gold", x, z, 0, .35, 1.5); put("SM_cv_flame_red", x, z, 45, .2, 1.1); block(x, z, 2.2, 2.2); glow(x, z, 13, TORCH); glow(x, z, 6, [1, .8, .45, .8])
    EV.append(dict(id=key, name="Campfire", x=x, z=z + 3.3, w=6, d=3.4, trigger="talk", prompt="Rest by the fire",
                   actions=[dict(type="say", who="", text="You settle by the fire. Warmth soaks into tired limbs, and for a moment the cave is only a quiet room."), dict(type="rest")])); reserve(x, z + 3.3, 3.5)
campfire(0, -58, "dg_rest1")
box_prop("SM_tent_01", -22, -70, 0); box_prop("SM_tent_02", 22, -70, 0); box_prop("SM_tent_08", -29.5, -52, 90); box_prop("SM_tent_06", 29.5, -52, 90)
box_prop("SM_table_chairs", -14, -48, 0); box_prop("SM_table_group_04", 13, -66, 180)
for k, (dx, dz) in enumerate(((0, 0), (1.5, .4), (.5, 1.5))): box_prop("SM_barrel_0%d" % (1 + k % 4), -27 + dx, -44.5 + dz, 30 * k)
box_prop("SM_crate_group_02", 22, -43.5, 0); box_prop("SM_crate_group_01", -27, -62, 90); box_prop("SM_crate_02", 8, -44, 10)
box_prop("SM_bag", 26.5, -62, 40, coll=False); box_prop("SM_bottle", 12.5, -66.2, 0, .93, 2.0, coll=False)
for (x, z) in ((-8, -74), (8, -74), (-24, -45), (24, -45)): brazier(x, z, 8)
note("dg_log", "Smugglers' log", 14, -48, "'...the Captain had us light the Gallery lamps with the four embers, in the old order, or the roof comes down on the lot of us. Tide first, always. Then the hearth. Then the sun. Moss last. One ember to a lamp, and the lamps bite if you get it wrong. We hid the embers in the stashes round the cave so no one could do it by accident. Hope nobody does.' The rest is smeared with grease.", "Smuggler's log")
npc(id="dg_shop1", name="Pell", title="Cave fence", sprite="Kael", x=-9.5, z=-60, tint=[.7, .7, .95, 1], line="Psst. Everything here was found, not stolen. Browse?", action="shop")
npc(id="dg_hero1", name="Captain Merrow", title="Sellsword", sprite="Sera", x=9.5, z=-60.5, tint=[1.1, .95, .9, 1], line="Coin buys steel, steel buys time. Looking to hire?", action="heroes")
npc(id="dg_sera", name="Sera", title="Chapel healer", sprite="Sera", x=5.4, z=-56, tint=[1, 1.05, 1.15, 1], hideIf="st_sera", line="", actions=[
    {'type': 'say', 'who': 'Sera', 'text': 'Easy. I am not a smuggler, and I am not one of the drowned either. My name is Sera. I am a healer from the Tide Chapel on the mainland.'},
    {'type': 'say', 'who': 'Sera', 'text': "The chapel's records say a king was laid to rest in this cave with his whole court sealed in beside him, still waiting on a tide that never came. Someone ought to see them to rest. I came to do that. I did not expect the cave to be full of bandits."},
    {'type': 'say', 'who': 'Sera', 'text': 'I have been camped here three days, waiting for someone who can actually swing a sword. A village girl came through before that, with a sack and a lantern, asking the way to the moonglow moss. I told her to turn back. I do not think she did.'},
    {'type': 'say', 'who': 'Sera', 'text': "If she went deeper, she is behind the same sealed doors as the court. Please, let me walk with you. I am no fighter, but I can keep you standing, and I know how the Chapel's seals are meant to be undone."},
    {'type': 'say', 'who': '', 'text': 'Sera takes up her staff and falls in beside you. She joins your party! Equip her before you head on.'},
    {'type': 'recruit', 'name': 'Sera'},
    {'type': 'flag', 'key': 'st_sera'}])
npc(id="dg_smug1", name="Old Dov", title="Smuggler", sprite="Rook", x=-3.6, z=-52, tint=[.75, .75, .7, 1], line="", actions=[
    dict(type="say", who="Old Dov", text="Gallery's north of here, past the long hall. The lamps in there want four embers, and the embers are hid in the side rooms. Don't light 'em wrong; the lamps bite."),
    dict(type="say", who="Old Dov", text="Captain kept a log on the table by the crates. Read it before you touch a thing.")])
# S1 / S2: the camp's stash rooms
chest(X(-17.5), X(-15.5), 1); put("SM_barrel_03", X(-18.6), X(-12.5), 0); block(X(-18.6), X(-12.5), .8, .8)
box_prop("SM_crate_group_01", X(-19), X(-17.8), 90); box_prop("SM_bed", X(-16.5), X(-11.5), 90)
tablet("dg_t_s1", "Scratched wall", X(-17.5), X(-19) + .9, 0, "'DOV WAS HERE. DOV WAS ALSO HERE FIRST.'", "Scratched into the rock")
chest(X(17.5), X(-17), 1); box_prop("SM_barrel_01", X(19), X(-14), 0); box_prop("SM_crate_03", X(16.4), X(-11.6), 90)
note("dg_n_s2", "Wet journal", X(17.8), X(-12.2), "'Hid the good rum in the east stash. Hid the better rum under it. Do not tell Dov about the best rum.'", "Journal")
glow(X(-17.5), X(-14.5), 6, TORCH); glow(X(17.5), X(-14.5), 6, TORCH)
ember("blue", X(-16.2), X(-16.2), "In a crack at the back of the west stash a pale-blue stone glows.")
ember("red", X(16.4), X(-17.6), "Under a pile of rags in the east stash, a red cinder pulses.")

# ------------------------------------------------------------------ 3. Gallery (puzzle 1: the four braziers)
SEQ = ["blue", "red", "gold", "green"]
POSG = [("red", -24), ("green", -8), ("blue", 8), ("gold", 24)]
FLC = {"blue": [.35, .65, 1, .9], "red": [1, .4, .2, .9], "gold": [1, .8, .3, .9], "green": [.35, 1, .55, .9]}
for col, x in POSG:
    z = -141.5; idx = SEQ.index(col)
    put("SM_dg_brazier", x, z, 0, 0, 1.15, pre=DG); block(x, z, 1.3, 1.3)
    put("SM_cv_gem_" + col, x, z + 1.55, 0, .35, 1.4)                                  # always visible: tells which brazier this is
    put("SM_cv_flame_" + col, x, z, 0, 1.75, 1.4, "S:dg_pa_%d" % (idx + 1)); glow(x, z, 9, FLC[col], showIf="dg_pa_%d" % (idx + 1))
    pi = "dg_pi_" + col
    for n in range(5):
        spec = ("dg_pa_%d,!dg_pa_%d" % (n, n + 1)) if 0 < n < 4 else ("!dg_pa_1" if n == 0 else "dg_pa_4")
        def addev(tag, sp, acts, prompt):
            EV.append(dict(id="dg_pa_%s_%d%s" % (col, n, tag), name="%s lamp" % col.capitalize(), x=x, z=z + 3.0, w=4.4, d=3.4, trigger="talk", prompt=prompt, showIf=sp, actions=acts))
        if n == 4: addev("", spec, [dict(type="say", who="", text="The %s lamp burns steadily. The way north stands open." % col)], "Look at the %s lamp" % col)
        elif idx < n: addev("", spec, [dict(type="say", who="", text="The %s lamp is already burning." % col)], "Look at the %s lamp" % col)
        else:
            addev("n", spec + ",!" + pi, [dict(type="say", who="", text="The lamp is cold and empty. You have no %s to set in it." % ENAME[col])], "Inspect the %s lamp" % col)
            if idx == n and n == 3: ok = [dict(type="say", who="", text="You set the %s in the last lamp. It catches, and a long groan rolls through the Gallery as the rockfall to the north shudders aside." % ENAME[col]), dict(type="flag", key="dg_pa_4")]
            elif idx == n: ok = [dict(type="say", who="", text="You set the %s in the lamp. The flame catches and burns steady." % ENAME[col]), dict(type="flag", key="dg_pa_%d" % (n + 1))]
            else: ok = [dict(type="say", who="", text="You set the %s in the lamp. It shrieks, every lit lamp gutters out, and something answers from the dark!" % ENAME[col]), dict(type="unflag", prefix="dg_pa_"),
                        dict(type="battle", key="", pool=["stone_gargoyle", "bandit_rogue", "dark_cultist"], level=[4, 5])]
            addev("y", spec + "," + pi, ok, "Set the %s in the lamp" % ENAME[col])
    reserve(x, z + 3.0, 3)
tablet("dg_t_ga", "Gallery tablet", 0, -149.4, 0, "FOUR LAMPS, FOUR EMBERS. THE EMBERS ARE HIDDEN IN THE SIDE ROOMS OF THE CAVE. CARRY THEM HERE AND SET THEM IN THE ORDER THE SMUGGLERS KEPT. A WRONG LAMP PUTS ALL FOUR OUT AND WAKES WHAT SLEEPS IN THE WALLS.")
rockfall(GATE_A, "dg_pa_4", [1, .6, .3, 1])
for x in (-36, 36):                                                         # pillars of rock lining the hall
    for z in (-130, -118):
        put("SM_stalactic_0%d" % (4 if x < 0 else 7), x, z, rng.choice([0, 90]), 0, .55); block(x, z, 2.2, 2.2); reserve(x, z, 2)
glow(0, -125, 16, [.55, .7, 1, .22])
for (x, z) in ((-16, -112), (16, -112), (-36, -146), (36, -146)): brazier(x, z, 8)
# west room: bridge gem 3 + chest. east room: the Gallery Warden
NP_G = {}
def guardian(key, name, title, sprite, tint, x, z, line, pool, level, h=2.8):
    npc(id=key, name=name, title=title, sprite=sprite, x=round(x, 2), z=round(z, 2), h=h, tint=tint, hideIf=key, reach=5.2,
        actions=[dict(type="say", who=name, text=line), dict(type="battle", key=key, pool=pool, level=level)])
    glow(x, z, 10, [1, .45, .3, .5], hideIf=key)
def gem_switch(n, x, z, where):
    put("SM_dg_dais", x, z, 0, 0, .55, pre=DG); block(x, z, 1.6, 1.6)
    put("SM_cv_crystal_off", x, z, 0, .4, 1.1, "dg_pb_%d" % n); put("SM_cv_crystal_blue", x, z, 0, .4, 1.1, "S:dg_pb_%d" % n); glow(x, z, 7, ICE, showIf="dg_pb_%d" % n)
    EV.append(dict(id="dg_pb_off_%d" % n, name="Winch gem", x=x, z=z + 2.2, w=3.4, d=2.6, trigger="talk", prompt="Press the gem", showIf="!dg_pb_%d" % n,
                   actions=[dict(type="say", who="", text="The gem sinks under your palm and glows a deep blue. Somewhere far off, stone grinds on stone."), dict(type="flag", key="dg_pb_%d" % n)]))
    EV.append(dict(id="dg_pb_on_%d" % n, name="Winch gem", x=x, z=z + 2.2, w=3.4, d=2.6, trigger="talk", prompt="Look at the gem", showIf="dg_pb_%d" % n,
                   actions=[dict(type="say", who="", text="The gem hums. One of the causeway's three winches is awake.")])); reserve(x, z + 2.2, 2.5)
gw = rc("GW"); ge = rc("GE")
ember("gold", gw["x"] + 3, gw["z"] - 6, "On a ledge in the Gallery's west room a golden stone glows."); chest(gw["x"] + 5, gw["z"] + 3, 1)
for k, (dx, dz) in enumerate(((-6, 6), (6, -6), (-7, -5))):
    if free(gw["x"] + dx, gw["z"] + dz): put("SM_stalactic_0%d" % (2 + k), gw["x"] + dx, gw["z"] + dz, 40 * k, 0, .5); block(gw["x"] + dx, gw["z"] + dz, 1.4, 1.4)
glow(gw["x"], gw["z"], 9, ICE)
guardian("dg_g1", "Gallery Warden", "Seal Keeper", "Draven", [.8, .85, 1.25, 1], ge["x"] + 2, ge["z"] - 3,
         "...the first seal... is mine to keep. Let the dead king's gate stay shut.", ["stone_gargoyle", "goblin_skirmisher"], 5)
brazier(ge["x"] - 6, ge["z"] + 7, 8); brazier(ge["x"] + 6, ge["z"] + 7, 8)
chest(ge["x"] + 6, ge["z"] - 6, 2)
ember("green", ge["x"] - 5, ge["z"] - 1, "Behind where the Warden stood, a green stone glows in the moss.")
tablet("dg_t_ge", "Carved tablet", ge["x"] - 4, ge["z"] - 8.9, 0, "THE FIRST SEAL IS KEPT BY THE GALLERY'S WARDEN. IT HAS STOOD HERE SO LONG THE ROCK HAS GROWN OVER ITS FEET.")

# ------------------------------------------------------------------ 4. Grotto (puzzle 2: three winch gems wake the causeway)
for x in (-9, 9):
    brazier(x, X(-47) - 2.5, 8)
tablet("dg_t_gr", "Grotto tablet", 0, X(-47) - 1, 0, "THE CAUSEWAY SLEEPS BENEATH THE WATER. THREE WINCH-GEMS RAISE IT. EACH WAS SET AT THE FAR END OF A LONG HALL: ONE BEYOND THE CAMP'S EAST STASH, ONE BEYOND THE GALLERY'S WEST ROOM, AND ONE BEYOND THE LAKE'S EAST BANK.")
rw = rc("RW"); re_ = rc("RE")
chest(rw["x"] + 3, rw["z"] + 5, 1); chest(rw["x"] - 3, rw["z"] - 5, 2); glow(rw["x"], rw["z"], 9, ICE)
chest(re_["x"] - 3, re_["z"] + 5, 2); glow(re_["x"], re_["z"], 9, ICE)
for (nm, n, side, txt) in (("A2", 1, -1, "THE WEST WINCH. THE GALLERY'S MASTERS WANTED THE LAKE RAISED ONLY BY THOSE WILLING TO WALK TO THE END OF THE WORLD."),
                           ("A1", 2, 1, "THE EAST WINCH, BEYOND THE SMUGGLERS' STASH. THE SMUGGLERS NEVER FOUND IT; THEY NEVER LOOKED PAST THE RUM."),
                           ("A3", 3, 1, "THE LAKE WINCH. THE LONGEST HALL FOR THE LAST GEM.")):
    a_ = rc(nm); sx = a_["x1"] - 4 if side > 0 else a_["x0"] + 4
    gem_switch(n, sx, a_["z"] - 6, nm); glow(a_["x"], a_["z"], 10, ICE); chest(sx - side * 4, a_["z"] + 8, 2)
    brazier(sx - side * 8, a_["z"] + 11, 8, ICE); tablet("dg_t_w%d" % n, "Winch tablet", sx - side * 8, a_["z"] - 12.5, 0, txt)
for (x, z, nm) in ((-48, X(-50), "SM_stalactic_03"), (48, X(-50), "SM_stalactic_01"), (-52, X(-63), "SM_stalactic_06"), (52, X(-64), "SM_stalactic_06")):
    if free(x, z): put(nm, x, z, rng.choice([0, 90]), 0, .6); block(x, z, 1.6, 1.6)
for k in range(6): glow(rng.uniform(-50, 50), X(rng.uniform(-60, -54)), 12, [.3, .6, .9, .08])
glow(0, X(-57), 22, [.3, .65, 1, .08])
tablet("dg_t_far", "Far shore tablet", -6, X(-66) + 2.4, 0, "THE WATER IS COLD AND DEEPER THAN IT LOOKS. THE KING'S MEN WERE ALL GOOD SWIMMERS. THEY ARE STILL DOWN THERE.", ez=2.2)

# ------------------------------------------------------------------ 5. Crystal Cavern and its spurs
cv = rc("CV")
CRC = ["blue", "violet", "white", "green", "gold"]
for k in range(10):
    a = rng.uniform(0, math.tau); r_ = rng.uniform(15, 33)
    x, z = cv["x"] + math.cos(a) * r_ * 1.2, cv["z"] + math.sin(a) * r_ * .5
    if abs(x) < 8 and True: x += 14 * (1 if x >= 0 else -1)
    if free(x, z, 1.5) and abs(x) < cv["w"] / 2 - 4 and abs(z - cv["z"]) < cv["d"] / 2 - 3:
        c_ = rng.choice(CRC); put("SM_cv_crystal_" + c_, x, z, rng.randint(0, 359), 0, 1.9); block(x, z, 1.5, 1.5); glow(x, z, 9, {"blue": ICE, "violet": VIO, "white": [.9, .95, 1, .6], "green": [.4, 1, .6, .6], "gold": GOLD}[c_]); OCC.append((x, z, 1.5))
glow(cv["x"], cv["z"], 24, [.5, .6, 1, .2])
tablet("dg_t_cv", "Cavern tablet", -7, cv["z"] + cv["d"] / 2 - .9, 180, "THE CRYSTALS SING WHEN THE SEA IS HIGH. THE MINERS CAME FOR THEIR SONG AND LEFT THEIR DEAD BEHIND.", ez=-2.0)
cw = rc("CW"); ce = rc("CE")
chest(cw["x"] - 2, cw["z"] - 4, 2); chest(cw["x"] + 4, cw["z"] + 4, 2)
for k in range(5): c_ = rng.choice(CRC); put("SM_cv_crystal_" + c_, cw["x"] + rng.uniform(-8, 8) , cw["z"] + rng.uniform(-8, 8), rng.randint(0, 359), 0, 1.7)
note("dg_n_cw", "Prospector's slate", cw["x"] - 2, cw["z"] + 6.5, "'West shaft is a dead end. Do not let them tell you otherwise. Left a nice big chest for whoever digs through. Be kind. - H.'", "Slate")
guardian("dg_g2", "Cavern Lurker", "Seal Keeper", "Rook", [.7, 1.1, 1.25, 1], ce["x"], ce["z"] - 3,
         "The second seal sleeps under my claws. Every light that comes this deep goes out.", ["venom_spider", "frost_wraith"], 6)
brazier(ce["x"] - 6, ce["z"] + 7, 8, ICE); brazier(ce["x"] + 6, ce["z"] + 7, 8, ICE); chest(ce["x"] + 6, ce["z"] - 6, 2)
tablet("dg_t_ce", "Carved tablet", ce["x"] - 5, ce["z"] - 8.9, 0, "THE SECOND SEAL LIES WHERE THE CRYSTALS ARE THICKEST. WHATEVER NESTS THERE FEEDS ON THE LIGHT.")
for (x, z) in ((-8, X(-92)), (8, X(-92)), (-8, X(-76)), (8, X(-76))): brazier(x, z, 8, ICE) if False else None

# ------------------------------------------------------------------ 6. Miners' Camp (K2) and the three note galleries
k2 = rc("K2")
campfire(0, -406, "dg_rest2")
box_prop("SM_tent_05", -20, -392, 0); box_prop("SM_tent_03", 24, -388, 0); box_prop("SM_tent_08", 29.5, -420, 90)
box_prop("SM_table_chairs", -14, -421, 180); box_prop("SM_crate_group_02", -26, -421, 0); box_prop("SM_crate_group_01", 26, -402, 90)
for k, (dx, dz) in enumerate(((0, 0), (1.5, .3), (.4, 1.5), (-1.2, 1.2))): box_prop("SM_barrel_0%d" % (1 + k % 4), 24 + dx, -428 + dz, 30 * k)
for x in (-26, -14, 14, 26): put("SM_beam_01", x, -385, 0, 0, 1.0); block(x, -385, .5, .5)
for (x, z) in ((-8, -429), (8, -429), (-8, -383), (8, -383)): brazier(x, z, 8)
npc(id="dg_shop2", name="Tolliver", title="Miner-trader", sprite="Kael", x=-9.5, z=-409, tint=[.9, .85, .7, 1], line="Picks, rope, and a good lantern. What are you short of?", action="shop")
npc(id="dg_miner", name="Hale", title="Last miner", sprite="Yulia", x=8.5, z=-410, tint=[.85, .8, .75, 1], line="", actions=[
    dict(type="say", who="Hale", text="The Sigil Hall's north of here. Three crystal stones, and the door won't open until all three show the right colour. Foreman wrote it down. Three sheets, three galleries."),
    dict(type="say", who="Hale", text="West shaft, east shaft, and the little one off the south passage. And mind the stones: they cycle red, blue, green, gold.")])
mw = rc("MW"); me = rc("ME"); ms = rc("MS")
note("dg_n_mw", "Foreman's sheet I", mw["x"] - 1, mw["z"] - 4, "Foreman's tally, sheet one. 'THE LEFT STONE IN THE SIGIL HALL MUST WEAR THE COLOUR OF THE SEA. Put the others wrong and the door just laughs.'", "Foreman's sheet")
chest(mw["x"] - 3, mw["z"] + 5, 2); box_prop("SM_barrel_04", mw["x"] + 5, mw["z"] - 5, 0); box_prop("SM_crate_02", mw["x"] + 4, mw["z"] + 6, 0); glow(mw["x"], mw["z"], 8, TORCH)
note("dg_n_me", "Foreman's sheet II", me["x"] + 1, me["z"] - 4, "Foreman's tally, sheet two. 'THE MIDDLE STONE MUST WEAR THE COLOUR OF THE SUN. If it turns up red it is only the dust. Turn it once more.'", "Foreman's sheet")
chest(me["x"] + 3, me["z"] + 5, 2); box_prop("SM_barrel_02", me["x"] - 5, me["z"] - 5, 0); box_prop("SM_crate_03", me["x"] - 4, me["z"] + 6, 0); glow(me["x"], me["z"], 8, TORCH)
note("dg_n_ms", "Foreman's sheet III", ms["x"], ms["z"] - 2, "Foreman's tally, sheet three. 'THE RIGHT STONE MUST WEAR THE COLOUR OF MOSS. Left, middle, right: sea, sun, moss. Then the door. Then the dead. God help the next shift.'", "Foreman's sheet")
chest(ms["x"] - 2, ms["z"] + 3, 3); glow(ms["x"], ms["z"], 8, TORCH); box_prop("SM_bed", ms["x"] + 3, ms["z"] + 3.5, 90)

# ------------------------------------------------------------------ 7. Sigil Hall (puzzle 3: three crystal stones)
sh = rc("SH")
STATE_COL = ["red", "blue", "green", "gold"]
SOLVED = "dg_pc_0_1,dg_pc_1_3,dg_pc_2_2"
def pc_spec(i, s): return "!dg_pc_%d_1,!dg_pc_%d_2,!dg_pc_%d_3" % (i, i, i) if s == 0 else "dg_pc_%d_%d" % (i, s)
for i, x in enumerate((-16, 0, 16)):
    z = -506
    put("SM_dg_dais", x, z, 0, 0, .7, pre=DG); block(x, z, 2.4, 2.4)
    for s in range(4):
        put("SM_cv_crystal_" + STATE_COL[s], x, z, 20 * s, .5, 1.5, "S:" + pc_spec(i, s) + ",!dg_pc_done")
        EV.append(dict(id="dg_pc_%d_%d" % (i, s), name="Crystal stone", x=x, z=z + 3.2, w=4.4, d=3.2, trigger="talk", prompt="Turn the stone (now %s)" % STATE_COL[s], showIf=pc_spec(i, s) + ",!dg_pc_done",
                       actions=[dict(type="say", who="", text="The stone turns and its glow shifts to %s." % STATE_COL[(s + 1) % 4]), dict(type="unflag", prefix="dg_pc_%d_" % i)] + ([dict(type="flag", key="dg_pc_%d_%d" % (i, s + 1))] if s < 3 else [])))
    put("SM_cv_crystal_" + {0: "blue", 1: "gold", 2: "green"}[i], x, z, 0, .5, 1.5, "S:dg_pc_done")                   # the locked-in colour once solved
    EV.append(dict(id="dg_pc_done_%d" % i, name="Crystal stone", x=x, z=z + 3.2, w=4.4, d=3.2, trigger="talk", prompt="Look at the stone", showIf="dg_pc_done",
                   actions=[dict(type="say", who="", text="The stone is locked in place, humming softly.")])); reserve(x, z + 3.2, 3)
    glow(x, z, 9, [1, .5, .9, .4])
for x in (-6, 6): brazier(x, X(-118) - 3, 8, VIO)
tablet("dg_t_sh", "Sigil tablet", 0, X(-130) + 1.2, 0, "THREE STONES, THREE COLOURS. LEFT, MIDDLE, RIGHT. THE MINERS KEPT THE ORDER ON PAPER, ONE SHEET PER SHAFT. A TURNED STONE CYCLES RED, BLUE, GREEN, GOLD.")
rockfall(GATE_S, "dg_pc_done", [.8, .5, 1, 1])
DEC.append(dict(type="glyph", x=0, z=X(-134) + 5, r=5.0, spin=-18, color=[.8, .5, 1, 1], hideIf="dg_pc_done"))
glow(0, -500, 20, [.7, .5, 1, .22])
for (x, z) in ((-26, -480), (26, -480), (-26, -512), (26, -512)):
    put("SM_cv_crystal_violet", x, z, rng.randint(0, 359), 0, 1.5); block(x, z, 1.3, 1.3); glow(x, z, 8, VIO)

# ------------------------------------------------------------------ 8. Crypt
cr = rc("CR")
for i in range(5):
    x = -36 + i * 18
    for z in (-600, -572):                                                   # rows of stone sarcophagi (long tables turned stone-grey by the dark)
        put("SM_dg_block", x, z, 0, 0, 1.6, pre=DG); block(x, z, 1.9, 1.9)
for (x, z) in ((-30, -620), (30, -620), (-30, -552), (30, -552)): brazier(x, z, 9, ICE)
glow(0, -590, 26, [.5, .65, 1, .2]); glow(0, -566, 14, ICE)
tablet("dg_t_cr", "Crypt tablet", 0, X(-158) + 1.5, 0, "THE COURT OF THE DROWNED SOVEREIGN. THEY SWORE TO STAND WITH HIM UNTIL THE TIDE TURNED. THE TIDE HAS NEVER TURNED.", ez=2.0)
pw = rc("PW"); pe = rc("PE")
guardian("dg_g3", "Crypt Sentinel", "Seal Keeper", "Draven", [.55, .7, 1.25, 1], pw["x"], pw["z"] - 3,
         "The third seal, and the last. The king's court sleeps. Leave it to its sleep.", ["dark_cultist", "frost_wraith"], 7, 3.0)
brazier(pw["x"] - 6, pw["z"] + 7, 8, ICE); brazier(pw["x"] + 6, pw["z"] + 7, 8, ICE); chest(pw["x"] - 6, pw["z"] - 6, 3)
chest(pe["x"] + 2, pe["z"] - 5, 3); chest(pe["x"] - 4, pe["z"] + 5, 3)
note("dg_n_pe", "Chapel record", pe["x"], pe["z"] - 8, "'HERE LIE THE KING'S TWELVE, EACH WITH HIS OWN TREASURE, EACH BOUND TO KEEP IT. IF YOU TAKE IT, TAKE IT QUIETLY.'", "Chapel record", table=False)
for k in range(4): put("SM_stalactic_0%d" % (1 + k), pe["x"] + rng.choice([-1, 1]) * rng.uniform(5, 9), pe["z"] + rng.choice([-1, 1]) * rng.uniform(4, 8), 30 * k, 0, .5)

# ------------------------------------------------------------------ 9. Antechamber and the Seal door
an = rc("AN")
for i, (col, key) in enumerate((("gold", "dg_g1"), ("blue", "dg_g2"), ("violet", "dg_g3"))):
    x = (-6, 0, 6)[i]; z = X(-170) + 1.5
    put("SM_dg_block", x, z, 0, 0, .9, pre=DG); block(x, z, 1.3, 1.3)
    put("SM_cv_crystal_off", x, z, 0, 1.05, .7, key); put("SM_cv_gem_" + col, x, z, 0, 1.2, 1.5, "S:" + key); glow(x, z, 6, {"gold": GOLD, "blue": ICE, "violet": VIO}[col], showIf=key)
tablet("dg_t_an", "Door tablet", -12.5, X(-165) - 1, 0, "BEYOND THIS DOOR THE SOVEREIGN KEEPS HIS THRONE. THREE KEEPERS HOLD THREE SEALS. WHEN ALL THREE HAVE FALLEN, THE DOOR WILL OPEN. ONLY THE BRAVE ENTER.", ez=2.0)
for sx in (-1, 1): brazier(sx * 15, X(-168), 9, ICE)
rockfall(GATE_B, "dg_g1,dg_g2,dg_g3", [.5, .7, 1, 1])
glow(0, X(-168), 14, ICE)

# ------------------------------------------------------------------ 10. The Sovereign's hall (boss, Lani, stairs home)
bh = rc("BH")
BZ = -758
put("SM_dg_dais", 0, BZ - 6, 0, 0, 1.0, pre=DG)
for sx in (-1, 1):
    for z in (-720, -740, -760): put("SM_cv_crystal_blue", sx * 26, z, rng.randint(0, 359), 0, 2.0); block(sx * 26, z, 1.6, 1.6); glow(sx * 26, z, 10, ICE)
    brazier(sx * 14, -724, 10, ICE); brazier(sx * 14, -764, 10, ICE)
glow(0, BZ, 22, [.45, .65, 1, .5]); glow(0, -735, 24, [.5, .65, 1, .2]); glow(0, -722, 5, [.6, .85, 1, .5], showIf="dg_boss")
NP.append(dict(id="dg_boss", name="Drowned Sovereign", title="King of the Hollow", sprite="Rook", x=0.0, z=BZ, h=4.0, tint=[0.45, 0.65, 1.2, 1], hideIf="dg_boss", reach=6.0,
               actions=[dict(type="say", who="Drowned Sovereign", text="You have cut through my court. Few come this far."), dict(type="say", who="Drowned Sovereign", text="Then draw your blades, and let the sea decide."),
                        dict(type="battle", key="dg_boss", boss="drowned_sovereign_boss", level=8)]))
NP.append(dict(id="dg_spirit", name="Spirit of the King", title="At rest", sprite="Lyra", x=0.0, z=BZ, h=2.6, tint=[0.7, 0.9, 1.4, 1], showIf="dg_boss", reach=5.0,
               actions=[dict(type="say", who="Spirit of the King", text="The tide is turned at last. Take what is left of my crown, and the thanks of the court."),
                        dict(type="say", who="Sera", text="Rest now, Your Majesty, you and all your court. The tide has turned.", **{"if": "st_sera"}),
                        dict(type="say", who="Spirit of the King", text="A mortal girl took shelter in the alcove by my throne when the doors sealed. Speak with her.", unless="st_found"),
                        dict(type="say", who="", text="The doors stand open and the cave is quiet. Touch the waking stone by the entrance to wake it again, or take the stairs home.")]))
NP.append(dict(id="dg_lani", name="Lani", title="Missing villager", sprite="Sera", x=-8.0, z=BZ + 7, h=2.2, tint=[1.25, 0.95, 1.1, 1], showIf="dg_boss", hideIf="st_found", reach=5.0,
               actions=[dict(type="say", who="Lani", text="You... beat the king? I was sure nobody would ever come."),
                        dict(type="say", who="Sera", text="Lani! Thank the tides. Sit, you are shaking. Here, drink this.", **{"if": "st_sera"}),
                        dict(type="say", who="Lani", text="I only wanted moonglow moss for Elder Mahina's cough. Then the doors sealed behind me and the dead king's court would not let me out."),
                        dict(type="say", who="Lani", text="There is a side tunnel up to the beach. Go ahead and I will meet you in the village!"), dict(type="flag", key="st_found")]))
EV.append(dict(id="dg_portal", name="Stairs to the surface", x=0.0, z=-722, w=5, d=2.4, trigger="talk", prompt="Climb back to the island", showIf="dg_boss", actions=[dict(type="warp", scene="island", x=0, z=-39.5)]))
for sx in (-1, 1): put("SM_stalactic_05", sx * 34, -712, 40 + sx * 30, 0, .45)

# ------------------------------------------------------------------ corridor lamps, rubble and stalagmites
for name, (i0, j0, i1, j1, kind) in R.items():
    if kind != "corr": continue
    long_ = (j1 - j0) > (i1 - i0)
    if not long_ and (i1 - i0) >= 10:                                       # long side halls: a lamp every 7 cells, alternating sides
        for k, ii in enumerate(range(i0 + 3, i1 - 1, 7)):
            bz = X(j0) - 1.1 if k % 2 == 0 else X(j1) + 1.1
            if free(X(ii), bz, 1.2): brazier(X(ii), bz, 7, TORCH)
    if long_ and (j1 - j0) >= 5:
        zc = X((j0 + j1) / 2)
        for sx in (-1, 1):
            if free(sx * 5.2, zc, 1.2): brazier(sx * 5.4, zc, 7, TORCH if X(j0) > -380 else ICE)
for name, (i0, j0, i1, j1, kind) in R.items():
    if kind != "room" or name in ("E", "BH"): pass
    r_ = rc(name)
    n = int(r_["w"] * r_["d"] / 150)
    for _ in range(n):
        side = rng.choice("nsew"); u = rng.uniform(-.5, .5)
        if side in "ns": x, z = r_["x"] + u * (r_["w"] - 6), (r_["z0"] + 2.0 if side == "n" else r_["z1"] - 2.0)
        else: x, z = (r_["x0"] + 2.0 if side == "w" else r_["x1"] - 2.0), r_["z"] + u * (r_["d"] - 6)
        if (round(x / CS), round(z / CS)) not in F or not free(x, z, 1.4): continue
        if rng.random() < .6: put("SM_stalactic_0%d" % rng.choice([1, 3, 6, 2]), x, z, rng.randint(0, 359), 0, rng.uniform(.4, .7)); block(x, z, 1.4, 1.4)
        else: put("SM_rock_0%d" % rng.choice([1, 2, 3]), x, z, rng.randint(0, 359), 0, rng.uniform(.9, 1.6)); block(x, z, 1.5, 1.5)
        OCC.append((x, z, 1.2))

# ------------------------------------------------------------------ verify the plan (walk the cave with the doors shut / open)
def flood(start, open_a, open_s, open_b, bridge):
    seen = {start}; q = deque([start])
    def ok(c):
        if c not in F: return False
        if c in LAKE and not (bridge and BRIDGE[0] <= c[0] <= BRIDGE[1]): return False
        if c[1] == GATE_A and not open_a: return False
        if c[1] == GATE_S and not open_s: return False
        if c[1] == GATE_B and not open_b: return False
        return True
    while q:
        c = q.popleft()
        for n in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)):
            if n not in seen and ok(n): seen.add(n); q.append(n)
    return seen
st = (0, -1)
r0 = flood(st, 0, 0, 0, 0); ra = flood(st, 1, 0, 0, 0); rb = flood(st, 1, 0, 0, 1); rs = flood(st, 1, 1, 0, 1); rall = flood(st, 1, 1, 1, 1)
tags = lambda s: {F[c] for c in s}
assert {"E", "K1", "GA", "GW", "GE", "S1", "S2", "c3", "h1", "A1", "h2", "A2"} <= tags(r0) and "GR" not in tags(r0), tags(r0)
assert "GR" in tags(ra) and "RW" in tags(ra) and "RE" in tags(ra) and "A3" in tags(ra) and "CV" not in tags(ra)
assert {"CV", "CW", "CE", "K2", "MW", "ME", "MS", "SH"} <= tags(rb) and "CR" not in tags(rb)
assert {"CR", "PW", "PE", "AN"} <= tags(rs) and "BH" not in tags(rs)
miss = [c for c in F if c not in rall and not (c in LAKE and not (BRIDGE[0] <= c[0] <= BRIDGE[1]))]
assert not miss and "BH" in tags(rall), miss[:10]
def cell_of(x, z): return (round(x / CS), round(z / CS))
bad = []
for o in NP + EV:
    c = cell_of(o["x"], o["z"])
    if c not in F or c not in rall: bad.append((o["id"], o["x"], o["z"]))
assert not bad, bad
for o in NP + EV:                                                    # nothing may sit inside a (permanent) collider, which would make it unreachable
    for cl in COL:
        if cl.get("hideIf"): continue
        if abs(o["x"] - cl["x"]) < cl["w"] / 2 - .05 and abs(o["z"] - cl["z"]) < cl["d"] / 2 - .05 and o["id"] not in {c[0] for c in CHESTS} and not o["id"].startswith(("dg_pa_", "dg_pc_", "dg_pb_")):
            if o.get("trigger") == "talk" and "prompt" in o and o["id"] in {c[0] for c in CHESTS}: continue
            bad.append((o["id"], "inside collider", cl))
assert not bad, bad[:6]
lost = [p for p in P if p[0].startswith((CC, DG, KEN)) and "floor_" not in p[0] and "SM_cv_wall" not in p[0] and p[0].find("/SM_floor_plank") < 0 and cell_of(p[1], p[2]) not in F]
assert not lost, [(q[0].split("/")[-1], q[1], q[2]) for q in lost[:12]]
# the shortest route start -> boss
def sp(a, b):
    dd = {a: 0}; q = deque([a])
    while q:
        c = q.popleft()
        if c == b: return dd[c]
        for n in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)):
            if n in rall and n not in dd: dd[n] = dd[c] + 1; q.append(n)
route = sp(st, (0, -190)) * CS
print("shortest route start->boss: %.0f m" % route, "| floor cells", len(F) - len(LAKE), "| lake", len(LAKE))

# ------------------------------------------------------------------ zones, objectives, scene
def zbox(i0, j0, i1, j1, **kw): d = dict(x=X((i0 + i1) / 2), z=X((j0 + j1) / 2), w=(i1 - i0 + 1) * CS + 8, d=(j1 - j0 + 1) * CS + 8); d.update(kw); return d
RATE = 75
ZONES = [zbox(-4, -5, 4, 0, safe=True), zbox(-8, -19, 8, -10, safe=True), zbox(-8, -108, 8, -95, safe=True), zbox(-5, -172, 5, -165, safe=True), zbox(-10, -194, 10, -173, safe=True),
         zbox(-60, -45, 60, -1, pool=["goblin_skirmisher", "bandit_rogue", "venom_spider"], level=[2, 3], rate=RATE),
         zbox(-60, -75, 60, -46, pool=["venom_spider", "stone_gargoyle", "bandit_rogue", "goblin_skirmisher"], level=[3, 4], rate=RATE),
         zbox(-60, -106, 60, -76, pool=["frost_wraith", "stone_gargoyle", "venom_spider"], level=[4, 5], rate=RATE),
         zbox(-60, -136, 60, -107, pool=["frost_wraith", "stone_gargoyle", "dark_cultist"], level=[4, 5], rate=RATE),
         zbox(-60, -171, 60, -137, pool=["dark_cultist", "frost_wraith", "stone_gargoyle"], level=[5, 6], rate=RATE)]
OBJ = [dict(unless="st_sera", text="Speak with the healer by the Smugglers' campfire"),
       dict(unless="dg_pa_4", text="Find the four embers hidden in the side rooms, then set them in the Gallery lamps in order"),
       dict(unless=BR_SPEC, text="Find the three winch gems at the far ends of the long halls to raise the Grotto causeway"),
       dict(unless="dg_pc_done", text="Find the miners' sheets and set the Sigil Hall stones"),
       dict(unless="dg_g1,dg_g2,dg_g3", text="Defeat the three Seal Keepers"),
       dict(unless="dg_boss", text="Open the door to the throne and face the Drowned Sovereign")]
AUTO = [dict(**{"if": "dg_boss", "unless": "st_bossmsg"}, actions=[dict(type="say", who="", text="The Drowned Sovereign crumbles, and the hall falls still. Somewhere near the throne, a girl is sobbing."), dict(type="flag", key="st_bossmsg")]),
        dict(**{"if": SOLVED, "unless": "dg_pc_done"}, actions=[dict(type="say", who="", text="The third stone settles. A deep chime runs through the hall, and the sigil door grinds open."), dict(type="flag", key="dg_pc_done")])]
def _runs(cells):
    out = []
    for j in sorted({c[1] for c in cells}):
        row = sorted(c[0] for c in cells if c[1] == j); a = b = row[0]
        for i in row[1:] + [None]:
            if i is not None and i == b + 1: b = i; continue
            out.append([X(a) - CS / 2, X(j) - CS / 2, (b - a + 1) * CS, CS])
            if i is not None: a = b = i
    return out
MINIMAP = dict(cell=CS, rects=_runs([c for c in F if c not in LAKE]), water=_runs(list(LAKE)))
xs = [c[0] for c in F]; zs = [c[1] for c in F]
d = dict(name="Hollow Cave", kit="", tile=4, pieces=P, colliders=COL, npcs=NP, events=EV, decals=DEC, story=True, restart="dg_", objectives=OBJ, autorun=AUTO,
         encounters=dict(rate=RATE, level=[2, 5], pool=["goblin_skirmisher", "bandit_rogue", "venom_spider", "stone_gargoyle", "frost_wraith", "dark_cultist"], zones=ZONES, text="Something stirs in the dark... monsters attack!"),
         bounds=dict(minX=X(min(xs)) - 6, maxX=X(max(xs)) + 6, minZ=X(min(zs)) - 6, maxZ=X(max(zs)) + 6), spawn=dict(x=SPAWN[0], z=SPAWN[1]), playerHeight=2.4, minimap=MINIMAP,
         sky=dict(type="gradient", stops=[[0, "#05070d"], [1, "#0d1420"]]), fx=[dict(type="dust", amount=.25)],
         light=dict(dir=[-0.35, -1, -0.25], color=[0.78, 0.82, 1.0], ambient=[0.38, 0.40, 0.50]), fog=dict(color=[0.03, 0.04, 0.07], near=34, far=92))
os.makedirs(OUT, exist_ok=True); json.dump(d, open(os.path.join(OUT, "dungeon.json"), "w"), separators=(",", ":"))
print("pieces", len(P), "walls", len(wallc), "colliders", len(COL), "npcs", len(NP), "events", len(EV), "decals", len(DEC), "chests", len(CHESTS), "chunks", len(chunks), "bounds", d["bounds"])

# ------------------------------------------------------------------ layout preview
try:
    from PIL import Image, ImageDraw
    S = 5; W_ = (max(xs) - min(xs) + 3) * S; H_ = (max(zs) - min(zs) + 3) * S
    im = Image.new("RGB", (W_, H_), (12, 14, 20)); dr = ImageDraw.Draw(im)
    for (i, j), t in F.items():
        col = (60, 110, 190) if (i, j) in LAKE else ((200, 150, 70) if t.startswith("K") else ((110, 110, 125) if R[t][4] == "corr" else (90, 130, 100)))
        x0, y0 = (i - min(xs) + 1) * S, (j - min(zs) + 1) * S; dr.rectangle([x0, y0, x0 + S - 1, y0 + S - 1], fill=col)
    for k, (key, x, z, t) in enumerate(CHESTS):
        cx, cy = (x / CS - min(xs) + 1) * S, (z / CS - min(zs) + 1) * S; dr.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(255, 220, 60))
    for n in NP:
        if n["id"].startswith("dg_g") or n["id"] == "dg_boss":
            cx, cy = (n["x"] / CS - min(xs) + 1) * S, (n["z"] / CS - min(zs) + 1) * S; dr.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(255, 60, 60))
    im.save(os.path.join(OUT, "cave_layout.png"))
except Exception as ex: print("preview skipped", ex)

"""Builds html_hub/3d/dungeon.json: the Hollow Cave under the island (claude/hollow-cave-dungeon.md). v3: a winding, branching cave (no straight corridors).
Kit: Assets/3D/CaveCamp (converted Cave_Camp meshes, see convert_cavecamp.py; procedural rock walls / water / flames / gems from gen_cave_meshes.py)
plus a few Dungeon-kit props (braziers, tablets, dais) and Kenney crates for the chests. Floors and the lake are merged into chunk GLBs written next to the kit.

How the layout works (v3):
  * Every room (camp, gallery, grotto, ...) is still authored in its own local frame (the old v2 coordinates, 4 m cells, north = -z), so all the props,
    NPCs, events and puzzles keep their exact positions relative to the room. Each room is then moved to a new place (POS below) as a block.
  * The rooms are joined by generated winding tunnels (EDGES below): an A* route with noise + waypoints, smoothed and rasterised with a round brush,
    leaving every room through a short straight 'stub'. The three door gates sit on straight stubs. Several extra links make loops, so there is more
    than one way to get around (the original ids, flags and puzzle order are unchanged; loops only join rooms that are reachable at the same time).
  * Room outlines are eroded with noise (coves, bays) instead of being plain rectangles.
Flags: dg_* are reset by the waking stone / restart (puzzle state, guardians, boss); chests are dc_* and stay opened (chest numbering is the same as v2).
Run:  python make_cave.py [outdir]   (writes dungeon.json to outdir and the floor/lake chunks into ../../Assets/3D/CaveCamp). Re-running overwrites hand edits made in /builder3d.
Env: CAVE_ASSET overrides the asset folder, CAVE_SEED changes the tunnel shapes."""
import json, math, os, random, struct, sys, heapq
from collections import deque
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glbkit import write_glb
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
HERE = os.path.dirname(os.path.abspath(__file__))
ASSET = os.environ.get("CAVE_ASSET") or os.path.normpath(os.path.join(HERE, "..", "..", "Assets", "3D", "CaveCamp"))
SEED = int(os.environ.get("CAVE_SEED", "5"))
CC, DG = "/assets/3D/CaveCamp/", "/assets/3D/Dungeon/"
KEN = "/assets/3D/kenney_retro-fantasy-kit/Models/GLB format/"
CS = 4.0
rng = random.Random(8841)                  # the content stream: unchanged from v2 so chest ids / loot stay the same
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
def cell_of(x, z): return (int(math.floor(x / CS + 0.5)), int(math.floor(z / CS + 0.5)))
def _h(a, b, s):
    n = (a * 73856093 ^ b * 19349663 ^ s * 83492791) & 0xFFFFFFFF; n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0
def vnoise(x, y, s=0):                     # smooth value noise in 0..1
    xi, yi = math.floor(x), math.floor(y); fx, fy = x - xi, y - yi; fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    a, b, c, d = _h(xi, yi, s), _h(xi + 1, yi, s), _h(xi, yi + 1, s), _h(xi + 1, yi + 1, s)
    return a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy

# ------------------------------------------------------------------ rooms (authored in the old v2 frame; moved to POS later)
F = {}                                     # (i,j) -> room tag (old frame, until the rooms are moved)
LAKE = set()
R = {}                                     # name -> (i0,j0,i1,j1,kind)
def room(name, i0, j0, i1, j1, kind="room"):
    R[name] = (i0, j0, i1, j1, kind)
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1): F[(i, j)] = name
def rc(name):                              # world centre + size of a room (old frame)
    i0, j0, i1, j1, _ = R[name]
    return dict(x=X((i0 + i1) / 2), z=X((j0 + j1) / 2), w=(i1 - i0 + 1) * CS, d=(j1 - j0 + 1) * CS, x0=X(i0) - 2, x1=X(i1) + 2, z0=X(j0) - 2, z1=X(j1) + 2)
room("E", -4, -5, 4, 0)
room("K1", -8, -19, 8, -10); room("S1", -20, -19, -15, -10); room("S2", 15, -19, 20, -10)
room("GA", -11, -38, 11, -27); room("GW", -25, -37, -19, -28); room("GE", 19, -37, 25, -28)
room("GR", -14, -66, 14, -47)
for i in range(-14, 15):
    for j in range(-61, -52): LAKE.add((i, j))
room("RW", -27, -55, -21, -46); room("RE", 21, -55, 27, -46)
room("CV", -10, -87, 10, -74); room("CW", -24, -86, -18, -77); room("CE", 18, -86, 24, -77)
room("K2", -8, -108, 8, -95); room("MW", -21, -107, -15, -98); room("ME", 15, -107, 21, -98); room("MS", -14, -116, -8, -110)
room("SH", -8, -130, 8, -118)
room("CR", -12, -158, 12, -138); room("PW", -25, -154, -19, -145); room("PE", 19, -154, 25, -145)
room("AN", -5, -172, 5, -165)
room("BH", -10, -194, 10, -177)
room("A1", 41, -19, 46, -10); room("A2", -51, -37, -46, -28); room("A3", 48, -55, 53, -46)       # the three winch-gem rooms (halls to them are generated tunnels now)
SPAWN = (0, -4.0)
GATE_A = GATE_S = GATE_B = 0                   # (v2 door rows; the doors are placed on tunnel stubs now, see GATE_LIST)
BR_SPEC = "dg_pb_1,dg_pb_2,dg_pb_3"

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
# ---- noise erosion of the outline (coves and bays, up to 2 cells deep) so rooms read as caverns, not boxes
ero = random.Random(31)
for name, (i0, j0, i1, j1, kind) in list(R.items()):
    if name in ("E",): continue
    sd = ero.randrange(1000); cut = []
    for (i, j), t in F.items():
        if t != name or (i, j) in LAKE: continue
        d = min(i - i0, i1 - i, j - j0, j1 - j)
        if 0 <= d <= 1 and vnoise(i / 3.3, j / 3.3, sd) < (0.50, 0.24)[d]: cut.append((i, j))
    for c in cut: F.pop(c, None)
    cells = [c for c, t in F.items() if t == name]                         # keep only the largest connected piece
    seen = set(); best = []
    for c in cells:
        if c in seen: continue
        comp = []; q = deque([c]); seen.add(c)
        while q:
            a = q.popleft(); comp.append(a)
            for n in ((a[0] + 1, a[1]), (a[0] - 1, a[1]), (a[0], a[1] + 1), (a[0], a[1] - 1)):
                if n not in seen and F.get(n) == name: seen.add(n); q.append(n)
        if len(comp) > len(best): best = comp
    for c in cells:
        if c not in set(best): F.pop(c, None)
F_PRISTINE_RECT = {n: v[:4] for n, v in R.items()}
GATE_LIST = []

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
    put("SM_TreasureChest", x, z, rot, 0, 1.0, key, pre="/assets/3D/Generated/"); block(x, z, 1.6, 1.6, key)      # the chest (and its blocker) vanish once opened
    EV.append(dict(id=key, name="Treasure chest", x=round(x, 2), z=round(z, 2), w=4.2, d=4.2, trigger="talk", prompt="Open the chest", hideIf=key,
                   actions=[dict(type="flag", key=key), dict(type="chest", loot=make_loot(tier, rng))])); reserve(x, z, 2.4)

# ---- doors (a rockfall of rock blocks + rubble that vanishes when the way opens)
def rockfall(row, key, glowcol=None):       # v3: the door is placed later, on a straight tunnel stub (see build_gate)
    GATE_LIST.append(dict(key=key, glowcol=glowcol, rot=[rng.choice([0, 90, 180]) for _ in range(3)]))

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
box_prop("SM_crate_group_02", 22, -43.5, 0); box_prop("SM_crate_group_01", -27, -67, 90); box_prop("SM_crate_02", 8, -44, 10)
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
tablet("dg_t_s1", "Scratched wall", X(-19.3), X(-19) + .9, 0, "'DOV WAS HERE. DOV WAS ALSO HERE FIRST.'", "Scratched into the rock")
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

# ------------------------------------------------------------------ where each room goes (centre cell, new frame; +i east, -j north) and how they are joined
SPINE = {"E": (0, -3), "K1": (12, -22), "GA": (-6, -44), "GR": (18, -71), "CV": (-4, -99), "K2": (18, -124), "SH": (-8, -149), "CR": (16, -176), "AN": (8, -202), "BH": (-6, -226)}
WID = {"K1": 17, "GA": 23, "GR": 29, "CV": 21, "K2": 17, "CR": 25}
POS = dict(SPINE)
def _spur(par, child, side, dj=0):
    w = WID[par]; POS[child] = (SPINE[par][0] + side * (w // 2 + 3 + 12 + 3), SPINE[par][1] + dj)
_spur("K1", "S1", -1); _spur("K1", "S2", 1)
_spur("GA", "GW", -1); _spur("GA", "GE", 1)
_spur("GR", "RW", -1, 1); _spur("GR", "RE", 1, 1)
_spur("CV", "CW", -1, -1); _spur("CV", "CE", 1, -1)
_spur("K2", "MW", -1); _spur("K2", "ME", 1)
_spur("CR", "PW", -1); _spur("CR", "PE", 1)
POS["MS"] = (SPINE["K2"][0] + 30, SPINE["K2"][1] - 18)
POS["A1"] = (POS["S2"][0] + 18, POS["S2"][1] - 20)
POS["A2"] = (POS["GW"][0] - 21, POS["GW"][1] - 22)
POS["A3"] = (POS["RE"][0] + 20, POS["RE"][1] - 22)
TIER = {"E": 0, "K1": 0, "S1": 0, "S2": 0, "A1": 0, "GA": 0, "GW": 0, "GE": 0, "A2": 0, "GR": 1, "RW": 1, "RE": 1, "A3": 1, "CV": 2, "CW": 2, "CE": 2, "K2": 2, "MW": 2, "ME": 2, "MS": 2,
        "SH": 3, "CR": 4, "PW": 4, "PE": 4, "AN": 4, "BH": 4}
SAFE = {"E", "K1", "K2", "AN", "BH"}
# (a, b, kind, extra)   kind: main = the spine, spur = side room, hall = long way to a winch gem, loop = extra link between rooms reachable at the same time, gate = door on the stub
EDGES = [
    dict(a="E", b="K1", kind="main"),
    dict(a="K1", b="GA", kind="main", pool=(0.2, 0.82)),
    dict(a="GA", b="GR", kind="gate", gate=0),
    dict(a="GR", b="CV", kind="main"),
    dict(a="CV", b="K2", kind="main", pool=(0.2, 0.82)),
    dict(a="K2", b="SH", kind="main", pool=(0.2, 0.82)),
    dict(a="SH", b="CR", kind="gate", gate=1),
    dict(a="CR", b="AN", kind="main"),
    dict(a="AN", b="BH", kind="gate", gate=2),
    dict(a="K1", b="S1", kind="spur"), dict(a="K1", b="S2", kind="spur"),
    dict(a="GA", b="GW", kind="spur"), dict(a="GA", b="GE", kind="spur"),
    dict(a="GR", b="RW", kind="spur"), dict(a="GR", b="RE", kind="spur"),
    dict(a="CV", b="CW", kind="spur"), dict(a="CV", b="CE", kind="spur"),
    dict(a="K2", b="MW", kind="spur"), dict(a="K2", b="ME", kind="spur"), dict(a="K2", b="MS", kind="spur", sa="s", sb="w"),
    dict(a="CR", b="PW", kind="spur"), dict(a="CR", b="PE", kind="spur"),
    dict(a="S2", b="A1", kind="hall", sa="e", sb="s"), dict(a="GW", b="A2", kind="hall"), dict(a="RE", b="A3", kind="hall"),
    dict(a="E", b="S1", kind="loop", sa="w", sb="s"), dict(a="S1", b="GW", kind="loop"), dict(a="S2", b="GE", kind="loop"),
    dict(a="CW", b="MW", kind="loop"), dict(a="CE", b="ME", kind="loop"), dict(a="PW", b="AN", kind="loop", sa="n", sb="w"),
]
GATE_EDGE = {e["gate"]: e for e in EDGES if e["kind"] == "gate"}
assert len(GATE_LIST) == 3 and len(GATE_EDGE) == 3
def _fl(v): return int(math.floor(v + 0.5))
OFF = {n: (_fl(POS[n][0] - (R[n][0] + R[n][2]) / 2), _fl(POS[n][1] - (R[n][1] + R[n][3]) / 2)) for n in R}
assert set(POS) == set(R), set(POS) ^ set(R)
def newcen(n): return (POS[n][0], POS[n][1])

# ---- ports: where a tunnel leaves a room (old frame), a short straight stub 3 cells wide
def port_ok(room, side, c, why=None):
    i0, j0, i1, j1, _ = R[room]
    if side in "ns":
        x0, x1 = X(c) - 3.2, X(c) + 3.2; z0, z1 = (X(j0) - 2, X(j0) + 6) if side == "n" else (X(j1) - 6, X(j1) + 2)
    else:
        z0, z1 = X(c) - 3.2, X(c) + 3.2; x0, x1 = (X(i0) - 2, X(i0) + 6) if side == "w" else (X(i1) - 6, X(i1) + 2)
    for cl in COL:
        if cl.get("hideIf"): continue
        if abs(cl["x"] - (x0 + x1) / 2) < cl["w"] / 2 + (x1 - x0) / 2 and abs(cl["z"] - (z0 + z1) / 2) < cl["d"] / 2 + (z1 - z0) / 2:
            if why is not None: why.append(("col", cl))
            return False
    for o in NP + EV:
        if x0 - 1 < o["x"] < x1 + 1 and z0 - 1 < o["z"] < z1 + 1:
            if why is not None: why.append(("obj", o["id"]))
            return False
    return True
PORTS = []
def make_port(room, side, tgt, L, prefer=None, lo=None, hi=None):
    i0, j0, i1, j1, _ = R[room]
    if side in "ns": a, b = (i0 + 3, i1 - 3) if (i1 - i0) > 8 else (i0 + 2, i1 - 2); pref = tgt[0] if prefer is None else prefer
    else: a, b = (j0 + 3, j1 - 3) if (j1 - j0) > 8 else (j0 + 2, j1 - 2); pref = tgt[1] if prefer is None else prefer
    if lo is not None: a = max(a, lo)
    if hi is not None: b = min(b, hi)
    cands = sorted(range(a, b + 1), key=lambda c: (abs(c - pref), c))
    for c in cands:
        if any(p["room"] == room and p["side"] == side and abs(p["c"] - c) < 6 for p in PORTS): continue
        if not port_ok(room, side, c): continue
        p = dict(room=room, side=side, c=c, L=L); PORTS.append(p); return p
    dbg = []
    for c in cands: w_ = []; port_ok(room, side, c, w_); dbg.append((c, w_[:2]))
    raise SystemExit("no free port for %s side %s (range %d..%d) %s" % (room, side, a, b, dbg))
def pick_side(a, b):
    dx, dz = newcen(b)[0] - newcen(a)[0], newcen(b)[1] - newcen(a)[1]
    if abs(dz) >= 0.55 * abs(dx): return ("n" if dz < 0 else "s"), ("s" if dz < 0 else "n")
    return ("e" if dx > 0 else "w"), ("w" if dx > 0 else "e")
for e in EDGES:
    a, b = e["a"], e["b"]
    sa, sb = pick_side(a, b)
    sa, sb = e.get("sa", sa), e.get("sb", sb)
    if e["kind"] == "gate": sa, sb = "n", "s"                      # gates sit on the south stub of the later room
    if e["kind"] == "gate": e["gate_up"] = b
    ta = (newcen(b)[0] - OFF[a][0], newcen(b)[1] - OFF[a][1]); tb = (newcen(a)[0] - OFF[b][0], newcen(a)[1] - OFF[b][1])
    kw_a, kw_b = {}, {}
    if a == "GR" and sa in "we": kw_a = dict(prefer=R["GR"][3] - 3, lo=R["GR"][3] - 4, hi=R["GR"][3] - 3)        # RW / RE open on the south bank, before the lake
    if b == "GR" and sb in "we": kw_b = dict(prefer=R["GR"][3] - 3, lo=R["GR"][3] - 4, hi=R["GR"][3] - 3)
    e["pa"] = make_port(a, sa, ta, 4, **kw_a); e["pb"] = make_port(b, sb, tb, 7 if e["kind"] == "gate" else 4, **kw_b)


for p in PORTS:                                                           # keep the scatter (rocks, stalactites) out of the tunnel mouths
    i0, j0, i1, j1, _ = R[p["room"]]
    for d_ in (-1, -2, -3):
        if p["side"] in "ns": x, z = X(p["c"]), (X(j0 - 1 - d_) if p["side"] == "n" else X(j1 + 1 + d_))
        else: z, x = X(p["c"]), (X(i0 - 1 - d_) if p["side"] == "w" else X(i1 + 1 + d_))
        OCC.append((x, z, 3.6))

for name, (i0, j0, i1, j1, kind) in R.items():
    if kind != "room" or name in ("E", "BH"): pass
    r_ = rc(name)
    n = int(r_["w"] * r_["d"] / 150)
    for _ in range(n):
        side = rng.choice("nsew"); u = rng.uniform(-.5, .5)
        if side in "ns": x, z = r_["x"] + u * (r_["w"] - 6), (r_["z0"] + 2.0 if side == "n" else r_["z1"] - 2.0)
        else: x, z = (r_["x0"] + 2.0 if side == "w" else r_["x1"] - 2.0), r_["z"] + u * (r_["d"] - 6)
        if cell_of(x, z) not in F or not free(x, z, 1.4): continue
        if rng.random() < .6: put("SM_stalactic_0%d" % rng.choice([1, 3, 6, 2]), x, z, rng.randint(0, 359), 0, rng.uniform(.4, .7)); block(x, z, 1.4, 1.4)
        else: put("SM_rock_0%d" % rng.choice([1, 2, 3]), x, z, rng.randint(0, 359), 0, rng.uniform(.9, 1.6)); block(x, z, 1.5, 1.5)
        OCC.append((x, z, 1.2))


# ------------------------------------------------------------------ keep every authored object on a floor cell (the outline erosion above may have eaten a cell under a prop)
def _near_room(x, z):
    c = cell_of(x, z)
    if c in F: return F[c]
    best, bn = 1e9, None
    for n, (i0, j0, i1, j1, _) in R.items():
        dx = max(i0 - c[0], 0, c[0] - i1); dz = max(j0 - c[1], 0, c[1] - j1); d = math.hypot(dx, dz)
        if d < best: best, bn = d, n
    return bn
for o in NP + EV:
    c = cell_of(o["x"], o["z"]); t = _near_room(o["x"], o["z"])
    for a in (-1, 0, 1):
        for b in (-1, 0, 1):
            n = (c[0] + a, c[1] + b)
            if n not in F and not any(F.get((n[0] + p, n[1] + q), t) != t for p in (-1, 0, 1) for q in (-1, 0, 1)): F[n] = t
    if c not in F: F[c] = t
for cl in COL:
    if cl.get("hideIf"): continue
    c = cell_of(cl["x"], cl["z"]); t = _near_room(cl["x"], cl["z"])
    if c not in F and t and not any(F.get((c[0] + p, c[1] + q), t) != t for p in (-1, 0, 1) for q in (-1, 0, 1)): F[c] = t
for p in P:
    if p[0].startswith((CC, DG, KEN)) and "SM_floor_plank" not in p[0]:
        c = cell_of(p[1], p[2]); t = _near_room(p[1], p[2])
        if c not in F and t and not any(F.get((c[0] + a, c[1] + b), t) != t for a in (-1, 0, 1) for b in (-1, 0, 1)): F[c] = t
for c in list(F):                                                         # fill single-cell notches
    pass

# ------------------------------------------------------------------ move the rooms (and everything authored in them) to their new places
def tag_at(x, z): return _near_room(x, z)
def shift(o, k="x", kz="z"):
    t = tag_at(o[k], o[kz]); di, dj = OFF[t]; o[k] = round(o[k] + di * CS, 3); o[kz] = round(o[kz] + dj * CS, 3); return t
for p in P:
    t = tag_at(p[1], p[2]); di, dj = OFF[t]; p[1] = round(p[1] + di * CS, 3); p[2] = round(p[2] + dj * CS, 3)
for cl in COL: shift(cl)
for d_ in DEC: shift(d_)
for o in NP + EV: shift(o)
OCC[:] = [(x + OFF[tag_at(x, z)][0] * CS, z + OFF[tag_at(x, z)][1] * CS, r) for (x, z, r) in OCC]
FN = {}                                    # final room cells, new frame
for (i, j), t in F.items(): FN[(i + OFF[t][0], j + OFF[t][1])] = t
LAKE = {(i + OFF["GR"][0], j + OFF["GR"][1]) for (i, j) in LAKE}
BRIDGE = (OFF["GR"][0] - 1, OFF["GR"][0] + 1)
RECT = {n: (v[0] + OFF[n][0], v[1] + OFF[n][1], v[2] + OFF[n][0], v[3] + OFF[n][1]) for n, v in F_PRISTINE_RECT.items()}
rects = sorted(RECT.items())
for ia in range(len(rects)):
    for ib in range(ia + 1, len(rects)):
        (na, ra), (nb, rb) = rects[ia], rects[ib]
        gx = max(ra[0] - rb[2], rb[0] - ra[2]); gz = max(ra[1] - rb[3], rb[1] - ra[3])
        assert max(gx, gz) >= 8, ("rooms too close", na, nb, gx, gz)
def stub_cells(p, shifted=True):             # cells of a port's straight stub (new frame), d = -3 (inside the room) .. L-1
    i0, j0, i1, j1, _ = R[p["room"]]; di, dj = OFF[p["room"]]; out = []
    for d in range(-3, p["L"]):
        for l in (-1, 0, 1):
            if p["side"] == "n": c = (p["c"] + l, j0 - 1 - d)
            elif p["side"] == "s": c = (p["c"] + l, j1 + 1 + d)
            elif p["side"] == "w": c = (i0 - 1 - d, p["c"] + l)
            else: c = (i1 + 1 + d, p["c"] + l)
            out.append((c[0] + di, c[1] + dj, d))
    return out
def stub_end(p):
    return [(c[0], c[1]) for c in stub_cells(p) if c[2] == p["L"] - 1 and c[0] is not None][1]            # the middle cell of the outermost row

# ------------------------------------------------------------------ tunnels: A* with noise + waypoints, smoothed, rasterised with a round brush
trng = random.Random(SEED)
allc = list(FN)
GI0 = min(c[0] for c in allc) - 40; GJ0 = min(c[1] for c in allc) - 40
GW_ = max(c[0] for c in allc) + 40 - GI0 + 1; GH_ = max(c[1] for c in allc) + 40 - GJ0 + 1
def mask_of(cells):
    m = np.zeros((GW_, GH_), bool)
    for c in cells:
        x, y = c[0] - GI0, c[1] - GJ0
        if 0 <= x < GW_ and 0 <= y < GH_: m[x, y] = True
    return m
def dil(m, r):
    out = m.copy()
    for a in range(-r, r + 1):
        for b in range(-r, r + 1):
            if a == 0 and b == 0: continue
            sh = np.zeros_like(m)
            sh[max(a, 0):GW_ + min(a, 0), max(b, 0):GH_ + min(b, 0)] = m[max(-a, 0):GW_ + min(-a, 0), max(-b, 0):GH_ + min(-b, 0)]
            out |= sh
    return out
ROOM_M = {n: mask_of([c for c, t in FN.items() if t == n]) for n in R}
ROOM_D4 = {n: dil(ROOM_M[n], 4) for n in R}; ROOM_D2 = {n: dil(ROOM_M[n], 2) for n in R}
for e in EDGES:
    e["stubs"] = [stub_cells(e["pa"]), stub_cells(e["pb"])]
    e["stubset"] = {(c[0], c[1]) for s in e["stubs"] for c in s}
    e["endA"], e["endB"] = stub_end(e["pa"]), stub_end(e["pb"])
    for s in e["stubset"]: assert s not in FN or FN[s] in (e["a"], e["b"]), ("stub hits another room", e["a"], e["b"], s, FN.get(s))
TUN = {}                                    # edge index -> set of cells (stubs + routed brush)
TPATH = {}                                  # edge index -> smoothed centre line (list of (i, j) floats)
TUN_D4 = {}
for k, e in enumerate(EDGES): TUN[k] = set(e["stubset"]); TUN_D4[k] = dil(mask_of(TUN[k]), 4)
def astar(start, goal, forb, noise_seed):
    s = (start[0] - GI0, start[1] - GJ0); g = (goal[0] - GI0, goal[1] - GJ0)
    openq = [(0.0, 0.0, s)]; best = {s: 0.0}; came = {}
    while openq:
        f, gc, cur = heapq.heappop(openq)
        if cur == g:
            path = [cur]
            while cur in came: cur = came[cur]; path.append(cur)
            return [(x + GI0, y + GJ0) for (x, y) in reversed(path)]
        if gc > best.get(cur, 1e18): continue
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (cur[0] + dx, cur[1] + dy)
            if not (0 <= n[0] < GW_ and 0 <= n[1] < GH_) or (forb[n] and n != g): continue
            c = gc + 1.0 + 1.3 * vnoise(n[0] / 9.0, n[1] / 9.0, noise_seed)
            if c < best.get(n, 1e18): best[n] = c; came[n] = cur; heapq.heappush(openq, (c + abs(n[0] - g[0]) + abs(n[1] - g[1]), c, n))
    return None
def smooth_path(pts, pin=3, iters=14):
    p = [list(map(float, q)) for q in pts]
    for _ in range(iters):
        q = [r[:] for r in p]
        for n in range(pin, len(p) - pin):
            for ax in (0, 1):
                w = [(n + o, 4 - abs(o)) for o in (-3, -2, -1, 0, 1, 2, 3) if 0 <= n + o < len(p)]
                q[n][ax] = sum(p[m][ax] * wt for m, wt in w) / sum(wt for m, wt in w)
        p = q
    return p
def brush(poly, rbase, rr, wob_seed, bulge=None):
    cells = set(); step = 0.4; s = 0.0
    tot = sum(math.hypot(poly[a + 1][0] - poly[a][0], poly[a + 1][1] - poly[a][1]) for a in range(len(poly) - 1))
    for a in range(len(poly) - 1):
        (x0, y0), (x1, y1) = poly[a], poly[a + 1]; L = math.hypot(x1 - x0, y1 - y0); n = max(1, int(L / step))
        for t in range(n):
            x = x0 + (x1 - x0) * t / n; y = y0 + (y1 - y0) * t / n; s += L / n
            r = rbase + 0.45 * (vnoise(s / 7.0, wob_seed * 3.1, wob_seed) - 0.5) * 2 + 0.55 * max(0, vnoise(s / 15.0, 9.3, wob_seed + 5) - 0.62) * 4
            rcap = rbase + 1.5
            if bulge:
                t = (s - bulge[0] * tot) / ((bulge[1] - bulge[0]) * tot)
                if 0 < t < 1: r = r + (bulge[2] - rbase) * max(0.0, min(1.0, t / 0.22, (1 - t) / 0.22)); rcap = bulge[2] + 1.2
            r = max(1.25, min(r, rcap))
            for i in range(int(x - r - 1), int(x + r + 2)):
                for j in range(int(y - r - 1), int(y + r + 2)):
                    if (i - x) ** 2 + (j - y) ** 2 <= r * r: cells.add((i, j))
    return cells
def route_edge(k):
    e = EDGES[k]; A, B = e["endA"], e["endB"]
    others = [n for n in R if n not in (e["a"], e["b"])]
    base = np.zeros((GW_, GH_), bool)
    for n in others: base |= ROOM_D4[n]
    base |= ROOM_D2[e["a"]] | ROOM_D2[e["b"]]
    for k2 in TUN:
        if k2 != k: base |= TUN_D4[k2]
    for kk in (0, 1):                                                           # a gate stub is never approached closely by its own tunnel
        pass
    if e["kind"] == "gate":
        up = e["pb"]; gate_cells = [(c[0], c[1]) for c in stub_cells(up) if c[2] <= 3]
        base |= dil(mask_of(gate_cells), 3)
    for (px, py) in (A, B):
        x, y = px - GI0, py - GJ0; base[max(0, x - 1):x + 2, max(0, y - 1):y + 2] = False
    hard = np.zeros((GW_, GH_), bool)
    for n in others: hard |= dil(ROOM_M[n], 1)
    for k2 in TUN:
        if k2 != k: hard |= dil(mask_of(TUN[k2]), 1)
    nwp = {"main": 2, "spur": 1, "hall": 3, "loop": 2, "gate": 1}[e["kind"]]
    amp = {"main": (5, 11), "spur": (3, 7), "hall": (8, 16), "loop": (5, 10), "gate": (4, 8)}[e["kind"]]
    rb = {"main": 1.75, "spur": 1.65, "hall": 1.5, "loop": 1.6, "gate": 1.75}[e["kind"]]
    last = None; why = {'wp': 0, 'astar': 0, 'bad': 0, 'short': 0}
    for attempt in range(60):
        scale = 1.0 if attempt < 20 else (0.6 if attempt < 40 else 0.3)
        if attempt == 30 and e.get('pool'): e['pool'] = None          # no room for a pool cave here
        sg = 1 if trng.random() < .5 else -1
        wps = []
        dx, dz = B[0] - A[0], B[1] - A[1]; ln = math.hypot(dx, dz) or 1.0; nx, nz = -dz / ln, dx / ln
        nw = nwp if attempt < 40 else (1 if attempt < 50 else 0)
        for w in range(nw):
            t = (w + 1) / (nw + 1) + trng.uniform(-.06, .06); off = sg * trng.uniform(*amp) * scale * (1 if w % 2 == 0 else -1)
            wp = (int(round(A[0] + dx * t + nx * off)), int(round(A[1] + dz * t + nz * off)))
            wps.append(wp)
        ok = True; path = [A]
        stops = wps + [B]; cur = A
        for wp in stops:
            if not (0 <= wp[0] - GI0 < GW_ and 0 <= wp[1] - GJ0 < GH_) or (base[wp[0] - GI0, wp[1] - GJ0] and wp != B): ok = False; why['wp'] += 1; break
            leg = astar(cur, wp, base, k * 31 + attempt)
            if not leg: ok = False; why['astar'] += 1; break
            path += leg[1:]; cur = wp
        if not ok: continue
        sm = smooth_path(path, pin=4)
        cells = brush(sm, rb, None, k + 1, (e['pool'][0], e['pool'][1], 4.0) if e.get('pool') else None)
        bad = [c for c in cells if 0 <= c[0] - GI0 < GW_ and 0 <= c[1] - GJ0 < GH_ and hard[c[0] - GI0, c[1] - GJ0]]
        if bad: last = len(bad); why['bad'] += 1; continue
        if len(path) < 1.18 * (abs(B[0] - A[0]) + abs(B[1] - A[1])) and e["kind"] in ("main", "hall") and attempt < 30: why['short'] += 1; continue
        e["poly"] = sm; return cells
    try:
        from PIL import Image
        im = np.zeros((GW_, GH_, 3), np.uint8); im[base] = (70, 30, 30)
        for n in R: im[ROOM_M[n]] = (90, 140, 100)
        for k2 in TUN:
            for c in TUN[k2]: im[c[0] - GI0, c[1] - GJ0] = (120, 120, 140)
        for (px, py) in (A, B): im[px - GI0 - 1:px - GI0 + 2, py - GJ0 - 1:py - GJ0 + 2] = (255, 255, 0)
        Image.fromarray(np.transpose(im, (1, 0, 2))).resize((GW_ * 4, GH_ * 4), Image.NEAREST).save("/tmp/claude-0/cave/fail.png")
    except Exception as ex: print("dbg", ex)
    if e["kind"] == "loop":
        print("WARNING: loop %s-%s could not be routed (%s)" % (e["a"], e["b"], why)); e["poly"] = None; return None
    raise SystemExit("could not route %s-%s (%s) last conflict %s %s A=%s B=%s" % (e["a"], e["b"], e["kind"], last, why, A, B))
ORDER = sorted(range(len(EDGES)), key=lambda k: ({"gate": 0, "main": 0, "spur": 1, "hall": 2, "loop": 3}[EDGES[k]["kind"]], k))
for k in ORDER:
    cells = route_edge(k)
    if cells is None: TUN[k] = set(); TUN_D4[k] = dil(mask_of(set()), 1); continue
    TUN[k] |= cells; TUN_D4[k] = dil(mask_of(TUN[k]), 4)


# ------------------------------------------------------------------ final floor plan = rooms + tunnels
TNAME = {k: "t_%s_%s" % (e["a"], e["b"]) for k, e in enumerate(EDGES)}
F = dict(FN)
TUNCELL = {}
for k, cells in TUN.items():
    for c in cells:
        c = (c[0], c[1])
        if c not in F: F[c] = TNAME[k]
        TUNCELL.setdefault(c, set()).add(k)
# every tunnel brush cell that is not part of a room is a tunnel floor
GATES = {}
for gi, e in GATE_EDGE.items():
    p = e["pb"]; cc = [c for c in stub_cells(p) if c[2] == 3]
    ci, cj = sorted(cc)[1][0], sorted(cc)[1][1]
    GATES[gi] = dict(cells={(ci + l, cj) for l in (-1, 0, 1)}, ci=ci, cj=cj, **GATE_LIST[gi])
    # the gate must be a clean 3-wide throat: only its own three cells may connect the two sides
    for l in (-1, 0, 1): assert (ci + l, cj) in F, (gi, ci + l, cj)
    assert (ci - 2, cj) not in F and (ci + 2, cj) not in F, ("gate not a clean throat", gi)

def seg_dist(px, py, poly):
    best = 1e9
    for a in range(len(poly) - 1):
        (x0, y0), (x1, y1) = poly[a], poly[a + 1]; dx, dy = x1 - x0, y1 - y0; L2 = dx * dx + dy * dy or 1e-9
        t = max(0, min(1, ((px - x0) * dx + (py - y0) * dy) / L2)); best = min(best, math.hypot(px - (x0 + t * dx), py - (y0 + t * dy)))
    return best
POOLSET = set(); POOLLANE = []                     # pool caves: water everywhere except a boardwalk lane along the tunnel's centre line
for k, e in enumerate(EDGES):
    if not (e.get("poly") and e.get("pool")): continue
    poly = e["poly"]; cum = [0.0]
    for a in range(len(poly) - 1): cum.append(cum[-1] + math.hypot(poly[a + 1][0] - poly[a][0], poly[a + 1][1] - poly[a][1]))
    tot = cum[-1]; s0, s1 = e["pool"][0] * tot + 2, e["pool"][1] * tot - 2
    for c in TUN[k]:
        c = (c[0], c[1])
        if F.get(c) != TNAME[k] or len(TUNCELL.get(c, ())) != 1: continue
        bi = min(range(len(poly)), key=lambda i: (poly[i][0] - c[0]) ** 2 + (poly[i][1] - c[1]) ** 2)
        if not (s0 <= cum[bi] <= s1): continue
        if seg_dist(c[0], c[1], poly) > 0.8: POOLSET.add(c)
        else:
            a_, b_ = poly[max(bi - 1, 0)], poly[min(bi + 1, len(poly) - 1)]
            POOLLANE.append((c, 90 if abs(b_[0] - a_[0]) > abs(b_[1] - a_[1]) else 0))
for _ in range(4):                                  # floor cells that a pool cut off from the rest become water too (no unreachable pockets)
    st0 = (0 + OFF["E"][0], -1 + OFF["E"][1]); seen0 = {st0}; q0 = deque([st0])
    while q0:
        c = q0.popleft()
        for n in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)):
            if n not in seen0 and n in F and n not in POOLSET: seen0.add(n); q0.append(n)
    lone = {c for c in F if c not in seen0 and c not in POOLSET}
    assert all(F[c].startswith("t_") for c in lone), [c for c in lone if not F[c].startswith("t_")][:5]
    if not lone: break
    POOLSET |= lone; POOLLANE = [(c, r) for (c, r) in POOLLANE if c not in lone]
WATER = LAKE | POOLSET
blocked = set()
for (i, j) in F:
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            if (i + di, j + dj) not in F: blocked.add((i + di, j + dj))
wallc = {c for c in blocked if any((c[0] + di, c[1] + dj) in F for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
wr = random.Random(555)
WALLS = ("SM_cv_wall_rock",) * 3                      # user's Cave-Wall mesh (Assets/3D/Generated), decimated + sized 4x6x4 -> SM_cv_wall_rock.glb
for c in sorted(wallc):
    h = (c[0] * 73856093 ^ c[1] * 19349663) & 0xFFFF
    sc = 1.05 + ((h >> 8) % 6) * .07; sy = 0.85 + ((h >> 13) % 9) * .11
    jx = (((h >> 3) % 7) - 3) * .22; jz = (((h >> 6) % 7) - 3) * .22
    put(WALLS[h % 3], X(c[0]) + jx, X(c[1]) + jz, (0, 90, 180, 270)[(h >> 4) % 4], 0, [round(sc, 3), round(sy, 3), round(sc, 3)])
    if (h >> 11) % 7 == 0: put("SM_cv_wall_rock", X(c[0]), X(c[1]), (0, 90, 180, 270)[(h >> 5) % 4], 0, [1.0, 1.5, 1.0])
rows = {}
for (i, j) in blocked: rows.setdefault(j, []).append(i)
for j, xs in rows.items():
    xs.sort(); s = prev = xs[0]
    for x in xs[1:] + [None]:
        if x is None or x != prev + 1:
            block(X((s + prev) / 2), X(j), (prev - s + 1) * CS, CS); s = x
        if x is not None: prev = x
prow = {}
for (i, j) in POOLSET: prow.setdefault(j, []).append(i)
for j, xs_ in prow.items():
    xs_.sort(); s = prev = xs_[0]
    for x in xs_[1:] + [None]:
        if x is None or x != prev + 1:
            block(X((s + prev) / 2), X(j), (prev - s + 1) * CS, CS); s = x
        if x is not None: prev = x
def glb_image(path):
    b = open(path, "rb").read(); jl = struct.unpack("<I", b[12:16])[0]; js = json.loads(b[20:20 + jl]); bl = struct.unpack("<I", b[20 + jl:24 + jl])[0]
    bin0 = 20 + jl + 8; bv = js["bufferViews"][js["images"][0]["bufferView"]]
    return b[bin0 + bv["byteOffset"]: bin0 + bv["byteOffset"] + bv["byteLength"]]
FLOOR_IMG = open(os.path.join(ASSET, "tex_floor_cave.jpg"), "rb").read()      # user's Generated/Textures/Cave-Floor.webp made seamless (512 px)
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
    if c not in WATER: chunks.setdefault((c[0] // 16, c[1] // 16), []).append(c)
for (ci, cj), cells in sorted(chunks.items()):
    p, n, uv, idx = quads(cells, 0.0, 18.0); nm = "floor_%d_%d" % (ci, cj)
    write_glb(os.path.join(ASSET, nm + ".glb"), p, n, idx, nm, uv=uv, img=FLOOR_IMG, color=(.6, .56, .54, 1))
    put(nm, 0, 0, 0, 0, 1)
p, n, uv, idx = quads(WATER, -1.5, 18.0)
write_glb(os.path.join(ASSET, "floor_lakebed.glb"), p, n, idx, "floor_lakebed", uv=uv, img=FLOOR_IMG, color=(.28, .4, .5, 1)); put("floor_lakebed", 0, 0, 0, 0, 1)
p, n, uv, idx = quads(WATER, -0.35, 2.0)
write_glb(os.path.join(ASSET, "floor_lake.glb"), p, n, idx, "floor_lake", uv=uv, img=WATER_IMG, color=(1, 1, 1, .78), alpha="BLEND", double=True); put("floor_lake", 0, 0, 0, 0, 1)
# the lake itself is impassable except on the causeway lane
lj = [c[1] for c in LAKE]; li = [c[0] for c in LAKE]
lz0, lz1 = X(min(lj)) - 2, X(max(lj)) + 2; GRX = OFF["GR"][0] * CS
LX0, LX1 = X(min(li)) - 2, X(max(li)) + 2
block(((LX0) + (GRX - 4.8)) / 2, (lz0 + lz1) / 2, (GRX - 4.8) - LX0, lz1 - lz0)
block(((GRX + 4.8) + LX1) / 2, (lz0 + lz1) / 2, LX1 - (GRX + 4.8), lz1 - lz0)
block(GRX, (lz0 + lz1) / 2, 9.6, lz1 - lz0, BR_SPEC)
for j in range(min(lj), max(lj) + 1):
    for px in (-2.25, 2.25): put("SM_floor_plank_01", GRX + px, X(j), 0, 0.08, 1.05, "S:" + BR_SPEC)

for (c, rt) in POOLLANE: put("SM_floor_plank_01", X(c[0]), X(c[1]), rt, 0.06, 1.0)
# ---- the three doors (a rockfall of rock blocks + rubble that vanishes when the way opens)
def build_gate(g):
    z = X(g["cj"]); x0 = X(g["ci"]); key = g["key"]
    for l, i in enumerate((-1, 0, 1)):
        put("SM_cv_wall_rock", x0 + X(i), z, 90 * (i + 1), 0, 1.0, key)
    block(x0, z, 12, 4, key)
    for (dx, nm), rt in zip(((-4.3, "SM_rock_02"), (3.6, "SM_rock_03"), (0.4, "SM_rock_01")), g["rot"]): put(nm, x0 + dx, z + 2.6, rt, 0, 1.4, key)
    if g["glowcol"]: DEC.append(dict(type="glyph", x=round(x0, 3), z=round(z + 2.4, 2), r=4.0, spin=20, color=g["glowcol"], hideIf=key))
for g in GATES.values(): build_gate(g)

# ------------------------------------------------------------------ tunnel dressing (after the rooms: uses its own random stream)
dr = random.Random(2024)
EDGE_CELLS = {c for c in F if any((c[0] + a, c[1] + b) not in F for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
LANESET = {c for c, _ in POOLLANE}
def tunnel_free(x, z, r=1.2): return free(x, z, r) and cell_of(x, z) not in POOLSET and cell_of(x, z) not in LANESET
CENTRE = {}
for k, e in enumerate(EDGES): CENTRE[k] = e["poly"]
EDGES_OK = [k for k, e in enumerate(EDGES) if e.get('poly')]
for k, e in enumerate(EDGES):
    if not e.get('poly'): continue
    poly = e["poly"]; tun_ice = TIER[e["b"]] >= 2
    acc = 0.0; side = 1 if k % 2 == 0 else -1; nlamp = 0
    for a in range(len(poly) - 1):
        (x0, y0), (x1, y1) = poly[a], poly[a + 1]; L = math.hypot(x1 - x0, y1 - y0); acc += L
        if acc < 7.5 or a < 6 or a > len(poly) - 8: continue
        acc = 0.0; nx, ny = -(y1 - y0) / (L or 1), (x1 - x0) / (L or 1)
        for off in (1.35, 1.0, 0.7):
            wx, wz = X(x1 + nx * off * side), X(y1 + ny * off * side)
            if cell_of(wx, wz) in F and tunnel_free(wx, wz, 1.2) and seg_dist(x1 + nx * off * side, y1 + ny * off * side, poly) > 0.5:
                brazier(wx, wz, 7, ICE if tun_ice else TORCH); nlamp += 1; side = -side; break
# stalagmites / rocks hugging the tunnel walls
for c in sorted(EDGE_CELLS):
    t = F[c]
    if not t.startswith("t_") or c in POOLSET or c in LANESET or dr.random() > .09: continue
    ang = dr.uniform(0, math.tau); x, z = X(c[0]) + math.cos(ang) * 1.0, X(c[1]) + math.sin(ang) * 1.0
    if cell_of(x, z) not in F or not free(x, z, 1.3): continue
    kl = [kk for kk in TUNCELL.get(c, []) if EDGES[kk].get('poly')]
    if not kl or min(seg_dist(c[0], c[1], EDGES[kk]["poly"]) for kk in kl) < 1.15: continue
    if dr.random() < .55: put("SM_stalactic_0%d" % dr.choice([1, 3, 6, 2]), x, z, dr.randint(0, 359), 0, dr.uniform(.4, .65)); block(x, z, 1.3, 1.3)
    else: put("SM_rock_0%d" % dr.choice([1, 2, 3]), x, z, dr.randint(0, 359), 0, dr.uniform(.9, 1.5)); block(x, z, 1.4, 1.4)
    OCC.append((x, z, 1.2))
# blue light along the lower tunnels, warm along the upper-middle ones
for k, e in enumerate(EDGES):
    if not e.get('poly'): continue
    poly = e["poly"]
    for a in range(10, len(poly) - 10, 14):
        glow(X(poly[a][0]), X(poly[a][1]), 9, [.35, .6, .95, .10] if TIER[e["b"]] >= 1 else [1, .6, .3, .08])
for (c, rt) in POOLLANE[::5]: glow(X(c[0]), X(c[1]), 8, [.3, .75, 1, .16])
glow(0, 3, 16, [1, .95, .8, .38])                                           # daylight spilling in at the island exit


# ------------------------------------------------------------------ verify the plan (walk the cave with the doors shut / open)
def flood(start, open_a, open_s, open_b, bridge):
    seen = {start}; q = deque([start])
    gates_open = {0: open_a, 1: open_s, 2: open_b}
    shut = set()
    for gi, g in GATES.items():
        if not gates_open[gi]: shut |= g["cells"]
    def ok(c):
        if c not in F or c in shut or c in POOLSET: return False
        if c in LAKE and not (bridge and BRIDGE[0] <= c[0] <= BRIDGE[1]): return False
        return True
    while q:
        c = q.popleft()
        for n in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)):
            if n not in seen and ok(n): seen.add(n); q.append(n)
    return seen
st = (0 + OFF["E"][0], -1 + OFF["E"][1])
r0 = flood(st, 0, 0, 0, 0); ra = flood(st, 1, 0, 0, 0); rb = flood(st, 1, 0, 0, 1); rs = flood(st, 1, 1, 0, 1); rall = flood(st, 1, 1, 1, 1)
def rooms_of(s): return {F[c] for c in s if not F[c].startswith("t_")}
assert {"E", "K1", "GA", "GW", "GE", "S1", "S2", "A1", "A2"} <= rooms_of(r0) and not ({"GR", "RW", "RE", "A3", "CV"} & rooms_of(r0)), rooms_of(r0)
assert {"GR", "RW", "RE", "A3"} <= rooms_of(ra) and not ({"CV", "CW", "CE", "K2"} & rooms_of(ra)), rooms_of(ra)
assert {"CV", "CW", "CE", "K2", "MW", "ME", "MS", "SH"} <= rooms_of(rb) and not ({"CR", "PW", "PE", "AN", "BH"} & rooms_of(rb)), rooms_of(rb)
assert {"CR", "PW", "PE", "AN"} <= rooms_of(rs) and "BH" not in rooms_of(rs), rooms_of(rs)
miss = [c for c in F if c not in rall and c not in POOLSET and not (c in LAKE and not (BRIDGE[0] <= c[0] <= BRIDGE[1]))]
assert not miss and "BH" in rooms_of(rall), miss[:10]
bad = []
for o in NP + EV:
    c = cell_of(o["x"], o["z"])
    if c not in F or c not in rall: bad.append((o["id"], o["x"], o["z"]))
assert not bad, bad
CHEST_IDS = {c[0] for c in CHESTS}
for o in NP + EV:                                                    # nothing may sit inside a (permanent) collider, which would make it unreachable
    for cl in COL:
        if cl.get("hideIf"): continue
        if abs(o["x"] - cl["x"]) < cl["w"] / 2 - .05 and abs(o["z"] - cl["z"]) < cl["d"] / 2 - .05 and o["id"] not in CHEST_IDS and not o["id"].startswith(("dg_pa_", "dg_pc_", "dg_pb_")):
            if o.get("trigger") == "talk" and "prompt" in o and o["id"] in CHEST_IDS: continue
            bad.append((o["id"], "inside collider", cl))
assert not bad, bad[:6]
lost = [p for p in P if p[0].startswith((CC, DG, KEN)) and "floor_" not in p[0] and "SM_cv_wall" not in p[0] and p[0].find("/SM_floor_plank") < 0 and cell_of(p[1], p[2]) not in F]
assert not lost, [(q[0].split("/")[-1], q[1], q[2]) for q in lost[:12]]
# real walkability: rasterise every permanent collider at 1 m and flood from the spawn (doors open, bridge up) so a tunnel / door / stub can never be sealed by a prop
def collider_walk():
    perm = [c for c in COL if not c.get("hideIf")]
    xs_ = [X(c[0]) for c in F]; zs_ = [X(c[1]) for c in F]
    x0, z0 = min(xs_) - 8, min(zs_) - 8; W = int((max(xs_) - x0) + 16); H = int((max(zs_) - z0) + 16)
    grid = np.zeros((W, H), bool)
    for c in perm:
        a, b = int(c["x"] - c["w"] / 2 - x0), int(c["x"] + c["w"] / 2 - x0); e_, f_ = int(c["z"] - c["d"] / 2 - z0), int(c["z"] + c["d"] / 2 - z0)
        grid[max(a, 0):min(b + 1, W), max(e_, 0):min(f_ + 1, H)] = True
    return grid, x0, z0, W, H
grid, gx0, gz0, GWm, GHm = collider_walk()
def walk_from(x, z):
    s = (int(x - gx0), int(z - gz0)); seen = {s}; q = deque([s])
    while q:
        a = q.popleft()
        for n in ((a[0] + 1, a[1]), (a[0] - 1, a[1]), (a[0], a[1] + 1), (a[0], a[1] - 1)):
            if 0 <= n[0] < GWm and 0 <= n[1] < GHm and n not in seen and not grid[n]: seen.add(n); q.append(n)
    return seen
walk = walk_from(SPAWN[0] + OFF["E"][0] * CS, SPAWN[1] + OFF["E"][1] * CS)
unreach = []
for o in NP + EV:
    if o["id"].startswith(("dg_pa_", "dg_pc_", "dg_pb_")) or o.get("hideIf") in ("dg_boss",): pass
    ok = any((int(o["x"] - gx0) + a, int(o["z"] - gz0) + b) in walk for a in range(-3, 4) for b in range(-3, 4))
    if not ok: unreach.append((o["id"], o["x"], o["z"]))
print("not reachable at 1 m resolution (doors open / lake lane blocked):", unreach)
def sp(a, b):
    dd = {a: 0}; q = deque([a])
    while q:
        c = q.popleft()
        if c == b: return dd[c]
        for n in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)):
            if n in rall and n not in dd: dd[n] = dd[c] + 1; q.append(n)
bhc = (round(POS["BH"][0]), round(POS["BH"][1]))
route = sp(st, bhc) * CS
print("pool cells", len(POOLSET), "lane", len(POOLLANE), [(TNAME[k]) for k, e in enumerate(EDGES) if e.get("pool")]); print("shortest route start->boss: %.0f m" % route, "| floor cells", len(F) - len(LAKE), "| lake", len(LAKE), "| rooms", len(R), "| tunnels", len(EDGES))

# ------------------------------------------------------------------ zones, objectives, scene
def zrect(cells, pad=.5): xs_ = [c[0] for c in cells]; zs_ = [c[1] for c in cells]; i0, i1, j0, j1 = min(xs_), max(xs_), min(zs_), max(zs_); return dict(x=X((i0 + i1) / 2), z=X((j0 + j1) / 2), w=(i1 - i0 + 1 + 2 * pad) * CS, d=(j1 - j0 + 1 + 2 * pad) * CS)
RATE = 85
POOLS = [(["goblin_skirmisher", "bandit_rogue", "venom_spider"], [2, 3]), (["venom_spider", "stone_gargoyle", "bandit_rogue", "goblin_skirmisher"], [3, 4]), (["frost_wraith", "stone_gargoyle", "venom_spider"], [4, 5]),
         (["frost_wraith", "stone_gargoyle", "dark_cultist"], [4, 5]), (["dark_cultist", "frost_wraith", "stone_gargoyle"], [5, 6])]
ZONES = []
for n in sorted(SAFE | {"E", "AN", "BH", "K1", "K2"}): ZONES.append(dict(zrect([c for c, t in F.items() if t == n]), safe=True))
for n in sorted(R):
    if n in SAFE: continue
    pl, lv = POOLS[TIER[n]]; ZONES.append(dict(zrect([c for c, t in F.items() if t == n]), pool=pl, level=lv, rate=RATE))
for k, e in enumerate(EDGES):                                       # tunnels: boxes of 7 x 7 cells so they follow the curves
    pl, lv = POOLS[max(TIER[e["a"]], TIER[e["b"]])]; tiles = {}
    for c in TUN[k]: tiles.setdefault((c[0] // 7, c[1] // 7), []).append(c)
    for cells in tiles.values(): ZONES.append(dict(zrect(cells, 0.5), pool=pl, level=lv, rate=RATE))

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
MINIMAP = dict(cell=CS, rects=_runs([c for c in F if c not in WATER]), water=_runs(list(WATER)))
xs = [c[0] for c in F]; zs = [c[1] for c in F]
d = dict(name="Hollow Cave", kit="", tile=4, pieces=P, colliders=COL, npcs=NP, events=EV, decals=DEC, story=True, restart="dg_", objectives=OBJ, autorun=AUTO,
         encounters=dict(rate=RATE, level=[2, 5], pool=["goblin_skirmisher", "bandit_rogue", "venom_spider", "stone_gargoyle", "frost_wraith", "dark_cultist"], zones=ZONES, text="Something stirs in the dark... monsters attack!"),
         bounds=dict(minX=X(min(xs)) - 6, maxX=X(max(xs)) + 6, minZ=X(min(zs)) - 6, maxZ=X(max(zs)) + 6), spawn=dict(x=SPAWN[0], z=SPAWN[1]), playerHeight=2.4, minimap=MINIMAP,
         sky=dict(type="gradient", stops=[[0, "#05070d"], [1, "#0d1420"]]), fx=[dict(type="dust", amount=.25)],
         light=dict(dir=[-0.35, -1, -0.25], color=[0.74, 0.82, 1.0], ambient=[0.36, 0.42, 0.56]), fog=dict(color=[0.035, 0.06, 0.105], near=32, far=100), cull=165, music=dict(url="/assets/Music/mp3/11. Dangerous Cave.mp3"))
import cave_story; cave_story.apply(d)                       # story layer: Sera joins on the island, guards vs the Sovereign, the knock-out (cave_story.py)
_gx = next(e for e in d["events"] if e["id"] == "dg_guards_cs"); assert cell_of(_gx["x"], _gx["z"]) in F, "guard cutscene trigger is not on floor"
for _n in d["npcs"]:
    if _n["id"] in ("dg_cap", "dg_gd1", "dg_gd2", "dg_gd3"): assert cell_of(_n["x"], _n["z"]) in F, "guard %s is not on floor" % _n["id"]
os.makedirs(OUT, exist_ok=True); json.dump(d, open(os.path.join(OUT, "dungeon.json"), "w"), separators=(",", ":"))
print("pieces", len(P), "walls", len(wallc), "colliders", len(COL), "npcs", len(NP), "events", len(EV), "decals", len(DEC), "chests", len(CHESTS), "chunks", len(chunks), "bounds", d["bounds"])
json.dump(dict(rooms={n: [X(POS[n][0]), X(POS[n][1])] for n in POS},
               tunnels={TNAME[k]: [[round(X(a), 1), round(X(b), 1)] for a, b in e["poly"][::2]] for k, e in enumerate(EDGES) if e.get("poly")}),
          open(os.path.join(OUT, "dungeon_layout.json"), "w"), separators=(",", ":"))


# ------------------------------------------------------------------ layout preview
try:
    from PIL import Image, ImageDraw
    S = 4; mnx, mxx, mnz, mxz = min(xs), max(xs), min(zs), max(zs); W_ = (mxx - mnx + 3) * S; H_ = (mxz - mnz + 3) * S
    im = Image.new("RGB", (W_, H_), (12, 14, 20)); dr_ = ImageDraw.Draw(im)
    for (i, j), t in F.items():
        col = (60, 110, 190) if (i, j) in LAKE else ((200, 150, 70) if t in ("K1", "K2") else ((110, 110, 125) if t.startswith("t_") else (90, 130, 100)))
        x0, y0 = (i - mnx + 1) * S, (j - mnz + 1) * S; dr_.rectangle([x0, y0, x0 + S - 1, y0 + S - 1], fill=col)
    for gi, g in GATES.items():
        for c in g["cells"]: x0, y0 = (c[0] - mnx + 1) * S, (c[1] - mnz + 1) * S; dr_.rectangle([x0, y0, x0 + S - 1, y0 + S - 1], fill=(255, 80, 80))
    evx = {e_["id"]: e_ for e_ in EV}
    for k, (key, x, z, t) in enumerate(CHESTS):
        x, z = evx[key]["x"], evx[key]["z"]
        cx, cy = (x / CS - mnx + 1) * S, (z / CS - mnz + 1) * S; dr_.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(255, 220, 60))
    for n in NP:
        if n["id"].startswith("dg_g") or n["id"] == "dg_boss":
            cx, cy = (n["x"] / CS - mnx + 1) * S, (n["z"] / CS - mnz + 1) * S; dr_.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(255, 60, 60))
    for n, (a_, b_) in POS.items(): dr_.text(((a_ - mnx + 1) * S - 8, (b_ - mnz + 1) * S - 5), n, fill=(255, 255, 255))
    im.save(os.path.join(OUT, "cave_layout.png"))
except Exception as ex: print("preview skipped", ex)
json.dump({TNAME[k]: [[round(X(a), 1), round(X(b), 1)] for a, b in e["poly"][::6]] for k, e in enumerate(EDGES) if e.get("poly")}, open(os.path.join(OUT, "tunnels.json"), "w"))

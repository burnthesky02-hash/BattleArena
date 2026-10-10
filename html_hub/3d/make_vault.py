"""Builds html_hub/3d/vault.json: "The Shard Vault" (claude/lyra-and-shard-vault.md), v2: a huge floating-walkway maze in a starless void.
Kit: Assets/3D/Megastructure (floor slabs, pillars, arches, lamps, monoliths; see convert_megastructure.py) plus a few Dungeon-kit props (gates, crystals, tablets).
Layout, on a global 6 m grid (cell gx,gz is centred at x=gx*6, z=gz*6; x = east, z = south):
  Nexus (5x5 cells) in the middle, spawn + waking stone + rest crystal + the lift back to the base (south).
  West maze A (cyan), east maze B (violet, gate opens when vt_g1 falls), north maze C (amber, gate opens when vt_g2 falls).
  Each maze is 12x12 rooms (23x23 cells, ~138 m) carved with a seeded recursive backtracker, with a few loops braided in. The farthest room holds a guardian.
  After C's guardian (vt_g3) the sealed door at the north edge opens onto a long bridge and the Warden's arena.
Everything that is not a floor cell is void, fenced by colliders (all non-floor cells touching a floor cell).
Encounters are per-maze (zone.pool / zone.level_rel / zone.rate, see encounterStep in hub3d.js); the Nexus, bridges and arena are safe.
Run:  python make_vault.py [outdir]. Re-running overwrites hand edits made in /builder3d."""
import json, math, os, random, sys
from collections import deque
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
MG, DG = "/assets/3D/Megastructure/", "/assets/3D/Dungeon/"
BASE = (-23, -3)                       # where the lift comes out on the asteroid (outside the hatch's solid area; see make_asteroid.py)
CS = 6.0                               # cell size in metres
SEED = 20260
P, COL, DEC, NP, EV = [], [], [], [], []
def put(n, x, z, rot=0, y=0, sc=1, hide=None, pre=MG):
    p = [pre + n, round(x, 3), round(z, 3), rot, round(y, 3), sc]
    if hide: p.append(hide)
    P.append(p)
def block(x, z, w, d, hide=None):
    c = {"x": round(x, 3), "z": round(z, 3), "w": round(w, 3), "d": round(d, 3)}
    if hide: c["hideIf"] = hide
    COL.append(c)
def glow(x, z, r, c): DEC.append(dict(type="glow", x=round(x, 2), z=round(z, 2), r=r, color=c))
def W(g): return g * CS
CA, CB, CC, VIO, WHT = [.35, .85, 1, .22], [.72, .42, 1, .24], [1, .6, .3, .24], [.7, .42, 1, .24], [.75, .85, 1, .14]

# ------------------------------------------------------------------ floor plan
F = {}                                  # (gx,gz) -> sector tag
def fl(g, tag): F[g] = tag
# Nexus
for gx in range(-2, 3):
    for gz in range(-2, 3): fl((gx, gz), "N")
fl((0, 3), "N")                         # lift pad
def maze(name, ox, oz, entry, rng, braid=0.10, N=23, force_top=False, target=10):
    """A twisty maze whose junction rooms are (odd,odd) cells, plus big open ROOMS: rectangles of 2-3 x 2-3 maze rooms with their walls removed.
    entry = local boundary cell of the door. Returns (adj, entry room, dist map, rects)."""
    R = (N - 1) // 2
    adj = {(i, j): set() for i in range(R) for j in range(R)}
    ex, ez = entry
    er = (min(max((ex - 1) // 2, 0), R - 1), min(max((ez - 1) // 2, 0), R - 1))
    seen = {er}; stack = [er]
    while stack:
        c = stack[-1]; nb = [n for n in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)) if n in adj and n not in seen]
        if not nb: stack.pop(); continue
        n = rng.choice(nb); adj[c].add(n); adj[n].add(c); seen.add(n); stack.append(n)
    for c in list(adj):                                         # a few loops so wall-following does not solve it
        for n in ((c[0] + 1, c[1]), (c[0], c[1] + 1)):
            if n in adj and n not in adj[c] and rng.random() < braid: adj[c].add(n); adj[n].add(c)
    def bfs():
        d = {er: 0}; q = deque([er])
        while q:
            c = q.popleft()
            for n in adj[c]:
                if n not in d: d[n] = d[c] + 1; q.append(n)
        return d
    rects, taken = [], set()
    def rooms_of(i0, j0, w, h): return [(i, j) for i in range(i0, i0 + w) for j in range(j0, j0 + h)]
    def can(i0, j0, w, h):
        rs = rooms_of(i0, j0, w, h)
        return i0 >= 0 and j0 >= 0 and i0 + w <= R and j0 + h <= R and not any(r in taken for r in rs) and er not in rs
    def add(i0, j0, w, h):
        rs = rooms_of(i0, j0, w, h)
        for (i, j) in rooms_of(i0 - 1, j0 - 1, w + 2, h + 2): taken.add((i, j))          # keep one maze room between two halls
        for r in rs:
            for n in ((r[0] + 1, r[1]), (r[0], r[1] + 1)):
                if n in rs: adj[r].add(n); adj[n].add(r)
        x0, x1 = ox + 2 * i0 + 1, ox + 2 * (i0 + w - 1) + 1; z0, z1 = oz + 2 * j0 + 1, oz + 2 * (j0 + h - 1) + 1
        rects.append(dict(i0=i0, j0=j0, w=w, h=h, rooms=rs, x0=x0, x1=x1, z0=z0, z1=z1, cx=(x0 + x1) / 2, cz=(z0 + z1) / 2))
    if force_top:                                               # C: a hall behind the sealed north door, at the farthest top-row room
        d0 = bfs(); gt = max((d0[(i, 0)], (i, 0)) for i in range(R))[1]
        i0 = min(max(gt[0] - 1, 0), R - 3)
        if can(i0, 0, 3, 2): add(i0, 0, 3, 2)
    tries = 0
    while len(rects) < target and tries < 600:
        tries += 1
        w, h = rng.choice([(2, 2), (2, 2), (2, 3), (3, 2), (3, 3), (2, 2), (3, 2)])
        i0, j0 = rng.randrange(0, R - w + 1), rng.randrange(0, R - h + 1)
        if can(i0, j0, w, h): add(i0, j0, w, h)
    for c, ns in adj.items():
        fl((ox + 2 * c[0] + 1, oz + 2 * c[1] + 1), name)
        for n in ns: fl((ox + c[0] + n[0] + 1, oz + c[1] + n[1] + 1), name)
    for rc in rects:
        for x in range(rc["x0"], rc["x1"] + 1):
            for z in range(rc["z0"], rc["z1"] + 1): fl((x, z), name); RECTCELLS.add((x, z))
    fl((ox + ex, oz + ez), name)
    return adj, er, bfs(), rects
RECTCELLS = set()
rng = random.Random(SEED)
AO, BO, CO = (-35, -11), (13, -11), (-11, -35)
adjA, erA, dA, rcA = maze("A", *AO, (22, 11), rng)
adjB, erB, dB, rcB = maze("B", *BO, (0, 11), rng)
adjC, erC, dC, rcC = maze("C", *CO, (11, 22), rng, force_top=True)
def guard_rect(rects, dist):                                    # the hall farthest (by walking) from the door
    return max(rects, key=lambda r: min(dist[x] for x in r["rooms"]))
grA, grB, grC = guard_rect(rcA, dA), guard_rect(rcB, dB), rcC[0]
gAc, gBc, gCc = (grA["cx"], grA["cz"]), (grB["cx"], grB["cz"]), (grC["cx"], grC["cz"])
grA["guard"] = grB["guard"] = grC["guard"] = True
# connectors Nexus <-> mazes (the door cells are part of the mazes)
for gx in range(-12, -2): fl((gx, 0), "cA")
for gx in range(3, 13): fl((gx, 0), "cB")
for gz in range(-12, -2): fl((0, gz), "cC")
# C's north door, bridge and the Warden's arena
gC = (grC['i0'] + 1, 0)
bossdoor = (grC['x0'] + (grC['x1'] - grC['x0']) // 2, CO[1])
fl(bossdoor, "C")
for gz in range(-39, -35): fl((bossdoor[0], gz), "cD")
arena_c = (bossdoor[0], -44)
for gx in range(arena_c[0] - 4, arena_c[0] + 5):
    for gz in range(-48, -39): fl((gx, gz), "D")

# ------------------------------------------------------------------ floor slabs and the fence
for (gx, gz) in sorted(F): put("SM_floor_module_02", W(gx), W(gz), 0, -2.4, 1.2)
blocked = set()
for (gx, gz) in F:
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if (gx + dx, gz + dz) not in F: blocked.add((gx + dx, gz + dz))
WALL_H = 6.0                                                   # visible height; low enough that the camera still sees the party over the wall in front of it
walls = {c for c in blocked if any((c[0] + dx, c[1] + dz) in F for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
for (gx, gz) in sorted(walls): put("SM_dg_wall", W(gx), W(gz), 0, WALL_H - 4.2 * 1.5, 1.5, pre=DG)
rows = {}
for (gx, gz) in blocked: rows.setdefault(gz, []).append(gx)
for gz, xs in rows.items():
    xs.sort(); s = prev = xs[0]
    for x in xs[1:] + [None]:
        if x is None or x != prev + 1:
            block(W((s + prev) / 2), W(gz), (prev - s + 1) * CS, CS); s = x
        if x is not None: prev = x

# ------------------------------------------------------------------ props
def pillar(x, z, kind=None, sc=1.0):
    k = kind or rng.choice(["03", "04", "05"])
    put("SM_architecture_module_" + k, x, z, rng.choice([0, 90]), -2.4, sc); block(x, z, 1.5 * sc, 1.5 * sc)
def lamp(x, z, col, r=7.0):
    put("SM_lamp_big", x, z, 0, 0.0, 1.6); glow(x, z, r, col)
def crystal(x, z, rot=0, rad=5.0, col=VIO, sc=1.0):
    put("SM_dg_crystal", x, z, rot, 0, sc, pre=DG); block(x, z, 0.9 * sc, 0.9 * sc); glow(x, z, rad, col)
def brazier(x, z, rad=6.0, col=CA):
    put("SM_dg_brazier", x, z, pre=DG); put("SM_dg_flame", x, z, 0, 1.55, 1.0, pre=DG); block(x, z, 1.1, 1.1); glow(x, z, rad, col)
def tablet(key, name, x, z, rot, text, ex=0, ez=1.8):
    put("SM_dg_tablet", x, z, rot, pre=DG); block(x, z, 1.6 if rot % 180 == 0 else 0.5, 0.5 if rot % 180 == 0 else 1.6)
    EV.append(dict(id=key, name=name, x=round(x + ex, 2), z=round(z + ez, 2), w=3.2, d=2.4, trigger="talk", prompt="Read the tablet",
                   actions=[dict(type="say", who="Etched Plate", text=text)]))
SECT = {"A": CA, "B": CB, "C": CC, "D": VIO}
TIER = {"A": 1, "B": 2, "C": 3, "D": 3}
LOOT_ITEMS = {1: ["potion", "ether", "antidote"], 2: ["hi_potion", "ether", "antidote", "potion"], 3: ["hi_potion", "phoenix_down", "ether"]}
# equipment ids by rarity (data/equipment_db.py), picked at build time
EQ_IDS = {"rare":["knights_blade","falcon_saber","war_hatchet","bearded_cleaver","chapel_mace","skullcracker","twinfang_daggers","serrated_kris","longshot_bow","hawkeye_recurve","crystal_staff","emberwood_staff","moonlit_wand","chorister_wand","tome_of_mending","gilded_hymnal","bulwark_shield","wardens_tower_shield","parrying_buckler","brawlers_buckler","swift_quiver","huntsmans_quiver","crystal_focus","warded_focus","armor_light_rare","armor_medium_rare","armor_heavy_rare","helm_light_rare","helm_medium_rare","helm_heavy_rare","boots_light_rare","boots_medium_rare","boots_heavy_rare","sages_ring","gladiators_signet","ring_of_swift_feet"],"epic":["warshard","blade_of_the_underdog","gorehowl_splitter","ravagers_axe","aegis_mace","sunforged_mace","nightfall_fang","cutthroats_favor","stormcaller_bow","huntresss_longbow","staff_of_the_tempest","archmages_focus","wand_of_the_faithful","wraithglass_wand","tome_of_unbroken_faith","codex_of_the_ward","aegis_shield","stormward_shield","featherweight_buckler","gamblers_buckler","windrunner_quiver","quiver_of_fortune","focus_of_clarity","stormglass_focus","armor_light_epic","armor_medium_epic","armor_heavy_epic","helm_light_epic","helm_medium_epic","helm_heavy_epic","boots_light_epic","boots_medium_epic","boots_heavy_epic","band_of_vigor","talisman_of_the_veteran","ring_of_the_gambler"],"legendary":["flameheart_blade","duskbreaker","titanfall_axe","stormrend","hammer_of_verdicts","dawnbreakers_mace","vexs_bite","whisper_of_ruin","gale_piercer","sureshot_of_finn","staff_of_starfall","world_ash_branch","wand_of_the_last_light","seraphs_wandrest","grand_tome_of_salvation","liturgy_of_dawn","unbreakable_bulwark","dawnwall_shield","vipers_buckler","fortunes_buckler","stormfeather_quiver","quiver_of_the_hundred","focus_of_the_infinite","aegis_focus","armor_light_legendary","armor_medium_legendary","armor_heavy_legendary","helm_light_legendary","helm_medium_legendary","helm_heavy_legendary","boots_light_legendary","boots_medium_legendary","boots_heavy_legendary","crown_of_the_undefeated","heartstone_amulet","ring_of_the_arcanist"],"mythic":["kaels_edge","thornes_reckoning","garricks_bulwark_mace","kaels_shadow_twin","rooks_windcaller","lyras_starlight_staff","seras_mercy_wand","osrics_final_verse","garricks_last_stand","thornes_offhand_edge","finns_endless_quiver","lyras_second_light","armor_light_mythic","armor_medium_mythic","armor_heavy_mythic","helm_light_mythic","helm_medium_mythic","helm_heavy_mythic","boots_light_mythic","boots_medium_mythic","boots_heavy_mythic","champions_medallion","aegis_of_the_colosseum"]}
KEN = "/assets/3D/kenney_retro-fantasy-kit/Models/GLB format/"
CHESTS = []
def make_loot(tier, rg):
    r = rg.random(); loot = {}
    gold = {1: (250, 650), 2: (550, 1150), 3: (950, 1900)}[tier]
    if r < 0.42: loot["gold"] = rg.randrange(gold[0], gold[1], 10)
    elif r < 0.67:
        loot["items"] = {rg.choice(LOOT_ITEMS[tier]): rg.randint(2, 4)}
        if rg.random() < .5: loot["items"][rg.choice(LOOT_ITEMS[tier])] = rg.randint(1, 3)
        loot["gold"] = rg.randrange(gold[0] // 3, gold[1] // 3, 10)
    elif r < 0.82: loot["gems"] = rg.randint(*{1: (8, 20), 2: (15, 35), 3: (30, 60)}[tier]); loot["gold"] = rg.randrange(gold[0] // 4, gold[1] // 4, 10)
    else:
        rar = rg.choices({1: ["rare", "epic"], 2: ["epic", "legendary"], 3: ["legendary", "mythic"]}[tier], weights=[78, 22])[0]
        if EQ_IDS.get(rar): loot["equipment"] = [rg.choice(EQ_IDS[rar])]
        loot["shards"] = rg.randint(5, 25) * tier
    if tier >= 2 and rg.random() < .18: loot["tickets"] = {"common": rg.randint(1, 2)}
    return loot
def chest(x, z, tier, sector):
    key = "vc_%s%d" % (sector, len([c for c in CHESTS if c[0].startswith("vc_" + sector)]) + 1)
    rot = rng.choice([0, 90, 180, 270]); CHESTS.append((key, x, z))
    put("SM_TreasureChest", x, z, rot, 0, 1.0, key, pre="/assets/3D/Generated/")
    block(x, z, 1.6, 1.6)
    EV.append(dict(id=key, name="Treasure chest", x=round(x, 2), z=round(z, 2), w=4.2, d=4.2, trigger="talk", prompt="Open the chest", hideIf=key,
                   actions=[dict(type="flag", key=key), dict(type="chest", loot=make_loot(tier, rng))]))
def hall_pillars(rc, sc=1.3):
    for (cx_, cz_, sx, sz) in ((rc["x0"], rc["z0"], -1, -1), (rc["x1"], rc["z0"], 1, -1), (rc["x0"], rc["z1"], -1, 1), (rc["x1"], rc["z1"], 1, 1)):
        pillar(W(cx_) + sx * (CS / 2 - 0.9), W(cz_) + sz * (CS / 2 - 0.9), sc=sc)
for name, o, adj, rects, er in (("A", AO, adjA, rcA, erA), ("B", BO, adjB, rcB, erB), ("C", CO, adjC, rcC, erC)):
    col, tier = SECT[name], TIER[name]
    inrect = {r for rc in rects for r in rc["rooms"]}
    spare = []
    for rc in rects:                                              # open halls: corner pillars, a lamp (and a chest in most)
        hall_pillars(rc, 1.3)
        if rc.get("guard"): continue
        lamp(W(rc["cx"]), W(rc["cz"]), col, 11)
        if rng.random() < 0.75:
            edge = rng.choice(["n", "s", "e", "w"])
            mx, mz = (rc["x0"] + rc["x1"]) // 2, (rc["z0"] + rc["z1"]) // 2
            cell = {"n": (mx, rc["z0"]), "s": (mx, rc["z1"]), "w": (rc["x0"], mz), "e": (rc["x1"], mz)}[edge]
            chest(W(cell[0]), W(cell[1]), tier, name)
    for c in sorted(adj):                                         # corridors and junction rooms outside the halls
        if c in inrect or c == er: continue
        cx, cz = W(o[0] + 2 * c[0] + 1), W(o[1] + 2 * c[1] + 1)
        if len(adj[c]) == 1:                                      # a dead end: sometimes a chest at its end
            if rng.random() < 0.34: chest(cx, cz, tier, name)
            else: spare.append((cx, cz))
            continue
        r = rng.random()
        if r < 0.20: pillar(cx + rng.choice([-1, 1]) * (CS / 2 - 0.9), cz + rng.choice([-1, 1]) * (CS / 2 - 0.9), sc=rng.choice([1.0, 1.0, 1.3]))
        elif r < 0.26: lamp(cx, cz, col)
        if rng.random() < 0.05: glow(cx, cz, 9, col)
    rng.shuffle(spare)
    while spare and len([c for c in CHESTS if c[0].startswith("vc_" + name)]) < 7:      # make every sector worth exploring
        chest(*spare.pop(), tier, name)
    for (cx, cz) in spare:
        if rng.random() < .3: lamp(cx, cz, col, 6)
    for (gx, gz), t in list(F.items()):                           # ring arches over passages
        if t != name or (gx, gz) in RECTCELLS: continue
        lx, lz = gx - o[0], gz - o[1]
        if (lx + lz) % 2 == 1 and rng.random() < 0.14:
            put("SM_arch_04" if rng.random() < .6 else "SM_arch_01", W(gx), W(gz), 90 if lz % 2 == 1 else 0, 0, 0.8)
# sector doors and bridges: bigger arches
for (gx, gz, rot) in [(-13, 0, 90), (13, 0, 90), (0, -13, 0), (-8, 0, 90), (8, 0, 90), (0, -8, 0), (bossdoor[0], -36, 0), (bossdoor[0], -38, 0)]:
    put("SM_arch_03", W(gx), W(gz), rot, 0, 0.8)
for g in [(-6, 0, 90), (6, 0, 90), (0, -6, 0)]: put("SM_arch_04", W(g[0]), W(g[1]), g[2], 0, 0.8)

# ------------------------------------------------------------------ the Nexus
put("SM_dg_dais", 0, -2.0, 0, 0, 1.0, pre=DG)
put("SM_dg_crystal", 0, -2.0, 0, 0, 2.6, pre=DG); block(0, -2.0, 2.6, 2.6); glow(0, -2.0, 11, WHT)
for sx in (-1, 1):
    for sz in (-1, 1):
        put("SM_architecture_module_05", sx * 12.5, sz * 12.5, 0, -2.4, 1.3); block(sx * 12.5, sz * 12.5, 2.0, 2.0)
        lamp(sx * 8.0, sz * 8.0, WHT, 8.0)
tablet("vt_t0", "Nexus plate", -6, 14.2, 0, "THE SHARD VAULT. THE WALKWAYS WERE LAID OVER NOTHING SO THAT NOTHING COULD BE HIDDEN ON THEM. THREE WARDENS KEEP THREE ROADS. THE FOURTH ROAD IS KEPT BY THE FIRST WARDEN OF ALL.")
tablet("vt_t1", "West plate", -39, -2.3, 0, "WEST ROAD. THE SENTINEL MARCHES THE LOOPS. THE MAZE WAS MADE TO TIRE THE LIVING; THE SENTINEL HAS NEVER BEEN TIRED.")
tablet("vt_t2", "East plate", 39, -2.3, 0, "EAST ROAD. THE PHASE STALKER HUNTS BY SMELL. IT HAS LEARNED THE SMELL OF THE OTHER SIDE, AND YOU SMELL OF IT.")
tablet("vt_t3", "North plate", 2.3, -39, 90, "NORTH ROAD. THE COLOSSUS STANDS AT THE DOOR TO THE CORE. IT WAS NOT BUILT TO KEEP YOU OUT. IT WAS BUILT TO KEEP SOMETHING IN.", ex=-1.8, ez=0)
put("SM_dg_block", 9.0, 9.0, 0, 0, 1.2, pre=DG); block(9.0, 9.0, 1.2, 1.2)
EV.append(dict(id="vt_altar", name="Waking stone", x=9.0, z=10.4, w=3.0, d=2.4, trigger="talk", prompt="Touch the stone",
               actions=[dict(type="say", who="Waking Stone", text="The stone hums against your palm. Across the void, the guardians reset and the sealed gates slide shut."),
                        dict(type="reset_progress", prefix="vt_")]))
put("SM_dg_crystal", -9.0, 9.0, 40, 0, 1.2, pre=DG); block(-9.0, 9.0, 1.2, 1.2); glow(-9.0, 9.0, 7, CA)
EV.append(dict(id="vt_rest", name="Rest crystal", x=-9.0, z=10.4, w=3.0, d=2.4, trigger="talk", prompt="Rest at the crystal",
               actions=[dict(type="say", who="", text="Soft light settles over the party. Wounds close and breath comes easy."), dict(type="rest")]))
lamp(0, 18, WHT, 6); glow(0, 18, 4.5, [.7, .9, 1, .16])
EV.append(dict(id="vt_exit", name="Lift to the base", x=0, z=18.6, w=6, d=3.2, trigger="talk", prompt="Ride the lift up to Outpost Kestrel",
               actions=[dict(type="warp", scene="asteroid", x=BASE[0], z=BASE[1])]))

# ------------------------------------------------------------------ gates (Dungeon-kit gate, scaled to a 6 m cell)
def gate(gx, gz, rot, key):
    x, z = W(gx), W(gz)
    put("SM_dg_gate", x, z, rot, 0, 1.5, key, pre=DG)
    block(x, z, 1.5 if rot else 6.0, 6.0 if rot else 1.5, key)
gate(5, 0, 90, "vt_g1"); gate(0, -5, 0, "vt_g2"); gate(bossdoor[0], -36, 0, "vt_g3")

# ------------------------------------------------------------------ guardians, beacons and the Warden
def foe(key, name, sprite, c, tint, line, boss_id, lv, col, h=2.8):
    x, z = W(c[0]), W(c[1])
    NP.append(dict(id=key, name=name, title="Hostile", sprite=sprite, x=round(x, 2), z=round(z, 2), h=h, tint=tint, hideIf=key, reach=5.0,
                   actions=[dict(type="say", who=name, text=line), dict(type="battle", key=key, boss=boss_id, level=lv)]))
    glow(x, z, 12, col); crystal(x - 2.2, z - 2.2, 20, 5, col, 1.3); crystal(x + 2.2, z - 2.2, 130, 5, col, 1.3)
    bx, bz = x, z + 2.4        # beacon: appears once the guardian is down
    put("SM_dg_crystal", bx, bz, 0, 0, 2.2, hide="!" + key, pre=DG); put("SM_lamp_big", bx - 1.9, bz + 0.2, 0, 0, 1.3, hide="!" + key); put("SM_lamp_big", bx + 1.9, bz + 0.2, 0, 0, 1.3, hide="!" + key)
    DEC.append(dict(type="glyph", x=round(bx, 2), z=round(bz, 2), r=3.6, spin=40, color=[.8, .6, 1, 1], showIf=key)); DEC.append(dict(type="glow", x=round(bx, 2), z=round(bz, 2), r=9, color=[.7, .42, 1, .5], showIf=key))
    EV.append(dict(id="beacon_" + key, name="Rift beacon", x=round(x, 2), z=round(z + 2.4, 2), w=3.4, d=2.6, trigger="talk", prompt="Step into the rift beacon (back to the Nexus)", showIf=key,
                   actions=[dict(type="say", who="", text="A rift beacon flares up from the floor and pulls at you."), dict(type="flash"), dict(type="tp", x=0, z=10)]))
foe("vt_g1", "Vault Sentinel", "Draven", gAc, [.6, .8, 1.3, 1], "INTRUDER. THE EAST GATE IS SEALED UNTIL I AM UNMADE. STATE YOUR ENDING.", "vault_sentinel_boss", 12, CA)
foe("vt_g2", "Phase Stalker", "Kenji", gBc, [.9, .55, 1.3, 1], "...you smell like the other side. Like the rift. Good.", "phase_stalker_boss", 13, CB)
foe("vt_g3", "Rift Colossus", "Yulia", gCc, [1.3, .7, .55, 1], "THE CORE IS NOT FOR YOU. THE CORE IS NOT FOR ANYONE.", "rift_colossus_boss", 15, CC, 3.4)
# Warden arena
ax, az = W(arena_c[0]), W(arena_c[1])
for sx in (-1, 1):
    for sz in (-1, 1):
        pillar(ax + sx * 21, az + sz * 21, "05", 1.4); lamp(ax + sx * 15, az + sz * 15, VIO, 9)
for k in range(8):
    a = k / 8 * math.tau
    crystal(ax + math.cos(a) * 11, az + math.sin(a) * 11 + 2, int(a * 57), 5, VIO, 1.2)
glow(ax, az - 6, 14, VIO)
tablet("vt_t4", "Arena plate", ax - 2.2, W(-38) - 2.3, 0, "BEYOND THIS BRIDGE THE VAULT'S WARDEN KEEPS THE SHARD. IT WILL NOT STOP FOR ANY VOICE BUT ITS MAKERS'.")
NP.append(dict(id="vt_boss", name="Vault Warden", title="Keeper of the Shard", sprite="Rook", x=round(ax, 2), z=round(az - 8, 2), h=4.4, tint=[.75, .55, 1.3, 1], hideIf="vt_boss", reach=6.0,
               actions=[dict(type="say", who="Vault Warden", text="THE SHARD IS NOT TO BE CARRIED. THE SHARD IS NOT TO BE TOUCHED."),
                        dict(type="say", who="Vault Warden", text="VISITORS WITHOUT A KEY ARE TO BE UNMADE."), dict(type="battle", key="vt_boss", boss="vault_warden_boss")]))
NP.append(dict(id="vt_lyra", name="Lyra", title="Rift Scholar", sprite="Lyra", x=round(ax, 2), z=round(az + 4, 2), h=2.4, tint=[1, 1, 1.1, 1], showIf="vt_boss", reach=5.0,
               actions=[dict(type="say", who="Lyra", text="It is quiet. The Shard stopped singing the moment the Warden fell."),
                        dict(type="say", who="Lyra", text="The heart of it is still warm, though. Whatever carried it here left a trail, and the trail leads further than this base."),
                        dict(type="say", who="Lyra", text="Let's go back up and tell Rhea. This was only the first piece.")]))
EV.append(dict(id="vt_portal", name="Lift to the base", x=round(ax, 2), z=round(az + 8, 2), w=5, d=3, trigger="talk", prompt="Ride the lift up to Outpost Kestrel", showIf="vt_boss",
               actions=[dict(type="warp", scene="asteroid", x=BASE[0], z=BASE[1])]))
lamp(ax, az + 8, WHT, 6); glow(ax, az + 8, 4.5, [.7, .9, 1, .16])

# ------------------------------------------------------------------ the void: monoliths below, rings above
rb = random.Random(SEED + 1)
for _ in range(46):
    nm = rb.choice(["09", "10", "13", "09", "13"]); sc = rb.uniform(2.0, 4.2)
    h = {"09": 21.4, "10": 21.4, "13": 21.4}[nm]
    put("SM_architecture_module_" + nm, rb.uniform(-250, 250), rb.uniform(-320, 60), rb.choice([0, 90, 45]), -(h * sc) - 8 - rb.uniform(0, 26), sc)
for _ in range(7):
    put("SM_triangle_arch", rb.uniform(-260, 260), rb.uniform(-330, 80), rb.uniform(0, 180), rb.uniform(-30, 30), rb.uniform(1.5, 2.6))

# ------------------------------------------------------------------ verify the plan
def reach(start, opened):
    seen = {start}; q = deque([start])
    walls = {(5, 0): "vt_g1", (0, -5): "vt_g2", (bossdoor[0], -36): "vt_g3"}
    while q:
        c = q.popleft()
        for n in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)):
            if n in F and n not in seen and not (n in walls and walls[n] not in opened): seen.add(n); q.append(n)
    return seen
r0 = reach((0, 0), set()); r3 = reach((0, 0), {"vt_g1", "vt_g2", "vt_g3"})
assert gAc in r0 and gBc not in r0 and gCc not in r0, "gates must close off B and C"
assert len(r3) == len(F), (len(r3), len(F))
assert gBc in reach((0, 0), {"vt_g1"}) and gCc not in reach((0, 0), {"vt_g1"})
assert arena_c not in reach((0, 0), {"vt_g1", "vt_g2"}) and arena_c in r3
def sp(a, b):                           # shortest path in cells
    dd = {a: 0}; q = deque([a])
    while q:
        c = q.popleft()
        if c == b: return dd[c]
        for n in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)):
            if n in F and n not in dd: dd[n] = dd[c] + 1; q.append(n)
legs = [sp((0, 0), gAc), sp((0, 0), gBc), sp((0, 0), gCc), sp(gCc, arena_c)]
print("shortest legs (m):", [l * CS for l in legs], "total one-way", sum(legs) * CS)

def box(cells):
    xs = [c[0] for c in cells]; zs = [c[1] for c in cells]
    return dict(x=W((min(xs) + max(xs)) / 2), z=W((min(zs) + max(zs)) / 2), w=(max(xs) - min(xs) + 1) * CS, d=(max(zs) - min(zs) + 1) * CS)
def zone(tag, pool_ids, lvl, rate): z = box([c for c, t in F.items() if t == tag]); z.update(pool=pool_ids, level=lvl, rate=rate); return z
ZONES = [zone("A", ["shard_sentry", "arc_drone", "rift_leech", "lattice_medic"], [10, 12], 40),
         zone("B", ["phase_hound", "void_acolyte", "frost_mirage", "arc_drone", "lattice_medic"], [11, 14], 38),
         zone("C", ["forge_juggernaut", "null_reaper", "void_acolyte", "phase_hound", "rift_leech"], [13, 15], 36)]
xs = [c[0] for c in F]; zs = [c[1] for c in F]
d = dict(name="The Shard Vault", kit="", tile=4, pieces=P, colliders=COL, npcs=NP, events=EV, decals=DEC, story=True, restart="vt_",
         encounters=dict(rate=40, level=[10, 12], pool=ZONES[0]["pool"], zones=ZONES, text="The vault wakes around you... something steps out of the void!"),
         bounds=dict(minX=W(min(xs)) - 6, maxX=W(max(xs)) + 6, minZ=W(min(zs)) - 6, maxZ=W(max(zs)) + 6), spawn=dict(x=0, z=10), playerHeight=2.4,
         sky=dict(type="layers", base=dict(type="gradient", stops=[[0, "#02010a"], [.5, "#0a0620"], [1, "#1b1038"]]),
                  layers=[dict(url="/assets/Backgrounds/layers/stars.webp", y=.30, height=.66, parallax=.04, alpha=1, tint=[1, .9, 1.2]),
                          dict(url="/assets/Backgrounds/layers/stars.webp", y=.55, height=.5, parallax=.12, alpha=.5, tint=[.8, .8, 1.3], drift=.002)]),
         fx=[dict(type="dust", amount=.2)],
         light=dict(dir=[-0.35, -1, -0.25], color=[0.62, 0.58, 0.85], ambient=[0.26, 0.24, 0.42]), fog=dict(color=[0.03, 0.02, 0.07], near=55, far=170))
d["music"] = {"url": "/assets/Music/mp3/25. Dark Factory.mp3"}   # keep the scene music (also settable in the 3D editor)
os.makedirs(OUT, exist_ok=True); json.dump(d, open(os.path.join(OUT, "vault.json"), "w"), separators=(",", ":"))
print("rects", len(rcA), len(rcB), len(rcC), "chests", len(CHESTS), "floor cells", len(F), "pieces", len(P), "colliders", len(COL), "npcs", len(NP), "events", len(EV), "decals", len(DEC), "bounds", d["bounds"])

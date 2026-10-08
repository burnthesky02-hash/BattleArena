"""Builds html_hub/3d/forest.json: the Whispering Wood, a big trail-and-clearing forest north-west of the village (scene `forest`).
Random fights on the trails (levels 1-5, harder to the north), a ranger's pool with a waterfall, a goblin camp (Chieftain Skraag), a thorn barrier,
the Old Oak Grove (Briarmaw, boss) and Ranger Willa; dead-end clearings hold chests.  Quest flags: fq_start, fq_chief, fq_boss, fq_seal, fq_done.
Run:  python make_forest.py [outdir]   (needs forestmap.py, kenhouse.py, gen_forest_meshes.py output).   x = east, z = south."""
import json, math, os, random, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from forestmap import TRAILS, CLEAR, POND, FALL, BOUNDS, WALK_HW, dist_walk, walkable
from kenhouse import Town, S, KEN
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
GC = "/assets/3D/GodCity/"
T = Town(); rnd = random.Random(33)
put, ken, block, glow = T.put, T.ken, T.block, T.glow
NP, EV = [], []
def gc(n, x, z, rot=0, y=0, sc=1, spec=None): put(GC + n, x, z, rot, y, sc, spec)
put("SM_forest_ground", 0, 0, 0, 0, 1)

# ---------------------------------------------------------------- solid forest: block every 1.5 m cell that is not walkable (row runs merged)
CELL = 1.5
xs = np.arange(BOUNDS["minX"], BOUNDS["maxX"], CELL); zs = np.arange(BOUNDS["minZ"], BOUNDS["maxZ"], CELL)
for z in zs:
    row = ~walkable(xs + CELL / 2, np.full(xs.shape, z + CELL / 2)); i = 0
    while i < len(xs):
        if not row[i]: i += 1; continue
        j = i
        while j < len(xs) and row[j]: j += 1
        block(xs[i] + (j - i) * CELL / 2, z + CELL / 2, (j - i) * CELL, CELL + 0.02); i = j
for sgn in (-1, 1):                                                         # the outer fence
    block(sgn * (BOUNDS["maxX"] + 4), -7, 8, 160);
block(0, BOUNDS["minZ"] - 4, 160, 8); block(0, BOUNDS["maxZ"] + 4, 160, 8)

# ---------------------------------------------------------------- trees: a dense wall of forest round the trails and clearings
GAPLESS = [(0, 62, 3.0)]
trees = []
def too_close(x, z, gap): return any((x - a) ** 2 + (z - b) ** 2 < gap * gap for a, b in trees)
AVOID = []                                           # (x, z, r) kept free of trees (props and landmarks)
for _ in range(60000):
    x = rnd.uniform(BOUNDS["minX"] - 10, BOUNDS["maxX"] + 10); z = rnd.uniform(BOUNDS["minZ"] - 10, BOUNDS["maxZ"] + 10)
    dw = float(dist_walk(x, z))
    if dw < 0.9 or dw > 26: continue
    gap = 2.5 if dw < 6 else (3.4 if dw < 12 else 4.8)
    if too_close(x, z, gap): continue
    if (x - FALL[0]) ** 2 + (z - FALL[1]) ** 2 < 36 or (x - POND[0]) ** 2 + (z - POND[1]) ** 2 < 49: continue
    r = rnd.random(); trees.append((x, z))
    if r < 0.82: put(KEN + "tree-large", x, z, rnd.randrange(360), 0, rnd.uniform(2.4, 3.8) if dw > 2 else rnd.uniform(2.3, 3.2))
    elif r < 0.93: put(KEN + "tree-shrub", x, z, rnd.randrange(360), 0, rnd.uniform(2.0, 3.0))
    else: put("SM_rock_0%d" % rnd.randint(1, 2), x, z, rnd.randrange(360), -0.2, rnd.uniform(1.4, 2.6))
    if len(T.P) > 2300: break
# undergrowth on the walkable fringe (no collision): ferns and flowers
for _ in range(900):
    x = rnd.uniform(BOUNDS["minX"], BOUNDS["maxX"]); z = rnd.uniform(BOUNDS["minZ"], BOUNDS["maxZ"]); dw = float(dist_walk(x, z))
    if not (-1.4 < dw < 1.2): continue
    r = rnd.random()
    if r < 0.45: put(rnd.choice(["SM_Plant_01", "SM_Plant_02", "SM_Plant_03"]), x, z, rnd.randrange(360), 0, rnd.uniform(0.45, 0.8))
    elif r < 0.8: put(rnd.choice(["SM_grass_01", "SM_grass_02"]), x, z, rnd.randrange(360), 0, rnd.uniform(2.0, 3.0))
    else: gc(rnd.choice(["SM_flowers_01", "SM_flowers_02"]), x, z, rnd.randrange(360), 0, rnd.uniform(0.9, 1.4))

# ---------------------------------------------------------------- loot
LOOT_ITEMS = {1: ["potion", "antidote", "potion"], 2: ["potion", "hi_potion", "ether", "antidote"]}
RARE_EQ = ["knights_blade", "falcon_saber", "war_hatchet", "chapel_mace", "twinfang_daggers", "longshot_bow", "crystal_staff", "moonlit_wand", "bulwark_shield",
           "parrying_buckler", "armor_light_rare", "armor_medium_rare", "helm_light_rare", "helm_medium_rare", "boots_light_rare", "boots_medium_rare", "sages_ring", "ring_of_swift_feet"]
def make_loot(tier, rg):
    r = rg.random(); loot = {}; gold = {1: (80, 220), 2: (180, 420)}[tier]
    if r < .40: loot["gold"] = rg.randrange(gold[0], gold[1], 10)
    elif r < .68:
        loot["items"] = {rg.choice(LOOT_ITEMS[tier]): rg.randint(2, 4)}; loot["gold"] = rg.randrange(gold[0] // 3, gold[1] // 3, 10)
    elif r < .84: loot["gems"] = rg.randint(*{1: (3, 7), 2: (6, 12)}[tier]); loot["gold"] = rg.randrange(gold[0] // 3, gold[1] // 3, 10)
    else: loot["equipment"] = [rg.choice(RARE_EQ)]; loot["shards"] = rg.randint(2, 6) * tier
    return loot
lrng = random.Random(77); NCH = [0]
def chest(x, z, tier, rot=0):
    NCH[0] += 1; key = "fc_%d" % NCH[0]
    put("/assets/3D/Generated/SM_TreasureChest", x, z, rot, 0, 1.0, key); block(x, z, 1.6, 1.6)
    EV.append(dict(id=key, name="Treasure chest", x=round(x, 2), z=round(z, 2), w=4.2, d=4.2, trigger="talk", prompt="Open the chest", hideIf=key,
                   actions=[dict(type="flag", key=key), dict(type="chest", loot=make_loot(tier, lrng))]))
def note(key, name, x, z, text, who="Torn page"):
    put("SM_table_02", x, z, 0, 0, 1.4); block(x, z, 1.8, 1.8)
    EV.append(dict(id=key, name=name, x=round(x, 2), z=round(z + 1.6, 2), w=3.6, d=2.8, trigger="talk", prompt="Read the page", actions=[dict(type="say", who=who, text=text)]))
def sign(key, x, z, text, rot=0):
    ken("structure-poles", x, z, rot, 0, 1.6); block(x, z, 1.0, 1.0)
    EV.append(dict(id=key, name="Signpost", x=round(x, 2), z=round(z + 1.8, 2), w=3.4, d=2.8, trigger="talk", prompt="Read the sign", actions=[dict(type="say", who="Signpost", text=text)]))
def fire(x, z, r=4.0):
    gc("SM_brasero", x, z, 0, 0, 0.04); block(x, z, 1.2, 1.2); glow(x, z, r, [1, .6, .25, .8])

# ---------------------------------------------------------------- trailhead: the hunter's cabin
hx, hz, hat = T.house(15.0, 53.0, 270, [(0, 0, 2, 1)], "wood", "", "brown")
T.barrels(*hat(3.6, 2.0)); T.crate(*hat(-3.6, 1.6), 20)
sign("fs_head", -3.8, 50.0, "THE WHISPERING WOOD. Goblins on the trail; something worse in the north. Pools and a ranger's camp are to the east. TURN BACK IF YOU ARE ALONE.")
T.torch(-4.5, 58.5); T.torch(4.5, 58.5)

# ---------------------------------------------------------------- the pool, the waterfall and the ranger's camp
px, pz, pr = CLEAR["pool"]
for k in range(9):                                                            # cliff of boulders behind the falls
    put("SM_rock_0%d" % (1 + k % 2), FALL[0] - 8 + k * 2.1, FALL[1] - 1.2 - (k % 3) * 0.8, rnd.randrange(360), -0.3, rnd.uniform(3.4, 5.0))
for k in range(6): put("SM_rock_0%d" % (1 + k % 2), FALL[0] - 5 + k * 2.2, FALL[1] - 4.2, rnd.randrange(360), 1.5, rnd.uniform(3.6, 5.0))
put("SM_waterfall", FALL[0], FALL[1] + 0.2, 0, 0.0, 1.3)
glow(FALL[0], FALL[1] + 1.0, 4.5, [0.7, 0.9, 1.0, 0.35]); glow(POND[0], POND[1], 5.5, [0.4, 0.75, 1.0, 0.25])
for k in range(10):                                                           # reeds and rocks round the pond
    a = k * 0.63 + rnd.random() * .3; x, z = POND[0] + (POND[2] + 0.9) * math.cos(a), POND[1] + (POND[2] + 0.9) * math.sin(a)
    put(rnd.choice(["SM_rock_01", "SM_rock_02"]), x, z, rnd.randrange(360), -0.2, rnd.uniform(0.7, 1.2))
gc("SM_market_tent_01", 3.4, 6.8, 160, 0, 0.8); block(3.4, 6.8, 3.6, 5.6)               # Willa's camp
fire(8.0, 6.2, 5.0); T.crate(0.6, 4.4, 30); T.barrels(5.6, 9.6, 40)
put("SM_bed", -0.4, 8.6, 20, 0, 0.9)
note("fn_journal", "Ranger's journal", 11.4, 7.0, "Day 1. Goblin raiders are stealing from the farms. The trail is full of them. Day 2. Their chief, Skraag, keeps a thorn-totem at his camp in the north-east, and the totem is feeding brambles across the north trail. Day 3. The totem hums at night. Whatever is under the Old Oak answers it. I carry the Warden's Seal north to end this. If you read this, Ranger Willa has not come back.", "Ranger Willa's journal")
EV.append(dict(id="fire_rest", name="Ranger's campfire", x=8.0, z=4.4, w=4.4, d=3.0, trigger="talk", prompt="Rest by the fire", actions=[dict(type="say", who="", text="The ranger's fire still holds some heat. You rest a while by the pool, and the water's sound washes the fight out of you."), dict(type="rest")]))

# ---------------------------------------------------------------- the goblin camp (north-east): tents, fires, a totem, the Chieftain
cx, cz, cr = CLEAR["camp"]
for (hx_, hz_, hr_) in ((cx + 8.0, cz - 4.5, 270), (cx - 8.0, cz - 3.5, 90), (cx - 0.5, cz + 9.0, 180)):       # three wooden huts round the fire
    T.house(hx_, hz_, hr_, [(0, 0, 2, 1)], "wood", "", "brown")
fire(cx - 0.5, cz + 0.5, 5.0); fire(cx + 7.0, cz + 4.0, 3.5)
for dx, dz in ((3.5, 6.0), (-8.5, 4.5), (8.0, -1.0)): T.crate(cx + dx, cz + dz, rnd.randrange(90));
T.barrels(cx - 8.2, cz - 8.0, 30); T.barrels(cx + 9.0, cz + 1.5, 70)
for k in range(6): ken("fence", cx - 9 + k * 1.6, cz + 10.2, 0, 0, 1.6)
ken("column-wood", cx + 0.5, cz - 6.5, 0, 0, 5.0); ken("column-wood", cx + 0.5, cz - 6.5, 0, 3.4, 3.0); block(cx + 0.5, cz - 6.5, 1.0, 1.0); glow(cx + 0.5, cz - 6.5, 4.0, [1, .25, .3, .8])    # the totem
chest(cx - 9.2, cz - 1.0, 2, 90)
GOB = dict(sprite="Draven", tint=[0.55, 1.1, 0.55, 1])
NP += [
 dict(id="skraag", name="Chieftain Skraag", title="Goblin Chieftain", x=cx + 0.8, z=cz - 3.4, h=3.0, sprite="Draven", tint=[0.45, 1.15, 0.5, 1], hideIf="fq_chief",
      actions=[dict(type="say", who="Chieftain Skraag", text="Ha! Two-legs with sharp sticks! Skraag takes the farms, Skraag takes the Seal, Skraag takes YOU!"),
               dict(type="say", who="Chieftain Skraag", text="Boys! Cut them down!"),
               dict(type="battle", key="fq_chief", pool=["goblin_skirmisher", "bandit_rogue"], level=[4, 5])]),
 dict(id="gob1", name="Goblin Guard", title="Camp guard", x=cx - 4.5, z=cz + 3.0, h=2.2, sprite="Draven", tint=[0.5, 1.1, 0.5, 1], hideIf="fq_g1",
      actions=[dict(type="say", who="Goblin Guard", text="Nobody passes Skraag's camp! Hee hee!"), dict(type="battle", key="fq_g1", pool=["goblin_skirmisher"], level=[3, 4])]),
 dict(id="gob2", name="Goblin Guard", title="Camp guard", x=cx + 6.0, z=cz + 6.5, h=2.2, sprite="Draven", tint=[0.5, 1.1, 0.5, 1], hideIf="fq_g2",
      actions=[dict(type="say", who="Goblin Guard", text="More soft ones! Smash them!"), dict(type="battle", key="fq_g2", pool=["goblin_skirmisher", "bandit_rogue"], level=[3, 4])]),
]

# ---------------------------------------------------------------- the thorn barrier on the north trail
bx, bz = -14.0, -50.0
for k in range(34):
    x = bx + rnd.uniform(-5.2, 5.2); z = bz + rnd.uniform(-1.8, 1.8)
    put(rnd.choice([KEN + "tree-shrub", GC + "SM_bush_01", GC + "SM_bush_02"]), x, z, rnd.randrange(360), 0, rnd.uniform(1.6, 2.6) if "tree" in "x" else rnd.uniform(1.4, 2.4), "fq_chief")
block(bx, bz, 9.0, 3.4, "fq_chief"); glow(bx, bz, 4.5, [.8, .2, .3, .4])
EV.append(dict(id="thorns", name="Thorn barrier", x=bx, z=bz + 3.4, w=9, d=3.0, trigger="talk", prompt="Examine the thorns", hideIf="fq_chief",
               actions=[dict(type="say", who="", text="A wall of black brambles, thick as your arm, humming with some wrong, borrowed life. Blades slide off it. Something is feeding it from far away."),
                        dict(type="say", who="", text="Willa's journal said the goblin chieftain keeps a totem in his camp in the north-east. Perhaps the thorns die with it.")]))
AUTO = [dict(**{"if": "fq_chief", "unless": "fq_chief_msg"}, actions=[dict(type="say", who="", text="Skraag's totem cracks and goes dark. Far to the north, a groan of splintering thorns rolls through the trees. The way to the Old Oak is open."), dict(type="flag", key="fq_chief_msg")])]

# ---------------------------------------------------------------- the Old Oak Grove (boss) and Ranger Willa
gx, gz, gr = CLEAR["grove"]
put(KEN + "tree-large", gx, gz - 5.0, 0, 0, 11.0); block(gx, gz - 5.0, 5.0, 5.0)
for k in range(10):
    a = k * 2 * math.pi / 10 + 0.2; x, z = gx + 9.5 * math.cos(a), gz - 2.0 + 8.0 * math.sin(a)
    if abs(x - gx) < 3 and z > gz + 3: continue
    ken("column", x, z, 0, 0, 3.4); block(x, z, 0.8, 0.8)
glow(gx, gz - 1.0, 7.0, [0.55, 1.0, 0.5, 0.3])
chest(gx - 9.5, gz + 5.5, 2, 20); chest(gx + 9.5, gz + 5.5, 2, -20)
NP += [
 dict(id="briarmaw", name="Briarmaw", title="Heart of the Wood", x=gx, z=gz + 1.2, h=4.6, sprite="Rook", tint=[0.35, 1.2, 0.45, 1], hideIf="fq_boss",
      actions=[dict(type="say", who="Briarmaw", text="...A SMALL FIRE... IN MY WOOD... THE THORNS... SANG ME... A WARM SONG..."),
               dict(type="say", who="Briarmaw", text="NOW... THE SONG IS BROKEN. I AM... AWAKE. WHO... WALKS... UNDER MY BOUGHS?"),
               dict(type="battle", key="fq_boss", boss="briarmaw_boss")]),
 dict(id="willa0", name="Ranger Willa", title="Ranger", x=gx + 6.0, z=gz + 6.0, h=2.4, sprite="Yulia", tint=[1.1, 1.0, 0.8, 1], hideIf="fq_boss",
      actions=[dict(type="say", who="Ranger Willa", text="Stay back! The Oak's heart is awake, and the thorns have my legs pinned. It will go for you first!"),
               dict(type="say", who="Ranger Willa", text="Strike at the Briarmaw, quickly! I can hold on.")]),
 dict(id="willa1", name="Ranger Willa", title="Ranger", x=gx + 6.0, z=gz + 6.0, h=2.4, sprite="Yulia", tint=[1.1, 1.0, 0.8, 1], showIf="fq_boss", hideIf="fq_seal",
      actions=[dict(type="say", who="Ranger Willa", text="You did it. I felt the Oak let go of the whole Wood. I thought I was done for."),
               dict(type="say", who="Ranger Willa", text="Take the Warden's Seal to Mayor Orrin. It will open the cave. I'll catch my breath, then follow the trail home."),
               dict(type="flag", key="fq_seal")]),
 dict(id="willa2", name="Ranger Willa", title="Ranger", x=gx + 6.0, z=gz + 6.0, h=2.4, sprite="Yulia", tint=[1.1, 1.0, 0.8, 1], showIf="fq_seal",
      actions=[dict(type="say", who="Ranger Willa", text="Go on, hurry to the mayor. The Seal is yours. Mind the cave: older things than goblins sleep down there.")]),
]

# ---------------------------------------------------------------- dead ends
lx, lz, _ = CLEAR["look"]                               # hunter's lookout
gc("SM_market_tent_02", lx - 1.5, lz - 2.5, 30, 0, 0.7); block(lx - 1.5, lz - 2.5, 3.6, 5.4); chest(lx + 2.4, lz + 1.0, 1, 30)
note("fn_lookout", "Hunter's note", lx - 2.8, lz + 1.6, "From up here you can see the whole Wood. The pool is south-east of the island's heart, the goblin camp lies north-east, and the oldest tree stands far to the north, behind a wall of thorns. I do not go there.", "Hunter's note")
ggx, ggz, _ = CLEAR["giant"]                            # the fallen giant
for k in range(7): ken("column-wood", ggx - 3 + k * 1.05, ggz - 1.5 + 0.2 * math.sin(k), 90, 0, 2.2)
block(ggx, ggz - 1.5, 7.6, 1.6); chest(ggx + 2.0, ggz + 2.6, 1, -30)
sx, sz, _ = CLEAR["spider"]                             # the webbed hollow
for k in range(8): put(rnd.choice(["SM_Plant_01", "SM_Plant_03"]), sx + rnd.uniform(-5, 5), sz + rnd.uniform(-5, 5), rnd.randrange(360), 0, rnd.uniform(0.6, 1.0))
glow(sx, sz, 6.0, [0.75, 0.9, 0.7, 0.25]); chest(sx + 3.0, sz + 2.8, 2, 40)
NP += [dict(id="spider", name="Giant Spider", title="Webbed hollow", x=sx - 1.0, z=sz - 1.0, h=2.6, sprite="Sera", tint=[0.55, 0.45, 0.7, 1], hideIf="fq_spider",
            actions=[dict(type="say", who="", text="Silk glimmers between the trunks. Something large and many-legged drops down in front of you."),
                     dict(type="battle", key="fq_spider", pool=["venom_spider"], level=[5, 5])])]
cax, caz, _ = CLEAR["cache"]                            # ranger's cache
ken("structure", cax, caz - 1.0, 0, 0, 2.4); block(cax, caz - 1.0, 2.6, 2.6); chest(cax + 2.8, caz + 1.0, 2, 0); T.crate(cax - 2.8, caz + 0.6, 20); T.barrels(cax - 3.0, caz - 2.4, 0)
note("fn_cache", "Ranger's cache note", cax + 0.4, caz + 3.6, "Spare arrows, salt pork, and a charm against the Oak. If you are reading this, Willa, they got further than I did. Keep the Seal off the ground; the thorns grow where it falls.", "Ranger's note")
glx, glz, _ = CLEAR["glade"]                            # the spirit spring
gc("SM_circular_terrace", glx, glz, 0, -0.3, 0.5)
put("SM_rock_02", glx - 2.4, glz - 1.0, 0, 0, 1.3); glow(glx, glz, 6.0, [0.6, 1.0, 0.8, 0.4])
EV.append(dict(id="spirit_spring", name="Spirit spring", x=glx, z=glz + 1.8, w=5, d=4, trigger="talk", prompt="Drink from the spring",
               actions=[dict(type="say", who="", text="Clear, cold water wells up between the roots. It tastes of rain, and for a moment every ache leaves you."), dict(type="rest")]))
chest(glx + 2.8, glz - 2.4, 1, 20)
NP += [dict(id="hermit", name="Mossbeard", title="Forest hermit", x=glx - 3.2, z=glz + 2.2, h=2.4, sprite="Draven", tint=[0.8, 1.0, 0.8, 1], line="Hm? Oh, travellers. The Oak is older than the island's name. It sings to the thorns. Lately somebody has been singing back."),
        dict(id="hunter", name="Garrick", title="Hunter", x=hx - 1.6 if False else 10.4, z=56.2, h=2.4, sprite="Kael", tint=[0.9, 1.05, 0.8, 1],
             line="Mind yourself in there. Goblins on the trails, spiders in the hollows, and worse to the north. Rest at the ranger's camp by the pool if you need it. Follow the water.")]

# ---------------------------------------------------------------- exit back to the village, scene events
EV += [dict(id="exit_island", name="Back to the island", x=0, z=62.5, w=9, d=2.4, trigger="touch", once=False, actions=[dict(type="warp", scene="island", x=-39.0, z=-41.5)])]

# ---------------------------------------------------------------- fights, objectives, scene
MM_CELL = 2.0
_rects = []
for z in np.arange(BOUNDS["minZ"], BOUNDS["maxZ"], MM_CELL):
    row = walkable(np.arange(BOUNDS["minX"], BOUNDS["maxX"], MM_CELL) + MM_CELL / 2, np.full(len(np.arange(BOUNDS["minX"], BOUNDS["maxX"], MM_CELL)), z + MM_CELL / 2)); i = 0
    while i < len(row):
        if not row[i]: i += 1; continue
        j = i
        while j < len(row) and row[j]: j += 1
        _rects.append([BOUNDS["minX"] + i * MM_CELL, float(z), (j - i) * MM_CELL, MM_CELL]); i = j
RATE = 70
def zb(x0, z0, x1, z1, **kw): d = dict(x=(x0 + x1) / 2, z=(z0 + z1) / 2, w=x1 - x0, d=z1 - z0); d.update(kw); return d
ZONES = [zb(-13, 44, 13, 70, safe=True),
         zb(-3, -12, 28, 14, safe=True),                       # the pool and the ranger's camp
         zb(16, -64, 46, -36, safe=True),                       # the goblin camp
         zb(-30, -80, 4, -52, safe=True),                       # the Old Oak Grove
         zb(-80, 30, 80, 70, pool=["goblin_skirmisher", "bandit_rogue"], level=[1, 2], rate=RATE),
         zb(-80, 12, 80, 30, pool=["goblin_skirmisher", "bandit_rogue", "venom_spider"], level=[2, 3], rate=RATE),
         zb(-80, -22, 80, 12, pool=["goblin_skirmisher", "venom_spider", "bandit_rogue"], level=[2, 4], rate=RATE),
         zb(-80, -50, 80, -22, pool=["venom_spider", "bandit_rogue", "dark_cultist", "goblin_skirmisher"], level=[3, 5], rate=RATE),
         zb(-80, -90, 80, -50, pool=["venom_spider", "dark_cultist", "storm_harpy"], level=[4, 5], rate=RATE)]
OBJ = [dict(unless="fq_start", text="Speak with Mayor Orrin in the village first"),
       dict(**{"if": "fq_start", "unless": "fq_chief"}, text="Find Ranger Willa. Follow the water, and find who feeds the thorn barrier (goblin camp in the north-east)"),
       dict(**{"if": "fq_chief", "unless": "fq_boss"}, text="Cut through the withered brambles on the north trail and reach the Old Oak Grove"),
       dict(**{"if": "fq_boss", "unless": "fq_seal"}, text="Speak with Ranger Willa in the grove"),
       dict(**{"if": "fq_seal", "unless": "fq_done"}, text="Take the Warden's Seal back to Mayor Orrin"),
       dict(text="The Wood is quiet. Explore for treasure, or head to the cave")]
d = dict(name="The Whispering Wood", kit="", tile=4, pieces=T.P, colliders=T.COL, npcs=NP, events=EV, decals=T.DEC, objectives=OBJ, autorun=AUTO, story=True,
         encounters=dict(rate=RATE, level=[1, 3], pool=["goblin_skirmisher", "bandit_rogue", "venom_spider"], zones=ZONES, text="Something rustles in the undergrowth... monsters attack!"),
         bounds=BOUNDS, spawn=dict(x=0, z=56), playerHeight=2.4,
         sky=dict(type="gradient", stops=[[0, "#1d3d44"], [.5, "#3d6a5a"], [1, "#9fc29a"]]),
         fx=[dict(type="fireflies", amount=0.6), dict(type="leaves", amount=0.35)],
         light=dict(dir=[-0.35, -1, -0.3], color=[0.95, 1.0, 0.82], ambient=[0.46, 0.54, 0.48]), fog=dict(color=[0.12, 0.2, 0.17], near=34, far=105), camera=dict(pitch=47, dist=26),
         minimap=dict(cell=4, rects=_rects, water=[[POND[0] - POND[2], POND[1] - POND[2], POND[2] * 2, POND[2] * 2]]))
os.makedirs(OUT, exist_ok=True); json.dump(d, open(os.path.join(OUT, "forest.json"), "w"), separators=(",", ":"))
print("pieces", len(T.P), "colliders", len(T.COL), "npcs", len(NP), "events", len(EV), "trees", len(trees), "chests", NCH[0])

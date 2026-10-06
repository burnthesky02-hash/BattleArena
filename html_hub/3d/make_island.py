"""Builds html_hub/3d/island.json: Paradise Island, a hilly harbour town built from the StylizedIsland kit (stylhouse.py / convert_stylized.py):
tavern & inn, the mayor's big house on the hill, blacksmith, item shop, harbourmaster's lodge, farm, fountain terrace, a harbour with docks, the Hollow Cave
headland to the north and the path to the Whispering Wood (scene `forest`) in the north-west.  The ground is a real heightmap (islandheight.py -> `terrain`
in the scene, plus SM_island_ground.glb from gen_island_meshes.py); every prop is placed at the terrain height.  The cave is sealed until the forest quest (fq_*) is done.
Run:  python make_island.py [outdir]   (needs islandshape.py, islandheight.py, villagemap.py, stylhouse.py next to it).   x = east, z = south."""
import json, math, os, random, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from islandshape import q_of
import islandheight as IH
from villagemap import PATHS, PLAZA, FARM, TERRACE, dist_to_paths
from stylhouse import Town
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
GC = "/assets/3D/GodCity/"; DG = "/assets/3D/Dungeon/"
T = Town(IH.gy); rnd = random.Random(21)
put, block, glow = T.put, T.block, T.glow
NP, EV = [], []
def gc(n, x, z, rot=0, y=0, sc=1, spec=None): put(GC + n, x, z, rot, y, sc, spec)
def inside(x, z, lim=0.80): return bool(q_of(x, z) < lim)

put("/assets/3D/Paradise/SM_ocean", 0, 0, 0, 0, 1, abs_y=True); put("/assets/3D/Paradise/SM_island_ground", 0, 0, 0, 0, 1, abs_y=True)
KEEP = []; RECTS = []
def keep_house(cx, cz, rot, w, d, door):
    if rot % 180 == 90: w, d = d, w
    RECTS.append((cx, cz, w / 2 + 1.2, d / 2 + 1.2)); KEEP.append((door[0], door[1], 5.0))

# ================================================================ the village
# ---- plaza: the fountain, lamp posts, benches, two market stalls
put("SM_Stylized_Fountain", PLAZA[0], PLAZA[1], 0, 0, 1.5); block(PLAZA[0], PLAZA[1], 6.2, 6.2); glow(PLAZA[0], PLAZA[1], 4.5, [0.45, 0.75, 1.0, 0.22])
for k in range(8):
    a = k * math.pi / 4 + 0.39; x, z = PLAZA[0] + 8.6 * math.cos(a), PLAZA[1] + 8.6 * math.sin(a)
    if any(dist_to_paths(np.array(x), np.array(z), [n]) < 2.6 for n in ("dock", "cave", "west", "east", "shop", "harbor")): continue
    T.lamp(x, z)
for k, a in enumerate((0.9, 3.5)):
    x, z = PLAZA[0] + 5.6 * math.cos(a + 0.25), PLAZA[1] + 5.6 * math.sin(a + 0.25)
    put("SM_Stylized_Bench", x, z, -math.degrees(a) + 90, 0, 2.2); block(x, z, 1.4, 1.4)
for sgn, rr in ((-1, 25), (1, -20)):                                            # market stalls: a table, crates and an awning-less counter
    x, z = sgn * 7.4, 9.0; put("SM_Stylized_Table_A", x, z, rr, 0, 1.0); block(x, z, 3.0, 2.0)
    put("SM_Stylized_Basket", x + .6, z, rr, .9, 2.0); T.box(x - 2.2 * sgn, z + 0.6, 30, 1); T.barrel(x + 2.4 * sgn, z - .4)
KEEP.append((PLAZA[0], PLAZA[1], PLAZA[2] + 1.5))

# ---- Tavern & Inn (centre-left): two floors, red roof, a one-floor annex to the west, tables out front
TAV = (-10.6, -15.5, 0)
fx, fz, at = T.house(*TAV, floors=2, bays=3, wall="cream", roof="red", door_bay=0)
tav_door = (fx, fz); keep_house(TAV[0], TAV[1], 0, 8.5, 12.5, tav_door)
fx2, fz2, at2 = T.house(-18.6, -19.5, 0, floors=1, bays=1, wall="sand", roof="brown", skip=("R",)); RECTS.append((-18.6, -19.5, 5.5, 3.2))
for dx, dz in ((2.4, 3.2), (6.0, 3.4)):
    x, z = at(dx, 6 + dz); put("SM_Stylized_Table_B", x, z, 0, 0, 1.0); block(x, z, 2.2, 2.2)
    put("SM_Stylized_Bench", x - 1.4, z, 90, 0, 2.0); put("SM_Stylized_Bench", x + 1.4, z, 270, 0, 2.0)
x, z = at(5.2, 6.4); T.barrel(x, z); x, z = at(6.2, 5.8); T.barrel(x, z, 40); x, z = at(5.4, 7.4); T.box(x, z, 15, 2)
T.lamp(fx + 2.4, fz + 0.6); put("SM_Chimney", *at(2.2, -2.0), 0, 6.0, 1.0)

# ---- Mayor's House: the big blue-roofed house on the hill (the kit's Mill building: stone base, steps, dormers)
MAY = (18.4, -25.0)
put("SM_Mill", MAY[0], MAY[1], 0, 0, 1.0); block(MAY[0], MAY[1], 10.8, 11.4)
may_door = (MAY[0] + 0.9, MAY[1] + 7.0); keep_house(MAY[0], MAY[1], 0, 11.4, 12.0, may_door)
T.lamp(MAY[0] - 2.4, MAY[1] + 8.4); T.lamp(MAY[0] + 4.0, MAY[1] + 8.4)
for k in range(6): put("SM_Sunflower", MAY[0] - 6 + k * 0.9, MAY[1] + 7.2, rnd.randrange(360), 0, rnd.uniform(1.2, 1.7))
T.fence(MAY[0] + 6.5, MAY[1] + 6.0, MAY[0] + 11.0, MAY[1] + 6.0)

# ---- Blacksmith (east): grey stone, brown roof, forge fire, barrels and crates; faces west onto the east path
SMI = (31.0, 6.4, 270)
fx, fz, at = T.house(*SMI, floors=1, bays=2, wall="stone", roof="brown", door_bay=0)
smi_door = (fx, fz); keep_house(SMI[0], SMI[1], 270, 8.5, 8.5, smi_door)
x, z = at(4.8, 6.4); put("SM_Stylized_Bonfire", x, z, 0, 0, 1.2); block(x, z, 1.8, 1.8); glow(x, z, 3.2, [1, 0.55, 0.2, 0.8])
for dx, dz in ((-3.0, 6.2), (-4.0, 5.6)): x, z = at(dx, dz); T.barrel(x, z, 70)
x, z = at(2.4, 6.4); T.box(x, z, 20, 2); T.lamp(fx - 1.4, fz - 2.0); put("SM_Chimney", *at(2.0, 0.5), 0, 3.0, 1.0)

# ---- Item Shop (south): blue walls, brown roof, door facing the path (north), crates and barrels
SHP = (13.0, 16.5, 180)
fx, fz, at = T.house(*SHP, floors=1, bays=2, wall="blue", roof="brown", door_bay=0)
shp_door = (fx, fz); keep_house(SHP[0], SHP[1], 180, 8.5, 8.5, shp_door)
x, z = at(3.4, 6.0); T.barrel(x, z, 30); x, z = at(4.5, 5.4); T.box(x, z, 10, 1); x, z = at(-4.2, 5.6); T.box(x, z, 80, 2)
T.lamp(fx + 2.8, fz - 0.4); put("SM_Stylized_Basket", *at(1.6, 5.6), 0, 0, 2.0)

# ---- Harbormaster's lodge (west of the harbour path)
LOD = (-24.0, 11.5, 0)
fx, fz, at = T.house(*LOD, floors=1, bays=2, wall="mint", roof="slate", door_bay=1)
lod_door = (fx, fz); keep_house(LOD[0], LOD[1], 0, 8.5, 8.5, lod_door)
x, z = at(-3.4, 5.8); T.barrel(x, z, 5); T.lamp(fx + 2.0, fz + 0.2)

# ---- Farm (west): a barn, a fenced field of wheat with a scarecrow, a wagon and hay
BARN = (-23.5, -13.0, 0)
fx, fz, at = T.house(*BARN, floors=1, bays=3, wall="rose", roof="brown", door_bay=1)
barn_door = (fx, fz); keep_house(BARN[0], BARN[1], 0, 8.5, 12.5, barn_door)
x, z = at(6.4, -1.0); put("SM_Stylized_Wagon", x, z, 8, 0, 1.2); block(x, z, 2.6, 5.0)
for dx, dz in ((6.0, 5.5), (6.8, 6.7), (5.0, 6.9)): x, z = at(dx, dz); put("SM_Hay", x, z, rnd.randrange(360), 0, 2.2); block(x, z, 1.4, 1.4)
fcx, fcz, fhw, fhd = FARM
for jz in range(6):
    z = fcz - fhd + 1.3 + jz * 2.3
    for t in range(15):
        x = fcx - fhw + 1.0 + t * 1.15 + rnd.uniform(-.1, .1)
        put(["SM_Wheat", "SM_Wheat", "SM_Sunflower"][jz % 3], x, z + rnd.uniform(-.1, .1), rnd.randrange(360), 0, rnd.uniform(1.4, 2.0) if jz % 3 != 2 else rnd.uniform(1.0, 1.4))
put("SM_Stylized_Scarecrow", fcx, fcz, 15, 0, 1.3); block(fcx, fcz, 1.2, 1.2)
x0, x1, z0, z1 = fcx - fhw - 1.4, fcx + fhw + 1.4, fcz - fhd - 1.4, fcz + fhd + 1.4
T.fence(x0, z0, x1, z0); T.fence(x0, z1, x1, z1); T.fence(x0, z0, x0, z1); T.fence(x1, z0, x1, fcz - 1.8); T.fence(x1, fcz + 1.8, x1, z1)
RECTS.append((fcx, fcz, fhw + 3, fhd + 3)); KEEP.append((-31, -9, 3.0))

# ---- Fountain terrace (east headland): a stone fountain, lamps, benches, an arch and a lookout sign
TX, TZ, TR = TERRACE
put("SM_Stylized_Fountain", TX, TZ, 0, 0, 1.7); block(TX, TZ, 7.4, 7.4); glow(TX, TZ, 5.0, [0.4, 0.75, 1.0, 0.25])
for k in range(4):
    a = k * math.pi / 2 + 0.78; T.lamp(TX + 7.0 * math.cos(a), TZ + 7.0 * math.sin(a))
for k in range(4):
    a = k * math.pi / 2; put("SM_Stylized_Bench", TX + 5.3 * math.cos(a), TZ + 5.3 * math.sin(a), -math.degrees(a) + 90, 0, 2.2)
put("SM_Stylized_Well", TX + 4.0, TZ - 8.2, 180, 0, 1.0); block(TX + 4.0, TZ - 8.2, 2.8, 2.4)
KEEP.append((TX, TZ, TR + 1.5))

# ---- docks: the ferry pier (centre) and a smaller harbour pier (south-west); boats alongside
WALK = []                          # walkable surfaces for the engine (scene.walk): flat boxes you can stand on that the heightmap does not know about
DECK_TOP = 0.27                    # top of the dock planks (4.61 m mesh height + DECK)
DECK = -4.35                       # the dock meshes have 4.6 m tall posts; this puts the deck ~0.26 m above the grass
def pier(x, z0, wide=2):
    zc = z0 + 3.8
    for k in range(wide):
        xx = x + (k - (wide - 1) / 2) * 2.45
        put("SM_Dock_Small", xx, z0 - 0.4, 0, DECK, 1.0, abs_y=True) if False else None
        put("SM_Dock_Straight", xx, z0 + 3.8, 0, DECK, 1.0, abs_y=True); put("SM_Dock_Straight", xx, z0 + 11.2, 0, DECK, 1.0, abs_y=True) if False else None
    w = wide * 2.45
    WALK.append(dict(x=x, z=z0 + 3.8, w=round(w, 2), d=7.6, rot=0, y=DECK_TOP))      # you walk ON the deck, not along the seabed under it
    for sgn in (-1, 1): block(x + sgn * (w / 2 + 0.3), z0 + 4.0, 0.5, 8.6)
    block(x, z0 + 7.9, w + 1.2, 0.6)
    for sgn in (-1, 1): glow(x + sgn * w / 2, z0 + 6.0, 2.2, [1, 0.8, 0.45, 0.5])
pier(0.0, 25.9, 2); pier(-23.0, 24.2, 1)
for sgn in (-1, 1): T.lamp(sgn * 3.0, 25.4)
put("SM_Stylized_Boat", -28.5, 29.0, 8, -0.95, 1.0, abs_y=True); put("SM_Stylized_Boat", -18.0, 28.0, -12, -0.95, 1.0, abs_y=True); put("SM_Stylized_Boat", 6.5, 31.0, 80, -0.95, 1.1, abs_y=True)
put("SM_Stylized_Boat", 36.0, 20.5, 40, -0.55, 1.0, abs_y=True)
for sgn in (-1, 1): T.barrel(sgn * 3.6, 24.4, 20 * sgn)
T.box(-25.4, 23.2, 10, 1); T.barrel(-20.8, 23.0); T.box(-20.4, 24.4, 35, 2)
put("SM_Stylized_Flag_Var1", 3.8, 33.3, 0, 0, 1.0) if False else None

# ---- beach (south-east): a rowing boat, driftwood crates
T.box(26.0, 16.4, 15, 1); T.box(27.2, 17.2, 50, 2); T.barrel(24.0, 15.6, 0)

# ---- the cave mouth, braziers, guardian statues and the headland
MZ = -44.0
put("/assets/3D/Paradise/SM_cave_mountain", 0, MZ, 0, 0, 1); put("/assets/3D/Paradise/SM_cave_inner", 0, MZ, 0, 0, 1)
for sgn in (-1, 1):
    gc("SM_temple_column", sgn * 4.9, MZ + 1.2, 0, 0, 0.34); block(sgn * 4.9, MZ + 1.2, 1.0, 1.0)
    gc("SM_brasero", sgn * 6.8, MZ + 3.0, 0, 0, 0.04); block(sgn * 6.8, MZ + 3.0, 1.2, 1.2); glow(sgn * 6.8, MZ + 3.0, 4.0, [1, .6, .25, .8])
    gc("SM_temple_decoration", sgn * 8.8, MZ + 4.2, 90 if sgn < 0 else 270, 0, 0.5); block(sgn * 8.8, MZ + 4.2, 1.6, 2.4)
for sgn in (-1, 1):
    for k in range(5): put("/assets/3D/Paradise/SM_dg_rock", sgn * rnd.uniform(5, 16), MZ + rnd.uniform(1.5, 4), rnd.randrange(360), 0, rnd.uniform(.9, 1.8))
glow(0, MZ - 9, 3.5, [.35, .55, 1, .35])
block(-19.2, MZ - 15.2, 31.6, 30.8); block(22.2, MZ - 15.2, 37.6, 30.8); block(0, MZ - 10.2, 7, 0.8); block(0, MZ - 24, 90, 8)
for i, x in enumerate((-2.0, 0.0, 2.0)):                                   # the sealed gate: a rockfall across the mouth until the forest quest is done
    put("/assets/3D/Paradise/SM_dg_rock", x, MZ - 0.6, 90 * i, 0, 2.3, "fq_done"); put("/assets/3D/Paradise/SM_dg_rock", x * 0.7, MZ - 1.9, 40 * i, 0, 2.0, "fq_done")
block(0, MZ - 1.0, 7.0, 3.0, "fq_done"); glow(0, MZ - 1.0, 3.5, [.9, .55, .3, .3])

# ---- the forest path (north-west): the stone arch, twin ancient trees, a signpost
FX, FZ = -40.5, -45.5
put("SM_Stylized_Arch", FX, FZ - 0.6, 0, 0, 1.0); block(FX - 3.1, FZ - 0.6, 1.0, 1.2); block(FX + 3.1, FZ - 0.6, 1.0, 1.2)
put("Tree_03", FX - 7.0, FZ + 1.0, 0, 0, 1.2); block(FX - 7.0, FZ + 1.0, 1.4, 1.4); put("Tree_03", FX + 7.4, FZ + 0.5, 90, 0, 1.15); block(FX + 7.4, FZ + 0.5, 1.4, 1.4)
put("SM_Stylized_WantedBoard", FX + 2.9, FZ + 3.6, 0, 0, 1.0); block(FX + 2.9, FZ + 3.6, 2.2, 0.8)
put("SM_Stylized_Flag_Var1", FX - 3.2, FZ + 2.6, 0, 0, 1.0); put("SM_Stylized_Flag_Var2", FX + 3.0, FZ - 2.4, 0, 0, 1.0)
KEEP.append((FX, FZ, 7.0)); KEEP.append((0, MZ + 3, 11.0)); KEEP.append((0, -32, 4.0))

# ================================================================ planting
def blocked(x, z, pad=0.0):
    if not inside(x, z): return True
    if dist_to_paths(np.array(x), np.array(z)) < 3.3 + pad: return True
    for cx, cz, r in KEEP:
        if math.hypot(x - cx, z - cz) < r + pad: return True
    for cx, cz, hw, hd in RECTS:
        if abs(x - cx) < hw + pad and abs(z - cz) < hd + pad: return True
    if z < -40 and abs(x) < 34: return True                                    # the rocky headland
    if z > 20 and (abs(x) < 6 or abs(x + 23) < 6): return True               # piers
    if math.hypot(x - TX, z - TZ) < TR + 1.0: return True
    return False
trees = []
TREES = ["Tree_01", "Tree_02", "Tree_03", "Tree_05", "Tree_06", "Tree_02", "Tree_06"]
def try_tree(x, z, gap):
    if blocked(x, z, 0.4) or any((x - a) ** 2 + (z - b) ** 2 < gap * gap for a, b in trees): return False
    n = rnd.choice(TREES) if rnd.random() > 0.12 else rnd.choice(["B_Tree_01", "B_Tree_05"]); sc = rnd.uniform(0.7, 1.0) * (0.8 if n in ("Tree_01", "Tree_03", "B_Tree_01", "B_Tree_05") else 1.0)
    put(n, x, z, rnd.randrange(360), -0.15, sc); block(x, z, 1.0, 1.0); trees.append((x, z)); return True
for _ in range(30000):                      # dense canopy: north-west woodland, the rim, and the headland flanks
    x = rnd.uniform(-62, 62); z = rnd.uniform(-70, 28); q = float(q_of(x, z))
    nw = (x < -6 and z < -18)
    gap = 4.6 if nw else (5.2 if q > 0.58 else (7.5 if (abs(x) > 28 or z < -20) else 12.0))
    if rnd.random() < (0.9 if nw else 0.6): try_tree(x, z, gap)
for _ in range(1500):                      # shrubs, flowers, tufts at the edges of everything
    x = rnd.uniform(-62, 62); z = rnd.uniform(-70, 28)
    if blocked(x, z, 0.0) or dist_to_paths(np.array(x), np.array(z)) < 3.9: continue
    r = rnd.random()
    if r < 0.55: put(rnd.choice(["SM_Grass_A", "SM_Grass_B"]), x, z, rnd.randrange(360), 0, rnd.uniform(2.0, 3.2))
    elif r < 0.75: put(rnd.choice(["SM_Red_Flower", "SM_Yellow_Flower", "SM_Blue_Flower", "SM_Pink_Flower", "SM_White_Flower"]), x, z, rnd.randrange(360), 0, rnd.uniform(2.0, 3.0))
    elif r < 0.9: put("Tree_04", x, z, rnd.randrange(360), 0, rnd.uniform(0.9, 1.5)); block(x, z, 0.8, 0.8)
    else: put("SM_TrunkTree", x, z, rnd.randrange(360), 0, rnd.uniform(1.0, 1.6))
# rocks / cliffs on steep ground and all round the shore
_h = IH.hgrid(); _gz, _gx = np.gradient(_h, IH.CELL); _sl = np.hypot(_gx, _gz)
def slope_at(x, z): return float(_sl[int(np.clip(round((z - IH.GZ0) / IH.CELL), 0, IH.GNZ - 1)), int(np.clip(round((x - IH.GX0) / IH.CELL), 0, IH.GNX - 1))])
cl = []
for _ in range(60000):
    x = rnd.uniform(-66, 66); z = rnd.uniform(-76, 34); q = float(q_of(x, z))
    if q > 0.97 or any((x - a) ** 2 + (z - b) ** 2 < 36 for a, b in cl): continue
    if dist_to_paths(np.array(x), np.array(z)) < 4.5 or any(math.hypot(x - cx, z - cz) < r + 2 for cx, cz, r in KEEP) or any(abs(x - cx) < hw + 1 and abs(z - cz) < hd + 1 for cx, cz, hw, hd in RECTS): continue
    if z < -40 and abs(x) < 36: continue
    s = slope_at(x, z)
    if q < 0.80 and (s < 1.1 or q < 0.7): continue
    if s > 0.85 and rnd.random() < 0.55: put(rnd.choice(["SM_Vertical_Cliff_01", "SM_Vertical_Cliff_02"]), x, z, rnd.randrange(360), -0.6, rnd.uniform(0.9, 1.5)); cl.append((x, z))
    elif s > 0.5 and rnd.random() < 0.5: put(rnd.choice(["SM_Cliff_01", "SM_Cliff_02", "SM_Cliff_03"]), x, z, rnd.randrange(360), -0.4, rnd.uniform(0.6, 1.0)); cl.append((x, z))
    if len(cl) > 190: break
for k in range(40):                         # shore rocks all round
    a = rnd.random() * 6.283; r = 1.0
    for rr in np.linspace(1.12, 0.9, 40):
        if q_of(62 * rr * math.cos(a), -22 + 56 * rr * math.sin(a)) < 1.0: r = rr; break
    x, z = 62 * r * math.cos(a), -22 + 56 * r * math.sin(a)
    if z > 20 and (abs(x) < 6 or abs(x + 23) < 7): continue
    put(rnd.choice(["SM_Cliff_01", "SM_Cliff_02", "SM_Cliff_03"]), x, z, rnd.randrange(360), -1.0, rnd.uniform(0.4, 0.8), abs_y=False) if False else put(rnd.choice(["SM_Cliff_01", "SM_Cliff_02", "SM_Cliff_03"]), x, z, rnd.randrange(360), -1.2, rnd.uniform(0.5, 0.9), abs_y=True)
for x, z, s in ((-90, -105, 4.0), (95, -90, 3.2), (-105, 20, 3.0), (80, 70, 2.6), (-60, 80, 3.4), (10, -135, 3.8)):
    put("SM_Cliff_02", x, z, rnd.randrange(360), -2.5, s, abs_y=True); put("Tree_02", x + 1, z - 1, 0, 0.5, 0.8 * s / 3, abs_y=True)

# ---- shore colliders: a staircase of boxes just outside the walkable edge; the two piers cut gaps in it
PIERS = [(0.0, 24.0, 33.0), (-23.0, 23.5, 32.0)]
def add_row(xa, xb, zc):
    segs = [(xa, xb)]
    for px, z0, z1 in PIERS:
        if z0 - 2.0 <= zc <= z1 + 3.0:
            new = []
            for a, b in segs:
                lo, hi = px - 3.2, px + 3.2
                if b <= lo or a >= hi: new.append((a, b))
                else:
                    if a < lo: new.append((a, lo))
                    if b > hi: new.append((hi, b))
            segs = new
    for a, b in segs:
        if b - a > 0.3: block((a + b) / 2, zc, b - a, 2.0)
for zc in np.arange(-77, 38, 2.0) + 1.0:
    for sgn in (-1, 1):
        edge = None
        for x in np.arange(0, 74, 0.5):
            if q_of(sgn * x, zc) > 0.86: edge = x; break
        if edge is None: continue
        if sgn < 0: add_row(-74.0, -edge, zc)
        else: add_row(edge, 74.0, zc)
    if q_of(0, zc) > 0.86: add_row(-74.0, 74.0, zc)

# ================================================================ people
NP += [
 dict(id="ferry", name="Ferryman Osk", title="Ferry", sprite="Rook", x=1.4, z=31.0, h=2.3, tint=[0.85, 1.1, 1.2, 1], line="The ferry runs whenever the tide allows. Walk to the end of the pier when you want to head back to the colosseum."),
 dict(id="elder", name="Elder Mahina", title="Village Elder", sprite="Lyra", x=-5.0, z=0.8, h=2.4, tint=[1.15, 1.05, 0.9, 1], line="Welcome to Paradise Island. The mayor lives in the big blue-roofed house up the hill; he has been asking after a stranger who can fight."),
 dict(id="fisher", name="Pua", title="Fisher", sprite="Kael", x=-23.0, z=29.0, h=2.3, tint=[0.9, 1.1, 1.0, 1], line="Biting well today. Don't tell the gulls."),
 dict(id="trader", name="Kai", title="Island Trader", sprite="Yulia", x=24.8, z=13.2, h=2.4, tint=[1.15, 1.0, 0.8, 1], line="Coconuts, shells, and rumours from the mainland. The rumours are free. The crates on the beach are the harbour's; I'd leave them be."),
 dict(id="farmer", name="Old Tane", title="Farmer", sprite="Draven", x=-32.5, z=-9.6, h=2.4, tint=[0.9, 0.95, 1.1, 1], line="Turnips, beans and one very stubborn goat. The goblins have been at my fence ever since they moved into the Whispering Wood."),
 dict(id="keeper", name="Bram", title="Innkeeper", sprite="Lyra", x=tav_door[0] + 0.2, z=tav_door[1] + 1.8, h=2.4, tint=[1.15, 0.95, 0.85, 1],
      actions=[dict(type="say", who="Bram", text="Welcome to the Salty Anchor. A hot meal and a warm bed, on the house for anyone who looks as beaten as you do."), dict(type="rest")]),
 dict(id="smith", name="Hild", title="Blacksmith", sprite="Draven", x=smi_door[0] - 2.0, z=smi_door[1] + 0.4, h=2.5, tint=[1.2, 0.8, 0.7, 1], action="heroes"),
 dict(id="shopkeeper", name="Marla", title="Item Shop", sprite="Rook", x=shp_door[0] - 0.4, z=shp_door[1] - 1.8, h=2.3, tint=[0.8, 1.05, 1.15, 1], action="shop"),
 dict(id="harbourmaster", name="Harbourmaster Teo", title="Harbourmaster", sprite="Kael", x=lod_door[0] + 0.3, z=lod_door[1] + 1.8, h=2.4, tint=[0.8, 0.95, 1.2, 1], line="Mind the boats. The big ferry from the colosseum comes in at the long pier; mine are the little ones."),
 dict(id="scholar", name="Scholar Nema", title="Lore keeper", sprite="Sera", x=-9.0, z=MZ + 6.0, h=2.4, tint=[1.0, 1.05, 1.15, 1], line="The Hollow Cave is older than the colosseum, older than the ladder. The tunnel behind me goes down to a flooded court."),
 # --- Mayor Orrin: four states, driven by the forest quest flags
 dict(id="mayor0", name="Mayor Orrin", title="Mayor", sprite="Kael", x=may_door[0] + 0.2, z=may_door[1] + 1.8, h=2.4, tint=[1.25, 1.1, 0.75, 1], hideIf="fq_start",
      actions=[dict(type="say", who="Mayor Orrin", text="A fighter, at last. I am Orrin, mayor of this island. Listen closely: the Hollow Cave north of the village has been sealed by order of the council, and the Warden's Seal that opens it is gone."),
               dict(type="say", who="Mayor Orrin", text="Ranger Willa carried the Seal into the Whispering Wood to deal with a goblin raiding party that kept robbing the farms. That was three days ago. She has not come back."),
               dict(type="say", who="Mayor Orrin", text="Take the path in the north-west corner of the island. Fight your way through, find Willa, and bring the Seal home. I will make it worth your while."),
               dict(type="flag", key="fq_start")]),
 dict(id="mayor1", name="Mayor Orrin", title="Mayor", sprite="Kael", x=may_door[0] + 0.2, z=may_door[1] + 1.8, h=2.4, tint=[1.25, 1.1, 0.75, 1], showIf="fq_start", hideIf="fq_seal",
      actions=[dict(type="say", who="Mayor Orrin", text="Any sign of Willa? The Whispering Wood is in the north-west. Follow the path past the farm. Goblins and worse live in there, so bring your whole party.")]),
 dict(id="mayor2", name="Mayor Orrin", title="Mayor", sprite="Kael", x=may_door[0] + 0.2, z=may_door[1] + 1.8, h=2.4, tint=[1.25, 1.1, 0.75, 1], showIf="fq_seal", hideIf="fq_done",
      actions=[dict(type="say", who="Mayor Orrin", text="The Warden's Seal! And Willa is safe? You have done this island a great service."),
               dict(type="say", who="Mayor Orrin", text="Take this purse, and my blessing. The council's order is lifted: the Cave Warden will let you through the gate."),
               dict(type="flag", key="fq_done"), dict(type="chest", loot={"gold": 600, "gems": 12})]),
 dict(id="mayor3", name="Mayor Orrin", title="Mayor", sprite="Kael", x=may_door[0] + 0.2, z=may_door[1] + 1.8, h=2.4, tint=[1.25, 1.1, 0.75, 1], showIf="fq_done",
      actions=[dict(type="say", who="Mayor Orrin", text="The cave is open to you now. The old tales say a drowned king sleeps at the bottom of it. Do not wake him lightly.")]),
 # --- the cave warden, before and after the quest
 dict(id="warden0", name="Cave Warden", title="Guard of the cave", sprite="Rook", x=6.4, z=MZ + 4.8, h=2.5, tint=[0.7, 0.8, 1.05, 1], hideIf="fq_done",
      actions=[dict(type="say", who="Cave Warden", text="Halt. The tunnel is sealed by order of the council, and the rockfall will not move without the Warden's Seal."),
               dict(type="say", who="Cave Warden", text="Mayor Orrin knows more. His house is the big one with the blue roof.")]),
 dict(id="warden1", name="Cave Warden", title="Guard of the cave", sprite="Rook", x=6.4, z=MZ + 4.8, h=2.5, tint=[0.7, 0.8, 1.05, 1], showIf="fq_done",
      actions=[dict(type="say", who="Cave Warden", text="The Seal has been returned and the council's order lifted. The rockfall has been cleared."),
               dict(type="say", who="Cave Warden", text="Beyond this arch the old crypt begins. Restless guardians wander it, and at its heart a drowned king keeps his throne. Bring your whole party.")]),
]
for x, z, c in ((-5.0, 0.8, [1, .8, .5, 1]), (1.4, 31, [.5, .85, 1, 1]), (may_door[0], may_door[1] + 1.8, [1, .85, .4, 1]), (tav_door[0], tav_door[1] + 1.8, [1, .7, .4, 1])): glow(x, z, 3.0, c[:3] + [0.7])

# ================================================================ events
EV += [dict(id="ferry_to_colosseum", name="Ferry to the colosseum", x=0, z=32.4, w=7, d=1.6, trigger="touch", once=False,
            actions=[dict(type="warp", scene="outside", x=0, z=35.2)])]
EV += [dict(id="forest_path", name="The Whispering Wood", x=FX, z=FZ - 1.4, w=6.5, d=1.8, trigger="touch", once=False,
            actions=[dict(type="say", who="", text="The path narrows between ancient trunks, and the sea-wind dies away. Something rustles in the leaves ahead."), dict(type="warp", scene="forest", x=0, z=55)])]
EV += [dict(id="forest_sign", name="Signpost", x=FX + 2.6, z=FZ + 5.0, w=3.4, d=3.0, trigger="talk", prompt="Read the signpost",
            actions=[dict(type="say", who="Weathered Signpost", text="NORTH-WEST: the Whispering Wood. Goblins have been seen on the trail. TRAVELLERS GO ARMED.")])]
EV += [dict(id="sign_cave", name="Trail marker", x=3.4, z=-33.0, w=3.4, d=3.0, trigger="talk", prompt="Read the marker",
            actions=[dict(type="say", who="Weathered Marker", text="NORTH: the Hollow Cave. The council has sealed it. WEST: the forest path, the farm and the harbour. SOUTH: the village.")])]
put("SM_Stylized_WantedBoard", 3.4, -34.4, 0, 0, 1.0); block(3.4, -34.4, 2.2, 0.8)
EV += [dict(id="fountain_note", name="Fountain", x=TX, z=TZ + 4.4, w=4.0, d=3.0, trigger="talk", prompt="Read the rim",
            actions=[dict(type="say", who="Carved Rim", text="THE TIDE GIVES, THE TIDE TAKES. DRINK, REST, AND PAY THE SEA ITS DUE.")])]
EV += [dict(id="enter_cave", name="Hollow Cave", x=0, z=MZ - 8.4, w=5.6, d=1.6, trigger="touch", once=False, showIf="fq_done",
            actions=[dict(type="say", who="", text="Cold air breathes out of the dark. The tunnel slopes down into the Hollow Cave."), dict(type="warp", scene="dungeon", x=0, z=-2.0)])]
# a beach chest
put("SM_Stylized_Chest", 30.4, 14.8, 200, 0, 1.4, "!ic_1"); put("SM_Stylized_Basket", 30.4, 14.8, 20, 0, 2.2, "ic_1"); block(30.4, 14.8, 1.4, 1.4)
EV += [dict(id="ic_1", name="Treasure chest", x=30.4, z=14.8, w=4.2, d=4.2, trigger="talk", prompt="Open the chest", hideIf="ic_1",
            actions=[dict(type="flag", key="ic_1"), dict(type="chest", loot={"gold": 180, "gems": 3})])]

OBJ = [dict(unless="fq_start", text="Speak with Mayor Orrin in the big blue-roofed house"),
       dict(**{"if": "fq_start", "unless": "fq_chief"}, text="Find Ranger Willa in the Whispering Wood (the path in the north-west)"),
       dict(**{"if": "fq_chief", "unless": "fq_boss"}, text="Cut through the brambles and reach the Old Oak Grove"),
       dict(**{"if": "fq_boss", "unless": "fq_seal"}, text="Speak with Ranger Willa in the grove"),
       dict(**{"if": "fq_seal", "unless": "fq_done"}, text="Bring the Warden's Seal to Mayor Orrin"),
       dict(unless="dg_boss", text="Enter the Hollow Cave north of the village")]

from island_intro import INTRO
LYR = "/assets/Backgrounds/layers/"
d = dict(name="Paradise Island", kit="", tile=4, pieces=T.P, colliders=T.COL, npcs=NP, events=EV, decals=T.DEC, objectives=OBJ, story=True, autorun=INTRO,
         bounds=dict(minX=-66, maxX=66, minZ=-70, maxZ=36), spawn=dict(x=0, z=22.5), playerHeight=2.4,
         sky=dict(type="layers", base=dict(type="gradient", stops=[[0, "#2f7fd8"], [.4, "#6fb4ee"], [.75, "#bfe3f7"], [1, "#fff4d6"]]),
                  layers=[dict(url=LYR + "clouds_wisps.webp", y=.18, height=.22, drift=.007, alpha=.9, tint=[1, 1, 1]),
                          dict(url=LYR + "clouds_puffy.webp", y=.34, height=.32, drift=.004, alpha=1, tint=[1, 1, 1], parallax=.2),
                          dict(url=LYR + "ridges_far.webp", y=.9, height=.22, parallax=.15, tint=[.7, .85, .95])]),
         fx=[dict(type="dust", amount=.1)], terrain=IH.terrain_json(), walk=WALK,
         light=dict(dir=[-0.4, -1, -0.3], color=[1, 0.96, 0.86], ambient=[0.55, 0.57, 0.64]), fog=dict(color=[0.72, 0.88, 0.97], near=90, far=250))
d.setdefault("music", {"url": "/assets/Music/mp3/04. Peaceful Village.mp3"})
import island_story; island_story.apply(d)          # chapter-1 story chain (Mahina -> Sera at the cave arch -> the cave and the Colosseum guards, see island_story.py)
os.makedirs(OUT, exist_ok=True); json.dump(d, open(os.path.join(OUT, "island.json"), "w"), separators=(",", ":"))
print("pieces", len(T.P), "colliders", len(T.COL), "npcs", len(NP), "events", len(EV), "trees", len(trees))

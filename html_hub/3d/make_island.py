"""Builds html_hub/3d/island.json: the big Paradise Island (Paradise_island kit + God_city ruins), 124 x 112 m: a village with enterable houses
on the south shore, an ancient road north through ruins to a rocky headland with a cave mouth; the cave warps to the `dungeon` scene.
Run:  python make_island.py [outdir]   (needs islandshape.py next to it). Pieces are [model, x, z, rotY, y, scale].  x = east, z = south.
Re-running overwrites hand edits made in /builder3d."""
import json, math, os, random, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from islandshape import q_of
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
PA = "/assets/3D/Paradise/"; GC = "/assets/3D/GodCity/"
P, COL, DEC, NP, EV = [], [], [], [], []
rnd = random.Random(21)
def put(n, x, z, rot=0, y=0, sc=1): P.append([(n if n.startswith("/") else PA + n), round(x, 3), round(z, 3), rot, y, sc])
def gc(n, x, z, rot=0, y=0, sc=1): put(GC + n, x, z, rot, y, sc)
def block(x, z, w, d): COL.append({"x": round(x, 3), "z": round(z, 3), "w": round(w, 3), "d": round(d, 3)})
def glow(x, z, r, c): DEC.append(dict(type="glow", x=x, z=z, r=r, color=c))

# ---------------------------------------------------------------- sea and island
put("SM_ocean", 0, 0, 0, 0, 1); put("SM_island_ground", 0, 0, 0, 0, 1)

# ---------------------------------------------------------------- the village: enterable houses round a swept plaza
# A house is built from the kit's modules at ground level: 7.4 wide x 8 deep, walls 2.8 high, a 3.1 wide doorway in the front wall
# (local +z), a plank floor, a hay roof on top and furniture inside. rot turns the whole house (90 faces +x, 270 faces -x, 0 faces +z).
def house(cx, cz, rot, kind):
    a = math.radians(rot); c, s = math.cos(a), math.sin(a)
    def at(dx, dz): return cx + dx * c + dz * s, cz - dx * s + dz * c
    def p(n, dx, dz, r=0, y=0, sc=1): x, z = at(dx, dz); put(n, x, z, rot + r, y, sc)
    def col(dx, dz, w, d):
        x, z = at(dx, dz); sw = rot % 180 == 90; block(x, z, d if sw else w, w if sw else d)
    W, D = 7.4, 8.0
    x, z = at(0, 0)
    put("SM_floor_wood", x, z, rot, 0.03, 7.6)
    p("SM_module_wall_03", 0, -D / 2, 0)                                       # back wall
    p("SM_entrance_module", 0, D / 2, 0)                                       # front wall with the doorway
    for k, dz in enumerate((-3.0, -1.0, 1.0, 3.0)):                            # side walls, windows in the middle
        for sgn in (-1, 1):
            p("SM_window_module" if k in (1, 2) else "SM_module_wall_01", sgn * W / 2, dz, 90)
    p("SM_roof_02", 0, 0, 0, 2.8, 0.65)
    col(0, -D / 2, W, 0.5); col(-W / 2, 0, 0.5, D); col(W / 2, 0, 0.5, D)      # solid walls
    col(-(W / 2 + 1.55) / 2 - 0.0, D / 2, W / 2 - 1.55, 0.5); col((W / 2 + 1.55) / 2, D / 2, W / 2 - 1.55, 0.5)   # front wall either side of the 3.1 wide door
    if kind == "bedroom":
        p("SM_bed", -2.2, -2.6, 0, 0, 1.0); col(-2.2, -2.6, 3.0, 3.7); p("SM_bed_table", -0.2, -3.5, 0, 0, 1.0); p("SM_pillow", -2.2, -4.0, 0, 0.9, 0.9)
        p("SM_carpet", 1.2, 0.8, 0, 0.04, 0.8); p("SM_table_02", 2.4, -2.2, 0, 0, 1.3); col(2.4, -2.2, 1.5, 1.5); p("SM_chair_01", 3.2, -1.0, -90, 0, 1.4)
        p("SM_lamp", 0.6, -1.0, 0, 1.5, 1.0)
    elif kind == "kitchen":
        p("SM_table_02", 0, -0.6, 0, 0, 1.8); col(0, -0.6, 2.4, 2.4); p("SM_decoration", 0, -0.6, 0, 0.98, 1.5)
        for dx, dz, r in ((-1.9, -0.6, 90), (1.9, -0.6, -90), (0, -2.4, 0), (0, 1.2, 180)): p("SM_chair_01", dx, dz, r, 0, 1.4)
        p("SM_carpet", 0, -0.6, 0, 0.04, 1.2); p("SM_lamp", 0, -0.6, 0, 1.5, 1.0)
        p("SM_bed_table", 3.0, -3.3, 0, 0, 1.8); col(3.0, -3.3, 1.0, 1.0)
    else:                                                                      # storehouse
        p("SM_bed", 2.4, -2.8, 0, 0, 1.0); col(2.4, -2.8, 3.0, 3.7); p("SM_table_02", -2.6, -2.4, 0, 0, 1.5); col(-2.6, -2.4, 1.8, 1.8)
        p("SM_chair_01", -2.6, -0.8, 180, 0, 1.4); p("SM_carpet", 0, 1.4, 90, 0.04, 0.9); p("SM_lamp", -1.0, 0.0, 0, 1.5, 1.0)
house(-15.5, -8.5, 90, "bedroom"); house(15.5, -9.5, 270, "kitchen"); house(-17.5, 5.5, 90, "storehouse"); house(17.0, 6.0, 270, "bedroom"); house(0, -17.5, 0, "kitchen")
# open-air market pavilions on the plaza: a hay roof raised on four posts
for sgn in (-1, 1):
    px = sgn * 9.0
    put("SM_roof_02", px, 12.5, 0 if sgn < 0 else 180, 2.8, 0.55)
    for dx in (-2.6, 2.6):
        for dz in (-3.2, 3.2): put("SM_pillar", px + dx, 12.5 + dz, 0, 0, 1.0); block(px + dx, 12.5 + dz, 0.5, 0.5)
    put("SM_table_02", px, 14.0, 0, 0, 1.8); put("SM_chair_01", px - 1.9, 14.0, 90, 0, 1.4); put("SM_chair_01", px + 1.9, 14.0, -90, 0, 1.4); put("SM_decoration", px, 14.0, 0, 0.98, 1.5)
    block(px, 14.0, 2.4, 2.4)
# torch posts ring the plaza and flank the path to the dock
for k in range(8):
    a = k * math.pi / 4 + 0.39; x, z = 10.2 * math.cos(a), -1.0 + 10.2 * math.sin(a)
    put("SM_pillar", x, z, 0, 0, 1.0); block(x, z, 0.6, 0.6); glow(x, z, 2.2, [1, 0.8, 0.45, 0.6])
for z in (16, 20):
    for sgn in (-1, 1): put("SM_pillar", sgn * 3.4, z, 0, 0, 1.0); block(sgn * 3.4, z, 0.6, 0.6); glow(sgn * 3.4, z, 2.2, [1, 0.8, 0.45, 0.6])
# the plaza centrepiece: a little stone-ringed beacon of rocks and a stair-stepped dais
put("SM_stair_02", 0, -0.5, 180, 0, 1.0); put("SM_pillar", -1.8, -3.6, 0, 0, 1.4); put("SM_pillar", 1.8, -3.6, 0, 0, 1.4); block(0, -2.0, 4.0, 5.0)
# fences around the lawns
for x in (-24, -21, -18): put("SM_fence", x, 14.0, 90, 0, 1.4)
for sgn in (-1, 1):
    for z in (-4, 0, 4): put("SM_fence", sgn * 24.0, z + 14, 90, 0, 1.2)

# ---------------------------------------------------------------- the dock (south shore)
for i in range(7): put("SM_house_support", 0, 24.0 + i * 0.0, 0, 0, 0.0001); P.pop()
put("SM_bridge_01", 0, 27.8, 0, -0.8, 1.15)       # arched plank walkway onto the pier
put("SM_small_boat", -9.5, 29.5, 15, -0.9, 0.6); put("SM_small_boat", 8.5, 30.5, -10, -0.9, 0.55)
for sgn in (-1, 1): put("SM_pillar", sgn * 2.6, 25.2, 0, 0, 1.5); put("SM_pillar", sgn * 2.6, 29.8, 0, -0.5, 1.5)


# ================================================================ the ancient road, the ruins and the cave
def road_x(z): return 2.0 * math.sin(z / 9.0)
# stone forecourt tiles (10 m marble slabs, a few missing) in front of the cave, and one under each ruin
for tx, tz in ((-5, -31), (5, -31), (-5, -40), (5, -40)):
    if rnd.random() < 0.2: continue
    gc("SM_ground_20x20", tx + rnd.uniform(-.3, .3), tz + rnd.uniform(-.3, .3), rnd.choice((0, 90, 180)), -0.15 + rnd.uniform(0, .04), 0.5)
# two rows of weathered columns lining the road; the nearer ones still stand, the rest are stumps
for k, z in enumerate((-24, -29, -34, -39)):
    for sgn in (-1, 1):
        x = road_x(z) + sgn * 5.6; stump = rnd.random() < (0.15 if k < 2 else 0.55); h = rnd.uniform(0.9, 1.9)
        gc(rnd.choice(("SM_temple_column", "SM_temple_column_02")), x, z, rnd.randrange(4) * 90, (-(3.9 - h) if stump else 0), 0.3); block(x, z, 1.0, 1.0)
        if stump and rnd.random() < .6: gc("Sm_large_block", x + rnd.uniform(-1.4, 1.4), z + rnd.uniform(-1.2, 1.2), rnd.randrange(360), -0.15, rnd.uniform(.12, .2))
# the cave mouth: two tall columns, braziers, guardian statues and the mountain itself
MZ = -44.0                                   # world z of the tunnel mouth
put("SM_cave_mountain", 0, MZ, 0, 0, 1); put("SM_cave_inner", 0, MZ, 0, 0, 1)
for sgn in (-1, 1):
    gc("SM_temple_column", sgn * 4.9, MZ + 1.2, 0, 0, 0.34); block(sgn * 4.9, MZ + 1.2, 1.0, 1.0)
    gc("SM_brasero", sgn * 6.8, MZ + 3.0, 0, 0, 0.04); block(sgn * 6.8, MZ + 3.0, 1.2, 1.2); glow(sgn * 6.8, MZ + 3.0, 4.0, [1, .6, .25, .8])
    gc("SM_temple_decoration", sgn * 8.8, MZ + 4.2, 90 if sgn < 0 else 270, 0, 0.5); block(sgn * 8.8, MZ + 4.2, 1.6, 2.4)
for sgn in (-1, 1):                          # rubble at the foot of the mountain
    for k in range(5): put("SM_dg_rock", sgn * rnd.uniform(5, 16), MZ + rnd.uniform(1.5, 4), rnd.randrange(360), 0, rnd.uniform(.9, 1.8))
glow(0, MZ - 9, 3.5, [.35, .55, 1, .35])    # a pale blue gleam deep inside
# solid mountain: left and right masses, back of the tunnel
block(-22.2, MZ - 15.2, 37.6, 30.8); block(22.2, MZ - 15.2, 37.6, 30.8); block(0, MZ - 10.2, 7, 0.8); block(0, MZ - 24, 90, 8)
# ---- ruined temple (north-east): tiles, broken walls, a colonnade and an altar
RX_, RZ_ = 32.0, -31.0
for tx, tz in ((27, -31), (37, -31), (27, -40), (37, -40), (42, -31)):
    if rnd.random() < 0.25: continue
    gc("SM_ground_20x20", tx + rnd.uniform(-.3, .3), tz + rnd.uniform(-.3, .3), rnd.choice((0, 90, 180)), -0.15 + rnd.uniform(0, .04), 0.5)
for i in range(4):                          # back wall (along x)
    x = 25.0 + i * 3.9; h = rnd.choice((1.6, 2.4, 3.0)); gc("SM_wall_10x13", x, -41.0, 90, -(3.0 - h), 0.3); block(x, -41.0, 3.9, 0.7)
    if rnd.random() < .6: gc("SM_ivy_01", x, -40.4, 90, 0.2, 1.3)
for i in range(3):                          # west wall (along z), mostly collapsed
    z = -38.5 + i * 3.9; h = (3.0, 1.4, 0.9)[i]; gc("SM_wall_10x13", 23.0, z, 0, -(3.0 - h), 0.3); block(23.0, z, 0.7, 3.9)
for i, x in enumerate((26, 30, 34, 38, 42)):  # front colonnade
    stump = i in (1, 3); h = rnd.uniform(0.9, 1.7); gc("SM_temple_column_02", x, -26.5, 0, (-(3.9 - h) if stump else 0), 0.3); block(x, -26.5, 1.0, 1.0)
gc("SM_temple_decoration", 33.0, -36.0, 180, 0, 0.7); block(33.0, -36.0, 2.0, 2.6); glow(33, -36, 3.2, [.6, .8, 1, .5])
put("SM_stair_02", 33.0, -25.0, 180, 0, 1.0); put("SM_stair_02", 38.0, -42.5, 0, 0, 0.8)
for _ in range(7): gc("Sm_large_block", RX_ + rnd.uniform(-8, 9), RZ_ + rnd.uniform(-9, 6), rnd.randrange(360), -0.15, rnd.uniform(.1, .18))
for _ in range(5): put("SM_dg_rock", RX_ + rnd.uniform(-9, 10), RZ_ + rnd.uniform(-9, 7), rnd.randrange(360), 0, rnd.uniform(.5, 1.0))
gc("SM_vase_07", 29.5, -35.0, 40, 0, 1.2); gc("SM_vase_03", 36.0, -34.0, 0, 0, 1.4)
# ---- sunken gazebo (north-west): a domed terrace ringed by broken columns
GX, GZ = -31.0, -34.0
for tx, tz in ((-31, -34), (-41, -34), (-31, -44), (-37, -25)):
    if rnd.random() < 0.2: continue
    gc("SM_ground_20x20", tx + rnd.uniform(-.3, .3), tz + rnd.uniform(-.3, .3), rnd.choice((0, 90, 180)), -0.15 + rnd.uniform(0, .04), 0.5)
gc("SM_circular_terrace_02", GX, GZ, 0, -0.4, 1.0); block(GX, GZ, 6.0, 6.0)
for k in range(9):
    a = k * 2 * math.pi / 9 + 0.3; x, z = GX + 8.6 * math.cos(a), GZ + 8.6 * math.sin(a)
    if abs(z - GZ) < 1 and x > GX + 6: continue
    stump = rnd.random() < 0.55; h = rnd.uniform(0.8, 1.8); gc(rnd.choice(("SM_temple_column", "SM_temple_column_03")), x, z, 0, (-(3.9 - h) if stump else 0), 0.3); block(x, z, 1.0, 1.0)
for _ in range(6): gc("Sm_large_block", GX + rnd.uniform(-10, 10), GZ + rnd.uniform(-10, 10), rnd.randrange(360), -0.15, rnd.uniform(.1, .16))
for _ in range(4): put("SM_dg_rock", GX + rnd.uniform(-11, 11), GZ + rnd.uniform(-11, 11), rnd.randrange(360), 0, rnd.uniform(.5, 1.0))
gc("SM_ivy_02", GX - 2.9, GZ, 90, 0.2, 1.3); gc("SM_ivy_03", GX, GZ - 2.9, 0, 0.1, 0.6)
# ---------------------------------------------------------------- vegetation
def inside(x, z): return bool(q_of(x, z) < 0.80)
def near_town(x, z): return abs(x) < 30 and -27 < z < 27
def keep_clear(x, z):
    if near_town(x, z) or not inside(x, z): return True
    if abs(x - road_x(z)) < 8.5 and -50 < z < 12: return True              # ancient road
    if z > 12 and abs(x) < 10: return True                                    # plaza -> dock
    if z < -40 and abs(x) < 46: return True                                   # headland
    for cx, cz, r in ((32, -32, 13), (-31, -34, 14)):
        if math.hypot(x - cx, z - cz) < r: return True
    return False
palms = ["SM_tree_new", "SM_tree_new2", "SM_tree_05", "SM_tree_01"]; trees = []
def try_tree(x, z, gap):
    if keep_clear(x, z) or any(math.hypot(x - a, z - b) < gap for a, b in trees): return False
    put(rnd.choice(palms), x, z, rnd.randrange(360), 0, rnd.uniform(0.30, 0.44)); block(x, z, 1.0, 1.0); trees.append((x, z)); return True
for k in range(2000):                      # palm groves, denser the farther from the village
    x = rnd.uniform(-62, 62); z = rnd.uniform(-74, 30); dens = 1.0 if abs(x) > 34 or z < -30 else 0.45
    if rnd.random() < dens and try_tree(x, z, 6.6 if dens > .5 else 8.5) and len(trees) >= 85: break
for k in range(170):                       # village-side palms (looser, away from the houses)
    x = rnd.uniform(-30, 30); z = rnd.uniform(-27, 27)
    if not (math.hypot(x, z + 1.5) > 13) or any(abs(x - a) < 6 and abs(z - c) < 7 for a, c in ((-15.5, -8.5), (15.5, -9.5), (-17.5, 5.5), (17, 6), (0, -17.5), (-9, 12.5), (9, 12.5))): continue
    if (z > 12 and abs(x) < 10) or (abs(x) < 7 and z > 8) or any(math.hypot(x - a, z - b) < 6.5 for a, b in trees) or not inside(x, z): continue
    put(rnd.choice(palms), x, z, rnd.randrange(360), 0, rnd.uniform(0.30, 0.42)); block(x, z, 1.0, 1.0); trees.append((x, z))
    if len([1 for t in trees if near_town(*t)]) >= 22: break
smalls = ["SM_Plant_01", "SM_Plant_02", "SM_Plant_03", "SM_grass_01", "SM_grass_02"]
for _ in range(650):
    x = rnd.uniform(-62, 62); z = rnd.uniform(-74, 30)
    if not inside(x, z) or (math.hypot(x, z + 1.5) < 12.5) or (abs(x - road_x(z)) < 3.0 and -48 < z < 12) or (z > 12 and abs(x) < 6): continue
    if any(abs(x - a) < 5 and abs(z - c) < 6 for a, c in ((-15.5, -8.5), (15.5, -9.5), (-17.5, 5.5), (17, 6), (0, -17.5))) or (z < -42 and abs(x) < 46): continue
    n = rnd.choice(smalls); put(n, x, z, rnd.randrange(360), 0, rnd.uniform(0.9, 1.5) if "Plant" in n else rnd.uniform(2.0, 3.0))
    if len(P) > 1900: break
for _ in range(0):                          # big ferns in the jungle (SM_Plant_05 has no texture yet: a grey flower)
    x = rnd.uniform(-60, 60); z = rnd.uniform(-70, 24)
    if inside(x, z) and not keep_clear(x, z): put("SM_Plant_05", x, z, rnd.randrange(360), 0, 0.8)
for k in range(34):                         # shore rocks all round
    a = rnd.random() * 6.283; r = 1.0
    for rr in np.linspace(1.12, 0.9, 40):
        if q_of(62 * rr * math.cos(a), -22 + 56 * rr * math.sin(a)) < 1.0: r = rr; break
    x, z = 62 * r * math.cos(a), -22 + 56 * r * math.sin(a)
    if z > 21 and abs(x) < 14: continue
    put(rnd.choice(["SM_rock_01", "SM_rock_02"]), x, z, rnd.randrange(360), -0.5, rnd.uniform(0.7, 1.4))
for x, z, s in ((-90, -105, 6.0), (95, -90, 4.5), (-105, 20, 4.0), (80, 70, 3.6), (-60, 80, 4.6), (10, -135, 5.0)):   # distant islets
    put("SM_rock_02", x, z, rnd.randrange(360), -1.2, s); put("SM_tree_new", x + 1, z - 1, 0, 2.6 * s / 5, 0.5 * s / 5 + 0.3)
# shore colliders: staircase of boxes just inside the waterline so the ellipse is the walkable edge
for zc in np.arange(-77, 29, 2.0) + 1.0:
    for sgn in (-1, 1):
        edge = None
        for x in np.arange(0, 74, 0.5):
            if q_of(sgn * x, zc) > 0.86: edge = x; break
        if edge is None: continue
        w = 74.0 - edge; block(sgn * (edge + w / 2), zc, w, 2.0)
    if q_of(0, zc) > 0.86: block(0, zc, 150, 2.0)

# ---------------------------------------------------------------- people
NP += [
 dict(id="ferry", name="Ferryman Osk", title="Ferry", sprite="Rook", x=2.4, z=21.0, h=2.3, tint=[0.85, 1.1, 1.2, 1], line="The ferry runs whenever the tide allows. Walk onto the pier when you want to head back to the colosseum."),
 dict(id="elder", name="Elder Mahina", title="Village Elder", sprite="Lyra", x=-3.4, z=-4.4, h=2.4, tint=[1.15, 1.05, 0.9, 1], line="Welcome to Paradise Island. Walk the old road north if you're brave: the ruins, and the cave beyond, have swallowed more than one fighter."),
 dict(id="fisher", name="Pua", title="Fisher", sprite="Kael", x=-11.5, z=19.0, h=2.3, tint=[0.9, 1.1, 1.0, 1], line="Biting well today. Don't tell the gulls."),
 dict(id="trader", name="Kai", title="Island Trader", sprite="Yulia", x=9.0, z=15.8, h=2.4, tint=[1.15, 1.0, 0.8, 1], line="Coconuts, shells, and rumours from the mainland. The rumours are free."),
 dict(id="hermit", name="Old Tane", title="Hermit", sprite="Draven", x=-19.5, z=-0.5, h=2.4, tint=[0.9, 0.95, 1.1, 1], line="They say the oldest palm on the island remembers every storm. I just sit under it."),
 dict(id="scholar", name="Scholar Nema", title="Ruins scholar", sprite="Sera", x=-8.5, z=-30.5, h=2.4, tint=[1.0, 1.05, 1.15, 1], line="These ruins are older than the colosseum, older than the ladder. The tunnel behind me goes down to a flooded court."),
 dict(id="warden", name="Cave Warden", title="Guard of the cave", sprite="Rook", x=6.4, z=-39.2, h=2.5, tint=[0.7, 0.8, 1.05, 1],
      actions=[dict(type="say", who="Cave Warden", text="Beyond this arch the old crypt begins. Restless guardians wander it, and at its heart a drowned king keeps his throne."),
               dict(type="say", who="Cave Warden", text="Bring your whole party. Fights down there do not end until one side stands. Step into the tunnel when you are ready.")]),
]
for x, z, c in ((-3.4, -4.4, [1, .8, .5, 1]), (9, 15.8, [1, .75, .4, 1]), (2.4, 21, [.5, .85, 1, 1])): glow(x, z, 3.0, c[:3] + [0.7])

# ---------------------------------------------------------------- events
EV += [dict(id="ferry_to_colosseum", name="Ferry to the colosseum", x=0, z=24.4, w=8, d=1.6, trigger="touch", once=False,
            actions=[dict(type="warp", scene="outside", x=0, z=35.2)])]
EV += [dict(id="shrine_note", name="Stone cairn", x=18.5, z=-1.5, w=3.2, d=3.2, trigger="talk", prompt="Read the carving",
            actions=[dict(type="say", who="Carved Stone", text="Rest well, wanderer. The arena will wait.")])]
put("SM_rock_01", 18.5, -1.5, 30, 0, 0.5); block(18.5, -1.5, 1.4, 1.4)
put("/assets/3D/Dungeon/SM_dg_tablet", 5.6, -12.9, 0, 0, 0.8); block(5.6, -12.9, 1.3, 0.4)
EV += [dict(id="sign_road", name="Trail marker", x=5.6, z=-12.2, w=3.4, d=3.0, trigger="talk", prompt="Read the marker",
            actions=[dict(type="say", who="Weathered Marker", text="NORTH: the Old Road, the ruined courts, and the Hollow Cave. SOUTH: the village and the ferry.")])]
EV += [dict(id="ne_altar", name="Broken altar", x=33.0, z=-36.0, w=4.0, d=4.0, trigger="talk", prompt="Read the inscription",
            actions=[dict(type="say", who="Worn Inscription", text="HERE THE COURT OF THE TIDE KEPT ITS ORACLE. WHEN THE SEA ROSE THE KING WENT DOWN WITH HIS CROWN, AND THE HALL WAS SEALED.")])]
EV += [dict(id="nw_gazebo", name="Sunken gazebo", x=GX, z=GZ + 4.4, w=4.0, d=3.0, trigger="talk", prompt="Look inside",
            actions=[dict(type="say", who="", text="Moss and salt have eaten the carvings, but a sunburst is still cut into the floor, pointing north toward the cave.")])]
EV += [dict(id="enter_cave", name="Hollow Cave", x=0, z=MZ - 8.4, w=5.6, d=1.6, trigger="touch", once=False,
            actions=[dict(type="say", who="", text="Cold air breathes out of the dark. The tunnel slopes down into the Hollow Crypt."), dict(type="warp", scene="dungeon", x=0, z=-2.0)])]

LYR = "/assets/Backgrounds/layers/"
d = dict(name="Paradise Island", kit="", tile=4, pieces=P, colliders=COL, npcs=NP, events=EV, decals=DEC,
         bounds=dict(minX=-66, maxX=66, minZ=-70, maxZ=25.6), spawn=dict(x=0, z=19.8), playerHeight=2.4,
         sky=dict(type="layers", base=dict(type="gradient", stops=[[0, "#2f7fd8"], [.4, "#6fb4ee"], [.75, "#bfe3f7"], [1, "#fff4d6"]]),
                  layers=[dict(url=LYR + "clouds_wisps.webp", y=.18, height=.22, drift=.007, alpha=.9, tint=[1, 1, 1]),
                          dict(url=LYR + "clouds_puffy.webp", y=.34, height=.32, drift=.004, alpha=1, tint=[1, 1, 1], parallax=.2),
                          dict(url=LYR + "ridges_far.webp", y=.9, height=.22, parallax=.15, tint=[.7, .85, .95])]),
         fx=[dict(type="dust", amount=.1)],
         light=dict(dir=[-0.4, -1, -0.3], color=[1, 0.96, 0.86], ambient=[0.55, 0.57, 0.64]), fog=dict(color=[0.72, 0.88, 0.97], near=90, far=250))
os.makedirs(OUT, exist_ok=True); json.dump(d, open(os.path.join(OUT, "island.json"), "w"), separators=(",", ":"))
print("pieces", len(P), "colliders", len(COL), "npcs", len(NP), "events", len(EV))

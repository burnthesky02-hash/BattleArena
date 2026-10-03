"""Builds html_hub/3d/outside.json: the marble hill-city outside the Olympus colosseum, built from the God_city kit (Assets/3D/GodCity,
textured by UassetConverter). Load it with /?scene=outside ; olympus.json warps here from its south exit and back through the gate.
Run:  python make_outside.py [outdir]     Pieces are [model, x, z, rotY, y, scale].  Once you hand-edit outside.json in the 3D editor,
stop re-running this (it overwrites the file).   x = east, z = south (the camera looks north, so the facade is at the back)."""
import json, math, os, random, sys
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
G = "/assets/3D/GodCity/"
def g(n): return G + n
W20, W13, COLM, COLM2, BEAM = g("SM_wall_10x20"), g("SM_wall_10x13"), g("SM_temple_column"), g("SM_temple_column_02"), g("SM_beam_02")
GROUND, G12, G8, G3, GS = g("SM_ground_20x20"), g("SM_garden_12x12"), g("SM_garden_8x8"), g("SM_garden_3x12"), g("SM_garden_small")
TOWER3, TOWER4, BRAS, TERR, TERR2 = g("SM_fire_tower_03"), g("SM_fire_tower_04"), g("SM_brasero"), g("SM_circular_terrace"), g("SM_circular_terrace_02")
ROOF1, ROOF2, AMPHI, ARC, HUGE, BRIDGE, MOUNT = g("SM_temple_roof_prefab_01"), g("SM_temple_roof_prefab_02"), g("SM_amphitheatre"), g("SM_arc_entrance"), g("SM_Garden_huge"), g("SM_bridge_prefab"), g("SM_mountain")
FAB2, FAB3, FAB5, FAB6, FAB4 = g("SM_fabric_decoration_02"), g("SM_fabric_decoration_03"), g("SM_fabric_decoration_05"), g("SM_fabric_decoration_06"), g("SM_fabric_decoration_04")
MT1, MT2, MT3 = g("SM_market_tent_01"), g("SM_market_tent_02"), g("SM_market_tent_03")
LIGHT, RAIL, RAIL2 = g("SM_light"), g("SM_railing"), g("SM_railing_02")
BUSH = [g("SM_bush_0%d" % i) for i in (1, 2, 3, 4)]
VASE = [g("SM_vase_0%d" % i) for i in (1, 2, 3, 4, 6, 7)]
FLOW, CLUMP, IVY3 = g("SM_flowers_01"), g("SM_grass_clump"), g("SM_ivy_03")
CRATE, BASKET, APPLE, BAG, TABLE, TABLE2 = g("SM_crate_01"), g("SM_basket_01"), g("SM_Apple_crate"), g("SM_merchandise_bag_01"), g("Sm_table_01"), g("SM_table_02")
CARPET, CARPSQ = g("SM_carpet_01"), g("SM_carpet_square")
ROCK1, ROCK2, TDEC = g("SM_rock_01"), g("SM_rock_02"), g("SM_temple_decoration")
P, COL, DEC, NP, EV = [], [], [], [], []
rnd = random.Random(11)
def put(n, x, z, rot=0, y=0, sc=1): P.append([n, round(x, 3), round(z, 3), rot, y, sc])
def block(x, z, w, d): COL.append({"x": round(x, 3), "z": round(z, 3), "w": round(w, 3), "d": round(d, 3)})
def glow(x, z, r, c): DEC.append(dict(type="glow", x=x, z=z, r=r, color=c))

# ---------------------------------------------------------------- ground: marble paving everywhere, lawns in garden plots
for x in range(-50, 51, 20):
    for z in range(-70, 71, 20): put(GROUND, x, z, 0, -0.5, 1)

# ---------------------------------------------------------------- the hill behind the colosseum: terraced gardens, arcade, mountains
put(HUGE, 0, -62, 0, 0, 0.5)                                    # 97 wide stepped terraces
put(BRIDGE, 0, -92, 0, 0, 0.55); put(BRIDGE, -85, -80, 0, 0, 0.55); put(BRIDGE, 85, -80, 0, 0, 0.55)
put(AMPHI, 0, -45, 90, 0, 1.35)                                 # the great oval, rising behind the facade
for sgn in (-1, 1):
    put(TOWER3, sgn * 40, -30, 0, 0, 0.14); put(TOWER3, sgn * 62, -52, 0, 0, 0.16); put(TOWER4, sgn * 30, -60, 0, 0, 0.3)
    put(BRAS, sgn * 56, -22, 0, 0, 0.2); put(TERR, sgn * 74, -34, 0, 0, 0.26)
    
put(MOUNT, 0, -230, 0, -4, 0.2); put(MOUNT, -190, -200, 0, -4, 0.16); put(MOUNT, 190, -210, 0, -4, 0.16)

# ---------------------------------------------------------------- the colosseum facade (north), gate in the middle
FZ = -15.0
for sgn in (-1, 1):
    put(W20, sgn * 13.2, FZ, 90, 0, 0.8); put(W13, sgn * 26.4, FZ, 90, 0, 0.8)
    put(W20, sgn * 11.2, FZ - 1.2, 90, 8, 0.6); put(W13, sgn * 21.1, FZ - 1.2, 90, 8, 0.6)
    put(ROOF1, sgn * 12.0, FZ - 2.0, 0, 12.6, 0.42)
put(W13, 0, FZ - 2.6, 90, 0, 0.8)
for sgn in (-1, 1):
    for x in (9, 14, 19, 24): put(COLM2 if x in (14, 24) else COLM, sgn * x, FZ + 2.2, 0, 0, 0.62)
    for x in (11.5, 16.5, 21.5): put(BEAM, sgn * x, FZ + 2.2, 90, 7.9, 1.0)
    for x in (11.5, 16.5, 21.5): put(FAB3, sgn * x, FZ + 1.6, 0, 0.4, 0.25)                 # blue banners between the columns
    put(TOWER3, sgn * 30, FZ - 2, 0, 0, 0.1)
for sgn in (-1, 1): put(COLM, sgn * 5.2, FZ + 1.6, 0, 0, 0.9)
put(BEAM, 0, FZ + 1.6, 90, 11.3, 2.2)
put(FAB2, -2.4, FZ + 1.9, 0, 4.0, 0.28); put(FAB2, 2.4, FZ + 1.9, 0, 4.0, 0.28)
for sgn in (-1, 1): block(sgn * 14.2, FZ + 1.6, 20, 4.2); block(sgn * 5.2, FZ + 1.6, 2.4, 2.4)
block(0, FZ - 1.6, 12, 1.2)

# ---------------------------------------------------------------- the fountain, with lawns and braziers around the plaza
FOUNT = (0, 3.0)
for sgn in (-1, 1):
    put(G12, sgn * 16, -3, 0, 0, 1.0); put(G12, sgn * 16, 10, 0, 0, 1.0)
    put(G8, sgn * 22.5, 20, 0, 0, 1.0); put(G12, sgn * 16, 30, 0, 0, 1.0)
    for z in (-3, 10, 30): block(sgn * 16, z, 12, 12)
    block(sgn * 22.5, 20, 8, 8); put(TERR2, sgn * 22.5, 20, 0, 0.2, 0.95)
    put(BRAS, sgn * 11.5, 18, 0, 0, 0.13); block(sgn * 11.5, 18, 2.4, 2.4)             # small domed shrines
for sgn in (-1, 1):
    for z in (14, 22, 30, 38):
        put(g('SM_Brasero_02'), sgn * 5.6, z, 0, 0, 0.09); block(sgn * 5.6, z, 0.8, 0.8); glow(sgn * 5.6, z, 3.0, [1, 0.85, 0.5, 1])
    for z in range(-1, 36, 6): put(RAIL, sgn * 7.4, z, 90, 0, 0.3)
for sgn in (-1, 1):
    for z in (-6, 4, 10, 18, 27):
        x = sgn * 16; put(BUSH[rnd.randrange(4)], x + rnd.uniform(-3, 3), z + rnd.uniform(-2, 2), rnd.randrange(360), 0.2, rnd.uniform(1.2, 1.7))
    for _ in range(26): put(rnd.choice((FLOW, CLUMP)), sgn * 16 + rnd.uniform(-5, 5), rnd.uniform(-8, 34), rnd.randrange(360), 0.2, 6 if True else 1)
    for z in (-8, 5): put(VASE[0], sgn * 8.4, z, 0, 0, 2.2)

# ---------------------------------------------------------------- the market
def stall(cx, cz, rot, tent):
    put(tent, cx, cz, rot, 0, 1.15); a = math.radians(rot); c, s = math.cos(a), math.sin(a)
    def at(dx, dz): return cx + dx * c + dz * s, cz - dx * s + dz * c
    x, z = at(0, 3.6); put(CRATE, x, z, rot, 0, 1.8)
    x, z = at(-2.6, 3.4); put(BASKET, x, z, rot, 0, 1.8)
    x, z = at(2.6, 3.4); put(APPLE, x, z, rot, 0, 1.9)
    block(cx, cz, 6.4, 9.6) if rot in (0, 180) else block(cx, cz, 9.6, 6.4)
stall(15.5, 0.0, 90, MT2); stall(15.5, 8.5, 90, MT1); stall(-15.5, 4.0, 270, MT3)
for x, z in ((19.0, 5.0), (11.5, 11.5), (-19.5, 8.5)): put(BAG, x, z, 0, 0, 2.0)
put(CARPSQ, 0, 9.5, 0, 0.05, 0.7); put(CARPET, 0, -10.5, 90, 0.05, 0.6)

# ---------------------------------------------------------------- the road south, with the town gate
for sgn in (-1, 1):
    put(ARC, sgn * 10.0, 44.0, 90, 0, 0.35); block(sgn * 10.0, 44.0, 5, 7)
    put(TOWER4, sgn * 14, 43, 0, 0, 0.22)
    put(ROCK1, sgn * 45, 20, 0, 0, 0.08); put(ROCK2, sgn * 36, 44, 0, 0, 0.16)

# ---------------------------------------------------------------- people
NP += [
 dict(id="guard", name="Gate Guard", title="Colosseum Gate", sprite="Draven", x=-5.8, z=-10.5, h=2.5, line="The arena is open to all challengers. Step through the gate when you're ready.", reach=4.8),
 dict(id="crier", name="Town Crier", title="News", sprite="Kael", x=5.0, z=6.5, h=2.4, tint=[1.15, 0.95, 0.75, 1], line="Hear ye! Fresh blood on the ladder, and the Champion has not been beaten in a season!"),
 dict(id="vendor", name="Pip", title="Fruit seller", sprite="Rook", x=12.0, z=1.2, h=2.2, tint=[0.85, 1.15, 0.85, 1], line="Apples, figs, a little luck! Best you'll find outside the walls."),
 dict(id="traveler", name="Mara", title="Traveller", sprite="Lyra", x=-12.5, z=5.5, h=2.4, tint=[1.1, 1.0, 1.2, 1], line="They say the road south leads to the old forest. I'm waiting on my escort."),
 dict(id="road", name="Harbour Warden", title="Ferry Landing", sprite="Yulia", x=6.5, z=36.0, h=2.4, line="The ferry to Paradise Island leaves from the end of the road. A quiet place to rest between bouts."),
]
DEC += [dict(type="glow", x=0, z=-12.4, r=6.5, color=[1, 0.8, 0.45, 1])]

# ---------------------------------------------------------------- events: the gate leads into the colosseum
EV += [dict(id="enter_colosseum", name="Colosseum gate", x=0, z=-13.6, w=7, d=2.6, trigger="touch", once=False,
            actions=[dict(type="warp", scene="olympus", x=0, z=14.2)])]
EV += [dict(id="ferry_to_island", name="Ferry to Paradise Island", x=0, z=37.8, w=7, d=1.6, trigger="touch", once=False,
            actions=[dict(type="warp", scene="island", x=0, z=19.8)])]
EV += [dict(id="notice", name="Notice board", x=-19.0, z=-6.0, w=3.2, d=3.2, trigger="talk", prompt="Read the notice board",
            actions=[dict(type="say", who="Notice Board", text="BOUT SCHEDULE: Recruit bouts at dawn. The Unbroken Pair will face any who clear Rank 2."),
                     dict(type="say", who="Notice Board", text="Mercenaries wanted. Apply at the Summoning Circle, inside.")])]
put(FAB5, -19.0, -6.0, 0, 0, 0.5); put(g("SM_construction_block_01"), -19.0, -6.0, 0, 0, 0.6); block(-19.0, -6.0, 1.2, 1.4)

LYR = "/assets/Backgrounds/layers/"
d = dict(name="Outside the Colosseum", kit="", tile=4, pieces=P, colliders=COL, npcs=NP, events=EV, decals=DEC,
         bounds=dict(minX=-23.5, maxX=23.5, minZ=-16.2, maxZ=38.5), spawn=dict(x=0, z=-9.5), playerHeight=2.4,
         sky=dict(type="layers", base=dict(type="gradient", stops=[[0, "#3f86d6"], [.4, "#7fb6ec"], [.75, "#cfe6f8"], [1, "#fff6e0"]]),
                  layers=[dict(url=LYR + "clouds_wisps.webp", y=.18, height=.22, drift=.007, alpha=.9, tint=[1, 1, 1]),
                          dict(url=LYR + "clouds_puffy.webp", y=.34, height=.32, drift=.004, alpha=1, tint=[1, 1, 1], parallax=.2),
                          dict(url=LYR + "ridges_far.webp", y=.88, height=.3, parallax=.15, tint=[.78, .86, .98])]),
         fx=[dict(type="dust", amount=.12)],
         light=dict(dir=[-0.4, -1, -0.35], color=[0.95, 0.9, 0.8], ambient=[0.62, 0.63, 0.7]), fog=dict(color=[0.78, 0.88, 0.97], near=80, far=230))
os.makedirs(OUT, exist_ok=True); json.dump(d, open(os.path.join(OUT, "outside.json"), "w"), separators=(",", ":"))
print("pieces", len(P), "colliders", len(COL), "npcs", len(NP), "events", len(EV))

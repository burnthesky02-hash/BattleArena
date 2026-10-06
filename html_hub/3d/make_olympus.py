"""Builds html_hub/3d/olympus.json: the colosseum hall, built from the God_city kit (Assets/3D/GodCity, textured by UassetConverter).
Load it with  /?scene=olympus .  Run:  python make_olympus.py [outdir]     Pieces are [model, x, z, rotY, y, scale].
The exit warp back to the outside scene is defined at the bottom (events). Hand-edits in the 3D editor are overwritten if you re-run this."""
import json, math, os, random, sys
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
G = "/assets/3D/GodCity/"
def g(n): return G + n
W20, W13, COLM, COLM2, BEAM = g("SM_wall_10x20"), g("SM_wall_10x13"), g("SM_temple_column"), g("SM_temple_column_02"), g("SM_beam_02")
GROUND, AMPHI, BRAS, TOWER3, TOWER4, HUGE = g("SM_ground_20x20"), g("SM_amphitheatre"), g("SM_Brasero_02"), g("SM_fire_tower_03"), g("SM_fire_tower_04"), g("SM_Garden_huge")
FAB3, FAB2, FAB5, FAB6 = g("SM_fabric_decoration_03"), g("SM_fabric_decoration_02"), g("SM_fabric_decoration_05"), g("SM_fabric_decoration_06")
MT2, CRATE, BASKET, APPLE, BAG, TABLE = g("SM_market_tent_02"), g("SM_crate_01"), g("SM_basket_01"), g("SM_Apple_crate"), g("SM_merchandise_bag_01"), g("SM_table_02")
CARPET, CARPTHIN, CARPSQ, RAIL2 = g("SM_carpet_01"), g("SM_carpet_thin"), g("SM_carpet_square"), g("SM_railing_02")
B1, B2, B4 = g("SM_construction_block_01"), g("SM_construction_block_02"), g("SM_large_block") if False else g("SM_construction_block_01")
VASE = [g("SM_vase_0%d" % i) for i in (1, 2, 3, 4, 6, 7)]
ROOF1, BRIDGE, MOUNT, TERR2, TERR = g("SM_temple_roof_prefab_01"), g("SM_bridge_prefab"), g("SM_mountain"), g("SM_circular_terrace_02"), g("SM_circular_terrace")
P, COL, DEC = [], [], []
rnd = random.Random(5)
def put(n, x, z, rot=0, y=0, sc=1): P.append([n, round(x, 3), round(z, 3), rot, y, sc])
def block(x, z, w, d): COL.append({"x": x, "z": z, "w": w, "d": d})
def glow(x, z, r, c): DEC.append(dict(type="glow", x=x, z=z, r=r, color=c))
WS = 0.5                                   # wall/column scale: wall 5 tall x 10 long, column 6.5 tall (heroes are 2.4)
CH = 13.04 * WS

for x in range(-40, 41, 20):               # marble floor
    for z in range(-30, 51, 20): put(GROUND, x, z, 0, -0.5, 1)

# the great oval, the hanging gardens and the arcades rising behind the back wall
put(AMPHI, 0, -52, 90, 0, 1.7)
put(HUGE, 0, -92, 0, 0, 0.6); put(BRIDGE, 0, -112, 0, 0, 0.6)
for sgn in (-1, 1):
    put(TOWER3, sgn * 30, -22, 0, 0, 0.13); put(TOWER3, sgn * 46, -40, 0, 0, 0.15); put(TOWER4, sgn * 26, 30, 0, 0, 0.26)
    put(TERR, sgn * 52, -4, 0, 0, 0.3); put(ROOF1, sgn * 36, 2, 90, 0, 0.5)
put(MOUNT, 0, -260, 0, -4, 0.2); put(MOUNT, -200, -230, 0, -4, 0.16); put(MOUNT, 200, -240, 0, -4, 0.16)

# perimeter walls (walls run along local z; rotY 90 turns them along x)
BZ, SX = -10.6, 19.9
for sgn in (-1, 1):
    put(W20, sgn * 9, BZ, 90, 0, WS); put(W13, sgn * 17.25, BZ, 90, 0, WS)          # back wall, gate gap |x|<4
    r = 0 if sgn < 0 else 180
    put(W20, sgn * SX, -5.6, r, 0, WS); put(W20, sgn * SX, 4.4, r, 0, WS); put(W13, sgn * SX, 11.65, r, 0, WS); put(W13, sgn * SX, 18.15, r, 0, WS)
    put(COLM, sgn * SX, BZ, 0, 0, 0.7); put(COLM, sgn * SX, 20.6, 0, 0, 0.55)           # corner columns
    block(sgn * SX, BZ, 2, 2)
    for z in (-3.5, 3.5, 10.5): put(FAB3, sgn * (SX - 1.4), z, 90 * sgn, 0.6, 0.27)      # banners down the side walls
    for x in (6.5, 11.0, 15.5): put(FAB3, sgn * x, BZ + 0.8, 0, 0.6, 0.27)               # ...and along the back wall
    put(BRAS, sgn * 17.6, -8.6, 0, 0, 0.14); put(BRAS, sgn * 17.6, 16.0, 0, 0, 0.14)      # braziers in the corners
    put(ROOF1, sgn * 9, BZ - 2.2, 0, CH, 0.34)                                         # tiled roofs over the back wall

# the gate: two tall columns and a lintel beam across them
for sgn in (-1, 1):
    put(COLM, sgn * 4.7, -10.0, 0, 0, 0.62); block(sgn * 4.7, -10.0, 1.8, 1.8)
    put(FAB2, sgn * 2.4, -9.8, 0, 3.4, 0.26); put(VASE[0], sgn * 6.4, -8.4, 0, 0, 2.2)
put(BEAM, 0, -10.0, 90, 7.7, 2.0)

# colonnade along the back wall, paired columns carrying beams
for sgn in (-1, 1):
    for x in (8.0, 13.5):
        put(COLM2 if x == 13.5 else COLM, sgn * x, -8.2, 0, 0, WS); block(sgn * x, -8.2, 1.4, 1.4)
    put(BEAM, sgn * 10.75, -8.2, 90, CH - 0.35, 1.1)

# red carpets lead from the gate to the summoning circle and on to the exit
put(CARPTHIN, 0, -1.2, 90, 0.05, 0.55); put(CARPTHIN, 0, 8.5, 90, 0.05, 0.55); put(CARPSQ, 0, 3.2, 0, 0.05, 1.05)

# summoning circle: four short columns around the glyph
for k in range(4):
    a = math.pi / 4 + k * math.pi / 2; cx, cz = 4.3 * math.cos(a), 3.2 + 4.3 * math.sin(a)
    put(COLM2, cx, cz, 0, 0, 0.25); block(cx, cz, 0.9, 0.9)

# Rook's market stall: a striped tent with a counter and wares
put(MT2, 13, 4.2, 90, 0, 0.9); block(13, 6.2, 5.8, 2.6)
put(TABLE, 13, 6.6, 90, 0, 1.2); put(CRATE, 10.8, 7.4, 20, 0, 1.6); put(BASKET, 15.3, 7.6, 0, 0, 1.6); put(APPLE, 16.2, 6.2, 90, 0, 1.7)
# supply stacks in the back corners
for sgn in (-1, 1):
    put(B1, sgn * 16.4, -6.6, 90 * sgn, 0, 0.55); put(CRATE, sgn * 16.4, -5.2, 0, 0, 1.7); put(BAG, sgn * 14.9, -6.9, 0, 0, 2.2)
    block(sgn * 15.9, -6.0, 3.6, 3.0)
# trainer yard rail and ruined columns
for x in (-14.2, -11.0): put(RAIL2, x, 13.4, 90, 0, 1.0)
block(-12.7, 13.4, 5, 1)
put(COLM, -17.2, 10.6, 0, 0, 0.3); block(-17.2, 10.6, 1.2, 1.2); put(COLM, 17.0, 12.6, 0, 0, 0.3); block(17.0, 12.6, 1.2, 1.2)
for x, z in ((-8.6, 12.6), (8.8, 12.0), (-17.6, 3.4)): put(rnd.choice(VASE), x, z, 0, 0, 2.2)

NP = [
 dict(id="boss", name="Gate Warden", title="Colosseum Gate", sprite="Draven", x=0, z=-6.4, h=2.5, action="challenge", reach=5.2, radius=1.3),
 dict(id="battle", name="Draven", title="Battlemaster", sprite="Draven", x=-9.5, z=-1.5, h=2.4, action="battle"),
 dict(id="ladder", name="Kael", title="Rank Keeper", sprite="Kael", x=9.5, z=-1.5, h=2.4, action="ladder"),
 dict(id="summon", name="Sera", title="Summoner", sprite="Sera", x=0, z=3.2, h=2.4, action="summon", reach=5.0),
 dict(id="heroes", name="Lyra", title="Trainer", sprite="Lyra", x=-11.5, z=8.5, h=2.4, action="heroes"),
 dict(id="shop", name="Rook", title="Shopkeeper", sprite="Rook", x=13, z=7.2, h=2.4, action="shop"),
 dict(id="world", name="Yulia", title="Scout", sprite="Yulia", x=17.2, z=15, h=2.4, action="world"),
 dict(id="save", name="Scribe", title="Records", sprite="Kael", x=-17.2, z=15, h=2.3, action="save_and_quit", tint=[0.75, 0.88, 1.15, 1]),
]
DEC += [dict(type="glyph", x=0, z=3.2, r=3.4, color=[0.6, 0.4, 1, 1], spin=14),
        dict(type="glow", x=0, z=-6, r=6, color=[1, 0.8, 0.45, 1]), dict(type="glow", x=13, z=6, r=5, color=[1, 0.75, 0.4, 1]),
        dict(type="glow", x=-9.5, z=-1.5, r=4, color=[1, 0.4, 0.3, 1]), dict(type="glow", x=9.5, z=-1.5, r=4, color=[0.5, 0.8, 1, 1]),
        dict(type="glow", x=-11.5, z=8.5, r=4, color=[0.5, 1, 0.6, 1])]
for sgn in (-1, 1): glow(sgn * 17.6, -8.6, 4, [1, 0.7, 0.35, 1]); glow(sgn * 17.6, 16.0, 4, [1, 0.7, 0.35, 1])
# ---- story (claude/prison-and-asteroid.md): freed from the Pit -> try to go home -> the masked raiders attack the Colosseum -> portal to the asteroid base
RAID = [.5, .45, .8, 1]
def raider(key, name, sprite, x, z, show, tint, lines, lvl, pool, h=2.4):
    NP.append(dict(id=key, name=name, title="Hostile", sprite=sprite, x=x, z=z, h=h, tint=tint, hideIf=key, showIf=show, reach=5.0,
                   actions=[dict(type="say", who=name, text=t) for t in lines] + [dict(type="battle", key=key, boss="", level_rel=lvl, pool=pool)]))
raider("st_b1", "Masked Raider", "Draven", -5, 9, "st_siege", RAID, ["Found you. The portal is not done with you, islander."], [0, 2], ["dark_cultist", "cursed_knight", "bandit_rogue"])
raider("st_b2", "Masked Raider", "Kael", 5, 9, "st_b1", RAID, ["Cut down one of us and two more take his place."], [0, 2], ["dark_cultist", "cursed_knight", "bandit_rogue"])
raider("st_b3", "Hooded Leader", "Rook", 0, 6.5, "st_b2", [.55, .3, .9, 1], ["You grew strong in the Pit. Good. The Arena sings louder for it.", "Come. See what we serve."], [1, 3], ["cursed_knight", "dark_cultist", "abyssal_horror"], 2.6)
GATE_SAY = lambda who, text, **c: dict(type="say", who=who, text=text, **c)
EV = [dict(id="exit_outside", name="Colosseum exit", x=0, z=15.6, w=10, d=1.6, trigger="touch", once=False, actions=[
        GATE_SAY("", "Smoke and masked raiders fill the gate. You cannot leave until the Colosseum is defended!", **{"if": "st_siege", "unless": "st_space"}),
        GATE_SAY("", "You step toward the gate and a horn sounds from the stands. Smoke pours across the sands. Raiders in violet masks storm the walls!", **{"if": "st_free", "unless": "st_siege"}),
        GATE_SAY("Gate Warden", "The same masks that burned the island! To arms, hero. This is your home too now.", **{"if": "st_free", "unless": "st_siege"}),
        dict(type="flag", key="st_siege", **{"if": "st_free", "unless": "st_siege"}),
        dict(type="warp", scene="outside", x=0, z=-9.5, unless="st_free")])]
AUTO = [
 dict(**{"if": "st_b3", "unless": "st_space"}, actions=[
     GATE_SAY("", "The Hooded Leader staggers back, laughing under the mask."),
     GATE_SAY("Hooded Leader", "Did you think the Arena was the end of it? You are only the key. The door has been waiting for you."),
     GATE_SAY("", "The air above the sands tears like cloth. A whirl of violet light drags at your feet, colder than before, and the Colosseum falls away..."),
     dict(type="flash"), dict(type="flag", key="st_space"), dict(type="warp", scene="asteroid", x=0, z=6)]),
 dict(**{"if": "st_free", "unless": "st_arrived"}, actions=[
     GATE_SAY("", "Sunlight hits you like a wave. The sand is hot, the stands are roaring, and for the first time in a long while nobody holds your chain."),
     GATE_SAY("Gate Warden", "Free, are you? The Pit does not often give back what it takes."),
     GATE_SAY("Gate Warden", "The Colosseum is yours to walk. Heal up, gear up, fight if you like. When you are ready to go home, the main gate is to the south."),
     dict(type="flag", key="st_arrived")]),
]
LYR = "/assets/Backgrounds/layers/"
d = dict(name="Olympus Colosseum", kit="", tile=4, pieces=P, colliders=COL, npcs=NP, decals=DEC, events=EV, story=True, autorun=AUTO,
         bounds=dict(minX=-18.2, maxX=18.2, minZ=-7.4, maxZ=16.4), spawn=dict(x=0, z=11), playerHeight=2.4,
         sky=dict(type="layers", base=dict(type="gradient", stops=[[0, "#3f86d6"], [.4, "#7fb6ec"], [.75, "#cfe6f8"], [1, "#fff6e0"]]),
                  layers=[dict(url=LYR + "clouds_wisps.webp", y=.18, height=.22, drift=.007, alpha=.9, tint=[1, 1, 1]),
                          dict(url=LYR + "clouds_puffy.webp", y=.34, height=.32, drift=.004, alpha=1, tint=[1, 1, 1], parallax=.2),
                          dict(url=LYR + "ridges_far.webp", y=.88, height=.3, parallax=.15, tint=[.78, .86, .98])]),
         light=dict(dir=[-0.4, -1, -0.35], color=[0.95, 0.9, 0.8], ambient=[0.62, 0.63, 0.7]), fog=dict(color=[0.78, 0.88, 0.97], near=80, far=230))
import story_pit; story_pit.apply_olympus(d)         # Sera in the infirmary, exit gate waits for her (Oct 6)
os.makedirs(OUT, exist_ok=True); json.dump(d, open(os.path.join(OUT, "olympus.json"), "w"), separators=(",", ":"))
print("pieces", len(P), "colliders", len(COL))

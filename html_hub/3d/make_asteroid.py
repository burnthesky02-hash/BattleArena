"""Builds html_hub/3d/asteroid.json: "Outpost Kestrel", the asteroid base the hero is dragged to after the Colosseum attack (claude/prison-and-asteroid.md).
Pieces come from the Asteroid_base kit (Assets/3D/Asteroid, textured by convert_asteroid.py). The base stands on four 60x40 deck plates over open space;
walls, buildings and the ship are solid, the landing pad in the middle is where the portal drops you. Pieces are [model, x, z, rotY, y, scale].
Run:  python make_asteroid.py [outdir]    Re-running overwrites hand edits made in /builder3d."""
import json, math, os, random, sys
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
A = "/assets/3D/Asteroid/"
P, COL, DEC, NP, EV = [], [], [], [], []
rnd = random.Random(11)
def put(n, x, z, rot=0, y=0, sc=1): P.append([A + n, round(x, 3), round(z, 3), rot, y, sc])
def block(x, z, w, d): COL.append({"x": round(x, 3), "z": round(z, 3), "w": round(w, 3), "d": round(d, 3)})
def glow(x, z, r, c): DEC.append(dict(type="glow", x=x, z=z, r=r, color=c))
def building(n, x, z, w, d, rot=0, sc=1, shrink=0.94):          # a solid building: model + a collider of its footprint
    put(n, x, z, rot, 0, sc); w2, d2 = (d, w) if rot % 180 else (w, d); block(x, z, w2 * sc * shrink, d2 * sc * shrink)

# ---- the base floor: four deck plates (their legs hang into the void), the landing pad on top
DECK_Y = -22.795
for x in (-30, 30):
    for z in (-20, 20): put("SM_support_module_large", x, z, 0, DECK_Y, 1)
PAD = (0, 10)
put("SM_landing_pad", PAD[0], PAD[1], 0, 0.02, 1)

# ---- big buildings round the edge (solid)
building("SM_module_building_02", 0, -26, 24.9, 24.9)                         # command dome
building("SM_module_building_01", -44, -24, 30.8, 30.8)                       # tall tower (west)
building("SM_module_building_03", 44, -24, 30.8, 30.8)                        # tall tower (east)
building("SM_house_01", -40, 10, 28.0, 18.2)                                  # barracks
building("SM_house_02", -36, 29, 27.3, 18.9)                                  # mess hall
building("SM_house_03", 24, 31, 15.0, 15.8)                                   # workshop
building("SM_house_small", 46, 31, 20.5, 15.8)                                # clinic
put("SM_ship_landed", 38, 4, 0, 0, 1); block(38, 4, 21.0, 18.0)               # the ship that brought the survivors
# antennas at the pad edge and on the buildings
for x in (-22, 22): put("SM_antenna_02", x, -13.5, 0, 0, 1.3); block(x, -13.5, 1.6, 1.6)
put("SM_antenna_03", 0, -38, 0, 0, 1.2)
# ---- supplies near the ship, a mess table by the hall, pipes along the dome
for i, (n, x, z, r) in enumerate((("SM_crate_01", 24.0, 12.5, 10), ("SM_crate_03", 25.4, 14.0, 35), ("SM_crate_05", 23.0, 15.0, 80), ("SM_crate_01", 26.0, 10.8, 0), ("SM_crate_03", 22.5, 11.2, 60))):
    put(n, x, z, r, 0, 2.2); block(x, z, 1.7, 1.7)
put("SM_large_container", 31, 17.6, 0, 0, 1.2); block(31, 17.6, 7.0, 5.0)
put("SM_table_02", -21.5, 22.0, 0, 0, 1.2); block(-21.5, 22.0, 4.9, 3.7); put("SM_chair_group", -21.5, 24.6, 0, 0, 1.9); put("SM_chair", -24.6, 22.0, 90, 0, 1.9); put("SM_chair", -18.4, 22.0, 270, 0, 1.9)
put("SM_table_01", 16.0, 26.6, 0, 0, 1.4); block(16.0, 26.6, 3.7, 1.9); put("SM_chair", 16.0, 28.4, 180, 0, 1.9)
for x in (-6, 6): put("SM_pipe_03", x, -14.4, 0, 0, 1.3); block(x, -14.4, 1.6, 1.8)
put("SM_pipe_01", -10, -13.8, 0, 0, 1.3); put("SM_pipe_02", 10, -13.8, 0, 0, 1.3)
put("SM_door_01", 0, -14.2, 0, 0, 0.8)
# ---- boulders of the asteroid itself, floating round the deck
for k in range(22):
    a = rnd.random() * math.tau; rad = 70 + rnd.random() * 50
    put(rnd.choice(("SM_rock_01", "SM_rock_02")), math.cos(a) * rad * 1.15, math.sin(a) * rad * 0.8, rnd.randint(0, 359), -26 + rnd.random() * 14, 6 + rnd.random() * 9)
for x, z in ((-52, -5), (52, -12), (50, 18), (-54, 38)): put("SM_ground_rocks", x, z, rnd.randint(0, 359), 0, 4 + rnd.random() * 2)
# ---- lights
cy, bl = [.4, .85, 1, 1], [.35, .6, 1, 1]
DEC += [dict(type="glyph", x=PAD[0], z=PAD[1] - 2, r=4.2, color=[.6, .4, 1, 1], spin=18), dict(type="glow", x=PAD[0], z=PAD[1] - 2, r=10, color=[.5, .35, 1, .7])]
for x, z in ((-12, 18), (12, 18), (0, -9), (-18, 4), (24, 13), (0, 30)): glow(x, z, 5, cy)
for x in (-22, 22): glow(x, -13.5, 6, [1, .3, .3, .9])
glow(0, -13, 8, [1, .85, .55, 1]); glow(38, 15, 6, bl); glow(-38, 20, 6, [1, .8, .5, 1])

# ---- people (hub services: no ladder or rank gate out here; the Colosseum is gone)
def npc(**kw): kw.setdefault("h", 2.4); NP.append(kw)
npc(id="rhea", name="Captain Rhea", title="Outpost Kestrel", sprite="Yulia", x=0, z=-9.6, tint=[.8, 1, 1.2, 1], reach=5.0, actions=[
    dict(type="say", who="Captain Rhea", text="Easy now. You came through the rift, so you are the one the masked raiders wanted. Welcome to Outpost Kestrel, far from any sea.", unless="st_met"),
    dict(type="say", who="Captain Rhea", text="They have been pulling fighters out of the world and dropping them on rocks like this one. We think the portal at the Colosseum was only the first door.", unless="st_met"),
    dict(type="say", who="Captain Rhea", text="We have a scholar here who has been studying the rift since she was dragged through it. Lyra. She is usually in the mess hall, west of the pad, buried in notes. Go and talk to her.", unless="st_met"),
    dict(type="flag", key="st_met", unless="st_met"),
    dict(type="say", who="Captain Rhea", text="Lyra is in the mess hall, west of the landing pad. She knows more about the rift than all of my techs together.", **{"if": "st_met", "unless": "st_lyra"}),
    dict(type="say", who="Captain Rhea", text="Lyra says there is a vault under the base, and that it is the reason the rift keeps tearing open. I had the old hatch west of the pad unsealed for you. Take Lyra, take care, and come back alive.", **{"if": "st_lyra", "unless": "vt_boss"}),
    dict(type="say", who="Captain Rhea", text="The Shard stopped singing the moment the Warden fell. Good work. The rift console has a new coordinate on it now. We will find out where it points. For now, rest.", **{"if": "vt_boss"})])
npc(id="battle", name="Sergeant Kade", title="Drill Sergeant", sprite="Draven", x=-13, z=18.5, line="Rift or no rift, soldiers stay sharp. Want a bout in the practice ring?", tint=[.8, .95, 1.15, 1], action="battle")
npc(id="heroes", name="Ysol", title="Technician", sprite="Lyra", x=13, z=18.5, line="I tune gear and drill skills. Bring me your fighters.", tint=[.8, 1.05, 1.1, 1], action="heroes")
npc(id="summon", name="Oro", title="Rift Seer", sprite="Sera", x=-19, z=3.5, line="The rift leaks. Sometimes things climb out of it and want to fight for you.", tint=[.85, .9, 1.25, 1], action="summon", reach=5.0)
npc(id="shop", name="Quartermaster Pike", title="Supplies", sprite="Rook", x=22.5, z=8.2, line="Everything we salvaged, for everything you earned. Browse.", tint=[1.1, .95, .8, 1], action="shop")
npc(id="save", name="Archivist", title="Records", sprite="Kael", x=0, z=29.5, tint=[.75, .88, 1.15, 1], action="save_and_quit")
npc(id="lyra", name="Lyra", title="Rift Scholar", sprite="Lyra", x=-17.0, z=19.8, tint=[1, 1, 1.1, 1], hideIf="st_lyra", reach=5.0, actions=[
    dict(type="say", who="Lyra", text="Another one who fell out of the sky? ...Oh. You are the one the Captain mentioned. You came through the Colosseum portal. Good. I have a map of what is under this base, and I need someone who can fight.", **{"if": "st_met"}),
    dict(type="say", who="Lyra", text="I was a scholar at a library very far from here, until a door opened in the reading room and the floor stopped being the floor. Since then I have been tracing where the rift gets its strength.", **{"if": "st_met"}),
    dict(type="say", who="Lyra", text="It points down. There is a vault below Kestrel, and something called a Shard in it that is pulling doors open across the world. Wherever you are going next, I would like to come with you.", **{"if": "st_met"}),
    dict(type="recruit", name="Lyra", **{"if": "st_met"}),
    dict(type="flag", key="st_lyra", **{"if": "st_met"}),
    dict(type="say", who="Lyra", text="Lyra joins your party. The hatch to the vault is west of the landing pad. Equip her at Ysol's bench first; I have no armour to my name.", **{"if": "st_met"}),
    dict(type="say", who="Lyra", text="The Captain wants to see you first. She is by the command dome, north of the pad.", unless="st_met")])
EV += [dict(id="rift_console", name="Rift console", x=PAD[0], z=PAD[1] + 7.5, w=4.0, d=3.0, trigger="talk", prompt="Read the console",
            actions=[dict(type="say", who="Rift Console", text="COORDINATES CYCLING: PARADISE ISLAND... OLYMPUS COLOSSEUM... A third entry flickers and will not resolve. THE RIFT IS SEALED. The way home is not open yet.", unless="vt_boss"),
                     dict(type="say", who="Rift Console", text="COORDINATES CYCLING: PARADISE ISLAND... OLYMPUS COLOSSEUM... A third entry has resolved: UNKNOWN. SIGNAL STRENGTH RISING. The way home is still sealed, but something on the other end has noticed us.", **{"if": "vt_boss"})])]
put("SM_table_01", PAD[0], PAD[1] + 9.5, 0, 0, 1.3); block(PAD[0], PAD[1] + 9.5, 3.4, 1.8)
EV += [dict(id="ship_note", name="Landed ship", x=38, z=14.4, w=8.0, d=3.0, trigger="talk", prompt="Look at the ship",
            actions=[dict(type="say", who="", text="Scorched hull plates and a cracked canopy. Someone brought this ship in the hard way.")])]

# ---- the vault hatch: a heavy door in the deck west of the pad (leads to vault.json)
HATCH = (-27, -3)
put("SM_door_module", HATCH[0], HATCH[1], 90, 0, 1.0); block(HATCH[0] - 1.2, HATCH[1], 2.4, 7.0)
glow(HATCH[0] + 2.5, HATCH[1], 6, [.7, .42, 1, .9])
EV += [dict(id="vault_hatch", name="Vault hatch", x=HATCH[0] + 3.0, z=HATCH[1], w=4.0, d=5.0, trigger="talk", prompt="Open the hatch",
            actions=[dict(type="say", who="", text="A heavy hatch, scorched and sealed. Something below it hums.", unless="st_lyra"),
                     dict(type="say", who="", text="The hatch grinds open on a staircase that spirals down into violet light. The air tastes of metal and old storms.", **{"if": "st_lyra"}),
                     dict(type="warp", scene="vault", x=0, z=10, **{"if": "st_lyra"})])]
# ---- the rift gate (chapter 4): opens once the Vault Warden is down; leads to reach.json (the Shattered Reach)
GATE = (14, 23)
DEC.append(dict(type="glow", x=GATE[0], z=GATE[1], r=7, color=[1, .35, .5, .9], showIf="vt_boss"))
EV += [dict(id="rift_gate", name="Rift gate", x=GATE[0], z=GATE[1], w=5.0, d=4.0, trigger="talk", prompt="Step into the rift",
            actions=[dict(type="say", who="", text="The air above the pad is quiet. Nothing answers the console yet.", unless="vt_boss"),
                     dict(type="say", who="Captain Rhea", text="The new coordinate resolved overnight. The rift has torn open past the pad: a chain of broken ruins hanging in nothing. Whatever is calling, it is on the far side. Come back alive.", **{"if": "vt_boss", "unless": "rc_arrive"}),
                     dict(type="say", who="", text="A wound in the sky hangs open, bleeding violet light. You step through.", **{"if": "vt_boss"}),
                     dict(type="warp", scene="reach", x=0, z=8, **{"if": "vt_boss"})])]
AUTO = [dict(unless="st_landed", actions=[
    dict(type="say", who="", text="Cold, thin air and the hum of machinery. You stand on a landing pad, stars wheeling overhead. A huge ringed planet hangs in the sky."),
    dict(type="say", who="", text="You are not on the island. You are not in the Colosseum. You are not, by the look of it, even in the same world."),
    dict(type="say", who="", text="A woman in a flight jacket is walking toward you across the pad. Speak to Captain Rhea."),
    dict(type="flag", key="st_landed")])]
LYR = "/assets/Backgrounds/layers/"
d = dict(name="Outpost Kestrel", kit="", tile=4, pieces=P, colliders=COL, npcs=NP, events=EV, decals=DEC, story=True, autorun=AUTO, music=dict(url="/assets/Music/mp3/02. Lively City.mp3"),
         bounds=dict(minX=-56, maxX=56, minZ=-34, maxZ=36), spawn=dict(x=PAD[0], z=PAD[1] - 2), playerHeight=2.4,
         sky=dict(type="layers", base=dict(type="gradient", stops=[[0, "#010208"], [.5, "#060b1f"], [1, "#171335"]]),
                  layers=[dict(url=LYR + "stars.webp", y=.30, height=.66, parallax=.04, alpha=1, tint=[1, 1, 1.1]),
                          dict(url=LYR + "planet.webp", y=.26, height=.78, parallax=.06, alpha=1, tile=False, tint=[1, 1, 1]),
                          dict(url=LYR + "stars.webp", y=.55, height=.5, parallax=.12, alpha=.55, tint=[.8, .9, 1.2], drift=.002)]),
         light=dict(dir=[-0.55, -1, -0.3], color=[0.8, 0.88, 1.0], ambient=[0.3, 0.34, 0.5]), fog=dict(color=[0.01, 0.015, 0.045], near=120, far=300))
os.makedirs(OUT, exist_ok=True); json.dump(d, open(os.path.join(OUT, "asteroid.json"), "w"), separators=(",", ":"))
print("pieces", len(P), "colliders", len(COL), "npcs", len(NP), "events", len(EV))

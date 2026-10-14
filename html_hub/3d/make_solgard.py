"""Builds html_hub/3d/solgard.json: "Solgard, the Sunwall City", Veyra Chapter C (claude/veyra-solgard-oct-13.md).
Continues make_ashroad.py: the party goes down the Underdrain hatch and comes up in Veyra's last city.
Layout (x east, z south, the camera looks north):
  1. The Underdrain (z 56 .. 22): a stone drain tunnel, the lamplighter Odo (who keeps the code), the way back up to the Road of Ash.
  2. The Bright Ring (z 8 .. -78): the warm city under the Sunwall, a fountain plaza, houses, market, notice board, an inn, and the palace steps (a speech cutscene on entering the plaza).
  3. The Works (z -98 .. -170): the Overseer's gate, the courtyard and bunks of the kindlers, Tomas, a Watcher plate and the Great Valve (the door to the Emberheart, Chapter D).
The Spire choice from the Road of Ash (ar_spire_off / ar_spire_left) changes the Ring, Odo's letter, the Works, and Tomas.
Flags: sg_arrive sg_speech (the address seen) sg_overseer (Overseer Cathal beaten) sg_tomas sg_tomas2 (the choice made, valve key) sg_end (descended) sc1..sc4 (chests); the valve now warps to heart.json (Chapter D, make_heart.py)
Run:  python make_solgard.py [outdir]   (needs kenhouse.py next to it; re-running overwrites hand edits made in /builder3d)"""
import json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kenhouse

KEN = kenhouse.KEN
GC, ST, PA, DG, GEN = ("/assets/3D/GodCity/", "/assets/3D/Stylized/", "/assets/3D/Paradise/", "/assets/3D/Dungeon/", "/assets/3D/Generated/")
S = kenhouse.S
MUSIC = "/assets/Music/mp3/"
rng = random.Random(5521)
T = kenhouse.Town(PA)
put, ken, block = T.put, T.ken, T.block
SAY = lambda who, text, **k: dict(type="say", who=who, text=text, **k)
ACT = lambda _ty, **k: dict(type=_ty, **k)
NPCS, EVENTS = [], []
BOUNDS = dict(minX=-44, maxX=44, minZ=-176, maxZ=62)
GOLD = [1.0, 0.82, 0.5]


def glow(x, z, r, c, show=None, hide=None):
    d = dict(type="glow", x=round(x, 2), z=round(z, 2), r=r, color=c)
    if show: d["showIf"] = show
    if hide: d["hideIf"] = hide
    T.DEC.append(d)


def glyph(x, z, r, c, spin=0, show=None, hide=None):
    d = dict(type="glyph", x=round(x, 2), z=round(z, 2), r=r, spin=spin, color=c)
    if show: d["showIf"] = show
    if hide: d["hideIf"] = hide
    T.DEC.append(d)


def npc(id, name, title, sprite, x, z, actions=None, action=None, show=None, hide=None, h=2.4, reach=4.6, tint=None):
    n = dict(id=id, name=name, title=title, sprite=sprite, x=x, z=z, h=h, reach=reach)
    if actions: n["actions"] = actions
    if action: n["action"] = action
    if show: n["showIf"] = show
    if hide: n["hideIf"] = hide
    if tint: n["tint"] = tint
    NPCS.append(n)


def event(id, name, x, z, actions, prompt="Examine", w=3.0, d=3.0, show=None, hide=None, trigger="talk", once=False):
    e = dict(id=id, name=name, x=x, z=z, w=w, d=d, trigger=trigger, prompt=prompt, actions=actions)
    if show: e["showIf"] = show
    if hide: e["hideIf"] = hide
    if once: e["once"] = True
    EVENTS.append(e)


def chest(id, x, z, loot):
    put(GEN + "SM_TreasureChest", x, z, rng.randint(0, 359), 0, 1.0); block(x, z, 1.4, 1.4)
    event(id, "Treasure chest", x, z, [dict(type="flag", key=id), dict(type="chest", loot=loot, text="You prise the chest open and find")], "Open the chest", 3.4, 3.4, hide=id)


def lamp(x, z, warm=(1, 0.8, 0.5, 0.5), r=7):
    put(ST + "SM_Stylized_Lamp_C", x, z, 0, 0, 1.1); block(x, z, 0.6, 0.6); glow(x, z, r, list(warm))


# ------------------------------------------------------------------ ground
for gx in range(-3, 3):
    for gz in range(-9, 4):
        put(GC + "SM_ground_20x20", gx * 20 + 10, gz * 20 + 10, 0, -0.5, 1)
for i in range(110):                                   # the rock of the plateau closes the city on both sides
    z = rng.uniform(-184, 70)
    put(ST + "SM_Cliff_0%d" % rng.randint(1, 2), rng.choice((-1, 1)) * rng.uniform(47, 56), z, rng.randint(0, 359), -0.2, rng.uniform(1.3, 2.4))

# ------------------------------------------------------------------ 1. the Underdrain (z 56 .. 22)
UW = 13.0                                              # half width of the tunnel
nz = int((56 - 22) / S) + 1
for j in range(nz + 1):
    z = 22 + j * S
    for sx in (-UW, UW):
        ken("wall-fortified", sx, z, 90, 0, S); block(sx, z, 1.0, S)
for i in range(int(2 * UW / S) + 1):                   # the south end wall
    x = -UW + i * S
    ken("wall-fortified", x, 58.5, 0, 0, S); block(x, 58.5, S, 1.0)
for (x, z) in ((-7, 50), (7, 50), (-7, 30), (7, 30)):
    put(DG + "SM_dg_brazier", x, z); put(DG + "SM_dg_flame", x, z, 0, 1.55, 1.0); block(x, z, 1.1, 1.1); glow(x, z, 8, [1, 0.6, 0.3, 0.45])
put(DG + "SM_dg_dais", 0, 54.5, 0, 0, 0.8); glyph(0, 54.5, 3.0, [1, 0.75, 0.4, 0.9], 25)
for (x, z) in ((-10, 44), (9.5, 36), (-9, 28)):
    put(ST + "SM_Stylized_Box_var1", x, z, rng.randint(0, 359), 0, 1.3); block(x, z, 1.3, 1.3)
put(ST + "_Stylized_Barrel", 10.0, 47.0, 0, 0, 1.3)
put(ST + "SM_Stylized_Table_A", -9.0, 38.0, 0, 0, 1.1); block(-9.0, 38.0, 2.6, 1.3)
chest("sc1", 10.5, 28.0, dict(gold=2000, shards=30, items={"potion": 4, "ether": 2}))
# the drain stair: the tunnel narrows and climbs into the light
put(DG + "SM_dg_dais", 0, 16.0, 0, 0, 1.0); put(DG + "SM_dg_dais", 0, 10.0, 0, 0, 1.2)
for sx in (-7.5, 7.5):
    for z in (19.0, 13.0):
        ken("wall-fortified", sx, z, 90, 0, S); block(sx, z, 1.0, S)
glow(0, 8, 14, [1.0, 0.92, 0.7, 0.5])

event("sg_up", "The hatch", 0.0, 56.8, [
    SAY("", "Iron rungs go up into the dark, and past them, faintly, the smell of the Road of Ash."),
    dict(type="choice", who="Kenji", text="Climb back up to the Road of Ash?", options=[
        dict(label="Go back up", actions=[ACT("fade", to="black", t=1.0), ACT("warp", scene="ashroad", x=25.0, z=-141.8, fresh=True)]),
        dict(label="Stay in Solgard", actions=[ACT("end")])])],
    "Look up the hatch", 5.0, 2.4)

npc("odo", "Lamplighter Odo", "Keeper of the Drain", "Elder", 0.0, 40.0, tint=[1.0, 0.95, 0.8, 1], reach=5.0, actions=[
    SAY("Odo", "Three, then two. Nine years I have answered that knock and in nine years it has been a smuggler, a stray child and a rat. A rat that knew the code. I have always wondered about the rat.", **{"unless": "sg_odo"}),
    SAY("Reya", "Odo. It's Reya. Hesk's bridge. Tomas's sister.", **{"unless": "sg_odo"}),
    SAY("Odo", "Little knife. You got tall. And you brought company. Are they what the courier whispered about, the ones who cut the Spire's seam?", **{"if": "ar_spire_off", "unless": "sg_odo"}),
    SAY("Odo", "The Wall dimmed for an hour the night your Spire died. Half the Ring went to the windows to see. The Queen came out on the steps and said nothing at all. Then the Works doubled the shifts and the Wall came back up.", **{"if": "ar_spire_off", "unless": "sg_odo"}),
    SAY("Odo", "I'm not blaming you. I'm telling you what the Ring will not. The Works pays for every honest thing a hero does. That is its whole design.", **{"if": "ar_spire_off", "unless": "sg_odo"}),
    SAY("Odo", "A courier named Dov came through before you. He left a letter. He said it was from the Ford, for the strangers who left the Spire humming.", **{"if": "ar_spire_left,!ar_spire_off,!sg_odo"}),
    SAY("Odo", "I read it. I should not have. Here. Better it's in your hands than mine.", **{"if": "ar_spire_left,!ar_spire_off,!sg_odo"}),
    SAY("", "The paper is thin, written in Elder Wen's careful hand. 'Seven of ours did not see spring: two old, a mason, a girl of four, a man with a bad chest, and Nessa's youngest, who was nine days old. I do not write this to blame you. I write it because it has a number, and a number should be known by the people who are warm because of it.'", **{"if": "ar_spire_left,!ar_spire_off,!sg_odo"}),
    SAY("Reya", "...Kenji.", **{"if": "ar_spire_left,!ar_spire_off,!sg_odo"}),
    SAY("Kenji", "I read it. I'll carry it. Don't tell me it was the right choice, and don't tell me it wasn't. Not yet.", **{"if": "ar_spire_left,!ar_spire_off,!sg_odo"}),
    SAY("Odo", "Enough. Listen. Tomas is alive. They call him the Steady, because he is the shift lead of the Third Ring Works and he does not break. If you want to see him, you go up the stair, through the Ring, east around the palace, and you ask the Overseer very politely to let you in. He will say no. Ask again.", **{"unless": "sg_odo"}),
    SAY("Odo", "And mind your hand, stranger. The gold on it is a risky thing to wear in the Ring this month.", **{"unless": "sg_odo"}),
    ACT("flag", key="sg_odo", **{"unless": "sg_odo"}),
    SAY("Odo", "The stair is behind me. Go gently. The Ring is warm and the people in it are kind, and that is the hardest part.", **{"if": "sg_odo"})])

# ------------------------------------------------------------------ 2. the Bright Ring (z 8 .. -78)
FZ = -30.0
put(ST + "SM_Stylized_Fountain", 0, FZ, 0, 0, 1.6); block(0, FZ, 6.6, 6.6); glow(0, FZ, 12, [1, 0.88, 0.6, 0.55])
for (x, z, r) in ((-27, -8, 90), (-31, -26, 90), (-27, -46, 90), (-31, -64, 90), (27, -8, 270), (31, -26, 270), (27, -46, 270)):
    T.house(x, z, r, [(0, 0, 3, 2)], wall="stone", col="cream", roof="red")
    glow(x, z, 9, [1, 0.8, 0.5, 0.5])
for (x, z, r) in ((-14, -14, 90), (14, -14, 270), (-14, -62, 90), (14, -62, 270)):
    put(GC + "SM_market_tent_0%d" % (1 + int(abs(x) + abs(z)) % 3), x, z, r, 0, 1.0); block(x, z, 4.6, 8.0)
for z in range(0, -78, -13):
    lamp(-9.5, z - 3, r=9); lamp(9.5, z - 3, r=9)
for k in range(6):
    a = k * math.tau / 6
    put(ST + "SM_Stylized_Bench", 7.8 * math.cos(a), FZ + 7.8 * math.sin(a), math.degrees(a) + 90, 0, 1.0)
glow(0, -20, 28, [1.0, 0.9, 0.65, 0.35]); glow(0, -50, 28, [1.0, 0.9, 0.65, 0.35])
chest("sc2", -39.0, -38.0, dict(gold=2300, shards=34, items={"potion": 4, "ether": 3}))
chest("sc3", 40.0, -62.0, dict(gold=2600, shards=36, items={"antidote": 3, "ether": 2}))
# the palace wall (north of the Ring) with the barred great door; the gap on the east is the Works road
for i in range(int((80.0) / S) + 1):
    x = -44 + i * S
    if x > 28: break
    ken("wall-fortified", x, -80.0, 0, 0, S); block(x, -80.0, S, 1.0)
for sx in (-30, 0, 30):
    ken("tower-base", sx, -80.0, 0, 0, S * 1.5); ken("tower", sx, -80.0, 0, S * 1.5, S * 1.5); ken("tower-top", sx, -80.0, 0, S * 3.0, S * 1.5); block(sx, -80.0, 4.4, 4.4)
put(DG + "SM_dg_dais", 0, -74.5, 0, 0, 1.0)
for fxp in (-6.0, 6.0):
    put(ST + "SM_Stylized_Flag_Var1", fxp, -76.0, 0, 0, 2.8); block(fxp, -76.0, 0.5, 0.5)
glow(0, -84, 40, [1.0, 0.95, 0.75, 0.55])
# the Sunwall: golden glow rings behind the palace
glow(0, -100, 60, [1.0, 0.92, 0.7, 0.5])

# notice board and the consequences of the Spire choice
put(ST + "SM_Stylized_WantedBoard", -8.0, -9.0, 0, 0, 1.2); block(-8.0, -9.0, 2.0, 1.0)
event("sg_board", "Notice board", -8.0, -11.2, [
    SAY("", "THE SUNWALL PROVIDES. A neat poster, three years old, listing the blessings of the Third Ring: warmth, bread, the Works' thanks."),
    SAY("", "Pinned over it, fresh and crooked: WANTED, THE SPIRE-BREAKER. Two thousand crowns. A man with a gold mark on his right hand. He severed the Harrow's Ford tithe and brought the Wall down for an hour. The Queen does not forgive attacks on the Wall.", **{"if": "ar_spire_off"}),
    SAY("Reya", "Put your glove on, Kenji.", **{"if": "ar_spire_off"}),
    SAY("Kenji", "Wasn't it right to cut it?", **{"if": "ar_spire_off"}),
    SAY("Reya", "It was kind. It was kind to Ford. The Ring doesn't care which one of those two words matters.", **{"if": "ar_spire_off"}),
    SAY("", "Under it, the ration table: BREAD, ONE-HALF LOAF PER PERSON. WARMTH LIMITS IN EFFECT.", **{"if": "ar_spire_off"}),
    SAY("", "Under it, the ration table: BREAD, ONE LOAF PER PERSON. The Wall is bright, and the board shows no sign that anywhere is cold.", **{"if": "ar_spire_left,!ar_spire_off"})],
    "Read the notices", 3.6, 2.6)
event("sg_inn", "The Sun and Hearth", -19.5, -44.0, [
    SAY("", "A broad stone house with a hearth that never goes out. The innkeeper nods you in without asking, and the beds smell of clean linen. Nobody here has ever been cold."),
    dict(type="rest")], "Rest at the inn", 4.0, 3.0)

npc("baker", "Baker Mira", "Ring Baker", "Farmer", -17.0, -20.0, actions=[
    SAY("Baker Mira", "Warm bread! Warm as the Wall, still! Take two... oh. Half-loaves, this week. Take one. The Works says the Ring must tighten its belt a little.", **{"if": "ar_spire_off"}),
    SAY("Baker Mira", "Warm bread, warm as the Wall! Two loaves, friends, the Queen's grain came in plenty this year.", **{"if": "ar_spire_left,!ar_spire_off"}),
    SAY("Baker Mira", "You're not from the Ring. Mother's light, nobody is, any more. Folk used to come to the Sunwall to be safe. Now folk come to be fed, and I think that's all the same thing to the Queen.")])
npc("child1", "Ring child", "Citizen", "Townee", 3.0, -22.0, actions=[
    SAY("Ring child", "I'm never cold! Never ever. Mama says the Wall keeps us. I'm going to be a lamplighter when I grow up.", **{"unless": "ar_spire_off"}),
    SAY("Ring child", "The Wall went out for a whole hour once. Mama said it was a test. I'm not scared of the dark. I'm scared of the people who said so.", **{"if": "ar_spire_off"})])
npc("guard1", "Ring Guard", "Royal Guard", "Warden", 8.0, -4.0, tint=[1.15, 0.8, 0.7, 1], actions=[
    SAY("Ring Guard", "Move along. Nothing to see. Papers? ...no? You're with the courier? Fine. Keep the glove on.", **{"if": "ar_spire_off"}),
    SAY("Ring Guard", "Welcome to Solgard. The warmest place in Veyra. Enjoy it, and don't ask about the Works.", **{"unless": "ar_spire_off"})])
npc("elder_ring", "Elder Brienne", "Ring Elder", "Elder", -22.0, -56.0, actions=[
    SAY("Elder Brienne", "I was a child in the cold before the Wall. I remember my mother wrapping me in her shawl and her shawl not being enough. I would not send a child to the cold again.", ),
    SAY("Elder Brienne", "And I have never once asked where the heat comes from. Do you know I knew? Every one of us knew. We just stopped saying it aloud, because saying it aloud is the beginning of having to decide.")])
npc("postmaster", "Mailwarden Fenn", "Postmaster", "Shopkeeper", 20.0, -34.0, actions=[
    SAY("Mailwarden Fenn", "Letters from the provinces? There are none. The Crown stopped delivering the outer villages six years ago. I still sort the pigeonholes. Somebody has to believe it will start again.")])

# the Queen's address (touch event on entering the plaza)
npc("maelis", "Queen Maelis", "The Sun Queen", "Mayor", 0.0, -77.2, tint=[1.25, 1.05, 0.7, 1], h=3.0, hide="sg_speech", reach=1.0)
npc("counsellor", "The Counsellor", "No name on the record", "Rook", 3.6, -77.2, tint=[0.22, 0.22, 0.35, 1], h=3.3, hide="sg_speech", reach=1.0)
SPEECH = [
    ACT("cine", on=True),
    ACT("walk", who="player", x=0.0, z=-12.0, speed=4),
    ACT("cam", x=0, z=-62, yaw=0, pitch=24, dist=34, t=2.4),
    SAY("", "A bell, once. The hum in the stones stops. Everyone in the plaza turns north, and on the palace steps, in a gown the colour of banked embers, a woman steps into the light."),
    SAY("Queen Maelis", "People of Solgard. Last night the Wall burned for its seven-thousand-and-fortieth night. In all that time it has never gone out for longer than an hour, and an hour was a cruelty to this city that I have not forgiven myself for."),
    SAY("Queen Maelis", "I will not tell you that the heat of this Wall is clean. I will tell you the number. This dawn the Works recorded forty-one thousand and twelve in its care. I read every name. I will not tell you that is just. I will tell you it is why you are warm."),
    SAY("Reya", "Forty-one thousand and twelve. That's Hesk's number. It's the same number."),
    SAY("Lyra", "She's reading the same ledger. Mind your face."),
    SAY("", "Beside the Queen, one pace back, a tall figure in a dark coat with a hood drawn low. It does not move. It has not moved once. No one in the plaza looks at it, as though they cannot."),
    SAY("Queen Maelis", "Count the saved, my people. Not the lost. It is the only arithmetic that has kept this city alive."),
    ACT("shake", t=0.6, amp=0.15),
    SAY("", "The hooded head turns, slowly, past the Queen, down across the plaza. It stops on Kenji. On his right hand. The gold line under the skin flares like a struck match."),
    SAY("Kenji", "He's looking at the mark."),
    SAY("Miya", "Everyone else is looking at the Queen. He is the only one looking at us."),
    SAY("", "The hooded figure inclines its head, once, politely, the way you would to an old acquaintance. Then the Queen raises her hand and the bell tolls again, and the plaza breathes out, and the steps are empty."),
    SAY("Lyra", "He knows we are here. I would very much like to know since when."),
    SAY("Kenji", "Since Eldergate, probably. Maybe longer. Let's go and find Tomas."),
    ACT("flag", key="sg_speech"),
    ACT("follow", t=1.2),
]
event("sg_speech_cs", "The Queen's address", 0.0, -8.0, SPEECH, "", 20.0, 3.0, hide="sg_speech", trigger="touch", once=True)

# ------------------------------------------------------------------ 3. the Works (z -98 .. -170)
WZ = -98.0
for i in range(int(88 / S) + 1):                      # the Works' outer wall, with the gate gap at x 33 .. 41
    x = -44 + i * S
    if 31.5 < x < 41.5: continue
    ken("wall-fortified", x, WZ, 0, 0, S); block(x, WZ, S, 1.2)
ken("wall-fortified-gate", 34.5, WZ, 0, 0, S * 0.6, "sg_overseer"); ken("wall-fortified-gate", 38.5, WZ, 0, 0, S * 0.6, "sg_overseer")
T.COL.append(dict(x=37.0, z=WZ, w=9.0, d=1.4, hideIf="sg_overseer"))
for sx in (-30, 30, 44):
    ken("tower-base", sx, WZ, 0, 0, S * 1.5); ken("tower", sx, WZ, 0, S * 1.5, S * 1.5); ken("tower-top", sx, WZ, 0, S * 3.0, S * 1.5); block(sx, WZ, 4.4, 4.4)
for z in range(-98, -172, -6):                        # side walls and the back wall
    for sx in (-44, 44):
        ken("wall-fortified", sx, z, 90, 0, S); block(sx, z, 1.0, 6.0)
for i in range(int(88 / S) + 1):
    x = -44 + i * S
    ken("wall-fortified", x, -174.0, 0, 0, S); block(x, -174.0, S, 1.0)
# pipes: rows of pillars carrying gold light up into the Wall
for (x, z) in [(sx, z) for sx in (-36, -12, 12, 36) for z in (-110, -126, -142, -158)]:
    put(DG + "SM_dg_pillar", x, z, 0, 0, 1.2); block(x, z, 1.4, 1.4); glow(x, z, 6, [1, 0.8, 0.4, 0.5])
for k in range(8):
    glow(-34 + k * 9.5, -120.0, 8, [1, 0.8, 0.45, 0.28]); glow(-34 + k * 9.5, -150.0, 8, [1, 0.8, 0.45, 0.28])
# bunks
for (x, z) in ((-28, -116), (-20, -116), (-28, -130), (-20, -130), (24, -116), (32, -116), (24, -130), (32, -130)):
    put(ST + "SM_Stylized_Bench", x, z, 90, 0, 1.0); block(x, z, 1.4, 3.0)
chest("sc4", -40.0, -170.0, dict(gold=3000, shards=40, items={"potion": 5, "ether": 3, "antidote": 2}))
# the Overseer's gate, then the Great Valve at the back
npc("cathal", "Overseer Cathal", "Overseer of the Works", "Draven", 37.0, -94.5, tint=[1.2, 0.95, 0.5, 1], h=2.9, reach=5.0, hide="sg_overseer", actions=[
    SAY("Overseer Cathal", "Halt. The Works is not a place for visitors. The Queen herself has not passed this gate in years. State your business, in writing, in triplicate."),
    SAY("Kenji", "I'm here for a boy named Tomas. And for the forty others in his shift."),
    SAY("Overseer Cathal", "'Boy.' Kindler Tomas is the second-longest-serving lamp in this Works. He has never missed a shift. Is that not the character of a boy? Would you pull the lamps from the Wall?"),
    SAY("Reya", "He's my brother."),
    SAY("Overseer Cathal", "Then you should be proud. He is the only reason the Third Ring has heat on its coldest nights. I hold the gate for him. I hold it for the nine hundred thousand."),
    SAY("Miya", "And what do you hold it against?"),
    SAY("Overseer Cathal", "Hysteria. Heroes. Idealists who are very sure of themselves and very certain they are alone in having noticed. Stand back."),
    dict(type="battle", key="sg_overseer", pool=["stone_gargoyle"], level_rel=[2, 4], elite=1.55)])
npc("cathal_b", "Overseer Cathal", "Overseer of the Works", "Draven", 33.0, -94.5, tint=[1.2, 0.95, 0.5, 1], h=2.9, reach=5.0, show="sg_overseer", actions=[
    SAY("Overseer Cathal", "...Go in. I have counted the pipes for thirty years and I never once counted what I was asking of them. Tomas is at the far end, at the valve. He will not speak to you at first. Be patient. He has had practice at not being heard."),
    SAY("Overseer Cathal", "Do not take them out in a night. If the Wall goes out all at once, the Ring will come to the Works with torches, and they will not be wrong to. Find another way.")])
KIND = [("kindler1", -26.0, -122.0), ("kindler2", -22.0, -122.0), ("kindler3", -26.0, -136.0), ("kindler4", 28.0, -122.0), ("kindler5", 30.0, -136.0), ("kindler6", 0.0, -118.0)]
LINES = [
    ("I'm not tired. I'm not. Tomas says if I say it enough, the shift passes faster.", "The shifts got long when somebody cut the Spire. Tomas says it isn't your fault. I think it's a bit your fault."),
    ("Is it morning? The light never changes. I forgot what morning looks like.", "The gold's getting thin on my hands. Tomas says to ignore it. He ignores it for all of us."),
    ("If you take me outside, will it be cold?", "If you take me outside, will it be warm? Will it be warmer than here?"),
    ("They gave me a number when I came in. I can't remember what my name was. Tomas says it's Pim.", "They doubled the shifts and Pim fell asleep standing up. Tomas carried him to his bunk and took his shift."),
    ("My mother's name is on a ledger. I can read it. I can't read the part after it.", "My mother's name is on a ledger. Someone wrote 'serving' next to it. What does 'serving' mean?"),
    ("Shh. The lamp is humming. When it hums low, the Wall is happy.", "The lamp is humming wrong. Tomas says to ignore it. The Wall is running hungry."),
]
for (kid, x, z), (a, b) in zip(KIND, LINES):
    npc(kid, "Kindler", "Works child", "Townee", x, z, h=1.9, tint=[1.25, 1.05, 0.6, 1], actions=[
        SAY("Kindler", a, **{"unless": "ar_spire_off"}), SAY("Kindler", b, **{"if": "ar_spire_off"}),
        SAY("", "A faint gold light moves in the child's hands like a slow pulse.")])
event("sg_plate", "A brass plate", -20.0, -158.0, [
    SAY("", "A brass plate bolted to the nearest pillar. Crown lettering: THIRD RING WORKS. And beneath it, in a cold, even hand, scratched into the metal as if it had always been there: SUBJECT PRESENT. OBSERVE CHOICE.", ),
    SAY("Lyra", "It isn't just watching, Kenji. It is taking notes."),
    SAY("Kenji", "Then let it write something it didn't expect.")], "Read the plate", 3.6, 2.6)

# Tomas and the Great Valve
npc("tomas", "Tomas", "Shift lead, the Steady", "Townee", 0.0, -164.5, h=2.2, tint=[1.25, 1.05, 0.65, 1], reach=5.0, show="sg_overseer", actions=[
    ACT("cine", on=True, **{"if": "!sg_tomas"}),
    ACT("cam", x=0, z=-160, yaw=0, pitch=28, dist=16, t=1.2, **{"if": "!sg_tomas"}),
    SAY("", "A tall young man stands at the iron wheel of the Great Valve, hands flat against the metal. Gold runs under his skin from palm to wrist in a thin, patient pulse. He does not turn around when the party approaches.", **{"if": "!sg_tomas"}),
    SAY("Tomas", "Overseer's off tonight, I take it. Or you've killed him. Either way, you're early. The next shift's in an hour.", **{"if": "!sg_tomas"}),
    SAY("Reya", "Tomas.", **{"if": "!sg_tomas"}),
    SAY("", "His hands stay where they are. His shoulders go very still.", **{"if": "!sg_tomas"}),
    SAY("Tomas", "...Three. Two.", **{"if": "!sg_tomas"}),
    SAY("Reya", "Three. Then two. You taught me. You said somebody has to be on the other side.", **{"if": "!sg_tomas"}),
    SAY("", "He turns. He is seventeen and looks older, with the careful, unhurried face of someone who has learned to spend every motion once. He looks at Reya for a long time, and a single gold tear runs down his face and goes out.", **{"if": "!sg_tomas"}),
    SAY("Tomas", "You're so tall. You've got Da's ears. I... I thought they'd stopped sending anyone to the Third Ring. I thought you'd all forgotten the code.", **{"if": "!sg_tomas"}),
    SAY("Reya", "I never forgot. I've been knocking on that hatch for six years. Come home.", **{"if": "!sg_tomas"}),
    SAY("Tomas", "I can't.", **{"if": "!sg_tomas"}),
    SAY("Reya", "What do you mean you CAN'T. I came all the way down here, I fought the Quartermaster, I...", **{"if": "!sg_tomas"}),
    SAY("Tomas", "If I leave, there are forty of them on this shift who will take mine on top of theirs. Pim can barely stand. Ria is six. I know the count by heart: the heat in these pipes is the sum of us, and every one I take out puts a hundred and sixty weight on the ones who stay.", **{"if": "!sg_tomas,!ar_spire_off"}),
    SAY("Tomas", "And nine days ago the shifts doubled. Somebody cut a spire in the provinces and the Wall flickered. They took the cold from the Works. I've been on a double for nine days, and the little ones on triples. I don't blame whoever did it. I'd have done it too. But I'd have asked what comes after.", **{"if": "!sg_tomas,ar_spire_off"}),
    SAY("Kenji", "What comes after? You tell me.", **{"if": "!sg_tomas,ar_spire_off"}),
    SAY("Tomas", "Nothing good. Not unless somebody goes down.", **{"if": "!sg_tomas,ar_spire_off"}),
    SAY("Tomas", "Down. Past the valve. The pipes all run to something under the throne. The older ones call it the Heart. Nobody who goes there comes back, and nobody who stays up here asks. If you wanted to end this, that's where you'd have to go. But I think the Queen would rather turn the valve than let anyone see it.", **{"if": "!sg_tomas"}),
    ACT("flag", key="sg_tomas", **{"if": "!sg_tomas"}),
    dict(type="choice", who="Kenji", text="What do you say to Tomas?", **{"if": "sg_tomas,!sg_tomas2"}, options=[
        dict(label="\"Tell me how to reach the Heart.\"", actions=[
            SAY("Kenji", "I'm not taking you out in a night, and I'm not going to ask you to stay in a cage while I think about it. Tell me how to get to the bottom of it."),
            SAY("Tomas", "The valve opens with a kindler's key. Every shift lead has one. It's the only thing I've ever owned."),
            SAY("", "He takes a ring of old brass from around his neck. The key is warm, and it hums when he puts it in Kenji's marked hand."),
            SAY("Tomas", "The Queen isn't a monster. She cried when she signed the first intake. I was there. Don't go down there thinking she is one."),
            ACT("flag", key="sg_tomas2")]),
        dict(label="\"Reya. It's your call.\"", actions=[
            SAY("Kenji", "He's your brother. I'm not going to pretend I know what he's owed. What do you want to do?"),
            SAY("Reya", "...I want to drag him out by the collar. I want to put him on my back and run. And I know exactly what happens to the Ring if I do."),
            SAY("Reya", "So I'm going to do the stupid thing. I'm going to stay on the side of the people who find out what's at the bottom of this."),
            SAY("Tomas", "That's the first thing you've said that sounds like Da."),
            SAY("", "He takes a ring of old brass from around his neck, the kindler's key, and presses it into Reya's palm, then folds her fingers shut.", ),
            SAY("Tomas", "Don't lose it. And don't let them make you count."),
            ACT("flag", key="sg_tomas2")])]),
    SAY("Tomas", "The valve's behind me. Don't wait on my account. The shift's in an hour and I want to be on my feet for it.", **{"if": "sg_tomas2"}),
    ACT("follow", t=1.2)])
event("sg_valve", "The Great Valve", 0.0, -169.5, [
    SAY("", "An iron wheel the size of a house, brass-ringed, bolted over a shaft that goes down into the dark. Warm air rises through the spokes, and under it, very faint, something that sounds like a heartbeat a long way off.", **{"unless": "eh_end"}),
    SAY("Lyra", "The Emberheart. It's beneath us. Everything in this city is a pump built on top of it.", **{"unless": "sg_end"}),
    SAY("", "The wheel is unlatched, and the shaft below is quiet and warm. Where the heartbeat used to be there is only a soft, even hum, like someone breathing in their sleep.", **{"if": "eh_end"}),
    dict(type="choice", who="Kenji", text="Go down the Great Valve?", options=[
        dict(label="Go down to the Emberheart", actions=[
            SAY("Kenji", "Whatever she decides when we get there, I want her to decide it knowing we saw it.", **{"unless": "sg_end"}),
            SAY("Reya", "And I want to look the Queen in the eye.", **{"unless": "sg_end"}),
            SAY("", "The valve turns on the kindler's key. The wheel groans open, and a column of gold air rises through the grate. The party goes down the iron stair one at a time.", **{"unless": "sg_end"}),
            ACT("flag", key="sg_end"),
            ACT("fade", to="black", t=1.2),
            ACT("warp", scene="heart", x=0.0, z=52.0, fresh=True)]),
        dict(label="Not yet", actions=[ACT("end")])])],
    "Look at the valve", 6.0, 3.6, show="sg_tomas2")

# ------------------------------------------------------------------ after Chapter D (flags set in heart.json): Solgard reacts to the Queen's fate
def after_fate(npc_id, f1, f2, f3, who=None, replace=True):
    """Puts three fate-dependent lines (eh_f1 / eh_f2 / eh_f3) in front of an NPC's lines and, when replace, hides the old lines once eh_end is set."""
    n = next(n for n in NPCS if n["id"] == npc_id)
    who = who or n["name"]
    if replace:
        for a in n["actions"]:
            ifs = []
            if a.get("if"): ifs.append(a.pop("if"))
            if a.get("unless"): ifs.append("!" + a.pop("unless"))
            ifs.append("!eh_end")
            a["if"] = ",".join(ifs)
    new = []
    for flag, txt in (("eh_f1", f1), ("eh_f2", f2), ("eh_f3", f3)):
        new.append(SAY(who, txt, **{"if": "eh_end," + flag}))
    n["actions"] = new + n["actions"]


after_fate("baker", "The Wall went out at dawn and nobody died of it. The Works children walked out holding hands and the whole Ring came into the street, and I gave away every loaf I had. The Queen's in the Heart by her own will, they say. I don't know whether to curse her or cry.",
           "The Queen is reading names on the palace steps and nobody has gone home. Some are shouting and some are crying, and one old man has just handed her a blanket. I don't know what we are, as a city. I think we're about to find out.",
           "The Queen is dead, they say, and a boy with a gold hand did it. The Wall went out in the night and the Ring did not riot. It just stood in the streets in the dark. Nobody is in charge. Brienne has put herself at the head of the bread line because nobody else would.")
after_fate("elder_ring", "She did it herself. I will never forgive her and I will never forget that she did it. I am eighty-one and I will stand in the cold with everyone else this winter, and I want you to know that I am glad.",
           "They have asked me to sit on a council. I said I never asked where the heat came from. They said: that is why. Ask now.",
           "Three people have asked me who rules the Ring now. I said no one does, and that we had better learn how to do it ourselves, quickly, because the cold does not care how we feel about it.")
after_fate("cathal_b", "The Works doors are open. I walked them through each one. I have never in my life been thanked by a child. It is a very uncomfortable thing and I would do it again.",
           "I have offered the Queen my testimony. I counted every pipe. I am to read my part in the ledger directly after hers, and I find I would like to hear her read it first.",
           "The Works is open and nobody knows what to do with it. The Queen is dead and I signed her orders for thirty years. I am hanging my chain of office on the gatepost. Someone should have it who has not counted so well.")
after_fate("tomas", "I'm taking Pim out at dawn. Then Ria. Then, I suppose, myself. I keep waiting for someone to tell me to go back to my post.",
           "I'm going to stand beside her on the steps. Not for her. For the ledger. Somebody should hold the lamp.",
           "I'm staying until the last child has gone up the stair. After that I think I'll want to sleep for about a year.", replace=False)
for t in NPCS:
    if t["id"] == "tomas":                                           # his old closing line must not show once the Heart is done
        for a in t["actions"]:
            if a.get("if") == "sg_tomas2": a["if"] = "sg_tomas2,!eh_end"
for t in NPCS:
    if t["id"].startswith("kindler") and t["id"] != "kindler_h":
        for a in t["actions"]:
            ifs = []
            if a.get("if"): ifs.append(a.pop("if"))
            if a.get("unless"): ifs.append("!" + a.pop("unless"))
            ifs.append("!eh_end"); a["if"] = ",".join(ifs)
        t["actions"] = [SAY("Kindler", "Is it morning? It is! There's a sky, and it's a different colour from the lamp.", **{"if": "eh_end,!eh_f3"}),
                        SAY("Kindler", "The lamp went out. I thought I'd be scared. I'm mostly just cold, and the cold feels like mine.", **{"if": "eh_end,eh_f3"}),
                        SAY("", "The gold under the child's skin has gone quiet. What's left is only warmth, and it doesn't hum.", **{"if": "eh_end"})] + t["actions"]


# ------------------------------------------------------------------ arrival scene
ARRIVE = [
    ACT("cine", on=True),
    dict(type="music", url=MUSIC + "15. Volcanic Crater.mp3"),
    ACT("fade", to="clear", t=2.5, wait=False),
    ACT("cam", x=0, z=44, yaw=0, pitch=36, dist=22, t=0),
    SAY("", "Iron rungs, a wet stone tunnel, the smell of oil and bread and lamp smoke. A gold light moves ahead of you in the dark, and when you reach the bottom of the ladder, a stooped man holds a lantern up to your faces."),
    SAY("Reya", "Odo?"),
    SAY("", "Warm air drifts through the tunnel from somewhere ahead. After the Road of Ash it feels like a lie."),
    SAY("Lyra", "This is the first warmth in days that feels like it has a price."),
    SAY("Kenji", "Then let's find out who pays it."),
    ACT("flag", key="sg_arrive"),
    ACT("follow", t=1.2),
]
OBJECTIVES = [
    {"unless": "sg_odo", "text": "Speak with the lamplighter at the foot of the Underdrain."},
    {"unless": "sg_speech", "text": "Climb the drain stair and enter the Bright Ring. (Mind your right hand.)"},
    {"unless": "sg_overseer", "text": "The Works is east of the palace. Get past Overseer Cathal at its gate."},
    {"unless": "sg_tomas", "text": "Find Tomas in the Works, past the bunks, at the Great Valve."},
    {"unless": "sg_tomas2", "text": "Decide how to answer Tomas."},
    {"unless": "sg_end", "text": "Take the kindler's key to the Great Valve and descend to the Emberheart."},
    {"unless": "eh_arrive", "text": "Go down the Great Valve to the Emberheart."},
    {"unless": "eh_end", "text": "Go down the Great Valve to the Emberheart again."},
    {"text": "The Heart burns for itself now. Chapter E, the dawn after, follows in a later part of the story."},
]

scene = {
    "story": True, "name": "Solgard", "kit": "", "tile": 4,
    "autorun": [dict(unless="sg_arrive", cine=True, actions=ARRIVE)], "objectives": OBJECTIVES,
    "music": {"url": MUSIC + "15. Volcanic Crater.mp3"},
    "pieces": T.P, "colliders": T.COL, "decals": T.DEC, "npcs": NPCS, "events": EVENTS,
    "spawn": {"x": 0, "z": 50}, "bounds": BOUNDS, "playerHeight": 2.4,
    "camera": {"pitch": 24, "dist": 30},
    "light": {"dir": [-0.4, -1, -0.3], "color": [0.78, 0.68, 0.55], "ambient": [0.38, 0.34, 0.32]},
    "fog": {"color": [0.42, 0.36, 0.3], "near": 35, "far": 125},
    "sky": {"type": "layers", "base": {"type": "gradient", "stops": [[0, "#3b2e2a"], [0.5, "#b88a5a"], [1, "#f0d29a"]]}, "layers": []},
    "fx": [{"type": "embers", "amount": 0.22}],
    "encounters": {"rate": 66, "level": [28, 32], "level_rel": [0, 2], "pool": ["bandit_rogue", "venom_spider", "dark_cultist", "stone_gargoyle"],
                   "zones": [{"x": 0, "z": 38, "w": 28, "d": 8, "safe": True}, {"x": 0, "z": 0, "w": 100, "d": 150, "safe": True},
                             {"x": 0, "z": -96, "w": 100, "d": 6, "safe": True},
                             {"x": 0, "z": -136, "w": 88, "d": 66, "rate": 62, "pool": ["iron_golem", "stone_gargoyle", "flame_imp", "cursed_knight"]},
                             {"x": 0, "z": -166, "w": 20, "d": 10, "safe": True}],
                   "text": "Something stirs in the pipes..."},
}

if __name__ == "__main__":
    out = os.path.join(sys.argv[1] if len(sys.argv) > 1 else HERE, "solgard.json")
    with open(out, "w", encoding="utf-8", newline="") as f:
        json.dump(scene, f, ensure_ascii=False, separators=(",", ":"))
    print("solgard.json:", len(T.P), "pieces,", len(T.COL), "colliders,", len(NPCS), "npcs,", len(EVENTS), "events")

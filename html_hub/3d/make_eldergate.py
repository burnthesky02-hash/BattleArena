"""Builds html_hub/3d/eldergate.json: "The Eldergate Network", the buried portal hall under Dawnwatch (claude/eldergate-veyra-oct-13.md).
Reached by the Sunken Stair in the north-west ruin of Dawnwatch (strange.json, open from phase I once Brannoch has been met).
Layout on a 6 m grid (cell gx,gz centred at x=gx*6, z=gz*6; x = east, z = south, the camera looks north):
  Processional Hall (south, x -9..9, z -3..27): stair landing at the south end, four Chronicle plates I-IV down both walls.
  Rotunda (north, 9x9 cells): the Core (centre), six gates along the north wall, the Watcher's Ledger (west alcove) and the Last King's seat (east alcove, plate V).
Story flags (all eg_*):  eg_enter (arrival scene seen)  eg_t1..eg_t5 (plates read)  eg_ledger (Watcher's Ledger read)  eg_core (Core woken: the Veyra gate is open)
Run:  python make_eldergate.py [outdir]   (re-running overwrites hand edits made in /builder3d)"""
import json, math, os, sys, random
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
MG, DG = "/assets/3D/Megastructure/", "/assets/3D/Dungeon/"
MUSIC = "/assets/Music/mp3/"
CS = 6.0
P, COL, DEC, NP, EV = [], [], [], [], []


def put(n, x, z, rot=0, y=0, sc=1, spec=None, pre=DG):
    p = [pre + n, round(x, 3), round(z, 3), rot, round(y, 3), sc]
    if spec: p.append(spec)
    P.append(p)


def block(x, z, w, d, hide=None):
    c = {"x": round(x, 3), "z": round(z, 3), "w": round(w, 3), "d": round(d, 3)}
    if hide: c["hideIf"] = hide
    COL.append(c)


def glow(x, z, r, c, show=None, hide=None):
    d = dict(type="glow", x=round(x, 2), z=round(z, 2), r=r, color=c)
    if show: d["showIf"] = show
    if hide: d["hideIf"] = hide
    DEC.append(d)


def glyph(x, z, r, c, spin=0, show=None, hide=None):
    d = dict(type="glyph", x=round(x, 2), z=round(z, 2), r=r, spin=spin, color=c)
    if show: d["showIf"] = show
    if hide: d["hideIf"] = hide
    DEC.append(d)


SAY = lambda who, text, **k: dict(type="say", who=who, text=text, **k)
ACT = lambda _ty, **k: dict(type=_ty, **k)
GOLD, BLUE, PALE, VIO, GREY = [1, .8, .35, .24], [.4, .8, 1, .045], [.8, .9, 1, .06], [.7, .42, 1, .2], [.55, .6, .7, .08]


def event(id, name, x, z, actions, prompt, w=3.2, d=2.6, show=None, hide=None):
    e = dict(id=id, name=name, x=round(x, 2), z=round(z, 2), w=w, d=d, trigger="talk", prompt=prompt, actions=actions)
    if show: e["showIf"] = show
    if hide: e["hideIf"] = hide
    EV.append(e)


# ------------------------------------------------------------------ floor plan
F = set()
for gx in range(-1, 2):
    for gz in range(0, 5): F.add((gx, gz))                    # the hall, z 0..24 (cells) -> metres -3..27
for gx in range(-4, 5):
    for gz in range(-9, 0): F.add((gx, gz))                   # the rotunda
for gx in range(-7, -4):
    for gz in range(-7, -3): F.add((gx, gz))                  # west alcove (the Ledger)
for gx in range(5, 8):
    for gz in range(-7, -3): F.add((gx, gz))                  # east alcove (the Last King)
W = lambda g: g * CS
for (gx, gz) in sorted(F): put("SM_floor_module_02", W(gx), W(gz), 0, -2.4, 1.2, pre=MG)

blocked = set()
for (gx, gz) in F:
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if (gx + dx, gz + dz) not in F: blocked.add((gx + dx, gz + dz))
WALL_H = 6.0
walls = {c for c in blocked if any((c[0] + dx, c[1] + dz) in F for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
for (gx, gz) in sorted(walls):
    if gz >= 5: continue                                          # no wall in front of the camera at the stair end
    put("SM_dg_wall", W(gx), W(gz), 0, WALL_H - 4.2 * 1.5, 1.5)
rows = {}
for (gx, gz) in blocked: rows.setdefault(gz, []).append(gx)
for gz, xs in rows.items():
    xs.sort(); s = prev = xs[0]
    for x in xs[1:] + [None]:
        if x is None or x != prev + 1:
            block(W((s + prev) / 2), W(gz), (prev - s + 1) * CS, CS); s = x
        if x is not None: prev = x


# ------------------------------------------------------------------ props
def pillar(x, z, sc=1.6, col=PALE):
    put("SM_dg_pillar", x, z, 0, 0, sc); block(x, z, 1.6, 1.6)


def brazier(x, z, rad=7.0, col=BLUE):
    put("SM_dg_brazier", x, z); put("SM_dg_flame", x, z, 0, 1.55, 1.0); block(x, z, 1.1, 1.1); glow(x, z, rad, col)


def plate(key, name, x, z, rot, text_actions, flag, ex=0, ez=1.8):
    put("SM_dg_tablet", x, z, rot); block(x, z, 1.6 if rot % 180 == 0 else 0.5, 0.5 if rot % 180 == 0 else 1.6)
    event(key, name, x + ex, z + ez, text_actions + [ACT("flag", key=flag)], "Read the plate", 3.4, 2.6)
    glow(x + ex * 0.5, z + ez * 0.5, 3.5, [.8, .9, 1, .10])


# the hall: braziers and pillars
for z in (22, 10, -2):
    for sx in (-1, 1):
        pillar(sx * 8.0, z)
        glow(sx * 8.0, z, 5, [.8, .9, 1, .03])
for z in (16, 4):
    for sx in (-1, 1): brazier(sx * 8.0, z, 6, BLUE)

# ---- the Chronicle plates I-IV (hall) and V (the Last King's seat)
LINE = lambda who, t: SAY(who, t)
plate("eg_p1", "Chronicle I", -8.4, 21.0, 90, [
    SAY("Chronicle I", "ELDERGATE, SEAT OF THE KINGDOM OF THE OPEN DOOR. OUR FOUNDERS HELD THAT THE GREATEST DANGER TO ANY PEOPLE IS TO BE ALONE."),
    SAY("Chronicle I", "THE SCHOLARS OF THE HIGH COLLEGE PROVED WHAT THE POETS HAD ONLY GUESSED: THE UNIVERSE IS NOT ONE CONTINUOUS WORLD. WORLDS LIE BESIDE ONE ANOTHER, PARTED BY BARRIERS THAT KNOWLEDGE CAN CROSS."),
    SAY("Lyra", "That is the theory I spent half my life chasing. They built a city on it."),
    SAY("Miya", "A kingdom that believed isolation was the danger. After the Colosseum, I find I cannot argue with them."),
], "eg_t1", ex=1.9, ez=0)
plate("eg_p2", "Chronicle II", 8.4, 15.0, 270, [
    SAY("Chronicle II", "THE ELDERGATE NETWORK. A GATE FOR EVERY WORLD THAT ANSWERED. THROUGH THEM WENT GRAIN AND GLASS, MEDICINE AND SONG, AND FOR GENERATIONS NO CHILD OF THE KINGDOM WENT HUNGRY."),
    SAY("Chronicle II", "THE GATES DO NOT ALL OPEN ON THE SAME DAY. WE LEARNED TO ASK 'WHEN?' BEFORE 'WHERE?'. SOME LEAD TO WORLDS IN THEIR NOON, SOME TO WORLDS IN THEIR FAMINE, A FEW TO PLACES WHERE NOTHING REMAINS BUT WIND."),
    SAY("Kenji", "So a door here does not open on the same year there."),
    SAY("Lyra", "Which means whatever is on the other side of any gate, the people in it may already be too late, or about to be."),
], "eg_t2", ex=-1.9, ez=0)
plate("eg_p3", "Chronicle III", -8.4, 9.0, 90, [
    SAY("Chronicle III", "BUT SOME DOORS OPENED ON WORLDS WHOSE POWERS COULD NOT BE CARRIED SAFELY. ONE SPARK SPILLING THROUGH COULD BURN A NEIGHBOURING SKY."),
    SAY("Chronicle III", "THE CROWN SEALED THOSE GATES AND SET GUARDIANS UPON THE KEYS. ACCESS TO THE DANGEROUS WORLDS WAS FORBIDDEN, AND WE CALLED THIS WISDOM."),
    SAY("Lyra", "The Shard Vault. The lattice, the wardens, the sealed door. That was one of their locks."),
    SAY("Miya", "Then Rook, the Mind, whoever he is, simply walked through a door the old kingdom shut."),
], "eg_t3", ex=1.9, ez=0)
plate("eg_p4", "Chronicle IV", 8.4, 3.0, 270, [
    SAY("Chronicle IV", "THEN THE ROYAL SCHOLARS FOUND THE THING WE WRITE HERE WITH SHAME. CERTAIN GATES WERE NOT OURS. THEY HAD BEEN OPENED FROM THE OTHER SIDE: NOT TO TRAVEL, BUT TO OBSERVE."),
    SAY("Chronicle IV", "SOMEONE HAD BEEN WATCHING THE WORLDS. SOMEONE HAD BEEN RECORDING THE RISE AND FALL OF PEOPLES. AND SOMEONE HAD BEGUN TO LEAN UPON THEM."),
    SAY("Miya", "Lean?"),
    SAY("Lyra", "Influence. A rumour to a king, a bad harvest left unmended, a door left unlocked. Small pushes."),
    SAY("Kenji", "The Mind."),
    SAY("Lyra", "The plate does not name him."),
    SAY("Kenji", "It does not have to."),
    SAY("", "A faint cold gathers in the west alcove of the great hall ahead."),
], "eg_t4", ex=-1.9, ez=0)

# ---- the Core: a dormant mechanism in the heart of the rotunda
CX, CZ = 0.0, -26.0
put("SM_dg_dais", CX, CZ, 0, 0, 2.6); block(CX, CZ, 6.0, 6.0)
put("SM_dg_crystal", CX, CZ, 0, 0.6, 3.2, spec="H:eg_core")
put("SM_dg_crystal", CX, CZ, 0, 0.6, 3.6, spec="S:eg_core")
glow(CX, CZ, 9, GREY, hide="eg_core"); glow(CX, CZ, 16, GOLD, show="eg_core")
glyph(CX, CZ, 6.5, [.5, .55, .7, 0.5], 0, hide="eg_core"); glyph(CX, CZ, 9.5, [1, .8, .35, 1], 30, show="eg_core")
for k in range(8):
    a = k * math.tau / 8 + math.pi / 8
    x, z = CX + 8.5 * math.cos(a), CZ + 8.5 * math.sin(a)
    if z > -12: continue
    pillar(x, z, 1.5)
for sx in (-1, 1):
    brazier(sx * 12.0, -14, 6, BLUE)

# ---- the six gates along the north wall (the third from the east, "Veyra", is the only one that ever answers)
GATE_Z = -49.0
GATES = [
    ("Hollowmere", "A DROWNED KINGDOM. THE WATER DID NOT RECEDE. THE GATE SHOWS ONLY SLOW GREEN LIGHT."),
    ("The Glass Reach", "A MERCHANT-PRINCEDOM AT ITS NOON. THREE MOONS, SIX THOUSAND LANTERNS. THE GATE IS DARK; ITS KEY IS MISSING."),
    ("Veyra, the Kingdom of Ash", "A KINGDOM THAT BURNS ITS OWN HEARTH TO KEEP WARM. TWENTY WINTERS INTO THE ASHFALL."),
    ("Ninefold", "NINE REALMS AT WAR, EACH TOLD THE OTHERS STARTED IT. THE GATE IS SEALED FROM THE OTHER SIDE."),
    ("Cinderhold", "NOTHING REMAINS BUT WIND. THE GATE REMEMBERS A CITY AND OFFERS ONLY DUST."),
    ("The Last Orchard", "A GARDEN WORLD, OR WHAT IS LEFT OF ONE. THE GATE FLICKERS AND GIVES NOTHING."),
]
GX = [-22.0, -13.2, -4.4, 4.4, 13.2, 22.0]
VEYRA = 3                                                       # index: x = 4.4 (the 4th from the west)
for i, (nm, txt) in enumerate(GATES):
    x = GX[i]
    on = i == VEYRA
    put("SM_dg_gate", x, GATE_Z, 0, 0, 1.5, spec="H:eg_core" if on else None); block(x, GATE_Z, 6.0, 1.5, "eg_core" if on else None)
    if on:
        put("SM_dg_crystal", x - 3.6, GATE_Z + 2.0, 20, 0, 1.3, spec="H:eg_core"); put("SM_dg_crystal", x + 3.6, GATE_Z + 2.0, 130, 0, 1.3, spec="H:eg_core")
        put("SM_dg_crystal", x - 3.6, GATE_Z + 2.0, 20, 0, 1.6, spec="S:eg_core"); put("SM_dg_crystal", x + 3.6, GATE_Z + 2.0, 130, 0, 1.6, spec="S:eg_core")
        glow(x, GATE_Z + 1.5, 6, GREY, hide="eg_core"); glow(x, GATE_Z + 2.0, 12, [1, .62, .3, .55], show="eg_core")
        glyph(x, GATE_Z + 3.5, 3.4, [1, .62, .3, 1], 45, show="eg_core")
    else:
        put("SM_dg_crystal", x - 3.6, GATE_Z + 2.0, 20 * i, 0, 1.0); put("SM_dg_crystal", x + 3.6, GATE_Z + 2.0, 130 + i, 0, 1.0)
        glow(x, GATE_Z + 1.5, 6, GREY)
    # plaque in front of the gate
    put("SM_dg_tablet", x, GATE_Z + 6.0, 180, 0, 0.8); block(x, GATE_Z + 6.0, 1.3, 0.5)
    acts = [SAY("Gate Plaque", nm.upper() + ". " + txt)]
    if on:
        acts.append(SAY("Gate Plaque", "THIS GATE ALONE STILL ANSWERS THE KEY IN THE ROYAL HAND.", hide="eg_core"))
        acts.append(SAY("Gate Plaque", "THE GATE IS OPEN. THE ASH IS FALLING ON THE FAR SIDE; THE WINTER IS OLD.", show="eg_core"))
    event("eg_plq%d" % i, "Gate plaque", x, GATE_Z + 7.9, acts, "Read the plaque", 3.4, 2.2)

# ---- the Veyra gate itself
event("eg_veyra", "The Veyra gate", GX[VEYRA], GATE_Z + 4.4, [
    SAY("", "The gate holds open on a wall of falling grey. Cold wind carries the smell of old fires. Somewhere beyond it, a bell is tolling for the dead, slowly, as if there were no hurry left to hurry for."),
    dict(type="choice", who="Kenji", text="Step through to Veyra?", options=[
        dict(label="Step through (you can come back through this gate)", actions=[
            ACT("flag", key="eg_veyra_go"),
            ACT("fade", to="black", t=1.4),
            ACT("title", text="Veyra", sub="The Kingdom of Ash", t=3.4),
            ACT("warp", scene="veyra", x=0, z=28, fresh=True)]),
        dict(label="Not yet", actions=[ACT("end")])])],
    "Look through the gate", 7.0, 3.6, show="eg_core")

# ---- the Watcher's Ledger (west alcove)
LX, LZ = -39.0, -30.0
for k, z in enumerate((-34.5, -30.0, -25.5)):
    put("SM_dg_tablet", LX - 1.5, z, 90, 0, 1.2); block(LX - 1.5, z, 0.5, 1.8)
    glow(LX - 0.4, z, 3.6, [.35, .95, .85, .35])
put("SM_dg_crystal", LX + 3.2, LZ - 5.5, 40, 0, 1.2); block(LX + 3.2, LZ - 5.5, 1.1, 1.1); glow(LX + 3.2, LZ - 5.5, 6, [.35, .95, .85, .3])
glyph(LX + 2.0, LZ, 4.5, [.35, .95, .85, 0.9], -25)
event("eg_ledger", "The Watcher's Ledger", LX + 1.2, LZ, [
    SAY("", "Black glass stands in a half-circle, each pane showing a world: a drowned city under green light, a glass market beneath three moons, a battlefield older than its flags. Under each, a line of fine script rewrites itself as you watch.", **{"unless": "eg_t4"}),
    SAY("", "You have not read enough to understand what you are looking at. The old plates in the hall may help.", **{"unless": "eg_t4"}),
    SAY("", "Black glass stands in a half-circle, each pane showing a world: a drowned city under green light, a glass market beneath three moons, a battlefield older than its flags. Under each, a line of fine script rewrites itself as you watch.", **{"if": "eg_t4", "unless": "eg_ledger"}),
    SAY("Lyra", "Observation records. They are live. Whoever wrote the plates said a watcher had opened gates from the other side. This is what he saw.", **{"if": "eg_t4", "unless": "eg_ledger"}),
    SAY("Ledger", "HOLLOWMERE. PRESSURE APPLIED 410 SEASONS PAST: A SEA-WALL LEFT UNMENDED, A WARNING SUPPRESSED. OUTCOME: EXTINCTION.", **{"if": "eg_t4", "unless": "eg_ledger"}),
    SAY("Ledger", "THE GLASS REACH. PRESSURE APPLIED: A SCHISM IN THE MERCHANT COUNCIL. OUTCOME: ONGOING, UNFAVOURABLE.", **{"if": "eg_t4", "unless": "eg_ledger"}),
    SAY("Ledger", "VEYRA. PRESSURE APPLIED, TWENTY WINTERS: THE THRONE RECEIVES INCOMPLETE REPORTS. PEACEFUL COUNSELS SUPPRESSED. EVERY SACRIFICE APPEARS NECESSARY. OUTCOME: FAILING. INTERVENTION SUBJECT RECOMMENDED.", **{"if": "eg_t4", "unless": "eg_ledger"}),
    SAY("Miya", "Every entry ends the same way. Not with a cause. With a result he wanted to measure.", **{"if": "eg_t4", "unless": "eg_ledger"}),
    SAY("Ledger", "SUBJECT: KENJI. ARRIVED AT ELDERGATE. ........ PROCEEDING.", **{"if": "eg_t4", "unless": "eg_ledger"}),
    SAY("Kenji", "He is writing about me. While I stand here reading it.", **{"if": "eg_t4", "unless": "eg_ledger"}),
    SAY("Lyra", "He does not control every disaster. He does not need to. He finds the crack in a world, and he leans.", **{"if": "eg_t4", "unless": "eg_ledger"}),
    SAY("Kenji", "Then we find the crack first.", **{"if": "eg_t4", "unless": "eg_ledger"}),
    ACT("flag", key="eg_ledger", **{"if": "eg_t4"}),
    SAY("", "The glass keeps writing. The last line has gone dark. The line above it reads: VEYRA. PROCEEDING.", **{"if": "eg_ledger"}),
], "Read the Ledger", 5.0, 5.0)

# ---- the Last King's seat (east alcove): Chronicle V
RX, RZ = 39.0, -30.0
put("SM_dg_throne", RX + 1.5, RZ, 270, 0, 1.4); block(RX + 1.5, RZ, 2.2, 2.2)
brazier(RX - 4.0, RZ - 5.0, 6, [1, .75, .4, .3]); brazier(RX - 4.0, RZ + 5.0, 6, [1, .75, .4, .3])
put("SM_dg_tablet", RX - 4.5, RZ, 270, 0, 1.2); block(RX - 4.5, RZ, 0.5, 1.8)
glow(RX - 1.5, RZ, 5, [1, .85, .5, .3])
event("eg_p5", "The Last King's seat", RX - 6.2, RZ, [
    SAY("Chronicle V", "THE KING WOULD HAVE THE NETWORK BROKEN. HALF THE KINGDOM WOULD NOT HEAR IT. THE COLLEGES SPLIT. THE CROWN FRACTURED. HE ORDERED THE GATES SEALED, ONE BY ONE."),
    SAY("Chronicle V", "THE LAST GATE HAD NOT YET CLOSED WHEN IT FELL. THE CASTLE CAME DOWN UPON ITS OWN FOUNDATIONS. THE ROYAL HOUSE WAS NEVER FOUND. THE NETWORK WAS BURIED WITH US."),
    SAY("Chronicle V", "LET WHOEVER READS THIS KNOW WE WERE NOT ENEMIES. ONLY FRIGHTENED. AND FRIGHT, LEFT TO ITSELF, BUILDS THE VERY WALLS IT FEARS."),
    SAY("Miya", "The Grey Tide. That is what the survivors called the Fall of the Last Gate."),
    SAY("Lyra", "Brannoch's stones remembered the sunrise. These remember the end of it."),
    SAY("Kenji", "A capital built to keep every world connected, and it died of a quarrel over whether to disconnect them. Come on. I think the Core is waiting."),
    ACT("flag", key="eg_t5"),
], "Read the plate", 4.0, 3.4)

# ---- the Core (waking it opens the Veyra gate)
CORE = [
    SAY("", "The Core is cold stone and dust, a crystal the colour of old ash on a dais carved with nine rings. It looks like nothing at all. It looks like a clock that has been stopped so long it forgot how to be a clock.", **{"unless": "eg_t5"}),
    SAY("Lyra", "I would not touch it blind. Read what the builders left, all five plates. The Ledger too, if you can stand to.", **{"unless": "eg_t5"}),
    SAY("Lyra", "You have read everything the hall has to say, but you have not looked into the Ledger yet. West alcove. Do that first.", **{"if": "eg_t5", "unless": "eg_ledger"}),
    SAY("Kenji", "The mark has been warm since the stair. It is hot now.", **{"if": "eg_ledger", "unless": "eg_core"}),
    ACT("cine", on=True, **{"if": "eg_ledger", "unless": "eg_core"}),
    ACT("cam", x=0, z=-22, yaw=0, pitch=28, dist=18, t=1.4, **{"if": "eg_ledger", "unless": "eg_core"}),
    SAY("", "Kenji lays his marked hand on the crystal. Gold light runs up his arm and through the dais. The nine rings turn, one after another, for the first time in centuries.", **{"if": "eg_ledger", "unless": "eg_core"}),
    ACT("flash", **{"if": "eg_ledger", "unless": "eg_core"}),
    ACT("shake", **{"if": "eg_ledger", "unless": "eg_core"}),
    ACT("flag", key="eg_core", **{"if": "eg_ledger", "unless": "eg_core"}),
    SAY("", "Along the north wall, six gates stir. Five cough dust and die. The sixth holds, and burns amber.", **{"unless": "eg_core_done", "if": "eg_core"}),
    SAY("Lyra", "The Network is barely working. Whatever kept it alive kept it outside of time, but it is running on the last of that. One door answers. One.", **{"unless": "eg_core_done", "if": "eg_core"}),
    SAY("Miya", "Veyra. The same name the Ledger finished on.", **{"unless": "eg_core_done", "if": "eg_core"}),
    SAY("Kenji", "He is pointing us at it. Or leaning on it and waiting to see what we do.", **{"unless": "eg_core_done", "if": "eg_core"}),
    SAY("Lyra", "Does it matter which?", **{"unless": "eg_core_done", "if": "eg_core"}),
    SAY("Kenji", "No. If there are people at the other end of that door, I am going. And when I get there I do the one thing he did not plan for.", **{"unless": "eg_core_done", "if": "eg_core"}),
    ACT("flag", key="eg_core_done", **{"if": "eg_core"}),
    ACT("follow", t=1.2, **{"if": "eg_core"}),
    SAY("", "The Core hums low and steady. Behind you, the amber gate waits.", **{"if": "eg_core_done"}),
]
event("eg_core", "The Core", CX, CZ + 4.4, CORE, "Touch the Core", 5.0, 3.6)

# ---- the stair back up to Dawnwatch and the arrival scene
put("SM_dg_dais", 0, 27.5, 0, 0, 0.9); glyph(0, 27.5, 3.2, [1, .85, .6, .9], 20)
glow(0, 26, 6, [1, .85, .6, .3])
event("eg_up", "The stair", 0, 27.0, [
    ACT("fade", to="black", t=0.8), ACT("warp", scene="strange", x=-20, z=-23, fresh=True)], "Climb the Sunken Stair to Dawnwatch", 6.0, 2.4)

ARRIVE = [
    ACT("cine", on=True),
    ACT("music", url=MUSIC + "22. Ancient Library.mp3"),
    ACT("fade", to="clear", t=2.5, wait=False),
    ACT("cam", x=0, z=24, yaw=0, pitch=36, dist=16, t=0),
    SAY("", "The stair is longer than any ruin should hold. The mark on Kenji's hand throbs in time with your steps. At the bottom, lamp after lamp wakes along a hall of pale stone."),
    ACT("cam", x=0, z=6, yaw=0, pitch=26, dist=22, t=5, wait=False),
    SAY("Lyra", "That script. Not Veyran, not anything I have seen on a map of the Mind's. It is older. I can read it, barely. It says: ELDERGATE."),
    SAY("Kenji", "Brannoch called the keep Dawnwatch."),
    SAY("Lyra", "Dawnwatch is what soldiers call a hill they were told to hold. Eldergate is the name this place was born with."),
    SAY("Miya", "Then somebody built a city on top of whatever is down here, and forgot it."),
    SAY("Lyra", "Or tried to. Read the walls. Every plate is a page. Let's find out who builds a door this big."),
    ACT("flag", key="eg_enter"),
    ACT("follow", t=1.2),
]

OBJ = [
    {"unless": "eg_t4", "text": "Read the Chronicle plates in the hall (four along the walls, a fifth in the east alcove)."},
    {"unless": "eg_ledger", "text": "Look into the Watcher's Ledger in the west alcove of the great hall."},
    {"unless": "eg_t5", "text": "Read the Last King's plate in the east alcove."},
    {"unless": "eg_core", "text": "Touch the Core in the centre of the great hall."},
    {"unless": "eg_veyra_go", "text": "The Veyra gate is open, third from the east along the north wall. Step through when ready."},
    {"text": "Eldergate's other gates are silent. Return when Veyra has changed."},
]

scene = {
    "story": True, "name": "The Eldergate Network", "kit": "", "tile": 4,
    "autorun": [dict(unless="eg_enter", cine=True, actions=ARRIVE)], "objectives": OBJ,
    "music": {"url": MUSIC + "22. Ancient Library.mp3"},
    "pieces": P, "colliders": COL, "decals": DEC, "npcs": NP, "events": EV,
    "spawn": {"x": 0, "z": 22}, "bounds": {"minX": -52, "maxX": 52, "minZ": -62, "maxZ": 34}, "playerHeight": 2.4,
    "camera": {"pitch": 40, "dist": 34},
    "sky": {"type": "layers", "base": {"type": "gradient", "stops": [[0, "#02010a"], [0.5, "#0a0818"], [1, "#16102c"]]},
            "layers": [{"url": "/assets/Backgrounds/layers/stars.webp", "y": 0.3, "height": 0.66, "parallax": 0.04, "alpha": 0.8, "tint": [1, 0.95, 1.1]}]},
    "light": {"dir": [-0.3, -1, -0.2], "color": [0.42, 0.42, 0.6], "ambient": [0.22, 0.22, 0.34]},
    "fog": {"color": [0.04, 0.03, 0.09], "near": 40, "far": 150},
    "fx": [{"type": "dust", "amount": 0.2}],
}

if __name__ == "__main__":
    out = os.path.join(OUT, "eldergate.json")
    with open(out, "w", encoding="utf-8", newline="") as f:
        json.dump(scene, f, ensure_ascii=False, separators=(",", ":"))
    print("eldergate.json:", len(P), "pieces,", len(COL), "colliders,", len(EV), "events")

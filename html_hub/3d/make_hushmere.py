"""Builds html_hub/3d/hushmere.json: "Hushmere, the City That Smiles", Lethenia Chapter I (claude/lethenia-hushmere-oct-13.md).
Portal world #2.  Lethenia is a kingdom with no war in three hundred years; Hushmere is its capital.  Its peace is kept by the Stillheart, a device in the central tower
that suppresses grief, rage, envy and, more and more, doubt (outline: "Elarion"/"Elyndra", renamed Hushmere/Lethenia; the architect Aurelia Voss is Maren Aldwyn).
Chapter I, "A World That Smiles": the party steps out of the Eldergate gate into a garden outside the city, sees the child's glass ornament break and nobody mind,
is welcomed by attendants, meets Tavian, and is approached by the junior archivist Neris, whose mentor Corrow has vanished under the tower.  The Concordant of Care gives the
first hint of Kenji's irritation.  The lower stair leads to lowerhush.json (Chapter II, make_lowerhush.py).
Layout (x east, z south, the camera looks north):
  1. The Quiet Garden (z 58 .. 32): the gate-ring in the south, a child and parent, Attendant Sorrel, trees and benches.
  2. The Avenue (z 28 .. -50): white houses, the Guest House (inn), the Public Garden with Tavian, the Rest Pavilion, a memorial wall.
  3. The Concord Square (z -52 .. -100): the Archive (west, Neris), the Hall of Concord (east, the Concordant), the lower stair (far west), and the Stillheart Tower (north, sealed).
Flags: hs_arrive (arrival seen)  hs_welcome (an attendant has welcomed you)  hs_tavian  hs_neris (Neris has asked for help)  hs_official (the Concordant spoken to after)  hs_end (down the lower stair)  hsc1..hsc3 (chests)
Run:  python make_hushmere.py [outdir]   (needs kenhouse.py next to it; re-running overwrites hand edits made in /builder3d)"""
import json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kenhouse

KEN = kenhouse.KEN
GC, ST, PA, DG, GEN = ("/assets/3D/GodCity/", "/assets/3D/Stylized/", "/assets/3D/Paradise/", "/assets/3D/Dungeon/", "/assets/3D/Generated/")
S = kenhouse.S
MUSIC = "/assets/Music/mp3/"
rng = random.Random(8821)
T = kenhouse.Town(PA)
put, ken, block = T.put, T.ken, T.block
SAY = lambda who, text, **k: dict(type="say", who=who, text=text, **k)
ACT = lambda _ty, **k: dict(type=_ty, **k)
NPCS, EVENTS = [], []
BOUNDS = dict(minX=-37, maxX=37, minZ=-122, maxZ=60)
NERIS, TAVIAN, SEFA, CORROW, MERROW = "Neris", "Tavian", "Sefa", "Archivist Corrow", "Concordant Merrow"
PALE = [0.8, 0.9, 1.0, 0.4]
BLUE = [0.78, 0.9, 1.0, 1]                              # attendants and the Concordant (a washed, clean look)


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


def npc(id, name, title, sprite, x, z, actions=None, show=None, hide=None, h=2.4, reach=4.6, tint=None):
    n = dict(id=id, name=name, title=title, sprite=sprite, x=x, z=z, h=h, reach=reach)
    if actions: n["actions"] = actions
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


def chest(id, x, z, loot, show=None):
    put(GEN + "SM_TreasureChest", x, z, rng.randint(0, 359), 0, 1.0); block(x, z, 1.4, 1.4)
    event(id, "Treasure chest", x, z, [dict(type="flag", key=id), dict(type="chest", loot=loot, text="You open it and find")], "Open the chest", 3.4, 3.4, hide=id, show=show)


def lamp(x, z, r=8):
    put(ST + "SM_Stylized_Lamp_C", x, z, 0, 0, 1.1); block(x, z, 0.6, 0.6); glow(x, z, r, [0.85, 0.93, 1.0, 0.35])


def tree(x, z, sc=None):
    put(PA + "SM_tree_05", x, z, rng.randint(0, 359), 0, sc or rng.uniform(0.6, 0.85)); block(x, z, 1.4, 1.4)


def plant(x, z):
    put(PA + "SM_Plant_0%d" % rng.randint(1, 5), x, z, rng.randint(0, 359), 0, rng.uniform(0.9, 1.3))


# ------------------------------------------------------------------ ground
for gx in range(-2, 2):
    for gz in range(-7, 3):
        put(GC + "SM_ground_20x20", gx * 20 + 10, gz * 20 + 10, 0, -0.5, 1)
for k in range(220):                                   # grass and flowers everywhere, thicker in the garden and the Public Garden
    x, z = rng.uniform(-36, 36), rng.uniform(-120, 58)
    if abs(x) < 7 and -52 < z < 30: continue          # keep the avenue bare
    put(PA + "SM_grass_0%d" % rng.randint(1, 2), x, z, rng.randint(0, 359), 0, rng.uniform(3.4, 4.8))
for k in range(26):
    tree(rng.choice((-1, 1)) * rng.uniform(32, 36.5), rng.uniform(-118, 56))   # a soft ring of trees at the city edge

# ------------------------------------------------------------------ 1. the Quiet Garden (z 58 .. 32)
put(DG + "SM_dg_dais", 0, 54.0, 0, 0, 1.0); glyph(0, 54.0, 3.2, [0.78, 0.9, 1.0, 0.9], 20); glow(0, 54.0, 8, [0.8, 0.9, 1.0, 0.4])
for (x, z) in ((-14, 50), (14, 50), (-22, 42), (22, 42), (-12, 38), (12, 38), (-30, 52), (30, 52)):
    tree(x, z)
for k in range(30):
    plant(rng.uniform(-34, 34), rng.uniform(34, 58))
for (x, z, r) in ((-9, 44, 0), (9, 44, 0), (-6, 36, 90), (6, 36, 270)):
    put(ST + "SM_Stylized_Bench", x, z, r, 0, 1.0)
T.fence(-36, 32, -5, 32); T.fence(5, 32, 36, 32)       # the garden hedge/fence with a gate gap at x -5 .. 5
put(ST + "SM_Stylized_Arch", 0, 32.0, 0, 0, 1.4)
event("hs_ring", "The Eldergate ring", 0.0, 55.5, [
    SAY("", "The ring-stone you stepped out of hums softly and does not look like a door any more. It looks like a decorative paving circle, with benches around it."),
    SAY("", "A small brass plate is set into the rim. Cold, even lettering: SUBJECT ARRIVED. NO PRESSURE REQUIRED. OBSERVE."),
    SAY("Lyra", "He doesn't need to push here. This world pushes itself."),
    dict(type="choice", who="Kenji", text="Return to Eldergate?", options=[
        dict(label="Go back through the ring", actions=[ACT("fade", to="black", t=1.2), ACT("warp", scene="eldergate", x=13.2, z=-40.5, fresh=True)]),
        dict(label="Stay in Lethenia", actions=[ACT("end")])])],
    "Look at the ring", 5.0, 2.6)
npc("parent", "Parent", "Citizen", "Townee", -8.0, 40.0, tint=[1.0, 1.0, 1.0, 1], actions=[
    SAY("Parent", "Oh, travellers! You are so welcome. Hushmere is so happy to see you. Please, sit, please. Have you had enough to eat?", **{"unless": "hs_arrive"}),
    SAY("Parent", "It's a wonderful day. They're all wonderful days. I think the weather knows."),
    SAY("Parent", "Oh, that? A glass ornament. We have so many. It's quite all right.", **{"if": "hs_arrive"})])
npc("child", "Child", "Citizen", "Townee", -5.5, 40.0, h=1.7, actions=[
    SAY("Child", "I dropped something and it broke and Mama says it's all right so it's all right!"),
    SAY("", "The child is smiling. It is a very good smile. It has no corners.")])
npc("sorrel", "Attendant Sorrel", "Hushmere Attendant", "Shopkeeper", 2.0, 36.0, tint=BLUE, reach=5.0, actions=[
    SAY("Attendant Sorrel", "Welcome, welcome. You must be travellers. We see so few, and we are so glad of you. Food, lodging, medical care: everything is provided, and there is no cost. Please do not think of it as a cost.", **{"unless": "hs_welcome"}),
    SAY("Kenji", "No cost at all? To strangers?", **{"unless": "hs_welcome"}),
    SAY("Attendant Sorrel", "Why would anyone make a stranger feel they owe us? That would only make you unhappy. The Guest House is on the Avenue, to the west. The beds are very soft.", **{"unless": "hs_welcome"}),
    SAY("", "A small pale stone is set at the hollow of her throat on a thin chain, glowing faintly, like a coal that has forgotten how to burn. It brightens a little when she smiles.", **{"unless": "hs_welcome"}),
    ACT("flag", key="hs_welcome", **{"unless": "hs_welcome"}),
    SAY("Attendant Sorrel", "The Guest House is on the Avenue, to the west. The Public Garden is lovely at this hour. Please, anything at all.", **{"if": "hs_welcome"})])
ARRIVE = [
    ACT("cine", on=True),
    dict(type="music", url=MUSIC + "22. Ancient Library.mp3"),
    ACT("fade", to="clear", t=3.0, wait=False),
    ACT("cam", x=0, z=44, yaw=0, pitch=30, dist=24, t=0),
    SAY("", "The gate lets go of you gently. You are standing in a garden. Everything is green and white and clean, and very, very quiet; the kind of quiet that has been rehearsed."),
    SAY("Reya", "It's warm. I keep checking behind me. After the Road of Ash, I keep waiting for the price."),
    SAY("Miya", "Birds. There are birds. Do you hear them? Only they're all singing the same three notes."),
    SAY("", "Nearby, a child is carrying a glass ornament, a little blue sphere with a silver thread. It slips. It shatters on the path."),
    ACT("shake", t=0.4, amp=0.08),
    SAY("", "The child looks at the glittering pieces. There is no flinch. No sob. The mother kneels, smiles, and says: 'It's all right.' And the child, at once, smiles back."),
    SAY("Lyra", "Kenji. The child did not even start to cry. There was not even a beginning of it."),
    SAY("Kenji", "Maybe they're just calm people."),
    SAY("Lyra", "Maybe."),
    SAY("", "On the mother's throat, and the child's, and on the chests of every person passing along the avenue beyond the gate, a small pale stone glows softly."),
    ACT("flag", key="hs_arrive"),
    ACT("follow", t=1.2),
]

# ------------------------------------------------------------------ 2. the Avenue (z 28 .. -50)
for z in range(28, -52, -13):
    lamp(-7.5, z, 9); lamp(7.5, z, 9)
for (x, z, r) in ((-24, 20, 90), (-24, 2, 90), (-24, -14, 90), (24, 20, 270), (24, 2, 270), (24, -14, 270)):
    T.house(x, z, r, [(0, 0, 3, 2)], wall="stone", col="cream", roof="red")
    glow(x, z, 9, [0.9, 0.95, 1.0, 0.3])
for (x, z) in ((-30, 28), (30, 28), (-31, -2), (31, -2)):
    tree(x, z)
# the Guest House (inn) in the west of the Avenue
T.house(-26, -34, 90, [(0, 0, 4, 2)], wall="stone", col="cream", roof="red")
event("hs_inn", "The Guest House", -17.5, -34.0, [
    SAY("", "A soft room, a soft bed, a basin of warm water, and a tray of fruit someone has already set down. There is a small card on the pillow: 'WE HOPE YOU FEEL EXACTLY AS YOU SHOULD.'"),
    SAY("Reya", "Nobody asked what we wanted to feel."),
    dict(type="rest")], "Rest at the Guest House", 4.0, 3.0)
npc("wren", "Attendant Wren", "Hushmere Attendant", "Shopkeeper", -15.0, -30.0, tint=BLUE, actions=[
    SAY("Attendant Wren", "Is the room all right? Is it exactly what you wanted? If there is anything at all that is not as you wished, please say so. We would so like to correct it."),
    SAY("Attendant Wren", "Oh, you look a little unsettled. A moment in the Rest Pavilion would help. It is just there, across the Avenue. It takes only a breath.", **{"if": "hs_neris"})])
# the Rest Pavilion (east of the Avenue): a booth where citizens go when they feel too much
put(DG + "SM_dg_dais", 16.0, -4.0, 0, 0, 1.2); put(DG + "SM_dg_crystal", 16.0, -4.0, 0, 0.3, 1.3); block(16.0, -4.0, 2.8, 2.8); glow(16.0, -4.0, 9, [0.8, 0.92, 1.0, 0.55])
event("hs_pavilion", "The Rest Pavilion", 16.0, -1.2, [
    SAY("", "A pale crystal on a low dais, humming a single note. A sign in friendly lettering: 'FEELING UNSETTLED? A MOMENT IN THE REST PAVILION RESTORES BALANCE. NO RECORD IS KEPT.'"),
    SAY("", "A man steps up to it with a tight, working jaw. He presses his palm to the crystal. A breath later his shoulders drop. He smiles at no one, and walks away without looking back at what he came to forget."),
    SAY("Kenji", "He was upset. About something. And now he isn't, and doesn't know what."),
    SAY("Miya", "And it said 'no record is kept'. I don't think that means what they think it means.")], "Look at the pavilion", 5.0, 3.6)
chest("hsc1", -30.0, 6.0, dict(gold=4200, shards=56, items={"potion": 6, "ether": 5}))
# the Public Garden (east) with Tavian
for (x, z) in ((28, -30), (32, -36), (27, -44), (33, -46), (30, -26)):
    tree(x, z)
for k in range(30):
    plant(rng.uniform(22, 35), rng.uniform(-50, -24))
for (x, z, r) in ((24, -34, 270), (24, -42, 270), (30, -40, 0)):
    put(ST + "SM_Stylized_Bench", x, z, r, 0, 1.0)
npc("tavian", TAVIAN, "Public Garden volunteer", "Farmer", 26.0, -38.0, reach=5.0, actions=[
    SAY(TAVIAN, "Oh, hello! Are you new? Welcome, welcome. I'm Tavian. I tend this garden. Not as a job, no, just because it's nice to give something back.", **{"unless": "hs_tavian"}),
    SAY(TAVIAN, "I had a bad start in life. Bad enough that I won't tell you about it. And then the Stillheart came to my street and it was like someone opened a window in a room I had been shut in for years. I can't tell you what that is like.", **{"unless": "hs_tavian"}),
    SAY("Kenji", "The Stillheart.", **{"unless": "hs_tavian"}),
    SAY(TAVIAN, "The stone, the tower, all of it. It is a gift. I know people argue about it. They are usually the ones who haven't needed it.", **{"unless": "hs_tavian"}),
    SAY(TAVIAN, "My friend Neris does. She is an archivist, and a sweet person, but I worry about her. She looks tired. She feels things too hard, I think. I hope she comes to the Pavilion.", **{"unless": "hs_tavian"}),
    SAY(TAVIAN, "And my sister Sefa is away, resting. Two years now. She writes on the first of every month, such lovely letters. I keep them all.", **{"unless": "hs_tavian"}),
    ACT("flag", key="hs_tavian", **{"unless": "hs_tavian"}),
    SAY(TAVIAN, "The roses by the bench are Sefa's. She planted them before she went to rest. I water them every day. They have never once wilted.", **{"if": "hs_tavian"})])
event("hs_memorial", "A memorial wall", -16.0, -48.0, [
    SAY("", "A long white wall for 'the dead of the Long War, remembered with gratitude'. There are hundreds of small plaques, each with a smooth, blank oval where a name should be."),
    SAY("Reya", "There are no names."),
    SAY("", "An old man sits on the bench in front of it, smiling gently at the wall. He does not seem to be waiting for anything."),
    SAY("Kenji", "How do you remember people with no names?"),
    SAY("Lyra", "Gently. I imagine that's the idea.")], "Read the wall", 5.0, 3.0)
chest("hsc2", 35.0, -10.0, dict(gold=4400, shards=58, items={"potion": 5, "ether": 6, "antidote": 3}))

# ------------------------------------------------------------------ 3. the Concord Square (z -52 .. -100)
FZ = -66.0
put(ST + "SM_Stylized_Fountain", 0, FZ, 0, 0, 1.6); block(0, FZ, 6.6, 6.6); glow(0, FZ, 12, [0.85, 0.93, 1.0, 0.4])
for z in (-56.0, -78.0):
    lamp(-9.0, z, 9); lamp(9.0, z, 9)
T.house(-28, -78, 90, [(0, 0, 4, 2)], wall="stone", col="cream", roof="red")               # the Archive
T.house(28, -78, 270, [(0, 0, 4, 2)], wall="stone", col="cream", roof="red")               # the Hall of Concord
glow(-20, -78, 9, [1.0, 0.9, 0.7, 0.4])
for k in range(4):
    put(ST + "SM_Stylized_Bench", -6 + k * 4, -88.0, 0, 0, 1.0)
# the Stillheart Tower in the north
for h, sc in ((0, S * 3.0), ):
    pass
ken("tower-base", 0, -112.0, 0, 0, S * 3.0); ken("tower", 0, -112.0, 0, S * 3.0, S * 3.0); ken("tower-top", 0, -112.0, 0, S * 6.0, S * 3.0); block(0, -112.0, 8.4, 8.4)
glow(0, -112.0, 22, [0.75, 0.9, 1.0, 0.65]); glow(0, -104.0, 10, [0.9, 0.97, 1.0, 0.5]); glyph(0, -104.0, 4.0, [0.8, 0.92, 1.0, 0.9], 12)
event("hs_tower", "The Stillheart Tower", 0.0, -103.5, [
    SAY("", "A tall tower of white stone, wrapped in a faint pale light that pulses slowly, once for every two or three heartbeats of the city. A door at its foot is sealed with a smooth plate: 'ADMISSION BY APPOINTMENT OF THE CONCORD.'"),
    SAY("Lyra", "The mark on your hand is warm, Kenji. It is a different warmth to the Emberheart. It feels like something holding its breath."),
    SAY("Kenji", "It's listening."),
    SAY("", "Beneath the door plate, scratched coldly into the stone as if it had always been there: SUBJECT PRESENT. NO PRESSURE REQUIRED.")], "Look at the tower", 6.0, 3.6)
chest("hsc3", -34.0, -100.0, dict(gold=4600, shards=60, items={"potion": 6, "ether": 6, "antidote": 3}))
# the Archive and Neris
npc("neris", NERIS, "Junior Archivist", "Townee", -19.0, -78.0, tint=[0.85, 0.75, 1.0, 1], reach=5.0, hide="hs_end", actions=[
    SAY(NERIS, "Not here. Please. Come down to the lower stair when you are ready, west of the square. We can speak where the stones don't listen.", **{"if": "hs_neris", "unless": "hs_official"}),
    SAY(NERIS, "You spoke to the Concordant. Good. Now you know what it sounds like when a smile is a locked door. The lower stair, west of the square. I will meet you there.", **{"if": "hs_official", "unless": "hs_end"}),
    SAY(NERIS, "The archive is open to all citizens, and nobody comes. They don't need to. Is there anything you would like to forget?", **{"unless": "hs_neris"})])
NERIS_CS = [
    ACT("cine", on=True),
    ACT("cam", x=-14, z=-76, yaw=0, pitch=26, dist=20, t=1.6),
    SAY("", "A young woman steps out from between two pillars of the Archive and looks over her shoulder before she speaks, and then again. She wears the pale stone at her collar, but it is dim, and she holds her hand over it as though to keep it warm. Or to hide it."),
    SAY(NERIS, "You have a mark. On your right hand. It was glowing when you crossed the square. I'm sorry. Don't look at it. People look."),
    SAY("Kenji", "You can see it?"),
    SAY(NERIS, "I see a lot of things people don't. It's... a fault in me. I'm Neris. I work in the Archive. And I have a question I can't ask anyone else."),
    SAY(NERIS, "Do you remember everything that makes you unhappy?"),
    SAY("Kenji", "Is that a joke?"),
    SAY(NERIS, "I wish it were. The tower in the middle of the city can alter memories. I've seen it. I've seen the records, and the records have been edited. There are people listed as married to strangers. Years missing from lives. Whole events that nobody remembers, because nobody is allowed to."),
    SAY(NERIS, "My mentor, Archivist Corrow, found something beneath the tower. Three weeks ago he failed to open the Archive. His desk was cleared by morning. His name is not in the register. Nobody here thinks anything of it. They say he has been 'receiving care'."),
    SAY("Miya", "Has anyone looked for him?"),
    SAY(NERIS, "I asked the Concordant of Care. She smiled and said all citizens in care are receiving appropriate care. That is not a sentence with an answer in it."),
    SAY("Kenji", "A man is missing, and nobody else is bothered. That's enough for me. We'll help."),
    SAY(NERIS, "You will? Just like that? You don't know me."),
    SAY("Kenji", "I know the look of a person who's the only one saying it out loud."),
    SAY("Reya", "He does this. Stand back, it's catching."),
    SAY(NERIS, "Then talk to the Concordant. The Hall is east of the square. She will tell you everything is fine. Listen to how she says it. Then come to the lower stair, west of the square. I'll be there."),
    ACT("flag", key="hs_neris"),
    ACT("follow", t=1.2),
]
event("hs_neris_cs", "Neris", -8.0, -76.0, NERIS_CS, "", 16.0, 3.0, show="hs_welcome", hide="hs_neris", trigger="touch", once=True)
event("hs_archive", "The Archive records", -23.0, -70.0, [
    SAY("", "Shelves of public records, row after row, tidy and bright. You open a register at random. A woman is listed as the wife of a man who was, three pages earlier, married to someone else. Both marriages are described as long and happy."),
    SAY("Lyra", "These aren't records. They're a story somebody keeps tidying.")], "Look through the records", 4.0, 3.0, show="hs_neris")
# the Hall of Concord and the Concordant of Care
npc("merrow", MERROW, "Concordant of Care", "Mayor", 20.0, -78.0, tint=BLUE, h=2.9, reach=5.0, hide="hs_end", actions=[
    SAY(MERROW, "Welcome to the Hall of Concord. We are so glad you are well. Is there anything at all the city can provide?", **{"unless": "hs_neris"}),
    SAY(MERROW, "Ah. The archivist. She is a dear, a little over-tender. Her mentor? Archivist Corrow is receiving care, as all our citizens do when they find they cannot be at ease. I assure you he is very comfortable.", **{"if": "hs_neris", "unless": "hs_official"}),
    SAY("Kenji", "Did anyone actually ask him what he wanted?", **{"if": "hs_neris", "unless": "hs_official"}),
    SAY(MERROW, "Of course. His preferences were carefully considered.", **{"if": "hs_neris", "unless": "hs_official"}),
    SAY("", "Kenji looks at Neris's empty place by the pillars, then back at the Concordant. His voice stays level.", **{"if": "hs_neris", "unless": "hs_official"}),
    SAY("Kenji", "That's not what I asked.", **{"if": "hs_neris", "unless": "hs_official"}),
    SAY(MERROW, "I'm afraid I don't understand the question. But I do see you are a little unsettled. The Rest Pavilion is just across the Avenue. A single breath. It would be my pleasure to walk you there.", **{"if": "hs_neris", "unless": "hs_official"}),
    SAY("Miya", "Kenji. Smile. Don't take the walk.", **{"if": "hs_neris", "unless": "hs_official"}),
    SAY("Kenji", "No, thank you. I'm precisely as unsettled as I ought to be.", **{"if": "hs_neris", "unless": "hs_official"}),
    ACT("flag", key="hs_official", **{"if": "hs_neris", "unless": "hs_official"}),
    SAY(MERROW, "Of course. Whatever feels right for you. Please, anything at all.", **{"if": "hs_official"})])
# the lower stair (far west): the way into Chapter II
put(DG + "SM_dg_dais", -32.0, -92.0, 0, 0, 1.0); put(DG + "SM_dg_dais", -32.0, -95.0, 0, 0, 0.7); glow(-32.0, -92.0, 8, [0.6, 0.65, 0.8, 0.5])
event("hs_stair", "The lower stair", -31.0, -90.0, [
    SAY("", "A plain stone stair in the far west corner of the square, leading down below the white streets. A smooth plate over the arch says: 'NO ONE NEED GO DOWN.' It is the only sign in Hushmere that doesn't say please."),
    dict(type="choice", who="Kenji", text="Go down to meet Neris?", options=[
        dict(label="Go down", actions=[
            SAY(NERIS, "You came. Good. Quietly. Follow me, and don't be surprised by anything you see. They've stopped being able to be surprised.", **{"unless": "hs_end"}),
            SAY("Kenji", "Lead the way.", **{"unless": "hs_end"}),
            ACT("flag", key="hs_end"),
            ACT("fade", to="black", t=1.2),
            ACT("title", text="The Lower Districts", sub="The Happiness Protocol", t=3.0),
            ACT("warp", scene="lowerhush", x=0.0, z=52.0, fresh=True)]),
        dict(label="Not yet", actions=[ACT("end")])])],
    "Look down the stair", 5.0, 3.0, show="hs_official")

OBJECTIVES = [
    {"unless": "hs_welcome", "text": "Leave the Quiet Garden and talk to the attendant, Sorrel."},
    {"unless": "hs_neris", "text": "Explore Hushmere. Cross the Avenue to the Concord Square, where an archivist is waiting."},
    {"unless": "hs_official", "text": "Speak to the Concordant of Care in the Hall of Concord, east of the square."},
    {"unless": "hs_end", "text": "Meet Neris at the lower stair, in the west corner of the square."},
    {"text": "Chapter II continues in the Lower Districts, down the stair in the west corner of the square."},
]

scene = {
    "story": True, "name": "Hushmere", "kit": "", "tile": 4,
    "autorun": [dict(unless="hs_arrive", cine=True, actions=ARRIVE)], "objectives": OBJECTIVES,
    "music": {"url": MUSIC + "22. Ancient Library.mp3"},
    "pieces": T.P, "colliders": T.COL, "decals": T.DEC, "npcs": NPCS, "events": EVENTS,
    "spawn": {"x": 0, "z": 50}, "bounds": BOUNDS, "playerHeight": 2.4,
    "camera": {"pitch": 24, "dist": 30},
    "light": {"dir": [-0.4, -1, -0.3], "color": [1.0, 0.98, 0.92], "ambient": [0.6, 0.62, 0.68]},
    "fog": {"color": [0.86, 0.92, 0.98], "near": 60, "far": 190},
    "sky": {"type": "layers", "base": {"type": "gradient", "stops": [[0, "#6fa8e8"], [0.5, "#cfe6f7"], [1, "#fff6e0"]]}, "layers": []},
    "fx": [],
}

if __name__ == "__main__":
    out = os.path.join(sys.argv[1] if len(sys.argv) > 1 else HERE, "hushmere.json")
    with open(out, "w", encoding="utf-8", newline="") as f:
        json.dump(scene, f, ensure_ascii=False, separators=(",", ":"))
    print("hushmere.json:", len(T.P), "pieces,", len(T.COL), "colliders,", len(NPCS), "npcs,", len(EVENTS), "events")

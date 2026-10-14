"""Builds html_hub/3d/lowerhush.json: "The Lower Districts", Lethenia Chapter II "The Happiness Protocol" (claude/lethenia-lowerhush-oct-13.md).
Continues make_hushmere.py: Neris leads the party down the lower stair and joins them (placeholder art).  Hushmere quietly relocates the people who resist memory correction here.
Layout (x east, z south, the camera looks north):
  1. The Landing and the Quiet Rows (z 58 .. -10): the way back up, rows of identical small houses, relocated citizens, a calming station.
  2. Mender's Row (z -12 .. -52): a bench plaza.  Oriel, searching for her son Davin, is calmed by an attendant and forgets; later Kenji finds her smiling at nothing and must decide what to do (the chapter's moral centre).
  3. The Sealed Annex (z -54 .. -100): an old records hall, opened by Neris's key once the choice is made, guarded by the Correction Warden at its far door.
  4. The Archive Facility (z -102 .. -134): racks of stored memories, Archivist Corrow in his cell, and the Correction Rolls (the proof that the Stillheart erases dissent).
Flags: lh_arrive (arrival; Neris joins)  lh_woman (Oriel's scene seen)  lh_choice (decision made) + lh_w1 (told her) / lh_w2 (left her be) / lh_w3 (searching for Davin)  lh_warden  lh_corrow  lh_ledger  lh_end  lhc1..lhc3 (chests)
Run:  python make_lowerhush.py [outdir]   (needs kenhouse.py next to it; re-running overwrites hand edits made in /builder3d)"""
import json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kenhouse

KEN = kenhouse.KEN
GC, ST, PA, DG, GEN = ("/assets/3D/GodCity/", "/assets/3D/Stylized/", "/assets/3D/Paradise/", "/assets/3D/Dungeon/", "/assets/3D/Generated/")
S = kenhouse.S
MUSIC = "/assets/Music/mp3/"
rng = random.Random(9931)
T = kenhouse.Town(PA)
put, ken, block = T.put, T.ken, T.block
SAY = lambda who, text, **k: dict(type="say", who=who, text=text, **k)
ACT = lambda _ty, **k: dict(type=_ty, **k)
NPCS, EVENTS = [], []
BOUNDS = dict(minX=-33, maxX=33, minZ=-134, maxZ=60)
NERIS, TAVIAN, SEFA, CORROW, MERROW, ORIEL, DAVIN = "Neris", "Tavian", "Sefa", "Corrow", "Concordant Merrow", "Oriel", "Davin"
BLUE = [0.78, 0.9, 1.0, 1]


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


def lamp(x, z, r=7):
    put(ST + "SM_Stylized_Lamp_C", x, z, 0, 0, 1.0); block(x, z, 0.6, 0.6); glow(x, z, r, [0.75, 0.85, 1.0, 0.3])


def hwall(x0, x1, z, gap=None):
    n = int((x1 - x0) / S) + 1
    for i in range(n + 1):
        x = x0 + i * S
        if x > x1 + 0.01: break
        if gap and gap[0] < x < gap[1]: continue
        ken("wall-fortified", x, z, 0, 0, S); block(x, z, S, 1.0)


def vwall(x, z0, z1):
    n = int(abs(z1 - z0) / S) + 1
    for i in range(n + 1):
        z = z0 - i * S
        if z < z1 - 0.01: break
        ken("wall-fortified", x, z, 90, 0, S); block(x, z, 1.0, S)


def crosswall(z, flag, half=33.0):
    """A full-width wall at z with a 10 m opening in the middle, closed by a gate while `flag` is not set."""
    for k in range(2, 14):
        for sgn in (-1, 1):
            x = sgn * (k * S - S * 0.0)
            if abs(x) < 5.0 or abs(x) > half + 0.5: continue
            ken("wall-fortified", x, z, 0, 0, S); block(x, z, S, 1.0)
    ken("wall-fortified-gate", -2.0, z, 0, 0, S * 0.6, flag); ken("wall-fortified-gate", 2.0, z, 0, 0, S * 0.6, flag)
    T.COL.append(dict(x=0.0, z=z, w=9.0, d=1.4, hideIf=flag))


# ------------------------------------------------------------------ ground, walls, light
for gx in range(-2, 2):
    for gz in range(-7, 3):
        put(GC + "SM_ground_20x20", gx * 20 + 10, gz * 20 + 10, 0, -0.5, 1)
vwall(-31.0, 58.0, -134.0); vwall(31.0, 58.0, -134.0)
hwall(-31.0, 31.0, 59.0); hwall(-31.0, 31.0, -135.0)
for i in range(70):
    z = rng.uniform(-142, 66)
    put(ST + "SM_Cliff_0%d" % rng.randint(1, 2), rng.choice((-1, 1)) * rng.uniform(36, 46), z, rng.randint(0, 359), -0.2, rng.uniform(1.3, 2.2))

# ------------------------------------------------------------------ 1. the Landing and the Quiet Rows (z 58 .. -10)
put(DG + "SM_dg_dais", 0, 55.5, 0, 0, 1.0); glyph(0, 55.5, 3.0, [0.7, 0.8, 1.0, 0.8], 15); glow(0, 55.5, 8, [0.7, 0.8, 1.0, 0.4])
event("lh_up", "The stair up", 0.0, 57.4, [
    SAY("", "A stone stair climbs back to the white streets of Hushmere. The light up there is warmer than the light down here. It is also the light that put you down here."),
    dict(type="choice", who="Kenji", text="Climb back up to Hushmere?", options=[
        dict(label="Go back up", actions=[ACT("fade", to="black", t=1.0), ACT("warp", scene="hushmere", x=-28.0, z=-88.0, fresh=True)]),
        dict(label="Stay below", actions=[ACT("end")])])],
    "Look up the stair", 5.0, 2.4)
for z in range(44, -12, -14):
    lamp(-9.0, z); lamp(9.0, z)
for (x, z, r) in ((-22, 40, 90), (-22, 26, 90), (-22, 12, 90), (-22, -2, 90), (22, 40, 270), (22, 26, 270), (22, 12, 270), (22, -2, 270)):
    T.house(x, z, r, [(0, 0, 2, 1)], wall="stone", col="cream", roof="red")
    glow(x, z, 6, [0.7, 0.8, 1.0, 0.2])
put(ST + "SM_Stylized_WantedBoard", -8.0, 50.0, 0, 0, 1.2); block(-8.0, 50.0, 2.0, 1.0)
event("lh_notice", "A relocation notice", -8.0, 48.0, [
    SAY("", "THE LOWER DISTRICTS: A QUIET PLACE TO REST. THE CITY IS GRATEFUL FOR YOUR TIME OF REST. THERE IS NO NEED TO RETURN."),
    SAY("Reya", "'There is no need to return.' That's what the Hollow's evacuation ledger said."),
    SAY("Kenji", "Same sentence. Different country.")], "Read the notice", 3.6, 2.6)
npc("painter", "Painter", "Relocated citizen", "Farmer", 14.0, 30.0, actions=[
    SAY("Painter", "This is my door. It was blue. I painted it red this morning, because red is cheerful. Oh, it's blue again. Somebody must have repainted it. How kind."),
    SAY("", "The painter holds a pot of red paint. His door is already red. It is, in fact, the only red door in the row.")])
npc("sweeper", "Sweeper", "Relocated citizen", "Townee", -14.0, 18.0, actions=[
    SAY("Sweeper", "I sweep the Rows every morning. I like it. It is so quiet, and no one needs me for anything else."),
    SAY("Sweeper", "Did I have a family? I think there was a family. It isn't important. Everyone here is so kind.")])
npc("calm_stn", "Attendant", "Calming attendant", "Shopkeeper", 12.0, 4.0, tint=BLUE, actions=[
    SAY("Attendant", "If you feel the slightest unease, anything at all, just say. The wand takes only a breath. No record is kept."),
    SAY("Miya", "Everyone keeps saying that. 'No record is kept.' I'd like to see the record.")])
chest("lhc1", -28.0, 54.0, dict(gold=5000, shards=66, items={"potion": 6, "ether": 6, "antidote": 3}))

# ------------------------------------------------------------------ 2. Mender's Row (z -12 .. -52)
FZ = -32.0
put(ST + "SM_Stylized_Fountain", 0, FZ, 0, 0, 1.4); block(0, FZ, 5.8, 5.8)
for k in range(5):
    a = k * math.tau / 5 + 0.3
    put(ST + "SM_Stylized_Bench", 8.6 * math.cos(a), FZ + 8.6 * math.sin(a), math.degrees(a) + 90, 0, 1.0)
for z in (-18.0, -46.0):
    lamp(-12.0, z); lamp(12.0, z)
npc("attendant_o", "Attendant", "Calming attendant", "Shopkeeper", 11.0, -22.0, tint=BLUE, actions=[
    SAY("Attendant", "Oriel is a dear. She does get so worked up. We do what we can for her every day. Isn't it good that there's something we can do?")])
ORIEL_CS = [
    ACT("cine", on=True),
    ACT("cam", x=0, z=-24, yaw=0, pitch=26, dist=24, t=1.8),
    SAY("", "A woman in a plain grey dress comes running across the plaza the moment she sees you. She is not smiling. It is the first face you have seen in two days that isn't."),
    SAY(ORIEL, "You're travellers. The attendant at the garden said there were travellers. Please. My son, Davin. He is eight. He went to the Hall of Concord on the first of the month to take a petition, a paper, only a paper, and he never came home."),
    SAY(ORIEL, "They say he is in care. Which care? I have asked every attendant in the Rows. Nobody will say which, or what for. He has a cough, he sleeps with a light on, he hates the dark and they keep sending me down to the dark to be calm, please, please, can you find him?"),
    SAY("Reya", "...Kenji."),
    SAY("Kenji", "We will. Tell me everything you remember about..."),
    SAY("", "The attendant has crossed the plaza without hurrying. A gentle hand rests on Oriel's shoulder; in the other, a slender wand with a pale crystal at the tip."),
    SAY("Attendant", "Oriel, you're distressed. It's all right. A moment. A single breath."),
    SAY(ORIEL, "No, please, I'm in the middle of... I am so sorry. I'm so sorry, I'm causing a disturbance. I'm..."),
    ACT("flash"),
    SAY("", "The crystal brushes the stone at her throat. It brightens. Her shoulders drop, her face smooths, and the tears on her cheeks are the only thing in the plaza that still look like what they were."),
    SAY(ORIEL, "...Oh. What was I saying? What a lovely day it is."),
    SAY("Attendant", "Beautiful. Come and sit. You're doing so well."),
    SAY("Reya", "I'm going to take that wand and..."),
    SAY("Kenji", "No. Not here. Not yet. Look at her face."),
    SAY(NERIS, "Three months. Every morning she finds a new traveller and asks. Every morning she forgets, and in the evening she asks someone else."),
    SAY("Kenji", "Then somebody should do something about it. I'm going to speak to her. After."),
    ACT("flag", key="lh_woman"),
    ACT("follow", t=1.2),
]
event("lh_oriel_cs", "Oriel", 0.0, -14.0, ORIEL_CS, "", 40.0, 4.0, show="lh_arrive", hide="lh_woman", trigger="touch", once=True)

def oriel_choice():
    return [
        dict(label="\"Your son is called Davin. You asked us to find him.\"", actions=[
            SAY("Kenji", "You told us about your son this morning. His name is Davin. He is eight. He sleeps with the light on."),
            SAY("", "For a moment, nothing. Then something moves in her face like a fish under ice, and her eyes fill. The stone at her throat throbs, bright, twice."),
            SAY(ORIEL, "Davin... I..."),
            SAY("", "The tears stop. She wipes her cheeks with the back of her hand, puzzled, as though someone else had made her cry, and her smile comes back like a door being closed."),
            SAY(ORIEL, "How strange. I am so sorry. I don't know why I did that."),
            SAY(NERIS, "That is what you have just seen. Not a woman who doesn't care. A woman who cares and is stopped."),
            SAY("Kenji", "She remembered. For a second. I saw it."),
            SAY(NERIS, "Yes. And now you know what it costs her every time. I'm not telling you not to. I'm telling you to know."),
            ACT("flag", key="lh_w1"), ACT("flag", key="lh_choice")]),
        dict(label="\"Tell me you're all right, then. Then I'll leave you alone.\"", actions=[
            SAY("Kenji", "You don't have to tell me anything. I wanted to be sure you were being looked after."),
            SAY(ORIEL, "I am so well looked after. Everyone is so kind. I don't think I've ever been so content."),
            SAY("Kenji", "...Good."),
            SAY(NERIS, "You hate that, don't you."),
            SAY("Kenji", "I hate it. She said it, and I believe that she means it, and I still hate it. I can't tell whether that makes it a lie."),
            SAY(NERIS, "Or whether it makes you the cruel one. That is the question I couldn't answer either. I'm glad you're asking it."),
            SAY("Miya", "Whatever is in that stone, it is a good deal gentler than the thing that made her need it."),
            ACT("flag", key="lh_w2"), ACT("flag", key="lh_choice")]),
        dict(label="\"Where would Davin be? Neris, can the Archive tell us?\"", actions=[
            SAY("Kenji", "Neris. If a boy of eight is taken into care, there's a list. There's always a list."),
            SAY(NERIS, "There is. Intake rolls, in the old Records Annex, under the tower. They're sealed to the public. I have a key I shouldn't."),
            SAY("Kenji", "Then she gets her son's name back from the list, and not from me. I won't take away her peace for a minute of grief. I'll find him, and then she can choose what to do."),
            SAY(ORIEL, "Are you talking about me? How kind you all are."),
            SAY("Reya", "I'd like to say I'm coming. I'm coming."),
            ACT("flag", key="lh_w3"), ACT("flag", key="lh_choice")]),
    ]

npc("oriel", ORIEL, "Relocated citizen", "Townee", -11.0, -44.0, show="lh_woman", h=2.2, reach=5.0, actions=[
    SAY("", "Oriel sits on the bench beside the fountain, hands folded in her lap, smiling at nothing in particular. The smile is a good one. It has no corners.", **{"unless": "lh_choice"}),
    SAY(ORIEL, "Oh, hello! Are you travellers? Welcome, welcome. It's such a lovely day. I'm so content here. They look after us so well.", **{"unless": "lh_choice"}),
    SAY("Kenji", "...She doesn't know us.", **{"unless": "lh_choice"}),
    SAY(NERIS, "She never does. She has asked every new face for months, and she has thanked the Concord each time they erase it.", **{"unless": "lh_choice"}),
    SAY("Kenji", "She's thanking them. She means it. I can see she means it.", **{"unless": "lh_choice"}),
    SAY(NERIS, "That is the whole trouble, Kenji. The person who is choosing is not the person who was hurt. The stone has been editing the chooser.", **{"unless": "lh_choice"}),
    dict(type="choice", who="Kenji", text="What do you do for Oriel?", **{"unless": "lh_choice"}, options=oriel_choice()),
    SAY(ORIEL, "It's such a lovely day. Are you travellers? Welcome.", **{"if": "lh_choice"}),
    SAY(ORIEL, "My son? Oh... did I have a son? I think I may have had a son. I am sure he is happy.", **{"if": "lh_w3"})])
event("lh_key", "Neris's key", 0.0, -52.0, [
    SAY(NERIS, "The old Records Annex is through the iron doors ahead. Every intake of the last twenty years is kept there, and the Concord has forgotten it's there, because the Concord forgets what it likes."),
    SAY(NERIS, "I'll warn you: there are things in the Annex the tower keeps to keep us quiet. They won't be gentle."),
    SAY("", "A heavy key hangs from Neris's belt. It turns in the lock without a sound, as if oiled for this."),
    ], "Look at the doors", 8.0, 3.0, show="lh_choice")
chest("lhc2", 28.0, -50.0, dict(gold=5200, shards=68, items={"potion": 6, "ether": 6, "antidote": 3}))

# ------------------------------------------------------------------ 3. the Sealed Annex (z -54 .. -100)
crosswall(-54.0, "lh_choice")
for (x, z) in [(sx, z) for sx in (-20, -8, 8, 20) for z in (-62, -76, -90)]:
    put(DG + "SM_dg_pillar", x, z, 0, 0, 1.1); block(x, z, 1.4, 1.4); glow(x, z, 6, [0.75, 0.85, 1.0, 0.35])
for (x, z) in ((-26, -66), (26, -66), (-26, -84), (26, -84)):
    put(ST + "SM_Stylized_Table_A", x, z, 90, 0, 1.2); block(x, z, 1.4, 2.8)
event("lh_roll", "The intake rolls", -26.0, -68.5, [
    SAY("", "A great ledger on a reading stand: CONCORD INTAKE, LOWER DISTRICTS. Dates down the left, names, ages, and a short column of reasons in cold, even letters: FEELS TOO MUCH. REFUSES COMFORT. ASKS QUESTIONS. PETITIONED FOR MOURNING LEAVE."),
    SAY("Reya", "'Petitioned for mourning leave.' That's a reason."),
    SAY(NERIS, "It's the reason, in nineteen cases out of twenty. Grief that doesn't end when it should is classed as destabilising. Then it's corrected, and then it's 'resolved'."),
    SAY("", "Under today's date, in the child column: DAVIN, AGE 8. REASON: PETITIONED FOR HIS MOTHER. DISPOSITION: ARCHIVE FACILITY, LEVEL 2.", **{"if": "lh_w3"})], "Read the roll", 4.0, 3.0, show="lh_choice")
chest("lhc3", -28.0, -96.0, dict(gold=5400, shards=70, items={"potion": 6, "ether": 7, "antidote": 3}))
glow(0, -78, 40, [0.78, 0.88, 1.0, 0.25])

# ------------------------------------------------------------------ 4. the Archive Facility (z -102 .. -134)
crosswall(-100.0, "lh_warden")
npc("warden", "Correction Warden", "Keeper of the Annex door", "Draven", 0.0, -96.5, tint=[0.62, 0.78, 1.2, 1], h=3.0, reach=5.0, hide="lh_warden", actions=[
    SAY("Correction Warden", "THIS AREA IS CLOSED. YOU ARE TIRED. YOU WOULD LIKE TO REST. THE PAVILION IS ABOVE."),
    SAY(NERIS, "Lower your voice. It's a construct. The Concord wound it years ago and never checked what it learned."),
    SAY("Kenji", "We're not tired. Stand aside."),
    SAY("Correction Warden", "THE TIRED CANNOT BE TRUSTED WITH THEIR OWN DECISIONS. ASSISTANCE WILL BE PROVIDED."),
    dict(type="battle", key="lh_warden", pool=["shard_sentry", "lattice_medic"], level_rel=[2, 4], elite=1.7)])
for k in range(8):                                    # racks of stored memory: pale crystals on low plinths
    for sgn in (-1, 1):
        x, z = sgn * 22.0, -106.0 - k * 3.4
        put(DG + "SM_dg_crystal", x, z, rng.randint(0, 359), 0, 1.0); block(x, z, 1.2, 1.2); glow(x, z, 4, [0.75, 0.88, 1.0, 0.45])
event("lh_crystals", "A rack of memory crystals", -20.5, -114.0, [
    SAY("", "A rack of pale crystals, each the size of a fist, each humming a different very faint voice. You hold one near your ear."),
    SAY("", "A woman's voice: 'Davin, come home for supper. Davin, the light is on.'", **{"if": "lh_woman"}),
    SAY("", "A man laughs, and keeps laughing, and keeps laughing, the same peal of laughter again and again with no joy in it."),
    SAY("Miya", "These are people's memories. They took them out and kept them."),
    SAY(NERIS, "Kept. Not destroyed. That's the part I can't forgive them for. Every one of these could be given back.")], "Listen to the crystals", 4.0, 3.0, show="lh_warden")
event("lh_davin", "A small crystal", 20.5, -128.0, [
    SAY("", "One crystal is set apart on a velvet cloth, smaller than the others and labelled in a child's block letters: DAVIN. MY LIGHT STAYS ON."),
    SAY("", "When you hold it, a small voice says: 'Mama, can I have the light on? Just the small one.' Then, in a different tone, patient: 'It is for the best, young man. The small light is off.'", **{"if": "lh_woman"}),
    SAY("Kenji", "He's here. Or part of him is."),
    SAY(NERIS, "Not only his memories. His disposition says he's in the facility. We have to find him, or find where he was moved."),
    SAY("Reya", "...He asked for a light. For a light. And they didn't."),
    ACT("flag", key="lh_davin")], "Take the crystal", 4.0, 3.0, show="lh_warden", hide="lh_davin")
npc("corrow", CORROW, "Archivist, Mentor of Neris", "Elder", -2.0, -125.0, tint=[0.9, 0.92, 1.0, 1], reach=5.0, show="lh_warden", actions=[
    SAY("", "An elderly man sits in a cell without a door, ink on his fingers and a quill in his hand. He is writing on the air, in short, patient strokes, as if the page were still there.", **{"unless": "lh_corrow"}),
    SAY(CORROW, "Neris? ...You've grown. You've been crying. Whose fault is that, I wonder. Did I teach you to cry? I don't think I did.", **{"unless": "lh_corrow"}),
    SAY(NERIS, "Archivist! You're alive. They said you were receiving care. I looked for you for three weeks.", **{"unless": "lh_corrow"}),
    SAY(CORROW, "Three weeks. Is that all? It has felt longer. I'm told I've had a rather pleasant time. I find I don't believe them. I think I know a lie when I've been told one very gently.", **{"unless": "lh_corrow"}),
    SAY(CORROW, "I found a thing in the Archive. A ledger. I read it three times, to be sure, and then they came with the wand, and I was very calm, and I forgot every word. But I wrote the first line on my sleeve before I forgot. See?", **{"unless": "lh_corrow"}),
    SAY("", "He pulls back a frayed cuff. In ink, in a trembling hand: 'THE ROLLS ARE NOT MEDICAL. LOOK AT WHO IS ON THEM.'", **{"unless": "lh_corrow"}),
    SAY(CORROW, "I've no idea what it means, Neris. But I wrote it for you. The desk behind me. The Correction Rolls. I'm sorry I can't give you more.", **{"unless": "lh_corrow"}),
    SAY("Kenji", "We'll get you out.", **{"unless": "lh_corrow"}),
    SAY(CORROW, "I'd rather you didn't. Leave me where they think I am. A missing man is a story; a returning man is a warning. Read the desk. Then go home, and be careful of kind people.", **{"unless": "lh_corrow"}),
    ACT("flag", key="lh_corrow", **{"unless": "lh_corrow"}),
    SAY(CORROW, "The desk. Read the desk, Neris.", **{"if": "lh_corrow", "unless": "lh_ledger"}),
    SAY(CORROW, "Go on. I'll write you a letter. I shall not remember writing it, so it will be honest.", **{"if": "lh_ledger"})])
event("lh_rolls", "The Correction Rolls", 4.0, -126.0, [
    SAY("", "A desk, a lamp, a single heavy ledger bound in grey. Its cover reads: CORRECTION ROLLS, THE STILLHEART. Each page lists a name, a date, and a 'level'."),
    SAY(NERIS, "Level one: comfort. Level two: suppression. Level three: ...redirection. I've never seen that word. What are they redirecting?"),
    SAY("", "Under the headings, in the margin, the notes are short and political. PETITIONED THE CONCORD FOR AN OPEN VOTE. ORGANISED A GATHERING. WROTE A PAMPHLET ON THE LONG WAR. SPOKE AT THE GRAVES. ALL: LEVEL THREE."),
    SAY("Miya", "These aren't the grieving. These are the people who spoke."),
    SAY(NERIS, "Here. A name I know. Sefa. ...SEFA, ORGANISER OF THE PUBLIC GARDEN PETITION. LEVEL THREE. DISPOSITION: RESTING."),
    SAY(NERIS, "Tavian's sister. 'Resting.' Tavian told us she writes every month. He kept the letters."),
    SAY("Kenji", "He told us she was resting, and he believed it. Neris, I don't think those letters are hers."),
    SAY(NERIS, "I don't either.", ),
    SAY("", "On the last page, in cold, even lettering, scratched into the paper as though it had always been there: SUBJECT PRESENT. OBSERVE CHOICE."),
    SAY("Lyra", "He's reading over our shoulder. He's here, one way or another."),
    SAY("Kenji", "Then he can read this too: the Stillheart is not a medicine. It's a muzzle."),
    ACT("flag", key="lh_ledger")], "Read the Rolls", 4.0, 3.0, show="lh_corrow", hide="lh_ledger")
event("lh_leave", "The way up", 0.0, -131.0, [
    SAY(NERIS, "We have what we came for, and more than I wanted. Corrow's right: if we take him, they'll know we found it. Let me think about who to tell. Not the Concord. Not the tower."),
    SAY(NERIS, "There are people who have started to ask questions: quietly, in the old Hall of Songs. I think it's time you met them."),
    SAY("Kenji", "Then lead on. And Neris... thank you for showing me this."),
    ACT("flag", key="lh_end"),
    ACT("fade", to="black", t=1.2),
    ACT("title", text="The Hall of Songs", sub="The People Who Chose This", t=3.0),
    ACT("warp", scene="songhall", x=0.0, z=52.0, fresh=True)],
    "Leave the facility", 5.0, 3.0, show="lh_ledger")
put(DG + "SM_dg_dais", 0, -131.0, 0, 0, 1.0); glyph(0, -131.0, 3.0, [0.7, 0.85, 1.0, 0.8], 15)

# ------------------------------------------------------------------ arrival
ARRIVE = [
    ACT("cine", on=True),
    dict(type="music", url=MUSIC + "22. Ancient Library.mp3"),
    ACT("fade", to="clear", t=2.0, wait=False),
    ACT("cam", x=0, z=48, yaw=0, pitch=34, dist=22, t=0),
    SAY("", "The stair opens onto a grey landing. The light down here is the same white as above, only thinner, and nothing in it is quite as warm. The air smells of clean cloth."),
    SAY(NERIS, "Welcome to the Lower Districts. They call it the Rest. Nobody who is sent here is told why, because nobody who is sent here remembers being sent."),
    SAY("Kenji", "You've been down here before."),
    SAY(NERIS, "Eleven times. Looking for him. I never found him. I found a lot of other people."),
    SAY("Reya", "She's good at this. She hasn't once looked back for the guard."),
    SAY(NERIS, "I stopped looking back. It doesn't help. The thing that watches here isn't behind you."),
    SAY("Kenji", "Neris. Come with us. Properly. Not just to show the way. You see things the rest of us can't, and I'd rather you were beside me than behind a door."),
    SAY(NERIS, "...Nobody's ever asked me to come before. Everyone just asked me to be calm."),
    SAY(NERIS, "I'll come. But I'm warning you: I don't forget. I'll remember every single thing we see, and I'll bring it all to every conversation you ever have."),
    SAY("Kenji", "Good."),
    dict(type="recruit", name="Neris", **{"unless": "lh_arrive"}),
    ACT("flag", key="lh_arrive"),
    ACT("follow", t=1.2),
]
OBJECTIVES = [
    {"unless": "lh_woman", "text": "Walk through the Quiet Rows to Mender's Row, at the centre of the Lower Districts."},
    {"unless": "lh_choice", "text": "Find Oriel on the bench by the fountain, and decide what to do for her."},
    {"unless": "lh_warden", "text": "Go through the iron doors to the Sealed Annex, and deal with the Correction Warden at its far door."},
    {"unless": "lh_corrow", "text": "Find Archivist Corrow in the Archive Facility."},
    {"unless": "lh_ledger", "text": "Read the Correction Rolls on his desk."},
    {"unless": "lh_end", "text": "Leave through the stair at the south end of the facility."},
    {"text": "The Hall of Songs lies up the stair at the south end of the facility."},
]

scene = {
    "story": True, "name": "The Lower Districts", "kit": "", "tile": 4,
    "autorun": [dict(unless="lh_arrive", cine=True, actions=ARRIVE)], "objectives": OBJECTIVES,
    "music": {"url": MUSIC + "22. Ancient Library.mp3"},
    "pieces": T.P, "colliders": T.COL, "decals": T.DEC, "npcs": NPCS, "events": EVENTS,
    "spawn": {"x": 0, "z": 50}, "bounds": BOUNDS, "playerHeight": 2.4,
    "camera": {"pitch": 24, "dist": 30},
    "light": {"dir": [-0.4, -1, -0.3], "color": [0.82, 0.88, 0.98], "ambient": [0.5, 0.54, 0.62]},
    "fog": {"color": [0.7, 0.76, 0.84], "near": 40, "far": 140},
    "sky": {"type": "layers", "base": {"type": "gradient", "stops": [[0, "#4a5b78"], [0.5, "#8d9db5"], [1, "#c8d3df"]]}, "layers": []},
    "fx": [],
    "encounters": {"rate": 62, "level": [33, 37], "level_rel": [0, 2], "pool": ["shard_sentry", "arc_drone", "lattice_medic", "phase_hound"],
                   "zones": [{"x": 0, "z": 22, "w": 66, "d": 78, "safe": True}, {"x": 0, "z": -32, "w": 66, "d": 40, "safe": True},
                             {"x": 0, "z": -77, "w": 66, "d": 46, "rate": 60}, {"x": 0, "z": -118, "w": 66, "d": 34, "rate": 56}],
                   "text": "The Stillheart's wards stir..."},
}

if __name__ == "__main__":
    out = os.path.join(sys.argv[1] if len(sys.argv) > 1 else HERE, "lowerhush.json")
    with open(out, "w", encoding="utf-8", newline="") as f:
        json.dump(scene, f, ensure_ascii=False, separators=(",", ":"))
    print("lowerhush.json:", len(T.P), "pieces,", len(T.COL), "colliders,", len(NPCS), "npcs,", len(EVENTS), "events")

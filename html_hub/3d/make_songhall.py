"""Builds html_hub/3d/songhall.json: "The Hall of Songs and the Old Quarter", Lethenia Chapter III "The People Who Chose This" (claude/lethenia-songhall-oct-13.md).
Continues make_lowerhush.py: Neris brings the party to the people who have started to ask questions.  Placeholder names, as agreed.
Layout (x east, z south, the camera looks north):
  1. The Hall of Songs (z 56 .. -34): an old round hall under the city.  Tavian follows Neris here (arrival scene).  Four citizens argue; the party hears each, then Kenji takes the floor.
  2. The Old Quarter (z -40 .. -130): the ruins of the Long War, kept as they were.  Maren Aldwyn walks Kenji through them and asks her question; the Charter in the memorial vault proves the Stillheart's instability is built in; Maren offers a compromise.
Flags: sh_arrive (Tavian scene)  sh_ivel sh_hanne sh_orsk sh_varro (heard)  sh_debate (all four heard)  sh_speech (+ sh_s1 / sh_s2 / sh_s3)  sh_walk (Maren's walk seen)  sh_charter (read)  sh_offer (answered) + sh_a1 (accept the repair) / sh_a2 (refuse) / sh_a3 (see the core first)  sh_end  shc1..shc3 (chests)
Run:  python make_songhall.py [outdir]   (needs kenhouse.py next to it; re-running overwrites hand edits made in /builder3d)"""
import json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kenhouse

KEN = kenhouse.KEN
GC, ST, PA, DG, GEN = ("/assets/3D/GodCity/", "/assets/3D/Stylized/", "/assets/3D/Paradise/", "/assets/3D/Dungeon/", "/assets/3D/Generated/")
S = kenhouse.S
MUSIC = "/assets/Music/mp3/"
rng = random.Random(1103)
T = kenhouse.Town(PA)
put, ken, block = T.put, T.ken, T.block
SAY = lambda who, text, **k: dict(type="say", who=who, text=text, **k)
ACT = lambda _ty, **k: dict(type=_ty, **k)
NPCS, EVENTS = [], []
BOUNDS = dict(minX=-33, maxX=33, minZ=-132, maxZ=60)
NERIS, TAVIAN, SEFA, MAREN = "Neris", "Tavian", "Sefa", "Maren Aldwyn"
IVEL, HANNE, ORSK, VARRO = "Ivel", "Hanne", "Orsk", "Elder Varro"
LAV = [0.92, 0.86, 1.05, 1]


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


def rubble(x, z):
    put(PA + "SM_rock_0%d" % rng.randint(1, 2), x, z, rng.randint(0, 359), 0, rng.uniform(0.7, 1.2)); block(x, z, 1.8, 1.8)


# ------------------------------------------------------------------ ground and walls
for gx in range(-2, 2):
    for gz in range(-7, 3):
        put(GC + "SM_ground_20x20", gx * 20 + 10, gz * 20 + 10, 0, -0.5, 1)
vwall(-31.0, 58.0, -132.0); vwall(31.0, 58.0, -132.0)
hwall(-31.0, 31.0, 59.0); hwall(-31.0, 31.0, -133.0)
for i in range(70):
    z = rng.uniform(-140, 66)
    put(ST + "SM_Cliff_0%d" % rng.randint(1, 2), rng.choice((-1, 1)) * rng.uniform(36, 46), z, rng.randint(0, 359), -0.2, rng.uniform(1.3, 2.2))

# ------------------------------------------------------------------ 1. the Hall of Songs (z 56 .. -34)
put(DG + "SM_dg_dais", 0, 55.5, 0, 0, 1.0); glyph(0, 55.5, 3.0, [1, 0.85, 0.6, 0.8], 15); glow(0, 55.5, 8, [1, 0.85, 0.6, 0.35])
event("sh_up", "The stair back", 0.0, 57.4, [
    SAY("", "The stair back to the Lower Districts. A scrap of old song is scratched on the wall beside it, a few bars of music with no words."),
    dict(type="choice", who="Kenji", text="Go back to the Lower Districts?", options=[
        dict(label="Go back", actions=[ACT("fade", to="black", t=1.0), ACT("warp", scene="lowerhush", x=0.0, z=-128.0, fresh=True)]),
        dict(label="Stay", actions=[ACT("end")])])],
    "Look back", 5.0, 2.4)
# rings of benches around a low stage
HZ = 8.0
for ring, n in ((10.0, 12), (15.0, 16), (20.0, 20)):
    for k in range(n):
        a = k * math.tau / n
        x, z = ring * math.cos(a), HZ + ring * math.sin(a) * 0.75
        if z > 52 or z < -30: continue
        if abs(x) < 2.5 and z > 40: continue
        put(ST + "SM_Stylized_Bench", x, z, math.degrees(a) + 90, 0, 1.0)
put(DG + "SM_dg_dais", 0, HZ, 0, 0, 1.8); block(0, HZ, 4.0, 4.0)
glow(0, HZ, 16, [1, 0.8, 0.5, 0.5])
for (x, z) in ((-26, 40), (26, 40), (-26, 8), (26, 8), (-26, -22), (26, -22)):
    put(DG + "SM_dg_brazier", x, z); put(DG + "SM_dg_flame", x, z, 0, 1.55, 1.0); block(x, z, 1.1, 1.1); glow(x, z, 9, [1, 0.65, 0.3, 0.5])
for fxp in (-8.0, 8.0):
    put(ST + "SM_Stylized_Flag_Var1", fxp, -30.0, 0, 0, 2.6); block(fxp, -30.0, 0.5, 0.5)
chest("shc1", 27.0, 52.0, dict(gold=5600, shards=72, items={"potion": 6, "ether": 7, "antidote": 3}))
ARRIVE = [
    ACT("cine", on=True),
    dict(type="music", url=MUSIC + "22. Ancient Library.mp3"),
    ACT("fade", to="clear", t=2.0, wait=False),
    ACT("cam", x=0, z=46, yaw=0, pitch=32, dist=22, t=0),
    SAY("", "The old Hall of Songs is the first room in Hushmere with a fire in it that anyone chose to light. It is round, and cold at the edges, and crowded with the sound of people arguing, not the first arguing you have heard in this city."),
    SAY("", "Behind you on the stair, quick footsteps. A figure comes down the last steps two at a time and stops, breathing hard."),
    SAY(TAVIAN, "Neris! Neris, wait. I followed you from the Garden. You said you had to go to the archive and you weren't heading for the archive. I was worried. Please, come up. The Rest Pavilion is open all evening."),
    SAY(NERIS, "Tavian. I need you to look at something. Just look."),
    SAY("", "She takes a folded page from inside her coat, a copy of one line from the Correction Rolls, and holds it out. He reads it. His lips move over each word."),
    SAY(TAVIAN, "'Sefa. Organiser of the Public Garden petition. Level three. Disposition: resting.' ...Well. Yes. She was resting. She wasn't well, Neris. You didn't see her that winter. She was so angry. She'd stop eating. She said things about Mother."),
    SAY(NERIS, "She organised a petition to open the Garden to a vote. She was put on a list because she asked for something."),
    SAY(TAVIAN, "If she asked for something and they felt it was wrong for her, that is what care is. Sometimes people don't know what they need. I didn't. The Stillheart gave me my life back, and it would have been very easy to refuse, and I'm so grateful that I didn't."),
    SAY("Kenji", "Do you know where she is?"),
    SAY(TAVIAN, "Resting. She writes every month. Why would anyone lie about that? Why would they bother?"),
    SAY("Miya", "Tavian... have you ever written back? And has anyone ever written back to you with something you didn't expect?"),
    SAY("", "For a moment there is a crack in his composure, no wider than a hair. It closes before it is even a crack."),
    SAY(TAVIAN, "I'm going to go and water her roses. They're getting dry. ...Please, Neris. Please be careful what you're hoping for."),
    SAY("", "He climbs the stair without looking back. On his throat, the pale stone brightens once, the way a smile brightens a face."),
    SAY(NERIS, "That is what I'm afraid of. Not that he's lying. That he's telling the truth."),
    SAY("Kenji", "He's not wrong that she was angry. He's wrong about what the anger was for."),
    ACT("flag", key="sh_arrive"),
    ACT("follow", t=1.2),
]


def hear(flag, who, lines):
    return lines + [ACT("flag", key=flag)]


npc("ivel", IVEL, "Organiser, the Garden petition", "Ranger", -12.0, 20.0, tint=LAV, reach=5.0, actions=[
    SAY(IVEL, "You're the ones with the Rolls? Show me. ...Oh. Oh, Sefa. They wrote 'resting'.", **{"unless": "sh_ivel"}),
    SAY(IVEL, "We should tear it down tonight. The tower, the stones, the Pavilion, the lot. Every day we wait, another name goes onto that list. I'll take a hammer to it myself.", **{"unless": "sh_ivel"}),
    SAY("Kenji", "And everyone who depends on it?", **{"unless": "sh_ivel"}),
    SAY(IVEL, "Depends. That's the word, isn't it. They depend on it because it was made to be depended on. I'm not angry at the people. I'm angry at the lock.", **{"unless": "sh_ivel"}),
    SAY(NERIS, "He's not wrong, Kenji. He's just only half right.", **{"unless": "sh_ivel"}),
    ACT("flag", key="sh_ivel", **{"unless": "sh_ivel"}),
    ACT("flag", key="sh_debate", **{"if": "sh_ivel,sh_hanne,sh_orsk,sh_varro", "unless": "sh_debate"}),
    SAY(IVEL, "Tonight. That's all I'm saying. Tonight.", **{"if": "sh_ivel"})])
npc("hanne", HANNE, "Weaver", "Farmer", 12.0, 22.0, reach=5.0, actions=[
    SAY(HANNE, "I won't argue with the young man. He means well. But I want to say one thing, and I want you to listen to all of it.", **{"unless": "sh_hanne"}),
    SAY(HANNE, "My husband used to put me against the wall. Every night for eleven years. After the Stillheart he started bringing me tea. He has not raised his voice at me in nine years. I am alive. My children are alive. I don't know what he would be without it, and I am not willing to find out.", **{"unless": "sh_hanne"}),
    SAY("Kenji", "Does he know what was done to him?", **{"unless": "sh_hanne"}),
    SAY(HANNE, "He knows he feels better. I know I am safe. And you are the first person in nine years to ask me whether he consented, and I find I cannot answer that.", **{"unless": "sh_hanne"}),
    SAY(NERIS, "Her fear is real. Her relief is real. So is what was done to him.", **{"unless": "sh_hanne"}),
    ACT("flag", key="sh_hanne", **{"unless": "sh_hanne"}),
    ACT("flag", key="sh_debate", **{"if": "sh_ivel,sh_hanne,sh_orsk,sh_varro", "unless": "sh_debate"}),
    SAY(HANNE, "Nine years of tea. I am sorry. I'm not able to want it taken away.", **{"if": "sh_hanne"})])
npc("orsk", ORSK, "Veteran of the last border skirmish", "Warden", 14.0, -6.0, reach=5.0, actions=[
    SAY(ORSK, "I was at Harrow Bridge. I won't tell you what I saw there. I used to see it every time I closed my eyes. For nineteen years, every night.", **{"unless": "sh_orsk"}),
    SAY(ORSK, "The stone doesn't take it away. I can still remember it if I want to. I just don't have to be in it. I don't want you to have the kind of nights I had.", **{"unless": "sh_orsk"}),
    SAY("Kenji", "Then you could keep your stone and keep your memories both. Nobody's asking to take that from you.", **{"unless": "sh_orsk"}),
    SAY(ORSK, "That is not what the tower does, son. That's what it did, once, for me. They take it further now. They took my sister's boy. He asked questions about the bridge and was gone in a week. I know it. I haven't said it out loud since.", **{"unless": "sh_orsk"}),
    SAY(ORSK, "So I'm holding both. I am grateful and I am afraid. I don't know how a man does that.", **{"unless": "sh_orsk"}),
    ACT("flag", key="sh_orsk", **{"unless": "sh_orsk"}),
    ACT("flag", key="sh_debate", **{"if": "sh_ivel,sh_hanne,sh_orsk,sh_varro", "unless": "sh_debate"}),
    SAY(ORSK, "Grateful and afraid. I am. Both. Every night.", **{"if": "sh_orsk"})])
npc("varro", VARRO, "Keeper of the Hall", "Elder", -14.0, -8.0, tint=LAV, reach=5.0, actions=[
    SAY(VARRO, "I am old enough to remember the Long War, young man. Not the memorial version. The version with the smell. I was eleven when the Ashen Quarter burned.", **{"unless": "sh_varro"}),
    SAY(VARRO, "People forget that the Stillheart wasn't invented by tyrants. It was invented by the grieving. We were so tired. We would have done almost anything. We did.", **{"unless": "sh_varro"}),
    SAY("Kenji", "And now? Would you do it again?", **{"unless": "sh_varro"}),
    SAY(VARRO, "I don't know. That's the honest answer, and the people who shout don't want it. I think if you tear it down overnight, people like Orsk will go mad, and people like Hanne's husband will remember what they were, and there will be a second Long War inside the year. And I think if you leave it, it will take Sefa, and then your friend Corrow, and then the people who ask about Sefa.", **{"unless": "sh_varro"}),
    SAY(VARRO, "I have run this Hall for thirty years on a single belief: nobody should have to decide alone. Let the Hall decide. Then I'll abide by whatever it chooses.", **{"unless": "sh_varro"}),
    ACT("flag", key="sh_varro", **{"unless": "sh_varro"}),
    ACT("flag", key="sh_debate", **{"if": "sh_ivel,sh_hanne,sh_orsk,sh_varro", "unless": "sh_debate"}),
    SAY(VARRO, "When you are ready, take the floor. Speak plainly. They will not mind plain.", **{"if": "sh_varro", "unless": "sh_speech"}),
    SAY(VARRO, "Go and see Maren, then. I would rather she heard it from you.", **{"if": "sh_speech"})])
npc("bystander", "Citizen", "Hall regular", "Townee", -4.0, 36.0, actions=[
    SAY("Citizen", "Last week this room had four people in it. Tonight it's forty. Nobody knows what to do with that."),
    SAY("Citizen", "I had a daughter. I think I had a daughter. Something is wrong with me, and I'd like to find out what.", **{"if": "sh_arrive"})])
event("sh_floor", "The floor of the Hall", 0.0, 3.5, [
    SAY("Elder Varro", "The Hall is listening. Say what you came to say."),
    dict(type="choice", who="Kenji", text="What do you say to the Hall?", options=[
        dict(label="\"Break it. Tonight.\"", actions=[
            SAY("Kenji", "It's a muzzle. I've seen the Rolls and I've seen the crystals, and I've seen a woman forget her son's name between one breath and the next. Break it, and break it now."),
            SAY(IVEL, "Yes. YES."),
            SAY(HANNE, "And my husband? And Orsk? Do we simply wake up one morning and find out what we were?"),
            SAY("Kenji", "..."),
            SAY(NERIS, "That wasn't wrong. It just wasn't the whole of it. Say the rest."),
            ACT("flag", key="sh_s1"), ACT("flag", key="sh_speech")]),
        dict(label="\"Nothing changes until each of you has a real choice.\"", actions=[
            SAY("Kenji", "I'm not here to tear anything down or to keep it standing. I'm here because I've seen a world where one person decided for everyone and called it necessity. I won't do that to you. I'm asking that every one of you gets to choose, with the truth in front of you, whether to keep your stone."),
            SAY(HANNE, "...And if my husband chooses to keep his?"),
            SAY("Kenji", "Then he keeps it. Because he chose."),
            SAY(ORSK, "That I can live with."),
            SAY(IVEL, "It's slow. It's so slow."),
            SAY(NERIS, "It's the only answer that doesn't cost anyone their say."),
            ACT("flag", key="sh_s2"), ACT("flag", key="sh_speech")]),
        dict(label="\"Ask each of you, here, now, one by one.\"", actions=[
            SAY("Kenji", "I don't know what's right for you. I don't think I'm the one who should. So I'm going to ask. One by one. Hands up if you'd keep your stone, knowing everything on this page."),
            SAY("", "Slowly, uncertainly, hands rise. Orsk's. Hanne's. A dozen others. Then, a moment later, more hands that stay down, and Ivel's fist at his side. The Hall looks at itself for the first time."),
            SAY(VARRO, "Well. Now we know what we are. That is more than we knew this morning."),
            SAY(NERIS, "It's messy. It's the first honest thing this room has seen in years."),
            ACT("flag", key="sh_s3"), ACT("flag", key="sh_speech")])])],
    "Take the floor", 5.0, 3.5, show="sh_debate", hide="sh_speech")
# the old door, and the Old Quarter beyond
crossgate_z = -34.0
for k in range(2, 14):
    for sgn in (-1, 1):
        x = sgn * k * S
        if abs(x) < 5.0 or abs(x) > 31.5: continue
        ken("wall-fortified", x, crossgate_z, 0, 0, S); block(x, crossgate_z, S, 1.0)
ken("wall-fortified-gate", -2.0, crossgate_z, 0, 0, S * 0.6, "sh_speech"); ken("wall-fortified-gate", 2.0, crossgate_z, 0, 0, S * 0.6, "sh_speech")
T.COL.append(dict(x=0.0, z=crossgate_z, w=9.0, d=1.4, hideIf="sh_speech"))
event("sh_door", "The old door", 0.0, -30.5, [
    SAY("", "A heavy door, older than the Hall, set in the north wall. Varro says it has not been opened since the Stillheart was installed. It opens when the Hall has spoken."),
    SAY("Elder Varro", "Go on. Someone is waiting for you out there. She has waited a long time.", **{"if": "sh_speech"})], "Look at the door", 6.0, 2.6, show="sh_debate")

# ------------------------------------------------------------------ 2. the Old Quarter (z -40 .. -130)
for k in range(46):
    x, z = rng.uniform(-28, 28), rng.uniform(-46, -128)
    if abs(x) < 6: continue
    ken("wall-fortified", x, z, rng.choice((0, 90, 45, 135)), 0, S * rng.uniform(0.5, 1.0)); block(x, z, 2.4, 1.2)
for k in range(40):
    x, z = rng.uniform(-28, 28), rng.uniform(-44, -128)
    if abs(x) < 6: continue
    rubble(x, z)
T.house(-22, -82, 90, [(0, 0, 3, 1)], wall="stone", col="cream", roof="red", collide=True)         # the burnt chapel (kept as it fell)
glow(-22, -82, 8, [1, 0.6, 0.3, 0.35])
event("sh_chapel", "The burnt chapel", -15.0, -82.0, [
    SAY("", "A chapel with the roof gone and the walls black to the eaves. The pews are all still in their rows, and on each one, set neatly, a single child's shoe. Nobody cleaned them up. Nobody has been brave enough to."),
    SAY("Reya", "They kept it exactly. They kept it, and then they put a Pavilion over the top of every other grief in the city.")], "Look inside", 4.0, 3.0)
# the Mourning Field: a wall of named plaques
for k in range(14):
    x = -14.0 + k * 2.1
    put(DG + "SM_dg_tablet", x, -108.0, 180, 0, 0.8); block(x, -108.0, 1.3, 0.5)
glow(0, -110, 14, [1, 0.85, 0.65, 0.4])
event("sh_names", "The Mourning Field", 0.0, -105.5, [
    SAY("", "Every plaque is carved with a name, in full, with a date and the words IN SORROW. Hundreds of them, in a long white line. They are kept clean. A few have flowers, long dry, laid by a hand that stopped coming."),
    SAY(NERIS, "In Hushmere's memorial wall, the plaques are blank. These are the real ones. Nobody comes here. Nobody can bear to."),
    SAY("Kenji", "Somebody scrubs them.", ),
    SAY(NERIS, "Maren does. Or her people do. I used to wonder why.")], "Read the names", 5.0, 3.0, show="sh_walk")
chest("shc2", 27.0, -52.0, dict(gold=5800, shards=74, items={"potion": 6, "ether": 7, "antidote": 4}))
chest("shc3", -27.0, -122.0, dict(gold=6000, shards=76, items={"potion": 7, "ether": 7, "antidote": 4}))
# Maren waits at the gate to the Old Quarter, then at the Mourning Field
npc("maren_a", MAREN, "Founder of the Stillheart", "Mayor", 0.0, -58.0, tint=[0.95, 0.9, 1.15, 1], h=2.8, reach=1.0, show="sh_speech", hide="sh_walk")
npc("maren_b", MAREN, "Founder of the Stillheart", "Mayor", 3.0, -102.0, tint=[0.95, 0.9, 1.15, 1], h=2.8, reach=5.0, show="sh_walk", actions=[
    SAY(MAREN, "Have you read the Charter? The vault is behind me. Read it before you answer me. I would much prefer to be argued with by someone who knows the worst of me.", **{"unless": "sh_charter"}),
    SAY(MAREN, "You've read it, then. You know what it says. I'd have told you if you'd asked. I have told every Concordant for forty years, and they all answer the same: 'We will address it in the next cycle.'", **{"if": "sh_charter", "unless": "sh_offer"}),
    SAY(MAREN, "Now. I have one thing to put to you, and then I will be quiet.", **{"if": "sh_charter", "unless": "sh_offer"}),
    SAY(MAREN, "Help me repair it. Not end it, repair it. I know every wire of that machine. With your mark and my knowledge we can stop it drawing on the unwilling. The worst abuses end tonight. The peace remains. No one has to wake up to a second war.", **{"if": "sh_charter", "unless": "sh_offer"}),
    dict(type="choice", who="Kenji", text="Maren Aldwyn's offer", **{"if": "sh_charter", "unless": "sh_offer"}, options=[
        dict(label="Accept: repair it together, end the worst abuses", actions=[
            SAY("Kenji", "End the worst abuses first. Today. In front of witnesses. If you can do that, I'll stand beside you at the core."),
            SAY(MAREN, "...Today. Thank you. I mean that."),
            SAY(NERIS, "Kenji. The Charter. The draw increases by itself. You can't repair a machine whose purpose is the problem."),
            SAY("Kenji", "I know. We'll see how far her word goes. I'd rather find out than assume."),
            ACT("flag", key="sh_a1"), ACT("flag", key="sh_offer")]),
        dict(label="Refuse: the purpose is the problem", actions=[
            SAY("Kenji", "I read the Charter. It isn't failing, it's working. It's built to need more and more of people, and a repair that leaves that alone just feeds it slower."),
            SAY(MAREN, "Then you'll tear down a city's peace and call it virtue. I will stand in your way. I'll do it gently. I have no other way of doing it."),
            SAY("Kenji", "I know. I'm sorry. I don't want to fight you."),
            SAY(MAREN, "You won't have a choice. Neither will I."),
            ACT("flag", key="sh_a2"), ACT("flag", key="sh_offer")]),
        dict(label="Ask to see the core first", actions=[
            SAY("Kenji", "I won't give you an answer until I've seen what's under the tower. Show me. All of it."),
            SAY(MAREN, "You'll see the Stillheart as I made it, and as I am ashamed of it now. That is a fair thing to ask. That is how it should be done."),
            SAY("Kenji", "Then take me down."),
            SAY(NERIS, "Careful. She will show you what she wants you to see."),
            SAY(MAREN, "She will show you everything. It's worse than anything I'd choose to show you.", ),
            ACT("flag", key="sh_a3"), ACT("flag", key="sh_offer")])]),
    SAY(MAREN, "Come to the tower at dusk. Bring whatever you need to say to me before then.", **{"if": "sh_offer", "unless": "sh_end"}),
    ACT("flag", key="sh_end", **{"if": "sh_offer", "unless": "sh_end"}),
    SAY("", "Chapter III, the People Who Chose This, is complete. Chapter IV, Beneath the Stillheart, opens in a later part of the story. The Old Quarter will wait for you.", **{"if": "sh_end", "unless": "sh_toldend"}),
    ACT("flag", key="sh_toldend", **{"if": "sh_end"}),
    SAY(MAREN, "Come to the tower at dusk.", **{"if": "sh_toldend"})])
# the vault and the Charter
put(DG + "SM_dg_gate", 0, -125.0, 0, 0, 1.2); block(0, -125.0, 6.0, 1.5, "sh_walk")
glow(0, -124.0, 10, [0.8, 0.9, 1.0, 0.5])
event("sh_charter", "The Stillheart Charter", 0.0, -120.5, [
    SAY("", "A vault, small and clean, and a single sheet of paper in a case of glass. It is signed, in a younger, steadier hand, MAREN ALDWYN. At the head: THE STILLHEART MAINTENANCE CHARTER, FIRST EDITION."),
    SAY(NERIS, "'Article Four. The Stillheart draws upon the emotional output of its subjects to power its suppression. As population contentment increases, the draw per citizen shall increase by four parts in a hundred each cycle, to maintain the appearance of equilibrium.'"),
    SAY(NERIS, "'Article Seven. The draw cannot be reduced without proportional release. Release shall be deferred for as long as practicable.'"),
    SAY("Reya", "In plain words?"),
    SAY(NERIS, "It needs more of everyone, forever, to hold the same level of calm. And if it ever stops, everything it's been holding comes out at once. It's not a medicine. It's a debt."),
    SAY("Miya", "And it was written in the first edition. Before anyone abused it. This isn't what went wrong. It's what was built."),
    SAY("Kenji", "She told me to read it. She wanted me to know the worst of it."),
    SAY(NERIS, "She isn't hiding it. She's known all along. She's been trying to keep it from breaking, and never once asked whether it should exist."),
    SAY("Kenji", "Then repairing it just means pulling the same rope more slowly."),
    SAY("", "Scratched into the glass of the case, cold and even: SUBJECT PRESENT. OBSERVE CHOICE."),
    ACT("flag", key="sh_charter")], "Read the Charter", 5.0, 3.0, show="sh_walk", hide="sh_charter")

# Maren's walk (touch scene when the old door is open)
WALK = [
    ACT("cine", on=True),
    ACT("walk", who="player", x=0.0, z=-52.0, speed=4),
    ACT("cam", x=0, z=-62, yaw=0, pitch=26, dist=24, t=1.8),
    SAY("", "Beyond the old door the air changes. It is colder, and it smells like stone and rain and old smoke. The streets here have no roofs. The houses are shells. And standing in the middle of the road, small and upright and entirely alone, an old woman in a plain grey coat is waiting for you."),
    SAY(MAREN, "Kenji. I'm Maren Aldwyn. I have been wanting to meet you since the day you came through the garden gate. Your mark was visible from the tower. Forgive me for the audacity of the invitation."),
    SAY("Kenji", "You made the Stillheart."),
    SAY(MAREN, "I did. I'm told that means I'm a monster. Some days I think so too. Walk with me. There is something I want you to see, and it can't be said, only walked."),
    ACT("walk", who="player", x=0.0, z=-76.0, speed=3),
    ACT("cam", x=-6, z=-82, yaw=0, pitch=24, dist=20, t=1.4),
    SAY(MAREN, "This was the Ashen Quarter. It burned for nine days. My sister and her children were in that chapel, and I was in a lecture hall four streets away explaining to my students how grief can be treated like an infection. I did not smell the fire until the third day."),
    SAY(MAREN, "A boy of seven used to sing in the chapel. I did not know his name, I knew his voice. After the fire, nobody sang for eleven years. A whole generation grew up without a song, because the people who would have taught it to them could not forgive each other for the fire. They taught their children to hate instead."),
    ACT("walk", who="player", x=0.0, z=-98.0, speed=3),
    ACT("cam", x=0, z=-104, yaw=0, pitch=22, dist=18, t=1.4),
    SAY(MAREN, "That is the Mourning Field. Every name. I carve them myself. When I could have made the Stillheart forget them, I decided the dead deserve better than that."),
    SAY("Kenji", "You scrub the plaques, and then you blank the memorial in the city."),
    SAY(MAREN, "Yes. I know. I have held both of those truths for forty years, and I wake up every morning hoping one of them will give way."),
    SAY(MAREN, "The Stillheart began as a gift. Veterans came to my door with their hands shaking and I put a stone in each palm and they slept. Mothers who could not stop screaming. Fathers who had held their children's bodies. I gave them a night's sleep. Do you know what I was? I was the first person in a generation who had given anyone anything."),
    SAY(MAREN, "And I watched what the grief had done. Fathers killing sons over a field boundary because their brothers had died fighting over it. Women poisoning wells. Children raised on stories of who to hate. I watched a people destroy itself with its own pain."),
    SAY(MAREN, "Then I will ask you the only question I have ever wanted to ask anyone who came here with a clear conscience."),
    ACT("shake", t=0.5, amp=0.12),
    SAY(MAREN, "How many people must suffer so that you can preserve the right to suffer?"),
    SAY("", "Kenji opens his mouth. Nothing comes. A long silence. Behind him, Neris is very still."),
    SAY("Kenji", "..."),
    SAY("Kenji", "I don't have an answer. Not a good one. You've shown me something real, and I'm not going to pretend I didn't see it."),
    SAY(MAREN, "That is the most honest thing anyone has said to me in thirty years. Thank you."),
    SAY(MAREN, "Read the Charter in the vault behind me. Every word. I'd rather you knew the worst of what I built before you decide. Then come back and tell me what you think."),
    ACT("flag", key="sh_walk"),
    ACT("follow", t=1.2),
]
event("sh_walk_cs", "Maren Aldwyn", 0.0, -42.0, WALK, "", 40.0, 4.0, show="sh_speech", hide="sh_walk", trigger="touch", once=True)

OBJECTIVES = [
    {"unless": "sh_arrive", "text": "Take the stair down to the Hall of Songs."},
    {"unless": "sh_debate", "text": "Hear the four citizens arguing in the Hall: Ivel, Hanne, Orsk and Elder Varro."},
    {"unless": "sh_speech", "text": "Take the floor at the centre of the Hall and tell them what you think."},
    {"unless": "sh_walk", "text": "Go through the old door in the north wall to the Old Quarter. Someone is waiting."},
    {"unless": "sh_charter", "text": "Read the Stillheart Charter in the vault at the far end of the Old Quarter."},
    {"unless": "sh_offer", "text": "Give Maren Aldwyn your answer, at the Mourning Field."},
    {"text": "Chapter IV, Beneath the Stillheart, opens in a later part of the story."},
]
HEARD = ["sh_ivel", "sh_hanne", "sh_orsk", "sh_varro"]

scene = {
    "story": True, "name": "The Hall of Songs", "kit": "", "tile": 4,
    "autorun": [dict(unless="sh_arrive", cine=True, actions=ARRIVE)], "objectives": OBJECTIVES,
    "music": {"url": MUSIC + "22. Ancient Library.mp3"},
    "pieces": T.P, "colliders": T.COL, "decals": T.DEC, "npcs": NPCS, "events": EVENTS,
    "spawn": {"x": 0, "z": 50}, "bounds": BOUNDS, "playerHeight": 2.4,
    "camera": {"pitch": 24, "dist": 30},
    "light": {"dir": [-0.4, -1, -0.3], "color": [0.95, 0.85, 0.7], "ambient": [0.46, 0.44, 0.5]},
    "fog": {"color": [0.55, 0.52, 0.58], "near": 40, "far": 140},
    "sky": {"type": "layers", "base": {"type": "gradient", "stops": [[0, "#3c3a52"], [0.5, "#7a6e84"], [1, "#c9b79c"]]}, "layers": []},
    "fx": [{"type": "embers", "amount": 0.08}],
    "encounters": {"rate": 62, "level": [35, 39], "level_rel": [0, 2], "pool": ["shard_sentry", "arc_drone", "phase_hound", "rift_leech"],
                   "zones": [{"x": 0, "z": 14, "w": 66, "d": 90, "safe": True}, {"x": 0, "z": -38, "w": 66, "d": 10, "safe": True},
                             {"x": 0, "z": -85, "w": 66, "d": 90, "rate": 58}, {"x": 0, "z": -105, "w": 20, "d": 8, "safe": True}],
                   "text": "Something stirs in the ruins..."},
}

if __name__ == "__main__":
    out = os.path.join(sys.argv[1] if len(sys.argv) > 1 else HERE, "songhall.json")
    with open(out, "w", encoding="utf-8", newline="") as f:
        json.dump(scene, f, ensure_ascii=False, separators=(",", ":"))
    print("songhall.json:", len(T.P), "pieces,", len(T.COL), "colliders,", len(NPCS), "npcs,", len(EVENTS), "events")

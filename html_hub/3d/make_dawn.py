"""Builds html_hub/3d/dawn.json: "Solgard, Dawn", Veyra Chapter E (claude/veyra-dawn-oct-13.md).
Continues make_heart.py: the morning after the Emberheart.  The Sunwall is out, the sky is back, and the story reads the flags set earlier:
  Queen Maelis's fate  eh_f1 (first watch) / eh_f2 (spared, reading the ledger) / eh_f3 (ended)   and the Spire  ar_spire_off / ar_spire_left.
Layout (x east, z south, the camera looks north): the Palace Square (z 40 .. -62): fountain, houses, the palace steps in the north, the Veyra ring in the south.
Flags: dn_arrive (the arrival scene seen)  dn_tomas (Tomas and Reya spoken to)  dn_watch (the counsellor spoken to)  dn_end (left for Eldergate; opens the Lethenia gate)  dnc1 (Odo's gift chest)
Run:  python make_dawn.py [outdir]   (needs kenhouse.py next to it; re-running overwrites hand edits made in /builder3d)"""
import json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kenhouse

KEN = kenhouse.KEN
GC, ST, PA, DG, GEN = ("/assets/3D/GodCity/", "/assets/3D/Stylized/", "/assets/3D/Paradise/", "/assets/3D/Dungeon/", "/assets/3D/Generated/")
S = kenhouse.S
MUSIC = "/assets/Music/mp3/"
rng = random.Random(7712)
T = kenhouse.Town(PA)
put, ken, block = T.put, T.ken, T.block
SAY = lambda who, text, **k: dict(type="say", who=who, text=text, **k)
ACT = lambda _ty, **k: dict(type=_ty, **k)
NPCS, EVENTS = [], []
BOUNDS = dict(minX=-33, maxX=33, minZ=-61, maxZ=42)
F1, F2, F3 = {"if": "eh_f1"}, {"if": "eh_f2"}, {"if": "eh_f3"}
SOFF, SLEFT = "ar_spire_off", "ar_spire_left,!ar_spire_off"


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


def lamp(x, z, warm=(1, 0.8, 0.5, 0.4), r=7):
    put(ST + "SM_Stylized_Lamp_C", x, z, 0, 0, 1.1); block(x, z, 0.6, 0.6); glow(x, z, r, list(warm))


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


# ------------------------------------------------------------------ ground and the square
for gx in range(-2, 2):
    for gz in range(-4, 3):
        put(GC + "SM_ground_20x20", gx * 20 + 10, gz * 20 + 10, 0, -0.5, 1)
for i in range(70):
    z = rng.uniform(-74, 52)
    put(ST + "SM_Cliff_0%d" % rng.randint(1, 2), rng.choice((-1, 1)) * rng.uniform(40, 50), z, rng.randint(0, 359), -0.2, rng.uniform(1.3, 2.2))
vwall(-34.0, 42.0, -62.0); vwall(34.0, 42.0, -62.0)
hwall(-34.0, 34.0, 43.0)
FZ = -8.0
put(ST + "SM_Stylized_Fountain", 0, FZ, 0, 0, 1.6); block(0, FZ, 6.6, 6.6); glow(0, FZ, 12, [1, 0.92, 0.75, 0.4])
for (x, z, r) in ((-27, 28, 90), (-27, 10, 90), (-27, -12, 90), (-27, -32, 90), (27, 28, 270), (27, 10, 270), (27, -12, 270)):
    T.house(x, z, r, [(0, 0, 3, 2)], wall="stone", col="cream", roof="red")
    glow(x, z, 8, [1, 0.8, 0.5, 0.3])
for z in range(34, -50, -14):
    lamp(-12.0, z, r=8); lamp(12.0, z, r=8)
for k in range(6):
    a = k * math.tau / 6
    put(ST + "SM_Stylized_Bench", 7.8 * math.cos(a), FZ + 7.8 * math.sin(a), math.degrees(a) + 90, 0, 1.0)
# the palace steps (north) with the great doors open
hwall(-34.0, 34.0, -62.0, gap=(-8.0, 8.0))
for sx in (-30, 30):
    ken("tower-base", sx, -62.0, 0, 0, S * 1.5); ken("tower", sx, -62.0, 0, S * 1.5, S * 1.5); ken("tower-top", sx, -62.0, 0, S * 3.0, S * 1.5); block(sx, -62.0, 4.4, 4.4)
put(DG + "SM_dg_dais", 0, -54.0, 0, 0, 1.2); put(DG + "SM_dg_dais", 0, -50.0, 0, 0, 1.4)
for fxp in (-6.5, 6.5):
    put(ST + "SM_Stylized_Flag_Var1", fxp, -58.0, 0, 0, 2.8); block(fxp, -58.0, 0.5, 0.5)
# dawn light: pale rose over the north, no more Sunwall gold
glow(0, -60, 44, [1.0, 0.82, 0.75, 0.5]); glow(0, -20, 40, [0.95, 0.88, 0.9, 0.3])
glow(0, FZ, 40, [0.55, 0.7, 1.0, 0.25], show="eh_f1"); glow(0, FZ, 40, [1.0, 0.75, 0.5, 0.2], show="eh_f2")
chest("dnc1", -30.0, 38.0, dict(gold=3600, shards=48, items={"potion": 6, "ether": 5, "antidote": 3}), show="dn_arrive")
# the Veyra ring in the south: the way back to Eldergate
put(DG + "SM_dg_dais", 0, 36.0, 0, 0, 1.0); glyph(0, 36.0, 3.4, [1, 0.8, 0.4, 0.9], 20); glow(0, 36.0, 8, [1, 0.75, 0.4, 0.4])

# ------------------------------------------------------------------ people
npc("tomas_d", "Tomas", "Shift lead, the Steady", "Townee", -6.0, -30.0, tint=[1.15, 1.05, 0.85, 1], h=2.2, reach=5.0, actions=[
    SAY("Tomas", "I have never seen so much sky. They told us it was always like this outside the Wall. I thought they were being kind.", **{"unless": "dn_tomas"}),
    SAY("Tomas", "I am taking Pim home to Bridgeford, and Ria to her mother. Ria's mother is alive. Did you know? Nobody told her, because nobody told anyone anything. I get to be the one who walks up to her door.", **{"if": "eh_f1", "unless": "dn_tomas"}),
    SAY("Tomas", "I am going to stand on the steps with her tonight, with a lamp. Not for her. For the ledger. If she gets tired I will read a page. Then I will take Pim home to Bridgeford and Ria to her mother.", **{"if": "eh_f2", "unless": "dn_tomas"}),
    SAY("Tomas", "The Works is empty. I walked every row last night to be sure. It is the first time I have heard my own footsteps in six years. Pim is asleep on my coat. I will take him to Bridgeford, and Ria to her mother, when the roads are light.", **{"if": "eh_f3", "unless": "dn_tomas"}),
    SAY("Reya", "Tomas. You can come with us. Or I can stay. I would stay. I would be good at staying.", **{"unless": "dn_tomas"}),
    SAY("Tomas", "No. You would hate it by spring. You have been running something since you were eleven, and so have I, and now I want to find out what I am like when nothing is humming.", **{"unless": "dn_tomas"}),
    dict(type="choice", who="Kenji", text="Reya is looking at you. What do you say?", **{"unless": "dn_tomas"}, options=[
        dict(label="\"You can stay with him, Reya. We will manage.\"", actions=[
            SAY("Kenji", "You came all this way for the door. You don't owe us the rest of it."),
            SAY("Reya", "Don't be noble at me, Kenji, it doesn't suit you. I know exactly what I owe. I'm coming."),
            SAY("Tomas", "She will always say the opposite of what the nicest person in the room says. It is how you can tell she likes you.")]),
        dict(label="\"Go with him. Then come and find us.\"", actions=[
            SAY("Kenji", "He came back to the surface after six years. Go and see what the surface is like with him."),
            SAY("Reya", "...No. I would only spend the whole time wanting to know what happens next. Thank you for offering."),
            SAY("Reya", "I'll write. I'll write something short and rude, so you know it's me.")]),
        dict(label="Say nothing, and let her decide", actions=[
            SAY("", "Kenji keeps quiet. It is hard. Reya notices, and the corner of her mouth moves."),
            SAY("Reya", "Look at him not telling me what to do. I think he is learning.")])]),
    SAY("Tomas", "Three. Then two. You remembered. Somebody has to be on the other side, Reya, and now it is going to be me for a change. Go and be on the other side of something.", **{"unless": "dn_tomas"}),
    SAY("", "He folds the old brass key back into her hand a second time. It is cool now, only a key.", **{"unless": "dn_tomas"}),
    ACT("flag", key="dn_tomas", **{"unless": "dn_tomas"}),
    SAY("Tomas", "Go on. The sky is waiting for you. It keeps changing, and I want to see what it does next.", **{"if": "dn_tomas"})])
npc("maelis_d", "Queen Maelis", "Reading the ledger", "Mayor", 0.0, -47.0, tint=[0.85, 0.82, 0.8, 1], h=3.0, show="eh_f2", reach=5.0, actions=[
    SAY("Maelis", "Forty-one thousand and twelve. I read the first thousand in the dark and the rest by the light that is left. They have not left. I did not expect that. I expected stones."),
    SAY("Maelis", "A woman asked me to read her daughter's name again. Slowly. I read it three times. She said, thank you. I would rather she had struck me.", **{"unless": "ar_spire_left"}),
    SAY("Maelis", "The courier from the Ford asked me to add seven names to the ledger. The ones who did not see spring. I said yes. I said it is the only honest page in this book.", **{"if": SLEFT}),
    SAY("Maelis", "They will decide at the end of the week whether I live. Brienne has said she will speak for me and against me in the same breath. It is the fairest thing anyone has done in this city in twenty years.")])
npc("brienne_d", "Elder Brienne", "Ring Elder", "Elder", -4.0, -46.0, tint=[1.05, 1.0, 1.0, 1], reach=5.0, actions=[
    SAY("Brienne", "Come to the bread line, all of you, there is plenty and it is not warm. I have been telling people this since the Wall went out. Not warm, and plenty, and we will manage.", **F1),
    SAY("Brienne", "I have never in my life stood on a step this high. It is a very long way down. I think that is the point of it.", **F2),
    SAY("Brienne", "Nobody rules the Ring. I keep saying it and it keeps sounding like a threat. We will be cold this winter and we will learn to share the cold. I do not know another way to learn it.", **F3),
    SAY("Brienne", "You did not have to come back up and see this. Thank you for coming back up.")])
npc("odo_d", "Lamplighter Odo", "Keeper of the Drain", "Elder", 12.0, 30.0, tint=[1.0, 0.98, 0.9, 1], reach=5.0, actions=[
    SAY("Odo", "Nine years I have lit lamps in a city where it was never dark. Last night I lit them all anyway. They looked tiny. They looked wonderful."),
    SAY("Odo", "Little knife. Mind the road. And mind the gold on your hand, stranger. It does not look risky now. It looks like a lantern.")])
npc("baker_d", "Baker Mira", "Ring Baker", "Farmer", -18.0, 12.0, actions=[
    SAY("Baker Mira", "Cold bread. First cold bread of my life. It tastes like bread. I did not know bread had a flavour of its own."),
    SAY("Baker Mira", "Take three. Please. It is a poor way to say thank you but it is all I have.")])
for (i, x, z) in ((1, 10.0, -26.0), (2, 14.0, -30.0), (3, -14.0, -20.0)):
    npc("kid%d" % i, "Kindler", "Free child", "Townee", x, z, h=1.9, tint=[1.15, 1.05, 0.9, 1], actions=[
        SAY("Child", "It is so big! The sky! It does not have a roof! Where does it end? Tomas says it does not."),
        SAY("", "The faint gold under the child's skin is gone. Only a child is left, out in the cold, delighted.")])
npc("crowd1", "Citizen", "Ring citizen", "Shopkeeper", 18.0, -12.0, actions=[
    SAY("Citizen", "We knew. That's what I keep saying to myself. We knew and we turned the lamps up. I am not going to be able to stop knowing it.", ),
    SAY("Citizen", "Somebody has to fetch wood. Somebody has to show the young ones how a fire is built. We used to know. It is coming back, a little at a time.")])
npc("guard_d", "Ring Guard", "Royal Guard", "Warden", 8.0, -40.0, tint=[1.15, 0.8, 0.7, 1], actions=[
    SAY("Ring Guard", "Nobody has told us what we are guarding, so we are guarding the steps. It seems the right thing.", ),
    SAY("Ring Guard", "Captain Rhenn took off his plume. Said he would wear it again when he had earned it.")])

# the counsellor, alone at the edge of the square
npc("counsel_d", "The Counsellor", "No name on the record", "Rook", 22.0, -22.0, tint=[0.22, 0.22, 0.35, 1], h=3.3, hide="dn_watch", reach=5.0, actions=[
    SAY("", "The hooded figure stands apart from the crowd, though the crowd presses all around it. Nobody touches him. Nobody meets his eye. The dawn does not light his face."),
    SAY("Kenji", "You were at her shoulder for sixteen years. Was that the experiment? Or was it just another lie she told herself?"),
    SAY("The Counsellor", "...", ),
    SAY("", "The hood tilts, politely. There is a long pause, as of someone reading from a card. Then a voice, dry as paper, and not unkind."),
    SAY("The Counsellor", "A WARDEN WHO CHOSE. UNEXPECTED. I HAD ESTIMATED THE THRONE WOULD HOLD.", **F1),
    SAY("The Counsellor", "A QUEEN WHO ANSWERS. UNEXPECTED. I HAD ESTIMATED SHE WOULD HIDE.", **F2),
    SAY("The Counsellor", "A QUEEN CUT DOWN BY THE HERO. EXPECTED. IT IS THE MOST COMMON OUTCOME.", **F3),
    SAY("Kenji", "Expected.", **F3),
    SAY("Miya", "Kenji. Don't.", **F3),
    SAY("Kenji", "No. I'm not doing anything. I'm standing here. I am standing very still.", **F3),
    SAY("Kenji", "You had the Heart in a cage for sixteen years and called it advice. People got to walk out of the Works this morning. Put that in your notes."),
    SAY("The Counsellor", "NOTED. SUBJECT DISPLAYED HOPE. ADJUST."),
    SAY("", "It turns away. The hooded coat is among the crowd, and then it is not, and where it stood the paving shows a single brass plate, bolted flat to the stone, which was not there a moment before. 'NEXT: LETHENIA. PROCEED AT SUBJECT'S DISCRETION.'"),
    SAY("Lyra", "He is telling us where the next door is. He wants us to go. He is polite about it."),
    SAY("Kenji", "Then let's go. We'll go as we are, and we'll bring all of it with us. And when we're there I'll do the one thing he cannot write down."),
    SAY("Reya", "Which is?"),
    SAY("Kenji", "Stay. Long enough to ask the people there what they actually want."),
    ACT("flag", key="dn_watch")])
event("dn_plate", "A brass plate", 22.0, -22.0, [
    SAY("", "A plate set into the paving where the counsellor stood. Cold, even lettering: NEXT: LETHENIA. PROCEED AT SUBJECT'S DISCRETION."),
    SAY("Miya", "Discretion. As if we had been given one.")], "Read the plate", 3.2, 3.2, show="dn_watch")
event("dn_grate", "A grate in the stone", 0.0, -37.0, [
    SAY("", "A warm iron grate set in the paving, the last of the pipes. Under it, very faint and a long way down, a woman's voice is humming. It is not a ledger. It is a lullaby."),
    SAY("Reya", "...She's singing to it."),
    SAY("Kenji", "It's singing back.")], "Listen at the grate", 3.6, 3.0, show="eh_f1")
event("dn_throne", "The empty doors", 0.0, -58.0, [
    SAY("", "The great doors stand open on an empty hall. A crown sits on the third stair, where nobody has quite wanted to touch it."),
    SAY("Reya", "I thought I would want to look at it for a long time. I find I don't."), ], "Look in", 5.0, 3.0, show="eh_f3")

# the Veyra ring: leave for Eldergate
event("dn_ring", "The Veyra ring", 0.0, 36.0, [
    SAY("", "The old ring-stone in the south of the square hums low and gold, as it did when you came up from Cinder Hollow, or the Core did. The way back to Eldergate stands open."),
    SAY("Kenji", "There's something here I haven't done yet.", **{"unless": "dn_tomas"}),
    ACT("end", **{"unless": "dn_tomas"}),
    SAY("Kenji", "The counsellor's still out there somewhere in the crowd. I want a word.", **{"if": "dn_tomas", "unless": "dn_watch"}),
    ACT("end", **{"if": "dn_tomas", "unless": "dn_watch"}),
    dict(type="choice", who="Kenji", text="Return to Eldergate?", options=[
        dict(label="Go back through the ring", actions=[
            SAY("Kenji", "Veyra is a country with a winter ahead of it. It won't be an easy one. But it isn't a machine any more."),
            SAY("Reya", "Let's go and be on the other side of something."),
            SAY("Lyra", "The Core in Eldergate has stirred. A second gate has woken. It woke the moment the Wall went out."),
            ACT("flag", key="dn_end"),
            ACT("fade", to="black", t=1.4),
            ACT("title", text="Veyra, At Dawn", sub="Chapter complete", t=3.0),
            ACT("warp", scene="eldergate", x=4.4, z=-40.5, fresh=True)]),
        dict(label="Not yet", actions=[ACT("end")])])],
    "Step onto the ring", 6.0, 3.0)

# ------------------------------------------------------------------ arrival scene
ARRIVE = [
    ACT("cine", on=True),
    dict(type="music", url=MUSIC + "15. Volcanic Crater.mp3"),
    ACT("fade", to="clear", t=3.0, wait=False),
    ACT("cam", x=0, z=-10, yaw=0, pitch=22, dist=34, t=0),
    SAY("", "Dawn comes up over Solgard, and it is the first time in twenty years that anyone has seen it do so. The Sunwall has gone out. Behind where it burned there is a pale sky the colour of the inside of a shell, and the whole city is standing in the streets, looking up."),
    SAY("", "On the palace steps, Elder Brienne stands in her nightgown with a lamp, because nobody else would. The Works' doors are open, and children are coming out in a line, blinking, holding each other's sleeves. At the end of the line a tall boy carries a smaller one on his back.", **F1),
    SAY("", "On the palace steps, in the plain grey dress of someone who has taken off her crown, Queen Maelis reads names from a ledger by lamplight. She has been reading since the Wall went out. Nobody has stopped her and nobody has gone home. Some weep. A few shout. An old man climbs the steps and puts a blanket round her shoulders.", **F2),
    SAY("", "The palace steps are empty. The great doors stand open and nobody has gone in. The Ring is out in its streets in the grey light, in blankets, not speaking. Brienne has taken the bread line because no one else would, and a chain of office hangs from the Works gatepost for whoever will have it.", **F3),
    SAY("", "A courier in Harrow's Ford grey pushes through the crowd on a lathered horse. 'Dov of the Ford!' he calls. 'Elder Wen says the Ford is warm and the Spire is dead and the soup is on, if Solgard wants any.' Nobody knows what to do with that. Reya laughs once, hard, like a cough.", **{"if": SOFF}),
    SAY("", "Dov of the Ford threads through the crowd with a letter in his hand. 'From Elder Wen,' he says to no one, and reads it to the square instead: seven names, and an age beside each. When he reaches the baby he stops, and the square stops with him, and the only sound is a city learning to be cold.", **{"if": SLEFT}),
    SAY("Lyra", "Every chimney in the Ring is smoking. They are lighting their own fires. Look at them, Kenji. They don't know how."),
    SAY("Kenji", "Then they'll learn. That's what the cold is for, apparently. It's the only teacher that ever had enough patience."),
    SAY("Reya", "Tomas is down there. By the fountain. I can see his coat.", **F1),
    SAY("Reya", "Tomas is down there. By the fountain. Don't let me run, Kenji.", **F2),
    SAY("Reya", "Tomas is down there. By the fountain. He hasn't moved. I don't think he knows how.", **F3),
    ACT("flag", key="dn_arrive"),
    ACT("follow", t=1.2),
]
OBJECTIVES = [
    {"unless": "dn_tomas", "text": "Find Tomas by the fountain, and say goodbye."},
    {"unless": "dn_watch", "text": "Speak to the counsellor, who stands apart at the east edge of the square."},
    {"unless": "dn_end", "text": "Step onto the Veyra ring in the south of the square and return to Eldergate."},
    {"text": "Veyra is behind you. In Eldergate, a second gate has woken."},
]

scene = {
    "story": True, "name": "Solgard, Dawn", "kit": "", "tile": 4,
    "autorun": [dict(unless="dn_arrive", cine=True, actions=ARRIVE)], "objectives": OBJECTIVES,
    "music": {"url": MUSIC + "15. Volcanic Crater.mp3"},
    "pieces": T.P, "colliders": T.COL, "decals": T.DEC, "npcs": NPCS, "events": EVENTS,
    "spawn": {"x": 0, "z": 28}, "bounds": BOUNDS, "playerHeight": 2.4,
    "camera": {"pitch": 24, "dist": 30},
    "light": {"dir": [-0.35, -1, -0.25], "color": [0.95, 0.82, 0.78], "ambient": [0.52, 0.5, 0.56]},
    "fog": {"color": [0.78, 0.7, 0.72], "near": 55, "far": 170},
    "sky": {"type": "layers", "base": {"type": "gradient", "stops": [[0, "#7a8ab0"], [0.5, "#e6b9b0"], [1, "#fbe3c6"]]}, "layers": []},
    "fx": [{"type": "embers", "amount": 0.05}],
}

if __name__ == "__main__":
    out = os.path.join(sys.argv[1] if len(sys.argv) > 1 else HERE, "dawn.json")
    with open(out, "w", encoding="utf-8", newline="") as f:
        json.dump(scene, f, ensure_ascii=False, separators=(",", ":"))
    print("dawn.json:", len(T.P), "pieces,", len(T.COL), "colliders,", len(NPCS), "npcs,", len(EVENTS), "events")

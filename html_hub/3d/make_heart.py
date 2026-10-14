"""Builds html_hub/3d/heart.json: "The Emberheart", Veyra Chapter D (claude/veyra-heart-oct-13.md).
Continues make_solgard.py: the party opens the Great Valve with the kindler's key and goes down beneath the throne.
Layout (x east, z south, the camera looks north):
  1. The Descent (z 58 .. 24): a drain-stair shaft, a Watcher plate, the way back up to the Works.  Captain Rhenn guards the inner gate.
  2. The Gallery of Names (z 20 .. -56): the ledger wall (41,012 names), pipes of gold light, a kindler's brazier (rest point), chests.
  3. The Emberheart (z -62 .. -136): the great chamber.  Queen Maelis waits at the Heart with the faceless counsellor; the Ember Regent guards it.
     After the Regent falls, Kenji's mark reconnects the Heart (its warmth flows out as a shared flame and the Sunwall dims) and the party chooses Maelis's fate.
Maelis's fate (flags): eh_f1 she takes the first watch of the Emberheart herself, the kindlers go free;  eh_f2 she is spared and sent up to answer to the city;
  eh_f3 she is ended and Kenji steadies the Heart alone, Solgard gets a leaderless winter.  eh_fate is set with whichever one was chosen.
Flags: eh_arrive eh_captain eh_names eh_parley eh_regent eh_fate eh_f1 eh_f2 eh_f3 eh_end ec1..ec4 (chests)
Run:  python make_heart.py [outdir]   (needs kenhouse.py next to it; re-running overwrites hand edits made in /builder3d)"""
import json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kenhouse

KEN = kenhouse.KEN
GC, ST, PA, DG, GEN = ("/assets/3D/GodCity/", "/assets/3D/Stylized/", "/assets/3D/Paradise/", "/assets/3D/Dungeon/", "/assets/3D/Generated/")
S = kenhouse.S
MUSIC = "/assets/Music/mp3/"
rng = random.Random(6643)
T = kenhouse.Town(PA)
put, ken, block = T.put, T.ken, T.block
SAY = lambda who, text, **k: dict(type="say", who=who, text=text, **k)
ACT = lambda _ty, **k: dict(type=_ty, **k)
NPCS, EVENTS = [], []
BOUNDS = dict(minX=-34, maxX=34, minZ=-140, maxZ=62)


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
    event(id, "Treasure chest", x, z, [dict(type="flag", key=id), dict(type="chest", loot=loot, text="You prise the chest open and find")], "Open the chest", 3.4, 3.4, hide=id, show=show)


def hwall(x0, x1, z, gap=None):
    """A wall along x at depth z, skipping the open interval gap=(a, b)."""
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


def brazier(x, z, r=9, c=(1, 0.55, 0.22, 0.55)):
    put(DG + "SM_dg_brazier", x, z); put(DG + "SM_dg_flame", x, z, 0, 1.55, 1.0); block(x, z, 1.1, 1.1); glow(x, z, r, list(c))


EMBER = [1.0, 0.55, 0.2, 0.55]
# ------------------------------------------------------------------ ground and rock
for gx in range(-2, 2):
    for gz in range(-7, 4):
        put(GC + "SM_ground_20x20", gx * 20 + 10, gz * 20 + 10, 0, -0.5, 1)
for i in range(90):
    z = rng.uniform(-148, 70)
    put(ST + "SM_Cliff_0%d" % rng.randint(1, 2), rng.choice((-1, 1)) * rng.uniform(36, 46), z, rng.randint(0, 359), -0.2, rng.uniform(1.3, 2.3))

# ------------------------------------------------------------------ 1. the Descent (z 58 .. 24)
vwall(-13.0, 58.0, 20.0); vwall(13.0, 58.0, 20.0)
hwall(-13.0, 13.0, 59.5)
for (x, z) in ((-7, 50), (7, 50), (-7, 34), (7, 34)):
    brazier(x, z, 8)
put(DG + "SM_dg_dais", 0, 55.5, 0, 0, 0.8); glyph(0, 55.5, 3.0, [1, 0.7, 0.35, 0.9], 25)
for (x, z) in ((-10, 42), (10, 40)):
    put(ST + "SM_Stylized_Box_var1", x, z, rng.randint(0, 359), 0, 1.3); block(x, z, 1.3, 1.3)
event("eh_up", "The valve stair", 0.0, 57.6, [
    SAY("", "A spiral of iron steps goes back up toward the Works, and the warm light of the valve above."),
    dict(type="choice", who="Kenji", text="Climb back up to the Works?", options=[
        dict(label="Go back up", actions=[ACT("fade", to="black", t=1.0), ACT("warp", scene="solgard", x=0.0, z=-163.0, fresh=True)]),
        dict(label="Stay below", actions=[ACT("end")])])],
    "Look up the stair", 5.0, 2.4)
event("eh_plate", "A brass plate", -9.5, 28.0, [
    SAY("", "A brass plate in the wall, crown lettering: HEART ACCESS. AUTHORISED KEY ONLY. And under it, cold and even: PRESSURE APPLIED. SUBJECT PROCEEDING."),
    SAY("Kenji", "It's always one step ahead of the paint."),
    SAY("Lyra", "Or one step ahead of us. I would like to know which.")], "Read the plate", 3.6, 2.6)

# the inner gate, held by the guard captain
GATE_Z = 24.0
for gx in (-5.6, -8.4, -11.2, 5.6, 8.4, 11.2):
    ken("wall-fortified", gx, GATE_Z, 0, 0, S); block(gx, GATE_Z, S, 1.0)
ken("wall-fortified-gate", -2.0, GATE_Z, 0, 0, S * 0.6, "eh_captain"); ken("wall-fortified-gate", 2.0, GATE_Z, 0, 0, S * 0.6, "eh_captain")
T.COL.append(dict(x=0.0, z=GATE_Z, w=9.0, d=1.4, hideIf="eh_captain"))
npc("rhenn", "Captain Rhenn", "Captain of the Throne Guard", "Warden", 0.0, GATE_Z + 3.2, tint=[1.25, 0.8, 0.6, 1], h=2.7, reach=5.0, hide="eh_captain", actions=[
    SAY("Captain Rhenn", "Stop there. That is a kindler's key you wear, and it was not issued to you. Which child did you take it from?"),
    SAY("Reya", "My brother gave it to me. He's the Steady. Tomas. He's seventeen."),
    SAY("Captain Rhenn", "I know Tomas. I carried him down the first night, when he was eleven and would not stop shaking. I signed that intake as a witness, and I have signed every one since. Do not think the Throne Guard does not know what it guards."),
    SAY("Kenji", "Then you know what you're guarding is wrong."),
    SAY("Captain Rhenn", "I know it is a debt. A debt is not the same as a crime, boy. There were three hundred and sixty dead in the cold winter. I count them every night. I would count a great many more, if the Wall went dark."),
    SAY("Miya", "And so you count the children instead."),
    SAY("Captain Rhenn", "...I did not say it was a good sum. Stand down, or I stand you down."),
    dict(type="battle", key="eh_captain", pool=["cursed_knight", "iron_golem"], level_rel=[2, 4], elite=1.6)])
npc("rhenn_b", "Captain Rhenn", "Captain of the Throne Guard", "Warden", 4.2, GATE_Z - 2.4, tint=[1.25, 0.8, 0.6, 1], h=2.7, reach=5.0, show="eh_captain", actions=[
    SAY("Captain Rhenn", "...Go on. I have been at this gate for twenty years and I never once wanted to be beaten at it. She is at the bottom, with the Regent. She has not eaten since the valve turned. She will want to talk first. Let her.", **{"unless": "eh_fate"}),
    SAY("Captain Rhenn", "Whatever you decided, thank you for deciding it face to face. Most do it by letter.", **{"if": "eh_fate"})])

# ------------------------------------------------------------------ 2. the Gallery of Names (z 20 .. -56)
GW = 24.0
vwall(-GW, 20.0, -60.0); vwall(GW, 20.0, -60.0)
hwall(-GW, -13.0, 21.5); hwall(13.0, GW, 21.5)
for (x, z) in [(sx, z) for sx in (-14, 14) for z in (10, -6, -22, -38, -52)]:
    put(DG + "SM_dg_pillar", x, z, 0, 0, 1.2); block(x, z, 1.4, 1.4); glow(x, z, 7, [1, 0.62, 0.28, 0.5])
for k in range(5):
    glow(0, 14 - k * 16, 12, [1, 0.6, 0.25, 0.3])
brazier(-18, -28, 10, (1, 0.7, 0.35, 0.6)); brazier(18, -28, 10, (1, 0.7, 0.35, 0.6))
event("eh_rest", "Kindlers' brazier", -18.0, -26.0, [
    SAY("", "Someone has kept a brazier burning here, with a blanket folded over a crate and a row of tin cups. A scrap in a child's hand: 'for whoever comes down next. It is warm, I promise.'"),
    dict(type="rest")], "Rest by the brazier", 4.0, 3.0)
# the wall of names: tall plates down both walls
for z in range(14, -56, -9):
    for sx in (-GW + 0.8, GW - 0.8):
        put(ST + "SM_Stylized_WantedBoard", sx, z, 90 if sx < 0 else 270, 0, 1.2)
event("eh_names", "The Wall of Names", 20.0, -4.0, [
    SAY("", "The wall is plates of brass, row on row, from floor to roof, each stamped with a name, an age at intake, and a single word: SERVING."),
    SAY("Reya", "...It goes on forever."),
    SAY("", "Reya's hand stops on one near the middle: TOMAS, CINDER HOLLOW. AGE ELEVEN. SERVING. She does not say anything. She puts her thumb over the word and holds it there."),
    SAY("", "At the end of the last column the plates are bright and new. The last one reads: PIM, BRIDGEFORD. AGE EIGHT. No. 41,012. Beneath it is a blank plate, already bolted to the wall, waiting."),
    SAY("Reya", "That blank one is for someone. It was always for someone."),
    SAY("", "Beneath the blank plate, scratched coldly into the brass as if it had always been there: SUBJECT PRESENT. OBSERVE CHOICE."),
    SAY("Kenji", "Then let's give it something to observe."),
    ACT("flag", key="eh_names")], "Read the plates", 4.0, 3.0)
chest("ec1", -20.5, 8.0, dict(gold=3200, shards=44, items={"potion": 5, "ether": 3, "antidote": 2}))
chest("ec2", 20.5, -46.0, dict(gold=3400, shards=46, items={"potion": 4, "ether": 4}))
npc("kindler_h", "Ember warden", "Hollow-eyed kindler", "Townee", 12.0, -14.0, tint=[1.25, 1.0, 0.55, 1], h=1.9, actions=[
    SAY("Ember warden", "I was told if I stayed very still the Heart would not notice me. It notices everyone. It just doesn't mind."),
    SAY("Ember warden", "Do you hear it? It sounds sleepy. It used to sound hungry. I think it likes the one with the gold hand.", **{"if": "eh_captain"})])

# ------------------------------------------------------------------ 3. the Emberheart (z -62 .. -136)
CW = 32.0
vwall(-CW, -58.0, -138.0); vwall(CW, -58.0, -138.0)
hwall(-CW, CW, -138.0)
hwall(-CW, CW, -60.0, gap=(-5.0, 5.0))
for sx in (-30, 30):
    for z in (-60, -138):
        ken("tower-base", sx, z, 0, 0, S * 1.5); ken("tower", sx, z, 0, S * 1.5, S * 1.5); ken("tower-top", sx, z, 0, S * 3.0, S * 1.5); block(sx, z, 4.4, 4.4)
HZ = -100.0                                           # the Heart
put(DG + "SM_dg_dais", 0, HZ, 0, 0, 2.6); put(DG + "SM_dg_flame", 0, HZ, 0, 1.2, 3.6); block(0, HZ, 5.0, 5.0)
glow(0, HZ, 30, [1.0, 0.55, 0.2, 0.75]); glow(0, HZ, 16, [1.0, 0.8, 0.45, 0.6])
glyph(0, HZ, 11.0, [1, 0.7, 0.35, 0.9], 18); glyph(0, HZ, 7.0, [1, 0.85, 0.5, 0.9], -30)
glow(0, HZ, 44, [0.55, 0.7, 1.0, 0.55], show="eh_fate")        # after the choice the Heart burns blue-white, a shared flame
for k in range(10):
    a = k * math.tau / 10
    x, z = 17 * math.cos(a), HZ + 17 * math.sin(a)
    put(DG + "SM_dg_pillar", x, z, 0, 0, 1.3); block(x, z, 1.4, 1.4); glow(x, z, 7, [1, 0.6, 0.28, 0.5])
chest("ec3", -29.0, -134.0, dict(gold=4000, shards=52, items={"potion": 6, "ether": 5}))

# the Regent (a guardian beside the Heart)
npc("regent", "Ember Regent", "Guardian of the Heart", "Draven", 0.0, HZ + 8.0, tint=[1.6, 0.7, 0.3, 1], h=4.4, reach=6.0, hide="eh_regent", actions=[
    SAY("Ember Regent", "THE HEART IS LIT. THE HEART IS FED. THE HEART IS NOT TO BE TOUCHED."),
    SAY("Kenji", "It's blocking the Heart. We have to go through it."),
    SAY("Queen Maelis", "Please. It cannot be reasoned with. I am sorry. Do not let it think you are me.", **{"if": "eh_parley"}),
    dict(type="battle", key="eh_regent", boss="ember_regent_boss")])

# the Queen at the Heart: a touch cutscene on entering the chamber
npc("maelis_h", "Queen Maelis", "The Sun Queen", "Mayor", 0.0, HZ + 3.6, tint=[1.25, 1.05, 0.7, 1], h=3.0, hide="eh_fate", reach=1.0)
npc("counsellor_h", "The Counsellor", "No name on the record", "Rook", 4.0, HZ + 3.6, tint=[0.22, 0.22, 0.35, 1], h=3.3, hide="eh_fate", reach=1.0)
PARLEY = [
    ACT("cine", on=True),
    ACT("walk", who="player", x=0.0, z=-80.0, speed=4),
    ACT("cam", x=0, z=-96, yaw=0, pitch=26, dist=30, t=2.2),
    SAY("", "The chamber opens like a held breath. In the middle a pulse of living gold hangs in the air above a dais, and the whole room beats with it, slowly, like a very large animal asleep."),
    SAY("Queen Maelis", "You came down. Good. I had hoped the Steady would find someone to give his key to. He is a careful boy."),
    SAY("Kenji", "You knew we'd come."),
    SAY("Queen Maelis", "I knew someone would. I have waited every night for sixteen years. I wished it would be a child with a sword and a bad temper, and it is, and I find I am grateful."),
    SAY("Reya", "Don't. Don't be gentle with us. You put my brother on a plate on a wall."),
    SAY("Queen Maelis", "I did. I put forty-one thousand on that wall, and I signed every one myself. The winter I took the throne three hundred and sixty froze in a single week. I held the baby of the girl who baked my bread. She was not yet a day old. She was cold in my arms."),
    SAY("Queen Maelis", "The Heart was dying. It is the last of something that old Veyra worshipped, and it was going out, and with it the warmth of the whole province. I learned that children's hands could keep it lit. I learned it from a voice that told me, kindly, how."),
    SAY("", "She does not look at the tall figure at her shoulder. It does not look at her. Its hood is turned, and at once, politely, to Kenji."),
    SAY("Lyra", "Kenji. That voice. It has been in every plate in this country, and it is wearing a coat."),
    SAY("Queen Maelis", "He has been my counsellor for sixteen years. I have never learned his name, and I have never once been able to remember his face. I think now that was a mercy he arranged."),
    ACT("flash"), ACT("shake", t=0.8, amp=0.2),
    SAY("", "The Heart flares. A gold shape rises out of the dais, a ring of old armour fused with fire, taller than a house, its seams alive with light."),
    SAY("Queen Maelis", "The Regent. It was built to keep the Heart lit at any cost. I cannot call it back. I never could. Forgive me. If you mean to touch the Heart, you must go through it."),
    ACT("flag", key="eh_parley"),
    ACT("follow", t=1.2),
]
event("eh_parley_cs", "The Emberheart", 0.0, -66.0, PARLEY, "", 20.0, 3.0, hide="eh_parley", trigger="touch", once=True)

# after the Regent falls: the reconnection and the fate choice
def fate_scene(flag, lines):
    return [ACT("flag", key=flag), ACT("flag", key="eh_fate")] + lines

END_COMMON = [
    ACT("shake", t=1.0, amp=0.25), ACT("flash"),
    SAY("", "The glow in the chamber changes. Gold turns blue-white, and the flame on the dais lets go of the pipes. For a heartbeat the whole shaft goes dark; then every kindler's hand in the Works lights from within, warm and quiet and their own."),
    SAY("Lyra", "It's not feeding the Wall any more. It's feeding everyone. The Wall is going out, one lamp at a time, and every house in Solgard is getting warmer."),
]
FATE1 = fate_scene("eh_f1", [
    SAY("Kenji", "You said you'd carry the number. Carry it here. Take the first watch of the Heart yourself, in your own hands, so it never needs a child's again."),
    SAY("Queen Maelis", "...Yes. Yes, that is just. I could not have asked it, but that is just."),
    SAY("", "She walks into the light with her gown of banked embers and puts both palms flat against the flame. It does not burn her. It does not spare her, either. Her hair goes white from root to tip as the gold travels up her arms."),
    SAY("Queen Maelis", "Tell the Works to open every door. Tell Tomas I... tell Tomas I said the first number out loud. He will understand."),
] + END_COMMON + [
    SAY("Tomas", "She said it? Out loud? ...Good. Good. I didn't think she could."),
    SAY("Reya", "Tomas. You can walk out of here. You can walk out of here with me, tonight."),
    SAY("Tomas", "I know. I'm going to. I'm going to carry Pim out on my back first."),
    SAY("Reya", "I would have killed her, you know. If you hadn't been standing right there with that face."),
    SAY("Tomas", "I know. That's why I stood there."),
    SAY("Kenji", "She chose it, so it isn't punishment and it isn't mercy. It's what she was owed, and what the children were."),
])
FATE2 = fate_scene("eh_f2", [
    SAY("Kenji", "I'm not going to kill you, and I'm not going to let you hide in here. You'll climb the stair, you'll stand on the palace steps, and you'll read the number to them. All of them. Out loud. Then they decide."),
    SAY("Queen Maelis", "...They might hang me."),
    SAY("Kenji", "They might. That is theirs to decide. You've been deciding for them for sixteen years."),
    SAY("", "Her shoulders go down a little, the way a person's do when they put down a thing they have carried too long. She kneels to the ember-gold light of the dais and takes off her crown."),
    SAY("Queen Maelis", "Forty-one thousand and twelve. I will read it as many times as they ask."),
    SAY("", "Kenji puts his marked hand into the flame, and it takes him in, and does not burn."),
] + END_COMMON + [
    SAY("Tomas", "She'll face the Ring? The whole Ring? ...I think that's the bravest thing I ever heard of her doing, and I hate that."),
    SAY("Reya", "I wanted her gone. I wanted her ended. And I'm glad you didn't, and I'm angry that I'm glad."),
    SAY("Tomas", "Welcome to the family. That's every feeling I had for sixteen years."),
    SAY("Kenji", "It is going to be a hard winter for her. It's going to be a harder one if she lies."),
])
FATE3 = fate_scene("eh_f3", [
    SAY("Kenji", "I can't let you walk back up that stair. Not after the plate with Tomas's name on it. I'm sorry."),
    SAY("Queen Maelis", "No. Do not be. Please. You have my leave, and my thanks, which is a bitter thing to say."),
    SAY("", "It is quick, and it is not clean. Reya turns her face away. The Queen's crown rolls once across the dais and stops against the Heart, and the flame takes it."),
    SAY("", "Kenji lays his marked hand on the Heart alone. Gold climbs his wrist and keeps climbing. He sets his teeth and does not make a sound."),
] + END_COMMON + [
    SAY("Kenji", "It's steady. I've got it. Give me a minute."),
    SAY("Tomas", "She cried when she signed the first intake. I was there. That's all I wanted known. That one thing. Not that she was right. That she cried."),
    SAY("Reya", "...I don't know what I'm feeling, Kenji. I don't think I want you to tell me."),
    SAY("Kenji", "I won't. I'm sorry. The winter will be hard up there and nobody is going to be in charge of it. I'll have to live with that part."),
    SAY("Lyra", "He is bleeding gold from the palm, and he won't let anyone help. That is a very particular kind of grief."),
])

AFTER = [
    ACT("cine", on=True),
    ACT("cam", x=0, z=-96, yaw=0, pitch=26, dist=28, t=1.5),
    SAY("", "The Regent's last seam goes dark and the gold drains out of its armour onto the floor. The chamber is quiet; only the Heart beats, slow and a little afraid."),
    SAY("Queen Maelis", "It is done. It will not ever have to be done again. Thank you for that, whatever else you do."),
    SAY("Kenji", "The Heart. It's looking at the mark. It knows what I am."),
    SAY("Lyra", "Of course it does. It's a piece of the same thing. It was broken off before you were, Kenji. This is a little of what you were."),
    SAY("Kenji", "Then I can reconnect it. The pipes are what makes it a prison. If I take it out of the pipes it's just a fire."),
    SAY("Queen Maelis", "Then the Wall goes out. The whole city goes cold, in a night, and Solgard will tear itself apart, and it will be my doing and yours."),
    SAY("Kenji", "It doesn't have to go cold in a night. The Heart can warm everyone, not just the Wall. But somebody has to stand with it while it learns how. And I have to know what to do with you."),
    SAY("", "The counsellor has not moved. The hood tilts, a polite, expectant angle. It is waiting to see what you do."),
    dict(type="choice", who="Kenji", text="What becomes of Queen Maelis?", options=[
        dict(label="She takes the first watch of the Emberheart herself. The kindlers go free.", actions=FATE1),
        dict(label="Spare her. She answers to the city.", actions=FATE2),
        dict(label="End her. Kenji steadies the Heart alone.", actions=FATE3)]),
    SAY("", "The plate on the wall beside the dais rewrites itself in cold, even letters, and then, as if embarrassed, again: SUBJECT DISPLAYED HOPE. ADJUST."),
    SAY("Miya", "It's rattled. It wrote that twice."),
    SAY("Kenji", "Good. Let it scramble. We're going to go and see the sky."),
    ACT("flag", key="eh_end"),
    ACT("follow", t=1.2),
]
event("eh_after_cs", "The Emberheart", 0.0, HZ + 4.0, AFTER, "", 60.0, 30.0, show="eh_regent", hide="eh_fate", trigger="touch", once=True)

# the Queen after the choice (fate 1 stays at the Heart, fate 2 waits by the stair, fate 3 is gone)
npc("maelis_1", "Queen Maelis", "First Warden of the Heart", "Mayor", 0.0, HZ + 3.2, tint=[1.5, 1.35, 1.1, 1], h=3.0, show="eh_f1", actions=[
    SAY("Queen Maelis", "It is not a burden, strangely. It is more like holding a hand in the dark. The Heart does not want my years. It wants company. I think I can give it that."),
    SAY("Queen Maelis", "Send the Steady home, and the little ones. Put the Wall to a vote. Let Solgard learn the cold gently, as I should have let it learn.")])
npc("maelis_2", "Queen Maelis", "Awaiting the city's judgment", "Mayor", -6.0, -72.0, tint=[0.9, 0.85, 0.8, 1], h=3.0, show="eh_f2", actions=[
    SAY("Queen Maelis", "I have asked the Throne Guard to open the great doors at dawn. I mean to stand on the steps with a lamp and read the ledger aloud, once for each name. It will take until the following dawn."),
    SAY("Queen Maelis", "If the Ring wants a queen after that, it can choose one. I would advise Brienne. She has never once asked where the heat came from, and has felt it every day.")])

# ------------------------------------------------------------------ exit and ending
event("eh_stair", "The climb out", 0.0, -128.5, [
    SAY("", "A second stair, newly warm, climbs out of the chamber toward the valve, the Works and, beyond them, the morning."),
    dict(type="choice", who="Kenji", text="Climb back up?", options=[
        dict(label="Climb out into the dawn (Chapter E)", actions=[ACT("fade", to="black", t=1.2), ACT("warp", scene="dawn", x=0.0, z=28.0, fresh=True)]),
        dict(label="Go up to the Works", actions=[ACT("fade", to="black", t=1.0), ACT("warp", scene="solgard", x=0.0, z=-163.0, fresh=True)]),
        dict(label="Stay a while", actions=[ACT("end")])])],
    "Climb to the Works", 6.0, 3.0, show="eh_end")
glow(0.0, -128.5, 10, [0.6, 0.8, 1.0, 0.6], show="eh_end")
event("ec4", "A shard of the shared flame", 28.0, -134.0, [dict(type="flag", key="ec4"), dict(type="chest", loot=dict(gold=5000, shards=60, items={"potion": 6, "ether": 6}), text="Where the shared flame fell, you find")], "Take it", 3.6, 3.6, hide="ec4", show="eh_end")

# ------------------------------------------------------------------ arrival
ARRIVE = [
    ACT("cine", on=True),
    dict(type="music", url=MUSIC + "15. Volcanic Crater.mp3"),
    ACT("fade", to="clear", t=2.5, wait=False),
    ACT("cam", x=0, z=50, yaw=0, pitch=36, dist=22, t=0),
    SAY("", "The valve wheel closes behind you with a clang. The iron stair winds down into a warm, humming dark, and the heartbeat you have been hearing since the Works is louder now, almost close enough to touch."),
    SAY("Reya", "Tomas's key is warm. It's been warm the whole way. Like it knows where it's going."),
    SAY("Lyra", "It does. It is a very old key, and you are being led by it."),
    SAY("Kenji", "Then let's go and meet whatever is at the bottom."),
    ACT("flag", key="eh_arrive"),
    ACT("follow", t=1.2),
]
OBJECTIVES = [
    {"unless": "eh_captain", "text": "Descend the valve stair and get past Captain Rhenn at the inner gate."},
    {"unless": "eh_parley", "text": "Cross the Gallery of Names and enter the Emberheart chamber."},
    {"unless": "eh_regent", "text": "Defeat the Ember Regent guarding the Heart."},
    {"unless": "eh_fate", "text": "Decide the fate of Queen Maelis."},
    {"unless": "eh_end", "text": "See it through at the Heart."},
    {"text": "The Heart burns for itself. Climb out into the dawn and see what the city will make of it."},
]

scene = {
    "story": True, "name": "The Emberheart", "kit": "", "tile": 4,
    "autorun": [dict(unless="eh_arrive", cine=True, actions=ARRIVE)], "objectives": OBJECTIVES,
    "music": {"url": MUSIC + "15. Volcanic Crater.mp3"},
    "pieces": T.P, "colliders": T.COL, "decals": T.DEC, "npcs": NPCS, "events": EVENTS,
    "spawn": {"x": 0, "z": 52}, "bounds": BOUNDS, "playerHeight": 2.4,
    "camera": {"pitch": 24, "dist": 30},
    "light": {"dir": [-0.4, -1, -0.3], "color": [0.85, 0.62, 0.42], "ambient": [0.3, 0.24, 0.22]},
    "fog": {"color": [0.3, 0.17, 0.12], "near": 28, "far": 105},
    "sky": {"type": "layers", "base": {"type": "gradient", "stops": [[0, "#1a0f0c"], [0.5, "#4a2a1b"], [1, "#8a4a26"]]}, "layers": []},
    "fx": [{"type": "embers", "amount": 0.4}],
    "encounters": {"rate": 64, "level": [30, 34], "level_rel": [0, 2], "pool": ["flame_imp", "iron_golem", "cursed_knight", "stone_gargoyle"],
                   "zones": [{"x": 0, "z": 42, "w": 28, "d": 36, "safe": True},
                             {"x": 0, "z": -18, "w": 50, "d": 80, "rate": 60, "pool": ["flame_imp", "iron_golem", "cursed_knight", "stone_gargoyle"]},
                             {"x": 0, "z": -100, "w": 66, "d": 80, "safe": True}],
                   "text": "Embers stir in the dark..."},
}

if __name__ == "__main__":
    out = os.path.join(sys.argv[1] if len(sys.argv) > 1 else HERE, "heart.json")
    with open(out, "w", encoding="utf-8", newline="") as f:
        json.dump(scene, f, ensure_ascii=False, separators=(",", ":"))
    print("heart.json:", len(T.P), "pieces,", len(T.COL), "colliders,", len(NPCS), "npcs,", len(EVENTS), "events")

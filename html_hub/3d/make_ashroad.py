"""Builds html_hub/3d/ashroad.json: "The Road of Ash", Veyra Chapter B (claude/veyra-road-of-ash-oct-13.md).
Continues make_veyra.py: the north road out of Cinder Hollow runs 240 leagues to Solgard. This scene compresses it to three stops (south to north):
  1. Wayfarers' Rest (z ~ 20): a burnt inn, a cookfire, refugees turned back from the capital, the deserter Garrick, Old Maud, the courier Dov.
  2. Harrow's Ford (z ~ -62): a frozen village and a Tithe Spire that pipes its warmth up the road to Solgard's Sunwall. Fight the Spire Warden, then choose: cut the conduit or leave it.
  3. The Toll Bridge and the Cold Gate (z ~ -130 .. -166): the Lamp Wagon convoy (children, "kindling intake") passes, Quartermaster Hesk holds the bridge, and Reya's Underdrain hatch lies under the east pier.
Layout: x east, z south, the camera looks north. The arrival from Cinder Hollow is at the south end (0, 62); a look-back event returns there.
Flags: ar_arrive ar_wagon ar_warden (Spire Warden beaten) ar_spire_done (+ ar_spire_off | ar_spire_left) ar_hesk (Hesk beaten) ar_end (hatch opened, Chapter B complete) ac1..ac4 (chests)
Run:  python make_ashroad.py [outdir]   (needs kenhouse.py next to it; re-running overwrites hand edits made in /builder3d)"""
import json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kenhouse

KEN = kenhouse.KEN
GC, ST, PA, DG, GEN = ("/assets/3D/GodCity/", "/assets/3D/Stylized/", "/assets/3D/Paradise/", "/assets/3D/Dungeon/", "/assets/3D/Generated/")
S = kenhouse.S
MUSIC = "/assets/Music/mp3/"
rng = random.Random(9137)
T = kenhouse.Town(PA)
put, ken, block = T.put, T.ken, T.block
SAY = lambda who, text, **k: dict(type="say", who=who, text=text, **k)
ACT = lambda _ty, **k: dict(type=_ty, **k)
NPCS, EVENTS = [], []
BOUNDS = dict(minX=-34, maxX=34, minZ=-178, maxZ=68)


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


def ruin(x, z, r):
    """a burnt home: four half walls, a charred post, a rubble block"""
    for k, (dx, dz) in enumerate(((-2, -1.5), (2, -1.5), (-2, 1.5), (2, 1.5))):
        ken(("wall-fortified-half" if k % 2 else "wall-half"), x + dx, z + dz, r + 90 * (k % 2), 0, S * rng.uniform(0.8, 1.0))
    ken("column-damaged", x, z, r + 30, 0, S * 1.2)
    block(x, z, 5.0, 4.5)


# ------------------------------------------------------------------ ground (cracked paving under the ash) and the rim of the world
for gx in range(-2, 2):
    for gz in range(-9, 4):
        put(GC + "SM_ground_20x20", gx * 20 + 10, gz * 20 + 10, 0, -0.5, 1)
for i in range(120):                                   # cliffs and rock mounds close both sides of the road
    z = rng.uniform(-186, 76)
    side = rng.choice((-1, 1))
    put(ST + "SM_Cliff_0%d" % rng.randint(1, 2), side * rng.uniform(37, 46), z, rng.randint(0, 359), -0.2, rng.uniform(1.2, 2.3))
for i in range(90):                                    # burnt posts and dead trunks off the verge
    x, z = rng.choice((-1, 1)) * rng.uniform(26, 36), rng.uniform(-176, 66)
    if rng.random() < 0.6: ken("column-damaged", x, z, rng.randint(0, 359), 0, S * rng.uniform(0.8, 1.5))
    else: put(ST + "SM_TrunkTree", x, z, rng.randint(0, 359), 0, rng.uniform(1.4, 3.0))
for i in range(70):
    ken("bricks", rng.choice((-1, 1)) * rng.uniform(5, 30), rng.uniform(-170, 62), rng.randint(0, 359), 0, S * rng.uniform(0.35, 0.8))
# the mile posts: one black post every 15 m, every fourth carries a name
for i in range(16):
    z = 56 - i * 15
    put(ST + "SM_Stylized_Fence_01", -5.5, z, 90, 0, 0.8)

# ------------------------------------------------------------------ the south end: the way back to Cinder Hollow
event("ar_back", "The road south", 0.0, 66.2, [
    SAY("", "Behind you the north road runs back down to the garrison and the roofs of Cinder Hollow, a few lamps in the ash."),
    dict(type="choice", who="Kenji", text="Go back to Cinder Hollow?", options=[
        dict(label="Return to Cinder Hollow", actions=[ACT("fade", to="black", t=1.0), ACT("warp", scene="veyra", x=0, z=-53, fresh=True)]),
        dict(label="Keep walking north", actions=[ACT("end")])])],
    "Look back down the road", 12.0, 2.4)

# ------------------------------------------------------------------ 1. Wayfarers' Rest (z 36 .. 4)
ruin(-16, 22, 10)                                                    # what is left of the inn
ruin(-24, 10, 70)
put(ST + "SM_Stylized_Bonfire", 9.5, 22.0, 0, 0, 1.2); glow(9.5, 22, 7, [1, 0.6, 0.3, 0.5])
put(ST + "SM_Stylized_Wagon", -4.0, 32.0, 15, 0, 1.0); block(-4.0, 32.0, 2.4, 4.6)
put(ST + "SM_Stylized_Wagon", 17.0, 8.0, 160, 0, 1.0); block(17.0, 8.0, 2.4, 4.6)
for (x, z, r) in ((-22, 30, 90), (21, 28, 270), (24, 14, 250)):
    put(GC + "SM_market_tent_0%d" % (1 + int(abs(x)) % 3), x, z, r, 0, 1.0); block(x, z, 4.6, 8.0)
for (x, z) in ((12.5, 25.0), (6.5, 25.5), (8.0, 18.5), (13.0, 19.0)):
    put(ST + "SM_Stylized_Box_var2", x, z, rng.randint(0, 359), 0, 1.0 if rng.random() < .5 else 0.9)
put(ST + "SM_Stylized_Table_A", 4.0, 16.0, 0, 0, 1.1); block(4.0, 16.0, 2.6, 1.3)
glow(-16, 22, 6, [1, 0.45, 0.2, 0.2])
chest("ac1", -30.0, 28.0, dict(gold=1300, shards=22, items={"potion": 3, "ether": 1}))
chest("ac2", 29.0, 4.0, dict(gold=1500, shards=24, items={"antidote": 3}))

npc("maud", "Old Maud", "Keeper of the Rest", "Elder", -6.0, 20.0, reach=5.0, actions=[
    SAY("Old Maud", "Fire is free. Water is free. Questions cost a coin. (I am joking. Mostly.) Sit, you look like people who have been walking since the ring."),
    SAY("Old Maud", "I have kept this Rest since before the Ashfall. Pilgrims, then traders, then refugees. Now I mostly keep the ones the Cold Gate sends back."),
    SAY("Old Maud", "Three days north the road runs through Harrow's Ford. A fine village, once. Then the Queen's engineers put a spire on the hill, and the Ford has been frozen since the thaw failed.", **{"unless": "ar_warden"}),
    SAY("Old Maud", "Funny thing. Every night the Ford freezes harder, the Sunwall burns brighter. I am old, not stupid.", **{"unless": "ar_warden"}),
    SAY("Old Maud", "You went to the Ford. Is it true what they say, that someone finally stood up to the Spire?", **{"if": "ar_warden", "unless": "ar_spire_done"}),
    SAY("Old Maud", "They say the Ford's chimneys are smoking again. Whatever you did, the Rest is yours, any night, as long as I live.", **{"if": "ar_spire_off"}),
    SAY("Old Maud", "You walked past the Spire and left it humming. I am not saying you were wrong. I am saying I would not want to be the one explaining that to a frozen child.", **{"if": "ar_spire_left", "unless": "ar_spire_off"})])
npc("garrick", "Garrick", "Deserter", "Warden", 14.0, 26.0, tint=[0.85, 0.85, 0.95, 1], actions=[
    SAY("Garrick", "Do not salute. I stopped being that. I walked out of Solgard seventeen days ago, still wearing the coat. Maud made me burn the rest."),
    SAY("Garrick", "They put me on the door of the Works. Night shift. Nobody tells you what is behind it, but the children walk in through the front and nobody walks out through the front."),
    SAY("Garrick", "I never carried a lantern down there. You do not need one. The little ones glow when they are tired, and they are always tired, and the glow goes into the pipes that go up to the wall."),
    SAY("Reya", "...How old?", **{"if": "vy_join"}),
    SAY("Garrick", "Ten, twelve. Sometimes younger. They call it kindling. I am sorry. I should have said something. I only ever put down my spear.", **{"if": "vy_join"}),
    SAY("Kenji", "Where are they taken in?", **{"if": "vy_join"}),
    SAY("Garrick", "Cold Gate, the main road, under writ of the Works. If you want in without a writ, ask a courier. I hear a woman called Reya knows a door.", **{"if": "vy_join"})])
npc("tessa", "Tessa", "Refugee", "Townee", 3.5, 11.0, actions=[
    SAY("Tessa", "My boy is eight. We reached the Cold Gate in the spring and the gate-captain said, third ring only. We had no writ.", **{"unless": "ar_spire_off"}),
    SAY("Tessa", "So I turned back. There is a wall of light on the horizon and I could not walk through the door of it with my son. Tell me that is not the whole story of this kingdom.", **{"unless": "ar_spire_off"}),
    SAY("Tessa", "They say the Ford is warm. I may take Jory there. Thank you, stranger.", **{"if": "ar_spire_off"})])
npc("dov", "Dov", "Courier", "Farmer", -16.5, 9.0, tint=[0.95, 1.0, 0.9, 1], actions=[
    SAY("Dov", "Reya! Still alive, still insulting people, good. Let me guess. You are taking the Underdrain.", **{"if": "vy_join"}),
    SAY("Reya", "Is the east pier still open?", **{"if": "vy_join"}),
    SAY("Dov", "Under the old toll bridge, a hatch behind the east pier. Three knocks, then two. The garrison there now is a Quartermaster who counts everything twice. I would not stop for his questions.", **{"if": "vy_join"}),
    SAY("Reya", "I never do.", **{"if": "vy_join"})])
event("ar_rest", "Cookfire", 9.0, 24.8, [
    SAY("", "Maud's fire. People nod at you and move over without being asked. The party rests a while, and nobody mentions payment."),
    dict(type="rest")], "Rest by the fire", 3.4, 2.6)

# ------------------------------------------------------------------ 2. Harrow's Ford and the Tithe Spire (z -34 .. -96)
T.house(-24.0, -46.0, 90, [(0, 0, 3, 2)], wall="stone", col="cream", roof="brown")
T.house(-22.0, -72.0, 90, [(0, 0, 3, 2)], wall="stone", col="cream", roof="brown")
ruin(-28, -84, 40)
ruin(-14, -86, 120)
put(ST + "SM_Stylized_Well", -12.0, -60.0, 0, 0, 1.2); block(-12.0, -60.0, 3.0, 2.4)
for z in (-38, -44, -50, -56, -62, -68, -74, -80):
    put(ST + "SM_Stylized_Fence_01", -7.5, z, 90, 0, 1.0)
glow(-24, -46, 7, [0.5, 0.7, 1, 0.30], hide="ar_spire_off"); glow(-22, -72, 7, [0.5, 0.7, 1, 0.30], hide="ar_spire_off"); glow(-12, -60, 6, [0.55, 0.75, 1, 0.30], hide="ar_spire_off")
glow(-24, -46, 7, [1, 0.62, 0.3, 0.55], show="ar_spire_off"); glow(-22, -72, 7, [1, 0.62, 0.3, 0.55], show="ar_spire_off"); glow(-12, -60, 6, [1, 0.6, 0.3, 0.5], show="ar_spire_off")
# the Tithe Spire on its hill (east of the road)
SPX, SPZ = 17.0, -66.0
put(DG + "SM_dg_dais", SPX, SPZ, 0, 0, 1.5)
put(DG + "SM_dg_crystal", SPX, SPZ, 0, 0.6, 3.4, spec="H:ar_spire_off")
put(DG + "SM_dg_crystal", SPX, SPZ, 0, 0.6, 3.4, spec="S:ar_spire_off")        # same crystal; the dark look comes from the missing light below
block(SPX, SPZ, 3.2, 3.2)
for k in range(4):
    a = k * math.pi / 2 + math.pi / 4
    x, z = SPX + 6.2 * math.cos(a), SPZ + 6.2 * math.sin(a)
    put(DG + "SM_dg_pillar", x, z, 0, 0, 1.1); block(x, z, 1.4, 1.4)
glow(SPX, SPZ, 10, [0.75, 0.9, 1, 0.55], hide="ar_spire_off")
glyph(SPX, SPZ, 5.2, [0.7, 0.9, 1, 0.95], 35, hide="ar_spire_off")
glyph(SPX, SPZ, 9.0, [0.7, 0.9, 1, 0.55], -20, hide="ar_spire_off")
for k in range(9):                                   # the conduit: a line of cold light from the Spire up the road to the north
    glow(SPX - k * 1.2, SPZ - 8 - k * 7.5, 3.4, [0.7, 0.88, 1, 0.45], hide="ar_spire_off")
# the Ford's barricade across the road (north of the village): carts, pews and doors. Elder Wen lets travellers pass once the Spire has been dealt with (ar_spire_done)
for k, bx in enumerate((-27, -15, -3, 9, 21, 31)):
    put(ST + "SM_Stylized_Wagon", bx, -94.0, 90 + rng.choice((-8, 0, 8)), 0, 1.0, "ar_spire_done")
for k in range(15):
    put(ST + "SM_Stylized_Fence_01", -32 + k * 4.6, -95.2 + rng.uniform(-0.3, 0.3), 90, 0, 1.0, "ar_spire_done")
for bx in (-20, -9, 3, 14, 26):
    put(ST + "SM_Stylized_Box_var1", bx, -92.6, rng.randint(0, 359), 0, 1.4, "ar_spire_done")
T.COL.append(dict(x=0.0, z=-94.0, w=68.0, d=2.6, hideIf="ar_spire_done"))
event("ar_barricade", "The Ford's barricade", 0.0, -91.0, [
    SAY("", "Carts, church pews and doors lashed across the whole width of the road. A board wired to the top is painted in a child's hand: THE FORD DECIDES WHO PASSES. ASK ELDER WEN."),
    SAY("Reya", "They built it against the Crown's tithe-men. It has never come down. It will come down when Wen says.")],
    "Read the board", 14.0, 3.0, hide="ar_spire_done")
chest("ac3", -30.0, -98.0, dict(gold=1700, shards=26, items={"potion": 4, "ether": 2}))

npc("wen", "Elder Wen", "Harrow's Ford", "Elder", -14.0, -50.0, reach=5.0, actions=[
    SAY("Elder Wen", "The hill is not ours any more. The spire came with a writ and eleven engineers, five winters ago. They said it would 'share the warmth fairly'.", **{"unless": "ar_spire_done"}),
    SAY("Elder Wen", "It shares ours. Every hearth in the Ford goes cold at dusk. We burn furniture. We burned the church pews in the second winter. I do not know what we will burn this year.", **{"unless": "ar_spire_done"}),
    SAY("Elder Wen", "You are going up that hill? A warden walks it. It does not sleep and it does not talk. Go gently. Or do not go at all.", **{"unless": "ar_warden"}),
    SAY("Elder Wen", "The warden is down. That is more than anyone has done. I will ask only one thing of you, stranger. Whatever you decide up there, decide it knowing our names.", **{"if": "ar_warden", "unless": "ar_spire_done"}),
    SAY("Elder Wen", "The barricade is coming down. Go on. If you ever come back through the Ford, there will be a place at the table.", **{"if": "ar_spire_done"}),
    SAY("Elder Wen", "The ovens are lit. Lio fell asleep in a patch of sun on the kitchen floor and I did not wake him. I had forgotten that the floor could be warm.", **{"if": "ar_spire_off"}),
    SAY("Elder Wen", "You left it running. I understand why. I think you are a kind person who did not want to be the one to break a thing you do not understand. The Ford will survive another winter. Some of us will not.", **{"if": "ar_spire_left", "unless": "ar_spire_off"})])
npc("lio", "Lio", "Child", "Townee", -9.5, -66.0, actions=[
    SAY("Lio", "Look, I can make a ghost! Haaah. See?", **{"unless": "ar_spire_off"}),
    SAY("Lio", "Gran says the hill eats the warm. I think it is a dragon. A small one. Are you going to fight it?", **{"unless": "ar_warden"}),
    SAY("Lio", "My toes are BACK! I can feel my toes!", **{"if": "ar_spire_off"})])
npc("nessa", "Nessa", "Villager", "Farmer", -17.5, -80.0, actions=[
    SAY("Nessa", "I used to bake. I still do, if you can call a hot stone and a sack of ash-flour baking.", **{"unless": "ar_spire_off"}),
    SAY("Nessa", "Take this. A real loaf. First in five years. Eat it before you do anything brave.", **{"if": "ar_spire_off"})])
npc("spire_warden", "Spire Warden", "Tithe Engine", "Draven", SPX - 5.0, SPZ + 8.0, tint=[0.6, 0.85, 1.35, 1], h=3.3, reach=5.2, hide="ar_warden", actions=[
    SAY("", "A tall construct of grey plate, standing between the Spire and the road. Frost runs off its shoulders like water. It does not speak. When you approach, its chest opens like a lantern and a cold white light spills out."),
    SAY("Lyra", "Tithe engine. The sigil on its breastplate is the Crown's. The one beneath it is much older.", ),
    SAY("Kenji", "Then it has no choice about what it does. That does not mean I do."),
    dict(type="battle", key="ar_warden", pool=["iron_golem"], level_rel=[2, 4], elite=1.35)])
event("ar_spire", "The Tithe Spire", SPX - 4.2, SPZ, [
    SAY("", "The Spire hums at the pitch of a held breath. Up close, you can see the conduit: a seam of white light that leaves the crystal and runs north, up the road, dwindling into the dark. A brass plate on the plinth reads: THIRD RING TITHE. HARROW'S FORD: 61%. TO THE SUNWALL, WITH THE CROWN'S GRATITUDE.", **{"unless": "ar_spire_done"}),
    SAY("Lyra", "It is not a heater and it is not a mine. It takes warmth from the Ford, the way a well takes water, and sends it to Solgard. The sixty-one is how much of the Ford's heat it has taken.", **{"unless": "ar_spire_done"}),
    SAY("", "Beneath the Crown's engraving, in cold, even lettering that is not carved so much as written on the metal: THIRD RING TITHE RAISED BY COUNCIL. PRESSURE APPLIED. SUBJECT PROCEEDING.", **{"unless": "ar_spire_done"}),
    SAY("Lyra", "That is the lettering from the Watcher's Ledger in Eldergate. The same hand.", **{"unless": "ar_spire_done"}),
    SAY("Miya", "Kenji, your hand.", **{"unless": "ar_spire_done"}),
    SAY("Kenji", "I know. The mark has been warm since the Warden fell. As though it recognises whoever wrote this.", **{"unless": "ar_spire_done"}),
    SAY("Reya", "He did not build the Spire. The Crown did. He found it already hungry and leaned on it.", **{"unless": "ar_spire_done"}),
    SAY("Lyra", "I can open the seam. I would rather not guess what is on the far end of a conduit that has run for five winters.", **{"unless": "ar_spire_done"}),
    SAY("", "The Spire's heart is bare under your hand. You could sever the conduit and give the Ford its warmth back. Or you could walk on and leave it humming.", **{"if": "ar_spire_left", "unless": "ar_spire_off"}),
    dict(type="choice", who="Kenji", text="What do you do with the Spire?", options=[
        dict(label="Sever the conduit (the Ford is warm again)", actions=[
            ACT("flash"), ACT("shake", t=1.2, amp=0.3),
            SAY("", "Kenji sets his marked hand on the seam and pulls. Gold light runs through the white, and the white tears. Somewhere far to the north, a long way off, a bell stops tolling."),
            SAY("Reya", "Solgard will feel that by nightfall."),
            SAY("Kenji", "Good."),
            SAY("Miya", "...Somewhere at the other end of that line, there is a hearth that just went cold."),
            SAY("Kenji", "There are always people at the other end of it. Funny how the ones doing the counting are never in the count."),
            SAY("Lyra", "That is not an answer to her, Kenji."),
            SAY("Kenji", "I know."),
            ACT("flag", key="ar_spire_off"), ACT("flag", key="ar_spire_done"),
            dict(type="chest", loot=dict(gold=900, shards=18, items={"potion": 3}), text="The Ford leaves a bundle at the Spire's foot as thanks. Inside:")]),
        dict(label="Leave it and decide later", actions=[
            SAY("Kenji", "We do not know what dies if we pull it. I am not going to guess with someone else's life."),
            SAY("Reya", "Tell that to the Ford."),
            SAY("Kenji", "I will. When I know what I am telling them."),
            SAY("Miya", "You are not wrong. I just wish being careful did not feel so much like walking away."),
            ACT("flag", key="ar_spire_left"), ACT("flag", key="ar_spire_done")]),
        dict(label="Step back for now", actions=[ACT("end")])])],
    "Examine the Tithe Spire", 5.0, 5.0, show="ar_warden", hide="ar_spire_off")

# ------------------------------------------------------------------ 3. The Toll Bridge and the Cold Gate (z -104 .. -170)
# the dry river bed and the old toll bridge
for k in range(-6, 7):
    put(PA + "SM_rock_01", k * 5.0, -140.0, rng.randint(0, 359), -1.2, rng.uniform(0.25, 0.4))
put(ST + "SM_Stylized_Arch", 0, -132, 0, 0, 1.15); block(-3.4, -132, 1.8, 1.4); block(3.4, -132, 1.8, 1.4)
fx, fz, _ = T.house(-17.0, -128.0, 90, [(0, 0, 2, 2)], wall="stone", col="cream", roof="brown")                       # the Quartermaster's tollhouse
put(ST + "SM_Stylized_Table_A", -9.0, -122.0, 0, 0, 1.1); block(-9.0, -122.0, 2.6, 1.3)
for (x, z) in ((-7.0, -127.0), (-8.5, -126.0), (-7.5, -124.5)):
    put(ST + "SM_Stylized_Box_var1", x, z, rng.randint(0, 359), 0, 1.3); block(x, z, 1.3, 1.3)
for fxp in (-6.0, 6.0):
    put(ST + "SM_Stylized_Flag_Var2", fxp, -134.0, 0, 0, 2.6); block(fxp, -134.0, 0.5, 0.5)
put(DG + "SM_dg_brazier", -3, -127); put(DG + "SM_dg_flame", -3, -127, 0, 1.55, 1.0); block(-3, -127, 1.1, 1.1); glow(-3, -127, 7, [1, 0.5, 0.25, 0.4])
put(DG + "SM_dg_brazier", 3, -127); put(DG + "SM_dg_flame", 3, -127, 0, 1.55, 1.0); block(3, -127, 1.1, 1.1); glow(3, -127, 7, [1, 0.5, 0.25, 0.4])
# the east pier and the Underdrain hatch
put(DG + "SM_dg_dais", 25.0, -136.0, 0, 0, 0.8); block(25.0, -136.0, 2.4, 2.4)
glyph(25.0, -136.0, 3.2, [1, 0.62, 0.3, 0.9], 30, show="ar_hesk")
glow(25.0, -136.0, 7, [1, 0.62, 0.3, 0.35], show="ar_hesk")
chest("ac4", 30.0, -120.0, dict(gold=1900, shards=30, items={"potion": 3, "ether": 2, "antidote": 2}))
# the Lamp Wagon (slides north when the convoy passes; the pieces and its guards vanish once ar_wagon is set)
for (dx, dz) in ((0.0, 0.0), (0.0, -5.4)):
    T.P.append([ST + "SM_Stylized_Wagon", 4.0 + dx, -88.0 + dz, 0, 0, 1.15, "ar_wagon", "lw"])
# the Cold Gate: the outer wall of Solgard, closed
CZ = -168.0
nx = int((BOUNDS["maxX"] - BOUNDS["minX"]) / S)
for i in range(nx + 1):
    x = BOUNDS["minX"] + i * S + 0.5 * S
    if x > BOUNDS["maxX"] + 1: break
    if abs(x) < 4.4: continue
    ken("wall-fortified", x, CZ, 0, 0, S); block(x, CZ, S, 1.2)
ken("wall-fortified-gate", -3.0, CZ, 0, 0, S * 0.6); ken("wall-fortified-gate", 3.0, CZ, 0, 0, S * 0.6); block(0, CZ, 9.0, 1.4)
for sx in (-9.0, 9.0):
    ken("tower-base", sx, CZ, 0, 0, S * 1.5); ken("tower", sx, CZ, 0, S * 1.5, S * 1.5); ken("tower-top", sx, CZ, 0, S * 3.0, S * 1.5); block(sx, CZ, 4.4, 4.4)
for fxp in (-5.5, 5.5):
    put(ST + "SM_Stylized_Flag_Var1", fxp, CZ + 3.0, 0, 0, 2.6); block(fxp, CZ + 3.0, 0.5, 0.5)
glow(0, CZ - 6, 40, [1.0, 0.92, 0.72, 0.55])                             # the Sunwall glow beyond the gate
glow(0, CZ - 24, 60, [1.0, 0.95, 0.8, 0.45])
glow(0, CZ + 4, 14, [1.0, 0.9, 0.7, 0.35])

npc("hesk", "Quartermaster Hesk", "Royal Quartermaster", "Draven", 0.0, -122.5, tint=[1.25, 0.9, 0.5, 1], h=2.8, reach=5.0, hide="ar_hesk", actions=[
    SAY("Quartermaster Hesk", "Halt. State your writ, your province, your cargo and the number of persons in your party. Count aloud."),
    SAY("Kenji", "No writ. No province. Four of us."),
    SAY("Quartermaster Hesk", "Five. You left one out, a quiet one, at the back. I count people. It is what I am for. Every wagon that crosses this bridge, I count. Every soul that does not, I count, too."),
    SAY("Reya", "Hesk. You are the one who counts the children at the Cold Gate."),
    SAY("Quartermaster Hesk", "Of course I am. Do you imagine the kindling counts itself? Forty-one thousand and twelve, as of this dawn. A tidy figure."),
    SAY("Kenji", "You are talking about children."),
    SAY("Quartermaster Hesk", "I am talking about a margin. The Sunwall holds because there is a number. If the number falls, nine million people freeze. I did not choose the number. I only refuse to lie about it."),
    SAY("Miya", "That is a very clean way of saying you do not look."),
    SAY("Quartermaster Hesk", "Step off the bridge, healer. I would prefer you not be counted among the dead."),
    dict(type="battle", key="ar_hesk", pool=["cursed_knight"], level_rel=[2, 4], elite=1.5)])
npc("hesk_b", "Quartermaster Hesk", "Royal Quartermaster", "Draven", -1.5, -122.5, tint=[1.25, 0.9, 0.5, 1], h=2.8, reach=5.0, show="ar_hesk", actions=[
    SAY("Quartermaster Hesk", "...You are not what I expected the Mother's light to look like. Go on. Take the east pier. I did not see you. I will count you tomorrow, and the number will be wrong.", **{"unless": "ar_end"}),
    SAY("Quartermaster Hesk", "A counsellor joined the council the winter the thaw failed. No face on the record, no name. He speaks, and the Queen listens. 'Count the saved,' he said. 'Not the lost.' It made so much sense, I wrote it above my door.", **{"unless": "ar_end"}),
    SAY("", "His eyes drop to the back of Kenji's hand, and stay there.", **{"unless": "ar_end"}),
    SAY("Quartermaster Hesk", "There is a gold line on your hand. The last writ the Queen signed has the same line in the margin, drawn in no ink I know. Unsigned. Whatever you are, I do not think you belong to him. Pass.", **{"unless": "ar_end"}),
    SAY("Quartermaster Hesk", "The east pier. Three knocks, then two. The Underdrain does not forgive a wrong count.", **{"if": "ar_end"})])
npc("toll1", "Waiting refugee", "Turned back", "Townee", 12.0, -112.0, actions=[
    SAY("Waiting refugee", "I have a nephew in the Works. The Crown wrote that he is 'serving'. I do not know how a six-year-old serves."),
    SAY("Waiting refugee", "I have been here eleven days. Hesk says his number is full.")])
npc("toll2", "Waiting refugee", "Turned back", "Farmer", -11.0, -112.5, actions=[
    SAY("Waiting refugee", "They let in the wagons with the lamps. Never the ones with the families. I used to ask why. I stopped asking."),
    SAY("Waiting refugee", "I think I do not want the answer. I think I know it.")])
npc("gate_guard", "Gate Sentry", "Royal Garrison", "Warden", 7.5, -163.0, tint=[1.1, 0.75, 0.75, 1], actions=[
    SAY("Gate Sentry", "The Cold Gate opens for writs of the Works. Not for you. Not for anyone with a face I do not recognise. Please do not make me make you leave."),
    SAY("Gate Sentry", "I am not the cruel one. I am the one who stands here.")])

event("ar_hatch", "The Underdrain hatch", 25.0, -139.3, [
    SAY("", "Behind the east pier, under the arch of the old toll bridge, a hatch the colour of the river bed. A courier's mark has been burned into the iron: three short, two long.", **{"unless": "ar_end"}),
    SAY("Reya", "Three, then two. My brother taught it to me before the soldiers took him. I have knocked it for six years with no one on the other side.", **{"unless": "ar_end"}),
    SAY("", "Reya knocks. Three. Then two. After a long moment, something answers from below, two soft taps, and the hatch breathes out a column of warm air that smells of oil and bread and lamp smoke.", **{"unless": "ar_end"}),
    SAY("Reya", "That is the drain keeper. It has been the same code for nine years. Somebody has been keeping the door.", **{"unless": "ar_end"}),
    SAY("Lyra", "Beyond that hatch is the city the plaque called the last one standing. We should rest first, and be sure.", **{"unless": "ar_end"}),
    dict(type="choice", who="Kenji", text="Go down into the Underdrain?", options=[
        dict(label="Descend into the Underdrain (Solgard)", actions=[
            SAY("Kenji", "Stay close. Whatever we find, we find it together.", **{"unless": "ar_end"}),
            SAY("", "The party goes down the iron rungs one at a time. Behind you the hatch closes with a hollow sound, and the Sunwall's light slides off the door like water off a slate.", **{"unless": "ar_end"}),
            ACT("flag", key="ar_end"),
            ACT("fade", to="black", t=1.2), ACT("warp", scene="solgard", x=0.0, z=50.0, fresh=True)]),
        dict(label="Not yet", actions=[ACT("end")])])],
    "Knock on the hatch", 5.0, 3.6, show="ar_hesk")
event("ar_sign", "Mile post", -3.8, 52.0, [
    SAY("Mile post", "SOLGARD, 231 LEAGUES. The wood is carved all over with names, and under them, in a child's hand: 'LOOK UP. IT IS STILL THERE.'")], "Read the post", 3.2, 2.4)
event("ar_gate", "The Cold Gate", 0.0, CZ + 5.0, [
    SAY("", "The Cold Gate is a slab of iron six men high, ringed with sun-gold. It is warm to the touch, which no iron has any right to be in this air. Light bleeds from the cracks around its edges like honey.", ),
    SAY("Reya", "It opens for writs and for wagons with lamps. That is all it opens for."),
    SAY("Lyra", "And for whoever the people on the other side decide is a person. Let us not give them the chance to decide.")], "Look at the gate", 10.0, 3.2, show="ar_spire_done")

# ------------------------------------------------------------------ the Lamp Wagon (a touch cutscene on the road)
WAGON = [
    ACT("cine", on=True),
    ACT("walk", who="player", x=-9.0, z=-100.0, speed=5),
    ACT("cam", x=2, z=-98, yaw=0, pitch=34, dist=26, t=1.4),
    SAY("", "Wheels, from the south. Iron-shod, slow, and heavy. A column of Crown guards walks with them, lantern-bearers with their hoods up, and behind them a long wagon with a canvas hood and a row of narrow windows set too high to see out of."),
    SAY("Reya", "That is not a grain wagon."),
    ACT("slide", grp="lw", dx=0, dy=0, dz=-50, t=11, wait=False),
    SAY("", "As the wagon passes, the canvas shifts. A small hand rests flat against one of the windows. Then another, and another, a whole row of them, pressed to the glass, and each one throws a thin gold light across the road."),
    SAY("Miya", "They're glowing."),
    SAY("", "Tied to the tailboard is a ticket of stamped brass: ROYAL WORKS. KINDLING INTAKE. THIRD RING. LOT 311."),
    SAY("Reya", "Tomas."),
    ACT("shake", t=0.8, amp=0.2),
    SAY("", "She is moving before anyone can stop her. Kenji catches her arm at the last step, and she nearly takes his hand off."),
    SAY("Kenji", "Reya. There are thirty guards. If you run at them, they do not have to be cruel, only careful."),
    SAY("Reya", "He was ELEVEN. He is seventeen now. He is in one of those boxes or in a pipe or in a ledger, and I am standing in the road."),
    SAY("Kenji", "You are standing in the road with four people who are going the same way. Hold on to that for a little longer."),
    ACT("wait", t=1.0),
    SAY("", "The wagon rolls into the dark ahead and dims like a coal. The Cold Gate is out there, and the white sky beyond it."),
    SAY("Reya", "...Kindling. They wrote it on a ticket. Like it was firewood."),
    SAY("Lyra", "The ledger at Eldergate said the Mind's pressure on Veyra was 'applied'. It did not say whose hand held the lever."),
    SAY("Kenji", "Whoever it is, I would like to ask them."),
    ACT("flag", key="ar_wagon"),
    ACT("follow", t=1.2),
]
event("ar_wagon_cs", "The Lamp Wagon", 0.0, -102.0, WAGON, "", 18.0, 3.0, hide="ar_wagon", trigger="touch", once=True)

# ------------------------------------------------------------------ arrival scene
ARRIVE = [
    ACT("cine", on=True),
    dict(type="music", url=MUSIC + "15. Volcanic Crater.mp3"),
    ACT("fade", to="clear", t=2.5, wait=False),
    ACT("cam", x=0, z=40, yaw=0, pitch=36, dist=26, t=0),
    SAY("", "The Road of Ash runs north out of the garrison and does not turn for two hundred and forty leagues, or so the milestones claim. Every league has a black post. Every tenth has a name carved into it, each in a different hand. Travellers' names."),
    ACT("cam", x=0, z=-40, yaw=0, pitch=28, dist=44, t=5.0),
    SAY("Reya", "Nine days on foot to Solgard if nothing stops you. Something always does."),
    SAY("Lyra", "The Eldergate plaques said the cities fell one by one. Everyone says Solgard is the last. Nobody says why it is still standing."),
    SAY("Miya", "Is that the sun? Over the hills?"),
    SAY("Reya", "The Sunwall. Twenty winters, and it has never once set. Tomas told me, before they took him, that it was the only warm thing in the world. He was eleven. He was proud of it."),
    SAY("Kenji", "Then we walk."),
    ACT("flag", key="ar_arrive"),
    ACT("follow", t=1.4),
]

OBJECTIVES = [
    {"unless": "ar_arrive", "text": "Walk the Road of Ash north."},
    {"unless": "ar_warden", "text": "Reach Harrow's Ford, three days up the road, where a Tithe Spire has frozen the village. (Old Maud, at the Wayfarers' Rest, knows the way.)"},
    {"unless": "ar_spire_done", "text": "The Spire Warden is down. Decide what to do with the Tithe Spire."},
    {"unless": "ar_hesk", "text": "Elder Wen has opened the Ford's barricade. Reach the old toll bridge before the Cold Gate. Quartermaster Hesk holds it."},
    {"unless": "ar_end", "text": "Hesk has stood aside. Find the Underdrain hatch behind the east pier and knock three, then two."},
    {"text": "The Underdrain hatch behind the east pier leads down to Solgard."},
]

scene = {
    "story": True, "name": "The Road of Ash", "kit": "", "tile": 4,
    "autorun": [dict(unless="ar_arrive", cine=True, actions=ARRIVE)], "objectives": OBJECTIVES,
    "music": {"url": MUSIC + "15. Volcanic Crater.mp3"},
    "pieces": T.P, "colliders": T.COL, "decals": T.DEC, "npcs": NPCS, "events": EVENTS,
    "spawn": {"x": 0, "z": 62}, "bounds": BOUNDS, "playerHeight": 2.4,
    "camera": {"pitch": 24, "dist": 30},
    "light": {"dir": [-0.4, -1, -0.3], "color": [0.55, 0.5, 0.48], "ambient": [0.28, 0.27, 0.32]},
    "fog": {"color": [0.26, 0.24, 0.24], "near": 28, "far": 110},
    "sky": {"type": "layers", "base": {"type": "gradient", "stops": [[0, "#1b1a1e"], [0.45, "#3d3633"], [1, "#8a7660"]]}, "layers": []},
    "fx": [{"type": "snow", "amount": 0.75, "color": "#b9b3ab", "wind": 0.18, "speed": 0.7}, {"type": "embers", "amount": 0.14}],
    "encounters": {"rate": 60, "level": [26, 30], "level_rel": [0, 2], "pool": ["frost_wraith", "flame_imp", "storm_harpy", "bandit_rogue", "dark_cultist", "cursed_knight"],
                   "zones": [{"x": 0, "z": 52, "w": 40, "d": 30, "safe": True}, {"x": 0, "z": 20, "w": 68, "d": 38, "safe": True},
                             {"x": -18, "z": -62, "w": 24, "d": 54, "safe": True}, {"x": 14, "z": -64, "w": 22, "d": 22, "safe": True},
                             {"x": 0, "z": -128, "w": 68, "d": 24, "safe": True}, {"x": 0, "z": -160, "w": 68, "d": 20, "safe": True}],
                   "text": "Something moves in the ash..."},
}

if __name__ == "__main__":
    out = os.path.join(sys.argv[1] if len(sys.argv) > 1 else HERE, "ashroad.json")
    with open(out, "w", encoding="utf-8", newline="") as f:
        json.dump(scene, f, ensure_ascii=False, separators=(",", ":"))
    print("ashroad.json:", len(T.P), "pieces,", len(T.COL), "colliders,", len(NPCS), "npcs,", len(EVENTS), "events")

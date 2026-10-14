"""Builds html_hub/3d/veyra.json: "Cinder Hollow", the first portal world's outer province (Veyra, the Kingdom of Ash).
Chapter A of the Veyra storyline (claude/eldergate-veyra-oct-13.md): arrival through the Eldergate ring, Reya's ambush and the medicine she is protecting, the royal garrison
that confiscated the village's supplies (Captain Dorgan, an elite fight), the return to the sick house, and Reya joining the party.
Layout (x east, z south, the camera looks north): arrival ring (south, z 34), Cinder Hollow village (centre), the sick house (west), the north road, and the garrison compound (north, z -42).
Flags: vy_arrive (ambush scene seen) vy_quest hg_captain (Dorgan beaten) vy_supplies (medicine recovered) vy_returned / vy_join (delivered; Reya recruited) vc1.. (chests)
Run:  python make_veyra.py [outdir]   (needs kenhouse.py next to it; re-running overwrites hand edits made in /builder3d)"""
import json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kenhouse

KEN = kenhouse.KEN
GC, ST, PA, DG, GEN = ("/assets/3D/GodCity/", "/assets/3D/Stylized/", "/assets/3D/Paradise/", "/assets/3D/Dungeon/", "/assets/3D/Generated/")
S = kenhouse.S
MUSIC = "/assets/Music/mp3/"
rng = random.Random(4721)
T = kenhouse.Town(PA)
put, ken, block = T.put, T.ken, T.block
SAY = lambda who, text, **k: dict(type="say", who=who, text=text, **k)
ACT = lambda _ty, **k: dict(type=_ty, **k)
NPCS, EVENTS = [], []


def glow(x, z, r, c, show=None, hide=None):
    d = dict(type="glow", x=round(x, 2), z=round(z, 2), r=r, color=c)
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


def event(id, name, x, z, actions, prompt="Examine", w=3.0, d=3.0, show=None, hide=None, trigger="talk"):
    e = dict(id=id, name=name, x=x, z=z, w=w, d=d, trigger=trigger, prompt=prompt, actions=actions)
    if show: e["showIf"] = show
    if hide: e["hideIf"] = hide
    EVENTS.append(e)


def chest(id, x, z, loot):
    put(GEN + "SM_TreasureChest", x, z, rng.randint(0, 359), 0, 1.0); block(x, z, 1.4, 1.4)
    event(id, "Treasure chest", x, z, [dict(type="flag", key=id), dict(type="chest", loot=loot, text="You prise the chest open and find")], "Open the chest", 3.4, 3.4, hide=id)


# ------------------------------------------------------------------ ground (cracked paving under the ash) and the rim of the world
for gx in range(-3, 3):
    for gz in range(-3, 3):
        put(GC + "SM_ground_20x20", gx * 20 + 10, gz * 20 + 10, 0, -0.5, 1)
# a rim of rock mounds and dead posts
for i in range(70):
    a = rng.uniform(0, math.tau)
    rx, rz = 58 * math.cos(a), 58 * math.sin(a) * 0.95 - 8
    if abs(rx) < 47 and -52 < rz < 40: continue
    put(ST + "SM_Cliff_0%d" % rng.randint(1, 2), rx, rz, rng.randint(0, 359), -0.2, rng.uniform(1.2, 2.2))
for i in range(80):
    x, z = rng.uniform(-48, 48), rng.uniform(-56, 40)
    if abs(x) < 36 and -34 < z < 36: continue                   # keep the village, road and arrival clear
    if abs(x) < 18 and z < -34: continue                         # and the garrison
    ken("column-damaged", x, z, rng.randint(0, 359), 0, S * rng.uniform(0.8, 1.5))                       # burnt posts stand where the forest was
for i in range(40):
    x, z = rng.uniform(-48, 48), rng.uniform(-56, 40)
    if abs(x) < 36 and -34 < z < 36: continue
    put(ST + "SM_TrunkTree", x, z, rng.randint(0, 359), 0, rng.uniform(1.4, 3.0))
for i in range(30):
    put(PA + "SM_rock_01", rng.uniform(-46, 46), rng.uniform(-55, 40), rng.randint(0, 359), 4, rng.uniform(0.2, 0.45))
for i in range(60):
    x, z = rng.uniform(-36, 36), rng.uniform(-30, 33)
    ken("bricks", x, z, rng.randint(0, 359), 0, S * rng.uniform(0.35, 0.8))                              # ash-drifted rubble

# ------------------------------------------------------------------ the arrival ring (south): an old Eldergate arch and nine broken standing stones
AX, AZ = 0.0, 40.0
put(ST + "SM_Stylized_Arch", AX, AZ, 0, 0, 1.2); block(AX - 3.4, AZ, 1.8, 1.4); block(AX + 3.4, AZ, 1.8, 1.4)
put(DG + "SM_dg_dais", AX, AZ - 3.0, 0, 0, 0.7)
for k in range(8):
    a = k * math.tau / 8
    x, z = AX + 5.5 * math.cos(a), AZ - 3.0 + 5.5 * math.sin(a) * 0.8
    if z > 40.5: continue
    ken("column-damaged", x, z, 20 * k, 0, S * 1.2); block(x, z, 1.0, 1.0)
glow(AX, AZ - 3, 8, [1, 0.62, 0.3, 0.30])
T.DEC.append(dict(type="glyph", x=AX, z=AZ - 3.0, r=4.2, spin=30, color=[1, 0.62, 0.3, 0.95]))
event("vy_ring", "The Eldergate ring", AX, AZ - 6.4, [
    SAY("", "The ring hums when the mark on Kenji's hand is near. Through it, faintly, there is a pale hall and a long gate with its bars drawn back."),
    dict(type="choice", who="Kenji", text="Go back through the ring to Eldergate?", options=[
        dict(label="Return to Eldergate (and Dawnwatch above it)", actions=[ACT("fade", to="black", t=1.2), ACT("warp", scene="eldergate", x=4.4, z=-40.5, fresh=True)]),
        dict(label="Stay in Veyra", actions=[ACT("end")])])],
    "Look into the ring", 6.0, 3.2)

# ------------------------------------------------------------------ the village: a burnt-out Cinder Hollow, a well, the sick house (west)
put(ST + "SM_Stylized_Well", 0, 6, 0, 0, 1.3); block(0, 6, 3.2, 2.6)
put(ST + "SM_Stylized_Scarecrow", 3.4, 4.0, 200, 0, 1.2)
put(ST + "SM_Stylized_Bonfire", -17.5, 3.5, 0, 0, 1.1); glow(-17.5, 3.5, 6, [1, 0.6, 0.3, 0.45])
# the sick house (intact, the only roof left)
fx, fz, _ = T.house(-25.0, -2.0, 90, [(0, 0, 3, 2)], wall="stone", col="cream", roof="brown")
glow(-22, -2, 5, [1, 0.75, 0.45, 0.40])
# burnt homes: half-walls and fallen beams
HOMES = [(-12, -10, 10), (11, -9, 70), (13, 9, 150), (-11, 13, 30), (22, 2, 100), (24, -12, 20), (-31, 12, 60), (32, 16, 5), (-4, -16, 120), (5, 18, 40)]
for (x, z, r) in HOMES:
    for k, (dx, dz) in enumerate(((-2, -1.5), (2, -1.5), (-2, 1.5), (2, 1.5))):
        ken(("wall-fortified-half" if k % 2 else "wall-half"), x + dx, z + dz, r + 90 * (k % 2), 0, S * rng.uniform(0.8, 1.0))
    ken("column-damaged", x, z, r + 30, 0, S * 1.2)
    block(x, z, 5.0, 4.5)
    glow(x, z, 4, [1, 0.45, 0.2, 0.18])
# broken fences, a burnt cart, scattered crates
for i in range(14):
    put(ST + "SM_Stylized_Fence_01", -28 + i * 4.4, 27.5 + rng.uniform(-0.8, 0.8), rng.choice([0, 0, 15, -12]), 0, 1.0)
put(ST + "SM_Stylized_Wagon", 12, -22, 70, 0, 1.0); block(12, -22, 4.4, 2.2)
put(ST + "SM_Stylized_Wagon", -9, 22, 200, 0, 1.0); block(-9, 22, 2.2, 4.4)
for (x, z) in ((10.0, 12.0), (-14.0, -3.0), (4.0, -4.0), (-6.0, 8.0)):
    put(ST + "SM_Stylized_Box_var2", x, z, rng.randint(0, 359), 0, 1.4)
# the north road: fences either side and a milestone
for i in range(8):
    z = -14 - i * 2.8
    put(ST + "SM_Stylized_Fence_01", -4.8, z, 90, 0, 1.0); put(ST + "SM_Stylized_Fence_01", 4.8, z, 90, 0, 1.0)
chest("vc1", -30.0, 28.0, dict(gold=700, shards=12, items={"potion": 2}))
chest("vc2", 33.0, -4.0, dict(gold=900, shards=14, items={"antidote": 2}))
chest("vc3", -33.0, -22.0, dict(gold=1100, shards=20, items={"ether": 1}))

# ------------------------------------------------------------------ the royal garrison checkpoint (north)
GZ0, GZ1, GX0, GX1 = -50.0, -34.0, -14.0, 14.0
nx = int((GX1 - GX0) / S)
for i in range(nx + 1):
    x = GX0 + i * S + 0.5 * S
    if x > GX1: break
    ken("wall-fortified", x, GZ0, 0, 0, S); block(x, GZ0, S, 1.0)                    # back wall
    if abs(x) > 4.5: ken("wall-fortified", x, GZ1, 0, 0, S); block(x, GZ1, S, 1.0)   # front wall with a gate gap
nz = int((GZ1 - GZ0) / S)
for j in range(nz + 1):
    z = GZ0 + j * S + 0.5 * S
    if z > GZ1: break
    for sx in (GX0, GX1):
        ken("wall-fortified", sx, z, 90, 0, S); block(sx, z, 1.0, S)
for (x, z) in ((GX0, GZ0), (GX1, GZ0), (GX0, GZ1), (GX1, GZ1)):
    ken("tower-base", x, z, 0, 0, S * 1.4); ken("tower", x, z, 0, S * 1.4, S * 1.4); ken("tower-top", x, z, 0, S * 2.8, S * 1.4); block(x, z, 4.0, 4.0)
ken("wall-fortified-gate", -3.5, GZ1, 0, 0, S * 0.6); ken("wall-fortified-gate", 3.5, GZ1, 0, 0, S * 0.6)
for (x, z, r) in ((-10, -38, 90), (10, -38, 270), (-10, -47, 90)):
    put(GC + "SM_market_tent_0%d" % (1 + int(abs(x)) % 3), x, z, r, 0, 1.0); block(x, z, 4.6, 8.0)
for fxp in (-6.5, 6.5):
    put(ST + "SM_Stylized_Flag_Var2", fxp, GZ1 + 1.5, 0, 0, 2.6); block(fxp, GZ1 + 1.5, 0.5, 0.5)
put(DG + "SM_dg_brazier", -3, -44); put(DG + "SM_dg_flame", -3, -44, 0, 1.55, 1.0); block(-3, -44, 1.1, 1.1); glow(-3, -44, 7, [1, 0.5, 0.25, 0.4])
put(DG + "SM_dg_brazier", 3, -44); put(DG + "SM_dg_flame", 3, -44, 0, 1.55, 1.0); block(3, -44, 1.1, 1.1); glow(3, -44, 7, [1, 0.5, 0.25, 0.4])
put(ST + "SM_Stylized_Table_A", 8, -46, 0, 0, 1.2); block(8, -46, 2.7, 1.3)
# the stacked supplies (the village's, tagged for the crown)
for (x, z) in ((6.5, -43.0), (8.2, -43.5), (7.3, -41.4)):
    put(ST + "SM_Stylized_Box_var1", x, z, rng.randint(0, 359), 0, 1.5); block(x, z, 1.4, 1.4)
put(ST + "_Stylized_Barrel", 9.5, -41.5, 0, 0, 1.3)
glow(7.4, -42.5, 6, [0.9, 0.9, 1.0, 0.3], show="hg_captain", hide="vy_supplies")

# ------------------------------------------------------------------ NPCs
# Reya (the ambush: she starts here; the arrival scene walks her over)
npc("reya", "Reya", "Courier", "Yulia", 10.0, 22.0, hide="vy_supplies", tint=[1.15, 0.95, 0.85, 1], actions=[
    SAY("Reya", "You are still here. Do not take it personally. I have just never watched anyone walk toward the garrison on purpose.", **{"if": "vy_arrive", "unless": "vy_supplies"}),
    SAY("Reya", "North road, past the burnt wagon. Forty men and a captain called Dorgan. If you are going, go. If you are not, stop standing where I can see you.", **{"if": "vy_arrive", "unless": "vy_supplies"}),
])
npc("reya_b", "Reya", "Courier", "Yulia", -18.5, 3.5, show="vy_supplies", hide="vy_join", tint=[1.15, 0.95, 0.85, 1], actions=[
    SAY("Reya", "Take it to Marta. She is in the sick house, west of the well. Go.", **{"unless": "vy_returned"})])
npc("marta", "Marta", "Village Healer", "Elder", -21.0, 1.5, reach=5.0, actions=[
    SAY("Marta", "The fever came with the ash. Cinderlung, we call it. The lungs fill, then the heart tires. We had medicine and the crown took it, for the capital, they said.", **{"unless": "vy_supplies"}),
    SAY("Marta", "Reya brings what she can. It is never enough. Please, if you have any way...", **{"unless": "vy_supplies"}),
    # --- the delivery scene
    ACT("cine", on=True, **{"if": "vy_supplies", "unless": "vy_returned"}),
    ACT("cam", x=-20, z=1, yaw=0, pitch=36, dist=14, t=1.2, **{"if": "vy_supplies", "unless": "vy_returned"}),
    SAY("Kenji", "From the garrison. Every bottle that was taken, and the bread.", **{"if": "vy_supplies", "unless": "vy_returned"}),
    SAY("Marta", "...Child. Child, hold this one up to the light. Is it the green bottle? It is. It is!", **{"if": "vy_supplies", "unless": "vy_returned"}),
    SAY("Miya", "Let me. I can measure it out, and I will sit with each of them.", **{"if": "vy_supplies", "unless": "vy_returned"}),
    SAY("", "Miya kneels between the cots and goes down the row with bottle and cup, and for the first time since you arrived, someone in the sick house laughs.", **{"if": "vy_supplies", "unless": "vy_returned"}),
    SAY("Reya", "You went into forty men for a village that is not yours.", **{"if": "vy_supplies", "unless": "vy_returned"}),
    SAY("Kenji", "I said I would bring it back.", **{"if": "vy_supplies", "unless": "vy_returned"}),
    SAY("Reya", "People say that. Heroes say that. The ones who mean it die, and the ones who do not leave. You are the first I have seen who walked there and walked back.", **{"if": "vy_supplies", "unless": "vy_returned"}),
    SAY("Reya", "There was a ledger in the crate with the sacks. Evacuation lists from this province. I read it twice on the way back.", **{"if": "vy_supplies", "unless": "vy_returned"}),
    SAY("Reya", "My brother's name is on it. Tomas. Eleven. 'Transferred to Solgard, royal works.' The soldiers took the children from the outer villages six years ago. They said it was for safety. I have been trying to follow that road ever since.", **{"if": "vy_supplies", "unless": "vy_returned"}),
    SAY("Lyra", "Solgard. The capital. The plaque said it was the last city standing.", **{"if": "vy_supplies", "unless": "vy_returned"}),
    SAY("Kenji", "Then that is where we are going.", **{"if": "vy_supplies", "unless": "vy_returned"}),
    SAY("Reya", "I want to save one person. You want to save everyone you can. I do not know which of us is the fool.", **{"if": "vy_supplies", "unless": "vy_returned"}),
    SAY("Kenji", "Then we have a road in common.", **{"if": "vy_supplies", "unless": "vy_returned"}),
    SAY("Reya", "...I know every smuggler's path between here and the capital. I will not promise you my trust. But I will walk it with you.", **{"if": "vy_supplies", "unless": "vy_returned"}),
    SAY("", "Reya joins your party! Equip her before you head out.", **{"if": "vy_supplies", "unless": "vy_returned"}),
    dict(type="recruit", name="Reya", **{"if": "vy_supplies", "unless": "vy_returned"}),
    ACT("flag", key="vy_returned", **{"if": "vy_supplies", "unless": "vy_returned"}),
    ACT("flag", key="vy_join", **{"if": "vy_supplies", "unless": "vy_join"}),
    ACT("follow", t=1.2, **{"if": "vy_returned"}),
    SAY("Marta", "Go with the Mother's light, all of you. The road north is not kind, and the capital is worse. But I think... I think you may be what we stopped hoping for.", **{"if": "vy_returned"}),
])
npc("hale", "Hale", "Farmer", "Farmer", 6.0, 12.5, actions=[
    SAY("Hale", "The wheat went grey before the harvest. The sky has been the colour of a dead coal for twenty winters. My father said it would pass. His grave is behind the chapel.", **{"unless": "vy_returned"}),
    SAY("Hale", "Reya's been feeding the whole hollow out of the garrison's wagons. They say she has stolen from the queen herself. If there is a hero in this village, it is a courier with a knife.", **{"unless": "vy_returned"}),
    SAY("Hale", "The sick are better today. Whatever you did, thank you.", **{"if": "vy_returned"})])
npc("pip", "Pip", "Child", "Townee", -4.0, 14.5, actions=[
    SAY("Pip", "Are you from the capital? Mama said everyone good went to the capital. Are you good?", **{"unless": "vy_returned"}),
    SAY("Pip", "Reya said you are not soldiers. Soldiers do not have funny hands.", **{"unless": "vy_returned"}),
    SAY("Pip", "Mama is breathing easier! Reya says you went and got the medicine. Can I hold your sword?", **{"if": "vy_returned"})])
npc("patient1", "Sick villager", "Cinderlung", "Townee", -22.0, -4.5, actions=[SAY("Sick villager", "...I keep hearing a bell. Is it morning?", **{"unless": "vy_returned"}), SAY("Sick villager", "I can breathe. I can breathe.", **{"if": "vy_returned"})])
npc("patient2", "Sick villager", "Cinderlung", "Elder", -20.2, -0.5, actions=[SAY("Sick villager", "Cold... so cold... Do not let the fires go out.", **{"unless": "vy_returned"}), SAY("Sick villager", "The warm has come back into my hands.", **{"if": "vy_returned"})])
# the garrison
npc("dorgan", "Captain Dorgan", "Royal Garrison", "Draven", 0.0, -42.0, tint=[1.15, 0.7, 0.7, 1], h=2.8, reach=5.0, hide="hg_captain", actions=[
    SAY("Captain Dorgan", "Halt. By order of Her Majesty's Quartermaster, this road is closed. Supplies requisitioned for the capital's defence. Turn around or add your bones to the road."),
    SAY("Kenji", "There are children dying of fever in the village down the road. Those supplies are theirs."),
    SAY("Captain Dorgan", "There are millions in Solgard. Do the arithmetic. I did, and it kept me awake for a year. Then I stopped doing it."),
    dict(type="battle", key="hg_captain", pool=["cursed_knight"], level_rel=[1, 3], elite=1.3)])
npc("dorgan_b", "Captain Dorgan", "Royal Garrison", "Draven", 0.0, -42.0, show="hg_captain", hide="vy_supplies", tint=[1.15, 0.7, 0.7, 1], h=2.8, reach=5.0, actions=[
    SAY("Captain Dorgan", "...Take the sacks. The crates behind the table. Orders said every province beyond the third ring is 'beyond saving'. I did not read the orders closely. I read them often."),
    SAY("Captain Dorgan", "Tell Reya the soldier who did not shoot her last winter says... never mind. Take them. Go.")])
npc("soldier1", "Garrison Soldier", "Royal Garrison", "Warden", -8.0, -41.0, tint=[1.1, 0.75, 0.75, 1], actions=[
    SAY("Garrison Soldier", "I only carry what I am told to carry. Do not look at me like that. I have a sister in Solgard.", **{"unless": "hg_captain"}),
    SAY("Garrison Soldier", "The Captain has stood down. I will not stop you. I... I will not tell anyone which way you went.", **{"if": "hg_captain"})])
npc("soldier2", "Garrison Soldier", "Royal Garrison", "Warden", 12.0, -36.5, tint=[1.1, 0.75, 0.75, 1], actions=[
    SAY("Garrison Soldier", "We were told the northern villages were evacuated. Then why does the road have so many footprints going the wrong way?", **{"unless": "hg_captain"}),
    SAY("Garrison Soldier", "Solgard has a wall of light, they say. It feeds on the provinces. I only learned that last month.", **{"if": "hg_captain"})])

# ------------------------------------------------------------------ events
event("vy_rest", "Cookfire", -17.5, 5.2, [
    SAY("", "A banked fire, a kettle that never quite boils, and a patch of floor warmer than the rest. The party rests a while. Wounds close and breath comes easy.", ),
    dict(type="rest")], "Rest by the fire", 3.2, 2.4)
event("vy_crates", "Supply crates", 7.4, -40.0, [
    SAY("", "Behind the table, three crates stamped with the crown's sun and a clerk's scrawl: CINDER HOLLOW. REQUISITIONED. FOR THE CAPITAL.", ),
    SAY("", "Inside, sacks of grain, bottles of green tincture and a ledger, thick with names. 'EVACUATION PROGRAMME, OUTER PROVINCES. Transferred to Solgard, royal works.'"),
    SAY("Miya", "Take it all. The ledger, too. Someone will want to know where these people were sent."),
    ACT("flag", key="vy_supplies"),
    dict(type="chest", loot=dict(gold=500, shards=8, items={"potion": 3, "antidote": 2}), text="Among the crown's stores you also find")],
    "Search the crates", 3.6, 3.6, show="hg_captain", hide="vy_supplies")
event("vy_road", "The Road of Ash", 0.0, -55.0, [
    SAY("", "Beyond the garrison, the north road runs into the ash and does not turn. A bell tolls slowly in the distance. Solgard is out there, past the abandoned provinces and whatever the failing Emberheart has made of them."),
    dict(type="choice", who="Kenji", text="Take the Road of Ash north?", options=[
        dict(label="Walk the Road of Ash", actions=[ACT("fade", to="black", t=1.2), ACT("warp", scene="ashroad", x=0, z=62.0, fresh=True)]),
        dict(label="Not yet", actions=[ACT("end")])])],
    "Look up the road", 10.0, 3.0, show="vy_join")
event("vy_sign", "Milestone", -3.2, -10.5, [
    SAY("Milestone", "CINDER HOLLOW. SOLGARD, 240 LEAGUES. (Someone has scratched out the second line and written beneath it: 'TOO FAR.')")], "Read the milestone", 3.2, 2.4)

# ------------------------------------------------------------------ arrival scene (Reya's ambush)
ARRIVE = [
    ACT("cine", on=True),
    dict(type="music", url=MUSIC + "15. Volcanic Crater.mp3"),
    ACT("fade", to="clear", t=2.5, wait=False),
    ACT("cam", x=0, z=30, yaw=0, pitch=44, dist=22, t=0),
    SAY("", "Ash falls like snow, and like snow it does not melt. The ring hums once behind you and goes quiet. The air tastes of cold hearths."),
    SAY("Lyra", "Twenty winters into the Ashfall, the plaque said. Look at the sky. That is not weather."),
    SAY("Miya", "There is a bell tolling somewhere. Slowly, as though there were no reason to hurry."),
    SAY("Kenji", "Stay close. We know nothing about this place."),
    ACT("walk", who="reya", x=3.0, z=27.0, speed=7),
    SAY("Reya", "Hands where I can see them!"),
    ACT("flash"), ACT("shake"),
    SAY("", "A figure drops from the broken wall with a short blade, her face wrapped against the ash. She strikes before anyone can answer, and Kenji's sword is up before he has decided to raise it."),
    ACT("shake"),
    SAY("", "Three exchanges. On the fourth he turns her blade aside, steps inside her guard, and the knife spins away into the ash."),
    SAY("Reya", "Go on, then. Finish it. You royal dogs always do."),
    SAY("Kenji", "I am not a royal anything. And you are not a soldier, either. Soldiers do not guard a sack like that with their lives."),
    SAY("", "She is crouched over a canvas satchel, a corner torn open. Bottles of medicine. Hard bread wrapped in cloth."),
    SAY("Kenji", "Who is it for?"),
    SAY("Reya", "...Cinder Hollow. Down the road. The fever came with the storms. This morning the garrison took the last of the village's supplies 'for the capital'. This is what I stole back. It will last a day."),
    SAY("Reya", "You walked out of a ruin that has been dead since before I was born. Outsiders. Heroes. I know what heroes are. They arrive too late, promise what they cannot keep, and leave the rest of us to clean up."),
    SAY("Kenji", "I have not promised anything. Where is the garrison?"),
    SAY("Reya", "North road, an hour's walk. Forty men and a captain called Dorgan. The last outsider who asked them nicely is buried behind the chapel. Do not."),
    SAY("Kenji", "Then watch what I do instead of what I say."),
    SAY("Reya", "...Reya. Not that you will need it. Follow the road past the well. The sick house is on the west side. Go and look, before you decide to be brave."),
    ACT("flag", key="vy_arrive"),
    ACT("flag", key="vy_quest"),
    ACT("follow", t=1.2),
]

OBJECTIVES = [
    {"unless": "vy_supplies", "text": "Cinder Hollow's medicine was seized by the royal garrison. Recover it from the checkpoint on the north road."},
    {"unless": "vy_returned", "text": "Take the recovered medicine to Marta in the sick house, west of the well."},
    {"text": "Reya has joined you. Take the north road past the garrison: the Road of Ash leads to Solgard. The ring in the south leads back to Eldergate and Dawnwatch."},
]

scene = {
    "story": True, "name": "Cinder Hollow", "kit": "", "tile": 4,
    "autorun": [dict(unless="vy_arrive", cine=True, actions=ARRIVE)], "objectives": OBJECTIVES,
    "music": {"url": MUSIC + "15. Volcanic Crater.mp3"},
    "pieces": T.P, "colliders": T.COL, "decals": T.DEC, "npcs": NPCS, "events": EVENTS,
    "spawn": {"x": 0, "z": 28}, "bounds": {"minX": -50, "maxX": 50, "minZ": -58, "maxZ": 42}, "playerHeight": 2.4,
    "camera": {"pitch": 24, "dist": 30},
    "light": {"dir": [-0.4, -1, -0.3], "color": [0.5, 0.45, 0.45], "ambient": [0.27, 0.26, 0.31]},
    "fog": {"color": [0.24, 0.22, 0.22], "near": 28, "far": 105},
    "sky": {"type": "layers", "base": {"type": "gradient", "stops": [[0, "#1b1a1e"], [0.45, "#3a3533"], [1, "#6d6055"]]}, "layers": []},
    "fx": [{"type": "snow", "amount": 0.7, "color": "#b9b3ab", "wind": 0.15, "speed": 0.7}, {"type": "embers", "amount": 0.18}],
    "encounters": {"rate": 62, "level": [24, 28], "level_rel": [0, 2], "pool": ["frost_wraith", "flame_imp", "storm_harpy", "bandit_rogue", "dark_cultist"],
                   "zones": [{"x": 0, "z": 28, "w": 30, "d": 16, "safe": True}, {"x": 0, "z": 4, "w": 62, "d": 34, "safe": True},
                             {"x": 0, "z": -24, "w": 30, "d": 30, "rate": 58}, {"x": 0, "z": -44, "w": 34, "d": 20, "safe": True}],
                   "text": "Something moves in the ash..."},
}

if __name__ == "__main__":
    out = os.path.join(sys.argv[1] if len(sys.argv) > 1 else HERE, "veyra.json")
    with open(out, "w", encoding="utf-8", newline="") as f:
        json.dump(scene, f, ensure_ascii=False, separators=(",", ":"))
    print("veyra.json:", len(T.P), "pieces,", len(T.COL), "colliders,", len(NPCS), "npcs,", len(EVENTS), "events")

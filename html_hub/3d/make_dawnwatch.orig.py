"""Builds html_hub/3d/strange.json: "Dawnwatch", the ruined castle that becomes the main hub (chapter 6, after the Vault betrayal).
(The scene file keeps the id "strange" so the Vault's warp and the INNS entry did not have to change.)

One scene, four phases. The phase is a set of cumulative story flags:  (none) = I Ruins,  hp_2 = II Camp,  hp_3 = III Village,  hp_4 = IV Castle town.
Every piece, collider, glow, NPC and event carries a visibility rule, so the same scene shows the castle slowly being rebuilt:
    wall slot repaired in phase n :  ruin piece hideIf hp_n  /  wall piece showIf hp_n   (see slot_phase)
    tent in II, house from III    :  "S:hp_2,!hp_3"  /  "S:hp_3"
Suikoden-style growth: the mason Brannoch rebuilds a phase when (a) its townsfolk have been found (flags hr_<name>), (b) its story gate has
been cleared (hg_<name>) and (c) you pay gold and shards (/api/story/build). Residents move in and run the services:
    II  Camp         Orla (blacksmith -> heroes page)  Tilda (inn)
    III Village      Pell (item shop)  Wick (fishing)  the notice board (Dove)          needs hg_knight
    IV  Castle town  Sennet (archive / save)                                            needs hg_seer
Flags: hr_mason hr_orla hr_tilda hr_pell hr_wick hr_sennet hr_dove | hp_2 hp_3 hp_4 | hp_2_seen.. (reveal cutscene played) | hg_orla hg_pell hg_knight hg_seer (fights) | hc1.. (chests)
Run:  python make_dawnwatch.py   (re-running overwrites hand edits made in /builder3d)"""
import json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kenhouse

KEN = kenhouse.KEN
GC, ST, PA, DG, MGS, GEN = ("/assets/3D/GodCity/", "/assets/3D/Stylized/", "/assets/3D/Paradise/", "/assets/3D/Dungeon/", "/assets/3D/Megastructure/", "/assets/3D/Generated/")
S = kenhouse.S                        # one Kenney tile in metres
rng = random.Random(1307)
MUSIC = "/assets/Music/mp3/"


def spec_of(show=None, hide=None):
    """piece 7th-element rule from a showIf / hideIf flag spec"""
    if show and hide: return "S:%s,!%s" % (show, hide)
    if show: return "S:" + show
    if hide: return "H:" + hide
    return None


def phase_vis(frm=1, to=None):
    """(showIf, hideIf) for something that exists from phase `frm` until (not including) phase `to`"""
    show = ("hp_%d" % frm) if frm > 1 else None
    hide = ("hp_%d" % to) if to else None
    return show, hide


class Hub(kenhouse.Town):
    def __init__(self):
        super().__init__(PA)
        self.cur = (None, None)
        self.NP, self.EV = [], []

    def at(self, frm=1, to=None):
        self.cur = phase_vis(frm, to)
        return self

    def put(self, n, x, z, rot=0, y=0, sc=1, spec=None):
        sp = spec or spec_of(*self.cur)
        super().put(n, x, z, rot, y, sc, sp)

    def block(self, x, z, w, d, hide=None):
        c = {"x": round(x, 3), "z": round(z, 3), "w": round(w, 3), "d": round(d, 3)}
        show, hd = self.cur
        if show: c["showIf"] = show
        if hd: c["hideIf"] = hd
        self.COL.append(c)

    def glow(self, x, z, r, c, frm=1, to=None):
        d = dict(type="glow", x=round(x, 2), z=round(z, 2), r=r, color=c)
        show, hd = phase_vis(frm, to)
        if show: d["showIf"] = show
        if hd: d["hideIf"] = hd
        self.DEC.append(d)


T = Hub()
ken, put, block = T.ken, T.put, T.block
at = T.at

# ------------------------------------------------------------------ geometry
HALF = 35.0                               # the curtain wall stands on |x| = 35 and |z| = 35
NSLOT = 25                                # 25 tiles of 2.8 m = 70 m per side
GATE = {11, 12, 13}                       # slots left open as the south gate / north postern
SLOTX = [-HALF + S / 2 + S * i for i in range(NSLOT)]


def slot_phase(side, i):
    """the phase in which a ruined wall slot is repaired (1 = it never fell)"""
    v = random.Random(ord(side) * 131 + i * 17).random()
    return 1 if v < 0.34 else 2 if v < 0.52 else 3 if v < 0.82 else 4


WALLS = ("wall-fortified", "wall-fortified-window", "wall-fortified-door")
RUIN = ("wall-fortified-half", "column-damaged", "bricks", "wall-half")


def wall_slot(side, i):
    """one tile of the curtain wall: intact, or rubble that is replaced when the slot is repaired"""
    c = SLOTX[i]
    if side == "S": x, z, rot = c, HALF, 0
    elif side == "N": x, z, rot = c, -HALF, 0
    elif side == "W": x, z, rot = -HALF, c, 90
    else: x, z, rot = HALF, c, 90
    gate = (side in "SN") and i in GATE
    if gate:
        at(1)                                                                  # the open gate: a broken column either side
        if i == 11: ken("column-damaged", x - 0.4, z, rot, 0, S)
        if i == 13: ken("column-damaged", x + 0.4, z, rot, 0, S)
        return
    ph = slot_phase(side, i)
    wname = WALLS[1] if (i % 5 == 2) else WALLS[0]
    if ph == 1:
        at(1); ken(wname, x, z, rot, 0, S); block(x, z, S if rot == 0 else 1.0, 1.0 if rot == 0 else S)
    else:
        ruin = RUIN[(i + ord(side)) % len(RUIN)]
        at(1, ph); ken(ruin, x, z, rot, 0, S)
        if ruin == "bricks": ken("bricks", x + 0.6, z + 0.5, rot + 40, 0, S * 0.7)
        at(ph); ken(wname, x, z, rot, 0, S); block(x, z, S if rot == 0 else 1.0, 1.0 if rot == 0 else S)
    at(4); ken("battlement", x, z, rot, S, S)                                  # battlements crown the finished wall


# ------------------------------------------------------------------ ground (cracked paving), scenery, outskirts
for gx in range(-3, 3):
    for gz in range(-3, 3):
        T.pa = GC
        at(1); put(GC + "SM_ground_20x20", gx * 20 + 10, gz * 20 + 10, 0, -0.5, 1)
T.pa = PA

for side in "SNWE":
    for i in range(NSLOT): wall_slot(side, i)

# corner towers: (x, z, phase it is rebuilt in, stands as a stump until then)
for sx, sz, ph in ((-1, -1, 1), (1, -1, 3), (-1, 1, 2), (1, 1, 4)):
    x, z = sx * (HALF + 0.6), sz * (HALF + 0.6)
    if ph == 1:
        at(1); ken("tower-base", x, z, 0, 0, S * 1.5); ken("tower", x, z, 0, S * 1.5, S * 1.5); block(x, z, 4.4, 4.4)
    else:
        at(1, ph); ken("tower-base", x, z, 0, 0, S * 1.5); ken("column-damaged", x, z, 0, S * 1.5, S * 1.4); ken("bricks", x + 1.5, z + 1.2, 30, 0, S)
        at(ph); ken("tower-base", x, z, 0, 0, S * 1.5); ken("tower", x, z, 0, S * 1.5, S * 1.5); block(x, z, 4.4, 4.4)
    at(max(ph, 3)); ken("tower-top", x, z, 0, S * 3, S * 1.5)                             # a roofed tower once it is a village
    at(4); ken("battlement", x, z, 0, S * 3.0, S * 1.5)

# the south gate: rubble now, a gatehouse in phase IV
at(4); ken("wall-fortified-gate", 0, HALF, 0, 0, S); ken("tower-base", -8.8, HALF + 0.4, 0, 0, S * 1.4); ken("tower", -8.8, HALF + 0.4, 0, S * 1.4, S * 1.4); ken("tower-top", -8.8, HALF + 0.4, 0, S * 2.8, S * 1.4)
ken("tower-base", 8.8, HALF + 0.4, 0, 0, S * 1.4); ken("tower", 8.8, HALF + 0.4, 0, S * 1.4, S * 1.4); ken("tower-top", 8.8, HALF + 0.4, 0, S * 2.8, S * 1.4)
block(-8.8, HALF + 0.4, 4.0, 4.0); block(8.8, HALF + 0.4, 4.0, 4.0)
at(1, 4); ken("bricks", -3.2, HALF - 1.5, 20, 0, S); ken("bricks", 3.6, HALF + 1.0, 110, 0, S * 0.8)

# ------------------------------------------------------------------ the keep (north, around (0,-24))
KX, KZ = 0.0, -25.0
KCOLS = [-5.6, -2.8, 0, 2.8, 5.6]
KROWS = [-4.2, -1.4, 1.4, 4.2]
ring = []
for ci, cx in enumerate(KCOLS):
    for ri, rz in enumerate(KROWS):
        if ci in (0, len(KCOLS) - 1) or ri in (0, len(KROWS) - 1):
            ring.append((ci, ri, KX + cx, KZ + rz))
for k, (ci, ri, x, z) in enumerate(ring):
    front = ri == len(KROWS) - 1
    side_w = ci == 0 or ci == len(KCOLS) - 1
    rot = 180 if front else (0 if ri == 0 else (90 if ci == 0 else 270))
    n = WALLS[2] if (front and ci == 2) else (WALLS[1] if (k % 3 == 1) else WALLS[0])
    ph = 1 if k % 4 == 0 else 3                                                    # a few stretches still stand in phase I
    if ph == 1:
        at(1); ken(n, x, z, rot, 0, S)
    else:
        at(1, 3); ken(RUIN[k % 3], x, z, rot, 0, S)
        at(3); ken(n, x, z, rot, 0, S)
    at(1 if ph == 1 else 3); block(x, z, S - 0.1, S - 0.1) if not (front and ci == 2) else None
    at(4); ken("battlement", x, z, rot, S, S)
# scaffolding while it is being rebuilt (phase II)
at(2, 3)
for sx in (-9.5, 9.5):
    ken("structure-poles", KX + sx, KZ + 6.5, 0, 0, S); ken("structure", KX + sx, KZ + 6.5, 0, S, S * 0.9)
ken("structure-wall", KX - 3, KZ - 6.5, 0, 0, S); ken("structure-poles", KX + 3, KZ - 6.5, 0, 0, S)
for i in range(4): ken("bricks", KX - 8 + i * 5, KZ + 8.5, i * 40, 0, S * 0.8)
# the great tower behind the hall (phase IV) and banners
at(4)
ken("tower-base", KX, KZ - 11.5, 0, 0, S * 2.0); ken("tower", KX, KZ - 11.5, 0, S * 2.0, S * 2.0); ken("tower-top", KX, KZ - 11.5, 0, S * 4.0, S * 2.0); block(KX, KZ - 11.5, 5.8, 5.8)
for fx in (-7.5, 7.5): put(ST + "SM_Stylized_Flag_Var1", fx, KZ + 7.2, 0, 0, 2.6); block(fx, KZ + 7.2, 0.5, 0.5)
# the ruin before it: toppled columns and a cracked floor
at(1, 3)
for (x, z, r) in ((-6, -16.5, 20), (5.5, -17.5, 70), (-3, -13, 140), (2, -11.5, 0)): ken("column-damaged", KX + x, z, r, 0, S * 1.3)
for i in range(7): ken("bricks", rng.uniform(-9, 9), rng.uniform(-18, -10), rng.randint(0, 359), 0, S * rng.uniform(0.6, 0.9))
T.glow(0, -18, 7, [0.6, 0.7, 1.0, 0.28], 1, 3)
T.glow(0, -18, 9, [1.0, 0.85, 0.5, 0.30], 4)

# ------------------------------------------------------------------ camp (south courtyard): bonfire, crystal, tents, the builder's yard
at(1)
put(ST + "SM_Stylized_Bonfire", 0, 30, 0, 0, 1.6); block(0, 30, 2.0, 2.0); T.glow(0, 30, 7, [1, 0.62, 0.3, 0.5])
put(DG + "SM_dg_crystal", 7, 31, 0, 0, 2.0); block(7, 31, 1.4, 1.4); T.glow(7, 31, 6, [0.55, 0.85, 1, 0.3])
at(1, 3)                                                                       # the two survivors' tents come down once the village is built
for (x, z, r) in ((-9, 29, 90), (10, 27.5, 270)):
    put(GC + "SM_market_tent_03", x, z, r, 0, 1.1); block(x, z, 4.8, 4.0)
at(1)
put(ST + "SM_Stylized_Table_A", -6.5, 21, 0, 0, 1.1); block(-6.5, 21, 2.7, 1.3)
for (x, z) in ((-9.5, 19), (-3.5, 17.5), (-8.5, 16)):
    put(GC + "SM_construction_block_01", x, z, rng.randint(0, 359), 0, 1.2); block(x, z, 1.5, 1.5)
put(ST + "_Stylized_Barrel", -4, 19, 0, 0, 1.2); put(ST + "SM_Stylized_Box_var1", -2.5, 18.5, 20, 0, 1.2)
at(2, 3)                                                                       # phase II: a proper camp (struck again in III)
for (x, z, r) in ((-26, 7, 90), (-26, 22, 90), (26.5, 8, 270)):
    pass                                                                       # (the tents of the service lots are drawn below with the houses)
put(ST + "SM_Stylized_Bonfire", -17, 14, 0, 0, 1.3); T.glow(-17, 14, 6, [1, 0.62, 0.3, 0.45], 2, 3)
for i, (x, z) in enumerate(((-14, 27.5), (14, 22), (16, 31))):
    put(GC + ("SM_market_tent_02" if i % 2 else "SM_market_tent_01"), x, z, 90 if x < 0 else 270, 0, 1.0); block(x, z, 4.6, 8.0)
put(ST + "SM_Stylized_Wagon", 9, 14, 100, 0, 1.0); block(9, 14, 2.0, 4.4)
put(ST + "SM_Stylized_Fence_01", -12, 33, 0, 0, 1.0)
at(1)
# phase III: a square with a fountain and a well
at(1, 3)
put(KEN + "bricks", 0, 8, 10, 0, S * 1.2); put(KEN + "column-damaged", -2.2, 7, 35, 0, S); put(KEN + "bricks", 2.5, 9.5, 120, 0, S * 0.8); block(0, 8, 3.6, 3.6)
at(3)
put(ST + "SM_Stylized_Fountain", 0, 8, 0, 0, 1.5); block(0, 8, 6.4, 6.0); T.glow(0, 8, 8, [0.55, 0.85, 1.0, 0.25], 3)
put(ST + "SM_Stylized_Well", -14, 4, 0, 0, 1.3); block(-14, 4, 3.2, 2.6)
for (x, z) in ((-5.5, 13), (5.5, 13), (-5.5, 3), (5.5, 3)): put(ST + "SM_Stylized_Lamp_C", x, z, 0, 0, 2.4); block(x, z, 0.5, 0.5); T.glow(x, z, 5, [1, 0.85, 0.5, 0.45], 3)
at(4)
for (x, z, v) in ((-3.5, -9.8, 1), (3.5, -9.8, 2)): put(ST + "SM_Stylized_Flag_Var%d" % v, x, z, 0, 0, 2.6)
put(KEN + "wall-fortified-gate", 0, HALF, 0, 0, S)

# ------------------------------------------------------------------ the service lots. II: a tent, III: a house, IV: a better one
LOTS = {
    "smith": dict(x=-25.0, z=7.0, rot=90, blocks=[(0, 0, 3, 1)], roof="brown", wall="stone", col="cream", tent="SM_market_tent_02"),
    "inn":   dict(x=-25.0, z=21.0, rot=90, blocks=[(0, 0, 3, 2)], roof="red", wall="paint", col="cream", tent="SM_market_tent_01"),
    "shop":  dict(x=25.0, z=6.0, rot=270, blocks=[(0, 0, 3, 1)], roof="blue", wall="paint", col="sand", tent=None),
    "library": dict(x=22.0, z=-22.0, rot=0, blocks=[(0, 0, 3, 1), (S * 2, 0, 3, 2)], roof="brown", wall="stone", col="cream", tent=None),
}
for name, L in LOTS.items():
    frm = {"smith": 3, "inn": 3, "shop": 3, "library": 4}[name]
    if L["tent"]:
        at(2, 3); put(GC + L["tent"], L["x"], L["z"], L["rot"] + 90, 0, 1.05); block(L["x"], L["z"], 4.8, 8.4)
    at(frm)
    fx, fz, _ = T.house(L["x"], L["z"], L["rot"], L["blocks"], wall=L["wall"], col=L["col"], roof=L["roof"], spec=spec_of(*phase_vis(frm)))
# the library's ruin (until phase IV)
at(1, 4)
for (x, z, r) in ((15, -21, 15), (18, -26, 60), (25, -19.5, 100), (28.5, -24, 10), (21, -17, 150)):
    ken("column-damaged" if r % 2 else "wall-half", x, z, r, 0, S * 1.2)
for i in range(6): ken("bricks", rng.uniform(15, 29), rng.uniform(-27, -17), rng.randint(0, 359), 0, S * rng.uniform(0.6, 0.9))
block(22, -22, 13, 8)
# the smithy's forge fire and sign, the market stall, the inn lantern (III+)
at(3)
put(ST + "SM_Stylized_Bonfire", -21.0, 7.0, 0, 0, 0.9); T.glow(-21, 7, 4.5, [1, 0.5, 0.2, 0.55], 3)
put(ST + "SM_Stylized_Table_A", 21.0, 10.0, 90, 0, 1.0); block(21, 10, 1.4, 2.7); put(ST + "SM_Stylized_Basket", 21.0, 9.0, 0, 0, 1.2)
put(GC + "SM_market_tent_03", 20.5, 1.5, 270, 0, 1.0); block(20.5, 1.5, 4.0, 4.6)
put(ST + "SM_Stylized_Lamp_C", -21, 18.5, 0, 0, 2.4); T.glow(-21, 18.5, 5, [1, 0.85, 0.5, 0.45], 3)
# cottages (decor): III adds three, IV three more
COTT = [(-27, -6, 90, 3, "paint", "blue", "red"), (-27, -13.5, 90, 3, "paint", "sand", "brown"), (27, -6, 270, 3, "paint", "cream", "red"),
        (-27, 30, 90, 4, "paint", "sand", "red"), (27, 30, 270, 4, "paint", "blue", "brown"), (27, 20, 270, 4, "paint", "cream", "blue")]
for (x, z, rot, ph, wl, col, rf) in COTT:
    at(1, ph)
    ken("bricks", x, z, rot, 0, S * 1.0); ken("column-damaged", x + 1.8, z - 1.4, rot + 30, 0, S)
    at(ph)
    T.house(x, z, rot, [(0, 0, 2, 1)], wall=wl, col=col, roof=rf, spec=spec_of(*phase_vis(ph)))
# gardens and fences, phase IV polish
at(4)
for (x, z) in ((-14, 14), (14, 14)): put(GC + "SM_garden_8x8", x, z, 0, 0, 1.0)
for x in (-30, 30):
    for z in (-1, 12): put(ST + "SM_Stylized_Fence_01", x, z, 90, 0, 1.0)

# ------------------------------------------------------------------ pond (east): water, reeds, a fishing spot from phase III
for gx in range(4):
    for gz in range(3):
        at(1); ken("water", 21.0 + gx * S, 15.0 + gz * S, 0, -0.18, S)
block(21 + 1.5 * S, 15 + S, 4 * S - 0.6, 3 * S - 0.6)
at(1)
for i in range(10): put(ST + "SM_Wheat", 19.5 + rng.uniform(0, 14), 12.2 + rng.uniform(0, 1.2), 0, 0, 1.2)
at(3)
put(ST + "SM_Stylized_Boat", 22.8, 14.0, 80, 0, 1.0); put(ST + "SM_Stylized_Bench", 19.0, 17.5, 90, 0, 1.3); put(ST + "_Stylized_Barrel", 19.2, 20.5, 0, 0, 1.0)
T.glow(19.5, 18, 5, [1, 0.85, 0.5, 0.35], 3)

# ------------------------------------------------------------------ rubble, trees, overgrowth: heavier in phase I, cleared as the town grows
rubble = []
for i in range(46):
    x, z = rng.uniform(-33, 33), rng.uniform(-33, 30)
    if abs(x) < 9 and z > 14: continue                     # keep the camp clear
    rubble.append((x, z, rng.randint(0, 359), rng.uniform(0.5, 1.0)))
for i, (x, z, r, s) in enumerate(rubble):
    to = 2 + (i % 3)                                       # cleared in phase II, III or IV
    at(1, to); ken(RUIN[2] if i % 2 else "column-damaged", x, z, r, 0, S * s)
for i in range(60):
    x, z = rng.uniform(-34, 34), rng.uniform(-34, 34)
    at(1, 2 + (i % 3)); put(ST + ("SM_Grass_A" if i % 2 else "SM_Grass_B"), x, z, rng.randint(0, 359), 0, rng.uniform(1.2, 2.2))
for i in range(14):
    x, z = rng.uniform(-33, 33), rng.uniform(-33, 30)
    at(1, 3); put(GC + "SM_ivy_01", x, z, rng.randint(0, 359), 0, 1.5)
# the forest outside the walls
for i in range(70):
    a = rng.uniform(0, math.tau); rad = rng.uniform(41, 58)
    x, z = rad * math.cos(a) * 1.0, rad * math.sin(a) * 1.0
    if abs(x) < 36 and abs(z) < 36: continue
    at(1); put(ST + rng.choice(("Tree_02", "Tree_03", "Tree_04")), x, z, rng.randint(0, 359), 0, rng.uniform(1.0, 1.5));
for i in range(26):
    a = rng.uniform(0, math.tau); rad = rng.uniform(38, 50)
    x, z = rad * math.cos(a), rad * math.sin(a)
    if abs(x) < 36.5 and abs(z) < 36.5: continue
    at(1); put(GC + "SM_bush_0%d" % rng.randint(1, 4), x, z, rng.randint(0, 359), 0, rng.uniform(0.8, 1.3))
for (x, z) in ((-44, 0), (44, 6), (0, -46), (-40, 40), (41, -38)):
    at(1); put(PA + "SM_rock_01", x, z, rng.randint(0, 359), 4, 0.35)

# ------------------------------------------------------------------ the Sunken Stair (north-west ruin): the way down to the Eldergate Network, open from phase I
at(1)
put(DG + "SM_dg_dais", -20, -28, 0, 0, 0.6); block(-20, -28, 3.0, 3.0)
put(DG + "SM_dg_crystal", -22.6, -29.6, 20, 0, 1.0); put(DG + "SM_dg_crystal", -17.4, -29.6, 130, 0, 1.0)
for (x, z, r) in ((-24, -26, 40), (-16.5, -26.5, 100), (-21, -32, 10), (-18, -31.5, 160)): ken("column-damaged", x, z, r, 0, S * 1.1)
T.glow(-20, -28, 6, [1.0, 0.85, 0.45, 0.22], 1)
T.DEC.append(dict(type="glyph", x=-20, z=-28, r=3.6, spin=-20, color=[1, 0.8, 0.4, 0.9]))

# ------------------------------------------------------------------ NPCs, events
NPCS, EVENTS = [], []
SAY = lambda who, text, **k: dict(type="say", who=who, text=text, **k)
ACT = lambda _ty, **k: dict(type=_ty, **k)


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


def chest(id, x, z, loot, frm=None):
    T.cur = (None, None); put(GEN + "SM_TreasureChest", x, z, rng.randint(0, 359), 0, 1.0); block(x, z, 1.4, 1.4)
    event(id, "Treasure chest", x, z, [dict(type="flag", key=id), dict(type="chest", loot=loot, text="You prise the chest open and find")], "Open the chest", 3.4, 3.4, hide=id)


# ---- Brannoch the mason: the builder, the heart of the rebuild mechanic
B = "Brannoch"
REQ = {   # phase -> (cost, residents needed, gate flag, label)
    2: dict(cost=dict(gold=600, shards=12), need="hr_orla,hr_tilda", gate=None),
    3: dict(cost=dict(gold=1800, shards=35), need="hr_pell,hr_wick", gate="hg_knight"),
    4: dict(cost=dict(gold=4200, shards=70), need="hr_sennet,hr_dove", gate="hg_seer"),
}
PHASE_NAME = {2: "The Camp", 3: "The Village", 4: "The Castle Town"}
PHASE_PITCH = {
    2: "Tents and cookfires first: a forge for Orla, a hearth for Tilda. Not pretty. Warm.",
    3: "Real walls and a roof over every head. A market for Pell, a pier for Wick, a board for the young herald, and the keep standing again.",
    4: "The curtain wall whole, the gatehouse raised, the library roofed and the keep crowned. Dawnwatch as it was, if not better.",
}


def brannoch_talk():
    acts = []
    acts.append(SAY(B, "And one more thing, lad. In the north-west corner there is a paved ring I never could lift, dig under or chip. It hums when it thinks nobody is listening. Whoever put your mark on you, I would try your hand on it.", **{"if": "hr_mason", "unless": "eg_open"}))
    for p in (2, 3, 4):
        r = REQ[p]
        need = r["need"]
        stage = ("hp_%d,!hp_%d" % (p - 1, p)) if p > 2 else "!hp_2"            # the town stands at phase p-1 and phase p is not built yet
        cs = "%d gold and %d shards" % (r["cost"]["gold"], r["cost"]["shards"])
        acts.append(SAY(B, "Next is %s: %s" % (PHASE_NAME[p], PHASE_PITCH[p]), **{"if": stage}))
        acts.append(SAY(B, {2: "But it is no good raising walls for nobody. Orla and Tilda are still lost in the ruins: the smith somewhere in the west rubble, the innkeeper hiding in the old chapel cellar to the east.",
                            3: "But I will not raise a market with no merchant to fill it. Pell and Wick are still out there: a wagon stranded outside the south gate, and an angler by the east pond.",
                            4: "But a library needs a librarian and a town needs a voice. Sennet is hiding in the ruined library corner, and Dove keeps watch from the north-east tower."}[p],
                        **{"if": stage, "unless": need}))
        if r["gate"]:
            acts.append(SAY(B, {3: "And the keep is not safe to work beside. A Hollow Knight still stalks its door. Put it down.",
                                4: "And something watches from beyond the north postern. A cult seer, by the look of its robes. Deal with it before the masons go near that side."}[p],
                            **{"if": stage + "," + need, "unless": r["gate"]}))
        ready = stage + "," + need + (("," + r["gate"]) if r["gate"] else "")
        opt = dict(label="Rebuild: %s (%s)" % (PHASE_NAME[p], cs), actions=[
            ACT("build", who=B, cost=r["cost"], then=[
                SAY(B, "Stand clear! Stone and shard-mortar, lads! Up she goes!"),
                ACT("flag", key="hp_%d" % p),
                ACT("fade", to="black", t=1.4),
                ACT("title", text="Dawnwatch", sub="Phase %s: %s" % ({2: "II", 3: "III", 4: "IV"}[p], PHASE_NAME[p]), t=3.4),
                ACT("warp", scene="strange", x=0, z=24, fresh=True)])])
        acts.append(dict(type="choice", who=B, text="Shall I start? It will cost %s." % cs, options=[opt, dict(label="Not yet", actions=[ACT("end")])], **{"if": ready}))
    acts.append(SAY(B, "Dawnwatch is whole again. Look at her. The foundation stones have not seen this since before the Grey Tide. There is more to do out there, but this is home.", **{"if": "hp_4"}))
    return acts


npc("brannoch", "Brannoch", "Master Mason", "Farmer", -3.0, 23.5, actions=None, reach=5.0)
NPCS[-1]["actions"] = brannoch_talk()

# ---- the notice board (the herald Dove keeps it from phase III): shows who is found and what each phase needs
def board():
    lines = []
    lines.append(SAY("Notice Board", "DAWNWATCH: HANDS NEEDED. Residents found so far, and what remains."))
    names = [("hr_mason", "Brannoch, mason"), ("hr_orla", "Orla, blacksmith"), ("hr_tilda", "Tilda, innkeeper"), ("hr_pell", "Pell, merchant"),
             ("hr_wick", "Wick, angler"), ("hr_sennet", "Sennet, archivist"), ("hr_dove", "Dove, herald")]
    for f, label in names:
        lines.append(SAY("Notice Board", label + ": settled in Dawnwatch.", **{"if": f}))
        lines.append(SAY("Notice Board", label + ": MISSING. Last seen in the ruins.", **{"unless": f}))
    lines.append(SAY("Notice Board", "Next rebuild: " + "; ".join("%s needs %d gold, %d shards" % (PHASE_NAME[p], REQ[p]["cost"]["gold"], REQ[p]["cost"]["shards"]) for p in (2, 3, 4)) + ". Speak to Brannoch."))
    return lines


# ---- residents: found in the ruins, then they settle and run the services
def resident(id, name, title, sprite, found_xz, found_lines, flag, bonus=None, tint=None, fight=None):
    """before: stands in the ruins (hideIf flag). A fight, if any, comes first (key hg_<id>); then the thanks recruits them."""
    x, z = found_xz
    if fight:
        pre = [SAY(name, fight["pre"]), dict(type="battle", key="hg_" + id, pool=fight["pool"], level_rel=fight.get("lr", [0, 2]), elite=fight.get("elite", 0.6))]
        npc(id + "_0", name, title, sprite, x, z, pre, show=None, hide="hg_" + id, tint=tint)
        post = [SAY(name, t) for t in found_lines] + [ACT("flag", key=flag)]
        if bonus: post.append(dict(type="chest", loot=bonus, text=name + " presses a reward into your hands"))
        npc(id + "_1", name, title, sprite, x, z, post, show="hg_" + id, hide=flag, tint=tint)
    else:
        post = [SAY(name, t) for t in found_lines] + [ACT("flag", key=flag)]
        if bonus: post.append(dict(type="chest", loot=bonus, text=name + " presses a reward into your hands"))
        npc(id + "_0", name, title, sprite, x, z, post, hide=flag, tint=tint)



# Orla the blacksmith (west rubble) -- pinned by a gargoyle that came alive
resident("orla", "Orla", "Blacksmith", "Blacksmith", (-30.5, -17.0),
         ["A hammer! A friend! Thank the forge. That thing woke when the keep fell and has been sitting on my anvil ever since.",
          "I am Orla. I forged for the garrison here, and I will forge for whoever is brave enough to light the fire again. Get Brannoch to put up a roof, and I will make something worth carrying."],
         "hr_orla", bonus=dict(gold=300, shards=6),
         fight=dict(pre="Keep back! It is... It will not let me leave the forge! It is a gargoyle, the keep's own, and it has gone mad!", pool=["stone_gargoyle"], lr=[0, 2], elite=0.5))
put(KEN + "bricks", -30.5, -15.5, 30, 0, S); put(KEN + "column-damaged", -32, -18, 70, 0, S * 1.2)
# Tilda the innkeeper (the old chapel cellar, east)
resident("tilda", "Tilda", "Innkeeper", "Innkeeper", (29.5, -10.5),
         ["...Are they gone? The masked ones, the grey riders? ...You are not one of them. Oh, thank the hearth.",
          "I kept the inn at the Dawn Gate for thirty years. Give me four walls and a bed frame and I will have a stew on by nightfall. A bed costs a little, mind. Love does not pay the baker."],
         "hr_tilda", bonus=dict(gold=200, items={"potion": 3}))
put(DG + "SM_dg_block", 29.5, -9.5, 0, 0, 1.1)
# Pell the merchant (a stranded wagon outside the south gate)
resident("pell", "Pell", "Travelling Merchant", "Shopkeeper", (-17.0, 40.0),
         ["Thank the road! Bandits, three of them, and not one could count. They let go of my axle the moment you arrived.",
          "Pell, of Pell and Pell, merchants. There is no other Pell. I carry the best goods three worlds can reach. Give me a stall in a proper market and I will sell you the lot at honest prices."],
         "hr_pell", bonus=dict(gold=400, shards=8),
         fight=dict(pre="Stay back, friend! Bandits... they took my team and left the wagon! Will you help? I can pay you!", pool=["bandit_rogue"], lr=[0, 2], elite=0.6))
at(1); put(ST + "SM_Stylized_Wagon", -17, 42, 20, 0, 1.0); block(-17, 42, 2.2, 4.4); put(ST + "SM_Hay", -15.5, 41, 0, 0, 1.6)
# Wick the angler (the east pond)
resident("wick", "Wick", "Angler", "Fisherman", (18.5, 20.5),
         ["Shh! You will scare the... ah, never mind. Nothing is biting. Nothing has bitten since the sky changed.",
          "Wick. I fish. I fished the river at Dawn Gate and now I fish a puddle in a ruin, and I am happy. Get Brannoch to put a proper pier on the east bank and I will show you what lives in these waters."],
         "hr_wick", bonus=dict(gold=250, items={"antidote": 2}))
# Sennet the archivist (the library rubble, north-east)
resident("sennet", "Sennet", "Archivist", "Elder", (24.5, -19.5),
         ["Mind the third shelf! Mind... oh. You are not a looter. I can tell by the boots.",
          "I am Sennet, keeper of the Dawnwatch archive. Half of it burned. The other half is in my head and in these notes. Give me a roof and I will keep your records, and you can set your own progress down in my ledger whenever you like."],
         "hr_sennet", bonus=dict(gold=300, shards=10))
# Dove the herald (the north-east tower)
resident("dove", "Dove", "Young Herald", "Townee", (31.0, -31.0),
         ["You can see everything from up here. I saw the keep burn, and the grey riders, and I saw you walk in this morning looking like you had been fighting the sky.",
          "I am Dove. The herald, or I was, until there was nobody left to herald to. Let me keep the notice board when the village is up. Somebody should tell people who is missing, and what is needed."],
         "hr_dove", bonus=dict(gold=250, items={"hi_potion": 1}))

# ---- the services (they appear when the resident has settled AND their phase is built)
npc("orla_smith", "Orla", "Blacksmith", "Blacksmith", -22.0, 10.5, action="heroes", show="hr_orla,hp_2")
npc("tilda_inn", "Tilda", "Innkeeper", "Innkeeper", -22.0, 24.0, actions=[SAY("Tilda", "Welcome to the Dawn Gate Inn. A hot meal and a bed for the night is 60 gold, and worth every coin."), dict(type="rest", cost=60)], show="hr_tilda,hp_2")
npc("pell_shop", "Pell", "Item Shop", "Shopkeeper", 22.0, 8.4, action="shop", show="hr_pell,hp_3")
npc("pell_wait", "Pell", "Travelling Merchant", "Shopkeeper", 22.0, 8.4, actions=[SAY("Pell", "Nothing to sell from a ditch, friend. Get me a market and I will open the doors.")], show="hr_pell", hide="hp_3")
npc("wick_pond", "Wick", "Angler", "Fisherman", 18.0, 21.5, actions=[SAY("Wick", "Try the pond bench. Floats best when you do not look at it. A bite now and then, even in ruins."), dict(type="fishing", op="shop")], show="hr_wick,hp_3")
npc("wick_wait", "Wick", "Angler", "Fisherman", 18.0, 21.5, actions=[SAY("Wick", "Nobody fishes a ruin. Get me a pier and a bench and I will have this pond singing.")], show="hr_wick", hide="hp_3")
npc("sennet_archive", "Sennet", "Archivist", "Elder", 22.0, -17.0, action="save_and_quit", show="hr_sennet,hp_4")
npc("sennet_wait", "Sennet", "Archivist", "Elder", 24.5, -19.5, actions=[SAY("Sennet", "The archive is not open yet. Give me a roof over the shelves.")], show="hr_sennet", hide="hp_4")
npc("dove_board", "Dove", "Herald", "Townee", 3.4, 12.0, actions=[SAY("Dove", "I keep the board, and the board keeps Dawnwatch honest. Read it, Kenji. It says who is missing and what the next stones cost.")], show="hr_dove,hp_3")
npc("dove_wait", "Dove", "Young Herald", "Townee", 31.0, -31.0, actions=[SAY("Dove", "A board and a village to herald to, that is all I want. Ask Brannoch.")], show="hr_dove", hide="hp_3")
# townsfolk who come with the phases
npc("t_guard", "Gate Warden", "Dawnwatch Guard", "Warden", 3.0, 31.0, actions=[SAY("Gate Warden", "Dawnwatch is not safe yet, but it is ours. Keep to the road and shout if you see grey riders.")], show="hp_2")
npc("t_villager1", "Maren", "Villager", "Townee", -12.5, 12.0, actions=[SAY("Maren", "A real roof! I had forgotten what the rain sounded like on one.")], show="hp_3")
npc("t_villager2", "Old Joss", "Villager", "Farmer", 12.0, 19.0, actions=[SAY("Old Joss", "They say worlds fall into this one. If more of them bring bread, I say let them.")], show="hp_3")
npc("t_knight", "Ser Calder", "Keep Captain", "Warden", 0.0, -17.0, actions=[SAY("Ser Calder", "The keep is yours to command, Kenji. Command it well. Dawnwatch has had too many bad kings and too few good gardeners.")], show="hp_4")
npc("t_herald4", "Town Crier", "Crier", "Mayor", 5.0, 3.0, actions=[SAY("Town Crier", "Hear ye! Dawnwatch stands, and the road beyond lies open! Heroes, take heart!")], show="hp_4")

# ---- story gates (fights)
npc("knight", "Hollow Knight", "Haunt of the keep", "Draven", 0.0, -17.0, tint=[0.55, 0.6, 0.85, 1], h=2.8, reach=5.0, hide="hg_knight",
    actions=[SAY("Hollow Knight", "...THE KEEP... IS NOT... TO BE ENTERED. THE KING... HAS NOT... RETURNED."), dict(type="battle", key="hg_knight", pool=["cursed_knight"], level_rel=[1, 3], elite=1.2)])
npc("seer", "Cult Seer", "Watcher at the postern", "Rook", 0.0, -41.0, tint=[0.7, 0.45, 1.1, 1], h=2.8, reach=5.0, hide="hg_seer",
    actions=[SAY("Cult Seer", "He walks! The Heart's shadow walks! The Mind will be pleased to hear it."), dict(type="battle", key="hg_seer", pool=["dark_cultist"], level_rel=[1, 3], elite=1.2)])

# ---- events
event("dw_rest", "Rest crystal", 7, 31, [SAY("", "Soft light settles over the party. Wounds close and breath comes easy. The crystal hums and remembers this place: it is now your save point."), dict(type="checkpoint"), dict(type="rest")], "Rest and save at the crystal", w=3, d=2.6)
event("dw_board", "Notice board", 3.5, 14.5, board(), "Read the notice board", w=3.4, d=2.4, show="hp_3")
put(ST + "SM_Stylized_WantedBoard", 3.5, 14.5, 180, 0, 1.4); block(3.5, 14.5, 2.4, 0.5)
event("dw_fish", "Fishing spot", 19.0, 18.2, [SAY("", "A quiet bench by the pond. The water is clear enough to see the stones."), dict(type="game", game="fish", stake=0, spot="pier", scene="fish_pier")], "Drop a line", show="hp_3")
event("dw_plate", "Weathered plate", -3.0, 33.0, [SAY("Weathered Plate", "DAWNWATCH KEEP. WHERE THE REALM FIRST SAW THE MORNING. WHEN THE GREY TIDE CAME, THE GATE WAS THE LAST TO FALL.", hide="hp_4"),
                                                 SAY("", "Scratched under the lettering in an older hand, half worn away: ELDERGATE.", show="eg_open"),
                                                 SAY("Weathered Plate", "DAWNWATCH KEEP. REBUILT BY THE LAST OF THE REALM'S FRIENDS, AND BY THOSE WHO FELL INTO IT FROM THE SKY.", show="hp_4")], "Read the plate", w=3.2, d=2.4)
event("dw_throne", "Broken dais", 0.0, -20.5, [SAY("", "A cracked dais of pale stone, scorched black along one edge. Something very large sat here once."),
                                                  SAY("", "The air above it is faintly cold.", hide="hp_4"), SAY("", "A banner of the new Dawnwatch hangs over it. The chill is gone.", show="hp_4")], "Look at the dais", w=4, d=3, show="hg_knight")
event("dw_gate", "South road", 0.0, 42.5, [SAY("", "The road south runs into a grey haze that does not feel like weather. Whatever lies out there, you are not ready to walk it yet. (The way out of Dawnwatch will open in a later chapter.)")], "Look down the road", w=8, d=3)

STAIR_DOWN = [ACT("fade", to="black", t=0.9), ACT("warp", scene="eldergate", x=0, z=22, fresh=True)]
event("dw_stair", "Sunken Stair", -20.0, -25.4, [
    SAY("", "A ring of cracked paving, nine bands wide, and every crack is faintly warm. The golden mark on Kenji's hand throbs in time with the hum under your boots.", **{"unless": "eg_open"}),
    SAY("Kenji", "It knows me. Whatever this is, it has been waiting.", **{"unless": "eg_open"}),
    SAY("Miya", "Brannoch said stones remember. I think these remember a hand like yours.", **{"unless": "eg_open"}),
    ACT("flash", **{"unless": "eg_open"}),
    SAY("", "Kenji lays his palm on the stone. The rings turn against each other like the gears of a clock, and the dais sinks, step by step, into a stair that was never meant to be found.", **{"unless": "eg_open"}),
    ACT("flag", key="eg_open", **{"unless": "eg_open"}),
] + STAIR_DOWN, "Touch the ring stone", w=4.4, d=2.6, show="hr_mason")

# ---- treasure that helps fund the rebuild
chest("hc1", -30.0, 31.0, dict(gold=500, shards=10))
chest("hc2", 31.0, 33.0, dict(gold=450, shards=8, items={"potion": 2}))
chest("hc3", -32.0, -31.5, dict(gold=600, shards=12))
chest("hc4", 12.0, -12.0, dict(gold=700, shards=14))
chest("hc5", -12.5, -11.5, dict(gold=650, shards=12, items={"ether": 1}))
chest("hc6", 33.0, 1.5, dict(gold=900, shards=18))
chest("hc7", -4.0, -33.0, dict(gold=1200, shards=24))

# ------------------------------------------------------------------ cutscenes: the wake-up (arrival) and one reveal per phase
WAKE = [
    ACT("cine", on=True),
    dict(type="music", url=MUSIC + "05. Long Journey.mp3"),
    ACT("fade", to="clear", t=3.0, wait=False),
    ACT("cam", x=0, z=30, yaw=0, pitch=62, dist=30, t=0),
    SAY("", "Cold stone. Woodsmoke. The slow creak of something very old settling in the wind."),
    ACT("cam", x=0, z=26, yaw=0, pitch=40, dist=14, t=4, wait=False),
    SAY("Kenji", "...Miya? Lyra?"),
    SAY("Miya", "Here. I think. Everything hurts, but it is the ordinary kind of hurt."),
    SAY("Lyra", "Look at the sky. I count one sun, and it is the wrong colour for any sun I know. This is not on Rook's maps."),
    SAY("Kenji", "He was never Rook."),
    SAY("Lyra", "No. And he is still out there, with that thing in his hand and a door open behind him."),
    ACT("walk", who="brannoch", x=-1.0, z=25.5, speed=2.6),
    SAY("Brannoch", "Easy, easy. Three more of you, are there? That is the fourth batch to fall out of the sky this season, and the first with swords."),
    SAY("Kenji", "Where are we?"),
    SAY("Brannoch", "Dawnwatch Keep, or what the Grey Tide left of her. I am Brannoch, mason, and the last of the garrison's builders. The rest are rubble or runaways."),
    SAY("Brannoch", "Folk wash up here from all over: other realms, other skies, a few with no world to go back to. The Tide took our kingdom and, if I am reading the cracks right, quite a few others."),
    SAY("Miya", "The Tide. The Mind's doing, then. His fingerprints are everywhere."),
    SAY("Brannoch", "Whoever he is, he picked the wrong foundation to knock down. This keep sat on the first sunrise. Stones remember. Give me hands, a little coin and a few shards of that violet glass you lot bleed, and I will make her stand again."),
    SAY("Brannoch", "And there are people hidden in these ruins who would stand with us, if they were found. Orla the smith, Tilda the innkeeper... Find them. Bring them home. A castle is its people, whatever the masonry says."),
    SAY("Kenji", "We have nowhere else to be. Show me where to start."),
    ACT("flag", key="hr_mason"),
    ACT("flag", key="st_strange"),
    ACT("follow", t=1.4),
]


def reveal(p, pan, lines, music=None):
    a = [ACT("cine", on=True)]
    if music: a.append(dict(type="music", url=MUSIC + music))
    a.append(ACT("fade", to="clear", t=1.6, wait=False))
    a += pan
    a += lines
    a += [ACT("flag", key="hp_%d_seen" % p), ACT("follow", t=1.4)]
    return {"if": "hp_%d" % p, "unless": "hp_%d_seen" % p, "cine": True, "actions": a}


R2 = reveal(2, [dict(type="cam", x=0, z=20, yaw=0, pitch=40, dist=30, t=0), dict(type="cam", x=-12, z=14, yaw=-20, pitch=26, dist=22, t=5, wait=False)],
            [SAY("", "Canvas goes up over the broken foundations. Smoke rises from two new fires. A forge hammer rings somewhere in the west, and in the east a pot begins to simmer."),
             SAY("Brannoch", "Not much to look at yet, but it is a camp, and a camp is how every town starts. Orla has her anvil under cloth, and Tilda has hung a lantern. Go and see them."),
             SAY("Miya", "It looks lived in already.")], "04. Peaceful Village.mp3")
R3 = reveal(3, [dict(type="cam", x=0, z=24, yaw=0, pitch=36, dist=34, t=0), dict(type="cam", x=0, z=-8, yaw=0, pitch=30, dist=30, t=6, wait=False)],
            [SAY("", "Where there was rubble, there are walls. Roofs of red and blue climb the lots, and a fountain throws water in the square again. Beyond it, the keep's shell has teeth: its walls are whole."),
             SAY("Brannoch", "There! Houses for the folk, a market for Pell, a bench for Wick, and a board for young Dove. The curtain wall is mending, too. The north postern is still a hole, mind."),
             SAY("Lyra", "Four days ago this was a graveyard. I think I will start calling it a town.")], "02. Lively City.mp3")
R4 = reveal(4, [dict(type="cam", x=0, z=40, yaw=0, pitch=26, dist=36, t=0), dict(type="cam", x=0, z=-14, yaw=0, pitch=24, dist=36, t=7, wait=False)],
            [SAY("", "The gatehouse rises first, its twin towers catching the morning. Banners fill the wind. Behind the square, the great tower of the keep stands crowned in battlements, and the library roof is whole."),
             SAY("Brannoch", "Dawnwatch. Look at her, lad. Not a stone out of place, and a good few I did not know she had."),
             SAY("Kenji", "It is not the Colosseum, and it is not the island. It is the first place I have seen since waking that feels like it could be home."),
             SAY("Miya", "Then let us keep it standing."),
             SAY("Lyra", "The Mind will come for it, you know. That is why we need it so badly.")], "03. Royal Castle.mp3")

AUTORUN = [
    dict(unless="st_strange", cine=True, actions=WAKE),
    R2, R3, R4,
]

OBJECTIVES = [
    {"unless": "hr_mason", "text": "Speak with the mason, Brannoch, by the camp."},
    {"unless": "eg_open", "text": "Brannoch mentioned a humming paved ring in the north-west ruin. Try your hand on it."},
    {"if": "eg_open", "unless": "eg_core", "text": "Explore the Eldergate Network beneath Dawnwatch (the Sunken Stair, north-west ruin)."},
    {"if": "eg_core", "unless": "eg_veyra_go", "text": "The Veyra gate beneath Dawnwatch is open (the Sunken Stair, north-west ruin). Rebuilding can wait for you."},
    {"if": "hp_4", "text": "Dawnwatch is whole. (The way out of the ruins opens in a later chapter.)"},
    {"if": "hp_3", "text": "Phase IV, the Castle Town: find Sennet (north-east library ruin) and Dove (north-east tower), defeat the Cult Seer outside the north postern, then bring gold and shards to Brannoch."},
    {"if": "hp_2", "text": "Phase III, the Village: find Pell (the wagon outside the south gate) and Wick (the east pond), defeat the Hollow Knight at the keep door, then bring gold and shards to Brannoch."},
    {"text": "Phase II, the Camp: find Orla (the west rubble) and Tilda (the old chapel cellar, east), then bring gold and shards to Brannoch. Chests in the ruins help pay for it."},
]

ISL = json.load(open(os.path.join(HERE, "island.json"), encoding="utf-8"))
scene = {
    "story": True, "restart": "sg_", "name": "Dawnwatch", "kit": "", "tile": 4,
    "autorun": AUTORUN, "objectives": OBJECTIVES,
    "music": [{"if": "hp_4", "url": MUSIC + "03. Royal Castle.mp3"}, {"if": "hp_3", "url": MUSIC + "02. Lively City.mp3"},
              {"if": "hp_2", "url": MUSIC + "04. Peaceful Village.mp3"}, {"url": MUSIC + "05. Long Journey.mp3"}],
    "pieces": T.P, "colliders": T.COL, "decals": T.DEC, "npcs": NPCS, "events": EVENTS,
    "spawn": {"x": 0, "z": 28}, "bounds": {"minX": -46, "maxX": 46, "minZ": -46, "maxZ": 46}, "playerHeight": 2.4,
    "camera": {"pitch": 19, "dist": 33},
    "light": {"dir": [-0.45, -1, -0.35], "color": [0.95, 0.88, 0.74], "ambient": [0.36, 0.38, 0.46]}, "fog": {"color": [0.7, 0.78, 0.86], "near": 70, "far": 210}, "sky": ISL["sky"],
    "fx": [{"type": "dust", "amount": 0.1}],
    "encounters": {"rate": 62, "level": [22, 26], "level_rel": [0, 2], "pool": ["stone_gargoyle", "bandit_rogue", "goblin_skirmisher", "dark_cultist", "cursed_knight"],
                   "zones": [{"x": 0, "z": 20, "w": 40, "d": 30, "safe": True},
                             {"x": 0, "z": -20, "w": 66, "d": 30, "rate": 62}, {"x": -26, "z": 0, "w": 14, "d": 24, "rate": 70}, {"x": 26, "z": 4, "w": 14, "d": 18, "rate": 70}],
                   "text": "Something stirs in the rubble..."},
}

if __name__ == "__main__":
    out = os.path.join(sys.argv[1] if len(sys.argv) > 1 else HERE, "strange.json")
    with open(out, "w", encoding="utf-8", newline="") as f:
        json.dump(scene, f, ensure_ascii=False, separators=(",", ":"))
    print("strange.json:", len(T.P), "pieces,", len(T.COL), "colliders,", len(NPCS), "npcs,", len(EVENTS), "events")

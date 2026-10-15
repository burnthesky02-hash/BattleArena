"""Builds html_hub/3d/strange.json: "Dawnwatch" (v4), the cliff-side town of the Eldergate reference.  For now it holds only the terrain, the market plaza,
the keep with the great arch (the Eldergate portal) at the head of a grand stair, the river with its bridge and the service lots; houses, chapel, library and
the north gate were stripped.  x east, z south, heights from dawnheight.py (plaza y 3, keep terrace y 10, rock ledges all round).  Phases I-IV are unchanged."""
import json, math, os, random, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kenhouse, stylhouse
import dawnheight as DH

KEN = kenhouse.KEN
GC, ST, PA, DG, GEN = ("/assets/3D/GodCity/", "/assets/3D/Stylized/", "/assets/3D/Paradise/", "/assets/3D/Dungeon/", "/assets/3D/Generated/")
S = kenhouse.S                        # one Kenney tile in metres
rng = random.Random(1307)
MUSIC = "/assets/Music/mp3/"
gy = DH.gy


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


class Hub(stylhouse.Town):
    def __init__(self):
        super().__init__(gy=gy)
        self.cur = (None, None)

    def at(self, frm=1, to=None):
        self.cur = phase_vis(frm, to)
        return self

    def put(self, n, x, z, rot=0, y=0.0, sc=1, spec=None, abs_y=False):
        super().put(n, x, z, rot, y, sc, spec or spec_of(*self.cur), abs_y)

    def ken(self, n, x, z, rot=0, y=0.0, sc=S, spec=None):
        self.put(KEN + n, x, z, rot, y, sc, spec)

    def block(self, x, z, w, d, hide=None):
        c = {"x": round(x, 3), "z": round(z, 3), "w": round(w, 3), "d": round(d, 3)}
        show, hd = self.cur
        if show: c["showIf"] = show
        if hd: c["hideIf"] = hd
        self.COL.append(c)

    def glow(self, x, z, r, c, frm=1, to=None, h=None):
        d = dict(type="glow", x=round(x, 2), z=round(z, 2), r=r, color=c)
        if h is not None: d["y"] = round(gy(x, z) + h, 2)
        show, hd = phase_vis(frm, to)
        if show: d["showIf"] = show
        if hd: d["hideIf"] = hd
        self.DEC.append(d)

    def lamp(self, x, z, rot=0, frm=3, to=None):
        self.at(frm, to); self.put("SM_Stylized_Lamp_C", x, z, rot, 0, 2.4); self.block(x, z, 0.5, 0.5); self.glow(x, z, 5.0, [1, 0.82, 0.5, 0.5], frm, to, h=2.6)

    def lot_house(self, x, z, rot, frm, to=None, base=None, **kw):
        """a Stylized house standing from phase `frm`; its floor is set on the highest ground under it"""
        self.at(frm, to)
        if base is None:
            base = max(gy(x + dx, z + dz) for dx in (-4, 0, 4) for dz in (-4, 0, 4)) - 0.1
        return self.house(x, z, rot, base=base, **kw)


T = Hub()
put, block, at, ken = T.put, T.block, T.at, T.ken
NPCS, EVENTS = [], []
WALK = []

# ------------------------------------------------------------------ the land: ground, river, three bridges, piers, boats
at(1)
put(GEN + "SM_dw_ground", 0, 0, 0, 0, 1, abs_y=True)
put(GEN + "SM_dw_river", 0, 0, 0, 0, 1, abs_y=True)
BR_Y, BR_L, BR_HW, BR_Z = 3.0, 19.5, 3.7, DH.RIVER_Z


def bridge(bx, bz):
    at(1)
    put(GEN + "SM_dw_bridge", bx, bz, 0, BR_Y, 1, abs_y=True)
    WALK.append(dict(x=bx, z=bz, w=2 * BR_HW - 0.2, d=BR_L, rot=0, y=BR_Y))                       # you walk ON the deck, not along the river bed under it
    for sgn in (-1, 1): block(bx + sgn * (BR_HW - 0.3), bz, 0.7, BR_L)                              # parapets
    for zz in (bz - BR_L / 2 + 0.45, bz + BR_L / 2 - 0.45):                                          # lamps from phase III, flags in IV
        for sgn in (-1, 1):
            x = bx + sgn * (BR_HW - 0.3)
            at(3); put("SM_Stylized_Lamp_C", x, zz, 0, BR_Y + 1.7 - gy(x, zz), 2.2); T.glow(x, zz, 5.0, [1, 0.82, 0.5, 0.5], 3, None, h=BR_Y + 2.6 - gy(x, zz))
            at(4); put("SM_Stylized_Flag_Var%d" % (1 if sgn < 0 else 2), x, zz + (0.9 if zz < bz else -0.9), 0, BR_Y + 1.7 - gy(x, zz), 2.2)


BRIDGES2 = [(bx, BR_Z) for bx in DH.BRIDGES]
for (bx, bz) in BRIDGES2: bridge(bx, bz)

# piers: the north-bank ones run south into the river, the south-bank ones run north.  (x, z of the shore end, runs_south)
DECK_TOP = 0.9; DOCK_Y = DECK_TOP - 4.62                                                           # the Stylized dock mesh is 4.62 m tall; its deck is the top
PIERS2 = [(-44.0, 55.4), (-16.0, 55.4), (16.0, 55.4), (44.0, 55.4), (-30.0, 72.6), (30.0, 72.6)]
at(3)
for (px, pz) in PIERS2:
    south_run = pz < BR_Z
    zc = pz + (3.8 if south_run else -3.8)
    put("SM_Dock_Straight", px, zc, 0, DOCK_Y, 1.0, abs_y=True)
    WALK.append(dict(x=px, z=zc, w=2.45, d=7.6, rot=0, y=DECK_TOP))
    ld = -1 if south_run else 1                                                                   # the land side of the pier
    put("SM_Stylized_Box_var1", px + 2.2, pz + ld * 1.0, 30, 0, 1.2); put("_Stylized_Barrel", px - 2.2, pz + ld * 1.4, 0, 0, 1.2); put("SM_Stylized_Basket", px + 2.0, pz + ld * 2.4, 0, 0, 1.2)
at(3)
for (bx, bz, br) in ((-112, 63.5, 88), (-98, 61.0, 80), (-84, 66.0, 95), (-72, 62.0, 70), (-52, 66.0, 90), (-30, 61.5, 86), (-24, 66.0, 100), (-8, 62.0, 80), (10, 66.0, 90),
                     (24, 61.5, 84), (36, 66.0, 95), (52, 62.0, 80), (74, 66.0, 90), (88, 62.0, 100), (104, 65.0, 85), (116, 62.5, 90)):
    if gy(bx, bz) < -1.2: put("SM_Stylized_Boat", bx, bz, br, -0.18, 1.1, abs_y=True)
at(4)
for (bx, bz, br) in ((-120, 78.0, 90), (-96, 80.0, 70), (-76, 74.0, 100), (-66, 69.0, 85), (-90, 63.0, 88), (-40, 63.5, 92), (28, 63.0, 85), (60, 65.5, 95), (96, 63.0, 90), (124, 61.5, 88)):
    if gy(bx, bz) < -1.2: put("SM_Stylized_Boat", bx, bz, br, -0.18, 1.0, abs_y=True)

# ------------------------------------------------------------------ the survivors' camp: the SW corner of the (ruined) market square
at(1)
put(ST + "SM_Stylized_Bonfire", -12, 44, 0, 0, 1.6); block(-12, 44, 2.0, 2.0); T.glow(-12, 44, 7, [1, 0.62, 0.3, 0.5], h=1.2)
put(DG + "SM_dg_crystal", -5, 44.5, 0, 0, 2.0); block(-5, 44.5, 1.4, 1.4); T.glow(-5, 44.5, 6, [0.55, 0.85, 1, 0.3], h=1.5)
at(1, 3)                                                                                          # the two survivors' tents come down once the village is built
for (x, z, r) in ((-22, 41, 90), (-2.5, 39.5, 270)):
    put(GC + "SM_market_tent_03", x, z, r, 0, 1.1); block(x, z, 4.8, 4.0)
at(1)
put(ST + "SM_Stylized_Table_A", -17, 38, 0, 0, 1.1); block(-17, 38, 2.7, 1.3)
for (x, z) in ((-20.5, 35.5), (-14.5, 34.5), (-19.5, 32.5)):
    put(GC + "SM_construction_block_01", x, z, rng.randint(0, 359), 0, 1.2); block(x, z, 1.5, 1.5)
put(ST + "_Stylized_Barrel", -15, 46.5, 0, 0, 1.2); put(ST + "SM_Stylized_Box_var1", -13.5, 47.5, 20, 0, 1.2)
at(2, 3)                                                                                          # phase II: a proper camp (struck again in III)
put(ST + "SM_Stylized_Bonfire", -27, 49, 0, 0, 1.3); T.glow(-27, 49, 6, [1, 0.62, 0.3, 0.45], 2, 3, h=1.2)
for i, (x, z) in enumerate(((-31, 41), (-30, 47.5), (12, 46), (13, 40))):
    put(GC + ("SM_market_tent_02" if i % 2 else "SM_market_tent_01"), x, z, 90 if x < 0 else 270, 0, 1.0); block(x, z, 4.6, 8.0)
put(ST + "SM_Stylized_Wagon", 18, 48, 100, 0, 1.0); block(18, 48, 2.0, 4.4)
at(1)
put(PA + "SM_rock_01", -48, 51, 40, 0, 0.35)

# ------------------------------------------------------------------ the market square (68 x 45 m): a fountain ruin until III, then the fountain, stalls, lamps, benches
PX, PZ = 0.0, 30.0
at(1, 3)
put(KEN + "bricks", PX, PZ, 10, 0, S * 1.4); put(KEN + "column-damaged", PX - 2.4, PZ - 1, 35, 0, S * 1.1); put(KEN + "bricks", PX + 2.8, PZ + 1.7, 120, 0, S * 0.9); block(PX, PZ, 4.0, 4.0)
for i in range(16):                                                                               # a ruined square: toppled columns and rubble strewn across it
    x, z = rng.uniform(-30, 30), rng.uniform(10, 50)
    if -34 < x < 0 and z > 32 or abs(x) < 3.5 and z > 36: continue
    if i % 2: ken("column-damaged", x, z, rng.randint(0, 359), 0, S * rng.uniform(0.9, 1.3))
    else: ken("bricks", x, z, rng.randint(0, 359), 0, S * rng.uniform(0.6, 0.9))
at(3)
put(ST + "SM_Stylized_Fountain", PX, PZ, 0, 0, 2.5); block(PX, PZ, 9.4, 8.9); T.glow(PX, PZ, 11, [0.55, 0.85, 1.0, 0.25], 3, None, h=2.6)
for (x, z) in ((-11, 20.5), (11, 20.5), (-11, 39.5), (11, 39.5), (-31, 11), (31, 11), (-31, 30), (31, 30), (-31, 50), (31, 50), (-16, 11), (16, 11), (0, 50)): T.lamp(x, z)
for (x, z, r) in ((-8, 30, 90), (8, 30, 270), (0, 22, 0), (0, 38, 180), (-16, 21, 0), (16, 21, 0), (-16, 39, 180), (16, 39, 180)): at(3); put(ST + "SM_Stylized_Bench", x, z, r, 0, 2.2)
STALLS = [(-26, 14, 180, "SM_market_tent_01"), (-18, 14, 180, "SM_market_tent_02"), (-10, 14, 180, "SM_market_tent_03"), (10, 14, 180, "SM_market_tent_03"), (18, 14, 180, "SM_market_tent_01"), (26, 14, 180, "SM_market_tent_02"),
          (27, 25, 270, "SM_market_tent_03"), (27, 32, 270, "SM_market_tent_03"), (27, 39, 270, "SM_market_tent_03"), (27, 46, 270, "SM_market_tent_03"),
          (-27, 25, 90, "SM_market_tent_03"), (-27, 32, 90, "SM_market_tent_03"), (-27, 39, 90, "SM_market_tent_03"), (-27, 46, 90, "SM_market_tent_03")]
for (x, z, r, tent) in STALLS:
    at(3); put(GC + tent, x, z, r, 0, 1.0); block(x, z, 4.8 if r in (90, 270) else 5.0, 5.0 if r in (90, 270) else 8.0 if tent != "SM_market_tent_03" else 4.8)
at(3)
for (x, z) in ((-14, 19.5), (14, 19.5), (-14, 40.5), (14, 40.5), (22, 28.5), (22, 42.5), (-22, 28.5), (-22, 42.5)):
    put(ST + "SM_Stylized_Table_A", x, z, 90, 0, 1.0); block(x, z, 1.4, 2.7); put(ST + "SM_Stylized_Basket", x, z + 0.8, 0, 0.93, 1.2)
at(4)
for (x, z, v) in ((-6, 51, 1), (6, 51, 2), (-24, 11, 1), (24, 11, 2), (-20, 51, 1), (20, 51, 2), (-9, 9, 1), (9, 9, 2)): put(ST + "SM_Stylized_Flag_Var%d" % v, x, z, 0, 0, 2.6)

# ------------------------------------------------------------------ service lots (II: a tent, III: a house) on the square's flanks
LOTS = {
    "smith": dict(x=-41.0, z=14.0, rot=90, frm=3, wall="stone", roof="brown", bays=2, floors=1, tent="SM_market_tent_02"),
    "inn":   dict(x=-41.0, z=47.0, rot=90, frm=3, wall="cream", roof="red", bays=2, floors=2, tent="SM_market_tent_01"),
    "shop":  dict(x=41.0, z=14.0, rot=270, frm=3, wall="blue", roof="slate", bays=2, floors=1, tent=None),
}
for name, L in LOTS.items():
    if L["tent"]:
        at(2, 3); put(GC + L["tent"], L["x"], L["z"], L["rot"] + 90, 0, 1.05); block(L["x"], L["z"], 4.8, 8.4)
    T.lot_house(L["x"], L["z"], L["rot"], L["frm"], wall=L["wall"], roof=L["roof"], bays=L["bays"], floors=L["floors"], door_bay=0)
at(3)                                                                                             # the smithy's forge fire, the shop stall, the inn lantern
put(ST + "SM_Stylized_Bonfire", -34.2, 14.0, 0, 0, 0.9); T.glow(-34.2, 14, 4.5, [1, 0.5, 0.2, 0.55], 3, None, h=1.5)
put(ST + "SM_Stylized_Table_A", 34.0, 10.5, 90, 0, 1.0); block(34, 10.5, 1.4, 2.7); put(ST + "SM_Stylized_Basket", 34.0, 9.7, 0, 0.93, 1.2)
T.lamp(-34.0, 50.5)

# ------------------------------------------------------------------ the keep (at the north end of the square, base level) round the great pointed arch with the Eldergate portal
KX, KZ = 0.0, -22.0
RAMP_WALL_Z = DH.RAMP_Z - 1.2
KY = gy(KX, KZ)


def tower(x, z, sc, mids, ph_up, ph_roof=4, rubble_to=None):
    """a Kenney tower stack: stump until phase `ph_up`, the full tower (base + `mids` shafts) from `ph_up`, roofed from `ph_roof`"""
    sc = S * sc
    at(1, ph_up); ken("tower-base", x, z, 0, 0, sc); ken("column-damaged", x, z, 0, sc, sc * 0.9); ken("bricks", x + 1.6, z + 1.4, 30, 0, S)
    at(ph_up); ken("tower-base", x, z, 0, 0, sc)
    for m in range(mids): ken("tower", x, z, 0, sc * (1 + m), sc)
    block(x, z, 1.05 * sc, 1.05 * sc)
    at(ph_roof); ken("tower-top", x, z, 0, sc * (1 + mids), sc)


# front wall: two tiers on either side of the gate (stump -> wall in phase III -> second tier, battlements in IV)
GATE_HALF = 7.2
for side in (-1, 1):
    for i in range(6):
        x = KX + side * (GATE_HALF + 1.4 + i * S); z = KZ + 0.6
        broken = (i * 7 + (1 if side > 0 else 0)) % 3 == 0
        at(1, 3); ken("wall-fortified-half" if i % 2 else "bricks", x, z, 0, 0, S * (1.0 if i % 2 else 1.1))
        if i % 3 == 0: ken("column-damaged", x + 0.5, z + 1.0, 20 * i, 0, S)
        at(3); ken("wall-fortified-window" if i % 3 == 1 else "wall-fortified", x, z, 0, 0, S); block(x, z, S, 1.2)
        at(4); ken("wall-fortified-window" if i % 2 == 0 else "wall-fortified", x, z, 0, S, S); ken("battlement", x, z, 0, 2 * S, S)
    for i in range(5):                                                                            # side wings running back from the front towers
        x = KX + side * 26.0; z = KZ - 1.4 - i * S
        at(3); ken("wall-fortified", x, z, 90, 0, S); block(x, z, 1.2, S)
        at(4); ken("wall-fortified", x, z, 90, S, S); ken("battlement", x, z, 90, 2 * S, S)
# towers: the gate towers (tall), the corner towers (middle), the great towers behind the arch (tallest)
tower(KX - 11.4, KZ + 0.8, 1.7, 2, 3); tower(KX + 11.4, KZ + 0.8, 1.7, 2, 3)
tower(KX - 26.0, KZ + 0.8, 1.35, 2, 4); tower(KX + 26.0, KZ + 0.8, 1.35, 2, 3)
tower(KX - 6.0, KZ - 6.0, 2.1, 3, 4); tower(KX + 6.0, KZ - 6.0, 2.1, 3, 4); tower(KX, KZ - 8.0, 2.5, 3, 4)
at(4)
for x in (KX - 11.4, KX + 11.4):                                                                  # banners down the gate towers
    put(GEN + "SM_dw_banner", x, KZ + 3.4, 0, KY - gy(x, KZ + 3.4) + 6.5, 1.5)
for x in (KX - 4.0, KX + 4.0): put(GEN + "SM_dw_banner", x, KZ + 2.2, 0, KY - gy(x, KZ + 2.2) + 8.0, 1.6)
for x in (KX - 20.0, KX + 20.0): put(GEN + "SM_dw_banner", x, KZ + 1.9, 0, KY - gy(x, KZ + 1.9) + 3.0, 1.1)
# the great arch: a stone frame always (the town was built round it), the glow once the gate is awake or the keep is crowned
at(1); put(GEN + "SM_dw_portal_frame", KX, KZ, 0, 0, 1.0); block(KX, KZ, 17.0, 3.0)
for spec in ("S:eg_open", "S:hp_4,!eg_open"):
    T.P.append([GEN + "SM_dw_portal_glow", KX, KZ, 0, round(KY + 0.1, 3), 1.0, spec])
    T.P.append([GEN + "SM_dw_portal_beam", KX, KZ - 0.2, 0, round(KY + 6.0, 3), 1.0, spec])
for spec_d in ({"showIf": "eg_open"}, {"showIf": "hp_4", "hideIf": "eg_open"}):
    T.DEC.append(dict(type="glow", x=KX, z=KZ + 3.5, r=14, y=round(KY + 5.5, 2), color=[0.35, 0.62, 1.0, 0.55], **spec_d))
    T.DEC.append(dict(type="glow", x=KX, z=KZ + 8.0, r=10, y=round(KY + 2.0, 2), color=[0.45, 0.7, 1.0, 0.35], **spec_d))
# the ring stone in front of the arch (the Sunken Stair): a dormant glyph now, the way down
at(1)
put(DG + "SM_dg_dais", KX, KZ + 9.0, 0, 0, 0.6); block(KX, KZ + 9.0, 3.0, 3.0)
put(DG + "SM_dg_crystal", KX - 2.6, KZ + 7.4, 20, 0, 1.0); put(DG + "SM_dg_crystal", KX + 2.6, KZ + 7.4, 130, 0, 1.0)
for (x, z, r) in ((-3.5, 10.5, 40), (3.8, 11.0, 100), (-2.5, 5.0, 10), (2.5, 4.8, 160)): ken("column-damaged", KX + x, KZ + z, r, 0, S * 1.1)
T.glow(KX, KZ + 9.0, 6, [1.0, 0.85, 0.45, 0.22], 1, None, h=1.3)
T.DEC.append(dict(type="glyph", x=KX, z=KZ + 9.0, r=3.6, spin=-20, color=[1, 0.8, 0.4, 0.9]))
# the ruin before the keep: toppled columns, a cracked floor, scaffolding while it is rebuilt (II)
at(1, 3)
for (x, z, r) in ((-8, -2, 20), (6, -3, 70), (-14, 4, 140), (15, 5, 0), (0, 14, 50)): ken("column-damaged", KX + x, KZ + z, r, 0, S * 1.3)
for i in range(10): ken("bricks", KX + rng.uniform(-22, 22), KZ + rng.uniform(-6, 12), rng.randint(0, 359), 0, S * rng.uniform(0.6, 0.9))
at(2, 3)
for sx in (-17.0, 17.0):
    ken("structure-poles", KX + sx, KZ + 3.5, 0, 0, S); ken("structure", KX + sx, KZ + 3.5, 0, S, S * 0.9)
ken("structure-wall", KX - 6, KZ + 4, 0, 0, S); ken("structure-poles", KX + 6, KZ + 4, 0, 0, S)
# the keep's forecourt in IV: lamps and flags up the road
at(4)
for (x, z) in ((KX - 7, KZ + 14), (KX + 7, KZ + 14), (KX - 7, KZ + 22), (KX + 7, KZ + 22)): T.lamp(x, z, frm=4)
for (x, z, v) in ((KX - 10, KZ + 12, 1), (KX + 10, KZ + 12, 2)): put(ST + "SM_Stylized_Flag_Var%d" % v, x, z, 0, 0, 2.6)


def keepout(x, z, pad=3.0):
    """True where scenery must stay clear: the whole playable floor, roads, the river"""
    d, w = DH.river_dist(np.array([x]), np.array([z]))
    if d[0] < w[0] + 3.5: return True
    if abs(x) < 50 + pad and -40 - pad < z < 92 + pad: return True
    for pl in DH.ROAD:
        for (x0, z0), (x1, z1) in zip(pl[:-1], pl[1:]):
            dx, dz = x1 - x0, z1 - z0
            t = max(0.0, min(1.0, ((x - x0) * dx + (z - z0) * dz) / (dx * dx + dz * dz)))
            if math.hypot(x - (x0 + t * dx), z - (z0 + t * dz)) < 3.2 + pad * 0.3: return True
    return False


def slope_ok(x, z, lim=0.7):
    return abs(gy(x + 2, z) - gy(x - 2, z)) < lim * 4 and abs(gy(x, z + 2) - gy(x, z - 2)) < lim * 4


def rubble_ok(x, z):
    """ruins lie across the plaza and the keep forecourt, never on the river, the camp or the stair"""
    d, w = DH.river_dist(np.array([x]), np.array([z]))
    if d[0] < w[0] + 3.5: return False
    if abs(x) < 52 and 12 < z < 52 and not (-34 < x < 0 and z > 32): return abs(x) < 36
    if abs(x) < 32 and -40 < z < -4: return (abs(x) > 5 or z < -34) and not (abs(x) < 28 and -36 < z < -20)
    return False


# ---- lamps: the stair, the quay street and the south road; banners on the retaining wall
for (x, z) in ((-7, 9.5), (7, 9.5), (-7, -2.5), (7, -2.5), (-13, -9), (13, -9)): T.lamp(x, z, frm=3)
for x in range(-44, 46, 12):
    if abs(x) > 8: T.lamp(x, 55.2, frm=3)
    if abs(x) > 8: T.lamp(x + 2, 79.9, frm=3)
at(4)
for x in (-24.0, -18.0, 18.0, 24.0): put(GEN + "SM_dw_banner", x, RAMP_WALL_Z, 0, 4.0, 1.3)
for x in (-44.0, -38.0, 38.0, 44.0): put(ST + "SM_Stylized_Flag_Var%d" % (1 if x < 0 else 2), x, 8.0, 0, 0, 2.6)
# crates, barrels and wagons by the piers and along the south road
WAGON_ = ST + "SM_Stylized_Wagon"
deco_ = [(WAGON_, -40, 78.6, 90, 1.0, 4.4, 2.0), (WAGON_, 36, 78.6, 80, 1.0, 4.4, 2.0), (ST + "SM_Hay", 62, 77.6, 0, 1.2, 1.4, 1.4), (ST + "_Stylized_Barrel", -64, 77.4, 0, 1.3, 1.0, 1.0),
         (ST + "SM_Stylized_Box_var1", -62.5, 77.8, 30, 1.3, 1.0, 1.0), (ST + "_Stylized_Barrel", 66, 77.4, 0, 1.3, 1.0, 1.0)]
at(3)
for (m_, x, z, r, sc, bw, bd) in deco_:
    put(m_, x, z, r, 0, sc)
    if bw: block(x, z, bw, bd)


# ------------------------------------------------------------------ rubble, ivy, overgrowth: heavier in phase I, cleared as the town grows
RUIN = ("wall-fortified-half", "column-damaged", "bricks", "wall-half")
rubble = []
for i in range(140):
    x, z = rng.uniform(-52, 52), rng.uniform(-40, 52)
    if not rubble_ok(x, z): continue
    rubble.append((x, z, rng.randint(0, 359), rng.uniform(0.5, 1.0)))
for i, (x, z, r, s) in enumerate(rubble):
    at(1, 2 + (i % 2)); ken(RUIN[2] if i % 2 else "column-damaged", x, z, r, 0, S * s)
for i in range(300):                                                                                # grass tufts and ivy on the climbs and outer hills
    x, z = rng.uniform(-112, 112), rng.uniform(-132, 56)
    if keepout(x, z, 0.0) or not slope_ok(x, z) or gy(x, z) < 0.5: continue
    at(1, 2 + (i % 3)); put(ST + ("SM_Grass_A" if i % 2 else "SM_Grass_B"), x, z, rng.randint(0, 359), 0, rng.uniform(1.2, 2.2))
for i in range(120):
    x, z = rng.uniform(-112, 112), rng.uniform(-132, 56)
    if keepout(x, z, 0.0) or not slope_ok(x, z) or gy(x, z) < 0.5: continue
    at(1, 3); put(GC + "SM_ivy_01", x, z, rng.randint(0, 359), 0, 1.5)
# flowers and reeds
at(1)
for i in range(520):
    x, z = rng.uniform(-112, 112), rng.uniform(-132, 90)
    if keepout(x, z, 0.5) or not slope_ok(x, z) or gy(x, z) < 0.5: continue
    put(ST + rng.choice(("SM_Red_Flower", "SM_Yellow_Flower", "SM_White_Flower", "SM_Pink_Flower", "SM_Blue_Flower")), x, z, rng.randint(0, 359), 0, rng.uniform(2.0, 3.4))
for i in range(260):                                                                                # reeds along both banks
    x = rng.uniform(-70, 70); side = rng.choice((-1, 1))
    z = np.interp(x, [p[0] for p in DH.RIVER], [p[1] for p in DH.RIVER]) + side * (np.interp(x, [p[0] for p in DH.RIVER], [p[2] for p in DH.RIVER]) + 0.3 + rng.uniform(0, 0.8))
    if any(abs(x - bx) < 6 for bx in DH.BRIDGES) or any(abs(x - p[0]) < 3.5 for p in PIERS2): continue
    put(ST + "SM_Wheat", x, z, 0, 0, rng.uniform(1.4, 2.0))

# ------------------------------------------------------------------ trees: the shelves and the basin are built; the climbs between them and the hills round the valley are wooded
trees = []
for i in range(7000):
    x, z = rng.uniform(-146, 146), rng.uniform(-186, 126)
    if abs(x) < 50 and -40 < z < 92: continue                                                       # the floor is built
    h_ = gy(x, z)
    if h_ > 62 or h_ < 0.0 or rng.random() > 0.9 or not slope_ok(x, z, 0.6): continue
    d_, w_ = DH.river_dist(np.array([x]), np.array([z]))
    if d_[0] < w_[0] + 2.0: continue
    trees.append((x, z))
    at(1)
    put(ST + rng.choice(("Tree_01", "Tree_02", "Tree_03", "Tree_05", "Tree_06", "B_Tree_01", "B_Tree_05")), x, z, rng.randint(0, 359), -0.1, rng.uniform(1.0, 1.9))
for i in range(300):
    x, z = rng.uniform(-130, 130), rng.uniform(-150, 110)
    if (abs(x) < 50 and -40 < z < 92) or gy(x, z) < 0.2 or not slope_ok(x, z, 0.8): continue
    at(1); put(GC + "SM_bush_0%d" % rng.randint(1, 4), x, z, rng.randint(0, 359), 0, rng.uniform(0.8, 1.3))

# ------------------------------------------------------------------ river colliders: block the water and the bank foot, leave gaps for the bridges and the piers
GAPS = [*[(bx - BR_HW - 0.1, bx + BR_HW + 0.1, bz - BR_L / 2 - 1, bz + BR_L / 2 + 1) for (bx, bz) in BRIDGES2],
        *[(px - 1.9, px + 1.9, pz - 1, pz + 8.2) if pz < BR_Z else (px - 1.9, px + 1.9, pz - 8.2, pz + 1) for (px, pz) in PIERS2]]
CELLS = 2.0
rows = {}
for zc in np.arange(48.0, 90.0, CELLS):
    run = None
    for xc in np.arange(-60.0, 60.0 + CELLS, CELLS):
        d, w = DH.river_dist(np.array([xc]), np.array([zc]))
        hh = gy(xc, zc)
        blocked = hh < 1.0 and d[0] < w[0] + 3.5 and not any(g[0] <= xc <= g[1] and g[2] <= zc <= g[3] for g in GAPS)
        if blocked and run is None: run = [xc, xc]
        elif blocked: run[1] = xc
        if (not blocked or xc >= 60) and run is not None:
            rows.setdefault(zc, []).append(tuple(run)); run = None
at(1)
for sgn in (-1, 1):
    T.COL.append({"x": sgn * 31.5, "z": 3.0, "w": 33.0, "d": 12.0})                                 # the retaining wall beside the stair
    T.COL.append({"x": sgn * 42.0, "z": -23.0, "w": 12.0, "d": 34.0})                                # the canyon foot beside the keep terrace
T.COL.append({"x": 0.0, "z": -42.0, "w": 100.0, "d": 8.0})                                          # the rock behind the keep
for zc, runs in rows.items():
    for (a, b) in runs: T.COL.append({"x": round((a + b) / 2, 2), "z": round(zc, 2), "w": round(b - a + CELLS, 2), "d": CELLS + 0.2})


# ------------------------------------------------------------------ NPCs, events
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
    3: "Real walls and a roof over every head. A market for Pell, a pier for Wick, a board for the young herald, and the keep's gate towers standing again.",
    4: "The keep crowned with its towers and banners, and the great arch lit. Dawnwatch as it was, if not better.",
}


def brannoch_talk():
    acts = []
    acts.append(SAY(B, "And one more thing, lad. Up on the keep terrace, in front of the great arch, there is a paved ring I never could lift, dig under or chip. It hums when it thinks nobody is listening. Whoever put your mark on you, I would try your hand on it.", **{"if": "hr_mason", "unless": "eg_open"}))
    for p in (2, 3, 4):
        r = REQ[p]
        need = r["need"]
        stage = ("hp_%d,!hp_%d" % (p - 1, p)) if p > 2 else "!hp_2"            # the town stands at phase p-1 and phase p is not built yet
        cs = "%d gold and %d shards" % (r["cost"]["gold"], r["cost"]["shards"])
        acts.append(SAY(B, "Next is %s: %s" % (PHASE_NAME[p], PHASE_PITCH[p]), **{"if": stage}))
        acts.append(SAY(B, {2: "But it is no good raising walls for nobody. Orla and Tilda are still lost in the ruins: the smith somewhere in the ruins west of the keep terrace, the innkeeper in the rubble on the east side.",
                            3: "But I will not raise a market with no merchant to fill it. Pell and Wick are still out there: a wagon stranded on the road south of the camp, and an angler on the river's east bank.",
                            4: "But a library needs a librarian and a town needs a voice. Sennet is hiding in the rubble at the back of the keep terrace, east side, and Dove keeps watch from the west."}[p],
                        **{"if": stage, "unless": need}))
        if r["gate"]:
            acts.append(SAY(B, {3: "And the keep is not safe to work beside. A Hollow Knight still stalks its steps. Put it down.",
                                4: "And something watches from the back of the keep terrace. A cult seer, by the look of its robes. Deal with it before the masons go near the cliff."}[p],
                            **{"if": stage + "," + need, "unless": r["gate"]}))
        ready = stage + "," + need + (("," + r["gate"]) if r["gate"] else "")
        opt = dict(label="Rebuild: %s (%s)" % (PHASE_NAME[p], cs), actions=[
            ACT("build", who=B, cost=r["cost"], then=[
                SAY(B, "Stand clear! Stone and shard-mortar, lads! Up she goes!"),
                ACT("flag", key="hp_%d" % p),
                ACT("fade", to="black", t=1.4),
                ACT("title", text="Dawnwatch", sub="Phase %s: %s" % ({2: "II", 3: "III", 4: "IV"}[p], PHASE_NAME[p]), t=3.4),
                ACT("warp", scene="strange", x=0, z=28, fresh=True)])])
        acts.append(dict(type="choice", who=B, text="Shall I start? It will cost %s." % cs, options=[opt, dict(label="Not yet", actions=[ACT("end")])], **{"if": ready}))
    acts.append(SAY(B, "Dawnwatch is whole again. Look at her. The foundation stones have not seen this since before the Grey Tide. There is more to do out there, but this is home.", **{"if": "hp_4"}))
    return acts


npc("brannoch", "Brannoch", "Master Mason", "Farmer", -9.0, 47.0, actions=None, reach=5.0)
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


# Orla the blacksmith (west end of the keep terrace) -- pinned by a gargoyle that came alive
resident("orla", "Orla", "Blacksmith", "Blacksmith", (-31.0, -8.0),
         ["A hammer! A friend! Thank the forge. That thing woke when the keep fell and has been sitting on my anvil ever since.",
          "I am Orla. I forged for the garrison here, and I will forge for whoever is brave enough to light the fire again. Get Brannoch to put up a roof, and I will make something worth carrying."],
         "hr_orla", bonus=dict(gold=300, shards=6),
         fight=dict(pre="Keep back! It is... It will not let me leave the forge! It is a gargoyle, the keep's own, and it has gone mad!", pool=["stone_gargoyle"], lr=[0, 2], elite=0.5))
at(1); put(KEN + "bricks", -31.0, -6.5, 30, 0, S); put(KEN + "column-damaged", -33, -9.5, 70, 0, S * 1.2)
# Tilda the innkeeper (the old chapel cellar, north-east of the east cottages)
resident("tilda", "Tilda", "Innkeeper", "Innkeeper", (31.0, -8.0),
         ["...Are they gone? The masked ones, the grey riders? ...You are not one of them. Oh, thank the hearth.",
          "I kept the inn at the Dawn Gate for thirty years. Give me four walls and a bed frame and I will have a stew on by nightfall. A bed costs a little, mind. Love does not pay the baker."],
         "hr_tilda", bonus=dict(gold=200, items={"potion": 3}))
at(1); put(DG + "SM_dg_block", 31.0, -6.5, 0, 0, 1.1)
# Pell the merchant (a stranded wagon on the south road)
resident("pell", "Pell", "Travelling Merchant", "Shopkeeper", (-38.0, 76.0),
         ["Thank the road! Bandits, three of them, and not one could count. They let go of my axle the moment you arrived.",
          "Pell, of Pell and Pell, merchants. There is no other Pell. I carry the best goods three worlds can reach. Give me a stall in a proper market and I will sell you the lot at honest prices."],
         "hr_pell", bonus=dict(gold=400, shards=8),
         fight=dict(pre="Stay back, friend! Bandits... they took my team and left the wagon! Will you help? I can pay you!", pool=["bandit_rogue"], lr=[0, 2], elite=0.6))
at(1); put(ST + "SM_Stylized_Wagon", -38, 77.8, 20, 0, 1.0); block(-38, 77.8, 2.2, 4.4); put(ST + "SM_Hay", -36.5, 77.4, 0, 0, 1.6)
# Wick the angler (the river's east bank)
resident("wick", "Wick", "Angler", "Fisherman", (40.0, 54.3),
         ["Shh! You will scare the... ah, never mind. Nothing is biting. Nothing has bitten since the sky changed.",
          "Wick. I fish. I fished the river at Dawn Gate and now I fish a puddle in a ruin, and I am happy. Get Brannoch to put a proper pier on the bank and I will show you what lives in these waters."],
         "hr_wick", bonus=dict(gold=250, items={"antidote": 2}))
# Sennet the archivist (the library ruin, north-east terrace)
resident("sennet", "Sennet", "Archivist", "Elder", (33.0, -26.0),
         ["Mind the third shelf! Mind... oh. You are not a looter. I can tell by the boots.",
          "I am Sennet, keeper of the Dawnwatch archive. Half of it burned. The other half is in my head and in these notes. Give me a roof and I will keep your records, and you can set your own progress down in my ledger whenever you like."],
         "hr_sennet", bonus=dict(gold=300, shards=10))
# Dove the herald (the herald's tower, north-east)
resident("dove", "Dove", "Young Herald", "Townee", (-33.0, -26.0),
         ["You can see everything from up here. I saw the keep burn, and the grey riders, and I saw you walk in this morning looking like you had been fighting the sky.",
          "I am Dove. The herald, or I was, until there was nobody left to herald to. Let me keep the notice board when the village is up. Somebody should tell people who is missing, and what is needed."],
         "hr_dove", bonus=dict(gold=250, items={"hi_potion": 1}))

# ---- the services (they appear when the resident has settled AND their phase is built)
npc("orla_smith", "Orla", "Blacksmith", "Blacksmith", -36.0, 17.8, action="heroes", show="hr_orla,hp_2")
npc("tilda_inn", "Tilda", "Innkeeper", "Innkeeper", -36.5, 47.0, actions=[SAY("Tilda", "Welcome to the Dawn Gate Inn. A hot meal and a bed for the night is 60 gold, and worth every coin."), dict(type="rest", cost=60)], show="hr_tilda,hp_2")
npc("pell_shop", "Pell", "Item Shop", "Shopkeeper", 36.5, 16.0, action="shop", show="hr_pell,hp_3")
npc("pell_wait", "Pell", "Travelling Merchant", "Shopkeeper", 36.5, 16.0, actions=[SAY("Pell", "Nothing to sell from a ditch, friend. Get me a market and I will open the doors.")], show="hr_pell", hide="hp_3")
npc("wick_pond", "Wick", "Angler", "Fisherman", 12.4, 54.2, actions=[SAY("Wick", "Try the end of the pier. Floats best when you do not look at it. A bite now and then, even in ruins."), dict(type="fishing", op="shop")], show="hr_wick,hp_3")
npc("wick_wait", "Wick", "Angler", "Fisherman", 40.0, 54.3, actions=[SAY("Wick", "Nobody fishes a ruin. Get me a pier and a bench and I will have this river singing.")], show="hr_wick", hide="hp_3")
npc("sennet_archive", "Sennet", "Archivist", "Elder", 33.0, -14.0, action="save_and_quit", show="hr_sennet,hp_4")
npc("sennet_wait", "Sennet", "Archivist", "Elder", 33.0, -26.0, actions=[SAY("Sennet", "The archive is not open yet. Give me a roof over the shelves.")], show="hr_sennet", hide="hp_4")
npc("dove_board", "Dove", "Herald", "Townee", 10.4, 13.6, actions=[SAY("Dove", "I keep the board, and the board keeps Dawnwatch honest. Read it, Kenji. It says who is missing and what the next stones cost.")], show="hr_dove,hp_3")
npc("dove_wait", "Dove", "Young Herald", "Townee", -33.0, -26.0, actions=[SAY("Dove", "A board and a village to herald to, that is all I want. Ask Brannoch.")], show="hr_dove", hide="hp_3")
# townsfolk who come with the phases
npc("t_guard", "Gate Warden", "Dawnwatch Guard", "Warden", 6.0, 50.0, actions=[SAY("Gate Warden", "Dawnwatch is not safe yet, but it is ours. Keep to the road and shout if you see grey riders.")], show="hp_2")
npc("t_villager1", "Maren", "Villager", "Townee", -14.0, 24.0, actions=[SAY("Maren", "A real roof! I had forgotten what the rain sounded like on one.")], show="hp_3")
npc("t_villager2", "Old Joss", "Villager", "Farmer", 8.0, 44.0, actions=[SAY("Old Joss", "They say worlds fall into this one. If more of them bring bread, I say let them.")], show="hp_3")
npc("t_knight", "Ser Calder", "Keep Captain", "Warden", KX + 5.0, KZ + 13.0, actions=[SAY("Ser Calder", "The keep is yours to command, Kenji. Command it well. Dawnwatch has had too many bad kings and too few good gardeners.")], show="hp_4")
npc("t_herald4", "Town Crier", "Crier", "Mayor", 0.0, 9.5, actions=[SAY("Town Crier", "Hear ye! Dawnwatch stands, and the road beyond lies open! Heroes, take heart!")], show="hp_4")

# townsfolk of the grown town (they move in with the phases)
npc("t_harbour", "Harbourmaster Bryn", "Harbourmaster", "Dockmaster", -18.0, 54.2, actions=[SAY("Bryn", "Salt, tar and honest rope. Give me a season and a crew and these piers will be loud again. Mind the boats; they bite.")], show="hp_3")
npc("t_netter", "Net-mender Hale", "Fisherman", "Fisherman", 43.0, 54.2, actions=[SAY("Hale", "The river runs clear since the Tide went out. Fat silver things, turning in the shallows. I swear they watch me work.")], show="hp_3")
npc("t_ferry", "Ferryman Ibb", "Ferryman", "Ferryman", 3.5, 77.0, actions=[SAY("Ibb", "The west bridge saves me a living, they tell me. I had a living? I thought I had a boat.")], show="hp_3")
npc("t_dame", "Market Dame Orsa", "Market Dame", "Shopkeeper", 23.5, 28.5, actions=[SAY("Orsa", "Honey, onions, a good knife. Nothing from the old stores, mind. Everything on this table was grown or made here since the Tide.")], show="hp_3")
npc("t_cheese", "Pip", "Cheesemonger", "Townee", 23.5, 41.5, actions=[SAY("Pip", "Free sample! Do not ask what it is. It is cheese. It is definitely cheese.")], show="hp_4")
npc("t_marrow", "Old Marrow", "Angler", "Fisherman", -43.0, 54.2, actions=[SAY("Old Marrow", "Wick has the west of the bridge, I have the east. We do not speak of the big one.")], show="hp_3")
npc("t_dunn", "Farmer Dunn", "Farmer", "Farmer", -40.0, 76.4, actions=[SAY("Farmer Dunn", "Wheat in a valley that was ash a season ago. Do not tell the soil. It has not noticed.")], show="hp_3")
npc("t_dunna", "Goodwife Tam", "Farmer", "Townee", 40.0, 76.4, actions=[SAY("Tam", "Eggs, if the hens cooperate. They have opinions about the gate. Loud ones.")], show="hp_3")
npc("t_gardener", "Gardener Linnet", "Gardener", "Townee", 20.0, -9.0, actions=[SAY("Linnet", "The keep had a garden once. Under the rubble the roots were still alive. I only asked them nicely.")], show="hp_4")

# ---- story gates (fights)
npc("knight", "Hollow Knight", "Haunt of the keep", "Draven", KX + 4.0, KZ + 17.0, tint=[0.55, 0.6, 0.85, 1], h=2.8, reach=5.0, hide="hg_knight",
    actions=[SAY("Hollow Knight", "...THE KEEP... IS NOT... TO BE ENTERED. THE KING... HAS NOT... RETURNED."), dict(type="battle", key="hg_knight", pool=["cursed_knight"], level_rel=[1, 3], elite=1.2)])
npc("seer", "Cult Seer", "Watcher at the keep", "Rook", -30.0, -30.0, tint=[0.7, 0.45, 1.1, 1], h=2.8, reach=5.0, hide="hg_seer",
    actions=[SAY("Cult Seer", "He walks! The Heart's shadow walks! The Mind will be pleased to hear it."), dict(type="battle", key="hg_seer", pool=["dark_cultist"], level_rel=[1, 3], elite=1.2)])

# ---- events
event("dw_rest", "Rest crystal", -5, 44.5, [SAY("", "Soft light settles over the party. Wounds close and breath comes easy. The crystal hums and remembers this place: it is now your save point."), dict(type="checkpoint"), dict(type="rest")], "Rest and save at the crystal", w=3, d=2.6)
event("dw_board", "Notice board", 8.0, 12.5, board(), "Read the notice board", w=3.4, d=2.4, show="hp_3")
at(3); put(ST + "SM_Stylized_WantedBoard", 8.0, 12.5, 180, 0, 1.4); block(8.0, 12.5, 2.4, 0.5)
event("dw_fish", "Fishing spot", 16.0, 61.2, [SAY("", "The end of the pier. The water is clear enough to see the stones, and a few fat shapes turning in the current."), dict(type="game", game="fish", stake=0, spot="pier", scene="fish_pier")], "Drop a line", w=3.0, d=3.0, show="hp_3")
event("dw_plate", "Weathered plate", -4.0, 50.0, [SAY("Weathered Plate", "DAWNWATCH KEEP. WHERE THE REALM FIRST SAW THE MORNING. WHEN THE GREY TIDE CAME, THE GATE WAS THE LAST TO FALL.", hide="hp_4"),
                                                 SAY("", "Scratched under the lettering in an older hand, half worn away: ELDERGATE.", show="eg_open"),
                                                 SAY("Weathered Plate", "DAWNWATCH KEEP. REBUILT BY THE LAST OF THE REALM'S FRIENDS, AND BY THOSE WHO FELL INTO IT FROM THE SKY.", show="hp_4")], "Read the plate", w=3.2, d=2.4)
at(1); put(DG + "SM_dg_block", -4.0, 50.6, 0, 0, 0.9)
event("dw_throne", "Broken dais", KX - 9.0, KZ + 14.0, [SAY("", "A cracked dais of pale stone, scorched black along one edge. Something very large sat here once."),
                                                       SAY("", "The air above it is faintly cold.", hide="hp_4"), SAY("", "A banner of the new Dawnwatch hangs over it. The chill is gone.", show="hp_4")], "Look at the dais", w=4, d=3, show="hg_knight")

STAIR_DOWN = [ACT("fade", to="black", t=0.9), ACT("warp", scene="eldergate", x=0, z=22, fresh=True)]
event("dw_stair", "Sunken Stair", KX, KZ + 6.7, [
    SAY("", "A ring of cracked paving, nine bands wide, set in the terrace below the great arch. Every crack is faintly warm. The golden mark on Kenji's hand throbs in time with the hum under your boots.", **{"unless": "eg_open"}),
    SAY("Kenji", "It knows me. Whatever this is, it has been waiting.", **{"unless": "eg_open"}),
    SAY("Miya", "Brannoch said stones remember. I think these remember a hand like yours.", **{"unless": "eg_open"}),
    ACT("flash", **{"unless": "eg_open"}),
    SAY("", "Kenji lays his palm on the stone. The rings turn against each other like the gears of a clock, and the great arch behind you wakes: blue fire fills it from base to crown, and a column of light climbs into the sky. The dais sinks, step by step, into a stair that was never meant to be found.", **{"unless": "eg_open"}),
    ACT("flag", key="eg_open", **{"unless": "eg_open"}),
] + STAIR_DOWN, "Touch the ring stone", w=4.4, d=2.6, show="hr_mason")

# ---- treasure that helps fund the rebuild
chest("hc1", -26.0, 17.0, dict(gold=500, shards=10))
chest("hc2", 29.0, 49.0, dict(gold=450, shards=8, items={"potion": 2}))
chest("hc3", -33.0, -30.0, dict(gold=600, shards=12))
chest("hc4", 22.0, -32.0, dict(gold=700, shards=14))
chest("hc5", -20.0, -33.0, dict(gold=650, shards=12, items={"ether": 1}))
chest("hc6", 33.0, -30.0, dict(gold=900, shards=18))
chest("hc7", 0.0, -35.0, dict(gold=1200, shards=24))
chest("hc8", -44.0, 40.0, dict(gold=500, shards=10))
chest("hc9", -34.0, -14.0, dict(gold=700, shards=14, items={"ether": 1}))
chest("hc10", 44.0, 40.0, dict(gold=600, shards=12))
chest("hc11", 44.0, 82.0, dict(gold=800, shards=16))
chest("hc12", -44.0, 82.0, dict(gold=500, shards=10, items={"potion": 2}))
chest("hc13", 34.0, -14.0, dict(gold=900, shards=18))
chest("hc14", -44.0, 24.0, dict(gold=600, shards=12))

# ------------------------------------------------------------------ cutscenes: the wake-up (arrival) and one reveal per phase
WAKE = [
    ACT("cine", on=True),
    dict(type="music", url=MUSIC + "05. Long Journey.mp3"),
    ACT("fade", to="clear", t=3.0, wait=False),
    ACT("cam", x=0, z=46, yaw=0, pitch=62, dist=30, t=0),
    SAY("", "Cold stone. Woodsmoke. The slow creak of something very old settling in the wind."),
    ACT("cam", x=-6, z=42, yaw=0, pitch=40, dist=14, t=4, wait=False),
    SAY("Kenji", "...Miya? Lyra?"),
    SAY("Miya", "Here. I think. Everything hurts, but it is the ordinary kind of hurt."),
    SAY("Lyra", "Look at the sky. I count one sun, and it is the wrong colour for any sun I know. This is not on Rook's maps."),
    SAY("Kenji", "He was never Rook."),
    SAY("Lyra", "No. And he is still out there, with that thing in his hand and a door open behind him."),
    ACT("walk", who="brannoch", x=-8.0, z=44.0, speed=2.6),
    SAY("Brannoch", "Easy, easy. Three more of you, are there? That is the fourth batch to fall out of the sky this season, and the first with swords."),
    SAY("Kenji", "Where are we?"),
    SAY("Brannoch", "Dawnwatch, or what the Grey Tide left of her. I am Brannoch, mason, and the last of the garrison's builders. The rest are rubble or runaways."),
    ACT("cam", x=0, z=4, yaw=0, pitch=30, dist=44, t=5, wait=False),
    SAY("Brannoch", "Look north, past the bridge. That was a market square, and up the great stair at the head of it, the keep. Folk wash up here from all over: other realms, other skies, a few with no world to go back to."),
    SAY("Miya", "The Tide. The Mind's doing, then. His fingerprints are everywhere."),
    SAY("Brannoch", "Whoever he is, he picked the wrong foundation to knock down. This valley sat on the first sunrise. Stones remember. Give me hands, a little coin and a few shards of that violet glass you lot bleed, and I will make her stand again."),
    SAY("Brannoch", "And there are people hidden in these ruins who would stand with us, if they were found. Orla the smith, Tilda the innkeeper... Find them. Bring them home. A town is its people, whatever the masonry says."),
    ACT("cam", x=-6, z=44, yaw=0, pitch=36, dist=20, t=2.5, wait=False),
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


R2 = reveal(2, [dict(type="cam", x=0, z=44, yaw=0, pitch=40, dist=30, t=0), dict(type="cam", x=-30, z=22, yaw=-0.35, pitch=26, dist=28, t=5, wait=False)],
            [SAY("", "Canvas goes up over the broken foundations. Smoke rises from new fires on both banks. A forge hammer rings across the water, and a pot begins to simmer."),
             SAY("Brannoch", "Not much to look at yet, but it is a camp, and a camp is how every town starts. Orla has her anvil under cloth on the square's west side, and Tilda has hung a lantern by the old inn. Go and see them."),
             SAY("Miya", "It looks lived in already.")], "04. Peaceful Village.mp3")
R3 = reveal(3, [dict(type="cam", x=0, z=44, yaw=0, pitch=34, dist=40, t=0), dict(type="cam", x=0, z=0, yaw=0, pitch=30, dist=44, t=7, wait=False)],
            [SAY("", "Where there was rubble, there are walls. Roofs of red and slate climb the lots, boats nose the new pier, and a fountain throws water in the square again. Up the great stair the keep's gate towers have teeth."),
             SAY("Brannoch", "There! Houses for the folk, a market for Pell, a pier for Wick, and a board for young Dove. The gate towers are up. The curtain... well. We never needed a wall, with these hills wrapped round us."),
             SAY("Lyra", "Four days ago this was a graveyard. I think I will start calling it a town.")], "02. Lively City.mp3")
R4 = reveal(4, [dict(type="cam", x=0, z=46, yaw=0, pitch=24, dist=40, t=0), dict(type="cam", x=0, z=-20, yaw=0, pitch=18, dist=52, t=8, wait=False)],
            [SAY("", "Banners fill the wind along the quay. At the head of the square the keep stands crowned in towers, and in the heart of its great arch, the old gate burns blue."),
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
    {"unless": "eg_open", "text": "Brannoch mentioned a humming paved ring on the keep terrace, below the great arch. Try your hand on it."},
    {"if": "eg_open", "unless": "eg_core", "text": "Explore the Eldergate Network beneath Dawnwatch (the Sunken Stair, in the keep's forecourt)."},
    {"if": "eg_core", "unless": "eg_veyra_go", "text": "The Veyra gate beneath Dawnwatch is open (the Sunken Stair, in the keep's forecourt). Rebuilding can wait for you."},
    {"if": "hp_4", "text": "Dawnwatch is whole. (The way out of the valley opens in a later chapter.)"},
    {"if": "hp_3", "text": "Phase IV, the Castle Town: find Sennet (the rubble at the back of the keep terrace, east) and Dove (west end of the same terrace), defeat the Cult Seer behind the keep, then bring gold and shards to Brannoch."},
    {"if": "hp_2", "text": "Phase III, the Village: find Pell (the wagon on the south road, across the bridge) and Wick (the east end of the quay), defeat the Hollow Knight in the keep's forecourt, then bring gold and shards to Brannoch."},
    {"text": "Phase II, the Camp: find Orla (west end of the keep terrace) and Tilda (east end of it), then bring gold and shards to Brannoch. Chests in the ruins help pay for it."},
]

ISL = json.load(open(os.path.join(HERE, "island.json"), encoding="utf-8"))
scene = {
    "story": True, "restart": "sg_", "name": "Dawnwatch", "kit": "", "tile": 4,
    "autorun": [], "objectives": [],   # styling pass: no story scripting yet (AUTORUN / OBJECTIVES are kept above)
    "music": [{"if": "hp_4", "url": MUSIC + "03. Royal Castle.mp3"}, {"if": "hp_3", "url": MUSIC + "02. Lively City.mp3"},
              {"if": "hp_2", "url": MUSIC + "04. Peaceful Village.mp3"}, {"url": MUSIC + "05. Long Journey.mp3"}],
    "pieces": T.P, "colliders": T.COL, "decals": T.DEC, "npcs": [], "events": [],   # styling pass: NPCs / events / chests are built above but not emitted (NPCS, EVENTS)
    "terrain": DH.terrain_json(), "walk": WALK,
    "spawn": {"x": 0, "z": 50}, "bounds": {"minX": -46, "maxX": 46, "minZ": -37, "maxZ": 90}, "playerHeight": 2.4,
    "camera": {"pitch": 22, "dist": 34},
    "light": {"dir": [-0.45, -1, -0.35], "color": [1.0, 0.93, 0.8], "ambient": [0.46, 0.49, 0.58]}, "fog": {"color": [0.72, 0.82, 0.92], "near": 110, "far": 320}, "sky": ISL["sky"],
    "fx": [{"type": "dust", "amount": 0.1}], "lod": {"match": "Tree_0", "dist": 110, "res": 256},
    "encounters": {"rate": 62, "level": [22, 26], "level_rel": [0, 2], "pool": ["stone_gargoyle", "bandit_rogue", "goblin_skirmisher", "dark_cultist", "cursed_knight"],
                   "zones": [{"x": 0, "z": 26, "w": 100, "d": 140, "safe": True}],
                   "text": "Something stirs in the rubble..."},
}

if __name__ == "__main__":
    out = os.path.join(sys.argv[1] if len(sys.argv) > 1 else HERE, "strange.json")
    with open(out, "w", encoding="utf-8", newline="") as f:
        json.dump(scene, f, ensure_ascii=False, separators=(",", ":"))
    print("strange.json:", len(T.P), "pieces,", len(T.COL), "colliders,", len(NPCS), "npcs,", len(EVENTS), "events,", len(trees), "trees")

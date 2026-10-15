"""Builds html_hub/3d/strange.json: "Dawnwatch" (v7) on the landscape sculpted in the 3D editor (dw_land.json, read through dwland.py).
The terrain heights, the painted splat map, the lake planes, the bridge segments and the citadel's round forecourt are the editor's and are kept as they are; this script adds
one grand ramp up to the citadel plateau (dwland.py) and builds the town on the terraces:
  basin (y 32, repainted grass) : a cobbled plaza with the fountain and stalls, ringed by houses on cobbled streets, piers on the south shore, the service lots, houses under the north wall, the survivors' camp, the quay
  west terraces (37 / 53 / 61): cottages, the chapel with its clock tower, the grand ramp
  citadel (y 85)              : the keep round the great arch (the Eldergate portal), the barracks
  east (47 / 55 / 74)         : the library, farmland, stables, the watchtower
  south bank (y 32)           : a row of houses facing the lake
The four rebuild phases (flags hp_2..hp_4) work as before: ruin piles until a house's phase.  NPCs / events / cutscenes are not emitted in this styling pass.
x east, z south."""
import json, math, os, random, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kenhouse, stylhouse
import dwland as DH

KEN = kenhouse.KEN
GC, ST, PA, DG, GEN = ("/assets/3D/GodCity/", "/assets/3D/Stylized/", "/assets/3D/Paradise/", "/assets/3D/Dungeon/", "/assets/3D/Generated/")
S = kenhouse.S
rng = random.Random(1307)
gy = DH.gy
LAKE_Y = DH.WATER_Y


def spec_of(show=None, hide=None):
    if show and hide: return "S:%s,!%s" % (show, hide)
    if show: return "S:" + show
    if hide: return "H:" + hide
    return None


def phase_vis(frm=1, to=None):
    return (("hp_%d" % frm) if frm > 1 else None), (("hp_%d" % to) if to else None)


class Hub(stylhouse.Town):
    def __init__(self):
        super().__init__(gy=gy)
        self.cur = (None, None)

    def at(self, frm=1, to=None):
        self.cur = phase_vis(frm, to); return self

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
        self.at(frm, to)
        if base is None:
            base = max(gy(x + dx, z + dz) for dx in (-4, 0, 4) for dz in (-4, 0, 4)) - 0.1
        return self.house(x, z, rot, base=base, **kw)


T = Hub()
put, block, at, ken = T.put, T.block, T.at, T.ken
WALK = []
FOOT = []                                            # (x, z, r) of everything built, so scatter and later buildings keep clear
REPORT = []


def free(x, z, r=0.0):
    return all(math.hypot(x - a, z - b) > r + rr for a, b, rr in FOOT)


def claim(x, z, r):
    FOOT.append((x, z, r))


def flat_ok(x, z, r=5.5, tol=0.8):                       # r = half the square that has to be level
    hs = [gy(x + dx, z + dz) for dx in (-r, 0, r) for dz in (-r, 0, r)]
    return max(hs) - min(hs) <= tol and not DH.carved(x, z, r + 1)


# ------------------------------------------------------------------ the editor's pieces (lake planes, bridge segments, the round forecourt ...) are kept
BR_HW, BR_L = 3.7, 19.5
for p in DH.LAND["pieces"]:
    nm = p[0].split("/")[-1]
    if nm in ("SM_dw_portal_frame", "SM_dw_portal_glow", "SM_dw_portal_beam"): continue        # the arch is rebuilt below, in the same spot, with its phases
    T.P.append(list(p))
    if nm == "SM_dw_bridge":
        bx, bz, by = p[1], p[2], p[4]
        WALK.append(dict(x=bx, z=bz, w=2 * BR_HW - 0.2, d=BR_L, rot=0, y=by))
        at(1)
        for sgn in (-1, 1): block(bx + sgn * (BR_HW - 0.3), bz, 0.7, BR_L)
BRIDGES = sorted({p[1] for p in DH.LAND["pieces"] if p[0].endswith("SM_dw_bridge")})
BR_SPANS = {bx: (min(p[2] for p in DH.LAND["pieces"] if p[0].endswith("SM_dw_bridge") and p[1] == bx) - BR_L / 2,
                 max(p[2] for p in DH.LAND["pieces"] if p[0].endswith("SM_dw_bridge") and p[1] == bx) + BR_L / 2) for bx in BRIDGES}
for bx, (za, zb) in BR_SPANS.items():
    for zz in (za + 0.6, zb - 0.6):                                                                     # lamps and flags on the bridge heads
        for sgn in (-1, 1):
            x = bx + sgn * (BR_HW - 0.3); by = gy(bx, zz + (3 if zz < (za + zb) / 2 else -3))
            at(3); put("SM_Stylized_Lamp_C", x, zz, 0, 1.7, 2.2); T.glow(x, zz, 5.0, [1, 0.82, 0.5, 0.5], 3, None, h=2.6)
            at(4); put("SM_Stylized_Flag_Var%d" % (1 if sgn < 0 else 2), x, zz + (0.9 if zz < (za + zb) / 2 else -0.9), 0, 1.7, 2.2)

# ------------------------------------------------------------------ the market square (basin, y 32): a cobbled plaza round the fountain, ringed by houses
PX, PZ = 14.0, 2.0
PLAZA_R = 17.0
claim(PX, PZ, 19)
at(1, 3)
put(KEN + "bricks", PX, PZ, 10, 0, S * 1.4); put(KEN + "column-damaged", PX - 2.4, PZ - 1, 35, 0, S * 1.1); put(KEN + "bricks", PX + 2.8, PZ + 1.7, 120, 0, S * 0.9); block(PX, PZ, 4.0, 4.0)
for i in range(14):
    x, z = PX + rng.uniform(-22, 22), PZ + rng.uniform(-18, 20)
    if abs(x - PX) < 6 and abs(z - PZ) < 6: continue
    if i % 2: ken("column-damaged", x, z, rng.randint(0, 359), 0, S * rng.uniform(0.9, 1.3))
    else: ken("bricks", x, z, rng.randint(0, 359), 0, S * rng.uniform(0.6, 0.9))
at(3)
put(ST + "SM_Stylized_Fountain", PX, PZ, 0, 0, 2.5); block(PX, PZ, 9.4, 8.9); T.glow(PX, PZ, 11, [0.55, 0.85, 1.0, 0.25], 3, None, h=2.6)
for (dx, dz) in ((-11, -9.5), (11, -9.5), (-11, 9.5), (11, 9.5), (-15, 0), (15, 0), (0, -16), (0, 16)): T.lamp(PX + dx, PZ + dz)
for (dx, dz, r) in ((-8, 0, 90), (8, 0, 270), (0, -8, 0), (0, 8, 180), (-13, -7, 0), (13, -7, 0), (-13, 7, 180), (13, 7, 180)): at(3); put(ST + "SM_Stylized_Bench", PX + dx, PZ + dz, r, 0, 2.2)
STALLS = [(-17.5, -14, 180, "SM_market_tent_01"), (-8.8, -15.5, 180, "SM_market_tent_02"), (8.8, -15.5, 180, "SM_market_tent_03"), (17.5, -14, 180, "SM_market_tent_01"),
          (15, -3, 270, "SM_market_tent_03"), (15, 4, 270, "SM_market_tent_03"), (15, 11, 270, "SM_market_tent_03"),
          (-15, -3, 90, "SM_market_tent_03"), (-15, 4, 90, "SM_market_tent_03"), (-15, 11, 90, "SM_market_tent_03")]
for (dx, dz, r, tent) in STALLS:
    at(3); put(GC + tent, PX + dx, PZ + dz, r, 0, 1.0); block(PX + dx, PZ + dz, 4.8 if r in (90, 270) else 5.0, 5.0 if r in (90, 270) else 8.0 if tent != "SM_market_tent_03" else 4.8)
at(3)
for (dx, dz) in ((-12, -10.5), (12, -10.5), (-12, 10.5), (12, 10.5)):
    put(ST + "SM_Stylized_Table_A", PX + dx, PZ + dz, 90, 0, 1.0); block(PX + dx, PZ + dz, 1.4, 2.7); put(ST + "SM_Stylized_Basket", PX + dx, PZ + dz + 0.8, 0, 0.93, 1.2)
at(4)
for (dx, dz, v) in ((-6, 17, 1), (6, 17, 2), (-15, -17, 1), (15, -17, 2), (-17, 14, 1), (17, 14, 2)): put(ST + "SM_Stylized_Flag_Var%d" % v, PX + dx, PZ + dz, 0, 0, 2.6)

# ---- the survivors' camp, south-west corner of the square, by the quay
CPX, CPZ = -14.0, 33.0
claim(CPX, CPZ, 14)
at(1)
put(ST + "SM_Stylized_Bonfire", CPX, CPZ, 0, 0, 1.6); block(CPX, CPZ, 2.0, 2.0); T.glow(CPX, CPZ, 7, [1, 0.62, 0.3, 0.5], h=1.2)
put(DG + "SM_dg_crystal", CPX + 7, CPZ + 0.5, 0, 0, 2.0); block(CPX + 7, CPZ + 0.5, 1.4, 1.4); T.glow(CPX + 7, CPZ + 0.5, 6, [0.55, 0.85, 1, 0.3], h=1.5)
at(1, 3)
for (dx, dz, r) in ((-10, -3, 90), (9.5, -4.5, 270)): put(GC + "SM_market_tent_03", CPX + dx, CPZ + dz, r, 0, 1.1); block(CPX + dx, CPZ + dz, 4.8, 4.0)
at(1)
put(ST + "SM_Stylized_Table_A", CPX - 5, CPZ - 6, 0, 0, 1.1); block(CPX - 5, CPZ - 6, 2.7, 1.3)
for (dx, dz) in ((-8.5, -8.5), (-2.5, -9.5), (-7.5, -11.5)): put(GC + "SM_construction_block_01", CPX + dx, CPZ + dz, rng.randint(0, 359), 0, 1.2); block(CPX + dx, CPZ + dz, 1.5, 1.5)
put(ST + "_Stylized_Barrel", CPX - 3, CPZ + 2.5, 0, 0, 1.2); put(ST + "SM_Stylized_Box_var1", CPX - 1.5, CPZ + 3.5, 20, 0, 1.2)
at(2, 3)
put(ST + "SM_Stylized_Bonfire", CPX - 15, CPZ + 5, 0, 0, 1.3); T.glow(CPX - 15, CPZ + 5, 6, [1, 0.62, 0.3, 0.45], 2, 3, h=1.2)
for i, (dx, dz) in enumerate(((-19, -3), (-18, 3.5), (24, 2), (25, -4))):
    put(GC + ("SM_market_tent_02" if i % 2 else "SM_market_tent_01"), CPX + dx, CPZ + dz, 90 if dx < 0 else 270, 0, 1.0); block(CPX + dx, CPZ + dz, 4.6, 8.0)

# ------------------------------------------------------------------ houses (ruin pile until phase 3 or 4, then a house)
_n = [0]
WALLS = ("stone", "cream", "stone", "blue", "cream", "stone", "rose"); ROOFS = ("slate", "brown", "slate", "red", "slate", "brown")


def house_at(x, z, rot, ph, floors=None, bays=2, wall=None, roof=None, need_flat=True, fr=5.0, fc=5.2):
    if need_flat and not (flat_ok(x, z, fr) and free(x, z, fc)): return False
    k = _n[0]; _n[0] += 1
    at(1, ph)
    put(KEN + "bricks", x, z, rot, 0, S * 1.0); put(KEN + "column-damaged", x + 1.8, z - 1.4, rot + 30, 0, S); put(KEN + "bricks", x - 2.0, z + 1.5, rot + 80, 0, S * 0.7); block(x, z, 3.2, 3.2)
    T.lot_house(x, z, rot, ph, wall=wall or WALLS[k % 7], roof=roof or ROOFS[k % 6], floors=floors or (1, 2, 2, 1)[k % 4], bays=bays, door_bay=k % 2)
    a = math.radians(rot); c, s = math.cos(a), math.sin(a)
    T.lamp(x + 6.6 * s - 2.0 * c, z + 6.6 * c + 2.0 * s, frm=ph)                                      # a lantern at the door
    claim(x, z, 5.2)
    DOORS.append((x + 7.5 * s, z + 7.5 * c))
    return True


DOORS, STREETS = [], []                                 # door points of every house; streets = polylines the paint pass turns into cobbled paths


def row(xs, z, rot, phases, **kw):
    n = 0; pts = []
    for i, x in enumerate(xs):
        if house_at(x, z, rot, phases[i % len(phases)], **kw): n += 1; pts.append(DOORS[-1])
    if len(pts) > 1: STREETS.append(pts)
    elif pts: STREETS.append(pts + [(pts[0][0] + 0.01, pts[0][1])])
    return n


def col(x, zs, rot, phases, **kw):
    n = 0; pts = []
    for i, z in enumerate(zs):
        if house_at(x, z, rot, phases[i % len(phases)], **kw): n += 1; pts.append(DOORS[-1])
    if len(pts) > 1: STREETS.append(pts)
    return n


# service lots on the quay side of the square: a tent from phase 2, a house from phase 3
LOTS = {"smith": dict(x=-26.0, z=26.0, rot=0, wall="stone", roof="brown", floors=1, tent="SM_market_tent_02"),
        "inn":   dict(x=-4.0, z=30.0, rot=0, wall="cream", roof="red", floors=2, tent="SM_market_tent_01"),
        "shop":  dict(x=30.0, z=28.0, rot=0, wall="blue", roof="slate", floors=1, tent=None)}
for name, L in LOTS.items():
    if L["tent"]:
        at(2, 3); put(GC + L["tent"], L["x"], L["z"], L["rot"] + 90, 0, 1.05); block(L["x"], L["z"], 4.8, 8.4)
    T.lot_house(L["x"], L["z"], L["rot"], 3, wall=L["wall"], roof=L["roof"], bays=2, floors=L["floors"], door_bay=0)
    claim(L["x"], L["z"], 6)
at(3)
put(ST + "SM_Stylized_Bonfire", -26.0, 21.5, 0, 0, 0.9); T.glow(-26, 21.5, 4.5, [1, 0.5, 0.2, 0.55], 3, None, h=1.5)
put(ST + "SM_Stylized_Table_A", 36.0, 24.0, 0, 0, 1.0); block(36, 24, 2.7, 1.4)

# basin: houses under the north wall facing the square, and along the east side
row([-12 + 9.5 * i for i in range(7)], -35.5, 0, (3, 4, 3, 4, 3, 4, 4), fr=4.2, fc=4.6)             # north shelf, above the plaza
col(-11.5, [-22, -12, -1, 13, 24], 90, (4, 3, 4, 4, 3), fr=3.8, fc=4.6)                          # west shelf
col(40.5, [-22, -12, -1, 13, 24], 270, (4, 3, 4, 4, 3), fr=3.8, fc=4.6)                          # east shelf
# west terraces
row([-60, -49, -38, -29 + 0], 15.0, 0, (3, 3, 4, 4))
row([-56, -45, -35], -10.0, 0, (3, 4, 4))
row([-50, -39, -28, -17], -36.0, 0, (3, 4, 3, 4))
row([-50, -39], -52.0, 0, (4, 3))
# east terraces
row([88, 99, 110, 121, 132], -28.0, 0, (4, 3, 4, 4, 3))
row([88, 99], 30.0, 180, (3, 4))

# ------------------------------------------------------------------ the chapel and its clock tower (west61 plateau), ruined until phase III
CX, CZ = -34.0, -52.0
if flat_ok(CX, CZ, 8, 1.2):
    claim(CX, CZ, 13)
    at(1, 3)
    for (x, z, r) in ((-14, -24, 20), (-2, -26, 100), (-10, -36, 60), (-3, -33, 150), (-14, -31, 80), (0, -30, 10)): ken("wall-fortified-half" if r % 3 else "column-damaged", CX + x + 8, CZ + (z + 30), r, 0, S * 1.1)
    for i in range(9): ken("bricks", CX + rng.uniform(-8, 8), CZ + rng.uniform(-8, 7), rng.randint(0, 359), 0, S * rng.uniform(0.6, 0.9))
    block(CX, CZ, 11, 9); T.glow(CX, CZ - 1, 7, [0.6, 0.7, 1.0, 0.25], 1, 3, h=1.2)
    at(3)
    T.house(CX, CZ - 4.0, 0, floors=2, bays=3, wall="stone", roof="slate", door_bay=0, windows="many", base=gy(CX, CZ) - 0.1, collide=True)
    tw_x, tw_z, tw_sc = CX, CZ + 4.4, S * 1.55
    ken("tower-base", tw_x, tw_z, 0, 0, tw_sc); ken("tower", tw_x, tw_z, 0, tw_sc, tw_sc); ken("tower", tw_x, tw_z, 0, tw_sc * 2, tw_sc); ken("tower", tw_x, tw_z, 0, tw_sc * 3, tw_sc)
    ken("tower-top", tw_x, tw_z, 0, tw_sc * 4, tw_sc); block(tw_x, tw_z, 5.0, 5.0)
    put(GEN + "SM_dw_clock", tw_x, tw_z + tw_sc * 0.5 + 0.06, 0, tw_sc * 3.5, 1.5)
    put(GEN + "SM_dw_clock", tw_x - tw_sc * 0.5 - 0.06, tw_z, 270, tw_sc * 3.5, 1.5)
    at(4)
    put(GEN + "SM_dw_banner", CX + 5.2, CZ + 2.5, 0, 4.2, 1.1); put(GEN + "SM_dw_banner", CX - 5.2, CZ + 2.5, 0, 4.2, 1.1)
    T.glow(tw_x, tw_z + 3, 8, [1.0, 0.85, 0.5, 0.3], 4, None, h=11.0)
else: REPORT.append("chapel spot not flat")

# ------------------------------------------------------------------ the library (east47 terrace), ruined until phase IV
LX, LZ = 56.0, 12.0
if flat_ok(LX, LZ, 7, 1.2):
    claim(LX, LZ, 12)
    at(1, 4)
    for (x, z, r) in ((-6, -2, 15), (-3, -6, 60), (5, -3, 100), (7, 2, 10), (0, 3, 150)): ken("column-damaged" if r % 2 else "wall-half", LX + x, LZ + z, r, 0, S * 1.2)
    for i in range(8): ken("bricks", LX + rng.uniform(-8, 8), LZ + rng.uniform(-7, 7), rng.randint(0, 359), 0, S * rng.uniform(0.6, 0.9))
    block(LX, LZ, 11, 9)
    T.lot_house(LX, LZ, 270, 4, wall="stone", roof="slate", floors=2, bays=3, door_bay=0, windows="many")
    at(4); T.lamp(LX - 7.5, LZ + 3, frm=4); T.lamp(LX - 7.5, LZ - 3, frm=4); put(GEN + "SM_dw_banner", LX - 5.0, LZ + 6.4, 270, 6.0, 1.2)
else: REPORT.append("library spot not flat")

# ------------------------------------------------------------------ the keep round the great arch, on the citadel plateau (the editor's forecourt disc lies in front of it)
KX, KZ = 24.0, -67.0
KY = gy(KX, KZ)
claim(KX, KZ, 22)


def tower(x, z, sc, mids, ph_up, ph_roof=4):
    sc = S * sc
    at(1, ph_up); ken("tower-base", x, z, 0, 0, sc); ken("column-damaged", x, z, 0, sc, sc * 0.9); ken("bricks", x + 1.6, z + 1.4, 30, 0, S)
    at(ph_up); ken("tower-base", x, z, 0, 0, sc)
    for m in range(mids): ken("tower", x, z, 0, sc * (1 + m), sc)
    block(x, z, 1.05 * sc, 1.05 * sc)
    at(ph_roof); ken("tower-top", x, z, 0, sc * (1 + mids), sc)


GATE_HALF = 7.2
for side in (-1, 1):
    for i in range(3):                                                                              # front wall: stump -> wall (III) -> second tier + battlements (IV)
        x = KX + side * (GATE_HALF + 1.4 + i * S); z = KZ + 0.6
        at(1, 3); ken("wall-fortified-half" if i % 2 else "bricks", x, z, 0, 0, S * (1.0 if i % 2 else 1.1))
        at(3); ken("wall-fortified-window" if i % 3 == 1 else "wall-fortified", x, z, 0, 0, S); block(x, z, S, 1.2)
        at(4); ken("wall-fortified-window" if i % 2 == 0 else "wall-fortified", x, z, 0, S, S); ken("battlement", x, z, 0, 2 * S, S)
    for i in range(5):                                                                              # side wings running back from the end towers
        x = KX + side * 16.5; z = KZ - 1.4 - i * S
        at(3); ken("wall-fortified", x, z, 90, 0, S); block(x, z, 1.2, S)
        at(4); ken("wall-fortified", x, z, 90, S, S); ken("battlement", x, z, 90, 2 * S, S)
tower(KX - 11.4, KZ + 0.8, 1.7, 2, 3); tower(KX + 11.4, KZ + 0.8, 1.7, 2, 3)
tower(KX - 16.5, KZ + 0.8, 1.35, 2, 4); tower(KX + 16.5, KZ + 0.8, 1.35, 2, 3)
tower(KX - 6.0, KZ - 6.0, 2.1, 3, 4); tower(KX + 6.0, KZ - 6.0, 2.1, 3, 4); tower(KX, KZ - 8.0, 2.5, 3, 4)
tower(KX - 22.0, KZ + 0.8, 1.5, 2, 4); tower(KX + 22.0, KZ + 0.8, 1.5, 2, 4)                  # corner towers, joined to the end towers by a short curtain
for side in (-1, 1):
    x = KX + side * 19.3; z = KZ + 0.6
    at(3); ken("wall-fortified", x, z, 0, 0, S); block(x, z, S, 1.2)
    at(4); ken("wall-fortified-window", x, z, 0, S, S); ken("battlement", x, z, 0, 2 * S, S)
tower(KX, KZ - 16.0, 3.0, 4, 4)                                                                   # the donjon behind the arch
tower(KX - 12.0, KZ - 13.0, 2.0, 3, 4); tower(KX + 12.0, KZ - 13.0, 2.0, 3, 4)
at(4); put(GEN + "SM_dw_banner", KX, KZ - 13.0, 0, 14.0, 2.2); put(GEN + "SM_dw_banner", KX - 12.0, KZ - 10.6, 0, 9.0, 1.5); put(GEN + "SM_dw_banner", KX + 12.0, KZ - 10.6, 0, 9.0, 1.5)
at(4)
for x in (KX - 11.4, KX + 11.4): put(GEN + "SM_dw_banner", x, KZ + 3.4, 0, 6.5, 1.5)
for x in (KX - 4.0, KX + 4.0): put(GEN + "SM_dw_banner", x, KZ + 2.2, 0, 8.0, 1.6)
at(1); put(GEN + "SM_dw_portal_frame", KX, KZ, 0, 0, 1.0); block(KX, KZ, 17.0, 3.0)                      # the great arch: a stone frame always, the glow once the gate is awake or the keep is crowned
for spec in ("S:eg_open", "S:hp_4,!eg_open"):
    T.P.append([GEN + "SM_dw_portal_glow", KX, KZ, 0, round(KY + 0.1, 3), 1.0, spec])
    T.P.append([GEN + "SM_dw_portal_beam", KX, KZ - 0.2, 0, round(KY + 6.0, 3), 1.0, spec])
for spec_d in ({"showIf": "eg_open"}, {"showIf": "hp_4", "hideIf": "eg_open"}):
    T.DEC.append(dict(type="glow", x=KX, z=KZ + 3.5, r=14, y=round(KY + 5.5, 2), color=[0.35, 0.62, 1.0, 0.55], **spec_d))
    T.DEC.append(dict(type="glow", x=KX, z=KZ + 8.0, r=10, y=round(KY + 2.0, 2), color=[0.45, 0.7, 1.0, 0.35], **spec_d))
at(1, 3)                                                                                           # rubble and scaffolding on the plateau flanks
for (x, z, r) in ((-12, 4, 20), (14, 3, 70), (-18, -6, 140), (19, -8, 0), (-3, -14, 50)): ken("column-damaged", KX + x, KZ + z, r, 0, S * 1.3)
for i in range(10): ken("bricks", KX + rng.uniform(-22, 22), KZ + rng.uniform(-14, 6), rng.randint(0, 359), 0, S * rng.uniform(0.6, 0.9))
at(2, 3)
for sx in (-22.0, 22.0): ken("structure-poles", KX + sx, KZ - 3.5, 0, 0, S); ken("structure", KX + sx, KZ - 3.5, 0, S, S * 0.9)
# the barracks: two stone halls on the east end of the plateau, and a watch fire on the west end
for (x, z) in ((47.0, -76.0), (47.0, -64.0)): house_at(x, z, 270, 4, floors=2, bays=2, wall="stone", roof="slate", need_flat=False)
at(1); put(ST + "SM_Stylized_Bonfire", 12.0, -78.0, 0, 0, 1.2); block(12, -78, 1.8, 1.8); T.glow(12, -78, 6, [1, 0.62, 0.3, 0.5], h=1.2)
for x in (KX - 20, KX + 20): T.lamp(x, KZ + 6, frm=4)

# ------------------------------------------------------------------ the grand ramp: stone walls and lamps up its south edge
for r_ in DH.RAMPS:
    (xa, za, _), (xb, zb, _) = r_["pts"][0], r_["pts"][-1]
    xs = np.arange(xa + 2, xb - 1, 2.8)
    at(3)
    for x in xs: put(KEN + "wall-half", float(x), za + r_["hw"] + 0.3, 0, 0, S)
    block((xa + xb) / 2, za + r_["hw"] + 0.3, abs(xb - xa), 0.8)
    for x in np.arange(xa + 6, xb - 2, 10.0):
        T.lamp(float(x), za + r_["hw"] + 0.3); T.lamp(float(x), za - r_["hw"] - 0.3)
    at(4)
    for x in np.arange(xa + 11, xb - 4, 20.0): put(GEN + "SM_dw_banner", float(x), za - r_["hw"] - 0.5, 0, 3.4, 1.2)
    claim((xa + xb) / 2, za, 30)

# ------------------------------------------------------------------ stone treads laid along every stair run (the ground under them is the carved ramp)
STEP = GEN + "SM_dw_step"
NSTEP = 0
for r_ in DH.RAMPS:
    if not r_.get("stairs"): continue
    pts = [(p[0], p[1]) for p in r_["pts"]]
    segs = [(pts[i], pts[i + 1], math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])) for i in range(len(pts) - 1)]
    total = sum(sg[2] for sg in segs); depth = 1.0 if r_["hw"] < 3 else 1.25; width = 2 * r_["hw"] + 0.5
    at(1)
    for k in range(int(total / depth)):
        t = (k + 0.5) * depth
        for (a_, b_, L_) in segs:
            if t <= L_ or (a_, b_, L_) == segs[-1]:
                u = min(t / L_, 1.0); x = a_[0] + (b_[0] - a_[0]) * u; z = a_[1] + (b_[1] - a_[1]) * u
                rot = math.degrees(math.atan2(b_[0] - a_[0], b_[1] - a_[1])); break
            t -= L_
        put(STEP, x, z, rot, 0.1, [width / 4.0, 1.0, depth], None); NSTEP += 1
    claim(sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts), total / 2 + 1.5)

# ------------------------------------------------------------------ the watchtower (east ledge, y 74) and the stables (east plateau)
WX, WZ = 67.0, -36.0
tower(WX, WZ, 1.6, 2, 4); at(4); T.glow(WX, WZ, 12, [1.0, 0.62, 0.3, 0.55], 4, None, h=11.5); put(ST + "SM_Stylized_Bonfire", WX, WZ + 3.2, 0, 0, 1.0); claim(WX, WZ, 6)
house_at(66.0, -22.0, 0, 4, floors=2, bays=2, wall="stone", roof="slate", need_flat=False)

# south bank: a row of houses facing the lake (north), and the road lamps
row([-76 + 14 * i for i in range(17)], 106.0, 180, (3, 4, 3, 4, 4), floors=1)
for x in range(-78, 148, 14): T.lamp(x + 7.0, 112.5, frm=3)

# ------------------------------------------------------------------ boats on the lake, crates and wagons on the quay
at(3)
for (bx, bz, br) in ((-12, 70, 88), (-28, 82, 80), (4, 66, 95), (42, 72, 90), (-56, 70, 70), (-20, 62, 85), (60, 80, 100), (12, 92, 90)):
    if gy(bx, bz) < LAKE_Y - 1.5: put("SM_Stylized_Boat", bx, bz, br, LAKE_Y - 0.18, 1.1, abs_y=True)
at(3)
for (m_, x, z, r, sc, bw, bd) in ((ST + "SM_Stylized_Wagon", -22, 44, 90, 1.0, 4.4, 2.0), (ST + "SM_Hay", 12, 44, 0, 1.2, 1.4, 1.4), (ST + "_Stylized_Barrel", -32, 45, 0, 1.3, 1.0, 1.0),
                                  (ST + "SM_Stylized_Box_var1", -30.5, 45.4, 30, 1.3, 1.0, 1.0), (ST + "_Stylized_Barrel", 36, 44, 0, 1.3, 1.0, 1.0)):
    put(m_, x, z, r, 0, sc); block(x, z, bw, bd)

# ---- the quay: three timber piers running out into the lake with boats alongside
DECK_TOP = 29.6; DOCK_Y = DECK_TOP - 4.62                                                          # the Stylized dock mesh is 4.62 m tall, the deck is its top
at(3)
PIERS = [(-10.0, 3), (4.0, 3), (12.5, 2)]
for (px, n) in PIERS:
    for k in range(n):
        zc = 50.6 + 3.8 + 7.6 * k
        put(ST + "SM_Dock_Straight", px, zc, 0, DOCK_Y, 1.0, abs_y=True)
        WALK.append(dict(x=px, z=zc, w=2.45, d=7.6, rot=0, y=DECK_TOP))
    put(ST + "_Stylized_Barrel", px + 1.8, 49.2, 0, 0, 1.2); put(ST + "SM_Stylized_Box_var1", px - 1.8, 49.0, 30, 0, 1.2); put(ST + "SM_Stylized_Basket", px + 1.6, 47.6, 0, 0, 1.2)
    T.lamp(px - 1.5, 56.0, frm=3) if False else None
    claim(px, 52.0, 4)
for (bx, bz, br) in ((-13.5, 60.5, 92), (-6.5, 63.0, 88), (7.2, 61.0, 90), (15.5, 57.5, 84), (0.0, 70.0, 86), (-20, 66, 94)):
    put("SM_Stylized_Boat", bx, bz, br, LAKE_Y - 0.18, 1.1, abs_y=True)
for (px, n) in PIERS[:2]:
    at(4); T.lamp(px + 1.35, 52.4, frm=4); T.lamp(px - 1.35, 52.4, frm=4)

# ------------------------------------------------------------------ farmland on the east plateau: wheat rows
at(3)
for fx in (84, 92, 100):
    for fz in range(-6, 22, 4):
        if flat_ok(fx, fz, 2.5, 0.5): put(ST + "SM_Wheat", fx + rng.uniform(-1, 1), fz, rng.randint(0, 359), 0, rng.uniform(1.6, 2.2))
claim(92, 8, 16)

# ------------------------------------------------------------------ overgrowth: grass, ivy, rubble, flowers, then trees on the unbuilt, unpaved ground
IMG0, RES = DH.paint_image()
from scipy.ndimage import gaussian_filter, map_coordinates as _mc


def repaint(img0):
    """the editor's stone floor in the basin becomes grass with a cobbled plaza, streets to every door, and roads to the quay and the bridges"""
    hP, wP = img0.shape[:2]
    Xg, Zg = np.meshgrid(DH.GX0 + (np.arange(wP) + 0.5) / RES, DH.GZ0 + (np.arange(hP) + 0.5) / RES)
    Hp = DH.gy_many(Xg, Zg)
    gz_, gx_ = np.gradient(DH.H, DH.CELL); slope = np.hypot(gx_, gz_)
    Sp = _mc(slope, [(Zg - DH.GZ0) / DH.CELL, (Xg - DH.GX0) / DH.CELL], order=1, mode="nearest")
    roadP = np.kron(DH.ROAD_MASK, np.ones((RES, RES), bool))[:hP, :wP]
    flat = (Sp < 0.45) & (Hp < 70) & (Hp > LAKE_Y + 0.8) & ~roadP
    stone_now = (img0[..., 3] >= 128) & (img0[..., :3].max(axis=2) < 128)
    nz = gaussian_filter(np.random.RandomState(5).randn(hP, wP), 16); nz /= nz.std()
    base = img0.astype(float)
    g = flat & stone_now
    base[g] = (255, 0, 0, 0)
    dm = g & (nz > 0.8)
    base[dm] = (190, 70, 0, 0)                                                                    # a little bare earth in the grass
    terrP = np.kron(DH.TERR_CHANGED, np.ones((RES, RES), bool))[:hP, :wP]
    base[terrP & (Sp > 0.9) & ~roadP] = (0, 0, 255, 0)                                           # the faces of the shelves are bare rock
    w = np.zeros((hP, wP))
    d = np.hypot(Xg - PX, Zg - PZ)
    w = np.maximum(w, np.clip((PLAZA_R * (1 + 0.05 * nz) - d) / 1.6, 0, 1))
    xy = Xg.ravel(), Zg.ravel()

    def road(p0, p1, half):
        (x0, z0), (x1, z1) = p0, p1
        h_ref = gy(x0, z0)
        i0 = max(int((min(z0, z1) - half - 3 - DH.GZ0) * RES), 0); i1 = min(int((max(z0, z1) + half + 3 - DH.GZ0) * RES), hP)
        j0 = max(int((min(x0, x1) - half - 3 - DH.GX0) * RES), 0); j1 = min(int((max(x0, x1) + half + 3 - DH.GX0) * RES), wP)
        if i1 <= i0 or j1 <= j0: return
        X, Z = Xg[i0:i1, j0:j1], Zg[i0:i1, j0:j1]
        dx, dz = x1 - x0, z1 - z0; L2 = max(dx * dx + dz * dz, 1e-6)
        t = np.clip(((X - x0) * dx + (Z - z0) * dz) / L2, 0, 1)
        dist = np.hypot(X - (x0 + t * dx), Z - (z0 + t * dz))
        wt = np.clip((half + 0.8 - dist) / 1.0, 0, 1) * (np.abs(Hp[i0:i1, j0:j1] - h_ref) < 1.4) * flat[i0:i1, j0:j1]
        w[i0:i1, j0:j1] = np.maximum(w[i0:i1, j0:j1], wt)

    for st in STREETS:
        for a, b in zip(st[:-1], st[1:]): road(a, b, 1.5)
        mid = st[len(st) // 2]
        if abs(gy(*mid) - gy(PX, PZ)) < 1.0: road(mid, (PX, PZ), 1.4)                           # a spur from the middle of a basin street to the plaza
    road((PX, PZ), (PX, 49.5), 2.2); road((PX, PZ), (-4, 30), 1.4); road((PX, PZ), (30, 28), 1.4)  # to the quay, the inn and the shop
    for px_, n_ in PIERS: road((px_, 44), (px_, 50), 1.8)
    for r_ in DH.RAMPS:
        if r_.get("stairs") and r_["hw"] < 3: road((r_["pts"][0][0], r_["pts"][0][1]), (PX, PZ), 1.4)       # from the foot of each flight to the plaza
    for bx, (za, zb) in BR_SPANS.items():
        road((bx, za - 12), (bx, za + 1), 2.2); road((bx, zb - 1), (bx, zb + 12), 2.2)
    wm = w[..., None]
    out = base * (1 - wm) + np.array([0, 0, 0, 255.0]) * wm
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


IMG = repaint(IMG0)


def paint_at(x, z):
    return IMG[min(max(int((z - DH.GZ0) * RES), 0), IMG.shape[0] - 1), min(max(int((x - DH.GX0) * RES), 0), IMG.shape[1] - 1)]


def slope_ok(x, z, lim=0.7):
    return abs(gy(x + 2, z) - gy(x - 2, z)) < lim * 4 and abs(gy(x, z + 2) - gy(x, z - 2)) < lim * 4


def grassy(x, z):
    p = paint_at(x, z)
    return p[3] < 90 and gy(x, z) > LAKE_Y + 0.8


RUIN = ("wall-fortified-half", "column-damaged", "bricks", "wall-half")
for i in range(160):                                                                               # ruins across the basin and the plateaus, heavier in phase I
    x, z = rng.uniform(-70, 60), rng.uniform(-75, 48)
    if not (flat_ok(x, z, 2, 0.6) and free(x, z, 1.5)) or gy(x, z) < 31: continue
    at(1, 2 + (i % 2)); ken(RUIN[2] if i % 2 else "column-damaged", x, z, rng.randint(0, 359), 0, S * rng.uniform(0.5, 1.0))
tries = 0
for i in range(900):
    x, z = rng.uniform(-125, 148), rng.uniform(-90, 126)
    if not (grassy(x, z) and slope_ok(x, z) and free(x, z, 1.0)): continue
    at(1, 2 + (i % 3)); put(ST + ("SM_Grass_A" if i % 2 else "SM_Grass_B"), x, z, rng.randint(0, 359), 0, rng.uniform(1.2, 2.2))
at(1)
for i in range(500):
    x, z = rng.uniform(-125, 148), rng.uniform(-90, 126)
    if not (grassy(x, z) and slope_ok(x, z) and free(x, z, 1.0)): continue
    put(ST + rng.choice(("SM_Red_Flower", "SM_Yellow_Flower", "SM_White_Flower", "SM_Pink_Flower", "SM_Blue_Flower")), x, z, rng.randint(0, 359), 0, rng.uniform(2.0, 3.4))
trees = []
for i in range(5200):
    x, z = rng.uniform(-125, 148), rng.uniform(-90, 126)
    if len(trees) >= 1100: break
    if not (grassy(x, z) and slope_ok(x, z, 0.6) and free(x, z, 2.5)): continue
    if paint_at(x, z)[0] < 120 or (x > 78 and -46 < z < 46 and rng.random() < 0.88) or math.hypot(x - PX, z - PZ) < 27 or (-24 < x < 52 and -44 < z < 49 and abs(gy(x, z) - 31.9) < 0.7): continue
    trees.append((x, z)); at(1)
    put(ST + rng.choice(("Tree_01", "Tree_02", "Tree_03", "Tree_03", "Tree_05", "Tree_06", "Tree_06", "B_Tree_01", "B_Tree_05")), x, z, rng.randint(0, 359), -0.1, rng.uniform(0.8, 1.45))
    claim(x, z, 1.2)
for i in range(260):
    x, z = rng.uniform(-125, 148), rng.uniform(-90, 126)
    if not (grassy(x, z) and slope_ok(x, z, 0.7) and free(x, z, 1.5)): continue
    at(1); put(GC + "SM_bush_0%d" % rng.randint(1, 4), x, z, rng.randint(0, 359), 0, rng.uniform(0.8, 1.3))

# ------------------------------------------------------------------ colliders from the terrain: the lake and the cliffs cannot be walked; the bridges and the ramp are open
BOUNDS = dict(minX=-128, maxX=148, minZ=-92, maxZ=126)
CELLS = 2.0
xs_ = np.arange(BOUNDS["minX"], BOUNDS["maxX"] + CELLS, CELLS); zs_ = np.arange(BOUNDS["minZ"], BOUNDS["maxZ"] + CELLS, CELLS)
GXg, GZg = np.meshgrid(xs_, zs_)
hh_ = DH.gy_many(GXg, GZg)
from scipy.ndimage import maximum_filter, map_coordinates
slp = np.hypot(*np.gradient(DH.H, DH.CELL)); slp = maximum_filter(slp, size=3)
sl_ = map_coordinates(slp, [(GZg - DH.GZ0) / DH.CELL, (GXg - DH.GX0) / DH.CELL], order=0, mode="nearest")
blocked = (hh_ < LAKE_Y - 0.4) | (sl_ > 1.35)
for bx, (za, zb) in BR_SPANS.items():                                                              # the bridges
    blocked &= ~((np.abs(GXg - bx) <= BR_HW + 0.2) & (GZg >= za - 1.0) & (GZg <= zb + 1.0))
runs = {}
for r_i, zc in enumerate(zs_):
    run = None
    for c_i, xc in enumerate(xs_):
        b = blocked[r_i, c_i]
        if b and run is None: run = [c_i, c_i]
        elif b: run[1] = c_i
        if (not b or c_i == len(xs_) - 1) and run is not None:
            runs.setdefault((run[0], run[1]), []).append(r_i); run = None
at(1)
ncol = 0
for (c0, c1), rows_ in runs.items():                                                               # merge consecutive rows with identical column runs
    rows_.sort(); start = prev = rows_[0]
    for r_i in rows_[1:] + [None]:
        if r_i is not None and r_i == prev + 1: prev = r_i; continue
        z0, z1 = zs_[start], zs_[prev]; x0, x1 = xs_[c0], xs_[c1]
        T.COL.append({"x": round((x0 + x1) / 2, 2), "z": round((z0 + z1) / 2, 2), "w": round(x1 - x0 + CELLS, 2), "d": round(z1 - z0 + CELLS, 2)}); ncol += 1
        if r_i is not None: start = prev = r_i

# ------------------------------------------------------------------ the scene: the editor's block with the new pieces, colliders, terrain and bounds
scene = {k: v for k, v in DH.LAND.items() if k not in ("pieces", "colliders", "decals", "walk", "terrain", "npcs", "events", "spawn", "bounds")}
scene.update(pieces=T.P, colliders=T.COL, decals=T.DEC, walk=WALK, npcs=[], events=[], autorun=[], objectives=[], terrain=DH.terrain_json(IMG),
             spawn={"x": 8, "z": 36}, bounds=BOUNDS, playerHeight=2.4, camera={"pitch": 24, "dist": 38},
             encounters={"rate": 0, "level": [22, 26], "pool": ["stone_gargoyle"], "zones": [{"x": 0, "z": 0, "w": 800, "d": 800, "safe": True}], "text": ""},
             lod={"match": "Tree_0", "dist": 110, "res": 256})
if __name__ == "__main__":
    out = os.path.join(sys.argv[1] if len(sys.argv) > 1 else HERE, "strange.json")
    with open(out, "w", encoding="utf-8", newline="") as f:
        json.dump(scene, f, ensure_ascii=False, separators=(",", ":"))
    print("strange.json:", len(T.P), "pieces,", NSTEP, "treads,", len(T.COL), "colliders (%d from terrain)," % ncol, len(trees), "trees,", len(FOOT), "footprints", REPORT)

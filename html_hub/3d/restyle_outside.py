"""Re-dresses the `outside` hub scene to look like the Colosseum plaza concept art: pale slab paving, a three-tier arcaded Colosseum with a stair
landing and winged-angel statue, two tiered fountains, red-roofed cream houses down both sides, striped-awning market stalls, red banners.
Run:  python restyle_outside.py [in.json] [out.json]   (default: reads outside.pre_colosseum.json -> writes outside.json; the first run copies the old outside.json to outside.pre_colosseum.json)
It PATCHES the scene: NPCs, events, quest props (crates, locket basket), the notice board and the harbour gate are kept; everything decorative is replaced.
Needs the generated pieces in Assets/3D/Colosseum/ (gen_colosseum_meshes.py)."""
import json, math, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stylhouse import Town

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "outside.json"); BAK = os.path.join(HERE, "outside.pre_colosseum.json")
CO = "/assets/3D/Colosseum/"; GC = "/assets/3D/GodCity/"; ST = "/assets/3D/Stylized/"
src = sys.argv[1] if len(sys.argv) > 1 else None; dst = sys.argv[2] if len(sys.argv) > 2 else OUT
if src is None:
    if not os.path.exists(BAK): shutil.copyfile(OUT, BAK)
    src = BAK
d = json.load(open(src))

# ------------------------------------------------------------------ layout constants (x east, z south; the camera looks north at the Colosseum)
WALL_Z = -52.0                         # nearest point of the Colosseum front
STEP_N, TREAD, RISE, LANDING, STEP_W = 8, 1.0, 0.3, 2.6, 16.0
STEP_FOOT = WALL_Z + STEP_N * TREAD + LANDING          # z of the foot of the stairs
TOP = STEP_N * RISE                                    # landing height
STATUE_Z, STATUE_S = -37.4, 0.7
FOUNT = [(-11.5, -28.5), (11.5, -28.5)]
KEEP_NEAR = [(-19, -6, 3.2), (-22, -6, 3.2), (-17, 22, 2.2), (15.4, 22.2, 2.2), (4.5, 27, 2.2)]      # quest / notice-board props stay
def near_keep(x, z): return any(math.hypot(x - a, z - b) < r for a, b, r in KEEP_NEAR)
GATE_KEEP = ("SM_arc_entrance", "SM_fire_tower_04", "SM_rock_02")                                  # the harbour gate in the south

# ------------------------------------------------------------------ strip the old decoration
old = d["pieces"]; P = []
for p in old:
    n = p[0].split("/")[-1]; x, z = p[1], p[2]
    if near_keep(x, z) and n in ("SM_Apple_crate", "SM_basket_01", "SM_construction_block_01", "SM_fabric_decoration_05"): P.append(p); continue
    if n in GATE_KEEP and z > 30: P.append(p); continue
d["pieces"] = P
keepc = []
for c in d["colliders"]:
    if abs(c["x"] + 19) < 0.5 and abs(c["z"] + 6) < 0.5: keepc.append(c)                              # notice board
    elif c["z"] > 40: keepc.append(c)                                                                  # harbour gate
d["colliders"] = keepc
d["decals"] = [c for c in d["decals"] if c.get("sq") or c["z"] > 10]                                    # lamp glows in the south + the locket glow (re-added below where lamps stay)

def put(m, x, z, rot=0, y=0, sc=1, sa=None, spec=None):
    e = [m if m.startswith("/") else CO + m, round(x, 3), round(z, 3), round(rot, 2), round(y, 3), sc if sa is None else [round(sc * a, 4) for a in sa]]
    if spec: e.append(spec)
    d["pieces"].append(e)
def block(x, z, w, dd): d["colliders"].append({"x": round(x, 3), "z": round(z, 3), "w": round(w, 3), "d": round(dd, 3)})
def glow(x, z, r, c=(1, 0.82, 0.5, 1)): d["decals"].append({"type": "glow", "x": round(x, 2), "z": round(z, 2), "r": r, "color": list(c)})

# ------------------------------------------------------------------ paving (20 m tiles, enough to cover the whole visible ground)
for gx in range(-70, 71, 20):
    for gz in range(-110, 91, 20): put("SM_paving_20x20", gx, gz, 0, 0, 1)

# ------------------------------------------------------------------ colosseum, stairs, statue, fountains
put("SM_colo_wall", 0, WALL_Z); put("SM_colo_inner", 0, WALL_Z)
put("SM_colo_steps", 0, STEP_FOOT)
put("SM_statue_angel", 0, STATUE_Z, 0, 0, STATUE_S); block(0, STATUE_Z, 3.4, 3.4)
for fx, fz in FOUNT:
    put("SM_fountain", fx, fz); put("SM_fountain_water", fx, fz); block(fx, fz, 6.6, 6.6); glow(fx, fz, 5, (0.8, 0.92, 1, 0.55))
block(-(STEP_W / 2 + 0.55), (WALL_Z + STEP_FOOT) / 2, 1.3, STEP_FOOT - WALL_Z); block(STEP_W / 2 + 0.55, (WALL_Z + STEP_FOOT) / 2, 1.3, STEP_FOOT - WALL_Z)
for sg in (-1, 1): put(GC + "SM_vase_07", sg * (STEP_W / 2 + 0.55), STEP_FOOT + 0.55 - 0.0, 0, 2.1, 1.2)       # urns on the foot pedestals
d["walk"] = [dict(x=0, z=round(STEP_FOOT - STEP_N * TREAD / 2, 2), w=STEP_W - 0.4, d=STEP_N * TREAD, rot=0, y=round(TOP + 0.15, 2), y1=0.15),
             dict(x=0, z=round(WALL_Z + LANDING / 2, 2), w=STEP_W - 0.4, d=LANDING, rot=0, y=TOP)]
d["bounds"]["minZ"] = round(WALL_Z + 0.8, 2)

# ------------------------------------------------------------------ houses down both sides (scaled Stylized kit houses: cream walls, red roofs)
HS = 1.5
def house(cx, cz, rot, floors=2, bays=2, door_bay=0, windows="many"):
    t = Town(); t.house(cx, cz, rot, floors=floors, bays=bays, wall="cream", roof="red", door_bay=door_bay, windows=windows)
    for e in t.P:
        e[1] = round(cx + (e[1] - cx) * HS, 3); e[2] = round(cz + (e[2] - cz) * HS, 3); e[4] = round(e[4] * HS, 3); e[5] = HS * (e[5] if isinstance(e[5], (int, float)) else 1)
        d["pieces"].append(e)
    for c in t.COL: block(cx + (c["x"] - cx) * HS, cz + (c["z"] - cz) * HS, c["w"] * HS, c["d"] * HS)
FRONT = 24.3
rows = []
for side in (-1, 1):
    for i, z in enumerate((-45, -32.5, -20, -7.5, 5, 17.5, 30)):
        floors = 3 if z < -25 else 2
        depth = 4 * 2 * HS
        house(side * (FRONT + depth / 2), z, 90 if side < 0 else 270, floors, 2, door_bay=i % 2)
        rows.append((side, z, floors))

# ------------------------------------------------------------------ awning stalls (free standing in the middle band, attached to houses elsewhere)
def stall(x, z, rot, goods=True):
    put("SM_stall_awning", x, z, rot); a = math.radians(rot)
    fx, fz = math.sin(a), math.cos(a)                                        # world direction of the stall's front (+z local)
    cx, cz = x + fx * 1.2, z + fz * 1.2
    block(cx, cz, 4.6 if rot % 180 == 0 else 1.3, 1.3 if rot % 180 == 0 else 4.6)
    if goods:
        for k, nm in enumerate(("_Stylized_Barrel", "SM_Stylized_Box_var1", "_Stylized_Barrel")):
            gx = x + fx * 2.2 + (math.cos(a) * (k - 1) * 1.7); gz = z + fz * 2.2 - (math.sin(a) * (k - 1) * 1.7)
            put(ST + nm, gx, gz, k * 40, 0, 1.2 if "Barrel" in nm else 1.3); block(gx, gz, 1.0, 1.0)
for (x, z, rot) in ((-21.0, -14, 90), (-21.0, 11, 90), (21.0, -14, 270), (21.0, 11, 270)):                  # attached to the house rows
    stall(x, z, rot)
for (x, z, rot) in ((15.5, 0, 270), (15.5, 8.5, 270), (-15.5, 4, 90)):                                       # the three old tent spots (Pip, Mara)
    stall(x, z, rot, goods=False)
# ------------------------------------------------------------------ banners, lamps, braziers
for sx in (-12.4, -6.2, 6.2, 12.4): put("SM_banner_tall", sx, WALL_Z + 1.05, 0, 9.0)
for (side, z, fl) in rows:
    xw = side * (FRONT - 0.15)
    put("SM_banner_tall", xw, z - 4.2, 90 if side < 0 else 270, 3.4 * fl * 0.5 + 3.2)
for z in (-40, -22, -3, 20):                                                                                # wide banners on poles
    for side in (-1, 1): put("SM_banner_wide", side * 22.4, z, 0, 8.6)
for z in (-18, -6, 8, 14, 22, 30, 38):
    for sg in (-1, 1):
        if z in (14, 22, 30, 38): continue
        put(ST + "SM_Stylized_Lamp_C", sg * 6.0, z, 0, 0, 2.4); block(sg * 6.0, z, 0.6, 0.6); glow(sg * 6.0, z, 3.4, (1, 0.8, 0.45, 0.6))
for pz in (14, 22, 30, 38):                                                                                  # the existing lamp spots in the south become the same lamps
    for sg in (-1, 1):
        put(ST + "SM_Stylized_Lamp_C", sg * 5.6, pz, 0, 0, 2.4); block(sg * 5.6, pz, 0.6, 0.6)
        if not any(abs(c.get("x", 99) - sg * 5.6) < 0.1 and abs(c.get("z", 99) - pz) < 0.1 for c in d["decals"]): glow(sg * 5.6, pz, 3, (1, 0.85, 0.5, 1))
for sg in (-1, 1): put(GC + "SM_Brasero_02", sg * 9.5, STEP_FOOT + 1.4, 0, 0, 0.09); glow(sg * 9.5, STEP_FOOT + 1.4, 3.5)

# ------------------------------------------------------------------ entities
for n in d["npcs"]:
    if n["id"] == "guard": n["x"], n["z"] = -11.0, STEP_FOOT + 1.6
for e in d["events"]:
    if e["id"] == "enter_colosseum": e["x"], e["z"], e["w"], e["d"] = 0, round(WALL_Z + 1.4, 2), 12, 2.4
d["spawn"] = {"x": 0, "z": -9.5}
d["camera"] = {"pitch": 19, "dist": 33}
# ------------------------------------------------------------------ sky and light: golden hour
d["sky"] = {"type": "layers", "base": {"type": "gradient", "stops": [[0, "#35539c"], [0.36, "#7b94d0"], [0.62, "#eab3a6"], [0.82, "#ffcb9d"], [1, "#ffe6bd"]]},
            "layers": [{"url": "/assets/Backgrounds/layers/clouds_wisps.webp", "y": 0.2, "height": 0.22, "drift": 0.007, "alpha": 0.85, "tint": [1, 0.8, 0.78]},
                       {"url": "/assets/Backgrounds/layers/clouds_puffy.webp", "y": 0.36, "height": 0.3, "drift": 0.004, "alpha": 0.95, "tint": [1, 0.84, 0.8], "parallax": 0.2}]}
d["light"] = {"dir": [-0.5, -0.55, -0.55], "color": [1.0, 0.86, 0.68], "ambient": [0.60, 0.58, 0.68]}
d["fog"] = {"color": [0.93, 0.76, 0.70], "near": 95, "far": 280}
d["name"] = d.get("name", "Outside the Colosseum")
json.dump(d, open(dst, "w"), separators=(",", ":"))
print("pieces", len(d["pieces"]), "colliders", len(d["colliders"]), "decals", len(d["decals"]), "->", dst)

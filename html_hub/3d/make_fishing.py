"""Builds the two fishing scenes of the fishing mini-game:  fish_pier.json (the harbour pier, sea fish) and fish_pond.json (the
whispering pool, fresh-water fish), plus their ground meshes (Assets/3D/Fishing/SM_fish_beach.glb, SM_fish_bank.glb, SM_pond_water.glb).

Both are small stage-like scenes: a shore you walk around on (tackle seller, fish-log board, the way home), and a wooden pier that runs out
over the water.  Standing at the end of the pier and pressing E starts the fishing mechanic (html_hub/3d/fishing.js); everything about what
bites lives in data/fishing_db.py.  x = east, z = south, the water is to the NORTH (-z) so the default camera looks over it.

Run:  python make_fishing.py [json_outdir] [asset_outdir]      (needs numpy + Pillow; glbkit.py next to it; scenes/island.json for the sea sky)"""
import json, math, os, random, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from glbkit import write_glb, encode, normals, fnoise

OUT = sys.argv[1] if len(sys.argv) > 1 else HERE
ASSET = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "Assets", "3D", "Fishing")
os.makedirs(ASSET, exist_ok=True)
ST, PA, FI = "/assets/3D/Stylized/", "/assets/3D/Paradise/", "/assets/3D/Fishing/"
DOCK_LEN, DOCK_W, DECK_Y, DECK_TOP = 7.58, 2.46, -4.35, 0.27           # SM_Dock_Straight: 7.58 long (z), 2.46 wide, posts 4.6 m tall -> deck 0.27 above the ground


def smooth(a, b, x): t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)


def noise_field(w, h, scale, seed, octs=4):
    """Non-tiling fractal noise in 0..1 at w x h (built from tileable FFT noise, upsampled)."""
    acc = np.zeros((h, w)); amp = 1.0; tot = 0.0
    for o in range(octs):
        n = 256; base = fnoise(n, 1.4, seed + o * 17)
        sz = max(8, int(scale / (2 ** o)))
        im = Image.fromarray((base * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        # tile the 256 map `w/sz` times by sampling at a scaled coordinate
        xs = (np.arange(w) % sz) * (n / sz); ys = (np.arange(h) % sz) * (n / sz)
        a = base[(ys.astype(int) % n)[:, None], (xs.astype(int) % n)[None, :]]
        acc += a * amp; tot += amp; amp *= 0.5
    return acc / tot


def build_ground(name, hfun, x0, x1, z0, z1, cell, tex_fn, tex_w, tex_h):
    xs = np.arange(x0, x1 + 1e-6, cell); zs = np.arange(z0, z1 + 1e-6, cell)
    X, Z = np.meshgrid(xs, zs); H = np.vectorize(hfun)(X, Z)
    pos = np.stack([X, H, Z], -1).reshape(-1, 3).astype(np.float32)
    nx, nz = len(xs), len(zs); idx = []
    for j in range(nz - 1):
        for i in range(nx - 1):
            a = j * nx + i; b = a + 1; c = a + nx; d = c + 1
            idx += [a, c, b, b, c, d]
    idx = np.array(idx, np.uint32).reshape(-1, 3)
    uv = np.stack([(X - x0) / (x1 - x0), (Z - z0) / (z1 - z0)], -1).reshape(-1, 2).astype(np.float32)
    nrm = normals(pos, idx)
    if nrm[:, 1].mean() < 0: idx = idx[:, ::-1].copy(); nrm = normals(pos, idx)             # keep faces up
    img = tex_fn(x0, x1, z0, z1, tex_w, tex_h)
    b, mime = encode(img, 'JPEG', 84)
    write_glb(os.path.join(ASSET, name + ".glb"), pos, nrm, idx, name, uv=uv, img=b, mime=mime, color=(1, 1, 1, 1), repeat=False)
    print(name, "%d verts, %d tris, %.0f kB texture" % (len(pos), len(idx), len(b) / 1024))


# ============================================================================================================ the harbour pier (sea)
SHORE_Z = -1.5
def h_beach(x, z):
    if z >= SHORE_Z: return 0.0 + 0.0
    return -min(3.2, (SHORE_Z - z) * 0.30)

def tex_beach(x0, x1, z0, z1, w, h):
    zz = np.linspace(z0, z1, h)[:, None] * np.ones((1, w)); xx = np.linspace(x0, x1, w)[None, :] * np.ones((h, 1))
    n1 = noise_field(w, h, 220, 3); n2 = noise_field(w, h, 40, 9, 3); n3 = noise_field(w, h, 9, 21, 2)
    sand = np.array([0.70, 0.61, 0.43]); wet = np.array([0.45, 0.39, 0.28]); grass = np.array([0.26, 0.40, 0.17]); dry = np.array([0.60, 0.53, 0.36]); deep = np.array([0.33, 0.45, 0.50])
    t_grass = smooth(14, 26, zz + (n1 - 0.5) * 14); t_wet = smooth(2.5, -0.5, zz + (n2 - 0.5) * 1.6); t_deep = smooth(-1.2, -9, zz)
    col = sand * (1 - t_grass[..., None]) + grass * t_grass[..., None]
    col = col * (1 - 0.35 * smooth(0.45, 0.8, n1)[..., None]) + dry * (0.35 * smooth(0.45, 0.8, n1)[..., None])
    col = col * (1 - t_wet[..., None]) + wet * t_wet[..., None]
    col = col * (1 - t_deep[..., None]) + deep * t_deep[..., None]
    col *= (0.88 + 0.24 * n3)[..., None] * (0.94 + 0.12 * n2)[..., None]
    return np.clip(col, 0, 1)


# ============================================================================================================ the whispering pool (fresh)
PC, PH, PR = (0.0, -27.25), (34.0, 25.75), 12.0                     # basin centre, half extents, corner radius
def sd_basin(x, z):
    qx = abs(x - PC[0]) - (PH[0] - PR); qz = abs(z - PC[1]) - (PH[1] - PR)
    return math.hypot(max(qx, 0), max(qz, 0)) + min(max(qx, qz), 0) - PR

_bn = None
def bank_noise(x, z):
    global _bn
    if _bn is None: _bn = fnoise(256, 1.6, 77)
    i = int(((x + 100) / 200) * 255 * 3) % 256; j = int(((z + 100) / 200) * 255 * 3) % 256
    return _bn[j, i]

POND_Y = -0.4
def h_bank(x, z):
    if z >= SHORE_Z: return 0.0
    d = sd_basin(x, z)
    if d < 0: return -min(2.4, -d * 0.28)
    k = float(smooth(SHORE_Z, SHORE_Z - 7, z))
    return k * (min(7.5, d * 0.27) + (bank_noise(x, z) - 0.5) * 1.6 * float(smooth(2, 14, d)))

def tex_bank(x0, x1, z0, z1, w, h):
    zz = np.linspace(z0, z1, h)[:, None] * np.ones((1, w)); xx = np.linspace(x0, x1, w)[None, :] * np.ones((h, 1))
    hh = np.vectorize(h_bank)(xx[::4, ::4], zz[::4, ::4]); hh = np.array(Image.fromarray(hh.astype(np.float32)).resize((w, h), Image.BILINEAR))
    n1 = noise_field(w, h, 200, 5); n2 = noise_field(w, h, 36, 13, 3); n3 = noise_field(w, h, 8, 31, 2)
    mud = np.array([0.30, 0.26, 0.16]); silt = np.array([0.20, 0.24, 0.20]); grass = np.array([0.20, 0.46, 0.15]); dark = np.array([0.13, 0.33, 0.11]); path = np.array([0.50, 0.42, 0.27])
    t_mud = smooth(0.35, -0.1, hh + (n2 - 0.5) * 0.4); t_silt = smooth(-0.6, -1.6, hh)
    col = grass * (1 - smooth(0.4, 0.7, n1)[..., None]) + dark * smooth(0.4, 0.7, n1)[..., None]
    col = col * (1 - t_mud[..., None]) + mud * t_mud[..., None]
    col = col * (1 - t_silt[..., None]) + silt * t_silt[..., None]
    tp = np.exp(-((xx / 3.0) ** 2)) * smooth(3, 8, zz) * smooth(60, 40, zz)                 # the trodden path down to the dock
    col = col * (1 - 0.7 * tp[..., None]) + path * (0.7 * tp[..., None])
    col *= (0.88 + 0.24 * n3)[..., None]
    return np.clip(col, 0, 1)

def build_pond_water():
    hw, hd = 50.0, 38.0; cx, cz = PC
    pos = np.array([[cx - hw, POND_Y, cz - hd], [cx + hw, POND_Y, cz - hd], [cx + hw, POND_Y, cz + hd], [cx - hw, POND_Y, cz + hd]], np.float32)
    idx = np.array([0, 2, 1, 0, 3, 2], np.uint32).reshape(-1, 3); nrm = np.tile([0, 1, 0], (4, 1)).astype(np.float32)
    uv = np.array([[0, 0], [hw * 2 / 16, 0], [hw * 2 / 16, hd * 2 / 16], [0, hd * 2 / 16]], np.float32)
    n = noise_field(512, 512, 120, 41, 4); base = np.array([0.12, 0.33, 0.31]); hi = np.array([0.26, 0.5, 0.45])
    img = base * (1 - n[..., None]) + hi * n[..., None]
    b, mime = encode(np.clip(img, 0, 1), 'JPEG', 86)
    write_glb(os.path.join(ASSET, "SM_pond_water.glb"), pos, nrm, idx, "SM_pond_water", uv=uv, img=b, mime=mime, color=(1, 1, 1, 1), double=True)


# ============================================================================================================ scene assembly
class Scene:
    def __init__(self, hf): self.P, self.C, self.D, self.hf = [], [], [], hf
    def put(self, m, x, z, rot=0, y=None, sc=1.0):
        if not m.startswith("/"): m = ST + m
        self.P.append([m, round(x, 3), round(z, 3), round(rot, 2), round(self.hf(x, z) if y is None else y, 3), sc])
    def block(self, x, z, w, d): self.C.append(dict(x=round(x, 3), z=round(z, 3), w=round(w, 3), d=round(d, 3)))
    def glow(self, x, z, r, c): self.D.append(dict(type="glow", x=x, z=z, r=r, color=c))
    def barrel(self, x, z, rot=0): self.put("_Stylized_Barrel", x, z, rot, sc=1.3); self.block(x, z, 1.0, 1.0)
    def box(self, x, z, rot=0, v=2): self.put("SM_Stylized_Box_var%d" % v, x, z, rot, sc=1.3); self.block(x, z, 1.0, 1.0)
    def lamp(self, x, z): self.put("SM_Stylized_Lamp_C", x, z, 0, sc=2.2); self.block(x, z, 0.5, 0.5); self.glow(x, z, 2.6, [1, 0.8, 0.45, 0.4])


def say(who, text): return dict(type="say", who=who, text=text)


def pier(sc, n_docks, walk):
    """n_docks wooden dock sections running north from the shore; returns the z of the far end."""
    for k in range(n_docks):
        zc = -DOCK_LEN / 2 - k * DOCK_LEN
        sc.put("SM_Dock_Straight", 0, zc, 0, DECK_Y, 1.0)
    end = -n_docks * DOCK_LEN
    walk.append(dict(x=0, z=round(end / 2, 2), w=DOCK_W, d=round(n_docks * DOCK_LEN, 2), rot=0, y=DECK_TOP))
    walk.append(dict(x=0, z=0.6, w=DOCK_W, d=1.2, rot=0, y=DECK_TOP, y1=0.0))                  # a ramp from the sand onto the planks
    return end


def water_blockers(sc, x_edge, z_north, z_south):
    """Keep the player on the shore and the pier: boxes over the water either side, and a cap past the pier's end."""
    for sgn in (-1, 1):
        w = x_edge - (DOCK_W / 2 + 0.22)
        sc.block(sgn * (DOCK_W / 2 + 0.22 + w / 2), (z_north + z_south) / 2, w, abs(z_south - z_north))
    sc.block(0, z_north - 0.1, 8, 1.2)


def finish(name, title, sc, walk, spawn, bounds, extras, stand, cfg_extra, extra_events, npcs, intro):
    d = dict(story=True, name=title, kit="", tile=4, pieces=sc.P, colliders=sc.C, npcs=npcs, events=extra_events, decals=sc.D, walk=walk,
             spawn=spawn, bounds=bounds, playerHeight=2.3, fishing=dict(stand=stand, **cfg_extra))
    d.update(extras)
    with open(os.path.join(OUT, name + ".json"), "w") as f: json.dump(d, f, separators=(",", ":"))
    print(name, "%d pieces, %d colliders" % (len(sc.P), len(sc.C)))


def seller_actions(who, line): return [say(who, line), dict(type="fishing", op="shop")]


def make_pier():
    rnd = random.Random(11)
    sc = Scene(h_beach); walk = []
    build_ground("SM_fish_beach", h_beach, -70, 70, -24, 70, 2.0, tex_beach, 1792, 1216)
    sc.put(PA + "SM_ocean", 0, 0, 0, 0, 1); sc.put(FI + "SM_fish_beach", 0, 0, 0, 0, 1)
    end = pier(sc, 4, walk); stand_z = round(end + 1.9, 2)
    water_blockers(sc, 30, end - 0.3, SHORE_Z - 0.2)
    sc.block(0, end - 0.9, 8, 1.2) if False else None
    # --- the shore: the tackle stall, the log board, a campfire, boats pulled up on the sand
    sc.put("SM_Stylized_Table_A", 6.0, 3.6, 8, sc=1.0); sc.block(6.0, 3.6, 3.0, 1.6); sc.put("SM_Stylized_Basket", 5.3, 3.5, 0, 0.93, 1.6); sc.put("SM_Stylized_Basket", 7.0, 3.7, 40, 0.93, 1.4)
    sc.barrel(9.2, 2.6, 20); sc.barrel(10.1, 3.4, 60); sc.box(9.4, 4.6, 35, 1); sc.box(10.6, 2.2, 10, 2)
    sc.put("SM_Stylized_WantedBoard", -5.6, 4.2, 12, sc=1.3); sc.block(-5.6, 4.2, 3.0, 0.9)
    sc.put("SM_Stylized_Bonfire", -9.5, 11.0, 0, sc=1.4); sc.block(-9.5, 11.0, 1.8, 1.8); sc.glow(-9.5, 11.0, 5.5, [1, 0.62, 0.25, 0.7])
    for a in (0.3, 1.9, 3.6, 5.0): sc.put("SM_Stylized_Bench" if False else "SM_Hay", -9.5 + 3.3 * math.cos(a), 11.0 + 3.3 * math.sin(a), math.degrees(a), sc=1.6)
    for x, z, r in ((-18.0, 5.0, 75), (17.0, 7.0, -35), (-4.0, 15.5, 100)):
        sc.put("SM_Stylized_Boat", x, z, r, 0.0, 1.15); sc.block(x, z, 2.0, 4.4) if abs(r) < 60 else sc.block(x, z, 4.4, 2.0)
    for sgn in (-1, 1): sc.lamp(sgn * 2.4, 1.9)
    sc.lamp(2.0, end + 0.8) if False else None
    sc.put("SM_Stylized_Flag_Var1", 3.0, 0.4, 0, 0.0, 1.8)
    # --- scenery: rocks along the tide line, palms and plants behind the beach, a few islets out at sea
    for _ in range(14):
        x = rnd.choice([-1, 1]) * rnd.uniform(12, 33); z = rnd.uniform(-1.2, 1.0)
        sc.put(PA + rnd.choice(["SM_rock_01", "SM_rock_02"]), x, z, rnd.uniform(0, 360), 0 if z > SHORE_Z else None, rnd.uniform(0.7, 1.4))
    placed = []
    for _ in range(400):
        x = rnd.uniform(-66, 66); z = rnd.uniform(-8, 66)
        if abs(x) < 34 and z < 56: continue                            # keep the beach and the way back clear; palms stand on the flanks and far behind
        if any(math.hypot(x - a, z - b) < 6.5 for a, b in placed): continue
        placed.append((x, z)); sc.put(PA + "SM_tree_05", x, z, rnd.uniform(0, 360), None, rnd.uniform(0.42, 0.62))
    for _ in range(46):
        x = rnd.uniform(-60, 60); z = rnd.uniform(14, 30)
        if abs(x) < 9 and z > 20: continue
        k = rnd.choice(["SM_Plant_01", "SM_Plant_02", "SM_grass_01", "SM_grass_02"])
        sc.put(PA + k, x, z, rnd.uniform(0, 360), sc=rnd.uniform(0.8, 1.4) if "Plant" in k else rnd.uniform(2.0, 3.4))
    for x, z, s in ((-58, -62, 4.5), (47, -74, 6.0), (-30, -95, 5.0), (70, -50, 3.5)): sc.put(PA + "SM_rock_01", x, z, rnd.uniform(0, 360), -1.2, s)
    for x, z in ((-23, -40), (31, -33), (-44, -22)): sc.put(ST + "SM_Stylized_Boat", x, z, rnd.uniform(0, 360), -0.95, 1.1)
    island = json.load(open(os.path.join(HERE, "island.json"))) if os.path.exists(os.path.join(HERE, "island.json")) else {}
    npcs = [dict(id="seller", name="Old Brine", title="Tackle & Bait", sprite="Rook", x=6.0, z=5.4, h=2.3, tint=[1.05, 0.95, 0.8, 1], reach=4.6,
                 actions=seller_actions("Old Brine", "Rods, bait, and honest advice: the far water is where the big ones sleep, and a longer rod gets you there. Take a look."))]
    events = [
        dict(id="spot", name="Pier end", x=0, z=round(end + 3.2, 2), w=2.4, d=6.0, trigger="talk", prompt="Start fishing", actions=[dict(type="fishing", op="start")]),
        dict(id="log", name="Fish log", x=-5.6, z=6.0, w=4.4, d=3.0, trigger="talk", prompt="Read the fish log", actions=[dict(type="fishing", op="log")]),
        dict(id="home", name="Back to the village", x=0, z=22.6, w=16, d=2.6, trigger="touch", prompt="Head back",
             actions=[dict(type="choice", who="", text="Head back to the village?", options=[dict(label="Head back", actions=[dict(type="warp", scene="@return")]), dict(label="Stay a while", actions=[dict(type="end")])])]),
    ]
    extras = {k: island[k] for k in ("sky", "light", "fog", "music") if k in island}
    extras.update(fx=[dict(type="dust", amount=0.08)], camera=dict(pitch=36, dist=25), uiRange=dict(tag=12, mark=18))
    finish("fish_pier", "Harbour Pier", sc, walk, dict(x=0, z=19.5), dict(minX=-27, maxX=27, minZ=-31.6, maxZ=25.2), extras, dict(x=0, z=stand_z),
           dict(spot="pier", waterY=-0.9, maxAim=0.72, title="Harbour Pier", look=7, pitch=24, dist=19), events, npcs,
           "A quiet pier at the edge of the harbour. Old Brine sells tackle by the stall; walk to the end of the pier and press E to start fishing. Hold SPACE to charge a cast, strike when the float dives, then reel - but ease off when the line glows red.")


def make_pond():
    rnd = random.Random(23)
    sc = Scene(h_bank); walk = []
    build_ground("SM_fish_bank", h_bank, -100, 100, -96, 72, 3.0, tex_bank, 2048, 1700)
    build_pond_water()
    sc.put(FI + "SM_fish_bank", 0, 0, 0, 0, 1); sc.put(FI + "SM_pond_water", PC[0], PC[1], 0, 0, 1)
    end = pier(sc, 3, walk); stand_z = round(end + 1.9, 2)
    water_blockers(sc, 30, end - 0.3, SHORE_Z - 0.2)
    sc.put("SM_Stylized_Table_A", -6.0, 3.8, -10, sc=1.0); sc.block(-6.0, 3.8, 3.0, 1.6); sc.put("SM_Stylized_Basket", -6.7, 3.7, 0, 0.93, 1.6)
    sc.barrel(-9.6, 3.0, 30); sc.box(-9.8, 4.4, 25, 1); sc.box(-3.6, 5.8, 40, 2)
    sc.put("SM_Stylized_WantedBoard", 6.2, 4.6, -10, sc=1.3); sc.block(6.2, 4.6, 3.0, 0.9)
    for sgn in (-1, 1): sc.lamp(sgn * 2.4, 1.9)
    sc.put("SM_Hay", 10.5, 8.0, 20, sc=1.8); sc.put("SM_Hay", 11.6, 9.0, 80, sc=1.5)
    # reeds and rocks around the water's edge, trees up the banks
    for _ in range(150):
        x = rnd.uniform(-34, 34); z = rnd.uniform(-52, -2); d = sd_basin(x, z)
        if not (-1.6 < d < -0.2) or abs(x) < 3.2 and z > end - 4: continue
        k = rnd.choice(["SM_Plant_01", "SM_Plant_02", "SM_grass_01", "SM_grass_02"])
        sc.put(PA + k, x, z, rnd.uniform(0, 360), POND_Y - 0.1, rnd.uniform(0.9, 1.6) if "Plant" in k else rnd.uniform(2.0, 3.2))
    for _ in range(18):
        x = rnd.uniform(-32, 32); z = rnd.uniform(-52, -3); d = sd_basin(x, z)
        if not (-1.2 < d < 1.5) or abs(x) < 4: continue
        sc.put(PA + rnd.choice(["SM_rock_01", "SM_rock_02"]), x, z, rnd.uniform(0, 360), None, rnd.uniform(0.6, 1.3))
    placed = []
    for _ in range(420):
        x = rnd.uniform(-98, 98); z = rnd.uniform(-92, 70)
        if z > -2 and abs(x) < 36 and z < 40: continue
        d = sd_basin(x, z) if z < SHORE_Z else 99
        if z < SHORE_Z and d < 3.5: continue
        if any(math.hypot(x - a, z - b) < 5.2 for a, b in placed): continue
        placed.append((x, z)); m = rnd.choice(["Tree_03", "Tree_02", "Tree_04", PA + "SM_tree_05"])
        s = rnd.uniform(0.38, 0.58) if m.endswith("tree_05") else (rnd.uniform(1.3, 1.9) if m == "Tree_04" else rnd.uniform(1.0, 1.5))
        sc.put(m, x, z, rnd.uniform(0, 360), None, s)
    for _ in range(40):
        x = rnd.uniform(-34, 34); z = rnd.uniform(10, 34)
        if abs(x) < 9 and z < 26: continue
        k = rnd.choice(["SM_Plant_01", "SM_grass_01", "SM_grass_02"])
        sc.put(PA + k, x, z, rnd.uniform(0, 360), None, rnd.uniform(0.8, 1.3) if k == "SM_Plant_01" else rnd.uniform(2.0, 3.0))
    forest = json.load(open(os.path.join(HERE, "forest.json"))) if os.path.exists(os.path.join(HERE, "forest.json")) else {}
    npcs = [dict(id="seller", name="Mossy Hen", title="Tackle & Bait", sprite="Yulia", x=-6.0, z=5.6, h=2.3, tint=[0.85, 1.1, 0.85, 1], reach=4.6,
                 actions=seller_actions("Mossy Hen", "Hush, you'll scare them. The pool's deep in the middle and the old ones live out there. Bait and rods, if you want them."))]
    events = [
        dict(id="spot", name="Dock end", x=0, z=round(end + 3.2, 2), w=2.4, d=6.0, trigger="talk", prompt="Start fishing", actions=[dict(type="fishing", op="start")]),
        dict(id="log", name="Fish log", x=6.2, z=6.2, w=4.4, d=3.0, trigger="talk", prompt="Read the fish log", actions=[dict(type="fishing", op="log")]),
        dict(id="home", name="Back to the camp", x=0, z=22.6, w=16, d=2.6, trigger="touch", prompt="Head back",
             actions=[dict(type="choice", who="", text="Head back to the ranger camp?", options=[dict(label="Head back", actions=[dict(type="warp", scene="@return")]), dict(label="Stay a while", actions=[dict(type="end")])])]),
    ]
    extras = dict(sky=dict(type="gradient", stops=[[0, "#3f7f96"], [0.45, "#8fc7c0"], [1, "#e8f2d0"]]),
                  light=dict(dir=[-0.35, -1, -0.3], color=[1, 0.97, 0.84], ambient=[0.52, 0.58, 0.55]),
                  fog=dict(color=[0.62, 0.78, 0.72], near=55, far=170),
                  music=forest.get("music") or dict(url="/assets/Music/mp3/07. Spirits Forest (loop).mp3"),
                  fx=[dict(type="fireflies", amount=0.15), dict(type="leaves", amount=0.2)], camera=dict(pitch=36, dist=25), uiRange=dict(tag=12, mark=18))
    finish("fish_pond", "Whispering Pool", sc, walk, dict(x=0, z=19.5), dict(minX=-27, maxX=27, minZ=-31.6 - 0, maxZ=25.2), extras, dict(x=0, z=stand_z),
           dict(spot="pond", waterY=POND_Y, maxAim=0.72, title="Whispering Pool", look=8, pitch=16, dist=21), events, npcs,
           "A still green pool deep in the Whispering Wood. Mossy Hen keeps the tackle by the path; walk to the end of the dock and press E to start fishing. Hold SPACE to charge a cast, strike when the float dives, then reel - but ease off when the line glows red.")


if __name__ == "__main__":
    make_pier(); make_pond()

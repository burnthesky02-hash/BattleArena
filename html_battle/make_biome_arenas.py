"""Builds three location battle arenas for html_battle/maps/:
    paradise_shore  (Paradise Island)   forest_glade  (Whispering Wood)   cave_hall  (Hollow Cave)
Each is <id>.json (props, light, fog, sky, fx, `scenes`) + <id>_ground.glb (procedural ground).
`scenes` lists the hub scene ids whose fights should use that arena automatically (see battle3d.js loadMapList).
Run from html_battle/:   python make_biome_arenas.py        (needs numpy + Pillow; glbkit.py lives in ../html_hub/3d)
Combat field is x -10..10, z -4..10 (camera on the +z side looking toward -z); everything else is backdrop."""
import json, math, os, random, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "html_hub", "3d"))
import glbkit

OUT = os.path.join(HERE, "maps")
A3 = "/assets/3D/"
ST, PA, CV, KN = A3 + "Stylized/", A3 + "Paradise/", A3 + "CaveCamp/", A3 + "kenney_retro-fantasy-kit/Models/GLB format/"


class Arena:
    def __init__(self, id_, name, seed):
        self.id, self.name = id_, name
        self.rng = random.Random(seed)
        self.props = []

    def put(self, model, x, z, y=0.0, rot=None, scale=1.0, jit=0.0):
        r = self.rng
        if rot is None: rot = r.choice((0, 60, 120, 180, 240, 300)) + r.uniform(-12, 12)
        if jit: scale *= r.uniform(1 - jit, 1 + jit)
        self.props.append({"model": model + ".glb", "pos": [round(x, 2), round(y, 2), round(z, 2)], "rotY": round(rot, 1),
                           "scale": round(scale, 3) if not isinstance(scale, (list, tuple)) else scale})

    def ring(self, models, n, rx, rz, cx=0.0, cz=3.0, a0=0, a1=360, scale=1.0, jit=0.15, rj=1.5, y=0.0, skip=None):
        """n props along an ellipse (angle 0 = +x, 90 = +z toward the camera)."""
        for i in range(n):
            a = math.radians(a0 + (a1 - a0) * (i + 0.5) / n + self.rng.uniform(-3, 3))
            x = cx + (rx + self.rng.uniform(-rj, rj)) * math.cos(a); z = cz + (rz + self.rng.uniform(-rj, rj)) * math.sin(a)
            if skip and skip(x, z): continue
            self.put(self.rng.choice(models), x, z, y=y, scale=scale, jit=jit)

    def scatter(self, models, n, xr, zr, avoid=None, scale=1.0, jit=0.2, y=0.0):
        k = 0
        while k < n:
            x = self.rng.uniform(*xr); z = self.rng.uniform(*zr)
            if avoid and avoid(x, z): continue
            self.put(self.rng.choice(models), x, z, y=y, scale=scale, jit=jit); k += 1

    def write(self, ground_glb, **cfg):
        data = {"name": self.name, "model": ground_glb, "scale": 1, "offset": [0, 0, 0], "rotY": 0, "props": self.props,
                "cullNearCamera": 8}
        data.update(cfg)
        os.makedirs(OUT, exist_ok=True)
        json.dump(data, open(os.path.join(OUT, self.id + ".json"), "w"), indent=1)
        print(f"{self.id}: {len(self.props)} props")


def ground(path, name, x0, x1, z0, z1, h, color, tex, uvs=6.0, step=1.0):
    """Flat-ish ground grid. h(x,z) -> y, color(x,z) -> (r,g,b) vertex tint, tex = float RGB array (tiles)."""
    xs = np.arange(x0, x1 + 1e-6, step); zs = np.arange(z0, z1 + 1e-6, step)
    X, Z = np.meshgrid(xs, zs)
    Y = np.vectorize(h)(X, Z)
    pos = np.stack([X, Y, Z], -1).reshape(-1, 3).astype(np.float32)
    col = np.array([[*color(x, z), 1.0] for x, z in zip(X.ravel(), Z.ravel())], np.float32)
    uv = np.stack([X / uvs, Z / uvs], -1).reshape(-1, 2).astype(np.float32)
    nz, nx = X.shape
    idx = []
    for j in range(nz - 1):
        for i in range(nx - 1):
            a = j * nx + i; b = a + 1; c = a + nx; d = c + 1
            idx += [a, c, b, b, c, d]
    idx = np.array(idx, np.uint32)
    nrm = glbkit.normals(pos, idx)
    # make sure normals point up (winding sanity)
    nrm[nrm[:, 1] < 0] *= -1
    img, mime = glbkit.encode(tex, 'JPEG', 88)
    glbkit.write_glb(os.path.join(OUT, path), pos, nrm, idx, name, uv=uv, img=img, mime=mime, col=col, double=True)


def tex_noise(base, var, seed, n=256, beta=1.6, tint2=None, k2=0.35):
    """Seamless noisy texture around `base` colour (floats 0-1), optional second tint blended by a second noise."""
    a = glbkit.fnoise(n, beta, seed)[..., None]; b = glbkit.fnoise(n, 2.6, seed + 7)[..., None]
    t = np.array(base)[None, None, :] * (1 + (a - 0.5) * var * 2) + (b - 0.5) * var * 0.6
    if tint2 is not None:
        m = np.clip((glbkit.fnoise(n, 2.0, seed + 13)[..., None] - 0.5) * 3.2 + 0.5, 0, 1) * k2
        t = t * (1 - m) + np.array(tint2)[None, None, :] * m
    return np.clip(t, 0, 1)


def smooth(a, b, x):
    t = min(1, max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t)


def in_field(x, z, pad=0.0):
    """The combat field plus a margin: nothing tall gets placed here."""
    return -12 - pad <= x <= 12 + pad and -5 - pad <= z <= 11 + pad


# ------------------------------------------------------------------------------------------------ Paradise shore
def paradise_shore():
    A = Arena("paradise_shore", "Paradise Shore", 101)
    shore = lambda x: -9.5 + 1.6 * math.sin(x * 0.35) + 0.9 * math.sin(x * 0.11 + 1)       # waterline z(x)

    def h(x, z):
        d = shore(x) - z                                    # > 0 : in the water
        return -0.9 * smooth(-0.5, 2.2, d) + 0.02 * math.sin(x * 0.7) * math.cos(z * 0.6)

    def color(x, z):
        d = z - shore(x)
        wet = 1 - smooth(0.0, 4.5, d)                       # darker, wetter sand near the waterline
        grass = smooth(14, 22, z) * 0.7 + smooth(15, 22, abs(x)) * 0.6
        sand = np.array([0.88, 0.8, 0.66]) * (1 - 0.28 * wet)
        g = np.array([0.62, 0.78, 0.45])
        c = sand * (1 - min(1, grass)) + g * min(1, grass)
        return tuple(np.clip(c, 0, 1))
    ground("paradise_shore_ground.glb", "ShoreGround", -34, 34, -16, 30, h, color,
           tex_noise((0.93, 0.84, 0.64), 0.07, 5, tint2=(0.82, 0.72, 0.54), k2=0.5), uvs=7.0)
    # sea (the island scene's own ocean mesh, lowered so the beach slope disappears under it)
    A.put(PA + "SM_ocean", 0, -40, y=0.62, rot=0, scale=1)
    # headland cliffs on both flanks and behind the beach
    for x, z, r in ((-19.5, -2, 90), (-21, 6, 95), (-19, 14, 85), (19.5, -1, 270), (21, 7, 265), (19, 15, 275)):
        A.put(ST + "SM_Cliff_02", x, z, rot=r, scale=1.5)
    A.put(ST + "SM_Cliff_03", -17.5, -11.5, rot=60, scale=1.7); A.put(ST + "SM_Cliff_01", 17.5, -11.5, rot=-60, scale=1.7)
    # trees on the bluffs
    for x, z in ((-23, -4), (-25, 6), (-22, 16), (-27, 1), (23.5, -3), (25, 8), (22, 17), (27, 0), (-14, -15), (14, -16)):
        A.put(ST + A.rng.choice(("Tree_04", "Tree_06", "Tree_02")), x, z, scale=A.rng.uniform(0.9, 1.25))
    # dock, boat and driftwood at the water's edge (back left)
    A.put(ST + "SM_Dock_Straight", -9, -12.5, y=-2.6, rot=0, scale=1.3)
    A.put(ST + "SM_Stylized_Boat", -4.5, -9.2, y=-0.15, rot=70, scale=2.0)
    A.put(ST + "SM_TrunkTree", 6.5, -6.2, rot=20, scale=2.0); A.put(ST + "SM_TrunkTree", 12.5, 12.6, rot=140, scale=1.6)
    # rocks, tufts, flowers: kept clear of the combat lanes
    A.scatter([PA + "SM_rock_01", PA + "SM_rock_02"], 7, (-22, 22), (-8.5, 22), avoid=lambda x, z: in_field(x, z, 1.5) or z < shore(x) + 1.5, scale=0.65, jit=0.3)
    A.scatter([ST + "SM_Grass_A", ST + "SM_Grass_B"], 26, (-22, 22), (11, 24), avoid=lambda x, z: in_field(x, z, -1.5) and z < 10.5, scale=1.7, jit=0.3)
    A.scatter([ST + "SM_Yellow_Flower", ST + "SM_White_Flower", ST + "SM_Pink_Flower"], 18, (-22, 22), (12, 24), scale=2.4, jit=0.3)
    A.put(ST + "SM_Stylized_Bonfire", 13.2, 12.2, scale=1.4); A.put(ST + "SM_Stylized_Chest", -12.5, 12.8, rot=200, scale=1.3)
    A.write("paradise_shore_ground.glb",
            light={"dir": [-0.4, -1, -0.3], "color": [1, 0.96, 0.86], "ambient": [0.5, 0.53, 0.6]},
            fog={"color": [0.72, 0.88, 0.97], "near": 60, "far": 150},
            sky={"type": "layers",
                 "base": {"type": "gradient", "stops": [[0, "#2f7fd8"], [0.4, "#6fb4ee"], [0.75, "#bfe3f7"], [1, "#fff4d6"]]},
                 "layers": [{"url": "/assets/Backgrounds/layers/clouds_wisps.webp", "y": 0.18, "height": 0.22, "drift": 0.007, "alpha": 0.9},
                            {"url": "/assets/Backgrounds/layers/clouds_puffy.webp", "y": 0.34, "height": 0.32, "drift": 0.004, "parallax": 0.2},
                            {"url": "/assets/Backgrounds/layers/ridges_far.webp", "y": 0.9, "height": 0.22, "parallax": 0.15, "tint": [0.7, 0.85, 0.95]}]},
            fx=[{"type": "dust", "amount": 0.08}],
            scenes=["island"])


# ------------------------------------------------------------------------------------------------ Whispering Wood glade
def forest_glade():
    A = Arena("forest_glade", "Whispering Wood Glade", 202)
    cl = lambda x, z: math.hypot(x / 15.0, (z - 3) / 13.0)          # < 1 inside the clearing

    def h(x, z): return 0.025 * math.sin(x * 0.5) * math.sin(z * 0.45)

    def color(x, z):
        r = cl(x, z)
        dirt = (1 - smooth(0.2, 0.75, r)) * 0.55 * (0.6 + 0.4 * math.sin(x * 0.9) * math.cos(z * 0.8))
        moss = smooth(0.7, 1.15, r) * 0.55
        g = np.array([0.55, 0.72, 0.40]); d = np.array([0.78, 0.66, 0.46]); m = np.array([0.34, 0.5, 0.32])
        c = g * (1 - dirt) + d * dirt; c = c * (1 - moss) + m * moss
        return tuple(np.clip(c, 0, 1))
    ground("forest_glade_ground.glb", "GladeGround", -36, 36, -22, 30, h, color,
           tex_noise((0.52, 0.66, 0.34), 0.12, 21, tint2=(0.36, 0.5, 0.26), k2=0.6), uvs=6.0)
    big = [ST + "Tree_03", ST + "Tree_06", ST + "Tree_02"]
    small = [KN + "tree-large", KN + "tree-shrub"]
    # tall trees ringing the clearing (back and flanks); the camera side stays open so the view never gets blocked
    A.ring(big, 16, 23.0, 20.0, a0=150, a1=390, scale=1.05, jit=0.18, rj=1.6, skip=lambda x, z: z > 12)
    A.ring(small, 22, 27.0, 24.0, a0=140, a1=400, scale=3.4, jit=0.3, rj=2.5, skip=lambda x, z: z > 12)
    A.ring(small, 12, 16.5, 14.0, a0=165, a1=375, scale=2.0, jit=0.3, rj=1.0, skip=lambda x, z: in_field(x, z, 0.5) or z > 11)
    # undergrowth, rocks and a few fallen logs round the edge
    A.scatter([PA + "SM_Plant_01", PA + "SM_Plant_02", PA + "SM_Plant_03"], 22, (-20, 20), (-12, 20), avoid=lambda x, z: cl(x, z) < 0.92 or z > 13, scale=1.25, jit=0.3)
    A.scatter([ST + "SM_Grass_A", ST + "SM_Grass_B"], 40, (-18, 18), (-10, 18), avoid=lambda x, z: in_field(x, z, -1.0) and z < 10.5, scale=2.2, jit=0.35)
    A.scatter([PA + "SM_rock_01", PA + "SM_rock_02"], 6, (-17, 17), (-10, 14), avoid=lambda x, z: cl(x, z) < 0.95, scale=0.7, jit=0.3)
    for x, z, r in ((-8.5, -7.8, 15), (9.5, -7.2, 160), (-14.5, 8.0, 80), (15.0, 5.5, 100)):
        A.put(ST + "SM_TrunkTree", x, z, rot=r, scale=2.6)
    A.scatter([ST + "SM_Yellow_Flower", ST + "SM_White_Flower", ST + "SM_Blue_Flower"], 20, (-15, 15), (-8, 16), avoid=lambda x, z: in_field(x, z, -0.5) and z < 10, scale=2.4, jit=0.3)
    A.write("forest_glade_ground.glb",
            light={"dir": [-0.35, -1, -0.3], "color": [0.98, 1.0, 0.82], "ambient": [0.5, 0.58, 0.52]},
            fog={"color": [0.16, 0.26, 0.21], "near": 36, "far": 100},
            sky={"type": "gradient", "stops": [[0, "#1d3d44"], [0.5, "#3d6a5a"], [1, "#9fc29a"]]},
            fx=[{"type": "fireflies", "amount": 0.55}, {"type": "leaves", "amount": 0.3}],
            scenes=["forest"])


# ------------------------------------------------------------------------------------------------ Hollow Cave hall
def cave_hall():
    A = Arena("cave_hall", "Hollow Cave Hall", 303)

    def h(x, z): return 0.04 * math.sin(x * 0.8 + z * 0.3) * math.cos(z * 0.7)

    def color(x, z):
        r = math.hypot(x / 14.0, (z - 3) / 12.0)
        lit = 1.0 - 0.45 * smooth(0.6, 1.4, r)
        return (0.78 * lit + 0.12, 0.82 * lit + 0.12, 0.92 * lit + 0.14)
    ground("cave_hall_ground.glb", "CaveGround", -30, 30, -20, 28, h, color,
           tex_noise((0.38, 0.37, 0.40), 0.16, 33, tint2=(0.24, 0.24, 0.30), k2=0.55), uvs=5.0)
    rng = A.rng
    # walls: the big textured cave rocks (CaveCamp SM_rock_04 / 05, ~18 m wide and tall) in a ring round the field
    RING = [[-29, -5, 345], [-24, -12, 315], [-19, -17, 300], [-8, -20, 270], [7.334, -20, 270], [18.335, -17.001, 240], [26, -11, 225], [30.335, -7.001, 195], [32.335, 2.001, 180], [31.335, 7.999, 165], [27, 16.999, 135], [21, 22, 120], [11.333, 24.999, 90], [-4, 25, 90], [-15, 22, 60], [-20, 20, 60], [-27, 12, 15], [-29, 3, 0]]
    for i, (x, z, rot) in enumerate(RING):
        A.put(CV + ("SM_rock_04" if i % 2 == 0 else "SM_rock_05"), x, z, rot=rot, scale=1.0)
    # stalagmites and boulders hugging the walls
    spikes = [CV + f"SM_stalactic_0{i}" for i in (1, 2, 3, 4, 6)]
    A.scatter(spikes, 14, (-17, 17), (-11, 17), avoid=lambda x, z: -13.5 < x < 13.5 and -9.5 < z < 14, scale=0.7, jit=0.35)
    A.scatter([CV + "SM_rock_01", CV + "SM_rock_02", CV + "SM_rock_03"], 12, (-14, 14), (-10, 16), avoid=lambda x, z: in_field(x, z, 0.5), scale=1.4, jit=0.3)
    # glowing crystals
    for i, (x, z) in enumerate(((-13, -9), (-9.5, -10.5), (12.5, -9.5), (14.0, 2.0), (-14.5, 6.0), (-13, 13), (13.5, 13.5), (10, -10.8))):
        A.put(CV + rng.choice(("SM_cv_crystal_blue", "SM_cv_crystal_violet", "SM_cv_crystal_blue", "SM_cv_crystal_green")), x, z, scale=rng.uniform(1.4, 2.1))
    # braziers (dungeon kit + flame) lighting the field
    for x, z in ((-13.2, 0.5), (13.2, 5.5), (-6.5, -10.2), (6.5, -10.2)):
        A.put(A3 + "Dungeon/SM_dg_brazier", x, z, rot=0, scale=1.0); A.put(CV + "SM_cv_flame_gold", x, z, y=1.55, rot=0, scale=1.0)
    # a pool at the back and a bit of camp clutter
    for x in (-3.2, 0.8, 4.8):
        A.put(CV + "SM_cv_water", x, -9.0, y=0.03, rot=0, scale=1.0)
    A.put(CV + "SM_crate_group_02", -12.0, 11.8, rot=200, scale=1.0); A.put(CV + "SM_barrel_02", -10.4, 12.9, scale=1.0)
    A.put(CV + "SM_barrel_03", 12.2, 12.4, scale=1.0); A.put(CV + "SM_crate_group_01", 13.5, 11.0, rot=30, scale=1.0)
    A.write("cave_hall_ground.glb",
            light={"dir": [-0.35, -1, -0.25], "color": [0.78, 0.86, 1.0], "ambient": [0.58, 0.62, 0.78]},
            fog={"color": [0.05, 0.075, 0.13], "near": 38, "far": 105},
            sky={"type": "gradient", "stops": [[0, "#05070d"], [1, "#0d1420"]]},
            fx=[{"type": "dust", "amount": 0.25}],
            scenes=["dungeon"])


if __name__ == "__main__":
    paradise_shore(); forest_glade(); cave_hall()

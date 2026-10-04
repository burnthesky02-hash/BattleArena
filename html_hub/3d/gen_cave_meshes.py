"""Procedural cave kit for the Hollow Cave dungeon -> Assets/3D/CaveCamp/ (SM_cv_*.glb): rough rock wall blocks, translucent water,
coloured flames / gems / crystal clusters for the puzzles.  The rock and ground colours are sampled from the Cave_Camp kit's own textures
(UassetConverter/Cave_Camp: T_rock_01_D, T_ground_02_D) and turned into seamless noise textures, so the walls and floors sit next to the
real Cave_Camp meshes (see convert_cavecamp.py) without visible tiling seams.   Needs numpy + Pillow (and the kit's uassets for the colour ramps;
the ramps are cached in Assets/3D/CaveCamp/ramps.json so the script also runs without them).
Run:  python gen_cave_meshes.py [outdir]     (then make_cave.py)"""
import json, os, sys, io
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from glbkit import write_glb, encode, normals, fnoise
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'Assets', '3D', 'CaveCamp'); os.makedirs(OUT, exist_ok=True)
TS = 1024

# ------------------------------------------------------------------ colour ramps from the real textures
def ramp_from(im, n=8):
    a = np.asarray(im.convert('RGB').resize((256, 256)), np.float64) / 255; lum = a @ np.array([.3, .59, .11]); o = np.argsort(lum.ravel()); c = a.reshape(-1, 3)[o]
    return [c[int(len(c) * (i + 0.5) / n)].tolist() for i in range(n)]
RAMPS = os.path.join(OUT, 'ramps.json')
if os.path.exists(RAMPS): R = json.load(open(RAMPS))
else:
    sys.path.insert(0, os.path.join(HERE, '..', '..', 'UassetConverter'))
    import convert_cavecamp as C, convert_paradise as P
    R = {k: ramp_from(P.texim(n)) for k, n in (('rock1', 'T_rock_01_D'), ('rock2', 'T_rock_02_D'), ('rock3', 'T_rock_03_D'), ('ground', 'T_ground_02_D'), ('stal', 'T_stalactic_D'))}
    json.dump(R, open(RAMPS, 'w'))
def lut(v, ramp, gain=1.0):
    ramp = np.asarray(ramp); x = np.clip(v, 0, 1) * (len(ramp) - 1); i = np.clip(x.astype(int), 0, len(ramp) - 2); f = (x - i)[..., None]
    return (ramp[i] * (1 - f) + ramp[i + 1] * f) * gain
def equalize(v):                     # rank-equalise so the whole ramp is used
    o = np.argsort(v.ravel()); r = np.empty(v.size); r[o] = np.linspace(0, 1, v.size); return r.reshape(v.shape)

def floor_tex(seed=3):
    a = fnoise(TS, 1.6, seed); b = fnoise(TS, 2.4, seed + 1); c = fnoise(TS, 0.9, seed + 2)
    v = equalize(0.55 * a + 0.3 * b + 0.15 * c)
    im = lut(v, R['ground'], 0.62)
    pebbles = np.clip((fnoise(TS, 0.6, seed + 7) - 0.8) * 8, 0, 1)[..., None]; im = im * (1 - pebbles * .35)                 # dark grit
    im *= (0.92 + 0.16 * fnoise(TS, 0.5, seed + 9))[..., None]
    return np.clip(im, 0, 1)
def wall_tex(seed, key):
    a = fnoise(TS, 1.5, seed); b = fnoise(TS, 2.2, seed + 1); y = np.linspace(0, 1, TS)[:, None]
    strata = 0.5 + 0.5 * np.sin((y * 11 + 2.2 * (a - .5)) * 2 * np.pi)                                                    # horizontal rock layers (tileable: whole periods)
    v = equalize(0.45 * a + 0.3 * b + 0.25 * strata)
    im = lut(v, R[key], 0.85)
    ridge = 1 - np.abs(fnoise(TS, 1.3, seed + 4) - 0.5) * 2; crack = np.clip((ridge - 0.9) * 10, 0, 1)[..., None]; im = im * (1 - crack * .6)   # cracks
    moss = np.clip((fnoise(TS, 1.4, seed + 5) - 0.7) * 5, 0, 1)[..., None]; im = im * (1 - moss * .5) + moss * np.array([.1, .17, .07]) * .6
    return np.clip(im, 0, 1)
def water_tex():
    a = fnoise(256, 1.8, 4); b = fnoise(256, 2.6, 6); v = 0.55 + 0.5 * a + 0.2 * b
    return np.clip(np.stack([0.06 * v, 0.28 * v, 0.40 * v], -1), 0, 1)
def save_jpg(name, arr):
    p = os.path.join(OUT, 'tex'); os.makedirs(p, exist_ok=True); Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).save(os.path.join(p, name + '.jpg'), quality=88)
FLOOR_IMG = encode(floor_tex())[0]
WALL_IMGS = [encode(wall_tex(11, 'rock1'))[0], encode(wall_tex(23, 'rock2'))[0], encode(wall_tex(37, 'rock3'))[0]]
open(os.path.join(OUT, 'tex_floor.jpg'), 'wb').write(FLOOR_IMG)      # make_cave.py embeds this in the floor chunks

# ------------------------------------------------------------------ rough rock wall block
def smooth(t): return t * t * (3 - 2 * t)
def sample2(img, u, v):              # bilinear lookup in a 0..1 noise image, wrapping
    n = img.shape[0]; x = (u % 1) * n; y = (v % 1) * n; x0 = x.astype(int) % n; y0 = y.astype(int) % n; fx = x - np.floor(x); fy = y - np.floor(y); x1 = (x0 + 1) % n; y1 = (y0 + 1) % n
    return img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x1] * fx * (1 - fy) + img[y1, x0] * (1 - fx) * fy + img[y1, x1] * fx * fy
def rock_block(w=4.0, h=6.0, seed=1, sub=8, amp=0.55, tile=6.0):
    """w x w footprint, h tall, no bottom face. Every face is a sub x sub grid displaced by noise (zero at the face edges so neighbours meet)."""
    N = fnoise(128, 1.4, seed); hw = w / 2; P = []; NR = []; U = []; I = []
    def face(origin, du, dv, nrm, ulen, vlen, taper_v=True):
        g = np.linspace(0, 1, sub + 1); uu, vv = np.meshgrid(g, g); pts = origin[None, None, :] + uu[..., None] * du[None, None, :] + vv[..., None] * dv[None, None, :]
        edge = np.minimum.reduce([uu, 1 - uu, vv, 1 - vv]); k = smooth(np.clip(edge * 4, 0, 1))
        wx = (pts[..., 0] * .11 + pts[..., 1] * .07 + pts[..., 2] * .13 + seed * .31); wz = (pts[..., 2] * .09 + pts[..., 1] * .12 - pts[..., 0] * .05 + seed * .17)
        d = (sample2(N, wx, wz) - 0.5) * 2 * amp * k
        pts = pts + d[..., None] * np.asarray(nrm)[None, None, :]
        o = len(P); P.extend(pts.reshape(-1, 3).tolist()); NR.extend([nrm] * len(uu.ravel()))
        U.extend(np.stack([(uu * ulen + seed * 1.7) / tile, (vv * vlen) / tile], -1).reshape(-1, 2).tolist())
        for i in range(sub):
            for j in range(sub):
                a = o + j * (sub + 1) + i; I.extend([(a, a + 1, a + sub + 2), (a, a + sub + 2, a + sub + 1)])
    A = lambda *v: np.array(v, np.float64)
    face(A(-hw, 0, hw), A(w, 0, 0), A(0, h, 0), (0, 0, 1), w, h)              # +z
    face(A(hw, 0, -hw), A(-w, 0, 0), A(0, h, 0), (0, 0, -1), w, h)            # -z
    face(A(hw, 0, hw), A(0, 0, -w), A(0, h, 0), (1, 0, 0), w, h)              # +x
    face(A(-hw, 0, -hw), A(0, 0, w), A(0, h, 0), (-1, 0, 0), w, h)            # -x
    face(A(-hw, h, hw), A(w, 0, 0), A(0, 0, -w), (0, 1, 0), w, w)             # top
    P = np.array(P, np.float32); I = np.array(I, np.uint32)
    P[:, 1] += (P[:, 1] > h - 0.01) * 0                                          # keep the rim crisp
    nrm = normals(P, I); uv = np.array(U, np.float32)
    # flip winding if the normals came out inverted for the +z face (they are built consistently, but verify with the declared normals)
    chk = np.sum(nrm * np.array(NR, np.float32), 1).mean()
    if chk < 0: I = I[:, ::-1].copy(); nrm = normals(P, I)
    return P, nrm, uv, I
for k in range(3):
    P, Nn, UV, I = rock_block(4.0, 6.0, seed=3 + k * 5)
    write_glb(os.path.join(OUT, 'SM_cv_wall_%s.glb' % 'abc'[k]), P, Nn, I, 'SM_cv_wall_' + 'abc'[k], uv=UV, img=WALL_IMGS[k], color=(1, 1, 1, 1))
# a lower, rounder rock rim used for the second row of walls (taller, rougher)
P, Nn, UV, I = rock_block(4.0, 9.0, seed=61, amp=0.8, sub=8)
write_glb(os.path.join(OUT, 'SM_cv_wall_tall.glb'), P, Nn, I, 'SM_cv_wall_tall', uv=UV, img=WALL_IMGS[0], color=(.85, .85, .9, 1))

# ------------------------------------------------------------------ water tile (4 x 4 m), translucent
hw = 2.0; wi = encode(water_tex())[0]
write_glb(os.path.join(OUT, 'SM_cv_water.glb'), np.array([[-hw, .1, -hw], [hw, .1, -hw], [hw, .1, hw], [-hw, .1, hw]], np.float32), np.tile([0, 1, 0], (4, 1)).astype(np.float32),
          [(0, 3, 1), (1, 3, 2)], 'SM_cv_water', uv=np.array([[0, 0], [2, 0], [2, 2], [0, 2]], np.float32), img=wi, color=(1, 1, 1, 0.74), alpha='BLEND', double=True)

# ------------------------------------------------------------------ coloured flames, gems and crystal clusters (puzzle pieces)
COLS = {'red': (1.0, .32, .12), 'blue': (.25, .55, 1.0), 'white': (.92, .95, 1.0), 'gold': (1.0, .78, .2), 'green': (.3, 1.0, .5), 'violet': (.7, .4, 1.0)}
def octa(h=1.0, r=.45):
    p = np.array([(0, h, 0), (r, 0, 0), (0, 0, r), (-r, 0, 0), (0, 0, -r)], np.float32); i = np.array([(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1)], np.uint32); return p, i
for nm, c in COLS.items():
    p, i = octa(1.0, .45)
    write_glb(os.path.join(OUT, 'SM_cv_flame_%s.glb' % nm), p, normals(p, i), i, 'SM_cv_flame_' + nm, color=(*c, 1), emissive=c, unlit=True, double=True)
    p = np.array([(0, .8, 0), (.32, .4, 0), (0, .4, .32), (-.32, .4, 0), (0, .4, -.32), (0, 0, 0)], np.float32)
    i = np.array([(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1), (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4)], np.uint32)               # a cut gem (double pyramid)
    write_glb(os.path.join(OUT, 'SM_cv_gem_%s.glb' % nm), p, normals(p, i), i, 'SM_cv_gem_' + nm, color=(*c, 1), emissive=c, unlit=True, double=True)
def crystal(color, emissive, name, unlit=False):
    cp = []; ci = []
    for ox, oz, s, lean in ((0, 0, 1.0, 0), (.5, .2, .65, .2), (-.45, .25, .75, -.2), (.1, -.5, .55, .1)):
        o = len(cp); h = 1.8 * s; w = .28 * s
        cp += [(ox + lean * h, h, oz), (ox + w, 0, oz), (ox, 0, oz + w), (ox - w, 0, oz), (ox, 0, oz - w)]; ci += [(o, o + 1, o + 2), (o, o + 2, o + 3), (o, o + 3, o + 4), (o, o + 4, o + 1)]
    cp = np.array(cp, np.float32); ci = np.array(ci, np.uint32)
    write_glb(os.path.join(OUT, name + '.glb'), cp, normals(cp, ci), ci, name, color=(*color, 1), emissive=emissive, unlit=unlit, double=True)
crystal((.32, .32, .36), None, 'SM_cv_crystal_off')
for nm, c in COLS.items(): crystal(c, tuple(v * .8 for v in c), 'SM_cv_crystal_' + nm)
print('ok', sorted(os.listdir(OUT)))

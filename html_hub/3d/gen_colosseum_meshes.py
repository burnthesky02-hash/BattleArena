"""Procedural pieces for the 'Outside the Colosseum' plaza -> Assets/3D/Colosseum/  (numpy + Pillow; run: python gen_colosseum_meshes.py [outdir])
 SM_colo_wall / SM_colo_inner  : curved three-tier arcaded colosseum front (stone + warm lit arches / dark attic windows). Origin: the wall's nearest point at z = 0, facing +z, base y = 0.
 SM_colo_steps                 : wide marble stairs + landing, origin at the foot centre, climbs toward -z
 SM_statue_angel               : winged angel on a pedestal      SM_fountain / SM_fountain_water : tiered marble fountain + its water
 SM_stall_awning               : red-and-white striped awning stall      SM_banner_tall / SM_banner_wide : red banners with a gold emblem
 SM_paving_20x20               : pale slab paving tile (replaces SM_ground_20x20)"""
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glbkit import write_glb, encode
from cmesh import Mesh, box, lathe, smooth, stone_tex, marble_tex, paving_tex
OUT = sys.argv[1] if len(sys.argv) > 1 else '.'
os.makedirs(OUT, exist_ok=True)
STONE_M = 6.0                                                    # metres per stone texture repeat

def save(name, m, tex=None, mime='image/jpeg', **kw):
    P, N, I, UV = m.arrays()
    img = None
    if tex is not None: img, mime = encode(tex, 'JPEG' if mime == 'image/jpeg' else 'PNG', 88)
    write_glb(os.path.join(OUT, name + '.glb'), P, N, I, name, uv=UV, img=img, mime=mime, **kw)
    print(name, len(I) // 3, 'tris', np.round(P.min(0), 1), np.round(P.max(0), 1))

# ---------------------------------------------------------------- colosseum front
def colosseum(R=70.0, wb=6.2, spans=11, tiers=((10.5, 4.3, 0.80), (9.2, 4.0, 0.74), (9.0, 3.8, 0.70)), attic=7.6, pw_c=0.55):
    """spans: bays each side of the central one.  tiers: (height, arch width, opening/height) per tier"""
    dth = 2 * math.atan(wb / (2 * R)); zc = -R; stone, inner = Mesh(), Mesh()
    def T(th, u, y, d):                           # bay-local (tangent u, y, depth d inward) -> world
        r = R - d; return (r * math.sin(th) + u * math.cos(th), y, zc + r * math.cos(th) - u * math.sin(th))
    def Nrm(th, nu, ny, nd):                      # bay-local direction -> world
        return (nu * math.cos(th) + nd * math.sin(th) * -1, ny, -nu * math.sin(th) - nd * math.cos(th))
    for k in range(-spans, spans + 1):
        th = k * dth; U0 = k * wb
        def uvS(u, y, d, face):                   # stone uv, continuous along the wall
            if face == 'f': return ((U0 + u) / STONE_M, y / STONE_M)
            if face == 's': return (d / STONE_M + 0.31, y / STONE_M)
            return ((U0 + u) / STONE_M, d / STONE_M + 0.57)
        def Q(mesh, pts, hint, face='f'):         # pts are (u,y,d)
            w = [T(th, *p) for p in pts]; n = Nrm(th, *hint)
            mesh.quad(*w, n, *[uvS(p[0], p[1], p[2], face) for p in pts])
        hw = wb / 2; y0 = 0.0; centre = (k == 0)
        for ti, (H, aw, oh) in enumerate(tiers):
            if centre and ti == 0: aw, oh = 5.6, 0.86
            ah = aw / 2; opening = oh * H; hj = opening - ah; ys = y0 + hj; tw = 3.2; cor = 0.95
            Q(stone, [(-hw, y0, 0), (-ah, y0, 0), (-ah, y0 + H, 0), (-hw, y0 + H, 0)], (0, 0, -1))          # piers
            Q(stone, [(ah, y0, 0), (hw, y0, 0), (hw, y0 + H, 0), (ah, y0 + H, 0)], (0, 0, -1))
            n = 14; xs = [-ah + 2 * ah * i / n for i in range(n + 1)]
            for i in range(n):                                                                                  # spandrel above the arch
                ya0 = ys + math.sqrt(max(0, ah * ah - xs[i] ** 2)); ya1 = ys + math.sqrt(max(0, ah * ah - xs[i + 1] ** 2))
                Q(stone, [(xs[i], ya0, 0), (xs[i + 1], ya1, 0), (xs[i + 1], y0 + H, 0), (xs[i], y0 + H, 0)], (0, 0, -1))
            Q(stone, [(-ah, y0, 0), (-ah, ys, 0), (-ah, ys, tw), (-ah, y0, tw)], (1, 0, 0), 's')               # jambs
            Q(stone, [(ah, y0, 0), (ah, ys, 0), (ah, ys, tw), (ah, y0, tw)], (-1, 0, 0), 's')
            for i in range(n):                                                                                  # soffit
                a0, a1 = math.pi * i / n, math.pi * (i + 1) / n; p0 = (ah * math.cos(a0), ys + ah * math.sin(a0)); p1 = (ah * math.cos(a1), ys + ah * math.sin(a1))
                am = (a0 + a1) / 2; Q(stone, [(p0[0], p0[1], 0), (p1[0], p1[1], 0), (p1[0], p1[1], tw), (p0[0], p0[1], tw)], (-math.cos(am), -math.sin(am), 0), 's')
            Q(stone, [(-ah, y0 + 0.02, 0), (ah, y0 + 0.02, 0), (ah, y0 + 0.02, tw), (-ah, y0 + 0.02, tw)], (0, 1, 0), 't')                    # floor of the opening
            # lit interior panel
            for i in range(n):
                a0, a1 = math.pi * i / n, math.pi * (i + 1) / n; p0 = (ah * math.cos(a0), ys + ah * math.sin(a0)); p1 = (ah * math.cos(a1), ys + ah * math.sin(a1))
                inner.tri(T(th, 0, ys, tw), T(th, p0[0], p0[1], tw), T(th, p1[0], p1[1], tw), Nrm(th, 0, 0, -1), (0.5, 0.1 + 0.5 * (ys - y0) / H), (0.5 + p0[0] / aw, 0.1 + 0.8 * (p0[1] - y0) / (opening + 0.01)), (0.5 + p1[0] / aw, 0.1 + 0.8 * (p1[1] - y0) / (opening + 0.01)))
            inner.quad(T(th, -ah, y0, tw), T(th, ah, y0, tw), T(th, ah, ys, tw), T(th, -ah, ys, tw), Nrm(th, 0, 0, -1), (0, 0.1), (1, 0.1), (1, 0.1 + 0.8 * hj / opening), (0, 0.1 + 0.8 * hj / opening))
            # engaged half column at the +hw joint (and -hw for the first bay), base + capital
            for ux in ([hw] + ([-hw] if k == -spans else [])):
                rc = pw_c; segs = 8; cy0, cy1 = y0 + 0.45, y0 + H - cor - 0.05
                for s in range(segs):
                    a0, a1 = -math.pi / 2 + math.pi * s / segs, -math.pi / 2 + math.pi * (s + 1) / segs
                    pa = [(ux + rc * math.sin(a), 0, -rc * math.cos(a)) for a in (a0, a1)]
                    am = (a0 + a1) / 2; nl = (math.sin(am), 0, -math.cos(am))
                    Q(stone, [(pa[0][0], cy0, pa[0][2]), (pa[1][0], cy0, pa[1][2]), (pa[1][0], cy1, pa[1][2]), (pa[0][0], cy1, pa[0][2])], nl, 'f')
                for (yb, hh, ww, dd) in ((y0 + 0.225, 0.45, 1.5 * rc * 2, 0.70), (cy1 + 0.05, 0.35, 1.45 * rc * 2, 0.64)):
                    for (a, b_, c_, d_, nh) in (((-ww / 2, yb - hh / 2, -dd), (ww / 2, yb - hh / 2, -dd), (ww / 2, yb + hh / 2, -dd), (-ww / 2, yb + hh / 2, -dd), (0, 0, -1)),):
                        Q(stone, [(ux + a[0], a[1], a[2]), (ux + b_[0], b_[1], b_[2]), (ux + c_[0], c_[1], c_[2]), (ux + d_[0], d_[1], d_[2])], nh)
                    Q(stone, [(ux - ww / 2, yb + hh / 2, -dd), (ux + ww / 2, yb + hh / 2, -dd), (ux + ww / 2, yb + hh / 2, 0), (ux - ww / 2, yb + hh / 2, 0)], (0, 1, 0), 't')
                    Q(stone, [(ux - ww / 2, yb - hh / 2, -dd), (ux - ww / 2, yb + hh / 2, -dd), (ux - ww / 2, yb + hh / 2, 0), (ux - ww / 2, yb - hh / 2, 0)], (-1, 0, 0), 's')
                    Q(stone, [(ux + ww / 2, yb - hh / 2, -dd), (ux + ww / 2, yb + hh / 2, -dd), (ux + ww / 2, yb + hh / 2, 0), (ux + ww / 2, yb - hh / 2, 0)], (1, 0, 0), 's')
            # cornice band at the top of the tier
            yt = y0 + H; pr = 0.65
            Q(stone, [(-hw, yt - cor, -pr), (hw, yt - cor, -pr), (hw, yt, -pr), (-hw, yt, -pr)], (0, 0, -1))
            Q(stone, [(-hw, yt, -pr), (hw, yt, -pr), (hw, yt, 0), (-hw, yt, 0)], (0, 1, 0), 't')
            Q(stone, [(-hw, yt - cor, 0), (hw, yt - cor, 0), (hw, yt - cor, -pr), (-hw, yt - cor, -pr)], (0, -1, 0), 't')
            y0 += H
        # attic: plain wall with pilasters and small dark windows
        H = attic; pr = 0.3
        Q(stone, [(-hw, y0, 0), (hw, y0, 0), (hw, y0 + H, 0), (-hw, y0 + H, 0)], (0, 0, -1))
        for ux in ([hw] + ([-hw] if k == -spans else [])):
            for (a, b_) in ((-0.35, 0.35),):
                Q(stone, [(ux + a, y0, -pr), (ux + b_, y0, -pr), (ux + b_, y0 + H - 1.0, -pr), (ux + a, y0 + H - 1.0, -pr)], (0, 0, -1))
                Q(stone, [(ux + a, y0, 0), (ux + a, y0, -pr), (ux + a, y0 + H - 1.0, -pr), (ux + a, y0 + H - 1.0, 0)], (-1, 0, 0), 's')
                Q(stone, [(ux + b_, y0, 0), (ux + b_, y0, -pr), (ux + b_, y0 + H - 1.0, -pr), (ux + b_, y0 + H - 1.0, 0)], (1, 0, 0), 's')
        wy0, wy1, ww = y0 + 2.1, y0 + 4.5, 0.55
        inner.quad(T(th, -ww, wy0, 0), T(th, ww, wy0, 0), T(th, ww, wy1, 0), T(th, -ww, wy1, 0), Nrm(th, 0, 0, -1), (0.05, 0.9), (0.95, 0.9), (0.95, 0.98), (0.05, 0.98))
        yt = y0 + H; pr = 1.1; cor = 1.5                                                                            # crowning cornice
        Q(stone, [(-hw, yt - cor, -pr), (hw, yt - cor, -pr), (hw, yt, -pr), (-hw, yt, -pr)], (0, 0, -1))
        Q(stone, [(-hw, yt, -pr), (hw, yt, -pr), (hw, yt, 0.4), (-hw, yt, 0.4)], (0, 1, 0), 't')
        Q(stone, [(-hw, yt - cor, 0), (hw, yt - cor, 0), (hw, yt - cor, -pr), (-hw, yt - cor, -pr)], (0, -1, 0), 't')
        Q(stone, [(-hw, yt, 0.4), (hw, yt, 0.4), (hw, yt + 0.6, 0.4), (-hw, yt + 0.6, 0.4)], (0, 0, -1))
        Q(stone, [(-hw, yt + 0.6, 0.4), (hw, yt + 0.6, 0.4), (hw, yt + 0.6, 2.4), (-hw, yt + 0.6, 2.4)], (0, 1, 0), 't')
        if k == -spans or k == spans:
            sg = -1 if k == -spans else 1
            Q(stone, [(sg * hw, 0, 0), (sg * hw, 0, 3.2), (sg * hw, yt + 0.6, 3.2), (sg * hw, yt + 0.6, 0)], (sg, 0, 0), 's')
    save('SM_colo_wall', stone, stone_tex(1, 1024, STONE_M))
    # inner atlas: v 0..0.1 dark base, 0.1..0.9 warm lit arch interior (bright at the bottom edge fading up), 0.9..1 attic window (dark blue-grey)
    H_, W_ = 256, 64; a = np.zeros((H_, W_, 3)); y = np.linspace(0, 1, H_)[:, None]
    warm = np.array([1.0, 0.72, 0.38]) * (0.9 - 0.45 * np.clip((y - 0.1) / 0.8, 0, 1)) ; a[:] = warm[:, None, :].repeat(W_, 1) if False else 0
    for i in range(H_):
        t = y[i, 0]
        if t < 0.1: a[i] = [0.20, 0.12, 0.07]
        elif t < 0.9: s = (t - 0.1) / 0.8; a[i] = np.array([1.0, 0.80, 0.52]) * (0.50 + 0.50 * (1 - s) ** 1.3)
        else: a[i] = [0.12, 0.13, 0.17]
    xx = np.linspace(-1, 1, W_)[None, :, None]; a = a * (0.72 + 0.28 * (1 - xx ** 2))
    save('SM_colo_inner', inner, a, emissive=(0.42, 0.32, 0.20), repeat=False)


def triplanar(scale):
    def f(p, n):
        ax, ay, az = abs(n[0]), abs(n[1]), abs(n[2])
        if ay >= ax and ay >= az: return (p[0] / scale, p[2] / scale)
        if ax >= az: return (p[2] / scale, p[1] / scale)
        return (p[0] / scale, p[1] / scale)
    return f

def merge(dst, src):
    off = len(dst.P); dst.P += src.P; dst.N += src.N; dst.UV += src.UV; dst.I += [i + off for i in src.I]

# ---------------------------------------------------------------- steps
def steps(W=16.0, n=8, tread=1.0, rise=0.3, landing=2.6):
    m = Mesh(); uv = triplanar(4.0)
    for i in range(n): box(m, (0, (i + 1) * rise / 2, -(i + 0.5) * tread), (W, (i + 1) * rise, tread), uv)
    top = n * rise; box(m, (0, top / 2, -n * tread - landing / 2), (W, top, landing), uv)
    for sg in (-1, 1):
        for i in range(n): box(m, (sg * (W / 2 + 0.55), ((i + 1) * rise + 1.15) / 2, -(i + 0.5) * tread), (1.1, (i + 1) * rise + 1.15, tread), uv)
        box(m, (sg * (W / 2 + 0.55), (top + 1.15) / 2, -n * tread - landing / 2), (1.1, top + 1.15, landing), uv)
        box(m, (sg * (W / 2 + 0.55), 0.9, 0.55), (1.5, 1.8, 1.5), uv)                                      # foot pedestal
        box(m, (sg * (W / 2 + 0.55), 1.95, 0.55), (1.8, 0.3, 1.8), uv)
    save('SM_colo_steps', m, marble_tex(3, 512), repeat=True)

# ---------------------------------------------------------------- angel statue on a pedestal
def sphere(m, c, r, seg=12, rings=8, sy=1.0):
    prof = [(r * math.sin(math.pi * k / rings), c[1] + sy * r * -math.cos(math.pi * k / rings)) for k in range(rings + 1)]
    lathe(m, [(p[0], p[1] - c[1]) for p in prof], seg, lambda p, n: (0, 0), c[0], c[1], c[2])

def limb(m, a, b, ra, rb, seg=8):
    a = np.array(a, float); b = np.array(b, float); d = b - a; L = np.linalg.norm(d); d /= L
    t = np.cross(d, [0, 0, 1.0]); t = t / np.linalg.norm(t) if np.linalg.norm(t) > 1e-6 else np.array([1.0, 0, 0]); u = np.cross(d, t)
    for s in range(seg):
        a0, a1 = 2 * math.pi * s / seg, 2 * math.pi * (s + 1) / seg
        def ring(o, r, ang): return o + r * (math.cos(ang) * t + math.sin(ang) * u)
        pts = [ring(a, ra, a0), ring(a, ra, a1), ring(b, rb, a1), ring(b, rb, a0)]; am = (a0 + a1) / 2; n = math.cos(am) * t + math.sin(am) * u
        m.quad(*[p.tolist() for p in pts], n.tolist(), (0, 0), (0, 0), (0, 0), (0, 0))

def feather(m, root, sdir, tdir, ndir, ang, L, wd, bend, zoff, nseg=7):
    d = math.cos(ang) * sdir + math.sin(ang) * tdir; side = np.cross(ndir, d); side /= np.linalg.norm(side)
    ts = [k / nseg for k in range(nseg + 1)]; t0 = max(0.5, 1 - wd / L); rows = []
    def cen(t): return root + d * (L * t) + ndir * (bend * (t ** 2) * L * 0.12 + zoff)
    for t in ts[:-1]:
        w = wd * (0.55 + 0.45 * t) if t < t0 else wd; rows.append((cen(t), w))
    for k in range(1, 6):                                                            # rounded tip
        u = k / 6; t = t0 + (1 - t0) * u; w = wd * math.sqrt(max(0.0, 1 - u * u)) if t0 < 1 else 0; rows.append((cen(min(1.0, t0 + (1 - t0) * 0.0) + 0) + d * (L * (1 - t0)) * 0 + d * (wd) * u * 0 + d * (L * (t - t0)) * 0, 0)) if False else rows.append((cen(t0) + d * wd * u, w))
    rows.append((cen(t0) + d * wd, 0.0))
    for i in range(len(rows) - 1):
        (c0, w0), (c1, w1) = rows[i], rows[i + 1]; p = [c0 - side * w0, c0 + side * w0, c1 + side * w1, c1 - side * w1]
        for nn, off in ((ndir, 0.02), (-ndir, -0.02)):
            m.quad(*[(q + nn * 0.0 + ndir * off).tolist() for q in p], nn.tolist(), (0, 0), (1, 0), (1, 1), (0, 1))

def statue():
    m = Mesh(); uvp = triplanar(4.0)
    for (w, h, y) in ((4.4, 0.6, 0.0), (3.8, 0.5, 0.6), (2.9, 4.3, 1.1), (3.7, 0.5, 5.4), (3.2, 0.3, 5.9)): box(m, (0, y + h / 2, 0), (w, h, w), uvp)
    o = Mesh(); y0 = 6.2
    lathe(o, [(0, y0), (1.35, y0), (1.3, y0 + 0.5), (1.12, y0 + 1.6), (0.95, y0 + 3.0), (0.82, y0 + 4.2), (0.78, y0 + 5.0), (0.86, y0 + 5.55), (0.6, y0 + 5.95), (0.3, y0 + 6.1), (0.28, y0 + 6.35)], 16, lambda p, n: (0, 0))
    lathe(o, [(0.0, y0 + 4.3), (1.05, y0 + 4.15), (1.0, y0 + 2.4), (0.0, y0 + 2.0)], 16, lambda p, n: (0, 0), 0, 0, 0.0) if False else None
    sphere(o, (0, y0 + 6.85, 0.02), 0.52, 14, 9, 1.12)
    sphere(o, (-0.86, y0 + 5.5, 0), 0.4, 8, 5); sphere(o, (0.86, y0 + 5.5, 0), 0.4, 8, 5)
    limb(o, (-0.86, y0 + 5.4, 0.05), (-1.45, y0 + 3.9, 0.55), 0.3, 0.22); limb(o, (0.86, y0 + 5.4, 0.05), (1.85, y0 + 6.7, 0.25), 0.3, 0.21)
    sphere(o, (1.92, y0 + 6.9, 0.25), 0.26, 8, 5)
    limb(o, (1.92, y0 + 6.1, 0.25), (1.92, y0 + 10.6, 0.25), 0.1, 0.06); limb(o, (1.92, y0 + 10.6, 0.25), (1.92, y0 + 11.3, 0.25), 0.06, 0.0)       # sword
    limb(o, (1.45, y0 + 6.4, 0.25), (2.4, y0 + 6.4, 0.25), 0.1, 0.1)
    lathe(o, [(0, 0.0), (1.0, 0.0), (1.05, 0.12), (0.2, 0.28), (0, 0.3)], 18, lambda p, n: (0, 0), -1.7, y0 + 3.9, 0.9) if False else None
    smooth(o); merge(m, o)
    sh = Mesh(); cx, cy, cz = -1.65, y0 + 3.6, 0.78                                                                   # round shield on the lowered arm
    ring = lambda r, z: [(cx + r * math.cos(2 * math.pi * k / 20), cy + r * math.sin(2 * math.pi * k / 20), cz + z) for k in range(20)]
    for k in range(20):
        k2 = (k + 1) % 20; ro, ri = ring(1.0, 0.0), ring(0.25, 0.22)
        sh.quad(ro[k], ro[k2], ri[k2], ri[k], (0, 0.3, 1), (0, 0), (1, 0), (1, 1), (0, 1)); sh.quad(ro[k], ro[k2], (cx + 1.0 * math.cos(2 * math.pi * k2 / 20), cy + math.sin(2 * math.pi * k2 / 20), cz - 0.25), (cx + math.cos(2 * math.pi * k / 20), cy + math.sin(2 * math.pi * k / 20), cz - 0.25), (math.cos(2 * math.pi * k / 20), math.sin(2 * math.pi * k / 20), 0), (0, 0), (1, 0), (1, 1), (0, 1))
    merge(m, sh)
    for sg in (-1, 1):                                                                                                  # wings: rows of rounded feathers fanned from the shoulder
        root = np.array([sg * 0.55, y0 + 5.3, -0.55]); sdir = np.array([sg * 0.66, 0, -0.75]); sdir /= np.linalg.norm(sdir); tdir = np.array([0, 1.0, 0]); ndir = np.cross(sdir, tdir); ndir /= np.linalg.norm(ndir)
        if sg < 0: ndir = -ndir
        for row, (lm, zo, na, a0, a1, wd) in enumerate(((1.0, 0.0, 11, -8, 84, 0.66), (0.66, 0.07, 10, 4, 86, 0.58), (0.40, 0.14, 9, 14, 88, 0.48))):
            for i in range(na):
                f = i / (na - 1); a = math.radians(a0 + (a1 - a0) * f); L = lm * (3.4 + 4.0 * math.sin(math.pi * (0.2 + 0.7 * f)))
                feather(m, root + np.array([0, 0, 0.0]), sdir, tdir, ndir, a, L, wd, 1.0, zo + 0.012 * i + row * 0.02)
    save('SM_statue_angel', m, marble_tex(7, 512))

# ---------------------------------------------------------------- tiered fountain
def fountain():
    m = Mesh(); w = Mesh(); uv = triplanar(4.0)
    prof = [(0, 0.0), (3.9, 0.0), (3.9, 1.0), (3.6, 1.1), (3.4, 1.0), (3.4, 0.75), (0, 0.75)]
    lathe(m, prof, 28, uv)                                                      # lower basin rim
    lathe(m, [(3.4, 0.75), (3.4, 1.0)][::-1], 28, uv)
    lathe(m, [(0.9, 0.75), (0.8, 1.6), (0.55, 2.0), (0.5, 3.0), (0.75, 3.1), (1.5, 3.35), (2.0, 3.55)], 20, uv)           # stem + mid bowl
    lathe(m, [(2.0, 3.55), (2.05, 3.8), (1.8, 3.8), (1.7, 3.55), (0.4, 3.35)], 20, uv)
    lathe(m, [(0.4, 3.35), (0.32, 4.2), (0.32, 5.0), (0.62, 5.1), (1.05, 5.3), (1.15, 5.5), (0.95, 5.5), (0.9, 5.3), (0.3, 5.2)], 18, uv)   # top bowl
    lathe(m, [(0.3, 5.2), (0.22, 5.9), (0.3, 6.1), (0.12, 6.7), (0.0, 6.95)], 12, uv)                                       # finial
    sphere(m, (0, 6.1, 0), 0.32, 10, 6)
    save('SM_fountain', m, marble_tex(11, 512))
    lathe(w, [(0, 0.86), (3.38, 0.86)], 28, lambda p, n: (0.5, 0.5)); lathe(w, [(0, 3.62), (1.95, 3.62)], 20, lambda p, n: (0.5, 0.5)); lathe(w, [(0, 5.42), (0.9, 5.42)], 16, lambda p, n: (0.5, 0.5))
    for r_, y0_, y1_ in ((1.95, 3.6, 0.86), (0.9, 5.4, 3.65)):                    # falling water sheets (thin translucent skirts)
        lathe(w, [(r_ * 0.98, y0_), (r_ * 1.12, (y0_ + y1_) / 2 + 0.2), (r_ * 1.3, y1_ + 0.05)] if False else [(r_, y0_), (r_ * 1.02, y1_)], 20, lambda p, n: (0.5, 0.5))
    lathe(w, [(0.06, 5.5), (0.1, 6.6), (0.0, 7.4)], 8, lambda p, n: (0.5, 0.5))   # central jet
    t = np.zeros((16, 16, 4)); t[..., :3] = (0.62, 0.84, 0.92); t[..., 3] = 0.62
    P, N, I, UV = w.arrays(); img, mime = encode(t[..., :3], 'PNG'); 
    # translucent water: use baseColorFactor alpha with BLEND
    write_glb(os.path.join(OUT, 'SM_fountain_water.glb'), P, N, I, 'SM_fountain_water', uv=UV, img=img, mime=mime, color=(1, 1, 1, 0.66), emissive=(0.16, 0.22, 0.26), alpha='BLEND', double=True)
    print('SM_fountain_water', len(I) // 3)

# ---------------------------------------------------------------- striped awning stall
def awning(W=5.0, D=3.4, hb=3.9, hf=2.7, drop=0.55, n_stripes=10):
    m = Mesh(); a = np.zeros((64, 256, 3))
    for i in range(256):                                              # u 0..0.5 stripes (n_stripes), 0.5..0.625 wood, 0.625..0.75 cream cloth underside, 0.75..1 dark
        u = i / 256
        if u < 0.5: s = int(u / 0.5 * n_stripes); a[:, i] = (0.80, 0.16, 0.18) if s % 2 == 0 else (0.96, 0.93, 0.86)
        elif u < 0.625: a[:, i] = (0.40, 0.27, 0.16)
        elif u < 0.75: a[:, i] = (0.92, 0.85, 0.72)
        else: a[:, i] = (0.18, 0.12, 0.09)
    def uvS(i_, j_): return (0.5 * i_ / n_stripes * 0.998 + 0.001, j_)
    UW = lambda: (0.56, 0.5); UC = lambda: (0.69, 0.5)
    hw = W / 2; zb, zf = -D / 2, D / 2
    nx = n_stripes
    for i in range(nx):                                               # canopy, one quad per stripe
        x0, x1 = -hw + W * i / nx, -hw + W * (i + 1) / nx; n = (0, 0.55, 0.83)
        m.quad((x0, hb, zb), (x1, hb, zb), (x1, hf, zf), (x0, hf, zf), n, uvS(i, 0), uvS(i + 1, 0), uvS(i + 1, 1), uvS(i, 1))
        m.quad((x0, hb - 0.04, zb), (x1, hb - 0.04, zb), (x1, hf - 0.04, zf), (x0, hf - 0.04, zf), (0, -1, 0), UC(), UC(), UC(), UC())
        for sub in range(2):                                          # scalloped valance
            xa = x0 + (x1 - x0) * sub / 2; xb = x0 + (x1 - x0) * (sub + 1) / 2
            m.tri((xa, hf, zf), (xb, hf, zf), ((xa + xb) / 2, hf - drop, zf + 0.12), (0, 0, 1), uvS(i + sub / 2, 1), uvS(i + (sub + 1) / 2, 1), uvS(i + (sub + 0.5) / 2, 1))
            m.tri((xa, hf, zf), (xb, hf, zf), ((xa + xb) / 2, hf - drop, zf + 0.12), (0, 0, -1), UC(), UC(), UC())
    for sg in (-1, 1):                                                # front posts + back posts, counter
        for zz, hh in ((zf - 0.1, hf), (zb + 0.1, hb)): box(m, (sg * (hw - 0.12), hh / 2 - 0.02, zz), (0.16, hh, 0.16), lambda p, n: (0.56, 0.5))
    box(m, (0, 0.5, zf - 0.7), (W - 0.5, 1.0, 1.0), lambda p, n: (0.56, 0.5))                         # counter
    box(m, (0, 1.02, zf - 0.7), (W - 0.3, 0.08, 1.2), lambda p, n: (0.56, 0.5))
    box(m, (0, 1.1, zb + 0.35), (W - 0.5, 0.08, 0.7), lambda p, n: (0.56, 0.5)); box(m, (0, 1.8, zb + 0.35), (W - 0.5, 0.08, 0.7), lambda p, n: (0.56, 0.5))   # back shelves
    save('SM_stall_awning', m, a, mime='image/png', double=True, repeat=False)

# ---------------------------------------------------------------- banners
def banner_tex(w=128, h=320):
    im = Image.new('RGB', (w * 2, h), (170, 28, 34)); d = ImageDraw.Draw(im)
    for X0 in (0, w):
        pass
    d.rectangle([0, 0, w - 1, h - 1], fill=(172, 30, 36)); d.rectangle([w, 0, 2 * w - 1, h - 1], fill=(214, 168, 70))              # left half cloth, right half gold
    gold = (226, 182, 78); cx, cy = w // 2, int(h * 0.36)
    d.rectangle([5, 5, w - 6, h - 6], outline=gold, width=4); d.rectangle([12, 12, w - 13, h - 13], outline=(120, 18, 24), width=2)
    d.ellipse([cx - 34, cy - 34, cx + 34, cy + 34], outline=gold, width=5); d.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], fill=(226, 182, 78))
    d.polygon([(cx, cy - 20), (cx + 14, cy + 4), (cx + 4, cy + 4), (cx + 4, cy + 20), (cx - 4, cy + 20), (cx - 4, cy + 4), (cx - 14, cy + 4)], fill=(150, 24, 30))      # stylised sword + wings
    d.polygon([(cx - 8, cy - 4), (cx - 38, cy - 22), (cx - 30, cy + 2), (cx - 8, cy + 6)], fill=(226, 182, 78)); d.polygon([(cx + 8, cy - 4), (cx + 38, cy - 22), (cx + 30, cy + 2), (cx + 8, cy + 6)], fill=(226, 182, 78))
    for k in range(3): d.line([(cx - 28, int(h * 0.62) + k * 14), (cx + 28, int(h * 0.62) + k * 14)], fill=gold, width=3)
    return np.asarray(im) / 255.0

def banner(name, W, H, swallow=True, arm=True, waves=0.12):
    m = Mesh(); tex = banner_tex(*((128, 320) if H > W else (330, 190))); n = 8
    for i in range(n):
        x0, x1 = -W / 2 + W * i / n, -W / 2 + W * (i + 1) / n; z0, z1 = waves * math.sin(i * 0.9), waves * math.sin((i + 1) * 0.9)
        u0, u1 = 0.5 * i / n * 0.98 + 0.01, 0.5 * (i + 1) / n * 0.98 + 0.01
        yb0 = 0.0 + (0.18 * H * (1 - abs((x0 / (W / 2)))) if swallow else 0); yb1 = 0.0 + (0.18 * H * (1 - abs((x1 / (W / 2)))) if swallow else 0)
        pts = [(x0, -H + yb0, z0), (x1, -H + yb1, z1), (x1, 0, z1), (x0, 0, z0)]
        m.quad(*pts, (0, 0, 1), (u0, yb0 / H * 0 + 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)); m.quad(*pts, (0, 0, -1), (u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0))
    gu = lambda p, nn: (0.75, 0.5)
    box(m, (0, 0.06, 0), (W + 0.5, 0.14, 0.16), gu)
    if arm: box(m, (0, 0.06, -0.0), (W + 0.5, 0.14, 0.16), gu); sphere(m, (-(W / 2 + 0.3), 0.06, 0), 0.14, 8, 5); sphere(m, ((W / 2 + 0.3), 0.06, 0), 0.14, 8, 5)
    save(name, m, tex, mime='image/png', double=True, repeat=False)

# ---------------------------------------------------------------- paving
def paving():
    m = Mesh(); s = 10.0
    m.quad((-s, 0, -s), (s, 0, -s), (s, 0, s), (-s, 0, s), (0, 1, 0), (0, 0), (1, 0), (1, 1), (0, 1))
    box(m, (0, -0.25, 0), (20, 0.5, 20), lambda p, n: (0.5, 0.5), faces=("-x", "+x", "-z", "+z"))
    save('SM_paving_20x20', m, paving_tex(5, 1024, base=(0.70, 0.68, 0.64)))

if __name__ == '__main__':
    which = sys.argv[2:] or ['colosseum', 'steps', 'statue', 'fountain', 'awning', 'banner', 'paving']
    if 'colosseum' in which: colosseum()
    if 'steps' in which: steps()
    if 'statue' in which: statue()
    if 'fountain' in which: fountain()
    if 'awning' in which: awning()
    if 'banner' in which: banner('SM_banner_tall', 1.7, 5.6); banner('SM_banner_wide', 5.2, 3.0, swallow=False)
    if 'paving' in which: paving()

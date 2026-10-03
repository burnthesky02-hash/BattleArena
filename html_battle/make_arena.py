"""Generates maps/arena_placeholder.glb -- a stand-in colosseum built from plain geometry (no external assets).
Run: python make_arena.py   (writes next to this script / into ./maps)
"""
import json, math, struct, zlib, os, random

random.seed(7)
mats = []          # glTF materials
def mat(color, emissive=None, tex=None):
    m = {"pbrMetallicRoughness": {"baseColorFactor": list(color), "metallicFactor": 0, "roughnessFactor": 1}}
    if emissive: m["emissiveFactor"] = list(emissive)
    if tex is not None: m["pbrMetallicRoughness"]["baseColorTexture"] = {"index": tex}
    mats.append(m); return len(mats) - 1

# ---- sand texture (value noise, seamless-ish) as PNG
def png(w, h, px):
    raw = b"".join(b"\x00" + bytes(px[y * w * 3:(y + 1) * w * 3]) for y in range(h))
    def ch(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 9)) + ch(b"IEND", b"")
W = 256
grid = [[random.random() for _ in range(16)] for _ in range(16)]
def noise(x, y, f):
    g = 16 // f; fx, fy = x / W * g * 1.0, y / W * g * 1.0
    x0, y0 = int(fx) % 16, int(fy) % 16; x1, y1 = (x0 + 1) % 16, (y0 + 1) % 16
    tx, ty = fx - int(fx), fy - int(fy); tx = tx * tx * (3 - 2 * tx); ty = ty * ty * (3 - 2 * ty)
    a = grid[y0][x0] * (1 - tx) + grid[y0][x1] * tx; b = grid[y1][x0] * (1 - tx) + grid[y1][x1] * tx
    return a * (1 - ty) + b * ty
px = []
for y in range(W):
    for x in range(W):
        n = 0.5 * noise(x, y, 1) + 0.3 * noise(x * 2 % W, y * 2 % W, 1) + 0.2 * random.random()
        r, g, b = 196 + (n - .5) * 60, 168 + (n - .5) * 56, 120 + (n - .5) * 50
        px += [max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b)))]
sand_png = png(W, W, px)

M_SAND = mat((1, 1, 1, 1), tex=0)
M_STONE = mat((0.62, 0.58, 0.66, 1)); M_STONE2 = mat((0.50, 0.46, 0.56, 1)); M_DARK = mat((0.30, 0.26, 0.38, 1))
M_TRIM = mat((0.78, 0.70, 0.52, 1)); M_EMBER = mat((1, .6, .2, 1), emissive=(1.0, 0.45, 0.1))

class Mesh:
    def __init__(s): s.p = []; s.n = []; s.t = []; s.i = []
    def quad(s, a, b, c, d, uv=((0, 0), (1, 0), (1, 1), (0, 1))):
        # a,b,c,d counter-clockwise seen from the front; flat normal
        ux, uy, uz = (b[k] - a[k] for k in range(3)); vx, vy, vz = (d[k] - a[k] for k in range(3))
        n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx); l = math.sqrt(sum(x * x for x in n)) or 1; n = tuple(x / l for x in n)
        base = len(s.p)
        for v, u in zip((a, b, c, d), uv): s.p.append(v); s.n.append(n); s.t.append(u)
        s.i += [base, base + 1, base + 2, base, base + 2, base + 3]
    def tri(s, a, b, c):
        ux, uy, uz = (b[k] - a[k] for k in range(3)); vx, vy, vz = (c[k] - a[k] for k in range(3))
        n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx); l = math.sqrt(sum(x * x for x in n)) or 1; n = tuple(x / l for x in n)
        base = len(s.p)
        for v in (a, b, c): s.p.append(v); s.n.append(n); s.t.append((0, 0))
        s.i += [base, base + 1, base + 2]

def box(m, cx, cy, cz, sx, sy, sz, rot=0.0):
    c, s_ = math.cos(rot), math.sin(rot)
    def P(x, y, z): return (cx + x * c + z * s_, cy + y, cz - x * s_ + z * c)
    x0, x1, y0, y1, z0, z1 = -sx / 2, sx / 2, 0, sy, -sz / 2, sz / 2
    m.quad(P(x0, y1, z1), P(x1, y1, z1), P(x1, y1, z0), P(x0, y1, z0))   # top
    m.quad(P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1))   # +z
    m.quad(P(x1, y0, z0), P(x0, y0, z0), P(x0, y1, z0), P(x1, y1, z0))   # -z
    m.quad(P(x1, y0, z1), P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1))   # +x
    m.quad(P(x0, y0, z0), P(x0, y0, z1), P(x0, y1, z1), P(x0, y1, z0))   # -x

def sector(m, r0, r1, a0, a1, y0, y1, steps=3):
    """annular sector prism: top, inner face, outer face, two end caps"""
    def pt(r, a, y): return (r * math.sin(a), y, r * math.cos(a))
    for k in range(steps):
        u0 = a0 + (a1 - a0) * k / steps; u1 = a0 + (a1 - a0) * (k + 1) / steps
        m.quad(pt(r0, u0, y1), pt(r1, u0, y1), pt(r1, u1, y1), pt(r0, u1, y1))      # top (CCW from above)
        m.quad(pt(r1, u0, y0), pt(r1, u1, y0), pt(r1, u1, y1), pt(r1, u0, y1))      # outer face
        m.quad(pt(r0, u1, y0), pt(r0, u0, y0), pt(r0, u0, y1), pt(r0, u1, y1))      # inner face
    m.quad(pt(r0, a0, y0), pt(r1, a0, y0), pt(r1, a0, y1), pt(r0, a0, y1))
    m.quad(pt(r1, a1, y0), pt(r0, a1, y0), pt(r0, a1, y1), pt(r1, a1, y1))

def disc(m, r, y, seg=64, uvscale=6.0, rin=0.0):
    for k in range(seg):
        a0 = 2 * math.pi * k / seg; a1 = 2 * math.pi * (k + 1) / seg
        def pt(rr, a): return (rr * math.sin(a), y, rr * math.cos(a))
        def uv(rr, a): return (0.5 + rr / r * math.sin(a) * uvscale / 2, 0.5 + rr / r * math.cos(a) * uvscale / 2)
        if rin == 0:
            m.tri(pt(0, 0), pt(r, a1), pt(r, a0)); m.t[-3:] = [uv(0, 0), uv(r, a1), uv(r, a0)]
        else:
            m.quad(pt(rin, a0), pt(rin, a1), pt(r, a1), pt(r, a0), uv=(uv(rin, a0), uv(rin, a1), uv(r, a1), uv(r, a0)))

nodes_def = []   # (name, mesh, material)
def add(name, mesh, mat_i): nodes_def.append((name, mesh, mat_i))

R_FLOOR, R_WALL = 17.0, 17.6
g = Mesh(); disc(g, R_FLOOR, 0.0); add("ground", g, M_SAND)
ring = Mesh(); disc(ring, 6.0, 0.012, rin=5.7, uvscale=1.0); add("ground_ring_inner", ring, M_TRIM)
ring2 = Mesh(); disc(ring2, 12.2, 0.012, rin=11.9, uvscale=1.0); add("ground_ring_outer", ring2, M_TRIM)
curb = Mesh(); sector(curb, R_FLOOR, R_WALL, 0, 2 * math.pi, 0, 0.45, steps=64); add("curb", curb, M_TRIM)

N = 16
for i in range(N):
    a0 = 2 * math.pi * i / N + 0.012; a1 = 2 * math.pi * (i + 1) / N - 0.012
    w = Mesh(); sector(w, R_WALL, R_WALL + 0.6, a0, a1, 0.45, 3.4, steps=4); add(f"wall_{i:02d}", w, M_STONE if i % 2 == 0 else M_STONE2)
    st = Mesh()
    for tier in range(5):
        sector(st, R_WALL + 0.6 + tier * 2.2, R_WALL + 0.6 + (tier + 1) * 2.2, a0, a1, 0, 3.4 + tier * 1.1, steps=4)
    add(f"stand_{i:02d}", st, M_DARK if i % 2 == 0 else M_STONE2)
    am = 2 * math.pi * i / N                       # column at the joint between pieces
    col = Mesh(); cx, cz = (R_WALL + 0.3) * math.sin(am), (R_WALL + 0.3) * math.cos(am)
    box(col, cx, 0.45, cz, 1.3, 5.6, 1.3, rot=am); box(col, cx, 6.0, cz, 1.8, 0.5, 1.8, rot=am); add(f"column_{i:02d}", col, M_STONE)
    br = Mesh(); box(br, cx, 6.5, cz, 0.7, 0.55, 0.7, rot=am); add(f"brazier_{i:02d}", br, M_EMBER)

# gate arches (decor, near the far side): two dark slabs
for k, ang in enumerate((math.pi, math.pi * 0.62)):
    gm = Mesh(); cx, cz = (R_WALL + 0.35) * math.sin(ang), (R_WALL + 0.35) * math.cos(ang)
    box(gm, cx, 0.45, cz, 3.6, 3.2, 0.5, rot=ang); add(f"gate_{k}", gm, M_DARK)

# ---- assemble GLB
bin_ = bytearray(); views = []; accs = []; meshes = []; nodes = []
def add_view(data, target=None):
    while len(bin_) % 4: bin_.append(0)
    off = len(bin_); bin_.extend(data); v = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
    if target: v["target"] = target
    views.append(v); return len(views) - 1
def add_acc(vi, ctype, count, typ, mn=None, mx=None):
    a = {"bufferView": vi, "componentType": ctype, "count": count, "type": typ}
    if mn: a["min"] = mn; a["max"] = mx
    accs.append(a); return len(accs) - 1
for name, m, mi in nodes_def:
    P = [c for v in m.p for c in v]
    mn = [min(v[k] for v in m.p) for k in range(3)]; mx = [max(v[k] for v in m.p) for k in range(3)]
    ap = add_acc(add_view(struct.pack(f"<{len(P)}f", *P), 34962), 5126, len(m.p), "VEC3", mn, mx)
    N_ = [c for v in m.n for c in v]; an = add_acc(add_view(struct.pack(f"<{len(N_)}f", *N_), 34962), 5126, len(m.n), "VEC3")
    T = [c for v in m.t for c in v]; at = add_acc(add_view(struct.pack(f"<{len(T)}f", *T), 34962), 5126, len(m.t), "VEC2")
    ai = add_acc(add_view(struct.pack(f"<{len(m.i)}I", *m.i), 34963), 5125, len(m.i), "SCALAR")
    meshes.append({"name": name, "primitives": [{"attributes": {"POSITION": ap, "NORMAL": an, "TEXCOORD_0": at}, "indices": ai, "material": mi}]})
    nodes.append({"name": name, "mesh": len(meshes) - 1})
img_view = add_view(sand_png)
gltf = {"asset": {"version": "2.0", "generator": "make_arena.py"}, "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}], "nodes": nodes,
        "meshes": meshes, "materials": mats, "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": len(bin_)}],
        "images": [{"bufferView": img_view, "mimeType": "image/png"}], "textures": [{"source": 0, "sampler": 0}],
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}]}
js = json.dumps(gltf, separators=(",", ":")).encode()
while len(js) % 4: js += b" "
while len(bin_) % 4: bin_.append(0)
glb = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(bin_)) + struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(bin_), 0x004E4942) + bytes(bin_)
os.makedirs("maps", exist_ok=True)
open("maps/arena_placeholder.glb", "wb").write(glb)
json.dump({"name": "Placeholder Arena", "model": "arena_placeholder.glb", "scale": 1, "offset": [0, 0, 0], "rotY": 0,
           "light": {"dir": [-0.45, -1, -0.35], "color": [1.0, 0.93, 0.82], "ambient": [0.52, 0.5, 0.62]},
           "fog": {"color": [0.11, 0.08, 0.2], "near": 38, "far": 95}, "sky": "painted", "cullNearCamera": 8},
          open("maps/arena_placeholder.json", "w"), indent=2)
print("wrote", len(glb), "bytes,", len(nodes), "nodes")

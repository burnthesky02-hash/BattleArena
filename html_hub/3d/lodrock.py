"""Quadric edge-collapse decimation of a single-mesh textured GLB (positions/normals/uvs kept per surviving vertex).
usage: python lodrock.py in.glb out.glb target_tris"""
import json, struct, sys, heapq, numpy as np
src, dst, target = sys.argv[1], sys.argv[2], int(sys.argv[3]); TINT = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
b = open(src, 'rb').read(); jl = struct.unpack('<I', b[12:16])[0]; j = json.loads(b[20:20 + jl]); bo = 20 + jl + 8
def acc(i):
    a = j['accessors'][i]; bv = j['bufferViews'][a['bufferView']]; n = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[a['type']]
    dt = {5126: '<f4', 5125: '<u4', 5123: '<u2', 5121: 'u1'}[a['componentType']]
    off = bo + bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    return np.frombuffer(b, dt, a['count'] * n, off).reshape(a['count'], n).copy()
pr = j['meshes'][0]['primitives'][0]
P = acc(pr['attributes']['POSITION']).astype(np.float64); N = acc(pr['attributes']['NORMAL']); UV = acc(pr['attributes']['TEXCOORD_0'])
T = acc(pr['indices']).reshape(-1, 3).astype(np.int64)
print('in', len(P), 'verts', len(T), 'tris')
kq = np.round(P, 4); Pw, inv = np.unique(kq, axis=0, return_inverse=True); inv = inv.ravel()
TUVc = UV[T]                       # per-triangle-corner UV (kept as is)
T = inv[T]; P = Pw.astype(np.float64); nv = len(P)
keep = np.array([len(set(t)) == 3 for t in T]); T = T[keep]; TUVc = TUVc[keep]
# per-vertex quadrics
Q = np.zeros((nv, 4, 4))
p0, p1, p2 = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
fn = np.cross(p1 - p0, p2 - p0); ar = np.linalg.norm(fn, axis=1); ok = ar > 1e-12; fn[ok] /= ar[ok, None]
d = -np.einsum('ij,ij->i', fn, p0); pl = np.concatenate([fn, d[:, None]], 1)
K = pl[:, :, None] * pl[:, None, :] * ar[:, None, None]
for k in range(3): np.add.at(Q, T[:, k], K)
alive_t = np.ones(len(T), bool); T = T.copy()
vt = [set() for _ in range(nv)]
for ti, t in enumerate(T):
    for v in t: vt[v].add(ti)
# boundary vertices: edges with one triangle
from collections import Counter
ec = Counter()
for t in T:
    for a, c in ((0, 1), (1, 2), (2, 0)): ec[(min(t[a], t[c]), max(t[a], t[c]))] += 1
bnd = np.zeros(nv, bool)
for (a, c), n in ec.items():
    if n == 1: bnd[a] = bnd[c] = True
def cost(a, c):                       # collapse a -> c
    if bnd[a] and not bnd[c]: return None
    v = np.append(P[c], 1.0); q = Q[a] + Q[c]
    return float(v @ q @ v)
ver = np.zeros(nv, int); heap = []
def push(a, c):
    cs = cost(a, c)
    if cs is not None: heapq.heappush(heap, (cs, a, c, ver[a], ver[c]))
for (a, c) in ec: push(a, c); push(c, a)
ntri = len(T)
while ntri > target and heap:
    cs, a, c, va, vc = heapq.heappop(heap)
    if ver[a] != va or ver[c] != vc or not vt[a] or not vt[c]: continue
    # edge must still exist
    if not (vt[a] & vt[c]): continue
    # fold check: normals of surviving triangles around a must not flip badly
    bad = False
    for ti in vt[a]:
        if not alive_t[ti] or c in T[ti]: continue
        t = T[ti].copy(); t[t == a] = c
        q0, q1, q2 = P[t[0]], P[t[1]], P[t[2]]; nn = np.cross(q1 - q0, q2 - q0)
        o0, o1, o2 = P[T[ti][0]], P[T[ti][1]], P[T[ti][2]]; on = np.cross(o1 - o0, o2 - o0)
        if np.dot(nn, on) < 0.15 * np.linalg.norm(nn) * np.linalg.norm(on): bad = True; break
    if bad: continue
    Q[c] += Q[a]
    for ti in list(vt[a]):
        if not alive_t[ti]: continue
        if c in T[ti]:
            alive_t[ti] = False; ntri -= 1
            for v in T[ti]: vt[v].discard(ti)
        else:
            T[ti][T[ti] == a] = c; vt[c].add(ti)
    vt[a] = set(); ver[a] += 1; ver[c] += 1
    nbr = set()
    for ti in vt[c]:
        if alive_t[ti]: nbr.update(int(v) for v in T[ti])
    for n in nbr:
        if n != c: push(c, n); push(n, c)
T2w = T[alive_t]; U2w = TUVc[alive_t]
keyd = {}; Pl = []; UVl = []; T2 = np.zeros_like(T2w)
for ti in range(len(T2w)):
    for k in range(3):
        key = (int(T2w[ti][k]), round(float(U2w[ti][k][0]), 5), round(float(U2w[ti][k][1]), 5))
        ix = keyd.get(key)
        if ix is None: ix = len(Pl); keyd[key] = ix; Pl.append(P[key[0]]); UVl.append(U2w[ti][k])
        T2[ti][k] = ix
P2 = np.array(Pl, np.float32); UV2 = np.array(UVl, np.float32)
# recompute smooth normals
pp = P2.astype(np.float64); nrm = np.zeros_like(pp)
f = np.cross(pp[T2[:, 1]] - pp[T2[:, 0]], pp[T2[:, 2]] - pp[T2[:, 0]])
for k in range(3): np.add.at(nrm, T2[:, k], f)
l = np.linalg.norm(nrm, axis=1, keepdims=True); l[l == 0] = 1; N2 = (nrm / l).astype(np.float32)
print('out', len(P2), 'verts', len(T2), 'tris')
# write glb (reuse source material + image)
mat = json.loads(json.dumps(j['materials'][pr['material']])); mat['pbrMetallicRoughness']['baseColorFactor'] = [TINT, TINT, TINT * 1.08, 1.0]; img = j['images'][0]; bv = j['bufferViews'][img['bufferView']]
imgb = b[bo + bv.get('byteOffset', 0): bo + bv.get('byteOffset', 0) + bv['byteLength']]
out = bytearray(); bvs = []; accs = []
def add(arr, target, **kw):
    data = arr.tobytes()
    while len(out) % 4: out.append(0)
    bvs.append(dict(buffer=0, byteOffset=len(out), byteLength=len(data), target=target)); out.extend(data)
    accs.append(dict(bufferView=len(bvs) - 1, **kw)); return len(accs) - 1
at = {}
at['POSITION'] = add(P2, 34962, componentType=5126, count=len(P2), type='VEC3', min=P2.min(0).tolist(), max=P2.max(0).tolist())
at['NORMAL'] = add(N2, 34962, componentType=5126, count=len(N2), type='VEC3')
at['TEXCOORD_0'] = add(UV2, 34962, componentType=5126, count=len(UV2), type='VEC2')
ii = add(T2.astype('<u4').ravel(), 34963, componentType=5125, count=T2.size, type='SCALAR')
while len(out) % 4: out.append(0)
bvs.append(dict(buffer=0, byteOffset=len(out), byteLength=len(imgb))); out.extend(imgb); ib = len(bvs) - 1
g = dict(asset=dict(version='2.0', generator='lodrock'), scene=0, scenes=[dict(nodes=[0])], nodes=[dict(mesh=0)],
         meshes=[dict(primitives=[dict(attributes=at, indices=ii, material=0, mode=4)])], materials=[mat],
         images=[dict(bufferView=ib, mimeType=img['mimeType'])], textures=[dict(source=0, sampler=0)],
         samplers=j.get('samplers') or [dict(magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497)],
         accessors=accs, bufferViews=bvs, buffers=[dict(byteLength=len(out))])
js = json.dumps(g, separators=(',', ':')).encode()
while len(js) % 4: js += b' '
open(dst, 'wb').write(struct.pack('<III', 0x46546C67, 2, 28 + len(js) + len(out)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(out), 0x004E4942) + bytes(out))

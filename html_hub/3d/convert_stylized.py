"""Textured, game-ready GLBs for the StylizedIsland kit (UE5): UassetConverter/glb_output/StylizedIsland/Mesh -> Assets/3D/Stylized/.
Run from anywhere:  python html_hub/3d/convert_stylized.py [srcdir] [dstdir]
 * geometry GLBs come from `python -m uasset_to_glb UassetConverter/StylizedIsland UassetConverter/glb_output/StylizedIsland --recursive`
 * textures are read from the material/texture uassets under UassetConverter/StylizedIsland (BaseColor only, 512 px JPEG; PNG + MASK for leaves)
 * Modular_Pieces keep their original pivot (a wall's origin is its bottom-left corner: x 0..4, y 0..3, z 0..0.35); everything else is re-pivoted
   (x/z centred, base on y=0).  Output names are the mesh file names; sizes.json lists each model's bounding box after re-pivoting.
Materials with no readable texture fall back to FALLBACK flat colours."""
import sys, os, io, json, struct, glob
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.abspath(os.path.join(HERE, '..', '..')) if os.path.basename(HERE) == '3d' else HERE
sys.path.insert(0, os.path.join(PROJ, 'UassetConverter'))
import numpy as np
from PIL import Image
from uasset_to_glb.materials import MaterialLibrary
from uasset_to_glb.texture import read_texture
ROOT = os.path.join(PROJ, 'UassetConverter')
lib = MaterialLibrary(ROOT + '/StylizedIsland')
FALLBACK = {'MI_Wall': (.93, .86, .72), 'M_Wall': (.93, .86, .72), 'MI_Roof': (.75, .32, .22), 'MI_Trim': (.55, .38, .24), 'MI_Window': (.55, .75, .85),
            'MI_Stone_Trim': (.62, .6, .56), 'MI_Basket': (.78, .62, .36), 'MI_Boat': (.6, .4, .26), 'MI_Bonfire': (.5, .38, .3), 'MI_Bucket': (.55, .4, .26),
            'MI_Chest': (.6, .38, .2), 'M_Water_Inst': (.35, .65, .8), 'GrassRVTMaster1_Inst1': (.38, .62, .26), 'GrassRVTMaster1_Inst3': (.86, .74, .34)}
FLOWER = {'Blue': (.3, .45, .95), 'Pink': (.95, .5, .7), 'Red': (.9, .2, .2), 'White': (.95, .95, .9), 'Yellow': (.97, .85, .2), 'Sunflower': (.98, .8, .1)}
_cache = {}
def texim(name):
    if name in _cache: return _cache[name]
    p = lib.find(name); im = None
    if p:
        try:
            png, w, h = read_texture(p); im = Image.open(io.BytesIO(png)); im.load()
        except Exception as e: print('  tex fail', name, e)
    _cache[name] = im; return im

def enc(im, alpha=False, size=512):
    im = im.copy()
    if max(im.size) > size:
        w, h = im.size; im = im.resize((size, max(1, size * h // w)) if w >= h else (max(1, size * w // h), size), Image.LANCZOS)
    b = io.BytesIO()
    if alpha: im.convert('RGBA').save(b, 'PNG', optimize=True)
    else: im.convert('RGB').save(b, 'JPEG', quality=86)
    return b.getvalue()

def grade(im, tname, leaf, mname):
    """Brightness / hue grade baked into the pixels (the UE materials tint at runtime; we can't)."""
    if leaf:
        a = np.asarray(im.convert('RGBA')).astype('f4') / 255
        L = a[..., :3].max(2)
        al = a[..., 3] if a[..., 3].min() < 0.9 else np.clip(L * 1.6, 0, 1)
        tint = np.array((.35, .55, .95) if mname.startswith('B_Tree') else (.30, .62, .22), 'f4')
        sh = 0.55 + 0.6 * np.clip(L, 0, 1)
        rgb = tint[None, None] * sh[..., None]
        return Image.fromarray((np.dstack([np.clip(rgb, 0, 1), al]) * 255).astype('u1'), 'RGBA')
    a = np.asarray(im.convert('RGB')).astype('f4') / 255
    if 'Plaster' in tname or 'Wall_C' in tname: g = np.array((1.45, 1.42, 1.30), 'f4')
    else:
        m = float((a * np.array((.3, .59, .11), 'f4')).sum(2).mean()); g = np.full(3, min(2.2, max(1.0, 0.42 / max(m, .02))), 'f4')
    return Image.fromarray((np.clip(a * g, 0, 1) * 255).astype('u1'), 'RGB')

def apply_tint(im, f):
    a = np.asarray(im.convert('RGB')).astype('f4') / 255
    return Image.fromarray((np.clip(f(a), 0, 1) * 255).astype('u1'), 'RGB')

def mul(r, g, b): return lambda a: a * np.array((r, g, b), 'f4')
def perm(i, j, k, gain=1.0): return lambda a: a[..., [i, j, k]] * gain
def grey(r, g, b): return lambda a: (a * np.array((.3, .59, .11), 'f4')).sum(2, keepdims=True) * np.array((r, g, b), 'f4')
WALL_T = dict(cream=None, sand=mul(1, .9, .68), blue=mul(.78, .9, 1.12), rose=mul(1.06, .82, .8), mint=mul(.84, 1.02, .86), stone=grey(.95, .95, .92))
ROOF_T = dict(red=None, blue=perm(2, 1, 0, 1.1), brown=mul(.85, .8, .7), green=perm(1, 0, 2, 1.1), slate=grey(.85, .92, 1.02))
VAR_WALL = ['Door_Wall_01', 'Door_Wall_02', 'Window_Wall_01', 'Window_Wall_02', 'Window_Wall_03', 'Window_Wall_04', 'Large_Wall_01', 'Large_Wall_02', 'Large_Wall_03', 'Roof_Wall']
VAR_ROOF = ['Roof_02', 'Roof_05', 'Roof_04']

def variants(srcdir, dstdir):
    sp = os.path.join(dstdir, 'sizes.json'); sizes = json.load(open(sp)) if os.path.exists(sp) else {}
    for n in VAR_WALL:
        f = glob.glob(srcdir + '/**/SM_' + n + '.glb', recursive=True)[0]
        for k, fn in WALL_T.items():
            r = convert(f, os.path.join(dstdir, 'SM_%s_w%s.glb' % (n, k)), keep_pivot=True, tint={'MI_Wall': fn, 'M_Wall': fn} if fn else None); print(n, k, r['bytes'] // 1024)
    for n in VAR_ROOF:
        f = glob.glob(srcdir + '/**/SM_' + n + '.glb', recursive=True)[0]
        for k, fn in ROOF_T.items():
            r = convert(f, os.path.join(dstdir, 'SM_%s_r%s.glb' % (n, k)), keep_pivot=True, tint={'MI_Roof': fn} if fn else None); print(n, k, r['bytes'] // 1024)

def load(path):
    b = open(path, 'rb').read(); l = struct.unpack('<I', b[12:16])[0]; j = json.loads(b[20:20 + l]); off = 20 + l + 8
    return j, b[off:]

def acc(j, bin, i):
    a = j['accessors'][i]; bv = j['bufferViews'][a['bufferView']]
    n = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3}[a['type']]; dt = {5126: '<f4', 5125: '<u4', 5123: '<u2'}[a['componentType']]
    o = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    return np.frombuffer(bin, dt, a['count'] * n, o).reshape(-1, n) if n > 1 else np.frombuffer(bin, dt, a['count'], o)

def base_tex(m):
    """(texture name, opacity-from-alpha?) for a material instance."""
    if m is None: return None, False
    if m.base_color: return m.base_color, False
    for k in ('BaseColor_01', 'Leaf_Texture', 'BaseColor', 'Color'):
        if m.textures.get(k): return m.textures[k], k == 'Leaf_Texture'
    return None, False

def convert(src, dst, size=512, keep_pivot=False, tint=None):
    j, bin = load(src); mesh = j['meshes'][0]; mname = mesh['name']
    prims = []; allp = []
    for p in mesh['primitives']:
        pos = acc(j, bin, p['attributes']['POSITION']).astype('f4')
        nor = acc(j, bin, p['attributes']['NORMAL']).astype('f4') if 'NORMAL' in p['attributes'] else None
        uv = acc(j, bin, p['attributes']['TEXCOORD_0']).astype('f4') if 'TEXCOORD_0' in p['attributes'] else np.zeros((len(pos), 2), 'f4')
        idx = acc(j, bin, p['indices']).astype('u4'); prims.append((pos, nor, uv, idx, p.get('material', 0))); allp.append(pos)
    P = np.concatenate(allp); mn, mx = P.min(0), P.max(0)
    off = np.zeros(3, 'f4') if keep_pivot else np.array([(mn[0] + mx[0]) / 2, mn[1], (mn[2] + mx[2]) / 2], 'f4')
    out = bytearray(); bvs = []; accs = []; imgs = []; texs = []; mats = []; prm = []
    def addbv(data, target=None):
        while len(out) % 4: out.append(0)
        bvs.append(dict(buffer=0, byteOffset=len(out), byteLength=len(data), **({'target': target} if target else {}))); out.extend(data); return len(bvs) - 1
    icache = {}; mcache = {}; info = {}
    for (pos, nor, uv, idx, mi) in prims:
        mnm = j['materials'][mi]['name']; base = mnm[:-(len(mname) + 1)] if mnm.endswith('_' + mname) else mnm
        if mi not in mcache:
            m = lib.material(base) or (lib.material('MI_Wall') if base == 'M_Wall' else None)
            pbr = dict(metallicFactor=0.0, roughnessFactor=0.9); mat = dict(name=base, pbrMetallicRoughness=pbr); fac = [.75, .75, .75, 1]
            tname, leaf = base_tex(m); im = texim(tname) if tname else None
            if im is not None:
                tf = tint.get(base) if tint else None
                key = (tname, leaf, mname.startswith('B_Tree') if leaf else 0, id(tf))
                if key not in icache:
                    im = grade(im, tname, leaf, mname)
                    if tf is not None: im = apply_tint(im, tf)
                    if leaf: data, mime = enc(im, True, size), 'image/png'
                    else: data, mime = enc(im, False, size), 'image/jpeg'
                    bv = addbv(data); imgs.append(dict(bufferView=bv, mimeType=mime)); texs.append(dict(source=len(imgs) - 1, sampler=0)); icache[key] = len(texs) - 1
                pbr['baseColorTexture'] = dict(index=icache[key]); fac = [1, 1, 1, 1]
                if leaf: mat['alphaMode'] = 'MASK'; mat['alphaCutoff'] = 0.4; mat['doubleSided'] = True; mat['extensions'] = {'KHR_materials_unlit': {}}
                info[base] = 'tex:' + tname
            else:
                fac = list(next((v for k, v in FLOWER.items() if k in mname), None) or FALLBACK.get(base, (.62, .6, .55))) + [1]; info[base] = 'flat'
            if 'Window' in base and im is not None: mat['alphaMode'] = 'BLEND'; fac[3] = 0.55
            pbr['baseColorFactor'] = fac; mcache[mi] = len(mats); mats.append(mat)
        p2 = pos - off; vcol = None
        if mats[mcache[mi]].get('alphaMode') == 'MASK':                      # leaf cards: shade like a soft ball (normals point away from the crown centre) instead of per-card flat/dark backs
            c = (pos.min(0) + pos.max(0)) / 2; c[1] = pos[:, 1].min() + 0.55 * (pos[:, 1].max() - pos[:, 1].min()); v = pos - c; v[:, 1] = v[:, 1] * 0.7 + 0.45 * np.abs(v).max()
            nor = (v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-6)).astype('f4')
            tr = idx.reshape(-1, 3); fn = np.cross(pos[tr[:, 1]] - pos[tr[:, 0]], pos[tr[:, 2]] - pos[tr[:, 0]]); cen = pos[tr].mean(1) - c   # wind every card to face outwards (the engine flips normals on back faces)
            hf = (pos[:, 1] - pos[:, 1].min()) / max(float(np.ptp(pos[:, 1])), 1e-6); lum = np.clip(0.70 + 0.38 * hf + 0.14 * nor[:, 1] + 0.10 * nor[:, 0], 0.6, 1.2)      # baked light: brighter crown top / sun side
            vcol = np.stack([lum, lum, lum, np.ones_like(lum)], 1).astype('<f4')
            fl = (fn * cen).sum(1) < 0; tr = tr.copy(); tr[fl] = tr[fl][:, [0, 2, 1]]; idx = tr.reshape(-1)
        b = addbv(p2.astype('<f4').tobytes(), 34962); accs.append(dict(bufferView=b, componentType=5126, count=len(p2), type='VEC3', min=p2.min(0).tolist(), max=p2.max(0).tolist())); at = {'POSITION': len(accs) - 1}
        if nor is not None: b = addbv(nor.astype('<f4').tobytes(), 34962); accs.append(dict(bufferView=b, componentType=5126, count=len(nor), type='VEC3')); at['NORMAL'] = len(accs) - 1
        b = addbv(uv.astype('<f4').tobytes(), 34962); accs.append(dict(bufferView=b, componentType=5126, count=len(uv), type='VEC2')); at['TEXCOORD_0'] = len(accs) - 1
        if vcol is not None: b = addbv(vcol.tobytes(), 34962); accs.append(dict(bufferView=b, componentType=5126, count=len(vcol), type='VEC4')); at['COLOR_0'] = len(accs) - 1
        b = addbv(idx.astype('<u4').tobytes(), 34963); accs.append(dict(bufferView=b, componentType=5125, count=len(idx), type='SCALAR'))
        prm.append(dict(attributes=at, indices=len(accs) - 1, material=mcache[mi], mode=4))
    while len(out) % 4: out.append(0)
    g = dict(asset=dict(version='2.0', generator='stylized-build'), scene=0, scenes=[dict(nodes=[0])], nodes=[dict(name=mname, mesh=0)], meshes=[dict(name=mname, primitives=prm)],
             materials=mats, accessors=accs, bufferViews=bvs, buffers=[dict(byteLength=len(out))])
    if any('extensions' in m for m in mats): g['extensionsUsed'] = ['KHR_materials_unlit']
    if imgs: g['images'] = imgs; g['textures'] = texs; g['samplers'] = [dict(magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497)]
    js = json.dumps(g, separators=(',', ':')).encode()
    while len(js) % 4: js += b' '
    blob = struct.pack('<III', 0x46546C67, 2, 28 + len(js) + len(out)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(out), 0x004E4942) + bytes(out)
    open(dst, 'wb').write(blob)
    q = P - off
    return dict(size=[round(float(v), 3) for v in (mx - mn)], min=[round(float(v), 3) for v in q.min(0)], max=[round(float(v), 3) for v in q.max(0)], mats=info, bytes=len(blob))

if __name__ == '__main__' and '--variants' in sys.argv:
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    variants(a[0] if a else os.path.join(ROOT, 'glb_output', 'StylizedIsland', 'Mesh'), a[1] if len(a) > 1 else os.path.join(PROJ, 'Assets', '3D', 'Stylized'))
elif __name__ == '__main__':
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    if only: sys.argv = [a for i, a in enumerate(sys.argv) if a != '--only' and (i == 0 or sys.argv[i - 1] != '--only')]
    srcdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'glb_output', 'StylizedIsland', 'Mesh')
    dstdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(PROJ, 'Assets', '3D', 'Stylized'); os.makedirs(dstdir, exist_ok=True)
    sp = os.path.join(dstdir, 'sizes.json'); sizes = json.load(open(sp)) if os.path.exists(sp) else {}
    for f in sorted(glob.glob(srcdir + '/**/*.glb', recursive=True)):
        n = os.path.basename(f)
        if n.startswith('S_EV_Fog') or (only and only not in f.replace('\\', '/')): continue
        try:
            r = convert(f, os.path.join(dstdir, n), keep_pivot='Modular_Pieces' in f.replace('\\', '/'))
            sizes[n[:-4]] = dict(min=r['min'], max=r['max']); print(n, r['size'], r['bytes'] // 1024, 'KB', r['mats'])
        except Exception:
            import traceback; traceback.print_exc()
    json.dump(sizes, open(sp, 'w'), indent=0)

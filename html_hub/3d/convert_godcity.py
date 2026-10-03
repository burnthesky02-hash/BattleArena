"""Textured, game-ready GLBs from the converter's geometry GLBs (God_city kit).

Usage (from the project root):  python html_hub/3d/convert_godcity.py
  reads  UassetConverter/glb_output/God_city/Meshes/**/*.glb   (geometry from uasset_to_glb, no textures)
         UassetConverter/God_city/{Materials,Textures}/*.uasset (material instances and texture packages)
  writes Assets/3D/GodCity/*.glb + sizes.json                   (re-pivoted: x/z centred, base at y=0; textures embedded)
Textures: 512px JPEG (PNG + alphaMode MASK for opacity-masked foliage). Stone textures are brightened toward white marble (GAIN)."""
import sys, os, io, json, struct, glob
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(PROJ, 'UassetConverter'))
import numpy as np
from PIL import Image
from uasset_to_glb.materials import MaterialLibrary
from uasset_to_glb.texture import read_texture

ROOT = os.path.join(PROJ, 'UassetConverter')
lib = MaterialLibrary(ROOT + '/God_city')
_tex = {}
GAIN = {'T_Greek_ground_basecolor': (1.55, 1.5, 1.4), 'T_God_city_Trimsheet_basecolor': (1.3, 1.28, 1.22)}
def tex(name, mask=False, size=512):
    k = (name, mask, size)
    if k in _tex: return _tex[k]
    p = lib.find(name)
    try:
        png, w, h = read_texture(p)
    except Exception as e:
        print('  tex fail', name, e); _tex[k] = None; return None
    im = Image.open(io.BytesIO(png)).convert('RGBA' if False else 'RGB') if name in GAIN else Image.open(io.BytesIO(png))
    if name in GAIN:                      # brighten the dull stone toward the reference's white-cream marble
        gr, gg, gb = GAIN[name]
        a = np.asarray(im, np.float32); a = a * np.array([gr, gg, gb], np.float32)
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    return _tex.setdefault(k, im)

def enc(im, alpha=False, size=512):
    im = im.copy()
    if max(im.size) > size: im = im.resize((size, size * im.size[1] // im.size[0]) if im.size[0] >= im.size[1] else (size * im.size[0] // im.size[1], size), Image.LANCZOS)
    b = io.BytesIO()
    if alpha: im.convert('RGBA').save(b, 'PNG', optimize=True)
    else: im.convert('RGB').save(b, 'JPEG', quality=84)
    return b.getvalue()

def load(path):
    b = open(path, 'rb').read()
    l = struct.unpack('<I', b[12:16])[0]
    j = json.loads(b[20:20 + l])
    off = 20 + l + 8
    return j, b[off:]

def acc(j, bin, i):
    a = j['accessors'][i]; bv = j['bufferViews'][a['bufferView']]
    n = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3}[a['type']]
    dt = {5126: '<f4', 5125: '<u4', 5123: '<u2'}[a['componentType']]
    o = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    return np.frombuffer(bin, dt, a['count'] * n, o).reshape(-1, n) if n > 1 else np.frombuffer(bin, dt, a['count'], o)

def tex_for(mi_name):
    m = lib.material(mi_name)
    if m is None: return None
    bc = m.base_color
    if not bc and 'bush' in mi_name.lower(): bc = 'T_branch_D'; m.opacity_override = 'T_branch_O'
    return dict(base=bc, op=m.opacity or getattr(m,'opacity_override',None), tint=m.tint, mi=mi_name)

def convert(src, dst, uvset=0, size=512):
    j, bin = load(src)
    mesh = j['meshes'][0]
    mname = mesh['name']
    pos_all = []
    prims = []
    for p in mesh['primitives']:
        pos = acc(j, bin, p['attributes']['POSITION']).astype('f4')
        nor = acc(j, bin, p['attributes']['NORMAL']).astype('f4') if 'NORMAL' in p['attributes'] else None
        uvk = 'TEXCOORD_%d' % uvset
        uv = acc(j, bin, p['attributes'][uvk]).astype('f4') if uvk in p['attributes'] else np.zeros((len(pos), 2), 'f4')
        idx = acc(j, bin, p['indices']).astype('u4')
        prims.append((pos, nor, uv, idx, p.get('material', 0)))
        pos_all.append(pos)
    P = np.concatenate(pos_all)
    mn, mx = P.min(0), P.max(0)
    cx, cz, by = (mn[0] + mx[0]) / 2, (mn[2] + mx[2]) / 2, mn[1]
    out = bytearray(); bvs = []; accs = []; imgs = []; texs = []; mats = []; prm = []
    def addbv(data, target=None):
        while len(out) % 4: out.append(0)
        bvs.append(dict(buffer=0, byteOffset=len(out), byteLength=len(data), **({'target': target} if target else {})))
        out.extend(data); return len(bvs) - 1
    imgcache = {}
    def addimg(key, data, mime):
        if key in imgcache: return imgcache[key]
        bv = addbv(data)
        imgs.append(dict(bufferView=bv, mimeType=mime)); texs.append(dict(source=len(imgs) - 1))
        imgcache[key] = len(texs) - 1; return imgcache[key]
    matcache = {}
    info = {}
    for (pos, nor, uv, idx, mi) in prims:
        mnm = j['materials'][mi]['name']
        base = mnm[:-(len(mname) + 1)] if mnm.endswith('_' + mname) else mnm
        if mi not in matcache:
            t = tex_for(base)
            pbr = dict(metallicFactor=0.0, roughnessFactor=0.85)
            mat = dict(name=base, pbrMetallicRoughness=pbr)
            fac = [1, 1, 1, 1]
            if t and t['base']:
                im = tex(t['base'])
                if im is not None:
                    opn = tex(t['op']) if t['op'] else None
                    if opn is not None:
                        a = opn.convert('L').resize(im.size)
                        r = im.convert('RGB'); r.putalpha(a); data = enc(r, True, size); mime = 'image/png'
                        mat['alphaMode'] = 'MASK'; mat['alphaCutoff'] = 0.4; mat['doubleSided'] = True
                    else:
                        data = enc(im, False, size); mime = 'image/jpeg'
                    pbr['baseColorTexture'] = dict(index=addimg((t['base'], bool(opn)), data, mime))
                if t['tint'] and not t['base'].lower().startswith('t_god'):
                    pass
                if t['tint'] and any(v < 0.98 for v in t['tint']) and 'bush' in base.lower():
                    fac = list(t['tint']) + [1]
            else:
                fac = [0.8, 0.78, 0.72, 1]
            if t: info[base] = t['base']
            pbr['baseColorFactor'] = fac
            matcache[mi] = len(mats); mats.append(mat)
        p2 = pos - np.array([cx, by, cz], 'f4')
        a_pos = addbv(p2.astype('<f4').tobytes(), 34962); accs.append(dict(bufferView=a_pos, componentType=5126, count=len(p2), type='VEC3', min=p2.min(0).tolist(), max=p2.max(0).tolist()))
        at = {'POSITION': len(accs) - 1}
        if nor is not None:
            b = addbv(nor.astype('<f4').tobytes(), 34962); accs.append(dict(bufferView=b, componentType=5126, count=len(nor), type='VEC3')); at['NORMAL'] = len(accs) - 1
        b = addbv(uv.astype('<f4').tobytes(), 34962); accs.append(dict(bufferView=b, componentType=5126, count=len(uv), type='VEC2')); at['TEXCOORD_0'] = len(accs) - 1
        b = addbv(idx.astype('<u4').tobytes(), 34963); accs.append(dict(bufferView=b, componentType=5125, count=len(idx), type='SCALAR'))
        prm.append(dict(attributes=at, indices=len(accs) - 1, material=matcache[mi], mode=4))
    g = dict(asset=dict(version='2.0', generator='godcity-build'), scene=0, scenes=[dict(nodes=[0])], nodes=[dict(name=mname, mesh=0)],
             meshes=[dict(name=mname, primitives=prm)], materials=mats, accessors=accs, bufferViews=bvs, buffers=[dict(byteLength=len(out))])
    if imgs: g['images'] = imgs; g['textures'] = texs; g['samplers'] = [dict(magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497)]
    for m in mats:
        t = m['pbrMetallicRoughness'].get('baseColorTexture')
        if t: t['index'] = t['index']
    for t in g.get('textures', []): t['sampler'] = 0
    while len(out) % 4: out.append(0)
    g['buffers'][0]['byteLength'] = len(out)
    js = json.dumps(g, separators=(',', ':')).encode()
    while len(js) % 4: js += b' '
    blob = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(out)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(out), 0x004E4942) + bytes(out)
    open(dst, 'wb').write(blob)
    return dict(size=[round(float(mx[0] - mn[0]), 3), round(float(mx[1] - mn[1]), 3), round(float(mx[2] - mn[2]), 3)], mats=info, bytes=len(blob))

if __name__ == '__main__':
    srcdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'glb_output', 'God_city', 'Meshes')
    dstdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(PROJ, 'Assets', '3D', 'GodCity')
    os.makedirs(dstdir, exist_ok=True)
    sizes = {}
    for f in sorted(glob.glob(srcdir + '/**/*.glb', recursive=True)):
        n = os.path.basename(f)
        try:
            r = convert(f, os.path.join(dstdir, n))
            sizes[n[:-4]] = r['size']; print(n, r['size'], r['bytes'] // 1024, 'KB', r['mats'])
        except Exception as e:
            import traceback; traceback.print_exc(); print('FAIL', n, e)
    json.dump(sizes, open(os.path.join(dstdir, 'sizes.json'), 'w'), indent=0)

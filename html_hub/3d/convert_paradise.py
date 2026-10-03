"""Textured game GLBs for the Paradise_island kit (UE5): UassetConverter/glb_output/Paradise_island/Meshes -> Assets/3D/Paradise/.
Run from anywhere:  python html_hub/3d/convert_paradise.py     (same approach as convert_godcity.py, which supplies the GLB helpers)
Materials whose textures are not readable fall back to a flat colour (FALLBACK); re-run once the texture packages are available.
Then run gen_island_meshes.py (island + ocean) and make_island.py."""
import sys, os, io, json, struct, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
from PIL import Image
import convert_godcity as B
from convert_godcity import load, acc, enc
from uasset_to_glb.materials import MaterialLibrary
from uasset_to_glb.texture import read_texture
ROOT = B.ROOT
lib = MaterialLibrary(ROOT + '/Paradise_island')
# flat colours used when a texture package is not available (sampled from the Unreal look)
FALLBACK = {'MI_wood': (.52, .36, .22), 'MI_wood_plank': (.62, .45, .28), 'MI_wood_plank1': (.72, .5, .3), 'MI_wood_plank_floor': (.55, .4, .26),
            'MI_wall': (.93, .87, .74), 'MI_modules': (.86, .78, .64), 'MI_hay_roof': (.66, .5, .24), 'MI_bridge': (.5, .36, .22),
            'MI_tree_bark': (.46, .34, .22), 'MI_tree_bark_02': (.4, .3, .2), 'MI_rock_01': (.58, .55, .5), 'MI_rock_01_B': (.5, .55, .35), 'MI_rock_02': (.55, .52, .47),
            'MI_small_boat': (.62, .42, .26), 'MI_interior_props': (.62, .46, .3), 'MI_lamp': (.9, .78, .45), 'MI_cliff': (.6, .56, .5), 'MI_curtain': (.9, .85, .8)}
_cache = {}
def texim(name):
    if name in _cache: return _cache[name]
    p = lib.find(name); im = None
    if p:
        try:
            png, w, h = read_texture(p); im = Image.open(io.BytesIO(png))
        except Exception as e: print('  tex fail', name, e)
    _cache[name] = im; return im
def tinted(im, tint):
    a = np.asarray(im.convert('RGB'), np.float32) * np.array(tint[:3], np.float32)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

def convert(src, dst, size=512):
    j, bin = load(src); mesh = j['meshes'][0]; mname = mesh['name']
    prims = []; allp = []
    for p in mesh['primitives']:
        pos = acc(j, bin, p['attributes']['POSITION']).astype('f4')
        nor = acc(j, bin, p['attributes']['NORMAL']).astype('f4') if 'NORMAL' in p['attributes'] else None
        uv = acc(j, bin, p['attributes']['TEXCOORD_0']).astype('f4') if 'TEXCOORD_0' in p['attributes'] else np.zeros((len(pos), 2), 'f4')
        idx = acc(j, bin, p['indices']).astype('u4'); prims.append((pos, nor, uv, idx, p.get('material', 0))); allp.append(pos)
    P = np.concatenate(allp); mn, mx = P.min(0), P.max(0); cx, cz, by = (mn[0] + mx[0]) / 2, (mn[2] + mx[2]) / 2, mn[1]
    out = bytearray(); bvs = []; accs = []; imgs = []; texs = []; mats = []; prm = []
    def addbv(data, target=None):
        while len(out) % 4: out.append(0)
        bvs.append(dict(buffer=0, byteOffset=len(out), byteLength=len(data), **({'target': target} if target else {}))); out.extend(data); return len(bvs) - 1
    icache = {}; mcache = {}; info = {}
    for (pos, nor, uv, idx, mi) in prims:
        mnm = j['materials'][mi]['name']; base = mnm[:-(len(mname) + 1)] if mnm.endswith('_' + mname) else mnm
        if mi not in mcache:
            m = lib.material(base); pbr = dict(metallicFactor=0.0, roughnessFactor=0.9); mat = dict(name=base, pbrMetallicRoughness=pbr); fac = [.75, .75, .75, 1]
            im = texim(m.base_color) if (m and m.base_color) else None
            if im is not None:
                tint = [min(v, 4.0) for v in (m.tint or [1, 1, 1])]
                opn = texim(m.opacity) if m.opacity and 'Opacity' in ''.join(m.textures.keys()) + 'Opacity' else None
                key = (m.base_color, m.opacity if opn is not None else None, tuple(round(v, 3) for v in tint))
                if key not in icache:
                    rgb = tinted(im, tint) if 'leaf' in m.base_color.lower() or 'veget' in m.base_color.lower() or tint != [1, 1, 1] else im.convert('RGB')
                    if opn is not None:
                        a = opn.convert('L').resize(rgb.size); rgb.putalpha(a); data, mime = enc(rgb, True, size), 'image/png'
                    else: data, mime = enc(rgb, False, size), 'image/jpeg'
                    bv = addbv(data); imgs.append(dict(bufferView=bv, mimeType=mime)); texs.append(dict(source=len(imgs) - 1, sampler=0)); icache[key] = len(texs) - 1
                pbr['baseColorTexture'] = dict(index=icache[key])
                if opn is not None: mat['alphaMode'] = 'MASK'; mat['alphaCutoff'] = 0.45; mat['doubleSided'] = True
                fac = [1, 1, 1, 1]; info[base] = 'tex:' + m.base_color
            else:
                fac = list(FALLBACK.get(base, (.5, .5, .5))) + [1]; info[base] = 'flat'
                if m and m.opacity: mat['doubleSided'] = True
            pbr['baseColorFactor'] = fac; mcache[mi] = len(mats); mats.append(mat)
        p2 = pos - np.array([cx, by, cz], 'f4')
        b = addbv(p2.astype('<f4').tobytes(), 34962); accs.append(dict(bufferView=b, componentType=5126, count=len(p2), type='VEC3', min=p2.min(0).tolist(), max=p2.max(0).tolist())); at = {'POSITION': len(accs) - 1}
        if nor is not None: b = addbv(nor.astype('<f4').tobytes(), 34962); accs.append(dict(bufferView=b, componentType=5126, count=len(nor), type='VEC3')); at['NORMAL'] = len(accs) - 1
        b = addbv(uv.astype('<f4').tobytes(), 34962); accs.append(dict(bufferView=b, componentType=5126, count=len(uv), type='VEC2')); at['TEXCOORD_0'] = len(accs) - 1
        b = addbv(idx.astype('<u4').tobytes(), 34963); accs.append(dict(bufferView=b, componentType=5125, count=len(idx), type='SCALAR'))
        prm.append(dict(attributes=at, indices=len(accs) - 1, material=mcache[mi], mode=4))
    while len(out) % 4: out.append(0)
    g = dict(asset=dict(version='2.0', generator='paradise-build'), scene=0, scenes=[dict(nodes=[0])], nodes=[dict(name=mname, mesh=0)], meshes=[dict(name=mname, primitives=prm)],
             materials=mats, accessors=accs, bufferViews=bvs, buffers=[dict(byteLength=len(out))])
    if imgs: g['images'] = imgs; g['textures'] = texs; g['samplers'] = [dict(magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497)]
    js = json.dumps(g, separators=(',', ':')).encode()
    while len(js) % 4: js += b' '
    blob = struct.pack('<III', 0x46546C67, 2, 28 + len(js) + len(out)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(out), 0x004E4942) + bytes(out)
    open(dst, 'wb').write(blob)
    return dict(size=[round(float(v), 3) for v in (mx - mn)], mats=info, bytes=len(blob))

if __name__ == '__main__':
    srcdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'glb_output', 'Paradise_island', 'Meshes')
    dstdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(B.PROJ, 'Assets', '3D', 'Paradise'); os.makedirs(dstdir, exist_ok=True); sizes = {}
    for f in sorted(glob.glob(srcdir + '/**/*.glb', recursive=True)):
        n = os.path.basename(f)
        if 'SkySphere' in n or 'high_cliff' in n: continue
        try:
            r = convert(f, os.path.join(dstdir, n)); sizes[n[:-4]] = r['size']; print(n, r['size'], r['bytes'] // 1024, 'KB', r['mats'])
        except Exception as e:
            import traceback; traceback.print_exc()
    json.dump(sizes, open(os.path.join(dstdir, 'sizes.json'), 'w'), indent=0)

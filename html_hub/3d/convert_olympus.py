"""Converts the Unreal-exported Olympus .gltf+.bin+PNG meshes into compact self-contained GLBs the game's loader can read.
Run: python convert_olympus.py <Olympus dir> <out dir>
 - uses UV set 1 (Unreal's texCoord:1) as TEXCOORD_0 and bakes KHR_texture_transform into it
 - bakes ambient-occlusion into base colour, downsizes to 1024 JPEG, embeds it
 - re-pivots every mesh to centre x/z with its base on y=0; writes sizes.json"""
import json, struct, sys, os, io, glob
import numpy as np
from PIL import Image
SRC, OUT = sys.argv[1], sys.argv[2]; os.makedirs(OUT, exist_ok=True)
CT = {5121: np.uint8, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}; NC = dict(SCALAR=1, VEC2=2, VEC3=3, VEC4=4)
def acc(g, buf, i):
    a = g['accessors'][i]; v = g['bufferViews'][a['bufferView']]; n = NC[a['type']]
    off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
    return np.frombuffer(buf, CT[a['componentType']], a['count'] * n, off).reshape(a['count'], n)
def tex(g, name_idx, ao_idx, cache):
    key = (name_idx, ao_idx)
    if key in cache: return cache[key]
    uri = g['images'][g['textures'][name_idx]['source']]['uri']
    im = Image.open(os.path.join(SRC, uri)).convert('RGB')
    if ao_idx is not None:
        ao = Image.open(os.path.join(SRC, g['images'][g['textures'][ao_idx]['source']]['uri'])).convert('L').resize(im.size)
        im = Image.fromarray((np.asarray(im, np.float32) * (0.55 + 0.45 * np.asarray(ao, np.float32)[..., None] / 255)).astype(np.uint8))
    im = im.resize((1024, 1024), Image.LANCZOS) if im.size[0] > 1024 else im
    b = io.BytesIO(); im.save(b, 'JPEG', quality=86); cache[key] = b.getvalue(); return cache[key]
sizes = {}
for gf in sorted(glob.glob(os.path.join(SRC, 'SM_*.gltf'))):
    name = os.path.basename(gf)[:-5]; g = json.load(open(gf)); buf = open(os.path.join(SRC, g['buffers'][0]['uri']), 'rb').read()
    prims = []; allp = []
    for p in g['meshes'][0]['primitives']:
        pos = acc(g, buf, p['attributes']['POSITION']).astype(np.float32); allp.append(pos)
    allp = np.concatenate(allp); mn, mx = allp.min(0), allp.max(0)
    shift = np.array([-(mn[0] + mx[0]) / 2, -mn[1], -(mn[2] + mx[2]) / 2], np.float32)
    bin_ = bytearray(); views = []; accs = []; mats = []; texs = []; imgs = []; meshprims = []; cache = {}
    def add(data, target=None):
        while len(bin_) % 4: bin_.append(0)
        views.append(dict(buffer=0, byteOffset=len(bin_), byteLength=len(data), **({'target': target} if target else {}))); bin_.extend(data); return len(views) - 1
    for p in g['meshes'][0]['primitives']:
        pos = acc(g, buf, p['attributes']['POSITION']).astype(np.float32) + shift
        nrm = acc(g, buf, p['attributes']['NORMAL']).astype(np.float32)
        uv = acc(g, buf, p['attributes']['TEXCOORD_1']).astype(np.float32).copy()
        idx = acc(g, buf, p['indices']).astype(np.uint32)
        m = g['materials'][p['material']]; bc = m['pbrMetallicRoughness']['baseColorTexture']
        t = bc.get('extensions', {}).get('KHR_texture_transform')
        if t: uv = uv * np.array(t.get('scale', [1, 1]), np.float32) + np.array(t.get('offset', [0, 0]), np.float32)
        ao = m.get('occlusionTexture', {}).get('index')
        jpg = tex(g, bc['index'], ao, cache)
        iv = add(jpg); imgs.append(dict(bufferView=iv, mimeType='image/jpeg')); texs.append(dict(source=len(imgs) - 1, sampler=0))
        mats.append(dict(name=m['name'], pbrMetallicRoughness=dict(baseColorTexture=dict(index=len(texs) - 1), metallicFactor=0, roughnessFactor=0.9), doubleSided=True))
        at = {}
        for key, arr, ct, ty in (('POSITION', pos, 5126, 'VEC3'), ('NORMAL', nrm, 5126, 'VEC3'), ('TEXCOORD_0', uv, 5126, 'VEC2')):
            v = add(arr.astype(np.float32).tobytes(), 34962)
            a = dict(bufferView=v, componentType=ct, count=len(arr), type=ty)
            if key == 'POSITION': a['min'] = arr.min(0).tolist(); a['max'] = arr.max(0).tolist()
            accs.append(a); at[key] = len(accs) - 1
        v = add(idx.tobytes(), 34963); accs.append(dict(bufferView=v, componentType=5125, count=len(idx), type='SCALAR'))
        meshprims.append(dict(attributes=at, indices=len(accs) - 1, material=len(mats) - 1))
    while len(bin_) % 4: bin_.append(0)
    J = dict(asset=dict(version='2.0', generator='convert_olympus.py'), scene=0, scenes=[dict(nodes=[0])], nodes=[dict(mesh=0, name=name)], meshes=[dict(name=name, primitives=meshprims)],
             materials=mats, textures=texs, images=imgs, samplers=[dict(magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497)], accessors=accs, bufferViews=views, buffers=[dict(byteLength=len(bin_))])
    jb = json.dumps(J, separators=(',', ':')).encode(); jb += b' ' * (-len(jb) % 4)
    glb = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(jb) + 8 + len(bin_)) + struct.pack('<II', len(jb), 0x4E4F534A) + jb + struct.pack('<II', len(bin_), 0x004E4942) + bytes(bin_)
    open(os.path.join(OUT, name + '.glb'), 'wb').write(glb)
    sizes[name] = dict(w=float(mx[0] - mn[0]), h=float(mx[1] - mn[1]), d=float(mx[2] - mn[2]), kb=len(glb) // 1024)
    print(name, sizes[name])
json.dump(sizes, open(os.path.join(OUT, 'sizes.json'), 'w'), indent=1)

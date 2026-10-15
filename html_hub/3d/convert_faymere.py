"""Faymere River Village (Fab, FBX) -> one textured game GLB per mesh, for the 3D editor.

  python html_hub/3d/convert_faymere.py [path\\to\\Village2.fbx] [dstdir]

Steps (all local, nothing is uploaded):
  1. runs FBX2glTF (https://github.com/facebookincubator/FBX2glTF, official release; downloaded to tools/ if missing) -> one big .glb
  2. splits that .glb into one GLB per unique mesh: placement rotation/translation dropped, scale kept, pivot at the x/z centre of the
     bounding box with the base on y = 0, textures re-encoded at <= 512 px (JPEG, or PNG when the material has transparency),
     placeholder textures (tiny files that carry no image) replaced by the material's flat colour
  3. writes sizes.json ({name: [x, y, z] metres}) next to them, like the other kits (Assets/3D/<Kit>/).
Needs Python 3 with numpy and Pillow.  Options:  --glb big.glb (skip step 1)   --dst DIR   --max-px 512   --min-tris 4   --scale S (extra scale)
"""
import argparse, hashlib, io, json, os, re, struct, subprocess, sys, urllib.request
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, '..', '..'))
DEFAULT_FBX = r'C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\FabLibrary\Faymere_River_Village_A_Forgotten_Medieval_Gem-6e579cff\fbx\fbx_whisperwind_village__extracted\FBX Whisperwind Village 5.5\Village2.fbx'
EXE_URL = {'nt': 'https://github.com/facebookincubator/FBX2glTF/releases/download/v0.9.7/FBX2glTF-windows-x64.exe',
           'posix': 'https://github.com/facebookincubator/FBX2glTF/releases/download/v0.9.7/FBX2glTF-linux-x64'}
COMP = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2), 5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


# ----------------------------------------------------------------------------- glb reading
def load_glb(path):
    d = open(path, 'rb').read()
    magic, ver, total = struct.unpack_from('<III', d, 0)
    if magic != 0x46546C67:
        raise SystemExit('not a .glb: ' + path)
    o, js, bn = 12, None, None
    while o + 8 <= len(d):
        n, t = struct.unpack_from('<II', d, o); body = d[o + 8:o + 8 + n]
        if t == 0x4E4F534A: js = json.loads(body.decode('utf-8'))
        elif t == 0x004E4942 and bn is None: bn = body
        o += 8 + n
    return js, memoryview(bn) if bn is not None else memoryview(b'')


def accessor(j, bn, idx):
    a = j['accessors'][idx]; fmt, sz = COMP[a['componentType']]; nc = NCOMP[a['type']]; n = a['count']
    dt = np.dtype('<' + fmt)
    if 'bufferView' not in a:
        arr = np.zeros((n, nc), dt)
    else:
        bv = j['bufferViews'][a['bufferView']]; off = bv.get('byteOffset', 0) + a.get('byteOffset', 0); stride = bv.get('byteStride') or sz * nc
        if stride == sz * nc:
            arr = np.frombuffer(bn, dt, n * nc, off).reshape(n, nc)
        else:
            raw = np.frombuffer(bn, np.uint8, (n - 1) * stride + sz * nc, off)
            arr = np.lib.stride_tricks.as_strided(raw, (n, sz * nc), (stride, 1)).copy().view(dt).reshape(n, nc)
    if a.get('normalized'):
        arr = arr.astype(np.float32) / float(np.iinfo(dt).max)
    return arr


def node_matrix(nd):
    if 'matrix' in nd:
        return np.array(nd['matrix'], float).reshape(4, 4).T
    m = np.eye(4); t = nd.get('translation', [0, 0, 0]); r = nd.get('rotation', [0, 0, 0, 1]); s = nd.get('scale', [1, 1, 1])
    x, y, z, w = r
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    m[:3, :3] = R * np.array(s)[None, :]; m[:3, 3] = t
    return m


def mesh_instances(j):
    """yield (node_name, mesh_index, world 4x4) for every node that carries a mesh"""
    nodes = j.get('nodes', []); out = []
    def walk(i, parent):
        nd = nodes[i]; w = parent @ node_matrix(nd)
        if 'mesh' in nd: out.append((nd.get('name') or 'mesh', nd['mesh'], w))
        for c in nd.get('children', []): walk(c, w)
    scenes = j.get('scenes') or [{'nodes': list(range(len(nodes)))}]
    for r in scenes[j.get('scene', 0)].get('nodes', []): walk(r, np.eye(4))
    return out


# ----------------------------------------------------------------------------- textures
_img_cache = {}


def image_for(j, bn, tex_idx, max_px, want_alpha):
    """-> (PIL image or None, flat colour (r,g,b) or None).  None image = placeholder / unreadable."""
    key = (tex_idx, want_alpha)
    if key in _img_cache: return _img_cache[key]
    res = (None, None)
    try:
        src = j['textures'][tex_idx]['source']; im = j['images'][src]
        if 'bufferView' in im:
            bv = j['bufferViews'][im['bufferView']]; raw = bytes(bn[bv.get('byteOffset', 0):bv.get('byteOffset', 0) + bv['byteLength']])
        else:
            raw = None
        if raw is not None:
            pil = Image.open(io.BytesIO(raw)); pil.load()
            if pil.width > 2 or pil.height > 2:
                pil = pil.convert('RGBA' if want_alpha else 'RGB')
                if max(pil.size) > max_px:
                    f = max_px / max(pil.size); pil = pil.resize((max(1, round(pil.width * f)), max(1, round(pil.height * f))), Image.LANCZOS)
                res = (pil, None)
            else:
                px = pil.convert('RGB').getpixel((0, 0))
                if sum(px) > 30: res = (None, tuple(c / 255 for c in px))      # a real flat colour; pure black = empty placeholder -> default colour
    except Exception as e:
        print('    texture %s unreadable: %s' % (tex_idx, e))
    _img_cache[key] = res
    return res


def encode(pil, alpha):
    b = io.BytesIO()
    if alpha: pil.save(b, 'PNG', optimize=True); return b.getvalue(), 'image/png'
    pil.convert('RGB').save(b, 'JPEG', quality=85); return b.getvalue(), 'image/jpeg'


# ----------------------------------------------------------------------------- glb writing
def write_glb(path, prims, materials, images):
    """prims: [(pos Nx3 f4, nor Nx3 f4|None, uv Nx2 f4, idx 1-D u4, material index)]; materials: dicts; images: [(bytes, mime)]"""
    out = bytearray(); views = []; accs = []
    def add(data, target=None):
        while len(out) % 4: out.append(0)
        v = {'buffer': 0, 'byteOffset': len(out), 'byteLength': len(data)}
        if target: v['target'] = target
        out.extend(data); views.append(v); return len(views) - 1
    img_j = [dict(bufferView=add(b), mimeType=m) for b, m in images]
    mprims = []
    for pos, nor, uv, idx, mi in prims:
        at = {}
        accs.append({'bufferView': add(pos.astype('<f4').tobytes(), 34962), 'componentType': 5126, 'count': len(pos), 'type': 'VEC3', 'min': pos.min(0).tolist(), 'max': pos.max(0).tolist()}); at['POSITION'] = len(accs) - 1
        if nor is not None:
            accs.append({'bufferView': add(nor.astype('<f4').tobytes(), 34962), 'componentType': 5126, 'count': len(nor), 'type': 'VEC3'}); at['NORMAL'] = len(accs) - 1
        accs.append({'bufferView': add(uv.astype('<f4').tobytes(), 34962), 'componentType': 5126, 'count': len(uv), 'type': 'VEC2'}); at['TEXCOORD_0'] = len(accs) - 1
        accs.append({'bufferView': add(idx.astype('<u4').tobytes(), 34963), 'componentType': 5125, 'count': len(idx), 'type': 'SCALAR'}); mprims.append({'attributes': at, 'indices': len(accs) - 1, 'material': mi, 'mode': 4})
    while len(out) % 4: out.append(0)
    g = {'asset': {'version': '2.0', 'generator': 'convert_faymere.py'}, 'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}], 'meshes': [{'primitives': mprims}],
         'materials': materials, 'accessors': accs, 'bufferViews': views, 'buffers': [{'byteLength': len(out)}]}
    if images:
        g['images'] = img_j; g['samplers'] = [{'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497}]
        g['textures'] = [{'source': i, 'sampler': 0} for i in range(len(images))]
    js = json.dumps(g, separators=(',', ':')).encode()
    while len(js) % 4: js += b' '
    with open(path, 'wb') as f:
        f.write(struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(out))); f.write(struct.pack('<II', len(js), 0x4E4F534A)); f.write(js)
        f.write(struct.pack('<II', len(out), 0x004E4942)); f.write(bytes(out))


# ----------------------------------------------------------------------------- main
def fbx2glb(fbx, out_glb):
    exe = os.path.join(PROJ, 'tools', 'FBX2glTF' + ('.exe' if os.name == 'nt' else ''))
    if not os.path.exists(exe):
        os.makedirs(os.path.dirname(exe), exist_ok=True); url = EXE_URL['nt' if os.name == 'nt' else 'posix']
        print('downloading FBX2glTF 0.9.7 from', url); urllib.request.urlretrieve(url, exe); os.chmod(exe, 0o755)
    base = out_glb[:-4]
    cmd = [exe, '--binary', '--pbr-metallic-roughness', '--long-indices', 'auto', '--compute-normals', 'missing', '-i', fbx, '-o', base]
    print('running:', ' '.join('"%s"' % c if ' ' in c else c for c in cmd)); r = subprocess.run(cmd)
    if r.returncode != 0 or not os.path.exists(out_glb): raise SystemExit('FBX2glTF failed (code %s)' % r.returncode)


def safe(n):
    n = re.sub(r'[^A-Za-z0-9_.-]+', '_', n).strip('_.') or 'mesh'
    return n


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('fbx', nargs='?', default=DEFAULT_FBX); ap.add_argument('dst_pos', nargs='?', default=os.path.join(PROJ, 'Assets', '3D', 'Faymere'))
    ap.add_argument('--glb'); ap.add_argument('--dst'); ap.add_argument('--max-px', type=int, default=512); ap.add_argument('--min-tris', type=int, default=4); ap.add_argument('--scale', type=float, default=1.0)
    a = ap.parse_args(); a.dst = a.dst or a.dst_pos; os.makedirs(a.dst, exist_ok=True)
    glb = a.glb
    if not glb:
        glb = os.path.join(a.dst, '_village_all.glb'); fbx2glb(a.fbx, glb)
    print('reading', glb); j, bn = load_glb(glb)
    inst = mesh_instances(j); seen_mesh = {}; seen_hash = {}; used = set(); sizes = {}
    for nm, mi, w in inst:
        if mi in seen_mesh: continue
        seen_mesh[mi] = (nm, w)
    for mi in range(len(j.get('meshes', []))):
        if mi not in seen_mesh: seen_mesh[mi] = (j['meshes'][mi].get('name') or 'mesh%d' % mi, np.eye(4))
    print('%d unique meshes (%d placed instances)' % (len(seen_mesh), len(inst)))
    for mi, (nm, w) in sorted(seen_mesh.items()):
        mesh = j['meshes'][mi]; name = safe(mesh.get('name') or nm)
        S = np.linalg.norm(w[:3, :3], axis=0); S = np.where(S < 1e-9, 1, S) * a.scale
        prims, mats, imgs, mcache, icache = [], [], [], {}, {}
        for p in mesh['primitives']:
            if p.get('mode', 4) != 4 or 'POSITION' not in p['attributes']: continue
            pos = accessor(j, bn, p['attributes']['POSITION']).astype(np.float32)
            idx = accessor(j, bn, p['indices']).reshape(-1).astype(np.uint32) if 'indices' in p else np.arange(len(pos), dtype=np.uint32)
            if len(idx) // 3 < 1: continue
            nor = accessor(j, bn, p['attributes']['NORMAL']).astype(np.float32) if 'NORMAL' in p['attributes'] else None
            uv = accessor(j, bn, p['attributes']['TEXCOORD_0']).astype(np.float32) if 'TEXCOORD_0' in p['attributes'] else np.zeros((len(pos), 2), np.float32)
            gm = p.get('material'); src = j['materials'][gm] if gm is not None else {}
            if gm not in mcache:
                pbr = src.get('pbrMetallicRoughness', {}); fac = list(pbr.get('baseColorFactor', [1, 1, 1, 1]))
                mode = src.get('alphaMode', 'OPAQUE'); alpha = mode in ('MASK', 'BLEND')
                m = {'name': src.get('name', 'mat'), 'pbrMetallicRoughness': {'metallicFactor': 0.0, 'roughnessFactor': 0.9, 'baseColorFactor': fac}}
                bt = pbr.get('baseColorTexture')
                if bt is not None:
                    pil, flat = image_for(j, bn, bt['index'], a.max_px, alpha)
                    if pil is not None:
                        k = (bt['index'], alpha)
                        if k not in icache: icache[k] = len(imgs); imgs.append(encode(pil, alpha))
                        m['pbrMetallicRoughness']['baseColorTexture'] = {'index': icache[k]}; m['pbrMetallicRoughness']['baseColorFactor'] = [1, 1, 1, fac[3]]
                    elif flat is not None:
                        m['pbrMetallicRoughness']['baseColorFactor'] = [flat[0] * fac[0], flat[1] * fac[1], flat[2] * fac[2], fac[3]]
                    else:
                        m['pbrMetallicRoughness']['baseColorFactor'] = [.55, .5, .45, fac[3]]
                if alpha: m['alphaMode'] = 'MASK' if mode == 'MASK' else 'BLEND'; m['alphaCutoff'] = src.get('alphaCutoff', 0.45); m['doubleSided'] = True
                if src.get('doubleSided'): m['doubleSided'] = True
                mcache[gm] = len(mats); mats.append(m)
            prims.append([pos * S.astype(np.float32), nor, uv, idx, mcache[gm]])
        if not prims or sum(len(p[3]) for p in prims) // 3 < a.min_tris: continue
        allp = np.concatenate([p[0] for p in prims]); mn, mx = allp.min(0), allp.max(0)
        shift = np.array([(mn[0] + mx[0]) / 2, mn[1], (mn[2] + mx[2]) / 2], np.float32)
        for p in prims: p[0] = p[0] - shift
        h = hashlib.md5(np.round(np.sort(allp[:, 0])[::max(1, len(allp) // 512)], 3).tobytes() + str(len(allp)).encode()).hexdigest()
        if h in seen_hash: print('  skip duplicate', name, '=', seen_hash[h]); continue
        base = name; k = 2
        while name.lower() in used: name = '%s_%d' % (base, k); k += 1
        used.add(name.lower()); seen_hash[h] = name
        write_glb(os.path.join(a.dst, name + '.glb'), [tuple(p) for p in prims], mats, imgs)
        sizes[name] = [round(float(v), 3) for v in (mx - mn)]
        print('  %s %s %d tris %d tex' % (name, sizes[name], sum(len(p[3]) for p in prims) // 3, len(imgs)))
    json.dump(sizes, open(os.path.join(a.dst, 'sizes.json'), 'w'), indent=0)
    print('wrote %d GLBs + sizes.json to %s' % (len(sizes), a.dst))
    if not a.glb and os.path.exists(glb):
        print('(the combined %s can be deleted)' % glb)


if __name__ == '__main__':
    main()

"""Textured game GLBs for the Hidden_shrine kit (UE5.2): UassetConverter/glb_output/Hidden_shrine/Meshes -> Assets/3D/HiddenShrine/.
Reuses convert_paradise.convert with the Hidden_shrine material library. Run:  python html_hub/3d/convert_hiddenshrine.py [srcdir] [dstdir]
Geometry first:  python -m uasset_to_glb Hidden_shrine/Meshes glb_output/Hidden_shrine/Meshes --recursive   (run inside UassetConverter)"""
import sys, os, json, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import convert_paradise as P
from uasset_to_glb.materials import MaterialLibrary
ROOT = P.ROOT
P.lib = MaterialLibrary(ROOT + '/Hidden_shrine'); P._cache.clear()
P.FALLBACK = {'MI_rock_01': (.55, .5, .45), 'MI_rock_02': (.5, .46, .42), 'MI_window': (.35, .5, .6), 'MI_water_02': (.15, .35, .45),
              'MI_petals': (.9, .55, .65), 'MI_tree_bark': (.4, .3, .22), 'MI_wood': (.5, .36, .22)}
SKIP = ()
if __name__ == '__main__':
    srcdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'glb_output', 'Hidden_shrine', 'Meshes')
    dstdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(P.B.PROJ, 'Assets', '3D', 'HiddenShrine'); os.makedirs(dstdir, exist_ok=True); sizes = {}
    for f in sorted(glob.glob(srcdir + '/**/*.glb', recursive=True)):
        n = os.path.basename(f)
        if any(s in n for s in SKIP) or n[:-4] in sizes: continue
        try:
            r = P.convert(f, os.path.join(dstdir, n)); sizes[n[:-4]] = r['size']; print(n, r['size'], r['bytes'] // 1024, 'KB', r['mats'])
        except Exception:
            import traceback; traceback.print_exc()
    json.dump(sizes, open(os.path.join(dstdir, 'sizes.json'), 'w'), indent=0)

"""Textured game GLBs for the Asteroid_base kit (UE): UassetConverter/glb_output/Asteroid_base/Meshes -> Assets/3D/Asteroid/.
Reuses convert_paradise.convert with the asteroid material library. Run:  python html_hub/3d/convert_asteroid.py"""
import sys, os, json, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import convert_paradise as P
from uasset_to_glb.materials import MaterialLibrary
ROOT = P.ROOT
P.lib = MaterialLibrary(ROOT + '/Asteroid_base'); P._cache.clear()
P.FALLBACK = {'MI_antenna': (.6, .62, .66), 'MI_antenna_02': (.6, .62, .66), 'MI_container': (.55, .5, .42), 'MI_crates': (.5, .5, .48), 'MI_floor': (.45, .47, .5),
              'MI_props_01': (.5, .5, .52), 'MI_props_02': (.5, .5, .52), 'MI_rock_01': (.55, .42, .32), 'MI_rock_01_B': (.55, .42, .32), 'MI_rock_02': (.55, .42, .32),
              'MI_rock_02_B': (.55, .42, .32), 'MI_ship_': (.6, .6, .62), 'MI_small_mehses': (.5, .5, .52), 'MI_trim': (.62, .64, .68), 'MI_emissive': (.4, .9, 1.0),
              'MI_window_01': (.3, .5, .65)}
SKIP = ('SkySphere',)
if __name__ == '__main__':
    srcdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'glb_output', 'Asteroid_base', 'Meshes')
    dstdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(P.B.PROJ, 'Assets', '3D', 'Asteroid'); os.makedirs(dstdir, exist_ok=True); sizes = {}
    for f in sorted(glob.glob(srcdir + '/**/*.glb', recursive=True)):
        n = os.path.basename(f)
        if any(s in n for s in SKIP) or n[:-4] in sizes: continue
        try:
            r = P.convert(f, os.path.join(dstdir, n)); sizes[n[:-4]] = r['size']; print(n, r['size'], r['bytes'] // 1024, 'KB', r['mats'])
        except Exception:
            import traceback; traceback.print_exc()
    json.dump(sizes, open(os.path.join(dstdir, 'sizes.json'), 'w'), indent=0)

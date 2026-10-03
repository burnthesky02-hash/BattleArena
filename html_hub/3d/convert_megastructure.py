"""Textured game GLBs for the Megastructure_Scifi_World kit (UE): UassetConverter/glb_output/Megastructure_Scifi_World/Meshes -> Assets/3D/Megastructure/.
Reuses convert_paradise.convert with the megastructure material library. Run:  python html_hub/3d/convert_megastructure.py"""
import sys, os, json, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import convert_paradise as P
from uasset_to_glb.materials import MaterialLibrary
ROOT = P.ROOT
P.lib = MaterialLibrary(ROOT + '/Megastructure_Scifi_World'); P._cache.clear()
P.FALLBACK = {'MI_metal_01': (.55, .58, .64), 'MI_metal_01_O': (.5, .52, .58), 'MI_Demo': (.5, .5, .55), 'MI_emissive_blue': (.4, .8, 1.0), 'MI_emissive_red': (1.0, .3, .25), 'MI_emissive_white': (1, 1, 1)}
SKIP = ('SkySphere',)
if __name__ == '__main__':
    srcdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'glb_output', 'Megastructure_Scifi_World', 'Meshes')
    dstdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(P.B.PROJ, 'Assets', '3D', 'Megastructure'); os.makedirs(dstdir, exist_ok=True); sizes = {}
    for f in sorted(glob.glob(srcdir + '/**/*.glb', recursive=True)):
        n = os.path.basename(f)
        if any(s in n for s in SKIP) or n[:-4] in sizes: continue
        try:
            r = P.convert(f, os.path.join(dstdir, n)); sizes[n[:-4]] = r['size']; print(n, r['size'], r['bytes'] // 1024, 'KB', r['mats'])
        except Exception:
            import traceback; traceback.print_exc()
    json.dump(sizes, open(os.path.join(dstdir, 'sizes.json'), 'w'), indent=0)

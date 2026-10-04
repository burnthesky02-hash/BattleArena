"""Textured game GLBs for the Cave_Camp kit (UE): UassetConverter/glb_output/Cave_Camp/Meshes -> Assets/3D/CaveCamp/.
Reuses convert_paradise.convert with the Cave_Camp material library. Run:  python html_hub/3d/convert_cavecamp.py [srcdir] [dstdir]"""
import sys, os, json, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import convert_paradise as P
from uasset_to_glb.materials import MaterialLibrary
ROOT = P.ROOT
P.lib = MaterialLibrary(ROOT + '/Cave_Camp'); P._cache.clear()
P.FALLBACK = {'MI_rock_01': (.36, .33, .31), 'MI_rock_02': (.38, .35, .32), 'MI_rock_03': (.34, .32, .3), 'MI_stalactic': (.4, .37, .34), 'MI_small_rock': (.42, .4, .37),
              'MI_barrel': (.5, .36, .22), 'MI_crates': (.55, .4, .25), 'MI_table': (.52, .38, .24), 'MI_Tent': (.72, .62, .45), 'MI_bed': (.6, .5, .4),
              'MI_bed_plates_Paper': (.8, .75, .62), 'MI_water_01': (.2, .4, .5), 'MI_water_02': (.2, .4, .5)}
SKIP = ('pine_tree',)
if __name__ == '__main__':
    srcdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'glb_output', 'Cave_Camp', 'Meshes')
    dstdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(P.B.PROJ, 'Assets', '3D', 'CaveCamp'); os.makedirs(dstdir, exist_ok=True); sizes = {}
    for f in sorted(glob.glob(srcdir + '/**/*.glb', recursive=True)):
        n = os.path.basename(f)
        if any(s in n for s in SKIP): continue
        sub = os.path.basename(os.path.dirname(f)); out = n if sub != 'Small_rocks' else n.replace('SM_', 'SM_small_')   # Small_rocks reuses SM_rock_01/02
        if out[:-4] in sizes: continue
        try:
            r = P.convert(f, os.path.join(dstdir, out)); sizes[out[:-4]] = r['size']; print(out, r['size'], r['bytes'] // 1024, 'KB', r['mats'])
        except Exception:
            import traceback; traceback.print_exc()
    json.dump(sizes, open(os.path.join(dstdir, 'sizes.json'), 'w'), indent=0)

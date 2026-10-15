"""Textured game GLBs for the MedievalDungeon kit (UE4.x, FRawMesh): UassetConverter/glb_output/MedievalDungeon/Meshes -> Assets/3D/MedievalDungeon/.
Reuses convert_paradise.convert with the MedievalDungeon material library. Run:  python html_hub/3d/convert_medievaldungeon.py [srcdir] [dstdir]
Geometry first:  python -m uasset_to_glb MedievalDungeon/Meshes glb_output/MedievalDungeon/Meshes --recursive   (run inside UassetConverter)"""
import sys, os, json, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import convert_paradise as P
from uasset_to_glb.materials import MaterialLibrary
ROOT = P.ROOT
P.lib = MaterialLibrary(ROOT + '/MedievalDungeon'); P._cache.clear()
P.FALLBACK = {'M_Gargoyle_Inst': (.4, .4, .42), 'M_Gargoyle_Stand_Inst': (.45, .43, .4), 'M_Gibbet_Cage_Inst': (.25, .22, .2), 'M_Mausoleum_Ceiling_Inst': (.45, .43, .4),
              'M_Pillar_Inst': (.5, .47, .43), 'M_Pots_Inst': (.5, .32, .2), 'M_Small_Window_Inst': (.35, .33, .3), 'M_Log_Inst': (.4, .3, .2),
              'M_Statue_Hooded_Metal_Inst': (.3, .3, .32), 'M_Torch_Inst': (.4, .28, .15), 'M_Fire_Pit_Inst': (.3, .28, .26),
              'M_Skeleton_Dirty': (.8, .76, .65), 'M_Statue': (.5, .48, .45), 'M_Statue_Stand_Inst': (.45, .43, .4), 'M_Wood_Inst': (.4, .28, .18),
              'M_Stocks_Inst': (.4, .28, .18), 'M_Stairs_10_Inst': (.45, .43, .4), 'M_Table_Inst': (.4, .28, .18), 'M_Torture_Chair_Inst': (.3, .25, .2),
              'M_StoneWall_Inst': (.45, .43, .4), 'M_Stone_Altar_Inst': (.45, .43, .4), 'M_Stone_Coffin_Inst': (.45, .43, .4), 'M_Tiling_Plaster_Inst': (.6, .56, .5)}
# base materials (not instances) / unusual parameter names: pin the albedo texture by hand
from uasset_to_glb.materials import MaterialInfo
_PIN = {'M_Skeleton_Dirty': 'T_Skeleton_Dirty_A', 'M_Statue': 'T_Statue_Hooded_A', 'M_Statue_Stand_Inst': 'T_Statue_Stand_A'}
_orig_material = P.lib.material
def _material(name):
    if name in _PIN:
        m = MaterialInfo(name); m.textures = {'Albedo': _PIN[name]}; return m
    return _orig_material(name)
P.lib.material = _material
SKIP = ()
if __name__ == '__main__':
    srcdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'glb_output', 'MedievalDungeon', 'Meshes')
    dstdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(P.B.PROJ, 'Assets', '3D', 'MedievalDungeon'); os.makedirs(dstdir, exist_ok=True); sizes = {}
    for f in sorted(glob.glob(srcdir + '/**/*.glb', recursive=True)):
        n = os.path.basename(f)
        if any(s in n for s in SKIP) or n[:-4] in sizes: continue
        try:
            r = P.convert(f, os.path.join(dstdir, n)); sizes[n[:-4]] = r['size']; print(n, r['size'], r['bytes'] // 1024, 'KB', r['mats'])
        except Exception:
            import traceback; traceback.print_exc()
    json.dump(sizes, open(os.path.join(dstdir, 'sizes.json'), 'w'), indent=0)

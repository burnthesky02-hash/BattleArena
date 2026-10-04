"""Recolours Kenney Retro Fantasy Kit pieces for the village: makes <piece>-<colour>.glb copies whose roof / painted-wall texture is hue-shifted.
Roofs: -red -blue -brown.  Painted walls: -cream -sand -blue (plaster).   Run: python make_kenney_variants.py [kit_dir]   (kit_dir = '.../Models/GLB format')"""
import colorsys, json, os, struct, sys
from PIL import Image
KIT = sys.argv[1] if len(sys.argv) > 1 else "."
ROOFS = ["roof", "roof-corner", "roof-edge", "roof-side", "roof-side-corner", "roof-side-corner-inner", "roof-high-side", "roof-high-side-corner", "roof-high-side-corner-inner"]
WALLS = ["wall-paint", "wall-paint-door", "wall-paint-window", "wall-paint-detail", "wall-paint-flat", "wall-paint-half"]
def tint(png, out, fn):
    im = Image.open(os.path.join(KIT, "Textures", png)).convert("RGB"); px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = [c / 255 for c in px[x, y]]; h, s, v = colorsys.rgb_to_hsv(r, g, b); h, s, v = fn(h, s, v)
            px[x, y] = tuple(int(round(max(0, min(1, c)) * 255)) for c in colorsys.hsv_to_rgb(h % 1, max(0, min(1, s)), max(0, min(1, v))))
    im.save(os.path.join(KIT, "Textures", out))
def patch(name, new, rep):
    b = open(os.path.join(KIT, name + ".glb"), "rb").read(); L = struct.unpack("<I", b[12:16])[0]; js = b[20:20 + L].decode(); rest = b[20 + L:]
    for a, c in rep.items(): js = js.replace(a, c)
    js = js.encode(); js += b" " * ((4 - len(js) % 4) % 4)
    out = b[:8] + struct.pack("<I", 12 + 8 + len(js) + len(rest)) + struct.pack("<I", len(js)) + b[16:20] + js + rest
    open(os.path.join(KIT, new + ".glb"), "wb").write(out)
# roof.png is teal slate; move the hue to red tile / blue slate / brown shingle
for col, fn in (("red", lambda h, s, v: (0.012, min(1, s * 1.5 + 0.1), v * 1.15)), ("blue", lambda h, s, v: (0.60, s * 1.4, v * 1.2)), ("brown", lambda h, s, v: (0.07, s * 1.1, v * 0.9))):
    tint("roof.png", "roof-%s.png" % col, fn)
    for n in ROOFS:
        if os.path.exists(os.path.join(KIT, n + ".glb")): patch(n, n + "-" + col, {"Textures/roof.png": "Textures/roof-%s.png" % col})
# cobblestonePainted.png: the painted plaster band of the houses
for col, fn in (("cream", lambda h, s, v: (0.11, s * 0.5, min(1, v * 1.15))), ("sand", lambda h, s, v: (0.09, s * 0.9, v)), ("blue", lambda h, s, v: (0.57, s * 0.9, v * 1.0))):
    tint("cobblestonePainted.png", "cobblestonePainted-%s.png" % col, fn)
    for n in WALLS:
        if os.path.exists(os.path.join(KIT, n + ".glb")): patch(n, n + "-" + col, {"Textures/cobblestonePainted.png": "Textures/cobblestonePainted-%s.png" % col})
print("ok")

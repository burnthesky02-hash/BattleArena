"""Builds html_hub/3d/plaza.json (the walkable colosseum plaza) from the Kenney Retro Fantasy Kit (CC0).
Run:  python make_plaza.py [outdir]     (default ./hub3d)   Pieces are [model, x, z, rotY, y, scale]; 1 tile = 4 units."""
import json, os, random, sys
random.seed(5)
OUT = sys.argv[1] if len(sys.argv) > 1 else "hub3d"
KIT = "/assets/3D/kenney_retro-fantasy-kit/Models/GLB format/"
S = 4
P, COL, DEC = [], [], []
def put(n, x, z, rot=0, y=0, sc=S): P.append([n, x, z, rot, y, sc])
def block(x, z, w, d): COL.append({"x": x, "z": z, "w": w, "d": d})

XS = range(-16, 17, 4); ZS = range(-6, 15, 4)
for x in XS:
    for z in ZS: put("floor-flat", x, z)
# outer walls: back (gate in the middle = the colosseum entrance), sides, front (hidden when it blocks the camera)
for i, x in enumerate(XS):
    put("wall-fortified-gate" if x == 0 else ("wall-fortified-window" if i % 2 else "wall-fortified"), x, -10, 0)
    put("battlement", x, -10, 0, S)
for z in range(-6, 15, 4):
    k = "wall-fortified-window" if (z // 4) % 2 else "wall-fortified"
    put(k, -20, z, 90); put(k, 20, z, 270); put("battlement", -20, z, 90, S); put("battlement", 20, z, 270, S)
for cx, cz in ((-20, -10), (20, -10)):
    put("tower-base", cx, cz); put("tower-top", cx, cz, 0, S)
for x in (-12, -6, 6, 12): put("column", x, -7.6)
# props (see NPC stations): shop stall, forge corner, trainer yard, scribe desk, guide gate
def stall(cx, cz, rot=0):
    for dx in (-2.4, 2.4): put("column-wood", cx + dx, cz - 1.6, 0, 0, 3.2)
    put("wood-floor", cx, cz - 0.4, 0, 0, 4)
    put("detail-crate", cx - 1.6, cz + 0.8, 10, 0, 4); put("barrels", cx + 1.8, cz + 0.9, 30, 0, 4); put("detail-crate-small", cx + 0.2, cz + 1.3, 40, 0, 4)
    block(cx, cz - 0.3, 5.4, 2.6)
stall(13, 6)
put("barrels", -17, -6.5, 20); put("detail-crate", -15.2, -7, 15); put("detail-barrel", -16.4, -4.6, 0, 0, 4); block(-16.2, -6, 3.2, 3)
put("detail-crate", 16.5, -6.8, 70); put("barrels", 14.8, -6.4, 200); put("detail-crate-small", 16.8, -4.8, 40); block(15.8, -6, 3.6, 3)
put("fence-wood", -12, 13.4, 0); put("fence-wood", -16, 13.4, 0); put("fence-wood", -9.2, 11.6, 90); block(-14, 13.4, 8, 0.6)
put("bricks", 11.2, -2.4, 20, 0, 4); put("bricks", -4.4, 11.4, 70, 0, 4)
put("tree-large", -17.5, 10.5, 90, 0, 5); block(-17.5, 10.5, 2.4, 2.4)
put("tree-shrub", 17.2, 12.6, 0, 0, 4.5); block(17.2, 12.6, 1.6, 1.6)
for x, z in ((-30, -16), (-12, -22), (14, -21), (31, -14), (-34, 6), (34, 8), (-28, 22), (29, 24)):
    put("tree-large", x, z, random.choice((0, 90, 180)), 0, S * 1.3)

NP = [
 dict(id="boss", name="Gate Warden", title="Colosseum Gate", sprite="Draven", x=0, z=-6.4, h=2.5, action="challenge", reach=5.2, radius=1.3),
 dict(id="battle", name="Draven", title="Battlemaster", sprite="Draven", x=-9.5, z=-1.5, h=2.4, action="battle"),
 dict(id="ladder", name="Kenji", title="Rank Keeper", sprite="Kenji", x=9.5, z=-1.5, h=2.4, action="ladder"),
 dict(id="summon", name="Miya", title="Summoner", sprite="Miya", x=0, z=3.2, h=2.4, action="summon", reach=5.0),
 dict(id="heroes", name="Lyra", title="Trainer", sprite="Lyra", x=-11.5, z=8.5, h=2.4, action="heroes"),
 dict(id="shop", name="Rook", title="Shopkeeper", sprite="Rook", x=13, z=7.2, h=2.4, action="shop"),
 dict(id="world", name="Yulia", title="Scout", sprite="Yulia", x=17.2, z=15, h=2.4, action="world"),
 dict(id="save", name="Scribe", title="Records", sprite="Kenji", x=-17.2, z=15, h=2.3, action="save_and_quit", tint=[0.75, 0.88, 1.15, 1]),
]
DEC += [dict(type="glyph", x=0, z=3.2, r=3.4, color=[0.6, 0.4, 1, 1], spin=14),
        dict(type="glow", x=0, z=-6, r=6, color=[1, 0.7, 0.35, 1]), dict(type="glow", x=13, z=6, r=5, color=[1, 0.75, 0.4, 1]),
        dict(type="glow", x=-9.5, z=-1.5, r=4, color=[1, 0.4, 0.3, 1]), dict(type="glow", x=9.5, z=-1.5, r=4, color=[0.5, 0.8, 1, 1]),
        dict(type="glow", x=-11.5, z=8.5, r=4, color=[0.5, 1, 0.6, 1])]
d = dict(name="Colosseum Plaza", kit=KIT, tile=S, pieces=P, colliders=COL, npcs=NP, decals=DEC,
         bounds=dict(minX=-18.2, maxX=18.2, minZ=-7.4, maxZ=16.4), spawn=dict(x=0, z=11), playerHeight=2.4,
         light=dict(dir=[-0.45, -1, -0.5], color=[1.0, 0.9, 0.76], ambient=[0.6, 0.57, 0.68]), fog=dict(color=[0.2, 0.14, 0.3], near=60, far=150))
os.makedirs(OUT, exist_ok=True); json.dump(d, open(os.path.join(OUT, "plaza.json"), "w"), separators=(",", ":"))
# preview scene: one of each interesting piece on a grid
names = ["roof","roof-corner","roof-edge","roof-high-side","roof-side","roof-side-corner","structure","structure-cross","structure-poles","structure-wall","wall-paint","wall-pane-wood-door","wall-pane-paint-window","wall-door","wall-gate","wall-low","dock-corner","dock-side","stairs-stone","stairs-wood","overhang","floor-stairs","wood-floor-railing","water"]
pp = [["floor-flat", (i % 6) * 5 - 12.5, (i // 6) * 5, 0, 0, 5] for i in range(24)] + [[n, (i % 6) * 5 - 12.5, (i // 6) * 5, 0, 0, 4] for i, n in enumerate(names)]
json.dump(dict(kit=KIT, pieces=pp, npcs=[], spawn=dict(x=-12, z=-8), bounds=dict(minX=-40, maxX=40, minZ=-40, maxZ=40)), open(os.path.join(OUT, "preview.json"), "w"))
print("pieces", len(P), "colliders", len(COL))

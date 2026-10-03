"""Builds html_hub/3d/dungeon.json: the Hollow Crypt under the island's cave. Rooms are cell rectangles (4 m cells, x = (col-10)*4, z = (row-26)*4,
north = up); walls are generated round every floor cell. Monsters are NPCs with a `battle` action (a real fight; a win comes back as ?cleared=<key>
and hides them, opening the gates that use hideIf). The boss fight is the WORLD_BOSS `drowned_sovereign_boss` (data/bosses.py).
Run:  python make_dungeon.py [outdir]. Re-running overwrites hand edits made in /builder3d."""
import json, math, os, sys
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
DG = "/assets/3D/Dungeon/"
P, COL, DEC, NP, EV = [], [], [], [], []
def put(n, x, z, rot=0, y=0, sc=1, hide=None):
    p = [DG + n, round(x, 3), round(z, 3), rot, y, sc]
    if hide: p.append(hide)
    P.append(p)
def block(x, z, w, d, hide=None):
    c = {"x": round(x, 3), "z": round(z, 3), "w": round(w, 3), "d": round(d, 3)}
    if hide: c["hideIf"] = hide
    COL.append(c)
def glow(x, z, r, c): DEC.append(dict(type="glow", x=x, z=z, r=r, color=c))
def X(c): return (c - 10) * 4.0
def Z(r): return (r - 26) * 4.0

# ---- rooms (inclusive col/row rectangles)
ROOMS = dict(entrance=(8, 12, 24, 26), c1=(10, 10, 22, 23), gallery=(6, 14, 18, 21), west=(1, 4, 19, 22), east=(16, 19, 19, 22), wpass=(5, 5, 20, 20), epass=(15, 15, 20, 20),
             c2=(10, 10, 16, 17), crypt=(6, 14, 11, 15), c3=(10, 10, 9, 10), ante=(8, 12, 7, 8), boss=(5, 15, 1, 6))
GATES = {(10, 17): "dg_a", (10, 9): "dg_b2"}               # cell -> key that opens it
floor = set()
for (c0, c1, r0, r1) in ROOMS.values():
    for c in range(c0, c1 + 1):
        for r in range(r0, r1 + 1): floor.add((c, r))
walls = set()
for (c, r) in floor:
    for dc in (-1, 0, 1):
        for dr in (-1, 0, 1):
            if (c + dc, r + dr) not in floor: walls.add((c + dc, r + dr))
for (c, r) in sorted(floor): put("SM_dg_floor", X(c), Z(r), 0, 0, 4.0)
for (c, r) in sorted(walls): put("SM_dg_wall", X(c), Z(r), 0, 0, 1.0)
# wall colliders: merge runs along each row
for r in sorted({r for _, r in walls}):
    cs = sorted(c for c, rr in walls if rr == r); s = cs[0]; prev = cs[0]
    for c in cs[1:] + [None]:
        if c is None or c != prev + 1:
            n = prev - s + 1; block(X((s + prev) / 2), Z(r), n * 4.0, 4.0); s = c
        prev = c if c is not None else prev
for (c, r), key in GATES.items():
    put("SM_dg_gate", X(c), Z(r), 0, 0, 1.0, key); block(X(c), Z(r), 4.0, 1.0, key)

def brazier(x, z, rad=6.0):
    put("SM_dg_brazier", x, z); put("SM_dg_flame", x, z, 0, 1.55, 1.0); block(x, z, 1.1, 1.1); glow(x, z, rad, [1, .62, .25, .85])
def crystal(x, z, rot=0, rad=4.6):
    put("SM_dg_crystal", x, z, rot); block(x, z, 0.9, 0.9); glow(x, z, rad, [.35, .75, 1, .8])
def pond(x, z, w, d, rad=0):
    put("SM_dg_water", x, z, 0, 0, 1.0); P[-1][5] = 1.0                                                   # unit plane scaled per axis is not possible: tile it
def pool(cx, cz, w, d):                                                                                   # a pool made of 2 m tiles
    for i in range(int(w // 2)):
        for j in range(int(d // 2)): put("SM_dg_water", cx - w / 2 + 1 + i * 2, cz - d / 2 + 1 + j * 2, 0, 0, 2.0)
    block(cx, cz, w, d)

# ---- entrance hall: braziers, a lore tablet and the reset altar
brazier(X(8.6), Z(24.6)); brazier(X(11.4), Z(24.6))
put("SM_dg_tablet", X(10), Z(24.3), 0); block(X(10), Z(24.3), 1.6, 0.5)
EV += [dict(id="dg_entry_tablet", name="Entrance tablet", x=X(10), z=Z(24.3) + 1.6, w=3.2, d=2.4, trigger="talk", prompt="Read the tablet",
            actions=[dict(type="say", who="Carved Tablet", text="THE HOLLOW CRYPT. HERE THE COURT OF THE DROWNED SOVEREIGN WAS LAID TO REST. THOSE WHO DISTURB IT WILL BE MET IN KIND.")])]
put("SM_dg_block", X(12.3), Z(25.4), 0, 0, 1.2); block(X(12.3), Z(25.4), 1.2, 1.2)
EV += [dict(id="dg_altar", name="Waking stone", x=X(12.3), z=Z(25.4) + 1.4, w=3.0, d=2.4, trigger="talk", prompt="Touch the stone",
            actions=[dict(type="say", who="Waking Stone", text="The stone is warm. You feel the crypt stir: every guardian you felled stands again, and the sealed doors close behind you."),
                     dict(type="reset_progress", prefix="dg_")])]
EV += [dict(id="dg_exit", name="Back to the island", x=0, z=Z(26) + 0.6, w=8, d=2.2, trigger="touch", once=False,
            actions=[dict(type="warp", scene="island", x=0, z=-39.5)])]

# ---- gallery: pillars, braziers, two side rooms
for c in (7, 13):
    for r in (18.5, 21):
        put("SM_dg_pillar", X(c), Z(r)); block(X(c), Z(r), 1.2, 1.2)
brazier(X(6.5), Z(21.4)); brazier(X(13.5), Z(21.4))
# west room: sarcophagi and a tablet
for r in (19.7, 21.7): put("SM_dg_sarcophagus", X(2.2), Z(r), 90); block(X(2.2), Z(r), 3.0, 1.5)
brazier(X(3.6), Z(22.5)); put("SM_dg_tablet", X(1.2), Z(20.7), 90); block(X(1.2), Z(20.7), 0.5, 1.6)
EV += [dict(id="dg_west_tablet", name="West tablet", x=X(1.2) + 1.8, z=Z(20.7), w=2.4, d=3.2, trigger="talk", prompt="Read the tablet",
            actions=[dict(type="say", who="Carved Tablet", text="THE KING'S GUARD, SWORN TO HOLD THE GALLERY UNTIL THE TIDE TURNS. THE TIDE HAS NEVER TURNED.")])]
# east room: crystals and a tablet
for x, z in ((17.0, 19.4), (18.8, 21.5), (16.7, 22.0)): crystal(X(x), Z(z), (x * 37) % 360)
put("SM_dg_tablet", X(19.4), Z(20.2), 270); block(X(19.4), Z(20.2), 0.5, 1.6)
EV += [dict(id="dg_east_tablet", name="East tablet", x=X(19.4) - 1.8, z=Z(20.2), w=2.4, d=3.2, trigger="talk", prompt="Read the tablet",
            actions=[dict(type="say", who="Carved Tablet", text="SEA-GLASS GROWS WHERE THE KING'S TEARS FELL. IT GLOWS FOR THOSE WHO MEAN TO STAY.")])]

# ---- the flooded crypt: pools either side, crystals, pillars
pool(X(7.7), Z(13), 4, 8); pool(X(12.3), Z(13), 4, 8)
crystal(X(6.5), Z(11.5), 40); crystal(X(13.5), Z(11.5), 200); crystal(X(6.4), Z(14.8), 120); crystal(X(13.6), Z(14.8), 310)
for r in (11.6, 14.4): put("SM_dg_pillar", X(9.2), Z(r)); block(X(9.2), Z(r), 1.2, 1.2); put("SM_dg_pillar", X(10.8), Z(r)); block(X(10.8), Z(r), 1.2, 1.2)

# ---- antechamber before the boss door
brazier(X(8.5), Z(7.4)); brazier(X(11.5), Z(7.4)); put("SM_dg_tablet", X(10), Z(7.3), 0); block(X(10), Z(7.3), 1.6, 0.5)
EV += [dict(id="dg_ante_tablet", name="Door tablet", x=X(10), z=Z(7.3) + 1.8, w=3.2, d=2.4, trigger="talk", prompt="Read the tablet",
            actions=[dict(type="say", who="Carved Tablet", text="BEYOND THIS DOOR THE SOVEREIGN KEEPS HIS THRONE. THE DOOR OPENS ONLY FOR THOSE WHO HAVE CLEARED THE CRYPT.")])]

# ---- boss hall: dais, throne, two rows of pillars, braziers, pools
put("SM_dg_dais", X(10), Z(1.6)); block(X(10), Z(1.6) - 0.3, 14, 7.0)
put("SM_dg_throne", X(10), Z(0.9), 0); 
for sgn in (-1, 1):
    for r in (2.8, 4.5, 6.0): put("SM_dg_pillar", X(10 + sgn * 3.8), Z(r)); block(X(10 + sgn * 3.8), Z(r), 1.2, 1.2)
    brazier(X(10 + sgn * 4.6), Z(1.3)); brazier(X(10 + sgn * 4.6), Z(6.2))
pool(X(6.4), Z(3.9), 3, 7); pool(X(13.6), Z(3.9), 3, 7)
glow(X(10), Z(2.6), 7.0, [.45, .65, 1, .55])

# ---- monsters (NPC + battle action); key = progress id, gate keys are the ones in GATES
def foe(key, name, sprite, col, row, tint, line, h=2.4):
    NP.append(dict(id=key, name=name, title="Hostile", sprite=sprite, x=round(X(col), 2), z=round(Z(row), 2), h=h, tint=tint, hideIf=key, reach=5.0,
                   actions=[dict(type="say", who=name, text=line), dict(type="battle", key=key, boss="")]))
foe("dg_m1", "Restless Guard", "Draven", 7.7, 19.2, [1.25, .75, .75, 1], "Intruders... in the gallery of the king.")
foe("dg_m2", "Restless Guard", "Draven", 12.3, 19.2, [1.25, .75, .75, 1], "None pass the gallery. None.")
foe("dg_a", "Gallery Warden", "Rook", 10, 18.6, [.65, .8, 1.15, 1], "I have held this hall for a thousand tides. Kneel or fall.", 2.8)
foe("dg_w1", "Crypt Stalker", "Kael", 2.8, 19.6, [.7, 1.1, .85, 1], "You walk among the king's dead. Join them.")
foe("dg_e1", "Drowned Acolyte", "Lyra", 17.8, 20.2, [.6, .85, 1.2, 1], "The sea-glass sings your name...")
foe("dg_b1", "Tide Wraith", "Yulia", 10, 14.6, [.6, .9, 1.25, 1], "Cold, so cold. Stay and be cold with us.")
foe("dg_b2", "Hollow Knight", "Draven", 10, 12.2, [.7, .75, 1.0, 1], "The Sovereign's door stays shut. Prove yourself.", 2.9)
NP.append(dict(id="dg_boss", name="Drowned Sovereign", title="King of the Hollow", sprite="Rook", x=round(X(10), 2), z=round(Z(2.0), 2), h=4.0, tint=[.45, .65, 1.2, 1], hideIf="dg_boss", reach=6.0,
               actions=[dict(type="say", who="Drowned Sovereign", text="You have cut through my court. Few come this far."),
                        dict(type="say", who="Drowned Sovereign", text="Then draw your blades, and let the sea decide."), dict(type="battle", key="dg_boss", boss="drowned_sovereign_boss")]))
# after the boss: a spirit and a way home
NP.append(dict(id="dg_spirit", name="Spirit of the King", title="At rest", sprite="Lyra", x=round(X(10), 2), z=round(Z(2.0), 2), h=2.6, tint=[.7, .9, 1.4, 1], showIf="dg_boss", reach=5.0,
               actions=[dict(type="say", who="Spirit of the King", text="The tide is turned at last. Take what is left of my crown, and the thanks of the court."),
                        dict(type="say", who="", text="The doors stand open and the crypt is quiet. Touch the waking stone by the entrance to wake it again, or take the stairs home.")]))
EV += [dict(id="dg_portal", name="Stairs to the surface", x=X(10), z=Z(5.0), w=5, d=2.4, trigger="talk", prompt="Climb back to the island", showIf="dg_boss",
            actions=[dict(type="warp", scene="island", x=0, z=-39.5)])]
glow(X(10), Z(5.0), 4.0, [.6, .85, 1, .6])

d = dict(name="Hollow Crypt", kit="", tile=4, pieces=P, colliders=COL, npcs=NP, events=EV, decals=DEC,
         bounds=dict(minX=-44, maxX=44, minZ=-102, maxZ=3.4), spawn=dict(x=0, z=-4.0), playerHeight=2.4,
         sky=dict(type="gradient", stops=[[0, "#05070d"], [1, "#0d1420"]]),
         fx=[dict(type="dust", amount=.2)],
         light=dict(dir=[-0.35, -1, -0.25], color=[0.78, 0.82, 1.0], ambient=[0.34, 0.36, 0.47]), fog=dict(color=[0.03, 0.04, 0.07], near=34, far=85))
os.makedirs(OUT, exist_ok=True); json.dump(d, open(os.path.join(OUT, "dungeon.json"), "w"), separators=(",", ":"))
print("pieces", len(P), "colliders", len(COL), "npcs", len(NP), "events", len(EV))

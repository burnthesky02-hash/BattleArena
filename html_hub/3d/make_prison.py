"""Builds html_hub/3d/prison.json: "The Pit", the cellblock under the Olympus colosseum where the portal drops the hero (see claude/prison-and-asteroid.md).
Built from the Hollow Crypt kit (Assets/3D/Dungeon, 4 m cells: x = col*4, z = row*4, north = up). The hero is a slave here: every hub service
(battle / ladder / rank challenge / heroes / shop / summon / save) is on the floor, but the stairs up stay locked until the player's rank passes
`freeRank - 1`; then the autorun cutscene frees them and warps to olympus.  Run:  python make_prison.py [outdir]
Re-running overwrites hand edits made in /builder3d."""
import json, os, sys
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
DG = "/assets/3D/Dungeon/"
FREE_RANK = 3                                   # rank the player must reach to be freed (= "past rank 2")
P, COL, DEC, NP, EV = [], [], [], [], []
def put(n, x, z, rot=0, y=0, sc=1): P.append([DG + n, round(x, 3), round(z, 3), rot, y, sc])
def block(x, z, w, d): COL.append({"x": round(x, 3), "z": round(z, 3), "w": round(w, 3), "d": round(d, 3)})
def glow(x, z, r, c): DEC.append(dict(type="glow", x=x, z=z, r=r, color=c))
X = lambda c: c * 4.0
Z = lambda r: r * 4.0

# ---- rooms (inclusive col/row rectangles)
ROOMS = dict(hall=(-4, 4, 1, 5), west=(-8, -6, 2, 4), wpass=(-5, -5, 3, 3), east=(6, 8, 2, 4), epass=(5, 5, 3, 3))
CELLS = [-4, -2, 0, 2, 4]                       # one cell column each, rows -1..0; the middle one is the hero's and stands open
for c in CELLS: ROOMS["cell%d" % c] = (c, c, -1, 0)
floor = set()
for (c0, c1, r0, r1) in ROOMS.values():
    for c in range(c0, c1 + 1):
        for r in range(r0, r1 + 1): floor.add((c, r))
walls = set()
for (c, r) in floor:
    for dc in (-1, 0, 1):
        for dr in (-1, 0, 1):
            if (c + dc, r + dr) not in floor: walls.add((c + dc, r + dr))
ARENA_CELL, EXIT_CELL = (9, 3), (0, 6)          # wall cells replaced by a gate
walls -= {ARENA_CELL, EXIT_CELL}
for (c, r) in sorted(floor): put("SM_dg_floor", X(c), Z(r), 0, 0, 4.0)
for (c, r) in sorted(walls): put("SM_dg_wall", X(c), Z(r), 0, 0, 1.0)
for r in sorted({r for _, r in walls}):          # merge wall runs into colliders
    cs = sorted(c for c, rr in walls if rr == r); s = prev = cs[0]
    for c in cs[1:] + [None]:
        if c is None or c != prev + 1:
            block(X((s + prev) / 2), Z(r), (prev - s + 1) * 4.0, 4.0); s = c
        prev = c if c is not None else prev
# cell doors: iron bars facing the hall (closed except the hero's own cell)
for c in CELLS:
    if c != 0: put("SM_dg_gate", X(c), 2.0, 0, 0, 1.0); block(X(c), 2.0, 4.0, 1.0)
put("SM_dg_gate", X(EXIT_CELL[0]), Z(EXIT_CELL[1]), 0, 0, 1.0); block(X(EXIT_CELL[0]), Z(EXIT_CELL[1]), 4.0, 1.2)          # the way up (locked)
put("SM_dg_gate", X(ARENA_CELL[0]), Z(ARENA_CELL[1]), 90, 0, 1.0); block(X(ARENA_CELL[0]), Z(ARENA_CELL[1]), 1.2, 4.0)      # the arena door

def brazier(x, z, rad=6.0):
    put("SM_dg_brazier", x, z); put("SM_dg_flame", x, z, 0, 1.55, 1.0); block(x, z, 1.1, 1.1); glow(x, z, rad, [1, .62, .25, .85])
# ---- hall: pillars, braziers, the Overseer's corner
for x in (-8, 8):
    for z in (8, 16): put("SM_dg_pillar", x, z); block(x, z, 1.2, 1.2)
for x, z in ((-17.0, 20.4), (17.0, 20.4), (-17.0, 3.6), (17.0, 3.6), (-3.2, 11.0), (3.2, 11.0)): brazier(x, z)
put("SM_dg_dais", 0, 11.0, 0, 0, 0.45)
# ---- west wing: the prisoners' market (crates and blocks)
for x, z, s in ((-31.4, 7.6, 1.2), (-30.0, 7.4, 0.9), (-31.4, 17.0, 1.2), (-29.8, 17.2, 1.0)): put("SM_dg_block", x, z, 0, 0, s); block(x, z, s, s)
brazier(-23.4, 11.6, 5.0)
# ---- east wing: the fighters' ready room before the arena door
brazier(33.0, 8.4, 6.0); brazier(33.0, 15.6, 6.0)
put("SM_dg_block", 24.8, 7.8, 0, 0, 1.3); block(24.8, 7.8, 1.3, 1.3); put("SM_dg_crystal", 25.0, 16.8, 20); block(25.0, 16.8, 0.9, 0.9); glow(25.0, 16.8, 4.0, [.35, .75, 1, .8])
# ---- rules tablet on the south wall
put("SM_dg_tablet", 6.0, 21.3, 0); block(6.0, 21.3, 1.6, 0.5)
EV += [dict(id="pit_rules", name="Rules of the Pit", x=6.0, z=19.7, w=3.2, d=2.4, trigger="talk", prompt="Read the tablet",
            actions=[dict(type="say", who="Rules of the Pit", text="I. THE COLOSSEUM OWNS WHAT THE PORTAL BRINGS. II. A SLAVE FIGHTS WHEN THE OVERSEER SAYS. III. THE CROWD MAY BUY A CHAMPION'S COLLAR. THE PIT HAS NEVER KEPT ONE LONG.")])]
# the hero's cot: a low stone slab with a block for a pillow
put("SM_dg_dais", 0, -1.4, 0, 0, 0.34); put("SM_dg_block", 0, -2.5, 0, 0.0, 0.8); block(0, -1.6, 1.9, 1.9)
EV += [dict(id="pit_cot", name="Your cot", x=0, z=-1.6, w=3.8, d=3.4, trigger="talk", prompt="Sleep on the cot (pass time)",
            actions=[dict(type="pass_time")])]
EV += [dict(id="pit_exit", name="Stairs up", x=0, z=21.0, w=6, d=3.0, trigger="talk", prompt="Try the gate",
            actions=[dict(type="say", who="", text="The gate to the stairs is barred from the other side. Above it, faintly, the crowd roars.", unless="st_free")])]
EV += [dict(id="pit_arena", name="Arena door", x=31.0, z=12.0, w=5.0, d=6.0, trigger="talk", prompt="Look through the door",
            actions=[dict(type="say", who="", text="The arena door rumbles with the noise of the crowd. Gatekeeper Brakk opens it when it is your turn. Speak to him to challenge the next rank.")])]

# ---- people
def npc(**kw): kw.setdefault("h", 2.4); NP.append(kw)
npc(id="battle", name="Overseer Vex", title="Pit Overseer", sprite="Draven", x=0, z=12.6, line="Fresh meat. The crowd wants blood and you are what I have. Pick your fight, slave.", tint=[.85, .7, .7, 1], reach=5.0, action="battle")
npc(id="ladder", name="Dagna", title="Pit Boss", sprite="Yulia", x=-9.5, z=19.0, line="Bouts back to back, bigger purses. The house takes its cut, but a slave can dream.", tint=[.8, .85, .8, 1], action="ladder")
npc(id="boss", name="Gatekeeper Brakk", title="Arena Door", sprite="Draven", x=30.5, z=12.0, h=2.7, tint=[.7, .75, 1, 1], action="challenge", reach=5.2, radius=1.3)
npc(id="heroes", name="Old Marek", title="Fellow prisoner", sprite="Rook", x=-26.5, z=9.4, line="Even a slave can sharpen a blade. Let's see to your fighters.", tint=[.75, .8, .75, 1], action="heroes")
npc(id="shop", name="Whisper", title="Smuggler", sprite="Kenji", x=-26.0, z=15.4, line="Psst. Nothing here fell off a cart. Much. Care to browse?", tint=[.6, .6, .85, 1], action="shop")
npc(id="summon", name="Hanna", title="Cell-block seer", sprite="Miya", x=10.5, z=18.0, line="The old glyph under my cell still answers. Pay the toll and see who comes.", tint=[.85, .8, 1, 1], action="summon", reach=5.0)
npc(id="save", name="The Scribe", title="Keeper of ledgers", sprite="Lyra", x=14.5, z=5.8, tint=[.75, .88, 1.15, 1], action="save_and_quit")
for i, (x, name, line) in enumerate(((-16, "Brann", "Three years in this cell. The cheering above never stops, you stop hearing it."), (-8, "Pale Tessa", "They take the strong ones to the arena. The strong ones don't come back to the cells."),
                                      (8, "Little Joss", "Don't cross Vex. He isn't cruel, he just never forgets."), (16, "The Quiet One", "..."))):
    npc(id="pr%d" % (i + 1), name=name, title="Prisoner", sprite=("Rook", "Lyra", "Kenji", "Draven")[i], x=x, z=-4.2, tint=[.55, .55, .6, 1], actions=[dict(type="say", who=name, text=line)], line=line)
DEC += [dict(type="glyph", x=10.5, z=18.0, r=3.0, color=[.6, .4, 1, 1], spin=14), dict(type="glow", x=0, z=12.6, r=5, color=[1, .45, .35, 1]),
        dict(type="glow", x=30.5, z=12.0, r=5, color=[.55, .75, 1, 1]), dict(type="glow", x=0, z=-1.4, r=3.5, color=[1, .8, .45, .9]), dict(type="glow", x=0, z=-4, r=3.5, color=[.7, .55, 1, 1])]

# ---- story: arriving as a slave, and winning freedom (rank >= freeRank)
AUTO = [
 dict(**{"if": "st_done", "unless": "st_free", "minRank": "freeRank"}, actions=[
     dict(type="say", who="", text="A thunderous chant shakes the dust from the ceiling. Above you, the whole Colosseum is shouting your name."),
     dict(type="say", who="Overseer Vex", text="Rank " + str(FREE_RANK - 1) + " behind you, and the crowd wants you free. They bought your collar with their cheering. Don't look so surprised."),
     dict(type="say", who="Overseer Vex", text="The Colosseum doesn't keep a champion in a cage. The stairs are open. Go on, before I change my mind."),
     dict(type="say", who="", text="The collar clicks open and falls away. Light spills down the stairs from the sands above."),
     dict(type="flag", key="st_free"), dict(type="warp", scene="olympus", x=0, z=11)]),
 dict(unless="st_jailed", actions=[
     dict(type="say", who="", text="The violet light fades. Cold stone against your back, iron bars humming in the dark. Somewhere above, a crowd roars."),
     dict(type="say", who="Overseer Vex", text="On your feet, islander. That portal dropped a fresh one into my pit."),
     dict(type="say", who="Overseer Vex", text="You belong to the Colosseum now. You fight when I say, you bleed when they cheer."),
     dict(type="say", who="Overseer Vex", text="Rise past Rank " + str(FREE_RANK - 1) + " and the crowd may buy your collar. Until then you are property. Speak to me when you are ready to fight."),
     dict(type="flag", key="st_jailed")]),
]
d = dict(name="The Pit", kit="", tile=4, pieces=P, colliders=COL, npcs=NP, events=EV, decals=DEC,
         bounds=dict(minX=-33.5, maxX=33.5, minZ=-5.5, maxZ=22.4), spawn=dict(x=0, z=-3.6), playerHeight=2.4,
         story=True, freeRank=FREE_RANK, autorun=AUTO,
         sky=dict(type="gradient", stops=[[0, "#05070d"], [1, "#120d18"]]), fx=[dict(type="dust", amount=.25)],
         light=dict(dir=[-0.35, -1, -0.25], color=[0.9, 0.78, 0.7], ambient=[0.42, 0.38, 0.45]), fog=dict(color=[0.05, 0.04, 0.07], near=40, far=95))
import story_pit; story_pit.apply_prison(d)          # Kenji wakes here after the Hollow Cave knock-out (Oct 6)
os.makedirs(OUT, exist_ok=True); json.dump(d, open(os.path.join(OUT, "prison.json"), "w"), separators=(",", ":"))
print("pieces", len(P), "colliders", len(COL), "npcs", len(NP), "events", len(EV))

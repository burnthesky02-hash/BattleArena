"""Builds html_hub/3d/reach.json: "The Shattered Reach" -- chapter 4, reached from Outpost Kestrel's rift gate once the Vault Warden is down
(claude/chapter-4-shattered-reach.md). A line of floating ruins over a broken sky:

    Landing (spawn, rest crystal, way back)  ->  causeway  ->  Islet A (random fights, the Breach Warden)
        ->  gate (opens when rc_g1 falls)  ->  causeway  ->  Islet B (random fights, tablets, chests)  ->  bridge  ->  the Harbinger's arena

Kit: Assets/3D/Megastructure floor slabs and pillars + Dungeon-kit crystals/gates/tablets (same pieces the Shard Vault uses).
Flags: rc_g1 (Breach Warden), rc_boss (Rift Harbinger), rc_end (aftermath cutscene seen), rc_arrive (arrival cutscene seen), rc_c1.. (chests).
Run:  python make_reach.py [outdir]    Re-running overwrites hand edits made in /builder3d."""
import json, math, os, random, sys
from collections import deque
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
MG, DG, KEN = "/assets/3D/Megastructure/", "/assets/3D/Dungeon/", "/assets/3D/kenney_retro-fantasy-kit/Models/GLB format/"
BASE = (8, 21)                          # where the gate drops you back on the asteroid (just in front of the rift gate; see reach_hook.py)
CS = 6.0
P, COL, DEC, NP, EV = [], [], [], [], []
rng = random.Random(4242)
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "make_vault.py"), encoding="utf-8").read()
EQ_IDS = eval(_src.split("EQ_IDS = ", 1)[1].split("\n", 1)[0])        # equipment ids by rarity, shared with the vault's chests

def put(n, x, z, rot=0, y=0, sc=1, hide=None, pre=MG):
    p = [pre + n, round(x, 3), round(z, 3), rot, round(y, 3), sc]
    if hide: p.append(hide)
    P.append(p)
def block(x, z, w, d, hide=None):
    c = {"x": round(x, 3), "z": round(z, 3), "w": round(w, 3), "d": round(d, 3)}
    if hide: c["hideIf"] = hide
    COL.append(c)
def glow(x, z, r, c, show=None):
    d = dict(type="glow", x=round(x, 2), z=round(z, 2), r=r, color=c)
    if show: d["showIf"] = show
    DEC.append(d)
def W(g): return g * CS
EMB, VIO, GLD, WHT = [1, .5, .3, .24], [.7, .42, 1, .24], [1, .8, .4, .22], [.75, .85, 1, .14]

# ------------------------------------------------------------------ floor plan (6 m cells; x east, z south)
F = {}
def rect(tag, x0, x1, z0, z1):
    for gx in range(x0, x1 + 1):
        for gz in range(z0, z1 + 1): F[(gx, gz)] = tag
rect("L", -3, 3, -2, 2)              # landing
rect("c1", -1, 0, -9, -3)            # causeway 1
rect("A", -6, 6, -18, -10)           # islet A
rect("c2", 0, 1, -24, -19)           # causeway 2 (gated at z=-21)
rect("B", -5, 5, -33, -25)           # islet B
rect("c3", 0, 1, -38, -34)           # bridge
rect("D", -6, 6, -50, -39)           # the Harbinger's arena

for (gx, gz) in sorted(F): put("SM_floor_module_02", W(gx), W(gz), 0, -2.4, 1.2)
blocked = set()
for (gx, gz) in F:
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if (gx + dx, gz + dz) not in F: blocked.add((gx + dx, gz + dz))
rows = {}
for (gx, gz) in blocked: rows.setdefault(gz, []).append(gx)
for gz, xs in rows.items():
    xs.sort(); s = prev = xs[0]
    for x in xs[1:] + [None]:
        if x is None or x != prev + 1:
            block(W((s + prev) / 2), W(gz), (prev - s + 1) * CS, CS); s = x
        if x is not None: prev = x
# a low broken rim of wall stones along the edge so the walkways read as ruins, not tiles
edge = [c for c in blocked if any((c[0] + dx, c[1] + dz) in F for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
for (gx, gz) in sorted(edge):
    if rng.random() < 0.22: put("SM_dg_wall", W(gx), W(gz), 0, 1.0 - 4.2 * 1.5 / 2, rng.uniform(0.6, 1.1), pre=DG)

# ------------------------------------------------------------------ props
def pillar(x, z, kind=None, sc=1.0):
    k = kind or rng.choice(["03", "04", "05"])
    put("SM_architecture_module_" + k, x, z, rng.choice([0, 90]), -2.4, sc); block(x, z, 1.5 * sc, 1.5 * sc)
def lamp(x, z, col, r=7.0):
    put("SM_lamp_big", x, z, 0, 0.0, 1.6); glow(x, z, r, col)
def crystal(x, z, rot=0, rad=5.0, col=VIO, sc=1.0):
    put("SM_dg_crystal", x, z, rot, 0, sc, pre=DG); block(x, z, 0.9 * sc, 0.9 * sc); glow(x, z, rad, col)
def brazier(x, z, rad=6.0, col=EMB):
    put("SM_dg_brazier", x, z, pre=DG); put("SM_dg_flame", x, z, 0, 1.55, 1.0, pre=DG); block(x, z, 1.1, 1.1); glow(x, z, rad, col)
def tablet(key, name, x, z, rot, text, ex=0, ez=1.8):
    put("SM_dg_tablet", x, z, rot, pre=DG); block(x, z, 1.6 if rot % 180 == 0 else 0.5, 0.5 if rot % 180 == 0 else 1.6)
    EV.append(dict(id=key, name=name, x=round(x + ex, 2), z=round(z + ez, 2), w=3.2, d=2.4, trigger="talk", prompt="Read the tablet",
                   actions=[dict(type="say", who="Etched Plate", text=text)]))
LOOT_ITEMS = {2: ["hi_potion", "ether", "antidote", "potion"], 3: ["hi_potion", "phoenix_down", "ether"]}
CHESTS = []
def make_loot(tier):
    r = rng.random(); loot = {}
    gold = {2: (550, 1150), 3: (950, 1900)}[tier]
    if r < 0.40: loot["gold"] = rng.randrange(gold[0], gold[1], 10)
    elif r < 0.65:
        loot["items"] = {rng.choice(LOOT_ITEMS[tier]): rng.randint(2, 4)}
        loot["gold"] = rng.randrange(gold[0] // 3, gold[1] // 3, 10)
    elif r < 0.80: loot["gems"] = rng.randint(*{2: (15, 35), 3: (30, 60)}[tier]); loot["gold"] = rng.randrange(gold[0] // 4, gold[1] // 4, 10)
    else:
        rar = rng.choices({2: ["epic", "legendary"], 3: ["legendary", "mythic"]}[tier], weights=[78, 22])[0]
        if EQ_IDS.get(rar): loot["equipment"] = [rng.choice(EQ_IDS[rar])]
        loot["shards"] = rng.randint(5, 25) * tier
    return loot
def chest(x, z, tier):
    key = "rc_c%d" % (len(CHESTS) + 1); rot = rng.choice([0, 90, 180, 270]); CHESTS.append(key)
    put("detail-crate", x, z, rot, 0, 5.0, key, pre=KEN); put("detail-crate-small", x, z, rot, 0, 5.0, "!" + key, pre=KEN)
    block(x, z, 1.6, 1.6)
    EV.append(dict(id=key, name="Treasure chest", x=round(x, 2), z=round(z, 2), w=4.2, d=4.2, trigger="talk", prompt="Open the chest", hideIf=key,
                   actions=[dict(type="flag", key=key), dict(type="chest", loot=make_loot(tier))]))
def gate(gx, gz, rot, key):
    x, z = W(gx), W(gz)
    put("SM_dg_gate", x, z, rot, 0, 1.5, key, pre=DG)
    block(x, z, 1.5 if rot else 6.0, 6.0 if rot else 1.5, key)

# ---- landing: where the rift gate drops you
lx, lz = 0, 0
put("SM_dg_dais", lx, lz - 3.0, 0, 0, 1.0, pre=DG)
put("SM_dg_crystal", lx, lz - 3.0, 0, 0, 2.4, pre=DG); block(lx, lz - 3.0, 2.4, 2.4); glow(lx, lz - 3.0, 12, GLD)
for sx in (-1, 1):
    for sz in (-1, 1):
        pillar(sx * 15.5, sz * 9.5, "05", 1.3); lamp(sx * 11, sz * 6.5, GLD, 8)
tablet("rc_t0", "Landing plate", -7.5, 4.0, 0, "THE REACH. WHEN THE FIRST DOOR WAS FORCED, THIS IS WHERE THE WORLD BROKE. WHAT YOU WALK ON IS WHAT WAS LEFT OVER.")
put("SM_dg_crystal", 9.0, 5.0, 40, 0, 1.2, pre=DG); block(9.0, 5.0, 1.2, 1.2); glow(9.0, 5.0, 7, [.4, .85, 1, .26])
EV.append(dict(id="rc_rest", name="Rest crystal", x=9.0, z=6.4, w=3.0, d=2.4, trigger="talk", prompt="Rest at the crystal",
               actions=[dict(type="say", who="", text="Soft light settles over the party. Wounds close and breath comes easy."), dict(type="rest")]))
put("SM_dg_block", -9.0, 5.0, 0, 0, 1.2, pre=DG); block(-9.0, 5.0, 1.2, 1.2)
EV.append(dict(id="rc_altar", name="Waking stone", x=-9.0, z=6.4, w=3.0, d=2.4, trigger="talk", prompt="Touch the stone",
               actions=[dict(type="say", who="Waking Stone", text="The stone hums against your palm. Across the Reach, the wardens reset and the gate slides shut."),
                        dict(type="reset_progress", prefix="rc_")]))
lamp(0, 11.0, WHT, 6); glow(0, 11.0, 4.5, [.7, .9, 1, .16])
EV.append(dict(id="rc_exit", name="Rift gate", x=0, z=11.6, w=6, d=3.2, trigger="talk", prompt="Step back through the rift to Outpost Kestrel",
               actions=[dict(type="warp", scene="asteroid", x=BASE[0], z=BASE[1])]))

# ---- islet A: ruined court, the Breach Warden at its north edge, a gate behind him
for sx in (-1, 1):
    for sz in (-1, 1):
        pillar(W(sx * 5.4), W(-14 + sz * 3.4), "05", 1.4); lamp(W(sx * 3.4), W(-14 + sz * 2.2), EMB, 9)
for k in range(8):
    a = k / 8 * math.tau; crystal(W(0) + math.cos(a) * 15.0, W(-14) + math.sin(a) * 11.0, int(a * 57), 5, EMB, 1.2)
chest(W(-5), W(-11), 2); chest(W(5), W(-17), 2)
tablet("rc_t1", "Court plate", 4.0, W(-10) - 2.0, 0, "THE FIRST COURT. THE WARDEN WAS A FORGE ONCE; THE BREACH GAVE IT A PURPOSE AND TOOK EVERYTHING ELSE.", ez=1.8)
NP.append(dict(id="rc_g1", name="Breach Warden", title="Hostile", sprite="Draven", x=round(W(0) + 3.0, 2), z=round(W(-18) + 1.5, 2), h=3.6, tint=[1.3, .8, .6, 1], hideIf="rc_g1", reach=5.5,
               actions=[dict(type="say", who="Breach Warden", text="THE SECOND COURT IS SEALED. THE HARBINGER WILL NOT BE DISTURBED."),
                        dict(type="battle", key="rc_g1", pool=["forge_juggernaut"], level_rel=[1, 2])]))
glow(W(0) + 3.0, W(-18) + 1.5, 12, EMB)
gate(0, -21, 0, "rc_g1"); gate(1, -21, 0, "rc_g1")
for gx in (0, 1):
    put("SM_arch_03", W(gx), W(-19), 0, 0, 0.8); put("SM_arch_04", W(gx), W(-22), 0, 0, 0.8)

# ---- islet B: the quiet before the bridge
for sx in (-1, 1):
    for sz in (-1, 1):
        pillar(W(sx * 4.2), W(-29 + sz * 3.0), "05", 1.4)
brazier(W(-2.5), W(-29), 8, GLD); brazier(W(2.5), W(-29), 8, GLD)
for k in range(6):
    a = k / 6 * math.tau; crystal(W(0) + math.cos(a) * 14.0, W(-29) + math.sin(a) * 9.0, int(a * 57), 5, VIO, 1.1)
chest(W(-4), W(-27), 3); chest(W(4), W(-31), 3)
tablet("rc_t2", "Bridge plate", -3.0, W(-33) + 3.0, 180, "BEYOND THIS BRIDGE: THE HARBINGER. IT HAS NOT BEEN IDLE. EVERY FIGHTER THE RAIDERS TOOK PASSED UNDER ITS HAND FIRST.", ez=-1.8)
put("SM_dg_crystal", W(-4), W(-27) + 3.0, 40, 0, 1.2, pre=DG); block(W(-4), W(-27) + 3.0, 1.2, 1.2); glow(W(-4), W(-27) + 3.0, 7, [.4, .85, 1, .26])
EV.append(dict(id="rc_rest2", name="Rest crystal", x=round(W(-4), 2), z=round(W(-27) + 4.4, 2), w=3.0, d=2.4, trigger="talk", prompt="Rest at the crystal",
               actions=[dict(type="say", who="", text="Soft light settles over the party. Wounds close and breath comes easy."), dict(type="rest")]))
for gz in (-34, -36, -38): put("SM_arch_03", W(0.5), W(gz), 0, 0, 1.4)

# ---- arena
ax, az = W(0), W(-45)
for sx in (-1, 1):
    for sz in (-1, 1):
        pillar(ax + sx * 32, az + sz * 21, "05", 1.5); lamp(ax + sx * 24, az + sz * 15, VIO, 10)
for k in range(10):
    a = k / 10 * math.tau; crystal(ax + math.cos(a) * 13, az + math.sin(a) * 12 + 2, int(a * 57), 5, VIO, 1.3)
glow(ax, az - 6, 16, VIO)
NP.append(dict(id="rc_boss", name="Rift Harbinger", title="Collector of Doors", sprite="Rook", x=round(ax, 2), z=round(az - 8, 2), h=4.4, tint=[.75, .5, 1.3, 1], hideIf="rc_boss", reach=6.5,
               actions=[dict(type="cine", on=True),
                        dict(type="music", url="/assets/Music/mp3/26. Demon King Castle (loop).mp3", intro="/assets/Music/mp3/26. Demon King Castle (intro).mp3"),
                        dict(type="cam", x=round(ax, 2), z=round(az - 8, 2), yaw=-6, pitch=8, dist=26, t=2.6),
                        dict(type="say", who=None, text="Something tall stands at the heart of the arena, robed in the same dark as the sky. It does not turn. It has been waiting."),
                        dict(type="say", who="Rift Harbinger", text="Three doors I opened. A fisherman's island. A sea of sand and cheering. A rock in the dark. Each one drew a fighter through."),
                        dict(type="say", who="Rift Harbinger", text="And now the best of them has walked to the hand that held the doors. How generous."),
                        dict(type="say", who="Kael", text="You took people from their homes. You made them fight. Give them back."),
                        dict(type="say", who="Rift Harbinger", text="Give them back? They were never lost. They were gathered. Come, then. Be gathered."),
                        dict(type="fade", to="black", t=0.9),
                        dict(type="title", text="RIFT HARBINGER", sub="Collector of Doors", t=3.2),
                        dict(type="battle", key="rc_boss", boss="rift_harbinger_boss")]))
EV.append(dict(id="rc_portal", name="Rift gate", x=round(ax, 2), z=round(az + 4, 2), w=5, d=3, trigger="talk", prompt="Step through the open rift to Outpost Kestrel", showIf="rc_boss",
               actions=[dict(type="warp", scene="asteroid", x=BASE[0], z=BASE[1])]))
glow(ax, az + 4, 8, [.7, .9, 1, .3], "rc_boss")
DEC.append(dict(type="glyph", x=round(ax, 2), z=round(az + 4, 2), r=3.4, spin=40, color=[.6, .85, 1, 1], showIf="rc_boss"))

# ---- the void: broken monoliths below, drifting rocks and arches round the ruins
rb = random.Random(4243)
for _ in range(40):
    nm = rb.choice(["09", "10", "13"]); sc = rb.uniform(2.0, 4.2)
    put("SM_architecture_module_" + nm, rb.uniform(-200, 200), rb.uniform(-380, 80), rb.choice([0, 90, 45]), -(21.4 * sc) - 8 - rb.uniform(0, 26), sc)
for _ in range(8):
    put("SM_triangle_arch", rb.uniform(-220, 220), rb.uniform(-380, 80), rb.uniform(0, 180), rb.uniform(-30, 30), rb.uniform(1.5, 2.6))

# ---- verify the plan: the gate must wall off islet B and the arena
def reach(start, opened):
    seen = {start}; q = deque([start]); walls = {(0, -21): "rc_g1", (1, -21): "rc_g1"}
    while q:
        c = q.popleft()
        for n in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)):
            if n in F and n not in seen and not (n in walls and walls[n] not in opened): seen.add(n); q.append(n)
    return seen
assert (0, -30) not in reach((0, 0), set()) and (0, -45) not in reach((0, 0), set())
assert len(reach((0, 0), {"rc_g1"})) == len(F)

def box(tags):
    cells = [c for c, t in F.items() if t in tags]
    xs = [c[0] for c in cells]; zs = [c[1] for c in cells]
    return dict(x=W((min(xs) + max(xs)) / 2), z=W((min(zs) + max(zs)) / 2), w=(max(xs) - min(xs) + 1) * CS, d=(max(zs) - min(zs) + 1) * CS)
def zone(tags, pool_ids, rel, rate): z = box(tags); z.update(pool=pool_ids, level_rel=rel, level=[16, 20], rate=rate); return z
ZONES = [zone(("c1", "A"), ["shard_sentry", "arc_drone", "rift_leech", "lattice_medic", "phase_hound"], [0, 2], 40),
         zone(("c2", "B", "c3"), ["forge_juggernaut", "null_reaper", "void_acolyte", "phase_hound", "frost_mirage"], [1, 3], 36)]
xs = [c[0] for c in F]; zs = [c[1] for c in F]
OBJ = [dict(unless="rc_g1", text="Fight across the floating ruins and defeat the Breach Warden to open the gate to the second court."),
       dict({"if": "rc_g1"}, unless="rc_boss", text="Cross the bridge and defeat the Rift Harbinger in its arena."),
       dict({"if": "rc_boss"}, text="The Harbinger has fallen. Step through the rift gate back to Outpost Kestrel.")]
AUTO = [dict(unless="rc_arrive", cine=True, actions=[
            dict(type="cine", on=True),
            dict(type="music", url="/assets/Music/mp3/14. Traveling the Sky.mp3"),
            dict(type="fade", to="clear", t=1.6, wait=False),
            dict(type="cam", x=0, z=-60, yaw=0, pitch=22, dist=60, t=0),
            dict(type="say", who=None, text="The rift lets go of you, and there is no floor but the one you stand on. Islands of old stone hang in a sky the colour of a bruise."),
            dict(type="cam", x=0, z=-150, yaw=0, pitch=18, dist=70, t=5.0, wait=False),
            dict(type="say", who="Lyra", text="The Reach. I have read about it, in a book that was supposed to be fiction. It is where the first door was forced, and the world has never healed."),
            dict(type="say", who="Kael", text="Then someone is still holding the doors open. Let's find them."),
            dict(type="flag", key="rc_arrive"), dict(type="follow", t=1.4)]),
        dict({"if": "rc_boss"}, unless="rc_end", cine=True, actions=[
            dict(type="cine", on=True),
            dict(type="music", url="/assets/Music/mp3/28. Holy Sanctuary.mp3"),
            dict(type="cam", x=round(ax, 2), z=round(az - 8, 2), yaw=-6, pitch=24, dist=22, t=0),
            dict(type="fade", to="clear", t=1.2, wait=False),
            dict(type="say", who=None, text="The Harbinger kneels. Its robe unravels into threads of dusk, and where it stood a seam of pale light hangs open in the air."),
            dict(type="say", who="Rift Harbinger", text="...You think... I was the hand? I was only... the door's keeper. The one who holds the doors... is still... out there."),
            dict(type="say", who="Lyra", text="Three doors, and a keeper that answers to someone. That is why the signal on the console would not resolve. There is a fourth coordinate, and it was never ours to read."),
            dict(type="say", who="Kael", text="Then we follow the signal. Whoever they are, they took people from their homes. That ends."),
            dict(type="flag", key="rc_end"), dict(type="follow", t=1.4)])]
d = dict(name="The Shattered Reach", kit="", tile=4, pieces=P, colliders=COL, npcs=NP, events=EV, decals=DEC, story=True, restart="rc_", autorun=AUTO, objectives=OBJ,
         encounters=dict(rate=40, level=[16, 20], level_rel=[0, 2], pool=ZONES[0]["pool"], zones=ZONES, text="The Reach stirs... something steps out of the broken sky!"),
         bounds=dict(minX=W(min(xs)) - 6, maxX=W(max(xs)) + 6, minZ=W(min(zs)) - 6, maxZ=W(max(zs)) + 6), spawn=dict(x=0, z=8), playerHeight=2.4,
         sky=dict(type="layers", base=dict(type="gradient", stops=[[0, "#05020c"], [.5, "#1a0a2a"], [1, "#4a1d3a"]]),
                  layers=[dict(url="/assets/Backgrounds/layers/stars.webp", y=.30, height=.66, parallax=.04, alpha=1, tint=[1.2, .9, 1.2]),
                          dict(url="/assets/Backgrounds/layers/planet.webp", y=.30, height=.9, parallax=.05, alpha=.85, tile=False, tint=[1.3, .8, .9]),
                          dict(url="/assets/Backgrounds/layers/stars.webp", y=.55, height=.5, parallax=.12, alpha=.5, tint=[1, .8, 1.2], drift=.002)]),
         fx=[dict(type="dust", amount=.25)],
         light=dict(dir=[-0.35, -1, -0.25], color=[0.85, 0.6, 0.8], ambient=[0.3, 0.22, 0.4]), fog=dict(color=[0.06, 0.02, 0.08], near=55, far=190))
d["music"] = {"url": "/assets/Music/mp3/14. Traveling the Sky.mp3"}
os.makedirs(OUT, exist_ok=True); json.dump(d, open(os.path.join(OUT, "reach.json"), "w"), separators=(",", ":"))
print("floor cells", len(F), "pieces", len(P), "colliders", len(COL), "npcs", len(NP), "events", len(EV), "chests", len(CHESTS), "bounds", d["bounds"])

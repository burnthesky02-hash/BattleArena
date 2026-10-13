"""Hollow Cave secret rooms (claude/cave-secret-rooms-oct-12.md). Applied to the finished scene dict by make_cave.py and restretch_cave_walls.py.

Two rooms cut into solid rock, none of them on the minimap (the minimap is drawn from the floor cells; the secret floors are separate):
  1  "Brask's Cache"   north of the Miners' camp: a rusted lever in the camp sinks the wall, a short tunnel leads to a treasure vault (three chests, the middle one legendary).
  2  "The Champion's Tomb" south of the Crypt: kneeling on a glowing seal sinks the wall, a tunnel leads to a tomb guarded by the Hollow Champion (mini boss, level 11).
Until the mechanism is used nothing of the room shows: the doorway is a block of the normal cave wall (piece group `ds_doorN`), and the floor and every prop of the room are
pieces tagged "R:<flag>" (built, but not drawn until a `reveal` action or the flag). The mechanism is a cutscene: shake, `reveal`, `slide` the door block down, flag `ds_openN`.
Flags: ds_open1 / ds_open2 (door open), ds_champ (boss beaten), dc_sec1a/b/c, dc_sec2 (chests). None of them start with dg_, so the waking stone does not reset them.
Engine side: hub3d.js actions slide / reveal / shake and the piece 8th element "G:group" (see the notes in claude/cave-secret-rooms-oct-12.md).
"""
import math, os, struct, json
import cave_walls as cw

CS = 4.0
SINK, HEIGHT, THICK = cw.SINK, cw.HEIGHT, cw.THICK
HALF = THICK * CS / 2
WALL = "/assets/3D/CaveCamp/SM_cv_wall_rock"
CC, DG, GEN = "/assets/3D/CaveCamp/", "/assets/3D/Dungeon/", "/assets/3D/Generated/"
WIN = 1.8            # half width (m) of the doorway cut out of the cave wall
DOOR_LEN = 2 * WIN + 1.8

SITES = [
    dict(n=1, c=(19, -132), dir=(0, -1), L=3, D=3, W=3, kind="cache"),
    dict(n=2, c=(18, -168), dir=(0, 1), L=3, D=4, W=5, kind="tomb"),
]


def _fl(v): return int(math.floor(v + 0.5))
def cell_of(x, z): return (_fl(x / CS), _fl(z / CS))
def _rot(a): return round(math.degrees(math.atan2(-a[1], a[0])) % 360, 2)            # y rotation that turns a model's x axis along the world vector a
def _face(v): return round(math.degrees(math.atan2(v[0], v[1])) % 360, 2)            # y rotation that turns a model's +z (its front) along v


class Site:
    def __init__(s, spec):
        s.__dict__.update(spec)
        dx, dz = s.dir; s.perp = (-dz, dx)
        s.O = (CS * s.c[0] + 2 * dx, CS * s.c[1] + 2 * dz)                                 # on the cave wall's face plane, in front of the doorway (t = 0)
        s.key = "ds_open%d" % s.n
        s.cells = set()
        for k in range(s.L): s.cells.add((s.c[0] + dx * (1 + k), s.c[1] + dz * (1 + k)))
        for r in range(s.D):
            for o in range(-(s.W // 2), s.W // 2 + 1):
                s.cells.add((s.c[0] + dx * (1 + s.L + r) + s.perp[0] * o, s.c[1] + dz * (1 + s.L + r) + s.perp[1] * o))
        s.sill = (s.c[0] + dx, s.c[1] + dz)
        s.t_room = CS * s.L; s.t_end = s.t_room + CS * s.D; s.hw = CS * s.W / 2

    def w(s, u, t):
        return (s.O[0] + s.perp[0] * u + s.dir[0] * t, s.O[1] + s.perp[1] * u + s.dir[1] * t)

    def rect(s, u, t, su, st):
        """axis-aligned box (x, z, w, d) for a thing centred at (u, t) that is su wide across and st deep along the tunnel"""
        x, z = s.w(u, t)
        return (x, z, st, su) if s.dir[0] else (x, z, su, st)


# --------------------------------------------------------------------------- walls
def _hash(x, z): return (int(abs(x * 73856093) + abs(z * 19349663)) & 0xFFFF) >> 3 & 1


def _strip(P, A, B, nout, e0, e1, inset, key=None, grp=None):
    """one stretched rock block whose cave-side face runs along A->B (world points); the rock lies on the nout side"""
    dx, dz = B[0] - A[0], B[1] - A[1]; L = math.hypot(dx, dz)
    d = (dx / L, dz / L); total = L + e0 + e1
    m = max(1, math.ceil(total / cw.MAXLEN)); each = total / m
    for q in range(m):
        s0 = -e0 + q * each; s1 = s0 + each + (0.4 if m > 1 else 0); c = (s0 + s1) / 2
        cx = A[0] + d[0] * c + nout[0] * (HALF - inset); cz = A[1] + d[1] * c + nout[1] * (HALF - inset)
        rot = _rot(d) + (180 if _hash(cx, cz) else 0)
        P.append([WALL, round(cx, 3), round(cz, 3), round(rot % 360, 2), -SINK, [round((s1 - s0) / CS, 3), HEIGHT, THICK]] + ([key] if key else []) + (["G:" + grp] if grp else []))


def _seg_rect_hit(cx, cz, a, hl, ht, rc):
    """oriented box (centre, unit axis a along the block, half length hl, half thickness ht) against the world-axis box rc = (xmin, xmax, zmin, zmax)"""
    b = (-a[1], a[0])                                                          # the block's local z axis in the world
    pts = [(rc[i], rc[j]) for i in (0, 1) for j in (2, 3)]
    for ax in ((1, 0), (0, 1), a, b):
        rb = hl * abs(a[0] * ax[0] + a[1] * ax[1]) + ht * abs(b[0] * ax[0] + b[1] * ax[1]); cc = cx * ax[0] + cz * ax[1]
        pr = [p[0] * ax[0] + p[1] * ax[1] for p in pts]
        if cc + rb < min(pr) or cc - rb > max(pr): return False
    return True


def _cut_doorway(P, S):
    """cut the doorway out of the cave wall: every wall block that touches it is replaced by the pieces left on either side; returns the door block's centre"""
    ux, uz = S.perp; dx, dz = S.dir
    u0, u1, t0, t1 = -WIN, WIN, -3.0, 8.5
    corners = [S.w(u, t) for u in (u0, u1) for t in (t0, t1)]
    rc = (min(p[0] for p in corners), max(p[0] for p in corners), min(p[1] for p in corners), max(p[1] for p in corners))
    out, hit, door_t = [], 0, None
    for p in P:
        if p[0] != WALL or p[4] != -SINK or len(p) > 6 or not isinstance(p[5], list):
            out.append(p); continue
        r = math.radians(p[3]); a = (math.cos(r), -math.sin(r)); hl = p[5][0] * CS / 2; ht = p[5][2] * CS / 2
        if not _seg_rect_hit(p[1], p[2], a, hl, ht, rc): out.append(p); continue
        if abs(a[0] * dx + a[1] * dz) > 0.35: raise RuntimeError("secret %d: the wall at the doorway is diagonal (axis %s)" % (S.n, a))
        hit += 1
        pr = [(c[0] - p[1]) * a[0] + (c[1] - p[2]) * a[1] for c in corners]; w0, w1 = min(pr), max(pr)
        if door_t is None: door_t = (p[1] - S.O[0]) * dx + (p[2] - S.O[1]) * dz           # the block's centre line, along the tunnel
        for lo, hi in ((-hl, w0), (w1, hl)):
            if hi - lo >= 0.8:
                c = (lo + hi) / 2; q = list(p); q[1] = round(p[1] + a[0] * c, 3); q[2] = round(p[2] + a[1] * c, 3); q[5] = [round((hi - lo) / CS, 3), p[5][1], p[5][2]]
                out.append(q)
    if not hit: raise RuntimeError("secret %d: no wall at the doorway" % S.n)
    P[:] = out
    return door_t


# --------------------------------------------------------------------------- colliders
def _subtract(c, hole):
    x0, x1, z0, z1 = c["x"] - c["w"] / 2, c["x"] + c["w"] / 2, c["z"] - c["d"] / 2, c["z"] + c["d"] / 2
    hx0, hx1, hz0, hz1 = hole
    if x1 <= hx0 or x0 >= hx1 or z1 <= hz0 or z0 >= hz1: return [c]
    res = []
    def add(a0, a1, b0, b1):
        if a1 - a0 > 0.05 and b1 - b0 > 0.05:
            q = dict(c); q.update(x=round((a0 + a1) / 2, 3), z=round((b0 + b1) / 2, 3), w=round(a1 - a0, 3), d=round(b1 - b0, 3)); res.append(q)
    add(x0, min(x1, hx0), z0, z1); add(max(x0, hx1), x1, z0, z1)
    add(max(x0, hx0), min(x1, hx1), z0, min(z1, hz0)); add(max(x0, hx0), min(x1, hx1), max(z0, hz1), z1)
    return res


def _runs(cells):
    rows = {}
    for (i, j) in cells: rows.setdefault(j, []).append(i)
    out = []
    for j, xs in rows.items():
        xs.sort(); s = prev = xs[0]
        for x in xs[1:] + [None]:
            if x is None or x != prev + 1:
                out.append({"x": CS * (s + prev) / 2, "z": CS * j, "w": (prev - s + 1) * CS, "d": CS}); s = x
            if x is not None: prev = x
    return out


# --------------------------------------------------------------------------- floors
def _write_floor(path, cells, img):
    import numpy as np
    from glbkit import write_glb
    pos, uv, idx = [], [], []
    for (i, j) in sorted(cells):
        x0, x1, z0, z1 = CS * i - 2, CS * i + 2, CS * j - 2, CS * j + 2; o = len(pos)
        pos += [(x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1)]; uv += [(x0 / 18, z0 / 18), (x1 / 18, z0 / 18), (x1 / 18, z1 / 18), (x0 / 18, z1 / 18)]
        idx += [(o, o + 3, o + 1), (o + 1, o + 3, o + 2)]
    nm = os.path.basename(path)[:-4]
    write_glb(path, np.array(pos, np.float32), np.tile([0, 1, 0], (len(pos), 1)).astype(np.float32), idx, nm, uv=np.array(uv, np.float32), img=img, color=(.6, .56, .54, 1))


# --------------------------------------------------------------------------- the builder
class Builder:
    def __init__(s, d, F, asset_dir, img):
        s.d, s.F, s.asset, s.img = d, F, asset_dir, img
        s.P, s.COL, s.EV, s.NP, s.DEC = d["pieces"], d["colliders"], d["events"], d["npcs"], d["decals"]

    # -- helpers for the room contents (u across the tunnel, t along it)
    def put(s, S, name, u, t, rot=0, y=0, sc=1.0, hide=None, pre=CC, show=None):
        x, z = S.w(u, t); tag = "R:" + S.key if hide is None and show is None else (("S:" + show) if show else hide)
        s.P.append([pre + name, round(x, 3), round(z, 3), rot, round(y, 3), sc, tag])

    def block(s, S, u, t, su, st, **kw):
        x, z, w, d = S.rect(u, t, su, st); c = {"x": round(x, 3), "z": round(z, 3), "w": round(w, 3), "d": round(d, 3)}; c.update(kw); s.COL.append(c)

    def glow(s, S, u, t, r, col, **kw):
        x, z = S.w(u, t); kw.setdefault("showIf", S.key); s.DEC.append(dict(type="glow", x=round(x, 2), z=round(z, 2), r=r, color=col, **kw))

    def event(s, S, id, name, u, t, su, st, **kw):
        x, z = S.w(u, t); e = dict(id=id, name=name, x=round(x, 2), z=round(z, 2), w=su, d=st); e.update(kw); s.EV.append(e)

    def brazier(s, S, u, t, col, flame="SM_cv_flame_gold", rad=8):
        s.put(S, "SM_dg_brazier", u, t, 0, 0, 1.2, pre=DG); s.put(S, flame, u, t, 0, 1.55 * 1.2, 1.2); s.block(S, u, t, 1.3, 1.3); s.glow(S, u, t, rad, col)

    def chest(s, S, key, u, t, loot, text, sc=1.0, y=0.0, face=None, show=None):
        x, z = S.w(u, t); fx, fz = face if face else (-S.dir[0], -S.dir[1])
        cond = "%s,!%s" % (show or S.key, key)
        s.P.append([GEN + "SM_TreasureChest", round(x, 3), round(z, 3), _face((fx, fz)), round(y, 3), sc, "S:" + cond])
        s.block(S, u, t, 1.7 * sc, 1.4 * sc, showIf=cond)
        s.event(S, key, "Treasure chest", u, t, 4.4, 4.4, trigger="talk", prompt="Open the chest", showIf=cond, actions=[dict(type="flag", key=key), dict(type="chest", loot=loot, text=text)])

    # -- door, floor, walls, colliders, hidden-until-opened state
    def shell(s, S):
        P = s.P
        door_t = _cut_doorway(P, S)
        # the door block: same rock as the walls around it, in the doorway; sinks into the ground when the mechanism fires
        dc = S.w(0, door_t); a = (S.perp[0], S.perp[1])
        P.append([WALL, round(dc[0], 3), round(dc[1], 3), _rot(a), -SINK, [round(DOOR_LEN / CS, 3), HEIGHT, THICK], S.key, "G:ds_door%d" % S.n])
        # walls around the tunnel and the room (cave-side faces tucked 0.3 / 0.7 m inside the floor edge, see cave_walls.GAP)
        pp, dd = S.perp, S.dir; neg = lambda v: (-v[0], -v[1])
        _strip(P, S.w(-2, 3.5), S.w(-2, S.t_room), neg(pp), 0, 0.6, 0.3); _strip(P, S.w(2, 3.5), S.w(2, S.t_room), pp, 0, 0.6, 0.3)
        _strip(P, S.w(-S.hw, S.t_room), S.w(-2, S.t_room), neg(dd), 3.0, 0.3, 0.7); _strip(P, S.w(2, S.t_room), S.w(S.hw, S.t_room), neg(dd), 0.3, 3.0, 0.7)
        _strip(P, S.w(-S.hw, S.t_room), S.w(-S.hw, S.t_end), neg(pp), 3.0, 3.0, 0.7); _strip(P, S.w(S.hw, S.t_room), S.w(S.hw, S.t_end), pp, 3.0, 3.0, 0.7)
        _strip(P, S.w(-S.hw, S.t_end), S.w(S.hw, S.t_end), dd, 3.0, 3.0, 0.7)
        # floor (invisible until the door opens)
        nm = "floor_sec%d" % S.n
        if s.asset:
            _write_floor(os.path.join(s.asset, nm + ".glb"), S.cells, s.img)
        P.append([CC + nm, 0, 0, 0, 0, 1, "R:" + S.key])
        # colliders: the doorway cell is solid while the door is shut, walls all round the tunnel and room
        sx, sz = CS * S.sill[0], CS * S.sill[1]; hole = (sx - 2, sx + 2, sz - 2, sz + 2); new = []
        for c in s.COL:
            new.extend(_subtract(c, hole) if "hideIf" not in c and "showIf" not in c else [c])
        s.COL[:] = new
        s.COL.append({"x": sx, "z": sz, "w": CS, "d": CS, "hideIf": S.key})
        ring = {(i + a, j + b) for (i, j) in S.cells for a in (-1, 0, 1) for b in (-1, 0, 1)} - S.cells - s.F
        ring.discard(S.sill)
        s.COL.extend(_runs(ring))
        # no random fights in there, and keep the scene bounds around it
        xs = [CS * i for i, j in S.cells]; zs = [CS * j for i, j in S.cells]
        zone = dict(x=(min(xs) + max(xs)) / 2, z=(min(zs) + max(zs)) / 2, w=max(xs) - min(xs) + CS * 3, d=max(zs) - min(zs) + CS * 3, safe=True)
        s.d["encounters"]["zones"].insert(0, zone)
        b = s.d["bounds"]; b["minX"] = min(b["minX"], min(xs) - 6); b["maxX"] = max(b["maxX"], max(xs) + 6); b["minZ"] = min(b["minZ"], min(zs) - 6); b["maxZ"] = max(b["maxZ"], max(zs) + 6)

    def ring_of_spots(s, S, d0, d1, near):
        """candidate (x, z) on the floor, between d0 and d1 metres from the doorway, nearest to `near` metres first (2 m grid)"""
        out = []
        for gx in range(-40, 41):
            for gz in range(-40, 41):
                x, z = S.O[0] + 2 * gx, S.O[1] + 2 * gz; dist = math.hypot(x - S.O[0], z - S.O[1])
                if d0 <= dist <= d1 and cell_of(x, z) in s.F: out.append((abs(dist - near), x, z))
        out.sort(); return [(x, z) for _, x, z in out]

    def free_spot(s, cands, r=2.6):
        """first candidate (x, z) that sits on floor with open floor all round and clear of props, events and npcs"""
        for (x, z) in cands:
            if any(cell_of(x + r * math.cos(a / 4 * math.pi), z + r * math.sin(a / 4 * math.pi)) not in s.F for a in range(8)): continue
            if any(math.hypot(p[1] - x, p[2] - z) < r + 0.8 for p in s.P if "wall_rock" not in p[0] and "/floor_" not in p[0] and "stalag" not in p[0]): continue
            if any(math.hypot(e["x"] - x, e["z"] - z) < r + 1.4 for e in s.EV) or any(math.hypot(n["x"] - x, n["z"] - z) < r + 1 for n in s.NP): continue
            return (x, z)
        raise RuntimeError("no free spot for a mechanism")

    def mechanism_cutscene(s, S, lead, tail):
        """shake, show the room, sink the door, flag; `lead` runs first (after the letterbox bars), `tail` before the camera comes back"""
        Ox, Oz = S.O
        return ([dict(type="cine", on=True)] + lead + [
            dict(type="cam", x=round(Ox, 2), z=round(Oz, 2), pitch=34, dist=26, t=1.5),
            dict(type="shake", t=3.2, amp=0.5), dict(type="reveal", key=S.key),
            dict(type="slide", grp="ds_door%d" % S.n, dx=0, dy=-13, dz=0, t=2.6), dict(type="wait", t=0.4)] + tail + [
            dict(type="flag", key=S.key), dict(type="follow", t=1.2)])

    # ---- 1. Brask's Cache
    def cache(s, S):
        # mechanism: a lever on the Miners' camp wall beside the doorway
        lx, lz = s.free_spot(s.ring_of_spots(S, 9, 24, 15), r=1.6)
        P = s.P
        P.append([DG + "SM_dg_block", round(lx, 3), round(lz, 3), 0, 0, [0.9, 0.55, 0.9]])
        P.append([CC + "SM_beam_01", round(lx, 3), round(lz, 3), 0, 0.5, 0.7, S.key])                        # lever up
        P.append([CC + "SM_cv_gem_gold", round(lx, 3), round(lz, 3), 0, 1.95, 0.7, S.key])
        P.append([CC + "SM_beam_01", round(lx, 3), round(lz, 3), 0, 0.5, [0.7, 0.35, 0.7], "S:" + S.key])     # lever pulled
        s.COL.append({"x": round(lx, 3), "z": round(lz, 3), "w": 1.1, "d": 1.1})
        s.DEC.append(dict(type="glow", x=round(lx, 2), z=round(lz, 2), r=5, color=[1, .8, .3, .6], hideIf=S.key))
        s.EV.append(dict(id="ds_lever1", name="Rusted lever", x=round(lx + S.dir[0] * -1.3, 2), z=round(lz + S.dir[1] * -1.3, 2), w=3.6, d=3.0, trigger="talk", prompt="Pull the lever", hideIf=S.key,
                         actions=s.mechanism_cutscene(S, [dict(type="say", who="", text="The lever is stiff with rust, but it gives. Deep in the rock, an old counterweight lets go with a groan.")],
                                                      [dict(type="say", who=None, text="Part of the wall sinks into the floor. Behind it, a narrow tunnel runs on into the dark: a sealed way the miners meant nobody to find.")])))
        s.EV.append(dict(id="ds_lever1_done", name="Rusted lever", x=round(lx + S.dir[0] * -1.3, 2), z=round(lz + S.dir[1] * -1.3, 2), w=3.6, d=3.0, trigger="talk", prompt="Look at the lever", showIf=S.key,
                         actions=[dict(type="say", who="", text="The lever hangs low. The wall it moved stands open, and the old tunnel waits.")]))
        s.EV.append(dict(id="ds_tablet1", name="Scratched plate", x=round(lx + S.dir[0] * -1.3 + S.perp[0] * 2.4, 2), z=round(lz + S.dir[1] * -1.3 + S.perp[1] * 2.4, 2), w=2.6, d=2.6, trigger="talk", prompt="Read the plate", actions=[
            dict(type="say", who="Scratched plate", text="BRASK'S LEVER. PULL IT WHEN THE VEIN RUNS DRY, AND NOT BEFORE. WHAT IS BEHIND IT IS MINE, AND I WILL KNOW.")]))
        P.append([DG + "SM_dg_block", round(lx + S.perp[0] * 2.4 + S.dir[0] * -1.0, 3), round(lz + S.perp[1] * 2.4 + S.dir[1] * -1.0, 3), 0, 0, [0.6, 1.1, 0.25]])
        # the vault
        GOLD, WARM = [1, .8, .3, .7], [1, .62, .25, .85]
        for u in (-4.6, 4.6):
            s.brazier(S, u, 14.2, WARM); s.brazier(S, u, 19.6, WARM)
        for u in (-4.9, 4.9):
            s.put(S, "SM_cv_crystal_gold", u, 22.4, 20 * (1 if u < 0 else -1), 0, 2.0); s.block(S, u, 22.4, 1.8, 1.8)
        s.glow(S, 0, 20, 12, GOLD); s.glow(S, 0, 14, 8, WARM)
        s.put(S, "SM_dg_dais", 0, 21.3, _rot(S.perp), 0, 0.3, pre=DG); s.block(S, 0, 21.3, 4.2, 2.4)
        for (u, t, sc, r) in ((-2.2, 17.2, 1.5, 30), (2.6, 16.8, 1.5, -20), (-5.0, 17.5, 1.5, 50), (5.2, 21.2, 1.5, 10)): s.put(S, "SM_bag", u, t, r, 0, sc)
        s.put(S, "SM_barrel_03", -5.0, 20.8, 0, 0, 1.5); s.block(S, -5.0, 20.8, 1.1, 1.1); s.put(S, "SM_barrel_02", 5.3, 18.4, 40, 0, 1.5); s.block(S, 5.3, 18.4, 1.2, 1.2)
        s.put(S, "SM_crate_01", 3.6, 13.8, 20, 0, 1.5); s.put(S, "SM_crate_01", 4.4, 13.9, -10, 0.63, 1.2)
        big = {"gold": 2500, "gems": 60, "shards": 120, "tickets": {"premium": 2}, "items": {"hi_potion": 5, "ether": 5, "phoenix_down": 3},
               "equipment": ["flameheart_blade", "staff_of_starfall", "heartstone_amulet", "unbreakable_bulwark"]}
        s.chest(S, "dc_sec1a", 0, 21.3, big, "Brask's hoard, kept back from the Colosseum. Inside", sc=1.5, y=0.45)
        s.chest(S, "dc_sec1b", -3.4, 22.2, {"gold": 1800, "gems": 30}, "A fat purse and a pouch of gems", face=S.perp)
        s.chest(S, "dc_sec1c", 3.4, 22.2, {"items": {"hi_potion": 8, "ether": 8, "phoenix_down": 4}, "shards": 80, "tickets": {"common": 5}}, "Supplies, laid by for a long siege", face=(-S.perp[0], -S.perp[1]))
        s.event(S, "ds_tablet1b", "Brask's ledger", 0, 14.4, 3.2, 2.6, trigger="talk", prompt="Read the ledger", showIf=S.key, actions=[
            dict(type="say", who="Brask's ledger", text="Foreman Brask, his hoard. Every coin the Colosseum paid for the miners' silence, and every stone I could carry out of the deep. If you are reading this, the miners kept their word and I did not. Spend it well.")])
        s.put(S, "SM_dg_tablet", 0.0, 13.2, _face(S.dir), 0, 0.8, pre=DG); s.block(S, 0, 13.2, 1.6, 0.6)

    # ---- 2. The Champion's Tomb
    def tomb(s, S):
        # mechanism: a glowing seal on the Crypt floor; kneel on it
        sx, sz = s.free_spot(s.ring_of_spots(S, 12, 30, 18), r=2.2)
        s.DEC.append(dict(type="glyph", x=round(sx, 3), z=round(sz, 2), r=2.4, spin=14, color=[.7, .45, 1, .85], hideIf=S.key))
        s.DEC.append(dict(type="glow", x=round(sx, 2), z=round(sz, 2), r=7, color=[.7, .42, 1, .5], hideIf=S.key))
        s.EV.append(dict(id="ds_seal2", name="Faded seal", x=round(sx, 2), z=round(sz, 2), w=4.0, d=4.0, trigger="talk", prompt="Kneel on the seal", hideIf=S.key,
                         actions=s.mechanism_cutscene(S, [dict(type="say", who="", text="You kneel on the seal. The glyph flares violet, and the stone under your knees hums like a struck bell.")],
                                                      [dict(type="say", who=None, text="A whole slab of the Crypt wall drops into the floor. Beyond it, a tunnel runs south into a cold, dry dark.")])))
        s.EV.append(dict(id="ds_seal2_done", name="Faded seal", x=round(sx, 2), z=round(sz, 2), w=4.0, d=4.0, trigger="talk", prompt="Look at the seal", showIf=S.key,
                         actions=[dict(type="say", who="", text="The seal has gone dark. Whatever it kept shut is open now.")]))
        tx, tz = sx + S.perp[0] * 3.2, sz + S.perp[1] * 3.2
        if cell_of(tx, tz) not in s.F: tx, tz = sx - S.perp[0] * 3.2, sz - S.perp[1] * 3.2
        s.P.append([DG + "SM_dg_tablet", round(tx, 3), round(tz, 3), _face((-S.dir[0], -S.dir[1])), 0, 1.0]); s.COL.append({"x": round(tx, 3), "z": round(tz, 3), "w": 1.6, "d": 1.6})
        s.EV.append(dict(id="ds_tablet2", name="Carved tablet", x=round(tx - S.dir[0] * 1.9, 2), z=round(tz - S.dir[1] * 1.9, 2), w=3.4, d=2.6, trigger="talk", prompt="Read the tablet", actions=[
            dict(type="say", who="Carved Tablet", text="THE SOVEREIGN'S LAST CHAMPION KNELT ON THIS SEAL TO SWEAR HIS OATH, AND WAS SEALED BELOW THE SOUTH WALL WITH HIS BLADE. THE SEAL STILL REMEMBERS THOSE WHO KNEEL.")]))
        VIO, ICE = [.7, .42, 1, .75], [.35, .75, 1, .8]
        # the tomb
        for u in (-8.3, 8.3):
            for t in (15.0, 23.0):
                s.put(S, "SM_dg_pillar", u, t, 0, 0, 1.3, pre=DG); s.block(S, u, t, 1.6, 1.6)
        for u, t in ((-5.2, 13.8), (5.2, 13.8), (-5.2, 26.0), (5.2, 26.0)): s.brazier(S, u, t, VIO, "SM_cv_flame_violet", 9)
        s.glow(S, 0, 21, 14, VIO); s.glow(S, 0, 15, 8, ICE)
        s.put(S, "SM_dg_throne", 0, 27.2, _face((-S.dir[0], -S.dir[1])), 0, 1.4, pre=DG); s.block(S, 0, 27.3, 4.2, 3.2)
        for u in (-6.4, 6.4):
            s.put(S, "SM_dg_sarcophagus", u, 20.5, _face(S.dir), 0, 1.4, pre=DG); s.block(S, u, 20.5, 2.2, 4.4)
        for u in (-3.2, 3.2): s.put(S, "SM_dg_brazier", u, 25.0, 0, 0, 1.0, pre=DG); s.block(S, u, 25.0, 1.1, 1.1)
        # the champion
        bx, bz = S.w(0, 22.0)
        s.NP.append(dict(id="ds_champ", name="Hollow Champion", title="Last Knight of the Drowned Court", sprite="Rook", x=round(bx, 2), z=round(bz, 2), h=3.4, tint=[.55, .55, .95, 1],
                         hideIf="ds_champ", showIf=S.key, reach=6.0, actions=[
                             dict(type="say", who="Hollow Champion", text="...You woke me. Good. The Court is empty, the king is drowned, and I have had no one to fight in a hundred years."),
                             dict(type="say", who="Hollow Champion", text="Draw your steel. I have not yet learned how to lose."),
                             dict(type="battle", key="ds_champ", boss="hollow_champion_boss", level=11)]))
        s.DEC.append(dict(type="glow", x=round(bx, 2), z=round(bz, 2), r=10, color=[.5, .5, 1, .45], showIf=S.key, hideIf="ds_champ"))
        s.event(S, "ds_champ_cs", "The Champion's Tomb", 0, 15.6, 14.0, 3.0, trigger="touch", once=False, showIf="%s,!ds_champ_seen,!ds_champ" % S.key, actions=[
            dict(type="cine", on=True), dict(type="flag", key="ds_champ_seen"),
            dict(type="cam", x=round(bx, 2), z=round(bz, 2), yaw=0, pitch=22, dist=20, t=2.2),
            dict(type="say", who=None, text="Violet fire wakes along the walls, one brazier after another. At the far end, before a broken throne, a knight in rusted gladiator plate stands with his sword point resting on the stone. He has been standing there a very long time."),
            dict(type="follow", t=1.2)])
        s.chest(S, "dc_sec2", 0, 24.4, {"gold": 900, "gems": 25, "shards": 60, "items": {"hi_potion": 4, "ether": 4, "phoenix_down": 2}, "equipment": ["talisman_of_the_veteran"]},
                "The Champion's spoils", sc=1.2, show="ds_champ")

    def build(s):
        for spec in SITES:
            S = Site(spec)
            s.shell(S)
            getattr(s, spec["kind"])(S)


def apply(d, F, asset_dir=None, img=None):
    """add both secret rooms to the scene dict d (floor cell set F); asset_dir = where floor_sec*.glb are written (None: not written)"""
    Builder(d, F, asset_dir, img).build()
    return d

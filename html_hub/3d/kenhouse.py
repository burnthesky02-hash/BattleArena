"""Modular building helper for the Kenney Retro Fantasy Kit, shared by make_island.py and make_forest.py.
A Town collects pieces [model, x, z, rotY, y, scale], colliders {x,z,w,d} and glow decals.  World axes: x east, z south.
Engine rotY turns a piece's +z towards +x (local->world: x = cx + dx*cos + dz*sin, z = cz - dx*sin + dz*cos).
Kit facts (all tiles are 1x1x1 at scale 1): wall-door's doorway faces -z at rot 0; roof-high-side has its eave at -x and its high edge at +x at rot 0."""
import math

KEN = "/assets/3D/kenney_retro-fantasy-kit/Models/GLB format/"
S = 2.8            # one tile in metres (walls are S high)
WALLS = {          # style -> (plain, window, door); {c} is the colour suffix
    "paint": ("wall-paint-{c}", "wall-paint-window-{c}", "wall-paint-door-{c}"),
    "stone": ("wall", "wall-window", "wall-door"),
    "pane": ("wall-pane-paint", "wall-pane-paint-window", "wall-pane-paint-door"),
    "wood": ("wall-pane-wood", "wall-pane-wood-window", "wall-pane-wood-door"),
}


class Town:
    def __init__(self, pa="/assets/3D/Paradise/"):
        self.P, self.COL, self.DEC = [], [], []
        self.pa = pa

    # ---- raw placement
    def put(self, n, x, z, rot=0, y=0, sc=1, spec=None):
        m = n if n.startswith("/") else self.pa + n
        e = [m, round(x, 3), round(z, 3), rot, round(y, 3), sc]
        if spec: e.append(spec)
        self.P.append(e)

    def ken(self, n, x, z, rot=0, y=0, sc=S, spec=None): self.put(KEN + n, x, z, rot, y, sc, spec)

    def block(self, x, z, w, d, hide=None):
        c = {"x": round(x, 3), "z": round(z, 3), "w": round(w, 3), "d": round(d, 3)}
        if hide: c["hideIf"] = hide
        self.COL.append(c)

    def glow(self, x, z, r, c): self.DEC.append(dict(type="glow", x=round(x, 2), z=round(z, 2), r=r, color=c))

    # ---- a gabled house: one or more 2-tile-wide blocks, ridge along the local z axis, front = local +z
    def house(self, cx, cz, rot, blocks, wall="paint", col="cream", roof="red", door_block=0, collide=True, spec=None, doorcol=None):
        """blocks = [(ox, oz, D, floors), ...] in tiles/metres: ox, oz are the block centre offset in metres (local), D is its depth in tiles.
        The door is on the front (+z) row of blocks[door_block]. Returns the world position just in front of the door."""
        a = math.radians(rot); c, s = math.cos(a), math.sin(a)
        def at(dx, dz): return cx + dx * c + dz * s, cz - dx * s + dz * c
        plain, win, dr = [w.format(c=col) for w in WALLS[wall]]
        front = None
        for bi, (ox, oz, D, fl) in enumerate(blocks):
            zs = [(-(D - 1) / 2 + k) * S for k in range(D)]
            for f in range(fl):
                for ix, lx in enumerate((-S / 2, S / 2)):
                    for k, lz in enumerate(zs):
                        first, last = k == 0, k == D - 1
                        if last: r_rel = 180                        # front (+z)
                        elif first: r_rel = 0                       # back (-z)
                        else: r_rel = 90 if ix == 0 else 270        # left / right side
                        if last: n = win if (ix == 1 or f > 0) else plain
                        elif first: n = win if (ix == 0 or f > 0) else plain
                        else: n = win if (k == D // 2 or f > 0) else plain
                        if last and f == 0 and bi == door_block and ix == 0:
                            n = dr; front = (ox + lx, oz + lz + S)
                        x, z = at(ox + lx, oz + lz)
                        self.ken(n, x, z, rot + r_rel, f * S, S, spec)
            for k, lz in enumerate(zs):                                  # roof: left slope then right slope
                x, z = at(ox - S / 2, oz + lz); self.ken("roof-high-side-" + roof, x, z, rot, fl * S, S, spec)
                x, z = at(ox + S / 2, oz + lz); self.ken("roof-high-side-" + roof, x, z, rot + 180, fl * S, S, spec)
            if collide:
                x, z = at(ox, oz); w_, d_ = 2 * S, D * S
                if rot % 180 == 90: w_, d_ = d_, w_
                self.block(x, z, w_ + 0.1, d_ + 0.1, spec if spec and not spec.startswith(("S:", "H:", "!")) else None)
        fx, fz = at(*front) if front else (cx, cz)
        return fx, fz, at

    # ---- small props
    def barrels(self, x, z, rot=0): self.ken("barrels", x, z, rot, 0, 2.2); self.block(x, z, 1.4, 0.8)
    def crate(self, x, z, rot=0, small=False): self.ken("detail-crate-small" if small else "detail-crate", x, z, rot, 0, 3.2); self.block(x, z, 1.0, 1.0)
    def fence(self, x0, z0, x1, z1, gap=1.6, sc=1.6):
        L = math.hypot(x1 - x0, z1 - z0); n = max(1, int(round(L / gap))); rot = math.degrees(math.atan2(-(z1 - z0), x1 - x0)) if False else (0 if abs(x1 - x0) >= abs(z1 - z0) else 90)
        for i in range(n):
            t = (i + 0.5) / n; self.ken("fence", x0 + (x1 - x0) * t, z0 + (z1 - z0) * t, rot, 0, sc)
        self.block((x0 + x1) / 2, (z0 + z1) / 2, abs(x1 - x0) + 0.4, abs(z1 - z0) + 0.4)
    def torch(self, x, z, hide=None):
        self.put("SM_pillar", x, z, 0, 0, 1.0); self.block(x, z, 0.6, 0.6); self.glow(x, z, 2.4, [1, 0.8, 0.45, 0.6])

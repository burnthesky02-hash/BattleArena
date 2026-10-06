"""Building helper for the StylizedIsland kit (see convert_stylized.py), used by make_island.py.
A Town collects pieces [model, x, z, rotY, y, scale], colliders {x,z,w,d} and glow decals.  World axes: x east, z south.
Engine rotY turns a piece's +z towards +x (local->world: x = cx + dx*cos + dz*sin, z = cz - dx*sin + dz*cos).
Kit facts (metres, scale 1): a wall module is 4 wide x 3 high x 0.35 thick, origin at its corner (x 0..4, z 0..0.35);
Roof_02 is the left slope half of a gable (x -4.09..0, z -3.85..0.15, eave y -0.18, ridge x=0 y~3.07); rot 180 gives the right half.
Roof_Wall is a gable triangle (left half, x -4..0).  Props are centred in x/z with the base on y=0 (see Assets/3D/Stylized/sizes.json).
y values passed to put() are RELATIVE to the terrain height at (x, z) (self.gy) unless abs_y=True."""
import math

ST = "/assets/3D/Stylized/"
WALL_TINTS = ("cream", "sand", "blue", "rose", "mint", "stone")      # -> files <piece>_w<tint>.glb  (made by convert_stylized.py --variants)
WT = 0.352                                                           # wall module thickness
ROOF_TINTS = ("red", "blue", "brown", "green", "slate")              # -> SM_Roof_02_r<tint>.glb


class Town:
    def __init__(self, gy=None):
        self.P, self.COL, self.DEC = [], [], []
        self.gy = gy or (lambda x, z: 0.0)

    def put(self, n, x, z, rot=0, y=0.0, sc=1, spec=None, abs_y=False):
        m = n if n.startswith("/") else ST + n
        yy = y if abs_y else self.gy(x, z) + y
        e = [m, round(x, 3), round(z, 3), round(rot, 2), round(yy, 3), sc]
        if spec: e.append(spec)
        self.P.append(e)

    def block(self, x, z, w, d, hide=None):
        c = {"x": round(x, 3), "z": round(z, 3), "w": round(w, 3), "d": round(d, 3)}
        if hide: c["hideIf"] = hide
        self.COL.append(c)

    def glow(self, x, z, r, c): self.DEC.append(dict(type="glow", x=round(x, 2), z=round(z, 2), r=r, color=c))

    # ---- a gabled house: footprint 8 m wide (2 bays) x 4*bays deep, ridge along local z, front = local +z, door in the front bay `door_bay` (0 = left)
    def house(self, cx, cz, rot, floors=1, bays=2, wall="cream", roof="red", door_bay=0, base=None, collide=True, spec=None, windows=True, skip=()):
        """Returns (door_x, door_z, at) where (door_x, door_z) is the spot 1.8 m in front of the door and at(dx, dz) maps house-local metres to world."""
        a = math.radians(rot); c, s = math.cos(a), math.sin(a)
        def at(dx, dz): return cx + dx * c + dz * s, cz - dx * s + dz * c
        by = self.gy(cx, cz) if base is None else base
        D = 4 * bays; sfx = "_w" + wall; rfx = "_r" + roof
        def w(n, lx, lz, rr, y):
            x, z = at(lx, lz); self.put(n + sfx, x, z, rot + rr, y, 1, spec, abs_y=True)
        lvl = {True: "normal", False: "none"}.get(windows, windows)        # windows: "none" | "few" (front only) | "normal" | "many" (every bay); True/False still work
        def win(side, f, k):
            if lvl == "none": return False
            if lvl == "many": return True
            if lvl == "few": return side == "front"
            return side == "front" or (f > 0 if side == "back" else (k % 2 == 1 or f > 0))
        for f in range(floors):
            y = by + 3 * f
            for i in range(2):                                              # front (+z) and back (-z)
                nm = "SM_Window_Wall_01" if win("front", f, i) else "SM_Large_Wall_02"
                if f == 0 and i == door_bay: nm = "SM_Door_Wall_01"
                w(nm, -4 + 4 * i, D / 2, 0, y)
                w("SM_Window_Wall_02" if win("back", f, i) else "SM_Large_Wall_02", 4 * i, -D / 2, 180, y)
            for k in range(bays):                                           # sides
                zs = -D / 2 + 4 * k
                nm = "SM_Window_Wall_02" if win("side", f, k) else "SM_Large_Wall_03"
                if 'R' not in skip: w(nm, 4 - WT, zs + 4, 90, y)          # side slabs sit x 3.648..4 so their outer face is flush with the front/back wall ends
                if 'L' not in skip: w(nm, -4 + WT, zs, 270, y)
        x, z = at(-4 + 4 * door_bay + 1.43, D / 2 + 0.175); self.put("SM_Door_01", x, z, rot, by, 1, spec, abs_y=True)      # the door leaf in its frame
        y = by + 3 * floors
        for k in range(bays):                                               # roof: left slope then right slope
            x, z = at(0, -D / 2 + 4 * k + 3.85); self.put("SM_Roof_02" + rfx, x, z, rot, y, 1, spec, abs_y=True)
            x, z = at(0, -D / 2 + 4 * k + 0.15); self.put("SM_Roof_02" + rfx, x, z, rot + 180, y, 1, spec, abs_y=True)
        for zz, lo in ((D / 2, 0.0), (-D / 2, -WT)):                        # gable triangles, flush with the wall slab (left half spans z -0.091..0.258, the rot-180 half -0.258..0.091)
            x, z = at(0, zz + lo + 0.091); self.put("SM_Roof_Wall" + sfx, x, z, rot, y, 1, spec, abs_y=True)
            x, z = at(0, zz + lo + 0.258); self.put("SM_Roof_Wall" + sfx, x, z, rot + 180, y, 1, spec, abs_y=True)
        if collide:
            x, z = at(0, 0); w_, d_ = 8.4, D + 0.8
            if rot % 180 == 90: w_, d_ = d_, w_
            self.block(x, z, w_, d_, spec if spec and not spec.startswith(("S:", "H:", "!")) else None)
        dx, dz = at(-2 + 4 * door_bay, D / 2 + 1.9)
        return dx, dz, at

    # ---- small props
    def barrel(self, x, z, rot=0): self.put("_Stylized_Barrel", x, z, rot, 0, 1.3); self.block(x, z, 1.0, 1.0)
    def box(self, x, z, rot=0, v=2): self.put("SM_Stylized_Box_var%d" % v, x, z, rot, 0, 1.3); self.block(x, z, 1.0, 1.0)
    def lamp(self, x, z, rot=0, hide=None):
        self.put("SM_Stylized_Lamp_C", x, z, rot, 0, 2.2); self.block(x, z, 0.5, 0.5); self.glow(x, z, 2.6, [1, 0.8, 0.45, 0.55])
    def fence(self, x0, z0, x1, z1, sc=1.0):
        L = math.hypot(x1 - x0, z1 - z0); n = max(1, int(round(L / 2.3))); rot = math.degrees(math.atan2(-(z1 - z0), (x1 - x0)))
        for i in range(n):
            t = (i + 0.5) / n; self.put("SM_Stylized_Fence_01", x0 + (x1 - x0) * t, z0 + (z1 - z0) * t, rot, 0, sc)
        self.block((x0 + x1) / 2, (z0 + z1) / 2, abs(x1 - x0) + 0.4, abs(z1 - z0) + 0.4)

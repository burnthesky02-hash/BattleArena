"""Hollow Cave walls built from long stretched rock blocks that follow the cave outline.

SM_cv_wall_rock.glb is a 4 x 6 x 4 m block with its base on y=0. Instead of one block per 4 m wall cell, the outline of the walkable floor is
traced, simplified to straight segments (they can run at any angle, so corners and diagonals work), and each segment becomes ONE block
scaled along its length, turned to follow the line. All blocks have the same height and thickness, and each overlaps its neighbours a little.

Used by make_cave.py (floor cells -> pieces) and restretch_cave_walls.py (rewrites an existing dungeon.json).
"""
import math

CS = 4.0              # cell size (m)
HEIGHT = 2.0          # y scale of every wall block (6 m mesh -> 12 m block)
SINK = 2.5            # blocks are lowered this far (m) below y=0 so they run down into the ground: top at 12-2.5 = 9.5 m
THICK = 1.3           # scale across the wall (4 m mesh -> 5.2 m thick)
TOL = 1.8             # how far (m) a straight segment may stray from the real (jagged, 4 m cell) floor outline
GAP = -1.0            # the mesh is a bumpy rock, not a box: at floor level its real face is ~0.7-1.0 m behind the 4 m bounding box (measured from the glb), so the nominal face is pushed this far (m) PAST the floor edge into the cave to make the rock itself reach the floor
MAXLEN = 20.0         # longest single block (m); longer walls are split into equal blocks (the rock texture is stretched along the length)
OVERLAP = 0.8         # each block extends this far past its ends (m), more on sharp corners, so neighbours overlap
MAXEXT = 3.0


def _loops(F):
    """Outline of the floor cells F as closed loops of lattice points (units of 2 m), floor on the LEFT of the direction of travel."""
    edges = {}
    for (i, j) in F:
        x0, x1, z0, z1 = 2 * i - 1, 2 * i + 1, 2 * j - 1, 2 * j + 1
        if (i + 1, j) not in F: edges.setdefault((x1, z0), []).append((x1, z1))
        if (i, j + 1) not in F: edges.setdefault((x1, z1), []).append((x0, z1))
        if (i - 1, j) not in F: edges.setdefault((x0, z1), []).append((x0, z0))
        if (i, j - 1) not in F: edges.setdefault((x0, z0), []).append((x1, z0))
    loops = []
    while edges:
        start = min(edges)
        loop, cur, prev = [start], None, None
        a = start
        while True:
            outs = edges[a]
            if len(outs) > 1 and prev is not None:          # pinch point: take the left-most turn so loops never cross
                dx, dz = a[0] - prev[0], a[1] - prev[1]
                outs.sort(key=lambda b: -((dx * (b[1] - a[1]) - dz * (b[0] - a[0]))))   # most positive cross product = left turn
            b = outs.pop(0)
            if not outs: del edges[a]
            prev, a = a, b
            if a == start: break
            loop.append(a)
            if a not in edges: break
        loops.append(loop)
    return loops


def _collapse(pts):
    """drop collinear points of a closed loop"""
    n, out = len(pts), []
    for k in range(n):
        p0, p1, p2 = pts[k - 1], pts[k], pts[(k + 1) % n]
        if (p1[0] - p0[0]) * (p2[1] - p1[1]) - (p1[1] - p0[1]) * (p2[0] - p1[0]) != 0: out.append(p1)
    return out


def _dp(pts, i0, i1, tol, keep):
    """Douglas-Peucker on pts[i0..i1] (inclusive, indices into pts); adds kept indices to `keep`"""
    ax, az = pts[i0]; bx, bz = pts[i1]; dx, dz = bx - ax, bz - az; L = math.hypot(dx, dz) or 1e-9
    best, bi = -1, -1
    for k in range(i0 + 1, i1):
        d = abs((pts[k][0] - ax) * dz - (pts[k][1] - az) * dx) / L
        if d > best: best, bi = d, k
    if best > tol:
        _dp(pts, i0, bi, tol, keep); keep.add(bi); _dp(pts, bi, i1, tol, keep)


def _simplify_loop(loop, tol):
    """closed loop (metres) -> indices of the corners to keep"""
    n = len(loop)
    if n <= 4: return list(range(n))
    far = max(range(n), key=lambda k: (loop[k][0] - loop[0][0]) ** 2 + (loop[k][1] - loop[0][1]) ** 2)
    keep = {0, far}
    ext = loop + [loop[0]]
    _dp(ext, 0, far, tol, keep); _dp(ext, far, n, tol, keep)
    return sorted(keep)


def segments(F, tol=TOL):
    """-> list of loops; each loop is a list of (A, B, path): a straight segment from A to B (metres) and the real outline points between them"""
    out = []
    for lp in _loops(F):
        pts = [(2.0 * x, 2.0 * z) for (x, z) in _collapse(lp)]
        if len(pts) < 3: continue
        keep = _simplify_loop(pts, tol)
        segs = []
        for a in range(len(keep)):
            i0, i1 = keep[a], keep[(a + 1) % len(keep)]
            path = pts[i0:i1 + 1] if i1 > i0 else pts[i0:] + pts[:i1 + 1]
            segs.append((pts[i0], pts[i1], path))
        out.append(segs)
    return out


def pieces(F, tol=TOL):
    """-> list of [x, z, rot, [sx, sy, sz]] wall blocks for the floor cell set F (rot = degrees about y; local x runs along the wall)"""
    res = []
    half = THICK * CS / 2

    def ext_at(u, v):
        """How far to run a block past its end. Only the inner (cave side) face is ever seen, so a block is extended only where the outline
        turns LEFT (floor corner sticking out: carrying straight on leaves the floor). At a right turn (rock sticking into the cave) the blocks
        already meet at the vertex, and extending would push the wall into the walkable floor."""
        lu, lv = math.hypot(*u), math.hypot(*v)
        if lu < 1e-6 or lv < 1e-6: return OVERLAP
        ang = math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])        # + = left turn
        if ang > 0.09: return min(MAXEXT, OVERLAP + 2.0 * math.tan(min(ang, 2.4) / 2))
        if ang < -0.09: return 0.15
        return OVERLAP

    for segs in segments(F, tol):
        n = len(segs)
        for k, (A, B, path) in enumerate(segs):
            dx, dz = B[0] - A[0], B[1] - A[1]; L = math.hypot(dx, dz)
            if L < 1e-6: continue
            d = (dx / L, dz / L)
            ln, rn = (-d[1], d[0]), (d[1], -d[0])           # left (floor side) / right (rock side) normals
            dl = [((p[0] - A[0]) * ln[0] + (p[1] - A[1]) * ln[1]) for p in path]
            gap, bulge = max(dl), -min(dl)                   # real edge on the floor side of the chord (gap) / on the rock side (bulge)
            off = GAP - gap          # shift of the wall's inner face from the chord, towards the rock when positive
            P0, N0 = segs[k - 1], segs[(k + 1) % n]
            ea = ext_at((A[0] - P0[0][0], A[1] - P0[0][1]), (dx, dz)) if n > 1 else OVERLAP
            eb = ext_at((dx, dz), (N0[1][0] - N0[0][0], N0[1][1] - N0[0][1])) if n > 1 else OVERLAP
            total = L + ea + eb
            m = max(1, math.ceil(total / MAXLEN)); each = total / m
            for q in range(m):
                s0 = -ea + q * each; s1 = s0 + each + (0.4 if m > 1 else 0)     # sub-blocks overlap a little too
                c = (s0 + s1) / 2; length = s1 - s0
                cx = A[0] + d[0] * c + rn[0] * (off + half); cz = A[1] + d[1] * c + rn[1] * (off + half)
                rot = math.degrees(math.atan2(-d[1], d[0]))
                h = int(abs(cx * 73856093) + abs(cz * 19349663)) & 0xFFFF
                if (h >> 3) & 1: rot += 180                  # flip some blocks so the rock texture does not repeat the same way
                res.append([round(cx, 3), round(cz, 3), round(rot % 360, 2), [round(length / CS, 3), HEIGHT, THICK]])
    return res

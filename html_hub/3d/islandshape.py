"""Shape of the big island, shared by gen_island_meshes.py (ground + colours) and make_island.py (shore colliders, planting).
World axes: x east, z south. The island is a wobbly ellipse centred on (CX, CZ); q = 1 is the waterline, q < FLAT is the flat walkable top."""
import numpy as np
CX, CZ, RX, RZ = 0.0, -22.0, 62.0, 56.0
FLAT = 0.88
def q_of(X, Z):
    qx = (np.asarray(X, float) - CX) / RX; qz = (np.asarray(Z, float) - CZ) / RZ
    ang = np.arctan2(qz, qx); wob = 1 + 0.06 * np.sin(ang * 3 + 1.0) + 0.04 * np.sin(ang * 5 + 2.3) + 0.025 * np.sin(ang * 8 + 0.4)
    return np.hypot(qx, qz) / wob

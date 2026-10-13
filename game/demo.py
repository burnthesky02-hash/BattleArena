"""Demo build switches. The packaged demo (tools/build_demo.py) ships a generated top-level module `demo_build`
(DEMO = True plus the asset-pack key); the normal game has no such module, so DEMO is False.
Set BATTLE_ARENA_DEMO=1 to try the demo rules from a source checkout (no pack, files read normally)."""
import os

try:
    import demo_build as _build
    DEMO = bool(getattr(_build, "DEMO", False))
except ImportError:
    _build = None
    DEMO = os.environ.get("BATTLE_ARENA_DEMO", "").lower() in ("1", "true", "yes")

# The only 3D scenes the demo can enter: Paradise Island, the Whispering Wood and the two fishing spots.
DEMO_SCENES = ("island", "forest", "fish_pier", "fish_pond")
# Everything past the Hollow Cave (kept out of the demo pack, and refused by the server).
LATE_SCENES = ("dungeon", "prison", "olympus", "outside", "plaza", "asteroid", "vault", "reach", "strange", "eldergate", "veyra")
DEMO_END_TEXT = ("That is the end of the demo. Thanks for playing Skyborne Saga! "
                 "The Hollow Cave stays sealed for now, but you are welcome to keep exploring the island and the "
                 "Whispering Wood, fish, hunt for treasure and fight on.")


def pak_key() -> bytes:
    """The asset-pack key, assembled from the two halves the build baked into demo_build."""
    if _build is None or not hasattr(_build, "_A"):
        return b""
    return bytes(a ^ b for a, b in zip(_build._A, _build._B))

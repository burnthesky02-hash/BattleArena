"""Loads the overworld's actual content -- towns, a connecting field, one
dungeon, and the warp back into the Colosseum hub -- from JSON files under
data/maps/ instead of hardcoding it here as Python.

That split happened so Andrew's map builder (html_builder/index.html) can
paint a map and hit Save and have it take effect immediately: the builder's
save endpoint (hub_server.py) writes the edited map straight to its JSON
file via game/world.py's save_map_to_dir(), then calls reload_world_maps()
below, which re-reads every file in data/maps/ and refreshes WORLD_MAPS *in
place*. That "in place" part matters -- every other module in this project
did `from data.world_data import WORLD_MAPS` at import time, which binds to
this exact dict object, not a name that gets re-looked-up later. Reassigning
WORLD_MAPS to a new dict here wouldn't be seen by them; clearing and
re-populating the same dict is.

Sprites are reused battle idle/run sheets (data/Battlers/<Name>/) as
placeholder overworld art for NPCs, same as before -- real overworld/NPC art
can swap those names out later without touching game/world.py, hub_server.py,
or these JSON files at all, since nothing here cares whether a sheet is
"real" or a placeholder. (The player's own avatar has real walk-cycle art --
see assets/walking/ and html_overworld/index.html.)

Map layout, unchanged from the original hand-built version: HAVEN_TOWN <->
FIELD_ROAD <-> EMBER_TOWN, with FIELD_ROAD also dropping south into
DUNGEON_HOLLOW. HAVEN_TOWN additionally has a warp tile that opens the
Colosseum hub (the pre-existing game) instead of another map. See
data/maps/*.json for the actual tile grids, NPCs, and warps, and
html_builder/index.html to edit them visually instead of by hand.
"""
import json
from pathlib import Path
from typing import Dict

from game.world import MapDef, load_maps_from_dir

MAPS_DIR = Path(__file__).resolve().parent / "maps"
META_PATH = MAPS_DIR / "_meta.json"

DEFAULT_START_MAP = "haven_town"


def _load_meta() -> dict:
    if META_PATH.is_file():
        try:
            return json.loads(META_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {}


WORLD_MAPS: Dict[str, MapDef] = {}
START_MAP = DEFAULT_START_MAP


def reload_world_maps() -> None:
    """Re-reads data/maps/*.json (and _meta.json's start_map) from disk and refreshes WORLD_MAPS
    *in place* -- see the module docstring for why that has to be clear()+update() rather than a
    reassignment. Called once at import time below, and again by the map builder's save endpoint
    (hub_server.py's _handle_builder_save) so an edit takes effect without restarting the server."""
    global START_MAP
    meta = _load_meta()
    START_MAP = meta.get("start_map", START_MAP)
    fresh = load_maps_from_dir(MAPS_DIR)
    WORLD_MAPS.clear()
    WORLD_MAPS.update(fresh)


reload_world_maps()

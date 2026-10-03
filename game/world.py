"""The overworld: tile-based maps the player walks around on between fights,
with towns, a dungeon, NPCs, and a warp back into the Colosseum hub (the
original whole game, before this pass -- see data/world_data.py's module
docstring for how that fits together).

Movement is server-authoritative, same spirit as everything else in this
project: the client only ever sends a direction, this module decides whether
it's legal, rolls encounters, and is the one thing that updates
PlayerState.world_*. That keeps hub_server.py's handlers thin (see
_handle_world_move/_handle_world_interact) and means there's exactly one
place that can desync a player's position from what they're actually
looking at.

Sentinel: WARP_TO_COLOSSEUM is used as a Warp's target_map instead of a real
map id to mean "leave the overworld and open the Colosseum hub ('/')" --
stepping onto one of these does NOT change world_map/world_x/world_y, so the
player is standing right back outside the entrance the next time they walk
out of the hub.

Maps themselves live as JSON files under data/maps/ (one per map, plus
_meta.json for START_MAP), loaded by load_maps_from_dir() below -- not
hardcoded Python anymore. That's what lets html_builder/index.html (Andrew's
paint-and-place map builder) save a map by just writing its JSON file and
telling the running server to reload, instead of needing generated Python
code pasted back into the source. map_to_dict()/map_from_dict() (and the
matching npc_*/warp_* helpers) are the full round-trip used for that --
MapDef.serialize() above is a *different*, gameplay-only trimmed-down view
handed to the overworld client, not suitable for editing.

Tiles used to be a fixed 5-character legend ('.'/','/'#'/'T'/'~'). Now
they're a palette: MapDef.tiles is a grid of tile-palette ids (arbitrary
strings, e.g. "grass1"), each one a crop out of some sheet image, described
by a TileKind in the module-level TILE_PALETTE dict below (floor/encounter/
blocked walkability lives on the TileKind, not hardcoded per-character
anymore). Standalone obstacles like the big tree are no longer baked into a
tile at all -- they're PropKind entries in PROP_PALETTE, placed on top of a
tile via MapDef.props ({"prop_id","x","y"} per placement), the same way an
NPC or a warp is a separate thing sitting on a tile rather than the tile
itself. Both palettes are backed by data/tile_palette.json and
data/prop_palette.json (falling back to the hand-picked defaults below when
those files don't exist yet), and are hot-reloaded in place the same way
WORLD_MAPS is (see reload_tile_palette()/reload_prop_palette()) so
html_builder/index.html's Tile Chooser can add a new palette entry and have
it usable immediately, no restart.
"""
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from game.player_state import PlayerState

WARP_TO_COLOSSEUM = "__COLOSSEUM__"

DIRECTIONS: Dict[str, Tuple[int, int]] = {
    "up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0),
}

DEFAULT_NPC_SPRITE = "Draven"   # same fallback battler the client's Actor.loadSheet chain lands on


# ----------------------------------------------------------------------
# Tile/prop palette -- see the module docstring above. Loaded from
# data/tile_palette.json / data/prop_palette.json, falling back to these
# hand-picked defaults (the same crops the hardcoded 5-tile legend used to
# point at) so a fresh checkout with no palette files still renders
# correctly. TILE_PALETTE/PROP_PALETTE are the live registries other
# modules import by name (data.world_data, hub_server) -- reload_*() below
# mutates them in place (.clear()+.update()) rather than rebinding, same
# reason reload_world_maps() does that for WORLD_MAPS: a `from module import
# TILE_PALETTE` elsewhere binds to this exact dict object.
# ----------------------------------------------------------------------
_PALETTE_DIR = Path(__file__).resolve().parent.parent / "data"
TILE_PALETTE_PATH = _PALETTE_DIR / "tile_palette.json"
PROP_PALETTE_PATH = _PALETTE_DIR / "prop_palette.json"


@dataclass
class TileKind:
    id: str
    label: str
    category: str          # "floor" (walkable) | "encounter" (walkable, rolls fights) | "blocked"
    sheet_url: str
    sheet_w: int
    sheet_h: int
    x: int                 # crop rect within the sheet, in the sheet's own native pixels
    y: int
    size: int              # crop is always a `size`x`size` square


@dataclass
class PropKind:
    id: str
    label: str
    image_url: str          # its own standalone image (not a crop out of a bigger sheet)
    image_w: int
    image_h: int
    height_tiles: float = 1.0   # rendered height, in tile-widths, taller than 1 lets it rise above its cell
    blocking: bool = True       # False for a decorative prop you can walk through (e.g. a small plant)


_DEFAULT_TILE_PALETTE: Dict[str, dict] = {
    "grass1": {"label": "Grass", "category": "encounter",
               "sheet_url": "/assets/tilesets/forest/forestground06dv5.png", "sheet_w": 629, "sheet_h": 679,
               "x": 140, "y": 100, "size": 40},
    "floor1": {"label": "Floor / Path", "category": "floor",
               "sheet_url": "/assets/tilesets/forest/forestground06dv5.png", "sheet_w": 629, "sheet_h": 679,
               "x": 180, "y": 500, "size": 40},
    "stone1": {"label": "Stone", "category": "blocked",
               "sheet_url": "/assets/tilesets/forest/forestground06dv5.png", "sheet_w": 629, "sheet_h": 679,
               "x": 90, "y": 410, "size": 40},
    "water1": {"label": "Water", "category": "blocked",
               "sheet_url": "/assets/tilesets/forest/watertileset3qb2tg0.png", "sheet_w": 410, "sheet_h": 331,
               "x": 60, "y": 140, "size": 40},
}

_DEFAULT_PROP_PALETTE: Dict[str, dict] = {
    "tree1": {"label": "Big Tree", "image_url": "/assets/tilesets/forest/big_tree_bshadow.png",
              "image_w": 281, "image_h": 255, "height_tiles": 1.6, "blocking": True},
    "plant1": {"label": "Plant", "image_url": "/assets/tilesets/forest/plant2.png",
               "image_w": 225, "image_h": 205, "height_tiles": 1.0, "blocking": False},
    "stump1": {"label": "Tree Stump", "image_url": "/assets/tilesets/forest/treetrunk2006bu8.png",
               "image_w": 143, "image_h": 122, "height_tiles": 0.8, "blocking": True},
}

TILE_PALETTE: Dict[str, TileKind] = {}
PROP_PALETTE: Dict[str, PropKind] = {}


def _read_palette_json(path: Path, default: Dict[str, dict]) -> Dict[str, dict]:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return dict(default)


def load_tile_palette() -> Dict[str, TileKind]:
    raw = _read_palette_json(TILE_PALETTE_PATH, _DEFAULT_TILE_PALETTE)
    return {tid: TileKind(id=tid, **fields) for tid, fields in raw.items()}


def load_prop_palette() -> Dict[str, PropKind]:
    raw = _read_palette_json(PROP_PALETTE_PATH, _DEFAULT_PROP_PALETTE)
    return {pid: PropKind(id=pid, **fields) for pid, fields in raw.items()}


def reload_tile_palette() -> None:
    fresh = load_tile_palette()
    TILE_PALETTE.clear()
    TILE_PALETTE.update(fresh)


def reload_prop_palette() -> None:
    fresh = load_prop_palette()
    PROP_PALETTE.clear()
    PROP_PALETTE.update(fresh)


def save_tile_palette() -> None:
    _PALETTE_DIR.mkdir(parents=True, exist_ok=True)
    data = {t.id: {"label": t.label, "category": t.category, "sheet_url": t.sheet_url,
                   "sheet_w": t.sheet_w, "sheet_h": t.sheet_h, "x": t.x, "y": t.y, "size": t.size}
            for t in TILE_PALETTE.values()}
    TILE_PALETTE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def save_prop_palette() -> None:
    _PALETTE_DIR.mkdir(parents=True, exist_ok=True)
    data = {p.id: {"label": p.label, "image_url": p.image_url, "image_w": p.image_w, "image_h": p.image_h,
                   "height_tiles": p.height_tiles, "blocking": p.blocking}
            for p in PROP_PALETTE.values()}
    PROP_PALETTE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def tile_kind_to_dict(t: TileKind) -> dict:
    return {"id": t.id, "label": t.label, "category": t.category, "sheet_url": t.sheet_url,
            "sheet_w": t.sheet_w, "sheet_h": t.sheet_h, "x": t.x, "y": t.y, "size": t.size}


def prop_kind_to_dict(p: PropKind) -> dict:
    return {"id": p.id, "label": p.label, "image_url": p.image_url, "image_w": p.image_w,
            "image_h": p.image_h, "height_tiles": p.height_tiles, "blocking": p.blocking}


reload_tile_palette()
reload_prop_palette()


@dataclass
class NPC:
    id: str
    name: str
    x: int
    y: int
    sprite: str                       # Battler folder to reuse (data/Battlers/<sprite>/) -- falls back
                                       # to Draven the same way a hero with no sheet of their own does.
    lines: List[str] = field(default_factory=list)
    facing: str = "down"
    # Talking to this NPC starts a real battle right after their dialogue closes. With no boss_id, it's
    # a plain build_scaled_battle fight, same as a random encounter -- for an NPC that should just pick
    # a fight. With boss_id set (a key into data/bosses.WORLD_BOSSES), hub_server.py instead runs that
    # BossDef's real script (game/boss_script.py's BossRunner) -- used for the dungeon's guardian so the
    # "at least one dungeon" slice has an actual scripted boss room, not a generic encounter wearing a
    # boss's name.
    battle: bool = False
    boss_id: Optional[str] = None
    # Talking to this NPC also offers a link to an existing hub screen (e.g. "/shop") -- lets a town NPC
    # double as a real shortcut instead of being pure flavor text.
    navigate: Optional[str] = None


@dataclass
class Warp:
    x: int
    y: int
    target_map: str                   # a real map id, or WARP_TO_COLOSSEUM
    target_x: int = 0
    target_y: int = 0
    target_facing: str = "down"
    label: str = ""


@dataclass
class MapDef:
    id: str
    name: str
    tiles: List[List[str]]            # rows, top to bottom; each cell is a TILE_PALETTE id
    npcs: List[NPC] = field(default_factory=list)
    warps: List[Warp] = field(default_factory=list)
    props: List[dict] = field(default_factory=list)   # [{"prop_id","x","y"}, ...] -- see PROP_PALETTE
    spawn: Tuple[int, int] = (1, 1)
    spawn_facing: str = "down"
    encounter_chance: float = 0.12

    def height(self) -> int:
        return len(self.tiles)

    def width(self) -> int:
        return len(self.tiles[0]) if self.tiles else 0

    def tile_at(self, x: int, y: int) -> Optional[str]:
        """Returns the TILE_PALETTE id at (x, y), or None if that cell is off the map (treated as
        blocked, same as an unknown/removed palette id -- see is_walkable)."""
        if y < 0 or y >= len(self.tiles):
            return None
        row = self.tiles[y]
        return row[x] if 0 <= x < len(row) else None

    def prop_at(self, x: int, y: int) -> Optional[dict]:
        return next((p for p in self.props if p.get("x") == x and p.get("y") == y), None)

    def is_walkable(self, x: int, y: int) -> bool:
        kind = TILE_PALETTE.get(self.tile_at(x, y))
        if kind is None or kind.category == "blocked":
            return False
        prop = self.prop_at(x, y)
        if prop is not None:
            pkind = PROP_PALETTE.get(prop.get("prop_id"))
            if pkind is not None and pkind.blocking:
                return False
        return True

    def is_encounter_tile(self, x: int, y: int) -> bool:
        kind = TILE_PALETTE.get(self.tile_at(x, y))
        return kind is not None and kind.category == "encounter"

    def npc_at(self, x: int, y: int) -> Optional[NPC]:
        return next((n for n in self.npcs if n.x == x and n.y == y), None)

    def warp_at(self, x: int, y: int) -> Optional[Warp]:
        return next((w for w in self.warps if w.x == x and w.y == y), None)

    def npc_in_front_of(self, x: int, y: int, facing: str) -> Optional[NPC]:
        dx, dy = DIRECTIONS.get(facing, (0, 1))
        return self.npc_at(x + dx, y + dy)

    def serialize(self) -> dict:
        return {
            "id": self.id, "name": self.name,
            "tiles": [list(row) for row in self.tiles],
            "props": [dict(p) for p in self.props],
            "width": self.width(), "height": self.height(),
            "npcs": [{"id": n.id, "name": n.name, "x": n.x, "y": n.y,
                      "sprite": n.sprite, "facing": n.facing} for n in self.npcs],
            "warps": [{"x": w.x, "y": w.y, "label": w.label,
                       "colosseum": w.target_map == WARP_TO_COLOSSEUM} for w in self.warps],
        }


def ensure_spawned(player_state: PlayerState, maps: Dict[str, "MapDef"], default_map: str) -> None:
    """Called once at server startup (and it's cheap to call again any time): makes sure
    player_state.world_map actually names a map that still exists, falling back to the default map's
    spawn point otherwise. Covers both a brand-new save (world_map starts "") and an old save from
    before the overworld existed (same empty-string default -- see save_system.py)."""
    if player_state.world_map in maps:
        return
    start = maps[default_map]
    player_state.world_map = default_map
    player_state.world_x, player_state.world_y = start.spawn
    player_state.world_facing = start.spawn_facing


def move_player(player_state: PlayerState, maps: Dict[str, "MapDef"], direction: str) -> dict:
    """Resolves one step. Always updates facing (bumping into a wall just turns you, same as any
    JRPG); only advances position when the destination tile is walkable AND not occupied by an NPC.
    Returns a plain dict the HTTP handler can hand straight to _send_json -- see its shape used in
    hub_server.py's _handle_world_move."""
    current = maps.get(player_state.world_map)
    if current is None or direction not in DIRECTIONS:
        return {"ok": False, "message": "Nowhere to go from here."}
    dx, dy = DIRECTIONS[direction]
    x, y = player_state.world_x, player_state.world_y
    nx, ny = x + dx, y + dy
    player_state.world_facing = direction

    blocking_npc = current.npc_at(nx, ny)
    if not current.is_walkable(nx, ny) or blocking_npc is not None:
        return {"ok": True, "moved": False, "blocked": "npc" if blocking_npc else "wall",
                "player": _player_payload(player_state)}

    player_state.world_x, player_state.world_y = nx, ny

    warp = current.warp_at(nx, ny)
    if warp is not None:
        if warp.target_map == WARP_TO_COLOSSEUM:
            # Position is left exactly where they stepped -- walking back out of the hub drops them
            # right at the entrance they used.
            return {"ok": True, "moved": True, "colosseum": True, "player": _player_payload(player_state)}
        target = maps.get(warp.target_map)
        if target is not None:
            player_state.world_map = warp.target_map
            player_state.world_x, player_state.world_y = warp.target_x, warp.target_y
            player_state.world_facing = warp.target_facing
            return {"ok": True, "moved": True, "map_changed": True, "map": target.serialize(),
                     "player": _player_payload(player_state)}

    encounter = current.is_encounter_tile(nx, ny) and random.random() < current.encounter_chance
    return {"ok": True, "moved": True, "encounter": bool(encounter), "player": _player_payload(player_state)}


def interact(player_state: PlayerState, maps: Dict[str, "MapDef"]) -> dict:
    """Talks to whatever NPC is directly in front of the player, if any."""
    current = maps.get(player_state.world_map)
    if current is None:
        return {"ok": False, "message": "Nowhere to talk to anyone."}
    npc = current.npc_in_front_of(player_state.world_x, player_state.world_y, player_state.world_facing)
    if npc is None:
        return {"ok": True, "npc": None}
    return {"ok": True, "npc": {"id": npc.id, "name": npc.name, "sprite": npc.sprite, "lines": list(npc.lines)},
            "battle": npc.battle or bool(npc.boss_id), "boss_id": npc.boss_id, "navigate": npc.navigate}


def _player_payload(player_state: PlayerState) -> dict:
    return {"map": player_state.world_map, "x": player_state.world_x, "y": player_state.world_y,
            "facing": player_state.world_facing}


# ----------------------------------------------------------------------
# JSON round-trip -- full fidelity (unlike MapDef.serialize() above, which
# trims warps/NPCs down to what the *playing* client needs). Used by the map
# builder to load a map for editing and to save one back out.
# ----------------------------------------------------------------------
def npc_from_dict(d: dict) -> NPC:
    return NPC(
        id=d["id"], name=d.get("name", d["id"]), x=int(d["x"]), y=int(d["y"]),
        sprite=d.get("sprite") or DEFAULT_NPC_SPRITE, lines=list(d.get("lines") or []),
        facing=d.get("facing", "down"), battle=bool(d.get("battle", False)),
        boss_id=(d.get("boss_id") or None), navigate=(d.get("navigate") or None),
    )


def npc_to_dict(n: NPC) -> dict:
    return {"id": n.id, "name": n.name, "x": n.x, "y": n.y, "sprite": n.sprite,
            "facing": n.facing, "lines": list(n.lines), "battle": n.battle,
            "boss_id": n.boss_id, "navigate": n.navigate}


def warp_from_dict(d: dict) -> Warp:
    return Warp(
        x=int(d["x"]), y=int(d["y"]), target_map=d["target_map"],
        target_x=int(d.get("target_x", 0)), target_y=int(d.get("target_y", 0)),
        target_facing=d.get("target_facing", "down"), label=d.get("label", ""),
    )


def warp_to_dict(w: Warp) -> dict:
    return {"x": w.x, "y": w.y, "target_map": w.target_map, "target_x": w.target_x,
            "target_y": w.target_y, "target_facing": w.target_facing, "label": w.label}


def map_from_dict(d: dict) -> MapDef:
    return MapDef(
        id=d["id"], name=d.get("name", d["id"]),
        tiles=[list(row) for row in d["tiles"]],
        npcs=[npc_from_dict(n) for n in d.get("npcs", [])],
        warps=[warp_from_dict(w) for w in d.get("warps", [])],
        props=[{"prop_id": p["prop_id"], "x": int(p["x"]), "y": int(p["y"])} for p in d.get("props", [])],
        spawn=tuple(d.get("spawn", [1, 1])), spawn_facing=d.get("spawn_facing", "down"),
        encounter_chance=float(d.get("encounter_chance", 0.12)),
    )


def map_to_dict(m: MapDef) -> dict:
    return {
        "id": m.id, "name": m.name, "tiles": [list(row) for row in m.tiles],
        "npcs": [npc_to_dict(n) for n in m.npcs],
        "warps": [warp_to_dict(w) for w in m.warps],
        "props": [dict(p) for p in m.props],
        "spawn": list(m.spawn), "spawn_facing": m.spawn_facing,
        "encounter_chance": m.encounter_chance,
    }


def load_maps_from_dir(path: Path) -> Dict[str, MapDef]:
    """Reads every data/maps/*.json file (skipping _meta.json and anything else starting with
    "_") into a fresh {map_id: MapDef} dict. Doesn't touch any existing registry -- see
    data/world_data.py's reload_world_maps() for how the result gets installed."""
    result: Dict[str, MapDef] = {}
    if not path.is_dir():
        return result
    for f in sorted(path.glob("*.json")):
        if f.name.startswith("_"):
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        m = map_from_dict(data)
        result[m.id] = m
    return result


def save_map_to_dir(path: Path, m: MapDef) -> None:
    """Writes one map's JSON file (data/maps/<id>.json), overwriting it if present. The map
    builder's save endpoint calls this and then data.world_data.reload_world_maps() so the
    live server picks the change up immediately."""
    path.mkdir(parents=True, exist_ok=True)
    target = path / (m.id + ".json")
    target.write_text(json.dumps(map_to_dict(m), indent=2) + "\n", encoding="utf-8")

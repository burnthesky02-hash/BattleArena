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
"""
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from game.player_state import PlayerState

WARP_TO_COLOSSEUM = "__COLOSSEUM__"

# Tile legend (see data/world_data.py for the actual maps):
#   '#' wall / obstacle       -- blocks movement
#   '.' floor                 -- walkable, no encounters
#   ',' tall grass            -- walkable, random encounters roll here
#   'T' tree, '~' water       -- decorative obstacles, same as '#'
WALKABLE_TILES = {".", ","}
ENCOUNTER_TILES = {","}
BLOCKED_TILES = {"#", "T", "~"}

DIRECTIONS: Dict[str, Tuple[int, int]] = {
    "up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0),
}


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
    tiles: List[str]                  # rows, top to bottom; see legend above
    npcs: List[NPC] = field(default_factory=list)
    warps: List[Warp] = field(default_factory=list)
    spawn: Tuple[int, int] = (1, 1)
    spawn_facing: str = "down"
    encounter_chance: float = 0.12

    def height(self) -> int:
        return len(self.tiles)

    def width(self) -> int:
        return len(self.tiles[0]) if self.tiles else 0

    def tile_at(self, x: int, y: int) -> str:
        if y < 0 or y >= len(self.tiles):
            return "#"
        row = self.tiles[y]
        return row[x] if 0 <= x < len(row) else "#"

    def is_walkable(self, x: int, y: int) -> bool:
        return self.tile_at(x, y) in WALKABLE_TILES

    def is_encounter_tile(self, x: int, y: int) -> bool:
        return self.tile_at(x, y) in ENCOUNTER_TILES

    def npc_at(self, x: int, y: int) -> Optional[NPC]:
        return next((n for n in self.npcs if n.x == x and n.y == y), None)

    def warp_at(self, x: int, y: int) -> Optional[Warp]:
        return next((w for w in self.warps if w.x == x and w.y == y), None)

    def npc_in_front_of(self, x: int, y: int, facing: str) -> Optional[NPC]:
        dx, dy = DIRECTIONS.get(facing, (0, 1))
        return self.npc_at(x + dx, y + dy)

    def serialize(self) -> dict:
        return {
            "id": self.id, "name": self.name, "tiles": list(self.tiles),
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

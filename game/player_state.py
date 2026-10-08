"""PlayerState: everything that persists across battles and save/load for a
single playthrough -- the roster, both currencies, consumable inventory, and
owned-but-not-equipped gear. One save file holds exactly one PlayerState
(see game/save_system.py); there's no multi-save-slot support yet since
Andrew hasn't asked for one and nothing here would need to change to add it
later (save_system.py already takes an explicit path).
"""
from dataclasses import dataclass, field
from typing import Dict, List, TYPE_CHECKING

from game.equipment_instances import EquipmentInstance
from game.roster import PlayerCharacter

if TYPE_CHECKING:
    # Avoids a player_state.py <-> legacy.py import cycle at module load: legacy.py imports
    # PlayerState itself, so this side can only see LegacyItem as a type-checking-only forward ref.
    from game.legacy import LegacyItem

STARTING_MONEY = 100
STARTING_GEMS = 20


@dataclass
class PlayerState:
    characters: List[PlayerCharacter] = field(default_factory=list)
    money: int = 0
    gems: int = 0
    inventory: Dict[str, int] = field(default_factory=dict)        # consumable item_id -> count
    # Every equipment instance ever created (game/equipment_instances.py), keyed by instance id --
    # includes both stash AND currently-equipped copies (a PlayerCharacter.equipped value is one of
    # these keys). `equipment_stash` lists which instance ids are unequipped right now; an instance
    # falls out of both once nothing references it (there's no discard yet, so in practice this only
    # shrinks via save-migration dedup).
    equipment_instances: Dict[str, EquipmentInstance] = field(default_factory=dict)
    equipment_stash: List[str] = field(default_factory=list)
    # Legacy items (game/legacy.py) a fallen hero leaves behind -- same "every instance ever created,
    # plus which ones are unequipped right now" shape as equipment_instances/equipment_stash above. A
    # PlayerCharacter's `equipped_legacies` (game/roster.py) holds a list of these ids.
    legacy_instances: Dict[str, "LegacyItem"] = field(default_factory=dict)
    legacy_stash: List[str] = field(default_factory=list)
    # Character ids selected on the last confirmed party-selection screen
    # (see game/party.py), capped at MAX_PARTY_SIZE. Empty on a fresh
    # new_game -- game/party.py's default_party_ids falls back to the first
    # MAX_PARTY_SIZE roster members whenever this is empty or stale.
    active_party: List[str] = field(default_factory=list)
    # Ids of bosses (data/bosses.py) the player has beaten at least once -- the first
    # clear pays a bigger bonus than rematches. Missing from old saves -> empty.
    cleared_bosses: List[str] = field(default_factory=list)
    # Bestiary: enemy/boss name -> {"seen": fights it appeared in, "defeated": fights won against it}. Missing from old saves -> empty.
    bestiary: Dict[str, Dict[str, int]] = field(default_factory=dict)
    # The arena team: after the hero is freed from the Pit they must BUY a Colosseum team (hub_server.py's
    # /api/arena/buy_team: gold + one free automatic summon). Until then the Colosseum roster is empty -- the story
    # party (Mythic heroes) and the arena party are two separate groups. Missing from old saves -> derived on load.
    arena_team_bought: bool = False
    # The Colosseum ladder (game/renown.py): your rank, and the renown meter within it.
    rank: int = 1
    renown: int = 0
    # Summon tickets (data/summon_pool.py TICKET_KINDS): "common" and "premium" counts.
    tickets: Dict[str, int] = field(default_factory=lambda: {"common": 0, "premium": 0})
    # Equipment shards (data/summon_pool.py EQUIPMENT_SHARD_*): the dedicated currency for equipment
    # summons, replacing the old Premium-Ticket option for gear. Earned via a small per-win drop chance
    # (game/rewards.py) and salvaging owned gear (game/shop.py's salvage_equipment); spent
    # EQUIPMENT_SHARD_SUMMON_COST at a time in game/summon.py's pay="shards" option. Missing from old
    # saves -> 0, same convention as every other currency here.
    equipment_shards: int = 0
    # Where the player is standing in the overworld (game/world.py, data/world_data.py) -- new as of
    # the JRPG-overworld pass. world_map is a map id from data/world_data.WORLD_MAPS, or "" for a save
    # that predates the overworld / hasn't been placed on a map yet; hub_server.py calls
    # game.world.ensure_spawned() once at startup to drop any such save onto the starting map's spawn
    # point, exactly like a brand-new game gets via new_game() below. The Colosseum hub itself
    # (everything this project did before this pass) is unaffected either way -- it's reached by
    # walking onto a warp tile in the overworld, not by anything stored here.
    world_map: str = ""
    world_x: int = 0
    world_y: int = 0
    world_facing: str = "down"
    # The fishing mini-game (game/fishing.py): owned rods, bait packs, the fish log. A plain dict so the shape can grow;
    # game.fishing.fstate() fills in defaults, so an old save (no key) just means "nothing caught yet, driftwood rod".
    fishing: Dict[str, object] = field(default_factory=dict)

    def add_tickets(self, won: Dict[str, int]) -> None:
        for k, n in (won or {}).items():
            self.tickets[k] = max(0, self.tickets.get(k, 0) + int(n))

    def add_equipment_shards(self, amount: int) -> None:
        self.equipment_shards = max(0, self.equipment_shards + int(amount))

    @classmethod
    def new_game(cls, hero: PlayerCharacter) -> "PlayerState":
        from data.items_db import STARTING_INVENTORY  # local import: avoids a data/ <-> game/ import cycle at module load
        # Local import for the same reason: data/world_data.py imports game/world.py, which imports
        # PlayerState (this class) for typing -- importing it at module load here would be a cycle.
        from data.world_data import START_MAP, WORLD_MAPS
        start = WORLD_MAPS[START_MAP]
        return cls(
            characters=[hero], money=STARTING_MONEY, gems=STARTING_GEMS,
            inventory=dict(STARTING_INVENTORY),
            world_map=START_MAP, world_x=start.spawn[0], world_y=start.spawn[1],
            world_facing=start.spawn_facing,
        )

    def add_rewards(self, money: int, gems: int) -> None:
        self.money += max(0, money)
        self.gems += max(0, gems)

    def add_equipment_to_stash(self, inst: EquipmentInstance) -> None:
        """Registers a freshly-created instance (game/equipment_instances.new_instance) and drops it in
        the stash. The one place anything -- Shop, Summon, the debug menu, save migration -- adds gear,
        so nothing can register an instance without also making it reachable from the stash."""
        self.equipment_instances[inst.instance_id] = inst
        self.equipment_stash.append(inst.instance_id)

    def take_from_stash(self, instance_id: str) -> bool:
        """Removes one instance id from the stash (it's presumably about to be equipped). False if it
        wasn't there."""
        try:
            self.equipment_stash.remove(instance_id)
        except ValueError:
            return False
        return True

    def return_to_stash(self, instance_id: str) -> None:
        if instance_id and instance_id in self.equipment_instances:
            self.equipment_stash.append(instance_id)

    def add_legacy_to_stash(self, item: "LegacyItem") -> None:
        self.legacy_instances[item.instance_id] = item
        self.legacy_stash.append(item.instance_id)

    def take_legacy_from_stash(self, instance_id: str) -> bool:
        try:
            self.legacy_stash.remove(instance_id)
        except ValueError:
            return False
        return True

    def return_legacy_to_stash(self, instance_id: str) -> None:
        if instance_id and instance_id in self.legacy_instances:
            self.legacy_stash.append(instance_id)

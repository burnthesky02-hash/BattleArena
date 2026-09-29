"""Save/load for PlayerState, as plain JSON on disk.

Single fixed save slot for now (SAVE_PATH) -- both functions take an
explicit path anyway so adding multiple slots later is just a caller-side
change, not a rewrite. Writes go to a temp file and get os.replace()'d into
place so a crash or interrupted write can't leave a half-written,
unparsable save file sitting at SAVE_PATH.
"""
import json
import os

from game import equipment_instances as _eq_inst
from game import renown as _renown
from game.equipment_instances import EquipmentInstance
from game.legacy import LegacyItem
from game.player_state import PlayerState
from game.roster import PlayerCharacter

# BATTLE_ARENA_HOME lets the launcher / packaged .exe keep saves next to the app instead of inside the bundle.
_HOME = os.environ.get("BATTLE_ARENA_HOME") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE_DIR = os.path.join(_HOME, "saves")
SAVE_PATH = os.path.join(SAVE_DIR, "save1.json")

SAVE_FORMAT_VERSION = 1


def save_exists(path: str = SAVE_PATH) -> bool:
    return os.path.isfile(path)


def save_game(state: PlayerState, path: str = SAVE_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {
        "version": SAVE_FORMAT_VERSION,
        "money": state.money,
        "gems": state.gems,
        "equipment_shards": state.equipment_shards,
        "inventory": state.inventory,
        "equipment_instances": {
            iid: {"base_id": inst.base_id, "bonus_stats": inst.bonus_stats}
            for iid, inst in state.equipment_instances.items()
        },
        "equipment_stash": list(state.equipment_stash),
        "legacy_instances": {
            iid: {"hero_name": item.hero_name, "hero_class_id": item.hero_class_id,
                  "rarity": item.rarity, "bonuses": item.bonuses}
            for iid, item in state.legacy_instances.items()
        },
        "legacy_stash": list(state.legacy_stash),
        "characters": [
            {"id": c.id, "name": c.name, "class_id": c.class_id, "equipped": c.equipped,
             "level": c.level, "xp": c.xp,
             "rarity": c.rarity, "stars": c.stars, "shards": c.shards,
             "skill_ranks": dict(c.skill_ranks),
             "equipped_legacies": list(c.equipped_legacies),
             "wounded_runs_remaining": c.wounded_runs_remaining,
             "formation": c.formation}
            for c in state.characters
        ],
        "active_party": list(state.active_party),
        "cleared_bosses": list(state.cleared_bosses),
        "rank": state.rank,
        "renown": state.renown,
        "tickets": dict(state.tickets),
        # World position is new as of the JRPG-overworld pass -- see game/player_state.py's fields.
        "world_map": state.world_map,
        "world_x": state.world_x,
        "world_y": state.world_y,
        "world_facing": state.world_facing,
    }
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)


def _migrate_equipment(data: dict) -> tuple:
    """Pre-equipment-overhaul saves have no "equipment_instances" key at all: `owned_equipment` was a
    plain {base_id: count} stash and each character's `equipped` values were base catalog ids directly.
    Migrates both into instances (see game/equipment_instances.py) -- every migrated instance has an
    empty bonus roll (never a summon pull, so "only the summoned gear" gets random stats stays true even
    retroactively). An id no longer in the catalog is dropped, same as an unknown equipped id always was.
    Returns (instances: Dict[str, EquipmentInstance], stash_ids: List[str],
    equipped_migration: Dict[old_base_id, new_instance_id] -- one fresh instance per OWNED unit, reused
    by identical equipped slots so two heroes both wielding a migrated "rusty_sword" don't fight over
    one instance)."""
    from data.equipment_db import EQUIPMENT as _DB   # local import: avoids a data/ <-> game/ cycle at module load
    instances: dict = {}
    stash_ids: list = []
    equipped_migration: dict = {}   # base_id -> instance id, first-come reused for every equipped slot with that id
    for base_id, count in data.get("owned_equipment", {}).items():
        if base_id not in _DB:
            continue
        for _ in range(max(0, int(count))):
            inst = _eq_inst.new_instance(base_id, rolled=False, equipment_db=_DB)
            instances[inst.instance_id] = inst
            stash_ids.append(inst.instance_id)
    for c in data.get("characters", []):
        for slot, val in (c.get("equipped") or {}).items():
            if not val or val not in _DB:
                continue
            if val not in equipped_migration:
                inst = _eq_inst.new_instance(val, rolled=False, equipment_db=_DB)
                instances[inst.instance_id] = inst
                equipped_migration[val] = inst.instance_id
    return instances, stash_ids, equipped_migration


def load_game(path: str = SAVE_PATH) -> PlayerState:
    with open(path) as f:
        data = json.load(f)
    migrating = "equipment_instances" not in data
    migrated_instances, migrated_stash, equipped_migration = (
        _migrate_equipment(data) if migrating else ({}, [], {}))

    def _equipped_for(c: dict) -> dict:
        raw = dict(c.get("equipped") or {})
        if not migrating:
            return raw
        # A migrated character's equipped values are still base catalog ids -- swap in the instance
        # id new_instance minted for that id (equipped_migration), one shared instance per base id.
        return {slot: equipped_migration.get(val) if val else None for slot, val in raw.items()}

    characters = [
        PlayerCharacter(id=c["id"], name=c["name"], class_id=c["class_id"], equipped=_equipped_for(c),
                         # level/xp are new as of the level-curve pass -- default to level 1/0 XP so a
                         # save written before this stage still loads (an old file simply won't have
                         # the keys, not a version bump; SAVE_FORMAT_VERSION only tracks breaking changes).
                         level=c.get("level", 1), xp=c.get("xp", 0),
                         # rarity/stars/shards are new as of the hero-rarity pass -- same story: a save
                         # written before this feature has none of these keys, so default to "a plain,
                         # never-upgraded hero" (exactly what every character was before this existed).
                         rarity=c.get("rarity", "common"), stars=c.get("stars", 1), shards=c.get("shards", 0),
                         # skill_ranks is new as of the skill-rank/talent-point pass -- an old save has
                         # no such key, so default to {} (every skill starts at rank 1, same as it
                         # always implicitly was before ranks existed).
                         skill_ranks=dict(c.get("skill_ranks", {})),
                         # equipped_legacies is new as of the legacy-item pass -- an old save has no
                         # such key, so default to [] (nobody had any legacy items before this existed).
                         equipped_legacies=list(c.get("equipped_legacies", [])),
                         # wounded_runs_remaining is new as of the death-penalty rework (permanent
                         # death -> temporary benching) -- an old save (including one from the original
                         # legacy-item pass, which still had permanent death) has no such key, so
                         # default to 0 (nobody's mid-recovery before this existed).
                         wounded_runs_remaining=int(c.get("wounded_runs_remaining", 0)),
                         # formation is new as of the battle-formations pass -- an old save has no such
                         # key, so default to "middle" (engine/formation.py's DEFAULT_FORMATION), same
                         # as a freshly created PlayerCharacter gets.
                         formation=c.get("formation", "middle"))
        for c in data.get("characters", [])
    ]
    if migrating:
        instances = migrated_instances
        stash = migrated_stash
    else:
        instances = {
            iid: EquipmentInstance(instance_id=iid, base_id=rec.get("base_id", ""),
                                   bonus_stats=dict(rec.get("bonus_stats", {})))
            for iid, rec in data.get("equipment_instances", {}).items()
        }
        stash = list(data.get("equipment_stash", []))
    legacy_instances = {
        iid: LegacyItem(instance_id=iid, hero_name=rec.get("hero_name", ""),
                        hero_class_id=rec.get("hero_class_id", ""),
                        rarity=rec.get("rarity", "common"), bonuses=dict(rec.get("bonuses", {})))
        for iid, rec in data.get("legacy_instances", {}).items()
    }
    legacy_stash = list(data.get("legacy_stash", []))
    return PlayerState(
        characters=characters,
        money=data.get("money", 0),
        gems=data.get("gems", 0),
        # equipment_shards is new as of the equipment-summon rebalance pass -- an old save has no such
        # key, so default to 0 (nobody had banked any before this currency existed). NOTE: this key was
        # missing from both save_game and load_game for one prior commit this session -- a save made in
        # that window would have silently lost its shard balance on the next save/load round-trip; this
        # fix closes that gap going forward.
        equipment_shards=data.get("equipment_shards", 0),
        inventory=dict(data.get("inventory", {})),
        equipment_instances=instances,
        equipment_stash=stash,
        legacy_instances=legacy_instances,
        legacy_stash=legacy_stash,
        # New as of the hero-rarity pass too -- an old save has no active_party key at all, so default to
        # empty; game/party.py's default_party_ids falls back to "first MAX_PARTY_SIZE on the roster"
        # whenever this is empty, so a first post-update battle just works without extra migration.
        active_party=list(data.get("active_party", [])),
        cleared_bosses=list(data.get("cleared_bosses", [])),
        # Ranks/renown are new: a save from before them has neither key. Derive the rank from the bosses
        # already cleared (so a player who beat the Champion is already Rank 2) and start renown at 0.
        rank=data.get("rank") or _renown.rank_for_cleared(data.get("cleared_bosses", [])),
        renown=data.get("renown", 0),
        tickets={"common": 0, "premium": 0, **{k: int(v) for k, v in data.get("tickets", {}).items()}},
        # world_map is new as of the JRPG-overworld pass -- an old save has none of these keys, so
        # default world_map to "" (empty), which game.world.ensure_spawned() (called once at
        # hub_server.py startup) treats the same as a save that has never been placed on a map: it
        # drops the player at the starting map's spawn point, same as a brand-new game gets.
        world_map=data.get("world_map", ""),
        world_x=int(data.get("world_x", 0)),
        world_y=int(data.get("world_y", 0)),
        world_facing=data.get("world_facing", "down"),
    )


def delete_save(path: str = SAVE_PATH) -> None:
    if os.path.isfile(path):
        os.remove(path)

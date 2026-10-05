"""Equipment INSTANCES: one specific physical copy of a catalog item (data/equipment_db.py), because two
copies of the same item can now differ -- a copy pulled from a summon (never a shop purchase) rolls
1/2/3/4 random bonus stats on top of the catalog baseline, for rare/epic/legendary/mythic respectively
(engine/equipment.py's RARITY_BONUS_STAT_COUNT). A shop-bought copy, or a debug-menu one, always has an
empty bonus roll -- "only the summoned gear" gets the random stats, per Andrew.

PlayerState (game/player_state.py) keeps every instance ever created in `equipment_instances` (keyed by
instance id) and lists which ones are currently in the stash (unequipped) in `equipment_stash`; a
PlayerCharacter's `equipped` dict (game/roster.py) holds instance ids too, not base catalog ids, so a
specific summoned copy's rolled stats travel with it once it's worn.

`resolve_equipment_db` is the bridge back to the rest of the game: it builds a plain Dict[str, Equipment]
that has every base catalog entry PLUS one synthetic Equipment per live instance (id = instance id,
stat_bonuses = base + rolled), so PlayerCharacter.effective_stats/build_combatant (which just do
`equipment_db.get(some_id)`) work completely unchanged whether `some_id` is a real catalog id (an old
save, or something the debug menu granted) or an instance id -- callers never need to know the
difference.
"""
import random as _random_module
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

from engine.equipment import Equipment, RARITY_BONUS_STAT_COUNT

# The stat pool a random bonus roll can pick from, and the plain (pre-rarity-scaling) range for each --
# roughly matched to the catalog's own rare/epic baseline bonuses (data/equipment_db.py) so a bonus roll
# feels like "another line of the same gear", not a different game.
BONUS_STAT_POOL = ("atk", "def_", "mag", "res", "spd", "luk", "max_hp", "max_mp")
BONUS_STAT_RANGE = {
    "atk": (2, 5), "def_": (2, 5), "mag": (2, 5), "res": (2, 5),
    "spd": (1, 3), "luk": (2, 6), "max_hp": (6, 14), "max_mp": (4, 10),
}
# Higher rarities don't just get more stats, each rolled stat is also a bit bigger.
BONUS_RARITY_SCALE = {"common": 1.0, "rare": 1.0, "epic": 1.25, "legendary": 1.5, "mythic": 1.85}


@dataclass
class EquipmentInstance:
    instance_id: str
    base_id: str                                    # data/equipment_db.py catalog id
    bonus_stats: Dict[str, int] = field(default_factory=dict)   # random extras, empty for shop/debug gear
    upgrade_level: int = 0                          # blacksmith upgrades (weapons only), 0..WEAPON_MAX_UPGRADE

    def total_bonuses(self, equipment_db: Dict[str, Equipment]) -> Dict[str, int]:
        base = equipment_db[self.base_id].stat_bonuses if self.base_id in equipment_db else {}
        out = dict(base)
        for k, v in self.bonus_stats.items():
            out[k] = out.get(k, 0) + v
        if self.upgrade_level > 0:
            for k, v in list(out.items()):
                out[k] = v + weapon_upgrade_bonus(v, self.upgrade_level)
        return out


# ---- Blacksmith weapon upgrades ------------------------------------------------------------------
WEAPON_MAX_UPGRADE = 10
WEAPON_UPGRADE_STEP = 0.15          # each +1 adds 15% of the weapon's (base + rolled) stat bonuses, at least +1 per stat
# Gold for the NEXT upgrade = base for the weapon's rarity x (current level + 1). So a common +0 -> +1 costs 150
# and +9 -> +10 costs 1500; a mythic +9 -> +10 costs 16000.
WEAPON_UPGRADE_BASE_COST = {"common": 150, "rare": 300, "epic": 600, "legendary": 1000, "mythic": 1600}


def weapon_upgrade_bonus(stat_value: int, level: int) -> int:
    if level <= 0 or stat_value <= 0:
        return 0
    return max(1, round(stat_value * WEAPON_UPGRADE_STEP * level))


def weapon_upgrade_cost(rarity: str, level: int) -> int:
    """Gold to take a weapon from `level` to `level + 1`."""
    return WEAPON_UPGRADE_BASE_COST.get(rarity, WEAPON_UPGRADE_BASE_COST["common"]) * (level + 1)


def roll_bonus_stats(rarity: str, rng: Optional[_random_module.Random] = None) -> Dict[str, int]:
    """`RARITY_BONUS_STAT_COUNT[rarity]` random stats, each a different one from BONUS_STAT_POOL, sized
    by BONUS_STAT_RANGE and scaled up for the rarer tiers. Empty for common (and any unknown rarity)."""
    n = RARITY_BONUS_STAT_COUNT.get(rarity, 0)
    if n <= 0:
        return {}
    r = rng or _random_module
    scale = BONUS_RARITY_SCALE.get(rarity, 1.0)
    picked = r.sample(BONUS_STAT_POOL, min(n, len(BONUS_STAT_POOL)))
    out = {}
    for stat in picked:
        lo, hi = BONUS_STAT_RANGE[stat]
        out[stat] = max(1, round(r.randint(lo, hi) * scale))
    return out


def new_instance(base_id: str, rolled: bool, equipment_db: Dict[str, Equipment],
                 rng: Optional[_random_module.Random] = None) -> EquipmentInstance:
    """A fresh instance of `base_id`. `rolled=True` (summon pulls only) rolls random bonus stats off the
    item's own rarity; `rolled=False` (shop purchases, debug grants, save migration) never does."""
    item = equipment_db.get(base_id)
    bonus = roll_bonus_stats(item.rarity, rng) if (rolled and item is not None) else {}
    return EquipmentInstance(instance_id=uuid.uuid4().hex[:12], base_id=base_id, bonus_stats=bonus)


def bonus_text(inst: EquipmentInstance, equipment_db: Dict[str, Equipment]) -> str:
    from engine.equipment import STAT_LABEL
    total = inst.total_bonuses(equipment_db)
    if not total:
        return "(no stat bonus)"
    return ", ".join(f"+{v} {STAT_LABEL.get(k, k.upper())}" for k, v in total.items())


def resolve_equipment_db(base_db: Dict[str, Equipment], instances: Dict[str, EquipmentInstance]
                          ) -> Dict[str, Equipment]:
    """base_db plus one synthetic Equipment per instance (its id IS the instance id), each carrying the
    base item's slot/subtype/rarity/description but stat_bonuses = base + that instance's rolled bonus.
    Pass the result anywhere a plain equipment_db was passed before (effective_stats, build_combatant,
    build_battle, ...) whenever a PlayerCharacter's `equipped` values might be instance ids -- which is
    every real, owned character. An instance whose base_id has gone missing from the catalog (a save
    referencing removed content) is skipped, same as an unknown equipped id always was."""
    out = dict(base_db)
    for inst in instances.values():
        base = base_db.get(inst.base_id)
        if base is None:
            continue
        out[inst.instance_id] = Equipment(
            id=inst.instance_id, name=base.name + (f" +{inst.upgrade_level}" if inst.upgrade_level > 0 else ""), slot=base.slot, subtype=base.subtype, rarity=base.rarity,
            stat_bonuses=inst.total_bonuses(base_db), cost=0, description=base.description,
        )
    return out

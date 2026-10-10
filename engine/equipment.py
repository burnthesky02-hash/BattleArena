"""Equipment (gear) definitions -- weapon/armor/accessory items a persistent
player character can own and equip between battles.

This is deliberately separate from engine/items.py's Item (a battle-time
consumable): equipment is a meta-progression concept with no in-battle
behavior of its own -- it just adds flat stat bonuses to whichever
Combatant gets built from a character that has it equipped (see
game/roster.py's PlayerCharacter.build_combatant). Keeping it here rather
than in game/ mirrors how Skill/Item live in engine/ with their game data
in data/skills_db.py / data/items_db.py -- a plain data definition, no
behavior, no dependency on anything outside engine/.

--- The equipment overhaul (six slots, subtypes, class restrictions) ---

Six slots now (was weapon/armor/accessory): a weapon and an off-hand, three
armor pieces (armor/helmet/boots, each with a light/medium/heavy WEIGHT),
and a universal accessory. Weapons and off-hands also have a SUBTYPE (a
sword, a bow, a shield, ...) -- see data/classes.py's ClassArchetype for
which subtypes/weights each class can use (class_can_equip below is the
actual check; it takes plain sets/strings rather than an archetype object
so this module doesn't need to import data/classes and create a cycle).

Random bonus stats (rarity past common = that many extra random stats) are
a per-instance thing -- see game/equipment_instances.py -- because two
copies of the same base item can roll differently. This module only holds
the base catalog (data/equipment_db.py): fixed slot/subtype/rarity and a
fixed baseline stat_bonuses that every copy of that item starts with.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional

SLOTS = ("weapon", "offhand", "armor", "helmet", "boots", "accessory")

# Slots whose restriction is a WEIGHT class (light/medium/heavy), ordered light-to-heavy so a class's
# max weight also allows everything lighter (a tank in light armor is legal, a mage in heavy isn't).
ARMOR_SLOTS = ("armor", "helmet", "boots")
ARMOR_WEIGHTS = ("light", "medium", "heavy")
ARMOR_WEIGHT_ORDER = {w: i for i, w in enumerate(ARMOR_WEIGHTS)}

# Weapon/off-hand subtypes. A class can equip a weapon/off-hand only if its subtype is in that class's
# allowed set (data/classes.py) -- unlike armor weight, there's no "lighter is always fine" ordering here.
WEAPON_TYPES = ("sword", "axe", "mace", "dagger", "bow", "staff", "wand", "tome", "dual_blades")
OFFHAND_TYPES = ("shield", "buckler", "quiver", "focus")

# Weapon subtypes that fill BOTH hands: equipping one takes the weapon slot AND the off-hand slot (the off-hand is
# emptied -- anything in it goes back to the stash -- and can't be filled again until the weapon comes off).
# Which heroes may wield them is data/classes.py's HERO_EXTRA_WEAPON_TYPES (dual blades are Kenji's signature type).
TWO_SLOT_WEAPON_TYPES = ("dual_blades",)

RARITIES = ("common", "rare", "epic", "legendary", "mythic")  # epic+ are premium, gem-summon-only

# Random bonus stats an equipment INSTANCE gets when it's acquired from a summon (never from the shop):
# one per rarity tier past common. See game/equipment_instances.py's roll_bonus_stats.
RARITY_BONUS_STAT_COUNT: Dict[str, int] = {"common": 0, "rare": 1, "epic": 2, "legendary": 3, "mythic": 4}


@dataclass
class Equipment:
    id: str
    name: str
    slot: str                                   # one of SLOTS
    rarity: str = "common"                      # one of RARITIES
    # Weapon/offhand: one of WEAPON_TYPES/OFFHAND_TYPES. Armor/helmet/boots: one of ARMOR_WEIGHTS.
    # Accessory: always None -- accessories are universal, no class restricts them.
    subtype: Optional[str] = None
    stat_bonuses: Dict[str, int] = field(default_factory=dict)  # Stats field name -> flat bonus
    cost: int = 0                                # money cost in the shop; 0 = not shop-purchasable
    description: str = ""

    def __post_init__(self):
        if self.slot not in SLOTS:
            raise ValueError(f"Equipment {self.id!r} has unknown slot {self.slot!r} (must be one of {SLOTS})")
        if self.rarity not in RARITIES:
            raise ValueError(f"Equipment {self.id!r} has unknown rarity {self.rarity!r} (must be one of {RARITIES})")
        if self.slot == "weapon" and self.subtype not in WEAPON_TYPES:
            raise ValueError(f"Equipment {self.id!r} (weapon) needs a subtype in {WEAPON_TYPES}, got {self.subtype!r}")
        if self.slot == "offhand" and self.subtype not in OFFHAND_TYPES:
            raise ValueError(f"Equipment {self.id!r} (offhand) needs a subtype in {OFFHAND_TYPES}, got {self.subtype!r}")
        if self.slot in ARMOR_SLOTS and self.subtype not in ARMOR_WEIGHTS:
            raise ValueError(f"Equipment {self.id!r} ({self.slot}) needs a weight in {ARMOR_WEIGHTS}, got {self.subtype!r}")
        if self.slot == "accessory" and self.subtype is not None:
            raise ValueError(f"Equipment {self.id!r} is an accessory -- accessories don't take a subtype")

    def bonus_text(self) -> str:
        """A short human-readable summary of the stat bonuses, e.g. '+5 ATK, +2 DEF'."""
        if not self.stat_bonuses:
            return "(no stat bonus)"
        return ", ".join(f"+{v} {STAT_LABEL.get(k, k.upper())}" for k, v in self.stat_bonuses.items())


STAT_LABEL = {"max_hp": "HP", "max_mp": "MP", "atk": "ATK", "def_": "DEF",
              "mag": "MAG", "res": "RES", "spd": "SPD", "luk": "LUK"}


def occupies_offhand(item: Optional[Equipment]) -> bool:
    """True for a weapon that uses both hands (see TWO_SLOT_WEAPON_TYPES), so the off-hand slot is taken by it."""
    return bool(item) and item.slot == "weapon" and item.subtype in TWO_SLOT_WEAPON_TYPES


def class_can_equip(item: Equipment, weapon_types, offhand_types, max_armor_weight: str) -> bool:
    """Whether a class that allows `weapon_types`/`offhand_types` (subtype sets) and armor up to
    `max_armor_weight` can equip `item`. Accessories are always fine -- nothing restricts them."""
    if item.slot == "weapon":
        return item.subtype in weapon_types
    if item.slot == "offhand":
        return item.subtype in offhand_types
    if item.slot in ARMOR_SLOTS:
        return ARMOR_WEIGHT_ORDER[item.subtype] <= ARMOR_WEIGHT_ORDER[max_armor_weight]
    return True

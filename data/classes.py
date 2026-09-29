"""Player class archetypes, chosen once at character creation.

Each archetype's starting skill kit deliberately reuses skills already in
data/skills_db.py rather than inventing a parallel set, both to keep this
first pass contained and because the existing default party (Kael/Lyra/
Sera/Rook, still used as enemy-side-agnostic sample data / test fixtures)
already demonstrates four of these five kits well: Kael ~ melee_dps,
Lyra ~ mage, Sera ~ support, Rook ~ ranged_dps. Tank is the one archetype
the original fixed party never had (nothing on the party's side played that
role -- only Iron Golem did, enemy-side), so it borrows Iron Golem's
Self-Repair for the same "durable, self-sustaining" identity.

Stats are hand-tuned to be roughly comparable to that original party's
per-member stats, since a solo new character is expected to be an
underdog against the existing 3-enemy Colosseum trio at first -- softened
by the fact that a lost battle still pays out money (see game/rewards.py),
and the roster is meant to grow via summons, not by one character leveling
into being able to solo three monsters forever.

Each archetype also carries `growth: Stats` -- the flat amount each stat
gains per level past 1, applied by data/leveling.py's `apply_growth`
(base_stats is deliberately the level-1 block, not some separate "starting
stats" concept). Growth is shaped around each class's identity rather than
being uniform: tank leans on HP/DEF growth, melee_dps on ATK, ranged_dps
splits ATK/SPD/LUK, mage and support both grow MP faster than HP since
their kits are MP-hungry. These are first-pass numbers -- see README's
"Known limitations" for how to retune them.
"""
from dataclasses import dataclass, field
from typing import FrozenSet, List, Tuple

from engine.equipment import ARMOR_WEIGHTS, OFFHAND_TYPES, WEAPON_TYPES
from engine.stats import Stats

# Rendering order for character-creation UI; also literally "which 5 classes exist".
CLASS_IDS: Tuple[str, ...] = ("tank", "melee_dps", "ranged_dps", "mage", "support")


@dataclass
class ClassArchetype:
    id: str
    name: str
    description: str
    base_stats: Stats      # level-1 stats
    growth: Stats           # flat per-level stat gain past level 1 (see data/leveling.py)
    skill_ids: List[str]
    sprite_color: tuple
    # Equipment restrictions (engine/equipment.py's class_can_equip): which weapon/off-hand subtypes
    # this class can wield, and the heaviest armor weight it can wear (anything lighter is also fine).
    weapon_types: FrozenSet[str] = field(default_factory=frozenset)
    offhand_types: FrozenSet[str] = field(default_factory=frozenset)
    armor_weight: str = "medium"
    # Battle formations (engine/formation.py): whether this class is a melee fighter for TARGETING
    # purposes -- i.e. can be blocked by an occupied enemy front row. game/roster.py's build_combatant
    # reads this into the Combatant it builds.
    is_melee: bool = True

    def __post_init__(self):
        assert self.weapon_types <= set(WEAPON_TYPES), f"{self.id}: unknown weapon type in {self.weapon_types}"
        assert self.offhand_types <= set(OFFHAND_TYPES), f"{self.id}: unknown offhand type in {self.offhand_types}"
        assert self.armor_weight in ARMOR_WEIGHTS, f"{self.id}: unknown armor weight {self.armor_weight!r}"


CLASS_ARCHETYPES = {
    "tank": ClassArchetype(
        id="tank", name="Tank",
        description="Built to take a beating and keep swinging. High HP and defense, weak magic.",
        base_stats=Stats(max_hp=130, max_mp=18, atk=16, def_=20, mag=4, res=12, spd=8, luk=9),
        growth=Stats(max_hp=9, max_mp=1, atk=1, def_=2, mag=0, res=1, spd=0, luk=0),
        skill_ids=["iron_stance", "power_strike", "sunder", "self_repair"],
        sprite_color=(90, 130, 190),
        weapon_types=frozenset({"sword", "axe", "mace"}), offhand_types=frozenset({"shield"}), armor_weight="heavy",
        is_melee=True,
    ),
    "melee_dps": ClassArchetype(
        id="melee_dps", name="Melee DPS",
        description="Gets in close and hits hard. High attack, fragile against magic.",
        base_stats=Stats(max_hp=100, max_mp=18, atk=23, def_=13, mag=5, res=8, spd=12, luk=10),
        growth=Stats(max_hp=6, max_mp=1, atk=2, def_=1, mag=0, res=0, spd=1, luk=0),
        skill_ids=["power_strike", "cleave", "crushing_blow", "holy_reset"],
        sprite_color=(200, 90, 70),
        weapon_types=frozenset({"sword", "axe", "dagger"}), offhand_types=frozenset({"buckler"}), armor_weight="medium",
        is_melee=True,
    ),
    "ranged_dps": ClassArchetype(
        id="ranged_dps", name="Ranged DPS",
        description="Fast and precise, whittles targets down from a distance. Fragile up close.",
        base_stats=Stats(max_hp=88, max_mp=22, atk=28, def_=9, mag=6, res=9, spd=18, luk=15),
        growth=Stats(max_hp=5, max_mp=1, atk=2, def_=0, mag=0, res=0, spd=1, luk=1),
        skill_ids=["piercing_shot", "poison_dart", "weaken", "sunder"],
        sprite_color=(90, 170, 110),
        weapon_types=frozenset({"bow"}), offhand_types=frozenset({"quiver"}), armor_weight="medium",
        is_melee=False,
    ),
    "mage": ClassArchetype(
        id="mage", name="Mage",
        description="Elemental firepower at range. Very high magic, very low HP/defense.",
        base_stats=Stats(max_hp=72, max_mp=58, atk=7, def_=7, mag=25, res=13, spd=12, luk=11),
        growth=Stats(max_hp=4, max_mp=4, atk=0, def_=0, mag=2, res=1, spd=0, luk=0),
        skill_ids=["fireball", "ice_lance", "thunderbolt", "firestorm"],
        sprite_color=(80, 110, 220),
        weapon_types=frozenset({"staff", "wand"}), offhand_types=frozenset({"focus"}), armor_weight="light",
        is_melee=False,
    ),
    "support": ClassArchetype(
        id="support", name="Support",
        description="Keeps everyone standing. Strong healing, decent magic resistance.",
        base_stats=Stats(max_hp=82, max_mp=52, atk=8, def_=10, mag=19, res=17, spd=11, luk=11),
        growth=Stats(max_hp=5, max_mp=3, atk=0, def_=0, mag=1, res=1, spd=0, luk=0),
        skill_ids=["heal", "greater_heal", "prayer", "holy_light"],
        sprite_color=(230, 210, 90),
        weapon_types=frozenset({"mace", "wand", "tome"}), offhand_types=frozenset({"focus"}), armor_weight="light",
        is_melee=False,
    ),
}

assert set(CLASS_ARCHETYPES) == set(CLASS_IDS), "CLASS_IDS and CLASS_ARCHETYPES must list the same classes"

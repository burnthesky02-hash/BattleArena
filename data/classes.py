"""Player class archetypes, chosen once at character creation.

Each archetype's starting skill kit deliberately reuses skills already in
data/skills_db.py rather than inventing a parallel set, both to keep this
first pass contained and because the existing default party (Kenji/Lyra/
Miya/Rook, still used as enemy-side-agnostic sample data / test fixtures)
already demonstrates four of these five kits well: Kenji ~ melee_dps,
Lyra ~ mage, Miya ~ support, Rook ~ ranged_dps. Tank is the one archetype
the original fixed party never had (nothing on the party's side played that
role -- only Iron Golem did, enemy-side), so it borrows Iron Golem's
Self-Repair for the same "durable, self-sustaining" identity.

Stats are hand-tuned to be roughly comparable to that original party's
per-member stats, since a solo new character is expected to be an
underdog against the existing 3-enemy Colosseum trio at first -- softened
by the fact that a lost battle still pays out money (see game/rewards.py),
and the roster is meant to grow via summons, not by one character leveling
into being able to solo three monsters forever.

Level-99 targets (Andrew: "close to 9999 health, 999 magic and 999 in their main stats, varying slightly by
class"): `growth` below is fractional and was solved so a STORY hero (growth x1.3, mythic x1.35 rarity, one star)
reaches roughly these numbers at level 99, ignoring gear:
    tank        HP 9999  MP 500  ATK 520  DEF 999  MAG  14  RES 500
    melee_dps   HP 9500  MP 550  ATK 999  DEF 500  MAG  20  RES  30
    ranged_dps  HP 9100  MP 650  ATK 999  DEF  32  MAG  21  RES  32
    mage        HP 8600  MP 999  ATK  24  DEF  24  MAG 999  RES 500
    support     HP 9200  MP 999  ATK  30  DEF  37  MAG 900  RES 800
growth per level = (target / 1.35 - level-1 value) / (98 * 1.3). SPD and LUK growth are unchanged. Colosseum
(non-story) heroes use the same per-level growth, they just stop at their rarity's level cap.

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
        growth=Stats(max_hp=57.12, max_mp=2.77, atk=2.9, def_=5.65, mag=0.05, res=2.81, spd=0, luk=0),   # L99 story: 9999 HP / 500 MP / 999 DEF
        skill_ids=["iron_stance", "power_strike", "sunder", "self_repair"],
        sprite_color=(90, 130, 190),
        weapon_types=frozenset({"sword", "axe", "mace"}), offhand_types=frozenset({"shield"}), armor_weight="heavy",
        is_melee=True,
    ),
    "melee_dps": ClassArchetype(
        id="melee_dps", name="Melee DPS",
        description="Gets in close and hits hard. High attack, fragile against magic.",
        base_stats=Stats(max_hp=100, max_mp=18, atk=23, def_=13, mag=5, res=8, spd=12, luk=10),
        growth=Stats(max_hp=54.45, max_mp=3.06, atk=5.63, def_=2.81, mag=0.08, res=0.11, spd=1, luk=0),   # L99 story: 9500 HP / 550 MP / 999 ATK
        skill_ids=["power_strike", "cleave", "crushing_blow", "holy_reset"],
        sprite_color=(200, 90, 70),
        weapon_types=frozenset({"sword", "axe", "dagger"}), offhand_types=frozenset({"buckler"}), armor_weight="medium",
        is_melee=True,
    ),
    "ranged_dps": ClassArchetype(
        id="ranged_dps", name="Ranged DPS",
        description="Fast and precise, whittles targets down from a distance. Fragile up close.",
        base_stats=Stats(max_hp=88, max_mp=22, atk=28, def_=9, mag=6, res=9, spd=18, luk=15),
        growth=Stats(max_hp=52.22, max_mp=3.61, atk=5.59, def_=0.12, mag=0.08, res=0.12, spd=1, luk=1),   # L99 story: 9100 HP / 650 MP / 999 ATK
        skill_ids=["piercing_shot", "poison_dart", "weaken", "sunder"],
        sprite_color=(90, 170, 110),
        weapon_types=frozenset({"bow"}), offhand_types=frozenset({"quiver"}), armor_weight="medium",
        is_melee=False,
    ),
    "mage": ClassArchetype(
        id="mage", name="Mage",
        description="Elemental firepower at range. Very high magic, very low HP/defense.",
        base_stats=Stats(max_hp=72, max_mp=58, atk=7, def_=7, mag=25, res=13, spd=12, luk=11),
        growth=Stats(max_hp=49.44, max_mp=5.35, atk=0.08, def_=0.08, mag=5.61, res=2.81, spd=0, luk=0),   # L99 story: 8600 HP / 999 MP / 999 MAG
        skill_ids=["fireball", "ice_lance", "thunderbolt", "firestorm"],
        sprite_color=(80, 110, 220),
        weapon_types=frozenset({"staff", "wand"}), offhand_types=frozenset({"focus"}), armor_weight="light",
        is_melee=False,
    ),
    "support": ClassArchetype(
        id="support", name="Support",
        description="Keeps everyone standing. Strong healing, decent magic resistance.",
        base_stats=Stats(max_hp=82, max_mp=52, atk=8, def_=10, mag=19, res=17, spd=11, luk=11),
        growth=Stats(max_hp=52.85, max_mp=5.4, atk=0.11, def_=0.14, mag=5.08, res=4.52, spd=0, luk=0),   # L99 story: 9200 HP / 999 MP / 900 MAG / 800 RES
        skill_ids=["heal", "greater_heal", "prayer", "holy_light"],
        sprite_color=(230, 210, 90),
        weapon_types=frozenset({"mace", "wand", "tome"}), offhand_types=frozenset({"focus"}), armor_weight="light",
        is_melee=False,
    ),
}

# Weapon subtypes a specific HERO may use on top of what their class allows (matched by hero name, like
# data/hero_skills.py). Dual blades are Kenji's own weapon type: no other hero, even another melee DPS, can wield
# them. They use both hands (engine/equipment.py's TWO_SLOT_WEAPON_TYPES), so Kenji's off-hand is empty while
# they are equipped; he can still use his class's swords, axes and daggers (with a buckler) as before.
HERO_EXTRA_WEAPON_TYPES = {
    "Kenji": frozenset({"dual_blades"}),
}
for _name, _types in HERO_EXTRA_WEAPON_TYPES.items():
    assert _types <= set(WEAPON_TYPES), f"{_name}: unknown weapon type in {_types}"


def weapon_types_for(name: str, class_id: str) -> FrozenSet[str]:
    """Every weapon subtype this hero can wield: their class's set plus any hero-specific extras."""
    return CLASS_ARCHETYPES[class_id].weapon_types | HERO_EXTRA_WEAPON_TYPES.get(name, frozenset())


assert set(CLASS_ARCHETYPES) == set(CLASS_IDS), "CLASS_IDS and CLASS_ARCHETYPES must list the same classes"

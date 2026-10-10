"""The Colosseum's enemy roster: what Battle Setup (game/battle_setup.py)
randomly draws 1-4 opponents from once a difficulty is picked. This is
deliberately separate from data/enemies.py's `make_enemy_group()`, which
keeps returning the original fixed Iron Golem/Bandit Rogue/Dark Cultist
trio at their original hand-tuned stats, unleveled -- that function is now
sample/test-fixture data (several tests balance-check against that exact
fixed trio, the same fate data/characters.py's fixed party had in the
Meta-game layer stage) rather than what a real Colosseum battle fights.
Real battles, as of the level-curve/difficulty pass, draw from here.

Each EnemyArchetype mirrors data/classes.py's ClassArchetype shape on
purpose: `base_stats` is the level-1 block, `growth` is the flat per-level
increment data/leveling.py's `apply_growth` applies, so an enemy scales
exactly the same way a player character does. `persona` is flavor
text describing each opponent's tactics; ai/enemy_ai.py's PROFILES table (keyed by
the archetype ids below) is what actually makes each one behave differently. Skill kits reuse data/skills_db.py's existing
skills rather than inventing a parallel set, the same call data/classes.py
made for player kits.

The original three keep their exact original level-1 stats (so nothing
about their known balance changes, only that they can now level past it)
and get first-pass growth numbers alongside the ten new arrivals. Andrew
asked for "about 10 more" without specifying which -- this pass adds a
deliberately varied spread (a fast/fragile skirmisher, a physical tank, an
ice/fire/thunder caster each, a poison striker, a life-draining bruiser, an
elite all-rounder, a healer/support enemy -- a role none of the original
three had -- and a tanky dark caster) so a random 1-4 draw produces a
genuinely different fight each time rather than reshuffling three
archetypes.
"""
import random as _random_module
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from data.classes import CLASS_ARCHETYPES
from data.hero_rarity import HERO_RARITY_COLOR, SHARDS_PER_DUPLICATE
from data.leveling import apply_growth, power_mult
from data.summon_pool import RECRUITABLE_ROSTER
import engine.formation as formation
from engine.combatant import Combatant
from engine.stats import Stats
from engine.types import Element


@dataclass
class EnemyArchetype:
    id: str
    name: str
    base_stats: Stats       # level-1 stats
    growth: Stats            # flat per-level stat gain past level 1 (see data/leveling.py)
    skill_ids: List[str]
    persona: str
    sprite_color: tuple
    resistances: Dict[Element, float] = field(default_factory=dict)
    # Battle formations (engine/formation.py): whether this monster is a melee fighter for TARGETING
    # purposes. game/battle_setup.py's build_enemy_combatant reads this to set both Combatant.is_melee
    # and (via formation.auto_formation) its default row.
    is_melee: bool = True


ENEMY_ARCHETYPES: Dict[str, EnemyArchetype] = {
    # --- the original trio -- same level-1 stats/kit/persona as data/enemies.py, now with growth ---
    "iron_golem": EnemyArchetype(
        id="iron_golem", name="Iron Golem",
        base_stats=Stats(max_hp=215, max_mp=14, atk=27, def_=24, mag=4, res=10, spd=6, luk=6),
        growth=Stats(max_hp=10, max_mp=1, atk=2, def_=2, mag=0, res=1, spd=0, luk=0),
        skill_ids=["power_strike", "crushing_blow", "iron_stance", "self_repair"],
        resistances={Element.PHYSICAL: 0.8, Element.THUNDER: 1.3},
        persona=(
            "A slow, methodical construct. It is patient and calculating: it prefers to "
            "focus fire on whichever enemy has the lowest HP to secure a kill, braces "
            "defensively or repairs itself when its own HP is high and no kill is "
            "available this turn, and saves Crushing Blow for when it can afford the MP."
        ),
        sprite_color=(140, 140, 150),
        is_melee=True,
    ),
    "bandit_rogue": EnemyArchetype(
        id="bandit_rogue", name="Bandit Rogue",
        base_stats=Stats(max_hp=108, max_mp=18, atk=24, def_=11, mag=5, res=7, spd=19, luk=15),
        growth=Stats(max_hp=6, max_mp=1, atk=2, def_=1, mag=0, res=0, spd=1, luk=1),
        skill_ids=["poison_dart", "piercing_shot", "sunder"],
        resistances={},
        persona=(
            "Aggressive, reckless, and a bit cocky. Always goes for whichever target it "
            "thinks it can bring down fastest, likes poisoning tough-looking targets to "
            "whittle them down over time, and will sunder (crack the armor of) a "
            "heavily-defended target that's proving hard to kill outright."
        ),
        sprite_color=(150, 90, 40),
        is_melee=False,
    ),
    "dark_cultist": EnemyArchetype(
        id="dark_cultist", name="Dark Cultist",
        base_stats=Stats(max_hp=98, max_mp=55, atk=8, def_=8, mag=26, res=14, spd=9, luk=9),
        growth=Stats(max_hp=5, max_mp=4, atk=0, def_=0, mag=2, res=1, spd=0, luk=0),
        skill_ids=["shadow_bolt", "life_drain", "weaken", "sunder"],
        resistances={Element.DARK: 0.5, Element.HOLY: 1.3},
        persona=(
            "Cowardly and manipulative caster. Prefers to weaken or sunder the enemy's "
            "strongest-looking fighter rather than trade blows directly, favors Life "
            "Drain over a plain Shadow Bolt when its own HP isn't full since the "
            "lifesteal keeps it in the fight longer, and only attacks directly when it "
            "feels safe (its own HP is comfortably high)."
        ),
        sprite_color=(90, 40, 110),
        is_melee=False,
    ),

    # --- ten new arrivals ------------------------------------------------
    "goblin_skirmisher": EnemyArchetype(
        id="goblin_skirmisher", name="Goblin Skirmisher",
        base_stats=Stats(max_hp=70, max_mp=10, atk=16, def_=6, mag=2, res=5, spd=16, luk=12),
        growth=Stats(max_hp=4, max_mp=1, atk=1, def_=0, mag=0, res=0, spd=1, luk=0),
        skill_ids=["piercing_shot", "poison_dart", "sunder"],
        resistances={},
        persona=(
            "A twitchy pack fighter that only feels brave in numbers. Goes after whichever "
            "target already looks the most wounded rather than the toughest, favors a "
            "poisoned dart when it can afford one, and never picks a fight with the "
            "healthiest-looking target if a weaker one is available."
        ),
        sprite_color=(60, 140, 60),
        is_melee=False,
    ),
    "stone_gargoyle": EnemyArchetype(
        id="stone_gargoyle", name="Stone Gargoyle",
        base_stats=Stats(max_hp=180, max_mp=10, atk=20, def_=22, mag=3, res=16, spd=5, luk=5),
        growth=Stats(max_hp=9, max_mp=1, atk=1, def_=2, mag=0, res=1, spd=0, luk=0),
        skill_ids=["power_strike", "iron_stance", "crushing_blow"],
        resistances={Element.PHYSICAL: 0.7, Element.HOLY: 1.4},
        persona=(
            "A cursed statue that barely bothers to move. Braces into Iron Stance when "
            "it's safe and no kill is on the table, otherwise grinds down whichever "
            "enemy has the lowest HP with its heaviest available strike."
        ),
        sprite_color=(110, 110, 130),
        is_melee=True,
    ),
    "frost_wraith": EnemyArchetype(
        id="frost_wraith", name="Frost Wraith",
        base_stats=Stats(max_hp=80, max_mp=45, atk=6, def_=6, mag=22, res=12, spd=13, luk=10),
        growth=Stats(max_hp=4, max_mp=3, atk=0, def_=0, mag=2, res=1, spd=0, luk=0),
        skill_ids=["ice_lance", "shadow_bolt", "weaken"],
        resistances={Element.ICE: 0.5, Element.FIRE: 1.4},
        persona=(
            "An ethereal, calculating chill given form. Prefers Ice Lance on whoever hits "
            "hardest to chip away their defense over time, keeps its distance, and never "
            "engages a target in melee range if a spell will do."
        ),
        sprite_color=(140, 190, 230),
        is_melee=False,
    ),
    "flame_imp": EnemyArchetype(
        id="flame_imp", name="Flame Imp",
        base_stats=Stats(max_hp=68, max_mp=40, atk=8, def_=5, mag=24, res=9, spd=15, luk=13),
        growth=Stats(max_hp=3, max_mp=3, atk=0, def_=0, mag=2, res=0, spd=1, luk=0),
        skill_ids=["fireball", "firestorm", "weaken"],
        resistances={Element.FIRE: 0.5, Element.ICE: 1.4},
        persona=(
            "A gleeful little arsonist. Opens with Firestorm the moment it can afford the "
            "MP to hit everyone at once, and otherwise throws Fireball at whichever "
            "target has the lowest defense -- it wants the biggest, flashiest damage "
            "number available, not necessarily the smartest play."
        ),
        sprite_color=(220, 110, 40),
        is_melee=False,
    ),
    "storm_harpy": EnemyArchetype(
        id="storm_harpy", name="Storm Harpy",
        base_stats=Stats(max_hp=95, max_mp=30, atk=14, def_=8, mag=16, res=10, spd=22, luk=14),
        growth=Stats(max_hp=5, max_mp=2, atk=1, def_=0, mag=1, res=0, spd=1, luk=0),
        skill_ids=["thunderbolt", "piercing_shot", "sunder"],
        resistances={Element.THUNDER: 0.6},
        persona=(
            "An erratic aerial striker that hits and runs. Opens on the fastest-looking "
            "target with Thunderbolt hoping to stun it, then finishes whatever's already "
            "stunned or badly hurt with Piercing Shot rather than starting something new."
        ),
        sprite_color=(210, 220, 120),
        is_melee=False,
    ),
    "venom_spider": EnemyArchetype(
        id="venom_spider", name="Venom Spider",
        base_stats=Stats(max_hp=90, max_mp=20, atk=17, def_=10, mag=4, res=8, spd=14, luk=11),
        growth=Stats(max_hp=5, max_mp=1, atk=1, def_=1, mag=0, res=0, spd=0, luk=0),
        skill_ids=["poison_dart", "cleave", "sunder"],
        resistances={},
        persona=(
            "A patient predator that poisons first and lets time do the work. Poisons "
            "whichever healthy target isn't poisoned yet, and switches to Cleave once "
            "most of the enemy side is already poisoned and it wants to hit everyone at "
            "once instead of picking a single target."
        ),
        sprite_color=(70, 90, 50),
        is_melee=True,
    ),
    "cursed_knight": EnemyArchetype(
        id="cursed_knight", name="Cursed Knight",
        base_stats=Stats(max_hp=150, max_mp=25, atk=22, def_=15, mag=10, res=10, spd=9, luk=8),
        growth=Stats(max_hp=8, max_mp=1, atk=2, def_=1, mag=0, res=0, spd=0, luk=0),
        skill_ids=["crushing_blow", "life_drain", "iron_stance"],
        resistances={Element.DARK: 0.5, Element.HOLY: 1.4},
        persona=(
            "A relentless undead armsman bound to keep fighting. Prefers Life Drain over "
            "a plain strike whenever it isn't at full HP, since the lifesteal keeps it "
            "standing, and otherwise brings Crushing Blow down on whichever enemy looks "
            "like the biggest threat."
        ),
        sprite_color=(90, 70, 100),
        is_melee=True,
    ),
    "colosseum_champion": EnemyArchetype(
        id="colosseum_champion", name="Colosseum Champion",
        base_stats=Stats(max_hp=170, max_mp=25, atk=24, def_=17, mag=8, res=12, spd=14, luk=16),
        growth=Stats(max_hp=8, max_mp=2, atk=2, def_=1, mag=0, res=1, spd=1, luk=0),
        skill_ids=["power_strike", "crushing_blow", "warcry", "sunder"],
        resistances={},
        persona=(
            "A proud veteran gladiator who's fought here longer than anyone watching. "
            "Opens a fight with Warcry to raise its own attack before committing to "
            "anything else, then focuses whichever enemy it judges the real threat -- "
            "the highest attack or magic stat it can see -- rather than the easiest kill."
        ),
        sprite_color=(210, 180, 60),
        is_melee=True,
    ),
    "temple_oracle": EnemyArchetype(
        id="temple_oracle", name="Temple Oracle",
        base_stats=Stats(max_hp=85, max_mp=50, atk=6, def_=9, mag=18, res=16, spd=10, luk=12),
        growth=Stats(max_hp=4, max_mp=3, atk=0, def_=0, mag=1, res=1, spd=0, luk=0),
        skill_ids=["heal", "greater_heal", "holy_light", "weaken"],
        resistances={Element.HOLY: 0.5, Element.DARK: 1.4},
        persona=(
            "A devoted healer that puts its squadmates first, every single turn. Checks "
            "whether any living squadmate is below roughly half HP and heals the lowest "
            "one before considering anything else; only attacks with Holy Light once the "
            "whole squad is topped up, and never attacks while someone needs healing."
        ),
        sprite_color=(235, 225, 190),
        is_melee=False,
    ),
    "abyssal_horror": EnemyArchetype(
        id="abyssal_horror", name="Abyssal Horror",
        base_stats=Stats(max_hp=140, max_mp=55, atk=10, def_=12, mag=27, res=15, spd=8, luk=9),
        growth=Stats(max_hp=7, max_mp=3, atk=0, def_=1, mag=2, res=1, spd=0, luk=0),
        skill_ids=["shadow_bolt", "life_drain", "thunderbolt", "weaken"],
        resistances={Element.DARK: 0.4, Element.HOLY: 1.5},
        persona=(
            "An ancient, contemptuous thing that barely acknowledges its opponents as a "
            "threat. Uses Life Drain on whichever enemy is closest to death to deny an "
            "easy kill and sustain itself, and otherwise unleashes its strongest offense "
            "on whichever enemy looks like it's actually dangerous."
        ),
        sprite_color=(60, 30, 70),
        is_melee=False,
    ),
}

# --- Shard Vault natives (html_hub/3d/make_vault.py): level 10-15 monsters that only live in the vault. They sit in ENEMY_ARCHETYPES
# so the hub's `battle` pools can name them, but are kept OUT of ENEMY_IDS so the Colosseum's random draw never picks them. ---
VAULT_ENEMY_ARCHETYPES: Dict[str, EnemyArchetype] = {
    "shard_sentry": EnemyArchetype(
        id="shard_sentry", name="Shard Sentry",
        base_stats=Stats(max_hp=230, max_mp=30, atk=30, def_=26, mag=6, res=12, spd=8, luk=8),
        growth=Stats(max_hp=13, max_mp=1, atk=3, def_=2, mag=0, res=1, spd=0, luk=0),
        skill_ids=["shield_bash", "power_strike", "iron_stance", "ground_slam"],
        resistances={Element.PHYSICAL: 0.8, Element.THUNDER: 1.3},
        persona=("A vault guard of fused crystal. It opens with Shield Bash on whoever hits hardest to stun them, braces with Iron Stance when hurt, "
                 "and slams the whole party with Ground Slam when it has the MP."),
        sprite_color=(120, 190, 220), is_melee=True),
    "arc_drone": EnemyArchetype(
        id="arc_drone", name="Arc Drone",
        base_stats=Stats(max_hp=100, max_mp=70, atk=8, def_=8, mag=30, res=14, spd=20, luk=12),
        growth=Stats(max_hp=6, max_mp=4, atk=0, def_=1, mag=3, res=1, spd=1, luk=0),
        skill_ids=["spark", "arc_discharge", "thunderbolt", "weaken"],
        resistances={Element.THUNDER: 0.4, Element.PHYSICAL: 1.2},
        persona=("A hovering lightning emitter. It weakens the sturdiest target first, then chains Arc Discharge through the whole party as often as its "
                 "MP allows, and falls back on Thunderbolt against a single weak target."),
        sprite_color=(90, 220, 255), is_melee=False),
    "rift_leech": EnemyArchetype(
        id="rift_leech", name="Rift Leech",
        base_stats=Stats(max_hp=170, max_mp=40, atk=24, def_=14, mag=16, res=12, spd=13, luk=10),
        growth=Stats(max_hp=10, max_mp=2, atk=2, def_=1, mag=1, res=1, spd=0, luk=0),
        skill_ids=["life_drain", "poison_dart", "weaken"],
        resistances={Element.DARK: 0.6, Element.HOLY: 1.4},
        persona=("A parasite that feeds on whatever leaks through the rift. It poisons anyone not yet poisoned, then drains the weakest living target "
                 "to heal itself, and never wastes a turn on a target already near death by poison."),
        sprite_color=(120, 60, 160), is_melee=True),
    "lattice_medic": EnemyArchetype(
        id="lattice_medic", name="Lattice Medic",
        base_stats=Stats(max_hp=130, max_mp=90, atk=10, def_=12, mag=22, res=22, spd=11, luk=12),
        growth=Stats(max_hp=7, max_mp=5, atk=1, def_=1, mag=2, res=2, spd=0, luk=0),
        skill_ids=["heal", "greater_heal", "holy_light", "shield_bash"],
        resistances={Element.HOLY: 0.5, Element.DARK: 1.4},
        persona=("A repair automaton that keeps the vault's other creatures alive. It heals the most wounded squadmate whenever anyone is under "
                 "60% HP, and otherwise attacks with Holy Light. Kill it first."),
        sprite_color=(210, 240, 200), is_melee=False),
    "phase_hound": EnemyArchetype(
        id="phase_hound", name="Phase Hound",
        base_stats=Stats(max_hp=150, max_mp=30, atk=34, def_=12, mag=6, res=10, spd=30, luk=18),
        growth=Stats(max_hp=8, max_mp=1, atk=3, def_=1, mag=0, res=1, spd=2, luk=1),
        skill_ids=["rending_strike", "reckless_swing", "piercing_shot"],
        resistances={Element.PHYSICAL: 0.9},
        persona=("A pack hunter that slips between the walkways. It always goes first, picks the lowest-defence target and keeps hitting it with "
                 "Rending Strike, and uses Reckless Swing when it is already hurt and wants the kill."),
        sprite_color=(190, 120, 255), is_melee=True),
    "void_acolyte": EnemyArchetype(
        id="void_acolyte", name="Void Acolyte",
        base_stats=Stats(max_hp=140, max_mp=100, atk=10, def_=11, mag=34, res=20, spd=14, luk=10),
        growth=Stats(max_hp=8, max_mp=5, atk=0, def_=1, mag=3, res=2, spd=1, luk=0),
        skill_ids=["void_lance", "shadow_bolt", "life_drain", "weaken"],
        resistances={Element.DARK: 0.4, Element.HOLY: 1.5},
        persona=("A robed scholar who followed the Shard into the void. It saves Void Lance for the target with the most HP, drains whoever is lowest, "
                 "and weakens anyone who has not been weakened yet."),
        sprite_color=(70, 40, 110), is_melee=False),
    "frost_mirage": EnemyArchetype(
        id="frost_mirage", name="Frost Mirage",
        base_stats=Stats(max_hp=125, max_mp=85, atk=8, def_=9, mag=32, res=18, spd=18, luk=14),
        growth=Stats(max_hp=7, max_mp=4, atk=0, def_=1, mag=3, res=1, spd=1, luk=1),
        skill_ids=["frost_nova", "ice_lance", "weaken"],
        resistances={Element.ICE: 0.4, Element.FIRE: 1.5},
        persona=("A shimmering heat-haze of cold. It opens with Frost Nova on the whole party, then Ice Lance on the tankiest target, "
                 "and keeps its distance."),
        sprite_color=(170, 220, 255), is_melee=False),
    "forge_juggernaut": EnemyArchetype(
        id="forge_juggernaut", name="Forge Juggernaut",
        base_stats=Stats(max_hp=320, max_mp=40, atk=36, def_=28, mag=18, res=14, spd=7, luk=6),
        growth=Stats(max_hp=18, max_mp=2, atk=3, def_=2, mag=1, res=1, spd=0, luk=0),
        skill_ids=["crushing_blow", "ground_slam", "warcry", "firestorm"],
        resistances={Element.FIRE: 0.3, Element.PHYSICAL: 0.8, Element.ICE: 1.5},
        persona=("A furnace-hearted war machine. It opens with Warcry, hammers the strongest target with Crushing Blow, "
                 "and engulfs everyone in Firestorm when its MP allows."),
        sprite_color=(255, 140, 50), is_melee=True),
    "null_reaper": EnemyArchetype(
        id="null_reaper", name="Null Reaper",
        base_stats=Stats(max_hp=190, max_mp=60, atk=38, def_=14, mag=26, res=16, spd=19, luk=20),
        growth=Stats(max_hp=11, max_mp=3, atk=3, def_=1, mag=2, res=1, spd=1, luk=1),
        skill_ids=["executioners_edge", "void_lance", "life_drain"],
        resistances={Element.DARK: 0.5, Element.HOLY: 1.4},
        persona=("A pale harvester that finishes the wounded. Executioner's Edge goes to the lowest-HP target, Void Lance to the strongest, "
                 "and Life Drain when it needs to recover."),
        sprite_color=(240, 240, 255), is_melee=True),
}
ENEMY_ARCHETYPES.update(VAULT_ENEMY_ARCHETYPES)
VAULT_ENEMY_IDS = tuple(VAULT_ENEMY_ARCHETYPES.keys())

ENEMY_IDS = tuple(k for k in ENEMY_ARCHETYPES.keys() if k not in VAULT_ENEMY_ARCHETYPES)

# Hero enemies are sourced from the same recruitable roster as summons, but can
# appear in battle encounters as rare, higher-skill opponents instead of only
# as friendly recruits. The id is stable and round-trippable: a summonable hero
# named "Kenji" using the melee_dps class maps to "hero_melee_dps_kael".
HERO_ENEMY_SHARD_DROP_CHANCE: Dict[str, float] = {
    "common": 0.90,
    "rare": 0.85,
    "epic": 0.80,
    "legendary": 0.75,
    "mythic": 0.70,
}


def build_hero_enemy_id(name: str, class_id: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"hero_{class_id}_{normalized}"


_HERO_BY_ENEMY_ID: Dict[str, object] = {
    build_hero_enemy_id(hero.name, hero.class_id): hero for hero in RECRUITABLE_ROSTER
}
HERO_ENEMY_IDS = tuple(_HERO_BY_ENEMY_ID.keys())


def build_hero_enemy_combatant(hero_enemy_id: str, level: int) -> Combatant:
    hero = _HERO_BY_ENEMY_ID.get(hero_enemy_id)
    if hero is None:
        raise KeyError(f"Unknown hero enemy id: {hero_enemy_id!r}")
    archetype = CLASS_ARCHETYPES[hero.class_id]
    stats = apply_growth(archetype.base_stats, archetype.growth, level)
    return Combatant(
        id=hero_enemy_id,
        name=hero.name,
        is_enemy=True,
        base_stats=stats,
        skill_ids=list(archetype.skill_ids),
        resistances={},
        persona=(
            f"{hero.name} is a rival hero who has gone rogue. It fights with the same class-based style "
            f"as its recruitable counterpart and does not hold back once combat starts."
        ),
        sprite_color=HERO_RARITY_COLOR.get(hero.rarity, (180, 60, 60)),
        is_melee=archetype.is_melee,
        formation=formation.auto_formation(archetype.is_melee),
        power_mult=power_mult(level),
    )


def maybe_award_hero_enemy_shards(player_state, defeated_enemy_ids: List[str], rng: Optional[_random_module.Random] = None) -> int:
    """Grants shard drops to matching owed heroes when a defeated hero enemy is a recruitable hero."""
    r = rng or _random_module
    total = 0
    for enemy_id in defeated_enemy_ids:
        hero = _HERO_BY_ENEMY_ID.get(enemy_id)
        if hero is None:
            continue
        chance = HERO_ENEMY_SHARD_DROP_CHANCE.get(hero.rarity, 0.5)
        if r.random() >= chance:
            continue
        existing = next((c for c in player_state.characters if c.name == hero.name and c.class_id == hero.class_id), None)
        if existing is None:
            continue
        gained = SHARDS_PER_DUPLICATE[hero.rarity]
        existing.shards += gained
        total += gained
    return total

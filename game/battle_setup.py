"""Battle Setup: turns a difficulty + opponent-count choice into an actual
enemy encounter, sitting between the Colosseum hub and BattleEngine the same
way game/summon.py sits between the hub and PlayerState.

Andrew's spec (paraphrased from his request): before a battle, choose a
difficulty (easy/normal/hard/extreme) and how many opponents (1-4).
Difficulty sets the enemies' level relative to the party's average level;
opponents are drawn at random from data/enemy_pool.py's full archetype list.
This module owns exactly that: level math + random enemy selection + turning
the result into real engine.combatant.Combatant objects, ready to hand to
BattleEngine(enemies=...). game/rewards.py owns the payout side (which also
depends on difficulty and party/enemy size) -- kept separate because reward
math has nothing to do with *building* a battle, it only cares about the
BattleResult afterward.

Difficulty -> enemy level, Andrew's literal wording and how it was resolved
into a formula (his phrasing left one genuine ambiguity, flagged below):
    "easy would be 2-3 levels under normal within 1 level either way,
     hard 2-3 levels higher and extreme 5 levels higher"
Read as: there's an implicit "normal" target level first (the party's
average level, with a small +/-1 jitter so normal fights aren't perfectly
static), and easy/hard/extreme are offsets *from that normal target* --
easy = normal_target - (2 or 3), hard = normal_target + (2 or 3), extreme =
normal_target + 5 flat (Andrew gave no jitter range for extreme, so this
takes "5 levels higher" literally). This is an interpretation, not a
transcription -- the alternative reading ("easy/hard offsets are from the
party's raw average, not from a jittered normal") would only differ by the
+/-1 jitter term, so it's a minor judgment call either way. Retune the
offsets below if this doesn't feel right in play.

Enemy selection: "enemies should be chosen at random" is implemented as a
random sample *without replacement* from the full archetype pool (13 as of
the level-curve pass -- see data/enemy_pool.py), so a single encounter never
fields two copies of the same archetype. With opponent counts capped at 4
against a pool of 13 this never runs out of variety; if the pool ever
shrinks below 4 this would need sampling with replacement instead.

Hero rivals (Andrew's request: "Hero characters can show up as enemies as
well"): each opponent slot independently rolls HERO_ENEMY_CHANCE to be
filled by a rival version of one of data/summon_pool.py's 25 recruitable
heroes instead of a data/enemy_pool.py monster archetype. Which hero rolls
is itself rarity-weighted the same way a Summon pull is (data/hero_rarity.py's
HERO_SUMMON_WEIGHTS) so a mythic-tier rival is just as rare to run into as it
is to pull -- this reuses the existing rarity-flavor rather than inventing a
separate "how tough is this hero" scale. A rival is built from its class's
own data/classes.py kit (the same stats/skills/growth a player of that class
would have) rather than getting bespoke stats, since the interesting part of
"you can fight heroes" is that they fight *like a real hero of that class*,
not that they're a reskinned monster. Personas are per-class (5 total, not
25) for the same reason data/classes.py itself has 5 kits, not 25 -- combat
behavior comes from the shared kit, not the individual name, so one
well-written persona per class covers every rival built from it. See
game/rewards.py's roll_hero_enemy_shard_drops for what happens when one of
these is actually defeated.
"""
import random as _random_module
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from data.classes import CLASS_ARCHETYPES
from data.enemy_pool import ENEMY_ARCHETYPES, ENEMY_IDS
from data.hero_rarity import HERO_RARITIES, HERO_SUMMON_WEIGHTS, rarity_multiplier
from data.hero_skills import skill_ids_for
from data.leveling import MAX_LEVEL, apply_growth, power_mult
from data.summon_pool import RECRUITABLE_BY_RARITY, RecruitableHero
import engine.formation as formation
from engine.combatant import Combatant
from engine.equipment import Equipment
from game.roster import PlayerCharacter

DIFFICULTY_IDS = ("easy", "normal", "hard", "extreme")

# Reward multiplier per difficulty -- game/rewards.py applies this, not this
# module, but it lives here too (single source of truth) since it's part of
# the same "difficulty" concept battle setup lets the player choose.
DIFFICULTY_REWARD_MODIFIER: Dict[str, float] = {
    "easy": 0.75,
    "normal": 1.0,
    "hard": 1.25,
    "extreme": 2.0,
}

MIN_OPPONENTS = 1
MAX_OPPONENTS = 4

_EASY_HARD_OFFSET_RANGE = (2, 3)   # "2-3 levels" for easy/hard
_EXTREME_OFFSET = 5                # "5 levels higher", flat -- see module docstring
_NORMAL_JITTER_RANGE = (-1, 1)     # "within 1 level either way" for normal

# Chance that any *individual* opponent slot is filled by a hero rival
# instead of a monster archetype -- rolled independently per slot, so a
# 4-opponent fight could end up with anywhere from 0 to 4 rivals in it.
# First-pass number, same "retune by feel" spirit as everything else in this
# module: frequent enough that Andrew will actually run into the new
# mechanic without playing for hours, not so frequent that monster variety
# (the whole point of data/enemy_pool.py's 13-archetype pool) gets crowded
# out.
HERO_ENEMY_CHANCE = 0.25

# Rarity-weighted, same curve a Summon pull uses (data/hero_rarity.py's
# HERO_SUMMON_WEIGHTS) -- a mythic rival should feel just as rare to run
# into in the Colosseum as it is to pull from Summon.
_HERO_ENEMY_RARITY_ROLL_WEIGHTS = [HERO_SUMMON_WEIGHTS[r] for r in HERO_RARITIES]

# One persona per class (not per hero) -- see module docstring for why.
# Written in the same "personality + concrete tactic tied to its actual
# skill kit" style as data/enemy_pool.py's monster personas, just aimed at
# "a rival adventurer of this class" rather than a specific named person, so
# swapping in any of the 5 heroes per class doesn't need 5x the flavor text.
HERO_ENEMY_PERSONAS: Dict[str, str] = {
    "tank": (
        "A rival adventurer who plants themselves at the front and dares you to get "
        "through. Opens with Iron Stance when it's safe and no kill is on the table, "
        "leans on Sunder to wear down whichever target is proving hardest to crack, "
        "and patches itself up with Self-Repair rather than pressing an attack when "
        "its own HP runs low."
    ),
    "melee_dps": (
        "A rival adventurer who wants this fight over fast and up close. Opens with "
        "Warcry to hit harder before committing to anything else, then goes straight "
        "for whichever enemy looks like the easiest kill with Power Strike or Cleave, "
        "saving Crushing Blow for when it can afford the MP."
    ),
    "ranged_dps": (
        "A rival adventurer who never lets anyone get close. Keeps its distance and "
        "picks apart whoever's already hurt with Piercing Shot, poisons a healthy, "
        "tough-looking target it isn't ready to commit to yet, and sunders a "
        "heavily-defended target that's dragging the fight out."
    ),
    "mage": (
        "A rival adventurer who leans entirely on elemental firepower. Opens with "
        "Firestorm the moment it can afford to hit the whole party at once, otherwise "
        "throws Fireball, Ice Lance, or Thunderbolt at whichever target has the "
        "lowest defense -- it wants the biggest damage number available, not "
        "necessarily the smartest play."
    ),
    "support": (
        "A rival adventurer that puts its own squad first, every single turn. Checks "
        "whether any living squadmate is below roughly half HP and heals the lowest "
        "one with Heal or Greater Heal before considering anything else; only "
        "attacks with Holy Light once the whole squad is topped up, and never "
        "attacks while someone needs healing."
    ),
}
assert set(HERO_ENEMY_PERSONAS) == set(CLASS_ARCHETYPES)


def party_average_level(party: Sequence[PlayerCharacter]) -> float:
    """Average level of the roster fielding this battle. Every character in
    player_state.characters fights every battle (there's no active-party
    subset yet), so callers just pass player_state.characters."""
    if not party:
        return 1.0
    return sum(c.level for c in party) / len(party)


def compute_enemy_level(avg_party_level: float, difficulty: str,
                         rng: Optional[_random_module.Random] = None) -> int:
    """The enemy level a battle at this difficulty should use, given the
    party's average level. See module docstring for the offset formula."""
    if difficulty not in DIFFICULTY_IDS:
        raise ValueError(f"Unknown difficulty {difficulty!r} (must be one of {DIFFICULTY_IDS})")
    r = rng or _random_module

    normal_target = round(avg_party_level) + r.randint(*_NORMAL_JITTER_RANGE)
    if difficulty == "normal":
        level = normal_target
    elif difficulty == "easy":
        level = normal_target - r.randint(*_EASY_HARD_OFFSET_RANGE)
    elif difficulty == "hard":
        level = normal_target + r.randint(*_EASY_HARD_OFFSET_RANGE)
    else:  # extreme
        level = normal_target + _EXTREME_OFFSET
    return max(1, min(level, MAX_LEVEL))


def choose_enemy_ids(num_enemies: int, rng: Optional[_random_module.Random] = None) -> List[str]:
    """Randomly picks `num_enemies` distinct archetype ids from the full pool
    (see module docstring on why it's sampling without replacement)."""
    if not (MIN_OPPONENTS <= num_enemies <= MAX_OPPONENTS):
        raise ValueError(f"num_enemies must be between {MIN_OPPONENTS} and {MAX_OPPONENTS}, got {num_enemies}")
    r = rng or _random_module
    return r.sample(ENEMY_IDS, k=num_enemies)


def choose_hero_rivals(n: int, rng: Optional[_random_module.Random] = None) -> List[RecruitableHero]:
    """Randomly picks `n` distinct RecruitableHero rivals (no repeats within
    one encounter, same rule choose_enemy_ids applies to monsters), rolling a
    rarity per pick the same way a Summon pull does. With 25 heroes total and
    n capped at MAX_OPPONENTS (4), this always has plenty of room -- the
    retry loop is a safety margin, not load-bearing."""
    r = rng or _random_module
    chosen: List[RecruitableHero] = []
    chosen_keys = set()
    attempts = 0
    max_attempts = max(50, n * 50)
    while len(chosen) < n and attempts < max_attempts:
        attempts += 1
        rarity = r.choices(HERO_RARITIES, weights=_HERO_ENEMY_RARITY_ROLL_WEIGHTS, k=1)[0]
        candidates = [h for h in RECRUITABLE_BY_RARITY[rarity] if (h.class_id, h.name) not in chosen_keys]
        if not candidates:
            continue
        pick = r.choice(candidates)
        chosen.append(pick)
        chosen_keys.add((pick.class_id, pick.name))
    return chosen


def _hero_enemy_id(recruit: RecruitableHero) -> str:
    """A stable, human-readable stand-in for a monster archetype id (see
    ENEMY_IDS) so BattleSetup.enemy_ids can hold a mix of monster ids and
    hero-rival ids while staying a flat list of unique strings."""
    return f"hero::{recruit.class_id}::{recruit.name}"


def build_hero_enemy_combatant(recruit: RecruitableHero, level: int) -> Combatant:
    """Builds one battle-ready enemy Combatant for a hero rival, using the
    recruit's own class kit (data/classes.py) grown to `level` exactly the
    way build_enemy_combatant grows a monster archetype and PlayerCharacter
    grows an owned hero. Named "Rival <name>" rather than just "<name>" so
    the battle log/UI can't be confused with an owned party member of the
    same name fighting on your own side."""
    archetype = CLASS_ARCHETYPES[recruit.class_id]
    stats = apply_growth(archetype.base_stats, archetype.growth, level)
    rm = rarity_multiplier(recruit.rarity)  # same rarity scaling an owned hero of this rarity gets
    if rm != 1.0:
        for f in ("max_hp", "max_mp", "atk", "def_", "mag", "res", "spd", "luk"):
            setattr(stats, f, round(getattr(stats, f) * rm))
    return Combatant(
        name=f"Rival {recruit.name}", is_enemy=True,
        base_stats=stats,
        skill_ids=skill_ids_for(recruit.name, recruit.class_id),
        resistances={},  # heroes carry no elemental resistances, same as an owned PlayerCharacter's build_combatant
        persona=HERO_ENEMY_PERSONAS[recruit.class_id],
        sprite_color=archetype.sprite_color,
        is_melee=archetype.is_melee,
        formation=formation.auto_formation(archetype.is_melee),
        power_mult=power_mult(level),
    )


# Monsters were consistently stronger than a same-role hero of the same level
# (rival heroes, built from class kits, felt balanced). This trims monster
# stats at build time, after level growth, so it scales with every level.
# Retune here: 1.0 = unchanged. MP/SPD/LUK are left alone.
MONSTER_STAT_SCALE = {"max_hp": 0.80, "atk": 0.80, "mag": 0.80, "def_": 0.90, "res": 0.90}


ENEMY_MP_FLOOR = 30
ENEMY_MP_PER_LEVEL = 3


def _apply_monster_nerf(stats) -> None:
    for name, mult in MONSTER_STAT_SCALE.items():
        setattr(stats, name, max(1, round(getattr(stats, name) * mult)))


def build_enemy_combatant(enemy_id: str, level: int) -> Combatant:
    """Builds one battle-ready Combatant for an enemy archetype at a given
    level, applying growth the same way PlayerCharacter.build_combatant does
    for heroes (see data/leveling.py's apply_growth)."""
    archetype = ENEMY_ARCHETYPES[enemy_id]
    stats = apply_growth(archetype.base_stats, archetype.growth, level, enemy=True)
    _apply_monster_nerf(stats)
    # Brutes used to carry 10-14 MP -- enough for one or two skills, then plain attacks all fight. Every monster
    # gets enough MP for a handful of skill casts, so battles keep showing their kit.
    stats.max_mp = max(stats.max_mp, ENEMY_MP_FLOOR + ENEMY_MP_PER_LEVEL * max(1, level))
    return Combatant(
        name=archetype.name, is_enemy=True,
        base_stats=stats,
        skill_ids=list(archetype.skill_ids),
        resistances=dict(archetype.resistances),
        persona=archetype.persona,
        sprite_color=archetype.sprite_color,
        is_melee=archetype.is_melee,
        formation=formation.auto_formation(archetype.is_melee),
        power_mult=power_mult(level),
    )


def apply_squad_formations(enemies: List[Combatant]) -> None:
    """Rebalances a whole enemy squad's formation rows in place via
    engine.formation.assign_squad_formations, so the squad as a group respects ROW_CAPACITY (2 per
    row) instead of each member's individually-assigned auto_formation() row (which only knows its
    own melee/ranged nature, not how many squadmates already claimed that row -- a squad of 3+ melee
    monsters would otherwise all say "front"). Called once the full `enemies` list for a fight is
    built (build_battle below, and hub_server.py's debug-battle path), never per-unit."""
    rows = formation.assign_squad_formations([c.is_melee for c in enemies])
    for c, row in zip(enemies, rows):
        c.formation = row


@dataclass
class BattleSetup:
    """Everything BattleEngine and game/rewards.py need for one battle,
    resolved once up front so both sides of the fight (and the payout after)
    agree on the same difficulty/level/roster numbers."""
    difficulty: str
    enemy_level: int
    enemy_ids: List[str]
    party: List[Combatant] = field(default_factory=list)
    enemies: List[Combatant] = field(default_factory=list)
    # Parallel to `enemies` (same length, same order): the RecruitableHero a
    # given enemy slot was built from, or None for an ordinary monster slot.
    # game/rewards.py's roll_hero_enemy_shard_drops is the only consumer --
    # it needs to know which defeated enemies were hero rivals (and which
    # specific hero/rarity) to roll a shard drop against.
    enemy_hero_recruits: List[Optional[RecruitableHero]] = field(default_factory=list)

    @property
    def num_heroes(self) -> int:
        return len(self.party)

    @property
    def num_enemies(self) -> int:
        return len(self.enemies)


def build_battle(party: Sequence[PlayerCharacter], equipment_db: Dict[str, Equipment],
                  difficulty: str, num_enemies: int,
                  rng: Optional[_random_module.Random] = None,
                  legacy_db: Optional[Dict[str, object]] = None) -> BattleSetup:
    """The single entry point the hub/UI layer calls: turns (difficulty,
    opponent count) plus the player's current roster into a ready-to-run
    BattleSetup. Heroes are built at their own saved level (build_combatant
    already applies their own growth); enemies are built at the
    difficulty-computed level.

    Each opponent slot independently rolls HERO_ENEMY_CHANCE to be a hero
    rival (see module docstring) instead of a monster; whichever slots come
    up monsters are drawn from the enemy pool exactly as before (still
    unique among themselves), and whichever come up rivals are drawn from
    the hero roster (also unique among themselves via choose_hero_rivals) --
    the two draws never collide since a monster id and a hero id never look
    the same (see _hero_enemy_id), so enemy_ids as a whole stays unique."""
    if difficulty not in DIFFICULTY_IDS:
        raise ValueError(f"Unknown difficulty {difficulty!r} (must be one of {DIFFICULTY_IDS})")
    r = rng or _random_module
    avg_level = party_average_level(party)
    enemy_level = compute_enemy_level(avg_level, difficulty, rng=r)

    slot_is_hero = [r.random() < HERO_ENEMY_CHANCE for _ in range(num_enemies)]
    num_hero_slots = sum(slot_is_hero)
    num_monster_slots = num_enemies - num_hero_slots

    monster_ids = choose_enemy_ids(num_monster_slots, rng=r) if num_monster_slots else []
    hero_rivals = choose_hero_rivals(num_hero_slots, rng=r) if num_hero_slots else []

    enemy_ids: List[str] = []
    enemies: List[Combatant] = []
    enemy_hero_recruits: List[Optional[RecruitableHero]] = []
    mi = hi = 0
    for is_hero in slot_is_hero:
        if is_hero:
            recruit = hero_rivals[hi]
            hi += 1
            enemy_ids.append(_hero_enemy_id(recruit))
            enemies.append(build_hero_enemy_combatant(recruit, enemy_level))
            enemy_hero_recruits.append(recruit)
        else:
            eid = monster_ids[mi]
            mi += 1
            enemy_ids.append(eid)
            enemies.append(build_enemy_combatant(eid, enemy_level))
            enemy_hero_recruits.append(None)

    apply_squad_formations(enemies)

    return BattleSetup(
        difficulty=difficulty,
        enemy_level=enemy_level,
        enemy_ids=enemy_ids,
        party=[c.build_combatant(equipment_db, legacy_db) for c in party],
        enemies=enemies,
        enemy_hero_recruits=enemy_hero_recruits,
    )

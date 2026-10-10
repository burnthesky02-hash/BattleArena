"""Shared level-curve math: the XP curve and the per-level stat-growth
formula, used by both player characters (game/roster.py's PlayerCharacter)
and enemies (data/enemy_pool.py via game/battle_setup.py) so both sides of
a fight scale the same way. Kept dependency-free (just engine/stats.py)
the same way data/classes.py and data/equipment_db.py are -- plain data
and pure functions, no UI/engine-loop involvement.

Andrew asked for "level curves" without specifying the XP mechanism, and
a follow-up question settled it: battles award XP (scaled by the same
difficulty/team-size multiplier as money and gems -- see
game/rewards.py), and a character levels up automatically once they cross
the threshold this module defines. These are first-pass numbers, tuned by
feel rather than real playtesting -- see README's "Known limitations" for
how to retune them.
"""
from typing import Tuple

from engine.stats import Stats

MAX_LEVEL = 99

# Talent points (Andrew's request): a hero earns one every TALENT_POINT_INTERVAL levels, spendable on
# raising one of their skills a rank (see engine/skills.py's MAX_SKILL_RANK / game/heroes.py's
# upgrade_skill_rank). At MAX_LEVEL that's 60 // 5 = 12 points total per hero -- not enough to max every
# skill in a 4-skill kit to rank 10 (that would take 4 * 9 = 36), so choosing which abilities to invest
# in is a real, permanent-feeling decision, not just busywork.
TALENT_POINT_INTERVAL = 5


# The first few levels are cheap: a level-1 hero pays EARLY_XP_FLOOR of the full price, climbing in a straight
# line to the full price at EARLY_XP_FULL_LEVEL (so 1->2 is 40% of the curve, 4->5 about 70%, 8->9 onward 100%).
EARLY_XP_FLOOR = 0.40
EARLY_XP_FULL_LEVEL = 8


def _early_xp_factor(level: int) -> float:
    if level >= EARLY_XP_FULL_LEVEL:
        return 1.0
    t = (max(1, level) - 1) / (EARLY_XP_FULL_LEVEL - 1)
    return EARLY_XP_FLOOR + (1.0 - EARLY_XP_FLOOR) * t


def full_xp_for_next_level(level: int, story: bool = False) -> int:
    """The undiscounted curve (what xp_for_next_level was before the early-level discount). story_fight_xp
    still pays out against this one, so a discounted early level really does take fewer fights."""
    if story:
        n = max(0, level - 1)
        return round(60 + 30 * n + 1.2 * n * n)
    return 40 + 20 * (level - 1)


def xp_for_next_level(level: int, story: bool = False) -> int:
    """XP required to go from `level` to `level + 1`. A gently increasing
    curve -- about 1->2 costs 16, 2->3 costs 29, ... full price from level 8 on (+20
    per level, 40 + 20 * (level - 1)) -- so leveling slows down gradually instead of spiking
    exponentially. Undefined/irrelevant at MAX_LEVEL and above.

    `story=True` is the much longer curve story (Mythic) heroes climb to level 99: 60 + 30n + 1.2n^2 for
    n = level - 1 (about 417 at level 10, 1.9k at 30, 6k at 60, 14k at 98), with the same cheap early levels."""
    return max(1, round(full_xp_for_next_level(level, story) * _early_xp_factor(level)))


def story_fight_xp(enemy_level: int, rng=None) -> int:
    """XP each story hero earns for a normal fight outside the Colosseum: about 1/9 of a level at the
    enemies' level (so roughly nine even fights per level the whole way up), with a little variance."""
    import random as _r
    r = rng or _r
    return max(1, round(full_xp_for_next_level(max(1, int(enemy_level)), True) * 0.11 * r.uniform(0.85, 1.15)))


# --- Level-99 scale (Andrew: a level-99 hero lands near 9999 HP / 999 MP / 999 in their main stats) -----------
# Hero classes (data/classes.py) now carry growth that reaches those numbers. Monsters, bosses and everything else
# built from a hand-tuned ENEMY archetype keep their small per-level growth tables, so apply_growth(enemy=True)
# multiplies that growth by ENEMY_GROWTH_SCALE (the same factor the class growth went up by, on average). Level-1
# stats are untouched. Because HP grew ~9x and offense/defense only ~2.8x, damage and healing get a level-based
# POWER_MULT (see power_mult) so a fight lasts about as many rounds as before; gear bonuses and item heals scale
# the same way (stat_scale / scale_item_heal).
ENEMY_GROWTH_SCALE = {"max_hp": 9.2, "atk": 2.8, "def_": 2.8, "mag": 2.8, "res": 2.8}

# Class-average reference blocks used only to turn "level" into those scale factors: [level-1 value, old growth, new growth].
_REF_HP = (94.0, 5.8, 53.2)
_REF_OFF = (20.0, 2.0, 5.6)


def _ref_ratio(ref, n: float) -> float:
    base, old, new = ref
    return (base + new * n) / (base + old * n)


def stat_scale(stat: str, level: int, growth_mult: float = 1.0) -> float:
    """How much bigger a stat is at `level` than it was before the level-99 rebalance (1.0 at level 1, about 8 for
    HP and 2.6 for ATK/DEF/MAG/RES at level 99). Flat gear bonuses are multiplied by this so equipment stays the
    same share of a hero's stats as before. MP/SPD/LUK are not rescaled."""
    n = max(0, level - 1) * growth_mult
    if stat == "max_hp":
        return _ref_ratio(_REF_HP, n)
    if stat in ("atk", "def_", "mag", "res"):
        return _ref_ratio(_REF_OFF, n)
    return 1.0


def power_mult(level: int, growth_mult: float = 1.0) -> float:
    """Multiplier on every damage and heal roll made by a combatant of this level (1.0 at level 1, about 3 at 99):
    HP grew faster than ATK/MAG, so without it every fight would drag on ~3x as many rounds."""
    return stat_scale("max_hp", level, growth_mult) / stat_scale("atk", level, growth_mult)


ITEM_HEAL_REF_HP = 230.0   # a potion's listed 100 HP is calibrated for a hero with about this much max HP
ITEM_HEAL_EXP = 0.75       # items scale with max HP to this power, so they stay useful without becoming full heals


def scale_item_heal(amount: int, max_hp: int) -> int:
    """HP restored by an item with a listed `amount`, grown for a target whose max HP is far above the level-10 hero
    the listed numbers were written for. A target at or below ITEM_HEAL_REF_HP gets exactly `amount`."""
    if amount <= 0:
        return 0
    return max(1, round(amount * max(1.0, max_hp / ITEM_HEAL_REF_HP) ** ITEM_HEAL_EXP))


def apply_growth(base_stats: Stats, growth: Stats, level: int, growth_mult: float = 1.0, enemy: bool = False) -> Stats:
    """base_stats is the level-1 block (a class archetype's or enemy
    archetype's `base_stats`); growth is that archetype's flat per-level
    increment (`growth`). Level 1 returns base_stats unchanged -- "levels
    gained past 1" is what actually multiplies the growth block.
    `enemy=True` (monsters, bosses) additionally multiplies the growth by ENEMY_GROWTH_SCALE."""
    levels_gained = max(0, level - 1) * growth_mult
    k = ENEMY_GROWTH_SCALE if enemy else {}
    stats = base_stats.copy()
    stats.max_hp += round(growth.max_hp * levels_gained * k.get("max_hp", 1.0))
    stats.max_mp += round(growth.max_mp * levels_gained)
    stats.atk += round(growth.atk * levels_gained * k.get("atk", 1.0))
    stats.def_ += round(growth.def_ * levels_gained * k.get("def_", 1.0))
    stats.mag += round(growth.mag * levels_gained * k.get("mag", 1.0))
    stats.res += round(growth.res * levels_gained * k.get("res", 1.0))
    stats.spd += round(growth.spd * levels_gained)
    stats.luk += round(growth.luk * levels_gained)
    return stats


def resolve_level_up(level: int, xp: int, level_cap: int = MAX_LEVEL, story: bool = False) -> Tuple[int, int, int]:
    """Given a character's current level and their accumulated XP toward
    the next one, resolves as many level-ups as that XP covers (a single
    big grant can cross more than one threshold at once). Returns
    (new_level, remaining_xp, levels_gained). Caps at `level_cap` -- any XP
    earned past that point is simply not spent (xp stops climbing once it
    would have no next level to buy). Defaults to MAX_LEVEL (the engine's
    absolute ceiling) but a caller with a lower per-character cap --
    PlayerCharacter.level_cap, from data/hero_rarity.py's rarity-based caps
    -- passes that instead, so an owned hero stops gaining levels well
    before the engine's own ceiling, once they hit their own rarity's cap."""
    level_cap = min(level_cap, MAX_LEVEL)
    levels_gained = 0
    while level < level_cap:
        needed = xp_for_next_level(level, story)
        if xp < needed:
            break
        xp -= needed
        level += 1
        levels_gained += 1
    if level >= level_cap:
        xp = 0
    return level, xp, levels_gained

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

MAX_LEVEL = 60

# Talent points (Andrew's request): a hero earns one every TALENT_POINT_INTERVAL levels, spendable on
# raising one of their skills a rank (see engine/skills.py's MAX_SKILL_RANK / game/heroes.py's
# upgrade_skill_rank). At MAX_LEVEL that's 60 // 5 = 12 points total per hero -- not enough to max every
# skill in a 4-skill kit to rank 10 (that would take 4 * 9 = 36), so choosing which abilities to invest
# in is a real, permanent-feeling decision, not just busywork.
TALENT_POINT_INTERVAL = 5


def xp_for_next_level(level: int) -> int:
    """XP required to go from `level` to `level + 1`. A gently increasing
    curve -- 1->2 costs 40, 2->3 costs 60, 3->4 costs 80, and so on (+20
    per level) -- so leveling slows down gradually instead of spiking
    exponentially. Undefined/irrelevant at MAX_LEVEL and above."""
    return 40 + 20 * (level - 1)


def apply_growth(base_stats: Stats, growth: Stats, level: int) -> Stats:
    """base_stats is the level-1 block (a class archetype's or enemy
    archetype's `base_stats`); growth is that archetype's flat per-level
    increment (`growth`). Level 1 returns base_stats unchanged -- "levels
    gained past 1" is what actually multiplies the growth block."""
    levels_gained = max(0, level - 1)
    stats = base_stats.copy()
    stats.max_hp += growth.max_hp * levels_gained
    stats.max_mp += growth.max_mp * levels_gained
    stats.atk += growth.atk * levels_gained
    stats.def_ += growth.def_ * levels_gained
    stats.mag += growth.mag * levels_gained
    stats.res += growth.res * levels_gained
    stats.spd += growth.spd * levels_gained
    stats.luk += growth.luk * levels_gained
    return stats


def resolve_level_up(level: int, xp: int, level_cap: int = MAX_LEVEL) -> Tuple[int, int, int]:
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
        needed = xp_for_next_level(level)
        if xp < needed:
            break
        xp -= needed
        level += 1
        levels_gained += 1
    if level >= level_cap:
        xp = 0
    return level, xp, levels_gained

"""Skill (spell/ability) definitions."""
from dataclasses import dataclass
from typing import Optional
from engine.types import Element, TargetType


@dataclass
class Skill:
    id: str
    name: str
    mp_cost: int
    power: float                 # multiplier applied to ATK (physical) or MAG (magical/heal)
    kind: str                    # "physical" | "magical" | "heal"
    element: Element = Element.NONE
    target: TargetType = TargetType.SINGLE_ENEMY
    status_to_apply: Optional[str] = None   # key into STATUS_DB
    status_chance: float = 0.0              # 0..1
    lifesteal: float = 0.0                  # fraction of dealt damage the caster heals for (magical/physical)
    description: str = ""

    def is_offensive(self) -> bool:
        return self.kind in ("physical", "magical")


# --- Skill ranks (talent points) --------------------------------------------
#
# Andrew's request: every ability has 10 ranks, each rank more potent than the last but costing more
# MP, and a hero gets a talent point to spend on this every 5 levels (see data/leveling.py's
# TALENT_POINT_INTERVAL). Rank is per-hero, per-skill state (game/roster.py's PlayerCharacter.skill_ranks,
# carried onto their battle Combatant as skill_ranks -- see engine/combatant.py); the base `Skill` objects
# above stay exactly as authored (the rank-1 numbers) and every rank above 1 is a scale-up computed here
# at the moment a skill is actually used or displayed, rather than mutating/duplicating Skill objects per
# rank per hero. A skill's id/kind/element/target/status/lifesteal are unchanged by rank -- only power and
# MP cost scale, exactly per Andrew's spec ("more potent... but also costing more mp").
MAX_SKILL_RANK = 10
# +8% power per rank above 1 -- rank 10 is +72% power over rank 1. First-pass number, same "retune by
# feel" spirit as every other numeric constant in this project.
RANK_POWER_STEP = 0.08
# +12% MP cost per rank above 1 -- rank 10 is +108% MP cost (more than double), so pushing a skill to max
# rank is a real MP-economy tradeoff, not a pure upgrade.
RANK_MP_COST_STEP = 0.12


def clamp_skill_rank(rank: int) -> int:
    return max(1, min(MAX_SKILL_RANK, int(rank)))


def power_at_rank(skill: "Skill", rank: int) -> float:
    r = clamp_skill_rank(rank)
    return skill.power * (1 + RANK_POWER_STEP * (r - 1))


def mp_cost_at_rank(skill: "Skill", rank: int) -> int:
    r = clamp_skill_rank(rank)
    return max(0, round(skill.mp_cost * (1 + RANK_MP_COST_STEP * (r - 1))))


# power_at_rank does nothing for a pure status/buff skill (power=0, e.g. Iron Stance's self def_up) --
# ranking one of those would otherwise ONLY raise its MP cost with no upside, which contradicts "more
# potent than the last." So a status application (engine/battle.py's _do_skill, when
# skill.status_to_apply triggers) also gets extra turns of duration per rank -- +1 turn per
# RANK_STATUS_DURATION_STEP ranks above 1, capped at rank 10's bonus. A permanent status (duration <= 0,
# e.g. bloodlust/marked/bulwark's -1 "until cured/battle end") is untouched -- there's no "longer" than
# permanent.
RANK_STATUS_DURATION_STEP = 3


def status_duration_bonus_at_rank(rank: int) -> int:
    r = clamp_skill_rank(rank)
    return (r - 1) // RANK_STATUS_DURATION_STEP

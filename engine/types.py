"""Shared enums used across the engine."""
from enum import Enum


class Element(str, Enum):
    PHYSICAL = "physical"   # non-elemental physical damage
    FIRE = "fire"
    ICE = "ice"
    THUNDER = "thunder"
    HOLY = "holy"
    DARK = "dark"
    NONE = "none"           # true damage / status effects with no element


class TargetType(str, Enum):
    SINGLE_ENEMY = "single_enemy"
    ALL_ENEMIES = "all_enemies"
    SINGLE_ALLY = "single_ally"     # includes self
    ALL_ALLIES = "all_allies"
    SELF = "self"
    ALL = "all_allies && all_enemies"


class ActionType(str, Enum):
    ATTACK = "attack"
    SKILL = "skill"
    ITEM = "item"
    DEFEND = "defend"
    FLEE = "flee"


class BattleResult(str, Enum):
    ONGOING = "ongoing"
    VICTORY = "victory"
    DEFEAT = "defeat"
    FLED = "fled"

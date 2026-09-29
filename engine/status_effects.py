"""Status effect definitions and the registry of ones available in the game.

A StatusEffect *instance* attached to a Combatant carries its own remaining
duration; the registry below holds immutable templates that get cloned.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class StatusEffect:
    key: str
    name: str
    duration: int                              # turns remaining; -1 = until cured/battle end
    stat_mods: Dict[str, float] = field(default_factory=dict)   # e.g. {"atk": 1.3} multiplicative
    dot_damage: int = 0                          # flat damage applied at start of holder's turn
    skip_turn: bool = False                      # stun/sleep/paralyze: holder loses their action
    icon_color: tuple = (200, 200, 200)          # placeholder-UI tint
    description: str = ""

    def clone(self, duration: Optional[int] = None) -> "StatusEffect":
        return StatusEffect(
            key=self.key,
            name=self.name,
            duration=self.duration if duration is None else duration,
            stat_mods=dict(self.stat_mods),
            dot_damage=self.dot_damage,
            skip_turn=self.skip_turn,
            icon_color=self.icon_color,
            description=self.description,
        )


# --- Registry of status effects available in the game ---------------------
STATUS_DB: Dict[str, StatusEffect] = {
    "poison": StatusEffect(
        key="poison", name="Poison", duration=3, dot_damage=0,  # dot_damage computed dynamically (see battle.py)
        icon_color=(140, 60, 200), description="Takes damage each turn.",
    ),
    "stun": StatusEffect(
        key="stun", name="Stunned", duration=1, skip_turn=True,
        icon_color=(220, 200, 40), description="Loses their next action.",
    ),
    "atk_up": StatusEffect(
        key="atk_up", name="Attack Up", duration=3, stat_mods={"atk": 1.3},
        icon_color=(220, 90, 60), description="Physical attack raised.",
    ),
    "atk_down": StatusEffect(
        key="atk_down", name="Attack Down", duration=3, stat_mods={"atk": 0.7},
        icon_color=(120, 90, 160), description="Physical attack lowered.",
    ),
    "def_up": StatusEffect(
        key="def_up", name="Defense Up", duration=3, stat_mods={"def_": 1.3},
        icon_color=(70, 130, 220), description="Physical defense raised.",
    ),
    "def_down": StatusEffect(
        key="def_down", name="Defense Down", duration=3, stat_mods={"def_": 0.7},
        icon_color=(160, 100, 70), description="Physical defense lowered.",
    ),
    "regen": StatusEffect(
        key="regen", name="Regen", duration=3, dot_damage=0,
        icon_color=(80, 200, 120), description="Recovers HP each turn.",
    ),
}


def get_status(key: str) -> StatusEffect:
    return STATUS_DB[key].clone()

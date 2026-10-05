"""Combatant: the single class backing both party members and enemies.

Keeping one class for both sides (rather than separate Character/Enemy
classes) keeps the battle engine's logic symmetric -- the same damage
formulas, status handling, and turn-order code apply no matter which side
is acting. `is_enemy` plus a couple of optional AI-flavor fields is all
that distinguishes an enemy from a hero.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import itertools

from engine.stats import Stats
from engine.types import Element
from engine.status_effects import StatusEffect
from engine.formation import DEFAULT_FORMATION, clamp_formation

_id_counter = itertools.count(1)


@dataclass
class Combatant:
    name: str
    base_stats: Stats
    is_enemy: bool
    skill_ids: List[str] = field(default_factory=list)
    # Battle formation (engine/formation.py): "front"/"middle"/"rear". Set once at construction --
    # from a hero's own PlayerCharacter.formation (game/roster.py's build_combatant), or auto-assigned
    # for an enemy/hero-rival/boss (engine/formation.py's auto_formation). Drives per-hit damage/
    # healing modifiers (engine/formulas.py) and single-target reach (engine/formation.py's
    # reachable_targets, used by engine/battle.py's _resolve_targets).
    formation: str = DEFAULT_FORMATION
    # Whether this combatant is a melee fighter for TARGETING purposes -- i.e. can be blocked by an
    # occupied enemy front row. Deliberately independent of any one skill's kind (physical/magical);
    # see this module's formation-related fields and engine/formation.py's module docstring for why.
    is_melee: bool = True
    # skill_id -> rank (1-10, see engine/skills.py's MAX_SKILL_RANK). Missing = rank 1 (unranked/base).
    # Only ever populated for a hero-built Combatant (game/roster.py's build_combatant, from
    # PlayerCharacter.skill_ranks) -- enemies never rank up, so this stays empty for them.
    skill_ranks: Dict[str, int] = field(default_factory=dict)
    resistances: Dict[Element, float] = field(default_factory=dict)  # multiplier; <1 resist, >1 weak, 0 immune
    persona: str = ""            # flavor text describing how this enemy fights (the tactics themselves live in ai/enemy_ai.py)
    sprite_color: tuple = (180, 60, 60)   # placeholder-UI fill color
    id: str = field(default_factory=lambda: f"c{next(_id_counter)}")

    def __post_init__(self):
        self.hp: int = self.base_stats.max_hp
        self.mp: int = self.base_stats.max_mp
        self.status_effects: List[StatusEffect] = []
        self.defending: bool = False
        self.formation = clamp_formation(self.formation)
        # --- ATB (engine/battle.py's step()): gauge 0..1 while "charging", then "ready" (waiting for a command),
        # then "casting" (a skill with a cast time) until it resolves and the gauge starts over.
        self.atb_gauge: float = 0.0
        self.atb_phase: str = "charging"
        self.cast: Optional[dict] = None          # {"action", "total", "left", "name", "pushed"} while casting
        self.ready_since: float = 0.0
        self.turn_count: int = 0                  # commands requested from this combatant so far
        self.turns_skipped: int = 0               # turns lost to a stun

    # --- state queries -----------------------------------------------
    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def max_hp(self) -> int:
        return self.base_stats.max_hp

    @property
    def max_mp(self) -> int:
        return self.base_stats.max_mp

    def effective_stat(self, name: str) -> float:
        """Base stat with active status-effect multipliers applied (min 1)."""
        value = float(getattr(self.base_stats, name))
        for status in self.status_effects:
            mult = status.stat_mods.get(name)
            if mult is not None:
                value *= mult
        return max(1.0, value)

    def rank_of(self, skill_id: str) -> int:
        return self.skill_ranks.get(skill_id, 1)

    def has_status(self, key: str) -> bool:
        return any(s.key == key for s in self.status_effects)

    def is_stunned(self) -> bool:
        return any(s.skip_turn for s in self.status_effects)

    # --- state mutation ------------------------------------------------
    def take_damage(self, amount: int) -> int:
        """Applies damage, clamped so HP never goes below 0. Returns actual damage dealt."""
        amount = max(0, amount)
        dealt = min(self.hp, amount)
        self.hp -= dealt
        return dealt

    def heal(self, amount: int) -> int:
        """Heals, clamped to max_hp. Returns actual amount healed. No-op if KO'd (use revive)."""
        if not self.alive:
            return 0
        amount = max(0, amount)
        healed = min(self.max_hp - self.hp, amount)
        self.hp += healed
        return healed

    def revive(self, hp_amount: int) -> None:
        self.hp = min(self.max_hp, max(1, hp_amount))

    unlimited_mp = False      # scripted bosses: MP is never spent (their script, not a mana pool, limits them)

    def spend_mp(self, amount: int) -> bool:
        if self.unlimited_mp:
            return True
        if self.mp < amount:
            return False
        self.mp -= amount
        return True

    def restore_mp(self, amount: int) -> int:
        amount = max(0, amount)
        restored = min(self.max_mp - self.mp, amount)
        self.mp += restored
        return restored

    def add_status(self, status: StatusEffect) -> None:
        """Adds a status effect, refreshing duration if the combatant already has it."""
        existing = next((s for s in self.status_effects if s.key == status.key), None)
        if existing:
            existing.duration = max(existing.duration, status.duration)
        else:
            self.status_effects.append(status)

    def remove_status(self, key: str) -> bool:
        before = len(self.status_effects)
        self.status_effects = [s for s in self.status_effects if s.key != key]
        return len(self.status_effects) != before

    def clear_all_status(self) -> None:
        self.status_effects = []

    def tick_statuses(self) -> List[str]:
        """Called once at the start of this combatant's own turn.

        Applies damage/heal-over-time, then decrements durations and expires
        any that hit zero. Returns a list of human-readable log lines.
        """
        events: List[str] = []
        for status in self.status_effects:
            if status.dot_damage > 0:
                if status.key == "regen":
                    healed = self.heal(status.dot_damage)
                    if healed:
                        events.append(f"{self.name} regenerates {healed} HP from {status.name}.")
                else:
                    dealt = self.take_damage(status.dot_damage)
                    if dealt:
                        events.append(f"{self.name} takes {dealt} damage from {status.name}.")
        expired = []
        for status in self.status_effects:
            if status.duration > 0:
                status.duration -= 1
                if status.duration <= 0:
                    expired.append(status)
        for status in expired:
            self.status_effects.remove(status)
            events.append(f"{status.name} wore off {self.name}.")
        return events

    def to_public_dict(self) -> dict:
        """A trimmed-down view of this combatant, safe to hand to the UI or the enemy AI."""
        return {
            "id": self.id,
            "name": self.name,
            "is_enemy": self.is_enemy,
            "alive": self.alive,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "mp": self.mp,
            "max_mp": self.max_mp,
            "statuses": [s.key for s in self.status_effects],
            "defending": self.defending,
            "sprite_color": self.sprite_color,
            "formation": self.formation,
            "is_melee": self.is_melee,
            "atb_phase": self.atb_phase,
            "casting": self.cast["name"] if self.cast else None,
        }

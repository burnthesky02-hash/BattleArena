"""The Action a combatant takes on their turn, and validation helpers.

Both the human player (via a UI) and the rule-based enemy AI (via ai/enemy_ai.py) ultimately
produce one of these; battle.py doesn't care which.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from engine.types import ActionType


@dataclass
class Action:
    type: ActionType
    actor_id: str
    target_ids: List[str] = field(default_factory=list)
    skill_id: Optional[str] = None
    item_id: Optional[str] = None
    # --- ATB extras a scripted/AI "heavy" move can attach to an ordinary skill (see ai/enemy_ai.py, game/boss_script.py) ---
    cast_time: Optional[float] = None   # seconds of cast bar, replacing the skill's own
    no_pushback: bool = False           # hits on the caster do not delay this cast (a stun still cancels it)
    brace_mult: float = 1.0             # damage multiplier on targets that are NOT defending ("Defend or die")
    power_mult: float = 1.0             # plain damage multiplier on top of the skill's power

    @staticmethod
    def attack(actor_id: str, target_id: str) -> "Action":
        return Action(ActionType.ATTACK, actor_id, [target_id])

    @staticmethod
    def use_skill(actor_id: str, skill_id: str, target_ids: List[str], **extra) -> "Action":
        return Action(ActionType.SKILL, actor_id, target_ids, skill_id=skill_id, **extra)

    @staticmethod
    def use_item(actor_id: str, item_id: str, target_ids: List[str]) -> "Action":
        return Action(ActionType.ITEM, actor_id, target_ids, item_id=item_id)

    @staticmethod
    def defend(actor_id: str) -> "Action":
        return Action(ActionType.DEFEND, actor_id, [])

    @staticmethod
    def flee(actor_id: str) -> "Action":
        return Action(ActionType.FLEE, actor_id, [])

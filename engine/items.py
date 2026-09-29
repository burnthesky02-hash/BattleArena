"""Consumable item definitions usable in battle."""
from dataclasses import dataclass
from typing import Optional
from engine.types import TargetType


@dataclass
class Item:
    id: str
    name: str
    heal_hp: int = 0
    heal_mp: int = 0
    cure_status: Optional[str] = None   # a STATUS_DB key, or "all" to cure everything
    revive: bool = False                # brings a KO'd ally back with heal_hp HP
    target: TargetType = TargetType.SINGLE_ALLY
    description: str = ""
    cost: int = 0   # money cost in the Shop; 0 = not shop-purchasable

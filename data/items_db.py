"""The item registry and the party's starting inventory."""
from engine.items import Item
from engine.types import TargetType

ITEMS = {
    "potion": Item(
        id="potion", name="Potion", heal_hp=40, target=TargetType.SINGLE_ALLY,
        description="Restores 40 HP to one ally.", cost=15,
    ),
    "hi_potion": Item(
        id="hi_potion", name="Hi-Potion", heal_hp=100, target=TargetType.SINGLE_ALLY,
        description="Restores 100 HP to one ally.", cost=40,
    ),
    "ether": Item(
        id="ether", name="Ether", heal_mp=25, target=TargetType.SINGLE_ALLY,
        description="Restores 25 MP to one ally.", cost=20,
    ),
    "antidote": Item(
        id="antidote", name="Antidote", cure_status="poison", target=TargetType.SINGLE_ALLY,
        description="Cures poison.", cost=10,
    ),
    "phoenix_down": Item(
        id="phoenix_down", name="Phoenix Down", heal_hp=60, revive=True, target=TargetType.SINGLE_ALLY,
        description="Revives a fallen ally with some HP.", cost=60,
    ),
}

# Item id -> starting count. Only party members draw from this (see BattleEngine.inventory).
STARTING_INVENTORY = {
    "potion": 4,
    "hi_potion": 1,
    "ether": 2,
    "antidote": 2,
    "phoenix_down": 1,
}

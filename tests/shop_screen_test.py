"""Exercises ui/pygame_ui.py's Shop screen (tabs and buying) against the
fake pygame module, the same approach as tests/meta_screens_test.py. Gear
management (equip/unequip) moved to the Heroes screen as of the
hero-rarity pass -- see tests/heroes_screen_test.py for that coverage;
Shop no longer has a "Gear" tab at all.

Run directly: python3 tests/shop_screen_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.pygame_stub import make_pygame_stub, Event

event_queue = []
sys.modules["pygame"] = make_pygame_stub(event_queue)

from data.equipment_db import EQUIPMENT  # noqa: E402
from data.items_db import ITEMS  # noqa: E402
from data.skills_db import SKILLS  # noqa: E402
from game.player_state import PlayerState  # noqa: E402
from game.roster import PlayerCharacter  # noqa: E402
from ui.pygame_ui import PygameUI  # noqa: E402

MOUSEBUTTONDOWN = 3


def click_at(x, y) -> Event:
    return Event(MOUSEBUTTONDOWN, type=MOUSEBUTTONDOWN, button=1, pos=(x, y))


def _fresh(money=200):
    ui = PygameUI(SKILLS, ITEMS)
    hero = PlayerCharacter(name="Buyer", class_id="tank")
    state = PlayerState.new_game(hero)
    state.money = money
    return ui, state, hero


def test_items_tab_is_default_and_buying_updates_money_and_inventory():
    ui, state, hero = _fresh(money=100)
    starting_antidotes = state.inventory.get("antidote", 0)
    event_queue.clear()
    # Items sorted by cost ascending: antidote(10) is row 0 at y=142.
    event_queue.append(click_at(40, 150))
    event_queue.append(click_at(30, ui.height - 40))  # "Back to Colosseum"
    ui.show_shop(state, ITEMS, EQUIPMENT)
    assert state.money == 100 - ITEMS["antidote"].cost
    assert state.inventory["antidote"] == starting_antidotes + 1
    print("test_items_tab_is_default_and_buying_updates_money_and_inventory: PASS")


def test_switching_to_weapon_tab_and_buying_adds_to_stash():
    ui, state, hero = _fresh(money=200)
    event_queue.clear()
    event_queue.append(click_at(196, 100))   # "Weapons" tab (2nd of 5, x=30+156=186..334)
    event_queue.append(click_at(40, 150))    # cheapest weapon (rusty_sword, cost 60) at row 0
    event_queue.append(click_at(30, ui.height - 40))
    ui.show_shop(state, ITEMS, EQUIPMENT)
    assert state.money == 200 - EQUIPMENT["rusty_sword"].cost
    assert state.owned_equipment.get("rusty_sword") == 1
    assert hero.equipped["weapon"] is None, "buying should not auto-equip"
    print("test_switching_to_weapon_tab_and_buying_adds_to_stash: PASS")


def test_cannot_afford_purchase_is_not_clickable():
    ui, state, hero = _fresh(money=5)  # less than antidote's cost (10)
    starting_antidotes = state.inventory.get("antidote", 0)
    event_queue.clear()
    event_queue.append(click_at(40, 150))  # would-be antidote row -- unaffordable, not clickable
    event_queue.append(click_at(30, ui.height - 40))
    ui.show_shop(state, ITEMS, EQUIPMENT)
    assert state.money == 5, "an unaffordable row must not be purchasable"
    assert state.inventory.get("antidote", 0) == starting_antidotes, "unaffordable click must not grant the item"
    print("test_cannot_afford_purchase_is_not_clickable: PASS")


def test_back_button_returns_without_side_effects():
    ui, state, hero = _fresh(money=200)
    event_queue.clear()
    event_queue.append(click_at(30, ui.height - 40))  # immediately back out
    ui.show_shop(state, ITEMS, EQUIPMENT)
    assert state.money == 200
    print("test_back_button_returns_without_side_effects: PASS")


def test_shop_has_no_gear_tab():
    """The Shop screen should offer exactly the 4 buying tabs -- no "Gear"
    tab, since equip/unequip moved to the Heroes screen (see
    tests/heroes_screen_test.py)."""
    ui, state, hero = _fresh(money=200)
    state.owned_equipment["rusty_sword"] = 1
    event_queue.clear()
    # Where "Gear" used to be (664, 100) is past the last real tab now --
    # clicking there should be a no-op, not equip anything.
    event_queue.append(click_at(664, 100))
    event_queue.append(click_at(30, ui.height - 40))
    ui.show_shop(state, ITEMS, EQUIPMENT)
    assert hero.equipped["weapon"] is None, "there's no Gear tab left to equip from"
    assert state.owned_equipment.get("rusty_sword") == 1
    print("test_shop_has_no_gear_tab: PASS")


def main():
    test_items_tab_is_default_and_buying_updates_money_and_inventory()
    test_switching_to_weapon_tab_and_buying_adds_to_stash()
    test_cannot_afford_purchase_is_not_clickable()
    test_shop_has_no_gear_tab()
    test_back_button_returns_without_side_effects()
    print("\nALL SHOP SCREEN TESTS PASSED")


if __name__ == "__main__":
    main()

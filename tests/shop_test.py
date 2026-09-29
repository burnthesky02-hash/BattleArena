"""Headless coverage for game/shop.py -- buying items/equipment and moving
gear between the unequipped stash and a character's equipped slots. No UI
involved, same as engine/'s tests: these are plain functions over
PlayerState/PlayerCharacter, so they're exercised directly.

Run directly: python3 tests/shop_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.equipment_db import EQUIPMENT
from data.items_db import ITEMS
from game import shop
from game.player_state import PlayerState
from game.roster import PlayerCharacter


def _fresh_state(money=200):
    hero = PlayerCharacter(name="Buyer", class_id="tank")
    state = PlayerState.new_game(hero)
    state.money = money
    return state, hero


def test_buy_item_deducts_money_and_adds_inventory():
    state, _ = _fresh_state(money=100)
    starting_potions = state.inventory.get("potion", 0)
    ok, msg = shop.buy_item(state, "potion", ITEMS)
    assert ok, msg
    assert state.money == 100 - ITEMS["potion"].cost
    assert state.inventory["potion"] == starting_potions + 1
    print(f"test_buy_item_deducts_money_and_adds_inventory: PASS ({msg})")


def test_buy_item_fails_cleanly_when_too_poor_or_unknown():
    state, _ = _fresh_state(money=0)
    ok, msg = shop.buy_item(state, "potion", ITEMS)
    assert not ok and "Not enough money" in msg, msg
    assert state.money == 0  # nothing should have been deducted on failure

    ok, msg = shop.buy_item(state, "does_not_exist", ITEMS)
    assert not ok and "doesn't exist" in msg, msg
    print("test_buy_item_fails_cleanly_when_too_poor_or_unknown: PASS")


def test_buy_equipment_adds_to_stash_not_equipped_slot():
    state, hero = _fresh_state(money=200)
    ok, msg = shop.buy_equipment(state, "rusty_sword", EQUIPMENT)
    assert ok, msg
    assert state.owned_equipment.get("rusty_sword") == 1
    assert hero.equipped["weapon"] is None, "buying gear should not auto-equip it"
    print(f"test_buy_equipment_adds_to_stash_not_equipped_slot: PASS ({msg})")


def test_legendary_equipment_is_not_shop_purchasable():
    state, _ = _fresh_state(money=999999)
    ok, msg = shop.buy_equipment(state, "flameheart_blade", EQUIPMENT)  # legendary, cost=0
    assert not ok, msg
    assert "summon-only" in msg or "isn't for sale" in msg
    assert "flameheart_blade" not in state.owned_equipment
    print(f"test_legendary_equipment_is_not_shop_purchasable: PASS ({msg})")


def test_equip_from_stash_moves_item_and_returns_previous_to_stash():
    state, hero = _fresh_state(money=500)
    shop.buy_equipment(state, "rusty_sword", EQUIPMENT)
    shop.buy_equipment(state, "knights_blade", EQUIPMENT)

    ok, msg = shop.equip_from_stash(state, hero.id, "rusty_sword", EQUIPMENT)
    assert ok, msg
    assert hero.equipped["weapon"] == "rusty_sword"
    assert "rusty_sword" not in state.owned_equipment, "equipped copy should leave the stash"

    ok, msg = shop.equip_from_stash(state, hero.id, "knights_blade", EQUIPMENT)
    assert ok, msg
    assert hero.equipped["weapon"] == "knights_blade"
    assert state.owned_equipment.get("rusty_sword") == 1, "swapping weapons should return the old one to the stash"
    print("test_equip_from_stash_moves_item_and_returns_previous_to_stash: PASS")


def test_equip_from_stash_fails_if_not_owned():
    state, hero = _fresh_state(money=0)
    ok, msg = shop.equip_from_stash(state, hero.id, "rusty_sword", EQUIPMENT)
    assert not ok and "don't own" in msg, msg
    print("test_equip_from_stash_fails_if_not_owned: PASS")


def test_unequip_returns_item_to_stash():
    state, hero = _fresh_state(money=500)
    shop.buy_equipment(state, "rusty_sword", EQUIPMENT)
    shop.equip_from_stash(state, hero.id, "rusty_sword", EQUIPMENT)

    ok, msg = shop.unequip(state, hero.id, "weapon", EQUIPMENT)
    assert ok, msg
    assert hero.equipped["weapon"] is None
    assert state.owned_equipment.get("rusty_sword") == 1

    ok, msg = shop.unequip(state, hero.id, "weapon", EQUIPMENT)
    assert not ok and "Nothing is equipped" in msg, msg
    print("test_unequip_returns_item_to_stash: PASS")


def test_shop_actions_reject_an_unknown_character_id():
    state, _ = _fresh_state(money=200)
    shop.buy_equipment(state, "rusty_sword", EQUIPMENT)
    ok, msg = shop.equip_from_stash(state, "not-a-real-id", "rusty_sword", EQUIPMENT)
    assert not ok and "Unknown character" in msg, msg
    ok, msg = shop.unequip(state, "not-a-real-id", "weapon", EQUIPMENT)
    assert not ok and "Unknown character" in msg, msg
    print("test_shop_actions_reject_an_unknown_character_id: PASS")


def main():
    test_buy_item_deducts_money_and_adds_inventory()
    test_buy_item_fails_cleanly_when_too_poor_or_unknown()
    test_buy_equipment_adds_to_stash_not_equipped_slot()
    test_legendary_equipment_is_not_shop_purchasable()
    test_equip_from_stash_moves_item_and_returns_previous_to_stash()
    test_equip_from_stash_fails_if_not_owned()
    test_unequip_returns_item_to_stash()
    test_shop_actions_reject_an_unknown_character_id()
    print("\nALL SHOP TESTS PASSED")


if __name__ == "__main__":
    main()

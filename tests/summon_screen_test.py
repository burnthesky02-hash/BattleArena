"""Exercises ui/pygame_ui.py's Summon screen -- a left banner rail (Hero
Summon / Gear Summon) + splash panel + 1x/10x pull buttons when idle, and a
card-flip reveal (one big card for a 1x pull, a 5-wide grid for a 10x pull)
after a pull -- against the fake pygame module, the same approach as
tests/heroes_screen_test.py.

Coordinates below are derived from the same module-level constants
ui/pygame_ui.py's show_summon uses (SUMMON_RAIL_*, SUMMON_PANEL_X,
SUMMON_PULL_BTN_*, SUMMON_SOLO_CARD_*, SUMMON_REVEAL_*), imported directly
rather than re-typed as magic numbers, so a future layout tweak can't
silently desync this file from the real one (same convention
tests/heroes_screen_test.py already established).

Run directly: python3 tests/summon_screen_test.py
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
from data.summon_pool import (  # noqa: E402
    CHARACTER_SUMMON_COST, CHARACTER_SUMMON_COST_X10, EQUIPMENT_SUMMON_COST, EQUIPMENT_SUMMON_COST_X10,
    RECRUITABLE_ROSTER, SUMMON_X10_COUNT,
)
from game.player_state import PlayerState  # noqa: E402
from game.roster import PlayerCharacter  # noqa: E402
from ui.pygame_ui import (  # noqa: E402
    SUMMON_PANEL_X, SUMMON_PULL_BTN_GAP, SUMMON_PULL_BTN_H, SUMMON_PULL_BTN_W, SUMMON_RAIL_GAP,
    SUMMON_RAIL_TILE_H, SUMMON_RAIL_W, SUMMON_RAIL_X, SUMMON_RAIL_Y, SUMMON_REVEAL_CARD_GAP,
    SUMMON_REVEAL_CARD_H, SUMMON_REVEAL_CARD_W, SUMMON_REVEAL_COLS, SUMMON_REVEAL_TOP, SUMMON_SOLO_CARD_H,
    SUMMON_SOLO_CARD_W, PygameUI,
)

MOUSEBUTTONDOWN = 3


def click_at(x, y) -> Event:
    return Event(MOUSEBUTTONDOWN, type=MOUSEBUTTONDOWN, button=1, pos=(x, y))


def _fresh(gems=200):
    ui = PygameUI(SKILLS, ITEMS)
    hero = PlayerCharacter(name="Hero", class_id="tank")
    state = PlayerState.new_game(hero)
    state.gems = gems
    return ui, state, hero


def _back_point(ui):
    return 30, ui.height - 40


def _banner_tile_point(index: int):
    """Center of the index-th rail tile -- 0 = Hero Summon, 1 = Gear Summon."""
    x = SUMMON_RAIL_X + SUMMON_RAIL_W // 2
    y = SUMMON_RAIL_Y + index * (SUMMON_RAIL_TILE_H + SUMMON_RAIL_GAP) + SUMMON_RAIL_TILE_H // 2
    return x, y


def _pull_button_point(ui, x10: bool):
    """Center of the "Pull x1"/"Pull x10" button -- position is identical
    regardless of which banner is selected, only the label/cost differs."""
    panel_w = max(300, ui.content_width - SUMMON_PANEL_X - 30)
    pull_y = ui.height - 130
    if x10:
        x = SUMMON_PANEL_X + panel_w // 2 + SUMMON_PULL_BTN_GAP // 2
    else:
        x = SUMMON_PANEL_X + panel_w // 2 - SUMMON_PULL_BTN_W - SUMMON_PULL_BTN_GAP // 2
    return x + SUMMON_PULL_BTN_W // 2, pull_y + SUMMON_PULL_BTN_H // 2


def _solo_card_point(ui):
    x = ui.content_width // 2 - SUMMON_SOLO_CARD_W // 2
    return x + SUMMON_SOLO_CARD_W // 2, 110 + SUMMON_SOLO_CARD_H // 2


def _grid_card_point(ui, index: int):
    grid_w = SUMMON_REVEAL_COLS * (SUMMON_REVEAL_CARD_W + SUMMON_REVEAL_CARD_GAP) - SUMMON_REVEAL_CARD_GAP
    grid_x = ui.content_width // 2 - grid_w // 2
    row, col = divmod(index, SUMMON_REVEAL_COLS)
    x = grid_x + col * (SUMMON_REVEAL_CARD_W + SUMMON_REVEAL_CARD_GAP)
    y = SUMMON_REVEAL_TOP + row * (SUMMON_REVEAL_CARD_H + SUMMON_REVEAL_CARD_GAP)
    return x + SUMMON_REVEAL_CARD_W // 2, y + SUMMON_REVEAL_CARD_H // 2


def _reveal_all_or_continue_point(ui):
    """Same rect either way -- "Reveal All" before every card's flipped,
    "Continue" once they all are."""
    return ui.content_width // 2, ui.height - 50


def test_pulling_x1_character_reveals_a_card_and_recruits_on_continue():
    ui, state, hero = _fresh(gems=100)
    starting_roster = len(state.characters)
    event_queue.clear()
    event_queue.append(click_at(*_pull_button_point(ui, x10=False)))   # Hero Summon is the default banner
    event_queue.append(click_at(*_solo_card_point(ui)))                # flip the one reveal card
    event_queue.append(click_at(*_reveal_all_or_continue_point(ui)))   # Continue back to the select screen
    event_queue.append(click_at(*_back_point(ui)))
    ui.show_summon(state, EQUIPMENT)
    assert state.gems == 100 - CHARACTER_SUMMON_COST
    assert len(state.characters) == starting_roster + 1
    print("test_pulling_x1_character_reveals_a_card_and_recruits_on_continue: PASS")


def test_pulling_x1_equipment_reveals_a_card_and_adds_to_stash():
    ui, state, hero = _fresh(gems=100)
    event_queue.clear()
    event_queue.append(click_at(*_banner_tile_point(1)))                # switch to Gear Summon
    event_queue.append(click_at(*_pull_button_point(ui, x10=False)))
    event_queue.append(click_at(*_reveal_all_or_continue_point(ui)))    # "Reveal All" while face-down...
    event_queue.append(click_at(*_reveal_all_or_continue_point(ui)))    # ...then "Continue" once flipped
    event_queue.append(click_at(*_back_point(ui)))
    ui.show_summon(state, EQUIPMENT)
    assert state.gems == 100 - EQUIPMENT_SUMMON_COST
    assert sum(state.owned_equipment.values()) == 1
    (item_id,) = state.owned_equipment.keys()
    assert EQUIPMENT[item_id].cost <= 0, "Gear Summon must only ever hand out premium gear"
    assert hero.equipped["weapon"] is None, "summoning gear should not auto-equip it"
    print("test_pulling_x1_equipment_reveals_a_card_and_adds_to_stash: PASS")


def test_x10_character_pull_reveals_a_grid_flipping_one_card_leaves_the_rest_face_down():
    ui, state, hero = _fresh(gems=1000)
    starting_roster = len(state.characters)
    event_queue.clear()
    event_queue.append(click_at(*_pull_button_point(ui, x10=True)))
    event_queue.append(click_at(*_grid_card_point(ui, 0)))    # flip just the first card
    event_queue.append(click_at(*_reveal_all_or_continue_point(ui)))   # still "Reveal All" (not everyone's flipped)
    event_queue.append(click_at(*_reveal_all_or_continue_point(ui)))   # now "Continue"
    event_queue.append(click_at(*_back_point(ui)))
    ui.show_summon(state, EQUIPMENT)
    assert state.gems == 1000 - CHARACTER_SUMMON_COST_X10
    # 10 pulls landed -- some may have been duplicates (shards, no new slot),
    # so just confirm the roster grew by at most 10 and gems/roster both moved.
    assert starting_roster < len(state.characters) <= starting_roster + SUMMON_X10_COUNT
    print("test_x10_character_pull_reveals_a_grid_flipping_one_card_leaves_the_rest_face_down: PASS")


def test_x10_equipment_pull_adds_ten_items_to_the_stash():
    ui, state, hero = _fresh(gems=1000)
    event_queue.clear()
    event_queue.append(click_at(*_banner_tile_point(1)))
    event_queue.append(click_at(*_pull_button_point(ui, x10=True)))
    event_queue.append(click_at(*_reveal_all_or_continue_point(ui)))   # Reveal All
    event_queue.append(click_at(*_reveal_all_or_continue_point(ui)))   # Continue
    event_queue.append(click_at(*_back_point(ui)))
    ui.show_summon(state, EQUIPMENT)
    assert state.gems == 1000 - EQUIPMENT_SUMMON_COST_X10
    assert sum(state.owned_equipment.values()) == SUMMON_X10_COUNT
    print("test_x10_equipment_pull_adds_ten_items_to_the_stash: PASS")


def test_unaffordable_pull_buttons_are_not_clickable():
    # Enough for a x1 character pull but not a x10 pull or anything equipment.
    ui, state, hero = _fresh(gems=CHARACTER_SUMMON_COST)
    starting_roster = len(state.characters)
    event_queue.clear()
    event_queue.append(click_at(*_pull_button_point(ui, x10=True)))   # too expensive -- should be a no-op
    event_queue.append(click_at(*_back_point(ui)))
    ui.show_summon(state, EQUIPMENT)
    assert state.gems == CHARACTER_SUMMON_COST, "an unaffordable x10 pull must not spend gems"
    assert len(state.characters) == starting_roster
    print("test_unaffordable_pull_buttons_are_not_clickable: PASS")


def test_back_to_colosseum_is_unavailable_mid_reveal():
    """Back to Colosseum only renders on the select screen -- clicking where
    it would be while a reveal is up must be a harmless no-op, not an early
    return that skips flipping/continuing."""
    ui, state, hero = _fresh(gems=100)
    starting_roster = len(state.characters)
    event_queue.clear()
    event_queue.append(click_at(*_pull_button_point(ui, x10=False)))
    event_queue.append(click_at(*_back_point(ui)))                     # ignored -- no Back button during reveal
    event_queue.append(click_at(*_reveal_all_or_continue_point(ui)))   # Reveal All / flip the solo card
    event_queue.append(click_at(*_reveal_all_or_continue_point(ui)))   # Continue
    event_queue.append(click_at(*_back_point(ui)))                     # the real Back, now that we're back at select
    ui.show_summon(state, EQUIPMENT)
    assert state.gems == 100 - CHARACTER_SUMMON_COST, "exactly one pull should have happened, not zero or two"
    assert len(state.characters) == starting_roster + 1
    print("test_back_to_colosseum_is_unavailable_mid_reveal: PASS")


def test_summon_character_button_grants_shards_instead_of_a_new_slot_once_everyone_is_owned():
    """As of the hero-rarity pass, a character summon that matches a hero
    you already own is a duplicate (hero shards), not a dead end -- with
    every recruitable hero already on the roster, every possible pull is
    guaranteed to be a duplicate, so this proves the Summon screen handles
    that path (via game/summon.py) without crashing or padding the roster."""
    ui, state, hero = _fresh(gems=100)
    for h in RECRUITABLE_ROSTER:
        state.characters.append(PlayerCharacter(name=h.name, class_id=h.class_id, rarity=h.rarity))
    roster_size = len(state.characters)

    event_queue.clear()
    event_queue.append(click_at(*_pull_button_point(ui, x10=False)))
    event_queue.append(click_at(*_reveal_all_or_continue_point(ui)))
    event_queue.append(click_at(*_reveal_all_or_continue_point(ui)))
    event_queue.append(click_at(*_back_point(ui)))
    ui.show_summon(state, EQUIPMENT)
    assert state.gems == 100 - CHARACTER_SUMMON_COST, "gems should still be spent on a duplicate pull"
    assert len(state.characters) == roster_size, "a duplicate pull must not add a new roster entry"
    assert sum(c.shards for c in state.characters) > 0, "a duplicate pull must grant shards to someone"
    print("test_summon_character_button_grants_shards_instead_of_a_new_slot_once_everyone_is_owned: PASS")


def test_back_button_returns_without_side_effects():
    ui, state, hero = _fresh(gems=200)
    event_queue.clear()
    event_queue.append(click_at(*_back_point(ui)))    # immediately back out
    ui.show_summon(state, EQUIPMENT)
    assert state.gems == 200
    assert len(state.characters) == 1
    assert state.owned_equipment == {}
    print("test_back_button_returns_without_side_effects: PASS")


def main():
    test_pulling_x1_character_reveals_a_card_and_recruits_on_continue()
    test_pulling_x1_equipment_reveals_a_card_and_adds_to_stash()
    test_x10_character_pull_reveals_a_grid_flipping_one_card_leaves_the_rest_face_down()
    test_x10_equipment_pull_adds_ten_items_to_the_stash()
    test_unaffordable_pull_buttons_are_not_clickable()
    test_back_to_colosseum_is_unavailable_mid_reveal()
    test_summon_character_button_grants_shards_instead_of_a_new_slot_once_everyone_is_owned()
    test_back_button_returns_without_side_effects()
    print("\nALL SUMMON SCREEN TESTS PASSED")


if __name__ == "__main__":
    main()

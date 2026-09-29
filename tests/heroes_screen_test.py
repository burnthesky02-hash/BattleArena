"""Exercises ui/pygame_ui.py's Heroes screen -- a Mobile-Legends-Adventure-
style scrollable hero-card grid (portrait art from data/portraits/ when
present, a drawn placeholder otherwise -- see _get_portrait/
_draw_portrait_placeholder), a detail panel, star upgrade, and gear
equip/unequip (the new home for equipping as of the hero-rarity pass,
replacing Shop's old "Gear" tab) -- against the fake pygame module, the same
approach as tests/shop_screen_test.py.

Card/grid coordinates below are derived from the same module-level
constants ui/pygame_ui.py's show_heroes uses (HERO_GRID_*, HERO_CARD_*,
HERO_DETAIL_X), imported directly rather than re-typed as magic numbers, so
a future layout tweak can't silently desync this file from the real one
(same convention tests/pygame_ui_smoke_test.py's `BY = HEIGHT - 62` already
established).

Run directly: python3 tests/heroes_screen_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.pygame_stub import make_pygame_stub, Event

event_queue = []
sys.modules["pygame"] = make_pygame_stub(event_queue)

from data.equipment_db import EQUIPMENT  # noqa: E402
from data.hero_rarity import shard_cost_for_next_star  # noqa: E402
from data.items_db import ITEMS  # noqa: E402
from data.skills_db import SKILLS  # noqa: E402
from game.player_state import PlayerState  # noqa: E402
from game.roster import PlayerCharacter  # noqa: E402
from ui import pygame_ui  # noqa: E402
from ui.pygame_ui import (  # noqa: E402
    HERO_CARD_GAP, HERO_CARD_H, HERO_CARD_W, HERO_DETAIL_X, HERO_GRID_COLS, HERO_GRID_LEFT, HERO_GRID_TOP,
    PygameUI,
)

MOUSEBUTTONDOWN = 3
MOUSEWHEEL = 4

ROW_STRIDE = HERO_CARD_H + HERO_CARD_GAP
COL_STRIDE = HERO_CARD_W + HERO_CARD_GAP


def click_at(x, y) -> Event:
    return Event(MOUSEBUTTONDOWN, type=MOUSEBUTTONDOWN, button=1, pos=(x, y))


def wheel(y) -> Event:
    """y follows real pygame's convention: positive = scrolled up/away from
    the player, negative = scrolled down/toward the player."""
    return Event(MOUSEWHEEL, type=MOUSEWHEEL, y=y)


def _fresh(rarity="common", stars=1, shards=0):
    ui = PygameUI(SKILLS, ITEMS)
    hero = PlayerCharacter(name="Ari", class_id="tank", rarity=rarity, stars=stars, shards=shards)
    state = PlayerState.new_game(hero)
    return ui, state, hero


def _card_click_point(index_on_screen: int):
    """Center-ish point of the `index_on_screen`-th visible card (0 = first
    row/first column of whatever's currently displayed -- i.e. after
    whatever scrolling has already happened), following show_heroes' own
    row-major grid layout."""
    row, col = divmod(index_on_screen, HERO_GRID_COLS)
    x = HERO_GRID_LEFT + col * COL_STRIDE + HERO_CARD_W // 2
    y = HERO_GRID_TOP + row * ROW_STRIDE + HERO_CARD_H // 2
    return x, y


def _upgrade_button_point():
    """The "Upgrade Star" button sits at a fixed y regardless of which hero
    is selected (the detail panel above it -- name/subtitle/star line/4
    stat lines -- is always the same height), so one constant point works
    for every non-maxed hero."""
    return HERO_DETAIL_X + 150, 256


def _stash_row_point():
    return HERO_DETAIL_X + 50, 321


def _weapon_slot_point():
    return HERO_DETAIL_X + 50, 387


def test_first_hero_is_selected_by_default_and_back_button_exits_cleanly():
    ui, state, hero = _fresh()
    event_queue.clear()
    event_queue.append(click_at(30, ui.height - 40))  # Back to Colosseum, no other clicks
    ui.show_heroes(state, EQUIPMENT)  # must not raise -- the detail panel renders for the default selection
    print("test_first_hero_is_selected_by_default_and_back_button_exits_cleanly: PASS")


def test_selecting_a_second_hero_switches_the_detail_panel():
    ui, state, hero = _fresh()
    mage = PlayerCharacter(name="Zel", class_id="mage")
    state.characters.append(mage)

    event_queue.clear()
    event_queue.append(click_at(*_card_click_point(1)))  # select the 2nd hero card (Zel)
    event_queue.append(click_at(*_upgrade_button_point()))  # upgrade Zel's star (common, cost 2)
    event_queue.append(click_at(30, ui.height - 40))
    mage.shards = 10
    ui.show_heroes(state, EQUIPMENT)
    assert mage.stars == 2, "the upgrade click should have applied to the selected 2nd hero, not the first"
    assert hero.stars == 1, "the non-selected hero must be untouched"
    print("test_selecting_a_second_hero_switches_the_detail_panel: PASS")


def test_upgrade_star_button_spends_shards_and_increments_stars():
    cost = shard_cost_for_next_star("common", 1)
    ui, state, hero = _fresh(rarity="common", stars=1, shards=cost)
    event_queue.clear()
    event_queue.append(click_at(*_upgrade_button_point()))
    event_queue.append(click_at(30, ui.height - 40))
    ui.show_heroes(state, EQUIPMENT)
    assert hero.stars == 2
    assert hero.shards == 0
    print(f"test_upgrade_star_button_spends_shards_and_increments_stars: PASS (cost={cost})")


def test_upgrade_star_button_does_nothing_when_shards_are_insufficient():
    ui, state, hero = _fresh(rarity="mythic", stars=1, shards=0)  # mythic star 2 costs > 0
    event_queue.clear()
    # The button is drawn but not registered as clickable when unaffordable
    # (same convention as Shop's unaffordable rows) -- this click should
    # simply hit nothing.
    event_queue.append(click_at(*_upgrade_button_point()))
    event_queue.append(click_at(30, ui.height - 40))
    ui.show_heroes(state, EQUIPMENT)
    assert hero.stars == 1 and hero.shards == 0
    print("test_upgrade_star_button_does_nothing_when_shards_are_insufficient: PASS")


def test_equip_and_unequip_round_trip():
    ui, state, hero = _fresh()
    state.owned_equipment["rusty_sword"] = 1  # pre-seed the stash, skip the Shop buy step

    event_queue.clear()
    event_queue.append(click_at(*_stash_row_point()))  # the one stashed item (rusty_sword) -> equip
    event_queue.append(click_at(30, ui.height - 40))
    ui.show_heroes(state, EQUIPMENT)
    assert hero.equipped["weapon"] == "rusty_sword"
    assert "rusty_sword" not in state.owned_equipment

    event_queue.clear()
    event_queue.append(click_at(*_weapon_slot_point()))  # the now-populated "Weapon" slot row -> unequip
    event_queue.append(click_at(30, ui.height - 40))
    ui.show_heroes(state, EQUIPMENT)
    assert hero.equipped["weapon"] is None
    assert state.owned_equipment.get("rusty_sword") == 1
    print("test_equip_and_unequip_round_trip: PASS")


def test_empty_roster_does_not_crash():
    ui = PygameUI(SKILLS, ITEMS)
    state = PlayerState()  # no characters at all
    event_queue.clear()
    event_queue.append(click_at(30, ui.height - 40))
    ui.show_heroes(state, EQUIPMENT)  # must not raise
    print("test_empty_roster_does_not_crash: PASS")


def test_mouse_wheel_scrolls_the_hero_grid_to_reveal_and_select_later_heroes():
    """A 20-hero roster (Ari + 19 more), at 4 cards/row, spans more grid rows
    than fit on screen at once -- confirms scrolling both happens (the row
    offset moves) and actually works (a hero only reachable after scrolling
    is the one a click at the first card slot now selects)."""
    ui, state, hero = _fresh()
    for i in range(1, 20):
        state.characters.append(PlayerCharacter(name=f"H{i}", class_id="mage"))

    grid_bottom = ui.height - 70
    visible_rows = max(1, (grid_bottom - HERO_GRID_TOP) // ROW_STRIDE)
    total_rows = -(-len(state.characters) // HERO_GRID_COLS)  # ceil division
    assert visible_rows < total_rows, (
        "test setup needs more grid rows than fit on screen at once for scrolling to matter")

    scroll_down_events = total_rows - visible_rows  # scroll all the way to the bottom row
    target_index = scroll_down_events * HERO_GRID_COLS  # who ends up at the first card slot after scrolling
    target = state.characters[target_index]

    event_queue.clear()
    for _ in range(scroll_down_events):
        event_queue.append(wheel(-1))  # scroll down, one grid row at a time
    event_queue.append(click_at(*_card_click_point(0)))  # first card slot, post-scroll
    event_queue.append(click_at(*_upgrade_button_point()))  # upgrade the now-selected hero's star
    event_queue.append(click_at(30, ui.height - 40))
    target.shards = 10
    ui.show_heroes(state, EQUIPMENT)
    assert target.stars == 2, f"expected the post-scroll first-card hero ({target.name}) to have been selected"
    assert hero.stars == 1, "scrolling/selecting shouldn't touch anyone else"
    print(f"test_mouse_wheel_scrolls_the_hero_grid_to_reveal_and_select_later_heroes: PASS "
          f"(visible_rows={visible_rows}, scrolled {scroll_down_events} rows to reach {target.name})")


def test_get_portrait_returns_none_without_a_file_and_a_cached_scaled_surface_with_one():
    """_get_portrait is what lets show_heroes draw real art the moment
    Andrew drops a matching file into data/portraits/ with zero code
    changes -- covers both halves: no file -> None (caller falls back to
    _draw_portrait_placeholder), a file present -> a Surface scaled to the
    requested size, cached so a second call doesn't reload it."""
    ui = PygameUI(SKILLS, ITEMS)
    assert ui._get_portrait("Definitely Not A Real Hero Name", (64, 64)) is None

    os.makedirs(pygame_ui.PORTRAIT_DIR, exist_ok=True)
    portrait_path = os.path.join(pygame_ui.PORTRAIT_DIR, "__test_portrait__.png")
    with open(portrait_path, "wb") as f:
        f.write(b"not a real png -- the fake pygame.image.load never actually decodes it")
    try:
        portrait = ui._get_portrait("__test_portrait__", (64, 96))
        assert portrait is not None
        assert portrait.get_width() == 64 and portrait.get_height() == 96
        assert ui._get_portrait("__test_portrait__", (64, 96)) is portrait, "must be cached, not reloaded"
    finally:
        os.remove(portrait_path)
    print("test_get_portrait_returns_none_without_a_file_and_a_cached_scaled_surface_with_one: PASS")


def main():
    test_first_hero_is_selected_by_default_and_back_button_exits_cleanly()
    test_selecting_a_second_hero_switches_the_detail_panel()
    test_upgrade_star_button_spends_shards_and_increments_stars()
    test_upgrade_star_button_does_nothing_when_shards_are_insufficient()
    test_equip_and_unequip_round_trip()
    test_empty_roster_does_not_crash()
    test_mouse_wheel_scrolls_the_hero_grid_to_reveal_and_select_later_heroes()
    test_get_portrait_returns_none_without_a_file_and_a_cached_scaled_surface_with_one()
    print("\nALL HEROES SCREEN TESTS PASSED")


if __name__ == "__main__":
    main()

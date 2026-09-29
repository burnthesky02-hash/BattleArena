"""Exercises ui/pygame_ui.py's Party Select screen -- as of fix #20, a
Heroes-page-style card layout rather than a plain toggle-list: a fixed top
strip of PARTY_SELECT_SLOT_* cards shows the current battle party (an
empty "+" slot for each open spot), and a scrollable HERO_GRID_*/HERO_CARD_*
grid below it -- the same card geometry show_heroes uses for its own grid --
shows every owned hero, bordered when they're in the party. Clicking a
hero's portrait, in the top strip or in the roster grid below, toggles them
in/out of the party (game/party.py's toggle_member).

Card/grid coordinates below are derived from the same module-level
constants ui/pygame_ui.py's show_party_select uses (PARTY_SELECT_*,
HERO_GRID_*, HERO_CARD_*), imported directly rather than re-typed as magic
numbers, so a future layout tweak can't silently desync this file from the
real one (same convention tests/heroes_screen_test.py's `_card_click_point`
already established).

Run directly: python3 tests/party_select_screen_test.py
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
from game import party as party_logic  # noqa: E402
from game.player_state import PlayerState  # noqa: E402
from game.roster import PlayerCharacter  # noqa: E402
from ui.pygame_ui import (  # noqa: E402
    HERO_CARD_GAP, HERO_CARD_H, HERO_CARD_W, HERO_GRID_COLS, HERO_GRID_LEFT,
    PARTY_SELECT_ROSTER_GRID_TOP, PARTY_SELECT_SLOT_GAP, PARTY_SELECT_SLOT_H, PARTY_SELECT_SLOT_TOP,
    PARTY_SELECT_SLOT_W, PygameUI,
)

MOUSEBUTTONDOWN = 3


def click_at(x, y) -> Event:
    return Event(MOUSEBUTTONDOWN, type=MOUSEBUTTONDOWN, button=1, pos=(x, y))


def _party_slot_point(i: int):
    """Center of the i-th top-strip slot (0-indexed, left to right)."""
    x = HERO_GRID_LEFT + i * (PARTY_SELECT_SLOT_W + PARTY_SELECT_SLOT_GAP) + PARTY_SELECT_SLOT_W // 2
    y = PARTY_SELECT_SLOT_TOP + PARTY_SELECT_SLOT_H // 2
    return x, y


def _roster_card_point(index_on_screen: int):
    """Center of the index_on_screen-th visible roster-grid card (0 = first
    row/first column of whatever's currently displayed), following
    show_party_select's own row-major grid layout below the party strip."""
    row, col = divmod(index_on_screen, HERO_GRID_COLS)
    x = HERO_GRID_LEFT + col * (HERO_CARD_W + HERO_CARD_GAP) + HERO_CARD_W // 2
    y = PARTY_SELECT_ROSTER_GRID_TOP + row * (HERO_CARD_H + HERO_CARD_GAP) + HERO_CARD_H // 2
    return x, y


def _confirm_point(ui):
    return 40, ui.height - 40


def _back_point(ui):
    return 320, ui.height - 40


def _fresh(num_extra: int = 0):
    """A fresh PlayerState with Ari plus `num_extra` more mages appended
    (roster order: Ari, H0, H1, ...)."""
    ui = PygameUI(SKILLS, ITEMS)
    hero = PlayerCharacter(name="Ari", class_id="tank")
    state = PlayerState.new_game(hero)
    for i in range(num_extra):
        state.characters.append(PlayerCharacter(name=f"H{i}", class_id="mage"))
    return ui, state, hero


def test_confirm_returns_the_default_preselected_party():
    """With no prior active_party, show_party_select should start with the
    first MAX_PARTY_SIZE heroes pre-checked (game/party.py's
    default_party_ids) -- clicking Confirm immediately should return
    exactly that set, in roster order, and persist it to active_party."""
    ui, state, hero = _fresh(num_extra=5)  # 6 total, one more than MAX_PARTY_SIZE
    event_queue.clear()
    event_queue.append(click_at(*_confirm_point(ui)))
    party = ui.show_party_select(state, EQUIPMENT)
    assert party is not None
    assert [c.id for c in party] == [c.id for c in state.characters[:party_logic.MAX_PARTY_SIZE]]
    assert state.active_party == [c.id for c in party]
    print("test_confirm_returns_the_default_preselected_party: PASS")


def test_clicking_a_party_strip_slot_removes_that_hero():
    """Clicking an already-selected hero's card in the top "Your Party"
    strip should remove them -- confirming afterward should reflect that
    deselection."""
    ui, state, hero = _fresh(num_extra=1)
    second = state.characters[1]

    event_queue.clear()
    event_queue.append(click_at(*_party_slot_point(0)))  # Ari is slot 0 by default -- remove her
    event_queue.append(click_at(*_confirm_point(ui)))
    party = ui.show_party_select(state, EQUIPMENT)
    assert [c.id for c in party] == [second.id]
    print("test_clicking_a_party_strip_slot_removes_that_hero: PASS")


def test_clicking_an_unselected_roster_card_adds_that_hero():
    """Clicking a hero's card in the "All Heroes" grid below the strip --
    not yet in the party -- should add them, as long as there's room.
    active_party is set explicitly to just Ari (below MAX_PARTY_SIZE) so the
    default preselection doesn't already fill every slot -- with 4+ total
    heroes and no explicit active_party, default_party_ids always fills to
    the cap immediately (see test_cannot_select_a_5th_hero), so this needs
    a party that starts under-full to actually exercise "adding" rather
    than "the cap rejecting a 5th."."""
    ui, state, hero = _fresh(num_extra=2)  # Ari, H0, H1
    state.active_party = [hero.id]  # only Ari pre-selected -- room for 3 more
    h0 = state.characters[1]

    event_queue.clear()
    event_queue.append(click_at(*_roster_card_point(1)))  # H0's card in the roster grid (row 0, col 1)
    event_queue.append(click_at(*_confirm_point(ui)))
    party = ui.show_party_select(state, EQUIPMENT)
    assert h0.id in [c.id for c in party]
    assert len(party) == 2
    print("test_clicking_an_unselected_roster_card_adds_that_hero: PASS")


def test_clicking_a_selected_heros_roster_card_also_removes_them():
    """The roster grid shows every owned hero, selected ones bordered --
    clicking a *selected* hero's card there (not just their top-strip slot)
    should remove them too, same underlying toggle."""
    ui, state, hero = _fresh(num_extra=1)
    second = state.characters[1]

    event_queue.clear()
    event_queue.append(click_at(*_roster_card_point(0)))  # Ari's card in the roster grid (she's selected)
    event_queue.append(click_at(*_confirm_point(ui)))
    party = ui.show_party_select(state, EQUIPMENT)
    assert [c.id for c in party] == [second.id]
    print("test_clicking_a_selected_heros_roster_card_also_removes_them: PASS")


def test_back_returns_none_without_changing_active_party():
    ui, state, hero = _fresh()
    state.active_party = ["some-previous-value"]

    event_queue.clear()
    event_queue.append(click_at(*_back_point(ui)))
    party = ui.show_party_select(state, EQUIPMENT)
    assert party is None
    assert state.active_party == ["some-previous-value"], "backing out must not touch active_party"
    print("test_back_returns_none_without_changing_active_party: PASS")


def test_cannot_select_a_5th_hero():
    """Clicking a 5th (unselected) hero's roster card on top of a full
    4-hero default selection should be a no-op (see game/party.py's
    toggle_member) -- confirming right after should still return exactly
    the original 4."""
    ui, state, hero = _fresh(num_extra=4)  # 5 total, one more than MAX_PARTY_SIZE

    event_queue.clear()
    event_queue.append(click_at(*_roster_card_point(4)))  # try to add the unselected 5th hero
    event_queue.append(click_at(*_confirm_point(ui)))
    party = ui.show_party_select(state, EQUIPMENT)
    assert [c.id for c in party] == [c.id for c in state.characters[:4]]
    print("test_cannot_select_a_5th_hero: PASS")


def test_empty_slots_render_and_empty_roster_does_not_crash():
    """A single-hero roster leaves 3 empty "+" slots in the top strip, and
    an entirely empty roster (defensive -- new_game always seeds one
    character today, but nothing should assume that forever) must not
    crash the screen either."""
    ui, state, hero = _fresh()  # just Ari -- 3 empty slots
    event_queue.clear()
    event_queue.append(click_at(*_confirm_point(ui)))
    party = ui.show_party_select(state, EQUIPMENT)
    assert [c.id for c in party] == [hero.id]

    state.characters = []
    event_queue.clear()
    event_queue.append(click_at(*_back_point(ui)))
    party = ui.show_party_select(state, EQUIPMENT)  # must not raise
    assert party is None
    print("test_empty_slots_render_and_empty_roster_does_not_crash: PASS")


def main():
    test_confirm_returns_the_default_preselected_party()
    test_clicking_a_party_strip_slot_removes_that_hero()
    test_clicking_an_unselected_roster_card_adds_that_hero()
    test_clicking_a_selected_heros_roster_card_also_removes_them()
    test_back_returns_none_without_changing_active_party()
    test_cannot_select_a_5th_hero()
    test_empty_slots_render_and_empty_roster_does_not_crash()
    print("\nALL PARTY SELECT SCREEN TESTS PASSED")


if __name__ == "__main__":
    main()

"""Exercises the new meta-game screens in ui/pygame_ui.py (title screen,
character creation, the Colosseum hub) against the fake pygame module,
the same way tests/pygame_ui_smoke_test.py covers the battle-menu screens.
These are plain menu screens over PlayerState/class-archetype data, not
BattleEngine state, so they're covered separately here rather than folded
into that file.

Run directly: python3 tests/meta_screens_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.pygame_stub import make_pygame_stub, Event

event_queue = []
sys.modules["pygame"] = make_pygame_stub(event_queue)

from data.classes import CLASS_ARCHETYPES, CLASS_IDS  # noqa: E402
from data.equipment_db import EQUIPMENT  # noqa: E402
from data.items_db import ITEMS  # noqa: E402
from data.skills_db import SKILLS  # noqa: E402
from game.player_state import PlayerState  # noqa: E402
from game.roster import PlayerCharacter  # noqa: E402
from ui.pygame_ui import PygameUI  # noqa: E402

KEYDOWN, MOUSEBUTTONDOWN = 2, 3


def click_at(x, y) -> Event:
    return Event(MOUSEBUTTONDOWN, type=MOUSEBUTTONDOWN, button=1, pos=(x, y))


def type_char(ch: str) -> Event:
    return Event(KEYDOWN, type=KEYDOWN, key=999, unicode=ch)  # 999: not any of the special keys checked


def key(code: int) -> Event:
    return Event(KEYDOWN, type=KEYDOWN, key=code)


def test_title_screen_new_game_and_continue_options():
    ui = PygameUI(SKILLS, ITEMS)
    # No save yet: only "New Game" (y=260) and "Quit" (y=318) should exist --
    # clicking where "Quit" would be if there *were* a save (the 3rd-row slot,
    # y=376) lands on nothing here and must not register as a click.
    event_queue.clear()
    event_queue.append(click_at(ui.content_width // 2, 376))  # empty when has_save=False
    event_queue.append(click_at(ui.content_width // 2, 260))  # "New Game"
    choice = ui.show_title_screen(has_save=False)
    assert choice == "new_game", choice

    # With a save: "New Game" / "Continue" / "Quit" in that order.
    event_queue.clear()
    event_queue.append(click_at(ui.content_width // 2, 318))  # now really "Continue"
    choice = ui.show_title_screen(has_save=True)
    assert choice == "continue", choice
    print("test_title_screen_new_game_and_continue_options: PASS")


def test_title_screen_quit():
    ui = PygameUI(SKILLS, ITEMS)
    event_queue.clear()
    event_queue.append(click_at(ui.content_width // 2, 376))  # "Quit" (3rd button, has_save=True)
    choice = ui.show_title_screen(has_save=True)
    assert choice == "quit", choice
    print("test_title_screen_quit: PASS")


def test_character_creation_requires_both_name_and_class():
    ui = PygameUI(SKILLS, ITEMS)
    event_queue.clear()
    # Click "confirm" before typing anything or picking a class -- since
    # confirm_enabled is False, that rect isn't even in the clickable list,
    # so this click should be a no-op, not a premature return.
    event_queue.append(click_at(40, 452))
    # Type a name.
    for ch in "Ari":
        event_queue.append(type_char(ch))
    # Pick "tank" (first class button, y=122..176).
    event_queue.append(click_at(40, 130))
    # Now confirm for real.
    event_queue.append(click_at(40, 452))
    name, class_id = ui.show_character_creation(CLASS_ARCHETYPES, CLASS_IDS)
    assert name == "Ari", name
    assert class_id == "tank", class_id
    print("test_character_creation_requires_both_name_and_class: PASS")


def test_character_creation_backspace_and_class_reselection():
    ui = PygameUI(SKILLS, ITEMS)
    event_queue.clear()
    for ch in "Xyzz":
        event_queue.append(type_char(ch))
    event_queue.append(key(8))  # K_BACKSPACE -- "Xyzz" -> "Xyz"
    event_queue.append(click_at(40, 130))    # tank
    event_queue.append(click_at(40, 192))    # melee_dps (2nd button, y=184..238) -- should replace tank
    event_queue.append(key(13))              # K_RETURN confirms once name+class are both set
    name, class_id = ui.show_character_creation(CLASS_ARCHETYPES, CLASS_IDS)
    assert name == "Xyz", name
    assert class_id == "melee_dps", class_id
    print("test_character_creation_backspace_and_class_reselection: PASS")


def _hub_base_y(ui, num_options):
    btn_h, btn_gap = 44, 12
    return ui.height - (num_options * btn_h + (num_options - 1) * btn_gap) - 20


def test_colosseum_hub_returns_each_button_value():
    """As of the hero-rarity pass the hub has 5 non-debug buttons (Heroes is
    new, 4th) -- see _hub_base_y for the same dynamic layout formula
    ui/pygame_ui.py's show_colosseum_hub uses."""
    ui = PygameUI(SKILLS, ITEMS)
    hero = PlayerCharacter(name="Ari", class_id="tank")
    hero.equip("rusty_sword", EQUIPMENT)
    state = PlayerState.new_game(hero)

    base_y = _hub_base_y(ui, 5)
    expected = [("battle", 0), ("shop", 1), ("summon", 2), ("heroes", 3), ("quit_to_title", 4)]
    for value, row in expected:
        event_queue.clear()
        y = base_y + row * (44 + 12) + 10
        event_queue.append(click_at(40, y))
        choice = ui.show_colosseum_hub(state, EQUIPMENT)
        assert choice == value, (value, choice)
    print("test_colosseum_hub_returns_each_button_value: PASS")


def test_colosseum_hub_debug_gem_button_only_appears_in_debug_mode():
    """The "[DEBUG] Add N Gems" cheat button (for testing Summon without
    grinding real battles) should only ever be offered when the UI was
    constructed with debug=True, and shouldn't shift where the 5 regular
    buttons land when it's absent."""
    hero = PlayerCharacter(name="Ari", class_id="tank")
    state = PlayerState.new_game(hero)

    # Non-debug: 5 buttons (Battle/Shop/Summon/Heroes/Quit), no debug button.
    ui = PygameUI(SKILLS, ITEMS, debug=False)
    base_y = _hub_base_y(ui, 5)
    event_queue.clear()
    event_queue.append(click_at(40, base_y + 0 * (44 + 12) + 10))
    assert ui.show_colosseum_hub(state, EQUIPMENT) == "battle"
    # Clicking where a 6th button *would* be (if it existed) should hit nothing.
    event_queue.clear()
    event_queue.append(click_at(40, base_y + 5 * (44 + 12) + 10))
    event_queue.append(click_at(40, base_y + 4 * (44 + 12) + 10))  # then the real "quit_to_title"
    assert ui.show_colosseum_hub(state, EQUIPMENT) == "quit_to_title"

    # Debug mode: a 6th button appears and returns "debug_add_gems".
    debug_ui = PygameUI(SKILLS, ITEMS, debug=True)
    debug_base_y = _hub_base_y(debug_ui, 6)
    event_queue.clear()
    event_queue.append(click_at(40, debug_base_y + 5 * (44 + 12) + 10))
    assert debug_ui.show_colosseum_hub(state, EQUIPMENT) == "debug_add_gems"
    print("test_colosseum_hub_debug_gem_button_only_appears_in_debug_mode: PASS")


def test_battle_setup_difficulty_then_count_round_trip():
    """Click a difficulty, then a count -- show_battle_setup should return
    exactly that (difficulty, num_enemies) pair (see game/battle_setup.py).
    `party` (the fielded heroes, chosen on show_party_select beforehand) is
    only used for the average-level display here -- it doesn't affect
    layout/coordinates."""
    ui = PygameUI(SKILLS, ITEMS)
    hero = PlayerCharacter(name="Ari", class_id="tank")
    state = PlayerState.new_game(hero)

    # Difficulty buttons are a vertical column starting at (30, 140), 44 tall, 10 gap.
    # ("easy", "normal", "hard", "extreme") is DIFFICULTY_IDS' order.
    event_queue.clear()
    event_queue.append(click_at(40, 140 + 2 * (44 + 10) + 10))  # 3rd button: "hard"
    # Count buttons are a horizontal row starting at (30, 140), 80 wide, 10 gap.
    # MIN_OPPONENTS..MAX_OPPONENTS is (1, 2, 3, 4); index 2 -> num_enemies == 3.
    event_queue.append(click_at(30 + 2 * (80 + 10) + 10, 150))
    choice = ui.show_battle_setup(state, [hero])
    assert choice == ("hard", 3), choice
    print("test_battle_setup_difficulty_then_count_round_trip: PASS")


def test_battle_setup_back_from_count_returns_to_difficulty_not_the_hub():
    """Clicking "Back" on the opponent-count step should return to the
    difficulty step (re-pick), not immediately bail out of the whole
    screen -- only backing out at the difficulty step returns None."""
    ui = PygameUI(SKILLS, ITEMS)
    hero = PlayerCharacter(name="Ari", class_id="tank")
    state = PlayerState.new_game(hero)

    event_queue.clear()
    event_queue.append(click_at(40, 140 + 10))                    # difficulty: "easy" (1st button)
    event_queue.append(click_at(40, ui.height - 56 + 10))          # "Back" on the count step
    event_queue.append(click_at(40, 140 + 1 * (44 + 10) + 10))    # difficulty: "normal" (2nd button)
    event_queue.append(click_at(30 + 0 * (80 + 10) + 10, 150))    # count: 1st button -> num_enemies == 1
    choice = ui.show_battle_setup(state, [hero])
    assert choice == ("normal", 1), choice
    print("test_battle_setup_back_from_count_returns_to_difficulty_not_the_hub: PASS")


def test_battle_setup_back_from_difficulty_returns_none():
    ui = PygameUI(SKILLS, ITEMS)
    hero = PlayerCharacter(name="Ari", class_id="tank")
    state = PlayerState.new_game(hero)

    event_queue.clear()
    event_queue.append(click_at(40, ui.height - 56 + 10))  # "Back to Colosseum" on the difficulty step
    choice = ui.show_battle_setup(state, [hero])
    assert choice is None
    print("test_battle_setup_back_from_difficulty_returns_none: PASS")


def main():
    test_title_screen_new_game_and_continue_options()
    test_title_screen_quit()
    test_character_creation_requires_both_name_and_class()
    test_character_creation_backspace_and_class_reselection()
    test_colosseum_hub_returns_each_button_value()
    test_colosseum_hub_debug_gem_button_only_appears_in_debug_mode()
    test_battle_setup_difficulty_then_count_round_trip()
    test_battle_setup_back_from_count_returns_to_difficulty_not_the_hub()
    test_battle_setup_back_from_difficulty_returns_none()
    print("\nALL META-SCREEN TESTS PASSED")


if __name__ == "__main__":
    main()

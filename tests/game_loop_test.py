"""Integration coverage for main.py's new title -> character creation ->
Colosseum hub -> battle loop, split into two levels since scripting a full
real battle through PygameUI's click-driven UI runs into a real problem:
PygameUI._pump() (called on every single log line during a battle) drains
the fake pygame module's whole event queue, which would eat any clicks
queued up for screens *after* the battle (the end screen, the next hub
visit) before the battle even finishes. So:

  - test_run_one_battle_* drives main.run_one_battle() directly (real
    BattleEngine, real scripted-fallback enemy AI, a real PygameUI whose
    get_party_action is monkeypatched to always Defend so the battle runs
    to completion deterministically) and checks the reward/inventory
    wiring around a real battle.
  - test_run_game_loop_* drives main.run_game_loop() with a scripted fake
    UI double (not real PygameUI) and main.run_one_battle monkeypatched to
    a fast fake, to check the title/character-creation/hub *control flow*
    (new game vs. continue, save timing, hub dispatch) in isolation from
    both pygame and real battle mechanics.

Run directly: python3 tests/game_loop_test.py
"""
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.pygame_stub import make_pygame_stub, Event

event_queue = []
sys.modules["pygame"] = make_pygame_stub(event_queue)

import main  # noqa: E402
import config  # noqa: E402
from ai.ollama_client import OllamaClient  # noqa: E402
from data.items_db import ITEMS  # noqa: E402
from data.skills_db import SKILLS  # noqa: E402
from engine.actions import Action  # noqa: E402
from engine.types import BattleResult  # noqa: E402
from game import save_system  # noqa: E402
from game.player_state import PlayerState  # noqa: E402
from game.roster import PlayerCharacter  # noqa: E402
from ui.pygame_ui import PygameUI  # noqa: E402


def test_run_one_battle_applies_rewards_and_persists_inventory():
    ui = PygameUI(SKILLS, ITEMS)
    ui.get_party_action = lambda c, s: Action.defend(c.id)  # deterministic: never touches items/MP

    hero = PlayerCharacter(name="Solo", class_id="tank")
    player_state = PlayerState.new_game(hero)
    starting_money, starting_gems = player_state.money, player_state.gems
    starting_inventory = dict(player_state.inventory)

    client = OllamaClient(host="http://localhost:1", model="unreachable", timeout=0.5)
    # party=None -- the default -- falls back to the whole roster (just the
    # solo hero here), same as every call site before the party-select
    # screen existed; see main.run_one_battle's docstring.
    result, money, gems, xp, level_ups = main.run_one_battle(ui, player_state, client, "normal", 1)

    assert isinstance(result, BattleResult)
    assert money > 0, "money should be awarded regardless of outcome"
    if result == BattleResult.VICTORY:
        assert gems > 0
        assert xp > 0
    else:
        assert gems == 0
        assert xp == 0
    assert player_state.money == starting_money + money
    assert player_state.gems == starting_gems + gems
    # A fresh level-1 hero needs 40 XP to hit level 2 (data/leveling.py); a single
    # normal-difficulty 1v1 victory's XP range (20-30, see VICTORY_XP_RANGE) can't
    # reach that on its own, so no level-up is expected here either way.
    assert isinstance(level_ups, dict)
    # Nobody used an item (always defending), so inventory should come back unchanged.
    assert player_state.inventory == starting_inventory
    print(f"test_run_one_battle_applies_rewards_and_persists_inventory: PASS "
          f"(result={result.value}, +{money} money, +{gems} gems, +{xp} xp)")


class _FakeUI:
    """A scripted stand-in for PygameUI/TextUI's meta-screen interface, used
    to test run_game_loop's control flow without touching pygame, a real
    battle, or the filesystem. Each show_* pops its next scripted return
    value off a list so a test can lay out an exact sequence of screens."""

    def __init__(self, title_choices, hub_choices, battle_setup_choices=None, party_select_choices=None):
        self.title_choices = list(title_choices)
        self.hub_choices = list(hub_choices)
        # Defaults to always picking ("normal", 1) for every "battle" hub
        # choice -- pass an explicit list (one entry per "battle" choice,
        # None meaning "back out without fighting") to script otherwise.
        self.battle_setup_choices = list(battle_setup_choices) if battle_setup_choices is not None else None
        # Defaults to always fielding the whole roster for every "battle"
        # hub choice -- pass an explicit list (one entry per "battle"
        # choice, None/[] meaning "back out without fighting") to script
        # otherwise. See game/party.py -- this stands in for
        # show_party_select's real toggle/confirm screen.
        self.party_select_choices = list(party_select_choices) if party_select_choices is not None else None
        self.chargen_calls = 0
        self.end_screen_calls = []
        self.battle_setup_calls = 0
        self.party_select_calls = 0
        self.not_implemented_calls = []
        self.shop_calls = []
        self.summon_calls = []
        self.heroes_calls = []

    def show_title_screen(self, has_save):
        return self.title_choices.pop(0)

    def show_character_creation(self, class_archetypes, class_ids):
        self.chargen_calls += 1
        return "Hero", "melee_dps"

    def show_colosseum_hub(self, player_state, equipment_db):
        return self.hub_choices.pop(0)

    def show_party_select(self, player_state, equipment_db):
        self.party_select_calls += 1
        if self.party_select_choices is not None:
            return self.party_select_choices.pop(0)
        return list(player_state.characters)

    def show_battle_setup(self, player_state, party):
        self.battle_setup_calls += 1
        if self.battle_setup_choices is not None:
            return self.battle_setup_choices.pop(0)
        return "normal", 1

    def show_end_screen(self, result, money=None, gems=None, quit_on_close=False, xp=None, level_ups=None):
        self.end_screen_calls.append((result, money, gems, xp, level_ups))

    def show_not_implemented(self, title, message):
        self.not_implemented_calls.append(title)

    def show_shop(self, player_state, items_db, equipment_db):
        self.shop_calls.append(1)

    def show_summon(self, player_state, equipment_db):
        self.summon_calls.append(1)

    def show_heroes(self, player_state, equipment_db):
        self.heroes_calls.append(1)

    def attach_engine(self, engine):
        pass

    def reset_battle_view(self):
        pass


def _with_temp_save(test_fn):
    """Points game.save_system's default SAVE_PATH-based calls at a temp
    file for the duration of test_fn, then restores everything -- default
    arguments are bound at function-definition time, so this patches the
    save/load/exists functions themselves rather than the SAVE_PATH constant
    (reassigning the constant alone wouldn't affect already-defined defaults)."""
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, "save1.json")
    orig_save_game, orig_save_exists, orig_load_game = (
        save_system.save_game, save_system.save_exists, save_system.load_game)
    save_system.save_game = lambda state, path=tmp_path: orig_save_game(state, path)
    save_system.save_exists = lambda path=tmp_path: orig_save_exists(path)
    save_system.load_game = lambda path=tmp_path: orig_load_game(path)
    try:
        test_fn(tmp_path)
    finally:
        save_system.save_game, save_system.save_exists, save_system.load_game = (
            orig_save_game, orig_save_exists, orig_load_game)
        shutil.rmtree(tmp_dir)


def test_new_game_creates_and_saves_then_battle_then_quit(tmp_path=None):
    def run(tmp_path):
        orig_run_one_battle = main.run_one_battle
        battle_calls = []

        def fake_run_one_battle(ui, player_state, client, difficulty, num_enemies, party=None):
            battle_calls.append((difficulty, num_enemies))
            player_state.add_rewards(40, 5)
            return BattleResult.VICTORY, 40, 5, 0, {}

        main.run_one_battle = fake_run_one_battle
        try:
            assert not save_system.save_exists()
            ui = _FakeUI(title_choices=["new_game", "quit"], hub_choices=["battle", "quit_to_title"])
            main.run_game_loop(ui, client=None)

            assert ui.chargen_calls == 1, "new_game should trigger character creation exactly once"
            assert ui.battle_setup_calls == 1, "the 'battle' hub choice should show the battle setup screen first"
            assert len(battle_calls) == 1, "the 'battle' hub choice should run exactly one battle"
            assert battle_calls == [("normal", 1)], "the setup screen's choice should be passed through to run_one_battle"
            assert ui.end_screen_calls == [(BattleResult.VICTORY, 40, 5, 0, {})]
            assert save_system.save_exists(), "a save should exist after creating a character"

            saved = save_system.load_game()
            assert saved.characters[0].name == "Hero"
            assert saved.characters[0].class_id == "melee_dps"
            assert saved.money == 100 + 40, "the reward from the battle should be persisted"
            assert saved.gems == 20 + 5
        finally:
            main.run_one_battle = orig_run_one_battle

    _with_temp_save(run)
    print("test_new_game_creates_and_saves_then_battle_then_quit: PASS")


def test_continue_loads_existing_save_without_recreating_a_character():
    def run(tmp_path):
        hero = PlayerCharacter(name="Returning", class_id="support")
        existing = PlayerState.new_game(hero)
        existing.money = 999
        save_system.save_game(existing)

        ui = _FakeUI(title_choices=["continue", "quit"], hub_choices=["quit_to_title"])
        main.run_game_loop(ui, client=None)

        assert ui.chargen_calls == 0, "continuing an existing save must not create a new character"
        reloaded = save_system.load_game()
        assert reloaded.characters[0].name == "Returning"
        assert reloaded.money == 999

    _with_temp_save(run)
    print("test_continue_loads_existing_save_without_recreating_a_character: PASS")


def test_battle_setup_back_out_skips_battle():
    """Backing out of the difficulty/opponent-count picker (show_battle_setup
    returning None) should return straight to the hub without running a
    battle at all -- game/battle_setup.py's screen is a real gate, not just
    a cosmetic step before an unavoidable fight."""
    def run(tmp_path):
        orig_run_one_battle = main.run_one_battle
        main.run_one_battle = lambda *a, **k: (_ for _ in ()).throw(AssertionError("battle should not run"))
        try:
            ui = _FakeUI(title_choices=["new_game", "quit"], hub_choices=["battle", "quit_to_title"],
                         battle_setup_choices=[None])
            main.run_game_loop(ui, client=None)
            assert ui.battle_setup_calls == 1
            assert ui.end_screen_calls == [], "no end screen should show when the player backs out"
        finally:
            main.run_one_battle = orig_run_one_battle

    _with_temp_save(run)
    print("test_battle_setup_back_out_skips_battle: PASS")


def test_party_select_back_out_skips_battle_and_battle_setup():
    """Backing out of the party-select screen (show_party_select returning
    None/empty) should return straight to the hub without ever showing
    show_battle_setup or running a battle -- the same "real gate" contract
    test_battle_setup_back_out_skips_battle covers for the step after it."""
    def run(tmp_path):
        orig_run_one_battle = main.run_one_battle
        main.run_one_battle = lambda *a, **k: (_ for _ in ()).throw(AssertionError("battle should not run"))
        try:
            ui = _FakeUI(title_choices=["new_game", "quit"], hub_choices=["battle", "quit_to_title"],
                         party_select_choices=[None])
            main.run_game_loop(ui, client=None)
            assert ui.party_select_calls == 1
            assert ui.battle_setup_calls == 0, "backing out of party select must not even show battle setup"
            assert ui.end_screen_calls == []
        finally:
            main.run_one_battle = orig_run_one_battle

    _with_temp_save(run)
    print("test_party_select_back_out_skips_battle_and_battle_setup: PASS")


def test_only_the_selected_party_fights_and_earns_xp():
    """End-to-end (real run_one_battle, real BattleEngine) check that
    game/party.py's selection actually limits who's built into the battle
    and who gets XP afterward -- a bystander left off the selected party
    must come back completely untouched."""
    ui = PygameUI(SKILLS, ITEMS)
    ui.get_party_action = lambda c, s: Action.defend(c.id)

    fighter = PlayerCharacter(name="Fighter", class_id="tank")
    bystander = PlayerCharacter(name="Bystander", class_id="mage")
    player_state = PlayerState.new_game(fighter)
    player_state.characters.append(bystander)
    bystander_xp, bystander_level = bystander.xp, bystander.level

    client = OllamaClient(host="http://localhost:1", model="unreachable", timeout=0.5)
    result, money, gems, xp, level_ups = main.run_one_battle(
        ui, player_state, client, "normal", 1, [fighter])

    assert bystander.name not in level_ups
    assert bystander.xp == bystander_xp and bystander.level == bystander_level, (
        "a character left out of the selected party must not fight or earn XP")
    print("test_only_the_selected_party_fights_and_earns_xp: PASS")


def test_debug_add_gems_hub_choice_grants_gems_and_saves():
    """The debug-only "Add Gems" hub button (see config.DEBUG_GEM_GRANT,
    ui/pygame_ui.py's/ui/text_ui.py's show_colosseum_hub) should just grant
    gems and save -- no battle, no other side effects."""
    def run(tmp_path):
        orig_run_one_battle = main.run_one_battle
        main.run_one_battle = lambda *a, **k: (_ for _ in ()).throw(AssertionError("battle should not run"))
        try:
            ui = _FakeUI(title_choices=["new_game", "quit"],
                         hub_choices=["debug_add_gems", "quit_to_title"])
            starting_gems = 20  # PlayerState.new_game's STARTING_GEMS
            main.run_game_loop(ui, client=None)
            saved = save_system.load_game()
            assert saved.gems == starting_gems + config.DEBUG_GEM_GRANT, (saved.gems, config.DEBUG_GEM_GRANT)
        finally:
            main.run_one_battle = orig_run_one_battle

    _with_temp_save(run)
    print("test_debug_add_gems_hub_choice_grants_gems_and_saves: PASS")


def test_shop_hub_choice_calls_show_shop_and_saves():
    def run(tmp_path):
        orig_run_one_battle = main.run_one_battle
        main.run_one_battle = lambda *a, **k: (_ for _ in ()).throw(AssertionError("battle should not run"))
        try:
            ui = _FakeUI(title_choices=["new_game", "quit"],
                         hub_choices=["shop", "quit_to_title"])
            main.run_game_loop(ui, client=None)
            assert ui.shop_calls == [1], "the 'shop' hub choice should call the real show_shop, not a placeholder"
            assert save_system.save_exists(), "leaving the shop should save (equip/buy changes must persist)"
        finally:
            main.run_one_battle = orig_run_one_battle

    _with_temp_save(run)
    print("test_shop_hub_choice_calls_show_shop_and_saves: PASS")


def test_summon_hub_choice_calls_show_summon_and_saves():
    def run(tmp_path):
        orig_run_one_battle = main.run_one_battle
        main.run_one_battle = lambda *a, **k: (_ for _ in ()).throw(AssertionError("battle should not run"))
        try:
            ui = _FakeUI(title_choices=["new_game", "quit"],
                         hub_choices=["summon", "quit_to_title"])
            main.run_game_loop(ui, client=None)
            assert ui.summon_calls == [1], "the 'summon' hub choice should call the real show_summon, not a placeholder"
            assert ui.not_implemented_calls == [], "nothing on the hub should still be a placeholder"
            assert save_system.save_exists(), "leaving Summon should save (a new recruit/gear must persist)"
        finally:
            main.run_one_battle = orig_run_one_battle

    _with_temp_save(run)
    print("test_summon_hub_choice_calls_show_summon_and_saves: PASS")


def test_heroes_hub_choice_calls_show_heroes_and_saves():
    def run(tmp_path):
        orig_run_one_battle = main.run_one_battle
        main.run_one_battle = lambda *a, **k: (_ for _ in ()).throw(AssertionError("battle should not run"))
        try:
            ui = _FakeUI(title_choices=["new_game", "quit"],
                         hub_choices=["heroes", "quit_to_title"])
            main.run_game_loop(ui, client=None)
            assert ui.heroes_calls == [1], "the 'heroes' hub choice should call the real show_heroes"
            assert save_system.save_exists(), "leaving Heroes should save (an equip/upgrade must persist)"
        finally:
            main.run_one_battle = orig_run_one_battle

    _with_temp_save(run)
    print("test_heroes_hub_choice_calls_show_heroes_and_saves: PASS")


def main_test():
    test_run_one_battle_applies_rewards_and_persists_inventory()
    test_only_the_selected_party_fights_and_earns_xp()
    test_new_game_creates_and_saves_then_battle_then_quit()
    test_continue_loads_existing_save_without_recreating_a_character()
    test_party_select_back_out_skips_battle_and_battle_setup()
    test_battle_setup_back_out_skips_battle()
    test_debug_add_gems_hub_choice_grants_gems_and_saves()
    test_shop_hub_choice_calls_show_shop_and_saves()
    test_summon_hub_choice_calls_show_summon_and_saves()
    test_heroes_hub_choice_calls_show_heroes_and_saves()
    print("\nALL GAME LOOP INTEGRATION TESTS PASSED")


if __name__ == "__main__":
    main_test()

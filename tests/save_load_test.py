"""Covers game/save_system.py (JSON save/load round-trip) and
game/rewards.py (the money-always/gems-on-win payout rule).

Run directly: python3 tests/save_load_test.py
"""
import json
import os
import random
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.equipment_db import EQUIPMENT
from engine.types import BattleResult
from game import save_system
from game.player_state import PlayerState, STARTING_GEMS, STARTING_MONEY
from game.roster import PlayerCharacter
from game.rewards import compute_battle_rewards


def test_new_game_starts_with_one_hero_and_starting_currency():
    hero = PlayerCharacter(name="Vex", class_id="ranged_dps")
    state = PlayerState.new_game(hero)
    assert state.characters == [hero]
    assert state.money == STARTING_MONEY
    assert state.gems == STARTING_GEMS
    assert state.inventory, "new_game should carry over the standard starting consumables"
    print("test_new_game_starts_with_one_hero_and_starting_currency: PASS")


def test_save_and_load_round_trips_everything():
    tmp_dir = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp_dir, "save1.json")
        assert not save_system.save_exists(path)

        hero = PlayerCharacter(name="Brann", class_id="tank")
        hero.equip("rusty_sword", EQUIPMENT)
        hero.grant_xp(105)  # should land partway into level 3 -- see data/leveling.py's resolve_level_up
        state = PlayerState.new_game(hero)
        state.money = 245
        state.gems = 17
        state.inventory["potion"] = 9
        state.owned_equipment["lucky_charm"] = 2

        save_system.save_game(state, path)
        assert save_system.save_exists(path)

        loaded = save_system.load_game(path)
        assert loaded.money == 245
        assert loaded.gems == 17
        assert loaded.inventory["potion"] == 9
        assert loaded.owned_equipment["lucky_charm"] == 2
        assert len(loaded.characters) == 1
        loaded_hero = loaded.characters[0]
        assert loaded_hero.id == hero.id
        assert loaded_hero.name == "Brann"
        assert loaded_hero.class_id == "tank"
        assert loaded_hero.equipped["weapon"] == "rusty_sword"
        assert loaded_hero.equipped["armor"] is None
        assert loaded_hero.level == 3, "level must round-trip (105 xp from level 1 resolves to level 3)"
        assert loaded_hero.xp == 5, "leftover xp toward the next level must round-trip too"

        # And the loaded character must still actually work as a real character
        # (build_combatant, effective_stats) -- not just round-trip as inert data.
        combatant = loaded_hero.build_combatant(EQUIPMENT)
        assert combatant.name == "Brann"
        print("test_save_and_load_round_trips_everything: PASS")
    finally:
        shutil.rmtree(tmp_dir)


def test_save_and_load_round_trips_rarity_stars_shards_and_active_party():
    """New as of the hero-rarity pass -- rarity/stars/shards on each
    character, and PlayerState.active_party (game/party.py's selection),
    must all survive a save/load round trip."""
    tmp_dir = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp_dir, "save1.json")
        hero = PlayerCharacter(name="Nadia", class_id="ranged_dps", rarity="legendary", stars=4, shards=9)
        second = PlayerCharacter(name="Gareth", class_id="tank")
        state = PlayerState.new_game(hero)
        state.characters.append(second)
        state.active_party = [hero.id, second.id]

        save_system.save_game(state, path)
        loaded = save_system.load_game(path)

        loaded_hero = next(c for c in loaded.characters if c.id == hero.id)
        assert loaded_hero.rarity == "legendary"
        assert loaded_hero.stars == 4
        assert loaded_hero.shards == 9
        assert loaded.active_party == [hero.id, second.id]
        print("test_save_and_load_round_trips_rarity_stars_shards_and_active_party: PASS")
    finally:
        shutil.rmtree(tmp_dir)


def test_loading_a_pre_hero_rarity_save_defaults_cleanly():
    """A save written before the hero-rarity pass has no rarity/stars/shards
    keys on its characters and no active_party key at all -- load_game must
    default those (common/1/0, empty party) rather than KeyError, same
    forward-compatibility story as test_loading_a_pre_level_curve_save_defaults_to_level_1."""
    tmp_dir = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp_dir, "save1.json")
        legacy_data = {
            "version": 1, "money": 50, "gems": 4, "inventory": {}, "owned_equipment": {},
            "characters": [{"id": "abc12345", "name": "Old", "class_id": "mage",
                             "equipped": {"weapon": None, "armor": None, "accessory": None},
                             "level": 3, "xp": 5}],
        }
        with open(path, "w") as f:
            json.dump(legacy_data, f)

        loaded = save_system.load_game(path)
        assert loaded.characters[0].rarity == "common"
        assert loaded.characters[0].stars == 1
        assert loaded.characters[0].shards == 0
        assert loaded.active_party == []
        print("test_loading_a_pre_hero_rarity_save_defaults_cleanly: PASS")
    finally:
        shutil.rmtree(tmp_dir)


def test_loading_a_pre_level_curve_save_defaults_to_level_1():
    """A save file written before the level-curve pass has no "level"/"xp"
    keys on its characters at all -- load_game must default those to (1, 0)
    rather than KeyError, so old saves don't become unloadable."""
    tmp_dir = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp_dir, "save1.json")
        legacy_data = {
            "version": 1, "money": 50, "gems": 4, "inventory": {}, "owned_equipment": {},
            "characters": [{"id": "abc12345", "name": "Old", "class_id": "mage",
                             "equipped": {"weapon": None, "armor": None, "accessory": None}}],
        }
        with open(path, "w") as f:
            json.dump(legacy_data, f)

        loaded = save_system.load_game(path)
        assert loaded.characters[0].level == 1
        assert loaded.characters[0].xp == 0
        print("test_loading_a_pre_level_curve_save_defaults_to_level_1: PASS")
    finally:
        shutil.rmtree(tmp_dir)


def test_save_write_is_atomic_no_partial_file_left_on_disk():
    """save_game writes to a .tmp file and os.replace()s it into place --
    confirm the temp file doesn't linger and the real path is valid JSON
    (not e.g. truncated) immediately after saving."""
    tmp_dir = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp_dir, "save1.json")
        state = PlayerState.new_game(PlayerCharacter(name="Iri", class_id="mage"))
        save_system.save_game(state, path)
        assert os.path.isfile(path)
        assert not os.path.isfile(path + ".tmp"), "temp file should be renamed away, not left behind"
        # A second save (overwrite) should behave the same way.
        state.money += 10
        save_system.save_game(state, path)
        reloaded = save_system.load_game(path)
        assert reloaded.money == state.money
        print("test_save_write_is_atomic_no_partial_file_left_on_disk: PASS")
    finally:
        shutil.rmtree(tmp_dir)


def test_delete_save_removes_the_file():
    tmp_dir = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp_dir, "save1.json")
        save_system.save_game(PlayerState.new_game(PlayerCharacter(name="X", class_id="support")), path)
        assert save_system.save_exists(path)
        save_system.delete_save(path)
        assert not save_system.save_exists(path)
        save_system.delete_save(path)  # deleting a nonexistent save should be a no-op, not an error
        print("test_delete_save_removes_the_file: PASS")
    finally:
        shutil.rmtree(tmp_dir)


def test_rewards_always_pay_money_but_gems_and_xp_only_on_victory():
    rng = random.Random(1234)
    for _ in range(200):
        money, gems, xp = compute_battle_rewards(BattleResult.VICTORY, rng)
        assert money > 0 and gems > 0 and xp > 0, (money, gems, xp)
        money, gems, xp = compute_battle_rewards(BattleResult.DEFEAT, rng)
        assert money > 0 and gems == 0 and xp == 0, (money, gems, xp)
        money, gems, xp = compute_battle_rewards(BattleResult.FLED, rng)
        assert money > 0 and gems == 0 and xp == 0, (money, gems, xp)
    print("test_rewards_always_pay_money_but_gems_and_xp_only_on_victory: PASS (200 samples of each outcome)")


def test_reward_multiplier_matches_andrews_worked_example():
    """1 hero vs 3 enemies = x1.5; on extreme difficulty = x3 -- the exact
    example from the original feature request."""
    from game.rewards import reward_multiplier
    assert reward_multiplier("normal", 1, 3) == 1.5
    assert reward_multiplier("extreme", 1, 3) == 3.0
    print("test_reward_multiplier_matches_andrews_worked_example: PASS")


def main():
    test_new_game_starts_with_one_hero_and_starting_currency()
    test_save_and_load_round_trips_everything()
    test_save_and_load_round_trips_rarity_stars_shards_and_active_party()
    test_loading_a_pre_hero_rarity_save_defaults_cleanly()
    test_loading_a_pre_level_curve_save_defaults_to_level_1()
    test_save_write_is_atomic_no_partial_file_left_on_disk()
    test_delete_save_removes_the_file()
    test_rewards_always_pay_money_but_gems_and_xp_only_on_victory()
    test_reward_multiplier_matches_andrews_worked_example()
    print("\nALL SAVE/LOAD + REWARDS TESTS PASSED")


if __name__ == "__main__":
    main()

"""Headless coverage for game/heroes.py -- spending a hero's banked shards
(granted by duplicate summons, see tests/summon_test.py) on a star upgrade.
No UI involved, same approach as tests/shop_test.py and tests/party_test.py.

Run directly: python3 tests/heroes_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.hero_rarity import MAX_STARS, shard_cost_for_next_star
from game import heroes
from game.player_state import PlayerState
from game.roster import PlayerCharacter


def _state_with(rarity="common", stars=1, shards=0):
    hero = PlayerCharacter(name="Ari", class_id="tank", rarity=rarity, stars=stars, shards=shards)
    return PlayerState.new_game(hero), hero


def test_upgrade_star_spends_exact_cost_and_increments_stars():
    state, hero = _state_with(rarity="common", stars=1, shards=100)
    cost = shard_cost_for_next_star("common", 1)
    ok, msg = heroes.upgrade_star(state, hero.id)
    assert ok, msg
    assert hero.stars == 2
    assert hero.shards == 100 - cost
    print(f"test_upgrade_star_spends_exact_cost_and_increments_stars: PASS ({msg})")


def test_upgrade_star_fails_cleanly_when_not_enough_shards():
    state, hero = _state_with(rarity="mythic", stars=1, shards=1)  # mythic star 2 costs more than 1
    ok, msg = heroes.upgrade_star(state, hero.id)
    assert not ok and "Not enough shards" in msg, msg
    assert hero.stars == 1 and hero.shards == 1, "a failed upgrade must not spend anything"
    print("test_upgrade_star_fails_cleanly_when_not_enough_shards: PASS")


def test_upgrade_star_refuses_past_max_stars():
    state, hero = _state_with(rarity="common", stars=MAX_STARS, shards=1000)
    ok, msg = heroes.upgrade_star(state, hero.id)
    assert not ok and "max stars" in msg, msg
    assert hero.stars == MAX_STARS and hero.shards == 1000
    print("test_upgrade_star_refuses_past_max_stars: PASS")


def test_upgrade_star_rejects_unknown_character_id():
    state, hero = _state_with()
    ok, msg = heroes.upgrade_star(state, "not-a-real-id")
    assert not ok and "Unknown character" in msg, msg
    print("test_upgrade_star_rejects_unknown_character_id: PASS")


def test_upgrade_star_can_walk_a_hero_all_the_way_to_max():
    """Banking a huge pile of shards up front and repeatedly upgrading
    should walk a hero from 1 star to MAX_STARS, one call per star, then
    refuse further upgrades -- exercises every entry in
    data/hero_rarity.py's SHARD_COST_FOR_STAR["rare"]."""
    state, hero = _state_with(rarity="rare", stars=1, shards=10_000)
    for expected_star in range(2, MAX_STARS + 1):
        ok, msg = heroes.upgrade_star(state, hero.id)
        assert ok, msg
        assert hero.stars == expected_star
    ok, msg = heroes.upgrade_star(state, hero.id)
    assert not ok and "max stars" in msg
    print(f"test_upgrade_star_can_walk_a_hero_all_the_way_to_max: PASS (ended with {hero.shards} shards left over)")


def main():
    test_upgrade_star_spends_exact_cost_and_increments_stars()
    test_upgrade_star_fails_cleanly_when_not_enough_shards()
    test_upgrade_star_refuses_past_max_stars()
    test_upgrade_star_rejects_unknown_character_id()
    test_upgrade_star_can_walk_a_hero_all_the_way_to_max()
    print("\nALL HERO STAR-UPGRADE TESTS PASSED")


if __name__ == "__main__":
    main()

"""Covers game/rewards.py's roll_hero_enemy_shard_drops -- the payout half of
"Hero characters can show up as enemies as well, and defeating them gives a
small chance to win their respective hero shards" (see
game/battle_setup.py's HERO_ENEMY_CHANCE for the encounter half). The rest of
game/rewards.py (compute_battle_rewards/reward_multiplier/size_modifier) is
already covered end-to-end by tests/save_load_test.py's
test_rewards_always_pay_money_but_gems_and_xp_only_on_victory and
test_reward_multiplier_matches_andrews_worked_example, so this file sticks to
the new function.

Run directly: python3 tests/rewards_test.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.hero_rarity import SHARDS_PER_DUPLICATE
from data.summon_pool import RecruitableHero
from engine.combatant import Combatant
from engine.stats import Stats
from game.battle_setup import build_hero_enemy_combatant
from game.player_state import PlayerState
from game.rewards import HERO_SHARD_DROP_CHANCE, roll_hero_enemy_shard_drops
from game.roster import PlayerCharacter


def _dead_combatant(name: str) -> Combatant:
    c = Combatant(name=name, is_enemy=True, base_stats=Stats(max_hp=10, max_mp=0, atk=1, def_=1, mag=1, res=1, spd=1, luk=1))
    c.take_damage(999)
    assert not c.alive
    return c


def test_no_drop_when_rng_misses_the_chance():
    hero = PlayerCharacter(name="Vex", class_id="melee_dps", rarity="rare")
    state = PlayerState.new_game(hero)
    recruit = RecruitableHero("Vex", "melee_dps", "rare")
    rng = random.Random()
    rng.random = lambda: HERO_SHARD_DROP_CHANCE  # exactly at the threshold -- ">=" in the source must reject this
    messages = roll_hero_enemy_shard_drops([(recruit, _dead_combatant("Rival Vex"))], state, rng=rng)
    assert messages == []
    assert hero.shards == 0
    print("test_no_drop_when_rng_misses_the_chance: PASS")


def test_drop_grants_shards_to_the_matching_owned_hero():
    hero = PlayerCharacter(name="Vex", class_id="melee_dps", rarity="rare")
    state = PlayerState.new_game(hero)
    recruit = RecruitableHero("Vex", "melee_dps", "rare")
    rng = random.Random()
    rng.random = lambda: 0.0  # always beats the chance
    messages = roll_hero_enemy_shard_drops([(recruit, _dead_combatant("Rival Vex"))], state, rng=rng)
    assert len(messages) == 1 and "Vex" in messages[0]
    assert hero.shards == SHARDS_PER_DUPLICATE["rare"]
    print(f"test_drop_grants_shards_to_the_matching_owned_hero: PASS ({messages[0]})")


def test_no_drop_for_a_hero_not_yet_recruited():
    """Shards only mean anything against an owned PlayerCharacter (see
    game/heroes.py's upgrade_star) -- a rival for a hero you've never pulled
    must be a silent no-op, not a crash or a phantom banked amount."""
    hero = PlayerCharacter(name="Someone Else", class_id="tank")
    state = PlayerState.new_game(hero)
    recruit = RecruitableHero("Kael", "melee_dps", "mythic")
    rng = random.Random()
    rng.random = lambda: 0.0
    messages = roll_hero_enemy_shard_drops([(recruit, _dead_combatant("Rival Kael"))], state, rng=rng)
    assert messages == []
    print("test_no_drop_for_a_hero_not_yet_recruited: PASS")


def test_no_drop_for_an_enemy_that_is_still_alive():
    hero = PlayerCharacter(name="Vex", class_id="melee_dps", rarity="rare")
    state = PlayerState.new_game(hero)
    recruit = RecruitableHero("Vex", "melee_dps", "rare")
    alive_combatant = build_hero_enemy_combatant(recruit, level=1)
    assert alive_combatant.alive
    rng = random.Random()
    rng.random = lambda: 0.0
    messages = roll_hero_enemy_shard_drops([(recruit, alive_combatant)], state, rng=rng)
    assert messages == []
    assert hero.shards == 0
    print("test_no_drop_for_an_enemy_that_is_still_alive: PASS")


def test_shard_amount_scales_with_rarity_like_a_duplicate_summon():
    hero = PlayerCharacter(name="Yulia", class_id="tank", rarity="mythic")
    state = PlayerState.new_game(hero)
    recruit = RecruitableHero("Yulia", "tank", "mythic")
    rng = random.Random()
    rng.random = lambda: 0.0
    roll_hero_enemy_shard_drops([(recruit, _dead_combatant("Rival Yulia"))], state, rng=rng)
    assert hero.shards == SHARDS_PER_DUPLICATE["mythic"]
    assert SHARDS_PER_DUPLICATE["mythic"] > SHARDS_PER_DUPLICATE["common"]
    print("test_shard_amount_scales_with_rarity_like_a_duplicate_summon: PASS")


def test_empty_defeated_list_is_a_safe_no_op():
    hero = PlayerCharacter(name="Solo", class_id="tank")
    state = PlayerState.new_game(hero)
    assert roll_hero_enemy_shard_drops([], state) == []
    print("test_empty_defeated_list_is_a_safe_no_op: PASS")


def main():
    test_no_drop_when_rng_misses_the_chance()
    test_drop_grants_shards_to_the_matching_owned_hero()
    test_no_drop_for_a_hero_not_yet_recruited()
    test_no_drop_for_an_enemy_that_is_still_alive()
    test_shard_amount_scales_with_rarity_like_a_duplicate_summon()
    test_empty_defeated_list_is_a_safe_no_op()
    print("\nALL HERO-RIVAL SHARD-DROP TESTS PASSED")


if __name__ == "__main__":
    main()

"""Covers data/leveling.py's pure functions in isolation from
PlayerCharacter/EnemyArchetype -- see tests/roster_test.py for the
integration-level checks against a real PlayerCharacter.

Run directly: python3 tests/leveling_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.leveling import (ENEMY_GROWTH_SCALE, MAX_LEVEL, apply_growth, full_xp_for_next_level, power_mult, resolve_level_up,
                           scale_item_heal, stat_scale, story_fight_xp, xp_for_next_level)
from engine.stats import Stats


def test_xp_curve_increases_by_20_per_level():
    # Full price from level 8 on: 40 + 20 * (level - 1).
    assert xp_for_next_level(8) == 40 + 20 * 7
    assert xp_for_next_level(9) == 40 + 20 * 8
    assert xp_for_next_level(10) == 40 + 20 * 9
    assert xp_for_next_level(50) == 40 + 20 * 49
    print("test_xp_curve_increases_by_20_per_level: PASS")


def test_first_few_levels_are_cheap():
    # The first levels cost a discounted share of the full price, climbing smoothly up to it.
    assert xp_for_next_level(1) == 16 and xp_for_next_level(2) == 29
    for story in (False, True):
        costs = [xp_for_next_level(lv, story) for lv in range(1, 12)]
        assert costs == sorted(costs), "early levels must never get cheaper as you climb"
        assert costs[0] < 0.5 * full_xp_for_next_level(1, story)
    assert xp_for_next_level(1, True) == 24
    assert story_fight_xp(1, rng=_FixedRng()) > xp_for_next_level(1, True) / 4, "a level-1 fight should be worth a good chunk of level 1->2"
    print("test_first_few_levels_are_cheap: PASS")


class _FixedRng:
    def uniform(self, a, b):
        return 1.0


def test_level_99_story_heroes_reach_the_target_numbers():
    from data.classes import CLASS_ARCHETYPES
    from data.hero_rarity import STORY_GROWTH_MULT, rarity_multiplier
    mult = rarity_multiplier("mythic")
    for cid, a in CLASS_ARCHETYPES.items():
        s = apply_growth(a.base_stats, a.growth, 99, STORY_GROWTH_MULT)
        hp, mp = round(s.max_hp * mult), round(s.max_mp * mult)
        assert 8500 <= hp <= 10000, (cid, hp)
        assert 450 <= mp <= 1000, (cid, mp)
        main = max(round(getattr(s, f) * mult) for f in ("atk", "def_", "mag"))
        assert 890 <= main <= 1000, (cid, main)   # support tops out at MAG 900, every other class at 999
    print("test_level_99_story_heroes_reach_the_target_numbers: PASS")


def test_power_mult_and_stat_scale_are_neutral_at_level_1():
    assert power_mult(1) == 1.0 and stat_scale("max_hp", 1) == 1.0 and stat_scale("atk", 1) == 1.0
    assert 2.5 < power_mult(99) < 3.6
    assert stat_scale("spd", 99) == 1.0 and stat_scale("max_mp", 99) == 1.0
    print("test_power_mult_and_stat_scale_are_neutral_at_level_1: PASS")


def test_item_heals_grow_with_max_hp_but_not_below_the_listed_amount():
    assert scale_item_heal(100, 100) == 100 and scale_item_heal(100, 230) == 100
    assert 100 < scale_item_heal(100, 1000) < scale_item_heal(100, 9999) < 100 * 9999 / 230
    print("test_item_heals_grow_with_max_hp_but_not_below_the_listed_amount: PASS")


def test_enemy_growth_is_scaled_and_level_1_is_untouched():
    base = Stats(max_hp=100, max_mp=20, atk=10, def_=8, mag=5, res=5, spd=10, luk=10)
    growth = Stats(max_hp=5, max_mp=1, atk=2, def_=1, mag=0, res=0, spd=1, luk=0)
    assert apply_growth(base, growth, 1, enemy=True) == base
    s = apply_growth(base, growth, 11, enemy=True)
    assert s.max_hp == 100 + round(5 * 10 * ENEMY_GROWTH_SCALE["max_hp"])
    assert s.atk == 10 + round(2 * 10 * ENEMY_GROWTH_SCALE["atk"])
    assert s.spd == 10 + 10 and s.max_mp == 20 + 10, "MP/SPD/LUK growth is not rescaled"
    print("test_enemy_growth_is_scaled_and_level_1_is_untouched: PASS")


def test_apply_growth_at_level_1_is_a_no_op():
    base = Stats(max_hp=100, max_mp=20, atk=10, def_=8, mag=5, res=5, spd=10, luk=10)
    growth = Stats(max_hp=5, max_mp=1, atk=2, def_=1, mag=0, res=0, spd=1, luk=0)
    stats = apply_growth(base, growth, 1)
    assert stats == base
    assert stats is not base, "apply_growth must return a copy, not the original object"
    print("test_apply_growth_at_level_1_is_a_no_op: PASS")


def test_apply_growth_multiplies_by_levels_past_1():
    base = Stats(max_hp=100, max_mp=20, atk=10, def_=8, mag=5, res=5, spd=10, luk=10)
    growth = Stats(max_hp=5, max_mp=1, atk=2, def_=1, mag=0, res=0, spd=1, luk=0)
    stats = apply_growth(base, growth, 4)  # 3 levels of growth applied
    assert stats.max_hp == 100 + 5 * 3
    assert stats.atk == 10 + 2 * 3
    assert stats.mag == 5, "zero growth stats should stay flat"
    print("test_apply_growth_multiplies_by_levels_past_1: PASS")


def test_resolve_level_up_matches_hand_worked_examples():
    # Sanity-checked by hand during the level-curve pass: xp_for_next_level(1) == 40.
    assert resolve_level_up(1, 15) == (1, 15, 0), "15 xp isn't enough to reach level 2 (needs 16)"
    assert resolve_level_up(1, 16) == (2, 0, 1), "exactly 16 xp should resolve to level 2 with 0 leftover"
    # level 1->2 costs 16, 2->3 costs 29 -- 50 total crosses both with 5 left over.
    assert resolve_level_up(1, 50) == (3, 5, 2)
    print("test_resolve_level_up_matches_hand_worked_examples: PASS")


def test_resolve_level_up_caps_at_max_level_and_stops_spending_xp():
    level, xp, gained = resolve_level_up(MAX_LEVEL - 1, xp_for_next_level(MAX_LEVEL - 1) + 999999)
    assert level == MAX_LEVEL
    assert xp == 0, "xp past the cap should be discarded, not left accumulating forever"
    assert gained == 1
    # Already at the cap: no further level-ups, no xp accrual.
    level, xp, gained = resolve_level_up(MAX_LEVEL, 500)
    assert level == MAX_LEVEL and xp == 0 and gained == 0
    print("test_resolve_level_up_caps_at_max_level_and_stops_spending_xp: PASS")


def test_resolve_level_up_with_zero_xp_is_a_no_op():
    assert resolve_level_up(5, 0) == (5, 0, 0)
    print("test_resolve_level_up_with_zero_xp_is_a_no_op: PASS")


def main():
    test_xp_curve_increases_by_20_per_level()
    test_first_few_levels_are_cheap()
    test_level_99_story_heroes_reach_the_target_numbers()
    test_power_mult_and_stat_scale_are_neutral_at_level_1()
    test_item_heals_grow_with_max_hp_but_not_below_the_listed_amount()
    test_enemy_growth_is_scaled_and_level_1_is_untouched()
    test_apply_growth_at_level_1_is_a_no_op()
    test_apply_growth_multiplies_by_levels_past_1()
    test_resolve_level_up_matches_hand_worked_examples()
    test_resolve_level_up_caps_at_max_level_and_stops_spending_xp()
    test_resolve_level_up_with_zero_xp_is_a_no_op()
    print("\nALL LEVELING TESTS PASSED")


if __name__ == "__main__":
    main()

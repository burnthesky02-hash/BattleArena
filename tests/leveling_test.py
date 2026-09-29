"""Covers data/leveling.py's pure functions in isolation from
PlayerCharacter/EnemyArchetype -- see tests/roster_test.py for the
integration-level checks against a real PlayerCharacter.

Run directly: python3 tests/leveling_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.leveling import MAX_LEVEL, apply_growth, resolve_level_up, xp_for_next_level
from engine.stats import Stats


def test_xp_curve_increases_by_20_per_level():
    assert xp_for_next_level(1) == 40
    assert xp_for_next_level(2) == 60
    assert xp_for_next_level(3) == 80
    assert xp_for_next_level(10) == 40 + 20 * 9
    print("test_xp_curve_increases_by_20_per_level: PASS")


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
    assert resolve_level_up(1, 39) == (1, 39, 0), "39 xp isn't enough to reach level 2 (needs 40)"
    assert resolve_level_up(1, 40) == (2, 0, 1), "exactly 40 xp should resolve to level 2 with 0 leftover"
    # level 1->2 costs 40, 2->3 costs 60 -- 105 total crosses both with 5 left over.
    assert resolve_level_up(1, 105) == (3, 5, 2)
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
    test_apply_growth_at_level_1_is_a_no_op()
    test_apply_growth_multiplies_by_levels_past_1()
    test_resolve_level_up_matches_hand_worked_examples()
    test_resolve_level_up_caps_at_max_level_and_stops_spending_xp()
    test_resolve_level_up_with_zero_xp_is_a_no_op()
    print("\nALL LEVELING TESTS PASSED")


if __name__ == "__main__":
    main()

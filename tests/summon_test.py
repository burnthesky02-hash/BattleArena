"""Headless coverage for game/summon.py -- spending gems on a new roster
character or a piece of premium equipment. No UI involved, same approach as
tests/shop_test.py and tests/rewards (compute_battle_rewards): an injectable
random.Random makes the rarity/name rolls deterministic.

As of the hero-rarity pass, character summons roll a rarity first
(data/hero_rarity.py's HERO_SUMMON_WEIGHTS) then a class-matched hero at
that rarity (data/summon_pool.py's RECRUITABLE_BY_RARITY) -- and a pull
matching a hero already owned is no longer avoided, it grants hero shards
instead (see data/hero_rarity.py's SHARDS_PER_DUPLICATE). The old
"avoid duplicates while a fresh option remains" tests are gone along with
that behavior; test_summon_character_matching_an_owned_hero_grants_shards
and friends replace them.

Run directly: python3 tests/summon_test.py
"""
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.classes import CLASS_IDS
from data.equipment_db import EQUIPMENT
from data.hero_rarity import HERO_RARITIES, MAX_STARS, SHARDS_PER_DUPLICATE
from data.summon_pool import (
    CHARACTER_SUMMON_COST, CHARACTER_SUMMON_COST_X10, EQUIPMENT_SUMMON_COST, EQUIPMENT_SUMMON_COST_X10,
    RECRUITABLE_BY_RARITY, RECRUITABLE_ROSTER, SUMMON_X10_COUNT,
)
from game import summon
from game.player_state import PlayerState
from game.roster import PlayerCharacter


def test_recruitable_roster_has_5_per_class_and_one_of_each_rarity_per_class():
    assert len(RECRUITABLE_ROSTER) == 25
    pairs = [(h.name, h.class_id) for h in RECRUITABLE_ROSTER]
    assert len(set(pairs)) == len(pairs), "duplicate (name, class_id) pairs found"
    counts = Counter(h.class_id for h in RECRUITABLE_ROSTER)
    assert set(counts) == set(CLASS_IDS)
    assert all(n == 5 for n in counts.values()), counts
    # Every class has exactly one hero at each of the 5 rarities.
    for class_id in CLASS_IDS:
        rarities = sorted(h.rarity for h in RECRUITABLE_ROSTER if h.class_id == class_id)
        assert rarities == sorted(HERO_RARITIES), (class_id, rarities)
    print("test_recruitable_roster_has_5_per_class_and_one_of_each_rarity_per_class: PASS")


def test_recruitable_by_rarity_has_exactly_one_hero_per_class():
    for rarity in HERO_RARITIES:
        heroes = RECRUITABLE_BY_RARITY[rarity]
        assert len(heroes) == 5, (rarity, len(heroes))
        assert {h.class_id for h in heroes} == set(CLASS_IDS)
        assert all(h.rarity == rarity for h in heroes)
    print("test_recruitable_by_rarity_has_exactly_one_hero_per_class: PASS")


def test_every_recruit_builds_a_real_level_1_character():
    """A summoned recruit should be a normal, fully-functional level-1
    PlayerCharacter -- not just a valid (name, class_id, rarity) on paper."""
    for h in RECRUITABLE_ROSTER:
        recruit = PlayerCharacter(name=h.name, class_id=h.class_id, rarity=h.rarity)
        assert recruit.level == 1 and recruit.xp == 0
        assert recruit.stars == 1 and recruit.shards == 0
        combatant = recruit.build_combatant(EQUIPMENT)
        assert combatant.name == h.name
    print("test_every_recruit_builds_a_real_level_1_character: PASS")


def _fresh_state(gems=200):
    hero = PlayerCharacter(name="Buyer", class_id="tank")
    state = PlayerState.new_game(hero)
    state.gems = gems
    return state, hero


def test_summon_character_deducts_gems_and_adds_to_roster():
    state, hero = _fresh_state(gems=100)
    ok, msg, recruit, rarity = summon.summon_character(state, rng=random.Random(1))
    assert ok, msg
    assert state.gems == 100 - CHARACTER_SUMMON_COST
    assert len(state.characters) == 2
    assert state.characters[-1] is recruit
    assert recruit.rarity == rarity
    assert any(h.name == recruit.name and h.class_id == recruit.class_id and h.rarity == rarity
               for h in RECRUITABLE_ROSTER)
    print(f"test_summon_character_deducts_gems_and_adds_to_roster: PASS ({msg})")


def test_summon_character_fails_cleanly_when_too_poor():
    state, hero = _fresh_state(gems=CHARACTER_SUMMON_COST - 1)
    ok, msg, recruit, rarity = summon.summon_character(state, rng=random.Random(1))
    assert not ok and "Not enough gems" in msg, msg
    assert recruit is None and rarity is None
    assert state.gems == CHARACTER_SUMMON_COST - 1  # nothing deducted on failure
    assert len(state.characters) == 1
    print("test_summon_character_fails_cleanly_when_too_poor: PASS")


def test_summon_character_matching_an_owned_hero_grants_shards_not_a_new_slot():
    state, hero = _fresh_state(gems=100000)
    # Seed the roster with every recruitable hero so every future pull is a
    # guaranteed duplicate -- proves duplicates are allowed (no dedup logic
    # left) and that they grant shards instead of failing or padding the
    # roster.
    for h in RECRUITABLE_ROSTER:
        state.characters.append(PlayerCharacter(name=h.name, class_id=h.class_id, rarity=h.rarity))
    roster_size = len(state.characters)

    ok, msg, hit, rarity = summon.summon_character(state, rng=random.Random(42))
    assert ok, msg
    assert "Duplicate" in msg
    assert len(state.characters) == roster_size, "a duplicate pull must not add a new roster entry"
    assert hit.shards == SHARDS_PER_DUPLICATE[rarity], (hit.shards, rarity)
    print(f"test_summon_character_matching_an_owned_hero_grants_shards_not_a_new_slot: PASS ({msg})")


def test_summon_character_duplicate_shards_accumulate_across_pulls():
    state, hero = _fresh_state(gems=100000)
    recruit_data = RECRUITABLE_BY_RARITY["common"][0]
    owned = PlayerCharacter(name=recruit_data.name, class_id=recruit_data.class_id, rarity="common")
    state.characters.append(owned)

    total_expected = 0
    hits = 0
    # Roll until we've actually landed on this exact hero a few times (rare
    # rolls make a fixed small seed loop unreliable otherwise).
    for i in range(400):
        ok, msg, hit, rarity = summon.summon_character(state, rng=random.Random(i))
        assert ok, msg
        if hit is owned:
            total_expected += SHARDS_PER_DUPLICATE[rarity]
            hits += 1
        if hits >= 3:
            break
    assert hits >= 3, "expected to re-roll the same seeded common hero at least 3 times in 400 pulls"
    assert owned.shards == total_expected, (owned.shards, total_expected)
    print(f"test_summon_character_duplicate_shards_accumulate_across_pulls: PASS "
          f"({hits} duplicate hits, {owned.shards} shards banked)")


def test_summon_character_rarity_weights_favor_common_over_mythic():
    state, hero = _fresh_state(gems=10_000_000)
    rng = random.Random(7)
    seen = Counter()
    for _ in range(3000):
        ok, msg, _recruit, rarity = summon.summon_character(state, rng=rng)
        assert ok, msg
        seen[rarity] += 1
    assert seen["common"] > seen["rare"] > seen["epic"] > seen["legendary"] > seen["mythic"] > 0, seen
    print(f"test_summon_character_rarity_weights_favor_common_over_mythic: PASS ({dict(seen)})")


def test_summon_equipment_deducts_gems_and_adds_to_stash():
    state, hero = _fresh_state(gems=100)
    ok, msg = summon.summon_equipment(state, EQUIPMENT, rng=random.Random(1))
    assert ok, msg
    assert state.gems == 100 - EQUIPMENT_SUMMON_COST
    assert sum(state.owned_equipment.values()) == 1
    (item_id,) = state.owned_equipment.keys()
    assert EQUIPMENT[item_id].cost <= 0, "summon should only ever hand out premium (cost<=0) gear"
    assert hero.equipped["weapon"] is None, "summoning gear should not auto-equip it"
    print(f"test_summon_equipment_deducts_gems_and_adds_to_stash: PASS ({msg})")


def test_summon_equipment_fails_cleanly_when_too_poor():
    state, hero = _fresh_state(gems=EQUIPMENT_SUMMON_COST - 1)
    ok, msg = summon.summon_equipment(state, EQUIPMENT, rng=random.Random(1))
    assert not ok and "Not enough gems" in msg, msg
    assert state.gems == EQUIPMENT_SUMMON_COST - 1
    assert state.owned_equipment == {}
    print("test_summon_equipment_fails_cleanly_when_too_poor: PASS")


def test_summon_equipment_only_ever_draws_epic_or_legendary():
    state, hero = _fresh_state(gems=1000000)
    seen_rarities = set()
    for i in range(200):
        ok, msg = summon.summon_equipment(state, EQUIPMENT, rng=random.Random(i))
        assert ok, msg
    for item_id, count in state.owned_equipment.items():
        if count > 0:
            seen_rarities.add(EQUIPMENT[item_id].rarity)
    assert seen_rarities <= {"epic", "legendary"}, seen_rarities
    assert seen_rarities, "200 pulls should have produced at least one item"
    print(f"test_summon_equipment_only_ever_draws_epic_or_legendary: PASS (saw {seen_rarities})")


def test_x10_costs_are_exactly_ten_times_the_single_pull_cost():
    assert CHARACTER_SUMMON_COST_X10 == CHARACTER_SUMMON_COST * SUMMON_X10_COUNT
    assert EQUIPMENT_SUMMON_COST_X10 == EQUIPMENT_SUMMON_COST * SUMMON_X10_COUNT
    print("test_x10_costs_are_exactly_ten_times_the_single_pull_cost: PASS")


class _FixedRng:
    """A random.Random look-alike (just the two methods game/summon.py's
    rolling helpers actually call) that always returns the same rarity and
    the same index within that rarity's 5 class-matched heroes -- used
    below to force a guaranteed duplicate within a single batch, something
    real randomness can't reliably be seeded to do in a small batch."""
    def __init__(self, rarity: str, recruit_index: int = 0):
        self._rarity = rarity
        self._recruit_index = recruit_index

    def choices(self, population, weights=None, k=1):
        return [self._rarity] * k

    def choice(self, seq):
        return seq[self._recruit_index]


class _SequenceRng:
    """Same idea as _FixedRng, but pops a different rarity off a fixed list
    each call -- used to force a specific rarity to land at a specific
    position within a batch (e.g. "the 2nd of 3 pulls is mythic")."""
    def __init__(self, rarities):
        self._rarities = list(rarities)

    def choices(self, population, weights=None, k=1):
        return [self._rarities.pop(0)]

    def choice(self, seq):
        return seq[0]


def test_summon_character_batch_fails_all_or_nothing_when_too_poor_for_the_whole_batch():
    state, hero = _fresh_state(gems=CHARACTER_SUMMON_COST_X10 - 1)  # affordable for 9 pulls, not 10
    ok, msg, results = summon.summon_character_x10(state, rng=random.Random(1))
    assert not ok and "Not enough gems" in msg, msg
    assert results == []
    assert state.gems == CHARACTER_SUMMON_COST_X10 - 1, "a failed batch must not spend anything, not even a partial amount"
    assert len(state.characters) == 1
    print("test_summon_character_batch_fails_all_or_nothing_when_too_poor_for_the_whole_batch: PASS")


def test_summon_character_x10_deducts_one_lump_sum_and_returns_ten_results():
    state, hero = _fresh_state(gems=1000)
    ok, msg, results = summon.summon_character_x10(state, rng=random.Random(3))
    assert ok, msg
    assert len(results) == SUMMON_X10_COUNT
    assert state.gems == 1000 - CHARACTER_SUMMON_COST_X10
    assert f"Pulled {SUMMON_X10_COUNT} heroes" in msg, msg
    assert all(r.rarity in HERO_RARITIES for r in results)
    print(f"test_summon_character_x10_deducts_one_lump_sum_and_returns_ten_results: PASS ({msg})")


def test_summon_character_batch_second_pull_of_same_hero_within_one_batch_is_a_duplicate():
    state, hero = _fresh_state(gems=100000)
    ok, msg, results = summon.summon_character_batch(state, 3, rng=_FixedRng("common", 0))
    assert ok, msg
    assert not results[0].is_duplicate, "the first pull of a never-owned hero must be a new recruit"
    assert results[1].is_duplicate and results[2].is_duplicate, (
        "a hero pulled again later in the same batch must be treated as a duplicate, same as across two separate summons")
    assert results[0].character is results[1].character is results[2].character
    assert results[0].character.shards == results[1].shards_gained + results[2].shards_gained
    print("test_summon_character_batch_second_pull_of_same_hero_within_one_batch_is_a_duplicate: PASS")


def test_summon_character_batch_summary_names_the_highest_rarity_pulled():
    state, hero = _fresh_state(gems=100000)
    ok, msg, results = summon.summon_character_batch(state, 3, rng=_SequenceRng(["common", "mythic", "common"]))
    assert ok, msg
    assert results[1].rarity == "mythic"
    assert "Mythic" in msg, msg
    print(f"test_summon_character_batch_summary_names_the_highest_rarity_pulled: PASS ({msg})")


def test_summon_equipment_x10_deducts_one_lump_sum_and_adds_ten_items():
    state, hero = _fresh_state(gems=1000)
    ok, msg, results = summon.summon_equipment_x10(state, EQUIPMENT, rng=random.Random(5))
    assert ok, msg
    assert len(results) == SUMMON_X10_COUNT
    assert state.gems == 1000 - EQUIPMENT_SUMMON_COST_X10
    assert sum(state.owned_equipment.values()) == SUMMON_X10_COUNT
    assert all(EQUIPMENT[r.item.id].cost <= 0 for r in results)
    print(f"test_summon_equipment_x10_deducts_one_lump_sum_and_adds_ten_items: PASS ({msg})")


def test_summon_equipment_batch_fails_all_or_nothing_when_too_poor_for_the_whole_batch():
    state, hero = _fresh_state(gems=EQUIPMENT_SUMMON_COST_X10 - 1)
    ok, msg, results = summon.summon_equipment_x10(state, EQUIPMENT, rng=random.Random(1))
    assert not ok and "Not enough gems" in msg, msg
    assert results == []
    assert state.gems == EQUIPMENT_SUMMON_COST_X10 - 1
    assert state.owned_equipment == {}
    print("test_summon_equipment_batch_fails_all_or_nothing_when_too_poor_for_the_whole_batch: PASS")


def test_summon_equipment_weights_epic_more_than_legendary():
    state, hero = _fresh_state(gems=1000000)
    rng = random.Random(7)
    epic_pulls = legendary_pulls = 0
    for _ in range(300):
        state.owned_equipment.clear()
        ok, msg = summon.summon_equipment(state, EQUIPMENT, rng=rng)
        assert ok, msg
        (item_id,) = [k for k, v in state.owned_equipment.items() if v > 0]
        rarity = EQUIPMENT[item_id].rarity
        if rarity == "epic":
            epic_pulls += 1
        elif rarity == "legendary":
            legendary_pulls += 1
    assert epic_pulls > legendary_pulls, (
        f"epic should be weighted heavier than legendary, got epic={epic_pulls} legendary={legendary_pulls}")
    print(f"test_summon_equipment_weights_epic_more_than_legendary: PASS (epic={epic_pulls}, legendary={legendary_pulls})")


def main():
    test_recruitable_roster_has_5_per_class_and_one_of_each_rarity_per_class()
    test_recruitable_by_rarity_has_exactly_one_hero_per_class()
    test_every_recruit_builds_a_real_level_1_character()
    test_summon_character_deducts_gems_and_adds_to_roster()
    test_summon_character_fails_cleanly_when_too_poor()
    test_summon_character_matching_an_owned_hero_grants_shards_not_a_new_slot()
    test_summon_character_duplicate_shards_accumulate_across_pulls()
    test_summon_character_rarity_weights_favor_common_over_mythic()
    test_x10_costs_are_exactly_ten_times_the_single_pull_cost()
    test_summon_character_batch_fails_all_or_nothing_when_too_poor_for_the_whole_batch()
    test_summon_character_x10_deducts_one_lump_sum_and_returns_ten_results()
    test_summon_character_batch_second_pull_of_same_hero_within_one_batch_is_a_duplicate()
    test_summon_character_batch_summary_names_the_highest_rarity_pulled()
    test_summon_equipment_x10_deducts_one_lump_sum_and_adds_ten_items()
    test_summon_equipment_batch_fails_all_or_nothing_when_too_poor_for_the_whole_batch()
    test_summon_equipment_deducts_gems_and_adds_to_stash()
    test_summon_equipment_fails_cleanly_when_too_poor()
    test_summon_equipment_only_ever_draws_epic_or_legendary()
    test_summon_equipment_weights_epic_more_than_legendary()
    print("\nALL SUMMON TESTS PASSED")


if __name__ == "__main__":
    main()

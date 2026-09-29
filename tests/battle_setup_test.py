"""Covers data/enemy_pool.py (the level/difficulty-aware enemy archetype
roster) and game/battle_setup.py (difficulty -> enemy level, random
opponent selection, and building a full BattleSetup) -- the "expand battle
selection" half of the level-curve feature request. data/enemies.py's fixed
three-enemy make_enemy_group() is deliberately untested here; it's legacy
test-fixture data covered by tests/headless_battle_test.py and friends, and
is not touched by this feature.

Run directly: python3 tests/battle_setup_test.py
"""
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.classes import CLASS_ARCHETYPES, CLASS_IDS
from data.enemy_pool import ENEMY_ARCHETYPES, ENEMY_IDS
from data.equipment_db import EQUIPMENT
from data.leveling import MAX_LEVEL
from data.skills_db import SKILLS
from data.summon_pool import RECRUITABLE_ROSTER
from engine.types import Element
from game.battle_setup import (
    DIFFICULTY_IDS, DIFFICULTY_REWARD_MODIFIER, HERO_ENEMY_CHANCE, HERO_ENEMY_PERSONAS, MAX_OPPONENTS,
    MIN_OPPONENTS, build_battle, build_enemy_combatant, build_hero_enemy_combatant, choose_enemy_ids,
    choose_hero_rivals, compute_enemy_level, party_average_level,
)
from game.roster import PlayerCharacter


def test_enemy_pool_has_13_valid_archetypes():
    assert len(ENEMY_ARCHETYPES) == 13
    assert len(ENEMY_IDS) == 13
    assert set(ENEMY_IDS) == set(ENEMY_ARCHETYPES)
    for eid, archetype in ENEMY_ARCHETYPES.items():
        assert archetype.id == eid
        assert archetype.skill_ids, f"{eid} has an empty skill kit"
        for skill_id in archetype.skill_ids:
            assert skill_id in SKILLS, f"{eid}'s kit references unknown skill {skill_id!r}"
        for element in archetype.resistances:
            assert isinstance(element, Element), f"{eid} has a non-Element resistance key"
        assert archetype.persona, f"{eid} has no persona text"
    print("test_enemy_pool_has_13_valid_archetypes: PASS")


def test_original_three_enemies_kept_their_exact_legacy_stats():
    """iron_golem/bandit_rogue/dark_cultist's level-1 base_stats must exactly
    match data/enemies.py's original fixed trio -- the pool is meant to
    extend the roster, not quietly retune the enemies every existing
    balance test (tests/headless_battle_test.py's ~79% win-rate check in
    particular) depends on."""
    from data.enemies import make_enemy_group
    legacy_by_name = {c.name: c for c in make_enemy_group()}
    mapping = {"iron_golem": "Iron Golem", "bandit_rogue": "Bandit Rogue", "dark_cultist": "Dark Cultist"}
    for pool_id, legacy_name in mapping.items():
        pool_stats = ENEMY_ARCHETYPES[pool_id].base_stats
        legacy_stats = legacy_by_name[legacy_name].base_stats
        assert pool_stats == legacy_stats, (pool_id, pool_stats, legacy_stats)
    print("test_original_three_enemies_kept_their_exact_legacy_stats: PASS")


def test_party_average_level():
    party = [PlayerCharacter(name="A", class_id="tank", level=10),
             PlayerCharacter(name="B", class_id="mage", level=14)]
    assert party_average_level(party) == 12.0
    assert party_average_level([]) == 1.0, "an empty party shouldn't crash or divide by zero"
    print("test_party_average_level: PASS")


def test_compute_enemy_level_matches_andrews_offsets():
    """easy = normal target - 2 or 3, hard = normal target + 2 or 3, extreme
    = normal target + 5 flat, all relative to a party-average-level +/-1
    jittered "normal" target (see game/battle_setup.py's module docstring
    for why this reading was chosen)."""
    rng = random.Random(99)
    avg = 20.0
    samples = {d: [compute_enemy_level(avg, d, rng=rng) for _ in range(3000)] for d in DIFFICULTY_IDS}

    # normal should hover tightly around the party's average level (+/-1 jitter only).
    assert all(19 <= lv <= 21 for lv in samples["normal"])
    # easy should be strictly, comfortably below normal's range.
    assert all(15 <= lv <= 19 for lv in samples["easy"])
    assert max(samples["easy"]) < max(samples["normal"]) + 1
    # hard should be strictly, comfortably above normal's range.
    assert all(21 <= lv <= 25 for lv in samples["hard"])
    # extreme is a flat +5 on top of the jittered normal target (19-21 -> 24-26).
    assert all(24 <= lv <= 26 for lv in samples["extreme"])
    print("test_compute_enemy_level_matches_andrews_offsets: PASS")


def test_compute_enemy_level_never_goes_below_1_or_past_max_level():
    rng = random.Random(1)
    low = [compute_enemy_level(1.0, "easy", rng=rng) for _ in range(200)]
    assert all(lv >= 1 for lv in low)
    high = [compute_enemy_level(MAX_LEVEL, "extreme", rng=rng) for _ in range(200)]
    assert all(lv <= MAX_LEVEL for lv in high)
    print("test_compute_enemy_level_never_goes_below_1_or_past_max_level: PASS")


def test_compute_enemy_level_rejects_unknown_difficulty():
    try:
        compute_enemy_level(10.0, "nightmare")
        raise AssertionError("expected ValueError")
    except ValueError:
        print("test_compute_enemy_level_rejects_unknown_difficulty: PASS")


def test_choose_enemy_ids_respects_bounds_and_uniqueness():
    rng = random.Random(5)
    for n in range(MIN_OPPONENTS, MAX_OPPONENTS + 1):
        ids = choose_enemy_ids(n, rng=rng)
        assert len(ids) == n
        assert len(set(ids)) == n, "no archetype should be picked twice in one encounter"
        assert all(i in ENEMY_IDS for i in ids)
    for bad in (0, MAX_OPPONENTS + 1, -1):
        try:
            choose_enemy_ids(bad)
            raise AssertionError(f"expected ValueError for num_enemies={bad}")
        except ValueError:
            pass
    print("test_choose_enemy_ids_respects_bounds_and_uniqueness: PASS")


def test_build_enemy_combatant_applies_growth():
    archetype = ENEMY_ARCHETYPES["goblin_skirmisher"]
    lvl1 = build_enemy_combatant("goblin_skirmisher", 1)
    assert lvl1.base_stats == archetype.base_stats
    lvl5 = build_enemy_combatant("goblin_skirmisher", 5)
    assert lvl5.base_stats.max_hp == archetype.base_stats.max_hp + archetype.growth.max_hp * 4
    assert lvl5.is_enemy is True
    assert lvl5.name == archetype.name
    print("test_build_enemy_combatant_applies_growth: PASS")


def test_build_battle_end_to_end():
    party = [PlayerCharacter(name="Solo", class_id="support", level=8)]
    rng = random.Random(3)
    setup = build_battle(party, EQUIPMENT, "hard", 4, rng=rng)
    assert setup.difficulty == "hard"
    assert len(setup.party) == 1
    assert len(setup.enemies) == 4
    assert setup.num_heroes == 1 and setup.num_enemies == 4
    assert len(setup.enemy_ids) == 4 and len(set(setup.enemy_ids)) == 4
    for enemy in setup.enemies:
        assert enemy.is_enemy is True
        assert enemy.alive

    try:
        build_battle(party, EQUIPMENT, "impossible", 2)
        raise AssertionError("expected ValueError for a bad difficulty")
    except ValueError:
        pass
    print("test_build_battle_end_to_end: PASS")


def test_difficulty_reward_modifiers_match_andrews_spec():
    assert DIFFICULTY_REWARD_MODIFIER == {"easy": 0.75, "normal": 1.0, "hard": 1.25, "extreme": 2.0}
    print("test_difficulty_reward_modifiers_match_andrews_spec: PASS")


# --- hero rivals ("Hero characters can show up as enemies as well") --------

def test_hero_enemy_personas_cover_every_class():
    assert set(HERO_ENEMY_PERSONAS) == set(CLASS_IDS)
    for class_id, persona in HERO_ENEMY_PERSONAS.items():
        assert persona, f"{class_id} has no hero-rival persona text"
    print("test_hero_enemy_personas_cover_every_class: PASS")


def test_choose_hero_rivals_respects_bounds_and_uniqueness():
    rng = random.Random(7)
    for n in range(MIN_OPPONENTS, MAX_OPPONENTS + 1):
        rivals = choose_hero_rivals(n, rng=rng)
        assert len(rivals) == n
        keys = {(r.class_id, r.name) for r in rivals}
        assert len(keys) == n, "no hero rival should be picked twice in one encounter"
        assert all(r in RECRUITABLE_ROSTER for r in rivals)
    print("test_choose_hero_rivals_respects_bounds_and_uniqueness: PASS")


def test_choose_hero_rivals_rarity_weights_favor_common_over_mythic():
    """Same shape as tests/summon_test.py's rarity-weight check -- hero rivals
    reuse the exact same HERO_SUMMON_WEIGHTS curve, so common should dominate
    and mythic should be rare across enough draws."""
    rng = random.Random(11)
    counts = Counter()
    for _ in range(3000):
        rival = choose_hero_rivals(1, rng=rng)[0]
        counts[rival.rarity] += 1
    assert counts["common"] > counts["rare"] > counts["epic"] > counts["legendary"] > counts["mythic"] > 0
    print(f"test_choose_hero_rivals_rarity_weights_favor_common_over_mythic: PASS ({dict(counts)})")


def test_build_hero_enemy_combatant_uses_class_kit_and_growth():
    recruit = next(r for r in RECRUITABLE_ROSTER if r.class_id == "mage")
    archetype = CLASS_ARCHETYPES["mage"]

    lvl1 = build_hero_enemy_combatant(recruit, 1)
    assert lvl1.base_stats == archetype.base_stats
    assert lvl1.is_enemy is True
    assert lvl1.name == f"Rival {recruit.name}", "must be visually distinguishable from an owned party member"
    assert lvl1.skill_ids == archetype.skill_ids
    assert lvl1.persona == HERO_ENEMY_PERSONAS["mage"]
    assert lvl1.resistances == {}

    lvl6 = build_hero_enemy_combatant(recruit, 6)
    assert lvl6.base_stats.max_hp == archetype.base_stats.max_hp + archetype.growth.max_hp * 5
    print("test_build_hero_enemy_combatant_uses_class_kit_and_growth: PASS")


def test_build_battle_can_field_hero_rivals_tracked_parallel_to_enemies():
    """Runs build_battle enough times (fixed rng, varying opponent counts) to
    see both monster-only and at-least-one-rival encounters, and checks that
    enemy_hero_recruits always lines up with enemies/enemy_ids -- None for a
    monster slot, the matching RecruitableHero for a rival slot."""
    party = [PlayerCharacter(name="Solo", class_id="tank", level=5)]
    rng = random.Random(42)
    saw_a_rival = False
    for _ in range(200):
        setup = build_battle(party, EQUIPMENT, "normal", 4, rng=rng)
        assert len(setup.enemy_hero_recruits) == len(setup.enemies) == len(setup.enemy_ids) == 4
        assert len(set(setup.enemy_ids)) == 4, "monster ids and hero ids must never collide"
        for eid, enemy, recruit in zip(setup.enemy_ids, setup.enemies, setup.enemy_hero_recruits):
            assert enemy.is_enemy is True and enemy.alive
            if recruit is None:
                assert eid in ENEMY_IDS
                assert not enemy.name.startswith("Rival ")
            else:
                assert eid.startswith("hero::")
                assert enemy.name == f"Rival {recruit.name}"
                saw_a_rival = True
    assert saw_a_rival, f"expected at least one hero rival across 800 opponent slots at chance={HERO_ENEMY_CHANCE}"
    print("test_build_battle_can_field_hero_rivals_tracked_parallel_to_enemies: PASS")


def main():
    test_enemy_pool_has_13_valid_archetypes()
    test_original_three_enemies_kept_their_exact_legacy_stats()
    test_party_average_level()
    test_compute_enemy_level_matches_andrews_offsets()
    test_compute_enemy_level_never_goes_below_1_or_past_max_level()
    test_compute_enemy_level_rejects_unknown_difficulty()
    test_choose_enemy_ids_respects_bounds_and_uniqueness()
    test_build_enemy_combatant_applies_growth()
    test_build_battle_end_to_end()
    test_difficulty_reward_modifiers_match_andrews_spec()
    test_hero_enemy_personas_cover_every_class()
    test_choose_hero_rivals_respects_bounds_and_uniqueness()
    test_choose_hero_rivals_rarity_weights_favor_common_over_mythic()
    test_build_hero_enemy_combatant_uses_class_kit_and_growth()
    test_build_battle_can_field_hero_rivals_tracked_parallel_to_enemies()
    print("\nALL BATTLE SETUP / ENEMY POOL TESTS PASSED")


if __name__ == "__main__":
    main()

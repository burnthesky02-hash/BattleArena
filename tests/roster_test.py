"""Covers the new meta-progression data model introduced for character
creation / gear: data/classes.py's archetypes, game/roster.py's
PlayerCharacter (the persistent character record, distinct from
engine.combatant.Combatant which is battle-scoped and resets every time
one's constructed), and the equipment stat-bonus math.

Run directly: python3 tests/roster_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.classes import CLASS_ARCHETYPES, CLASS_IDS
from data.equipment_db import EQUIPMENT
from data.skills_db import SKILLS
from engine.types import ActionType
from game.roster import PlayerCharacter


def test_every_class_kit_only_uses_real_skill_ids():
    for class_id, archetype in CLASS_ARCHETYPES.items():
        assert archetype.skill_ids, f"{class_id} has an empty skill kit"
        for skill_id in archetype.skill_ids:
            assert skill_id in SKILLS, f"{class_id}'s kit references unknown skill {skill_id!r}"
    print("test_every_class_kit_only_uses_real_skill_ids: PASS")


def test_all_five_archetypes_exist_and_are_distinct():
    assert set(CLASS_IDS) == {"tank", "melee_dps", "ranged_dps", "mage", "support"}
    assert set(CLASS_ARCHETYPES) == set(CLASS_IDS)
    kits = [tuple(sorted(a.skill_ids)) for a in CLASS_ARCHETYPES.values()]
    assert len(set(kits)) == len(kits), "two classes ended up with identical skill kits"
    print("test_all_five_archetypes_exist_and_are_distinct: PASS")


def test_unknown_class_id_is_rejected():
    try:
        PlayerCharacter(name="Bad", class_id="necromancer")
        raise AssertionError("expected ValueError for an unknown class_id")
    except ValueError:
        print("test_unknown_class_id_is_rejected: PASS")


def test_build_combatant_uses_the_archetypes_kit_and_stats():
    hero = PlayerCharacter(name="Ari", class_id="mage")
    combatant = hero.build_combatant(EQUIPMENT)
    archetype = CLASS_ARCHETYPES["mage"]
    assert combatant.name == "Ari"
    assert combatant.is_enemy is False
    assert sorted(combatant.skill_ids) == sorted(archetype.skill_ids)
    assert combatant.max_hp == archetype.base_stats.max_hp
    assert combatant.hp == combatant.max_hp, "a freshly built combatant should start at full HP"
    print("test_build_combatant_uses_the_archetypes_kit_and_stats: PASS")


def test_equipment_bonuses_apply_on_top_of_base_stats():
    hero = PlayerCharacter(name="Tor", class_id="tank")
    base_atk = CLASS_ARCHETYPES["tank"].base_stats.atk
    assert hero.equipped == {"weapon": None, "armor": None, "accessory": None}

    previous = hero.equip("rusty_sword", EQUIPMENT)  # +4 atk
    assert previous is None, "nothing was equipped there before"
    stats = hero.effective_stats(EQUIPMENT)
    assert stats.atk == base_atk + 4, (stats.atk, base_atk)

    previous = hero.equip("knights_blade", EQUIPMENT)  # +8 atk, +2 def_ -- replaces rusty_sword
    assert previous == "rusty_sword"
    stats = hero.effective_stats(EQUIPMENT)
    assert stats.atk == base_atk + 8, "swapping weapons should replace, not stack, the old bonus"

    combatant = hero.build_combatant(EQUIPMENT)
    assert combatant.base_stats.atk == base_atk + 8, "build_combatant must use effective_stats, not raw base_stats"
    print("test_equipment_bonuses_apply_on_top_of_base_stats: PASS")


def test_new_character_starts_at_level_1_with_zero_xp():
    """Summon recruits (and any freshly-created PlayerCharacter) start at
    level 1 -- confirmed with Andrew via AskUserQuestion during the
    level-curve pass, so newly recruited teammates always start weak and
    have to catch up rather than joining pre-leveled."""
    hero = PlayerCharacter(name="Newbie", class_id="ranged_dps")
    assert hero.level == 1
    assert hero.xp == 0
    print("test_new_character_starts_at_level_1_with_zero_xp: PASS")


def test_grant_xp_levels_up_and_carries_remainder():
    hero = PlayerCharacter(name="Grower", class_id="melee_dps")
    # xp_for_next_level(1) == 40 (data/leveling.py) -- 39 isn't quite enough.
    gained = hero.grant_xp(39)
    assert gained == 0 and hero.level == 1 and hero.xp == 39

    gained = hero.grant_xp(1)  # crosses the 40 threshold exactly
    assert gained == 1 and hero.level == 2 and hero.xp == 0

    # A single big grant can cross more than one threshold: level 2 needs 60
    # more, level 3 needs 80 more -- 60 + 80 + 5 leftover = 145.
    gained = hero.grant_xp(145)
    assert gained == 2 and hero.level == 4 and hero.xp == 5, (gained, hero.level, hero.xp)
    print("test_grant_xp_levels_up_and_carries_remainder: PASS")


def test_effective_stats_applies_growth_before_equipment():
    archetype = CLASS_ARCHETYPES["melee_dps"]
    hero = PlayerCharacter(name="Leveled", class_id="melee_dps")
    hero.grant_xp(40)  # -> level 2, one level of growth applied
    assert hero.level == 2

    stats = hero.effective_stats(EQUIPMENT)
    assert stats.atk == archetype.base_stats.atk + archetype.growth.atk
    assert stats.max_hp == archetype.base_stats.max_hp + archetype.growth.max_hp

    hero.equip("rusty_sword", EQUIPMENT)  # +4 atk, applies on top of the grown stat
    stats = hero.effective_stats(EQUIPMENT)
    assert stats.atk == archetype.base_stats.atk + archetype.growth.atk + 4
    print("test_effective_stats_applies_growth_before_equipment: PASS")


def test_level_is_clamped_between_1_and_max_level():
    from data.leveling import MAX_LEVEL
    low = PlayerCharacter(name="TooLow", class_id="tank", level=0)
    assert low.level == 1
    high = PlayerCharacter(name="TooHigh", class_id="tank", level=MAX_LEVEL + 50)
    assert high.level == MAX_LEVEL
    print("test_level_is_clamped_between_1_and_max_level: PASS")


def test_new_character_defaults_to_common_rarity_and_1_star():
    """A fresh PlayerCharacter -- whether from character creation or a
    summon recruit whose rarity wasn't given -- starts at 1 star (0% bonus,
    confirmed by test_effective_stats_applies_growth_before_equipment above
    passing unchanged) with no banked shards."""
    hero = PlayerCharacter(name="Newbie", class_id="tank")
    assert hero.rarity == "common"
    assert hero.stars == 1
    assert hero.shards == 0
    print("test_new_character_defaults_to_common_rarity_and_1_star: PASS")


def test_unknown_rarity_is_rejected():
    try:
        PlayerCharacter(name="Bad", class_id="tank", rarity="ultra")
        raise AssertionError("expected ValueError for an unknown rarity")
    except ValueError:
        print("test_unknown_rarity_is_rejected: PASS")


def test_stars_are_clamped_between_1_and_max_stars():
    from data.hero_rarity import MAX_STARS
    low = PlayerCharacter(name="TooLow", class_id="tank", stars=0)
    assert low.stars == 1
    high = PlayerCharacter(name="TooHigh", class_id="tank", stars=MAX_STARS + 10)
    assert high.stars == MAX_STARS
    print("test_stars_are_clamped_between_1_and_max_stars: PASS")


def test_negative_shards_are_clamped_to_zero():
    hero = PlayerCharacter(name="Odd", class_id="tank", shards=-5)
    assert hero.shards == 0
    print("test_negative_shards_are_clamped_to_zero: PASS")


def test_star_level_scales_stats_multiplicatively_before_equipment():
    """5 stars = the max +32% (4 upgrades * 8%, see data/hero_rarity.py) on
    top of leveled base stats, applied before equipment's flat bonuses --
    equipment gear numbers shouldn't silently grow just because the wearer
    got duplicate-upgraded."""
    from data.hero_rarity import MAX_STARS, star_multiplier
    base = PlayerCharacter(name="Base", class_id="melee_dps")
    starred = PlayerCharacter(name="Starred", class_id="melee_dps", stars=MAX_STARS)
    base_stats = base.effective_stats(EQUIPMENT)
    starred_stats = starred.effective_stats(EQUIPMENT)
    mult = star_multiplier(MAX_STARS)
    assert mult == 1.32
    assert starred_stats.max_hp == round(base_stats.max_hp * mult)
    assert starred_stats.atk == round(base_stats.atk * mult)

    # Equipment bonuses are flat on top -- not scaled by stars.
    starred.equip("rusty_sword", EQUIPMENT)  # +4 atk
    with_gear = starred.effective_stats(EQUIPMENT)
    assert with_gear.atk == starred_stats.atk + 4
    print("test_star_level_scales_stats_multiplicatively_before_equipment: PASS")


def test_missing_equipment_id_in_a_slot_is_skipped_not_fatal():
    """A save file could reference gear from a since-removed catalog entry
    (or, in tests, a made-up id) -- effective_stats should tolerate that
    rather than crashing the whole character/battle setup over one bad id."""
    hero = PlayerCharacter(name="Odd", class_id="support", equipped={"weapon": "does_not_exist", "armor": None, "accessory": None})
    stats = hero.effective_stats(EQUIPMENT)  # must not raise
    assert stats.atk == CLASS_ARCHETYPES["support"].base_stats.atk
    print("test_missing_equipment_id_in_a_slot_is_skipped_not_fatal: PASS")


def main():
    test_every_class_kit_only_uses_real_skill_ids()
    test_all_five_archetypes_exist_and_are_distinct()
    test_unknown_class_id_is_rejected()
    test_build_combatant_uses_the_archetypes_kit_and_stats()
    test_equipment_bonuses_apply_on_top_of_base_stats()
    test_new_character_starts_at_level_1_with_zero_xp()
    test_grant_xp_levels_up_and_carries_remainder()
    test_effective_stats_applies_growth_before_equipment()
    test_level_is_clamped_between_1_and_max_level()
    test_new_character_defaults_to_common_rarity_and_1_star()
    test_unknown_rarity_is_rejected()
    test_stars_are_clamped_between_1_and_max_stars()
    test_negative_shards_are_clamped_to_zero()
    test_star_level_scales_stats_multiplicatively_before_equipment()
    test_missing_equipment_id_in_a_slot_is_skipped_not_fatal()
    print("\nALL ROSTER/EQUIPMENT TESTS PASSED")


if __name__ == "__main__":
    main()

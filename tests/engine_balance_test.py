"""Unit-level checks for engine mechanics that headless_battle_test.py's full
random battles can't reliably exercise or verify precisely (a status effect
might not get applied/rolled in any given seeded battle, and its exact tick
damage isn't something you'd want to assert against noisy full-battle logs).
These construct a BattleEngine directly and drive it with explicit Action
objects instead, so each mechanic can be checked in isolation.

Covers two real bugs found and fixed during a balance-tuning pass:
  - poison and regen previously had `dot_damage=0` baked into STATUS_DB with
    a comment claiming it was "computed dynamically" -- except nothing
    actually computed it anywhere, so both effects were silently inert (the
    status was applied and logged, but ticked zero damage/healing every
    turn). This mattered for balance: Bandit Rogue's whole "poisons
    tough-looking targets to whittle them down over time" persona was doing
    nothing.
  - a new `Skill.lifesteal` field (used by the new Life Drain skill) needed
    verifying end to end: caster HP should actually go up by a share of the
    damage dealt.

Run directly: python3 tests/engine_balance_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.actions import Action
from engine.battle import BattleEngine
from engine.combatant import Combatant
from engine.stats import Stats
from engine.skills import Skill
from engine.types import TargetType, Element
from data.skills_db import SKILLS
from data.items_db import ITEMS, STARTING_INVENTORY


def _make_pair(attacker_extra_skills=None):
    """A minimal one-vs-one setup so a single skill's effect is easy to isolate."""
    attacker = Combatant(
        name="Attacker", is_enemy=True,
        base_stats=Stats(max_hp=100, max_mp=50, atk=20, def_=10, mag=20, res=10, spd=10, luk=0),
        skill_ids=list(attacker_extra_skills or []),
    )
    defender = Combatant(
        name="Defender", is_enemy=False,
        base_stats=Stats(max_hp=200, max_mp=50, atk=10, def_=5, mag=5, res=5, spd=10, luk=0),
    )
    engine = BattleEngine(
        party=[defender], enemies=[attacker], skills_db=SKILLS, items_db=ITEMS,
        inventory=dict(STARTING_INVENTORY),
        get_party_action=lambda c, s: Action.defend(c.id),
        get_enemy_action=lambda c, s: Action.defend(c.id),
    )
    return engine, attacker, defender


def test_poison_actually_deals_damage_over_time():
    engine, attacker, defender = _make_pair(["poison_dart"])
    # Force the status roll to land regardless of poison_dart's 0.75 chance,
    # by looping resolve_action until it's actually applied (bounded so a real
    # regression -- e.g. the roll never landing at all -- still fails loudly
    # instead of hanging).
    applied = False
    for _ in range(50):
        defender.hp = defender.max_hp
        defender.status_effects = []
        engine.resolve_action(Action.use_skill(attacker.id, "poison_dart", [defender.id]))
        if defender.has_status("poison"):
            applied = True
            break
    assert applied, "poison_dart never applied Poison in 50 tries -- status roll or targeting broke"

    hp_before = defender.hp
    events = defender.tick_statuses()
    assert defender.hp < hp_before, (
        f"poison ticked for zero damage (hp stayed at {defender.hp}) -- this is exactly the "
        f"dot_damage=0 bug: STATUS_DB entries don't carry their own tick amount, it must be "
        f"computed where the status is applied (see engine/battle.py's _do_skill)."
    )
    assert any("Poison" in e for e in events), events
    print(f"test_poison_actually_deals_damage_over_time: PASS (ticked {hp_before - defender.hp} damage)")


def test_regen_actually_heals_over_time():
    engine, attacker, defender = _make_pair()
    defender.hp = 50  # damaged, so healing has room to show up
    status_skill = Skill(id="_test_regen", name="Test Regen", mp_cost=0, power=0.0, kind="status",
                          target=TargetType.SINGLE_ALLY, status_to_apply="regen", status_chance=1.0)
    engine.skills_db = dict(engine.skills_db, **{"_test_regen": status_skill})
    engine.resolve_action(Action.use_skill(defender.id, "_test_regen", [defender.id]))
    assert defender.has_status("regen")

    hp_before = defender.hp
    events = defender.tick_statuses()
    assert defender.hp > hp_before, f"regen ticked for zero healing (hp stayed at {defender.hp})"
    assert any("regenerates" in e for e in events), events
    print(f"test_regen_actually_heals_over_time: PASS (ticked {defender.hp - hp_before} healing)")


def test_lifesteal_heals_the_caster():
    engine, attacker, defender = _make_pair(["life_drain"])
    attacker.hp = 40  # damaged, so lifesteal healing has room to show up
    hp_before = attacker.hp
    engine.resolve_action(Action.use_skill(attacker.id, "life_drain", [defender.id]))
    assert defender.hp < defender.max_hp, "life_drain dealt no damage to the target"
    assert attacker.hp > hp_before, (
        f"life_drain has lifesteal={SKILLS['life_drain'].lifesteal} but the caster's HP "
        f"didn't increase (stayed at {attacker.hp}) -- lifesteal isn't wired up in _do_skill"
    )
    print(f"test_lifesteal_heals_the_caster: PASS (attacker healed from {hp_before} to {attacker.hp})")


def main():
    test_poison_actually_deals_damage_over_time()
    test_regen_actually_heals_over_time()
    test_lifesteal_heals_the_caster()
    print("\nALL ENGINE BALANCE TESTS PASSED")


if __name__ == "__main__":
    main()

"""Unit tests for the rule-based enemy AI (ai/enemy_ai.py): legal targeting, behavior profiles,
telegraphed charges and how a stun breaks them, healing, rival adaptation and full battles.

    python3 tests/enemy_ai_test.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.enemy_ai import (CHARGE_STATUS, decay_memory, make_enemy_ai_fn, new_rival_memory,
                         profile_for, scripted_fallback_action)
from data.characters import make_party
from data.items_db import ITEMS, STARTING_INVENTORY
from data.skills_db import SKILLS
from engine.actions import Action
from engine.battle import BattleEngine
from engine.status_effects import get_status
from engine.types import ActionType, BattleResult
from game.battle_setup import build_enemy_combatant


def _engine(enemy_ids, party=None):
    enemies = [build_enemy_combatant(e, 10) for e in enemy_ids]
    return BattleEngine(party=party or make_party(), enemies=enemies, skills_db=SKILLS, items_db=ITEMS,
                        inventory=dict(STARTING_INVENTORY),
                        get_party_action=lambda c, s: Action.defend(c.id),
                        get_enemy_action=lambda c, s: Action.defend(c.id)), enemies


def test_profiles_resolve():
    assert profile_for(build_enemy_combatant("iron_golem", 5)).get("charge") == "crushing_blow"
    assert profile_for(build_enemy_combatant("phase_hound", 5))["target"] == "weakest"
    assert profile_for(build_enemy_combatant("null_reaper", 5)).get("adaptive")
    print("test_profiles_resolve: PASS")


def test_melee_only_hits_front_row():
    engine, enemies = _engine(["iron_golem"])
    for p in engine.party:
        p.formation = "rear"
    engine.party[0].formation = "front"
    ai = make_enemy_ai_fn(rng=random.Random(1))
    for _ in range(60):
        state = engine.build_state(for_actor=enemies[0])
        act = ai(enemies[0], state)
        for tid in act.target_ids:
            if act.type == ActionType.ATTACK or SKILLS[act.skill_id].target.value == "single_enemy":
                assert tid == engine.party[0].id, "melee unit reached past the front row"
    print("test_melee_only_hits_front_row: PASS")


def test_medic_heals_wounded_squadmate():
    engine, enemies = _engine(["lattice_medic", "iron_golem"])
    enemies[1].hp = int(enemies[1].max_hp * 0.2)
    enemies[0].mp = enemies[0].max_mp
    ai = make_enemy_ai_fn(rng=random.Random(3))
    healed = 0
    for _ in range(20):
        act = ai(enemies[0], engine.build_state(for_actor=enemies[0]))
        if act.type == ActionType.SKILL and SKILLS[act.skill_id].kind == "heal" and enemies[1].id in act.target_ids:
            healed += 1
    assert healed >= 14, f"medic only healed the wounded golem {healed}/20 times"
    print("test_medic_heals_wounded_squadmate: PASS")


def test_opener_used_first():
    engine, enemies = _engine(["colosseum_champion"])
    ai = make_enemy_ai_fn(rng=random.Random(5))
    act = ai(enemies[0], engine.build_state(for_actor=enemies[0]))
    assert act.type == ActionType.SKILL and act.skill_id == "warcry", act
    print("test_opener_used_first: PASS")


def test_charge_telegraph_release_and_stun_break():
    engine, enemies = _engine(["iron_golem"])
    golem = enemies[0]
    golem.mp = golem.max_mp
    records = []
    import ai.enemy_ai as mod
    old = mod.CHARGE_CHANCE
    mod.CHARGE_CHANCE = 1.0
    try:
        ai = make_enemy_ai_fn(on_decision=records.append, rng=random.Random(7))
        engine.round_number = 2
        act = ai(golem, engine.build_state(for_actor=golem))
        assert act.type == ActionType.DEFEND and golem.has_status(CHARGE_STATUS)
        assert records and records[0]["phase"] == "telegraph" and "gathers power" in records[0]["message"]
        atk_before = golem.effective_stat("atk")
        assert atk_before > golem.base_stats.atk * 1.5

        engine.round_number = 3
        act = ai(golem, engine.build_state(for_actor=golem))
        assert act.type == ActionType.SKILL and act.skill_id == "crushing_blow", act
        assert golem.has_status(CHARGE_STATUS)           # still boosted while the hit lands

        engine.round_number = 4                          # the turn after the release clears the boost
        ai(golem, engine.build_state(for_actor=golem))
        assert not golem.has_status(CHARGE_STATUS)

        # A stunned turn (the AI is never called) breaks a fresh charge.
        golem.remove_status(CHARGE_STATUS)
        golem.mp = golem.max_mp
        engine.round_number = 8
        ai2 = make_enemy_ai_fn(on_decision=records.append, rng=random.Random(9))
        ai2(golem, engine.build_state(for_actor=golem))
        assert golem.has_status(CHARGE_STATUS)
        engine.round_number = 10                        # skipped round 9 (stunned) -> too late
        ai2(golem, engine.build_state(for_actor=golem))
        assert not golem.has_status(CHARGE_STATUS), "stale charge should fizzle"
        assert any(r["phase"] == "interrupt" for r in records)
    finally:
        mod.CHARGE_CHANCE = old
    print("test_charge_telegraph_release_and_stun_break: PASS")


def test_rival_hunts_the_healer():
    engine, enemies = _engine(["colosseum_champion"])
    champ = enemies[0]
    champ.mp = 0                                        # force basic attacks so targeting is visible
    ai = make_enemy_ai_fn(rng=random.Random(11))
    healer = engine.party[-1]
    for _ in range(3):
        ai.observe(healer, Action.use_skill(healer.id, "heal", [engine.party[0].id]))
    assert ai.memory["heals_by"][healer.name] == 3
    for p in engine.party:
        p.formation = "front"
    hits = 0
    for _ in range(40):
        state = engine.build_state(for_actor=champ)
        act = ai(champ, state)
        if act.type == ActionType.ATTACK and act.target_ids[0] == healer.id:
            hits += 1
    baseline = make_enemy_ai_fn(memory=new_rival_memory(), rng=random.Random(11))
    base_hits = sum(1 for _ in range(40)
                    if (lambda a: a.type == ActionType.ATTACK and a.target_ids[0] == healer.id)(
                        baseline(champ, engine.build_state(for_actor=champ))))
    assert hits > base_hits, f"adapted rival should favor the healer more ({hits} vs {base_hits})"
    decay_memory(ai.memory)
    assert ai.memory["heals_by"][healer.name] == 1.5
    print("test_rival_hunts_the_healer: PASS")


def test_full_battles_complete():
    for seed in range(12):
        random.seed(seed)
        engine, _ = _engine(["iron_golem", "lattice_medic", "frost_mirage"])
        ai = make_enemy_ai_fn()
        engine.get_enemy_action = ai
        engine.get_party_action = lambda c, s: Action.attack(c.id, next(e["id"] for e in s["enemies"] if e["alive"]))
        result = engine.run()
        assert result in (BattleResult.VICTORY, BattleResult.DEFEAT)
    print("test_full_battles_complete: PASS")


if __name__ == "__main__":
    test_profiles_resolve()
    test_melee_only_hits_front_row()
    test_medic_heals_wounded_squadmate()
    test_opener_used_first()
    test_charge_telegraph_release_and_stun_break()
    test_rival_hunts_the_healer()
    test_full_battles_complete()
    print("ALL PASS")

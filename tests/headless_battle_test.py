"""Headless correctness test for the battle engine.

Runs many full battles with NO pygame and NO real Ollama server (none is
reachable from this sandbox), using:
  - a scripted stand-in for the human player (exercises attack/skill/item/defend)
  - the REAL enemy AI pipeline (ai.enemy_ai.make_enemy_ai_fn) pointed at an
    unreachable Ollama host, which forces every single enemy decision through
    the scripted fallback path -- so this also proves the "Ollama is down"
    failure mode never crashes or hangs a battle.

This is a sanity/integration check, not a formal test suite -- run it with:
    python3 tests/headless_battle_test.py
"""
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.battle import BattleEngine
from engine.actions import Action
from engine.types import BattleResult
from data.skills_db import SKILLS
from data.items_db import ITEMS, STARTING_INVENTORY
from data.characters import make_party
from data.enemies import make_enemy_group
from ai.ollama_client import OllamaClient
from ai.enemy_ai import make_enemy_ai_fn, scripted_fallback_action, _parse_llm_action


def scripted_party_action(combatant, state: dict) -> Action:
    """A simple heuristic stand-in for a human player, used to drive the party
    side in this headless test (the real game uses TextUI/PygameUI instead)."""
    party_alive = [p for p in state["party"] if p["alive"]]
    enemies_alive = [e for e in state["enemies"] if e["alive"]]
    skills = state.get("available_skills", [])
    items = state.get("available_items", [])

    critical_ally = min(party_alive, key=lambda p: p["hp"] / p["max_hp"]) if party_alive else None

    # 1) Heal a critically-low ally if we have a heal skill and MP for it.
    if critical_ally and critical_ally["hp"] / critical_ally["max_hp"] < 0.35:
        heal_skills = [s for s in skills if s["kind"] == "heal" and s["mp_cost"] <= combatant.mp]
        if heal_skills:
            skill = heal_skills[0]
            target_ids = [p["id"] for p in party_alive] if skill["target"] == "all_allies" else [critical_ally["id"]]
            return Action.use_skill(combatant.id, skill["id"], target_ids)
        healing_items = [i for i in items if ITEMS[i["id"]].heal_hp > 0 and not ITEMS[i["id"]].revive]
        if healing_items:
            return Action.use_item(combatant.id, healing_items[0]["id"], [critical_ally["id"]])

    # 2) Revive a KO'd ally if possible.
    ko_allies = [p for p in state["party"] if not p["alive"]]
    if ko_allies:
        revive_items = [i for i in items if ITEMS[i["id"]].revive]
        if revive_items:
            return Action.use_item(combatant.id, revive_items[0]["id"], [ko_allies[0]["id"]])

    if not enemies_alive:
        return Action.defend(combatant.id)

    lowest_hp_enemy = min(enemies_alive, key=lambda e: e["hp"])

    # 3) Sometimes use an offensive/status skill.
    offensive = [s for s in skills if s["mp_cost"] <= combatant.mp and s["kind"] != "heal"]
    if offensive and random.random() < 0.6:
        skill = random.choice(offensive)
        if skill["target"] == "self":
            target_ids = [combatant.id]
        elif skill["target"] == "all_enemies":
            target_ids = [e["id"] for e in enemies_alive]
        else:
            target_ids = [lowest_hp_enemy["id"]]
        return Action.use_skill(combatant.id, skill["id"], target_ids)

    # 4) Otherwise basic attack.
    return Action.attack(combatant.id, lowest_hp_enemy["id"])


def run_one_battle(seed: int) -> BattleEngine:
    random.seed(seed)
    client = OllamaClient(host="http://localhost:1", model="does-not-matter", timeout=0.5)
    get_enemy_action = make_enemy_ai_fn(client, use_fallback_on_error=True)

    engine = BattleEngine(
        party=make_party(),
        enemies=make_enemy_group(),
        skills_db=SKILLS,
        items_db=ITEMS,
        inventory=dict(STARTING_INVENTORY),
        get_party_action=scripted_party_action,
        get_enemy_action=get_enemy_action,
        on_event=None,
    )
    result = engine.run()
    assert result in (BattleResult.VICTORY, BattleResult.DEFEAT, BattleResult.FLED), f"unexpected result {result}"
    assert engine.round_number <= 100

    for c in engine.all_combatants():
        assert c.hp >= 0, f"{c.name} has negative HP ({c.hp})"
        assert c.hp <= c.max_hp, f"{c.name} HP exceeds max ({c.hp}/{c.max_hp})"
        assert c.mp >= 0, f"{c.name} has negative MP ({c.mp})"

    for item_id, count in engine.inventory.items():
        assert count >= 0, f"inventory for {item_id} went negative ({count})"

    return engine


def test_fallback_ai_unit():
    """Unit-level check of the scripted fallback AI and LLM-response parser
    without needing a network call at all."""
    party = make_party()
    enemies = make_enemy_group()
    engine = BattleEngine(
        party=party, enemies=enemies, skills_db=SKILLS, items_db=ITEMS,
        inventory=dict(STARTING_INVENTORY),
        get_party_action=scripted_party_action, get_enemy_action=lambda c, s: Action.defend(c.id),
    )
    actor = enemies[0]
    state = engine.build_state(for_actor=actor)

    action = scripted_fallback_action(actor, state)
    assert isinstance(action, Action)

    # A well-formed "LLM" response should parse into a skill action.
    skill_id = state["available_skills"][0]["id"]
    target_id = state["party"][0]["id"]
    parsed = _parse_llm_action(actor, state, {"action": "skill", "skill_id": skill_id, "target_id": target_id})
    assert parsed.type.value == "skill" and parsed.skill_id == skill_id

    # A malformed skill_id should degrade to a basic attack rather than raising.
    parsed_bad = _parse_llm_action(actor, state, {"action": "skill", "skill_id": "nonsense", "target_id": target_id})
    assert parsed_bad.type.value == "attack"

    # Total gibberish should raise ValueError, which enemy_ai's try/except turns into a fallback.
    try:
        _parse_llm_action(actor, state, {"action": "moonwalk"})
        raise AssertionError("expected ValueError for unrecognized action")
    except ValueError:
        pass

    print("test_fallback_ai_unit: PASS")


def main():
    test_fallback_ai_unit()

    # 150 battles, not 25 -- a win-rate *band* (rather than just "won at least
    # once") needs enough samples to not be noise. See README's "Balance"
    # section for how this number was tuned: the original roster had the
    # party winning ~100% of the time (turn-economy alone, 4 party members'
    # actions per round vs. 3 enemies', plus a couple of easily-exploited
    # elemental weaknesses, let the party end fights in a handful of rounds
    # before its generous healing/item buffer was ever really tested).
    # Tuned enemy stats now land around an 80% party win rate against this
    # deliberately-simpler-than-real scripted fallback AI -- real losses are
    # possible, most fights are still winnable, and the actual local-LLM
    # enemy AI in real play should be smarter than this heuristic, adding
    # more pressure on top rather than less.
    n_battles = 150
    outcomes = {"victory": 0, "defeat": 0, "fled": 0}
    max_round_seen = 0
    for seed in range(n_battles):
        engine = run_one_battle(seed)
        outcomes[engine.result.value] += 1
        max_round_seen = max(max_round_seen, engine.round_number)

    win_rate = outcomes["victory"] / n_battles
    print(f"Ran {n_battles} full headless battles with no crashes.")
    print(f"Outcomes: {outcomes} (party win rate: {win_rate:.0%})")
    print(f"Longest battle: {max_round_seen} rounds")
    assert outcomes["victory"] + outcomes["defeat"] + outcomes["fled"] == n_battles
    # Sanity band, not a precise target: enough losses to prove enemies are a
    # real threat, but the party (playing a reasonable, if scripted, strategy)
    # should still win more often than not against the *fallback* AI.
    assert 0.55 <= win_rate <= 0.95, (
        f"party win rate {win_rate:.0%} is outside the intended 55-95% band -- "
        f"enemies are either too weak (party always wins) or too strong "
        f"(the battle no longer feels winnable); see data/enemies.py."
    )
    print("\nALL HEADLESS BATTLE TESTS PASSED")


if __name__ == "__main__":
    main()

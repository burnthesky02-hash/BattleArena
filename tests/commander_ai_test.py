"""Verifies the "commander" prompt framing: the model should be told to
direct one member of a squad it commands (with visibility into its
squadmates' current standing), not to roleplay as that member in isolation.

This was a deliberate, lower-risk choice over a single "one call per round
plans the whole squad" architecture (which would need one Ollama call for
all enemies together, more complex parsing, and a fallback that covers the
full squad if that one call fails) -- here every enemy turn still makes its
own call, same as before, but the prompt now frames the model as the
commander directing that one unit with squad awareness rather than as the
unit itself. See ai/enemy_ai.py's module docstring for the tradeoff.

Also covers a follow-up fix: Andrew reported the model "doesn't seem to have
an understanding of which characters its controlling and which characters
its fighting against in the beginning." The likely cause was the payload key
"party_side_targets" -- in JRPG parlance "the party" almost always means the
player's *own* team, which is backwards here (the humans are the commander's
*target*, not its team), and that naming collision had the least context to
be overridden by on an early turn, before recent_log has anything in it. The
fix: rename that key to "human_party_targets", and add a plain-English
preamble sentence (outside the JSON) naming the squad and the opposing party
explicitly, every turn, independent of log state.

Separately, also covers a graceful-degrade fix for the "MP so skills can't be
spammed" request: MP cost/deduction already existed in the engine (it was
never unlimited), but a model that misjudged its own MP and asked for a
skill it couldn't afford used to waste the *entire* turn once the engine
rejected it (the unit "hesitates"). Now that degrades to a basic attack
instead, same as an invalid/unknown skill_id already did.

Checks:
  - SYSTEM_PROMPT talks about commanding a squad and issuing orders, not
    "you are this monster" / "stay in character as".
  - _build_user_prompt's JSON payload uses "acting_unit_*" keys for the unit
    the order is for, and a "rest_of_your_squad" list of the *other* living
    enemies (excluding the acting unit itself) so the commander has
    squad-wide visibility when deciding this one order.
  - The old "party_side_targets" key is gone, replaced by
    "human_party_targets", and the prompt's plain-text preamble names both
    the squad and the opposing party explicitly (not just via JSON keys).
  - recent_log (where a teammate's already-taken action this round would
    show up) is still included.
  - _parse_llm_action degrades an unaffordable skill request to a basic
    attack instead of letting the turn get wasted by the engine's MP check.

Run directly: python3 tests/commander_ai_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.enemy_ai import SYSTEM_PROMPT, _build_user_prompt, _parse_llm_action
from data.characters import make_party
from data.enemies import make_enemy_group
from data.skills_db import SKILLS
from data.items_db import ITEMS, STARTING_INVENTORY
from engine.actions import Action
from engine.types import ActionType
from engine.battle import BattleEngine


def test_system_prompt_frames_a_commander_not_a_roleplaying_monster():
    lowered = SYSTEM_PROMPT.lower()
    assert "commander" in lowered and "squad" in lowered, "prompt should frame the model as directing a squad"
    assert "stay fully in character" not in lowered, "old roleplay-as-the-monster framing should be gone"
    assert "you are the tactical ai controlling one monster" not in lowered
    print("test_system_prompt_frames_a_commander_not_a_roleplaying_monster: PASS")


def test_user_prompt_gives_squad_visibility_for_the_acting_unit():
    party = make_party()
    enemies = make_enemy_group()
    engine = BattleEngine(
        party=party, enemies=enemies, skills_db=SKILLS, items_db=ITEMS,
        inventory=dict(STARTING_INVENTORY),
        get_party_action=lambda c, s: Action.defend(c.id), get_enemy_action=lambda c, s: Action.defend(c.id),
    )
    acting_unit = enemies[0]
    state = engine.build_state(for_actor=acting_unit)
    prompt = _build_user_prompt(acting_unit, state)

    json_text = prompt.split("Battle state (JSON):\n", 1)[1].rsplit("\n\nChoose", 1)[0]
    import json
    payload = json.loads(json_text)

    for key in ("acting_unit_id", "acting_unit_name", "acting_unit_tendencies",
                "acting_unit_hp", "acting_unit_max_hp", "acting_unit_mp", "acting_unit_max_mp"):
        assert key in payload, f"missing {key} in commander prompt payload"
    assert payload["acting_unit_id"] == acting_unit.id
    assert payload["acting_unit_name"] == acting_unit.name

    assert "rest_of_your_squad" in payload
    squad_ids = {m["id"] for m in payload["rest_of_your_squad"]}
    assert acting_unit.id not in squad_ids, "the acting unit shouldn't list itself as one of its own squadmates"
    other_enemy_ids = {e.id for e in enemies if e.id != acting_unit.id}
    assert squad_ids == other_enemy_ids, (squad_ids, other_enemy_ids)

    assert "recent_log" in payload  # where an already-acted squadmate's move this round would show up
    assert "your_persona" not in payload and "your_id" not in payload, "old first-person keys should be gone"

    # "party_side_targets" read as "your own party" in JRPG parlance -- the
    # opposite of what it meant here. It must be gone, replaced by a name
    # that can't be misread as "your team" even in isolation.
    assert "party_side_targets" not in payload, "old ambiguous key should be renamed"
    assert "human_party_targets" in payload
    assert {p["id"] for p in payload["human_party_targets"]} == {p.id for p in party}
    print("test_user_prompt_gives_squad_visibility_for_the_acting_unit: PASS")


def test_prompt_names_squad_and_party_in_plain_text_up_front():
    """The JSON keys alone weren't enough to keep a local model from mixing up
    who it commands vs. who it's fighting, especially on an early turn with
    little recent_log to lean on -- so the prompt now also says so in plain
    English, every turn, regardless of log state."""
    party = make_party()
    enemies = make_enemy_group()
    engine = BattleEngine(
        party=party, enemies=enemies, skills_db=SKILLS, items_db=ITEMS,
        inventory=dict(STARTING_INVENTORY),
        get_party_action=lambda c, s: Action.defend(c.id), get_enemy_action=lambda c, s: Action.defend(c.id),
    )
    acting_unit = enemies[0]
    # Round 0, no log yet -- the exact "beginning of battle" situation Andrew reported.
    state = engine.build_state(for_actor=acting_unit)
    assert state["log_tail"] == []
    prompt = _build_user_prompt(acting_unit, state)

    preamble = prompt.split("Battle state (JSON):")[0]
    assert "command" in preamble.lower() and "fighting" in preamble.lower()
    for e in enemies:
        assert e.name in preamble, f"squad member {e.name} should be named in the preamble"
    for p in party:
        assert p.name in preamble, f"opposing party member {p.name} should be named in the preamble"
    print("test_prompt_names_squad_and_party_in_plain_text_up_front: PASS")


def test_unaffordable_skill_request_degrades_to_attack_not_a_wasted_turn():
    """If the model asks for a skill it can no longer pay for, the old behavior
    let that request reach the engine unchanged, which just makes the unit
    "hesitate" and burns the whole turn. That's a worse outcome than the
    already-existing "invalid skill_id" degrade, so it should behave the same
    way: fall back to a basic attack instead of doing nothing."""
    party = make_party()
    enemies = make_enemy_group()
    engine = BattleEngine(
        party=party, enemies=enemies, skills_db=SKILLS, items_db=ITEMS,
        inventory=dict(STARTING_INVENTORY),
        get_party_action=lambda c, s: Action.defend(c.id), get_enemy_action=lambda c, s: Action.defend(c.id),
    )
    acting_unit = enemies[0]  # Iron Golem, max_mp=14
    acting_unit.mp = 2  # not enough for any of its skills (cheapest is 5)
    state = engine.build_state(for_actor=acting_unit)
    expensive_skill = next(s for s in state["available_skills"] if s["mp_cost"] > acting_unit.mp)

    raw = {"action": "skill", "skill_id": expensive_skill["id"], "target_id": party[0].id}
    action = _parse_llm_action(acting_unit, state, raw)
    assert action.type == ActionType.ATTACK, f"expected a graceful attack fallback, got {action.type}"
    print("test_unaffordable_skill_request_degrades_to_attack_not_a_wasted_turn: PASS")


def main():
    test_system_prompt_frames_a_commander_not_a_roleplaying_monster()
    test_user_prompt_gives_squad_visibility_for_the_acting_unit()
    test_prompt_names_squad_and_party_in_plain_text_up_front()
    test_unaffordable_skill_request_degrades_to_attack_not_a_wasted_turn()
    print("\nALL COMMANDER AI PROMPT TESTS PASSED")


if __name__ == "__main__":
    main()

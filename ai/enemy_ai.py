"""Turns battle state into an enemy Action, using a local Ollama model as a
single tactical commander directing the whole enemy squad -- one order at a
time, as each squad member's turn comes up.

Public entry point: make_enemy_ai_fn(client, skills_db) -> a function with
the exact signature BattleEngine.get_enemy_action expects:
    (combatant, state_dict) -> Action

That factory is what main.py wires into the BattleEngine, which keeps this
module decoupled from the engine (it only imports engine.actions/types for
the Action/enum it needs to construct).

Note on "commander" vs. "one call per round": this still makes one Ollama
call per enemy turn (same cadence/speed as before) rather than one call per
round that plans the whole squad's actions at once. What changed is the
*framing*: the model is prompted to reason as a commander issuing this one
order with full visibility into the whole squad's state (not as the monster
itself, roleplaying in isolation), and it can see what the rest of the
squad has already done this round via recent_log. It does NOT get to see
what a not-yet-acted teammate will do later this same round -- that hasn't
been decided yet -- so coordination is "aware of the board and of orders
already given," not "planned out for the whole team in advance."

Follow-up fix: after playing with the commander framing above, the model
would sometimes lose track of which characters it controls vs. which it's
fighting, especially on the very first turn or two of a battle (before
recent_log has anything in it to lean on). The likely cause was the old
"party_side_targets" payload key -- in JRPG parlance "the party" almost
always means the *player's own* team, which is exactly backwards here (the
humans are the commander's target, not its team), and that word carries a
lot of pretrained bias for a model to override from key-naming alone.
_build_user_prompt now (a) calls that field "human_party_targets" instead,
and (b) opens every prompt with a plain-English sentence -- outside the
JSON entirely -- naming the squad and the opposing party by name, so the
"who's mine vs. who's the enemy" fact doesn't depend on the model parsing
JSON key semantics correctly or on any battle history existing yet.

Related fix, same conversation: MP cost/deduction was never actually
missing (engine.battle._do_skill has always checked and spent it), but a
model that misjudges its own MP and asks for a skill it can't afford used
to waste the whole turn once the engine's MP check rejected it silently
(the unit "hesitates" and nothing happens). _parse_llm_action now catches
that case the same way it already caught an invalid skill_id: it degrades
to a basic attack instead of burning the turn on an unaffordable request.
"""
import json
import queue
import random
import re
import threading
import time
from typing import Callable, Dict, Optional

from engine.actions import Action
from engine.types import ActionType
from ai.ollama_client import OllamaClient, OllamaError

# Streamed in two parts so debug mode has actual prose to show "typing" live:
# a short THINKING line (plain text, in character) followed by an ACTION_JSON
# line. We deliberately do NOT use Ollama's format="json" mode here -- that
# constrains the *whole* reply to be a JSON document, which would rule out
# the free-text THINKING prefix. See _split_thinking_and_json for how the
# two get pulled back apart once the stream finishes, and
# ai/ollama_client.py's chat_stream docstring for the streaming mechanics.
SYSTEM_PROMPT = """You are the tactical commander directing an entire squad of monsters in a classic \
turn-based JRPG battle, staged in a gladiatorial colosseum. You do not play as any single monster -- \
you are the one mind coordinating the whole squad, issuing one order at a time as each squad member's \
turn comes up. Right now you are issuing the order for ONE specific squad member (the "acting unit" \
below); its squadmates will get their own orders on their own turns.

Think about the squad's overall position, not just what this one unit would do sitting in isolation: \
which enemy is most exposed and worth finishing off, whether this unit should protect or set up a \
wounded squadmate instead of just attacking, and whether your squad has already committed to a plan \
this round (check recent_log for what your squad has already done). Don't have every unit pile onto \
the same target for no reason, and don't waste an order on flavor when a squadmate already needs \
covering. Always choose a *legal, sensible* order for this unit given the situation.

The acting unit's own combat tendencies (temperament, preferred tactics) are given below as a note on \
how that unit fights and what it's inclined to do -- use it to inform this order (it should still feel \
like giving orders to a golem vs. a rogue vs. a cultist), but you are the one deciding, not the unit \
deciding for itself.

Respond with EXACTLY two lines, nothing before, between, or after them:

THINKING: <one short sentence of the commander's tactical reasoning for this order>
ACTION_JSON: {"action": "attack" | "skill" | "defend" | "flee", "skill_id": "<id from available_skills, or null>", "target_id": "<id of the combatant being targeted, or null>"}

Rules:
- The THINKING line must come first, must be plain text (not JSON), and must be brief -- one sentence, \
  written from the commander's perspective (e.g. "Send the golem after the wounded mage before she can \
  heal again" rather than "I want to attack the mage").
- The ACTION_JSON line must contain ONLY the JSON object after the "ACTION_JSON:" label -- no markdown, \
  no code fences, no extra commentary.
- "attack": a basic physical attack. Requires a target_id from human_party_targets below (an opposing \
  human hero) -- NEVER a target from rest_of_your_squad or the acting unit itself; those are your own side.
- "skill": use one of the acting unit's available_skills by id, but ONLY if acting_unit_mp is greater \
  than or equal to that skill's mp_cost -- your squad's MP does not refill during the fight, so treat it \
  as a limited resource and don't call for an expensive skill the unit can't currently pay for (fall back \
  to "attack", "defend", or a cheaper skill instead). Also requires a legal target_id for that skill's \
  target type: an opposing hero from human_party_targets for offensive/single-enemy-style skills, a \
  squadmate from rest_of_your_squad for an ally-support skill, or the acting unit itself for a self-only \
  skill -- never send an offensive skill at your own squad, and never send a support/self skill at a \
  human_party_targets id.
- "defend": brace defensively this turn, reducing incoming damage. No target needed.
- "flee": order this one unit to retreat from the fight entirely (ends the battle if it succeeds). Only \
  choose this if the unit's tendencies suggest it's notably self-preserving AND its HP is low -- it \
  should be rare, and it's about this unit breaking formation, not the whole squad routing.
- Only target combatants where "alive" is true.
- Never invent a skill_id that isn't listed in available_skills.
- Formations: each human_party_targets entry has a "formation" of "front", "middle", or "rear". If \
  acting_unit_is_melee is true and ANY human_party_targets entry has formation "front" and is alive, an \
  "attack" or single-target-enemy "skill" from this unit may ONLY target one of those front-row humans \
  -- the front row is physically blocking your reach to anyone behind it. Only once no human_party_targets \
  entry is alive with formation "front" can this unit's single-target orders reach a middle/rear human. \
  If acting_unit_is_melee is false, ignore this rule entirely -- this unit fights at range and can target \
  any living human regardless of row. This restriction never applies to an "all_enemies" skill (it still \
  hits everyone) or to a target from rest_of_your_squad.

Reminder: "rest_of_your_squad" and the acting unit are the monsters you command. "human_party_targets" \
are the human adventurers you are fighting -- they are never yours to command and never a target for a \
support/self skill. This distinction matters most on an early turn, before recent_log has much in it to \
lean on, so decide it from the roster below, not from the log.
"""


def _build_user_prompt(combatant, state: dict) -> str:
    party_view = [
        {"id": p["id"], "name": p["name"], "hp": p["hp"], "max_hp": p["max_hp"],
         "alive": p["alive"], "statuses": p["statuses"], "formation": p.get("formation", "middle")}
        for p in state["party"]
    ]
    # The rest of the squad (excluding the unit this order is for) -- what the
    # commander can see of its other units' current standing, so an order for
    # this unit can be made with the squad's overall position in mind rather
    # than in isolation. Not what they'll do later this round (undecided yet).
    squadmates_view = [
        {"id": e["id"], "name": e["name"], "hp": e["hp"], "max_hp": e["max_hp"],
         "alive": e["alive"], "statuses": e["statuses"]}
        for e in state["enemies"] if e["id"] != combatant.id
    ]
    payload = {
        "acting_unit_id": combatant.id,
        "acting_unit_name": combatant.name,
        "acting_unit_tendencies": combatant.persona or "A generic colosseum monster.",
        "acting_unit_hp": combatant.hp,
        "acting_unit_max_hp": combatant.max_hp,
        "acting_unit_mp": combatant.mp,
        "acting_unit_max_mp": combatant.max_mp,
        # Battle formations (engine/formation.py): whether THIS unit is a melee fighter for targeting
        # purposes. When true, a "front" human_party_target blocks this unit from reaching anyone
        # behind it -- see the preamble sentence below and the formation note in the system prompt.
        "acting_unit_is_melee": combatant.is_melee,
        "available_skills": state.get("available_skills", []),
        # Deliberately NOT called "party_*" -- in JRPG parlance "the party" almost
        # always means the *player's own* team, which is exactly backwards here
        # (the humans are the commander's target, not its team). That naming
        # collision was the likely cause of the model losing track of who it
        # controls vs. who it's fighting, especially on an early turn with little
        # recent_log to lean on. "your squad" / "human_party_targets" is meant to
        # read unambiguously even in isolation.
        "human_party_targets": party_view,        # the opposing humans -- never your own squad
        "rest_of_your_squad": squadmates_view,     # the other monsters you also command
        "recent_log": state.get("log_tail", []),   # includes what your squad already did this round
    }
    squad_names = ", ".join([combatant.name] + [m["name"] for m in squadmates_view]) or combatant.name
    party_names = ", ".join(p["name"] for p in party_view) or "(no living targets)"
    preamble = (
        f"You command a monster squad: {squad_names}. You are giving this turn's order to {combatant.name} "
        f"specifically. You are fighting AGAINST a party of human adventurers: {party_names} -- they are "
        f"human_party_targets below, not your own units.\n\n"
    )
    return (
        preamble + "Battle state (JSON):\n" + json.dumps(payload, indent=2) +
        "\n\nChoose this unit's order now. Respond with only the JSON object described in the system prompt."
    )


def _split_thinking_and_json(full_text: str):
    """Splits the model's streamed reply into (thinking_text, action_dict).

    Primary path: look for the "ACTION_JSON:" marker the prompt asks for and
    split on it. Falls back to just grabbing the last {...} blob in the text
    if the model didn't follow the format exactly (still fairly common with
    smaller/less-obedient local models) -- this keeps minor formatting
    deviations from wasting the whole turn on a parse failure.

    Raises ValueError if no JSON object can be found at all.
    """
    marker_match = re.search(r"ACTION_JSON\s*:", full_text, re.IGNORECASE)
    if marker_match:
        before = full_text[:marker_match.start()]
        after = full_text[marker_match.end():]
    else:
        before, after = "", full_text

    thinking = re.sub(r"^\s*THINKING\s*:\s*", "", before.strip(), flags=re.IGNORECASE).strip()

    json_start = after.find("{")
    json_end = after.rfind("}")
    if json_start == -1 or json_end == -1 or json_end < json_start:
        # Last resort: maybe the JSON landed before the marker somehow, or there
        # was no marker at all -- scan the whole text for a {...} blob.
        json_start = full_text.find("{")
        json_end = full_text.rfind("}")
        if json_start == -1 or json_end == -1 or json_end < json_start:
            raise ValueError(f"No JSON action found in model output: {full_text!r}")
        if not thinking:
            thinking = full_text[:json_start].strip()
        raw = json.loads(full_text[json_start:json_end + 1])
        return thinking, raw

    raw = json.loads(after[json_start:json_end + 1])
    return thinking, raw


def _parse_llm_action(combatant, state: dict, raw: dict) -> Action:
    action_str = str(raw.get("action", "")).lower().strip()
    skill_id = raw.get("skill_id") or None
    target_id = raw.get("target_id") or None
    target_ids = [target_id] if target_id else []

    skills_by_id = {s["id"]: s for s in state.get("available_skills", [])}
    # A model can misjudge its own MP (or ignore the "only if you can afford it"
    # instruction) and ask for a skill it can no longer pay for. Previously that
    # request reached the engine unchanged, which just makes the unit "hesitate"
    # and burns the whole turn doing nothing -- a worse outcome than the
    # already-existing "invalid skill_id" degrade below. Catching it here and
    # falling back to a basic attack keeps a turn from being wasted purely
    # because the commander's MP math was off.
    requested_skill = skills_by_id.get(skill_id) if action_str == "skill" else None
    unaffordable = requested_skill is not None and combatant.mp < requested_skill["mp_cost"]

    if action_str == "skill" and requested_skill is not None and not unaffordable:
        return Action.use_skill(combatant.id, skill_id, target_ids)
    if action_str == "defend":
        return Action.defend(combatant.id)
    if action_str == "flee":
        return Action.flee(combatant.id)
    if action_str == "attack" or (action_str == "skill" and (requested_skill is None or unaffordable)):
        # A skill request with an invalid/missing id, or one the unit can't currently
        # afford, degrades gracefully to a basic attack rather than wasting the whole
        # turn on a parsing failure or an MP shortfall.
        return Action.attack(combatant.id, target_id or "")
    raise ValueError(f"Unrecognized action from LLM: {raw!r}")


def scripted_fallback_action(combatant, state: dict) -> Action:
    """A simple heuristic AI, used when Ollama is unreachable or misbehaves.

    Keeps the battle playable even with no local LLM running at all, and
    guarantees enemy turns never simply hang or crash the game. This is
    deliberately simpler than what a real LLM enemy would do -- it's a
    safety net, not the intended difficulty -- but it's also what the
    headless tests measure balance against, so it's worth it being a little
    sharper than "always attack the lowest-HP target": a status-only skill
    (a debuff, since this AI never carries buffs on itself as its *only*
    option) is aimed at whichever living party member has the most MP
    instead, since this roster's two casters (Lyra, Sera) both sit well
    above the two MP-light fighters -- a rough but free-to-compute stand-in
    for "go bother the spellcaster" without needing to see anyone's actual
    skill list, which this AI doesn't have access to for the *party* side.
    """
    party = [p for p in state["party"] if p["alive"]]
    if not party:
        return Action.defend(combatant.id)

    # Battle formations (engine/formation.py's reachable_targets, reimplemented inline here rather
    # than imported -- this module stays self-contained from engine/, same as the rest of ai/): a
    # melee unit (combatant.is_melee) can only reach an occupied front row; a ranged/magical unit
    # reaches anyone. Only narrows SINGLE-target picks below -- all_enemies still hits everyone.
    if getattr(combatant, "is_melee", True):
        front = [p for p in party if p.get("formation") == "front"]
        reachable = front if front else party
    else:
        reachable = party

    skills = state.get("available_skills", [])
    affordable = [s for s in skills if s["mp_cost"] <= combatant.mp and s.get("kind") not in ("heal",)]
    lowest_hp_target = min(reachable, key=lambda p: p["hp"])
    highest_mp_target = max(reachable, key=lambda p: p["mp"])

    # Occasionally defend for flavor/unpredictability if healthy and no cheap skill available.
    if not affordable and random.random() < 0.15:
        return Action.defend(combatant.id)

    if affordable and random.random() < 0.8:
        # Prefer an actually-damaging skill when one's affordable -- a self-buff
        # or self-heal is fine as occasional flavor, but picking uniformly at
        # random among everything affordable let self-only skills (which this
        # roster has a few of) eat turns that should've been offense.
        damaging = [s for s in affordable if s.get("kind") in ("physical", "magical")]
        pool = damaging if damaging and random.random() < 0.8 else affordable
        skill = random.choice(pool)
        target_type = skill.get("target")
        if target_type == "self":
            return Action.use_skill(combatant.id, skill["id"], [combatant.id])
        if target_type == "all_enemies":
            return Action.use_skill(combatant.id, skill["id"], [p["id"] for p in party])
        if skill.get("kind") == "status":
            return Action.use_skill(combatant.id, skill["id"], [highest_mp_target["id"]])
        return Action.use_skill(combatant.id, skill["id"], [lowest_hp_target["id"]])

    return Action.attack(combatant.id, lowest_hp_target["id"])


def _run_streaming_with_relay(stream_fn: Callable[[Callable[[str], None]], str],
                               on_chunk: Optional[Callable[[str], None]] = None,
                               on_tick: Optional[Callable[[float], None]] = None,
                               tick_interval: float = 0.08) -> str:
    """Runs stream_fn(emit) on a background thread -- stream_fn should call
    emit(text_chunk) for each piece of streamed content it receives (see
    OllamaClient.chat_stream). Chunks are relayed to on_chunk on the
    *calling* thread through a queue, which is what makes it safe for
    on_chunk to call straight into a UI toolkit like pygame (SDL calls must
    happen on the main thread) instead of the network thread.

    on_tick(elapsed_seconds), if given, fires roughly every tick_interval
    even between chunks -- this covers the gap before the first token
    arrives (prompt processing/"prefill" can itself take a moment on a large
    model), where there'd otherwise be nothing to show yet.

    Returns stream_fn's full return value once the thread finishes; re-raises
    whatever it raised, on the calling thread.
    """
    q: "queue.Queue" = queue.Queue()
    box: Dict[str, object] = {}
    done_marker = object()

    def emit(chunk: str) -> None:
        q.put(("chunk", chunk))

    def worker() -> None:
        try:
            box["result"] = stream_fn(emit)
        except Exception as exc:  # noqa: BLE001 - re-raised on the calling thread below
            box["error"] = exc
        q.put((done_marker, None))

    thread = threading.Thread(target=worker, daemon=True)
    start = time.perf_counter()
    thread.start()
    while True:
        try:
            kind, payload = q.get(timeout=tick_interval)
        except queue.Empty:
            if on_tick:
                on_tick(time.perf_counter() - start)
            continue
        if kind is done_marker:
            break
        if kind == "chunk" and on_chunk:
            on_chunk(payload)
    thread.join()
    if on_tick:
        on_tick(time.perf_counter() - start)
    if "error" in box:
        raise box["error"]
    return box.get("result", "")


def make_enemy_ai_fn(client: OllamaClient, use_fallback_on_error: bool = True,
                      on_decision: Optional[Callable[[dict], None]] = None) -> Callable:
    """Builds the (combatant, state) -> Action callable BattleEngine expects.

    on_decision, if given, is called with a small dict at several points in
    each enemy turn -- this is the hook debug mode's "what's the model
    thinking, and how long is it taking" popup is built on (see
    ui/pygame_ui.py and ui/text_ui.py's on_ai_event):
      {"phase": "start",         "combatant_id", "combatant_name", "model"}
      {"phase": "tick",          "combatant_id", "combatant_name", "elapsed_seconds"}
          -- fires ~every 80ms while waiting, including gaps between chunks
      {"phase": "thinking_chunk", "combatant_id", "combatant_name",
       "delta", "text_so_far"}
          -- fires as each piece of the model's THINKING text streams in
      {"phase": "done", "combatant_id", "combatant_name", "elapsed_seconds",
       "used_fallback", "action_type", "skill_id", "target_id", "reason", "raw_content", "error"}
    """

    def _notify(record: dict) -> None:
        if on_decision:
            try:
                on_decision(record)
            except Exception as exc:  # noqa: BLE001 - a broken debug UI must never break the battle
                print(f"[debug-ui] on_decision callback raised {exc!r}; ignoring.")

    def get_enemy_action(combatant, state: dict) -> Action:
        _notify({"phase": "start", "combatant_id": combatant.id, "combatant_name": combatant.name,
                 "model": client.model})

        def tick(elapsed: float) -> None:
            _notify({"phase": "tick", "combatant_id": combatant.id, "combatant_name": combatant.name,
                     "elapsed_seconds": elapsed})

        # Streamed chunks are raw model output, which includes the "THINKING: "
        # label itself and (once it shows up) the start of "ACTION_JSON: {...".
        # We only want to display the THINKING sentence as it types, so we stop
        # relaying chunks once we've seen the ACTION_JSON marker -- the JSON
        # itself isn't meant to be watched typing out character by character.
        #
        # Stripping "THINKING:" off progressively (rather than just once at the
        # end) needs care: a naive regex-strip-per-chunk makes the displayed
        # text visibly SHRINK the instant the label finishes streaming in (e.g.
        # showing "THINKI" for a moment, then jumping back to "" once "NG:" of
        # "THINKING:" arrives). _visible_thinking_prefix avoids that by holding
        # back any output at all until it's sure whether a leading "THINKING:"
        # label is present.
        label = "THINKING:"
        action_marker = "ACTION_JSON:"

        def _visible_thinking_prefix(value: str) -> str:
            stripped = value.lstrip()
            upper = stripped.upper()
            if upper.startswith(label):
                return stripped[len(label):].lstrip()
            if label.startswith(upper):
                return ""  # only a partial prefix of "THINKING:" so far -- nothing to show yet
            return stripped  # doesn't look like our label format; show the raw text rather than lose it

        def _hold_back_partial_marker(text: str, marker: str) -> str:
            # Same problem in reverse, at the *end* of the text: if the tail could be
            # the start of "ACTION_JSON:" (e.g. text ending in "...now.\nACT"), showing
            # it would flash "ACT" on screen for a moment before it gets swallowed once
            # the marker completes. Hold back any tail that's still an unresolved prefix.
            upper = text.upper()
            for k in range(min(len(marker) - 1, len(text)), 0, -1):
                if upper.endswith(marker[:k]):
                    return text[: len(text) - k]
            return text

        seen_text = {"value": "", "action_marker_hit": False}

        def on_chunk(delta: str) -> None:
            seen_text["value"] += delta
            if seen_text["action_marker_hit"]:
                return
            value = seen_text["value"]
            marker_idx = value.upper().find(action_marker)
            if marker_idx != -1:
                seen_text["action_marker_hit"] = True
                visible = _visible_thinking_prefix(value[:marker_idx])
            else:
                visible = _hold_back_partial_marker(_visible_thinking_prefix(value), action_marker)
            _notify({"phase": "thinking_chunk", "combatant_id": combatant.id,
                     "combatant_name": combatant.name, "delta": delta, "text_so_far": visible})

        start = time.perf_counter()
        try:
            full_text = _run_streaming_with_relay(
                lambda emit: client.chat_stream(SYSTEM_PROMPT, _build_user_prompt(combatant, state), emit=emit),
                on_chunk=on_chunk, on_tick=tick,
            )
            thinking, raw = _split_thinking_and_json(full_text)
            action = _parse_llm_action(combatant, state, raw)
            elapsed = time.perf_counter() - start
            _notify({
                "phase": "done", "combatant_id": combatant.id, "combatant_name": combatant.name,
                "elapsed_seconds": elapsed, "used_fallback": False,
                "action_type": action.type.value, "skill_id": action.skill_id,
                "target_id": action.target_ids[0] if action.target_ids else None,
                "reason": thinking, "raw_content": raw, "error": None,
            })
            return action
        except (OllamaError, ValueError, KeyError, TypeError) as exc:
            elapsed = time.perf_counter() - start
            if not use_fallback_on_error:
                _notify({
                    "phase": "done", "combatant_id": combatant.id, "combatant_name": combatant.name,
                    "elapsed_seconds": elapsed, "used_fallback": False, "action_type": None,
                    "skill_id": None, "target_id": None, "reason": None, "raw_content": None,
                    "error": str(exc),
                })
                raise
            print(f"[ai] {combatant.name}: falling back to scripted AI ({exc})")
            fallback = scripted_fallback_action(combatant, state)
            _notify({
                "phase": "done", "combatant_id": combatant.id, "combatant_name": combatant.name,
                "elapsed_seconds": elapsed, "used_fallback": True,
                "action_type": fallback.type.value, "skill_id": fallback.skill_id,
                "target_id": fallback.target_ids[0] if fallback.target_ids else None,
                "reason": None, "raw_content": None, "error": str(exc),
            })
            return fallback

    return get_enemy_action

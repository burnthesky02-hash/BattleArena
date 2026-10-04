"""Rule-based enemy AI -- no model, no network. Every enemy decision is a pure
function of the battle state plus a small per-enemy *behavior profile*.

Public entry points
-------------------
make_enemy_ai_fn(memory=None, on_decision=None, rng=None) -> get_enemy_action
    get_enemy_action(combatant, state_dict) -> Action is the exact signature
    BattleEngine.get_enemy_action expects. The returned function also carries:
      .observe(party_combatant, action)  feed it the player's moves so rivals can adapt
      .memory                            the (optionally persistent) rival memory dict
scripted_fallback_action(combatant, state) -> Action
    stateless one-shot decision with the default profile (kept for tests/tools).
new_rival_memory() / decay_memory(memory)
    rival learning that can survive between fights (the host owns the dict).

How a decision is made (utility scoring)
----------------------------------------
Every legal option (basic attack, each affordable skill, defend) gets a score in
rough "HP points": damage it should do (capped by what the target has left, plus
a bonus for a kill), the value of a debuff/poison/buff that is not already in
place, healing that is actually needed, and so on. The profile then bends the
numbers: whom the unit likes to hit (weakest / tank / caster / strongest), skills
it opens with, when it heals or turtles, a finisher it saves for wounded targets,
and how much random noise keeps it from being perfectly predictable.

Telegraphed attacks
-------------------
Profiles with a `charge` skill sometimes spend a turn *gathering power* instead of
attacking: they brace (halving damage), gain the visible "Charging" status
(+60% atk/mag) and the host is told to log a warning. On their very next turn they
release the named skill. The player's answers: stun it (a missed turn cancels the
charge), defend through it, or spread the party out. See _Brain._maybe_charge.

Rival adaptation
----------------
Profiles flagged `adaptive` (hero rivals, the champion, the oracle, the reaper,
the horror) watch the player's moves via .observe(): they start hunting a healer
who keeps healing, focus the party's main damage dealer, and punish turtling with
debuffs and area attacks. The memory dict can be kept by the host across fights
(halved by decay_memory at the start of each new fight) so a rival remembers you.
"""
import random
import re
from typing import Callable, Dict, List, Optional

from engine.actions import Action
from engine.types import ActionType

CHARGE_STATUS = "charging"
CHARGE_COOLDOWN_ROUNDS = 4
CHARGE_CHANCE = 0.55

# ----------------------------------------------------------------------------
# Behavior profiles. Keys are enemy archetype ids (data/enemy_pool.py); a combatant
# matches the first key found in its normalised name ("Elite Iron Golem" -> iron_golem).
#   target     weakest | tank | caster | strongest | balanced   (who it prefers to hit)
#   open       skill ids it wants to use first, once each
#   aoe_at     living heroes needed before it prefers an area attack (default 3)
#   heal_at    ally HP fraction under which healing is worth a turn (default .45)
#   guard_at   own HP fraction under which it braces / buffs (default .25)
#   finisher   (skill_id, hp_fraction): bonus when the target is under that fraction
#   charge     skill id it telegraphs and releases a turn later
#   debuff     multiplier on debuff/poison value (default 1)
#   chaos      random noise on scores (default .12)
#   adaptive   learns from the player's moves
# ----------------------------------------------------------------------------
PROFILES: Dict[str, dict] = {
    "iron_golem":         {"target": "balanced", "guard_at": 0.40, "charge": "crushing_blow", "chaos": 0.08},
    "bandit_rogue":       {"target": "weakest", "open": ["sunder"], "chaos": 0.15},
    "dark_cultist":       {"target": "caster", "open": ["weaken"], "debuff": 1.3},
    "goblin_skirmisher":  {"target": "weakest", "chaos": 0.28},
    "stone_gargoyle":     {"target": "strongest", "guard_at": 0.50, "charge": "crushing_blow"},
    "frost_wraith":       {"target": "caster", "open": ["weaken"]},
    "flame_imp":          {"target": "weakest", "aoe_at": 3},
    "storm_harpy":        {"target": "caster", "open": ["sunder"], "chaos": 0.2},
    "venom_spider":       {"target": "balanced", "debuff": 1.6},
    "cursed_knight":      {"target": "strongest", "charge": "crushing_blow", "guard_at": 0.3},
    "colosseum_champion": {"target": "strongest", "open": ["warcry"], "charge": "crushing_blow",
                           "adaptive": True, "chaos": 0.06},
    "temple_oracle":      {"target": "caster", "heal_at": 0.6, "open": ["weaken"], "adaptive": True},
    "abyssal_horror":     {"target": "strongest", "open": ["weaken"], "charge": "thunderbolt",
                           "adaptive": True, "chaos": 0.07},
    "shard_sentry":       {"target": "strongest", "open": ["shield_bash"], "guard_at": 0.45,
                           "charge": "ground_slam"},
    "arc_drone":          {"target": "tank", "open": ["weaken"], "aoe_at": 2},
    "rift_leech":         {"target": "weakest", "debuff": 1.8},
    "lattice_medic":      {"target": "caster", "heal_at": 0.70},
    "phase_hound":        {"target": "weakest", "chaos": 0.04},
    "void_acolyte":       {"target": "strongest", "finisher": ("life_drain", 0.4)},
    "frost_mirage":       {"target": "tank", "open": ["frost_nova"], "aoe_at": 2},
    "forge_juggernaut":   {"target": "strongest", "open": ["warcry"], "charge": "crushing_blow"},
    "null_reaper":        {"target": "strongest", "finisher": ("executioners_edge", 0.5),
                           "adaptive": True, "chaos": 0.05},
}
DEFAULT_PROFILE: dict = {"target": "balanced"}
HERO_RIVAL_PROFILE: dict = {"target": "balanced", "adaptive": True, "chaos": 0.07}


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")


def profile_for(combatant) -> dict:
    """Finds the behavior profile for a combatant (by archetype name; hero rivals by id)."""
    name = _norm(getattr(combatant, "name", ""))
    for key, prof in PROFILES.items():
        if key in name:
            return prof
    if str(getattr(combatant, "id", "")).startswith("hero_"):
        return HERO_RIVAL_PROFILE
    return DEFAULT_PROFILE


# ----------------------------------------------------------------------------
# Rival memory
# ----------------------------------------------------------------------------
def new_rival_memory() -> dict:
    return {"heals_by": {}, "dmg_by": {}, "defends": 0, "attacks": 0, "debuffs": 0, "turns": 0}


def decay_memory(memory: dict) -> None:
    """Called at the start of each fight: old habits fade by half so a rival adapts to *recent* play."""
    for key in ("heals_by", "dmg_by"):
        for who in list(memory.get(key, {})):
            memory[key][who] = memory[key][who] / 2.0
            if memory[key][who] < 0.5:
                del memory[key][who]
    for key in ("defends", "attacks", "debuffs", "turns"):
        memory[key] = memory.get(key, 0) / 2.0


def _skills_db() -> dict:
    try:
        from data.skills_db import SKILLS
        return SKILLS
    except Exception:  # noqa: BLE001 - the AI must work even if the data module can't be imported
        return {}


def _bump(d: dict, key, amount=1.0) -> None:
    d[key] = d.get(key, 0.0) + amount


# ----------------------------------------------------------------------------
# The decision maker
# ----------------------------------------------------------------------------
class _Brain:
    def __init__(self, memory: dict, notify: Callable[[dict], None], rng: random.Random):
        self.memory = memory
        self.notify = notify
        self.rng = rng
        self.opened: Dict[str, set] = {}        # actor id -> skill ids already used as openers
        self.charges: Dict[str, dict] = {}      # actor id -> {"skill", "round", "released"}
        self.last_charge_round: Dict[str, int] = {}
        self.skills = _skills_db()

    # --- helpers -------------------------------------------------------
    def _reachable(self, actor, party: List[dict]) -> List[dict]:
        if getattr(actor, "is_melee", True):
            front = [p for p in party if p.get("formation") == "front"]
            return front if front else party
        return party

    def _target_weight(self, prof: dict, t: dict, party: List[dict], marks: dict) -> float:
        mode = prof.get("target", "balanced")
        hp_frac = t["hp"] / max(1, t["max_hp"])
        if mode == "weakest":
            w = 1.0 + 0.9 * (1.0 - hp_frac)
        elif mode == "tank":
            w = 1.0 + 0.6 * (t["max_hp"] / max(1, max(p["max_hp"] for p in party)))
        elif mode == "caster":
            w = 1.0 + 0.8 * (t["max_mp"] / max(1, max(p["max_mp"] for p in party)))
        elif mode == "strongest":
            w = 1.0 + 0.6 * (t["hp"] / max(1, max(p["hp"] for p in party)))
        else:
            w = 1.0 + 0.8 * (1.0 - hp_frac)
        if t.get("name") == marks.get("healer"):
            w *= 1.45
        if t.get("name") == marks.get("nuker"):
            w *= 1.30
        return w

    def _marks(self, prof: dict) -> dict:
        if not prof.get("adaptive"):
            return {}
        mem, marks = self.memory, {}
        heals = mem.get("heals_by", {})
        if heals:
            who, n = max(heals.items(), key=lambda kv: kv[1])
            if n >= 2:
                marks["healer"] = who
        dmg = mem.get("dmg_by", {})
        total = sum(dmg.values())
        if total >= 4:
            who, n = max(dmg.items(), key=lambda kv: kv[1])
            if n / total >= 0.4:
                marks["nuker"] = who
        if mem.get("defends", 0) >= 3:
            marks["turtle"] = True
        return marks

    @staticmethod
    def _est(actor, sk: Optional[dict], t: dict) -> float:
        kind = sk["kind"] if sk else "physical"
        power = sk["power"] if sk and sk.get("power") else 1.0
        stat = actor.effective_stat("mag" if kind == "magical" else "atk")
        est = power * stat * 1.1
        if t.get("defending"):
            est *= 0.5
        return est

    # --- charge / telegraph ----------------------------------------------
    def _maybe_charge(self, actor, state, prof, sk_list, party) -> Optional[Action]:
        sid = prof.get("charge")
        if not sid:
            return None
        sk = next((s for s in sk_list if s["id"] == sid), None)
        if sk is None or sk["mp_cost"] > actor.mp:
            return None
        rnd = state.get("round", 1)
        if rnd < 2 or rnd - self.last_charge_round.get(actor.id, -99) < CHARGE_COOLDOWN_ROUNDS:
            return None
        if actor.hp < actor.max_hp * 0.3 or self.rng.random() > CHARGE_CHANCE:
            return None
        from engine.status_effects import get_status
        actor.add_status(get_status(CHARGE_STATUS))
        self.charges[actor.id] = {"skill": sid, "round": rnd, "released": False}
        self.last_charge_round[actor.id] = rnd
        self.notify({"phase": "telegraph", "combatant_id": actor.id, "combatant_name": actor.name,
                     "skill_id": sid, "skill_name": sk["name"],
                     "message": f"{actor.name} gathers power for {sk['name']}! (stun it, or brace)"})
        return Action.defend(actor.id)

    def _release_or_clear(self, actor, state, prof, sk_list, party, marks) -> Optional[Action]:
        ch = self.charges.get(actor.id)
        if not ch:
            if actor.has_status(CHARGE_STATUS):
                actor.remove_status(CHARGE_STATUS)
            return None
        if ch["released"] or state.get("round", 1) != ch["round"] + 1:
            # Already spent, or a missed turn (stunned) broke the charge: the power fizzles.
            if not ch["released"]:
                self.notify({"phase": "interrupt", "combatant_id": actor.id, "combatant_name": actor.name,
                             "message": f"{actor.name}'s charge fizzles out!"})
            actor.remove_status(CHARGE_STATUS)
            del self.charges[actor.id]
            return None
        sk = next((s for s in sk_list if s["id"] == ch["skill"]), None)
        if sk is None or sk["mp_cost"] > actor.mp:
            actor.remove_status(CHARGE_STATUS)
            del self.charges[actor.id]
            return None
        ch["released"] = True
        return self._skill_action(actor, sk, party, prof, marks)

    def _skill_action(self, actor, sk, party, prof, marks) -> Action:
        if sk["target"] == "all_enemies":
            return Action.use_skill(actor.id, sk["id"], [p["id"] for p in party])
        pool = self._reachable(actor, party)
        best = max(pool, key=lambda t: self._est(actor, sk, t) * self._target_weight(prof, t, party, marks))
        return Action.use_skill(actor.id, sk["id"], [best["id"]])

    # --- main decision -----------------------------------------------------
    def decide(self, actor, state: dict) -> Action:
        party = [p for p in state["party"] if p["alive"]]
        if not party:
            return Action.defend(actor.id)
        prof = profile_for(actor)
        marks = self._marks(prof)
        sk_list = state.get("available_skills", [])
        allies = [e for e in state.get("enemies", []) if e["alive"]]

        released = self._release_or_clear(actor, state, prof, sk_list, party, marks)
        if released is not None:
            return released
        telegraph = self._maybe_charge(actor, state, prof, sk_list, party)
        if telegraph is not None:
            return telegraph

        reach = self._reachable(actor, party)
        hp_frac = actor.hp / max(1, actor.max_hp)
        opened = self.opened.setdefault(actor.id, set())
        chaos = prof.get("chaos", 0.12)
        aoe_at = prof.get("aoe_at", 3)
        options = []   # (score, Action, opener_skill_id_or_None)

        def add(score, action, opener=None):
            options.append((score * (1.0 + self.rng.uniform(-chaos, chaos)), action, opener))

        add(5.0 + (14.0 if hp_frac < prof.get("guard_at", 0.25) else 0.0), Action.defend(actor.id))
        for t in reach:
            dmg = min(self._est(actor, None, t), t["hp"])
            kill = 0.3 * t["max_hp"] if self._est(actor, None, t) >= t["hp"] else 0.0
            add((dmg + kill) * self._target_weight(prof, t, party, marks), Action.attack(actor.id, t["id"]))

        for sk in sk_list:
            if sk["mp_cost"] > actor.mp:
                continue
            sid, kind, tgt = sk["id"], sk["kind"], sk["target"]
            db = self.skills.get(sid)
            applies = getattr(db, "status_to_apply", None) if db else None
            opener = sid if sid in prof.get("open", []) and sid not in opened else None
            open_bonus = 500.0 if opener else 0.0   # openers are close to forced, once each
            cost = 0.8 * sk["mp_cost"]

            if kind in ("physical", "magical"):
                if tgt == "all_enemies":
                    total = sum(min(self._est(actor, sk, t), t["hp"]) * self._target_weight(prof, t, party, marks)
                                for t in party)
                    if len(party) >= aoe_at:
                        total += 10.0 * (len(party) - aoe_at + 1)
                    if marks.get("turtle"):
                        total *= 1.2
                    add(total - cost + open_bonus, Action.use_skill(actor.id, sid, [p["id"] for p in party]), opener)
                else:
                    for t in reach:
                        est = self._est(actor, sk, t)
                        score = min(est, t["hp"]) * self._target_weight(prof, t, party, marks)
                        if est >= t["hp"]:
                            score += 0.3 * t["max_hp"]
                        fin = prof.get("finisher")
                        if fin and fin[0] == sid and t["hp"] <= fin[1] * t["max_hp"]:
                            score += 40.0
                        if applies and applies not in t["statuses"]:
                            score += 0.10 * t["max_hp"] * prof.get("debuff", 1.0)
                        add(score - cost + open_bonus, Action.use_skill(actor.id, sid, [t["id"]]), opener)
            elif kind == "status":
                if tgt == "self":
                    if applies and actor.has_status(applies):
                        continue
                    score = 22.0
                    if applies == "def_up":
                        score += 30.0 * (1.0 - hp_frac)
                    elif applies == "regen":
                        score += 70.0 * (1.0 - hp_frac) if hp_frac < 0.7 else -15.0
                    elif applies == "atk_up" and state.get("round", 1) <= 2:
                        score += 15.0
                    add(score - cost + open_bonus, Action.use_skill(actor.id, sid, [actor.id]), opener)
                elif tgt == "single_enemy":
                    for t in reach:
                        if applies and applies in t["statuses"]:
                            continue
                        score = (12.0 + 0.10 * t["max_hp"]) * prof.get("debuff", 1.0)
                        if marks.get("turtle"):
                            score *= 1.3
                        w = self._target_weight(prof, t, party, marks)
                        add(score * w - cost + open_bonus, Action.use_skill(actor.id, sid, [t["id"]]), opener)
            elif kind == "heal":
                mag = actor.effective_stat("mag")
                if tgt == "all_allies":
                    gain = sum(min(a["max_hp"] - a["hp"], sk["power"] * mag) for a in allies)
                    needy = sum(1 for a in allies if a["hp"] < prof.get("heal_at", 0.45) * a["max_hp"])
                    if needy:
                        add(gain * 1.2 - cost, Action.use_skill(actor.id, sid, [a["id"] for a in allies]))
                else:
                    for a in allies:
                        missing = a["max_hp"] - a["hp"]
                        frac = a["hp"] / max(1, a["max_hp"])
                        amount = min(missing, sk["power"] * mag * 1.2)
                        if frac < prof.get("heal_at", 0.45):
                            add(amount * 1.5 - cost, Action.use_skill(actor.id, sid, [a["id"]]))
                        elif frac < 0.8:
                            add(amount * 0.3 - cost, Action.use_skill(actor.id, sid, [a["id"]]))

        score, action, opener = max(options, key=lambda o: o[0])
        if opener:
            opened.add(opener)
        return action


def make_enemy_ai_fn(memory: Optional[dict] = None,
                     on_decision: Optional[Callable[[dict], None]] = None,
                     rng: Optional[random.Random] = None) -> Callable:
    """Builds the (combatant, state) -> Action callable BattleEngine expects.

    on_decision(record) is called for visible tells: {"phase": "telegraph" | "interrupt",
    "combatant_id", "combatant_name", "message", ...}. The host turns those into log lines.
    """
    mem = memory if memory is not None else new_rival_memory()

    def _notify(record: dict) -> None:
        if on_decision:
            try:
                on_decision(record)
            except Exception as exc:  # noqa: BLE001 - a broken UI hook must never break the battle
                print(f"[ai] on_decision callback raised {exc!r}; ignoring.")

    brain = _Brain(mem, _notify, rng or random)

    def get_enemy_action(combatant, state: dict) -> Action:
        mem["turns"] = mem.get("turns", 0) + 1
        try:
            return brain.decide(combatant, state)
        except Exception as exc:  # noqa: BLE001 - never hang a battle on an AI bug
            print(f"[ai] {combatant.name}: decision failed ({exc!r}); attacking instead.")
            party = [p for p in state.get("party", []) if p["alive"]]
            if not party:
                return Action.defend(combatant.id)
            return Action.attack(combatant.id, min(party, key=lambda p: p["hp"])["id"])

    def observe(party_member, action: Action) -> None:
        """Records one player action so adaptive rivals can react to the player's habits."""
        name = getattr(party_member, "name", None)
        if not name or action is None:
            return
        if action.type == ActionType.DEFEND:
            mem["defends"] = mem.get("defends", 0) + 1
        elif action.type == ActionType.ATTACK:
            mem["attacks"] = mem.get("attacks", 0) + 1
            _bump(mem.setdefault("dmg_by", {}), name, 1.0)
        elif action.type == ActionType.SKILL:
            sk = _skills_db().get(action.skill_id)
            kind = getattr(sk, "kind", "")
            if kind == "heal":
                _bump(mem.setdefault("heals_by", {}), name, 1.0)
            elif kind == "status":
                mem["debuffs"] = mem.get("debuffs", 0) + 1
            else:
                _bump(mem.setdefault("dmg_by", {}), name, 1.0 + (1.0 if getattr(sk, "power", 1) >= 1.8 else 0.0))

    get_enemy_action.observe = observe
    get_enemy_action.memory = mem
    return get_enemy_action


def scripted_fallback_action(combatant, state: dict) -> Action:
    """One stateless decision with the combatant's profile (kept for tests and tools)."""
    brain = _Brain(new_rival_memory(), lambda record: None, random)
    return brain.decide(combatant, state)

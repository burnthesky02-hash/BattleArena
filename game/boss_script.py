"""Runs a BossDef's script (see data/bosses.py for the format) against a live
BattleEngine. Kept free of any networking: the host (hub_server.py) hands in
two callables --

    emit(message: dict)         push a message to the browser (dialogue / fx / log)
    wait_for_dialogue()         block until the player has clicked through the dialogue

so the same runner can be driven headlessly in tests (emit=list.append,
wait_for_dialogue=lambda: None).

Hooks the host calls:
    runner.on_start()                 before round 1 (plays "intro")
    runner.after_action()             after every resolved action (checks triggers)
    runner.before_boss_action() -> Action | None
                                      just before the boss decides; returns a forced
                                      (scripted) Action if a trigger queued one
    runner.on_end(result)             plays "victory"/"defeat"
"""
import random
from typing import Callable, List, Optional

from engine.actions import Action
from engine.status_effects import get_status
from engine.types import ActionType, BattleResult
import engine.formulas as formulas


class BossRunner:
    counter_key = "counter"     # status that turns physical hits on the boss into counter-strikes

    def __init__(self, boss_def, boss, engine, emit: Callable[[dict], None],
                 wait_for_dialogue: Callable[[], None], refresh_state: Callable[[], None] = lambda: None):
        self.d = boss_def
        self.boss = boss
        self.engine = engine
        self.emit = emit
        self.wait_for_dialogue = wait_for_dialogue
        self.refresh_state = refresh_state
        self.script = boss_def.script or {}
        self.fired: set = set()
        self.forced: List[dict] = []      # queued {"skill", "target"} scripted actions
        self._last_periodic_round = {}    # trigger id -> last round it fired (for every_n_rounds)
        self.flags: set = set()           # script flags ({"flag": name} steps), read by rules
        self.on_skill: dict = {}          # skill id -> {"vfx", "sfx"} cosmetics registered by an {"on_skill": {...}} step
        self._hp_seen = boss.hp           # boss HP at its previous decision (for boss_lost_pct_above)
        self._rule_last: dict = {}        # rule id -> round it last fired (for cooldown)
        boss.unlimited_mp = True          # scripted bosses never run dry: forced moves and rules must always be castable

    # ------------------------------------------------------------------
    def on_start(self) -> None:
        self._play(self.script.get("intro", []))

    def on_end(self, result: BattleResult) -> None:
        if result == BattleResult.VICTORY:
            self._play(self.script.get("victory", []))
        elif result == BattleResult.DEFEAT:
            self._play(self.script.get("defeat", []))

    # --- multi-unit hooks (no-ops for a single boss; game/twins_fight.py overrides them) ---
    def controls(self, combatant_id: str) -> bool:
        """True if this runner scripts the given enemy's turns."""
        return combatant_id == self.boss.id

    def before_action(self, action: Action) -> Action:
        """Called just before any action is broadcast/resolved; may return a rewritten action."""
        return action

    def after_action(self, action=None, boss_hp_before=None, **_kw) -> None:
        if action is not None and boss_hp_before is not None:
            self._maybe_counter(action, boss_hp_before)
        if action is not None and action.actor_id == self.boss.id and getattr(action, "skill_id", None) in self.on_skill:
            self._skill_fx(self.on_skill[action.skill_id])
        self._check_triggers()

    def _maybe_counter(self, action, boss_hp_before) -> None:
        """While the boss has Counter Stance, a hero's physical hit that actually hurt it is
        answered immediately with a counter-strike on that hero."""
        b, e = self.boss, self.engine
        if not b.alive or e.result != BattleResult.ONGOING or b.hp >= boss_hp_before:
            return
        if not any(s.key == self.counter_key for s in b.status_effects):
            return
        actor = e.get_by_id(action.actor_id)
        if actor is None or actor.is_enemy or not actor.alive:
            return
        skill = e.skills_db.get(action.skill_id) if action.type == ActionType.SKILL else None
        if not (action.type == ActionType.ATTACK or (skill is not None and skill.kind == "physical")):
            return
        self.emit({"type": "action_event", "actor_id": b.id, "target_id": actor.id, "is_melee": True,
                   "action_type": "counter", "skill_id": None, "item_id": None})
        res = formulas.physical_damage(b, actor, 1.2)
        dealt = actor.take_damage(res.amount)
        e.log(f"{b.name} counters {actor.name} for {dealt} damage!{' Critical!' if res.crit else ''}")
        self.flags.add("countered")
        if hasattr(e, "_damage"):
            e._damage[b.id] = e._damage.get(b.id, 0) + dealt
        if not actor.alive:
            e.log(f"{actor.name} is defeated!")
        e._check_result()
        self.refresh_state()

    def before_boss_action(self, combatant=None) -> Optional[Action]:
        self._check_triggers()
        held = []       # brace-or-die casts nobody could answer yet: they wait (max 2 boss turns) for the party to be able to react
        while self.forced:
            f = self.forced.pop(0)
            target_ids = self._pick_targets(f.get("target", "random"))
            if target_ids is None:
                continue
            if f.get("brace") and f.get("cast") and f.get("waited", 0) < 2 and not self._party_can_react(f["cast"]):
                f["waited"] = f.get("waited", 0) + 1
                held.append(f)
                continue
            self.forced = held + self.forced
            return Action.use_skill(self.boss.id, f["skill"], target_ids, cast_time=f.get("cast"),
                                    no_pushback=bool(f.get("nopush")), brace_mult=float(f.get("brace") or 1.0),
                                    power_mult=float(f.get("mult") or 1.0))
        self.forced = held
        # Holding a counter stance: he waits for a physical hit to punish instead of attacking normally.
        if self.boss.alive and any(s.key == self.counter_key for s in self.boss.status_effects):
            self.engine.log(f"{self.boss.name} holds his stance, waiting to counter...")
            self._hp_seen = self.boss.hp
            return Action.defend(self.boss.id)
        return self._rule_action()

    # ------------------------------------------------------------------
    def _party_can_react(self, cast: float) -> bool:
        """ATB: at least half of the living heroes will have a turn before a `cast`-second wind-up lands (outside ATB: always)."""
        alive = [h for h in self._heroes() if h.alive]
        if not alive or not getattr(self.engine, "atb", False):
            return True
        quick = sum(1 for h in alive if self._eta(h) <= cast - 1.0)
        return quick >= (len(alive) + 1) // 2

    def _eta(self, h) -> float:
        """Seconds until hero h can act (ATB); 0 outside ATB. Lets a long cast wait until someone can still answer it."""
        e = self.engine
        if not getattr(e, "atb", False):
            return 0.0
        if h.atb_phase == "ready":
            return 0.0
        if h.atb_phase == "casting" and h.cast:
            return max(0.0, h.cast["left"])
        return max(0.0, (1.0 - h.atb_gauge) * e.fill_seconds(h))

    def _rule_action(self) -> Optional[Action]:
        """Optional script["rules"]: an ordered list of conditional skill choices, checked on each of the boss's own turns.
        The first rule whose conditions hold becomes the boss's action; if none match, the normal AI decides.
          {"id", "skill", "target": "self"|"lowest_hp"|"highest_hp"|"random", "cooldown": rounds, "clear_flag": bool,
           "when": {"flag", "boss_lost_pct_above" (share of max HP lost since its last turn), "boss_hp_below", "boss_lacks_status",
                    "round_at_least", "target_hp_above", "target_hp_below" (hero HP fraction), "target_lacks_status"}}"""
        rules = self.script.get("rules")
        b, e = self.boss, self.engine
        if not rules or not b.alive:
            return None
        lost = max(0, self._hp_seen - b.hp) / max(1, b.max_hp)
        self._hp_seen = b.hp
        heroes = [h for h in self._heroes() if h.alive]
        if not heroes:
            return None
        for rule in rules:
            rid, w = rule.get("id", rule["skill"]), rule.get("when", {})
            if e.round_number - self._rule_last.get(rid, -999) < rule.get("cooldown", 0):
                continue
            if "flag" in w and w["flag"] not in self.flags:
                continue
            if "boss_lost_pct_above" in w and lost < w["boss_lost_pct_above"]:
                continue
            if "boss_hp_below" in w and b.hp / max(1, b.max_hp) > w["boss_hp_below"]:
                continue
            if "boss_lacks_status" in w and any(s.key == w["boss_lacks_status"] for s in b.status_effects):
                continue
            if "round_at_least" in w and e.round_number < w["round_at_least"]:
                continue
            mode = rule.get("target", "random")
            if mode == "self":
                ids = []
            else:
                pool = [h for h in heroes
                        if ("target_hp_above" not in w or h.hp / max(1, h.max_hp) > w["target_hp_above"])
                        and ("target_hp_below" not in w or h.hp / max(1, h.max_hp) < w["target_hp_below"])
                        and ("target_lacks_status" not in w or not any(s.key == w["target_lacks_status"] for s in h.status_effects))
                        and ("target_eta_below" not in w or self._eta(h) <= w["target_eta_below"])]
                if not pool:
                    continue
                pick = (min(pool, key=lambda h: h.hp) if mode == "lowest_hp" else
                        max(pool, key=lambda h: h.hp) if mode == "highest_hp" else random.choice(pool))
                ids = [pick.id]
            if rule.get("clear_flag") and "flag" in w:
                self.flags.discard(w["flag"])
            self._rule_last[rid] = e.round_number
            return Action.use_skill(b.id, rule["skill"], ids)
        return None

    _VFX = {"earth_shake": ("shake", None), "bark_crack": ("shake", None), "heavy_wood_impact": ("shake", None), "deep_thud": ("shake", None),
            "green_mist": ("flash", "#1c4a26"), "leaves_scatter": ("flash", "#25552a"), "roots_coil": ("flash", "#3a2a12"), "forest_glow": ("flash", "#2f7a3a")}

    def _skill_fx(self, cfg: dict) -> None:
        kind = self._VFX.get(cfg.get("vfx"))
        if kind is None:
            return
        self.emit({"type": "fx", "kind": kind[0], **({"color": kind[1]} if kind[1] else {})})

    # ------------------------------------------------------------------
    def _heroes(self):
        return list(self.engine.party)

    def _cond_ok(self, tid: str, when: dict) -> bool:
        e = self.engine
        heroes = self._heroes()
        alive = [h for h in heroes if h.alive]
        if "hp_below" in when and not (self.boss.alive and self.boss.hp / max(1, self.boss.max_hp) <= when["hp_below"]):
            return False
        if "round_at_least" in when and e.round_number < when["round_at_least"]:
            return False
        if "heroes_down_at_least" in when and (len(heroes) - len(alive)) < when["heroes_down_at_least"]:
            return False
        if "heroes_alive_at_most" in when and len(alive) > when["heroes_alive_at_most"]:
            return False
        if "party_has" in when and not any(h.name == when["party_has"] for h in alive):
            return False
        if "boss_has_status" in when and not any(st.key == when["boss_has_status"] for st in self.boss.status_effects):
            return False
        if "any_hero_has_status" in when and not any(st.key == when["any_hero_has_status"] for h in alive for st in h.status_effects):
            return False
        if "any_hero_hp_below" in when and not any(h.hp / max(1, h.max_hp) < when["any_hero_hp_below"] for h in alive):
            return False
        if "flag" in when and when["flag"] not in self.flags:
            return False
        if "every_n_rounds" in when:
            n, start = when["every_n_rounds"], when.get("from", when["every_n_rounds"])
            r = e.round_number
            if r < start or (r - start) % n != 0 or self._last_periodic_round.get(tid) == r:
                return False
        return True

    def _check_triggers(self) -> None:
        if self.engine.result != BattleResult.ONGOING or not self.boss.alive:
            return
        for trig in self.script.get("triggers", []):
            tid = trig["id"]
            once = trig.get("once", True)
            if once and tid in self.fired:
                continue
            if not self._cond_ok(tid, trig.get("when", {})):
                continue
            self.fired.add(tid)
            self._last_periodic_round[tid] = self.engine.round_number
            self._play(trig.get("steps", []))
            if self.engine.result != BattleResult.ONGOING:
                return

    # ------------------------------------------------------------------
    def _pick_targets(self, mode: str):
        alive = [h for h in self._heroes() if h.alive]
        if not alive:
            return None
        if mode == "highest_hp":
            return [max(alive, key=lambda h: h.hp).id]
        if mode == "lowest_hp":
            return [min(alive, key=lambda h: h.hp).id]
        if mode == "all":
            return []          # the skill's own target type decides (ALL_ENEMIES / SELF)
        if mode == "player":
            return [random.choice(alive).id]   # "the challenger": any hero (the only one in a solo fight)
        return [random.choice(alive).id]

    def _play(self, steps: list) -> None:
        dialogue_batch: list = []

        def flush():
            if dialogue_batch:
                self.refresh_state()
                self.emit({"type": "dialogue", "lines": list(dialogue_batch)})
                dialogue_batch.clear()
                self.wait_for_dialogue()

        for step in steps:
            if "if_party" in step and not any(h.name == step["if_party"] and h.alive for h in self._heroes()):
                continue        # e.g. a line only Kael speaks: skipped when he is not in the fight
            if "say" in step:
                s = step["say"]
                line = {"speaker": s[0], "text": s[1]}
                if len(s) > 2:
                    line["portrait"] = s[2]
                dialogue_batch.append(line)
                continue
            flush()   # keep effects in order relative to dialogue
            if "log" in step:
                self.engine.log(step["log"])
            elif "announce" in step:
                self.emit({"type": "fx", "kind": "announce", "text": step["announce"]})
            elif "shake" in step:
                self.emit({"type": "fx", "kind": "shake"})
            elif "flash" in step:
                self.emit({"type": "fx", "kind": "flash", "color": step["flash"]})
            elif "pause" in step:
                self.emit({"type": "fx", "kind": "pause", "ms": step["pause"]})
            elif "heal_boss_pct" in step:
                if self.boss.alive:
                    healed = self.boss.heal(round(self.boss.max_hp * step["heal_boss_pct"]))
                    self.engine.log(f"{self.boss.name} recovers {healed} HP!")
                    self.refresh_state()
            elif "apply_status" in step:
                a = step["apply_status"]
                targets = [self.boss] if a.get("target", "boss") == "boss" else [h for h in self._heroes() if h.alive]
                for t in targets:
                    st = get_status(a["status"])
                    if a.get("duration") is not None:
                        st.duration = a["duration"]
                    t.add_status(st)
                    self.engine.log(f"{t.name} gains {st.name}!")
                self.refresh_state()
            elif "force_skill" in step:
                self.forced.append(dict(step["force_skill"]))
            elif "cleanse_status" in step:
                c = step["cleanse_status"]
                targets = [self.boss] if c.get("target", "boss") == "boss" else [h for h in self._heroes() if h.alive]
                for t in targets:
                    if t.remove_status(c["status"]):
                        self.engine.log(f"{t.name} is cleansed of {c['status'].replace('_', ' ')}.")
                self.refresh_state()
            elif "flag" in step:
                self.flags.add(step["flag"])
            elif "on_skill" in step:
                self.on_skill.update(step["on_skill"])
        flush()

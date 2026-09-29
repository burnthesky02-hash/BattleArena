"""The Unbroken Pair (Ronan & Selene): the mechanics that make this a two-boss fight.

data/bosses.py owns the numbers (TWINS_TUNING), skills and dialogue; this module owns the rules:

  * GUARD    -- Ronan has a 50% chance to take a single-target *physical* hit meant for Selene.
  * REVIVE   -- when Ronan falls, Selene spends her next turn starting a rite (Crimson Rebirth):
                she gains a barrier and chants. On her following turn (a full round later) the
                rite completes and Ronan rises. Break the barrier, then deal any HP damage to
                her, and the chant is interrupted and she is staggered (loses a turn).
  * BLOODLUST-- if Selene falls while Ronan still stands he enrages: heals, grows, glows red,
                loses his guard, swaps to a deadlier kit and gets a large stat boost.
  * DANCE OF BLADES -- while Ronan is down Selene acts twice every turn, but only once her chant
                barrier is broken (or she isn't chanting).
  * MARKED FOR DEATH -- every few rounds Selene marks a hero; next turn she executes them unless
                they Defend or the mark is broken (Selene stunned / dies).
  * BULWARK  -- every few rounds Ronan plants his claymore: 100% guard + counter-strikes on physical
                hits until his next turn (spells and AoE slip past).
  * HARMONY  -- a shared meter that builds while both stand; full = both twins strike the whole
                party. Damage to either twin drains it; a stagger drains a lot.
  * ESCALATION -- every revive leaves Ronan stronger (and gives him Avenging Slam the first time);
                Selene's next barrier grows.
  * LINKED STRIKES -- when one twin hits a hero with a single-target attack, the other follows up
                on the same hero (once a round, chance-based).

Everything is done from the outside -- a Combatant subclass (barrier absorbs damage inside
take_damage) plus a BossRunner subclass driven by the same hooks hub_server already calls -- so
engine/ is untouched. Enemy turns still go through the normal AI; only the two revive actions
are forced.
"""
import random
from collections import defaultdict
from typing import Optional

from engine.actions import Action
from engine.combatant import Combatant
from engine.status_effects import get_status
from engine.types import ActionType, BattleResult, TargetType
from game.boss_script import BossRunner


_PAIR_SKILLS = ("pair_strike_ronan", "pair_strike_selene")
_MARK_SKILLS = ("execution", "execution_glancing")
_SCRIPTED = {"crimson_rebirth", "rebirth_complete", "deaths_mark", "bulwark_stance",
             *_PAIR_SKILLS, *_MARK_SKILLS}


class TwinCombatant(Combatant):
    """A Combatant that can carry a damage-absorbing barrier and UI flags."""

    def __post_init__(self):
        super().__post_init__()
        self.shield: int = 0
        self.shield_max: int = 0
        self.channeling: bool = False
        self.enraged: bool = False
        self.harmony: int = 0          # mirrored on both twins so the UI can read it from either
        self.harmony_max: int = 100
        self.dancing: bool = False     # Selene's Dance of Blades window
        self.on_shield_break = None    # callable(combatant) -- fired the moment the barrier hits 0
        self.on_hp_damage = None       # callable(combatant, dealt) -- fired for any real HP loss

    def take_damage(self, amount: int) -> int:
        amount = max(0, amount)
        if self.shield > 0 and amount > 0:
            absorbed = min(self.shield, amount)
            self.shield -= absorbed
            amount -= absorbed
            if self.shield == 0 and self.on_shield_break:
                self.on_shield_break(self)
        dealt = super().take_damage(amount)
        if dealt > 0 and self.on_hp_damage:
            self.on_hp_damage(self, dealt)
        return dealt

    def to_public_dict(self) -> dict:
        d = super().to_public_dict()
        d.update({"shield": self.shield, "shield_max": self.shield_max,
                  "channeling": self.channeling, "enraged": self.enraged,
                  "harmony": self.harmony, "harmony_max": self.harmony_max, "dancing": self.dancing})
        return d


class TwinsRunner(BossRunner):
    counter_key = "bulwark"       # Ronan's Bulwark is what turns physical hits into counters

    def __init__(self, boss_def, ronan, selene, engine, emit, wait_for_dialogue,
                 refresh_state=lambda: None, tuning=None, rng=None):
        super().__init__(boss_def, ronan, engine, emit, wait_for_dialogue, refresh_state)
        from data.bosses import TWINS_TUNING
        self.t = dict(TWINS_TUNING, **(tuning or {}))
        self.rng = rng or random
        self.ronan, self.selene = ronan, selene
        self.events = (boss_def.script or {}).get("events", {})
        self.revives_used = 0
        self._ronan_was_alive = True
        self._selene_was_alive = True
        self._pending_shield_break = False
        self._pending_interrupt = False
        self._guard_announced = False
        self.stats = defaultdict(int)     # counters for tests / balance sims
        self.harmony = 0
        self._harmony_announced = False
        self.mark_target_id = None
        self._next_mark = None
        self._last_mark_target = None
        self._last_mark_round = -1
        self._last_bulwark_round = -1
        self._last_link_round = -1
        self._in_extra = 0
        self._bonus_turn = False
        self._dance_announced = False
        for c in (ronan, selene):
            c.harmony_max = self.t["harmony_max"]
        selene.on_shield_break = self._shield_broken
        selene.on_hp_damage = self._selene_hurt
        ronan.on_hp_damage = self._ronan_hurt

    # ------------------------------------------------------------------ helpers
    def controls(self, combatant_id: str) -> bool:
        return combatant_id in (self.ronan.id, self.selene.id)

    def _event(self, name: str) -> None:
        ev = self.events.get(name)
        if not ev:
            return
        if ev.get("once") and name in self.fired:
            return
        self.fired.add(name)
        self._play(ev.get("steps", []))

    def _callout(self, combatant, text: str, color: str = "#ffe27a") -> None:
        self.emit({"type": "fx", "kind": "callout", "target_id": combatant.id, "text": text, "color": color})

    def _ronan_can_guard(self) -> bool:
        r = self.ronan
        return r.alive and not r.is_stunned() and not r.enraged and self.selene.alive

    # ------------------------------------------------------------------ damage callbacks (mid-action: log only)
    def _shield_broken(self, selene) -> None:
        if selene.channeling:
            self.engine.log("Selene's barrier shatters! Hit her now to break the chant!")
            self._pending_shield_break = True

    def _drain(self, c, dealt: int) -> None:
        """Damage to either twin loosens their synchronisation."""
        if self.harmony > 0 and c.max_hp > 0:
            self._set_harmony(self.harmony - dealt / c.max_hp * 100 * self.t["harmony_drain_per_pct"])
            if self.harmony < self.t["harmony_max"]:
                self._harmony_announced = False

    def _ronan_hurt(self, ronan, dealt: int) -> None:
        self._drain(ronan, dealt)

    def _set_harmony(self, v) -> None:
        self.harmony = int(max(0, min(self.t["harmony_max"], round(v))))
        for c in (self.ronan, self.selene):
            c.harmony = self.harmony

    def _both_up(self) -> bool:
        return self.ronan.alive and self.selene.alive and not self.ronan.enraged

    def _extra(self, action: Action) -> None:
        """Resolves an out-of-turn action (follow-up / dance / finisher half) through the normal pipeline."""
        e = self.engine
        if e.result != BattleResult.ONGOING:
            return
        self._in_extra += 1
        try:
            e.resolve_action(action)
            e._check_result()
        finally:
            self._in_extra -= 1

    def _dance_active(self) -> bool:
        """Dance of Blades: Selene's fury at Ronan's fall. It waits until her chant barrier is broken."""
        s = self.selene
        return bool(self.t["dance_of_blades"] and s.alive and not self.ronan.alive
                    and not (s.channeling and s.shield > 0))

    def _sync_flags(self) -> None:
        self.selene.dancing = self._dance_active()

    def _selene_hurt(self, selene, dealt: int) -> None:
        self._drain(selene, dealt)
        if selene.channeling and selene.shield <= 0 and selene.alive:
            selene.channeling = False
            selene.shield_max = 0
            self._pending_interrupt = True
            self.engine.log("The chant is broken -- Ronan's revival fizzles and Selene reels!")

    # ------------------------------------------------------------------ guard
    def before_action(self, action: Action) -> Action:
        e = self.engine
        actor = e.get_by_id(action.actor_id)
        if actor is None or actor.is_enemy or not actor.alive or not self._ronan_can_guard():
            return action
        if not action.target_ids or action.target_ids[0] != self.selene.id:
            return action
        if action.type == ActionType.ATTACK:
            physical = True
        elif action.type == ActionType.SKILL:
            sk = e.skills_db.get(action.skill_id)
            physical = bool(sk and sk.kind == "physical" and sk.target == TargetType.SINGLE_ENEMY)
        else:
            physical = False
        chance = self.t["bulwark_guard_chance"] if self.ronan.has_status("bulwark") else self.t["guard_chance"]
        if not physical or self.rng.random() >= chance:
            return action
        action.target_ids = [self.ronan.id]
        e.log("Ronan steps in front of Selene and takes the blow!")
        self._callout(self.ronan, "GUARD!", "#8fd0ff")
        if not self._guard_announced:
            self._guard_announced = True
            self._event("guard_first")
        return action

    # ------------------------------------------------------------------ forced (scripted / telegraphed) actions
    def _round(self) -> int:
        return self.engine.round_number

    def _periodic_due(self, start_key: str, every_key: str, last_round: int) -> bool:
        r = self._round()
        start, every = self.t[start_key], self.t[every_key]
        return r >= start and (r - start) % every == 0 and last_round != r

    def _marked_hero(self):
        if self.mark_target_id is None:
            return None
        h = self.engine.get_by_id(self.mark_target_id)
        if h is None or not h.alive:
            self._clear_mark()
            return None
        return h

    def _clear_mark(self) -> None:
        self.mark_target_id = None
        for h in self.engine.party:
            h.remove_status("marked")

    def _execution_skill(self, hero) -> str:
        """A hero who braced (Defend) only takes a glancing cut; anyone else is executed."""
        return "execution_glancing" if hero.defending else "execution"

    def _pick_mark_target(self):
        alive = [h for h in self.engine.party if h.alive]
        if not alive:
            return None
        pool = [h for h in alive if h.id != self._last_mark_target] or alive
        dmg = getattr(self.engine, "_damage", {}) or {}
        return max(pool, key=lambda h: (dmg.get(h.id, 0), h.hp))      # the biggest threat, rotating

    def _harmony_full(self) -> bool:
        return (self._both_up() and self.harmony >= self.t["harmony_max"]
                and not self.selene.channeling and not self.ronan.is_stunned() and not self.selene.is_stunned())

    def _bonus_attack(self) -> None:
        """Dance of Blades: Selene takes a second, normal (AI-chosen) action."""
        e, s = self.engine, self.selene
        if e.result != BattleResult.ONGOING or not s.alive or s.is_stunned() or not self._dance_active():
            return
        heroes = [h for h in e.party if h.alive]
        if not heroes:
            return
        if not self._dance_announced:
            self._dance_announced = True
            self.refresh_state()
            self._callout(s, "DANCE OF BLADES!", "#ff6a9a")
            self._event("dance_start")
        else:
            self._callout(s, "DANCE!", "#ff6a9a")
        self.stats["dance"] += 1
        e.log("Selene moves again -- Dance of Blades!")
        self._bonus_turn = True
        try:
            action = e.get_enemy_action(s, e.build_state(for_actor=s))
        except Exception:                                    # noqa: BLE001 - never let the AI crash the fight
            action = Action.attack(s.id, heroes[0].id)
        finally:
            self._bonus_turn = False
        self._extra(action)

    def before_boss_action(self, combatant=None) -> Optional[Action]:
        s, r, e, t = self.selene, self.ronan, self.engine, self.t
        if combatant is not None and combatant.id == s.id and s.alive:
            if self._bonus_turn:
                return None                                   # the extra Dance action is a normal AI move
            if s.channeling:
                if self._dance_active():
                    self._bonus_attack()                      # barrier broken: she strikes first, THEN the rite completes
                    if e.result != BattleResult.ONGOING:
                        return Action.defend(s.id)
                return Action.use_skill(s.id, "rebirth_complete", [s.id])
            if not r.alive and self.revives_used < t["max_revives"]:
                return Action.use_skill(s.id, "crimson_rebirth", [s.id])
            hero = self._marked_hero()
            if hero is not None:
                return Action.use_skill(s.id, self._execution_skill(hero), [hero.id])
            if self._harmony_full():
                return Action.use_skill(s.id, "pair_strike_selene", [])
            if (self.mark_target_id is None and self._periodic_due("mark_from_round", "mark_every", self._last_mark_round)):
                h = self._pick_mark_target()
                if h is not None:
                    self._next_mark = h.id
                    self._last_mark_round = self._round()
                    return Action.use_skill(s.id, "deaths_mark", [s.id])
            return None
        if combatant is not None and combatant.id == r.id and r.alive and not r.enraged and s.alive:
            if self._harmony_full():
                return Action.use_skill(r.id, "pair_strike_ronan", [])
            if (not r.has_status("bulwark") and
                    self._periodic_due("bulwark_from_round", "bulwark_every", self._last_bulwark_round)):
                self._last_bulwark_round = self._round()
                self.stats["bulwark"] += 1
                return Action.use_skill(r.id, "bulwark_stance", [r.id])
        return super().before_boss_action(combatant) if (combatant is None or combatant.id == self.boss.id) else None

    # ------------------------------------------------------------------ after every action
    def after_action(self, action=None, boss_hp_before=None, **_kw) -> None:
        e = self.engine
        s, r = self.selene, self.ronan
        twin_actor = action is not None and action.actor_id in (s.id, r.id)
        sid = action.skill_id if (action is not None and action.type == ActionType.SKILL) else None
        if twin_actor and sid:
            if sid == "crimson_rebirth":
                self._begin_channel()
            elif sid == "rebirth_complete":
                self._complete_revive()
            elif sid == "deaths_mark":
                self._apply_mark()
            elif sid in _MARK_SKILLS:
                self.stats[sid] += 1
                self._clear_mark()
                self.refresh_state()
            elif sid in _PAIR_SKILLS and not self._in_extra:
                self._pair_finisher(action)
        if self._pending_shield_break:
            self._pending_shield_break = False
            if s.alive:
                self.refresh_state()
                self._callout(s, "BARRIER BROKEN!", "#bfe8ff")
                self._event("shield_break")
        if self._pending_interrupt:
            self._pending_interrupt = False
            if s.alive:
                s.add_status(self._stagger())
                self._set_harmony(self.harmony - self.t["harmony_stagger_loss"])
                self._harmony_announced = False
                self.refresh_state()
                self._callout(s, "INTERRUPTED!", "#ffffff")
                self._event("interrupted")
        # a stunned Selene loses her mark (she cannot strike next turn)
        if self.mark_target_id is not None and (s.is_stunned() or not s.alive):
            self._clear_mark()
            e.log("Selene is thrown off -- the mark fades!")
            self.refresh_state()
        # Ronan just fell
        if self._ronan_was_alive and not r.alive:
            self._ronan_was_alive = False
            self._set_harmony(0)
            self._harmony_announced = False
            if self.mark_target_id is not None:
                self._clear_mark()
            if s.alive and e.result == BattleResult.ONGOING:
                self._event("ronan_down")
                if self.revives_used < self.t["max_revives"]:
                    e.log("Selene will try to raise Ronan on her next turn!")
        if not self._ronan_was_alive and r.alive:
            self._ronan_was_alive = True
        # Selene just fell
        if self._selene_was_alive and not s.alive:
            self._selene_was_alive = False
            s.channeling = False
            s.shield = 0
            s.shield_max = 0
            self._set_harmony(0)
            self._clear_mark()
            self._sync_flags()
            self.refresh_state()
            if r.alive and e.result == BattleResult.ONGOING:
                self._event("selene_down")
                self._enrage()
        self._sync_flags()
        if twin_actor and not self._in_extra and e.result == BattleResult.ONGOING:
            self._twin_bookkeeping(action, sid)
        if e.result == BattleResult.ONGOING:
            super().after_action(action, boss_hp_before)

    def _twin_bookkeeping(self, action, sid) -> None:
        """Per twin action (not for out-of-turn extras): build Harmony, Linked Strike, Dance of Blades."""
        e, t = self.engine, self.t
        if sid in _PAIR_SKILLS:
            return
        actor = e.get_by_id(action.actor_id)
        partner = self.ronan if actor is self.selene else self.selene
        if self._both_up():
            self._set_harmony(self.harmony + t["harmony_per_action"])
            if self.harmony >= t["harmony_max"] and not self._harmony_announced:
                self._harmony_announced = True
                self.refresh_state()
                self._callout(actor, "IN SYNC!", "#ff9ad1")
                e.log("Their movements align -- the Unbroken Pair will strike together on their next turn!")
                self._event("harmony_full")
            else:
                self.refresh_state()
        self._maybe_link(actor, partner, action, sid)
        if actor is self.selene and self._dance_active():
            self._bonus_attack()
            self._sync_flags()

    def _maybe_link(self, actor, partner, action, sid) -> None:
        e = self.engine
        if e.result != BattleResult.ONGOING or self._last_link_round == e.round_number:
            return
        if action.type == ActionType.SKILL:
            sk = e.skills_db.get(sid)
            if (sk is None or sid in _SCRIPTED or sk.target != TargetType.SINGLE_ENEMY
                    or sk.kind not in ("physical", "magical") or sk.power <= 0):
                return
        elif action.type != ActionType.ATTACK:
            return
        if not action.target_ids:
            return
        tgt = e.get_by_id(action.target_ids[0])
        if tgt is None or tgt.is_enemy or not tgt.alive:
            return
        if not partner.alive or partner.is_stunned() or partner.channeling or partner.enraged:
            return
        if self.rng.random() >= self.t["linked_chance"]:
            return
        self._last_link_round = e.round_number
        self.stats["link"] += 1
        e.log(f"{partner.name} follows up on {tgt.name}!")
        self._callout(partner, "LINKED STRIKE!", "#ffb84a")
        self._extra(Action.attack(partner.id, tgt.id))

    def _apply_mark(self) -> None:
        e = self.engine
        hero = e.get_by_id(self._next_mark) if self._next_mark else None
        self._next_mark = None
        if hero is None or not hero.alive:
            return
        self._clear_mark()
        hero.add_status(get_status("marked"))
        self.mark_target_id = hero.id
        self.stats["mark"] += 1
        self._last_mark_target = hero.id
        e.log(f"Selene marks {hero.name} for death! She will strike next turn -- Defend, heal them, or stop her!")
        self.refresh_state()
        self._callout(hero, "MARKED!", "#ff4a6a")
        self._callout(self.selene, "DEATH'S MARK", "#ff4a6a")
        self._event("mark_first")

    def _pair_finisher(self, action) -> None:
        e = self.engine
        actor = e.get_by_id(action.actor_id)
        partner = self.ronan if actor is self.selene else self.selene
        self.stats["pair"] += 1
        self._set_harmony(0)
        self._harmony_announced = False
        self._callout(actor, "UNBROKEN PAIR!", "#ff9ad1")
        e.log("THE UNBROKEN PAIR strike as one!")
        if partner.alive and not partner.is_stunned() and e.result == BattleResult.ONGOING:
            sid = "pair_strike_selene" if partner is self.selene else "pair_strike_ronan"
            self._callout(partner, "UNBROKEN PAIR!", "#ff9ad1")
            self._extra(Action.use_skill(partner.id, sid, []))
        self.refresh_state()

    def _check_triggers(self) -> None:
        """Like BossRunner's, but the script keeps running while EITHER twin stands."""
        if self.engine.result != BattleResult.ONGOING or not (self.ronan.alive or self.selene.alive):
            return
        for trig in self.script.get("triggers", []):
            tid = trig["id"]
            if trig.get("once", True) and tid in self.fired:
                continue
            if not self._cond_ok(tid, trig.get("when", {})):
                continue
            self.fired.add(tid)
            self._last_periodic_round[tid] = self.engine.round_number
            self._play(trig.get("steps", []))
            if self.engine.result != BattleResult.ONGOING:
                return

    def _stagger(self):
        st = get_status("stun")
        st.duration = self.t["stagger_turns"]
        return st

    def _begin_channel(self) -> None:
        s = self.selene
        grow = 1.0 + self.t["escalate_barrier"] * self.revives_used
        s.shield_max = max(1, round(s.max_hp * self.t["shield_pct"] * grow))
        s.shield = s.shield_max
        s.channeling = True
        self.engine.log(f"Selene gathers a crimson barrier ({s.shield} strong) and begins to chant...")
        self.refresh_state()
        self._event("cast_start")

    def _complete_revive(self) -> None:
        s, r = self.selene, self.ronan
        s.channeling = False
        s.shield = 0
        s.shield_max = 0
        if r.alive:
            self.engine.log("Ronan is already on his feet -- the rite dissolves.")
            self.refresh_state()
            return
        self.revives_used += 1
        r.revive(round(r.max_hp * self.t["revive_hp_pct"]))
        r.defending = False
        r.clear_all_status()
        n = self.revives_used
        up = get_status("unyielding")
        up.stat_mods = {"atk": 1 + self.t["escalate_atk"] * n, "def_": 1 + self.t["escalate_def"] * n}
        r.add_status(up)
        if "avenging_slam" not in r.skill_ids:
            r.skill_ids.append("avenging_slam")
        self.engine.log(f"Ronan rises with {r.hp} HP -- stronger than before! (Unyielding x{n})")
        self.refresh_state()
        self._event("revive_done" if self.revives_used == 1 else "revive_done_repeat")

    def _enrage(self) -> None:
        r = self.ronan
        r.enraged = True
        r.add_status(get_status("bloodlust"))
        r.skill_ids = ["bloodlust_rampage", "executioners_arc", "crushing_cleave"]
        r.persona = ("ENRAGED Ronan: his sister is dead and he has lost all restraint. He hits as hard as he "
                     "can every turn: Bloodlust Rampage when several heroes stand, Executioner's Arc on "
                     "whoever is weakest or most dangerous.")
        healed = r.heal(round(r.max_hp * self.t["enrage_heal_pct"]))
        self.engine.log(f"Ronan roars with grief and rage -- BLOODLUST! (+{healed} HP)")
        self.refresh_state()
        self._event("enrage")


def build_twin_members(bdef, level: int):
    """Builds the two TwinCombatants (Ronan first, then Selene) for a `runner == "twins"` BossDef."""
    from data.leveling import apply_growth
    out = []
    for m in bdef.members:
        stats = apply_growth(m.base_stats, m.growth, level)
        stats.max_hp = max(1, round(stats.max_hp * m.hp_mult))
        out.append(TwinCombatant(name=m.name, is_enemy=True, base_stats=stats, skill_ids=list(m.skill_ids),
                                 resistances=dict(m.resistances), persona=m.persona, sprite_color=m.sprite_color,
                                 formation="front", is_melee=True))
    return out

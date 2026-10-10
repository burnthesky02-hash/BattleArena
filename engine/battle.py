"""BattleEngine: turn order, round loop, and action resolution.

Design notes:
- This module knows nothing about pygame, or the console. It takes
  two callables at construction time -- get_party_action and
  get_enemy_action -- and calls whichever one is appropriate when it's a
  given combatant's turn. That's the seam that lets the *same* engine be
  driven by a human player and either a text UI, a pygame UI, or (in tests)
  a scripted stand-in, while enemies are driven by the rule-based AI in ai/enemy_ai.py.
- resolve_action() is defensive: if a skill_id/item_id/target_id doesn't
  resolve (e.g. a stale UI click), it falls back to something safe
  rather than crashing the battle.
"""
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from engine.combatant import Combatant
from engine.actions import Action
from data.leveling import scale_item_heal
from engine.skills import Skill, MAX_SKILL_RANK, mp_cost_at_rank, power_at_rank, status_duration_bonus_at_rank
from engine.items import Item
from engine.status_effects import get_status
from engine.types import ActionType, TargetType, BattleResult
import engine.formulas as formulas
import engine.formation as formation

# ---- ATB (active time battle) tuning --------------------------------------------------------------------------------
# Every combatant has a gauge that fills over fill_seconds(); at full they get a turn ("ready"), pick a command, and
# skills with a cast time run a cast bar before they resolve. Speed is compressed (SPEED_BIAS) so a fast monster acts a
# bit more often than a slow one rather than five times as often. Retune by feel.
ATB_FILL_K = 240.0           # fill_seconds = K / (spd + SPEED_BIAS), clamped
ATB_SPEED_BIAS = 18.0
ATB_FILL_MIN, ATB_FILL_MAX = 3.0, 16.0
ATB_START_MAX = 0.45         # opening gauges are random in [0, this] so nobody opens in lockstep
ROUND_SECONDS = 8.0          # boss scripts count "rounds": one per this many seconds of un-frozen battle time
ATB_MAX_SECONDS = 1200.0     # draw if a fight runs this long
ATB_TICK = 0.05              # seconds of battle time per loop tick
# Cast times (seconds) by skill kind: base + per_mp * mp_cost. 0-MP skills, attacks, items, defend and flee are instant.
CAST_BASE = {"physical": (0.8, 0.10), "magical": (1.2, 0.11), "heal": (1.0, 0.09), "status": (0.8, 0.07)}
CAST_MAX = 5.0
CAST_AOE_MULT = 1.25
# Interrupts: every hit on a casting unit delays its cast by CAST_PUSH_BASE + damage/max_hp (capped) of the cast time.
CAST_PUSH_BASE = 0.12
CAST_PUSH_DMG_CAP = 0.30
CAST_PUSH_TOTAL_CAP = 1.0    # the total delay can never exceed this fraction of the original cast time
STUN_GAUGE_LOSS = 0.5        # a stunned unit that is not casting loses this much gauge

MAX_ROUNDS = 100  # safety valve against infinite battles (e.g. two turtling sides that can't kill each other)

# MP does NOT regenerate during a battle (Andrew: remove the automatic MP regeneration). A combatant's
# MP is a budget for the whole fight; once it runs dry they fall back to basic attacks. MP comes back
# only from Ether-type items, resting, or leaving the battle. The constant stays (at 0) so anything that
# imports it keeps working; set it above 0 to bring a flat per-turn fraction of max MP back.
MP_REGEN_FRACTION = 0.0


@dataclass
class BattleEngine:
    party: List[Combatant]
    enemies: List[Combatant]
    skills_db: Dict[str, Skill]
    items_db: Dict[str, Item]
    inventory: Dict[str, int]                      # item_id -> count, shared by the party
    get_party_action: Callable[[Combatant, dict], Action]
    get_enemy_action: Callable[[Combatant, dict], Action]
    on_event: Optional[Callable[[str], None]] = None   # optional live-log hook for a UI
    # --- ATB mode (see the ATB constants above) ---
    atb: bool = False
    # Non-blocking command source for heroes: (combatant, state) -> Action, or None while the player is still choosing.
    # Without it ATB falls back to get_party_action (which then must answer immediately).
    poll_party_action: Optional[Callable[[Combatant, dict], Optional[Action]]] = None
    on_tick: Optional[Callable[["BattleEngine"], None]] = None        # every ATB tick (UI snapshot, input pump)
    on_cast_start: Optional[Callable[[Combatant, Action, float], None]] = None
    on_cast_cancel: Optional[Callable[[Combatant, str], None]] = None  # reason: "stun" | "dead"
    on_need_cancel: Optional[Callable[[Combatant], None]] = None       # a ready hero lost their turn before choosing
    sleep: Optional[Callable[[float], None]] = None                    # real-time wait per tick (None = run flat out)

    def __post_init__(self):
        self.log_history: List[str] = []
        self.result: BattleResult = BattleResult.ONGOING
        self.round_number: int = 0
        self.clock: float = 0.0          # ATB battle time in seconds (frozen while paused / animating)
        self.paused: bool = False        # set by the host while the player is in a sub-menu (wait mode)
        self._rng = random.Random()
        self._last_action_was_cast: bool = False   # read by the host's resolve wrapper (was this a finished cast?)

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------
    def all_combatants(self) -> List[Combatant]:
        return self.party + self.enemies

    def get_by_id(self, cid: str) -> Optional[Combatant]:
        for c in self.all_combatants():
            if c.id == cid:
                return c
        return None

    def alive_party(self) -> List[Combatant]:
        return [c for c in self.party if c.alive]

    def alive_enemies(self) -> List[Combatant]:
        return [c for c in self.enemies if c.alive]

    def side_of(self, combatant: Combatant) -> List[Combatant]:
        return self.enemies if combatant.is_enemy else self.party

    def opposing_side(self, combatant: Combatant) -> List[Combatant]:
        return self.party if combatant.is_enemy else self.enemies

    def log(self, message: str) -> None:
        self.log_history.append(message)
        if self.on_event:
            self.on_event(message)

    # ------------------------------------------------------------------
    # Turn order
    # ------------------------------------------------------------------
    def _build_turn_order(self) -> List[Combatant]:
        alive = [c for c in self.all_combatants() if c.alive]
        # A small random jitter keeps speed ties (and near-ties) from being
        # perfectly deterministic every round, while still respecting SPD overall.
        return sorted(alive, key=lambda c: c.effective_stat("spd") + random.uniform(-3, 3), reverse=True)

    # ------------------------------------------------------------------
    # State snapshot (handed to the UI and to the enemy AI)
    # ------------------------------------------------------------------
    def build_state(self, for_actor: Optional[Combatant] = None) -> dict:
        state = {
            "round": self.round_number,
            "atb": self.atb,
            "party": [c.to_public_dict() for c in self.party],
            "enemies": [c.to_public_dict() for c in self.enemies],
            "log_tail": self.log_history[-8:],
            "result": self.result.value,
        }
        if self.atb:
            for entry, c in zip(state["party"], self.party):
                entry["eta"] = round(self.eta(c), 2)         # seconds until this hero can act (the AI times its heavy casts by it)
        if for_actor is not None:
            state["actor_id"] = for_actor.id
            state["actor_name"] = for_actor.name
            state["actor_turn"] = for_actor.turn_count
            state["actor_skipped"] = for_actor.turns_skipped
            state["actor_persona"] = for_actor.persona
            state["actor_mp"] = for_actor.mp
            # Formation (engine/formation.py): lets a UI/AI pre-filter which single-target actions are
            # even legal, rather than relying only on _resolve_targets' server-side fallback.
            state["actor_formation"] = for_actor.formation
            state["actor_is_melee"] = for_actor.is_melee
            # mp_cost/power reflect this actor's actual current rank per skill (rank 1 = base numbers,
            # for anyone/anything that never ranks up -- enemies, and any hero skill they haven't put a
            # talent point into) -- see engine/skills.py's power_at_rank/mp_cost_at_rank.
            state["available_skills"] = [
                {"id": sid, "name": sk.name, "mp_cost": mp_cost_at_rank(sk, for_actor.rank_of(sid)),
                 "power": round(power_at_rank(sk, for_actor.rank_of(sid)), 3), "kind": sk.kind,
                 "element": sk.element.value if hasattr(sk.element, "value") else sk.element,
                 "target": sk.target.value if hasattr(sk.target, "value") else sk.target,
                 "description": sk.description,
                 "rank": for_actor.rank_of(sid), "max_rank": MAX_SKILL_RANK}
                for sid in for_actor.skill_ids
                for sk in (self.skills_db.get(sid),) if sk is not None
            ]
            if not for_actor.is_enemy:
                state["available_items"] = [
                    {"id": iid, "name": self.items_db[iid].name, "count": count,
                     "description": self.items_db[iid].description}
                    for iid, count in self.inventory.items() if count > 0 and iid in self.items_db
                ]
        return state

    # ------------------------------------------------------------------
    # Target resolution (defensive: never lets a bad id crash the battle)
    # ------------------------------------------------------------------
    def _resolve_targets(self, actor: Combatant, target_type: TargetType, requested_ids: List[str]) -> List[Combatant]:
        ally_side = [c for c in self.side_of(actor) if c.alive]
        enemy_side = [c for c in self.opposing_side(actor) if c.alive]

        def pick_requested(pool: List[Combatant]) -> Optional[Combatant]:
            for rid in requested_ids:
                match = next((c for c in pool if c.id == rid), None)
                if match:
                    return match
            return None

        if target_type == TargetType.SELF:
            return [actor]
        if target_type == TargetType.ALL_ALLIES:
            return ally_side
        if target_type == TargetType.ALL_ENEMIES:
            return enemy_side
        if target_type == TargetType.SINGLE_ALLY:
            chosen = pick_requested(ally_side)
            return [chosen] if chosen else ([actor] if actor.alive else ally_side[:1])
        # SINGLE_ENEMY (default/fallback case too). Formations (engine/formation.py): a melee actor
        # can only reach enemy_side's front row while it's occupied -- reachable narrows the pool
        # BEFORE a requested id is matched or a random fallback is picked, so a blocked target (from a
        # stale UI click or a bad AI pick) is never honored, just silently redirected to a
        # legal one instead of crashing or cheating past the row.
        reachable = formation.reachable_targets(actor, enemy_side)
        chosen = pick_requested(reachable)
        if chosen:
            return [chosen]
        return [random.choice(reachable)] if reachable else []

    # ------------------------------------------------------------------
    # Action resolution
    # ------------------------------------------------------------------
    def resolve_action(self, action: Action) -> None:
        actor = self.get_by_id(action.actor_id)
        if actor is None or not actor.alive:
            return

        was_defending = action.type == ActionType.DEFEND
        # Defense lasts until the defender's *next* action; clear it now that
        # they're acting again (unless they're defending again).
        if not was_defending:
            actor.defending = False

        if action.type == ActionType.ATTACK:
            self._do_attack(actor, action)
        elif action.type == ActionType.SKILL:
            self._do_skill(actor, action)
        elif action.type == ActionType.ITEM:
            self._do_item(actor, action)
        elif action.type == ActionType.DEFEND:
            actor.defending = True
            self.log(f"{actor.name} braces to defend.")
        elif action.type == ActionType.FLEE:
            self._do_flee(actor)

    def _do_attack(self, actor: Combatant, action: Action) -> None:
        targets = self._resolve_targets(actor, TargetType.SINGLE_ENEMY, action.target_ids)
        if not targets:
            return
        target = targets[0]
        result = formulas.physical_damage(actor, target)
        dealt = target.take_damage(result.amount)
        crit_txt = " A critical hit!" if result.crit else ""
        self.log(f"{actor.name} attacks {target.name} for {dealt} damage.{crit_txt}")
        if not target.alive:
            self.log(f"{target.name} is defeated!")

    def _do_skill(self, actor: Combatant, action: Action) -> None:
        skill = self.skills_db.get(action.skill_id) if action.skill_id else None
        if skill is None:
            self.log(f"{actor.name} tries to use an unknown skill and fumbles the turn.")
            return
        # Rank scales power up and MP cost up together (engine/skills.py) -- rank 1 (the default for
        # anyone who hasn't spent a talent point on this skill, and for every enemy) is exactly the
        # base Skill numbers, unchanged.
        rank = actor.rank_of(skill.id)
        mp_cost = mp_cost_at_rank(skill, rank)
        power = power_at_rank(skill, rank)
        if actor.mp < mp_cost:
            self.log(f"{actor.name} doesn't have enough MP for {skill.name} and hesitates.")
            return
        actor.spend_mp(mp_cost)
        targets = self._resolve_targets(actor, skill.target, action.target_ids)
        if not targets:
            self.log(f"{actor.name} uses {skill.name}, but there's no valid target.")
            return

        self.log(f"{actor.name} uses {skill.name}!")
        for target in targets:
            if not target.alive and skill.kind != "heal":
                continue
            dealt = 0
            if skill.kind == "physical":
                result = formulas.physical_damage(actor, target, power * action.power_mult)
                amount = result.amount
                brace = skill.undefended_mult * action.brace_mult
                if brace != 1.0 and not target.defending:
                    amount = round(amount * brace)      # a brace-or-die attack: Defend is the answer
                dealt = target.take_damage(amount)
                crit_txt = " Critical!" if result.crit else ""
                self.log(f"  {target.name} takes {dealt} damage.{crit_txt}")
            elif skill.kind == "magical":
                result = formulas.magical_damage(actor, target, power * action.power_mult, skill.element)
                amount = result.amount
                if action.brace_mult != 1.0 and not target.defending:
                    amount = round(amount * action.brace_mult)
                dealt = target.take_damage(amount)
                crit_txt = " Critical!" if result.crit else ""
                weak_txt = " It's super effective!" if target.resistances.get(skill.element, 1.0) > 1.0 else ""
                self.log(f"  {target.name} takes {dealt} {skill.element.value} damage.{crit_txt}{weak_txt}")
            elif skill.kind == "heal":
                amt = formulas.heal_amount(actor, power)
                healed = target.heal(amt)
                self.log(f"  {target.name} recovers {healed} HP.")

            if dealt and skill.lifesteal:
                reclaimed = actor.heal(max(1, round(dealt * skill.lifesteal)))
                if reclaimed:
                    self.log(f"  {actor.name} drains {reclaimed} HP from {target.name}.")

            if not target.alive:
                self.log(f"  {target.name} is defeated!")
                continue
            if skill.status_to_apply and random.random() < skill.status_chance:
                status = get_status(skill.status_to_apply)
                # poison/regen carry no fixed per-tick amount in STATUS_DB (a flat
                # number there would either be trivial against a high-HP target or
                # crushing against a low-HP one) -- scale it here, at the moment of
                # application, off whichever stat the source used to land the hit.
                if status.key == "poison":
                    status.dot_damage = max(1, round(target.max_hp * 0.07))
                elif status.key == "regen":
                    status.dot_damage = max(1, round(target.max_hp * 0.05))
                # Rank makes a status application last longer too (not just the power/mp_cost scaling
                # above) -- the only way a pure-buff skill like Iron Stance (power=0) actually gets
                # "more potent" per rank, per Andrew's request. Permanent statuses (duration <= 0)
                # aren't extended -- nothing is longer than permanent.
                if status.duration > 0:
                    status.duration += status_duration_bonus_at_rank(rank)
                target.add_status(status)
                self.log(f"  {target.name} is afflicted with {status.name}!")

    def _do_item(self, actor: Combatant, action: Action) -> None:
        item = self.items_db.get(action.item_id) if action.item_id else None
        if item is None:
            self.log(f"{actor.name} fumbles with an item that isn't there.")
            return
        if self.inventory.get(action.item_id, 0) <= 0:
            self.log(f"{actor.name} reaches for {item.name}, but there are none left!")
            return

        # Items can target a KO'd ally (for revives), so build the pool manually.
        ally_side = self.side_of(actor)
        candidates = [c for c in ally_side if c.id in action.target_ids] or ally_side
        if item.revive:
            targets = [c for c in candidates if not c.alive] or [c for c in ally_side if not c.alive]
        else:
            targets = [c for c in candidates if c.alive] or [c for c in ally_side if c.alive]
        if not targets:
            self.log(f"{actor.name} has no valid target for {item.name}.")
            return

        self.inventory[action.item_id] -= 1
        self.log(f"{actor.name} uses {item.name}!")
        for target in targets[:1] if item.target == TargetType.SINGLE_ALLY else targets:
            if item.revive:
                if not target.alive:
                    target.revive(scale_item_heal(item.heal_hp, target.max_hp))
                    self.log(f"  {target.name} is revived with {target.hp} HP!")
                continue
            if item.heal_hp:
                healed = target.heal(scale_item_heal(item.heal_hp, target.max_hp))
                self.log(f"  {target.name} recovers {healed} HP.")
            if item.heal_mp:
                restored = target.restore_mp(item.heal_mp)
                self.log(f"  {target.name} recovers {restored} MP.")
            if item.cure_status == "all":
                target.clear_all_status()
                self.log(f"  {target.name}'s status ailments are cured.")
            elif item.cure_status:
                if target.remove_status(item.cure_status):
                    self.log(f"  {target.name} is cured of {item.cure_status}.")

    def _do_flee(self, actor: Combatant) -> None:
        side = self.side_of(actor)
        other = self.opposing_side(actor)
        side_spd = sum(c.effective_stat("spd") for c in side if c.alive) / max(1, len([c for c in side if c.alive]))
        other_spd = sum(c.effective_stat("spd") for c in other if c.alive) / max(1, len([c for c in other if c.alive]))
        chance = formulas.flee_chance(side_spd, other_spd)
        if random.random() < chance:
            if actor.is_enemy:
                self.log(f"{actor.name} loses its nerve and flees the arena! You win by default.")
                self.result = BattleResult.VICTORY
            else:
                self.log(f"{actor.name}'s party flees from battle!")
                self.result = BattleResult.FLED
        else:
            self.log(f"{actor.name} tries to flee, but can't get away!")

    # ------------------------------------------------------------------
    # Round / battle loop
    # ------------------------------------------------------------------
    def _check_result(self) -> None:
        if self.result != BattleResult.ONGOING:
            return
        if not self.alive_enemies():
            self.result = BattleResult.VICTORY
        elif not self.alive_party():
            self.result = BattleResult.DEFEAT

    def run_round(self) -> None:
        self.round_number += 1
        self.log(f"--- Round {self.round_number} ---")
        order = self._build_turn_order()
        for combatant in order:
            if self.result != BattleResult.ONGOING:
                return
            if not combatant.alive:
                continue
            for line in combatant.tick_statuses():
                self.log(line)
            if MP_REGEN_FRACTION > 0:
                restored = combatant.restore_mp(max(1, round(combatant.max_mp * MP_REGEN_FRACTION)))
                if restored:
                    self.log(f"{combatant.name} regenerates {restored} MP.")
            self._check_result()
            if self.result != BattleResult.ONGOING:
                return
            if not combatant.alive:
                continue
            if combatant.is_stunned():
                self.log(f"{combatant.name} is stunned and can't act!")
                continue

            state = self.build_state(for_actor=combatant)
            try:
                if combatant.is_enemy:
                    self.log(f"{combatant.name} is deciding its move...")
                    action = self.get_enemy_action(combatant, state)
                else:
                    action = self.get_party_action(combatant, state)
            except Exception as exc:  # noqa: BLE001 - a bad action source must never crash the battle
                self.log(f"({combatant.name}'s action failed to resolve: {exc}; defending instead.)")
                action = Action.defend(combatant.id)

            self.resolve_action(action)
            self._check_result()


    # ------------------------------------------------------------------
    # ATB (active time battle)
    # ------------------------------------------------------------------
    def fill_seconds(self, c: Combatant) -> float:
        spd = c.effective_stat("spd")
        return max(ATB_FILL_MIN, min(ATB_FILL_MAX, ATB_FILL_K / (spd + ATB_SPEED_BIAS)))

    def eta(self, c: Combatant) -> float:
        """Seconds until c next acts (0 when ready; the cast time left while casting)."""
        if c.atb_phase == "ready":
            return 0.0
        if c.atb_phase == "casting" and c.cast:
            return max(0.0, c.cast["left"])
        return max(0.0, (1.0 - c.atb_gauge) * self.fill_seconds(c))

    def cast_seconds(self, actor: Combatant, action: Action) -> float:
        """How long this command's cast bar runs. Attacks, items, defend and flee are instant."""
        if action.type != ActionType.SKILL or not action.skill_id:
            return 0.0
        skill = self.skills_db.get(action.skill_id)
        if skill is None:
            return 0.0
        explicit = action.cast_time if action.cast_time is not None else getattr(skill, "cast_time", None)
        if explicit is not None:
            base = float(explicit)
        else:
            mp = mp_cost_at_rank(skill, actor.rank_of(skill.id))
            if mp <= 0:
                return 0.0
            b, per = CAST_BASE.get(skill.kind, CAST_BASE["status"])
            base = b + per * mp
            if getattr(skill.target, "value", skill.target) in ("all_enemies", "all_allies"):
                base *= CAST_AOE_MULT
        if explicit is not None:
            return base          # a hand-set cast (boss telegraph, heavy move) is the same length whoever casts it
        base = min(CAST_MAX, base)
        speed_factor = max(0.7, min(1.6, (actor.effective_stat("spd") + ATB_SPEED_BIAS) / 30.0))
        return base / speed_factor

    def begin_atb(self) -> None:
        """Opening gauges: random head starts, round counter at 1."""
        self.round_number = 1
        for c in self.all_combatants():
            start = getattr(c, "atb_start", None)       # (lo, hi) opening-gauge range a profile asked for, else the default
            lo, hi = start if start else (0.0, ATB_START_MAX)
            c.atb_gauge = self._rng.uniform(lo, hi)
            c.atb_phase = "charging"
            c.cast = None

    def _ready_heroes(self) -> List[Combatant]:
        return sorted((c for c in self.party if c.alive and c.atb_phase == "ready"), key=lambda c: c.ready_since)

    def _turn_ready(self, c: Combatant) -> None:
        """A gauge just filled: statuses tick, then an enemy decides at once and a hero waits for the player."""
        for line in c.tick_statuses():
            self.log(line)
        self._check_result()
        if self.result != BattleResult.ONGOING or not c.alive:
            return
        if c.is_stunned():
            self.log(f"{c.name} is stunned and can't act!")
            c.turns_skipped += 1
            c.atb_gauge, c.atb_phase = 0.0, "charging"
            return
        c.atb_gauge, c.atb_phase, c.ready_since = 1.0, "ready", self.clock
        if c.is_enemy:
            self._request_action(c)

    def _request_action(self, c: Combatant) -> Optional[Action]:
        """Asks the right source for c's command. Returns the action once started (cast or executed), else None."""
        state = self.build_state(for_actor=c)
        try:
            if c.is_enemy:
                action = self.get_enemy_action(c, state)
            elif self.poll_party_action is not None:
                action = self.poll_party_action(c, state)
            else:
                action = self.get_party_action(c, state)
        except Exception as exc:  # noqa: BLE001 - a bad action source must never crash the battle
            self.log(f"({c.name}'s action failed to resolve: {exc}; defending instead.)")
            action = Action.defend(c.id)
        if action is None:
            return None
        c.turn_count += 1
        self._begin_action(c, action)
        return action

    def _begin_action(self, c: Combatant, action: Action) -> None:
        total = self.cast_seconds(c, action)
        if total <= 0.05:
            self._execute(c, action)
            return
        skill = self.skills_db.get(action.skill_id)
        c.cast = {"action": action, "total": total, "left": total, "pushed": 0.0, "name": skill.name if skill else "?",
                  "pushback": bool(getattr(skill, "interruptible_by_damage", True)) and not action.no_pushback,
                  "brace": action.brace_mult > 1.0 or getattr(skill, "undefended_mult", 1.0) > 1.0}
        c.atb_phase = "casting"
        if self.on_cast_start:
            self.on_cast_start(c, action, total)

    def _execute(self, c: Combatant, action: Action) -> None:
        """Resolves the action now (cast finished or instant), then restarts the actor's gauge."""
        was_cast = c.cast is not None
        hp_before = {x.id: x.hp for x in self.all_combatants()}
        stun_before = {x.id: x.is_stunned() for x in self.all_combatants()}
        c.cast = None
        c.atb_gauge, c.atb_phase = 0.0, "charging"
        action_cast_flag = was_cast
        self._last_action_was_cast = action_cast_flag
        self.resolve_action(action)
        self._after_action_interrupts(c, hp_before, stun_before)
        self._check_result()

    def _after_action_interrupts(self, actor: Combatant, hp_before: dict, stun_before: dict) -> None:
        """Hits delay other units' casts; a freshly stunned unit loses its cast (or half its gauge)."""
        for x in self.all_combatants():
            if x is actor or not x.alive and x.cast is None:
                continue
            if not x.alive:
                if x.cast is not None:
                    x.cast = None
                    x.atb_phase, x.atb_gauge = "charging", 0.0
                    if self.on_cast_cancel:
                        self.on_cast_cancel(x, "dead")
                continue
            if not stun_before.get(x.id) and x.is_stunned():
                if x.cast is not None:
                    x.cast = None
                    x.atb_phase, x.atb_gauge = "charging", 0.0
                    self.log(f"{x.name}'s casting is interrupted by the stun!")
                    if self.on_cast_cancel:
                        self.on_cast_cancel(x, "stun")
                elif x.atb_phase == "charging":
                    x.atb_gauge = max(0.0, x.atb_gauge - STUN_GAUGE_LOSS)
                continue
            if x.cast is not None:
                lost = max(0, hp_before.get(x.id, x.hp) - x.hp)
                if lost > 0 and x.cast.get("pushback", True):
                    cast = x.cast
                    push = cast["total"] * (CAST_PUSH_BASE + min(CAST_PUSH_DMG_CAP, lost / max(1, x.max_hp)))
                    push = min(push, cast["total"] * CAST_PUSH_TOTAL_CAP - cast["pushed"])
                    if push > 0:
                        cast["left"] += push
                        cast["pushed"] += push
                        self.log(f"{x.name}'s {cast['name']} is delayed!")

    def _finish_cast(self, c: Combatant) -> None:
        action = c.cast["action"] if c.cast else None
        if action is None:
            c.atb_phase, c.atb_gauge = "charging", 0.0
            return
        self._execute(c, action)

    def step(self, dt: float) -> None:
        """Advances ATB battle time by dt seconds (gauges fill, casts count down, turns come up)."""
        if self.result != BattleResult.ONGOING:
            return
        self.clock += dt
        new_round = int(self.clock // ROUND_SECONDS) + 1
        if new_round > self.round_number:
            self.round_number = new_round
        units = [c for c in self.all_combatants() if c.alive]
        self._rng.shuffle(units)
        for c in units:
            if self.result != BattleResult.ONGOING:
                return
            if not c.alive:
                continue
            if c.atb_phase == "charging":
                c.atb_gauge += dt / self.fill_seconds(c)
                if c.atb_gauge >= 1.0:
                    c.atb_gauge = 1.0
                    self._turn_ready(c)
            elif c.atb_phase == "casting" and c.cast is not None:
                c.cast["left"] -= dt
                if c.cast["left"] <= 0:
                    self._finish_cast(c)
        self._check_result()

    def service_heroes(self) -> None:
        """Offers a command slot to every ready hero, longest-waiting first."""
        for h in self._ready_heroes():
            if self.result != BattleResult.ONGOING:
                return
            if h.is_stunned():
                if self.on_need_cancel:
                    self.on_need_cancel(h)
                h.turns_skipped += 1
                h.atb_gauge, h.atb_phase = 0.0, "charging"
                continue
            self._request_action(h)

    def run_atb(self) -> BattleResult:
        self.begin_atb()
        while self.result == BattleResult.ONGOING and self.clock < ATB_MAX_SECONDS:
            self.service_heroes()
            if self.result != BattleResult.ONGOING:
                break
            if not self.paused:
                self.step(ATB_TICK)
            if self.on_tick:
                self.on_tick(self)
            if self.sleep:
                self.sleep(ATB_TICK)
        if self.result == BattleResult.ONGOING:
            self.log("The battle drags on too long and ends in a draw.")
            self.result = BattleResult.DEFEAT
        return self.result

    def timeline(self) -> List[dict]:
        """Who acts next: [{id, name, is_enemy, eta, phase, cast}] soonest first (for the turn-order strip)."""
        out = []
        for c in self.all_combatants():
            if not c.alive:
                continue
            eta = self.eta(c)
            out.append({"id": c.id, "name": c.name, "is_enemy": c.is_enemy, "eta": round(eta, 2),
                        "phase": c.atb_phase, "cast": c.cast["name"] if c.cast else None})
        return sorted(out, key=lambda e: e["eta"])

    def run(self) -> BattleResult:
        """Runs rounds until the battle ends. Returns the final result."""
        if self.atb:
            return self.run_atb()
        while self.result == BattleResult.ONGOING and self.round_number < MAX_ROUNDS:
            self.run_round()
        if self.result == BattleResult.ONGOING:
            self.log("The battle drags on too long and ends in a draw.")
            self.result = BattleResult.DEFEAT
        return self.result

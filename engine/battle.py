"""BattleEngine: turn order, round loop, and action resolution.

Design notes:
- This module knows nothing about pygame, the console, or Ollama. It takes
  two callables at construction time -- get_party_action and
  get_enemy_action -- and calls whichever one is appropriate when it's a
  given combatant's turn. That's the seam that lets the *same* engine be
  driven by a human player and either a text UI, a pygame UI, or (in tests)
  a scripted stand-in, while enemies are driven by the local LLM (or a
  scripted fallback AI when the LLM is unavailable).
- resolve_action() is defensive: if a skill_id/item_id/target_id doesn't
  resolve (e.g. a malformed LLM response), it falls back to something safe
  rather than crashing the battle.
"""
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from engine.combatant import Combatant
from engine.actions import Action
from engine.skills import Skill, MAX_SKILL_RANK, mp_cost_at_rank, power_at_rank, status_duration_bonus_at_rank
from engine.items import Item
from engine.status_effects import get_status
from engine.types import ActionType, TargetType, BattleResult
import engine.formulas as formulas
import engine.formation as formation

MAX_ROUNDS = 100  # safety valve against infinite battles (e.g. two turtling sides that can't kill each other)

# MP never regenerated anywhere in the engine, so skills were usable only 2-3
# times per battle before falling back to free basic attacks. Each combatant
# now regains a flat fraction of their own max MP at the start of their own
# turn (same cadence as tick_statuses() below).
#
# Rebalance (Andrew: "some characters never run out of mp"): halved from the original 0.10 -- 10% of
# max MP per turn meant a full refill in ~10 turns of doing nothing but basic-attacking, which made MP
# a non-constraint for anyone patient. 0.05 doubles that to ~20 turns, and now compounds with the
# skill-rank system just below (engine/skills.py's RANK_MP_COST_STEP): a maxed-rank skill costs over
# 2x its base MP, so regen alone increasingly can't keep pace with a heavily-ranked kit. Minimum 1 per
# turn unchanged, so this never fully zeroes out for a low-max-MP combatant.
MP_REGEN_FRACTION = 0.05


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

    def __post_init__(self):
        self.log_history: List[str] = []
        self.result: BattleResult = BattleResult.ONGOING
        self.round_number: int = 0

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
    # State snapshot (handed to the UI and to the LLM prompt builder)
    # ------------------------------------------------------------------
    def build_state(self, for_actor: Optional[Combatant] = None) -> dict:
        state = {
            "round": self.round_number,
            "party": [c.to_public_dict() for c in self.party],
            "enemies": [c.to_public_dict() for c in self.enemies],
            "log_tail": self.log_history[-8:],
            "result": self.result.value,
        }
        if for_actor is not None:
            state["actor_id"] = for_actor.id
            state["actor_name"] = for_actor.name
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
        # stale UI click or a disobedient LLM pick) is never honored, just silently redirected to a
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
                result = formulas.physical_damage(actor, target, power)
                dealt = target.take_damage(result.amount)
                crit_txt = " Critical!" if result.crit else ""
                self.log(f"  {target.name} takes {dealt} damage.{crit_txt}")
            elif skill.kind == "magical":
                result = formulas.magical_damage(actor, target, power, skill.element)
                dealt = target.take_damage(result.amount)
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
                    target.revive(item.heal_hp)
                    self.log(f"  {target.name} is revived with {target.hp} HP!")
                continue
            if item.heal_hp:
                healed = target.heal(item.heal_hp)
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
            regen = max(1, round(combatant.max_mp * MP_REGEN_FRACTION))
            restored = combatant.restore_mp(regen)
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

    def run(self) -> BattleResult:
        """Runs rounds until the battle ends. Returns the final result."""
        while self.result == BattleResult.ONGOING and self.round_number < MAX_ROUNDS:
            self.run_round()
        if self.result == BattleResult.ONGOING:
            self.log("The battle drags on too long and ends in a draw.")
            self.result = BattleResult.DEFEAT
        return self.result

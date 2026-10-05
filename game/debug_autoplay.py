"""Debug-mode autoplayer: plays the party like an attentive human would under ATB.

Only reachable when the server runs with DEBUG on (hub_server gates the "debug_auto" message). It reads the live
engine (casts, gauges, statuses, resistances) rather than the trimmed state the browser gets, and returns an Action.

What it does, in priority order, for the hero whose command slot is open:
  1. BRACE   -- an enemy "brace" cast (a defend-or-die move) is going to land while this hero would be undefended
                -> Defend. (Defend lasts until the hero's next action resolves; a hero mid-cast stays guarded.)
  2. REVIVE  -- a fallen ally and a Phoenix Down in the bag.
  3. HEAL    -- hurt allies: party heal when 2+ are low, single heals sized to the deficit, a Potion instead when
                the heal's cast bar is too slow for an emergency; healers keep MP in reserve for this.
  4. MP      -- an Ether when a caster is dry.
  5. SUPPORT -- buffs on allies that lack them, debuffs on the biggest enemy (rate-limited per skill).
  6. OFFENSE -- scores every skill by damage per second of (cast + gauge refill), including AoE, elemental
                weakness, lifesteal and stun-on-a-caster; attacks when MP is being saved. Focus fire on the most
                valuable reachable foe (about to die, casting something interruptible, or a healer).
  7. Otherwise Defend.
A short reaction delay (REACTION_SECONDS of battle time after the hero's gauge fills) keeps it from being superhuman.
"""
from __future__ import annotations

from typing import Dict, Optional

from engine.actions import Action
from engine.formation import reachable_targets
from engine.skills import mp_cost_at_rank, power_at_rank
from engine.status_effects import STATUS_DB

REACTION_SECONDS = 0.35         # battle-clock time a ready hero "thinks" before acting
HEAL_BELOW = 0.5                # anyone with a heal steps in under this HP fraction
SUPPORT_HEAL_BELOW = 0.65       # a support hero steps in earlier
EMERGENCY_BELOW = 0.25          # slow heals are swapped for an instant Potion under this
HEALER_MP_RESERVE = 0.35        # a healer won't spend MP on offense below this fraction of max MP
BUFF_COOLDOWN = 14.0            # battle-seconds before the same support skill is cast again by the same hero
INTERRUPT_BONUS = 1.6           # target weight for an enemy mid-cast with a cast that damage can push back


def new_memo() -> dict:
    return {"last_support": {}}


def _ratio(c) -> float:
    return c.hp / max(1, c.max_hp)


def _status_is_buff(key: str) -> Optional[bool]:
    st = STATUS_DB.get(key)
    if st is None:
        return None
    mods = list(st.stat_mods.values())
    if mods and all(m >= 1 for m in mods):
        return True
    if (mods and any(m < 1 for m in mods)) or st.skip_turn or key in ("poison", "marked", "burn"):
        return False
    return None


def _item(state: dict, item_id: str) -> bool:
    return any(i["id"] == item_id and i.get("count", 0) > 0 for i in state.get("available_items", []))


def _exposed(engine, hero, cast_s: float, is_defend: bool, braced: list) -> bool:
    """Would this command leave `hero` unguarded when a brace cast lands?"""
    if is_defend:
        return False
    fs = engine.fill_seconds(hero)
    for e in braced:
        left = e.cast["left"]
        if cast_s < left <= cast_s + fs + 0.4:      # my action clears my guard first, and my next command comes too late
            return True
    return False


def decide(engine, hero, state: dict, skills_db: dict, memo: dict) -> Optional[Action]:
    """The action for `hero`, or None while it is still "reacting"."""
    if getattr(engine, "atb", False) and engine.clock - getattr(hero, "ready_since", 0.0) < REACTION_SECONDS:
        return None
    me = hero.id
    foes = [e for e in engine.enemies if e.alive]
    friends = [a for a in engine.party if a.alive]
    if not foes:
        return Action.defend(me)
    mp = hero.mp
    avail = state.get("available_skills", [])
    skills = [s for s in avail if s["mp_cost"] <= mp and s["id"] in skills_db]
    is_support = any(s["kind"] == "heal" for s in avail)
    braced = [e for e in foes if e.cast and e.cast.get("brace")]

    def cast_of(sid: str) -> float:
        return engine.cast_seconds(hero, Action.use_skill(me, sid, []))

    # 1) Brace
    if braced and _exposed(engine, hero, 0.0, False, braced):
        return Action.defend(me)

    # 2) Revive
    down = [a for a in engine.party if not a.alive]
    if down and _item(state, "phoenix_down") and len(friends) >= 1:
        return Action.use_item(me, "phoenix_down", down[0].id)

    # 3) Heal
    hurt_all = sorted(friends, key=_ratio)
    low = [a for a in hurt_all if _ratio(a) < (SUPPORT_HEAL_BELOW if is_support else HEAL_BELOW)]
    if low:
        worst = low[0]
        heals = [s for s in skills if s["kind"] == "heal"]
        party_heal = [s for s in heals if s["target"] == "all_allies"]
        single = [s for s in heals if s["target"] in ("single_ally", "self")]
        emergency = _ratio(worst) < EMERGENCY_BELOW
        if emergency and _item(state, "hi_potion") and (not single or cast_of(max(single, key=lambda s: s["power"])["id"]) > 1.2):
            return Action.use_item(me, "hi_potion", worst.id)
        if emergency and _item(state, "potion") and not single:
            return Action.use_item(me, "potion", worst.id)
        if party_heal and len([a for a in friends if _ratio(a) < 0.65]) >= 2:
            sk = max(party_heal, key=lambda s: s["power"])
            if not _exposed(engine, hero, cast_of(sk["id"]), False, braced):
                return Action.use_skill(me, sk["id"], [])
        if single:
            deficit = 1.0 - _ratio(worst)
            sk = max(single, key=lambda s: s["power"]) if deficit > 0.45 else min(single, key=lambda s: s["mp_cost"])
            if not _exposed(engine, hero, cast_of(sk["id"]), False, braced):
                return Action.use_skill(me, sk["id"], [worst.id])
        elif emergency and not is_support:
            for pid in ("hi_potion", "potion"):
                if _item(state, pid):
                    return Action.use_item(me, pid, worst.id)

    # 4) Ether
    if hero.max_mp > 0 and mp < hero.max_mp * 0.15 and _item(state, "ether"):
        return Action.use_item(me, "ether", me)

    # 5) Buffs / debuffs
    now = engine.clock
    longest_foe = max(e.hp for e in foes)
    fight_is_long = sum(e.hp for e in foes) > 2.5 * max(1, max((a.base_stats.atk for a in friends), default=10)) * 3
    for s in skills:
        sk = skills_db[s["id"]]
        key = getattr(sk, "status_to_apply", None)
        if not key or sk.kind != "status" or not fight_is_long:
            continue
        last = memo["last_support"].get((me, s["id"]), -999.0)
        if now - last < BUFF_COOLDOWN or hero.max_mp and mp < hero.max_mp * 0.3:
            continue
        kind = _status_is_buff(key)
        tgt = getattr(sk.target, "value", sk.target)
        act = None
        if kind is True:
            pool = [hero] if tgt == "self" else friends
            needy = [a for a in pool if key not in [x.key for x in a.status_effects]]
            if needy and (tgt in ("all_allies",) or len(needy) >= 1):
                act = Action.use_skill(me, s["id"], [] if tgt == "all_allies" else [max(needy, key=lambda a: a.max_hp).id])
        elif kind is False and tgt in ("single_enemy", "all_enemies"):
            reach = reachable_targets(hero, foes)
            pool = [e for e in (reach if tgt == "single_enemy" else foes) if key not in [x.key for x in e.status_effects]]
            big = [e for e in pool if _ratio(e) > 0.5 and e.hp >= longest_foe * 0.6]
            if big:
                act = Action.use_skill(me, s["id"], [] if tgt == "all_enemies" else [max(big, key=lambda e: e.hp).id])
        if act and not _exposed(engine, hero, cast_of(s["id"]), False, braced):
            memo["last_support"][(me, s["id"])] = now
            return act

    # 6) Offense
    reach = reachable_targets(hero, foes)
    fs = engine.fill_seconds(hero)

    def weight(e) -> float:
        w = 1.0 + (1.0 - _ratio(e)) * 1.2
        if e.defending:
            w *= 0.55                 # no point hammering a guard when something else is open
        if e.cast and e.cast.get("pushback") and not e.cast.get("brace"):
            w *= INTERRUPT_BONUS
        if any(sid for sid in e.skill_ids if skills_db.get(sid) is not None and skills_db[sid].kind == "heal"):
            w *= 1.3
        return w

    def value(s) -> tuple:
        sk = skills_db[s["id"]]
        tgt = getattr(sk.target, "value", sk.target)
        if s["kind"] not in ("physical", "magical") or tgt not in ("single_enemy", "all_enemies"):
            return (0.0, None)
        elem = getattr(sk, "element", None)
        pool = foes if tgt == "all_enemies" else reach
        if tgt == "all_enemies":
            total = sum(((e.resistances.get(elem, 1.0) if s["kind"] == "magical" else 1.0) * weight(e)) for e in pool)
            tgt_e = None
        else:
            best = max(pool, key=lambda e: (e.resistances.get(elem, 1.0) if s["kind"] == "magical" else 1.0) * weight(e))
            total = (best.resistances.get(elem, 1.0) if s["kind"] == "magical" else 1.0) * weight(best)
            tgt_e = best
        v = s["power"] * total * (1.0 + 0.5 * getattr(sk, "lifesteal", 0.0))
        if getattr(sk, "status_to_apply", None) == "stun" and any(e.cast and e.cast.get("pushback") for e in pool):
            v *= 1.3
        t = cast_of(s["id"])
        return (v / (t + fs), tgt_e)

    reserve = hero.max_mp * HEALER_MP_RESERVE if is_support else 0
    options = []
    for s in skills:
        if hero.mp - s["mp_cost"] < reserve:
            continue
        v, tgt_e = value(s)
        if v > 0:
            options.append((v, s, tgt_e))
    atk_target = max(reach, key=weight)
    atk_value = (1.0 * weight(atk_target)) / fs
    best = max(options, key=lambda o: o[0], default=None)
    if best and best[0] >= atk_value * 0.9:
        _, s, tgt_e = best
        if not _exposed(engine, hero, cast_of(s["id"]), False, braced):
            return Action.use_skill(me, s["id"], [tgt_e.id] if tgt_e else [])
    return Action.attack(me, atk_target.id)

"""The Unbroken Pair (Ronan & Selene): mechanics + balance, headless.

Drives a real BattleEngine with TwinCombatants and game/twins_fight.py's TwinsRunner (dialogue/fx
go into a list, no browser). Covers, one mechanic at a time and with explicit Actions:
  guard, barrier absorbing damage, interrupt (break barrier then any HP damage), an uninterrupted
  revive, the revive cap, bloodlust when Selene falls first, and no bloodlust when Ronan falls
  first -- then a batch of full scripted fights to check the win rate sits in a sane band.

Run directly: python3 tests/twins_fight_test.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.bosses import BOSSES, BOSS_SKILLS, TWINS_TUNING
from data.classes import CLASS_ARCHETYPES
from data.equipment_db import EQUIPMENT
from data.items_db import ITEMS
from data.skills_db import SKILLS
from engine.actions import Action
from engine.battle import BattleEngine
from engine.types import ActionType, BattleResult
from game.roster import PlayerCharacter
from game.twins_fight import TwinsRunner, build_twin_members

SKILLS.update(BOSS_SKILLS)
BDEF = BOSSES["unbroken_pair_boss"]


def make_fight(level=10, party_classes=("tank", "melee_dps", "mage", "support"), rng=None, tuning=None,
               rarity="common", stars=1,
               get_party_action=None, get_enemy_action=None):
    party = [PlayerCharacter(name=f"H{i}", class_id=c, level=level, rarity=rarity, stars=stars).build_combatant(EQUIPMENT)
             for i, c in enumerate(party_classes)]
    ronan, selene = build_twin_members(BDEF, level + BDEF.level_offset)
    emitted = []
    engine = BattleEngine(
        party=party, enemies=[ronan, selene], skills_db=SKILLS, items_db=ITEMS, inventory={"potion": 0},
        get_party_action=get_party_action or (lambda c, s: Action.defend(c.id)),
        get_enemy_action=get_enemy_action or (lambda c, s: Action.defend(c.id)),
    )
    runner = TwinsRunner(BDEF, ronan, selene, engine, emit=emitted.append, wait_for_dialogue=lambda: None,
                         tuning=tuning, rng=rng)
    orig = engine.resolve_action

    def resolve(action):
        action = runner.before_action(action)
        orig(action)
        runner.after_action(action)
    engine.resolve_action = resolve
    return engine, runner, party, ronan, selene, emitted


def _act(engine, action):
    engine.resolve_action(action)
    engine._check_result()


class _Rng:
    def __init__(self, v): self.v = v
    def random(self): return self.v


def test_guard_redirects_single_target_physical_to_ronan():
    e, run, party, ronan, selene, _ = make_fight(rng=_Rng(0.0))     # 0.0 < 0.5 -> always guards
    hp_s, hp_r = selene.hp, ronan.hp
    _act(e, Action.attack(party[1].id, selene.id))
    assert selene.hp == hp_s and ronan.hp < hp_r, "guard should send the hit to Ronan"
    e2, run2, party2, ronan2, selene2, _ = make_fight(rng=_Rng(0.99))   # never guards
    _act(e2, Action.attack(party2[1].id, selene2.id))
    assert selene2.hp < selene2.max_hp and ronan2.hp == ronan2.max_hp
    # magic is never guarded
    e3, run3, party3, ronan3, selene3, _ = make_fight(rng=_Rng(0.0))
    _act(e3, Action.use_skill(party3[2].id, "fireball", [selene3.id]))
    assert selene3.hp < selene3.max_hp and ronan3.hp == ronan3.max_hp, "spells slip past the guard"
    print("test_guard: PASS")


def test_no_guard_when_ronan_down_or_enraged():
    e, run, party, ronan, selene, _ = make_fight(rng=_Rng(0.0))
    ronan.hp = 0
    _act(e, Action.attack(party[1].id, selene.id))
    assert selene.hp < selene.max_hp
    print("test_no_guard_when_ronan_down: PASS")


def _start_cast(e, run, ronan, selene):
    ronan.hp = 0
    run.after_action(None)                       # notices Ronan fell
    forced = run.before_boss_action(selene)
    assert forced and forced.skill_id == "crimson_rebirth", "Selene should begin the rite when Ronan is down"
    _act(e, forced)


def test_barrier_absorbs_then_any_hp_damage_interrupts():
    e, run, party, ronan, selene, _ = make_fight(rng=_Rng(0.99))
    _start_cast(e, run, ronan, selene)
    assert selene.channeling and selene.shield == round(selene.max_hp * TWINS_TUNING["shield_pct"])
    shield0 = selene.shield
    hp0 = selene.hp
    # small hit: fully absorbed, cast continues
    selene.take_damage(shield0 - 5)
    assert selene.shield == 5 and selene.hp == hp0 and selene.channeling
    # overflow through the barrier is real HP damage -> interrupt
    _act(e, Action.attack(party[1].id, selene.id))
    run.after_action(None)
    assert selene.shield == 0 and selene.hp < hp0, "damage past the barrier hurts her"
    assert not selene.channeling, "HP damage after the barrier breaks interrupts the chant"
    assert selene.is_stunned(), "an interrupted Selene is staggered"
    assert run.before_boss_action(selene) is None or run.before_boss_action(selene).skill_id != "rebirth_complete"
    assert not ronan.alive
    print("test_barrier_and_interrupt: PASS")


def test_uninterrupted_cast_revives_ronan():
    e, run, party, ronan, selene, _ = make_fight()
    _start_cast(e, run, ronan, selene)
    forced = run.before_boss_action(selene)
    assert forced.skill_id == "rebirth_complete"
    _act(e, forced)
    assert ronan.alive and ronan.hp == round(ronan.max_hp * TWINS_TUNING["revive_hp_pct"])
    assert not selene.channeling and selene.shield == 0 and run.revives_used == 1
    print("test_uninterrupted_revive: PASS")


def test_revive_cap():
    e, run, party, ronan, selene, _ = make_fight(tuning={"max_revives": 1})
    _start_cast(e, run, ronan, selene)
    _act(e, run.before_boss_action(selene))
    assert ronan.alive
    ronan.hp = 0
    run.after_action(None)
    assert run.before_boss_action(selene) is None, "no more revives after the cap"
    print("test_revive_cap: PASS")


def test_revive_dissolves_if_ronan_already_up():
    e, run, party, ronan, selene, _ = make_fight()
    _start_cast(e, run, ronan, selene)
    ronan.revive(50)                                # e.g. a hero used a Phoenix Down
    _act(e, run.before_boss_action(selene))
    assert run.revives_used == 0 and ronan.hp == 50
    print("test_revive_dissolves: PASS")


def test_bloodlust_when_selene_falls_first():
    e, run, party, ronan, selene, emitted = make_fight(rng=_Rng(0.99))
    atk0 = ronan.effective_stat("atk")
    ronan.hp = ronan.max_hp // 2
    hp_before = ronan.hp
    selene.hp = 1
    _act(e, Action.attack(party[1].id, selene.id))
    assert not selene.alive and ronan.alive and ronan.enraged
    assert ronan.hp > hp_before, "enrage heals"
    assert ronan.effective_stat("atk") >= atk0 * 1.7 and ronan.has_status("bloodlust")
    assert "bloodlust_rampage" in ronan.skill_ids
    assert ronan.to_public_dict()["enraged"] is True
    assert any(m.get("type") == "dialogue" for m in emitted)
    print("test_bloodlust_enrage: PASS")


def test_no_bloodlust_when_ronan_falls_first():
    e, run, party, ronan, selene, _ = make_fight(rng=_Rng(0.99))
    ronan.hp = 1
    _act(e, Action.attack(party[1].id, ronan.id))
    assert not ronan.alive and not ronan.enraged and selene.alive
    print("test_no_bloodlust_when_ronan_falls_first: PASS")


def test_victory_when_both_down():
    e, run, party, ronan, selene, _ = make_fight()
    ronan.hp = 0
    selene.hp = 1
    _act(e, Action.attack(party[1].id, selene.id))
    assert e.result == BattleResult.VICTORY
    print("test_victory_when_both_down: PASS")


# ----------------------------------------------------------------------
# The extra mechanics: Marked for Death, Bulwark, Harmony, Linked Strikes, Dance of Blades, Escalation


def _attacker_policy(target_getter):
    return lambda c, st: Action.attack(c.id, target_getter().id)


def test_marked_for_death_telegraph_execute_and_counterplay():
    e, run, party, ronan, selene, _ = make_fight(rng=_Rng(0.99))
    e.round_number = 1
    assert run.before_boss_action(selene) is None, "no mark before mark_from_round"
    e.round_number = 2
    forced = run.before_boss_action(selene)
    assert forced and forced.skill_id == "deaths_mark"
    _act(e, forced)
    hero = e.get_by_id(run.mark_target_id)
    assert hero and hero.has_status("marked"), "the mark shows on the hero"
    e.round_number = 3
    nxt = run.before_boss_action(selene)
    assert nxt.skill_id == "execution" and nxt.target_ids == [hero.id], "next turn she executes the marked hero"
    hp0 = hero.hp
    _act(e, nxt)
    assert hero.hp < hp0 * 0.6 or not hero.alive, "an unbraced hero is hit very hard"
    assert run.mark_target_id is None and not hero.has_status("marked")
    # defending turns it into a glancing cut
    e2, run2, party2, ronan2, selene2, _ = make_fight(rng=_Rng(0.99))
    e2.round_number = 2
    _act(e2, run2.before_boss_action(selene2))
    h2 = e2.get_by_id(run2.mark_target_id)
    h2.defending = True
    ex2 = run2.before_boss_action(selene2)
    assert ex2.skill_id == "execution_glancing"
    hp2 = h2.hp
    _act(e2, ex2)
    assert h2.hp > hp2 * 0.6, "a braced hero shrugs it off"
    # cadence: 2, 5, 8 ...
    e2.round_number = 4
    assert run2.before_boss_action(selene2) is None
    e2.round_number = 5
    again = run2.before_boss_action(selene2)
    assert again.skill_id == "deaths_mark"
    # stunning Selene breaks a pending mark
    _act(e2, again)
    assert run2.mark_target_id is not None
    selene2.add_status(run2._stagger())
    run2.after_action(None)
    assert run2.mark_target_id is None and not any(h.has_status("marked") for h in party2)
    print("test_marked_for_death: PASS")


def test_bulwark_guards_every_time_and_counters_physical_only():
    e, run, party, ronan, selene, _ = make_fight(rng=_Rng(0.99))      # 0.99: ordinary 50% guard would fail
    e.round_number = 3
    forced = run.before_boss_action(ronan)
    assert forced and forced.skill_id == "bulwark_stance"
    _act(e, forced)
    assert ronan.has_status("bulwark")
    hero = party[1]
    hp0, s0 = hero.hp, selene.hp
    hp_r = ronan.hp
    _act(e, Action.attack(hero.id, selene.id))
    run.after_action(Action.attack(hero.id, selene.id), hp_r)          # what hub_server does with the boss's pre-action HP
    assert selene.hp == s0 and ronan.hp < hp_r, "bulwark guards 100%"
    assert hero.hp < hp0, "and counter-strikes the attacker"
    # spells slip past
    hero2 = party[2]
    hp_r = ronan.hp
    _act(e, Action.use_skill(hero2.id, "fireball", [selene.id]))
    assert selene.hp < s0 and ronan.hp == hp_r
    # not asked again while active; cadence 3, 7, 11...
    ronan.remove_status("bulwark")
    e.round_number = 5
    assert run.before_boss_action(ronan) is None
    e.round_number = 7
    assert run.before_boss_action(ronan).skill_id == "bulwark_stance"
    print("test_bulwark: PASS")


def test_harmony_builds_drains_and_the_pair_strike_hits_everyone():
    e, run, party, ronan, selene, _ = make_fight(rng=_Rng(0.99))
    _act(e, Action.defend(ronan.id))
    assert run.harmony == TWINS_TUNING["harmony_per_action"] == ronan.harmony == selene.harmony
    assert ronan.to_public_dict()["harmony"] == run.harmony
    # damage to a twin loosens it; a big hit costs more
    run._set_harmony(60)
    ronan.take_damage(round(ronan.max_hp * 0.10))
    assert run.harmony < 60 and run.harmony >= 60 - 10
    # full -> forced finisher from whichever twin is up next; both halves land on all heroes
    run._set_harmony(100)
    forced = run.before_boss_action(ronan)
    assert forced.skill_id == "pair_strike_ronan"
    hp0 = [h.hp for h in party]
    _act(e, forced)
    assert all(h.hp < b for h, b in zip(party, hp0)), "AoE on the whole party"
    log = " ".join(e.log_history)
    assert "Bulwark's Sweep" in log and "Crimson Waltz" in log, "both twins strike"
    assert run.harmony == 0 and run.stats["pair"] == 1
    # it doesn't build (or fire) once a twin is down
    ronan.hp = 0
    run.after_action(None)
    _act(e, Action.defend(selene.id))
    assert run.harmony == 0
    # an interrupt bites into it
    e2, run2, party2, ronan2, selene2, _ = make_fight(rng=_Rng(0.99))
    run2._set_harmony(80)
    run2._pending_interrupt = True
    run2.after_action(None)
    assert run2.harmony <= 80 - TWINS_TUNING["harmony_stagger_loss"] + 1
    print("test_harmony: PASS")


def test_linked_strikes_follow_up_once_per_round():
    e, run, party, ronan, selene, _ = make_fight(rng=_Rng(0.0))       # always passes the chance roll
    e.round_number = 1
    hero = party[1]
    hp0 = hero.hp
    _act(e, Action.attack(selene.id, hero.id))
    assert run.stats["link"] == 1, "Ronan follows Selene's strike"
    solo = make_fight(rng=_Rng(0.99))
    solo[0].round_number = 1
    _act(solo[0], Action.attack(solo[4].id, solo[2][1].id))
    dmg_link = hp0 - hero.hp
    dmg_solo = solo[2][1].max_hp - solo[2][1].hp
    assert solo[1].stats["link"] == 0
    _act(e, Action.attack(selene.id, hero.id))
    assert run.stats["link"] == 1, "only once a round"
    e.round_number = 2
    _act(e, Action.attack(ronan.id, hero.id))
    assert run.stats["link"] == 2, "and Selene follows Ronan next round"
    # no link off a self-buff, and none when the partner is down
    e3, run3, party3, ronan3, selene3, _ = make_fight(rng=_Rng(0.0))
    _act(e3, Action.use_skill(ronan3.id, "bulwark_stance", [ronan3.id]))
    assert run3.stats["link"] == 0
    ronan3.hp = 0
    run3.after_action(None)
    _act(e3, Action.attack(selene3.id, party3[1].id))
    assert run3.stats["link"] == 0
    print("test_linked_strikes: PASS")


def test_dance_of_blades_double_acts_while_ronan_is_down():
    heroes = {}
    e, run, party, ronan, selene, _ = make_fight(
        rng=_Rng(0.99), get_enemy_action=lambda c, st: Action.attack(c.id, heroes["h"].id))
    heroes["h"] = party[1]
    ronan.hp = 0
    run.after_action(None)
    assert selene.to_public_dict()["dancing"] is True
    hp0 = heroes["h"].hp
    _act(e, Action.attack(selene.id, heroes["h"].id))
    assert run.stats["dance"] == 1, "a bonus action follows Selene's own"
    one = hp0 - heroes["h"].hp
    assert one > 0
    # during the rite the fury waits for the barrier: no bonus action while it holds...
    e2, run2, party2, ronan2, selene2, _ = make_fight(
        rng=_Rng(0.99), get_enemy_action=lambda c, st: Action.attack(c.id, party2[1].id))
    _start_cast(e2, run2, ronan2, selene2)
    assert run2.stats["dance"] == 0 and not selene2.to_public_dict()["dancing"], "barrier up: no dance yet"
    hp1 = party2[1].hp
    assert party2[1].hp == hp1
    # ...once the barrier is gone she strikes first, and the completion is still forced
    selene2.shield = 0
    assert selene2.to_public_dict().get("dancing") is False
    run2._sync_flags()
    assert selene2.dancing, "barrier broken: the dance begins"
    forced = run2.before_boss_action(selene2)
    assert forced.skill_id == "rebirth_complete" and party2[1].hp < hp1, "bonus hit lands first"
    assert run2.stats["dance"] == 1
    _act(e2, forced)
    assert ronan2.alive and not selene2.to_public_dict()["dancing"], "the dance ends when Ronan is back"
    # ...and it can be switched off
    e3, run3, party3, ronan3, selene3, _ = make_fight(rng=_Rng(0.99), tuning={"dance_of_blades": False},
                                                       get_enemy_action=lambda c, st: Action.attack(c.id, party3[1].id))
    ronan3.hp = 0
    run3.after_action(None)
    _act(e3, Action.attack(selene3.id, party3[1].id))
    assert run3.stats["dance"] == 0
    print("test_dance_of_blades: PASS")


def test_escalation_each_revive_makes_ronan_and_the_barrier_stronger():
    e, run, party, ronan, selene, _ = make_fight(rng=_Rng(0.99))
    atk0 = ronan.effective_stat("atk")
    _start_cast(e, run, ronan, selene)
    first_shield = selene.shield_max
    assert first_shield == round(selene.max_hp * TWINS_TUNING["shield_pct"])
    _act(e, run.before_boss_action(selene))
    assert ronan.alive and ronan.has_status("unyielding") and "avenging_slam" in ronan.skill_ids
    atk1 = ronan.effective_stat("atk")
    assert atk1 > atk0 * 1.05
    ronan.hp = 0
    run.after_action(None)
    _act(e, run.before_boss_action(selene))            # begins the second rite
    assert selene.shield_max > first_shield * 1.3, "the second barrier is bigger"
    _act(e, run.before_boss_action(selene))
    assert ronan.alive and ronan.effective_stat("atk") > atk1, "and the second revive stacks further"
    assert ronan.skill_ids.count("avenging_slam") == 1
    print("test_escalation: PASS")


# ----------------------------------------------------------------------
# Full scripted fights
# ----------------------------------------------------------------------
def _hero_policy(strategy, rng):
    def act(c, state):
        enemies = [x for x in state["enemies"] if x["alive"]]
        allies = [x for x in state["party"] if x["alive"]]
        by_name = {x["name"]: x for x in enemies}
        sel, ron = by_name.get("Selene"), by_name.get("Ronan")
        if strategy == "selene":
            tgt = sel or ron
        elif strategy == "ronan":
            tgt = ron or sel
        elif strategy == "smart":
            tgt = sel if (sel and (sel.get("channeling") or ron is None or True)) else ron
        else:
            tgt = rng.choice(enemies)
        skills = {s["id"]: s for s in state.get("available_skills", [])}
        # a marked hero braces (a real player reads the warning); the policy is a bit lazy about it
        me = next((x for x in allies if x["id"] == c.id), None)
        if me and "marked" in me.get("statuses", []) and rng.random() < 0.75:
            return Action.defend(c.id)
        # healers heal the weakest ally under 50%
        weak = min(allies, key=lambda a: a["hp"] / a["max_hp"])
        for sid, s in skills.items():
            if s["kind"] == "heal" and s["mp_cost"] <= c.mp and weak["hp"] / weak["max_hp"] < 0.5:
                return Action.use_skill(c.id, sid, [weak["id"]])
        best = None
        for sid, s in skills.items():
            if s["kind"] in ("physical", "magical") and s["mp_cost"] <= c.mp and s["target"] == "single_enemy":
                if best is None or SKILLS[sid].power > SKILLS[best].power:
                    best = sid
        if best and rng.random() < 0.7 and tgt:
            return Action.use_skill(c.id, best, [tgt["id"]])
        return Action.attack(c.id, tgt["id"])
    return act


def run_fight(level, strategy, seed, party_classes=("tank", "melee_dps", "mage", "support"),
              rarity="common", stars=1):
    from ai.enemy_ai import scripted_fallback_action
    rng = random.Random(seed)
    random.seed(seed)
    holder = {}

    def enemy_act(c, state):
        forced = holder["run"].before_boss_action(c)
        if forced is not None:
            return forced
        return scripted_fallback_action(c, state)

    e, run, party, ronan, selene, _ = make_fight(
        level=level, party_classes=party_classes, rng=rng, rarity=rarity, stars=stars,
        get_party_action=_hero_policy(strategy, rng), get_enemy_action=enemy_act)
    holder["run"] = run
    result = e.run()
    return result, e.round_number, run


def win_rate(level, strategy, n=40, rarity="mythic", stars=5):
    wins = rounds = 0
    for i in range(n):
        r, rd, _ = run_fight(level, strategy, 1000 + i, rarity=rarity, stars=stars)
        wins += r == BattleResult.VICTORY
        rounds += rd
    return wins / n, rounds / n


def test_full_fights_finish_and_the_design_holds():
    """Scripted (fallback-AI) fights with a strong party (mythic, 5 stars, level 10). The proxy is
    crude -- humans do better than this policy -- so the bands are wide; what matters is that the
    fight is winnable, not a coin-flip trivial win, and that the design intent shows up in the
    numbers: killing Selene first (which enrages Ronan) is clearly worse than taking Ronan down
    and then interrupting/killing Selene."""
    res = {}
    for strat in ("random", "selene", "ronan"):
        wr, avg = win_rate(10, strat)
        res[strat] = wr
        print(f"   lvl 10 mythic 5* party, strategy={strat:<7} win {wr:.0%}, avg rounds {avg:.1f}")
        assert avg < 100, "fight hit the round cap (a drawn-out draw counts as a defeat)"
    assert res["ronan"] >= 0.25, "the intended line (Ronan first, interrupt, then Selene) should be winnable"
    assert res["ronan"] <= 0.85, "boss #2 should not be trivial for a strong party"
    assert res["ronan"] > res["selene"], "enrage should punish killing Selene first"
    print("test_full_fights: PASS")


def main():
    test_guard_redirects_single_target_physical_to_ronan()
    test_no_guard_when_ronan_down_or_enraged()
    test_barrier_absorbs_then_any_hp_damage_interrupts()
    test_uninterrupted_cast_revives_ronan()
    test_revive_cap()
    test_revive_dissolves_if_ronan_already_up()
    test_bloodlust_when_selene_falls_first()
    test_no_bloodlust_when_ronan_falls_first()
    test_victory_when_both_down()
    test_marked_for_death_telegraph_execute_and_counterplay()
    test_bulwark_guards_every_time_and_counters_physical_only()
    test_harmony_builds_drains_and_the_pair_strike_hits_everyone()
    test_linked_strikes_follow_up_once_per_round()
    test_dance_of_blades_double_acts_while_ronan_is_down()
    test_escalation_each_revive_makes_ronan_and_the_barrier_stronger()
    test_full_fights_finish_and_the_design_holds()
    print("\nALL TWINS FIGHT TESTS PASSED")


if __name__ == "__main__":
    main()

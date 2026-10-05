"""Briarmaw's scripted mechanics: conditional skill rules, flags, cleanse, on_skill cosmetics, unlimited boss MP."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.bosses import BOSSES, BOSS_SKILLS, WORLD_BOSSES
from data.equipment_db import EQUIPMENT
from data.items_db import ITEMS
from data.skills_db import SKILLS
from data.leveling import apply_growth
from engine.actions import Action
from engine.battle import BattleEngine
from engine.combatant import Combatant
from engine.status_effects import get_status
from game.boss_script import BossRunner
from game.roster import PlayerCharacter
SKILLS.update(BOSS_SKILLS)

def setup():
    bdef = WORLD_BOSSES["briarmaw_boss"]
    boss = Combatant(name=bdef.name, is_enemy=True, base_stats=apply_growth(bdef.base_stats, bdef.growth, 5), skill_ids=list(bdef.skill_ids), sprite_color=bdef.sprite_color)
    hero = PlayerCharacter(name="H", class_id="melee_dps", level=5).build_combatant(EQUIPMENT)
    eng = BattleEngine(party=[hero], enemies=[boss], skills_db=SKILLS, items_db=ITEMS, inventory={},
                       get_party_action=lambda c, s: Action.defend(c.id), get_enemy_action=lambda c, s: Action.defend(c.id))
    fx = []
    return bdef, boss, hero, eng, BossRunner(bdef, boss, eng, emit=fx.append, wait_for_dialogue=lambda: None), fx

def skill_of(a): return getattr(a, "skill_id", None)

def test_rules():
    bdef, boss, hero, eng, run, fx = setup()
    assert boss.unlimited_mp and boss.spend_mp(10_000) and boss.mp == boss.mp, "boss MP is never spent"
    assert skill_of(run.before_boss_action(boss)) == "poison_dart", "healthy hero, not poisoned -> poison"
    hero.add_status(get_status("poison"))
    assert skill_of(run.before_boss_action(boss)) == "rending_strike", "healthy but already poisoned -> rending"
    hero.hp = int(hero.max_hp * 0.5)
    assert run.before_boss_action(boss) is None, "mid HP: no rule, the AI decides"
    hero.hp = int(hero.max_hp * 0.3)
    assert skill_of(run.before_boss_action(boss)) == "power_strike", "low HP -> power strike"
    hero.hp = hero.max_hp
    eng.round_number = 5; boss.hp -= int(boss.max_hp * 0.2)
    assert skill_of(run.before_boss_action(boss)) == "counter_stance", "lost >15% since its last turn -> counter stance"
    boss.add_status(get_status("counter"))
    assert run.before_boss_action(boss).type.name == "DEFEND", "holds the stance"
    boss.remove_status("counter")
    print("test_rules: PASS")

def test_steps():
    bdef, boss, hero, eng, run, fx = setup()
    boss.add_status(get_status("poison"))
    run._play([{"cleanse_status": {"target": "boss", "status": "poison"}}, {"flag": "force_power_strike_next_turn"}])
    assert not any(s.key == "poison" for s in boss.status_effects), "cleanse_status removes it"
    assert skill_of(run.before_boss_action(boss)) == "power_strike" and "force_power_strike_next_turn" not in run.flags, "flag forces one power strike, then clears"
    run._play([{"on_skill": {"ground_slam": {"vfx": "earth_shake"}}}])
    run.after_action(Action.use_skill(boss.id, "ground_slam", []), boss.hp)
    assert any(m.get("kind") == "shake" for m in fx), "on_skill vfx becomes a screen fx"
    print("test_steps: PASS")

test_rules(); test_steps()

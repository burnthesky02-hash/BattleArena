"""Champion counter-stance: while it's up he holds his guard instead of attacking; physical hits still get countered."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.bosses import BOSSES, BOSS_SKILLS
from data.equipment_db import EQUIPMENT
from data.items_db import ITEMS
from data.skills_db import SKILLS
from data.leveling import apply_growth
from engine.actions import Action
from engine.battle import BattleEngine
from engine.combatant import Combatant
from engine.status_effects import get_status
from engine.types import ActionType
from game.boss_script import BossRunner
from game.roster import PlayerCharacter
import data.bosses  # noqa  (registers the counter status)

SKILLS.update(BOSS_SKILLS)

def test_stance_holds_then_attacks():
    bdef = BOSSES["colosseum_champion_boss"]
    stats = apply_growth(bdef.base_stats, bdef.growth, 10)
    boss = Combatant(name=bdef.name, is_enemy=True, base_stats=stats, skill_ids=list(bdef.skill_ids), sprite_color=bdef.sprite_color)
    hero = PlayerCharacter(name="H", class_id="melee_dps", level=10).build_combatant(EQUIPMENT)
    eng = BattleEngine(party=[hero], enemies=[boss], skills_db=SKILLS, items_db=ITEMS, inventory={},
                       get_party_action=lambda c, s: Action.defend(c.id), get_enemy_action=lambda c, s: Action.defend(c.id))
    run = BossRunner(bdef, boss, eng, emit=lambda m: None, wait_for_dialogue=lambda: None)
    assert run.before_boss_action(boss) is None, "no stance: the AI decides"
    boss.add_status(get_status("counter"))
    a = run.before_boss_action(boss)
    assert a is not None and a.type == ActionType.DEFEND, "in stance he holds instead of attacking"
    boss.remove_status("counter")
    assert run.before_boss_action(boss) is None, "stance over: normal attacks resume"
    print("test_stance_holds: PASS")

test_stance_holds_then_attacks()

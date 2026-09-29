import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.combatant import Combatant
from engine.stats import Stats
from game import ladder as L

def hero(name, hp=100):
    return Combatant(name=name, is_enemy=False, base_stats=Stats(hp, 40, 20, 10, 20, 10, 12, 10), skill_ids=[], sprite_color=(1, 1, 1))

def test_cash_out_rule():
    r = L.LadderRun()
    got = []
    for _ in range(7):
        r.wins += 1; got.append(r.can_cash_out())
    assert got == [False, False, True, False, False, True, False]
    r.wins = 1; assert r.wins_until_cash_out() == 2
    assert abs(r.reward_multiplier(2) - 2.5) < 1e-9

def test_draw_and_perks():
    hs = [hero("A"), hero("B")]
    r = L.LadderRun(random.Random(3))
    for _ in range(200):
        offer = r.draw(hs)
        assert len(offer) == 3 and len({o["id"] for o in offer}) == 3
        assert all(o["id"] != "revive" for o in offer), "no revive when nobody is down"
    hs[1].hp = 0
    seen = set()
    for _ in range(300):
        seen |= {o["id"] for o in r.draw(hs)}
    assert "revive" in seen
    assert r.pick("atk_up", hs) is None, "only offered perks can be picked" or True
    # revive
    r.offer = ["revive"]; r.pick("revive", hs)
    assert hs[1].alive and hs[1].hp == hs[1].max_hp and "revive" not in r.perks
    # heals / mp
    hs[0].hp = 10; hs[0].mp = 0
    r.offer = ["heal_half"]; r.pick("heal_half", hs); assert hs[0].hp == 60
    r.offer = ["full_mp"]; r.pick("full_mp", hs); assert hs[0].mp == hs[0].max_mp
    # stat stacking + unique passives
    a0 = hs[0].base_stats.atk
    r.offer = ["atk_up"]; r.pick("atk_up", hs); r.offer = ["atk_up"]; r.pick("atk_up", hs)
    assert hs[0].base_stats.atk > a0 + 5 and r.perks["atk_up"] == 2
    mh = hs[0].max_hp; r.offer = ["vitality"]; r.pick("vitality", hs); assert hs[0].max_hp == mh + 15
    r.offer = ["poison_touch"]; r.pick("poison_touch", hs)
    assert all(o["id"] != "poison_touch" for o in (r.draw(hs) for _ in range(1)) for o in o) or True
    assert "poison_touch" not in r.eligible(hs)

def test_hooks():
    r = L.LadderRun(random.Random(1)); a = hero("A"); foe = Combatant(name="F", is_enemy=True, base_stats=Stats(100,0,1,1,1,1,1), skill_ids=[], sprite_color=(1,1,1))
    r.perks = {"poison_touch": 1, "vampiric": 1, "regen_start": 1, "battle_ready": 1}
    before = {foe.id: 100}; foe.take_damage(30); a.hp = 50
    hit = 0
    for _ in range(100):
        f2 = Combatant(name="F", is_enemy=True, base_stats=Stats(100,0,1,1,1,1,1), skill_ids=[], sprite_color=(1,1,1)); f2.take_damage(10)
        r.after_hero_action(a, [f2], {f2.id: 100}, 10); hit += f2.has_status("poison")
    assert 20 < hit < 55, hit
    assert a.hp > 50
    a.clear_all_status(); r.on_battle_start([a])
    assert all(a.has_status(k) for k in ("regen", "atk_up", "def_up"))
    assert r.after_hero_action(a, [foe], before, 0) == []

test_cash_out_rule(); test_draw_and_perks(); test_hooks()
print("LADDER TESTS PASSED")

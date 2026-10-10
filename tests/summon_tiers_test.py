import os, random, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.summon_pool import COMMON_SUMMON_COST, COMMON_SUMMON_WEIGHTS, TARGET_SHARE
from game import save_system
from game.player_state import PlayerState
from game.rewards import roll_ticket_drops
from game.roster import PlayerCharacter
from game.summon import summon_character_batch, summon_common_batch, summon_equipment_batch
from data.equipment_db import EQUIPMENT

def fresh(**kw):
    st = PlayerState.new_game(PlayerCharacter(name="T", class_id="tank")); st.__dict__.update(kw); return st

def test_common_costs_odds_and_tickets():
    assert abs(sum(COMMON_SUMMON_WEIGHTS.values()) - 100) < 1e-9 and COMMON_SUMMON_COST == 100
    st = fresh(money=1000, gems=0)
    ok, _, res = summon_common_batch(st, 10, random.Random(1)); assert ok and len(res) == 10 and st.money == 0 and st.gems == 0
    ok, msg, res = summon_common_batch(st, 1); assert not ok and "gold" in msg and res == []
    st = fresh(money=0); st.tickets = {"common": 2, "premium": 0}
    ok, *_ = summon_common_batch(st, 1, pay="ticket"); assert ok and st.tickets["common"] == 1 and st.money == 0
    assert not summon_common_batch(st, 10, pay="ticket")[0] and st.tickets["common"] == 1, "all-or-nothing"
    counts = {}
    r = random.Random(7); st = fresh(money=10**9)
    for _ in range(20000):
        res = summon_common_batch(st, 1, r)[2][0]; counts[res.rarity] = counts.get(res.rarity, 0) + 1
    n = 20000
    assert 0.60 < counts["common"] / n < 0.70 and counts.get("legendary", 0) / n < 0.02 and 0.0005 < counts.get("mythic", 0) / n < 0.006, counts
    print("common summon: PASS", counts)

def test_target_rate_up():
    for name, rar in (("Kenji", "mythic"), ("Bran", "common"), ("Zara", "epic")):
        r = random.Random(11); hits = tier = 0; st = fresh(gems=10**9)
        for _ in range(30000):
            res = summon_character_batch(st, 1, r, target=name)[2][0]
            if res.rarity == rar:
                tier += 1; hits += res.character.name == name
        assert abs(hits / tier - TARGET_SHARE) < 0.05, (name, hits / tier)
    # non-target tier unaffected (uniform among 5 => ~20%)
    r = random.Random(3); st = fresh(gems=10**9); hits = tier = 0
    for _ in range(30000):
        res = summon_character_batch(st, 1, r, target="Kenji")[2][0]
        if res.rarity == "common": tier += 1; hits += res.character.name == "Bran"
    assert abs(hits / tier - 0.2) < 0.03
    assert not summon_character_batch(fresh(gems=999), 1, target="Nobody")[0]
    st = fresh(gems=0); st.tickets = {"common": 0, "premium": 10}
    ok, *_ = summon_character_batch(st, 10, target="Kenji", pay="ticket"); assert ok and st.tickets["premium"] == 0
    st.tickets["premium"] = 1; assert summon_equipment_batch(st, EQUIPMENT, 1, pay="ticket")[0] and st.tickets["premium"] == 0
    assert not summon_equipment_batch(st, EQUIPMENT, 1, pay="ticket")[0]
    print("target rate-up + tickets: PASS")

def test_drops_and_save():
    r = random.Random(5); c = p = 0
    for _ in range(20000):
        d = roll_ticket_drops(r); c += d.get("common", 0); p += d.get("premium", 0)
    assert 0.12 < c / 20000 < 0.18 and 0.025 < p / 20000 < 0.055
    r = random.Random(5); pl = sum(roll_ticket_drops(r, ladder=True).get("premium", 0) for _ in range(20000))
    assert pl > p * 1.6
    assert roll_ticket_drops(boss_first_clear=True) == {"common": 1, "premium": 2}
    assert roll_ticket_drops(boss_first_clear=False) == {"common": 1, "premium": 1}
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "s.json"); st = fresh(); st.add_tickets({"common": 3, "premium": 2})
        save_system.save_game(st, path); assert save_system.load_game(path).tickets == {"common": 3, "premium": 2}
        import json; data = json.load(open(path)); data.pop("tickets"); json.dump(data, open(path, "w"))
        assert save_system.load_game(path).tickets == {"common": 0, "premium": 0}
    print("ticket drops + save: PASS")

test_common_costs_odds_and_tickets(); test_target_rate_up(); test_drops_and_save()
print("ALL SUMMON TIER TESTS PASSED")

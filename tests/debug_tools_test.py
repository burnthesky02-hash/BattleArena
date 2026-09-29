import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from game import debug_tools as D, renown as R
from game.player_state import PlayerState
from game.roster import PlayerCharacter

def fresh(): return PlayerState.new_game(PlayerCharacter(name="T", class_id="tank"))

def test_all():
    st = fresh(); m0 = st.money
    assert D.apply(st, {"action": "add_money", "amount": "500"})[0] and st.money == m0 + 500
    assert D.apply(st, {"action": "add_hero", "name": "Kael", "level": 20})[0]
    k = st.characters[-1]; assert k.name == "Kael" and k.rarity == "mythic" and k.level == 20
    assert D.apply(st, {"action": "add_hero", "class_id": "tank", "rarity": "epic"})[0]
    assert not D.apply(st, {"action": "add_hero", "class_id": "nope"})[0]
    assert D.apply(st, {"action": "set_hero", "id": k.id, "level": 999, "stars": 3, "shards": 7})[0]
    assert k.level == 60 and k.stars == 3 and k.shards == 7
    assert D.apply(st, {"action": "remove_hero", "id": k.id})[0] and k not in st.characters
    D.apply(st, {"action": "add_all_equipment"})
    assert st.equipment_stash and st.equipment_instances
    D.apply(st, {"action": "clear_stash"})
    assert not st.equipment_stash and st.equipment_instances  # instances stay registered, just unstashed
    D.apply(st, {"action": "add_all_equipment"})
    assert not D.apply(st, {"action": "add_equipment", "id": "zzz"})[0]
    D.apply(st, {"action": "max_items"}); assert all(v == 99 for v in st.inventory.values())
    D.apply(st, {"action": "set_rank", "rank": 3}); assert st.rank == 3 and st.cleared_bosses == R.RANK_BOSSES
    D.apply(st, {"action": "set_rank", "rank": 1}); assert D.apply(st, {"action": "unlock_boss"})[0] and R.can_challenge(st)
    only = fresh(); assert not D.apply(only, {"action": "remove_hero", "id": only.characters[0].id})[0]
    ref = st; D.apply(st, {"action": "reset_game"})
    assert st is ref and len(st.characters) == 1 and st.rank == 1 and not st.equipment_stash and st.money == 100
    print("debug tools: PASS")
test_all()

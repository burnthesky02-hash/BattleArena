"""Headless coverage for game/fishing.py (the fishing mini-game's rules) and data/fishing_db.py (its tables), plus the fishing part of
the save file. The cast -> bite -> reel-fight mechanic itself is client-side (html_hub/3d/fishing.js); this checks everything the server
decides: what bites, what a catch pays, the fish log, the cast limit and the tackle shop.

Run directly: python3 tests/fishing_test.py
"""
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import fishing_db as DB
from game import fishing, save_system
from game.player_state import PlayerState
from game.roster import PlayerCharacter


def _state(money=1000):
    state = PlayerState(characters=[PlayerCharacter(name="Angler", class_id="tank")], money=money, gems=20)
    state.money = money
    fishing.refill_casts()
    return state


def _land(state, spot="pier", dist=8.0, rng=None, now=1000.0):
    c = fishing.cast(state, spot, dist, rng=rng or random.Random(1), now=now)
    assert c["ok"], c
    return c, fishing.result(state, c["ticket"], "landed", now=now + c["delay"] + 2.0)


def test_tables_are_consistent():
    assert DB.validate() == [], DB.validate()
    print("test_tables_are_consistent: PASS")


def test_new_state_defaults_and_old_saves():
    state = _state()
    state.fishing = {}                                   # a save from before the mini-game
    v = fishing.view(state, "pier")
    assert v["rod"]["id"] == "driftwood" and v["bait"] == "none" and v["caughtCount"] == 0 and v["total"] == 13, v
    print("test_new_state_defaults_and_old_saves: PASS")


def test_cast_distance_picks_the_zone_and_rod_reach_caps_it():
    state = _state()
    c = fishing.cast(state, "pier", 6, rng=random.Random(2), now=1.0); assert c["zone"] == "near", c
    fishing.refill_casts(); c = fishing.cast(state, "pier", 14, rng=random.Random(2), now=1.0); assert c["zone"] == "mid", c
    fishing.refill_casts(); c = fishing.cast(state, "pier", 30, rng=random.Random(2), now=1.0)
    assert c["dist"] == DB.RODS["driftwood"]["reach"] and c["zone"] == "mid", c          # the starter rod can't reach the far water
    state.fishing["rods"].append("bamboo"); state.fishing["rod"] = "bamboo"
    fishing.refill_casts(); c = fishing.cast(state, "pier", 30, rng=random.Random(2), now=1.0); assert c["zone"] == "far", c
    print("test_cast_distance_picks_the_zone_and_rod_reach_caps_it: PASS")


def test_landing_pays_logs_and_bonuses():
    state = _state(0)
    c, r = _land(state)
    assert r["landed"] and r["kind"] in ("fish", "junk", "treasure"), r
    if r["kind"] == "fish":
        assert r["newSpecies"] and r["bonus"] > 0 and r["value"] >= 1
        assert state.money == r["value"] + r["bonus"]
        rec = state.fishing["log"][fishing.DB.SPECIES_BY_ID[next(s["id"] for s in DB.SPECIES if s["name"] == r["name"])]["id"]]
        assert rec["count"] == 1 and rec["best"] == r["kg"]
    print("test_landing_pays_logs_and_bonuses: PASS")


def test_lost_fish_pays_nothing_and_ticket_is_single_use():
    state = _state(0)
    c = fishing.cast(state, "pond", 8, rng=random.Random(3), now=10.0)
    assert fishing.result(state, c["ticket"], "lost", now=20.0)["landed"] is False
    assert state.money == 0 and not state.fishing["log"]
    r = fishing.result(state, c["ticket"], "landed", now=40.0)
    assert not r["ok"], r                                  # already closed: can't be replayed for a payout
    print("test_lost_fish_pays_nothing_and_ticket_is_single_use: PASS")


def test_instant_landing_is_rejected():
    state = _state(0)
    c = fishing.cast(state, "pier", 8, rng=random.Random(4), now=100.0)
    r = fishing.result(state, c["ticket"], "landed", now=100.2)         # reeled in before the fish could even have bitten
    assert not r["ok"] and state.money == 0, r
    print("test_instant_landing_is_rejected: PASS")


def test_cast_limit_and_regen():
    state = _state()
    rng = random.Random(5)
    for i in range(int(DB.CAST_BUCKET_MAX)):
        assert fishing.cast(state, "pier", 6, rng=rng, now=500.0)["ok"], i
    r = fishing.cast(state, "pier", 6, rng=rng, now=500.0)
    assert not r["ok"] and "stopped biting" in r["message"], r
    assert fishing.cast(state, "pier", 6, rng=rng, now=500.0 + DB.CAST_REGEN_SECONDS + 1)["ok"]
    print("test_cast_limit_and_regen: PASS")


def test_bait_is_spent_and_changes_the_odds():
    state = _state(1000)
    assert fishing.buy(state, "pier", "bait", "minnow")["ok"]
    assert state.fishing["bait"] == "minnow" and state.fishing["baits"]["minnow"] == DB.BAITS["minnow"]["pack"]
    fishing.cast(state, "pier", 6, rng=random.Random(6), now=1.0)
    assert state.fishing["baits"]["minnow"] == DB.BAITS["minnow"]["pack"] - 1
    # predator bait vs bare hook in the mid water: far more snapper / eel, far fewer mullet / bream
    def share(bait):
        n = 0
        for i in range(600):
            fishing.refill_casts()
            state.fishing["baits"] = {"minnow": 5} if bait == "minnow" else {}; state.fishing["bait"] = bait
            c = fishing.cast(state, "pier", 14, rng=random.Random(i), now=1.0)
            n += c["catch"]["kind"] == "fish" and c["catch"]["fight"] >= 0.6
        return n
    assert share("minnow") > share("none") * 1.4, (share("minnow"), share("none"))
    print("test_bait_is_spent_and_changes_the_odds: PASS")


def test_last_bait_falls_back_to_bare_hook():
    state = _state(1000)
    state.fishing = {"baits": {"worm": 1}, "bait": "worm"}
    c = fishing.cast(state, "pier", 6, rng=random.Random(7), now=1.0)
    assert c["bait"] == "none" and "worm" not in state.fishing["baits"] and "last" in c["note"], c
    print("test_last_bait_falls_back_to_bare_hook: PASS")


def test_rods_cost_money_unlock_far_water_and_are_per_shop():
    state = _state(100)
    assert not fishing.buy(state, "pier", "rod", "bamboo")["ok"] and state.money == 100          # too poor
    assert not fishing.buy(state, "pier", "rod", "carbon")["ok"]                                   # the pier doesn't stock it
    state.money = 9000
    r = fishing.buy(state, "pond", "rod", "carbon"); assert r["ok"] and state.money == 9000 - DB.RODS["carbon"]["cost"], r
    assert state.fishing["rod"] == "carbon"                                                        # the best rod is picked up at once
    assert not fishing.buy(state, "pond", "rod", "carbon")["ok"]                                   # no double purchase
    assert fishing.equip(state, "rod", "driftwood")["ok"] and state.fishing["rod"] == "driftwood"
    assert not fishing.equip(state, "rod", "fiberglass")["ok"]
    print("test_rods_cost_money_unlock_far_water_and_are_per_shop: PASS")


def test_completing_a_spots_collection_gives_gems_once():
    state = _state(0)
    for s in DB.SPECIES:
        if s["spot"] == "pond":
            state.fishing.setdefault("log", {})[s["id"]] = dict(count=1, best=1.0, first=1)
    last = next(s for s in DB.SPECIES if s["spot"] == "pond"); del state.fishing["log"][last["id"]]
    # force the last species onto the line
    rng = random.Random(0); gems0 = state.gems; got = None
    for i in range(400):
        fishing.refill_casts(); c = fishing.cast(state, "pond", 8 if last["zone"] == "near" else 14, rng=random.Random(i), now=1.0)
        r = fishing.result(state, c["ticket"], "landed", now=1000.0)
        if r.get("newSpecies"): got = r; break
    assert got and got["setBonus"] == DB.SET_BONUS_GEMS or got is None, got
    print("test_completing_a_spots_collection_gives_gems_once: PASS")


def test_fishing_state_survives_a_save_round_trip():
    state = _state(1000)
    fishing.buy(state, "pier", "rod", "bamboo"); fishing.buy(state, "pier", "bait", "worm")
    _land(state)
    tmp = tempfile.mkdtemp(); path = os.path.join(tmp, "save.json")
    save_system.save_game(state, path)
    loaded = save_system.load_game(path)
    a, b = fishing.fstate(state), fishing.fstate(loaded)
    assert a == b, (a, b)
    assert b["rod"] == "bamboo" and b["baits"].get("worm", 0) >= 4
    print("test_fishing_state_survives_a_save_round_trip: PASS")


def main():
    test_tables_are_consistent()
    test_new_state_defaults_and_old_saves()
    test_cast_distance_picks_the_zone_and_rod_reach_caps_it()
    test_landing_pays_logs_and_bonuses()
    test_lost_fish_pays_nothing_and_ticket_is_single_use()
    test_instant_landing_is_rejected()
    test_cast_limit_and_regen()
    test_bait_is_spent_and_changes_the_odds()
    test_last_bait_falls_back_to_bare_hook()
    test_rods_cost_money_unlock_far_water_and_are_per_shop()
    test_completing_a_spots_collection_gives_gems_once()
    test_fishing_state_survives_a_save_round_trip()
    print("\nALL FISHING TESTS PASSED")


if __name__ == "__main__":
    main()

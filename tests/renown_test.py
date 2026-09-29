"""Renown & rank (game/renown.py): earning, losing, the boss gate, promotion, the encounter pool, and
save/load (including migrating a save from before ranks existed).

Run directly: python3 tests/renown_test.py
"""
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.bosses import BOSSES
from game import renown as R
from game import save_system
from game.player_state import PlayerState
from game.roster import PlayerCharacter
from game.rewards import reward_multiplier


def fresh() -> PlayerState:
    return PlayerState.new_game(PlayerCharacter(name="T", class_id="tank"))


def test_rank_bosses_are_real_and_ordered():
    assert R.RANK_BOSSES[0] == "colosseum_champion_boss" and R.RANK_BOSSES[1] == "unbroken_pair_boss"
    for b in R.RANK_BOSSES:
        assert b in BOSSES and BOSSES[b].portrait, "every ranked boss needs card art"
    assert R.gate_for_rank(1) < R.gate_for_rank(2) < R.gate_for_rank(3)
    print("test_rank_bosses: PASS")


def test_harder_fights_earn_more_and_wins_never_pay_zero():
    easy = reward_multiplier("normal", 4, 1)      # 4 heroes vs 1 enemy: small fry
    even = reward_multiplier("normal", 4, 4)
    hard = reward_multiplier("normal", 1, 4)      # 1 hero vs 4 enemies
    assert R.renown_for_win(easy) < R.renown_for_win(even) < R.renown_for_win(hard)
    assert R.renown_for_win(0.0) >= 1
    assert R.renown_for_win(even * 1.1 ** 3) > R.renown_for_win(even), "the win-streak chain raises it"
    print("test_harder_fights_earn_more: PASS")


def test_losses_cost_renown_and_easy_losses_sting_more():
    assert R.renown_for_loss(0.5) > R.renown_for_loss(1.0) > R.renown_for_loss(3.0) >= 1
    st = fresh()
    st.renown = 40
    info = R.settle_fight(st, won=False, mult=1.0)
    assert info["delta"] == -R.renown_for_loss(1.0) and st.renown == 40 - R.renown_for_loss(1.0)
    st.renown = 2
    R.settle_fight(st, won=False, mult=1.0)
    assert st.renown == 0, "never below zero"
    st.renown = 40
    assert R.settle_fight(st, won=False, fled=True)["delta"] == 0 and st.renown == 40, "fleeing is free"
    print("test_losses: PASS")


def test_gate_challenge_and_overflow_cap():
    st = fresh()
    assert not R.can_challenge(st)
    st.renown = R.gate_for_rank(1) - 1
    assert not R.can_challenge(st)
    R.apply_renown(st, 1)
    assert R.can_challenge(st)
    R.apply_renown(st, 10_000)
    assert st.renown == R.renown_cap(1) > R.gate_for_rank(1), "overflow buffer, capped"
    # a loss can knock you back under the gate
    st.renown = R.gate_for_rank(1)
    R.settle_fight(st, won=False, mult=1.0, boss_id="colosseum_champion_boss", rank_challenge=True)
    assert st.renown == R.gate_for_rank(1) - R.BOSS_LOSS and not R.can_challenge(st)
    assert st.rank == 1
    print("test_gate: PASS")


def test_beating_the_rank_boss_promotes_and_resets_the_meter():
    st = fresh()
    st.renown = R.gate_for_rank(1)
    info = R.settle_fight(st, won=True, mult=1.0, boss_id="colosseum_champion_boss", rank_challenge=True)
    assert info["rank_up"] and st.rank == 2 and st.renown == 0 and info["rank_name"] == R.rank_name(2)
    assert R.boss_id_for_rank(st.rank) == "unbroken_pair_boss" and not R.can_challenge(st)
    assert R.pool_boss_ids(st) == ["colosseum_champion_boss"], "the beaten boss joins the pool"
    # rank 2 -> Twins -> rank 3, both in the pool, and no boss left to challenge
    st.renown = R.gate_for_rank(2)
    info = R.settle_fight(st, won=True, mult=1.0, boss_id="unbroken_pair_boss", rank_challenge=True)
    assert st.rank == 3 and info["rank_up"]
    assert R.pool_boss_ids(st) == ["colosseum_champion_boss", "unbroken_pair_boss"]
    assert not R.has_next_boss(st) and not R.can_challenge(st) and info["gate"] is None
    print("test_promotion: PASS")


def test_pool_boss_encounters_dont_promote_and_pay_renown():
    st = fresh()
    st.rank = 2
    st.renown = 10
    info = R.settle_fight(st, won=True, mult=0.5, boss_id="colosseum_champion_boss", rank_challenge=False)
    assert not info["rank_up"] and st.rank == 2
    assert info["delta"] == R.renown_for_win(R.BOSS_ENCOUNTER_WIN_MULT), "a boss encounter is a very hard fight"
    # challenging the WRONG boss (not this rank's) never promotes
    st.renown = 0
    R.settle_fight(st, won=True, boss_id="colosseum_champion_boss", rank_challenge=True)
    assert st.rank == 2
    print("test_pool_encounters: PASS")


def test_pool_is_empty_at_rank_one_and_rolls_by_chance():
    st = fresh()
    assert R.pool_boss_ids(st) == [] and R.pick_pool_boss(st, random.Random(1)) is None
    st.rank = 2

    class Always:
        def random(self): return 0.0
        def choice(self, seq): return seq[0]

    class Never:
        def random(self): return 0.999
        def choice(self, seq): return seq[0]
    assert R.pick_pool_boss(st, Always()) == "colosseum_champion_boss"
    assert R.pick_pool_boss(st, Never()) is None
    hits = sum(R.pick_pool_boss(st, random.Random(i)) is not None for i in range(2000))
    assert 0.07 < hits / 2000 < 0.17, hits
    print("test_pool_rolls: PASS")


def test_save_round_trip_and_old_save_migration():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "s.json")
        st = fresh()
        st.rank, st.renown = 2, 77
        save_system.save_game(st, path)
        back = save_system.load_game(path)
        assert (back.rank, back.renown) == (2, 77)
        # an old save: no rank/renown keys; bosses already cleared imply the rank
        import json
        data = json.load(open(path))
        data.pop("rank"); data.pop("renown")
        data["cleared_bosses"] = ["colosseum_champion_boss"]
        json.dump(data, open(path, "w"))
        old = save_system.load_game(path)
        assert old.rank == 2 and old.renown == 0
        data["cleared_bosses"] = []
        json.dump(data, open(path, "w"))
        assert save_system.load_game(path).rank == 1
        data["cleared_bosses"] = ["unbroken_pair_boss"]            # out-of-order clear doesn't skip a rank
        json.dump(data, open(path, "w"))
        assert save_system.load_game(path).rank == 1
    print("test_save: PASS")


def main():
    test_rank_bosses_are_real_and_ordered()
    test_harder_fights_earn_more_and_wins_never_pay_zero()
    test_losses_cost_renown_and_easy_losses_sting_more()
    test_gate_challenge_and_overflow_cap()
    test_beating_the_rank_boss_promotes_and_resets_the_meter()
    test_pool_boss_encounters_dont_promote_and_pay_renown()
    test_pool_is_empty_at_rank_one_and_rolls_by_chance()
    test_save_round_trip_and_old_save_migration()
    print("\nALL RENOWN TESTS PASSED")


if __name__ == "__main__":
    main()

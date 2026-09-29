"""Headless coverage for game/party.py -- battle party selection (the
4-hero cap and the pre-battle picker screen's underlying logic). No UI
involved, same approach as tests/shop_test.py and tests/summon_test.py.

Run directly: python3 tests/party_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import party
from game.player_state import PlayerState
from game.roster import PlayerCharacter


def _roster(n):
    hero = PlayerCharacter(name="H0", class_id="tank")
    state = PlayerState.new_game(hero)
    for i in range(1, n):
        state.characters.append(PlayerCharacter(name=f"H{i}", class_id="mage"))
    return state


def test_default_party_ids_falls_back_to_first_max_party_size_when_no_active_party():
    state = _roster(6)
    ids = party.default_party_ids(state)
    assert ids == [c.id for c in state.characters[:party.MAX_PARTY_SIZE]]
    print("test_default_party_ids_falls_back_to_first_max_party_size_when_no_active_party: PASS")


def test_default_party_ids_prefers_previous_selection_filtered_to_owned():
    state = _roster(6)
    keep = [state.characters[4].id, state.characters[1].id]
    state.active_party = keep + ["not-a-real-id"]
    ids = party.default_party_ids(state)
    assert ids == keep, ids
    print("test_default_party_ids_prefers_previous_selection_filtered_to_owned: PASS")


def test_default_party_ids_falls_back_when_previous_selection_is_entirely_stale():
    state = _roster(3)
    state.active_party = ["gone-1", "gone-2"]
    ids = party.default_party_ids(state)
    assert ids == [c.id for c in state.characters[:party.MAX_PARTY_SIZE]]
    print("test_default_party_ids_falls_back_when_previous_selection_is_entirely_stale: PASS")


def test_active_party_characters_prefers_saved_active_party():
    state = _roster(6)
    keep = [state.characters[4].id, state.characters[1].id, "stale-id"]
    state.active_party = keep
    resolved = party.active_party_characters(state)
    # Roster order, not selection order, and the stale id is silently dropped.
    assert [c.id for c in resolved] == [state.characters[1].id, state.characters[4].id]
    print("test_active_party_characters_prefers_saved_active_party: PASS")


def test_active_party_characters_falls_back_to_default_when_unset():
    state = _roster(6)
    resolved = party.active_party_characters(state)
    assert [c.id for c in resolved] == [c.id for c in state.characters[:party.MAX_PARTY_SIZE]]
    print("test_active_party_characters_falls_back_to_default_when_unset: PASS")


def test_active_party_characters_is_never_the_whole_roster_once_capped():
    state = _roster(9)
    ok, msg, resolved = party.confirm_party(state, [c.id for c in state.characters[:party.MAX_PARTY_SIZE]])
    assert ok, msg
    resolved = party.active_party_characters(state)
    assert len(resolved) == party.MAX_PARTY_SIZE
    assert len(resolved) < len(state.characters), "the hub summary must not silently fall back to everyone"
    print("test_active_party_characters_is_never_the_whole_roster_once_capped: PASS")


def test_toggle_member_adds_and_removes():
    selected, changed = party.toggle_member([], "a")
    assert selected == ["a"] and changed
    selected, changed = party.toggle_member(selected, "a")
    assert selected == [] and changed
    print("test_toggle_member_adds_and_removes: PASS")


def test_toggle_member_refuses_past_max_party_size():
    full = [f"h{i}" for i in range(party.MAX_PARTY_SIZE)]
    selected, changed = party.toggle_member(full, "one-too-many")
    assert selected == full, "an over-cap add must not change the selection"
    assert not changed
    print("test_toggle_member_refuses_past_max_party_size: PASS")


def test_confirm_party_saves_active_party_and_resolves_in_roster_order():
    state = _roster(5)
    # Pick out of roster order -- confirm should still resolve in roster order.
    picks = [state.characters[3].id, state.characters[0].id]
    ok, msg, resolved = party.confirm_party(state, picks)
    assert ok, msg
    assert [c.id for c in resolved] == [state.characters[0].id, state.characters[3].id]
    assert state.active_party == picks
    print("test_confirm_party_saves_active_party_and_resolves_in_roster_order: PASS")


def test_confirm_party_rejects_empty_or_oversized_selection():
    state = _roster(6)
    ok, msg, resolved = party.confirm_party(state, [])
    assert not ok and resolved is None
    assert state.active_party == [], "a rejected confirm must not touch active_party"

    too_many = [c.id for c in state.characters[:party.MAX_PARTY_SIZE + 1]]
    ok, msg, resolved = party.confirm_party(state, too_many)
    assert not ok and resolved is None
    print("test_confirm_party_rejects_empty_or_oversized_selection: PASS")


def test_confirm_party_dedupes_and_drops_unknown_ids():
    state = _roster(3)
    real_id = state.characters[0].id
    ok, msg, resolved = party.confirm_party(state, [real_id, real_id, "not-real"])
    assert ok, msg
    assert [c.id for c in resolved] == [real_id]
    print("test_confirm_party_dedupes_and_drops_unknown_ids: PASS")


def main():
    test_default_party_ids_falls_back_to_first_max_party_size_when_no_active_party()
    test_default_party_ids_prefers_previous_selection_filtered_to_owned()
    test_default_party_ids_falls_back_when_previous_selection_is_entirely_stale()
    test_active_party_characters_prefers_saved_active_party()
    test_active_party_characters_falls_back_to_default_when_unset()
    test_active_party_characters_is_never_the_whole_roster_once_capped()
    test_toggle_member_adds_and_removes()
    test_toggle_member_refuses_past_max_party_size()
    test_confirm_party_saves_active_party_and_resolves_in_roster_order()
    test_confirm_party_rejects_empty_or_oversized_selection()
    test_confirm_party_dedupes_and_drops_unknown_ids()
    print("\nALL PARTY SELECTION TESTS PASSED")


if __name__ == "__main__":
    main()

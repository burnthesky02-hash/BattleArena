"""Headless coverage for the Dual Blades weapon type: Kenji's own weapon subtype, which fills BOTH hands
(weapon + off-hand slots) while equipped.

Run directly: python3 tests/dual_blades_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import vendors
from data.classes import CLASS_ARCHETYPES, weapon_types_for
from data.equipment_db import EQUIPMENT
from data.items_db import ITEMS
from engine.equipment import RARITIES, TWO_SLOT_WEAPON_TYPES, WEAPON_TYPES, occupies_offhand
from game import shop
from game.equipment_instances import new_instance, resolve_equipment_db
from game.player_state import PlayerState
from game.roster import PlayerCharacter

BLADES = [e for e in EQUIPMENT.values() if e.subtype == "dual_blades"]


def _state(name="Kenji", class_id="melee_dps", money=999999):
    hero = PlayerCharacter(name=name, class_id=class_id)
    st = PlayerState.new_game(hero)
    st.money = money
    return st, hero


def _own(st, base_id):
    """Puts a fresh instance of a catalog item in the stash (no money involved) and returns (instance id, resolved db)."""
    inst = new_instance(base_id, rolled=False, equipment_db=EQUIPMENT)
    st.add_equipment_to_stash(inst)
    return inst.instance_id, resolve_equipment_db(EQUIPMENT, st.equipment_instances)


def test_catalog_has_dual_blades_for_every_rarity():
    assert "dual_blades" in WEAPON_TYPES and "dual_blades" in TWO_SLOT_WEAPON_TYPES
    assert {e.rarity for e in BLADES} == set(RARITIES)
    for e in BLADES:
        assert e.slot == "weapon" and occupies_offhand(e)
        assert (e.cost > 0) == (e.rarity in ("common", "rare")), e.id       # same shop/summon split as every other weapon
    assert not occupies_offhand(EQUIPMENT["rusty_sword"]) and not occupies_offhand(None)
    print("test_catalog_has_dual_blades_for_every_rarity: PASS")


def test_only_kael_can_wield_dual_blades():
    assert "dual_blades" in weapon_types_for("Kenji", "melee_dps")
    for cid, arche in CLASS_ARCHETYPES.items():
        assert "dual_blades" not in arche.weapon_types, f"{cid}: dual blades must stay hero-specific"
    assert "dual_blades" not in weapon_types_for("Bran", "melee_dps")        # another melee DPS can't
    st, other = _state("Bran")
    iid, edb = _own(st, "twin_falchions")
    ok, msg = shop.equip_from_stash(st, other.id, iid, edb)
    assert not ok and "can't equip" in msg and iid in st.equipment_stash
    assert PlayerCharacter(name="Kenji", class_id="melee_dps").weapon_types >= {"sword", "axe", "dagger", "dual_blades"}
    print("test_only_kael_can_wield_dual_blades: PASS")


def test_equipping_blades_empties_offhand_into_stash():
    st, kael = _state()
    buckler, edb = _own(st, "cracked_buckler")
    ok, _ = shop.equip_from_stash(st, kael.id, buckler, edb)
    assert ok and kael.equipped["offhand"] == buckler
    sword, edb = _own(st, "rusty_sword")
    shop.equip_from_stash(st, kael.id, sword, edb)
    blades, edb = _own(st, "twin_falchions")
    ok, msg = shop.equip_from_stash(st, kael.id, blades, edb)
    assert ok, msg
    assert kael.equipped["weapon"] == blades and kael.equipped["offhand"] is None
    assert buckler in st.equipment_stash and sword in st.equipment_stash and blades not in st.equipment_stash
    assert "stash" in msg and "both hands" in msg
    assert kael.offhand_locked_by(edb).id == blades
    print("test_equipping_blades_empties_offhand_into_stash: PASS")


def test_offhand_goes_to_stash_even_with_no_weapon_equipped():
    st, kael = _state()
    buckler, edb = _own(st, "cracked_buckler")
    shop.equip_from_stash(st, kael.id, buckler, edb)
    assert kael.equipped["weapon"] is None
    blades, edb = _own(st, "twin_falchions")
    ok, msg = shop.equip_from_stash(st, kael.id, blades, edb)
    assert ok and kael.equipped["offhand"] is None and buckler in st.equipment_stash
    assert "Cracked Buckler" in msg and "both hands" in msg
    ok, msg = shop.equip_from_stash(st, kael.id, _own(st, "rusty_sword")[0], resolve_equipment_db(EQUIPMENT, st.equipment_instances))
    assert ok and "both hands" not in msg                       # a single weapon says nothing about hands
    print("test_offhand_goes_to_stash_even_with_no_weapon_equipped: PASS")


def test_offhand_blocked_while_blades_worn_then_allowed_after_unequip():
    st, kael = _state()
    blades, edb = _own(st, "iron_twin_blades")
    shop.equip_from_stash(st, kael.id, blades, edb)
    buckler, edb = _own(st, "cracked_buckler")
    ok, msg = shop.equip_from_stash(st, kael.id, buckler, edb)
    assert not ok and "both hands" in msg
    assert kael.equipped["offhand"] is None and buckler in st.equipment_stash      # refusal changed nothing
    ok, _ = shop.unequip(st, kael.id, "weapon", edb)
    assert ok and kael.offhand_locked_by(edb) is None
    ok, _ = shop.equip_from_stash(st, kael.id, buckler, edb)
    assert ok and kael.equipped["offhand"] == buckler
    print("test_offhand_blocked_while_blades_worn_then_allowed_after_unequip: PASS")


def test_swapping_to_a_single_weapon_frees_the_offhand():
    st, kael = _state()
    blades, edb = _own(st, "iron_twin_blades")
    shop.equip_from_stash(st, kael.id, blades, edb)
    sword, edb = _own(st, "rusty_sword")
    ok, _ = shop.equip_from_stash(st, kael.id, sword, edb)
    assert ok and kael.equipped["weapon"] == sword and blades in st.equipment_stash
    buckler, edb = _own(st, "cracked_buckler")
    ok, _ = shop.equip_from_stash(st, kael.id, buckler, edb)
    assert ok
    print("test_swapping_to_a_single_weapon_frees_the_offhand: PASS")


def test_stats_use_the_blades_and_no_offhand():
    st, kael = _state()
    base = kael.effective_stats(EQUIPMENT).atk
    blades, edb = _own(st, "twin_falchions")
    shop.equip_from_stash(st, kael.id, blades, edb)
    s = kael.effective_stats(edb)
    assert s.atk == base + EQUIPMENT["twin_falchions"].stat_bonuses["atk"]
    print("test_stats_use_the_blades_and_no_offhand: PASS")


def test_buy_and_equip_rules():
    st, kael = _state()
    buckler_iid, edb = _own(st, "cracked_buckler")
    shop.equip_from_stash(st, kael.id, buckler_iid, edb)
    money = st.money
    ok, msg = shop.buy_and_equip(st, "twin_falchions", kael.id, EQUIPMENT, lambda: resolve_equipment_db(EQUIPMENT, st.equipment_instances))
    assert ok, msg
    assert st.money == money - EQUIPMENT["twin_falchions"].cost
    assert kael.equipped["offhand"] is None and buckler_iid in st.equipment_stash and "stash too" in msg
    # now an off-hand purchase is refused BEFORE any money moves
    money = st.money
    ok, msg = shop.buy_and_equip(st, "dueling_buckler", kael.id, EQUIPMENT, lambda: resolve_equipment_db(EQUIPMENT, st.equipment_instances))
    assert not ok and "both hands" in msg and st.money == money
    # another hero buying blades is refused before paying
    st2, other = _state("Bran")
    money = st2.money
    ok, msg = shop.buy_and_equip(st2, "twin_falchions", other.id, EQUIPMENT, lambda: resolve_equipment_db(EQUIPMENT, st2.equipment_instances))
    assert not ok and "can't equip" in msg and st2.money == money
    print("test_buy_and_equip_rules: PASS")


def test_vendor_tables_still_valid_and_kael_shops_sell_blades():
    problems = vendors.validate(EQUIPMENT, ITEMS, {"Kenji": "melee_dps", "Miya": "support"}, CLASS_ARCHETYPES)
    assert problems == [], problems
    island = vendors.equipment_ids(vendors.SHOPS["island/shopkeeper"], EQUIPMENT)
    assert "iron_twin_blades" in island
    print("test_vendor_tables_still_valid_and_kael_shops_sell_blades: PASS")


def test_save_round_trip_keeps_blades_and_empty_offhand():
    import tempfile
    from game import save_system
    st, kael = _state()
    blades, edb = _own(st, "twin_falchions")
    shop.equip_from_stash(st, kael.id, blades, edb)
    path = os.path.join(tempfile.mkdtemp(), "s.json")
    save_system.save_game(st, path)
    st2 = save_system.load_game(path)
    k2 = st2.characters[0]
    edb2 = resolve_equipment_db(EQUIPMENT, st2.equipment_instances)
    assert k2.equipped["weapon"] == blades and k2.equipped["offhand"] is None
    assert k2.offhand_locked_by(edb2) is not None
    print("test_save_round_trip_keeps_blades_and_empty_offhand: PASS")


def main():
    test_catalog_has_dual_blades_for_every_rarity()
    test_only_kael_can_wield_dual_blades()
    test_equipping_blades_empties_offhand_into_stash()
    test_offhand_goes_to_stash_even_with_no_weapon_equipped()
    test_offhand_blocked_while_blades_worn_then_allowed_after_unequip()
    test_swapping_to_a_single_weapon_frees_the_offhand()
    test_stats_use_the_blades_and_no_offhand()
    test_buy_and_equip_rules()
    test_vendor_tables_still_valid_and_kael_shops_sell_blades()
    test_save_round_trip_keeps_blades_and_empty_offhand()
    print("\nALL DUAL BLADES TESTS PASSED")


if __name__ == "__main__":
    main()

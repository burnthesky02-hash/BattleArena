import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.classes import CLASS_ARCHETYPES
from data.equipment_db import EQUIPMENT
from engine.equipment import ARMOR_WEIGHTS, OFFHAND_TYPES, RARITIES, RARITY_BONUS_STAT_COUNT, SLOTS, \
    WEAPON_TYPES, class_can_equip
from game import debug_tools as D
from game import save_system, shop as shop_logic
from game.equipment_instances import new_instance, resolve_equipment_db, roll_bonus_stats
from game.player_state import PlayerState
from game.roster import PlayerCharacter
from game.summon import summon_equipment_batch


def fresh(class_id="tank"):
    return PlayerState.new_game(PlayerCharacter(name="T", class_id=class_id))


def test_catalog_shape():
    assert len(EQUIPMENT) > 150
    by_slot = {}
    for e in EQUIPMENT.values():
        by_slot[e.slot] = by_slot.get(e.slot, 0) + 1
        assert e.slot in SLOTS
        assert e.rarity in RARITIES
    for slot in SLOTS:
        assert by_slot.get(slot, 0) > 0, f"no items for slot {slot}"
    print("test_catalog_shape: PASS")


def test_class_restrictions():
    tank = CLASS_ARCHETYPES["tank"]
    mage = CLASS_ARCHETYPES["mage"]
    sword = next(e for e in EQUIPMENT.values() if e.slot == "weapon" and e.subtype == "sword")
    staff = next(e for e in EQUIPMENT.values() if e.slot == "weapon" and e.subtype == "staff")
    heavy_helm = next(e for e in EQUIPMENT.values() if e.slot == "helmet" and e.subtype == "heavy")
    light_helm = next(e for e in EQUIPMENT.values() if e.slot == "helmet" and e.subtype == "light")

    assert class_can_equip(sword, tank.weapon_types, tank.offhand_types, tank.armor_weight)
    assert not class_can_equip(staff, tank.weapon_types, tank.offhand_types, tank.armor_weight)
    assert class_can_equip(staff, mage.weapon_types, mage.offhand_types, mage.armor_weight)
    assert not class_can_equip(heavy_helm, mage.weapon_types, mage.offhand_types, mage.armor_weight)
    assert class_can_equip(light_helm, mage.weapon_types, mage.offhand_types, mage.armor_weight)
    assert class_can_equip(light_helm, tank.weapon_types, tank.offhand_types, tank.armor_weight)  # lighter is fine
    print("test_class_restrictions: PASS")


def test_shop_hard_blocks_wrong_subtype():
    st = fresh("mage")
    st.money = 999999
    heavy_helm = next(e for e in EQUIPMENT.values() if e.slot == "helmet" and e.subtype == "heavy" and e.cost > 0)
    ok, _ = shop_logic.buy_equipment(st, heavy_helm.id, EQUIPMENT)
    assert ok
    edb = resolve_equipment_db(EQUIPMENT, st.equipment_instances)
    iid = st.equipment_stash[0]
    ok, msg = shop_logic.equip_from_stash(st, st.characters[0].id, iid, edb)
    assert not ok and "can't equip" in msg
    assert iid in st.equipment_stash  # refused equip leaves the stash untouched
    print("test_shop_hard_blocks_wrong_subtype: PASS")


def test_equip_unequip_roundtrip():
    st = fresh("tank")
    st.money = 999999
    sword = next(e for e in EQUIPMENT.values() if e.slot == "weapon" and e.subtype == "sword" and e.cost > 0)
    shop_logic.buy_equipment(st, sword.id, EQUIPMENT)
    edb = resolve_equipment_db(EQUIPMENT, st.equipment_instances)
    iid = st.equipment_stash[0]
    hero = st.characters[0]
    ok, _ = shop_logic.equip_from_stash(st, hero.id, iid, edb)
    assert ok and hero.equipped["weapon"] == iid and iid not in st.equipment_stash
    ok, _ = shop_logic.unequip(st, hero.id, "weapon", edb)
    assert ok and hero.equipped["weapon"] is None and iid in st.equipment_stash
    print("test_equip_unequip_roundtrip: PASS")


def test_only_summoned_gear_rolls_stats():
    st = fresh("tank")
    st.gems = 999999
    r = random.Random(7)
    # Shop/debug gear: always zero bonus stats, regardless of rarity.
    for e in EQUIPMENT.values():
        if e.cost > 0:
            inst = new_instance(e.id, rolled=False, equipment_db=EQUIPMENT, rng=r)
            assert inst.bonus_stats == {}
    # Summoned gear: bonus stat count matches RARITY_BONUS_STAT_COUNT for its rarity.
    ok, _, results = summon_equipment_batch(st, EQUIPMENT, 30, rng=r)
    assert ok
    seen_nonzero = False
    for res in results:
        want = RARITY_BONUS_STAT_COUNT[res.rarity]
        assert len(res.instance.bonus_stats) == want, (res.rarity, res.instance.bonus_stats)
        if want:
            seen_nonzero = True
    assert seen_nonzero
    print("test_only_summoned_gear_rolls_stats: PASS")


def test_resolve_equipment_db_bridge():
    st = fresh("tank")
    st.gems = 999999
    r = random.Random(3)
    ok, _, results = summon_equipment_batch(st, EQUIPMENT, 1, rng=r)
    assert ok
    inst = results[0].instance
    edb = resolve_equipment_db(EQUIPMENT, st.equipment_instances)
    resolved = edb[inst.instance_id]
    base = EQUIPMENT[inst.base_id]
    for k, v in inst.bonus_stats.items():
        assert resolved.stat_bonuses.get(k, 0) == base.stat_bonuses.get(k, 0) + v
    assert resolved.slot == base.slot and resolved.subtype == base.subtype and resolved.rarity == base.rarity
    # An id not in EQUIPMENT and not a live instance is simply absent, same as before the refactor.
    assert edb.get("totally-made-up-id") is None
    print("test_resolve_equipment_db_bridge: PASS")


def test_debug_tools_stash_and_instances():
    st = fresh("tank")
    D.apply(st, {"action": "add_all_equipment"})
    assert len(st.equipment_stash) == len(EQUIPMENT)
    assert len(st.equipment_instances) == len(EQUIPMENT)
    D.apply(st, {"action": "clear_stash"})
    assert not st.equipment_stash
    assert len(st.equipment_instances) == len(EQUIPMENT)  # instances stay registered
    print("test_debug_tools_stash_and_instances: PASS")


def test_save_migration_old_format():
    import json
    old = {
        "version": 1, "money": 500, "gems": 50, "inventory": {},
        "owned_equipment": {"rusty_sword": 2},
        "characters": [{"id": "abc123", "name": "Garrick", "class_id": "tank", "level": 5, "xp": 0,
                        "equipped": {"weapon": "rusty_sword", "armor": None, "accessory": None}}],
        "active_party": [], "cleared_bosses": [], "rank": 1, "renown": 0,
    }
    path = "/tmp/equipment_overhaul_migration_test.json"
    with open(path, "w") as f:
        json.dump(old, f)
    st = save_system.load_game(path=path)
    assert len(st.equipment_stash) == 2
    c = st.characters[0]
    weapon_iid = c.equipped["weapon"]
    assert weapon_iid and weapon_iid in st.equipment_instances
    assert st.equipment_instances[weapon_iid].base_id == "rusty_sword"
    assert c.equipped.get("helmet") is None and c.equipped.get("boots") is None and c.equipped.get("offhand") is None
    os.remove(path)
    print("test_save_migration_old_format: PASS")


def test_save_load_roundtrip_new_format():
    st = fresh("mage")
    st.gems = 999999
    r = random.Random(11)
    summon_equipment_batch(st, EQUIPMENT, 5, rng=r)
    path = "/tmp/equipment_overhaul_roundtrip_test.json"
    save_system.save_game(st, path=path)
    st2 = save_system.load_game(path=path)
    assert len(st2.equipment_instances) == len(st.equipment_instances)
    assert set(st2.equipment_stash) == set(st.equipment_stash)
    for iid, inst in st.equipment_instances.items():
        inst2 = st2.equipment_instances[iid]
        assert inst2.base_id == inst.base_id and inst2.bonus_stats == inst.bonus_stats
    os.remove(path)
    print("test_save_load_roundtrip_new_format: PASS")


if __name__ == "__main__":
    test_catalog_shape()
    test_class_restrictions()
    test_shop_hard_blocks_wrong_subtype()
    test_equip_unequip_roundtrip()
    test_only_summoned_gear_rolls_stats()
    test_resolve_equipment_db_bridge()
    test_debug_tools_stash_and_instances()
    test_save_migration_old_format()
    test_save_load_roundtrip_new_format()
    print("\nALL EQUIPMENT OVERHAUL TESTS PASSED")

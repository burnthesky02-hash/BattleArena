"""Who sells what, and how far each blacksmith can take a weapon (Andrew: shops carry only a few things that fit the
point in the story, and blacksmiths have an upgrade level cap that rises as you progress).

A 3D hub scene's shop / gear NPC is identified by "<scene>/<npc id>" (hub3d.js stores that key in sessionStorage
before opening /shop or /heroes, and the pages pass it to /api/shop?vendor= and /api/heroes?vendor=). Everything here
is a plain table: retune stock lists and caps by editing it. Stock is explicit ids from data/equipment_db.py /
data/items_db.py; tests/vendors_test.py-style checks (see validate()) make sure every id exists and fits the heroes
the shop says it is for.

Progression: Paradise Island -> Hollow Cave -> the Pit -> the Colosseum -> Outpost Kestrel. Shops only sell common and
rare gear (epic and above is summon-only), so the tiers are: low commons (island), mid commons for Kenji + Miya (cave),
all commons plus rare armor (Colosseum), everything rare (the base).
"""
from typing import Dict, List, Optional

# ---- Shops ---------------------------------------------------------------------------------------------------------
# for_heroes: names of the heroes the stock is picked for (None = any class). The shop page still lets you compare
# every hero in your party; this is just the shop's pitch and what validate() checks the gear against.
SHOPS: Dict[str, dict] = {
    "island/shopkeeper": {
        "name": "Marla's Goods", "note": "A few basics for a farmhand with a sword.", "for_heroes": ["Kenji"],
        "equipment": ["rusty_sword", "camp_hatchet", "iron_twin_blades", "cracked_buckler", "armor_medium_common"],
        "items": ["potion", "antidote"],
    },
    "dungeon/dg_shop1": {
        "name": "Pell's Finds", "note": "Found, not stolen. Better steel for two fighters.", "for_heroes": ["Kenji", "Miya"],
        "equipment": ["soldiers_sword", "brawlers_axe", "duelists_pair", "willow_wand", "field_grimoire", "dueling_buckler", "acolytes_orb",
                      "armor_light_common", "helm_light_common", "boots_light_common"],
        "items": ["potion", "antidote"],
    },
    "dungeon/dg_shop2": {
        "name": "Tolliver's Supplies", "note": "Lanterns, rope and a few trinkets.", "for_heroes": ["Kenji", "Miya"],
        "equipment": ["travelers_band", "lucky_charm", "apprentice_focus_ring", "swift_boots_charm"],
        "items": ["potion", "hi_potion", "antidote", "ether"],
    },
    "prison/shop": {
        "name": "Whisper's Stash", "note": "Smuggled goods, priced for a slave who got lucky.", "for_heroes": ["Kenji"],
        "equipment": ["alley_shiv", "soldiers_sword", "iron_twin_blades", "dueling_buckler", "armor_medium_common", "helm_medium_common",
                      "boots_medium_common"],
        "items": ["potion", "antidote", "hi_potion"],
    },
    "olympus/shop": {
        "name": "The Armory", "note": "Colosseum-grade kit for every kind of fighter.", "for_heroes": None,
        "equipment": ["iron_flail", "alley_shiv", "iron_twin_blades", "duelists_pair", "willow_wand", "field_grimoire", "soldiers_sword", "brawlers_axe",
                      "recurve_bow", "oak_staff", "wooden_buckler_shield", "iron_kite_shield", "dueling_buckler",
                      "fletchers_quiver", "acolytes_orb",
                      "armor_light_common", "armor_medium_common", "armor_heavy_common",
                      "helm_light_common", "helm_medium_common", "helm_heavy_common",
                      "boots_light_common", "boots_medium_common", "boots_heavy_common",
                      "armor_light_rare", "armor_medium_rare", "armor_heavy_rare",
                      "lucky_charm", "travelers_band", "apprentice_focus_ring", "swift_boots_charm", "gladiators_signet"],
        "items": ["potion", "hi_potion", "antidote", "ether", "phoenix_down"],
    },
    "asteroid/shop": {
        "name": "Quartermaster's Cache", "note": "Salvaged rare gear, everything the base has.", "for_heroes": None,
        "equipment": "ALL_RARE",
        "items": ["potion", "hi_potion", "antidote", "ether", "phoenix_down"],
    },
}
DEFAULT_SHOP = "olympus/shop"          # the shop page opened with no vendor (2D hub nav, old links)

# ---- Blacksmiths (the gear NPCs: whoever opens the Heroes page) -------------------------------------------------------
# cap = the highest weapon upgrade level this smith can take a weapon to (game/equipment_instances.py WEAPON_MAX_UPGRADE
# is the absolute ceiling, +10).
SMITHS: Dict[str, dict] = {
    "island/smith": {"name": "Hild the Blacksmith", "cap": 3},
    "dungeon/dg_hero1": {"name": "Captain Merrow", "cap": 5},
    "prison/heroes": {"name": "Old Marek", "cap": 5},
    "olympus/heroes": {"name": "Lyra", "cap": 7},
    "asteroid/heroes": {"name": "Ysol", "cap": 10},
}
DEFAULT_SMITH = {"name": "the Colosseum smith", "cap": 7}     # Heroes page opened with no smith (2D hub nav)


def shop_for(key: Optional[str]) -> dict:
    return SHOPS.get(key or "") or SHOPS[DEFAULT_SHOP]


def smith_for(key: Optional[str]) -> dict:
    return SMITHS.get(key or "") or DEFAULT_SMITH


def equipment_ids(shop: dict, equipment_db) -> List[str]:
    """The shop's equipment ids (expanding "ALL_RARE"), only ones that exist and are actually for sale (cost > 0)."""
    eq = shop["equipment"]
    if eq == "ALL_RARE":
        ids = [e.id for e in equipment_db.values() if e.cost > 0 and e.rarity == "rare"]
    else:
        ids = list(eq)
    return [i for i in ids if i in equipment_db and equipment_db[i].cost > 0]


def validate(equipment_db, items_db, class_by_hero: Dict[str, str], classes) -> List[str]:
    """Problems with the tables above (empty list = fine): unknown ids, and gear no listed hero's class can use."""
    from data.classes import weapon_types_for
    from engine.equipment import class_can_equip
    bad: List[str] = []
    for key, shop in SHOPS.items():
        for i in (shop["equipment"] if shop["equipment"] != "ALL_RARE" else []):
            if i not in equipment_db or equipment_db[i].cost <= 0:
                bad.append(f"{key}: unknown or unsellable equipment {i}")
        for i in shop["items"]:
            if i not in items_db or items_db[i].cost <= 0:
                bad.append(f"{key}: unknown or unsellable item {i}")
        names = shop["for_heroes"]
        if names:
            arche = [(classes[class_by_hero[n]], weapon_types_for(n, class_by_hero[n])) for n in names]
            for i in equipment_ids(shop, equipment_db):
                e = equipment_db[i]
                if not any(class_can_equip(e, wt, a.offhand_types, a.armor_weight) for a, wt in arche):
                    bad.append(f"{key}: {i} fits none of {names}")
    for key, sm in SMITHS.items():
        if not (1 <= sm["cap"] <= 10):
            bad.append(f"{key}: bad cap {sm['cap']}")
    return bad

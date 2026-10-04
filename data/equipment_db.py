"""The equipment registry: every base piece of gear in the game.

Nothing here is owned by anyone by default -- new characters start with
empty equipment slots (see game/player_state.py); this is just the catalog
of what exists to buy (the Shop, game/shop.py) or draw from the premium
pool (Summon, game/summon.py).

Six slots now (engine/equipment.py's SLOTS): weapon, offhand, armor,
helmet, boots, accessory. Weapons and off-hands have a class-restricted
SUBTYPE (a sword, a bow, a shield, ...); armor/helmet/boots have a
light/medium/heavy WEIGHT instead (data/classes.py says which subtypes/
weight each class can use -- engine/equipment.py's class_can_equip does
the actual check). Accessories are universal, same as before.

Rarity still roughly maps to how it's acquired: common/rare are
shop-buyable (nonzero `cost`); epic/legendary/mythic have `cost=0` and are
gem-summon-only (game/summon.py's summon_equipment), each rarer and
stronger than the last. The numbers below are each item's fixed BASELINE
bonus -- every copy starts with these. A copy pulled from a summon (never
a shop purchase) also gets 1/2/3/4 random bonus stats on top for
rare/epic/legendary/mythic respectively (game/equipment_instances.py) --
that part is per-instance, not in this catalog, since two summoned copies
of the same item can roll differently.

Stat bonus fields match engine/stats.py's Stats field names exactly (atk,
def_, mag, res, spd, luk, max_hp, max_mp) since PlayerCharacter.
effective_stats applies them with plain getattr/setattr.
"""
from engine.equipment import Equipment


SHOP_PRICE_MULT = 9        # shop prices were too cheap: every shop-buyable item's listed cost is multiplied by this (cost 0 = summon-only stays 0)


def _e(id, name, slot, subtype, rarity, cost, bonuses, desc):
    cost = cost * SHOP_PRICE_MULT if cost > 0 else cost
    return Equipment(id=id, name=name, slot=slot, subtype=subtype, rarity=rarity, cost=cost,
                     stat_bonuses=bonuses, description=desc)


EQUIPMENT = {}


def _add(*items):
    for it in items:
        EQUIPMENT[it.id] = it


# ========================================================================
# WEAPONS -- one subtype family at a time, common -> mythic. Every class
# picks from data/classes.py's weapon_types, so each subtype has to cover
# every rarity tier or that subtype's users would hit a wall.
# ========================================================================

# --- sword (tank, melee_dps) -------------------------------------------
_add(
    _e("rusty_sword", "Rusty Sword", "weapon", "sword", "common", 60, {"atk": 4}, "A basic blade. Better than fists."),
    _e("soldiers_sword", "Soldier's Sword", "weapon", "sword", "common", 75, {"atk": 5, "def_": 1}, "Standard-issue Colosseum steel."),
    _e("knights_blade", "Knight's Blade", "weapon", "sword", "rare", 180, {"atk": 8, "def_": 2}, "Well-balanced steel, favored by veterans."),
    _e("falcon_saber", "Falcon Saber", "weapon", "sword", "rare", 190, {"atk": 9, "spd": 2}, "Curved for a faster draw."),
    _e("warshard", "Warshard", "weapon", "sword", "epic", 0, {"atk": 13, "spd": 3}, "A shattered greatsword's edge, still hungry."),
    _e("blade_of_the_underdog", "Blade of the Underdog", "weapon", "sword", "epic", 0, {"atk": 12, "luk": 4}, "Won in a fight nobody thought it would survive."),
    _e("flameheart_blade", "Flameheart Blade", "weapon", "sword", "legendary", 0, {"atk": 18, "mag": 6}, "Said to have been forged in a dying star."),
    _e("duskbreaker", "Duskbreaker", "weapon", "sword", "legendary", 0, {"atk": 19, "def_": 5}, "Cuts a line the dark can't cross."),
    _e("kaels_edge", "Kael's Edge", "weapon", "sword", "mythic", 0, {"atk": 26, "spd": 6, "luk": 6}, "Kael's own blade, worn smooth by a thousand bouts."),
)

# --- axe (tank, melee_dps) ----------------------------------------------
_add(
    _e("camp_hatchet", "Camp Hatchet", "weapon", "axe", "common", 60, {"atk": 5}, "Meant for firewood. Works fine on foes."),
    _e("brawlers_axe", "Brawler's Axe", "weapon", "axe", "common", 75, {"atk": 6, "spd": -1, "def_": 1}, "Heavy-headed and swung with both hands."),
    _e("war_hatchet", "War Hatchet", "weapon", "axe", "rare", 180, {"atk": 10, "def_": 2}, "Balanced enough to throw, if it ever came to that."),
    _e("bearded_cleaver", "Bearded Cleaver", "weapon", "axe", "rare", 190, {"atk": 11, "max_hp": 8}, "The hook catches shields as well as it catches flesh."),
    _e("gorehowl_splitter", "Gorehowl Splitter", "weapon", "axe", "epic", 0, {"atk": 15, "def_": 3}, "It sings on the downswing."),
    _e("ravagers_axe", "Ravager's Axe", "weapon", "axe", "epic", 0, {"atk": 16, "max_hp": 10}, "Notched from bone, never sharpened, never dulled."),
    _e("titanfall_axe", "Titanfall Axe", "weapon", "axe", "legendary", 0, {"atk": 21, "def_": 6}, "Said to have felled something much larger than a man."),
    _e("stormrend", "Stormrend", "weapon", "axe", "legendary", 0, {"atk": 20, "spd": 4, "max_hp": 12}, "Crackles faintly before every swing."),
    _e("thornes_reckoning", "Thorne's Reckoning", "weapon", "axe", "mythic", 0, {"atk": 29, "def_": 7, "max_hp": 14}, "Thorne's signature axe -- undefeated in the pits."),
)

# --- mace (tank, support) ------------------------------------------------
_add(
    _e("wooden_club", "Wooden Club", "weapon", "mace", "common", 55, {"atk": 4, "def_": 1}, "Blunt, simple, effective."),
    _e("iron_flail", "Iron Flail", "weapon", "mace", "common", 70, {"atk": 5, "spd": 1}, "Unpredictable, but hits like a cart."),
    _e("chapel_mace", "Chapel Mace", "weapon", "mace", "rare", 175, {"atk": 7, "mag": 3}, "Blessed steel, favored by battle-clerics."),
    _e("skullcracker", "Skullcracker", "weapon", "mace", "rare", 185, {"atk": 9, "def_": 3}, "Subtle it is not."),
    _e("aegis_mace", "Aegis Mace", "weapon", "mace", "epic", 0, {"atk": 11, "def_": 5, "mag": 3}, "Doubles as a shield when the moment calls for it."),
    _e("sunforged_mace", "Sunforged Mace", "weapon", "mace", "epic", 0, {"atk": 10, "mag": 6, "res": 3}, "Warm to the touch, always."),
    _e("hammer_of_verdicts", "Hammer of Verdicts", "weapon", "mace", "legendary", 0, {"atk": 14, "def_": 7, "mag": 5}, "Every swing feels like a ruling."),
    _e("dawnbreakers_mace", "Dawnbreaker's Mace", "weapon", "mace", "legendary", 0, {"atk": 13, "mag": 9, "res": 5}, "Lights the arena for a heartbeat on impact."),
    _e("garricks_bulwark_mace", "Garrick's Bulwark Mace", "weapon", "mace", "mythic", 0, {"atk": 17, "def_": 10, "max_hp": 20}, "A tank's mace, built to end a fight, not start one."),
)

# --- dagger (melee_dps) --------------------------------------------------
_add(
    _e("kitchen_knife", "Kitchen Knife", "weapon", "dagger", "common", 55, {"atk": 3, "spd": 2}, "Not built for this, but it'll do."),
    _e("alley_shiv", "Alley Shiv", "weapon", "dagger", "common", 70, {"atk": 4, "luk": 2}, "Quick, quiet, and a little dirty."),
    _e("twinfang_daggers", "Twinfang Daggers", "weapon", "dagger", "rare", 175, {"atk": 7, "spd": 3}, "A pair, thrown as often as stabbed."),
    _e("serrated_kris", "Serrated Kris", "weapon", "dagger", "rare", 185, {"atk": 8, "luk": 3}, "Wavy steel that never cuts clean."),
    _e("nightfall_fang", "Nightfall Fang", "weapon", "dagger", "epic", 0, {"atk": 11, "spd": 5}, "Barely visible until it's already too late."),
    _e("cutthroats_favor", "Cutthroat's Favor", "weapon", "dagger", "epic", 0, {"atk": 12, "luk": 5}, "Every gambler's lucky blade, eventually."),
    _e("vexs_bite", "Vex's Bite", "weapon", "dagger", "legendary", 0, {"atk": 16, "spd": 7}, "Named for the duelist who never dropped it."),
    _e("whisper_of_ruin", "Whisper of Ruin", "weapon", "dagger", "legendary", 0, {"atk": 15, "luk": 8, "spd": 3}, "You hear it a half-second after you feel it."),
    _e("kaels_shadow_twin", "Kael's Shadow-Twin", "weapon", "dagger", "mythic", 0, {"atk": 20, "spd": 9, "luk": 6}, "A second blade to match his sword, just as feared."),
)

# --- bow (ranged_dps) -----------------------------------------------------
_add(
    _e("hunting_bow", "Hunting Bow", "weapon", "bow", "common", 60, {"atk": 3, "spd": 2}, "Light and quick to draw."),
    _e("recurve_bow", "Recurve Bow", "weapon", "bow", "common", 75, {"atk": 4, "luk": 1}, "A little more draw weight, a little more sting."),
    _e("longshot_bow", "Longshot Bow", "weapon", "bow", "rare", 180, {"atk": 8, "spd": 2}, "Rangers swear by the extra reach."),
    _e("hawkeye_recurve", "Hawkeye Recurve", "weapon", "bow", "rare", 190, {"atk": 7, "luk": 3}, "Never misses by much."),
    _e("stormcaller_bow", "Stormcaller Bow", "weapon", "bow", "epic", 0, {"atk": 12, "spd": 4}, "Draws faster than the eye can follow."),
    _e("huntresss_longbow", "Huntress's Longbow", "weapon", "bow", "epic", 0, {"atk": 11, "luk": 5}, "Every shot lands where it's meant to."),
    _e("gale_piercer", "Gale Piercer", "weapon", "bow", "legendary", 0, {"atk": 16, "spd": 6}, "The string hums even at rest."),
    _e("sureshot_of_finn", "Sureshot of Finn", "weapon", "bow", "legendary", 0, {"atk": 15, "luk": 7, "spd": 2}, "Finn's own bow, retired undefeated."),
    _e("rooks_windcaller", "Rook's Windcaller", "weapon", "bow", "mythic", 0, {"atk": 20, "spd": 8, "luk": 5}, "Rook's signature bow -- the crowd goes quiet before every shot."),
)

# --- staff (mage) -----------------------------------------------------------
_add(
    _e("apprentice_wand", "Apprentice's Wand", "weapon", "staff", "common", 60, {"mag": 4}, "A simple focus for channeling magic."),
    _e("oak_staff", "Oak Staff", "weapon", "staff", "common", 75, {"mag": 5, "max_mp": 5}, "Carved from a tree struck by lightning."),
    _e("crystal_staff", "Crystal Staff", "weapon", "staff", "rare", 180, {"mag": 8, "max_mp": 10}, "The crystal never quite stops humming."),
    _e("emberwood_staff", "Emberwood Staff", "weapon", "staff", "rare", 190, {"mag": 9, "res": 2}, "Still faintly warm from the fire that shaped it."),
    _e("staff_of_the_tempest", "Staff of the Tempest", "weapon", "staff", "epic", 0, {"mag": 13, "spd": 3}, "Storms gather where it's planted."),
    _e("archmages_focus", "Archmage's Focus", "weapon", "staff", "epic", 0, {"mag": 14, "max_mp": 15}, "A career's worth of study, distilled into a stick."),
    _e("staff_of_starfall", "Staff of Starfall", "weapon", "staff", "legendary", 0, {"mag": 19, "max_mp": 20}, "Every cast leaves a trail of falling light."),
    _e("world_ash_branch", "World-Ash Branch", "weapon", "staff", "legendary", 0, {"mag": 18, "res": 6, "max_mp": 10}, "Cut from a tree that shouldn't still be growing."),
    _e("lyras_starlight_staff", "Lyra's Starlight Staff", "weapon", "staff", "mythic", 0, {"mag": 26, "max_mp": 25, "res": 5}, "Lyra's own staff, said to remember every spell it's cast."),
)

# --- wand (mage, support) -----------------------------------------------
_add(
    _e("apprentice_rod", "Apprentice Rod", "weapon", "wand", "common", 55, {"mag": 3, "res": 1}, "The staff's shorter, cheaper cousin."),
    _e("willow_wand", "Willow Wand", "weapon", "wand", "common", 70, {"mag": 4, "max_mp": 4}, "Bends without breaking, same as its bearer."),
    _e("moonlit_wand", "Moonlit Wand", "weapon", "wand", "rare", 175, {"mag": 7, "res": 3}, "Cool to the touch even in the arena heat."),
    _e("chorister_wand", "Chorister's Wand", "weapon", "wand", "rare", 185, {"mag": 6, "max_mp": 12}, "Hums a note only its bearer can hear."),
    _e("wand_of_the_faithful", "Wand of the Faithful", "weapon", "wand", "epic", 0, {"mag": 10, "res": 5}, "Warm in a healer's hand, cold in anyone else's."),
    _e("wraithglass_wand", "Wraithglass Wand", "weapon", "wand", "epic", 0, {"mag": 11, "max_mp": 14}, "Faintly translucent -- you can almost see the spell forming."),
    _e("wand_of_the_last_light", "Wand of the Last Light", "weapon", "wand", "legendary", 0, {"mag": 15, "res": 8}, "Never goes dark, no matter how deep the arena's shadows get."),
    _e("seraphs_wandrest", "Seraph's Wandrest", "weapon", "wand", "legendary", 0, {"mag": 14, "max_mp": 22}, "Passed down through generations of battle-clerics."),
    _e("seras_mercy_wand", "Sera's Mercy Wand", "weapon", "wand", "mythic", 0, {"mag": 19, "res": 10, "max_mp": 18}, "Sera's own wand -- no champion under her care has ever fallen."),
)

# --- tome (support) --------------------------------------------------------
_add(
    _e("worn_prayer_book", "Worn Prayer Book", "weapon", "tome", "common", 55, {"mag": 3, "max_mp": 5}, "Pages soft from a thousand readings."),
    _e("field_grimoire", "Field Grimoire", "weapon", "tome", "common", 70, {"mag": 4, "res": 1}, "A battle-cleric's working copy."),
    _e("tome_of_mending", "Tome of Mending", "weapon", "tome", "rare", 175, {"mag": 6, "max_mp": 14}, "Every chapter is a different way to keep someone standing."),
    _e("gilded_hymnal", "Gilded Hymnal", "weapon", "tome", "rare", 185, {"mag": 7, "res": 3}, "Sung from more than read, these days."),
    _e("tome_of_unbroken_faith", "Tome of Unbroken Faith", "weapon", "tome", "epic", 0, {"mag": 10, "max_mp": 18}, "Its binding has never once cracked."),
    _e("codex_of_the_ward", "Codex of the Ward", "weapon", "tome", "epic", 0, {"mag": 9, "res": 6, "max_hp": 10}, "Half prayer book, half shield."),
    _e("grand_tome_of_salvation", "Grand Tome of Salvation", "weapon", "tome", "legendary", 0, {"mag": 14, "max_mp": 24}, "Said to have saved more lives than any healer alone could."),
    _e("liturgy_of_dawn", "Liturgy of Dawn", "weapon", "tome", "legendary", 0, {"mag": 13, "res": 9, "max_hp": 14}, "Its first page glows faintly at sunrise."),
    _e("osrics_final_verse", "Osric's Final Verse", "weapon", "tome", "mythic", 0, {"mag": 18, "res": 11, "max_mp": 20}, "Osric's own tome, still open to the page he never finished."),
)

# ========================================================================
# OFF-HAND -- shield (tank), buckler (melee_dps), quiver (ranged_dps),
# focus (mage, support).
# ========================================================================
_add(
    _e("wooden_buckler_shield", "Wooden Round Shield", "offhand", "shield", "common", 45, {"def_": 3}, "Splintered at the edges, still holds."),
    _e("iron_kite_shield", "Iron Kite Shield", "offhand", "shield", "common", 60, {"def_": 4, "max_hp": 5}, "Standard Colosseum-issue."),
    _e("bulwark_shield", "Bulwark Shield", "offhand", "shield", "rare", 165, {"def_": 7, "max_hp": 10}, "Heavy enough to stop a charging bull."),
    _e("wardens_tower_shield", "Warden's Tower Shield", "offhand", "shield", "rare", 175, {"def_": 8, "res": 3}, "Big enough to hide a whole squad behind."),
    _e("aegis_shield", "Aegis Shield", "offhand", "shield", "epic", 0, {"def_": 12, "max_hp": 15}, "Named for the myth, not the maker."),
    _e("stormward_shield", "Stormward Shield", "offhand", "shield", "epic", 0, {"def_": 11, "res": 6}, "Crackles when it blocks a spell."),
    _e("unbreakable_bulwark", "Unbreakable Bulwark", "offhand", "shield", "legendary", 0, {"def_": 16, "max_hp": 22}, "It has never once cracked, in or out of the arena."),
    _e("dawnwall_shield", "Dawnwall Shield", "offhand", "shield", "legendary", 0, {"def_": 15, "res": 9, "max_hp": 12}, "Catches the arena lights like a second sunrise."),
    _e("garricks_last_stand", "Garrick's Last Stand", "offhand", "shield", "mythic", 0, {"def_": 20, "res": 10, "max_hp": 30}, "Garrick's own shield -- nothing has ever gotten past it."),
)
_add(
    _e("cracked_buckler", "Cracked Buckler", "offhand", "buckler", "common", 40, {"def_": 2, "spd": 1}, "Light enough to not slow you down."),
    _e("dueling_buckler", "Dueling Buckler", "offhand", "buckler", "common", 55, {"def_": 3, "luk": 1}, "Favored in one-on-one arena bouts."),
    _e("parrying_buckler", "Parrying Buckler", "offhand", "buckler", "rare", 160, {"def_": 5, "spd": 2}, "Built for the riposte, not the block."),
    _e("brawlers_buckler", "Brawler's Buckler", "offhand", "buckler", "rare", 170, {"def_": 6, "luk": 2}, "Scuffed on every edge -- it's earned every scar."),
    _e("featherweight_buckler", "Featherweight Buckler", "offhand", "buckler", "epic", 0, {"def_": 8, "spd": 4}, "Barely there, but always exactly where it needs to be."),
    _e("gamblers_buckler", "Gambler's Buckler", "offhand", "buckler", "epic", 0, {"def_": 7, "luk": 5}, "Every block feels like a coin flip that keeps landing right."),
    _e("vipers_buckler", "Viper's Buckler", "offhand", "buckler", "legendary", 0, {"def_": 10, "spd": 6}, "Strikes back before the attacker's even set."),
    _e("fortunes_buckler", "Fortune's Buckler", "offhand", "buckler", "legendary", 0, {"def_": 9, "luk": 8}, "Somehow it's always in the right place."),
    _e("thornes_offhand_edge", "Thorne's Offhand Edge", "offhand", "buckler", "mythic", 0, {"def_": 12, "spd": 7, "luk": 5}, "A second blade Thorne barely needs, and rarely draws."),
)
_add(
    _e("leather_quiver", "Leather Quiver", "offhand", "quiver", "common", 40, {"atk": 2, "spd": 1}, "Keeps the arrows dry and the draw quick."),
    _e("fletchers_quiver", "Fletcher's Quiver", "offhand", "quiver", "common", 55, {"atk": 3, "luk": 1}, "Hand-fletched, every shaft true."),
    _e("swift_quiver", "Swift Quiver", "offhand", "quiver", "rare", 160, {"atk": 4, "spd": 3}, "Somehow never runs dry mid-fight."),
    _e("huntsmans_quiver", "Huntsman's Quiver", "offhand", "quiver", "rare", 170, {"atk": 5, "luk": 2}, "Every arrow in it feels a little luckier."),
    _e("windrunner_quiver", "Windrunner Quiver", "offhand", "quiver", "epic", 0, {"atk": 7, "spd": 5}, "The arrows seem to fly themselves."),
    _e("quiver_of_fortune", "Quiver of Fortune", "offhand", "quiver", "epic", 0, {"atk": 6, "luk": 6}, "Never once been shot empty at the wrong moment."),
    _e("stormfeather_quiver", "Stormfeather Quiver", "offhand", "quiver", "legendary", 0, {"atk": 9, "spd": 7}, "Fletched with feathers that were never on any bird."),
    _e("quiver_of_the_hundred", "Quiver of the Hundred", "offhand", "quiver", "legendary", 0, {"atk": 8, "luk": 9}, "Named for a hundred straight bullseyes, and counting."),
    _e("finns_endless_quiver", "Finn's Endless Quiver", "offhand", "quiver", "mythic", 0, {"atk": 11, "spd": 8, "luk": 6}, "Finn's own quiver -- nobody has ever seen it run out."),
)
_add(
    _e("cracked_orb", "Cracked Orb", "offhand", "focus", "common", 40, {"mag": 2, "max_mp": 4}, "Still holds a charge, somehow."),
    _e("acolytes_orb", "Acolyte's Orb", "offhand", "focus", "common", 55, {"mag": 3, "res": 1}, "First given to every battle-mage in training."),
    _e("crystal_focus", "Crystal Focus", "offhand", "focus", "rare", 160, {"mag": 5, "max_mp": 10}, "Steadies a spell mid-cast."),
    _e("warded_focus", "Warded Focus", "offhand", "focus", "rare", 170, {"mag": 4, "res": 4}, "Deflects the backlash of a botched cast."),
    _e("focus_of_clarity", "Focus of Clarity", "offhand", "focus", "epic", 0, {"mag": 8, "max_mp": 15}, "Thoughts come sharper with it in hand."),
    _e("stormglass_focus", "Stormglass Focus", "offhand", "focus", "epic", 0, {"mag": 7, "res": 6}, "Weather seems to shift when it's raised."),
    _e("focus_of_the_infinite", "Focus of the Infinite", "offhand", "focus", "legendary", 0, {"mag": 11, "max_mp": 20}, "Every spell through it feels like the first draft of something bigger."),
    _e("aegis_focus", "Aegis Focus", "offhand", "focus", "legendary", 0, {"mag": 10, "res": 9}, "Turns aside more than it channels."),
    _e("lyras_second_light", "Lyra's Second Light", "offhand", "focus", "mythic", 0, {"mag": 14, "max_mp": 22, "res": 6}, "Lyra's backup focus -- rarely needed, never found wanting."),
)

# ========================================================================
# ARMOR / HELMET / BOOTS -- light (mage, support), medium (melee_dps,
# ranged_dps), heavy (tank; also legal for medium/light classes' below-cap
# picks... no, wait: class_can_equip caps AT a class's weight, doesn't
# raise it, so heavy stays tank-only. Medium classes CAN wear light gear.)
# ========================================================================

def _armor_family(slot, id_prefix, name_suffix, base_stat, base_hp):
    """common/rare/epic/legendary/mythic x light/medium/heavy for one armor slot -- the three weight
    tiers share a naming/stat shape (defense-leaning for the slot's `base_stat`, HP scales with weight)
    so this loop keeps the 15-entries-per-slot pattern from turning into 15x the typo risk."""
    cost = {"common": (45, 60), "rare": (150, 165)}
    weight_hp_mult = {"light": 0.6, "medium": 1.0, "heavy": 1.5}
    weight_stat_mult = {"light": 0.7, "medium": 1.0, "heavy": 1.3}
    tier_stat = {"common": 3, "rare": 6, "epic": 9, "legendary": 13, "mythic": 17}
    tier_hp = {"common": 6, "rare": 14, "epic": 20, "legendary": 28, "mythic": 38}
    tier_extra = {"epic": 3, "legendary": 6, "mythic": 9}   # a secondary stat, epic+ only
    extra_stat = {"light": "res", "medium": "spd", "heavy": "def_" if base_stat != "def_" else "res"}
    names = {
        "light": {"common": "Cloth", "rare": "Silk-Lined", "epic": "Warded", "legendary": "Starweave", "mythic": "Aetherweave"},
        "medium": {"common": "Leather", "rare": "Studded", "epic": "Reinforced", "legendary": "Dragonhide", "mythic": "Wyrmscale"},
        "heavy": {"common": "Iron", "rare": "Steel Plate", "epic": "Champion's", "legendary": "Colosseum", "mythic": "Titan's"},
    }
    out = []
    for weight in ARMOR_WEIGHTS_LOCAL:
        for rarity in ("common", "rare", "epic", "legendary", "mythic"):
            stat_val = round(tier_stat[rarity] * weight_stat_mult[weight])
            hp_val = round(tier_hp[rarity] * weight_hp_mult[weight])
            bonuses = {base_stat: stat_val, "max_hp": hp_val}
            if rarity in tier_extra:
                bonuses[extra_stat[weight]] = round(tier_extra[rarity] * weight_stat_mult[weight])
            item_cost = cost.get(rarity, (0, 0))
            item_cost = item_cost[0] if weight == "light" else (item_cost[1] if weight == "heavy" else round(sum(item_cost) / 2))
            item_cost = item_cost if rarity in ("common", "rare") else 0
            out.append(_e(
                f"{id_prefix}_{weight}_{rarity}", f"{names[weight][rarity]} {name_suffix}", slot, weight, rarity,
                item_cost, bonuses,
                f"{weight.capitalize()}-weight {slot} -- {rarity} grade.",
            ))
    return out


ARMOR_WEIGHTS_LOCAL = ("light", "medium", "heavy")
_add(*_armor_family("armor", "armor", "Armor", "def_", 8))
_add(*_armor_family("helmet", "helm", "Helm", "def_", 4))
_add(*_armor_family("boots", "boots", "Boots", "spd", 3))

# ========================================================================
# ACCESSORY -- universal, no subtype. Common/rare are single-stat and
# shop-buyable; epic+ are multi-stat and summon-only.
# ========================================================================
_add(
    _e("lucky_charm", "Lucky Charm", "accessory", None, "common", 45, {"luk": 5}, "A rabbit's foot. It's had better days."),
    _e("swift_boots_charm", "Swift Anklet", "accessory", None, "common", 45, {"spd": 4}, "Light enough to forget you're wearing it."),
    _e("travelers_band", "Traveler's Band", "accessory", None, "common", 45, {"max_hp": 10}, "Worn smooth from a long road."),
    _e("apprentice_focus_ring", "Apprentice Focus Ring", "accessory", None, "common", 45, {"max_mp": 8}, "A student's first real focus."),
    _e("sages_ring", "Sage's Ring", "accessory", None, "rare", 160, {"mag": 5, "max_mp": 15}, "Hums faintly when spells are cast nearby."),
    _e("gladiators_signet", "Gladiator's Signet", "accessory", None, "rare", 165, {"atk": 4, "def_": 3}, "Given to every fighter who survives their first ten bouts."),
    _e("ring_of_swift_feet", "Ring of Swift Feet", "accessory", None, "rare", 155, {"spd": 5, "luk": 2}, "Never quite sits still."),
    _e("band_of_vigor", "Band of Vigor", "accessory", None, "epic", 0, {"atk": 3, "mag": 3, "spd": 3}, "Worn by an undercard fighter who never lost a bout."),
    _e("talisman_of_the_veteran", "Talisman of the Veteran", "accessory", None, "epic", 0, {"def_": 5, "res": 5, "max_hp": 15}, "Every scar it's prevented is a story untold."),
    _e("ring_of_the_gambler", "Ring of the Gambler", "accessory", None, "epic", 0, {"luk": 10, "spd": 3}, "The house doesn't like this one."),
    _e("crown_of_the_undefeated", "Crown of the Undefeated", "accessory", None, "legendary", 0, {"atk": 5, "mag": 5, "spd": 5, "luk": 10}, "A crown that has never once left the Colosseum in defeat."),
    _e("heartstone_amulet", "Heartstone Amulet", "accessory", None, "legendary", 0, {"max_hp": 35, "res": 8, "def_": 6}, "Beats faintly, in time with its wearer's own pulse."),
    _e("ring_of_the_arcanist", "Ring of the Arcanist", "accessory", None, "legendary", 0, {"mag": 12, "max_mp": 25, "res": 6}, "Three schools of magic, one small band."),
    _e("champions_medallion", "Champion's Medallion", "accessory", None, "mythic", 0, {"atk": 8, "mag": 8, "def_": 6, "res": 6, "spd": 6, "luk": 8}, "Struck fresh for every undisputed Colosseum champion -- only the truly great ever wear one."),
    _e("aegis_of_the_colosseum", "Aegis of the Colosseum", "accessory", None, "mythic", 0, {"def_": 12, "res": 12, "max_hp": 40}, "Worn by champions whose names are still chanted in the stands."),
)

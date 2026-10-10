"""Data for the Summon screen (game/summon.py): gem costs and the pool a
character-summon draws from.

RECRUITABLE_ROSTER is a list of RecruitableHero(name, class_id, rarity)
entries themed after the original four-person party in data/characters.py:
Kenji/Lyra/Miya/Rook rejoin here as actual recruitable teammates, closing the
loop the README already draws between them and four of the five class
archetypes (see data/classes.py's module docstring). Each class still has
exactly 5 names (25 total, unchanged from the level-curve pass) -- as of the
hero-rarity pass, that turned out to be a perfect fit for data/hero_rarity.py's
5 rarity tiers, so each class now has exactly one name at each rarity
(confirmed with Andrew via AskUserQuestion rather than assumed). Within each
class the callback name (Kenji/Lyra/Miya/Rook) was put at the rare end --
mythic, the tier that best matches "the name most worth pulling" -- and the
rest filled in around it; tank never had an original-party counterpart, so
its five names are just assigned common..mythic in listed order.

game/summon.py's summon_character rolls a rarity first (data/hero_rarity.py's
HERO_SUMMON_WEIGHTS), then picks uniformly among the (up to) 5 class-matched
heroes at that rarity -- so "which class" and "which rarity" are independent
rolls, same odds either way. A pull matching a hero already on the roster no
longer avoids itself (that dedup logic is gone as of this pass) -- it grants
hero shards for that hero instead (see data/hero_rarity.py's
SHARDS_PER_DUPLICATE / SHARD_COST_FOR_STAR).
"""
from dataclasses import dataclass
from typing import Dict, List

from data.hero_rarity import HERO_RARITIES

# Tunable economy knobs -- see game/rewards.py's VICTORY_GEM_RANGE (3-6 per
# win) for what these actually cost in battles: equipment is affordable
# with your starting 20 gems, a character recruit takes a few wins to save
# for, on purpose (a whole new teammate is worth more than a stat stick).
CHARACTER_SUMMON_COST = 30
EQUIPMENT_SUMMON_COST = 15

# The Summon screen's "pull 10 at once" option (see game/summon.py's
# summon_character_batch/summon_equipment_batch and ui/pygame_ui.py's
# show_summon card-reveal grid). A flat x10 multiplier, no bulk discount --
# simplest first-pass number, same "tune by feel later" spirit as every
# other economy constant in this file. If Andrew wants a discount later
# (e.g. "9x cost for 10 pulls"), these two become the one place to change it.
SUMMON_X10_COUNT = 10
CHARACTER_SUMMON_COST_X10 = CHARACTER_SUMMON_COST * SUMMON_X10_COUNT
EQUIPMENT_SUMMON_COST_X10 = EQUIPMENT_SUMMON_COST * SUMMON_X10_COUNT


# --- Common (gold) summon, Premium target rate-up, and tickets -----------------
# Premium Summon = the gem summon above (HERO_SUMMON_WEIGHTS) with an optional TARGET hero: when the
# rarity roll lands on the target's tier, the target is picked TARGET_SHARE of the time (the rest is the
# usual uniform pick among the tier's other heroes). Rarity odds themselves are unchanged.
TARGET_SHARE = 0.5

# Common Summon: gold only, heroes only, low chance of high rarity. Weights sum to 100.
COMMON_SUMMON_COST = 100
COMMON_SUMMON_COST_X10 = COMMON_SUMMON_COST * SUMMON_X10_COUNT
COMMON_SUMMON_WEIGHTS: Dict[str, float] = {"common": 65.0, "rare": 27.0, "epic": 6.8, "legendary": 1.0, "mythic": 0.2}

# Tickets: "common" pays for one Common Summon pull; "premium" for one Premium (hero) pull.
# Equipment summons no longer take tickets at all -- see EQUIPMENT_SHARD_* below, Andrew's request to
# replace the equipment side of this with its own currency ("secondary summon" = equipment, as opposed
# to the gem-cost Premium hero pull, which keeps using premium tickets exactly as before).
TICKET_KINDS = ("common", "premium")
TICKET_LABEL = {"common": "Common Ticket", "premium": "Premium Ticket"}
TICKET_DROP_CHANCE = {"common": 0.15, "premium": 0.04}   # per normal win; doubled in Ladder Mode
BOSS_TICKETS_FIRST = {"common": 1, "premium": 2}         # first clear of a boss
BOSS_TICKETS_REPEAT = {"common": 1, "premium": 1}        # boss rematches / pool-boss encounters

# --- Equipment summon rebalance + equipment shards --------------------------------
#
# Equipment summons used to draw ONLY from cost<=0 (epic/legendary/mythic) gear -- every pull was
# guaranteed at least epic, weighted 3:1 toward epic over legendary and mythic drawing the same
# implicit weight as legendary (~65% epic / ~22% legendary / ~14% mythic per item-count). Andrew's
# call: that made it too easy to walk away with top-end gear, so the roll pool now spans every rarity
# in the catalog (common through mythic) and EQUIPMENT_RARITY_WEIGHTS below is a per-TIER target
# (summing to 100, mirrors HERO_SUMMON_WEIGHTS' shape) rather than a per-item one -- game/summon.py
# divides each tier's weight by how many items are actually in that tier so a pull lands on any common
# item as often as any other common item, and the tier as a whole hits its target rate regardless of
# how many base items happen to be cataloged in it.
EQUIPMENT_RARITY_WEIGHTS: Dict[str, float] = {"common": 45.0, "rare": 30.0, "epic": 18.0, "legendary": 6.0, "mythic": 1.0}
assert set(EQUIPMENT_RARITY_WEIGHTS) == {"common", "rare", "epic", "legendary", "mythic"}
assert sum(EQUIPMENT_RARITY_WEIGHTS.values()) == 100

# Equipment shards: a new currency dedicated to equipment summons (replaces spending a Premium Ticket
# on gear). Two ways to earn them -- a small independent chance per battle win (mirrors
# TICKET_DROP_CHANCE's shape, doubled in Ladder Mode) and salvaging an owned, unequipped piece of gear
# for a rarity-scaled amount (game/shop.py's salvage_equipment) -- spent EQUIPMENT_SHARD_SUMMON_COST
# per equipment-summon pull (Andrew's number: 10).
EQUIPMENT_SHARD_SUMMON_COST = 10
EQUIPMENT_SHARD_DROP_CHANCE = 0.20        # per normal win; doubled in Ladder Mode
EQUIPMENT_SHARD_DROP_RANGE = (1, 3)       # amount granted when the drop chance hits
BOSS_EQUIPMENT_SHARDS_FIRST = 8           # first clear of a boss
BOSS_EQUIPMENT_SHARDS_REPEAT = 4          # boss rematches / pool-boss encounters

# Shards gained salvaging one owned instance, by its rarity -- deliberately steep (not linear with
# EQUIPMENT_SUMMON_COST's old epic/legendary-only economy) so salvaging a pile of common duplicates is
# a real but slow way to fund a pull, while breaking down one unwanted mythic roughly covers a pull.
EQUIPMENT_SALVAGE_YIELD: Dict[str, int] = {"common": 1, "rare": 2, "epic": 4, "legendary": 7, "mythic": 12}
assert set(EQUIPMENT_SALVAGE_YIELD) == {"common", "rare", "epic", "legendary", "mythic"}


@dataclass(frozen=True)
class RecruitableHero:
    name: str
    class_id: str
    rarity: str

    def __post_init__(self):
        if self.rarity not in HERO_RARITIES:
            raise ValueError(f"RecruitableHero {self.name!r} has unknown rarity {self.rarity!r}")


RECRUITABLE_ROSTER: List[RecruitableHero] = [
    # melee_dps -- Kenji's kit (data/classes.py); Kenji himself is the mythic pull.
    RecruitableHero("Bran", "melee_dps", "common"),
    RecruitableHero("Vex", "melee_dps", "rare"),
    RecruitableHero("Thorne", "melee_dps", "epic"),
    RecruitableHero("Rhea", "melee_dps", "legendary"),
    RecruitableHero("Kenji", "melee_dps", "mythic"),
    # ranged_dps -- Rook's kit; Rook is the mythic pull.
    RecruitableHero("Sylas", "ranged_dps", "common"),
    RecruitableHero("Nadia", "ranged_dps", "rare"),
    RecruitableHero("Zara", "ranged_dps", "epic"),
    RecruitableHero("Finn", "ranged_dps", "legendary"),
    RecruitableHero("Rook", "ranged_dps", "mythic"),
    # mage -- Lyra's kit; Lyra is the mythic pull.
    RecruitableHero("Ignis", "mage", "common"),
    RecruitableHero("Wren", "mage", "rare"),
    RecruitableHero("Solene", "mage", "epic"),
    RecruitableHero("Kade", "mage", "legendary"),
    RecruitableHero("Lyra", "mage", "mythic"),
    # support -- Miya's kit; Miya is the mythic pull.
    RecruitableHero("Elowen", "support", "common"),
    RecruitableHero("Dassin", "support", "rare"),
    RecruitableHero("Mira", "support", "epic"),
    RecruitableHero("Osric", "support", "legendary"),
    RecruitableHero("Miya", "support", "mythic"),
    # tank -- no original-party counterpart, so just common..mythic in order.
    RecruitableHero("Gareth", "tank", "common"),
    RecruitableHero("Brutus", "tank", "rare"),
    RecruitableHero("Petra", "tank", "epic"),
    RecruitableHero("Draven", "tank", "legendary"),
    RecruitableHero("Yulia", "tank", "mythic"),
]

# Precomputed rarity -> [RecruitableHero, ...] (one per class, 5 total) so
# game/summon.py can roll a rarity, then pick uniformly among that tier's
# entries, without rescanning the whole list on every pull.
RECRUITABLE_BY_RARITY: Dict[str, List[RecruitableHero]] = {
    rarity: [h for h in RECRUITABLE_ROSTER if h.rarity == rarity] for rarity in HERO_RARITIES
}

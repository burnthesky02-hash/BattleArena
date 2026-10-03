"""Hero rarity: the common/rare/epic/legendary/mythic tier every recruitable
character (data/summon_pool.py) and every owned PlayerCharacter (game/roster.py)
carries, plus everything derived from it -- summon odds, the color theme
used to render it (ui/pygame_ui.py's Summon/Heroes screens; text mode uses
HERO_RARITY_LABEL instead of color, see below), and the shard/star upgrade
economy for duplicate summons.

This is a *hero* rarity system, deliberately separate from
engine/equipment.py's RARITIES (common/rare/epic/legendary, no mythic) --
Andrew only asked for rarity on heroes, and equipment's rarity already
means something specific there (epic/legendary = gem-summon-only, not
shop-purchasable). Keeping them as two independent enums avoids quietly
changing what equipment rarity means just to add a tier heroes wanted.

Confirmed with Andrew via AskUserQuestion (this feature had several
genuinely open design calls, unlike most follow-up asks in this project):
  - Star upgrades (not a level-cap raise or free-form stat points) are what
    hero shards buy.
  - Each class's existing 5 recruitable names map one-to-one onto the 5
    rarities (see data/summon_pool.py) rather than some other split.
  - Summon odds use the "standard gacha curve" preset below.
  - The new Heroes page replaces Shop's old "Gear" tab as the one place to
    equip characters (see ui/pygame_ui.py's/ui/text_ui.py's show_heroes).

Everything numeric below is still a first-pass tuning knob, same spirit as
game/battle_setup.py's difficulty offsets or data/leveling.py's XP curve --
retune by feel once this has actually been played with, not from any
deeper design principle.
"""
from typing import Dict, List, Optional, Tuple

# Rendering order everywhere a rarity list is shown (Summon odds display,
# Heroes screen legend, etc.) -- weakest to strongest.
HERO_RARITIES: Tuple[str, ...] = ("common", "rare", "epic", "legendary", "mythic")

HERO_RARITY_LABEL: Dict[str, str] = {r: r.capitalize() for r in HERO_RARITIES}

# RGB, for ui/pygame_ui.py to render a hero's name/card/stars in. Chosen to
# read clearly against BG_COLOR (24, 24, 34) and step up in "excitement"
# with rarity: a flat gray, up through blue/purple/gold to a mythic red
# that's deliberately close to an alert color -- it's meant to grab the eye
# as "you will not see this often." Text mode has no established ANSI-color
# convention anywhere else in this codebase (plain print() throughout,
# partly to stay safe on older Windows terminals), so it sticks to
# HERO_RARITY_LABEL text tags (e.g. "[Legendary]") instead of also growing
# an escape-code palette here.
HERO_RARITY_COLOR: Dict[str, Tuple[int, int, int]] = {
    "common": (190, 190, 195),
    "rare": (90, 170, 230),
    "epic": (185, 110, 230),
    "legendary": (235, 175, 60),
    "mythic": (230, 60, 90),
}

# Character-summon odds (game/summon.py passes these straight to
# random.choices' weights, so they don't strictly need to sum to 100, but
# keeping them as whole percentages makes the numbers easy to read/retune at
# a glance). Equipment summons (game/summon.py's summon_equipment) are
# untouched by this -- they keep their own separate epic/legendary-only
# weighting.
#
# Tuned down once after Andrew played with the original "standard gacha
# curve" pick (common/rare/epic/legendary/mythic = 50/30/13/5/2) and said the
# top tiers felt too easy to pull. Legendary and mythic were cut hardest
# (roughly -20% and -50% relative to the original) since those are the ones
# meant to feel rare; still a first-pass number, not a final one -- retune
# again by feel.
HERO_SUMMON_WEIGHTS: Dict[str, int] = {
    "common": 55,
    "rare": 28,
    "epic": 12,
    "legendary": 4,
    "mythic": 1,
}
assert set(HERO_SUMMON_WEIGHTS) == set(HERO_RARITIES)
assert sum(HERO_SUMMON_WEIGHTS.values()) == 100

# --- Duplicate summons -> hero shards -> star upgrades ---------------------
#
# A summon pull that matches a hero you already own no longer fails/repeats
# silently (see the old RECRUITABLE_ROSTER dedup logic this replaces) -- it
# grants hero shards for that specific hero instead. Rarer duplicates are
# rarer to land at all, so they're worth more shards per pull (see
# SHARDS_PER_DUPLICATE) rather than costing more per star (SHARD_COST_FOR_STAR
# is otherwise the reason rarer heroes could feel like they take forever to
# max out -- this keeps the actual number of *pulls* needed roughly sane
# across rarities, even though the raw shard numbers scale up).
MAX_STARS = 5

# Flat % bonus to every stat per star past the first (a fresh recruit/summon
# always starts at 1 star -- see PlayerCharacter.stars' default -- so this is
# 0% until the first upgrade). 5 stars = (5-1) * 8% = +32%, matching the
# "+8%/star, stacking to +32% at 5 stars" language from the AskUserQuestion
# this settled.
STAR_STAT_BONUS_PER_LEVEL = 0.08

# Shards granted per duplicate pull, by the rarity that was actually rolled.
SHARDS_PER_DUPLICATE: Dict[str, int] = {
    "common": 1,
    "rare": 2,
    "epic": 3,
    "legendary": 4,
    "mythic": 5,
}
assert set(SHARDS_PER_DUPLICATE) == set(HERO_RARITIES)

# Shards needed to go from star N to star N+1, one entry per upgrade (4
# upgrades get you from 1 star to MAX_STARS=5), scaled up a bit by rarity --
# a mythic hero being fully starred out is meant to still feel like a
# project, not just as cheap as a common one once you're lucky enough to
# duplicate it a few times.
SHARD_COST_FOR_STAR: Dict[str, List[int]] = {
    "common": [2, 4, 6, 9],
    "rare": [3, 5, 8, 12],
    "epic": [3, 6, 10, 15],
    "legendary": [4, 7, 12, 18],
    "mythic": [4, 8, 14, 20],
}
assert set(SHARD_COST_FOR_STAR) == set(HERO_RARITIES)
assert all(len(costs) == MAX_STARS - 1 for costs in SHARD_COST_FOR_STAR.values())


# Flat stat multiplier per rarity, applied to every hero of that rarity (owned
# heroes in game/roster.py, hero rivals in game/battle_setup.py), on top of
# the class kit and the star bonus. Common stays exactly 1.0 so existing
# balance is unchanged; higher rarities are strictly better.
RARITY_STAT_MULTIPLIER: Dict[str, float] = {
    "common": 1.00,
    "rare": 1.08,
    "epic": 1.16,
    "legendary": 1.25,
    "mythic": 1.35,
}
assert set(RARITY_STAT_MULTIPLIER) == set(HERO_RARITIES)


def rarity_multiplier(rarity: str) -> float:
    return RARITY_STAT_MULTIPLIER.get(rarity, 1.0)


# --- Per-rarity level caps ---------------------------------------------------
#
# Replaces the old "heroes are lost forever on death" design: a hero is never
# permanently lost in battle any more (see game/legacy.py's apply_wound_penalty
# for what actually happens instead), and legacy items are now earned by
# deliberately retiring a hero who's reached THEIR OWN level cap
# (game/legacy.py's sacrifice_hero) rather than by losing one. Every hero's
# cap is set by their rarity alone: common=10, then +10 per rarity step above
# that (rare=20, epic=30, legendary=40, mythic=50) -- a mythic hero simply has
# further to climb (and a stronger legacy waiting at the end of it) than a
# common one. data/leveling.py's MAX_LEVEL (60) stays the engine's absolute
# ceiling (enemies/hero-rivals still scale off it); this is a lower, per-hero
# ceiling layered on top of it for owned characters specifically.
LEVEL_CAP_BASE = 10
LEVEL_CAP_STEP = 10


# --- Story heroes vs Colosseum heroes ---------------------------------------------------------------
# Mythic heroes are the STORY cast (Kael, Lyra, Rook, Sera, Yulia): they fight everything outside the
# Colosseum (the 3D story scenes, dungeons, world bosses), are never summoned, never wounded, can't be
# sacrificed, and climb a much longer, steeper arc to level 99. Every other rarity is a Colosseum hero
# (ladder fights, summons, wounds, legacy sacrifice) with the old per-rarity caps.
STORY_RARITY = "mythic"
STORY_LEVEL_CAP = 99
STORY_GROWTH_MULT = 1.3      # story heroes gain 30% more of their class's per-level stat growth


def is_story_rarity(rarity: str) -> bool:
    return rarity == STORY_RARITY


def level_cap_for(rarity: str) -> int:
    if rarity == STORY_RARITY:
        return STORY_LEVEL_CAP
    idx = HERO_RARITIES.index(rarity) if rarity in HERO_RARITIES else 0
    return LEVEL_CAP_BASE + LEVEL_CAP_STEP * idx


def star_multiplier(stars: int) -> float:
    """The flat multiplier a hero's grown-but-pre-equipment stats get from
    their current star count (see game/roster.py's PlayerCharacter.effective_stats).
    1 star (the starting/default value) is exactly 1.0x -- no behavior change
    for a hero that's never been duplicated."""
    return 1.0 + STAR_STAT_BONUS_PER_LEVEL * (max(1, stars) - 1)


def shard_cost_for_next_star(rarity: str, current_stars: int) -> Optional[int]:
    """Shards needed to go from current_stars to current_stars + 1, or None
    if current_stars is already at (or somehow past) MAX_STARS."""
    if current_stars >= MAX_STARS:
        return None
    costs = SHARD_COST_FOR_STAR.get(rarity, SHARD_COST_FOR_STAR["common"])
    return costs[current_stars - 1]


def star_display(stars: int) -> str:
    """A plain-text star readout ("*** .." style, ASCII so it's identical in
    both ui/text_ui.py and ui/pygame_ui.py's default font, which may not
    have a real star glyph) -- e.g. star_display(3) -> '[***..]'."""
    stars = max(1, min(stars, MAX_STARS))
    return "[" + "*" * stars + "." * (MAX_STARS - stars) + "]"

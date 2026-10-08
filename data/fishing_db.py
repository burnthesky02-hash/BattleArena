"""Fishing tables: where you can fish (SPOTS), what lives there (SPECIES), and the tackle you can buy (RODS, BAITS).

Everything is a plain table -- retune freely; game/fishing.py reads these and nothing else is hard-coded.

Zones are how far you cast from the pier:  near < 10 m,  mid 10-18 m,  far > 18 m.  A rod's `reach` caps the cast, so the
far water (the big, rare fish) needs a better rod.  Species have `tags`; a bait has `affinity` {tag: weight multiplier},
which is how bait changes what bites.  `luck` (rod + bait) pushes the roll toward uncommon / rare / legendary fish.
"""
from typing import Dict, List

ZONES = ("near", "mid", "far")
ZONE_EDGES = (10.0, 18.0)                      # near < 10 <= mid < 18 <= far
CAST_MIN = 5.0                                  # shortest cast (m)

RARITIES = ("common", "uncommon", "rare", "legendary")
RARITY_WEIGHT = {"common": 100.0, "uncommon": 28.0, "rare": 5.0, "legendary": 0.5}
RARITY_LUCK = {"common": 0.0, "uncommon": 3.0, "rare": 8.0, "legendary": 20.0}       # weight *= 1 + luck * this
FIRST_CATCH_BONUS = {"common": 20, "uncommon": 60, "rare": 200, "legendary": 800}    # gold, the first time a species goes in the log
SET_BONUS_GEMS = 5                                                                      # every species of one spot logged

SIZE_CLASSES = (                                                                        # (upper bound of the size roll, name, value multiplier)
    (0.18, "Runt", 0.7), (0.45, "Small", 0.9), (0.75, "Average", 1.0), (0.93, "Large", 1.25), (1.01, "Trophy", 1.8))

# ---- spots -----------------------------------------------------------------------------------------------------------
# scene = the 3D hub scene you fish in (html_hub/3d/<scene>.json). shop = which tackle the seller there stocks.
SPOTS: Dict[str, dict] = {
    "pier": {"name": "Harbour Pier", "scene": "fish_pier", "water": "sea",
             "seller": "Old Brine", "rods": ["bamboo", "fiberglass"], "baits": ["worm", "dough", "shrimp", "minnow", "glow"]},
    "pond": {"name": "Whispering Pool", "scene": "fish_pond", "water": "fresh",
             "seller": "Mossy Hen", "rods": ["bamboo", "carbon"], "baits": ["worm", "dough", "minnow", "glow"]},
}

# ---- species ---------------------------------------------------------------------------------------------------------
def _s(id, name, spot, zone, rarity, kg, rate, fight, tags, color, note):
    return dict(id=id, name=name, spot=spot, zone=zone, rarity=rarity, kg=kg, rate=rate, fight=fight, tags=tags, color=color, note=note)

SPECIES: List[dict] = [
    # ---- Harbour Pier (sea) ----
    _s("sprat",        "Silver Sprat",      "pier", "near", "common",    (0.05, 0.25), 90,  0.15, ["small", "shoal"],       "#c9d6e0", "Thumb-sized and everywhere."),
    _s("striped_perch","Striped Perch",     "pier", "near", "common",    (0.2, 1.1),   60,  0.30, ["small", "bottom"],      "#7aa56b", "Barred like a tiny tiger."),
    _s("pufferfish",   "Grumpy Puffer",     "pier", "near", "uncommon",  (0.3, 1.5),   110, 0.35, ["bottom"],               "#e3c777", "Puffs up when reeled. Insulted."),
    _s("sand_crab",    "Sand Crab",         "pier", "near", "uncommon",  (0.2, 0.9),   120, 0.25, ["bottom", "gourmet"],    "#d98a5b", "Not a fish, but it bit."),
    _s("mullet",       "Silver Mullet",     "pier", "mid",  "common",    (0.5, 2.5),   45,  0.40, ["shoal"],                "#b8c7d3", "Runs in noisy schools."),
    _s("moon_bream",   "Moon Bream",        "pier", "mid",  "common",    (0.8, 3.5),   55,  0.45, ["shoal", "bottom"],      "#e8e2c8", "Pale as the tide-moon."),
    _s("red_snapper",  "Red Snapper",       "pier", "mid",  "uncommon",  (1.5, 7.0),   70,  0.60, ["gourmet", "predator"],  "#d1493f", "A harbour-market favourite."),
    _s("harbor_eel",   "Harbour Eel",       "pier", "mid",  "rare",      (1.0, 6.0),   140, 0.70, ["bottom", "predator"],   "#5a6b4d", "Lives under the pilings."),
    _s("grouper",      "Giant Grouper",     "pier", "far",  "common",    (8, 35),      28,  0.75, ["bottom", "predator"],   "#8a6f4e", "Swallows the bait and the sinker."),
    _s("tuna",         "Bluefin Tuna",      "pier", "far",  "uncommon",  (10, 45),     22,  0.80, ["predator", "gourmet"],  "#3e6fa8", "Built like a torpedo."),
    _s("lantern_angler","Lantern Angler",   "pier", "far",  "rare",      (3, 12),      90,  0.65, ["predator"],             "#6a4d8a", "Its lure glows in daylight."),
    _s("swordtooth",   "Swordtooth Marlin", "pier", "far",  "rare",      (45, 140),    14,  0.95, ["predator"],             "#2f8fb0", "Dock-hands tell lies about these."),
    _s("leviathan_eel","Old Leviathan",     "pier", "far",  "legendary", (80, 220),    25,  1.00, ["predator", "bottom"],   "#2d2f55", "Older than the pier. Older than the harbour."),
    # ---- Whispering Pool (fresh water) ----
    _s("minnow",       "Pond Minnow",       "pond", "near", "common",    (0.02, 0.12), 150, 0.12, ["small", "shoal"],       "#a9c4a0", "Bait-sized and bold."),
    _s("bluegill",     "Bluegill",          "pond", "near", "common",    (0.1, 0.9),   65,  0.30, ["small", "shoal"],       "#4f8fb8", "A blue cheek, a bright belly."),
    _s("mud_loach",    "Mud Loach",         "pond", "near", "uncommon",  (0.1, 0.6),   130, 0.30, ["bottom", "small"],      "#8b7355", "Wriggles. A lot."),
    _s("crayfish",     "Moss Crayfish",     "pond", "near", "uncommon",  (0.1, 0.5),   150, 0.25, ["bottom", "gourmet"],    "#a4452e", "Pinched the hook, then you."),
    _s("brook_trout",  "Brook Trout",       "pond", "mid",  "common",    (0.4, 2.5),   75,  0.50, ["gourmet", "shoal"],     "#c28d5a", "Speckled like fallen leaves."),
    _s("bass",         "Largemouth Bass",   "pond", "mid",  "uncommon",  (1.0, 6.0),   70,  0.65, ["predator"],             "#5f7f3f", "All mouth and attitude."),
    _s("catfish",      "Whiskered Catfish", "pond", "mid",  "uncommon",  (1.5, 9.0),   60,  0.60, ["bottom", "predator"],   "#6b5b4a", "Sulks at the bottom of the pool."),
    _s("glass_eel",    "Glass Eel",         "pond", "mid",  "rare",      (0.1, 0.8),   600, 0.55, ["bottom"],               "#cfeaf0", "See-through. Spooky, and valuable."),
    _s("gar",          "Needlenose Gar",    "pond", "far",  "common",    (2, 10),      40,  0.70, ["predator", "shoal"],    "#9fb08a", "Armoured, toothy, unimpressed."),
    _s("pike",         "Marsh Pike",        "pond", "far",  "uncommon",  (3, 15),      45,  0.80, ["predator"],             "#7d9a3a", "A green blur with teeth."),
    _s("moss_carp",    "Mossback Carp",     "pond", "far",  "uncommon",  (5, 25),      30,  0.70, ["shoal", "bottom"],      "#6e8a5a", "Wears a coat of moss like a cloak."),
    _s("golden_carp",  "Golden Carp",       "pond", "far",  "rare",      (3, 14),      130, 0.75, ["shoal", "rare"],        "#f0c040", "Said to bring luck to whoever lets it go."),
    _s("sturgeon",     "Ancient Sturgeon",  "pond", "far",  "legendary", (60, 180),    28,  1.00, ["bottom", "predator"],   "#8e9aa6", "A living fossil. It has seen the god fall."),
]
SPECIES_BY_ID: Dict[str, dict] = {s["id"]: s for s in SPECIES}

# ---- non-fish catches ------------------------------------------------------------------------------------------------
# kind "junk" = sells for a few coins; "treasure" = items / gems. `fight` is how hard the reel-in is (low: they don't struggle).
JUNK = [("Tangle of Weeds", 1, 0.05), ("Waterlogged Boot", 2, 0.05), ("Rusty Tin Can", 1, 0.05), ("Snagged Driftwood", 3, 0.10)]
TREASURE = [
    dict(name="Waterlogged Satchel", text="Inside: a Potion.",            give={"inventory": {"potion": 1}}, w=40),
    dict(name="Corked Bottle",       text="It holds an Antidote.",        give={"inventory": {"antidote": 1}}, w=30),
    dict(name="Sunken Supply Pouch", text="Two Potions, still sealed.",   give={"inventory": {"potion": 2}}, w=20),
    dict(name="Pearl Pouch",         text="A few gems clink inside.",     give={"gems": 2}, w=8),
    dict(name="Old Strongbox",       text="Coins, green with age.",       give={"money": 160}, w=10),
]
TREASURE_CHANCE = 0.05
JUNK_CHANCE = 0.10

# ---- tackle ----------------------------------------------------------------------------------------------------------
RODS: Dict[str, dict] = {
    "driftwood":  dict(id="driftwood",  name="Driftwood Rod",       cost=0,    reach=14, power=1.00, stress=1.00, window=0.85, luck=0.00, tolerance=0.35,
                       desc="A bent stick and some string. Reaches the shallows and a little beyond."),
    "bamboo":     dict(id="bamboo",     name="Bamboo Rod",          cost=400,  reach=21, power=1.15, stress=0.90, window=1.05, luck=0.05, tolerance=0.45,
                       desc="Springy and light. Casts into the far water; a touch more forgiving."),
    "fiberglass": dict(id="fiberglass", name="Fiberglass Rod",      cost=1600, reach=27, power=1.30, stress=0.78, window=1.25, luck=0.12, tolerance=0.60,
                       desc="A real angler's rod. Long casts, smooth drag, rarer fish take notice."),
    "carbon":     dict(id="carbon",     name="Master's Carbon Rod", cost=6000, reach=33, power=1.50, stress=0.62, window=1.50, luck=0.25, tolerance=0.80,
                       desc="The best that money buys. The line forgives almost everything."),
}
ROD_ORDER = ["driftwood", "bamboo", "fiberglass", "carbon"]

BAITS: Dict[str, dict] = {
    "none":   dict(id="none",   name="Bare Hook",    cost=0,   pack=0, wait=1.00, luck=0.00, affinity={}, desc="No bait. Fish are not impressed."),
    "worm":   dict(id="worm",   name="Worms",        cost=15,  pack=5, wait=0.80, luck=0.00, affinity={"small": 3.0, "bottom": 2.0}, desc="Quick bites from small and bottom-feeding fish."),
    "dough":  dict(id="dough",  name="Dough Balls",  cost=30,  pack=5, wait=0.85, luck=0.00, affinity={"shoal": 3.0}, desc="Shoaling fish swarm it: mullet, bream, trout, carp."),
    "shrimp": dict(id="shrimp", name="Fresh Shrimp", cost=60,  pack=5, wait=0.80, luck=0.04, affinity={"gourmet": 3.0, "bottom": 1.5}, desc="Table fish love it: snapper, crab, tuna, trout."),
    "minnow": dict(id="minnow", name="Live Minnows", cost=90,  pack=5, wait=1.10, luck=0.04, affinity={"predator": 4.0, "small": 0.4, "shoal": 0.6}, desc="Big predators only. Slower bites, bigger fish."),
    "glow":   dict(id="glow",   name="Glow Lure",    cost=220, pack=3, wait=1.00, luck=0.30, affinity={"rare": 2.0}, desc="Strange fish rise to it. Raises your odds of rare catches a lot."),
}
BAIT_ORDER = ["none", "worm", "dough", "shrimp", "minnow", "glow"]

CAST_BUCKET_MAX = 8.0
CAST_REGEN_SECONDS = 45.0                       # one more cast every 45 s, up to CAST_BUCKET_MAX stored (keeps fishing a break, not an income machine)


def validate() -> List[str]:
    """Problems with the tables above (empty = fine)."""
    bad: List[str] = []
    seen = set()
    for s in SPECIES:
        if s["id"] in seen: bad.append("duplicate species " + s["id"])
        seen.add(s["id"])
        if s["spot"] not in SPOTS: bad.append(f"{s['id']}: unknown spot")
        if s["zone"] not in ZONES: bad.append(f"{s['id']}: unknown zone")
        if s["rarity"] not in RARITIES: bad.append(f"{s['id']}: unknown rarity")
        if not (0 < s["kg"][0] < s["kg"][1]): bad.append(f"{s['id']}: bad weight range")
    for spot in SPOTS:
        for z in ZONES:
            if not [s for s in SPECIES if s["spot"] == spot and s["zone"] == z]: bad.append(f"{spot}/{z}: no species")
        for r in SPOTS[spot]["rods"]:
            if r not in RODS: bad.append(f"{spot}: unknown rod {r}")
        for b in SPOTS[spot]["baits"]:
            if b not in BAITS: bad.append(f"{spot}: unknown bait {b}")
    if RODS["driftwood"]["cost"] != 0: bad.append("the starter rod must be free")
    return bad

"""The overworld's actual content: towns, a connecting field, one dungeon,
and the warp back into the Colosseum hub -- the first-pass "bigger" slice
Andrew asked for (multiple towns/regions, a dungeon, NPCs with dialogue, and
the Colosseum as one destination within a larger world, not the whole game
anymore).

Sprites are reused battle idle/run sheets (data/Battlers/<Name>/) as
placeholder overworld art, exactly as agreed -- real overworld art can swap
these names out later without touching game/world.py or hub_server.py at
all, since nothing here cares whether a sheet is "real" or a placeholder.

Map layout: HAVEN_TOWN <-> FIELD_ROAD <-> EMBER_TOWN, with FIELD_ROAD also
dropping south into DUNGEON_HOLLOW. HAVEN_TOWN additionally has a warp tile
that opens the Colosseum hub (the pre-existing game) instead of another map.

FIELD_ROAD is deliberately bigger than the towns/dungeon (33x15 vs. their
13x9) -- it's the one map meant to actually need html_overworld/index.html's
camera-follow scrolling rather than fit on screen at once, so it's built
programmatically below (_build_field_road_tiles) instead of hand-typed like
the smaller maps, which keeps a grid that size easy to read and edit.
"""
from game.world import MapDef, NPC, Warp, WARP_TO_COLOSSEUM

START_MAP = "haven_town"

HAVEN_TOWN = MapDef(
    id="haven_town",
    name="Haven Town",
    tiles=[
        "#############",
        "#...........#",
        "#.T.......T.#",
        "#...........#",
        "#............",
        "#...........#",
        "#..#...#....#",
        "#...........#",
        "#############",
    ],
    spawn=(6, 7), spawn_facing="up",
    npcs=[
        NPC(id="kael_haven", name="Kael", x=7, y=2, sprite="Kael", facing="down", lines=[
            "Kael: First time out of the Colosseum, huh?",
            "Kael: The whole world opened back up once someone finally rebuilt the roads.",
            "Kael: Follow the road east and you'll hit the fields, then Ember Town.",
        ]),
        NPC(id="sera_haven", name="Sera", x=9, y=6, sprite="Sera", facing="left", lines=[
            "Sera: That glowing archway is the Colosseum entrance.",
            "Sera: Step on it whenever you want to fight, shop, or manage your party.",
            "Sera: We'll still be here when you get back.",
        ]),
    ],
    warps=[
        Warp(x=4, y=3, target_map=WARP_TO_COLOSSEUM, label="Colosseum"),
        # Field Road's west opening now sits at its own (1, 7) -- see _build_field_road_tiles below,
        # its geometry changed independently of this map's.
        Warp(x=12, y=4, target_map="field_road", target_x=1, target_y=7,
             target_facing="right", label="Field Road"),
    ],
)


def _build_field_road_tiles():
    """A 33x15 grid -- roughly 6x the tile count of a town -- big enough that
    html_overworld/index.html's camera actually has to follow the player instead of
    showing the whole map at once. Built as a grid of characters and joined into rows at
    the end, rather than hand-typed like the smaller maps, so a grid this size stays easy
    to read/tweak without miscounting a row's length by one somewhere.

    Layout: a solid outer wall with three openings -- west (to Haven Town) and east (to
    Ember Town) both at the map's vertical center (y=7), and a path south to the dungeon
    entrance at (16, 12). Two guaranteed clear lanes connect all three: the full-width
    row at y=7, and the column at x=16 from y=7 down to y=12 -- ponds/trees are placed
    off both lanes so there's always a walkable route between every warp regardless of
    where the decorative obstacles land.
    """
    W, H = 33, 15
    grid = [["." for _ in range(W)] for _ in range(H)]
    for x in range(W):
        grid[0][x] = "#"
        grid[H - 1][x] = "#"
    for y in range(H):
        grid[y][0] = "#"
        grid[y][W - 1] = "#"
    grid[7][0] = "."     # west opening -> Haven Town
    grid[7][W - 1] = "." # east opening -> Ember Town

    def rect(x0, y0, x1, y1, ch):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                grid[y][x] = ch

    # Two ponds, kept clear of the y=7 east-west lane and the x=16 north-south lane.
    rect(20, 2, 27, 5, "~")
    rect(5, 9, 12, 12, "~")
    # Two tall-grass encounter patches flanking the ponds.
    rect(2, 2, 9, 6, ",")
    rect(22, 9, 30, 13, ",")
    # A scatter of decorative trees, clear of both lanes and the water/grass blocks above.
    for (tx, ty) in [(13, 2), (14, 3), (19, 11), (18, 12), (2, 11), (3, 12), (29, 3), (30, 2)]:
        if grid[ty][tx] == ".":
            grid[ty][tx] = "T"
    return ["".join(row) for row in grid]


FIELD_ROAD = MapDef(
    id="field_road",
    name="Field Road",
    tiles=_build_field_road_tiles(),
    spawn=(1, 7), spawn_facing="right",
    encounter_chance=0.14,
    npcs=[],
    warps=[
        Warp(x=0, y=7, target_map="haven_town", target_x=11, target_y=4,
             target_facing="left", label="Haven Town"),
        Warp(x=32, y=7, target_map="ember_town", target_x=1, target_y=4,
             target_facing="right", label="Ember Town"),
        Warp(x=16, y=12, target_map="dungeon_hollow", target_x=6, target_y=7,
             target_facing="up", label="Hollow Depths"),
    ],
)

EMBER_TOWN = MapDef(
    id="ember_town",
    name="Ember Town",
    tiles=[
        "#############",
        "#...........#",
        "#.T.......T.#",
        "#...........#",
        "............#",
        "#...........#",
        "#....###....#",
        "#...........#",
        "#############",
    ],
    spawn=(1, 4), spawn_facing="left",
    npcs=[
        NPC(id="mira_ember", name="Old Mira", x=6, y=2, sprite="Lyra", facing="down", lines=[
            "Old Mira: Ember Town's smaller than Haven, but the smiths here are sharper.",
            "Old Mira: Something's stirring in the Hollow south of the field road again.",
            "Old Mira: Take a mercenary or two if you're headed down there.",
        ]),
        NPC(id="merchant_ember", name="Traveling Merchant", x=9, y=6, sprite="Rook", facing="up",
            navigate="/shop", lines=[
                "Traveling Merchant: Ah, a customer! My real stock's back at the Colosseum shop.",
                "Traveling Merchant: Here, I'll walk you over.",
            ]),
    ],
    warps=[
        # Field Road's east opening now sits at its own (32, 7) -- see _build_field_road_tiles above.
        Warp(x=0, y=4, target_map="field_road", target_x=31, target_y=7,
             target_facing="left", label="Field Road"),
    ],
)

DUNGEON_HOLLOW = MapDef(
    id="dungeon_hollow",
    name="Hollow Depths",
    tiles=[
        "#############",
        "#...........#",
        "#.##.....##.#",
        "#.#,,,,,,,#.#",
        "#.#,,,,,,,#.#",
        "#.#,,,,,,,#.#",
        "#...........#",
        "#...........#",
        "######.######",
    ],
    spawn=(6, 7), spawn_facing="up",
    encounter_chance=0.20,
    npcs=[
        NPC(id="guardian_hollow", name="Ancient Guardian", x=6, y=4, sprite="Yulia", facing="down",
            boss_id="ancient_guardian_boss", lines=[
                "Ancient Guardian: You've come far enough, traveler.",
                "Ancient Guardian: Prove your party is worth the rest of this dungeon!",
            ]),
    ],
    warps=[
        # Lands just north of Field Road's dungeon-entrance tile (16, 12) so walking out
        # doesn't immediately re-trigger the warp back in.
        Warp(x=6, y=8, target_map="field_road", target_x=16, target_y=11,
             target_facing="down", label="Field Road"),
    ],
)

WORLD_MAPS = {
    m.id: m for m in (HAVEN_TOWN, FIELD_ROAD, EMBER_TOWN, DUNGEON_HOLLOW)
}

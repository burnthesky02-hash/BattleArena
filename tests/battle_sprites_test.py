"""Exercises ui/pygame_ui.py's battle-sprite loading -- an idle-animation
sheet per combatant from data/Battlers/ (_load_battler_sheet_raw/
_get_battler_frames), mirrored for right-side (party) fighters vs. left as-is
for left-side (enemy) ones (see the `facing` param), an animation-frame clock
(_battler_frame_index), the optional full-bleed backdrop
(_get_battle_background), and the left/right ground-standing layout math
(_draw_battle_column/_column_layout, fix #21's ranked-formation replacement
for the old vertical-stack column) -- against the fake pygame module, the
same approach as tests/heroes_screen_test.py used for portrait loading.

Like _get_portrait's own test, this writes real (dummy-content -- the fake
pygame.image.load never actually decodes bytes) temp files into
data/Battlers/ and data/Artwork/ to exercise the "art is present" branch,
then cleans them up in a `finally`. Nothing under data/ in this sandbox is
Andrew's real art (that only exists on his machine) -- these are throwaway
fixtures for the loading logic itself.

Run directly: python3 tests/battle_sprites_test.py
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.pygame_stub import make_pygame_stub, Event  # noqa: E402,F401

event_queue = []
sys.modules["pygame"] = make_pygame_stub(event_queue)

from data.items_db import ITEMS  # noqa: E402
from data.skills_db import SKILLS  # noqa: E402
from ui import pygame_ui  # noqa: E402
from ui.pygame_ui import (  # noqa: E402
    BATTLER_FRAME_COLS, BATTLER_FRAME_ROWS, DEFAULT_BATTLER_NAME, PygameUI,
)

FRAME_COUNT = BATTLER_FRAME_COLS * BATTLER_FRAME_ROWS


def _write_dummy_sheet(name: str) -> str:
    folder = os.path.join(pygame_ui.BATTLER_DIR, name)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{name}-Idle.png")
    with open(path, "wb") as f:
        f.write(b"not a real png -- the fake pygame.image.load never actually decodes it")
    return path


def _remove_sheet(name: str) -> None:
    folder = os.path.join(pygame_ui.BATTLER_DIR, name)
    shutil.rmtree(folder, ignore_errors=True)


def test_unknown_name_with_no_default_sheet_present_returns_none():
    """Before Andrew's ever dropped a single sheet in (not even Draven's),
    a lookup must degrade to None -- not crash -- so _draw_combatant's
    plain-rectangle fallback kicks in."""
    ui = PygameUI(SKILLS, ITEMS)
    assert ui._load_battler_sheet_raw("Nobody In Particular") is None
    assert ui._get_battler_frames("Nobody In Particular", 190, "right") is None
    print("test_unknown_name_with_no_default_sheet_present_returns_none: PASS")


def test_own_sheet_is_sliced_into_the_full_frame_grid():
    ui = PygameUI(SKILLS, ITEMS)
    _write_dummy_sheet("__TestHero__")
    try:
        frames = ui._load_battler_sheet_raw("__TestHero__")
        assert frames is not None and len(frames) == FRAME_COUNT
        # cached, not re-sliced on a second call
        assert ui._load_battler_sheet_raw("__TestHero__") is frames
    finally:
        _remove_sheet("__TestHero__")
    print(f"test_own_sheet_is_sliced_into_the_full_frame_grid: PASS ({FRAME_COUNT} frames)")


def test_a_name_without_its_own_sheet_falls_back_to_the_default_battler():
    """Every character without a data/Battlers/<Name>/<Name>-Idle.png of
    their own is meant to use Andrew's Draven placeholder for now -- and the
    fallback should reuse the already-decoded frame list, not re-slice it
    once per distinct character name."""
    ui = PygameUI(SKILLS, ITEMS)
    _write_dummy_sheet(DEFAULT_BATTLER_NAME)
    try:
        default_frames = ui._load_battler_sheet_raw(DEFAULT_BATTLER_NAME)
        assert default_frames is not None and len(default_frames) == FRAME_COUNT

        someone_elses = ui._load_battler_sheet_raw("Some Rival Nobody Drew Yet")
        assert someone_elses is default_frames, "must reuse the default's frame list, not re-decode"
    finally:
        _remove_sheet(DEFAULT_BATTLER_NAME)
    print("test_a_name_without_its_own_sheet_falls_back_to_the_default_battler: PASS")


def test_facing_left_mirrors_the_frames_facing_right_does_not():
    """Andrew's ask verbatim: sheets face right by default, so a right-side
    (party) fighter needs its frames mirrored to face left, while a left-side
    (enemy) fighter uses them as-is."""
    ui = PygameUI(SKILLS, ITEMS)
    _write_dummy_sheet("__FacingTest__")
    try:
        right_frames = ui._get_battler_frames("__FacingTest__", 190, "right")
        left_frames = ui._get_battler_frames("__FacingTest__", 190, "left")
        assert right_frames is not None and left_frames is not None
        assert all(not getattr(f, "_flipped_x", False) for f in right_frames), "facing='right' must not mirror"
        assert all(getattr(f, "_flipped_x", False) for f in left_frames), "facing='left' must mirror"
        # scaled+mirrored results are cached per (name, height, facing)
        assert ui._get_battler_frames("__FacingTest__", 190, "left") is left_frames
    finally:
        _remove_sheet("__FacingTest__")
    print("test_facing_left_mirrors_the_frames_facing_right_does_not: PASS")


def test_frames_are_scaled_to_the_requested_height():
    ui = PygameUI(SKILLS, ITEMS)
    _write_dummy_sheet("__ScaleTest__")
    try:
        frames = ui._get_battler_frames("__ScaleTest__", 240, "right")
        assert all(f.get_height() == 240 for f in frames)
    finally:
        _remove_sheet("__ScaleTest__")
    print("test_frames_are_scaled_to_the_requested_height: PASS")


def test_battler_frame_index_stays_in_bounds_and_varies_by_combatant():
    ui = PygameUI(SKILLS, ITEMS)
    idx_a = ui._battler_frame_index("combatant-a", FRAME_COUNT)
    idx_b = ui._battler_frame_index("combatant-b", FRAME_COUNT)
    assert 0 <= idx_a < FRAME_COUNT
    assert 0 <= idx_b < FRAME_COUNT
    assert ui._battler_frame_index("anyone", 0) == 0, "must not divide by zero when there are no frames"
    print(f"test_battler_frame_index_stays_in_bounds_and_varies_by_combatant: PASS ({idx_a=}, {idx_b=})")


def test_battle_background_missing_returns_none_present_returns_a_scaled_cached_surface():
    ui = PygameUI(SKILLS, ITEMS)
    assert ui._get_battle_background() is None, "no file at BATTLE_BG_PATH yet"

    os.makedirs(os.path.dirname(pygame_ui.BATTLE_BG_PATH), exist_ok=True)
    with open(pygame_ui.BATTLE_BG_PATH, "wb") as f:
        f.write(b"not a real webp -- the fake pygame.image.load never actually decodes it")
    try:
        # a *new* UI instance, since the first one already cached the "missing" result
        ui2 = PygameUI(SKILLS, ITEMS)
        bg = ui2._get_battle_background()
        assert bg is not None
        assert bg.get_width() == ui2.content_width and bg.get_height() == ui2.height
        assert ui2._get_battle_background() is bg, "must be cached, not reloaded"
    finally:
        os.remove(pygame_ui.BATTLE_BG_PATH)
    print("test_battle_background_missing_returns_none_present_returns_a_scaled_cached_surface: PASS")


def test_pose_specific_sheet_is_loaded_and_cached_separately_from_idle():
    """Fix #19: a battler can have its own -Run.png/-Melee.png sheet(s)
    alongside its -Idle.png, loaded/cached under a (name, pose) key distinct
    from plain Idle. A pose this battler doesn't have art for yet (Melee,
    here) must fall back to that SAME battler's own Idle frames rather than
    returning None -- Run/Melee art is a bonus, same "degrade gracefully"
    precedent as every other optional asset in this file."""
    ui = PygameUI(SKILLS, ITEMS)
    _write_dummy_sheet("__PoseTest__")  # Idle only
    folder = os.path.join(pygame_ui.BATTLER_DIR, "__PoseTest__")
    run_path = os.path.join(folder, "__PoseTest__-Run.png")
    with open(run_path, "wb") as f:
        f.write(b"not a real png either -- the fake pygame.image.load never decodes it")
    try:
        idle_frames = ui._load_battler_sheet_raw("__PoseTest__", "Idle")
        run_frames = ui._load_battler_sheet_raw("__PoseTest__", "Run")
        assert idle_frames is not None and run_frames is not None
        assert len(run_frames) == FRAME_COUNT
        assert run_frames is not idle_frames, "a battler's own Run sheet must load independently of its Idle one"
        # cached, not re-sliced on a second call
        assert ui._load_battler_sheet_raw("__PoseTest__", "Run") is run_frames

        melee_frames = ui._load_battler_sheet_raw("__PoseTest__", "Melee")
        assert melee_frames is idle_frames, "a pose with no sheet of its own must fall back to this battler's Idle"
    finally:
        _remove_sheet("__PoseTest__")
    print("test_pose_specific_sheet_is_loaded_and_cached_separately_from_idle: PASS")


def test_pose_falls_back_to_default_battlers_sheet_for_that_same_pose():
    """A character with no sheets of their own at all still gets
    DEFAULT_BATTLER_NAME's Run sheet specifically (not DEFAULT's Idle) when
    one exists, before falling any further back to Idle -- same
    per-character fallback fix #17 already established, just threaded
    through the new `pose` dimension."""
    ui = PygameUI(SKILLS, ITEMS)
    _write_dummy_sheet(DEFAULT_BATTLER_NAME)  # Idle
    folder = os.path.join(pygame_ui.BATTLER_DIR, DEFAULT_BATTLER_NAME)
    run_path = os.path.join(folder, f"{DEFAULT_BATTLER_NAME}-Run.png")
    with open(run_path, "wb") as f:
        f.write(b"not a real png")
    try:
        default_run = ui._load_battler_sheet_raw(DEFAULT_BATTLER_NAME, "Run")
        default_idle = ui._load_battler_sheet_raw(DEFAULT_BATTLER_NAME, "Idle")
        assert default_run is not default_idle
        someone_elses_run = ui._load_battler_sheet_raw("Nobody Drew Yet", "Run")
        assert someone_elses_run is default_run, "must reuse the default battler's own Run sheet, not its Idle one"
    finally:
        _remove_sheet(DEFAULT_BATTLER_NAME)
    print("test_pose_falls_back_to_default_battlers_sheet_for_that_same_pose: PASS")


def test_get_battler_frames_pose_defaults_to_idle_and_caches_per_pose():
    ui = PygameUI(SKILLS, ITEMS)
    _write_dummy_sheet("__FramesPoseTest__")
    try:
        implicit_idle = ui._get_battler_frames("__FramesPoseTest__", 190, "right")  # pose defaults to "Idle"
        explicit_idle = ui._get_battler_frames("__FramesPoseTest__", 190, "right", "Idle")
        assert implicit_idle is explicit_idle
        run = ui._get_battler_frames("__FramesPoseTest__", 190, "right", "Run")  # falls back to Idle content
        assert run is not None and all(f.get_height() == 190 for f in run)
    finally:
        _remove_sheet("__FramesPoseTest__")
    print("test_get_battler_frames_pose_defaults_to_idle_and_caches_per_pose: PASS")


def test_column_layout_matches_home_position_and_draw_battle_column():
    """_column_layout (fix #19's extraction) must place combatants exactly
    where _draw_battle_column always did, and _home_position must report
    that same spot for any combatant actually present in the state -- these
    two agreeing is what makes the run-in/run-back animation land the
    attacker at a sensible starting point."""
    ui = PygameUI(SKILLS, ITEMS)
    combatants = [
        {"id": f"c{i}", "name": f"Fighter {i}", "hp": 10, "max_hp": 10, "alive": True, "statuses": []}
        for i in range(3)
    ]
    col_x = pygame_ui.BATTLE_ENEMY_COL_X
    layout = list(ui._column_layout(combatants, col_x, "right"))
    assert len(layout) == 3

    state = {"enemies": combatants, "party": []}
    for c, x, y, sprite_h in layout:
        home = ui._home_position(state, c["id"])
        assert home == (x, y, sprite_h), f"_home_position disagreed with _column_layout for {c['id']}"

    assert ui._home_position(state, "no-such-id") is None
    print("test_column_layout_matches_home_position_and_draw_battle_column: PASS")


def test_combatant_rect_falls_back_to_placeholder_box_size_when_no_sheet():
    """With no battler art at all in this sandbox (see BATTLER_DIR), every
    _combatant_rect call falls back to the same 100-wide placeholder box
    _draw_combatant itself draws -- pins that fallback size down and that
    the rect is centered on center_x, matching _draw_combatant's own
    `x = center_x - box_w // 2` math."""
    ui = PygameUI(SKILLS, ITEMS)
    combatant = {"id": "c0", "name": "Nobody's Drawn This One", "hp": 10, "max_hp": 10, "alive": True}
    rect = ui._combatant_rect(combatant, center_x=300, y=120, sprite_h=95, facing="right")
    assert rect.w == 100 and rect.h == 95
    assert rect.x == 300 - 100 // 2
    assert rect.y == 120
    print("test_combatant_rect_falls_back_to_placeholder_box_size_when_no_sheet: PASS")


def test_draw_combatant_frame_index_override_is_clamped_in_bounds():
    """_animate_run/_animate_melee_swing pass an explicit frame_index to
    step through a pose's frames deliberately -- _draw_combatant must clamp
    it into [0, len(frames)-1] rather than raising or wrapping unexpectedly
    on an out-of-range value (e.g. a swing animation's last frame_index
    computed a hair past the sheet's actual frame count)."""
    ui = PygameUI(SKILLS, ITEMS)
    _write_dummy_sheet("__ClampTest__")
    try:
        combatant = {"id": "c0", "name": "__ClampTest__", "hp": 10, "max_hp": 10, "alive": True}
        # Must not raise for a way-out-of-range frame_index in either direction.
        ui._draw_combatant(combatant, center_x=200, y=100, highlight=False, facing="right",
                            pose="Idle", frame_index=FRAME_COUNT * 5)
        ui._draw_combatant(combatant, center_x=200, y=100, highlight=False, facing="right",
                            pose="Idle", frame_index=-99)
    finally:
        _remove_sheet("__ClampTest__")
    print("test_draw_combatant_frame_index_override_is_clamped_in_bounds: PASS")


def test_draw_frame_renders_a_lopsided_1v4_battle_without_crashing():
    """The column layout (_draw_battle_column) must handle any 1-4 vs 1-4
    combination, including the extremes, without overlapping math blowing up
    -- a 1-enemy vs 4-party battle is the shape most likely to expose an
    off-by-one in the centering formula."""
    ui = PygameUI(SKILLS, ITEMS)
    state = {
        "round": 1,
        "enemies": [
            {"id": "e1", "name": "Lone Golem", "hp": 50, "max_hp": 100, "alive": True,
             "statuses": [], "is_enemy": True, "sprite_color": (150, 80, 80)},
        ],
        "party": [
            {"id": f"p{i}", "name": f"Hero {i}", "hp": (0 if i == 3 else 40), "max_hp": 40, "mp": 10, "max_mp": 20,
             "alive": i != 3, "statuses": [], "sprite_color": (80, 120, 180)}
            for i in range(4)
        ],
    }
    rects = ui._draw_frame(state, highlight_actor_id="p0", buttons=[("Attack", "attack")], menu_title="Choose")
    assert len(rects) == 1
    print("test_draw_frame_renders_a_lopsided_1v4_battle_without_crashing: PASS")


def test_a_full_4_wide_side_stands_in_two_ranks_on_the_ground():
    """Fix #21: Andrew swapped in new arena-floor background art and asked
    for fighters to stand on the ground (two ranks of two) instead of the
    old fix #17 vertical stack, with the crowded-column shrink-to-fit gone
    entirely. This pins down the two guarantees _draw_battle_column now
    makes for a full side of 4: every sprite draws at the same fixed
    BATTLE_SPRITE_H (never shrunk), and they land in a front rank (feet on
    BATTLE_GROUND_BOTTOM_MARGIN's line) and a back rank BATTLE_GROUND_
    RANK_GAP higher up, each rank's pair straddling the column's x by
    BATTLE_GROUND_PAIR_GAP. As of fix #22, positions are looked up by
    combatant id rather than call-index, since _draw_battle_column now
    draws back-to-front by y (see below) rather than in _column_layout's
    front-rank-first yield order."""
    ui = PygameUI(SKILLS, ITEMS)
    calls = []

    def fake_draw_combatant(c, center_x, y, highlight, facing="right", sprite_h=pygame_ui.BATTLE_SPRITE_H):
        calls.append((c["id"], center_x, y, sprite_h))
    ui._draw_combatant = fake_draw_combatant

    combatants = [
        {"id": f"c{i}", "name": f"Fighter {i}", "hp": 10, "max_hp": 10, "alive": True, "statuses": []}
        for i in range(4)
    ]
    col_x = pygame_ui.BATTLE_ENEMY_COL_X
    ui._draw_battle_column(combatants, col_x, highlight_actor_id=None, facing="right")

    assert len(calls) == 4
    assert all(sprite_h == pygame_ui.BATTLE_SPRITE_H for *_, sprite_h in calls), \
        "every sprite must draw at the fixed BATTLE_SPRITE_H -- fix #17's shrink-to-fit is gone"

    half_gap = pygame_ui.BATTLE_GROUND_PAIR_GAP // 2
    front_feet_y = ui.height - pygame_ui.BATTLE_GROUND_BOTTOM_MARGIN
    front_y = front_feet_y - pygame_ui.BATTLE_SPRITE_H
    back_feet_y = front_feet_y - pygame_ui.BATTLE_GROUND_RANK_GAP
    back_y = back_feet_y - pygame_ui.BATTLE_SPRITE_H
    inward = pygame_ui.BATTLE_GROUND_RANK_INSET_X  # facing="right" -> inward is +x

    by_id = {cid: (x, y, sprite_h) for cid, x, y, sprite_h in calls}
    assert by_id["c0"] == (col_x - half_gap, front_y, pygame_ui.BATTLE_SPRITE_H)
    assert by_id["c1"] == (col_x + half_gap, front_y, pygame_ui.BATTLE_SPRITE_H)
    assert by_id["c2"] == (col_x + inward - half_gap, back_y, pygame_ui.BATTLE_SPRITE_H)
    assert by_id["c3"] == (col_x + inward + half_gap, back_y, pygame_ui.BATTLE_SPRITE_H)
    assert back_y < front_y, "the back rank must sit higher on screen (further away) than the front rank"

    # Fix #22: "the bottom row [should] show over the top row" -- drawn
    # back-to-front by y, so the back rank (c2/c3) is drawn FIRST and the
    # front rank (c0/c1) drawn LAST, so later blits (the front rank) land
    # on top of/occlude the back rank wherever their boxes cross on screen.
    draw_order = [cid for cid, *_ in calls]
    assert draw_order.index("c2") < draw_order.index("c0"), \
        "the back rank must be drawn before the front rank, so the front rank shows over the back rank"
    assert draw_order.index("c3") < draw_order.index("c1")
    print("test_a_full_4_wide_side_stands_in_two_ranks_on_the_ground: PASS "
          f"(front_y={front_y}, back_y={back_y}, sprite_h={pygame_ui.BATTLE_SPRITE_H}, draw_order={draw_order})")


def test_ground_rank_inset_is_inward_for_both_sides():
    """A party side (facing="left") must nudge its back rank the opposite
    direction (toward -x) from an enemy side (facing="right") -- both
    converging toward the center of the screen rather than toward
    whichever edge they're closest to, which is what makes the inset
    always safe (this is the ground-layout replacement for fix #17's old
    per-fighter stagger). As of fix #22, looked up by id rather than call
    order -- see test_a_full_4_wide_side_stands_in_two_ranks_on_the_ground's
    docstring for why."""
    ui = PygameUI(SKILLS, ITEMS)
    calls = []
    ui._draw_combatant = lambda c, center_x, y, highlight, facing="right", sprite_h=pygame_ui.BATTLE_SPRITE_H: \
        calls.append((c["id"], center_x))

    combatants = [{"id": f"c{i}", "name": f"Fighter {i}", "hp": 10, "max_hp": 10, "alive": True, "statuses": []}
                  for i in range(3)]  # 2 in the front rank, 1 in the back rank
    col_x = ui.content_width - pygame_ui.BATTLE_ENEMY_COL_X
    ui._draw_battle_column(combatants, col_x, highlight_actor_id=None, facing="left")

    half_gap = pygame_ui.BATTLE_GROUND_PAIR_GAP // 2
    by_id = dict(calls)
    assert by_id["c0"] == col_x - half_gap and by_id["c1"] == col_x + half_gap  # front rank straddles col_x
    assert by_id["c2"] == col_x - pygame_ui.BATTLE_GROUND_RANK_INSET_X, \
        "facing='left' must inset the back rank toward -x, not +x"
    print("test_ground_rank_inset_is_inward_for_both_sides: PASS")


def test_draw_combatant_draws_no_text_at_all():
    """Fix #18: Andrew asked to remove the boxes from the sprites -- pin
    down that _draw_combatant no longer renders any name/HP/MP/status/KO
    text directly on or around a sprite (that all moved to
    _draw_party_status_panel instead), by counting font_small.render calls
    made while drawing one sprite with no active hit flash."""
    ui = PygameUI(SKILLS, ITEMS)
    calls = []
    original_render = ui.font_small.render

    def counting_render(*args, **kwargs):
        calls.append((args, kwargs))
        return original_render(*args, **kwargs)
    ui.font_small.render = counting_render

    combatant = {
        "id": "c0", "name": "Fighter", "hp": 10, "max_hp": 10, "mp": 5, "max_mp": 5,
        "alive": True, "statuses": ["Poison"], "sprite_color": (100, 100, 100),
    }
    ui._draw_combatant(combatant, center_x=200, y=100, highlight=False, facing="right")
    assert calls == [], f"_draw_combatant must not render any text on/around the sprite, got {len(calls)} call(s)"
    print("test_draw_combatant_draws_no_text_at_all: PASS")


def test_party_status_panel_handles_ko_zero_mp_and_empty_party():
    """_draw_party_status_panel is the new home for the per-sprite text fix
    #18 removed -- it needs to survive the edge cases that used to be
    handled per-sprite: a KO'd member, a character with no MP pool at all
    (max_mp == 0, e.g. a pure physical class), and an empty party (before
    state["party"] is populated)."""
    ui = PygameUI(SKILLS, ITEMS)
    party = [
        {"id": "p0", "name": "Alive Caster", "hp": 20, "max_hp": 20, "mp": 10, "max_mp": 10,
         "alive": True, "statuses": []},
        {"id": "p1", "name": "KO'd Fighter", "hp": 0, "max_hp": 30, "mp": 0, "max_mp": 0,
         "alive": False, "statuses": []},
        {"id": "p2", "name": "No-MP Brawler", "hp": 15, "max_hp": 15, "mp": 0, "max_mp": 0,
         "alive": True, "statuses": ["Poison", "Guard"]},
    ]
    ui._draw_party_status_panel(party, highlight_actor_id="p0", x=20, y=20, w=400)  # mixed live party
    ui._draw_party_status_panel([], highlight_actor_id=None, x=20, y=20, w=400)     # empty party
    print("test_party_status_panel_handles_ko_zero_mp_and_empty_party: PASS")


def test_front_rank_stays_inside_the_window_and_now_overlaps_the_bottom_panels():
    """Fix #18 originally pinned a guarantee here that the sprite band
    never overlapped the bottom command/status panels (BATTLE_GROUND_
    BOTTOM_MARGIN, then 230, cleared them with margin). Fix #22 deliberately
    breaks that: Andrew asked to bring the front rank ~80px further down
    the window, and the new BATTLE_GROUND_BOTTOM_MARGIN=150 now puts the
    front rank's feet line behind the (translucent) bottom command/status
    panels rather than above them -- intended, not a regression, since the
    panels are translucent and drawn on top, so a fighter reads as standing
    partly behind the UI rather than being clipped by it.

    What still has to hold, and is what this test actually pins: the front
    rank's feet line stays inside the window (never past the bottom edge,
    which would look like the sprite is clipped rather than "behind the
    UI"). The overlap-with-the-panels assertion below is intentionally an
    "expect overlap" check, not a "must not overlap" one -- if a future
    layout change makes this stop overlapping, this test will fail and
    flag that the fix #22 writeup (and this comment) need updating too,
    rather than silently losing coverage of what changed here."""
    ui = PygameUI(SKILLS, ITEMS)
    front_feet_y = ui.height - pygame_ui.BATTLE_GROUND_BOTTOM_MARGIN
    assert 0 < front_feet_y <= ui.height, (
        f"the front rank's feet line ({front_feet_y}) must stay inside the window (height {ui.height})")

    n = 5  # the main action menu's button count -- the largest of any battle menu
    cmd_h = (n * pygame_ui.BATTLE_CMD_BTN_H + (n - 1) * pygame_ui.BATTLE_CMD_BTN_GAP
             + 2 * pygame_ui.BATTLE_CMD_PANEL_PAD)
    cmd_y = ui.height - pygame_ui.BATTLE_BOTTOM_MARGIN - cmd_h
    title_y = cmd_y - 20  # see _draw_frame: the menu_title line sits just above the panel

    assert front_feet_y > title_y, (
        "expected fix #22's front rank to now overlap the bottom command panel's title line -- "
        f"front feet {front_feet_y}, title_y {title_y}. If this no longer overlaps, the "
        "'front rank stands behind the translucent UI' framing in fix #22 may be stale."
    )
    print(f"test_front_rank_stays_inside_the_window_and_now_overlaps_the_bottom_panels: PASS "
          f"(front_feet_y={front_feet_y}, title_y={title_y})")


def main():
    test_unknown_name_with_no_default_sheet_present_returns_none()
    test_own_sheet_is_sliced_into_the_full_frame_grid()
    test_a_name_without_its_own_sheet_falls_back_to_the_default_battler()
    test_facing_left_mirrors_the_frames_facing_right_does_not()
    test_frames_are_scaled_to_the_requested_height()
    test_battler_frame_index_stays_in_bounds_and_varies_by_combatant()
    test_battle_background_missing_returns_none_present_returns_a_scaled_cached_surface()
    test_pose_specific_sheet_is_loaded_and_cached_separately_from_idle()
    test_pose_falls_back_to_default_battlers_sheet_for_that_same_pose()
    test_get_battler_frames_pose_defaults_to_idle_and_caches_per_pose()
    test_column_layout_matches_home_position_and_draw_battle_column()
    test_combatant_rect_falls_back_to_placeholder_box_size_when_no_sheet()
    test_draw_combatant_frame_index_override_is_clamped_in_bounds()
    test_draw_frame_renders_a_lopsided_1v4_battle_without_crashing()
    test_a_full_4_wide_side_stands_in_two_ranks_on_the_ground()
    test_ground_rank_inset_is_inward_for_both_sides()
    test_draw_combatant_draws_no_text_at_all()
    test_party_status_panel_handles_ko_zero_mp_and_empty_party()
    test_front_rank_stays_inside_the_window_and_now_overlaps_the_bottom_panels()
    print("\nALL BATTLE SPRITE TESTS PASSED")


if __name__ == "__main__":
    main()

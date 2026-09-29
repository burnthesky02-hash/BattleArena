"""Graphical UI: a click-driven action menu, bars for HP/MP, and a scrolling
log, with real art wherever Andrew's dropped it in and a colored-rectangle
fallback everywhere else. The Heroes page (see show_heroes) loads portrait
art from data/portraits/ (see PORTRAIT_DIR below). The battle screen (see
_draw_frame/_draw_combatant) loads an idle-animation sprite sheet per
combatant from data/Battlers/ (see BATTLER_DIR below) -- as of this pass,
only Andrew's "Draven" placeholder sheet exists, standing in for every
character until real per-hero sheets are added, exactly the way a missing
portrait falls back to a drawn placeholder. Battle is laid out as a classic
side-view duel: enemies stand on the left facing right (the sheet's
native orientation), party stands on the right facing left (the same
frames mirrored -- see _get_battler_frames's `facing` param), over a
full-bleed background image when one's present at BATTLE_BG_PATH. As of
fix #21, each side's up to 4 fighters stand in up to two ranks of up to
two each on the arena floor -- a front rank near the bottom of the screen
and a back rank higher up and nudged toward the opposing side, matching
the perspective floor in Andrew's current background art -- rather than
the fix #17 vertical stack a column used to be; that stagger/shrink-to-fit
scheme is gone entirely, and every sprite now always draws at the same
fixed BATTLE_SPRITE_H. See _column_layout/_draw_battle_column. The combat
log panel lives at the top of the screen, just under the round counter,
rather than at the bottom where it used to sit on top of the lowest
sprite in a full column.

As of fix #18, every battle-screen panel (log, the bottom command list,
and a new party status panel) is translucent (_draw_translucent_panel)
instead of a flat opaque fill, so the background art shows through.
_draw_combatant no longer draws any name/HP/MP text, status label, KO tag,
or highlight box on/around a sprite at all -- a party member's name/HP/MP
moved into a dedicated bottom-of-screen status panel
(_draw_party_status_panel), and enemies simply don't show any of that on
the battlefield, matching the reference screenshot Andrew sent. The old
4-column button grid became a single-column list inside its own
bottom-left command panel (every battle menu -- main actions or a
skill/item/target submenu -- tops out at 5 entries, so one column always
fits).

As of fix #19, a battler can carry up to three poses -- data/Battlers/
<Name>/<Name>-Idle.png (the standing loop, as before), -Run.png (a
looping run cycle), and -Melee.png (a one-shot 36-frame swing) -- loaded
the same way via _load_battler_sheet_raw/_get_battler_frames, now both
keyed by (name, pose) instead of just name. If a given pose doesn't exist
yet for a battler, the fallback goes narrowest-first: that battler's own
Idle frames if it has any art of its own at all (so a hero with bespoke
art but no Run/Melee sheet yet just holds their own idle pose during a
move, rather than jumping to a different character's sprite), then
DEFAULT_BATTLER_NAME's sheet for that same pose (so a battler with no art
of its own reuses the placeholder's matching pose, not straight to its
Idle), and only then DEFAULT_BATTLER_NAME's own Idle -- see
_load_battler_sheet_raw's docstring. Art is always a bonus, never a hard
requirement, same precedent as every other asset in this file. The basic
Attack action and any physical-kind skill now play out as a real move
instead of resolving in place: attach_engine wraps the BattleEngine's
resolve_action (see _resolve_action_with_movement) so the actor's sprite
runs from its column position to stand next to its target (_animate_run,
Run pose), plays the Melee swing in place (_animate_melee_swing) --
calling the engine's real, unwrapped resolve_action partway through the
swing, timed to land close to the sheet's own energy-burst frame so the
damage number/flash appear right around the visual impact -- then runs
back home. This is entirely a UI-side layer around
BattleEngine.resolve_action, the same "derive it, don't touch engine/"
precedent the hit-flash system already established; magical/heal/status
skills and non-attack actions (item/defend/flee) are untouched and still
resolve instantly. Separately, fix #19 also makes a combatant's own
on-screen sprite clickable as a target wherever the text button menu
already offers it as one (see _draw_frame's use of
_sprite_click_targets) -- clicking the sprite is exactly equivalent to
clicking its row in the target list, no changes needed to the actual
targeting logic in get_party_action/_choose_target/_wait_for_choice.

As of fix #21, Andrew swapped in new background art (data/Artwork/
Background.webp) that's an actual arena-floor scene -- a circular stone
floor with a visible perspective vanishing point at back-center,
replacing the old atmospheric vista with no ground plane at all (kept
around as Background1.webp for reference) -- and asked for the layout to
match it ("reposition the fighters to appear on the ground instead...
closer to a 2.5D perspective") and for the old crowded-column shrink-to-
fit to go away ("remove the shrinking of the heroes"). _column_layout now
places each side's fighters in up to two ranks of up to two (front rank
low/near, back rank high/far and shifted toward the opposing column,
echoing the floor's converging tile lines) instead of a tall single-file
stack, and every sprite draws at the same fixed BATTLE_SPRITE_H regardless
of party size -- see the BATTLE_GROUND_* constants below.
_home_position/_sprite_click_targets/_animate_run/_animate_melee_swing
needed no changes at all for this: they only ever consumed whatever
(x, y, sprite_h) _column_layout handed them, never assumed anything about
the shape of a column.

As of fix #22, Andrew tuned that ground layout after seeing it against
his real art: both sides moved ~100px toward screen center
(BATTLE_ENEMY_COL_X 230 -> 330), the front rank moved 80px further down
the window (BATTLE_GROUND_BOTTOM_MARGIN 230 -> 150, which now
intentionally lets the front rank's feet sit behind the translucent
bottom command/status panels rather than clearing them), the gap between
ranks widened by 20px (BATTLE_GROUND_RANK_GAP 96 -> 116), and
_draw_battle_column now draws back-to-front by y so the front rank's
sprites visually overlap/occlude the back rank's where they cross on
screen, instead of the reverse. See fix #22 below.

pygame is imported lazily (inside __init__) so the rest of the codebase --
and the headless tests -- can be imported and run even in an environment
that doesn't have pygame installed (e.g. this project's own CI/sandbox).
"""
import math
import os
import time

from engine.actions import Action
from engine.types import ActionType

WIDTH, HEIGHT = 1280, 800
HIT_FLASH_DURATION = 0.5   # seconds a hit/heal flash + floating number stays visible
DEBUG_PANEL_W = 320
BG_COLOR = (24, 24, 34)
PANEL_COLOR = (40, 40, 56)
DEBUG_PANEL_COLOR = (30, 34, 48)
TEXT_COLOR = (235, 235, 240)
DIM_COLOR = (120, 120, 130)
HP_GREEN = (70, 190, 90)
HP_YELLOW = (220, 190, 60)
HP_RED = (210, 70, 70)
MP_BLUE = (70, 130, 220)
HIGHLIGHT = (255, 255, 255)
BUTTON_COLOR = (60, 60, 84)
BUTTON_HOVER = (90, 90, 130)
THINKING_COLOR = (230, 200, 90)
LLM_COLOR = (120, 220, 140)
FALLBACK_COLOR = (230, 150, 60)

# Where Andrew drops portrait art, one image per character, named after the
# character (e.g. "Kael.png") -- see show_heroes' hero-card grid below.
# Deliberately just a folder of loose images, not a data/portraits.py
# registry: nothing in code needs to know the full set of filenames up
# front, since _get_portrait() only ever looks up one name at a time and
# falls back to a drawn placeholder when that name has no file yet, so
# dropping in art is a zero-code-change, drop-the-file-in operation.
PORTRAIT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "portraits")
PORTRAIT_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")

# Mobile-gacha-style hero card grid (see show_heroes) -- module-level so
# tests can import the exact geometry instead of hardcoding magic numbers
# (same convention as HEIGHT/WIDTH above).
HERO_CARD_W = 150
HERO_CARD_H = 190
HERO_CARD_GAP = 16
HERO_GRID_COLS = 4
HERO_GRID_LEFT = 30
HERO_GRID_TOP = 96
HERO_CARD_BANNER_H = 46   # bottom strip of a card: name/level/star pips, over the portrait
HERO_DETAIL_X = HERO_GRID_LEFT + HERO_GRID_COLS * (HERO_CARD_W + HERO_CARD_GAP) + 24  # right-panel left edge

# Party Select screen layout (see show_party_select), added in fix #20 to
# replace that screen's old plain toggle-list with a card layout matching
# show_heroes: a fixed top strip of MAX_PARTY_SIZE slot-cards showing the
# current party, then a scrollable grid of every owned hero below it (the
# same HERO_GRID_*/HERO_CARD_* geometry show_heroes uses for its own grid,
# so the two screens read as one visual family and share portrait cache
# entries for a hero shown on both). Slot cards are smaller than the Heroes
# grid's own cards purely to leave more vertical room for the roster grid
# underneath -- same _draw_hero_card draw path either way, just a different
# size/banner-height passed in. Clicking a hero's portrait -- in the top
# strip or in the grid below -- toggles them in/out of the party.
PARTY_SELECT_SLOT_W = 130
PARTY_SELECT_SLOT_H = 158
PARTY_SELECT_SLOT_BANNER_H = 34
PARTY_SELECT_SLOT_GAP = 14
PARTY_SELECT_SLOT_TOP = 104         # y of the top "your party" strip
PARTY_SELECT_ROSTER_LABEL_Y = 278   # "All Heroes" label, just under the strip
PARTY_SELECT_ROSTER_GRID_TOP = 300  # roster grid top -- x/cards reuse HERO_GRID_LEFT/HERO_CARD_*

# Summon screen layout (see show_summon): a left banner rail + a big center
# splash panel + a bottom pull bar when idle, or a card-flip reveal (one big
# card for a x1 pull, a 5-wide grid for a x10 pull) after a pull. Module-level
# for the same reason as the HERO_* constants above -- tests import the real
# geometry instead of hardcoding magic numbers.
SUMMON_RAIL_X = 30
SUMMON_RAIL_Y = 92
SUMMON_RAIL_W = 230
SUMMON_RAIL_TILE_H = 108
SUMMON_RAIL_GAP = 14
SUMMON_PANEL_X = SUMMON_RAIL_X + SUMMON_RAIL_W + 24   # splash panel's left edge

SUMMON_PULL_BTN_W = 260
SUMMON_PULL_BTN_H = 64
SUMMON_PULL_BTN_GAP = 20

# A x1 pull's reveal is one big card...
SUMMON_SOLO_CARD_W = 240
SUMMON_SOLO_CARD_H = 320
SUMMON_SOLO_BANNER_H = 70
SUMMON_SOLO_TAG_H = 30

# ...a x10 pull's reveal is a grid of smaller face-down/face-up cards.
SUMMON_REVEAL_CARD_W = 150
SUMMON_REVEAL_CARD_H = 210
SUMMON_REVEAL_CARD_GAP = 18
SUMMON_REVEAL_COLS = 5
SUMMON_REVEAL_TOP = 140
SUMMON_REVEAL_BANNER_H = 46
SUMMON_REVEAL_TAG_H = 20

# Battle screen background art -- see the module docstring. Optional: when
# the file isn't there (or fails to load), _get_battle_background() returns
# None and _draw_frame just leaves the plain BG_COLOR fill showing, the same
# "art is a bonus, never a hard requirement" precedent as portraits/battlers.
BATTLE_BG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "Artwork", "Background.webp")

# Where Andrew drops battle sprite sheets, one folder per character (e.g.
# data/Battlers/Draven/Draven-Idle.png), mirroring PORTRAIT_DIR's "just a
# folder of loose files, no registry" convention above. Each sheet is a
# BATTLER_FRAME_COLS x BATTLER_FRAME_ROWS grid of equal-sized frames read in
# row-major order as one continuous idle loop, drawn facing right (see
# _get_battler_frames's `facing` param for how a right-side fighter gets
# mirrored to face left instead).
BATTLER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "Battlers")
BATTLER_FRAME_COLS = 6
BATTLER_FRAME_ROWS = 6
BATTLER_ANIM_FPS = 8   # idle-loop playback speed -- tune-by-feel, same spirit as every other pacing constant here
# Andrew's placeholder idle sheet: every combatant without a
# data/Battlers/<Name>/<Name>-Idle.png of their own falls back to this one
# (see _load_battler_sheet_raw), so "add sprites" didn't need to wait on 25+
# individual character sheets to exist first.
DEFAULT_BATTLER_NAME = "Draven"

# Battle sprite layout (fix #21): a classic side-view duel, enemies
# standing on the left, party standing on the right, both feet-anchored to
# the arena floor near the bottom of the window rather than stacked in a
# tall column -- module-level for the same reason as every other screen's
# layout constants (HERO_*/SUMMON_* above): tests import the real geometry
# instead of hardcoding magic numbers.
BATTLE_SPRITE_H = 190          # on-screen display height for every battler sprite -- fixed, never shrunk to fit
                                # (fix #17's BATTLE_SPRITE_MIN_H shrink-to-cram scheme is gone per Andrew's ask)
BATTLE_ENEMY_COL_X = 430       # enemy side's horizontal anchor (party's is content_width - this, computed at draw
                                # time) -- fix #23 pulled both sides another 100px toward center from fix #22's 330
BATTLE_GROUND_BOTTOM_MARGIN = 150  # front rank's feet line, measured up from self.height -- fix #22 dropped this
                                     # 80px from fix #21's 230 per Andrew's ask, which now intentionally lets the
                                     # front rank's feet sit behind the (translucent) bottom command/status panels
                                     # rather than clearing them, see fix #22 below
BATTLE_GROUND_RANK_GAP = 60   # how much higher each subsequent row's feet line sits than the one below it -- adjusted for 4-row staggered layout
BATTLE_GROUND_PAIR_GAP = 180    # horizontal gap between the two fighters sharing a rank
BATTLE_GROUND_RANK_INSET_X = 180  # how far the back rank shifts toward the opposing side vs. the front rank -- the
                                   # perspective cue that sells "further back on a floor converging toward the
                                   # arena's center", the ground-layout analog of fix #17's old per-fighter stagger

# Battle log panel: fix #17 moved this from the bottom of the screen (where
# it used to sit right on top of the bottom sprite(s) in a full column) up
# to just under the round counter -- the button bar/menu title stay put at
# the bottom, since those are the input controls, not the combat log.
BATTLE_LOG_Y = 36
BATTLE_LOG_H = 90

# Bottom command panel + party status panel (fix #18): a translucent,
# rounded, bottom-anchored pair of boxes -- a narrow single-column action
# list on the left (Attack/Skill/Item/Defend/Flee, or whatever submenu is
# currently active) and a wider party HP/MP readout on the right --
# replacing the old 4-column opaque button grid and the old per-sprite
# name/HP/MP text respectively. Modeled on the reference screenshot Andrew
# sent (a compact command list plus a separate status strip, both sitting
# on top of the battle art rather than a solid bar blocking it). Every
# submenu (skill/item/target) tops out at 5 entries -- the same as the
# 5-button main menu -- so one single-column layout covers all of them,
# no per-menu-type branching needed.
BATTLE_BOTTOM_MARGIN = 14      # margin from the window's left/right/bottom edges for both bottom panels
BATTLE_CMD_PANEL_X = 14
BATTLE_CMD_BTN_W = 190
BATTLE_CMD_BTN_H = 28
BATTLE_CMD_BTN_GAP = 6
BATTLE_CMD_PANEL_PAD = 10
BATTLE_CMD_PANEL_W = BATTLE_CMD_BTN_W + 2 * BATTLE_CMD_PANEL_PAD

BATTLE_STATUS_PANEL_GAP = 16   # gap between the command panel's right edge and the status panel's left edge
BATTLE_STATUS_PANEL_W = 520    # capped against content_width at draw time, see _draw_frame
BATTLE_STATUS_PANEL_PAD = 10
BATTLE_STATUS_ROW_H = 34
BATTLE_STATUS_BAR_W = 100
BATTLE_STATUS_BAR_H = 8
BATTLE_STATUS_HP_LABEL_OFF = 130   # x-offsets below are from the status panel's own left edge, not the window's
BATTLE_STATUS_HP_BAR_OFF = 206
BATTLE_STATUS_MP_LABEL_OFF = 322
BATTLE_STATUS_MP_BAR_OFF = 398

BATTLE_PANEL_ALPHA = 175       # translucency shared by every battle-screen panel (log/command/status)
BATTLE_CMD_PANEL_COLOR = (12, 12, 18)
BATTLE_STATUS_PANEL_COLOR = (16, 46, 50)

# Melee movement (fix #19): the basic Attack and any physical-kind skill now
# run the actor's sprite over to its target instead of resolving in place --
# see _play_melee_action/_animate_run/_animate_melee_swing and the module
# docstring above. All first-pass, tune-by-feel numbers, same spirit as
# BATTLE_GROUND_RANK_GAP/BATTLE_GROUND_RANK_INSET_X above.
BATTLE_RUN_ANIM_FPS = 14        # run-cycle playback speed while sliding to/from a target (faster than the idle loop)
BATTLE_RUN_SPEED = 1400         # px/second the run-in/run-back slide covers, before the min/max clamp below
BATTLE_RUN_MIN_DURATION = 0.15  # a very short hop still gets at least this much visible run-cycle motion
BATTLE_RUN_MAX_DURATION = 0.55  # a full-width dash across the screen is capped here so it never feels sluggish
BATTLE_MELEE_ANIM_FPS = 26      # one-shot swing playback speed (faster than the idle/run loops -- a hit is a beat, not a cycle)
BATTLE_MELEE_ENGAGE_OFFSET = 120 # how far short of the target's own position the attacker stops (so sprites don't fully overlap)
# Roughly where in the 36-frame -Melee.png sheet the energy-burst/impact
# frame sits (eyeballed off the actual sheet Andrew supplied) -- the real,
# unwrapped BattleEngine.resolve_action() call (and therefore the damage
# number/flash it reveals) fires when playback reaches this frame, so the
# visual "hit" and the numeric one land close together without needing any
# engine-side hook.
BATTLE_MELEE_IMPACT_FRACTION = 0.44


class PygameUI:
    def __init__(self, skills_db, items_db, width=None, height=HEIGHT, debug=False, fullscreen=False):
        import pygame  # local import: keeps engine/ai import-able without pygame installed
        self.pygame = pygame
        pygame.init()
        self.debug = debug
        self.content_width = width or WIDTH   # battlefield/menu/log layout area
        self.width = self.content_width + (DEBUG_PANEL_W if debug else 0)  # full window
        self.height = height
        caption = "Battle Colosseum - Prototype (placeholder graphics)"
        if debug:
            caption += " [DEBUG]"
        pygame.display.set_caption(caption)
        # fullscreen=True scales this same (self.width, self.height) logical
        # surface up to fill the real display (pygame's SCALED flag) rather
        # than trying to make every screen's hardcoded pixel layout adapt to
        # an arbitrary monitor resolution -- everything drawn below still
        # thinks in the same 1280x800-ish coordinates either way. Windowed
        # mode (the default) is untouched from before -- no flags, so
        # nothing about its behavior changes for anyone not opting in.
        flags = (pygame.FULLSCREEN | pygame.SCALED) if fullscreen else 0
        self.screen = pygame.display.set_mode((self.width, self.height), flags)
        self.font = pygame.font.SysFont("consolas", 18)
        self.font_small = pygame.font.SysFont("consolas", 15)
        self.font_big = pygame.font.SysFont("consolas", 26, bold=True)
        self.clock = pygame.time.Clock()
        self.skills_db = skills_db
        self.items_db = items_db
        self.log_lines = []
        self.engine = None  # set via attach_engine
        self._thinking = None      # dict while an enemy decision is in flight, else None
        self.debug_history = []    # most-recent-last list of completed "done" decision records
        # Lightweight hit/heal feedback: since actions otherwise resolve instantly
        # with only the log/bars changing, we diff each combatant's HP between
        # frames (see _update_hit_flashes) and show a brief flash + floating
        # number on whoever changed. No engine changes needed for this -- it's
        # entirely derived from build_state() snapshots the UI already gets.
        self._prev_hp = {}   # combatant_id -> hp as of the last diff
        self._flashes = {}   # combatant_id -> {"delta": int, "start": perf_counter}
        self._portrait_cache = {}   # (name, (w, h)) -> loaded+scaled Surface, or None if no art found
        self._battler_raw_cache = {}   # (name, pose) -> list of 36 unscaled Surfaces sliced from that sheet, or None
        self._battler_cache = {}       # (name, height, facing, pose) -> list of scaled(+mirrored) Surfaces, or None
        self._battle_bg_cache = None   # None until first attempted; then a 1-tuple wrapping the Surface or None,
                                        # so a missing/failed background is cached as "don't retry" too (see
                                        # _get_battle_background -- the tuple wrapper distinguishes "not attempted
                                        # yet" from "attempted, found nothing")
        # Melee movement (fix #19): while a run-in/swing/run-back animation is
        # playing, this holds where+how the acting combatant should be drawn
        # instead of its normal column slot -- see _draw_battle_column and
        # _animate_run/_animate_melee_swing. None the rest of the time (the
        # overwhelming majority of frames), so every pre-existing draw path
        # is unaffected unless a melee action is actually mid-animation.
        self._mover = None

    def attach_engine(self, battle_engine) -> None:
        """Wires up the BattleEngine this UI is driving, and -- as of fix #19
        -- wraps its resolve_action so a melee action (the basic Attack, or
        any physical-kind skill) plays a run-in/swing/run-back animation
        around the engine's real, unwrapped resolution instead of resolving
        silently in place. See _resolve_action_with_movement and the module
        docstring. type(battle_engine).resolve_action (the plain, unbound
        class method) is captured fresh on every call, so wiring up a new
        BattleEngine each battle (as main.py's run_one_battle does) never
        double-wraps or accumulates old wrappers."""
        self.engine = battle_engine
        original_resolve_action = type(battle_engine).resolve_action

        def resolve_action_with_movement(action):
            self._resolve_action_with_movement(battle_engine, original_resolve_action, action)

        battle_engine.resolve_action = resolve_action_with_movement

    def reset_battle_view(self) -> None:
        """Clears everything the previous battle left behind (log lines, debug
        history, in-flight 'thinking', hit-flash state). Call this before
        starting a new BattleEngine on the same PygameUI/window -- without it,
        the log panel and debug history would still be showing the end of the
        *last* fight when the next one starts."""
        self.log_lines = []
        self.debug_history = []
        self._thinking = None
        self._prev_hp = {}
        self._flashes = {}
        self._mover = None

    # ------------------------------------------------------------------
    # Event pumping / lifecycle
    # ------------------------------------------------------------------
    def _pump(self) -> None:
        for event in self.pygame.event.get():
            if event.type == self.pygame.QUIT:
                self.pygame.quit()
                raise SystemExit(0)
            if event.type == self.pygame.KEYDOWN and event.key == self.pygame.K_ESCAPE:
                self.pygame.quit()
                raise SystemExit(0)

    def print_line(self, message: str) -> None:
        """Wire this in as BattleEngine(on_event=ui.print_line)."""
        self.log_lines.append(message)
        self.log_lines = self.log_lines[-9:]
        state = self.engine.build_state() if self.engine else None
        if state:
            self._update_hit_flashes(state)
            self._draw_frame(state)
        self._pump()
        self.pygame.time.delay(350)  # brief pause so the player can actually read each event

    def _update_hit_flashes(self, state: dict) -> None:
        """Diffs this snapshot's HP against the last one seen and starts a
        flash/floating-number for anyone whose HP moved. Called from
        print_line, since that's the only place a resolved action's HP change
        becomes visible -- on_ai_event's own redraws (while an enemy is still
        deciding) don't need this, HP can't have changed yet."""
        now = time.perf_counter()
        for c in state["party"] + state["enemies"]:
            prev = self._prev_hp.get(c["id"])
            if prev is not None and c["hp"] != prev:
                self._flashes[c["id"]] = {"delta": c["hp"] - prev, "start": now}
            self._prev_hp[c["id"]] = c["hp"]

    def _active_flash(self, combatant_id: str):
        """Returns (delta, age_fraction 0..1) if combatant_id has a live flash,
        else None. age_fraction is how far through HIT_FLASH_DURATION we are,
        for fading/rising the floating number -- and expires+removes the
        flash once it's played out."""
        flash = self._flashes.get(combatant_id)
        if not flash:
            return None
        age = time.perf_counter() - flash["start"]
        if age > HIT_FLASH_DURATION:
            del self._flashes[combatant_id]
            return None
        return flash["delta"], age / HIT_FLASH_DURATION

    # Wire this in as on_decision=ui.on_ai_event when building the enemy AI (see main.py).
    # Called at several points per enemy turn (see ai/enemy_ai.py's make_enemy_ai_fn docstring
    # for the exact record shapes): "start", repeated "tick"s while the Ollama call is in
    # flight, "thinking_chunk" as the model's THINKING sentence streams in, and "done". We
    # redraw + pump events on every call (not just in debug mode) -- that's what keeps the
    # window responsive/alive instead of looking frozen while an enemy is deciding, regardless
    # of whether --debug is on. The debug panel itself only shows when self.debug is True.
    def on_ai_event(self, record: dict) -> None:
        phase = record["phase"]
        if phase == "start":
            self._thinking = {"name": record["combatant_name"], "model": record.get("model", "?"),
                               "elapsed": 0.0, "text": ""}
        elif phase == "tick":
            if self._thinking:
                self._thinking["elapsed"] = record["elapsed_seconds"]
        elif phase == "thinking_chunk":
            if self._thinking:
                self._thinking["text"] = record.get("text_so_far", "")
        elif phase == "done":
            self._thinking = None
            self.debug_history.append(record)
            self.debug_history = self.debug_history[-8:]

        state = self.engine.build_state() if self.engine else None
        if state:
            self._draw_frame(state)
        self._pump()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def _hp_color(self, hp, max_hp):
        ratio = hp / max_hp if max_hp else 0
        if ratio > 0.5:
            return HP_GREEN
        if ratio > 0.2:
            return HP_YELLOW
        return HP_RED

    def _draw_bar(self, x, y, w, h, ratio, color, bg=(60, 60, 60)):
        pygame = self.pygame
        pygame.draw.rect(self.screen, bg, (x, y, w, h))
        pygame.draw.rect(self.screen, color, (x, y, max(0, int(w * max(0, min(1, ratio)))), h))
        pygame.draw.rect(self.screen, (10, 10, 10), (x, y, w, h), 1)

    def _draw_translucent_panel(self, x: int, y: int, w: int, h: int, color, alpha: int = BATTLE_PANEL_ALPHA,
                                 border_radius: int = 10) -> None:
        """Draws a rounded, alpha-blended panel background -- as of fix #18,
        every battle-screen panel (log/command/status) uses this instead of
        a fully-opaque rect, so the background art shows through, per
        Andrew's "make the ui backgrounds transparent" request. Uses a
        dedicated per-pixel-alpha Surface (SRCALPHA + an RGBA draw color)
        rather than Surface.set_alpha, since set_alpha fades the whole
        surface as one flat block and would lose the rounded corners'
        anti-aliasing against whatever's behind them."""
        pygame = self.pygame
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (*color, alpha), (0, 0, w, h), border_radius=border_radius)
        self.screen.blit(panel, (x, y))

    def _battler_sheet_candidates(self, name: str, pose: str = "Idle"):
        """Folder/file name variants tried for `name`'s `pose` sheet, same
        "exact name, then safe-filename transforms" spirit as
        _portrait_path_candidates -- each yields data/Battlers/<n>/<n>-<pose>.png.
        `pose` is one of "Idle" (standing loop, always expected to exist),
        "Run" (looping run cycle, fix #19) or "Melee" (one-shot swing, fix
        #19) -- see the module docstring."""
        seen = set()
        for base in (name, name.replace(" ", "_")):
            if base in seen:
                continue
            seen.add(base)
            yield os.path.join(BATTLER_DIR, base, f"{base}-{pose}.png")

    def _load_battler_sheet_raw(self, name: str, pose: str = "Idle"):
        """Loads and slices `name`'s BATTLER_FRAME_COLS x BATTLER_FRAME_ROWS
        `pose` sheet into a flat list of unscaled, unmirrored frame Surfaces
        (row-major order), cached per (name, pose) for the life of the
        window.

        Fallback order, when `name` has no `pose` sheet of its own (or it
        exists but fails to decode) -- narrowest/most-correct-looking first:
          1. `name`'s own Idle sheet, if `name` has one -- a battler with
             bespoke art but no Run/Melee sheet yet should keep looking like
             *itself* (just standing still) during a move, not suddenly
             swap to a different character's sprite.
          2. DEFAULT_BATTLER_NAME's `pose` sheet -- for a battler with no art
             of its own at all (the common case, before Andrew's drawn
             everyone), this reuses the placeholder's matching pose (e.g.
             its Run cycle) rather than jumping straight to its Idle pose.
          3. DEFAULT_BATTLER_NAME's Idle sheet -- reached automatically
             when even the default doesn't have this pose, since that
             recursive call goes through the same step-1-then-step-2 chain
             for DEFAULT_BATTLER_NAME itself.
        Each fallback reuses its target's already-cached frame list rather
        than re-decoding it. Returns None only if nothing at all could be
        loaded anywhere in the chain, so a missing/corrupt asset degrades to
        the plain rectangle fallback instead of crashing the battle
        screen."""
        key = (name, pose)
        if key in self._battler_raw_cache:
            return self._battler_raw_cache[key]
        pygame = self.pygame
        own_path = next((p for p in self._battler_sheet_candidates(name, pose) if os.path.isfile(p)), None)
        frames = None
        if own_path is not None:
            try:
                sheet = pygame.image.load(own_path)
                if hasattr(sheet, "convert_alpha"):
                    sheet = sheet.convert_alpha()
                sw, sh = sheet.get_width(), sheet.get_height()
                fw, fh = sw // BATTLER_FRAME_COLS, sh // BATTLER_FRAME_ROWS
                frames = []
                for row in range(BATTLER_FRAME_ROWS):
                    for col in range(BATTLER_FRAME_COLS):
                        frame = sheet.subsurface((col * fw, row * fh, fw, fh))
                        frames.append(frame.copy() if hasattr(frame, "copy") else frame)
            except Exception:
                # A present-but-corrupt/unsupported sheet must never crash the
                # battle screen -- same "bad content-data, not a bug" precedent
                # as a stale equipment id in a save file or a bad portrait file.
                frames = None

        if frames is None and pose != "Idle":
            # Step 1 above: only follow this if `name` actually HAS an Idle
            # sheet of its own -- checked directly (not via a recursive call,
            # which would also chase DEFAULT_BATTLER_NAME and jump straight
            # past step 2 for a battler with no art of its own at all).
            own_idle_path = next(
                (p for p in self._battler_sheet_candidates(name, "Idle") if os.path.isfile(p)), None)
            if own_idle_path is not None:
                frames = self._load_battler_sheet_raw(name, "Idle")

        if frames is None and name != DEFAULT_BATTLER_NAME:
            # Step 2 above.
            frames = self._load_battler_sheet_raw(DEFAULT_BATTLER_NAME, pose)

        self._battler_raw_cache[key] = frames
        return frames

    def _get_battler_frames(self, name: str, height: int, facing: str, pose: str = "Idle"):
        """Returns `name`'s `pose` frames scaled to `height` tall (width
        follows the sheet's own aspect ratio) and, when facing=="left",
        mirrored to face the opposite way from the sheet's native right-facing
        orientation -- or None if no sheet could be loaded at all (caller
        falls back to the plain rectangle). Cached per (name, height, facing,
        pose) so a sprite redrawn 30 times a second doesn't rescale/reflip
        every frame; only the frame *index* changes per draw (see
        _battler_frame_index)."""
        key = (name, height, facing, pose)
        if key in self._battler_cache:
            return self._battler_cache[key]
        raw = self._load_battler_sheet_raw(name, pose)
        if not raw:
            self._battler_cache[key] = None
            return None
        pygame = self.pygame
        fw, fh = raw[0].get_width(), raw[0].get_height()
        scaled_w = max(1, round(fw * height / fh)) if fh else height
        frames = [pygame.transform.smoothscale(f, (scaled_w, height)) for f in raw]
        if facing == "left":
            frames = [pygame.transform.flip(f, True, False) for f in frames]
        self._battler_cache[key] = frames
        return frames

    def _battler_frame_index(self, combatant_id: str, num_frames: int) -> int:
        """Which idle-loop frame to show right now, driven by wall-clock time
        (not per-battle state) so it keeps animating smoothly across the many
        separate _draw_frame calls a single turn makes (print_line, on_ai_event,
        the ~30fps _wait_for_choice poll loop). A per-combatant phase offset
        (from hashing their id) keeps a whole column of identical placeholder
        sprites from breathing in perfect unison."""
        if num_frames <= 0:
            return 0
        phase = hash(combatant_id) % num_frames
        return (int(time.time() * BATTLER_ANIM_FPS) + phase) % num_frames

    def _get_battle_background(self):
        """Returns the battle backdrop Surface (pre-scaled to fill the
        content area), or None if BATTLE_BG_PATH doesn't exist or fails to
        load -- _draw_frame just leaves the plain BG_COLOR fill showing in
        that case. Attempted once and cached either way (see the
        1-tuple-wrapper note on self._battle_bg_cache in __init__)."""
        if self._battle_bg_cache is not None:
            return self._battle_bg_cache[0]
        pygame = self.pygame
        surf = None
        if os.path.isfile(BATTLE_BG_PATH):
            try:
                loaded = pygame.image.load(BATTLE_BG_PATH)
                if hasattr(loaded, "convert_alpha"):
                    loaded = loaded.convert_alpha()
                surf = pygame.transform.smoothscale(loaded, (self.content_width, self.height))
            except Exception:
                surf = None
        self._battle_bg_cache = (surf,)
        return surf

    def _draw_battle_column(self, combatants, col_center_x: int, highlight_actor_id, facing: str):
        """Draws up to MAX_PARTY_SIZE-ish combatants standing on the arena
        floor near the bottom of the window, in up to two ranks of up to
        two each (see _column_layout for the actual placement math -- this
        method just walks it and draws). `col_center_x` is each side's
        horizontal anchor, the ground-layout analog of the old
        ex_start/px_start centering math (still used elsewhere) -- enemies
        and party each get their own left/right anchor rather than sharing
        a top/bottom row.

        As of fix #21, this no longer stacks a side's fighters in a tall
        single-file column (that was fix #17's staggered/shrink-to-fit
        scheme, replaced now that Andrew's new background art gives the
        battlefield an actual ground plane to stand fighters on) -- see
        _column_layout's own docstring for the current ranked-formation
        math.

        As of fix #19, the per-combatant layout math itself lives in
        _column_layout (so _home_position/_sprite_click_targets can compute
        the same positions without drawing anything); this method just walks
        that layout and, for whichever single combatant is currently mid-
        melee-animation (self._mover, see _mover_override), draws it at its
        override position/pose/frame instead of its normal ground slot --
        everyone else is drawn exactly as before.

        As of fix #22, draw order is back-to-front by y (ascending) rather
        than _column_layout's own yield order (front rank first) -- Andrew
        asked for "the bottom row to show over the top row," i.e. the front
        rank's sprites should visually overlap/occlude the back rank's where
        their boxes overlap on screen, the same painter's-algorithm z-order
        real depth would imply. Sorting here, rather than changing
        _column_layout's yield order, keeps _home_position/_sprite_click_
        targets (which don't care what order they see combatants in, only
        that every id maps to the right (x, y, sprite_h)) untouched."""
        entries = sorted(self._column_layout(combatants, col_center_x, facing), key=lambda e: e[2])
        for c, x, y, sprite_h in entries:
            mover = self._mover_override(c["id"])
            if mover is None:
                self._draw_combatant(c, x, y, highlight_actor_id == c["id"], facing, sprite_h=sprite_h)
            else:
                self._draw_combatant(
                    c, mover.get("x", x), mover.get("y", y), highlight_actor_id == c["id"],
                    mover.get("facing", facing), sprite_h=mover.get("sprite_h", sprite_h),
                    pose=mover.get("pose", "Idle"), frame_index=mover.get("frame_index"),
                )

    def _column_layout(self, combatants, col_center_x: int, facing: str):
        """The layout math _draw_battle_column uses to place each combatant,
        as its own generator (fix #19) so _home_position and
        _sprite_click_targets can compute the same (x, y, sprite_h) a
        combatant's sprite normally sits at without drawing anything.
        Yields (combatant_dict, x, y, sprite_h) tuples; x/y are the same
        center_x/y coordinates _draw_combatant's params expect (x IS a
        center, not a left edge).

        As of fix #24, this stands a side's fighters in a 2-column, 4-row
        staggered layout (one per row, up to 2 per column) on the arena
        floor. Each subsequent combatant's feet line sits
        BATTLE_GROUND_RANK_GAP higher up than the one below it. The
        columns are separated by BATTLE_GROUND_PAIR_GAP. Every fighter
        draws at the same fixed BATTLE_SPRITE_H no matter how many share
        a side."""
        if not combatants:
            return
        front_feet_y = self.height - BATTLE_GROUND_BOTTOM_MARGIN
        half_gap = BATTLE_GROUND_PAIR_GAP / 2
        for i, c in enumerate(combatants):
            row = i
            col = i % 2
            feet_y = front_feet_y - row * BATTLE_GROUND_RANK_GAP
            y = int(feet_y - BATTLE_SPRITE_H)
            if facing == "right":  # Enemies
                x = col_center_x - half_gap if col == 0 else col_center_x + half_gap
            else:  # Party (facing left)
                x = col_center_x + half_gap if col == 0 else col_center_x - half_gap
            yield c, x, y, BATTLE_SPRITE_H

    def _mover_override(self, combatant_id: str):
        """Returns self._mover if it's currently animating combatant_id (see
        _animate_run/_animate_melee_swing), else None. This tiny shared
        check is what keeps _draw_battle_column (what to actually draw) and
        _sprite_click_targets (what rect a click on that sprite should hit)
        from ever disagreeing about where a mid-animation sprite currently
        is."""
        if self._mover and self._mover.get("id") == combatant_id:
            return self._mover
        return None

    def _home_position(self, state: dict, combatant_id: str):
        """Where combatant_id's sprite normally sits in its column -- i.e.
        exactly what _column_layout would place it at, ignoring any
        in-progress melee animation. Used by _resolve_action_with_movement
        to compute run-in/run-back endpoints. Returns (x, y, sprite_h), or
        None if combatant_id isn't in either column of `state` (shouldn't
        normally happen for a fresh build_state() snapshot)."""
        for combatants, col_center_x, facing in (
            (state["enemies"], BATTLE_ENEMY_COL_X, "right"),
            (state["party"], self.content_width - BATTLE_ENEMY_COL_X, "left"),
        ):
            for c, x, y, sprite_h in self._column_layout(combatants, col_center_x, facing):
                if c["id"] == combatant_id:
                    return x, y, sprite_h
        return None

    def _find_combatant_dict(self, state: dict, combatant_id: str):
        """Looks up combatant_id's public-dict snapshot (name/hp/alive/...)
        in `state`, or None if it isn't there. Small helper for the fix #19
        animation code, which is handed a live engine.Combatant (for id/
        is_enemy/name) but needs the *dict* form _draw_combatant expects."""
        for c in state["party"] + state["enemies"]:
            if c["id"] == combatant_id:
                return c
        return None

    def _combatant_rect(self, c: dict, center_x: int, y: int, sprite_h: int, facing: str, pose: str = "Idle"):
        """The Rect _draw_combatant would blit `c`'s sprite (or its colored-
        rectangle fallback) into at (center_x, y) -- computed independently
        of _draw_combatant itself (rather than having _draw_combatant return
        it) so the existing tests that monkeypatch _draw_combatant to return
        None keep working unchanged. Used by _sprite_click_targets to make a
        combatant's on-screen sprite clickable as a target (fix #19)."""
        frames = self._get_battler_frames(c["name"], sprite_h, facing, pose)
        if frames:
            box_w, box_h = frames[0].get_width(), frames[0].get_height()
        else:
            box_w, box_h = 100, sprite_h
        x = center_x - box_w // 2
        return self.pygame.Rect(x, y, box_w, box_h)

    def _sprite_click_targets(self, state: dict) -> dict:
        """Maps combatant id -> the Rect its sprite currently occupies on
        screen (accounting for self._mover, same as _draw_battle_column), so
        _draw_frame can offer a combatant's own sprite as an extra click
        target alongside the text button menu (fix #19) -- see the module
        docstring."""
        targets = {}
        for combatants, col_center_x, facing in (
            (state["enemies"], BATTLE_ENEMY_COL_X, "right"),
            (state["party"], self.content_width - BATTLE_ENEMY_COL_X, "left"),
        ):
            for c, x, y, sprite_h in self._column_layout(combatants, col_center_x, facing):
                mover = self._mover_override(c["id"])
                if mover is None:
                    targets[c["id"]] = self._combatant_rect(c, x, y, sprite_h, facing)
                else:
                    targets[c["id"]] = self._combatant_rect(
                        c, mover.get("x", x), mover.get("y", y), mover.get("sprite_h", sprite_h),
                        mover.get("facing", facing), mover.get("pose", "Idle"),
                    )
        return targets

    def _draw_combatant(self, c: dict, center_x: int, y: int, highlight: bool, facing: str = "right",
                         sprite_h: int = BATTLE_SPRITE_H, pose: str = "Idle", frame_index=None):
        """Draws just the combatant's sprite (or the colored-rectangle
        fallback) and a floating hit/heal number. As of fix #18, per
        Andrew's "removing the boxes from the sprites" request, this no
        longer draws a name/HP/MP text block, a status-effect label, a KO
        tag, or a highlight border directly on/around the sprite -- a
        party member's name/HP/MP moved to _draw_party_status_panel
        instead (matching his reference screenshot), and enemies simply
        don't get any of that on the battlefield at all, the same as the
        reference. Target selection is still driven by the text button
        menu by name (see get_party_action/_choose_target) -- as of fix
        #19 a combatant's own sprite is ALSO clickable as that same target
        (see _sprite_click_targets), but that's handled entirely outside
        this method, by _draw_frame appending extra entries to its returned
        button_rects. `highlight` is accepted (kept for call-site
        stability with _draw_battle_column) but intentionally unused now --
        whose turn it is is shown by the highlighted row in the party
        status panel and by the menu title text instead of a box on the
        sprite itself. `pose`/`frame_index` are fix #19 additions: `pose`
        selects which sheet to draw from ("Idle" as always, or "Run"/"Melee"
        while self._mover has this combatant mid-animation -- see
        _get_battler_frames's fallback chain for what happens when a given
        battler has no art for that pose yet); `frame_index`, when given,
        overrides the normal wall-clock-driven idle loop (_battler_frame_index)
        with a caller-controlled frame -- used by _animate_run/
        _animate_melee_swing to step through a run cycle or one-shot swing
        deliberately rather than just looping forever."""
        pygame = self.pygame
        frames = self._get_battler_frames(c["name"], sprite_h, facing, pose)
        if frames:
            idx = frame_index if frame_index is not None else self._battler_frame_index(c["id"], len(frames))
            idx = max(0, min(int(idx), len(frames) - 1))
            frame = frames[idx]
            box_w, box_h = frame.get_width(), frame.get_height()
            x = center_x - box_w // 2
            frame.set_alpha(255 if c["alive"] else 110)  # dim a KO'd combatant instead of hiding them
            self.screen.blit(frame, (x, y))
        else:
            # No sheet could be loaded at all (missing/corrupt, and even the
            # DEFAULT_BATTLER_NAME fallback failed) -- the original colored
            # placeholder rectangle, so the battle screen never goes blank.
            box_w, box_h = 100, sprite_h
            x = center_x - box_w // 2
            color = tuple(c.get("sprite_color", (150, 150, 150)))
            if not c["alive"]:
                color = (55, 55, 60)
            pygame.draw.rect(self.screen, color, (x, y, box_w, box_h), border_radius=8)

        flash = self._active_flash(c["id"])
        if flash:
            delta, t = flash  # t: 0 (just happened) .. 1 (about to disappear)
            # No more edge-color box around the sprite on a hit (that was
            # one of the "boxes" being removed) -- just the floating
            # rising/fading +/-N number, which still gives per-hit
            # feedback even without an HP bar next to the sprite anymore.
            is_damage = delta < 0
            number_color = (255, 110, 110) if is_damage else (140, 235, 150)
            number_txt = f"-{abs(delta)}" if is_damage else f"+{delta}"
            num_surf = self.font.render(number_txt, True, number_color)
            rise = int(t * 22)
            self.screen.blit(num_surf, (x + box_w // 2 - num_surf.get_width() // 2, y - 34 - rise))

    def _draw_party_status_panel(self, party: list, highlight_actor_id, x: int, y: int, w: int) -> None:
        """Renders the party's Name/HP/MP readout as its own panel, bottom
        of the screen -- what fix #18 moved this into out of
        _draw_combatant's old per-sprite text, matching the reference
        screenshot Andrew sent (a status strip separate from the sprites,
        not floating labels on top of them). Enemies don't get one of
        these: the reference doesn't show enemy stats either, and (per
        _draw_combatant's docstring) targeting has never depended on
        seeing them on the battlefield, only on the text button menu's
        target list. The currently-acting party member's row is
        highlighted (bright name text) instead of the old box-on-the-
        sprite -- that's the replacement "whose turn is it" indicator."""
        if not party:
            return
        panel_h = BATTLE_STATUS_PANEL_PAD * 2 + len(party) * BATTLE_STATUS_ROW_H
        self._draw_translucent_panel(x, y, w, panel_h, BATTLE_STATUS_PANEL_COLOR)
        for i, c in enumerate(party):
            row_y = y + BATTLE_STATUS_PANEL_PAD + i * BATTLE_STATUS_ROW_H
            is_current = c["id"] == highlight_actor_id
            name_color = HIGHLIGHT if is_current else (TEXT_COLOR if c["alive"] else DIM_COLOR)
            name_txt = c["name"] if c["alive"] else f"{c['name']} (KO)"
            name_surf = self.font_small.render(name_txt, True, name_color)
            self.screen.blit(name_surf, (x + 14, row_y + 8))

            hp_x = x + BATTLE_STATUS_HP_LABEL_OFF
            self.screen.blit(self.font_small.render("HP", True, DIM_COLOR), (hp_x, row_y + 8))
            self.screen.blit(self.font_small.render(f"{c['hp']}/{c['max_hp']}", True, TEXT_COLOR),
                              (hp_x + 26, row_y + 8))
            self._draw_bar(x + BATTLE_STATUS_HP_BAR_OFF, row_y + 12, BATTLE_STATUS_BAR_W, BATTLE_STATUS_BAR_H,
                            c["hp"] / c["max_hp"] if c["max_hp"] else 0, self._hp_color(c["hp"], c["max_hp"]))

            if c.get("max_mp", 0) > 0:
                mp_x = x + BATTLE_STATUS_MP_LABEL_OFF
                self.screen.blit(self.font_small.render("MP", True, DIM_COLOR), (mp_x, row_y + 8))
                self.screen.blit(self.font_small.render(f"{c['mp']}/{c['max_mp']}", True, TEXT_COLOR),
                                  (mp_x + 26, row_y + 8))
                self._draw_bar(x + BATTLE_STATUS_MP_BAR_OFF, row_y + 12, BATTLE_STATUS_BAR_W, BATTLE_STATUS_BAR_H,
                                c["mp"] / c["max_mp"] if c["max_mp"] else 0, MP_BLUE)

            if c["statuses"]:
                status_surf = self.font_small.render(",".join(c["statuses"]), True, (230, 180, 90))
                self.screen.blit(status_surf, (x + w - status_surf.get_width() - 12, row_y + 8))

    def _draw_frame(self, state: dict, highlight_actor_id=None, buttons=None, menu_title=None):
        pygame = self.pygame
        self.screen.fill(BG_COLOR)
        bg = self._get_battle_background()
        if bg is not None:
            self.screen.blit(bg, (0, 0))

        # Classic side-view duel: enemies in a column on the left facing
        # right (the sheet's native orientation), party in a column on the
        # right facing left (the same frames mirrored) -- replaces the old
        # top-enemies/bottom-party stacked rows. See _draw_battle_column.
        self._draw_battle_column(state["enemies"], BATTLE_ENEMY_COL_X, highlight_actor_id, facing="right")
        self._draw_battle_column(state["party"], self.content_width - BATTLE_ENEMY_COL_X, highlight_actor_id,
                                  facing="left")

        # Round counter
        round_txt = self.font.render(f"Round {state.get('round', 0)}", True, DIM_COLOR)
        self.screen.blit(round_txt, (12, 10))

        # Log panel: fix #17 moved this here, just under the round counter,
        # after a full 3-4-wide column put the bottom sprite right behind
        # where this used to sit at the bottom of the screen (see
        # BATTLE_LOG_Y/_H above). As of fix #18 it's translucent (like every
        # other battle panel) instead of a flat opaque fill.
        self._draw_translucent_panel(10, BATTLE_LOG_Y, self.content_width - 20, BATTLE_LOG_H, PANEL_COLOR)
        for i, line in enumerate(self.log_lines[-5:]):
            surf = self.font_small.render(line[:110], True, TEXT_COLOR)
            self.screen.blit(surf, (18, BATTLE_LOG_Y + 6 + i * 17))

        # Party status panel (fix #18): always drawn, regardless of whether
        # a menu is up, since the player should be able to see the party's
        # HP/MP at any point in the turn, not just while choosing an
        # action -- e.g. while an enemy's turn is resolving. See
        # _draw_party_status_panel's docstring for why enemies don't get
        # one. Bottom-anchored off self.height, same reasoning as the
        # command panel below: it uses the room a taller window gives it
        # instead of staying pinned to a fixed pixel offset.
        status_x = BATTLE_CMD_PANEL_X + BATTLE_CMD_PANEL_W + BATTLE_STATUS_PANEL_GAP
        status_w = min(BATTLE_STATUS_PANEL_W, self.content_width - status_x - BATTLE_BOTTOM_MARGIN)
        status_h = BATTLE_STATUS_PANEL_PAD * 2 + len(state["party"]) * BATTLE_STATUS_ROW_H
        status_y = self.height - BATTLE_BOTTOM_MARGIN - status_h
        self._draw_party_status_panel(state["party"], highlight_actor_id, status_x, status_y, status_w)

        # Command panel (fix #18): a single-column translucent box, bottom-
        # left, sized to however many buttons this particular menu has (the
        # main action menu and every submenu -- skill/item/target -- top
        # out at 5, so one column always fits without needing per-menu-type
        # layout branching). Replaces the old 4-column opaque button grid.
        # Bottom-anchored the same way the old grid was, off self.height,
        # so a taller window still uses the extra room rather than leaving
        # a dead gap.
        button_rects = []
        if buttons:
            n = len(buttons)
            cmd_h = n * BATTLE_CMD_BTN_H + max(0, n - 1) * BATTLE_CMD_BTN_GAP + 2 * BATTLE_CMD_PANEL_PAD
            cmd_x = BATTLE_CMD_PANEL_X
            cmd_y = self.height - BATTLE_BOTTOM_MARGIN - cmd_h
            self._draw_translucent_panel(cmd_x, cmd_y, BATTLE_CMD_PANEL_W, cmd_h, BATTLE_CMD_PANEL_COLOR)
            if menu_title:
                title_surf = self.font_small.render(menu_title, True, DIM_COLOR)
                self.screen.blit(title_surf, (cmd_x, cmd_y - 20))
            mouse_pos = pygame.mouse.get_pos()
            bx = cmd_x + BATTLE_CMD_PANEL_PAD
            by0 = cmd_y + BATTLE_CMD_PANEL_PAD
            for i, (label, _value) in enumerate(buttons):
                rect = pygame.Rect(bx, by0 + i * (BATTLE_CMD_BTN_H + BATTLE_CMD_BTN_GAP),
                                    BATTLE_CMD_BTN_W, BATTLE_CMD_BTN_H)
                hovered = rect.collidepoint(mouse_pos)
                pygame.draw.rect(self.screen, BUTTON_HOVER if hovered else BUTTON_COLOR, rect, border_radius=6)
                pygame.draw.rect(self.screen, (10, 10, 10), rect, 1, border_radius=6)
                label_surf = self.font_small.render(label[:34], True, TEXT_COLOR)
                self.screen.blit(label_surf, (rect.x + 8, rect.y + (BATTLE_CMD_BTN_H - label_surf.get_height()) // 2))
                button_rects.append((rect, _value))

            # Sprite-click targeting (fix #19): any button whose value is a
            # combatant dict -- i.e. a target-selection button, see
            # get_party_action/_choose_target, which hand back entries from
            # state["party"]/state["enemies"] themselves -- is also
            # selectable by clicking that combatant's own on-screen sprite,
            # exactly equivalent to clicking its row above. _wait_for_choice
            # already searches button_rects via rect.collidepoint, so no
            # targeting logic anywhere else needs to change at all.
            sprite_targets = self._sprite_click_targets(state)
            for _label, _value in buttons:
                if isinstance(_value, dict) and "hp" in _value and "alive" in _value:
                    sprite_rect = sprite_targets.get(_value.get("id"))
                    if sprite_rect is not None:
                        button_rects.append((sprite_rect, _value))

        if self.debug:
            self._draw_debug_panel()

        pygame.display.flip()
        return button_rects

    # ------------------------------------------------------------------
    # Melee movement (fix #19) -- see the module docstring and
    # attach_engine's docstring for how this gets wired in.
    # ------------------------------------------------------------------
    def _is_melee_action(self, engine, action) -> bool:
        """The basic Attack is always melee; a Skill is melee only if it's a
        physical-kind skill (skills_db[skill_id].kind == "physical" -- Power
        Strike, Cleave, Piercing Shot, Poison Dart, Crushing Blow, as of
        this writing). Everything else (magical/heal/status skills, item,
        defend, flee) is not, and keeps resolving instantly in place."""
        if action.type == ActionType.ATTACK:
            return True
        if action.type == ActionType.SKILL and action.skill_id:
            skill = engine.skills_db.get(action.skill_id)
            return bool(skill and skill.kind == "physical")
        return False

    def _melee_target_for(self, engine, actor, action):
        """Best-effort guess at which combatant a melee action is about to
        hit, purely so _resolve_action_with_movement knows where to run the
        attacker to -- the engine's own target resolution (inside the real,
        unwrapped resolve_action call fired mid-swing, see
        _animate_melee_swing) is what actually decides the target and is
        free to land on someone else in an edge case (e.g. the requested
        target died to something else first); if it does, the swing still
        lands, just not perfectly lined up on whoever the engine ultimately
        picks. Returns a live Combatant, or None if there's no living
        opponent to run to at all (caller falls back to resolving in
        place)."""
        opposing = [c for c in engine.opposing_side(actor) if c.alive]
        if not opposing:
            return None
        for target_id in (action.target_ids or []):
            match = next((c for c in opposing if c.id == target_id), None)
            if match:
                return match
        return opposing[0]

    def _animate_run(self, state: dict, mover_id: str, from_xy, to_xy, facing: str, sprite_h: int) -> None:
        """Slides mover_id's sprite from from_xy to to_xy, looping its Run-
        pose frames (falling back to Idle if this battler has no Run sheet
        of its own -- see _load_battler_sheet_raw's fallback chain) while it
        moves. Duration is distance-scaled (BATTLE_RUN_SPEED), clamped to
        [BATTLE_RUN_MIN_DURATION, BATTLE_RUN_MAX_DURATION] so a short hop
        still reads as motion and a long dash never feels sluggish. Sets
        self._mover for the duration so _draw_battle_column/
        _sprite_click_targets draw/hit-test mover_id at its current slide
        position instead of its normal column slot (see _mover_override) --
        the caller is responsible for clearing self._mover once the whole
        run/swing/run-back sequence is over. `state` is only redrawn as-is
        here (nothing else in it changes mid-slide -- no engine call happens
        until _animate_melee_swing)."""
        combatant = self._find_combatant_dict(state, mover_id)
        if combatant is None:
            return
        fx, fy = from_xy
        tx, ty = to_xy
        dist = ((tx - fx) ** 2 + (ty - fy) ** 2) ** 0.5
        duration = min(BATTLE_RUN_MAX_DURATION, max(BATTLE_RUN_MIN_DURATION, dist / BATTLE_RUN_SPEED))
        run_frames = self._get_battler_frames(combatant["name"], sprite_h, facing, "Run")
        num_frames = len(run_frames) if run_frames else 0
        start = time.time()
        while True:
            elapsed = time.time() - start
            t = min(1.0, elapsed / duration) if duration > 0 else 1.0
            x = int(fx + (tx - fx) * t)
            y = int(fy + (ty - fy) * t)
            frame_index = int(elapsed * BATTLE_RUN_ANIM_FPS) % num_frames if num_frames else None
            self._mover = {"id": mover_id, "x": x, "y": y, "sprite_h": sprite_h, "facing": facing,
                            "pose": "Run", "frame_index": frame_index}
            self._draw_frame(state)
            self._pump()
            if t >= 1.0:
                break
            self.clock.tick(30)

    def _animate_melee_swing(self, state: dict, engine, action, actor, x: int, y: int, facing: str,
                              sprite_h: int, original_resolve) -> dict:
        """Plays the one-shot Melee swing in place at (x, y) -- falling back
        to the Idle pose if this battler has no Melee sheet of its own, same
        fallback chain as Run -- firing the engine's real, unwrapped
        resolve_action right when playback reaches
        BATTLE_MELEE_IMPACT_FRACTION of the way through (roughly the
        sheet's own energy-burst frame, see that constant's comment above)
        so the damage number/flash the engine's log line triggers appears
        close to the swing's visual "hit" instead of at the very start or
        end of the animation. Always fires original_resolve exactly once,
        even if the sheet is too short/missing to naturally reach the
        impact frame (the fallback fires it right before the swing's final
        frame instead) -- a melee action must never silently fail to
        resolve just because of a missing/odd asset.

        Returns a freshly-rebuilt state snapshot (post-hit HP/KO), since the
        caller's own `state` goes stale the instant original_resolve runs --
        the party status panel and KO dimming depend on the actual dict
        passed to _draw_frame, unlike the flash/floating number overlay
        (which always reads self.engine.build_state() itself fresh, see
        print_line/_update_hit_flashes) -- so those two effects stay in sync
        without this method needing to know anything about them."""
        combatant = self._find_combatant_dict(state, actor.id)
        name = combatant["name"] if combatant else actor.name
        swing_frames = self._get_battler_frames(name, sprite_h, facing, "Melee")
        num_frames = len(swing_frames) if swing_frames else BATTLER_FRAME_COLS * BATTLER_FRAME_ROWS
        impact_index = min(num_frames - 1, round(num_frames * BATTLE_MELEE_IMPACT_FRACTION))
        duration = max(0.05, num_frames / BATTLE_MELEE_ANIM_FPS)
        start = time.time()
        fired = False
        current_state = state
        while True:
            elapsed = time.time() - start
            frame_index = min(num_frames - 1, int(elapsed * BATTLE_MELEE_ANIM_FPS)) if num_frames else 0
            self._mover = {"id": actor.id, "x": x, "y": y, "sprite_h": sprite_h, "facing": facing,
                            "pose": "Melee", "frame_index": frame_index}
            if not fired and (frame_index >= impact_index or elapsed >= duration):
                original_resolve(engine, action)
                fired = True
                current_state = engine.build_state()
            self._draw_frame(current_state)
            self._pump()
            if elapsed >= duration:
                break
            self.clock.tick(30)
        return current_state

    def _resolve_action_with_movement(self, engine, original_resolve, action) -> None:
        """The attach_engine-installed replacement for
        BattleEngine.resolve_action. A melee action (basic Attack, or any
        physical-kind skill -- see _is_melee_action) plays a run-in/swing/
        run-back animation around the engine's real resolution instead of
        resolving silently in place; everything else just calls straight
        through, unchanged from before fix #19. Also falls straight through
        for a melee action if the actor is already dead (shouldn't normally
        happen -- resolve_action itself no-ops on a dead actor too, see
        engine/battle.py) or there's no living opponent/home position to
        animate against, so a melee action never crashes the battle just
        because the animation couldn't be set up."""
        actor = engine.get_by_id(action.actor_id)
        if actor is None or not actor.alive or not self._is_melee_action(engine, action):
            original_resolve(engine, action)
            return

        target = self._melee_target_for(engine, actor, action)
        if target is None:
            original_resolve(engine, action)
            return

        state = engine.build_state()
        facing = "right" if actor.is_enemy else "left"
        home = self._home_position(state, actor.id)
        target_home = self._home_position(state, target.id)
        if home is None or target_home is None:
            original_resolve(engine, action)
            return
        home_x, home_y, sprite_h = home
        target_x, target_y, _ = target_home

        # Stop short of the target's own position (rather than running
        # fully on top of it) so the two sprites don't overlap -- which
        # side to stop short on depends on which side of the target the
        # attacker is coming from.
        if home_x < target_x:
            engage_x = target_x - BATTLE_MELEE_ENGAGE_OFFSET
        else:
            engage_x = target_x + BATTLE_MELEE_ENGAGE_OFFSET
        engage_y = target_y

        try:
            self._animate_run(state, actor.id, (home_x, home_y), (engage_x, engage_y), facing, sprite_h)
            state = self._animate_melee_swing(state, engine, action, actor, engage_x, engage_y, facing,
                                               sprite_h, original_resolve)
            self._animate_run(state, actor.id, (engage_x, engage_y), (home_x, home_y), facing, sprite_h)
        finally:
            # Always clear, even if a redraw/animation step above raised
            # (e.g. SystemExit from _pump on window-close) -- otherwise a
            # stray self._mover would keep drawing this combatant at its
            # last animated position forever instead of its normal slot.
            self._mover = None

    def _wrap(self, text: str, width_chars: int):
        import textwrap
        return textwrap.wrap(text, width=width_chars) or [""]

    def _debug_target_name(self, target_id):
        if not target_id:
            return None
        if self.engine:
            combatant = self.engine.get_by_id(target_id)
            if combatant:
                return combatant.name
        return target_id

    def _draw_debug_panel(self) -> None:
        """Renders the 'what's the model thinking, how long is it taking' panel
        along the right edge of the window (only drawn when debug=True)."""
        pygame = self.pygame
        panel_x = self.content_width
        panel_w = self.width - self.content_width
        pygame.draw.rect(self.screen, DEBUG_PANEL_COLOR, (panel_x, 0, panel_w, self.height))
        pygame.draw.rect(self.screen, (10, 10, 10), (panel_x, 0, panel_w, self.height), 1)

        pad = 14
        x = panel_x + pad
        y = 14
        wrap_chars = max(20, (panel_w - 2 * pad) // 8)
        header = self.font.render("AI DEBUG", True, TEXT_COLOR)
        self.screen.blit(header, (x, y))
        y += 30

        if self._thinking:
            think_txt = self.font_small.render(f"{self._thinking['name']} is thinking...", True, THINKING_COLOR)
            self.screen.blit(think_txt, (x, y))
            y += 18
            timer_txt = self.font.render(f"{self._thinking['elapsed']:.1f}s", True, THINKING_COLOR)
            self.screen.blit(timer_txt, (x, y))
            model_txt = self.font_small.render(f"({self._thinking['model']})", True, DIM_COLOR)
            self.screen.blit(model_txt, (x + timer_txt.get_width() + 8, y + 4))
            y += 28
            # The model's THINKING sentence, live, growing as it streams in.
            live_text = self._thinking.get("text", "")
            if live_text:
                for line in self._wrap(live_text, wrap_chars)[:6]:
                    surf = self.font_small.render(line, True, TEXT_COLOR)
                    self.screen.blit(surf, (x, y))
                    y += 16
            else:
                # A long wait here with the timer still climbing (not frozen) usually
                # means Ollama is still loading the model into memory rather than
                # generating -- large models can take a while to load, especially if
                # keep_alive expired since the last call. main.py's startup warm-up
                # avoids this for the first turn of a battle; this just keeps it from
                # reading as a hang if it happens again later.
                elapsed = self._thinking.get("elapsed", 0.0)
                if elapsed < 8:
                    wait_lines = ["(waiting for first token...)"]
                else:
                    wait_lines = self._wrap(
                        "(still waiting -- this usually means the model is still "
                        "loading into memory, not stuck; large models can take a "
                        "while, especially if it had been idle)", wrap_chars)
                for line in wait_lines[:5]:
                    surf = self.font_small.render(line, True, DIM_COLOR)
                    self.screen.blit(surf, (x, y))
                    y += 16
            y += 8
        else:
            idle_txt = self.font_small.render("(idle)", True, DIM_COLOR)
            self.screen.blit(idle_txt, (x, y))
            y += 24

        pygame.draw.rect(self.screen, (60, 60, 76), (x, y, self.width - pad - x, 1))
        y += 10
        history_label = self.font_small.render("Recent decisions:", True, DIM_COLOR)
        self.screen.blit(history_label, (x, y))
        y += 20

        for record in reversed(self.debug_history):
            if y > self.height - 20:
                break
            elapsed = record.get("elapsed_seconds", 0.0)
            name = record.get("combatant_name", "?")
            if record.get("used_fallback") or record.get("error"):
                color = FALLBACK_COLOR
                headline = f"{name}: fallback ({elapsed:.2f}s)"
            else:
                color = LLM_COLOR
                bits = [record.get("action_type") or "?"]
                if record.get("skill_id"):
                    bits.append(record["skill_id"])
                target_name = self._debug_target_name(record.get("target_id"))
                if target_name:
                    bits.append(f"-> {target_name}")
                headline = f"{name}: {' '.join(bits)} ({elapsed:.2f}s)"

            for line in self._wrap(headline, wrap_chars):
                if y > self.height - 20:
                    break
                surf = self.font_small.render(line, True, color)
                self.screen.blit(surf, (x, y))
                y += 16

            reason = record.get("reason")
            if reason:
                for line in self._wrap(f'"{reason}"', wrap_chars):
                    if y > self.height - 20:
                        break
                    surf = self.font_small.render(line, True, DIM_COLOR)
                    self.screen.blit(surf, (x, y))
                    y += 14
            elif record.get("error"):
                for line in self._wrap(record["error"], wrap_chars):
                    if y > self.height - 20:
                        break
                    surf = self.font_small.render(line, True, DIM_COLOR)
                    self.screen.blit(surf, (x, y))
                    y += 14
            y += 10

    # ------------------------------------------------------------------
    # Meta-game screens: title, character creation, Colosseum hub.
    #
    # These don't touch BattleEngine/build_state at all (unlike everything
    # above, which is written in terms of a battle's state dict) -- they're
    # plain menu screens over PlayerState/class-archetype/equipment data, so
    # each one draws its own frame from scratch rather than reusing
    # _draw_frame. They share the same window/clock/fonts as battle, so the
    # whole new-game -> create character -> Colosseum -> battle -> Colosseum
    # loop runs in one persistent PygameUI instance (see main.py).
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Hero portraits (see show_heroes) -- real art from data/portraits/ when
    # Andrew's dropped a matching file in, a drawn placeholder otherwise.
    # ------------------------------------------------------------------
    @staticmethod
    def _portrait_path_candidates(name: str):
        """Filename variants tried for `name`'s portrait, cheapest/most-exact
        first: the name as-is, then common "safe filename" transforms
        (lowercased, spaces -> underscores) in case Andrew's saving them a
        little differently than the in-game name is capitalized/spaced --
        each tried against every extension in PORTRAIT_EXTENSIONS."""
        seen = set()
        for base in (name, name.lower(), name.replace(" ", "_"), name.replace(" ", "_").lower()):
            if base in seen:
                continue
            seen.add(base)
            for ext in PORTRAIT_EXTENSIONS:
                yield base + ext

    def _get_portrait(self, name: str, size):
        """Returns a Surface for `name`'s portrait pre-scaled to `size`
        (width, height), or None if no portrait file exists for them --
        callers fall back to _draw_portrait_placeholder in that case. Loaded
        images are cached per (name, size) for the life of the window, so a
        card re-drawn every frame doesn't re-hit disk every frame; a missing
        or unreadable file is cached as None too, so a typo'd/corrupt image
        doesn't get retried 30 times a second either."""
        key = (name, size)
        if key in self._portrait_cache:
            return self._portrait_cache[key]
        pygame = self.pygame
        surf = None
        for filename in self._portrait_path_candidates(name):
            path = os.path.join(PORTRAIT_DIR, filename)
            if not os.path.isfile(path):
                continue
            try:
                loaded = pygame.image.load(path)
                if hasattr(loaded, "convert_alpha"):
                    loaded = loaded.convert_alpha()
                surf = pygame.transform.smoothscale(loaded, size)
            except Exception:
                # A present-but-corrupt/unsupported file must never crash the
                # Heroes page -- fall back to the placeholder like a missing
                # file would, same "never let bad content-data crash the
                # game" precedent as a stale equipment id in a save file.
                surf = None
            break
        self._portrait_cache[key] = surf
        return surf

    def _draw_portrait_placeholder(self, rect, class_color) -> None:
        """A simple drawn silhouette (dimmed class color background, a
        lighter head+shoulders shape) for a character with no portrait file
        yet -- so an empty data/portraits/ folder still looks intentional
        rather than like a rendering bug."""
        pygame = self.pygame

        def _shade(c, factor, boost=0):
            return tuple(max(0, min(255, int(v * factor) + boost)) for v in c)

        pygame.draw.rect(self.screen, _shade(class_color, 0.35), rect, border_radius=10)
        cx = rect.x + rect.w // 2
        head_r = max(6, rect.w // 6)
        head_cy = rect.y + rect.h // 3
        silhouette = _shade(class_color, 0.7, boost=35)
        pygame.draw.circle(self.screen, silhouette, (cx, head_cy), head_r)
        body_top = head_cy + head_r - 2
        body_rect = pygame.Rect(cx - rect.w // 3, body_top, (rect.w * 2) // 3, max(0, (rect.y + rect.h) - body_top))
        pygame.draw.rect(self.screen, silhouette, body_rect, border_radius=max(4, rect.w // 7))
        pygame.draw.rect(self.screen, (10, 10, 10), rect, 1, border_radius=10)

    def _draw_star_pips(self, x, y, stars, max_stars, color, radius=4, gap=4) -> None:
        """Small filled/hollow dot row for a hero card's star count -- a
        compact alternative to hero_rarity.star_display's `[***..]` text,
        used where a card banner doesn't have room for the bracketed form."""
        pygame = self.pygame
        for i in range(max_stars):
            cx = x + i * (radius * 2 + gap) + radius
            if i < stars:
                pygame.draw.circle(self.screen, color, (cx, y), radius)
            else:
                pygame.draw.circle(self.screen, color, (cx, y), radius, 1)

    def _draw_hero_card(self, c, x, y, w, h, banner_h, selected: bool, hovered: bool):
        """Draws one hero card -- portrait (or placeholder silhouette) over a
        rarity-tinted banner with name/level/star pips, bordered by rarity
        color (white/HIGHLIGHT when selected) -- at an arbitrary position and
        size, and returns its outer Rect for the caller to use as a click
        target. Extracted in fix #20 so show_heroes' own card grid and
        show_party_select's party-strip/roster-grid cards render from one
        code path instead of two copies that could silently drift apart;
        the only thing that varies between callers is size/banner height
        and whether a card counts as "selected" (a hero in the current
        battle party vs. the hero whose detail panel is open), so those are
        the only things this takes as parameters rather than reading state
        itself."""
        pygame = self.pygame
        from data.hero_rarity import HERO_RARITY_COLOR, MAX_STARS

        rect = pygame.Rect(x, y, w, h)
        rarity_color = HERO_RARITY_COLOR.get(c.rarity, TEXT_COLOR)

        portrait_h = h - banner_h
        portrait_rect = pygame.Rect(x, y, w, portrait_h)
        portrait = self._get_portrait(c.name, (w, portrait_h))
        if portrait is not None:
            self.screen.blit(portrait, (x, y))
        else:
            self._draw_portrait_placeholder(portrait_rect, c.archetype.sprite_color)

        banner_rect = pygame.Rect(x, y + portrait_h, w, banner_h)
        banner_bg = tuple(max(0, int(v * 0.28)) for v in rarity_color)
        pygame.draw.rect(self.screen, banner_bg, banner_rect)
        name_surf = self.font_small.render(c.name[:14], True, TEXT_COLOR)
        self.screen.blit(name_surf, (x + 6, y + portrait_h + 4))
        lvl_surf = self.font_small.render(f"Lv{c.level}", True, DIM_COLOR)
        self.screen.blit(lvl_surf, (x + w - lvl_surf.get_width() - 6, y + portrait_h + 4))
        self._draw_star_pips(x + 9, y + portrait_h + banner_h - 11, c.stars, MAX_STARS, rarity_color)

        border_w = 3 if selected else (2 if hovered else 1)
        border_color = HIGHLIGHT if selected else rarity_color
        pygame.draw.rect(self.screen, border_color, rect, border_w, border_radius=10)
        return rect

    # ------------------------------------------------------------------
    # Small drawing primitives shared by the Summon screen's splash panel
    # and card-reveal animation (see show_summon) -- kept generic (no
    # Summon-specific data touched here) in case a later screen wants the
    # same "dynamic" polish.
    # ------------------------------------------------------------------
    @staticmethod
    def _lerp_color(a, b, t: float):
        """Linear-interpolates two RGB tuples at t in [0, 1] -- the cheap
        way to get a "shimmering"/pulsing color over time (see show_summon's
        `pulse = 0.5 + 0.5*sin(time.time()*k)` callers) without needing
        per-pixel alpha blending, which the fake pygame stub used in tests
        doesn't support anyway."""
        t = max(0.0, min(1.0, t))
        return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

    def _draw_vertical_gradient(self, rect, top_color, bottom_color, steps=20) -> None:
        """Bands `rect` from top_color to bottom_color -- real pygame has no
        one-call gradient primitive, so this is just `steps` stacked flat
        rects, each individually cheap to draw at 30fps."""
        pygame = self.pygame
        step_h = max(1, rect.h // steps)
        for i in range(steps):
            t = i / max(1, steps - 1)
            color = self._lerp_color(top_color, bottom_color, t)
            band = pygame.Rect(rect.x, rect.y + i * step_h, rect.w, step_h + 1)
            pygame.draw.rect(self.screen, color, band)

    def _draw_rarity_spectrum_bar(self, rect, rarities) -> None:
        """A thin strip of `rect` divided into one flat-colored segment per
        rarity in `rarities` (data/hero_rarity.py's HERO_RARITY_COLOR) --
        decorates a Summon banner tile with a quick "here's what's in this
        pool" visual without needing any real art."""
        pygame = self.pygame
        from data.hero_rarity import HERO_RARITY_COLOR
        n = max(1, len(rarities))
        seg_w = max(1, rect.w // n)
        for i, rarity in enumerate(rarities):
            seg = pygame.Rect(rect.x + i * seg_w, rect.y, seg_w + 1, rect.h)
            pygame.draw.rect(self.screen, HERO_RARITY_COLOR.get(rarity, TEXT_COLOR), seg)

    def _draw_pull_button(self, rect, label: str, afford: bool, mouse_pos) -> None:
        pygame = self.pygame
        hovered = afford and rect.collidepoint(mouse_pos)
        color = BUTTON_HOVER if hovered else (BUTTON_COLOR if afford else (40, 40, 46))
        pygame.draw.rect(self.screen, color, rect, border_radius=10)
        text_color = TEXT_COLOR if afford else DIM_COLOR
        surf = self.font.render(label, True, text_color)
        self.screen.blit(surf, (rect.x + rect.w // 2 - surf.get_width() // 2,
                                 rect.y + rect.h // 2 - surf.get_height() // 2))
        pygame.draw.rect(self.screen, (10, 10, 10), rect, 1, border_radius=10)

    def _draw_reveal_card(self, rect, kind: str, result, revealed: bool, banner_h: int, tag_h: int) -> None:
        """Draws one Summon-reveal card at `rect`: a plain card back with a
        "?" while face-down (`revealed=False`), or the actual pull once
        flipped -- a portrait-or-placeholder (kind="character", via the same
        _get_portrait/_draw_portrait_placeholder show_heroes uses) or a
        colored gem icon (kind="equipment", since there's no item art),
        topped with a rarity-tinted name banner and a bottom tag strip
        ("NEW!"/"+N shards" for a character, "GEAR" for equipment)."""
        pygame = self.pygame
        from data.hero_rarity import HERO_RARITY_COLOR, HERO_RARITY_LABEL

        if not revealed:
            pygame.draw.rect(self.screen, (46, 46, 66), rect, border_radius=10)
            q = self.font_big.render("?", True, DIM_COLOR)
            self.screen.blit(q, (rect.x + rect.w // 2 - q.get_width() // 2,
                                  rect.y + rect.h // 2 - q.get_height() // 2))
            pygame.draw.rect(self.screen, (10, 10, 10), rect, 2, border_radius=10)
            return

        rarity = result.rarity
        color = HERO_RARITY_COLOR.get(rarity, TEXT_COLOR)
        portrait_h = rect.h - banner_h - tag_h

        if kind == "character":
            character = result.character
            portrait_rect = pygame.Rect(rect.x, rect.y, rect.w, portrait_h)
            portrait = self._get_portrait(character.name, (rect.w, portrait_h))
            if portrait is not None:
                self.screen.blit(portrait, (rect.x, rect.y))
            else:
                self._draw_portrait_placeholder(portrait_rect, character.archetype.sprite_color)
            name_text, sub_text = character.name, f"Lv{character.level}"
            if result.is_duplicate:
                tag_text, tag_color = f"+{result.shards_gained} shards", (230, 210, 90)
            else:
                tag_text, tag_color = "NEW!", (140, 235, 150)
        else:
            item = result.item
            icon_rect = pygame.Rect(rect.x, rect.y, rect.w, portrait_h)
            pygame.draw.rect(self.screen, tuple(max(0, int(v * 0.3)) for v in color), icon_rect, border_radius=10)
            cx, cy = rect.x + rect.w // 2, rect.y + portrait_h // 2
            s = min(rect.w, portrait_h) // 3
            pygame.draw.polygon(self.screen, color, [(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)])
            name_text, sub_text = item.name, item.slot.title()
            tag_text, tag_color = "GEAR", (150, 200, 255)

        banner_rect = pygame.Rect(rect.x, rect.y + portrait_h, rect.w, banner_h)
        banner_bg = tuple(max(0, int(v * 0.28)) for v in color)
        pygame.draw.rect(self.screen, banner_bg, banner_rect)
        name_surf = self.font_small.render(name_text[:16], True, TEXT_COLOR)
        self.screen.blit(name_surf, (rect.x + 6, rect.y + portrait_h + 4))
        sub_surf = self.font_small.render(sub_text, True, DIM_COLOR)
        self.screen.blit(sub_surf, (rect.x + 6, rect.y + portrait_h + 4 + name_surf.get_height()))

        tag_rect = pygame.Rect(rect.x, rect.y + portrait_h + banner_h, rect.w, tag_h)
        pygame.draw.rect(self.screen, (20, 20, 28), tag_rect)
        tag_surf = self.font_small.render(f"[{HERO_RARITY_LABEL[rarity]}] {tag_text}", True, tag_color)
        self.screen.blit(tag_surf, (rect.x + 4, rect.y + portrait_h + banner_h + (tag_h - tag_surf.get_height()) // 2))

        pygame.draw.rect(self.screen, color, rect, 3, border_radius=10)

    def _simple_button_row(self, labels_values, x, y, w=220, h=44, gap=14, vertical=True, selected=None):
        """Draws a column (or row) of buttons and returns their (rect, value)
        pairs for click detection -- the shared layout piece behind the title
        screen, the Colosseum hub, and any other plain menu screen.
        `selected`, if given (a single value or a set of values), renders
        those buttons as "active" (e.g. the current shop tab) regardless of
        mouse position."""
        pygame = self.pygame
        selected_set = {selected} if selected is not None and not isinstance(selected, (set, frozenset, list, tuple)) \
            else set(selected or ())
        mouse_pos = pygame.mouse.get_pos()
        rects = []
        for i, (label, value) in enumerate(labels_values):
            rx = x if vertical else x + i * (w + gap)
            ry = y + i * (h + gap) if vertical else y
            rect = pygame.Rect(rx, ry, w, h)
            hovered = rect.collidepoint(mouse_pos)
            is_selected = value in selected_set
            color = BUTTON_HOVER if (hovered or is_selected) else BUTTON_COLOR
            pygame.draw.rect(self.screen, color, rect, border_radius=8)
            pygame.draw.rect(self.screen, HIGHLIGHT if is_selected else (10, 10, 10),
                              rect, 2 if is_selected else 1, border_radius=8)
            label_surf = self.font.render(label, True, TEXT_COLOR)
            self.screen.blit(label_surf, (rect.x + 14, rect.y + (h - label_surf.get_height()) // 2))
            rects.append((rect, value))
        return rects

    def show_title_screen(self, has_save: bool) -> str:
        """Returns "new_game", "continue", or "quit". "continue" is only ever
        offered (and thus only ever returnable) when has_save is True."""
        pygame = self.pygame
        while True:
            self.screen.fill(BG_COLOR)
            title_surf = self.font_big.render("BATTLE COLOSSEUM", True, TEXT_COLOR)
            self.screen.blit(title_surf, (self.content_width // 2 - title_surf.get_width() // 2, 150))
            subtitle = self.font_small.render("placeholder-graphics prototype", True, DIM_COLOR)
            self.screen.blit(subtitle, (self.content_width // 2 - subtitle.get_width() // 2, 188))

            options = [("New Game", "new_game")]
            if has_save:
                options.append(("Continue", "continue"))
            options.append(("Quit", "quit"))
            rects = self._simple_button_row(options, self.content_width // 2 - 110, 260, w=220)

            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for rect, value in rects:
                        if rect.collidepoint(event.pos):
                            return value
            self.clock.tick(30)

    def show_character_creation(self, class_archetypes: dict, class_ids) -> tuple:
        """Name entry + class picker. Returns (name, class_id) once both a
        non-empty (post-strip) name and a class are chosen and the player
        confirms (click or Enter). Loops forever otherwise -- there's no
        "cancel" here since this only ever runs right after "New Game"."""
        pygame = self.pygame
        max_name_len = 18
        name_text = ""
        selected_class = None

        while True:
            self.screen.fill(BG_COLOR)
            header = self.font_big.render("Create Your Character", True, TEXT_COLOR)
            self.screen.blit(header, (30, 20))

            name_label = self.font.render("Name:", True, TEXT_COLOR)
            self.screen.blit(name_label, (30, 74))
            box = pygame.Rect(110, 68, 260, 32)
            pygame.draw.rect(self.screen, PANEL_COLOR, box)
            pygame.draw.rect(self.screen, HIGHLIGHT if name_text else (80, 80, 90), box, 1)
            cursor = "_" if (int(time.time() * 2) % 2 == 0) else " "
            name_surf = self.font.render(name_text + cursor, True, TEXT_COLOR)
            self.screen.blit(name_surf, (box.x + 8, box.y + 5))

            class_col_x = 30
            class_col_y = 122
            class_rects = []
            for cid in class_ids:
                archetype = class_archetypes[cid]
                rect = pygame.Rect(class_col_x, class_col_y, 240, 54)
                selected = selected_class == cid
                pygame.draw.rect(self.screen, BUTTON_HOVER if selected else BUTTON_COLOR, rect, border_radius=6)
                pygame.draw.rect(self.screen, HIGHLIGHT if selected else (10, 10, 10), rect,
                                  2 if selected else 1, border_radius=6)
                name_surf = self.font.render(archetype.name, True, TEXT_COLOR)
                self.screen.blit(name_surf, (rect.x + 10, rect.y + 6))
                skill_names = ", ".join(self.skills_db[sid].name for sid in archetype.skill_ids if sid in self.skills_db)
                skills_surf = self.font_small.render(skill_names[:34], True, DIM_COLOR)
                self.screen.blit(skills_surf, (rect.x + 10, rect.y + 30))
                class_rects.append((rect, cid))
                class_col_y += 62

            # Description panel for whichever class is currently selected.
            desc_x = 300
            if selected_class:
                archetype = class_archetypes[selected_class]
                stats = archetype.base_stats
                desc_y = 122
                for line in self._wrap(archetype.description, 46):
                    surf = self.font_small.render(line, True, TEXT_COLOR)
                    self.screen.blit(surf, (desc_x, desc_y))
                    desc_y += 18
                desc_y += 8
                stat_line1 = f"HP {stats.max_hp}  MP {stats.max_mp}  ATK {stats.atk}  DEF {stats.def_}"
                stat_line2 = f"MAG {stats.mag}  RES {stats.res}  SPD {stats.spd}  LUK {stats.luk}"
                for line in (stat_line1, stat_line2):
                    surf = self.font_small.render(line, True, (150, 200, 255))
                    self.screen.blit(surf, (desc_x, desc_y))
                    desc_y += 18
            else:
                hint = self.font_small.render("Pick a class to see its details.", True, DIM_COLOR)
                self.screen.blit(hint, (desc_x, 122))

            confirm_enabled = bool(name_text.strip()) and selected_class is not None
            confirm_rect = pygame.Rect(30, class_col_y + 10, 200, 44)
            confirm_color = BUTTON_HOVER if confirm_enabled else (45, 45, 54)
            pygame.draw.rect(self.screen, confirm_color, confirm_rect, border_radius=8)
            confirm_label = "Begin!" if confirm_enabled else "Enter a name & pick a class"
            confirm_surf = self.font_small.render(confirm_label, True, TEXT_COLOR if confirm_enabled else DIM_COLOR)
            self.screen.blit(confirm_surf, (confirm_rect.x + 12, confirm_rect.y + 14))

            pygame.display.flip()

            clickable = list(class_rects)
            if confirm_enabled:
                clickable.append((confirm_rect, "__confirm__"))

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        raise SystemExit(0)
                    if event.key == pygame.K_BACKSPACE:
                        name_text = name_text[:-1]
                    elif event.key == pygame.K_RETURN:
                        if confirm_enabled:
                            return name_text.strip(), selected_class
                    else:
                        ch = getattr(event, "unicode", "")
                        if ch and ch.isprintable() and len(name_text) < max_name_len:
                            name_text += ch
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for rect, value in clickable:
                        if rect.collidepoint(event.pos):
                            if value == "__confirm__":
                                return name_text.strip(), selected_class
                            selected_class = value
            self.clock.tick(30)

    def show_colosseum_hub(self, player_state, equipment_db: dict) -> str:
        """Returns "battle", "shop", "summon", "heroes", "quit_to_title", or,
        in debug mode only, "debug_add_gems" -- a cheat button (only ever
        shown when self.debug is True) that grants config.DEBUG_GEM_GRANT
        gems on the spot, so Summon's gacha pulls can be tested/spammed
        without grinding out real battle rewards for gems first."""
        pygame = self.pygame
        import config
        from data.hero_rarity import HERO_RARITY_COLOR, star_display
        from game import party as party_logic
        while True:
            self.screen.fill(BG_COLOR)
            header = self.font_big.render("The Colosseum", True, TEXT_COLOR)
            self.screen.blit(header, (30, 20))
            currency = self.font.render(
                f"Money: {player_state.money}    Gems: {player_state.gems}", True, (230, 210, 90))
            self.screen.blit(currency, (30, 62))

            # Shows the current battle party (see game/party.py), not the
            # whole owned roster -- once a roster can run past the 4-hero
            # party cap, "your roster" here stopped meaning "who I'm about
            # to fight with." The full collection is still one click away
            # on Heroes.
            party_chars = party_logic.active_party_characters(player_state)
            bench_count = len(player_state.characters) - len(party_chars)
            roster_label = self.font_small.render("Your party:", True, DIM_COLOR)
            self.screen.blit(roster_label, (30, 96))
            y = 118
            for c in party_chars:
                archetype = c.archetype
                equipped_bits = [equipment_db[i].name for i in c.equipped.values() if i and i in equipment_db]
                gear_txt = f" -- {', '.join(equipped_bits)}" if equipped_bits else " -- no gear equipped"
                line = f"{c.name}  ({archetype.name})  Lvl {c.level} {star_display(c.stars)}{gear_txt}"
                color = HERO_RARITY_COLOR.get(c.rarity, TEXT_COLOR)
                surf = self.font_small.render(line[:90], True, color)
                self.screen.blit(surf, (30, y))
                y += 20
            if not party_chars:
                empty = self.font_small.render("(no one selected yet -- Enter Battle to pick a party)", True, DIM_COLOR)
                self.screen.blit(empty, (30, y))
                y += 20
            if bench_count > 0:
                bench_txt = self.font_small.render(
                    f"+ {bench_count} more in reserve -- see Heroes", True, DIM_COLOR)
                self.screen.blit(bench_txt, (30, y))
                y += 20

            options = [("Enter Battle", "battle"), ("Shop", "shop"),
                       ("Summon", "summon"), ("Heroes", "heroes"),
                       ("Save & Quit to Title", "quit_to_title")]
            if self.debug:
                options.append((f"[DEBUG] Add {config.DEBUG_GEM_GRANT} Gems", "debug_add_gems"))
            btn_h, btn_gap = 44, 12
            base_y = self.height - (len(options) * btn_h + (len(options) - 1) * btn_gap) - 20
            rects = self._simple_button_row(options, 30, base_y, w=260, h=btn_h, gap=btn_gap)

            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for rect, value in rects:
                        if rect.collidepoint(event.pos):
                            return value
            self.clock.tick(30)

    def show_party_select(self, player_state, equipment_db: dict):
        """Toggle-select up to game/party.py's MAX_PARTY_SIZE heroes to
        actually fight the next battle (see main.py's run_game_loop, which
        calls this before show_battle_setup). Returns the confirmed list of
        PlayerCharacter (in roster order), or None if the player backs out
        without confirming -- mirrors show_battle_setup's own back-to-hub
        convention rather than introducing a new one.

        As of fix #20, this is a card screen matching show_heroes' look
        rather than a plain toggle-list: a fixed top strip of
        PARTY_SELECT_SLOT_* cards shows the current party (an empty "+"
        slot for each open spot), and a scrollable HERO_GRID_*/HERO_CARD_*
        grid below it -- the exact same card geometry show_heroes uses --
        shows every owned hero, bordered when they're in the party.
        Clicking a hero's portrait, in the top strip or in the grid below,
        toggles them in/out (via game/party.py's toggle_member); both draw
        through the shared _draw_hero_card helper so a hero looks identical
        wherever they're shown."""
        pygame = self.pygame
        from game import party as party_logic

        selected = party_logic.default_party_ids(player_state)
        message = ""
        message_color = (230, 120, 110)
        message_until = 0.0
        scroll_row = 0  # index of the first visible roster-grid row

        def flash(text: str) -> None:
            nonlocal message, message_until
            message = text
            message_until = time.time() + 3.0

        def toggle(character_id: str) -> None:
            nonlocal selected
            selected, changed = party_logic.toggle_member(selected, character_id)
            if not changed:
                flash(f"Party is already full ({party_logic.MAX_PARTY_SIZE} max) -- deselect someone first.")

        while True:
            mouse_pos = pygame.mouse.get_pos()
            self.screen.fill(BG_COLOR)
            header = self.font_big.render("Choose Your Party", True, TEXT_COLOR)
            self.screen.blit(header, (30, 20))
            sub = self.font_small.render(
                f"Click a hero's portrait to add or remove them -- up to {party_logic.MAX_PARTY_SIZE} heroes.",
                True, DIM_COLOR)
            self.screen.blit(sub, (30, 58))

            # --- top strip: the current party, MAX_PARTY_SIZE fixed slots --
            party_rects = []
            party_label = self.font_small.render(
                f"Your Party ({len(selected)}/{party_logic.MAX_PARTY_SIZE}):", True, DIM_COLOR)
            self.screen.blit(party_label, (HERO_GRID_LEFT, 84))
            id_to_char = {c.id: c for c in player_state.characters}
            for i in range(party_logic.MAX_PARTY_SIZE):
                slot_x = HERO_GRID_LEFT + i * (PARTY_SELECT_SLOT_W + PARTY_SELECT_SLOT_GAP)
                slot_y = PARTY_SELECT_SLOT_TOP
                slot_char = id_to_char.get(selected[i]) if i < len(selected) else None
                if slot_char is not None:
                    hovered = pygame.Rect(slot_x, slot_y, PARTY_SELECT_SLOT_W,
                                           PARTY_SELECT_SLOT_H).collidepoint(mouse_pos)
                    rect = self._draw_hero_card(slot_char, slot_x, slot_y, PARTY_SELECT_SLOT_W,
                                                 PARTY_SELECT_SLOT_H, PARTY_SELECT_SLOT_BANNER_H,
                                                 selected=True, hovered=hovered)
                    party_rects.append((rect, ("toggle", slot_char.id)))
                else:
                    # Empty "+" slot -- centerx/centery/bottom aren't used
                    # here (the fake pygame stub's Rect is x/y/w/h only, same
                    # limitation _draw_portrait_placeholder worked around in
                    # fix #14), just plain x+w//2/y+h arithmetic instead.
                    rect = pygame.Rect(slot_x, slot_y, PARTY_SELECT_SLOT_W, PARTY_SELECT_SLOT_H)
                    pygame.draw.rect(self.screen, (30, 30, 36), rect, border_radius=10)
                    pygame.draw.rect(self.screen, (70, 70, 78), rect, 2, border_radius=10)
                    center_x = slot_x + PARTY_SELECT_SLOT_W // 2
                    plus = self.font_big.render("+", True, DIM_COLOR)
                    self.screen.blit(plus, (center_x - plus.get_width() // 2,
                                             slot_y + PARTY_SELECT_SLOT_H // 2 - plus.get_height() // 2 - 8))
                    empty_label = self.font_small.render("Empty", True, DIM_COLOR)
                    self.screen.blit(empty_label, (center_x - empty_label.get_width() // 2,
                                                    slot_y + PARTY_SELECT_SLOT_H - 22))

            # --- roster grid below: every owned hero, click to toggle ------
            grid_rects = []
            roster_label = self.font_small.render("All Heroes (click to add/remove):", True, DIM_COLOR)
            self.screen.blit(roster_label, (HERO_GRID_LEFT, PARTY_SELECT_ROSTER_LABEL_Y))

            roster = player_state.characters
            row_stride = HERO_CARD_H + HERO_CARD_GAP
            grid_top = PARTY_SELECT_ROSTER_GRID_TOP
            grid_bottom = self.height - 70
            visible_rows = max(1, (grid_bottom - grid_top) // row_stride)
            total_rows = max(1, -(-len(roster) // HERO_GRID_COLS))  # ceil division
            max_scroll_row = max(0, total_rows - visible_rows)
            scroll_row = max(0, min(scroll_row, max_scroll_row))
            first_i = scroll_row * HERO_GRID_COLS
            last_i = min(len(roster), (scroll_row + visible_rows) * HERO_GRID_COLS)

            if not roster:
                empty = self.font_small.render(
                    "You have no heroes to field -- recruit one via Summon first.", True, DIM_COLOR)
                self.screen.blit(empty, (HERO_GRID_LEFT, grid_top))
            if scroll_row > 0:
                up_hint = self.font_small.render(f"^ scroll up for {first_i} more", True, DIM_COLOR)
                self.screen.blit(up_hint, (HERO_GRID_LEFT, grid_top - 18))

            for i in range(first_i, last_i):
                c = roster[i]
                row = (i // HERO_GRID_COLS) - scroll_row
                col = i % HERO_GRID_COLS
                card_x = HERO_GRID_LEFT + col * (HERO_CARD_W + HERO_CARD_GAP)
                card_y = grid_top + row * row_stride
                is_selected = c.id in selected
                hovered = pygame.Rect(card_x, card_y, HERO_CARD_W, HERO_CARD_H).collidepoint(mouse_pos)
                rect = self._draw_hero_card(c, card_x, card_y, HERO_CARD_W, HERO_CARD_H, HERO_CARD_BANNER_H,
                                             selected=is_selected, hovered=hovered)
                grid_rects.append((rect, ("toggle", c.id)))

            remaining_below = len(roster) - last_i
            if remaining_below > 0:
                hint_row = min(visible_rows, max(0, total_rows - scroll_row))
                hint_y = grid_top + hint_row * row_stride
                down_hint = self.font_small.render(f"v scroll down for {remaining_below} more", True, DIM_COLOR)
                self.screen.blit(down_hint, (HERO_GRID_LEFT, hint_y))

            if message and time.time() < message_until:
                msg_surf = self.font_small.render(message, True, message_color)
                self.screen.blit(msg_surf, (30, self.height - 100))

            confirm_label = f"Confirm Party ({len(selected)}/{party_logic.MAX_PARTY_SIZE})"
            confirm_rects = self._simple_button_row([(confirm_label, "confirm")], 30, self.height - 56, w=260, h=40)
            back_rects = self._simple_button_row([("Back to Colosseum", "back")], 310, self.height - 56, w=220, h=40)

            pygame.display.flip()

            clickable_rects = party_rects + grid_rects + confirm_rects + back_rects
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type == pygame.MOUSEWHEEL:
                    # Same convention show_heroes' own grid scrolling uses:
                    # event.y > 0 ("scrolled up") moves toward the start of
                    # the roster grid, clamped again at the top of the next
                    # frame.
                    scroll_row -= event.y
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for rect, value in clickable_rects:
                        if not rect.collidepoint(event.pos):
                            continue
                        if value == "back":
                            return None
                        if value == "confirm":
                            ok, msg, resolved = party_logic.confirm_party(player_state, selected)
                            if ok:
                                return resolved
                            flash(msg)
                        elif value[0] == "toggle":
                            toggle(value[1])
                        break
            self.clock.tick(30)

    def show_battle_setup(self, player_state, party):
        """Difficulty + opponent-count picker shown before entering a battle
        (see game/battle_setup.py). `party` is the list of PlayerCharacter
        chosen on show_party_select (up to game/party.py's MAX_PARTY_SIZE) --
        battle level/rewards scale off *this* group's average level, not the
        whole roster. Returns (difficulty, num_enemies), or None if the
        player backs all the way out to the hub. A tiny two-step screen
        (pick difficulty, then pick a count) rather than a full tabbed
        screen like Shop/Summon -- there's not much to browse."""
        pygame = self.pygame
        from game.battle_setup import (
            DIFFICULTY_IDS, DIFFICULTY_REWARD_MODIFIER, MAX_OPPONENTS, MIN_OPPONENTS, party_average_level,
        )

        avg_level = party_average_level(party)
        fielding = ", ".join(c.name for c in party)
        step = "difficulty"   # "difficulty" -> "count"
        difficulty = None

        while True:
            self.screen.fill(BG_COLOR)
            header = self.font_big.render("Battle Setup", True, TEXT_COLOR)
            self.screen.blit(header, (30, 20))
            level_surf = self.font.render(f"Party average level: {avg_level:.1f}", True, DIM_COLOR)
            self.screen.blit(level_surf, (30, 62))
            fielding_surf = self.font_small.render(f"Fielding: {fielding}"[:100], True, DIM_COLOR)
            self.screen.blit(fielding_surf, (30, 84))

            back_value = "back"
            if step == "difficulty":
                sub = self.font.render("Choose difficulty:", True, TEXT_COLOR)
                self.screen.blit(sub, (30, 106))
                options = [(f"{d.capitalize()}  (rewards x{DIFFICULTY_REWARD_MODIFIER[d]:g})", d)
                           for d in DIFFICULTY_IDS]
                rects = self._simple_button_row(options, 30, 140, w=320, h=44, gap=10)
                back_rects = self._simple_button_row([("Back to Colosseum", back_value)], 30, self.height - 56, w=220, h=40)
            else:
                sub = self.font.render(f"Difficulty: {difficulty.capitalize()}  --  How many opponents?", True, TEXT_COLOR)
                self.screen.blit(sub, (30, 106))
                options = [(str(n), n) for n in range(MIN_OPPONENTS, MAX_OPPONENTS + 1)]
                rects = self._simple_button_row(options, 30, 140, w=80, h=44, gap=10, vertical=False)
                back_rects = self._simple_button_row([("Back", back_value)], 30, self.height - 56, w=220, h=40)

            pygame.display.flip()

            clickable_rects = rects + back_rects
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for rect, value in clickable_rects:
                        if not rect.collidepoint(event.pos):
                            continue
                        if value == back_value:
                            if step == "count":
                                step = "difficulty"
                            else:
                                return None
                        elif step == "difficulty":
                            difficulty = value
                            step = "count"
                        else:  # step == "count", value is an int
                            return difficulty, value
                        break
            self.clock.tick(30)

    def show_shop(self, player_state, items_db: dict, equipment_db: dict) -> None:
        """Runs the Shop screen until the player clicks "Back to Colosseum".
        Mutates player_state in place via game/shop.py's pure functions --
        main.py saves afterward, same as it does after a battle. Equipping
        gear moved to the Heroes screen (show_heroes) as of the hero-rarity
        pass -- Andrew's AskUserQuestion answer had it replace Shop's old
        "Gear" tab rather than duplicate it, so Shop is buying-only now."""
        pygame = self.pygame
        from game import shop as shop_logic

        tabs = [("Items", "items"), ("Weapons", "weapon"), ("Armor", "armor"),
                ("Accessories", "accessory")]
        active_tab = "items"
        message = ""
        message_color = (140, 235, 150)
        message_until = 0.0

        def flash(ok: bool, text: str) -> None:
            nonlocal message, message_color, message_until
            message = text
            message_color = (140, 235, 150) if ok else (230, 120, 110)
            message_until = time.time() + 3.0

        while True:
            self.screen.fill(BG_COLOR)
            header = self.font_big.render("Shop", True, TEXT_COLOR)
            self.screen.blit(header, (30, 16))
            money_surf = self.font.render(f"Money: {player_state.money}", True, (230, 210, 90))
            self.screen.blit(money_surf, (30, 54))

            tab_rects = self._simple_button_row(tabs, 30, 90, w=148, h=34, gap=8,
                                                 vertical=False, selected=active_tab)

            row_rects = []
            list_y = 142
            row_w, row_h, row_gap = 720, 34, 6

            def draw_row(label: str, clickable: bool, value=None):
                nonlocal list_y
                rect = pygame.Rect(30, list_y, row_w, row_h)
                mouse_over = clickable and rect.collidepoint(pygame.mouse.get_pos())
                color = BUTTON_HOVER if mouse_over else (BUTTON_COLOR if clickable else (40, 40, 46))
                pygame.draw.rect(self.screen, color, rect, border_radius=6)
                text_color = TEXT_COLOR if clickable else DIM_COLOR
                surf = self.font_small.render(label[:104], True, text_color)
                self.screen.blit(surf, (rect.x + 10, rect.y + (row_h - surf.get_height()) // 2))
                list_y += row_h + row_gap
                if clickable:
                    row_rects.append((rect, value))

            if active_tab == "items":
                for item in sorted(items_db.values(), key=lambda i: i.cost):
                    if item.cost <= 0:
                        continue
                    owned = player_state.inventory.get(item.id, 0)
                    afford = player_state.money >= item.cost
                    label = f"{item.name} (x{owned} owned) -- {item.description}  [{item.cost}g]"
                    draw_row(label, afford, ("buy_item", item.id))
            else:  # "weapon", "armor", "accessory"
                for eq in sorted((e for e in equipment_db.values() if e.slot == active_tab and e.cost > 0),
                                  key=lambda e: e.cost):
                    afford = player_state.money >= eq.cost
                    label = f"{eq.name} -- {eq.bonus_text()}  [{eq.cost}g]"
                    draw_row(label, afford, ("buy_equipment", eq.id))

            if message and time.time() < message_until:
                msg_surf = self.font_small.render(message, True, message_color)
                self.screen.blit(msg_surf, (30, self.height - 96))

            back_rects = self._simple_button_row([("Back to Colosseum", "back")], 30, self.height - 56, w=220, h=40)

            pygame.display.flip()

            clickable_rects = tab_rects + row_rects + back_rects
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for rect, value in clickable_rects:
                        if not rect.collidepoint(event.pos):
                            continue
                        if value == "back":
                            return
                        if value in ("items", "weapon", "armor", "accessory"):
                            active_tab = value
                        elif value[0] == "buy_item":
                            flash(*shop_logic.buy_item(player_state, value[1], items_db))
                        elif value[0] == "buy_equipment":
                            flash(*shop_logic.buy_equipment(player_state, value[1], equipment_db))
                        break
            self.clock.tick(30)

    def _draw_summon_select_screen(self, player_state, banner: str, message: str, message_color,
                                    message_until: float, mouse_pos) -> list:
        """Draws the Summon screen's idle/banner-select view: a left rail of
        banner tiles (Hero Summon / Gear Summon, each showing its 1x/10x
        cost and a rarity-spectrum strip), a big center splash panel for
        whichever banner is currently selected (a showcase portrait/gem icon,
        a "Featuring..." caption, and the actual rarity odds), and a bottom
        pull bar. Returns the frame's clickable (rect, value) pairs."""
        pygame = self.pygame
        from data.hero_rarity import HERO_RARITIES, HERO_RARITY_COLOR, HERO_RARITY_LABEL, HERO_SUMMON_WEIGHTS
        from data.summon_pool import (
            CHARACTER_SUMMON_COST, CHARACTER_SUMMON_COST_X10, EQUIPMENT_SUMMON_COST,
            EQUIPMENT_SUMMON_COST_X10, RECRUITABLE_BY_RARITY, SUMMON_X10_COUNT,
        )
        from game.summon import EQUIPMENT_RARITY_WEIGHTS

        clickable = []
        header = self.font_big.render("Summon", True, TEXT_COLOR)
        self.screen.blit(header, (30, 16))
        currency = self.font.render(f"Gems: {player_state.gems}    Money: {player_state.money}",
                                     True, (230, 210, 90))
        self.screen.blit(currency, (self.content_width - currency.get_width() - 30, 24))

        # --- left banner rail ------------------------------------------------
        banners = [
            ("character", "Hero Summon", CHARACTER_SUMMON_COST, CHARACTER_SUMMON_COST_X10, HERO_RARITIES),
            ("equipment", "Gear Summon", EQUIPMENT_SUMMON_COST, EQUIPMENT_SUMMON_COST_X10, ("epic", "legendary")),
        ]
        rail_y = SUMMON_RAIL_Y
        for bid, title, cost1, cost10, spectrum in banners:
            rect = pygame.Rect(SUMMON_RAIL_X, rail_y, SUMMON_RAIL_W, SUMMON_RAIL_TILE_H)
            is_selected = banner == bid
            hovered = rect.collidepoint(mouse_pos)
            bg = BUTTON_HOVER if (hovered or is_selected) else BUTTON_COLOR
            pygame.draw.rect(self.screen, bg, rect, border_radius=10)
            self._draw_rarity_spectrum_bar(pygame.Rect(rect.x, rect.y, rect.w, 8), spectrum)
            title_surf = self.font.render(title, True, TEXT_COLOR)
            self.screen.blit(title_surf, (rect.x + 12, rect.y + 20))
            cost_surf = self.font_small.render(f"{cost1}g x1  /  {cost10}g x10", True, DIM_COLOR)
            self.screen.blit(cost_surf, (rect.x + 12, rect.y + 48))
            pygame.draw.rect(self.screen, HIGHLIGHT if is_selected else (10, 10, 10), rect,
                              3 if is_selected else 1, border_radius=10)
            clickable.append((rect, ("banner", bid)))
            rail_y += SUMMON_RAIL_TILE_H + SUMMON_RAIL_GAP

        owned_heroes = len(player_state.characters)
        owned_gear = sum(player_state.owned_equipment.values())
        stat1 = self.font_small.render(f"Heroes owned: {owned_heroes}/25", True, DIM_COLOR)
        self.screen.blit(stat1, (SUMMON_RAIL_X, rail_y + 8))
        stat2 = self.font_small.render(f"Gear in stash: {owned_gear}", True, DIM_COLOR)
        self.screen.blit(stat2, (SUMMON_RAIL_X, rail_y + 30))

        # --- center splash panel ---------------------------------------------
        panel_x = SUMMON_PANEL_X
        panel_w = max(300, self.content_width - panel_x - 30)
        panel_h = self.height - SUMMON_RAIL_Y - 190
        panel_rect = pygame.Rect(panel_x, SUMMON_RAIL_Y, panel_w, panel_h)
        if banner == "character":
            self._draw_vertical_gradient(panel_rect, (52, 40, 78), (18, 16, 28))
        else:
            self._draw_vertical_gradient(panel_rect, (60, 48, 30), (18, 16, 28))
        pygame.draw.rect(self.screen, (10, 10, 10), panel_rect, 1, border_radius=14)

        pulse = 0.5 + 0.5 * math.sin(time.time() * 2.2)  # a slow glow so the idle screen isn't static
        art_w, art_h = 240, 320
        art_rect = pygame.Rect(panel_x + panel_w // 2 - art_w // 2, panel_rect.y + 24, art_w, art_h)
        if banner == "character":
            feature = RECRUITABLE_BY_RARITY["mythic"][0]
            glow_color = self._lerp_color(HERO_RARITY_COLOR["mythic"], (255, 255, 255), pulse * 0.3)
            glow_rect = pygame.Rect(art_rect.x - 6, art_rect.y - 6, art_rect.w + 12, art_rect.h + 12)
            pygame.draw.rect(self.screen, glow_color, glow_rect, 3, border_radius=16)
            portrait = self._get_portrait(feature.name, (art_w, art_h))
            if portrait is not None:
                self.screen.blit(portrait, (art_rect.x, art_rect.y))
            else:
                self._draw_portrait_placeholder(art_rect, HERO_RARITY_COLOR["mythic"])
            caption = f'Featuring "{feature.name}" and 24 other heroes across 5 classes'
            odds = [f"{HERO_RARITY_LABEL[r]} {HERO_SUMMON_WEIGHTS[r]}%" for r in HERO_RARITIES]
        else:
            color = self._lerp_color(HERO_RARITY_COLOR["epic"], HERO_RARITY_COLOR["legendary"], pulse)
            pygame.draw.rect(self.screen, tuple(max(0, int(v * 0.3)) for v in color), art_rect, border_radius=16)
            cx, cy = art_rect.x + art_w // 2, art_rect.y + art_h // 2
            s = 70
            pygame.draw.polygon(self.screen, color, [(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)])
            pygame.draw.rect(self.screen, color, art_rect, 3, border_radius=16)
            caption = "Featuring premium epic & legendary gear"
            total = sum(EQUIPMENT_RARITY_WEIGHTS.values())
            odds = [f"{r.title()} {round(100 * w / total)}%" for r, w in EQUIPMENT_RARITY_WEIGHTS.items()]

        caption_surf = self.font_small.render(caption, True, TEXT_COLOR)
        self.screen.blit(caption_surf, (panel_x + panel_w // 2 - caption_surf.get_width() // 2, art_rect.y + art_h + 18))
        odds_surf = self.font_small.render("Odds: " + "  ".join(odds), True, DIM_COLOR)
        self.screen.blit(odds_surf, (panel_x + panel_w // 2 - odds_surf.get_width() // 2, art_rect.y + art_h + 40))

        # --- bottom pull bar ---------------------------------------------------
        cost1 = CHARACTER_SUMMON_COST if banner == "character" else EQUIPMENT_SUMMON_COST
        cost10 = CHARACTER_SUMMON_COST_X10 if banner == "character" else EQUIPMENT_SUMMON_COST_X10
        afford1 = player_state.gems >= cost1
        afford10 = player_state.gems >= cost10
        pull_y = self.height - 130
        pull1_rect = pygame.Rect(panel_x + panel_w // 2 - SUMMON_PULL_BTN_W - SUMMON_PULL_BTN_GAP // 2,
                                  pull_y, SUMMON_PULL_BTN_W, SUMMON_PULL_BTN_H)
        pull10_rect = pygame.Rect(panel_x + panel_w // 2 + SUMMON_PULL_BTN_GAP // 2,
                                   pull_y, SUMMON_PULL_BTN_W, SUMMON_PULL_BTN_H)
        self._draw_pull_button(pull1_rect, f"Pull x1 -- {cost1}g", afford1, mouse_pos)
        self._draw_pull_button(pull10_rect, f"Pull x{SUMMON_X10_COUNT} -- {cost10}g", afford10, mouse_pos)
        if afford1:
            clickable.append((pull1_rect, ("pull", banner, 1)))
        if afford10:
            clickable.append((pull10_rect, ("pull", banner, SUMMON_X10_COUNT)))

        if message and time.time() < message_until:
            msg_surf = self.font_small.render(message, True, message_color)
            self.screen.blit(msg_surf, (30, self.height - 96))

        clickable += self._simple_button_row([("Back to Colosseum", "back")], 30, self.height - 56, w=220, h=40)
        return clickable

    def _draw_summon_reveal_screen(self, kind: str, results: list, revealed: list, mouse_pos) -> list:
        """Draws the post-pull reveal: one big card for a x1 pull, or a
        5-wide grid of face-down/face-up cards for a x10 pull (see
        _draw_reveal_card). A still-face-down card is clickable to flip just
        that one; once every card is revealed, a rarity-count summary line
        appears with a "Continue" button, otherwise a "Reveal All" button
        lets the player skip straight to the fully-revealed state. Returns
        the frame's clickable (rect, value) pairs."""
        pygame = self.pygame
        header = self.font_big.render("Results", True, TEXT_COLOR)
        self.screen.blit(header, (30, 16))

        clickable = []
        count = len(results)
        if count == 1:
            rect = pygame.Rect(self.content_width // 2 - SUMMON_SOLO_CARD_W // 2, 110,
                                SUMMON_SOLO_CARD_W, SUMMON_SOLO_CARD_H)
            self._draw_reveal_card(rect, kind, results[0], revealed[0], SUMMON_SOLO_BANNER_H, SUMMON_SOLO_TAG_H)
            if not revealed[0]:
                clickable.append((rect, ("flip", 0)))
            grid_bottom = rect.y + rect.h
        else:
            cols = SUMMON_REVEAL_COLS
            rows = -(-count // cols)  # ceil division
            grid_w = cols * (SUMMON_REVEAL_CARD_W + SUMMON_REVEAL_CARD_GAP) - SUMMON_REVEAL_CARD_GAP
            grid_x = self.content_width // 2 - grid_w // 2
            row_stride = SUMMON_REVEAL_CARD_H + SUMMON_REVEAL_CARD_GAP
            for i, result in enumerate(results):
                row, col = divmod(i, cols)
                rect = pygame.Rect(grid_x + col * (SUMMON_REVEAL_CARD_W + SUMMON_REVEAL_CARD_GAP),
                                    SUMMON_REVEAL_TOP + row * row_stride,
                                    SUMMON_REVEAL_CARD_W, SUMMON_REVEAL_CARD_H)
                self._draw_reveal_card(rect, kind, result, revealed[i], SUMMON_REVEAL_BANNER_H, SUMMON_REVEAL_TAG_H)
                if not revealed[i]:
                    clickable.append((rect, ("flip", i)))
            grid_bottom = SUMMON_REVEAL_TOP + rows * row_stride

        if all(revealed):
            from collections import Counter
            from data.hero_rarity import HERO_RARITIES, HERO_RARITY_LABEL
            counts = Counter(r.rarity for r in results)
            summary = "  ".join(f"{HERO_RARITY_LABEL[r]} x{counts[r]}" for r in HERO_RARITIES if counts.get(r))
            summary_surf = self.font_small.render(summary, True, TEXT_COLOR)
            self.screen.blit(summary_surf, (self.content_width // 2 - summary_surf.get_width() // 2, grid_bottom + 14))
            clickable += self._simple_button_row([("Continue", "continue")],
                                                  self.content_width // 2 - 110, self.height - 70, w=220, h=40)
        else:
            clickable += self._simple_button_row([("Reveal All", "reveal_all")],
                                                  self.content_width // 2 - 110, self.height - 70, w=220, h=40)
        return clickable

    def show_summon(self, player_state, equipment_db: dict) -> None:
        """Runs the Summon screen until the player clicks "Back to
        Colosseum" (only offered from the banner-select view -- Back is
        hidden during a reveal, same "finish looking at what you pulled
        first" convention any gacha game uses). Two banners -- Hero Summon
        (game/summon.py's summon_character_batch, recruits or grants hero
        shards on a duplicate) and Gear Summon (summon_equipment_batch, a
        random premium item into the unequipped stash) -- each offering a
        1x and a 10x pull. Every pull lands in a card-flip reveal: a single
        big card for a 1x pull, a 5-wide grid of face-down cards for a 10x
        pull that the player can flip one at a time or all at once via
        "Reveal All". Mutates player_state in place; main.py saves
        afterward, same as every other hub screen. See
        _draw_summon_select_screen/_draw_summon_reveal_screen for the actual
        rendering."""
        pygame = self.pygame
        from game import summon as summon_logic

        banner = "character"
        phase = "select"    # "select" | "reveal"
        pending_kind = None
        pending_results = []
        card_revealed = []
        message = ""
        message_color = (230, 120, 110)
        message_until = 0.0

        def flash(text: str) -> None:
            nonlocal message, message_color, message_until
            message = text
            message_color = (230, 120, 110)
            message_until = time.time() + 3.0

        while True:
            self.screen.fill(BG_COLOR)
            mouse_pos = pygame.mouse.get_pos()

            if phase == "select":
                clickable_rects = self._draw_summon_select_screen(
                    player_state, banner, message, message_color, message_until, mouse_pos)
            else:
                clickable_rects = self._draw_summon_reveal_screen(pending_kind, pending_results, card_revealed,
                                                                    mouse_pos)

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for rect, value in clickable_rects:
                        if not rect.collidepoint(event.pos):
                            continue
                        if phase == "select":
                            if value == "back":
                                return
                            elif value[0] == "banner":
                                banner = value[1]
                            elif value[0] == "pull":
                                pull_kind, count = value[1], value[2]
                                if pull_kind == "character":
                                    ok, msg, results = summon_logic.summon_character_batch(player_state, count)
                                else:
                                    ok, msg, results = summon_logic.summon_equipment_batch(
                                        player_state, equipment_db, count)
                                if ok:
                                    pending_kind, pending_results = pull_kind, results
                                    card_revealed = [False] * len(results)
                                    phase = "reveal"
                                else:
                                    flash(msg)
                        else:  # phase == "reveal"
                            if value[0] == "flip":
                                card_revealed[value[1]] = True
                            elif value == "reveal_all":
                                card_revealed = [True] * len(card_revealed)
                            elif value == "continue":
                                phase = "select"
                                pending_kind, pending_results, card_revealed = None, [], []
                        break
            self.clock.tick(30)

    def show_heroes(self, player_state, equipment_db: dict) -> None:
        """Runs the Heroes screen until the player clicks "Back to
        Colosseum": a scrollable grid of Mobile-Legends-Adventure-style hero
        cards on the left -- portrait art from data/portraits/ when Andrew's
        dropped a matching file in, a drawn placeholder silhouette
        otherwise (see _get_portrait/_draw_portrait_placeholder), each card
        bordered/banner-tinted by rarity with a star-pip row -- and a detail
        panel on the right for whichever card's selected: stats, star
        level/shards with an upgrade button (game/heroes.py), and gear
        equip/unequip (game/shop.py, moved here from Shop's old "Gear" tab
        as of the hero-rarity pass). Scrolling (mouse wheel, same
        convention the old single-column list used) moves a whole grid row
        at a time -- see scroll_row below."""
        pygame = self.pygame
        from data.hero_rarity import HERO_RARITY_COLOR, HERO_RARITY_LABEL, shard_cost_for_next_star, star_display
        from game import heroes as heroes_logic
        from game import shop as shop_logic

        selected_id = player_state.characters[0].id if player_state.characters else None
        message = ""
        message_color = (140, 235, 150)
        message_until = 0.0
        scroll_row = 0  # index of the first visible grid row

        def flash(ok: bool, text: str) -> None:
            nonlocal message, message_color, message_until
            message = text
            message_color = (140, 235, 150) if ok else (230, 120, 110)
            message_until = time.time() + 3.0

        while True:
            character = next((c for c in player_state.characters if c.id == selected_id), None)
            mouse_pos = pygame.mouse.get_pos()

            self.screen.fill(BG_COLOR)
            header = self.font_big.render("Heroes", True, TEXT_COLOR)
            self.screen.blit(header, (30, 16))
            list_label = self.font_small.render("Your heroes:", True, DIM_COLOR)
            self.screen.blit(list_label, (HERO_GRID_LEFT, 58))

            # --- hero card grid, scrollable a row at a time -----------------
            grid_rects = []
            roster = player_state.characters
            row_stride = HERO_CARD_H + HERO_CARD_GAP
            grid_bottom = self.height - 70
            visible_rows = max(1, (grid_bottom - HERO_GRID_TOP) // row_stride)
            total_rows = max(1, -(-len(roster) // HERO_GRID_COLS))  # ceil division
            max_scroll_row = max(0, total_rows - visible_rows)
            scroll_row = max(0, min(scroll_row, max_scroll_row))
            first_i = scroll_row * HERO_GRID_COLS
            last_i = min(len(roster), (scroll_row + visible_rows) * HERO_GRID_COLS)

            if not roster:
                empty = self.font_small.render("(none yet -- try Summon)", True, DIM_COLOR)
                self.screen.blit(empty, (HERO_GRID_LEFT, HERO_GRID_TOP))
            if scroll_row > 0:
                up_hint = self.font_small.render(f"^ scroll up for {first_i} more", True, DIM_COLOR)
                self.screen.blit(up_hint, (HERO_GRID_LEFT, HERO_GRID_TOP - 18))

            for i in range(first_i, last_i):
                c = roster[i]
                row = (i // HERO_GRID_COLS) - scroll_row
                col = i % HERO_GRID_COLS
                card_x = HERO_GRID_LEFT + col * (HERO_CARD_W + HERO_CARD_GAP)
                card_y = HERO_GRID_TOP + row * row_stride
                is_selected = c.id == selected_id
                hovered = pygame.Rect(card_x, card_y, HERO_CARD_W, HERO_CARD_H).collidepoint(mouse_pos)
                rect = self._draw_hero_card(c, card_x, card_y, HERO_CARD_W, HERO_CARD_H, HERO_CARD_BANNER_H,
                                             selected=is_selected, hovered=hovered)
                grid_rects.append((rect, ("select", c.id)))

            remaining_below = len(roster) - last_i
            if remaining_below > 0:
                hint_row = min(visible_rows, max(0, total_rows - scroll_row))
                hint_y = HERO_GRID_TOP + hint_row * row_stride
                down_hint = self.font_small.render(f"v scroll down for {remaining_below} more", True, DIM_COLOR)
                self.screen.blit(down_hint, (HERO_GRID_LEFT, hint_y))

            # --- right panel: stats, star upgrade, gear ---------------------
            detail_rects = []
            panel_x = HERO_DETAIL_X
            if character is None:
                hint = self.font.render("Select a hero on the left.", True, DIM_COLOR)
                self.screen.blit(hint, (panel_x, 80))
            else:
                stats = character.effective_stats(equipment_db)
                color = HERO_RARITY_COLOR.get(character.rarity, TEXT_COLOR)
                name_surf = self.font_big.render(character.name, True, color)
                self.screen.blit(name_surf, (panel_x, 58))
                sub = self.font_small.render(
                    f"[{HERO_RARITY_LABEL[character.rarity]}] {character.archetype.name}  --  "
                    f"Lvl {character.level}", True, DIM_COLOR)
                self.screen.blit(sub, (panel_x, 94))
                star_surf = self.font.render(
                    f"{star_display(character.stars)}   Shards: {character.shards}", True, TEXT_COLOR)
                self.screen.blit(star_surf, (panel_x, 116))

                stat_lines = [
                    f"HP {stats.max_hp}    MP {stats.max_mp}",
                    f"ATK {stats.atk}    DEF {stats.def_}",
                    f"MAG {stats.mag}    RES {stats.res}",
                    f"SPD {stats.spd}    LUK {stats.luk}",
                ]
                y = 152
                for line in stat_lines:
                    surf = self.font_small.render(line, True, TEXT_COLOR)
                    self.screen.blit(surf, (panel_x, y))
                    y += 20
                y += 6

                cost = shard_cost_for_next_star(character.rarity, character.stars)
                if cost is None:
                    max_surf = self.font_small.render("Stars: MAX", True, (140, 235, 150))
                    self.screen.blit(max_surf, (panel_x, y))
                    y += 30
                else:
                    afford = character.shards >= cost
                    upgrade_label = f"Upgrade Star ({character.shards}/{cost} shards)"
                    rect = pygame.Rect(panel_x, y, 300, 36)
                    hovered = afford and rect.collidepoint(mouse_pos)
                    btn_color = BUTTON_HOVER if hovered else (BUTTON_COLOR if afford else (40, 40, 46))
                    pygame.draw.rect(self.screen, btn_color, rect, border_radius=8)
                    surf = self.font_small.render(upgrade_label, True, TEXT_COLOR if afford else DIM_COLOR)
                    self.screen.blit(surf, (rect.x + 12, rect.y + (rect.h - surf.get_height()) // 2))
                    if afford:
                        detail_rects.append((rect, ("upgrade", character.id)))
                    y += 36 + 10

                row_w2 = max(300, self.content_width - panel_x - 20)  # fit within the window regardless of grid width

                def draw_gear_row(label: str, clickable: bool, value=None):
                    nonlocal y
                    rect = pygame.Rect(panel_x, y, row_w2, 30)
                    hovered = clickable and rect.collidepoint(mouse_pos)
                    bg = BUTTON_HOVER if hovered else (BUTTON_COLOR if clickable else (40, 40, 46))
                    pygame.draw.rect(self.screen, bg, rect, border_radius=6)
                    text_color = TEXT_COLOR if clickable else DIM_COLOR
                    surf = self.font_small.render(label[:90], True, text_color)
                    self.screen.blit(surf, (rect.x + 10, rect.y + (rect.h - surf.get_height()) // 2))
                    y += 30 + 6
                    if clickable:
                        detail_rects.append((rect, value))

                stash_label = self.font_small.render("Owned, unequipped (click to equip):", True, DIM_COLOR)
                self.screen.blit(stash_label, (panel_x, y))
                y += 22
                stashed = [(eid, n) for eid, n in player_state.owned_equipment.items() if n > 0]
                if not stashed:
                    draw_gear_row("(nothing in your stash -- buy some gear first)", False)
                for eq_id, count in stashed:
                    eq = equipment_db.get(eq_id)
                    if not eq:
                        continue
                    label = f"{eq.name} x{count} -- {eq.bonus_text()}"
                    draw_gear_row(label, True, ("equip", eq_id))

                y += 8
                equipped_label = self.font_small.render(
                    f"{character.name}'s equipped gear (click to unequip):", True, DIM_COLOR)
                self.screen.blit(equipped_label, (panel_x, y))
                y += 22
                for slot in ("weapon", "armor", "accessory"):
                    eq_id = character.equipped.get(slot)
                    eq = equipment_db.get(eq_id) if eq_id else None
                    label = f"{slot.title()}: {eq.name if eq else '(empty)'}"
                    draw_gear_row(label, bool(eq_id), ("unequip", slot))

            if message and time.time() < message_until:
                msg_surf = self.font_small.render(message, True, message_color)
                self.screen.blit(msg_surf, (30, self.height - 96))

            back_rects = self._simple_button_row([("Back to Colosseum", "back")], 30, self.height - 56, w=220, h=40)

            pygame.display.flip()

            clickable_rects = grid_rects + detail_rects + back_rects
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type == pygame.MOUSEWHEEL:
                    # event.y > 0 is "wheel scrolled up" (away from the
                    # player) -- move the visible window toward the start of
                    # the grid, same direction convention as scrolling up a
                    # page. Clamped again at the top of the next frame.
                    scroll_row -= event.y
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for rect, value in clickable_rects:
                        if not rect.collidepoint(event.pos):
                            continue
                        if value == "back":
                            return
                        if value[0] == "select":
                            selected_id = value[1]
                        elif value[0] == "upgrade":
                            flash(*heroes_logic.upgrade_star(player_state, value[1]))
                        elif value[0] == "equip" and character is not None:
                            flash(*shop_logic.equip_from_stash(player_state, character.id, value[1], equipment_db))
                        elif value[0] == "unequip" and character is not None:
                            flash(*shop_logic.unequip(player_state, character.id, value[1], equipment_db))
                        break
            self.clock.tick(30)

    def show_not_implemented(self, title: str, message: str) -> None:
        """A generic 'coming soon' screen -- used by Shop and Summon while
        those stages were still stubs; both are built now (see show_shop,
        show_summon), but this stays around as reusable scaffolding for
        whatever hub feature is next. Waits for any click/keypress, then
        returns."""
        pygame = self.pygame
        waiting = True
        while waiting:
            self.screen.fill(BG_COLOR)
            title_surf = self.font_big.render(title, True, TEXT_COLOR)
            self.screen.blit(title_surf, (self.content_width // 2 - title_surf.get_width() // 2, self.height // 2 - 70))
            y = self.height // 2 - 20
            for line in self._wrap(message, 50):
                surf = self.font_small.render(line, True, DIM_COLOR)
                self.screen.blit(surf, (self.content_width // 2 - surf.get_width() // 2, y))
                y += 18
            hint = self.font_small.render("Press any key or click to go back", True, DIM_COLOR)
            self.screen.blit(hint, (self.content_width // 2 - hint.get_width() // 2, y + 20))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    waiting = False
            self.clock.tick(30)

    # ------------------------------------------------------------------
    # Menu interaction
    # ------------------------------------------------------------------
    def _wait_for_choice(self, state, highlight_actor_id, buttons, menu_title):
        pygame = self.pygame
        while True:
            rects = self._draw_frame(state, highlight_actor_id, buttons, menu_title)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    raise SystemExit(0)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for rect, value in rects:
                        if rect.collidepoint(event.pos):
                            return value
            self.clock.tick(30)

    # ------------------------------------------------------------------
    # BattleEngine.get_party_action implementation
    # ------------------------------------------------------------------
    def get_party_action(self, combatant, state: dict) -> Action:
        main_buttons = [("Attack", "attack"), ("Skill", "skill"), ("Item", "item"),
                         ("Defend", "defend"), ("Flee", "flee")]
        choice = self._wait_for_choice(state, combatant.id, main_buttons, f"{combatant.name}: choose an action")

        if choice == "attack":
            target = self._choose_target(state, combatant.id, state["enemies"], "Attack who?")
            return Action.attack(combatant.id, target["id"])

        if choice == "skill":
            skills = state.get("available_skills", [])
            if not skills:
                target = self._choose_target(state, combatant.id, state["enemies"], "No skills known -- attack who?")
                return Action.attack(combatant.id, target["id"])
            buttons = [(f"{s['name']} (MP{s['mp_cost']})", s) for s in skills]
            skill = self._wait_for_choice(state, combatant.id, buttons, "Choose a skill")
            if combatant.mp < skill["mp_cost"]:
                return self.get_party_action(combatant, state)  # not enough MP, re-prompt
            target_type = skill["target"]
            if target_type == "self":
                return Action.use_skill(combatant.id, skill["id"], [combatant.id])
            if target_type == "all_enemies":
                return Action.use_skill(combatant.id, skill["id"], [e["id"] for e in state["enemies"] if e["alive"]])
            if target_type == "all_allies":
                return Action.use_skill(combatant.id, skill["id"], [p["id"] for p in state["party"] if p["alive"]])
            pool = state["party"] if target_type == "single_ally" else state["enemies"]
            target = self._choose_target(state, combatant.id, pool, "Target who?")
            return Action.use_skill(combatant.id, skill["id"], [target["id"]])

        if choice == "item":
            items = state.get("available_items", [])
            if not items:
                return self.get_party_action(combatant, state)
            buttons = [(f"{i['name']} x{i['count']}", i) for i in items]
            item_info = self._wait_for_choice(state, combatant.id, buttons, "Choose an item")
            item = self.items_db[item_info["id"]]
            pool = [p for p in state["party"] if not p["alive"]] if item.revive else [p for p in state["party"] if p["alive"]]
            target = self._choose_target(state, combatant.id, pool, "Use on whom?")
            return Action.use_item(combatant.id, item_info["id"], [target["id"]])

        if choice == "defend":
            return Action.defend(combatant.id)

        return Action.flee(combatant.id)

    def _choose_target(self, state, actor_id, candidates, title):
        alive = [c for c in candidates if c["alive"]] or candidates
        if len(alive) == 1:
            return alive[0]
        buttons = [(f"{c['name']} ({c['hp']}/{c['max_hp']})", c) for c in alive]
        return self._wait_for_choice(state, actor_id, buttons, title)

    # ------------------------------------------------------------------
    # End-of-battle screen
    # ------------------------------------------------------------------
    def show_end_screen(self, result: str, money: int = None, gems: int = None, quit_on_close: bool = True,
                         xp: int = None, level_ups: dict = None) -> None:
        """money/gems, when given, are shown as a reward line under the result
        (see game/rewards.py) -- omit them for a one-off battle with no meta
        economy attached. xp/level_ups add an XP line and one "leveled up"
        line per character who gained a level (level_ups is
        {character_name: levels_gained}, see PlayerCharacter.grant_xp).
        quit_on_close controls whether closing this screen exits the whole
        program (the original single-battle-and-done behavior, still used
        when main.py isn't running the full title/hub game loop) or just
        returns control to the caller (the Colosseum hub loop, which wants
        to keep the window open and go back to the hub afterward)."""
        pygame = self.pygame
        message = {
            "victory": "VICTORY!",
            "defeat": "DEFEAT...",
            "fled": "You fled the battle.",
        }.get(result, result.upper())
        state = self.engine.build_state() if self.engine else {"party": [], "enemies": [], "round": 0}
        reward_line = None
        if money is not None:
            reward_line = f"+{money} money"
            if gems:
                reward_line += f"   +{gems} gems"
            if xp:
                reward_line += f"   +{xp} XP each"
        level_up_lines = [f"{name} leveled up! (+{levels})" for name, levels in (level_ups or {}).items() if levels]
        overlay_h = 120
        if reward_line:
            overlay_h += 40
        overlay_h += 24 * len(level_up_lines)
        waiting = True
        while waiting:
            self._draw_frame(state)  # leaves the debug panel (if any) visible under the overlay
            overlay = pygame.Surface((self.content_width, overlay_h))
            overlay.set_alpha(220)
            overlay.fill((15, 15, 20))
            self.screen.blit(overlay, (0, self.height // 2 - overlay_h // 2))
            text = self.font_big.render(message, True, TEXT_COLOR)
            self.screen.blit(text, (self.content_width // 2 - text.get_width() // 2, self.height // 2 - overlay_h // 2 + 20))
            next_y = self.height // 2 - overlay_h // 2 + 60
            if reward_line:
                reward_surf = self.font.render(reward_line, True, (230, 210, 90))
                self.screen.blit(reward_surf, (self.content_width // 2 - reward_surf.get_width() // 2, next_y))
                next_y += 30
            for line in level_up_lines:
                lu_surf = self.font_small.render(line, True, (140, 220, 250))
                self.screen.blit(lu_surf, (self.content_width // 2 - lu_surf.get_width() // 2, next_y))
                next_y += 24
            hint = self.font_small.render("Press any key or click to continue", True, DIM_COLOR)
            self.screen.blit(hint, (self.content_width // 2 - hint.get_width() // 2, next_y))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    waiting = False
                    if not quit_on_close:
                        pygame.quit()
                        raise SystemExit(0)
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    waiting = False
            self.clock.tick(30)
        if quit_on_close:
            pygame.quit()

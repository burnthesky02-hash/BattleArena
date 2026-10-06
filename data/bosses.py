"""Boss fights: hand-authored, scripted encounters.

A BossDef is a one-enemy encounter with a big custom sprite, a big HP pool,
its own unique skills, and a *script* -- a data-driven list of triggers that
fire dialogue, effects and scripted actions at chosen moments of the fight.
game/boss_script.py's BossRunner executes the script; the browser renders the
dialogue boxes and effects. Adding a boss = adding one BossDef below (plus its
sprite under data/Bosses/) -- no engine or UI code needed.

SCRIPT FORMAT
-------------
script = {
    "intro":    [step, ...],   # before round 1
    "triggers": [trigger, ...],
    "victory":  [step, ...],   # player wins
    "defeat":   [step, ...],   # party wiped
}

trigger = {
    "id": "phase2",                    # unique per boss; used for once-only bookkeeping
    "when": {...},                     # condition, see below
    "once": True,                      # default True; False = fires every time it is true
    "steps": [step, ...],
}

conditions ("when"; every key present must hold):
    {"hp_below": 0.6}                  boss HP fraction <= 0.6
    {"round_at_least": 3}              current round >= 3
    {"every_n_rounds": 3, "from": 3}   fires on rounds 3, 6, 9... (use with "once": False)
    {"heroes_down_at_least": 1}        at least one hero is KO'd
    {"heroes_alive_at_most": 1}        only one hero is left standing

Triggers are checked right after every action, and once more just before the
boss decides its move (so round-based triggers land at the start of its turn).

steps (each is a dict with one key):
    {"say": ("Speaker", "Text")}                   dialogue box (click to advance; blocks the fight)
    {"say": ("Speaker", "Text", "portrait_name")}  optional portrait (Portraits/<name>.webp)
    {"log": "text"}                                 line in the battle log
    {"announce": "TEXT"}                            big banner over the arena
    {"shake": True}                                 screen shake
    {"flash": "#ffffff"}                            screen flash in that color
    {"heal_boss_pct": 0.10}                         boss heals 10% of max HP
    {"apply_status": {"target": "boss"|"party", "status": "atk_up", "duration": 3}}
    {"force_skill": {"skill": "arena_slam", "target": "highest_hp"|"lowest_hp"|"random"|"all"}}
        -> the boss's NEXT action is this skill, regardless of what the AI would pick
        (this is how telegraphed / scripted attacks are done)
    {"pause": 600}                                  wait ms before continuing
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from engine.skills import Skill
from engine.stats import Stats
from engine.status_effects import STATUS_DB, StatusEffect
from engine.types import Element, TargetType


# Boss-only status: while a boss has it, every physical hit it takes from a hero is answered
# with an immediate counter-strike (game/boss_script.py's BossRunner does the countering).
STATUS_DB["counter"] = StatusEffect(
    key="counter", name="Counter Stance", duration=2, icon_color=(230, 120, 60),
    description="Punishes physical attackers with an immediate counter-strike. Spells slip past it.",
)

# Ronan's enrage. duration -1 = lasts until the battle ends.
STATUS_DB["bloodlust"] = StatusEffect(
    key="bloodlust", name="Bloodlust", duration=-1, icon_color=(230, 30, 30),
    stat_mods={"atk": 1.8, "spd": 1.35, "mag": 1.5, "def_": 1.1},
    description="Ronan has lost his sister and will not stop. Vastly stronger and faster.",
)

# The Unbroken Pair's extra statuses (game/twins_fight.py drives them).
# Selene's telegraphed execution: sits on a hero until she strikes (or the mark is broken).
STATUS_DB["marked"] = StatusEffect(
    key="marked", name="Marked for Death", duration=-1, icon_color=(200, 30, 60),
    description="Selene will execute this hero next turn. Defend, or stun or kill Selene first.",
)
# Ronan's stance: guards Selene every time and counter-strikes physical attackers.
STATUS_DB["bulwark"] = StatusEffect(
    key="bulwark", name="Bulwark", duration=1, icon_color=(90, 160, 240), stat_mods={"def_": 1.4},
    description="Guards Selene 100% of the time and counter-strikes physical attackers. Spells slip past.",
)
# Each revive leaves Ronan a little stronger (stat_mods are rewritten per revive in twins_fight.py).
STATUS_DB["unyielding"] = StatusEffect(
    key="unyielding", name="Unyielding", duration=-1, icon_color=(230, 190, 80),
    stat_mods={"atk": 1.1, "def_": 1.12},
    description="Every time he rises he comes back harder.",
)

# ----------------------------------------------------------------------
# Boss-only skills. hub_server merges these into the shared SKILLS table.
# ----------------------------------------------------------------------
BOSS_SKILLS: Dict[str, Skill] = {
    # Briarmaw's signature: a long, un-delayable wind-up (the cast bar is the warning) that nearly kills anyone who is not
    # braced. Defend before it lands. Only started when some hero can still act before it resolves (see the rule below).
    "briarmaw_rend": Skill(
        id="briarmaw_rend", name="Rending Strike", mp_cost=7, power=2.6, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="def_down", status_chance=1.0,
        cast_time=8.0, interruptible_by_damage=False, undefended_mult=2.6,
        description="Briarmaw rears back for a killing blow. Defend before it lands, or be torn apart.",
    ),
    # Power bumped ~20% alongside the Champion's stat rebalance above (same reasoning: this rank-1
    # gate fight was tuned before hero power-creep, and needed to catch back up).
    "arena_slam": Skill(
        id="arena_slam", name="Arena Slam", mp_cost=10, power=0.8, kind="physical",
        target=TargetType.ALL_ENEMIES,
        description="Hammers the sand with his shield, sending a shockwave through your whole party.",
    ),
    "shield_bash": Skill(
        id="shield_bash", name="Shield Bash", mp_cost=6, power=1.3, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="stun", status_chance=0.5,
        description="A brutal shield strike that may stun the target.",
    ),
    "gladiators_verdict": Skill(
        id="gladiators_verdict", name="Gladiator's Verdict", mp_cost=14, power=3.1, kind="physical",
        target=TargetType.SINGLE_ENEMY,
        description="A crowd-pleasing finisher on one target. Brace yourself (Defend) when he winds up.",
    ),
    "counter_stance": Skill(
        id="counter_stance", name="Counter Stance", mp_cost=8, power=0.0, kind="status",
        target=TargetType.SELF, status_to_apply="counter", status_chance=1.0,
        description="Raises his shield: physical attackers eat a counter-strike. Use spells, or wait it out.",
    ),
    "crowds_fury": Skill(
        id="crowds_fury", name="Crowd's Fury", mp_cost=8, power=0.0, kind="status",
        target=TargetType.SELF, status_to_apply="atk_up", status_chance=1.0,
        description="Feeds off the roar of the crowd to hit harder.",
    ),
    # --- The Ancient Guardian (Hollow Depths dungeon boss, see WORLD_BOSSES below) ---
    "tremor_slam": Skill(
        id="tremor_slam", name="Tremor Slam", mp_cost=9, power=0.75, kind="physical",
        target=TargetType.ALL_ENEMIES,
        description="Slams the ground hard enough to shake the whole party.",
    ),
    # --- The Unbroken Pair: Ronan ---
    "claymore_sweep": Skill(
        id="claymore_sweep", name="Claymore Sweep", mp_cost=8, power=0.6, kind="physical",
        target=TargetType.ALL_ENEMIES,
        description="A wide sweep of the great blade that catches the whole party.",
    ),
    "crushing_cleave": Skill(
        id="crushing_cleave", name="Crushing Cleave", mp_cost=10, power=1.6, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="def_down", status_chance=0.4,
        description="An overhead cleave that can crack armor.",
    ),
    "stalwart_oath": Skill(
        id="stalwart_oath", name="Stalwart Oath", mp_cost=6, power=0.0, kind="status",
        target=TargetType.SELF, status_to_apply="def_up", status_chance=1.0,
        description="Ronan plants his blade and swears nothing will pass him.",
    ),
    "bloodlust_rampage": Skill(
        id="bloodlust_rampage", name="Bloodlust Rampage", mp_cost=0, power=1.1, kind="physical",
        target=TargetType.ALL_ENEMIES,
        description="Enraged Ronan tears through the whole party.",
    ),
    "executioners_arc": Skill(
        id="executioners_arc", name="Executioner's Arc", mp_cost=0, power=2.8, kind="physical",
        target=TargetType.SINGLE_ENEMY,
        description="A furious killing blow on a single hero.",
    ),
    # --- The Unbroken Pair: Selene ---
    "twin_fangs": Skill(
        id="twin_fangs", name="Twin Fangs", mp_cost=5, power=1.2, kind="physical",
        target=TargetType.SINGLE_ENEMY,
        description="Two quick slashes from her paired blades.",
    ),
    "crimson_flurry": Skill(
        id="crimson_flurry", name="Crimson Flurry", mp_cost=9, power=1.7, kind="physical",
        target=TargetType.SINGLE_ENEMY,
        description="A whirl of red steel on one target.",
    ),
    "rending_edge": Skill(
        id="rending_edge", name="Rending Edge", mp_cost=7, power=0.9, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="poison", status_chance=0.7,
        description="Barbed cuts that leave a bleeding poison.",
    ),
    "assassinate": Skill(
        id="assassinate", name="Assassinate", mp_cost=12, power=2.4, kind="physical",
        target=TargetType.SINGLE_ENEMY,
        description="A precise killing stroke, best used on the weakest hero.",
    ),
    # Scripted-only (never chosen by the AI; game/twins_fight.py forces them): the revive rite.
    "crimson_rebirth": Skill(
        id="crimson_rebirth", name="Crimson Rebirth", mp_cost=0, power=0.0, kind="status",
        target=TargetType.SELF,
        description="Selene begins the rite to raise her fallen brother. She is shielded while she chants.",
    ),
    "rebirth_complete": Skill(
        id="rebirth_complete", name="Rebirth Complete", mp_cost=0, power=0.0, kind="status",
        target=TargetType.SELF,
        description="The rite finishes and Ronan rises.",
    ),
    # Scripted-only: Selene's telegraphed execution (mark now, strike next turn).
    "deaths_mark": Skill(
        id="deaths_mark", name="Death's Mark", mp_cost=0, power=0.0, kind="status",
        target=TargetType.SELF,
        description="Selene marks a hero. Next turn she executes them.",
    ),
    "execution": Skill(
        id="execution", name="Execution", mp_cost=0, power=4.2, kind="physical",
        target=TargetType.SINGLE_ENEMY,
        description="A shadow-step killing stroke on the marked hero. Ronan cannot guard it.",
    ),
    "execution_glancing": Skill(
        id="execution_glancing", name="Execution (Parried)", mp_cost=0, power=0.8, kind="physical",
        target=TargetType.SINGLE_ENEMY,
        description="The marked hero braced: only a glancing cut lands.",
    ),
    # Scripted-only: Ronan's stance (guard 100% + counter until his next turn).
    "bulwark_stance": Skill(
        id="bulwark_stance", name="Bulwark", mp_cost=0, power=0.0, kind="status",
        target=TargetType.SELF, status_to_apply="bulwark", status_chance=1.0,
        description="Plants the claymore: guards Selene every time and counters physical attacks.",
    ),
    # Scripted-only: the Harmony finisher -- both twins strike, one after the other.
    "pair_strike_ronan": Skill(
        id="pair_strike_ronan", name="Unbroken Pair: Bulwark's Sweep", mp_cost=0, power=1.3, kind="physical",
        target=TargetType.ALL_ENEMIES,
        description="Ronan's half of the Unbroken Pair.",
    ),
    "pair_strike_selene": Skill(
        id="pair_strike_selene", name="Unbroken Pair: Crimson Waltz", mp_cost=0, power=1.1, kind="physical",
        target=TargetType.ALL_ENEMIES,
        description="Selene's half of the Unbroken Pair.",
    ),
    # Gained by Ronan the first time he is revived.
    "avenging_slam": Skill(
        id="avenging_slam", name="Avenging Slam", mp_cost=0, power=0.85, kind="physical",
        target=TargetType.ALL_ENEMIES,
        description="Fury for a fallen self: a shockwave across the whole party.",
    ),
}


@dataclass
class BossDef:
    id: str
    name: str
    sprite: dict                 # {"file": path under data/, "scale": x SPRITE_H, "native_left": bool, "idle_only": bool}
    base_stats: Stats            # level-1 block (pre hp_mult)
    growth: Stats
    hp_mult: float               # multiplies the grown max HP -- the "big health pool" knob
    level_offset: int            # boss level = round(avg party level) + this
    skill_ids: List[str]
    persona: str
    script: dict = field(default_factory=dict)
    rewards_first: dict = field(default_factory=dict)    # {"money","gems","xp"} first clear
    rewards_repeat: dict = field(default_factory=dict)   # rematches
    resistances: dict = field(default_factory=dict)
    sprite_color: tuple = (210, 180, 60)
    # Multi-unit bosses (e.g. the Unbroken Pair): one BossMember per enemy on the field. The
    # top-level fields above then describe the "lead" member (used by the debug menu).
    members: List["BossMember"] = field(default_factory=list)
    runner: str = "single"       # "single" -> game/boss_script.BossRunner, "twins" -> game/twins_fight.TwinsRunner
    portrait: str = ""           # path under data/ of the full-body card art (the hub's "next challenger" spot)
    escorts: List[tuple] = field(default_factory=list)   # [(enemy archetype id, level), ...] regular monsters fighting beside a single boss


@dataclass
class BossMember:
    key: str                     # short id, e.g. "ronan"
    name: str
    sprite: dict
    base_stats: Stats
    growth: Stats
    hp_mult: float
    skill_ids: List[str]
    persona: str
    resistances: dict = field(default_factory=dict)
    sprite_color: tuple = (210, 180, 60)


COLOSSEUM_CHAMPION = BossDef(
    id="colosseum_champion_boss",
    name="Colosseum Champion",
    portrait="Bosses/ColliseumChamp/ColliseumChamp-Portrait.webp",
    sprite={"file": "Bosses/ColliseumChamp/ColliseumChamp-Idle.png", "scale": 1.85, "native_left": False, "idle_only": True},
    # Rebalance pass: the Champion (rank 1's gate boss) started feeling too weak after this project's
    # last few sessions of hero power-creep -- every named hero went from a shared, MP-starved 4-skill
    # kit to 3 unique skills plus a 10%/turn MP regen (engine/battle.py's MP_REGEN_FRACTION), and hero
    # rarity/stars (data/hero_rarity.py) can add up to ~1.78x effective stats on top of that. None of
    # that existed when hp_mult=3.0/level_offset=1 were first tuned. Bumped base stats ~20-25%,
    # hp_mult 3.0->4.5 (a much bigger effective HP pool), and level_offset 1->2 (a wider level gap,
    # which also compounds through `growth` every level the party is above rank-1 average) -- first-pass
    # numbers, same "retune by feel" spirit as everything else numeric in this project, not derived from
    # real playtesting data.
    base_stats=Stats(max_hp=250, max_mp=200, atk=34, def_=26, mag=10, res=18, spd=14, luk=14),
    growth=Stats(max_hp=26, max_mp=0, atk=3, def_=2, mag=1, res=1, spd=1, luk=0),
    hp_mult=4.5,
    level_offset=2,
    skill_ids=["shield_bash", "arena_slam", "gladiators_verdict", "crowds_fury", "counter_stance", "power_strike", "sunder"],
    persona=(
        "The undefeated Colosseum Champion: a proud, theatrical veteran who fights for the crowd as much as "
        "for the win. Opens with Crowd's Fury. Uses Shield Bash on whoever looks most dangerous (highest attack "
        "or magic), and Arena Slam when three or more heroes are standing. Counter Stance punishes physical attackers, so he raises it when he expects melee blows. Saves Gladiator's Verdict for a "
        "target that is already hurt. Never wastes a turn defending."
    ),
    script={
        "intro": [
            {"shake": True},
            {"say": ("Colosseum Champion", "So. Fresh blood on the sand.")},
            {"say": ("Colosseum Champion", "Ten thousand throats scream my name. Let's see if any of you are worth remembering.")},
            {"announce": "THE CHAMPION ENTERS"},
        ],
        "triggers": [
            {"id": "first_blood", "when": {"heroes_down_at_least": 1}, "steps": [
                {"say": ("Colosseum Champion", "Hah! Hear that? The crowd loves it.")},
            ]},
            {"id": "counter_tell", "when": {"every_n_rounds": 3, "from": 2}, "once": False, "steps": [
                {"announce": "COUNTER STANCE!"},
                {"log": "The Champion raises his shield -- physical attackers will be countered. Use spells or hold back!"},
                {"force_skill": {"skill": "counter_stance", "target": "all"}},
            ]},
            {"id": "verdict_tell", "when": {"every_n_rounds": 3, "from": 4}, "once": False, "steps": [
                {"announce": "THE CHAMPION RAISES HIS BLADE..."},
                {"log": "The Champion winds up a Gladiator's Verdict -- Defend to survive it!"},
                {"force_skill": {"skill": "gladiators_verdict", "target": "highest_hp", "cast": 5.0, "brace": 2.0, "nopush": True}},
            ]},
            {"id": "phase2", "when": {"hp_below": 0.6}, "steps": [
                {"shake": True},
                {"say": ("Colosseum Champion", "Not bad... not bad at all! But I have not even begun to bleed for them!")},
                {"apply_status": {"target": "boss", "status": "atk_up", "duration": 4}},
                {"flash": "#ff8844"},
                {"announce": "THE CROWD ROARS!"},
                {"force_skill": {"skill": "arena_slam", "target": "all", "cast": 3.0, "brace": 1.5}},
            ]},
            {"id": "phase3", "when": {"hp_below": 0.3}, "steps": [
                {"shake": True},
                {"say": ("Colosseum Champion", "Enough! I am the Champion! I do NOT fall to the likes of you!")},
                {"heal_boss_pct": 0.10},
                {"apply_status": {"target": "boss", "status": "def_up", "duration": 4}},
                {"flash": "#ffdd55"},
                {"announce": "LAST STAND"},
                {"apply_status": {"target": "boss", "status": "haste", "duration": 5}}, {"force_skill": {"skill": "crowds_fury", "target": "all"}},
            ]},
            {"id": "last_hero", "when": {"heroes_alive_at_most": 1, "heroes_down_at_least": 1}, "steps": [
                {"say": ("Colosseum Champion", "One left standing. Make it a good show.")},
            ]},
        ],
        "victory": [
            {"say": ("Colosseum Champion", "...Heh. So this is what it feels like, on the sand.")},
            {"say": ("Colosseum Champion", "Take it. The crowd chose you. Don't let them forget your name.")},
        ],
        "defeat": [
            {"say": ("Colosseum Champion", "Down you go. The crowd will forget you by morning.")},
        ],
    },
    rewards_first={"money": 1500, "gems": 60, "xp": 400},
    rewards_repeat={"money": 300, "gems": 6, "xp": 80},
    sprite_color=(210, 180, 60),
)



# ======================================================================
# THE UNBROKEN PAIR -- Ronan & Selene (boss #2)
# ======================================================================
# Mechanics live in game/twins_fight.py; the numbers that tune them are here.
TWINS_TUNING = {
    "guard_chance": 0.5,        # Ronan takes a single-target physical hit meant for Selene
    "shield_pct": 0.30,         # Selene's channel barrier, as a fraction of HER max HP
    "revive_hp_pct": 0.40,      # Ronan's HP when raised (fraction of his max)
    "max_revives": 2,           # how many times Selene may raise him in one fight
    "enrage_heal_pct": 0.25,    # Ronan's heal when Selene falls
    "enrage_scale": 1.12,       # sprite growth on enrage
    "stagger_turns": 2,         # stun duration on interrupt (2 == she loses her next turn; see tick_statuses)
    # --- Dance of Blades: while Ronan is down Selene acts twice per turn
    "dance_of_blades": True,
    # --- Marked for Death (Selene): mark a hero, execute them on her next turn
    "mark_from_round": 2,
    "mark_every": 3,
    # --- Bulwark (Ronan): 100% guard + counter until his next turn
    "bulwark_from_round": 3,
    "bulwark_every": 4,
    "bulwark_guard_chance": 1.0,
    # --- Twin Harmony: builds while both stand; full = both strike the whole party
    "harmony_max": 100,
    "harmony_per_action": 14,   # per twin action
    "harmony_drain_per_pct": 0.8,   # harmony lost per 1% of a twin's max HP they lose
    "harmony_stagger_loss": 50,
    # --- Escalation: each revive
    "escalate_atk": 0.10,       # Ronan's ATK bonus per revive
    "escalate_def": 0.12,       # Ronan's DEF bonus per revive
    "escalate_barrier": 0.40,   # Selene's next barrier is this much bigger per revive already done
    # --- Linked Strikes: one twin's single-target hit draws a follow-up from the other (once a round)
    "linked_chance": 0.8,
}

_TWIN_DIR = "Bosses/Twins/"


def _pose(file, ref_h, foot, frames=(0, 35), fps=8, loop=True):
    """One sprite-sheet pose. ref_h = the character's standing height in source pixels and
    foot = (x, y) of the feet in the frame (both measured from the art, so every pose lines
    up and stays the same size); frames = inclusive 6x6-grid frame range to play."""
    return {"file": _TWIN_DIR + file, "ref_h": ref_h, "foot": list(foot),
            "frames": list(frames), "fps": fps, "loop": loop}


RONAN_SPRITE = {
    "scale": 1.4, "native_left": False,
    "poses": {
        "Idle": _pose("Ronan-Idle.png", 372, (126, 378), fps=8),
        "Run": _pose("Ronan-Run.png", 380, (167, 417), fps=24),
        "Melee": _pose("Ronan-Attack.png", 317, (162, 472), frames=(8, 27), fps=16, loop=False),
    },
}

SELENE_SPRITE = {
    "scale": 1.15, "native_left": False,
    "poses": {
        "Idle": _pose("Selene-Idle.png", 289, (162, 293), fps=8),
        "Run": _pose("Selene-Run.png", 272, (186, 289), fps=26),
        "Melee": _pose("Selene-Attack.png", 282, (239, 287), frames=(12, 30), fps=18, loop=False),
        # Selene-Barrier.png split in two: the cast start (arms cross, orb kindles, the barrier
        # blooms) plays once, then the chant loops for as long as the barrier holds.
        "CastStart": _pose("Selene-Barrier.png", 289, (184, 361), frames=(0, 23), fps=14, loop=False),
        "CastLoop": _pose("Selene-Barrier.png", 289, (184, 361), frames=(24, 35), fps=10, loop=True),
        # Same sheet, the pre-bloom chanting frames: what she looks like once her barrier is broken.
        "CastBroken": _pose("Selene-Barrier.png", 289, (184, 361), frames=(14, 20), fps=8, loop=True),
    },
}

RONAN_MEMBER = BossMember(
    key="ronan", name="Ronan", sprite=RONAN_SPRITE,
    base_stats=Stats(max_hp=280, max_mp=120, atk=18, def_=22, mag=6, res=12, spd=9, luk=8),
    growth=Stats(max_hp=22, max_mp=0, atk=1, def_=2, mag=0, res=1, spd=1, luk=0),
    hp_mult=2.0,
    skill_ids=["stalwart_oath", "claymore_sweep", "crushing_cleave", "power_strike"],
    persona=(
        "Ronan, the Unbroken Bulwark: Selene's older twin, a huge, stoic claymore knight whose whole life is "
        "keeping his sister alive. He is a tank, not a glass cannon. Opens with Stalwart Oath. Uses Claymore "
        "Sweep when three or more heroes are standing, and Crushing Cleave on whichever hero is doing the most "
        "damage. He automatically takes some physical blows meant for Selene, so he never needs to defend. "
        "When Selene falls he goes berserk."
    ),
    sprite_color=(150, 40, 50),
)

SELENE_MEMBER = BossMember(
    key="selene", name="Selene", sprite=SELENE_SPRITE,
    base_stats=Stats(max_hp=170, max_mp=110, atk=22, def_=10, mag=14, res=18, spd=20, luk=22),
    growth=Stats(max_hp=14, max_mp=0, atk=1, def_=1, mag=0, res=1, spd=1, luk=1),
    hp_mult=2.0,
    skill_ids=["twin_fangs", "rending_edge", "crimson_flurry", "assassinate"],
    persona=(
        "Selene, the Crimson Blade: Ronan's younger twin, an elegant, lethal dual-blade assassin. She is fragile "
        "and fast and goes for the kill: Assassinate on the lowest-HP hero, Rending Edge to poison a tough "
        "target, Twin Fangs or Crimson Flurry otherwise. Her brother shields her from many physical attacks. "
        "If Ronan falls she interrupts her offense to revive him (the game handles that automatically)."
    ),
    sprite_color=(200, 50, 90),
)

_TWIN_SCRIPT = {
    "intro": [
        {"shake": True},
        {"say": ("Selene", "Two of us, and a whole arena of you. How generous.")},
        {"say": ("Ronan", "Stay behind me, Selene. Nobody touches you.")},
        {"announce": "THE UNBROKEN PAIR"},
    ],
    "triggers": [
        {"id": "hero_falls", "when": {"heroes_down_at_least": 1}, "steps": [
            {"say": ("Selene", "One down. Don't stop, brother.")},
        ]},
    ],
    # Named moments fired by game/twins_fight.py.  {"once": True} events only ever fire once.
    "events": {
        "guard_first": {"once": True, "steps": [
            {"say": ("Ronan", "You'll have to come through me.")},
        ]},
        "ronan_down": {"once": True, "steps": [
            {"say": ("Selene", "Ronan! No -- hold on. Hold ON.")},
        ]},
        "cast_start": {"once": False, "steps": [
            {"announce": "SELENE CHANTS..."},
            {"log": "Break her barrier, then hurt her to interrupt the revival!"},
        ]},
        "shield_break": {"once": False, "steps": [
            {"flash": "#bfe8ff"},
            {"shake": True},
        ]},
        "interrupted": {"once": False, "steps": [
            {"flash": "#ffffff"},
            {"announce": "REVIVAL INTERRUPTED!"},
        ]},
        "revive_done": {"once": False, "steps": [
            {"flash": "#ff6a5a"},
            {"announce": "RONAN RISES"},
            {"say": ("Ronan", "...Selene. I heard you. I'm here.")},
        ]},
        "revive_done_repeat": {"once": False, "steps": [
            {"flash": "#ff6a5a"},
            {"announce": "RONAN RISES AGAIN"},
        ]},
        "dance_start": {"once": True, "steps": [
            {"flash": "#ff3a6a"},
            {"say": ("Selene", "Without him to hold me back... I am so much faster.")},
            {"announce": "DANCE OF BLADES"},
        ]},
        "mark_first": {"once": True, "steps": [
            {"say": ("Selene", "That one. Remember their face, brother.")},
        ]},
        "bulwark_first": {"once": True, "steps": [
            {"say": ("Ronan", "Come on, then. Break yourselves on me.")},
        ]},
        "harmony_full": {"once": True, "steps": [
            {"say": ("Selene", "Ready, Ronan?")},
            {"say": ("Ronan", "Always.")},
        ]},
        "selene_down": {"once": True, "steps": [
            {"shake": True},
            {"say": ("Selene", "Ronan... finish it...")},
        ]},
        "enrage": {"once": True, "steps": [
            {"flash": "#ff1a1a"},
            {"shake": True},
            {"say": ("Ronan", "SELENE!")},
            {"say": ("Ronan", "You will not leave this sand. NONE of you.")},
            {"announce": "BLOODLUST"},
        ]},
    },
    "victory": [
        {"say": ("Ronan", "...Sister. I'm coming.")},
        {"say": ("Selene", "The Unbroken Pair... broken at last. Well fought.")},
    ],
    "defeat": [
        {"say": ("Selene", "Stay down. We are not done here.")},
        {"say": ("Ronan", "Come, Selene. The crowd wants more.")},
    ],
}

UNBROKEN_PAIR = BossDef(
    id="unbroken_pair_boss",
    name="The Unbroken Pair",
    portrait="Bosses/Twins/Twins-Portrait.png",
    # Top-level fields describe the lead member (Ronan) for the debug menu; the fight itself
    # is built from `members`.
    sprite=RONAN_SPRITE, base_stats=RONAN_MEMBER.base_stats, growth=RONAN_MEMBER.growth,
    hp_mult=RONAN_MEMBER.hp_mult,
    level_offset=2,
    skill_ids=RONAN_MEMBER.skill_ids + SELENE_MEMBER.skill_ids,
    persona="The Unbroken Pair: Ronan the Bulwark and Selene the Crimson Blade.",
    script=_TWIN_SCRIPT,
    rewards_first={"money": 3000, "gems": 120, "xp": 900},
    rewards_repeat={"money": 600, "gems": 12, "xp": 180},
    sprite_color=(180, 45, 70),
    members=[RONAN_MEMBER, SELENE_MEMBER],
    runner="twins",
)

BOSSES: Dict[str, BossDef] = {COLOSSEUM_CHAMPION.id: COLOSSEUM_CHAMPION, UNBROKEN_PAIR.id: UNBROKEN_PAIR}


# ======================================================================
# THE ANCIENT GUARDIAN -- Hollow Depths dungeon boss (game/world.py's overworld, not the Colosseum
# ladder). Kept in a separate WORLD_BOSSES dict rather than added to BOSSES/RANK_BOSSES above: this
# fight is reached by walking up to the guardian NPC in data/maps/dungeon_hollow.json and talking to
# it, not by renown/rank (game/renown.py never sees this id, so it can't affect rank-gate derivation
# or show up in the Colosseum's boss card/pool), though it uses the exact same BossDef/BossRunner
# machinery -- hub_server.py's run_battle treats "a boss NPC talked to in the overworld" and "a rank
# challenge started from the hub" as the same kind of fight once a BossDef is in hand.
# ======================================================================
ANCIENT_GUARDIAN = BossDef(
    id="ancient_guardian_boss",
    name="Ancient Guardian",
    # Static (single-image) art: "static": True makes the battle view fit the image to its alpha bounds.
    sprite={"file": "Bosses/AncientGuardian/Ancient-Guardian.png", "scale": 1.5, "native_left": False, "idle_only": True, "static": True},
    # Deliberately lighter than the rank bosses above (Champion: 250 HP base x4.5; Pair: similar) --
    # this is an EARLY dungeon encounter a fresh party can stumble into, not a renown-gated wall.
    base_stats=Stats(max_hp=150, max_mp=100, atk=22, def_=20, mag=8, res=14, spd=9, luk=8),
    growth=Stats(max_hp=16, max_mp=0, atk=2, def_=2, mag=1, res=1, spd=1, luk=0),
    hp_mult=2.2,
    level_offset=1,
    skill_ids=["power_strike", "sunder", "tremor_slam", "counter_stance"],
    persona=(
        "An ancient stone guardian sealed in the Hollow Depths: patient, implacable, speaks rarely and "
        "in short sentences. Opens with Sunder to weaken whoever looks strongest. Uses Power Strike on "
        "the lowest-HP hero to finish them. Raises Counter Stance once wounded rather than trading "
        "blows carelessly, and unleashes Tremor Slam when badly hurt as a last stand."
    ),
    script={
        "intro": [
            {"shake": True},
            {"say": ("Ancient Guardian", "You've come far enough, traveler.")},
            {"say": ("Ancient Guardian", "Prove your party is worth the rest of this dungeon!")},
            {"announce": "THE GUARDIAN AWAKENS"},
        ],
        "triggers": [
            {"id": "ward", "when": {"hp_below": 0.6}, "steps": [
                {"announce": "ANCIENT WARD"},
                {"log": "The Guardian raises an ancient ward -- physical attackers will be countered."},
                {"force_skill": {"skill": "counter_stance", "target": "all"}},
            ]},
            {"id": "tremor", "when": {"hp_below": 0.3}, "steps": [
                {"shake": True},
                {"say": ("Ancient Guardian", "Enough. The Hollow will remember this.")},
                {"flash": "#8899aa"},
                {"announce": "TREMOR SLAM"},
                {"apply_status": {"target": "boss", "status": "haste", "duration": 5}}, {"force_skill": {"skill": "tremor_slam", "target": "all", "cast": 4.0, "brace": 1.8, "nopush": True}},
            ]},
        ],
        "victory": [
            {"say": ("Ancient Guardian", "...Pass, then. You have earned it.")},
        ],
        "defeat": [
            {"say": ("Ancient Guardian", "The Hollow keeps its secrets a while longer.")},
        ],
    },
    rewards_first={"money": 400, "gems": 15, "xp": 120},
    rewards_repeat={"money": 120, "gems": 3, "xp": 40},
    sprite_color=(150, 150, 165),
)


# ======================================================================
# THE DROWNED SOVEREIGN -- final boss of the island dungeon (html_hub/3d/dungeon.json). Started from a
# 3D hub scene's `battle` action with boss "drowned_sovereign_boss" (hub_server.py /api/world/hub_battle);
# same machinery as the Ancient Guardian above. Tougher than the Guardian: a mid-game wall, not a
# starter fight.
# ======================================================================
DROWNED_SOVEREIGN = BossDef(
    id="drowned_sovereign_boss",
    name="Drowned Sovereign",

    sprite={
        "file": "Bosses/DrownedSovereign/Drowned_Sovereign.png",
        "scale": 1.6,
        "native_left": False,
        "idle_only": True,
        "static": True
    },

    # --- BASE STATS ---
    base_stats=Stats(max_hp=190, max_mp=120, atk=25, def_=22, mag=12, res=18, spd=10, luk=10),
    growth=Stats(max_hp=18, max_mp=0, atk=2, def_=2, mag=1, res=2, spd=1, luk=0),

    hp_mult=2.5,
    level_offset=2,

    # --- SKILLS ---
    skill_ids=[
        "power_strike",   # Finisher on weakest hero (usually healer)
        "sunder",         # Break the frontline (melee fighter)
        "tremor_slam",    # Collapse phase AoE
        "arena_slam"      # Tide cycle AoE
    ],

    # --- PERSONA ---
    persona=(
        "The long-dead king of the island, bound to his flooded throne room: grave, courtly, bitterly "
        "proud. He breaks the frontline with Sunder, punishes the weak with Power Strike, and unleashes "
        "the tide itself when the hall stirs. When wounded, he raises his royal guard, and near the end, "
        "brings the whole sunken hall down with Tremor Slam."
    ),

    # --- SCRIPT ---
    script={

        # ---------------------------------------------------------
        # INTRO
        # ---------------------------------------------------------
        "intro": [
            {"shake": True},
            {"say": ("Drowned Sovereign", "Who wakes the king beneath the tide?")},
            {"say": ("Drowned Sovereign", "Kneel, or sink with the rest of my court.")},
            {"announce": "THE DROWNED SOVEREIGN RISES"}
        ],

        # ---------------------------------------------------------
        # TRIGGERS
        # ---------------------------------------------------------
        "triggers": [

            # -----------------------------------------------------
            # TIDE ECHO — Passive environmental reaction
            # -----------------------------------------------------
            {
                "id": "tide_echo",
                "when": {"always": True},
                "once": False,
                "steps": [
                    {"on_skill": {
                        "sunder":       {"vfx": "water_ripple", "sfx": "surge_low"},
                        "power_strike": {"vfx": "pillar_groan", "sfx": "stone_shift"},
                        "arena_slam":   {"vfx": "wave_crash", "sfx": "heavy_surge"},
                        "tremor_slam":  {"vfx": "ceiling_crack", "sfx": "deep_rumble"},
                        "counter_stance": {"vfx": "water_shield", "sfx": "royal_echo"}
                    }}
                ]
            },

            # -----------------------------------------------------
            # TIDE SURGE — Arena Slam every 4 rounds
            # -----------------------------------------------------
            {
                "id": "tide_surge",
                "when": {"every_n_rounds": 4, "from": 3},
                "once": False,
                "steps": [
                    {"announce": "THE TIDE SURGES"},
                    {"log": "Black water pours across the floor — the Sovereign winds up a crushing blow."},
                    {"force_skill": {"skill": "arena_slam", "target": "all", "cast": 3.5, "brace": 1.5}}
                ]
            },

            # -----------------------------------------------------
            # ROYAL WARD — HP < 60% → ATK Up + Counter Stance
            # -----------------------------------------------------
            {
                "id": "royal_ward",
                "when": {"hp_below": 0.6},
                "steps": [
                    {"shake": True},
                    {"say": ("Drowned Sovereign", "My crown has outlived a hundred challengers.")},
                    {"apply_status": {"target": "boss", "status": "atk_up", "duration": 4}},
                    {"force_skill": {"skill": "counter_stance", "target": "all"}}
                ]
            },

            # -----------------------------------------------------
            # LAST STAND — HP < 30% → Heal + DEF Up + Tremor Slam
            # -----------------------------------------------------
            {
                "id": "last_stand",
                "when": {"hp_below": 0.3},
                "steps": [
                    {"shake": True},
                    {"flash": "#223a55"},
                    {"say": ("Drowned Sovereign", "Then let the sea take the hall — and you with it!")},
                    {"heal_boss_pct": 0.08},
                    {"apply_status": {"target": "boss", "status": "def_up", "duration": 4}},
                    {"announce": "THE HALL COLLAPSES"},
                    {"apply_status": {"target": "boss", "status": "haste", "duration": 5}}, {"force_skill": {"skill": "tremor_slam", "target": "all", "cast": 4.5, "brace": 2.0, "nopush": True}}
                ]
            }
        ],

        # ---------------------------------------------------------
        # VICTORY / DEFEAT
        # ---------------------------------------------------------
        "victory": [
            {"say": ("Drowned Sovereign", "...The tide... lets me go. Take the crown, hero.")}
        ],

        "defeat": [
            {"say": ("Drowned Sovereign", "The sea keeps what it takes.")}
        ]
    },

    # --- REWARDS ---
    rewards_first={"money": 900, "gems": 30, "xp": 260},
    rewards_repeat={"money": 220, "gems": 6, "xp": 70},

    sprite_color=(70, 110, 150)
)



VAULT_WARDEN = BossDef(
    id="vault_warden_boss",
    name="Vault Warden",
    sprite={"file": "Bosses/VaultWarden/Vault-Warden.png", "scale": 1.6, "native_left": False, "idle_only": True, "static": True},
    base_stats=Stats(max_hp=210, max_mp=140, atk=24, def_=24, mag=14, res=20, spd=12, luk=10),   # balance pass: was atk 29 / mag 18 / hp_mult 3.2
    growth=Stats(max_hp=20, max_mp=0, atk=2, def_=2, mag=2, res=2, spd=1, luk=0),
    hp_mult=2.0,
    level_offset=2,
    skill_ids=["power_strike", "sunder", "shield_bash", "arena_slam", "tremor_slam"],
    persona=(
        "An ancient guardian construct that keeps the Shard: flat, mechanical, relentless. Opens with Sunder on the "
        "hardest-hitting hero, uses Shield Bash on whoever looks most dangerous, Power Strike on the weakest, and "
        "Arena Slam when several heroes are healthy. When damaged it overloads and brings the whole core down with Tremor Slam."
    ),
    script={
        "intro": [
            {"shake": True},
            {"say": ("Vault Warden", "THE SHARD IS NOT TO BE CARRIED. THE SHARD IS NOT TO BE TOUCHED.")},
            {"say": ("Vault Warden", "VISITORS WITHOUT A KEY ARE TO BE UNMADE.")},
            {"announce": "THE VAULT WARDEN ACTIVATES"},
        ],
        "triggers": [
            {"id": "pulse", "when": {"every_n_rounds": 4, "from": 3}, "once": False, "steps": [
                {"announce": "CORE PULSE"},
                {"log": "The Shard flares -- the Warden channels a crushing pulse through the floor."},
                {"force_skill": {"skill": "arena_slam", "target": "all", "cast": 3.5, "brace": 1.5}},
            ]},
            {"id": "overclock", "when": {"hp_below": 0.6}, "steps": [
                {"shake": True},
                {"say": ("Vault Warden", "THREAT LEVEL RAISED. SAFEGUARDS RELEASED.")},
                {"apply_status": {"target": "boss", "status": "atk_up", "duration": 4}},
            ]},
            {"id": "meltdown", "when": {"hp_below": 0.3}, "steps": [
                {"shake": True},
                {"flash": "#3a2266"},
                {"say": ("Vault Warden", "CORE BREACH. IF THE SHARD IS LOST, THE VAULT IS LOST WITH IT.")},
                {"heal_boss_pct": 0.08},
                {"apply_status": {"target": "boss", "status": "def_up", "duration": 4}},
                {"announce": "THE CORE DESTABILISES"},
                {"apply_status": {"target": "boss", "status": "haste", "duration": 5}}, {"force_skill": {"skill": "tremor_slam", "target": "all", "cast": 4.5, "brace": 2.0, "nopush": True}},
            ]},
        ],
        "victory": [
            {"say": ("Vault Warden", "...GUARD DUTY... CONCLUDED... THE SHARD... IS YOURS TO ANSWER FOR.")},
        ],
        "defeat": [
            {"say": ("Vault Warden", "UNMADE. RESUME POST.")},
        ],
    },
    rewards_first={"money": 1400, "gems": 45, "xp": 420},
    rewards_repeat={"money": 320, "gems": 9, "xp": 110},
    sprite_color=(140, 100, 200),
)


def _guardian(id_, name, sprite_file, scale, stats, growth, hp_mult, lvoff, skills, persona, intro, triggers, victory, defeat, rf, rr, color):
    return BossDef(id=id_, name=name, sprite={"file": sprite_file, "scale": scale, "native_left": False, "idle_only": True, "static": True},
                   base_stats=stats, growth=growth, hp_mult=hp_mult, level_offset=lvoff, skill_ids=skills, persona=persona,
                   script={"intro": intro, "triggers": triggers, "victory": victory, "defeat": defeat},
                   rewards_first=rf, rewards_repeat=rr, sprite_color=color)


VAULT_SENTINEL = _guardian(
    "vault_sentinel_boss", "Vault Sentinel", "Bosses/VaultSentinel/Vault-Sentinel.png", 1.5,
    Stats(max_hp=170, max_mp=100, atk=24, def_=26, mag=12, res=16, spd=9, luk=8),
    Stats(max_hp=16, max_mp=0, atk=2, def_=2, mag=1, res=1, spd=1, luk=0), 2.5, 0,
    ["shield_bash", "power_strike", "iron_stance", "ground_slam", "self_repair"],
    "A sealed-gate construct: methodical and defensive. Shield Bash on the most dangerous hero, Power Strike on the weakest, Iron Stance when hurt, Ground Slam when the party is healthy.",
    [{"shake": True}, {"say": ("Vault Sentinel", "EAST GATE PROTOCOL ENGAGED. INTRUDERS WILL BE HELD.")}, {"announce": "THE VAULT SENTINEL ACTIVATES"}],
    [{"id": "lockdown", "when": {"every_n_rounds": 3, "from": 3}, "once": False, "steps": [
        {"announce": "LOCKDOWN"}, {"log": "The Sentinel slams its shield into the floor and the gate-lattice shudders."},
        {"force_skill": {"skill": "ground_slam", "target": "all", "cast": 3.0, "brace": 1.5}}]},
     {"id": "bulwark", "when": {"hp_below": 0.5}, "steps": [
        {"shake": True}, {"say": ("Vault Sentinel", "SHIELD ARRAY AT FULL OUTPUT.")},
        {"apply_status": {"target": "boss", "status": "def_up", "duration": 4}}]},
     {"id": "repairs", "when": {"hp_below": 0.25}, "steps": [
        {"say": ("Vault Sentinel", "INTEGRITY CRITICAL. EMERGENCY REPAIR.")}, {"heal_boss_pct": 0.08},
        {"announce": "THE SENTINEL REPAIRS ITSELF"}]}],
    [{"say": ("Vault Sentinel", "GATE... SEALED. THE INTRUDERS... REMAIN.")}],
    [{"say": ("Vault Sentinel", "...GATE... OPEN. PROCEED... TO YOUR ENDING.")}],
    {"money": 520, "gems": 14, "xp": 170}, {"money": 150, "gems": 3, "xp": 50}, (90, 150, 210))

PHASE_STALKER = _guardian(
    "phase_stalker_boss", "Phase Stalker", "Bosses/PhaseStalker/Phase-Stalker.png", 1.4,
    Stats(max_hp=140, max_mp=110, atk=27, def_=15, mag=16, res=18, spd=17, luk=14),
    Stats(max_hp=14, max_mp=0, atk=3, def_=1, mag=1, res=1, spd=2, luk=1), 2.4, 0,
    ["rending_strike", "piercing_shot", "poison_dart", "reckless_swing", "quick_shot"],
    "A fast rift predator that flickers in and out of phase. Poisons the healthiest hero, Rending Strike on the weakest, Reckless Swing when it smells blood, quick Quick Shots to finish wounded heroes.",
    [{"shake": True}, {"say": ("Phase Stalker", "Two steps behind you. Always. Every step.")}, {"announce": "THE PHASE STALKER SLIPS IN"}],
    [{"id": "phase", "when": {"every_n_rounds": 4, "from": 2}, "once": False, "steps": [
        {"announce": "PHASE SHIFT"}, {"log": "The Stalker blinks out of sight and strikes from every angle."},
        {"force_skill": {"skill": "poison_dart", "target": "all"}}]},
     {"id": "frenzy", "when": {"hp_below": 0.55}, "steps": [
        {"shake": True}, {"say": ("Phase Stalker", "Hold still. It is easier if you hold still.")},
        {"apply_status": {"target": "boss", "status": "haste", "duration": 4}}, {"apply_status": {"target": "boss", "status": "atk_up", "duration": 4}}]},
     {"id": "desperate", "when": {"hp_below": 0.25}, "steps": [
        {"flash": "#2a1a55"}, {"say": ("Phase Stalker", "The rift takes me back. It takes you too.")},
        {"apply_status": {"target": "boss", "status": "atk_up", "duration": 3}},
        {"force_skill": {"skill": "reckless_swing", "target": "lowest_hp"}}]}],
    [{"say": ("Phase Stalker", "No one leaves. No one... ever leaves...")}],
    [{"say": ("Phase Stalker", "Back... to the other side. Tell it I was loyal.")}],
    {"money": 600, "gems": 16, "xp": 200}, {"money": 170, "gems": 4, "xp": 60}, (170, 110, 230))

RIFT_COLOSSUS = _guardian(
    "rift_colossus_boss", "Rift Colossus", "Bosses/RiftColossus/Rift-Colossus.png", 1.7,
    Stats(max_hp=230, max_mp=120, atk=22, def_=22, mag=17, res=14, spd=8, luk=8),   # balance pass: was atk 28 / mag 22 / hp_mult 2.8
    Stats(max_hp=22, max_mp=0, atk=2, def_=2, mag=2, res=1, spd=1, luk=0), 1.6, 0,
    ["crushing_blow", "ground_slam", "warcry", "firestorm", "power_strike"],
    "A towering core-forged giant. Slow and brutal: Crushing Blow on the strongest hero, Power Strike on the weakest, Ground Slam against healthy parties, and Firestorm when the core overheats.",
    [{"shake": True}, {"say": ("Rift Colossus", "THE CORE IS HEAVY. THE CORE IS HOT. THE CORE IS MINE.")}, {"announce": "THE RIFT COLOSSUS AWAKENS"}],
    [{"id": "meltcore", "when": {"every_n_rounds": 4, "from": 3}, "once": False, "steps": [
        {"announce": "CORE SURGE"}, {"log": "The Colossus's chest-core flares white-hot."},
        {"force_skill": {"skill": "firestorm", "target": "all", "cast": 4.0, "brace": 1.6}}]},
     {"id": "warcry", "when": {"hp_below": 0.6}, "steps": [
        {"shake": True}, {"say": ("Rift Colossus", "GRIND THEM TO SLAG.")},
        {"apply_status": {"target": "boss", "status": "atk_up", "duration": 4}}]},
     {"id": "overload", "when": {"hp_below": 0.3}, "steps": [
        {"shake": True}, {"flash": "#5a2a10"}, {"say": ("Rift Colossus", "CORE... OVERLOAD. TAKE IT ALL WITH ME.")},
        {"heal_boss_pct": 0.06}, {"announce": "THE CORE OVERLOADS"},
        {"apply_status": {"target": "boss", "status": "haste", "duration": 4}}, {"force_skill": {"skill": "ground_slam", "target": "all", "cast": 5.0, "brace": 2.0, "nopush": True}}]}],
    [{"say": ("Rift Colossus", "THE CORE... ENDURES. YOU DO NOT.")}],
    [{"say": ("Rift Colossus", "...CORE... COOLING. THE WAY... IS OPEN.")}],
    {"money": 720, "gems": 20, "xp": 260}, {"money": 200, "gems": 5, "xp": 75}, (230, 140, 70))



BRIARMAW = _guardian(
    "briarmaw_boss", "Briarmaw", "Bosses/Briarmaw/Briarmaw.png", 1.6,

    # --- BASE STATS ---
    Stats(max_hp=150, max_mp=90, atk=21, def_=17, mag=10, res=13, spd=11, luk=8),
    Stats(max_hp=15, max_mp=0, atk=2, def_=2, mag=1, res=1, spd=1, luk=0),

    2.3, 1,

    # --- SKILL LIST ---
    [
        "briarmaw_rend",    # Long wind-up, lethal unless you Defend (used when a hero can still react)
        "poison_dart",      # Used when player HP > 80% or player cured poison
        "power_strike",     # Used when player HP < 40%
        "counter_stance",   # Triggered when Briarmaw takes >15% HP in one turn
        "ground_slam"       # Every 3 rounds (thorns rise)
    ],

    # --- LORE ---
    "The awakened heart of the Whispering Wood: slow to anger, brutal once roused. "
    "It punishes recklessness, adapts to healing, and unleashes the forest’s wrath "
    "in predictable cycles. The ground itself reacts to its every move.",

    # --- INTRO EVENTS ---
    [
        {"shake": True},
        {"say": ("Briarmaw", "...ROOTS... REMEMBER... EVERY FOOTSTEP...")},
        {"announce": "BRIARMAW AWAKENS"}
    ],

    # --- BEHAVIOR EVENTS ---
    [
        # ---------------------------------------------------------
        # ROOT PULSE — Passive environmental reaction
        # ---------------------------------------------------------
        {
            "id": "root_pulse",
            "when": {"always": True},
            "once": False,
            "steps": [
                {"on_skill": {
                    "briarmaw_rend": {"vfx": "leaves_scatter", "sfx": "forest_rustle"},
                    "poison_dart": {"vfx": "green_mist", "sfx": "toxin_hiss"},
                    "power_strike": {"vfx": "bark_crack", "sfx": "heavy_wood_impact"},
                    "counter_stance": {"vfx": "roots_coil", "sfx": "low_creak"},
                    "ground_slam": {"vfx": "earth_shake", "sfx": "deep_thud"},
                    "regrow": {"vfx": "forest_glow", "sfx": "soft_pulse"}
                }}
            ]
        },

        # ---------------------------------------------------------
        # THORNS RISE — Every 3 rounds → Ground Slam
        # ---------------------------------------------------------
        {
            "id": "thorns",
            "when": {"every_n_rounds": 3, "from": 3},
            "once": False,
            "steps": [
                {"announce": "THE THORNS RISE"},
                {"log": "Black brambles burst from the earth and lash across the lone challenger."},
                {"force_skill": {"skill": "ground_slam", "target": "player", "cast": 3.0, "brace": 1.5}},
                {"apply_status": {"target": "boss", "status": "def_up", "duration": 2}},   # 2 = survives the tick at the start of its own turn
                {"cleanse_status": {"target": "boss", "status": "poison"}}
            ]
        },

        # ---------------------------------------------------------
        # BARK THICKENS — HP < 50%
        # ---------------------------------------------------------
        {
            "id": "bark",
            "when": {"hp_below": 0.5},
            "steps": [
                {"shake": True},
                {"say": ("Briarmaw", "BARK... THICKENS. YOU... CANNOT... CUT THE OAK.")},
                {"apply_status": {"target": "boss", "status": "def_up", "duration": 4}}
            ]
        },

        # ---------------------------------------------------------
        # REGROW — HP < 25%
        # ---------------------------------------------------------
        {
            "id": "regrow",
            "when": {"hp_below": 0.25},
            "steps": [
                {"say": ("Briarmaw", "THE WOOD... GIVES... ME... STRENGTH.")},
                {"heal_boss_pct": 0.08},
                {"apply_status": {"target": "boss", "status": "haste", "duration": 4}}, {"announce": "BRIARMAW REGROWS"},
                {"flag": "force_power_strike_next_turn"}
            ]
        }
    ],

    # --- DEFEAT EVENTS ---
    [
        {"say": ("Briarmaw", "...THE SONG... IS OVER. LEAVE... THE SEEDLINGS... ALONE.")}
    ],

    # --- VICTORY EVENTS ---
    [
        {"say": ("Briarmaw", "...ROOT... AND... LEAF... REMAIN. YOU... DO NOT.")}
    ],

    # --- REWARDS ---
    {"money": 700, "gems": 18, "xp": 220},
    {"money": 180, "gems": 4, "xp": 60},

    (80, 170, 90)
)

# Briarmaw's skill choices (the comments on its skill list above), as rules the BossRunner checks on each of its turns
# (game/boss_script.py _rule_action); anything not matched here falls back to the normal AI. Thorns / Bark / Regrow stay as triggers.
BRIARMAW.script["rules"] = [
    {"id": "regrow_strike", "skill": "power_strike", "target": "lowest_hp", "when": {"flag": "force_power_strike_next_turn"}, "clear_flag": True},
    {"id": "root_counter", "skill": "counter_stance", "target": "self", "when": {"boss_lost_pct_above": 0.15, "boss_lacks_status": "counter"}, "cooldown": 4},
    {"id": "finish", "skill": "power_strike", "target": "lowest_hp", "when": {"target_hp_below": 0.4}},
    {"id": "toxin", "skill": "poison_dart", "target": "highest_hp", "when": {"target_hp_above": 0.8, "target_lacks_status": "poison"}},
    {"id": "rend", "skill": "briarmaw_rend", "target": "highest_hp", "when": {"target_hp_above": 0.6, "target_eta_below": 3.0}, "cooldown": 2},
]

# First-boss pointers: Kael's thoughts as the fight goes (each once, only when Kael is in the party). `if_party` / `party_has` keep
# them out of fights without him; the triggers are checked after every action (game/boss_script.py).
BRIARMAW.script["intro"] = list(BRIARMAW.script["intro"]) + [
    {"say": ("Kael", "(A guardian this size won't fall to one lucky swing. Watch what it does each round, and keep my HP up.)"), "if_party": "Kael"}]
_K = lambda text: [{"say": ("Kael", "(" + text + ")")}]
BRIARMAW.script["triggers"] = list(BRIARMAW.script["triggers"]) + [
    {"id": "tip_poison", "when": {"any_hero_has_status": "poison", "party_has": "Kael"}, "steps": _K(
        "Poison. It eats a little HP at the start of every turn until it wears off. Nothing to cure it, so I have to out-heal it.")},
    {"id": "tip_thorns", "when": {"every_n_rounds": 3, "from": 3, "party_has": "Kael"}, "steps": _K(
        "The ground itself is lashing out! Every third round the thorns rise and I can't dodge them. Best to heal up before they land.")},
    {"id": "teach_counter", "when": {"round_at_least": 4}, "steps": [{"force_skill": {"skill": "counter_stance", "target": "all"}}]},
    {"id": "tip_counter", "when": {"boss_has_status": "counter", "party_has": "Kael"}, "steps": _K(
        "He's bracing, roots coiling around him. If I swing now he'll throw the hit right back. Better to Defend and wait it out.")},
    {"id": "tip_countered", "when": {"flag": "countered", "party_has": "Kael"}, "steps": _K(
        "Argh! I walked right into that. Next time I wait until the stance drops before I attack.")},
    {"id": "tip_low_hp", "when": {"any_hero_hp_below": 0.4, "party_has": "Kael"}, "steps": _K(
        "I'm in trouble. He goes for the kill when I'm low. Potion first, then back to the fight.")},
    {"id": "tip_bark", "when": {"hp_below": 0.5, "party_has": "Kael"}, "steps": _K(
        "His bark is thickening. My hits will land softer for a while, but he's hurting. Keep at it.")},
    {"id": "tip_regrow", "when": {"hp_below": 0.25, "party_has": "Kael"}, "steps": _K(
        "He's healing himself! Don't let up. Finish it before he can regrow.")},
]

# ======================================================================
# CHIEFTAIN SKRAAG -- mini boss of the goblin camp in the Whispering Wood (html_hub/3d/forest.json, NPC "skraag").
# A level-2 brute with two level-1 Goblin Skirmishers at his side ("escorts": plain monsters built by hub_server's
# _build_boss_setup). Light script: a war-cry buff, a telegraphed Bone Smash you can Defend against, a rage phase.
# ======================================================================
SKRAAG = _guardian(
    "skraag_boss", "Chieftain Skraag", "Bosses/Skraag/gen-31b029ed-6c8d-40a7-b315-9c4f53079aeb.png", 1.5,
    Stats(max_hp=85, max_mp=80, atk=17, def_=10, mag=4, res=7, spd=9, luk=8),
    Stats(max_hp=12, max_mp=0, atk=2, def_=1, mag=0, res=1, spd=1, luk=0), 2.0, 0,
    ["power_strike", "crushing_blow", "reckless_swing", "warcry"],
    "A loud, greedy goblin chieftain who hits like a cart. Power Strike on the weakest hero, Reckless Swing once he is hurt, a roaring Warcry to start, and a slow Bone Smash he telegraphs to crush whoever does not Defend.",
    [{"shake": True}, {"say": ("Chieftain Skraag", "Skraag is BIGGEST! Skraag takes your shiny sticks, and your shiny Seal!")},
     {"announce": "CHIEFTAIN SKRAAG"}],
    [{"id": "war_cry", "when": {"round_at_least": 2}, "steps": [
        {"announce": "WAR CRY"}, {"say": ("Chieftain Skraag", "Faster, boys! Skraag wants SHINIES!")},
        {"apply_status": {"target": "boss", "status": "atk_up", "duration": 4}}]},
     {"id": "bone_smash", "when": {"every_n_rounds": 4, "from": 3}, "once": False, "steps": [
        {"announce": "BONE SMASH"}, {"log": "Skraag hoists his bone club high over his head..."},
        {"force_skill": {"skill": "crushing_blow", "target": "highest_hp", "cast": 2.5, "brace": 1.2}}]},
     {"id": "tip_smash", "when": {"every_n_rounds": 4, "from": 3, "party_has": "Kael"}, "steps": [
        {"say": ("Kael", "(He's winding up a big one! Defend now or it'll flatten somebody!)")}]},
     {"id": "rage", "when": {"hp_below": 0.5}, "steps": [
        {"shake": True}, {"say": ("Chieftain Skraag", "Ow! Skraag is MAD now!")},
        {"apply_status": {"target": "boss", "status": "atk_up", "duration": 5}}]},
     {"id": "tip_rage", "when": {"hp_below": 0.5, "party_has": "Kael"}, "steps": [
        {"say": ("Kael", "(He's wounded and angry. Keep hitting, and don't let anyone drop low.)")}]}],
    [{"say": ("Chieftain Skraag", "Skraag... smash... Two-legs... too sharp...")}],
    [{"say": ("Chieftain Skraag", "Hee hee! Nobody beats Skraag! Not ever!")}],
    {"money": 120, "gems": 3, "xp": 45}, {"money": 40, "gems": 1, "xp": 15}, (70, 150, 60))
SKRAAG.escorts = [("goblin_skirmisher", 1), ("goblin_skirmisher", 1)]

# ======================================================================
# THE RIFT HARBINGER -- chapter 4 boss (the Shattered Reach, html_hub/3d/make_reach.py). The thing that
# has been dragging fighters through the doors. Uses the Null Reaper's static art until it gets its own.
# ======================================================================
RIFT_HARBINGER = _guardian(
    "rift_harbinger_boss", "Rift Harbinger", "Battlers/Enemies/Null-Reaper.png", 1.8,
    Stats(max_hp=190, max_mp=140, atk=20, def_=18, mag=22, res=18, spd=13, luk=10),
    Stats(max_hp=18, max_mp=0, atk=2, def_=1, mag=2, res=2, spd=1, luk=0), 2.0, 1,
    ["void_lance", "shadow_bolt", "life_drain", "sunder", "weaken", "crushing_blow"],
    "A patient collector of fighters, cold and exact. Void Lance on the weakest hero, Shadow Bolt on the strongest caster, Sunder on whoever carries the most armour, Weaken before a big hit, Life Drain when its own HP is low, and Crushing Blow to finish.",
    [{"shake": True}, {"say": ("Rift Harbinger", "Three doors I opened. Three fighters I drew through. You are the first to walk back to the hand that held them.")}, {"announce": "THE RIFT HARBINGER STIRS"}],
    [{"id": "harvest", "when": {"every_n_rounds": 4, "from": 3}, "once": False, "steps": [
        {"announce": "HARVEST"}, {"log": "The Harbinger raises a hand and the air itself tears toward the weakest of you."},
        {"force_skill": {"skill": "void_lance", "target": "lowest_hp", "cast": 3.0, "brace": 1.8, "nopush": True}}]},
     {"id": "unmake", "when": {"hp_below": 0.55}, "steps": [
        {"shake": True}, {"say": ("Rift Harbinger", "Enough. Let me show you how the doors are made.")},
        {"apply_status": {"target": "boss", "status": "atk_up", "duration": 4}}]},
     {"id": "last_door", "when": {"hp_below": 0.25}, "steps": [
        {"flash": "#1a0a3a"}, {"say": ("Rift Harbinger", "The last door opens inward. Come. Come and see.")},
        {"heal_boss_pct": 0.06}, {"announce": "THE LAST DOOR OPENS"},
        {"apply_status": {"target": "boss", "status": "haste", "duration": 4}}, {"force_skill": {"skill": "shadow_bolt", "target": "lowest_hp", "cast": 4.0, "brace": 1.8, "nopush": True}}]}],
    [{"say": ("Rift Harbinger", "...The hand... was never mine. Find the one who... holds... the doors...")}],
    [{"say": ("Rift Harbinger", "Another one for the Reach. Sleep.")}],
    {"money": 1000, "gems": 26, "xp": 340}, {"money": 280, "gems": 7, "xp": 100}, (150, 60, 200))


WORLD_BOSSES: Dict[str, BossDef] = {BRIARMAW.id: BRIARMAW, ANCIENT_GUARDIAN.id: ANCIENT_GUARDIAN, DROWNED_SOVEREIGN.id: DROWNED_SOVEREIGN, VAULT_WARDEN.id: VAULT_WARDEN,
                                VAULT_SENTINEL.id: VAULT_SENTINEL, PHASE_STALKER.id: PHASE_STALKER, RIFT_COLOSSUS.id: RIFT_COLOSSUS,
                                RIFT_HARBINGER.id: RIFT_HARBINGER, SKRAAG.id: SKRAAG}


# Every boss fights at a SET level, whatever the party's level (Andrew: "bosses should be a set level"). This overrides
# the old "average party level + level_offset" rule for both Colosseum rank bosses and world/dungeon bosses -- and any
# `level` a 3D scene passes. A boss not listed here still falls back to party average + level_offset.
# Retune by feel: just change the numbers.
BOSS_FIXED_LEVELS: Dict[str, int] = {
    "skraag_boss": 2,               # goblin camp, Whispering Wood (with two level-1 skirmishers)
    "briarmaw_boss": 5,             # Whispering Wood
    "ancient_guardian_boss": 8,     # island ruins cave
    "drowned_sovereign_boss": 12,   # Hollow Cave
    "vault_sentinel_boss": 14,      # Shard Vault, west
    "phase_stalker_boss": 15,       # Shard Vault, east
    "colosseum_champion_boss": 16,  # Colosseum rank 1 gate
    "rift_colossus_boss": 17,       # Shard Vault, north
    "vault_warden_boss": 19,        # Shard Vault, final
    "unbroken_pair_boss": 20,       # Colosseum rank 2 gate
    "rift_harbinger_boss": 24,      # Shattered Reach
}


def fixed_level_for(boss_id: str):
    """The boss's set level, or None when it has none (then party average + level_offset applies)."""
    return BOSS_FIXED_LEVELS.get(boss_id)

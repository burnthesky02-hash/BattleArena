"""Battle formations: front/middle/rear row assignment for both sides of a
fight, and everything derived from it.

Andrew's request: set each party member's row on Party Select (front/mid/
rear), with a live preview; front row takes less damage, mid row deals
more, rear row deals and takes less but heals for more; and a melee
attacker can't target past an occupied front row (ranged/magical attackers
can always reach anyone). The exact numbers and "should enemies use this
too" were both confirmed via AskUserQuestion: the milder of two tuning
presets below, and yes -- formations apply symmetrically to BOTH sides, so
enemies (data/enemy_pool.py's EnemyArchetype, hero rivals, bosses) are
auto-assigned a row from their own melee/ranged nature rather than only
ever existing on the player's side (see auto_formation). That keeps the
mechanic meaningful in both directions: your melee heroes can be blocked
by an enemy's front line exactly the same way theirs can be blocked by
yours.

"Melee" vs "ranged" is a property of the ATTACKER (their class/archetype),
not of any one skill they use -- engine/combatant.py's Combatant.is_melee,
set once at construction from data/classes.py's ClassArchetype.is_melee
(owned heroes, hero rivals) or data/enemy_pool.py's EnemyArchetype.is_melee
(monsters), or hardcoded True for scripted bosses (every boss kit in
data/bosses.py is physical/melee-flavored). This is deliberately separate
from hub_server.py's `_is_melee_action`, which classifies one ACTION
(physical vs magical skill.kind) purely to pick a battle animation --
ranged_dps's bow skills are "physical" for damage-formula purposes but the
class itself is NOT melee for targeting purposes, so conflating the two
would incorrectly let a ranged_dps's arrows be blocked by an enemy's front
line.
"""
from typing import Dict, List, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from engine.combatant import Combatant

FORMATIONS: tuple = ("front", "middle", "rear")
DEFAULT_FORMATION = "middle"
# The battle grid (both html_battle/index.html's columnLayout and html_hub/party.html's preview)
# is a fixed 2x3 layout -- 3 rows, 2 set spots each -- so no row can ever hold more than this many
# combatants on either side, whether hand-picked (Party Select) or auto-assigned (enemy squads).
ROW_CAPACITY = 2

# Milder preset (Andrew picked this over a punchier one via AskUserQuestion). Fractions -- 0.15 = 15%.
DAMAGE_TAKEN_MODIFIER: Dict[str, float] = {"front": -0.15, "middle": 0.0, "rear": -0.15}
DAMAGE_DEALT_MODIFIER: Dict[str, float] = {"front": 0.0, "middle": 0.10, "rear": -0.15}
# Healing a rear-row combatant CASTS is stronger (parallels "deals less damage" -- both describe what
# the rear-row unit itself puts out, not what they receive). A rear-row healer is safer AND more
# potent; a rear-row damage-dealer is safer but weaker.
HEALING_GIVEN_MODIFIER: Dict[str, float] = {"front": 0.0, "middle": 0.0, "rear": 0.20}


def clamp_formation(value: str) -> str:
    return value if value in FORMATIONS else DEFAULT_FORMATION


def damage_dealt_multiplier(row: str) -> float:
    return 1.0 + DAMAGE_DEALT_MODIFIER.get(row, 0.0)


def damage_taken_multiplier(row: str) -> float:
    return 1.0 + DAMAGE_TAKEN_MODIFIER.get(row, 0.0)


def healing_given_multiplier(row: str) -> float:
    return 1.0 + HEALING_GIVEN_MODIFIER.get(row, 0.0)


def auto_formation(is_melee: bool) -> str:
    """Default row for a single Combatant that never went through Party Select (a solo boss, or any
    other one-off construction) -- melee-flavored fighters plant themselves front-line, everyone
    else (casters, archers, healers) hangs back. For a full squad of more than one enemy, use
    assign_squad_formations instead: it respects ROW_CAPACITY, which a blind front/rear split on
    each unit individually cannot (four melee monsters would all say "front")."""
    return "front" if is_melee else "rear"


def assign_squad_formations(is_melee_flags: Sequence[bool]) -> List[str]:
    """Assigns a full enemy squad's rows in one pass, respecting ROW_CAPACITY (2 per row) on the
    fixed 2x3 battle grid -- something auto_formation can't do since it only ever sees one unit at
    a time. Each member prefers auto_formation's own front/rear split, but overflows into whichever
    row still has room (front/middle/rear order for a melee overflow, rear/middle/front for a
    ranged one) once its preferred row is full, so e.g. a squad of four melee monsters ends up 2
    front / 2 middle instead of illegally stacking 4 into front. Mirrors the same grid enemies are
    actually drawn on (html_battle/index.html's columnLayout) and the same cap Party Select enforces
    on the player's own side (game/party.py's confirm_party), so both sides of a fight play by the
    same formation rules."""
    counts = {row: 0 for row in FORMATIONS}
    assigned: List[str] = []
    for is_melee in is_melee_flags:
        preferred = auto_formation(is_melee)
        order = FORMATIONS if is_melee else tuple(reversed(FORMATIONS))
        row = next((r for r in order if counts[r] < ROW_CAPACITY), preferred)
        counts[row] += 1
        assigned.append(row)
    return assigned


def reachable_targets(actor: "Combatant", enemy_side: Sequence["Combatant"]) -> List["Combatant"]:
    """Which of `enemy_side` (expected already alive-only) a single-target action from `actor` can
    actually reach. A ranged/magical actor (is_melee=False) always reaches anyone. A melee actor is
    blocked by an occupied front row: if any front-row member of enemy_side is alive, only front-row
    members are reachable; once the front row is empty, melee reaches whoever's left."""
    pool = list(enemy_side)
    if not getattr(actor, "is_melee", True):
        return pool
    front = [c for c in pool if getattr(c, "formation", DEFAULT_FORMATION) == "front"]
    return front if front else pool

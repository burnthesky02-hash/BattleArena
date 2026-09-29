"""Renown and rank: the Colosseum's ladder.

  * Every player has a RANK (starts at 1) and a RENOWN meter for that rank (starts at 0).
  * Winning a fight earns renown -- more for harder fights (the same difficulty/team-size
    multiplier the money/gems/XP rewards use, times the win-streak chain bonus). Losing a fight
    costs renown (losing an easy fight stings a bit more than losing a hard one). Fleeing is free.
  * Once the meter reaches the rank's gate you may CHALLENGE that rank's boss. Beating it promotes
    you: rank +1 and the meter starts over. Losing to a boss costs a chunk of renown, which can drop
    you back below the gate.
  * The renown meter can overflow the gate by 50% as a buffer against a bad loss.
  * Every boss you have beaten (the bosses of all the ranks below your current one) joins the
    random encounter pool.

Pure logic over PlayerState -- no UI, no networking. All the tunable numbers are the constants at the
top of this file.
"""
import random
from typing import List, Optional

# The boss you must beat to LEAVE each rank: index 0 -> rank 1's boss, index 1 -> rank 2's boss, ...
RANK_BOSSES: List[str] = ["colosseum_champion_boss", "unbroken_pair_boss"]

# Display names, one per rank (rank 1 is index 0). Ranks past the list fall back to "Rank N".
RANK_NAMES: List[str] = ["Rookie", "Contender", "Veteran"]

# Renown needed to challenge the boss of rank N (dict key = the rank you are currently in).
RENOWN_GATE = {1: 100, 2: 250}
DEFAULT_GATE_STEP = 150          # ranks with no explicit gate: previous gate + this

RENOWN_OVERFLOW = 1.5            # meter cap = gate * this (a buffer against a bad loss)

WIN_BASE = 12                    # renown for a win at multiplier 1.0
LOSS_BASE = 8                    # renown lost for a defeat at multiplier 1.0
LOSS_MULT_MIN, LOSS_MULT_MAX = 0.75, 1.5   # losing an EASY fight (low mult) stings more, a hard one less
BOSS_LOSS = 20                   # any defeat against a boss (challenge or encounter)
BOSS_ENCOUNTER_WIN_MULT = 3.0    # a random boss encounter counts as a very hard fight for renown

BOSS_ENCOUNTER_CHANCE = 0.12     # chance a random fight is a boss from the pool (when the pool isn't empty)


# ----------------------------------------------------------------------
# Lookups
# ----------------------------------------------------------------------
def rank_name(rank: int) -> str:
    return RANK_NAMES[rank - 1] if 1 <= rank <= len(RANK_NAMES) else f"Rank {rank}"


def boss_id_for_rank(rank: int) -> Optional[str]:
    """The boss you face to leave `rank`, or None if there is no boss for it (yet)."""
    return RANK_BOSSES[rank - 1] if 1 <= rank <= len(RANK_BOSSES) else None


def gate_for_rank(rank: int) -> int:
    if rank in RENOWN_GATE:
        return RENOWN_GATE[rank]
    last = max(RENOWN_GATE)
    return RENOWN_GATE[last] + DEFAULT_GATE_STEP * (rank - last)


def renown_cap(rank: int) -> int:
    return round(gate_for_rank(rank) * RENOWN_OVERFLOW)


def has_next_boss(state) -> bool:
    return boss_id_for_rank(state.rank) is not None


def can_challenge(state) -> bool:
    return has_next_boss(state) and state.renown >= gate_for_rank(state.rank)


def pool_boss_ids(state) -> List[str]:
    """Bosses that may show up as random encounters: those of every rank you have already cleared."""
    return list(RANK_BOSSES[:max(0, state.rank - 1)])


def rank_for_cleared(cleared_bosses) -> int:
    """Rank implied by a list of cleared boss ids (used to migrate saves from before ranks existed):
    one rank per rank-boss cleared in order."""
    rank = 1
    for boss_id in RANK_BOSSES:
        if boss_id in cleared_bosses:
            rank += 1
        else:
            break
    return rank


# ----------------------------------------------------------------------
# Renown deltas
# ----------------------------------------------------------------------
def renown_for_win(mult: float) -> int:
    """Renown for a win. `mult` is the fight's difficulty multiplier (see game/rewards.reward_multiplier
    x the win-streak chain factor); at least 1 renown is always awarded."""
    return max(1, round(WIN_BASE * max(0.1, mult)))


def renown_for_loss(mult: float) -> int:
    """Renown LOST (returned positive) for a defeat in an ordinary fight."""
    scale = min(LOSS_MULT_MAX, max(LOSS_MULT_MIN, 1.0 / max(0.1, mult)))
    return max(1, round(LOSS_BASE * scale))


def apply_renown(state, delta: int) -> int:
    """Adds `delta` (may be negative) to the meter, clamped to [0, cap]. Returns the ACTUAL change."""
    before = state.renown
    state.renown = max(0, min(renown_cap(state.rank), before + delta))
    return state.renown - before


def settle_fight(state, *, won: bool, fled: bool = False, mult: float = 1.0,
                 boss_id: Optional[str] = None, rank_challenge: bool = False) -> dict:
    """Applies the renown consequences of a finished (non-debug) fight to `state` and returns a summary
    for the UI: {delta, total, rank, rank_name, rank_up, gate, can_challenge}.

    `rank_challenge` is True only for the fight the player started from the hub's boss card; winning
    it (against that rank's boss) promotes them."""
    rank_before = state.rank
    delta = 0
    rank_up = False
    if fled:
        pass
    elif won:
        if boss_id is not None:
            mult = BOSS_ENCOUNTER_WIN_MULT
        delta = apply_renown(state, renown_for_win(mult))
        if rank_challenge and boss_id is not None and boss_id == boss_id_for_rank(state.rank):
            state.rank += 1
            state.renown = 0
            rank_up = True
    else:
        loss = BOSS_LOSS if boss_id is not None else renown_for_loss(mult)
        delta = apply_renown(state, -loss)
    return {
        "delta": delta, "total": state.renown, "rank": state.rank, "rank_name": rank_name(state.rank),
        "rank_before": rank_before, "rank_up": rank_up,
        "gate": gate_for_rank(state.rank) if has_next_boss(state) else None,
        "can_challenge": can_challenge(state),
    }


def pick_pool_boss(state, rng=None) -> Optional[str]:
    """Rolls whether this random fight is a boss encounter; returns the boss id or None."""
    pool = pool_boss_ids(state)
    if not pool:
        return None
    r = rng or random
    if r.random() >= BOSS_ENCOUNTER_CHANCE:
        return None
    return r.choice(pool) if hasattr(r, "choice") else pool[0]

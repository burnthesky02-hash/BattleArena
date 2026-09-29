"""Battle party selection: which up-to-4 owned heroes actually fight a
battle (see main.py's run_game_loop and ui/pygame_ui.py's/ui/text_ui.py's
show_party_select). Everything here is a plain function over PlayerState,
the same shape as game/shop.py and game/summon.py, so both UIs drive the
exact same rules.

Before this pass the whole roster fought every battle. Andrew asked for a
4-hero cap with an explicit pre-battle selection screen instead.
game/battle_setup.py's build_battle already just takes "whichever
PlayerCharacters you hand it" -- it never assumed "the whole roster" -- so
this module's only job is deciding *which* PlayerCharacters that ends up
being; build_battle itself needed no changes.
"""
from typing import Dict, List, Optional, Sequence, Tuple

import engine.formation as formation
from game.player_state import PlayerState
from game.roster import PlayerCharacter

MAX_PARTY_SIZE = 4
MIN_PARTY_SIZE = 1


def default_party_ids(player_state: PlayerState) -> List[str]:
    """The party a fresh trip to the selection screen should start
    pre-checked with: the previous confirmed selection
    (player_state.active_party), filtered down to characters still actually
    owned AND not currently wounded (game/legacy.py's apply_wound_penalty --
    a wounded hero can't fight until they've recovered or been healed, so
    they're never pre-checked here even if they were in the last confirmed
    party), or -- the first time, or if that filtered list comes up empty --
    the first MAX_PARTY_SIZE fit-to-fight characters in roster order."""
    owned_ids = {c.id for c in player_state.characters if not c.wounded_runs_remaining}
    kept = [cid for cid in player_state.active_party if cid in owned_ids]
    if kept:
        return kept[:MAX_PARTY_SIZE]
    return [c.id for c in player_state.characters if not c.wounded_runs_remaining][:MAX_PARTY_SIZE]


def active_party_characters(player_state: PlayerState) -> List[PlayerCharacter]:
    """Resolves whichever ids represent the *current* battle lineup --
    player_state.active_party if it's set, else the same fallback
    default_party_ids would pre-check on a first-ever trip to Party Select
    -- into actual PlayerCharacter objects, in roster order, silently
    dropping any stale/unknown ids (same defensive spirit as confirm_party)
    AND anyone currently wounded (defensive -- confirm_party already keeps a
    wounded hero out of active_party in the first place, and apply_wound_penalty
    pulls them back out the moment they're wounded, but a hero could in
    principle still be wounded on the very run they're carried out on, so
    this is the last line of defense against a wounded hero ever actually
    fighting).

    Added so the Colosseum hub can show "who's actually going to fight"
    instead of the entire owned roster -- Andrew asked for the hub to stop
    listing every collected hero once that list could run well past the
    4-hero party cap. The full roster is still browsable in full on the
    Heroes screen; this is just the hub's summary line."""
    ids = player_state.active_party or default_party_ids(player_state)
    id_set = set(ids)
    return [c for c in player_state.characters if c.id in id_set and not c.wounded_runs_remaining]


def toggle_member(selected_ids: Sequence[str], character_id: str) -> Tuple[List[str], bool]:
    """Pure toggle helper for the selection screen's click handler: removes
    character_id if it's already selected, otherwise adds it if there's
    room. Returns (new_selected_ids, changed) -- changed is False only when
    trying to add past MAX_PARTY_SIZE, so a UI can flash "party full"
    instead of silently doing nothing."""
    selected = list(selected_ids)
    if character_id in selected:
        selected.remove(character_id)
        return selected, True
    if len(selected) >= MAX_PARTY_SIZE:
        return selected, False
    selected.append(character_id)
    return selected, True


def confirm_party(player_state: PlayerState,
                   selected_ids: Sequence[str],
                   formations: Optional[Dict[str, str]] = None) -> Tuple[bool, str, Optional[List[PlayerCharacter]]]:
    """Validates the selection (between MIN_PARTY_SIZE and MAX_PARTY_SIZE,
    all real owned, not-currently-wounded characters), saves it as
    player_state.active_party for next time, and returns the resolved
    PlayerCharacter list in roster order -- what main.py hands to
    run_one_battle/build_battle. On failure (empty selection, somehow more
    than MAX_PARTY_SIZE, or a selection that's entirely wounded heroes)
    nothing is changed and the 3rd element is None. A wounded id is
    silently dropped rather than rejecting the whole request -- same
    defensive spirit as dropping an unknown id.

    `formations` (optional): character_id -> "front"/"middle"/"rear", the
    row each confirmed hero was assigned on the Party Select screen. Only
    ids that end up in the confirmed party are applied; anyone not present
    in `formations` keeps whatever formation they already had
    (PlayerCharacter.formation persists between battles -- see
    game/roster.py). Invalid values are silently clamped rather than
    rejecting the whole request, same defensive spirit as everything else
    here. The battle grid is a fixed 2x3 layout (engine/formation.py's
    ROW_CAPACITY), so no row can hold more than 2 -- a request that would
    overfill one (the party.html row picker is expected to block this
    client-side, but a stale client or a direct API call could still send
    it) silently bumps the overflowing hero into whichever row still has
    room instead of rejecting the whole confirm, same as an invalid row
    value."""
    owned = {c.id for c in player_state.characters}
    wounded = {c.id for c in player_state.characters if c.wounded_runs_remaining}
    ids = [cid for cid in dict.fromkeys(selected_ids) if cid in owned and cid not in wounded]
    if not (MIN_PARTY_SIZE <= len(ids) <= MAX_PARTY_SIZE):
        return False, f"Choose between {MIN_PARTY_SIZE} and {MAX_PARTY_SIZE} fit-to-fight heroes to enter battle.", None
    player_state.active_party = ids
    id_set = set(ids)
    party = [c for c in player_state.characters if c.id in id_set]
    if formations:
        counts: Dict[str, int] = {row: 0 for row in formation.FORMATIONS}
        for c in party:
            if c.id not in formations:
                counts[c.formation] = counts.get(c.formation, 0) + 1
        for c in party:
            if c.id not in formations:
                continue
            want = formation.clamp_formation(formations[c.id])
            if counts.get(want, 0) >= formation.ROW_CAPACITY:
                want = next((r for r in formation.FORMATIONS if counts.get(r, 0) < formation.ROW_CAPACITY), want)
            counts[want] = counts.get(want, 0) + 1
            c.formation = want
    return True, f"Party of {len(party)} confirmed.", party

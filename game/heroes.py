"""Heroes-page logic: spending a hero's banked shards (granted by duplicate
summons -- see game/summon.py) to star-upgrade them. Equip/unequip for the
Heroes page reuses game/shop.py's equip_from_stash/unequip unchanged --
Andrew's AskUserQuestion answer had the new Heroes page take over Shop's
old "Gear" tab as the one place to manage a character's gear, not
reinvent the equip logic itself -- so this module only owns the one thing
that's genuinely new here: shards -> stars.
"""
from typing import Dict, Optional, Tuple

from data.hero_rarity import MAX_STARS, shard_cost_for_next_star
from data.hero_skills import skill_ids_for
from engine.skills import MAX_SKILL_RANK, Skill
from game.player_state import PlayerState
from game.roster import PlayerCharacter


def _find_character(player_state: PlayerState, character_id: str) -> Optional[PlayerCharacter]:
    return next((c for c in player_state.characters if c.id == character_id), None)


def upgrade_star(player_state: PlayerState, character_id: str) -> Tuple[bool, str]:
    """Spends exactly one star's worth of shards on this hero, if they have
    enough and aren't already at MAX_STARS. Never partially spends -- either
    the full cost comes off character.shards and character.stars goes up by
    1, or nothing changes at all."""
    character = _find_character(player_state, character_id)
    if character is None:
        return False, "Unknown character."
    if character.stars >= MAX_STARS:
        return False, f"{character.name} is already at max stars ({MAX_STARS})."
    cost = shard_cost_for_next_star(character.rarity, character.stars)
    if character.shards < cost:
        return False, (f"Not enough shards to upgrade {character.name} "
                        f"(need {cost}, have {character.shards}).")
    character.shards -= cost
    character.stars += 1
    return True, f"{character.name} reached {character.stars} stars!"


def upgrade_skill_rank(player_state: PlayerState, character_id: str, skill_id: str,
                        skills_db: Optional[Dict[str, Skill]] = None) -> Tuple[bool, str]:
    """Spends exactly one talent point (game/roster.py's PlayerCharacter.talent_points_available,
    earned every data/leveling.py's TALENT_POINT_INTERVAL levels) to raise skill_id one rank, if this
    hero actually knows that skill, isn't already at MAX_SKILL_RANK on it, and has an unspent point.
    Never partially spends -- either the rank goes up by exactly 1, or nothing changes. `skills_db` is
    optional and only used to put the skill's real name in the message instead of its raw id."""
    character = _find_character(player_state, character_id)
    if character is None:
        return False, "Unknown character."
    if skill_id not in skill_ids_for(character.name, character.class_id):
        return False, f"{character.name} doesn't know that skill."
    current = character.skill_rank(skill_id)
    if current >= MAX_SKILL_RANK:
        return False, f"That skill is already at max rank ({MAX_SKILL_RANK})."
    if character.talent_points_available() < 1:
        return False, f"{character.name} has no talent points to spend."
    character.skill_ranks[skill_id] = current + 1
    label = skills_db[skill_id].name if skills_db and skill_id in skills_db else skill_id
    return True, f"{character.name}'s {label} is now rank {current + 1}."

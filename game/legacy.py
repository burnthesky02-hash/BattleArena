"""Legacy items: what a hero leaves behind when they're deliberately retired.

A hero is NEVER lost just from being downed in battle any more -- being
downed, win or lose, only costs them a stint on the bench (see
apply_wound_penalty/heal_wound below). The only way a hero is ever
permanently removed from the roster is a deliberate, player-initiated
sacrifice (sacrifice_hero), and only once they've maxed out their own
rarity's level cap (data/hero_rarity.py's level_cap_for -- common=10 up
through mythic=50). Sacrificing a maxed hero mints a LegacyItem: a stash
item any surviving hero can equip for a flat percentage stat bonus themed
to the retired hero's class (a melee fighter's legacy boosts ATK, a tank's
boosts DEF/HP, etc -- see LEGACY_CLASS_BONUSES), scaled by the retired
hero's own rarity using the exact same common->mythic curve
data/hero_rarity.py already uses for everything else (rarity_multiplier)
-- not a new curve invented for this. A legacy's power is fixed by class +
rarity alone, same as always -- level/stars still don't factor in, since
reaching the level cap is now just a precondition, not a variable.

Every hero has legacy slots of their own to equip these into -- 3 base,
plus one more per rarity step above common (a mythic hero has 3+4=7).
Unlike equipment, legacy items aren't typed to a slot -- any legacy item
can go in any of a hero's legacy slots, so equipping is just "is there
room," not "does this fit here."

--- The death penalty ---

A hero who's still downed (0 HP) at the moment the player actually leaves
the Colosseum (an explicit "leave"/cash-out, or the run simply ending on a
loss) is carried out wounded: they're benched (pulled out of the active
party, and unselectable on Party Select -- see game/party.py) for
WOUND_RUNS future runs, counted down once per run regardless of whether
they were even in that run's party (see tick_wounds). Nothing else about
them changes -- no XP loss, no gear loss, no roster removal. Paying gold
(heal_wound) clears the wound immediately instead of waiting it out. This
mirrors the win-streak's existing "the same Combatant objects fight every
round, so HP carries over" behavior (see hub_server.py's run_battle) -- a
downed hero is just a hero at 0 HP like any other status, until the run
actually ends; only then does it cost them anything at all.
"""
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from data.hero_rarity import HERO_RARITIES, HERO_RARITY_LABEL, rarity_multiplier
from engine.combatant import Combatant
from engine.equipment import STAT_LABEL
from game.player_state import PlayerState
from game.roster import PlayerCharacter

# Every hero gets this many legacy slots no matter their own rarity, plus
# one more per rarity step above common (see legacy_slots_for below).
LEGACY_BASE_SLOTS = 3

# Per-class base bonus (fraction, e.g. 0.08 = +8%) at COMMON rarity -- scaled
# up per the retired hero's actual rarity by rarity_multiplier below, the
# exact same 1.00/1.08/1.16/1.25/1.35 curve owned-hero stats and hero-rival
# enemy stats already scale by. A class with two stats gets two smaller
# bonuses rather than one big one, so no single legacy item trivializes a
# whole build.
LEGACY_CLASS_BONUSES: Dict[str, Dict[str, float]] = {
    "tank": {"def_": 0.06, "max_hp": 0.05},
    "melee_dps": {"atk": 0.08},
    "ranged_dps": {"atk": 0.05, "spd": 0.04},
    "mage": {"mag": 0.08},
    "support": {"res": 0.05, "max_mp": 0.05},
}

# How many future runs a wounded hero sits out (see apply_wound_penalty), counted down once per run
# by tick_wounds regardless of whether they were actually in that run's party.
WOUND_RUNS = 2

# Gold cost to clear a wound immediately instead of waiting it out (heal_wound), scaled by the
# wounded hero's own rarity -- same "rarer hero, bigger number" shape as SHARD_COST_FOR_STAR.
WOUND_HEAL_COST: Dict[str, int] = {
    "common": 50,
    "rare": 80,
    "epic": 120,
    "legendary": 180,
    "mythic": 260,
}
assert set(WOUND_HEAL_COST) == set(HERO_RARITIES)


@dataclass
class LegacyItem:
    instance_id: str
    hero_name: str
    hero_class_id: str
    rarity: str                                   # the retired hero's rarity when they were sacrificed
    bonuses: Dict[str, float] = field(default_factory=dict)   # stat name -> fractional bonus (0.08 = +8%)

    @property
    def name(self) -> str:
        return f"{self.hero_name}'s Legacy"

    def bonus_text(self) -> str:
        if not self.bonuses:
            return "(no bonus)"
        return ", ".join(f"+{round(v * 100)}% {STAT_LABEL.get(k, k.upper())}" for k, v in self.bonuses.items())


def legacy_slots_for(character: PlayerCharacter) -> int:
    """3 base slots, plus one more per rarity step above common (common=0
    extra ... mythic=4 extra, so 3/4/5/6/7 across the five tiers)."""
    idx = HERO_RARITIES.index(character.rarity) if character.rarity in HERO_RARITIES else 0
    return LEGACY_BASE_SLOTS + idx


def create_legacy_item(character: PlayerCharacter) -> LegacyItem:
    """Builds the legacy item a retired hero leaves behind, from their class
    and rarity alone -- deliberately NOT their level/stars. Level doesn't
    even vary any more at the point this is called (sacrifice_hero only
    allows this once a hero is already at their own level_cap), so this
    would be redundant to factor in even if it weren't already the
    confirmed design."""
    base = LEGACY_CLASS_BONUSES.get(character.class_id, {})
    mult = rarity_multiplier(character.rarity)
    bonuses = {stat: round(pct * mult, 4) for stat, pct in base.items()}
    return LegacyItem(
        instance_id=uuid.uuid4().hex[:12],
        hero_name=character.name,
        hero_class_id=character.class_id,
        rarity=character.rarity,
        bonuses=bonuses,
    )


def apply_legacy_bonuses(stats, equipped_legacy_ids: Sequence[str], legacy_db: Dict[str, LegacyItem]) -> None:
    """Mutates `stats` in place, applying every equipped legacy item's %
    bonuses on top of whatever's already there (growth + stars + equipment)
    -- so a legacy item makes the wearer's existing gear hit harder too,
    rather than being computed off some separate unbuffed baseline."""
    for legacy_id in equipped_legacy_ids:
        item = legacy_db.get(legacy_id)
        if not item:
            continue
        for stat_name, pct in item.bonuses.items():
            if hasattr(stats, stat_name):
                current = getattr(stats, stat_name)
                setattr(stats, stat_name, round(current * (1 + pct)))


def _find_character(player_state: PlayerState, character_id: str) -> Optional[PlayerCharacter]:
    return next((c for c in player_state.characters if c.id == character_id), None)


def equip_legacy(player_state: PlayerState, character_id: str, legacy_id: str) -> Tuple[bool, str]:
    character = _find_character(player_state, character_id)
    if character is None:
        return False, "Unknown character."
    item = player_state.legacy_instances.get(legacy_id)
    if item is None:
        return False, "That legacy item doesn't exist."
    if legacy_id not in player_state.legacy_stash:
        return False, f"You don't own {item.name}."
    if legacy_id in character.equipped_legacies:
        return False, f"{item.name} is already equipped on {character.name}."
    cap = legacy_slots_for(character)
    if len(character.equipped_legacies) >= cap:
        return False, f"{character.name} has no free legacy slots ({cap} max)."
    character.equipped_legacies.append(legacy_id)
    player_state.take_legacy_from_stash(legacy_id)
    return True, f"Equipped {item.name} on {character.name}."


def unequip_legacy(player_state: PlayerState, character_id: str, legacy_id: str) -> Tuple[bool, str]:
    character = _find_character(player_state, character_id)
    if character is None:
        return False, "Unknown character."
    if legacy_id not in character.equipped_legacies:
        return False, "That's not equipped there."
    character.equipped_legacies.remove(legacy_id)
    player_state.return_legacy_to_stash(legacy_id)
    item = player_state.legacy_instances.get(legacy_id)
    name = item.name if item else legacy_id
    return True, f"Unequipped {name} from {character.name}."


def sacrifice_hero(player_state: PlayerState, character_id: str) -> Tuple[bool, str]:
    """The only way a hero is ever permanently lost now: a deliberate,
    player-initiated retirement, allowed only once they've reached their
    OWN level_cap (data/hero_rarity.py's level_cap_for -- see
    PlayerCharacter.is_level_maxed). Mints the LegacyItem they leave behind
    (create_legacy_item) into the stash, and -- since this is a voluntary
    retirement, not a battlefield loss -- returns whatever gear and legacy
    items they had equipped to the stash rather than discarding it."""
    character = _find_character(player_state, character_id)
    if character is None:
        return False, "Unknown character."
    if not character.is_level_maxed:
        return False, f"{character.name} must reach level {character.level_cap} before they can be sacrificed."
    if character.is_wounded:
        return False, f"{character.name} is wounded and needs to recover before being sacrificed."
    if len(player_state.characters) <= 1:
        return False, "You can't sacrifice your only hero."

    for item_id in character.equipped.values():
        if item_id:
            player_state.return_to_stash(item_id)
    for legacy_id in list(character.equipped_legacies):
        player_state.return_legacy_to_stash(legacy_id)

    legacy = create_legacy_item(character)
    player_state.add_legacy_to_stash(legacy)

    player_state.characters.remove(character)
    if character.id in player_state.active_party:
        player_state.active_party.remove(character.id)

    rarity_label = HERO_RARITY_LABEL.get(character.rarity, character.rarity.capitalize())
    return True, f"{character.name} steps down, passing on their [{rarity_label}] legacy."


def heal_wound(player_state: PlayerState, character_id: str) -> Tuple[bool, str]:
    """Pays WOUND_HEAL_COST (by the hero's own rarity) to clear a wound immediately instead of
    waiting out tick_wounds."""
    character = _find_character(player_state, character_id)
    if character is None:
        return False, "Unknown character."
    if not character.is_wounded:
        return False, f"{character.name} isn't wounded."
    cost = WOUND_HEAL_COST.get(character.rarity, WOUND_HEAL_COST["common"])
    if player_state.money < cost:
        return False, f"Not enough gold to heal {character.name} (needs {cost})."
    player_state.money -= cost
    character.wounded_runs_remaining = 0
    return True, f"{character.name} is healed and ready to fight again (-{cost} gold)."


def apply_wound_penalty(player_state: PlayerState, heroes: Sequence[Combatant],
                         party: Sequence[PlayerCharacter], run_won: bool) -> List[str]:
    """Called once, when the player actually leaves the Colosseum (an
    explicit leave/cash-out, or the run ending on a loss) -- NOT after every
    individual battle in a streak, since a downed hero can still be revived
    in a later battle of the same run. `heroes`/`party` must be the same
    parallel lists run_battle already keeps (heroes[i] is the Combatant
    built from party[i] -- see game/battle_setup.py's build_battle), so
    combatant.alive tells us who's still down right now.

    For every hero who ends the run downed: benches them (wounded_runs_remaining
    = WOUND_RUNS, and pulled out of active_party so Party Select can't
    re-pick them) -- nothing else. `run_won` is unused here (the chosen
    penalty doesn't soften on a win) but kept in the signature since
    hub_server.py already has it on hand at every call site and a future
    tuning pass may want it.

    Returns one human-readable log line per newly-wounded hero, meant to be
    pushed into the battle log right as the run ends."""
    fallen_ids = {pc.id for combatant, pc in zip(heroes, party) if not combatant.alive}
    if not fallen_ids:
        return []
    messages: List[str] = []
    for pc in player_state.characters:
        if pc.id not in fallen_ids:
            continue
        pc.wounded_runs_remaining = WOUND_RUNS
        if pc.id in player_state.active_party:
            player_state.active_party.remove(pc.id)
        messages.append(
            f"{pc.name} was carried out of the Colosseum, wounded -- they'll sit out the next "
            f"{WOUND_RUNS} runs, or can be healed for gold from the Heroes page."
        )
    return messages


def tick_wounds(player_state: PlayerState) -> List[str]:
    """Called once at the very start of a new run (top of hub_server.py's
    run_battle, non-debug only) -- counts as "a run has now begun" for
    every wounded hero's countdown, whether or not they're actually in
    this run's party (a hero benched at home still heals up over time).
    Returns log lines for anyone whose wound just fully cleared."""
    messages: List[str] = []
    for pc in player_state.characters:
        if pc.wounded_runs_remaining > 0:
            pc.wounded_runs_remaining -= 1
            if pc.wounded_runs_remaining == 0:
                messages.append(f"{pc.name} has recovered and is fit to fight again.")
    return messages

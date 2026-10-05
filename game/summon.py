"""Summon: spend gems on either a new roster character or a piece of
premium equipment. Mirrors game/shop.py's shape -- plain functions over
PlayerState, no UI dependency, so ui/pygame_ui.py and ui/text_ui.py can
drive the exact same rules. Takes an injectable random.Random (same
convention as game/rewards.py's compute_battle_rewards) so tests can be
deterministic.

Character summons draw from data/summon_pool.py's RECRUITABLE_ROSTER, in
two independent rolls: first a rarity (data/hero_rarity.py's
HERO_SUMMON_WEIGHTS -- the "standard gacha curve"), then a uniform pick
among that rarity's (up to) 5 class-matched heroes. As of the hero-rarity
pass, a pull matching a hero you already own no longer avoids itself the
way it used to (there's no "fresh pool" concept left at all) -- duplicates
are allowed and grant hero shards for that hero instead of a new roster
entry (data/hero_rarity.py's SHARDS_PER_DUPLICATE; spend them via
game/heroes.py's upgrade_star). This was a deliberate behavior change
confirmed with Andrew via AskUserQuestion, not an oversight -- the old
dedup logic existed only because duplicates used to be worthless.

Equipment summons draw from the FULL catalog of data/equipment_db.py
(common through mythic, as of the equipment-summon rebalance -- it used to
be restricted to the cost<=0 epic/legendary/mythic slice, which made it too
easy to walk away with top-end gear), weighted per-tier by
data/summon_pool.py's EQUIPMENT_RARITY_WEIGHTS so common/rare are now the
common outcome and epic/legendary/mythic are rarer, more exciting pulls.
Results land in the unequipped stash exactly like a Shop purchase --
equip_from_stash (game/shop.py) is still the only way to actually put it on
a character. Equipment rarity is a separate, older rarity concept from hero
rarity (engine/equipment.py's RARITIES has its own 5 tiers, common..mythic,
distinct from data/hero_rarity.py's).

Equipment summons can also be paid for with equipment shards
(pay="shards" -- EQUIPMENT_SHARD_SUMMON_COST each) instead of gems, as of
Andrew's request to replace the old Premium-Ticket equipment option with a
dedicated currency, earned via battle drops and salvaging owned gear (see
game/shop.py's salvage_equipment and game/rewards.py's shard-drop roll).

--- Batch pulls (added for the Mobile-Legends-Adventure-style Summon
screen's card-reveal animation) ---

summon_character/summon_equipment above are single-pull convenience
wrappers kept exactly as they were (same signatures, same message text) so
every pre-existing caller/test keeps working unmodified. Both are now thin
wrappers around summon_character_batch/summon_equipment_batch(count=1) --
the actual roll logic lives there exactly once, so a 1x pull and a 10x
pull can never quietly drift apart. summon_character_x10/
summon_equipment_x10 are the same batch call pinned to
data/summon_pool.py's SUMMON_X10_COUNT.

A batch spends its *total* cost as one all-or-nothing lump sum up front
(can't afford 10 pulls -> nothing happens, no partial batch) and returns a
list of HeroSummonResult/EquipmentSummonResult -- one structured record per
pull, in roll order -- so a UI can render a per-card reveal (rarity,
portrait-or-icon, name, duplicate-vs-new) without re-deriving any of that
from a message string. A duplicate rolled more than once *within the same
batch* is handled correctly because each pull mutates player_state as it
goes, exactly like 10 separate single pulls would: the 2nd copy of a hero
pulled earlier in the same 10x batch sees them already on the roster and
grants shards, same as it would across two separate summons.
"""
import random as _random_module
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from data.hero_rarity import HERO_RARITIES, HERO_RARITY_LABEL, HERO_SUMMON_WEIGHTS, SHARDS_PER_DUPLICATE, STORY_RARITY
from data.summon_pool import (
    CHARACTER_SUMMON_COST, EQUIPMENT_SUMMON_COST, RECRUITABLE_BY_RARITY, SUMMON_X10_COUNT,
    COMMON_SUMMON_COST, COMMON_SUMMON_WEIGHTS, RECRUITABLE_ROSTER, TARGET_SHARE,
    EQUIPMENT_RARITY_WEIGHTS, EQUIPMENT_SHARD_SUMMON_COST,
)
from engine.equipment import Equipment
from game.equipment_instances import EquipmentInstance, bonus_text as _inst_bonus_text, new_instance
from game.player_state import PlayerState
from game.roster import PlayerCharacter

_HERO_RARITY_ROLL_WEIGHTS = [HERO_SUMMON_WEIGHTS[r] for r in HERO_RARITIES]


@dataclass(frozen=True)
class HeroSummonResult:
    """One character-summon pull's outcome, structured for a UI card
    (see ui/pygame_ui.py's _draw_reveal_card) rather than just a message
    string. `character` is the new-or-duplicated PlayerCharacter either
    way -- for a duplicate it's the *existing* roster member who just
    banked shards, not a throwaway record."""
    rarity: str
    character: PlayerCharacter
    is_duplicate: bool
    shards_gained: int
    message: str


@dataclass(frozen=True)
class EquipmentSummonResult:
    rarity: str
    item: Equipment              # the base catalog item (name, slot, subtype, baseline stat_bonuses)
    instance: EquipmentInstance  # the specific rolled copy that landed in the stash
    message: str


_COMMON_ROLL_WEIGHTS = [COMMON_SUMMON_WEIGHTS[r] for r in HERO_RARITIES]


def find_recruitable(name: Optional[str]):
    return next((h for h in RECRUITABLE_ROSTER if h.name == name), None) if name else None


def _roll_character(player_state: PlayerState, r: _random_module.Random,
                    weights=None, target=None) -> HeroSummonResult:
    """One character pull's worth of rolling + applying the result to
    player_state (roster append or shard grant) -- no gem check/deduction,
    callers (the batch functions below) handle the lump-sum cost.
    `weights` overrides the rarity odds (the Common Summon); `target` is a RecruitableHero the Premium
    Summon is rate-up'd for: if the rarity roll lands on the target's tier the target is chosen
    TARGET_SHARE of the time, otherwise uniformly among the tier's other heroes."""
    rarity = r.choices(HERO_RARITIES, weights=weights or _HERO_RARITY_ROLL_WEIGHTS, k=1)[0]
    if rarity == STORY_RARITY:        # Mythic heroes are the story cast: never summoned, so the pull lands as Legendary
        rarity = HERO_RARITIES[HERO_RARITIES.index(STORY_RARITY) - 1]
    tier = RECRUITABLE_BY_RARITY[rarity]
    if target is not None and target.rarity == rarity and target in tier:
        others = [h for h in tier if h is not target]
        recruit_data = target if (not others or r.random() < TARGET_SHARE) else r.choice(others)
    else:
        recruit_data = r.choice(tier)
    label = HERO_RARITY_LABEL[rarity]

    existing = next((c for c in player_state.characters
                      if c.name == recruit_data.name and c.class_id == recruit_data.class_id), None)
    if existing is not None:
        gained = SHARDS_PER_DUPLICATE[rarity]
        existing.shards += gained
        message = (f"[{label}] Duplicate! {existing.name} gives you +{gained} hero shards "
                   f"({existing.shards} banked -- visit Heroes to upgrade).")
        return HeroSummonResult(rarity, existing, True, gained, message)

    recruit = PlayerCharacter(name=recruit_data.name, class_id=recruit_data.class_id, rarity=rarity)
    player_state.characters.append(recruit)
    message = f"[{label}] {recruit.name} the {recruit.archetype.name} joins your team!"
    return HeroSummonResult(rarity, recruit, False, 0, message)


def free_team_summon(player_state: PlayerState, rng: Optional[_random_module.Random] = None) -> HeroSummonResult:
    """The free pull that comes with buying the arena team: one random hero at the Common Summon's odds, no cost.
    Still random -- the tutorial just does the pull for the player."""
    return _roll_character(player_state, rng or _random_module, weights=_COMMON_ROLL_WEIGHTS)


def _pay(player_state: PlayerState, currency: str, cost_each: int, count: int, ticket_kind: str, pay: str,
         shard_cost_each: Optional[int] = None):
    """Returns an error message, or None after deducting the cost.
    pay="currency" spends `currency` ("gems"/"money"); pay="ticket" spends `count` tickets of
    `ticket_kind`; pay="shards" spends count * shard_cost_each equipment shards (equipment summons
    only -- see EQUIPMENT_SHARD_SUMMON_COST)."""
    if pay == "ticket":
        have = player_state.tickets.get(ticket_kind, 0)
        if have < count:
            return f"Not enough {ticket_kind} tickets (need {count}, have {have})."
        player_state.tickets[ticket_kind] = have - count
        return None
    if pay == "shards":
        total = (shard_cost_each or 0) * count
        if player_state.equipment_shards < total:
            return f"Not enough equipment shards (need {total}, have {player_state.equipment_shards})."
        player_state.equipment_shards -= total
        return None
    total = cost_each * count
    if getattr(player_state, currency) < total:
        word = "gold" if currency == "money" else currency
        return f"Not enough {word} (need {total}, have {getattr(player_state, currency)})."
    setattr(player_state, currency, getattr(player_state, currency) - total)
    return None


def summon_common_batch(player_state: PlayerState, count: int, rng: Optional[_random_module.Random] = None,
                        pay: str = "currency") -> Tuple[bool, str, List[HeroSummonResult]]:
    """The Common Summon: COMMON_SUMMON_COST gold (or one Common Ticket) per pull, heroes only, low odds
    of high rarity (data/summon_pool.py COMMON_SUMMON_WEIGHTS)."""
    r = rng or _random_module
    err = _pay(player_state, "money", COMMON_SUMMON_COST, count, "common", pay)
    if err:
        return False, err, []
    results = [_roll_character(player_state, r, weights=_COMMON_ROLL_WEIGHTS) for _ in range(count)]
    return True, _summarize(results), results


def _summarize(results) -> str:
    if len(results) == 1:
        return results[0].message
    best = max(results, key=lambda res: HERO_RARITIES.index(res.rarity))
    return f"Pulled {len(results)} heroes! Best pull: [{HERO_RARITY_LABEL[best.rarity]}] {best.character.name}"


def summon_character_batch(player_state: PlayerState, count: int,
                            rng: Optional[_random_module.Random] = None,
                            target: Optional[str] = None, pay: str = "currency"
                            ) -> Tuple[bool, str, List[HeroSummonResult]]:
    """Spends count * CHARACTER_SUMMON_COST gems (as one lump sum -- either
    the whole batch is affordable or nothing happens) and rolls `count`
    independent character pulls. Returns (ok, message, results) -- results
    is a list of exactly `count` HeroSummonResult on success, empty on
    failure. `message` is the single pull's own message when count == 1
    (so summon_character's return stays identical to before this batch
    machinery existed), or a "Pulled N heroes! Best pull: ..." summary
    otherwise."""
    r = rng or _random_module
    target_hero = find_recruitable(target)
    if target and target_hero is None:
        return False, f"Unknown target hero {target!r}.", []
    if target_hero is not None and target_hero.rarity == STORY_RARITY:
        return False, f"{target_hero.name} is part of the story and can't be summoned.", []
    err = _pay(player_state, "gems", CHARACTER_SUMMON_COST, count, "premium", pay)
    if err:
        return False, err, []
    results = [_roll_character(player_state, r, target=target_hero) for _ in range(count)]
    return True, _summarize(results), results


def summon_character(player_state: PlayerState, rng: Optional[_random_module.Random] = None
                      ) -> Tuple[bool, str, Optional[PlayerCharacter], Optional[str]]:
    """Spends CHARACTER_SUMMON_COST gems to roll a hero rarity, then a
    class-matched hero at that rarity. If that hero is already on the
    roster, grants hero shards for them instead of a new entry. Returns
    (ok, message, the new-or-duplicated PlayerCharacter or None on failure,
    the rolled rarity or None on failure) -- the 4th element lets a UI
    color the reveal by rarity (see data/hero_rarity.py's HERO_RARITY_COLOR)
    without re-deriving it from the message text. A thin wrapper around
    summon_character_batch(count=1) -- see this module's docstring."""
    ok, msg, results = summon_character_batch(player_state, 1, rng)
    if not ok:
        return False, msg, None, None
    result = results[0]
    return True, result.message, result.character, result.rarity


def summon_character_x10(player_state: PlayerState, rng: Optional[_random_module.Random] = None
                          ) -> Tuple[bool, str, List[HeroSummonResult]]:
    """summon_character_batch pinned to data/summon_pool.py's
    SUMMON_X10_COUNT -- the Summon screen's "Pull x10" option."""
    return summon_character_batch(player_state, SUMMON_X10_COUNT, rng)


def _equipment_roll_pool(equipment_db: Dict[str, Equipment]) -> Tuple[List[Equipment], List[float]]:
    """Every catalog item (common through mythic -- as of the equipment-summon rebalance this is no
    longer restricted to the epic+/cost<=0 "premium" slice) paired with a per-item weight, computed by
    splitting EQUIPMENT_RARITY_WEIGHTS' per-TIER target evenly across however many items actually exist
    in that tier -- so the tier as a whole lands at its target rate regardless of catalog size, and every
    item within a tier is equally likely."""
    pool = list(equipment_db.values())
    counts: Dict[str, int] = {}
    for item in pool:
        counts[item.rarity] = counts.get(item.rarity, 0) + 1
    weights = [EQUIPMENT_RARITY_WEIGHTS.get(item.rarity, 0) / counts[item.rarity] for item in pool]
    return pool, weights


def _roll_equipment(player_state: PlayerState, pool: List[Equipment], weights: List[float],
                     r: _random_module.Random, base_db: Dict[str, Equipment]) -> EquipmentSummonResult:
    """Every equipment summon is a *rolled* instance (rolled=True) -- "only the summoned gear" gets
    random bonus stats, per Andrew. `base_db` must be the plain catalog (not a resolved db) since
    new_instance looks up the item's rarity by its base id."""
    item = r.choices(pool, weights=weights, k=1)[0]
    inst = new_instance(item.id, rolled=True, equipment_db=base_db, rng=r)
    player_state.add_equipment_to_stash(inst)
    message = f"You summoned {item.name} ({item.rarity})! {_inst_bonus_text(inst, base_db)}"
    return EquipmentSummonResult(item.rarity, item, inst, message)


def summon_equipment_batch(player_state: PlayerState, equipment_db: Dict[str, Equipment], count: int,
                            rng: Optional[_random_module.Random] = None, pay: str = "currency"
                            ) -> Tuple[bool, str, List[EquipmentSummonResult]]:
    """Spends count * EQUIPMENT_SUMMON_COST gems (pay="currency") or count * EQUIPMENT_SHARD_SUMMON_COST
    equipment shards (pay="shards" -- replaces the old Premium-Ticket option for gear) as one lump sum,
    all-or-nothing, for `count` random items drawn from the FULL catalog (data/summon_pool.py's
    EQUIPMENT_RARITY_WEIGHTS -- common through mythic, common/rare now included), each rolled into a
    fresh instance (with random bonus stats -- see game/equipment_instances.py) and added to the
    unequipped stash -- never auto-equipped, same rule as a single pull. `equipment_db` here must be the
    plain catalog (not a resolved db): the pool is chosen from base items, one fresh roll per pull."""
    r = rng or _random_module
    pool, weights = _equipment_roll_pool(equipment_db)
    if not pool:
        return False, "There's no equipment to summon right now.", []

    err = _pay(player_state, "gems", EQUIPMENT_SUMMON_COST, count, "premium", pay,
               shard_cost_each=EQUIPMENT_SHARD_SUMMON_COST)
    if err:
        return False, err, []
    results = [_roll_equipment(player_state, pool, weights, r, equipment_db) for _ in range(count)]

    summary = results[0].message if count == 1 else f"Summoned {count} pieces of gear!"
    return True, summary, results


def summon_equipment(player_state: PlayerState, equipment_db: Dict[str, Equipment],
                      rng: Optional[_random_module.Random] = None) -> Tuple[bool, str]:
    """Spends EQUIPMENT_SUMMON_COST gems for a random piece of premium
    (cost<=0) gear, added to the unequipped stash -- never auto-equipped,
    same rule as a Shop equipment purchase. A thin wrapper around
    summon_equipment_batch(count=1) -- see this module's docstring."""
    ok, msg, results = summon_equipment_batch(player_state, equipment_db, 1, rng)
    if not ok:
        return False, msg
    return True, results[0].message


def summon_equipment_x10(player_state: PlayerState, equipment_db: Dict[str, Equipment],
                          rng: Optional[_random_module.Random] = None
                          ) -> Tuple[bool, str, List[EquipmentSummonResult]]:
    """summon_equipment_batch pinned to data/summon_pool.py's
    SUMMON_X10_COUNT -- the Summon screen's "Pull x10" option."""
    return summon_equipment_batch(player_state, equipment_db, SUMMON_X10_COUNT, rng)

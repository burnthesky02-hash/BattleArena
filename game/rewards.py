"""Battle payout: money for showing up, gems and XP for winning -- all three
scaled by a difficulty/team-size multiplier as of the level-curve pass.

Andrew's spec: "you get money from fighting battles, regardless if you win
or not, and ... when you win you get gems." So money always has a nonzero
floor (just a smaller one on a loss/flee than a win), and gems are strictly
victory-only. Kept as a pure function of the battle result (plus an
injectable random.Random for deterministic tests) rather than something
BattleEngine itself knows about -- the engine has no concept of a
meta-currency, on purpose (see engine/'s module docstrings elsewhere about
staying UI/AI/progression-agnostic); main.py calls this once after
BattleEngine.run() returns and applies the result to PlayerState itself.

Reward multiplier, exactly per Andrew's spec: difficulty_modifier (easy
.75, normal 1, hard 1.25, extreme 2) times a size_modifier that's +0.25 per
enemy beyond the first and -0.25 per hero beyond the first -- so 1 hero vs 3
enemies is 1 + 0.25*2 = 1.5x, and on extreme that's 2 * 1.5 = 3x, matching
his own worked example exactly. One addition beyond his literal spec: the
size_modifier is floored at 0.1 so a very large roster (nothing in
game/player_state.py caps roster size) can't drive it to zero or negative --
he only described the 1-hero example, so this floor is a safety clamp, not
part of the formula he gave.

Money is scaled by the multiplier regardless of outcome (fighting a harder,
bigger fight costs more effort even in a loss); gems and XP stay
victory-only, same as gems always were -- Andrew's battle-XP answer said XP
should scale "the same as money/gems" but didn't say whether a loss should
grant any, so this follows gems' existing victory-only precedent rather
than inventing a new rule. XP is per character who fought (see
PlayerCharacter.grant_xp), not a pooled amount split between them.

Hero-rival shard drops (Andrew's request: defeating a hero enemy -- see
game/battle_setup.py's HERO_ENEMY_CHANCE -- has "a small chance to win their
respective hero shards"): kept separate from compute_battle_rewards above on
purpose. Money/gems/XP are unconditional battle-shape math (difficulty,
party size, enemy count); a shard drop is conditional on *which specific
enemies* were in the fight and whether they're actually dead, which
compute_battle_rewards' pure (result, difficulty, sizes) signature has no way
to see. roll_hero_enemy_shard_drops is the victory-only, per-defeated-rival
counterpart main.py calls alongside compute_battle_rewards.
"""
import random as _random_module
from typing import Dict, List, Optional, Sequence, Tuple

from data.hero_rarity import SHARDS_PER_DUPLICATE
from data.summon_pool import RecruitableHero
from engine.combatant import Combatant
from engine.types import BattleResult
from game.battle_setup import DIFFICULTY_REWARD_MODIFIER
from game.player_state import PlayerState

# Flat base ranges -- multiplied by the difficulty/size multiplier below.
# These used to be the whole story before difficulty existed; now they're
# just the "normal, 1v1" baseline.
VICTORY_MONEY_RANGE = (35, 55)
LOSS_MONEY_RANGE = (10, 20)
FLED_MONEY_RANGE = (5, 15)
VICTORY_GEM_RANGE = (3, 6)
VICTORY_XP_RANGE = (20, 30)  # per character who fought

SIZE_MODIFIER_FLOOR = 0.1


def size_modifier(num_heroes: int, num_enemies: int) -> float:
    """+0.25 per enemy beyond the first, -0.25 per hero beyond the first
    (Andrew's exact wording), floored so a huge roster can't go negative."""
    raw = 1.0 + 0.25 * (max(1, num_enemies) - 1) - 0.25 * (max(1, num_heroes) - 1)
    return max(SIZE_MODIFIER_FLOOR, raw)


def reward_multiplier(difficulty: str, num_heroes: int, num_enemies: int) -> float:
    """difficulty_modifier * size_modifier -- the single multiplier applied
    to money/gems/XP. Unknown difficulty falls back to "normal" (1.0) rather
    than raising, so a stray/legacy call site degrades gracefully."""
    diff_mod = DIFFICULTY_REWARD_MODIFIER.get(difficulty, 1.0)
    return diff_mod * size_modifier(num_heroes, num_enemies)


def compute_battle_rewards(result: BattleResult, rng: Optional[_random_module.Random] = None, *,
                            difficulty: str = "normal", num_heroes: int = 1,
                            num_enemies: int = 1) -> Tuple[int, int, int]:
    """Returns (money, gems, xp_per_character) earned for a battle that ended
    with this result. Pass an explicit `rng` (a random.Random instance) for
    deterministic tests; defaults to the shared `random` module otherwise.
    difficulty/num_heroes/num_enemies default to a plain "normal, 1v1" fight
    (multiplier 1.0) so existing call sites that don't pass them keep
    behaving exactly as before -- only game/battle_setup.py-driven battles
    pass the real numbers."""
    r = rng or _random_module
    mult = reward_multiplier(difficulty, num_heroes, num_enemies)

    if result == BattleResult.VICTORY:
        money = round(r.randint(*VICTORY_MONEY_RANGE) * mult)
        gems = round(r.randint(*VICTORY_GEM_RANGE) * mult)
        xp = round(r.randint(*VICTORY_XP_RANGE) * mult)
        return max(1, money), max(1, gems), max(1, xp)
    if result == BattleResult.FLED:
        return max(1, round(r.randint(*FLED_MONEY_RANGE) * mult)), 0, 0
    # DEFEAT (and anything else unexpected) still pays the "you showed up" floor.
    return max(1, round(r.randint(*LOSS_MONEY_RANGE) * mult)), 0, 0


# Chance, per defeated hero rival (see game/battle_setup.py's HERO_ENEMY_CHANCE),
# that beating them pays out hero shards at all. Deliberately independent of
# rarity -- rarity already controls how *much* a hit pays out (it reuses
# SHARDS_PER_DUPLICATE below, the exact same table a duplicate Summon pull
# uses) and how *often you run into that rival in the first place*
# (HERO_ENEMY_CHANCE's rarity-weighted roll); stacking a second rarity effect
# on top of the drop chance itself would make mythic rivals nearly
# pointless to fight. First-pass number, same "retune by feel" spirit as
# everything else numeric in this project.
HERO_SHARD_DROP_CHANCE = 0.15


def roll_ticket_drops(rng: Optional[_random_module.Random] = None, *, boss_first_clear: Optional[bool] = None,
                      ladder: bool = False) -> Dict[str, int]:
    """Summon tickets earned by one victory. Normal fights: a small independent chance of each kind
    (doubled in Ladder Mode). Boss fights (boss_first_clear is True/False, not None): a guaranteed haul,
    bigger on the first clear. Returns only the kinds that dropped, e.g. {"common": 1}."""
    from data.summon_pool import (TICKET_DROP_CHANCE, BOSS_TICKETS_FIRST, BOSS_TICKETS_REPEAT)
    r = rng or _random_module
    if boss_first_clear is not None:
        return dict(BOSS_TICKETS_FIRST if boss_first_clear else BOSS_TICKETS_REPEAT)
    out: Dict[str, int] = {}
    for kind, chance in TICKET_DROP_CHANCE.items():
        if r.random() < chance * (2 if ladder else 1):
            out[kind] = 1
    return out


# Item drops from random (wild / dungeon) fights. Colosseum bouts pay gems/tickets/shards instead.
ITEM_DROP_CHANCE = 0.40                 # chance that a won random fight drops anything at all
# (item id, weight, min enemy level) -- potions are common, ethers and revives are rare finds.
ITEM_DROP_TABLE = (("potion", 55, 1), ("antidote", 18, 1), ("hi_potion", 14, 12), ("ether", 9, 8), ("phoenix_down", 4, 10))


def roll_item_drops(enemy_level: int = 1, rng: Optional[_random_module.Random] = None) -> Dict[str, int]:
    """Consumables dropped by one won random fight: ITEM_DROP_CHANCE of a single item picked from
    ITEM_DROP_TABLE (rarer entries only unlock at higher enemy levels), and a one-in-five chance of a second.
    Returns {item_id: count} (empty when nothing dropped); the caller adds it to the inventory."""
    r = rng or _random_module
    if r.random() >= ITEM_DROP_CHANCE:
        return {}
    pool = [(iid, w) for iid, w, lo in ITEM_DROP_TABLE if (enemy_level or 1) >= lo]
    if not pool:
        return {}
    out: Dict[str, int] = {}
    for _ in range(2 if r.random() < 0.2 else 1):
        iid = r.choices([i for i, _w in pool], weights=[w for _i, w in pool])[0]
        out[iid] = out.get(iid, 0) + 1
    return out


def roll_equipment_shard_drops(rng: Optional[_random_module.Random] = None, *,
                                boss_first_clear: Optional[bool] = None, ladder: bool = False) -> int:
    """Equipment shards earned by one victory -- the battle-drop half of the equipment-shard economy
    (the other half is salvaging owned gear, game/shop.py's salvage_equipment). Mirrors
    roll_ticket_drops' exact shape: normal fights get a small independent chance of a small random
    amount (doubled in Ladder Mode); boss fights (boss_first_clear True/False, not None) get a
    guaranteed flat haul, bigger on the first clear. Returns the amount gained (0 if nothing dropped),
    meant to be passed straight to PlayerState.add_equipment_shards."""
    from data.summon_pool import (
        EQUIPMENT_SHARD_DROP_CHANCE, EQUIPMENT_SHARD_DROP_RANGE,
        BOSS_EQUIPMENT_SHARDS_FIRST, BOSS_EQUIPMENT_SHARDS_REPEAT,
    )
    r = rng or _random_module
    if boss_first_clear is not None:
        return BOSS_EQUIPMENT_SHARDS_FIRST if boss_first_clear else BOSS_EQUIPMENT_SHARDS_REPEAT
    if r.random() < EQUIPMENT_SHARD_DROP_CHANCE * (2 if ladder else 1):
        return r.randint(*EQUIPMENT_SHARD_DROP_RANGE)
    return 0


def roll_hero_enemy_shard_drops(defeated_hero_enemies: Sequence[Tuple[RecruitableHero, Combatant]],
                                 player_state: PlayerState,
                                 rng: Optional[_random_module.Random] = None) -> List[str]:
    """Victory-only companion to compute_battle_rewards: for every (recruit,
    combatant) pair naming a hero-rival enemy from this battle, rolls
    HERO_SHARD_DROP_CHANCE and, on a hit, banks SHARDS_PER_DUPLICATE[rarity]
    shards onto the matching owned PlayerCharacter (same name+class_id
    identity check game/summon.py's duplicate-pull logic uses) -- exactly as
    if that pull had been a duplicate Summon. A rival for a hero you haven't
    recruited yet is skipped silently: shards only mean anything spent
    against an owned PlayerCharacter (see game/heroes.py's upgrade_star), so
    there's nothing to bank them onto yet. This is a deliberate first-pass
    scope call, not an oversight -- see the module docstring above for why
    this is a separate function from compute_battle_rewards rather than a
    parameter on it. A combatant that somehow isn't actually dead (shouldn't
    happen when the caller only passes this after a VICTORY, but cheap to
    guard) is skipped too. Returns one human-readable message per drop that
    actually landed, meant to be handed to ui.print_line so it shows up in
    the battle log right where the fight just ended."""
    r = rng or _random_module
    messages: List[str] = []
    for recruit, combatant in defeated_hero_enemies:
        if combatant.alive:
            continue
        if r.random() >= HERO_SHARD_DROP_CHANCE:
            continue
        owned = next((c for c in player_state.characters
                      if c.name == recruit.name and c.class_id == recruit.class_id), None)
        if owned is None:
            continue
        gained = SHARDS_PER_DUPLICATE[recruit.rarity]
        owned.shards += gained
        messages.append(
            f"{combatant.name} drops {gained} hero shards for {owned.name}! ({owned.shards} banked -- see Heroes)"
        )
    return messages

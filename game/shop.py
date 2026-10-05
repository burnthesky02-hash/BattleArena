"""Shop and equip logic: plain functions over PlayerState, kept free of any
UI so buying/equipping can be tested headlessly and driven identically by
either ui/pygame_ui.py or ui/text_ui.py -- the same separation engine/ keeps
from ui/ and ai/.

Money buys consumable items (data/items_db.py) and common/rare equipment
(nonzero `cost` -- see data/equipment_db.py); epic/legendary/mythic gear has
`cost=0` and is reserved for the gem-summon pool, not sold here, so
buy_equipment refuses it the same way it refuses an id that isn't in the
catalog at all.

--- The equipment overhaul: instances, not counts ---

Buying equipment mints a fresh EquipmentInstance (game/equipment_instances.py,
`rolled=False` -- shop gear never gets random bonus stats, only summoned
gear does) and drops it in PlayerState.equipment_stash rather than
auto-equipping it -- equip_from_stash is a separate, explicit step, since
which character should wear it isn't implied by the purchase.

`equipment_db` in every function below is expected to be a RESOLVED db
(game/equipment_instances.resolve_equipment_db) whenever real player gear
might be involved -- it has one entry per catalog item AND one per live
instance (keyed by instance id), so `equipment_db.get(some_id)` works
identically whether `some_id` is a base catalog id (buy_equipment's
argument, always a catalog id) or an instance id (equip_from_stash/unequip's
argument, always an instance id).

equip_from_stash hard-blocks a class from equipping a subtype/weight it
can't use (engine.equipment.class_can_equip), per Andrew.

Every function returns (ok: bool, message: str) -- ok says whether
anything changed, message is a ready-to-display reason either way, so a UI
just needs to render it rather than build its own copy for every failure
mode.
"""
from typing import Dict, Tuple

from data.summon_pool import EQUIPMENT_SALVAGE_YIELD
from engine.equipment import Equipment, class_can_equip
from engine.items import Item
from game.equipment_instances import new_instance
from game.player_state import PlayerState
from game.roster import PlayerCharacter


def buy_item(player_state: PlayerState, item_id: str, items_db: Dict[str, Item]) -> Tuple[bool, str]:
    item = items_db.get(item_id)
    if item is None:
        return False, "That item doesn't exist."
    if item.cost <= 0:
        return False, f"{item.name} isn't for sale."
    if player_state.money < item.cost:
        return False, f"Not enough money for {item.name} (need {item.cost}, have {player_state.money})."
    player_state.money -= item.cost
    player_state.inventory[item_id] = player_state.inventory.get(item_id, 0) + 1
    return True, f"Bought {item.name} for {item.cost} money."


def buy_equipment(player_state: PlayerState, equipment_id: str,
                   equipment_db: Dict[str, Equipment]) -> Tuple[bool, str]:
    """`equipment_id` is always a base catalog id here -- the shop only ever sells catalog items, never a
    specific instance. Mints a fresh, un-rolled instance and stashes it."""
    item = equipment_db.get(equipment_id)
    if item is None:
        return False, "That equipment doesn't exist."
    if item.cost <= 0:
        return False, f"{item.name} isn't for sale here (it's a summon-only item)."
    if player_state.money < item.cost:
        return False, f"Not enough money for {item.name} (need {item.cost}, have {player_state.money})."
    player_state.money -= item.cost
    inst = new_instance(equipment_id, rolled=False, equipment_db=equipment_db)
    player_state.add_equipment_to_stash(inst)
    return True, f"Bought {item.name} for {item.cost} money."


def _find_character(player_state: PlayerState, character_id: str) -> "PlayerCharacter | None":
    return next((c for c in player_state.characters if c.id == character_id), None)


def equip_from_stash(player_state: PlayerState, character_id: str, instance_id: str,
                      equipment_db: Dict[str, Equipment]) -> Tuple[bool, str]:
    """Moves instance_id out of the unequipped stash and onto character_id,
    returning whatever was equipped in that slot before (if anything) to the
    stash. Refuses (hard block, no partial equip) when character_id's class
    can't use item's subtype/weight -- e.g. a mage and a heavy helmet."""
    character = _find_character(player_state, character_id)
    if character is None:
        return False, "Unknown character."
    item = equipment_db.get(instance_id)
    if item is None:
        return False, "That equipment doesn't exist."
    if instance_id not in player_state.equipment_stash:
        return False, f"You don't own a {item.name}."

    archetype = character.archetype
    if not class_can_equip(item, archetype.weapon_types, archetype.offhand_types, archetype.armor_weight):
        return False, f"{character.name} ({archetype.name}) can't equip {item.name}."

    previous = character.equip(instance_id, equipment_db)

    player_state.take_from_stash(instance_id)
    if previous:
        player_state.return_to_stash(previous)

    return True, f"Equipped {item.name} on {character.name}."


def buy_and_equip(player_state: PlayerState, equipment_id: str, character_id: str,
                  catalog_db: Dict[str, Equipment], resolve_db) -> Tuple[bool, str]:
    """Shop's "Buy & Equip": buys one catalog item and puts it straight on `character_id`. Everything that
    could refuse (unknown item/character, summon-only, too poor, class can't wear it) is checked BEFORE any
    money moves, so a refusal never costs anything. `resolve_db` is a zero-arg callable returning a fresh
    resolved equipment db (the new instance only exists in it after the purchase). Whatever the hero was
    wearing in that slot goes back to the stash, same as equip_from_stash."""
    item = catalog_db.get(equipment_id)
    if item is None:
        return False, "That equipment doesn't exist."
    character = _find_character(player_state, character_id)
    if character is None:
        return False, "Unknown character."
    if item.cost > 0:
        archetype = character.archetype
        if not class_can_equip(item, archetype.weapon_types, archetype.offhand_types, archetype.armor_weight):
            return False, f"{character.name} ({archetype.name}) can't equip {item.name}."
    old_id = character.equipped.get(item.slot)
    stash_before = set(player_state.equipment_stash)
    ok, msg = buy_equipment(player_state, equipment_id, catalog_db)
    if not ok:
        return False, msg
    new_ids = [i for i in player_state.equipment_stash if i not in stash_before]
    if not new_ids:
        return True, msg + " (it is in your stash)"
    edb = resolve_db()
    old_name = edb[old_id].name if old_id and old_id in edb else None
    ok2, msg2 = equip_from_stash(player_state, character_id, new_ids[0], edb)
    if not ok2:
        return True, f"{msg} It is in your stash ({msg2})"
    text = f"Bought {item.name} for {item.cost} money and equipped it on {character.name}."
    if old_name:
        text += f" {old_name} went to the stash."
    return True, text


def salvage_equipment(player_state: PlayerState, instance_id: str,
                       equipment_db: Dict[str, Equipment]) -> Tuple[bool, str]:
    """Breaks down one unequipped stash instance into equipment shards (data/summon_pool.py's
    EQUIPMENT_SALVAGE_YIELD, keyed by the item's base rarity) -- the second of the two ways to earn
    shards for game/summon.py's equipment-shard summon option, alongside battle drops
    (game/rewards.py). Only stash items can be salvaged (mirrors equip_from_stash's membership check) --
    salvage the item from a character first via unequip() if it's currently worn."""
    item = equipment_db.get(instance_id)
    if item is None:
        return False, "That equipment doesn't exist."
    if instance_id not in player_state.equipment_stash:
        return False, f"You don't own an unequipped {item.name} (unequip it first if it's worn)."

    yield_amount = EQUIPMENT_SALVAGE_YIELD.get(item.rarity, 0)
    player_state.take_from_stash(instance_id)
    player_state.equipment_instances.pop(instance_id, None)
    player_state.add_equipment_shards(yield_amount)
    return True, f"Salvaged {item.name} for {yield_amount} equipment shards."


def unequip(player_state: PlayerState, character_id: str, slot: str,
            equipment_db: Dict[str, Equipment]) -> Tuple[bool, str]:
    """Removes whatever instance is in `slot` and returns it to the stash."""
    character = _find_character(player_state, character_id)
    if character is None:
        return False, "Unknown character."
    if slot not in character.equipped:
        return False, f"Unknown equipment slot {slot!r}."
    current_id = character.equipped[slot]
    if not current_id:
        return False, "Nothing is equipped there."

    character.equipped[slot] = None
    player_state.return_to_stash(current_id)

    item = equipment_db.get(current_id)
    name = item.name if item else current_id
    return True, f"Unequipped {name} from {character.name}."


def upgrade_weapon(player_state: PlayerState, instance_id: str,
                   equipment_db: Dict[str, Equipment], cap: int = 10, smith_name: str = "The blacksmith") -> Tuple[bool, str]:
    """Blacksmith: pay gold to take one WEAPON (worn by anyone, or in the stash) up one upgrade level. Each level
    adds a slice of the weapon's stat bonuses (game/equipment_instances.py's weapon_upgrade_bonus). All-or-nothing."""
    from game.equipment_instances import WEAPON_MAX_UPGRADE, weapon_upgrade_cost
    inst = player_state.equipment_instances.get(instance_id)
    item = equipment_db.get(instance_id)
    if inst is None or item is None:
        return False, "That weapon doesn't exist."
    if item.slot != "weapon":
        return False, "The blacksmith only upgrades weapons."
    owned = instance_id in player_state.equipment_stash or any(
        instance_id in c.equipped.values() for c in player_state.characters)
    if not owned:
        return False, "You don't own that weapon."
    if inst.upgrade_level >= WEAPON_MAX_UPGRADE:
        return False, f"{item.name} is already at its limit (+{WEAPON_MAX_UPGRADE})."
    if inst.upgrade_level >= cap:
        return False, f"{smith_name} can't take a weapon past +{cap}. Look for a master smith further on."
    cost = weapon_upgrade_cost(item.rarity, inst.upgrade_level)
    if player_state.money < cost:
        return False, f"Upgrading costs {cost} gold; you have {player_state.money}."
    player_state.money -= cost
    inst.upgrade_level += 1
    base_item = equipment_db.get(inst.base_id)
    base_name = base_item.name if base_item else item.name
    return True, f"{smith_name} reforges {base_name} to +{inst.upgrade_level} for {cost} gold."

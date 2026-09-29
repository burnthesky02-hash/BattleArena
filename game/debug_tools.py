"""Debug cheats over PlayerState (hub debug menu). Pure logic, no UI/networking. Every action returns
(ok, message); callers hold the state lock and save afterwards."""
from data.classes import CLASS_ARCHETYPES
from data.equipment_db import EQUIPMENT
from data.hero_rarity import HERO_RARITIES, MAX_STARS
from data.items_db import ITEMS, STARTING_INVENTORY
from data.leveling import MAX_LEVEL
from data.summon_pool import RECRUITABLE_ROSTER
from game import renown as R
from game.equipment_instances import new_instance
from game.roster import PlayerCharacter

MAX_AMOUNT = 10_000_000


def _int(v, default=0, lo=0, hi=MAX_AMOUNT):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def _hero(state, hid):
    return next((c for c in state.characters if c.id == hid), None)


def reset_state(state, starter_name="Garrick", starter_class="tank") -> None:
    """Back to a brand-new game, in place (so every holder of `state` sees it)."""
    from game.player_state import PlayerState
    fresh = PlayerState.new_game(PlayerCharacter(name=starter_name, class_id=starter_class))
    state.__dict__.clear()
    state.__dict__.update(fresh.__dict__)


def apply(state, msg: dict, starter=("Garrick", "tank")):
    a = msg.get("action")
    if a == "reset_game":
        reset_state(state, *starter)
        return True, "Game reset to a fresh save."
    if a == "add_money":
        n = _int(msg.get("amount"), 1000)
        state.money += n
        return True, f"+{n} gold."
    if a == "add_gems":
        n = _int(msg.get("amount"), 100)
        state.gems += n
        return True, f"+{n} gems."
    if a == "add_tickets":
        kind = msg.get("kind")
        if kind not in ("common", "premium"):
            return False, "Unknown ticket kind."
        n = _int(msg.get("count"), 10, 1, 9999)
        state.add_tickets({kind: n})
        return True, f"+{n} {kind} tickets."
    if a == "add_equipment_shards":
        n = _int(msg.get("amount"), 50, 1, 9999)
        state.add_equipment_shards(n)
        return True, f"+{n} equipment shards."
    if a == "add_hero":
        name = (msg.get("name") or "").strip()
        rec = next((h for h in RECRUITABLE_ROSTER if h.name == name), None)
        class_id = rec.class_id if rec else msg.get("class_id")
        rarity = rec.rarity if rec else (msg.get("rarity") or "common")
        if class_id not in CLASS_ARCHETYPES:
            return False, "Pick a class."
        if rarity not in HERO_RARITIES:
            return False, "Unknown rarity."
        c = PlayerCharacter(name=name or f"Debug {CLASS_ARCHETYPES[class_id].name}", class_id=class_id,
                            rarity=rarity, level=_int(msg.get("level"), 1, 1, MAX_LEVEL),
                            stars=_int(msg.get("stars"), 1, 1, MAX_STARS))
        state.characters.append(c)
        return True, f"{c.name} joined (Lv {c.level})."
    if a == "remove_hero":
        c = _hero(state, msg.get("id"))
        if c is None:
            return False, "No such hero."
        if len(state.characters) <= 1:
            return False, "Can't remove your only hero."
        state.characters.remove(c)
        state.active_party = [i for i in state.active_party if i != c.id]
        return True, f"{c.name} removed."
    if a == "set_hero":
        c = _hero(state, msg.get("id"))
        if c is None:
            return False, "No such hero."
        if msg.get("level") not in (None, ""):
            c.level, c.xp = _int(msg["level"], c.level, 1, MAX_LEVEL), 0
        if msg.get("stars") not in (None, ""):
            c.stars = _int(msg["stars"], c.stars, 1, MAX_STARS)
        if msg.get("shards") not in (None, ""):
            c.shards = _int(msg["shards"], c.shards)
        return True, f"{c.name}: Lv {c.level}, {c.stars} stars, {c.shards} shards."
    if a == "level_all":
        lv = _int(msg.get("level"), MAX_LEVEL, 1, MAX_LEVEL)
        for c in state.characters:
            c.level, c.xp = lv, 0
        return True, f"Everyone is level {lv}."
    if a == "add_equipment":
        eid = msg.get("id")
        if eid not in EQUIPMENT:
            return False, "Unknown equipment."
        n = _int(msg.get("count"), 1, 1, 99)
        for _ in range(n):
            state.add_equipment_to_stash(new_instance(eid, rolled=False, equipment_db=EQUIPMENT))
        return True, f"+{n} {EQUIPMENT[eid].name}."
    if a == "add_all_equipment":
        for eid in EQUIPMENT:
            state.add_equipment_to_stash(new_instance(eid, rolled=False, equipment_db=EQUIPMENT))
        return True, f"+1 of every equipment ({len(EQUIPMENT)})."
    if a == "clear_stash":
        # Only clears the unequipped stash list -- equipped instances stay registered in
        # equipment_instances (still referenced by a character's `equipped`), same guarantee the old
        # owned_equipment-based version made ("equipped gear untouched").
        state.equipment_stash.clear()
        return True, "Equipment stash emptied (equipped gear untouched)."
    if a == "add_item":
        iid = msg.get("id")
        if iid not in ITEMS:
            return False, "Unknown item."
        n = _int(msg.get("count"), 1, 1, 99)
        state.inventory[iid] = state.inventory.get(iid, 0) + n
        return True, f"+{n} {ITEMS[iid].name}."
    if a == "max_items":
        for iid in ITEMS:
            state.inventory[iid] = 99
        return True, "All consumables set to 99."
    if a == "reset_items":
        state.inventory = dict(STARTING_INVENTORY)
        return True, "Consumables reset to starting stock."
    if a == "set_rank":
        rank = _int(msg.get("rank"), 1, 1, len(R.RANK_BOSSES) + 1)
        state.rank, state.renown = rank, 0
        state.cleared_bosses = list(R.RANK_BOSSES[:rank - 1])
        return True, f"Rank {rank} ({R.rank_name(rank)}); renown 0; earlier bosses marked cleared."
    if a == "set_renown":
        state.renown = 0
        R.apply_renown(state, _int(msg.get("renown"), 0))
        return True, f"Renown {state.renown}."
    if a == "unlock_boss":
        if not R.has_next_boss(state):
            return False, "No boss left to challenge."
        state.renown = R.gate_for_rank(state.rank)
        return True, "Renown set to the boss gate."
    if a == "reset_boss_clears":
        state.cleared_bosses = []
        return True, "First-clear bonuses re-armed (rank unchanged)."
    return False, f"Unknown debug action {a!r}."

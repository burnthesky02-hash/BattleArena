"""hub_server.py -- the single real game server: your ACTUAL PlayerState
(real save file, real money/gems/roster) behind every screen that touches
it, plus the live battle itself, all in one process.

This used to be two processes (hub_server.py for the Colosseum hub/Heroes/
Summon, battle_server.py for the live battle) sharing a port scheme but NOT
sharing memory -- each loaded its own in-memory PlayerState at startup, so a
battle's rewards never made it back into the save the hub was showing, and
running both while multi-tabbed was a real (if narrow) multi-writer risk.
Andrew asked directly whether that split was actually necessary; it wasn't
-- a live battle is a longer-lived connection than a plain HTTP request, but
that only means it needs its own protocol (WebSocket), not its own process.
This file now runs BOTH: a ThreadingHTTPServer for every page/asset/JSON API
call (hub, Heroes, Summon, and now the battle page too), and an asyncio
`websockets` server for the one long-lived battle connection, on a
background thread of its own -- and, critically, both sides read and write
the exact same `player_state` object behind the exact same `threading.Lock`.
That's what makes battle rewards (money/gems/XP, hero-rival shard drops)
finally persist to the real save the instant a fight ends, instead of never
touching it at all (the gap flagged since Stage 6/fix #24) -- and it's what
makes "Enter Battle" fight with your REAL active party instead of a fixed
four-person demo squad, since the battle thread now reads
game/party.py's active_party_characters() off the same PlayerState the hub
shows, rather than building its own throwaway one.

`battle_server.py` still exists as a file on disk (this session can't
delete files on your machine) but now just prints a short redirect message
and exits -- see the bottom of this docstring and that file's own comment.
Only ever run `python hub_server.py` from here on; it does everything.

Screen by screen, what this process does for real:

  Colosseum hub (/ or /index.html):
  - Loads game/save_system.py's actual save1.json if one exists; creates
    and saves a brand-new game otherwise (see _default_new_game below --
    character creation isn't in HTML yet, so a new game starts with one
    fixed starter hero, same stopgap idea the battle side uses below for
    the enemy-side difficulty/count).
  - Shows the real active battle party (game/party.py's
    active_party_characters), real money/gems, real bench count, real
    hero portraits out of data/Portraits/.
  - "Enter Battle" navigates the browser to /battle -- same origin, same
    process, no more separate port to juggle.
  - Debug-only "Add Gems" cheat button, same config.DEBUG_GEM_GRANT/
    config.DEBUG gate show_colosseum_hub already used.
  - "Save & Quit" really calls save_system.save_game.

  Heroes (/heroes) and Summon (/summon): unchanged from the previous
  hub_server.py -- see their own sections further down if you're looking
  for that logic; nothing about merging in battle changed how they work.

  Battle (/battle, plus a WebSocket at ws://.../  on WS_PORT):
  - Real BattleEngine, real game/battle_setup.py.build_battle, real
    ai/enemy_ai.py Ollama-driven enemy AI with scripted fallback -- all
    exactly as battle_server.py ran them, unmodified.
  - The party fighting is now `game/party.py`'s active_party_characters
    read off the SAME player_state the hub/Heroes show -- not a fixed
    four-person demo party. Difficulty and opponent count are still
    hardcoded (DEMO_DIFFICULTY/DEMO_NUM_ENEMIES below) since Party
    Select/Battle Setup don't exist in HTML yet -- that's the one thing
    this merge did NOT change, flagged again at the bottom of this file.
  - On battle end, real rewards are computed exactly the way
    main.py's run_one_battle does it (game/rewards.py's
    compute_battle_rewards + roll_hero_enemy_shard_drops), applied to the
    real player_state under the same lock every hub/Heroes/Summon action
    uses, and saved to disk immediately -- so returning to the Colosseum
    after a real win now actually shows the money/gems/XP you earned,
    which it never did before this merge.

Needs the same extra dependency battle_server.py needed (not in
requirements.txt yet -- add it there once this is committed for real):
    pip install websockets

Run from the Battle Arena project root:
    python hub_server.py
Then open http://127.0.0.1:8767/ in a browser.

Two ports, still: 8767 (HTTP -- pages, assets, hub/Heroes/Summon JSON API,
the battle page) and 8766 (WebSocket -- the one live battle connection).
Collapsing those down to a single port too would mean hand-rolling the
WebSocket upgrade handshake inside http.server (or switching this whole
file to an aiohttp-style stack) -- a bigger, riskier rewrite for a cosmetic
win with no real browser here to verify it against, so it wasn't done.
What actually mattered -- one process, one shared PlayerState, real reward
persistence -- is done; the two ports are just an implementation detail of
"one process talks two protocols," not two servers to start/manage anymore.
"""
import argparse
import asyncio
import json
import random
import queue
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from ai.enemy_ai import make_enemy_ai_fn
from ai.ollama_client import OllamaClient
from data.equipment_db import EQUIPMENT
from data.hero_rarity import HERO_SUMMON_WEIGHTS, rarity_multiplier, HERO_RARITY_COLOR, MAX_STARS, shard_cost_for_next_star, star_display
from data.items_db import ITEMS, STARTING_INVENTORY
from data.skills_db import SKILLS
from data.summon_pool import (
    CHARACTER_SUMMON_COST, CHARACTER_SUMMON_COST_X10,
    EQUIPMENT_SUMMON_COST, EQUIPMENT_SUMMON_COST_X10, SUMMON_X10_COUNT,
)
from engine.actions import Action
from engine.battle import BattleEngine
from engine import formulas
from engine.combatant import Combatant
from data.bosses import BOSSES, BOSS_SKILLS, WORLD_BOSSES
from data.leveling import apply_growth, TALENT_POINT_INTERVAL
from engine.skills import MAX_SKILL_RANK, power_at_rank, mp_cost_at_rank, status_duration_bonus_at_rank
from game.boss_script import BossRunner
from game.twins_fight import TwinsRunner, build_twin_members
from engine.equipment import SLOTS, RARITIES as EQUIP_RARITIES, class_can_equip
from game.equipment_instances import bonus_text as inst_bonus_text, resolve_equipment_db
from engine.types import ActionType, BattleResult, TargetType
from game import heroes as heroes_logic
from game import legacy as legacy_logic
from game import party as party_logic
from game import save_system
from game import shop as shop_logic
from data.classes import CLASS_ARCHETYPES
from data.enemy_pool import ENEMY_ARCHETYPES
from data.hero_skills import skill_ids_for, STAPLE_SKILL_INDEX
from data.hero_lore import HERO_LORE
from data.leveling import MAX_LEVEL
from data.summon_pool import RECRUITABLE_ROSTER
from game.battle_setup import (MONSTER_STAT_SCALE, BattleSetup, apply_squad_formations, build_battle,
                               build_enemy_combatant, build_hero_enemy_combatant, _hero_enemy_id,
                               party_average_level)
from game import renown as renown_logic
from game import debug_tools
from game import ladder as ladder_logic
from game import world as world_logic
from data.world_data import WORLD_MAPS, START_MAP
from game.player_state import PlayerState
from game.roster import PlayerCharacter
from game.rewards import compute_battle_rewards, reward_multiplier, roll_hero_enemy_shard_drops
from game.summon import summon_character_batch, summon_equipment_batch, summon_common_batch
from data.summon_pool import (COMMON_SUMMON_COST, COMMON_SUMMON_COST_X10, COMMON_SUMMON_WEIGHTS, TARGET_SHARE,
                              TICKET_LABEL, EQUIPMENT_RARITY_WEIGHTS, EQUIPMENT_SHARD_SUMMON_COST,
                              EQUIPMENT_SALVAGE_YIELD)
from game.rewards import roll_ticket_drops, roll_equipment_shard_drops

try:
    import websockets
except ImportError:
    print("Missing dependency. Run this first:\n    pip install websockets")
    sys.exit(1)

HTTP_HOST, HTTP_PORT = "127.0.0.1", 8767
WS_HOST, WS_PORT = "127.0.0.1", 8766

HTML_DIR = PROJECT_ROOT / "html_hub"
BATTLE_HTML_DIR = PROJECT_ROOT / "html_battle"
WORLD_HTML_DIR = PROJECT_ROOT / "html_overworld"
DATA_DIR = PROJECT_ROOT / "data"
ASSETS_DIR = PROJECT_ROOT / "Assets"  # sibling of data/ -- Music/, SFX/, and walking/ live here, served under /assets/ too

# Still hardcoded -- see the module docstring. Real Party Select/Battle Setup
# screens (not yet built in HTML) are what would let the player choose these;
# until then every battle is a "normal", 2-opponent encounter, same as
# battle_server.py used before this merge.
DEMO_DIFFICULTY = "normal"
MIN_ENEMIES, MAX_ENEMIES = 1, 4  # each fight rolls its own enemy party size

# Enemy scaling, applied to every enemy after it is built. d = |heroes - enemies|:
#   enemies outnumbered (heroes > enemies, "boss" fights): HP +100% per d, other stats +5% per d
#   enemies outnumber heroes:                             HP -10% per d, other stats -5% per d
#   chain bonus: x1.10 per extra battle in a win streak, compounding, on all scaled stats.
# Only HP/ATK/DEF/MAG/RES are scaled (MP/SPD/LUK are left alone).
SCALED_ENEMY_STATS = ("max_hp", "atk", "def_", "mag", "res")
CHAIN_BONUS_PER_WIN = 0.10
SIZE_UP_HP, SIZE_UP_OTHER = 1.00, 0.05      # per extra hero
SIZE_DOWN_HP, SIZE_DOWN_OTHER = 0.10, 0.05  # per extra enemy


def enemy_scale_factors(num_heroes: int, num_enemies: int, wins: int):
    """Returns (hp_size_mult, other_size_mult, chain_mult)."""
    d = num_heroes - num_enemies
    if d >= 0:
        hp, other = 1 + SIZE_UP_HP * d, 1 + SIZE_UP_OTHER * d
    else:
        hp, other = 1 + SIZE_DOWN_HP * d, 1 + SIZE_DOWN_OTHER * d   # d negative
    chain = (1 + CHAIN_BONUS_PER_WIN) ** max(0, wins)
    return max(0.05, hp), max(0.05, other), chain


def apply_enemy_scaling(setup, wins: int = 0):
    hp_m, other_m, chain = enemy_scale_factors(setup.num_heroes, setup.num_enemies, wins)
    setup._enemy_scale = (hp_m, other_m, chain)
    for e in setup.enemies:
        st = e.base_stats
        for name in SCALED_ENEMY_STATS:
            m = (hp_m if name == "max_hp" else other_m) * chain
            setattr(st, name, max(1, round(getattr(st, name) * m)))
        e.hp = st.max_hp
    return setup


def build_scaled_battle(party, wins: int = 0, equipment_db=None, legacy_db=None):
    # Bosses you have already beaten (every rank below yours) can turn up as random encounters.
    equipment_db = EQUIPMENT if equipment_db is None else equipment_db
    boss_id = renown_logic.pick_pool_boss(player_state)
    if boss_id in BOSSES:
        return _build_rank_boss_setup(BOSSES[boss_id], party, challenge=False, equipment_db=equipment_db, legacy_db=legacy_db)
    n = random.randint(MIN_ENEMIES, MAX_ENEMIES)
    setup = build_battle(party, equipment_db, DEMO_DIFFICULTY, n, legacy_db=legacy_db)
    return apply_enemy_scaling(setup, wins)


def _build_rank_boss_setup(bdef, party_pcs, challenge: bool, equipment_db=None, legacy_db=None):
    """A boss fight for the ladder: level = average party level + the boss's own offset."""
    level = max(1, min(MAX_LEVEL, round(party_average_level(party_pcs)) + bdef.level_offset))
    setup = _build_boss_setup(bdef, party_pcs, level, equipment_db=equipment_db, legacy_db=legacy_db)
    setup._rank_challenge = challenge
    return setup

SKILLS.update(BOSS_SKILLS)  # boss-only skills live in data/bosses.py

CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".js": "application/javascript",
                  ".css": "text/css", ".png": "image/png", ".webp": "image/webp",
                  ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".json": "application/json",
                  ".mp3": "audio/mpeg", ".wav": "audio/wav"}

# A brand-new save needs *some* starting hero and there's no character
# creation screen in HTML yet -- same stopgap the battle side takes below
# with hardcoded difficulty/opponent count, just for the roster's first
# hero instead. Real character creation replaces this the same turn
# Title/New Game gets built.
DEFAULT_STARTER_NAME = "Garrick"
DEFAULT_STARTER_CLASS = "tank"


def _default_new_game() -> PlayerState:
    hero = PlayerCharacter(name=DEFAULT_STARTER_NAME, class_id=DEFAULT_STARTER_CLASS)
    return PlayerState.new_game(hero)


# One process-wide PlayerState, loaded once at startup and saved back out on
# every mutating action -- hub actions, Heroes actions, Summon pulls, AND
# now battle rewards, all under this one lock. This is the whole point of
# the merge: there is exactly one in-memory copy of the save, so nothing
# can silently clobber anything else's changes.
_state_lock = threading.Lock()
if save_system.save_exists():
    player_state = save_system.load_game()
else:
    player_state = _default_new_game()
    save_system.save_game(player_state)
# A save from before the overworld existed (or one that somehow names a map that's since been
# removed) has no valid world_map -- drop it at the starting map's spawn point, same as a brand-new
# game gets from PlayerState.new_game().
world_logic.ensure_spawned(player_state, WORLD_MAPS, START_MAP)


def _resolved_equipment_db():
    """EQUIPMENT (the base catalog) plus one synthetic entry per live equipment instance the player
    owns (game/equipment_instances.py) -- pass this wherever a real, owned PlayerCharacter's stats or
    combat is being built (Heroes/Party serialization, real battles) so an instance id in `equipped`
    resolves to that specific copy's rolled bonus stats. Debug-battle throwaway characters never own
    gear, so they can keep using raw EQUIPMENT -- see _build_debug_battle."""
    return resolve_equipment_db(EQUIPMENT, player_state.equipment_instances)


# ----------------------------------------------------------------------
# Serialization helpers -- Hub
# ----------------------------------------------------------------------
def _rarity_hex(rarity: str) -> str:
    return "#%02x%02x%02x" % HERO_RARITY_COLOR.get(rarity, (190, 190, 195))


def _serialize_character_summary(c: PlayerCharacter) -> dict:
    """The hub's compact per-hero summary -- name/class/level/rarity/stars/
    gear-count only, no full stat block (that's Heroes' job, below)."""
    return {
        "id": c.id,
        "name": c.name,
        "class_name": c.archetype.name,
        "level": c.level,
        "rarity": c.rarity,
        "rarity_color": _rarity_hex(c.rarity),
        "stars_display": star_display(c.stars),
        "stars": c.stars,
        "gear_equipped": sum(1 for v in c.equipped.values() if v),
        "gear_total": len(c.equipped),
        "portrait": f"/assets/Portraits/{c.name}.webp",
        # Wounded (game/legacy.py's apply_wound_penalty): benched, can't be picked for a party, until
        # this hits 0 or they're healed for gold (Heroes page).
        "wounded_runs_remaining": c.wounded_runs_remaining,
        "is_wounded": c.is_wounded,
        # Battle formation row (engine/formation.py): "front"/"middle"/"rear", set on Party Select
        # and persisted on the hero (game/roster.py) until changed.
        "formation": c.formation,
        "is_melee": c.archetype.is_melee,
    }


def _any_hero_needs_attention() -> bool:
    """Whether ANY hero in the full roster (not just the active party) has a star-upgrade ready or
    a better item sitting in the stash -- drives the red dot on the hub's Heroes nav button. Reuses
    _hero_upgrade_info per hero (same check the Heroes page runs for each roster card / the detail
    page's own badges), stopping at the first hit rather than scoring the whole roster every poll."""
    edb = _resolved_equipment_db()
    for c in player_state.characters:
        info = _hero_upgrade_info(c, edb)
        if info["can_rank_up"] or info["upgrade_slots"] or info["has_talent_points"]:
            return True
    return False


def _serialize_hub_state() -> dict:
    party_chars = party_logic.active_party_characters(player_state)
    bench_count = len(player_state.characters) - len(party_chars)
    return {
        "money": player_state.money,
        "gems": player_state.gems,
        "tickets": dict(player_state.tickets),
        "equipment_shards": player_state.equipment_shards,
        "party": [_serialize_character_summary(c) for c in party_chars],
        "bench_count": bench_count,
        "roster_count": len(player_state.characters),
        "debug": config.DEBUG,
        "debug_gem_grant": config.DEBUG_GEM_GRANT,
        # Same origin, same process now -- just a path, not a different port.
        "battle_url": "/party",
        "world_url": "/world",
        "ladder": _serialize_ladder(),
        "heroes_need_attention": _any_hero_needs_attention(),
    }


def _world_player_sprite() -> dict:
    """The overworld avatar reuses the active party leader's battle sheet (same fallback-to-Draven
    convention the battle screen itself uses for a hero with no sheet of its own -- see
    html_battle/index.html's loadSheet), so no separate "walk sprite" art is needed for this pass."""
    party_chars = party_logic.active_party_characters(player_state)
    leader = party_chars[0] if party_chars else (player_state.characters[0] if player_state.characters else None)
    return {"name": leader.name if leader else "Hero", "sprite": leader.name if leader else "Draven"}


def _serialize_world_state() -> dict:
    current = WORLD_MAPS.get(player_state.world_map) or WORLD_MAPS[START_MAP]
    return {
        "map": current.serialize(),
        "player": {
            "map": player_state.world_map, "x": player_state.world_x, "y": player_state.world_y,
            "facing": player_state.world_facing, **_world_player_sprite(),
        },
    }


def _serialize_debug_menu() -> dict:
    """Everything the hub debug menu needs: the catalogs to pick from and what you currently own."""
    return {
        "heroes": [{"name": h.name, "class_id": h.class_id, "rarity": h.rarity} for h in RECRUITABLE_ROSTER],
        "classes": [{"id": k, "name": v.name} for k, v in CLASS_ARCHETYPES.items()],
        "rarities": list(debug_tools.HERO_RARITIES),
        "equipment": [{"id": e.id, "name": e.name, "slot": e.slot, "subtype": e.subtype, "rarity": e.rarity}
                      for e in EQUIPMENT.values()],
        "items": [{"id": i.id, "name": i.name} for i in ITEMS.values()],
        "max_level": MAX_LEVEL, "max_stars": MAX_STARS,
        "max_rank": len(renown_logic.RANK_BOSSES) + 1,
        "roster": [{"id": c.id, "name": c.name, "class": c.archetype.name, "level": c.level,
                    "stars": c.stars, "shards": c.shards, "rarity": c.rarity} for c in player_state.characters],
        "rank": player_state.rank, "renown": player_state.renown,
        "gate": renown_logic.gate_for_rank(player_state.rank) if renown_logic.has_next_boss(player_state) else None,
    }


def _serialize_ladder() -> dict:
    """Rank/renown for the hub: your rank, the renown meter, and the NEXT boss (locked until the meter
    reaches the gate). `next_boss` is None once every ranked boss has been beaten."""
    st = player_state
    boss_id = renown_logic.boss_id_for_rank(st.rank)
    bdef = BOSSES.get(boss_id) if boss_id else None
    gate = renown_logic.gate_for_rank(st.rank) if bdef else None
    return {
        "rank": st.rank,
        "rank_name": renown_logic.rank_name(st.rank),
        "renown": st.renown,
        "gate": gate,
        "cap": renown_logic.renown_cap(st.rank) if bdef else None,
        "unlocked": bool(bdef) and renown_logic.can_challenge(st),
        "next_boss": ({"id": bdef.id, "name": bdef.name,
                       "portrait": ("/assets/" + bdef.portrait) if bdef.portrait else None,
                       "rank": st.rank} if bdef else None),
        "pool": [BOSSES[b].name for b in renown_logic.pool_boss_ids(st) if b in BOSSES],
    }


# ----------------------------------------------------------------------
# Serialization helpers -- Heroes
# ----------------------------------------------------------------------
def _serialize_equipped_slot(item_id, equipment_db) -> dict:
    if not item_id:
        return None
    item = equipment_db.get(item_id)
    if not item:
        return {"id": item_id, "name": item_id, "slot": None, "subtype": None, "rarity": None, "bonus_text": ""}
    return {"id": item.id, "name": item.name, "slot": item.slot, "subtype": item.subtype, "rarity": item.rarity,
            "bonus_text": item.bonus_text()}


EQUIP_RARITY_RANK: Dict[str, int] = {r: i for i, r in enumerate(EQUIP_RARITIES)}


def _hero_upgrade_info(c: PlayerCharacter, equipment_db) -> dict:
    """Whether this hero can star-upgrade right now (enough shards already banked), and which
    equipped slots have a strictly-better item sitting unused in the stash -- drives the red-dot
    notification on the Heroes nav button, the Heroes roster cards, and the detail page's Upgrade
    Star button / equipped-slot rows. "Better" means a higher rarity tier first, and a higher total
    flat stat bonus as the tiebreak within the same tier -- gear power in this game is rarity-led,
    same ranking data/equipment_db.py / engine/equipment.py's RARITIES already uses everywhere else."""
    next_cost = None if c.stars >= MAX_STARS else shard_cost_for_next_star(c.rarity, c.stars)
    can_rank_up = next_cost is not None and c.shards >= next_cost
    # Unspent talent points (the skill-rank system) are the same kind of "banked resource ready to
    # spend" as can_rank_up above -- folded into the same notification info rather than a parallel
    # check, so the hub nav dot / roster card dot / detail page badges all pick it up for free.
    has_talent_points = c.talent_points_available() > 0

    def power(item):
        return (EQUIP_RARITY_RANK.get(item.rarity, 0), sum(item.stat_bonuses.values()))

    archetype = c.archetype
    upgrade_slots = []
    for slot in SLOTS:
        current_id = c.equipped.get(slot)
        current_item = equipment_db.get(current_id) if current_id else None
        current_power = power(current_item) if current_item else (-1, 0)
        for instance_id in player_state.equipment_stash:
            if instance_id == current_id:
                continue
            item = equipment_db.get(instance_id)
            if not item or item.slot != slot:
                continue
            if not class_can_equip(item, archetype.weapon_types, archetype.offhand_types, archetype.armor_weight):
                continue
            if power(item) > current_power:
                upgrade_slots.append(slot)
                break
    return {"can_rank_up": can_rank_up, "upgrade_slots": upgrade_slots, "has_talent_points": has_talent_points}


def _serialize_hero_skills(c: PlayerCharacter) -> list:
    """This hero's actual 4-skill kit (data/hero_skills.py's per-hero overrides,
    same source the battle engine builds their Combatant from), with the full
    Skill fields the Heroes detail page's ability tooltips need. Each entry
    is flagged "shared": whether it's the one staple move data/hero_skills.py
    leaves shared across the whole class, vs. one of this hero's own three --
    lets the UI visually call out which slot is which."""
    staple_index = STAPLE_SKILL_INDEX.get(c.class_id, 0)
    out = []
    for index, sid in enumerate(skill_ids_for(c.name, c.class_id)):
        sk = SKILLS.get(sid)
        if not sk:
            continue
        rank = c.skill_rank(sid)
        out.append({
            "id": sk.id, "name": sk.name,
            # mp_cost/power below are RANK-SCALED (this hero's actual current numbers -- see
            # engine/skills.py's mp_cost_at_rank/power_at_rank); base_mp_cost/base_power are the
            # unscaled rank-1 numbers, and next_mp_cost/next_power preview the following rank (None at
            # MAX_SKILL_RANK) so the Heroes detail page can show a "rank up" comparison.
            "mp_cost": mp_cost_at_rank(sk, rank), "power": round(power_at_rank(sk, rank), 3),
            "base_mp_cost": sk.mp_cost, "base_power": sk.power,
            "next_mp_cost": mp_cost_at_rank(sk, rank + 1) if rank < MAX_SKILL_RANK else None,
            "next_power": round(power_at_rank(sk, rank + 1), 3) if rank < MAX_SKILL_RANK else None,
            "rank": rank, "max_rank": MAX_SKILL_RANK,
            "kind": sk.kind,
            "element": sk.element.value if hasattr(sk.element, "value") else sk.element,
            "target": sk.target.value if hasattr(sk.target, "value") else sk.target,
            "status_to_apply": sk.status_to_apply, "status_chance": sk.status_chance,
            "lifesteal": sk.lifesteal, "description": sk.description,
            "shared": index == staple_index,
            # Extra turns of status duration this rank grants, for skills that apply one (a pure buff
            # like Iron Stance has power=0, so this -- not power -- is how IT gets "more potent" per
            # rank; see engine/skills.py's status_duration_bonus_at_rank). None for a skill with no
            # status at all, so the UI knows not to show a duration line for it.
            "status_duration_bonus": status_duration_bonus_at_rank(rank) if sk.status_to_apply else None,
            "next_status_duration_bonus": (
                status_duration_bonus_at_rank(rank + 1)
                if sk.status_to_apply and rank < MAX_SKILL_RANK else None
            ),
        })
    return out


def _serialize_equipped_legacy(legacy_id: str) -> Optional[dict]:
    item = player_state.legacy_instances.get(legacy_id)
    if not item:
        return None
    return {"instance_id": legacy_id, "name": item.name, "hero_name": item.hero_name,
            "hero_class_id": item.hero_class_id, "rarity": item.rarity,
            "rarity_color": _rarity_hex(item.rarity), "bonus_text": item.bonus_text()}


def _serialize_hero_full(c: PlayerCharacter, equipment_db) -> dict:
    stats = c.effective_stats(equipment_db, player_state.legacy_instances)
    next_cost = None if c.stars >= MAX_STARS else shard_cost_for_next_star(c.rarity, c.stars)
    archetype = c.archetype
    return {
        "id": c.id,
        "name": c.name,
        "class_name": archetype.name,
        "level": c.level,
        # This hero's own rarity-based ceiling (data/hero_rarity.py's level_cap_for) -- once level
        # reaches this, they're eligible to be sacrificed for a legacy item (game/legacy.py's
        # sacrifice_hero); the Heroes page shows the Sacrifice action once is_level_maxed is true.
        "level_cap": c.level_cap,
        "is_level_maxed": c.is_level_maxed,
        # Wounded (game/legacy.py's apply_wound_penalty): can't be sacrificed or fielded until this
        # clears (waited out or healed for gold -- wound_heal_cost, by this hero's rarity).
        "wounded_runs_remaining": c.wounded_runs_remaining,
        "is_wounded": c.is_wounded,
        "wound_heal_cost": legacy_logic.WOUND_HEAL_COST.get(c.rarity, legacy_logic.WOUND_HEAL_COST["common"]),
        "rarity": c.rarity,
        "rarity_color": _rarity_hex(c.rarity),
        "stars": c.stars,
        "max_stars": MAX_STARS,
        "stars_display": star_display(c.stars),
        "shards": c.shards,
        "shard_cost_next": next_cost,
        "portrait": f"/assets/Portraits/{c.name}.webp",
        "class_id": c.class_id,
        "talent_points_available": c.talent_points_available(),
        "talent_points_earned": c.talent_points_earned(),
        "talent_point_interval": TALENT_POINT_INTERVAL,
        "stats": {
            "max_hp": stats.max_hp, "max_mp": stats.max_mp, "atk": stats.atk,
            "def_": stats.def_, "mag": stats.mag, "res": stats.res,
            "spd": stats.spd, "luk": stats.luk,
        },
        "skills": _serialize_hero_skills(c),
        "lore": HERO_LORE.get(c.name, ""),
        **_hero_upgrade_info(c, equipment_db),
        "equipped": {slot: _serialize_equipped_slot(c.equipped.get(slot), equipment_db) for slot in SLOTS},
        # What this class can wear -- lets the Heroes UI grey out stash items this hero hard-can't-equip.
        "weapon_types": sorted(archetype.weapon_types),
        "offhand_types": sorted(archetype.offhand_types),
        "armor_weight": archetype.armor_weight,
        # Legacy items (game/legacy.py): what fallen heroes left behind, equipped here for a % stat
        # bonus. legacy_slots is 3 + one per rarity step above common (THIS hero's own rarity).
        "legacy_slots": c.legacy_slots,
        "equipped_legacies": [x for x in (_serialize_equipped_legacy(lid) for lid in c.equipped_legacies) if x],
    }


def _serialize_stash(equipment_db) -> list:
    """One entry per owned INSTANCE (not grouped by base item any more -- two copies of the same base
    item can have different rolled bonus stats), newest-looking-up-in-catalog-first is irrelevant here
    since stash order is just insertion order."""
    stash = []
    for instance_id in player_state.equipment_stash:
        item = equipment_db.get(instance_id)
        if not item:
            continue
        inst = player_state.equipment_instances.get(instance_id)
        stash.append({
            "instance_id": instance_id, "base_id": inst.base_id if inst else item.id,
            "name": item.name, "slot": item.slot, "subtype": item.subtype, "rarity": item.rarity,
            "bonus_text": item.bonus_text(),
            "is_rolled": bool(inst and inst.bonus_stats),
            "salvage_value": EQUIPMENT_SALVAGE_YIELD.get(item.rarity, 0),
        })
    return stash


def _serialize_legacy_stash() -> list:
    out = []
    for legacy_id in player_state.legacy_stash:
        item = player_state.legacy_instances.get(legacy_id)
        if not item:
            continue
        out.append({"instance_id": legacy_id, "name": item.name, "hero_name": item.hero_name,
                    "hero_class_id": item.hero_class_id, "rarity": item.rarity,
                    "rarity_color": _rarity_hex(item.rarity), "bonus_text": item.bonus_text()})
    return out


def _serialize_heroes_state() -> dict:
    edb = _resolved_equipment_db()
    return {
        "roster": [_serialize_hero_full(c, edb) for c in player_state.characters],
        "stash": _serialize_stash(edb),
        "legacy_stash": _serialize_legacy_stash(),
        "slots": list(SLOTS),
        "equipment_shards": player_state.equipment_shards,
        # For the Sacrifice/Heal Wound actions' affordability checks -- the Heroes page has never
        # needed a money readout before this.
        "money": player_state.money,
    }


# ----------------------------------------------------------------------
# Serialization helpers -- Shop / Party Select
# ----------------------------------------------------------------------
def _serialize_shop_state() -> dict:
    items = [
        {"id": it.id, "name": it.name, "description": it.description, "cost": it.cost,
         "owned": player_state.inventory.get(it.id, 0)}
        for it in ITEMS.values() if it.cost > 0
    ]
    # "owned" = how many un-rolled (shop-bought/debug) instances of this base item are sitting in the
    # stash right now -- the shop only ever sells/grants un-rolled copies, so this stays a plain count.
    owned_counts = {}
    for iid in player_state.equipment_stash:
        inst = player_state.equipment_instances.get(iid)
        if inst:
            owned_counts[inst.base_id] = owned_counts.get(inst.base_id, 0) + 1
    equipment = [
        {"id": e.id, "name": e.name, "slot": e.slot, "subtype": e.subtype, "rarity": e.rarity, "cost": e.cost,
         "bonus_text": e.bonus_text(), "description": e.description,
         "owned": owned_counts.get(e.id, 0)}
        for e in EQUIPMENT.values() if e.cost > 0
    ]
    return {"money": player_state.money, "items": items, "equipment": equipment, "slots": list(SLOTS),
            "equipment_shards": player_state.equipment_shards}


def _serialize_party_hero(c: PlayerCharacter, equipment_db) -> dict:
    st = c.effective_stats(equipment_db, player_state.legacy_instances)
    return {**_serialize_character_summary(c),
            "stats": {"max_hp": st.max_hp, "max_mp": st.max_mp, "atk": st.atk, "mag": st.mag}}


def _serialize_party_state() -> dict:
    edb = _resolved_equipment_db()
    return {
        "roster": [_serialize_party_hero(c, edb) for c in player_state.characters],
        "selected": party_logic.default_party_ids(player_state),
        "max_size": party_logic.MAX_PARTY_SIZE,
        "min_size": party_logic.MIN_PARTY_SIZE,
        "challenge": BOSSES[pending_challenge].name if pending_challenge in BOSSES else None,
        "ladder": bool(pending_ladder),
    }


# ----------------------------------------------------------------------
# Serialization helpers -- Summon
# ----------------------------------------------------------------------
def _serialize_summon_state() -> dict:
    return {
        "gems": player_state.gems,
        "gold": player_state.money,
        "tickets": dict(player_state.tickets),
        "ticket_labels": TICKET_LABEL,
        "equipment_shards": player_state.equipment_shards,
        "heroes": [{"name": h.name, "class_id": h.class_id, "rarity": h.rarity,
                    "owned": any(c.name == h.name for c in player_state.characters)} for h in RECRUITABLE_ROSTER],
        "common": {"cost_1x": COMMON_SUMMON_COST, "cost_10x": COMMON_SUMMON_COST_X10,
                   "odds": dict(COMMON_SUMMON_WEIGHTS)},
        "premium_odds": {k: float(v) for k, v in HERO_SUMMON_WEIGHTS.items()},
        "equipment_odds": dict(EQUIPMENT_RARITY_WEIGHTS),
        "target_share": TARGET_SHARE,
        "roster_size": len(player_state.characters),
        "costs": {
            "character_1x": CHARACTER_SUMMON_COST, "character_10x": CHARACTER_SUMMON_COST_X10,
            "equipment_1x": EQUIPMENT_SUMMON_COST, "equipment_10x": EQUIPMENT_SUMMON_COST_X10,
            "equipment_shard_1x": EQUIPMENT_SHARD_SUMMON_COST,
            "equipment_shard_10x": EQUIPMENT_SHARD_SUMMON_COST * SUMMON_X10_COUNT,
        },
        "x10_count": SUMMON_X10_COUNT,
    }


def _serialize_character_results(results) -> list:
    return [
        {"rarity": r.rarity, "name": r.character.name, "class_id": r.character.class_id,
         "is_duplicate": r.is_duplicate, "shards_gained": r.shards_gained, "message": r.message}
        for r in results
    ]


def _serialize_equipment_results(results) -> list:
    return [
        {"rarity": r.rarity, "name": r.item.name, "slot": r.item.slot, "subtype": r.item.subtype,
         "instance_id": r.instance.instance_id, "bonus_text": inst_bonus_text(r.instance, EQUIPMENT),
         "message": r.message}
        for r in results
    ]


# ----------------------------------------------------------------------
# Serialization helpers -- Battle (moved over from battle_server.py as-is)
# ----------------------------------------------------------------------
def _sprite_name_for(combatant_name: str) -> str:
    # Hero rivals are named "Rival <Name>" (see game/battle_setup.py) so the
    # log/UI never confuses them with an owned party member -- strip that
    # prefix for sprite lookup, since the art (or its Draven fallback) is
    # keyed by the underlying hero's own name.
    return combatant_name[len("Rival "):] if combatant_name.startswith("Rival ") else combatant_name


_DEBUG_STAT_KEYS = ("atk", "def_", "mag", "res", "spd", "luk")


def _serialize_combatant(c) -> dict:
    d = c.to_public_dict()
    d["sprite_name"] = _sprite_name_for(c.name)
    if config.DEBUG:
        # Debug stat boxes: base (equipment/perk-inclusive) vs effective (with status multipliers), plus
        # each active status and the multipliers it contributes.
        d["stats"] = {k: {"base": getattr(c.base_stats, k), "eff": round(c.effective_stat(k), 1)} for k in _DEBUG_STAT_KEYS}
        d["status_detail"] = [{"key": s.key, "name": s.name, "duration": s.duration, "mods": dict(s.stat_mods)}
                              for s in c.status_effects]
        d["resist"] = {getattr(e, "value", str(e)): m for e, m in (getattr(c, "resistances", None) or {}).items()}
    return d


def _serialize_battle_state(engine: BattleEngine) -> dict:
    roles = getattr(engine, "_roles", {})  # hero name -> class_id (tank/melee_dps/ranged_dps/mage/support)
    return {
        "round": engine.round_number,
        "party": [{**_serialize_combatant(c), "role": roles.get(c.name),
                   "level": getattr(engine, "_levels", {}).get(c.name)} for c in engine.party],
        "enemies": [{**_serialize_combatant(c),
                     "level": getattr(engine, "_enemy_levels", {}).get(c.id, getattr(engine, "_enemy_level", None)),
                     "boss_sprite": getattr(engine, "_boss_sprites", {}).get(c.id)}
                    for c in engine.enemies],
        "debug": bool(config.DEBUG),
        "damage": dict(getattr(engine, "_damage", {})),  # combatant id -> total damage dealt this fight (debug graphs)
        "result": engine.result.value,
    }


def _boss_sprite_payloads(bdef, enemies) -> dict:
    """combatant id -> sprite config the browser needs. Single-sheet bosses (the Champion) send one
    url; multi-pose bosses send a `poses` table (see data/bosses.py's _pose)."""
    def payload(sp):
        out = {"scale": sp.get("scale", 1.0), "native_left": sp.get("native_left", False)}
        if "poses" in sp:
            out["poses"] = {name: {**cfg, "url": "/assets/" + cfg["file"]} for name, cfg in sp["poses"].items()}
        else:
            out.update({"url": "/assets/" + sp["file"], "idle_only": sp.get("idle_only", False)})
        return out
    if bdef.members:
        return {c.id: payload(m.sprite) for c, m in zip(enemies, bdef.members)}
    return {enemies[0].id: payload(bdef.sprite)}


def _is_melee_action(action: Action) -> bool:
    if action.type == ActionType.ATTACK:
        return True
    if action.type == ActionType.SKILL and action.skill_id in SKILLS:
        return SKILLS[action.skill_id].kind == "physical"
    return False


def _role_for_actor(actor, roles: dict, enemy_roles: dict):
    """actor.class_id/role lookup used only to pick a battle-screen animation -- roles maps hero
    name -> class_id for the party (engine._roles), enemy_roles maps enemy combatant id -> class_id
    for hero-recruit enemies (built from setup.enemy_hero_recruits, parallel to setup.enemies).
    Plain monster enemies (no recruit behind them) and anything else unmapped default to melee below."""
    if actor is None:
        return None
    return enemy_roles.get(actor.id) if getattr(actor, "is_enemy", False) else roles.get(actor.name)


def _anim_kind_for(action: Action, actor, roles: dict, enemy_roles: dict) -> str:
    """Richer replacement for the old is_melee boolean: tells the browser which battle-screen
    animation family to play (melee run-in, ranged/magic projectile + impact, heal glow, or a
    self/idle status pop) for this action. See html_battle/index.html's handleActionEvent()."""
    if action.type != ActionType.SKILL:
        # A plain ATTACK is always "physical" -- ranged_dps heroes (Rook & co.) still shoot it.
        role = _role_for_actor(actor, roles, enemy_roles)
        return "ranged" if role == "ranged_dps" else "melee"
    sk = SKILLS.get(action.skill_id)
    if sk is None:
        return "melee"
    if sk.kind == "magical":
        return "magic"
    if sk.kind == "heal":
        return "heal"
    if sk.kind == "status":
        return "status"
    if sk.kind == "physical":
        role = _role_for_actor(actor, roles, enemy_roles)
        return "ranged" if role == "ranged_dps" else "melee"
    return "melee"  # unknown/legacy skill kind -- safe default, matches the old behaviour


def _aoe_target_ids(engine: BattleEngine, actor, target_type: TargetType):
    """For a skill that hits more than one combatant (cleave, firestorm, prayer, holy_reset...),
    the extra ids the browser needs to show the effect landing on every target -- action.target_ids
    (from the client message) only ever carries the single id the player clicked, if any."""
    if target_type == TargetType.ALL_ENEMIES:
        return [c.id for c in engine.opposing_side(actor) if c.alive]
    if target_type == TargetType.ALL_ALLIES:
        return [c.id for c in engine.side_of(actor) if c.alive]
    if target_type == TargetType.ALL:
        return [c.id for c in list(engine.party) + list(engine.enemies) if c.alive]
    return None


def _action_from_message(actor_id: str, msg: dict) -> Action:
    kind = msg.get("action")
    target_id = msg.get("target_id")
    target_ids = [target_id] if target_id else []
    if kind == "attack":
        return Action(ActionType.ATTACK, actor_id, target_ids)
    if kind == "skill" and msg.get("skill_id"):
        return Action(ActionType.SKILL, actor_id, target_ids, skill_id=msg["skill_id"])
    if kind == "item" and msg.get("item_id"):
        return Action(ActionType.ITEM, actor_id, target_ids, item_id=msg["item_id"])
    if kind == "flee":
        return Action.flee(actor_id)
    return Action.defend(actor_id)  # unrecognized/missing -- safe default, never crashes the battle


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[hub_server:http]", fmt % args)

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # No explicit caching headers used to be sent at all, which left the browser free to use its
        # own heuristic caching for index.html/heroes.html/etc -- meaning a page reload could silently
        # keep running old JS after a file on disk changed. These are actively-edited dev assets, so
        # never let the browser cache them.
        if content_type in (CONTENT_TYPES[".html"], "application/javascript", "text/javascript"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict) -> None:
        self._send_bytes(status, json.dumps(payload).encode("utf-8"), "application/json")

    def _send_html_file(self, directory: Path, filename: str) -> None:
        path = directory / filename
        if not path.is_file():
            self._send_bytes(404, b"not found", "text/plain")
            return
        self._send_bytes(200, path.read_bytes(), CONTENT_TYPES[".html"])

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return {}

    # ------------------------------------------------------------------
    def do_GET(self):
        global debug_battle, pending_challenge, pending_ladder
        # self.path is the raw request target and can carry a query string (e.g. the overworld's
        # "/battle?return=world" -- see html_overworld/index.html) -- every route match below needs
        # the path alone, or "/battle?return=world" != "/battle" falls through to a 404 (which is
        # exactly what happened before this fix: talking to the dungeon guardian, or triggering any
        # wild encounter, 404'd instead of opening the battle screen).
        route_path = self.path.split("?", 1)[0]
        if route_path in ("/", "/index.html"):
            self._send_html_file(HTML_DIR, "index.html")
            return
        if route_path in ("/heroes", "/heroes/", "/heroes/index.html"):
            self._send_html_file(HTML_DIR, "heroes.html")
            return
        if route_path in ("/summon", "/summon/", "/summon/index.html"):
            self._send_html_file(HTML_DIR, "summon.html")
            return
        if route_path in ("/shop", "/shop/", "/shop/index.html"):
            self._send_html_file(HTML_DIR, "shop.html")
            return
        if route_path in ("/party", "/party/", "/party/index.html"):
            debug_battle = None  # normal battle flow -- drop any pending debug setup
            self._send_html_file(HTML_DIR, "party.html")
            return
        if route_path in ("/debug", "/debug/", "/debug/index.html") and config.DEBUG:
            self._send_html_file(HTML_DIR, "debug.html")
            return
        if route_path == "/api/debug/options" and config.DEBUG:
            self._send_json(200, _serialize_debug_options())
            return
        if route_path == "/api/debug/menu" and config.DEBUG:
            with _state_lock:
                self._send_json(200, _serialize_debug_menu())
            return
        if route_path == "/api/shop":
            with _state_lock:
                self._send_json(200, _serialize_shop_state())
            return
        if route_path == "/api/party":
            with _state_lock:
                self._send_json(200, _serialize_party_state())
            return
        if route_path in ("/battle", "/battle/", "/battle/index.html"):
            self._send_html_file(BATTLE_HTML_DIR, "index.html")
            return
        if route_path in ("/world", "/world/", "/world/index.html"):
            self._send_html_file(WORLD_HTML_DIR, "index.html")
            return
        if route_path == "/api/world/state":
            with _state_lock:
                self._send_json(200, _serialize_world_state())
            return
        if route_path == "/api/state":
            with _state_lock:
                pending_challenge = None   # back on the hub: any half-started boss challenge is abandoned
                pending_ladder = False
                self._send_json(200, _serialize_hub_state())
            return
        if route_path == "/api/heroes":
            with _state_lock:
                self._send_json(200, _serialize_heroes_state())
            return
        if route_path == "/api/summon/state":
            with _state_lock:
                self._send_json(200, _serialize_summon_state())
            return
        if route_path.startswith("/assets/"):
            rel = route_path[len("/assets/"):]
            # Music/, SFX/, and walking/ (the overworld's real 4-direction walk-cycle sheets --
            # see html_overworld/index.html) live under the sibling Assets/ folder (capital A),
            # not data/ -- same generic static-file serving, just a different root for those subtrees.
            root = ASSETS_DIR if rel.startswith(("Music/", "SFX/", "walking/")) else DATA_DIR
            path = (root / rel).resolve()
            if root.resolve() not in path.parents or not path.is_file():
                self._send_bytes(404, b"not found", "text/plain")
                return
            content_type = CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")
            self._send_bytes(200, path.read_bytes(), content_type)
            return
        self._send_bytes(404, b"not found", "text/plain")

    # ------------------------------------------------------------------
    def do_POST(self):
        global debug_battle
        if self.path == "/api/debug/setup" and config.DEBUG:
            cfg, err = _validate_debug_setup(self._read_json_body())
            if cfg is None:
                self._send_json(200, {"ok": False, "message": err})
            else:
                debug_battle = cfg
                self._send_json(200, {"ok": True, "message": "Debug battle ready."})
            return
        if self.path == "/api/debug/act" and config.DEBUG:
            self._handle_debug_act()
            return
        if self.path == "/api/action":
            self._handle_hub_action()
        elif self.path == "/api/heroes/upgrade_star":
            self._handle_upgrade_star()
        elif self.path == "/api/heroes/upgrade_skill":
            self._handle_upgrade_skill()
        elif self.path == "/api/heroes/equip":
            self._handle_equip()
        elif self.path == "/api/heroes/unequip":
            self._handle_unequip()
        elif self.path == "/api/heroes/salvage":
            self._handle_salvage_equipment()
        elif self.path == "/api/heroes/equip_legacy":
            self._handle_equip_legacy()
        elif self.path == "/api/heroes/unequip_legacy":
            self._handle_unequip_legacy()
        elif self.path == "/api/heroes/sacrifice":
            self._handle_sacrifice_hero()
        elif self.path == "/api/heroes/heal_wound":
            self._handle_heal_wound()
        elif self.path == "/api/shop/buy_item":
            self._handle_buy(shop_logic.buy_item, ITEMS, "item_id")
        elif self.path == "/api/shop/buy_equipment":
            self._handle_buy(shop_logic.buy_equipment, EQUIPMENT, "equipment_id")
        elif self.path == "/api/party/confirm":
            self._handle_party_confirm()
        elif self.path == "/api/ladder/start":
            self._handle_ladder_start()
        elif self.path == "/api/boss/challenge":
            self._handle_boss_challenge()
        elif self.path == "/api/summon/character":
            self._handle_summon_character()
        elif self.path == "/api/summon/equipment":
            self._handle_summon_equipment()
        elif self.path == "/api/world/move":
            self._handle_world_move()
        elif self.path == "/api/world/interact":
            self._handle_world_interact()
        else:
            self._send_bytes(404, b"not found", "text/plain")

    def _handle_debug_act(self) -> None:
        global pending_challenge, debug_battle
        msg = self._read_json_body()
        with _state_lock:
            ok, message = debug_tools.apply(player_state, msg, (DEFAULT_STARTER_NAME, DEFAULT_STARTER_CLASS))
            if ok:
                if msg.get("action") == "reset_game":
                    pending_challenge = None
                    pending_ladder = False
                    debug_battle = None
                save_system.save_game(player_state)
            self._send_json(200, {"ok": ok, "message": message, "hub": _serialize_hub_state(),
                                  "menu": _serialize_debug_menu()})

    def _handle_hub_action(self) -> None:
        msg = self._read_json_body()
        action = msg.get("action")
        with _state_lock:
            if action == "debug_add_gems" and config.DEBUG:
                player_state.add_rewards(0, config.DEBUG_GEM_GRANT)
                save_system.save_game(player_state)
                self._send_json(200, _serialize_hub_state())
                return
            if action == "save_and_quit":
                save_system.save_game(player_state)
                self._send_json(200, {"ok": True, **_serialize_hub_state()})
                return
        self._send_json(400, {"ok": False, "error": f"unrecognized action {action!r}"})

    def _handle_upgrade_star(self) -> None:
        msg = self._read_json_body()
        character_id = msg.get("character_id")
        with _state_lock:
            ok, message = heroes_logic.upgrade_star(player_state, character_id)
            if ok:
                save_system.save_game(player_state)
            self._send_json(200, {"ok": ok, "message": message, **_serialize_heroes_state()})

    def _handle_upgrade_skill(self) -> None:
        msg = self._read_json_body()
        character_id = msg.get("character_id")
        skill_id = msg.get("skill_id")
        with _state_lock:
            ok, message = heroes_logic.upgrade_skill_rank(player_state, character_id, skill_id, SKILLS)
            if ok:
                save_system.save_game(player_state)
            self._send_json(200, {"ok": ok, "message": message, **_serialize_heroes_state()})

    def _handle_equip(self) -> None:
        msg = self._read_json_body()
        character_id = msg.get("character_id")
        # instance_id is the current field name; equipment_id is accepted too so an un-updated client
        # (or a saved bookmark to the old API) still works during the transition.
        instance_id = msg.get("instance_id") or msg.get("equipment_id")
        with _state_lock:
            ok, message = shop_logic.equip_from_stash(player_state, character_id, instance_id, _resolved_equipment_db())
            if ok:
                save_system.save_game(player_state)
            self._send_json(200, {"ok": ok, "message": message, **_serialize_heroes_state()})

    def _handle_unequip(self) -> None:
        msg = self._read_json_body()
        character_id = msg.get("character_id")
        slot = msg.get("slot")
        with _state_lock:
            ok, message = shop_logic.unequip(player_state, character_id, slot, _resolved_equipment_db())
            if ok:
                save_system.save_game(player_state)
            self._send_json(200, {"ok": ok, "message": message, **_serialize_heroes_state()})

    def _handle_equip_legacy(self) -> None:
        msg = self._read_json_body()
        character_id = msg.get("character_id")
        instance_id = msg.get("instance_id")
        with _state_lock:
            ok, message = legacy_logic.equip_legacy(player_state, character_id, instance_id)
            if ok:
                save_system.save_game(player_state)
            self._send_json(200, {"ok": ok, "message": message, **_serialize_heroes_state()})

    def _handle_unequip_legacy(self) -> None:
        msg = self._read_json_body()
        character_id = msg.get("character_id")
        instance_id = msg.get("instance_id")
        with _state_lock:
            ok, message = legacy_logic.unequip_legacy(player_state, character_id, instance_id)
            if ok:
                save_system.save_game(player_state)
            self._send_json(200, {"ok": ok, "message": message, **_serialize_heroes_state()})

    def _handle_sacrifice_hero(self) -> None:
        msg = self._read_json_body()
        character_id = msg.get("character_id")
        with _state_lock:
            ok, message = legacy_logic.sacrifice_hero(player_state, character_id)
            if ok:
                # A sacrificed hero may have been the last one in the confirmed party -- refresh it
                # the same defensive way removing a hero already does elsewhere (game/debug_tools.py's
                # remove_hero), so a stale active_party entry never lingers.
                player_state.active_party = [cid for cid in player_state.active_party
                                              if cid in {c.id for c in player_state.characters}]
                save_system.save_game(player_state)
            self._send_json(200, {"ok": ok, "message": message, **_serialize_heroes_state()})

    def _handle_heal_wound(self) -> None:
        msg = self._read_json_body()
        character_id = msg.get("character_id")
        with _state_lock:
            ok, message = legacy_logic.heal_wound(player_state, character_id)
            if ok:
                save_system.save_game(player_state)
            self._send_json(200, {"ok": ok, "message": message, **_serialize_heroes_state()})

    def _handle_buy(self, buy_fn, db, key) -> None:
        msg = self._read_json_body()
        with _state_lock:
            ok, message = buy_fn(player_state, msg.get(key), db)
            if ok:
                save_system.save_game(player_state)
            self._send_json(200, {"ok": ok, "message": message, **_serialize_shop_state()})

    def _handle_ladder_start(self) -> None:
        global pending_ladder, pending_challenge, debug_battle
        with _state_lock:
            pending_ladder, pending_challenge, debug_battle = True, None, None
            self._send_json(200, {"ok": True, "url": "/party"})

    def _handle_boss_challenge(self) -> None:
        """Hub's boss card: starts the challenge flow (party select, then the fight) if the renown is there."""
        global pending_challenge, pending_ladder, debug_battle
        with _state_lock:
            boss_id = renown_logic.boss_id_for_rank(player_state.rank)
            if boss_id not in BOSSES or not renown_logic.can_challenge(player_state):
                self._send_json(200, {"ok": False, "message": "You are not renowned enough to challenge this boss yet."})
                return
            pending_challenge = boss_id
            pending_ladder = False
            debug_battle = None
            self._send_json(200, {"ok": True, "boss": BOSSES[boss_id].name, "url": "/party"})

    def _handle_party_confirm(self) -> None:
        msg = self._read_json_body()
        ids = msg.get("ids") or []
        formations = msg.get("formations") or {}
        with _state_lock:
            ok, message, party = party_logic.confirm_party(player_state, ids, formations=formations)
            if ok:
                save_system.save_game(player_state)
            self._send_json(200, {"ok": ok, "message": message})

    def _handle_summon_character(self) -> None:
        msg = self._read_json_body()
        count = msg.get("count", 1)
        pay = "ticket" if msg.get("pay") == "ticket" else "currency"
        if count not in (1, SUMMON_X10_COUNT):
            self._send_json(400, {"ok": False, "message": f"count must be 1 or {SUMMON_X10_COUNT}",
                                   "gems": player_state.gems, "results": []})
            return
        with _state_lock:
            if msg.get("mode") == "common":
                ok, message, results = summon_common_batch(player_state, count, pay=pay)
            else:
                ok, message, results = summon_character_batch(player_state, count,
                                                              target=msg.get("target") or None, pay=pay)
            if ok:
                save_system.save_game(player_state)
            self._send_json(200, {"ok": ok, "message": message, "gems": player_state.gems,
                                   **{k: v for k, v in _serialize_summon_state().items() if k in ("gold", "tickets")},
                                   "results": _serialize_character_results(results) if ok else []})

    def _handle_summon_equipment(self) -> None:
        msg = self._read_json_body()
        count = msg.get("count", 1)
        if count not in (1, SUMMON_X10_COUNT):
            self._send_json(400, {"ok": False, "message": f"count must be 1 or {SUMMON_X10_COUNT}",
                                   "gems": player_state.gems, "results": []})
            return
        with _state_lock:
            # Equipment summons no longer take Premium Tickets -- Andrew's request replaced that option
            # with equipment shards (data/summon_pool.py's EQUIPMENT_SHARD_SUMMON_COST). "currency" (gems)
            # is unchanged.
            pay = "shards" if msg.get("pay") == "shards" else "currency"
            ok, message, results = summon_equipment_batch(player_state, EQUIPMENT, count, pay=pay)
            if ok:
                save_system.save_game(player_state)
            self._send_json(200, {"ok": ok, "message": message, "gems": player_state.gems,
                                   **{k: v for k, v in _serialize_summon_state().items()
                                      if k in ("gold", "tickets", "equipment_shards")},
                                   "results": _serialize_equipment_results(results) if ok else []})

    def _handle_salvage_equipment(self) -> None:
        msg = self._read_json_body()
        instance_id = msg.get("instance_id")
        with _state_lock:
            ok, message = shop_logic.salvage_equipment(player_state, instance_id, _resolved_equipment_db())
            if ok:
                save_system.save_game(player_state)
            self._send_json(200, {"ok": ok, "message": message, **_serialize_heroes_state()})

    def _handle_world_move(self) -> None:
        global pending_world_encounter
        msg = self._read_json_body()
        direction = msg.get("direction")
        with _state_lock:
            result = world_logic.move_player(player_state, WORLD_MAPS, direction)
            if result.get("encounter"):
                # Consumed by the next battle's run_battle() -- see pending_world_encounter's own
                # comment -- so a wild overworld fight always ends after one battle instead of
                # offering the usual "keep fighting for a bigger multiplier" chain prompt.
                pending_world_encounter = True
            # Only worth a disk write when something durable changed -- a plain step (or a step that
            # just bumped a wall/NPC) is cheap to redo from wherever the last save left off, and saving
            # on literally every keypress would mean a disk write per footstep. A map change, a wild
            # encounter, or stepping into the Colosseum are all "leaving this spot for a while", so
            # those get persisted immediately, same as every other mutating action in this file.
            if result.get("map_changed") or result.get("encounter") or result.get("colosseum"):
                save_system.save_game(player_state)
            self._send_json(200, result)

    def _handle_world_interact(self) -> None:
        global pending_world_boss
        with _state_lock:
            result = world_logic.interact(player_state, WORLD_MAPS)
            if result.get("boss_id") in WORLD_BOSSES:
                pending_world_boss = result["boss_id"]
            self._send_json(200, result)


# ----------------------------------------------------------------------
# Debug battle: hand-picked heroes/enemies/levels, launched from /debug.
# Held here until the battle page connects; stays set so "Fight Again"
# (a page reload) repeats it. Visiting /party (the normal Enter Battle
# flow) clears it. Debug battles never touch rewards, XP, inventory or saves.
# ----------------------------------------------------------------------
debug_battle = None  # {"party": [{name, level}], "enemies": [{kind, id, level}]} or None
pending_ladder = False     # the hub's Ladder Mode button was pressed; consumed by the next battle
pending_challenge = None   # boss id the player started from the hub's boss card; consumed by the next battle
pending_world_boss = None  # boss id from talking to a boss NPC in the overworld (game/world.py);
                            # consumed by the next battle, same one-shot spirit as pending_challenge --
                            # see data/bosses.WORLD_BOSSES and _handle_world_interact below.
pending_world_encounter = False  # a wild encounter was rolled while walking the overworld (game/world.py);
                            # consumed by the next battle. Andrew asked for overworld fights to end after
                            # one battle instead of offering the Colosseum's usual "keep fighting for a
                            # bigger streak multiplier" prompt -- see run_battle's `from_world` below,
                            # which both this flag and pending_world_boss feed into.


_STAT_KEYS = ("max_hp", "max_mp", "atk", "def_", "mag", "res", "spd", "luk")


def _stat_block(stats) -> dict:
    return {k: getattr(stats, k) for k in _STAT_KEYS}


def _skill_names(ids) -> list:
    return [SKILLS[i].name if i in SKILLS else i for i in ids]


def _serialize_boss_option(b) -> dict:
    base, growth = _stat_block(b.base_stats), _stat_block(b.growth)
    base["max_hp"] = round(base["max_hp"] * b.hp_mult)      # fold the HP multiplier in so the menu's
    growth["max_hp"] = round(growth["max_hp"] * b.hp_mult)  # base + growth*(level-1) matches the fight
    return {"id": b.id, "name": b.name, "boss": True, "base": base, "growth": growth,
            "skills": _skill_names(b.skill_ids), "rewards_first": b.rewards_first, "rewards_repeat": b.rewards_repeat}


def _serialize_debug_options() -> dict:
    return {
        "max_level": MAX_LEVEL,
        "heroes": [{"name": h.name, "class_id": h.class_id, "class_name": CLASS_ARCHETYPES[h.class_id].name,
                    "rarity": h.rarity, "rarity_color": _rarity_hex(h.rarity),
                    "mult": rarity_multiplier(h.rarity),
                    "base": _stat_block(CLASS_ARCHETYPES[h.class_id].base_stats),
                    "growth": _stat_block(CLASS_ARCHETYPES[h.class_id].growth),
                    "skills": _skill_names(skill_ids_for(h.name, h.class_id))} for h in RECRUITABLE_ROSTER],
        "bosses": [_serialize_boss_option(b) for b in BOSSES.values()],
        "monster_scale": MONSTER_STAT_SCALE,
        "scaled_stats": list(SCALED_ENEMY_STATS),
        "size_scale": {"up_hp": SIZE_UP_HP, "up_other": SIZE_UP_OTHER, "down_hp": SIZE_DOWN_HP, "down_other": SIZE_DOWN_OTHER},
        "monsters": [{"id": a.id, "name": a.name, "monster": True, "base": _stat_block(a.base_stats),
                      "growth": _stat_block(a.growth), "skills": _skill_names(a.skill_ids)}
                     for a in ENEMY_ARCHETYPES.values()],
        "rivals": [{"name": h.name, "class_id": h.class_id, "class_name": CLASS_ARCHETYPES[h.class_id].name,
                    "rarity": h.rarity} for h in RECRUITABLE_ROSTER],
        "current": debug_battle,
    }


def _clamp_level(v) -> int:
    try:
        return max(1, min(int(v), MAX_LEVEL))
    except (TypeError, ValueError):
        return 1


def _validate_debug_setup(msg: dict):
    """Returns (cleaned_config, error_message)."""
    by_name = {h.name: h for h in RECRUITABLE_ROSTER}
    party, seen = [], set()
    for e in msg.get("party") or []:
        h = by_name.get(e.get("name"))
        if not h or h.name in seen:
            continue
        seen.add(h.name)
        party.append({"name": h.name, "level": _clamp_level(e.get("level"))})
    enemies = []
    for e in msg.get("enemies") or []:
        kind, eid = e.get("kind"), e.get("id")
        if kind == "monster" and eid in ENEMY_ARCHETYPES:
            enemies.append({"kind": "monster", "id": eid, "level": _clamp_level(e.get("level"))})
        elif kind == "hero" and eid in by_name:
            enemies.append({"kind": "hero", "id": eid, "level": _clamp_level(e.get("level"))})
        elif kind == "boss" and eid in BOSSES:
            enemies.append({"kind": "boss", "id": eid, "level": _clamp_level(e.get("level"))})
    bosses = [e for e in enemies if e["kind"] == "boss"]
    if bosses:
        enemies = bosses[:1]   # a boss fights alone
    if not (party_logic.MIN_PARTY_SIZE <= len(party) <= party_logic.MAX_PARTY_SIZE):
        return None, "Pick 1-4 heroes for your party."
    if not (1 <= len(enemies) <= 4):
        return None, "Pick 1-4 enemies."
    return {"party": party, "enemies": enemies, "rewards": bool(msg.get("rewards"))}, ""


def _build_boss_setup(bdef, party_pcs, level: int, equipment_db=None, legacy_db=None):
    """One-enemy BattleSetup for a boss at an explicit level (no party-size/chain scaling)."""
    equipment_db = EQUIPMENT if equipment_db is None else equipment_db
    if bdef.members:   # multi-unit boss (the Unbroken Pair): one enemy per member, all at the same level
        bosses = build_twin_members(bdef, level)
        setup = BattleSetup(
            difficulty="normal", enemy_level=level, enemy_ids=[m.key for m in bdef.members],
            party=[c.build_combatant(equipment_db, legacy_db) for c in party_pcs], enemies=bosses,
            enemy_hero_recruits=[None] * len(bosses),
        )
        setup._enemy_levels = {b.id: level for b in bosses}
        setup._boss_def = bdef
        return setup
    stats = apply_growth(bdef.base_stats, bdef.growth, level)
    stats.max_hp = max(1, round(stats.max_hp * bdef.hp_mult))
    boss = Combatant(name=bdef.name, is_enemy=True, base_stats=stats, skill_ids=list(bdef.skill_ids),
                     resistances=dict(bdef.resistances), persona=bdef.persona, sprite_color=bdef.sprite_color,
                     formation="front", is_melee=True)
    setup = BattleSetup(
        difficulty="normal", enemy_level=level, enemy_ids=[bdef.id],
        party=[c.build_combatant(equipment_db, legacy_db) for c in party_pcs], enemies=[boss], enemy_hero_recruits=[None],
    )
    setup._enemy_levels = {boss.id: level}
    setup._boss_def = bdef
    return setup


def _build_debug_battle(cfg: dict):
    """Returns (party_characters, BattleSetup) for a debug config."""
    by_name = {h.name: h for h in RECRUITABLE_ROSTER}
    party = []
    for e in cfg["party"]:
        h = by_name[e["name"]]
        party.append(PlayerCharacter(name=h.name, class_id=h.class_id, level=e["level"], rarity=h.rarity))
    if cfg["enemies"][0]["kind"] == "boss":
        e = cfg["enemies"][0]
        return party, _build_boss_setup(BOSSES[e["id"]], party, e["level"])
    enemies, ids, recruits = [], [], []
    for e in cfg["enemies"]:
        if e["kind"] == "monster":
            enemies.append(build_enemy_combatant(e["id"], e["level"]))
            ids.append(e["id"]); recruits.append(None)
        else:
            rec = by_name[e["id"]]
            enemies.append(build_hero_enemy_combatant(rec, e["level"]))
            ids.append(_hero_enemy_id(rec)); recruits.append(rec)
    apply_squad_formations(enemies)
    setup = BattleSetup(
        difficulty="normal", enemy_level=round(sum(e["level"] for e in cfg["enemies"]) / len(cfg["enemies"])),
        enemy_ids=ids, party=[c.build_combatant(EQUIPMENT) for c in party],
        enemies=enemies, enemy_hero_recruits=recruits,
    )
    setup._enemy_levels = {c.id: e["level"] for c, e in zip(enemies, cfg["enemies"])}
    apply_enemy_scaling(setup, 0)
    return party, setup


def run_http_server():
    server = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), Handler)
    print(f"[hub_server] Colosseum hub + Heroes + Summon + Battle on http://{HTTP_HOST}:{HTTP_PORT}")
    server.serve_forever()


# ----------------------------------------------------------------------
# Live battle -- moved over from battle_server.py, now reading the real
# active party off the shared player_state and writing real rewards back
# to it under _state_lock when the fight ends, instead of a fixed demo
# party that never touched the save.
# ----------------------------------------------------------------------
def run_battle(outbound: "queue.Queue[dict]", inbound: "queue.Queue[dict]", ollama_client: OllamaClient) -> None:
    """Runs exactly one full battle on this thread, pushing every event onto
    `outbound` for the WebSocket side to relay, and blocking on `inbound`
    whenever a human party member needs to act -- same shape
    ui/pygame_ui.py's get_party_action blocks on pygame events for, and the
    same shape battle_server.py used before this merge. The one real
    difference from before: `party` is the ACTUAL active_party_characters
    off the shared player_state (not a fixed demo squad), and rewards are
    applied to that same player_state -- under _state_lock -- once the
    fight ends, the same computation main.py's run_one_battle uses."""
    global pending_challenge, pending_ladder, pending_world_boss, pending_world_encounter
    dbg = debug_battle  # hand-picked debug fight (no rewards/saves), or None for a normal one
    from_world = False    # a wild encounter or boss NPC from the overworld -- forces can_continue off below
    if dbg:
        party, setup = _build_debug_battle(dbg)
    else:
        challenge_boss = None
        is_rank_challenge = False    # only true for the hub's own rank-ladder boss card (see below)
        with _state_lock:
            want_ladder, pending_ladder = pending_ladder, False       # consumed: one ladder run
            party = party_logic.active_party_characters(player_state)
            want, pending_challenge = pending_challenge, None      # consumed: one challenge, one fight
            want_world_boss, pending_world_boss = pending_world_boss, None  # consumed: one world-boss fight
            want_world_encounter, pending_world_encounter = pending_world_encounter, False  # consumed: one wild fight
            if (want in BOSSES and want == renown_logic.boss_id_for_rank(player_state.rank)
                    and renown_logic.can_challenge(player_state)):
                challenge_boss = BOSSES[want]
                is_rank_challenge = True
            elif want_world_boss in WORLD_BOSSES:
                # A boss NPC talked to in the overworld (game/world.py) -- same BossDef/BossRunner
                # machinery as a rank challenge, but never gated by renown and never promotes rank
                # (is_rank_challenge stays False, so settle_fight below can't mistake this for the
                # ladder's own boss card).
                challenge_boss = WORLD_BOSSES[want_world_boss]
                from_world = True
            elif want_world_encounter:
                from_world = True
        edb = _resolved_equipment_db()
        with _state_lock:
            ldb = dict(player_state.legacy_instances)
            # A new run is starting (this whole win-streak lives inside this one run_battle call) --
            # count it against every wounded hero's bench time, whether or not they're in this run's
            # party (see game/legacy.py's tick_wounds).
            wound_messages = legacy_logic.tick_wounds(player_state)
            if wound_messages:
                save_system.save_game(player_state)
        for message in wound_messages:
            outbound.put({"type": "log", "message": message})
        setup = (_build_rank_boss_setup(challenge_boss, party, challenge=is_rank_challenge, equipment_db=edb, legacy_db=ldb) if challenge_boss
                 else build_scaled_battle(party, equipment_db=edb, legacy_db=ldb))
        setup._from_world = from_world
    # Win streak: the SAME hero Combatant objects fight every round, so HP/MP
    # carry over (no recovery between fights). Each win after the first
    # doubles that fight's reward. Inventory also persists across the streak.
    ladder = ladder_logic.LadderRun() if (not dbg and want_ladder and not getattr(setup, "_rank_challenge", False)) else None
    heroes = setup.party
    bdef = getattr(setup, "_boss_def", None)   # set for scripted boss fights (see data/bosses.py)
    pay_boss_rewards = bool(bdef) and (not dbg or bool(dbg.get("rewards")))
    # Debug battles stream every damage/heal calculation into the log; normal ones turn the hook off.
    formulas.calc_hook = ((lambda text: outbound.put({"type": "log", "message": text, "debug": True}))
                          if dbg else None)
    with _state_lock:
        inventory = ({k: 9 for k in ITEMS} if dbg else dict(player_state.inventory))  # debug: plenty of everything
    wins = 0

    def ladder_status() -> dict:
        if ladder is None:
            return {"active": False}
        return {"active": True, "wins": ladder.wins, "can_cash_out": ladder.can_cash_out(),
                "until_cash_out": ladder.wins_until_cash_out(), "every": ladder_logic.CASH_OUT_EVERY,
                "bonus": ladder_logic.REWARD_BONUS, "perks": ladder.summary()}

    def sync_inventory() -> None:
        if dbg:
            return
        # Items used in battle are gone for good, win or lose.
        with _state_lock:
            player_state.inventory = {k: v for k, v in inventory.items() if v > 0}
            save_system.save_game(player_state)

    def finalize_departures(run_won: bool) -> None:
        """Called exactly once, right as the player actually leaves the
        Colosseum (see the three call sites below) -- never after an
        individual battle in a streak, since a hero downed mid-streak can
        still be revived in a later battle of the same run. Nobody is ever
        removed from the roster here any more -- anyone still downed right
        now is benched wounded instead (game/legacy.py's apply_wound_penalty),
        not lost. Debug fights use throwaway, unowned characters, so
        they're skipped entirely."""
        if dbg:
            return
        with _state_lock:
            messages = legacy_logic.apply_wound_penalty(player_state, heroes, party, run_won)
            if messages:
                save_system.save_game(player_state)
        for message in messages:
            outbound.put({"type": "log", "message": message})

    # Winnings are held in a pot and only paid out when the player leaves
    # (or flees). A defeat forfeits the whole pot.
    pot = {"money": 0, "gems": 0, "xp": 0}
    pot_tickets = {"common": 0, "premium": 0}     # summon tickets ride in the pot too
    pot_rivals = []

    def cash_out() -> dict:
        if dbg:
            return {"money": 0, "gems": 0, "xp": 0, "level_ups": {}}
        with _state_lock:
            for message in roll_hero_enemy_shard_drops(list(pot_rivals), player_state):
                outbound.put({"type": "log", "message": message})
            player_state.add_rewards(pot["money"], pot["gems"])
            player_state.add_tickets(pot_tickets)
            paid_tickets = {k: v for k, v in pot_tickets.items() if v}
            for k in pot_tickets:
                pot_tickets[k] = 0
            level_ups = {}
            if pot["xp"]:
                for character in party:
                    gained = character.grant_xp(pot["xp"])
                    if gained:
                        level_ups[character.name] = gained
            save_system.save_game(player_state)
            paid = dict(pot, level_ups=level_ups, tickets=paid_tickets)
            for k in pot:
                pot[k] = 0
            pot_rivals.clear()
        return paid

    engine_ref = [None]

    def debug_refresh() -> None:
        """Debug stat boxes: push a fresh snapshot at the start of every turn so ticked/expired statuses show."""
        if config.DEBUG and engine_ref[0] is not None:
            outbound.put({"type": "state", "state": _serialize_battle_state(engine_ref[0])})

    def get_party_action(combatant, state: dict) -> Action:
        debug_refresh()
        for sk in state.get("available_skills", []):  # let the browser's auto-battle compare skill damage
            if sk["id"] in SKILLS:
                sk["power"] = SKILLS[sk["id"]].power
        outbound.put({"type": "need_action", "actor_id": combatant.id, "state": state})
        while True:
            msg = inbound.get()
            if msg.get("actor_id") == combatant.id:
                return _action_from_message(combatant.id, msg)
            # A stale reply from a previous prompt (e.g. a slow double-click) -- ignore and keep waiting.

    base_enemy_action = make_enemy_ai_fn(
        ollama_client, use_fallback_on_error=config.AI_FALLBACK_ON_ERROR,
        on_decision=lambda record: outbound.put({"type": "ai_event", **record}),
    )
    runner_ref = [None]  # the BossRunner for this fight, once the engine exists

    def get_enemy_action(combatant, state):
        debug_refresh()
        runner = runner_ref[0]
        if runner is not None and runner.controls(combatant.id):
            forced = runner.before_boss_action(combatant)   # scripted (telegraphed) move overrides the AI
            if forced is not None:
                return forced
        return base_enemy_action(combatant, state)

    def wait_for_dialogue() -> None:
        """Block the battle thread until the browser has clicked through the dialogue."""
        while True:
            msg = inbound.get()
            if msg.get("type") == "dialogue_done":
                return
            if msg.get("type") == "leave":
                inbound.put(msg)   # let the normal flow see it
                return

    if ladder is not None:
        outbound.put({"type": "ladder_status", **ladder_status()})
    while True:
        bdef = getattr(setup, "_boss_def", None)   # a streak can roll a boss from the pool mid-way
        pay_boss_rewards = bool(bdef) and (not dbg or bool(dbg.get("rewards")))
        roles = {ch.name: ch.class_id for ch in party}
        # Parallel to setup.enemies: the RecruitableHero (with its class_id) behind each hero-rival
        # enemy, when there is one -- lets us pick a ranged vs. melee animation for them too. Plain
        # monsters/bosses have no recruit behind them and fall back to "melee" in _anim_kind_for.
        enemy_roles = {
            c.id: r.class_id
            for c, r in zip(setup.enemies, getattr(setup, "enemy_hero_recruits", None) or [])
            if r is not None
        }
        engine = BattleEngine(
            party=heroes, enemies=setup.enemies, skills_db=SKILLS, items_db=ITEMS,
            inventory=inventory,
            get_party_action=get_party_action, get_enemy_action=get_enemy_action,
            on_event=lambda line: outbound.put({"type": "log", "message": line}),
        )

        engine_ref[0] = engine
        engine._levels = {ch.name: ch.level for ch in party}
        engine._enemy_level = setup.enemy_level
        if dbg and not bdef:
            hp_m, other_m, chain = getattr(setup, "_enemy_scale", (1.0, 1.0, 1.0))
            outbound.put({"type": "log", "debug": True,
                          "message": f"[calc] ENEMY SCALING {setup.num_heroes} heroes vs {setup.num_enemies} enemies: "
                                     f"size HP x{hp_m:.2f} / other x{other_m:.2f}, chain x{chain:.2f} (HP/ATK/DEF/MAG/RES)"})
        engine._enemy_levels = getattr(setup, "_enemy_levels", {})
        if bdef:
            engine._boss_sprites = _boss_sprite_payloads(bdef, setup.enemies)
        engine._damage = {c.id: 0 for c in list(heroes) + list(setup.enemies)}
        engine._roles = roles  # lets the browser's auto-battle see each ally's class/role
        # Wrap resolve_action (same technique ui/pygame_ui.py's attach_engine
        # uses) so the browser gets an "about to happen" event -- with enough to
        # start a melee run-in animation -- before the state snapshot that
        # reflects its result.
        original_resolve = engine.resolve_action

        def resolve_with_broadcast(action: Action, _orig=original_resolve, _engine=engine) -> None:
            if runner_ref[0] is not None:
                action = runner_ref[0].before_action(action)   # e.g. Ronan guarding Selene rewrites the target
            target_id = action.target_ids[0] if action.target_ids else None
            _sk = SKILLS.get(action.skill_id) if action.type == ActionType.SKILL else None
            _actor = _engine.get_by_id(action.actor_id)
            anim_kind = _anim_kind_for(action, _actor, roles, enemy_roles)
            payload = {
                "type": "action_event", "actor_id": action.actor_id, "target_id": target_id,
                "is_melee": anim_kind == "melee", "anim_kind": anim_kind, "action_type": action.type.value,
                "skill_id": action.skill_id, "item_id": action.item_id,
                # Damage-number colouring in the browser: the skill's element / kind.
                "element": (_sk.element.value if _sk is not None else "physical"),
                "skill_kind": (_sk.kind if _sk is not None else None),
            }
            # AoE skills (cleave/firestorm/prayer/holy_reset...) hit every valid target on one or both
            # sides -- give the browser the full list so it can show the effect landing on all of them,
            # not just the single id the player happened to click (or none, for an enemy AI's AoE cast).
            if _sk is not None and _actor is not None:
                aoe_ids = _aoe_target_ids(_engine, _actor, _sk.target)
                if aoe_ids is not None:
                    payload["target_ids"] = aoe_ids
            outbound.put(payload)
            everyone = list(_engine.party) + list(_engine.enemies)
            before = {c.id: c.hp for c in everyone}
            side = {c.id: 0 for c in _engine.party}
            actor_is_party = action.actor_id in side
            _orig(action)
            # Debug damage tally: HP lost by the opposing side during this action is credited
            # to the actor (DoT/poison ticks are not attributed; heals don't count).
            foes = _engine.enemies if actor_is_party else _engine.party
            dealt = sum(max(0, before[c.id] - c.hp) for c in foes)
            if dealt:
                _engine._damage[action.actor_id] = _engine._damage.get(action.actor_id, 0) + dealt
            if ladder is not None and actor_is_party:
                actor_c = next((c for c in _engine.party if c.id == action.actor_id), None)
                if actor_c is not None:
                    for line in ladder.after_hero_action(actor_c, foes, before, dealt):
                        outbound.put({"type": "log", "message": line})
            outbound.put({"type": "state", "state": _serialize_battle_state(_engine)})
            if runner_ref[0] is not None:
                runner_ref[0].after_action(action, before.get(runner_ref[0].boss.id))   # counters + script triggers

        engine.resolve_action = resolve_with_broadcast

        runner_ref[0] = None
        if bdef:
            refresh = lambda _e=engine: outbound.put({"type": "state", "state": _serialize_battle_state(_e)})
            if bdef.runner == "twins":
                runner_ref[0] = TwinsRunner(bdef, setup.enemies[0], setup.enemies[1], engine, emit=outbound.put,
                                            wait_for_dialogue=wait_for_dialogue, refresh_state=refresh)
            else:
                runner_ref[0] = BossRunner(
                    bdef, setup.enemies[0], engine, emit=outbound.put, wait_for_dialogue=wait_for_dialogue,
                    refresh_state=refresh)
        outbound.put({"type": "state", "state": _serialize_battle_state(engine)})
        if runner_ref[0] is not None:
            runner_ref[0].on_start()
        result = engine.run()
        if runner_ref[0] is not None:
            runner_ref[0].on_end(result)
        sync_inventory()

        multiplier = 1
        this_win = {"money": 0, "gems": 0, "xp": 0}
        forfeited = None
        paid = None
        first_clear = False
        this_tickets = {}
        if bdef:
            # Boss fights: no win-streak pot. First clear pays big (tracked in the save), rematches pay less.
            if result == BattleResult.VICTORY:
                with _state_lock:
                    first_clear = bdef.id not in player_state.cleared_bosses
                this_win = dict(bdef.rewards_first if first_clear else bdef.rewards_repeat)
                this_tickets = roll_ticket_drops(boss_first_clear=first_clear)
                this_shards = roll_equipment_shard_drops(boss_first_clear=first_clear)
                if pay_boss_rewards:
                    with _state_lock:
                        player_state.add_rewards(this_win.get("money", 0), this_win.get("gems", 0))
                        player_state.add_tickets(this_tickets)
                        player_state.add_equipment_shards(this_shards)
                        level_ups = {}
                        if not dbg and this_win.get("xp"):   # debug parties aren't owned heroes
                            for character in party:
                                gained = character.grant_xp(this_win["xp"])
                                if gained:
                                    level_ups[character.name] = gained
                        if bdef.id not in player_state.cleared_bosses:
                            player_state.cleared_bosses.append(bdef.id)
                        save_system.save_game(player_state)
                    paid = dict(this_win, level_ups=level_ups, tickets=dict(this_tickets), equipment_shards=this_shards)
        elif result == BattleResult.VICTORY:
            wins += 1
            multiplier = 2 ** (wins - 1)
            if ladder is not None:
                multiplier = round(ladder.reward_multiplier(multiplier), 2)
            money, gems, xp = compute_battle_rewards(
                result, difficulty=DEMO_DIFFICULTY, num_heroes=setup.num_heroes, num_enemies=setup.num_enemies,
            )
            this_win = {"money": round(money * multiplier), "gems": round(gems * multiplier), "xp": round(xp * multiplier)}
            for k in pot:
                pot[k] += this_win[k]
            this_tickets = roll_ticket_drops(ladder=ladder is not None)
            for k, n in this_tickets.items():
                pot_tickets[k] += n
            # Equipment shards: awarded immediately on every win, the same simple way money/gems from
            # a normal (non-boss) fight are earned -- NOT routed through the ladder-mode ticket-pot
            # forfeit/bank mechanic above. A deliberate scope-reduction (Andrew's request just asked
            # for shards to "sometimes drop" -- it didn't ask for them to be at risk on a ladder flee/
            # loss the way pot money and pot tickets are), so a shard drop is kept even on a later
            # forfeit or defeat in this same ladder run.
            this_shards = roll_equipment_shard_drops(ladder=ladder is not None)
            if this_shards:
                with _state_lock:
                    player_state.add_equipment_shards(this_shards)
            pot_rivals.extend(
                (recruit, enemy) for recruit, enemy in zip(setup.enemy_hero_recruits, setup.enemies)
                if recruit is not None
            )
        elif result == BattleResult.FLED and ladder is not None:
            # Ladder Mode: you can't slip away with the loot -- only a scheduled cash-out pays out.
            forfeited = dict(pot, tickets={k: v for k, v in pot_tickets.items() if v})
            for k in pot:
                pot[k] = 0
            for k in pot_tickets:
                pot_tickets[k] = 0
            pot_rivals.clear()
        elif result == BattleResult.FLED:
            paid = cash_out()  # escaping with the loot keeps the pot
        else:
            # Defeat: everything in the pot is lost, nothing is saved.
            forfeited = dict(pot, tickets={k: v for k, v in pot_tickets.items() if v})
            for k in pot:
                pot[k] = 0
            for k in pot_tickets:
                pot_tickets[k] = 0
            pot_rivals.clear()

        # Renown: every real (non-debug) fight moves the ladder meter; a won rank challenge promotes you.
        renown_info = None
        if not dbg:
            chain = getattr(setup, "_enemy_scale", (1.0, 1.0, 1.0))[2]
            fight_mult = reward_multiplier(DEMO_DIFFICULTY, setup.num_heroes, setup.num_enemies) * chain
            with _state_lock:
                renown_info = renown_logic.settle_fight(
                    player_state, won=result == BattleResult.VICTORY, fled=result == BattleResult.FLED,
                    mult=fight_mult, boss_id=bdef.id if bdef else None,
                    rank_challenge=bool(getattr(setup, "_rank_challenge", False)))
                if renown_info["rank_up"]:
                    nxt = renown_logic.boss_id_for_rank(player_state.rank)
                    renown_info["next_boss"] = BOSSES[nxt].name if nxt in BOSSES else None
                save_system.save_game(player_state)

        if dbg and not pay_boss_rewards:  # debug fights pay nothing and never chain
            this_win = {"money": 0, "gems": 0, "xp": 0}
            for k in pot:
                pot[k] = 0
            pot_rivals.clear()
        # A wild overworld fight or dungeon boss (from_world) always ends after this one battle --
        # Andrew asked for overworld fights to skip the Colosseum's "keep fighting for a bigger streak
        # multiplier" prompt entirely and just drop the player back into /world.
        can_continue = (result == BattleResult.VICTORY and any(h.alive for h in heroes) and not dbg
                        and not getattr(setup, "_from_world", False))
        ladder_info = None
        if ladder is not None:
            if result == BattleResult.VICTORY:
                ladder.wins += 1
            ladder_info = ladder_status()
            if can_continue:
                ladder_info["perk_choices"] = ladder.draw(heroes)
        outbound.put({"type": "battle_end", "result": result.value,
                      "money": this_win["money"], "gems": this_win["gems"], "xp": this_win["xp"],
                      "pot": dict(pot), "win_streak": wins,
                      "tickets_won": this_tickets, "pot_tickets": {k: v for k, v in pot_tickets.items() if v},
                      "multiplier": multiplier,
                      "next_multiplier": (round(ladder.reward_multiplier(2 ** wins), 2) if ladder is not None else 2 ** wins),
                      "can_continue": can_continue, "from_world": bool(getattr(setup, "_from_world", False)),
                      "forfeited": forfeited, "paid": paid, "debug": bool(dbg),
                      "boss": bool(bdef), "first_clear": first_clear, "rewards_paid": bool(paid) if bdef else None,
                      "renown": renown_info, "ladder": ladder_info})
        if not can_continue:
            break
        # Wait for the browser: fight the next battle, or cash out and leave.
        while True:
            msg = inbound.get()
            if ladder is not None and msg.get("type") == "perk":
                text = ladder.pick(msg.get("id"), heroes)
                if text is not None:
                    outbound.put({"type": "perk_applied", "message": text, "state": _serialize_battle_state(engine),
                                  **ladder_status()})
                continue
            if msg.get("type") == "continue":
                if ladder is not None and ladder.offer:
                    continue          # the perk must be chosen first
                break
            if msg.get("type") == "leave":
                if ladder is not None and not ladder.can_cash_out():
                    if msg.get("forced"):     # closing the page mid-run forfeits the pot
                        finalize_departures(result == BattleResult.VICTORY)
                        outbound.put({"type": "session_end"})
                        return
                    continue                  # no cashing out yet
                outbound.put({"type": "cashed_out", "paid": cash_out()})
                finalize_departures(result == BattleResult.VICTORY)
                outbound.put({"type": "session_end"})
                return
        for h in heroes:
            h.clear_all_status()
            h.defending = False
        with _state_lock:
            # each extra battle: enemies +10% -- debug runs never own gear, real ones always resolve fresh
            # (a stash change mid-run, e.g. from a perk, would otherwise use a stale equipment_db).
            edb = EQUIPMENT if dbg else _resolved_equipment_db()
            ldb = {} if dbg else dict(player_state.legacy_instances)
            setup = build_scaled_battle(party, ladder.wins if ladder is not None else wins, equipment_db=edb, legacy_db=ldb)
        if ladder is not None:
            ladder.on_battle_start(heroes)
            outbound.put({"type": "ladder_status", **ladder_status()})
        outbound.put({"type": "new_battle"})
    finalize_departures(result == BattleResult.VICTORY)
    outbound.put({"type": "session_end"})


# ----------------------------------------------------------------------
# WebSocket: one connection = one battle, bridged onto its own thread
# ----------------------------------------------------------------------
async def handle_connection(websocket, ollama_client: OllamaClient):
    print("[hub_server:ws] client connected -- starting a new battle")
    outbound: "queue.Queue[dict]" = queue.Queue()
    inbound: "queue.Queue[dict]" = queue.Queue()

    battle_thread = threading.Thread(target=run_battle, args=(outbound, inbound, ollama_client), daemon=True)
    battle_thread.start()

    loop = asyncio.get_event_loop()

    async def pump_outbound():
        while True:
            msg = await loop.run_in_executor(None, outbound.get)
            await websocket.send(json.dumps(msg))
            if msg.get("type") == "session_end":
                return

    async def pump_inbound():
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            inbound.put(msg)

    tasks = [asyncio.ensure_future(pump_outbound()), asyncio.ensure_future(pump_inbound())]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        inbound.put({"type": "leave", "forced": True})  # closing the page while idle after a win cashes out the pot
        print("[hub_server:ws] client disconnected")


async def run_ws_server(ollama_client: OllamaClient):
    async with websockets.serve(lambda ws: handle_connection(ws, ollama_client), WS_HOST, WS_PORT):
        print(f"[hub_server] Live battle WebSocket on ws://{WS_HOST}:{WS_PORT}")
        await asyncio.Future()  # run forever


def main():
    parser = argparse.ArgumentParser(description="Battle Arena -- Colosseum hub / Heroes / Summon / Battle (one real backend)")
    parser.add_argument("--host", default=config.OLLAMA_HOST)
    parser.add_argument("--model", default=config.OLLAMA_MODEL)
    parser.add_argument("--debug", action="store_true", help="enable debug tools (same as DEBUG=1)")
    args = parser.parse_args()
    if args.debug:
        config.DEBUG = True

    ollama_client = OllamaClient(
        host=args.host, model=args.model, timeout=config.OLLAMA_TIMEOUT_SECONDS,
        num_predict=config.OLLAMA_NUM_PREDICT, keep_alive=config.OLLAMA_KEEP_ALIVE,
    )
    if not ollama_client.is_available():
        print(f"[warn] Could not reach Ollama at {args.host}. Enemies will use the scripted "
              f"fallback AI until Ollama is running there.")

    threading.Thread(target=run_http_server, daemon=True).start()
    try:
        asyncio.run(run_ws_server(ollama_client))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

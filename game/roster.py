"""PlayerCharacter: a persistent (saved) character, as distinct from
engine.combatant.Combatant, which is battle-scoped and resets its HP/MP the
instant it's constructed (see Combatant.__post_init__). A PlayerCharacter
survives between battles and across save/load; build_combatant() is the
only place it turns into the battle-time object the engine actually runs.
"""
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from data.classes import CLASS_ARCHETYPES
from data.hero_rarity import HERO_RARITIES, MAX_STARS, STORY_GROWTH_MULT, is_story_rarity, level_cap_for, rarity_multiplier, star_multiplier
from data.hero_skills import skill_ids_for
from data.leveling import MAX_LEVEL, TALENT_POINT_INTERVAL, apply_growth, resolve_level_up
import engine.formation as formation
from engine.combatant import Combatant
from engine.equipment import SLOTS, Equipment
from engine.skills import MAX_SKILL_RANK
from engine.stats import Stats


@dataclass
class PlayerCharacter:
    name: str
    class_id: str
    # slot -> equipped Equipment id, or None. Always has all three keys so
    # callers never need a .get() with a default -- a character with nothing
    # equipped yet still has {"weapon": None, "armor": None, "accessory": None}.
    equipped: Dict[str, Optional[str]] = field(default_factory=lambda: {slot: None for slot in SLOTS})
    level: int = 1
    xp: int = 0          # progress toward level + 1, per data/leveling.py's xp_for_next_level
    # Hero rarity (data/hero_rarity.py) + the shard/star duplicate-upgrade
    # economy it drives -- see PlayerCharacter.effective_stats for how stars
    # actually change stats, and game/heroes.py for spending shards.
    # "common" is the default rather than something pulled from
    # data/summon_pool.py because a self-made character (character creation,
    # not a summon) isn't drawn from that pool at all -- common is the
    # closest thing summons have to "no special rarity."
    rarity: str = "common"
    stars: int = 1        # 1 = never upgraded (0% bonus); see data/hero_rarity.py's star_multiplier
    shards: int = 0       # banked shards toward this hero's next star, from duplicate summons
    # skill_id -> rank (1-10). A skill missing from this dict is rank 1 (never invested in) --
    # see engine/skills.py's MAX_SKILL_RANK and this class's talent_points_* methods below.
    skill_ranks: Dict[str, int] = field(default_factory=dict)
    # Legacy item instance ids (game/legacy.py's LegacyItem) currently equipped on this hero --
    # capacity is legacy_slots (below), not a fixed set of named slots like `equipped`: any legacy
    # item can go in any free slot.
    equipped_legacies: List[str] = field(default_factory=list)
    # Runs remaining before this hero can rejoin the active party, after being carried out downed at
    # the end of a run (game/legacy.py's apply_wound_penalty) -- 0 means fit to fight. Pay gold to
    # clear this early (game/legacy.py's heal_wound) instead of waiting it out. This is the ONLY
    # in-battle death penalty now -- a downed hero is never removed from the roster for it (see
    # sacrifice_hero for the one deliberate, voluntary way a hero is ever permanently lost).
    wounded_runs_remaining: int = 0
    # Battle formation row (engine/formation.py): "front"/"middle"/"rear", chosen on Party Select
    # (game/party.py's confirm_party) and persisted here so it sticks between battles until changed.
    # Defaults to "middle" -- the engine's own DEFAULT_FORMATION -- for a freshly created hero.
    formation: str = formation.DEFAULT_FORMATION
    # Persistent current HP / MP, None = full. Only fights outside the Colosseum (the island dungeon and the
    # overworld: hub_server.py's from_world fights) carry damage over; the Colosseum, resting (the menu's Rest
    # action) and a wound recovery refill them. Read through hub_server._hp_mp_for, which clamps to the
    # hero's current max (gear and level changes move it).
    hp: Optional[int] = None
    mp: Optional[int] = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def __post_init__(self):
        if self.class_id not in CLASS_ARCHETYPES:
            raise ValueError(f"Unknown class_id {self.class_id!r} (must be one of {list(CLASS_ARCHETYPES)})")
        if self.rarity not in HERO_RARITIES:
            raise ValueError(f"Unknown rarity {self.rarity!r} (must be one of {HERO_RARITIES})")
        for slot in SLOTS:
            self.equipped.setdefault(slot, None)
        # Clamped to THIS hero's own rarity-based cap (data/hero_rarity.py's level_cap_for), not the
        # flat engine ceiling -- min() with MAX_LEVEL is just a defensive belt-and-suspenders, since
        # level_cap_for never returns anything close to MAX_LEVEL=60.
        self.level = max(1, min(self.level, min(MAX_LEVEL, level_cap_for(self.rarity))))
        self.stars = max(1, min(self.stars, MAX_STARS))
        self.shards = max(0, self.shards)
        self.wounded_runs_remaining = max(0, int(self.wounded_runs_remaining))
        self.formation = formation.clamp_formation(self.formation)
        # Defensive clamp for save-loaded data (a hand-edited or stale save could have an out-of-range
        # or non-int rank) -- ranks are otherwise only ever changed one step at a time via
        # game/heroes.py's upgrade_skill_rank, which can't produce an invalid value itself.
        self.skill_ranks = {
            sid: max(1, min(MAX_SKILL_RANK, int(r))) for sid, r in self.skill_ranks.items()
        }

    def skill_rank(self, skill_id: str) -> int:
        return self.skill_ranks.get(skill_id, 1)

    def talent_points_earned(self) -> int:
        return self.level // TALENT_POINT_INTERVAL

    def talent_points_spent(self) -> int:
        return sum(max(0, r - 1) for r in self.skill_ranks.values())

    def talent_points_available(self) -> int:
        return max(0, self.talent_points_earned() - self.talent_points_spent())

    @property
    def archetype(self):
        return CLASS_ARCHETYPES[self.class_id]

    @property
    def legacy_slots(self) -> int:
        """How many legacy items (game/legacy.py) this hero can hold: 3
        base, plus one more per rarity step above common. Local import to
        dodge a roster.py <-> legacy.py import cycle (legacy.py needs
        PlayerCharacter itself)."""
        from game.legacy import legacy_slots_for
        return legacy_slots_for(self)

    @property
    def level_cap(self) -> int:
        """This hero's own level ceiling, set by their rarity alone (data/hero_rarity.py's
        level_cap_for) -- common=10 up through mythic=50. Reaching it is what "maxed" means for the
        sacrifice-for-legacy flow (game/legacy.py's sacrifice_hero)."""
        return level_cap_for(self.rarity)

    @property
    def is_story(self) -> bool:
        """Story heroes (Mythic rarity) fight outside the Colosseum only; see data/hero_rarity.py."""
        return is_story_rarity(self.rarity)

    @property
    def is_level_maxed(self) -> bool:
        return self.level >= self.level_cap

    @property
    def is_wounded(self) -> bool:
        return self.wounded_runs_remaining > 0

    def grant_xp(self, amount: int) -> int:
        """Adds XP and resolves any level-ups it covers (possibly more than
        one from a single big grant), capped at this hero's OWN level_cap
        rather than the engine's flat MAX_LEVEL. Returns how many levels
        were gained, so a caller can report "X leveled up!" when it's
        nonzero."""
        self.xp += max(0, amount)
        self.level, self.xp, levels_gained = resolve_level_up(self.level, self.xp, self.level_cap, self.is_story)
        return levels_gained

    def effective_stats(self, equipment_db: Dict[str, Equipment], legacy_db: Optional[Dict[str, "LegacyItem"]] = None) -> Stats:
        """The archetype's base stats, grown to this character's level (see
        data/leveling.py), scaled by this hero's star level (see
        data/hero_rarity.py's star_multiplier -- 1 star, the default, is an
        exact 1.0x no-op), plus flat bonuses from whatever's currently
        equipped. Star scaling is applied before equipment on purpose: gear
        bonuses are flat numbers on the item tooltip, so they shouldn't
        silently grow just because the wearer got duplicate-upgraded.
        Unknown/missing equipment ids (e.g. a save file referencing gear
        from a since-removed catalog entry) are silently skipped rather than
        crashing -- a missing bonus is a much smaller problem than an
        unloadable save. `legacy_db` (game/legacy.py's LegacyItem instances,
        keyed by id) is optional and applied last, as a % bonus on top of
        everything else -- omit it (the default) for any caller that
        doesn't care about legacy items (e.g. a throwaway debug character)."""
        archetype = self.archetype
        stats = apply_growth(archetype.base_stats, archetype.growth, self.level, STORY_GROWTH_MULT if self.is_story else 1.0)
        mult = star_multiplier(self.stars) * rarity_multiplier(self.rarity)  # higher rarity = better base stats
        if mult != 1.0:
            stats.max_hp = round(stats.max_hp * mult)
            stats.max_mp = round(stats.max_mp * mult)
            stats.atk = round(stats.atk * mult)
            stats.def_ = round(stats.def_ * mult)
            stats.mag = round(stats.mag * mult)
            stats.res = round(stats.res * mult)
            stats.spd = round(stats.spd * mult)
            stats.luk = round(stats.luk * mult)
        for item_id in self.equipped.values():
            if not item_id:
                continue
            item = equipment_db.get(item_id)
            if not item:
                continue
            for stat_name, bonus in item.stat_bonuses.items():
                if hasattr(stats, stat_name):
                    setattr(stats, stat_name, getattr(stats, stat_name) + bonus)
        if legacy_db and self.equipped_legacies:
            from game.legacy import apply_legacy_bonuses  # local import: dodges a roster<->legacy cycle
            apply_legacy_bonuses(stats, self.equipped_legacies, legacy_db)
        return stats

    def build_combatant(self, equipment_db: Dict[str, Equipment], legacy_db: Optional[Dict[str, "LegacyItem"]] = None) -> Combatant:
        archetype = self.archetype
        return Combatant(
            name=self.name, is_enemy=False,
            base_stats=self.effective_stats(equipment_db, legacy_db),
            skill_ids=skill_ids_for(self.name, self.class_id),
            skill_ranks=dict(self.skill_ranks),
            sprite_color=archetype.sprite_color,
            formation=self.formation,
            is_melee=archetype.is_melee,
        )

    def equip(self, item_id: str, equipment_db: Dict[str, Equipment]) -> Optional[str]:
        """Equips item_id into its slot, returning whatever was previously
        equipped there (or None). Raises KeyError if item_id isn't in
        equipment_db -- callers should only offer items known to exist."""
        item = equipment_db[item_id]
        previous = self.equipped[item.slot]
        self.equipped[item.slot] = item_id
        return previous

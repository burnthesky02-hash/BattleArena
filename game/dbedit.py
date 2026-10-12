"""Backend for the in-game Database Editor (html_builder/database.html, served at /database).

The game's tuning data lives in Python tables (items, gear, enemies, bosses, shops, drop rates) and in two JSON files
(quests). This module exposes each one as a "table" of editable rows. Saving a row

  * changes the live in-memory object right away (no restart needed for anything but the quest log, which the 3D hub
    re-reads when it loads), and
  * records the row in data/db_overrides.json, which is re-applied on every start so the edit survives a restart.

The Python source files are never rewritten; delete a row's override (Reset) or the whole json file to get the shipped
values back. The quest tables are different: they are plain JSON files, so they are edited in place (a timestamped
backup is kept next to them in html_hub/3d/db_backups/).

Field types the page understands: text, area, int, float, bool, select (options), ro (read-only text), stats (the eight
stat numbers), numdict (fixed keys -> number), idlist (ordered ids from a catalog), strlist (comma separated names),
range ([lo, hi]), resist (element -> multiplier), rows (list of sub-objects described by `of`).
"""
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

STAT_KEYS = ("max_hp", "max_mp", "atk", "def_", "mag", "res", "spd", "luk")
STAT_LABEL = {"max_hp": "HP", "max_mp": "MP", "atk": "ATK", "def_": "DEF", "mag": "MAG", "res": "RES", "spd": "SPD", "luk": "LUK"}
ELEMENTS = ("physical", "fire", "ice", "thunder", "holy", "dark")

_data_dir: Optional[Path] = None
_quest_dir: Optional[Path] = None
_overrides: Dict[str, Dict[str, dict]] = {}
_defaults: Dict[str, Dict[str, dict]] = {}
TABLES: Dict[str, "Table"] = {}


# ---- small coercion helpers -----------------------------------------------------------------------------------------
def _int(v, lo=0, hi=10 ** 9, default=0) -> int:
    try:
        n = int(round(float(v)))
    except (TypeError, ValueError):
        n = default
    return max(lo, min(hi, n))


def _float(v, lo=0.0, hi=1e9, default=0.0) -> float:
    try:
        n = float(v)
    except (TypeError, ValueError):
        n = default
    return max(lo, min(hi, n))


def _text(v, limit=4000) -> str:
    return str(v if v is not None else "")[:limit]


def _stats_out(stats) -> dict:
    return {k: getattr(stats, k) for k in STAT_KEYS}


def _stats_in(stats, d: dict) -> None:
    for k in STAT_KEYS:
        if k in d:
            setattr(stats, k, _int(d[k], 0, 99999))


def _ids(v, valid) -> List[str]:
    out = []
    for i in (v or []):
        i = str(i)
        if i not in valid:
            raise ValueError(f"unknown id {i!r}")
        out.append(i)
    return out


class Table:
    id = ""
    label = ""
    desc = ""
    fields: List[dict] = []
    can_add = False
    can_delete = False
    file_backed = False

    def rows(self) -> List[dict]:
        raise NotImplementedError

    def apply(self, row: dict) -> None:
        raise NotImplementedError

    def schema(self) -> dict:
        return {"id": self.id, "label": self.label, "desc": self.desc, "fields": self.fields, "can_add": self.can_add,
                "can_delete": self.can_delete, "resettable": not self.file_backed}


def _f(key, label, type_="text", **kw) -> dict:
    return {"key": key, "label": label, "type": type_, **kw}


# ---- Items ----------------------------------------------------------------------------------------------------------
class ItemsTable(Table):
    id, label = "items", "Items"
    desc = "Consumables: what they cost, what they heal. Cost 0 means the shops can't sell it."
    fields = [_f("name", "Name"), _f("description", "Description", "area"), _f("cost", "Price", "int"),
              _f("heal_hp", "Heals HP", "int"), _f("heal_mp", "Restores MP", "int"), _f("revive", "Revives a KO'd ally", "bool")]

    def rows(self):
        from data.items_db import ITEMS
        return [{"id": i.id, "name": i.name, "description": i.description, "cost": i.cost, "heal_hp": i.heal_hp,
                 "heal_mp": i.heal_mp, "revive": bool(i.revive)} for i in ITEMS.values()]

    def apply(self, row):
        from data.items_db import ITEMS
        it = ITEMS.get(row.get("id"))
        if it is None:
            raise ValueError("unknown item")
        it.name = _text(row.get("name"), 60) or it.name
        it.description = _text(row.get("description"), 400)
        it.cost = _int(row.get("cost"), 0, 10 ** 7)
        it.heal_hp = _int(row.get("heal_hp"), 0, 99999)
        it.heal_mp = _int(row.get("heal_mp"), 0, 99999)
        it.revive = bool(row.get("revive"))


# ---- Equipment ------------------------------------------------------------------------------------------------------
class EquipmentTable(Table):
    id, label = "equipment", "Equipment"
    desc = "Weapons, armor and accessories. Price 0 = summon-only. Stat bonuses are flat; leave a stat at 0 to drop it."
    fields = [_f("name", "Name"), _f("slot", "Slot", "ro"), _f("subtype", "Type", "ro"),
              _f("rarity", "Rarity", "select", options=["common", "rare", "epic", "legendary", "mythic"]),
              _f("cost", "Price", "int"), _f("description", "Description", "area"), _f("stat_bonuses", "Stat bonuses", "stats")]

    def rows(self):
        from data.equipment_db import EQUIPMENT
        return [{"id": e.id, "name": e.name, "slot": e.slot, "subtype": e.subtype or "", "rarity": e.rarity, "cost": e.cost,
                 "description": e.description, "stat_bonuses": {k: e.stat_bonuses.get(k, 0) for k in STAT_KEYS}}
                for e in EQUIPMENT.values()]

    def apply(self, row):
        from data.equipment_db import EQUIPMENT
        from engine.equipment import RARITIES
        e = EQUIPMENT.get(row.get("id"))
        if e is None:
            raise ValueError("unknown equipment")
        if row.get("rarity") not in RARITIES:
            raise ValueError("bad rarity")
        e.name = _text(row.get("name"), 60) or e.name
        e.rarity = row["rarity"]
        e.cost = _int(row.get("cost"), 0, 10 ** 7)
        e.description = _text(row.get("description"), 400)
        sb = row.get("stat_bonuses") or {}
        e.stat_bonuses = {k: _int(sb.get(k), -9999, 99999) for k in STAT_KEYS if _int(sb.get(k), -9999, 99999)}


# ---- Enemies and bosses ---------------------------------------------------------------------------------------------
def _resist_out(res: dict) -> dict:
    return {getattr(k, "value", str(k)): v for k, v in (res or {}).items()}


def _resist_in(d: dict) -> dict:
    from engine.types import Element
    out = {}
    for k, v in (d or {}).items():
        if k in ELEMENTS:
            v = _float(v, 0.0, 5.0, 1.0)
            if abs(v - 1.0) > 1e-9:
                out[Element(k)] = v
    return out


def _skill_ids():
    from data.skills_db import SKILLS
    try:
        from data.bosses import BOSS_SKILLS
    except Exception:
        BOSS_SKILLS = {}
    return {**SKILLS, **BOSS_SKILLS}


_COMBAT_FIELDS = [_f("name", "Name"), _f("persona", "Behaviour notes", "area"), _f("base_stats", "Level-1 stats", "stats"),
                  _f("growth", "Growth per level", "stats"), _f("skill_ids", "Skills", "idlist", catalog="skills"),
                  _f("resistances", "Element multipliers (1 = normal, 0.5 = resists, 1.5 = weak)", "resist")]


class EnemiesTable(Table):
    id, label = "enemies", "Enemies"
    desc = "The Colosseum / wild enemy roster. Stats grow per level exactly like a hero's."
    fields = _COMBAT_FIELDS + [_f("is_melee", "Fights in melee", "bool")]

    def rows(self):
        from data.enemy_pool import ENEMY_ARCHETYPES
        return [{"id": a.id, "name": a.name, "persona": a.persona, "base_stats": _stats_out(a.base_stats), "growth": _stats_out(a.growth),
                 "skill_ids": list(a.skill_ids), "resistances": _resist_out(a.resistances), "is_melee": bool(a.is_melee)}
                for a in ENEMY_ARCHETYPES.values()]

    def apply(self, row):
        from data.enemy_pool import ENEMY_ARCHETYPES
        a = ENEMY_ARCHETYPES.get(row.get("id"))
        if a is None:
            raise ValueError("unknown enemy")
        skills = _ids(row.get("skill_ids"), _skill_ids())
        a.name = _text(row.get("name"), 60) or a.name
        a.persona = _text(row.get("persona"))
        _stats_in(a.base_stats, row.get("base_stats") or {})
        _stats_in(a.growth, row.get("growth") or {})
        a.skill_ids = skills
        a.resistances = _resist_in(row.get("resistances"))
        a.is_melee = bool(row.get("is_melee"))


def _boss_lookup(row_id: str):
    """('boss', BossDef) or ('member', BossMember, BossDef) for ids like 'unbroken_pair_boss/ronan'."""
    from data import bosses as B
    allb = {**B.BOSSES, **B.WORLD_BOSSES}
    if "/" in row_id:
        bid, key = row_id.split("/", 1)
        b = allb.get(bid)
        for m in (b.members if b else []):
            if m.key == key:
                return "member", m, b
        return None
    b = allb.get(row_id)
    return ("boss", b, b) if b else None


class BossesTable(Table):
    id, label = "bosses", "Bosses"
    desc = ("Boss fights. Boss level = the fixed level if one is set (story bosses), otherwise average party level + level offset. "
            "HP multiplier scales the grown max HP. Two-boss fights list each member on its own row.")
    fields = _COMBAT_FIELDS + [
        _f("hp_mult", "HP multiplier", "float"), _f("level_offset", "Level offset (when no fixed level)", "int"),
        _f("fixed_level", "Fixed level (0 = none)", "int"),
        _f("rewards_first", "First-clear rewards", "numdict", keys=["money", "gems", "xp"]),
        _f("rewards_repeat", "Rematch rewards", "numdict", keys=["money", "gems", "xp"])]

    def rows(self):
        from data import bosses as B
        out = []
        for b in {**B.BOSSES, **B.WORLD_BOSSES}.values():
            if b.members:
                for m in b.members:
                    out.append({"id": f"{b.id}/{m.key}", "name": m.name, "persona": m.persona, "base_stats": _stats_out(m.base_stats),
                                "growth": _stats_out(m.growth), "skill_ids": list(m.skill_ids), "resistances": _resist_out(m.resistances),
                                "hp_mult": m.hp_mult, "level_offset": b.level_offset, "fixed_level": B.BOSS_FIXED_LEVELS.get(b.id, 0),
                                "rewards_first": dict(b.rewards_first), "rewards_repeat": dict(b.rewards_repeat), "group": b.name})
            else:
                out.append({"id": b.id, "name": b.name, "persona": b.persona, "base_stats": _stats_out(b.base_stats),
                            "growth": _stats_out(b.growth), "skill_ids": list(b.skill_ids), "resistances": _resist_out(b.resistances),
                            "hp_mult": b.hp_mult, "level_offset": b.level_offset, "fixed_level": B.BOSS_FIXED_LEVELS.get(b.id, 0),
                            "rewards_first": dict(b.rewards_first), "rewards_repeat": dict(b.rewards_repeat)})
        return out

    def apply(self, row):
        from data import bosses as B
        hit = _boss_lookup(str(row.get("id")))
        if hit is None:
            raise ValueError("unknown boss")
        kind, obj, boss = hit
        skills = _ids(row.get("skill_ids"), _skill_ids())
        obj.name = _text(row.get("name"), 60) or obj.name
        obj.persona = _text(row.get("persona"))
        _stats_in(obj.base_stats, row.get("base_stats") or {})
        _stats_in(obj.growth, row.get("growth") or {})
        obj.skill_ids = skills
        obj.resistances = _resist_in(row.get("resistances"))
        obj.hp_mult = _float(row.get("hp_mult"), 0.1, 100.0, 1.0)
        boss.level_offset = _int(row.get("level_offset"), -50, 50)
        fl = _int(row.get("fixed_level"), 0, 99)
        if fl:
            B.BOSS_FIXED_LEVELS[boss.id] = fl
        else:
            B.BOSS_FIXED_LEVELS.pop(boss.id, None)
        for key in ("rewards_first", "rewards_repeat"):
            src = row.get(key) or {}
            setattr(boss, key, {k: _int(src.get(k), 0, 10 ** 7) for k in ("money", "gems", "xp")})


# ---- Shops and blacksmiths ------------------------------------------------------------------------------------------
class ShopsTable(Table):
    id, label = "shops", "Shops"
    desc = "What each shopkeeper sells. 'Everything rare' ignores the equipment list and stocks every rare piece for sale."
    fields = [_f("name", "Shop name"), _f("note", "Tagline"), _f("for_heroes", "Picked for heroes (comma separated, blank = anyone)", "strlist"),
              _f("items", "Consumables", "idlist", catalog="items"), _f("all_rare", "Stock everything rare", "bool"),
              _f("equipment", "Equipment", "idlist", catalog="equipment")]

    def rows(self):
        from data.vendors import SHOPS
        return [{"id": k, "name": s["name"], "note": s["note"], "for_heroes": list(s["for_heroes"] or []), "items": list(s["items"]),
                 "all_rare": s["equipment"] == "ALL_RARE", "equipment": [] if s["equipment"] == "ALL_RARE" else list(s["equipment"])}
                for k, s in SHOPS.items()]

    def apply(self, row):
        from data.vendors import SHOPS
        from data.items_db import ITEMS
        from data.equipment_db import EQUIPMENT
        s = SHOPS.get(row.get("id"))
        if s is None:
            raise ValueError("unknown shop")
        items = _ids(row.get("items"), ITEMS)
        equip = _ids(row.get("equipment"), EQUIPMENT)
        s["name"] = _text(row.get("name"), 60) or s["name"]
        s["note"] = _text(row.get("note"), 200)
        heroes = [h.strip() for h in (row.get("for_heroes") or []) if str(h).strip()]
        s["for_heroes"] = heroes or None
        s["items"] = items
        s["equipment"] = "ALL_RARE" if row.get("all_rare") else equip


class SmithsTable(Table):
    id, label = "smiths", "Blacksmiths"
    desc = "The highest weapon upgrade level (1-10) each blacksmith can take a weapon to."
    fields = [_f("name", "Name"), _f("cap", "Upgrade cap", "int")]

    def rows(self):
        from data.vendors import SMITHS
        return [{"id": k, "name": s["name"], "cap": s["cap"]} for k, s in SMITHS.items()]

    def apply(self, row):
        from data.vendors import SMITHS
        s = SMITHS.get(row.get("id"))
        if s is None:
            raise ValueError("unknown blacksmith")
        s["name"] = _text(row.get("name"), 60) or s["name"]
        s["cap"] = _int(row.get("cap"), 1, 10, s["cap"])


# ---- Drops and battle rewards ---------------------------------------------------------------------------------------
class DropsTable(Table):
    id, label = "drops", "Drops & rewards"
    desc = ("Global payout tuning: money/gems/XP for a win, how often items, tickets and shards drop, and what bosses always give. "
            "(These are multiplied by the difficulty and team-size modifiers.)")
    can_add = False
    fields = [
        _f("victory_money", "Win: money range", "range"), _f("victory_gems", "Win: gems range", "range"), _f("victory_xp", "Win: XP range (per hero)", "range"),
        _f("loss_money", "Loss: money range", "range"), _f("fled_money", "Fled: money range", "range"),
        _f("item_drop_chance", "Chance a random fight drops an item (0-1)", "float"),
        _f("item_drop_table", "Item drop table", "rows", of=[
            _f("item", "Item", "select", catalog="items"), _f("weight", "Weight", "int"), _f("min_level", "Min enemy level", "int")]),
        _f("ticket_drop_chance", "Ticket chance per win (0-1)", "numdict", keys=["common", "premium"], float=True),
        _f("boss_tickets_first", "Boss tickets: first clear", "numdict", keys=["common", "premium"]),
        _f("boss_tickets_repeat", "Boss tickets: rematch", "numdict", keys=["common", "premium"]),
        _f("shard_drop_chance", "Equipment shard chance per win (0-1)", "float"), _f("shard_drop_range", "Equipment shards when it drops", "range"),
        _f("boss_shards_first", "Boss shards: first clear", "int"), _f("boss_shards_repeat", "Boss shards: rematch", "int"),
        _f("hero_shard_drop_chance", "Hero-rival shard chance (0-1)", "float")]

    def rows(self):
        from game import rewards as R
        from data import summon_pool as S
        return [{"id": "drops",
                 "victory_money": list(R.VICTORY_MONEY_RANGE), "victory_gems": list(R.VICTORY_GEM_RANGE), "victory_xp": list(R.VICTORY_XP_RANGE),
                 "loss_money": list(R.LOSS_MONEY_RANGE), "fled_money": list(R.FLED_MONEY_RANGE),
                 "item_drop_chance": R.ITEM_DROP_CHANCE,
                 "item_drop_table": [{"item": i, "weight": w, "min_level": lo} for i, w, lo in R.ITEM_DROP_TABLE],
                 "ticket_drop_chance": dict(S.TICKET_DROP_CHANCE), "boss_tickets_first": dict(S.BOSS_TICKETS_FIRST),
                 "boss_tickets_repeat": dict(S.BOSS_TICKETS_REPEAT),
                 "shard_drop_chance": S.EQUIPMENT_SHARD_DROP_CHANCE, "shard_drop_range": list(S.EQUIPMENT_SHARD_DROP_RANGE),
                 "boss_shards_first": S.BOSS_EQUIPMENT_SHARDS_FIRST, "boss_shards_repeat": S.BOSS_EQUIPMENT_SHARDS_REPEAT,
                 "hero_shard_drop_chance": R.HERO_SHARD_DROP_CHANCE}]

    def apply(self, row):
        from game import rewards as R
        from data import summon_pool as S
        from data.items_db import ITEMS

        def rng(key, hi=10 ** 7):
            a, b = (list(row.get(key) or [0, 0]) + [0, 0])[:2]
            a, b = _int(a, 0, hi), _int(b, 0, hi)
            return (min(a, b), max(a, b))
        table = []
        for r in (row.get("item_drop_table") or []):
            if r.get("item") not in ITEMS:
                raise ValueError(f"unknown item {r.get('item')!r}")
            table.append((r["item"], _int(r.get("weight"), 0, 10 ** 6), _int(r.get("min_level"), 1, 99, 1)))
        R.VICTORY_MONEY_RANGE, R.VICTORY_GEM_RANGE, R.VICTORY_XP_RANGE = rng("victory_money"), rng("victory_gems"), rng("victory_xp")
        R.LOSS_MONEY_RANGE, R.FLED_MONEY_RANGE = rng("loss_money"), rng("fled_money")
        R.ITEM_DROP_CHANCE = _float(row.get("item_drop_chance"), 0.0, 1.0)
        R.ITEM_DROP_TABLE = tuple(table)
        R.HERO_SHARD_DROP_CHANCE = _float(row.get("hero_shard_drop_chance"), 0.0, 1.0)
        for name, key, conv in (("TICKET_DROP_CHANCE", "ticket_drop_chance", lambda v: _float(v, 0.0, 1.0)),
                                ("BOSS_TICKETS_FIRST", "boss_tickets_first", lambda v: _int(v, 0, 99)),
                                ("BOSS_TICKETS_REPEAT", "boss_tickets_repeat", lambda v: _int(v, 0, 99))):
            d = getattr(S, name)                       # mutated in place: other modules hold a reference to the same dict
            src = row.get(key) or {}
            for kind in list(d):
                d[kind] = conv(src.get(kind))
        S.EQUIPMENT_SHARD_DROP_CHANCE = _float(row.get("shard_drop_chance"), 0.0, 1.0)
        S.EQUIPMENT_SHARD_DROP_RANGE = rng("shard_drop_range", 9999)
        S.BOSS_EQUIPMENT_SHARDS_FIRST = _int(row.get("boss_shards_first"), 0, 9999)
        S.BOSS_EQUIPMENT_SHARDS_REPEAT = _int(row.get("boss_shards_repeat"), 0, 9999)


# ---- Quests (JSON files, edited in place) ----------------------------------------------------------------------------
class _JsonListTable(Table):
    file_backed = True
    can_add = True
    can_delete = True
    filename = ""
    list_key: Optional[str] = None            # None = the file is a bare list

    def _path(self) -> Path:
        return _quest_dir / self.filename

    def _load(self):
        data = json.loads(self._path().read_text(encoding="utf-8"))
        return data, (data[self.list_key] if self.list_key else data)

    def _save(self, data) -> None:
        p = self._path()
        bdir = p.parent / "db_backups"
        bdir.mkdir(exist_ok=True)
        (bdir / f"{p.stem}.{time.strftime('%Y%m%d-%H%M%S')}{p.suffix}").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        p.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


_STEP_FIELDS = [_f("text", "Text"), _f("if", "Shows once flag is set"), _f("unless", "Until this flag is set"),
                _f("count", "Counts these flags (comma separated)", "strlist")]


def _step_in(s: dict) -> dict:
    out = {"text": _text(s.get("text"), 600), "if": _text(s.get("if"), 80).strip(), "unless": _text(s.get("unless"), 80).strip()}
    cnt = [c.strip() for c in (s.get("count") or []) if str(c).strip()]
    if cnt:
        out["count"] = cnt
    return {k: v for k, v in out.items() if v or k == "text"}


class QuestsTable(_JsonListTable):
    id, label = "quests", "Quests"
    desc = ("Journal entries from html_hub/3d/quests.json. A quest shows once its 'accept' flag is set and is finished at its 'done' flag; "
            "each step shows while its 'if' flag is set and its 'unless' flag is not. Reload the game page to see changes. "
            "(Re-running make_quests.py regenerates this file and discards edits.)")
    filename, list_key = "quests.json", "quests"
    fields = [_f("title", "Title"), _f("kind", "Kind", "select", options=["main", "side"]), _f("giver", "Quest giver"), _f("where", "Where"),
              _f("summary", "Summary", "area"), _f("accept", "Accept flag"), _f("done", "Done flag"), _f("ready", "Ready-to-turn-in flag"),
              _f("steps", "Steps", "rows", of=_STEP_FIELDS)]

    def rows(self):
        _, qs = self._load()
        return [{"id": q["id"], "title": q.get("title", ""), "kind": q.get("kind", "side"), "giver": q.get("giver", ""), "where": q.get("where", ""),
                 "summary": q.get("summary", ""), "accept": q.get("accept", ""), "done": q.get("done", ""), "ready": q.get("ready", ""),
                 "steps": [{"text": s.get("text", ""), "if": s.get("if", ""), "unless": s.get("unless", ""), "count": s.get("count", [])}
                           for s in q.get("steps", [])]} for q in qs]

    def apply(self, row):
        data, qs = self._load()
        new = {"id": str(row["id"]), "kind": row.get("kind") if row.get("kind") in ("main", "side") else "side",
               "title": _text(row.get("title"), 120), "giver": _text(row.get("giver"), 80), "where": _text(row.get("where"), 120),
               "summary": _text(row.get("summary"), 800), "accept": _text(row.get("accept"), 80).strip(), "done": _text(row.get("done"), 80).strip(),
               "steps": [_step_in(s) for s in (row.get("steps") or [])]}
        if _text(row.get("ready"), 80).strip():
            new["ready"] = _text(row.get("ready"), 80).strip()
        for i, q in enumerate(qs):
            if q["id"] == new["id"]:
                qs[i] = {**q, **new}
                if "ready" not in new:
                    qs[i].pop("ready", None)
                break
        else:
            qs.append(new)
        self._save(data)

    def new_row(self):
        _, qs = self._load()
        n = 1
        while any(q["id"] == f"quest_{n}" for q in qs):
            n += 1
        return {"id": f"quest_{n}", "title": "New quest", "kind": "side", "giver": "", "where": "", "summary": "", "accept": "", "done": "",
                "ready": "", "steps": [{"text": "", "if": "", "unless": "", "count": []}]}

    def delete(self, row_id):
        data, qs = self._load()
        qs[:] = [q for q in qs if q["id"] != row_id]
        self._save(data)


class SideLogTable(_JsonListTable):
    id, label = "sidelog", "Side-quest log lines"
    desc = ("One-line objectives from html_hub/3d/sidequests.json, shown in the quest log while 'if' is set and 'unless' is not. "
            "Row numbers are just positions in the file.")
    filename = "sidequests.json"
    fields = _STEP_FIELDS

    def rows(self):
        _, ls = self._load()
        return [{"id": str(i + 1), "text": s.get("text", ""), "if": s.get("if", ""), "unless": s.get("unless", ""), "count": s.get("count", [])}
                for i, s in enumerate(ls)]

    def apply(self, row):
        data, ls = self._load()
        i = int(row["id"]) - 1
        new = _step_in(row)
        if 0 <= i < len(ls):
            ls[i] = new
        else:
            ls.append(new)
        self._save(data)

    def new_row(self):
        _, ls = self._load()
        return {"id": str(len(ls) + 1), "text": "New objective", "if": "", "unless": "", "count": []}

    def delete(self, row_id):
        data, ls = self._load()
        i = int(row_id) - 1
        if 0 <= i < len(ls):
            ls.pop(i)
        self._save(data)


# ---- registry / persistence -----------------------------------------------------------------------------------------
for _t in (ItemsTable(), EquipmentTable(), EnemiesTable(), BossesTable(), ShopsTable(), SmithsTable(), DropsTable(), QuestsTable(), SideLogTable()):
    TABLES[_t.id] = _t

_OVERRIDE_FILE = "db_overrides.json"


def init(data_dir: Path, quest_dir: Path, apply_overrides: bool = True) -> List[str]:
    """Snapshot the shipped values (for Reset), then re-apply the saved overrides. Returns problems (empty = fine)."""
    global _data_dir, _quest_dir, _overrides
    _data_dir, _quest_dir = Path(data_dir), Path(quest_dir)
    problems: List[str] = []
    for t in TABLES.values():
        if not t.file_backed:
            _defaults[t.id] = {r["id"]: json.loads(json.dumps(r)) for r in t.rows()}
    _overrides = {}
    path = _data_dir / _OVERRIDE_FILE
    if apply_overrides and path.is_file():
        try:
            _overrides = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return [f"{_OVERRIDE_FILE} unreadable: {exc}"]
        for tid, rows in list(_overrides.items()):
            t = TABLES.get(tid)
            for rid, row in list(rows.items()):
                try:
                    if t is None or t.file_backed:
                        raise ValueError("table no longer exists")
                    t.apply(row)
                except Exception as exc:                          # a stale override (an id that was removed) must not stop the game
                    problems.append(f"{tid}/{rid}: {exc}")
                    rows.pop(rid, None)
    return problems


def _persist() -> None:
    clean = {t: r for t, r in _overrides.items() if r}
    path = _data_dir / _OVERRIDE_FILE
    if clean:
        path.write_text(json.dumps(clean, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    elif path.is_file():
        path.unlink()


def catalogs() -> dict:
    from data.items_db import ITEMS
    from data.equipment_db import EQUIPMENT
    return {"items": [{"id": i.id, "name": i.name} for i in ITEMS.values()],
            "equipment": [{"id": e.id, "name": f"{e.name} ({e.rarity} {e.slot})"} for e in EQUIPMENT.values()],
            "skills": sorted(({"id": k, "name": getattr(s, "name", k)} for k, s in _skill_ids().items()), key=lambda x: x["name"].lower())}


def schema() -> dict:
    return {"tables": [t.schema() for t in TABLES.values()], "catalogs": catalogs(), "stat_keys": list(STAT_KEYS),
            "stat_labels": STAT_LABEL, "elements": list(ELEMENTS)}


def list_rows(table: str) -> dict:
    t = TABLES[table]
    over = _overrides.get(table, {})
    return {"rows": t.rows(), "edited": sorted(over), "defaults_known": not t.file_backed}


def save_row(table: str, row: dict) -> dict:
    t = TABLES[table]
    t.apply(row)
    if not t.file_backed:
        _overrides.setdefault(table, {})[str(row["id"])] = json.loads(json.dumps(row))
        _persist()
    saved = next((r for r in t.rows() if str(r["id"]) == str(row["id"])), row)
    return {"row": saved}


def reset_row(table: str, row_id: str) -> dict:
    t = TABLES[table]
    if t.file_backed:
        raise ValueError("quest files have no shipped copy to reset to (see html_hub/3d/db_backups)")
    base = _defaults.get(table, {}).get(row_id)
    if base is None:
        raise ValueError("unknown row")
    t.apply(base)
    _overrides.get(table, {}).pop(row_id, None)
    _persist()
    return {"row": next(r for r in t.rows() if str(r["id"]) == row_id)}


def new_row(table: str) -> dict:
    t = TABLES[table]
    if not t.can_add:
        raise ValueError("this table has a fixed set of rows")
    return t.new_row()


def delete_row(table: str, row_id: str) -> None:
    t = TABLES[table]
    if not t.can_delete:
        raise ValueError("rows can't be deleted from this table")
    t.delete(row_id)

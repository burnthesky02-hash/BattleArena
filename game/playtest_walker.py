"""playtest_walker.py -- DEBUG-ONLY offline playtest of the whole story, no browser, no server.

The story lives in the 3D scene files (html_hub/3d/<scene>.json): trigger zones and NPC scripts that set flags,
warp between scenes and start fights, all run by hub3d.js in the browser. This module re-plays that logic the same
way hub3d.js does (flag specs, showIf/hideIf, per-action if/unless/minRank, autorun on scene load and after every
flag change, battle wins coming back as a flag) and walks the game from a brand-new save like a player would:
talk to everyone, step on every zone, win every fight, take every warp -- until nothing else can change.

What it tells you:
  * whether the main story can be finished from a new game (m_wood ... m_reach, final flag rc_end)
  * every quest (main + side): reachable / completed / the exact step it gets stuck on
  * content that can never appear (NPCs, zones, autoruns whose flags are never satisfied)
  * flags that are read but never set anywhere (typos, content nobody finished), and flags set but never read
  * warps to scenes that do not exist, battles naming bosses that do not exist, shops with no vendor entry
  * the story beats in the order a player meets them, with every battle and its level
  * places where the walk had to assume a Colosseum rank (those need real ladder fights in the live bot)

Debug only: it refuses to run unless DEBUG=1 / --debug (same gate as the in-game debug tools).

    python -m game.playtest_walker --debug            (from the project root)
    python -m game.playtest_walker --debug --json     (machine-readable result)
Writes saves/playtest_story_report.md unless --no-report.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCENE_DIR = PROJECT_ROOT / "html_hub" / "3d"
MAX_RANK = 99

# Scene files that are not scenes.
NON_SCENES = {"quests", "sidequests", "stills", "sprites", "dungeon_layout"}


# ------------------------------------------------------------------ data loading
def load_scenes(scene_dir: Path = SCENE_DIR) -> Dict[str, dict]:
    scenes = {}
    for p in sorted(scene_dir.glob("*.json")):
        if ".pre_" in p.name or p.stem in NON_SCENES:
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and ("events" in d or "npcs" in d):
            scenes[p.stem] = d
    return scenes


def load_quests(scene_dir: Path = SCENE_DIR) -> dict:
    try:
        return json.loads((scene_dir / "quests.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"quests": [], "marks": {}}


def known_boss_ids() -> Set[str]:
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from data.bosses import WORLD_BOSSES, BOSSES          # the real tables when the project imports cleanly
        return set(WORLD_BOSSES) | set(BOSSES)
    except Exception:
        txt = (PROJECT_ROOT / "data" / "bosses.py").read_text(encoding="utf-8", errors="ignore")
        return set(re.findall(r'"([a-z0-9_]+_boss)"', txt))


def known_vendor_keys() -> Set[str]:
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from data import vendors
        return set(getattr(vendors, "SHOPS", {})) | set(getattr(vendors, "SMITHS", {})) | set(getattr(vendors, "BLACKSMITHS", {}))
    except Exception:
        return set()


# ------------------------------------------------------------------ hub3d.js flag logic, ported 1:1
def has(flags: Set[str], spec) -> bool:
    if not spec:
        return True
    for t in str(spec).split(","):
        t = t.strip()
        if not t:
            continue
        if t[0] == "!":
            if t[1:] in flags:
                return False
        elif t not in flags:
            return False
    return True


def spec_flags(spec) -> List[str]:
    out = []
    for t in str(spec or "").split(","):
        t = t.strip().lstrip("!")
        if t:
            out.append(t)
    return out


class World:
    def __init__(self, scenes: Dict[str, dict], quests: dict, start_rank: int = 0):
        self.scenes = scenes
        self.quests = quests
        self.flags: Set[str] = set()
        self.rank = start_rank
        self.party: Dict[str, bool] = {"Kael": True}       # name -> in story party (away=False)
        self.scene: Optional[str] = None
        self.trace: List[dict] = []                         # story beats in order
        self.seen_visible: Dict[str, Set[str]] = {s: set() for s in scenes}   # trigger ids ever visible
        self.visited: List[str] = []
        self.battles: List[dict] = []
        self.warnings: List[str] = []
        self.rank_blocks: Dict[str, dict] = {}
        self.steps = 0

    # --- conditions
    def min_rank_of(self, e: dict, scene: str) -> int:
        m = e.get("minRank")
        if isinstance(m, str):
            m = self.scenes.get(scene, {}).get(m, 0)
        try:
            return int(m or 0)
        except (TypeError, ValueError):
            return 0

    def cond_ok(self, e: dict, scene: str, note: Optional[str] = None) -> bool:
        if e.get("if") and not has(self.flags, e["if"]):
            return False
        if e.get("unless") and has(self.flags, e["unless"]):
            return False
        mr = self.min_rank_of(e, scene)
        if mr and self.rank < mr:
            self.rank_blocks.setdefault(f"{scene}:{note or '?'}", {"scene": scene, "where": note or "", "needs": mr})
            return False
        return True

    def visible(self, o: dict) -> bool:
        return (not o.get("hideIf") or not has(self.flags, o["hideIf"])) and (not o.get("showIf") or has(self.flags, o["showIf"]))

    # --- triggers visible in a scene right now
    def triggers(self, scene: str) -> List[dict]:
        d = self.scenes[scene]
        out = []
        for e in d.get("events", []):
            if self.visible(e):
                out.append({"kind": "event", "id": e.get("id", "?"), "o": e})
        for n in d.get("npcs", []):
            if self.visible(n):
                out.append({"kind": "npc", "id": n.get("id", "?"), "o": n})
        for t in out:
            self.seen_visible[scene].add(f'{t["kind"]}:{t["id"]}')
        return out

    # --- run one script; returns ("end"|"warp"|"battle", payload, dirty)
    def run_actions(self, scene: str, actions: List[dict], owner: str):
        dirty = False
        for a in actions:
            if not self.cond_ok(a, scene, f"{owner}/{a.get('type')}"):
                continue
            t = a.get("type")
            if t == "flag" and a.get("key"):
                if a["key"] not in self.flags:
                    self.flags.add(a["key"]); dirty = True
                    self.trace.append({"scene": scene, "who": owner, "beat": f"flag {a['key']}"})
            elif t == "unflag":
                before = set(self.flags)
                if a.get("key"):
                    self.flags.discard(a["key"])
                if a.get("prefix"):
                    self.flags = {k for k in self.flags if not k.startswith(a["prefix"])}
                dirty = dirty or before != self.flags
            elif t == "reset_progress":
                pre = a.get("prefix", "")
                self.flags = {k for k in self.flags if pre and not k.startswith(pre)}
                self.trace.append({"scene": scene, "who": owner, "beat": f"reset_progress '{pre}'"})
                dirty = True
            elif t == "warp":
                return "warp", a, dirty
            elif t == "battle":
                return "battle", a, dirty
            elif t == "recruit":
                self.party.setdefault(a.get("name", "?"), True)
                self.trace.append({"scene": scene, "who": owner, "beat": f"{a.get('name')} joins"})
            elif t == "away":
                if a.get("name") in self.party:
                    self.party[a["name"]] = a.get("away") is False
            # say / cam / fade / chest / rest / game / pass_time / tp / music ...: no state we track
        return "end", None, dirty

    # --- entering a scene: autorun, repeated after every flag change (hub3d.js reloads the scene on a dirty script)
    def enter(self, scene: str, depth: int = 0):
        if depth > 60:
            self.warnings.append(f"autorun/warp chain deeper than 60 starting at {scene}: probable loop")
            return
        if scene not in self.scenes:
            self.warnings.append(f"warp to unknown scene '{scene}'")
            return
        self.scene = scene
        if scene not in self.visited:
            self.visited.append(scene)
        self.triggers(scene)
        for _ in range(40):
            entry = next((e for e in self.scenes[scene].get("autorun", []) if self.cond_ok(e, scene, "autorun")), None)
            if not entry:
                return
            before = set(self.flags)
            outcome, a, dirty = self.run_actions(scene, entry.get("actions", []), "autorun")
            if self.resolve(scene, outcome, a, dirty, depth, "autorun"):
                return                                     # the script left the scene (warp / handled recursively)
            if set(self.flags) == before:
                return                                     # nothing changed: no reload, no new autorun
        self.warnings.append(f"autorun in {scene} kept changing state for 40 rounds: probable loop")

    def resolve(self, scene: str, outcome: str, a: Optional[dict], dirty: bool, depth: int, owner: str) -> bool:
        """True when control left this scene's autorun loop (warped away)."""
        if outcome == "warp":
            self.trace.append({"scene": scene, "who": owner, "beat": f"warp -> {a.get('scene')}"})
            self.enter(a.get("scene", ""), depth + 1)
            return True
        if outcome == "battle":
            key = a.get("key") or ""
            lvl = a.get("level") or a.get("level_rel") or a.get("level_min") or ""
            self.battles.append({"scene": scene, "who": owner, "boss": a.get("boss") or "", "key": key, "level": lvl, "elite": a.get("elite", 0)})
            self.trace.append({"scene": scene, "who": owner, "beat": f"BATTLE {a.get('boss') or 'wild'} key={key or '-'} level={lvl or '-'}"})
            if key:
                self.flags.add(key)                        # a win comes back as ?cleared=<key>
            self.enter_after_battle(scene, depth)
            return True
        return False

    def enter_after_battle(self, scene: str, depth: int):
        self.scene = scene
        # the page reloads: scene filtered by the new flags, autorun runs again
        self.enter(scene, depth + 1)

    # --- the player's walk
    def fire(self, scene: str, trig: dict) -> bool:
        """Talk to / step on one trigger. Returns True when the world state changed."""
        o = trig["o"]
        before = (frozenset(self.flags), self.scene, tuple(sorted(self.party.items())))
        if o.get("actions"):
            outcome, a, dirty = self.run_actions(scene, o["actions"], f'{trig["id"]}')
            if outcome in ("warp", "battle"):
                self.resolve(scene, outcome, a, dirty, 0, trig["id"])
            elif dirty:
                self.enter(scene)                          # dirty script: the scene reloads and autorun runs
        after = (frozenset(self.flags), self.scene, tuple(sorted(self.party.items())))
        return before != after

    def warp_targets(self, scene: str) -> List[tuple]:
        out = []
        for t in self.triggers(scene):
            for a in (t["o"].get("actions") or []):
                if a.get("type") == "warp" and self.cond_ok(a, scene, f'{t["id"]}/warp'):
                    out.append((t, a.get("scene")))
                    break
        return out

    # --- navigation helpers
    def mark_of(self, scene: str, tid: str) -> str:
        spec = self.quests.get("marks", {}).get(f"{scene}/{tid}")
        if isinstance(spec, str):
            return spec
        if isinstance(spec, list):
            for m in spec:
                if self.cond_ok(m, scene, "mark"):
                    return m.get("mark", "")
        return ""

    @staticmethod
    def is_side(scene: str, trig: dict) -> bool:
        return str(trig["id"]).startswith("sq_")

    def warp_graph(self) -> Dict[str, List[tuple]]:
        g: Dict[str, List[tuple]] = {}
        for s in self.scenes:
            g[s] = [(t, dest) for t, dest in self.warp_targets_quiet(s) if dest in self.scenes]
        return g

    def warp_targets_quiet(self, scene: str) -> List[tuple]:
        out = []
        d = self.scenes[scene]
        for kind, coll in (("event", "events"), ("npc", "npcs")):
            for o in d.get(coll, []):
                if not self.visible(o):
                    continue
                for a in (o.get("actions") or []):
                    if a.get("type") == "warp" and self.cond_ok(a, scene, f"{o.get('id')}/warp"):
                        out.append(({"kind": kind, "id": o.get("id", "?"), "o": o}, a.get("scene")))
                        break
        return out

    def reachable(self, src: str) -> Dict[str, List[tuple]]:
        """BFS over the warps a player could take right now: scene -> path [(trigger, dest), ...]"""
        g = self.warp_graph()
        paths = {src: []}
        queue = [src]
        while queue:
            cur = queue.pop(0)
            for t, dest in g.get(cur, []):
                if dest not in paths:
                    paths[dest] = paths[cur] + [(cur, t, dest)]
                    queue.append(dest)
        return paths

    def adds_flags(self, trig: dict, scene: str) -> bool:
        """Dry run: would this trigger set a flag that is not set yet (a battle with a key counts)?"""
        o = trig["o"]
        if not o.get("actions"):
            return False
        saved = (set(self.flags), self.rank, dict(self.party), list(self.trace), list(self.battles), list(self.warnings),
                 None, self.scene, list(self.visited))
        try:
            outcome, a, dirty = self.run_actions(scene, o["actions"], trig["id"])
            new = set(self.flags) - saved[0]
            if outcome == "battle" and (a.get("key") or "") and a["key"] not in saved[0]:
                new.add(a["key"])
            return bool(new)
        finally:
            (self.flags, self.rank, self.party, self.trace, self.battles, self.warnings, _rb, self.scene, self.visited) = saved

    def candidates(self, reach: Dict[str, List[tuple]]) -> List[dict]:
        out = []
        for scene, path in reach.items():
            for t in self.triggers(scene):
                if self.fired.get((scene, t["id"]), 0) >= 6:
                    continue
                if self.adds_flags(t, scene):
                    mk = self.mark_of(scene, t["id"])
                    out.append({"scene": scene, "t": t, "path": path, "dist": len(path),
                                "main": mk.startswith("main"), "side": mk.startswith("side") or self.is_side(scene, t)})
        return out

    def go(self, c: dict):
        for (scene, trig, dest) in c["path"]:
            if self.scene != scene:
                return False                                   # an autorun moved us: re-plan
            self.fire(scene, trig)
            if self.scene != dest:
                return False
        self.fired[(c["scene"], c["t"]["id"])] = self.fired.get((c["scene"], c["t"]["id"]), 0) + 1
        self.fire(c["scene"], c["t"])
        return True

    def play(self, completionist: bool = True, max_steps: int = 3000):
        """completionist=True: do every side quest / chest / extra first, then the next main step (what a thorough
        player does). False: only follow the main quest marks and whatever the story forces (a speed-runner)."""
        self.flags = set()
        self.fired: Dict[tuple, int] = {}
        self.enter("island")                               # a new game starts on Paradise Island
        while self.steps < max_steps:
            self.steps += 1
            reach = self.reachable(self.scene)
            cands = self.candidates(reach)
            pick = None
            if completionist:
                pool = [c for c in cands if c["side"] and not c["main"]]
                if pool:
                    pick = min(pool, key=lambda c: c["dist"])
            if pick is None:
                pool = [c for c in cands if c["main"]]
                if pool:
                    pick = min(pool, key=lambda c: c["dist"])
            if pick is None:
                pool = [c for c in cands if not c["side"]]
                if pool:
                    pick = min(pool, key=lambda c: c["dist"])
            if pick is None and completionist:
                pool = cands
                if pool:
                    pick = min(pool, key=lambda c: c["dist"])
            if pick is not None:
                self.go(pick)
                continue
            blocks = [b for b in self.rank_blocks.values() if b["needs"] > self.rank]
            if blocks:                                     # only a Colosseum rank gate is in the way: assume it was earned
                need = min(b["needs"] for b in blocks)
                self.trace.append({"scene": self.scene, "who": "walker", "beat": f"ASSUMED Colosseum rank {need} (needs real ladder fights)"})
                self.rank = need
                self.enter(self.scene)
                continue
            break


# ------------------------------------------------------------------ analysis
def collect_flag_use(scenes: Dict[str, dict], quests: dict):
    setters: Dict[str, List[str]] = {}
    readers: Dict[str, List[str]] = {}

    def add(d, k, where):
        d.setdefault(k, []).append(where)

    def read(spec, where):
        for f in spec_flags(spec):
            add(readers, f, where)

    for sname, d in scenes.items():
        for kind in ("events", "npcs"):
            for o in d.get(kind, []):
                where = f"{sname}/{o.get('id', '?')}"
                read(o.get("showIf"), where); read(o.get("hideIf"), where)
                for a in o.get("actions", []) or []:
                    read(a.get("if"), where); read(a.get("unless"), where)
                    if a.get("type") == "flag" and a.get("key"):
                        add(setters, a["key"], where)
                    if a.get("type") == "battle" and a.get("key"):
                        add(setters, a["key"], where + " (battle win)")
        for key in ("autorun", "objectives"):
            for e in d.get(key, []) or []:
                where = f"{sname}/{key}"
                read(e.get("if"), where); read(e.get("unless"), where)
                for a in e.get("actions", []) or []:
                    read(a.get("if"), where); read(a.get("unless"), where)
                    if a.get("type") == "flag" and a.get("key"):
                        add(setters, a["key"], where)
                    if a.get("type") == "battle" and a.get("key"):
                        add(setters, a["key"], where + " (battle win)")
        for coll in ("pieces", "colliders", "decals"):
            for o in d.get(coll, []) or []:
                if isinstance(o, dict):
                    read(o.get("showIf"), f"{sname}/{coll}"); read(o.get("hideIf"), f"{sname}/{coll}")
    for q in quests.get("quests", []):
        for k in ("accept", "done", "ready"):
            read(q.get(k), f"quest {q['id']}.{k}")
        for st in q.get("steps", []) or []:
            read(st.get("if"), f"quest {q['id']} step"); read(st.get("unless"), f"quest {q['id']} step")
            for c in st.get("count") or []:
                read(c, f"quest {q['id']} count")
    return setters, readers


# flags the game itself maintains outside the scene files
ENGINE_FLAGS = set()


def analyse(w: World) -> dict:
    scenes, quests = w.scenes, w.quests
    setters, readers = collect_flag_use(scenes, quests)
    bosses = known_boss_ids()
    vendors = known_vendor_keys()
    problems: List[dict] = []

    def prob(sev, text):
        problems.append({"severity": sev, "text": text})

    for k in sorted(readers):
        if k not in setters and k not in ENGINE_FLAGS:
            prob("error", f"flag '{k}' is read ({', '.join(sorted(set(readers[k]))[:4])}) but nothing ever sets it")
    for k in sorted(setters):
        if k not in readers:
            prob("info", f"flag '{k}' is set ({setters[k][0]}) but nothing reads it")
    for sname, d in scenes.items():
        for kind in ("events", "npcs"):
            for o in d.get(kind, []):
                for a in o.get("actions", []) or []:
                    if a.get("type") == "warp" and a.get("scene") not in scenes:
                        prob("error", f"{sname}/{o.get('id')} warps to missing scene '{a.get('scene')}'")
                    if a.get("type") == "battle" and a.get("boss") and bosses and a["boss"] not in bosses:
                        prob("error", f"{sname}/{o.get('id')} fights unknown boss '{a['boss']}'")
                if o.get("action") in ("shop", "heroes") and vendors and f"{sname}/{o.get('id')}" not in vendors:
                    prob("warn", f"{sname}/{o.get('id')} is a {o['action']} NPC with no entry in data/vendors.py")
        for e in d.get("autorun", []) or []:
            for a in e.get("actions", []) or []:
                if a.get("type") == "warp" and a.get("scene") not in scenes:
                    prob("error", f"{sname}/autorun warps to missing scene '{a.get('scene')}'")
    # flag collisions: several different things in different scenes use the same flag as their "done" marker
    owners: Dict[str, List[str]] = {}
    for sname, d in scenes.items():
        for coll in ("events", "npcs"):
            for o in d.get(coll, []):
                hide = set(spec_flags(o.get("hideIf")))
                for a in o.get("actions", []) or []:
                    if a.get("type") == "flag" and a.get("key") in hide:
                        owners.setdefault(a["key"], []).append(f"{sname}/{o.get('id')}")
    for k, v in sorted(owners.items()):
        if len({x.split("/")[0] for x in v}) > 1:
            prob("error", f"flag '{k}' is the done-marker of {len(v)} different things in different scenes ({', '.join(v)}): "
                          f"using one hides the others for good, so the others can never be used")
    linked = {a.get("scene") for d in scenes.values() for coll in ("events", "npcs", "autorun") for o in d.get(coll, []) or []
              for a in o.get("actions", []) or [] if a.get("type") == "warp"}
    for sname in scenes:
        if sname not in w.visited and sname not in linked and sname != "island":
            prob("info", f"scene '{sname}' is not linked from any other scene (nothing warps to it), so it is skipped")
    # never-visible content
    for sname, d in scenes.items():
        for kind, coll in (("event", "events"), ("npc", "npcs")):
            for o in d.get(coll, []):
                tid = f"{kind}:{o.get('id', '?')}"
                if tid not in w.seen_visible.get(sname, set()) and (o.get("actions") or o.get("action") or o.get("line")):
                    cond = " ".join(x for x in (f"showIf={o['showIf']}" if o.get("showIf") else "", f"hideIf={o['hideIf']}" if o.get("hideIf") else "") if x)
                    if sname not in w.visited and sname not in linked:
                        continue                          # covered by the 'not linked' line above
                    why = "scene never reached" if sname not in w.visited else "never visible during the walk"
                    prob("warn", f"{sname}/{o.get('id')} ({kind}) never shown: {why} {cond}".strip())
    # quests
    qres = []
    for q in quests.get("quests", []):
        acc, done = q.get("accept") in w.flags, q.get("done") in w.flags
        step = ""
        if acc and not done:
            st = next((s for s in q.get("steps", []) or [] if (not s.get("if") or has(w.flags, s["if"])) and (not s.get("unless") or not has(w.flags, s["unless"]))), None)
            step = st.get("text", "") if st else ""
        qres.append({"id": q["id"], "kind": q.get("kind"), "title": q.get("title"), "accepted": acc, "done": done, "stuck_on": step})
        if q.get("kind") == "main" and not done:
            prob("error", f"MAIN quest '{q['id']}' ({q.get('title')}) is not finished: {'accepted' if acc else 'never accepted'}; {step}")
        elif not done:
            prob("warn", f"side quest '{q['id']}' ({q.get('title')}) not finished: {'accepted' if acc else 'never accepted'}; {step}")
    return {"problems": problems, "quests": qres}


def render_report(w: World, res: dict) -> str:
    mains = [q for q in res["quests"] if q["kind"] == "main"]
    ok = bool(mains) and all(q["done"] for q in mains)
    L = ["# Story playtest (offline walker)", "",
         f"**Result: {'the whole main story can be finished from a new game' if ok else 'the main story CANNOT be finished'}**", "",
         f"Scenes visited ({len(w.visited)}): {' -> '.join(w.visited)}", f"Final flags: {len(w.flags)}   Battles fought: {len(w.battles)}   "
         f"Highest Colosseum rank assumed: {w.rank}", "", "## Problems", ""]
    for sev in ("error", "warn", "info"):
        items = [p["text"] for p in res["problems"] if p["severity"] == sev]
        L.append(f"### {sev.upper()} ({len(items)})")
        L += [f"- {t}" for t in items] or ["- none"]
        L.append("")
    L += ["## Quests", ""]
    for q in res["quests"]:
        L.append(f"- [{'x' if q['done'] else ' '}] {q['kind']}: {q['title']} ({q['id']})" + (f" -- stuck on: {q['stuck_on']}" if q["stuck_on"] else ""))
    L += ["", "## Battles in the order a player meets them", ""]
    for i, b in enumerate(w.battles, 1):
        L.append(f"{i}. {b['scene']} / {b['who']}: {b['boss'] or 'wild fight'}" + (f"  level {b['level']}" if b['level'] else "") + (f"  (elite {b['elite']})" if b['elite'] else "") + (f"  -> flag {b['key']}" if b['key'] else ""))
    if w.warnings:
        L += ["", "## Walker warnings", ""] + [f"- {x}" for x in w.warnings]
    L += ["", "## Story beats", ""]
    last = None
    for t in w.trace:
        L.append(f"- {t['scene']} / {t['who']}: {t['beat']}")
    return "\n".join(L) + "\n"


def run(start_rank: int = 0, completionist: bool = True) -> tuple:
    scenes = load_scenes()
    w = World(scenes, load_quests(), start_rank)
    w.play(completionist=completionist)
    return w, analyse(w)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Offline whole-story playtest (debug only)")
    ap.add_argument("--debug", action="store_true", help="required (same gate as the other debug tools)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-report", action="store_true")
    ap.add_argument("--rank", type=int, default=0, help="Colosseum rank the walker starts with (it raises it itself when stuck)")
    args = ap.parse_args(argv)
    if not (args.debug or os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")):
        print("The playtest bot is debug-only. Run with --debug (or set DEBUG=1).")
        return 2
    w, res = run(args.rank, True)
    report = render_report(w, res)
    w2, res2 = run(args.rank, False)               # speed-run: main quest only
    mains2 = [q for q in res2["quests"] if q["kind"] == "main"]
    report += "\n## Speed-run check (main quest marks only, no side content)\n\n" + (
        "Main story finishes: yes\n" if mains2 and all(q["done"] for q in mains2) else
        "Main story finishes: NO -- stuck on: " + "; ".join(f"{q['id']} ({q['stuck_on'] or 'never accepted'})" for q in mains2 if not q["done"]) + "\n")
    if args.json:
        print(json.dumps({"flags": sorted(w.flags), "visited": w.visited, "battles": w.battles, **res}, indent=1))
    else:
        print(report)
    if not args.no_report:
        out = PROJECT_ROOT / "saves"
        try:
            out.mkdir(exist_ok=True)
            (out / "playtest_story_report.md").write_text(report, encoding="utf-8")
            print(f"[report written to {out / 'playtest_story_report.md'}]", file=sys.stderr)
        except OSError as e:
            print(f"[could not write report: {e}]", file=sys.stderr)
    errors = [p for p in res["problems"] if p["severity"] == "error"]
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

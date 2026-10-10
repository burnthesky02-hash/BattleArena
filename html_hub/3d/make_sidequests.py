"""Side content layer ("between the dungeons"): side quests, hidden pickups, optional elite mini-bosses, fishing and dice.

Patches the *existing* scene JSONs in place (island, forest, outside, asteroid). Never regenerates them, so the 3D builder's
hand edits survive. Idempotent: every object it adds has an id starting with "sq_" and is removed and re-added on each run;
the few original line-only NPCs it takes over only get a `showIf` (their old line plays once the quest is done).

Run:  python make_sidequests.py [scene ...]        (default: all four)

Flag names: sq_<quest>_q (accepted), sq_<thing> (item found / elite beaten), sq_<quest>_done (rewarded). Elite fights use the
`battle` action with `elite` (see hub_server.py ELITE_MULT) and `level_rel` so they scale with the party; the reward comes
from an `autorun` entry the moment you are back in the scene.
"""
import copy
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PREFIX = "sq_"


# ---------- action helpers ----------
def say(who, text, **cond):
    return dict(type="say", who=who, text=text, **cond)


def flag(key, **cond):
    return dict(type="flag", key=key, **cond)


def chest(loot, text="Reward", **cond):
    return dict(type="chest", loot=loot, text=text, **cond)


def battle(key, pool, rel, elite=0, **cond):
    a = dict(type="battle", key=key, pool=pool, level_rel=list(rel), **cond)
    if elite:
        a["elite"] = elite
    return a


def game(kind, stake=0, **extra):
    return dict(type="game", game=kind, stake=stake, **extra)


def npc(id, name, title, sprite, x, z, tint, actions=None, line=None, h=2.3, **cond):
    n = dict(id=PREFIX + id, name=name, title=title, sprite=sprite, x=x, z=z, h=h, tint=tint)
    if actions:
        n["actions"] = actions
    if line:
        n["line"] = line
    n.update(cond)
    return n


def event(id, name, prompt, x, z, actions, w=3.2, d=3.2, **cond):
    e = dict(id=PREFIX + id, name=name, x=x, z=z, w=w, d=d, trigger="talk", prompt=prompt, actions=actions)
    e.update(cond)
    return e


# ---------- placement: nearest free, reachable spot ----------
sys.path.insert(0, HERE)


def _load(name):
    with open(os.path.join(HERE, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


class Scene:
    def __init__(self, name):
        self.name = name
        self.d = _load(name)
        self.removed = 0
        for key in ("npcs", "events", "pieces", "decals", "colliders", "autorun"):
            if key not in self.d:
                continue
            keep = []
            for o in self.d[key]:
                oid = o.get("id", "") if isinstance(o, dict) else ""
                tag = o.get("sq") if isinstance(o, dict) else None
                if str(oid).startswith(PREFIX) or tag:
                    self.removed += 1
                else:
                    keep.append(o)
            self.d[key] = keep
        self.T = self.d.get("terrain")
        if self.T:
            import base64, struct
            raw = base64.b64decode(self.T["data"])
            self.h = [v / self.T["scale"] for v in struct.unpack("<%dh" % (len(raw) // 2), raw)]
        self.taken = []                         # spots handed out this run
        self._reach = None

    # ground height (matches hub3d.js gh())
    def gh(self, x, z):
        T = self.T
        if not T:
            return 0.0
        fx = (x - T["x0"]) / T["cell"]; fz = (z - T["z0"]) / T["cell"]
        fx = max(0, min(T["nx"] - 1.001, fx)); fz = max(0, min(T["nz"] - 1.001, fz))
        i = int(fx); j = int(fz); u = fx - i; v = fz - j; h = self.h; o = j * T["nx"] + i; nx = T["nx"]
        return (h[o] * (1 - u) + h[o + 1] * u) * (1 - v) + (h[o + nx] * (1 - u) + h[o + nx + 1] * u) * v

    def blocked(self, x, z, r, static=False):
        for c in self.d["colliders"]:
            if static and (c.get("hideIf") or c.get("showIf")):
                continue                       # gates that open (hideIf) or appear later (showIf) do not decide what is reachable
            if abs(x - c["x"]) < c["w"] / 2 + r and abs(z - c["z"]) < c["d"] / 2 + r:
                return True
        return False

    def reachable(self):
        if self._reach is not None:
            return self._reach
        b = self.d["bounds"]; sp = self.d["spawn"]
        step = 1.0
        seen = set(); stack = [(round(sp["x"]), round(sp["z"]))]
        while stack:
            cx, cz = stack.pop()
            if (cx, cz) in seen:
                continue
            x, z = cx * step, cz * step
            if x < b["minX"] or x > b["maxX"] or z < b["minZ"] or z > b["maxZ"]:
                continue
            if self.blocked(x, z, 0.45, static=True) and (cx, cz) != (round(sp["x"]), round(sp["z"])):
                continue
            seen.add((cx, cz))
            stack += [(cx + 1, cz), (cx - 1, cz), (cx, cz + 1), (cx, cz - 1)]
        self._reach = seen
        return seen

    def spot(self, x, z, r=1.5, gap=3.0, land=True):
        """The nearest point to (x, z) that is on land, clear of colliders, away from everything else and walkable from the spawn."""
        reach = self.reachable(); b = self.d["bounds"]
        others = [(o["x"], o["z"]) for k in ("npcs", "events") for o in self.d[k]] + self.taken
        best = None
        for ring in range(0, 22):
            for k in range(0, max(1, ring * 8)):
                a = 2 * math.pi * k / max(1, ring * 8)
                px, pz = x + math.cos(a) * ring, z + math.sin(a) * ring
                if px < b["minX"] + 2 or px > b["maxX"] - 2 or pz < b["minZ"] + 2 or pz > b["maxZ"] - 2:
                    continue
                if land and self.T and self.gh(px, pz) < 0.15:
                    continue
                if self.blocked(px, pz, r) or (round(px), round(pz)) not in reach:
                    continue
                if any(math.hypot(px - ox, pz - oz) < gap for ox, oz in others):
                    continue
                best = (round(px, 1), round(pz, 1))
                break
            if best:
                break
        if not best:
            raise RuntimeError("no free spot near %s,%s in %s" % (x, z, self.name))
        self.taken.append(best)
        return best

    def prop(self, model_hint, x, z, cond=None, scale=None):
        """A small visible prop on the ground: copies model path / y / scale from an existing piece whose model name contains the hint."""
        pcs = [p for p in self.d["pieces"] if model_hint in p[0]]
        if not pcs:
            return
        t = min(pcs, key=lambda p: (p[1] - x) ** 2 + (p[2] - z) ** 2)
        y = t[4] if len(t) > 4 else 0
        if self.T:
            y = round(self.gh(x, z) + (t[4] - self.gh(t[1], t[2]) if len(t) > 4 else 0), 3)
        piece = [t[0], x, z, round((x * 7.3 + z * 3.1) % 6.28, 2), y, scale or (t[5] if len(t) > 5 else 1)]
        if cond:
            piece.append(cond)
        self.d["pieces"].append(piece)

    def glow(self, x, z, showIf, color=(1, 0.85, 0.4, 0.6), r=1.8):
        self.d["decals"].append(dict(type="glow", x=x, z=z, r=r, color=list(color), showIf=showIf, sq=1))

    def add(self, key, obj):
        self.d[key].append(obj)

    def add_autorun(self, entry):
        entry = dict(entry); entry["sq"] = 1
        self.d.setdefault("autorun", []).append(entry)

    def save(self):
        with open(os.path.join(HERE, self.name + ".json"), "w", encoding="utf-8") as f:
            json.dump(self.d, f, ensure_ascii=False, separators=(",", ":"))


def strip_old_pieces(d):
    """Pieces we add are recorded in d['sqPieces'] as [model, x, z] keys so a re-run can remove exactly those."""
    keys = {tuple(k) for k in d.get("sqPieces", [])}
    if keys:
        d["pieces"] = [p for p in d["pieces"] if (p[0], p[1], p[2]) not in keys]
    d["sqPieces"] = []


# ======================================================================================================
# helpers shared by the quest definitions
# ======================================================================================================
def tint(r, g, b):
    return [r, g, b, 1]


def chest_event(sc, cid, x, z, loot, model, text="You open the chest and find"):
    """A hidden treasure chest: a visible prop that is swapped for an open one when its flag is set."""
    key = PREFIX + cid
    x, z = sc.spot(x, z, r=1.2)
    sc.add("events", event(cid, "Treasure chest", "Open the chest", x, z,
                           [flag(key), chest(loot, text)], w=3.4, d=3.4, hideIf=key))
    sc.d["pieces"].append(["/assets/3D/Generated/SM_TreasureChest", x, z, round((x * 7.3 + z * 3.1) % 6.28, 2), round(sc.gh(x, z), 3) if sc.T else 0, 1.0, key])   # new chest model, gone once opened
    return x, z


def pickup(sc, pid, name, prompt, x, z, need, text, model, glow_color=(1, 0.85, 0.4, 0.6), loot=None):
    """A quest item lying around: visible once the quest is accepted (`need`), gone once picked up (flag sq_<pid>)."""
    key = PREFIX + pid
    x, z = sc.spot(x, z, r=1.0)
    acts = [say("", text), flag(key)]
    if loot:
        acts.append(chest(loot, "You also find"))
    sc.add("events", event(pid, name, prompt, x, z, acts, w=3.2, d=3.2, showIf=need, hideIf=key))
    sc.prop(model, x, z, cond="H:" + key)                      # the prop disappears once picked up; the glow marks the live ones
    sc.glow(x, z, showIf=need + ",!" + key, color=glow_color)
    return x, z


def elite_npc(sc, eid, name, title, sprite, x, z, tint_, intro, pool, rel, strength, need=None, key=None, **cond):
    key = key or PREFIX + eid
    x, z = sc.spot(x, z, r=1.4, gap=3.5)
    n = npc(eid, name, title, sprite, x, z, tint_,
            actions=[say(name, t) for t in intro] + [battle(key, pool, rel, strength)], h=2.7, hideIf=key, reach=5.0, **cond)
    if need:
        n["showIf"] = need
    sc.add("npcs", n)
    return key, x, z


def dice_tables(sc, ax, az, who):
    for i, (nm, title, spr, stake, tt) in enumerate(who):
        x, z = sc.spot(ax + i * 2.6, az + i * 1.4, r=1.2, gap=2.4)
        lines = {
            50: "Two dice, high roll wins. Fifty gold a throw, friend.",
            100: "A hundred gold a throw, high roll takes the pot. Ties give your coin back.",
            250: "Two hundred fifty. The dice don't care how pretty your sword is.",
            400: "Four hundred a throw. Come to lose it, or come to win it.",
            1000: "A thousand. Not for the faint of purse.",
        }
        sc.add("npcs", npc("dice%d" % i, nm, title, spr, x, z, tt,
                           actions=[say(nm, lines[stake]), game("dice", stake)], reach=4.0))


# ======================================================================================================
# ISLAND  (the town between the forest and the Hollow Cave)
# ======================================================================================================
def island():
    sc = Scene("island"); d = sc.d; strip_old_pieces(d); n0 = len(d["pieces"])
    # --- Pua the fisher: "Lost Net" (the net is in the Whispering Wood) ---
    fisher = next(n for n in d["npcs"] if n["id"] == "fisher"); fisher["showIf"] = "sq_net_done"
    fx, fz, fh, ft = fisher["x"], fisher["z"], fisher["h"], fisher["tint"]
    base = dict(title="Fisher", sprite="Kenji", x=fx, z=fz, h=fh, tint=ft)
    pua = lambda i, acts, **c: dict(base, id=PREFIX + i, name="Pua", actions=acts, **c)
    sc.add("npcs", pua("pua0", [
        say("Pua", "Ah, a pair of strong arms! A storm took my best net two days ago, and the current swept it up the stream into the Whispering Wood."),
        say("Pua", "It is tangled somewhere by the water. I would go myself, but the goblins and I have... a history. Fetch it and I will make it worth your while."),
        flag("sq_net_q")], hideIf="sq_net_q"))
    sc.add("npcs", pua("pua1", [say("Pua", "My net should be snagged by the water somewhere in the Whispering Wood. Follow the stream, friend.")],
                      showIf="sq_net_q", hideIf="sq_net"))
    sc.add("npcs", pua("pua2", [
        say("Pua", "That is her! Not a single hole. You are a marvel!"),
        flag("sq_net_done"),
        chest(dict(gold=450, items=dict(potion=2), equipment=["ring_of_swift_feet"]), "Pua presses a reward into your hands")],
        showIf="sq_net", hideIf="sq_net_done"))
    # a fishing spot at the end of Pua's pier
    sc.add("events", event("fish1", "Fishing spot", "Drop a line", fx - 1.4, fz + 1.8,
                           [say("", "A weathered fishing pier juts out over the water."), game("fish", spot="pier", scene="fish_pier")], w=4, d=3))
    # --- Old Tane: goblin brute at the fence ---
    farmer = next(n for n in d["npcs"] if n["id"] == "farmer"); farmer["showIf"] = "sq_fence_done"
    tx, tz = farmer["x"], farmer["z"]
    tb = dict(title="Farmer", sprite="Draven", x=tx, z=tz, h=farmer["h"], tint=farmer["tint"])
    sc.add("npcs", dict(tb, id="sq_tane0", name="Old Tane", actions=[
        say("Old Tane", "Mind where you step! A great goblin brute has been smashing my fence every night. Chewed through two of my goats' fence posts and half a turnip row."),
        say("Old Tane", "He camps by the broken fence to the south, if you can call it a camp. Knock some sense into him and I'll make it worth your while."),
        flag("sq_fence_q")], hideIf="sq_fence_q"))
    sc.add("npcs", dict(tb, id="sq_tane1", name="Old Tane", actions=[say("Old Tane", "Brute's by my broken fence. Don't let him eat the goat.")],
                        showIf="sq_fence_q", hideIf="sq_fence"))
    sc.add("npcs", dict(tb, id="sq_tane2", name="Old Tane", actions=[
        say("Old Tane", "Gone! Quiet at last. Here, this is what the village keeps for its heroes."),
        flag("sq_fence_done"), chest(dict(gold=700, equipment=["war_hatchet"]), "Old Tane's thanks")],
        showIf="sq_fence", hideIf="sq_fence_done"))
    elite_npc(sc, "brute", "Goblin Brute", "Fence-smasher", "Draven", tx + 4, tz + 7, tint(0.55, 1.1, 0.55),
              ["You! You the one the old man sent? Ha! I'll break you like I broke his fence!"], ["goblin_skirmisher"], (2, 3), 1.0,
              need="sq_fence_q", key="sq_fence")
    # --- Scholar Nema: three moon-glyph pages (one here, two in the Whispering Wood) ---
    sch = next(n for n in d["npcs"] if n["id"] == "scholar"); sch["showIf"] = "sq_pg_done"
    nb = dict(title="Scholar", sprite="Miya", x=sch["x"], z=sch["z"], h=sch["h"], tint=sch["tint"])
    sc.add("npcs", dict(nb, id="sq_nema0", name="Scholar Nema", actions=[
        say("Scholar Nema", "I am cataloguing the moon-glyphs, the old script on the cave walls. Three torn pages from the first survey were scattered when the expedition fled."),
        say("Scholar Nema", "One blew down near the cave path. The other two are somewhere in the Whispering Wood. Bring them to me, please, and I will see you rewarded."),
        flag("sq_pg_q")], hideIf="sq_pg_q"))
    sc.add("npcs", dict(nb, id="sq_nema1", name="Scholar Nema", actions=[
        say("Scholar Nema", "Still missing pages. One near the cave path, two in the Whispering Wood.", unless="sq_pg1,sq_pg2,sq_pg3"),
        say("Scholar Nema", "All three! Look at the ligatures! This confirms everything. Please, take this with my thanks.", **{"if": "sq_pg1,sq_pg2,sq_pg3"}),
        chest(dict(shards=12, gems=6, items=dict(ether=2), equipment=["tome_of_mending"]), "Nema's reward", **{"if": "sq_pg1,sq_pg2,sq_pg3"}),
        flag("sq_pg_done", **{"if": "sq_pg1,sq_pg2,sq_pg3"})], showIf="sq_pg_q", hideIf="sq_pg_done"))
    pickup(sc, "pg1", "Torn page", "Pick up the page", 9.5, -30, "sq_pg_q",
           "A page of strange glyphs is pinned under a stone by the path. One of Nema's.", "Basket")
    # --- Dice at the harbour ---
    hm = next(n for n in d["npcs"] if n["id"] == "harbourmaster")
    dice_tables(sc, hm["x"] + 4.5, hm["z"] + 3.5, [
        ("Dockhand Jory", "Dice, 100g", "Kenji", 100, tint(1.1, 0.9, 0.8)),
        ("Big Lu", "High stakes, 400g", "Rook", 400, tint(1.2, 0.8, 0.8))])
    # --- Optional mini-boss: the cracked gargoyle on the east cliff, with a cache ---
    key, gx, gz = elite_npc(sc, "garg", "Cracked Gargoyle", "Stone sentinel", "Rook", 44, -6, tint(0.6, 0.6, 0.75),
                            ["The statue's eyes open. Grit pours from its jaw. 'INTRUDER.'"], ["stone_gargoyle"], (3, 4), 0.4)
    sc.add_autorun(dict({"if": "sq_garg", "unless": "sq_garg_r"}, actions=[
        say("", "The gargoyle crumbles to gravel. Behind its pedestal, a hollow holds a sealed cache."),
        flag("sq_garg_r"), chest(dict(gold=600, gems=5, tickets=dict(common=1)), "You find")]))
    # --- Hidden chests ---
    for cid, (x, z), loot in [("c1", (-47, -29), dict(gold=180, items=dict(potion=3))), ("c2", (47, -32), dict(gold=260, gems=3)),
                              ("c3", (38, 22), dict(gold=140, items=dict(antidote=3, potion=1))), ("c4", (-44, 8), dict(gold=320, shards=4))]:
        chest_event(sc, cid, x, z, loot, "SM_Stylized_Chest")
    record(sc, n0); sc.save()
    return sc


# ======================================================================================================
# FOREST (the Whispering Wood)
# ======================================================================================================
def forest():
    sc = Scene("forest"); d = sc.d; strip_old_pieces(d); n0 = len(d["pieces"])
    pickup(sc, "net", "Tangled net", "Pull the net free", 52, 12, "sq_net_q", "Pua's net, snagged on a root at the water's edge. Not a single tear.", "detail-crate-small")
    pickup(sc, "pg2", "Torn page", "Pick up the page", -58, 38, "sq_pg_q", "A glyph-covered page wedged in a hollow log. One of Nema's.", "detail-crate-small")
    pickup(sc, "pg3", "Torn page", "Pick up the page", -30, -22, "sq_pg_q", "Another torn page, nailed to a tree by a long-dead surveyor.", "detail-crate-small")
    elite_npc(sc, "alpha", "Alpha Spider", "Webbed hollow", "Miya", -20, 30, tint(0.5, 0.4, 0.75),
              ["A web as thick as rope drops across the trail, and something very large lowers itself in front of you."],
              ["venom_spider"], (2, 4), 1.0)
    sc.add_autorun(dict({"if": "sq_alpha", "unless": "sq_alpha_r"}, actions=[
        say("", "The Alpha thrashes once and goes still. Wrapped in its silk, a hunter's pack lies untouched."),
        flag("sq_alpha_r"), chest(dict(gold=420, equipment=["serrated_kris"], items=dict(hi_potion=1)), "In the pack")]))
    # a fishing hole by the ranger camp pool
    x, z = sc.spot(13, 0, r=1.0)
    sc.add("events", event("fish2", "Fishing hole", "Drop a line", x, z, [say("", "A quiet pool, perfect for a line."), game("fish", spot="pond", scene="fish_pond")]))
    for cid, (x, z), loot in [("c1", (-30, 36), dict(gold=150, items=dict(potion=2))), ("c2", (40, -30), dict(gold=300, shards=5, gems=2)),
                              ("c3", (-10, -30), dict(gold=210, items=dict(antidote=2, potion=2)))]:
        chest_event(sc, cid, x, z, loot, "detail-crate")
    # Mossbeard: a short lore chain, no fight
    herm = next(n for n in d["npcs"] if n["id"] == "hermit"); herm["showIf"] = "sq_moss_done"
    mb = dict(title="Forest hermit", sprite="Draven", x=herm["x"], z=herm["z"], h=herm["h"], tint=herm["tint"])
    sc.add("npcs", dict(mb, id="sq_moss0", name="Mossbeard", actions=[
        say("Mossbeard", "Hm? Travellers. Do me a kindness, if you pass the spring: drink, and tell me what it says to you."),
        say("Mossbeard", "The Oak is older than the island's name. It sings to the thorns. Lately somebody has been singing back."),
        flag("sq_moss_q")], hideIf="sq_moss_q"))
    sc.add("npcs", dict(mb, id="sq_moss1", name="Mossbeard", actions=[
        say("Mossbeard", "Have you been to the spring yet? It is just south of here. Drink, and listen.")], showIf="sq_moss_q", hideIf="sq_spring"))
    sc.add("npcs", dict(mb, id="sq_moss2", name="Mossbeard", actions=[
        say("Mossbeard", "Ah, you have the look of someone who has listened. The wood is generous to those who hear it."),
        flag("sq_moss_done"), chest(dict(gold=250, items=dict(ether=1, antidote=2)), "Mossbeard offers")], showIf="sq_spring", hideIf="sq_moss_done"))
    spring = next(e for e in d["events"] if e["id"] == "spirit_spring")
    if not any(a.get("key") == "sq_spring" for a in spring["actions"]):
        spring["actions"].append(flag("sq_spring", **{"if": "sq_moss_q"}))
    record(sc, n0); sc.save()
    return sc


# ======================================================================================================
# OUTSIDE (the town in front of the Colosseum)
# ======================================================================================================
def outside():
    sc = Scene("outside"); d = sc.d; strip_old_pieces(d); n0 = len(d["pieces"])
    tr = next(n for n in d["npcs"] if n["id"] == "traveler"); tr["showIf"] = "sq_locket_done"
    mb = dict(title="Traveller", sprite="Lyra", x=tr["x"], z=tr["z"], h=tr["h"], tint=tr["tint"])
    sc.add("npcs", dict(mb, id="sq_mara0", name="Mara", actions=[
        say("Mara", "Oh! Excuse me. I dropped my mother's locket somewhere on the road in from the harbour, and my escort is late again."),
        say("Mara", "It is silver, with a blue stone. If you find it, I would be so grateful."), flag("sq_locket_q")], hideIf="sq_locket_q"))
    sc.add("npcs", dict(mb, id="sq_mara1", name="Mara", actions=[say("Mara", "My locket... somewhere on the road in from the harbour, I think.")],
                        showIf="sq_locket_q", hideIf="sq_locket"))
    sc.add("npcs", dict(mb, id="sq_mara2", name="Mara", actions=[
        say("Mara", "That is it! Mother's locket. Take this, please. It is all I carry, but it is yours."),
        flag("sq_locket_done"), chest(dict(gold=350, items=dict(hi_potion=1, ether=1)), "Mara's gift")], showIf="sq_locket", hideIf="sq_locket_done"))
    pickup(sc, "locket", "Silver locket", "Pick up the locket", 4.5, 27, "sq_locket_q", "A silver locket with a blue stone, half buried in the road dust.", "basket_01")
    pip = next(n for n in d["npcs"] if n["id"] == "vendor"); pip["showIf"] = "sq_bounty_done"
    pb = dict(title="Fruit seller", sprite="Rook", x=pip["x"], z=pip["z"], h=pip["h"], tint=pip["tint"])
    sc.add("npcs", dict(pb, id="sq_pip0", name="Pip", actions=[
        say("Pip", "Psst. See the knight standing by the road? He was a Colosseum prisoner. Broke his chains and now he smashes my fruit stand every night."),
        say("Pip", "Teach him a lesson, and I'll pay you what the stand earns in a month."), flag("sq_bounty_q")], hideIf="sq_bounty_q"))
    sc.add("npcs", dict(pb, id="sq_pip1", name="Pip", actions=[say("Pip", "He lurks by the road to the harbour. Watch your back, he hits like a cart.")],
                        showIf="sq_bounty_q", hideIf="sq_bounty"))
    sc.add("npcs", dict(pb, id="sq_pip2", name="Pip", actions=[
        say("Pip", "You did it! Not one apple bruised! Here, you earned every coin."),
        flag("sq_bounty_done"), chest(dict(gold=900, equipment=["armor_medium_rare"]), "Pip's reward")], showIf="sq_bounty", hideIf="sq_bounty_done"))
    elite_npc(sc, "knight", "Escaped Knight", "Runaway prisoner", "Draven", -2, 22, tint(0.7, 0.6, 0.8),
              ["You'll not drag me back to the pit! I have nothing left to lose!"], ["cursed_knight"], (2, 3), 0.5, need="sq_bounty_q", key="sq_bounty")
    dice_tables(sc, 9, 19, [("Gambler Ro", "Dice, 100g", "Kenji", 100, tint(1.1, 0.9, 0.8)), ("Velvet Vee", "High stakes, 400g", "Yulia", 400, tint(1.2, 0.8, 1.0))])
    # a bounty board listing every open side quest in town and on the island
    st = lambda txt, a, b=None: say("Bounty Board", txt, **({"if": a} if not b else {"if": a, "unless": b}))
    sc.add("events", event("board", "Bounty board", "Read the bounties", -22, -6, [
        say("Bounty Board", "SIDE BOUNTIES (Paradise Island and the road):"),
        st("- Pua the fisher lost a net in the Whispering Wood.", "sq_net_q", "sq_net_done"),
        st("- Old Tane has a goblin brute smashing his fence.", "sq_fence_q", "sq_fence_done"),
        st("- Scholar Nema wants three glyph pages.", "sq_pg_q", "sq_pg_done"),
        st("- Mara lost a locket on the harbour road.", "sq_locket_q", "sq_locket_done"),
        st("- Pip wants the runaway knight dealt with.", "sq_bounty_q", "sq_bounty_done"),
    ], w=3.6, d=3.2))
    for cid, (x, z), loot in [("c1", (-17, 24), dict(gold=200, items=dict(potion=2))), ("c2", (17, 30), dict(gold=260, gems=2))]:
        chest_event(sc, cid, x, z, loot, "Apple_crate")
    record(sc, n0); sc.save()
    return sc


# ======================================================================================================
# ASTEROID (Outpost Kestrel, after the Vault)
# ======================================================================================================
def asteroid():
    sc = Scene("asteroid"); d = sc.d; strip_old_pieces(d); n0 = len(d["pieces"])
    x0, z0 = sc.spot(34, 24, r=1.2)
    sc.add("npcs", npc("vel0", "Scrapper Vel", "Salvager", "Yulia", x0, z0, tint(1.1, 1.0, 0.8), actions=[
        say("Scrapper Vel", "Three salvage crates broke loose from the cargo sled when the rift pulsed. Mostly spare parts, but one has medical stock. I'd go myself if my knee was not shot."),
        say("Scrapper Vel", "They'll be scattered around the pad. Bring me what you find and I'll share the haul."), flag("sq_salv_q")], hideIf="sq_salv_q"))
    sc.add("npcs", npc("vel1", "Scrapper Vel", "Salvager", "Yulia", x0, z0, tint(1.1, 1.0, 0.8), actions=[
        say("Scrapper Vel", "Still short. Three crates, scattered around the pad.", unless="sq_s1,sq_s2,sq_s3"),
        say("Scrapper Vel", "All three! The medical stock is intact. Here, your share, and then some.", **{"if": "sq_s1,sq_s2,sq_s3"}),
        chest(dict(gold=1200, items=dict(ether=3, hi_potion=2), equipment=["chorister_wand"]), "Vel's share", **{"if": "sq_s1,sq_s2,sq_s3"}),
        flag("sq_salv_done", **{"if": "sq_s1,sq_s2,sq_s3"})], showIf="sq_salv_q", hideIf="sq_salv_done"))
    sc.add("npcs", npc("vel2", "Scrapper Vel", "Salvager", "Yulia", x0, z0, tint(1.1, 1.0, 0.8),
                       line="Good haul, good friends. Come by any time the sled breaks again.", showIf="sq_salv_done"))
    for i, (x, z) in enumerate([(-40, 10), (24, -20), (44, 26)], 1):
        pickup(sc, "s%d" % i, "Salvage crate", "Search the crate", x, z, "sq_salv_q",
               "A cargo crate lies split open, packed with salvage tags and spare parts.", "crate_03", glow_color=(0.5, 0.8, 1, 0.7))
    # Sergeant Kade's drone sweep: an optional elite fight
    kx, kz = sc.spot(-9, 24, r=1.2)
    sc.add("npcs", npc("kade0", "Corporal Dun", "Patrol", "Draven", kx, kz, tint(0.9, 1.0, 1.15), actions=[
        say("Corporal Dun", "One of the patrol drones went rogue after the last pulse. It is camped out past the east scaffolding and it keeps shooting at the supply sleds."),
        say("Corporal Dun", "Shut it down, and the quartermaster's reserve is yours."), flag("sq_drone_q")], hideIf="sq_drone_q"))
    sc.add("npcs", npc("kade1", "Corporal Dun", "Patrol", "Draven", kx, kz, tint(0.9, 1.0, 1.15), actions=[say("Corporal Dun", "Past the east scaffolding. It pings every few seconds, so you'll hear it.")],
                       showIf="sq_drone_q", hideIf="sq_drone"))
    sc.add("npcs", npc("kade2", "Corporal Dun", "Patrol", "Draven", kx, kz, tint(0.9, 1.0, 1.15), actions=[
        say("Corporal Dun", "Quiet at last. The reserve's yours, as promised."),
        flag("sq_drone_done"), chest(dict(tickets=dict(premium=1), gems=8, gold=800, items=dict(phoenix_down=1)), "From the reserve")], showIf="sq_drone", hideIf="sq_drone_done"))
    elite_npc(sc, "drone", "Rogue Drone", "Malfunctioning", "Rook", 46, -14, tint(0.6, 0.9, 1.2),
              ["BZZT. TARGET ACQUIRED. TARGET ACQUIRED. TARGET ACQUIRED."], ["arc_drone"], (2, 3), 0.15, need="sq_drone_q", key="sq_drone")
    # An alpha phase hound out in the open
    elite_npc(sc, "hound", "Alpha Phase Hound", "Rift predator", "Miya", -44, -16, tint(0.6, 0.5, 1.2),
              ["The air folds in on itself. A great shape steps out of the fold, and it does not look hungry. It looks curious."],
              ["phase_hound"], (0, 1), 0.05)
    sc.add_autorun(dict({"if": "sq_hound", "unless": "sq_hound_r"}, actions=[
        say("", "The hound dissolves into a spray of motes. Where it stood, a polished shard hums softly."),
        flag("sq_hound_r"), chest(dict(gold=1000, gems=6, shards=15, equipment=["gilded_hymnal"]), "You find")]))
    dice_tables(sc, -20, -22, [("Doc Ferro", "Dice, 250g", "Lyra", 250, tint(0.9, 1.1, 1.0)), ("Quartermaster's mate", "High stakes, 1000g", "Rook", 1000, tint(1.2, 0.9, 0.7))])
    cx, cz = sc.spot(-36, -22, r=1.2)
    sc.add("events", event("fix", "Repair bench", "Rest", cx, cz, [say("", "You sit on the workbench for a few minutes while the hum of the pad evens out your breathing."), dict(type="rest")], w=3.4))
    for cid, (x, z), loot in [("c1", (-48, 30), dict(gold=500, items=dict(hi_potion=1, ether=1))), ("c2", (50, 4), dict(gold=700, shards=8, gems=3))]:
        chest_event(sc, cid, x, z, loot, "crate_01")
    record(sc, n0); sc.save()
    return sc


SIDE = [
    ("sq_net_q", "sq_net", "Pua (island pier): find his lost fishing net in the Whispering Wood", None),
    ("sq_net", "sq_net_done", "Pua: bring the net back", None),
    ("sq_fence_q", "sq_fence", "Old Tane (island farm): beat the goblin brute by his fence", None),
    ("sq_fence", "sq_fence_done", "Old Tane: collect your reward", None),
    ("sq_pg_q", "sq_pg_done", "Scholar Nema (island): find the torn glyph pages (cave path, Whispering Wood)", ["sq_pg1", "sq_pg2", "sq_pg3"]),
    ("sq_moss_q", "sq_spring", "Mossbeard (Whispering Wood): drink from the spirit spring", None),
    ("sq_spring", "sq_moss_done", "Mossbeard: tell him what you heard", None),
    ("sq_locket_q", "sq_locket", "Mara (Colosseum town): find her locket on the harbour road", None),
    ("sq_locket", "sq_locket_done", "Mara: return the locket", None),
    ("sq_bounty_q", "sq_bounty", "Pip (Colosseum town): defeat the runaway knight on the road", None),
    ("sq_bounty", "sq_bounty_done", "Pip: collect your reward", None),
    ("sq_salv_q", "sq_salv_done", "Scrapper Vel (Outpost Kestrel): recover the loose salvage crates", ["sq_s1", "sq_s2", "sq_s3"]),
    ("sq_drone_q", "sq_drone", "Corporal Dun (Outpost Kestrel): shut down the rogue drone past the east scaffolding", None),
    ("sq_drone", "sq_drone_done", "Corporal Dun: collect the reserve", None),
]


def write_side():
    out = []
    for need, until, text, count in SIDE:
        q = {"if": need, "unless": until, "text": text}
        if count:
            q["count"] = count
        out.append(q)
    with open(os.path.join(HERE, "sidequests.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


def record(sc, n0):
    """Remember the pieces this run added, so the next run can remove exactly those."""
    sc.d["sqPieces"] = [[p[0], p[1], p[2]] for p in sc.d["pieces"][n0:]]


# ======================================================================================================
# THE DUNGEONS (Hollow Cave, Shard Vault, Shattered Reach): optional elites, extra chests, lore. Everything is placed near
# known-good spots (existing chests / zones) and must be reachable from the spawn.
# ======================================================================================================
def lore(sc, lid, name, who, text, x, z, model="SM_dg_tablet", prompt="Read the tablet"):
    x, z = sc.spot(x, z, r=1.2, gap=4.0)
    sc.add("events", event(lid, name, prompt, x, z, [say(who, t) for t in (text if isinstance(text, list) else [text])], w=3.4, d=2.6))
    sc.prop(model, x, z)


def dungeon_elite(sc, eid, name, title, sprite, ax, az, tint_, intro, pool, rel, strength, after, loot, lead="You find"):
    key, x, z = elite_npc(sc, eid, name, title, sprite, ax, az, tint_, intro, pool, rel, strength)
    sc.add_autorun(dict({"if": key, "unless": key + "_r"}, actions=[say("", t) for t in after] + [flag(key + "_r"), chest(loot, lead)]))
    return x, z


def _cave_layout():
    """make_cave.py writes dungeon_layout.json (room centres + tunnel centre lines) so the cave extras follow the winding layout."""
    p = os.path.join(HERE, "dungeon_layout.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def dungeon():
    sc = Scene("dungeon"); d = sc.d; strip_old_pieces(d); n0 = len(d["pieces"])
    L = _cave_layout()

    def room(n, dx, dz, old):
        return (round(L["rooms"][n][0] + dx, 1), round(L["rooms"][n][1] + dz, 1)) if L else old

    def tun(n, f, old):
        if not L:
            return old
        pts = L["tunnels"][n]; q = pts[max(0, min(len(pts) - 1, int(f * (len(pts) - 1))))]
        return (q[0], q[1])
    wx, wz = room("RW", 4, 2, (-80, -215)); zx, zz = room("ME", -4, 4, (70, -420))
    c1 = tun("t_K1_GA", .3, (40, -100)); c2 = room("CV", -16, 8, (-40, -300)); c3 = room("SH", 18, 0, (55, -520))
    l1 = tun("t_GA_GR", .5, (-30, -160)); l2 = tun("t_CV_K2", .1, (30, -350)); l3 = room("CR", 0, 30, (0, -560))
    dungeon_elite(sc, "wraith", "Lantern Wraith", "Drowned guide", "Lyra", wx, wz, tint(0.6, 0.8, 1.2),
                  ["A pale lantern drifts out of the dark, swaying. The face behind it is a drowned sailor's.", "'The king keeps no guests. Only company.'"],
                  ["frost_wraith"], (1, 2), 1.0,
                  ["The lantern gutters and drops into the water. In the silt beneath it, something glints."],
                  dict(gold=450, gems=4, equipment=["chapel_mace"]))
    dungeon_elite(sc, "zealot", "Crypt Zealot", "Last of the court", "Draven", zx, zz, tint(0.7, 0.55, 0.85),
                  ["A robed figure is kneeling in the dust, whispering the king's name over and over. He rises, slowly, as you approach."],
                  ["dark_cultist"], (1, 2), 1.0,
                  ["The zealot dissolves into ash. His offering bowl, still full, rolls to a stop at your feet."],
                  dict(gold=550, shards=8, items=dict(ether=1, hi_potion=1)))
    for cid, (x, z), loot in [("c1", c1, dict(gold=300, items=dict(potion=2))), ("c2", c2, dict(gold=380, shards=4)),
                              ("c3", c3, dict(gold=480, gems=3, items=dict(antidote=2)))]:
        chest_event(sc, "dg" + cid, x, z, loot, "detail-crate")
    lore(sc, "lore1", "Weathered tablet", "Tablet", "'WE SANK THE KING BENEATH THE TIDE, AND THE TIDE REMEMBERED. LET NO ONE WAKE HIS COURT.'", l1[0], l1[1])
    lore(sc, "lore2", "Cracked tablet", "Tablet", ["'HE WAS A GOOD KING, ONCE. THE SEA ASKED FOR A PRICE, AND HE PAID IT WITH HIS PEOPLE.'", "'THE BELL IN THE EASTERN HALL RINGS ON ITS OWN. DO NOT ANSWER IT.'"], l2[0], l2[1])
    lore(sc, "lore3", "Salt-eaten tablet", "Tablet", "'WHOEVER FINDS THIS: THE LANTERN-BEARERS WERE HIS KEEPERS. THEY ARE BOUND TO THE LAST LIGHT. PUT THE LIGHT OUT AND THEY REST.'", l3[0], l3[1])
    record(sc, n0); sc.save()
    return sc


def vault():
    sc = Scene("vault"); d = sc.d; strip_old_pieces(d); n0 = len(d["pieces"])
    dungeon_elite(sc, "medic", "Rogue Medic Unit", "Maintenance loop", "Lyra", -120, -45, tint(0.6, 1.1, 0.9),
                  ["A lattice unit unfolds from a wall niche, its repair arms humming. 'PATIENT DETECTED. PREPARING... TREATMENT.'"],
                  ["lattice_medic"], (1, 2), 0.8,
                  ["The unit sparks and goes dark. Its supply drawer pops open."],
                  dict(gold=900, items=dict(hi_potion=2), equipment=["wardens_tower_shield"]))
    dungeon_elite(sc, "leech", "Leech Mother", "Starved", "Miya", 120, -20, tint(0.8, 0.5, 1.0),
                  ["The floor ripples. A swollen leech the size of a cart slides up out of a drain, tasting the air."],
                  ["rift_leech"], (1, 2), 0.7,
                  ["The leech collapses in on itself. Something hard is lodged in what is left of it."],
                  dict(gold=800, shards=12, gems=5))
    for cid, (x, z), loot in [("c1", (-130, 40), dict(gold=700, items=dict(hi_potion=1, ether=1))), ("c2", (160, -10), dict(gold=900, shards=8)),
                              ("c3", (0, -90), dict(gold=1100, gems=4, items=dict(ether=2)))]:
        chest_event(sc, "vt" + cid, x, z, loot, "detail-crate")
    lore(sc, "lore1", "Survey log", "Survey log", ["'DAY 14. THE VAULT PLAYS BACK EVERYTHING WE SAY, IN OUR OWN VOICES, A FEW SECONDS LATE.'", "'DAY 15. NOBODY ANSWERED THE ROLL CALL BUT THE ECHO.'"], -120, 20, prompt="Read the log")
    lore(sc, "lore2", "Cracked lens", "Cracked lens", "'This was a window onto somewhere else. It shows you where you came from, and who is still looking.'", 100, 5)
    lore(sc, "lore3", "Bent plate", "Etched Plate", "'THE WARDEN WAS BUILT TO KEEP THINGS IN. IT HAS NEVER BEEN TOLD THAT SOMETHING LET THEM OUT.'", -10, -110)
    record(sc, n0); sc.save()
    return sc


def reach():
    sc = Scene("reach"); d = sc.d; strip_old_pieces(d); n0 = len(d["pieces"])
    dungeon_elite(sc, "mirage", "Mirror of the Reach", "Hollow reflection", "Kenji", -25, -80, tint(0.7, 0.9, 1.3),
                  ["A figure steps out of a seam in the air wearing your own stance. Its face is a smear of light."],
                  ["frost_mirage"], (1, 3), 0.2,
                  ["The reflection shatters into drifting glass, and one pane lands upright, humming."],
                  dict(gold=1500, items=dict(ether=2), equipment=["emberwood_staff"]))
    dungeon_elite(sc, "acolyte", "Rift Penitent", "Kneeling", "Rook", 20, -175, tint(0.8, 0.5, 1.2),
                  ["A cloaked figure kneels at the edge, facing the void. 'Do you hear it? It is not angry. It is only hungry.'"],
                  ["void_acolyte"], (1, 3), 0.2,
                  ["The penitent folds into a pile of cloth. A pouch of shards is tied to its belt."],
                  dict(gold=1400, shards=20, gems=8, tickets=dict(premium=1)))
    for cid, (x, z), loot in [("c1", (30, -75), dict(gold=900, items=dict(hi_potion=2))), ("c2", (30, -170), dict(gold=1200, shards=10)),
                              ("c3", (-30, -190), dict(gold=1500, gems=5, items=dict(ether=2))), ("c4", (-30, -250), dict(gold=1600, shards=12, items=dict(phoenix_down=1)))]:
        chest_event(sc, "rc" + cid, x, z, loot, "detail-crate")
    lore(sc, "lore1", "Drifting plate", "Etched Plate", "'THE SKY BROKE FIRST. THE GROUND ONLY FOLLOWED.'", 20, -15)
    lore(sc, "lore2", "Fallen plate", "Etched Plate", "'EVERY ISLET HERE WAS A ROOM IN A HOUSE. SOMEONE LEFT THE DOOR OPEN ON PURPOSE.'", -30, -100)
    lore(sc, "lore3", "Warm plate", "Etched Plate", "'THE LAST WARDEN IS NOT A MONSTER. IT IS A LOCK, AND LOCKS DO NOT HATE. THEY ONLY HOLD.'", 15, -285)
    record(sc, n0); sc.save()
    return sc


if __name__ == "__main__":
    which = sys.argv[1:] or ["island", "forest", "outside", "asteroid", "dungeon", "vault", "reach"]
    for w in which:
        sc = globals()[w]()
        write_side()
        print("%-9s +%d npcs? total npcs=%d events=%d decals=%d pieces=%d (removed %d old)" % (
            w, sum(1 for n in sc.d["npcs"] if n["id"].startswith(PREFIX)), len(sc.d["npcs"]), len(sc.d["events"]), len(sc.d["decals"]), len(sc.d["pieces"]), sc.removed))

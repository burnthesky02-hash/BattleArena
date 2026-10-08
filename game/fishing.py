"""Fishing mini-game rules: casting, what bites, landing a catch, the fish log, and buying rods / bait.

Plain functions over PlayerState (like game/shop.py), so they can be tested without the server. The 3D scene and the
cast -> bite -> reel-fight mechanic live in html_hub/3d/fishing.js; this module is the authority on the *results*:

  view(ps, spot)            everything the client needs to draw the HUD, tackle shop and fish log
  cast(ps, spot, dist)      spends a cast (and a bait), rolls what is on the line, returns a one-time ticket
  result(ps, ticket, outcome)  "landed" pays out and updates the log; "lost" just closes the ticket
  buy(ps, spot, kind, id)   rods and bait packs;  equip(ps, kind, id) picks the rod / bait in use

Persistent state is `ps.fishing` (a plain dict, saved by game/save_system.py):
  {rod, rods[], bait, baits{id: count}, log{species: {count, best, first}}, sets[spots completed], casts, landed}
"""
import random
import time
import uuid
from typing import Dict, Optional

from data import fishing_db as DB

_bucket = {"tokens": DB.CAST_BUCKET_MAX, "t": None}          # casts left (in memory only; a restart refills it)
_tickets: Dict[str, dict] = {}                                 # outstanding casts: ticket -> {...}


def fstate(ps) -> dict:
    """ps.fishing, filled out with defaults (older saves have none of it)."""
    f = getattr(ps, "fishing", None)
    if not isinstance(f, dict):
        f = {}
    f.setdefault("rod", "driftwood")
    rods = [r for r in f.get("rods", []) if r in DB.RODS]
    if "driftwood" not in rods:
        rods.insert(0, "driftwood")
    f["rods"] = rods
    if f["rod"] not in rods:
        f["rod"] = "driftwood"
    f["baits"] = {k: int(v) for k, v in (f.get("baits") or {}).items() if k in DB.BAITS and k != "none" and int(v) > 0}
    if f.get("bait") not in DB.BAITS or (f.get("bait") != "none" and f["baits"].get(f.get("bait"), 0) <= 0):
        f["bait"] = "none"
    f["log"] = {k: dict(count=int(v.get("count", 0)), best=float(v.get("best", 0)), first=v.get("first", 0))
                for k, v in (f.get("log") or {}).items() if k in DB.SPECIES_BY_ID and isinstance(v, dict) and int(v.get("count", 0)) > 0}
    f["sets"] = [s for s in f.get("sets", []) if s in DB.SPOTS]
    f["casts"] = int(f.get("casts", 0)); f["landed"] = int(f.get("landed", 0))
    ps.fishing = f
    return f


# ---- the cast bucket ----------------------------------------------------------------------------------------------
def _refill(now: float) -> float:
    if _bucket["t"] is None:
        _bucket["t"] = now
    _bucket["tokens"] = min(DB.CAST_BUCKET_MAX, _bucket["tokens"] + (now - _bucket["t"]) / DB.CAST_REGEN_SECONDS)
    _bucket["t"] = now
    return _bucket["tokens"]


def casts_left(now: Optional[float] = None) -> dict:
    t = _refill(now if now is not None else time.time())
    nxt = 0.0 if t >= DB.CAST_BUCKET_MAX else (1 - (t - int(t))) * DB.CAST_REGEN_SECONDS
    return {"left": int(t), "max": int(DB.CAST_BUCKET_MAX), "next": round(nxt, 1)}


def refill_casts() -> None:
    _bucket["tokens"] = DB.CAST_BUCKET_MAX; _bucket["t"] = None


# ---- view ---------------------------------------------------------------------------------------------------------
def zone_for(dist: float) -> str:
    return "near" if dist < DB.ZONE_EDGES[0] else ("mid" if dist < DB.ZONE_EDGES[1] else "far")


def _rod_out(r: dict, owned: bool, equipped: bool) -> dict:
    return dict(r, owned=owned, equipped=equipped)


def view(ps, spot: str) -> dict:
    f = fstate(ps)
    sp = DB.SPOTS.get(spot) or DB.SPOTS["pier"]
    species = []
    for s in DB.SPECIES:
        if s["spot"] != spot:
            continue
        rec = f["log"].get(s["id"])
        d = dict(id=s["id"], zone=s["zone"], rarity=s["rarity"], color=s["color"], caught=bool(rec))
        if rec:
            d.update(name=s["name"], note=s["note"], count=rec["count"], best=round(rec["best"], 2), kg=list(s["kg"]))
        else:
            d.update(name="???", note="Not caught yet.", count=0, best=0, kg=None)
        species.append(d)
    rod = DB.RODS[f["rod"]]
    return dict(
        ok=True, spot=spot, spotName=sp["name"], seller=sp["seller"], money=ps.money, gems=ps.gems,
        casts=casts_left(), rod=dict(rod), bait=f["bait"], baitName=DB.BAITS[f["bait"]]["name"], baits=dict(f["baits"]),
        rods=[_rod_out(DB.RODS[r], r in f["rods"], r == f["rod"]) for r in DB.ROD_ORDER if r in DB.RODS and (r in f["rods"] or r in sp["rods"])],
        baitShop=[dict(DB.BAITS[b], have=f["baits"].get(b, 0)) for b in sp["baits"]],
        species=species, caughtCount=sum(1 for s in species if s["caught"]), total=len(species),
        setDone=spot in f["sets"], landed=f["landed"], zones=dict(edges=list(DB.ZONE_EDGES), min=DB.CAST_MIN))


# ---- casting ------------------------------------------------------------------------------------------------------
def _pick_species(spot: str, zone: str, rod: dict, bait: dict, rng) -> dict:
    luck = rod["luck"] + bait["luck"]
    pool, weights = [], []
    for s in DB.SPECIES:
        if s["spot"] != spot or s["zone"] != zone:
            continue
        w = DB.RARITY_WEIGHT[s["rarity"]] * (1 + luck * DB.RARITY_LUCK[s["rarity"]])
        aff = 1.0                                              # boosts (> 1) take the best matching tag; a put-off (< 1) the worst
        for tag, m in bait["affinity"].items():
            if tag in s["tags"]:
                aff = max(aff, m) if m >= 1 and aff >= 1 else min(aff, m)
        pool.append(s); weights.append(w * aff)
    return rng.choices(pool, weights=weights, k=1)[0]


def _size_roll(s: dict, rng, luck: float):
    u = rng.random() ** 1.7                                   # most fish are on the small side
    u = min(1.0, u + luck * 0.12 * rng.random())
    kg = round(s["kg"][0] + (s["kg"][1] - s["kg"][0]) * u, 2)
    for hi, name, mult in DB.SIZE_CLASSES:
        if u < hi:
            return kg, name, mult


def cast(ps, spot: str, dist: float, rng=random, now: Optional[float] = None) -> dict:
    now = now if now is not None else time.time()
    f = fstate(ps)
    if spot not in DB.SPOTS:
        return dict(ok=False, message="There is nothing to fish here.")
    rod = DB.RODS[f["rod"]]
    try:
        dist = float(dist)
    except (TypeError, ValueError):
        dist = DB.CAST_MIN
    dist = max(DB.CAST_MIN, min(rod["reach"], dist))
    if _refill(now) < 1:
        return dict(ok=False, message="The fish have stopped biting for now. Give the water a minute.", casts=casts_left(now))
    _bucket["tokens"] -= 1
    f["casts"] += 1
    bait_id = f["bait"]
    note = ""
    if bait_id != "none":
        f["baits"][bait_id] -= 1
        if f["baits"][bait_id] <= 0:
            del f["baits"][bait_id]; f["bait"] = "none"; note = f"That was your last {DB.BAITS[bait_id]['name']}."
    bait = DB.BAITS[bait_id]
    zone = zone_for(dist)
    roll = rng.random()
    if roll < DB.TREASURE_CHANCE:
        t = rng.choices(DB.TREASURE, weights=[x["w"] for x in DB.TREASURE], k=1)[0]
        what = dict(kind="treasure", name=t["name"], kg=0, size="", rarity="uncommon", fight=0.25, color="#d9a441", sid=None, treasure=t["name"])
    elif roll < DB.TREASURE_CHANCE + DB.JUNK_CHANCE:
        j = rng.choice(DB.JUNK)
        what = dict(kind="junk", name=j[0], kg=0, size="", rarity="common", fight=j[2], color="#6f7a5a", sid=None, junk=j[1])
    else:
        s = _pick_species(spot, zone, rod, bait, rng)
        kg, size, mult = _size_roll(s, rng, rod["luck"] + bait["luck"])
        what = dict(kind="fish", name=s["name"], kg=kg, size=size, rarity=s["rarity"], fight=s["fight"], color=s["color"], sid=s["id"], mult=mult)
    ticket = uuid.uuid4().hex
    delay = round(rng.uniform(2.5, 8.0) * bait["wait"], 2)
    _tickets.clear()                                            # one line in the water at a time
    _tickets[ticket] = dict(spot=spot, what=what, t0=now, delay=delay, zone=zone, dist=dist)
    return dict(ok=True, ticket=ticket, zone=zone, dist=round(dist, 1), delay=delay, window=rod["window"], note=note,
                catch=dict(kind=what["kind"], kg=what["kg"], fight=what["fight"], color=what["color"], rarity=what["rarity"]),
                casts=casts_left(now), bait=f["bait"], baits=dict(f["baits"]))


def result(ps, ticket: str, outcome: str, now: Optional[float] = None) -> dict:
    now = now if now is not None else time.time()
    t = _tickets.pop(ticket, None)
    if not t:
        return dict(ok=False, landed=False, message="That line is already gone.")
    if outcome != "landed":
        return dict(ok=True, landed=False)
    if now - t["t0"] < t["delay"] + 1.0:
        return dict(ok=False, landed=False, message="The fish slips off the hook.")
    f = fstate(ps)
    w = t["what"]
    out = dict(ok=True, landed=True, kind=w["kind"], name=w["name"], kg=w["kg"], size=w["size"], rarity=w["rarity"], color=w["color"],
               value=0, bonus=0, newSpecies=False, record=False, setBonus=0, text="", items={})
    if w["kind"] == "fish":
        s = DB.SPECIES_BY_ID[w["sid"]]
        value = max(1, int(round(w["kg"] * s["rate"] * w["mult"])))
        out["value"] = value; ps.money += value
        rec = f["log"].get(s["id"])
        if not rec:
            rec = f["log"][s["id"]] = dict(count=0, best=0.0, first=int(now))
            out["newSpecies"] = True
            out["bonus"] = DB.FIRST_CATCH_BONUS[s["rarity"]]; ps.money += out["bonus"]
        rec["count"] += 1
        if w["kg"] > rec["best"]:
            out["record"] = rec["count"] > 1
            rec["best"] = w["kg"]
        f["landed"] += 1
        mine = [x["id"] for x in DB.SPECIES if x["spot"] == t["spot"]]
        if t["spot"] not in f["sets"] and all(i in f["log"] for i in mine):
            f["sets"].append(t["spot"]); out["setBonus"] = DB.SET_BONUS_GEMS; ps.gems += DB.SET_BONUS_GEMS
        out["text"] = s["note"]
    elif w["kind"] == "junk":
        out["value"] = w["junk"]; ps.money += w["junk"]; out["text"] = "Better than nothing. Barely."
    else:
        tr = next(x for x in DB.TREASURE if x["name"] == w["treasure"])
        g = tr["give"]
        for k, n in (g.get("inventory") or {}).items():
            ps.inventory[k] = ps.inventory.get(k, 0) + n; out["items"][k] = n
        if g.get("gems"):
            ps.gems += g["gems"]; out["gems"] = g["gems"]
        if g.get("money"):
            ps.money += g["money"]; out["value"] = g["money"]
        out["text"] = tr["text"]
    out["money"] = ps.money; out["gems"] = ps.gems
    return out


# ---- tackle -------------------------------------------------------------------------------------------------------
def buy(ps, spot: str, kind: str, item: str, packs: int = 1) -> dict:
    f = fstate(ps)
    sp = DB.SPOTS.get(spot)
    if not sp:
        return dict(ok=False, message="No tackle seller here.")
    if kind == "rod":
        r = DB.RODS.get(item)
        if not r or item not in sp["rods"]:
            return dict(ok=False, message="The seller doesn't stock that.")
        if item in f["rods"]:
            return dict(ok=False, message=f"You already own the {r['name']}.")
        if ps.money < r["cost"]:
            return dict(ok=False, message=f"Not enough gold for the {r['name']} (need {r['cost']}).")
        ps.money -= r["cost"]; f["rods"].append(item)
        if DB.ROD_ORDER.index(item) > DB.ROD_ORDER.index(f["rod"]):
            f["rod"] = item
        return dict(ok=True, message=f"Bought the {r['name']} for {r['cost']} gold and picked it up.")
    if kind == "bait":
        b = DB.BAITS.get(item)
        if not b or item == "none" or item not in sp["baits"]:
            return dict(ok=False, message="The seller doesn't stock that.")
        packs = max(1, min(5, int(packs or 1)))
        have = f["baits"].get(item, 0)
        if have >= 99:
            return dict(ok=False, message="You can't carry any more of that.")
        cost = b["cost"] * packs
        if ps.money < cost:
            return dict(ok=False, message=f"Not enough gold ({cost} needed).")
        ps.money -= cost; f["baits"][item] = min(99, have + b["pack"] * packs)
        if f["bait"] == "none":
            f["bait"] = item
        return dict(ok=True, message=f"Bought {b['pack'] * packs} x {b['name']} for {cost} gold.")
    return dict(ok=False, message="Unknown purchase.")


def equip(ps, kind: str, item: str) -> dict:
    f = fstate(ps)
    if kind == "rod":
        if item not in f["rods"]:
            return dict(ok=False, message="You don't own that rod.")
        f["rod"] = item; return dict(ok=True, message=f"Equipped the {DB.RODS[item]['name']}.")
    if kind == "bait":
        if item != "none" and f["baits"].get(item, 0) <= 0:
            return dict(ok=False, message="You have none of that.")
        f["bait"] = item; return dict(ok=True, message=f"Using {DB.BAITS[item]['name']}.")
    return dict(ok=False, message="Unknown choice.")

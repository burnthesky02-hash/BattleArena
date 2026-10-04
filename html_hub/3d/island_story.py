"""The island's chapter-1 story chain after the forest quest (restored after the stylized rebuild dropped it):
fq_done -> Elder Mahina tells of Lani (st_quest) -> Hollow Cave (dungeon.json sets st_found) -> smoke over the village (st_attack)
-> three raider fights in the plaza (st_a1..a3) -> the portal to the Colosseum's Pit (st_done).  Used by make_island.py and by the one-off patch of island.json."""
import copy

def say(who, text): return dict(type="say", who=who, text=text)

DARK = [0.55, 0.45, 0.7, 1]

def npcs(elder):
    e0 = dict(elder); e0["hideIf"] = "fq_done"
    base = {k: elder[k] for k in ("name", "title", "sprite", "x", "z", "h", "tint")}
    e1 = dict(base, id="elder1", showIf="fq_done", hideIf="st_quest", actions=[
        say("Elder Mahina", "So the Seal is home and the gate is open. You have done the island a great service, traveller."),
        say("Elder Mahina", "There is one more thing. Young Lani slipped into the Hollow Cave three days ago, before the council sealed it, to gather moonglow moss. She has not come back."),
        say("Elder Mahina", "The cave runs deep: at its end lies the crypt of the old drowned king, and his court still keeps it. Please. Bring her home."),
        dict(type="flag", key="st_quest")])
    e2 = dict(base, id="elder2", showIf="st_quest", hideIf="st_found", actions=[
        say("Elder Mahina", "The Hollow Cave is north of the village, past the old ruins. Lani is not foolish, only stubborn. Please hurry.")])
    e3 = dict(base, id="elder3", showIf="st_found", hideIf="st_done", actions=[
        say("Elder Mahina", "Lani is safe, but those masked men are in my village! Stop them, I beg you!")])
    raid = lambda i, nm, x, z, sprite, sh, hi, key, pool, lvl, lines: dict(
        id=i, name=nm, title="Raider", sprite=sprite, x=x, z=z, h=2.4, tint=DARK, showIf=sh, hideIf=hi, reach=5.0,
        actions=[say(nm, t) for t in lines] + [dict(type="battle", key=key, pool=pool, level=lvl)])
    r1 = raid("raid1", "Masked Raider", -7.0, 6.0, "Draven", "st_attack", "st_a1", "st_a1", ["dark_cultist", "cursed_knight", "bandit_rogue"], [5, 7],
              ["Fresh meat! The boss said someone would crawl out of that hole.", "Take the stranger, take the village, take it all!"])
    r2 = raid("raid2", "Masked Raider", 7.0, 6.0, "Kael", "st_a1", "st_a2", "st_a2", ["dark_cultist", "cursed_knight", "bandit_rogue"], [5, 7],
              ["You cut down my brother? Then you will not leave this square alive!"])
    r3 = raid("raid3", "Hooded Leader", 0.0, 7.5, "Rook", "st_a2", "st_a3", "st_a3", ["dark_cultist", "cursed_knight", "abyssal_horror"], [6, 7],
              ["Enough. You are stronger than you look. Good. The gate will need a strong key."])
    r3["title"] = "Raid leader"
    lani = dict(id="lani_home", name="Lani", title="Villager", sprite="Sera", x=-8.5, z=3.0, h=2.2, tint=[1.25, 0.95, 1.1, 1], showIf="st_found", hideIf="st_done", actions=[
        say("Lani", "I slipped out through the side tunnel. Thank you for facing the king for me!"),
        say("Lani", "Those masks came out of the sea fog. Please, protect the village!")])
    return e0, [e1, e2, e3, r1, r2, r3, lani]

AUTORUN = [
    dict({"if": "st_a3", "unless": "st_done"}, actions=[
        say("", "The Hooded Leader falls to one knee, laughing under the mask."),
        say("Hooded Leader", "It is done. The gate is open, and you are the key."),
        say("", "The air above the square tears like cloth. A whirl of violet light drags at your feet..."),
        dict(type="flash"), dict(type="flag", key="st_done"), dict(type="warp", scene="prison", x=0, z=-3.6)]),
    dict({"if": "st_found", "unless": "st_attack"}, actions=[
        say("", "You climb out into the daylight. Black smoke is rising over the village!"),
        say("", "Shouts and the clash of steel carry on the wind. Hurry back to the square!"),
        dict(type="flag", key="st_attack")]),
]

OBJ = [dict({"if": "fq_done", "unless": "st_quest"}, text="Speak with Elder Mahina in the village"),
       dict({"if": "st_quest", "unless": "dg_boss"}, text="Find Lani in the Hollow Cave north of the village")]

def apply(d):
    """idempotent: patches a built island scene dict in place"""
    if any(n.get("id") == "elder1" for n in d["npcs"]): return d
    i = next(k for k, n in enumerate(d["npcs"]) if n.get("id") == "elder")
    e0, extra = npcs(d["npcs"][i]); d["npcs"][i] = e0; d["npcs"] += extra
    obj = d.setdefault("objectives", [])
    j = next((k for k, o in enumerate(obj) if o.get("text", "").startswith("Enter the Hollow Cave")), len(obj))
    obj[j:j] = copy.deepcopy(OBJ)
    d["autorun"] = copy.deepcopy(AUTORUN) + list(d.get("autorun") or [])
    d["story"] = True
    return d

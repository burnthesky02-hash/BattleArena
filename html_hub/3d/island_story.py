"""The island's chapter-1 story chain after the forest quest (v2, Oct 6):
fq_done -> Elder Mahina asks you to escort a traveller through the Hollow Cave (st_quest) -> talk to Sera at the cave arch, she joins
(recruit, st_sera) -> the cave (dungeon.json / cave_story.py): the party meets Colosseum guards losing to the Drowned Sovereign, wins, is knocked out
and carried to the Colosseum's Pit while Sera goes to the infirmary (st_done, prison). Replaces the old Lani rescue + village raid + portal.
Used by make_island.py (which calls apply) and by the one-off patch of island.json. apply() is idempotent and also removes the v1 entries."""
import copy

def say(who, text, **cond): return dict(type="say", who=who, text=text, **cond)

OLD_IDS = {"elder3", "raid1", "raid2", "raid3", "lani_home"}

def npcs(elder):
    base = {k: elder[k] for k in ("name", "title", "sprite", "x", "z", "h", "tint")}
    e0 = dict(elder); e0["hideIf"] = "fq_done"
    e1 = dict(base, id="elder1", showIf="fq_done", hideIf="st_quest", actions=[
        say("Elder Mahina", "So the Seal is home and the gate is open. You have done the island a great service, traveller."),
        say("Elder Mahina", "There is one more favour I would ask. A young healer came off the morning boat: Sera, of the Tide Chapel on the mainland. She means to reach the Colosseum, and the harbour guild will not let her dock."),
        say("Elder Mahina", "The old smugglers' road under the Hollow Cave comes out beneath the arena itself. It is the only way she can go. But the cave runs deep, and at its heart sleeps a drowned king and his court."),
        say("Elder Mahina", "She is waiting at the arch, north of the village. Will you see her safely through?"),
        say("Kael", "The Colosseum? I was hoping to make my fortune somewhere with a crowd. Consider it done."),
        dict(type="flag", key="st_quest")])
    e2 = dict(base, id="elder2", showIf="st_quest", hideIf="st_sera", actions=[
        say("Elder Mahina", "Sera is at the arch of the Hollow Cave, north of the village, past the old braziers. She has been waiting since dawn.")])
    e3 = dict(base, id="elder3", showIf="st_sera", hideIf="st_done", actions=[
        say("Elder Mahina", "The tides keep you both. Mind the king's court, and do not let her walk ahead of you in the dark.")])
    sera = dict(id="sera_arch", name="Sera", title="Chapel healer", sprite="Sera", x=-2.6, z=-40.6, h=2.4, tint=[1, 1.05, 1.15, 1],
                showIf="st_quest", hideIf="st_sera", reach=4.6, actions=[
        say("Sera", "You must be the one Elder Mahina promised. I am Sera, a healer from the Tide Chapel on the mainland."),
        say("Sera", "The Colosseum's infirmary has sent for chapel healers. The harbour guild turns strangers away from its docks, but the old smugglers' road runs under the sea and comes out in the arena's cellars."),
        say("Sera", "It runs through this cave. The chapel's records say a king was laid to rest here with his whole court, still waiting on a tide that never came. I would rather not meet them alone."),
        say("Kael", "I am Kael. A secret road under the sea to the Colosseum? Lead on. I was going that way anyway."),
        say("Sera", "I am no fighter, but I can keep you standing, and I know how the Chapel's seals are meant to be undone. Stay close."),
        say(None, "Sera takes up her staff and falls in beside you. She joins your party! Equip her before you head on."),
        dict(type="recruit", name="Sera"),
        dict(type="flag", key="st_sera")])
    return e0, [e1, e2, e3, sera]

AUTORUN = []

OBJ = [dict({"if": "fq_done", "unless": "st_quest"}, text="Speak with Elder Mahina in the village"),
       dict({"if": "st_quest", "unless": "st_sera"}, text="Meet Sera at the arch of the Hollow Cave, north of the village"),
       dict({"if": "st_sera", "unless": "st_done"}, text="Enter the Hollow Cave with Sera and follow the smugglers' road to the Colosseum")]

def apply(d):
    """idempotent: patches a built island scene dict in place (also migrates the v1 Lani / raider chain away)"""
    d["npcs"] = [n for n in d["npcs"] if n.get("id") not in OLD_IDS and n.get("id") not in ("elder1", "elder2", "sera_arch")]
    i = next(k for k, n in enumerate(d["npcs"]) if n.get("id") == "elder")
    e0, extra = npcs(d["npcs"][i]); d["npcs"][i] = e0; d["npcs"] += extra
    # the cave arch: the Cave Warden mentions the traveller; the tunnel needs Sera
    for n in d["npcs"]:
        if n.get("id") == "warden1" and not any("pilgrim" in a.get("text", "") for a in n["actions"]):
            n["actions"].insert(1, say("Cave Warden", "A pilgrim girl has been standing at the arch since dawn. Elder Mahina's orders: nobody takes her down there alone."))
    ev = d["events"]
    for e in ev:
        if e.get("id") == "enter_cave": e["showIf"] = "fq_done,st_sera"
    if not any(e.get("id") == "enter_cave_wait" for e in ev):
        enter = next(e for e in ev if e.get("id") == "enter_cave")
        ev.append(dict(id="enter_cave_wait", name="Hollow Cave", x=enter["x"], z=enter["z"], w=enter["w"], d=enter["d"], trigger="touch", once=False, showIf="fq_done,!st_sera",
                       actions=[say(None, "The tunnel mouth is dark and cold. You have a feeling you should not go in alone.", unless="st_quest"),
                                say(None, "A chapel healer is waiting by the arch. Speak with Sera first: Elder Mahina asked you to see her through.", **{"if": "st_quest"})]))
    obj = d.setdefault("objectives", [])
    obj[:] = [o for o in obj if not (o.get("text", "").startswith(("Speak with Elder Mahina", "Find Lani", "Meet Sera", "Enter the Hollow Cave")))]
    j = len(obj)
    obj[j:j] = copy.deepcopy(OBJ)
    # drop the v1 autoruns (smoke over the village, raid portal)
    d["autorun"] = [a for a in (d.get("autorun") or []) if a.get("if") not in ("st_a3", "st_found")]
    d["story"] = True
    return d

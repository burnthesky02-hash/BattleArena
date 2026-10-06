"""Story beats after the Hollow Cave (Oct 6): Kael wakes in the Colosseum's Pit (prison) as the guards' catch; Sera was taken to the infirmary
(cutscene action `away` in cave_story.py) and rejoins in Olympus once Kael is free (st_hurt -> st_sera_back).
apply_prison(d) / apply_olympus(d) patch the built scene dicts in place; both are idempotent. Called by make_prison.py / make_olympus.py and by the
one-off patch of prison.json / olympus.json."""
import copy

def say(who, text, **cond): return dict(type="say", who=who, text=text, **cond)

# ---------------------------------------------------------------- prison
def apply_prison(d):
    for a in d.get("autorun", []):
        if a.get("unless") == "st_jailed":
            a["actions"] = [
                say(None, "Cold stone against your cheek. Iron bars humming in the dark, a chain on your wrist, and somewhere far above, a crowd roaring like surf."),
                say("Overseer Vex", "On your feet, islander. Captain Varro's guards dragged you in at dawn, half drowned and bleeding."),
                say("Overseer Vex", "Word is you broke a Sovereign the arena had already paid for. A beast like that costs eight thousand gold. The Colosseum wants its money's worth, and you are what is left."),
                say("Overseer Vex", "You belong to the Colosseum now. You fight when I say, you bleed when they cheer."),
                say("Kael", "...Where is Sera? The healer who was with me. What did you do with her?"),
                say("Overseer Vex", "The chapel girl? Up in the infirmary, stitching Varro's drowned men. She'll live. Forget her."),
                say("Overseer Vex", "Rise past Rank 2 and the crowd may buy your collar. Until then you are property. Speak to me when you are ready to fight."),
                dict(type="flag", key="st_jailed")]
    def walk(o):
        if isinstance(o, dict):
            t = o.get("text")
            if isinstance(t, str):
                o["text"] = t.replace("THE COLOSSEUM OWNS WHAT THE PORTAL BRINGS.", "THE COLOSSEUM OWNS WHAT ITS GUARDS BRING IN.")
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(d["npcs"]); walk(d.get("events", []))
    return d

# ---------------------------------------------------------------- olympus
def apply_olympus(d):
    for n in d["npcs"]:
        if n.get("id") == "summon" and n.get("name") == "Sera": n["name"] = "Ilya"          # the Colosseum summoner shared the story healer's name
        if n.get("id") == "st_b1":
            for a in n.get("actions", []):
                if "portal" in a.get("text", ""): a["text"] = a["text"].replace("The portal is not done with you", "The door is not done with you")
    d["npcs"] = [n for n in d["npcs"] if n.get("id") != "sera_infirmary"]
    d["npcs"].append(dict(id="sera_infirmary", name="Sera", title="Infirmary healer", sprite="Sera", x=-14.6, z=3.2, h=2.4, tint=[1, 1.05, 1.15, 1],
                          showIf="st_hurt,st_free", hideIf="st_sera_back", reach=4.6, actions=[
        say("Sera", "Kael! You are on your feet! They told me the Pit never gives anyone back."),
        say("Kael", "It gave me a collar, and then a crowd that liked the show. I am free, for now. Are you all right? Where have they had you?"),
        say("Sera", "Stitching up Captain Varro's drowned men, mostly. The infirmary ran out of chapel hands years ago, so they kept me because I was useful. It was an honest sort of captivity."),
        say("Sera", "I never meant to stay. Whatever was singing in that water, I felt it too, and I would like to know what it was. Let me walk with you again."),
        say("Kael", "I would like that. I do not know where this road goes from here, but I would rather not walk it alone."),
        say(None, "Sera takes up her staff and falls in beside you once more."),
        dict(type="flag", key="st_sera_back"),
        dict(type="away", name="Sera", away=False)]))
    # decor: a little infirmary corner on the west side of the concourse (rug, vases, a healing glow)
    GC = "/assets/3D/GodCity/"
    d["pieces"] = [p for p in d["pieces"] if not (p[0].endswith("SM_carpet_square") and p[1] == -14.6)]
    d["pieces"] += [[GC + "SM_carpet_square", -14.6, 3.2, 0, 0.05, 1.05], [GC + "SM_vase_01", -16.6, 1.0, 0, 0, 2.2], [GC + "SM_vase_01", -16.6, 5.4, 0, 0, 2.2]]
    d["decals"] = [x for x in d.get("decals", []) if not (x.get("type") == "glow" and x.get("x") == -14.6)]
    d["decals"].append(dict(type="glow", x=-14.6, z=3.2, r=3.6, color=[0.55, 1, 0.8, 0.9]))
    # leaving the Colosseum: only the old behaviour for saves that never went through the cave knock-out; otherwise Sera must be with you first
    ev = d["events"]
    ex = next((e for e in ev if e.get("id") == "exit_outside"), None)
    if ex is not None:
        for a in ex["actions"]:
            if a.get("text", "").startswith("The same masks that burned the island!"):
                a["text"] = "Violet masks! Raiders at the gate! To arms, hero. This is your home too now."
        ev[:] = [e for e in ev if e.get("id") not in ("exit_outside_b", "exit_wait")]
        ex["showIf"] = "!st_hurt"
        b = copy.deepcopy(ex); b["id"] = "exit_outside_b"; b["showIf"] = "st_hurt,st_sera_back"
        w = dict(id="exit_wait", name="Colosseum exit", x=ex["x"], z=ex["z"], w=ex["w"], d=ex["d"], trigger="touch", once=False, showIf="st_hurt,!st_sera_back",
                 actions=[say(None, "You stop at the gate. You are not leaving without Sera. She is still in the infirmary, on the west side of the concourse."),
                          dict(type="tp", x=0, z=12.2, fade=False)])
        ev += [b, w]
    ob = [o for o in d.get("objectives", []) if o.get("text", "").startswith(("Find Sera", "Defend the Colosseum"))]
    d["objectives"] = [o for o in d.get("objectives", []) if o not in ob] + [
        dict({"if": "st_siege", "unless": "st_space"}, text="Defend the Colosseum!"),
        dict({"if": "st_free,st_hurt", "unless": "st_sera_back"}, text="Find Sera in the Colosseum infirmary, on the west side of the concourse")]
    # arrival line (autorun st_free / not st_arrived): Kael thinks of Sera
    for a in d["autorun"]:
        if a.get("if") == "st_free" and a.get("unless") == "st_arrived" and not any("infirmary" in x.get("text", "") for x in a["actions"]):
            a["actions"].insert(len(a["actions"]) - 1, say("Kael", "Sera is somewhere in this place. The infirmary, the Overseer said. First thing I do is find her.", **{"if": "st_hurt"}))
    return d

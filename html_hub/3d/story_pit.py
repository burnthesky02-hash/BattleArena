"""Story beats after the Hollow Cave (Oct 6): Kenji wakes in the Colosseum's Pit (prison) as the guards' catch; Miya was taken to the infirmary
(cutscene action `away` in cave_story.py) and rejoins in Olympus once Kenji is free (st_hurt -> st_sera_back).
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
                say("Kenji", "...Where is Miya? The healer who was with me. What did you do with her?"),
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
        if n.get("id") == "summon" and n.get("name") == "Miya": n["name"] = "Ilya"          # the Colosseum summoner shared the story healer's name
        if n.get("id") == "st_b1":
            for a in n.get("actions", []):
                if "portal" in a.get("text", ""): a["text"] = a["text"].replace("The portal is not done with you", "The door is not done with you")
    d["npcs"] = [n for n in d["npcs"] if n.get("id") != "sera_infirmary"]
    d["npcs"].append(dict(id="sera_infirmary", name="Miya", title="Infirmary healer", sprite="Miya", x=-14.6, z=3.2, h=2.4, tint=[1, 1.05, 1.15, 1],
                          showIf="st_hurt,st_free", hideIf="st_sera_back", reach=4.6, actions=[
        say("Miya", "Kenji! You are on your feet! They told me the Pit never gives anyone back."),
        say("Kenji", "It gave me a collar, and then a crowd that liked the show. I am free, for now. Are you all right? Where have they had you?"),
        say("Miya", "Stitching up Captain Varro's drowned men, mostly. The infirmary ran out of chapel hands years ago, so they kept me because I was useful. It was an honest sort of captivity."),
        say("Miya", "I never meant to stay. Whatever was singing in that water, I felt it too, and I would like to know what it was. Let me walk with you again."),
        say("Kenji", "I would like that. I do not know where this road goes from here, but I would rather not walk it alone."),
        say(None, "Miya takes up her staff and falls in beside you once more."),
        dict(type="flag", key="st_sera_back"),
        dict(type="away", name="Miya", away=False)]))
    # decor: a little infirmary corner on the west side of the concourse (rug, vases, a healing glow)
    GC = "/assets/3D/GodCity/"
    d["pieces"] = [p for p in d["pieces"] if not (p[0].endswith("SM_carpet_square") and p[1] == -14.6)]
    d["pieces"] += [[GC + "SM_carpet_square", -14.6, 3.2, 0, 0.05, 1.05], [GC + "SM_vase_01", -16.6, 1.0, 0, 0, 2.2], [GC + "SM_vase_01", -16.6, 5.4, 0, 0, 2.2]]
    d["decals"] = [x for x in d.get("decals", []) if not (x.get("type") == "glow" and x.get("x") == -14.6)]
    d["decals"].append(dict(type="glow", x=-14.6, z=3.2, r=3.6, color=[0.55, 1, 0.8, 0.9]))
    # leaving the Colosseum: only the old behaviour for saves that never went through the cave knock-out; otherwise Miya must be with you first
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
                 actions=[say(None, "You stop at the gate. You are not leaving without Miya. She is still in the infirmary, on the west side of the concourse."),
                          dict(type="tp", x=0, z=12.2, fade=False)])
        ev += [b, w]
    ob = [o for o in d.get("objectives", []) if o.get("text", "").startswith(("Find Miya", "Defend the Colosseum"))]
    d["objectives"] = [o for o in d.get("objectives", []) if o not in ob] + [
        dict({"if": "st_siege", "unless": "st_space"}, text="Defend the Colosseum!"),
        dict({"if": "st_free,st_hurt", "unless": "st_sera_back"}, text="Find Miya in the Colosseum infirmary, on the west side of the concourse")]
    # arrival line (autorun st_free / not st_arrived): Kenji thinks of Miya
    for a in d["autorun"]:
        if a.get("if") == "st_free" and a.get("unless") == "st_arrived" and not any("infirmary" in x.get("text", "") for x in a["actions"]):
            a["actions"].insert(len(a["actions"]) - 1, say("Kenji", "Miya is somewhere in this place. The infirmary, the Overseer said. First thing I do is find her.", **{"if": "st_hurt"}))
    return d


# ================================================================ Oct 13: no freedom, Rook breaks you out
# Beating the Unbroken Pair no longer frees the hero. Vex sends him back to his cell to wait for "tomorrow's releasing ceremony"
# (st_ceremony). Sleeping on the cot (st_night) reloads the Pit into a night cutscene: Rook sneaks in, says nobody is ever released, that Miya
# was never taken to any infirmary (Varro's order was a lie; she was left for dead in the cave and Rook's people found her), and opens a door to
# Outpost Kestrel (st_rook, st_free, st_space). Miya is waiting on the landing pad (reunion = st_sera_back); Rook explains the Colosseum there
# (st_rook_told). The Olympus free-roam / siege (st_free arrival, st_siege, st_b1..b3) is no longer reachable on a new playthrough.
# Flags: st_ceremony -> st_night -> st_rook (+ st_free, st_space) -> st_landed -> st_sera_back, st_rook_told.
NIGHT_SPOT = (0, -2.8)          # where Kenji stands in his cell for the night scene (cot is at 0,-5)

def apply_prison_escape(d):
    """Prison scene: the rank-3 release becomes 'wait for the ceremony'; adds the night scene (autorun), Rook (hidden NPC), the cot trigger and the objective."""
    S = lambda who, text, **c: say(who, text, **c)
    ceremony = {"if": "st_done,!st_ceremony,!st_free", "minRank": "freeRank", "actions": [
        S("", "A thunderous chant shakes the dust from the ceiling. Above you, the whole Colosseum is shouting your name."),
        S("Overseer Vex", "Rank 2 behind you, and the crowd wants you free. They bought your collar with their cheering. Don't look so surprised."),
        S("Overseer Vex", "But the Colosseum does not turn a champion loose in the middle of the night. There is a ceremony. Dawn, tomorrow, on the sands, the whole city watching."),
        S("Overseer Vex", "Until then you wait. Back to your cell, champion. Sleep. Don't make me regret being generous."),
        dict(type="fade", to="black", t=0.8),
        dict(type="tp", x=NIGHT_SPOT[0], z=NIGHT_SPOT[1], fade=False),
        dict(type="face", who="player", dir="south"),
        dict(type="fade", to="clear", t=0.8),
        S("", "A guard walks you back to your cell and leaves you alone with the torchlight. Tomorrow. For the first time in a long while the word sounds almost like a promise."),
        S("", "Rest on your cot until the morning comes."),
        dict(type="flag", key="st_ceremony")]}
    night = {"if": "st_night", "unless": "st_rook", "cine": True, "actions": [
        dict(type="cine", on=True),
        dict(type="tp", x=NIGHT_SPOT[0], z=NIGHT_SPOT[1], fade=False), dict(type="face", who="player", dir="south"),
        dict(type="cam", x=0, z=-2.2, yaw=0, pitch=26, dist=15, t=0),
        dict(type="wait", t=0.6),
        dict(type="title", text="THE NIGHT BEFORE", sub="Tomorrow, the releasing ceremony.", t=3.6),
        dict(type="fade", to="clear", t=1.6),
        S("", "You cannot sleep. The crowd above has finally gone quiet, and the torches are burning low in their brackets."),
        S("", "Somewhere down the corridor, iron scrapes softly against stone. A latch turns. Footsteps, very careful ones, coming this way."),
        dict(type="walk", who="rook_night", x=0, z=-0.4, speed=2.4),
        S("Hooded Prisoner", "Quiet. Not a word until I say. You are Kenji, the swordsman off the island?"),
        S("Kenji", "Who are you? How did you get out of your cell?"),
        S("Hooded Prisoner", "A lock is only as good as the man paid to turn it. Listen to me, because we don't have long. There is no ceremony."),
        S("Hooded Prisoner", "Nobody goes free from the Pit. At dawn they walk you down to the Hall of Doors under the sands, and you are never seen again. The Colosseum is not what it seems."),
        S("Kenji", "The Overseer said the crowd bought my collar."),
        S("Hooded Prisoner", "The crowd cheers for whatever it is told to cheer for. Champions are what this place is for."),
        dict(type="face", who="rook_night", dir="east"),
        S("", "The stranger pushes back his hood. A lean face, a bow slung across his back, and the eyes of a man who has not slept in days."),
        S("Rook", "The name is Rook. I would shake your hand, but the guards on the stairs do not allow a lot of time for manners."),
        S("Kenji", "I'm not going anywhere. Miya is in the infirmary somewhere above us. I'm not leaving without her."),
        S("Rook", "Miya was never in the infirmary. Varro said that for your ears, so you'd keep fighting."),
        S("Rook", "His men left her in the cave for dead when the Sovereign fell. My people found her. She is alive, she is safe, and she is already back at my base asking after you."),
        S("Kenji", "...She's alive?"),
        dict(type="shake", t=0.9, amp=0.15, wait=False),
        S("", "Far above, a door slams. Boots on the stairs. A voice echoes down the corridor: \"Check the cells!\""),
        S("Rook", "That is our time gone. Come with me. Outpost Kestrel, the base I told you about. I will explain everything there, I swear it on the bow."),
        S("Kenji", "...All right. Take me to her."),
        S("", "Rook presses something small and humming into his palm. The air above the cot tears open, pale and steady, nothing like the violet doors of the masked raiders."),
        dict(type="flag", key="st_rook"), dict(type="flag", key="st_free"), dict(type="flag", key="st_space"),
        dict(type="flash"),
        dict(type="warp", scene="asteroid", x=0, z=6)]}
    d["autorun"] = [night, ceremony] + [a for a in d.get("autorun", []) if a.get("unless") == "st_jailed"]
    # Rook, hidden until the night scene (appears when st_night is set, gone again once the scene ends)
    d["npcs"] = [n for n in d["npcs"] if n.get("id") != "rook_night"]
    d["npcs"].append(dict(id="rook_night", name="Hooded Prisoner", title="Stranger", sprite="Rook", x=0, z=7.5, h=2.4, tint=[0.5, 0.5, 0.6, 1],
                          showIf="st_night", hideIf="st_rook", reach=0.1, actions=[S("Hooded Prisoner", "Not now.")]))
    # the cot: ordinary sleep until the ceremony is announced, then it starts the night
    ev = d["events"]
    cot = next(e for e in ev if e.get("id") == "pit_cot")
    cot["hideIf"] = "st_ceremony"
    ev[:] = [e for e in ev if e.get("id") != "pit_cot_night"]
    ev.append(dict(id="pit_cot_night", name="Your cot", x=cot["x"], z=cot["z"], w=cot["w"], d=cot["d"], trigger="talk", prompt="Sleep until the ceremony",
                   showIf="st_ceremony", hideIf="st_night", actions=[
        S("", "You lie back on the cot. Tomorrow you walk out into the light. You tell yourself that, over and over, until the roar above fades and sleep almost comes."),
        dict(type="fade", to="black", t=1.2),
        dict(type="flag", key="st_night"),
        dict(type="warp", scene="prison", x=NIGHT_SPOT[0], z=NIGHT_SPOT[1], fresh=True)]))
    d["objectives"] = [o for o in d.get("objectives", []) if o.get("if") != "st_ceremony"] + [
        dict({"if": "st_ceremony"}, unless="st_night", text="The releasing ceremony is at dawn. Rest on your cot in your cell to pass the night.")]
    return d


# ---------------------------------------------------------------- asteroid
def apply_asteroid_escape(d):
    """Outpost Kestrel: arrival through Rook's door, Miya waiting on the pad (reunion), Rook's explanation, Rhea's first lines adjusted."""
    S = lambda who, text, **c: say(who, text, **c)
    for a in d["autorun"]:
        if a.get("unless") == "st_landed":
            a["actions"] = [
                S("", "Cold, thin air and the hum of machinery. You stand on a landing pad, stars wheeling overhead. A huge ringed planet hangs in the sky."),
                S("", "You are not on the island. You are not in the Colosseum. You are not, by the look of it, even in the same world."),
                S("Rook", "Outpost Kestrel. Not much to look at, but nobody here sells tickets. Go on, Miya has been pacing a hole in the deck waiting for you."),
                S("", "Miya is waiting at the edge of the pad. Beyond her, a woman in a flight jacket watches from the far end: Captain Rhea. Speak to Miya first."),
                dict(type="flag", key="st_landed")]
    npcs = [n for n in d["npcs"] if n.get("id") not in ("miya_reunion", "rook_base")]
    npcs.append(dict(id="miya_reunion", name="Miya", title="Healer", sprite="Miya", x=-3.4, z=4.4, h=2.4, tint=[1, 1.05, 1.15, 1],
                     showIf="st_space", hideIf="st_sera_back", reach=4.6, actions=[
        S("Miya", "Kenji! Rook said he would bring you, and I did not dare believe it until I saw you standing on that pad."),
        S("Kenji", "Miya. Thank the sky. Varro told me you were in the Colosseum infirmary. Rook says you were never there."),
        S("Miya", "There was no infirmary. When the Sovereign fell the guards dragged you away and left me in the cave with the water still rising. I thought that was the end of me."),
        S("Miya", "Rook's people found me, carried me through one of their doors and put me back together here. I have been asking after you every day."),
        S("Kenji", "The Overseer lied to keep me fighting. All of it."),
        S("Miya", "Of course he did. Whatever was singing in that water, I felt it too, Kenji, and I do not think it is finished with us. Let me walk with you again."),
        S("Kenji", "I would like that. I would rather not walk this road alone."),
        S("", "Miya takes up her staff and falls in beside you once more."),
        dict(type="flag", key="st_sera_back"),
        dict(type="away", name="Miya", away=False)]))
    npcs.append(dict(id="rook_base", name="Rook", title="Scout of Outpost Kestrel", sprite="Rook", x=3.4, z=4.4, h=2.4, showIf="st_space", reach=4.6, actions=[
        S("Rook", "Right. You have earned the whole story, so here it is. The Colosseum is not an arena. It is a harvest.", unless="st_rook_told"),
        S("Rook", "The Pit sorts the fighters. The weak die in the sand. The strong get their collars bought at a releasing ceremony, a walk down to the Hall of Doors at dawn, and a masked man waiting at the bottom.", unless="st_rook_told"),
        S("Kenji", "The raiders from the island.", unless="st_rook_told"),
        S("Rook", "The same masks. The Colosseum feeds them champions. The portal on your island fed them you. I have spent a long time inside that place pulling out as many as I could, and counting the ones I couldn't.", unless="st_rook_told"),
        S("Rook", "There is a word in their reports. 'The key.' I think that is what they believe you are. And they were not going to let you climb the ladder for long. They were going to walk you straight down to the door.", unless="st_rook_told"),
        S("Kenji", "And what is on the other side of it?", unless="st_rook_told"),
        S("Rook", "Whatever is making whole worlds go quiet. Captain Rhea has the numbers. I only have the bodies. Go and talk to her. And Kenji, that pair you put down in the sand? The crowd really did love you. Shame about the ending they had planned.", unless="st_rook_told"),
        dict(type="flag", key="st_rook_told", unless="st_rook_told"),
        S("Rook", "Captain Rhea is at the far end of the pad. Talk to her when you are ready. And rest, Kenji. You look like you could sleep for a week.", **{"if": "st_rook_told"})]))
    d["npcs"] = npcs
    rhea = next(n for n in d["npcs"] if n.get("id") == "rhea")
    for a in rhea["actions"]:
        t = a.get("text", "")
        if t.startswith("Easy now. You came through the rift"):
            a["text"] = "Easy now. Rook said he would bring you out, and here you are. You are the one the masked raiders have been after. Welcome to Outpost Kestrel, far from any sea."
        elif t.startswith("They have been pulling fighters out of the world"):
            a["text"] = "They have been pulling fighters out of the world and dropping them on rocks like this one, or feeding them to arenas like yours. We think the Colosseum was only the first door."
    d["objectives"] = [o for o in d.get("objectives", []) if o.get("text", "").startswith("Find Miya") is False] + [
        dict({"if": "st_hurt,st_space"}, unless="st_sera_back", text="Find Miya. She is waiting for you at the edge of the landing pad.")]
    return d

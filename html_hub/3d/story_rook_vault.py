"""Story content for chapter 5 (Oct 13): Rook explains the Colosseum at Outpost Kestrel, the Vault tells the legend of the Mind and the Heart,
the living door opens for Kenji, Rook shows his true form (he is the Mind) and strikes the party down, and Kenji wakes on a strange world.

    apply_asteroid_vault(d)   asteroid.json  : Rook's explanation, the vault hatch waits for it, objectives
    apply_vault_rook(d)       vault.json     : lore scene on entry, Rook waits beyond the Warden, the living door, the Mind's reveal, objectives
    build_strange()           strange.json   : a small placeholder world (wake-up scene, rest crystal, plate, objective)

Flags (all st_ so the waking stone, which resets vt_, cannot undo the story):
    st_rook_told  Rook has explained the farm (existing flag, same name as before)
    st_lore       the Vault lore scene has played
    st_mind_a     the door has opened and Rook has taken the item (this flag is what hides Rook / the closed door and shows the Mind)
    st_mind       the Mind has struck the party down
    st_strange    the wake-up scene on the new world has played
Players who finished the Vault before this change keep the old lift / Reach flow because the new content needs st_rook_told or st_rook.
Idempotent: every apply_* function checks for its own marker before adding anything."""
import copy, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DG = "/assets/3D/Dungeon/"
MG = "/assets/3D/Megastructure/"


def say(who, text, **k):
    a = {"type": "say", "who": who, "text": text}
    a.update(k)
    return a


def A(type_, **k):
    d = {"type": type_}
    d.update(k)
    return d


# ---------------------------------------------------------------------------------------------------------------- outpost
ROOK_BASE_ACTIONS = [
    say("Rook", "Sit, Kenji. Breathe. You have earned the truth, or at least the part of it I own. The Colosseum is not an arena. It is a farm.", unless="st_rook_told"),
    say("Kenji", "A farm.", unless="st_rook_told"),
    say("Rook", "A soul farm, and it reaches across more than one world. The sand, the crowds, the ranks, the collars: all of it exists to ripen fighters. The ones who rise high enough get a releasing ceremony and a long walk down to a door. Nobody walks back up.", unless="st_rook_told"),
    say("Rook", "Had you stuck around, yours would have been claimed next.", unless="st_rook_told"),
    say("Kenji", "Who is behind it?", unless="st_rook_told"),
    say("Rook", "I do not know. Who, or what. My people had been investigating the place for a long time before you showed up. We have bodies and reports and rumours. We do not have a name.", unless="st_rook_told"),
    say("Kenji", "Then why free me? Why me, of all the prisoners in that Pit?", unless="st_rook_told"),
    say("Rook", "Because nobody had ever done what you did. In all the years I watched, not one fighter climbed past Rank 2. You were the first.", unless="st_rook_told"),
    say("Rook", "I think that makes you important to whatever the owners of that place are planning. Maybe the key to it. So I pulled you out. Whatever they wanted you for, they do not get it. Call it a wrench in the works.", unless="st_rook_told"),
    say("Miya", "That is a great deal to take in.", unless="st_rook_told"),
    say("Rook", "It is. And it is not finished. We are not in the same world any more, Kenji. The universe is made of many dimensions, and each of them holds many worlds. Your island was one. The Colosseum was another. This rock is a third.", unless="st_rook_told"),
    say("Kenji", "I have a hundred questions.", unless="st_rook_told"),
    say("Rook", "Then come and get your answers. There is a Vault under this base. It holds most of them, maybe all. Speak to Captain Rhea, find Lyra, she has the map, and meet me at the hatch west of the landing pad.", unless="st_rook_told"),
    A("flag", key="st_rook_told", unless="st_rook_told"),
    say("Rook", "Captain Rhea first, then Lyra, then the hatch west of the pad. I will be waiting. And rest if you need it. The Vault is not a place to walk into tired.", if_="st_rook_told"),
]
# `if` is a python keyword; fix the key name for the lines above
for _a in ROOK_BASE_ACTIONS:
    if "if_" in _a:
        _a["if"] = _a.pop("if_")

HATCH_ACTIONS = [
    say("", "A heavy hatch, scorched and sealed. Something below it hums.", unless="st_lyra"),
    say("", "The hatch is shut. Rook was very clear: you should hear what he has to say before you go down there.", if_="st_rook", unless="st_rook_told"),
    say("", "The hatch grinds open on a staircase that spirals down into violet light. The air tastes of metal and old storms.", if_="st_lyra", unless="st_rook,!st_rook_told"),
    A("warp", scene="vault", x=0, z=10, **{"if": "st_lyra", "unless": "st_rook,!st_rook_told"}),
]
for _a in HATCH_ACTIONS:
    if "if_" in _a:
        _a["if"] = _a.pop("if_")

ASTEROID_OBJECTIVES = [
    {"if": "st_sera_back", "unless": "st_rook_told", "text": "Rook has been waiting to talk to you. Find him near the landing pad."},
    {"if": "st_rook_told", "unless": "st_met", "text": "Rook says the answers are in the Vault. Speak with Captain Rhea first (north of the pad)."},
    {"if": "st_met", "unless": "st_lyra", "text": "Find Lyra, the rift scholar (the mess hall, west of the pad). She has the map to the Vault."},
    {"if": "st_lyra,st_rook_told", "unless": "vt_boss", "text": "Meet Rook at the Vault hatch, west of the landing pad, and go down. He promised answers."},
]


def apply_asteroid_vault(d):
    for n in d["npcs"]:
        if n["id"] == "rook_base":
            n["actions"] = copy.deepcopy(ROOK_BASE_ACTIONS)
            n["title"] = "Scout of Outpost Kestrel"
    for e in d["events"]:
        if e["id"] == "vault_hatch":
            e["actions"] = copy.deepcopy(HATCH_ACTIONS)
    have = {o.get("text") for o in d.get("objectives", [])}
    d.setdefault("objectives", [])
    for o in ASTEROID_OBJECTIVES:
        if o["text"] not in have:
            d["objectives"].append(copy.deepcopy(o))
    return d


# ---------------------------------------------------------------------------------------------------------------- vault
DOOR_XZ = (24.0, -284.0)       # the living door (a Dungeon gate scaled up), across the Warden's arena
PLINTH_XZ = (24.0, -289.0)     # the item rests here, behind the door

LORE = [
    "In the beginning there was one world and one being, and nothing else. It was whole, and it was alone.",
    "So it shattered itself. From the pieces it made worlds beyond counting, and in each world it set a life. Every creature that has ever walked, swum or flown is a splinter of that single being.",
    "But it kept two pieces for itself, and gave them the shape of people. One was its Mind. One was its Heart.",
    "They were meant to rule together. To live side by side, and guide the universe through eras of plenty.",
    "After many eons the two grew apart, until they could no longer share a sky. The war that followed shook every dimension. The Mind, the far greater strategist, beat the Heart, the far greater warrior.",
    "Neither could be destroyed. So the Heart was cast out into the human realm.",
    "Again and again, down the ages, the Heart has found its way back. Each time a battle follows that remakes the universe. Each time the Mind prevails, and the Heart is cast out again.",
    "A never-ending cycle.",
]

LORE_SCENE = {
    "if": "st_rook_told",
    "unless": "st_lore",
    "cine": True,
    "actions": [
        A("cine", on=True),
        A("fade", to="clear", t=1.4, wait=False),
        A("cam", x=0, z=12, yaw=0, pitch=26, dist=20, t=0),
        say("", "The stair ends in a hall of violet light. Rook walks ahead of you, Lyra a step behind him and Miya's staff tapping softly on the stone."),
        A("walk", who="vt_rook_in", x=0.5, z=14.2, speed=4),
        say("Rook", "Every wall down here is a page. Most of it I cannot read. But the stone will tell it if you let it."),
        A("face", who="vt_rook_in", dir="east"),
        A("shake", t=1.6, amp=0.12),
        say("", "Rook lays his palm on the Nexus plate. Light runs up the walls like water, and the carvings begin to move."),
    ] + [say("", t) for t in LORE[:3]] + [
        say("Lyra", "The Domain. One being, one law, one dream. My old texts said it was a metaphor."),
    ] + [say("", t) for t in LORE[3:]] + [
        say("Kenji", "The Heart. Cast out into the human realm, over and over."),
        say("Miya", "And the Mind wins every time. How is that not already the end of everything?"),
        say("Rook", "Because the game never finishes. Winning is not the same as being done. That is the whole trick of this place."),
        say("Rook", "There is a door at the heart of this Vault. It has not opened since the war. I have stood in front of it a dozen times and it has not so much as blinked at me."),
        say("Rook", "Something here has been counting the ones who come close. Go on, Kenji. Fight your way to the core. I will take the maintenance stair and meet you at the end. The sentinels know my face and like it even less than yours."),
        A("flag", key="st_lore"),
        A("follow", t=1.4),
    ],
}

# part 1 is Rook's own talk (he waits at the Warden's arena once vt_boss is set)
DOOR_PART1 = [
    say("Rook", "Neatly done. I would have bet on you losing a limb.", unless="st_rook_door"),
    say("Rook", "The door is just beyond the arena. Come. I want to see what it does when it sees you.", unless="st_rook_door"),
    A("flag", key="st_rook_door"),
    A("cine", on=True),
    A("walk", who="player", x=22.5, z=-277, speed=4),
    A("walk", who="vt_rook_end", x=25.5, z=-277, speed=4),
    A("cam", x=24, z=-284, yaw=0, pitch=20, dist=22, t=2.2),
    say("", "At the far end of the arena a door stands taller than a house, sealed by a seam of violet light. Its carvings are faces, hundreds of them, and every one has its eyes shut."),
    A("walk", who="player", x=23, z=-281, speed=3),
    say("Kenji", "It feels like it is looking at me."),
    A("shake", t=2.2, amp=0.3),
    say("", "The carved eyes open, all at once, and every face turns to Kenji."),
    say("The Door", "I KNOW YOU. YOU HAVE COME BACK."),
    A("slide", grp="vdoor", dx=0, dy=14, dz=0, t=3.2, wait=True),
    A("reveal", key="st_vitem"),
    A("shake", t=1.2, amp=0.15),
    say("", "Behind it, on a plinth of black glass, rests a shard of something darker than the room around it. Pale gold light runs along its edge, humming like a held breath."),
    say("Kenji", "What is that?"),
    say("Lyra", "I cannot read a single mark on it. Kenji, wait. Do not touch it."),
    say("Miya", "Rook?"),
    A("walk", who="vt_rook_end", x=24, z=-288, speed=13),
    A("flash"),
    A("shake", t=1.5, amp=0.4),
    say("Rook", "Finally."),
    A("flag", key="st_mind_a"),
    A("warp", scene="vault", x=24, z=-280),
]

DOOR_PART2 = {
    "if": "st_mind_a",
    "unless": "st_mind",
    "cine": True,
    "actions": [
        A("cine", on=True),
        A("fade", to="clear", t=1.2, wait=False),
        A("cam", x=24, z=-287, yaw=0, pitch=14, dist=13, t=0),
        say("", "The shard in Rook's hand drinks the light out of the room. Where the scout stood, something taller is standing, with a face that belongs to no one."),
        say("Kenji", "Rook...?"),
        say("The Mind", "A name for a coat. I wore it well, did I not? The scout. The friend. The hooded man in your cell."),
        say("Miya", "Everything you told us was a lie."),
        say("The Mind", "Every word of it was true, and none of it was the point. The farm is real. Your soul would have been claimed. I only needed you to arrive here with it intact."),
        say("Lyra", "The Mind. The legend on the wall. It was not a story. It was a mirror."),
        say("The Mind", "That door has been sealed since the war. It would open for exactly one hand. I have tried every other way for longer than your world has had a name."),
        say("The Mind", "You are not the first to be carried to it, Kenji. You are the first it opened for."),
        say("Kenji", "What is that thing?"),
        say("The Mind", "A beginning. And your part in it is done."),
        A("flash"),
        A("shake", t=2.5, amp=0.45),
        say("", "Light that is not light. The arena floor folds in on itself. Miya's cry is cut in half. Lyra's book hits the stone. Kenji reaches for his sword and finds his hand already empty."),
        A("flag", key="st_mind"),
        A("fade", to="black", t=1.8),
        A("title", text="Elsewhere", sub="", t=3.0),
        A("warp", scene="strange", x=0, z=28),
    ],
}

VAULT_NPCS = [
    {"id": "vt_rook_in", "name": "Rook", "title": "Scout of Outpost Kestrel", "sprite": "Rook", "x": 3.5, "z": 12.6, "h": 2.4,
     "showIf": "st_rook_told", "hideIf": "st_lore", "reach": 4.6,
     "actions": [say("Rook", "Walk the walkways, fight the sentinels, and read the plates. I will meet you at the end.")]},
    {"id": "vt_rook_end", "name": "Rook", "title": "Scout of Outpost Kestrel", "sprite": "Rook", "x": 24.0, "z": -262.0, "h": 2.4,
     "showIf": "st_rook,vt_boss", "hideIf": "st_mind_a", "reach": 6.0, "actions": DOOR_PART1},
    {"id": "vt_mind", "name": "The Mind", "title": "First Strategist", "sprite": "Rook", "x": 24.0, "z": -288.0, "h": 4.6,
     "tint": [0.55, 0.45, 1.5, 1], "showIf": "st_mind_a", "hideIf": "st_mind", "reach": 5.0, "actions": [say("The Mind", "...")]},
]

VAULT_OBJECTIVES = [
    {"if": "vt_boss,st_rook", "unless": "st_mind_a", "text": "The Warden has fallen. Rook is waiting at the end of the arena. Speak with him."},
]

VAULT_PIECES = [
    # the living door: a closed gate until the scene slides it up; gone for good (and not rebuilt) once st_mind_a is set. Piece = [model, x, z, rot, y, scale, vis, grp]
    [DG + "SM_dg_gate", DOOR_XZ[0], DOOR_XZ[1], 0, 0, 3.0, "st_mind_a", "vdoor"],
    # the item on its plinth, built hidden; the `reveal` action shows it (and nothing sets the flag, so it is gone again after the reload)
    [DG + "SM_dg_block", PLINTH_XZ[0], PLINTH_XZ[1], 0, 0, 1.3, "R:st_vitem"],
    [DG + "SM_dg_crystal", PLINTH_XZ[0], PLINTH_XZ[1], 0, 1.6, 1.0, "R:st_vitem"],
]
VAULT_COLLIDERS = [{"x": DOOR_XZ[0], "z": DOOR_XZ[1], "w": 12.0, "d": 2.0, "hideIf": "st_mind_a"}]
VAULT_DECALS = [{"type": "glow", "x": DOOR_XZ[0], "z": DOOR_XZ[1] - 1, "r": 12, "color": [0.7, 0.42, 1, 0.26], "hideIf": "st_mind_a"}]


def apply_vault_rook(d):
    ids = {n["id"] for n in d["npcs"]}
    if "vt_rook_in" in ids:
        return d
    d["autorun"].insert(0, copy.deepcopy(LORE_SCENE))
    d["autorun"].insert(1, copy.deepcopy(DOOR_PART2))
    d["npcs"].extend(copy.deepcopy(VAULT_NPCS))
    for n in d["npcs"]:
        if n["id"] == "vt_lyra":
            n["showIf"] = "vt_boss,!st_rook"          # in the new flow Lyra is already in the party; only old saves meet her here
    for e in d["events"]:
        if e["id"] == "vt_portal":
            e["showIf"] = "vt_boss,!st_rook"          # the lift waits until Rook's door scene has played (old saves keep it)
    d["pieces"].extend(copy.deepcopy(VAULT_PIECES))
    d["colliders"].extend(copy.deepcopy(VAULT_COLLIDERS))
    d["decals"].extend(copy.deepcopy(VAULT_DECALS))
    d.setdefault("objectives", [])
    d["objectives"].extend(copy.deepcopy(VAULT_OBJECTIVES))
    return d


# ---------------------------------------------------------------------------------------------------------------- strange world
def build_strange():
    reach = json.load(open(os.path.join(HERE, "reach.json"), encoding="utf-8"))
    CS = 6.0
    cells = {(gx, gz) for gx in range(-4, 5) for gz in range(-4, 5)}
    pieces, cols = [], []
    for gx, gz in sorted(cells):
        pieces.append([MG + "SM_floor_module_02", gx * CS, gz * CS, 0, -2.4, 1.2])
    ring = set()
    for gx, gz in cells:
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                if (gx + dx, gz + dz) not in cells:
                    ring.add((gx + dx, gz + dz))
    for gx, gz in sorted(ring):
        cols.append({"x": gx * CS, "z": gz * CS, "w": CS, "d": CS})
    decals = []
    import math
    for i in range(8):
        a = i * math.tau / 8
        x, z = round(17 * math.cos(a), 2), round(17 * math.sin(a), 2)
        pieces.append([DG + "SM_dg_crystal", x, z, 0, 0, 2.2])
        cols.append({"x": x, "z": z, "w": 1.6, "d": 1.6})
        decals.append({"type": "glow", "x": x, "z": z, "r": 9, "color": [0.4, 1, 0.8, 0.22]})
    pieces.append([MG + "SM_lamp_big", 0, 0, 0, 0, 1.3])
    cols.append({"x": 0, "z": 0, "w": 2.2, "d": 2.2})
    pieces.append([DG + "SM_dg_tablet", -6, 15.2, 0, 0, 1.0])
    pieces.append([DG + "SM_dg_crystal", 9, 14.4, 0, 0, 2.2])
    decals.append({"type": "glow", "x": 0, "z": 0, "r": 12, "color": [0.5, 1, 0.85, 0.22]})
    sky = copy.deepcopy(reach["sky"])
    if sky.get("base", {}).get("stops"):
        sky["base"]["stops"] = [[0, "#02100f"], [0.5, "#0a3a3a"], [1, "#2f7a6a"]]
    wake = [
        A("cine", on=True),
        A("music", url="/assets/Music/mp3/28. Holy Sanctuary.mp3"),
        A("fade", to="clear", t=3.0, wait=False),
        A("cam", x=0, z=12, yaw=0, pitch=60, dist=26, t=0),
        say("", "Cold. Then warm. Then a sound that is not the sea, not the arena, not the hum of the Vault: wind through something very tall."),
        A("cam", x=0, z=10, yaw=0, pitch=28, dist=16, t=4, wait=False),
        say("Kenji", "...Miya? Lyra?"),
        say("Miya", "Here. I think. Everything hurts, but it is the ordinary kind of hurt."),
        say("Lyra", "Look at the sky. I count three moons and none of them is one I know. This is not on Rook's maps."),
        say("Kenji", "He was never Rook."),
        say("Lyra", "No. And he is still out there, with that thing in his hand and a door open behind him."),
        say("Kenji", "Then we find a way back. And we find him."),
        A("flag", key="st_strange"),
        A("follow", t=1.4),
    ]
    d = {
        "story": True, "restart": "sg_", "name": "The Unnamed Shore", "kit": "", "tile": 4,
        "autorun": [{"unless": "st_strange", "cine": True, "actions": wake}],
        "objectives": [{"text": "A world with no name, and no way home yet. Look around. (Placeholder world: the story continues here.)"}],
        "music": {"url": "/assets/Music/mp3/28. Holy Sanctuary.mp3"},
        "pieces": pieces, "colliders": cols, "decals": decals, "npcs": [],
        "events": [
            {"id": "sg_rest", "name": "Rest crystal", "x": 9, "z": 14.4, "w": 3, "d": 2.4, "trigger": "talk", "prompt": "Rest and save at the crystal",
             "actions": [say("", "Soft light settles over the party. Wounds close and breath comes easy. The crystal hums and remembers this place: it is now your save point."), A("checkpoint"), A("rest")]},
            {"id": "sg_plate", "name": "Weathered plate", "x": -6, "z": 16.4, "w": 3.2, "d": 2.4, "trigger": "talk", "prompt": "Read the tablet",
             "actions": [say("Weathered Plate", "THIS WORLD HAS NO NAME YET. IT WAS PUT HERE WHERE NOBODY WOULD LOOK.")]},
            {"id": "sg_rift", "name": "Shimmering air", "x": 0, "z": -20, "w": 6, "d": 4, "trigger": "talk", "prompt": "Examine the shimmer",
             "actions": [say("", "The air folds like cloth, and for a moment you see violet light on the other side. Then it closes. Whatever opened this place has not finished with it.")]},
        ],
        "spawn": {"x": 0, "z": 10}, "bounds": {"minX": -27, "maxX": 27, "minZ": -27, "maxZ": 27}, "playerHeight": 2.4,
        "light": {"dir": [-0.35, -1, -0.25], "color": [0.7, 0.95, 0.85], "ambient": [0.28, 0.36, 0.34]},
        "fog": {"color": [0.02, 0.1, 0.1], "near": 40, "far": 150},
        "sky": sky, "fx": [{"type": "dust", "amount": 0.25}],
    }
    return d

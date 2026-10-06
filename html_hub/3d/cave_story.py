"""The Hollow Cave's story layer (v2, Oct 6): replaces the Lani rescue.
Sera joins at the cave arch on the island (island_story.py), so the cave camp no longer has her. At the far end the party walks in on
Colosseum guards who came to capture the Drowned Sovereign alive for the arena and are being crushed (touch event dg_guards_cs, a cutscene that
ends in the boss fight). When the Sovereign falls the party is knocked out (autorun on dg_boss): the guards cannot go home empty-handed, so Kael is
carried to the Colosseum's Pit (st_hurt, st_done, warp to prison) and Sera, a healer, to the infirmary (cutscene action `away`).
apply(d) patches a built dungeon scene dict (make_cave.py calls it just before writing; idempotent)."""
import copy

def say(who, text, **cond): return dict(type="say", who=who, text=text, **cond)
SERA = {"if": "st_sera"}

BOSS_HALL = (-24.0, -918.0)          # where the Sovereign stands (BZ in make_cave.py, moved with the room)

def guards(bx, bz):
    tint = [1.25, 0.8, 0.75, 1]
    out = []
    spots = [("dg_cap", "Captain Varro", "Colosseum beast-warden", "Draven", bx - 7, bz + 11, [1.3, 0.72, 0.68, 1]),
             ("dg_gd1", "Guard Dren", "Beast handler", "Rook", bx + 6, bz + 12, tint),
             ("dg_gd2", "Colosseum Guard", "Beast handler", "Rook", bx - 15, bz + 8, tint),
             ("dg_gd3", "Colosseum Guard", "Beast handler", "Rook", bx + 14, bz + 7, tint)]
    for i, (id_, nm, title, spr, x, z, t) in enumerate(spots):
        out.append(dict(id=id_, name=nm, title=title, sprite=spr, x=round(x, 1), z=round(z, 1), h=2.4, tint=t, hideIf="dg_boss", reach=4.4,
                        actions=[say(nm, "The Sovereign is no beast! It drowns the whole floor under us. Help us, swordsman, or we all go under!" if i == 0 else
                                     ("Chains... we need chains on its legs. Somebody hit it, anything!" if i == 1 else "Captain, the net's gone, it tore it like paper!"))]))
    return out

def guards_cutscene(bx, bz):
    return [
        dict(type="cine", on=True), dict(type="flag", key="dg_guards"),
        dict(type="cam", x=bx, z=bz + 9, yaw=0, pitch=24, dist=46, t=2.6, wait=False),
        say(None, "Steel rings off stone. Beyond the arch, the Sovereign's hall is half underwater: scarlet-and-iron Colosseum guards are scattering across the flooded floor, chains and nets tangled round a colossus of black water and rusted crown."),
        say("Captain Varro", "Hold the line! Nets on its legs! The arena is paying a fortune for this thing alive, so nobody lets it fall!"),
        say("Guard Dren", "Captain, it tore the net like paper! The water keeps healing it. We are losing the whole squad!"),
        say("Captain Varro", "...I can see that, Dren."),
        dict(type="walk", who="player", x=bx + 4, z=bz + 26, speed=5.2),
        dict(type="cam", x=bx - 6, z=bz + 14, yaw=-10, pitch=26, dist=22, t=2.2),
        say("Captain Varro", "You! Swordsman! Whoever you are, you are the best thing that has walked in here all day. Hit it before it drowns the lot of us!"),
        say("Kael", "Hold on. You are trying to capture that? Alive?"),
        say("Captain Varro", "Colosseum business. Do you want to argue, or do you want to live?"),
        say("Sera", "They are bleeding, Kael, and so are you if that thing reaches us. I will keep everyone standing. Please, just stop it.", **SERA),
        say("Kael", "Right. Then I will keep it busy.", **SERA),
        say("Kael", "Right. Keep your heads down, I will keep it busy.", unless="st_sera"),
        dict(type="cam", x=bx, z=bz, yaw=0, pitch=18, dist=26, t=2.0),
        dict(type="music", url="/assets/Music/mp3/27. The Evil One.mp3"),
        say("Drowned Sovereign", "More mortals. More chains. You come into my court, and you ask me to kneel?"),
        say("Drowned Sovereign", "Then draw your blades, and let the sea decide."),
        dict(type="fade", to="black", t=1.0),
        dict(type="title", text="THE DROWNED SOVEREIGN", sub="Lord of the Hollow", t=2.4),
        dict(type="battle", key="dg_boss", boss="drowned_sovereign_boss", level=8),
    ]

def aftermath(bx, bz):
    return [
        dict(type="cine", on=True),
        dict(type="cam", x=bx, z=bz + 6, yaw=0, pitch=26, dist=28, t=0),
        dict(type="fade", to="clear", t=1.4, wait=False),
        say(None, "The Sovereign's crown cracks. His armour of black water comes apart in one long, rushing sigh, and for a moment the whole hall is silent."),
        say("Captain Varro", "It is down... it is actually down! Chains! Get chains on it before it---"),
        say(None, "The water in the hall rises. Not a wave: one single breath, drawn back from every corner of the cave."),
        say("Drowned Sovereign", "The tide... remembers you. It has always... remembered..."),
        say("Kael", "...Do you hear that? Something in the water is singing. I feel like I have heard it before."),
        dict(type="flash"),
        say(None, "The Sovereign's last surge hits like a falling wall. The party is swept off its feet. Kael hears Sera cry out his name, and then there is only the sound of the sea.", **SERA),
        say(None, "The Sovereign's last surge hits like a falling wall. The party is swept off its feet, and then there is only the sound of the sea.", unless="st_sera"),
        dict(type="fade", to="black", t=1.2),
        dict(type="wait", t=1.4),
        say(None, "Voices, far away. Boots in shallow water."),
        say("Captain Varro", "A Sovereign, in dust. Eight thousand gold of arena beast, and nothing left to chain. I cannot march into the Colosseum with empty hands."),
        say("Guard Dren", "Captain... the swordsman is alive. He brought it down himself, near enough."),
        say("Captain Varro", "Then he is the catch. A fighter who can break a Sovereign belongs in the Pit. The crowd will pay to watch what he can do. Chain him."),
        say("Sera", "No, please, he needs a healer, not chains! Let me tend---", **SERA),
        say("Captain Varro", "A chapel healer? Good. The infirmary is full of my drowned men. Take her up to the Colosseum. The swordsman goes below.", **SERA),
        say("Sera", "Kael! Kael, stay with me, I will find you!", **SERA),
        say(None, "Darkness, and the long grind of a cart on stone."),
        dict(type="flag", key="st_bossmsg"), dict(type="flag", key="st_hurt"), dict(type="flag", key="st_done"),
        dict(type="away", name="Sera", away=True),
        dict(type="flash"),
        dict(type="warp", scene="prison", x=0, z=-3.6),
    ]

def apply(d):
    """idempotent"""
    boss = next((n for n in d["npcs"] if n.get("id") == "dg_boss"), None)
    bx, bz = (boss["x"], boss["z"]) if boss else BOSS_HALL
    gone = ("dg_sera", "dg_spirit", "dg_lani", "dg_cap", "dg_gd1", "dg_gd2", "dg_gd3")
    d["npcs"] = [n for n in d["npcs"] if n.get("id") not in gone]
    d["npcs"] += guards(bx, bz)
    for n in d["npcs"]:
        if n.get("id") == "dg_boss":
            n["actions"] = [say("Drowned Sovereign", "You come back to my court? Then draw your blades, and let the sea decide."),
                            dict(type="battle", key="dg_boss", boss="drowned_sovereign_boss", level=8)]
    ev = [e for e in d["events"] if e.get("id") not in ("dg_portal", "dg_guards_cs")]
    d["events"] = ev
    ev.append(dict(id="dg_guards_cs", name="The Sovereign's hall", x=bx + 27, z=bz + 50, w=14, d=3, trigger="touch", once=False, showIf="!dg_guards,!dg_boss",
                   actions=guards_cutscene(bx, bz)))
    obj = [o for o in d.get("objectives", []) if o.get("unless") != "st_sera"]
    d["objectives"] = obj
    ar = [a for a in (d.get("autorun") or []) if a.get("if") not in ("dg_boss", "st_sera")]
    ar.insert(0, {"if": "dg_boss", "unless": "st_hurt", "cine": True, "actions": aftermath(bx, bz)})
    ar.insert(1, {"if": "st_sera", "unless": "st_cave_in", "actions": [
        say("Sera", "The smugglers' road. The chapel's records say their camp lies a little way in, with a fire we can rest at, if it still burns."),
        say("Kael", "Lead on. Or follow, I am good either way. Just do not let me wake any kings."),
        dict(type="flag", key="st_cave_in")]})
    d["autorun"] = ar
    return d

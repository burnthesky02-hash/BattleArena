"""Sample player party. Recruiting/roster-management is out of scope for the
battle prototype, so this is just a fixed starting party of four.
"""
from engine.combatant import Combatant
from engine.stats import Stats


def make_party():
    """Returns a fresh list of party Combatants (call once per battle -- HP/MP/status
    reset via __post_init__ every time a new Combatant is constructed)."""
    kael = Combatant(
        name="Kael", is_enemy=False,
        base_stats=Stats(max_hp=120, max_mp=20, atk=22, def_=16, mag=6, res=8, spd=11, luk=10),
        skill_ids=["power_strike", "cleave", "warcry", "iron_stance"],
        sprite_color=(200, 70, 60),
    )
    lyra = Combatant(
        name="Lyra", is_enemy=False,
        base_stats=Stats(max_hp=75, max_mp=55, atk=8, def_=7, mag=24, res=14, spd=13, luk=12),
        skill_ids=["fireball", "ice_lance", "thunderbolt", "firestorm"],
        sprite_color=(70, 110, 220),
    )
    sera = Combatant(
        name="Sera", is_enemy=False,
        base_stats=Stats(max_hp=85, max_mp=50, atk=9, def_=10, mag=20, res=18, spd=10, luk=11),
        skill_ids=["heal", "greater_heal", "prayer", "holy_light"],
        sprite_color=(230, 210, 90),
    )
    rook = Combatant(
        name="Rook", is_enemy=False,
        base_stats=Stats(max_hp=90, max_mp=25, atk=19, def_=11, mag=7, res=9, spd=17, luk=16),
        skill_ids=["piercing_shot", "poison_dart", "weaken", "sunder"],
        sprite_color=(90, 190, 110),
    )
    return [kael, lyra, sera, rook]

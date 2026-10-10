"""Sample colosseum opponents. Each carries a `persona` string that is flavor
text describing how it fights; the actual tactics live in ai/enemy_ai.py's behavior
profiles, which are keyed by archetype.
"""
from engine.combatant import Combatant
from engine.stats import Stats
from engine.types import Element


def make_enemy_group():
    """Returns a fresh list of enemy Combatants for a colosseum bout."""
    # Stats and kits tuned up from the first pass -- headless testing showed the
    # original trio lost to the default party essentially every time (Miya's
    # healing throughput comfortably outran incoming damage). See README's
    # "Balance" section for the measured before/after win rates.
    golem = Combatant(
        name="Iron Golem", is_enemy=True,
        base_stats=Stats(max_hp=215, max_mp=14, atk=27, def_=24, mag=4, res=10, spd=6, luk=6),
        skill_ids=["power_strike", "crushing_blow", "iron_stance", "self_repair"],
        resistances={Element.PHYSICAL: 0.8, Element.THUNDER: 1.3},
        persona=(
            "A slow, methodical construct. It is patient and calculating: it prefers to "
            "focus fire on whichever enemy has the lowest HP to secure a kill, braces "
            "defensively or repairs itself when its own HP is high and no kill is "
            "available this turn, and saves Crushing Blow for when it can afford the MP."
        ),
        sprite_color=(140, 140, 150),
    )
    bandit = Combatant(
        name="Bandit Rogue", is_enemy=True,
        base_stats=Stats(max_hp=108, max_mp=18, atk=24, def_=11, mag=5, res=7, spd=19, luk=15),
        skill_ids=["poison_dart", "piercing_shot", "sunder"],
        resistances={},
        persona=(
            "Aggressive, reckless, and a bit cocky. Always goes for whichever target it "
            "thinks it can bring down fastest, likes poisoning tough-looking targets to "
            "whittle them down over time, and will sunder (crack the armor of) a "
            "heavily-defended target that's proving hard to kill outright."
        ),
        sprite_color=(150, 90, 40),
    )
    cultist = Combatant(
        name="Dark Cultist", is_enemy=True,
        base_stats=Stats(max_hp=98, max_mp=55, atk=8, def_=8, mag=26, res=14, spd=9, luk=9),
        skill_ids=["shadow_bolt", "life_drain", "weaken", "sunder"],
        resistances={Element.DARK: 0.5, Element.HOLY: 1.3},
        persona=(
            "Cowardly and manipulative caster. Prefers to weaken or sunder the enemy's "
            "strongest-looking fighter rather than trade blows directly, favors Life "
            "Drain over a plain Shadow Bolt when its own HP isn't full since the "
            "lifesteal keeps it in the fight longer, and only attacks directly when it "
            "feels safe (its own HP is comfortably high)."
        ),
        sprite_color=(90, 40, 110),
    )
    return [golem, bandit, cultist]

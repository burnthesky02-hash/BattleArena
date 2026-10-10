"""Short flavor bios for the 25 named recruitable heroes (data/summon_pool.py's
RECRUITABLE_ROSTER), shown on the Heroes screen's hero detail page. Purely
cosmetic -- nothing here is read by the battle engine.

One or two sentences each, in-setting for the Colosseum: who they are and
why they fight. Written to at least gesture at each hero's actual kit
(their signature skill, from data/hero_skills.py) rather than being
generic, but kept short enough not to crowd the detail page.
"""
from typing import Dict

HERO_LORE: Dict[str, str] = {
    # tank
    "Gareth": "A city-watch veteran who traded a quiet pension for the Colosseum sand. His shield has stopped more blows than he can count, and he still steps in front of the ones aimed at someone else.",
    "Brutus": "Built like the arena wall he trains against. Brutus doesn't dodge -- he plants his feet, lets the hit land, and answers it with a slam that cracks the stone underfoot.",
    "Petra": "A former siege-engineer who decided armor was a more interesting problem than architecture. She studies an opponent's swing before the fight even starts, and punishes it the moment it repeats.",
    "Draven": "Exiled from a northern legion for refusing to fall back. Draven treats every match as the last stand he was never allowed to make, and by the finish, he usually means it.",
    "Yulia": "The undefeated champion's bodyguard, until the champion asked her to fight instead of just guard. Her wall of light has never once come down mid-round.",
    # melee_dps
    "Bran": "A farmhand who found out the hard way that his swing could put a bandit through a fence post. He fights the same way he worked the fields -- flat out, no half measures.",
    "Vex": "Grew up picking locks and pockets before picking fights paid better. Twin blades, twin openings -- Vex is already gone before an opponent finishes reacting to the first cut.",
    "Thorne": "Pays for every reckless strike in his own blood, and calls it a fair trade. The crowd loves him for it; the healers less so.",
    "Rhea": "Daughter of a blademaster who never let her win a single sparring match at home. She's made up for it since, one clean execution at a time.",
    "Kenji": "The mythic name every melee_dps recruit gets compared to. Kenji doesn't so much fight as fall on people -- his skyfall strike has ended more matches than anyone bothers counting anymore.",
    # ranged_dps
    "Sylas": "A hunter who followed a wounded elk to the Colosseum gates and never left. His quick shots aren't flashy, but they're fast enough that flashy rarely gets the chance to matter.",
    "Nadia": "Raised catching snakes for the local apothecary; her arrows carry the same lesson -- it's never the first bite that finishes you off.",
    "Zara": "A former caravan scout who can read a battlefield the way others read a map. She marks her target early and lets the whole fight bend around that one arrow.",
    "Finn": "Won a betting pool once by putting six arrows in the air before the first one landed. He's been trying to beat his own record ever since.",
    "Rook": "The mythic marksman the ranged_dps line is named for. One arrow, one opening, one kill -- Rook doesn't need a second shot, and rarely takes one.",
    # mage
    "Ignis": "An apprentice who got expelled from the academy for setting the exam hall on fire. The Colosseum, it turns out, has far fewer complaints about that.",
    "Wren": "Grew up in the northern passes where a careless step meant an avalanche. She's brought that same cold, controlled violence to the arena floor.",
    "Solene": "A storm-chaser turned battlemage who insists the lightning found her, not the other way around. The scorch marks on her robes suggest it's a two-way relationship.",
    "Kade": "Studied under a hedge-wizard who vanished mid-lecture and was never seen again. Kade still isn't sure what that spell did, only that it works.",
    "Lyra": "The mythic mage whose prism magic the whole class is built around. She doesn't just throw one element at an opponent -- by the time the cascade lands, she's thrown all of them.",
    # support
    "Elowen": "A village healer who followed her patients into the arena because half of them kept getting hurt again anyway. She'd rather mend a fighter than bury one.",
    "Dassin": "A traveling priest who preaches less than he practices. His cleansing light has talked more curses and poisons out of a body than any sermon ever has.",
    "Mira": "Raised in a temple that trained knights, not clerics -- so her blessings land like a shield going up, not a prayer being said.",
    "Osric": "An old campaign banner-bearer who found out his voice alone could turn a losing fight around. He hasn't stopped shouting encouragement since.",
    "Miya": "The mythic support the whole class takes its name from. Wherever Miya stands, the fight tilts back toward the living -- her grace has pulled more allies back from the edge than anyone can properly thank her for.",
}

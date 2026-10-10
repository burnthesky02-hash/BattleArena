"""Per-hero unique skills.

Every hero of a given class used to share the exact same 4 skills forever --
recruiting a rarer hero of a class only ever granted better stats, never new
abilities. A first pass gave each of the 25 named heroes in
data/summon_pool.py's RECRUITABLE_ROSTER their own unique 4th "signature"
skill, leaving skills 1-3 shared per class. Andrew asked for skills to be
"different" across characters more broadly, while keeping some reuse ("some
skills could be reused here and there") -- so this module now keeps exactly
ONE skill shared per class (that class's basic "staple" move: power_strike/
piercing_shot/fireball/heal) and makes the other 3 of each hero's 4 skills
unique to them.

HERO_SKILLS maps a hero's name to their 3 non-staple skill ids, in the same
order as the class kit's non-staple slots (see STAPLE_SKILL_INDEX below for
which slot that is per class) -- the first two are new kit skills (defined
in data/skills_db.py's "hero kit skills (2nd pass)" section), and the third
is that hero's existing signature/capstone skill from the first pass
(data/skills_db.py's "signature skills" section), unchanged.

This also happens to fix melee_dps's old shared 4th skill (holy_reset, a
2-MP full heal that hit both sides -- almost certainly a debug leftover): a
named melee_dps hero now gets their own signature skill instead of ever
reaching for it. holy_reset itself is left in data/skills_db.py unchanged,
since data/classes.py's shared kit (the fallback for anyone not listed
below) still lists it.
"""
from typing import Dict, List

from data.classes import CLASS_ARCHETYPES

# Which index of a class's 4-skill kit (data/classes.py's
# CLASS_ARCHETYPES[class_id].skill_ids) is the shared "staple" that stays
# untouched. Every class puts its staple first except tank, whose kit lists
# it 2nd (["iron_stance", "power_strike", "sunder", "self_repair"]) --
# checked against the actual file rather than assumed.
STAPLE_SKILL_INDEX: Dict[str, int] = {
    "tank": 1,
    "melee_dps": 0,
    "ranged_dps": 0,
    "mage": 0,
    "support": 0,
}

# name -> [kit skill A, kit skill B, signature skill] (see module docstring).
HERO_SKILLS: Dict[str, List[str]] = {
    # tank
    "Gareth": ["brace", "pommel_strike", "shield_bash"],
    "Brutus": ["grit_teeth", "heavy_slam", "ground_slam"],
    "Petra": ["fortify", "overpower", "crushing_counter"],
    "Draven": ["iron_resolve", "colossus_blow", "dravens_fury"],
    "Yulia": ["unbreakable", "titans_judgment", "aegis_wall"],
    # melee_dps
    "Bran": ["flurry", "overhead_chop", "reckless_swing"],
    "Vex": ["twin_fangs", "savage_cut", "rending_strike"],
    "Thorne": ["whirling_blades", "brutal_combo", "blood_for_power"],
    "Rhea": ["storm_of_blades", "dragon_fang", "executioners_edge"],
    "Kenji": ["blade_dance", "ascendant_strike", "skyfall_slash"],
    # ranged_dps
    "Sylas": ["sting_shot", "snipe", "quick_shot"],
    "Nadia": ["crippling_arrow", "double_tap", "venom_volley"],
    "Zara": ["volley", "piercing_barrage", "hunters_mark"],
    "Finn": ["arrow_storm", "longshot", "rapid_barrage"],
    "Rook": ["rain_of_arrows", "piercing_fang", "dead_eye"],
    # mage
    "Ignis": ["frost_bite", "static_shock", "spark"],
    "Wren": ["ice_shard", "chain_lightning", "frost_nova"],
    "Solene": ["glacial_spike", "storm_call", "arc_discharge"],
    "Kade": ["absolute_zero", "thunder_judgment", "void_lance"],
    "Lyra": ["absolute_frost", "tempest", "prism_cascade"],
    # support
    "Elowen": ["soothing_touch", "gentle_wave", "mend"],
    "Dassin": ["purify", "circle_of_care", "cleansing_light"],
    "Mira": ["radiant_touch", "sanctuary", "aegis_blessing"],
    "Osric": ["lifebinder", "hymn_of_mercy", "rally_cry"],
    "Miya": ["divine_touch", "aura_of_life", "seras_grace"],
}


def skill_ids_for(name: str, class_id: str) -> List[str]:
    """The class's shared kit, with every slot except the staple slot
    (STAPLE_SKILL_INDEX) replaced by this hero's own 3 unique skills, in
    order, if they have any (falls back to the class default unchanged for
    anyone not in HERO_SKILLS -- a future recruit added to the roster
    without unique skills yet, or any non-hero combatant)."""
    base = list(CLASS_ARCHETYPES[class_id].skill_ids)
    skills = HERO_SKILLS.get(name)
    if not skills or not base:
        return base
    staple_index = STAPLE_SKILL_INDEX.get(class_id, 0)
    non_staple_indices = [i for i in range(len(base)) if i != staple_index]
    for index, skill_id in zip(non_staple_indices, skills):
        base[index] = skill_id
    return base

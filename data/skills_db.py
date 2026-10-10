"""The full skill registry. Every skill a character or enemy can know lives here."""
from engine.skills import Skill
from engine.types import Element, TargetType

SKILLS = {
    # --- physical --------------------------------------------------
    "power_strike": Skill(
        id="power_strike", name="Power Strike", mp_cost=7, power=1.5, kind="physical",
        target=TargetType.SINGLE_ENEMY, description="A heavy single-target physical blow.",
    ),
    "cleave": Skill(
        id="cleave", name="Cleave", mp_cost=8, power=0.9, kind="physical",
        target=TargetType.ALL_ENEMIES, description="A sweeping strike that hits all enemies.",
    ),
    "piercing_shot": Skill(
        id="piercing_shot", name="Piercing Shot", mp_cost=3, power=1.4, kind="physical",
        target=TargetType.SINGLE_ENEMY, description="A precise arrow shot, cheap and reliable.",
    ),
    "poison_dart": Skill(
        id="poison_dart", name="Poison Dart", mp_cost=5, power=0.8, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="poison", status_chance=0.75,
        description="A dart coated in venom; may poison the target.",
    ),
    "crushing_blow": Skill(
        id="crushing_blow", name="Crushing Blow", mp_cost=7, power=2.1, kind="physical",
        target=TargetType.SINGLE_ENEMY, description="A devastating heavy strike, slow but brutal.",
    ),


    # --- magical (offensive) ----------------------------------------
    "fireball": Skill(
        id="fireball", name="Fireball", mp_cost=6, power=1.8, kind="magical", element=Element.FIRE,
        target=TargetType.SINGLE_ENEMY, description="Hurls a ball of fire at one enemy.",
    ),
    "ice_lance": Skill(
        id="ice_lance", name="Ice Lance", mp_cost=6, power=1.7, kind="magical", element=Element.ICE,
        target=TargetType.SINGLE_ENEMY, status_to_apply="def_down", status_chance=0.3,
        description="A shard of ice that may chill the target's defenses.",
    ),
    "thunderbolt": Skill(
        id="thunderbolt", name="Thunderbolt", mp_cost=9, power=1.6, kind="magical", element=Element.THUNDER,
        target=TargetType.SINGLE_ENEMY, status_to_apply="stun", status_chance=0.25,
        description="A bolt of lightning that may stun the target.",
    ),
    "holy_light": Skill(
        id="holy_light", name="Holy Light", mp_cost=7, power=1.5, kind="magical", element=Element.HOLY,
        target=TargetType.SINGLE_ENEMY, description="Radiant energy, especially punishing to dark creatures.",
    ),
    "shadow_bolt": Skill(
        id="shadow_bolt", name="Shadow Bolt", mp_cost=7, power=1.5, kind="magical", element=Element.DARK,
        target=TargetType.SINGLE_ENEMY, description="A bolt of dark energy.",
    ),
    "life_drain": Skill(
        id="life_drain", name="Life Drain", mp_cost=10, power=1.3, kind="magical", element=Element.DARK,
        target=TargetType.SINGLE_ENEMY, lifesteal=0.6,
        description="Siphons the target's life force, healing the caster for a share of the damage.",
    ),
    "firestorm": Skill(
        id="firestorm", name="Firestorm", mp_cost=14, power=1.1, kind="magical", element=Element.FIRE,
        target=TargetType.ALL_ENEMIES, description="Fire rains down on the whole enemy side.",
    ),

    # --- healing / support --------------------------------------------
    "heal": Skill(
        id="heal", name="Heal", mp_cost=5, power=1.2, kind="heal",
        target=TargetType.SINGLE_ALLY, description="Restores a moderate amount of HP to one ally.",
    ),
    "greater_heal": Skill(
        id="greater_heal", name="Greater Heal", mp_cost=10, power=2.2, kind="heal",
        target=TargetType.SINGLE_ALLY, description="Restores a large amount of HP to one ally.",
    ),
    "prayer": Skill(
        id="prayer", name="Prayer", mp_cost=14, power=1.0, kind="heal",
        target=TargetType.ALL_ALLIES, description="A gentle heal that washes over the whole party.",
    ),

    # --- buffs / debuffs (status-only, no direct damage/heal) --------
    "warcry": Skill(
        id="warcry", name="Warcry", mp_cost=6, power=0.0, kind="status",
        target=TargetType.SELF, status_to_apply="atk_up", status_chance=1.0,
        description="A battle roar that raises the caster's own attack.",
    ),
    "iron_stance": Skill(
        id="iron_stance", name="Iron Stance", mp_cost=6, power=0.0, kind="status",
        target=TargetType.SELF, status_to_apply="def_up", status_chance=1.0,
        description="A defensive stance that raises the caster's own defense.",
    ),
    "self_repair": Skill(
        id="self_repair", name="Self-Repair", mp_cost=5, power=0.0, kind="status",
        target=TargetType.SELF, status_to_apply="regen", status_chance=1.0,
        description="Mends the caster's own wounds (or, for a construct, its own frame) over time.",
    ),
    "weaken": Skill(
        id="weaken", name="Weaken", mp_cost=6, power=0.0, kind="status",
        target=TargetType.SINGLE_ENEMY, status_to_apply="atk_down", status_chance=0.8,
        description="Saps an enemy's physical strength.",
    ),
    "sunder": Skill(
        id="sunder", name="Sunder", mp_cost=6, power=0.0, kind="status",
        target=TargetType.SINGLE_ENEMY, status_to_apply="def_down", status_chance=0.8,
        description="Cracks an enemy's armor, lowering its defense.",
    ),
    "holy_reset": Skill(
        id="holy_reset", name="Holy Reset", mp_cost=2, power=100.0, kind="heal",
        target=TargetType.ALL, description="Restores All Health",
    ),

    # --- signature skills ---------------------------------------------
    # One per named recruitable hero (data/summon_pool.py's RECRUITABLE_ROSTER),
    # slotted in as that hero's 4th/capstone skill by data/hero_skills.py's
    # skill_ids_for(), replacing the class's shared 4th slot (see that
    # module for how). Skills 1-3 stay shared per class; this is what makes
    # two heroes of the same class actually play differently.

    # tank (replaces the shared "self_repair" slot)
    "shield_bash": Skill(
        id="shield_bash", name="Shield Bash", mp_cost=5, power=1.2, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="stun", status_chance=0.2,
        description="Gareth slams a shield into the target, sometimes stunning it.",
    ),
    "ground_slam": Skill(
        id="ground_slam", name="Ground Slam", mp_cost=9, power=1.0, kind="physical",
        target=TargetType.ALL_ENEMIES, status_to_apply="def_down", status_chance=0.25,
        description="Brutus slams the ground, rattling every enemy's defenses.",
    ),
    "crushing_counter": Skill(
        id="crushing_counter", name="Crushing Counter", mp_cost=7, power=1.4, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="atk_down", status_chance=0.3,
        description="Petra punishes an opening with a blow that saps the target's own strength.",
    ),
    "dravens_fury": Skill(
        id="dravens_fury", name="Draven's Fury", mp_cost=8, power=0.0, kind="status",
        target=TargetType.SELF, status_to_apply="atk_up", status_chance=1.0,
        description="Draven works himself into a fighting rage, raising his own attack.",
    ),
    "aegis_wall": Skill(
        id="aegis_wall", name="Aegis Wall", mp_cost=10, power=1.6, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="def_down", status_chance=0.4, lifesteal=0.2,
        description="Yulia bulls through the target's guard and mends her own wounds with the impact.",
    ),

    # melee_dps (replaces the shared "holy_reset" slot)
    "reckless_swing": Skill(
        id="reckless_swing", name="Reckless Swing", mp_cost=6, power=1.7, kind="physical",
        target=TargetType.SINGLE_ENEMY, description="Bran swings with no regard for his own footing.",
    ),
    "rending_strike": Skill(
        id="rending_strike", name="Rending Strike", mp_cost=7, power=1.4, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="def_down", status_chance=0.35,
        description="Vex tears at armor and hide alike, weakening the target's defense.",
    ),
    "blood_for_power": Skill(
        id="blood_for_power", name="Blood for Power", mp_cost=6, power=1.6, kind="physical",
        target=TargetType.SINGLE_ENEMY, lifesteal=0.3,
        description="Thorne fuels the strike with his own blood, healing off the damage dealt.",
    ),
    "executioners_edge": Skill(
        id="executioners_edge", name="Executioner's Edge", mp_cost=11, power=2.3, kind="physical",
        target=TargetType.SINGLE_ENEMY, description="Rhea brings down a single, merciless finishing blow.",
    ),
    "skyfall_slash": Skill(
        id="skyfall_slash", name="Skyfall Slash", mp_cost=9, power=2.0, kind="physical",
        target=TargetType.ALL_ENEMIES, description="Kenji leaps and comes down through every enemy at once.",
    ),

    # ranged_dps (replaces the shared "sunder" slot)
    "quick_shot": Skill(
        id="quick_shot", name="Quick Shot", mp_cost=4, power=1.2, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="stun", status_chance=0.1,
        description="Sylas snaps off a fast shot, occasionally catching the target off guard.",
    ),
    "venom_volley": Skill(
        id="venom_volley", name="Venom Volley", mp_cost=10, power=1.1, kind="physical",
        target=TargetType.ALL_ENEMIES, status_to_apply="poison", status_chance=0.5,
        description="Nadia peppers the whole enemy line with poisoned arrows.",
    ),
    "hunters_mark": Skill(
        id="hunters_mark", name="Hunter's Mark", mp_cost=6, power=1.3, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="def_down", status_chance=0.4,
        description="Zara marks a target's weak point, exposing it to further hits.",
    ),
    "rapid_barrage": Skill(
        id="rapid_barrage", name="Rapid Barrage", mp_cost=10, power=2.0, kind="physical",
        target=TargetType.SINGLE_ENEMY, description="Finn fires a burst of arrows faster than the eye can follow.",
    ),
    "dead_eye": Skill(
        id="dead_eye", name="Dead Eye", mp_cost=8, power=2.2, kind="physical",
        target=TargetType.SINGLE_ENEMY, description="Rook lines up one shot and puts it exactly where it hurts.",
    ),

    # mage (replaces the shared "firestorm" slot)
    "spark": Skill(
        id="spark", name="Spark", mp_cost=4, power=1.3, kind="magical", element=Element.FIRE,
        target=TargetType.SINGLE_ENEMY, description="Ignis flicks out a cheap, reliable bolt of flame.",
    ),
    "frost_nova": Skill(
        id="frost_nova", name="Frost Nova", mp_cost=11, power=1.0, kind="magical", element=Element.ICE,
        target=TargetType.ALL_ENEMIES, status_to_apply="def_down", status_chance=0.25,
        description="Wren detonates a burst of frost that chills every enemy's defenses.",
    ),
    "arc_discharge": Skill(
        id="arc_discharge", name="Arc Discharge", mp_cost=8, power=1.6, kind="magical", element=Element.THUNDER,
        target=TargetType.SINGLE_ENEMY, status_to_apply="stun", status_chance=0.2,
        description="Solene channels a crackling arc that may lock the target up entirely.",
    ),
    "void_lance": Skill(
        id="void_lance", name="Void Lance", mp_cost=10, power=1.9, kind="magical", element=Element.DARK,
        target=TargetType.SINGLE_ENEMY, lifesteal=0.25,
        description="Kade drives a lance of dark energy through the target, drawing off some of its life.",
    ),
    "prism_cascade": Skill(
        id="prism_cascade", name="Prism Cascade", mp_cost=15, power=1.4, kind="magical", element=Element.HOLY,
        target=TargetType.ALL_ENEMIES, description="Lyra scatters radiant light across the whole enemy line.",
    ),

    # support (replaces the shared "holy_light" slot)
    "mend": Skill(
        id="mend", name="Mend", mp_cost=6, power=1.3, kind="heal",
        target=TargetType.SINGLE_ALLY, description="Elowen knits an ally's wounds shut with a gentle touch.",
    ),
    "cleansing_light": Skill(
        id="cleansing_light", name="Cleansing Light", mp_cost=8, power=1.0, kind="heal",
        target=TargetType.SINGLE_ALLY, status_to_apply="regen", status_chance=1.0,
        description="Dassin's light heals now and keeps healing an ally for a few turns after.",
    ),
    "aegis_blessing": Skill(
        id="aegis_blessing", name="Aegis Blessing", mp_cost=9, power=0.0, kind="status",
        target=TargetType.SINGLE_ALLY, status_to_apply="def_up", status_chance=1.0,
        description="Mira wraps an ally in a protective ward, raising their defense.",
    ),
    "rally_cry": Skill(
        id="rally_cry", name="Rally Cry", mp_cost=10, power=0.0, kind="status",
        target=TargetType.ALL_ALLIES, status_to_apply="atk_up", status_chance=1.0,
        description="Osric rallies the whole party, raising everyone's attack.",
    ),
    "seras_grace": Skill(
        id="seras_grace", name="Miya's Grace", mp_cost=12, power=2.0, kind="heal",
        target=TargetType.ALL_ALLIES, description="Miya pours out a large, party-wide heal.",
    ),

    # --- hero kit skills (2nd pass) ------------------------------------
    # Two more per named recruitable hero, slotted into the class kit's old
    # 2nd/3rd shared slots by data/hero_skills.py's skill_ids_for() (see that
    # module). Only the class's staple 1st skill (power_strike/piercing_shot/
    # fireball/heal) stays shared across all 5 heroes of a class now -- the
    # other 3 of each hero's 4 skills are unique to them.

    # tank (replace the shared "iron_stance" and "sunder" slots)
    "brace": Skill(
        id="brace", name="Brace", mp_cost=4, power=0.0, kind="status",
        target=TargetType.SELF, status_to_apply="def_up", status_chance=1.0,
        description="Gareth braces behind his shield, raising his own defense.",
    ),
    "pommel_strike": Skill(
        id="pommel_strike", name="Pommel Strike", mp_cost=4, power=1.1, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="stun", status_chance=0.1,
        description="Gareth cracks the target with his weapon's hilt, occasionally stunning it.",
    ),
    "grit_teeth": Skill(
        id="grit_teeth", name="Grit Teeth", mp_cost=6, power=0.0, kind="status",
        target=TargetType.SELF, status_to_apply="atk_up", status_chance=1.0,
        description="Brutus grits his teeth and pushes through the pain, raising his own attack.",
    ),
    "heavy_slam": Skill(
        id="heavy_slam", name="Heavy Slam", mp_cost=8, power=1.5, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="def_down", status_chance=0.3,
        description="Brutus brings his whole weight down on the target, cracking its guard.",
    ),
    "fortify": Skill(
        id="fortify", name="Fortify", mp_cost=7, power=0.0, kind="status",
        target=TargetType.SELF, status_to_apply="def_up", status_chance=1.0,
        description="Petra sets her footing, raising her own defense.",
    ),
    "overpower": Skill(
        id="overpower", name="Overpower", mp_cost=8, power=1.7, kind="physical",
        target=TargetType.SINGLE_ENEMY, description="Petra bulls straight through the target's guard.",
    ),
    "iron_resolve": Skill(
        id="iron_resolve", name="Iron Resolve", mp_cost=6, power=1.3, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="atk_down", status_chance=0.3,
        description="Draven grinds the target down, sapping its strength.",
    ),
    "colossus_blow": Skill(
        id="colossus_blow", name="Colossus Blow", mp_cost=10, power=1.9, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="stun", status_chance=0.25,
        description="Draven swings with his full mass behind it, sometimes stunning the target outright.",
    ),
    "unbreakable": Skill(
        id="unbreakable", name="Unbreakable", mp_cost=9, power=0.0, kind="status",
        target=TargetType.SELF, status_to_apply="def_up", status_chance=1.0,
        description="Yulia hardens herself against anything the enemy can throw, raising her own defense.",
    ),
    "titans_judgment": Skill(
        id="titans_judgment", name="Titan's Judgment", mp_cost=11, power=2.1, kind="physical",
        target=TargetType.ALL_ENEMIES, description="Yulia brings down a devastating blow across every enemy at once.",
    ),

    # melee_dps (replace the shared "cleave" and "crushing_blow" slots)
    "flurry": Skill(
        id="flurry", name="Flurry", mp_cost=5, power=1.3, kind="physical",
        target=TargetType.SINGLE_ENEMY, description="Bran strings together a fast flurry of blows.",
    ),
    "overhead_chop": Skill(
        id="overhead_chop", name="Overhead Chop", mp_cost=6, power=1.5, kind="physical",
        target=TargetType.SINGLE_ENEMY, description="Bran brings his weapon down in one heavy overhead chop.",
    ),
    "twin_fangs": Skill(
        id="twin_fangs", name="Twin Fangs", mp_cost=7, power=1.2, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="poison", status_chance=0.3,
        description="Vex strikes twice in quick succession, one blade coated in poison.",
    ),
    "savage_cut": Skill(
        id="savage_cut", name="Savage Cut", mp_cost=8, power=1.6, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="def_down", status_chance=0.2,
        description="Vex opens a savage cut that leaves the target's guard worse for it.",
    ),
    "whirling_blades": Skill(
        id="whirling_blades", name="Whirling Blades", mp_cost=9, power=1.1, kind="physical",
        target=TargetType.ALL_ENEMIES, description="Thorne spins through the whole enemy line at once.",
    ),
    "brutal_combo": Skill(
        id="brutal_combo", name="Brutal Combo", mp_cost=9, power=1.8, kind="physical",
        target=TargetType.SINGLE_ENEMY, description="Thorne chains together a brutal string of hits on one target.",
    ),
    "storm_of_blades": Skill(
        id="storm_of_blades", name="Storm of Blades", mp_cost=11, power=1.3, kind="physical",
        target=TargetType.ALL_ENEMIES, status_to_apply="def_down", status_chance=0.2,
        description="Rhea cuts down every enemy at once, leaving their defenses in tatters.",
    ),
    "dragon_fang": Skill(
        id="dragon_fang", name="Dragon Fang", mp_cost=10, power=2.1, kind="physical",
        target=TargetType.SINGLE_ENEMY, lifesteal=0.15,
        description="Rhea drives a fang-shaped blow through the target, drawing off some of its life.",
    ),
    "blade_dance": Skill(
        id="blade_dance", name="Blade Dance", mp_cost=11, power=1.5, kind="physical",
        target=TargetType.ALL_ENEMIES, description="Kenji weaves through the whole enemy line in one fluid dance of steel.",
    ),
    "ascendant_strike": Skill(
        id="ascendant_strike", name="Ascendant Strike", mp_cost=11, power=2.2, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="stun", status_chance=0.2,
        description="Kenji leaps and brings down a strike with enough force to stun the target.",
    ),

    # ranged_dps (replace the shared "poison_dart" and "weaken" slots)
    "sting_shot": Skill(
        id="sting_shot", name="Sting Shot", mp_cost=4, power=1.2, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="poison", status_chance=0.3,
        description="Sylas looses a barbed shot that may poison the target.",
    ),
    "snipe": Skill(
        id="snipe", name="Snipe", mp_cost=5, power=1.4, kind="physical",
        target=TargetType.SINGLE_ENEMY, description="Sylas takes a careful shot at a single target.",
    ),
    "crippling_arrow": Skill(
        id="crippling_arrow", name="Crippling Arrow", mp_cost=6, power=1.1, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="atk_down", status_chance=0.3,
        description="Nadia's arrow finds a joint, sapping the target's strength.",
    ),
    "double_tap": Skill(
        id="double_tap", name="Double Tap", mp_cost=8, power=1.6, kind="physical",
        target=TargetType.SINGLE_ENEMY, description="Nadia fires two shots in immediate succession.",
    ),
    "volley": Skill(
        id="volley", name="Volley", mp_cost=9, power=1.0, kind="physical",
        target=TargetType.ALL_ENEMIES, description="Zara looses a volley of arrows across the whole enemy line.",
    ),
    "piercing_barrage": Skill(
        id="piercing_barrage", name="Piercing Barrage", mp_cost=8, power=1.7, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="def_down", status_chance=0.25,
        description="Zara fires a barrage that punches straight through the target's guard.",
    ),
    "arrow_storm": Skill(
        id="arrow_storm", name="Arrow Storm", mp_cost=11, power=1.2, kind="physical",
        target=TargetType.ALL_ENEMIES, status_to_apply="poison", status_chance=0.3,
        description="Finn rains poisoned arrows down on the whole enemy line.",
    ),
    "longshot": Skill(
        id="longshot", name="Longshot", mp_cost=9, power=2.0, kind="physical",
        target=TargetType.SINGLE_ENEMY, description="Finn lines up an impossible shot and lands it anyway.",
    ),
    "rain_of_arrows": Skill(
        id="rain_of_arrows", name="Rain of Arrows", mp_cost=12, power=1.4, kind="physical",
        target=TargetType.ALL_ENEMIES, description="Rook drops a punishing rain of arrows on every enemy at once.",
    ),
    "piercing_fang": Skill(
        id="piercing_fang", name="Piercing Fang", mp_cost=9, power=2.1, kind="physical",
        target=TargetType.SINGLE_ENEMY, status_to_apply="def_down", status_chance=0.35,
        description="Rook's shot punches clean through, leaving the target's armor worse for it.",
    ),

    # mage (replace the shared "ice_lance" and "thunderbolt" slots)
    "frost_bite": Skill(
        id="frost_bite", name="Frost Bite", mp_cost=5, power=1.2, kind="magical", element=Element.ICE,
        target=TargetType.SINGLE_ENEMY, description="Ignis bites the target with a quick shard of frost.",
    ),
    "static_shock": Skill(
        id="static_shock", name="Static Shock", mp_cost=6, power=1.3, kind="magical", element=Element.THUNDER,
        target=TargetType.SINGLE_ENEMY, status_to_apply="stun", status_chance=0.15,
        description="Ignis zaps the target with a jolt that may lock it up.",
    ),
    "ice_shard": Skill(
        id="ice_shard", name="Ice Shard", mp_cost=7, power=1.4, kind="magical", element=Element.ICE,
        target=TargetType.SINGLE_ENEMY, status_to_apply="def_down", status_chance=0.25,
        description="Wren drives a shard of ice into the target, chilling its defenses.",
    ),
    "chain_lightning": Skill(
        id="chain_lightning", name="Chain Lightning", mp_cost=9, power=1.0, kind="magical", element=Element.THUNDER,
        target=TargetType.ALL_ENEMIES, description="Wren arcs lightning from one enemy to the next.",
    ),
    "glacial_spike": Skill(
        id="glacial_spike", name="Glacial Spike", mp_cost=8, power=1.6, kind="magical", element=Element.ICE,
        target=TargetType.SINGLE_ENEMY, description="Solene impales the target on a spike of solid ice.",
    ),
    "storm_call": Skill(
        id="storm_call", name="Storm Call", mp_cost=10, power=1.1, kind="magical", element=Element.THUNDER,
        target=TargetType.ALL_ENEMIES, status_to_apply="stun", status_chance=0.15,
        description="Solene calls down a storm that may stun every enemy it strikes.",
    ),
    "absolute_zero": Skill(
        id="absolute_zero", name="Absolute Zero", mp_cost=10, power=1.9, kind="magical", element=Element.ICE,
        target=TargetType.SINGLE_ENEMY, status_to_apply="def_down", status_chance=0.3,
        description="Kade drops the target's temperature past what it can withstand, cracking its defenses.",
    ),
    "thunder_judgment": Skill(
        id="thunder_judgment", name="Thunder Judgment", mp_cost=13, power=1.3, kind="magical", element=Element.THUNDER,
        target=TargetType.ALL_ENEMIES, status_to_apply="stun", status_chance=0.2,
        description="Kade calls down judgment on every enemy at once, sometimes stunning them outright.",
    ),
    "absolute_frost": Skill(
        id="absolute_frost", name="Absolute Frost", mp_cost=11, power=2.0, kind="magical", element=Element.ICE,
        target=TargetType.SINGLE_ENEMY, status_to_apply="def_down", status_chance=0.35,
        description="Lyra freezes the target solid, shattering its defenses in the process.",
    ),
    "tempest": Skill(
        id="tempest", name="Tempest", mp_cost=14, power=1.4, kind="magical", element=Element.THUNDER,
        target=TargetType.ALL_ENEMIES, status_to_apply="stun", status_chance=0.25,
        description="Lyra conjures a raging storm over the whole enemy line, stunning what it catches.",
    ),

    # support (replace the shared "greater_heal" and "prayer" slots)
    "soothing_touch": Skill(
        id="soothing_touch", name="Soothing Touch", mp_cost=5, power=1.1, kind="heal",
        target=TargetType.SINGLE_ALLY, status_to_apply="regen", status_chance=1.0,
        description="Elowen's touch heals an ally now and keeps mending them for a while after.",
    ),
    "gentle_wave": Skill(
        id="gentle_wave", name="Gentle Wave", mp_cost=8, power=0.8, kind="heal",
        target=TargetType.ALL_ALLIES, description="Elowen sends a gentle wave of healing over the whole party.",
    ),
    "purify": Skill(
        id="purify", name="Purify", mp_cost=7, power=1.2, kind="heal",
        target=TargetType.SINGLE_ALLY, status_to_apply="def_up", status_chance=0.5,
        description="Dassin's light heals an ally and may leave them steadier on their feet.",
    ),
    "circle_of_care": Skill(
        id="circle_of_care", name="Circle of Care", mp_cost=10, power=0.9, kind="heal",
        target=TargetType.ALL_ALLIES, description="Dassin draws the whole party into a healing circle.",
    ),
    "radiant_touch": Skill(
        id="radiant_touch", name="Radiant Touch", mp_cost=9, power=1.6, kind="heal",
        target=TargetType.SINGLE_ALLY, description="Mira's touch pours a large amount of healing into one ally.",
    ),
    "sanctuary": Skill(
        id="sanctuary", name="Sanctuary", mp_cost=11, power=1.0, kind="heal",
        target=TargetType.ALL_ALLIES, status_to_apply="def_up", status_chance=0.3,
        description="Mira surrounds the party in a ward that heals and may bolster everyone's defense.",
    ),
    "lifebinder": Skill(
        id="lifebinder", name="Lifebinder", mp_cost=11, power=1.9, kind="heal",
        target=TargetType.SINGLE_ALLY, status_to_apply="regen", status_chance=1.0,
        description="Osric binds an ally's life force back together, healing them now and over time.",
    ),
    "hymn_of_mercy": Skill(
        id="hymn_of_mercy", name="Hymn of Mercy", mp_cost=13, power=1.1, kind="heal",
        target=TargetType.ALL_ALLIES, status_to_apply="regen", status_chance=0.5,
        description="Osric sings a hymn that heals the party and may keep mending them afterward.",
    ),
    "divine_touch": Skill(
        id="divine_touch", name="Divine Touch", mp_cost=11, power=2.1, kind="heal",
        target=TargetType.SINGLE_ALLY, status_to_apply="regen", status_chance=1.0,
        description="Miya's touch pours a huge amount of healing into one ally, then keeps mending them.",
    ),
    "aura_of_life": Skill(
        id="aura_of_life", name="Aura of Life", mp_cost=14, power=1.2, kind="heal",
        target=TargetType.ALL_ALLIES, status_to_apply="def_up", status_chance=0.4,
        description="Miya wreathes the party in an aura that heals everyone and shores up their defenses.",
    ),
}

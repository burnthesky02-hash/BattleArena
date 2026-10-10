"""Damage, hit, crit, and flee math. Kept separate from battle.py so the
numbers can be tuned/tested in isolation.
"""
import random
from dataclasses import dataclass
from engine.combatant import Combatant
from engine.types import Element
import engine.formation as formation

VARIANCE = 0.15          # damage roll varies +/- this fraction
BASE_CRIT_CHANCE = 0.05  # at 0 luk
CRIT_MULTIPLIER = 1.75
MIN_DAMAGE = 1


# Optional debug hook: when set to a callable(str), every damage/heal roll
# reports its full calculation through it (hub_server's Battle Debug turns
# this on). None = zero overhead beyond one check.
calc_hook = None


def _report(text: str) -> None:
    if calc_hook:
        try:
            calc_hook(text)
        except Exception:
            pass


@dataclass
class DamageResult:
    amount: int
    crit: bool
    element: Element
    missed: bool = False


def _crit_chance(attacker: Combatant) -> float:
    # Every 10 LUK adds ~2% crit chance, soft-capped at 50%.
    return min(0.5, BASE_CRIT_CHANCE + attacker.effective_stat("luk") * 0.002)


def _elemental_multiplier(defender: Combatant, element: Element) -> float:
    if element in (Element.NONE, Element.PHYSICAL):
        return 1.0
    return defender.resistances.get(element, 1.0)


def physical_damage(attacker: Combatant, defender: Combatant, power: float = 1.0) -> DamageResult:
    atk = attacker.effective_stat("atk")
    df = defender.effective_stat("def_")
    if defender.defending:
        df *= 1.5
    raw = max(MIN_DAMAGE, (atk * power) - (df * 0.5)) * getattr(attacker, "power_mult", 1.0)
    roll = random.uniform(1 - VARIANCE, 1 + VARIANCE)
    base = raw * roll
    crit_chance = _crit_chance(attacker)
    crit = random.random() < crit_chance
    if crit:
        base *= CRIT_MULTIPLIER
    mult = _elemental_multiplier(defender, Element.PHYSICAL)
    row_dealt = formation.damage_dealt_multiplier(attacker.formation)
    row_taken = formation.damage_taken_multiplier(defender.formation)
    amount = max(MIN_DAMAGE, round(base * mult * row_dealt * row_taken))
    if calc_hook:
        _report(f"[calc] PHYS {attacker.name} ATK {atk} x power {power:g} = {atk * power:.1f}"
                f" - {defender.name} DEF {df:g}{' (defending x1.5)' if defender.defending else ''} x0.5 = {df * 0.5:.1f}"
                f" -> {raw:.1f} | roll x{roll:.2f} | crit {crit_chance:.0%}: {'YES x' + str(CRIT_MULTIPLIER) if crit else 'no'}"
                f" | elem x{mult:g} | row dealt x{row_dealt:g} ({attacker.formation}) taken x{row_taken:g} ({defender.formation})"
                f" => {amount}")
    return DamageResult(amount=amount, crit=crit, element=Element.PHYSICAL)


def magical_damage(attacker: Combatant, defender: Combatant, power: float, element: Element) -> DamageResult:
    mag = attacker.effective_stat("mag")
    res = defender.effective_stat("res")
    if defender.defending:
        res *= 1.5
    raw = max(MIN_DAMAGE, (mag * power) - (res * 0.5)) * getattr(attacker, "power_mult", 1.0)
    roll = random.uniform(1 - VARIANCE, 1 + VARIANCE)
    base = raw * roll
    crit_chance = _crit_chance(attacker) * 0.6   # spells crit a bit less often
    crit = random.random() < crit_chance
    if crit:
        base *= CRIT_MULTIPLIER
    mult = _elemental_multiplier(defender, element)
    row_dealt = formation.damage_dealt_multiplier(attacker.formation)
    row_taken = formation.damage_taken_multiplier(defender.formation)
    amount = max(MIN_DAMAGE if mult > 0 else 0, round(base * mult * row_dealt * row_taken))
    if calc_hook:
        _report(f"[calc] MAGIC {attacker.name} MAG {mag} x power {power:g} = {mag * power:.1f}"
                f" - {defender.name} RES {res:g}{' (defending x1.5)' if defender.defending else ''} x0.5 = {res * 0.5:.1f}"
                f" -> {raw:.1f} | roll x{roll:.2f} | crit {crit_chance:.0%}: {'YES x' + str(CRIT_MULTIPLIER) if crit else 'no'}"
                f" | {element.name} x{mult:g} | row dealt x{row_dealt:g} ({attacker.formation}) taken x{row_taken:g} ({defender.formation})"
                f" => {amount}")
    return DamageResult(amount=amount, crit=crit, element=element)


def heal_amount(caster: Combatant, power: float) -> int:
    mag = caster.effective_stat("mag")
    roll = random.uniform(1 - VARIANCE, 1 + VARIANCE)
    row_given = formation.healing_given_multiplier(caster.formation)
    amount = max(1, round(mag * power * getattr(caster, "power_mult", 1.0) * roll * row_given))
    if calc_hook:
        _report(f"[calc] HEAL {caster.name} MAG {mag} x power {power:g} = {mag * power:.1f} | roll x{roll:.2f}"
                f" | row x{row_given:g} ({caster.formation}) => {amount}")
    return amount


def flee_chance(fleeing_side_avg_spd: float, other_side_avg_spd: float) -> float:
    diff = fleeing_side_avg_spd - other_side_avg_spd
    return min(0.9, max(0.1, 0.5 + diff * 0.01))

"""Ladder Mode: a run of back-to-back battles where you may only cash out after every third win, and every
win lets you pick one of three random perks. Perks last for the run (they are dropped when the run ends).

Pure logic over the battle-time hero Combatants -- no networking. `LadderRun` holds the run's state; the hub
server (hub_server.run_battle) drives it.
"""
import random
from typing import Dict, List, Optional

from engine.status_effects import get_status

CASH_OUT_EVERY = 3        # cash out only after wins 3, 6, 9, ...
REWARD_BONUS = 1.25       # ladder pays +25% on top of the normal win-streak multiplier
CHOICES = 3

# id -> definition. `kind`: "instant" (applied once when picked) | "stat" (permanent for the run, stacks)
# | "passive" (a unique on-hit / start-of-battle effect). `weight` skews the random draw.
# `icon` = [row, col] on Icons.png.
PERKS: Dict[str, dict] = {
    "revive":      dict(name="Second Chance", kind="instant", weight=6, icon=[7, 1],
                        desc="Revive a fallen ally with full HP and MP."),
    "heal_half":   dict(name="Field Medic", kind="instant", weight=10, icon=[0, 0],
                        desc="Heal every living ally for 50% of their max HP."),
    "full_heal":   dict(name="Divine Blessing", kind="instant", weight=3, icon=[8, 4],
                        desc="Fully heal every living ally."),
    "full_mp":     dict(name="Mana Surge", kind="instant", weight=8, icon=[0, 1],
                        desc="Fully restore every living ally's MP."),
    "atk_up":      dict(name="Warrior's Might", kind="stat", weight=10, icon=[0, 2], stat="atk", pct=0.15,
                        desc="+15% ATK for the rest of the run. Stacks."),
    "def_up":      dict(name="Iron Skin", kind="stat", weight=10, icon=[0, 4], stat="def_", pct=0.15,
                        desc="+15% DEF for the rest of the run. Stacks."),
    "mag_up":      dict(name="Arcane Focus", kind="stat", weight=8, icon=[1, 5], stat="mag", pct=0.15,
                        desc="+15% MAG for the rest of the run. Stacks."),
    "res_up":      dict(name="Warding Charm", kind="stat", weight=7, icon=[2, 0], stat="res", pct=0.15,
                        desc="+15% RES for the rest of the run. Stacks."),
    "spd_up":      dict(name="Quickened", kind="stat", weight=7, icon=[1, 7], stat="spd", pct=0.12,
                        desc="+12% SPD for the rest of the run. Stacks."),
    "vitality":    dict(name="Vitality", kind="stat", weight=8, icon=[8, 4], stat="max_hp", pct=0.15,
                        desc="+15% max HP (and heals that much) for the run. Stacks."),
    "lucky":       dict(name="Four-Leaf Clover", kind="stat", weight=5, icon=[0, 5], stat="luk", flat=20,
                        desc="+20 LUK (crit chance) for the run. Stacks."),
    "poison_touch": dict(name="Venomous Strikes", kind="passive", weight=6, icon=[9, 1], unique=True,
                         desc="Your attacks have a 35% chance to poison the enemies they hit."),
    "vampiric":    dict(name="Vampiric Edge", kind="passive", weight=6, icon=[2, 9], unique=True,
                        desc="Heroes heal for 12% of the damage they deal."),
    "regen_start": dict(name="Second Wind", kind="passive", weight=6, icon=[7, 4], unique=True,
                        desc="Heroes begin every battle with Regen."),
    "battle_ready": dict(name="Battle Ready", kind="passive", weight=6, icon=[12, 3], unique=True,
                         desc="Heroes begin every battle with Attack Up and Defense Up."),
}

POISON_CHANCE = 0.35
LIFESTEAL = 0.12


class LadderRun:
    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()
        self.wins = 0
        self.perks: Dict[str, int] = {}      # perk id -> times taken
        self.offer: List[str] = []           # the current 3 choices (empty when none pending)

    # ---- cash-out rule ------------------------------------------------
    def can_cash_out(self) -> bool:
        return self.wins > 0 and self.wins % CASH_OUT_EVERY == 0

    def wins_until_cash_out(self) -> int:
        return 0 if self.can_cash_out() else CASH_OUT_EVERY - (self.wins % CASH_OUT_EVERY)

    def reward_multiplier(self, streak_multiplier: float) -> float:
        return streak_multiplier * REWARD_BONUS

    # ---- perk offers --------------------------------------------------
    def eligible(self, heroes) -> List[str]:
        out = []
        for pid, p in PERKS.items():
            if p.get("unique") and pid in self.perks:
                continue
            if pid == "revive" and not any(not h.alive for h in heroes):
                continue
            out.append(pid)
        return out

    def draw(self, heroes) -> List[dict]:
        pool = self.eligible(heroes)
        picks: List[str] = []
        while pool and len(picks) < CHOICES:
            pid = self.rng.choices(pool, weights=[PERKS[p]["weight"] for p in pool], k=1)[0]
            picks.append(pid)
            pool.remove(pid)
        self.offer = picks
        return [self.describe(p) for p in picks]

    @staticmethod
    def describe(pid: str) -> dict:
        p = PERKS[pid]
        return {"id": pid, "name": p["name"], "desc": p["desc"], "icon": p["icon"], "kind": p["kind"]}

    def summary(self) -> List[dict]:
        return [{**self.describe(pid), "count": n} for pid, n in self.perks.items()
                if PERKS[pid]["kind"] != "instant"]

    # ---- applying -----------------------------------------------------
    def pick(self, pid: str, heroes) -> Optional[str]:
        """Applies a perk from the current offer; returns a message, or None if it isn't on offer."""
        if pid not in self.offer:
            return None
        self.offer = []
        p = PERKS[pid]
        living = [h for h in heroes if h.alive]
        if p["kind"] != "instant":
            self.perks[pid] = self.perks.get(pid, 0) + 1
        if pid == "revive":
            dead = [h for h in heroes if not h.alive]
            if not dead:
                return "Second Chance fizzles: nobody has fallen."
            h = dead[0]
            h.revive(h.max_hp); h.mp = h.max_mp; h.clear_all_status()
            return f"{h.name} rises again at full strength!"
        if pid == "heal_half":
            for h in living:
                h.heal(h.max_hp // 2)
            return "Everyone recovers half their HP."
        if pid == "full_heal":
            for h in living:
                h.heal(h.max_hp)
            return "Everyone is fully healed."
        if pid == "full_mp":
            for h in living:
                h.restore_mp(h.max_mp)
            return "Everyone's MP is restored."
        if p["kind"] == "stat":
            for h in heroes:
                self._boost(h, p)
            return f"{p['name']}: the whole party grows stronger."
        return f"{p['name']} acquired."

    @staticmethod
    def _boost(h, p) -> None:
        stat = p["stat"]
        cur = getattr(h.base_stats, stat)
        add = p.get("flat") or max(1, round(cur * p["pct"]))
        setattr(h.base_stats, stat, cur + add)
        if stat == "max_hp" and h.alive:
            h.hp += add                                   # the new HP arrives filled

    # ---- run-long passives --------------------------------------------
    def on_battle_start(self, heroes) -> None:
        for h in heroes:
            if not h.alive:
                continue
            if "regen_start" in self.perks:
                h.add_status(get_status("regen"))
            if "battle_ready" in self.perks:
                h.add_status(get_status("atk_up")); h.add_status(get_status("def_up"))

    def after_hero_action(self, actor, foes, before_hp: dict, dealt: int) -> List[str]:
        """After a hero acts: venom on the foes it hurt, and lifesteal. Returns log lines."""
        lines = []
        if dealt <= 0:
            return lines
        if "poison_touch" in self.perks:
            for f in foes:
                if f.alive and f.hp < before_hp.get(f.id, f.hp) and self.rng.random() < POISON_CHANCE:
                    f.add_status(get_status("poison"))
                    lines.append(f"  {f.name} is poisoned by {actor.name}'s venom!")
        if "vampiric" in self.perks and actor.alive:
            healed = actor.heal(max(1, round(dealt * LIFESTEAL)))
            if healed:
                lines.append(f"  {actor.name} drains {healed} HP.")
        return lines

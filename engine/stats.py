"""Base stat block shared by every combatant (party member or enemy)."""
from dataclasses import dataclass


@dataclass
class Stats:
    """Base (unbuffed) stats. HP/MP current values live on Combatant, not here."""
    max_hp: int
    max_mp: int
    atk: int      # physical attack power
    def_: int     # physical defense
    mag: int      # magic attack power
    res: int      # magic defense / resistance
    spd: int      # turn-order speed
    luk: int = 10  # crit chance / status-resist / flee-chance influence

    def copy(self) -> "Stats":
        return Stats(self.max_hp, self.max_mp, self.atk, self.def_, self.mag, self.res, self.spd, self.luk)

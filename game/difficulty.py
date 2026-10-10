"""Game-wide difficulty (chosen on New Game, changeable from the Settings menu while in town).
Easy: enemies half as tough, rewards x0.75.  Normal: unchanged.  Hard: enemies 1.5x as tough, rewards x1.5.
Not to be confused with game/battle_setup.py's DIFFICULTY_IDS, which is the old Colosseum per-fight picker."""

GAME_DIFFICULTIES = ("easy", "normal", "hard")
DEFAULT_DIFFICULTY = "normal"
ENEMY_MULT = {"easy": 0.5, "normal": 1.0, "hard": 1.5}      # applied to every enemy's max HP, ATK and MAG
REWARD_MULT = {"easy": 0.75, "normal": 1.0, "hard": 1.5}    # gold, gems and XP from battles
SCALED_STATS = ("max_hp", "atk", "mag")


def clean(value) -> str:
    return value if value in GAME_DIFFICULTIES else DEFAULT_DIFFICULTY


def apply_to_setup(setup, difficulty: str) -> None:
    """Scale the enemies of a freshly built BattleSetup (once -- the flag stops a second pass)."""
    m = ENEMY_MULT.get(clean(difficulty), 1.0)
    if m == 1.0 or getattr(setup, "_game_diff_done", False):
        setup._game_diff_done = True
        return
    setup._game_diff_done = True
    for e in setup.enemies:
        st = e.base_stats
        for name in SCALED_STATS:
            setattr(st, name, max(1, round(getattr(st, name) * m)))
        e.hp = st.max_hp


def scale_rewards(win: dict, difficulty: str) -> dict:
    m = REWARD_MULT.get(clean(difficulty), 1.0)
    if m != 1.0:
        for k in ("money", "gems", "xp"):
            if win.get(k):
                win[k] = round(win[k] * m)
    return win

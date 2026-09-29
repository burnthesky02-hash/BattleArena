# The battle screen: real HTML replacement, take one

This is the first *real* (not throwaway) piece of the full pygame -> HTML
migration -- chosen to go first because it's the hardest and riskiest part
(sprite rendering, animation, and click-to-target in a browser instead of
pygame's draw calls). Unlike the two earlier comparisons (Unity, then HTML,
for the Summon screen), nothing here is disposable: `battle_server.py` runs
your actual `BattleEngine`, `game/battle_setup.py`, and `ai/enemy_ai.py`
unmodified.

## Run it

New dependency:
```
pip install websockets
```

Then from the project root:
```
python battle_server.py
```
Open **http://127.0.0.1:8765/**. A battle starts automatically against a
fixed demo party (one of each class, level 1) and a real
`build_battle("normal", 2)` encounter -- real random enemy/hero-rival draw,
real difficulty/level math, real Ollama-driven enemy AI (falls back to the
scripted AI exactly like the pygame version does if Ollama isn't reachable).

For the "own window" version: `pip install pywebview`, then
`python html_battle/run_desktop.py`.

## What's real vs. not yet

**Real:** the engine, the battle setup/enemy selection, the enemy AI
(including the live "thinking" text you're used to from debug mode), turn
order, damage/status formulas, the actual sprite sheets and background art
from `data/Battlers`/`data/Artwork`, the ground-standing two-rank formation
(same numbers as fix #21/#22), melee run-in/swing/run-back, click-to-target
on sprites, and translucent panels.

**Not yet, on purpose** -- this is the battle screen only, per the agreed
build order (battle screen first since it's hardest, then hub, shop, real
Summon, heroes, party select, battle setup):
- No title screen, character creation, save/load, or Colosseum hub. Every
  run fights the same fixed demo party -- nothing here reads or writes
  `saves/save1.json`.
- No money/gems/XP rewards.
- No Party Select / Battle Setup screens (difficulty and opponent count are
  hardcoded in `battle_server.py` -- `DEMO_DIFFICULTY`/`DEMO_NUM_ENEMIES`).
- Melee timing is a first pass: the run-in/swing/run-back animation plays,
  but the HP-bar update currently lands whenever the "state" message
  arrives (right after the swing starts), not necessarily synced to the
  visual "impact" frame the way fix #19's `BATTLE_MELEE_IMPACT_FRACTION`
  timed it in pygame. Worth tightening once you've seen it play.
- Only Draven (and Yulia's Idle-only) have real art, so almost everything
  you see will be Draven's placeholder sheet via the same fallback chain
  the pygame build used -- expected, not a bug.

## On `ui/pygame_ui.py`

You said to rip it out and commit fully -- here's the honest state of that:
I haven't touched or deleted it. Two real constraints:

1. **I can't delete or rename files on your machine from here** -- the file
   tools available to this session can create/overwrite files in your
   connected folder, but not move or delete them (that needs a shell on
   your machine, which this Windows setup doesn't expose to me). So even if
   I wanted to remove it outright right now, I mechanically can't -- you'd
   need to delete `ui/pygame_ui.py` (and its dedicated test files:
   `heroes_screen_test.py`, `summon_screen_test.py`, `battle_sprites_test.py`,
   `party_select_screen_test.py`, `pygame_ui_smoke_test.py`,
   `meta_screens_test.py`, `shop_screen_test.py`) yourself in File Explorer,
   or the whole test suite will start erroring on missing coverage of a
   file that still exists.
2. **`main.py` still uses it** -- your actual playable game (title, hub,
   shop, summon, heroes, party select, battle) all still runs through
   `ui/pygame_ui.py` today, because none of those screens have a real HTML
   replacement yet. Deleting it right now, even if I could, would leave you
   with no working game outside this one standalone battle demo.

What "committing fully" means in practice, given that: I'm not going to put
any more work into `ui/pygame_ui.py` from here on -- no more fixes, no more
polish, it's frozen. Once every screen has a real HTML replacement and
`main.py` is rewired to use only those, `ui/pygame_ui.py` and its tests
become genuinely dead code, and deleting them (by you, or by a future
session if a machine with shell access is used) is a clean, safe step at
that point -- not before.

## Next up

Per the agreed order: the Colosseum hub (title/new game/character creation
folded in, since that's the natural entry point) is next, then Shop, then
a real Summon screen (replacing the earlier throwaway comparison with one
wired the same way this battle screen is -- into your real save data this
time), then Heroes, then Party Select, then Battle Setup -- at which point
`main.py` gets rewritten to call into the web UI for the whole loop and
`ui/pygame_ui.py` is ready to actually remove.

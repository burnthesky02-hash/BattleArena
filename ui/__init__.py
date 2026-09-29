"""UI layer. Two renderers/input-sources are provided:

- text_ui.TextUI:   zero dependencies, runs in any terminal. This is the
                     fastest way to actually play a battle right now, and
                     it's also what the automated tests drive headlessly.
- pygame_ui.PygameUI: a graphical placeholder -- colored rectangles standing
                     in for sprites, HP/MP bars, a click-driven action menu.
                     Swap in real art later without touching engine/ or ai/.

Both expose the same shape: a callable usable as BattleEngine.get_party_action,
plus a way to display log lines/results as the battle progresses.
"""

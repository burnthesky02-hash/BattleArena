"""Runtime configuration. Values here can be overridden by CLI flags in main.py
or by environment variables.
"""
import os

# --debug on the CLI overrides this; DEBUG=1 (or true/yes) as an env var sets
# the default without needing the flag every run.
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")

# How many gems the debug-only "Add Gems" hub button grants per click (see
# ui/pygame_ui.py's/ui/text_ui.py's show_colosseum_hub and main.py's
# "debug_add_gems" handling). Only ever offered when --debug/DEBUG=1 is on --
# this exists purely to let Summon's gacha pulls be tested/spammed without
# grinding out real battle rewards first. 100 comfortably covers a handful of
# character summons (30 gems each) or equipment summons (15 each) per click.
DEBUG_GEM_GRANT = int(os.environ.get("DEBUG_GEM_GRANT", "100"))

# Whether the pygame window launches fullscreen (scaled up to fill the real
# monitor -- see ui/pygame_ui.py's PygameUI.__init__) instead of the default
# windowed mode. Off by default: the window itself got noticeably bigger
# (see ui/pygame_ui.py's WIDTH/HEIGHT) as its own fix for "the window feels
# small," and fullscreen is a bigger, more opinionated change (takes over
# the whole screen, no window chrome) that's better left opt-in than forced
# on everyone. --fullscreen on the CLI overrides this without needing the
# env var every run.
FULLSCREEN_ON_START = os.environ.get("FULLSCREEN_ON_START", "").lower() in ("1", "true", "yes")

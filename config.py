"""Runtime configuration. Values here can be overridden by CLI flags in main.py
or by environment variables, so nothing about Ollama's location is hardcoded
deep in the AI module.
"""
import os

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")
# This is the timeout for an already-warm in-battle turn, NOT for the initial
# model load (see WARM_UP_ON_START / OllamaClient.warm_up, which uses its own
# much longer timeout for that). Larger local models (13B+, and especially
# 27B-class ones like gemma3:27b) can still take a while per response on CPU
# or under a big prompt -- 90s is a safer default than a quick 20s. Raise it
# further with OLLAMA_TIMEOUT_SECONDS if turns still time out after warm-up.
OLLAMA_TIMEOUT_SECONDS = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "90"))

# Speed levers, both passed straight through to Ollama on every request:
# - num_predict caps how many tokens a reply can generate. Our prompt only
#   needs a short sentence plus a small JSON object, so a model that would
#   otherwise ramble on gets cut off well before it wastes real time doing
#   so. Lower this for snappier (but more truncation-risk) turns.
# - keep_alive tells Ollama how long to keep the model loaded in memory
#   after a request. Without this, Ollama's own default (a few minutes) can
#   let a big model get unloaded between a human player's slower turns and
#   the next enemy turn, so the enemy turn eats a full reload -- which is
#   what "stuck at waiting for first token" usually is for large models: not
#   actually stuck, just still loading. "30m" keeps it warm for essentially
#   any normal play session.
OLLAMA_NUM_PREDICT = int(os.environ.get("OLLAMA_NUM_PREDICT", "200"))
OLLAMA_KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "30m")

# Whether to force-load the model into memory at startup (before the battle
# begins) rather than letting the first enemy turn pay that cost mid-battle.
# See OllamaClient.warm_up for why this matters for large models. Set to
# "0"/"false" to skip it (e.g. if you know the model is already warm from a
# previous run and don't want to wait again).
WARM_UP_ON_START = os.environ.get("WARM_UP_ON_START", "1").lower() not in ("0", "false", "no")

# If the LLM call fails, is unreachable, times out, or returns something we
# can't parse, we fall back to a scripted heuristic AI rather than crashing
# or stalling the battle.
AI_FALLBACK_ON_ERROR = True

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

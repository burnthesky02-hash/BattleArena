"""Core battle engine: data model, formulas, and turn/round orchestration.

This package is intentionally UI-agnostic. Nothing in here imports pygame
or does console I/O — it just holds game state and exposes functions that
mutate/query it. That's what lets the whole engine be exercised headlessly
in tests, and driven by either the text UI or the pygame UI.
"""

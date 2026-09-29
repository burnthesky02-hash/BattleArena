"""Local-LLM integration: a thin Ollama client plus the enemy "tactician"
logic that turns battle state into an Action. Nothing in engine/ depends on
this package -- the dependency runs the other way, via callables the engine
is handed at construction time.
"""

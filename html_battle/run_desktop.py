"""Runs the real HTML battle screen as its own desktop window instead of a
browser tab -- same pattern as html_prototype/run_desktop.py, pointed at
battle_server.py instead.

Needs:
    pip install websockets pywebview

Run from the Battle Arena project root:
    python html_battle/run_desktop.py
"""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import battle_server

try:
    import webview
except ImportError:
    print("Missing dependency. Run this first:\n    pip install pywebview")
    sys.exit(1)


def main():
    ollama_client = battle_server.OllamaClient(
        host=battle_server.config.OLLAMA_HOST, model=battle_server.config.OLLAMA_MODEL,
        timeout=battle_server.config.OLLAMA_TIMEOUT_SECONDS,
        num_predict=battle_server.config.OLLAMA_NUM_PREDICT, keep_alive=battle_server.config.OLLAMA_KEEP_ALIVE,
    )
    if not ollama_client.is_available():
        print(f"[warn] Could not reach Ollama at {battle_server.config.OLLAMA_HOST}. "
              f"Enemies will use the scripted fallback AI.")

    threading.Thread(target=battle_server.run_http_server, daemon=True).start()

    def run_ws():
        import asyncio
        asyncio.run(battle_server.run_ws_server(ollama_client))

    threading.Thread(target=run_ws, daemon=True).start()

    webview.create_window(
        "Battle Arena",
        f"http://{battle_server.HTTP_HOST}:{battle_server.HTTP_PORT}/",
        width=1280, height=800, resizable=True,
    )
    webview.start()


if __name__ == "__main__":
    main()

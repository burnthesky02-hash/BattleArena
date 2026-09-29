"""Runs the Summon prototype as its own desktop window instead of a browser
tab: starts summon_server.py's HTTP server on a background thread, then
opens a pywebview window pointed at it -- no address bar, tabs, or browser
chrome, just the page.

Needs the `pywebview` package (not in requirements.txt -- this is prototype
tooling, not part of the real game yet):
    pip install pywebview

Run from the Battle Arena project root:
    python html_prototype/run_desktop.py
"""
import sys
import threading
from pathlib import Path

# So `import summon_server` resolves regardless of the current working
# directory this script is launched from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import summon_server

try:
    import webview
except ImportError:
    print("Missing dependency. Run this first:\n    pip install pywebview")
    sys.exit(1)


def _serve_forever():
    server = summon_server.ThreadingHTTPServer(
        (summon_server.HOST, summon_server.PORT), summon_server.Handler
    )
    print(f"[run_desktop] Backend running on http://{summon_server.HOST}:{summon_server.PORT}")
    server.serve_forever()


def main():
    thread = threading.Thread(target=_serve_forever, daemon=True)
    thread.start()

    webview.create_window(
        "Battle Arena -- Summon (HTML prototype)",
        f"http://{summon_server.HOST}:{summon_server.PORT}/",
        width=1000,
        height=800,
        resizable=True,
    )
    webview.start()


if __name__ == "__main__":
    main()

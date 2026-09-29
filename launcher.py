"""Battle Arena launcher: starts the game server and opens the game in its own
app-style window (Edge/Chrome "--app" mode -- no tabs or address bar). When that
window is closed, the server shuts down.

    python launcher.py            normal
    python launcher.py --debug    enable Battle Debug / debug tools
    python launcher.py --browser  open in your normal browser instead of an app window

Also the entry point of the packaged .exe (see build_exe.bat). When frozen, saves
are kept in a "saves" folder next to the .exe.
"""
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import webbrowser

FROZEN = getattr(sys, "frozen", False)
APP_DIR = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("BATTLE_ARENA_HOME", APP_DIR)      # save_system.py keeps saves/ here
os.chdir(APP_DIR)
if not FROZEN:
    sys.path.insert(0, APP_DIR)

LOG_PATH = os.path.join(APP_DIR, "launcher.log")
URL = "http://127.0.0.1:8767/"
HTTP_PORT = 8767


def _redirect_output_if_headless() -> None:
    """pythonw / windowed exe have no console: stdout/stderr are None, and print() would crash."""
    if sys.stdout is None or sys.stderr is None or FROZEN:
        try:
            f = open(LOG_PATH, "w", buffering=1, encoding="utf-8")
            sys.stdout = sys.stderr = f
        except OSError:
            pass


def _message_box(title: str, text: str) -> None:
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)
    except Exception:
        print(f"{title}: {text}")


def _port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _find_app_browser():
    candidates = []
    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            candidates += [
                os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"),
                os.path.join(base, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            ]
    for name in ("msedge", "chrome", "google-chrome", "chromium"):
        p = shutil.which(name)
        if p:
            candidates.append(p)
    return next((c for c in candidates if os.path.isfile(c)), None)


def _open_window(use_browser: bool) -> None:
    """Waits for the server, opens the window, and exits the whole process when it's closed."""
    for _ in range(200):
        if _port_open(HTTP_PORT):
            break
        time.sleep(0.1)
    exe = None if use_browser else _find_app_browser()
    if not exe:
        print("[launcher] no Edge/Chrome app window available -- opening your default browser; "
              "close this program from the task manager / Ctrl+C when done.")
        webbrowser.open(URL)
        return
    profile = os.path.join(os.environ.get("LOCALAPPDATA", APP_DIR), "BattleArena", "window-profile")
    os.makedirs(profile, exist_ok=True)
    proc = subprocess.Popen([
        exe, f"--app={URL}", f"--user-data-dir={profile}", "--window-size=1366,820",
        "--no-first-run", "--no-default-browser-check",
    ])
    proc.wait()               # returns when the game window is closed
    time.sleep(0.5)
    print("[launcher] window closed -- shutting down.")
    os._exit(0)


def main() -> None:
    _redirect_output_if_headless()
    args = sys.argv[1:]
    use_browser = "--browser" in args
    sys.argv = [sys.argv[0]] + [a for a in args if a != "--browser"]   # hub_server has its own argparse

    if _port_open(HTTP_PORT):                       # server already running -> just open a window
        threading.Thread(target=_open_window, args=(use_browser,), daemon=True).start()
        while True:
            time.sleep(3600)
    try:
        import websockets  # noqa: F401
    except ImportError:
        _message_box("Battle Arena", "The 'websockets' package is missing.\n\nRun:  python -m pip install websockets")
        return
    import hub_server
    threading.Thread(target=_open_window, args=(use_browser,), daemon=True).start()
    hub_server.main()                               # blocks; serves pages + battle WebSocket


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception:
        _redirect_output_if_headless()
        err = traceback.format_exc()
        print(err)
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(err)
        except OSError:
            pass
        _message_box("Battle Arena crashed", err[-1500:] + f"\n\nSee {LOG_PATH}")

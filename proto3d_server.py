"""Tiny standalone server for the 2.5D prototypes.

Run from the project root:   python proto3d_server.py
  http://127.0.0.1:8770/        2.5D battle prototype   (html_battle/index3d.html)
  http://127.0.0.1:8770/forest  2.5D forest overworld   (html_overworld/index3d.html)

Touches nothing else in the game. It serves the prototype pages plus your existing art:
  /assets/...  -> data/... first, then Assets/...   (same URL layout hub_server.py uses)
  /data/...    -> data/...  (map + palette JSON)
"""
import mimetypes
import os
import threading
import urllib.parse
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

mimetypes.add_type("image/webp", ".webp")

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
ASSETS = os.path.join(ROOT, "Assets")
PAGES = {
    "/": os.path.join(ROOT, "html_battle", "index3d.html"),
    "/forest": os.path.join(ROOT, "html_overworld", "index3d.html"),
}
PORT = int(os.environ.get("PROTO3D_PORT", "8770"))


def resolve(base, rel):
    """Case-insensitive path lookup under base (the palettes say 'forest', the folder is 'Forest')."""
    cur = os.path.normpath(base)
    for part in [p for p in rel.replace("\\", "/").split("/") if p]:
        if part in (".", ".."):
            return None
        try:
            names = os.listdir(cur)
        except OSError:
            return None
        match = part if part in names else next((n for n in names if n.lower() == part.lower()), None)
        if match is None:
            return None
        cur = os.path.join(cur, match)
    return cur if os.path.isfile(cur) else None


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        p = urllib.parse.unquote(path.split("?", 1)[0]).rstrip("/") or "/"
        if p in PAGES:
            return PAGES[p]
        found = None
        if p.startswith("/assets/"):
            rel = p[len("/assets/"):]
            found = resolve(DATA, rel) or resolve(ASSETS, rel)
        elif p.startswith("/data/"):
            found = resolve(DATA, p[len("/data/"):])
        return found or os.path.join(ROOT, "__does_not_exist__")

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}/"
    print(f"2.5D prototypes running:\n  battle: {url}\n  forest: {url}forest\n(Ctrl+C to stop)")
    if not os.environ.get("PROTO3D_NO_BROWSER"):
        threading.Timer(0.6, lambda: webbrowser.open(url + "forest")).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass

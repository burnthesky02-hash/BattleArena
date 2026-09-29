"""Prototype-only local HTTP server exposing game/summon.py both as a JSON
API and as the HTML/CSS/JS Summon screen itself (html_prototype/index.html)
-- built to test whether a browser-tech UI delivers more visual polish than
pygame, now that the earlier Unity version didn't land. Same backend either
way: game/summon.py, data/summon_pool.py, data/hero_rarity.py are used
directly and unmodified, so the odds/rarities/shard math you see here is
exactly what your real game does.

This is NOT wired to your real save file on purpose: it builds a throwaway
PlayerState in memory, seeded with a huge pile of gems, so you can mash the
pull buttons without worrying about the economy or touching
saves/save1.json. Nothing here writes to disk. Stop the server (Ctrl+C) and
every pull is forgotten.

Run this from the Battle Arena project root, the same way you run main.py:
    python summon_server.py
Then open http://127.0.0.1:8765/ in a browser -- or, for the "own window"
feel, run html_prototype/run_desktop.py instead (it starts this same server
in the background and opens a pywebview window pointed at it, no browser
chrome/tabs/address bar visible).

Endpoints:
    GET  /                 -> serves html_prototype/index.html
    GET  /health
        -> {"ok": true}

    GET  /state
        -> {"gems": <int>, "roster_size": <int>,
            "costs": {"character_1x": 30, "character_10x": 300,
                      "equipment_1x": 15, "equipment_10x": 150}}

    POST /summon/character   body: {"count": 1}   (count must be 1 or 10)
        -> {"ok": true, "message": "...", "gems": <int>,
            "results": [
                {"rarity": "epic", "name": "Zara", "class_id": "ranged_dps",
                 "is_duplicate": false, "shards_gained": 0,
                 "message": "[Epic] Zara the Ranger joins your team!"},
                ...
            ]}

    POST /summon/equipment   body: {"count": 1}   (count must be 1 or 10)
        -> {"ok": true, "message": "...", "gems": <int>,
            "results": [
                {"rarity": "legendary", "name": "Flameheart Blade",
                 "slot": "weapon",
                 "message": "You summoned Flameheart Blade (legendary)! ..."},
                ...
            ]}

A failed pull (not enough gems -- shouldn't happen given the seeded amount,
but handled anyway) returns {"ok": false, "message": "...", "gems": <int>,
"results": []} with HTTP 200 -- Unity-side code checks the "ok" field, not
the status code, to keep the client simple.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# So `from game.summon import ...` etc. resolve when this file is run
# directly, exactly like main.py already relies on being run from the
# project root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from data.equipment_db import EQUIPMENT
from data.summon_pool import (
    CHARACTER_SUMMON_COST, CHARACTER_SUMMON_COST_X10,
    EQUIPMENT_SUMMON_COST, EQUIPMENT_SUMMON_COST_X10, SUMMON_X10_COUNT,
)
from game.player_state import PlayerState
from game.summon import summon_character_batch, summon_equipment_batch

HOST = "127.0.0.1"
PORT = 8765

INDEX_HTML_PATH = Path(__file__).resolve().parent / "html_prototype" / "index.html"

# A throwaway prototype PlayerState -- huge gem pile, empty roster, so every
# possible rarity/duplicate path can actually be exercised by just clicking
# repeatedly. Never saved to disk.
player_state = PlayerState(characters=[], money=0, gems=999_999, inventory={}, owned_equipment={})


def _character_results_json(results):
    return [
        {
            "rarity": r.rarity,
            "name": r.character.name,
            "class_id": r.character.class_id,
            "is_duplicate": r.is_duplicate,
            "shards_gained": r.shards_gained,
            "message": r.message,
        }
        for r in results
    ]


def _equipment_results_json(results):
    return [
        {
            "rarity": r.rarity,
            "name": r.item.name,
            "slot": r.item.slot,
            "message": r.message,
        }
        for r in results
    ]


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: int, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8")) if raw else {}

    def log_message(self, fmt, *args):  # quieter console output
        print("[summon_server]", fmt % args)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            try:
                html = INDEX_HTML_PATH.read_text(encoding="utf-8")
            except FileNotFoundError:
                self._send_json(500, {"ok": False, "message": f"missing {INDEX_HTML_PATH}"})
                return
            self._send_html(200, html)
        elif self.path == "/health":
            self._send_json(200, {"ok": True})
        elif self.path == "/state":
            self._send_json(200, {
                "gems": player_state.gems,
                "roster_size": len(player_state.characters),
                "costs": {
                    "character_1x": CHARACTER_SUMMON_COST,
                    "character_10x": CHARACTER_SUMMON_COST_X10,
                    "equipment_1x": EQUIPMENT_SUMMON_COST,
                    "equipment_10x": EQUIPMENT_SUMMON_COST_X10,
                },
            })
        else:
            self._send_json(404, {"ok": False, "message": f"no such route: {self.path}"})

    def do_POST(self):
        try:
            body = self._read_json_body()
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"ok": False, "message": "invalid JSON body", "gems": player_state.gems, "results": []})
            return

        count = body.get("count", 1)
        if count not in (1, SUMMON_X10_COUNT):
            self._send_json(400, {"ok": False, "message": f"count must be 1 or {SUMMON_X10_COUNT}", "gems": player_state.gems, "results": []})
            return

        if self.path == "/summon/character":
            ok, message, results = summon_character_batch(player_state, count)
            self._send_json(200, {"ok": ok, "message": message, "gems": player_state.gems,
                                   "results": _character_results_json(results) if ok else []})
        elif self.path == "/summon/equipment":
            ok, message, results = summon_equipment_batch(player_state, EQUIPMENT, count)
            self._send_json(200, {"ok": ok, "message": message, "gems": player_state.gems,
                                   "results": _equipment_results_json(results) if ok else []})
        else:
            self._send_json(404, {"ok": False, "message": f"no such route: {self.path}", "gems": player_state.gems, "results": []})


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[summon_server] Prototype Summon API running on http://{HOST}:{PORT}")
    print(f"[summon_server] Seeded with {player_state.gems} gems, empty roster. Nothing here touches your real save.")
    print("[summon_server] Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

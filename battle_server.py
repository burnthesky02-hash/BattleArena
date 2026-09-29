"""battle_server.py -- RETIRED. The battle screen now lives inside
hub_server.py, merged there along with the Colosseum hub, Heroes, and
Summon, so all of them share one real PlayerState/save file instead of
each loading their own in-memory copy (which is also what let battle
rewards finally start persisting to the save -- see hub_server.py's
module docstring for the full story).

This file is kept on disk only because this build environment can create
or overwrite files on your machine but can't delete or rename them -- it
is otherwise dead code from here on. Don't run it; it does nothing but
print this message and exit.

Run this instead, from the Battle Arena project root:
    python hub_server.py

That single process now serves the Colosseum hub, Heroes, Summon, AND the
battle screen (http://127.0.0.1:8767/, with /battle for the fight itself
and its own WebSocket on port 8766) -- see hub_server.py's docstring.

Once every remaining pygame-only screen (Party Select, Battle Setup) has
its own real HTML page and main.py is rewired to the web UI entirely, this
file (and ui/pygame_ui.py plus its test files, per that earlier note) can
finally be deleted for real, by you or by a future session with shell
access to this machine.
"""
import sys

if __name__ == "__main__":
    print(__doc__)
    sys.exit(1)

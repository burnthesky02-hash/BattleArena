"""One-off, idempotent patch (Oct 13): the Pit no longer frees the hero; Rook breaks him out at night and takes him to Outpost Kestrel.
Edits prison.json and asteroid.json in place via story_pit.apply_prison_escape / apply_asteroid_escape (keeps each file's own formatting).
Run from html_hub/3d:  python patch_rook_escape.py
prison.json and asteroid.json were last saved by the 3D builder, so they are patched directly; make_prison.py also calls apply_prison_escape,
make_asteroid.py is NOT hooked (its output differs from the saved asteroid.json), so re-run this script after any regeneration."""
import json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import story_pit

def patch(name, fn, **fmt):
    p = os.path.join(HERE, name)
    raw = open(p, encoding="utf-8", newline="").read()
    d = fn(json.loads(raw))
    out = json.dumps(d, **fmt["dump"])
    if fmt.get("crlf"): out = out.replace("\n", "\r\n")
    out += fmt.get("tail", "")
    bak = p.replace(".json", ".pre_rook_escape.json")
    if not os.path.exists(bak): shutil.copyfile(p, bak)
    open(p, "w", encoding="utf-8", newline="").write(out)
    print("patched", name)

patch("prison.json", story_pit.apply_prison_escape, dump=dict(indent=1, ensure_ascii=False), crlf=True, tail="\r\n")
patch("asteroid.json", story_pit.apply_asteroid_escape, dump=dict(separators=(",", ":"), ensure_ascii=False))

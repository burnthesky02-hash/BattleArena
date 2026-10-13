"""One-off, idempotent patch (Oct 13): Rook's explanation at Outpost Kestrel, the Vault lore, the living door, the Mind's betrayal and the new strange world.
Edits asteroid.json and vault.json in place (keeping each file's own formatting), writes strange.json, makes backups (*.pre_rook_vault.json).
Run from html_hub/3d:  python patch_rook_vault.py
vault.json / asteroid.json were last saved by tools whose output differs from make_vault.py / make_asteroid.py, so re-run this after any regeneration."""
import json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import story_rook_vault as S


def patch(name, fn, dump, crlf=False, tail=""):
    p = os.path.join(HERE, name)
    raw = open(p, encoding="utf-8", newline="").read()
    d = fn(json.loads(raw))
    out = json.dumps(d, ensure_ascii=False, **dump)
    if crlf: out = out.replace("\n", "\r\n")
    out += tail
    bak = p.replace(".json", ".pre_rook_vault.json")
    if not os.path.exists(bak): shutil.copyfile(p, bak)
    open(p, "w", encoding="utf-8", newline="").write(out)
    print("patched", name)


patch("asteroid.json", S.apply_asteroid_vault, dict(indent=1), crlf=True, tail="\r\n")
patch("vault.json", S.apply_vault_rook, dict(separators=(",", ":")))
# the world the Vault drops you into is built by make_dawnwatch.py (strange.json); this patch only edits the asteroid and the vault

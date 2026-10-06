"""builder3d_api.py -- backend helpers for the 2.5D scene editor (html_builder/index3d.html, served at /builder3d).

Pure functions (no globals, no server state) so hub_server.py only has to route to them:
  list_scenes(hub3d_dir, maps_dir)  -> [{id, name, kind}]   hub scenes = html_hub/3d/<id>.json, battle maps = html_battle/maps/<id>.json
  list_music(music_dir)             -> [{url, name, folder, intro?}] tracks under Assets/Music (intro/loop pairs merged)
  list_models(assets3d_dir)         -> [{url, name, folder}] every .glb under Assets/3D, as /assets/3D/... URLs
  save_scene(kind, scene_id, data, hub3d_dir, maps_dir, backup_dir) -> {ok, path} | {ok: False, error}
Saves keep the previous file as a timestamped backup (last 15 per scene) so a bad edit is never destructive."""
import json
import re
import time
from pathlib import Path

SLUG = re.compile(r"^[a-z0-9][a-z0-9_\-]{0,47}$")
NOT_HUB_SCENES = {"sprites", "quests", "sidequests", "stills"}                  # html_hub/3d/*.json files that are not scenes
MAX_BYTES = 3_000_000
KINDS = ("hub", "battle")


def _scene_name(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return str(data.get("name") or path.stem) if isinstance(data, dict) else path.stem
    except (OSError, ValueError):
        return path.stem


def list_scenes(hub3d_dir: Path, maps_dir: Path) -> list:
    out = []
    if hub3d_dir.is_dir():
        for p in sorted(hub3d_dir.glob("*.json")):
            if p.stem not in NOT_HUB_SCENES:
                out.append({"id": p.stem, "name": _scene_name(p), "kind": "hub"})
    if maps_dir.is_dir():
        for p in sorted(maps_dir.glob("*.json")):
            if p.stem != "index":
                out.append({"id": p.stem, "name": _scene_name(p), "kind": "battle"})
    return out


IMAGE_EXT = {".webp", ".png", ".jpg", ".jpeg"}


def list_images(assets_dir: Path, data_dir: Path) -> list:
    """Backdrop candidates for scene skies: every image under Assets/Backgrounds (served as /assets/Backgrounds/...)
    plus data/Artwork (served as /assets/Artwork/..., e.g. the painted battle backdrop)."""
    out = []
    for root, prefix in ((assets_dir / "Backgrounds", "/assets/Backgrounds/"), (data_dir / "Artwork", "/assets/Artwork/")):
        if root.is_dir():
            for p in sorted(root.rglob("*")):
                if p.is_file() and p.suffix.lower() in IMAGE_EXT:
                    rel = p.relative_to(root)
                    top = prefix.strip("/").split("/")[-1]
                    out.append({"url": prefix + rel.as_posix(), "name": p.stem, "folder": top if rel.parent.as_posix() == "." else top + "/" + rel.parent.as_posix()})
    return out


MUSIC_EXT = {".mp3", ".wav"}
_PART = re.compile(r"^(.*?)\s*\((full|intro|loop)\)$", re.I)


def list_music(music_dir: Path) -> list:
    """Tracks under Assets/Music (served as /assets/Music/...). Files named "<Title> (intro)" + "<Title> (loop)" are merged into one
    entry {url: loop, intro: intro} (play the intro once, then loop); the "(full)" copy of such a set is hidden. Everything else is one entry."""
    out, parts = [], {}
    if not music_dir.is_dir():
        return out
    for p in sorted(music_dir.rglob("*")):
        if not (p.is_file() and p.suffix.lower() in MUSIC_EXT):
            continue
        rel = p.relative_to(music_dir)
        folder = rel.parent.as_posix() if rel.parent.as_posix() != "." else ""
        url = "/assets/Music/" + rel.as_posix()
        m = _PART.match(p.stem)
        if m:
            parts.setdefault((folder, m.group(1)), {})[m.group(2).lower()] = url
        else:
            out.append({"url": url, "name": p.stem, "folder": folder})
    for (folder, title), d in parts.items():
        if "loop" in d:
            e = {"url": d["loop"], "name": title + " (intro + loop)" if "intro" in d else title + " (loop)", "folder": folder}
            if "intro" in d:
                e["intro"] = d["intro"]
            out.append(e)
        elif "full" in d:
            out.append({"url": d["full"], "name": title, "folder": folder})
    out.sort(key=lambda e: (e["folder"], e["name"]))
    return out


def list_models(assets3d_dir: Path) -> list:
    out = []
    if assets3d_dir.is_dir():
        for p in sorted(assets3d_dir.rglob("*.glb")):
            rel = p.relative_to(assets3d_dir)
            out.append({"url": "/assets/3D/" + rel.as_posix(), "name": p.stem, "folder": rel.parent.as_posix() if rel.parent.as_posix() != "." else ""})
    return out


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_scene(kind: str, scene_id: str, data) -> str:
    """Returns an error string, or '' when the payload is safe to write."""
    if kind not in KINDS:
        return "kind must be 'hub' or 'battle'"
    if not isinstance(scene_id, str) or not SLUG.match(scene_id):
        return "id must be lowercase letters, digits, - or _ (max 48 chars)"
    if kind == "hub" and scene_id in NOT_HUB_SCENES:
        return f"'{scene_id}' is reserved"
    if not isinstance(data, dict):
        return "scene must be an object"
    for mk in ("music", "bossMusic"):
        m = data.get(mk)
        if m is not None and not (isinstance(m, dict) and isinstance(m.get("url"), str) and m["url"].startswith("/assets/Music/") and (m.get("intro") is None or isinstance(m.get("intro"), str))):
            return mk + " must be {url: \"/assets/Music/...\", intro?: ...}"
    sky = data.get("sky")
    if sky is not None and not isinstance(sky, (str, list, dict)):
        return "sky must be a string, a colour list or an object"
    if isinstance(sky, dict) and sky.get("type") == "gradient" and not (isinstance(sky.get("stops"), list) and sky["stops"]):
        return "gradient sky needs a non-empty stops list"
    if isinstance(sky, dict) and sky.get("type") == "layers":
        layers = sky.get("layers", [])
        if not isinstance(layers, list) or not all(isinstance(l, dict) and isinstance(l.get("url"), str) for l in layers):
            return "layered sky: layers must be a list of {url, ...} objects"
        if len(layers) > 12:
            return "layered sky: at most 12 layers"
    fx = data.get("fx")
    if fx is not None and (not isinstance(fx, list) or not all(isinstance(e, dict) and isinstance(e.get("type"), str) for e in fx)):
        return "fx must be a list of {type, ...} objects"
    if kind == "hub":
        pieces = data.get("pieces", [])
        if not isinstance(pieces, list):
            return "pieces must be a list"
        for i, p in enumerate(pieces):
            if not (isinstance(p, list) and len(p) in (6, 7) and isinstance(p[0], str) and (all(_num(v) for v in p[1:5]) and (_num(p[5]) or (isinstance(p[5], list) and len(p[5]) == 3 and all(_num(v) for v in p[5])))) and (len(p) == 6 or isinstance(p[6], str))):
                return f"piece {i} must be [model, x, z, rotY, y, scale | [sx, sy, sz]] (+ an optional hideIf key, \"!key\" = show only once cleared)"
        for key in ("npcs", "colliders", "decals", "events"):
            if not isinstance(data.get(key, []), list) or not all(isinstance(e, dict) for e in data.get(key, [])):
                return f"{key} must be a list of objects"
        for i, ev in enumerate(data.get("events", [])):
            if not isinstance(ev.get("actions", []), list) or not all(isinstance(a, dict) and isinstance(a.get("type"), str) for a in ev.get("actions", [])):
                return f"event {i}: actions must be a list of {{type: ...}} objects"
        for key in ("bounds", "spawn", "light", "fog"):
            if key in data and not isinstance(data[key], dict):
                return f"{key} must be an object"
    else:
        props = data.get("props", [])
        if not isinstance(props, list):
            return "props must be a list"
        for i, p in enumerate(props):
            if not (isinstance(p, dict) and isinstance(p.get("model"), str) and isinstance(p.get("pos"), list) and len(p["pos"]) == 3 and all(_num(v) for v in p["pos"])):
                return f"prop {i} needs a model and a pos [x, y, z]"
    return ""


def _target(kind: str, scene_id: str, hub3d_dir: Path, maps_dir: Path) -> Path:
    return (hub3d_dir if kind == "hub" else maps_dir) / (scene_id + ".json")


def save_scene(kind, scene_id, data, hub3d_dir: Path, maps_dir: Path, backup_dir: Path) -> dict:
    err = validate_scene(kind, scene_id, data)
    if err:
        return {"ok": False, "error": err}
    text = json.dumps(data, indent=1) + "\n"
    if len(text.encode("utf-8")) > MAX_BYTES:
        return {"ok": False, "error": "scene is too large"}
    path = _target(kind, scene_id, hub3d_dir, maps_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        (backup_dir / f"{kind}_{scene_id}_{stamp}.json").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        old = sorted(backup_dir.glob(f"{kind}_{scene_id}_*.json"))
        for b in old[:-15]:
            try:
                b.unlink()
            except OSError:
                pass
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return {"ok": True, "path": f"{path.parent.name}/{path.name}"}

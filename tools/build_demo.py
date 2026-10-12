"""Builds the standalone, protected demo of Skyborne Saga for Windows.   Run it with build_demo.bat (or: python tools/build_demo.py).

What it does
  1. Copies the web pages, scene data, art and audio (everything the demo needs, minus the story past the Hollow Cave and all
     editor / generator / backup files) into build_demo/web.
  2. Obfuscates the JavaScript (js_protect.js, needs Node.js; skipped with a warning when Node is missing).
  3. Packs it all into game.pak, encrypted with a fresh random key (game/vfs.py).
  4. Compiles the Python server to native code with Nuitka (no Python needed on the player's PC). The key is baked into the
     compiled demo_build module.
  5. Assembles dist_demo/SkyborneSagaDemo (exe + game.pak + the few legacy data files Python reads) and a zip of it.
Protection is a deterrent against copying and casual poking, not unbreakable: the pages are still delivered to a browser window.

Options: --no-obfuscate   skip step 2        --prune   leave out 3D models / music nothing in the demo mentions
         --skip-compile   stop after game.pak (for testing the pack)   --keep   keep build_demo/ afterwards
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from game import demo as game_demo, vfs          # noqa: E402  (game/demo.py reads BATTLE_ARENA_DEMO only; fine at build time)

BUILD = ROOT / "build_demo"
WEB = BUILD / "web"
PYSRC = BUILD / "py"
OUT = ROOT / "dist_demo"
APP_NAME = "SkyborneSagaDemo"
WEB_DIRS = ["html_hub", "html_battle", "html_overworld", "Assets", "data"]
LATE = set(game_demo.LATE_SCENES)


def skip_web(rel: Path) -> bool:
    n = rel.name
    parts = rel.parts
    if "__pycache__" in parts or n.endswith((".py", ".pyc", ".bak", ".log", ".psd", ".blend", ".uasset")) or ".pre_" in n:
        return True
    if n == "playtest_bot.js" or n == "dungeon_layout.json":
        return True
    if parts[0] == "html_hub" and len(parts) == 3 and parts[1] == "3d" and rel.suffix == ".json" and rel.stem in LATE:
        return True
    if parts[0] == "html_battle" and "backups" in parts:
        return True
    return False


def step(msg):
    print("\n==> " + msg, flush=True)


def run(cmd, **kw):
    print("   $ " + " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def copy_web():
    step("Collecting the web pages, scenes and assets")
    n = 0
    for top in WEB_DIRS:
        src_root = ROOT / top
        if not src_root.is_dir():
            print("   (missing, skipped): " + top)
            continue
        for p in src_root.rglob("*"):
            if p.is_dir():
                continue
            rel = p.relative_to(ROOT)
            if skip_web(rel):
                continue
            dst = WEB / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            n += 1
    print("   %d files" % n)


def prune_assets():
    """Drop 3D models and music that no kept page, scene or Python file mentions (by file name)."""
    step("Pruning unused 3D models and music")
    text = []
    for p in WEB.rglob("*"):
        if p.suffix.lower() in (".json", ".js", ".html"):
            text.append(p.read_text(encoding="utf-8", errors="ignore"))
    for p in list(ROOT.glob("*.py")) + list((ROOT / "data").glob("*.py")) + list((ROOT / "game").glob("*.py")):
        text.append(p.read_text(encoding="utf-8", errors="ignore"))
    blob = "\n".join(text).lower()
    removed = kept = freed = 0
    for sub in ("Assets/3D", "Assets/Music"):
        base = WEB / sub
        if not base.is_dir():
            continue
        for p in list(base.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in (".glb", ".gltf", ".mp3", ".ogg", ".wav", ".bin"):
                continue
            if p.name.lower() in blob or p.stem.lower() in blob:
                kept += 1
            else:
                freed += p.stat().st_size
                p.unlink()
                removed += 1
    print("   kept %d, removed %d (%.0f MB)" % (kept, removed, freed / 1e6))


def protect_js(skip):
    step("Obfuscating JavaScript")
    node = shutil.which("node")
    if skip or not node:
        print("   skipped (%s). The pages will be packed as they are." % ("--no-obfuscate" if skip else "Node.js not found - install it from nodejs.org and rebuild to obfuscate"))
        return
    nm = BUILD / "node"
    nm.mkdir(parents=True, exist_ok=True)
    if not (nm / "node_modules" / "javascript-obfuscator").is_dir():
        npm = shutil.which("npm")
        if npm:
            try:
                run([npm, "install", "--prefix", nm, "--no-audit", "--no-fund", "javascript-obfuscator@4.1.1"])
            except subprocess.CalledProcessError:
                print("   could not install javascript-obfuscator; trying whatever is available")
    env = dict(os.environ, NODE_PATH=str(nm / "node_modules"))
    r = subprocess.run([node, str(ROOT / "tools" / "js_protect.js"), str(WEB)], env=env)
    if r.returncode == 3:
        print("   no obfuscator available - pages packed as they are")
    elif r.returncode != 0:
        raise SystemExit("JavaScript protection failed")


def make_pak(key: bytes) -> Path:
    step("Packing and encrypting game.pak")
    entries = []
    for p in sorted(WEB.rglob("*")):
        if p.is_file():
            entries.append((p.relative_to(WEB).as_posix(), p))
    pak = BUILD / "game.pak"
    n = vfs.write_pak(pak, entries, key)
    # read it back to be sure the pack and the key agree
    if not vfs.mount(pak, key):
        raise SystemExit("game.pak failed its read-back check")
    check = next(a for a, _ in entries if a.endswith("title.html"))
    if vfs.PakPath(check).read_bytes() != (WEB / check).read_bytes():
        raise SystemExit("game.pak failed its read-back check")
    print("   %d files, %.0f MB" % (n, pak.stat().st_size / 1e6))
    return pak


def stage_python(key: bytes):
    step("Staging the Python sources")
    if PYSRC.exists():
        shutil.rmtree(PYSRC)
    PYSRC.mkdir(parents=True)
    for f in ("launcher.py", "hub_server.py", "config.py", "builder3d_api.py"):
        shutil.copy2(ROOT / f, PYSRC / f)
    for pkg in ("ai", "engine", "game", "data"):
        for p in (ROOT / pkg).rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            dst = PYSRC / p.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
    # the few plain data files Python itself reads (legacy overworld maps and palettes)
    if (ROOT / "data" / "maps").is_dir():
        shutil.copytree(ROOT / "data" / "maps", PYSRC / "data" / "maps")
    for j in (ROOT / "data").glob("*.json"):
        shutil.copy2(j, PYSRC / "data" / j.name)
    mask = os.urandom(len(key))
    mixed = bytes(a ^ b for a, b in zip(key, mask))
    (PYSRC / "demo_build.py").write_text(
        "DEMO = True\n_A = %r\n_B = %r\n" % (mask, mixed), encoding="utf-8")
    if (ROOT / "icon.ico").is_file():
        shutil.copy2(ROOT / "icon.ico", PYSRC / "icon.ico")


def compile_exe():
    step("Compiling the game to native code with Nuitka (this takes a while)")
    out = BUILD / "nuitka"
    if out.exists():
        shutil.rmtree(out)
    cmd = [sys.executable, "-m", "nuitka", "--standalone", "--assume-yes-for-downloads", "--remove-output",
           "--output-dir=" + str(out), "--output-filename=" + APP_NAME + ".exe",
           "--include-package=ai", "--include-package=engine", "--include-package=game", "--include-package=data",
           "--include-package=websockets", "--include-data-dir=data/maps=data/maps", "--include-data-files=data/*.json=data/",
           "--nofollow-import-to=tkinter", "--nofollow-import-to=pygame", "--nofollow-import-to=unittest", "--nofollow-import-to=pydoc",
           "--product-name=Skyborne Saga Demo", "--file-description=Skyborne Saga Demo", "--file-version=0.1.0.0", "--product-version=0.1.0.0"]
    if os.name == "nt":
        cmd += ["--windows-console-mode=disable"]
        if (PYSRC / "icon.ico").is_file():
            cmd += ["--windows-icon-from-ico=icon.ico"]
    cmd += ["launcher.py"]
    run(cmd, cwd=PYSRC)
    dist = next(out.glob("*.dist"))
    return dist


README = """SKYBORNE SAGA - DEMO

Run SkyborneSagaDemo.exe. Nothing else needs to be installed (it opens in an Edge/Chrome app window, which Windows already has).

Your saves are kept in %LOCALAPPDATA%\\SkyborneSagaDemo\\saves.

The demo covers Paradise Island and the Whispering Wood, up to the Hollow Cave. You can keep playing after that:
explore, fish, gamble, hunt treasure and fight; the Hollow Cave stays sealed.
"""


def assemble(dist: Path, pak: Path):
    step("Assembling " + str(OUT / APP_NAME))
    target = OUT / APP_NAME
    if target.exists():
        shutil.rmtree(target)
    OUT.mkdir(exist_ok=True)
    shutil.copytree(dist, target)
    shutil.copy2(pak, target / "game.pak")
    (target / "README.txt").write_text(README, encoding="utf-8")
    zpath = OUT / (APP_NAME + ".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for p in target.rglob("*"):
            if p.is_file():
                z.write(p, (Path(APP_NAME) / p.relative_to(target)).as_posix())
    print("   folder: %s\n   zip:    %s (%.0f MB)" % (target, zpath, zpath.stat().st_size / 1e6))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-obfuscate", action="store_true")
    ap.add_argument("--prune", action="store_true")
    ap.add_argument("--skip-compile", action="store_true")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    BUILD.mkdir(exist_ok=True)              # build_demo/venv and build_demo/node survive between builds
    for sub in ("web", "py", "nuitka"):
        shutil.rmtree(BUILD / sub, ignore_errors=True)
    (BUILD / "game.pak").unlink(missing_ok=True)
    key = os.urandom(32)
    copy_web()
    if a.prune:
        prune_assets()
    protect_js(a.no_obfuscate)
    pak = make_pak(key)
    if a.skip_compile:
        print("\nStopped after game.pak (--skip-compile): " + str(pak))
        return
    stage_python(key)
    dist = compile_exe()
    assemble(dist, pak)
    if not a.keep:
        for sub in ("web", "py", "nuitka"):
            shutil.rmtree(BUILD / sub, ignore_errors=True)
    print("\nDone.")


if __name__ == "__main__":
    main()

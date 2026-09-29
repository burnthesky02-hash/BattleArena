# Summon screen prototype, take two: HTML/CSS/JS instead of Unity

Same test as the Unity prototype, same backend (`summon_server.py` at your
project root, importing `game/summon.py`/`data/summon_pool.py`/
`data/hero_rarity.py` directly, seeded with a throwaway pile of gems, never
touching `saves/save1.json`) -- the only thing that changed is the front
end. The Unity version and its `unity_prototype/` folder are still there if
you want to compare them side by side; nothing here deletes it.

## 1. Run it

From your `Battle Arena` project root:

```
python summon_server.py
```

Then open **http://127.0.0.1:8765/** in any browser. That's it -- the page
*is* served by the same script that has your real summon logic, so there's
no separate front-end server, no CORS setup, nothing else to configure.

Click a banner (Recruit a Hero / Premium Gear), click Pull x1 or x10, then
either click individual cards or hit "Reveal All" to flip them. Gem count
and every rarity/odds number you see is your actual game data.

## 2. Run it as its own window instead of a browser tab

This is the "own app window" option you picked over a plain browser tab.
One extra dependency:

```
pip install pywebview
python html_prototype/run_desktop.py
```

This starts the exact same backend on a background thread and opens a
plain window with no address bar or tabs -- pywebview just wraps your
system's native web-rendering component (Edge WebView2 on Windows, which
you already have since it ships with Windows/Edge) around the page. Nothing
about the page itself changes between this and the plain browser-tab
version; it's purely how it's framed.

## Files

- **`summon_server.py`** (project root) -- extended from the Unity version:
  it now also serves `html_prototype/index.html` at `GET /`, on top of the
  same `/state`, `/summon/character`, `/summon/equipment` JSON endpoints.
- **`html_prototype/index.html`** -- the entire front end: markup, CSS, and
  JS in one file (no build step, no npm, nothing to install for the
  browser-tab path). Card flips are a real CSS 3D transform
  (`rotateY` + `backface-visibility: hidden`), and each rarity gets a
  colored glow (`box-shadow`) pulled from the same hex values as
  `data/hero_rarity.py`'s `HERO_RARITY_COLOR`.
- **`html_prototype/run_desktop.py`** -- the pywebview wrapper described
  above.

## What to compare against the Unity version

Specifically worth noticing, since this is the actual decision point:
- The card flip and rarity glow took a few CSS rules here (`transform`,
  `box-shadow`, `linear-gradient`) versus a hand-written rotation coroutine
  in C#. This is the same category of win CSS would give every other
  screen (translucent panels, gradients, hover states) that's taken
  fix-numbered passes in pygame.
- No compile step, no Editor, no scene-wiring by hand -- edit
  `index.html`, refresh the browser, see the change immediately.
- The tradeoff: this is browser/DOM layout, not a game canvas. The battle
  screen's sprite positioning/animation (idle sheets, run-in/swing
  melee, ranked formations) is a different kind of problem in HTML/CSS/JS
  than it was in pygame -- doable (canvas or absolutely-positioned
  elements with CSS animations), but not something this prototype touches,
  and not automatically free the way the panel/card styling was.

If this feels like the right direction, the next real decision is scope and
order: which screen becomes the first *real* replacement in
`ui/`, and whether the battle screen's sprites move to an HTML canvas or
stay a separate concern for longer.

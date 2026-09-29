# Summon screen prototype: Unity front end + your real Python summon logic

This is a small, throwaway test to answer one question: does Unity's UI
give the gacha-reveal screen more polish than the current pygame version,
enough to justify a bigger migration? It is **not** wired to your real save
file, and it doesn't replace anything in `ui/pygame_ui.py` -- your game runs
exactly as it does today, untouched.

## How it's split

- **`summon_server.py`** (in this folder) -- drop this into your `Battle
  Arena` project root, next to `main.py`. It imports your real
  `game/summon.py`, `data/summon_pool.py`, `data/hero_rarity.py`, and
  `data/equipment_db.py` directly, so the odds/rarities/shard math are
  exactly what your game already does -- nothing is reimplemented or
  approximated. It just seeds a throwaway `PlayerState` with a huge pile of
  gems (so you can mash the pull buttons without worrying about the
  economy) and serves it over a tiny local HTTP API. Nothing it does
  touches `saves/save1.json`.
- **`Scripts/*.cs`** -- copy these into a Unity project's `Assets/Scripts/`
  folder. They call that local API and render the reveal.

## 1. Run the Python side

From your `Battle Arena` folder (same place you run `main.py`):

```
python summon_server.py
```

You should see:

```
[summon_server] Prototype Summon API running on http://127.0.0.1:8765
[summon_server] Seeded with 999999 gems, empty roster. Nothing here touches your real save.
```

Leave this running the whole time you're testing in Unity. Ctrl+C stops it
whenever you're done -- nothing persists.

## 2. Create the Unity project

Open Unity Hub -> New Project -> **2D (Core)** template (the built-in
render pipeline is fine for a UI-only test, no need for URP/HDRP). Name it
whatever you like.

Once it opens:
1. Create the folder `Assets/Scripts/Summon/` and copy in the four `.cs`
   files from `Scripts/` here.
2. Wait for Unity to compile (bottom-right spinner). Fix nothing -- these
   compile clean against a stock 2D project.

## 3. Build the scene

This is the one part I can't hand you pre-built -- it needs the Unity
Editor GUI. It's about 10 minutes of clicking:

1. **Canvas.** Right-click Hierarchy -> UI -> Canvas. Set its Canvas Scaler
   to "Scale With Screen Size", reference 1280x800 (matches your pygame
   window, for a fair comparison).
2. **Empty GameObject** named `SummonController` under the Canvas. Add the
   `SummonApiClient` component and the `SummonScreenController` component
   to it.
3. **Top bar:** a Text for gems (`gemsText`) and a Text for the cost/status
   line (`statusText`).
4. **Four buttons:** "Pull Character x1", "Pull Character x10", "Pull
   Equipment x1", "Pull Equipment x10". Drag each into the matching field
   on `SummonScreenController` (`pullCharacter1xButton`, etc.) -- don't wire
   their `OnClick` in the Inspector, the script wires them itself in
   `Awake()`.
5. **Reveal grid:** an empty GameObject named `RevealGrid`, with a
   `Grid Layout Group` component (cell size ~160x200, spacing ~16) and a
   `Content Size Fitter` if you want it to grow. Drag it onto
   `revealGridParent`.
6. **Two more buttons:** "Reveal All" and "Continue" -> drag onto
   `revealAllButton` / `continueButton`.
7. **The card prefab** (`revealCardPrefab`) -- this is the one with a few
   sub-parts:
   - An Image (this is the card itself) with a `RevealCard` component.
   - A child `Front` -- an Image + a Text showing `?` (the face-down side).
   - A child `Back` -- **starts inactive** -- containing:
     - an Image named e.g. `Banner` (drag onto `backBanner` -- this gets
       tinted per rarity),
     - a Text for the name (`nameText`),
     - a Text for the rarity label (`rarityText`),
     - a Text for the tag (`tagText` -- shows "NEW!", "+N shards", or the
       equipment slot).
   - On the `RevealCard` component, drag the card's own `RectTransform`
     into `cardTransform`, `Front`/`Back` into `frontFace`/`backFace`, and
     the sub-parts above into their matching fields.
   - Optional: add a `Button` component to the card root and wire its
     `OnClick` to `RevealCard.OnCardClicked` so a single card can also be
     flipped by clicking it directly, not just via "Reveal All".
   - Drag this whole card GameObject into your Project window to make it a
     prefab, then delete the scene copy and assign the prefab asset to
     `SummonScreenController.revealCardPrefab`.

## 4. Press Play

With `summon_server.py` running, press Play in the Unity Editor. Click a
pull button, then "Reveal All" (or click individual cards). You should see
gems tick down, a "Pulled N heroes!"-style status line, and cards flipping
to reveal rarity-tinted results that match your game's actual odds.

## What this does and doesn't tell you

It'll tell you whether Unity's Canvas/UI system, animated the way this
script does it (a simple shrink-swap-grow flip, no external animation
package), already feels more polished than pygame's instant reveal -- and
it'll tell you how it feels to build UI this way (Inspector-wired
references vs. hand-computed pixel rects) now that you've done it once.

It deliberately does *not* cover: the battle screen's sprite
layout/animation (a much bigger, separate effort either way), hooking this
up to your real save file, or building anything you'd actually ship --
treat this whole folder as disposable once you've made a call.

If Unity's reveal feels like the right direction, the follow-up
conversation is which of the two integration paths from before makes
sense: port the Python game logic to C# so everything lives in one Unity
project, or keep growing this same split (Python backend, Unity front end)
into something the games' hub/shop/heroes/battle screens all eventually
move onto.

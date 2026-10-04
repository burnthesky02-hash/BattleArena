# Battle Colosseum -- Prototype

A classic-JRPG game where every enemy is driven by a hand-written, rule-based AI: each
monster has its own behavior profile (who it hunts, what it opens with, when it heals or
braces), the tougher ones telegraph big attacks you can answer, and rival enemies adapt to
how you play. Most of the UI is still placeholder (colored rectangles + bars); battle and
the Heroes/Summon screens have real art (see "Playing a battle" below), everything else
doesn't yet. The focus so far has been the battle engine, the enemy AI, and the surrounding
meta-game loop: a title screen, character creation, a persistent save file,
the Colosseum hub, a money/gems economy, a Shop (spend money on consumables
and common/rare gear), Summon (spend gems on a new recruit -- now with a
common/rare/epic/legendary/mythic **hero rarity** system, see "Summon"
below -- or a chance at premium epic/legendary gear), a **Heroes** page
(view/equip your roster and spend duplicate-summon shards on star
upgrades), and a **4-hero party cap** with a pick-your-party screen before
every battle. See "Known limitations" below for what's still rough around the
edges (difficulty scaling, animations, and so on).

## What's here

**The loop:** title screen -> New Game (create a character: name + one of
five class archetypes) or Continue (load your save) -> the Colosseum hub
(your roster, your money/gems, and buttons to fight, shop, summon, and
manage your heroes) -> Enter Battle (choose your party of up to 4, then
difficulty/opponent count) -> back to the hub, repeat. "Save & Quit to
Title" saves and returns to the title screen; the window's close
button/Escape exits (and saves first, if you're past character creation)
from anywhere.

**Battles:** a full turn-based battle loop -- speed-based turn order,
physical/magical attacks, buffs/debuffs, status effects (poison, stun,
atk/def up/down, regen), consumable items (potions, revives, antidotes),
and win/loss/flee conditions. Before each fight, a **Choose Your Party**
screen lets you pick **up to 4 heroes** from your roster to actually field
(see "Party selection" below), then a **Battle Setup** screen lets you pick
a **difficulty** (Easy/Normal/Hard/Extreme, which scales the enemies' level
relative to your *fielded party's* average level) and **how many
opponents** (1-4), then a real match is drawn at random from a 13-archetype
enemy pool (see "Level curves & battle difficulty" below) -- it's no longer
always the same fixed trio. You start with one created character; solo
against multiple opponents is meant to be a real underdog fight at first,
which is the point of the "recruit more characters via Summon" design (see
"Summon" below); losing still pays out, so it's never a dead end. Only the
party you selected fights and earns XP that battle -- everyone else on your
roster sits it out untouched. Each enemy's turn is decided by the rule-based AI in
`ai/enemy_ai.py` (see "How the enemy AI works" below): a per-archetype behavior
profile plus a utility score for every legal option, so every monster fights
differently and nothing about it needs a model or a network connection.

**Leveling:** every character (and every enemy) has a level and grows
stronger past level 1 along a class/archetype-specific growth curve.
Winning a battle grants XP to every character who fought, automatically
resolving any level-ups; a freshly Summoned recruit always joins at level 1
and has to catch up. See "Level curves & battle difficulty" below.

**Economy:** every battle pays money, win or lose (a smaller amount on a
loss/flee than a win); a win also pays gems and XP. All three scale with a
difficulty/party-size **reward multiplier** -- see "Level curves & battle
difficulty" below for the exact formula. Money and gems both persist to
your save file. The Shop spends money on consumables and common/rare gear;
Summon spends gems on a new recruit or a chance at premium gear -- see
"The Shop" and "Summon" below.

## Setup

1. **Python 3.10+**
2. Install the dependencies: `pip install -r requirements.txt` (just `pygame-ce`; the
   browser hub additionally uses `websockets`, which `Play.bat` installs on first run).
3. Run it -- no other services are needed.

## Running it

Graphical placeholder window (default), 1280x800:
```
python main.py
```

Fullscreen (scales that same layout up to fill your monitor) -- off by default, opt in with
`--fullscreen` or `FULLSCREEN_ON_START=1`:
```
python main.py --fullscreen
```

Plain terminal, no pygame required:
```
python main.py --mode text
```

The browser version (the one with the 3D hub, story and Colosseum) is started with `Play.bat`
(or `python launcher.py`); `Debug.bat` / `--debug` adds the Battle Debug menu and damage graphs.

## Debug mode

```
python main.py --debug
python main.py --mode text --debug
```

Adds the debug-only hub tools (for example the **Add Gems** button, `DEBUG_GEM_GRANT` gems
per click) and extra console lines. In the browser hub it enables the Battle Debug menu and
the damage calculation log.


## Character creation, the Colosseum hub, and saving

**Title screen:** New Game (only option on a first run), Continue (once a
save exists), Quit.

**Character creation** (New Game only): type a name, then pick one of five
class archetypes -- each has its own starting skill kit (see
`data/classes.py`), so the class you pick determines what your character
can actually do in battle, not just its stats:

| Class | Identity | Starting skills |
|---|---|---|
| Tank | High HP/DEF, weak magic | Iron Stance, Power Strike, Sunder, Self-Repair |
| Melee DPS | High ATK, fragile vs. magic | Power Strike, Cleave, Crushing Blow, Warcry |
| Ranged DPS | Fast, precise, fragile up close | Piercing Shot, Poison Dart, Weaken, Sunder |
| Mage | Very high MAG, very low HP/DEF | Fireball, Ice Lance, Thunderbolt, Firestorm |
| Support | Healing + party utility | Heal, Greater Heal, Prayer, Holy Light |

That's it for setup -- no stat allocation, no starting equipment (gear is
found/bought/summoned later). You're immediately saved and dropped into
the Colosseum hub with just that one character.

**The Colosseum hub** shows your **current 4-hero party** (with each
hero's rarity tag and star level, see "Summon" below), not your whole
collection -- once your roster can outgrow the party cap, "here's who I'm
about to fight with" and "here's everyone I own" stopped being the same
list, so the hub just shows the former (plus a "+N more in reserve" line)
and Heroes is where you browse the latter. It also shows your money and
gems, and five buttons: **Enter Battle** (opens Choose Your Party, then
Battle Setup, then fights a randomly drawn encounter; see "Party
selection", "Playing a battle", and "Level curves & battle difficulty"
below), **Shop** (see "The Shop" below), **Summon** (see "Summon" below),
**Heroes** (see "Heroes page" below), and **Save & Quit to Title**.

**Saving** is a single JSON save file (`saves/save1.json`, created
automatically on first save) holding your roster (name, class, level, xp,
equipped gear ids, rarity, star level, banked shards), money, gems,
consumable inventory, owned-but-unequipped gear, and your last-confirmed
battle party. It's written after character creation, after every battle
(win/lose/flee all still update your currency), and when you quit to the
title screen -- see `game/save_system.py`. Writes go through a temp file
and `os.replace()` so an interrupted write can't corrupt your save; a save
that still fails to load for some other reason (hand-edited into invalid
JSON, say) falls back to starting a new game rather than crashing, and a
save written before this feature (no rarity/star/shard/party keys at all)
still loads, defaulting every character to common rarity/1 star/0 shards
and an empty saved party.

**Equipment** exists as a full three-slot system (weapon/armor/accessory,
see `engine/equipment.py` and `data/equipment_db.py`) with flat stat
bonuses per piece and a rarity tier -- common/rare are shop-buyable (see
"The Shop" below), epic/legendary have `cost=0` and are gem-summon-only
(see "Summon" below), so the Shop refuses to sell them. Every new
character still starts with all three slots empty; the plumbing
(`PlayerCharacter.equip`, `effective_stats`, `build_combatant` applying
equipped bonuses on top of class base stats) is tested in
`tests/roster_test.py`, and both the Shop and Summon call straight into it
rather than duplicating any of it.

## The Shop

Reached from the Colosseum hub's **Shop** button (pygame: click it;
text mode: pick it from the hub menu). All the actual buying logic lives in
`game/shop.py` as plain functions over `PlayerState` -- `buy_item`,
`buy_equipment`, plus `equip_from_stash`/`unequip` (now driven from the
Heroes page, see below) -- each returning `(ok, message)`, so
`ui/pygame_ui.py`'s `show_shop` and `ui/text_ui.py`'s `show_shop` are just
two different front ends driving the exact same rules (tested headlessly
in `tests/shop_test.py`, and via the pygame click-through in
`tests/shop_screen_test.py`).

- **Buying a consumable** (Potion, Hi-Potion, Ether, Antidote, Phoenix
  Down -- see `data/items_db.py` for costs) spends money and adds one to
  your inventory, the same inventory battles draw from.
- **Buying equipment** only ever offers common/rare gear (nonzero `cost`);
  it's added to an unequipped **stash** (`PlayerState.owned_equipment`),
  never auto-equipped -- head to the **Heroes** page (see below) to
  actually put it on someone, since which character should wear a new
  piece isn't implied by the purchase alone.
- The shop is a plain hub excursion, not a battle action: leaving it
  (pygame: "Back to Colosseum"; text: "Back to Colosseum" menu option)
  saves your game immediately, same as returning from a battle.
- As of the hero-rarity pass, equipping/unequipping gear is no longer part
  of the Shop at all -- it moved to the new Heroes page below (one clear
  place to manage a character, instead of two overlapping screens).

## Summon

Reached from the Colosseum hub's **Summon** button. Spends gems (from
battle rewards, see "Economy" above) on one of two banners -- **Hero
Summon** and **Gear Summon** -- each offering a **1x pull** and a **10x
pull**. Both banners are driven by `game/summon.py`'s
`summon_character_batch`/`summon_equipment_batch` (a 1x pull is just
`batch(count=1)`, a 10x pull is `batch(count=10)` -- one shared code path,
so the two can never quietly behave differently), so `ui/pygame_ui.py`'s
`show_summon` and `ui/text_ui.py`'s `show_summon` are two front ends over
identical rules (tested headlessly in `tests/summon_test.py`, and via the
pygame click-through in `tests/summon_screen_test.py`).

As of this pass, pygame's Summon screen is a Mobile-Legends-Adventure-style
**dynamic screen with a card-flip reveal animation**, replacing the earlier
flat two-button layout:

- **Idle/select view**: a left-side **banner rail** (Hero Summon / Gear
  Summon, each showing its 1x and 10x cost and a rarity-colored spectrum
  strip) plus your owned-heroes/owned-gear counts; a big center **splash
  panel** for whichever banner is selected -- a showcase portrait (Hero
  Summon shows the mythic-tier pull, real art from `data/portraits/` when
  present, a placeholder otherwise -- see "Heroes page" below; Gear Summon
  shows a pulsing gem icon shaded between epic and legendary) plus a
  "Featuring..." caption and the actual roll odds; and a bottom **pull
  bar** with "Pull x1" / "Pull x10" buttons, grayed out and unclickable
  when you can't afford them (same affordability rule the Shop uses).
- **Reveal view**: every pull -- 1x or 10x -- lands on a card-flip reveal
  instead of an instant text message. A 1x pull shows one big face-down
  card; click it to flip. A 10x pull shows a 5-wide grid of face-down
  cards; click any card to flip just that one, or click **Reveal All** to
  flip everything at once. A flipped card shows a rarity-bordered
  portrait-or-placeholder (Hero Summon) or a colored gem icon (Gear
  Summon), the name, and a tag -- **NEW!** for a fresh recruit, **+N
  shards** for a duplicate, or **GEAR** for an equipment pull. Once every
  card in the reveal is flipped, a rarity-count summary line appears with
  a **Continue** button that returns to the select view. **Back to
  Colosseum only appears on the select view** -- you have to finish
  looking at what you pulled before leaving, same convention any gacha
  screen uses (and it keeps the "which screen am I on" state simple to
  reason about). The pull's actual outcome (gems spent, hero recruited/
  duplicated, item added to the stash) happens the instant you click Pull,
  not when a card is flipped -- flipping is purely a reveal animation, it
  can't be "undone" by not looking, and a real player tapping through
  quickly isn't leaving anything unresolved.
- Text mode has no animation to show (there's nothing to flip in a
  terminal), so its menu just gained two more options -- "Summon Character
  x10" and "Summon Equipment x10" -- that print all ten result lines at
  once.

**Hero Summon** (`CHARACTER_SUMMON_COST` gems for 1x, `CHARACTER_SUMMON_COST_X10`
for 10x -- a flat x10 multiplier, no bulk discount yet, see
`data/summon_pool.py`) rolls a **hero rarity** first, then a random
class-matched hero at that rarity, and recruits them straight to your
roster -- they're available for your very next battle (once selected on
the party screen), no separate "join the party" step. Every hero has one
of 5 rarities -- **common, rare, epic, legendary, mythic** -- each with
its own color (see `data/hero_rarity.py`'s `HERO_RARITY_COLOR`; pygame
shows a hero's name/card in their rarity's color throughout the hub,
Summon reveal, party-select, and Heroes screens) and its own summon odds
(see `HERO_SUMMON_WEIGHTS`: Common 55% / Rare 28% / Epic 12% /
Legendary 4% / Mythic 1% -- tuned down once from the original "standard
gacha curve" pick of 50/30/13/5/2 after Andrew said the top tiers felt
too easy to land; legendary/mythic took the biggest cuts since those are
the ones meant to feel rare, and the Summon screen's splash panel now
shows these numbers directly instead of leaving Andrew to remember them).
The 25-name recruitable pool (`RECRUITABLE_ROSTER`, 5 per class) turned
out to be a perfect fit for that: **each class has exactly one hero at
each rarity** -- so "which class" and "which rarity" are independent
rolls with the same odds either way. The original four-person party's
Kael/Lyra/Sera/Rook are each their class's **mythic** pull (the name
most worth landing); tank, which never had an original-party
counterpart, just runs common-to-mythic through its 5 names in order.

- **Duplicates are allowed**, on purpose, including *within the same 10x
  batch* -- pulling a hero you already own (or already pulled earlier in
  this same batch) no longer avoids itself or fails, it grants that hero
  **hero shards** instead (more for a rarer duplicate, see
  `SHARDS_PER_DUPLICATE`), banked on the character and spendable on the
  **Heroes** page (below) for a **star upgrade**. Every hero starts at 1
  star (no bonus); each star past that costs shards (more for rarer
  heroes, see `SHARD_COST_FOR_STAR`) and adds a flat +8% to every stat, up
  to +32% at the 5-star cap -- so a duplicate-heavy hero keeps getting
  more valuable instead of becoming a wasted pull once you already own
  them.

**Gear Summon** (`EQUIPMENT_SUMMON_COST` gems for 1x, `EQUIPMENT_SUMMON_COST_X10`
for 10x) draws a random piece from the epic/legendary (`cost=0`) slice of
`data/equipment_db.py`, weighted toward epic over legendary
(`game/summon.py`'s `EQUIPMENT_RARITY_WEIGHTS`, the Summon splash panel
shows the resulting odds directly) so legendary stays the rarer pull, and
adds it to your unequipped stash -- exactly like a Shop equipment
purchase, never auto-equipped. This is `engine/equipment.py`'s own
separate, older rarity concept (no "mythic" tier) -- untouched by hero
rarity. Head to the Heroes page to actually put it on someone.

- Leaving Summon (pygame: "Back to Colosseum" on the select view; text:
  the same menu option) saves immediately, same as the Shop and a battle.
- **Testing tip:** `--debug` adds a hub button that grants gems on the spot
  (see "Debug mode" above) specifically so you can spam Summon pulls and
  actually see rarer rarities/duplicates without grinding real battles
  first.

## Heroes page

Reached from the Colosseum hub's **Heroes** button -- the one place to see
your whole roster and manage each hero, replacing the Shop's old "Gear"
tab as of this pass. (The Colosseum hub itself only lists your *current
4-hero party*, not the whole roster -- see "Character creation, hub, and
saving" below -- so Heroes is also the only place to browse everyone you've
collected.)

As of this pass the roster renders as a **Mobile-Legends-Adventure-style
card grid** (pygame only; text mode still just prints the whole list, one
line per hero, nothing to scroll or click there) -- 4 cards per row
(`ui/pygame_ui.py`'s `HERO_GRID_COLS`), each card a portrait tile over a
rarity-tinted name/level/star-pips banner, with a rarity-colored border
(white when selected). The grid scrolls a whole row at a time with the
mouse wheel once the roster is taller than the visible area. Clicking a
card selects that hero and shows the same detail panel as before, now
pushed right to make room for the wider grid (`HERO_DETAIL_X`):

- **Stats**, computed live via `PlayerCharacter.effective_stats` -- level
  growth, then the star-level multiplier, then equipped gear's flat
  bonuses on top.
- **Star level and shards**: a `[***..]`-style readout of their current
  star (1-5) and banked shard count, plus an **Upgrade Star** button
  (`game/heroes.py`'s `upgrade_star`) that's only clickable once you have
  enough shards for the next star -- it spends the exact cost and never
  partially spends on a failed attempt.
- **Equip/unequip**: the same stash <-> equipped-slot flow the Shop's Gear
  tab used to offer (still `game/shop.py`'s `equip_from_stash`/`unequip`
  underneath, just presented here now), scoped to whichever hero is
  selected.

**Portrait art**: drop an image per character into `data/portraits/`
(created if missing) and the card grid will use it automatically -- no code
changes needed. Supported extensions: `.png`, `.jpg`, `.jpeg`, `.webp`.
Matching (`ui/pygame_ui.py`'s `_portrait_path_candidates`) tries the
hero's exact name first, then lowercased, then with spaces replaced by
underscores, then both (so `Ari.png`, `ari.png`, and `ari_the_tank.png`
style names all work as long as the base matches the hero's `name` field
some way). Any hero without a matching file -- or with a file pygame can't
decode -- silently falls back to a drawn placeholder (a simple
head-and-shoulders silhouette tinted from the hero's class color), so a
half-finished `data/portraits/` folder never breaks the page or crashes the
game. Loaded portraits are scaled once and cached per (name, size) for the
rest of the session.

Leaving Heroes (pygame: "Back to Colosseum"; text: the same menu option)
saves immediately, same as the Shop/Summon/a battle. Tested headlessly in
`tests/heroes_test.py` (the star-upgrade math) and via the pygame
click-through in `tests/heroes_screen_test.py`, including the card grid's
scroll-by-row behavior and both `_get_portrait` code paths (missing file
vs. a real file present).

## Party selection

Your whole roster no longer auto-fights every battle. Before Battle Setup,
a **Choose Your Party** screen (`game/party.py`, `ui/pygame_ui.py`'s/
`ui/text_ui.py`'s `show_party_select`) lets you pick **up to 4 heroes** from
your roster to actually field. It starts pre-checked with your previous
confirmed party (falling back to the first 4 on your roster the very first
time, or if that previous selection is stale), remembers your choice for
next time (`PlayerState.active_party`), and won't let you add a 5th while
already at 4 (the click is simply a no-op, with a "party is full" message).
Confirming needs at least 1 hero selected; backing out without confirming
returns straight to the hub, same convention Battle Setup's own back
button already used. Only your fielded party is built into the battle,
earns XP from it, and counts toward `game/battle_setup.py`'s average-level
math and `game/rewards.py`'s size-based reward multiplier -- a hero left
off the party sits that battle out completely untouched.

**As of fix #20**, the pygame version of this screen looks like a compact
Heroes page rather than a plain toggle-list: a fixed **top strip** of up to
4 slot-cards shows your current party (an empty dashed "+" slot for each
open spot), and a scrollable **card grid** below it -- the exact same
portrait/rarity-border/star-pip cards `show_heroes` draws, both now built
through a shared `_draw_hero_card` helper so a hero looks identical
wherever they're shown -- lists every owned hero, bordered when they're
in the party. Click a hero's portrait anywhere -- their slot up top, or
their card in the grid below -- to add or remove them; there's no
separate "select then confirm" row-click step anymore. Andrew's own
request drove the shape of it directly: "Change the choose your party
screen to look more like the heroes screen with the party on top, so you
can easily remove heroes and add new ones by clicking the portraits."
`ui/text_ui.py`'s version is unaffected (it has no portraits to click, so
it keeps its numbered toggle-list as-is). Tested headlessly in
`tests/party_test.py`, via the pygame click-through in the new
`tests/party_select_screen_test.py` (moved out of `tests/meta_screens_test.py`
now that this screen has its own card geometry to test, same split
`tests/heroes_screen_test.py`/`tests/summon_screen_test.py` already
established for the other card-style screens), and end-to-end (a real
battle where an unselected bystander earns no XP) in
`tests/game_loop_test.py`.

## Playing a battle

Your party in battle is whichever up-to-4 heroes you picked on the Choose
Your Party screen right before Battle Setup (see "Party selection" above)
-- one character at the start, more to choose from once Summon has
recruited additional teammates -- against a random selection of opponents
drawn from the 13-entry enemy archetype pool (`data/enemy_pool.py`), each
with a distinct behavior profile that shapes how the AI plays them, at a level and
count you chose on the Battle Setup screen right before the fight (see
"Level curves & battle difficulty" below). Each of your turns, pick Attack / Skill / Item / Defend
/ Flee, then a target if needed. Turn order each round is speed-based with
a little randomness for tie-breaking.

(The original fixed four-person party -- Kael/Lyra/Sera/Rook, in
`data/characters.py` -- still exists as sample data and a fixture several
tests build on; it's no longer what you actually play with in a real game
session, but four of the five class archetypes above are deliberately
close copies of those four characters' kits, so the balance work in
"Balance" below still applies to a same-class solo character. They're not
gone from real play either -- see "Summon" above: all four are
recruitable there by name, with their original kits, alongside newer
names for variety.)

In the pygame window, battle is a classic side-view duel: enemies stand on
the left, your party stands on the right, both facing each other over a
full-bleed background. Every combatant plays a
looping idle-animation sprite loaded from `data/Battlers/<Name>/<Name>-Idle.png`
-- as of this pass only one sheet exists (Andrew's "Draven" placeholder, a
6x6-frame grid), and every character without a sheet of their own falls back
to it, the same graceful-degrade convention the Heroes page's portraits
already use. The sheet's native orientation faces right, so enemies (left
side) use the frames as-is and party members (right side) get them mirrored
to face left, toward the enemies -- see `_get_battler_frames`'s `facing`
param in `ui/pygame_ui.py`. Whenever anyone's HP changes, you'll still see a
quick white-then-colored flash on their sprite and a floating `-N`/`+N`
number rise and fade -- red for damage, green for healing -- and a KO'd
combatant's sprite dims rather than disappearing. **As of fix #19**, a
basic Attack or any physical-kind skill (Power Strike, Cleave, Piercing
Shot, Poison Dart, Crushing Blow) is no longer resolved standing still --
see the fix #19 section right below for the run-in/swing/run-back move.

**As of fix #21**, each side's up to 4 fighters stand on the arena floor
in up to two ranks of up to two each, instead of the old fix #17 vertical
stack -- Andrew swapped in new background art
(`data/Artwork/Background.webp`) that's an actual arena-floor scene with a visible
perspective floor converging toward a vanishing point at back-center, and
asked for the layout to stand fighters on it ("reposition the fighters to
appear on the ground instead... closer to a 2.5D perspective") and for the
old crowded-column shrink-to-fit to go away ("remove the shrinking of the
heroes"). A front rank stands near the bottom of the playfield; a back
rank (for a 3rd/4th combatant) sits higher up and shifted toward the
opposing side, echoing how the floor's tile lines converge toward the
back of the arena -- and every sprite now always draws at the same fixed
size, never shrunk to cram a crowded side into a band (see
`_column_layout` in `ui/pygame_ui.py`). The combat log (the "Round N... X
uses Y!" scrolling text) still lives at the top of the screen, just under
the round counter (moved there by fix #17); the action menu
(Attack/Skill/Item/Defend/Flee) is unaffected and still anchors to the
bottom of the window.

**As of fix #22**, Andrew retuned that ground layout after actually
seeing it: both sides moved about 100px toward the center of the screen,
the front rank moved about 80px further down the window (close enough to
the bottom command/status panels now that it intentionally overlaps
them -- those panels are translucent and drawn on top, so a fighter reads
as standing partly behind the UI rather than being clipped), and the gap
between the front and back ranks widened by about 20px. The front rank
also now draws over the back rank wherever they cross on screen (Andrew:
"we need the bottom row to show over the top row") -- `_draw_battle_column`
draws back-to-front by vertical position instead of in whatever order
`_column_layout` yields, so the nearer rank always wins the overlap.

**As of fix #18**, the battle screen matches the clean RPG-Maker-MZ-style
reference Andrew sent, in three parts:
- **Translucent panels.** Every panel drawn over the battle background --
  the top combat-log panel, the bottom command list, and the new party
  status panel below -- is now see-through (`_draw_translucent_panel`, a
  `pygame.SRCALPHA` surface blitted at `BATTLE_PANEL_ALPHA`) instead of a
  flat opaque fill, so the backdrop art shows through behind the UI the
  same way it does in the reference.
- **No more boxes on the sprites.** `_draw_combatant` no longer draws a
  name/HP/MP text block, a status-effect label, a KO tag, or a highlight
  border on or around a sprite -- sprites render clean, just the art (or
  fallback rectangle) plus the floating hit/heal number, which Andrew's
  request didn't call a "box." Whose turn it is is now shown by a
  highlighted name in the party status panel and the existing menu-title
  text ("Zara: choose an action"), not a box around the sprite.
- **Party stats moved to a bottom status panel.** A new translucent panel,
  bottom-right (`_draw_party_status_panel`), lists each party member's
  Name/HP/MP -- HP and MP each as a label, a numeric value, and a bar --
  replacing the old per-sprite bars, matching where the reference puts
  them. Enemies don't get one of these (the reference doesn't show enemy
  stats either, and targeting has always worked off the text button
  menu's target list -- as of fix #19, clicking a combatant's own sprite
  works too, see right below, but the text menu is still there and still
  the primary way to pick a target). **TP was not added** -- the engine has no TP resource at
  all (only HP/MP), so there's nothing to display; flag this to Andrew if
  he wants a TP-like resource added to the engine itself, since that's a
  bigger change than a UI tweak. The old 4-column button grid is now a
  single-column list inside its own bottom-left panel -- every battle menu
  (the main 5-action menu, or a skill/item/target submenu) tops out at 5
  entries, so a single column always fits without needing separate layout
  logic per menu type.

**As of fix #19**, Andrew asked for melee movement ("they should run to the
target then use the attack/skill") and click-to-target on the sprites
themselves, plus wired in a run cycle and a melee swing animation for
Draven:
- **Run-in / swing / run-back for melee actions.** The basic Attack and any
  physical-kind skill (Power Strike, Cleave, Piercing Shot, Poison Dart,
  Crushing Blow -- `kind == "physical"` in `data/skills_db.py`) now play out
  as an actual move instead of resolving in place: the attacker's sprite
  runs from its column spot to stand next to its target, plays a one-shot
  melee swing in place, then runs back home. Magical/heal/status skills and
  non-attack actions (Item/Defend/Flee) are untouched and still resolve
  instantly, same as before. This is implemented entirely on the UI side --
  `PygameUI.attach_engine` wraps the `BattleEngine` instance's
  `resolve_action` (`_resolve_action_with_movement` in `ui/pygame_ui.py`),
  the same "derive it from state, never touch `engine/`" precedent the
  hit-flash system already established -- so `engine/battle.py` didn't
  change at all for this. The engine's real, unwrapped `resolve_action` call
  (and the damage number/flash it triggers) fires partway through the swing,
  timed to land close to the sheet's own impact frame, not at the very
  start or end of the animation.
- **New Run/Melee poses, alongside the existing Idle loop.** A battler can
  now have `data/Battlers/<Name>/<Name>-Run.png` (a looping run cycle) and
  `<Name>-Melee.png` (a one-shot 36-frame swing) next to its
  `<Name>-Idle.png`, sliced the same 6x6-frame-grid way. Andrew's added
  both for Draven. Neither is required: a battler with no Run/Melee sheet of
  its own falls back to its own Idle pose first (so it still looks like
  itself, just standing still, mid-move), then to
  `DEFAULT_BATTLER_NAME`'s sheet for that same pose, and only then to
  `DEFAULT_BATTLER_NAME`'s Idle -- see `_load_battler_sheet_raw`'s
  docstring for the exact order.
- **Click a sprite to target it.** Wherever the text button menu already
  offers a combatant as a choosable target (attacking, healing, using an
  item on someone), that combatant's own on-screen sprite is now clickable
  too -- exactly equivalent to clicking its row in the menu, no separate
  targeting path. No changes were needed to `get_party_action`,
  `_choose_target`, or `_wait_for_choice`; `_draw_frame` just appends the
  sprite's on-screen rect as an extra clickable entry alongside the text
  row's, for any button whose value is a target combatant.
- **Numbers Andrew may want to retune by feel**, all first-pass/eyeballed
  (see the "Melee movement (fix #19)" constants block in `ui/pygame_ui.py`):
  how fast the run cycle plays back and how far a run-in/run-back slide
  covers per second (clamped so a short hop and a long dash both look
  right), how fast the swing plays back, how far short of the target the
  attacker stops, and roughly which frame of the 36-frame swing sheet counts
  as "the hit" (tunes how early/late the damage number appears relative to
  the swing).

MP is a real, limited resource: every skill has an `mp_cost` (see
`data/skills_db.py`), it's deducted the instant the skill resolves
(`Combatant.spend_mp` in `engine/combatant.py`), and it never regenerates
mid-battle -- there's no per-turn MP tick anywhere in the engine, only
items that explicitly restore it. Your own MP bar is the blue bar under
each party member's HP bar; run dry on a caster and their skills stop
being choosable (the pygame UI re-prompts you rather than letting you pick
one you can't pay for) until they fall back to a plain Attack, which is
free. The same rule applies to enemies -- see the note on unaffordable
skill requests under "How the enemy AI works" below.

## Level curves & battle difficulty

Added in the same pass: every character and enemy now has a level, battles
award XP, and you choose difficulty/opponent count before each fight
instead of always facing the same fixed trio.

**Leveling.** `data/leveling.py` is the shared curve both sides of a fight
use: `xp_for_next_level(level)` needs 40 XP for 1->2, 60 for 2->3, 80 for
3->4 (+20 per level, a soft cap at level 60), and `apply_growth` adds each
class/enemy archetype's flat `growth` stat block on top of its level-1
`base_stats`, once per level past 1 -- see the `growth` fields in
`data/classes.py` (shaped per class: tank leans HP/DEF, melee_dps ATK,
ranged_dps splits ATK/SPD/LUK, mage/support grow MP faster than HP) and
`data/enemy_pool.py`. Every battle you win grants each character who fought
some XP (see "Rewards" below), resolved into level-ups automatically
(`PlayerCharacter.grant_xp`, `resolve_level_up` -- a single big XP grant can
cross more than one level at once); a freshly Summoned recruit always joins
at level 1, by design, so the roster keeps growing by recruiting rather
than one character leveling into soloing everything forever.

**The enemy pool.** `data/enemy_pool.py` holds 13 `EnemyArchetype`s: the
original Iron Golem/Bandit Rogue/Dark Cultist trio (kept at their exact
original level-1 stats -- `tests/battle_setup_test.py` pins this down) plus
10 new ones spanning roles the original trio didn't have, notably Temple
Oracle (a healer/support enemy that prioritizes healing wounded squadmates
over attacking) and Colosseum Champion (a tough boss-flavored fighter). All
20 skills come from the existing `data/skills_db.py` registry -- no new
skills were invented for this pass. `data/enemies.py`'s original
`make_enemy_group()` (the fixed trio) is left completely untouched and
still backs several tests -- it's legacy test-fixture data now, the same
way `data/characters.py`'s original fixed party became a fixture once real
character creation existed.

**Battle Setup.** Before each fight, pick a difficulty and an opponent
count (1-4); `game/battle_setup.py` then picks that many *distinct*
archetypes at random from the pool (no repeats within one encounter) and
levels them relative to your party's average level:

| Difficulty | Enemy level vs. your party's average |
|---|---|
| Easy | 2-3 levels *under* a jittered "normal" target |
| Normal | your average level, +/-1 |
| Hard | 2-3 levels *over* the normal target |
| Extreme | 5 levels over the normal target, flat |

This is one specific reading of an ambiguous spec ("easy would be 2-3
levels under normal within 1 level either way, hard 2-3 levels higher and
extreme 5 levels higher") -- there's an implicit jittered "normal" target
first, and easy/hard/extreme are offsets *from that target*, not from your
raw average. See `game/battle_setup.py`'s module docstring if these numbers
need retuning; `tests/battle_setup_test.py` pins the offset ranges down so
a retune shows up as a clear test change, not a silent drift.

**Rewards.** Money/gems/XP are all scaled by one multiplier,
`difficulty_modifier * size_modifier` (`game/rewards.py`):

- `difficulty_modifier`: Easy .75, Normal 1, Hard 1.25, Extreme 2
- `size_modifier`: `1 + 0.25 * (enemies - 1) - 0.25 * (heroes - 1)` -- +0.25
  per enemy beyond the first, -0.25 per hero beyond the first (floored at
  0.1 so a very large roster, which has no size cap, can't push it to zero
  or negative -- that floor is an addition, not part of the original spec)

Worked example (the one the multiplier was checked against): 1 hero vs. 3
enemies is `1 + 0.25*2 = 1.5x`; on Extreme that's `2 * 1.5 = 3x`. Money
scales on every outcome (win, lose, or flee); gems and XP stay win-only,
following the money-always/gems-on-win rule that already existed. XP is
*per character who fought*, not a pooled total split between them.

**Hero rivals.** Andrew's request: "Hero characters can show up as enemies
as well, and defeating them gives a small chance to win their respective
hero shards." Every individual opponent slot in a battle independently rolls
a 25% chance (`game/battle_setup.py`'s `HERO_ENEMY_CHANCE`) to be filled by a
rival version of one of `data/summon_pool.py`'s 25 recruitable heroes
instead of a `data/enemy_pool.py` monster -- so a 4-opponent fight might be
all monsters, all rivals, or any mix. Which rival shows up is rarity-weighted
the same curve a Summon pull uses (`data/hero_rarity.py`'s
`HERO_SUMMON_WEIGHTS`), so a mythic-tier rival is exactly as rare to run
into as it is to pull. A rival is built from its own class's real kit
(`data/classes.py` -- the same stats/skills/growth a player of that class
would have, leveled the same way a monster is for the fight's difficulty)
rather than getting bespoke stats, and named `"Rival <name>"` in the battle
log/UI so it's never confused with an owned party member fighting on your
own side. There's one persona per class (5 total, not 25) since combat
behavior comes from the shared class kit, not the individual name --
`game/battle_setup.py`'s `HERO_ENEMY_PERSONAS`.

Beating a rival rolls a separate, flat 15% chance
(`game/rewards.py`'s `HERO_SHARD_DROP_CHANCE`, victory-only, checked once per
defeated rival) to drop hero shards for that specific hero -- reusing
`SHARDS_PER_DUPLICATE`'s exact rarity scaling, so it pays out exactly as if
that had been a duplicate Summon pull. This only ever lands on a hero you've
*already* recruited: shards only mean anything spent against an owned
`PlayerCharacter` (see "Heroes page" below), so a rival for a hero you
haven't pulled yet is a normal fight with no bonus payout, on purpose, not
an oversight. The drop message prints straight into the battle log the
moment the fight ends (`ui.print_line`, from `main.py`'s `run_one_battle`),
the same channel every other in-battle event uses, rather than becoming a
new field threaded through `run_one_battle`'s reward tuple. Both numbers
(25% encounter chance, 15% drop chance) are first-pass, same "retune by
feel" spirit as everything else numeric in this project --
`tests/battle_setup_test.py` and the new `tests/rewards_test.py` cover the
mechanics, not the exact tuning.

## Balance

The original enemy trio lost to the default party in headless testing
essentially 100% of the time. Two real causes, not just "numbers too low":
- **Turn economy.** The party has 4 members acting every round against the
  enemies' 3, which is an inherent tempo advantage regardless of stats --
  by design (this was an explicit earlier scope decision), so the fix
  works around it rather than changing party/enemy counts.
- **A real bug**, not just a numbers problem: Poison and Regen were
  defined with `dot_damage=0` in `engine/status_effects.py`, with a
  comment claiming the actual amount was "computed dynamically" somewhere
  else -- except nothing ever computed it. Both effects were being applied
  (and logged) but silently ticking zero damage/healing every turn. Bandit
  Rogue's whole "poisons tough-looking targets to whittle them down" kit
  was doing nothing. Fixed in `engine/battle.py`'s `_do_skill`: poison now
  ticks 7% of the target's max HP per turn, regen ticks 5%, computed at
  the moment the status is applied (see `tests/engine_balance_test.py` for
  the regression coverage this didn't have before).
- Elemental weaknesses (1.5x) combined with the party's stronger nukes
  (e.g. Lyra's Thunderbolt vs. Iron Golem's Thunder weakness) were also
  landing single hits large enough to swing a fight almost by themselves;
  weaknesses are now 1.3x instead.

On top of the poison fix, enemy stats (HP/ATK/MAG) were raised, each enemy
got an extra skill (Iron Golem: **Crushing Blow**, a heavy single-target
hit, and **Self-Repair**, a self-regen it uses when there's no kill
available; Bandit Rogue: **Sunder** to crack a tough target's armor; Dark
Cultist: **Life Drain**, a new lifesteal spell -- see `Skill.lifesteal` in
`engine/skills.py` -- that lets it out-sustain some of the party's own
healing tempo instead of just trading damage), and the scripted fallback
AI (`ai/enemy_ai.py`'s `scripted_fallback_action`) was made a bit sharper:
it now aims debuffs at whichever living party member has the most MP
(a free-to-compute stand-in for "go bother the spellcaster," since this
heuristic can't see the party's actual skill lists) and prefers an
actually-damaging skill over a self-buff when one's affordable, instead of
choosing uniformly at random among everything it could afford.

Net result, measured over 150 seeded headless battles (see
`tests/headless_battle_test.py`): **~79% party win rate**, avg. battle
length ~15 rounds (previously ~8, cap is 100). That figure was measured against the older, simpler heuristic AI; the current rule-based AI
(behavior profiles, telegraphed charges, rival adaptation) is sharper, so real win rates run lower.
If it
still feels too easy or too hard once you've played it for real, the
numbers to tune are in `data/enemies.py` (stats/skills) and the elemental
multipliers there (`resistances={...}`).

## Project layout

```
engine/     Pure game logic -- no pygame, no console I/O.
  stats.py            Stat block (HP/MP/ATK/DEF/MAG/RES/SPD/LUK)
  types.py            Element / TargetType / ActionType / BattleResult enums
  status_effects.py   Status effect templates + registry (poison, stun, buffs...)
  skills.py           Skill definitions
  items.py            Consumable item definitions
  equipment.py        Weapon/armor/accessory gear definitions (flat stat
                       bonuses + rarity) -- meta-progression, not battle-time;
                       see "Character creation, the Colosseum hub, and saving"
  combatant.py        Combatant: the one class backing both heroes and enemies
  actions.py          Action: what a combatant does on its turn
  formulas.py         Damage/heal/crit/flee math
  battle.py           BattleEngine: turn order, round loop, action resolution

ai/         Rule-based enemy AI. Depends on engine/, not the other way around.
  enemy_ai.py         Behavior profiles per enemy archetype, utility scoring of every
                       legal option, telegraphed "Charging" attacks, and rival
                       adaptation memory -- see "How the enemy AI works" below.
                       make_enemy_ai_fn() returns the (combatant, state) -> Action
                       callable the engine uses; scripted_fallback_action() is a
                       stateless one-shot decision (kept for tests and tools)

data/       Sample/placeholder game content (swap for real content later).
  skills_db.py, items_db.py, characters.py, enemies.py
  classes.py          The 5 playable class archetypes (base stats + growth
                       curve + starting skill kit each) offered at
                       character creation
  leveling.py          Shared XP-curve and stat-growth math (xp_for_next_level,
                       apply_growth, resolve_level_up), used by both
                       PlayerCharacter and EnemyArchetype so both sides of a
                       fight scale the same way -- see "Level curves &
                       battle difficulty" above
  enemy_pool.py         13 EnemyArchetypes (base_stats + growth + persona +
                       skill kit each) that real Colosseum battles draw
                       from via game/battle_setup.py; enemies.py's original
                       fixed trio is left untouched as a legacy test fixture
  equipment_db.py      The gear catalog (nothing is owned by default -- see
                       game/player_state.py); common/rare (nonzero cost) is
                       Shop-buyable, epic/legendary (cost=0) is Summon-only.
                       This is a separate, older rarity concept from
                       hero_rarity.py's (no "mythic" tier), untouched by it
  hero_rarity.py       The 5 hero rarities (common/rare/epic/legendary/
                       mythic): HERO_RARITY_COLOR (pygame RGB per rarity),
                       HERO_SUMMON_WEIGHTS (the character-summon odds),
                       MAX_STARS/STAR_STAT_BONUS_PER_LEVEL/
                       SHARDS_PER_DUPLICATE/SHARD_COST_FOR_STAR (the
                       duplicate-summon -> shards -> star-upgrade economy,
                       see "Summon"/"Heroes page" above) and the
                       star_multiplier/shard_cost_for_next_star/star_display
                       helper functions
  summon_pool.py       RECRUITABLE_ROSTER (RecruitableHero(name, class_id,
                       rarity) entries a character summon can draw, 5 per
                       class/25 total -- exactly one name per rarity per
                       class), RECRUITABLE_BY_RARITY (the same list
                       precomputed by rarity, for game/summon.py's
                       rarity-then-class roll), both summon gem costs, and
                       (as of the Summon-screen redesign) SUMMON_X10_COUNT
                       plus each cost's _X10 sibling (a flat x10 multiplier,
                       no bulk discount yet)

game/       Meta-progression: everything that persists across battles and
            save/load. Depends on engine/+data/, not the other way around.
  roster.py           PlayerCharacter -- a persistent character record
                       (name, class, level, xp, equipped gear ids, rarity,
                       star level, banked shards); distinct from
                       engine.combatant.Combatant, which is battle-scoped
                       and resets its HP/MP the moment it's constructed.
                       build_combatant() is the only place one turns into
                       the other, applying level growth, then the star-level
                       multiplier, then equipped gear's flat stat bonuses on
                       top of the class's base stats. grant_xp() resolves
                       level-ups
  player_state.py     PlayerState -- one playthrough's roster, money, gems,
                       consumable inventory, owned-but-unequipped gear, and
                       active_party (the last confirmed battle party, see
                       party.py below)
  battle_setup.py      Difficulty -> enemy level math, random opponent
                       selection from data/enemy_pool.py, and
                       build_battle() which turns (difficulty, opponent
                       count, a *party*) into a ready-to-run BattleSetup --
                       see "Level curves & battle difficulty" above. Always
                       just took "whichever PlayerCharacters you hand it,"
                       never "the whole roster" -- so party.py's 4-hero cap
                       needed no changes here at all. Also owns hero rivals
                       (see "Hero rivals" above): HERO_ENEMY_CHANCE, per-class
                       HERO_ENEMY_PERSONAS, choose_hero_rivals(), and
                       build_hero_enemy_combatant() -- build_battle() mixes
                       these in alongside monster slots and records which is
                       which on BattleSetup.enemy_hero_recruits
  party.py            Battle party selection (see "Party selection" above):
                       MAX_PARTY_SIZE=4, default_party_ids() (previous
                       selection, filtered to owned, else first 4),
                       toggle_member(), confirm_party() (validates,
                       saves to PlayerState.active_party, resolves ids ->
                       PlayerCharacter in roster order)
  heroes.py           upgrade_star() -- spends a hero's banked shards on
                       exactly one star, if they can afford it and aren't
                       already at hero_rarity.py's MAX_STARS (see "Heroes
                       page" above); equip/unequip for that page still goes
                       through shop.py below, unchanged
  rewards.py          compute_battle_rewards(): money always, gems+XP only
                       on a win, all three scaled by the difficulty/party-size
                       reward multiplier (see "Level curves & battle
                       difficulty" above) -- party-size here is now
                       whichever party you fielded, not your whole roster.
                       Also roll_hero_enemy_shard_drops() -- the payout half
                       of hero rivals (see "Hero rivals" above):
                       HERO_SHARD_DROP_CHANCE per defeated rival, victory-only
  save_system.py      JSON save/load to saves/save1.json (single slot),
                       atomic writes (temp file + os.replace); level/xp
                       default to 1/0, and rarity/stars/shards/active_party
                       default to common/1/0/empty, when loading a save from
                       before either feature existed
  shop.py             buy_item/buy_equipment/equip_from_stash/unequip --
                       plain (ok, message) functions over PlayerState.
                       equip_from_stash/unequip are driven from the Heroes
                       page now (see "Heroes page" above), not Shop's UI,
                       but the functions themselves didn't need to move or
                       change
  summon.py           summon_character_batch/summon_equipment_batch -- the
                       actual roll logic, rolling `count` independent pulls
                       against one all-or-nothing lump-sum gem cost;
                       summon_character rolls a hero rarity
                       (data/hero_rarity.py's HERO_SUMMON_WEIGHTS) then a
                       class-matched hero at that rarity, granting hero
                       shards instead of a new roster slot on a duplicate
                       (see "Summon" above; a duplicate rolled again later
                       in the *same* batch is handled identically).
                       summon_character/summon_equipment (the original
                       single-pull functions, unchanged signatures/message
                       text) and summon_character_x10/summon_equipment_x10
                       are thin wrappers around the two _batch functions --
                       HeroSummonResult/EquipmentSummonResult are the
                       structured per-pull records a UI's card-reveal
                       animation renders from. EQUIPMENT_RARITY_WEIGHTS
                       (renamed from a private _RARITY_WEIGHTS so the
                       Summon screen can render the real odds) is untouched
                       otherwise

ui/         Two interchangeable front ends; BattleEngine doesn't know which is used.
  text_ui.py          Zero-dependency terminal UI
  pygame_ui.py        HP/MP bars and click menus for the title/character-
                       creation/Colosseum-hub/Shop/Battle-Setup meta screens
                       (still colored-rect placeholders) -- hero names/cards
                       render in data/hero_rarity.py's HERO_RARITY_COLOR
                       throughout. Battle and three meta screens go further:
                       the battle screen (_draw_frame/
                       _draw_combatant/_draw_battle_column) is a side-view
                       duel -- enemies in a left column facing right, party
                       in a right column facing left (mirrored) -- with every
                       combatant playing a looping idle sheet from
                       data/Battlers/<Name>/<Name>-Idle.png via
                       _get_battler_frames (falls back to
                       DEFAULT_BATTLER_NAME's sheet, currently Andrew's
                       "Draven" placeholder, when a character has none of
                       their own; falls back further to the original colored
                       rectangle if no sheet loads at all), over an optional
                       full-bleed backdrop from data/Artwork/Background.webp
                       via _get_battle_background -- see "Playing a battle"
                       above. The Heroes page (show_heroes) is a
                       Mobile-Legends-Adventure-style scrollable card grid
                       (HERO_CARD_*/HERO_GRID_*/HERO_DETAIL_X constants) with
                       real portrait art from data/portraits/ via
                       _get_portrait (falls back to a drawn silhouette,
                       _draw_portrait_placeholder, per-hero when no matching
                       file exists) -- see "Heroes page" above. The Summon
                       page (show_summon,
                       _draw_summon_select_screen/_draw_summon_reveal_screen,
                       SUMMON_* layout constants) is a banner-rail + splash-
                       panel select view plus a card-flip reveal animation
                       (_draw_reveal_card, shared by both the 1x solo card
                       and the 10x grid) -- see "Summon" above. As of fix
                       #20, Choose Your Party (show_party_select,
                       PARTY_SELECT_* layout constants) got the same card
                       treatment: a fixed top strip of party slots plus a
                       scrollable roster grid below it, both drawn through
                       the same _draw_hero_card helper show_heroes' own
                       grid now uses -- see "Party selection" above

tests/      Headless correctness checks (no pygame, no network needed).
  headless_battle_test.py    Runs many full battles end-to-end, reports/checks
                              the party's win rate (see "Balance" above)
  engine_balance_test.py     Unit-level checks for mechanics a random full
                              battle can't reliably exercise or verify
                              precisely -- poison/regen tick damage, lifesteal
  pygame_ui_smoke_test.py    Exercises pygame_ui.py's battle-menu logic
                              (including the hit/heal flash feedback and the
                              end screen's XP/level-up lines) against a fake
                              pygame module (this sandbox can't install real
                              pygame -- see "Known limitations" below)
  battle_sprites_test.py     Battle sprite-sheet loading (_load_battler_sheet_raw/
                              _get_battler_frames): an unknown name with no
                              sheet at all returns None; a character's own
                              sheet slices into the full 6x6 frame grid; a
                              name without one falls back to and reuses
                              DEFAULT_BATTLER_NAME's already-decoded frames;
                              facing="left" mirrors the frames and facing=
                              "right" doesn't; frames scale to the requested
                              height; the animation-frame clock stays in
                              bounds and varies per combatant; the optional
                              background loads/scales/caches correctly and a
                              missing one is a clean None; and a lopsided 1
                              enemy vs. 4 party (one KO'd) battle renders via
                              _draw_frame without crashing
  meta_screens_test.py       Same fake-pygame approach, for the title screen,
                              character creation, Colosseum hub (its 5
                              regular buttons including "Heroes", and the
                              debug-only "Add Gems" 6th button only
                              appearing when debug=True), and Battle Setup
                              screens (difficulty then opponent-count click
                              flow, backing out at each step). Choose Your
                              Party moved to its own file (below) once it
                              got a card layout of its own -- see
                              party_select_screen_test.py
  party_select_screen_test.py pygame_ui.py's show_party_select (the
                              Heroes-style card layout as of fix #20)
                              against the fake pygame module: confirming
                              the default preselection, clicking a filled
                              top-strip slot to remove that hero, clicking
                              an unselected roster-grid card to add a hero
                              when there's room, clicking a *selected*
                              hero's roster-grid card (not just their strip
                              slot) also removing them, refusing a 5th pick
                              once the party's full, backing out without
                              side effects, and empty "+" slots/an empty
                              roster not crashing the screen
  enemy_ai_test.py           Rule-based enemy AI: legal targeting, profiles, openers,
                              healing, charge/telegraph + stun break, rival adaptation
  roster_test.py             Class archetypes' skill kits are all real skill
                              ids and all distinct; PlayerCharacter equip/
                              effective_stats/build_combatant math; new
                              recruits start at level 1/0 xp; grant_xp
                              resolves level-ups (including multi-level
                              jumps) and carries the xp remainder correctly;
                              growth applies before equipment bonuses; level
                              is clamped to [1, MAX_LEVEL]
  leveling_test.py            data/leveling.py in isolation: the xp curve's
                              exact numbers, apply_growth at level 1 (no-op)
                              vs. later levels, resolve_level_up against
                              hand-worked examples, the MAX_LEVEL cap
                              discarding further xp, and a zero-xp no-op
  battle_setup_test.py        data/enemy_pool.py (13 valid archetypes, real
                              skill ids, the original trio's stats pinned
                              exactly to data/enemies.py's legacy values)
                              and game/battle_setup.py (party_average_level,
                              compute_enemy_level's difficulty offsets
                              sampled against Andrew's spec, level
                              clamping, choose_enemy_ids' bounds/uniqueness,
                              build_enemy_combatant's growth, and a full
                              build_battle() end-to-end). Also hero rivals:
                              every class has a persona, choose_hero_rivals'
                              bounds/uniqueness/rarity weights, a rival's
                              stats/kit/growth/name/persona come from its
                              own class, and build_battle() can field a mix
                              of monsters and rivals with enemy_hero_recruits
                              lined up correctly against enemies/enemy_ids
  rewards_test.py             game/rewards.py's roll_hero_enemy_shard_drops:
                              no drop below the roll chance or on a still-
                              alive enemy, a hit grants SHARDS_PER_DUPLICATE's
                              rarity-scaled amount to the matching *owned*
                              hero, and a rival for a hero you haven't
                              recruited yet is a silent no-op
  save_load_test.py          Save/load round-trips every field including
                              level/xp; a pre-level-curve save with no
                              level/xp keys at all loads and defaults to
                              level 1; atomic-write behavior;
                              compute_battle_rewards' money-always/
                              gems-and-xp-on-win rule and the exact
                              difficulty/size reward-multiplier formula
  shop_test.py               Headless coverage of game/shop.py -- buying,
                              stash vs. equipped, epic/legendary refused
  shop_screen_test.py        pygame_ui.py's show_shop tabs/buying against
                              the fake pygame module, and that there's no
                              "Gear" tab left at all (moved to Heroes)
  party_test.py               Headless coverage of game/party.py -- default
                              preselection (previous party filtered to
                              owned, else first 4), toggling past
                              MAX_PARTY_SIZE is a no-op, confirm_party
                              validates/saves/resolves in roster order and
                              rejects an empty or oversized selection,
                              de-dupes and drops unknown ids, and
                              active_party_characters (what the hub shows)
                              resolves the saved/default party in roster
                              order and is never just the whole roster once
                              it's capped
  heroes_test.py               Headless coverage of game/heroes.py --
                              upgrade_star spends the exact shard cost and
                              increments stars by 1, fails cleanly (no
                              partial spend) when short on shards or already
                              at MAX_STARS, rejects an unknown character id,
                              and walking a hero from 1 to MAX_STARS one
                              call at a time
  heroes_screen_test.py      pygame_ui.py's show_heroes (the card-grid
                              layout) against the fake pygame module --
                              selecting a card switches the detail panel,
                              the Upgrade Star button spends shards/
                              increments stars (and is a no-op when
                              unaffordable), the equip/unequip round trip
                              (ported from the old Gear-tab coverage), an
                              empty roster doesn't crash, mouse-wheel
                              scrolling past a one-screenful roster moves
                              the grid a whole row at a time (a hero only
                              reachable after scrolling is the one a click
                              at the first card slot selects), and
                              _get_portrait returns None with no matching
                              file (caller falls back to the drawn
                              placeholder) vs. a cached, correctly-scaled
                              Surface once a file is present
  summon_test.py             RECRUITABLE_ROSTER has exactly 5 names per
                              class (25 total, no duplicate pairs) with
                              exactly one hero per rarity per class, and
                              every recruit builds into a real level-1
                              character; headless coverage of
                              game/summon.py -- gem deduction, rarity-roll
                              weighting favors common over mythic as
                              expected, a pull matching an owned hero grants
                              shards instead of a new roster slot (and
                              shards accumulate correctly across repeated
                              duplicate pulls), and the epic/legendary
                              equipment weighting. As of the Summon-screen
                              redesign: the _X10 costs are exactly 10x the
                              single-pull cost, a batch spends its total
                              cost as one all-or-nothing lump sum (nothing
                              deducted if you can afford 9 pulls but not
                              10), a hero pulled twice within the *same*
                              10x batch is correctly treated as a duplicate
                              the second time (via a small fixed-output rng
                              double, since real randomness can't reliably
                              be seeded to repeat within one small batch),
                              and a batch's summary message names the
                              highest-rarity pull in it
  summon_screen_test.py      pygame_ui.py's show_summon against the fake
                              pygame module: switching banners, a 1x pull's
                              solo-card reveal and a 10x pull's grid reveal
                              (flipping one card at a time or all at once
                              via "Reveal All"), an unaffordable 10x pull
                              being genuinely unclickable while a cheaper 1x
                              pull still works, "Back to Colosseum" being a
                              no-op while a reveal is up (only the
                              select-screen's Back can actually leave), and
                              a guaranteed-duplicate pull (every recruitable
                              hero already owned) granting shards rather
                              than crashing or padding the roster
  game_loop_test.py          Integration coverage for main.py's title ->
                              character creation -> hub -> party select ->
                              Battle Setup -> battle loop, including backing
                              out of party select or Battle Setup skipping
                              the battle entirely, a real battle proving a
                              bystander left off the selected party earns no
                              XP, and the Heroes hub choice calling the real
                              show_heroes and saving (see that file's
                              docstring for why it's split into a
                              real-battle level and a scripted-fake-UI level)

main.py     Entry point / CLI -- title screen, character creation, and the
            Colosseum hub loop (New Game/Continue, Enter Battle -- now
            Choose Your Party then Battle Setup -- Shop, Summon, Heroes,
            Save & Quit, plus a debug-only "Add Gems" cheat button, see
            "Debug mode" above). run_one_battle() takes an optional `party`
            (the fielded PlayerCharacters) -- only they're built into the
            battle and earn XP; omitted, it falls back to the whole roster
config.py   Runtime settings (overridable via env vars or CLI flags): DEBUG_GEM_GRANT (the debug-only "Add Gems"
            cheat button's amount per click) and FULLSCREEN_ON_START
            (off by default; `--fullscreen` on the CLI overrides it)
```

## How the enemy AI works

`ai/enemy_ai.py` is a pure rule-based AI -- there is no model, no network and no external
service. `make_enemy_ai_fn(memory=None, on_decision=None)` returns the
`(combatant, state) -> Action` function the engine calls on each enemy turn.

**Utility scoring.** Every legal option (basic attack, each affordable skill against each
reachable target, defend) gets a score in rough "HP points": the damage it should do (capped
by what the target has left, with a bonus for a kill), the value of a debuff, poison or buff
that is not already in place, healing that is actually needed, and so on. Melee units can only
reach an occupied front row (battle formations); ranged and magic units reach anyone. A little
random noise (per profile) keeps enemies from being perfectly predictable.

**Behavior profiles.** The `PROFILES` table is keyed by enemy archetype id (`data/enemy_pool.py`).
A profile can set who the unit prefers to hit (`weakest`, `tank`, `caster`, `strongest`,
`balanced`), skills it opens with, how many living heroes make it prefer an area attack, when it
heals allies or braces, a finisher it saves for wounded targets, how much it favours debuffs, how
random it is, and whether it is `adaptive`. Hero rivals use a balanced adaptive profile.

**Telegraphed attacks.** Profiles with a `charge` skill sometimes spend a turn gathering power
instead of attacking: the unit braces (halving damage), gains the visible **Charging** status
(+60% attack and magic) and the log announces "gathers power for <skill>!". On its next turn it
releases that skill. Stun the unit (a missed turn breaks the charge), defend through the hit, or
spread the party out. Scripted bosses (`data/bosses.py`, `game/boss_script.py`) keep their own
hand-written phases and telegraphs on top of this.

**Rival adaptation.** Adaptive profiles (hero rivals, the Colosseum Champion, the Temple Oracle, the
Abyssal Horror, the Null Reaper) watch what the player does: they start hunting a healer who keeps
healing, focus the party's main damage dealer, and punish turtling (lots of defending) with debuffs
and area attacks. The memory dict is kept for the whole session and halved at the start of each new
fight (`decay_memory`), so a rival remembers recent habits without being locked into them forever.

`tests/enemy_ai_test.py` covers legal targeting, profiles, openers, healing, charging and breaking a
charge with a stun, rival adaptation and full battles.

## Verifying it works (what's already been tested)

Since this was built in a sandbox with no access to install pygame, verification so far is:
- `tests/headless_battle_test.py`: runs 25+ full battles with a scripted
  player stand-in and the *real* rule-based enemy AI, asserting no crashes, no invalid HP/MP, and that both win and
  loss are reachable.
- `tests/pygame_ui_smoke_test.py`: runs every menu path in `pygame_ui.py`
  (attack/skill/item/defend/flee, self-target and all-enemies skills), plus
  the hit/heal flash feedback (an HP drop/rise starts the right flash with
  the right sign and expires on schedule) and the end screen rendering an
  XP line plus per-character level-up lines without crashing, against a
  fake `pygame` module, so at least the logic is proven correct even though
  the visuals haven't been eyeballed yet. As of fix #19: `_is_melee_action`
  correctly classifies the basic Attack and a physical-kind skill (Cleave)
  as melee and a magical skill (Fireball), a status skill (Warcry),
  Defend, and Flee as not; `_melee_target_for` picks the action's own
  requested target when it's still alive, falls back to any living
  opponent when the requested id doesn't resolve, and returns `None` (so
  the caller skips the animation) when no opponent is left alive at all;
  `_resolve_action_with_movement` (the function `attach_engine` wraps
  `resolve_action` with) calls the engine's real resolution exactly once
  and always clears `self._mover` afterward, whether the action was melee
  (verified with a counting spy substituted for
  `BattleEngine.resolve_action` itself, so the wrapped call is checked
  end-to-end) or passed straight through untouched (a magical skill); and
  clicking a target's on-screen sprite rect (via `_sprite_click_targets`,
  the same helper `_draw_frame` itself uses) resolves to the exact same
  `Action` as clicking that target's row in the text menu.
- `tests/battle_sprites_test.py`: `_load_battler_sheet_raw`/
  `_get_battler_frames` correctly slice a character's own idle sheet into
  the full frame grid, fall back to (and reuse, not re-decode)
  `DEFAULT_BATTLER_NAME`'s sheet when a character has none of their own, and
  return `None` (not a crash) when no sheet exists at all; `facing="left"`
  mirrors the frames and `facing="right"` leaves them alone; frames scale to
  the requested height and are cached; the animation-frame clock stays in
  bounds; the background loader scales/caches correctly and degrades to
  `None` when the file's missing; and a lopsided 1-enemy-vs-4-party battle
  (one KO'd) renders through `_draw_frame` without crashing -- same "logic
  proven correct, visuals not yet eyeballed" caveat as everything else here.
  As of fix #21 (superseding fix #17's own version of this check): a full
  4-wide side stands in a front rank of two (feet on the
  `BATTLE_GROUND_BOTTOM_MARGIN` line) and a back rank of two
  (`BATTLE_GROUND_RANK_GAP` higher up, `BATTLE_GROUND_RANK_INSET_X` shifted
  toward the opposing side), every sprite drawn at the same fixed
  `BATTLE_SPRITE_H` regardless of how many share a side; a party side
  insets its back rank the opposite direction from an enemy side, both
  converging toward screen center. As of fix #22, those same position
  checks are looked up by combatant id rather than by draw-call order
  (since `_draw_battle_column` now draws back-to-front by y -- see right
  below), plus a new check that the back rank is drawn before the front
  rank so the front rank visually overlaps it, matching Andrew's "bottom
  row over the top row" ask. As of fix #18: `_draw_combatant` renders zero
  text (asserted by counting `font_small.render` calls while drawing one
  sprite), `_draw_party_status_panel` survives a KO'd member, a
  zero-`max_mp` character, and an empty party without crashing. The old
  "worst-case bottom UI stays clear of the sprite band" guarantee this
  section used to pin is gone as of fix #22 -- Andrew asked to bring the
  front rank down into the bottom panels' translucent space on purpose, so
  that test now instead pins that the front rank's feet line stays inside
  the window and confirms it does now overlap the command panel's title
  line, flagging (via a comment, not a silent pass) if a future layout
  change makes that stop being true.
  As of fix #19: a battler's own Run sheet loads and caches independently
  of its Idle sheet, and a pose it doesn't have art for yet falls back to
  its own Idle frames first, then to `DEFAULT_BATTLER_NAME`'s sheet for
  that same pose (not straight to `DEFAULT_BATTLER_NAME`'s Idle); a
  battler with no art of its own at all still gets
  `DEFAULT_BATTLER_NAME`'s Run sheet specifically when asked for Run;
  `_column_layout` (the layout math `_draw_battle_column` now shares with
  `_home_position`) agrees exactly with `_home_position`'s reported
  position for every combatant in a column; `_combatant_rect` falls back
  to the same 100-wide placeholder box `_draw_combatant` itself draws when
  no art is loaded; and `_draw_combatant`'s `frame_index` override clamps
  a way-out-of-range value into bounds instead of raising.
- `tests/leveling_test.py`: `data/leveling.py` in isolation -- the XP
  curve's exact per-level costs, `apply_growth` is a no-op at level 1 but
  correctly multiplies by levels-gained past that, `resolve_level_up`
  matches hand-worked examples including a single grant crossing two
  levels at once, and the `MAX_LEVEL` cap stops spending XP rather than
  accumulating it forever.
- `tests/battle_setup_test.py`: `data/enemy_pool.py`'s 13 archetypes are
  all valid (real skill ids, `Element` resistance keys, non-empty
  personas) and the original three enemies' level-1 stats are pinned
  exactly to `data/enemies.py`'s legacy values (so the pool never quietly
  retunes the fixture other tests balance-check against); and
  `game/battle_setup.py`'s difficulty-to-enemy-level offsets are sampled
  thousands of times per difficulty and checked against the ranges implied
  by Andrew's spec, enemy level is clamped to `[1, MAX_LEVEL]`,
  `choose_enemy_ids` respects the 1-4 opponent bounds and never repeats an
  archetype within one encounter, and a full `build_battle()` call
  produces a correctly-sized, correctly-leveled `BattleSetup`. Also hero
  rivals: every class has a persona, `choose_hero_rivals` respects bounds/
  uniqueness/rarity weighting, `build_hero_enemy_combatant` pulls its
  stats/kit/growth from the recruit's own class and labels it `"Rival
  <name>"`, and `build_battle()` correctly interleaves monster and rival
  slots (unique ids across the mix, `enemy_hero_recruits` lined up 1:1 with
  `enemies`/`enemy_ids`).
- `tests/rewards_test.py`: `roll_hero_enemy_shard_drops` grants no shards
  below its roll chance or against an enemy that's still alive, grants
  `SHARDS_PER_DUPLICATE`'s exact rarity-scaled amount to the matching
  *owned* hero on a hit, and is a silent no-op for a rival whose hero
  hasn't actually been recruited yet.
- `tests/engine_balance_test.py`: poison and regen actually tick real
  damage/healing (not just "gets applied and logged" -- see "Balance"
  above for the bug this catches), lifesteal actually heals the caster,
  plus targeted checks of stun skipping a turn, elemental
  weakness/resistance multipliers, item revival, and both flee outcomes.
- `tests/roster_test.py`: every class archetype's starting skill kit only
  references real skill ids and no two classes end up with an identical
  kit; an unknown `class_id` is rejected rather than silently accepted;
  `build_combatant` uses the archetype's kit/stats correctly; equipping and
  swapping gear applies (and correctly replaces, not stacks) stat bonuses,
  and `effective_stats`/`build_combatant` agree with each other; a
  reference to a nonexistent equipment id (e.g. from a stale save) is
  skipped rather than crashing character setup; new characters start at
  level 1/0 xp; `grant_xp` resolves level-ups correctly (including a
  single grant crossing more than one level, and carrying the leftover xp
  remainder); `effective_stats` applies level growth before equipment
  bonuses; level is clamped to `[1, MAX_LEVEL]` at construction.
- `tests/save_load_test.py`: a full save/load round-trip preserves every
  field (currencies, inventory, owned equipment, each character's id/name/
  class/equipped gear/level/xp/rarity/stars/shards, and
  `PlayerState.active_party`) and the reloaded character still works as
  a real character (`build_combatant` succeeds); a save file written
  before the level-curve pass (no `level`/`xp` keys) or before the
  hero-rarity pass (no `rarity`/`stars`/`shards`/`active_party` keys at
  all) still loads, defaulting each to level 1 / common-1-star-0-shards /
  an empty party respectively; saving is atomic (no `.tmp` file left
  behind, a second save correctly overwrites); `delete_save` is a no-op on
  a file that doesn't exist; `compute_battle_rewards` pays money on every
  outcome and gems+XP on victory only, sampled 200 times per outcome; the
  difficulty/size reward multiplier matches Andrew's own worked example
  (1 hero vs. 3 enemies = 1.5x, extreme = 3x) exactly.
- `tests/meta_screens_test.py`: the title screen only offers "Continue"
  when a save exists (and clicking where it *would* be otherwise is a
  no-op); character creation requires both a non-empty name and a chosen
  class before "confirm" is even clickable, supports backspace and
  re-picking a class, and Enter works as an alternate confirm; the
  Colosseum hub's 5 regular buttons (including "Heroes") each return the
  right value, and its debug-only "Add Gems" 6th button only ever appears
  when the UI was built with `debug=True` (and doesn't shift the other 5
  buttons' coordinates when it's absent); the Battle Setup screen returns
  the exact (difficulty, opponent count) clicked, backing out of the
  opponent-count step returns to the difficulty step rather than the hub,
  and backing out of the difficulty step returns `None`.
- `tests/party_select_screen_test.py` (fix #20, new -- Choose Your Party's
  old toggle-list coverage moved here once it got a card layout of its
  own): confirming with no clicks returns the default first-`MAX_PARTY_SIZE`
  preselection and persists it to `active_party`; clicking a filled
  top-strip slot removes that hero; clicking an unselected hero's card in
  the roster grid below adds them when there's room (with a party set up
  to start under-full, since a 4+-hero roster's *default* preselection
  already fills every slot -- adding a 5th on top of that is a separate,
  intentionally-rejected case, covered next); clicking a *selected* hero's
  roster-grid card (not just their strip slot) also removes them, proving
  both representations drive the same toggle; trying to add a 5th hero on
  top of a full party is a no-op; backing out returns `None` without
  touching `active_party`; and a roster with empty "+" slots, or with no
  heroes at all, doesn't crash the screen.
- `tests/shop_test.py`: headless coverage of `game/shop.py` -- buying an
  item/equipment deducts money and adds the right stash/inventory entry;
  buying fails cleanly (no partial deduction) when too poor or given an
  unknown id; epic/legendary (`cost=0`) equipment is refused as
  summon-only; equipping from the stash moves the item onto a character
  and returns whatever was equipped there before back to the stash
  (verified across a weapon swap); unequipping returns the item to the
  stash; every function rejects an unknown character id the same way.
- `tests/shop_screen_test.py`: drives `ui/pygame_ui.py`'s `show_shop`
  through the fake pygame module -- the Items tab is the default and
  buying there updates money/inventory; switching to a gear-buying tab and
  buying adds to the stash without auto-equipping; a purchase you can't
  afford isn't clickable at all (money/inventory unchanged); clicking
  where the old "Gear" tab used to sit is a no-op (there's no equip
  surface left in Shop at all -- see `tests/heroes_screen_test.py` for
  where that coverage moved); the Back button returns with no side
  effects.
- `tests/party_test.py`: `default_party_ids` falls back to the first
  `MAX_PARTY_SIZE` roster members with no previous selection, prefers a
  previous selection filtered to still-owned ids, and falls back again
  when that filtered selection is empty; `toggle_member` adds/removes
  correctly and refuses (no-op, `changed=False`) past `MAX_PARTY_SIZE`;
  `confirm_party` saves `active_party` and resolves the party in roster
  order regardless of pick order, rejects an empty or oversized selection
  without touching `active_party`, and de-dupes/drops unknown ids;
  `active_party_characters` (what the Colosseum hub actually shows)
  prefers the saved `active_party`, falls back to the same default the
  selection screen would pre-check, and is confirmed to stay capped at
  `MAX_PARTY_SIZE` rather than quietly falling back to the whole roster.
- `tests/heroes_test.py`: `upgrade_star` spends the exact shard cost for
  the hero's rarity/current star and increments stars by exactly 1; fails
  cleanly (no partial spend) when short on shards or already at
  `MAX_STARS`; rejects an unknown character id; walking a hero from 1
  star to `MAX_STARS` one call at a time exercises every entry in a
  rarity's shard-cost table.
- `tests/heroes_screen_test.py`: drives `ui/pygame_ui.py`'s `show_heroes`
  (the Mobile-Legends-Adventure-style card grid) through the fake pygame
  module -- the first hero is selected by default and Back exits cleanly;
  selecting a different card switches the detail panel (and an upgrade
  click applies to *that* hero, leaving others untouched); the Upgrade
  Star button spends shards and increments stars when affordable, and is
  genuinely unclickable (not just rejected after the fact) when it isn't;
  the equip-then-unequip round trip (ported from the old Shop Gear-tab
  coverage) leaves the character and stash back where they started; an
  empty roster doesn't crash the screen; scrolling a 20-hero roster with
  the mouse wheel moves the grid a whole row at a time and actually moves
  which heroes are reachable (a hero only visible after scrolling down is
  the one a click at the first card slot selects), not just an offset
  number nobody can see; and `_get_portrait` returns `None` for a hero
  with no matching file in `data/portraits/` (so the caller draws the
  placeholder silhouette instead) but a real, correctly-scaled, cached
  `Surface` once a matching file exists.
- `tests/summon_test.py`: `RECRUITABLE_ROSTER` has exactly 5 names per
  class (25 total, no duplicate name+class pairs) with exactly one hero
  per rarity per class, and every one of them builds into a real, working
  level-1 `PlayerCharacter`; headless coverage of `game/summon.py` -- a
  character summon deducts the right gem cost, the rolled rarity matches
  the returned recruit's, and rarity-roll weighting favors common over
  mythic as expected over thousands of pulls; it fails cleanly (no
  deduction) when too poor; a pull matching an already-owned hero grants
  hero shards to that hero instead of adding a new roster slot (and
  repeated duplicate pulls accumulate shards correctly); an equipment
  summon deducts its own gem cost and always lands a `cost<=0`
  (epic/legendary) item in the stash, never auto-equipped; it also fails
  cleanly when too poor; sampled over many pulls, only epic/legendary
  equipment rarities ever come out, and epic is confirmed to be weighted
  heavier than legendary. As of the Summon-screen redesign: the `_X10`
  costs are exactly 10x the single-pull cost; a 10x batch spends its total
  cost as one all-or-nothing lump sum (can't afford 9 pulls but not 10 ->
  nothing happens, not a partial deduction); a hero pulled a second time
  within the *same* batch is correctly flagged as a duplicate (verified
  with a small fixed-output rng double, since real randomness can't
  reliably be seeded to repeat within a 3-pull batch); and a batch's
  summary message correctly names the single highest-rarity pull in it.
- `tests/summon_screen_test.py`: drives `ui/pygame_ui.py`'s `show_summon`
  through the fake pygame module -- switching between the Hero Summon and
  Gear Summon banners; a 1x pull's solo-card reveal correctly recruits/
  adds-to-stash once "Continue" is clicked; a 10x pull's grid reveal
  (flipping one card individually, then "Reveal All" for the rest, then
  "Continue") correctly applies all 10 pulls; an unaffordable 10x pull is
  genuinely unclickable (not just rejected after the fact) while a
  cheaper 1x pull on the same banner still works; clicking where "Back to
  Colosseum" would be *during* a reveal is a harmless no-op -- exactly one
  pull happens, not zero or two -- proving Back really is unavailable
  outside the select view; a guaranteed-duplicate pull (every recruitable
  hero already owned) still deducts gems and grants shards without adding
  a new roster slot or crashing; and the Back button (from the select
  view) returns with no side effects.
## Known limitations / next steps

- ~~Balance is a first pass.~~ -- tuned: see the "Balance" section above. Win rates were
  re-measured after the rule-based AI replaced the old heuristic; keep tuning `data/enemies.py`,
  `data/enemy_pool.py` and the `PROFILES` table in `ai/enemy_ai.py` as you play.
- ~~No character creation, save/load, or Colosseum meta-layer~~ -- built:
  see "Character creation, the Colosseum hub, and saving" above.
- ~~No Shop~~ -- built: see "The Shop" above (buy consumables and
  common/rare gear with money, equip/unequip from a stash).
- ~~No Summon~~ -- built: see "Summon" above (recruit a new roster
  character, or draw a random piece of premium epic/legendary equipment,
  both with gems). This was the last piece of the original request --
  every stage (title/chargen/save-load/hub/economy/Shop/Summon) now
  exists and is wired together in `main.py`'s game loop. What's left is
  polish and depth, not missing features:
  - ~~Only one Colosseum "tier" exists~~ -- built: Battle Setup lets you
    pick difficulty (Easy/Normal/Hard/Extreme) and opponent count (1-4)
    before every fight, and opponents are drawn at random from a
    13-archetype pool with enemy level scaled to your party's average
    level -- see "Level curves & battle difficulty" above. Still worth
    tuning further once it's been played for real: the difficulty-offset
    numbers (`game/battle_setup.py`) are one reading of an ambiguously
    worded spec, and the XP/growth curves (`data/leveling.py`,
    `data/classes.py`, `data/enemy_pool.py`) are hand-picked, not
    playtested.
  - ~~No squad-size cap or bench~~ -- built: a 4-hero party cap plus a
    Choose Your Party screen before every battle (see "Party selection"
    above). Only your fielded party fights/earns XP/counts toward
    `game/rewards.py`'s `size_modifier` now -- an unfielded roster no
    longer drags the reward multiplier down just by existing, the way it
    did when "party size" meant "whole roster."
  - ~~`RECRUITABLE_ROSTER` duplicates just start repeating~~ -- built into
    something better: as of the hero-rarity pass, every recruitable hero
    now has one of 5 rarities (common/rare/epic/legendary/mythic, one per
    class per rarity) with its own summon odds, and a duplicate pull grants
    hero shards (spendable on a star upgrade via the Heroes page) instead
    of either failing or silently repeating -- see "Summon"/"Heroes page"
    above.
  - Summon costs (`CHARACTER_SUMMON_COST`/`EQUIPMENT_SUMMON_COST`), the
    equipment epic-vs-legendary pull weighting, and the whole shard/star
    economy (`SHARDS_PER_DUPLICATE`, `SHARD_COST_FOR_STAR`,
    `STAR_STAT_BONUS_PER_LEVEL`) are still first-pass numbers, hand-picked
    rather than tuned against real play -- worth revisiting once this has
    been played for a while, same spirit as the difficulty-offset and
    XP-curve numbers already flagged elsewhere in this file. The
    hero-rarity odds (`HERO_SUMMON_WEIGHTS`) already got one tuning pass
    after real play (see "Summon" above -- the original "standard gacha
    curve" felt too generous at the top end, legendary/mythic got cut
    hardest), but are still just a second guess, not a final answer.
  - ~~The Heroes screen's hero list has no scrolling~~ -- fixed: the list
    now scrolls with the mouse wheel once the roster is taller than the
    window, with "N more above/below" hints (see "Heroes page" above).
  - ~~Hero characters can't show up as enemies~~ -- built: see "Hero
    rivals" above (per-slot 25% chance, rarity-weighted which hero, class-
    kit stats, a 15% shard-drop chance on defeat for a hero you've already
    recruited). Both the 25% encounter chance and the 15% drop chance are
    first-pass, hand-picked numbers, same as the difficulty-offset and
    hero-rarity odds already flagged elsewhere in this file -- worth
    retuning once you've actually run into a few. Whether an *unrecruited*
    rival should offer some other payout (nothing currently happens beyond
    a normal fight) is also worth a look once this has been played.
  - Enemies within one encounter are chosen *without* replacement (no
    duplicate archetype twice in the same fight) -- reasonable with a
    13-archetype pool and a 4-opponent cap, but would need revisiting
    (sampling with replacement) if the pool ever shrinks below 4.
  - XP is awarded on victory only, same as gems -- a loss or flee grants
    no XP even though it still pays money. Andrew's spec didn't say either
    way; this follows gems' existing precedent rather than inventing a
    new rule, but is worth confirming once it's been played.
- `data/characters.py` (the original fixed four-person party) and
  `data/enemies.py` (the original fixed enemy trio) are both hand-written
  legacy sample rosters now -- neither is what you actually play with
  (real play uses `data/summon_pool.py`/character creation and
  `data/enemy_pool.py` respectively, see "Playing a battle" and "Level
  curves & battle difficulty" above), but both remain fixtures several
  tests build on and are deliberately left untouched.
- ~~No battle sprites, colored rectangles only~~ -- built: every combatant
  now plays a looping idle-animation sheet (currently one shared placeholder,
  "Draven", standing in for every character -- see "Playing a battle"
  above), laid out as a side-view duel (enemies left, party right, mirrored
  to face each other) over a full-bleed background. ~~Actions still resolve
  instantly with no attack/movement animation -- everyone just idles in
  place, even mid-action~~ -- see fix #19 right below for melee movement. A
  hit or heal still gets a flash + floating damage/heal number so it's not
  silent besides the log and bars. Worth a follow-up once Andrew's added
  more real per-character sheets (currently only Draven has Idle/Run/Melee
  art -- everyone else still falls back to it).
- ~~A full battle column ran a sprite off the bottom of the window, and the
  bottom log panel sat on top of the lowest sprite~~ -- see fix #17. The
  combat log moved from the bottom of the screen to just under the round
  counter at the top; the action menu is unaffected and still anchors to
  the bottom. ~~Each column staggered every other fighter sideways and
  compressed its own row spacing (and, if a full 4-wide column still
  needed it, the sprite height itself down to `BATTLE_SPRITE_MIN_H`) so
  every fighter stayed fully on-screen~~ -- see fix #21 right below:
  Andrew asked for that compression to go away entirely, and for fighters
  to stand on the ground instead, so this whole scheme (and both open
  questions it left -- whether the compressed size and the stagger amount
  read well) is moot now; replaced by the fixed-size, ranked ground
  layout.
- ~~Battle UI had opaque panels, per-sprite name/HP/MP boxes, and a
  4-column button grid~~ -- see fix #18. Every battle panel (log, command
  list, party status) is now translucent so the backdrop shows through;
  sprites render with no text/box on or around them at all; party HP/MP
  moved into a new bottom-right status panel; and the button grid is a
  single-column list, matching the reference screenshot Andrew sent. **TP
  was deliberately not added** -- the engine only has HP/MP, no TP
  resource to display -- worth a conversation with Andrew if he wants one
  added at the engine level. The exact pixel spacing/colors/alpha in the
  new panels (`BATTLE_PANEL_ALPHA`, `BATTLE_STATUS_PANEL_COLOR`, etc.) are
  a first pass, not yet seen in the real pygame window -- easy to retune
  once he's played it.
- ~~Heroes page was a plain scrollable list, no portrait art~~ -- built:
  the Heroes page now renders a Mobile-Legends-Adventure-style scrollable
  card grid, and loads real portrait art from `data/portraits/` per hero
  (falling back to a drawn placeholder silhouette when no file matches) --
  see "Heroes page" above. This was scoped to the Heroes page only, as a
  first slice -- worth a look at whether other screens want the same
  treatment now that Summon has followed (below).
- ~~Summon was a flat two-button screen with an instant text reveal, no
  10x pull~~ -- built: Summon is now a Mobile-Legends-Adventure-style
  banner-rail + splash-panel screen with a card-flip reveal animation (a
  big solo card for a 1x pull, a 5-wide flip-one-or-reveal-all grid for a
  new 10x pull), see "Summon" above. Andrew's original ask ("upgrade the
  UI to a more Mobile Legends Adventure style") named the Heroes page
  specifically and didn't explicitly ask for Summon too -- this pass was
  scoped to Summon on the strength of the reference screenshots he sent
  (a Summon screen and its reveal grid), not a direct instruction, so
  it's worth confirming this matched what he had in mind. Battle has
  since gotten its own visual pass too (see the sprite bullet above) --
  the Colosseum hub and Shop are what's left with the original
  placeholder-rect look.
- ~~The battle background was being used as the battle backdrop for now at
  Andrew's suggestion, but by his own account it was actually made for the
  game's main/title screen~~ -- resolved as of fix #21: Andrew replaced
  `data/Artwork/Background.webp` with new art made specifically for the
  battle engine (an arena-floor scene, see fix #21 above), and kept the
  old title-screen-style vista around as `data/Artwork/Background1.webp`
  for reference/backup rather than deleting it. `BATTLE_BG_PATH` itself is
  unchanged (still points at `Background.webp`) since only the file's
  content was swapped, not its location.
- ~~The pygame window felt small~~ -- the default window grew from
  1000x650 to 1280x800, and `_draw_frame`'s log/menu/button block (the
  main battle screen) now anchors off `self.height` instead of a fixed
  pixel offset, so it uses the extra room instead of leaving a dead gap at
  the bottom. A real fullscreen mode is also available now (`--fullscreen`
  or `FULLSCREEN_ON_START=1`, off by default) -- it scales that same
  1280x800 layout up to fill your monitor via pygame's `SCALED` flag
  rather than trying to make every screen's coordinates adapt to an
  arbitrary resolution, so nothing about the layout itself changes between
  windowed and fullscreen. Still first-pass sizing -- worth a look once
  it's been played on your actual monitor.
- ~~No melee movement -- attacks resolved standing still, and you could
  only target by name from the text menu, never by clicking a sprite~~ --
  see fix #19 above: the basic Attack and any physical-kind skill now run
  the attacker over to its target, play a swing, and run back, using
  Draven's new Run/Melee art (falling back to Idle for anyone else, same
  as before); and a combatant's own sprite is now clickable as a target
  wherever the text menu already offers it as one. Magical/heal/status
  skills and item/defend/flee are unaffected, still instant. Worth a
  follow-up once more characters have their own Run/Melee sheets (not just
  Draven), and the run-speed/swing-speed/impact-frame numbers
  (`BATTLE_RUN_SPEED`, `BATTLE_MELEE_ANIM_FPS`, `BATTLE_MELEE_IMPACT_FRACTION`,
  etc. -- see the "Melee movement (fix #19)" constants block in
  `ui/pygame_ui.py`) are all first-pass, eyeballed-not-played numbers. Also
  worth deciding later whether a *ranged* physical skill (Piercing Shot is
  currently lumped in as "melee" since it's `kind == "physical"`) should
  get its own non-running animation treatment instead of running the
  attacker all the way up to its target.
- ~~Choose Your Party was a plain checkbox-style toggle-list, out of step
  with the rest of the now-card-based UI~~ -- see fix #20. It's now a
  Heroes-page-style card screen: a fixed top strip shows the current
  party (with empty "+" slots for open spots), and a scrollable card grid
  below it lists every owned hero, bordered when they're in the party --
  clicking a portrait anywhere (top strip or grid) adds or removes that
  hero, no separate select-then-confirm step. Andrew's own wording drove
  the design directly: "look more like the heroes screen ... click on the
  portraits." Both this screen and the Heroes page's own grid now draw
  their cards through one shared `_draw_hero_card` helper, so the two
  can't silently drift apart visually. `ui/text_ui.py`'s numbered-menu
  version is unchanged -- there's no portrait to click there.
- ~~Battle sprites were laid out in a tall single-file column per side,
  staggered and shrunk to fit a crowded band, over background art that
  wasn't really meant for the battle screen~~ -- see fix #21. Andrew
  replaced `data/Artwork/Background.webp` with new art made for the
  battle engine specifically -- an arena-floor scene with a visible
  perspective floor converging toward a vanishing point at back-center
  (the old vista is kept as `Background1.webp` for reference) -- and
  asked for fighters to stand on that floor instead of stacking
  vertically ("reposition the fighters to appear on the ground instead...
  closer to a 2.5D perspective"), and for the old shrink-to-fit to go away
  entirely ("remove the shrinking of the heroes"). Each side now stands in
  up to two ranks of up to two fighters each -- a front rank near the
  bottom of the playfield, a back rank higher up and shifted toward the
  opposing side, echoing the floor's converging tile lines -- and every
  sprite always draws at the same fixed size (`BATTLE_SPRITE_H`), never
  shrunk regardless of how many share a side. `_home_position`,
  `_sprite_click_targets`, and the fix #19 run-in/swing/run-back melee
  animation all needed no changes at all, since they only ever consume
  whatever `(x, y, sprite_h)` `_column_layout` hands them. **Update, fix
  #22:** Andrew did look at this against the real art and came back with
  concrete tuning feedback, so the "not yet confirmed" question above is
  resolved -- see fix #22 right below for what changed
  (`BATTLE_ENEMY_COL_X`, `BATTLE_GROUND_BOTTOM_MARGIN`, and
  `BATTLE_GROUND_RANK_GAP` all got retuned, plus draw order). The
  "floating back rank" question wasn't specifically called out in that
  feedback, so it's still only worth a second look once Andrew plays
  another round against the fix #22 numbers.
- ~~As of fix #21, Andrew hadn't yet seen the ground-standing ranked
  layout rendered against his real background art, so the rank
  spacing/inset numbers and the back-rank "floating" question were open~~
  -- see fix #22. Andrew's follow-up feedback: "bring the bottom rows down
  80px or so and bring everyone closer to the center about 100px maybe
  spread the front row from the back row 20 more px or so, also we need
  the bottom row to show over the top row." All four landed as constant
  changes plus one behavioral fix in `ui/pygame_ui.py`: `BATTLE_ENEMY_COL_X`
  230 -> 330 (~100px toward screen center, both sides),
  `BATTLE_GROUND_BOTTOM_MARGIN` 230 -> 150 (front rank ~80px further down),
  `BATTLE_GROUND_RANK_GAP` 96 -> 116 (~20px more separation between ranks),
  and `_draw_battle_column` now sorts its layout entries by `y` ascending
  before drawing (a simple painter's-algorithm z-order) so the front
  rank's sprites visually overlap/occlude the back rank's wherever their
  boxes cross on screen, instead of the reverse. One side effect worth
  flagging: dropping the front rank's feet line down means it now
  intentionally overlaps the bottom command/status panels' top edge --
  those panels are translucent and drawn after sprites, so a fighter
  should read as standing partly behind the UI rather than being visually
  clipped, but this is exactly the kind of thing that's easy to misjudge
  without seeing it rendered. **Not yet confirmed with Andrew** whether
  the new numbers and the front-rank/panel overlap actually read well in
  the real pygame window -- this sandbox still has no real art to render
  against, only logic verified against a fake pygame module and hand-
  checked geometry.
#   B A 
 
 
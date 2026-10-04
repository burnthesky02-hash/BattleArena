"""Entry point for the Battle Colosseum prototype.

Run the full game (graphical placeholder window):
    python main.py

Run in a plain terminal (no pygame needed):
    python main.py --mode text

The flow is: title screen -> (New Game: create a character) or (Continue:
load the last save) -> the Colosseum hub -> Enter Battle (repeatable) ->
back to the hub, until you choose "Save & Quit to Title". See
game/player_state.py and game/save_system.py for what persists.
"""
import argparse

import config
from ai.enemy_ai import decay_memory, make_enemy_ai_fn, new_rival_memory
from data.classes import CLASS_ARCHETYPES, CLASS_IDS
from data.equipment_db import EQUIPMENT
from data.items_db import ITEMS
from data.skills_db import SKILLS
from engine.battle import BattleEngine
from engine.types import BattleResult
from game import save_system
from game.battle_setup import build_battle
from game.player_state import PlayerState
from game.roster import PlayerCharacter
from game.rewards import compute_battle_rewards, roll_hero_enemy_shard_drops


# One rival memory for the whole session: adaptive enemies (hero rivals, champions...) remember
# how you play from fight to fight (halved at the start of each new fight -- see ai/enemy_ai.py).
RIVAL_MEMORY = new_rival_memory()


def run_one_battle(ui, player_state: PlayerState, difficulty: str, num_enemies: int,
                    party=None):
    """Builds a fresh BattleEngine from `party` (a list of PlayerCharacter --
    see game/party.py's show_party_select flow) and a random
    difficulty/size-matched enemy encounter (see game/battle_setup.py), runs
    one full battle, then applies the difficulty/size-scaled money+gems+XP
    reward (see game/rewards.py) and persists whatever the battle consumed
    from inventory. `party` defaults to the whole roster when omitted, which
    is only the old pre-party-cap behavior for callers that don't care
    (namely tests/game_loop_test.py's direct run_one_battle call) -- the
    real hub flow in run_game_loop always passes an explicit, <=4-hero
    party. Returns (BattleResult, money, gems, xp_per_character, level_ups)
    where level_ups is {character_name: levels_gained} for anyone in `party`
    who leveled up (only nonzero entries) -- characters who didn't fight
    this battle earn no XP from it."""
    party = player_state.characters if party is None else party
    setup = build_battle(party, EQUIPMENT, difficulty, num_enemies)
    decay_memory(RIVAL_MEMORY)
    get_enemy_action = make_enemy_ai_fn(
        memory=RIVAL_MEMORY,
        on_decision=lambda record: ui.print_line(record["message"]) if record.get("message") else None,
    )

    def get_party_action(combatant, state):
        action = ui.get_party_action(combatant, state)
        get_enemy_action.observe(combatant, action)     # rivals learn from how you play
        return action
    engine = BattleEngine(
        party=setup.party, enemies=setup.enemies, skills_db=SKILLS, items_db=ITEMS,
        inventory=dict(player_state.inventory),
        get_party_action=get_party_action, get_enemy_action=get_enemy_action,
        on_event=ui.print_line,
    )
    ui.reset_battle_view()
    ui.attach_engine(engine)
    result = engine.run()

    if result == BattleResult.VICTORY:
        # Hero rivals (see game/battle_setup.py's HERO_ENEMY_CHANCE) that were
        # actually in this fight get a shot at dropping shards for themselves
        # -- printed straight into the battle log the player's already
        # looking at, rather than plumbed through as another return value
        # (see game/rewards.py's roll_hero_enemy_shard_drops docstring).
        defeated_hero_enemies = [
            (recruit, enemy) for recruit, enemy in zip(setup.enemy_hero_recruits, setup.enemies)
            if recruit is not None
        ]
        for message in roll_hero_enemy_shard_drops(defeated_hero_enemies, player_state):
            ui.print_line(message)

    player_state.inventory = dict(engine.inventory)  # potions/ethers/etc. consumed during battle stick
    money, gems, xp = compute_battle_rewards(
        result, difficulty=difficulty, num_heroes=setup.num_heroes, num_enemies=setup.num_enemies,
    )
    player_state.add_rewards(money, gems)
    level_ups = {}
    if xp:
        for character in party:
            gained = character.grant_xp(xp)
            if gained:
                level_ups[character.name] = gained
    return result, money, gems, xp, level_ups


def _announce_end(ui, result, money: int, gems: int, xp: int = 0, level_ups: dict = None) -> None:
    if hasattr(ui, "show_end_screen"):
        ui.show_end_screen(result.value, money=money, gems=gems, xp=xp, level_ups=level_ups, quit_on_close=False)
    else:
        ui.announce_result(result.value, money=money, gems=gems, xp=xp, level_ups=level_ups)


def run_game_loop(ui) -> None:
    """New Game / Continue / Quit at the title screen, then the Colosseum
    hub loop (Enter Battle / Shop / Summon / Heroes / Save & Quit to Title)
    for as long as the player keeps playing. Returns once the player quits
    from the title screen; the window itself is torn down by main()."""
    while True:
        has_save = save_system.save_exists()
        choice = ui.show_title_screen(has_save)
        if choice == "quit":
            return

        player_state = None
        if choice == "continue" and has_save:
            try:
                player_state = save_system.load_game()
            except Exception as exc:  # noqa: BLE001 - a corrupt/old save must never crash the game
                print(f"[warn] Could not load the save file ({exc}); starting a new game instead.")
                player_state = None

        if player_state is None:
            name, class_id = ui.show_character_creation(CLASS_ARCHETYPES, CLASS_IDS)
            hero = PlayerCharacter(name=name, class_id=class_id)
            player_state = PlayerState.new_game(hero)
            save_system.save_game(player_state)

        hub_choice = None
        while hub_choice != "quit_to_title":
            hub_choice = ui.show_colosseum_hub(player_state, EQUIPMENT)
            if hub_choice == "battle":
                # Party cap: pick which (up to MAX_PARTY_SIZE) heroes actually
                # fight before difficulty/opponent-count (see game/party.py).
                # Backing out of either screen returns None/empty and drops
                # straight back to the hub without fighting, same convention
                # show_battle_setup already used on its own back button.
                party = ui.show_party_select(player_state, EQUIPMENT)
                if not party:
                    continue
                setup_choice = ui.show_battle_setup(player_state, party)
                if setup_choice is None:
                    continue  # player backed out to the hub without fighting
                difficulty, num_enemies = setup_choice
                result, money, gems, xp, level_ups = run_one_battle(
                    ui, player_state, difficulty, num_enemies, party,
                )
                _announce_end(ui, result, money, gems, xp, level_ups)
                save_system.save_game(player_state)
            elif hub_choice == "shop":
                ui.show_shop(player_state, ITEMS, EQUIPMENT)
                save_system.save_game(player_state)
            elif hub_choice == "summon":
                ui.show_summon(player_state, EQUIPMENT)
                save_system.save_game(player_state)
            elif hub_choice == "heroes":
                ui.show_heroes(player_state, EQUIPMENT)
                save_system.save_game(player_state)
            elif hub_choice == "debug_add_gems":
                # Debug-only cheat button (only ever offered by show_colosseum_hub
                # when --debug/DEBUG=1 is on) -- grants gems on the spot so Summon's
                # gacha pulls can be tested/spammed without grinding out real
                # battles for gems first. See config.DEBUG_GEM_GRANT.
                player_state.add_rewards(0, config.DEBUG_GEM_GRANT)
                save_system.save_game(player_state)
        save_system.save_game(player_state)


def run_pygame_mode(args) -> None:
    from ui.pygame_ui import PygameUI  # raises ImportError here if pygame isn't installed
    ui = PygameUI(SKILLS, ITEMS, debug=args.debug, fullscreen=args.fullscreen)
    try:
        run_game_loop(ui)
    finally:
        ui.pygame.quit()


def run_text_mode(args) -> None:
    from ui.text_ui import TextUI
    ui = TextUI(SKILLS, ITEMS, debug=args.debug)
    run_game_loop(ui)


def main() -> None:
    parser = argparse.ArgumentParser(description="Battle Colosseum -- battle engine prototype")
    parser.add_argument("--mode", choices=["pygame", "text"], default="pygame",
                         help="pygame = graphical placeholder window, text = plain terminal")
    parser.add_argument("--debug", action="store_true", default=config.DEBUG,
                         help="Enable debug tools (Add Gems button, extra console lines)")
    parser.add_argument("--fullscreen", action="store_true", default=config.FULLSCREEN_ON_START,
                         help="Launch the pygame window fullscreen (scaled to fill your monitor) "
                              "instead of windowed. Ignored in --mode text.")
    args = parser.parse_args()

    if args.mode == "pygame":
        try:
            run_pygame_mode(args)
            return
        except ImportError:
            print("pygame isn't installed (run: pip install -r requirements.txt). Falling back to text mode.\n")
    run_text_mode(args)


if __name__ == "__main__":
    main()

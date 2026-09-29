"""Entry point for the Battle Colosseum prototype.

Run the full game (graphical placeholder window):
    python main.py

Run in a plain terminal (no pygame needed):
    python main.py --mode text

Point at a different Ollama host/model:
    python main.py --host http://localhost:11434 --model llama3.1

The flow is: title screen -> (New Game: create a character) or (Continue:
load the last save) -> the Colosseum hub -> Enter Battle (repeatable) ->
back to the hub, until you choose "Save & Quit to Title". See
game/player_state.py and game/save_system.py for what persists.
"""
import argparse

import config
from ai.enemy_ai import make_enemy_ai_fn
from ai.ollama_client import OllamaClient, OllamaError
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


def _normalize(name: str) -> str:
    # "gemma3:27b" vs "gemma3:27b" is an exact match, but Ollama often adds an
    # implicit ":latest" that people leave off when typing --model, so ignore
    # that specific tag when comparing.
    return name[:-len(":latest")] if name.endswith(":latest") else name


def setup_ollama_client(ollama_host: str, ollama_model: str) -> OllamaClient:
    """Connects, sanity-checks the model name, and warms it up once up front
    -- all of this used to happen inside build_engine() (i.e. once per
    battle); now that a session can run many battles in the Colosseum hub
    loop, it happens exactly once at startup instead, and every battle
    reuses the same already-warm client."""
    client = OllamaClient(
        host=ollama_host, model=ollama_model, timeout=config.OLLAMA_TIMEOUT_SECONDS,
        num_predict=config.OLLAMA_NUM_PREDICT, keep_alive=config.OLLAMA_KEEP_ALIVE,
    )
    if not client.is_available():
        print(f"[warn] Could not reach Ollama at {ollama_host}. Enemies will use the scripted "
              f"fallback AI until Ollama is running there (try: ollama serve).")
        return client

    available = client.list_models()
    wanted = _normalize(ollama_model)
    if available and not any(_normalize(m) == wanted for m in available):
        print(f"[warn] Ollama is reachable at {ollama_host}, but no pulled model matches "
              f"'{ollama_model}'.")
        print(f"       Models actually available: {', '.join(available)}")
        print(f"       Re-run with the exact name, e.g.: python main.py --model \"{available[0]}\"")
        print(f"       Enemies will use the scripted fallback AI until this is fixed.")
        return client

    print(f"[ok] Connected to Ollama at {ollama_host}, using model '{ollama_model}'.")
    if config.WARM_UP_ON_START:
        # Loading a large model's weights can itself take a long time (well past
        # a normal in-battle timeout) and produces no streamed output while it
        # happens -- paying that cost here once, with its own generous timeout,
        # means every battle this session only ever hits the fast already-warm
        # path (see OllamaClient.warm_up).
        print(f"[info] Warming up '{ollama_model}' (loading it into memory -- this can take a "
              f"while for a large model, especially the first time). Set WARM_UP_ON_START=0 to skip.")
        try:
            load_seconds = client.warm_up()
            print(f"[ok] Model loaded in {load_seconds:.1f}s -- will stay warm for "
                  f"{config.OLLAMA_KEEP_ALIVE} of inactivity.")
        except OllamaError as exc:
            print(f"[warn] Warm-up failed ({exc}). Enemies will still try the LLM on their turn, "
                  f"but the first one may be slow or fall back.")
    return client


def run_one_battle(ui, player_state: PlayerState, client: OllamaClient, difficulty: str, num_enemies: int,
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
    get_enemy_action = make_enemy_ai_fn(
        client, use_fallback_on_error=config.AI_FALLBACK_ON_ERROR, on_decision=ui.on_ai_event,
    )
    engine = BattleEngine(
        party=setup.party, enemies=setup.enemies, skills_db=SKILLS, items_db=ITEMS,
        inventory=dict(player_state.inventory),
        get_party_action=ui.get_party_action, get_enemy_action=get_enemy_action,
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


def run_game_loop(ui, client: OllamaClient) -> None:
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
                    ui, player_state, client, difficulty, num_enemies, party,
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
    client = setup_ollama_client(args.host, args.model)
    try:
        run_game_loop(ui, client)
    finally:
        ui.pygame.quit()


def run_text_mode(args) -> None:
    from ui.text_ui import TextUI
    ui = TextUI(SKILLS, ITEMS, debug=args.debug)
    client = setup_ollama_client(args.host, args.model)
    run_game_loop(ui, client)


def main() -> None:
    parser = argparse.ArgumentParser(description="Battle Colosseum -- battle engine prototype")
    parser.add_argument("--mode", choices=["pygame", "text"], default="pygame",
                         help="pygame = graphical placeholder window, text = plain terminal")
    parser.add_argument("--host", default=config.OLLAMA_HOST, help="Ollama server URL")
    parser.add_argument("--model", default=config.OLLAMA_MODEL, help="Ollama model name for enemy AI")
    parser.add_argument("--debug", action="store_true", default=config.DEBUG,
                         help="Show a live panel (pygame) or extra console lines (text) with what "
                              "the model is 'thinking' and how long each enemy decision takes")
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

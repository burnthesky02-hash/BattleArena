"""A plain-terminal battle UI. No dependencies beyond the stdlib, so this is
also what the headless tests drive the engine with (a scripted stand-in
replaces get_party_action there; humans use TextUI.get_party_action).
"""
from engine.actions import Action


class TextUI:
    def __init__(self, skills_db, items_db, debug: bool = False):
        self.skills_db = skills_db
        self.items_db = items_db
        self.debug = debug

    # Wire this in as on_event=ui.print_line for live commentary.
    def print_line(self, message: str) -> None:
        print(message)

    def render_battlefield(self, state: dict) -> None:
        print("\n" + "=" * 50)
        print(f" Round {state['round']}")
        print("-" * 50)
        print(" Your Party:")
        for p in state["party"]:
            tag = "" if p["alive"] else " [KO]"
            statuses = f" ({', '.join(p['statuses'])})" if p["statuses"] else ""
            print(f"   {p['name']:<10} HP {p['hp']:>4}/{p['max_hp']:<4} MP {p['mp']:>3}/{p['max_mp']:<3}{tag}{statuses}")
        print(" Enemies:")
        for e in state["enemies"]:
            tag = "" if e["alive"] else " [defeated]"
            statuses = f" ({', '.join(e['statuses'])})" if e["statuses"] else ""
            print(f"   {e['name']:<14} HP {e['hp']:>4}/{e['max_hp']:<4}{tag}{statuses}")
        print("=" * 50)

    def get_party_action(self, combatant, state: dict) -> Action:
        self.render_battlefield(state)
        print(f"\n{combatant.name}'s turn! (HP {combatant.hp}/{combatant.max_hp}, MP {combatant.mp}/{combatant.max_mp})")

        options = ["Attack", "Skill", "Item", "Defend", "Flee"]
        choice = self._menu("Choose an action:", options)

        if choice == "Attack":
            target = self._pick_target(state["enemies"], "Attack which enemy?")
            return Action.attack(combatant.id, target["id"])

        if choice == "Skill":
            skills = state.get("available_skills", [])
            if not skills:
                print("No skills known! Attacking instead.")
                target = self._pick_target(state["enemies"], "Attack which enemy?")
                return Action.attack(combatant.id, target["id"])
            labels = [f"{s['name']} (MP {s['mp_cost']}) - {s['description']}" for s in skills]
            idx = self._menu("Choose a skill:", labels, return_index=True)
            skill = skills[idx]
            if combatant.mp < skill["mp_cost"]:
                print("Not enough MP! Choose something else.")
                return self.get_party_action(combatant, state)
            target_type = skill["target"]
            if target_type == "self":
                return Action.use_skill(combatant.id, skill["id"], [combatant.id])
            if target_type == "all_enemies":
                return Action.use_skill(combatant.id, skill["id"], [e["id"] for e in state["enemies"] if e["alive"]])
            if target_type == "all_allies":
                return Action.use_skill(combatant.id, skill["id"], [p["id"] for p in state["party"] if p["alive"]])
            if target_type == "single_ally":
                target = self._pick_target(state["party"], "Target which ally?")
                return Action.use_skill(combatant.id, skill["id"], [target["id"]])
            target = self._pick_target(state["enemies"], "Target which enemy?")
            return Action.use_skill(combatant.id, skill["id"], [target["id"]])

        if choice == "Item":
            items = state.get("available_items", [])
            if not items:
                print("No usable items! Choose something else.")
                return self.get_party_action(combatant, state)
            labels = [f"{i['name']} x{i['count']} - {self.items_db[i['id']].description}" for i in items]
            idx = self._menu("Choose an item:", labels, return_index=True)
            item_info = items[idx]
            item = self.items_db[item_info["id"]]
            pool = [p for p in state["party"] if (not p["alive"])] if item.revive else [p for p in state["party"] if p["alive"]]
            target = self._pick_target(pool, "Use on whom?")
            return Action.use_item(combatant.id, item_info["id"], [target["id"]])

        if choice == "Defend":
            return Action.defend(combatant.id)

        return Action.flee(combatant.id)

    # --- small input helpers -----------------------------------------
    def _menu(self, prompt: str, options, return_index: bool = False):
        print(prompt)
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
        while True:
            raw = input("> ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                i = int(raw) - 1
                return i if return_index else options[i]
            print("Invalid choice, try again.")

    def _pick_target(self, candidates, prompt: str):
        alive_candidates = [c for c in candidates if c.get("alive", True)]
        pool = alive_candidates or candidates
        if len(pool) == 1:
            return pool[0]
        labels = [f"{c['name']} (HP {c['hp']}/{c['max_hp']})" for c in pool]
        idx = self._menu(prompt, labels, return_index=True)
        return pool[idx]

    def announce_result(self, result: str, money: int = None, gems: int = None,
                         xp: int = None, level_ups: dict = None) -> None:
        """level_ups, when given, is {character_name: levels_gained} for
        anyone who leveled up from this battle's XP (see
        PlayerCharacter.grant_xp) -- only characters with a nonzero value
        are expected, but zero/missing entries are tolerated."""
        banner = {
            "victory": "*** VICTORY! ***",
            "defeat": "*** DEFEAT... ***",
            "fled": "*** You fled the battle. ***",
        }.get(result, result)
        print("\n" + banner)
        if money is not None:
            reward = f"You earned {money} money"
            if gems:
                reward += f", {gems} gems"
            if xp:
                reward += f", and {xp} XP per character"
            print(reward + ".")
        for name, levels in (level_ups or {}).items():
            if levels:
                print(f"{name} leveled up! (+{levels})")
        print()

    # ------------------------------------------------------------------
    # Meta-game screens: title, character creation, Colosseum hub. Mirrors
    # ui/pygame_ui.py's screens of the same name so both UI modes support the
    # full new-game -> create character -> Colosseum -> battle loop (see
    # main.py) -- not just the battle itself.
    # ------------------------------------------------------------------
    def show_title_screen(self, has_save: bool) -> str:
        print("\n" + "=" * 40)
        print("        BATTLE COLOSSEUM")
        print("=" * 40)
        options = ["New Game"]
        if has_save:
            options.append("Continue")
        options.append("Quit")
        choice = self._menu("", options)
        return {"New Game": "new_game", "Continue": "continue", "Quit": "quit"}[choice]

    def show_character_creation(self, class_archetypes: dict, class_ids) -> tuple:
        print("\n-- Create Your Character --")
        while True:
            name = input("Name your character: ").strip()
            if name:
                break
            print("A name is required.")

        labels = []
        for cid in class_ids:
            a = class_archetypes[cid]
            skill_names = ", ".join(self.skills_db[sid].name for sid in a.skill_ids if sid in self.skills_db)
            labels.append(f"{a.name} -- {a.description} [{skill_names}]")
        idx = self._menu("Choose a class:", labels, return_index=True)
        class_id = class_ids[idx]
        print(f"\n{name} the {class_archetypes[class_id].name} steps into the Colosseum!")
        return name, class_id

    def show_colosseum_hub(self, player_state, equipment_db: dict) -> str:
        """Returns "battle"/"shop"/"summon"/"heroes"/"quit_to_title", or, in
        debug mode only, "debug_add_gems" -- a cheat button that grants
        config.DEBUG_GEM_GRANT gems on the spot, purely so Summon's gacha
        pulls can be tested/spammed without grinding out real battles for
        gems first. main.py only ever offers it when self.debug is True."""
        from data.hero_rarity import HERO_RARITY_LABEL, star_display
        from game import party as party_logic
        print("\n" + "-" * 40)
        print("THE COLOSSEUM")
        print(f"Money: {player_state.money}    Gems: {player_state.gems}")
        # Shows the current battle party, not the whole owned roster -- see
        # ui/pygame_ui.py's show_colosseum_hub for why. The full collection
        # is still browsable via the Heroes option below.
        party_chars = party_logic.active_party_characters(player_state)
        print("Your party:")
        if not party_chars:
            print("  (no one selected yet -- Enter Battle to pick a party)")
        for c in party_chars:
            archetype = c.archetype
            equipped_bits = [equipment_db[i].name for i in c.equipped.values() if i and i in equipment_db]
            gear_txt = f" -- {', '.join(equipped_bits)}" if equipped_bits else " -- no gear equipped"
            print(f"  [{HERO_RARITY_LABEL[c.rarity]}] {c.name} ({archetype.name}) Lvl {c.level} "
                  f"{star_display(c.stars)}{gear_txt}")
        bench_count = len(player_state.characters) - len(party_chars)
        if bench_count > 0:
            print(f"  + {bench_count} more in reserve -- see Heroes")
        print("-" * 40)
        options = ["Enter Battle", "Shop", "Summon", "Heroes", "Save & Quit to Title"]
        mapping = {
            "Enter Battle": "battle", "Shop": "shop", "Summon": "summon", "Heroes": "heroes",
            "Save & Quit to Title": "quit_to_title",
        }
        if self.debug:
            import config
            debug_label = f"[DEBUG] Add {config.DEBUG_GEM_GRANT} Gems"
            options.append(debug_label)
            mapping[debug_label] = "debug_add_gems"
        choice = self._menu("What now?", options)
        return mapping[choice]

    def show_party_select(self, player_state, equipment_db: dict):
        """Toggle-select up to game/party.py's MAX_PARTY_SIZE heroes to
        actually fight the next battle (see main.py's run_game_loop, which
        calls this before show_battle_setup). Returns the confirmed list of
        PlayerCharacter (in roster order), or None if the player backs out
        without confirming -- mirrors show_battle_setup's own back-to-hub
        convention rather than introducing a new one."""
        from data.hero_rarity import HERO_RARITY_LABEL, star_display
        from game import party as party_logic

        selected = party_logic.default_party_ids(player_state)
        while True:
            print("\n" + "-" * 40)
            print(f"CHOOSE YOUR PARTY (up to {party_logic.MAX_PARTY_SIZE})")
            print("-" * 40)
            if not player_state.characters:
                print("You have no heroes to field -- recruit one via Summon first.")
                return None
            labels = []
            for c in player_state.characters:
                mark = "[x]" if c.id in selected else "[ ]"
                labels.append(f"{mark} {c.name} -- [{HERO_RARITY_LABEL[c.rarity]}] {c.archetype.name}, "
                              f"Lvl {c.level} {star_display(c.stars)}")
            options = list(labels)
            options.append(f"Confirm Party ({len(selected)}/{party_logic.MAX_PARTY_SIZE})")
            options.append("Back to Colosseum")
            idx = self._menu("Toggle heroes (pick a number again to deselect), then confirm:",
                              options, return_index=True)
            if idx == len(options) - 1:
                return None
            if idx == len(options) - 2:
                ok, msg, resolved = party_logic.confirm_party(player_state, selected)
                if ok:
                    return resolved
                print(msg)
                continue
            character = player_state.characters[idx]
            selected, changed = party_logic.toggle_member(selected, character.id)
            if not changed:
                print(f"Party is already full ({party_logic.MAX_PARTY_SIZE} max) -- deselect someone first.")

    def show_battle_setup(self, player_state, party):
        """Difficulty + opponent-count picker shown before entering a battle
        (see game/battle_setup.py). `party` is the list of PlayerCharacter
        chosen on show_party_select (up to game/party.py's MAX_PARTY_SIZE) --
        battle level/rewards scale off *this* group's average level, not the
        whole roster. Returns (difficulty, num_enemies), or None if the
        player backs all the way out to the hub."""
        from game.battle_setup import (
            DIFFICULTY_IDS, DIFFICULTY_REWARD_MODIFIER, MAX_OPPONENTS, MIN_OPPONENTS, party_average_level,
        )

        avg_level = party_average_level(party)
        while True:
            print("\n" + "-" * 40)
            print("BATTLE SETUP")
            print(f"Fielding: {', '.join(c.name for c in party)}")
            print(f"Party average level: {avg_level:.1f}")
            print("-" * 40)
            diff_labels = [
                f"{d.capitalize()} (rewards x{DIFFICULTY_REWARD_MODIFIER[d]:g})" for d in DIFFICULTY_IDS
            ]
            diff_labels.append("Back to Colosseum")
            idx = self._menu("Choose difficulty:", diff_labels, return_index=True)
            if idx == len(DIFFICULTY_IDS):
                return None
            difficulty = DIFFICULTY_IDS[idx]

            count_labels = [str(n) for n in range(MIN_OPPONENTS, MAX_OPPONENTS + 1)]
            count_labels.append("Back")
            idx2 = self._menu("How many opponents?", count_labels, return_index=True)
            if idx2 == len(count_labels) - 1:
                continue  # back to difficulty choice
            return difficulty, MIN_OPPONENTS + idx2

    def show_shop(self, player_state, items_db: dict, equipment_db: dict) -> None:
        """Text-mode Shop: buy consumables/equipment with money. Mirrors
        ui/pygame_ui.py's show_shop, driving the same game/shop.py functions
        so both UIs behave identically -- only the presentation differs.
        Gear management (equip/unequip) moved to show_heroes as of the
        hero-rarity pass -- see that method's docstring for why."""
        from game import shop as shop_logic

        while True:
            print("\n" + "-" * 40)
            print("SHOP")
            print(f"Money: {player_state.money}")
            print("-" * 40)
            options = ["Buy Items", "Buy Equipment", "Back to Colosseum"]
            choice = self._menu("What would you like to do?", options)

            if choice == "Back to Colosseum":
                return

            if choice == "Buy Items":
                for_sale = sorted((i for i in items_db.values() if i.cost > 0), key=lambda i: i.cost)
                if not for_sale:
                    print("Nothing for sale.")
                    continue
                owned = lambda item_id: player_state.inventory.get(item_id, 0)
                labels = [f"{i.name} (x{owned(i.id)} owned) -- {i.description} [{i.cost}g]" for i in for_sale]
                labels.append("Cancel")
                idx = self._menu("Buy which item?", labels, return_index=True)
                if idx == len(for_sale):
                    continue
                ok, msg = shop_logic.buy_item(player_state, for_sale[idx].id, items_db)
                print(msg if ok else f"Can't do that: {msg}")

            elif choice == "Buy Equipment":
                slot = self._menu("Which slot?", ["Weapon", "Armor", "Accessory", "Cancel"])
                if slot == "Cancel":
                    continue
                slot_id = slot.lower()
                for_sale = sorted(
                    (e for e in equipment_db.values() if e.slot == slot_id and e.cost > 0),
                    key=lambda e: e.cost,
                )
                if not for_sale:
                    print("Nothing for sale in that slot.")
                    continue
                labels = [f"{e.name} -- {e.bonus_text()} [{e.cost}g]" for e in for_sale]
                labels.append("Cancel")
                idx = self._menu("Buy which equipment?", labels, return_index=True)
                if idx == len(for_sale):
                    continue
                ok, msg = shop_logic.buy_equipment(player_state, for_sale[idx].id, equipment_db)
                print(msg)

    def show_summon(self, player_state, equipment_db: dict) -> None:
        """Text-mode Summon: spend gems on either a new roster character or
        a random piece of premium equipment, one at a time or ten at once.
        Mirrors ui/pygame_ui.py's show_summon's options, driving the same
        game/summon.py batch functions (both x1 and x10 go through
        summon_character_batch/summon_equipment_batch, so a single pull and
        a 10-pull can never quietly behave differently between the two UI
        modes). Character summons can land on a hero already owned as of
        the hero-rarity pass -- that's not a failure, it's a duplicate
        (hero shards instead of a new roster slot), so the "ok" branch
        covers both. No card-flip animation here (there's nothing to
        animate in a terminal) -- a x10 pull just prints all ten result
        lines at once."""
        from data.summon_pool import (
            CHARACTER_SUMMON_COST, CHARACTER_SUMMON_COST_X10, EQUIPMENT_SUMMON_COST,
            EQUIPMENT_SUMMON_COST_X10, SUMMON_X10_COUNT,
        )
        from game import summon as summon_logic

        while True:
            print("\n" + "-" * 40)
            print("SUMMON")
            print(f"Gems: {player_state.gems}")
            print("-" * 40)
            options = [
                f"Summon Character x1 -- recruit a random teammate ({CHARACTER_SUMMON_COST}g)",
                f"Summon Character x{SUMMON_X10_COUNT} -- {SUMMON_X10_COUNT} pulls at once ({CHARACTER_SUMMON_COST_X10}g)",
                f"Summon Equipment x1 -- a random epic/legendary piece ({EQUIPMENT_SUMMON_COST}g)",
                f"Summon Equipment x{SUMMON_X10_COUNT} -- {SUMMON_X10_COUNT} pulls at once ({EQUIPMENT_SUMMON_COST_X10}g)",
                "Back to Colosseum",
            ]
            choice = self._menu("What would you like to do?", options, return_index=True)

            if choice == 4:
                return
            if choice == 0:
                ok, msg, results = summon_logic.summon_character_batch(player_state, 1)
            elif choice == 1:
                ok, msg, results = summon_logic.summon_character_batch(player_state, SUMMON_X10_COUNT)
            elif choice == 2:
                ok, msg, results = summon_logic.summon_equipment_batch(player_state, equipment_db, 1)
            else:
                ok, msg, results = summon_logic.summon_equipment_batch(player_state, equipment_db, SUMMON_X10_COUNT)

            if not ok:
                print(f"Can't do that: {msg}")
            elif len(results) == 1:
                print(results[0].message)
            else:
                for result in results:
                    print(result.message)

    def show_heroes(self, player_state, equipment_db: dict) -> None:
        """Text-mode Heroes page: view each hero's rarity/level/stars, spend
        banked hero shards on a star upgrade (game/heroes.py), and
        equip/unequip gear -- this is the new home for gear management as
        of the hero-rarity pass (Andrew's AskUserQuestion answer had it
        replace Shop's old "Manage Gear" option rather than duplicate it)."""
        from data.hero_rarity import HERO_RARITY_LABEL, star_display

        while True:
            print("\n" + "-" * 40)
            print("HEROES")
            print("-" * 40)
            if not player_state.characters:
                print("You have no heroes yet.")
                return
            labels = []
            for c in player_state.characters:
                labels.append(f"{c.name} -- [{HERO_RARITY_LABEL[c.rarity]}] {c.archetype.name}, "
                              f"Lvl {c.level} {star_display(c.stars)} (shards: {c.shards})")
            labels.append("Back to Colosseum")
            idx = self._menu("View which hero?", labels, return_index=True)
            if idx == len(player_state.characters):
                return
            self._show_hero_detail(player_state, player_state.characters[idx], equipment_db)

    def _show_hero_detail(self, player_state, character, equipment_db: dict) -> None:
        from data.hero_rarity import HERO_RARITY_LABEL, shard_cost_for_next_star, star_display
        from game import heroes as heroes_logic
        from game import shop as shop_logic

        while True:
            stats = character.effective_stats(equipment_db)
            print("\n" + "-" * 40)
            print(f"{character.name} -- [{HERO_RARITY_LABEL[character.rarity]}] {character.archetype.name}")
            cost = shard_cost_for_next_star(character.rarity, character.stars)
            stars_line = f"Level {character.level}  {star_display(character.stars)}  Shards: {character.shards}"
            stars_line += "  (MAX)" if cost is None else f"  (next star: {cost} shards)"
            print(stars_line)
            print(f"HP {stats.max_hp}  MP {stats.max_mp}  ATK {stats.atk}  DEF {stats.def_}  "
                  f"MAG {stats.mag}  RES {stats.res}  SPD {stats.spd}  LUK {stats.luk}")
            equipped_bits = [equipment_db[i].name for i in character.equipped.values() if i and i in equipment_db]
            print(f"Equipped: {', '.join(equipped_bits) if equipped_bits else '(nothing)'}")
            print("-" * 40)

            options = []
            if cost is not None:
                options.append(f"Upgrade Star ({character.shards}/{cost} shards)")
            stashed = sorted(player_state.owned_equipment.keys())
            for eq_id in stashed:
                eq = equipment_db.get(eq_id)
                name = eq.name if eq else eq_id
                count = player_state.owned_equipment[eq_id]
                options.append(f"Equip {name} (x{count})")
            equipped_slots = [s for s in ("weapon", "armor", "accessory") if character.equipped.get(s)]
            for s in equipped_slots:
                eq = equipment_db.get(character.equipped[s])
                name = eq.name if eq else character.equipped[s]
                options.append(f"Unequip {s}: {name}")
            options.append("Back")

            idx = self._menu("What now?", options, return_index=True)
            if idx == len(options) - 1:
                return

            offset = 0
            if cost is not None:
                if idx == 0:
                    ok, msg = heroes_logic.upgrade_star(player_state, character.id)
                    print(msg)
                    continue
                offset = 1
            stash_end = offset + len(stashed)
            if offset <= idx < stash_end:
                eq_id = stashed[idx - offset]
                ok, msg = shop_logic.equip_from_stash(player_state, character.id, eq_id, equipment_db)
            else:
                slot = equipped_slots[idx - stash_end]
                ok, msg = shop_logic.unequip(player_state, character.id, slot, equipment_db)
            print(msg)

    def show_not_implemented(self, title: str, message: str) -> None:
        """A generic 'coming soon' screen -- used by Shop and Summon while
        those stages were still stubs; both are built now (see show_shop,
        show_summon), but this stays around as reusable scaffolding for
        whatever hub feature is next."""
        print(f"\n[{title}] {message}")

    # No-ops so main.py's game loop can treat TextUI and PygameUI identically
    # (PygameUI actually uses these to track the battle window's state).
    def attach_engine(self, battle_engine) -> None:
        pass

    def reset_battle_view(self) -> None:
        pass

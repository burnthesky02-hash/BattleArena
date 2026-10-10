"""Exercises ui/pygame_ui.py's control flow (menus, target selection, event
handling, drawing calls) against a fake pygame module (tests/pygame_stub.py),
since this sandbox can't install real pygame/SDL (no network access to
pypi/apt here). This catches wrong-API-usage and logic bugs; it does NOT
verify the window actually looks right -- that needs a human running it for
real (see README "Known limitations").
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.pygame_stub import make_pygame_stub, Event

# Inject the stub BEFORE ui.pygame_ui does `import pygame` inside PygameUI.__init__
event_queue = []
sys.modules["pygame"] = make_pygame_stub(event_queue)

from engine.battle import BattleEngine  # noqa: E402
from engine.actions import Action  # noqa: E402
from engine.types import ActionType  # noqa: E402
from data.skills_db import SKILLS  # noqa: E402
from data.items_db import ITEMS, STARTING_INVENTORY  # noqa: E402
from data.characters import make_party  # noqa: E402
from data.enemies import make_enemy_group  # noqa: E402
from ui import pygame_ui  # noqa: E402
from ui.pygame_ui import (  # noqa: E402
    HEIGHT, BATTLE_BOTTOM_MARGIN, BATTLE_CMD_PANEL_X, BATTLE_CMD_BTN_W, BATTLE_CMD_BTN_H, BATTLE_CMD_BTN_GAP,
    BATTLE_CMD_PANEL_PAD, PygameUI,
)

# As of fix #18, the battle menu (main actions and every submenu -- they all
# top out at 5 entries) is a single-column list inside a bottom-left command
# panel, sized to however many buttons are showing right now and
# bottom-anchored off self.height -- so a click position depends on how many
# buttons this particular menu has, not a fixed row/col grid. Mirrors the
# exact math _draw_frame itself uses (imported constants, not re-typed magic
# numbers) so a future layout tweak can't silently desync this file.


def click_at(index: int, num_buttons: int) -> Event:
    cmd_h = num_buttons * BATTLE_CMD_BTN_H + max(0, num_buttons - 1) * BATTLE_CMD_BTN_GAP + 2 * BATTLE_CMD_PANEL_PAD
    cmd_y = HEIGHT - BATTLE_BOTTOM_MARGIN - cmd_h
    bx = BATTLE_CMD_PANEL_X + BATTLE_CMD_PANEL_PAD
    by0 = cmd_y + BATTLE_CMD_PANEL_PAD
    x = bx + BATTLE_CMD_BTN_W // 2
    y = by0 + index * (BATTLE_CMD_BTN_H + BATTLE_CMD_BTN_GAP) + BATTLE_CMD_BTN_H // 2
    return Event(3, type=3, button=1, pos=(x, y))  # pygame.MOUSEBUTTONDOWN == 3 in the stub


def make_engine_and_ui(debug=False):
    party = make_party()
    enemies = make_enemy_group()
    ui = PygameUI(SKILLS, ITEMS, debug=debug)
    engine = BattleEngine(
        party=party, enemies=enemies, skills_db=SKILLS, items_db=ITEMS,
        inventory=dict(STARTING_INVENTORY),
        get_party_action=ui.get_party_action,
        get_enemy_action=lambda c, s: Action.defend(c.id),
        on_event=ui.print_line,
    )
    ui.attach_engine(engine)
    return engine, ui, party, enemies


def test_print_line_draws_without_crashing():
    engine, ui, party, enemies = make_engine_and_ui()
    ui.print_line("A test log line appears.")
    assert ui.log_lines[-1] == "A test log line appears."
    print("print_line draw: OK")


MAIN_MENU_COUNT = 5  # Attack/Skill/Item/Defend/Flee -- the main action menu's button count, every test below clicks
                      # into this menu first, so its own click_at() calls always pass this as num_buttons


def test_attack_flow():
    engine, ui, party, enemies = make_engine_and_ui()
    kael = party[0]
    state = engine.build_state(for_actor=kael)
    alive_enemies = [e for e in enemies if e.hp > 0]
    event_queue.clear()
    event_queue.append(click_at(0, MAIN_MENU_COUNT))  # main menu: "Attack" (index 0)
    event_queue.append(click_at(0, len(alive_enemies)))  # target menu: first alive enemy (index 0)
    action = ui.get_party_action(kael, state)
    assert action.type == ActionType.ATTACK
    assert action.target_ids == [enemies[0].id]
    print("attack flow: OK")


def test_self_target_skill_flow():
    engine, ui, party, enemies = make_engine_and_ui()
    kael = party[0]  # skill_ids include "warcry" (target=SELF) as skill index 2
    state = engine.build_state(for_actor=kael)
    skills = state["available_skills"]
    skill_index = next(i for i, s in enumerate(skills) if s["id"] == "warcry")
    event_queue.clear()
    event_queue.append(click_at(1, MAIN_MENU_COUNT))  # main menu: "Skill" (index 1)
    event_queue.append(click_at(skill_index, len(skills)))  # skill menu: warcry
    action = ui.get_party_action(kael, state)
    assert action.type == ActionType.SKILL and action.skill_id == "warcry"
    assert action.target_ids == [kael.id]  # self-targeted, no extra click needed
    print("self-target skill flow: OK")


def test_all_enemies_skill_flow():
    engine, ui, party, enemies = make_engine_and_ui()
    kael = party[0]  # "cleave" targets all_enemies
    state = engine.build_state(for_actor=kael)
    skills = state["available_skills"]
    skill_index = next(i for i, s in enumerate(skills) if s["id"] == "cleave")
    event_queue.clear()
    event_queue.append(click_at(1, MAIN_MENU_COUNT))  # Skill
    event_queue.append(click_at(skill_index, len(skills)))  # cleave
    action = ui.get_party_action(kael, state)
    assert action.type == ActionType.SKILL and action.skill_id == "cleave"
    assert set(action.target_ids) == {e.id for e in enemies}
    print("all-enemies skill flow: OK")


def test_item_flow():
    engine, ui, party, enemies = make_engine_and_ui()
    kael = party[0]
    party[1].hp = 1  # make Lyra an obvious low-HP target (still alive, so still counted below)
    state = engine.build_state(for_actor=kael)
    items = state["available_items"]
    item_index = next(i for i, it in enumerate(items) if it["id"] == "potion")
    alive_party = [p for p in party if p.hp > 0]
    event_queue.clear()
    event_queue.append(click_at(2, MAIN_MENU_COUNT))  # main menu: "Item"
    event_queue.append(click_at(item_index, len(items)))  # potion
    event_queue.append(click_at(1, len(alive_party)))  # target menu: second alive party member (Lyra, index 1)
    action = ui.get_party_action(kael, state)
    assert action.type == ActionType.ITEM and action.item_id == "potion"
    print("item flow: OK")


def test_defend_and_flee_single_click():
    engine, ui, party, enemies = make_engine_and_ui()
    kael = party[0]
    state = engine.build_state(for_actor=kael)
    event_queue.clear()
    event_queue.append(click_at(3, MAIN_MENU_COUNT))  # Defend
    action = ui.get_party_action(kael, state)
    assert action.type == ActionType.DEFEND
    print("defend flow: OK")

    event_queue.clear()
    event_queue.append(click_at(4, MAIN_MENU_COUNT))  # Flee
    action = ui.get_party_action(kael, state)
    assert action.type == ActionType.FLEE
    print("flee flow: OK")


def test_end_screen_closes_on_click():
    engine, ui, party, enemies = make_engine_and_ui()
    event_queue.clear()
    event_queue.append(Event(3, type=3, button=1, pos=(0, 0)))
    ui.show_end_screen("victory")
    assert sys.modules["pygame"]._quit_called
    print("end screen: OK")


def test_end_screen_with_xp_and_level_ups_does_not_crash():
    """As of the level-curve pass, show_end_screen also renders an XP line
    and a "leveled up" line per character -- just needs to not blow up and
    to still respond to a click (quit_on_close=False, the Colosseum-hub path)."""
    engine, ui, party, enemies = make_engine_and_ui()
    event_queue.clear()
    event_queue.append(Event(3, type=3, button=1, pos=(0, 0)))
    ui.show_end_screen("victory", money=42, gems=5, xp=25, level_ups={"Kenji": 1, "Lyra": 0},
                        quit_on_close=False)
    print("end screen with xp/level-ups: OK")


def test_hit_and_heal_flash_feedback():
    """Actions resolve instantly with only bars/log updating otherwise, so
    print_line diffs HP between frames and starts a brief flash + floating
    +/-N number on whoever changed (see PygameUI._update_hit_flashes). No
    engine involvement -- purely derived from build_state() snapshots -- so
    this only needs a plain HP mutation + print_line call to verify."""
    engine, ui, party, enemies = make_engine_and_ui()
    target = party[0]

    # The very first frame just seeds _prev_hp; nothing has "changed" yet.
    ui._update_hit_flashes(engine.build_state())
    assert ui._flashes == {}, "no flash should fire before any HP is known"

    target.hp -= 23
    ui.print_line(f"{target.name} takes 23 damage.")
    delta, t = ui._active_flash(target.id)
    assert delta == -23, delta
    assert 0.0 <= t <= 1.0, t

    target.hp += 40
    ui.print_line(f"{target.name} recovers 40 HP.")
    delta, _ = ui._active_flash(target.id)
    assert delta == 40, delta

    time.sleep(0.6)  # longer than HIT_FLASH_DURATION (0.5s)
    assert ui._active_flash(target.id) is None, "flash should expire and clean itself up"
    print("hit/heal flash feedback: OK")


def test_is_melee_action_classifies_attack_physical_skill_vs_others():
    """Fix #19: the basic Attack and any physical-kind skill (e.g. Kenji's
    "cleave") get the run-in/swing/run-back treatment; a magical skill (e.g.
    "fireball") and a status skill (e.g. "warcry") do not -- see
    _is_melee_action's docstring."""
    engine, ui, party, enemies = make_engine_and_ui()
    kael = party[0]
    assert ui._is_melee_action(engine, Action.attack(kael.id, enemies[0].id)) is True
    assert ui._is_melee_action(engine, Action.use_skill(kael.id, "cleave", [e.id for e in enemies])) is True
    assert ui._is_melee_action(engine, Action.use_skill(kael.id, "fireball", [enemies[0].id])) is False
    assert ui._is_melee_action(engine, Action.use_skill(kael.id, "warcry", [kael.id])) is False
    assert ui._is_melee_action(engine, Action.defend(kael.id)) is False
    assert ui._is_melee_action(engine, Action.flee(kael.id)) is False
    print("is_melee_action classification (attack/physical-skill vs magical/status/other): OK")


def test_melee_target_for_picks_requested_target_or_first_alive_opponent():
    """_melee_target_for is just a best-effort guess for where to run the
    attacker to -- it should honor the action's own requested target_ids
    when one matches a living opponent, and otherwise fall back to any
    living opponent rather than returning None (which would skip the
    animation entirely)."""
    engine, ui, party, enemies = make_engine_and_ui()
    kael = party[0]
    requested = enemies[1]
    action = Action.attack(kael.id, requested.id)
    assert ui._melee_target_for(engine, kael, action) is requested

    # target_ids pointing at nobody real -- must still fall back to *some*
    # living opponent instead of returning None.
    bogus_action = Action.attack(kael.id, "no-such-id")
    fallback = ui._melee_target_for(engine, kael, bogus_action)
    assert fallback is not None and fallback in enemies and fallback.alive

    # No living opponents at all -- must return None so the caller resolves
    # in place instead of animating toward nothing.
    for e in enemies:
        e.hp = 0
    assert ui._melee_target_for(engine, kael, action) is None
    print("melee_target_for (requested/fallback/none-alive): OK")


def test_resolve_action_with_movement_attack_resolves_exactly_once_and_deals_damage():
    """attach_engine wraps BattleEngine.resolve_action so a melee action
    plays run-in/swing/run-back around the engine's real, unwrapped
    resolution (see _resolve_action_with_movement) -- this pins down that
    the real resolution still fires EXACTLY once (never skipped, never
    duplicated) and that self._mover is cleared again once the whole
    sequence finishes, by wrapping BattleEngine.resolve_action itself with a
    counting spy *before* attach_engine captures it, so the spy becomes the
    "original_resolve" the animation calls into.

    BATTLE_MELEE_ANIM_FPS is bumped way up for the duration of this test so
    the swing's real-wall-clock animation loop finishes near-instantly --
    this sandbox has no actual battler art (see BATTLER_DIR), so the swing
    always falls back to the full 36-frame default duration otherwise."""
    from engine.battle import BattleEngine

    engine, ui, party, enemies = make_engine_and_ui()
    kael = party[0]
    target = enemies[0]
    before_hp = target.hp

    calls = []
    real_resolve = BattleEngine.resolve_action

    def counting_resolve(self, action):
        calls.append(action)
        real_resolve(self, action)

    original_fps = pygame_ui.BATTLE_MELEE_ANIM_FPS
    BattleEngine.resolve_action = counting_resolve
    pygame_ui.BATTLE_MELEE_ANIM_FPS = 5000
    try:
        ui.reset_battle_view()
        ui.attach_engine(engine)  # captures counting_resolve as this battle's "original"
        engine.resolve_action(Action.attack(kael.id, target.id))
    finally:
        BattleEngine.resolve_action = real_resolve
        pygame_ui.BATTLE_MELEE_ANIM_FPS = original_fps

    assert len(calls) == 1, f"engine's real resolve_action must fire exactly once per melee action, got {len(calls)}"
    assert target.hp < before_hp, "the attack should have actually dealt damage"
    assert ui._mover is None, "self._mover must be cleared once the run/swing/run-back sequence finishes"
    print(f"resolve_action_with_movement (attack): resolved exactly once, dealt "
          f"{before_hp - target.hp} damage, _mover cleared: OK")


def test_resolve_action_with_movement_passes_non_melee_actions_straight_through():
    """A magical skill (or item/defend/flee) must resolve exactly like
    before fix #19 -- no animation, no self._mover ever set, resolve_action
    called exactly once."""
    from engine.battle import BattleEngine

    engine, ui, party, enemies = make_engine_and_ui()
    kael = party[1]  # Lyra -- has "fireball" among her skills
    target = enemies[0]
    before_hp = target.hp

    calls = []
    real_resolve = BattleEngine.resolve_action

    def counting_resolve(self, action):
        calls.append(action)
        real_resolve(self, action)

    BattleEngine.resolve_action = counting_resolve
    try:
        ui.reset_battle_view()
        ui.attach_engine(engine)
        engine.resolve_action(Action.use_skill(kael.id, "fireball", [target.id]))
    finally:
        BattleEngine.resolve_action = real_resolve

    assert len(calls) == 1
    assert target.hp < before_hp
    assert ui._mover is None
    print("resolve_action_with_movement (magical skill): passes straight through, no animation: OK")


def test_sprite_click_selects_target_same_as_text_button():
    """Fix #19: a combatant's own on-screen sprite is clickable as a target
    wherever the text button menu already offers it as one -- clicking the
    sprite must resolve to exactly the same Action a text-row click would.
    Uses ui._sprite_click_targets to find where the target's sprite would
    actually be drawn (same helper _draw_frame itself uses), then scripts a
    click at its center instead of at the text button's position."""
    engine, ui, party, enemies = make_engine_and_ui()
    kael = party[0]
    state = engine.build_state(for_actor=kael)
    target = enemies[0]

    rects = ui._sprite_click_targets(state)
    target_rect = rects[target.id]
    click_pos = (target_rect.x + target_rect.w // 2, target_rect.y + target_rect.h // 2)

    event_queue.clear()
    event_queue.append(click_at(0, MAIN_MENU_COUNT))  # main menu: "Attack"
    event_queue.append(Event(3, type=3, button=1, pos=click_pos))  # click the sprite, not its menu row
    action = ui.get_party_action(kael, state)
    assert action.type == ActionType.ATTACK
    assert action.target_ids == [target.id]
    print("sprite-click targeting (equivalent to clicking the text menu row): OK")


def main():
    test_print_line_draws_without_crashing()
    test_attack_flow()
    test_self_target_skill_flow()
    test_all_enemies_skill_flow()
    test_item_flow()
    test_defend_and_flee_single_click()
    test_end_screen_closes_on_click()
    test_end_screen_with_xp_and_level_ups_does_not_crash()
    test_hit_and_heal_flash_feedback()
    test_is_melee_action_classifies_attack_physical_skill_vs_others()
    test_melee_target_for_picks_requested_target_or_first_alive_opponent()
    test_resolve_action_with_movement_attack_resolves_exactly_once_and_deals_damage()
    test_resolve_action_with_movement_passes_non_melee_actions_straight_through()
    test_sprite_click_selects_target_same_as_text_button()
    print("\nALL PYGAME UI SMOKE TESTS PASSED (against a fake pygame -- run the real game to verify the window visually)")


if __name__ == "__main__":
    main()

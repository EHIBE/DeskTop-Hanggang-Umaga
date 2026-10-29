from typing import Any

import pytest

from rules.enemies import at_edge, flee_point, move_toward, pick_target
from rules.geometry import Point
from rules.resolve import (
    PUSH_CM,
    BoardState,
    EnemyType,
    Event,
    EventType,
    Outcome,
    apply_enemy_tags,
    apply_unit_tags,
    begin_turn,
    check_outcome,
    enemy_status_tags,
    illegal_moves,
    intent_error,
    resolve_turn,
    score,
    unit_status_tags,
    with_positions,
)
from rules.units import Difficulty, PowerId, UnitClass
from tests.test_resolve import (
    KUBO_ID,
    H,
    W,
    atk,
    board,
    enemy,
    find_enemy,
    find_unit,
    heal,
    kubo,
    of_type,
    power,
    run,
    types,
    unit,
)


def tik_board(target_pos: Point, tik_pos: Point, **over: Any) -> tuple[BoardState, str]:
    state = board(
        [kubo((55.0, 35.0)), unit("a", pos=target_pos, **over)],
        [enemy("t", EnemyType.TIKBALANG, pos=tik_pos, target="a")],
    )
    return state, "a"


def test_push_constant_matches_docs() -> None:
    assert PUSH_CM == 8.0


def test_tikbalang_pushes_eight_cm_straight_away() -> None:
    state, uid = tik_board((10.0, 10.0), (14.0, 10.0))
    new, events = run(state)
    assert find_unit(new, uid).position == pytest.approx((2.0, 10.0))
    assert types(events) == [EventType.ATTACK, EventType.PUSH]
    push = events[1]
    assert push.src == "t" and push.dst == uid
    assert push.pos == pytest.approx((2.0, 10.0))


def test_push_diagonal_keeps_distance() -> None:
    state, uid = tik_board((20.0, 20.0), (23.0, 24.0))
    new, _ = run(state)
    assert find_unit(new, uid).position == pytest.approx((15.2, 13.6))


def test_push_moves_hull_with_the_unit() -> None:
    state, uid = tik_board((10.0, 10.0), (14.0, 10.0))
    new, _ = run(state)
    moved = find_unit(new, uid)
    assert min(x for x, _ in moved.hull) == pytest.approx(0.5)


def test_push_when_tikbalang_sits_on_centroid_goes_north() -> None:
    state, uid = tik_board((10.0, 20.0), (10.0, 20.0))
    new, _ = run(state)
    assert find_unit(new, uid).position == pytest.approx((10.0, 12.0))


def test_push_happens_even_when_shield_absorbs_everything() -> None:
    state, uid = tik_board((10.0, 10.0), (14.0, 10.0), shield=5)
    new, events = run(state)
    assert events[0].dmg == 0
    assert find_unit(new, uid).hp == find_unit(state, uid).hp
    assert EventType.PUSH in types(events)
    assert find_unit(new, uid).position == pytest.approx((2.0, 10.0))


def test_push_to_exact_boundary_is_not_a_throw() -> None:
    state, uid = tik_board((8.0, 10.0), (12.0, 10.0))
    new, events = run(state)
    assert find_unit(new, uid).position == pytest.approx((0.0, 10.0))
    assert EventType.THROWN not in types(events)


def test_kubo_is_never_pushed() -> None:
    state = board(
        [kubo((30.0, 20.0))],
        [enemy("t", EnemyType.TIKBALANG, pos=(34.0, 20.0), target=KUBO_ID)],
    )
    new, events = run(state)
    assert find_unit(new, KUBO_ID).position == (30.0, 20.0)
    assert types(events) == [EventType.ATTACK, EventType.KUBO_HIT]


def test_downed_unit_is_not_pushed() -> None:
    state, uid = tik_board((10.0, 10.0), (14.0, 10.0), hp=1)
    state = board([*state.units, unit("b", pos=(40.0, 30.0))], list(state.enemies))
    new, events = run(state)
    assert find_unit(new, uid).position == (10.0, 10.0)
    assert types(events) == [EventType.ATTACK, EventType.DOWN]


def test_missed_tikbalang_does_not_push() -> None:
    state, uid = tik_board((10.0, 10.0), (25.0, 10.0))
    new, events = run(state)
    assert find_unit(new, uid).position == (10.0, 10.0)
    assert types(events) == [EventType.DODGE]


def test_other_enemies_do_not_push() -> None:
    state = board(
        [kubo((55.0, 35.0)), unit("a", pos=(10.0, 10.0))],
        [enemy("s", EnemyType.ASWANG, pos=(14.0, 10.0), target="a")],
    )
    new, events = run(state)
    assert find_unit(new, "a").position == (10.0, 10.0)
    assert EventType.PUSH not in types(events)


def test_push_off_the_desk_throws_the_unit() -> None:
    state, uid = tik_board((4.0, 10.0), (8.0, 10.0))
    new, events = run(state)
    thrown = find_unit(new, uid)
    assert thrown.position == (4.0, 10.0)
    assert thrown.out_turns == 1
    assert types(events) == [EventType.ATTACK, EventType.THROWN]
    assert events[1].src == "t" and events[1].dst == uid and events[1].pos is None


@pytest.mark.parametrize(
    ("target", "tik"),
    [
        ((10.0, 3.0), (10.0, 7.0)),
        ((W - 4.0, 10.0), (W - 8.0, 10.0)),
        ((20.0, H - 4.0), (20.0, H - 8.0)),
    ],
)
def test_throw_on_every_edge(target: Point, tik: Point) -> None:
    state, uid = tik_board(target, tik)
    new, events = run(state)
    assert EventType.THROWN in types(events)
    assert find_unit(new, uid).position == target


def test_thrown_unit_is_out_one_turn_then_back() -> None:
    state, uid = tik_board((4.0, 10.0), (8.0, 10.0))
    after, _ = run(state)
    assert find_unit(after, uid).out_turns == 1
    nxt, _ = begin_turn(after)
    assert find_unit(nxt, uid).out_turns == 1
    assert intent_error(nxt, atk(uid, "t")) == "cmd.unknown"
    done, _ = run(nxt)
    assert find_unit(done, uid).out_turns == 0
    back, _ = begin_turn(done)
    assert intent_error(back, atk(uid, "t")) is None


def test_out_turns_tick_down_for_units_already_out() -> None:
    state = board(
        [kubo((55.0, 35.0)), unit("a", pos=(10.0, 10.0), out_turns=2)],
        [enemy("s", pos=(30.0, 30.0))],
    )
    new, _ = run(state)
    assert find_unit(new, "a").out_turns == 1


def test_out_unit_cannot_act_or_be_targeted() -> None:
    state = board(
        [
            kubo((55.0, 35.0)),
            unit("a", pos=(10.0, 10.0), out_turns=1),
            unit("h", UnitClass.HEALER, (14.0, 10.0)),
        ],
        [
            enemy("s", pos=(10.0, 14.0)),
            enemy("t", EnemyType.TIKBALANG, pos=(30.0, 30.0)),
        ],
    )
    assert intent_error(state, atk("a", "s")) == "cmd.unknown"
    assert intent_error(state, power("a", "s")) == "cmd.unknown"
    assert intent_error(state, heal("h", "a")) == "cmd.unknown"
    assert find_unit(state, "a").can_act is False
    assert find_unit(state, "a").is_targetable is False
    assert pick_target(state.enemies[0], state) == "h"


def test_enemy_skips_out_target_during_resolve() -> None:
    state = board(
        [kubo((55.0, 35.0)), unit("a", pos=(10.0, 10.0), out_turns=1)],
        [enemy("s", pos=(14.0, 10.0), target="a")],
    )
    new, events = run(state)
    assert events == ()
    assert find_unit(new, "a").hp == find_unit(state, "a").hp


def test_out_unit_is_excluded_from_illegal_moves_and_positions() -> None:
    state = board(
        [
            kubo((55.0, 35.0)),
            unit("a", pos=(10.0, 10.0), out_turns=1),
            unit("b", pos=(20.0, 10.0)),
        ],
    )
    moved = with_positions(state, {"a": (50.0, 30.0), "b": (50.0, 30.0)})
    assert find_unit(moved, "a").position == (10.0, 10.0)
    assert find_unit(moved, "b").position == (50.0, 30.0)
    assert illegal_moves(moved) == ("b",)


def test_out_unit_does_not_receive_sigaw_or_shield() -> None:
    state = board(
        [
            kubo((55.0, 35.0)),
            unit("r", UnitClass.RANGED, (10.0, 10.0), power=PowerId.P10),
            unit("a", pos=(14.0, 10.0), out_turns=1),
        ],
        [enemy("s", pos=(40.0, 30.0))],
    )
    new, _ = run(state, power("r"))
    assert find_unit(new, "a").atk_bonus == 0


def test_duwende_target_is_charm_else_lowest_hp_non_kubo() -> None:
    state = board(
        [
            kubo((30.0, 12.0)),
            unit("f1", pos=(30.0, 14.0), hp=4),
            unit("f2", pos=(5.0, 35.0), hp=2),
            unit("c", UnitClass.CHARM, (50.0, 30.0)),
        ],
        [enemy("d", EnemyType.DUWENDE, pos=(30.0, 10.0))],
    )
    assert pick_target(state.enemies[0], state) == "c"
    no_charm = board(list(state.units[:3]), list(state.enemies))
    assert pick_target(no_charm.enemies[0], no_charm) == "f2"


def test_duwende_steal_event_and_state() -> None:
    state = board(
        [kubo((55.0, 35.0)), unit("a", pos=(10.0, 10.0))],
        [enemy("d", EnemyType.DUWENDE, pos=(14.0, 10.0), target="a")],
    )
    new, events = run(state)
    assert types(events) == [EventType.STEAL]
    assert events[0].src == "d" and events[0].dst == "a" and events[0].dmg is None
    stolen = find_unit(new, "a")
    assert stolen.stolen_by == "d" and stolen.hp == find_unit(state, "a").hp
    carrier = find_enemy(new, "d")
    assert carrier.carrying == "a" and carrier.target_id is None
    assert carrier.intent_dmg is None


def test_mahirap_duwende_still_steals_without_damage() -> None:
    state = board(
        [kubo((55.0, 35.0)), unit("a", pos=(10.0, 10.0))],
        [
            enemy(
                "d",
                EnemyType.DUWENDE,
                pos=(14.0, 10.0),
                target="a",
                difficulty=Difficulty.MAHIRAP,
            )
        ],
        difficulty=Difficulty.MAHIRAP,
    )
    new, events = run(state)
    assert types(events) == [EventType.STEAL]
    assert find_unit(new, "a").hp == find_unit(state, "a").hp


def test_duwende_out_of_range_dodges() -> None:
    state = board(
        [kubo((55.0, 35.0)), unit("a", pos=(10.0, 10.0))],
        [enemy("d", EnemyType.DUWENDE, pos=(30.0, 10.0), target="a")],
    )
    new, events = run(state)
    assert types(events) == [EventType.DODGE]
    assert find_unit(new, "a").stolen_by is None


def test_duwende_never_steals_the_kubo() -> None:
    state = board(
        [kubo((30.0, 20.0))],
        [enemy("d", EnemyType.DUWENDE, pos=(34.0, 20.0), target=KUBO_ID)],
    )
    new, events = run(state)
    assert events == ()
    assert find_unit(new, KUBO_ID).stolen_by is None
    assert find_enemy(new, "d").carrying is None


def test_two_duwendes_cannot_steal_the_same_unit() -> None:
    state = board(
        [kubo((55.0, 35.0)), unit("a", pos=(10.0, 10.0))],
        [
            enemy("d1", EnemyType.DUWENDE, pos=(14.0, 10.0), target="a"),
            enemy("d2", EnemyType.DUWENDE, pos=(14.0, 12.0), target="a"),
        ],
    )
    new, events = run(state)
    assert types(events) == [EventType.STEAL]
    assert find_unit(new, "a").stolen_by == "d1"
    assert find_enemy(new, "d2").carrying is None


def test_stolen_unit_cannot_act_be_targeted_or_move() -> None:
    state = board(
        [
            kubo((55.0, 35.0)),
            unit("a", pos=(10.0, 10.0), stolen_by="d"),
            unit("h", UnitClass.HEALER, (14.0, 10.0)),
            unit("b", pos=(40.0, 30.0)),
        ],
        [
            enemy("d", EnemyType.DUWENDE, pos=(2.0, 2.0), carrying="a"),
            enemy("s", pos=(10.0, 14.0)),
        ],
    )
    assert intent_error(state, atk("a", "s")) == "cmd.unknown"
    assert intent_error(state, power("a", "s")) == "cmd.unknown"
    assert intent_error(state, heal("h", "a")) == "cmd.unknown"
    assert pick_target(state.enemies[1], state) == "h"
    moved = with_positions(state, {"a": (30.0, 30.0)})
    assert find_unit(moved, "a").position == (10.0, 10.0)
    assert "a" not in illegal_moves(moved)


def test_stolen_unit_not_scored_but_not_a_loss() -> None:
    free = board([kubo(), unit("a"), unit("b")])
    stolen = board([kubo(), unit("a", stolen_by="d"), unit("b")])
    assert score(stolen) == score(free) - 10
    all_stolen = board([kubo(), unit("a", stolen_by="d")])
    assert check_outcome(all_stolen) is Outcome.CONTINUE


def test_carrying_duwende_picks_no_target_and_does_not_attack() -> None:
    state = board(
        [kubo((55.0, 35.0)), unit("a", pos=(10.0, 10.0)), unit("b", pos=(14.0, 10.0))],
        [enemy("d", EnemyType.DUWENDE, pos=(12.0, 10.0), target="b", carrying="a")],
    )
    assert pick_target(state.enemies[0], state) is None
    _, events = run(state)
    assert events == ()


def test_flee_point_goes_to_nearest_edge_twelve_cm() -> None:
    carrier = enemy("d", EnemyType.DUWENDE, pos=(30.0, 25.0))
    assert flee_point(carrier, W, H) == pytest.approx((30.0, 37.0))
    west = enemy("d", EnemyType.DUWENDE, pos=(8.0, 20.0))
    assert flee_point(west, W, H) == pytest.approx((0.0, 20.0))
    east = enemy("d", EnemyType.DUWENDE, pos=(52.0, 20.0))
    assert flee_point(east, W, H) == pytest.approx((60.0, 20.0))


def test_flee_ties_prefer_north_then_east_south_west() -> None:
    centre = enemy("d", EnemyType.DUWENDE, pos=(30.0, 20.0))
    assert flee_point(centre, W, H) == pytest.approx((30.0, 8.0))


def test_at_edge_uses_enemy_radius() -> None:
    assert at_edge((30.0, 2.0), W, H)
    assert not at_edge((30.0, 2.5), W, H)
    assert at_edge((60.0, 20.0), W, H)


def test_begin_turn_flees_without_intent_event() -> None:
    state = board(
        [kubo((55.0, 35.0)), unit("a", pos=(10.0, 10.0), stolen_by="d")],
        [enemy("d", EnemyType.DUWENDE, pos=(30.0, 25.0), carrying="a")],
        turn=10,
    )
    new, events = begin_turn(state)
    assert find_enemy(new, "d").position == pytest.approx((30.0, 37.0))
    assert find_enemy(new, "d").carrying == "a"
    assert EventType.INTENT not in types(events)
    assert find_unit(new, "a").stolen_by == "d"


def test_flee_takes_twelve_cm_per_turn_then_escapes_next_turn() -> None:
    state = board(
        [kubo((55.0, 35.0)), unit("a", pos=(10.0, 10.0), stolen_by="d")],
        [enemy("d", EnemyType.DUWENDE, pos=(30.0, 15.0), carrying="a")],
        turn=10,
    )
    first, events1 = begin_turn(state)
    assert find_enemy(first, "d").position == pytest.approx((30.0, 3.0))
    second, events2 = begin_turn(first)
    assert at_edge(find_enemy(second, "d").position, W, H) or not second.enemies
    third, events3 = begin_turn(second)
    assert EventType.ESCAPE not in types(events1)
    escaped = [e for e in (*events2, *events3) if e.type is EventType.ESCAPE]
    assert len(escaped) == 1
    assert not third.enemies


def test_escape_loses_the_unit_for_the_night() -> None:
    state = board(
        [kubo((55.0, 35.0)), unit("a", pos=(10.0, 10.0), stolen_by="d"), unit("b")],
        [enemy("d", EnemyType.DUWENDE, pos=(30.0, 0.0), carrying="a")],
        turn=10,
    )
    new, events = begin_turn(state)
    assert [e for e in events if e.type is EventType.ESCAPE] == [events[0]]
    assert events[0].src == "d" and events[0].dst == "a"
    assert events[0].pos == (30.0, 0.0)
    assert all(e.id != "d" for e in new.enemies)
    lost = find_unit(new, "a")
    assert lost.is_lost and lost.stolen_by is None
    assert lost.hp == find_unit(state, "a").hp
    assert not lost.is_targetable and not lost.can_act
    assert score(new) == score(state)
    assert score(new) == score(board([kubo((55.0, 35.0)), unit("b")]))


def test_escape_of_last_non_kubo_unit_loses_the_night() -> None:
    state = board(
        [kubo((55.0, 35.0)), unit("a", pos=(10.0, 10.0), stolen_by="d")],
        [enemy("d", EnemyType.DUWENDE, pos=(30.0, 0.0), carrying="a")],
        turn=10,
    )
    new, _ = begin_turn(state)
    assert check_outcome(new) is Outcome.LOSE
    _, events = resolve_turn(new, [])
    assert events[-1].type is EventType.LOSE


def test_escape_with_other_units_standing_continues() -> None:
    state = board(
        [kubo((55.0, 35.0)), unit("a", stolen_by="d"), unit("b", pos=(40.0, 30.0))],
        [enemy("d", EnemyType.DUWENDE, pos=(30.0, 0.0), carrying="a")],
        turn=10,
    )
    new, _ = begin_turn(state)
    assert check_outcome(new) is not Outcome.LOSE
    assert score(new) == 10 + 10 * 5


def test_escape_without_captive_just_removes_the_duwende() -> None:
    state = board(
        [kubo((55.0, 35.0)), unit("b")],
        [enemy("d", EnemyType.DUWENDE, pos=(30.0, 0.0), carrying="ghost")],
        turn=10,
    )
    new, events = begin_turn(state)
    assert EventType.ESCAPE not in types(events)
    assert all(e.id != "d" for e in new.enemies)


def test_killing_the_carrier_returns_the_unit_where_it_stands() -> None:
    state = board(
        [
            kubo((55.0, 35.0)),
            unit("a", pos=(10.0, 10.0), stolen_by="d", hp=3),
            unit("b", pos=(18.0, 10.0)),
        ],
        [enemy("d", EnemyType.DUWENDE, pos=(20.0, 12.0), hp=1, carrying="a")],
    )
    new, events = run(state, atk("b", "d"))
    assert types(events) == [
        EventType.ATTACK,
        EventType.DEFEAT_ENEMY,
        EventType.RETURN,
    ]
    back = events[2]
    assert back.src == "d" and back.dst == "a" and back.pos == (20.0, 12.0)
    freed = find_unit(new, "a")
    assert freed.position == (20.0, 12.0)
    assert freed.stolen_by is None and freed.hp == 3 and not freed.is_lost
    assert min(x for x, _ in freed.hull) == pytest.approx(18.5)
    nxt, _ = begin_turn(new)
    assert intent_error(nxt, atk("a", "d")) == "cmd.unknown"
    assert find_unit(nxt, "a").can_act


def test_killing_a_carrier_by_sweep_also_returns_the_unit() -> None:
    state = board(
        [
            kubo((55.0, 35.0)),
            unit("a", pos=(10.0, 10.0), stolen_by="d"),
            unit("b", pos=(18.0, 10.0), power=PowerId.P05),
        ],
        [enemy("d", EnemyType.DUWENDE, pos=(20.0, 12.0), hp=1, carrying="a")],
    )
    new, events = run(state, power("b"))
    assert EventType.RETURN in types(events)
    assert find_unit(new, "a").position == (20.0, 12.0)


def test_killing_a_carrier_with_stale_captive_returns_nothing() -> None:
    state = board(
        [
            kubo((55.0, 35.0)),
            unit("a", pos=(10.0, 10.0), stolen_by="other"),
            unit("b", pos=(18.0, 10.0)),
        ],
        [enemy("d", EnemyType.DUWENDE, pos=(20.0, 12.0), hp=1, carrying="a")],
    )
    new, events = run(state, atk("b", "d"))
    assert EventType.RETURN not in types(events)
    assert find_unit(new, "a").stolen_by == "other"
    ghost = board(
        [kubo((55.0, 35.0)), unit("b", pos=(18.0, 10.0))],
        [enemy("d", EnemyType.DUWENDE, pos=(20.0, 12.0), hp=1, carrying="ghost")],
    )
    _, events = run(ghost, atk("b", "d"))
    assert EventType.RETURN not in types(events)


def test_stolen_walls_and_auras_do_not_block() -> None:
    wall = unit("w", UnitClass.WALL, (20.0, 10.0), stolen_by="d")
    aura = unit("c", UnitClass.CHARM, (30.0, 10.0), power=PowerId.P07, is_lost=True)
    state = board(
        [kubo((55.0, 35.0)), wall, aura, unit("a", pos=(40.0, 10.0))],
        [enemy("s", pos=(10.0, 10.0))],
    )
    reached = move_toward(state.enemies[0], find_unit(state, "a").hull, state)
    assert reached[0] > 20.0


def test_status_tags_round_trip() -> None:
    base = unit("a")
    assert unit_status_tags(base) == ()
    marked = apply_unit_tags(base, ["out_1", "stolen_by:e_duwende_1", "lost"])
    assert marked.out_turns == 1
    assert marked.stolen_by == "e_duwende_1" and marked.is_lost
    assert unit_status_tags(marked) == ("out_1", "stolen_by:e_duwende_1", "lost")
    assert apply_unit_tags(marked, ["down", "out_x", "stolen_by:"]) == base
    carrier = enemy("e_duwende_1", EnemyType.DUWENDE)
    assert enemy_status_tags(carrier) == ()
    loaded = apply_enemy_tags(carrier, ["carrying:u_3"])
    assert loaded.carrying == "u_3"
    assert enemy_status_tags(loaded) == ("carrying:u_3",)
    assert apply_enemy_tags(loaded, ["carrying:", "other"]).carrying is None


def test_chained_night_with_both_enemy_kinds_is_deterministic() -> None:
    state = board(
        [
            kubo((30.0, 20.0)),
            unit("a", pos=(6.0, 10.0)),
            unit("b", pos=(40.0, 25.0), hp=2),
        ],
        [
            enemy("t", EnemyType.TIKBALANG, pos=(10.0, 10.0), target="a"),
            enemy("d", EnemyType.DUWENDE, pos=(44.0, 25.0), target="b"),
        ],
        turn=1,
    )
    runs = []
    for _ in range(2):
        current = state
        log: list[Event] = []
        for _ in range(4):
            current, events = resolve_turn(current, [])
            log.extend(events)
            current, events = begin_turn(current)
            log.extend(events)
        runs.append((current, tuple(log)))
    assert runs[0] == runs[1]
    kinds = {e.type for e in runs[0][1]}
    assert EventType.THROWN in kinds or EventType.PUSH in kinds
    assert EventType.STEAL in kinds
    assert of_type(runs[0][1], EventType.STEAL)

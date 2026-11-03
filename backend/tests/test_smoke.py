from dataclasses import replace

import pytest

from rules.resolve import (
    SMOKE_CLEAR_RADIUS_CM,
    SMOKE_RADIUS_CM,
    BoardState,
    EnemyState,
    EnemyType,
    EventType,
    Smoke,
    apply_unit_tags,
    begin_turn,
    start_night,
    unit_status_tags,
)
from rules.units import Difficulty, PowerId, UnitClass
from tests.test_resolve import (
    atk,
    board,
    enemy,
    find_enemy,
    find_unit,
    kubo,
    of_type,
    power,
    run,
    unit,
)


def kapre(turn_spawned: int, pos: tuple[float, float] = (30.0, 10.0)) -> EnemyState:
    return enemy("k", EnemyType.KAPRE, pos=pos, spawn_turn=turn_spawned)


def after_begin(turn_before: int, spawn_turn: int) -> BoardState:
    state = board(
        [kubo((30.0, 38.0)), unit("a", pos=(5.0, 5.0))],
        [kapre(spawn_turn)],
        turn=turn_before,
    )
    new, _ = begin_turn(state)
    return new


@pytest.mark.parametrize(
    ("turn_before", "smoked"),
    [(3, False), (4, True), (5, False), (6, True), (7, False)],
)
def test_kapre_smokes_on_second_and_fourth_turn_alive(
    turn_before: int, smoked: bool
) -> None:
    new = after_begin(turn_before, 4)
    assert bool(new.smoke) is smoked


def test_smoke_event_and_center_follow_kapre() -> None:
    state = board(
        [kubo((30.0, 38.0)), unit("a", pos=(5.0, 5.0))],
        [kapre(4)],
        turn=4,
    )
    new, events = begin_turn(state)
    cloud = new.smoke[0]
    assert cloud.source_id == "k"
    assert cloud.center == find_enemy(new, "k").position
    assert cloud.radius_cm == SMOKE_RADIUS_CM == 10.0
    smoke_events = of_type(events, EventType.SMOKE)
    assert len(smoke_events) == 1
    assert smoke_events[0].pos == cloud.center


def test_smoke_lasts_one_turn() -> None:
    state = after_begin(4, 4)
    assert state.smoke
    nxt, _ = begin_turn(replace(state, turn=5))
    assert nxt.smoke == ()


def test_dead_kapre_makes_no_smoke() -> None:
    state = board(
        [kubo((30.0, 38.0)), unit("a", pos=(5.0, 5.0))],
        [replace(kapre(4), hp=0)],
        turn=4,
    )
    new, _ = begin_turn(state)
    assert new.smoke == ()


def test_other_enemies_make_no_smoke() -> None:
    state = board(
        [kubo((30.0, 38.0)), unit("a", pos=(5.0, 5.0))],
        [enemy("t", EnemyType.TIKBALANG, spawn_turn=1)],
        turn=1,
    )
    new, _ = begin_turn(state)
    assert new.smoke == ()


def smoky_state(
    extra_enemies: list[EnemyState], unit_pos: tuple[float, float]
) -> BoardState:
    return board(
        [kubo((55.0, 35.0)), unit("f", pos=unit_pos, owner="p1")],
        extra_enemies,
        smoke=(Smoke("k", (20.0, 20.0)),),
    )


def test_unit_in_smoke_cannot_hit_enemy_outside() -> None:
    state = smoky_state([enemy("e", pos=(20.0, 31.5))], (20.0, 25.0))
    new, events = run(state, atk("f", "e"))
    assert find_enemy(new, "e").hp == 3
    assert of_type(events, EventType.DODGE)


def test_unit_in_smoke_can_hit_enemy_inside() -> None:
    state = smoky_state([enemy("e", pos=(20.0, 22.0))], (20.0, 25.0))
    new, _ = run(state, atk("f", "e"))
    assert find_enemy(new, "e").hp == 1


def test_unit_outside_smoke_can_hit_enemy_inside() -> None:
    state = smoky_state([enemy("e", pos=(20.0, 28.5))], (20.0, 32.0))
    _, events = run(state, atk("f", "e"))
    assert not of_type(events, EventType.DODGE)


def test_unit_outside_smoke_hits_enemy_outside() -> None:
    state = smoky_state([enemy("e", pos=(20.0, 36.0))], (20.0, 33.0))
    new, _ = run(state, atk("f", "e"))
    assert find_enemy(new, "e").hp == 1


def test_smoke_blocks_targeted_power_from_inside() -> None:
    state = board(
        [
            kubo((55.0, 35.0)),
            unit("f", pos=(20.0, 25.0), power=PowerId.P03),
        ],
        [enemy("e", pos=(20.0, 31.5))],
        smoke=(Smoke("k", (20.0, 20.0)),),
    )
    new, events = run(state, power("f", "e"))
    assert find_enemy(new, "e").position == (20.0, 31.5)
    assert of_type(events, EventType.DODGE)


def liwanag(charm_pos: tuple[float, float], cloud: tuple[float, float]) -> BoardState:
    return board(
        [
            kubo((55.0, 35.0)),
            unit("c", UnitClass.CHARM, charm_pos, power=PowerId.P08),
            unit("f", pos=(20.0, 25.0), owner="p1"),
        ],
        [enemy("e", pos=(20.0, 28.0))],
        smoke=(Smoke("k", cloud),),
    )


def test_p08_clears_smoke_within_twelve_cm() -> None:
    state = liwanag((20.0, 32.0), (20.0, 20.0))
    new, events = run(state, power("c"), atk("f", "e"))
    assert new.smoke == ()
    cleared = of_type(events, EventType.SMOKE_CLEARED)
    assert [(e.src, e.dst) for e in cleared] == [("c", "k")]
    assert find_enemy(new, "e").hp == 1
    assert find_unit(new, "c").cooldown == 1


def test_p08_keeps_smoke_beyond_twelve_cm() -> None:
    state = liwanag((20.0, 36.0), (20.0, 20.0))
    new, events = run(state, power("c"))
    assert len(new.smoke) == 1
    assert not of_type(events, EventType.SMOKE_CLEARED)


def test_p08_reach_boundary_uses_tolerance() -> None:
    assert SMOKE_CLEAR_RADIUS_CM == 12.0
    inside = liwanag((20.0, 33.0 + 1.5), (20.0, 20.0))
    outside = liwanag((20.0, 36.0), (20.0, 20.0))
    assert run(inside, power("c"))[0].smoke == ()
    assert len(run(outside, power("c"))[0].smoke) == 1


def test_p08_clears_only_nearby_cloud() -> None:
    state = replace(
        liwanag((20.0, 32.0), (20.0, 20.0)),
        smoke=(Smoke("k", (20.0, 20.0)), Smoke("k2", (50.0, 5.0))),
    )
    new, _ = run(state, power("c"))
    assert [c.source_id for c in new.smoke] == ["k2"]


def test_p08_on_cooldown_is_invalid() -> None:
    state = liwanag((20.0, 32.0), (20.0, 20.0))
    state = replace(
        state,
        units=tuple(replace(u, cooldown=1) if u.id == "c" else u for u in state.units),
    )
    new, _ = run(state, power("c"))
    assert len(new.smoke) == 1


def test_smoke_covers_helpers() -> None:
    cloud = Smoke("k", (10.0, 10.0))
    assert cloud.covers_point((10.0, 20.0))
    assert not cloud.covers_point((10.0, 20.5))
    assert cloud.covers_hull(unit("x", pos=(10.0, 28.0)).hull) is False
    assert cloud.covers_hull(unit("x", pos=(10.0, 21.0)).hull)


def test_kapre_still_attacks_through_smoke() -> None:
    state = board(
        [kubo((40.0, 30.0)), unit("a", pos=(5.0, 5.0))],
        [enemy("k", EnemyType.KAPRE, pos=(40.0, 22.0), target="u_kubo")],
        smoke=(Smoke("k", (40.0, 22.0)),),
    )
    new, _ = run(state)
    assert find_unit(new, "u_kubo").hp == 7


def test_unit_tags_round_trip_for_plain_unit() -> None:
    u = unit("a")
    assert apply_unit_tags(u, unit_status_tags(u)) == u


def test_wave_kapre_smokes_on_turns_five_and_seven() -> None:
    state = start_night(
        [kubo((30.0, 20.0)), unit("a", pos=(25.0, 20.0))],
        Difficulty.NORMAL,
        2,
        60.0,
        40.0,
    )
    seen: dict[int, bool] = {}
    for _ in range(8):
        state, _ = begin_turn(state)
        seen[state.turn] = bool(state.smoke)
        state = replace(
            state,
            units=tuple(replace(u, hp=u.hp_max) for u in state.units),
            enemies=tuple(replace(e, hp=e.hp_max) for e in state.enemies),
        )
    assert [turn for turn, smoked in seen.items() if smoked] == [5, 7]

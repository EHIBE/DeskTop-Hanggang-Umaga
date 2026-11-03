from dataclasses import replace
from typing import Any

import pytest

from rules.lost import centroid_inside, update_lost
from rules.resolve import (
    EventType,
    apply_unit_tags,
    check_outcome,
    intent_error,
    score,
    unit_status_tags,
    with_positions,
)
from tests.test_resolve import (
    H,
    W,
    atk,
    board,
    enemy,
    find_unit,
    kubo,
    run,
    unit,
)


def test_unit_inside_stays_found() -> None:
    state = board([kubo(), unit("a", pos=(10.0, 10.0))])
    new, events = update_lost(state)
    assert new == state
    assert events == ()


@pytest.mark.parametrize(
    "pos",
    [(-0.5, 10.0), (W + 0.5, 10.0), (10.0, -0.5), (10.0, H + 0.5), (-20.0, -20.0)],
)
def test_centroid_outside_becomes_lost(pos: tuple[float, float]) -> None:
    state = board([kubo(), unit("a", pos=pos)])
    new, events = update_lost(state)
    assert find_unit(new, "a").off_desk
    assert [(e.type, e.src, e.pos) for e in events] == [(EventType.LOST, "a", pos)]


def test_edge_is_inside() -> None:
    a = unit("a", pos=(0.0, H))
    assert centroid_inside(a, W, H)
    assert not update_lost(board([kubo(), a]))[1]


def test_half_hull_overhang_with_centroid_inside_is_not_lost() -> None:
    state = board([kubo(), unit("a", pos=(0.5, 10.0))])
    assert update_lost(state)[1] == ()


def test_lost_unit_cannot_act_or_be_targeted() -> None:
    state, _ = update_lost(board([kubo(), unit("a", pos=(-5.0, 10.0))], [enemy("e")]))
    a = find_unit(state, "a")
    assert not a.can_act
    assert not a.is_targetable
    assert intent_error(state, atk("a", "e")) == "cmd.unknown"


def test_enemy_ignores_lost_unit() -> None:
    state, _ = update_lost(
        board(
            [kubo((55.0, 35.0)), unit("a", pos=(-1.0, 10.0))],
            [enemy("e", target="a")],
        )
    )
    new, events = run(state)
    assert find_unit(new, "a").hp == find_unit(state, "a").hp
    assert events == ()


def test_lost_unit_returns_when_placed_back() -> None:
    lost, _ = update_lost(board([kubo(), unit("a", pos=(-5.0, 10.0))]))
    moved = with_positions(lost, {"a": (12.0, 12.0)})
    found, events = update_lost(moved)
    a = find_unit(found, "a")
    assert not a.off_desk
    assert a.can_act
    assert a.start == (12.0, 12.0)
    assert [(e.type, e.src) for e in events] == [(EventType.FOUND, "a")]


def test_lost_unit_still_off_is_unchanged() -> None:
    lost, _ = update_lost(board([kubo(), unit("a", pos=(-5.0, 10.0))]))
    again, events = update_lost(with_positions(lost, {"a": (-6.0, 10.0)}))
    assert find_unit(again, "a").off_desk
    assert events == ()


def test_update_is_idempotent() -> None:
    lost, _ = update_lost(board([kubo(), unit("a", pos=(-5.0, 10.0))]))
    assert update_lost(lost) == (lost, ())


@pytest.mark.parametrize(
    "over",
    [{"hp": 0}, {"stolen_by": "d"}, {"is_lost": True}, {"out_turns": 1}],
)
def test_other_absent_states_are_left_alone(over: dict[str, Any]) -> None:
    state = board([kubo(), unit("a", pos=(-5.0, 10.0), **over)])
    new, events = update_lost(state)
    assert new == state
    assert events == ()


def test_kubo_can_be_lost() -> None:
    state = board([kubo((-3.0, 5.0)), unit("a")])
    new, events = update_lost(state)
    assert find_unit(new, "u_kubo").off_desk
    assert len(events) == 1


def test_tags_round_trip() -> None:
    a = replace(unit("a"), off_desk=True)
    assert "off_desk" in unit_status_tags(a)
    assert apply_unit_tags(unit("a"), unit_status_tags(a)).off_desk


def test_lost_unit_not_scored_and_not_down() -> None:
    plain = board([kubo(), unit("a")])
    lost, _ = update_lost(board([kubo(), unit("a", pos=(-5.0, 5.0))]))
    assert score(lost) == score(plain) - 10
    assert check_outcome(lost).value == "continue"

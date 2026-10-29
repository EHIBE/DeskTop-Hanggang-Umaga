import random
import statistics
import time
from dataclasses import replace
from typing import Any

import pytest

from rules.enemies import enemy_stats
from rules.geometry import Point, hull_point_distance, square_hull
from rules.resolve import (
    POWER_COOLDOWN,
    TURNS_PER_NIGHT,
    Action,
    BoardState,
    Edge,
    EnemyState,
    EnemyType,
    Event,
    EventType,
    Intent,
    Outcome,
    Part,
    UnitState,
    bayani,
    begin_turn,
    check_outcome,
    illegal_moves,
    intent_error,
    moved_kubo,
    resolve_turn,
    score,
    start_night,
    with_positions,
)
from rules.units import (
    CLASS_TEMPLATES,
    KUBO_HP,
    Difficulty,
    PowerId,
    RangeClass,
    UnitClass,
)

W = 60.0
H = 40.0
HALF = 1.5
KUBO_ID = "u_kubo"


def unit(
    uid: str,
    unit_class: UnitClass = UnitClass.FIGHTER,
    pos: Point = (30.0, 20.0),
    power: PowerId | None = None,
    owner: str | None = None,
    **over: Any,
) -> UnitState:
    template = CLASS_TEMPLATES[unit_class]
    base = UnitState(
        id=uid,
        unit_class=unit_class,
        hp=template.hp,
        hp_max=template.hp,
        atk=template.atk,
        move=template.move,
        range=template.range,
        power_id=power or template.powers[0],
        cooldown=0,
        position=pos,
        start=pos,
        hull_offsets=square_hull((0.0, 0.0), HALF),
        owner=owner,
    )
    return replace(base, **over)


def kubo(pos: Point = (30.0, 20.0), **over: Any) -> UnitState:
    params: dict[str, Any] = {"hp": 10, "hp_max": 10}
    params.update(over)
    return unit(KUBO_ID, UnitClass.KUBO, pos, **params)


def enemy(
    eid: str,
    etype: EnemyType = EnemyType.ASWANG,
    pos: Point = (30.0, 10.0),
    part: Part | None = None,
    target: str | None = None,
    difficulty: Difficulty = Difficulty.NORMAL,
    **over: Any,
) -> EnemyState:
    hp, atk, move_cm, range_cm, flies = enemy_stats(etype, part, difficulty)
    base = EnemyState(
        id=eid,
        type=etype,
        part=part,
        hp=hp,
        hp_max=hp,
        atk=atk,
        move_cm=move_cm,
        range_cm=range_cm,
        flies=flies,
        position=pos,
        spawn_turn=1,
        target_id=target,
        intent_dmg=max(1, atk) if target else None,
    )
    return replace(base, **over)


def board(
    units: list[UnitState],
    enemies: list[EnemyState] | None = None,
    turn: int = 1,
    difficulty: Difficulty = Difficulty.NORMAL,
    players: int = 2,
    flags: frozenset[str] = frozenset(),
    **over: Any,
) -> BoardState:
    return BoardState(
        turn=turn,
        difficulty=difficulty,
        players=players,
        play_w_cm=W,
        play_h_cm=H,
        units=tuple(units),
        enemies=tuple(enemies or []),
        flags=flags,
        **over,
    )


def types(events: tuple[Event, ...]) -> list[EventType]:
    return [e.type for e in events]


def of_type(events: tuple[Event, ...], kind: EventType) -> list[Event]:
    return [e for e in events if e.type is kind]


def find_unit(state: BoardState, uid: str) -> UnitState:
    return next(u for u in state.units if u.id == uid)


def find_enemy(state: BoardState, eid: str) -> EnemyState:
    return next(e for e in state.enemies if e.id == eid)


def atk(uid: str, target: str | None) -> Intent:
    return Intent(uid, Action.ATTACK, target)


def power(uid: str, target: str | None = None) -> Intent:
    return Intent(uid, Action.POWER, target)


def heal(uid: str, target: str | None) -> Intent:
    return Intent(uid, Action.HEAL, target)


def cd_state(units: list[UnitState], enemies: list[EnemyState]) -> BoardState:
    return board([kubo((55.0, 35.0)), *units], enemies)


def run(state: BoardState, *intents: Intent) -> tuple[BoardState, tuple[Event, ...]]:
    return resolve_turn(state, intents)


def test_turns_per_night_and_cooldown_catalog() -> None:
    assert TURNS_PER_NIGHT == 8
    expected = {
        "P01": 0,
        "P02": 1,
        "P03": 1,
        "P04": 2,
        "P05": 1,
        "P06": 2,
        "P08": 1,
        "P09": 1,
        "P10": 2,
        "P11": 0,
        "P12": 2,
    }
    for pid, cooldown in expected.items():
        assert POWER_COOLDOWN[PowerId(pid)] == cooldown


def test_unit_properties() -> None:
    u = unit("u_2", pos=(10.0, 10.0), hp=0)
    assert u.is_down
    assert not u.is_kubo
    assert kubo().is_kubo
    assert (8.5, 8.5) in u.hull
    assert (11.5, 11.5) in u.hull


def test_enemy_is_alive() -> None:
    assert enemy("a").is_alive
    assert not enemy("a", hp=0).is_alive


def test_event_defaults() -> None:
    event = Event(EventType.WIN)
    assert event.src is None and event.pos is None and event.edge is None


def test_event_type_members() -> None:
    assert {e.value for e in EventType} == {
        "attack",
        "dodge",
        "spawn",
        "intent",
        "heal",
        "power",
        "shield",
        "down",
        "push",
        "thrown",
        "steal",
        "return",
        "escape",
        "split",
        "reform",
        "kubo_hit",
        "defeat_enemy",
        "win",
        "lose",
    }


def test_start_night() -> None:
    state = start_night(
        [kubo(hp=KUBO_HP[Difficulty.MAHIRAP]), unit("u_2"), unit("u_3")],
        Difficulty.MAHIRAP,
        3,
        W,
        H,
        frozenset({"tabi_tabi"}),
    )
    assert state.turn == 0
    assert state.enemies == ()
    assert state.players == 3
    assert "tabi_tabi" in state.flags
    assert state.kubo is not None and state.kubo.hp == 8


def test_with_positions_updates_positions_and_hulls() -> None:
    state = board([kubo(), unit("u_2", pos=(10.0, 10.0))])
    big = square_hull((0.0, 0.0), 3.0)
    moved = with_positions(
        state, {"u_2": (12.0, 11.0), "nobody": (1.0, 1.0)}, {"u_2": big}
    )
    u = find_unit(moved, "u_2")
    assert u.position == (12.0, 11.0)
    assert u.start == (10.0, 10.0)
    assert u.hull_offsets == big
    assert find_unit(moved, KUBO_ID).position == (30.0, 20.0)
    assert with_positions(state, {}) == state


def test_illegal_moves_use_move_class_and_tolerance() -> None:
    state = board(
        [
            kubo(),
            unit("fast", UnitClass.SCOUT, (10.0, 10.0)),
            unit("slow", UnitClass.HEALER, (10.0, 20.0)),
            unit("charm", UnitClass.CHARM, (40.0, 30.0)),
        ]
    )
    moved = with_positions(
        state,
        {"fast": (26.9, 10.0), "slow": (19.1, 20.0), "charm": (41.5, 30.0)},
    )
    assert illegal_moves(moved) == ("slow", "charm")
    ok = with_positions(state, {"fast": (27.0, 10.0), "slow": (19.0, 20.0)})
    assert illegal_moves(ok) == ()


def test_illegal_moves_ignore_kubo_and_down_units() -> None:
    state = board([kubo(), unit("a", pos=(10.0, 10.0), hp=0)])
    moved = with_positions(state, {KUBO_ID: (50.0, 5.0), "a": (50.0, 5.0)})
    assert illegal_moves(moved) == ()


def test_moved_kubo_threshold() -> None:
    state = board([kubo(), unit("a")])
    assert not moved_kubo(with_positions(state, {KUBO_ID: (32.0, 20.0)}))
    assert moved_kubo(with_positions(state, {KUBO_ID: (32.1, 20.0)}))
    assert not moved_kubo(board([unit("a")]))


def test_intent_error_unknown_unit_down_unit_and_target() -> None:
    state = board(
        [kubo(), unit("a", hp=0), unit("b")], [enemy("e1"), enemy("e2", hp=0)]
    )
    assert intent_error(state, atk("ghost", "e1")) == "cmd.unknown"
    assert intent_error(state, atk("a", "e1")) == "cmd.unknown"
    assert intent_error(state, atk("b", "e_missing")) == "cmd.unknown"
    assert intent_error(state, atk("b", "e2")) == "cmd.unknown"
    assert intent_error(state, atk("b", None)) == "cmd.unknown"
    assert intent_error(state, atk("b", "e1")) is None


def test_intent_error_no_atk() -> None:
    state = board(
        [
            kubo(),
            unit("charm", UnitClass.CHARM),
            unit("wall", UnitClass.WALL),
            unit("zero", UnitClass.FIGHTER, atk=0),
            unit("noreach", UnitClass.FIGHTER, range=RangeClass.NONE),
        ],
        [enemy("e1")],
    )
    for uid in ("charm", "wall", "zero", "noreach", KUBO_ID):
        assert intent_error(state, atk(uid, "e1")) == "cmd.no_atk"


def test_intent_error_does_not_check_range() -> None:
    state = board([kubo(), unit("a", pos=(1.0, 1.0))], [enemy("e1", pos=(59.0, 39.0))])
    assert intent_error(state, atk("a", "e1")) is None


def test_intent_error_heal_requires_p01() -> None:
    state = board(
        [
            kubo(),
            unit("h", UnitClass.HEALER, power=PowerId.P01),
            unit("g", UnitClass.HEALER, power=PowerId.P02),
        ]
    )
    assert intent_error(state, heal("h", "g")) is None
    assert intent_error(state, heal("h", KUBO_ID)) is None
    assert intent_error(state, power("h", "g")) is None
    assert intent_error(state, heal("g", "h")) == "cmd.unknown"
    assert intent_error(state, heal("h", "ghost")) == "cmd.unknown"
    assert intent_error(state, heal("h", None)) == "cmd.unknown"


def test_intent_error_down_heal_target() -> None:
    state = board(
        [kubo(), unit("h", UnitClass.HEALER, power=PowerId.P01), unit("x", hp=0)]
    )
    assert intent_error(state, heal("h", "x")) == "cmd.unknown"


def test_intent_error_power_targets() -> None:
    state = board(
        [
            kubo(),
            unit("healer", UnitClass.HEALER, power=PowerId.P02),
            unit("fighter", power=PowerId.P03),
            unit("reach", UnitClass.REACH, power=PowerId.P04),
            unit("fighter5", power=PowerId.P05),
            unit("charm6", UnitClass.CHARM, power=PowerId.P06),
            unit("charm7", UnitClass.CHARM, power=PowerId.P07),
            unit("charm8", UnitClass.CHARM, power=PowerId.P08),
            unit("reach9", UnitClass.REACH, power=PowerId.P09),
            unit("ranged10", UnitClass.RANGED, power=PowerId.P10),
            unit("scout11", UnitClass.SCOUT, power=PowerId.P11),
            unit("ranged12", UnitClass.RANGED, power=PowerId.P12),
        ],
        [
            enemy("e1"),
            enemy("low", EnemyType.MANANANGGAL, part=Part.LOWER),
            enemy("up", EnemyType.MANANANGGAL, part=Part.UPPER),
        ],
    )
    assert intent_error(state, power("healer", "fighter")) is None
    assert intent_error(state, power("healer", "e1")) == "cmd.unknown"
    assert intent_error(state, power("healer", None)) == "cmd.unknown"
    for pid in ("fighter", "reach", "reach9", "scout11"):
        assert intent_error(state, power(pid, "e1")) is None
        assert intent_error(state, power(pid, "fighter")) == "cmd.unknown"
        assert intent_error(state, power(pid, None)) == "cmd.unknown"
    assert intent_error(state, power("fighter5", None)) is None
    assert intent_error(state, power("fighter5", "e1")) is None
    assert intent_error(state, power("fighter5", "ghost")) == "cmd.unknown"
    assert intent_error(state, power("charm6", None)) is None
    assert intent_error(state, power("charm6", KUBO_ID)) is None
    assert intent_error(state, power("charm6", "fighter")) == "cmd.unknown"
    assert intent_error(state, power("charm7", None)) == "cmd.unknown"
    assert intent_error(state, power("charm8", None)) is None
    assert intent_error(state, power("ranged10", None)) is None
    assert intent_error(state, power("ranged12", "low")) is None
    assert intent_error(state, power("ranged12", "up")) == "cmd.unknown"
    assert intent_error(state, power("ranged12", "e1")) == "cmd.unknown"
    assert intent_error(state, power(KUBO_ID, None)) == "cmd.unknown"


def test_intent_error_power_on_cooldown() -> None:
    state = board(
        [kubo(), unit("r", UnitClass.REACH, power=PowerId.P04, cooldown=1)],
        [enemy("e1")],
    )
    assert intent_error(state, power("r", "e1")) == "cmd.unknown"
    ready = replace(state, units=(state.units[0], replace(state.units[1], cooldown=0)))
    assert intent_error(ready, power("r", "e1")) is None


def test_attack_hits_in_range_and_credits_owner() -> None:
    state = cd_state(
        [unit("a", pos=(10.0, 10.0), owner="p1")], [enemy("e1", pos=(14.0, 10.0))]
    )
    new, events = run(state, atk("a", "e1"))
    assert find_enemy(new, "e1").hp == 1
    assert events[0] == Event(EventType.ATTACK, "a", "e1", 2)
    assert new.damage_by_owner == (("p1", 2),)


def test_attack_out_of_range_dodges() -> None:
    state = cd_state(
        [unit("a", pos=(10.0, 10.0), owner="p1")], [enemy("e1", pos=(30.0, 10.0))]
    )
    new, events = run(state, atk("a", "e1"))
    assert find_enemy(new, "e1").hp == 3
    assert events == (Event(EventType.DODGE, "a", "e1"),)
    assert new.damage_by_owner == ()


@pytest.mark.parametrize(("dx", "hit"), [(9.4, True), (9.6, False)])
def test_attack_range_tolerance(dx: float, hit: bool) -> None:
    state = cd_state(
        [unit("a", pos=(10.0, 10.0))], [enemy("e1", pos=(10.0 + dx, 10.0))]
    )
    _, events = run(state, atk("a", "e1"))
    assert types(events)[0] is (EventType.ATTACK if hit else EventType.DODGE)


def test_attack_adds_atk_bonus() -> None:
    state = cd_state(
        [unit("a", pos=(10.0, 10.0), atk_bonus=1)],
        [enemy("e1", EnemyType.KAPRE, pos=(14.0, 10.0))],
    )
    new, _ = run(state, atk("a", "e1"))
    assert find_enemy(new, "e1").hp == 5


def test_min_damage_is_one() -> None:
    state = cd_state(
        [unit("a", UnitClass.SCOUT, (10.0, 10.0), atk_bonus=-3)],
        [enemy("e1", EnemyType.KAPRE, pos=(14.0, 10.0))],
    )
    new, _ = run(state, atk("a", "e1"))
    assert find_enemy(new, "e1").hp == 7


def test_attack_on_dead_enemy_dodges() -> None:
    state = cd_state(
        [unit("a", pos=(10.0, 10.0)), unit("b", pos=(10.0, 14.0))],
        [enemy("e1", pos=(14.0, 10.0), hp=2)],
    )
    new, events = run(state, atk("a", "e1"), atk("b", "e1"))
    assert types(events) == [
        EventType.ATTACK,
        EventType.DEFEAT_ENEMY,
        EventType.DODGE,
    ]
    assert new.enemies == ()


def test_kill_emits_defeat_removes_enemy_and_counts() -> None:
    state = cd_state(
        [unit("a", pos=(10.0, 10.0), owner="p2")],
        [enemy("e1", pos=(14.0, 10.0), hp=1)],
    )
    new, events = run(state, atk("a", "e1"))
    assert types(events) == [EventType.ATTACK, EventType.DEFEAT_ENEMY]
    assert events[0].dmg == 1
    assert new.enemies == ()
    assert new.enemies_defeated == 1
    assert new.damage_by_owner == (("p2", 1),)


def test_unowned_unit_damage_is_not_credited() -> None:
    state = cd_state([unit("a", pos=(10.0, 10.0))], [enemy("e1", pos=(14.0, 10.0))])
    new, _ = run(state, atk("a", "e1"))
    assert new.damage_by_owner == ()


def test_first_valid_intent_per_unit_only() -> None:
    state = cd_state(
        [unit("a", pos=(10.0, 10.0))],
        [enemy("e1", pos=(14.0, 10.0)), enemy("e2", pos=(10.0, 14.0))],
    )
    new, events = run(state, atk("a", "ghost"), atk("a", "e2"), atk("a", "e1"))
    assert find_enemy(new, "e2").hp == 1
    assert find_enemy(new, "e1").hp == 3
    assert len(of_type(events, EventType.ATTACK)) == 1


def test_invalid_intents_are_ignored() -> None:
    state = cd_state([unit("c", UnitClass.CHARM)], [enemy("e1")])
    new, events = run(state, atk("c", "e1"))
    assert events == ()
    assert new.enemies == state.enemies


def test_phase_order_powers_then_heals_then_attacks() -> None:
    state = cd_state(
        [
            unit("a", pos=(10.0, 10.0)),
            unit("h", UnitClass.HEALER, (10.0, 14.0), power=PowerId.P01, hp=1),
            unit("s", UnitClass.WALL, (14.0, 14.0), power=PowerId.P02),
        ],
        [enemy("e1", pos=(14.0, 10.0))],
    )
    _, events = run(state, atk("a", "e1"), heal("h", "h"), power("s", "h"))
    assert types(events) == [
        EventType.POWER,
        EventType.SHIELD,
        EventType.HEAL,
        EventType.ATTACK,
    ]


def test_powers_resolve_in_confirmed_order() -> None:
    state = cd_state(
        [
            unit("r", UnitClass.REACH, (10.0, 10.0), power=PowerId.P04),
            unit("f", pos=(10.0, 14.0), power=PowerId.P03),
        ],
        [enemy("e1", pos=(14.0, 10.0)), enemy("e2", pos=(14.0, 14.0))],
    )
    _, events = run(state, power("f", "e2"), power("r", "e1"))
    assert [e.src for e in of_type(events, EventType.POWER)] == ["f", "r"]


def test_p01_heals_two_and_caps_at_max() -> None:
    state = cd_state(
        [
            unit("h", UnitClass.HEALER, (10.0, 10.0), power=PowerId.P01),
            unit("a", pos=(14.0, 10.0), hp=3),
            unit("b", pos=(10.0, 14.0), hp=5),
        ],
        [],
    )
    new, events = run(state, heal("h", "a"))
    assert find_unit(new, "a").hp == 5
    assert events == (Event(EventType.HEAL, "h", "a", 2),)
    new2, events2 = run(state, power("h", "b"))
    assert find_unit(new2, "b").hp == 6
    assert events2 == (Event(EventType.HEAL, "h", "b", 1),)


def test_p01_self_heal_and_kubo_heal() -> None:
    state = cd_state(
        [unit("h", UnitClass.HEALER, (50.0, 30.0), power=PowerId.P01, hp=1)], []
    )
    new, _ = run(state, heal("h", "h"))
    assert find_unit(new, "h").hp == 3
    hurt = replace(state, units=(replace(state.units[0], hp=4), state.units[1]))
    new, _ = run(hurt, heal("h", KUBO_ID))
    assert find_unit(new, KUBO_ID).hp == 6


@pytest.mark.parametrize(("gap", "ok"), [(13.9, True), (14.1, False)])
def test_p01_range_tolerance(gap: float, ok: bool) -> None:
    state = cd_state(
        [
            unit("h", UnitClass.HEALER, (10.0, 10.0), power=PowerId.P01),
            unit("a", pos=(10.0 + gap, 10.0), hp=2),
        ],
        [],
    )
    new, events = run(state, heal("h", "a"))
    assert (find_unit(new, "a").hp == 4) is ok
    assert types(events) == [EventType.HEAL if ok else EventType.DODGE]


def test_p01_cooldown_stays_zero() -> None:
    state = cd_state(
        [
            unit("h", UnitClass.HEALER, (10.0, 10.0), power=PowerId.P01),
            unit("a", pos=(14.0, 10.0), hp=1),
        ],
        [],
    )
    new, _ = run(state, heal("h", "a"))
    assert find_unit(new, "h").cooldown == 0
    assert intent_error(new, heal("h", "a")) is None


def test_p02_shield_absorbs_and_sets_cooldown() -> None:
    state = cd_state(
        [
            unit("w", UnitClass.WALL, (10.0, 10.0), power=PowerId.P02),
            unit("a", pos=(14.0, 10.0)),
        ],
        [enemy("e1", pos=(18.0, 10.0), target="a")],
    )
    new, events = run(state, power("w", "a"))
    assert types(events) == [EventType.POWER, EventType.SHIELD, EventType.ATTACK]
    assert events[1].dmg == 2
    assert events[2].dmg == 0
    assert find_unit(new, "a").hp == 6
    assert find_unit(new, "w").cooldown == 1
    assert intent_error(new, power("w", "a")) == "cmd.unknown"


def test_p02_cooldown_across_turns() -> None:
    state = cd_state(
        [
            unit("w", UnitClass.WALL, (10.0, 10.0), power=PowerId.P02),
            unit("a", pos=(14.0, 10.0)),
        ],
        [],
    )
    state, _ = run(state, power("w", "a"))
    assert find_unit(state, "w").cooldown == 1
    state, _ = run(state)
    assert find_unit(state, "w").cooldown == 0
    assert intent_error(state, power("w", "a")) is None


@pytest.mark.parametrize(("gap", "ok"), [(13.9, True), (14.1, False)])
def test_p02_range_tolerance(gap: float, ok: bool) -> None:
    state = cd_state(
        [
            unit("w", UnitClass.WALL, (10.0, 10.0), power=PowerId.P02),
            unit("a", pos=(10.0 + gap, 10.0)),
        ],
        [],
    )
    new, events = run(state, power("w", "a"))
    assert (find_unit(new, "a").shield == 2) is ok
    assert find_unit(new, "w").cooldown == (1 if ok else 0)
    assert (EventType.DODGE in types(events)) is not ok


def test_shield_partial_absorb_and_event_damage_is_hp_lost() -> None:
    state = cd_state(
        [unit("a", pos=(14.0, 10.0), shield=1)],
        [enemy("e1", EnemyType.KAPRE, pos=(20.0, 10.0), target="a")],
    )
    new, events = run(state)
    assert find_unit(new, "a").hp == 4
    assert find_unit(new, "a").shield == 0
    assert events[0] == Event(EventType.ATTACK, "e1", "a", 2)


def test_p03_pushes_eight_cm_away() -> None:
    state = cd_state(
        [unit("f", pos=(10.0, 10.0), power=PowerId.P03)],
        [enemy("e1", pos=(14.0, 10.0))],
    )
    new, events = run(state, power("f", "e1"))
    assert find_enemy(new, "e1").position == pytest.approx((22.0, 10.0))
    push = of_type(events, EventType.PUSH)[0]
    assert push.src == "f" and push.dst == "e1"
    assert push.pos == pytest.approx((22.0, 10.0))
    assert find_unit(new, "f").cooldown == 1


def test_p03_diagonal_push() -> None:
    state = cd_state(
        [unit("f", pos=(10.0, 10.0), power=PowerId.P03)],
        [enemy("e1", pos=(13.0, 14.0))],
    )
    new, _ = run(state, power("f", "e1"))
    assert find_enemy(new, "e1").position == pytest.approx((13.0 + 4.8, 14.0 + 6.4))


def test_p03_clamped_to_play_area() -> None:
    state = cd_state(
        [unit("f", pos=(50.0, 10.0), power=PowerId.P03)],
        [enemy("e1", pos=(54.0, 10.0))],
    )
    new, events = run(state, power("f", "e1"))
    assert find_enemy(new, "e1").position == (60.0, 10.0)
    assert of_type(events, EventType.PUSH)[0].pos == (60.0, 10.0)


def test_p03_zero_vector_pushes_north() -> None:
    state = cd_state(
        [unit("f", pos=(10.0, 20.0), power=PowerId.P03)],
        [enemy("e1", pos=(10.0, 20.0))],
    )
    new, _ = run(state, power("f", "e1"))
    assert find_enemy(new, "e1").position == pytest.approx((10.0, 12.0))


@pytest.mark.parametrize(("dx", "ok"), [(9.4, True), (9.6, False)])
def test_p03_melee_tolerance(dx: float, ok: bool) -> None:
    state = cd_state(
        [unit("f", pos=(10.0, 10.0), power=PowerId.P03)],
        [enemy("e1", pos=(10.0 + dx, 10.0))],
    )
    _, events = run(state, power("f", "e1"))
    assert types(events)[0] is (EventType.POWER if ok else EventType.DODGE)


def test_p04_stuns_so_enemy_skips_attack_then_clears() -> None:
    state = cd_state(
        [
            unit("r", UnitClass.REACH, (10.0, 10.0), power=PowerId.P04),
            unit("t", pos=(10.0, 14.0)),
        ],
        [enemy("e1", pos=(14.0, 10.0), target="t")],
    )
    new, events = run(state, power("r", "e1"))
    assert types(events) == [EventType.POWER]
    assert not find_enemy(new, "e1").is_stunned
    assert find_unit(new, "t").hp == 6
    _, events_next = run(new)
    assert types(events_next) == [EventType.ATTACK]


@pytest.mark.parametrize(("dx", "ok"), [(13.4, True), (13.6, False)])
def test_p04_range_tolerance(dx: float, ok: bool) -> None:
    state = cd_state(
        [unit("r", UnitClass.REACH, (10.0, 10.0), power=PowerId.P04)],
        [enemy("e1", pos=(10.0 + dx, 10.0))],
    )
    _, events = run(state, power("r", "e1"))
    assert types(events) == [EventType.POWER if ok else EventType.DODGE]


def test_p04_cooldown_two_turns() -> None:
    state = cd_state(
        [unit("r", UnitClass.REACH, (10.0, 10.0), power=PowerId.P04)],
        [enemy("e1", pos=(14.0, 10.0))],
    )
    state, _ = run(state, power("r", "e1"))
    assert find_unit(state, "r").cooldown == 2
    state, _ = run(state)
    assert find_unit(state, "r").cooldown == 1
    assert intent_error(state, power("r", "e1")) == "cmd.unknown"
    state, _ = run(state)
    assert find_unit(state, "r").cooldown == 0
    assert intent_error(state, power("r", "e1")) is None


def test_p05_hits_every_enemy_within_six_cm() -> None:
    state = cd_state(
        [unit("f", pos=(10.0, 10.0), power=PowerId.P05, owner="p1")],
        [
            enemy("near", pos=(15.0, 10.0)),
            enemy("side", pos=(10.0, 17.0)),
            enemy("far", pos=(30.0, 10.0)),
        ],
    )
    new, events = run(state, power("f"))
    assert find_enemy(new, "near").hp == 2
    assert find_enemy(new, "side").hp == 2
    assert find_enemy(new, "far").hp == 3
    assert [e.dst for e in of_type(events, EventType.ATTACK)] == ["near", "side"]
    assert find_unit(new, "f").cooldown == 1
    assert new.damage_by_owner == (("p1", 2),)


@pytest.mark.parametrize(("dx", "hit"), [(10.4, True), (10.6, False)])
def test_p05_range_tolerance(dx: float, hit: bool) -> None:
    state = cd_state(
        [unit("f", pos=(10.0, 10.0), power=PowerId.P05)],
        [enemy("e1", pos=(10.0 + dx, 10.0))],
    )
    new, _ = run(state, power("f"))
    assert (find_enemy(new, "e1").hp == 2) is hit


def test_p05_can_kill_and_counts() -> None:
    state = cd_state(
        [unit("f", pos=(10.0, 10.0), power=PowerId.P05)],
        [enemy("e1", pos=(14.0, 10.0), hp=1)],
    )
    new, events = run(state, power("f"))
    assert EventType.DEFEAT_ENEMY in types(events)
    assert new.enemies_defeated == 1


def test_p06_kubo_shield_three() -> None:
    state = board(
        [kubo((40.0, 30.0)), unit("c", UnitClass.CHARM, (5.0, 5.0), power=PowerId.P06)],
        [enemy("k", EnemyType.KAPRE, pos=(40.0, 22.0), target=KUBO_ID)],
    )
    new, events = run(state, power("c", KUBO_ID))
    assert find_unit(new, KUBO_ID).hp == 10
    assert EventType.KUBO_HIT not in types(events)
    assert events[1] == Event(EventType.SHIELD, "c", KUBO_ID, 3)
    assert find_unit(new, "c").cooldown == 2
    new2, _ = run(state, power("c"))
    assert find_unit(new2, KUBO_ID).hp == 10


def test_p06_leftover_damage_hits_kubo() -> None:
    state = board(
        [kubo((40.0, 30.0), shield=1), unit("c", UnitClass.CHARM, (5.0, 5.0))],
        [enemy("k", EnemyType.KAPRE, pos=(40.0, 22.0), target=KUBO_ID)],
    )
    new, events = run(state)
    assert find_unit(new, KUBO_ID).hp == 8
    assert of_type(events, EventType.KUBO_HIT)[0].dmg == 2


def test_p07_is_passive_and_not_usable() -> None:
    state = board(
        [kubo(), unit("c", UnitClass.CHARM, power=PowerId.P07)], [enemy("e1")]
    )
    assert intent_error(state, power("c", None)) == "cmd.unknown"
    new, events = run(state, power("c", None))
    assert events == ()
    assert find_unit(new, "c").cooldown == 0


def test_p08_valid_but_no_effect() -> None:
    state = cd_state(
        [unit("c", UnitClass.CHARM, (5.0, 5.0), power=PowerId.P08)],
        [enemy("e1", pos=(40.0, 20.0))],
    )
    new, events = run(state, power("c"))
    assert events == (Event(EventType.POWER, "c", None),)
    assert find_unit(new, "c").cooldown == 1
    assert new.enemies == state.enemies


def test_p09_hits_target_and_enemy_behind() -> None:
    state = cd_state(
        [unit("r", UnitClass.REACH, (10.0, 10.0), power=PowerId.P09, owner="p1")],
        [
            enemy("front", pos=(16.0, 10.0)),
            enemy("closer", pos=(13.0, 13.0)),
            enemy("behind", pos=(20.0, 10.0)),
            enemy("distant", pos=(40.0, 10.0)),
        ],
    )
    new, events = run(state, power("r", "front"))
    assert [e.dst for e in of_type(events, EventType.ATTACK)] == ["front", "behind"]
    assert find_enemy(new, "front").hp == 1
    assert find_enemy(new, "behind").hp == 1
    assert find_enemy(new, "closer").hp == 3
    assert find_enemy(new, "distant").hp == 3
    assert find_unit(new, "r").cooldown == 1
    assert new.damage_by_owner == (("p1", 4),)


def test_p09_single_target_when_nothing_behind() -> None:
    state = cd_state(
        [unit("r", UnitClass.REACH, (10.0, 10.0), power=PowerId.P09)],
        [enemy("front", pos=(16.0, 10.0)), enemy("side", pos=(16.0, 30.0))],
    )
    new, events = run(state, power("r", "front"))
    assert len(of_type(events, EventType.ATTACK)) == 1
    assert find_enemy(new, "side").hp == 3


def test_p09_second_target_is_nearest_to_first() -> None:
    state = cd_state(
        [unit("r", UnitClass.REACH, (10.0, 10.0), power=PowerId.P09)],
        [
            enemy("front", pos=(16.0, 10.0)),
            enemy("far_one", pos=(22.0, 10.0)),
            enemy("near_one", pos=(19.0, 10.0)),
        ],
    )
    _, events = run(state, power("r", "front"))
    assert [e.dst for e in of_type(events, EventType.ATTACK)] == ["front", "near_one"]


@pytest.mark.parametrize(("dx", "ok"), [(13.4, True), (13.6, False)])
def test_p09_range_tolerance(dx: float, ok: bool) -> None:
    state = cd_state(
        [unit("r", UnitClass.REACH, (10.0, 10.0), power=PowerId.P09)],
        [enemy("front", pos=(10.0 + dx, 10.0))],
    )
    _, events = run(state, power("r", "front"))
    assert types(events)[0] is (EventType.POWER if ok else EventType.DODGE)


def test_p10_buffs_allies_not_self_before_attacks() -> None:
    state = cd_state(
        [
            unit("s", UnitClass.RANGED, (10.0, 10.0), power=PowerId.P10),
            unit("a", pos=(15.0, 10.0)),
            unit("far", pos=(40.0, 10.0)),
        ],
        [enemy("e1", EnemyType.KAPRE, pos=(19.0, 10.0)), enemy("e2", pos=(44.0, 10.0))],
    )
    new, events = run(state, atk("a", "e1"), atk("far", "e2"), power("s"))
    assert events[0].type is EventType.POWER
    assert find_enemy(new, "e1").hp == 5
    assert find_enemy(new, "e2").hp == 1
    assert find_unit(new, "s").atk_bonus == 0
    assert find_unit(new, "a").atk_bonus == 1
    assert find_unit(new, "far").atk_bonus == 0
    assert find_unit(new, "s").cooldown == 2


@pytest.mark.parametrize(("dx", "ok"), [(13.9, True), (14.1, False)])
def test_p10_range_tolerance(dx: float, ok: bool) -> None:
    state = cd_state(
        [
            unit("s", UnitClass.RANGED, (10.0, 10.0), power=PowerId.P10),
            unit("a", pos=(10.0 + dx, 10.0)),
        ],
        [],
    )
    new, _ = run(state, power("s"))
    assert find_unit(new, "a").atk_bonus == (1 if ok else 0)


def test_p10_skips_down_allies_and_bonus_clears_next_turn() -> None:
    state = cd_state(
        [
            unit("s", UnitClass.RANGED, (10.0, 10.0), power=PowerId.P10),
            unit("dead", pos=(14.0, 10.0), hp=0),
            unit("a", pos=(10.0, 14.0)),
        ],
        [],
    )
    new, _ = run(state, power("s"))
    assert find_unit(new, "dead").atk_bonus == 0
    assert find_unit(new, "a").atk_bonus == 1
    fresh, _ = begin_turn(new)
    assert find_unit(fresh, "a").atk_bonus == 0


def test_p11_plus_two_against_duwende_only() -> None:
    state = cd_state(
        [
            unit("s", UnitClass.SCOUT, (10.0, 10.0), power=PowerId.P11),
            unit("f", pos=(10.0, 20.0), power=PowerId.P11),
        ],
        [
            enemy("d", EnemyType.DUWENDE, pos=(14.0, 10.0), hp=6, hp_max=6),
            enemy("a", pos=(14.0, 20.0)),
        ],
    )
    new, events = run(state, power("s", "d"), power("f", "a"))
    assert find_enemy(new, "d").hp == 3
    assert find_enemy(new, "a").hp == 1
    assert [e.dmg for e in of_type(events, EventType.ATTACK)] == [3, 2]
    assert find_unit(new, "s").cooldown == 0


@pytest.mark.parametrize(("dx", "ok"), [(9.4, True), (9.6, False)])
def test_p11_melee_tolerance(dx: float, ok: bool) -> None:
    state = cd_state(
        [unit("f", pos=(10.0, 10.0), power=PowerId.P11)],
        [enemy("d", EnemyType.DUWENDE, pos=(10.0 + dx, 10.0))],
    )
    _, events = run(state, power("f", "d"))
    assert types(events)[0] is (EventType.POWER if ok else EventType.DODGE)


def test_p12_three_damage_to_lower_half() -> None:
    state = cd_state(
        [unit("r", UnitClass.RANGED, (10.0, 10.0), power=PowerId.P12, owner="p1")],
        [
            enemy("low", EnemyType.MANANANGGAL, pos=(20.0, 10.0), part=Part.LOWER),
            enemy("up", EnemyType.MANANANGGAL, pos=(25.0, 10.0), part=Part.UPPER),
        ],
    )
    new, events = run(state, power("r", "low"))
    assert types(events) == [
        EventType.POWER,
        EventType.ATTACK,
        EventType.DEFEAT_ENEMY,
    ]
    assert events[1].dmg == 3
    assert new.enemies == ()
    assert find_unit(new, "r").cooldown == 2
    assert new.damage_by_owner == (("p1", 3),)


def test_p12_charm_falls_back_to_melee_reach() -> None:
    state = cd_state(
        [unit("c", UnitClass.CHARM, (10.0, 10.0), power=PowerId.P12)],
        [enemy("low", EnemyType.MANANANGGAL, pos=(14.0, 10.0), part=Part.LOWER)],
    )
    _, events = run(state, power("c", "low"))
    assert EventType.POWER in types(events)
    far = replace(state, enemies=(replace(state.enemies[0], position=(30.0, 10.0)),))
    _, events = run(far, power("c", "low"))
    assert types(events) == [EventType.DODGE]


@pytest.mark.parametrize(("dx", "ok"), [(19.4, True), (19.6, False)])
def test_p12_range_tolerance(dx: float, ok: bool) -> None:
    state = cd_state(
        [unit("r", UnitClass.RANGED, (10.0, 10.0), power=PowerId.P12)],
        [enemy("low", EnemyType.MANANANGGAL, pos=(10.0 + dx, 10.0), part=Part.LOWER)],
    )
    _, events = run(state, power("r", "low"))
    assert types(events)[0] is (EventType.POWER if ok else EventType.DODGE)


def test_failed_power_does_not_start_cooldown() -> None:
    state = cd_state(
        [unit("f", pos=(10.0, 10.0), power=PowerId.P03)],
        [enemy("e1", pos=(40.0, 10.0))],
    )
    new, _ = run(state, power("f", "e1"))
    assert find_unit(new, "f").cooldown == 0


def test_enemy_attacks_telegraphed_target_in_range() -> None:
    state = cd_state(
        [unit("a", pos=(10.0, 10.0)), unit("b", pos=(40.0, 30.0))],
        [enemy("e1", pos=(14.0, 10.0), target="a")],
    )
    new, events = run(state)
    assert events == (Event(EventType.ATTACK, "e1", "a", 2),)
    assert find_unit(new, "a").hp == 4


def test_enemy_out_of_range_dodges_with_enemy_as_src() -> None:
    state = cd_state(
        [unit("a", pos=(10.0, 10.0))], [enemy("e1", pos=(30.0, 10.0), target="a")]
    )
    new, events = run(state)
    assert events == (Event(EventType.DODGE, "e1", "a"),)
    assert find_unit(new, "a").hp == 6


@pytest.mark.parametrize(("dx", "hit"), [(9.4, True), (9.6, False)])
def test_enemy_range_remeasured_with_tolerance(dx: float, hit: bool) -> None:
    state = cd_state(
        [unit("a", pos=(10.0, 10.0))],
        [enemy("e1", pos=(10.0 + dx, 10.0), target="a")],
    )
    _, events = run(state)
    assert types(events) == [EventType.ATTACK if hit else EventType.DODGE]


def test_enemy_skips_down_target_and_missing_target() -> None:
    state = cd_state(
        [unit("a", pos=(10.0, 10.0), hp=0), unit("z", pos=(40.0, 5.0))],
        [
            enemy("e1", pos=(14.0, 10.0), target="a"),
            enemy("e2", pos=(14.0, 10.0), target=None),
            enemy("e3", pos=(14.0, 10.0), target="ghost"),
        ],
    )
    _, events = run(state)
    assert events == ()


def test_enemies_act_in_spawn_order_and_target_can_go_down() -> None:
    state = cd_state(
        [unit("a", pos=(10.0, 10.0), hp=3), unit("z", pos=(40.0, 5.0))],
        [
            enemy("e1", pos=(14.0, 10.0), target="a"),
            enemy("e2", pos=(10.0, 14.0), target="a"),
        ],
    )
    new, events = run(state)
    assert types(events) == [EventType.ATTACK, EventType.ATTACK, EventType.DOWN]
    assert [e.dmg for e in events[:2]] == [2, 1]
    assert find_unit(new, "a").is_down
    assert events[2] == Event(EventType.DOWN, "e2", "a")


def test_down_unit_is_not_hit_again() -> None:
    state = cd_state(
        [unit("a", pos=(10.0, 10.0), hp=1), unit("z", pos=(40.0, 5.0))],
        [
            enemy("e1", pos=(14.0, 10.0), target="a"),
            enemy("e2", pos=(10.0, 14.0), target="a"),
        ],
    )
    _, events = run(state)
    assert types(events) == [EventType.ATTACK, EventType.DOWN]


def test_kubo_hit_event_follows_attack() -> None:
    state = board(
        [kubo((40.0, 30.0)), unit("a", pos=(5.0, 5.0))],
        [enemy("k", EnemyType.KAPRE, pos=(40.0, 22.0), target=KUBO_ID)],
    )
    new, events = run(state)
    assert types(events) == [EventType.ATTACK, EventType.KUBO_HIT]
    assert find_unit(new, KUBO_ID).hp == 7
    assert events[1].dmg == 3


def test_duwende_steals_instead_of_damaging() -> None:
    state = cd_state(
        [unit("a", pos=(10.0, 10.0))],
        [enemy("d", EnemyType.DUWENDE, pos=(14.0, 10.0), target="a")],
    )
    new, events = run(state)
    assert types(events) == [EventType.STEAL]
    assert find_unit(new, "a").hp == 6
    assert find_unit(new, "a").stolen_by == "d"


def test_mahirap_enemy_hits_harder() -> None:
    state = board(
        [kubo((55.0, 35.0)), unit("a", pos=(10.0, 10.0))],
        [enemy("e1", pos=(14.0, 10.0), target="a", difficulty=Difficulty.MAHIRAP)],
        difficulty=Difficulty.MAHIRAP,
    )
    _, events = run(state)
    assert events[0].dmg == 3


def test_lower_half_never_attacks() -> None:
    state = cd_state(
        [unit("a", pos=(14.0, 10.0))],
        [enemy("low", EnemyType.MANANANGGAL, pos=(14.0, 10.0), part=Part.LOWER)],
    )
    _, events = run(state)
    assert events == ()


def test_lower_death_removes_upper_but_upper_still_attacks_that_turn() -> None:
    state = cd_state(
        [
            unit("r", UnitClass.RANGED, (10.0, 10.0), power=PowerId.P12),
            unit("a", pos=(30.0, 30.0)),
        ],
        [
            enemy("low", EnemyType.MANANANGGAL, pos=(16.0, 10.0), part=Part.LOWER),
            enemy(
                "up",
                EnemyType.MANANANGGAL,
                pos=(30.0, 34.0),
                part=Part.UPPER,
                target="a",
            ),
        ],
    )
    new, events = run(state, power("r", "low"))
    assert new.enemies == ()
    assert [e.type for e in events if e.src == "up"] == [EventType.ATTACK]
    assert new.enemies_defeated == 1


def reform_state() -> BoardState:
    return cd_state(
        [unit("a", pos=(10.0, 10.0))],
        [
            enemy("low", EnemyType.MANANANGGAL, pos=(40.0, 10.0), part=Part.LOWER),
            enemy(
                "up",
                EnemyType.MANANANGGAL,
                pos=(14.0, 10.0),
                part=Part.UPPER,
                hp=1,
            ),
        ],
    )


def test_upper_death_schedules_reform_while_lower_alive() -> None:
    new, events = run(reform_state(), atk("a", "up"))
    assert EventType.DEFEAT_ENEMY in types(events)
    up = find_enemy(new, "up")
    assert up.hp == 0 and up.reform_in == 2
    assert not up.is_alive
    assert new.enemies_defeated == 1
    assert intent_error(new, atk("a", "up")) == "cmd.unknown"


def test_pending_reform_survives_following_resolution() -> None:
    state, _ = run(reform_state(), atk("a", "up"))
    state, _ = run(state)
    assert find_enemy(state, "up").reform_in == 2


def test_reform_after_two_turns_beside_lower() -> None:
    state, _ = run(reform_state(), atk("a", "up"))
    state, events = begin_turn(state)
    assert find_enemy(state, "up").reform_in == 1
    assert EventType.REFORM not in types(events)
    state, _ = run(state)
    state, events = begin_turn(state)
    reform = of_type(events, EventType.REFORM)
    assert len(reform) == 1
    assert reform[0].src == "up" and reform[0].dst == "low"
    up = find_enemy(state, "up")
    assert up.hp == up.hp_max == 4
    assert up.reform_in is None
    assert reform[0].pos == (45.0, 10.0)
    assert EventType.INTENT in types(events)


def test_pending_reform_dropped_when_lower_dies() -> None:
    state = cd_state(
        [unit("r", UnitClass.RANGED, (10.0, 10.0), power=PowerId.P12)],
        [
            enemy("low", EnemyType.MANANANGGAL, pos=(16.0, 10.0), part=Part.LOWER),
            enemy(
                "up",
                EnemyType.MANANANGGAL,
                pos=(30.0, 30.0),
                part=Part.UPPER,
                hp=0,
                reform_in=1,
            ),
        ],
    )
    new, _ = run(state, power("r", "low"))
    assert new.enemies == ()


def test_stun_flag_clears_after_enemy_phase_even_if_unspent() -> None:
    state = cd_state([unit("a")], [enemy("e1", pos=(50.0, 5.0), is_stunned=True)])
    new, _ = run(state)
    assert not find_enemy(new, "e1").is_stunned


def test_cooldowns_tick_for_unused_powers() -> None:
    state = cd_state([unit("r", UnitClass.RANGED, power=PowerId.P10, cooldown=2)], [])
    state, _ = run(state)
    assert find_unit(state, "r").cooldown == 1
    state, _ = run(state)
    state, _ = run(state)
    assert find_unit(state, "r").cooldown == 0


def test_check_outcome_continue_win_lose() -> None:
    live = board([kubo(), unit("a")], turn=3)
    assert check_outcome(live) is Outcome.CONTINUE
    assert check_outcome(replace(live, turn=7)) is Outcome.CONTINUE
    assert check_outcome(replace(live, turn=8)) is Outcome.WIN
    assert check_outcome(replace(live, turn=9)) is Outcome.WIN


def test_check_outcome_lose_kubo_down() -> None:
    state = board([kubo(hp=0), unit("a")], turn=8)
    assert check_outcome(state) is Outcome.LOSE


def test_check_outcome_lose_all_others_down() -> None:
    state = board([kubo(), unit("a", hp=0), unit("b", hp=0)], turn=2)
    assert check_outcome(state) is Outcome.LOSE
    some = board([kubo(), unit("a", hp=0), unit("b")], turn=2)
    assert check_outcome(some) is Outcome.CONTINUE


def test_check_outcome_kubo_only_is_not_a_loss() -> None:
    assert check_outcome(board([kubo()], turn=1)) is Outcome.CONTINUE


def test_resolve_emits_win_event_on_turn_eight() -> None:
    state = board([kubo(), unit("a")], turn=8)
    _, events = run(state)
    assert types(events)[-1] is EventType.WIN


def test_resolve_emits_lose_when_kubo_falls() -> None:
    state = board(
        [kubo((40.0, 30.0), hp=2), unit("a", pos=(5.0, 5.0))],
        [enemy("k", EnemyType.KAPRE, pos=(40.0, 22.0), target=KUBO_ID)],
        turn=8,
    )
    new, events = run(state)
    assert types(events) == [
        EventType.ATTACK,
        EventType.KUBO_HIT,
        EventType.DOWN,
        EventType.LOSE,
    ]
    assert check_outcome(new) is Outcome.LOSE


def test_resolve_emits_lose_when_everyone_else_down() -> None:
    state = board(
        [kubo(), unit("a", pos=(10.0, 10.0), hp=1)],
        [enemy("e1", pos=(14.0, 10.0), target="a")],
    )
    _, events = run(state)
    assert types(events)[-1] is EventType.LOSE


def test_no_outcome_event_mid_night() -> None:
    state = board([kubo(), unit("a")], turn=3)
    _, events = run(state)
    assert events == ()


def test_score_formula() -> None:
    state = board(
        [kubo(hp=6), *[unit(f"u{i}") for i in range(4)], unit("d", hp=0)],
        enemies_defeated=9,
    )
    assert score(state) == 4 * 10 + 6 * 5 + 9 * 3
    assert score(board([kubo(hp=0)])) == 0
    assert score(board([unit("a")])) == 10


def test_bayani_single_tied_and_empty() -> None:
    assert bayani(board([kubo()])) == ()
    assert bayani(board([kubo()], damage_by_owner=(("p1", 0),))) == ()
    assert bayani(board([kubo()], damage_by_owner=(("p1", 3), ("p2", 5)))) == ("p2",)
    tied = board([kubo()], damage_by_owner=(("p1", 5), ("p2", 5), ("p3", 2)))
    assert bayani(tied) == ("p1", "p2")


def test_begin_turn_resets_phase_state() -> None:
    state = board(
        [
            kubo(shield=3),
            unit("a", pos=(10.0, 10.0), shield=2, atk_bonus=1, start=(0.0, 0.0)),
        ],
        turn=0,
    )
    new, _ = begin_turn(state)
    a = find_unit(new, "a")
    assert new.turn == 1
    assert a.shield == 0 and a.atk_bonus == 0
    assert a.start == (10.0, 10.0)
    assert find_unit(new, KUBO_ID).shield == 0


def test_begin_turn_spawns_telegraphs_and_moves() -> None:
    state = board([kubo(), unit("a", pos=(30.0, 25.0))], turn=0)
    new, events = begin_turn(state)
    assert types(events) == [EventType.SPAWN, EventType.INTENT]
    spawn, intent = events
    assert spawn.src == "e_aswang_1"
    assert spawn.edge is Edge.NORTH
    assert spawn.pos == (30.0, 2.5)
    assert intent.dst == "a"
    assert intent.dmg == 2
    e = find_enemy(new, "e_aswang_1")
    assert e.target_id == "a" and e.intent_dmg == 2
    assert e.position[1] == pytest.approx(16.5)
    assert intent.pos == e.position
    assert e.spawn_turn == 1
    assert new.enemy_counter == (("aswang", 1),)


def test_begin_turn_enemy_stops_at_range_of_target() -> None:
    state = board([kubo(), unit("a", pos=(30.0, 25.0))], turn=0)
    new, _ = begin_turn(state)
    e = find_enemy(new, "e_aswang_1")
    gap = hull_point_distance(find_unit(new, "a").hull, e.position)
    assert gap == pytest.approx(5.0, abs=1e-6)


def test_begin_turn_counter_ids_are_stable_across_turns() -> None:
    state = board([kubo(), unit("a", pos=(30.0, 10.0))], turn=0)
    state, _ = begin_turn(state)
    state, _ = begin_turn(state)
    assert [e.id for e in state.enemies] == ["e_aswang_1", "e_aswang_2", "e_duwende_1"]


def test_begin_turn_tabi_tabi_skips_duwende() -> None:
    state = board(
        [kubo(), unit("a", pos=(30.0, 10.0))], turn=1, flags=frozenset({"tabi_tabi"})
    )
    new, events = begin_turn(state)
    assert [e.id for e in new.enemies] == ["e_aswang_1"]
    assert len(of_type(events, EventType.SPAWN)) == 1


def test_begin_turn_duwende_telegraphs_one() -> None:
    state = board([kubo(), unit("c", UnitClass.CHARM, (10.0, 20.0))], turn=1)
    new, events = begin_turn(state)
    duwende = find_enemy(new, "e_duwende_1")
    assert duwende.intent_dmg == 0 and duwende.target_id == "c"
    intents = [e for e in of_type(events, EventType.INTENT) if e.src == "e_duwende_1"]
    assert intents[0].dmg == 0


def test_begin_turn_manananggal_split_and_lower_has_no_intent() -> None:
    state = board([kubo((10.0, 20.0)), unit("a", pos=(12.0, 20.0))], turn=5)
    new, events = begin_turn(state)
    assert types(events)[:3] == [EventType.SPAWN, EventType.SPAWN, EventType.SPLIT]
    split = of_type(events, EventType.SPLIT)[0]
    lower = find_enemy(new, split.dst or "")
    upper = find_enemy(new, split.src or "")
    assert lower.part is Part.LOWER and upper.part is Part.UPPER
    assert lower.target_id is None and lower.intent_dmg is None
    assert lower.position == (57.5, 20.0)
    assert upper.target_id == KUBO_ID
    assert [e.src for e in of_type(events, EventType.INTENT)] == [upper.id]


def test_begin_turn_aura_keeps_enemy_out() -> None:
    charm = unit("c", UnitClass.CHARM, (30.0, 16.0), power=PowerId.P07)
    state = board([kubo((50.0, 35.0)), charm], turn=0)
    new, _ = begin_turn(state)
    e = find_enemy(new, "e_aswang_1")
    assert e.target_id == "c"
    assert e.position[1] == pytest.approx(4.5, abs=1e-6)
    assert hull_point_distance(charm.hull, e.position) >= 8.0


def test_begin_turn_without_kubo_still_spawns() -> None:
    state = board([unit("a")], turn=2)
    new, _ = begin_turn(state)
    assert len(new.enemies) == 2


def test_begin_turn_reform_without_lower_drops_pending() -> None:
    state = board(
        [kubo(), unit("a")],
        [
            enemy(
                "up",
                EnemyType.MANANANGGAL,
                part=Part.UPPER,
                hp=0,
                reform_in=1,
            )
        ],
        turn=10,
    )
    new, events = begin_turn(state)
    assert all(e.id != "up" for e in new.enemies)
    assert EventType.REFORM not in types(events)


def test_begin_turn_leaves_pending_upper_unmoved() -> None:
    state = board(
        [kubo(), unit("a")],
        [
            enemy("low", EnemyType.MANANANGGAL, part=Part.LOWER),
            enemy("up", EnemyType.MANANANGGAL, part=Part.UPPER, hp=0, reform_in=2),
        ],
        turn=10,
    )
    new, _ = begin_turn(state)
    assert find_enemy(new, "up").reform_in == 1
    assert find_enemy(new, "up").position == (30.0, 10.0)


def random_state(seed: int) -> tuple[BoardState, list[Intent]]:
    rng = random.Random(seed)
    classes = [
        UnitClass.CHARM,
        UnitClass.HEALER,
        UnitClass.FIGHTER,
        UnitClass.REACH,
        UnitClass.RANGED,
        UnitClass.SCOUT,
        UnitClass.WALL,
    ]
    units = [kubo((rng.uniform(10, 50), rng.uniform(10, 30)))]
    for i in range(rng.randint(2, 11)):
        cls = rng.choice(classes)
        template = CLASS_TEMPLATES[cls]
        units.append(
            unit(
                f"u_{i + 2}",
                cls,
                (rng.uniform(2, 58), rng.uniform(2, 38)),
                power=rng.choice(template.powers),
                owner=rng.choice(["p1", "p2", None]),
                hp=rng.randint(0, template.hp),
                cooldown=rng.randint(0, 2),
            )
        )
    enemies = []
    for i in range(rng.randint(0, 8)):
        kind = rng.choice(list(EnemyType))
        part = rng.choice(list(Part)) if kind is EnemyType.MANANANGGAL else None
        goal = rng.choice(units)
        spot = (rng.uniform(2, 58), rng.uniform(2, 38))
        if rng.random() < 0.5:
            spot = (goal.position[0] + rng.uniform(-4, 4), goal.position[1] + 3.0)
        enemies.append(enemy(f"e{i}", kind, spot, part, target=goal.id))
    if enemies and rng.random() < 0.4:
        units = [
            replace(u, out_turns=1) if i == 1 and not u.is_kubo else u
            for i, u in enumerate(units)
        ]
    if len(enemies) > 1 and rng.random() < 0.5:
        enemies[0] = replace(enemies[0], type=EnemyType.DUWENDE, atk=0, carrying="u_2")
        units = [replace(u, stolen_by="e0") if u.id == "u_2" else u for u in units]
    if len(enemies) > 2:
        enemies[1] = replace(enemies[1], type=EnemyType.TIKBALANG, atk=1)
        enemies[2] = replace(enemies[2], type=EnemyType.DUWENDE, atk=0)
    state = board(
        units,
        enemies,
        turn=rng.randint(1, 8),
        difficulty=rng.choice(list(Difficulty)),
        players=rng.randint(1, 4),
        flags=frozenset({"tabi_tabi"}) if rng.random() < 0.3 else frozenset(),
    )
    intents: list[Intent] = []
    for u in units:
        if enemies and rng.random() < 0.8:
            action = rng.choice(list(Action))
            target: str | None
            if action is Action.HEAL:
                target = rng.choice(units).id
            else:
                target = rng.choice([*(e.id for e in enemies), None])
            intents.append(Intent(u.id, action, target))
    rng.shuffle(intents)
    return state, intents


@pytest.mark.parametrize("seed", range(50))
def test_determinism_e7(seed: int) -> None:
    state, intents = random_state(seed)
    first = resolve_turn(state, intents)
    second = resolve_turn(state, intents)
    assert first == second
    assert begin_turn(state) == begin_turn(state)
    chained_a = resolve_turn(begin_turn(first[0])[0], intents)
    chained_b = resolve_turn(begin_turn(second[0])[0], intents)
    assert chained_a == chained_b


def test_resolve_does_not_mutate_input() -> None:
    state, intents = random_state(7)
    before = replace(state)
    resolve_turn(state, intents)
    assert state == before


def test_perf_resolve_under_50ms_for_12_units_8_enemies() -> None:
    units = [kubo((30.0, 20.0))]
    classes = [
        UnitClass.HEALER,
        UnitClass.FIGHTER,
        UnitClass.REACH,
        UnitClass.RANGED,
        UnitClass.SCOUT,
        UnitClass.WALL,
        UnitClass.CHARM,
        UnitClass.FIGHTER,
        UnitClass.REACH,
        UnitClass.RANGED,
        UnitClass.SCOUT,
    ]
    for i, cls in enumerate(classes):
        units.append(
            unit(
                f"u_{i + 2}",
                cls,
                (8.0 + 4.0 * i, 12.0 + 2.0 * (i % 4)),
                power=CLASS_TEMPLATES[cls].powers[0],
            )
        )
    enemies = [
        enemy(f"e{i}", EnemyType.ASWANG, (10.0 + 5.0 * i, 14.0), target=f"u_{i + 2}")
        for i in range(8)
    ]
    state = board(units, enemies)
    intents = [
        Intent(u.id, Action.ATTACK, enemies[i % 8].id)
        for i, u in enumerate(units[1:])
        if u.atk > 0
    ]
    samples: list[float] = []
    for _ in range(40):
        start = time.perf_counter()
        resolve_turn(state, intents)
        samples.append((time.perf_counter() - start) * 1000.0)
    median = statistics.median(samples)
    print(f"resolve_turn median {median:.3f} ms")
    assert median < 50.0

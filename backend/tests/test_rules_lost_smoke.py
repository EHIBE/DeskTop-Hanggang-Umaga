import copy
import random
from dataclasses import replace
from typing import Any

import pytest

from rules.enemies import EnemyType
from rules.geometry import hull_point_distance, square_hull
from rules.lost import centroid_inside, update_lost
from rules.resolve import (
    SMOKE_CLEAR_RADIUS_CM,
    Action,
    BoardState,
    EnemyState,
    EventType,
    Intent,
    Smoke,
    UnitState,
    begin_turn,
    intent_error,
    resolve_turn,
    score,
    with_positions,
)
from rules.units import CLASS_TEMPLATES, Difficulty, PowerId, UnitClass
from tests.rules_gen import (
    KUBO_ID,
    Gen,
    jitter,
    rand_board,
    rand_intents,
)

W = 60.0
H = 40.0
HALF = 1.5


def make_unit(
    uid: str,
    unit_class: UnitClass,
    pos: tuple[float, float],
    power: PowerId | None = None,
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
    )
    return replace(base, **over)


def make_enemy(
    eid: str, pos: tuple[float, float], kind: EnemyType = EnemyType.ASWANG
) -> EnemyState:
    return EnemyState(
        id=eid,
        type=kind,
        part=None,
        hp=8,
        hp_max=8,
        atk=0,
        move_cm=0.0,
        range_cm=0.0,
        flies=False,
        position=pos,
        spawn_turn=1,
    )


def make_board(
    units: list[UnitState],
    enemies: list[EnemyState],
    smoke: tuple[Smoke, ...] = (),
) -> BoardState:
    return BoardState(
        turn=2,
        difficulty=Difficulty.NORMAL,
        players=2,
        play_w_cm=W,
        play_h_cm=H,
        units=tuple(units),
        enemies=tuple(enemies),
        smoke=smoke,
    )


def is_smoked(unit: UnitState, state: BoardState) -> bool:
    return any(cloud.covers_hull(unit.hull) for cloud in state.smoke)


def in_cloud(enemy: EnemyState, state: BoardState) -> bool:
    return any(cloud.covers_point(enemy.position) for cloud in state.smoke)


SMOKE_GEN = Gen(
    force_smoke=True,
    deny_powers=frozenset({PowerId.P03, PowerId.P08, PowerId.P05, PowerId.P09}),
    allow_hostile_states=False,
)


def test_smoked_unit_never_hits_an_enemy_outside_every_cloud() -> None:
    blocked = 0
    allowed = 0
    for seed in range(300):
        rng = random.Random(seed)
        state = rand_board(rng, SMOKE_GEN)
        intents = rand_intents(rng, state, 0.05)
        _, events = resolve_turn(state, intents)
        units = {u.id: u for u in state.units}
        enemies = {e.id: e for e in state.enemies}
        for event in events:
            if event.type is not EventType.ATTACK or event.src not in units:
                continue
            attacker = units[event.src]
            assert event.dst in enemies
            if is_smoked(attacker, state):
                if in_cloud(enemies[event.dst], state):
                    allowed += 1
                else:
                    pytest.fail(f"seed {seed}: smoked unit hit outside: {event}")
        for intent in intents:
            unit = units.get(intent.unit_id)
            target = enemies.get(intent.target_id or "")
            if (
                unit is not None
                and target is not None
                and is_smoked(unit, state)
                and not in_cloud(target, state)
            ):
                blocked += 1
    assert blocked > 20
    assert allowed > 0


def test_smoked_unit_can_hit_inside_the_cloud_and_unsmoked_unit_is_free() -> None:
    cloud = Smoke("e_kapre_1", (30.0, 20.0))
    smoked = make_unit("u_a", UnitClass.FIGHTER, (30.0, 20.0))
    far = make_unit("u_b", UnitClass.FIGHTER, (5.0, 5.0))
    inside_enemy = make_enemy("e_aswang_1", (33.0, 20.0))
    outside_enemy = make_enemy("e_aswang_2", (6.0, 8.0))
    state = make_board(
        [make_unit(KUBO_ID, UnitClass.KUBO, (50.0, 30.0)), smoked, far],
        [inside_enemy, outside_enemy],
        (cloud,),
    )
    _, events = resolve_turn(
        state,
        [
            Intent("u_a", Action.ATTACK, "e_aswang_1"),
            Intent("u_b", Action.ATTACK, "e_aswang_2"),
        ],
    )
    hits = [(e.src, e.dst) for e in events if e.type is EventType.ATTACK]
    assert ("u_a", "e_aswang_1") in hits
    assert ("u_b", "e_aswang_2") in hits


def test_smoked_unit_cannot_reach_out_of_the_cloud() -> None:
    cloud = Smoke("e_kapre_1", (30.0, 20.0))
    smoked = make_unit("u_a", UnitClass.RANGED, (30.0, 20.0))
    outside = make_enemy("e_aswang_1", (42.0, 20.0))
    state = make_board(
        [make_unit(KUBO_ID, UnitClass.KUBO, (50.0, 30.0)), smoked], [outside], (cloud,)
    )
    _, events = resolve_turn(state, [Intent("u_a", Action.ATTACK, "e_aswang_1")])
    assert not any(e.type is EventType.ATTACK for e in events)
    assert any(e.type is EventType.DODGE for e in events)


def test_smoked_sweep_does_not_hit_outside_the_cloud() -> None:
    cloud = Smoke("e_kapre_1", (30.0, 20.0), radius_cm=2.0)
    smoked = make_unit("u_a", UnitClass.FIGHTER, (30.0, 20.0), PowerId.P05)
    outside = make_enemy("e_aswang_1", (36.0, 20.0))
    state = make_board(
        [make_unit(KUBO_ID, UnitClass.KUBO, (50.0, 30.0)), smoked], [outside], (cloud,)
    )
    assert is_smoked(smoked, state)
    assert not in_cloud(outside, state)
    _, events = resolve_turn(state, [Intent("u_a", Action.POWER, None)])
    assert not any(e.type is EventType.ATTACK and e.dst == "e_aswang_1" for e in events)


def test_smoked_pierce_does_not_hit_second_target_outside_the_cloud() -> None:
    cloud = Smoke("e_kapre_1", (30.0, 20.0), radius_cm=8.0)
    smoked = make_unit("u_a", UnitClass.REACH, (30.0, 20.0), PowerId.P09)
    first = make_enemy("e_aswang_1", (33.0, 20.0))
    behind = make_enemy("e_aswang_2", (39.0, 20.0))
    state = make_board(
        [make_unit(KUBO_ID, UnitClass.KUBO, (50.0, 30.0)), smoked],
        [first, behind],
        (cloud,),
    )
    assert is_smoked(smoked, state)
    assert in_cloud(first, state)
    assert not in_cloud(behind, state)
    _, events = resolve_turn(state, [Intent("u_a", Action.POWER, "e_aswang_1")])
    assert not any(e.type is EventType.ATTACK and e.dst == "e_aswang_2" for e in events)


def _p08_board(distance: float, clouds: int = 1) -> tuple[BoardState, UnitState]:
    center = (30.0, 20.0)
    charm = make_unit(
        "u_light",
        UnitClass.CHARM,
        (center[0] + distance + HALF, center[1]),
        PowerId.P08,
    )
    state = make_board(
        [make_unit(KUBO_ID, UnitClass.KUBO, (5.0, 35.0)), charm],
        [make_enemy("e_aswang_1", (55.0, 5.0))],
        tuple(Smoke(f"e_kapre_{i}", center) for i in range(clouds)),
    )
    return state, charm


def test_p08_clears_clouds_within_twelve_cm_plus_tolerance() -> None:
    rng = random.Random(8)
    for _ in range(60):
        distance = rng.uniform(0.0, SMOKE_CLEAR_RADIUS_CM + 0.99)
        state, charm = _p08_board(distance, clouds=rng.randint(1, 3))
        reach = hull_point_distance(charm.hull, (30.0, 20.0), 0.0)
        assert reach == pytest.approx(distance, abs=1e-6)
        post, events = resolve_turn(state, [Intent("u_light", Action.POWER, None)])
        assert post.smoke == ()
        cleared = [e for e in events if e.type is EventType.SMOKE_CLEARED]
        assert len(cleared) == len(state.smoke)


def test_p08_leaves_clouds_beyond_tolerance() -> None:
    rng = random.Random(9)
    for _ in range(60):
        distance = rng.uniform(SMOKE_CLEAR_RADIUS_CM + 1.2, 40.0)
        state, _ = _p08_board(distance)
        post, events = resolve_turn(state, [Intent("u_light", Action.POWER, None)])
        assert post.smoke == state.smoke
        assert not any(e.type is EventType.SMOKE_CLEARED for e in events)


def test_p08_clears_before_attacks_so_the_unit_can_fire_out() -> None:
    cloud = Smoke("e_kapre_1", (30.0, 20.0))
    caster = make_unit("u_light", UnitClass.CHARM, (30.0, 20.0), PowerId.P08)
    shooter = make_unit("u_gun", UnitClass.RANGED, (28.0, 20.0), PowerId.P10)
    outside = make_enemy("e_aswang_1", (42.0, 20.0))
    state = make_board(
        [make_unit(KUBO_ID, UnitClass.KUBO, (50.0, 30.0)), caster, shooter],
        [outside],
        (cloud,),
    )
    _, blocked = resolve_turn(state, [Intent("u_gun", Action.ATTACK, "e_aswang_1")])
    assert not any(e.type is EventType.ATTACK for e in blocked)
    post, freed = resolve_turn(
        state,
        [
            Intent("u_gun", Action.ATTACK, "e_aswang_1"),
            Intent("u_light", Action.POWER, None),
        ],
    )
    assert post.smoke == ()
    assert any(e.type is EventType.ATTACK and e.src == "u_gun" for e in freed)


def test_p08_on_cooldown_or_absent_does_not_clear() -> None:
    state, charm = _p08_board(2.0)
    for changed in (
        replace(charm, cooldown=1),
        replace(charm, off_desk=True),
        replace(charm, hp=0),
    ):
        board = replace(
            state, units=tuple(changed if u.id == charm.id else u for u in state.units)
        )
        post, _ = resolve_turn(board, [Intent("u_light", Action.POWER, None)])
        assert post.smoke == state.smoke


def test_smoke_is_rebuilt_from_living_kapres_on_the_right_turns() -> None:
    for seed in range(120):
        rng = random.Random(seed)
        state = rand_board(rng, Gen(allow_hostile_states=False))
        post, events = begin_turn(state)
        turn = post.turn
        expected = {
            e.id
            for e in post.enemies
            if e.type is EnemyType.KAPRE
            and e.is_alive
            and turn - e.spawn_turn + 1 in (2, 4)
        }
        assert {c.source_id for c in post.smoke} == expected
        assert sum(1 for e in events if e.type is EventType.SMOKE) == len(expected)


def lost_board(rng: random.Random) -> BoardState:
    return rand_board(rng, Gen(allow_hostile_states=True))


def test_update_lost_flags_exactly_the_units_outside_the_desk() -> None:
    flipped = 0
    for seed in range(200):
        rng = random.Random(seed)
        state = lost_board(rng)
        snapshot = copy.deepcopy(state)
        post, events = update_lost(state)
        assert state == snapshot
        before = {u.id: u for u in state.units}
        for unit in post.units:
            old = before[unit.id]
            watched = (
                not old.is_down
                and old.stolen_by is None
                and not old.is_lost
                and old.out_turns == 0
            )
            if watched:
                inside = centroid_inside(unit, state.play_w_cm, state.play_h_cm)
                assert unit.off_desk is (not inside)
                flipped += old.off_desk != unit.off_desk
            else:
                assert unit == old
        lost_ids = {e.src for e in events if e.type is EventType.LOST}
        found_ids = {e.src for e in events if e.type is EventType.FOUND}
        assert lost_ids.isdisjoint(found_ids)
        again, repeat = update_lost(post)
        assert again == post
        assert repeat == ()
    assert flipped > 50


def test_off_desk_units_are_never_targeted_and_never_act() -> None:
    checked = 0
    for seed in range(200):
        rng = random.Random(seed)
        state, _ = update_lost(lost_board(rng))
        away = {u.id for u in state.units if u.off_desk}
        begun, intents_events = begin_turn(state)
        for enemy in begun.enemies:
            if enemy.is_alive:
                assert enemy.target_id not in away
        for event in intents_events:
            assert event.dst not in away or event.type is not EventType.INTENT
        moved, _ = update_lost(jitter(rng, begun))
        absent = {u.id for u in moved.units if u.off_desk}
        if not absent:
            continue
        checked += len(absent)
        intents = rand_intents(rng, moved, 0.0)
        for intent in intents:
            if intent.unit_id in absent:
                assert intent_error(moved, intent) == "cmd.unknown"
        for unit_id in absent:
            assert intent_error(moved, Intent(unit_id, Action.ATTACK, "x")) == (
                "cmd.unknown"
            )
        _, events = resolve_turn(moved, intents)
        enemy_ids = {e.id for e in moved.enemies}
        for event in events:
            assert event.src not in absent, event
            if event.src in enemy_ids:
                assert event.dst not in absent, event
    assert checked > 20


def test_off_desk_units_return_when_placed_back() -> None:
    returned = 0
    for seed in range(200):
        rng = random.Random(seed)
        state, _ = update_lost(lost_board(rng))
        gone = [
            u
            for u in state.units
            if u.off_desk and not u.is_down and u.out_turns == 0 and not u.is_lost
        ]
        if not gone:
            continue
        spots = {
            u.id: (
                rng.uniform(5.0, state.play_w_cm - 5.0),
                rng.uniform(5.0, state.play_h_cm - 5.0),
            )
            for u in gone
        }
        moved = with_positions(state, spots)
        back, events = update_lost(moved)
        by_id = {u.id: u for u in back.units}
        found = {e.src for e in events if e.type is EventType.FOUND}
        for unit in gone:
            if unit.stolen_by is not None:
                continue
            assert not by_id[unit.id].off_desk
            assert by_id[unit.id].start == spots[unit.id]
            assert unit.id in found
            returned += 1
    assert returned > 20


def test_off_desk_unit_is_not_scored_as_alive() -> None:
    kubo = make_unit(KUBO_ID, UnitClass.KUBO, (30.0, 20.0))
    fighter = make_unit("u_a", UnitClass.FIGHTER, (10.0, 10.0))
    state = make_board([kubo, fighter], [])
    away = replace(state, units=(kubo, replace(fighter, off_desk=True)))
    assert score(state) - score(away) == 10
    assert not away.units[1].can_act
    assert not away.units[1].is_targetable

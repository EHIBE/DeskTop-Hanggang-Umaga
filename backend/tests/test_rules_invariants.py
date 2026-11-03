import copy
import random
from collections import Counter
from dataclasses import replace

import pytest

from rules.enemies import EnemyType, Part, pick_target
from rules.geometry import (
    hull_centroid,
    hull_hull_distance,
    hull_point_distance,
    in_range,
    square_hull,
    translate_hull,
)
from rules.resolve import (
    POWER_COOLDOWN,
    TURNS_PER_NIGHT,
    Action,
    BoardState,
    EventType,
    Intent,
    Outcome,
    bayani,
    begin_turn,
    check_outcome,
    resolve_turn,
    score,
)
from rules.units import (
    ATK_CAP,
    CLASS_TEMPLATES,
    HP_FLOOR,
    CardDraft,
    Difficulty,
    PowerId,
    UnitClass,
    clamp_card,
)
from rules.waves import spawns_for
from tests.rules_gen import (
    MAX_COOLDOWN,
    Gen,
    Step,
    play,
    rand_board,
    rand_intents,
)

SEEDS = range(120)
EPS = 1e-6
ACTING_EVENTS = frozenset(
    {
        EventType.ATTACK,
        EventType.DODGE,
        EventType.HEAL,
        EventType.POWER,
        EventType.SHIELD,
        EventType.PUSH,
        EventType.STEAL,
        EventType.THROWN,
        EventType.KUBO_HIT,
        EventType.DEFEAT_ENEMY,
    }
)


def inside(point: tuple[float, float], w: float, h: float) -> bool:
    return -EPS <= point[0] <= w + EPS and -EPS <= point[1] <= h + EPS


def assert_state_sane(state: BoardState) -> None:
    ids = [u.id for u in state.units]
    assert len(ids) == len(set(ids))
    for unit in state.units:
        assert 0 <= unit.hp <= unit.hp_max, unit
        assert unit.shield >= 0
        assert unit.atk_bonus >= 0
        assert unit.out_turns >= 0
        assert 0 <= unit.cooldown <= MAX_COOLDOWN
    for enemy in state.enemies:
        assert 0 <= enemy.hp <= enemy.hp_max, enemy
    assert all(total >= 0 for _, total in state.damage_by_owner)
    assert state.enemies_defeated >= 0


def all_steps(turns: int = 3) -> list[Step]:
    steps: list[Step] = []
    for seed in SEEDS:
        steps.extend(play(seed, turns))
    return steps


STEPS = all_steps()


def test_generator_covers_the_rule_surface() -> None:
    kinds: Counter[EventType] = Counter()
    for step in STEPS:
        kinds.update(event.type for event in step.events)
    for needed in (
        EventType.ATTACK,
        EventType.DODGE,
        EventType.POWER,
        EventType.HEAL,
        EventType.SHIELD,
        EventType.DOWN,
        EventType.PUSH,
        EventType.DEFEAT_ENEMY,
    ):
        assert kinds[needed] > 0, needed
    powers = {u.power_id for step in STEPS for u in step.pre.units}
    assert powers >= {p for p in PowerId if p is not PowerId.NONE}
    types = {e.type for step in STEPS for e in step.pre.enemies}
    assert types == set(EnemyType)
    assert any(step.pre.smoke for step in STEPS)
    assert any(u.off_desk for step in STEPS for u in step.pre.units)
    assert any(u.shield for step in STEPS for u in step.pre.units)


def test_states_stay_in_range_over_random_nights() -> None:
    for step in STEPS:
        assert_state_sane(step.post)


def test_events_never_carry_negative_damage() -> None:
    for step in STEPS:
        for event in step.events:
            assert event.dmg is None or event.dmg >= 0, event


def test_attack_damage_is_bounded_by_hit_points() -> None:
    for step in STEPS:
        enemies = {e.id: e for e in step.pre.enemies}
        for event in step.events:
            if event.type is EventType.ATTACK and event.dst in enemies:
                assert event.dmg is not None
                assert event.dmg <= enemies[event.dst].hp_max


def test_score_and_bayani_are_sane() -> None:
    for step in STEPS:
        assert score(step.post) >= 0
        owners = {owner for owner, _ in step.post.damage_by_owner}
        assert set(bayani(step.post)) <= owners


def test_defeated_count_only_grows() -> None:
    for step in STEPS:
        assert step.post.enemies_defeated >= step.pre.enemies_defeated
        killed = sum(1 for e in step.events if e.type is EventType.DEFEAT_ENEMY)
        assert step.post.enemies_defeated - step.pre.enemies_defeated == killed


def test_dead_and_absent_units_never_act() -> None:
    for step in STEPS:
        inactive = {u.id for u in step.pre.units if not u.can_act}
        for event in step.events:
            if event.type in ACTING_EVENTS and event.src in inactive:
                pytest.fail(f"inactive unit acted: {event}")


def test_dead_enemies_never_act() -> None:
    for step in STEPS:
        dead = {e.id for e in step.pre.enemies if not e.is_alive}
        for event in step.events:
            assert event.src not in dead, event


def test_stunned_and_carrying_enemies_do_not_attack() -> None:
    for step in STEPS:
        idle = {e.id for e in step.pre.enemies if e.is_stunned or e.carrying}
        for event in step.events:
            if event.type in (EventType.ATTACK, EventType.DODGE, EventType.STEAL):
                assert event.src not in idle, event


def test_enemies_never_hit_downed_or_absent_units() -> None:
    for step in STEPS:
        absent = {u.id for u in step.pre.units if not u.is_targetable}
        enemy_ids = {e.id for e in step.pre.enemies}
        for event in step.events:
            if event.src in enemy_ids and event.type in (
                EventType.ATTACK,
                EventType.STEAL,
                EventType.PUSH,
                EventType.THROWN,
            ):
                assert event.dst not in absent, event


def test_nothing_acts_after_it_is_removed_in_the_same_round() -> None:
    for step in STEPS:
        gone: set[str] = set()
        for event in step.events:
            if event.type in (EventType.DEFEAT_ENEMY,):
                assert event.dst is not None
                gone.add(event.dst)
            if event.type in (EventType.ATTACK, EventType.DODGE, EventType.STEAL):
                assert event.src not in gone, event


def test_resolution_is_deterministic_and_pure() -> None:
    for seed in range(120):
        rng = random.Random(seed)
        state = rand_board(rng)
        intents = rand_intents(rng, state)
        snapshot = copy.deepcopy(state)
        intent_snapshot = copy.deepcopy(intents)
        first = resolve_turn(state, intents)
        second = resolve_turn(copy.deepcopy(state), copy.deepcopy(intents))
        assert first == second
        assert state == snapshot
        assert intents == intent_snapshot
        begun = begin_turn(state)
        assert begun == begin_turn(copy.deepcopy(state))
        assert state == snapshot


def test_attack_order_does_not_change_enemy_outcomes() -> None:
    for seed in range(60):
        rng = random.Random(seed)
        state = rand_board(rng, Gen(allow_hostile_states=False))
        intents = [
            i for i in rand_intents(rng, state, 0.0) if i.action is Action.ATTACK
        ]
        forward = resolve_turn(state, intents)
        backward = resolve_turn(state, list(reversed(intents)))
        assert forward[0].enemies == backward[0].enemies


def test_begin_turn_targets_only_living_present_units() -> None:
    for seed in SEEDS:
        rng = random.Random(seed)
        state = rand_board(rng)
        present = {u.id for u in state.units if u.is_targetable}
        post, events = begin_turn(state)
        for enemy in post.enemies:
            if enemy.is_alive and enemy.target_id is not None:
                assert enemy.target_id in present, (seed, enemy)
        for event in events:
            if event.type is EventType.INTENT and event.src in {
                e.id for e in state.enemies
            }:
                assert event.dst in present


def test_pick_target_never_returns_unreachable_ids() -> None:
    for seed in SEEDS:
        rng = random.Random(seed)
        state = rand_board(rng)
        present = {u.id for u in state.units if u.is_targetable}
        for enemy in state.enemies:
            target = pick_target(enemy, state)
            assert target is None or target in present
            if enemy.carrying is not None:
                assert target is None
            if enemy.part is Part.LOWER:
                assert target is None


def test_inside_things_stay_inside() -> None:
    for step in STEPS:
        w, h = step.pre.play_w_cm, step.pre.play_h_cm
        before = {e.id: e for e in step.pre.enemies}
        for enemy in step.post.enemies:
            old = before.get(enemy.id)
            if old is not None and inside(old.position, w, h):
                assert inside(enemy.position, w, h), (old, enemy)
        units = {u.id: u for u in step.pre.units}
        for unit in step.post.units:
            old_unit = units[unit.id]
            if inside(old_unit.position, w, h) and old_unit.is_targetable:
                assert inside(unit.position, w, h), (old_unit, unit)


def test_spawned_enemies_start_inside_the_play_area() -> None:
    seen = 0
    for seed in SEEDS:
        rng = random.Random(seed)
        state = rand_board(rng)
        _, events = begin_turn(replace(state, turn=rng.randint(0, 7)))
        for event in events:
            if event.type is EventType.SPAWN:
                assert event.pos is not None
                assert inside(event.pos, state.play_w_cm, state.play_h_cm)
                seen += 1
    assert seen > 20


def test_used_power_sets_the_exact_cooldown() -> None:
    checked = 0
    for step in STEPS:
        users = {
            e.src
            for e in step.events
            if e.type in (EventType.POWER, EventType.HEAL)
            and e.src is not None
            and e.src.startswith("u_")
        }
        before = {u.id: u for u in step.pre.units}
        for unit in step.post.units:
            if unit.id in users:
                old = before[unit.id]
                assert unit.cooldown == max(
                    0, POWER_COOLDOWN[old.power_id] - old.cooldown_cut
                )
                checked += 1
    assert checked > 50


def test_cooldown_blocked_powers_never_fire() -> None:
    for step in STEPS:
        blocked = {
            u.id
            for u in step.pre.units
            if u.cooldown > 0 and u.power_id is not PowerId.P01
        }
        for event in step.events:
            if event.type is EventType.POWER:
                assert event.src not in blocked, event


def test_outcome_events_match_check_outcome() -> None:
    for step in STEPS:
        outcome = check_outcome(step.post)
        kinds = [e.type for e in step.events]
        assert kinds.count(EventType.WIN) == (1 if outcome is Outcome.WIN else 0)
        assert kinds.count(EventType.LOSE) == (1 if outcome is Outcome.LOSE else 0)


def test_outcome_rules_hold_for_random_boards() -> None:
    for seed in SEEDS:
        rng = random.Random(seed)
        state = rand_board(rng, Gen(allow_hostile_states=False))
        kubo = state.kubo
        assert kubo is not None
        down = replace(
            state,
            units=tuple(replace(u, hp=0) if u.is_kubo else u for u in state.units),
        )
        assert check_outcome(down) is Outcome.LOSE
        late = replace(state, turn=TURNS_PER_NIGHT)
        if check_outcome(late) is not Outcome.LOSE:
            assert check_outcome(late) is Outcome.WIN
        early = replace(state, turn=1)
        assert check_outcome(early) is not Outcome.WIN


def test_full_night_never_raises_and_ends_cleanly() -> None:
    for seed in range(40):
        rng = random.Random(seed)
        state = rand_board(rng, Gen(allow_hostile_states=False))
        state = replace(state, turn=0, enemies=(), enemy_counter=(), smoke=())
        for _ in range(TURNS_PER_NIGHT):
            state, _ = begin_turn(state)
            state, _ = resolve_turn(state, rand_intents(rng, state))
            assert_state_sane(state)
            if check_outcome(state) is Outcome.LOSE:
                break
        assert state.turn <= TURNS_PER_NIGHT


def test_garbage_intents_never_raise() -> None:
    for seed in range(120):
        rng = random.Random(seed)
        state = rand_board(rng)
        intents = rand_intents(rng, state, garbage=1.0)
        intents.append(Intent("", Action.POWER, ""))
        intents.append(Intent("u_kubo", Action.HEAL, "u_kubo"))
        resolve_turn(state, intents)
        resolve_turn(state, [])


def test_hulls_with_fewer_than_three_points_raise_value_error() -> None:
    for count in range(3):
        hull = tuple((float(i), 0.0) for i in range(count))
        with pytest.raises(ValueError):
            hull_point_distance(hull, (1.0, 1.0))
        with pytest.raises(ValueError):
            hull_hull_distance(hull, square_hull((0.0, 0.0), 1.0))
        with pytest.raises(ValueError):
            hull_centroid(hull)


def test_geometry_distances_are_symmetric_and_non_negative() -> None:
    rng = random.Random(7)
    for _ in range(200):
        a = square_hull((rng.uniform(-5, 70), rng.uniform(-5, 50)), rng.uniform(0.5, 3))
        b = translate_hull(a, rng.uniform(-20, 20), rng.uniform(-20, 20))
        assert hull_hull_distance(a, b) >= 0.0
        assert hull_hull_distance(a, b) == pytest.approx(hull_hull_distance(b, a))
        point = (rng.uniform(-10, 80), rng.uniform(-10, 60))
        assert hull_point_distance(a, point) >= 0.0
        assert hull_point_distance(a, point, 0.0) >= hull_point_distance(a, point)


def test_in_range_is_monotonic_with_one_cm_tolerance() -> None:
    rng = random.Random(3)
    for _ in range(300):
        reach = rng.uniform(0, 20)
        dist = rng.uniform(0, 30)
        assert in_range(dist, reach) == (dist <= reach + 1.0)
        if in_range(dist, reach):
            assert in_range(dist - 0.1, reach)
            assert in_range(dist, reach + 0.1)


def test_wave_spawns_are_deterministic_and_inside() -> None:
    for turn in range(11):
        for difficulty in Difficulty:
            for players in (1, 2, 3, 4):
                for flags in (frozenset[str](), frozenset({"tabi_tabi"})):
                    kubo = (30.0, 20.0)
                    first = spawns_for(turn, difficulty, players, flags, kubo, 60, 40)
                    again = spawns_for(turn, difficulty, players, flags, kubo, 60, 40)
                    assert first == again
                    if not 1 <= turn <= 8:
                        assert first == ()
                    for spawn in first:
                        assert inside(spawn.position, 60, 40)
                    lowers = [s for s in first if s.part is Part.LOWER]
                    uppers = [s for s in first if s.part is Part.UPPER]
                    assert len(lowers) == len(uppers)


def test_clamp_card_invariants_for_random_drafts() -> None:
    rng = random.Random(11)
    classes = list(UnitClass)
    powers = list(PowerId)
    for _ in range(500):
        roster = [rng.choice(classes) for _ in range(rng.randint(0, 11))]
        draft = CardDraft(
            rng.choice(classes),
            rng.randint(-5, 5),
            rng.randint(-5, 5),
            rng.choice(powers),
        )
        difficulty = rng.choice(list(Difficulty))
        card = clamp_card(draft, roster, difficulty)
        template = CLASS_TEMPLATES[card.unit_class]
        assert card.hp_max >= HP_FLOOR
        assert 0 <= card.atk <= ATK_CAP
        assert card.power_id in template.powers
        assert -1 <= card.hp_delta <= 1
        assert -1 <= card.atk_delta <= 1
        assert card.hp_delta + card.atk_delta <= 0 or card.unit_class is UnitClass.KUBO
        if roster:
            assert roster.count(UnitClass.CHARM) < 2 or card.unit_class is not (
                UnitClass.CHARM
            )
            assert roster.count(UnitClass.WALL) < 2 or card.unit_class is not (
                UnitClass.WALL
            )


def test_every_class_and_power_pair_resolves_without_error() -> None:
    rng = random.Random(5)
    seen: set[PowerId] = set()
    for unit_class in UnitClass:
        if unit_class is UnitClass.KUBO:
            continue
        for power in CLASS_TEMPLATES[unit_class].powers:
            seen.add(power)
            gen = Gen(allow_powers=frozenset({power}), allow_hostile_states=False)
            for _ in range(15):
                state = rand_board(rng, gen)
                begun, _ = begin_turn(state)
                resolve_turn(begun, rand_intents(rng, begun, 0.1))
    assert seen >= {p for p in PowerId if p is not PowerId.NONE}


def test_boards_without_a_kubo_or_without_units_do_not_raise() -> None:
    for seed in range(100):
        rng = random.Random(seed)
        state = rand_board(rng)
        for units in (
            tuple(u for u in state.units if not u.is_kubo),
            (),
        ):
            board = replace(state, units=units)
            begun, _ = begin_turn(board)
            resolved, _ = resolve_turn(begun, rand_intents(rng, begun))
            assert_state_sane(resolved)

import random
from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import Final

from rules.enemies import EnemyType, Part, enemy_stats
from rules.geometry import Hull, Point, square_hull
from rules.resolve import (
    POWER_COOLDOWN,
    Action,
    BoardState,
    EnemyState,
    Event,
    Intent,
    Smoke,
    UnitState,
    begin_turn,
    resolve_turn,
    with_positions,
)
from rules.units import (
    CLASS_TEMPLATES,
    MOVE_CM,
    Difficulty,
    PowerId,
    UnitClass,
)

KUBO_ID: Final = "u_kubo"
OWNERS: Final = ("P1", "P2", "P3", "P4", None)
TRIANGLE: Final[Hull] = ((-1.5, -1.5), (1.5, -1.5), (0.0, 2.0))
MAX_COOLDOWN: Final = max(POWER_COOLDOWN.values())
OTHER_CLASSES: Final = tuple(c for c in UnitClass if c is not UnitClass.KUBO)
ENEMY_KINDS: Final = (
    EnemyType.ASWANG,
    EnemyType.TIKBALANG,
    EnemyType.KAPRE,
    EnemyType.MANANANGGAL,
    EnemyType.DUWENDE,
)


@dataclass(frozen=True)
class Gen:
    allow_powers: frozenset[PowerId] | None = None
    deny_powers: frozenset[PowerId] = frozenset()
    force_smoke: bool = False
    min_units: int = 2
    max_units: int = 11
    max_enemies: int = 8
    allow_hostile_states: bool = True


def rand_point(rng: random.Random, w: float, h: float, wild: bool = True) -> Point:
    roll = rng.random()
    if roll < 0.55 or not wild:
        return (rng.uniform(0.0, w), rng.uniform(0.0, h))
    if roll < 0.8:
        x = rng.choice((rng.uniform(0.0, 1.5), rng.uniform(w - 1.5, w)))
        y = rng.choice((rng.uniform(0.0, 1.5), rng.uniform(h - 1.5, h)))
        return (x, y) if rng.random() < 0.5 else (rng.uniform(0.0, w), y)
    return (rng.uniform(-8.0, w + 8.0), rng.uniform(-8.0, h + 8.0))


def _hull(rng: random.Random) -> Hull:
    if rng.random() < 0.2:
        return TRIANGLE
    return square_hull((0.0, 0.0), rng.uniform(0.8, 3.0))


def _power_for(rng: random.Random, unit_class: UnitClass, gen: Gen) -> PowerId:
    powers = [
        p
        for p in CLASS_TEMPLATES[unit_class].powers
        if p not in gen.deny_powers
        and (gen.allow_powers is None or p in gen.allow_powers)
    ]
    if not powers:
        powers = [PowerId.NONE]
    return rng.choice(powers)


def rand_unit(
    rng: random.Random,
    uid: str,
    unit_class: UnitClass,
    w: float,
    h: float,
    gen: Gen,
) -> UnitState:
    template = CLASS_TEMPLATES[unit_class]
    hp_max = max(1, template.hp + rng.randint(-1, 2))
    if unit_class is UnitClass.KUBO:
        hp_max = rng.randint(8, 12)
    hp = rng.choice((hp_max, hp_max, rng.randint(0, hp_max)))
    if unit_class is UnitClass.KUBO:
        hp = max(1, hp)
    power = (
        PowerId.NONE
        if unit_class is UnitClass.KUBO
        else _power_for(rng, unit_class, gen)
    )
    pos = rand_point(rng, w, h)
    state = UnitState(
        id=uid,
        unit_class=unit_class,
        hp=hp,
        hp_max=hp_max,
        atk=min(3, max(0, template.atk + rng.randint(-1, 1))),
        move=template.move,
        range=template.range,
        power_id=power,
        cooldown=rng.choice((0, 0, rng.randint(0, MAX_COOLDOWN))),
        position=pos,
        start=pos,
        hull_offsets=_hull(rng),
        owner=rng.choice(OWNERS),
        shield=rng.choice((0, 0, rng.randint(0, 3))),
        atk_bonus=rng.choice((0, 0, rng.randint(0, 2))),
        cooldown_cut=rng.choice((0, 0, rng.randint(0, 2))),
    )
    if gen.allow_hostile_states:
        roll = rng.random()
        if roll < 0.06:
            state = replace(state, off_desk=True)
        elif roll < 0.1:
            state = replace(state, out_turns=1)
        elif roll < 0.13:
            state = replace(state, is_lost=True)
    return state


def rand_enemies(
    rng: random.Random, w: float, h: float, gen: Gen
) -> tuple[list[EnemyState], dict[str, int]]:
    counter: dict[str, int] = {}
    enemies: list[EnemyState] = []
    count = rng.randint(0, gen.max_enemies)
    difficulty = rng.choice(list(Difficulty))

    def make(kind: EnemyType, part: Part | None) -> EnemyState:
        number = counter.get(kind.value, 0) + 1
        counter[kind.value] = number
        hp, atk, move_cm, range_cm, flies = enemy_stats(kind, part, difficulty)
        return EnemyState(
            id=f"e_{kind.value}_{number}",
            type=kind,
            part=part,
            hp=rng.randint(1, hp),
            hp_max=hp,
            atk=atk,
            move_cm=move_cm,
            range_cm=range_cm,
            flies=flies,
            position=rand_point(rng, w, h),
            spawn_turn=rng.randint(1, 4),
            is_stunned=rng.random() < 0.1,
        )

    while len(enemies) < count:
        kind = rng.choice(ENEMY_KINDS)
        if kind is EnemyType.MANANANGGAL:
            lower = make(kind, Part.LOWER)
            upper = make(kind, Part.UPPER)
            if rng.random() < 0.25:
                upper = replace(upper, hp=0, reform_in=rng.randint(1, 2))
            enemies.extend((lower, upper))
        else:
            enemies.append(make(kind, None))
    return enemies, counter


def rand_board(rng: random.Random, gen: Gen | None = None) -> BoardState:
    gen = gen or Gen()
    w = rng.choice((60.0, 60.0, 50.0, 72.0, 90.0))
    h = rng.choice((40.0, 40.0, 35.0, 48.0, 60.0))
    units = [rand_unit(rng, KUBO_ID, UnitClass.KUBO, w, h, gen)]
    for index in range(rng.randint(gen.min_units, gen.max_units)):
        unit_class = rng.choice(OTHER_CLASSES)
        units.append(rand_unit(rng, f"u_{index}", unit_class, w, h, gen))
    enemies, counter = rand_enemies(rng, w, h, gen)
    smoke: list[Smoke] = []
    for enemy in enemies:
        if enemy.type is EnemyType.KAPRE and (gen.force_smoke or rng.random() < 0.6):
            smoke.append(Smoke(enemy.id, enemy.position))
    if gen.force_smoke and not smoke:
        smoke.append(Smoke("e_kapre_9", rand_point(rng, w, h, wild=False)))
    for index in range(rng.randint(0, 2)):
        smoke.append(Smoke(f"e_kapre_x{index}", rand_point(rng, w, h)))
    thieves = [e for e in enemies if e.type is EnemyType.DUWENDE and e.hp > 0]
    for index, unit in enumerate(units):
        if unit.is_kubo or not thieves or rng.random() > 0.2:
            continue
        thief = thieves[rng.randrange(len(thieves))]
        if thief.carrying is not None:
            continue
        units[index] = replace(unit, stolen_by=thief.id)
        enemies[enemies.index(thief)] = replace(thief, carrying=unit.id)
        thieves.remove(thief)
    return BoardState(
        turn=rng.randint(0, 6),
        difficulty=rng.choice(list(Difficulty)),
        players=rng.randint(1, 4),
        play_w_cm=w,
        play_h_cm=h,
        units=tuple(units),
        enemies=tuple(enemies),
        flags=rng.choice((frozenset[str](), frozenset({"tabi_tabi"}))),
        enemy_counter=tuple(counter.items()),
        smoke=tuple(smoke),
    )


def rand_intents(
    rng: random.Random, state: BoardState, garbage: float = 0.25
) -> list[Intent]:
    unit_ids = [u.id for u in state.units]
    enemy_ids = [e.id for e in state.enemies]
    intents: list[Intent] = []
    for unit in state.units:
        if rng.random() < 0.3:
            continue
        action = rng.choice(list(Action))
        roll = rng.random()
        target: str | None
        if roll < garbage:
            target = rng.choice([*unit_ids, *enemy_ids, None, "nobody", "e_x_99"])
        elif action is Action.ATTACK or unit.power_id in (
            PowerId.P03,
            PowerId.P04,
            PowerId.P09,
            PowerId.P11,
            PowerId.P12,
        ):
            target = rng.choice(enemy_ids) if enemy_ids else None
        elif unit.power_id in (PowerId.P01, PowerId.P02) or action is Action.HEAL:
            target = rng.choice(unit_ids)
        else:
            target = None
        intents.append(Intent(unit.id, action, target))
    if rng.random() < 0.2:
        intents.append(Intent("ghost", Action.ATTACK, rng.choice([*enemy_ids, None])))
    if intents and rng.random() < 0.2:
        intents.append(rng.choice(intents))
    rng.shuffle(intents)
    return intents


def jitter(rng: random.Random, state: BoardState) -> BoardState:
    positions: dict[str, Point] = {}
    for unit in state.units:
        if unit.is_kubo or rng.random() < 0.3:
            continue
        reach = MOVE_CM[unit.move]
        dx = rng.uniform(-reach, reach)
        dy = rng.uniform(-reach, reach)
        x, y = unit.position
        if rng.random() < 0.08:
            positions[unit.id] = rand_point(rng, state.play_w_cm, state.play_h_cm)
        else:
            positions[unit.id] = (x + dx, y + dy)
    moved = with_positions(state, positions)
    shielded = tuple(
        replace(u, shield=rng.randint(0, 3), atk_bonus=rng.randint(0, 2))
        if rng.random() < 0.25
        else u
        for u in moved.units
    )
    return replace(moved, units=shielded)


@dataclass(frozen=True)
class Step:
    pre: BoardState
    intents: tuple[Intent, ...]
    post: BoardState
    events: tuple[Event, ...]


def play(
    seed: int, turns: int = 3, gen: Gen | None = None, garbage: float = 0.25
) -> Iterator[Step]:
    rng = random.Random(seed)
    state = rand_board(rng, gen)
    for _ in range(turns):
        state, _ = begin_turn(state)
        state = jitter(rng, state)
        intents = rand_intents(rng, state, garbage)
        post, events = resolve_turn(state, intents)
        yield Step(state, tuple(intents), post, events)
        state = post

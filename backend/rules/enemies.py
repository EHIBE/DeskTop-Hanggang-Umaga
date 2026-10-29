from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final, cast

from rules.geometry import (
    AURA_RADIUS_CM,
    ENEMY_RADIUS_CM,
    ISOLATION_RADIUS_CM,
    Hull,
    Point,
    clamp_point,
    displacement,
    hull_centroid,
    hull_hull_distance,
    hull_point_distance,
)
from rules.units import Difficulty, PowerId, UnitClass

if TYPE_CHECKING:
    from rules.resolve import BoardState, EnemyState, UnitState


class EnemyType(StrEnum):
    ASWANG = "aswang"
    TIKBALANG = "tikbalang"
    KAPRE = "kapre"
    MANANANGGAL = "manananggal"
    DUWENDE = "duwende"


class Part(StrEnum):
    UPPER = "upper"
    LOWER = "lower"


@dataclass(frozen=True)
class EnemyBase:
    hp: int
    atk: int
    move_cm: float
    range_cm: float
    flies: bool


ENEMY_BASE: Final[dict[tuple[EnemyType, Part | None], EnemyBase]] = {
    (EnemyType.ASWANG, None): EnemyBase(3, 2, 15.0, 5.0, False),
    (EnemyType.TIKBALANG, None): EnemyBase(5, 1, 10.0, 5.0, False),
    (EnemyType.KAPRE, None): EnemyBase(8, 3, 5.0, 9.0, False),
    (EnemyType.MANANANGGAL, Part.UPPER): EnemyBase(4, 2, 20.0, 5.0, True),
    (EnemyType.MANANANGGAL, Part.LOWER): EnemyBase(3, 0, 0.0, 0.0, False),
    (EnemyType.DUWENDE, None): EnemyBase(2, 0, 12.0, 5.0, False),
}

MOVE_STEP_CM: Final = 0.25
BISECT_ITERATIONS: Final = 40
MIN_ENEMY_HP: Final = 1
MAHIRAP_ATK_BONUS: Final = 1
MADALI_HP_PENALTY: Final = 1
DISTANCE_KEY_DIGITS: Final = 6


def _normalize_part(enemy_type: EnemyType, part: Part | None) -> Part | None:
    if enemy_type is EnemyType.MANANANGGAL:
        return part or Part.UPPER
    return None


def enemy_stats(
    enemy_type: EnemyType, part: Part | None, difficulty: Difficulty
) -> tuple[int, int, float, float, bool]:
    base = ENEMY_BASE[(enemy_type, _normalize_part(enemy_type, part))]
    hp = base.hp
    atk = base.atk
    if difficulty is Difficulty.MADALI:
        hp = max(MIN_ENEMY_HP, hp - MADALI_HP_PENALTY)
    elif difficulty is Difficulty.MAHIRAP and atk > 0:
        atk += MAHIRAP_ATK_BONUS
    return hp, atk, base.move_cm, base.range_cm, base.flies


def _living(state: BoardState) -> list[UnitState]:
    return [u for u in state.units if u.is_targetable]


def _gap(enemy: EnemyState, unit: UnitState) -> float:
    return hull_point_distance(unit.hull, enemy.position)


def _nearest_key(enemy: EnemyState, ranked: tuple[int, UnitState]) -> tuple[float, int]:
    index, unit = ranked
    return (round(_gap(enemy, unit), DISTANCE_KEY_DIGITS), index)


def _nearest(enemy: EnemyState, units: list[UnitState]) -> UnitState | None:
    ranked = [(i, u) for i, u in enumerate(units)]
    if not ranked:
        return None
    return min(ranked, key=lambda item: _nearest_key(enemy, item))[1]


def _lowest_hp(enemy: EnemyState, units: list[UnitState]) -> UnitState | None:
    ranked = [(i, u) for i, u in enumerate(units)]
    if not ranked:
        return None
    best = min(
        ranked,
        key=lambda item: (item[1].hp, *_nearest_key(enemy, item)),
    )
    return best[1]


def _is_isolated(unit: UnitState, living: list[UnitState]) -> bool:
    return not any(
        other.id != unit.id
        and hull_hull_distance(unit.hull, other.hull) <= ISOLATION_RADIUS_CM
        for other in living
    )


def _kubo_of(living: list[UnitState]) -> UnitState | None:
    for unit in living:
        if unit.is_kubo:
            return unit
    return None


def _aswang_target(enemy: EnemyState, living: list[UnitState]) -> UnitState | None:
    others = [u for u in living if not u.is_kubo]
    isolated = [u for u in others if _is_isolated(u, living)]
    pick = _nearest(enemy, isolated) or _lowest_hp(enemy, others)
    return pick or _kubo_of(living)


def pick_target(enemy: EnemyState, state: BoardState) -> str | None:
    if enemy.carrying is not None:
        return None
    living = _living(state)
    pick: UnitState | None
    if enemy.type is EnemyType.ASWANG:
        pick = _aswang_target(enemy, living)
    elif enemy.type is EnemyType.TIKBALANG:
        pick = _nearest(enemy, living)
    elif enemy.type is EnemyType.KAPRE:
        pick = _kubo_of(living)
    elif enemy.type is EnemyType.MANANANGGAL:
        if enemy.part is Part.LOWER:
            return None
        pick = _kubo_of(living) or _nearest(enemy, living)
    else:
        charms = [u for u in living if u.unit_class is UnitClass.CHARM]
        pick = _nearest(enemy, charms) or _lowest_hp(
            enemy, [u for u in living if not u.is_kubo]
        )
    return pick.id if pick else None


def _is_hull(target: Point | Hull) -> bool:
    return isinstance(target[0], tuple)


def _target_gap(target: Point | Hull, position: Point) -> float:
    if _is_hull(target):
        return hull_point_distance(cast(Hull, target), position)
    point = cast(Point, target)
    return max(0.0, displacement(position, point) - ENEMY_RADIUS_CM)


def _goal_point(target: Point | Hull) -> Point:
    if _is_hull(target):
        return hull_centroid(cast(Hull, target))
    return cast(Point, target)


def _boundary(
    test: Callable[[float], bool], low: float, high: float
) -> tuple[float, float]:
    lo, hi = low, high
    for _ in range(BISECT_ITERATIONS):
        mid = (lo + hi) / 2.0
        if test(mid):
            hi = mid
        else:
            lo = mid
    return lo, hi


def _wall_hulls(state: BoardState) -> list[Hull]:
    return [
        u.hull
        for u in state.units
        if u.unit_class is UnitClass.WALL and not u.is_down and not u.is_out
    ]


def _aura_hulls(state: BoardState) -> list[Hull]:
    return [
        u.hull
        for u in state.units
        if u.power_id is PowerId.P07 and not u.is_down and not u.is_out
    ]


def move_toward(enemy: EnemyState, target: Point | Hull, state: BoardState) -> Point:
    start = enemy.position
    goal = _goal_point(target)
    total = displacement(start, goal)
    max_s = min(enemy.move_cm, total)
    if max_s <= 0.0 or _target_gap(target, start) <= enemy.range_cm:
        return start
    ux = (goal[0] - start[0]) / total
    uy = (goal[1] - start[1]) / total
    walls = [] if enemy.flies else _wall_hulls(state)
    auras = _aura_hulls(state)
    touching = {i for i, w in enumerate(walls) if hull_point_distance(w, start) <= 0.0}
    inside = {
        i for i, a in enumerate(auras) if hull_point_distance(a, start) < AURA_RADIUS_CM
    }
    width, height = state.play_w_cm, state.play_h_cm

    def at(s: float) -> Point:
        return clamp_point((start[0] + ux * s, start[1] + uy * s), width, height)

    def blocked(s: float) -> bool:
        p = at(s)
        hit_wall = any(
            hull_point_distance(w, p) <= 0.0
            for i, w in enumerate(walls)
            if i not in touching
        )
        hit_aura = any(
            hull_point_distance(a, p) < AURA_RADIUS_CM
            for i, a in enumerate(auras)
            if i not in inside
        )
        return hit_wall or hit_aura

    def reached(s: float) -> bool:
        return _target_gap(target, at(s)) <= enemy.range_cm

    previous = 0.0
    while previous < max_s:
        current = min(previous + MOVE_STEP_CM, max_s)
        if blocked(current):
            return at(_boundary(blocked, previous, current)[0])
        if reached(current):
            return at(_boundary(reached, previous, current)[1])
        previous = current
    return at(max_s)


def _edge_candidates(
    position: Point, width: float, height: float
) -> list[tuple[float, Point]]:
    return [
        (position[1], (0.0, -1.0)),
        (width - position[0], (1.0, 0.0)),
        (height - position[1], (0.0, 1.0)),
        (position[0], (-1.0, 0.0)),
    ]


def _nearest_edge(position: Point, width: float, height: float) -> tuple[float, Point]:
    candidates = _edge_candidates(position, width, height)
    ranked = min(
        enumerate(candidates),
        key=lambda item: (round(item[1][0], DISTANCE_KEY_DIGITS), item[0]),
    )
    return ranked[1]


def at_edge(position: Point, width: float, height: float) -> bool:
    return _nearest_edge(position, width, height)[0] <= ENEMY_RADIUS_CM


def flee_point(enemy: EnemyState, width: float, height: float) -> Point:
    distance, (dx, dy) = _nearest_edge(enemy.position, width, height)
    step = min(enemy.move_cm, max(0.0, distance))
    return clamp_point(
        (enemy.position[0] + dx * step, enemy.position[1] + dy * step), width, height
    )

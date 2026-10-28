import math
from enum import StrEnum
from functools import lru_cache
from typing import Final

from shapely.geometry import Point as ShapelyPoint  # type: ignore[import-untyped]
from shapely.geometry import Polygon

FOREST_EDGE_CM: Final = 5.0
ENEMY_RADIUS_CM: Final = 2.0
DISTANCE_TOLERANCE_CM: Final = 1.0
ISOLATION_RADIUS_CM: Final = 10.0
AURA_RADIUS_CM: Final = 8.0
KUBO_MOVED_WARN_CM: Final = 2.0
MIN_HULL_POINTS: Final = 3
POLYGON_CACHE_SIZE: Final = 512

Point = tuple[float, float]
Hull = tuple[Point, ...]


class Edge(StrEnum):
    NORTH = "north"
    EAST = "east"
    SOUTH = "south"
    WEST = "west"


@lru_cache(maxsize=POLYGON_CACHE_SIZE)
def _polygon(hull: Hull) -> Polygon:
    if len(hull) < MIN_HULL_POINTS:
        raise ValueError("hull needs at least 3 points")
    return Polygon(hull)


def square_hull(center: Point, half_cm: float) -> Hull:
    cx, cy = center
    return (
        (cx - half_cm, cy - half_cm),
        (cx + half_cm, cy - half_cm),
        (cx + half_cm, cy + half_cm),
        (cx - half_cm, cy + half_cm),
    )


def hull_point_distance(
    hull: Hull, point: Point, radius: float = ENEMY_RADIUS_CM
) -> float:
    raw = float(_polygon(hull).distance(ShapelyPoint(point)))
    return max(0.0, raw - radius)


def hull_hull_distance(a: Hull, b: Hull) -> float:
    return float(_polygon(a).distance(_polygon(b)))


def hull_centroid(hull: Hull) -> Point:
    centroid = _polygon(hull).centroid
    return (float(centroid.x), float(centroid.y))


def in_range(distance_cm: float, range_cm: float) -> bool:
    return distance_cm <= range_cm + DISTANCE_TOLERANCE_CM


def displacement(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def is_move_legal(start: Point, end: Point, move_cm: float) -> bool:
    return displacement(start, end) <= move_cm + DISTANCE_TOLERANCE_CM


def translate_hull(hull: Hull, dx: float, dy: float) -> Hull:
    return tuple((x + dx, y + dy) for x, y in hull)


def clamp_point(point: Point, width_cm: float, height_cm: float) -> Point:
    return (
        min(max(point[0], 0.0), width_cm),
        min(max(point[1], 0.0), height_cm),
    )

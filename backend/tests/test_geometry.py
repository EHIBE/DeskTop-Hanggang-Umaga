import math

import pytest

from rules.geometry import (
    AURA_RADIUS_CM,
    DISTANCE_TOLERANCE_CM,
    ENEMY_RADIUS_CM,
    FOREST_EDGE_CM,
    ISOLATION_RADIUS_CM,
    KUBO_MOVED_WARN_CM,
    Edge,
    clamp_point,
    displacement,
    hull_centroid,
    hull_hull_distance,
    hull_point_distance,
    in_range,
    is_move_legal,
    square_hull,
    translate_hull,
)


def test_constants_match_docs() -> None:
    assert FOREST_EDGE_CM == 5.0
    assert ENEMY_RADIUS_CM == 2.0
    assert DISTANCE_TOLERANCE_CM == 1.0
    assert ISOLATION_RADIUS_CM == 10.0
    assert AURA_RADIUS_CM == 8.0
    assert KUBO_MOVED_WARN_CM == 2.0


def test_edge_values() -> None:
    assert [e.value for e in Edge] == ["north", "east", "south", "west"]


def test_square_hull_corners() -> None:
    hull = square_hull((10.0, 20.0), 1.5)
    assert len(hull) == 4
    assert min(p[0] for p in hull) == 8.5
    assert max(p[1] for p in hull) == 21.5


def test_hull_point_distance_edge_to_edge() -> None:
    hull = square_hull((10.0, 10.0), 1.5)
    assert hull_point_distance(hull, (20.0, 10.0)) == pytest.approx(6.5)


def test_hull_point_distance_floored_at_zero() -> None:
    hull = square_hull((10.0, 10.0), 1.5)
    assert hull_point_distance(hull, (12.0, 10.0)) == 0.0
    assert hull_point_distance(hull, (10.0, 10.0)) == 0.0


def test_hull_point_distance_custom_radius() -> None:
    hull = square_hull((0.0, 0.0), 1.0)
    assert hull_point_distance(hull, (6.0, 0.0), radius=0.0) == pytest.approx(5.0)


def test_hull_hull_distance() -> None:
    a = square_hull((0.0, 0.0), 1.0)
    b = square_hull((10.0, 0.0), 1.0)
    assert hull_hull_distance(a, b) == pytest.approx(8.0)
    assert hull_hull_distance(a, a) == 0.0


def test_hull_needs_three_points() -> None:
    with pytest.raises(ValueError):
        hull_point_distance(((0.0, 0.0), (1.0, 1.0)), (5.0, 5.0))


def test_hull_centroid() -> None:
    assert hull_centroid(square_hull((4.0, 6.0), 2.0)) == pytest.approx((4.0, 6.0))


@pytest.mark.parametrize(
    ("distance", "range_cm", "expected"),
    [(5.0, 5.0, True), (6.0, 5.0, True), (6.01, 5.0, False), (0.0, 0.0, True)],
)
def test_in_range_tolerance(distance: float, range_cm: float, expected: bool) -> None:
    assert in_range(distance, range_cm) is expected


def test_displacement() -> None:
    assert displacement((0.0, 0.0), (3.0, 4.0)) == 5.0


@pytest.mark.parametrize(
    ("end", "legal"),
    [((9.0, 0.0), True), ((9.01, 0.0), False), ((0.0, 0.0), True)],
)
def test_is_move_legal_tolerance(end: tuple[float, float], legal: bool) -> None:
    assert is_move_legal((0.0, 0.0), end, 8.0) is legal


def test_translate_hull() -> None:
    hull = translate_hull(square_hull((0.0, 0.0), 1.0), 5.0, -2.0)
    assert hull[0] == (4.0, -3.0)


def test_clamp_point() -> None:
    assert clamp_point((-3.0, 50.0), 60.0, 40.0) == (0.0, 40.0)
    assert clamp_point((30.0, 20.0), 60.0, 40.0) == (30.0, 20.0)
    assert math.isclose(clamp_point((70.0, 5.0), 60.0, 40.0)[0], 60.0)

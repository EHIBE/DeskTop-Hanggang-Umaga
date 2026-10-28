import pytest

from rules.enemies import EnemyType, Part, enemy_stats, move_toward, pick_target
from rules.geometry import hull_point_distance, square_hull
from rules.resolve import EnemyState, UnitState
from rules.units import Difficulty, PowerId, UnitClass
from tests.test_resolve import KUBO_ID, W, board, enemy, kubo, unit

N = Difficulty.NORMAL
ASWANG = EnemyType.ASWANG
UPPER = Part.UPPER
LOWER = Part.LOWER


@pytest.mark.parametrize(
    ("etype", "part", "expected"),
    [
        (ASWANG, None, (3, 2, 15.0, 5.0, False)),
        (EnemyType.TIKBALANG, None, (5, 1, 10.0, 5.0, False)),
        (EnemyType.KAPRE, None, (8, 3, 5.0, 9.0, False)),
        (EnemyType.MANANANGGAL, UPPER, (4, 2, 20.0, 5.0, True)),
        (EnemyType.MANANANGGAL, LOWER, (3, 0, 0.0, 0.0, False)),
        (EnemyType.DUWENDE, None, (2, 0, 12.0, 5.0, False)),
    ],
)
def test_normal_stats(
    etype: EnemyType, part: Part | None, expected: tuple[int, int, float, float, bool]
) -> None:
    assert enemy_stats(etype, part, N) == expected


def test_madali_reduces_hp_with_floor_one() -> None:
    assert enemy_stats(ASWANG, None, Difficulty.MADALI)[0] == 2
    assert enemy_stats(EnemyType.KAPRE, None, Difficulty.MADALI)[0] == 7
    assert enemy_stats(EnemyType.DUWENDE, None, Difficulty.MADALI)[0] == 1
    assert enemy_stats(EnemyType.MANANANGGAL, LOWER, Difficulty.MADALI)[0] == 2
    assert enemy_stats(ASWANG, None, Difficulty.MADALI)[1] == 2


def test_mahirap_adds_atk_except_atk_zero() -> None:
    assert enemy_stats(ASWANG, None, Difficulty.MAHIRAP)[1] == 3
    assert enemy_stats(EnemyType.KAPRE, None, Difficulty.MAHIRAP)[1] == 4
    assert enemy_stats(EnemyType.DUWENDE, None, Difficulty.MAHIRAP)[1] == 0
    assert enemy_stats(EnemyType.MANANANGGAL, LOWER, Difficulty.MAHIRAP)[1] == 0
    assert enemy_stats(ASWANG, None, Difficulty.MAHIRAP)[0] == 3


def test_part_defaults_for_manananggal_and_ignored_elsewhere() -> None:
    assert enemy_stats(EnemyType.MANANANGGAL, None, N) == enemy_stats(
        EnemyType.MANANANGGAL, UPPER, N
    )
    assert enemy_stats(ASWANG, UPPER, N) == enemy_stats(ASWANG, None, N)


def target_of(e: EnemyState, units: list[UnitState]) -> str | None:
    return pick_target(e, board(units, [e]))


def test_aswang_prefers_isolated_unit() -> None:
    units = [
        kubo((55.0, 35.0)),
        unit("a", pos=(10.0, 10.0)),
        unit("b", pos=(12.0, 10.0)),
        unit("c", UnitClass.HEALER, (45.0, 10.0)),
    ]
    e = enemy("e", pos=(30.0, 2.5))
    assert target_of(e, units) == "c"


def test_aswang_isolation_counts_kubo_as_ally() -> None:
    units = [
        kubo((10.0, 10.0)),
        unit("a", pos=(12.0, 12.0), hp=2),
        unit("b", pos=(50.0, 30.0), hp=6),
    ]
    e = enemy("e", pos=(30.0, 2.5))
    assert target_of(e, units) == "b"


def test_aswang_picks_nearest_among_isolated() -> None:
    units = [
        kubo((55.0, 35.0)),
        unit("far", pos=(5.0, 35.0)),
        unit("near", pos=(45.0, 10.0)),
    ]
    e = enemy("e", pos=(50.0, 2.5))
    assert target_of(e, units) == "near"


def test_aswang_without_isolated_picks_lowest_hp_non_kubo() -> None:
    units = [
        kubo((30.0, 20.0)),
        unit("a", pos=(28.0, 20.0), hp=5),
        unit("b", pos=(32.0, 20.0), hp=2),
        unit("c", pos=(30.0, 24.0), hp=4),
    ]
    e = enemy("e", pos=(30.0, 2.5))
    assert target_of(e, units) == "b"


def test_aswang_lowest_hp_tie_goes_to_nearest_then_order() -> None:
    units = [
        kubo((30.0, 20.0)),
        unit("a", pos=(28.0, 24.0), hp=2),
        unit("b", pos=(32.0, 22.0), hp=2),
        unit("c", pos=(31.0, 22.0), hp=2),
    ]
    e = enemy("e", pos=(30.0, 2.5))
    assert target_of(e, units) == "c"
    same = [
        kubo((30.0, 20.0)),
        unit("a", pos=(26.0, 22.0), hp=2),
        unit("b", pos=(34.0, 22.0), hp=2),
    ]
    assert target_of(e, same) == "a"


def test_aswang_falls_back_to_kubo_when_alone() -> None:
    units = [kubo(), unit("a", hp=0)]
    e = enemy("e", pos=(30.0, 2.5))
    assert target_of(e, units) == KUBO_ID


def test_aswang_skips_down_units() -> None:
    units = [
        kubo((55.0, 35.0)),
        unit("dead", pos=(45.0, 10.0), hp=0),
        unit("live", pos=(5.0, 35.0)),
    ]
    e = enemy("e", pos=(50.0, 2.5))
    assert target_of(e, units) == "live"


def test_tikbalang_targets_nearest_unit_including_kubo() -> None:
    e = enemy("t", EnemyType.TIKBALANG, pos=(30.0, 10.0))
    units = [kubo((30.0, 14.0)), unit("a", pos=(30.0, 30.0))]
    assert target_of(e, units) == KUBO_ID
    units = [kubo((30.0, 30.0)), unit("a", pos=(30.0, 16.0))]
    assert target_of(e, units) == "a"


def test_tikbalang_tie_goes_to_unit_order() -> None:
    e = enemy("t", EnemyType.TIKBALANG, pos=(30.0, 10.0))
    units = [
        kubo((55.0, 35.0)),
        unit("a", pos=(26.0, 20.0)),
        unit("b", pos=(34.0, 20.0)),
    ]
    assert target_of(e, units) == "a"


def test_kapre_targets_kubo_only() -> None:
    e = enemy("k", EnemyType.KAPRE, pos=(30.0, 10.0))
    units = [kubo((50.0, 35.0)), unit("a", pos=(30.0, 12.0))]
    assert target_of(e, units) == KUBO_ID
    assert target_of(e, [kubo(hp=0), unit("a")]) is None


def test_manananggal_upper_kubo_else_nearest() -> None:
    e = enemy("m", EnemyType.MANANANGGAL, pos=(30.0, 10.0), part=UPPER)
    units = [kubo((50.0, 35.0)), unit("a", pos=(30.0, 12.0))]
    assert target_of(e, units) == KUBO_ID
    units = [kubo(hp=0), unit("far", pos=(5.0, 35.0)), unit("near", pos=(30.0, 14.0))]
    assert target_of(e, units) == "near"


def test_manananggal_lower_has_no_target() -> None:
    e = enemy("m", EnemyType.MANANANGGAL, pos=(30.0, 10.0), part=LOWER)
    assert target_of(e, [kubo(), unit("a")]) is None


def test_duwende_nearest_charm_else_lowest_hp_non_kubo() -> None:
    e = enemy("d", EnemyType.DUWENDE, pos=(30.0, 10.0))
    units = [
        kubo((30.0, 12.0)),
        unit("f", pos=(30.0, 14.0), hp=1),
        unit("c_far", UnitClass.CHARM, (5.0, 35.0)),
        unit("c_near", UnitClass.CHARM, (40.0, 30.0)),
    ]
    assert target_of(e, units) == "c_near"
    no_charm = [
        kubo((30.0, 12.0)),
        unit("f1", pos=(30.0, 14.0), hp=4),
        unit("f2", pos=(5.0, 35.0), hp=2),
    ]
    assert target_of(e, no_charm) == "f2"
    dead_charm = [
        kubo(),
        unit("c", UnitClass.CHARM, (40.0, 30.0), hp=0),
        unit("f", pos=(30.0, 14.0)),
    ]
    assert target_of(e, dead_charm) == "f"
    assert target_of(e, [kubo()]) is None


def test_move_full_distance_when_far() -> None:
    e = enemy("e", pos=(2.5, 20.0))
    state = board([kubo((55.0, 20.0))], [e])
    kubo_hull = state.units[0].hull
    assert move_toward(e, kubo_hull, state) == pytest.approx((17.5, 20.0))


def test_move_stops_when_in_range_without_tolerance() -> None:
    e = enemy("e", pos=(2.5, 20.0))
    state = board([kubo((20.0, 20.0))], [e])
    spot = move_toward(e, state.units[0].hull, state)
    assert spot[0] == pytest.approx(11.5, abs=1e-6)
    assert hull_point_distance(state.units[0].hull, spot) <= 5.0
    assert hull_point_distance(state.units[0].hull, spot) == pytest.approx(
        5.0, abs=1e-6
    )


def test_move_does_not_move_when_already_in_range() -> None:
    e = enemy("e", pos=(14.0, 20.0))
    state = board([kubo((20.0, 20.0))], [e])
    assert move_toward(e, state.units[0].hull, state) == (14.0, 20.0)


def test_move_zero_for_immobile_enemy() -> None:
    e = enemy("m", EnemyType.MANANANGGAL, pos=(10.0, 10.0), part=LOWER)
    state = board([kubo()], [e])
    assert move_toward(e, state.units[0].hull, state) == (10.0, 10.0)


def test_move_is_capped_by_move_distance_when_range_not_reached() -> None:
    e = enemy("k", EnemyType.KAPRE, pos=(2.5, 20.0))
    state = board([kubo((55.0, 20.0))], [e])
    assert move_toward(e, state.units[0].hull, state) == pytest.approx((7.5, 20.0))


def test_move_blocked_by_wall_at_first_contact() -> None:
    wall = unit("w", UnitClass.WALL, (10.0, 20.0))
    e = enemy("e", pos=(2.5, 20.0))
    state = board([kubo((55.0, 20.0)), wall], [e])
    spot = move_toward(e, state.units[0].hull, state)
    assert spot[0] == pytest.approx(6.5, abs=1e-6)
    assert hull_point_distance(wall.hull, spot) == pytest.approx(0.0, abs=1e-6)
    assert hull_point_distance(wall.hull, spot) > 0.0


def test_down_wall_does_not_block() -> None:
    wall = unit("w", UnitClass.WALL, (10.0, 20.0), hp=0)
    e = enemy("e", pos=(2.5, 20.0))
    state = board([kubo((55.0, 20.0)), wall], [e])
    assert move_toward(e, state.units[0].hull, state) == pytest.approx((17.5, 20.0))


def test_flying_enemy_passes_over_wall() -> None:
    wall = unit("w", UnitClass.WALL, (10.0, 20.0))
    e = enemy("m", EnemyType.MANANANGGAL, pos=(2.5, 20.0), part=UPPER)
    state = board([kubo((55.0, 20.0)), wall], [e])
    assert move_toward(e, state.units[0].hull, state) == pytest.approx((22.5, 20.0))


def test_enemy_starting_in_contact_with_wall_can_leave() -> None:
    wall = unit("w", UnitClass.WALL, (10.0, 20.0))
    e = enemy("e", pos=(7.0, 20.0))
    state = board([kubo((55.0, 20.0)), wall], [e])
    assert move_toward(e, state.units[0].hull, state)[0] == pytest.approx(22.0)


def test_non_wall_units_do_not_block() -> None:
    other = unit("f", pos=(10.0, 20.0))
    e = enemy("e", pos=(2.5, 20.0))
    state = board([kubo((55.0, 20.0)), other], [e])
    assert move_toward(e, state.units[0].hull, state) == pytest.approx((17.5, 20.0))


def test_move_stops_at_aura_boundary() -> None:
    charm = unit("c", UnitClass.CHARM, (30.0, 20.0), power=PowerId.P07)
    e = enemy("e", pos=(10.0, 20.0))
    state = board([kubo((55.0, 20.0)), charm], [e])
    spot = move_toward(e, state.units[0].hull, state)
    assert spot[0] == pytest.approx(18.5, abs=1e-6)
    assert hull_point_distance(charm.hull, spot) >= 8.0


def test_other_charm_powers_make_no_aura() -> None:
    charm = unit("c", UnitClass.CHARM, (30.0, 20.0), power=PowerId.P06)
    e = enemy("e", pos=(10.0, 20.0))
    state = board([kubo((55.0, 20.0)), charm], [e])
    assert move_toward(e, state.units[0].hull, state)[0] == pytest.approx(25.0)


def test_down_charm_has_no_aura() -> None:
    charm = unit("c", UnitClass.CHARM, (30.0, 20.0), power=PowerId.P07, hp=0)
    e = enemy("e", pos=(10.0, 20.0))
    state = board([kubo((55.0, 20.0)), charm], [e])
    assert move_toward(e, state.units[0].hull, state)[0] == pytest.approx(25.0)


def test_flying_enemy_still_respects_aura() -> None:
    charm = unit("c", UnitClass.CHARM, (30.0, 20.0), power=PowerId.P07)
    e = enemy("m", EnemyType.MANANANGGAL, pos=(10.0, 20.0), part=UPPER)
    state = board([kubo((55.0, 20.0)), charm], [e])
    assert move_toward(e, state.units[0].hull, state)[0] == pytest.approx(
        18.5, abs=1e-6
    )


def test_enemy_starting_inside_aura_ignores_that_aura() -> None:
    charm = unit("c", UnitClass.CHARM, (12.0, 20.0), power=PowerId.P07)
    e = enemy("e", pos=(10.0, 20.0))
    state = board([kubo((55.0, 20.0)), charm], [e])
    assert move_toward(e, state.units[0].hull, state)[0] == pytest.approx(25.0)


def test_move_clamped_inside_play_area() -> None:
    e = enemy("t", EnemyType.TIKBALANG, pos=(55.0, 20.0))
    state = board([kubo()], [e])
    spot = move_toward(e, (70.0, 20.0), state)
    assert spot == (W, 20.0)


def test_move_toward_point_target_stops_in_range() -> None:
    e = enemy("e", pos=(10.0, 20.0))
    state = board([kubo()], [e])
    spot = move_toward(e, (30.0, 20.0), state)
    assert spot[0] == pytest.approx(23.0, abs=1e-6)


def test_move_toward_same_spot_stays() -> None:
    e = enemy("e", pos=(10.0, 20.0))
    state = board([kubo()], [e])
    assert move_toward(e, (10.0, 20.0), state) == (10.0, 20.0)


def test_hull_target_with_offset_hull() -> None:
    big = unit("big", pos=(25.0, 20.0), hull_offsets=square_hull((0.0, 0.0), 5.0))
    e = enemy("e", pos=(2.5, 20.0))
    state = board([kubo((55.0, 35.0)), big], [e])
    spot = move_toward(e, big.hull, state)
    assert hull_point_distance(big.hull, spot) == pytest.approx(5.0, abs=1e-6)

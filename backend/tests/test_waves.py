import pytest

from rules.enemies import EnemyType, Part
from rules.geometry import FOREST_EDGE_CM, Edge
from rules.units import Difficulty
from rules.waves import Spawn, edge_position, farthest_edge, spawns_for

W = 60.0
H = 40.0
KUBO = (30.0, 20.0)
NONE: frozenset[str] = frozenset()
A = EnemyType.ASWANG
T = EnemyType.TIKBALANG
K = EnemyType.KAPRE
D = EnemyType.DUWENDE
M = EnemyType.MANANANGGAL
N = Edge.NORTH
E = Edge.EAST
S = Edge.SOUTH
WE = Edge.WEST


def summary(spawns: tuple[Spawn, ...]) -> list[tuple[EnemyType, Edge]]:
    return [(s.type, s.edge) for s in spawns]


def wave(
    turn: int,
    difficulty: Difficulty = Difficulty.NORMAL,
    players: int = 2,
    flags: frozenset[str] = NONE,
    kubo: tuple[float, float] = KUBO,
) -> tuple[Spawn, ...]:
    return spawns_for(turn, difficulty, players, flags, kubo, W, H)


def test_turn_1() -> None:
    assert summary(wave(1)) == [(A, N)]


def test_turn_2_and_tabi_tabi() -> None:
    assert summary(wave(2)) == [(A, E), (D, WE)]
    assert summary(wave(2, flags=frozenset({"tabi_tabi"}))) == [(A, E)]


def test_tabi_tabi_only_affects_turn_2_duwende() -> None:
    flags = frozenset({"tabi_tabi"})
    assert summary(wave(7, flags=flags)) == [(T, N), (D, E), (A, S)]


def test_turn_3() -> None:
    assert summary(wave(3)) == [(T, S), (A, N)]


def test_turn_4_kapre_goes_to_farthest_edge() -> None:
    assert summary(wave(4)) == [(K, E)]
    assert summary(wave(4, kubo=(50.0, 20.0))) == [(K, WE)]
    assert summary(wave(4, kubo=(30.0, 5.0))) == [(K, S)]
    assert summary(wave(4, kubo=(30.0, 35.0))) == [(K, N)]


def test_turn_5() -> None:
    assert summary(wave(5)) == [(A, N), (A, S)]


def test_turn_6_manananggal_pair() -> None:
    spawns = wave(6, kubo=(10.0, 20.0))
    assert [(s.type, s.part, s.edge) for s in spawns] == [
        (M, Part.LOWER, E),
        (M, Part.UPPER, E),
    ]
    lower, upper = spawns
    assert upper.position[0] == lower.position[0]
    assert upper.position[1] - lower.position[1] == 5.0


def test_turn_7() -> None:
    assert summary(wave(7)) == [(T, N), (D, E), (A, S)]


def test_turn_8() -> None:
    assert summary(wave(8)) == [(A, N), (A, S)]


@pytest.mark.parametrize("turn", [0, 9, -1])
def test_no_wave_outside_night(turn: int) -> None:
    assert wave(turn) == ()


@pytest.mark.parametrize("turn", range(1, 9))
def test_one_player_uses_two_player_table(turn: int) -> None:
    assert wave(turn, players=1) == wave(turn, players=2)


@pytest.mark.parametrize("players", [3, 4])
def test_many_players_add_aswang_on_turns_3_and_6(players: int) -> None:
    base3 = summary(wave(3))
    assert summary(wave(3, players=players)) == [*base3, (A, E)]
    assert len(wave(6, players=players)) == 3
    assert wave(6, players=players)[-1].type is A
    for turn in (1, 2, 4, 5, 7, 8):
        assert wave(turn, players=players) == wave(turn)


def test_mahirap_adds_aswang_on_turns_3_5_7() -> None:
    for turn in (3, 5, 7):
        normal = wave(turn)
        hard = wave(turn, Difficulty.MAHIRAP)
        assert len(hard) == len(normal) + 1
        assert hard[-1].type is A
    for turn in (1, 2, 4, 6, 8):
        assert wave(turn, Difficulty.MAHIRAP) == wave(turn)


def test_mahirap_with_many_players_stacks_on_turn_3() -> None:
    spawns = wave(3, Difficulty.MAHIRAP, players=4)
    assert len(spawns) == 4
    assert [s.edge for s in spawns[-2:]] == [E, E]
    assert spawns[-1].position[1] - spawns[-2].position[1] == 5.0


def test_madali_matches_normal_wave() -> None:
    for turn in range(1, 9):
        assert wave(turn, Difficulty.MADALI) == wave(turn)


def test_farthest_edge_ties_follow_edge_order() -> None:
    assert farthest_edge((30.0, 20.0), W, H) == E
    assert farthest_edge((30.0, 5.0), W, H) == S
    assert farthest_edge((5.0, 20.0), W, H) == E
    assert farthest_edge((30.0, 35.0), W, H) == N


def test_edge_positions_inset_half_forest_edge() -> None:
    inset = FOREST_EDGE_CM / 2
    assert edge_position(N, 0, W, H) == (30.0, inset)
    assert edge_position(S, 0, W, H) == (30.0, H - inset)
    assert edge_position(E, 0, W, H) == (W - inset, 20.0)
    assert edge_position(WE, 0, W, H) == (inset, 20.0)


def test_extra_enemy_on_same_edge_offsets_five_cm() -> None:
    assert edge_position(N, 1, W, H) == (35.0, 2.5)
    assert edge_position(E, 2, W, H) == (57.5, 30.0)


def test_spawns_are_deterministic() -> None:
    assert wave(6, Difficulty.MAHIRAP, 4) == wave(6, Difficulty.MAHIRAP, 4)

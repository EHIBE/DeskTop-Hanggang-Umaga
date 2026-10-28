from collections.abc import Collection
from dataclasses import dataclass
from typing import Final

from rules.enemies import EnemyType, Part
from rules.geometry import FOREST_EDGE_CM, Edge, Point
from rules.units import Difficulty

TABI_TABI_FLAG: Final = "tabi_tabi"
EXTRA_PLAYERS_MIN: Final = 3
SPAWN_OFFSET_CM: Final = 5.0
EDGE_ORDER: Final = (Edge.NORTH, Edge.EAST, Edge.SOUTH, Edge.WEST)
EXTRA_ASWANG_TURNS_MANY_PLAYERS: Final = frozenset({3, 6})
EXTRA_ASWANG_TURNS_MAHIRAP: Final = frozenset({3, 5, 7})

A = EnemyType.ASWANG
T = EnemyType.TIKBALANG
K = EnemyType.KAPRE
D = EnemyType.DUWENDE
M = EnemyType.MANANANGGAL

_BASE_TABLE: Final[dict[int, tuple[tuple[EnemyType, Edge | None], ...]]] = {
    1: ((A, Edge.NORTH),),
    2: ((A, Edge.EAST), (D, Edge.WEST)),
    3: ((T, Edge.SOUTH), (A, Edge.NORTH)),
    4: ((K, None),),
    5: ((A, Edge.NORTH), (A, Edge.SOUTH)),
    6: ((M, None),),
    7: ((T, Edge.NORTH), (D, Edge.EAST), (A, Edge.SOUTH)),
    8: ((A, Edge.NORTH), (A, Edge.SOUTH)),
}


@dataclass(frozen=True)
class Spawn:
    type: EnemyType
    part: Part | None
    edge: Edge
    position: Point


def farthest_edge(kubo_position: Point, play_w_cm: float, play_h_cm: float) -> Edge:
    x, y = kubo_position
    distances = {
        Edge.NORTH: y,
        Edge.EAST: play_w_cm - x,
        Edge.SOUTH: play_h_cm - y,
        Edge.WEST: x,
    }
    return max(EDGE_ORDER, key=lambda edge: (distances[edge], -EDGE_ORDER.index(edge)))


def edge_position(edge: Edge, slot: int, play_w_cm: float, play_h_cm: float) -> Point:
    inset = FOREST_EDGE_CM / 2.0
    shift = SPAWN_OFFSET_CM * slot
    if edge is Edge.NORTH:
        return (play_w_cm / 2.0 + shift, inset)
    if edge is Edge.SOUTH:
        return (play_w_cm / 2.0 + shift, play_h_cm - inset)
    if edge is Edge.EAST:
        return (play_w_cm - inset, play_h_cm / 2.0 + shift)
    return (inset, play_h_cm / 2.0 + shift)


def _extra_aswangs(turn: int, difficulty: Difficulty, players: int) -> int:
    extra = 0
    if players >= EXTRA_PLAYERS_MIN and turn in EXTRA_ASWANG_TURNS_MANY_PLAYERS:
        extra += 1
    if difficulty is Difficulty.MAHIRAP and turn in EXTRA_ASWANG_TURNS_MAHIRAP:
        extra += 1
    return extra


def spawns_for(
    turn: int,
    difficulty: Difficulty,
    players: int,
    flags: Collection[str],
    kubo_position: Point,
    play_w_cm: float,
    play_h_cm: float,
) -> tuple[Spawn, ...]:
    base = _BASE_TABLE.get(turn)
    if base is None:
        return ()
    far = farthest_edge(kubo_position, play_w_cm, play_h_cm)
    used: dict[Edge, int] = {}
    spawns: list[Spawn] = []

    def place(enemy_type: EnemyType, part: Part | None, edge: Edge) -> None:
        slot = used.get(edge, 0)
        used[edge] = slot + 1
        spawns.append(
            Spawn(
                enemy_type,
                part,
                edge,
                edge_position(edge, slot, play_w_cm, play_h_cm),
            )
        )

    for enemy_type, edge in base:
        if enemy_type is D and turn == 2 and TABI_TABI_FLAG in flags:
            continue
        if enemy_type is M:
            place(M, Part.LOWER, far)
            place(M, Part.UPPER, far)
            continue
        place(enemy_type, None, edge or far)
    for _ in range(_extra_aswangs(turn, difficulty, players)):
        place(A, None, far)
    return tuple(spawns)

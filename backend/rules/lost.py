from dataclasses import replace
from typing import Final

from rules.geometry import Point, hull_centroid
from rules.resolve import BoardState, Event, EventType, UnitState

LOST_COPY_KEY: Final = "unit.lost"
FOUND_COPY_KEY: Final = "unit.found"

__all__ = [
    "FOUND_COPY_KEY",
    "LOST_COPY_KEY",
    "centroid_inside",
    "update_lost",
]


def centroid_inside(unit: UnitState, play_w_cm: float, play_h_cm: float) -> bool:
    x, y = _centroid(unit)
    x, y = round(x, 6), round(y, 6)
    return 0.0 <= x <= play_w_cm and 0.0 <= y <= play_h_cm


def _centroid(unit: UnitState) -> Point:
    return hull_centroid(unit.hull)


def _watched(unit: UnitState) -> bool:
    return (
        not unit.is_down
        and unit.stolen_by is None
        and not unit.is_lost
        and unit.out_turns == 0
    )


def update_lost(state: BoardState) -> tuple[BoardState, tuple[Event, ...]]:
    units: list[UnitState] = []
    events: list[Event] = []
    for unit in state.units:
        if not _watched(unit):
            units.append(unit)
            continue
        inside = centroid_inside(unit, state.play_w_cm, state.play_h_cm)
        if not inside and not unit.off_desk:
            units.append(replace(unit, off_desk=True))
            events.append(Event(EventType.LOST, unit.id, pos=unit.position))
        elif inside and unit.off_desk:
            units.append(replace(unit, off_desk=False, start=unit.position))
            events.append(Event(EventType.FOUND, unit.id, pos=unit.position))
        else:
            units.append(unit)
    return replace(state, units=tuple(units)), tuple(events)

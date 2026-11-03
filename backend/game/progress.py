from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from db.store import UnitProgress
from rules.progression import (
    Badge,
    ProgressionError,
    ProgressUnit,
    apply_badge,
    apply_scars,
    cooldown_cut,
)
from rules.units import PowerId

BADGE_LABELS: Final = {Badge.HP: "HP+1", Badge.COOLDOWN: "Cooldown-1"}
SCAR_LIMIT: Final = 8


@dataclass(frozen=True)
class Effective:
    hp_max: int
    cooldown_cut: int


def parse_badges(ids: Sequence[str]) -> tuple[Badge, ...]:
    badges: list[Badge] = []
    for item in ids:
        try:
            badges.append(Badge(item.partition("_")[0]))
        except ValueError:
            continue
    return tuple(badges)


def progress_unit(
    unit_id: str,
    hp_max: int,
    power_id: PowerId,
    is_kubo: bool,
    progress: UnitProgress,
) -> ProgressUnit:
    unit = ProgressUnit(unit_id, hp_max, power_id, is_kubo=is_kubo)
    for badge in parse_badges(progress.badges):
        try:
            unit = apply_badge(unit, badge)
        except ProgressionError:
            continue
    for _ in progress.scars:
        unit = apply_scars([unit], {unit_id})[0]
    return unit


def effective_stats(
    unit_id: str,
    hp_max: int,
    power_id: PowerId,
    is_kubo: bool,
    progress: UnitProgress | None,
) -> Effective:
    if progress is None:
        return Effective(hp_max, 0)
    unit = progress_unit(unit_id, hp_max, power_id, is_kubo, progress)
    return Effective(unit.hp_max, cooldown_cut(unit.badges))


def badge_label(badge: str) -> str:
    try:
        return BADGE_LABELS[Badge(badge)]
    except (ValueError, KeyError):
        return badge


def badge_values(ids: Sequence[str]) -> tuple[str, ...]:
    return tuple(badge.value for badge in parse_badges(ids))


def next_badge_id(existing: Sequence[str], badge: Badge) -> str:
    count = sum(1 for known in parse_badges(existing) if known is badge)
    return badge.value if count == 0 else f"{badge.value}_{count + 1}"

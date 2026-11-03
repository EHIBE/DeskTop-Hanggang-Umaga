from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from rules.resolve import POWER_COOLDOWN
from rules.units import HP_FLOOR, PowerId

MAX_BARRIO_LEVEL: Final = 5
BADGE_HP_BONUS: Final = 1
BADGE_COOLDOWN_CUT: Final = 1
MAX_HP_BADGES: Final = 2
SCAR_HP_PENALTY: Final = 1


class Badge(StrEnum):
    HP = "hp"
    COOLDOWN = "cooldown"


@dataclass(frozen=True)
class ProgressUnit:
    unit_id: str
    hp_max: int
    power_id: PowerId
    badges: tuple[Badge, ...] = ()
    scars: int = 0
    is_kubo: bool = False


@dataclass(frozen=True)
class BadgeOffer:
    unit_id: str
    choices: tuple[Badge, ...]


class ProgressionError(Exception):
    pass


def barrio_level(nights_survived: int) -> int:
    return min(MAX_BARRIO_LEVEL, max(0, nights_survived))


def cooldown_cut(badges: Collection[Badge]) -> int:
    return sum(BADGE_COOLDOWN_CUT for badge in badges if badge is Badge.COOLDOWN)


def badge_choices(unit: ProgressUnit) -> tuple[Badge, ...]:
    choices: list[Badge] = []
    if unit.badges.count(Badge.HP) < MAX_HP_BADGES:
        choices.append(Badge.HP)
    base = POWER_COOLDOWN[unit.power_id]
    if not unit.is_kubo and base - cooldown_cut(unit.badges) > 0:
        choices.append(Badge.COOLDOWN)
    return tuple(choices)


def offer_badges(
    units: Sequence[ProgressUnit],
    surviving_ids: Collection[str],
    nights_survived: int,
) -> tuple[BadgeOffer, ...]:
    if nights_survived < 1 or nights_survived > MAX_BARRIO_LEVEL:
        return ()
    offers: list[BadgeOffer] = []
    for unit in units:
        if unit.unit_id not in surviving_ids:
            continue
        choices = badge_choices(unit)
        if choices:
            offers.append(BadgeOffer(unit.unit_id, choices))
    return tuple(offers)


def apply_badge(unit: ProgressUnit, badge: Badge) -> ProgressUnit:
    if badge not in badge_choices(unit):
        raise ProgressionError(f"badge {badge.value} not available")
    hp_max = unit.hp_max + BADGE_HP_BONUS if badge is Badge.HP else unit.hp_max
    return replace(unit, hp_max=hp_max, badges=(*unit.badges, badge))


def apply_scars(
    units: Sequence[ProgressUnit], downed_ids: Collection[str]
) -> tuple[ProgressUnit, ...]:
    return tuple(
        replace(
            unit,
            hp_max=max(HP_FLOOR, unit.hp_max - SCAR_HP_PENALTY),
            scars=unit.scars + 1,
        )
        if unit.unit_id in downed_ids
        else unit
        for unit in units
    )

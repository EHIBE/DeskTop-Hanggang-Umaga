from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class Difficulty(StrEnum):
    MADALI = "madali"
    NORMAL = "normal"
    MAHIRAP = "mahirap"


class UnitClass(StrEnum):
    KUBO = "kubo"
    CHARM = "charm"
    HEALER = "healer"
    FIGHTER = "fighter"
    REACH = "reach"
    RANGED = "ranged"
    SCOUT = "scout"
    WALL = "wall"


class MoveClass(StrEnum):
    NONE = "none"
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class RangeClass(StrEnum):
    NONE = "none"
    MELEE = "melee"
    REACH = "reach"
    FAR = "far"


class PowerId(StrEnum):
    NONE = "none"
    P01 = "P01"
    P02 = "P02"
    P03 = "P03"
    P04 = "P04"
    P05 = "P05"
    P06 = "P06"
    P07 = "P07"
    P08 = "P08"
    P09 = "P09"
    P10 = "P10"
    P11 = "P11"
    P12 = "P12"


MOVE_CM: Final[Mapping[MoveClass, float]] = {
    MoveClass.NONE: 0.0,
    MoveClass.SHORT: 8.0,
    MoveClass.MEDIUM: 12.0,
    MoveClass.LONG: 16.0,
}

RANGE_CM: Final[Mapping[RangeClass, float]] = {
    RangeClass.NONE: 0.0,
    RangeClass.MELEE: 5.0,
    RangeClass.REACH: 9.0,
    RangeClass.FAR: 15.0,
}

MAX_OBJECTS: Final = 12
MAX_CHARMS: Final = 2
MAX_WALLS: Final = 2
MIN_OTHER_UNITS: Final = 2
KUBO_SAM_ID: Final = 1
LAST_UNIT_SAM_ID: Final = 12
ATK_CAP: Final = 3
HP_FLOOR: Final = 1
ATK_FLOOR: Final = 0
REROLLS_PER_UNIT: Final = 1
DELTA_MIN: Final = -1
DELTA_MAX: Final = 1

KUBO_HP: Final[Mapping[Difficulty, int]] = {
    Difficulty.MADALI: 12,
    Difficulty.NORMAL: 10,
    Difficulty.MAHIRAP: 8,
}


@dataclass(frozen=True)
class ClassTemplate:
    hp: int
    atk: int
    move: MoveClass
    range: RangeClass
    powers: tuple[PowerId, ...]


CLASS_TEMPLATES: Final[Mapping[UnitClass, ClassTemplate]] = {
    UnitClass.KUBO: ClassTemplate(
        10, 0, MoveClass.NONE, RangeClass.NONE, (PowerId.NONE,)
    ),
    UnitClass.CHARM: ClassTemplate(
        3,
        0,
        MoveClass.NONE,
        RangeClass.NONE,
        (PowerId.P06, PowerId.P07, PowerId.P08, PowerId.P12),
    ),
    UnitClass.HEALER: ClassTemplate(
        4, 1, MoveClass.SHORT, RangeClass.MELEE, (PowerId.P01, PowerId.P02)
    ),
    UnitClass.FIGHTER: ClassTemplate(
        6,
        2,
        MoveClass.MEDIUM,
        RangeClass.MELEE,
        (PowerId.P03, PowerId.P05, PowerId.P11),
    ),
    UnitClass.REACH: ClassTemplate(
        4, 2, MoveClass.MEDIUM, RangeClass.REACH, (PowerId.P04, PowerId.P09)
    ),
    UnitClass.RANGED: ClassTemplate(
        3,
        1,
        MoveClass.MEDIUM,
        RangeClass.FAR,
        (PowerId.P04, PowerId.P10, PowerId.P12),
    ),
    UnitClass.SCOUT: ClassTemplate(
        3, 1, MoveClass.LONG, RangeClass.MELEE, (PowerId.P11, PowerId.P08)
    ),
    UnitClass.WALL: ClassTemplate(
        7, 0, MoveClass.SHORT, RangeClass.NONE, (PowerId.P02, PowerId.P06)
    ),
}


@dataclass(frozen=True)
class CardDraft:
    unit_class: UnitClass
    hp_delta: int
    atk_delta: int
    power_id: PowerId


@dataclass(frozen=True)
class ClampedCard:
    unit_class: UnitClass
    hp_max: int
    atk: int
    move: MoveClass
    range: RangeClass
    power_id: PowerId
    hp_delta: int
    atk_delta: int


class RosterError(Exception):
    def __init__(self, copy_key: str) -> None:
        super().__init__(copy_key)
        self.copy_key = copy_key


def _limit_delta(delta: int) -> int:
    return min(DELTA_MAX, max(DELTA_MIN, delta))


def _resolve_class(draft_class: UnitClass, roster: Sequence[UnitClass]) -> UnitClass:
    if not roster:
        return UnitClass.KUBO
    unit_class = UnitClass.FIGHTER if draft_class is UnitClass.KUBO else draft_class
    if unit_class is UnitClass.CHARM and roster.count(UnitClass.CHARM) >= MAX_CHARMS:
        return UnitClass.FIGHTER
    if unit_class is UnitClass.WALL and roster.count(UnitClass.WALL) >= MAX_WALLS:
        return UnitClass.FIGHTER
    return unit_class


def _balance_deltas(hp_delta: int, atk_delta: int) -> tuple[int, int]:
    if hp_delta + atk_delta <= 0:
        return hp_delta, atk_delta
    if hp_delta == DELTA_MAX and atk_delta == DELTA_MAX:
        return hp_delta, -1
    if hp_delta == DELTA_MAX:
        return 0, atk_delta
    return hp_delta, 0


def clamp_card(
    draft: CardDraft, roster: Sequence[UnitClass], difficulty: Difficulty
) -> ClampedCard:
    unit_class = _resolve_class(draft.unit_class, roster)
    template = CLASS_TEMPLATES[unit_class]
    if unit_class is UnitClass.KUBO:
        hp_delta, atk_delta = 0, 0
        base_hp = KUBO_HP[difficulty]
    else:
        hp_delta, atk_delta = _balance_deltas(
            _limit_delta(draft.hp_delta), _limit_delta(draft.atk_delta)
        )
        base_hp = template.hp
    power_id = (
        draft.power_id if draft.power_id in template.powers else template.powers[0]
    )
    return ClampedCard(
        unit_class=unit_class,
        hp_max=max(HP_FLOOR, base_hp + hp_delta),
        atk=min(ATK_CAP, max(ATK_FLOOR, template.atk + atk_delta)),
        move=template.move,
        range=template.range,
        power_id=power_id,
        hp_delta=hp_delta,
        atk_delta=atk_delta,
    )


def default_card(
    unit_class: UnitClass, roster: Sequence[UnitClass], difficulty: Difficulty
) -> ClampedCard:
    first_power = CLASS_TEMPLATES[unit_class].powers[0]
    return clamp_card(CardDraft(unit_class, 0, 0, first_power), roster, difficulty)


def check_can_summon(roster: Sequence[UnitClass]) -> None:
    if len(roster) >= MAX_OBJECTS:
        raise RosterError("summon.full")


def can_begin_night(roster: Sequence[UnitClass]) -> bool:
    return (
        len(roster) <= MAX_OBJECTS
        and roster.count(UnitClass.KUBO) == 1
        and roster[0] is UnitClass.KUBO
        and len(roster) - 1 >= MIN_OTHER_UNITS
    )


def begin_night_block_key(roster: Sequence[UnitClass]) -> str | None:
    if can_begin_night(roster):
        return None
    if UnitClass.KUBO not in roster:
        return "summon.kubo_first"
    return "summon.need_units"


def next_sam_id(used: Collection[int]) -> int:
    if KUBO_SAM_ID not in used:
        return KUBO_SAM_ID
    for sam_id in range(KUBO_SAM_ID + 1, LAST_UNIT_SAM_ID + 1):
        if sam_id not in used:
            return sam_id
    raise RosterError("summon.full")


def can_attack(card: ClampedCard) -> bool:
    return card.atk > 0 and card.range is not RangeClass.NONE

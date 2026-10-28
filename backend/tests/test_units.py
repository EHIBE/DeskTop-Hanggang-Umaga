import pytest

from rules.units import (
    ATK_CAP,
    CLASS_TEMPLATES,
    KUBO_HP,
    MOVE_CM,
    RANGE_CM,
    CardDraft,
    ClampedCard,
    Difficulty,
    MoveClass,
    PowerId,
    RangeClass,
    RosterError,
    UnitClass,
    begin_night_block_key,
    can_attack,
    can_begin_night,
    check_can_summon,
    clamp_card,
    default_card,
    next_sam_id,
)

K = UnitClass.KUBO
F = UnitClass.FIGHTER
ROSTER = [K, F]


def draft(
    unit_class: UnitClass = F,
    hp_delta: int = 0,
    atk_delta: int = 0,
    power: PowerId = PowerId.P03,
) -> CardDraft:
    return CardDraft(unit_class, hp_delta, atk_delta, power)


TEMPLATE_ROWS = [
    (UnitClass.KUBO, 10, 0, MoveClass.NONE, RangeClass.NONE, (PowerId.NONE,)),
    (
        UnitClass.CHARM,
        3,
        0,
        MoveClass.NONE,
        RangeClass.NONE,
        (PowerId.P06, PowerId.P07, PowerId.P08, PowerId.P12),
    ),
    (
        UnitClass.HEALER,
        4,
        1,
        MoveClass.SHORT,
        RangeClass.MELEE,
        (PowerId.P01, PowerId.P02),
    ),
    (
        UnitClass.FIGHTER,
        6,
        2,
        MoveClass.MEDIUM,
        RangeClass.MELEE,
        (PowerId.P03, PowerId.P05, PowerId.P11),
    ),
    (
        UnitClass.REACH,
        4,
        2,
        MoveClass.MEDIUM,
        RangeClass.REACH,
        (PowerId.P04, PowerId.P09),
    ),
    (
        UnitClass.RANGED,
        3,
        1,
        MoveClass.MEDIUM,
        RangeClass.FAR,
        (PowerId.P04, PowerId.P10, PowerId.P12),
    ),
    (
        UnitClass.SCOUT,
        3,
        1,
        MoveClass.LONG,
        RangeClass.MELEE,
        (PowerId.P08, PowerId.P11),
    ),
    (
        UnitClass.WALL,
        7,
        0,
        MoveClass.SHORT,
        RangeClass.NONE,
        (PowerId.P02, PowerId.P06),
    ),
]


@pytest.mark.parametrize(("cls", "hp", "atk", "move", "rng", "powers"), TEMPLATE_ROWS)
def test_class_template(
    cls: UnitClass,
    hp: int,
    atk: int,
    move: MoveClass,
    rng: RangeClass,
    powers: tuple[PowerId, ...],
) -> None:
    t = CLASS_TEMPLATES[cls]
    assert (t.hp, t.atk, t.move, t.range, t.powers) == (hp, atk, move, rng, powers)


def test_every_class_has_a_template() -> None:
    assert set(CLASS_TEMPLATES) == set(UnitClass)


def test_distance_tables() -> None:
    assert dict(MOVE_CM) == {
        MoveClass.NONE: 0,
        MoveClass.SHORT: 8,
        MoveClass.MEDIUM: 12,
        MoveClass.LONG: 16,
    }
    assert dict(RANGE_CM) == {
        RangeClass.NONE: 0,
        RangeClass.MELEE: 5,
        RangeClass.REACH: 9,
        RangeClass.FAR: 15,
    }


def test_fr10_both_plus_one_becomes_atk_minus_one() -> None:
    card = clamp_card(draft(F, 1, 1), ROSTER, Difficulty.NORMAL)
    assert card.atk_delta == -1
    assert card.hp_delta == 1
    assert card.hp_delta + card.atk_delta == 0
    assert card.hp_max == 7
    assert card.atk == 1


def test_only_hp_plus_one_resets_hp_delta() -> None:
    card = clamp_card(draft(F, 1, 0), ROSTER, Difficulty.NORMAL)
    assert (card.hp_delta, card.atk_delta) == (0, 0)
    assert card.hp_max == 6


def test_hp_plus_one_with_atk_minus_one_is_allowed() -> None:
    card = clamp_card(draft(F, 1, -1), ROSTER, Difficulty.NORMAL)
    assert (card.hp_delta, card.atk_delta) == (1, -1)


def test_only_atk_plus_one_resets_atk_delta() -> None:
    card = clamp_card(draft(F, 0, 1), ROSTER, Difficulty.NORMAL)
    assert (card.hp_delta, card.atk_delta) == (0, 0)
    assert card.atk == 2


def test_atk_plus_one_with_hp_minus_one_is_allowed() -> None:
    card = clamp_card(draft(F, -1, 1), ROSTER, Difficulty.NORMAL)
    assert (card.hp_delta, card.atk_delta) == (-1, 1)
    assert (card.hp_max, card.atk) == (5, 3)


def test_negative_sum_untouched() -> None:
    card = clamp_card(draft(F, -1, -1), ROSTER, Difficulty.NORMAL)
    assert (card.hp_delta, card.atk_delta) == (-1, -1)
    assert (card.hp_max, card.atk) == (5, 1)


def test_out_of_range_deltas_limited() -> None:
    card = clamp_card(draft(F, 5, -7), ROSTER, Difficulty.NORMAL)
    assert (card.hp_delta, card.atk_delta) == (1, -1)
    both = clamp_card(draft(F, 9, 9), ROSTER, Difficulty.NORMAL)
    assert (both.hp_delta, both.atk_delta) == (1, -1)
    low = clamp_card(draft(F, -9, -9), ROSTER, Difficulty.NORMAL)
    assert (low.hp_delta, low.atk_delta) == (-1, -1)


def test_first_summon_is_kubo() -> None:
    card = clamp_card(draft(UnitClass.HEALER, 1, 1, PowerId.P01), [], Difficulty.NORMAL)
    assert card.unit_class is K
    assert (card.hp_delta, card.atk_delta) == (0, 0)
    assert card.power_id is PowerId.NONE
    assert card.atk == 0
    assert card.move is MoveClass.NONE
    assert card.range is RangeClass.NONE


@pytest.mark.parametrize("difficulty", list(Difficulty))
def test_kubo_hp_per_difficulty(difficulty: Difficulty) -> None:
    card = clamp_card(draft(K, 1, 1, PowerId.NONE), [], difficulty)
    assert card.hp_max == KUBO_HP[difficulty]
    assert {
        Difficulty.MADALI: 12,
        Difficulty.NORMAL: 10,
        Difficulty.MAHIRAP: 8,
    }[difficulty] == card.hp_max


def test_later_kubo_becomes_fighter() -> None:
    card = clamp_card(draft(K, 0, 0, PowerId.NONE), ROSTER, Difficulty.NORMAL)
    assert card.unit_class is F
    assert card.power_id is PowerId.P03
    assert card.hp_max == 6


def test_charm_cap_converts_to_fighter() -> None:
    charm = UnitClass.CHARM
    under = clamp_card(draft(charm, 0, 0, PowerId.P06), [K, charm], Difficulty.NORMAL)
    assert under.unit_class is charm
    over = clamp_card(
        draft(charm, 0, 0, PowerId.P06), [K, charm, charm], Difficulty.NORMAL
    )
    assert over.unit_class is F
    assert over.power_id is PowerId.P03


def test_wall_cap_converts_to_fighter() -> None:
    wall = UnitClass.WALL
    under = clamp_card(draft(wall, 0, 0, PowerId.P02), [K, wall], Difficulty.NORMAL)
    assert under.unit_class is wall
    over = clamp_card(
        draft(wall, 0, 0, PowerId.P02), [K, wall, wall], Difficulty.NORMAL
    )
    assert over.unit_class is F
    assert over.power_id is PowerId.P03


def test_charm_cap_ignores_walls_and_vice_versa() -> None:
    wall = UnitClass.WALL
    charm = UnitClass.CHARM
    assert (
        clamp_card(
            draft(charm, 0, 0, PowerId.P06), [K, wall, wall], Difficulty.NORMAL
        ).unit_class
        is charm
    )
    assert (
        clamp_card(
            draft(wall, 0, 0, PowerId.P02), [K, charm, charm], Difficulty.NORMAL
        ).unit_class
        is wall
    )


@pytest.mark.parametrize(
    ("cls", "powers"), [(row[0], row[5]) for row in TEMPLATE_ROWS[1:]]
)
def test_allowed_power_kept_and_illegal_replaced(
    cls: UnitClass, powers: tuple[PowerId, ...]
) -> None:
    for power in powers:
        kept = clamp_card(draft(cls, 0, 0, power), [K], Difficulty.NORMAL)
        assert kept.power_id is power
    illegal = next(p for p in PowerId if p not in powers)
    replaced = clamp_card(draft(cls, 0, 0, illegal), [K], Difficulty.NORMAL)
    assert replaced.power_id is powers[0]


def test_hp_floor() -> None:
    card = clamp_card(
        draft(UnitClass.RANGED, -1, 0, PowerId.P10), [K], Difficulty.NORMAL
    )
    assert card.hp_max == 2
    assert card.hp_max >= 1


def test_atk_floor_and_cap() -> None:
    floor = clamp_card(
        draft(UnitClass.WALL, 0, -1, PowerId.P02), [K], Difficulty.NORMAL
    )
    assert floor.atk == 0
    capped = clamp_card(
        draft(UnitClass.REACH, -1, 1, PowerId.P04), [K], Difficulty.NORMAL
    )
    assert capped.atk == ATK_CAP
    assert capped.atk <= ATK_CAP


def test_move_and_range_from_template() -> None:
    card = clamp_card(draft(UnitClass.SCOUT, 0, 0, PowerId.P08), [K], Difficulty.NORMAL)
    assert card.move is MoveClass.LONG
    assert card.range is RangeClass.MELEE


@pytest.mark.parametrize("cls", list(UnitClass))
def test_default_card_matches_clamp(cls: UnitClass) -> None:
    for roster in ([], ROSTER):
        expected = clamp_card(
            CardDraft(cls, 0, 0, CLASS_TEMPLATES[cls].powers[0]),
            roster,
            Difficulty.MAHIRAP,
        )
        assert default_card(cls, roster, Difficulty.MAHIRAP) == expected


def test_default_card_first_summon_is_kubo() -> None:
    card = default_card(UnitClass.WALL, [], Difficulty.MADALI)
    assert card.unit_class is K
    assert card.hp_max == 12


def test_check_can_summon() -> None:
    check_can_summon([K] + [F] * 10)
    with pytest.raises(RosterError) as err:
        check_can_summon([K] + [F] * 11)
    assert err.value.copy_key == "summon.full"
    with pytest.raises(RosterError):
        check_can_summon([K] + [F] * 12)


def test_can_begin_night_cases() -> None:
    assert can_begin_night([K, F, F])
    assert can_begin_night([K] + [F] * 11)
    assert not can_begin_night([])
    assert not can_begin_night([K])
    assert not can_begin_night([K, F])
    assert not can_begin_night([F, K, F])
    assert not can_begin_night([F, F, F])
    assert not can_begin_night([K, K, F, F])
    assert not can_begin_night([K] + [F] * 12)


def test_begin_night_block_key() -> None:
    assert begin_night_block_key([K, F, F]) is None
    assert begin_night_block_key([]) == "summon.kubo_first"
    assert begin_night_block_key([F, F, F]) == "summon.kubo_first"
    assert begin_night_block_key([K, F]) == "summon.need_units"
    assert begin_night_block_key([F, K, F]) == "summon.need_units"
    assert begin_night_block_key([K, K, F, F]) == "summon.need_units"
    assert begin_night_block_key([K] + [F] * 12) == "summon.need_units"


def test_next_sam_id_order() -> None:
    assert next_sam_id([]) == 1
    assert next_sam_id({1}) == 2
    assert next_sam_id({1, 2, 3}) == 4
    assert next_sam_id({1, 2, 4}) == 3
    assert next_sam_id({2, 3}) == 1
    assert next_sam_id(set(range(1, 12))) == 12


def test_next_sam_id_exhausted() -> None:
    with pytest.raises(RosterError) as err:
        next_sam_id(set(range(1, 13)))
    assert err.value.copy_key == "summon.full"


def make_card(cls: UnitClass) -> ClampedCard:
    return default_card(cls, [K], Difficulty.NORMAL)


def test_can_attack() -> None:
    assert can_attack(make_card(F))
    assert can_attack(make_card(UnitClass.RANGED))
    assert not can_attack(make_card(UnitClass.CHARM))
    assert not can_attack(make_card(UnitClass.WALL))
    assert not can_attack(default_card(K, [], Difficulty.NORMAL))


def test_deterministic() -> None:
    a = clamp_card(draft(F, 1, 1), ROSTER, Difficulty.MAHIRAP)
    b = clamp_card(draft(F, 1, 1), ROSTER, Difficulty.MAHIRAP)
    assert a == b
    assert hash(a) == hash(b)

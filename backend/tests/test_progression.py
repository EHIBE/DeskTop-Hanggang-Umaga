import pytest

from rules.progression import (
    BADGE_COOLDOWN_CUT,
    BADGE_HP_BONUS,
    MAX_BARRIO_LEVEL,
    MAX_HP_BADGES,
    SCAR_HP_PENALTY,
    Badge,
    BadgeOffer,
    ProgressionError,
    ProgressUnit,
    apply_badge,
    apply_scars,
    badge_choices,
    barrio_level,
    cooldown_cut,
    offer_badges,
)
from rules.resolve import POWER_COOLDOWN
from rules.units import PowerId
from tests.test_resolve import board, enemy, find_unit, kubo, power, run, unit


def pu(
    uid: str = "a",
    power_id: PowerId = PowerId.P03,
    hp_max: int = 6,
    badges: tuple[Badge, ...] = (),
    scars: int = 0,
    is_kubo: bool = False,
) -> ProgressUnit:
    return ProgressUnit(uid, hp_max, power_id, badges, scars, is_kubo)


@pytest.mark.parametrize(
    ("nights", "level"), [(-1, 0), (0, 0), (1, 1), (4, 4), (5, 5), (6, 5), (99, 5)]
)
def test_barrio_level(nights: int, level: int) -> None:
    assert barrio_level(nights) == level
    assert MAX_BARRIO_LEVEL == 5


def test_constants() -> None:
    assert (BADGE_HP_BONUS, BADGE_COOLDOWN_CUT, MAX_HP_BADGES, SCAR_HP_PENALTY) == (
        1,
        1,
        2,
        1,
    )


def test_cooldown_cut_counts_cooldown_badges() -> None:
    assert cooldown_cut(()) == 0
    assert cooldown_cut((Badge.HP, Badge.COOLDOWN)) == 1
    assert cooldown_cut((Badge.COOLDOWN, Badge.COOLDOWN)) == 2


def test_choices_for_power_with_cooldown() -> None:
    assert badge_choices(pu()) == (Badge.HP, Badge.COOLDOWN)


@pytest.mark.parametrize(
    "power_id", [PowerId.P01, PowerId.P07, PowerId.P11, PowerId.NONE]
)
def test_no_cooldown_choice_when_cooldown_is_zero(power_id: PowerId) -> None:
    assert POWER_COOLDOWN[power_id] == 0
    assert badge_choices(pu(power_id=power_id)) == (Badge.HP,)


def test_cooldown_choice_vanishes_when_already_zero() -> None:
    assert badge_choices(pu(badges=(Badge.COOLDOWN,))) == (Badge.HP,)
    assert badge_choices(pu(power_id=PowerId.P04, badges=(Badge.COOLDOWN,))) == (
        Badge.HP,
        Badge.COOLDOWN,
    )


def test_hp_choice_vanishes_at_cap() -> None:
    capped = pu(badges=(Badge.HP, Badge.HP))
    assert badge_choices(capped) == (Badge.COOLDOWN,)


def test_kubo_gets_hp_only() -> None:
    assert badge_choices(pu(power_id=PowerId.NONE, is_kubo=True)) == (Badge.HP,)
    assert badge_choices(pu(power_id=PowerId.P06, is_kubo=True)) == (Badge.HP,)


def test_offers_only_surviving_units() -> None:
    units = [pu("a"), pu("b"), pu("c", power_id=PowerId.P01)]
    offers = offer_badges(units, {"a", "c"}, 1)
    assert offers == (
        BadgeOffer("a", (Badge.HP, Badge.COOLDOWN)),
        BadgeOffer("c", (Badge.HP,)),
    )


@pytest.mark.parametrize("nights", [0, -1, 6])
def test_no_offers_outside_level_range(nights: int) -> None:
    assert offer_badges([pu()], {"a"}, nights) == ()


def test_no_offer_when_nothing_left() -> None:
    full = pu(power_id=PowerId.P01, badges=(Badge.HP, Badge.HP))
    assert offer_badges([full], {"a"}, 2) == ()


def test_apply_hp_badge() -> None:
    new = apply_badge(pu(), Badge.HP)
    assert new.hp_max == 7
    assert new.badges == (Badge.HP,)


def test_apply_cooldown_badge() -> None:
    new = apply_badge(pu(), Badge.COOLDOWN)
    assert new.hp_max == 6
    assert new.badges == (Badge.COOLDOWN,)
    assert cooldown_cut(new.badges) == 1


def test_apply_badge_rejects_unavailable() -> None:
    with pytest.raises(ProgressionError):
        apply_badge(pu(power_id=PowerId.P11), Badge.COOLDOWN)
    with pytest.raises(ProgressionError):
        apply_badge(pu(badges=(Badge.HP, Badge.HP)), Badge.HP)


def test_apply_badge_is_pure() -> None:
    original = pu()
    apply_badge(original, Badge.HP)
    assert original == pu()


def test_scars_hit_only_downed_units() -> None:
    result = apply_scars([pu("a"), pu("b")], {"b"})
    assert result[0] == pu("a")
    assert result[1].hp_max == 5
    assert result[1].scars == 1


def test_scar_floor_is_one_hp() -> None:
    result = apply_scars([pu(hp_max=1, scars=2)], {"a"})
    assert result[0].hp_max == 1
    assert result[0].scars == 3


def test_scars_stack() -> None:
    once = apply_scars([pu()], {"a"})
    twice = apply_scars(once, {"a"})
    assert twice[0].hp_max == 4
    assert twice[0].scars == 2


def test_scar_with_unknown_id_changes_nothing() -> None:
    assert apply_scars([pu()], {"zzz"}) == (pu(),)


def test_badge_values_are_stable_strings() -> None:
    assert Badge("hp") is Badge.HP
    assert Badge("cooldown") is Badge.COOLDOWN


def test_cooldown_badge_shortens_power_cooldown_in_resolve() -> None:
    state = board(
        [
            kubo((55.0, 35.0)),
            unit("f", pos=(10.0, 10.0), power=PowerId.P03, cooldown_cut=1),
            unit("g", pos=(10.0, 30.0), power=PowerId.P03),
        ],
        [enemy("e", pos=(10.0, 14.0)), enemy("e2", pos=(10.0, 34.0))],
    )
    new, _ = run(state, power("f", "e"), power("g", "e2"))
    assert find_unit(new, "f").cooldown == 0
    assert find_unit(new, "g").cooldown == 1


def test_cooldown_cut_never_goes_negative() -> None:
    state = board(
        [
            kubo((55.0, 35.0)),
            unit("f", pos=(10.0, 10.0), power=PowerId.P03, cooldown_cut=5),
        ],
        [enemy("e", pos=(10.0, 14.0))],
    )
    new, _ = run(state, power("f", "e"))
    assert find_unit(new, "f").cooldown == 0

import random
from itertools import product

import pytest

from db.store import UnitProgress
from game.progress import (
    BADGE_LABELS,
    SCAR_LIMIT,
    Effective,
    badge_label,
    badge_values,
    effective_stats,
    next_badge_id,
    parse_badges,
    progress_unit,
)
from rules.progression import (
    MAX_BARRIO_LEVEL,
    MAX_HP_BADGES,
    Badge,
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
from rules.units import HP_FLOOR, PowerId

POWERS = tuple(PowerId)
TOKENS = (
    "hp",
    "hp_2",
    "hp_3",
    "cooldown",
    "cooldown_2",
    "cooldown_9",
    "cd_down",
    "hp_up",
    "",
    "_",
    "bogus",
    "HP",
    "Cooldown",
    "hp_",
    "_hp",
    "badge",
)


def rand_progress(rng: random.Random) -> UnitProgress:
    badges = tuple(rng.choice(TOKENS) for _ in range(rng.randint(0, 8)))
    scars = tuple(f"scar_{i}" for i in range(rng.randint(0, 10)))
    return UnitProgress(badges, scars)


def test_constants() -> None:
    assert BADGE_LABELS == {Badge.HP: "HP+1", Badge.COOLDOWN: "Cooldown-1"}
    assert SCAR_LIMIT == 8


def test_parse_badges_keeps_known_prefixes_only() -> None:
    assert parse_badges(["hp", "hp_2", "cooldown", "cooldown_2"]) == (
        Badge.HP,
        Badge.HP,
        Badge.COOLDOWN,
        Badge.COOLDOWN,
    )
    assert parse_badges(["bogus", "", "cd_down", "HP", "hp_up"]) == (Badge.HP,)
    assert parse_badges([]) == ()


def test_parse_badges_never_raises_and_only_yields_badges() -> None:
    rng = random.Random(1)
    alphabet = "hpcoldwn_2 9-é"
    for _ in range(400):
        ids = [
            "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 9)))
            for _ in range(rng.randint(0, 6))
        ]
        result = parse_badges(ids)
        assert all(isinstance(b, Badge) for b in result)
        assert len(result) <= len(ids)


def test_badge_label_and_values() -> None:
    assert badge_label("hp") == "HP+1"
    assert badge_label("cooldown") == "Cooldown-1"
    assert badge_label("mystery") == "mystery"
    assert badge_label("") == ""
    assert badge_label("hp_2") == "hp_2"
    assert badge_values(["hp_2", "x", "cooldown_3"]) == ("hp", "cooldown")


def test_next_badge_id_numbers_repeats() -> None:
    assert next_badge_id([], Badge.HP) == "hp"
    assert next_badge_id(["hp"], Badge.HP) == "hp_2"
    assert next_badge_id(["hp", "hp_2"], Badge.HP) == "hp_3"
    assert next_badge_id(["hp"], Badge.COOLDOWN) == "cooldown"
    assert next_badge_id(["junk", "hp"], Badge.COOLDOWN) == "cooldown"
    assert next_badge_id(["cooldown"], Badge.COOLDOWN) == "cooldown_2"


def test_next_badge_ids_round_trip_through_parse() -> None:
    rng = random.Random(2)
    for _ in range(100):
        ids: list[str] = []
        picks = [rng.choice(list(Badge)) for _ in range(rng.randint(0, 6))]
        for pick in picks:
            ids.append(next_badge_id(ids, pick))
        assert len(set(ids)) == len(ids)
        assert parse_badges(ids) == tuple(picks)


def test_progress_unit_without_progress_is_the_base_unit() -> None:
    unit = progress_unit("u_a", 6, PowerId.P03, False, UnitProgress((), ()))
    assert unit == ProgressUnit("u_a", 6, PowerId.P03)


def test_progress_unit_applies_badges_then_scars() -> None:
    unit = progress_unit(
        "u_a", 6, PowerId.P03, False, UnitProgress(("hp", "cooldown"), ("s1",))
    )
    assert unit.hp_max == 6
    assert unit.badges == (Badge.HP, Badge.COOLDOWN)
    assert unit.scars == 1


def test_progress_unit_drops_badges_that_were_never_offered() -> None:
    capped = progress_unit(
        "u_a", 6, PowerId.P03, False, UnitProgress(("hp", "hp_2", "hp_3", "hp_4"), ())
    )
    assert capped.badges.count(Badge.HP) == MAX_HP_BADGES
    assert capped.hp_max == 8
    kubo = progress_unit(
        "u_k", 10, PowerId.NONE, True, UnitProgress(("cooldown", "hp"), ())
    )
    assert kubo.badges == (Badge.HP,)
    free = progress_unit(
        "u_h", 4, PowerId.P01, False, UnitProgress(("cooldown", "cooldown_2"), ())
    )
    assert free.badges == ()


def test_progress_unit_scars_floor_at_one_hp() -> None:
    unit = progress_unit(
        "u_a", 3, PowerId.P08, False, UnitProgress((), tuple("sssssssss"))
    )
    assert unit.hp_max == HP_FLOOR
    assert unit.scars == 9


def test_effective_stats_none_progress() -> None:
    assert effective_stats("u_a", 5, PowerId.P03, False, None) == Effective(5, 0)


def test_effective_stats_with_progress() -> None:
    both = UnitProgress(("hp", "cooldown"), ("s",))
    assert effective_stats("u_a", 6, PowerId.P03, False, both) == Effective(6, 1)
    only_hp = UnitProgress(("hp",), ())
    assert effective_stats("u_a", 6, PowerId.P03, False, only_hp) == Effective(7, 0)


def test_effective_stats_properties_over_random_progress() -> None:
    rng = random.Random(3)
    for index in range(600):
        power = rng.choice(POWERS)
        kubo = rng.random() < 0.15
        base = rng.randint(1, 12)
        progress = rand_progress(rng)
        stats = effective_stats(f"u_{index}", base, power, kubo, progress)
        built = progress_unit(f"u_{index}", base, power, kubo, progress)
        assert stats.hp_max == built.hp_max >= HP_FLOOR
        assert stats.hp_max <= base + MAX_HP_BADGES
        assert built.badges.count(Badge.HP) <= MAX_HP_BADGES
        assert 0 <= stats.cooldown_cut <= POWER_COOLDOWN[power]
        if kubo:
            assert stats.cooldown_cut == 0
        hp = base + built.badges.count(Badge.HP)
        for _ in progress.scars:
            hp = max(HP_FLOOR, hp - 1)
        assert stats.hp_max == hp


def test_effective_stats_is_deterministic_and_pure() -> None:
    rng = random.Random(4)
    for _ in range(100):
        progress = rand_progress(rng)
        before = (progress.badges, progress.scars)
        first = effective_stats("u_a", 5, PowerId.P04, False, progress)
        assert first == effective_stats("u_a", 5, PowerId.P04, False, progress)
        assert (progress.badges, progress.scars) == before


@pytest.mark.parametrize(
    ("nights", "level"),
    [(-(10**9), 0), (-1, 0), (0, 0), (1, 1), (5, 5), (6, 5), (10**9, 5)],
)
def test_barrio_level_edges(nights: int, level: int) -> None:
    assert barrio_level(nights) == level


def test_barrio_level_is_always_zero_to_five_and_monotonic() -> None:
    rng = random.Random(6)
    values = sorted(rng.randint(-1000, 1000) for _ in range(500))
    levels = [barrio_level(v) for v in values]
    assert all(0 <= level <= MAX_BARRIO_LEVEL for level in levels)
    assert levels == sorted(levels)
    for nights in range(12):
        assert barrio_level(nights) == min(nights, MAX_BARRIO_LEVEL)


def test_apply_badge_accepts_exactly_the_offered_choices() -> None:
    rng = random.Random(7)
    for _ in range(600):
        power = rng.choice(POWERS)
        unit = ProgressUnit(
            "u_a",
            rng.randint(1, 12),
            power,
            tuple(rng.choice(list(Badge)) for _ in range(rng.randint(0, 5))),
            rng.randint(0, 4),
            rng.random() < 0.2,
        )
        offered = badge_choices(unit)
        for badge in Badge:
            if badge in offered:
                result = apply_badge(unit, badge)
                assert result.badges == (*unit.badges, badge)
                gain = 1 if badge is Badge.HP else 0
                assert result.hp_max == unit.hp_max + gain
                assert result.scars == unit.scars
            else:
                with pytest.raises(ProgressionError):
                    apply_badge(unit, badge)


def test_greedy_badge_chains_respect_every_cap() -> None:
    for power, kubo in product(POWERS, (False, True)):
        for order in (list(Badge), list(reversed(list(Badge)))):
            unit = ProgressUnit("u_a", 5, power, is_kubo=kubo)
            for _ in range(10):
                options = badge_choices(unit)
                if not options:
                    break
                pick = next((b for b in order if b in options), options[0])
                unit = apply_badge(unit, pick)
            assert badge_choices(unit) == ()
            assert unit.badges.count(Badge.HP) == MAX_HP_BADGES
            assert cooldown_cut(unit.badges) <= POWER_COOLDOWN[power]
            if kubo:
                assert Badge.COOLDOWN not in unit.badges
            assert unit.hp_max == 5 + MAX_HP_BADGES


def test_cooldown_never_offered_for_zero_cooldown_powers_or_kubo() -> None:
    for power in POWERS:
        unit = ProgressUnit("u_a", 4, power)
        assert (Badge.COOLDOWN in badge_choices(unit)) == (POWER_COOLDOWN[power] > 0)
        assert Badge.COOLDOWN not in badge_choices(
            ProgressUnit("u_k", 4, power, is_kubo=True)
        )


def test_apply_scars_keeps_hp_at_least_one_and_counts_scars() -> None:
    rng = random.Random(8)
    for _ in range(300):
        units = tuple(
            ProgressUnit(f"u_{i}", rng.randint(1, 9), rng.choice(POWERS))
            for i in range(rng.randint(0, 8))
        )
        downed = {u.unit_id for u in units if rng.random() < 0.5} | {"ghost"}
        result = apply_scars(units, downed)
        assert len(result) == len(units)
        for before, after in zip(units, result, strict=True):
            assert after.hp_max >= HP_FLOOR
            if before.unit_id in downed:
                assert after.scars == before.scars + 1
                assert after.hp_max == max(HP_FLOOR, before.hp_max - 1)
            else:
                assert after == before
        again = apply_scars(result, downed)
        assert all(u.hp_max >= HP_FLOOR for u in again)


def test_apply_scars_repeated_never_drops_below_floor() -> None:
    unit = ProgressUnit("u_a", 2, PowerId.P03)
    for _ in range(20):
        unit = apply_scars([unit], {"u_a"})[0]
        assert unit.hp_max >= HP_FLOOR
    assert unit.scars == 20
    assert unit.hp_max == HP_FLOOR


def test_offer_badges_window_and_survivors() -> None:
    rng = random.Random(9)
    for _ in range(300):
        units = tuple(
            ProgressUnit(
                f"u_{i}",
                rng.randint(1, 9),
                rng.choice(POWERS),
                tuple(rng.choice(list(Badge)) for _ in range(rng.randint(0, 3))),
                is_kubo=rng.random() < 0.1,
            )
            for i in range(rng.randint(0, 8))
        )
        survivors = {u.unit_id for u in units if rng.random() < 0.6}
        for nights in (-3, 0, 1, 3, 5, 6, 40):
            offers = offer_badges(units, survivors, nights)
            if not 1 <= nights <= MAX_BARRIO_LEVEL:
                assert offers == ()
                continue
            by_id = {u.unit_id: u for u in units}
            for offer in offers:
                assert offer.unit_id in survivors
                assert offer.choices
                assert offer.choices == badge_choices(by_id[offer.unit_id])
            offered_ids = {o.unit_id for o in offers}
            for unit in units:
                if unit.unit_id in survivors and badge_choices(unit):
                    assert unit.unit_id in offered_ids

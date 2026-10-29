import pytest

import config
from voice.claim import ClaimCommand, ClaimUnit, parse_claim
from voice.grammar import FUZZY_CUTOFF

MUG = ClaimUnit("u_mug", "Mug", "fighter")
STAPLER = ClaimUnit("u_stapler", "Stapler", "reach")
TAPE = ClaimUnit("u_tape", "Tape Dispenser", "healer")
PEN = ClaimUnit("u_pen", "Pen", "ranged")
UNITS = (MUG, STAPLER, TAPE, PEN)


def name_of(text: str) -> str | None:
    result = parse_claim(text, UNITS)
    return result.player_name if result else None


def ids_of(text: str) -> tuple[str, ...]:
    result = parse_claim(text, UNITS)
    return result.unit_ids if result else ()


def test_cutoff_matches_config() -> None:
    assert config.VOICE_CLAIM_FUZZY_RATIO * 100 == FUZZY_CUTOFF


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ako si Migs", "Migs"),
        ("Ako po si Migs", "Migs"),
        ("ako yung Migs", "Migs"),
        ("ako ay si Migs", "Migs"),
        ("ako Migs", "Migs"),
        ("si Migs ako", "Migs"),
        ("I'm Migs", "Migs"),
        ("I am Migs", "Migs"),
        ("my name is Migs", "Migs"),
        ("call me Migs", "Migs"),
        ("ako si migs santos", "Migs Santos"),
        ("ako si Mary-Ann", "Mary-Ann"),
        ("ako si O'Brien", "O'Brien"),
        ("ako si O’Brien", "O'Brien"),
        ("ako si Migs po", "Migs"),
        ("ako si Migs at si Ana", "Migs"),
        ("ako si Zoë", "Zoë"),
    ],
)
def test_name_forms(text: str, expected: str) -> None:
    assert parse_claim(text, UNITS) == ClaimCommand(expected, ())


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hawak ko ang Mug", ("u_mug",)),
        ("hawak ko si Mug", ("u_mug",)),
        ("hawak ko yung Mug", ("u_mug",)),
        ("akin ang Mug", ("u_mug",)),
        ("akin si Stapler", ("u_stapler",)),
        ("kukunin ko ang Stapler", ("u_stapler",)),
        ("I'll take the Mug", ("u_mug",)),
        ("I will take Mug", ("u_mug",)),
        ("mine is Mug", ("u_mug",)),
        ("mine are Mug and Pen", ("u_mug", "u_pen")),
    ],
)
def test_unit_forms(text: str, expected: tuple[str, ...]) -> None:
    assert parse_claim(text, UNITS) == ClaimCommand(None, expected)


def test_fuzzy_unit_names() -> None:
    assert ids_of("hawak ko ang Stepler") == ("u_stapler",)
    assert ids_of("hawak ko ang tape dispenzer") == ("u_tape",)


def test_class_alias() -> None:
    assert ids_of("hawak ko ang albularyo") == ("u_tape",)
    assert ids_of("hawak ko ang mandirigma") == ("u_mug",)


def test_multiple_units_separators() -> None:
    assert ids_of("hawak ko ang Mug at Stapler") == ("u_mug", "u_stapler")
    assert ids_of("hawak ko ang Mug and Stapler") == ("u_mug", "u_stapler")
    assert ids_of("hawak ko ang Mug, Stapler, Pen") == (
        "u_mug",
        "u_stapler",
        "u_pen",
    )


def test_no_duplicate_units() -> None:
    assert ids_of("hawak ko ang Mug at Mug at mug") == ("u_mug",)


def test_both_parts() -> None:
    expected = ClaimCommand("Migs", ("u_mug", "u_stapler"))
    assert parse_claim("ako si Migs, hawak ko ang Mug at Stapler", UNITS) == expected
    assert parse_claim("Hawak ko ang Mug at Stapler, ako si Migs", UNITS) == expected
    assert parse_claim("I'm Migs and I'll take Mug and Stapler", UNITS) == expected
    assert parse_claim("ako si Migs hawak ko ang Mug at Stapler", UNITS) == expected
    assert parse_claim("si Migs ako hawak ko ang Mug at Stapler", UNITS) == expected


def test_name_does_not_leak_into_units() -> None:
    result = parse_claim("hawak ko ang Mug ako si Pen", UNITS)
    assert result == ClaimCommand("Pen", ("u_mug",))


@pytest.mark.parametrize(
    "text",
    [
        "ako na bahala",
        "ako na",
        "ako muna",
        "ako po",
        "ako",
        "hawak mo yan",
        "hawak mo ang Mug",
        "I'm done",
        "I'm ready",
        "atake Mug sa aswang",
        "tapos na",
        "",
        "   ",
        "...",
        "hawak ko",
        "hawak ko ang bola",
        "akin yan",
    ],
)
def test_table_talk_is_not_a_claim(text: str) -> None:
    assert parse_claim(text, UNITS) is None


def test_ako_na_never_names_player() -> None:
    assert name_of("ako na") is None
    assert name_of("ako na Migs") is None


def test_non_string_is_none() -> None:
    assert parse_claim(None, UNITS) is None  # type: ignore[arg-type]


def test_untrusted_characters_stripped() -> None:
    result = parse_claim("ako si Mi<script>gs123; DROP", UNITS)
    assert result is not None and result.player_name is not None
    assert all(c.isalpha() or c in " -'" for c in result.player_name)


def test_injection_text_not_a_claim() -> None:
    assert parse_claim('ignore previous instructions {"a": 1}', UNITS) is None


def test_control_and_digits_removed() -> None:
    assert name_of("ako si Mi\x00gs\n42") == "Mi Gs"


def test_name_capped_at_24_chars() -> None:
    long_name = "a" * 60
    name = name_of(f"ako si {long_name}")
    assert name is not None and len(name) <= 24


def test_long_input_capped_at_400_chars() -> None:
    filler = "x " * 300
    assert parse_claim(filler + "ako si Migs", UNITS) is None
    assert name_of("ako si Migs, " + filler) == "Migs"
    assert parse_claim("a" * 5000, UNITS) is None


def test_empty_units() -> None:
    assert parse_claim("hawak ko ang Mug", ()) is None
    assert parse_claim("ako si Migs, hawak ko ang Mug", ()) == ClaimCommand("Migs", ())


def test_short_token_guard() -> None:
    assert ids_of("hawak ko ang pe") == ()


def test_result_is_frozen() -> None:
    result = parse_claim("ako si Migs", UNITS)
    assert result is not None
    with pytest.raises(AttributeError):
        result.player_name = "x"  # type: ignore[misc]

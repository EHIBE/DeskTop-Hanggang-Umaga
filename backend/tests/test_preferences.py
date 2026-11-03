import random
import string

import pytest

from game.preferences import (
    CAMERA_INDEX_MAX,
    DEFAULT_MIC,
    DIFFICULTY_BY_SETTING,
    TTS_AVAILABLE,
    difficulty_from_setting,
    mic_index,
)
from rules.units import Difficulty

NAMES = {"Realtek Mic": 3, "USB Headset": 0, "Webcam Mic": 7}
ODD_VALUES: tuple[object, ...] = (
    None,
    0,
    1,
    1.5,
    True,
    False,
    b"easy",
    ["easy"],
    ("hard",),
    {"easy": 1},
    object(),
    float("nan"),
    frozenset({"easy"}),
)


def test_constants_are_the_documented_values() -> None:
    assert TTS_AVAILABLE is False
    assert DEFAULT_MIC == "default"
    assert CAMERA_INDEX_MAX == 5
    assert DIFFICULTY_BY_SETTING == {
        "easy": Difficulty.MADALI,
        "normal": Difficulty.NORMAL,
        "hard": Difficulty.MAHIRAP,
    }


@pytest.mark.parametrize(
    ("setting", "expected"),
    [
        ("easy", Difficulty.MADALI),
        ("normal", Difficulty.NORMAL),
        ("hard", Difficulty.MAHIRAP),
    ],
)
def test_known_difficulty_settings_map(setting: str, expected: Difficulty) -> None:
    assert difficulty_from_setting(setting) is expected


@pytest.mark.parametrize(
    "setting", ["", "EASY", "Hard", " easy", "madali", "mahirap", "impossible", "0"]
)
def test_unknown_difficulty_strings_fall_back_to_normal(setting: str) -> None:
    assert difficulty_from_setting(setting) is Difficulty.NORMAL


@pytest.mark.parametrize("value", ODD_VALUES)
def test_non_string_difficulty_falls_back_to_normal(value: object) -> None:
    assert difficulty_from_setting(value) is Difficulty.NORMAL


def test_difficulty_never_raises_for_random_text() -> None:
    rng = random.Random(21)
    alphabet = string.printable + "ñáéก\U0001f600"
    for _ in range(500):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 12)))
        assert difficulty_from_setting(text) in set(Difficulty)


def test_default_mic_means_no_index() -> None:
    assert mic_index(DEFAULT_MIC, NAMES) is None
    assert mic_index(DEFAULT_MIC, {}) is None
    assert mic_index("default", {"default": 4}) is None


@pytest.mark.parametrize("value", ODD_VALUES)
def test_non_string_mic_gives_none(value: object) -> None:
    assert mic_index(value, NAMES) is None


@pytest.mark.parametrize(
    ("text", "index"), [("0", 0), ("2", 2), ("15", 15), ("007", 7)]
)
def test_digit_strings_are_indexes(text: str, index: int) -> None:
    assert mic_index(text, {}) == index
    assert mic_index(text, NAMES) == index


def test_digits_win_over_names() -> None:
    assert mic_index("3", {"3": 9}) == 3


def test_names_resolve_through_the_map() -> None:
    for name, index in NAMES.items():
        assert mic_index(name, NAMES) == index


@pytest.mark.parametrize("text", ["", " ", "realtek mic", "Realtek Mic ", "-1", "1.5"])
def test_unknown_names_give_none(text: str) -> None:
    assert mic_index(text, NAMES) is None


def test_mic_index_result_is_none_or_int_for_random_text() -> None:
    rng = random.Random(5)
    for _ in range(500):
        text = "".join(
            rng.choice(string.ascii_letters + string.digits + " -_.")
            for _ in range(rng.randint(0, 10))
        )
        result = mic_index(text, NAMES)
        assert result is None or isinstance(result, int)
        if text.isascii() and text.isdigit():
            assert result == int(text)


def test_unicode_digit_does_not_raise() -> None:
    assert mic_index("²", NAMES) is None


def test_huge_digit_string_does_not_raise() -> None:
    assert mic_index("9" * 5000, NAMES) is None

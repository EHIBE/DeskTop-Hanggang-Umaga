from typing import Final

from rules.units import Difficulty

TTS_AVAILABLE: Final = False
DEFAULT_MIC: Final = "default"
CAMERA_INDEX_MAX: Final = 5

DIFFICULTY_BY_SETTING: Final = {
    "easy": Difficulty.MADALI,
    "normal": Difficulty.NORMAL,
    "hard": Difficulty.MAHIRAP,
}


def difficulty_from_setting(value: object) -> Difficulty:
    if isinstance(value, str):
        return DIFFICULTY_BY_SETTING.get(value, Difficulty.NORMAL)
    return Difficulty.NORMAL


MIC_DIGITS_MAX = 4


def mic_index(value: object, names: dict[str, int]) -> int | None:
    if not isinstance(value, str) or value == DEFAULT_MIC:
        return None
    if value.isascii() and value.isdigit() and len(value) <= MIC_DIGITS_MAX:
        return int(value)
    return names.get(value)

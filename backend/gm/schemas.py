import json
import unicodedata
from collections.abc import Collection, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

GRID_MAX = 1000
LABEL_MAX = 40
POWER_NAME_MAX = 30
CARD_TEXT_MAX = 140
SPRITE_SUBJECT_MAX = 80
PLAYER_NAME_MAX = 40
NARRATION_MAX = 240
CALLOUT_MAX = 60
CALLOUTS_MAX = 4
HINT_MAX = 120
DATA_DIR = Path(__file__).parent / "data"

UnitClass = Literal[
    "kubo", "charm", "healer", "fighter", "reach", "ranged", "scout", "wall"
]
PowerId = Literal[
    "none",
    "P01",
    "P02",
    "P03",
    "P04",
    "P05",
    "P06",
    "P07",
    "P08",
    "P09",
    "P10",
    "P11",
    "P12",
]
UNIT_CLASSES: tuple[str, ...] = (
    "kubo",
    "charm",
    "healer",
    "fighter",
    "reach",
    "ranged",
    "scout",
    "wall",
)
POWER_IDS: tuple[str, ...] = (
    "none",
    "P01",
    "P02",
    "P03",
    "P04",
    "P05",
    "P06",
    "P07",
    "P08",
    "P09",
    "P10",
    "P11",
    "P12",
)

LEET_MAP = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "@": "a"})


class SchemaError(ValueError):
    pass


class _StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_by_name=True,
        validate_by_alias=True,
    )


class Mood(StrEnum):
    KALMADO = "kalmado"
    KABA = "kaba"
    TAKOT = "takot"
    TAGUMPAY = "tagumpay"
    UMAGA = "umaga"


class DetectedBox(_StrictModel):
    x1: int
    y1: int
    x2: int
    y2: int


class Detected(_StrictModel):
    found_new: bool
    label: str = Field(max_length=LABEL_MAX)
    box: DetectedBox
    matches_known_id: str | None


class UnitCardDraft(_StrictModel):
    class_: UnitClass = Field(alias="class")
    hp_delta: Literal[-1, 0, 1]
    atk_delta: Literal[-1, 0, 1]
    power_id: PowerId
    power_name_tl: str = Field(max_length=POWER_NAME_MAX)
    card_text_tl: str = Field(max_length=CARD_TEXT_MAX)
    card_text_en: str = Field(max_length=CARD_TEXT_MAX)
    sprite_subject_en: str = Field(max_length=SPRITE_SUBJECT_MAX)


class UnitCardResponse(_StrictModel):
    detected: Detected
    card: UnitCardDraft


class GmCallout(_StrictModel):
    entity_id: str
    text_tl: str = Field(max_length=CALLOUT_MAX)


class GmTurn(_StrictModel):
    narration_tl: str = Field(max_length=NARRATION_MAX)
    narration_en: str = Field(max_length=NARRATION_MAX)
    mood: Mood
    callouts: tuple[GmCallout, ...] = Field(max_length=CALLOUTS_MAX)
    hint_tl: str = Field(max_length=HINT_MAX)


class RecapDraft(_StrictModel):
    recap_tl: str = Field(min_length=1, max_length=NARRATION_MAX)
    recap_en: str = Field(min_length=1, max_length=NARRATION_MAX)


def _object_schema(properties: dict[str, object]) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def unit_card_json_schema(known_slot_ids: Sequence[str]) -> dict[str, object]:
    matches: dict[str, object]
    if known_slot_ids:
        matches = {
            "anyOf": [
                {"type": "string", "enum": list(known_slot_ids)},
                {"type": "null"},
            ]
        }
    else:
        matches = {"anyOf": [{"type": "null"}]}
    box = _object_schema(
        {
            "x1": {"type": "integer"},
            "y1": {"type": "integer"},
            "x2": {"type": "integer"},
            "y2": {"type": "integer"},
        }
    )
    detected = _object_schema(
        {
            "found_new": {"type": "boolean"},
            "label": {"type": "string", "maxLength": LABEL_MAX},
            "box": box,
            "matches_known_id": matches,
        }
    )
    card = _object_schema(
        {
            "class": {"type": "string", "enum": list(UNIT_CLASSES)},
            "hp_delta": {"type": "integer", "enum": [-1, 0, 1]},
            "atk_delta": {"type": "integer", "enum": [-1, 0, 1]},
            "power_id": {"type": "string", "enum": list(POWER_IDS)},
            "power_name_tl": {"type": "string", "maxLength": POWER_NAME_MAX},
            "card_text_tl": {"type": "string", "maxLength": CARD_TEXT_MAX},
            "card_text_en": {"type": "string", "maxLength": CARD_TEXT_MAX},
            "sprite_subject_en": {"type": "string", "maxLength": SPRITE_SUBJECT_MAX},
        }
    )
    return _object_schema({"detected": detected, "card": card})


def parse_unit_card(raw_json: str, known_slot_ids: Collection[str]) -> UnitCardResponse:
    try:
        payload = json.loads(raw_json)
        response = UnitCardResponse.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as error:
        raise SchemaError(str(error)) from error
    matched = response.detected.matches_known_id
    if matched is not None and matched not in known_slot_ids:
        raise SchemaError(f"matches_known_id {matched!r} is not a known slot id")
    return response


def gm_turn_json_schema(allowed_ids: Sequence[str]) -> dict[str, object]:
    callout = _object_schema(
        {
            "entity_id": {"type": "string", "enum": list(allowed_ids)},
            "text_tl": {"type": "string", "maxLength": CALLOUT_MAX},
        }
    )
    return _object_schema(
        {
            "narration_tl": {"type": "string", "maxLength": NARRATION_MAX},
            "narration_en": {"type": "string", "maxLength": NARRATION_MAX},
            "mood": {"type": "string", "enum": [mood.value for mood in Mood]},
            "callouts": {"type": "array", "maxItems": CALLOUTS_MAX, "items": callout},
            "hint_tl": {"type": "string", "maxLength": HINT_MAX},
        }
    )


def parse_gm_turn(raw_json: str, allowed_ids: Collection[str]) -> GmTurn:
    try:
        turn = GmTurn.model_validate_json(raw_json)
    except ValidationError as error:
        raise SchemaError(str(error)) from error
    kept = tuple(c for c in turn.callouts if c.entity_id in allowed_ids)
    if len(kept) == len(turn.callouts):
        return turn
    return turn.model_copy(update={"callouts": kept})


def recap_json_schema() -> dict[str, object]:
    return _object_schema(
        {
            "recap_tl": {"type": "string", "maxLength": NARRATION_MAX},
            "recap_en": {"type": "string", "maxLength": NARRATION_MAX},
        }
    )


def parse_recap(raw_json: str) -> RecapDraft:
    try:
        return RecapDraft.model_validate_json(raw_json)
    except ValidationError as error:
        raise SchemaError(str(error)) from error


def clamp_box(box: DetectedBox, width: int, height: int) -> tuple[int, int, int, int]:
    def to_px(value: int, size: int) -> int:
        return round(max(0, min(GRID_MAX, value)) / GRID_MAX * size)

    xs = sorted((to_px(box.x1, width), to_px(box.x2, width)))
    ys = sorted((to_px(box.y1, height), to_px(box.y2, height)))
    if xs[0] == xs[1] or ys[0] == ys[1]:
        raise SchemaError("box has zero area after clamping")
    return xs[0], ys[0], xs[1], ys[1]


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    leeted = stripped.translate(LEET_MAP)
    spaced = "".join(ch if ch.isalnum() else " " for ch in leeted)
    return " ".join(spaced.split())


class _PhraseSet:
    def __init__(self, lines: Sequence[str]) -> None:
        phrases = {normalized for line in lines if (normalized := _normalize(line))}
        self._phrases = frozenset(phrases)
        self._max_words = max((len(p.split()) for p in phrases), default=0)

    def matches(self, text: str) -> bool:
        words = _normalize(text).split()
        for start in range(len(words)):
            last = min(len(words), start + self._max_words)
            if any(
                " ".join(words[start:end]) in self._phrases
                for end in range(start + 1, last + 1)
            ):
                return True
        return False


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _strip_control(text: str) -> str:
    spaced = "".join(" " if ch.isspace() else ch for ch in text)
    return "".join(ch for ch in spaced if not unicodedata.category(ch).startswith("C"))


class ContentFilter:
    def __init__(self, data_dir: Path | None = None) -> None:
        root = data_dir if data_dir is not None else DATA_DIR
        self._profanity = _PhraseSet(
            _read_lines(root / "blocklist_en.txt")
            + _read_lines(root / "blocklist_tl.txt")
        )
        self._banned = _PhraseSet(_read_lines(root / "banned_words.txt"))
        self._places = _PhraseSet(_read_lines(root / "ph_places.txt"))

    @classmethod
    def from_data_dir(cls, path: Path | None = None) -> "ContentFilter":
        return cls(path)

    def is_profane(self, text: str) -> bool:
        return self._profanity.matches(text)

    def has_banned_words(self, text: str) -> bool:
        return self._banned.matches(text)

    def names_place(self, text: str) -> bool:
        return self._places.matches(text)

    def is_safe_narration(self, text: str) -> bool:
        return not (
            self.is_profane(text)
            or self.has_banned_words(text)
            or self.names_place(text)
        )

    def clean_player_name(self, name: str, fallback: str) -> str:
        cleaned = " ".join(_strip_control(name).split())
        if not cleaned or self.is_profane(cleaned):
            return fallback
        return cleaned[:PLAYER_NAME_MAX].strip()

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from voice.grammar import MAX_TEXT_CHARS, GrammarUnit, find_unit_mentions, normalize

MAX_NAME_CHARS: Final = 24
MAX_NAME_WORDS: Final = 2
MIN_NAME_CHARS: Final = 2

_TOKEN: Final = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*|,")
_LETTERS: Final = re.compile(r"[^\W\d_]+")
_COMMA: Final = ","
_ARTICLES: Final = frozenset(("ang", "si", "yung", "ung"))
_NAME_LINKS: Final = frozenset(("si", "yung", "ung"))
_NAME_STOP: Final = frozenset(
    (
        "na",
        "po",
        "ko",
        "mo",
        "ka",
        "ang",
        "ng",
        "ay",
        "at",
        "and",
        "ako",
        "si",
        "yung",
        "ung",
        "mga",
        "lang",
        "naman",
        "dito",
        "muna",
        "din",
        "rin",
        "nga",
        "ba",
        "bahala",
        "hawak",
        "akin",
        "kukunin",
        "ill",
        "mine",
        "the",
        "a",
        "an",
        "i",
        "my",
        "me",
        "is",
        "are",
        "am",
        "will",
        "take",
        "done",
        "ready",
        "not",
        "going",
        "gonna",
        "back",
        "here",
        "in",
        "out",
        "fine",
        "good",
        "sure",
        "so",
        "just",
        "also",
        "next",
        "ok",
        "okay",
        "sorry",
        "tapos",
        "end",
        "cancel",
        "hindi",
        "mali",
        "wag",
        "huwag",
        "ayaw",
        "stop",
        "bahala",
        "pa",
        "sa",
        "rito",
        "dyan",
        "diyan",
        "dito",
    )
)


@dataclass(frozen=True)
class ClaimUnit:
    game_id: str
    name: str
    unit_class: str


@dataclass(frozen=True)
class ClaimCommand:
    player_name: str | None
    unit_ids: tuple[str, ...]


@dataclass(frozen=True)
class _Token:
    text: str
    fold: str


def _fold(text: str) -> str:
    if text == _COMMA:
        return _COMMA
    return normalize(text).replace(" ", "")


def _tokenize(text: str) -> list[_Token]:
    tokens = []
    for match in _TOKEN.finditer(text[:MAX_TEXT_CHARS]):
        raw = match.group().replace("’", "'")
        tokens.append(_Token(raw, _fold(raw)))
    return tokens


def _title(word: str) -> str:
    return _LETTERS.sub(lambda m: m.group().capitalize(), word)


def _clean_name(words: list[str]) -> str | None:
    name = " ".join(_title(word) for word in words)[:MAX_NAME_CHARS].rstrip(" -'")
    if len(name) < MIN_NAME_CHARS:
        return None
    return name


def _is_name_word(token: _Token) -> bool:
    return bool(token.fold) and token.fold not in _NAME_STOP and token.fold != _COMMA


def _collect_name(tokens: list[_Token], start: int, limit: int) -> str | None:
    words: list[str] = []
    for token in tokens[start:limit]:
        if len(words) >= MAX_NAME_WORDS or not _is_name_word(token):
            break
        words.append(token.text)
    return _clean_name(words) if words else None


def _folds(tokens: list[_Token], index: int, count: int) -> tuple[str, ...]:
    return tuple(t.fold for t in tokens[index : index + count])


def _name_trigger_end(tokens: list[_Token], i: int) -> int | None:
    fold = tokens[i].fold
    pair = _folds(tokens, i, 3)
    if pair[:2] == ("ako", "po") and pair[2:] == ("si",):
        return i + 3
    if fold == "ako" and len(pair) > 1 and pair[1] in _NAME_LINKS:
        return i + 2
    if pair[:2] == ("ako", "ay"):
        return i + 3 if pair[2:] == ("si",) else i + 2
    if fold == "ako" and i == 0:
        return i + 1
    if fold == "im":
        return i + 1
    if pair[:2] == ("i", "am"):
        return i + 2
    if pair == ("my", "name", "is"):
        return i + 3
    if pair[:2] == ("call", "me"):
        return i + 2
    return None


def _trailing_name(tokens: list[_Token]) -> tuple[str, int] | None:
    if len(tokens) < 3 or tokens[0].fold != "si":
        return None
    for count in range(MAX_NAME_WORDS, 0, -1):
        end = 1 + count
        if (
            end < len(tokens)
            and tokens[end].fold == "ako"
            and all(_is_name_word(t) for t in tokens[1:end])
        ):
            name = _clean_name([t.text for t in tokens[1:end]])
            if name is not None:
                return name, 0
    return None


def _find_name(tokens: list[_Token], unit_start: int | None) -> tuple[str, int] | None:
    trailing = _trailing_name(tokens)
    if trailing is not None:
        return trailing
    for i in range(len(tokens)):
        end = _name_trigger_end(tokens, i)
        if end is None:
            continue
        limit = len(tokens)
        if unit_start is not None and unit_start > i:
            limit = unit_start
        name = _collect_name(tokens, end, limit)
        if name is not None:
            return name, i
    return None


def _unit_trigger_end(tokens: list[_Token], i: int) -> int | None:
    one, two, three = (_folds(tokens, i, 3) + ("", "", ""))[:3]
    if one in ("hawak", "kukunin") and two == "ko":
        return i + 2
    if one == "akin" and two in _ARTICLES:
        return i + 2
    if one == "ill" and two == "take":
        return i + 2
    if (one, two, three) == ("i", "will", "take"):
        return i + 3
    if one == "mine" and two in ("is", "are"):
        return i + 2
    return None


def _find_units_start(tokens: list[_Token]) -> tuple[int, int] | None:
    for i in range(len(tokens)):
        end = _unit_trigger_end(tokens, i)
        if end is not None:
            return i, end
    return None


def _match_units(
    tokens: list[_Token], end: int, stop: int | None, units: Sequence[ClaimUnit]
) -> tuple[str, ...]:
    limit = len(tokens) if stop is None else stop
    segment = normalize(" ".join(t.text for t in tokens[end:limit] if t.text != _COMMA))
    if not segment or not units:
        return ()
    grammar_units = tuple(
        GrammarUnit(u.game_id, u.name, u.unit_class, 0.0, 0.0) for u in units
    )
    mentions = find_unit_mentions(segment.split(), set(), grammar_units)
    return tuple(dict.fromkeys(m.unit.game_id for m in mentions))


def parse_claim(text: str, units: Sequence[ClaimUnit]) -> ClaimCommand | None:
    if not isinstance(text, str):
        return None
    tokens = _tokenize(text)
    if not tokens:
        return None
    located = _find_units_start(tokens)
    unit_start = located[0] if located is not None else None
    found = _find_name(tokens, unit_start)
    name = found[0] if found is not None else None
    unit_ids: tuple[str, ...] = ()
    if located is not None:
        stop = None
        if found is not None and found[1] > located[0]:
            stop = found[1]
        unit_ids = _match_units(tokens, located[1], stop, units)
    if name is None and not unit_ids:
        return None
    return ClaimCommand(name, unit_ids)

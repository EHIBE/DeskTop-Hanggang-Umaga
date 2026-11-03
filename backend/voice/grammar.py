import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from rapidfuzz import fuzz

FUZZY_CUTOFF: Final = 75
TRIGGER_FUZZY_CUTOFF: Final = 80
TRIGGER_FUZZY_MIN_LEN: Final = 5
MAX_TEXT_CHARS: Final = 400
MAX_ALIAS_TOKENS: Final = 3
MIN_ALIAS_CHARS: Final = 3
MIN_FUZZY_WINDOW_CHARS: Final = 4
KUBO_CLASS: Final = "kubo"
MAX_INSTANCE_DIGITS: Final = 2

ENEMY_FUZZY_CUTOFF: Final = 80
ENEMY_PREFIX_MIN_LEN: Final = 4
SHORT_ALIAS_CHARS: Final = 4
SHORT_ALIAS_CUTOFF: Final = 85

ATTACK_WORDS: Final = (
    "atake",
    "saksakin",
    "tira",
    "hampasin",
    "banatan",
    "attack",
    "hit",
    "tirahin",
    "saksak",
    "atakihin",
    "sugurin",
    "palo",
    "paluin",
    "hampas",
)
POWER_WORDS: Final = (
    "gamitin",
    "protektahan",
    "bantayan",
    "power",
    "use",
    "protekta",
    "bantay",
    "kalasag",
)
HEAL_WORDS: Final = ("gamutin", "pagalingin", "heal", "gamot", "pagaling", "ayusin")
END_WORDS: Final = ("tapos", "done", "end", "next")
CANCEL_WORDS: Final = (
    "hindi",
    "cancel",
    "mali",
    "wag",
    "huwag",
    "ayaw",
    "kansela",
    "stop",
)
CANCEL_FOLLOWERS: Final = frozenset(("yan", "yon", "iyan", "iyon", "na", "po"))
ENEMY_TYPES: Final = ("aswang", "tikbalang", "kapre", "manananggal", "duwende")
ENEMY_ALIASES: Final = {
    "tigbalang": "tikbalang",
    "duende": "duwende",
    "dwende": "duwende",
}
GENERIC_ENEMY_WORDS: Final = ("kalaban", "kaaway")
NUMBER_WORDS: Final = {
    "isa": 1,
    "uno": 1,
    "una": 1,
    "dalawa": 2,
    "dos": 2,
    "tatlo": 3,
    "tres": 3,
    "apat": 4,
    "kwatro": 4,
    "lima": 5,
    "singko": 5,
    "anim": 6,
    "pito": 7,
    "walo": 8,
}
CLASS_ALIASES: Final = {
    "charm": ("anting anting", "charm"),
    "healer": ("albularyo", "manggagamot", "healer"),
    "fighter": ("mandirigma", "fighter"),
    "reach": ("sibat", "reach"),
    "ranged": ("pana", "archer", "ranged"),
    "scout": ("scout",),
    "wall": ("pader", "wall"),
    "kubo": ("kubo", "bahay"),
}

_NON_WORD: Final = re.compile(r"[^a-z0-9]+")


class CommandKind(StrEnum):
    ATTACK = "attack"
    POWER = "power"
    HEAL = "heal"
    END_TURN = "end_turn"
    CANCEL = "cancel"


@dataclass(frozen=True)
class GrammarUnit:
    game_id: str
    name: str
    unit_class: str
    x_cm: float
    y_cm: float


@dataclass(frozen=True)
class GrammarEnemy:
    id: str
    type: str
    x_cm: float
    y_cm: float


@dataclass(frozen=True)
class GrammarContext:
    units: tuple[GrammarUnit, ...]
    enemies: tuple[GrammarEnemy, ...]


@dataclass(frozen=True)
class Command:
    kind: CommandKind
    unit_id: str | None
    target_id: str | None


@dataclass(frozen=True)
class _EnemyMention:
    enemy_type: str | None
    number: int | None
    index: int


@dataclass(frozen=True)
class _UnitMention:
    unit: GrammarUnit
    index: int
    width: int


_ACTION_KINDS: Final = {
    **dict.fromkeys(ATTACK_WORDS, CommandKind.ATTACK),
    **dict.fromkeys(POWER_WORDS, CommandKind.POWER),
    **dict.fromkeys(HEAL_WORDS, CommandKind.HEAL),
}
_TRIGGER_TOKENS: Final = frozenset((*_ACTION_KINDS, *END_WORDS, *CANCEL_WORDS))


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text[:MAX_TEXT_CHARS])
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(_NON_WORD.sub(" ", stripped.casefold()).split())


def _canonical(token: str) -> str:
    if token.startswith("i") and token[1:] in _ACTION_KINDS:
        return token[1:]
    return token


def _merge_prefix(tokens: list[str]) -> list[str]:
    merged: list[str] = []
    for index, token in enumerate(tokens):
        if (
            token == "i"
            and index + 1 < len(tokens)
            and _canonical(tokens[index + 1]) in _ACTION_KINDS
        ):
            continue
        merged.append(_canonical(token))
    return merged


def _is_cancel_word(token: str) -> bool:
    if token in CANCEL_WORDS:
        return True
    return len(token) >= TRIGGER_FUZZY_MIN_LEN and any(
        len(word) >= TRIGGER_FUZZY_MIN_LEN
        and fuzz.ratio(word, token) >= TRIGGER_FUZZY_CUTOFF
        for word in CANCEL_WORDS
    )


def _cancel_state(tokens: list[str]) -> str:
    if not _is_cancel_word(tokens[0]):
        return "none"
    if tokens[0] == "hindi" and len(tokens) > 1 and tokens[1] == "pa":
        return "none"
    if len(tokens) == 1:
        return "cancel"
    second = tokens[1]
    if second in CANCEL_FOLLOWERS or second in _TRIGGER_TOKENS:
        return "cancel"
    if all(_is_cancel_word(token) for token in tokens):
        return "cancel"
    return "soft"


def _has_end(tokens: list[str]) -> bool:
    if tokens == ["tapos"]:
        return True
    if any(token in ("done", "end", "next") for token in tokens):
        return True
    return any(
        tokens[i] == "tapos" and tokens[i + 1] == "na" for i in range(len(tokens) - 1)
    )


def _parse_instance(token: str) -> int | None:
    if token.isdigit() and len(token) <= MAX_INSTANCE_DIGITS:
        return int(token)
    return NUMBER_WORDS.get(token)


def _match_enemy_type(token: str, names: dict[str, str]) -> str | None:
    exact = names.get(token)
    if exact is not None:
        return exact
    best: tuple[float, str] | None = None
    for name, enemy_type in names.items():
        score = 0.0
        if len(token) >= ENEMY_PREFIX_MIN_LEN and name.startswith(token):
            score = 90.0
        elif len(token) >= len(name) - 1:
            ratio = fuzz.ratio(name, token)
            if ratio >= ENEMY_FUZZY_CUTOFF:
                score = ratio
        if score and (best is None or score > best[0]):
            best = (score, enemy_type)
    return best[1] if best is not None else None


def _find_enemy_mentions(
    tokens: list[str], enemy_types: tuple[str, ...]
) -> list[_EnemyMention]:
    mentions: list[_EnemyMention] = []
    used: set[int] = set()
    names = {enemy_type: enemy_type for enemy_type in enemy_types}
    for alias, enemy_type in ENEMY_ALIASES.items():
        if enemy_type in names:
            names[alias] = enemy_type
    for i, token in enumerate(tokens):
        if i in used or token in _TRIGGER_TOKENS or token.isdigit():
            continue
        if token in GENERIC_ENEMY_WORDS:
            used.add(i)
            mentions.append(_EnemyMention(None, None, i))
            continue
        matched = _match_enemy_type(token, names)
        if matched is None:
            continue
        number: int | None = None
        if i + 1 < len(tokens):
            number = _parse_instance(tokens[i + 1])
            repeated = i + 2 < len(tokens) and tokens[i + 2] == tokens[i + 1]
            if number is not None and repeated:
                number = None
            if number is not None:
                used.add(i + 1)
        used.add(i)
        mentions.append(_EnemyMention(matched, number, i))
    return mentions


def _unit_aliases(unit: GrammarUnit) -> list[tuple[str, int]]:
    aliases: list[tuple[str, int]] = []
    seen: set[str] = set()

    def add(raw: str, priority: int) -> None:
        alias = normalize(raw)
        if len(alias) >= MIN_ALIAS_CHARS and alias not in seen:
            seen.add(alias)
            aliases.append((alias, priority))

    add(unit.name, 0)
    add(unit.game_id.removeprefix("u_"), 1)
    unit_class = normalize(unit.unit_class)
    for alias in CLASS_ALIASES.get(unit_class, (unit_class,)):
        add(alias, 1)
    return aliases


def find_unit_mentions(
    tokens: list[str], blocked: set[int], units: tuple[GrammarUnit, ...]
) -> list[_UnitMention]:
    candidates: list[tuple[float, int, int, int, int]] = []
    alias_table = [_unit_aliases(unit) for unit in units]
    for start in range(len(tokens)):
        if start in blocked:
            continue
        for width in range(1, MAX_ALIAS_TOKENS + 1):
            indexes = range(start, start + width)
            if indexes[-1] >= len(tokens) or any(i in blocked for i in indexes):
                break
            window = " ".join(tokens[start : start + width])
            for unit_index, aliases in enumerate(alias_table):
                for alias, priority in aliases:
                    if alias.count(" ") + 1 != width:
                        continue
                    if len(window) < max(MIN_ALIAS_CHARS, 0.6 * len(alias)):
                        continue
                    if len(window) > 1.5 * len(alias) + 2:
                        continue
                    if len(window) < MIN_FUZZY_WINDOW_CHARS and window != alias:
                        continue
                    if len(alias) <= SHORT_ALIAS_CHARS:
                        score = fuzz.ratio(alias, window)
                        cutoff = SHORT_ALIAS_CUTOFF
                    else:
                        if len(window) < MIN_FUZZY_WINDOW_CHARS:
                            continue
                        score = fuzz.partial_ratio(alias, window)
                        cutoff = FUZZY_CUTOFF
                    if score >= cutoff:
                        candidates.append((-score, priority, start, width, unit_index))
    candidates.sort()
    taken: set[int] = set()
    accepted: list[_UnitMention] = []
    for _, _, start, width, unit_index in candidates:
        span = set(range(start, start + width))
        if span & taken:
            continue
        taken |= span
        accepted.append(_UnitMention(units[unit_index], start, width))
    accepted.sort(key=lambda mention: mention.index)
    return accepted


def _find_action(
    tokens: list[str], blocked: set[int]
) -> tuple[CommandKind, int] | None:
    for i, token in enumerate(tokens):
        kind = _ACTION_KINDS.get(token)
        if kind is not None:
            return kind, i
    best: tuple[float, int, CommandKind] | None = None
    for i, token in enumerate(tokens):
        if i in blocked or len(token) < TRIGGER_FUZZY_MIN_LEN:
            continue
        for word, kind in _ACTION_KINDS.items():
            if len(word) < TRIGGER_FUZZY_MIN_LEN:
                continue
            score = fuzz.ratio(word, token)
            if score >= TRIGGER_FUZZY_CUTOFF and (best is None or score > best[0]):
                best = (score, i, kind)
    if best is None:
        return None
    return best[2], best[1]


def _distance_sq(unit: GrammarUnit, enemy: GrammarEnemy) -> float:
    return (unit.x_cm - enemy.x_cm) ** 2 + (unit.y_cm - enemy.y_cm) ** 2


def _nearest(unit: GrammarUnit, enemies: list[GrammarEnemy]) -> str | None:
    if not enemies:
        return None
    return min(enemies, key=lambda enemy: (_distance_sq(unit, enemy), enemy.id)).id


def _resolve_enemy(
    mention: _EnemyMention, actor: GrammarUnit, enemies: tuple[GrammarEnemy, ...]
) -> str | None:
    if mention.enemy_type is None:
        return _nearest(actor, list(enemies))
    of_type = [e for e in enemies if e.type.casefold() == mention.enemy_type]
    if mention.number is not None:
        wanted = f"e_{mention.enemy_type}_{mention.number}"
        for enemy in of_type:
            if enemy.id == wanted:
                return enemy.id
    return _nearest(actor, of_type)


def _resolve_target(
    kind: CommandKind,
    actor: _UnitMention,
    unit_mentions: list[_UnitMention],
    enemy_mentions: list[_EnemyMention],
    context: GrammarContext,
) -> str | None:
    if kind is CommandKind.ATTACK:
        if enemy_mentions:
            named = _resolve_enemy(enemy_mentions[0], actor.unit, context.enemies)
            if named is not None:
                return named
        return _nearest(actor.unit, list(context.enemies))
    other_unit = next(
        (m for m in unit_mentions if m.unit.game_id != actor.unit.game_id), None
    )
    other_enemy = enemy_mentions[0] if enemy_mentions else None
    if other_unit is not None and (
        other_enemy is None or other_unit.index < other_enemy.index
    ):
        return other_unit.unit.game_id
    if other_enemy is not None:
        return _resolve_enemy(other_enemy, actor.unit, context.enemies)
    return None


def parse_command(text: str, context: GrammarContext) -> Command | None:
    if not isinstance(text, str):
        return None
    tokens = _merge_prefix(normalize(text).split())
    if not tokens:
        return None
    cancel = _cancel_state(tokens)
    if cancel == "cancel":
        return Command(CommandKind.CANCEL, None, None)
    command = _parse_order(tokens, context)
    is_soft_cancel = cancel == "soft"
    if is_soft_cancel and (command is None or command.kind is CommandKind.END_TURN):
        return Command(CommandKind.CANCEL, None, None)
    return command


def _parse_order(tokens: list[str], context: GrammarContext) -> Command | None:
    enemy_types = tuple(
        dict.fromkeys((*ENEMY_TYPES, *(e.type.casefold() for e in context.enemies)))
    )
    enemy_mentions = _find_enemy_mentions(tokens, enemy_types)
    blocked = {i for i, token in enumerate(tokens) if token in _TRIGGER_TOKENS}
    for mention in enemy_mentions:
        blocked.add(mention.index)
        if mention.number is not None:
            blocked.add(mention.index + 1)
    unit_mentions = find_unit_mentions(tokens, blocked, context.units)
    for unit_mention in unit_mentions:
        blocked.update(
            range(unit_mention.index, unit_mention.index + unit_mention.width)
        )

    action = _find_action(tokens, blocked)
    if action is None:
        if _has_end(tokens):
            return Command(CommandKind.END_TURN, None, None)
        return None
    if not unit_mentions:
        return None
    actor = unit_mentions[0]
    kind = action[0]
    is_kubo_healer = kind is CommandKind.HEAL and actor.unit.unit_class == KUBO_CLASS
    if is_kubo_healer and len(unit_mentions) == 1:
        return None
    target = _resolve_target(kind, actor, unit_mentions, enemy_mentions, context)
    return Command(kind, actor.unit.game_id, target)

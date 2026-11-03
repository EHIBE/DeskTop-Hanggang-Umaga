import random
import re
import string
import time

import pytest

from voice.grammar import (
    ATTACK_WORDS,
    CANCEL_WORDS,
    CLASS_ALIASES,
    END_WORDS,
    ENEMY_ALIASES,
    ENEMY_TYPES,
    HEAL_WORDS,
    MAX_TEXT_CHARS,
    NUMBER_WORDS,
    POWER_WORDS,
    Command,
    CommandKind,
    GrammarContext,
    GrammarEnemy,
    GrammarUnit,
    normalize,
    parse_command,
)

UNIT_NAMES = (
    "Spearman",
    "Albularyo",
    "Anting-anting",
    "Mandirigma",
    "Bantay Kusina",
    "Lola Ising",
    "Ate Bote",
    "Kuya Tasa",
    "Pader",
    "Sibat ni Lolo",
    "Banig",
    "Walis Tingting",
    "Tsinelas",
    "Payong",
    "Kutsara",
    "Sandok",
    "Pen",
    "Bao",
    "Ñandú",
    "名前",
    "\U0001f600",
    "",
    " ",
    "u_hack",
    "e_aswang_1",
    "tapos",
    "aswang",
    "hindi",
    "tira",
    "A" * 60,
)
CLASS_NAMES = (*CLASS_ALIASES, "Boss", "", "KUBO", "Fighter", "mystery")
ENEMY_NAMES = (*ENEMY_TYPES, "Aswang", "boss", "", "TIKBALANG")
FILLERS = (
    "si",
    "ang",
    "ni",
    "kay",
    "po",
    "na",
    "ng",
    "yung",
    "ba",
    "pa",
    "ay",
    "mo",
    "ko",
    "hawak",
    "ako",
    "please",
    "kalaban",
    "kaaway",
)
JUNK = (
    chr(0xF1),
    chr(0xE9),
    chr(0xE01),
    chr(0x1F600),
    chr(0x200B),
    chr(9),
    chr(0),
    chr(0x202E),
)
SEPARATORS = (" ", " ", ", ", "! ", "... ", "  ", "\n", "-", " - ")


def rand_context(rng: random.Random) -> GrammarContext:
    units = tuple(
        GrammarUnit(
            f"u_{index}",
            rng.choice(UNIT_NAMES),
            rng.choice(CLASS_NAMES),
            rng.uniform(-10, 90),
            rng.uniform(-10, 60),
        )
        for index in range(rng.randint(0, 7))
    )
    enemies = tuple(
        GrammarEnemy(
            f"e_{kind.casefold() or 'x'}_{index}",
            kind,
            rng.uniform(-10, 90),
            rng.uniform(-10, 60),
        )
        for index in range(rng.randint(0, 6))
        for kind in (rng.choice(ENEMY_NAMES),)
    )
    return GrammarContext(units, enemies)


def typo(rng: random.Random, word: str) -> str:
    if len(word) < 2:
        return word
    pos = rng.randrange(len(word))
    kind = rng.randrange(4)
    if kind == 0:
        return word[:pos] + word[pos + 1 :]
    if kind == 1:
        return word[:pos] + rng.choice(string.ascii_lowercase) + word[pos:]
    if kind == 2 and pos + 1 < len(word):
        return word[:pos] + word[pos + 1] + word[pos] + word[pos + 2 :]
    return word[:pos] + rng.choice(string.ascii_lowercase) + word[pos + 1 :]


def rand_text(rng: random.Random, context: GrammarContext) -> str:
    names = [u.name for u in context.units]
    pools: list[tuple[str, ...]] = [
        ATTACK_WORDS,
        POWER_WORDS,
        HEAL_WORDS,
        END_WORDS,
        CANCEL_WORDS,
        ENEMY_TYPES,
        tuple(ENEMY_ALIASES),
        tuple(NUMBER_WORDS),
        tuple(str(n) for n in range(120)),
        FILLERS,
        JUNK,
        tuple(names) or ("nobody",),
        tuple(names) or ("nobody",),
    ]
    pieces: list[str] = []
    for _ in range(rng.randint(1, 8)):
        pool = rng.choice(pools)
        piece = rng.choice(pool)
        roll = rng.random()
        if roll < 0.2:
            piece = typo(rng, piece)
        elif roll < 0.3:
            piece = piece.upper()
        elif roll < 0.4 and piece in ATTACK_WORDS + POWER_WORDS + HEAL_WORDS:
            piece = "i" + piece
        elif roll < 0.5:
            piece = "".join(rng.choice(string.ascii_lowercase) for _ in range(3))
        pieces.append(piece)
    out = ""
    for piece in pieces:
        out += piece + rng.choice(SEPARATORS)
    return out


def check_command(command: Command | None, context: GrammarContext) -> None:
    if command is None:
        return
    unit_ids = {u.game_id for u in context.units}
    enemy_ids = {e.id for e in context.enemies}
    if command.kind in (CommandKind.END_TURN, CommandKind.CANCEL):
        assert command.unit_id is None
        assert command.target_id is None
        return
    assert command.unit_id in unit_ids
    if command.target_id is not None:
        assert command.target_id in unit_ids | enemy_ids
        if command.kind is CommandKind.ATTACK:
            assert command.target_id in enemy_ids
        assert command.target_id != command.unit_id


def test_random_taglish_never_crashes_and_only_references_real_ids() -> None:
    kinds: set[CommandKind] = set()
    for seed in range(900):
        rng = random.Random(seed)
        context = rand_context(rng)
        for _ in range(3):
            text = rand_text(rng, context)
            first = parse_command(text, context)
            check_command(first, context)
            assert first == parse_command(text, context)
            if first is not None:
                kinds.add(first.kind)
    assert kinds == set(CommandKind)


def test_empty_context_never_yields_ids() -> None:
    context = GrammarContext((), ())
    for seed in range(300):
        rng = random.Random(seed)
        text = rand_text(rng, context)
        command = parse_command(text, context)
        assert command is None or command.kind in (
            CommandKind.END_TURN,
            CommandKind.CANCEL,
        )


def test_units_without_enemies_never_invent_enemy_targets() -> None:
    for seed in range(300):
        rng = random.Random(seed)
        full = rand_context(rng)
        context = GrammarContext(full.units, ())
        command = parse_command(rand_text(rng, context), context)
        check_command(command, context)
        if command is not None and command.kind is CommandKind.ATTACK:
            assert command.target_id is None


def test_real_unit_names_alone_and_with_verbs_never_crash() -> None:
    rng = random.Random(77)
    units = tuple(
        GrammarUnit(f"u_{i}", name, rng.choice(CLASS_NAMES), 5.0 * i, 3.0 * i)
        for i, name in enumerate(UNIT_NAMES)
    )
    context = GrammarContext(units, (GrammarEnemy("e_aswang_1", "aswang", 1.0, 1.0),))
    verbs = (*ATTACK_WORDS[:3], *POWER_WORDS[:3], *HEAL_WORDS[:3], "")
    for unit in units:
        for verb in verbs:
            for tail in ("", " aswang", f" {units[0].name}"):
                check_command(
                    parse_command(f"{unit.name} {verb}{tail}", context), context
                )
                check_command(
                    parse_command(f"{verb} {unit.name}{tail}", context), context
                )


@pytest.mark.parametrize("junk", [None, 5, 1.5, b"tira", ["tapos"], {"a": 1}, object()])
def test_non_string_input_returns_none(junk: object) -> None:
    context = GrammarContext((), ())
    assert parse_command(junk, context) is None  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "text", ["", " ", "\n\t", "...", "!!!", "\x00", "\u200b", "\U0001f600" * 50]
)
def test_blank_and_symbol_input_returns_none(text: str) -> None:
    context = GrammarContext(
        (GrammarUnit("u_a", "Spearman", "reach", 1, 1),),
        (GrammarEnemy("e_aswang_1", "aswang", 2, 2),),
    )
    assert parse_command(text, context) is None


def test_very_long_input_is_truncated_and_fast() -> None:
    context = GrammarContext(
        (GrammarUnit("u_a", "Spearman", "reach", 1, 1),),
        (GrammarEnemy("e_aswang_1", "aswang", 2, 2),),
    )
    text = "Spearman atake aswang " * 20000
    started = time.perf_counter()
    command = parse_command(text, context)
    assert time.perf_counter() - started < 1.0
    assert command == Command(CommandKind.ATTACK, "u_a", "e_aswang_1")
    assert len(normalize(text)) <= MAX_TEXT_CHARS
    hidden = "x " * MAX_TEXT_CHARS + "Spearman atake aswang"
    assert parse_command(hidden, context) is None


def test_normalize_is_idempotent_ascii_and_lowercase() -> None:
    rng = random.Random(31)
    alphabet = string.printable + "ñéก\U0001f600\u200b́"
    for _ in range(500):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 60)))
        once = normalize(text)
        assert normalize(once) == once
        assert re.fullmatch(r"[a-z0-9 ]*", once) or not once.isascii()
        assert "  " not in once
        assert once == once.strip()


def test_normalize_strips_accents() -> None:
    assert normalize("Ñandú") == "nandu"
    assert normalize("  HELLO,   world!! ") == "hello world"


def alias_substrings(alias: str) -> set[str]:
    return {
        alias[i : i + n].casefold()
        for n in range(1, 4)
        for i in range(len(alias) - n + 1)
        if alias[i : i + n].strip()
    }


LONG_UNITS = (
    GrammarUnit("u_1", "Spearman", "reach", 5.0, 5.0),
    GrammarUnit("u_2", "Albularyo", "healer", 9.0, 5.0),
    GrammarUnit("u_3", "Anting-anting", "charm", 12.0, 5.0),
    GrammarUnit("u_4", "Mandirigma", "fighter", 15.0, 5.0),
    GrammarUnit("u_5", "Tsinelas Ni Lola", "scout", 18.0, 5.0),
)
LONG_CONTEXT = GrammarContext(
    LONG_UNITS, (GrammarEnemy("e_aswang_1", "aswang", 40.0, 40.0),)
)


def test_three_letter_or_shorter_substrings_never_fuzzy_match_long_aliases() -> None:
    fragments: set[str] = set()
    for unit in LONG_UNITS:
        for alias in (unit.name, unit.unit_class, unit.game_id.removeprefix("u_")):
            fragments |= alias_substrings(alias)
        for alias in CLASS_ALIASES.get(unit.unit_class, ()):
            fragments |= alias_substrings(alias)
    assert len(fragments) > 100
    for fragment in sorted(fragments):
        for verb in ("tira", "gamitin", "gamutin", "hit"):
            for text in (f"{verb} {fragment}", f"{fragment} {verb}", fragment):
                command = parse_command(text, LONG_CONTEXT)
                assert command is None or command.unit_id is None, (text, command)


def test_random_short_tokens_never_pick_a_long_named_unit() -> None:
    rng = random.Random(404)
    for _ in range(1500):
        size = rng.randint(1, 3)
        token = "".join(rng.choice(string.ascii_lowercase) for _ in range(size))
        verb = rng.choice(("tira", "gamitin", "gamutin"))
        command = parse_command(f"{verb} {token}", LONG_CONTEXT)
        assert command is None or command.unit_id is None, (token, command)


def test_exact_three_letter_name_matches_but_two_letter_cut_does_not() -> None:
    unit = GrammarUnit("u_bao", "Bao", "reach", 1.0, 1.0)
    context = GrammarContext((unit,), (GrammarEnemy("e_aswang_1", "aswang", 2, 2),))
    assert parse_command("Bao atake aswang", context) == Command(
        CommandKind.ATTACK, "u_bao", "e_aswang_1"
    )
    assert parse_command("Ba atake aswang", context) is None
    assert parse_command("B atake aswang", context) is None


def test_three_letter_token_does_not_fuzzy_match_a_four_letter_alias() -> None:
    unit = GrammarUnit("u_tala", "Tala", "fighter", 1.0, 1.0)
    context = GrammarContext((unit,), (GrammarEnemy("e_aswang_1", "aswang", 2, 2),))
    command = parse_command("tira tal", context)
    assert command is None or command.unit_id is None


def test_two_letter_cut_of_a_four_letter_alias_does_not_match() -> None:
    unit = GrammarUnit("u_tala", "Tala", "fighter", 1.0, 1.0)
    context = GrammarContext((unit,), (GrammarEnemy("e_aswang_1", "aswang", 2, 2),))
    for cut in ("ta", "al", "la", "t", "a"):
        command = parse_command(f"tira {cut}", context)
        assert command is None or command.unit_id is None, cut

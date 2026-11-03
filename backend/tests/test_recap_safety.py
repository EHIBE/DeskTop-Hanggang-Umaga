import asyncio
import json
import random
import re
import string
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import httpx2
import pytest

from gm.glimmer import GlimmerClient
from gm.narrator import LineBank
from gm.prompts import recap_input_text
from gm.recap import (
    ALIAS_PATTERN,
    RECAP_PREFIX,
    NightSummary,
    Recap,
    RecapBuilder,
    RecapError,
    RecapOutcome,
    RecapSource,
    RecapUnit,
    SparkRecapWriter,
    build_line_bank_recap,
    recap_text_ok,
    restore_recap_names,
)
from gm.schemas import DATA_DIR, ContentFilter, Mood
from meta_client import CostMeter, MetaClient, MetaError, create_openai_client
from tests.test_meta_client import MemoryLog

CONTENT = ContentFilter()
BANK = LineBank()
REAL_NAMES = ("Migs", "Anna", "Kuya Jun", "Ate Liza", "Bong", "Joy Reyes")
UNIT_NAMES = (
    "Spearman",
    "Albu",
    "Lola Ising",
    "Pader",
    "Sibat",
    "Banig",
    "Tsinelas",
    "Payong",
)
CLASSES = ("healer", "fighter", "reach", "ranged", "scout", "wall", "charm")
BADGES = ("HP+1", "Cooldown-1", "hp", "cooldown")
LABELS = ("P1", "P2", "P3", "P4")
URL = "http://127.0.0.1:11434"


def rand_summary(rng: random.Random) -> NightSummary:
    players = tuple(rng.sample(LABELS, rng.randint(0, 4)))
    pool = players or (None,)
    units = tuple(
        RecapUnit(
            rng.choice(UNIT_NAMES),
            rng.choice(CLASSES),
            rng.choice(pool),
            tuple(rng.sample(BADGES, rng.randint(0, 2))),
            rng.random() < 0.3,
            rng.random() < 0.3,
        )
        for _ in range(rng.randint(0, 6))
    )
    return NightSummary(
        night=rng.randint(1, 5),
        outcome=rng.choice(list(RecapOutcome)),
        turns_survived=rng.randint(0, 8),
        enemies_beaten=rng.randint(0, 14),
        units_downed=rng.randint(0, 6),
        units=units,
        players=players,
    )


def base_summary() -> NightSummary:
    return NightSummary(
        night=2,
        outcome=RecapOutcome.SUNRISE,
        turns_survived=8,
        enemies_beaten=5,
        units_downed=1,
        units=(
            RecapUnit("Spearman", "reach", "P1", badges=("HP+1",)),
            RecapUnit("Albu", "healer", "P2", scarred=True),
        ),
        players=("P1", "P2"),
    )


def wordlist(*files: str) -> list[str]:
    words: list[str] = []
    for name in files:
        for line in (DATA_DIR / name).read_text(encoding="utf-8").splitlines():
            word = line.strip()
            if re.fullmatch(r"[a-z]{4,}", word) and CONTENT.is_profane(word):
                words.append(word)
    return sorted(set(words))


PROFANE = wordlist("blocklist_en.txt", "blocklist_tl.txt")
BANNED = [
    w
    for w in (DATA_DIR / "banned_words.txt").read_text(encoding="utf-8").splitlines()
    if re.fullmatch(r"[a-z]{3,}", w.strip()) and CONTENT.has_banned_words(w)
]
PLACES = [
    w.strip()
    for w in (DATA_DIR / "ph_places.txt").read_text(encoding="utf-8").splitlines()
    if re.fullmatch(r"[A-Za-z]{4,}", w.strip()) and CONTENT.names_place(w)
]


def test_filter_lists_load_and_are_large_enough() -> None:
    assert len(PROFANE) > 50
    assert len(BANNED) >= 5
    assert len(PLACES) >= 5


@pytest.mark.parametrize(
    "alias", ["P5", "P0", "p1", "P10", "P", "1", "", "Migs", "P1 ", "P1\n", " P1", "Ѡ"]
)
def test_summary_rejects_every_non_label_player(alias: str) -> None:
    with pytest.raises(RecapError):
        NightSummary(1, RecapOutcome.SUNRISE, 8, 1, 0, players=(alias,))
    if alias:
        with pytest.raises(RecapError):
            NightSummary(
                1,
                RecapOutcome.SUNRISE,
                8,
                1,
                0,
                units=(RecapUnit("A", "wall", alias),),
            )


def test_random_real_names_are_always_rejected_as_aliases() -> None:
    rng = random.Random(1)
    for _ in range(400):
        name = rng.choice(REAL_NAMES) + "".join(
            rng.choice(string.ascii_letters + " 1234") for _ in range(rng.randint(0, 4))
        )
        if re.fullmatch(r"P[1-4]", name):
            continue
        with pytest.raises(RecapError):
            NightSummary(1, RecapOutcome.DEFEAT, 3, 0, 1, players=(name,))


def test_unowned_units_and_all_labels_are_accepted() -> None:
    rng = random.Random(2)
    for _ in range(300):
        summary = rand_summary(rng)
        assert set(summary.allowed_aliases()) <= set(LABELS)


def test_prompt_never_contains_a_real_name_or_unknown_label() -> None:
    rng = random.Random(3)
    for _ in range(300):
        summary = rand_summary(rng)
        payload = summary.prompt_payload()
        text = recap_input_text(summary)
        assert json.loads(text) == payload
        for name in REAL_NAMES:
            assert name not in text
        assert set(payload["players"]) <= set(LABELS)
        for unit in payload["units"]:
            assert unit["owner"] is None or unit["owner"] in LABELS
        assert summary.allowed_numbers() >= {
            str(summary.night),
            str(summary.turns_survived),
            str(summary.enemies_beaten),
            str(summary.units_downed),
        }


def test_line_bank_recap_is_clean_for_random_summaries() -> None:
    rng = random.Random(4)
    for _ in range(400):
        summary = rand_summary(rng)
        recap = build_line_bank_recap(summary, BANK)
        assert recap == build_line_bank_recap(summary, BANK)
        assert recap.source is RecapSource.LINE_BANK
        assert recap.text_tl.startswith(RECAP_PREFIX)
        assert recap.night == summary.night
        for text in (recap.text_tl, recap.text_en):
            assert "[" not in text and "]" not in text
            assert CONTENT.is_safe_narration(text)
            for name in REAL_NAMES:
                assert name not in text
            assert set(ALIAS_PATTERN.findall(text)) <= summary.allowed_aliases()
        assert recap_text_ok((recap.text_tl, recap.text_en), summary, CONTENT)
        expected = Mood.UMAGA if summary.outcome is RecapOutcome.SUNRISE else Mood.KABA
        assert recap.mood is expected


def test_restore_names_is_single_pass_and_label_only() -> None:
    rng = random.Random(5)
    for _ in range(300):
        mapping = {label: rng.choice(REAL_NAMES + LABELS) for label in LABELS}
        words = [
            rng.choice((*LABELS, "P5", "P10", "XP1", "P1P2", "ako", "si"))
            for _ in range(6)
        ]
        text = " ".join(words)
        recap = Recap(1, text, text, Mood.UMAGA, RecapSource.SPARK)
        restored = restore_recap_names(recap, mapping)
        expected = " ".join(
            mapping.get(w, w) if re.fullmatch(r"P[1-4]", w) else w for w in words
        )
        assert restored.text_tl == expected
        assert restored.text_en == expected
        assert restored.night == recap.night and restored.mood is recap.mood
        assert recap.text_tl == text


def test_restore_names_with_empty_mapping_is_identity() -> None:
    recap = Recap(1, "Kagabi, P1 at P2.", "P3.", Mood.UMAGA, RecapSource.SPARK)
    assert restore_recap_names(recap, {}) == recap


def valid_texts() -> tuple[str, str]:
    return (
        "Kagabi, 8 dilim, 5 natalo, bayani si P1.",
        "Last night 8 turns, 5 beaten, P1.",
    )


def test_baseline_text_is_accepted() -> None:
    assert recap_text_ok(valid_texts(), base_summary(), CONTENT)


def test_profanity_anywhere_blocks_the_output() -> None:
    rng = random.Random(6)
    tl, en = valid_texts()
    for _ in range(300):
        word = rng.choice(PROFANE)
        words_tl = tl.split()
        words_en = en.split()
        words_tl.insert(rng.randint(1, len(words_tl)), word)
        words_en.insert(rng.randint(0, len(words_en)), word)
        pick = rng.randrange(3)
        out_tl = " ".join(words_tl) if pick in (0, 2) else tl
        out_en = " ".join(words_en) if pick in (1, 2) else en
        assert not recap_text_ok((out_tl, out_en), base_summary(), CONTENT), word


def test_banned_words_and_places_block_the_output() -> None:
    rng = random.Random(7)
    tl, en = valid_texts()
    for _ in range(200):
        word = rng.choice(BANNED + PLACES)
        assert not recap_text_ok((f"{tl} {word}", en), base_summary(), CONTENT)
        assert not recap_text_ok((tl, f"{en} {word}"), base_summary(), CONTENT)


def test_unknown_numbers_labels_ids_and_prefix_block_the_output() -> None:
    summary = base_summary()
    tl, en = valid_texts()
    rng = random.Random(8)
    allowed = summary.allowed_numbers()
    for _ in range(200):
        number = str(rng.randint(0, 500))
        verdict = recap_text_ok((f"{tl} {number}", en), summary, CONTENT)
        assert verdict == (number in allowed)
        label = rng.choice(("P3", "P4"))
        assert not recap_text_ok((tl, f"{en} {label}"), summary, CONTENT)
        ident = rng.choice(("u_spear", "e_aswang_1", "u_1", "e_kapre_22"))
        assert not recap_text_ok((f"{tl} {ident}", en), summary, CONTENT)
        assert not recap_text_ok((tl, f"{en} {ident}"), summary, CONTENT)
        head = rng.choice(("Kahapon", "kagabi", "Tahimik", "", "  ", "Sa Kagabi"))
        assert not recap_text_ok((head + tl[len("Kagabi") :], en), summary, CONTENT)


def fake_spark(
    answers: list[str],
) -> tuple[SparkRecapWriter, list[dict[str, Any]], list[str]]:
    calls: list[dict[str, Any]] = []
    invalid: list[str] = []

    class Responses:
        async def create(self, **kwargs: Any) -> SimpleNamespace:
            calls.append(kwargs)
            raw = answers[min(len(calls), len(answers)) - 1]
            return SimpleNamespace(
                output_text=raw,
                id=f"resp_{len(calls)}",
                usage=SimpleNamespace(
                    input_tokens=10,
                    input_tokens_details=SimpleNamespace(cached_tokens=0),
                    output_tokens=5,
                ),
            )

    client = MetaClient(
        create_openai_client("test-key"),
        CostMeter(MemoryLog(starting_total=Decimal(0))),
    )
    sdk = SimpleNamespace(responses=Responses())
    client.sdk = lambda: sdk  # type: ignore[method-assign, assignment, return-value]
    return SparkRecapWriter(client, CONTENT, invalid.append), calls, invalid


def run_build(builder: RecapBuilder, offline: bool = False) -> Recap:
    return asyncio.run(builder.build(base_summary(), offline))


BAD_JSON = (
    "",
    " ",
    "not json",
    "{",
    "}",
    "[]",
    "null",
    "true",
    "0",
    '"Kagabi"',
    "{}",
    '{"recap_tl": "Kagabi"}',
    '{"recap_en": "Last night"}',
    '{"recap_tl": 5, "recap_en": 6}',
    '{"recap_tl": null, "recap_en": null}',
    '{"recap_tl": [], "recap_en": {}}',
    '{"recap_tl": "", "recap_en": ""}',
    '{"recap_tl": "Kagabi", "recap_en": "x", "extra": 1}',
    '{"recap_tl": "' + "K" * 5000 + '", "recap_en": "x"}',
    "\x00\x01\x02",
    "\U0001f600" * 30,
    '{"recap_tl": "Kagabi", "recap_en": "x"} trailing',
    '[{"recap_tl": "Kagabi", "recap_en": "x"}]',
)


@pytest.mark.parametrize("raw", BAD_JSON)
def test_bad_json_from_spark_falls_back_to_the_line_bank(raw: str) -> None:
    writer, calls, invalid = fake_spark([raw, raw])
    recap = run_build(RecapBuilder(BANK, CONTENT, spark=writer))
    assert recap.source is RecapSource.LINE_BANK
    assert recap.text_tl.startswith(RECAP_PREFIX)
    assert recap == build_line_bank_recap(base_summary(), BANK)
    assert 1 <= len(calls) <= 2
    assert invalid


def test_random_garbage_from_spark_always_falls_back() -> None:
    rng = random.Random(9)
    alphabet = string.printable + "ñ\U0001f600"
    for _ in range(80):
        raw = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 80)))
        writer, _, _ = fake_spark([raw, raw])
        recap = run_build(RecapBuilder(BANK, CONTENT, spark=writer))
        assert recap.source is RecapSource.LINE_BANK


def unsafe_answer(tl: str, en: str) -> str:
    return json.dumps({"recap_tl": tl, "recap_en": en})


def test_unsafe_spark_text_falls_back_to_the_line_bank() -> None:
    rng = random.Random(10)
    cases = [
        ("Kagabi, 77 ang natalo.", "Last night 77 fell."),
        ("Kagabi, bayani si P4.", "P4 was brave."),
        ("Kagabi, u_spear ang bayani.", "Last night u_spear."),
        ("Tahimik ang gabi.", "Quiet night."),
        *[
            (f"Kagabi, {w} ang gabi.", "Last night passed.")
            for w in rng.sample(PROFANE, 20)
        ],
        *[("Kagabi, tahimik.", f"Last night {w}.") for w in rng.sample(PROFANE, 20)],
        *[(f"Kagabi, sa {w}.", "Last night passed.") for w in rng.sample(PLACES, 3)],
    ]
    for tl, en in cases:
        writer, calls, invalid = fake_spark([unsafe_answer(tl, en)])
        recap = run_build(RecapBuilder(BANK, CONTENT, spark=writer))
        assert recap.source is RecapSource.LINE_BANK, (tl, en)
        assert len(calls) == 1
        assert invalid == ["gm_invalid:UnsafeRecap"]


def test_good_spark_text_passes_and_uses_only_labels() -> None:
    answer = unsafe_answer(*valid_texts())
    writer, calls, invalid = fake_spark([answer])
    recap = run_build(RecapBuilder(BANK, CONTENT, spark=writer))
    assert recap.source is RecapSource.SPARK
    assert invalid == []
    assert "Migs" not in calls[0]["input"]
    restored = restore_recap_names(recap, {"P1": "Migs"})
    assert "Migs" in restored.text_tl


def test_spark_repair_then_fallback_is_bounded_at_two_calls() -> None:
    writer, calls, _ = fake_spark(["{}", "also bad", "never used"])
    recap = run_build(RecapBuilder(BANK, CONTENT, spark=writer))
    assert recap.source is RecapSource.LINE_BANK
    assert len(calls) == 2


@pytest.mark.parametrize(
    "error",
    [
        MetaError("down"),
        ValueError("bad"),
        TypeError("bad"),
        KeyError("bad"),
        OSError("bad"),
        TimeoutError("slow"),
    ],
)
def test_failing_writers_fall_back_to_the_line_bank(error: Exception) -> None:
    class Failing:
        async def write(self, _: NightSummary) -> None:
            raise error

    builder = RecapBuilder(BANK, CONTENT, spark=Failing())  # type: ignore[arg-type]
    recap = run_build(builder)
    assert recap.source is RecapSource.LINE_BANK
    assert recap == build_line_bank_recap(base_summary(), BANK)


def test_hanging_writer_times_out_to_the_line_bank() -> None:
    class Slow:
        async def write(self, _: NightSummary) -> None:
            await asyncio.sleep(5)

    builder = RecapBuilder(BANK, CONTENT, spark=Slow(), timeout_s=0.05)  # type: ignore[arg-type]
    assert run_build(builder).source is RecapSource.LINE_BANK


def test_offline_never_calls_spark_and_local_build_matches() -> None:
    writer, calls, _ = fake_spark([unsafe_answer(*valid_texts())])
    builder = RecapBuilder(BANK, CONTENT, spark=writer)
    recap = run_build(builder, offline=True)
    assert calls == []
    assert recap == builder.build_local(base_summary())


def glimmer_for(content: str) -> GlimmerClient:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"message": {"content": content}})

    return GlimmerClient(URL, CONTENT, None, transport=httpx2.MockTransport(handler))


@pytest.mark.parametrize("raw", BAD_JSON[:12])
def test_bad_glimmer_json_falls_back_to_the_line_bank(raw: str) -> None:
    builder = RecapBuilder(BANK, CONTENT, glimmer=glimmer_for(raw))
    assert run_build(builder, offline=True).source is RecapSource.LINE_BANK


def test_glimmer_profanity_and_unsafe_text_fall_back() -> None:
    rng = random.Random(11)
    for word in rng.sample(PROFANE, 15):
        content = unsafe_answer(f"Kagabi, {word}.", "Last night passed.")
        builder = RecapBuilder(BANK, CONTENT, glimmer=glimmer_for(content))
        assert run_build(builder, offline=True).source is RecapSource.LINE_BANK
    for tl, en in (
        ("Kagabi, 99 ang natalo.", "99 fell."),
        ("Tahimik.", "Quiet."),
    ):
        builder = RecapBuilder(
            BANK, CONTENT, glimmer=glimmer_for(unsafe_answer(tl, en))
        )
        assert run_build(builder, offline=True).source is RecapSource.LINE_BANK


def test_recap_json_round_trip_and_garbage_only_raises_recap_error() -> None:
    rng = random.Random(12)
    recap = build_line_bank_recap(base_summary(), BANK)
    assert Recap.from_json(recap.to_json()) == recap
    values: list[Any] = [
        None,
        True,
        False,
        0,
        1,
        -1,
        1.5,
        "",
        "x",
        [],
        {},
        ["a"],
        {"a": 1},
    ]
    good = recap.to_dict()
    for _ in range(600):
        data = dict(good)
        for key in rng.sample(list(good), rng.randint(1, 3)):
            if rng.random() < 0.3:
                del data[key]
            else:
                data[key] = rng.choice(values)
        try:
            parsed = Recap.from_json(json.dumps(data))
        except RecapError:
            continue
        assert parsed.text_tl
        assert isinstance(parsed.night, int)
    alphabet = string.printable + "ñ"
    for _ in range(300):
        raw = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
        with pytest.raises(RecapError):
            Recap.from_json(raw)
    for raw in ("[]", "null", "1", '"x"', "true"):
        with pytest.raises(RecapError):
            Recap.from_json(raw)

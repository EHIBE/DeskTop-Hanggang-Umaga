import asyncio
import json
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import httpx2
import pytest

from db.store import ApiUsageRecord
from gm.glimmer import (
    GLIMMER_URL_ENV,
    GlimmerClient,
    glimmer_from_env,
    normalize_glimmer_url,
)
from gm.narrator import LineBank
from gm.recap import (
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
from gm.schemas import ContentFilter, Mood, SchemaError, parse_recap, recap_json_schema
from meta_client import CostMeter, MetaClient, create_openai_client
from tests.test_meta_client import MemoryLog

CONTENT = ContentFilter()
BANK = LineBank()
URL = "http://127.0.0.1:11434"
EM_DASH = chr(0x2014)

NEW_MOMENTS = (
    "kapre_smoke_telegraph",
    "kapre_smoke_hit",
    "unit_lost",
    "unit_returned",
    "ownership_confirm",
    "badge_earned",
    "scar_gained",
    "object_recognized",
    "recap_win",
    "recap_lose",
    "recap_badge",
    "recap_scar",
)


def summary(
    outcome: RecapOutcome = RecapOutcome.SUNRISE,
    units: tuple[RecapUnit, ...] | None = None,
) -> NightSummary:
    return NightSummary(
        night=2,
        outcome=outcome,
        turns_survived=8,
        enemies_beaten=5,
        units_downed=1,
        units=(
            units
            if units is not None
            else (
                RecapUnit("Spearman", "reach", "P1", badges=("+1 HP",)),
                RecapUnit("Albu", "healer", "P2", scarred=True, downed=True),
            )
        ),
        players=("P1", "P2"),
    )


def recap_json(
    tl: str = "Kagabi, nakaligtas ang baryo sa 8 dilim.",
    en: str = "Last night the barrio survived 8 turns.",
) -> str:
    return json.dumps({"recap_tl": tl, "recap_en": en})


def test_new_moments_are_in_bank_and_clean() -> None:
    for moment in NEW_MOMENTS:
        assert moment in BANK.moments
        for tl, en, _ in BANK.lines(moment):
            for text in (tl, en):
                assert CONTENT.is_safe_narration(text), (moment, text)
                assert ";" not in text
                assert EM_DASH not in text


def test_fill_replaces_placeholders() -> None:
    tl, en, _ = BANK.fill("ownership_confirm", "x", {"player": "Migs", "unit": "Albu"})
    assert tl == "Kay Migs ang Albu. Ituloy?"
    assert "Migs" in en
    tl, _, _ = BANK.fill("unit_lost", "x", {"unit": "Albu"})
    assert tl == "Ang Albu ay nawala sa gubat!"


def test_line_bank_recap_win_with_badge() -> None:
    recap = build_line_bank_recap(summary(), BANK)
    assert recap.source is RecapSource.LINE_BANK
    assert recap.text_tl.startswith("Kagabi")
    assert "Spearman" in recap.text_tl
    assert "[" not in recap.text_tl
    assert "[" not in recap.text_en
    assert recap.mood is Mood.UMAGA
    assert len(recap.text_tl) <= 480
    assert recap_text_ok((recap.text_tl, recap.text_en), summary(), CONTENT)


def test_line_bank_recap_defeat_and_scar() -> None:
    units = (RecapUnit("Albu", "healer", "P2", scarred=True),)
    recap = build_line_bank_recap(summary(RecapOutcome.DEFEAT, units), BANK)
    assert recap.mood is Mood.KABA
    assert "Albu" in recap.text_tl
    assert recap.text_tl.startswith("Kagabi")


def test_line_bank_recap_without_highlight() -> None:
    plain = summary(units=(RecapUnit("Albu", "healer"),))
    recap = build_line_bank_recap(plain, BANK)
    assert "Albu" not in recap.text_tl


def test_summary_rejects_real_player_names() -> None:
    with pytest.raises(RecapError):
        NightSummary(1, RecapOutcome.SUNRISE, 8, 1, 0, players=("Migs",))
    with pytest.raises(RecapError):
        NightSummary(
            1, RecapOutcome.SUNRISE, 8, 1, 0, units=(RecapUnit("A", "wall", "Migs"),)
        )


def test_recap_round_trips_json() -> None:
    recap = build_line_bank_recap(summary(), BANK)
    assert Recap.from_json(recap.to_json()) == recap
    assert Recap.from_dict(recap.to_dict()) == recap


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        "{}",
        json.dumps(
            {
                "night": "1",
                "text_tl": "a",
                "text_en": "b",
                "mood": "umaga",
                "source": "spark",
            }
        ),
        json.dumps(
            {
                "night": 1,
                "text_tl": "a",
                "text_en": "b",
                "mood": "bad",
                "source": "spark",
            }
        ),
        json.dumps(
            {
                "night": 1,
                "text_tl": "a",
                "text_en": "b",
                "mood": "umaga",
                "source": "gemini",
            }
        ),
        json.dumps(
            {
                "night": 1,
                "text_tl": "",
                "text_en": "b",
                "mood": "umaga",
                "source": "spark",
            }
        ),
    ],
)
def test_recap_from_json_rejects_bad_input(raw: str) -> None:
    with pytest.raises(RecapError):
        Recap.from_json(raw)


def test_restore_names_swaps_only_p_labels() -> None:
    recap = Recap(
        1,
        "Kagabi, bayani si P1.",
        "P1 and P3 were brave.",
        Mood.UMAGA,
        RecapSource.SPARK,
    )
    out = restore_recap_names(recap, {"P1": "Migs"})
    assert out.text_tl == "Kagabi, bayani si Migs."
    assert out.text_en == "Migs and P3 were brave."


def test_recap_schema_is_strict() -> None:
    schema: Any = recap_json_schema()
    assert schema["additionalProperties"] is False
    assert schema["required"] == list(schema["properties"]) == ["recap_tl", "recap_en"]


def test_parse_recap_rejects_extra_and_missing() -> None:
    assert parse_recap(recap_json()).recap_tl.startswith("Kagabi")
    with pytest.raises(SchemaError):
        parse_recap(json.dumps({"recap_tl": "Kagabi", "recap_en": "x", "extra": 1}))
    with pytest.raises(SchemaError):
        parse_recap(json.dumps({"recap_tl": "Kagabi"}))
    with pytest.raises(SchemaError):
        parse_recap(recap_json(tl="K" * 241))


@pytest.mark.parametrize(
    ("tl", "en"),
    [
        ("Tahimik ang gabi.", "Quiet night."),
        ("Kagabi, 99 ang natalo.", "Last night 99 fell."),
        ("Kagabi, bayani si P4.", "P4 was brave."),
        ("Kagabi, gumalaw si u_spear.", "Last night u_spear moved."),
        ("Kagabi, nasa Manila ang kubo.", "Last night the kubo was in Manila."),
    ],
)
def test_recap_text_check_rejects(tl: str, en: str) -> None:
    assert not recap_text_ok((tl, en), summary(), CONTENT)


def test_recap_text_check_accepts_known_numbers_and_players() -> None:
    assert recap_text_ok(
        (
            "Kagabi, 8 dilim, 5 natalo, bayani si P1.",
            "Last night 8 turns, 5 beaten, P1.",
        ),
        summary(),
        CONTENT,
    )


class FakeResponses:
    def __init__(self, answers: list[str]) -> None:
        self.answers = answers
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_text=self.answers.pop(0),
            id=f"resp_{len(self.calls)}",
            usage=SimpleNamespace(
                input_tokens=100,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
                output_tokens=20,
            ),
        )


def spark_writer(
    answers: list[str], invalid: list[str]
) -> tuple[SparkRecapWriter, FakeResponses]:
    client = MetaClient(
        create_openai_client("test-key"),
        CostMeter(MemoryLog(starting_total=Decimal(0))),
    )
    responses = FakeResponses(answers)
    sdk = SimpleNamespace(responses=responses)
    client.sdk = lambda: sdk  # type: ignore[method-assign, assignment, return-value]
    return SparkRecapWriter(client, CONTENT, invalid.append), responses


def glimmer_client(
    handler: Any, usage: list[ApiUsageRecord] | None = None
) -> GlimmerClient:
    return GlimmerClient(
        URL,
        CONTENT,
        usage.append if usage is not None else None,
        transport=httpx2.MockTransport(handler),
    )


def ollama_ok(content: str) -> Any:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"message": {"content": content}})

    return handler


def build(builder: RecapBuilder, offline: bool = False, glimmer: bool = True) -> Recap:
    return asyncio.run(builder.build(summary(), offline, glimmer))


def test_spark_recap_success_sends_contract_call() -> None:
    invalid: list[str] = []
    writer, responses = spark_writer([recap_json()], invalid)
    recap = build(RecapBuilder(BANK, CONTENT, spark=writer))
    assert recap.source is RecapSource.SPARK
    assert recap.text_tl.startswith("Kagabi")
    assert invalid == []
    call = responses.calls[0]
    assert call["model"] == "muse-spark-1.3"
    assert call["store"] is False
    fmt = call["extra_body"]["text"]["format"]
    assert fmt["name"] == "night_recap"
    assert fmt["strict"] is True
    payload = json.loads(call["input"])
    assert payload["players"] == ["P1", "P2"]
    assert "Migs" not in call["input"]


def test_spark_recap_repairs_once() -> None:
    invalid: list[str] = []
    writer, responses = spark_writer(["{}", recap_json()], invalid)
    recap = build(RecapBuilder(BANK, CONTENT, spark=writer))
    assert recap.source is RecapSource.SPARK
    assert len(invalid) == 1
    assert "failed validation" in responses.calls[1]["input"]


def test_spark_recap_two_failures_use_line_bank() -> None:
    invalid: list[str] = []
    writer, _ = spark_writer(["{}", "{}"], invalid)
    recap = build(RecapBuilder(BANK, CONTENT, spark=writer))
    assert recap.source is RecapSource.LINE_BANK
    assert len(invalid) == 2


def test_spark_recap_unsafe_uses_line_bank_and_logs() -> None:
    invalid: list[str] = []
    bad = recap_json(tl="Kagabi, 77 ang natalo.", en="Last night 77 fell.")
    writer, _ = spark_writer([bad], invalid)
    recap = build(RecapBuilder(BANK, CONTENT, spark=writer))
    assert recap.source is RecapSource.LINE_BANK
    assert invalid == ["gm_invalid:UnsafeRecap"]


def test_offline_skips_spark() -> None:
    writer, responses = spark_writer([recap_json()], [])
    recap = build(RecapBuilder(BANK, CONTENT, spark=writer), offline=True)
    assert recap.source is RecapSource.LINE_BANK
    assert responses.calls == []


def test_no_models_uses_line_bank() -> None:
    assert build(RecapBuilder(BANK, CONTENT)).source is RecapSource.LINE_BANK


def test_builder_timeout_uses_line_bank() -> None:
    class Slow:
        async def write(self, _: NightSummary) -> None:
            await asyncio.sleep(1)

    builder = RecapBuilder(BANK, CONTENT, spark=Slow(), timeout_s=0.05)  # type: ignore[arg-type]
    assert build(builder).source is RecapSource.LINE_BANK


def test_glimmer_recap_is_labeled_and_logged() -> None:
    usage: list[ApiUsageRecord] = []
    client = glimmer_client(ollama_ok(recap_json()), usage)
    recap = build(RecapBuilder(BANK, CONTENT, glimmer=client))
    assert recap.source is RecapSource.GLIMMER
    assert len(usage) == 1
    assert usage[0].kind == "glimmer"
    assert usage[0].cost_usd == Decimal(0)
    assert usage[0].ok is True


def test_glimmer_request_shape() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json={"message": {"content": recap_json()}})

    build(RecapBuilder(BANK, CONTENT, glimmer=glimmer_client(handler)))
    assert str(seen[0].url) == f"{URL}/api/chat"
    body = json.loads(seen[0].content)
    assert body["stream"] is False
    assert body["format"]["additionalProperties"] is False
    assert body["messages"][0]["role"] == "system"


def test_glimmer_unreachable_falls_back_to_spark() -> None:
    usage: list[ApiUsageRecord] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("down", request=request)

    writer, _ = spark_writer([recap_json()], [])
    builder = RecapBuilder(
        BANK, CONTENT, spark=writer, glimmer=glimmer_client(handler, usage)
    )
    assert build(builder).source is RecapSource.SPARK
    assert usage[0].ok is False


def test_glimmer_unreachable_offline_uses_line_bank() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(503)

    builder = RecapBuilder(BANK, CONTENT, glimmer=glimmer_client(handler))
    assert build(builder, offline=True).source is RecapSource.LINE_BANK


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        json.dumps({"recap_tl": "Kagabi", "extra": 1}),
        recap_json(tl="Tahimik ang gabi.", en="Quiet."),
        recap_json(tl="Kagabi, 99 ang natalo.", en="99 fell."),
        recap_json(tl="Kagabi, putang ina.", en="Last night, damn it all."),
    ],
)
def test_glimmer_bad_output_falls_back(content: str) -> None:
    builder = RecapBuilder(BANK, CONTENT, glimmer=glimmer_client(ollama_ok(content)))
    assert build(builder).source is RecapSource.LINE_BANK


def test_glimmer_bad_payload_shape_falls_back() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"oops": 1})

    builder = RecapBuilder(BANK, CONTENT, glimmer=glimmer_client(handler))
    assert build(builder).source is RecapSource.LINE_BANK


def test_glimmer_disabled_by_flag() -> None:
    calls: list[int] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return httpx2.Response(200, json={"message": {"content": recap_json()}})

    builder = RecapBuilder(BANK, CONTENT, glimmer=glimmer_client(handler))
    assert build(builder, glimmer=False).source is RecapSource.LINE_BANK
    assert calls == []


def test_glimmer_banter() -> None:
    client = glimmer_client(
        ollama_ok(recap_json(tl="Hoy, tabi-tabi po!", en="Hey, excuse us!"))
    )
    text = asyncio.run(client.banter("duwende", "steals a charm"))
    assert text is not None
    assert text.source == "glimmer"
    assert text.text_tl == "Hoy, tabi-tabi po!"


def test_glimmer_banter_rejects_numbers_and_unknown_speaker() -> None:
    numbered = glimmer_client(
        ollama_ok(recap_json(tl="Tatlo kayo, 3!", en="Three, 3!"))
    )
    assert asyncio.run(numbered.banter("kapre", "smoke")) is None
    assert asyncio.run(numbered.banter("dragon", "smoke")) is None


def test_glimmer_url_env() -> None:
    assert normalize_glimmer_url(None) is None
    assert normalize_glimmer_url("") is None
    assert normalize_glimmer_url("   ") is None
    assert normalize_glimmer_url("http://localhost:11434/") == "http://localhost:11434"
    assert normalize_glimmer_url("https://127.0.0.1:11434") is None
    assert normalize_glimmer_url("http://example.com:11434") is None
    assert normalize_glimmer_url("http://[::1:11434") is None
    assert glimmer_from_env(CONTENT, environ={}) is None
    assert glimmer_from_env(CONTENT, environ={GLIMMER_URL_ENV: ""}) is None
    assert glimmer_from_env(CONTENT, environ={GLIMMER_URL_ENV: URL}) is not None
    custom = glimmer_from_env(
        CONTENT, environ={GLIMMER_URL_ENV: URL, "DESKTOP_GLIMMER_MODEL": "glimmer:30b"}
    )
    assert custom is not None

import asyncio
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from gm.narrator import (
    LINES_PATH,
    REQUIRED_MOMENTS,
    LineBank,
    LineBankError,
    LineBankNarrator,
    Narration,
    NarrationEnemy,
    NarrationPhase,
    NarrationRequest,
    NarrationSource,
    NarrationUnit,
    SparkNarrator,
)
from gm.prompts import GM_SYSTEM_PROMPT, gm_input_text
from gm.schemas import (
    ContentFilter,
    Mood,
    SchemaError,
    gm_turn_json_schema,
    parse_gm_turn,
)
from meta_client import (
    CostMeter,
    MetaClient,
    MetaUnavailableError,
    create_openai_client,
)
from rules.resolve import Edge, Event, EventType
from tests.test_meta_client import MemoryLog

CONTENT = ContentFilter()
BANK = LineBank()
IDS = ["u_kubo", "u_spear", "e_aswang_1"]
UNITS = (
    NarrationUnit("u_spear", "Spearman", "reach", 4, 4, "Migs"),
    NarrationUnit("u_albu", "Albu", "healer", 0, 3, None),
)
ENEMIES = (
    NarrationEnemy("e_aswang_1", "aswang", 2),
    NarrationEnemy("e_tikbalang_1", "tikbalang", 3),
)
PHASE = NarrationPhase.RESOLUTION_THEN_TELEGRAPH.value
EM_DASH = chr(0x2014)


def request(
    events: tuple[Event, ...] = (),
    phase: str = PHASE,
    turn: int = 3,
    night: int = 1,
    kubo_hp: int = 7,
) -> NarrationRequest:
    return NarrationRequest(
        night=night,
        turn=turn,
        phase=phase,
        difficulty="normal",
        kubo_hp=kubo_hp,
        kubo_hp_max=10,
        units=UNITS,
        enemies=ENEMIES,
        events=events,
    )


def turn_json(
    tl: str = "Tinamaan ang aswang!",
    en: str = "The aswang was hit!",
    hint: str = "",
    callouts: list[dict[str, str]] | None = None,
) -> str:
    return json.dumps(
        {
            "narration_tl": tl,
            "narration_en": en,
            "mood": "kaba",
            "callouts": callouts if callouts is not None else [],
            "hint_tl": hint,
        }
    )


def test_schema_is_strict_and_uses_allowed_ids() -> None:
    schema: Any = gm_turn_json_schema(IDS)
    assert schema["additionalProperties"] is False
    assert schema["required"] == list(schema["properties"])
    props = schema["properties"]
    assert props["mood"]["enum"] == ["kalmado", "kaba", "takot", "tagumpay", "umaga"]
    assert props["callouts"]["maxItems"] == 4
    item = props["callouts"]["items"]
    assert item["additionalProperties"] is False
    assert item["required"] == ["entity_id", "text_tl"]
    assert item["properties"]["entity_id"]["enum"] == IDS
    assert item["properties"]["text_tl"]["maxLength"] == 60
    assert props["narration_tl"]["maxLength"] == 240
    assert props["hint_tl"]["maxLength"] == 120


def test_parse_success() -> None:
    raw = turn_json(callouts=[{"entity_id": "u_spear", "text_tl": "Sibak!"}])
    turn = parse_gm_turn(raw, IDS)
    assert turn.mood is Mood.KABA
    assert turn.callouts[0].entity_id == "u_spear"


def test_parse_drops_unknown_callouts() -> None:
    raw = turn_json(
        callouts=[
            {"entity_id": "u_ghost", "text_tl": "Hoy"},
            {"entity_id": "u_kubo", "text_tl": "Kapit"},
        ]
    )
    turn = parse_gm_turn(raw, IDS)
    assert [c.entity_id for c in turn.callouts] == ["u_kubo"]


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "{}",
        turn_json().replace('"kaba"', '"galit"'),
        turn_json(tl="x" * 241),
        turn_json().replace("}", ', "extra": 1}'),
        turn_json(callouts=[{"entity_id": "u_kubo", "text_tl": "x" * 61}]),
        turn_json(callouts=[{"entity_id": "u_kubo", "text_tl": "a"}] * 5),
    ],
)
def test_parse_rejects_invalid(raw: str) -> None:
    with pytest.raises(SchemaError):
        parse_gm_turn(raw, IDS)


def test_line_bank_loads_every_moment() -> None:
    assert set(REQUIRED_MOMENTS) <= set(BANK.moments)
    assert len(BANK.moments) == len(REQUIRED_MOMENTS)


def test_line_bank_rejects_missing_moment(tmp_path: Path) -> None:
    path = tmp_path / "lines.json"
    path.write_text(json.dumps({"version": 1, "moments": {}}), encoding="utf-8")
    with pytest.raises(LineBankError):
        LineBank(path)


def test_every_line_is_safe_and_clean() -> None:
    for moment in BANK.moments:
        for tl, en, _ in BANK.lines(moment):
            for text in (tl, en):
                assert CONTENT.is_safe_narration(text), (moment, text)
                assert ";" not in text
                assert EM_DASH not in text
                assert len(text) <= 240


def test_lines_file_has_no_semicolon_or_em_dash() -> None:
    raw = LINES_PATH.read_text(encoding="utf-8")
    assert ";" not in raw
    assert EM_DASH not in raw


def spawn(edge: Edge, enemy: str = "e_aswang_1") -> Event:
    return Event(EventType.SPAWN, enemy, edge=edge)


def pick(req: NarrationRequest) -> str:
    return BANK.pick(req).narration_tl


def quiet_lines() -> set[str]:
    return {tl for tl, _, _ in BANK.lines("quiet")}


def test_priority_lose_and_win() -> None:
    assert "Nasira" in pick(request(phase="defeat"))
    assert "Nasira" in pick(request((Event(EventType.LOSE),)))
    assert "Sumikat" in pick(request(phase="sunrise"))
    assert "Sumikat" in pick(request((Event(EventType.WIN),)))
    both = request((Event(EventType.WIN), Event(EventType.LOSE)))
    assert "Nasira" in pick(both)


def test_priority_night_start_beats_events() -> None:
    hit = Event(EventType.KUBO_HIT, "e_aswang_1", "u_kubo", 1)
    assert "Lumulubog" in pick(request((hit,), "night_start"))


def test_kubo_hit_fills_hp() -> None:
    events = (
        Event(EventType.ATTACK, "e_aswang_1", "u_kubo", 1),
        Event(EventType.KUBO_HIT, "e_aswang_1", "u_kubo", 1),
    )
    narration = BANK.pick(request(events, kubo_hp=6))
    assert "6 na lang" in narration.narration_tl
    assert "6 left" in narration.narration_en
    assert "[HP]" not in narration.narration_tl


def test_unit_down_fills_name() -> None:
    narration = BANK.pick(request((Event(EventType.DOWN, "e_aswang_1", "u_albu"),)))
    assert narration.narration_tl == "Bagsak si Albu. Bawi tayo."
    assert "[unit]" not in narration.narration_en


def test_spawn_by_type_and_edge() -> None:
    assert "hilaga" in pick(request((spawn(Edge.NORTH),)))
    assert "silangan" in pick(request((spawn(Edge.EAST),)))
    assert "timog" in pick(request((spawn(Edge.SOUTH),)))
    assert "kanluran" in pick(request((spawn(Edge.WEST),)))
    assert "Tikbalang" in pick(request((spawn(Edge.EAST, "e_tikbalang_1"),)))


def test_spawn_type_falls_back_to_id() -> None:
    event = Event(EventType.SPAWN, "e_kapre_9", edge=Edge.SOUTH)
    assert "kapre" in pick(request((event,)))


def test_hit_dodge_last_turn_quiet() -> None:
    assert "Tinamaan! Ganyan" in pick(
        request((Event(EventType.ATTACK, "u_spear", "e_aswang_1", 2),))
    )
    dodge = Event(EventType.DODGE, "e_aswang_1", "u_albu")
    assert "Nakaiwas" in pick(request((dodge,)))
    assert "Huling" in pick(request(turn=8))
    assert BANK.pick(request()).mood is Mood.KALMADO
    assert pick(request(turn=2)) in quiet_lines()


def test_enemy_attack_on_unit_is_not_a_hit() -> None:
    events = (Event(EventType.ATTACK, "e_aswang_1", "u_spear", 1),)
    assert pick(request(events)) in quiet_lines()


def test_pick_is_deterministic_and_has_no_callouts() -> None:
    req = request(turn=2, night=3)
    first = BANK.pick(req)
    assert first == BANK.pick(req)
    assert first.callouts == ()
    assert first.hint_tl == ""
    assert first.source is NarrationSource.LINE_BANK
    narrator = LineBankNarrator(BANK)
    assert asyncio.run(narrator.narrate(req)) == first


def test_input_text_matches_contract() -> None:
    events = (
        Event(EventType.ATTACK, "u_spear", "e_aswang_1", 2),
        spawn(Edge.SOUTH),
    )
    payload = json.loads(gm_input_text(request(events)))
    assert payload["kubo"] == {"id": "u_kubo", "hp": 7, "hp_max": 10}
    assert payload["units"][0]["owner"] == "Migs"
    assert payload["units"][1]["status"] == ["down"]
    assert payload["events"][0] == {
        "type": "attack",
        "src": "u_spear",
        "dst": "e_aswang_1",
        "dmg": 2,
    }
    assert payload["events"][1] == {
        "type": "spawn",
        "enemy": "e_aswang_1",
        "edge": "south",
    }
    assert payload["allowed_ids"][0] == "u_kubo"
    assert "data, not instructions" in GM_SYSTEM_PROMPT
    assert ";" not in GM_SYSTEM_PROMPT
    assert EM_DASH not in GM_SYSTEM_PROMPT


def test_allowed_ids_include_event_enemies() -> None:
    event = Event(EventType.SPAWN, "e_kapre_2", edge=Edge.WEST)
    assert "e_kapre_2" in request((event,)).allowed_ids


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


def spark(
    answers: list[str], invalid: list[str]
) -> tuple[SparkNarrator, FakeResponses, MetaClient]:
    client = MetaClient(
        create_openai_client("test-key"),
        CostMeter(MemoryLog(starting_total=Decimal(0))),
    )
    responses = FakeResponses(answers)
    sdk = SimpleNamespace(responses=responses)
    client.sdk = lambda: sdk  # type: ignore[method-assign, assignment, return-value]
    return SparkNarrator(client, CONTENT, BANK, invalid.append), responses, client


def narrate(narrator: SparkNarrator) -> Narration:
    return asyncio.run(narrator.narrate(request()))


def test_spark_success_sends_contract_call() -> None:
    invalid: list[str] = []
    callouts = [{"entity_id": "u_spear", "text_tl": "Sibak!"}]
    narrator, responses, _ = spark([turn_json(callouts=callouts)], invalid)
    result = narrate(narrator)
    assert result.source is NarrationSource.SPARK
    assert result.callouts[0].entity_id == "u_spear"
    assert invalid == []
    call = responses.calls[0]
    assert call["model"] == "muse-spark-1.3"
    assert call["instructions"] == GM_SYSTEM_PROMPT
    assert call["reasoning"] == {"effort": "low"}
    assert call["store"] is False
    assert "previous_response_id" not in call
    fmt = call["extra_body"]["text"]["format"]
    assert fmt["name"] == "gm_turn"
    assert fmt["strict"] is True
    entity = fmt["schema"]["properties"]["callouts"]["items"]["properties"]
    assert entity["entity_id"]["enum"] == list(request().allowed_ids)


def test_spark_repairs_once_then_succeeds() -> None:
    invalid: list[str] = []
    narrator, responses, _ = spark(["{}", turn_json()], invalid)
    assert narrate(narrator).source is NarrationSource.SPARK
    assert len(invalid) == 1
    assert invalid[0].startswith("gm_invalid:")
    assert "failed validation" in responses.calls[1]["input"]


def test_spark_two_failures_use_line_bank() -> None:
    invalid: list[str] = []
    narrator, _, _ = spark(["{}", "not json"], invalid)
    assert narrate(narrator).source is NarrationSource.LINE_BANK
    assert len(invalid) == 2


def test_spark_meta_error_uses_line_bank() -> None:
    invalid: list[str] = []
    narrator, _, client = spark([], invalid)

    async def failing(*args: object, **kwargs: object) -> None:
        raise MetaUnavailableError("down")

    client.execute = failing  # type: ignore[method-assign, assignment]
    assert narrate(narrator).source is NarrationSource.LINE_BANK
    assert invalid == []


def test_spark_unsafe_narration_uses_line_bank() -> None:
    invalid: list[str] = []
    text = "Nasa Manila ang aswang"
    assert CONTENT.names_place(text)
    narrator, _, _ = spark([turn_json(tl=text)], invalid)
    assert narrate(narrator).source is NarrationSource.LINE_BANK
    assert invalid == ["gm_invalid:UnsafeNarration"]


def test_spark_unsafe_callout_is_dropped() -> None:
    callouts = [
        {"entity_id": "u_spear", "text_tl": "Sibak!"},
        {"entity_id": "u_kubo", "text_tl": "Nasa Manila"},
    ]
    narrator, _, _ = spark([turn_json(callouts=callouts)], [])
    result = narrate(narrator)
    assert [c.entity_id for c in result.callouts] == ["u_spear"]


def test_spark_unknown_id_in_text_uses_line_bank() -> None:
    invalid: list[str] = []
    narrator, _, _ = spark([turn_json(tl="Tinamaan si u_ghost!")], invalid)
    assert narrate(narrator).source is NarrationSource.LINE_BANK
    assert len(invalid) == 1


def test_spark_known_id_in_text_is_accepted() -> None:
    narrator, _, _ = spark([turn_json(tl="Sibak ni u_spear!")], [])
    assert narrate(narrator).source is NarrationSource.SPARK

import json
import logging
import random
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import cast, get_args

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from config import AppSettings
from meta_client import CostMeter, MetaClient
from server import MAX_MESSAGE_BYTES, create_app, websocket_origins
from tests.test_meta_client import MemoryLog
from tests.test_server import ORIGIN, TOKEN, connect, make_factory
from tests.test_server_messages import (
    CAMPAIGN_NEW,
    CORNERS,
    START_CASES,
    UUID_A,
    Harness,
    Msg,
    Wire,
    last_state,
    notices,
    reach_night,
)

SEED = 20261104
UNEXPECTED = "unexpected error while handling a message"


@pytest.fixture
def live(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> Iterator[tuple[Harness, Wire]]:
    built = Harness(tmp_path)
    caplog.set_level(logging.INFO, logger="desktop.server")
    with built.client, connect(built.client) as ws:
        wire = Wire(ws)
        assert wire.until("state")["phase"] == "START"
        yield built, wire
    assert not [r for r in caplog.records if UNEXPECTED in r.getMessage()]


@pytest.fixture(scope="module")
def shared(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Harness]:
    built = Harness(tmp_path_factory.mktemp("shared"))
    with built.client:
        yield built


@pytest.fixture
def shared_live(shared: Harness) -> Iterator[tuple[Harness, Wire]]:
    with connect(shared.client) as ws:
        wire = Wire(ws)
        assert wire.until("state")["phase"] == "START"
        yield shared, wire


def still_works(wire: Wire) -> None:
    got = wire.exchange({"type": "campaign.list"})
    assert got[0]["type"] == "campaigns"
    assert notices(got) == []


def settle(wire: Wire) -> None:
    wire.ws.send_text('{"type":"crops.get"}')
    wire.until("crops")
    wire.until("state")


def nested_array(depth: int) -> str:
    return "[" * depth + "]" * depth


def nested_object(depth: int) -> str:
    return '{"a":' * depth + "1" + "}" * depth


MALFORMED: list[tuple[str, str]] = [
    ("empty", ""),
    ("space", " "),
    ("not_json", "not json"),
    ("null", "null"),
    ("true", "true"),
    ("number", "42"),
    ("string", '"campaign.list"'),
    ("array", "[]"),
    ("array_of_message", '[{"type":"campaign.list"}]'),
    ("empty_object", "{}"),
    ("type_null", '{"type":null}'),
    ("type_number", '{"type":5}'),
    ("type_list", '{"type":["campaign.list"]}'),
    ("type_object", '{"type":{"x":1}}'),
    ("type_empty", '{"type":""}'),
    ("type_case", '{"type":"Campaign.List"}'),
    ("type_space", '{"type":"campaign.list "}'),
    ("type_nul", '{"type":"campaign.list\\u0000"}'),
    ("unknown_type", '{"type":"format.disk"}'),
    ("proto", '{"type":"__proto__"}'),
    ("trailing_comma", '{"type":"campaign.list",}'),
    ("single_quotes", "{'type':'campaign.list'}"),
    ("trailing_garbage", '{"type":"campaign.list"} x'),
    ("two_objects", '{"type":"campaign.list"}{"type":"campaign.list"}'),
    ("truncated", '{"type":"campaign.li'),
    ("bom", '\ufeff{"type":"campaign.list"}'),
    ("extra_field", '{"type":"campaign.list","extra":1}'),
    ("extra_null", '{"type":"campaign.list","x":null}'),
    ("deep_array", nested_array(5000)),
    ("deep_object", nested_object(2500)),
    ("deep_in_field", '{"type":"campaign.list","x":' + nested_array(4000) + "}"),
    ("deep_in_name", '{"type":"summon.name","name":' + nested_array(4000) + "}"),
    ("nan", '{"type":"camera.select","index":NaN}'),
    ("infinity", '{"type":"camera.select","index":Infinity}'),
    ("neg_infinity", '{"type":"camera.select","index":-Infinity}'),
    ("overflow_float", '{"type":"camera.select","index":1e999}'),
    ("float_index", '{"type":"camera.select","index":1.0}'),
    ("neg_index", '{"type":"camera.select","index":-1}'),
    ("big_index", '{"type":"camera.select","index":6}'),
    ("huge_int", '{"type":"camera.select","index":' + "9" * 300 + "}"),
    ("exp_index", '{"type":"camera.select","index":1e0}'),
    ("string_index", '{"type":"camera.select","index":"0"}'),
    ("bool_index", '{"type":"camera.select","index":true}'),
    ("null_index", '{"type":"camera.select","index":null}'),
    ("hex_index", '{"type":"camera.select","index":0x1}'),
    (
        "corners_nan",
        (
            '{"type":"calibrate.corners","corners":[[NaN,0],[1,0],[1,1],[0,1]],'
            '"play_w_cm":60,"play_h_cm":40}'
        ),
    ),
    (
        "corners_inf",
        (
            '{"type":"calibrate.corners","corners":[[1e999,0],[1,0],[1,1],[0,1]],'
            '"play_w_cm":60,"play_h_cm":40}'
        ),
    ),
    (
        "corners_huge",
        (
            '{"type":"calibrate.corners","corners":[[1e308,0],[1,0],[1,1],[0,1]],'
            '"play_w_cm":60,"play_h_cm":40}'
        ),
    ),
    (
        "corners_three",
        (
            '{"type":"calibrate.corners","corners":[[0,0],[1,0],[1,1]],'
            '"play_w_cm":60,"play_h_cm":40}'
        ),
    ),
    (
        "corners_five",
        (
            '{"type":"calibrate.corners","corners":[[0,0],[1,0],[1,1],[0,1],[5,5]],'
            '"play_w_cm":60,"play_h_cm":40}'
        ),
    ),
    (
        "corners_triple",
        (
            '{"type":"calibrate.corners","corners":[[0,0,0],[1,0],[1,1],[0,1]],'
            '"play_w_cm":60,"play_h_cm":40}'
        ),
    ),
    (
        "width_nan",
        (
            '{"type":"calibrate.corners","corners":[[0,0],[1,0],[1,1],[0,1]],'
            '"play_w_cm":NaN,"play_h_cm":40}'
        ),
    ),
    (
        "width_small",
        (
            '{"type":"calibrate.corners","corners":[[0,0],[1,0],[1,1],[0,1]],'
            '"play_w_cm":-60,"play_h_cm":40}'
        ),
    ),
    (
        "width_big",
        (
            '{"type":"calibrate.corners","corners":[[0,0],[1,0],[1,1],[0,1]],'
            '"play_w_cm":1e30,"play_h_cm":40}'
        ),
    ),
    ("tap_negative", '{"type":"summon.tap","point":[-1,0]}'),
    ("tap_big", '{"type":"summon.tap","point":[10001,0]}'),
    ("tap_inf", '{"type":"summon.tap","point":[1e999,1]}'),
    ("tap_huge", '{"type":"summon.tap","point":[' + "9" * 50 + ",1]}"),
    ("tap_float", '{"type":"summon.tap","point":[1.5,1]}'),
    ("tap_short", '{"type":"summon.tap","point":[1]}'),
    ("tap_object", '{"type":"summon.tap","point":{"x":1,"y":1}}'),
    ("name_number", '{"type":"summon.name","name":5}'),
    ("name_null", '{"type":"summon.name","name":null}'),
    ("name_list", '{"type":"summon.name","name":["a"]}'),
    ("name_long", '{"type":"summon.name","name":"' + "x" * 41 + '"}'),
    ("name_missing", '{"type":"summon.name"}'),
    ("id_short", '{"type":"unit.reroll","unit_id":"abc"}'),
    ("id_long", '{"type":"unit.reroll","unit_id":"' + "a" * 37 + '"}'),
    ("id_number", '{"type":"unit.reroll","unit_id":36}'),
    ("game_id_bad", '{"type":"claim.tap","player_name":"A","unit_ids":["u_x"]}'),
    (
        "game_id_many",
        '{"type":"claim.tap","player_name":"A","unit_ids":'
        + json.dumps(["u_1"] * 13)
        + "}",
    ),
    ("game_id_str", '{"type":"claim.tap","player_name":"A","unit_ids":"u_1"}'),
    (
        "action_bad",
        '{"type":"intent.tap","unit_id":"u_1","action":"nuke","target_id":null}',
    ),
    (
        "target_inj",
        '{"type":"intent.tap","unit_id":"u_1","action":"attack","target_id":"e_a_1; DROP"}',
    ),
    ("target_missing", '{"type":"intent.tap","unit_id":"u_1","action":"attack"}'),
    (
        "target_nl",
        '{"type":"intent.tap","unit_id":"u_1","action":"attack","target_id":"u_1\\n"}',
    ),
    (
        "unit_id_nl",
        '{"type":"intent.tap","unit_id":"u_1\\n","action":"attack","target_id":null}',
    ),
    ("force_string", '{"type":"night.resume","force":"yes"}'),
    ("force_int", '{"type":"night.resume","force":1}'),
    ("on_int", '{"type":"demo_safe","on":1}'),
    ("on_null", '{"type":"demo_safe","on":null}'),
    ("mode_bad", '{"type":"voice.mode","mode":"shout"}'),
    ("mode_case", '{"type":"voice.mode","mode":"PTT"}'),
    ("down_str", '{"type":"ptt","down":"true"}'),
    ("badge_bad", '{"type":"badge.pick","unit_id":"u_1","badge":"atk"}'),
    ("settings_float", '{"type":"settings.set","key":"camera_device","value":1.5}'),
    ("settings_null", '{"type":"settings.set","key":"camera_device","value":null}'),
    ("settings_list", '{"type":"settings.set","key":"mic_device","value":["a"]}'),
    ("settings_obj", '{"type":"settings.set","key":"mic_device","value":{}}'),
    ("settings_nan", '{"type":"settings.set","key":"camera_device","value":NaN}'),
    ("settings_empty", '{"type":"settings.set","key":"mic_device","value":""}'),
    (
        "settings_long",
        '{"type":"settings.set","key":"mic_device","value":"' + "m" * 201 + '"}',
    ),
    ("settings_nokey", '{"type":"settings.set","value":1}'),
    ("settings_key_num", '{"type":"settings.set","key":1,"value":1}'),
    (
        "campaign_both",
        '{"type":"campaign.start","campaign_id":"' + UUID_A + '","new":{"name":"x"}}',
    ),
    ("campaign_neither", '{"type":"campaign.start"}'),
    ("campaign_new_str", '{"type":"campaign.start","new":"x"}'),
    ("campaign_new_empty", '{"type":"campaign.start","new":{}}'),
    ("campaign_new_extra", '{"type":"campaign.start","new":{"name":"x","tier":1}}'),
    (
        "campaign_diff_null_str",
        '{"type":"campaign.start","new":{"name":"x","difficulty":"null"}}',
    ),
    (
        "campaign_name_long",
        '{"type":"campaign.start","new":{"name":"' + "n" * 41 + '"}}',
    ),
    ("consent_agree_str", '{"type":"consent","player_name":"A","agree":"true"}'),
    (
        "consent_long",
        '{"type":"consent","player_name":"' + "p" * 25 + '","agree":true}',
    ),
    ("one_mb_name", '{"type":"summon.name","name":"' + "x" * 1_000_000 + '"}'),
    ("one_mb_junk", "x" * 1_000_000),
    ("one_mb_unicode", '{"type":"summon.name","name":"' + "é" * 500_000 + '"}'),
    ("one_mb_array", "[" + "0," * 500_000 + "0]"),
    ("limit_plus_one", "x" * (MAX_MESSAGE_BYTES + 1)),
    ("limit_multibyte", "é" * (MAX_MESSAGE_BYTES // 2 + 1)),
    ("lone_surrogate", '{"type":"summon.name","name":"\\ud800"}'),
    ("surrogate_pair_broken", '{"type":"summon.name","name":"\\ud83d"}'),
    ("control_chars", '{"type":"summon.name","name":"\\u0001\\u0002"}'),
    ("raw_newline_in_string", '{"type":"summon.name","name":"a\nb"}'),
    ("raw_tab_in_string", '{"type":"summon.name","name":"a\tb"}'),
]


@pytest.mark.parametrize(
    "raw", [case[1] for case in MALFORMED], ids=[case[0] for case in MALFORMED]
)
def test_malformed_input_never_breaks_the_socket(
    shared_live: tuple[Harness, Wire], raw: str
) -> None:
    _, wire = shared_live
    got = wire.exchange(raw)
    assert set(notices(got)) <= {"cmd.unknown"}
    still_works(wire)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not json",
        "null",
        "[]",
        "{}",
        '{"type":null}',
        '{"type":"nope"}',
        '{"type":"campaign.list","extra":1}',
        nested_array(5000),
        "x" * (MAX_MESSAGE_BYTES + 1),
        '{"type":"camera.select","index":NaN}',
    ],
)
def test_malformed_input_gets_exactly_one_unknown_notice(
    shared_live: tuple[Harness, Wire], raw: str
) -> None:
    _, wire = shared_live
    assert notices(wire.exchange(raw)) == ["cmd.unknown"]


def test_empty_binary_and_oversized_binary_frames(
    shared_live: tuple[Harness, Wire],
) -> None:
    _, wire = shared_live
    for payload in (b"", b"\x00", b"\xff\xfe\x00", b"{}" * 10_000, bytes(range(256))):
        wire.ws.send_bytes(payload)
        assert wire.read()["copy_key"] == "cmd.unknown"
    still_works(wire)


def test_text_just_under_the_limit_is_parsed_not_size_rejected(
    shared_live: tuple[Harness, Wire],
) -> None:
    _, wire = shared_live
    pad = " " * (MAX_MESSAGE_BYTES - len('{"type":"campaign.list"}'))
    got = wire.exchange('{"type":"campaign.list"}' + pad)
    assert got[0]["type"] == "campaigns"


def test_text_at_the_limit_plus_one_is_rejected(
    shared_live: tuple[Harness, Wire],
) -> None:
    _, wire = shared_live
    pad = " " * (MAX_MESSAGE_BYTES + 1 - len('{"type":"campaign.list"}'))
    assert notices(wire.exchange('{"type":"campaign.list"}' + pad)) == ["cmd.unknown"]


NAMES = [
    "Ñandú",
    "名前",
    "🧌🔥",
    "a\u0000b",
    "\u0000",
    "x\u202ey",
    "e\u0301" * 20,
    "  padded  ",
    "   ",
    "\t",
    "a\nb",
    "'; DROP TABLE campaign; --",
    "<script>alert(1)</script>",
    "../../etc/passwd",
    "C:\\Windows\\System32",
    "%s%s%n",
    "{{7*7}}",
    "\u200b",
    "a" * 40,
    "🧌" * 40,
]


def test_odd_campaign_names_do_not_break_the_server(
    shared_live: tuple[Harness, Wire],
) -> None:
    _, wire = shared_live
    for name in NAMES:
        got = wire.exchange({"type": "campaign.start", "new": {"name": name}})
        assert set(notices(got)) <= {"cmd.unknown", "err.generic"}, name
        wire.exchange({"type": "calibrate.back"})
        still_works(wire)


def test_odd_unit_and_player_names_in_a_night(live: tuple[Harness, Wire]) -> None:
    _, wire = live
    reach_night(wire)
    for name in ("\u0000", "🧌🔥", "a\u0000b", "../x", "<b>", "x\u202ey"):
        got = wire.exchange(
            {"type": "claim.tap", "player_name": name, "unit_ids": ["u_2"]}
        )
        assert set(notices(got)) <= {"cmd.unknown", "claim.who", "err.generic"}
        still_works(wire)


def valid_payloads() -> list[Msg]:
    return [dict(case[1]) for case in START_CASES] + [
        {"type": "settings.set", "key": "tts_enabled", "value": False},
        dict(CAMPAIGN_NEW),
        dict(CORNERS),
    ]


WRONG_VALUES: list[object] = [
    None,
    True,
    False,
    0,
    -1,
    1,
    10**30,
    1.5,
    -0.0,
    "",
    " ",
    "x",
    "x" * 100,
    "\u0000",
    [],
    [None],
    ["a"],
    {},
    {"a": 1},
]


def mutants(rng: random.Random, payload: Msg) -> list[Msg]:
    out: list[Msg] = []
    out.append({**payload, "extra": rng.choice(WRONG_VALUES)})
    for key in payload:
        trimmed = {k: v for k, v in payload.items() if k != key}
        out.append(trimmed)
        for value in rng.sample(WRONG_VALUES, 2):
            out.append({**payload, key: value})
    return out


def test_field_mutations_of_every_message_are_refused_or_handled(
    shared_live: tuple[Harness, Wire],
) -> None:
    _, wire = shared_live
    rng = random.Random(SEED)
    count = 0
    for payload in valid_payloads():
        if payload["type"] in ("campaign.start", "calibrate.back"):
            continue
        for mutant in mutants(rng, payload):
            got = wire.exchange(mutant)
            assert all(
                m["type"]
                in (
                    "notice",
                    "state",
                    "settings",
                    "devices",
                    "campaigns",
                    "crops",
                    "card",
                    "sprite",
                    "events",
                    "narration",
                    "moment",
                    "caption",
                    "summon.result",
                    "recap",
                    "map",
                    "cost",
                )
                for m in got
            )
            count += 1
    assert count > 150
    still_works(wire)


def test_extra_field_on_every_message_type_is_refused(
    shared_live: tuple[Harness, Wire],
) -> None:
    _, wire = shared_live
    for payload in valid_payloads():
        if payload["type"] in ("campaign.start",):
            continue
        got = wire.exchange({**payload, "smuggled": 1})
        assert notices(got) == ["cmd.unknown"], payload["type"]
    still_works(wire)


def test_missing_type_on_every_message_is_refused(
    shared_live: tuple[Harness, Wire],
) -> None:
    _, wire = shared_live
    for payload in valid_payloads():
        stripped = {k: v for k, v in payload.items() if k != "type"}
        assert notices(wire.exchange(stripped)) == ["cmd.unknown"]


def random_json(rng: random.Random, depth: int = 0) -> object:
    kinds = ["null", "bool", "int", "float", "str", "list", "dict"]
    kind = rng.choice(kinds if depth < 3 else kinds[:5])
    if kind == "null":
        return None
    if kind == "bool":
        return rng.random() < 0.5
    if kind == "int":
        return rng.choice([0, 1, -1, 5, 255, 10_000, 10_001, 2**63, -(2**63), 10**25])
    if kind == "float":
        return rng.choice([0.0, 0.5, -3.25, 1e300, -1e300, 59.999, 120.001])
    if kind == "str":
        pool = [
            "",
            "x",
            "Mug",
            "u_1",
            "u_kubo",
            "e_aswang_1",
            "attack",
            "hp",
            "ptt",
            UUID_A,
            "\u0000",
            "é",
            "🧌",
        ]
        return rng.choice(pool)
    if kind == "list":
        return [random_json(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    return {
        rng.choice(["type", "name", "on", "x"]): random_json(rng, depth + 1)
        for _ in range(rng.randint(0, 3))
    }


def test_seeded_random_structures(shared_live: tuple[Harness, Wire]) -> None:
    _, wire = shared_live
    rng = random.Random(SEED + 1)
    for _ in range(120):
        value = random_json(rng)
        text = json.dumps(value)
        got = wire.exchange(text)
        assert set(notices(got)) <= {"cmd.unknown"}
    still_works(wire)


def test_seeded_random_bytes_and_text(shared_live: tuple[Harness, Wire]) -> None:
    _, wire = shared_live
    rng = random.Random(SEED + 2)
    alphabet = '{}[]",:0123456789.-eE truefalsnl\\\u0000é🧌type'
    for _ in range(100):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 120)))
        got = wire.exchange(text)
        assert set(notices(got)) <= {"cmd.unknown"}
    for _ in range(25):
        wire.ws.send_bytes(bytes(rng.randrange(256) for _ in range(rng.randint(0, 64))))
        assert wire.read()["copy_key"] == "cmd.unknown"
    still_works(wire)


def test_seeded_mutations_of_valid_messages_over_a_whole_run(
    shared_live: tuple[Harness, Wire],
) -> None:
    _, wire = shared_live
    rng = random.Random(SEED + 3)
    pool = [
        p
        for p in valid_payloads()
        if p["type"] not in ("campaign.start", "calibrate.back", "calibrate.restart")
    ]
    for _ in range(150):
        payload = dict(rng.choice(pool))
        move = rng.randrange(4)
        keys = list(payload)
        if move == 0 and len(keys) > 1:
            del payload[rng.choice([k for k in keys if k != "type"])]
        elif move == 1:
            target = rng.choice(keys)
            payload[target] = rng.choice(WRONG_VALUES)
        elif move == 2:
            payload[rng.choice(["a", "b", "type2"])] = rng.choice(WRONG_VALUES)
        wire.exchange(payload)
    still_works(wire)


def test_duplicate_type_keys_do_not_crash(shared_live: tuple[Harness, Wire]) -> None:
    _, wire = shared_live
    got = wire.exchange('{"type":"nope","type":"campaign.list"}')
    assert set(notices(got)) <= {"cmd.unknown"}
    still_works(wire)


@pytest.fixture
def served(tmp_path: Path) -> Iterator[TestClient]:
    settings = AppSettings(
        token=TOKEN, data_dir=tmp_path / "data", port=8765, api_key=None
    )
    with TestClient(
        create_app(settings, frozenset({ORIGIN}), make_factory(tmp_path))
    ) as client:
        yield client


@pytest.fixture
def bare(tmp_path: Path) -> TestClient:
    settings = AppSettings(
        token=TOKEN, data_dir=tmp_path / "data", port=8765, api_key=None
    )
    return TestClient(create_app(settings, frozenset({ORIGIN}), make_factory(tmp_path)))


BAD_TOKENS = [
    None,
    "",
    " ",
    "wrong",
    TOKEN[:-1],
    TOKEN + "x",
    TOKEN + " ",
    " " + TOKEN,
    "T" * 63,
    "T" * 64,
    TOKEN + "," + TOKEN,
    TOKEN + "\u0000",
    "0" * 64,
]


@pytest.mark.parametrize(
    "token", BAD_TOKENS, ids=[str(i) for i in range(len(BAD_TOKENS))]
)
def test_http_rejects_a_bad_token_on_every_route(
    bare: TestClient, token: str | None
) -> None:
    headers = {} if token is None else {"x-desktop-token": token}
    for path in ("/health", "/ws", "/nope"):
        try:
            response = bare.get(path, headers=headers)
        except UnicodeEncodeError:
            continue
        assert response.status_code == 401
        assert response.json() == {"detail": "unauthorized"}


def test_http_duplicate_token_headers(bare: TestClient) -> None:
    wrong_first = bare.get(
        "/health", headers=[("x-desktop-token", "bad"), ("x-desktop-token", TOKEN)]
    )
    assert wrong_first.status_code == 401
    joined = bare.get("/health", headers={"x-desktop-token": f"{TOKEN}, {TOKEN}"})
    assert joined.status_code == 401
    both_wrong = bare.get(
        "/health", headers=[("x-desktop-token", "a"), ("x-desktop-token", "b")]
    )
    assert both_wrong.status_code == 401


def test_http_token_in_other_places_is_not_accepted(bare: TestClient) -> None:
    assert bare.get(f"/health?token={TOKEN}").status_code == 401
    assert (
        bare.get("/health", headers={"authorization": f"Bearer {TOKEN}"}).status_code
        == 401
    )
    assert (
        bare.get("/health", headers={"cookie": f"x-desktop-token={TOKEN}"}).status_code
        == 401
    )
    assert (
        bare.get("/health", headers={"X-Desktop-Token-Extra": TOKEN}).status_code == 401
    )
    assert (
        bare.get(
            "/health", headers={"sec-websocket-protocol": f"desktop, {TOKEN}"}
        ).status_code
        == 401
    )


def test_http_header_name_is_case_insensitive_and_token_works(bare: TestClient) -> None:
    for name in ("X-Desktop-Token", "x-desktop-token", "X-DESKTOP-TOKEN"):
        assert bare.get("/health", headers={name: TOKEN}).status_code == 200


TRAVERSAL_PATHS = [
    "/",
    "/..",
    "/../",
    "/../../etc/passwd",
    "/..%2f..%2fetc/passwd",
    "/%2e%2e/%2e%2e/windows/win.ini",
    "/sprites/../../x",
    "/sprites/a.png",
    "/crops",
    "/health/..",
    "/health/../ws",
    "//health",
    "/openapi.json",
    "/docs",
    "/.env",
    "/backend/.env",
]


@pytest.mark.parametrize(
    "path", TRAVERSAL_PATHS, ids=[str(i) for i in range(len(TRAVERSAL_PATHS))]
)
def test_routes_outside_the_api_serve_nothing(bare: TestClient, path: str) -> None:
    response = bare.get(
        path, headers={"x-desktop-token": TOKEN}, follow_redirects=False
    )
    if path in ("/health/..", "/health/../ws", "//health"):
        assert response.status_code in (200, 307, 308, 404)
        return
    assert response.status_code == 404
    assert "root:" not in response.text
    assert "[fonts]" not in response.text


@pytest.mark.parametrize("method", ["post", "put", "delete", "patch", "options"])
def test_health_only_allows_get(bare: TestClient, method: str) -> None:
    response = getattr(bare, method)("/health", headers={"x-desktop-token": TOKEN})
    assert response.status_code == 405
    assert getattr(bare, method)("/health").status_code == 401


def test_head_health_is_not_a_bypass(bare: TestClient) -> None:
    assert bare.head("/health").status_code == 401


def reject(client: TestClient, protocols: list[str], origin: str | None) -> int:
    headers = {} if origin is None else {"origin": origin}
    with (
        pytest.raises(WebSocketDisconnect) as info,
        client.websocket_connect("/ws", subprotocols=protocols, headers=headers) as ws,
    ):
        ws.receive_text()
    return int(info.value.code)


BAD_PROTOCOLS: list[list[str]] = [
    [],
    ["desktop"],
    ["desktop", ""],
    ["desktop", " "],
    ["desktop", "wrong"],
    ["desktop", TOKEN[:-1]],
    ["desktop", TOKEN + "x"],
    ["desktop", TOKEN, "extra"],
    [TOKEN],
    [TOKEN, "desktop"],
    ["Desktop", TOKEN],
    ["desktop-v2", TOKEN],
    [f"desktop, {TOKEN}, {TOKEN}"],
    ["desktop", TOKEN.upper()],
]


@pytest.mark.parametrize(
    "protocols", BAD_PROTOCOLS, ids=[str(i) for i in range(len(BAD_PROTOCOLS))]
)
def test_websocket_rejects_bad_subprotocol_shapes(
    bare: TestClient, protocols: list[str]
) -> None:
    assert reject(bare, protocols, ORIGIN) == 1008


def test_websocket_ignores_the_http_token_header(bare: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as info,
        bare.websocket_connect(
            "/ws", headers={"origin": ORIGIN, "x-desktop-token": TOKEN}
        ) as ws,
    ):
        ws.receive_text()
    assert info.value.code == 1008


def test_websocket_rejects_the_token_in_the_query_string(bare: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as info,
        bare.websocket_connect(f"/ws?token={TOKEN}", headers={"origin": ORIGIN}) as ws,
    ):
        ws.receive_text()
    assert info.value.code == 1008


BAD_ORIGINS: list[str | None] = [
    None,
    "",
    " ",
    "null",
    "NULL",
    "file://",
    "http://localhost:5173/",
    "HTTP://LOCALHOST:5173",
    "http://localhost:5174",
    "http://localhost:5173.evil.test",
    "http://evil.test",
    "http://evil.test, http://localhost:5173",
    "*",
]


@pytest.mark.parametrize(
    "origin", BAD_ORIGINS, ids=[str(i) for i in range(len(BAD_ORIGINS))]
)
def test_websocket_rejects_wrong_origins_even_with_the_token(
    bare: TestClient, origin: str | None
) -> None:
    assert reject(bare, ["desktop", TOKEN], origin) == 1008


def test_rejected_sockets_do_not_block_a_good_one(served: TestClient) -> None:
    for _ in range(5):
        assert reject(served, ["desktop", "wrong"], ORIGIN) == 1008
        assert reject(served, ["desktop", TOKEN], "http://evil.test") == 1008
    with connect(served) as ws:
        assert Wire(ws).until("state")["phase"] == "START"


def test_accepted_socket_negotiates_the_desktop_subprotocol(served: TestClient) -> None:
    with connect(served) as ws:
        assert ws.accepted_subprotocol == "desktop"


@pytest.mark.parametrize(
    ("packaged", "origin", "ok"),
    [
        (True, "null", True),
        (False, "null", False),
        (True, "file://", True),
        (False, "file://", True),
        (True, "http://evil.test", False),
        (False, "NULL", False),
        (True, "Null", False),
    ],
)
def test_null_origin_in_dev_and_packaged(
    tmp_path: Path, packaged: bool, origin: str, ok: bool
) -> None:
    settings = AppSettings(
        token=TOKEN, data_dir=tmp_path / "data", port=8765, api_key=None
    )
    origins = websocket_origins("file://", packaged)
    client = TestClient(create_app(settings, origins, make_factory(tmp_path)))
    with client:
        if ok:
            with connect(client, TOKEN, origin) as ws:
                assert Wire(ws).until("state")["phase"] == "START"
        else:
            assert reject(client, ["desktop", TOKEN], origin) == 1008


def test_websocket_origins_parsing() -> None:
    assert websocket_origins("", False) == frozenset()
    assert websocket_origins("", True) == frozenset({"null"})
    assert websocket_origins(" a ,, b ,", False) == frozenset({"a", "b"})
    assert websocket_origins("null", False) == frozenset({"null"})


def test_two_sockets_get_independent_sequences_and_shared_state(
    served: TestClient,
) -> None:
    with connect(served) as first, connect(served) as second:
        a, b = Wire(first), Wire(second)
        assert a.until("state")["phase"] == "START"
        assert b.until("state")["phase"] == "START"
        a.exchange({"type": "campaign.start", "new": {"name": "Shared"}})
        got = b.exchange({"type": "devices.list"})
        assert any(m["type"] == "devices" for m in got)
        state = b.exchange({"type": "settings.get"})
        assert last_state(state)["phase"] in ("CALIBRATE", "START")
        assert a.last_seq > 0 and b.last_seq > 0


def test_closing_one_socket_leaves_the_other_working(served: TestClient) -> None:
    with connect(served) as keeper:
        wire = Wire(keeper)
        wire.until("state")
        with connect(served) as leaver:
            other = Wire(leaver)
            other.until("state")
            other.exchange({"type": "campaign.list"})
        still_works(wire)
        with connect(served) as third:
            assert Wire(third).until("state")["phase"] == "START"


def test_broadcast_reaches_every_socket(tmp_path: Path) -> None:
    built = Harness(tmp_path)
    with built.client, connect(built.client) as first, connect(built.client) as second:
        a, b = Wire(first), Wire(second)
        a.until("state")
        b.until("state")
        services = built.services[0]
        loop = services.controller._loop
        assert loop is not None
        loop.call_soon_threadsafe(
            lambda: services.broadcast.publish(
                {"type": "notice", "copy_key": "x.y", "params": {}}
            )
        )
        assert a.until("notice")["copy_key"] == "x.y"
        assert b.until("notice")["copy_key"] == "x.y"


def test_rapid_repeated_messages_all_answered_in_order(
    shared_live: tuple[Harness, Wire],
) -> None:
    _, wire = shared_live
    for _ in range(150):
        wire.ws.send_text('{"type":"campaign.list"}')
    seen = 0
    while seen < 150:
        if wire.read()["type"] == "campaigns":
            seen += 1
    settle(wire)
    still_works(wire)


def test_rapid_mixed_valid_and_invalid_messages(
    shared_live: tuple[Harness, Wire],
) -> None:
    _, wire = shared_live
    rng = random.Random(SEED + 4)
    expected_unknown = 0
    for _ in range(150):
        if rng.random() < 0.5:
            wire.ws.send_text(rng.choice(["not json", "{}", '{"type":"x"}', "[]"]))
            expected_unknown += 1
        else:
            wire.ws.send_text('{"type":"devices.list"}')
    wire.ws.send_text('{"type":"crops.get"}')
    unknown = 0
    while True:
        message = wire.read()
        if message["type"] == "notice" and message["copy_key"] == "cmd.unknown":
            unknown += 1
        if message["type"] == "crops":
            break
    assert unknown == expected_unknown


def test_threads_sending_at_once_on_one_socket(
    shared_live: tuple[Harness, Wire],
) -> None:
    _, wire = shared_live

    def blast() -> None:
        for _ in range(20):
            wire.ws.send_text('{"type":"campaign.list"}')

    threads = [threading.Thread(target=blast) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    seen = 0
    while seen < 80:
        if wire.read()["type"] == "campaigns":
            seen += 1
    settle(wire)
    still_works(wire)


def test_disconnect_right_after_sending_does_not_hurt_the_server(
    served: TestClient,
) -> None:
    payloads = [
        '{"type":"camera.select","index":0}',
        '{"type":"devices.list"}',
        '{"type":"campaign.start","new":{"name":"Gone"}}',
        '{"type":"demo_safe","on":true}',
        "garbage",
        "x" * 20_000,
    ]
    for index in range(18):
        with connect(served) as ws:
            ws.send_text(payloads[index % len(payloads)])
        with connect(served) as ws:
            ws.send_text(payloads[(index + 1) % len(payloads)])
            ws.close(code=1001)
    with connect(served) as ws:
        wire = Wire(ws)
        wire.until("state")
        still_works(wire)
    assert served.get("/health", headers={"x-desktop-token": TOKEN}).status_code == 200


def test_disconnect_with_a_slow_message_in_flight(served: TestClient) -> None:
    for _ in range(5):
        with connect(served) as ws:
            ws.send_text('{"type":"campaign.start","new":{"name":"Slow"}}')
            ws.send_text('{"type":"camera.select","index":0}')
            ws.send_text('{"type":"demo_safe","on":true}')
    with connect(served) as ws:
        wire = Wire(ws)
        wire.until("state")
        wire.exchange({"type": "demo_safe", "on": False})
        still_works(wire)


SETTING_MATRIX: dict[str, tuple[list[object], list[object]]] = {
    "camera_device": ([0, 1, 5], [-1, 6, 100, 10**30, True, False, "0", "a"]),
    "mic_device": (
        ["default", "3", "Mic", "a" * 200, "🧌", "a\u0000b"],
        [0, 5, True, False],
    ),
    "caption_language": (
        ["tl", "en"],
        ["fr", "EN", "Tl", "tl ", "tagalog", 1, True, "x" * 50],
    ),
    "difficulty": (
        ["easy", "normal", "hard"],
        ["madali", "mahirap", "Normal", "NORMAL", "medium", 1, True],
    ),
    "replay_enabled": ([True, False], [0, 1, "true", "yes", "false", "on"]),
    "tts_enabled": ([True, False], [0, 1, "true", "no"]),
    "show_real_objects": ([True, False], [0, 1, "true", "off"]),
    "strict_ownership": ([True, False], [0, 1, "true", "x"]),
    "generated_map": ([True, False], [0, 1, "true", "x"]),
}


def current(wire: Wire) -> dict[str, object]:
    values = wire.reply_of({"type": "settings.get"}, "settings")["values"]
    assert isinstance(values, dict)
    return dict(values)


def test_setting_matrix_covers_every_key() -> None:
    from server import SettingKey

    assert set(SETTING_MATRIX) == set(get_args(SettingKey))


@pytest.mark.parametrize("key", list(SETTING_MATRIX))
def test_valid_values_are_accepted_for_every_setting(
    shared_live: tuple[Harness, Wire], key: str
) -> None:
    _, wire = shared_live
    for value in SETTING_MATRIX[key][0]:
        got = wire.exchange({"type": "settings.set", "key": key, "value": value})
        assert notices(got) == []
        reply = next(m for m in got if m["type"] == "settings")
        values = cast(dict[str, object], reply["values"])
        if key == "tts_enabled":
            assert values[key] is False
        else:
            assert values[key] == value
        assert current(wire)[key] == values[key]


@pytest.mark.parametrize("key", list(SETTING_MATRIX))
def test_invalid_values_are_refused_and_change_nothing(
    shared_live: tuple[Harness, Wire], key: str
) -> None:
    _, wire = shared_live
    before = current(wire)
    for value in SETTING_MATRIX[key][1]:
        got = wire.exchange({"type": "settings.set", "key": key, "value": value})
        assert notices(got) == ["settings.invalid"], (key, value)
        assert not any(m["type"] == "settings" for m in got)
        assert current(wire) == before


SCHEMA_REJECTED_VALUES: list[object] = [
    None,
    1.5,
    -0.5,
    [],
    [1],
    {},
    {"a": 1},
    "",
    "x" * 201,
    float("nan"),
    float("inf"),
]


@pytest.mark.parametrize("key", list(SETTING_MATRIX))
def test_schema_level_bad_values_get_the_unknown_notice(
    shared_live: tuple[Harness, Wire], key: str
) -> None:
    _, wire = shared_live
    before = current(wire)
    for value in SCHEMA_REJECTED_VALUES:
        raw = json.dumps({"type": "settings.set", "key": key, "value": value})
        assert notices(wire.exchange(raw)) == ["cmd.unknown"], (key, value)
    assert current(wire) == before


@pytest.mark.parametrize(
    "key",
    [
        "nope",
        "",
        " ",
        "camera_device ",
        "Camera_Device",
        "__proto__",
        "constructor",
        "../x",
        "api_key",
        "token",
        "demo_safe",
        "camera_index",
        5,
        None,
        True,
    ],
)
def test_unknown_setting_keys_are_refused(
    shared_live: tuple[Harness, Wire], key: object
) -> None:
    _, wire = shared_live
    before = current(wire)
    assert notices(wire.exchange({"type": "settings.set", "key": key, "value": 1})) == [
        "cmd.unknown"
    ]
    assert current(wire) == before


def test_settings_set_requires_both_fields_and_forbids_extras(
    shared_live: tuple[Harness, Wire],
) -> None:
    _, wire = shared_live
    bad: list[Msg] = [
        {"type": "settings.set", "key": "difficulty"},
        {"type": "settings.set", "value": "easy"},
        {"type": "settings.set", "key": "difficulty", "value": "easy", "extra": 1},
    ]
    for payload in bad:
        assert notices(wire.exchange(payload)) == ["cmd.unknown"]


def test_camera_setting_is_refused_during_a_night(live: tuple[Harness, Wire]) -> None:
    _, wire = live
    reach_night(wire)
    got = wire.exchange({"type": "settings.set", "key": "camera_device", "value": 2})
    assert notices(got) == ["cmd.unknown"]
    ok = wire.exchange(
        {"type": "settings.set", "key": "caption_language", "value": "en"}
    )
    assert notices(ok) == []


def test_setting_values_survive_a_burst_of_changes(
    shared_live: tuple[Harness, Wire],
) -> None:
    _, wire = shared_live
    rng = random.Random(SEED + 5)
    expected = current(wire)
    for _ in range(120):
        key = rng.choice([k for k in SETTING_MATRIX if k != "camera_device"])
        good = rng.random() < 0.6
        pool = SETTING_MATRIX[key][0 if good else 1]
        value = rng.choice(pool)
        got = wire.exchange({"type": "settings.set", "key": key, "value": value})
        if good:
            expected[key] = False if key == "tts_enabled" else value
            assert notices(got) == []
        else:
            assert notices(got) == ["settings.invalid"]
    assert current(wire) == expected


def snapshot_of_files(root: Path) -> set[str]:
    return {
        str(p.relative_to(root))
        for p in root.rglob("*")
        if not p.name.startswith("desktop.db")
    }


TRAVERSAL_IDS = [
    "../" * 12,
    "..\\" * 12,
    "..%2f" * 7 + "..",
    "a" * 34 + "..",
    "/etc/passwd".ljust(36, "/"),
    "C:\\Windows\\System32\\drivers\\etc".ljust(36, "x"),
    "\\\\server\\share\\x".ljust(36, "x"),
    "../data/../data/../data/../data/..",
    "." * 36,
    "\u0000" * 36,
    "..\u0000/" * 9,
    "%00" * 12,
    "6f1d2a1e-7c1b-4c2e-9a3b-0a1b2c3d4e5f"[:-1] + "/",
    "6f1d2a1e-7c1b-4c2e-9a3b-0a1b2c3d4e/.",
    "6F1D2A1E-7C1B-4C2E-9A3B-0A1B2C3D4E5F",
    "6f1d2a1e7c1b4c2e9a3b0a1b2c3d4e5f0000",
    "{6f1d2a1e-7c1b-4c2e-9a3b-0a1b2c3d4e5}",
    "urn:uuid:6f1d2a1e-7c1b-4c2e-9a3b-0a1b2c",
]


def test_traversal_ids_touch_nothing_outside_the_data_dir(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    built = Harness(tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("keep")
    nearby = tmp_path / "data" / "campaigns" / "keepdir"
    nearby.mkdir(parents=True)
    (nearby / "f.txt").write_text("keep")
    before_outside = sorted(p.name for p in tmp_path.iterdir())
    before_inside = snapshot_of_files(tmp_path / "data")
    with built.client, connect(built.client) as ws:
        wire = Wire(ws)
        wire.until("state")
        for campaign_id in TRAVERSAL_IDS:
            padded = (
                campaign_id
                if len(campaign_id) == 36
                else campaign_id[:36].ljust(36, "x")
            )
            for kind in ("campaign.delete", "campaign.start"):
                got = wire.exchange({"type": kind, "campaign_id": padded})
                assert set(notices(got)) <= {
                    "cmd.unknown",
                    "delete.failed",
                    "err.generic",
                }
        still_works(wire)
    assert secret.read_text() == "keep"
    assert (nearby / "f.txt").read_text() == "keep"
    assert sorted(p.name for p in tmp_path.iterdir()) == before_outside
    assert snapshot_of_files(tmp_path / "data") >= before_inside
    assert not [r for r in caplog.records if UNEXPECTED in r.getMessage()]


def crops_of(wire: Wire) -> dict[str, str]:
    crops = wire.reply_of({"type": "crops.get"}, "crops")["crops"]
    assert isinstance(crops, dict)
    return cast(dict[str, str], crops)


def tamper(built: Harness, column_sql: str, value: str) -> None:
    store = built.controller._store
    with store._lock:
        store._conn.execute(column_sql, (value,))


def test_crops_never_read_outside_the_data_dir(tmp_path: Path) -> None:
    built = Harness(tmp_path)
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"TOP-SECRET-BYTES")
    with built.client, connect(built.client) as ws:
        wire = Wire(ws)
        wire.until("state")
        reach_night(wire)
        assert len(crops_of(wire)) == 3
        for hostile in (
            "../secret.png",
            r"..\secret.png",
            "../../secret.png",
            "sprites/../../secret.png",
        ):
            tamper(built, "UPDATE object_signature SET ref_crop_path = ?", hostile)
            got = crops_of(wire)
            assert got == {}
            assert "VE9QLVNFQ1JFVC1CWVRFUw==" not in json.dumps(got)
        still_works(wire)


def test_crops_refuse_an_absolute_path_outside_the_data_dir(tmp_path: Path) -> None:
    built = Harness(tmp_path)
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"TOP-SECRET-BYTES")
    with built.client, connect(built.client) as ws:
        wire = Wire(ws)
        wire.until("state")
        reach_night(wire)
        tamper(built, "UPDATE object_signature SET ref_crop_path = ?", str(secret))
        assert crops_of(wire) == {}


def test_a_tampered_sprite_path_is_not_followed_into_state(tmp_path: Path) -> None:
    built = Harness(tmp_path)
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"TOP-SECRET-BYTES")
    with built.client, connect(built.client) as ws:
        wire = Wire(ws)
        wire.until("state")
        reach_night(wire)
        tamper(built, "UPDATE sprite SET path = ?", "../secret.png")
        got = wire.exchange({"type": "campaign.list"})
        text = json.dumps(got)
        assert "VE9QLVNFQ1JFVC1CWVRFUw==" not in text
        still_works(wire)


def test_map_reply_only_reads_the_maps_folder(live: tuple[Harness, Wire]) -> None:
    built, wire = live
    wire.exchange(CAMPAIGN_NEW)
    outside = built.settings.data_dir / "secret.png"
    outside.write_bytes(b"TOP-SECRET-BYTES")
    wire.exchange({"type": "settings.set", "key": "generated_map", "value": True})
    got = wire.exchange({"type": "map.get"})
    assert notices(got) == ["map.none"]
    assert "VE9QLVNFQ1JFVC1CWVRFUw==" not in json.dumps(got)


def test_barrio_map_service_refuses_hostile_ids(tmp_path: Path) -> None:
    from vision.barrio_map import BarrioMapService

    meta = MetaClient(None, CostMeter(MemoryLog()))
    service = BarrioMapService(meta, tmp_path / "maps")
    (tmp_path / "secret.png").write_bytes(b"x")
    for hostile in (
        "../secret",
        "..\\secret",
        "../../secret",
        "/abs",
        "a/b",
        "",
        "a" * 200,
        "x\u0000",
    ):
        assert service.cached_map(hostile) is None
        with pytest.raises(ValueError):
            service.map_path(hostile)
        service.delete_map(hostile)
    assert (tmp_path / "secret.png").exists()

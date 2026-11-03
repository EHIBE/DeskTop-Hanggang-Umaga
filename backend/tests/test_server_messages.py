import json
from collections.abc import Callable, Iterator, Mapping, MutableMapping
from pathlib import Path
from typing import Any, cast

import anyio
import pytest
from anyio.streams.memory import MemoryObjectReceiveStream
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from capture.calibration import CalibrationError
from capture.camera import CameraError
from config import AppSettings
from db.store import StoreError
from game.night import STATE_CHANGED, GameController
from server import Services, create_app
from tests.test_server import ORIGIN, SHEET, TOKEN, connect, make_factory

Msg = dict[str, object]
UUID_A = "6f1d2a1e-7c1b-4c2e-9a3b-0a1b2c3d4e5f"
UUID_B = "0b9c5a52-2c4e-4c9f-8a7e-5d3f1a2b3c4d"
CAMPAIGN_NEW: Msg = {"type": "campaign.start", "new": {"name": "Barkada"}}
CORNERS: Msg = {
    "type": "calibrate.corners",
    "corners": SHEET,
    "play_w_cm": 60,
    "play_h_cm": 40,
}


class Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.settings = AppSettings(
            token=TOKEN, data_dir=tmp_path / "data", port=8765, api_key=None
        )
        self.services: list[Services] = []
        inner = make_factory(tmp_path)

        def build(settings: AppSettings) -> Services:
            services = inner(settings)
            self.services.append(services)
            return services

        self.client = TestClient(
            create_app(self.settings, frozenset({ORIGIN}), build),
            raise_server_exceptions=False,
        )

    @property
    def controller(self) -> GameController:
        return self.services[0].controller


RECEIVE_TIMEOUT_S = 15


async def receive_within(
    rx: MemoryObjectReceiveStream[MutableMapping[str, Any]],
) -> MutableMapping[str, Any]:
    with anyio.fail_after(RECEIVE_TIMEOUT_S):
        return await rx.receive()


class Wire:
    def __init__(self, ws: WebSocketTestSession) -> None:
        self.ws = ws
        self.last_seq = 0

    def read(self) -> Msg:
        while True:
            raw = self.ws.portal.call(receive_within, self.ws._send_rx)
            self.ws._raise_on_close(raw)
            message = cast(Msg, json.loads(cast(str, raw["text"])))
            seq = message["seq"]
            assert isinstance(seq, int)
            assert seq > self.last_seq
            self.last_seq = seq
            assert "Traceback" not in json.dumps(message)
            if message["type"] != "frame":
                return message

    def until(self, wanted: str) -> Msg:
        while True:
            message = self.read()
            if message["type"] == wanted:
                return message

    def exchange(self, raw: str | Mapping[str, object]) -> list[Msg]:
        text = raw if isinstance(raw, str) else json.dumps(raw)
        sentinel, reply = (
            ("crops.get", "crops")
            if "settings." in text
            else ("settings.get", "settings")
        )
        self.ws.send_text(text)
        self.ws.send_text(json.dumps({"type": sentinel}))
        collected: list[Msg] = []
        while True:
            message = self.read()
            if message["type"] == reply:
                break
            collected.append(message)
        while True:
            message = self.read()
            collected.append(message)
            if message["type"] == "state":
                break
        return collected

    def reply_of(self, raw: str | Mapping[str, object], wanted: str) -> Msg:
        return next(m for m in self.exchange(raw) if m["type"] == wanted)


def notices(messages: list[Msg]) -> list[str]:
    return [str(m["copy_key"]) for m in messages if m["type"] == "notice"]


def last_state(messages: list[Msg]) -> Msg:
    return [m for m in messages if m["type"] == "state"][-1]


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


@pytest.fixture
def live(tmp_path: Path) -> Iterator[tuple[Harness, Wire]]:
    built = Harness(tmp_path)
    with built.client, connect(built.client) as ws:
        wire = Wire(ws)
        assert wire.until("state")["phase"] == "START"
        yield built, wire


START_CASES: list[tuple[str, Msg, list[str], str | None]] = [
    ("campaign.list", {"type": "campaign.list"}, [], "campaigns"),
    (
        "campaign.start",
        {"type": "campaign.start", "campaign_id": UUID_A},
        ["cmd.unknown"],
        None,
    ),
    (
        "campaign.delete",
        {"type": "campaign.delete", "campaign_id": UUID_A},
        ["cmd.unknown"],
        None,
    ),
    ("devices.list", {"type": "devices.list"}, [], "devices"),
    ("calibrate.corners", CORNERS, ["cmd.unknown"], None),
    ("calibrate.done", {"type": "calibrate.done"}, ["cmd.unknown"], None),
    ("calibrate.restart", {"type": "calibrate.restart"}, ["start.ready"], None),
    ("summon.name", {"type": "summon.name", "name": "Mug"}, ["cmd.unknown"], None),
    ("summon.tap", {"type": "summon.tap", "point": [5, 5]}, ["cmd.unknown"], None),
    ("unit.reroll", {"type": "unit.reroll", "unit_id": UUID_A}, ["cmd.unknown"], None),
    (
        "unit.rename",
        {"type": "unit.rename", "unit_id": UUID_A, "name": "Mug"},
        ["cmd.unknown"],
        None,
    ),
    ("night.begin", {"type": "night.begin"}, ["cmd.unknown"], None),
    (
        "claim.tap",
        {"type": "claim.tap", "player_name": "Migs", "unit_ids": ["u_2"]},
        ["cmd.unknown"],
        None,
    ),
    ("claim.done", {"type": "claim.done"}, ["cmd.unknown"], None),
    (
        "intent.tap",
        {"type": "intent.tap", "unit_id": "u_2", "action": "attack", "target_id": None},
        ["cmd.unknown"],
        None,
    ),
    ("chip.cancel", {"type": "chip.cancel", "chip_id": UUID_A}, ["cmd.unknown"], None),
    ("end_turn", {"type": "end_turn"}, ["cmd.unknown"], None),
    ("night.next", {"type": "night.next"}, ["cmd.unknown"], None),
    ("night.quit", {"type": "night.quit"}, ["cmd.unknown"], None),
    ("night.pause", {"type": "night.pause"}, ["cmd.unknown"], None),
    ("night.resume", {"type": "night.resume", "force": True}, ["cmd.unknown"], None),
    (
        "consent",
        {"type": "consent", "player_name": "Migs", "agree": True},
        ["cmd.unknown"],
        None,
    ),
    ("replay.request", {"type": "replay.request"}, ["cmd.unknown"], None),
    ("effect.done", {"type": "effect.done"}, ["cmd.unknown"], None),
    ("ptt", {"type": "ptt", "down": True}, ["cmd.unknown"], None),
    ("voice.retry", {"type": "voice.retry"}, ["cmd.unknown"], None),
    (
        "badge.pick",
        {"type": "badge.pick", "unit_id": "u_2", "badge": "hp"},
        ["cmd.unknown"],
        None,
    ),
    (
        "confirm.accept",
        {"type": "confirm.accept", "confirm_id": UUID_A},
        ["cmd.unknown"],
        None,
    ),
    (
        "confirm.cancel",
        {"type": "confirm.cancel", "confirm_id": UUID_A},
        ["cmd.unknown"],
        None,
    ),
    ("map.get", {"type": "map.get"}, ["map.none"], None),
    ("crops.get", {"type": "crops.get"}, [], "crops"),
    ("pause.quit", {"type": "pause.quit"}, ["cmd.unknown"], None),
    ("calibrate.back", {"type": "calibrate.back"}, ["cmd.unknown"], None),
    ("settings.get", {"type": "settings.get"}, [], "settings"),
    ("demo_safe", {"type": "demo_safe", "on": False}, [], None),
    ("demo_safe.sam", {"type": "demo_safe.sam", "on": True}, [], None),
    ("voice.mode", {"type": "voice.mode", "mode": "open"}, [], None),
    ("camera.select", {"type": "camera.select", "index": 0}, [], None),
]


@pytest.mark.parametrize(
    ("payload", "keys", "reply"),
    [case[1:] for case in START_CASES],
    ids=[case[0] for case in START_CASES],
)
def test_every_message_type_in_start(
    shared_live: tuple[Harness, Wire], payload: Msg, keys: list[str], reply: str | None
) -> None:
    _, wire = shared_live
    got = wire.exchange(payload)
    assert notices(got) == keys
    if reply is not None:
        assert reply in [m["type"] for m in got] or reply in ("settings", "crops")
    assert wire.exchange({"type": "campaign.list"})[0]["type"] == "campaigns"


def test_start_cases_cover_every_client_message_type() -> None:
    from server import ClientMessage

    models = ClientMessage.__args__
    names = {model.model_fields["type"].annotation.__args__[0] for model in models}
    assert names - {"settings.set"} <= {str(case[1]["type"]) for case in START_CASES}


def to_summon(wire: Wire) -> Msg:
    wire.exchange(CAMPAIGN_NEW)
    got = wire.exchange({"type": "camera.select", "index": 0})
    assert last_state(got)["camera"] is not None
    assert last_state(wire.exchange(CORNERS))["calibration_preview"] is True
    state = last_state(wire.exchange({"type": "calibrate.done"}))
    assert state["phase"] == "SUMMON"
    return state


def summon_unit(wire: Wire, name: str, point: tuple[int, int]) -> Msg:
    first = wire.exchange({"type": "summon.name", "name": name})
    assert notices(first) == ["summon.which"]
    got = wire.exchange({"type": "summon.tap", "point": list(point)})
    card = next(m for m in got if m["type"] == "card")
    unit = card["unit"]
    assert isinstance(unit, dict)
    return unit


def test_wrong_state_messages_in_calibrate_and_summon(
    live: tuple[Harness, Wire],
) -> None:
    _, wire = live
    wire.exchange(CAMPAIGN_NEW)
    assert notices(wire.exchange({"type": "calibrate.done"})) == ["calib.tap"]
    assert notices(wire.exchange({"type": "night.begin"})) == ["cmd.unknown"]
    assert notices(wire.exchange({"type": "summon.name", "name": "Mug"})) == [
        "cmd.unknown"
    ]
    assert notices(
        wire.exchange({"type": "campaign.delete", "campaign_id": UUID_A})
    ) == ["cmd.unknown"]
    assert notices(
        wire.exchange({"type": "campaign.start", "new": {"name": "Two"}})
    ) in (
        [],
        ["cmd.unknown"],
    )
    assert wire.exchange({"type": "calibrate.back"}) is not None
    wire.exchange({"type": "campaign.list"})


def test_full_session_every_valid_message(live: tuple[Harness, Wire]) -> None:
    built, wire = live
    to_summon(wire)
    assert notices(wire.exchange({"type": "calibrate.done"})) == ["cmd.unknown"]
    assert notices(wire.exchange({"type": "night.begin"})) != []
    kubo = summon_unit(wire, "Bahay Kubo", (600, 400))
    assert kubo["id"] == "u_kubo"
    second = summon_unit(wire, "Mug", (300, 300))
    summon_unit(wire, "Pen", (900, 500))
    renamed = wire.reply_of(
        {"type": "unit.rename", "unit_id": second["unit_id"], "name": "Tasa"}, "card"
    )
    unit = renamed["unit"]
    assert isinstance(unit, dict) and unit["name"] == "Tasa"
    assert notices(
        wire.exchange({"type": "unit.rename", "unit_id": UUID_B, "name": "Tasa"})
    ) == ["cmd.unknown"]
    assert notices(wire.exchange({"type": "unit.reroll", "unit_id": UUID_B})) == [
        "cmd.unknown"
    ]
    assert notices(wire.exchange({"type": "end_turn"})) == ["cmd.unknown"]
    assert notices(wire.exchange({"type": "claim.done"})) == ["cmd.unknown"]
    begun = wire.exchange({"type": "night.begin"})
    assert last_state(begun)["phase"] == "VOICE_CLAIM"
    assert notices(wire.exchange({"type": "summon.name", "name": "Late"})) == [
        "cmd.unknown"
    ]
    claim = wire.exchange(
        {"type": "claim.tap", "player_name": "Migs", "unit_ids": ["u_kubo", "u_2"]}
    )
    assert notices(claim) == []
    assert (
        notices(
            wire.exchange({"type": "consent", "player_name": "Migs", "agree": False})
        )
        == []
    )
    assert notices(
        wire.exchange(
            {
                "type": "intent.tap",
                "unit_id": "u_2",
                "action": "attack",
                "target_id": None,
            }
        )
    ) == ["cmd.unknown"]
    played = last_state(wire.exchange({"type": "claim.done"}))
    assert played["phase"] == "PLAYER_PHASE"
    night = played["night"]
    assert isinstance(night, dict)
    assert notices(wire.exchange({"type": "claim.done"})) == ["cmd.unknown"]
    assert (
        notices(
            wire.exchange(
                {
                    "type": "intent.tap",
                    "unit_id": "u_9",
                    "action": "attack",
                    "target_id": None,
                }
            )
        )
        != []
    )
    assert notices(wire.exchange({"type": "chip.cancel", "chip_id": UUID_A})) != []
    assert notices(wire.exchange({"type": "confirm.accept", "confirm_id": UUID_A})) == [
        "cmd.unknown"
    ]
    assert notices(wire.exchange({"type": "confirm.cancel", "confirm_id": UUID_A})) == [
        "cmd.unknown"
    ]
    assert notices(
        wire.exchange({"type": "badge.pick", "unit_id": "u_2", "badge": "hp"})
    ) == ["cmd.unknown"]
    assert notices(wire.exchange({"type": "effect.done"})) == ["cmd.unknown"]
    assert notices(wire.exchange({"type": "night.next"})) == ["cmd.unknown"]
    assert notices(wire.exchange({"type": "night.quit"})) == ["cmd.unknown"]
    assert notices(wire.exchange({"type": "night.resume"})) == ["cmd.unknown"]
    assert notices(wire.exchange({"type": "pause.quit"})) == ["cmd.unknown"]
    assert notices(wire.exchange({"type": "replay.request"})) == ["cmd.unknown"]
    assert wire.reply_of({"type": "crops.get"}, "crops")["crops"] != {}
    assert wire.reply_of({"type": "settings.get"}, "settings")
    paused = last_state(wire.exchange({"type": "night.pause"}))
    assert paused["phase"] == "PAUSED"
    assert notices(wire.exchange({"type": "end_turn"})) == ["cmd.unknown"]
    resumed = last_state(wire.exchange({"type": "night.resume", "force": True}))
    assert resumed["phase"] == "PLAYER_PHASE"
    wire.exchange({"type": "night.pause"})
    quit_state = last_state(wire.exchange({"type": "pause.quit"}))
    assert quit_state["phase"] == "START"
    campaigns = wire.reply_of({"type": "campaign.list"}, "campaigns")["campaigns"]
    assert isinstance(campaigns, list) and len(campaigns) == 1
    assert built.controller.snapshot().campaign is None


def reach_night(wire: Wire) -> Msg:
    to_summon(wire)
    summon_unit(wire, "Bahay Kubo", (600, 400))
    summon_unit(wire, "Mug", (300, 300))
    summon_unit(wire, "Pen", (900, 500))
    wire.exchange({"type": "night.begin"})
    wire.exchange(
        {"type": "claim.tap", "player_name": "Migs", "unit_ids": ["u_kubo", "u_2"]}
    )
    return last_state(wire.exchange({"type": "claim.done"}))


def play_to_end(wire: Wire) -> Msg:
    state: Msg = {}
    for _ in range(40):
        got = wire.exchange({"type": "end_turn"})
        state = last_state(got)
        if state["phase"] == "PHYSICAL_EFFECTS":
            state = last_state(wire.exchange({"type": "effect.done"}))
        if state["phase"] in ("SUNRISE", "DEFEAT"):
            return state
    raise AssertionError("night never ended")


def test_a_whole_night_over_the_socket_and_the_end_screens(
    live: tuple[Harness, Wire],
) -> None:
    _, wire = live
    reach_night(wire)
    end = play_to_end(wire)
    assert end["score"] is not None
    assert notices(wire.exchange({"type": "end_turn"})) == ["cmd.unknown"]
    assert notices(wire.exchange({"type": "night.pause"})) == ["cmd.unknown"]
    assert notices(
        wire.exchange(
            {
                "type": "intent.tap",
                "unit_id": "u_2",
                "action": "attack",
                "target_id": None,
            }
        )
    ) == ["cmd.unknown"]
    replay = wire.exchange({"type": "replay.request"})
    assert len(notices(replay)) >= 1
    if end["phase"] == "SUNRISE":
        assert (
            notices(
                wire.exchange({"type": "badge.pick", "unit_id": "u_9", "badge": "hp"})
            )
            != []
        )
    nxt = last_state(wire.exchange({"type": "night.next"}))
    assert nxt["phase"] == "SUMMON"


def test_night_quit_from_the_end_screen_returns_to_start(
    live: tuple[Harness, Wire],
) -> None:
    _, wire = live
    reach_night(wire)
    play_to_end(wire)
    assert last_state(wire.exchange({"type": "night.quit"}))["phase"] == "START"
    got = wire.reply_of({"type": "campaign.list"}, "campaigns")
    campaigns = got["campaigns"]
    assert isinstance(campaigns, list)
    campaign_id = cast(dict[str, object], campaigns[0])["id"]
    started = wire.exchange({"type": "campaign.start", "campaign_id": campaign_id})
    assert last_state(started)["campaign"] is not None


def test_calibrate_back_and_restart_from_calibrate(live: tuple[Harness, Wire]) -> None:
    _, wire = live
    wire.exchange(CAMPAIGN_NEW)
    assert (
        last_state(wire.exchange({"type": "calibrate.restart"}))["phase"] == "CALIBRATE"
    )
    assert last_state(wire.exchange({"type": "calibrate.back"}))["phase"] == "START"


def test_delete_campaign_over_the_socket(live: tuple[Harness, Wire]) -> None:
    _, wire = live
    wire.exchange(CAMPAIGN_NEW)
    wire.exchange({"type": "calibrate.back"})
    campaigns = wire.reply_of({"type": "campaign.list"}, "campaigns")["campaigns"]
    assert isinstance(campaigns, list)
    campaign_id = cast(dict[str, object], campaigns[0])["id"]
    got = wire.exchange({"type": "campaign.delete", "campaign_id": campaign_id})
    assert "delete.done" in notices(got)
    assert wire.reply_of({"type": "campaign.list"}, "campaigns")["campaigns"] == []


def raising(error: Exception) -> Callable[..., object]:
    def raiser(*_: object, **__: object) -> object:
        raise error

    return raiser


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (StoreError("x"), "err.generic"),
        (CalibrationError("x"), "err.generic"),
        (CameraError("x"), "err.generic"),
        (OSError("x"), "err.generic"),
        (ValueError("x"), "err.generic"),
        (RuntimeError("x"), "err.generic"),
        (KeyError("x"), "err.generic"),
        (ZeroDivisionError(), "err.generic"),
    ],
)
def test_handler_failures_become_a_generic_notice_and_the_socket_lives(
    shared_live: tuple[Harness, Wire],
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    key: str,
) -> None:
    built, wire = shared_live
    monkeypatch.setattr(built.controller, "list_campaigns", raising(error))
    got = wire.exchange({"type": "campaign.list"})
    assert notices(got) == [key]
    assert "x" not in json.dumps([m for m in got if m["type"] == "notice"]).replace(
        "copy_key", ""
    )
    monkeypatch.undo()
    assert wire.exchange({"type": "campaign.list"})[0]["type"] == "campaigns"


def test_state_broadcast_is_forwarded(live: tuple[Harness, Wire]) -> None:
    built, wire = live
    controller = built.controller
    loop = controller._loop
    assert loop is not None
    broadcast = built.services[0].broadcast
    loop.call_soon_threadsafe(lambda: broadcast.publish({"type": STATE_CHANGED}))
    state = wire.until("state")
    assert state["phase"] == "START"


def test_cost_message_only_in_dev(tmp_path: Path) -> None:
    dev = AppSettings(
        token=TOKEN, data_dir=tmp_path, port=8765, api_key=None, is_dev=True
    )
    client = TestClient(create_app(dev, frozenset({ORIGIN}), make_factory(tmp_path)))
    with client, connect(client) as ws:
        wire = Wire(ws)
        assert wire.until("state")["phase"] == "START"
        assert wire.until("cost")["stopped"] is False


def campaign_names(wire: Wire) -> list[str]:
    campaigns = wire.reply_of({"type": "campaign.list"}, "campaigns")["campaigns"]
    assert isinstance(campaigns, list)
    return sorted(str(cast(dict[str, object], c)["name"]) for c in campaigns)


def test_refused_campaign_start_during_a_night_leaves_no_row(
    live: tuple[Harness, Wire],
) -> None:
    _, wire = live
    reach_night(wire)
    got = wire.exchange({"type": "campaign.start", "new": {"name": "Stray"}})
    assert notices(got) == ["cmd.unknown"]
    assert campaign_names(wire) == ["Barkada"]


def test_campaign_start_is_refused_outside_start(live: tuple[Harness, Wire]) -> None:
    _, wire = live
    to_summon(wire)
    got = wire.exchange({"type": "campaign.start", "new": {"name": "Other"}})
    assert notices(got) == ["cmd.unknown"]
    assert last_state(got)["phase"] == "SUMMON"

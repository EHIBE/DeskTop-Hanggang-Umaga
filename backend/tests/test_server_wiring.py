import asyncio
import io
import logging
import os
import sys
import threading
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar, cast

import pytest
from fastapi.testclient import TestClient

import server
from capture.camera import MicrophoneInfo
from capture.recorder import Recorder
from config import AppSettings
from game.night import GameController, GameError
from gm.glimmer import GLIMMER_URL_ENV
from gm.narrator import LineBank
from gm.schemas import ContentFilter
from meta_client import CostMeter, MetaClient, create_openai_client
from replay.render import ReelRequest
from server import (
    SUBPROTOCOL,
    Services,
    build_command_fallback,
    build_narration,
    build_pipeline_factory,
    build_recap_builder,
    build_recorder_factory,
    build_replay_runner,
    build_segmenter_factory,
    build_services,
    build_sprite_factory,
    build_voice_factory,
    create_app,
    create_app_from_env,
    exit_when_parent_closes_stdin,
    is_token_valid,
    recover_forever,
    token_from_subprotocols,
)
from tests.test_meta_client import MemoryLog
from tests.test_server import ORIGIN, TOKEN, connect, make_factory
from tests.test_server_messages import UUID_A, Harness, Wire, last_state, notices
from vision.sam import SamSegmenter, SamVideoTracker, TrackerOnlySegmenter
from vision.sprites import MuseImageGenerator, PlaceholderGenerator
from vision.summon import FallbackDetector, SparkDetector
from voice.grammar import GrammarContext
from voice.session import VoiceSession

CONTENT = ContentFilter.from_data_dir()
FAKE_KEY = "sk-not-a-real-key"


T = TypeVar("T")


def run(awaitable: Awaitable[T]) -> T:
    async def inner() -> T:
        return await awaitable

    return asyncio.run(inner())


def offline_meta() -> MetaClient:
    return MetaClient(None, CostMeter(MemoryLog()))


def live_meta() -> MetaClient:
    return MetaClient(create_openai_client(FAKE_KEY), CostMeter(MemoryLog()))


def settings_for(tmp_path: Path, api_key: str | None = None) -> AppSettings:
    return AppSettings(
        token=TOKEN, data_dir=tmp_path / "data", port=8765, api_key=api_key
    )


def test_is_token_valid_edge_cases() -> None:
    assert is_token_valid(TOKEN, TOKEN)
    assert not is_token_valid(TOKEN, None)
    assert not is_token_valid(TOKEN, "")
    assert not is_token_valid(TOKEN, TOKEN + "x")
    assert not is_token_valid(TOKEN, TOKEN[:-1])
    assert not is_token_valid(TOKEN, "é" * 64)
    assert not is_token_valid(TOKEN, "\u0000" * 64)
    assert is_token_valid("é" * 32, "é" * 32)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, None),
        ("", None),
        ("desktop", None),
        ("desktop,", ""),
        ("desktop, tok", "tok"),
        ("desktop,tok", "tok"),
        ("  desktop  ,  tok  ", "tok"),
        ("desktop, tok, extra", None),
        ("tok, desktop", None),
        ("Desktop, tok", None),
        (",tok", None),
        (",", None),
        ("desktop, desktop", "desktop"),
    ],
)
def test_token_from_subprotocols(header: str | None, expected: str | None) -> None:
    assert token_from_subprotocols(header) == expected


def test_build_services_offline_and_close(tmp_path: Path) -> None:
    services = build_services(settings_for(tmp_path))
    assert services.controller.snapshot().has_api_key is False
    assert services.meter is not None
    assert services.meter.is_stopped is False
    services.close()
    assert (tmp_path / "data").is_dir()


def test_build_services_with_a_key_enables_voice_and_the_meter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(GLIMMER_URL_ENV, raising=False)
    services = build_services(settings_for(tmp_path, FAKE_KEY))
    try:
        assert services.controller.snapshot().has_api_key is True
        assert services.controller._voice_factory is not None
        pipeline_factory = services.controller._pipeline_factory
        assert pipeline_factory is not None
        detector = pipeline_factory(False)._detector
        assert isinstance(detector, SparkDetector)
        detector._log_invalid("bad box")
    finally:
        services.close()


def test_selected_mic_follows_the_mic_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        server, "list_microphones", lambda: [MicrophoneInfo(2, "Desk Mic")]
    )
    opened: list[int | None] = []

    def fake_mic(index: int | None) -> object:
        opened.append(index)
        return object()

    monkeypatch.setattr(server, "SoundDeviceMicrophone", fake_mic)
    services = build_services(settings_for(tmp_path, FAKE_KEY))
    try:
        factory = services.controller._voice_factory
        assert factory is not None
        session = factory(("kubo",), print, print, lambda: None, print)
        assert isinstance(session, VoiceSession)
        make_mic = session._microphone_factory
        for value, expected in (
            ("default", None),
            ("3", 3),
            ("Desk Mic", 2),
            ("Missing Mic", None),
        ):
            services.controller.set_setting("mic_device", value)
            make_mic()
            assert opened[-1] == expected
    finally:
        services.close()


def test_pipeline_factory_picks_fallback_or_live() -> None:
    log: list[str] = []
    offline = build_pipeline_factory(offline_meta(), CONTENT, log.append)
    assert isinstance(offline(False)._detector, FallbackDetector)
    assert isinstance(offline(False)._segmenter, TrackerOnlySegmenter)
    live = build_pipeline_factory(live_meta(), CONTENT, log.append)
    assert isinstance(live(True)._detector, FallbackDetector)
    pipeline = live(False)
    assert isinstance(pipeline._detector, SparkDetector)
    assert isinstance(pipeline._segmenter, SamSegmenter)
    pipeline._detector._log_invalid("why")
    assert log == ["why"]


def test_segmenter_factory_picks_live_or_offline() -> None:
    assert isinstance(
        build_segmenter_factory(offline_meta())(False), TrackerOnlySegmenter
    )
    assert isinstance(build_segmenter_factory(live_meta())(True), SamSegmenter)


def test_sprite_factory_uses_the_placeholder_when_it_should(tmp_path: Path) -> None:
    from db.store import Store

    store = Store(tmp_path / "db.sqlite")
    try:
        assert isinstance(
            build_sprite_factory(store, offline_meta())(False)._generator,
            PlaceholderGenerator,
        )
        live = build_sprite_factory(store, live_meta())
        assert isinstance(live(True)._generator, PlaceholderGenerator)
        assert isinstance(live(False)._generator, MuseImageGenerator)
    finally:
        store.close()


def test_narration_and_recap_builders_follow_the_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(GLIMMER_URL_ENV, raising=False)
    bank = LineBank()
    log: list[str] = []
    assert (
        build_narration(offline_meta(), CONTENT, log.append, bank)._live_factory is None
    )
    assert (
        build_narration(live_meta(), CONTENT, log.append, bank)._live_factory
        is not None
    )
    assert build_recap_builder(offline_meta(), CONTENT, log.append, bank)._spark is None
    assert (
        build_recap_builder(live_meta(), CONTENT, log.append, bank)._spark is not None
    )


def test_command_fallback_is_silent_without_units_or_in_demo_safe() -> None:
    fallback = build_command_fallback(live_meta())
    empty = GrammarContext(units=(), enemies=())
    assert run(fallback("atake", empty, False)) is None
    assert run(fallback("atake", empty, True)) is None


def test_voice_factory_needs_a_key() -> None:
    meter = CostMeter(MemoryLog())
    assert build_voice_factory(None, meter, lambda: None) is None
    factory = build_voice_factory(FAKE_KEY, meter, lambda: 1)
    assert factory is not None
    assert isinstance(factory(("a",), print, print, lambda: None, print), VoiceSession)


def test_recorder_factory_builds_a_recorder(tmp_path: Path) -> None:
    factory = build_recorder_factory(None)
    recorder = factory(tmp_path / "rec.mp4", 640, 480, tmp_path)
    assert isinstance(recorder, Recorder)


def reel_request(tmp_path: Path) -> ReelRequest:
    return ReelRequest(
        sidecar=tmp_path / "x.json",
        rows=(),
        sprites={},
        out_path=tmp_path / "out.mp4",
        work_dir=tmp_path,
        root=tmp_path,
        ffmpeg=None,
        title_tl="a",
        title_en="b",
        night_number=1,
    )


def test_replay_runner_uses_the_live_client_only_when_paid_and_credentialed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[object, object]] = []

    reel: Any = object()

    async def fake_make_reel(request: object, client: object, tracker: object) -> Any:
        calls.append((client, tracker))
        return reel

    monkeypatch.setattr(server, "make_reel", fake_make_reel)
    request = reel_request(tmp_path)
    live = live_meta()
    assert run(build_replay_runner(live)(request, True)) is reel
    assert run(build_replay_runner(live)(request, False)) is reel
    assert run(build_replay_runner(offline_meta())(request, True)) is reel
    assert calls[0][0] is live and calls[0][1] is SamVideoTracker
    assert calls[1] == (None, None)
    assert calls[2] == (None, None)


class FakeController:
    def __init__(self, claim: Exception | None, recover: Exception | None) -> None:
        self.claim = claim
        self.recover = recover
        self.claim_calls = 0
        self.recover_calls = 0

    def enforce_claim_timeout(self) -> bool:
        self.claim_calls += 1
        if self.claim is not None:
            raise self.claim
        return False

    def enforce_effects(self) -> None:
        return None

    def enforce_confirm_timeout(self) -> None:
        return None

    async def recover_lost_objects(self) -> None:
        self.recover_calls += 1
        if self.recover is not None:
            raise self.recover


async def run_recovery(fake: FakeController, rounds: int) -> None:
    task = asyncio.create_task(recover_forever(cast(GameController, fake)))
    for _ in range(400):
        if fake.recover_calls >= rounds and fake.claim_calls >= rounds:
            break
        await asyncio.sleep(0.005)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.parametrize(
    ("claim", "recover", "logged"),
    [
        (None, None, ""),
        (GameError("cmd.unknown"), GameError("cmd.unknown"), "recovery skipped"),
        (GameError("cmd.unknown"), None, "timed night step skipped"),
        (RuntimeError("boom"), RuntimeError("boom"), "will retry"),
        (ValueError("x"), OSError("y"), "between-turn recovery failed"),
    ],
)
def test_recovery_loop_survives_every_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    claim: Exception | None,
    recover: Exception | None,
    logged: str,
) -> None:
    monkeypatch.setattr(server, "RECOVERY_INTERVAL_S", 0.0)
    caplog.set_level(logging.WARNING, logger="desktop.server")
    fake = FakeController(claim, recover)
    asyncio.run(run_recovery(fake, 3))
    assert fake.claim_calls >= 3 and fake.recover_calls >= 3
    assert logged in caplog.text


def test_lifespan_closes_services_once_on_shutdown(tmp_path: Path) -> None:
    closed: list[int] = []
    inner = make_factory(tmp_path)

    def factory(settings: AppSettings) -> Services:
        services = inner(settings)
        original = services.close

        def close() -> None:
            closed.append(1)
            original()

        return Services(
            settings=services.settings,
            controller=services.controller,
            pump=services.pump,
            live=services.live,
            content=services.content,
            meter=services.meter,
            broadcast=services.broadcast,
            close=close,
        )

    app = create_app(settings_for(tmp_path), frozenset({ORIGIN}), factory)
    with TestClient(app) as client, connect(client) as ws:
        assert Wire(ws).until("state")["phase"] == "START"
        assert closed == []
    assert closed == [1]


def test_every_socket_is_closed_cleanly_when_the_client_leaves(
    tmp_path: Path,
) -> None:
    app = create_app(
        settings_for(tmp_path), frozenset({ORIGIN}), make_factory(tmp_path)
    )
    with TestClient(app) as client:
        with connect(client) as ws:
            assert ws.accepted_subprotocol == SUBPROTOCOL
            ws.close(code=1001)
        with connect(client) as ws:
            assert Wire(ws).until("state")["phase"] == "START"


def base_env(tmp_path: Path) -> dict[str, str]:
    return {
        "DESKTOP_TOKEN": TOKEN,
        "DESKTOP_DATA_DIR": str(tmp_path / "data"),
        "DESKTOP_PORT": "8765",
        "DESKTOP_ALLOWED_ORIGINS": "file://",
    }


def apply_env(
    monkeypatch: pytest.MonkeyPatch, values: dict[str, str], clear: tuple[str, ...]
) -> None:
    for key in (
        "DESKTOP_TOKEN",
        "DESKTOP_DATA_DIR",
        "DESKTOP_PORT",
        "DESKTOP_ALLOWED_ORIGINS",
        "MODEL_API_KEY",
        "DESKTOP_DEV",
        "DESKTOP_PARENT_WATCH",
        "DESKTOP_PACKAGED",
        *clear,
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_create_app_from_env_builds_an_app_with_origin_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apply_env(monkeypatch, base_env(tmp_path), ())
    started: list[object] = []
    monkeypatch.setattr(threading, "Thread", lambda **kw: started.append(kw))
    loaded: list[object] = []
    monkeypatch.setattr(server, "load_dotenv", lambda *a, **k: loaded.append(a))
    app = create_app_from_env()
    assert app.openapi_url is None and app.docs_url is None
    assert started == [] and loaded == []
    client = TestClient(app)
    assert client.get("/health").status_code == 401
    assert client.get("/health", headers={"x-desktop-token": TOKEN}).status_code == 200


def test_create_app_from_env_packaged_allows_null_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apply_env(monkeypatch, {**base_env(tmp_path), "DESKTOP_PACKAGED": "1"}, ())
    with (
        TestClient(create_app_from_env()) as client,
        connect(client, TOKEN, "null") as ws,
    ):
        assert Wire(ws).until("state")["phase"] == "START"


def test_create_app_from_env_unpackaged_refuses_null_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from starlette.websockets import WebSocketDisconnect

    apply_env(monkeypatch, base_env(tmp_path), ())
    with TestClient(create_app_from_env()) as client:
        with (
            pytest.raises(WebSocketDisconnect) as info,
            connect(client, TOKEN, "null") as ws,
        ):
            ws.receive_text()
        assert info.value.code == 1008


def test_create_app_from_env_dev_loads_dotenv_and_parent_watch_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apply_env(
        monkeypatch,
        {**base_env(tmp_path), "DESKTOP_DEV": "1", "DESKTOP_PARENT_WATCH": "1"},
        (),
    )
    loaded: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        server, "load_dotenv", lambda *a, **k: loaded.append((a, tuple(k.items())))
    )
    started: list[dict[str, object]] = []

    class FakeThread:
        def __init__(self, **kwargs: object) -> None:
            started.append(kwargs)

        def start(self) -> None:
            started.append({"started": True})

    monkeypatch.setattr(threading, "Thread", FakeThread)
    create_app_from_env()
    assert len(loaded) == 1
    assert loaded[0][1] == (("override", False),)
    assert started[0]["name"] == "parent-watch"
    assert started[0]["daemon"] is True
    assert started[1] == {"started": True}


@pytest.mark.parametrize(
    "bad",
    [
        {"DESKTOP_TOKEN": ""},
        {"DESKTOP_TOKEN": "short"},
        {"DESKTOP_PORT": "99999"},
        {"DESKTOP_PORT": "abc"},
    ],
)
def test_create_app_from_env_refuses_a_bad_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: dict[str, str]
) -> None:
    from config import ConfigError

    apply_env(monkeypatch, {**base_env(tmp_path), **bad}, ())
    with pytest.raises(ConfigError):
        create_app_from_env()


def test_parent_watch_exits_when_stdin_closes(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class FakeStdin:
        buffer = io.BytesIO(b"")

    exits: list[int] = []
    monkeypatch.setattr(sys, "stdin", FakeStdin())
    monkeypatch.setattr(os, "_exit", exits.append)
    caplog.set_level(logging.WARNING, logger="desktop.server")
    exit_when_parent_closes_stdin()
    assert exits == [0]
    assert "parent process closed stdin" in caplog.text


def test_dispatch_passes_arguments_to_the_controller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built = Harness(tmp_path)
    calls: list[tuple[str, tuple[object, ...]]] = []

    def recorder(name: str) -> Callable[..., None]:
        def record(*args: object) -> None:
            calls.append((name, args))

        return record

    with built.client, connect(built.client) as ws:
        wire = Wire(ws)
        wire.until("state")
        controller = built.controller
        for name in (
            "pick_badge",
            "confirm_order",
            "cancel_chip",
            "retry_voice",
            "quit_paused",
            "back_to_start",
            "finish_effects_now",
            "set_ptt",
            "set_voice_mode",
            "give_consent",
            "add_intent",
        ):
            monkeypatch.setattr(controller, name, recorder(name))
        monkeypatch.setattr(
            controller,
            "request_replay",
            lambda *args: calls.append(("request_replay", args)),
        )
        monkeypatch.setattr(controller, "map_png", lambda: "QUJD")
        sent: list[dict[str, object]] = [
            {"type": "badge.pick", "unit_id": "u_2", "badge": "cooldown"},
            {"type": "confirm.accept", "confirm_id": UUID_A},
            {"type": "confirm.cancel", "confirm_id": UUID_A},
            {"type": "chip.cancel", "chip_id": UUID_A},
            {"type": "voice.retry"},
            {"type": "pause.quit"},
            {"type": "calibrate.back"},
            {"type": "effect.done"},
            {"type": "ptt", "down": True},
            {"type": "voice.mode", "mode": "ptt"},
            {"type": "consent", "player_name": "Migs", "agree": True},
            {"type": "replay.request"},
            {
                "type": "intent.tap",
                "unit_id": "u_2",
                "action": "attack",
                "target_id": None,
            },
        ]
        for payload in sent:
            got = wire.exchange(payload)
            assert notices(got) == []
            assert last_state(got)["phase"] == "START"
        reply = wire.reply_of({"type": "map.get"}, "map")
        assert reply["png"] == "QUJD"
    names = [name for name, _ in calls]
    assert names == [
        "pick_badge",
        "confirm_order",
        "confirm_order",
        "cancel_chip",
        "retry_voice",
        "quit_paused",
        "back_to_start",
        "finish_effects_now",
        "set_ptt",
        "set_voice_mode",
        "give_consent",
        "request_replay",
        "add_intent",
    ]
    assert calls[0][1][0] == "u_2"
    assert calls[1][1] == (UUID_A, True)
    assert calls[2][1] == (UUID_A, False)
    assert calls[8][1] == (True,)
    assert calls[10][1] == ("Migs", True)
    assert calls[11][1] == ("SUMIKAT NA", "SUNRISE")

import asyncio
import json
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config import AppSettings
from db.store import Store, UnitProgress
from game.night import AppPhase, GameController, GameError
from game.state_machine import TurnState
from gm.narrator import LineBank
from gm.recap import Recap, RecapBuilder, RecapOutcome, RecapSource
from rules.progression import Badge
from rules.resolve import TURNS_PER_NIGHT, Event, EventType, Smoke
from rules.units import Difficulty
from server import state_json
from state import Broadcast
from tests.test_barrio_map import ScriptedService, generated
from tests.test_night import CONTENT
from tests.test_night_flow import play_turns, start_night
from tests.test_server import (
    ORIGIN,
    TOKEN,
    connect,
    make_factory,
    receive_type,
)
from tests.test_tracking_flow import (
    ConfidentSegmenter,
    SequenceDetector,
    controller_for,
    summon_three,
)
from tests.test_voice_flow import Voices
from vision.sam import Anchor, AnchorStatus, PixelBox, TrackerOnlySegmenter
from vision.summon import SummonPipeline
from voice.grammar import Command, CommandKind
from voice.session import Caption

BANK = LineBank()


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    from server import create_app

    settings = AppSettings(token=TOKEN, data_dir=tmp_path, port=8765, api_key=None)
    app = create_app(settings, frozenset({ORIGIN}), make_factory(tmp_path))
    with TestClient(app) as test_client:
        yield test_client


def send(ws: object, payload: dict[str, object]) -> None:
    ws.send_text(json.dumps(payload))  # type: ignore[attr-defined]


def drain(queue: asyncio.Queue[dict[str, object]]) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return messages


def fresh_detector(controller: GameController) -> None:
    detector = SequenceDetector()
    controller._pipeline_factory = lambda _: SummonPipeline(
        detector, TrackerOnlySegmenter(), CONTENT
    )


def finish_night(controller: GameController, downed: tuple[str, ...] = ()) -> None:
    session = controller._session
    assert session is not None and session.board is not None
    board = session.board
    units = tuple(replace(u, hp=0) if u.id in downed else u for u in board.units)
    session._board = replace(board, turn=TURNS_PER_NIGHT, units=units)

    async def run() -> None:
        await controller.end_turn()
        if controller.snapshot().phase is AppPhase.PHYSICAL_EFFECTS:
            controller.finish_effects_now()
        await controller.wait_for_background()

    asyncio.run(run())


def test_settings_defaults_get_and_set_over_the_socket(client: TestClient) -> None:
    with connect(client) as ws:
        state = receive_type(ws, "state")
        assert state["tts_available"] is False
        assert state["settings"] == {
            "camera_device": 0,
            "mic_device": "default",
            "caption_language": "tl",
            "difficulty": "normal",
            "replay_enabled": True,
            "tts_enabled": False,
            "show_real_objects": True,
            "strict_ownership": False,
            "generated_map": False,
        }
        send(ws, {"type": "settings.get"})
        message = receive_type(ws, "settings")
        assert message["values"] == state["settings"]
        assert message["tts_available"] is False
        send(ws, {"type": "settings.set", "key": "strict_ownership", "value": True})
        updated = receive_type(ws, "settings")
        assert updated["values"]["strict_ownership"] is True  # type: ignore[index]
        assert receive_type(ws, "state")["settings"]["strict_ownership"] is True  # type: ignore[index]
        send(ws, {"type": "settings.set", "key": "caption_language", "value": "en"})
        assert receive_type(ws, "settings")["values"]["caption_language"] == "en"  # type: ignore[index]


def test_invalid_settings_are_refused(client: TestClient) -> None:
    with connect(client) as ws:
        receive_type(ws, "state")
        bad: tuple[dict[str, object], ...] = (
            {"type": "settings.set", "key": "difficulty", "value": "mahirap"},
            {"type": "settings.set", "key": "replay_enabled", "value": "yes"},
            {"type": "settings.set", "key": "camera_device", "value": 99},
            {"type": "settings.set", "key": "camera_device", "value": True},
        )
        for payload in bad:
            send(ws, payload)
            assert receive_type(ws, "notice")["copy_key"] == "settings.invalid"
            receive_type(ws, "state")
        send(ws, {"type": "settings.set", "key": "nope", "value": 1})
        assert receive_type(ws, "notice")["copy_key"] == "cmd.unknown"


def test_tts_is_stored_but_never_effective(client: TestClient) -> None:
    with connect(client) as ws:
        receive_type(ws, "state")
        send(ws, {"type": "settings.set", "key": "tts_enabled", "value": True})
        message = receive_type(ws, "settings")
        assert message["values"]["tts_enabled"] is False  # type: ignore[index]
        assert message["tts_available"] is False


def test_settings_persist_after_restart(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    controller.set_setting("strict_ownership", True)
    controller.set_setting("difficulty", "hard")
    controller.set_setting("mic_device", "3")
    controller.set_setting("replay_enabled", False)
    controller.set_setting("caption_language", "en")
    controller.close()
    store.close()
    again_store = Store(tmp_path / "db.sqlite")
    again = controller_for(again_store, ConfidentSegmenter())
    values = again.settings()
    assert values["strict_ownership"] is True
    assert values["difficulty"] == "hard"
    assert values["mic_device"] == "3"
    assert values["replay_enabled"] is False
    assert values["caption_language"] == "en"
    again.start_new_campaign("Barkada")
    campaign = again.snapshot().campaign
    assert campaign is not None
    assert campaign.difficulty is Difficulty.MAHIRAP
    again.close()
    again_store.close()


def test_camera_setting_selects_the_camera_and_uses_one_key(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    controller.start_new_campaign("B", Difficulty.NORMAL)
    controller.set_setting("camera_device", 0)
    camera = controller.snapshot().camera
    assert camera is not None and camera.index == 0
    assert store.get_preference("camera_device") == 0
    assert store.get_setting("camera_index") is None
    with pytest.raises(GameError) as info:
        controller.set_setting("camera_device", 9)
    assert info.value.copy_key == "settings.invalid"
    controller.close()
    store.close()


def test_replay_disabled_blocks_recording_and_the_reel(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    controller.set_setting("replay_enabled", False)
    summon_three(controller)
    controller.begin_night()
    controller.claim("Migs", ["u_kubo", "u_2", "u_3"], CONTENT.clean_player_name)
    controller.give_consent("Migs", True)
    controller.finish_claims()
    night = controller._night
    assert night is not None
    assert store.recording_consent(night.id) is False
    assert controller.snapshot().can_replay is False
    session = controller._session
    assert session is not None
    session._machine.force(TurnState.SUNRISE)
    with pytest.raises(GameError) as info:
        controller.request_replay("T", "T")
    assert info.value.copy_key == "replay.off"
    controller.close()
    store.close()


def test_mic_change_restarts_the_voice_session(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    voices = Voices()
    controller = controller_for(store, ConfidentSegmenter())
    controller._voice_factory = voices  # type: ignore[assignment]
    summon_three(controller)

    async def play() -> None:
        controller.begin_night()
        await asyncio.sleep(0)
        assert len(voices.made) == 1
        controller.set_setting("mic_device", "2")
        await asyncio.sleep(0)
        assert voices.made[0].is_stopped
        assert len(voices.made) == 2
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_calibration_back_returns_to_start_over_the_socket(client: TestClient) -> None:
    with connect(client) as ws:
        receive_type(ws, "state")
        send(ws, {"type": "calibrate.back"})
        assert receive_type(ws, "notice")["copy_key"] == "cmd.unknown"
        receive_type(ws, "state")
        send(ws, {"type": "campaign.start", "new": {"name": "B"}})
        state = receive_type(ws, "state")
        assert state["phase"] == "CALIBRATE"
        assert state["campaign"]["difficulty"] == "normal"  # type: ignore[index]
        send(ws, {"type": "calibrate.back"})
        state = receive_type(ws, "state")
        assert state["phase"] == "START"
        assert state["campaign"] is None


def test_back_is_refused_after_calibration(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    summon_three(controller)
    with pytest.raises(GameError):
        controller.back_to_start()
    controller.close()
    store.close()


def test_quit_from_pause_keeps_the_autosave_for_continue(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    with pytest.raises(GameError):
        controller.quit_paused()
    play_turns(controller, 2)
    campaign = controller.snapshot().campaign
    assert campaign is not None
    controller.pause_night()
    controller.quit_paused()
    snapshot = controller.snapshot()
    assert snapshot.phase is AppPhase.START
    assert snapshot.campaign is None
    assert snapshot.night is None
    controller.continue_campaign(campaign.id)
    resumed = controller.snapshot()
    assert resumed.phase is AppPhase.SUMMON
    assert resumed.resume_turn == 3
    controller.begin_night()
    assert controller.snapshot().night.turn == 3  # type: ignore[union-attr]
    controller.close()
    store.close()


def test_pause_quit_over_the_socket_needs_a_pause(client: TestClient) -> None:
    with connect(client) as ws:
        receive_type(ws, "state")
        send(ws, {"type": "pause.quit"})
        assert receive_type(ws, "notice")["copy_key"] == "cmd.unknown"


def test_off_desk_unit_is_lost_then_found(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    broadcast = Broadcast()
    queue = broadcast.subscribe()
    controller = controller_for(store, ConfidentSegmenter(), broadcast=broadcast)
    controller._line_bank = BANK
    start_night(controller)
    box = PixelBox(10, 10, 50, 50)
    outside = {2: Anchor(2, box, -8.0, 10.0, AnchorStatus.ACCEPTED)}
    inside = {2: Anchor(2, box, 20.0, 20.0, AnchorStatus.ACCEPTED)}
    anchors = outside

    async def reanchor(_: object = None) -> dict[int, Anchor]:
        return anchors

    controller.reanchor_all = reanchor  # type: ignore[method-assign,assignment]
    drain(queue)
    asyncio.run(controller.end_turn())
    lost = [m for m in drain(queue) if m["type"] in ("events", "moment")]
    kinds = [e["type"] for m in lost if m["type"] == "events" for e in m["events"]]  # type: ignore[attr-defined]
    assert "lost" in kinds
    moments = [m for m in lost if m["type"] == "moment"]
    assert moments[0]["moment"] == "unit_lost"
    assert moments[0]["unit_id"] == "u_2"
    night = controller.snapshot().night
    assert night is not None
    status = {u.game_id: u.status for u in night.units}
    assert "off_desk" in status["u_2"]
    assert ("unit.lost", {"unit": "Stapler"}) in controller.drain_notices()
    anchors = inside
    asyncio.run(controller.end_turn())
    found = drain(queue)
    kinds = [e["type"] for m in found if m["type"] == "events" for e in m["events"]]  # type: ignore[attr-defined]
    assert "found" in kinds
    assert any(m["type"] == "moment" and m["moment"] == "unit_returned" for m in found)
    night = controller.snapshot().night
    assert night is not None
    assert "off_desk" not in {u.game_id: u.status for u in night.units}["u_2"]
    controller.close()
    store.close()


def test_smoke_is_in_state_and_narrated(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    broadcast = Broadcast()
    queue = broadcast.subscribe()
    controller = controller_for(store, ConfidentSegmenter(), broadcast=broadcast)
    controller._line_bank = BANK
    start_night(controller)
    session = controller._session
    assert session is not None and session.board is not None
    board = session.board
    target = next(u for u in board.units if u.id == "u_2")
    cloud = Smoke("e_kapre_1", target.position)
    session._board = replace(board, smoke=(cloud,))
    snapshot = controller.snapshot()
    assert snapshot.night is not None
    assert [(c.source_id, c.radius_cm) for c in snapshot.night.smoke] == [
        ("e_kapre_1", cloud.radius_cm)
    ]
    assert {u.game_id: u.is_smoked for u in snapshot.night.units}["u_2"] is True
    payload = state_json(snapshot)["night"]
    assert payload["smoke"] == [  # type: ignore[index]
        {
            "source_id": "e_kapre_1",
            "x_cm": target.position[0],
            "y_cm": target.position[1],
            "radius_cm": cloud.radius_cm,
        }
    ]
    assert {u["id"]: u["smoked"] for u in payload["units"]}["u_2"] is True  # type: ignore[index]
    drain(queue)
    controller._emit_event_moments(
        1, (Event(EventType.SMOKE, "e_kapre_1", pos=target.position),)
    )
    moments = [m["moment"] for m in drain(queue) if m["type"] == "moment"]
    assert moments == ["kapre_smoke_telegraph", "kapre_smoke_hit"]
    controller.close()
    store.close()


def test_smoke_is_rebuilt_when_a_night_is_restored(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    play_turns(controller, 1)
    campaign = controller.snapshot().campaign
    assert campaign is not None
    controller.close()
    again = controller_for(store, ConfidentSegmenter())
    again.continue_campaign(campaign.id)
    again.select_camera(0)
    again.begin_night()
    session = again._session
    assert session is not None and session.board is not None
    assert session.board.smoke == ()
    again.close()
    store.close()


def make_strict(
    tmp_path: Path,
) -> tuple[Store, GameController, Voices, Broadcast]:
    store = Store(tmp_path / "db.sqlite")
    broadcast = Broadcast()
    voices = Voices()
    controller = controller_for(store, ConfidentSegmenter(), broadcast=broadcast)
    controller._voice_factory = voices  # type: ignore[assignment]
    summon_three(controller)
    return store, controller, voices, broadcast


def begin_two_players(controller: GameController) -> None:
    controller.begin_night()
    controller.claim("Migs", ["u_kubo", "u_2"], CONTENT.clean_player_name)
    controller.claim("Bea", ["u_3"], CONTENT.clean_player_name)
    controller.finish_claims()


def test_strict_ownership_holds_the_order_until_confirmed(tmp_path: Path) -> None:
    store, controller, voices, _ = make_strict(tmp_path)
    controller.set_setting("strict_ownership", True)

    async def play() -> None:
        begin_two_players(controller)
        await asyncio.sleep(0)
        controller._voice_players = {"spk_0": "Bea", "spk_1": "Migs"}
        voices.made[0].say("Stapler, atake ang aswang!", "spk_0")
        snapshot = controller.snapshot()
        assert snapshot.night is not None
        assert snapshot.night.chips == ()
        pending = snapshot.pending_confirm
        assert pending is not None
        assert (pending.owner, pending.unit_id, pending.action) == (
            "Migs",
            "u_2",
            "attack",
        )
        assert pending.text_tl == "Kay Migs ang Stapler. Ituloy?"
        assert pending.speaker == "Bea"
        payload = state_json(snapshot)["pending_confirm"]
        assert payload["confirm_id"] == pending.confirm_id  # type: ignore[index]
        with pytest.raises(GameError):
            controller.confirm_order("0" * 36, True)
        controller.confirm_order(pending.confirm_id, True)
        after = controller.snapshot()
        assert after.pending_confirm is None
        assert after.night is not None
        assert [(c.unit_id, c.source, c.speaker) for c in after.night.chips] == [
            ("u_2", "voice", "Bea")
        ]
        voices.made[0].say("Stapler, atake ang aswang!", "spk_0")
        again = controller.snapshot().pending_confirm
        assert again is not None
        controller.confirm_order(again.confirm_id, False)
        assert controller.snapshot().pending_confirm is None
        voices.made[0].say("Stapler, atake ang aswang!", "spk_1")
        assert controller.snapshot().pending_confirm is None
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_relaxed_ownership_and_unknown_speakers_need_no_confirmation(
    tmp_path: Path,
) -> None:
    store, controller, voices, _ = make_strict(tmp_path)

    async def play() -> None:
        begin_two_players(controller)
        await asyncio.sleep(0)
        controller._voice_players = {"spk_0": "Bea"}
        voices.made[0].say("Stapler, atake ang aswang!", "spk_0")
        assert controller.snapshot().pending_confirm is None
        assert len(controller.snapshot().night.chips) == 1  # type: ignore[union-attr]
        controller.set_setting("strict_ownership", True)
        voices.made[0].say("Phone, atake ang aswang!", "spk_9")
        assert controller.snapshot().pending_confirm is None
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_pending_confirm_expires(tmp_path: Path) -> None:
    store, controller, voices, _ = make_strict(tmp_path)
    controller.set_setting("strict_ownership", True)
    clock = {"now": 0.0}
    controller._clock = lambda: clock["now"]

    async def play() -> None:
        begin_two_players(controller)
        await asyncio.sleep(0)
        controller._voice_players = {"spk_0": "Bea"}
        voices.made[0].say("Stapler, atake ang aswang!", "spk_0")
        assert controller.snapshot().pending_confirm is not None
        assert controller.enforce_confirm_timeout() is False
        clock["now"] = 60.0
        assert controller.enforce_confirm_timeout() is True
        assert controller.snapshot().pending_confirm is None
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_confirm_messages_need_a_pending_order(client: TestClient) -> None:
    with connect(client) as ws:
        receive_type(ws, "state")
        for kind in ("confirm.accept", "confirm.cancel"):
            send(ws, {"type": kind, "confirm_id": "0" * 36})
            assert receive_type(ws, "notice")["copy_key"] == "cmd.unknown"
            receive_type(ws, "state")
        send(ws, {"type": "confirm.accept", "confirm_id": "short"})
        assert receive_type(ws, "notice")["copy_key"] == "cmd.unknown"


def spark_setup(
    tmp_path: Path,
    command: Callable[[GameController], Command | None],
    delay: float = 0.0,
) -> tuple[Store, GameController, Voices, list[str]]:
    store, controller, voices, _ = make_strict(tmp_path)
    calls: list[str] = []

    async def fallback(
        text: str, context: object, is_demo_safe: bool
    ) -> Command | None:
        calls.append(text)
        if delay:
            await asyncio.sleep(delay)
        return command(controller)

    controller._command_fallback = fallback
    return store, controller, voices, calls


def test_spark_fallback_turns_odd_speech_into_a_chip(tmp_path: Path) -> None:
    def attack(controller: GameController) -> Command:
        night = controller.snapshot().night
        assert night is not None
        return Command(CommandKind.ATTACK, "u_2", night.enemies[0].id)

    store, controller, voices, calls = spark_setup(tmp_path, attack)

    async def play() -> None:
        begin_two_players(controller)
        await asyncio.sleep(0)
        voices.made[0].say("Stapler plugh", "spk_0")
        await controller.wait_for_voice_end_turns()
        night = controller.snapshot().night
        assert night is not None
        assert [(c.unit_id, c.action, c.source) for c in night.chips] == [
            ("u_2", "attack", "voice")
        ]
        assert calls == ["Stapler plugh"]
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_spark_fallback_none_gives_the_unknown_notice(tmp_path: Path) -> None:
    store, controller, voices, calls = spark_setup(tmp_path, lambda _: None)

    async def play() -> None:
        begin_two_players(controller)
        await asyncio.sleep(0)
        controller.drain_notices()
        voices.made[0].say("Stapler plugh", "spk_0")
        await controller.wait_for_voice_end_turns()
        assert ("cmd.unknown", {}) in controller.drain_notices()
        assert calls == ["Stapler plugh"]
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_spark_fallback_never_ends_the_turn(tmp_path: Path) -> None:
    store, controller, voices, _ = spark_setup(
        tmp_path, lambda _: Command(CommandKind.END_TURN, None, None)
    )

    async def play() -> None:
        begin_two_players(controller)
        await asyncio.sleep(0)
        voices.made[0].say("Stapler plugh", "spk_0")
        await controller.wait_for_voice_end_turns()
        assert controller.snapshot().night.turn == 1  # type: ignore[union-attr]
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_spark_fallback_times_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("game.night.COMMAND_FALLBACK_TIMEOUT_S", 0.01)
    store, controller, voices, _ = spark_setup(
        tmp_path, lambda _: Command(CommandKind.ATTACK, "u_2", None), delay=1.0
    )

    async def play() -> None:
        begin_two_players(controller)
        await asyncio.sleep(0)
        controller.drain_notices()
        voices.made[0].say("Stapler plugh", "spk_0")
        await controller.wait_for_voice_end_turns()
        assert ("cmd.unknown", {}) in controller.drain_notices()
        assert controller.snapshot().night.chips == ()  # type: ignore[union-attr]
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_demo_safe_and_known_orders_skip_the_spark_fallback(tmp_path: Path) -> None:
    store, controller, voices, calls = spark_setup(tmp_path, lambda _: None)

    async def play() -> None:
        begin_two_players(controller)
        await asyncio.sleep(0)
        voices.made[0].say("Stapler, atake ang aswang!", "spk_0")
        await controller.wait_for_voice_end_turns()
        assert calls == []
        controller.set_demo_safe(True)
        controller.drain_notices()
        controller._start_voice()
        controller._on_voice_final(Caption("t2", "Stapler plugh", True, "spk_0"))
        await controller.wait_for_voice_end_turns()
        assert calls == []
        assert ("cmd.unknown", {}) in controller.drain_notices()
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_sunrise_awards_progression_scars_and_offers(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    broadcast = Broadcast()
    queue = broadcast.subscribe()
    controller = controller_for(store, ConfidentSegmenter(), broadcast=broadcast)
    controller._line_bank = BANK
    controller._recap_builder = RecapBuilder(BANK, CONTENT)
    start_night(controller)
    finish_night(controller, downed=("u_3",))
    snapshot = controller.snapshot()
    assert snapshot.phase is AppPhase.SUNRISE
    progression = snapshot.progression
    assert progression is not None
    assert (progression.barrio_level, progression.nights_survived) == (1, 1)
    offers = {o.unit_id: o.choices for o in progression.badge_offers}
    assert offers["u_kubo"] == ("hp",)
    assert offers["u_2"] == ("hp", "cooldown")
    assert "u_3" not in offers
    campaign = snapshot.campaign
    assert campaign is not None
    assert (campaign.barrio_level, campaign.nights_survived) == (1, 1)
    assert store.get_progression(campaign.id).nights_survived == 1
    downed = next(u for u in controller._units if u.sam_object_id == 3)
    assert store.get_unit_progress(downed.unit_id).scars == ("s1",)
    payload = state_json(snapshot)
    assert payload["progression"]["badge_offers"][0]["unit_id"] == "u_kubo"  # type: ignore[index]
    assert {u["id"]: u["scars"] for u in payload["night"]["units"]}["u_3"] == 1  # type: ignore[index]
    moments = [m["moment"] for m in drain(queue) if m["type"] == "moment"]
    assert "scar_gained" in moments
    controller.close()
    store.close()


def test_badge_pick_is_validated_applied_and_persisted(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    broadcast = Broadcast()
    queue = broadcast.subscribe()
    controller = controller_for(store, ConfidentSegmenter(), broadcast=broadcast)
    controller._line_bank = BANK
    start_night(controller)
    with pytest.raises(GameError):
        controller.pick_badge("u_2", Badge.HP)
    finish_night(controller)
    with pytest.raises(GameError):
        controller.pick_badge("u_kubo", Badge.COOLDOWN)
    with pytest.raises(GameError):
        controller.pick_badge("u_9", Badge.HP)
    drain(queue)
    controller.pick_badge("u_2", Badge.COOLDOWN)
    record = next(u for u in controller._units if u.sam_object_id == 2)
    assert store.get_unit_progress(record.unit_id) == UnitProgress(("cooldown",), ())
    offers = controller.snapshot().progression.badge_offers  # type: ignore[union-attr]
    assert "u_2" not in {o.unit_id for o in offers}
    with pytest.raises(GameError):
        controller.pick_badge("u_2", Badge.HP)
    moments = [m for m in drain(queue) if m["type"] == "moment"]
    assert moments[0]["moment"] == "badge_earned"
    assert "Cooldown-1" in str(moments[0]["text_tl"])
    controller.close()
    store.close()


def test_badge_pick_over_the_socket_needs_a_sunrise(client: TestClient) -> None:
    with connect(client) as ws:
        receive_type(ws, "state")
        send(ws, {"type": "badge.pick", "unit_id": "u_2", "badge": "hp"})
        assert receive_type(ws, "notice")["copy_key"] == "cmd.unknown"
        receive_type(ws, "state")
        send(ws, {"type": "badge.pick", "unit_id": "u_2", "badge": "mana"})
        assert receive_type(ws, "notice")["copy_key"] == "cmd.unknown"


def test_returning_object_keeps_badges_and_boosts_next_night(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    broadcast = Broadcast()
    queue = broadcast.subscribe()
    controller = controller_for(store, ConfidentSegmenter(), broadcast=broadcast)
    controller._line_bank = BANK
    start_night(controller)
    first = controller.snapshot()
    assert first.night is not None
    kubo_before = next(u for u in first.night.units if u.game_id == "u_kubo")
    finish_night(controller)
    controller.pick_badge("u_kubo", Badge.HP)
    kubo_record = next(u for u in controller._units if u.sam_object_id == 1)
    controller.next_night()
    assert controller.snapshot().phase is AppPhase.SUMMON
    assert controller.snapshot().units == ()
    fresh_detector(controller)
    drain(queue)
    view = asyncio.run(controller.summon("Bahay Kubo"))
    assert view.is_returning is True
    assert view.unit_id == kubo_record.unit_id
    assert view.badges == ("hp",)
    results = [m for m in drain(queue) if m["type"] in ("summon.result", "moment")]
    assert any(m["type"] == "summon.result" and m["returning"] for m in results)
    assert any(
        m["type"] == "moment" and m["moment"] == "object_recognized" for m in results
    )
    with pytest.raises(GameError):
        asyncio.run(controller.reroll_unit(view.unit_id))
    asyncio.run(controller.summon("Stapler"))
    asyncio.run(controller.summon("Phone"))
    controller.begin_night()
    controller.claim("Migs", ["u_kubo", "u_2", "u_3"], CONTENT.clean_player_name)
    controller.finish_claims()
    night = controller.snapshot().night
    assert night is not None
    kubo = next(u for u in night.units if u.game_id == "u_kubo")
    assert kubo.hp_max == kubo_before.hp_max + 1
    assert kubo.hp == kubo.hp_max
    assert kubo.badges == ("hp",)
    controller.close()
    store.close()


def test_scars_and_cooldown_badges_reach_unit_stats(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    summon_three(controller)
    records = {u.sam_object_id: u for u in controller._units}
    fighter = records[2]
    store.set_unit_progress(fighter.unit_id, ["cooldown", "hp"], ["s1"])
    controller._load_progress()
    controller.begin_night()
    controller.claim("Migs", ["u_kubo", "u_2", "u_3"], CONTENT.clean_player_name)
    controller.finish_claims()
    session = controller._session
    assert session is not None and session.board is not None
    unit = next(u for u in session.board.units if u.id == "u_2")
    assert unit.hp_max == fighter.card.hp_max
    assert unit.hp == unit.hp_max
    assert unit.cooldown_cut == 1
    controller.close()
    store.close()


def test_recap_is_saved_at_sunrise_and_shown_on_continue(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    controller._recap_builder = RecapBuilder(BANK, CONTENT)
    start_night(controller)
    finish_night(controller, downed=("u_3",))
    campaign = controller.snapshot().campaign
    assert campaign is not None
    saved = store.get_recap(campaign.id)
    assert saved is not None
    assert saved.source == "line_bank"
    recap = Recap.from_json(saved.text)
    assert recap.text_tl.startswith("Kagabi")
    assert recap.night == 1
    assert recap.source is RecapSource.LINE_BANK
    controller.close()
    again = controller_for(store, ConfidentSegmenter())
    again.continue_campaign(campaign.id)
    shown = again.snapshot().recap
    assert shown == recap
    payload = state_json(again.snapshot())["recap"]
    assert payload == recap.to_dict()
    again.select_camera(0)
    assert again.snapshot().recap == recap
    for name in ("Mug", "Stapler", "Phone"):
        asyncio.run(again.summon(name))
    again.begin_night()
    again.claim("Migs", ["u_kubo", "u_2", "u_3"], CONTENT.clean_player_name)
    assert again.snapshot().recap is not None
    again.finish_claims()
    assert again.snapshot().recap is None
    assert store.get_recap(campaign.id) is None
    again.close()
    store.close()


def test_defeat_recap_uses_the_losing_line(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    controller._recap_builder = RecapBuilder(BANK, CONTENT)
    start_night(controller)
    session = controller._session
    assert session is not None and session.board is not None
    session._board = replace(
        session.board,
        units=tuple(
            replace(u, hp=0) if u.id in ("u_2", "u_3") else u
            for u in session.board.units
        ),
    )

    async def run() -> None:
        await controller.end_turn()
        await controller.wait_for_background()

    asyncio.run(run())
    snapshot = controller.snapshot()
    assert snapshot.phase is AppPhase.DEFEAT
    assert snapshot.progression is not None
    assert snapshot.progression.nights_survived == 0
    assert snapshot.progression.badge_offers == ()
    assert snapshot.campaign is not None
    saved = store.get_recap(snapshot.campaign.id)
    assert saved is not None
    assert BANK.fill("recap_lose", "x", {})[2] is not None
    controller.close()
    store.close()


def test_recap_uses_the_local_path_when_no_loop_is_bound(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    controller._recap_builder = RecapBuilder(BANK, CONTENT)
    start_night(controller)
    session = controller._session
    assert session is not None and session.board is not None
    session._board = replace(session.board, turn=TURNS_PER_NIGHT)
    controller._finalize_night(session, RecapOutcome.SUNRISE)
    campaign = controller.snapshot().campaign
    assert campaign is not None
    assert store.get_recap(campaign.id) is not None
    controller.close()
    store.close()


def test_generated_map_is_made_once_served_and_deleted(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    broadcast = Broadcast()
    queue = broadcast.subscribe()
    controller = controller_for(store, ConfidentSegmenter(), broadcast=broadcast)
    service = ScriptedService(tmp_path / "maps", [generated()])
    controller._map_service = service

    async def play() -> None:
        from tests.test_night import ready_for_summon

        ready_for_summon(controller)
        assert controller.snapshot().map.is_enabled is False
        assert controller.map_png() is None
        controller.set_setting("generated_map", True)
        assert controller.snapshot().map.is_working is True
        await controller.wait_for_background()
        view = controller.snapshot().map
        assert (view.is_enabled, view.is_ready, view.is_working) == (True, True, False)
        assert controller.map_png() is not None
        messages = drain(queue)
        assert any(m["type"] == "map" for m in messages)
        controller.set_setting("generated_map", False)
        assert controller.snapshot().map.is_ready is False
        assert controller.map_png() is None
        controller.set_setting("generated_map", True)
        await controller.wait_for_background()
        assert len(service.references) == 1

    asyncio.run(play())
    campaign = controller.snapshot().campaign
    assert campaign is not None
    assert service.cached_map(campaign.id) is not None
    controller.close()
    store.close()


def test_map_is_skipped_when_off_or_in_demo_safe(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    service = ScriptedService(tmp_path / "maps", [generated()])
    controller._map_service = service
    controller.set_demo_safe(True)
    controller.set_setting("generated_map", True)

    async def play() -> None:
        from tests.test_night import ready_for_summon

        ready_for_summon(controller)
        await controller.wait_for_background()

    asyncio.run(play())
    assert service.references == []
    assert controller.snapshot().map.is_ready is False
    controller.close()
    store.close()


def test_deleting_a_campaign_removes_its_map(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    service = ScriptedService(tmp_path / "maps", [])
    controller._map_service = service
    campaign = store.create_campaign("X", Difficulty.NORMAL)
    path = service.map_path(campaign.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"png")
    assert service.cached_map(campaign.id) is not None
    controller.delete_campaign(campaign.id)
    assert service.cached_map(campaign.id) is None
    controller.close()
    store.close()


def test_map_and_crops_requests_over_the_socket(client: TestClient) -> None:
    with connect(client) as ws:
        receive_type(ws, "state")
        send(ws, {"type": "map.get"})
        assert receive_type(ws, "notice")["copy_key"] == "map.none"
        receive_type(ws, "state")
        send(ws, {"type": "crops.get"})
        assert receive_type(ws, "crops")["crops"] == {}


def test_crops_return_the_reference_crop_of_each_unit(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    summon_three(controller)
    crops = controller.crops()
    assert set(crops) == {u.unit_id for u in controller._units}
    assert all(len(value) > 20 for value in crops.values())
    controller.close()
    store.close()


def test_state_carries_new_unit_fields(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    summon_three(controller)
    payload = state_json(controller.snapshot())
    first = payload["units"][0]  # type: ignore[index]
    assert first["returning"] is False
    assert first["badges"] == []
    assert first["scars"] == 0
    assert payload["progression"] == {
        "barrio_level": 0,
        "nights_survived": 0,
        "badge_offers": [],
    }
    assert payload["pending_confirm"] is None
    assert payload["recap"] is None
    assert payload["map"] == {"enabled": False, "ready": False, "working": False}
    controller.close()
    store.close()


def test_continue_sends_the_saved_recap_over_the_socket(tmp_path: Path) -> None:
    from server import create_app

    seed = Store(tmp_path / "desktop.sqlite")
    campaign = seed.create_campaign("Barkada", Difficulty.NORMAL)
    recap = Recap(
        night=2,
        text_tl="Kagabi, nagtagumpay kayo.",
        text_en="Last night you won.",
        mood=BANK.fill("recap_win", "x", {})[2],
        source=RecapSource.GLIMMER,
    )
    seed.save_recap(campaign.id, recap.to_json(), recap.source.value)
    seed.close()
    settings = AppSettings(token=TOKEN, data_dir=tmp_path, port=8765, api_key=None)
    app = create_app(settings, frozenset({ORIGIN}), make_factory(tmp_path))
    with TestClient(app) as test_client, connect(test_client) as ws:
        assert receive_type(ws, "state")["recap"] is None
        send(ws, {"type": "campaign.start", "campaign_id": campaign.id})
        message = receive_type(ws, "recap")
        assert message["source"] == "glimmer"
        assert message["text_tl"] == "Kagabi, nagtagumpay kayo."
        assert message["night"] == 2
        state = receive_type(ws, "state")
        assert state["recap"]["source"] == "glimmer"  # type: ignore[index]

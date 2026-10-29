import asyncio
import json
from pathlib import Path

import pytest

import replay.render as render_module
from db.store import Store
from game.night import AppPhase, GameController, GameError
from replay.highlights import (
    Highlight,
    RecordingMeta,
    ReplayError,
    TurnLogRow,
    load_recording_meta,
)
from replay.proxy import Segment
from replay.render import ReelRequest, ReelResult, anchor_tracks, make_reel
from tests.test_night_flow import play_turns
from tests.test_recording_flow import Factory, setup


def finished_recorded_night(tmp_path: Path) -> tuple[Store, GameController, Factory]:
    factory = Factory()
    store, controller = setup(tmp_path, factory)
    controller.give_consent("Migs", True)
    controller.give_consent("Bea", True)
    controller.finish_claims()
    play_turns(controller, 8)
    assert controller.snapshot().phase in (AppPhase.SUNRISE, AppPhase.DEFEAT)
    return store, controller, factory


class Runner:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[ReelRequest, bool]] = []
        self.error = error

    async def __call__(self, request: ReelRequest, is_paid: bool) -> ReelResult:
        self.calls.append((request, is_paid))
        if self.error is not None:
            raise self.error
        request.out_path.write_bytes(b"mp4")
        return ReelResult(request.out_path, 30.0, 900, 9, 10)


def test_replay_runs_after_a_recorded_night(tmp_path: Path) -> None:
    store, controller, factory = finished_recorded_night(tmp_path)
    runner = Runner()
    controller._replay_runner = runner
    assert controller.snapshot().can_replay

    async def go() -> None:
        controller.request_replay("SUMIKAT NA", "SUNRISE")
        assert controller.snapshot().replay_status == "working"
        with pytest.raises(GameError):
            controller.request_replay("SUMIKAT NA", "SUNRISE")
        await controller.wait_for_replay()

    asyncio.run(go())
    request, is_paid = runner.calls[0]
    assert is_paid
    assert request.sidecar == factory.made[0].path.with_suffix(".json")
    assert request.out_path.parent == request.sidecar.parent
    assert request.root == store.data_root
    assert any(row.event_type == "transition" for row in request.rows)
    snapshot = controller.snapshot()
    assert snapshot.replay_status == "done"
    assert snapshot.replay_file == request.out_path.name
    keys = [key for key, _ in controller.drain_notices()]
    assert "replay.making" in keys
    assert "replay.done" in keys
    controller.next_night()
    assert controller.snapshot().replay_status == "idle"
    assert not controller.snapshot().can_replay
    controller.close()
    store.close()


def test_replay_failure_and_demo_safe(tmp_path: Path) -> None:
    store, controller, _ = finished_recorded_night(tmp_path)
    runner = Runner(ReplayError("ffmpeg was not found"))
    controller._replay_runner = runner
    controller.set_demo_safe(True)

    async def go() -> None:
        controller.request_replay("SUMIKAT NA", "SUNRISE")
        await controller.wait_for_replay()

    asyncio.run(go())
    assert runner.calls[0][1] is False
    assert controller.snapshot().replay_status == "failed"
    assert "replay.failed" in [key for key, _ in controller.drain_notices()]
    controller.close()
    store.close()


def test_replay_needs_a_consented_recording(tmp_path: Path) -> None:
    factory = Factory()
    store, controller = setup(tmp_path, factory)
    controller._replay_runner = Runner()
    controller.finish_claims()
    with pytest.raises(GameError):
        controller.request_replay("SUMIKAT NA", "SUNRISE")
    play_turns(controller, 8)
    with pytest.raises(GameError) as info:
        controller.request_replay("SUMIKAT NA", "SUNRISE")
    assert info.value.copy_key == "replay.none"
    controller.close()
    store.close()


def write_sidecar(tmp_path: Path) -> Path:
    folder = tmp_path / "recordings"
    folder.mkdir()
    (folder / "night.mp4").write_bytes(b"x")
    sidecar = folder / "night.json"
    sidecar.write_text(
        json.dumps(
            {
                "version": 1,
                "video": "night.mp4",
                "width": 1200,
                "height": 800,
                "fps": 25,
                "started_t_ms": 1000,
                "duration_s": 60.0,
                "anchors": [{"t_ms": 1000, "boxes": {"u_2": [10, 20, 50, 60]}}],
                "sprites": {},
            }
        ),
        encoding="utf-8",
    )
    return sidecar


def reel_request(
    tmp_path: Path, sidecar: Path, rows: tuple[TurnLogRow, ...]
) -> ReelRequest:
    return ReelRequest(
        sidecar=sidecar,
        rows=rows,
        sprites={},
        out_path=sidecar.parent / "reel.mp4",
        work_dir=sidecar.parent / "work",
        root=tmp_path,
        ffmpeg="ffmpeg",
        title_tl="T",
        title_en="E",
        night_number=1,
    )


ROWS = (
    TurnLogRow(
        1,
        "CHECK_END",
        "kubo_hit",
        {"src": "e_aswang_1", "dst": "u_kubo", "dmg": 2},
        9000,
    ),
    TurnLogRow(8, "CHECK_END", "win", {}, 50000),
)


def test_make_reel_falls_back_to_anchor_tracks_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = reel_request(tmp_path, write_sidecar(tmp_path), ROWS)
    seen: dict[str, object] = {}

    def fake_build(
        meta: RecordingMeta,
        highlights: tuple[Highlight, ...],
        work_dir: Path,
        *_: object,
    ) -> tuple[Path, tuple[Segment, ...]]:
        work_dir.mkdir(parents=True, exist_ok=True)
        segments = tuple(
            Segment(h, index * 80, 80) for index, h in enumerate(highlights)
        )
        return work_dir / "proxy.mp4", segments

    async def failing_track(*_: object) -> dict[str, object]:
        raise ReplayError("sam down")

    def fake_render(
        meta: RecordingMeta, segments: tuple[Segment, ...], tracks: object, *_: object
    ) -> ReelResult:
        seen["tracks"] = tracks
        return ReelResult(request.out_path, 20.0, 600, 1, 1)

    monkeypatch.setattr(render_module, "build_proxy", fake_build)
    monkeypatch.setattr(render_module, "track_highlights", failing_track)
    monkeypatch.setattr(render_module, "render_reel", fake_render)
    result = asyncio.run(make_reel(request, object(), object()))  # type: ignore[arg-type]
    assert result.path == request.out_path
    assert not request.work_dir.exists()
    tracks = seen["tracks"]
    assert isinstance(tracks, dict)
    assert tracks["u_2"][0].left == 10
    assert asyncio.run(make_reel(request, None, None)).seconds == 20.0


def test_make_reel_without_highlights_fails(tmp_path: Path) -> None:
    request = reel_request(tmp_path, write_sidecar(tmp_path), ())
    with pytest.raises(ReplayError):
        asyncio.run(make_reel(request, None, None))


def test_anchor_tracks_cover_each_segment(tmp_path: Path) -> None:
    meta = load_recording_meta(write_sidecar(tmp_path))
    highlight = Highlight("last_turn", 8, 10.0, 8.0, ())
    tracks = anchor_tracks(
        meta, (Segment(highlight, 0, 80), Segment(highlight, 80, 80))
    )
    assert [box.frame for box in tracks["u_2"]] == [0, 79, 80, 159]

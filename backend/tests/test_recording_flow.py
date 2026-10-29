import json
from pathlib import Path

import numpy as np

from capture.recorder import RecorderError, RecordingResult
from db.store import Store
from game.night import AppPhase, GameController
from tests.test_night import CONTENT
from tests.test_night_flow import play_turns
from tests.test_tracking_flow import ConfidentSegmenter, controller_for, summon_three


class FakeRecorder:
    def __init__(
        self, path: Path, width: int, height: int, root: Path, fail: bool
    ) -> None:
        self.path = path
        self.size = (width, height)
        self.root = root
        self.fail = fail
        self.frames = 0
        self.stopped = 0
        self.is_recording = False

    def start(self) -> None:
        if self.fail:
            raise RecorderError("no ffmpeg")
        self.is_recording = True

    def write(self, frame: np.ndarray) -> bool:
        self.frames += 1
        return True

    def stop(self) -> RecordingResult:
        self.stopped += 1
        self.is_recording = False
        return RecordingResult(self.path, self.frames, 0, 1.0, True)


class Factory:
    def __init__(self, fail: bool = False) -> None:
        self.made: list[FakeRecorder] = []
        self.fail = fail

    def __call__(self, path: Path, width: int, height: int, root: Path) -> FakeRecorder:
        recorder = FakeRecorder(path, width, height, root, self.fail)
        self.made.append(recorder)
        return recorder


def setup(tmp_path: Path, factory: Factory) -> tuple[Store, GameController]:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    controller._recorder_factory = factory  # type: ignore[assignment]
    summon_three(controller)
    controller.begin_night()
    controller.claim("Migs", ["u_2"], CONTENT.clean_player_name)
    controller.claim("Bea", ["u_3"], CONTENT.clean_player_name)
    return store, controller


def test_recording_starts_only_with_full_consent_and_stops_at_the_end(
    tmp_path: Path,
) -> None:
    factory = Factory()
    store, controller = setup(tmp_path, factory)
    controller.give_consent("Migs", True)
    controller.give_consent("Bea", True)
    assert dict(controller.snapshot().consents) == {"Migs": True, "Bea": True}
    controller.finish_claims()
    recorder = factory.made[0]
    campaign = controller.snapshot().campaign
    assert campaign is not None
    assert recorder.path.parent == store.campaign_dir(campaign.id) / "recordings"
    assert recorder.root == store.data_root
    assert controller.snapshot().is_recording
    assert ("rec.on", {}) in controller.drain_notices()
    assert controller.wait_for_frame() is not None
    controller.render_frame(1)
    controller.render_frame(2)
    assert recorder.frames == 2
    play_turns(controller, 8)
    assert controller.snapshot().phase in (AppPhase.SUNRISE, AppPhase.DEFEAT)
    assert recorder.stopped == 1
    assert not controller.snapshot().is_recording
    controller.close()
    assert recorder.stopped == 1
    store.close()


def test_missing_consent_means_no_recording(tmp_path: Path) -> None:
    factory = Factory()
    store, controller = setup(tmp_path, factory)
    controller.give_consent("Migs", True)
    controller.finish_claims()
    assert factory.made == []
    assert not controller.snapshot().is_recording
    controller.close()
    store.close()


def test_missing_ffmpeg_keeps_the_night_going(tmp_path: Path) -> None:
    factory = Factory(fail=True)
    store, controller = setup(tmp_path, factory)
    controller.give_consent("Migs", True)
    controller.give_consent("Bea", True)
    controller.finish_claims()
    assert controller.snapshot().phase is AppPhase.PLAYER_PHASE
    assert not controller.snapshot().is_recording
    assert ("rec.unavailable", {}) in controller.drain_notices()
    controller.close()
    store.close()


def test_sidecar_tracks_time_anchors_and_duration(tmp_path: Path) -> None:
    factory = Factory()
    store, controller = setup(tmp_path, factory)
    controller.give_consent("Migs", True)
    controller.give_consent("Bea", True)
    controller.finish_claims()
    recorder = factory.made[0]
    sidecar = recorder.path.with_suffix(".json")
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["video"] == recorder.path.name
    assert (data["width"], data["height"]) == recorder.size
    assert data["fps"] == 25
    assert data["started_t_ms"] >= 0
    assert len(data["anchors"]) == 1
    assert set(data["anchors"][0]["boxes"]) == {"u_kubo", "u_2", "u_3"}
    play_turns(controller, 1)
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert len(data["anchors"]) == 2
    assert data["anchors"][1]["t_ms"] >= data["anchors"][0]["t_ms"]
    controller.close()
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["duration_s"] == 1.0
    store.close()

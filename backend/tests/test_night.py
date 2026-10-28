from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt
import pytest

from capture.camera import VideoSource, list_microphones
from db.store import Difficulty, Store
from game.night import AppPhase, FramePump, GameController, GameError
from state import FrameView, LiveState
from tests.test_server import SCENE, SHEET, SceneSource

Image = npt.NDArray[np.uint8]


class ShiftedSource(SceneSource):
    def read(self) -> tuple[bool, Image | None]:
        matrix = np.array([[1.0, 0.0, 120.0], [0.0, 1.0, 0.0]])
        moved = cv2.warpAffine(
            SCENE, matrix, (1920, 1080), borderMode=cv2.BORDER_REFLECT
        )
        return True, np.asarray(moved, dtype=np.uint8)


def controller_with(store: Store, source: type[SceneSource]) -> GameController:
    def factory(_: int) -> VideoSource:
        return source()

    return GameController(store, LiveState(), has_api_key=True, camera_factory=factory)


def calibrate_campaign(store: Store) -> str:
    controller = controller_with(store, SceneSource)
    controller.start_new_campaign("Barkada", Difficulty.NORMAL)
    controller.select_camera(0)
    controller.submit_corners(SHEET, 60.0, 40.0)
    controller.confirm_calibration()
    snapshot = controller.snapshot()
    controller.close()
    assert snapshot.phase is AppPhase.SUMMON
    assert snapshot.campaign is not None
    return snapshot.campaign.id


def test_continue_with_unmoved_camera_skips_calibration(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    campaign_id = calibrate_campaign(store)
    controller = controller_with(store, SceneSource)
    controller.continue_campaign(campaign_id)
    assert controller.snapshot().phase is AppPhase.CALIBRATE
    controller.select_camera(0)
    assert controller.snapshot().phase is AppPhase.SUMMON
    controller.close()
    store.close()


def test_continue_with_moved_camera_asks_to_recalibrate(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    campaign_id = calibrate_campaign(store)
    controller = controller_with(store, ShiftedSource)
    controller.continue_campaign(campaign_id)
    with pytest.raises(GameError) as info:
        controller.select_camera(0)
    assert info.value.copy_key == "cam.moved"
    assert controller.snapshot().phase is AppPhase.CALIBRATE
    controller.restart_calibration()
    assert controller.snapshot().is_previewing is False
    controller.close()
    store.close()


def test_confirm_without_corners_is_rejected(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_with(store, SceneSource)
    controller.start_new_campaign("B", Difficulty.MADALI)
    with pytest.raises(GameError):
        controller.confirm_calibration()
    controller.close()
    store.close()


def test_frame_pump_publishes_raw_then_warped(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    live = LiveState()

    def factory(_: int) -> VideoSource:
        return SceneSource()

    controller = GameController(store, live, has_api_key=False, camera_factory=factory)
    pump = FramePump(controller, live)
    assert not pump.pump_once(1)
    controller.start_new_campaign("B", Difficulty.NORMAL)
    controller.select_camera(0)
    controller.submit_corners(SHEET, 60.0, 40.0)
    assert controller.wait_for_frame() is not None
    assert pump.pump_once(2)
    frame = live.latest()
    assert frame is not None
    assert frame.view is FrameView.WARPED
    assert (frame.width, frame.height) == (1200, 800)
    controller.close()
    store.close()


def test_list_microphones_keeps_input_devices_only() -> None:
    devices: list[dict[str, object]] = [
        {"name": "Speakers", "max_input_channels": 0},
        {"name": "Mic", "max_input_channels": 2},
        {"name": "Odd", "max_input_channels": "2"},
    ]
    found = list_microphones(lambda: devices)
    assert [(m.index, m.name) for m in found] == [(1, "Mic")]

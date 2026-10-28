import threading
from collections.abc import Callable

import cv2
import numpy as np
import numpy.typing as npt
import pytest

from capture.camera import (
    Camera,
    CameraBusyError,
    CameraError,
    CameraResolutionError,
    VideoSource,
    list_cameras,
)

Image = npt.NDArray[np.uint8]
WAIT_S = 2.0


class FakeSource:
    def __init__(
        self,
        is_open: bool = True,
        size: tuple[int, int] = (1920, 1080),
        frames: int | None = None,
    ) -> None:
        self._is_open = is_open
        self._size = size
        self._frames_left = frames
        self.released = False
        self.reads = 0
        self.first_frame = threading.Event()

    def isOpened(self) -> bool:
        return self._is_open

    def set(self, prop_id: int, value: float) -> bool:
        return True

    def get(self, prop_id: int) -> float:
        if prop_id == cv2.CAP_PROP_FRAME_WIDTH:
            return float(self._size[0])
        return float(self._size[1])

    def read(self) -> tuple[bool, Image | None]:
        self.reads += 1
        if self._frames_left is not None:
            if self._frames_left <= 0:
                return False, None
            self._frames_left -= 1
        self.first_frame.set()
        return True, np.zeros((4, 4, 3), dtype=np.uint8)

    def release(self) -> None:
        self.released = True


def factory_for(source: FakeSource) -> Callable[[int], VideoSource]:
    return lambda _: source


def test_open_busy_camera_raises_and_releases() -> None:
    source = FakeSource(is_open=False)
    with pytest.raises(CameraBusyError):
        Camera(0, factory=factory_for(source)).open()
    assert source.released


def test_low_resolution_camera_is_rejected() -> None:
    source = FakeSource(size=(640, 480))
    with pytest.raises(CameraResolutionError):
        Camera(0, factory=factory_for(source)).open()
    assert source.released


def test_index_out_of_range() -> None:
    with pytest.raises(CameraError):
        Camera(9)


def test_start_requires_open() -> None:
    with pytest.raises(CameraError):
        Camera(0, factory=factory_for(FakeSource())).start()


def test_frame_loop_publishes_latest_frame() -> None:
    source = FakeSource(frames=3)
    camera = Camera(0, factory=factory_for(source), clock=lambda: 5.0)
    assert camera.open() == (1920, 1080)
    camera.start()
    assert camera.join(WAIT_S)
    frame = camera.latest()
    assert frame is not None
    assert frame.captured_at == 5.0
    assert frame.sequence == 3
    assert camera.has_failed
    camera.stop()
    assert source.released


def test_repeated_read_failures_mark_the_camera_failed() -> None:
    source = FakeSource(frames=0)
    camera = Camera(0, factory=factory_for(source))
    camera.open()
    camera.start()
    assert camera.join(WAIT_S)
    assert camera.has_failed
    assert camera.latest() is None
    assert source.reads == 30
    camera.stop()


def test_stop_ends_a_running_loop() -> None:
    source = FakeSource()
    camera = Camera(0, factory=factory_for(source))
    camera.open()
    camera.start()
    assert source.first_frame.wait(WAIT_S)
    camera.stop()
    assert not camera.is_running
    assert source.released


def test_list_cameras_reports_open_devices() -> None:
    sources = {
        0: FakeSource(),
        1: FakeSource(is_open=False),
        2: FakeSource(size=(1280, 720)),
    }

    def factory(index: int) -> VideoSource:
        return sources.get(index, FakeSource(is_open=False))

    found = list_cameras(factory)
    assert [(c.index, c.width, c.height) for c in found] == [
        (0, 1920, 1080),
        (2, 1280, 720),
    ]
    assert all(source.released for source in sources.values())

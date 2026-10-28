import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Protocol

import cv2
import numpy as np
import numpy.typing as npt

from config import CAMERA_CAPTURE_SIZE, CAMERA_MIN_SIZE

Image = npt.NDArray[np.uint8]

MAX_CAMERA_INDEX: Final = 6
READ_FAILURE_LIMIT: Final = 30
STOP_TIMEOUT_S: Final = 2.0


class CameraError(Exception):
    pass


class CameraBusyError(CameraError):
    pass


class CameraResolutionError(CameraError):
    pass


class VideoSource(Protocol):
    def isOpened(self) -> bool: ...

    def set(self, prop_id: int, value: float) -> bool: ...

    def get(self, prop_id: int) -> float: ...

    def read(self) -> tuple[bool, Image | None]: ...

    def release(self) -> None: ...


SourceFactory = Callable[[int], VideoSource]


class DirectShowSource:
    def __init__(self, index: int) -> None:
        self._capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)

    def isOpened(self) -> bool:
        return bool(self._capture.isOpened())

    def set(self, prop_id: int, value: float) -> bool:
        return bool(self._capture.set(prop_id, value))

    def get(self, prop_id: int) -> float:
        return float(self._capture.get(prop_id))

    def read(self) -> tuple[bool, Image | None]:
        ok, image = self._capture.read()
        if not ok:
            return False, None
        return True, np.asarray(image, dtype=np.uint8)

    def release(self) -> None:
        self._capture.release()


def open_directshow(index: int) -> VideoSource:
    return DirectShowSource(index)


@dataclass(frozen=True)
class CameraInfo:
    index: int
    width: int
    height: int


@dataclass(frozen=True)
class Frame:
    image: Image
    captured_at: float
    sequence: int


def list_cameras(factory: SourceFactory = open_directshow) -> list[CameraInfo]:
    found: list[CameraInfo] = []
    for index in range(MAX_CAMERA_INDEX):
        source = factory(index)
        try:
            if not source.isOpened():
                continue
            width = int(source.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(source.get(cv2.CAP_PROP_FRAME_HEIGHT))
            found.append(CameraInfo(index=index, width=width, height=height))
        finally:
            source.release()
    return found


class Camera:
    def __init__(
        self,
        index: int,
        factory: SourceFactory = open_directshow,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not 0 <= index < MAX_CAMERA_INDEX:
            raise CameraError("camera index out of range")
        self._index = index
        self._factory = factory
        self._clock = clock
        self._lock = threading.Lock()
        self._latest: Frame | None = None
        self._source: VideoSource | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._failed = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def has_failed(self) -> bool:
        return self._failed.is_set()

    def open(self) -> tuple[int, int]:
        source = self._factory(self._index)
        if not source.isOpened():
            source.release()
            raise CameraBusyError("camera is busy or missing")
        source.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_CAPTURE_SIZE[0])
        source.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_CAPTURE_SIZE[1])
        width = int(source.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(source.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width < CAMERA_MIN_SIZE[0] or height < CAMERA_MIN_SIZE[1]:
            source.release()
            raise CameraResolutionError("camera must support 1280x720 or more")
        self._source = source
        return width, height

    def start(self) -> None:
        if self._source is None:
            raise CameraError("open the camera before starting it")
        if self.is_running:
            return
        self._stop.clear()
        self._failed.clear()
        self._thread = threading.Thread(
            target=self._loop, name="camera-loop", daemon=True
        )
        self._thread.start()

    def join(self, timeout: float) -> bool:
        if self._thread is None:
            return True
        self._thread.join(timeout=timeout)
        return not self._thread.is_alive()

    def latest(self) -> Frame | None:
        with self._lock:
            return self._latest

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=STOP_TIMEOUT_S)
            self._thread = None
        if self._source is not None:
            self._source.release()
            self._source = None

    def _loop(self) -> None:
        source = self._source
        if source is None:
            return
        failures = 0
        sequence = 0
        while not self._stop.is_set():
            ok, image = source.read()
            if not ok or image is None:
                failures += 1
                if failures >= READ_FAILURE_LIMIT:
                    self._failed.set()
                    return
                continue
            failures = 0
            sequence += 1
            frame = Frame(image=image, captured_at=self._clock(), sequence=sequence)
            with self._lock:
                self._latest = frame


@dataclass(frozen=True)
class MicrophoneInfo:
    index: int
    name: str


DeviceQuery = Callable[[], Sequence[Mapping[str, object]]]


def query_sound_devices() -> Sequence[Mapping[str, object]]:
    import sounddevice  # type: ignore[import-untyped]

    devices: Sequence[Mapping[str, object]] = sounddevice.query_devices()
    return devices


def list_microphones(query: DeviceQuery = query_sound_devices) -> list[MicrophoneInfo]:
    found: list[MicrophoneInfo] = []
    for index, device in enumerate(query()):
        channels = device.get("max_input_channels", 0)
        if not isinstance(channels, int) or channels <= 0:
            continue
        found.append(MicrophoneInfo(index=index, name=str(device.get("name", ""))[:80]))
    return found

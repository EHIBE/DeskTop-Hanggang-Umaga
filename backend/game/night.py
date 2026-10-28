import base64
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

import cv2
import numpy as np
import numpy.typing as npt

from capture.calibration import (
    Calibration,
    CalibrationError,
    Corners,
    PlayArea,
    compute_calibration,
    is_camera_moved,
    warp,
)
from capture.camera import (
    Camera,
    CameraError,
    CameraInfo,
    MicrophoneInfo,
    SourceFactory,
    list_cameras,
    list_microphones,
    open_directshow,
)
from config import STREAM_FPS, STREAM_JPEG_QUALITY, STREAM_WIDTH_PX
from db.store import Campaign, Difficulty, Store
from state import EncodedFrame, FrameView, LiveState

logger = logging.getLogger("desktop.game")

Image = npt.NDArray[np.uint8]

FIRST_FRAME_TIMEOUT_S: Final = 3.0
FIRST_FRAME_POLL_S: Final = 0.05
DEMO_SAFE_SETTING: Final = "demo_safe"
CAMERA_SETTING: Final = "camera_index"


class AppPhase(StrEnum):
    START = "START"
    CALIBRATE = "CALIBRATE"
    SUMMON = "SUMMON"


class GameError(Exception):
    def __init__(self, copy_key: str) -> None:
        super().__init__(copy_key)
        self.copy_key = copy_key


@dataclass(frozen=True)
class Snapshot:
    phase: AppPhase
    campaign: Campaign | None
    camera: CameraInfo | None
    is_calibrated: bool
    is_previewing: bool
    play_w_cm: float
    play_h_cm: float
    is_demo_safe: bool
    has_api_key: bool


@dataclass(frozen=True)
class Devices:
    cameras: tuple[CameraInfo, ...]
    microphones: tuple[MicrophoneInfo, ...]


def encode_jpeg(image: Image) -> tuple[str, int, int]:
    height, width = image.shape[:2]
    scale = STREAM_WIDTH_PX / width
    resized = cv2.resize(
        image, (STREAM_WIDTH_PX, round(height * scale)), interpolation=cv2.INTER_AREA
    )
    ok, buffer = cv2.imencode(
        ".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, STREAM_JPEG_QUALITY]
    )
    if not ok:
        raise GameError("cam.busy")
    return base64.b64encode(buffer.tobytes()).decode("ascii"), width, height


def encode_png(image: Image) -> bytes:
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise GameError("cam.busy")
    return buffer.tobytes()


class GameController:
    def __init__(
        self,
        store: Store,
        live: LiveState,
        has_api_key: bool,
        camera_factory: SourceFactory = open_directshow,
        list_camera_devices: Callable[[], list[CameraInfo]] = list_cameras,
        list_microphone_devices: Callable[[], list[MicrophoneInfo]] = list_microphones,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._store = store
        self._live = live
        self._has_api_key = has_api_key
        self._camera_factory = camera_factory
        self._list_cameras = list_camera_devices
        self._list_microphones = list_microphone_devices
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.RLock()
        self._campaign: Campaign | None = None
        self._camera: Camera | None = None
        self._camera_info: CameraInfo | None = None
        self._area = PlayArea()
        self._calibration: Calibration | None = None
        self._is_calibrated = False
        self._is_stored_calibration = False
        self._is_demo_safe = store.get_setting(DEMO_SAFE_SETTING) == "1"

    def snapshot(self) -> Snapshot:
        with self._lock:
            return Snapshot(
                phase=self._phase(),
                campaign=self._campaign,
                camera=self._camera_info,
                is_calibrated=self._is_calibrated,
                is_previewing=self._calibration is not None and not self._is_calibrated,
                play_w_cm=self._area.width_cm,
                play_h_cm=self._area.height_cm,
                is_demo_safe=self._is_demo_safe,
                has_api_key=self._has_api_key,
            )

    def _phase(self) -> AppPhase:
        if self._campaign is None:
            return AppPhase.START
        if not self._is_calibrated:
            return AppPhase.CALIBRATE
        return AppPhase.SUMMON

    def list_campaigns(self) -> list[Campaign]:
        return self._store.list_campaigns()

    def devices(self) -> Devices:
        return Devices(
            cameras=tuple(self._list_cameras()),
            microphones=tuple(self._list_microphones()),
        )

    def start_new_campaign(self, name: str, difficulty: Difficulty) -> None:
        campaign = self._store.create_campaign(name.strip(), difficulty)
        self._enter_campaign(campaign)

    def continue_campaign(self, campaign_id: str) -> None:
        self._enter_campaign(self._store.get_campaign(campaign_id))

    def _enter_campaign(self, campaign: Campaign) -> None:
        with self._lock:
            self._campaign = campaign
            self._calibration = None
            self._is_calibrated = False
            self._is_stored_calibration = False
            self._area = PlayArea()
            stored = self._store.latest_calibration(campaign.id)
            if stored is None:
                return
            try:
                area = PlayArea(width_cm=stored.play_w_cm, height_cm=stored.play_h_cm)
            except CalibrationError:
                logger.warning("stored calibration has an invalid play area")
                return
            self._area = area
            self._calibration = Calibration(
                homography=np.array(stored.homography, dtype=np.float64).reshape(3, 3),
                area=area,
            )
            self._is_stored_calibration = True
            if self._camera is not None:
                self._check_stored_calibration()

    def select_camera(self, index: int) -> None:
        with self._lock:
            self._close_camera()
            camera = Camera(index, factory=self._camera_factory, clock=self._clock)
            try:
                width, height = camera.open()
            except CameraError as error:
                logger.warning(
                    "camera %s could not open: %s", index, type(error).__name__
                )
                raise GameError("cam.busy") from error
            camera.start()
            self._camera = camera
            self._camera_info = CameraInfo(index=index, width=width, height=height)
            self._store.set_setting(CAMERA_SETTING, str(index))
            if self._is_stored_calibration and not self._is_calibrated:
                self._check_stored_calibration()

    def _check_stored_calibration(self) -> None:
        if self._campaign is None or self._calibration is None:
            return
        stored = self._store.latest_calibration(self._campaign.id)
        frame = self.wait_for_frame()
        if stored is None or frame is None:
            return
        try:
            encoded = stored.baseline_path.read_bytes()
        except OSError as error:
            raise GameError("cam.moved") from error
        baseline = cv2.imdecode(
            np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR
        )
        current = warp(frame, self._calibration)
        if baseline is None or baseline.shape != current.shape:
            raise GameError("cam.moved")
        if is_camera_moved(np.asarray(baseline, dtype=np.uint8), current, self._area):
            raise GameError("cam.moved")
        self._is_calibrated = True

    def wait_for_frame(self) -> Image | None:
        camera = self._camera
        if camera is None:
            return None
        deadline = self._clock() + FIRST_FRAME_TIMEOUT_S
        while self._clock() < deadline:
            frame = camera.latest()
            if frame is not None:
                return frame.image
            self._sleep(FIRST_FRAME_POLL_S)
        return None

    def submit_corners(
        self, corners: Corners, width_cm: float, height_cm: float
    ) -> None:
        with self._lock:
            self._require_phase(AppPhase.CALIBRATE)
            if self._camera is None:
                raise GameError("cam.busy")
            try:
                area = PlayArea(width_cm=width_cm, height_cm=height_cm)
                calibration = compute_calibration(corners, area)
            except CalibrationError as error:
                raise GameError("calib.tap") from error
            self._area = area
            self._calibration = calibration
            self._is_stored_calibration = False

    def confirm_calibration(self) -> None:
        with self._lock:
            self._require_phase(AppPhase.CALIBRATE)
            if self._calibration is None or self._campaign is None:
                raise GameError("calib.tap")
            frame = self.wait_for_frame()
            if frame is None:
                raise GameError("cam.busy")
            baseline = warp(frame, self._calibration)
            self._store.save_calibration(
                self._campaign.id,
                self._calibration.homography_list(),
                float(self._area.px_per_cm),
                (self._area.width_cm, self._area.height_cm),
                encode_png(baseline),
            )
            self._is_calibrated = True

    def restart_calibration(self) -> None:
        with self._lock:
            if self._campaign is None:
                raise GameError("start.ready")
            self._calibration = None
            self._is_calibrated = False
            self._is_stored_calibration = False

    def set_demo_safe(self, is_on: bool) -> None:
        with self._lock:
            self._is_demo_safe = is_on
            self._store.set_setting(DEMO_SAFE_SETTING, "1" if is_on else "0")

    def _require_phase(self, phase: AppPhase) -> None:
        if self._phase() is not phase:
            raise GameError("cmd.unknown")

    def render_frame(self, sequence: int) -> EncodedFrame | None:
        with self._lock:
            camera = self._camera
            calibration = self._calibration
        if camera is None:
            return None
        frame = camera.latest()
        if frame is None:
            return None
        if calibration is None:
            jpg, width, height = encode_jpeg(frame.image)
            return EncodedFrame(sequence, FrameView.RAW, width, height, jpg)
        jpg, width, height = encode_jpeg(warp(frame.image, calibration))
        return EncodedFrame(sequence, FrameView.WARPED, width, height, jpg)

    def _close_camera(self) -> None:
        if self._camera is not None:
            self._camera.stop()
        self._camera = None
        self._camera_info = None
        self._live.clear()

    def close(self) -> None:
        with self._lock:
            self._close_camera()


class FramePump:
    def __init__(
        self,
        controller: GameController,
        live: LiveState,
        fps: int = STREAM_FPS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._controller = controller
        self._live = live
        self._interval = 1.0 / fps
        self._clock = clock
        self._sleep = sleep
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="frame-pump", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def pump_once(self, sequence: int) -> bool:
        try:
            frame = self._controller.render_frame(sequence)
        except GameError:
            logger.warning("frame encode failed")
            return False
        if frame is None:
            return False
        self._live.publish(frame)
        return True

    def _loop(self) -> None:
        sequence = 0
        while not self._stop.is_set():
            started = self._clock()
            if self.pump_once(sequence + 1):
                sequence += 1
            self._sleep(max(0.0, self._interval - (self._clock() - started)))

import logging
import queue
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Protocol

import cv2
import numpy as np
import numpy.typing as npt

Image = npt.NDArray[np.uint8]

logger = logging.getLogger(__name__)

FFMPEG_ENV_KEY: Final = "DESKTOP_FFMPEG"
QUEUE_SIZE: Final = 8
POLL_INTERVAL_S: Final = 0.005
WAIT_TIMEOUT_S: Final = 5.0
WRITER_JOIN_TIMEOUT_S: Final = 5.0


class RecorderError(Exception):
    pass


class StdinLike(Protocol):
    def write(self, data: bytes, /) -> Any: ...

    def flush(self) -> None: ...

    def close(self) -> None: ...


class ProcessLike(Protocol):
    @property
    def stdin(self) -> StdinLike | None: ...

    @property
    def returncode(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def kill(self) -> None: ...


ProcessFactory = Callable[..., ProcessLike]


@dataclass(frozen=True)
class RecordingResult:
    path: Path
    frames_written: int
    frames_dropped: int
    seconds: float
    ok: bool


def find_ffmpeg(
    which: Callable[[str], str | None] = shutil.which,
    env: Mapping[str, str] | None = None,
) -> str | None:
    configured = (env or {}).get(FFMPEG_ENV_KEY)
    if configured and Path(configured).is_file():
        return configured
    return which("ffmpeg")


class Recorder:
    def __init__(
        self,
        path: Path,
        width: int,
        height: int,
        fps: int = 25,
        ffmpeg: str | None = None,
        process_factory: ProcessFactory = subprocess.Popen,
        clock: Callable[[], float] = time.monotonic,
        root: Path | None = None,
    ) -> None:
        if width <= 0 or height <= 0 or fps <= 0:
            raise RecorderError("invalid recording size or rate")
        self._path = path
        self._width = width
        self._height = height
        self._fps = fps
        self._ffmpeg = ffmpeg
        self._factory = process_factory
        self._clock = clock
        self._root = root
        self._queue: queue.Queue[Image] = queue.Queue(maxsize=QUEUE_SIZE)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._process: ProcessLike | None = None
        self._thread: threading.Thread | None = None
        self._started_at = 0.0
        self._written = 0
        self._dropped = 0
        self._broken = False
        self._recording = False
        self._result: RecordingResult | None = None

    @property
    def is_recording(self) -> bool:
        return self._recording and not self._broken

    @property
    def frames_written(self) -> int:
        with self._lock:
            return self._written

    @property
    def frames_dropped(self) -> int:
        with self._lock:
            return self._dropped

    def build_args(self) -> list[str]:
        if self._ffmpeg is None:
            raise RecorderError("ffmpeg was not found")
        return [
            self._ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{self._width}x{self._height}",
            "-r",
            str(self._fps),
            "-i",
            "-",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(self._path),
        ]

    def start(self) -> None:
        if self._recording:
            return
        if self._ffmpeg is None:
            raise RecorderError("ffmpeg was not found")
        self._check_path()
        args = self.build_args()
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            process = self._factory(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
        except (OSError, ValueError) as error:
            raise RecorderError("ffmpeg could not start") from error
        if process.stdin is None:
            process.kill()
            raise RecorderError("ffmpeg has no input pipe")
        self._process = process
        self._started_at = self._clock()
        self._stop_event.clear()
        self._recording = True
        self._thread = threading.Thread(
            target=self._loop, name="recorder-writer", daemon=True
        )
        self._thread.start()

    def write(self, frame: np.ndarray[Any, Any]) -> bool:
        if not self.is_recording:
            return False
        prepared = self._prepare(frame)
        if prepared is None:
            return False
        try:
            self._queue.put_nowait(prepared)
        except queue.Full:
            with self._lock:
                self._dropped += 1
            return False
        return True

    def stop(self) -> RecordingResult:
        if self._result is not None:
            return self._result
        if not self._recording:
            return RecordingResult(self._path, 0, 0, 0.0, False)
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=WRITER_JOIN_TIMEOUT_S)
            self._thread = None
        seconds = max(0.0, self._clock() - self._started_at)
        ok = not self._broken
        process = self._process
        if process is not None:
            ok = self._close_process(process) and ok
        self._recording = False
        self._process = None
        with self._lock:
            self._result = RecordingResult(
                path=self._path,
                frames_written=self._written,
                frames_dropped=self._dropped,
                seconds=seconds,
                ok=ok,
            )
            return self._result

    def _check_path(self) -> None:
        if self._root is None:
            raise RecorderError("recording root is required")
        try:
            root = self._root.resolve()
            target = self._path.resolve()
        except OSError as error:
            raise RecorderError("recording path is invalid") from error
        if target.parent == root or not target.parent.is_relative_to(root):
            raise RecorderError("recording path is outside the data root")
        self._path = target
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise RecorderError("recording folder could not be created") from error

    def _prepare(self, frame: np.ndarray[Any, Any]) -> Image | None:
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
            return None
        if frame.shape[0] == self._height and frame.shape[1] == self._width:
            return np.ascontiguousarray(frame)
        resized = cv2.resize(
            frame, (self._width, self._height), interpolation=cv2.INTER_AREA
        )
        return np.ascontiguousarray(resized, dtype=np.uint8)

    def _loop(self) -> None:
        last: Image | None = None
        while True:
            try:
                last = self._queue.get(timeout=POLL_INTERVAL_S)
            except queue.Empty:
                if self._stop_event.is_set():
                    break
            if self._broken:
                continue
            self._pace(last)
        self._pace(last)

    def _pace(self, last: Image | None) -> None:
        if last is None or self._broken:
            return
        process = self._process
        if process is None or process.stdin is None:
            return
        due = int(max(0.0, self._clock() - self._started_at) * self._fps)
        data = last.tobytes()
        while self._written < due:
            try:
                process.stdin.write(data)
            except (BrokenPipeError, OSError) as error:
                logger.warning("recorder write failed: %s", type(error).__name__)
                self._broken = True
                return
            with self._lock:
                self._written += 1

    def _close_process(self, process: ProcessLike) -> bool:
        ok = True
        stdin = process.stdin
        if stdin is not None:
            try:
                stdin.flush()
                stdin.close()
            except (BrokenPipeError, OSError) as error:
                logger.warning("recorder close failed: %s", type(error).__name__)
                ok = False
        try:
            code = process.wait(timeout=WAIT_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            process.kill()
            logger.warning("recorder killed ffmpeg after timeout")
            return False
        return ok and code == 0

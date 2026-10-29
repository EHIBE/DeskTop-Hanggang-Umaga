import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from capture.recorder import (
    Recorder,
    RecorderError,
    StdinLike,
    find_ffmpeg,
)

W, H = 8, 6


class FakeStdin:
    def __init__(self) -> None:
        self.chunks: list[bytes] = []
        self.closed = False
        self.fail: type[Exception] | None = None
        self.gate: threading.Event | None = None

    def write(self, data: bytes, /) -> int:
        if self.gate is not None:
            self.gate.wait(timeout=5)
        if self.fail is not None:
            raise self.fail()
        self.chunks.append(data)
        return len(data)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class FakeProcess:
    def __init__(self, hang: bool = False, code: int = 0) -> None:
        self.fake_stdin = FakeStdin()
        self.hang = hang
        self.returncode: int | None = None
        self.code = code
        self.killed = False
        self.args: list[str] = []
        self.kwargs: dict[str, Any] = {}

    @property
    def stdin(self) -> StdinLike | None:
        return self.fake_stdin

    def wait(self, timeout: float | None = None) -> int:
        if self.hang and not self.killed:
            raise subprocess.TimeoutExpired("ffmpeg", timeout or 0)
        self.returncode = self.code
        return self.code

    def kill(self) -> None:
        self.killed = True


class Factory:
    def __init__(self, process: FakeProcess | None = None) -> None:
        self.process = process or FakeProcess()

    def __call__(self, args: list[str], **kwargs: Any) -> FakeProcess:
        self.process.args = args
        self.process.kwargs = kwargs
        return self.process


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def frame(value: int = 7, w: int = W, h: int = H) -> np.ndarray[Any, Any]:
    return np.full((h, w, 3), value, dtype=np.uint8)


def make(
    tmp_path: Path,
    factory: Factory | None = None,
    clock: Clock | None = None,
    ffmpeg: str | None = "ffmpeg",
    path: Path | None = None,
) -> Recorder:
    return Recorder(
        path or tmp_path / "rec" / "night.mp4",
        W,
        H,
        fps=10,
        ffmpeg=ffmpeg,
        process_factory=factory or Factory(),
        clock=clock or Clock(),
        root=tmp_path,
    )


def test_args_match_build_guide(tmp_path: Path) -> None:
    factory = Factory()
    recorder = make(tmp_path, factory)
    recorder.start()
    recorder.stop()
    args = factory.process.args
    assert args == [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{W}x{H}",
        "-r",
        "10",
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
        str(tmp_path / "rec" / "night.mp4"),
    ]
    assert "-nostdin" not in args
    kwargs = factory.process.kwargs
    assert kwargs["stdin"] == subprocess.PIPE
    assert kwargs["stdout"] == subprocess.DEVNULL
    assert kwargs["stderr"] == subprocess.DEVNULL


def test_start_without_ffmpeg_raises(tmp_path: Path) -> None:
    recorder = make(tmp_path, ffmpeg=None)
    with pytest.raises(RecorderError):
        recorder.start()
    assert not recorder.is_recording
    assert recorder.write(frame()) is False


def test_path_outside_root_refused(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    recorder = Recorder(
        tmp_path / "elsewhere" / "x.mp4",
        W,
        H,
        ffmpeg="ffmpeg",
        process_factory=Factory(),
        root=root,
    )
    with pytest.raises(RecorderError):
        recorder.start()
    traversal = Recorder(
        root / ".." / "x.mp4",
        W,
        H,
        ffmpeg="ffmpeg",
        process_factory=Factory(),
        root=root,
    )
    with pytest.raises(RecorderError):
        traversal.start()


def test_process_failing_to_start_raises(tmp_path: Path) -> None:
    def boom(args: list[str], **kwargs: Any) -> FakeProcess:
        raise FileNotFoundError

    recorder = Recorder(
        tmp_path / "a.mp4",
        W,
        H,
        ffmpeg="ffmpeg",
        process_factory=boom,
        root=tmp_path,
    )
    with pytest.raises(RecorderError):
        recorder.start()


def test_frames_paced_to_fps_with_fake_clock(tmp_path: Path) -> None:
    clock = Clock()
    factory = Factory()
    recorder = make(tmp_path, factory, clock)
    recorder.start()
    assert recorder.is_recording
    assert recorder.write(frame(1)) is True
    clock.now = 1.0
    result = recorder.stop()
    assert result.ok is True
    assert result.frames_written == 10
    assert result.seconds == pytest.approx(1.0)
    chunks = factory.process.fake_stdin.chunks
    assert len(chunks) == 10
    assert all(len(chunk) == W * H * 3 for chunk in chunks)
    assert chunks[0] == frame(1).tobytes()
    assert factory.process.fake_stdin.closed is True


def test_slow_source_duplicates_and_fast_source_skips(tmp_path: Path) -> None:
    clock = Clock()
    factory = Factory()
    recorder = make(tmp_path, factory, clock)
    recorder.start()
    for value in (1, 2, 3):
        assert recorder.write(frame(value))
    deadline = time.monotonic() + 2
    while not recorder._queue.empty() and time.monotonic() < deadline:
        time.sleep(0.005)
    clock.now = 0.5
    result = recorder.stop()
    chunks = factory.process.fake_stdin.chunks
    assert result.frames_written == 5
    assert chunks[-1] == frame(3).tobytes()
    assert frame(1).tobytes() not in chunks


def test_queue_full_drops_and_counts(tmp_path: Path) -> None:
    clock = Clock()
    factory = Factory()
    gate = threading.Event()
    factory.process.fake_stdin.gate = gate
    recorder = make(tmp_path, factory, clock)
    recorder.start()
    recorder.write(frame(1))
    clock.now = 0.5
    deadline = time.monotonic() + 2
    while recorder._queue.qsize() > 0 and time.monotonic() < deadline:
        time.sleep(0.005)
    time.sleep(0.05)
    accepted = [recorder.write(frame(2)) for _ in range(40)]
    assert not all(accepted)
    assert recorder.frames_dropped == accepted.count(False)
    assert recorder.frames_dropped > 0
    gate.set()
    result = recorder.stop()
    assert result.frames_dropped == recorder.frames_dropped


def test_wrong_shape_frames(tmp_path: Path) -> None:
    clock = Clock()
    factory = Factory()
    recorder = make(tmp_path, factory, clock)
    recorder.start()
    assert recorder.write(np.zeros((H, W), dtype=np.uint8)) is False
    assert recorder.write(np.zeros((H, W, 4), dtype=np.uint8)) is False
    assert recorder.write(np.zeros((H, W, 3), dtype=np.float32)) is False
    assert recorder.write(frame(9, w=W * 2, h=H * 2)) is True
    clock.now = 0.1
    result = recorder.stop()
    chunks = factory.process.fake_stdin.chunks
    assert result.frames_written == 1
    assert len(chunks[0]) == W * H * 3
    assert chunks[0] == frame(9).tobytes()


def test_broken_pipe_ends_cleanly(tmp_path: Path, caplog: Any) -> None:
    clock = Clock()
    factory = Factory()
    factory.process.fake_stdin.fail = BrokenPipeError
    recorder = make(tmp_path, factory, clock)
    recorder.start()
    recorder.write(frame())
    clock.now = 1.0
    deadline = time.monotonic() + 2
    while recorder.is_recording and time.monotonic() < deadline:
        time.sleep(0.005)
    assert recorder.is_recording is False
    assert recorder.write(frame()) is False
    with caplog.at_level("WARNING"):
        result = recorder.stop()
    assert result.ok is False
    assert result.frames_written == 0
    assert "BrokenPipeError" in caplog.text


def test_oserror_ends_cleanly(tmp_path: Path) -> None:
    clock = Clock()
    factory = Factory()
    factory.process.fake_stdin.fail = OSError
    recorder = make(tmp_path, factory, clock)
    recorder.start()
    recorder.write(frame())
    clock.now = 1.0
    result = recorder.stop()
    assert result.ok is False


def test_stop_kills_after_timeout(tmp_path: Path) -> None:
    factory = Factory(FakeProcess(hang=True))
    recorder = make(tmp_path, factory)
    recorder.start()
    result = recorder.stop()
    assert factory.process.killed is True
    assert result.ok is False


def test_nonzero_exit_is_not_ok(tmp_path: Path) -> None:
    factory = Factory(FakeProcess(code=1))
    recorder = make(tmp_path, factory)
    recorder.start()
    assert recorder.stop().ok is False


def test_stop_is_idempotent(tmp_path: Path) -> None:
    clock = Clock()
    recorder = make(tmp_path, Factory(), clock)
    recorder.start()
    recorder.write(frame())
    clock.now = 0.3
    first = recorder.stop()
    clock.now = 9.0
    second = recorder.stop()
    assert first is second
    assert first.path == tmp_path / "rec" / "night.mp4"


def test_stop_without_start(tmp_path: Path) -> None:
    result = make(tmp_path).stop()
    assert result.ok is False
    assert result.frames_written == 0


def test_find_ffmpeg_env_wins(tmp_path: Path) -> None:
    exe = tmp_path / "ffmpeg.exe"
    exe.write_bytes(b"")
    found = find_ffmpeg(lambda name: "C:/path/ffmpeg", {"DESKTOP_FFMPEG": str(exe)})
    assert found == str(exe)


def test_find_ffmpeg_env_missing_file_falls_back(tmp_path: Path) -> None:
    missing = tmp_path / "nope.exe"
    found = find_ffmpeg(lambda name: "C:/path/ffmpeg", {"DESKTOP_FFMPEG": str(missing)})
    assert found == "C:/path/ffmpeg"


def test_find_ffmpeg_which_and_none() -> None:
    assert find_ffmpeg(lambda name: "/usr/bin/ffmpeg", {}) == "/usr/bin/ffmpeg"
    assert find_ffmpeg(lambda name: None, {}) is None
    assert find_ffmpeg(lambda name: None) is None

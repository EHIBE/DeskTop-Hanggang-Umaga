import io
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from replay.highlights import Highlight, RecordingMeta, ReelEvent, ReplayError
from replay.proxy import Segment
from replay.render import (
    MAX_REEL_S,
    OUTPUT_FPS,
    OUTPUT_SIZE,
    TITLE_S,
    FfmpegFrameSource,
    build_title_card,
    build_writer_args,
    interpolate_box,
    render_reel,
)
from vision.sam import Image, TrackBox
from vision.sprites import encode_png

SIZE = (240, 160)
FRAME_BYTES = SIZE[0] * SIZE[1] * 3
TITLE_FRAMES = round(TITLE_S * OUTPUT_FPS)


class FakeStdin:
    def __init__(self, fail_after: int | None = None) -> None:
        self.chunks: list[bytes] = []
        self.fail_after = fail_after
        self.closed = False

    def write(self, data: bytes, /) -> int:
        if self.fail_after is not None and len(self.chunks) >= self.fail_after:
            raise BrokenPipeError
        self.chunks.append(data)
        return len(data)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class FakeWriter:
    def __init__(self, code: int = 0, fail_after: int | None = None) -> None:
        self.stdin: FakeStdin | None = FakeStdin(fail_after)
        self.returncode: int | None = None
        self.code = code
        self.killed = False

    def wait(self, timeout: float | None = None) -> int:
        self.returncode = self.code
        return self.code

    def kill(self) -> None:
        self.killed = True


class Factory:
    def __init__(self, process: Any) -> None:
        self.process = process
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, args: list[str], **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        return self.process


class FakeSource:
    def __init__(self, gray: dict[float, int] | int = 100, limit: int | None = None):
        self.gray = gray
        self.limit = limit
        self.calls: list[tuple[float, float]] = []

    def read(self, start_s: float, duration_s: float) -> Iterator[Image]:
        self.calls.append((start_s, duration_s))
        value = self.gray if isinstance(self.gray, int) else self.gray[start_s]
        total = round(duration_s * 30) + 2
        if self.limit is not None:
            total = self.limit
        for _ in range(total):
            yield np.full((80, 120, 3), value, dtype=np.uint8)


def make_meta(tmp_path: Path) -> RecordingMeta:
    return RecordingMeta(
        video_path=tmp_path / "night.mp4",
        width=120,
        height=80,
        fps=30,
        started_t_ms=0,
        duration_s=100.0,
        anchors=(),
        sprites={},
    )


def make_segment(
    start_s: float = 0.0,
    duration_s: float = 1.0,
    events: tuple[ReelEvent, ...] = (),
    first_frame: int = 0,
) -> Segment:
    highlight = Highlight("kubo_hit", 1, start_s, duration_s, events)
    return Segment(highlight, first_frame, round(duration_s * 10))


def make_sprite() -> bytes:
    rgba = np.zeros((8, 8, 4), dtype=np.uint8)
    rgba[:, 4:] = (255, 0, 0, 255)
    return encode_png(rgba)


def still_track(frames: range, box: tuple[int, int, int, int]) -> list[TrackBox]:
    return [TrackBox(f, *box) for f in frames]


def run(
    tmp_path: Path,
    segments: list[Segment],
    tracks: dict[str, list[TrackBox]] | None = None,
    sprites: dict[str, bytes] | None = None,
    source: Any = None,
    process: Any = None,
) -> tuple[Any, FakeWriter, Factory, FakeSource]:
    writer = process or FakeWriter()
    factory = Factory(writer)
    src = source or FakeSource()
    result = render_reel(
        make_meta(tmp_path),
        segments,
        tracks or {},
        sprites or {},
        tmp_path / "reels" / "out.mp4",
        tmp_path,
        "ffmpeg",
        "SUMIKAT NA",
        "SUNRISE",
        3,
        frame_source=src,
        process_factory=factory,
        output_size=SIZE,
    )
    return result, writer, factory, src


def frames_of(writer: FakeWriter) -> list[Image]:
    assert writer.stdin is not None
    blob = b"".join(writer.stdin.chunks)
    count = len(blob) // FRAME_BYTES
    return [
        np.frombuffer(
            blob, dtype=np.uint8, count=FRAME_BYTES, offset=i * FRAME_BYTES
        ).reshape(SIZE[1], SIZE[0], 3)
        for i in range(count)
    ]


def test_title_card_only(tmp_path: Path) -> None:
    result, writer, _, _ = run(tmp_path, [])
    assert result.frames == TITLE_FRAMES
    assert result.seconds == pytest.approx(TITLE_S)
    frames = frames_of(writer)
    assert len(frames) == TITLE_FRAMES
    assert frames[0].shape == (SIZE[1], SIZE[0], 3)
    assert writer.stdin is not None and writer.stdin.closed


def test_title_card_gradient_and_default_size() -> None:
    card = build_title_card(SIZE, "SUMIKAT NA", "SUNRISE", 2)
    assert card.shape == (SIZE[1], SIZE[0], 3)
    top = card[0, 0].astype(int)
    bottom = card[-1, 0].astype(int)
    assert tuple(top) == (0x38, 0x22, 0x1B)
    assert bottom[2] > bottom[0]
    assert OUTPUT_SIZE == (1920, 1080)


def test_title_card_draws_text() -> None:
    plain = build_title_card(SIZE, "", "", 0)
    card = build_title_card(SIZE, "SUMIKAT NA", "SUNRISE", 2)
    assert np.any(plain != card)


def test_interpolate_box_between_frames() -> None:
    track = [TrackBox(0, 0, 0, 10, 10), TrackBox(2, 20, 40, 30, 50)]
    assert interpolate_box(track, 1.0) == (10, 20, 20, 30)
    assert interpolate_box(track, 0.0) == (0, 0, 10, 10)
    assert interpolate_box(track, 2.0) == (20, 40, 30, 50)
    assert interpolate_box(track, 0.5) == (5, 10, 15, 20)


def test_interpolate_box_outside_and_gaps() -> None:
    track = [TrackBox(2, 0, 0, 10, 10), TrackBox(4, 0, 0, 10, 10)]
    assert interpolate_box(track, 1.9) is None
    assert interpolate_box(track, 4.1) is None
    assert interpolate_box([], 0.0) is None
    gapped = [TrackBox(0, 0, 0, 10, 10), TrackBox(9, 0, 0, 10, 10)]
    assert interpolate_box(gapped, 4.0) is None
    assert interpolate_box(gapped, 9.0) == (0, 0, 10, 10)


def test_sprite_pinned_to_box_with_alpha(tmp_path: Path) -> None:
    tracks = {"a": still_track(range(10), (20, 20, 60, 60))}
    result, writer, _, _ = run(tmp_path, [make_segment()], tracks, {"a": make_sprite()})
    frame = frames_of(writer)[TITLE_FRAMES + 5]
    assert tuple(frame[80, 110]) == (0, 0, 255)
    assert tuple(frame[80, 50]) == (100, 100, 100)
    assert tuple(frame[20, 20]) == (100, 100, 100)
    assert tuple(frame[140, 200]) == (100, 100, 100)
    assert result.sprite_hit_frames == result.sprite_total_frames == 28


def test_sprite_follows_interpolated_box(tmp_path: Path) -> None:
    track = [TrackBox(0, 0, 0, 40, 40), TrackBox(3, 60, 0, 100, 40)]
    segment = Segment(Highlight("push", 1, 0.0, 0.4, ()), 0, 4)
    _, writer, _, _ = run(tmp_path, [segment], {"a": track}, {"a": make_sprite()})
    frames = frames_of(writer)
    first = frames[TITLE_FRAMES]
    later = frames[TITLE_FRAMES + 8]
    assert tuple(first[40, 60]) == (0, 0, 255)
    assert tuple(later[40, 60]) == (100, 100, 100)
    assert tuple(later[40, 170]) == (0, 0, 255)


def damage_diff(tmp_path: Path, events: tuple[ReelEvent, ...]) -> list[int]:
    tracks = {"a": still_track(range(20), (20, 20, 100, 60))}
    sprites = {"a": make_sprite()}
    segment = make_segment(duration_s=2.0, first_frame=0)
    _, plain, _, _ = run(tmp_path, [make_segment(duration_s=2.0)], tracks, sprites)
    _, hit, _, _ = run(
        tmp_path, [make_segment(duration_s=2.0, events=events)], tracks, sprites
    )
    assert segment.frame_count == 20
    base = frames_of(plain)
    marked = frames_of(hit)
    return [
        i - TITLE_FRAMES
        for i in range(TITLE_FRAMES, len(base))
        if np.any(base[i] != marked[i])
    ]


def test_damage_number_window(tmp_path: Path) -> None:
    event = ReelEvent(0.5, "attack", "x", "a", 7)
    changed = damage_diff(tmp_path, (event,))
    assert changed
    assert min(changed) == 15
    assert max(changed) == 44


def test_kubo_hit_number_and_ignored_events(tmp_path: Path) -> None:
    assert damage_diff(tmp_path, (ReelEvent(1.0, "kubo_hit", "x", "a", 3),))
    ignored = (
        ReelEvent(0.5, "move", "x", "a", 7),
        ReelEvent(0.5, "attack", "x", "a", None),
        ReelEvent(0.5, "attack", "x", "ghost", 4),
        ReelEvent(0.5, "attack", "x", None, 4),
    )
    assert damage_diff(tmp_path, ignored) == []


def test_reel_capped_at_sixty_seconds(tmp_path: Path) -> None:
    segments = [make_segment(start_s=s, duration_s=30.0) for s in (0.0, 40.0, 80.0)]
    result, writer, _, source = run(tmp_path, segments)
    assert result.frames == int(MAX_REEL_S * OUTPUT_FPS)
    assert result.seconds == pytest.approx(MAX_REEL_S)
    assert len(frames_of(writer)) == 1800
    assert len(source.calls) == 2
    assert source.calls[1][1] == pytest.approx(27.0)


def test_crossfade_between_segments(tmp_path: Path) -> None:
    source = FakeSource({0.0: 40, 5.0: 200})
    segments = [make_segment(0.0, 1.0), make_segment(5.0, 1.0)]
    _, writer, _, _ = run(tmp_path, segments, source=source)
    frames = frames_of(writer)
    base = TITLE_FRAMES + 30
    assert int(frames[base - 1][0, 0, 0]) == 40
    ramp = [int(frames[base + k][0, 0, 0]) for k in range(9)]
    assert all(40 < v < 200 for v in ramp)
    assert ramp == sorted(ramp)
    assert int(frames[base + 9][0, 0, 0]) == 200


def test_source_shorter_than_segment_holds_last_frame(tmp_path: Path) -> None:
    result, _, _, _ = run(tmp_path, [make_segment()], source=FakeSource(limit=5))
    assert result.frames == TITLE_FRAMES + 30


def test_empty_source_stops_segment(tmp_path: Path) -> None:
    result, _, _, _ = run(tmp_path, [make_segment()], source=FakeSource(limit=0))
    assert result.frames == TITLE_FRAMES


def test_writer_args_and_popen_kwargs(tmp_path: Path) -> None:
    _, _, factory, _ = run(tmp_path, [])
    args, kwargs = factory.calls[0]
    assert args == build_writer_args("ffmpeg", tmp_path / "reels" / "out.mp4", SIZE)
    assert isinstance(args, list)
    assert args[0] == "ffmpeg"
    assert "-s" in args and args[args.index("-s") + 1] == "240x160"
    assert args[args.index("-r") + 1] == "30"
    assert args[args.index("-i") + 1] == "-"
    assert args[args.index("-crf") + 1] == "20"
    assert args[-3:-1] == ["-movflags", "+faststart"]
    assert args[-1].endswith("out.mp4")
    assert kwargs["stdin"] == subprocess.PIPE
    assert "shell" not in kwargs
    assert kwargs["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)


def test_default_writer_args_use_1080p() -> None:
    args = build_writer_args("ffmpeg", Path("out.mp4"))
    assert args[args.index("-s") + 1] == "1920x1080"


def test_ffmpeg_missing(tmp_path: Path) -> None:
    with pytest.raises(ReplayError):
        render_reel(
            make_meta(tmp_path),
            [],
            {},
            {},
            tmp_path / "out.mp4",
            tmp_path,
            None,
            "a",
            "b",
            1,
            frame_source=FakeSource(),
            process_factory=Factory(FakeWriter()),
            output_size=SIZE,
        )


def test_path_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    factory = Factory(FakeWriter())
    with pytest.raises(ReplayError):
        render_reel(
            make_meta(tmp_path),
            [],
            {},
            {},
            tmp_path / "elsewhere" / "out.mp4",
            root,
            "ffmpeg",
            "a",
            "b",
            1,
            frame_source=FakeSource(),
            process_factory=factory,
            output_size=SIZE,
        )
    assert factory.calls == []


def test_writer_broken_pipe(tmp_path: Path) -> None:
    writer = FakeWriter(fail_after=10)
    with pytest.raises(ReplayError):
        run(tmp_path, [make_segment()], process=writer)
    assert writer.killed


def test_writer_nonzero_exit(tmp_path: Path) -> None:
    with pytest.raises(ReplayError):
        run(tmp_path, [], process=FakeWriter(code=1))


def test_writer_cannot_start(tmp_path: Path) -> None:
    def boom(args: list[str], **kwargs: Any) -> Any:
        raise OSError

    with pytest.raises(ReplayError):
        render_reel(
            make_meta(tmp_path),
            [],
            {},
            {},
            tmp_path / "out.mp4",
            tmp_path,
            "ffmpeg",
            "a",
            "b",
            1,
            frame_source=FakeSource(),
            process_factory=boom,
            output_size=SIZE,
        )


def test_sprite_hit_counts_with_gap(tmp_path: Path) -> None:
    track = still_track(range(3), (20, 20, 60, 60)) + still_track(
        range(8, 10), (20, 20, 60, 60)
    )
    segment = make_segment(duration_s=1.0)
    result, _, _, _ = run(tmp_path, [segment], {"a": track}, {"a": make_sprite()})
    assert result.sprite_total_frames == 28
    assert result.sprite_hit_frames == 11


def test_objects_without_sprites_are_not_counted(tmp_path: Path) -> None:
    tracks = {"a": still_track(range(10), (20, 20, 60, 60))}
    result, _, _, _ = run(tmp_path, [make_segment()], tracks, {})
    assert result.sprite_total_frames == 0


class FakeReaderProcess:
    def __init__(self, payload: bytes) -> None:
        self.stdout: io.BytesIO | None = io.BytesIO(payload)
        self.killed = False

    def wait(self, timeout: float | None = None) -> int:
        return 0

    def kill(self) -> None:
        self.killed = True


def test_ffmpeg_frame_source_decodes_frames(tmp_path: Path) -> None:
    frame_a = np.full((4, 6, 3), 9, dtype=np.uint8)
    frame_b = np.full((4, 6, 3), 200, dtype=np.uint8)
    payload = frame_a.tobytes() + frame_b.tobytes() + b"\x01\x02"
    process = FakeReaderProcess(payload)
    factory = Factory(process)
    source = FfmpegFrameSource(tmp_path / "v.mp4", 6, 4, 25, "ffmpeg", factory)
    frames = list(source.read(12.5, 2.0))
    assert len(frames) == 2
    assert frames[0].shape == (4, 6, 3)
    assert int(frames[1][0, 0, 0]) == 200
    args, kwargs = factory.calls[0]
    assert args[args.index("-ss") + 1] == "12.500"
    assert args[args.index("-t") + 1] == "2.000"
    assert args[args.index("-pix_fmt") + 1] == "bgr24"
    assert args[-1] == "-"
    assert args[args.index("-f") + 1] == "rawvideo"
    assert "shell" not in kwargs
    assert process.killed


def test_ffmpeg_frame_source_missing_ffmpeg(tmp_path: Path) -> None:
    source = FfmpegFrameSource(tmp_path / "v.mp4", 6, 4, 25, None)
    with pytest.raises(ReplayError):
        list(source.read(0.0, 1.0))

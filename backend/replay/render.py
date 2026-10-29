import asyncio
import bisect
import logging
import shutil
import subprocess
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final, Protocol

import cv2
import numpy as np
from PIL import Image as PilImage
from PIL import ImageDraw, ImageFont

from capture.recorder import ProcessFactory, ProcessLike
from meta_client import MetaClient, MetaError
from replay.highlights import (
    RecordingMeta,
    ReplayError,
    TurnLogRow,
    load_recording_meta,
    pick_highlights,
)
from replay.proxy import (
    PROXY_FPS,
    Segment,
    TrackerFactory,
    build_proxy,
    inside_root,
    nearest_anchor_boxes,
    track_highlights,
)
from vision.sam import Image, TrackBox
from vision.sprites import SpriteError, decode_png

logger = logging.getLogger("desktop.replay.render")

Color = tuple[int, int, int]
Box = tuple[int, int, int, int]

OUTPUT_SIZE: Final = (1920, 1080)
OUTPUT_FPS: Final = 30
MAX_REEL_S: Final = 60.0
TITLE_S: Final = 3.0
CROSSFADE_S: Final = 0.3
DAMAGE_WINDOW_S: Final = 1.0
MAX_GAP_FRAMES: Final = 3
WRITER_WAIT_S: Final = 120.0
READER_WAIT_S: Final = 5.0

DAMAGE_EVENT_TYPES: Final = frozenset({"attack", "kubo_hit"})

INK: Final[Color] = (0x0B, 0x0E, 0x1A)
NIGHT: Final[Color] = (0x1B, 0x22, 0x38)
MIST: Final[Color] = (0x8F, 0xA3, 0xC7)
EMBER: Final[Color] = (0xE0, 0x7A, 0x2E)
SINDAK: Final[Color] = (0xB3, 0x3A, 0x3A)
UBE: Final[Color] = (0x6B, 0x2D, 0x5C)
LIWAYWAY: Final[Color] = (0xFF, 0xD9, 0xA0)
GRADIENT_STOPS: Final[tuple[Color, ...]] = (NIGHT, UBE, EMBER)

FONT_PATH: Final = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "fonts"
    / "PressStart2P-Regular.ttf"
)
TITLE_PX_AT_1080: Final = 48
SUBTITLE_PX_AT_1080: Final = 24
NIGHT_PX_AT_1080: Final = 24
DAMAGE_PX_AT_1080: Final = 32
DAMAGE_RISE_AT_1080: Final = 60


class ReaderLike(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...


class ReaderProcessLike(Protocol):
    @property
    def stdout(self) -> ReaderLike | None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def kill(self) -> None: ...


ReaderFactory = Any


class FrameSource(Protocol):
    def read(self, start_s: float, duration_s: float) -> Iterator[Image]: ...


@dataclass(frozen=True)
class ReelResult:
    path: Path
    seconds: float
    frames: int
    sprite_hit_frames: int
    sprite_total_frames: int


class FfmpegFrameSource:
    def __init__(
        self,
        video_path: Path,
        width: int,
        height: int,
        fps: int,
        ffmpeg: str | None,
        process_factory: ReaderFactory = subprocess.Popen,
    ) -> None:
        if width <= 0 or height <= 0 or fps <= 0:
            raise ReplayError("invalid recording size or rate")
        self._video = video_path
        self._width = width
        self._height = height
        self._fps = fps
        self._ffmpeg = ffmpeg
        self._factory = process_factory

    def build_args(self, start_s: float, duration_s: float) -> list[str]:
        if self._ffmpeg is None:
            raise ReplayError("ffmpeg was not found")
        return [
            self._ffmpeg,
            "-v",
            "error",
            "-ss",
            f"{max(0.0, start_s):.3f}",
            "-t",
            f"{max(0.0, duration_s):.3f}",
            "-i",
            str(self._video),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-",
        ]

    def read(self, start_s: float, duration_s: float) -> Iterator[Image]:
        args = self.build_args(start_s, duration_s)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            process: ReaderProcessLike = self._factory(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
        except (OSError, ValueError) as error:
            raise ReplayError("ffmpeg could not start") from error
        stream = process.stdout
        if stream is None:
            process.kill()
            raise ReplayError("ffmpeg has no output pipe")
        size = self._width * self._height * 3
        try:
            while True:
                data = stream.read(size)
                if len(data) < size:
                    break
                yield (
                    np.frombuffer(data, dtype=np.uint8)
                    .reshape(self._height, self._width, 3)
                    .copy()
                )
        finally:
            process.kill()
            try:
                process.wait(timeout=READER_WAIT_S)
            except subprocess.TimeoutExpired:
                logger.warning("frame reader did not exit")


def interpolate_box(track: Sequence[TrackBox], frame_f: float) -> Box | None:
    if not track:
        return None
    if frame_f < track[0].frame or frame_f > track[-1].frame:
        return None
    upper = bisect.bisect_right(track, frame_f, key=lambda box: box.frame)
    if upper >= len(track):
        last = track[-1]
        return (last.left, last.top, last.right, last.bottom)
    after = track[upper]
    before = track[upper - 1]
    if before.frame == frame_f or after.frame == before.frame:
        return (before.left, before.top, before.right, before.bottom)
    if after.frame - before.frame > MAX_GAP_FRAMES:
        return None
    weight = (frame_f - before.frame) / (after.frame - before.frame)

    def mix(a: int, b: int) -> int:
        return round(a + (b - a) * weight)

    return (
        mix(before.left, after.left),
        mix(before.top, after.top),
        mix(before.right, after.right),
        mix(before.bottom, after.bottom),
    )


@lru_cache(maxsize=16)
def _font(px: int) -> ImageFont.FreeTypeFont | None:
    try:
        return ImageFont.truetype(str(FONT_PATH), px)
    except OSError:
        return None


def _text_mask(text: str, px: int) -> Image:
    font = _font(px)
    if font is not None:
        right, bottom = font.getbbox(text)[2:]
        canvas = PilImage.new("L", (round(right) + 2, round(bottom) + 2), 0)
        ImageDraw.Draw(canvas).text((0, 0), text, fill=255, font=font)
        return np.ascontiguousarray(np.asarray(canvas), dtype=np.uint8)
    scale = px / 22.0
    thickness = max(1, px // 12)
    (width, height), baseline = cv2.getTextSize(
        text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness
    )
    mask = np.zeros((height + baseline + 2, width + 2), dtype=np.uint8)
    cv2.putText(
        mask,
        text,
        (1, height + 1),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        255,
        thickness,
    )
    return mask


def _bgr(color: Color) -> Color:
    return (color[2], color[1], color[0])


def _blit_mask(frame: Image, mask: Image, cx: int, cy: int, color: Color) -> None:
    mask_h, mask_w = mask.shape[:2]
    left = cx - mask_w // 2
    top = cy - mask_h // 2
    x0 = max(0, left)
    y0 = max(0, top)
    x1 = min(frame.shape[1], left + mask_w)
    y1 = min(frame.shape[0], top + mask_h)
    if x1 <= x0 or y1 <= y0:
        return
    alpha = mask[y0 - top : y1 - top, x0 - left : x1 - left].astype(np.float32)
    alpha = alpha[:, :, None] / 255.0
    region = frame[y0:y1, x0:x1].astype(np.float32)
    ink = np.array(color, dtype=np.float32)
    frame[y0:y1, x0:x1] = (region * (1.0 - alpha) + ink * alpha).astype(np.uint8)


def _draw_text(
    frame: Image, text: str, cx: int, cy: int, px: int, color: Color
) -> None:
    mask = _text_mask(text, px)
    shadow = max(1, px // 8)
    _blit_mask(frame, mask, cx + shadow, cy + shadow, _bgr(INK))
    _blit_mask(frame, mask, cx, cy, _bgr(color))


def _scaled_px(base: int, height: int) -> int:
    return max(8, round(base * height / 1080))


def build_title_card(
    size: tuple[int, int], title_tl: str, title_en: str, night_number: int
) -> Image:
    width, height = size
    stops = np.array([_bgr(stop) for stop in GRADIENT_STOPS], dtype=np.float32)
    ys = np.linspace(0.0, len(stops) - 1.0, height, dtype=np.float32)
    low = np.floor(ys).astype(np.intp)
    high = np.minimum(low + 1, len(stops) - 1)
    frac = (ys - low)[:, None]
    column = stops[low] * (1.0 - frac) + stops[high] * frac
    card = np.repeat(column[:, None, :], width, axis=1).astype(np.uint8)
    card = np.ascontiguousarray(card)
    cx = width // 2
    _draw_text(
        card,
        title_tl,
        cx,
        round(height * 0.42),
        _scaled_px(TITLE_PX_AT_1080, height),
        LIWAYWAY,
    )
    _draw_text(
        card,
        title_en,
        cx,
        round(height * 0.55),
        _scaled_px(SUBTITLE_PX_AT_1080, height),
        MIST,
    )
    _draw_text(
        card,
        f"#{night_number}",
        cx,
        round(height * 0.68),
        _scaled_px(NIGHT_PX_AT_1080, height),
        LIWAYWAY,
    )
    return card


def _letterbox(frame: Image, size: tuple[int, int]) -> tuple[Image, float, int, int]:
    out_w, out_h = size
    src_h, src_w = frame.shape[:2]
    scale = min(out_w / src_w, out_h / src_h)
    new_w = max(1, round(src_w * scale))
    new_h = max(1, round(src_h * scale))
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
    canvas = np.empty((out_h, out_w, 3), dtype=np.uint8)
    canvas[:, :] = _bgr(INK)
    off_x = (out_w - new_w) // 2
    off_y = (out_h - new_h) // 2
    canvas[off_y : off_y + new_h, off_x : off_x + new_w] = resized
    return canvas, scale, off_x, off_y


def _paste_sprite(frame: Image, sprite_bgra: Image, box: Box) -> None:
    left, top, right, bottom = box
    box_w = max(1, right - left)
    box_h = max(1, bottom - top)
    sprite_h, sprite_w = sprite_bgra.shape[:2]
    fit = min(box_w / sprite_w, box_h / sprite_h)
    new_w = max(1, round(sprite_w * fit))
    new_h = max(1, round(sprite_h * fit))
    resized = cv2.resize(sprite_bgra, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
    px = (left + right) // 2 - new_w // 2
    py = (top + bottom) // 2 - new_h // 2
    x0 = max(0, px)
    y0 = max(0, py)
    x1 = min(frame.shape[1], px + new_w)
    y1 = min(frame.shape[0], py + new_h)
    if x1 <= x0 or y1 <= y0:
        return
    part = resized[y0 - py : y1 - py, x0 - px : x1 - px]
    alpha = part[:, :, 3:4].astype(np.float32) / 255.0
    region = frame[y0:y1, x0:x1].astype(np.float32)
    mixed = region * (1.0 - alpha) + part[:, :, :3].astype(np.float32) * alpha
    frame[y0:y1, x0:x1] = mixed.astype(np.uint8)


def _decode_sprites(sprites: Mapping[str, bytes]) -> dict[str, Image]:
    decoded: dict[str, Image] = {}
    for key, data in sprites.items():
        try:
            rgba = decode_png(data)
        except SpriteError:
            logger.warning("sprite %s could not be decoded", key)
            continue
        decoded[key] = np.ascontiguousarray(
            cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA), dtype=np.uint8
        )
    return decoded


def _close(iterator: object) -> None:
    closer = getattr(iterator, "close", None)
    if callable(closer):
        closer()


def _resample(frames: Iterator[Image], count: int, src_fps: int) -> Iterator[Image]:
    current: Image | None = None
    consumed = -1
    for k in range(count):
        need = int(k * src_fps / OUTPUT_FPS)
        while consumed < need:
            nxt = next(frames, None)
            if nxt is None:
                break
            current = nxt
            consumed += 1
        if current is None:
            return
        yield current


class _Stats:
    def __init__(self) -> None:
        self.hit = 0
        self.total = 0


def _compose(
    source_frame: Image,
    meta: RecordingMeta,
    segment: Segment,
    k: int,
    tracks: Mapping[str, Sequence[TrackBox]],
    sprites: Mapping[str, Image],
    size: tuple[int, int],
    stats: _Stats,
) -> Image:
    canvas, scale, off_x, off_y = _letterbox(source_frame, size)
    box_scale = scale * source_frame.shape[1] / meta.width
    t_rel = k / OUTPUT_FPS
    proxy_f = segment.first_frame + t_rel * PROXY_FPS
    last_frame = segment.first_frame + segment.frame_count - 1
    boxes: dict[str, Box] = {}
    for key, track in tracks.items():
        sprite = sprites.get(key)
        if sprite is None or not track:
            continue
        if not (
            segment.first_frame <= proxy_f <= last_frame
            and track[0].frame <= proxy_f <= track[-1].frame
        ):
            continue
        stats.total += 1
        raw = interpolate_box(track, proxy_f)
        if raw is None:
            continue
        stats.hit += 1
        box = (
            round(raw[0] * box_scale + off_x),
            round(raw[1] * box_scale + off_y),
            round(raw[2] * box_scale + off_x),
            round(raw[3] * box_scale + off_y),
        )
        boxes[key] = box
        _paste_sprite(canvas, sprite, box)
    start_s = segment.highlight.start_s
    px = _scaled_px(DAMAGE_PX_AT_1080, size[1])
    rise = DAMAGE_RISE_AT_1080 * size[1] / 1080
    for event in segment.highlight.events:
        if event.type not in DAMAGE_EVENT_TYPES or event.dmg is None:
            continue
        age = t_rel - (event.t_s - start_s)
        if age < 0.0 or age >= DAMAGE_WINDOW_S:
            continue
        target = boxes.get(event.dst) if event.dst is not None else None
        if target is None:
            continue
        cx = (target[0] + target[2]) // 2
        cy = target[1] - round(rise * age / DAMAGE_WINDOW_S)
        color = SINDAK if event.type == "kubo_hit" else EMBER
        _draw_text(canvas, f"-{event.dmg}", cx, cy, px, color)
    return canvas


class _Writer:
    def __init__(
        self, args: list[str], factory: ProcessFactory, size: tuple[int, int]
    ) -> None:
        self._size = size
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            process = factory(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
        except (OSError, ValueError) as error:
            raise ReplayError("ffmpeg could not start") from error
        if process.stdin is None:
            process.kill()
            raise ReplayError("ffmpeg has no input pipe")
        self._process: ProcessLike = process
        self.frames = 0

    def write(self, frame: Image) -> None:
        stdin = self._process.stdin
        if stdin is None:
            raise ReplayError("ffmpeg has no input pipe")
        if frame.shape != (self._size[1], self._size[0], 3):
            raise ReplayError("frame size does not match the output size")
        try:
            stdin.write(np.ascontiguousarray(frame).tobytes())
        except (BrokenPipeError, OSError) as error:
            self._process.kill()
            raise ReplayError("ffmpeg stopped accepting frames") from error
        self.frames += 1

    def abort(self) -> None:
        stdin = self._process.stdin
        if stdin is not None:
            try:
                stdin.close()
            except OSError:
                pass
        self._process.kill()

    def finish(self) -> None:
        stdin = self._process.stdin
        if stdin is not None:
            try:
                stdin.flush()
                stdin.close()
            except (BrokenPipeError, OSError) as error:
                self._process.kill()
                raise ReplayError("ffmpeg closed early") from error
        try:
            code = self._process.wait(timeout=WRITER_WAIT_S)
        except subprocess.TimeoutExpired as error:
            self._process.kill()
            raise ReplayError("ffmpeg did not finish") from error
        if code != 0:
            raise ReplayError("ffmpeg failed to encode the reel")


def build_writer_args(
    ffmpeg: str, out_path: Path, size: tuple[int, int] = OUTPUT_SIZE
) -> list[str]:
    return [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{size[0]}x{size[1]}",
        "-r",
        str(OUTPUT_FPS),
        "-i",
        "-",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(out_path),
    ]


def _check_path(out_path: Path, root: Path) -> Path:
    try:
        resolved_root = root.resolve()
        target = out_path.resolve()
    except OSError as error:
        raise ReplayError("reel path is invalid") from error
    if target.parent == resolved_root or not target.parent.is_relative_to(
        resolved_root
    ):
        raise ReplayError("reel path is outside the data root")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ReplayError("reel folder could not be created") from error
    return target


def render_reel(
    meta: RecordingMeta,
    segments: Sequence[Segment],
    tracks: Mapping[str, Sequence[TrackBox]],
    sprites: Mapping[str, bytes],
    out_path: Path,
    root: Path,
    ffmpeg: str | None,
    title_tl: str,
    title_en: str,
    night_number: int,
    frame_source: FrameSource | None = None,
    process_factory: ProcessFactory = subprocess.Popen,
    output_size: tuple[int, int] = OUTPUT_SIZE,
) -> ReelResult:
    if ffmpeg is None:
        raise ReplayError("ffmpeg was not found")
    target = _check_path(out_path, root)
    video = inside_root(meta.video_path, root)
    source: FrameSource = frame_source or FfmpegFrameSource(
        video, meta.width, meta.height, meta.fps, ffmpeg
    )
    decoded = _decode_sprites(sprites)
    max_frames = int(MAX_REEL_S * OUTPUT_FPS)
    crossfade_frames = round(CROSSFADE_S * OUTPUT_FPS)
    stats = _Stats()
    writer = _Writer(
        build_writer_args(ffmpeg, target, output_size), process_factory, output_size
    )
    try:
        card = build_title_card(output_size, title_tl, title_en, night_number)
        for _ in range(min(round(TITLE_S * OUTPUT_FPS), max_frames)):
            writer.write(card)
        previous: Image | None = None
        for segment in segments:
            remaining = max_frames - writer.frames
            if remaining <= 0:
                break
            count = min(round(segment.highlight.duration_s * OUTPUT_FPS), remaining)
            if count <= 0:
                continue
            window = source.read(segment.highlight.start_s, count / OUTPUT_FPS)
            fade_from = previous
            try:
                for k, raw in enumerate(_resample(window, count, meta.fps)):
                    frame = _compose(
                        raw, meta, segment, k, tracks, decoded, output_size, stats
                    )
                    if fade_from is not None and k < crossfade_frames:
                        mix = (k + 1) / (crossfade_frames + 1)
                        frame = np.asarray(
                            cv2.addWeighted(fade_from, 1.0 - mix, frame, mix, 0.0),
                            dtype=np.uint8,
                        )
                    writer.write(frame)
                    previous = frame
            finally:
                _close(window)
        writer.finish()
    except BaseException:
        writer.abort()
        raise
    return ReelResult(
        path=out_path,
        seconds=writer.frames / OUTPUT_FPS,
        frames=writer.frames,
        sprite_hit_frames=stats.hit,
        sprite_total_frames=stats.total,
    )


@dataclass(frozen=True)
class ReelRequest:
    sidecar: Path
    rows: tuple[TurnLogRow, ...]
    sprites: Mapping[str, bytes]
    out_path: Path
    work_dir: Path
    root: Path
    ffmpeg: str | None
    title_tl: str
    title_en: str
    night_number: int


def anchor_tracks(
    meta: RecordingMeta, segments: Sequence[Segment]
) -> dict[str, tuple[TrackBox, ...]]:
    tracks: dict[str, list[TrackBox]] = {}
    if not meta.anchors:
        return {}
    for segment in segments:
        last = segment.first_frame + max(0, segment.frame_count - 1)
        for game_id, box in nearest_anchor_boxes(
            meta, segment.highlight.start_s
        ).items():
            left, top, right, bottom = box
            tracks.setdefault(game_id, []).extend(
                [
                    TrackBox(segment.first_frame, left, top, right, bottom),
                    TrackBox(last, left, top, right, bottom),
                ]
            )
    return {game_id: tuple(boxes) for game_id, boxes in tracks.items()}


async def make_reel(
    request: ReelRequest,
    client: MetaClient | None,
    tracker_factory: TrackerFactory | None,
) -> ReelResult:
    meta = load_recording_meta(request.sidecar)
    highlights = pick_highlights(request.rows, meta)
    if not highlights:
        raise ReplayError("the night has no highlights")
    try:
        proxy_path, segments = await asyncio.to_thread(
            build_proxy,
            meta,
            highlights,
            request.work_dir,
            request.root,
            request.ffmpeg,
        )
        tracks = anchor_tracks(meta, segments)
        if client is not None and tracker_factory is not None:
            try:
                tracks = await track_highlights(
                    client, tracker_factory, meta, proxy_path, segments
                )
            except (MetaError, ReplayError) as error:
                logger.warning(
                    "SAM video tracking failed with %s, using anchor boxes",
                    type(error).__name__,
                )
        return await asyncio.to_thread(
            render_reel,
            meta,
            segments,
            tracks,
            request.sprites,
            request.out_path,
            request.root,
            request.ffmpeg,
            request.title_tl,
            request.title_en,
            request.night_number,
        )
    finally:
        shutil.rmtree(request.work_dir, ignore_errors=True)

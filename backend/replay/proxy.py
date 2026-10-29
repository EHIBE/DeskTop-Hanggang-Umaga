import logging
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Protocol

from openai.types.file_create_params import ExpiresAfter

from config import CallKind, MetaModel
from meta_client import CallSpec, MetaClient, MetaError, MetaRequestError, Usage
from replay.highlights import Highlight, RecordingMeta, ReplayError
from vision.sam import RecordingBox, TrackBox

logger = logging.getLogger(__name__)

PROXY_FPS: Final = 10
PROXY_WIDTH: Final = 960
SEGMENT_TIMEOUT_S: Final = 120.0
CONCAT_TIMEOUT_S: Final = 60.0
PROXY_NAME: Final = "proxy.mp4"
LIST_NAME: Final = "list.txt"
UPLOAD_PURPOSE: Final = "user_data"
EXPIRES_AFTER: Final[ExpiresAfter] = {"anchor": "created_at", "seconds": 86400}
MAX_UPLOAD_BYTES: Final = 1024 * 1024 * 1024

UPLOAD_SPEC: Final = CallSpec(
    model=MetaModel.FILES, kind=CallKind.FILES, is_idempotent=False
)
DELETE_SPEC: Final = CallSpec(
    model=MetaModel.FILES, kind=CallKind.FILES, is_idempotent=True
)

ProcessRunner = Callable[..., Any]


@dataclass(frozen=True)
class Segment:
    highlight: Highlight
    first_frame: int
    frame_count: int


class VideoTracker(Protocol):
    async def track(
        self,
        file_id: str,
        segments: Sequence[int],
        prompts: Mapping[int, Mapping[str, RecordingBox]],
        *,
        source_size: tuple[int, int],
        proxy_size: tuple[int, int],
    ) -> dict[str, tuple[TrackBox, ...]]: ...


TrackerFactory = Callable[[MetaClient], VideoTracker]


def proxy_dimensions(meta: RecordingMeta) -> tuple[int, int]:
    height = 2 * round(meta.height * PROXY_WIDTH / meta.width / 2)
    return PROXY_WIDTH, max(2, height)


def inside_root(path: Path, root: Path) -> Path:
    try:
        resolved = path.resolve()
        base = root.resolve()
    except OSError as error:
        raise ReplayError("a replay path is invalid") from error
    if resolved == base or not resolved.is_relative_to(base):
        raise ReplayError("a replay path is outside the data root")
    return resolved


def _segment_args(
    ffmpeg: str, source: Path, target: Path, highlight: Highlight
) -> list[str]:
    return [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-ss",
        f"{highlight.start_s:.3f}",
        "-t",
        f"{highlight.duration_s:.3f}",
        "-i",
        str(source),
        "-vf",
        f"fps={PROXY_FPS},scale={PROXY_WIDTH}:-2",
        "-frames:v",
        str(_frame_count(highlight)),
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(target),
    ]


def _concat_args(ffmpeg: str, list_path: Path, target: Path) -> list[str]:
    return [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-c",
        "copy",
        str(target),
    ]


def _frame_count(highlight: Highlight) -> int:
    return max(1, round(highlight.duration_s * PROXY_FPS))


def _run(runner: ProcessRunner, args: list[str], timeout_s: float, step: str) -> None:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = runner(
            args,
            shell=False,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_s,
            creationflags=flags,
        )
    except subprocess.TimeoutExpired as error:
        raise ReplayError(f"ffmpeg timed out during {step}") from error
    except (OSError, ValueError) as error:
        raise ReplayError(f"ffmpeg could not start for {step}") from error
    if result.returncode != 0:
        raise ReplayError(f"ffmpeg failed during {step}")


def build_proxy(
    meta: RecordingMeta,
    highlights: Sequence[Highlight],
    work_dir: Path,
    root: Path,
    ffmpeg: str | None,
    process_runner: ProcessRunner = subprocess.run,
) -> tuple[Path, tuple[Segment, ...]]:
    if ffmpeg is None:
        raise ReplayError("ffmpeg was not found")
    if not highlights:
        raise ReplayError("there are no highlights to cut")
    source = inside_root(meta.video_path, root)
    work = inside_root(work_dir, root)
    if not source.is_file():
        raise ReplayError("the recording file is missing")
    try:
        work.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ReplayError("the replay folder could not be created") from error
    cuts = [work / f"seg_{index}.mp4" for index in range(len(highlights))]
    list_path = work / LIST_NAME
    target = work / PROXY_NAME
    try:
        for highlight, cut in zip(highlights, cuts, strict=True):
            _run(
                process_runner,
                _segment_args(ffmpeg, source, cut, highlight),
                SEGMENT_TIMEOUT_S,
                "segment cut",
            )
        try:
            list_path.write_text(
                "".join(f"file '{cut.name}'\n" for cut in cuts), encoding="utf-8"
            )
        except OSError as error:
            raise ReplayError("the concat list could not be written") from error
        _run(
            process_runner,
            _concat_args(ffmpeg, list_path, target),
            CONCAT_TIMEOUT_S,
            "concat",
        )
        if not target.is_file():
            raise ReplayError("ffmpeg produced no proxy file")
    finally:
        for leftover in (*cuts, list_path):
            leftover.unlink(missing_ok=True)
    segments: list[Segment] = []
    first_frame = 0
    for highlight in highlights:
        count = _frame_count(highlight)
        segments.append(Segment(highlight, first_frame, count))
        first_frame += count
    return target, tuple(segments)


def _file_id_of(created: object) -> str:
    file_id = getattr(created, "id", None)
    if not isinstance(file_id, str) or not file_id:
        raise ReplayError("the upload response has no file id")
    return file_id


async def upload_proxy(client: MetaClient, path: Path) -> str:
    if path.suffix.lower() != ".mp4" or not path.is_file():
        raise ReplayError("the proxy must be an existing mp4 file")
    if path.stat().st_size > MAX_UPLOAD_BYTES:
        raise ReplayError("the proxy is over the 1 GiB upload limit")

    async def direct() -> object:
        with path.open("rb") as handle:
            return await client.sdk().files.create(
                file=handle, purpose=UPLOAD_PURPOSE, expires_after=EXPIRES_AFTER
            )

    async def extra_body() -> object:
        with path.open("rb") as handle:
            return await client.sdk().files.create(
                file=handle,
                purpose=UPLOAD_PURPOSE,
                extra_body={"expires_after": EXPIRES_AFTER},
            )

    for attempt in (direct, extra_body):
        try:
            created = await client.execute(UPLOAD_SPEC, attempt, lambda _: Usage())
        except MetaRequestError:
            continue
        return _file_id_of(created)
    raise ReplayError("the upload was rejected with an expiry, so nothing was sent")


async def delete_upload(client: MetaClient, file_id: str) -> None:
    async def operation() -> object:
        return await client.sdk().files.delete(file_id)

    await client.execute(DELETE_SPEC, operation, lambda _: Usage())


def nearest_anchor_boxes(
    meta: RecordingMeta, start_s: float
) -> Mapping[str, tuple[int, int, int, int]]:
    best = min(
        meta.anchors, key=lambda snapshot: (abs(snapshot.t_s - start_s), snapshot.t_s)
    )
    return best.boxes


def build_prompts(
    meta: RecordingMeta, segments: Sequence[Segment]
) -> dict[int, dict[str, RecordingBox]]:
    if not meta.anchors:
        raise ReplayError("the recording has no anchor snapshots")
    prompts: dict[int, dict[str, RecordingBox]] = {}
    for segment in segments:
        boxes = nearest_anchor_boxes(meta, segment.highlight.start_s)
        if boxes:
            prompts[segment.first_frame] = dict(boxes)
    if not prompts:
        raise ReplayError("no segment has anchor boxes to track")
    return prompts


async def track_highlights(
    client: MetaClient,
    tracker_factory: TrackerFactory,
    meta: RecordingMeta,
    proxy_path: Path,
    segments: Sequence[Segment],
) -> dict[str, tuple[TrackBox, ...]]:
    prompts = build_prompts(meta, segments)
    file_id = await upload_proxy(client, proxy_path)
    try:
        tracker = tracker_factory(client)
        return await tracker.track(
            file_id,
            [segment.first_frame for segment in segments],
            prompts,
            source_size=(meta.width, meta.height),
            proxy_size=proxy_dimensions(meta),
        )
    finally:
        try:
            await delete_upload(client, file_id)
        except MetaError as error:
            logger.warning(
                "proxy delete failed with %s, expiry will remove it",
                type(error).__name__,
            )

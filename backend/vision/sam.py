import base64
import math
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Final, Protocol, cast

import cv2
import numpy as np
import numpy.typing as npt
from meta_sam_parser import (
    FramePrompt,
    PromptBox,
    PromptObject,
    PromptPoint,
    SegmentationBoxRecord,
    SegmentationMask,
    SegmentationMaskRecord,
    SegmentationRecord,
    SegmentationTextRecord,
    build_object_prompt,
    decode_mask_to_raster,
    image_segmentation_format,
    parse_responses_stream,
    video_segmentation_format,
)

from config import (
    HISTOGRAM_MATCH_MAX,
    REANCHOR_BOX_PADDING,
    RECOVERY_SEARCH_RADIUS_CM,
    SAM_ACCEPT_CONFIDENCE,
    SAM_TRACKER_IOU_ACCEPT,
    CallKind,
    MetaModel,
)
from meta_client import CallSpec, MetaClient, MetaError, Usage

Image = npt.NDArray[np.uint8]
Mask = npt.NDArray[np.bool_]
MaskDecoder = Callable[[SegmentationMask], bytes]

SAM_SPEC: Final = CallSpec(
    model=MetaModel.SAM, kind=CallKind.SAM_IMAGE, is_idempotent=True
)
SAM_METADATA: Final = {"include_confidence": "true", "mask_encoding": "one_bit"}
SAM_JPEG_QUALITY: Final = 90
MIN_SAM_ID: Final = 1
MAX_SAM_ID: Final = 16


class SegmentationError(Exception):
    pass


@dataclass(frozen=True)
class PixelBox:
    left: int
    top: int
    right: int
    bottom: int

    def __post_init__(self) -> None:
        if self.right <= self.left or self.bottom <= self.top:
            raise SegmentationError("box must have positive area")

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def area(self) -> int:
        return self.width * self.height


@dataclass(frozen=True)
class ObjectPrompt:
    sam_id: int
    box: PixelBox
    point: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        if not MIN_SAM_ID <= self.sam_id <= MAX_SAM_ID:
            raise SegmentationError("SAM object ids run from 1 to 16")


@dataclass(frozen=True)
class ObjectMask:
    sam_id: int
    confidence: float | None
    bounds: PixelBox
    mask: Mask = field(compare=False)

    @property
    def pixel_count(self) -> int:
        return int(self.mask.sum())


@dataclass(frozen=True)
class SegmentationResult:
    masks: dict[int, ObjectMask] = field(default_factory=dict)

    def get(self, sam_id: int) -> ObjectMask | None:
        return self.masks.get(sam_id)


class Segmenter(Protocol):
    @property
    def is_available(self) -> bool: ...

    async def segment(
        self, image: Image, prompts: Sequence[ObjectPrompt]
    ) -> SegmentationResult: ...


def clamp_box(box: PixelBox, width: int, height: int) -> PixelBox:
    return PixelBox(
        left=min(max(box.left, 0), width - 1),
        top=min(max(box.top, 0), height - 1),
        right=min(max(box.right, 1), width),
        bottom=min(max(box.bottom, 1), height),
    )


def pad_box(box: PixelBox, ratio: float, width: int, height: int) -> PixelBox:
    pad_x = round(box.width * ratio)
    pad_y = round(box.height * ratio)
    padded = PixelBox(
        box.left - pad_x, box.top - pad_y, box.right + pad_x, box.bottom + pad_y
    )
    return clamp_box(padded, width, height)


def box_iou(first: PixelBox, second: PixelBox) -> float:
    left = max(first.left, second.left)
    top = max(first.top, second.top)
    right = min(first.right, second.right)
    bottom = min(first.bottom, second.bottom)
    if right <= left or bottom <= top:
        return 0.0
    overlap = (right - left) * (bottom - top)
    return overlap / (first.area + second.area - overlap)


def box_overlap_ratio(first: PixelBox, second: PixelBox) -> float:
    left = max(first.left, second.left)
    top = max(first.top, second.top)
    right = min(first.right, second.right)
    bottom = min(first.bottom, second.bottom)
    if right <= left or bottom <= top:
        return 0.0
    return (right - left) * (bottom - top) / min(first.area, second.area)


def mask_in_frame(mask: ObjectMask, width: int, height: int) -> Mask:
    full = np.zeros((height, width), dtype=np.bool_)
    bounds = clamp_box(mask.bounds, width, height)
    local = mask.mask[: bounds.height, : bounds.width]
    full[
        bounds.top : bounds.top + local.shape[0],
        bounds.left : bounds.left + local.shape[1],
    ] = local
    return full


def mask_centroid_px(mask: ObjectMask) -> tuple[float, float]:
    ys, xs = np.nonzero(mask.mask)
    if xs.size == 0:
        return (mask.bounds.left + mask.bounds.right) / 2, (
            mask.bounds.top + mask.bounds.bottom
        ) / 2
    return mask.bounds.left + float(xs.mean()), mask.bounds.top + float(ys.mean())


def mask_hull_px(mask: ObjectMask) -> list[tuple[float, float]]:
    ys, xs = np.nonzero(mask.mask)
    if xs.size < 3:
        box = mask.bounds
        return [
            (float(box.left), float(box.top)),
            (float(box.right), float(box.top)),
            (float(box.right), float(box.bottom)),
            (float(box.left), float(box.bottom)),
        ]
    points = np.stack([xs + mask.bounds.left, ys + mask.bounds.top], axis=1).astype(
        np.int32
    )
    hull = cv2.convexHull(points).reshape(-1, 2)
    return [(float(x), float(y)) for x, y in hull]


def build_prompt_text(prompts: Sequence[ObjectPrompt], width: int, height: int) -> str:
    if not prompts:
        raise SegmentationError("at least one object prompt is needed")
    if len({p.sam_id for p in prompts}) != len(prompts):
        raise SegmentationError("SAM object ids must be unique")
    objects = [
        PromptObject(
            id=prompt.sam_id,
            prompts=[
                FramePrompt(
                    frame=0,
                    box=PromptBox(
                        prompt.box.left,
                        prompt.box.top,
                        prompt.box.right,
                        prompt.box.bottom,
                    ),
                    points=[] if prompt.point is None else [PromptPoint(*prompt.point)],
                )
            ],
        )
        for prompt in prompts
    ]
    return build_object_prompt(size=(width, height), objects=objects)


def masks_from_records(
    records: Sequence[SegmentationRecord],
    decode: MaskDecoder = decode_mask_to_raster,
) -> SegmentationResult:
    masks: dict[int, ObjectMask] = {}
    for record in records:
        if (
            not isinstance(record, SegmentationMaskRecord)
            or not record.object_id.isdigit()
        ):
            continue
        raster = np.frombuffer(decode(record.mask), dtype=np.uint8)
        local = raster.reshape(record.mask.height, record.mask.width).astype(np.bool_)
        bounds = record.bounds
        box = PixelBox(
            left=int(np.floor(bounds.left)),
            top=int(np.floor(bounds.top)),
            right=max(int(np.ceil(bounds.right)), int(np.floor(bounds.left)) + 1),
            bottom=max(int(np.ceil(bounds.bottom)), int(np.floor(bounds.top)) + 1),
        )
        sam_id = int(record.object_id)
        masks[sam_id] = ObjectMask(
            sam_id=sam_id, confidence=record.confidence, bounds=box, mask=local
        )
    return SegmentationResult(masks=masks)


def encode_image(image: Image) -> str:
    ok, buffer = cv2.imencode(
        ".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, SAM_JPEG_QUALITY]
    )
    if not ok:
        raise SegmentationError("could not encode the frame")
    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode(
        "ascii"
    )


async def _parse_events(events: AsyncIterator[object]) -> Sequence[SegmentationRecord]:
    parsed = parse_responses_stream(events, image_segmentation_format())  # type: ignore[arg-type]
    async for _ in parsed:
        continue
    result = await parsed.final_result()
    return result.records


class SamSegmenter:
    def __init__(self, client: MetaClient) -> None:
        self._client = client

    @property
    def is_available(self) -> bool:
        return self._client.is_available(MetaModel.SAM)

    async def segment(
        self, image: Image, prompts: Sequence[ObjectPrompt]
    ) -> SegmentationResult:
        height, width = image.shape[:2]
        text = build_prompt_text(prompts, width, height)
        return await self._run(text, image)

    async def segment_concept(self, image: Image, label: str) -> SegmentationResult:
        concept = " ".join(label.split())[:40]
        if not concept:
            raise SegmentationError("concept label is empty")
        return await self._run(concept, image)

    async def _run(self, text: str, image: Image) -> SegmentationResult:
        data_url = encode_image(image)

        async def operation() -> Sequence[SegmentationRecord]:
            stream = await self._client.sdk().responses.create(
                model=MetaModel.SAM.value,
                store=False,
                input=[
                    {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": text},
                            {
                                "type": "input_image",
                                "image_url": data_url,
                                "detail": "auto",
                            },
                        ],
                    }
                ],
                stream=True,
                metadata=SAM_METADATA,
            )
            return await _parse_events(stream.__aiter__())

        records = await self._client.execute(
            SAM_SPEC, operation, lambda _: Usage(images=1)
        )
        return masks_from_records(records)


class TrackerOnlySegmenter:
    @property
    def is_available(self) -> bool:
        return False

    async def segment(
        self, image: Image, prompts: Sequence[ObjectPrompt]
    ) -> SegmentationResult:
        return SegmentationResult()


class ConceptSegmenter(Protocol):
    async def segment_concept(self, image: Image, label: str) -> SegmentationResult: ...


class AnchorStatus(StrEnum):
    ACCEPTED = "accepted"
    HISTOGRAM = "histogram"
    POINT = "point"
    CONCEPT = "concept"
    UNCERTAIN = "uncertain"
    TRACKER = "tracker"


@dataclass(frozen=True)
class ReanchorTarget:
    sam_id: int
    tracker_box: PixelBox
    label: str
    histogram: tuple[float, ...]


@dataclass(frozen=True)
class Anchor:
    sam_id: int
    box: PixelBox
    x_cm: float
    y_cm: float
    status: AnchorStatus
    mask: ObjectMask | None = field(default=None, compare=False)

    @property
    def is_uncertain(self) -> bool:
        return self.status in (AnchorStatus.UNCERTAIN, AnchorStatus.TRACKER)


HistogramFn = Callable[[Image, ObjectMask], tuple[float, ...]]
DistanceFn = Callable[[tuple[float, ...], tuple[float, ...]], float]


def _box_centre(box: PixelBox) -> tuple[float, float]:
    return (box.left + box.right) / 2, (box.top + box.bottom) / 2


def _centre_point(target: ReanchorTarget) -> tuple[int, int]:
    x, y = _box_centre(target.tracker_box)
    return round(x), round(y)


def _tracker_anchor(
    target: ReanchorTarget, px_per_cm: float, status: AnchorStatus
) -> Anchor:
    x, y = _box_centre(target.tracker_box)
    return Anchor(
        sam_id=target.sam_id,
        box=target.tracker_box,
        x_cm=x / px_per_cm,
        y_cm=y / px_per_cm,
        status=status,
    )


def _mask_anchor(mask: ObjectMask, px_per_cm: float, status: AnchorStatus) -> Anchor:
    x, y = mask_centroid_px(mask)
    return Anchor(
        sam_id=mask.sam_id,
        box=mask.bounds,
        x_cm=x / px_per_cm,
        y_cm=y / px_per_cm,
        status=status,
        mask=mask,
    )


def _confident(mask: ObjectMask | None) -> bool:
    return (
        mask is not None
        and mask.confidence is not None
        and mask.confidence >= SAM_ACCEPT_CONFIDENCE
    )


async def _concept_anchor(
    segmenter: ConceptSegmenter,
    image: Image,
    target: ReanchorTarget,
    px_per_cm: float,
    histogram_of: HistogramFn,
    distance_of: DistanceFn,
) -> Anchor | None:
    result = await segmenter.segment_concept(image, target.label)
    cx, cy = _box_centre(target.tracker_box)
    best: tuple[float, ObjectMask] | None = None
    for candidate in result.masks.values():
        mx, my = mask_centroid_px(candidate)
        if math.hypot(mx - cx, my - cy) / px_per_cm > RECOVERY_SEARCH_RADIUS_CM:
            continue
        distance = distance_of(target.histogram, histogram_of(image, candidate))
        if best is None or distance < best[0]:
            best = (distance, candidate)
    if best is None:
        return None
    return _mask_anchor(
        replace(best[1], sam_id=target.sam_id), px_per_cm, AnchorStatus.CONCEPT
    )


async def reanchor(
    segmenter: Segmenter,
    image: Image,
    targets: Sequence[ReanchorTarget],
    px_per_cm: float,
    histogram_of: HistogramFn,
    distance_of: DistanceFn,
) -> dict[int, Anchor]:
    if not targets:
        return {}
    fallback = {
        t.sam_id: _tracker_anchor(t, px_per_cm, AnchorStatus.TRACKER) for t in targets
    }
    if not segmenter.is_available:
        return fallback
    try:
        return await _reanchor_ladder(
            segmenter, image, targets, px_per_cm, histogram_of, distance_of
        )
    except (SegmentationError, MetaError):
        return fallback


async def _reanchor_ladder(
    segmenter: Segmenter,
    image: Image,
    targets: Sequence[ReanchorTarget],
    px_per_cm: float,
    histogram_of: HistogramFn,
    distance_of: DistanceFn,
) -> dict[int, Anchor]:
    height, width = image.shape[:2]
    padded = {
        t.sam_id: pad_box(t.tracker_box, REANCHOR_BOX_PADDING, width, height)
        for t in targets
    }
    first = await segmenter.segment(
        image, [ObjectPrompt(t.sam_id, padded[t.sam_id]) for t in targets]
    )
    anchors: dict[int, Anchor] = {}
    retry: list[ReanchorTarget] = []
    for target in targets:
        mask = first.get(target.sam_id)
        if mask is None or not _confident(mask):
            retry.append(target)
            continue
        if box_iou(mask.bounds, target.tracker_box) >= SAM_TRACKER_IOU_ACCEPT:
            anchors[target.sam_id] = _mask_anchor(
                mask, px_per_cm, AnchorStatus.ACCEPTED
            )
            continue
        distance = distance_of(target.histogram, histogram_of(image, mask))
        if distance <= HISTOGRAM_MATCH_MAX:
            anchors[target.sam_id] = _mask_anchor(
                mask, px_per_cm, AnchorStatus.HISTOGRAM
            )
        else:
            retry.append(target)

    remaining: list[ReanchorTarget] = []
    if retry:
        try:
            second = await segmenter.segment(
                image,
                [
                    ObjectPrompt(t.sam_id, padded[t.sam_id], point=_centre_point(t))
                    for t in retry
                ],
            )
        except (SegmentationError, MetaError):
            for target in retry:
                anchors[target.sam_id] = _tracker_anchor(
                    target, px_per_cm, AnchorStatus.UNCERTAIN
                )
            return anchors
        for target in retry:
            mask = second.get(target.sam_id)
            if mask is not None and _confident(mask):
                anchors[target.sam_id] = _mask_anchor(
                    mask, px_per_cm, AnchorStatus.POINT
                )
            else:
                remaining.append(target)

    concept_capable = callable(getattr(segmenter, "segment_concept", None))
    for target in remaining:
        found: Anchor | None = None
        if concept_capable:
            try:
                found = await _concept_anchor(
                    cast(ConceptSegmenter, segmenter),
                    image,
                    target,
                    px_per_cm,
                    histogram_of,
                    distance_of,
                )
            except (SegmentationError, MetaError):
                found = None
        anchors[target.sam_id] = found or _tracker_anchor(
            target, px_per_cm, AnchorStatus.UNCERTAIN
        )
    return anchors


SAM_VIDEO_SPEC: Final = CallSpec(
    model=MetaModel.SAM, kind=CallKind.SAM_VIDEO, is_idempotent=True
)
SAM_VIDEO_METADATA: Final = {
    "propagation_direction": "forward",
    "mask_encoding": "one_bit",
}

RecordingBox = tuple[int, int, int, int]


@dataclass(frozen=True)
class TrackBox:
    frame: int
    left: int
    top: int
    right: int
    bottom: int


async def _parse_video_events(
    events: AsyncIterator[object],
) -> Sequence[SegmentationRecord]:
    parsed = parse_responses_stream(events, video_segmentation_format())  # type: ignore[arg-type]
    async for _ in parsed:
        continue
    result = await parsed.final_result()
    return result.records


def _scaled_prompt_box(
    box: RecordingBox, source: tuple[int, int], proxy: tuple[int, int]
) -> PixelBox:
    scale_x = proxy[0] / source[0]
    scale_y = proxy[1] / source[1]
    scaled = PixelBox(
        round(box[0] * scale_x),
        round(box[1] * scale_y),
        round(box[2] * scale_x),
        round(box[3] * scale_y),
    )
    return clamp_box(scaled, proxy[0], proxy[1])


def _scaled_track_box(
    frame: int,
    bounds: tuple[float, float, float, float],
    source: tuple[int, int],
    proxy: tuple[int, int],
) -> TrackBox:
    scale_x = source[0] / proxy[0]
    scale_y = source[1] / proxy[1]
    left = min(max(math.floor(bounds[0] * scale_x), 0), source[0] - 1)
    top = min(max(math.floor(bounds[1] * scale_y), 0), source[1] - 1)
    right = min(max(math.ceil(bounds[2] * scale_x), left + 1), source[0])
    bottom = min(max(math.ceil(bounds[3] * scale_y), top + 1), source[1])
    return TrackBox(frame, left, top, right, bottom)


def tracks_from_records(
    records: Sequence[SegmentationRecord],
    game_ids: Mapping[int, str],
    source: tuple[int, int],
    proxy: tuple[int, int],
) -> dict[str, tuple[TrackBox, ...]]:
    found: dict[tuple[int, int], TrackBox] = {}
    from_box: set[tuple[int, int]] = set()
    for record in records:
        if not isinstance(record, (SegmentationBoxRecord, SegmentationMaskRecord)):
            continue
        if not record.object_id.isdigit() or record.frame is None:
            continue
        sam_id = int(record.object_id)
        if sam_id not in game_ids:
            continue
        key = (sam_id, record.frame.frame_index)
        if isinstance(record, SegmentationBoxRecord):
            bounds = (record.left, record.top, record.right, record.bottom)
            from_box.add(key)
        elif key not in from_box:
            edge = record.bounds
            bounds = (edge.left, edge.top, edge.right, edge.bottom)
        else:
            continue
        found[key] = _scaled_track_box(key[1], bounds, source, proxy)
    grouped: dict[str, list[TrackBox]] = {}
    for (sam_id, _), box in found.items():
        grouped.setdefault(game_ids[sam_id], []).append(box)
    return {
        game_id: tuple(sorted(boxes, key=lambda item: item.frame))
        for game_id, boxes in grouped.items()
    }


def build_video_prompt(
    game_ids: Mapping[int, str],
    segments: Sequence[int],
    prompts: Mapping[int, Mapping[str, RecordingBox]],
    source: tuple[int, int],
    proxy: tuple[int, int],
) -> str:
    sam_ids = {game_id: sam_id for sam_id, game_id in game_ids.items()}
    frames_by_object: dict[int, list[FramePrompt]] = {}
    for frame in sorted(segments):
        for game_id, box in prompts.get(frame, {}).items():
            pixel = _scaled_prompt_box(box, source, proxy)
            frames_by_object.setdefault(sam_ids[game_id], []).append(
                FramePrompt(
                    frame=frame,
                    box=PromptBox(pixel.left, pixel.top, pixel.right, pixel.bottom),
                )
            )
    objects = [
        PromptObject(id=sam_id, prompts=frame_prompts)
        for sam_id, frame_prompts in sorted(frames_by_object.items())
    ]
    return build_object_prompt(size=proxy, objects=objects)


def _assign_video_ids(
    segments: Sequence[int], prompts: Mapping[int, Mapping[str, RecordingBox]]
) -> dict[int, str]:
    ordered: list[str] = []
    for frame in sorted(segments):
        for game_id in prompts.get(frame, {}):
            if game_id not in ordered:
                ordered.append(game_id)
    if not ordered:
        raise SegmentationError("no object prompts were given")
    if len(ordered) > MAX_SAM_ID:
        raise SegmentationError("SAM tracks at most 16 objects per request")
    return {index + MIN_SAM_ID: game_id for index, game_id in enumerate(ordered)}


def _distinct_frames(records: Sequence[SegmentationRecord]) -> int:
    return len(
        {
            record.frame.frame_index
            for record in records
            if not isinstance(record, SegmentationTextRecord)
            and record.frame is not None
        }
    )


class SamVideoTracker:
    def __init__(self, client: MetaClient) -> None:
        self._client = client

    @property
    def is_available(self) -> bool:
        return self._client.is_available(MetaModel.SAM)

    async def track(
        self,
        file_id: str,
        segments: Sequence[int],
        prompts: Mapping[int, Mapping[str, RecordingBox]],
        *,
        source_size: tuple[int, int],
        proxy_size: tuple[int, int],
    ) -> dict[str, tuple[TrackBox, ...]]:
        if not file_id:
            raise SegmentationError("a file id is required")
        if not segments or not prompts:
            raise SegmentationError("segments and prompts are required")
        if min(source_size) <= 0 or min(proxy_size) <= 0:
            raise SegmentationError("frame sizes must be positive")
        if set(prompts) - set(segments) or min(segments) < 0:
            raise SegmentationError("prompts must sit on segment first frames")
        game_ids = _assign_video_ids(segments, prompts)
        text = build_video_prompt(game_ids, segments, prompts, source_size, proxy_size)

        async def operation() -> Sequence[SegmentationRecord]:
            message: Any = [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": text},
                        {"type": "input_video", "file_id": file_id},
                    ],
                }
            ]
            stream = await self._client.sdk().responses.create(
                model=MetaModel.SAM.value,
                store=False,
                input=message,
                stream=True,
                metadata=SAM_VIDEO_METADATA,
            )
            return await _parse_video_events(stream.__aiter__())

        records = await self._client.execute(
            SAM_VIDEO_SPEC,
            operation,
            lambda found: Usage(frames=_distinct_frames(found)),
        )
        return tracks_from_records(records, game_ids, source_size, proxy_size)

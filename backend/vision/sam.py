import base64
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass, field
from typing import Final, Protocol

import cv2
import numpy as np
import numpy.typing as npt
from meta_sam_parser import (
    FramePrompt,
    PromptBox,
    PromptObject,
    PromptPoint,
    SegmentationMask,
    SegmentationMaskRecord,
    SegmentationRecord,
    build_object_prompt,
    decode_mask_to_raster,
    image_segmentation_format,
    parse_responses_stream,
)

from config import CallKind, MetaModel
from meta_client import CallSpec, MetaClient, Usage

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

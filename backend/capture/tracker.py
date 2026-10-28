import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final, Protocol, cast

import cv2

from config import (
    MAX_BETWEEN_TURN_SAM_CALLS,
    POSITION_EMA_ALPHA,
    STILL_FRAME_MEAN_DIFF_MAX,
    TRACKER_LOSS_SAM_DELAY_S,
    TRACKING_WIDTH_PX,
)
from vision.sam import Image, PixelBox, SegmentationError, clamp_box

IntBox = tuple[int, int, int, int]
MIN_TRACK_SIDE_PX: Final = 4


class TrackerBackend(Protocol):
    def init(self, frame: Image, box: IntBox) -> None: ...

    def update(self, frame: Image) -> tuple[bool, IntBox]: ...


class _CvTracker(Protocol):
    def init(self, image: Image, boundingBox: IntBox) -> object: ...

    def update(self, image: Image) -> tuple[bool, tuple[float, ...]]: ...


class _CvBackend:
    def __init__(self, tracker: _CvTracker) -> None:
        self._tracker = tracker

    def init(self, frame: Image, box: IntBox) -> None:
        self._tracker.init(frame, box)

    def update(self, frame: Image) -> tuple[bool, IntBox]:
        ok, raw = self._tracker.update(frame)
        x, y, w, h = raw
        return bool(ok), (round(x), round(y), round(w), round(h))


def kcf_backend() -> TrackerBackend:
    tracker = cv2.TrackerKCF_create()  # type: ignore[attr-defined]
    return _CvBackend(cast(_CvTracker, tracker))


def csrt_backend() -> TrackerBackend:
    tracker = cv2.TrackerCSRT_create()  # type: ignore[attr-defined]
    return _CvBackend(cast(_CvTracker, tracker))


@dataclass(frozen=True)
class TrackedPose:
    sam_id: int
    box: PixelBox
    x_cm: float
    y_cm: float
    is_frozen: bool
    lost_for_s: float


@dataclass
class _Slot:
    backend: TrackerBackend
    box: PixelBox
    cx: float
    cy: float
    lost_since: float | None = None


def _centre(box: PixelBox) -> tuple[float, float]:
    return (box.left + box.right) / 2, (box.top + box.bottom) / 2


class TrackerSet:
    def __init__(
        self,
        px_per_cm: float,
        warped_size: tuple[int, int],
        backend_factory: Callable[[], TrackerBackend] = kcf_backend,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if px_per_cm <= 0:
            raise SegmentationError("px per cm must be positive")
        self._px_per_cm = px_per_cm
        self._width, self._height = warped_size
        self._factory = backend_factory
        self._clock = clock
        self._slots: dict[int, _Slot] = {}
        self._previous_gray: Image | None = None
        self._last_motion = False
        self._recoveries_used = 0

    def _scale(self, frame: Image) -> float:
        return TRACKING_WIDTH_PX / int(frame.shape[1])

    def _small(self, frame: Image) -> Image:
        scale = self._scale(frame)
        size = (TRACKING_WIDTH_PX, max(1, round(frame.shape[0] * scale)))
        return cast(Image, cv2.resize(frame, size, interpolation=cv2.INTER_AREA))

    @staticmethod
    def _gray(small: Image) -> Image:
        if small.ndim == 2:
            return small
        return cast(Image, cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))

    @staticmethod
    def _to_small_box(box: PixelBox, scale: float) -> IntBox:
        return (
            round(box.left * scale),
            round(box.top * scale),
            max(MIN_TRACK_SIDE_PX, round(box.width * scale)),
            max(MIN_TRACK_SIDE_PX, round(box.height * scale)),
        )

    def _init_slot(self, small: Image, scale: float, box: PixelBox) -> _Slot:
        backend = self._factory()
        backend.init(small, self._to_small_box(box, scale))
        cx, cy = _centre(box)
        return _Slot(backend=backend, box=box, cx=cx, cy=cy)

    def reset(self, frame: Image, boxes: Mapping[int, PixelBox]) -> None:
        small = self._small(frame)
        scale = self._scale(frame)
        self._slots = {
            sam_id: self._init_slot(small, scale, box) for sam_id, box in boxes.items()
        }
        self._previous_gray = self._gray(small)
        self._last_motion = False

    def _motion(self, gray: Image) -> bool:
        previous = self._previous_gray
        if previous is None or previous.shape != gray.shape:
            return False
        diff = cv2.absdiff(previous, gray)
        return bool(float(diff.mean()) > STILL_FRAME_MEAN_DIFF_MAX)

    def has_motion(self, frame: Image) -> bool:
        return self._motion(self._gray(self._small(frame)))

    def _pose(self, sam_id: int, slot: _Slot, now: float) -> TrackedPose:
        lost = 0.0 if slot.lost_since is None else max(0.0, now - slot.lost_since)
        return TrackedPose(
            sam_id=sam_id,
            box=slot.box,
            x_cm=slot.cx / self._px_per_cm,
            y_cm=slot.cy / self._px_per_cm,
            is_frozen=slot.lost_since is not None,
            lost_for_s=lost,
        )

    def _apply(self, slot: _Slot, small_box: IntBox, scale: float, now: float) -> bool:
        x, y, w, h = small_box
        if w <= 0 or h <= 0:
            return False
        height, width = self._height, self._width
        try:
            box = clamp_box(
                PixelBox(
                    round(x / scale),
                    round(y / scale),
                    round((x + w) / scale),
                    round((y + h) / scale),
                ),
                width,
                height,
            )
        except SegmentationError:
            return False
        mx, my = _centre(box)
        alpha = POSITION_EMA_ALPHA
        slot.cx = alpha * mx + (1 - alpha) * slot.cx
        slot.cy = alpha * my + (1 - alpha) * slot.cy
        slot.box = box
        slot.lost_since = None
        return True

    def update(self, frame: Image) -> list[TrackedPose]:
        small = self._small(frame)
        scale = self._scale(frame)
        gray = self._gray(small)
        self._last_motion = self._motion(gray)
        self._previous_gray = gray
        now = self._clock()
        poses: list[TrackedPose] = []
        for sam_id, slot in self._slots.items():
            ok, small_box = slot.backend.update(small)
            applied = ok and self._apply(slot, small_box, scale, now)
            if not applied and slot.lost_since is None:
                slot.lost_since = now
            poses.append(self._pose(sam_id, slot, now))
        return poses

    def recovery_candidates(self) -> list[int]:
        remaining = MAX_BETWEEN_TURN_SAM_CALLS - self._recoveries_used
        if remaining <= 0 or self._last_motion:
            return []
        now = self._clock()
        lost = [
            (now - slot.lost_since, sam_id)
            for sam_id, slot in self._slots.items()
            if slot.lost_since is not None
            and now - slot.lost_since >= TRACKER_LOSS_SAM_DELAY_S
        ]
        lost.sort(reverse=True)
        return [sam_id for _, sam_id in lost[:remaining]]

    def mark_recovery_used(self, sam_id: int) -> None:
        self._recoveries_used += 1

    def new_turn(self) -> None:
        self._recoveries_used = 0

    def relock(self, sam_id: int, frame: Image, box: PixelBox) -> None:
        small = self._small(frame)
        self._slots[sam_id] = self._init_slot(small, self._scale(frame), box)

    def remove(self, sam_id: int) -> None:
        self._slots.pop(sam_id, None)

    def boxes(self) -> dict[int, PixelBox]:
        return {sam_id: slot.box for sam_id, slot in self._slots.items()}

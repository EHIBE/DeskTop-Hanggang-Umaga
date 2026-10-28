from dataclasses import dataclass
from typing import Final

import cv2
import numpy as np
import numpy.typing as npt

from vision.sam import ObjectMask

Image = npt.NDArray[np.uint8]

HIST_BINS: Final = (8, 4, 4)
HIST_RANGES: Final = (0, 180, 0, 256, 0, 256)
REF_CROP_PX: Final = 128
HIST_WEIGHT: Final = 0.5
AREA_WEIGHT: Final = 0.3
ASPECT_WEIGHT: Final = 0.2


class SignatureError(Exception):
    pass


@dataclass(frozen=True)
class Signature:
    label: str
    histogram: tuple[float, ...]
    area_cm2: float
    aspect: float


@dataclass(frozen=True)
class SignatureCapture:
    signature: Signature
    ref_crop_png: bytes


def _crop(image: Image, mask: ObjectMask) -> tuple[Image, npt.NDArray[np.uint8]]:
    height, width = image.shape[:2]
    box = mask.bounds
    left, top = max(box.left, 0), max(box.top, 0)
    right, bottom = min(box.right, width), min(box.bottom, height)
    if right <= left or bottom <= top:
        raise SignatureError("mask lies outside the frame")
    crop = image[top:bottom, left:right]
    local = mask.mask[
        top - box.top : bottom - box.top, left - box.left : right - box.left
    ]
    return crop, (local.astype(np.uint8) * 255)


def histogram(image: Image, mask: ObjectMask) -> tuple[float, ...]:
    crop, local_mask = _crop(image, mask)
    if local_mask.shape[:2] != crop.shape[:2] or not local_mask.any():
        raise SignatureError("mask is empty")
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist(
        [hsv], [0, 1, 2], local_mask, list(HIST_BINS), list(HIST_RANGES)
    )
    cv2.normalize(hist, hist, alpha=1.0, norm_type=cv2.NORM_L1)
    return tuple(float(v) for v in hist.flatten())


def make_signature(
    image: Image, mask: ObjectMask, label: str, px_per_cm: float
) -> SignatureCapture:
    hist = histogram(image, mask)
    area_cm2 = mask.pixel_count / (px_per_cm * px_per_cm)
    aspect = mask.bounds.width / mask.bounds.height
    crop, local_mask = _crop(image, mask)
    masked = crop.copy()
    masked[local_mask == 0] = 128
    long_side = max(masked.shape[:2])
    scale = REF_CROP_PX / long_side
    size = (
        max(1, round(masked.shape[1] * scale)),
        max(1, round(masked.shape[0] * scale)),
    )
    resized = cv2.resize(masked, size, interpolation=cv2.INTER_AREA)
    ok, buffer = cv2.imencode(".png", resized)
    if not ok:
        raise SignatureError("could not encode the reference crop")
    signature = Signature(label=label, histogram=hist, area_cm2=area_cm2, aspect=aspect)
    return SignatureCapture(signature=signature, ref_crop_png=buffer.tobytes())


def bhattacharyya(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    if len(first) != len(second):
        raise SignatureError("histograms differ in size")
    a = np.asarray(first, dtype=np.float32)
    b = np.asarray(second, dtype=np.float32)
    return float(cv2.compareHist(a, b, cv2.HISTCMP_BHATTACHARYYA))


def _ratio(first: float, second: float) -> float:
    high = max(first, second)
    if high <= 0:
        return 0.0
    return min(first, second) / high


def match_score(first: Signature, second: Signature) -> float:
    histogram_similarity = 1.0 - bhattacharyya(first.histogram, second.histogram)
    return (
        HIST_WEIGHT * histogram_similarity
        + AREA_WEIGHT * _ratio(first.area_cm2, second.area_cm2)
        + ASPECT_WEIGHT * _ratio(first.aspect, second.aspect)
    )

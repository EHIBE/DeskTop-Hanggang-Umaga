import hashlib
from dataclasses import dataclass
from typing import Final

import cv2
import numpy as np
import numpy.typing as npt

from config import (
    CHROMA_KEY_HSV_DISTANCE,
    PALETTE_VERSION,
    PROMPT_VERSION,
    SPRITE_ALPHA_MAX,
    SPRITE_ALPHA_MIN,
    SPRITE_CROP_PADDING,
    SPRITE_SIZE_PX,
    SPRITE_SOURCE_LONG_SIDE_PX,
)
from vision.sam import Image, ObjectMask

Color = tuple[int, int, int]

GABI_16: Final[tuple[Color, ...]] = (
    (0x0B, 0x0E, 0x1A),
    (0x1B, 0x22, 0x38),
    (0x2E, 0x3A, 0x5C),
    (0x4A, 0x5D, 0x8A),
    (0x8F, 0xA3, 0xC7),
    (0xE8, 0xEE, 0xF7),
    (0xF2, 0xC1, 0x4E),
    (0xE0, 0x7A, 0x2E),
    (0xB3, 0x3A, 0x3A),
    (0x6B, 0x2D, 0x5C),
    (0x3E, 0x7D, 0x4F),
    (0x7F, 0xB0, 0x69),
    (0x8C, 0x5A, 0x3C),
    (0xC9, 0x9A, 0x6B),
    (0xF4, 0xA6, 0xA0),
    (0xFF, 0xD9, 0xA0),
)
OUTLINE_RGB: Final[Color] = (0x0B, 0x0E, 0x1A)
MAGENTA_KEY: Final[Color] = (255, 0, 255)
GREEN_KEY: Final[Color] = (0, 255, 0)
MAX_OBJECT_COLORS: Final = 8

FILL_GRAY: Final[Color] = (0x80, 0x80, 0x80)
MIN_KEY_SATURATION: Final = 60
MAGENTA_HUE_CV: Final = 150
MAGENTA_HUE_WINDOW_CV: Final = 15
HUE_BINS: Final = 180
HUE_SMOOTH_RADIUS: Final = 2
HUE_WEIGHT: Final = 255.0 / 90.0
OPAQUE_THRESHOLD: Final = 128
MIN_DISTINCT_COLORS: Final = 2
FALLBACK_SUBJECT: Final = "a small desk object"

SPRITE_PROMPT_TEMPLATE: Final = (
    "Redraw the object in this photo as one top-down 16-bit pixel art game "
    "sprite of {subject}, a {unit_class} defender in a Filipino folklore "
    "night game. Keep the object's main colors and silhouette so it is "
    "recognizable. Centered, fills about 80% of the frame, no shadow, no "
    "text, no border. Solid flat {key_hex} background."
)
STYLE_ANCHOR_SENTENCE: Final = "Match the pixel art style of the second image."


class SpriteError(Exception):
    pass


@dataclass(frozen=True)
class SpriteCheck:
    alpha_coverage: float
    distinct_colors: int
    is_valid: bool


def _as_rgb(image: Image) -> Image:
    if image.ndim != 3 or image.shape[2] not in (3, 4):
        raise SpriteError("image must be HxWx3 or HxWx4")
    if image.shape[0] == 0 or image.shape[1] == 0:
        raise SpriteError("image is empty")
    return np.ascontiguousarray(image[:, :, :3], dtype=np.uint8)


def prepare_crop(warped_bgr: Image, mask: ObjectMask) -> Image:
    if mask.mask.size == 0 or not mask.mask.any():
        raise SpriteError("mask is empty")
    frame_h, frame_w = warped_bgr.shape[:2]
    full_mask = mask.mask
    if full_mask.shape != (frame_h, frame_w):
        full_mask = (
            cv2.resize(
                full_mask.astype(np.uint8),
                (frame_w, frame_h),
                interpolation=cv2.INTER_NEAREST,
            )
            > 0
        )
    box = mask.bounds
    pad_x = round(box.width * SPRITE_CROP_PADDING)
    pad_y = round(box.height * SPRITE_CROP_PADDING)
    left = max(0, box.left - pad_x)
    top = max(0, box.top - pad_y)
    right = min(frame_w, box.right + pad_x)
    bottom = min(frame_h, box.bottom + pad_y)
    if right <= left or bottom <= top:
        raise SpriteError("crop falls outside the frame")
    rgb = cv2.cvtColor(warped_bgr[top:bottom, left:right], cv2.COLOR_BGR2RGB)
    local = full_mask[top:bottom, left:right]
    if not local.any():
        raise SpriteError("mask is empty inside the crop")
    gray = np.array(FILL_GRAY, dtype=np.uint8)
    crop = np.where(local[:, :, None], rgb, gray).astype(np.uint8)
    height, width = crop.shape[:2]
    scale = SPRITE_SOURCE_LONG_SIDE_PX / max(height, width)
    new_w = max(1, round(width * scale))
    new_h = max(1, round(height * scale))
    resized = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return np.ascontiguousarray(resized, dtype=np.uint8)


def encode_png(rgb_or_rgba: Image) -> bytes:
    if rgb_or_rgba.ndim != 3 or rgb_or_rgba.shape[2] not in (3, 4):
        raise SpriteError("image must be HxWx3 or HxWx4")
    code = cv2.COLOR_RGB2BGR if rgb_or_rgba.shape[2] == 3 else cv2.COLOR_RGBA2BGRA
    ok, buffer = cv2.imencode(".png", cv2.cvtColor(rgb_or_rgba, code))
    if not ok:
        raise SpriteError("png encode failed")
    return bytes(buffer.tobytes())


def decode_png(data: bytes) -> Image:
    try:
        decoded = cv2.imdecode(
            np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED
        )
    except cv2.error as exc:
        raise SpriteError("cannot decode image") from exc
    if decoded is None:
        raise SpriteError("cannot decode image")
    if decoded.dtype != np.uint8:
        raise SpriteError("only 8-bit images are supported")
    if decoded.ndim == 2:
        rgba = cv2.cvtColor(decoded, cv2.COLOR_GRAY2RGBA)
    elif decoded.shape[2] == 3:
        rgba = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGBA)
    elif decoded.shape[2] == 4:
        rgba = cv2.cvtColor(decoded, cv2.COLOR_BGRA2RGBA)
    else:
        raise SpriteError("unsupported channel count")
    return np.ascontiguousarray(rgba, dtype=np.uint8)


def pick_key_color(crop_rgb: Image) -> Color:
    rgb = _as_rgb(crop_rgb)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    fill = np.all(rgb == np.array(FILL_GRAY, dtype=np.uint8), axis=2)
    selected = (hsv[:, :, 1] > MIN_KEY_SATURATION) & ~fill
    if not selected.any():
        return MAGENTA_KEY
    hist = np.bincount(
        hsv[:, :, 0][selected].astype(np.intp), minlength=HUE_BINS
    ).astype(np.float64)
    smoothed = np.zeros(HUE_BINS, dtype=np.float64)
    for shift in range(-HUE_SMOOTH_RADIUS, HUE_SMOOTH_RADIUS + 1):
        smoothed += np.roll(hist, shift)
    dominant = int(np.argmax(smoothed))
    diff = abs(dominant - MAGENTA_HUE_CV)
    diff = min(diff, HUE_BINS - diff)
    if diff <= MAGENTA_HUE_WINDOW_CV:
        return GREEN_KEY
    return MAGENTA_KEY


def other_key(key: Color) -> Color:
    return GREEN_KEY if tuple(key) == MAGENTA_KEY else MAGENTA_KEY


def _hsv_distance(rgb: Image, key: Color) -> npt.NDArray[np.float64]:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.float64)
    key_pixel = np.array([[key]], dtype=np.uint8)
    key_hsv = cv2.cvtColor(key_pixel, cv2.COLOR_RGB2HSV).astype(np.float64)[0, 0]
    hue = np.abs(hsv[:, :, 0] - key_hsv[0])
    hue = np.minimum(hue, HUE_BINS - hue) * HUE_WEIGHT
    sat = hsv[:, :, 1] - key_hsv[1]
    val = hsv[:, :, 2] - key_hsv[2]
    distance: npt.NDArray[np.float64] = np.sqrt(hue**2 + sat**2 + val**2)
    return distance


def chroma_key(image_rgb_or_rgba: Image, key: Color) -> Image:
    rgb = _as_rgb(image_rgb_or_rgba)
    distance = _hsv_distance(rgb, key)
    alpha = np.where(distance <= CHROMA_KEY_HSV_DISTANCE, 0, 255).astype(np.uint8)
    if image_rgb_or_rgba.shape[2] == 4:
        alpha = np.minimum(alpha, image_rgb_or_rgba[:, :, 3])
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    eroded = cv2.erode(alpha, kernel, borderType=cv2.BORDER_REPLICATE)
    out = np.dstack([rgb, eroded]).astype(np.uint8)
    return np.ascontiguousarray(out)


def _median_cut(pixels: npt.NDArray[np.uint8], count: int) -> list[Color]:
    boxes: list[npt.NDArray[np.int32]] = [pixels.astype(np.int32)]
    while len(boxes) < count:
        best = -1
        best_range = 0
        for index, candidate in enumerate(boxes):
            if len(candidate) < 2:
                continue
            spread = int((candidate.max(axis=0) - candidate.min(axis=0)).max())
            if spread > best_range:
                best, best_range = index, spread
        if best < 0:
            break
        box = boxes.pop(best)
        channel = int((box.max(axis=0) - box.min(axis=0)).argmax())
        order = np.argsort(box[:, channel], kind="stable")
        box = box[order]
        middle = len(box) // 2
        boxes.append(box[:middle])
        boxes.append(box[middle:])
    colors: list[Color] = []
    for box in boxes:
        mean = box.mean(axis=0)
        colors.append((round(mean[0]), round(mean[1]), round(mean[2])))
    return colors


def finalize_sprite(keyed_rgba: Image) -> Image:
    size = SPRITE_SIZE_PX
    if keyed_rgba.ndim != 3 or keyed_rgba.shape[2] != 4:
        raise SpriteError("keyed image must be HxWx4")
    canvas = np.zeros((size, size, 4), dtype=np.uint8)
    ys, xs = np.nonzero(keyed_rgba[:, :, 3] >= OPAQUE_THRESHOLD)
    if len(ys) == 0:
        return canvas
    trimmed = keyed_rgba[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    limit = size - 2
    height, width = trimmed.shape[:2]
    scale = limit / max(height, width)
    new_w = max(1, min(limit, round(width * scale)))
    new_h = max(1, min(limit, round(height * scale)))
    small = cv2.resize(trimmed, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
    left = (size - new_w) // 2
    top = (size - new_h) // 2
    canvas[top : top + new_h, left : left + new_w] = small
    opaque = canvas[:, :, 3] >= OPAQUE_THRESHOLD
    canvas[~opaque] = 0
    canvas[opaque, 3] = 255
    pixels = canvas[opaque][:, :3]
    object_colors = _median_cut(pixels, MAX_OBJECT_COLORS)
    palette = np.array(list(GABI_16) + object_colors, dtype=np.int32)
    diff = pixels.astype(np.int32)[:, None, :] - palette[None, :, :]
    nearest = np.argmin((diff**2).sum(axis=2), axis=1)
    canvas[opaque, :3] = palette[nearest].astype(np.uint8)
    kernel = np.ones((3, 3), dtype=np.uint8)
    grown = cv2.dilate(opaque.astype(np.uint8), kernel) > 0
    ring = grown & ~opaque
    canvas[ring] = (*OUTLINE_RGB, 255)
    return canvas


def validate_sprite(sprite_rgba: Image) -> SpriteCheck:
    if sprite_rgba.ndim != 3 or sprite_rgba.shape[2] != 4:
        raise SpriteError("sprite must be HxWx4")
    opaque = sprite_rgba[:, :, 3] >= OPAQUE_THRESHOLD
    coverage = float(opaque.mean())
    colors = {(int(r), int(g), int(b)) for r, g, b in sprite_rgba[opaque][:, :3]}
    colors.discard(OUTLINE_RGB)
    distinct = len(colors)
    valid = (
        SPRITE_ALPHA_MIN <= coverage <= SPRITE_ALPHA_MAX
        and distinct >= MIN_DISTINCT_COLORS
    )
    return SpriteCheck(
        alpha_coverage=coverage, distinct_colors=distinct, is_valid=valid
    )


def process_generated(
    image_rgba_or_rgb: Image, key: Color
) -> tuple[Image, SpriteCheck]:
    keyed = chroma_key(image_rgba_or_rgb, key)
    sprite = finalize_sprite(keyed)
    return sprite, validate_sprite(sprite)


def apply_mask_alpha(image_rgb: Image, mask: npt.NDArray[np.bool_]) -> Image:
    rgb = _as_rgb(image_rgb)
    if mask.shape != rgb.shape[:2]:
        raise SpriteError("mask shape does not match the image")
    alpha = np.where(mask, 255, 0).astype(np.uint8)
    return np.ascontiguousarray(np.dstack([rgb, alpha]).astype(np.uint8))


def normalize_name(name: str) -> str:
    return " ".join(name.lower().split())


def cache_key(
    signature_id: str,
    unit_name: str,
    unit_class: str,
    palette_version: str = PALETTE_VERSION,
    prompt_version: str = PROMPT_VERSION,
) -> str:
    raw = "|".join(
        (
            signature_id,
            normalize_name(unit_name),
            unit_class,
            palette_version,
            prompt_version,
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def sprite_prompt(
    subject: str, unit_class: str, key: Color, has_style_anchor: bool
) -> str:
    text = SPRITE_PROMPT_TEMPLATE.format(
        subject=subject.strip() or FALLBACK_SUBJECT,
        unit_class=unit_class,
        key_hex=f"#{key[0]:02X}{key[1]:02X}{key[2]:02X}",
    )
    if has_style_anchor:
        text = f"{text} {STYLE_ANCHOR_SENTENCE}"
    return text

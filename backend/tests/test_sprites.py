import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from config import PALETTE_VERSION, PROMPT_VERSION
from vision.sam import Image, ObjectMask, PixelBox
from vision.sprites import (
    GABI_16,
    GREEN_KEY,
    MAGENTA_KEY,
    MAX_OBJECT_COLORS,
    OUTLINE_RGB,
    SpriteError,
    apply_mask_alpha,
    cache_key,
    chroma_key,
    decode_png,
    encode_png,
    finalize_sprite,
    other_key,
    pick_key_color,
    prepare_crop,
    process_generated,
    sprite_prompt,
    validate_sprite,
)

BLUE_MUG = (0x2E, 0x5A, 0xA8)
BROWN_WOOD = (0x8C, 0x5A, 0x3C)
WHITE = (0xE8, 0xEE, 0xF7)
PURPLE = (0xA0, 0x30, 0xA0)
GRAY = (0x60, 0x60, 0x60)


def solid(h: int, w: int, color: tuple[int, int, int]) -> Image:
    out = np.zeros((h, w, 3), dtype=np.uint8)
    out[:, :] = color
    return out


def noisy(image: Image, amount: int = 12, seed: int = 7) -> Image:
    rng = np.random.default_rng(seed)
    noise = rng.integers(-amount, amount + 1, size=image.shape)
    out: Image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return out


def blob_on_key(key: tuple[int, int, int], size: int = 1024) -> Image:
    image = solid(size, size, key)
    yy, xx = np.mgrid[0:size, 0:size]
    inside = (xx - size // 2) ** 2 + (yy - size // 2) ** 2 < (size // 3) ** 2
    image[inside] = BLUE_MUG
    image[inside & (xx > size // 2)] = BROWN_WOOD
    image[inside & (yy < size // 2 - 100)] = WHITE
    return image


def make_mask(frame_h: int, frame_w: int, box: PixelBox) -> ObjectMask:
    mask = np.zeros((frame_h, frame_w), dtype=np.bool_)
    mask[box.top : box.bottom, box.left : box.right] = True
    return ObjectMask(sam_id=1, confidence=0.9, bounds=box, mask=mask)


def test_prepare_crop_long_side_512_and_gray_fill_outside_mask() -> None:
    frame = np.zeros((600, 800, 3), dtype=np.uint8)
    frame[:, :] = (200, 100, 50)
    box = PixelBox(300, 200, 500, 300)
    mask = make_mask(600, 800, box)
    mask.mask[200:300, 300:350] = False
    crop = prepare_crop(frame, mask)
    assert crop.dtype == np.uint8
    assert max(crop.shape[:2]) == 512
    assert crop.shape[2] == 3
    assert tuple(crop[crop.shape[0] // 2, crop.shape[1] // 5]) == (0x80, 0x80, 0x80)
    assert tuple(crop[crop.shape[0] // 2, crop.shape[1] * 7 // 10]) == (50, 100, 200)


def test_prepare_crop_pads_box_and_clamps_to_frame() -> None:
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    box = PixelBox(0, 0, 100, 50)
    crop = prepare_crop(frame, make_mask(100, 100, box))
    assert crop.shape[1] == 512
    assert crop.shape[0] == round(512 * 58 / 100)


def test_prepare_crop_empty_mask_raises() -> None:
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    mask = make_mask(100, 100, PixelBox(10, 10, 40, 40))
    mask.mask[:] = False
    with pytest.raises(SpriteError):
        prepare_crop(frame, mask)


def test_pick_key_color_purple_object_gets_green() -> None:
    crop = solid(512, 512, (0x80, 0x80, 0x80))
    crop[100:400, 100:400] = PURPLE
    assert pick_key_color(crop) == GREEN_KEY


def test_pick_key_color_blue_object_gets_magenta() -> None:
    crop = solid(512, 512, (0x80, 0x80, 0x80))
    crop[100:400, 100:400] = BLUE_MUG
    assert pick_key_color(crop) == MAGENTA_KEY


def test_pick_key_color_gray_object_gets_magenta() -> None:
    crop = solid(512, 512, (0x80, 0x80, 0x80))
    crop[100:400, 100:400] = GRAY
    assert pick_key_color(crop) == MAGENTA_KEY


def test_other_key_swaps() -> None:
    assert other_key(MAGENTA_KEY) == GREEN_KEY
    assert other_key(GREEN_KEY) == MAGENTA_KEY


def test_chroma_key_hsv_distance_hue_wrap_weighted_plus_sat_val_euclid_clears_noisy_magenta() -> (
    None
):
    image = noisy(solid(200, 200, MAGENTA_KEY))
    keyed = chroma_key(image, MAGENTA_KEY)
    assert keyed.shape == (200, 200, 4)
    assert int(keyed[:, :, 3].max()) == 0


@pytest.mark.parametrize("color", [BLUE_MUG, BROWN_WOOD, WHITE])
def test_chroma_key_hsv_distance_keeps_typical_object_colors_on_magenta(
    color: tuple[int, int, int],
) -> None:
    image = solid(100, 100, MAGENTA_KEY)
    image[20:80, 20:80] = color
    keyed = chroma_key(noisy(image), MAGENTA_KEY)
    assert int(keyed[50, 50, 3]) == 255
    assert int(keyed[2, 2, 3]) == 0


def test_chroma_key_erodes_alpha_by_one_pixel() -> None:
    image = solid(40, 40, MAGENTA_KEY)
    image[10:30, 10:30] = BLUE_MUG
    keyed = chroma_key(image, MAGENTA_KEY)
    opaque = keyed[:, :, 3] == 255
    assert int(opaque.sum()) < 400
    assert bool(opaque[20, 20])
    assert not bool(opaque[10, 10])


def test_chroma_key_green_path_keeps_objects_and_clears_background() -> None:
    image = solid(100, 100, GREEN_KEY)
    image[20:80, 20:80] = PURPLE
    keyed = chroma_key(noisy(image), GREEN_KEY)
    assert int(keyed[50, 50, 3]) == 255
    assert int(keyed[2, 2, 3]) == 0


def test_chroma_key_accepts_rgba_and_respects_existing_alpha() -> None:
    rgba = np.dstack([solid(20, 20, BLUE_MUG), np.full((20, 20), 255, np.uint8)])
    rgba[:, :5, 3] = 0
    keyed = chroma_key(rgba, MAGENTA_KEY)
    assert int(keyed[10, 2, 3]) == 0
    assert int(keyed[10, 12, 3]) == 255


def test_chroma_key_rejects_bad_shape() -> None:
    with pytest.raises(SpriteError):
        chroma_key(np.zeros((4, 4), dtype=np.uint8), MAGENTA_KEY)


def test_finalize_sprite_48x48_with_outline_and_limited_palette() -> None:
    keyed = chroma_key(blob_on_key(MAGENTA_KEY, 256), MAGENTA_KEY)
    sprite = finalize_sprite(keyed)
    assert sprite.shape == (48, 48, 4)
    opaque = sprite[:, :, 3] == 255
    assert bool(opaque.any())
    assert set(np.unique(sprite[:, :, 3]).tolist()) <= {0, 255}
    colors = {tuple(int(v) for v in p) for p in sprite[opaque][:, :3]}
    assert OUTLINE_RGB in colors
    assert len(colors) <= 16 + MAX_OBJECT_COLORS
    outline = np.all(sprite[:, :, :3] == OUTLINE_RGB, axis=2) & opaque
    inner = opaque & ~outline
    grown = cv2.dilate(inner.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    assert bool(grown[outline].all())


def test_finalize_sprite_empty_input_returns_transparent_canvas() -> None:
    sprite = finalize_sprite(np.zeros((30, 30, 4), dtype=np.uint8))
    assert sprite.shape == (48, 48, 4)
    assert int(sprite[:, :, 3].max()) == 0


def test_finalize_sprite_is_deterministic() -> None:
    keyed = chroma_key(noisy(blob_on_key(MAGENTA_KEY, 256)), MAGENTA_KEY)
    first = encode_png(finalize_sprite(keyed))
    second = encode_png(finalize_sprite(keyed.copy()))
    assert first == second


def test_validate_sprite_almost_empty_fails() -> None:
    sprite = np.zeros((48, 48, 4), dtype=np.uint8)
    sprite[10:12, 10:12] = (*BLUE_MUG, 255)
    check = validate_sprite(sprite)
    assert not check.is_valid
    assert check.alpha_coverage < 0.15


def test_validate_sprite_full_canvas_fails() -> None:
    sprite = np.zeros((48, 48, 4), dtype=np.uint8)
    sprite[:, :, :3] = BLUE_MUG
    sprite[:, :24, :3] = BROWN_WOOD
    sprite[:, :, 3] = 255
    check = validate_sprite(sprite)
    assert not check.is_valid
    assert check.alpha_coverage == 1.0
    assert check.distinct_colors == 2


def test_validate_sprite_single_color_fails_and_two_colors_pass() -> None:
    sprite = np.zeros((48, 48, 4), dtype=np.uint8)
    sprite[10:38, 10:38] = (*BLUE_MUG, 255)
    one = validate_sprite(sprite)
    assert one.distinct_colors == 1
    assert not one.is_valid
    sprite[10:38, 10:20] = (*BROWN_WOOD, 255)
    two = validate_sprite(sprite)
    assert two.distinct_colors == 2
    assert two.is_valid


def test_validate_sprite_outline_color_not_counted() -> None:
    sprite = np.zeros((48, 48, 4), dtype=np.uint8)
    sprite[10:38, 10:38] = (*BLUE_MUG, 255)
    sprite[10:38, 10:12] = (*OUTLINE_RGB, 255)
    assert validate_sprite(sprite).distinct_colors == 1


def test_process_generated_end_to_end_on_1024_blob() -> None:
    sprite, check = process_generated(noisy(blob_on_key(MAGENTA_KEY)), MAGENTA_KEY)
    assert sprite.shape == (48, 48, 4)
    assert check.is_valid
    assert check == validate_sprite(sprite)
    assert 0.15 <= check.alpha_coverage <= 0.90


def test_process_generated_green_key_end_to_end() -> None:
    sprite, check = process_generated(noisy(blob_on_key(GREEN_KEY, 512)), GREEN_KEY)
    assert sprite.shape == (48, 48, 4)
    assert check.is_valid


def test_process_generated_all_key_image_is_invalid() -> None:
    sprite, check = process_generated(solid(256, 256, MAGENTA_KEY), MAGENTA_KEY)
    assert not check.is_valid
    assert int(sprite[:, :, 3].max()) == 0


def test_apply_mask_alpha_sets_alpha_from_mask() -> None:
    image = solid(10, 12, BLUE_MUG)
    mask = np.zeros((10, 12), dtype=np.bool_)
    mask[2:5, 3:7] = True
    out = apply_mask_alpha(image, mask)
    assert out.shape == (10, 12, 4)
    assert int(out[3, 4, 3]) == 255
    assert int(out[0, 0, 3]) == 0
    assert tuple(int(v) for v in out[3, 4, :3]) == BLUE_MUG


def test_apply_mask_alpha_shape_mismatch_raises() -> None:
    with pytest.raises(SpriteError):
        apply_mask_alpha(solid(10, 12, BLUE_MUG), np.zeros((5, 5), dtype=np.bool_))


def test_cache_key_stable_and_hex() -> None:
    a = cache_key("sig1", "Tasa", "tank")
    assert a == cache_key("sig1", "Tasa", "tank")
    assert len(a) == 64
    int(a, 16)


def test_cache_key_normalizes_name() -> None:
    assert cache_key("s", "  Mug   Ni  Lola ", "tank") == cache_key(
        "s", "mug ni lola", "tank"
    )


def test_cache_key_changes_with_fields_and_versions() -> None:
    base = cache_key("s", "mug", "tank")
    assert base != cache_key("t", "mug", "tank")
    assert base != cache_key("s", "cup", "tank")
    assert base != cache_key("s", "mug", "healer")
    assert base != cache_key("s", "mug", "tank", palette_version="gabi16-v2")
    assert base != cache_key("s", "mug", "tank", prompt_version="sprite-v2")
    assert base == cache_key("s", "mug", "tank", PALETTE_VERSION, PROMPT_VERSION)


def test_sprite_prompt_magenta_without_anchor() -> None:
    text = sprite_prompt("a blue mug", "tank", MAGENTA_KEY, False)
    assert "pixel art game sprite of a blue mug, a tank defender" in text
    assert text.endswith("Solid flat #FF00FF background.")
    assert "second image" not in text


def test_sprite_prompt_green_with_anchor() -> None:
    text = sprite_prompt("a stapler", "healer", GREEN_KEY, True)
    assert "Solid flat #00FF00 background." in text
    assert text.endswith("Match the pixel art style of the second image.")


def test_sprite_prompt_empty_subject_falls_back() -> None:
    text = sprite_prompt("  ", "tank", MAGENTA_KEY, False)
    assert "sprite of a small desk object, a tank" in text


def test_png_roundtrip_rgba_and_rgb() -> None:
    rgba = np.dstack([noisy(solid(8, 9, BLUE_MUG)), np.full((8, 9), 200, np.uint8)])
    assert np.array_equal(decode_png(encode_png(rgba)), rgba)
    rgb = noisy(solid(8, 9, BROWN_WOOD))
    back = decode_png(encode_png(rgb))
    assert back.shape == (8, 9, 4)
    assert np.array_equal(back[:, :, :3], rgb)
    assert int(back[:, :, 3].min()) == 255


def test_decode_png_grayscale_input() -> None:
    ok, buf = cv2.imencode(".png", np.full((4, 4), 90, dtype=np.uint8))
    assert ok
    out = decode_png(bytes(buf.tobytes()))
    assert out.shape == (4, 4, 4)
    assert tuple(int(v) for v in out[0, 0]) == (90, 90, 90, 255)


@pytest.mark.parametrize("data", [b"not a png", b"", b"\x89PNG\r\n\x1a\ngarbage"])
def test_decode_png_garbage_raises(data: bytes) -> None:
    with pytest.raises(SpriteError):
        decode_png(data)


def test_encode_png_bad_shape_raises() -> None:
    with pytest.raises(SpriteError):
        encode_png(np.zeros((4, 4), dtype=np.uint8))


def test_palette_json_matches_gabi_16() -> None:
    path = Path(__file__).resolve().parents[2] / "assets" / "palette.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == PALETTE_VERSION
    parsed = tuple(
        (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)) for h in data["colors"]
    )
    assert parsed == GABI_16
    assert GABI_16[0] == OUTLINE_RGB

import numpy as np
import numpy.typing as npt
import pytest
from meta_sam_parser import (
    SegmentationBoxRecord,
    SegmentationMask,
    SegmentationMaskBounds,
    SegmentationMaskIdentity,
    SegmentationMaskRecord,
    SegmentationRecord,
)

from vision.sam import (
    ObjectMask,
    ObjectPrompt,
    PixelBox,
    SegmentationError,
    TrackerOnlySegmenter,
    box_iou,
    box_overlap_ratio,
    build_prompt_text,
    clamp_box,
    mask_centroid_px,
    mask_hull_px,
    mask_in_frame,
    masks_from_records,
    pad_box,
)
from vision.signature import (
    SignatureError,
    bhattacharyya,
    histogram,
    make_signature,
    match_score,
)


def square_mask(
    sam_id: int = 1, left: int = 10, top: int = 20, size: int = 40
) -> ObjectMask:
    return ObjectMask(
        sam_id=sam_id,
        confidence=0.9,
        bounds=PixelBox(left, top, left + size, top + size),
        mask=np.ones((size, size), dtype=np.bool_),
    )


def test_pixel_box_needs_area() -> None:
    with pytest.raises(SegmentationError):
        PixelBox(5, 5, 5, 10)


def test_object_prompt_id_range() -> None:
    with pytest.raises(SegmentationError):
        ObjectPrompt(sam_id=17, box=PixelBox(0, 0, 10, 10))


def test_pad_and_clamp_box() -> None:
    padded = pad_box(PixelBox(100, 100, 200, 150), 0.2, 1200, 800)
    assert padded == PixelBox(80, 90, 220, 160)
    assert pad_box(PixelBox(0, 0, 50, 50), 0.5, 60, 60) == PixelBox(0, 0, 60, 60)
    assert clamp_box(PixelBox(-5, -5, 2000, 900), 1200, 800) == PixelBox(
        0, 0, 1200, 800
    )


def test_iou_and_overlap() -> None:
    a = PixelBox(0, 0, 10, 10)
    assert box_iou(a, a) == 1.0
    assert box_iou(a, PixelBox(20, 20, 30, 30)) == 0.0
    assert box_iou(a, PixelBox(5, 0, 15, 10)) == pytest.approx(50 / 150)
    assert box_overlap_ratio(a, PixelBox(0, 0, 5, 5)) == 1.0
    assert box_overlap_ratio(a, PixelBox(50, 50, 60, 60)) == 0.0


def test_prompt_text_uses_wire_grammar_and_points() -> None:
    text = build_prompt_text(
        [
            ObjectPrompt(1, PixelBox(400, 300, 490, 400)),
            ObjectPrompt(2, PixelBox(640, 120, 705, 182), point=(670, 150)),
        ],
        1200,
        800,
    )
    assert text.startswith("<0f>1<|box;")
    assert ",2<|box;" in text
    assert "<|point;" in text
    assert "w=1200;h=800" in text


def test_prompt_text_rejects_empty_and_duplicates() -> None:
    with pytest.raises(SegmentationError):
        build_prompt_text([], 100, 100)
    box = PixelBox(0, 0, 10, 10)
    with pytest.raises(SegmentationError):
        build_prompt_text([ObjectPrompt(1, box), ObjectPrompt(1, box)], 100, 100)


def mask_record(
    object_id: str, width: int, height: int, left: float, top: float
) -> SegmentationMaskRecord:
    identity = SegmentationMaskIdentity(
        media="image", frame_index=None, object_id=object_id
    )
    return SegmentationMaskRecord(
        order=0,
        object_id=object_id,
        identity=identity,
        revision=0,
        mask=SegmentationMask(
            encoding="one_bit", payload="!", width=width, height=height
        ),
        bounds=SegmentationMaskBounds(left, top, left + width, top + height),
        confidence=0.8,
    )


def test_masks_from_records_converts_and_skips_non_masks() -> None:
    records: list[SegmentationRecord] = [
        mask_record("3", 4, 2, 10.0, 20.0),
        SegmentationBoxRecord(order=1, object_id="5", left=0, top=0, right=1, bottom=1),
        mask_record("x", 1, 1, 0.0, 0.0),
    ]
    result = masks_from_records(
        records, decode=lambda mask: bytes([1] * (mask.width * mask.height))
    )
    assert set(result.masks) == {3}
    mask = result.masks[3]
    assert mask.bounds == PixelBox(10, 20, 14, 22)
    assert mask.mask.shape == (2, 4)
    assert mask.pixel_count == 8
    assert mask.confidence == 0.8
    assert result.get(9) is None


def test_mask_geometry() -> None:
    mask = square_mask()
    assert mask_centroid_px(mask) == pytest.approx((29.5, 39.5))
    hull = mask_hull_px(mask)
    assert len(hull) >= 4
    full = mask_in_frame(mask, 100, 100)
    assert full.shape == (100, 100)
    assert int(full.sum()) == 1600


def test_empty_mask_centroid_falls_back_to_box_center() -> None:
    empty = ObjectMask(
        1, 0.9, PixelBox(0, 0, 10, 20), np.zeros((20, 10), dtype=np.bool_)
    )
    assert mask_centroid_px(empty) == (5.0, 10.0)
    assert len(mask_hull_px(empty)) == 4


async def _no_segments() -> None:
    result = await TrackerOnlySegmenter().segment(
        np.zeros((10, 10, 3), dtype=np.uint8), []
    )
    assert result.masks == {}


def test_tracker_only_fallback_returns_empty_result() -> None:
    import asyncio

    asyncio.run(_no_segments())
    assert TrackerOnlySegmenter().is_available is False


def colored_frame(color: tuple[int, int, int]) -> npt.NDArray[np.uint8]:
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[20:60, 10:50] = color
    return frame


def test_signature_area_aspect_and_crop() -> None:
    capture = make_signature(
        colored_frame((0, 0, 255)), square_mask(), "mug", px_per_cm=20.0
    )
    assert capture.signature.area_cm2 == pytest.approx(4.0)
    assert capture.signature.aspect == pytest.approx(1.0)
    assert capture.signature.label == "mug"
    assert capture.ref_crop_png.startswith(b"\x89PNG")
    assert sum(capture.signature.histogram) == pytest.approx(1.0, abs=1e-5)


def test_same_object_matches_and_different_color_does_not() -> None:
    red = make_signature(
        colored_frame((0, 0, 255)), square_mask(), "mug", 20.0
    ).signature
    red_again = make_signature(
        colored_frame((0, 0, 255)), square_mask(), "mug", 20.0
    ).signature
    blue = make_signature(
        colored_frame((255, 0, 0)), square_mask(), "mug", 20.0
    ).signature
    assert bhattacharyya(red.histogram, red_again.histogram) == pytest.approx(
        0.0, abs=1e-6
    )
    assert match_score(red, red_again) == pytest.approx(1.0, abs=1e-6)
    assert match_score(red, blue) < 0.8


def test_signature_errors() -> None:
    frame = colored_frame((0, 0, 255))
    outside = ObjectMask(
        1, 0.9, PixelBox(200, 200, 210, 210), np.ones((10, 10), dtype=np.bool_)
    )
    with pytest.raises(SignatureError):
        histogram(frame, outside)
    empty = ObjectMask(
        1, 0.9, PixelBox(0, 0, 10, 10), np.zeros((10, 10), dtype=np.bool_)
    )
    with pytest.raises(SignatureError):
        histogram(frame, empty)
    with pytest.raises(SignatureError):
        bhattacharyya((0.5, 0.5), (1.0,))

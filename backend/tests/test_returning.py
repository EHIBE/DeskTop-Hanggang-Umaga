from dataclasses import dataclass

import cv2
import numpy as np
import numpy.typing as npt
import pytest

from vision.returning import (
    AMBIGUITY_MARGIN,
    MATCH_THRESHOLD,
    StoredSignature,
    find_returning,
    match_returning,
    smooth_histogram,
)
from vision.sam import ObjectMask, PixelBox
from vision.signature import Signature, SignatureError, make_signature

Image = npt.NDArray[np.uint8]
PX_PER_CM = 10.0
DESK = (96, 110, 120)


@dataclass(frozen=True)
class Thing:
    body: tuple[int, int, int]
    accent: tuple[int, int, int]
    width: int
    height: int


THINGS = (
    Thing((46, 90, 168), (232, 238, 247), 220, 220),
    Thing((40, 40, 200), (30, 200, 230), 300, 120),
    Thing((60, 170, 60), (240, 240, 240), 160, 260),
    Thing((200, 80, 40), (30, 30, 30), 240, 240),
    Thing((20, 200, 220), (180, 60, 160), 120, 340),
    Thing((150, 150, 150), (50, 50, 220), 280, 200),
    Thing((30, 30, 30), (200, 200, 60), 200, 300),
    Thing((180, 60, 180), (60, 200, 60), 340, 160),
    Thing((90, 140, 200), (20, 20, 120), 180, 180),
    Thing((230, 230, 230), (200, 120, 40), 260, 260),
)


def capture(
    thing: Thing,
    seed: int,
    scale: float = 1.0,
    brightness: float = 1.0,
    shift: tuple[int, int] = (0, 0),
) -> Signature:
    rng = np.random.default_rng(seed)
    frame = np.full((600, 800, 3), DESK, dtype=np.uint8)
    width = round(thing.width * scale)
    height = round(thing.height * scale)
    left = 300 + shift[0]
    top = 200 + shift[1]
    cv2.rectangle(frame, (left, top), (left + width, top + height), thing.body, -1)
    cv2.rectangle(
        frame,
        (left + width // 4, top + height // 4),
        (left + 3 * width // 4, top + 3 * height // 4),
        thing.accent,
        -1,
    )
    noisy = frame.astype(np.float32) * brightness + rng.normal(0, 4, frame.shape)
    image = np.clip(noisy, 0, 255).astype(np.uint8)
    mask = np.ones((height + 1, width + 1), dtype=np.bool_)
    box = PixelBox(left, top, left + width + 1, top + height + 1)
    capture_ = make_signature(image, ObjectMask(1, 0.9, box, mask), "thing", PX_PER_CM)
    return capture_.signature


def stored_set() -> list[StoredSignature]:
    return [
        StoredSignature(f"unit-{index}", capture(thing, index))
        for index, thing in enumerate(THINGS)
    ]


def test_returning_objects_match_at_least_eight_of_ten() -> None:
    stored = stored_set()
    correct = 0
    for index, thing in enumerate(THINGS):
        again = capture(
            thing,
            100 + index,
            scale=0.96 + 0.01 * (index % 3),
            brightness=0.92 + 0.03 * (index % 4),
            shift=(index * 7 - 30, 25 - index * 5),
        )
        if match_returning(stored, again) == f"unit-{index}":
            correct += 1
    assert correct >= 8


def test_wrong_matches_never_happen_across_the_set() -> None:
    stored = stored_set()
    wrong = 0
    for index, thing in enumerate(THINGS):
        again = capture(thing, 200 + index, brightness=0.9)
        found = match_returning(stored, again)
        if found is not None and found != f"unit-{index}":
            wrong += 1
    assert wrong == 0


def test_new_object_matches_nothing() -> None:
    stored = stored_set()
    stranger = Thing((10, 120, 250), (250, 10, 120), 140, 140)
    assert match_returning(stored, capture(stranger, 7)) is None


def test_empty_store_returns_none() -> None:
    assert match_returning([], capture(THINGS[0], 1)) is None


def test_twins_are_ambiguous_and_return_none() -> None:
    first = capture(THINGS[0], 1)
    twin = capture(THINGS[0], 2)
    stored = [StoredSignature("a", first), StoredSignature("b", twin)]
    found = find_returning(stored, capture(THINGS[0], 3))
    assert found is None


def test_clear_winner_reports_scores() -> None:
    stored = stored_set()
    found = find_returning(stored, capture(THINGS[3], 55))
    assert found is not None
    assert found.unit_id == "unit-3"
    assert found.score >= MATCH_THRESHOLD
    assert found.score - found.runner_up >= AMBIGUITY_MARGIN


def test_mismatched_histogram_size_is_skipped() -> None:
    good = capture(THINGS[0], 1)
    broken = Signature("bad", (1.0,), good.area_cm2, good.aspect)
    stored = [StoredSignature("bad", broken), StoredSignature("good", good)]
    assert match_returning(stored, capture(THINGS[0], 9)) == "good"


def test_dim_lighting_still_matches() -> None:
    stored = stored_set()
    dim = capture(THINGS[2], 77, brightness=0.88)
    assert match_returning(stored, dim) == "unit-2"


def test_smoothing_keeps_a_unit_sum_and_rejects_bad_sizes() -> None:
    smoothed = smooth_histogram(stored_set()[0].signature.histogram)
    assert abs(sum(smoothed) - 1.0) < 1e-6
    with pytest.raises(SignatureError):
        smooth_histogram((1.0, 0.0))
    with pytest.raises(SignatureError):
        smooth_histogram((0.0,) * 128)

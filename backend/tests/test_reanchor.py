import asyncio
from collections.abc import Sequence

import numpy as np
import pytest

from config import RECOVERY_SEARCH_RADIUS_CM
from meta_client import BreakerOpenError
from vision.sam import (
    Anchor,
    AnchorStatus,
    Image,
    ObjectMask,
    ObjectPrompt,
    PixelBox,
    ReanchorTarget,
    SegmentationError,
    SegmentationResult,
    reanchor,
)

PX = 20.0
IMAGE: Image = np.zeros((800, 1200, 3), dtype=np.uint8)
TRACKER_BOX = PixelBox(200, 200, 300, 300)


def mask_for(sam_id: int, box: PixelBox, confidence: float | None) -> ObjectMask:
    raster = np.ones((box.height, box.width), dtype=np.bool_)
    return ObjectMask(sam_id, confidence, box, raster)


def result(*masks: ObjectMask) -> SegmentationResult:
    return SegmentationResult({m.sam_id: m for m in masks})


class FakeSegmenter:
    def __init__(
        self,
        steps: list[SegmentationResult],
        concept: dict[str, SegmentationResult] | None = None,
        available: bool = True,
        error: Exception | None = None,
    ) -> None:
        self.steps = steps
        self.concepts = concept
        self.available = available
        self.error = error
        self.prompts: list[Sequence[ObjectPrompt]] = []
        self.concept_labels: list[str] = []
        if concept is not None:
            self.segment_concept = self._segment_concept

    @property
    def is_available(self) -> bool:
        return self.available

    async def segment(
        self, image: Image, prompts: Sequence[ObjectPrompt]
    ) -> SegmentationResult:
        if self.error is not None:
            raise self.error
        self.prompts.append(prompts)
        return self.steps[len(self.prompts) - 1]

    async def _segment_concept(self, image: Image, label: str) -> SegmentationResult:
        self.concept_labels.append(label)
        assert self.concepts is not None
        return self.concepts[label]


def target(sam_id: int = 1, label: str = "cup") -> ReanchorTarget:
    return ReanchorTarget(sam_id, TRACKER_BOX, label, (100.0, 0.0))


def hist_of(image: Image, mask: ObjectMask) -> tuple[float, ...]:
    return (float(mask.bounds.width), 0.0)


def distance(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    return abs(first[0] - second[0]) / 1000


def run(
    segmenter: FakeSegmenter, targets: Sequence[ReanchorTarget]
) -> dict[int, Anchor]:
    return asyncio.run(reanchor(segmenter, IMAGE, targets, PX, hist_of, distance))


def test_step1_accepts_confident_overlap() -> None:
    mask = mask_for(1, PixelBox(205, 205, 305, 305), 0.9)
    seg = FakeSegmenter([result(mask)])
    anchor = run(seg, [target()])[1]
    assert anchor.status is AnchorStatus.ACCEPTED
    assert anchor.box == mask.bounds
    assert anchor.x_cm == pytest.approx(254.5 / PX)
    assert anchor.y_cm == pytest.approx(254.5 / PX)
    assert anchor.mask is mask
    assert not anchor.is_uncertain
    assert len(seg.prompts) == 1
    assert seg.prompts[0][0].box == PixelBox(180, 180, 320, 320)


def test_step2_histogram_accepts_low_iou() -> None:
    mask = mask_for(1, PixelBox(600, 400, 700, 500), 0.8)
    seg = FakeSegmenter([result(mask)])
    anchor = run(seg, [target()])[1]
    assert anchor.status is AnchorStatus.HISTOGRAM
    assert len(seg.prompts) == 1


def test_step2_histogram_rejects_goes_to_point() -> None:
    far = mask_for(1, PixelBox(600, 400, 1200, 500), 0.8)
    point = mask_for(1, PixelBox(210, 210, 300, 300), 0.7)
    seg = FakeSegmenter([result(far), result(point)])
    anchor = run(seg, [target()])[1]
    assert anchor.status is AnchorStatus.POINT
    assert len(seg.prompts) == 2
    retry = seg.prompts[1][0]
    assert retry.point == (250, 250)
    assert retry.box == PixelBox(180, 180, 320, 320)


def test_step3_low_confidence_and_missing_share_one_call() -> None:
    low = mask_for(1, PixelBox(205, 205, 305, 305), 0.2)
    point_one = mask_for(1, PixelBox(205, 205, 305, 305), 0.9)
    point_two = mask_for(2, PixelBox(205, 205, 305, 305), 0.9)
    seg = FakeSegmenter([result(low), result(point_one, point_two)])
    anchors = run(seg, [target(1), target(2, "mug")])
    assert anchors[1].status is AnchorStatus.POINT
    assert anchors[2].status is AnchorStatus.POINT
    assert len(seg.prompts) == 2
    assert [p.sam_id for p in seg.prompts[1]] == [1, 2]


def test_step4_concept_picks_closest_histogram_within_radius() -> None:
    worse = mask_for(7, PixelBox(220, 220, 340, 320), 0.9)
    better = mask_for(8, PixelBox(220, 220, 322, 320), 0.9)
    seg = FakeSegmenter([result(), result()], {"cup": result(worse, better)})
    anchor = run(seg, [target()])[1]
    assert anchor.status is AnchorStatus.CONCEPT
    assert anchor.sam_id == 1
    assert anchor.box == better.bounds
    assert seg.concept_labels == ["cup"]


def test_step4_radius_filter() -> None:
    far_x = 300 + int((RECOVERY_SEARCH_RADIUS_CM + 1) * PX)
    far = mask_for(7, PixelBox(far_x, 200, far_x + 100, 300), 0.9)
    seg = FakeSegmenter([result(), result()], {"cup": result(far)})
    anchor = run(seg, [target()])[1]
    assert anchor.status is AnchorStatus.UNCERTAIN


def test_step5_uncertain_without_concept_support() -> None:
    seg = FakeSegmenter([result(), result()])
    anchor = run(seg, [target()])[1]
    assert anchor.status is AnchorStatus.UNCERTAIN
    assert anchor.is_uncertain
    assert anchor.box == TRACKER_BOX
    assert anchor.mask is None
    assert anchor.x_cm == pytest.approx(250 / PX)


def test_one_concept_call_per_remaining_object() -> None:
    seg = FakeSegmenter([result(), result()], {"cup": result(), "mug": result()})
    anchors = run(seg, [target(1, "cup"), target(2, "mug")])
    assert seg.concept_labels == ["cup", "mug"]
    assert all(a.status is AnchorStatus.UNCERTAIN for a in anchors.values())


def test_unavailable_gives_tracker_anchors() -> None:
    seg = FakeSegmenter([], available=False)
    anchors = run(seg, [target(1), target(2)])
    assert all(a.status is AnchorStatus.TRACKER for a in anchors.values())
    assert all(a.is_uncertain for a in anchors.values())
    assert seg.prompts == []


@pytest.mark.parametrize("error", [SegmentationError("bad"), BreakerOpenError("open")])
def test_exceptions_give_tracker_anchors(error: Exception) -> None:
    seg = FakeSegmenter([], error=error)
    anchors = run(seg, [target()])
    assert anchors[1].status is AnchorStatus.TRACKER
    assert anchors[1].box == TRACKER_BOX


def test_empty_targets() -> None:
    assert run(FakeSegmenter([]), []) == {}


class SecondStageFails(FakeSegmenter):
    async def segment(
        self, image: Image, prompts: Sequence[ObjectPrompt]
    ) -> SegmentationResult:
        self.prompts.append(prompts)
        if len(self.prompts) > 1:
            raise SegmentationError("second stage down")
        return self.steps[0]


def test_failing_second_stage_keeps_first_stage_anchors() -> None:
    good = mask_for(1, PixelBox(205, 205, 305, 305), 0.9)
    seg = SecondStageFails([result(good)])
    anchors = run(seg, [target(1), target(2)])
    assert anchors[1].status is AnchorStatus.ACCEPTED
    assert anchors[2].status is AnchorStatus.UNCERTAIN


class ConceptFails(FakeSegmenter):
    async def _segment_concept(self, image: Image, label: str) -> SegmentationResult:
        raise SegmentationError("concept down")


def test_failing_concept_marks_only_that_object_uncertain() -> None:
    good = mask_for(1, PixelBox(205, 205, 305, 305), 0.9)
    seg = ConceptFails([result(good), result()], concept={})
    anchors = run(seg, [target(1), target(2)])
    assert anchors[1].status is AnchorStatus.ACCEPTED
    assert anchors[2].status is AnchorStatus.UNCERTAIN

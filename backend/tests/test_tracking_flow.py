import asyncio
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import numpy.typing as npt

from capture.camera import VideoSource
from capture.tracker import TrackerSet
from db.store import Store
from game.night import GameController
from rules.units import CardDraft, PowerId, UnitClass
from state import LiveState
from tests.test_night import CONTENT, ready_for_summon
from tests.test_server import SceneSource
from vision.sam import (
    ObjectMask,
    ObjectPrompt,
    PixelBox,
    SegmentationResult,
    TrackerOnlySegmenter,
)
from vision.summon import CardText, Detection, SummonPipeline

Image = npt.NDArray[np.uint8]
BOXES = [
    PixelBox(100, 100, 180, 180),
    PixelBox(400, 300, 460, 360),
    PixelBox(800, 500, 860, 560),
]


class SequenceDetector:
    is_available = True

    def __init__(self) -> None:
        self._boxes = iter(BOXES)

    async def detect(
        self, snapshot: Image, spoken_name: str, known: object
    ) -> Detection:
        return Detection(
            found_new=True,
            label=spoken_name.lower(),
            box=next(self._boxes),
            draft=CardDraft(UnitClass.FIGHTER, 0, 0, PowerId.P03),
            text=CardText(),
            source="spark",
        )


class ConfidentSegmenter:
    is_available = True

    def __init__(self, shift_px: int = 0, confidence: float = 0.9) -> None:
        self.calls = 0
        self._shift = shift_px
        self._confidence = confidence

    async def segment(
        self, image: Image, prompts: Sequence[ObjectPrompt]
    ) -> SegmentationResult:
        self.calls += 1
        masks: dict[int, ObjectMask] = {}
        for prompt in prompts:
            box = prompt.box
            moved = PixelBox(
                box.left + self._shift, box.top, box.right + self._shift, box.bottom
            )
            mask = np.ones((moved.height, moved.width), dtype=np.bool_)
            masks[prompt.sam_id] = ObjectMask(
                prompt.sam_id, self._confidence, moved, mask
            )
        return SegmentationResult(masks=masks)


class LostBackend:
    def init(self, frame: Image, box: tuple[int, int, int, int]) -> None:
        return None

    def update(self, frame: Image) -> tuple[bool, tuple[int, int, int, int]]:
        return False, (0, 0, 0, 0)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def controller_for(
    store: Store,
    segmenter: object,
    tracker_clock: FakeClock | None = None,
) -> GameController:
    def source(_: int) -> VideoSource:
        return SceneSource()

    def tracker_factory(px_per_cm: float, size: tuple[int, int]) -> TrackerSet:
        if tracker_clock is None:
            return TrackerSet(px_per_cm=px_per_cm, warped_size=size)
        return TrackerSet(
            px_per_cm=px_per_cm,
            warped_size=size,
            backend_factory=LostBackend,
            clock=tracker_clock,
        )

    detector = SequenceDetector()
    return GameController(
        store,
        LiveState(),
        has_api_key=True,
        camera_factory=source,
        sleep=lambda _: None,
        pipeline_factory=lambda _: SummonPipeline(
            detector, TrackerOnlySegmenter(), CONTENT
        ),
        segmenter_factory=lambda _: segmenter,  # type: ignore[arg-type,return-value]
        tracker_factory=tracker_factory,
    )


def summon_three(controller: GameController) -> None:
    ready_for_summon(controller)
    for name in ("Mug", "Stapler", "Phone"):
        asyncio.run(controller.summon(name))


def test_frames_carry_poses_for_every_unit(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    summon_three(controller)
    assert controller.wait_for_frame() is not None
    first = controller.render_frame(1)
    second = controller.render_frame(2)
    assert first is not None and second is not None
    assert [p.id for p in second.poses] == ["u_kubo", "u_2", "u_3"]
    kubo = second.poses[0]
    assert abs(kubo.x_cm - 7.0) < 1.5
    assert abs(kubo.y_cm - 7.0) < 1.5
    controller.close()
    store.close()


def test_reanchor_moves_units_and_saves_positions(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    segmenter = ConfidentSegmenter(shift_px=10)
    controller = controller_for(store, segmenter)
    summon_three(controller)
    anchors = asyncio.run(controller.reanchor_all())
    assert segmenter.calls == 1
    assert all(not anchor.is_uncertain for anchor in anchors.values())
    snapshot = controller.snapshot()
    assert snapshot.campaign is not None
    night = store.start_or_resume_night(snapshot.campaign.id)
    saved = {u.sam_object_id: u for u in store.night_units(night.id)}
    assert abs(saved[1].x_cm - anchors[1].x_cm) < 1e-9
    assert anchors[1].x_cm > 6.9
    controller.close()
    store.close()


def test_reanchor_without_sam_marks_units_uncertain(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, TrackerOnlySegmenter())
    summon_three(controller)
    anchors = asyncio.run(controller.reanchor_all())
    assert all(anchor.is_uncertain for anchor in anchors.values())
    assert controller.wait_for_frame() is not None
    controller.render_frame(1)
    frame = controller.render_frame(2)
    assert frame is not None
    assert all(pose.uncertain for pose in frame.poses)
    controller.close()
    store.close()


def test_lost_tracker_triggers_one_recovery_call(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    clock = FakeClock()
    segmenter = ConfidentSegmenter()
    controller = controller_for(store, segmenter, tracker_clock=clock)
    summon_three(controller)
    assert controller.wait_for_frame() is not None
    controller.render_frame(1)
    controller.render_frame(2)
    assert asyncio.run(controller.recover_lost_objects()) == 0
    clock.now = 6.0
    controller.render_frame(3)
    recovered = asyncio.run(controller.recover_lost_objects())
    assert recovered == 3
    assert segmenter.calls == 3
    controller.close()
    store.close()


def test_demo_safe_skips_between_turn_recovery(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    clock = FakeClock()
    segmenter = ConfidentSegmenter()
    controller = controller_for(store, segmenter, tracker_clock=clock)
    summon_three(controller)
    controller.set_demo_safe(True)
    assert controller.wait_for_frame() is not None
    controller.render_frame(1)
    controller.render_frame(2)
    clock.now = 6.0
    controller.render_frame(3)
    assert asyncio.run(controller.recover_lost_objects()) == 0
    assert segmenter.calls == 0
    anchors = asyncio.run(controller.reanchor_all())
    assert segmenter.calls == 1
    assert not anchors[1].is_uncertain
    controller.close()
    store.close()

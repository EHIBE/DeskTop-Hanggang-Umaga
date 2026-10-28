import statistics
import time

import cv2
import numpy as np
import pytest

from capture.tracker import IntBox, TrackerBackend, TrackerSet, kcf_backend
from config import (
    MAX_BETWEEN_TURN_SAM_CALLS,
    POSITION_EMA_ALPHA,
    TRACKER_LOSS_SAM_DELAY_S,
)
from vision.sam import Image, PixelBox

FULL = (1200, 800)
PX_PER_CM = 20.0
FAIL: tuple[bool, IntBox] = (False, (0, 0, 0, 0))


class ScriptedBackend:
    def __init__(self, script: list[tuple[bool, IntBox]]) -> None:
        self.script = script
        self.init_calls: list[IntBox] = []
        self.index = 0

    def init(self, frame: Image, box: IntBox) -> None:
        self.init_calls.append(box)

    def update(self, frame: Image) -> tuple[bool, IntBox]:
        step = self.script[min(self.index, len(self.script) - 1)]
        self.index += 1
        return step


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def blank(width: int = 1200, height: int = 800, value: int = 0) -> Image:
    return np.full((height, width, 3), value, dtype=np.uint8)


def make_set(
    backends: list[ScriptedBackend] | None = None,
    clock: Clock | None = None,
    size: tuple[int, int] = FULL,
) -> TrackerSet:
    queue = list(backends or [])

    def factory() -> TrackerBackend:
        if queue:
            return queue.pop(0)
        return ScriptedBackend([(True, (0, 0, 10, 10))])

    return TrackerSet(PX_PER_CM, size, factory, clock or Clock())


def test_reset_scales_boxes_and_starts_at_centre() -> None:
    backend = ScriptedBackend([(True, (64, 64, 32, 32))])
    tracker = make_set([backend])
    tracker.reset(blank(), {1: PixelBox(120, 120, 180, 180)})
    assert backend.init_calls == [(64, 64, 32, 32)]
    assert tracker.boxes() == {1: PixelBox(120, 120, 180, 180)}


def test_ema_smoothing_math() -> None:
    backend = ScriptedBackend([(True, (128, 64, 32, 32))])
    tracker = make_set([backend])
    tracker.reset(blank(), {1: PixelBox(120, 120, 180, 180)})
    pose = tracker.update(blank())[0]
    expected_x = POSITION_EMA_ALPHA * 270 + (1 - POSITION_EMA_ALPHA) * 150
    expected_y = POSITION_EMA_ALPHA * 150 + (1 - POSITION_EMA_ALPHA) * 150
    assert pose.x_cm == pytest.approx(expected_x / PX_PER_CM)
    assert pose.y_cm == pytest.approx(expected_y / PX_PER_CM)
    assert pose.box == PixelBox(240, 120, 300, 180)
    assert not pose.is_frozen
    assert pose.lost_for_s == 0.0


def test_freeze_then_unfreeze_with_fake_clock() -> None:
    clock = Clock()
    script = [(True, (64, 64, 32, 32)), FAIL, FAIL, (True, (66, 64, 32, 32))]
    tracker = make_set([ScriptedBackend(script)], clock)
    tracker.reset(blank(), {1: PixelBox(120, 120, 180, 180)})
    good = tracker.update(blank())[0]
    clock.now += 2.0
    frozen = tracker.update(blank())[0]
    assert frozen.is_frozen
    assert frozen.box == good.box
    assert (frozen.x_cm, frozen.y_cm) == (good.x_cm, good.y_cm)
    assert frozen.lost_for_s == 0.0
    clock.now += 3.0
    still = tracker.update(blank())[0]
    assert still.is_frozen
    assert still.lost_for_s == pytest.approx(3.0)
    clock.now += 0.5
    back = tracker.update(blank())[0]
    assert not back.is_frozen
    assert back.lost_for_s == 0.0


def test_degenerate_box_counts_as_failure() -> None:
    tracker = make_set([ScriptedBackend([(True, (10, 10, 0, 0))])])
    tracker.reset(blank(), {1: PixelBox(120, 120, 180, 180)})
    assert tracker.update(blank())[0].is_frozen


def test_box_is_clamped_to_frame() -> None:
    tracker = make_set([ScriptedBackend([(True, (600, 400, 100, 100))])])
    tracker.reset(blank(), {1: PixelBox(120, 120, 180, 180)})
    box = tracker.update(blank())[0].box
    assert box.right <= 1200
    assert box.bottom <= 800


def test_has_motion_on_synthetic_frames() -> None:
    tracker = make_set()
    tracker.reset(blank(), {1: PixelBox(10, 10, 60, 60)})
    assert not tracker.has_motion(blank())
    assert tracker.has_motion(blank(value=40))


def lost_set(count: int, clock: Clock) -> TrackerSet:
    script = [(True, (64, 64, 32, 32)), FAIL]
    tracker = make_set([ScriptedBackend(list(script)) for _ in range(count)], clock)
    tracker.reset(
        blank(), {i: PixelBox(120, 120, 180, 180) for i in range(1, count + 1)}
    )
    tracker.update(blank())
    tracker.update(blank())
    clock.now += TRACKER_LOSS_SAM_DELAY_S + 1
    return tracker


def test_recovery_needs_delay_and_stillness() -> None:
    clock = Clock()
    tracker = lost_set(1, clock)
    assert tracker.recovery_candidates() == [1]
    tracker.update(blank(value=90))
    assert tracker.recovery_candidates() == []
    tracker.update(blank(value=90))
    assert tracker.recovery_candidates() == [1]


def test_recovery_not_before_delay() -> None:
    clock = Clock()
    tracker = make_set([ScriptedBackend([FAIL])], clock)
    tracker.reset(blank(), {1: PixelBox(120, 120, 180, 180)})
    tracker.update(blank())
    clock.now += TRACKER_LOSS_SAM_DELAY_S - 0.1
    assert tracker.recovery_candidates() == []


def test_recovery_budget_and_new_turn() -> None:
    clock = Clock()
    tracker = lost_set(MAX_BETWEEN_TURN_SAM_CALLS + 2, clock)
    first = tracker.recovery_candidates()
    assert len(first) == MAX_BETWEEN_TURN_SAM_CALLS
    for sam_id in first:
        tracker.mark_recovery_used(sam_id)
    assert tracker.recovery_candidates() == []
    tracker.new_turn()
    assert len(tracker.recovery_candidates()) == MAX_BETWEEN_TURN_SAM_CALLS


def test_relock_reinitialises_and_unfreezes() -> None:
    clock = Clock()
    replacement = ScriptedBackend([(True, (100, 100, 20, 20))])
    created: list[ScriptedBackend] = [
        ScriptedBackend([(True, (64, 64, 32, 32)), FAIL]),
        replacement,
    ]
    tracker = make_set(created, clock)
    tracker.reset(blank(), {1: PixelBox(120, 120, 180, 180)})
    tracker.update(blank())
    assert tracker.update(blank())[0].is_frozen
    tracker.relock(1, blank(), PixelBox(600, 400, 700, 500))
    assert replacement.init_calls == [(320, 213, 53, 53)]
    assert tracker.boxes()[1] == PixelBox(600, 400, 700, 500)
    assert not tracker.update(blank())[0].is_frozen


def test_remove() -> None:
    tracker = make_set()
    tracker.reset(
        blank(), {1: PixelBox(10, 10, 60, 60), 2: PixelBox(100, 100, 160, 160)}
    )
    tracker.remove(1)
    tracker.remove(9)
    assert list(tracker.boxes()) == [2]
    assert [p.sam_id for p in tracker.update(blank())] == [2]


@pytest.mark.parametrize("width,height", [(640, 427), (1200, 800)])
def test_scaling_between_sizes(width: int, height: int) -> None:
    scale = 640 / width
    box = PixelBox(width // 4, height // 4, width // 2, height // 2)
    expected = (
        round(box.left * scale),
        round(box.top * scale),
        round(box.width * scale),
        round(box.height * scale),
    )
    backend = ScriptedBackend([(True, expected)])
    tracker = make_set([backend], size=(width, height))
    frame = blank(width, height)
    tracker.reset(frame, {1: box})
    assert backend.init_calls == [expected]
    pose = tracker.update(frame)[0]
    assert abs(pose.box.left - box.left) <= 2
    assert abs(pose.box.right - box.right) <= 2


def textured_scene(offset_x: int) -> Image:
    rng = np.random.default_rng(3)
    noise = rng.integers(0, 90, (800, 1200, 3), dtype=np.uint8)
    frame = np.asarray(cv2.GaussianBlur(noise, (0, 0), 3), dtype=np.uint8)
    frame[300:360, offset_x : offset_x + 60] = rng.integers(
        0, 255, (60, 60, 3), dtype=np.uint8
    )
    return frame


def test_real_kcf_follows_moving_square() -> None:
    tracker = TrackerSet(PX_PER_CM, FULL, kcf_backend)
    start = 200
    tracker.reset(textured_scene(start), {1: PixelBox(start, 300, start + 60, 360)})
    pose = tracker.update(textured_scene(start))[0]
    for step in range(1, 11):
        pose = tracker.update(textured_scene(start + step * 6))[0]
    assert not pose.is_frozen
    assert abs(pose.x_cm - (start + 60 + 30) / PX_PER_CM) <= 2.0
    assert abs(pose.y_cm - 330 / PX_PER_CM) <= 2.0


def test_benchmark_twelve_kcf_trackers() -> None:
    rng = np.random.default_rng(7)
    noise = rng.integers(0, 255, (800, 1200, 3), dtype=np.uint8)
    base = np.asarray(cv2.GaussianBlur(noise, (0, 0), 2), dtype=np.uint8)
    boxes = {
        i + 1: PixelBox(
            40 + (i % 6) * 190,
            80 + (i // 6) * 340,
            130 + (i % 6) * 190,
            170 + (i // 6) * 340,
        )
        for i in range(12)
    }
    tracker = TrackerSet(PX_PER_CM, FULL, kcf_backend)
    tracker.reset(base, boxes)
    durations: list[float] = []
    for step in range(15):
        frame = np.roll(base, step, axis=1)
        started = time.perf_counter()
        tracker.update(frame)
        durations.append(time.perf_counter() - started)
    median_s = statistics.median(durations[3:])
    print(f"median 12-tracker update: {median_s * 1000:.1f} ms")
    assert median_s < 0.1

import asyncio
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt
import pytest

from capture.camera import VideoSource, list_microphones
from db.store import Store
from game.night import AppPhase, FramePump, GameController, GameError
from gm.schemas import ContentFilter
from rules.units import CardDraft, Difficulty, PowerId, UnitClass
from state import FrameView, LiveState
from tests.test_server import SCENE, SHEET, SceneSource
from vision.sam import PixelBox, TrackerOnlySegmenter
from vision.sprites import GeneratedSprite, SpriteJob, SpriteService
from vision.summon import CardText, Detection, FallbackDetector, SummonPipeline

Image = npt.NDArray[np.uint8]
CONTENT = ContentFilter.from_data_dir()


class ShiftedSource(SceneSource):
    def read(self) -> tuple[bool, Image | None]:
        matrix = np.array([[1.0, 0.0, 120.0], [0.0, 1.0, 0.0]])
        moved = cv2.warpAffine(
            SCENE, matrix, (1920, 1080), borderMode=cv2.BORDER_REFLECT
        )
        return True, np.asarray(moved, dtype=np.uint8)


def controller_with(store: Store, source: type[SceneSource]) -> GameController:
    def factory(_: int) -> VideoSource:
        return source()

    return GameController(store, LiveState(), has_api_key=True, camera_factory=factory)


def calibrate_campaign(store: Store) -> str:
    controller = controller_with(store, SceneSource)
    controller.start_new_campaign("Barkada", Difficulty.NORMAL)
    controller.select_camera(0)
    controller.submit_corners(SHEET, 60.0, 40.0)
    controller.confirm_calibration()
    snapshot = controller.snapshot()
    controller.close()
    assert snapshot.phase is AppPhase.SUMMON
    assert snapshot.campaign is not None
    return snapshot.campaign.id


def test_continue_with_unmoved_camera_skips_calibration(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    campaign_id = calibrate_campaign(store)
    controller = controller_with(store, SceneSource)
    controller.continue_campaign(campaign_id)
    assert controller.snapshot().phase is AppPhase.CALIBRATE
    controller.select_camera(0)
    assert controller.snapshot().phase is AppPhase.SUMMON
    controller.close()
    store.close()


def test_continue_with_moved_camera_asks_to_recalibrate(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    campaign_id = calibrate_campaign(store)
    controller = controller_with(store, ShiftedSource)
    controller.continue_campaign(campaign_id)
    with pytest.raises(GameError) as info:
        controller.select_camera(0)
    assert info.value.copy_key == "cam.moved"
    assert controller.snapshot().phase is AppPhase.CALIBRATE
    controller.restart_calibration()
    assert controller.snapshot().is_previewing is False
    controller.close()
    store.close()


def test_confirm_without_corners_is_rejected(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_with(store, SceneSource)
    controller.start_new_campaign("B", Difficulty.MADALI)
    with pytest.raises(GameError):
        controller.confirm_calibration()
    controller.close()
    store.close()


def test_frame_pump_publishes_raw_then_warped(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    live = LiveState()

    def factory(_: int) -> VideoSource:
        return SceneSource()

    controller = GameController(store, live, has_api_key=False, camera_factory=factory)
    pump = FramePump(controller, live)
    assert not pump.pump_once(1)
    controller.start_new_campaign("B", Difficulty.NORMAL)
    controller.select_camera(0)
    controller.submit_corners(SHEET, 60.0, 40.0)
    assert controller.wait_for_frame() is not None
    assert pump.pump_once(2)
    frame = live.latest()
    assert frame is not None
    assert frame.view is FrameView.WARPED
    assert (frame.width, frame.height) == (1200, 800)
    controller.close()
    store.close()


def test_list_microphones_keeps_input_devices_only() -> None:
    devices: list[dict[str, object]] = [
        {"name": "Speakers", "max_input_channels": 0},
        {"name": "Mic", "max_input_channels": 2},
        {"name": "Odd", "max_input_channels": "2"},
    ]
    found = list_microphones(lambda: devices)
    assert [(m.index, m.name) for m in found] == [(1, "Mic")]


def test_missing_baseline_file_asks_to_recalibrate(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    campaign_id = calibrate_campaign(store)
    stored = store.latest_calibration(campaign_id)
    assert stored is not None
    stored.baseline_path.unlink()
    controller = controller_with(store, SceneSource)
    controller.continue_campaign(campaign_id)
    with pytest.raises(GameError) as info:
        controller.select_camera(0)
    assert info.value.copy_key == "cam.moved"
    controller.close()
    store.close()


def test_camera_change_during_unsaved_preview_keeps_calibrating(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_with(store, SceneSource)
    controller.start_new_campaign("B", Difficulty.NORMAL)
    controller.select_camera(0)
    controller.submit_corners(SHEET, 60.0, 40.0)
    controller.select_camera(1)
    snapshot = controller.snapshot()
    assert snapshot.phase is AppPhase.CALIBRATE
    assert snapshot.is_previewing
    assert (
        store.latest_calibration(snapshot.campaign.id if snapshot.campaign else "")
        is None
    )
    controller.close()
    store.close()


def spark_controller(store: Store, boxes: list[PixelBox]) -> GameController:
    detections = iter(boxes)

    class SequenceDetector:
        is_available = True

        async def detect(
            self, snapshot: Image, spoken_name: str, known: object
        ) -> Detection:
            return Detection(
                found_new=True,
                label=spoken_name.lower(),
                box=next(detections, boxes[-1]),
                draft=CardDraft(UnitClass.REACH, 0, 0, PowerId.P04),
                text=CardText("Tigil", "Hinto", "Stops", spoken_name),
                source="spark",
            )

    def factory(_: bool) -> SummonPipeline:
        return SummonPipeline(SequenceDetector(), TrackerOnlySegmenter(), CONTENT)

    def source(_: int) -> VideoSource:
        return SceneSource()

    return GameController(
        store,
        LiveState(),
        has_api_key=True,
        camera_factory=source,
        sleep=lambda _: None,
        pipeline_factory=factory,
    )


def ready_for_summon(controller: GameController) -> None:
    controller.start_new_campaign("B", Difficulty.NORMAL)
    controller.select_camera(0)
    controller.submit_corners(SHEET, 60.0, 40.0)
    controller.confirm_calibration()


def test_summons_reroll_and_rename(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    boxes = [
        PixelBox(100, 100, 180, 180),
        PixelBox(400, 300, 460, 360),
        PixelBox(800, 500, 860, 560),
    ]
    controller = spark_controller(store, boxes)
    ready_for_summon(controller)
    kubo = asyncio.run(controller.summon("Mug"))
    assert kubo.card.unit_class is UnitClass.KUBO
    asyncio.run(controller.summon("Pen"))
    pencil = asyncio.run(controller.summon("Lapis"))
    assert pencil.card.unit_class is UnitClass.REACH
    assert controller.snapshot().begin_block_key is None
    rerolled = asyncio.run(controller.reroll_unit(pencil.unit_id))
    assert rerolled.rerolls_left == 0
    with pytest.raises(GameError):
        asyncio.run(controller.reroll_unit(pencil.unit_id))
    bad = (
        Path("gm/data/blocklist_en.txt")
        .read_text(encoding="utf-8")
        .splitlines()[0]
        .strip()
    )
    renamed = controller.rename_unit(pencil.unit_id, bad, CONTENT.clean_player_name)
    assert renamed.card.name == "Reach"
    snapshot = controller.snapshot()
    assert [u.game_id for u in snapshot.units] == ["u_kubo", "u_2", "u_3"]
    controller.log_invalid("SchemaError")
    assert snapshot.campaign is not None
    night = store.start_or_resume_night(snapshot.campaign.id)
    assert store.turn_log_count(night.id, "gm_invalid") == 1
    assert store.turn_log_count(night.id, "summon") == 3
    controller.close()
    store.close()


def test_resume_reloads_units_and_rerolls(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = spark_controller(
        store, [PixelBox(100, 100, 180, 180), PixelBox(400, 300, 460, 360)]
    )
    ready_for_summon(controller)
    asyncio.run(controller.summon("Mug"))
    pen = asyncio.run(controller.summon("Pen"))
    asyncio.run(controller.reroll_unit(pen.unit_id))
    campaign = controller.snapshot().campaign
    controller.close()
    assert campaign is not None
    again = spark_controller(store, [PixelBox(700, 300, 760, 360)])
    again.continue_campaign(campaign.id)
    again.select_camera(0)
    units = again.snapshot().units
    assert [u.card.name for u in units] == ["Mug", "Pen"]
    assert units[1].rerolls_left == 0
    again.close()
    store.close()


def test_summon_outside_summon_phase_is_rejected(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = spark_controller(store, [PixelBox(100, 100, 180, 180)])
    with pytest.raises(GameError):
        asyncio.run(controller.summon("Mug"))
    controller.close()
    store.close()


def test_reroll_respects_caps_counting_later_units(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    boxes = [PixelBox(100 + 150 * i, 100, 160 + 150 * i, 160) for i in range(5)]
    classes = iter(
        [
            UnitClass.KUBO,
            UnitClass.FIGHTER,
            UnitClass.CHARM,
            UnitClass.CHARM,
            UnitClass.CHARM,
        ]
    )
    box_iter = iter(boxes)

    class ClassDetector:
        is_available = True

        async def detect(
            self, snapshot: Image, spoken_name: str, known: object
        ) -> Detection:
            return Detection(
                found_new=True,
                label=spoken_name,
                box=next(box_iter, boxes[-1]),
                draft=CardDraft(next(classes), 0, 0, PowerId.P06),
                text=CardText(),
                source="spark",
            )

    def source(_: int) -> VideoSource:
        return SceneSource()

    controller = GameController(
        store,
        LiveState(),
        has_api_key=True,
        camera_factory=source,
        sleep=lambda _: None,
        pipeline_factory=lambda _: SummonPipeline(
            ClassDetector(), TrackerOnlySegmenter(), CONTENT
        ),
    )
    ready_for_summon(controller)
    asyncio.run(controller.summon("Mug"))
    fighter = asyncio.run(controller.summon("Stapler"))
    asyncio.run(controller.summon("Coin"))
    asyncio.run(controller.summon("Ring"))
    rerolled = asyncio.run(controller.reroll_unit(fighter.unit_id))
    assert rerolled.card.unit_class is UnitClass.FIGHTER
    charms = [
        u for u in controller.snapshot().units if u.card.unit_class is UnitClass.CHARM
    ]
    assert len(charms) == 2
    controller.close()
    store.close()


def test_new_summon_clears_a_stale_tap_request(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")

    def source(_: int) -> VideoSource:
        return SceneSource()

    controller = GameController(
        store,
        LiveState(),
        has_api_key=False,
        camera_factory=source,
        sleep=lambda _: None,
        pipeline_factory=lambda _: SummonPipeline(
            FallbackDetector(), TrackerOnlySegmenter(), CONTENT
        ),
    )
    ready_for_summon(controller)
    with pytest.raises(GameError):
        asyncio.run(controller.summon("Bantay"))
    assert controller.snapshot().is_awaiting_tap
    with pytest.raises(GameError):
        asyncio.run(controller.summon("Lampara"))
    unit = asyncio.run(controller.summon_tap((600, 400)))
    assert unit.card.name == "Lampara"
    controller.close()
    store.close()


def test_stale_sprite_job_does_not_overwrite_a_newer_one(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    release = asyncio.Event()

    class SlowFirstPenGenerator:
        is_available = True

        def __init__(self) -> None:
            self.has_blocked = False

        async def generate(
            self, job: SpriteJob, style_anchor_png: bytes | None
        ) -> GeneratedSprite:
            if job.unit_name == "Pen" and not self.has_blocked:
                self.has_blocked = True
                await release.wait()
                return GeneratedSprite(png=b"stale", response_id=None)
            return GeneratedSprite(
                png=f"{job.unit_name}-{job.unit_class}".encode(), response_id=None
            )

    generator = SlowFirstPenGenerator()
    classes = iter([UnitClass.KUBO, UnitClass.REACH, UnitClass.FIGHTER])
    boxes = iter([PixelBox(100, 100, 180, 180), PixelBox(400, 300, 460, 360)])

    class ChangingDetector:
        is_available = True

        async def detect(
            self, snapshot: Image, spoken_name: str, known: object
        ) -> Detection:
            return Detection(
                found_new=True,
                label=spoken_name,
                box=next(boxes, PixelBox(700, 300, 760, 360)),
                draft=CardDraft(next(classes), 0, 0, PowerId.P03),
                text=CardText(),
                source="spark",
            )

    def source(_: int) -> VideoSource:
        return SceneSource()

    controller = GameController(
        store,
        LiveState(),
        has_api_key=True,
        camera_factory=source,
        sleep=lambda _: None,
        pipeline_factory=lambda _: SummonPipeline(
            ChangingDetector(), TrackerOnlySegmenter(), CONTENT
        ),
        sprite_service_factory=lambda _: SpriteService(store, generator),
    )

    async def scenario() -> str:
        ready_for_summon(controller)
        await controller.summon("Mug")
        pen = await controller.summon("Pen")
        await asyncio.sleep(0)
        await controller.reroll_unit(pen.unit_id)
        release.set()
        await controller.wait_for_sprites()
        return pen.unit_id

    pen_id = asyncio.run(scenario())
    view = next(u for u in controller.snapshot().units if u.unit_id == pen_id)
    assert view.sprite_png is not None
    assert view.sprite_png != "c3RhbGU="
    controller.close()
    store.close()

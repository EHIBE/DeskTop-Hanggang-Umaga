import asyncio
import json
from collections.abc import Sequence
from decimal import Decimal

import numpy as np
import numpy.typing as npt
import pytest

from gm.schemas import DATA_DIR, ContentFilter
from meta_client import CostMeter, MetaClient, create_openai_client
from rules.units import CardDraft, Difficulty, PowerId, UnitClass
from tests.test_meta_client import MemoryLog
from vision.sam import ObjectMask, ObjectPrompt, PixelBox, SegmentationResult
from vision.summon import (
    CardText,
    Detection,
    FallbackDetector,
    KnownObject,
    SparkDetector,
    SummonError,
    SummonOutcome,
    SummonPipeline,
    SummonRequest,
    tap_box,
    to_grid,
)

Image = npt.NDArray[np.uint8]
CONTENT = ContentFilter.from_data_dir()


def first_line(name: str) -> str:
    return next(
        line.strip()
        for line in (DATA_DIR / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def frame() -> Image:
    image = np.full((800, 1200, 3), 60, dtype=np.uint8)
    image[300:400, 500:600] = (30, 120, 220)
    image[100:160, 100:160] = (200, 60, 40)
    return image


class FixedDetector:
    def __init__(self, detection: Detection, is_available: bool = True) -> None:
        self._detection = detection
        self._is_available = is_available
        self.calls = 0

    @property
    def is_available(self) -> bool:
        return self._is_available

    async def detect(
        self, snapshot: Image, spoken_name: str, known: Sequence[KnownObject]
    ) -> Detection:
        self.calls += 1
        return self._detection


class FakeSegmenter:
    def __init__(self, is_available: bool = True) -> None:
        self._is_available = is_available
        self.prompts: list[ObjectPrompt] = []

    @property
    def is_available(self) -> bool:
        return self._is_available

    async def segment(
        self, image: Image, prompts: Sequence[ObjectPrompt]
    ) -> SegmentationResult:
        self.prompts = list(prompts)
        masks = {
            p.sam_id: ObjectMask(
                p.sam_id,
                0.9,
                p.box,
                np.ones((p.box.height, p.box.width), dtype=np.bool_),
            )
            for p in prompts
        }
        return SegmentationResult(masks=masks)


def spark_detection(
    box: PixelBox | None, unit_class: UnitClass = UnitClass.HEALER
) -> Detection:
    return Detection(
        found_new=box is not None,
        label="keys",
        box=box,
        draft=CardDraft(unit_class, 1, 1, PowerId.P01),
        text=CardText("Gamot", "Hilot", "Heals", "keys"),
        source="spark",
    )


def request(
    known: tuple[KnownObject, ...] = (),
    name: str = "Albularyo",
    tap: tuple[int, int] | None = None,
) -> SummonRequest:
    return SummonRequest(
        snapshot=frame(),
        spoken_name=name,
        known=known,
        difficulty=Difficulty.NORMAL,
        px_per_cm=20.0,
        tap_point=tap,
    )


def run_pipeline(pipeline: SummonPipeline, req: SummonRequest) -> SummonOutcome:
    async def go() -> SummonOutcome:
        detection = await pipeline.detect(req)
        return await pipeline.run(req, detection)

    return asyncio.run(go())


KUBO = KnownObject(1, "mug", UnitClass.KUBO, PixelBox(100, 100, 160, 160))


def test_first_summon_becomes_the_kubo_in_slot_1() -> None:
    pipeline = SummonPipeline(
        FixedDetector(spark_detection(PixelBox(500, 300, 600, 400))),
        FakeSegmenter(),
        CONTENT,
    )
    outcome = run_pipeline(pipeline, request(name="Bahay Kubo"))
    assert outcome.sam_id == 1
    assert outcome.card.unit_class is UnitClass.KUBO
    assert outcome.card.hp_max == 10
    assert outcome.x_cm == pytest.approx(27.475, abs=0.01)
    assert outcome.y_cm == pytest.approx(17.475, abs=0.01)
    assert outcome.name == "Bahay Kubo"


def test_later_summon_is_clamped_and_segments_every_object() -> None:
    segmenter = FakeSegmenter()
    pipeline = SummonPipeline(
        FixedDetector(spark_detection(PixelBox(500, 300, 600, 400))), segmenter, CONTENT
    )
    outcome = run_pipeline(pipeline, request(known=(KUBO,)))
    assert outcome.sam_id == 2
    assert outcome.card.unit_class is UnitClass.HEALER
    assert (outcome.card.hp_delta, outcome.card.atk_delta) == (1, -1)
    assert [p.sam_id for p in segmenter.prompts] == [1, 2]
    assert set(outcome.known_masks) == {1}
    assert outcome.signature.signature.area_cm2 == pytest.approx(25.0)
    assert outcome.text.power_name_tl == "Gamot"


def test_unclear_object_asks_for_a_tap() -> None:
    pipeline = SummonPipeline(
        FixedDetector(spark_detection(None)), FakeSegmenter(), CONTENT
    )
    with pytest.raises(SummonError) as info:
        run_pipeline(pipeline, request(known=(KUBO,)))
    assert info.value.copy_key == "summon.which"


def test_tap_path_uses_a_box_around_the_point_and_keeps_the_prior_card() -> None:
    detector = FixedDetector(spark_detection(None))
    segmenter = FakeSegmenter()
    pipeline = SummonPipeline(detector, segmenter, CONTENT)
    prior = spark_detection(None)
    req = SummonRequest(
        frame(),
        "Albularyo",
        (KUBO,),
        Difficulty.NORMAL,
        20.0,
        tap_point=(550, 350),
        prior=prior,
    )
    outcome = run_pipeline(pipeline, req)
    assert detector.calls == 0
    assert outcome.card.unit_class is UnitClass.HEALER
    assert segmenter.prompts[-1].point == (550, 350)
    assert segmenter.prompts[-1].box == PixelBox(490, 290, 610, 410)


def test_stacked_object_is_refused() -> None:
    pipeline = SummonPipeline(
        FixedDetector(spark_detection(PixelBox(105, 105, 160, 160))),
        FakeSegmenter(),
        CONTENT,
    )
    with pytest.raises(SummonError) as info:
        run_pipeline(pipeline, request(known=(KUBO,)))
    assert info.value.copy_key == "summon.stack"


def test_thirteenth_object_is_refused() -> None:
    known = tuple(
        KnownObject(
            i,
            "x",
            UnitClass.KUBO if i == 1 else UnitClass.FIGHTER,
            PixelBox(i * 80, 600, i * 80 + 20, 620),
        )
        for i in range(1, 13)
    )
    pipeline = SummonPipeline(
        FixedDetector(spark_detection(PixelBox(500, 300, 600, 400))),
        FakeSegmenter(),
        CONTENT,
    )
    with pytest.raises(SummonError) as info:
        run_pipeline(pipeline, request(known=known))
    assert info.value.copy_key == "summon.full"


def test_without_sam_the_box_becomes_the_mask() -> None:
    pipeline = SummonPipeline(
        FixedDetector(spark_detection(PixelBox(500, 300, 600, 400))),
        FakeSegmenter(is_available=False),
        CONTENT,
    )
    outcome = run_pipeline(pipeline, request(known=(KUBO,)))
    assert outcome.mask.confidence is None
    assert outcome.mask.bounds == PixelBox(500, 300, 600, 400)
    assert outcome.known_masks == {}


def test_offline_detector_falls_back_and_default_card_is_used() -> None:
    pipeline = SummonPipeline(
        FixedDetector(spark_detection(None), is_available=False),
        FakeSegmenter(),
        CONTENT,
    )
    detection = asyncio.run(pipeline.detect(request(known=(KUBO,))))
    assert detection.source == "fallback"
    tapped = SummonRequest(
        frame(),
        "Pen",
        (KUBO,),
        Difficulty.NORMAL,
        20.0,
        tap_point=(550, 350),
        prior=detection,
    )
    outcome = run_pipeline(pipeline, tapped)
    assert outcome.card.unit_class is UnitClass.FIGHTER
    assert outcome.source == "fallback"


def test_profane_name_becomes_the_class_name() -> None:
    bad_word = first_line("blocklist_en.txt")
    pipeline = SummonPipeline(
        FixedDetector(spark_detection(PixelBox(500, 300, 600, 400))),
        FakeSegmenter(),
        CONTENT,
    )
    outcome = run_pipeline(pipeline, request(known=(KUBO,), name=bad_word))
    assert outcome.name == "Healer"


def test_grid_and_tap_box_helpers() -> None:
    assert to_grid(PixelBox(600, 400, 1200, 800), 1200, 800) == (500, 500, 1000, 1000)
    assert tap_box((5, 5), 20.0, 1200, 800) == PixelBox(0, 0, 65, 65)


def card_json(
    found_new: bool = True, power: str = "P01", text_tl: str = "Hilot at dasal"
) -> str:
    return json.dumps(
        {
            "detected": {
                "found_new": found_new,
                "label": "keys",
                "box": {"x1": 400, "y1": 375, "x2": 500, "y2": 500},
                "matches_known_id": None,
            },
            "card": {
                "class": "healer",
                "hp_delta": 0,
                "atk_delta": 0,
                "power_id": power,
                "power_name_tl": "Gamot",
                "card_text_tl": text_tl,
                "card_text_en": "Heals an ally.",
                "sprite_subject_en": "a ring of keys",
            },
        }
    )


def spark_with_answers(answers: list[str], invalid: list[str]) -> SparkDetector:
    client = MetaClient(
        create_openai_client("test-key"),
        CostMeter(MemoryLog(starting_total=Decimal(0))),
    )
    detector = SparkDetector(client, CONTENT, invalid.append)

    async def scripted_ask(
        image_url: str, prompt: str, schema: dict[str, object]
    ) -> str:
        return answers.pop(0)

    detector._ask = scripted_ask  # type: ignore[method-assign]
    return detector


def test_spark_detection_converts_the_box_and_card() -> None:
    invalid: list[str] = []
    detector = spark_with_answers([card_json()], invalid)
    detection = asyncio.run(detector.detect(frame(), "Albularyo", [KUBO]))
    assert detection.found_new
    assert detection.box == PixelBox(480, 300, 600, 400)
    assert detection.draft == CardDraft(UnitClass.HEALER, 0, 0, PowerId.P01)
    assert detection.text.card_text_tl == "Hilot at dasal"
    assert invalid == []


def test_spark_repairs_once_then_falls_back() -> None:
    invalid: list[str] = []
    repaired = spark_with_answers(["{}", card_json()], invalid)
    assert asyncio.run(repaired.detect(frame(), "x", [])).source == "spark"
    assert len(invalid) == 1
    failing = spark_with_answers(["{}", "not json"], invalid)
    detection = asyncio.run(failing.detect(frame(), "x", []))
    assert detection.source == "fallback"
    assert len(invalid) == 3


def test_unsafe_card_text_is_dropped() -> None:
    place = first_line("ph_places.txt")
    detector = spark_with_answers([card_json(text_tl=f"Aswang galing {place}")], [])
    detection = asyncio.run(detector.detect(frame(), "x", []))
    assert detection.text.card_text_tl == ""
    assert detection.text.sprite_subject_en == "a ring of keys"


def test_fallback_detector_never_finds_an_object() -> None:
    detection = asyncio.run(FallbackDetector().detect(frame(), "x", []))
    assert not detection.found_new
    assert detection.source == "fallback"

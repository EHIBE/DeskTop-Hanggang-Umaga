import asyncio
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import numpy.typing as npt
import pytest

from db.store import Store, UnitPlacement
from meta_client import (
    CostMeter,
    MetaClient,
    MetaRequestError,
    MetaUnavailableError,
    create_openai_client,
)
from rules.units import Difficulty
from tests.test_meta_client import MemoryLog
from tests.test_store import SIGNATURE, card_fields
from vision.sam import ObjectMask, PixelBox, SegmentationResult
from vision.sprites import (
    GREEN_KEY,
    MAGENTA_KEY,
    GeneratedSprite,
    MuseImageGenerator,
    PlaceholderGenerator,
    SpriteError,
    SpriteJob,
    SpriteService,
    decode_png,
    encode_png,
    image_payload,
)

Image = npt.NDArray[np.uint8]
Color = tuple[int, int, int]


def generated_image(key: Color) -> Image:
    image = np.zeros((1024, 1024, 3), dtype=np.uint8)
    image[:] = key
    cv2.circle(image, (512, 512), 300, (46, 90, 168), -1)
    cv2.circle(image, (512, 512), 120, (232, 238, 247), -1)
    return image


def flat_image(key: Color) -> Image:
    image = np.zeros((1024, 1024, 3), dtype=np.uint8)
    image[:] = key
    return image


def job(
    unit_id: str = "u", campaign_id: str = "c", signature_id: str = "s"
) -> SpriteJob:
    crop = np.full((512, 512, 3), 128, dtype=np.uint8)
    crop[100:400, 100:400] = (46, 90, 168)
    return SpriteJob(
        unit_id, campaign_id, signature_id, "Mug", "kubo", "a blue mug", crop
    )


class ScriptedGenerator(MuseImageGenerator):
    def __init__(
        self, results: list[Image | BaseException], segmenter: object = None
    ) -> None:
        client = MetaClient(
            create_openai_client("test-key"),
            CostMeter(MemoryLog(starting_total=Decimal(0))),
        )
        super().__init__(client, segmenter)  # type: ignore[arg-type]
        self.results = results
        self.calls: list[Color] = []

    async def _call(
        self,
        job: SpriteJob,
        crop_png: bytes,
        key: Color,
        style_anchor_png: bytes | None,
    ) -> tuple[bytes, str | None]:
        self.calls.append(key)
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return encode_png(result), "resp_1"


def test_valid_first_try_returns_a_48px_sprite() -> None:
    generator = ScriptedGenerator([generated_image(MAGENTA_KEY)])
    sprite = asyncio.run(generator.generate(job(), None))
    assert sprite is not None
    assert decode_png(sprite.png).shape == (48, 48, 4)
    assert sprite.response_id == "resp_1"


def test_failed_key_retries_with_the_other_color() -> None:
    generator = ScriptedGenerator([flat_image(MAGENTA_KEY), generated_image(GREEN_KEY)])
    assert asyncio.run(generator.generate(job(), None)) is not None
    assert generator.calls == [MAGENTA_KEY, GREEN_KEY]


def test_content_policy_keeps_the_placeholder_without_retry() -> None:
    generator = ScriptedGenerator([MetaRequestError("blocked", is_content_policy=True)])
    assert asyncio.run(generator.generate(job(), None)) is None
    assert len(generator.calls) == 1


def test_outage_keeps_the_placeholder() -> None:
    generator = ScriptedGenerator([MetaUnavailableError("down")])
    assert asyncio.run(generator.generate(job(), None)) is None


class CutoutSegmenter:
    is_available = True

    async def segment_concept(self, image: Image, label: str) -> SegmentationResult:
        local = np.zeros((600, 600), dtype=np.uint8)
        cv2.circle(local, (300, 300), 250, 1, -1)
        mask = ObjectMask(1, 0.9, PixelBox(212, 212, 812, 812), local.astype(np.bool_))
        return SegmentationResult({1: mask})


def test_both_keys_fail_then_sam_cutout_rescues() -> None:
    no_object = ScriptedGenerator(
        [flat_image(MAGENTA_KEY), flat_image(GREEN_KEY)], CutoutSegmenter()
    )
    assert asyncio.run(no_object.generate(job(), None)) is None
    halo = flat_image(GREEN_KEY)
    cv2.circle(halo, (512, 512), 250, (46, 90, 168), -1)
    cv2.circle(halo, (512, 512), 100, (232, 238, 247), -1)
    halo[:, :, 1] = np.where(halo[:, :, 1] == 255, 200, halo[:, :, 1])
    rescued = ScriptedGenerator([flat_image(MAGENTA_KEY), halo], CutoutSegmenter())
    assert asyncio.run(rescued.generate(job(), None)) is not None


def test_image_payload_parsing() -> None:
    good = SimpleNamespace(
        id="r1",
        output=[
            SimpleNamespace(type="message"),
            SimpleNamespace(type="image_generation_call", result="iVBORw0KGgo="),
        ],
    )
    data, response_id = image_payload(good)
    assert data.startswith(b"\x89PNG")
    assert response_id == "r1"
    with pytest.raises(SpriteError):
        image_payload(SimpleNamespace(output=[]))
    with pytest.raises(SpriteError):
        image_payload(
            SimpleNamespace(
                output=[SimpleNamespace(type="image_generation_call", result="***")]
            )
        )


class CountingGenerator:
    def __init__(self, available: bool = True) -> None:
        self.calls = 0
        self.anchors: list[bytes | None] = []
        self._available = available

    @property
    def is_available(self) -> bool:
        return self._available

    async def generate(
        self, job: SpriteJob, style_anchor_png: bytes | None
    ) -> GeneratedSprite | None:
        self.calls += 1
        self.anchors.append(style_anchor_png)
        return GeneratedSprite(png=f"png-{self.calls}".encode(), response_id=None)


def unit_in(store: Store) -> tuple[str, str, str]:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    night = store.start_or_resume_night(campaign.id)
    unit = store.add_unit(night, card_fields(), SIGNATURE, UnitPlacement(1, 30.0, 20.0))
    return campaign.id, unit.unit_id, unit.signature_id


def test_service_generates_caches_and_sets_the_style_anchor(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    campaign_id, unit_id, signature_id = unit_in(store)
    generator = CountingGenerator()
    service = SpriteService(store, generator)
    first = asyncio.run(service.ensure_sprite(job(unit_id, campaign_id, signature_id)))
    again = asyncio.run(service.ensure_sprite(job(unit_id, campaign_id, signature_id)))
    assert first is not None
    assert first == again
    assert generator.calls == 1
    assert store.style_anchor(campaign_id) == first
    renamed = SpriteJob(
        unit_id, campaign_id, signature_id, "Tasa", "kubo", "cup", job().crop_rgb
    )
    asyncio.run(service.ensure_sprite(renamed))
    assert generator.anchors == [None, b"png-1"]
    store.close()


def test_service_without_generator_uses_cache_only(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    campaign_id, unit_id, signature_id = unit_in(store)
    sprite_job = job(unit_id, campaign_id, signature_id)
    assert (
        asyncio.run(
            SpriteService(store, PlaceholderGenerator()).ensure_sprite(sprite_job)
        )
        is None
    )
    asyncio.run(SpriteService(store, CountingGenerator()).ensure_sprite(sprite_job))
    offline = CountingGenerator(available=False)
    assert (
        asyncio.run(SpriteService(store, offline).ensure_sprite(sprite_job)) is not None
    )
    assert offline.calls == 0
    store.close()

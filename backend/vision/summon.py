import base64
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Final, Literal, Protocol

import cv2
import numpy as np
import numpy.typing as npt
import openai

from config import STACK_OVERLAP, CallKind, MetaModel
from gm.prompts import SUMMON_SYSTEM_PROMPT, KnownBox, summon_input_text
from gm.schemas import (
    ContentFilter,
    SchemaError,
    UnitCardResponse,
    clamp_box,
    parse_unit_card,
    unit_card_json_schema,
)
from meta_client import CallSpec, MetaClient, MetaError, response_usage
from rules.units import (
    CardDraft,
    ClampedCard,
    Difficulty,
    PowerId,
    RosterError,
    UnitClass,
    check_can_summon,
    clamp_card,
    default_card,
    next_sam_id,
)
from vision.sam import (
    ObjectMask,
    ObjectPrompt,
    PixelBox,
    SegmentationError,
    Segmenter,
    box_overlap_ratio,
    mask_centroid_px,
)
from vision.sam import (
    clamp_box as clamp_pixel_box,
)
from vision.signature import SignatureCapture, SignatureError, make_signature

logger = logging.getLogger("desktop.summon")

Image = npt.NDArray[np.uint8]
DetectionSource = Literal["spark", "fallback"]

SPARK_SPEC: Final = CallSpec(
    model=MetaModel.SPARK, kind=CallKind.SPARK, is_idempotent=True
)
SCHEMA_NAME: Final = "unit_card"
REPAIR_PREFIX: Final = "Your last output failed validation: "
REPAIR_SUFFIX: Final = ". Return only valid JSON."
GRID_MAX: Final = 1000
TAP_BOX_HALF_CM: Final = 3.0
SPARK_JPEG_QUALITY: Final = 85
STACK_KEY: Final = "summon.stack"
WHICH_KEY: Final = "summon.which"


class SummonError(Exception):
    def __init__(self, copy_key: str) -> None:
        super().__init__(copy_key)
        self.copy_key = copy_key


@dataclass(frozen=True)
class CardText:
    power_name_tl: str = ""
    card_text_tl: str = ""
    card_text_en: str = ""
    sprite_subject_en: str = ""


@dataclass(frozen=True)
class Detection:
    found_new: bool
    label: str
    box: PixelBox | None
    draft: CardDraft | None
    text: CardText
    source: DetectionSource


@dataclass(frozen=True)
class KnownObject:
    sam_id: int
    label: str
    unit_class: UnitClass
    box: PixelBox


@dataclass(frozen=True)
class SummonRequest:
    snapshot: Image = field(compare=False)
    spoken_name: str
    known: tuple[KnownObject, ...]
    difficulty: Difficulty
    px_per_cm: float
    tap_point: tuple[int, int] | None = None
    prior: Detection | None = None


@dataclass(frozen=True)
class SummonOutcome:
    name: str
    label: str
    sam_id: int
    card: ClampedCard
    text: CardText
    mask: ObjectMask
    signature: SignatureCapture
    x_cm: float
    y_cm: float
    known_masks: dict[int, ObjectMask]
    source: DetectionSource


class Detector(Protocol):
    @property
    def is_available(self) -> bool: ...

    async def detect(
        self, snapshot: Image, spoken_name: str, known: Sequence[KnownObject]
    ) -> Detection: ...


def to_grid(box: PixelBox, width: int, height: int) -> tuple[int, int, int, int]:
    return (
        round(box.left / width * GRID_MAX),
        round(box.top / height * GRID_MAX),
        round(box.right / width * GRID_MAX),
        round(box.bottom / height * GRID_MAX),
    )


def known_boxes(
    known: Sequence[KnownObject], width: int, height: int
) -> list[KnownBox]:
    boxes: list[KnownBox] = []
    for item in known:
        x1, y1, x2, y2 = to_grid(item.box, width, height)
        boxes.append(
            KnownBox(
                slot_id=str(item.sam_id), label=item.label, x1=x1, y1=y1, x2=x2, y2=y2
            )
        )
    return boxes


def safe_text(text: CardText, content: ContentFilter) -> CardText:
    fields = (
        text.power_name_tl,
        text.card_text_tl,
        text.card_text_en,
        text.sprite_subject_en,
    )
    if all(
        content.is_safe_narration(value) and not content.is_profane(value)
        for value in fields
    ):
        return text
    logger.warning("unit card text failed the content filter")
    return CardText(
        sprite_subject_en=text.sprite_subject_en
        if content.is_safe_narration(text.sprite_subject_en)
        else ""
    )


def detection_from_response(
    response: UnitCardResponse, width: int, height: int, content: ContentFilter
) -> Detection:
    card = response.card
    draft = CardDraft(
        unit_class=UnitClass(card.class_),
        hp_delta=card.hp_delta,
        atk_delta=card.atk_delta,
        power_id=PowerId(card.power_id),
    )
    text = safe_text(
        CardText(
            card.power_name_tl,
            card.card_text_tl,
            card.card_text_en,
            card.sprite_subject_en,
        ),
        content,
    )
    label = (
        response.detected.label
        if not content.is_profane(response.detected.label)
        else ""
    )
    box: PixelBox | None = None
    if response.detected.found_new:
        try:
            x1, y1, x2, y2 = clamp_box(response.detected.box, width, height)
            box = PixelBox(x1, y1, x2, y2)
        except (SchemaError, SegmentationError):
            box = None
    return Detection(
        found_new=box is not None,
        label=label,
        box=box,
        draft=draft,
        text=text,
        source="spark",
    )


def encode_snapshot(image: Image) -> str:
    ok, buffer = cv2.imencode(
        ".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, SPARK_JPEG_QUALITY]
    )
    if not ok:
        raise SummonError(WHICH_KEY)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode(
        "ascii"
    )


class FallbackDetector:
    @property
    def is_available(self) -> bool:
        return True

    async def detect(
        self, snapshot: Image, spoken_name: str, known: Sequence[KnownObject]
    ) -> Detection:
        return Detection(
            found_new=False,
            label="",
            box=None,
            draft=None,
            text=CardText(),
            source="fallback",
        )


class SparkDetector:
    def __init__(
        self,
        client: MetaClient,
        content: ContentFilter,
        log_invalid: Callable[[str], None],
    ) -> None:
        self._client = client
        self._content = content
        self._log_invalid = log_invalid

    @property
    def is_available(self) -> bool:
        return self._client.is_available(MetaModel.SPARK)

    async def detect(
        self, snapshot: Image, spoken_name: str, known: Sequence[KnownObject]
    ) -> Detection:
        height, width = snapshot.shape[:2]
        slot_ids = [str(item.sam_id) for item in known]
        schema = unit_card_json_schema(slot_ids)
        image_url = encode_snapshot(snapshot)
        prompt = summon_input_text(spoken_name, known_boxes(known, width, height))
        repair = ""
        for _ in range(2):
            try:
                raw = await self._ask(image_url, prompt + repair, schema)
            except MetaError:
                logger.warning("spark detection unavailable, falling back to tap")
                break
            try:
                response = parse_unit_card(raw, slot_ids)
            except SchemaError as error:
                self._log_invalid(type(error).__name__)
                repair = f"\n\n{REPAIR_PREFIX}{str(error)[:300]}{REPAIR_SUFFIX}"
                continue
            return detection_from_response(response, width, height, self._content)
        return await FallbackDetector().detect(snapshot, spoken_name, known)

    async def _ask(self, image_url: str, prompt: str, schema: dict[str, object]) -> str:
        async def operation() -> openai.types.responses.Response:
            return await self._client.sdk().responses.create(
                model=MetaModel.SPARK.value,
                instructions=SUMMON_SYSTEM_PROMPT,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_image",
                                "image_url": image_url,
                                "detail": "auto",
                            },
                            {"type": "input_text", "text": prompt},
                        ],
                    }
                ],
                reasoning={"effort": "medium"},
                store=False,
                extra_body={
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": SCHEMA_NAME,
                            "schema": schema,
                            "strict": True,
                        }
                    }
                },
            )

        response = await self._client.execute(SPARK_SPEC, operation, response_usage)
        return response.output_text


def tap_box(
    point: tuple[int, int], px_per_cm: float, width: int, height: int
) -> PixelBox:
    half = round(TAP_BOX_HALF_CM * px_per_cm)
    x, y = point
    return clamp_pixel_box(
        PixelBox(x - half, y - half, x + half, y + half), width, height
    )


def box_mask(box: PixelBox, sam_id: int) -> ObjectMask:
    return ObjectMask(
        sam_id=sam_id,
        confidence=None,
        bounds=box,
        mask=np.ones((box.height, box.width), dtype=np.bool_),
    )


class SummonPipeline:
    def __init__(
        self, detector: Detector, segmenter: Segmenter, content: ContentFilter
    ) -> None:
        self._detector = detector
        self._segmenter = segmenter
        self._content = content

    async def detect(self, request: SummonRequest) -> Detection:
        if request.tap_point is not None:
            height, width = request.snapshot.shape[:2]
            prior = request.prior
            return Detection(
                found_new=True,
                label=prior.label if prior is not None else "",
                box=tap_box(request.tap_point, request.px_per_cm, width, height),
                draft=prior.draft if prior is not None else None,
                text=prior.text if prior is not None else CardText(),
                source=prior.source if prior is not None else "fallback",
            )
        detector: Detector = (
            self._detector if self._detector.is_available else FallbackDetector()
        )
        return await detector.detect(
            request.snapshot, request.spoken_name, request.known
        )

    async def run(self, request: SummonRequest, detection: Detection) -> SummonOutcome:
        roster = [item.unit_class for item in request.known]
        try:
            check_can_summon(roster)
        except RosterError as error:
            raise SummonError(error.copy_key) from error
        if not detection.found_new or detection.box is None:
            raise SummonError(WHICH_KEY)
        box = detection.box
        if any(
            box_overlap_ratio(box, item.box) > STACK_OVERLAP for item in request.known
        ):
            raise SummonError(STACK_KEY)
        try:
            sam_id = next_sam_id([item.sam_id for item in request.known])
        except RosterError as error:
            raise SummonError(error.copy_key) from error
        masks = await self._segment(request, sam_id, box)
        mask = masks.get(sam_id) or box_mask(box, sam_id)
        card = (
            clamp_card(detection.draft, roster, request.difficulty)
            if detection.draft is not None
            else default_card(UnitClass.FIGHTER, roster, request.difficulty)
        )
        name = self._content.clean_player_name(
            request.spoken_name, card.unit_class.value.title()
        )
        label = detection.label or name
        try:
            signature = make_signature(request.snapshot, mask, label, request.px_per_cm)
        except SignatureError:
            mask = box_mask(box, sam_id)
            signature = make_signature(request.snapshot, mask, label, request.px_per_cm)
        cx, cy = mask_centroid_px(mask)
        known_masks = {sid: m for sid, m in masks.items() if sid != sam_id}
        return SummonOutcome(
            name=name,
            label=label,
            sam_id=sam_id,
            card=card,
            text=detection.text,
            mask=mask,
            signature=signature,
            x_cm=cx / request.px_per_cm,
            y_cm=cy / request.px_per_cm,
            known_masks=known_masks,
            source=detection.source,
        )

    async def _segment(
        self, request: SummonRequest, sam_id: int, box: PixelBox
    ) -> dict[int, ObjectMask]:
        if not self._segmenter.is_available:
            return {}
        prompts = [ObjectPrompt(item.sam_id, item.box) for item in request.known]
        point = None if request.tap_point is None else request.tap_point
        prompts.append(ObjectPrompt(sam_id, box, point))
        try:
            result = await self._segmenter.segment(request.snapshot, prompts)
        except (SegmentationError, MetaError):
            logger.warning("summon masks unavailable, using boxes")
            return {}
        return dict(result.masks)

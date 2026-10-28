import argparse
import asyncio
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from meta_sam_parser import (
    FramePrompt,
    PromptBox,
    PromptObject,
    SegmentationMaskRecord,
    build_object_prompt,
    image_segmentation_format,
    parse_responses_stream,
)
from PIL import Image

from config import CallKind, MetaModel
from meta_client import CallSpec, MetaUnavailableError, Usage
from smoke import (
    JsonValue,
    SmokeContext,
    SmokeError,
    image_data_url,
    open_smoke_context,
    save_jsonl_fixture,
    save_text_fixture,
    to_json,
)

SPEC: Final = CallSpec(model=MetaModel.SAM, kind=CallKind.SAM_IMAGE, is_idempotent=True)
DELTA_EVENT: Final = "response.output_text.delta"
METADATA: Final = {"include_confidence": "true", "mask_encoding": "one_bit"}


@dataclass(frozen=True)
class BoxArg:
    object_id: int
    left: int
    top: int
    right: int
    bottom: int


def parse_box(raw: str) -> BoxArg:
    parts = raw.split(",")
    if len(parts) != 5 or not all(part.strip().isdigit() for part in parts):
        raise argparse.ArgumentTypeError(
            "box must be id,x1,y1,x2,y2 with whole numbers"
        )
    object_id, left, top, right, bottom = (int(part) for part in parts)
    if not 1 <= object_id <= 16 or right <= left or bottom <= top:
        raise argparse.ArgumentTypeError(
            "id must be 1 to 16 and the box must have area"
        )
    return BoxArg(object_id, left, top, right, bottom)


def build_prompt(size: tuple[int, int], boxes: Sequence[BoxArg]) -> str:
    objects = [
        PromptObject(
            id=box.object_id,
            prompts=[
                FramePrompt(
                    frame=0, box=PromptBox(box.left, box.top, box.right, box.bottom)
                )
            ],
        )
        for box in boxes
    ]
    return build_object_prompt(size=size, objects=objects)


async def stream_events(
    ctx: SmokeContext, prompt: str, image_path: Path
) -> list[JsonValue]:
    stream = await ctx.client.sdk().responses.create(
        model=MetaModel.SAM.value,
        input=[
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": image_data_url(image_path),
                        "detail": "auto",
                    },
                ],
            }
        ],
        stream=True,
        metadata=METADATA,
    )
    return [to_json(event) async for event in stream]


async def replay(events: Sequence[JsonValue]) -> AsyncIterator[dict[str, JsonValue]]:
    for event in events:
        if isinstance(event, dict):
            yield event


def raw_text(events: Sequence[JsonValue]) -> str:
    deltas = [
        str(event.get("delta", ""))
        for event in events
        if isinstance(event, dict) and event.get("type") == DELTA_EVENT
    ]
    return "".join(deltas)


async def summarize(events: Sequence[JsonValue]) -> None:
    parsed = parse_responses_stream(replay(events), image_segmentation_format())
    async for _ in parsed:
        continue
    result = await parsed.final_result()
    masks = [
        record
        for record in result.records
        if isinstance(record, SegmentationMaskRecord)
    ]
    print(
        f"[sam] outcome: {type(result.outcome).__name__}, records: {len(result.records)}"
    )
    for record in masks:
        bounds = record.bounds
        print(
            f"[sam] id {record.object_id}: confidence {record.confidence}, "
            f"bounds ({bounds.left:.0f},{bounds.top:.0f})-({bounds.right:.0f},{bounds.bottom:.0f}), "
            f"mask {record.mask.width}x{record.mask.height}"
        )
    for diagnostic in result.diagnostics:
        print(f"[sam] diagnostic: {diagnostic}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="SAM 3.1 image smoke test")
    parser.add_argument("--image", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--box", type=parse_box, action="append")
    group.add_argument("--concept", type=str)
    parser.add_argument("--name", type=str, default="sam_boxes")
    args = parser.parse_args()
    image_path: Path = args.image
    if not image_path.is_file():
        raise SmokeError(f"image not found: {image_path}")
    with Image.open(image_path) as image:
        size = image.size
    prompt = str(args.concept) if args.concept else build_prompt(size, args.box)
    print(f"[sam] image {size[0]}x{size[1]}, prompt: {prompt}")
    ctx = open_smoke_context()
    try:
        started = time.perf_counter()
        events = await ctx.client.execute(
            SPEC,
            lambda: stream_events(ctx, prompt, image_path),
            lambda _: Usage(images=1),
        )
        print(f"[sam] seconds: {time.perf_counter() - started:.2f}")
        name: str = args.name
        print(
            f"[sam] events fixture: {save_jsonl_fixture(f'{name}.jsonl', events, ctx.api_key)}"
        )
        print(
            f"[sam] text fixture: {save_text_fixture(f'{name}.txt', raw_text(events), ctx.api_key)}"
        )
        await summarize(events)
    except MetaUnavailableError as error:
        raise SmokeError(f"SAM unavailable: {error}") from error
    finally:
        print(f"[sam] total api spend so far: ${ctx.client.meter.spent_usd}")
        ctx.store.close()


if __name__ == "__main__":
    asyncio.run(main())

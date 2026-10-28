import argparse
import asyncio
import base64
import statistics
import time
from pathlib import Path
from typing import Final

from config import CallKind, MetaModel
from meta_client import CallSpec, MetaRequestError, MetaUnavailableError, Usage
from smoke import (
    JsonValue,
    SmokeContext,
    SmokeError,
    image_data_url,
    open_smoke_context,
    save_binary_fixture,
    save_json_fixture,
    to_json,
)

SPEC: Final = CallSpec(model=MetaModel.IMAGE, kind=CallKind.IMAGE, is_idempotent=True)
IMAGE_CALL_TYPE: Final = "image_generation_call"
MAX_RUNS: Final = 20
TOOL: Final[dict[str, JsonValue]] = {
    "type": "image_generation",
    "enable_web_search": False,
    "enable_image_search": False,
    "enable_shell": False,
    "reasoning_strength": "low",
    "size": "1024x1024",
    "output_format": "png",
}
PROMPT_TEMPLATE: Final = (
    "Redraw the object in this photo as one top-down 16-bit pixel art game sprite of {subject}, "
    "a {unit_class} defender in a Filipino folklore night game. Keep the object's main colors "
    "and silhouette so it is recognizable. Centered, fills about 80% of the frame, no shadow, "
    "no text, no border. Solid flat {key} background."
)


async def generate(ctx: SmokeContext, prompt: str, crop: Path) -> JsonValue:
    response = await ctx.client.sdk().responses.create(
        model=MetaModel.IMAGE.value,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": image_data_url(crop),
                        "detail": "auto",
                    },
                ],
            }
        ],
        extra_body={"tools": [TOOL]},
    )
    return to_json(response)


def split_image(data: JsonValue) -> tuple[bytes, JsonValue]:
    if not isinstance(data, dict):
        raise SmokeError("unexpected response shape")
    output = data.get("output")
    if not isinstance(output, list):
        raise SmokeError("response has no output list")
    for item in output:
        if not isinstance(item, dict) or item.get("type") != IMAGE_CALL_TYPE:
            continue
        result = item.get("result")
        if not isinstance(result, str):
            raise SmokeError("image_generation_call has no base64 result")
        item["result"] = f"[base64 png, {len(result)} chars, saved separately]"
        return base64.b64decode(result), data
    raise SmokeError("no image_generation_call in output")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Muse Image smoke test and latency timing"
    )
    parser.add_argument("--crop", type=Path, required=True)
    parser.add_argument("--subject", type=str, default="a bahay kubo")
    parser.add_argument("--unit-class", type=str, default="kubo")
    parser.add_argument(
        "--key", type=str, choices=["#FF00FF", "#00FF00"], default="#FF00FF"
    )
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--name", type=str, default="sprite_kubo")
    args = parser.parse_args()
    crop: Path = args.crop
    runs: int = args.runs
    if not crop.is_file():
        raise SmokeError(f"crop not found: {crop}")
    if not 1 <= runs <= MAX_RUNS:
        raise SmokeError(f"runs must be 1 to {MAX_RUNS}")
    prompt = PROMPT_TEMPLATE.format(
        subject=args.subject, unit_class=args.unit_class, key=args.key
    )
    ctx = open_smoke_context()
    timings: list[float] = []
    try:
        for run in range(runs):
            started = time.perf_counter()
            data = await ctx.client.execute(
                SPEC, lambda: generate(ctx, prompt, crop), lambda _: Usage(images=1)
            )
            timings.append(time.perf_counter() - started)
            png, metadata = split_image(data)
            suffix = "" if run == 0 else f"_{run + 1}"
            name: str = args.name
            print(f"[image] run {run + 1}: {timings[-1]:.2f} s")
            print(f"[image] png: {save_binary_fixture(f'{name}{suffix}.png', png)}")
            if run == 0:
                print(
                    f"[image] json: {save_json_fixture(f'{name}.json', metadata, ctx.api_key)}"
                )
        print(
            f"[image] seconds min {min(timings):.2f} median {statistics.median(timings):.2f} max {max(timings):.2f}"
        )
    except MetaRequestError as error:
        label = "content policy block" if error.is_content_policy else "HTTP 400"
        raise SmokeError(f"Muse Image rejected the request: {label}") from error
    except MetaUnavailableError as error:
        raise SmokeError(f"Muse Image unavailable: {error}") from error
    finally:
        print(f"[image] total api spend so far: ${ctx.client.meter.spent_usd}")
        ctx.store.close()


if __name__ == "__main__":
    asyncio.run(main())

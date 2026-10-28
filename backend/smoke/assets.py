import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np

from config import MetaModel
from meta_client import MetaRequestError, MetaUnavailableError, Usage
from smoke import REPO_DIR, SmokeContext, SmokeError, open_smoke_context
from vision.sam import Image
from vision.sprites import (
    IMAGE_SPEC,
    IMAGE_TOOL,
    MAGENTA_KEY,
    decode_png,
    encode_png,
    image_payload,
    other_key,
    process_generated,
)

PLACEHOLDER_DIR: Final = REPO_DIR / "assets" / "sprites" / "placeholders"
ENEMY_DIR: Final = REPO_DIR / "assets" / "sprites" / "enemies"
LICENSE_TEXT: Final = (
    "Generated for DeskTop: Hanggang Umaga with Meta Muse Image 1.0 on {date}, keyed and "
    "palette-locked by backend/vision/sprites.py. License: CC BY-NC 4.0 (project default, Q3).\n"
)
STYLE: Final = (
    "One top-down 16-bit pixel art game sprite, cute-spooky, readable silhouette, no gore, "
    "no blood, no text, no border, no shadow, centered, fills about 80% of the frame. "
    "Solid flat {key} background."
)


@dataclass(frozen=True)
class AssetSpec:
    folder: Path
    name: str
    subject: str
    is_animated: bool


PLACEHOLDERS: Final = (
    AssetSpec(
        PLACEHOLDER_DIR,
        "kubo",
        "a small bamboo and nipa bahay kubo hut seen from above",
        False,
    ),
    AssetSpec(PLACEHOLDER_DIR, "charm", "a glowing round amulet charm", False),
    AssetSpec(
        PLACEHOLDER_DIR,
        "healer",
        "a small bundle of healing herbs in a woven pouch",
        False,
    ),
    AssetSpec(
        PLACEHOLDER_DIR,
        "fighter",
        "a sturdy wooden shield with a bolo knife crossed behind it",
        False,
    ),
    AssetSpec(PLACEHOLDER_DIR, "reach", "a bamboo spear", False),
    AssetSpec(PLACEHOLDER_DIR, "ranged", "a small wooden bow with a quiver", False),
    AssetSpec(
        PLACEHOLDER_DIR, "scout", "a pair of woven sandals with motion lines", False
    ),
    AssetSpec(PLACEHOLDER_DIR, "wall", "a short bamboo fence segment", False),
)
ENEMIES: Final = (
    AssetSpec(
        ENEMY_DIR,
        "aswang",
        "a low, fast, four-legged shadowy night creature with glowing eyes, cute-spooky",
        True,
    ),
    AssetSpec(
        ENEMY_DIR,
        "tikbalang",
        "a tall lanky creature with a horse head, cute-spooky",
        True,
    ),
    AssetSpec(
        ENEMY_DIR,
        "kapre",
        "a big friendly-scary tree giant holding a large cigar, cute-spooky",
        True,
    ),
    AssetSpec(
        ENEMY_DIR,
        "manananggal_upper",
        "a winged upper half of a night creature with bat wings, no visible wound, cute-spooky",
        True,
    ),
    AssetSpec(
        ENEMY_DIR,
        "manananggal_lower",
        "a pair of standing legs in a skirt, cute-spooky, no gore",
        True,
    ),
    AssetSpec(
        ENEMY_DIR,
        "duwende",
        "a tiny mischievous gnome with a pointed hat, cute-spooky",
        True,
    ),
)


def bob_frame(sprite: Image) -> Image:
    shifted = np.zeros_like(sprite)
    shifted[:-1] = sprite[1:]
    return shifted


async def generate_one(ctx: SmokeContext, spec: AssetSpec) -> Image:
    key = MAGENTA_KEY
    for attempt_key in (key, other_key(key)):
        hex_key = f"#{attempt_key[0]:02X}{attempt_key[1]:02X}{attempt_key[2]:02X}"
        prompt = f"{STYLE.format(key=hex_key)} Subject: {spec.subject}."

        async def operation(text: str = prompt) -> object:
            return await ctx.client.sdk().responses.create(
                model=MetaModel.IMAGE.value,
                store=False,
                extra_body={"input": text, "tools": [IMAGE_TOOL]},
            )

        response = await ctx.client.execute(
            IMAGE_SPEC, operation, lambda _: Usage(images=1)
        )
        raw, _ = image_payload(response)
        sprite, check = process_generated(decode_png(raw), attempt_key)
        print(
            f"[assets] {spec.name}: coverage {check.alpha_coverage:.2f}, colors {check.distinct_colors}"
        )
        if check.is_valid:
            return sprite
    raise SmokeError(f"{spec.name} did not pass validation with either key colour")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate placeholder and enemy sprites with Muse Image"
    )
    parser.add_argument(
        "--only", choices=["placeholders", "enemies", "all"], default="all"
    )
    parser.add_argument("--date", type=str, required=True)
    args = parser.parse_args()
    specs = {
        "placeholders": PLACEHOLDERS,
        "enemies": ENEMIES,
        "all": PLACEHOLDERS + ENEMIES,
    }[str(args.only)]
    ctx = open_smoke_context()
    try:
        for spec in specs:
            spec.folder.mkdir(parents=True, exist_ok=True)
            sprite = await generate_one(ctx, spec)
            if spec.is_animated:
                (spec.folder / f"{spec.name}_0.png").write_bytes(encode_png(sprite))
                (spec.folder / f"{spec.name}_1.png").write_bytes(
                    encode_png(bob_frame(sprite))
                )
            else:
                (spec.folder / f"{spec.name}.png").write_bytes(encode_png(sprite))
        for folder in {spec.folder for spec in specs}:
            (folder / "LICENSE.txt").write_text(
                LICENSE_TEXT.format(date=args.date), encoding="utf-8"
            )
    except MetaRequestError as error:
        label = "content policy block" if error.is_content_policy else "HTTP 4xx"
        raise SmokeError(f"Muse Image rejected a request: {label}") from error
    except MetaUnavailableError as error:
        raise SmokeError(f"Muse Image unavailable: {error}") from error
    finally:
        print(f"[assets] total api spend so far: ${ctx.client.meter.spent_usd}")
        ctx.store.close()


if __name__ == "__main__":
    asyncio.run(main())

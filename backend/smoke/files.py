import argparse
import asyncio
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Final

from openai.types.file_create_params import ExpiresAfter

from config import CallKind, MetaModel
from meta_client import CallSpec, MetaRequestError, MetaUnavailableError, Usage
from smoke import (
    JsonValue,
    SmokeContext,
    SmokeError,
    open_smoke_context,
    save_json_fixture,
    to_json,
)

UPLOAD: Final = CallSpec(
    model=MetaModel.FILES, kind=CallKind.FILES, is_idempotent=False
)
DELETE: Final = CallSpec(model=MetaModel.FILES, kind=CallKind.FILES, is_idempotent=True)
EXPIRES_AFTER: Final[ExpiresAfter] = {"anchor": "created_at", "seconds": 86400}
MAX_UPLOAD_BYTES: Final = 1024 * 1024 * 1024


async def upload_direct(ctx: SmokeContext, clip: Path) -> JsonValue:
    with clip.open("rb") as handle:
        created = await ctx.client.sdk().files.create(
            file=handle, purpose="user_data", expires_after=EXPIRES_AFTER
        )
    return to_json(created)


async def upload_extra_body(ctx: SmokeContext, clip: Path) -> JsonValue:
    with clip.open("rb") as handle:
        created = await ctx.client.sdk().files.create(
            file=handle,
            purpose="user_data",
            extra_body={"expires_after": EXPIRES_AFTER},
        )
    return to_json(created)


async def upload_plain(ctx: SmokeContext, clip: Path) -> JsonValue:
    with clip.open("rb") as handle:
        created = await ctx.client.sdk().files.create(file=handle, purpose="user_data")
    return to_json(created)


async def delete_file(ctx: SmokeContext, file_id: str) -> JsonValue:
    deleted = await ctx.client.sdk().files.delete(file_id)
    return to_json(deleted)


def file_id_of(data: JsonValue) -> str:
    if not isinstance(data, dict) or not isinstance(data.get("id"), str):
        raise SmokeError("upload response has no id")
    return str(data["id"])


Uploader = Callable[[SmokeContext, Path], Awaitable[JsonValue]]


def bind_upload(
    upload: Uploader, ctx: SmokeContext, clip: Path
) -> Callable[[], Awaitable[JsonValue]]:
    return lambda: upload(ctx, clip)


async def upload_with_fallbacks(ctx: SmokeContext, clip: Path) -> tuple[str, JsonValue]:
    shapes = (
        ("expires_after as a direct argument", upload_direct),
        ("expires_after in extra_body", upload_extra_body),
        ("no expires_after, explicit DELETE only", upload_plain),
    )
    for label, upload in shapes:
        try:
            data = await ctx.client.execute(
                UPLOAD, bind_upload(upload, ctx, clip), lambda _: Usage()
            )
        except MetaRequestError as error:
            print(f"[files] {label}: rejected ({type(error).__name__})")
            continue
        print(f"[files] WORKS: {label}")
        return label, data
    raise SmokeError("every upload shape was rejected")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Files API upload and delete smoke test"
    )
    parser.add_argument("--clip", type=Path, required=True)
    args = parser.parse_args()
    clip: Path = args.clip
    if not clip.is_file() or clip.suffix.lower() != ".mp4":
        raise SmokeError("clip must be an existing .mp4 file")
    if clip.stat().st_size > MAX_UPLOAD_BYTES:
        raise SmokeError("clip is over the 1 GiB upload limit")
    ctx = open_smoke_context()
    try:
        started = time.perf_counter()
        _, created = await upload_with_fallbacks(ctx, clip)
        print(f"[files] upload seconds: {time.perf_counter() - started:.2f}")
        file_id = file_id_of(created)
        deleted = await ctx.client.execute(
            DELETE, lambda: delete_file(ctx, file_id), lambda _: Usage()
        )
        print(f"[files] deleted: {deleted}")
        path = save_json_fixture(
            "files_upload.json", {"create": created, "delete": deleted}, ctx.api_key
        )
        print(f"[files] fixture: {path}")
    except MetaUnavailableError as error:
        raise SmokeError(f"Files API unavailable: {error}") from error
    finally:
        ctx.store.close()


if __name__ == "__main__":
    asyncio.run(main())

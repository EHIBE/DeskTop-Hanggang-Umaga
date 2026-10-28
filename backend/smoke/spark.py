import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

from config import CallKind, MetaModel
from meta_client import CallSpec, MetaRequestError, MetaUnavailableError, Usage
from smoke import (
    JsonValue,
    SmokeContext,
    SmokeError,
    open_smoke_context,
    save_json_fixture,
    to_json,
    usage_from_chat,
    usage_from_responses,
)

SPEC: Final = CallSpec(model=MetaModel.SPARK, kind=CallKind.SPARK, is_idempotent=True)
SCHEMA_NAME: Final = "line"
PROMPT: Final = "Write one spooky Taglish line about an aswang near a bahay kubo."
SCHEMA: Final[dict[str, JsonValue]] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["line_tl", "line_en"],
    "properties": {
        "line_tl": {"type": "string", "maxLength": 240},
        "line_en": {"type": "string", "maxLength": 240},
    },
}


@dataclass(frozen=True)
class Attempt:
    shape: str
    call: Callable[[SmokeContext], Awaitable[JsonValue]]
    usage_of: Callable[[JsonValue], Usage]
    text_of: Callable[[JsonValue], str]


async def _responses_nested(ctx: SmokeContext) -> JsonValue:
    response = await ctx.client.sdk().responses.create(
        model=MetaModel.SPARK.value,
        input=PROMPT,
        reasoning={"effort": "low"},
        store=False,
        extra_body={
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": SCHEMA_NAME,
                    "schema": SCHEMA,
                    "strict": True,
                }
            }
        },
    )
    return to_json(response)


async def _responses_flat(ctx: SmokeContext) -> JsonValue:
    response = await ctx.client.sdk().responses.create(
        model=MetaModel.SPARK.value,
        input=PROMPT,
        reasoning={"effort": "low"},
        store=False,
        extra_body={
            "text": {
                "format": "json_schema",
                "json_schema": {"name": SCHEMA_NAME, "schema": SCHEMA, "strict": True},
            }
        },
    )
    return to_json(response)


async def _chat_completions(ctx: SmokeContext) -> JsonValue:
    response = await ctx.client.sdk().chat.completions.create(
        model=MetaModel.SPARK.value,
        messages=[{"role": "user", "content": PROMPT}],
        extra_body={
            "reasoning_effort": "low",
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": SCHEMA_NAME, "schema": SCHEMA, "strict": True},
            },
        },
    )
    return to_json(response)


def _usage_dict(data: JsonValue) -> dict[str, JsonValue] | None:
    if not isinstance(data, dict):
        return None
    usage = data.get("usage")
    return usage if isinstance(usage, dict) else None


def _responses_text(data: JsonValue) -> str:
    if not isinstance(data, dict):
        raise SmokeError("unexpected response shape")
    text = data.get("output_text")
    if isinstance(text, str) and text:
        return text
    output = data.get("output")
    items = output if isinstance(output, list) else []
    for item in items:
        content = item.get("content") if isinstance(item, dict) else None
        parts = content if isinstance(content, list) else []
        texts = [
            p["text"]
            for p in parts
            if isinstance(p, dict) and isinstance(p.get("text"), str)
        ]
        if texts:
            return str(texts[0])
    raise SmokeError("no output text in response")


def _chat_text(data: JsonValue) -> str:
    if not isinstance(data, dict):
        raise SmokeError("unexpected response shape")
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise SmokeError("no choices in response")
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise SmokeError("no message content in response")
    return str(message["content"])


ATTEMPTS: Final = (
    Attempt(
        "responses text.format {type, name, schema, strict}",
        _responses_nested,
        lambda data: usage_from_responses(_usage_dict(data)),
        _responses_text,
    ),
    Attempt(
        "responses text.format json_schema with nested json_schema",
        _responses_flat,
        lambda data: usage_from_responses(_usage_dict(data)),
        _responses_text,
    ),
    Attempt(
        "chat.completions response_format json_schema",
        _chat_completions,
        lambda data: usage_from_chat(_usage_dict(data)),
        _chat_text,
    ),
)


def _validate_line(text: str) -> None:
    parsed = json.loads(text)
    if not isinstance(parsed, dict) or set(parsed) != {"line_tl", "line_en"}:
        raise SmokeError("output does not match the schema")


async def run_attempt(ctx: SmokeContext, attempt: Attempt) -> bool:
    started = time.perf_counter()
    try:
        data = await ctx.client.execute(
            SPEC, lambda: attempt.call(ctx), attempt.usage_of
        )
    except MetaRequestError as error:
        print(f"[spark] {attempt.shape}: rejected with HTTP 400 ({error})")
        return False
    elapsed = time.perf_counter() - started
    text = attempt.text_of(data)
    _validate_line(text)
    path = save_json_fixture("spark_line.json", data, ctx.api_key)
    print(f"[spark] WORKS: {attempt.shape}")
    print(f"[spark] seconds: {elapsed:.2f}")
    print(f"[spark] output: {text}")
    print(f"[spark] fixture: {path}")
    return True


async def main() -> None:
    ctx = open_smoke_context()
    try:
        for attempt in ATTEMPTS:
            if await run_attempt(ctx, attempt):
                return
        raise SmokeError("every structured output shape was rejected")
    except MetaUnavailableError as error:
        raise SmokeError(f"Spark unavailable: {error}") from error
    finally:
        print(f"[spark] total api spend so far: ${ctx.client.meter.spent_usd}")
        ctx.store.close()


if __name__ == "__main__":
    asyncio.run(main())

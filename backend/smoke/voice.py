import argparse
import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from typing import Final

import sounddevice  # type: ignore[import-untyped]
import websockets
from websockets.asyncio.client import ClientConnection

from config import META_REALTIME_URL, MetaModel
from db.store import ApiUsageRecord
from meta_client import price_voice_seconds
from smoke import (
    JsonValue,
    SmokeContext,
    SmokeError,
    open_smoke_context,
    save_jsonl_fixture,
)

SAMPLE_RATE: Final = 24_000
FRAME_MS: Final = 80
FRAME_SAMPLES: Final = SAMPLE_RATE * FRAME_MS // 1000
MAX_SECONDS: Final = 60
POLICY_CLOSE: Final = 1008
DRAIN_TIMEOUT_S: Final = 10.0
MODES: Final = ("DIARIZATION", "ENDPOINTING", "PUSH_TO_TALK")
KEYWORDS: Final = ["tapos", "hindi", "kubo", "anting-anting", "albularyo", "aswang"]


@dataclass(frozen=True)
class VoiceRun:
    mode: str
    seconds: int
    with_extras: bool


def handshake(api_key: str, run: VoiceRun) -> str:
    message: dict[str, JsonValue] = {
        "authorization": {"accessToken": f"Bearer {api_key}"},
        "audioEncoding": "PCM_24KHZ",
        "model": MetaModel.VOICE.value,
        "mode": run.mode,
        "partialMode": "CUMULATIVE",
        "emitAudioProgress": False,
    }
    if run.with_extras:
        message["languageBias"] = ["English", "Tagalog"]
        message["keywords"] = list(KEYWORDS)
    return json.dumps(message)


async def receive_events(ws: ClientConnection, events: list[JsonValue]) -> None:
    async for message in ws:
        if isinstance(message, bytes):
            continue
        event: JsonValue = json.loads(message)
        events.append(event)
        if isinstance(event, dict):
            print(
                f"[voice] {event.get('type')}: {json.dumps(event, ensure_ascii=False)}"
            )


async def stream_microphone(ws: ClientConnection, seconds: int) -> None:
    loop = asyncio.get_running_loop()
    frames: asyncio.Queue[bytes] = asyncio.Queue()

    def on_audio(
        indata: bytes, frame_count: int, time_info: object, status: object
    ) -> None:
        loop.call_soon_threadsafe(frames.put_nowait, bytes(indata))

    with sounddevice.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=FRAME_SAMPLES,
        callback=on_audio,
    ):
        deadline = loop.time() + seconds
        while loop.time() < deadline:
            await ws.send(await frames.get())
    while not frames.empty():
        await ws.send(frames.get_nowait())
    await ws.send(json.dumps({"type": "endStream"}))


async def run_session(ctx: SmokeContext, run: VoiceRun) -> list[JsonValue]:
    url = f"{META_REALTIME_URL}?sessionId=smoke-{uuid.uuid4()}"
    events: list[JsonValue] = []
    async with websockets.connect(url, open_timeout=30) as ws:
        await ws.send(handshake(ctx.api_key, run))
        session: JsonValue = json.loads(await ws.recv())
        events.append(session)
        print(f"[voice] session opened in {run.mode}, extras {run.with_extras}")
        receiver = asyncio.create_task(receive_events(ws, events))
        print(f"[voice] speak Taglish now for {run.seconds} s")
        await stream_microphone(ws, run.seconds)
        try:
            await asyncio.wait_for(receiver, timeout=DRAIN_TIMEOUT_S)
        except TimeoutError:
            receiver.cancel()
    return events


async def run_with_fallback(
    ctx: SmokeContext, mode: str, seconds: int
) -> tuple[VoiceRun, list[JsonValue]]:
    run = VoiceRun(mode=mode, seconds=seconds, with_extras=True)
    try:
        return run, await run_session(ctx, run)
    except websockets.exceptions.ConnectionClosedError as error:
        if error.code != POLICY_CLOSE:
            raise
        print(
            "[voice] closed 1008 with languageBias and keywords, retrying without them"
        )
    plain = VoiceRun(mode=mode, seconds=seconds, with_extras=False)
    return plain, await run_session(ctx, plain)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Muse Voice Transcribe realtime smoke test"
    )
    parser.add_argument("--mode", choices=MODES, default="DIARIZATION")
    parser.add_argument("--seconds", type=int, default=10)
    args = parser.parse_args()
    seconds: int = args.seconds
    if not 1 <= seconds <= MAX_SECONDS:
        raise SmokeError(f"seconds must be 1 to {MAX_SECONDS}")
    ctx = open_smoke_context()
    started = time.perf_counter()
    try:
        ctx.client.meter.ensure_can_spend()
        run, events = await run_with_fallback(ctx, str(args.mode), seconds)
        name = f"voice_{run.mode.lower()}.jsonl"
        print(f"[voice] worked with extras: {run.with_extras}")
        print(f"[voice] fixture: {save_jsonl_fixture(name, events, ctx.api_key)}")
    finally:
        elapsed = int(time.perf_counter() - started)
        ctx.client.meter.record(
            ApiUsageRecord(
                model=MetaModel.VOICE.value,
                kind="voice",
                cost_usd=price_voice_seconds(seconds),
                ok=True,
                latency_ms=elapsed * 1000,
                audio_seconds=seconds,
            )
        )
        print(f"[voice] total api spend so far: ${ctx.client.meter.spent_usd}")
        ctx.store.close()


if __name__ == "__main__":
    asyncio.run(main())

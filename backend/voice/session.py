import asyncio
import json
import logging
import math
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final, Protocol

import sounddevice  # type: ignore[import-untyped]
import websockets
from websockets.asyncio.client import ClientConnection

from config import META_REALTIME_URL, MetaModel
from db.store import ApiUsageRecord
from meta_client import BudgetExceededError, CostMeter, price_voice_seconds

logger = logging.getLogger(__name__)

SAMPLE_RATE: Final = 24_000
FRAME_MS: Final = 80
FRAME_SAMPLES: Final = SAMPLE_RATE * FRAME_MS // 1000
FRAME_BYTES: Final = FRAME_SAMPLES * 2
SILENCE_FRAME: Final = bytes(FRAME_BYTES)
COST_INTERVAL_S: Final = 60.0
BACKOFF_S: Final = (0.5, 1.0, 2.0)
MAX_FAILURES: Final = 3
CLOSE_NORMAL: Final = 1000
CLOSE_POLICY: Final = 1008
OPEN_TIMEOUT_S: Final = 30
MAX_TEXT_CHARS: Final = 2_000
MAX_ID_CHARS: Final = 128
MAX_OPEN_TURNS: Final = 32
TEXT_KEYS: Final = ("text", "transcript")
SPEAKER_KEYS: Final = ("speaker", "speakerLabel", "label")


class VoiceStatus(StrEnum):
    OFF = "off"
    CONNECTING = "connecting"
    LISTENING = "listening"
    DOWN = "down"


class VoiceMode(StrEnum):
    OPEN = "open"
    PTT = "ptt"


@dataclass(frozen=True)
class Caption:
    turn_id: str
    text: str
    is_final: bool
    speaker: str | None


class MicrophoneError(Exception):
    pass


class ConnectionClosedError(Exception):
    def __init__(self, code: int | None) -> None:
        super().__init__(f"voice connection closed {code}")
        self.code = code


class Microphone(Protocol):
    def __aiter__(self) -> AsyncIterator[bytes]: ...

    async def close(self) -> None: ...


class Connection(Protocol):
    async def send(self, data: str | bytes) -> None: ...

    def __aiter__(self) -> AsyncIterator[str | bytes]: ...

    async def close(self) -> None: ...


class Connector(Protocol):
    async def connect(self, url: str) -> Connection: ...


class SoundDeviceMicrophone:
    def __init__(self, device_index: int | None = None) -> None:
        self._device = device_index
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._is_closed = False

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self._generate()

    async def close(self) -> None:
        self._is_closed = True
        self._queue.put_nowait(b"")

    async def _generate(self) -> AsyncIterator[bytes]:
        loop = asyncio.get_running_loop()
        queue = self._queue

        def on_audio(
            indata: bytes, frame_count: int, time_info: object, status: object
        ) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, bytes(indata))

        try:
            stream = sounddevice.RawInputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=FRAME_SAMPLES,
                device=self._device,
                callback=on_audio,
            )
            stream.start()
        except (sounddevice.PortAudioError, ValueError, OSError):
            raise MicrophoneError("microphone unavailable") from None
        try:
            while not self._is_closed:
                frame = await queue.get()
                if frame:
                    yield frame
        finally:
            stream.stop()
            stream.close()


def _close_code(error: websockets.exceptions.ConnectionClosed) -> int | None:
    received = error.rcvd
    return received.code if received is not None else None


class WebsocketsConnection:
    def __init__(self, ws: ClientConnection) -> None:
        self._ws = ws

    async def send(self, data: str | bytes) -> None:
        try:
            await self._ws.send(data)
        except websockets.exceptions.ConnectionClosed as error:
            raise ConnectionClosedError(_close_code(error)) from None

    def __aiter__(self) -> AsyncIterator[str | bytes]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[str | bytes]:
        try:
            async for message in self._ws:
                yield message
        except websockets.exceptions.ConnectionClosed as error:
            raise ConnectionClosedError(_close_code(error)) from None

    async def close(self) -> None:
        await self._ws.close()


class WebsocketsConnector:
    async def connect(self, url: str) -> Connection:
        try:
            ws = await websockets.connect(url, open_timeout=OPEN_TIMEOUT_S)
        except websockets.exceptions.ConnectionClosed as error:
            raise ConnectionClosedError(_close_code(error)) from None
        except (websockets.exceptions.WebSocketException, OSError, TimeoutError):
            raise ConnectionClosedError(None) from None
        return WebsocketsConnection(ws)


def build_handshake(api_key: str, keywords: Sequence[str], with_extras: bool) -> str:
    message: dict[str, object] = {
        "authorization": {"accessToken": f"Bearer {api_key}"},
        "audioEncoding": "PCM_24KHZ",
        "model": MetaModel.VOICE.value,
        "mode": "DIARIZATION",
        "partialMode": "CUMULATIVE",
        "emitAudioProgress": False,
    }
    if with_extras:
        message["languageBias"] = ["English", "Tagalog"]
        message["keywords"] = list(keywords)
    return json.dumps(message)


def _id_field(event: dict[str, object], key: str) -> str | None:
    value = event.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()[:MAX_ID_CHARS]
    return None


def _first_id(event: dict[str, object], keys: Sequence[str]) -> str | None:
    for key in keys:
        found = _id_field(event, key)
        if found is not None:
            return found
    return None


def _text_field(event: dict[str, object]) -> str | None:
    for key in TEXT_KEYS:
        value = event.get(key)
        if isinstance(value, str):
            return value.strip()[:MAX_TEXT_CHARS]
    return None


class VoiceSession:
    def __init__(
        self,
        api_key: str,
        keywords: Sequence[str],
        microphone_factory: Callable[[], Microphone],
        connector: Connector,
        on_caption: Callable[[Caption], None],
        on_final: Callable[[Caption], None],
        on_overlap: Callable[[], None],
        on_status: Callable[[VoiceStatus], None],
        meter: CostMeter,
        clock: Callable[[], float],
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._api_key = api_key
        self._keywords = tuple(keywords)
        self._microphone_factory = microphone_factory
        self._connector = connector
        self._on_caption = on_caption
        self._on_final = on_final
        self._on_overlap = on_overlap
        self._on_status = on_status
        self._meter = meter
        self._clock = clock
        self._sleep = sleep
        self._status = VoiceStatus.OFF
        self._mode = VoiceMode.OPEN
        self._is_ptt_down = False
        self._stop = asyncio.Event()
        self._with_extras = True
        self._is_hard_stopped = False
        self._has_received = False
        self._mark = 0.0
        self._open: dict[str, str | None] = {}
        self._tainted: set[str] = set()

    @property
    def status(self) -> VoiceStatus:
        return self._status

    @property
    def mode(self) -> VoiceMode:
        return self._mode

    def set_mode(self, mode: VoiceMode) -> None:
        self._mode = mode

    def set_ptt(self, is_down: bool) -> None:
        self._is_ptt_down = is_down

    def stop(self) -> None:
        self._stop.set()

    def _set_status(self, status: VoiceStatus) -> None:
        if status is self._status:
            return
        self._status = status
        self._on_status(status)

    async def run(self) -> None:
        try:
            await self._run_loop()
        finally:
            if self._status is not VoiceStatus.DOWN:
                self._set_status(VoiceStatus.OFF)

    async def _run_loop(self) -> None:
        failures = 0
        while not self._stop.is_set():
            try:
                self._meter.ensure_can_spend()
            except BudgetExceededError:
                self._set_status(VoiceStatus.DOWN)
                return
            self._set_status(VoiceStatus.CONNECTING)
            self._has_received = False
            try:
                code = await self._connect_and_stream()
            except MicrophoneError:
                logger.warning("voice microphone unavailable")
                self._set_status(VoiceStatus.DOWN)
                return
            if self._is_hard_stopped:
                self._set_status(VoiceStatus.DOWN)
                return
            if self._stop.is_set() or code == CLOSE_NORMAL:
                return
            logger.warning("voice connection ended code=%s", code)
            if code == CLOSE_POLICY:
                if not self._with_extras:
                    self._set_status(VoiceStatus.DOWN)
                    return
                self._with_extras = False
                continue
            if self._has_received:
                failures = 0
            failures += 1
            if failures >= MAX_FAILURES:
                self._set_status(VoiceStatus.DOWN)
                return
            await self._sleep(BACKOFF_S[failures - 1])

    async def _connect_and_stream(self) -> int | None:
        url = f"{META_REALTIME_URL}?sessionId=desktop-{uuid.uuid4()}"
        try:
            conn = await self._connector.connect(url)
        except ConnectionClosedError as error:
            return error.code
        except (OSError, TimeoutError):
            return None
        try:
            await conn.send(
                build_handshake(self._api_key, self._keywords, self._with_extras)
            )
        except ConnectionClosedError as error:
            await self._close_quietly(conn)
            return error.code
        except OSError:
            await self._close_quietly(conn)
            return None
        self._open.clear()
        self._tainted.clear()
        self._set_status(VoiceStatus.LISTENING)
        return await self._drive(conn)

    async def _drive(self, conn: Connection) -> int | None:
        mic = self._microphone_factory()
        self._mark = self._clock()
        sender = asyncio.create_task(self._send_audio(conn, mic))
        receiver = asyncio.create_task(self._receive(conn))
        stopper = asyncio.create_task(self._stop.wait())
        pending: set[asyncio.Task[Any]] = {sender, receiver, stopper}
        try:
            while True:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                if stopper in done or self._stop.is_set():
                    return CLOSE_NORMAL
                if receiver in done:
                    return self._code_of(receiver)
                if sender in done:
                    error = sender.exception()
                    if error is None:
                        continue
                    if isinstance(error, ConnectionClosedError):
                        return error.code
                    raise error
        finally:
            for task in (sender, receiver, stopper):
                task.cancel()
            await asyncio.gather(sender, receiver, stopper, return_exceptions=True)
            await self._finish(conn, mic)

    @staticmethod
    def _code_of(task: "asyncio.Task[None]") -> int | None:
        error = task.exception()
        if error is None:
            return CLOSE_NORMAL
        if isinstance(error, ConnectionClosedError):
            return error.code
        raise error

    async def _finish(self, conn: Connection, mic: Microphone) -> None:
        if self._stop.is_set():
            try:
                await conn.send(json.dumps({"type": "endStream"}))
            except (ConnectionClosedError, OSError):
                pass
        await self._close_quietly(conn)
        await mic.close()
        elapsed = self._clock() - self._mark
        if elapsed > 0:
            self._record_seconds(math.ceil(elapsed))
            self._mark = self._clock()
        if self._meter.is_stopped:
            self._is_hard_stopped = True

    @staticmethod
    async def _close_quietly(conn: Connection) -> None:
        try:
            await conn.close()
        except (ConnectionClosedError, OSError):
            pass

    def _record_seconds(self, seconds: int) -> None:
        self._meter.record(
            ApiUsageRecord(
                model=MetaModel.VOICE.value,
                kind="voice",
                cost_usd=price_voice_seconds(seconds),
                ok=True,
                audio_seconds=seconds,
            )
        )

    def _tick_cost(self) -> None:
        now = self._clock()
        while now - self._mark >= COST_INTERVAL_S:
            self._record_seconds(int(COST_INTERVAL_S))
            self._mark += COST_INTERVAL_S
        if self._meter.is_stopped:
            self._is_hard_stopped = True
            self._stop.set()

    def _next_payload(self, frame: bytes) -> bytes:
        if self._mode is VoiceMode.PTT and not self._is_ptt_down:
            return SILENCE_FRAME
        return frame

    async def _send_audio(self, conn: Connection, mic: Microphone) -> None:
        async for frame in mic:
            await conn.send(self._next_payload(frame))
            self._tick_cost()
            if self._stop.is_set():
                return
        await conn.send(json.dumps({"type": "endStream"}))

    async def _receive(self, conn: Connection) -> None:
        async for message in conn:
            self._has_received = True
            if isinstance(message, str):
                self._handle_message(message)

    def _handle_message(self, raw: str) -> None:
        try:
            event = json.loads(raw)
        except ValueError:
            return
        if not isinstance(event, dict):
            return
        kind = event.get("type")
        if kind == "speechStart":
            self._on_speech_start(event)
        elif kind == "transcript":
            self._on_transcript(event)
        elif kind == "speaker":
            self._on_speaker(event)
        elif kind == "speechComplete":
            self._on_speech_complete(event)
        elif kind == "error":
            logger.warning("voice error event received")

    def _current_turn(self, event: dict[str, object]) -> str | None:
        turn = _id_field(event, "turnId")
        if turn is not None:
            return turn
        if self._open:
            return next(reversed(self._open))
        return None

    def _on_speech_start(self, event: dict[str, object]) -> None:
        turn = _id_field(event, "turnId")
        if turn is None or turn in self._open:
            return
        if self._open:
            if not self._tainted & self._open.keys():
                self._on_overlap()
            self._tainted.update(self._open)
            self._tainted.add(turn)
        if len(self._open) >= MAX_OPEN_TURNS:
            self._open.pop(next(iter(self._open)))
        self._open[turn] = None

    def _on_transcript(self, event: dict[str, object]) -> None:
        turn = self._current_turn(event)
        text = _text_field(event)
        if turn is None or text is None:
            return
        self._on_caption(Caption(turn, text, False, self._open.get(turn)))

    def _on_speaker(self, event: dict[str, object]) -> None:
        turn = self._current_turn(event)
        label = _first_id(event, SPEAKER_KEYS)
        if turn is None or label is None or turn not in self._open:
            return
        self._open[turn] = label

    def _on_speech_complete(self, event: dict[str, object]) -> None:
        turn = self._current_turn(event)
        text = _text_field(event)
        if turn is None or not text:
            return
        label = self._open.pop(turn, None) or _first_id(event, SPEAKER_KEYS)
        if turn in self._tainted:
            self._tainted.discard(turn)
            return
        caption = Caption(turn, text, True, label)
        self._on_caption(caption)
        self._on_final(caption)

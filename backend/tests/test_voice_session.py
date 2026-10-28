import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, ClassVar

import pytest

from config import META_REALTIME_URL, MetaModel
from db.store import ApiUsageRecord
from meta_client import CostMeter, price_voice_seconds
from voice.session import (
    FRAME_BYTES,
    SILENCE_FRAME,
    Caption,
    ConnectionClosedError,
    Microphone,
    MicrophoneError,
    SoundDeviceMicrophone,
    VoiceMode,
    VoiceSession,
    VoiceStatus,
)

API_KEY = "sk-test-secret-key-123"
KEYWORDS = ["tapos", "hindi", "kubo", "Spearman"]
FRAME = bytes([1]) * FRAME_BYTES


class MemoryLog:
    def __init__(self, starting_total: Decimal = Decimal(0)) -> None:
        self.records: list[ApiUsageRecord] = []
        self._starting = starting_total

    def record_api_usage(self, record: ApiUsageRecord) -> None:
        self.records.append(record)

    def total_api_cost(self) -> Decimal:
        return self._starting + sum((r.cost_usd for r in self.records), Decimal(0))


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class FakeMic:
    def __init__(
        self,
        total: int | None = 3,
        on_frame: Callable[[int], None] | None = None,
        error: bool = False,
    ) -> None:
        self.total = total
        self.on_frame = on_frame
        self.error = error
        self.is_closed = False

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self._generate()

    async def _generate(self) -> AsyncIterator[bytes]:
        if self.error:
            raise MicrophoneError("no device")
        index = 0
        while not self.is_closed and (self.total is None or index < self.total):
            if self.on_frame is not None:
                self.on_frame(index)
            yield FRAME
            index += 1
            await asyncio.sleep(0)

    async def close(self) -> None:
        self.is_closed = True


class FakeConnection:
    def __init__(
        self,
        script: list[str | ConnectionClosedError] | None = None,
        gate: int = 0,
        hang: bool = False,
        stops_at_end: bool = True,
    ) -> None:
        self.script = script or []
        self.gate = gate
        self.hang = hang
        self.stops_at_end = stops_at_end
        self.on_end: Callable[[], None] | None = None
        self.sent: list[str | bytes] = []
        self.is_closed = False

    @property
    def audio(self) -> list[bytes]:
        return [m for m in self.sent if isinstance(m, bytes)]

    @property
    def text(self) -> list[str]:
        return [m for m in self.sent if isinstance(m, str)]

    async def send(self, data: str | bytes) -> None:
        self.sent.append(data)

    def __aiter__(self) -> AsyncIterator[str | bytes]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[str | bytes]:
        while len(self.audio) < self.gate:
            await asyncio.sleep(0)
        for item in self.script:
            await asyncio.sleep(0)
            if isinstance(item, ConnectionClosedError):
                raise item
            yield item
        if self.stops_at_end and not self.hang and self.on_end is not None:
            self.on_end()
        if self.hang:
            await asyncio.Event().wait()

    async def close(self) -> None:
        self.is_closed = True


class FakeConnector:
    def __init__(self, plan: list[FakeConnection | Exception]) -> None:
        self.plan = plan
        self.urls: list[str] = []

    async def connect(self, url: str) -> FakeConnection:
        self.urls.append(url)
        item = self.plan.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def event(kind: str, **fields: object) -> str:
    return json.dumps({"type": kind, **fields})


@dataclass
class Recorder:
    captions: list[Caption] = field(default_factory=list)
    finals: list[Caption] = field(default_factory=list)
    overlaps: int = 0
    statuses: list[VoiceStatus] = field(default_factory=list)
    sleeps: list[float] = field(default_factory=list)


@dataclass
class Harness:
    session: VoiceSession
    rec: Recorder
    connector: FakeConnector
    log: MemoryLog
    meter: CostMeter
    clock: FakeClock


def make_harness(
    plan: list[FakeConnection | Exception],
    mic_factory: Callable[[], Microphone] | None = None,
    meter_stop_usd: Decimal | None = None,
    overrides: dict[str, Any] | None = None,
    log: MemoryLog | None = None,
) -> Harness:
    rec = Recorder()
    log = log or MemoryLog()
    meter = (
        CostMeter(log)
        if meter_stop_usd is None
        else CostMeter(log, stop_usd=meter_stop_usd)
    )
    clock = FakeClock()
    connector = FakeConnector(plan)

    async def fake_sleep(seconds: float) -> None:
        rec.sleeps.append(seconds)

    def on_overlap() -> None:
        rec.overlaps += 1

    options: dict[str, Any] = {
        "api_key": API_KEY,
        "keywords": KEYWORDS,
        "microphone_factory": mic_factory or (lambda: FakeMic()),
        "connector": connector,
        "on_caption": rec.captions.append,
        "on_final": rec.finals.append,
        "on_overlap": on_overlap,
        "on_status": rec.statuses.append,
        "meter": meter,
        "clock": clock,
        "sleep": fake_sleep,
    }
    options.update(overrides or {})
    session = VoiceSession(**options)
    for item in plan:
        if isinstance(item, FakeConnection):
            item.on_end = session.stop
    return Harness(session, rec, connector, log, meter, clock)


def run(harness: Harness) -> None:
    asyncio.run(asyncio.wait_for(harness.session.run(), timeout=5))


def gated(script: list[str | ConnectionClosedError], gate: int = 3) -> FakeConnection:
    return FakeConnection(script, gate=gate)


def test_frame_is_80ms_of_int16_mono() -> None:
    assert FRAME_BYTES == 3_840
    assert SILENCE_FRAME == bytes(3_840)


def test_handshake_fields_and_url() -> None:
    conn = gated([])
    h = make_harness([conn])
    run(h)
    handshake = json.loads(conn.text[0])
    assert handshake["authorization"] == {"accessToken": f"Bearer {API_KEY}"}
    assert handshake["audioEncoding"] == "PCM_24KHZ"
    assert handshake["model"] == MetaModel.VOICE.value
    assert handshake["mode"] == "DIARIZATION"
    assert handshake["partialMode"] == "CUMULATIVE"
    assert handshake["emitAudioProgress"] is False
    assert handshake["languageBias"] == ["English", "Tagalog"]
    assert handshake["keywords"] == KEYWORDS
    assert h.connector.urls[0].startswith(f"{META_REALTIME_URL}?sessionId=desktop-")
    assert conn.audio == [FRAME] * 3
    assert h.rec.statuses == [
        VoiceStatus.CONNECTING,
        VoiceStatus.LISTENING,
        VoiceStatus.OFF,
    ]


def test_key_and_handshake_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    conn = gated([event("error", message=f"bad {API_KEY}"), "not json"])
    h = make_harness([conn, FakeConnection([ConnectionClosedError(1011)])])
    run(h)
    assert API_KEY not in caplog.text
    assert "Bearer" not in caplog.text
    assert "accessToken" not in caplog.text
    assert "languageBias" not in caplog.text


def test_partials_replace_and_final_fires_once() -> None:
    conn = gated(
        [
            event("speechStart", turnId="t1"),
            event("transcript", turnId="t1", text="Spear"),
            event("transcript", turnId="t1", text="Spearman saksa"),
            event("speechComplete", turnId="t1", text="Spearman saksakin ang aswang"),
        ]
    )
    h = make_harness([conn])
    run(h)
    assert [(c.text, c.is_final) for c in h.rec.captions] == [
        ("Spear", False),
        ("Spearman saksa", False),
        ("Spearman saksakin ang aswang", True),
    ]
    assert len(h.rec.finals) == 1
    assert h.rec.finals[0].turn_id == "t1"
    assert h.rec.finals[0].text == "Spearman saksakin ang aswang"


def test_speaker_label_attaches_to_open_turn() -> None:
    conn = gated(
        [
            event("speechStart", turnId="t1"),
            event("transcript", turnId="t1", text="Tapos"),
            event("speaker", turnId="t1", speaker="S2"),
            event("transcript", turnId="t1", text="Tapos na"),
            event("speechComplete", turnId="t1", text="Tapos na"),
        ]
    )
    h = make_harness([conn])
    run(h)
    assert [c.speaker for c in h.rec.captions] == [None, "S2", "S2"]
    assert h.rec.finals[0].speaker == "S2"


def test_speaker_event_without_turn_id_uses_latest_open_turn() -> None:
    conn = gated(
        [
            event("speechStart", turnId="t1"),
            event("speaker", speakerLabel="A"),
            event("speechComplete", turnId="t1", transcript="Hindi"),
        ]
    )
    h = make_harness([conn])
    run(h)
    assert h.rec.finals[0].speaker == "A"
    assert h.rec.finals[0].text == "Hindi"


def test_overlapping_turns_drop_both_finals_and_call_overlap_once() -> None:
    conn = gated(
        [
            event("speechStart", turnId="t1"),
            event("speechStart", turnId="t2"),
            event("speechComplete", turnId="t1", text="isa"),
            event("speechComplete", turnId="t2", text="dalawa"),
            event("speechStart", turnId="t3"),
            event("speechComplete", turnId="t3", text="Tapos"),
        ]
    )
    h = make_harness([conn])
    run(h)
    assert h.rec.overlaps == 1
    assert [c.text for c in h.rec.finals] == ["Tapos"]
    dropped = [c for c in h.rec.captions if c.turn_id in ("t1", "t2")]
    assert [(c.turn_id, c.text, c.is_final) for c in dropped] == [
        ("t1", "", True),
        ("t2", "", True),
    ]
    assert h.session._open == {}
    assert h.session._tainted == set()


def test_three_way_overlap_reports_once() -> None:
    conn = gated(
        [
            event("speechStart", turnId="a"),
            event("speechStart", turnId="b"),
            event("speechStart", turnId="c"),
            event("speechComplete", turnId="a", text="x"),
            event("speechComplete", turnId="b", text="y"),
            event("speechComplete", turnId="c", text="z"),
        ]
    )
    h = make_harness([conn])
    run(h)
    assert h.rec.overlaps == 1
    assert h.rec.finals == []


def test_untrusted_events_are_ignored_safely() -> None:
    conn = gated(
        [
            "not json",
            "[1, 2]",
            "42",
            event("transcript", text="orphan"),
            event("speechStart"),
            event("speechStart", turnId=True),
            event("speechStart", turnId="t1"),
            event("transcript", turnId="t1", text=["x"]),
            event("speechComplete", turnId="t1", text="   "),
            event("unknown", turnId="t1"),
            event("speechEnd", turnId="t1"),
        ]
    )
    h = make_harness([conn])
    run(h)
    assert h.rec.captions == [Caption("t1", "", True, None)]
    assert h.rec.finals == []
    assert h.rec.overlaps == 0
    assert h.session._open == {}


def test_long_text_is_truncated() -> None:
    conn = gated(
        [
            event("speechStart", turnId="t1"),
            event("speechComplete", turnId="t1", text="x" * 50_000),
        ]
    )
    h = make_harness([conn])
    run(h)
    assert len(h.rec.finals[0].text) == 2_000


def test_ptt_sends_silence_until_held_and_switch_back_to_open() -> None:
    holder: dict[str, VoiceSession] = {}

    def on_frame(index: int) -> None:
        session = holder["session"]
        if index == 0:
            session.set_mode(VoiceMode.PTT)
        elif index == 1:
            session.set_ptt(True)
        elif index == 2:
            session.set_ptt(False)
        elif index == 3:
            session.set_mode(VoiceMode.OPEN)

    conn = gated([], gate=5)
    h = make_harness([conn], lambda: FakeMic(total=5, on_frame=on_frame))
    holder["session"] = h.session
    assert h.session.mode is VoiceMode.OPEN
    run(h)
    assert conn.audio == [SILENCE_FRAME, FRAME, SILENCE_FRAME, FRAME, FRAME]
    assert h.session.mode is VoiceMode.OPEN


def test_ptt_silence_frames_have_full_frame_size() -> None:
    conn = gated([], gate=3)
    h = make_harness([conn])
    h.session.set_mode(VoiceMode.PTT)
    run(h)
    assert len(conn.audio) == 3
    assert all(len(frame) == FRAME_BYTES and not any(frame) for frame in conn.audio)


def test_1008_retries_once_without_extras_then_remembers() -> None:
    first = FakeConnection([ConnectionClosedError(1008)])
    second = gated([])
    h = make_harness([first, second])
    run(h)
    assert "languageBias" in json.loads(first.text[0])
    retry = json.loads(second.text[0])
    assert "languageBias" not in retry
    assert "keywords" not in retry
    assert h.rec.sleeps == []
    assert h.session.status is VoiceStatus.OFF


def test_1008_after_retry_is_down_without_blind_retry() -> None:
    plan: list[FakeConnection | Exception] = [
        FakeConnection([ConnectionClosedError(1008)]),
        FakeConnection([ConnectionClosedError(1008)]),
    ]
    h = make_harness(plan)
    run(h)
    assert len(h.connector.urls) == 2
    assert h.session.status is VoiceStatus.DOWN
    assert h.rec.statuses[-1] is VoiceStatus.DOWN


@pytest.mark.parametrize("code", [1011, 1013])
def test_retries_with_backoff_then_gives_up_after_three(code: int) -> None:
    plan: list[FakeConnection | Exception] = [
        FakeConnection([ConnectionClosedError(code)]) for _ in range(3)
    ]
    h = make_harness(plan)
    run(h)
    assert len(h.connector.urls) == 3
    assert h.rec.sleeps == [0.5, 1.0]
    assert h.session.status is VoiceStatus.DOWN


def test_connection_errors_retry_and_give_up() -> None:
    plan: list[FakeConnection | Exception] = [
        OSError("refused"),
        TimeoutError(),
        ConnectionClosedError(None),
    ]
    h = make_harness(plan)
    run(h)
    assert len(h.connector.urls) == 3
    assert h.rec.sleeps == [0.5, 1.0]
    assert h.session.status is VoiceStatus.DOWN


def test_recovery_after_failures_resets_the_count() -> None:
    plan: list[FakeConnection | Exception] = [
        OSError("refused"),
        FakeConnection(
            [event("speechStart", turnId="t1"), ConnectionClosedError(1011)]
        ),
        OSError("refused"),
        gated([]),
    ]
    h = make_harness(plan)
    run(h)
    assert len(h.connector.urls) == 4
    assert h.rec.sleeps == [0.5, 0.5, 1.0]
    assert h.session.status is VoiceStatus.OFF


def test_session_limit_close_reconnects() -> None:
    first = FakeConnection(
        [event("speechStart", turnId="t1"), ConnectionClosedError(1011)]
    )
    second = gated([])
    h = make_harness([first, second])
    run(h)
    assert len(h.connector.urls) == 2
    assert h.rec.sleeps == [0.5]
    assert h.session.status is VoiceStatus.OFF


def test_unexpected_normal_close_reconnects_with_backoff() -> None:
    plan: list[FakeConnection | Exception] = [
        FakeConnection([ConnectionClosedError(1000)]) for _ in range(3)
    ]
    h = make_harness(plan)
    run(h)
    assert len(h.connector.urls) == 3
    assert h.rec.sleeps == [0.5, 1.0]
    assert h.session.status is VoiceStatus.DOWN


def test_iterator_ending_without_stop_reconnects() -> None:
    first = FakeConnection([], stops_at_end=False)
    second = gated([])
    h = make_harness([first, second])
    run(h)
    assert len(h.connector.urls) == 2
    assert h.rec.sleeps == [0.5]
    assert h.session.status is VoiceStatus.OFF


def test_stop_makes_a_normal_close_expected() -> None:
    h = make_harness([gated([])])
    run(h)
    assert len(h.connector.urls) == 1
    assert h.rec.sleeps == []
    assert h.session.status is VoiceStatus.OFF


def test_cost_recorded_every_sixty_seconds_and_at_close() -> None:
    clock_holder: dict[str, FakeClock] = {}

    def on_frame(index: int) -> None:
        clock_holder["clock"].now += 30.0

    conn = gated([], gate=5)
    h = make_harness([conn], lambda: FakeMic(total=5, on_frame=on_frame))
    clock_holder["clock"] = h.clock
    run(h)
    assert [r.audio_seconds for r in h.log.records] == [60, 60, 30]
    for record in h.log.records:
        assert record.model == MetaModel.VOICE.value
        assert record.kind == "voice"
        assert record.ok is True
        assert record.audio_seconds is not None
        assert record.cost_usd == price_voice_seconds(record.audio_seconds)


def test_cost_recorded_on_stop() -> None:
    clock_holder: dict[str, FakeClock] = {}
    holder: dict[str, VoiceSession] = {}

    def on_frame(index: int) -> None:
        clock_holder["clock"].now += 10.0
        if index == 3:
            holder["session"].stop()

    conn = FakeConnection([], hang=True)
    h = make_harness([conn], lambda: FakeMic(total=None, on_frame=on_frame))
    clock_holder["clock"] = h.clock
    holder["session"] = h.session
    run(h)
    assert [r.audio_seconds for r in h.log.records] == [40]
    assert json.loads(conn.text[-1]) == {"type": "endStream"}
    assert conn.is_closed
    assert h.session.status is VoiceStatus.OFF


def test_hard_stop_ends_the_session_with_status_down() -> None:
    clock_holder: dict[str, FakeClock] = {}

    def on_frame(index: int) -> None:
        clock_holder["clock"].now += 30.0

    conn = FakeConnection([], hang=True)
    h = make_harness(
        [conn],
        lambda: FakeMic(total=None, on_frame=on_frame),
        meter_stop_usd=Decimal("0.002"),
    )
    clock_holder["clock"] = h.clock
    run(h)
    assert h.meter.is_stopped
    assert len(h.log.records) == 1
    assert h.session.status is VoiceStatus.DOWN
    assert len(h.connector.urls) == 1
    assert conn.is_closed


def test_budget_exceeded_before_connect_is_down_without_connecting() -> None:
    h = make_harness([gated([])])
    h.meter.force_stop()
    run(h)
    assert h.connector.urls == []
    assert h.session.status is VoiceStatus.DOWN
    assert h.rec.statuses == [VoiceStatus.DOWN]


def test_microphone_failure_is_down() -> None:
    h = make_harness([FakeConnection(hang=True)], lambda: FakeMic(error=True))
    run(h)
    assert h.session.status is VoiceStatus.DOWN
    assert len(h.connector.urls) == 1


def test_stop_before_run_returns_immediately() -> None:
    h = make_harness([])
    h.session.stop()
    run(h)
    assert h.connector.urls == []
    assert h.session.status is VoiceStatus.OFF


def test_empty_final_clears_the_stuck_partial_and_closes_the_turn() -> None:
    conn = gated(
        [
            event("speechStart", turnId="t1"),
            event("transcript", turnId="t1", text="Spear"),
            event("speaker", turnId="t1", speaker="S1"),
            event("speechComplete", turnId="t1", text=""),
        ]
    )
    h = make_harness([conn])
    run(h)
    assert h.rec.captions[-1] == Caption("t1", "", True, "S1")
    assert h.rec.finals == []
    assert h.session._open == {}
    assert h.session._tainted == set()


def test_empty_final_of_a_tainted_turn_clears_the_tainted_mark() -> None:
    conn = gated(
        [
            event("speechStart", turnId="t1"),
            event("speechStart", turnId="t2"),
            event("speechComplete", turnId="t1", text=""),
            event("speechComplete", turnId="t2", text="dalawa"),
        ]
    )
    h = make_harness([conn])
    run(h)
    assert h.session._tainted == set()
    assert h.rec.finals == []
    assert [c.turn_id for c in h.rec.captions] == ["t1", "t2"]
    assert all(c.is_final and c.text == "" for c in h.rec.captions)


def test_callback_exceptions_are_logged_by_type_and_do_not_kill_run(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    finals: list[Caption] = []

    def bad_caption(caption: Caption) -> None:
        raise RuntimeError("secret transcript text")

    def bad_overlap() -> None:
        raise ValueError("overlap secret")

    def bad_status(status: VoiceStatus) -> None:
        raise KeyError("status secret")

    conn = gated(
        [
            event("speechStart", turnId="t1"),
            event("speechStart", turnId="t2"),
            event("transcript", turnId="t1", text="hello"),
            event("speechComplete", turnId="t1", text="x"),
            event("speechComplete", turnId="t2", text="y"),
            event("speechStart", turnId="t3"),
            event("speechComplete", turnId="t3", text="Tapos"),
        ]
    )
    h = make_harness(
        [conn],
        overrides={
            "on_caption": bad_caption,
            "on_final": finals.append,
            "on_overlap": bad_overlap,
            "on_status": bad_status,
        },
    )
    run(h)
    assert [c.text for c in finals] == ["Tapos"]
    assert h.session.status is VoiceStatus.OFF
    assert "RuntimeError" in caplog.text
    assert "ValueError" in caplog.text
    assert "KeyError" in caplog.text
    assert "secret" not in caplog.text
    assert "Traceback" not in caplog.text


def test_final_callback_exception_does_not_kill_run() -> None:
    def bad_final(caption: Caption) -> None:
        raise RuntimeError("boom")

    conn = gated(
        [
            event("speechStart", turnId="t1"),
            event("speechComplete", turnId="t1", text="Tapos"),
            event("speechStart", turnId="t2"),
            event("speechComplete", turnId="t2", text="Hindi"),
        ]
    )
    h = make_harness([conn], overrides={"on_final": bad_final})
    run(h)
    assert [c.text for c in h.rec.captions] == ["Tapos", "Hindi"]


def test_microphone_is_closed_on_every_connection_end() -> None:
    mics: list[FakeMic] = []

    def factory() -> Microphone:
        mic = FakeMic(total=2)
        mics.append(mic)
        return mic

    plan: list[FakeConnection | Exception] = [
        FakeConnection([ConnectionClosedError(1011)]),
        FakeConnection([ConnectionClosedError(1013)]),
        gated([], gate=2),
    ]
    h = make_harness(plan, factory)
    run(h)
    assert len(mics) == 3
    assert all(mic.is_closed for mic in mics)


def test_microphone_is_closed_when_the_mic_errors() -> None:
    mics: list[FakeMic] = []

    def factory() -> Microphone:
        mic = FakeMic(error=True)
        mics.append(mic)
        return mic

    conn = FakeConnection(hang=True)
    h = make_harness([conn], factory)
    run(h)
    assert mics[0].is_closed
    assert conn.is_closed


def test_microphone_factory_failure_is_down_and_closes_the_connection() -> None:
    def factory() -> Microphone:
        raise OSError("no device")

    conn = FakeConnection(hang=True)
    h = make_harness([conn], factory)
    run(h)
    assert h.session.status is VoiceStatus.DOWN
    assert conn.is_closed


class StallMic:
    def __init__(self) -> None:
        self.is_closed = False

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self._generate()

    async def _generate(self) -> AsyncIterator[bytes]:
        yield FRAME
        await asyncio.Event().wait()

    async def close(self) -> None:
        self.is_closed = True


def test_mic_stall_while_listening_is_down_and_ends_run() -> None:
    mic = StallMic()
    conn = FakeConnection(hang=True)
    h = make_harness([conn], lambda: mic, overrides={"mic_timeout_s": 0.05})
    run(h)
    assert h.session.status is VoiceStatus.DOWN
    assert h.rec.statuses[-1] is VoiceStatus.DOWN
    assert mic.is_closed
    assert conn.is_closed
    assert len(h.connector.urls) == 1


class ExplodingLog(MemoryLog):
    def record_api_usage(self, record: ApiUsageRecord) -> None:
        raise RuntimeError("disk full secret")


def test_cost_record_failure_is_logged_by_type_and_session_survives(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    clock_holder: dict[str, FakeClock] = {}

    def on_frame(index: int) -> None:
        clock_holder["clock"].now += 30.0

    conn = gated([], gate=5)
    h = make_harness(
        [conn],
        lambda: FakeMic(total=5, on_frame=on_frame),
        log=ExplodingLog(),
    )
    clock_holder["clock"] = h.clock
    run(h)
    assert conn.audio == [FRAME] * 5
    assert h.session.status is VoiceStatus.OFF
    assert "RuntimeError" in caplog.text
    assert "secret" not in caplog.text


def test_stop_during_backoff_returns_promptly() -> None:
    async def never(seconds: float) -> None:
        await asyncio.Event().wait()

    h = make_harness(
        [FakeConnection([ConnectionClosedError(1011)])],
        overrides={"sleep": never},
    )

    async def scenario() -> None:
        task = asyncio.create_task(h.session.run())
        await asyncio.sleep(0.05)
        assert not task.done()
        h.session.stop()
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())
    assert len(h.connector.urls) == 1
    assert h.session.status is VoiceStatus.OFF


class HangingConnector:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.was_cancelled = False

    async def connect(self, url: str) -> FakeConnection:
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.was_cancelled = True
            raise
        raise AssertionError("unreachable")


def test_stop_aborts_a_pending_connect() -> None:
    async def scenario() -> HangingConnector:
        connector = HangingConnector()
        h = make_harness([], overrides={"connector": connector})
        task = asyncio.create_task(h.session.run())
        await asyncio.wait_for(connector.started.wait(), timeout=1)
        h.session.stop()
        await asyncio.wait_for(task, timeout=1)
        assert h.session.status is VoiceStatus.OFF
        return connector

    assert asyncio.run(scenario()).was_cancelled


class FakeStream:
    instances: ClassVar[list["FakeStream"]] = []
    fail_on_start = False

    def __init__(self, **kwargs: object) -> None:
        self.stops = 0
        self.closes = 0
        FakeStream.instances.append(self)

    def start(self) -> None:
        if FakeStream.fail_on_start:
            raise OSError("no device")

    def stop(self) -> None:
        self.stops += 1

    def close(self) -> None:
        self.closes += 1


@pytest.fixture
def fake_stream(monkeypatch: pytest.MonkeyPatch) -> type[FakeStream]:
    FakeStream.instances = []
    FakeStream.fail_on_start = False
    monkeypatch.setattr("voice.session.sounddevice.RawInputStream", FakeStream)
    return FakeStream


def test_sounddevice_close_stops_and_closes_the_stream_idempotently(
    fake_stream: type[FakeStream],
) -> None:
    async def scenario() -> None:
        mic = SoundDeviceMicrophone()
        task = asyncio.ensure_future(anext(mic.__aiter__()))
        await asyncio.sleep(0.01)
        assert len(fake_stream.instances) == 1
        await mic.close()
        await mic.close()
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())
    stream = fake_stream.instances[0]
    assert stream.stops == 1
    assert stream.closes == 1


def test_sounddevice_start_failure_closes_the_stream(
    fake_stream: type[FakeStream],
) -> None:
    fake_stream.fail_on_start = True

    async def scenario() -> None:
        mic = SoundDeviceMicrophone()
        with pytest.raises(MicrophoneError):
            await anext(mic.__aiter__())

    asyncio.run(scenario())
    stream = fake_stream.instances[0]
    assert stream.stops == 1
    assert stream.closes == 1


def test_sounddevice_close_before_start_is_safe(
    fake_stream: type[FakeStream],
) -> None:
    async def scenario() -> list[bytes]:
        mic = SoundDeviceMicrophone()
        await mic.close()
        await mic.close()
        return [frame async for frame in mic]

    assert asyncio.run(scenario()) == []
    assert fake_stream.instances == []

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import pytest
from meta_sam_parser import (
    FrameReference,
    SegmentationBoxRecord,
    SegmentationMask,
    SegmentationMaskBounds,
    SegmentationMaskIdentity,
    SegmentationMaskRecord,
    SegmentationRecord,
)

from config import CallKind, MetaModel
from db.store import ApiUsageRecord
from meta_client import CostMeter, MetaClient, MetaRequestError, create_openai_client
from vision.sam import (
    SAM_VIDEO_METADATA,
    SamVideoTracker,
    SegmentationError,
    TrackBox,
    build_video_prompt,
    tracks_from_records,
)

SOURCE = (1920, 1080)
PROXY = (960, 540)


@dataclass
class MemoryLog:
    records: list[ApiUsageRecord] = field(default_factory=list)

    def record_api_usage(self, record: ApiUsageRecord) -> None:
        self.records.append(record)

    def total_api_cost(self) -> Decimal:
        return Decimal(0)


def record_line(frame: int, entries: dict[int, tuple[int, int, int, int]]) -> str:
    width, height = PROXY
    parts = []
    for sam_id, (left, top, right, bottom) in entries.items():
        mask_w, mask_h = right - left, bottom - top
        parts.append(
            f"{sam_id}<|box;x1={left};y1={top};x2={right - 1};y2={bottom - 1};"
            f"w={width};h={height};c=0.9|>"
            f"<|mask;x=0;y=0;data={mask_h},{mask_w},!{'0' * 5};c=0.9|>"
        )
    return f"<{frame}f>" + ",".join(parts) + "\n"


def stream_events(text: str, split: int = 40) -> list[dict[str, Any]]:
    lane = {"item_id": "msg_1", "output_index": 0, "content_index": 0}
    events: list[dict[str, Any]] = [
        {"type": "response.output_text.delta", "delta": text[i : i + split], **lane}
        for i in range(0, len(text), split)
    ]
    events.append({"type": "response.output_text.done", "text": text, **lane})
    events.append({"type": "response.completed"})
    return events


class FakeStream:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.events = events

    def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        async def generate() -> AsyncIterator[dict[str, Any]]:
            for event in self.events:
                yield event

        return generate()


class FakeResponses:
    def __init__(self, events: list[dict[str, Any]] | Exception) -> None:
        self.events = events
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> FakeStream:
        self.calls.append(kwargs)
        if isinstance(self.events, Exception):
            raise self.events
        return FakeStream(self.events)


class FakeClient(MetaClient):
    def __init__(self, responses: FakeResponses) -> None:
        self.log = MemoryLog()
        super().__init__(create_openai_client("test-key"), CostMeter(self.log))
        self.sdk_fake = type("Sdk", (), {"responses": responses})()

    def sdk(self) -> Any:
        return self.sdk_fake


PROMPTS = {
    0: {"u_1": (0, 0, 200, 100), "u_2": (400, 400, 600, 500)},
    80: {"u_1": (100, 100, 300, 200)},
}


def run_track(client: FakeClient) -> dict[str, tuple[TrackBox, ...]]:
    return asyncio.run(
        SamVideoTracker(client).track(
            "file_1", [0, 80], PROMPTS, source_size=SOURCE, proxy_size=PROXY
        )
    )


def test_prompt_has_one_marker_per_segment_in_proxy_pixels() -> None:
    text = build_video_prompt({1: "u_1", 2: "u_2"}, [0, 80], PROMPTS, SOURCE, PROXY)
    assert text.startswith("<0f>1<|box;")
    assert "<80f>1<|box;" in text
    assert text.count("<0f>") == 1 and text.count("<80f>") == 1
    assert "w=960;h=540" in text
    assert "x1=0;y1=0;x2=99;y2=49" in text


def test_tracker_sends_one_streaming_video_request() -> None:
    line0 = record_line(0, {1: (0, 0, 100, 50), 2: (200, 200, 300, 250)})
    responses = FakeResponses(stream_events(line0))
    client = FakeClient(responses)
    run_track(client)
    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert call["model"] == MetaModel.SAM.value
    assert call["stream"] is True
    assert call["store"] is False
    assert call["metadata"] == SAM_VIDEO_METADATA
    assert call["metadata"] == {
        "propagation_direction": "forward",
        "mask_encoding": "one_bit",
    }
    content = call["input"][0]["content"]
    assert content[1] == {"type": "input_video", "file_id": "file_1"}
    assert content[0]["text"].startswith("<0f>1<|box;")


def test_streamed_records_become_scaled_tracks_per_game_id() -> None:
    text = (
        record_line(0, {1: (0, 0, 100, 50), 2: (200, 200, 300, 250)})
        + record_line(1, {1: (10, 5, 110, 55)})
        + record_line(80, {2: (210, 210, 310, 260), 1: (100, 100, 200, 150)})
    )
    client = FakeClient(FakeResponses(stream_events(text)))
    tracks = run_track(client)
    assert set(tracks) == {"u_1", "u_2"}
    assert [box.frame for box in tracks["u_1"]] == [0, 1, 80]
    assert tracks["u_1"][0] == TrackBox(0, 0, 0, 200, 100)
    assert tracks["u_1"][1] == TrackBox(1, 20, 10, 220, 110)
    assert tracks["u_2"][0] == TrackBox(0, 400, 400, 600, 500)
    assert tracks["u_2"][1] == TrackBox(80, 420, 420, 620, 520)


def test_usage_is_logged_as_sam_video_frames() -> None:
    text = record_line(0, {1: (0, 0, 100, 50)}) + record_line(1, {1: (0, 0, 100, 50)})
    client = FakeClient(FakeResponses(stream_events(text)))
    run_track(client)
    assert [r.kind for r in client.log.records] == [CallKind.SAM_VIDEO.value]
    assert client.log.records[0].cost_usd == Decimal("0.2") / 1000 * 50


def test_empty_output_gives_no_tracks() -> None:
    client = FakeClient(FakeResponses(stream_events("")))
    assert run_track(client) == {}


def test_request_errors_propagate() -> None:
    error = MetaRequestError("bad", is_content_policy=False)
    client = FakeClient(FakeResponses(error))
    with pytest.raises(MetaRequestError):
        run_track(client)


@pytest.mark.parametrize(
    ("segments", "prompts"),
    [
        ([], PROMPTS),
        ([0, 80], {}),
        ([0], PROMPTS),
        ([-1, 0], {-1: {"a": (0, 0, 5, 5)}}),
        ([0], {0: {}}),
        ([0], {0: {f"u_{i}": (0, 0, 9, 9) for i in range(17)}}),
    ],
)
def test_bad_inputs_are_rejected_before_any_call(
    segments: list[int], prompts: dict[int, dict[str, tuple[int, int, int, int]]]
) -> None:
    responses = FakeResponses(stream_events(""))
    client = FakeClient(responses)
    with pytest.raises(SegmentationError):
        asyncio.run(
            SamVideoTracker(client).track(
                "file_1", segments, prompts, source_size=SOURCE, proxy_size=PROXY
            )
        )
    assert responses.calls == []


def test_empty_file_id_is_rejected() -> None:
    client = FakeClient(FakeResponses(stream_events("")))
    with pytest.raises(SegmentationError):
        asyncio.run(
            SamVideoTracker(client).track(
                "", [0], {0: {"a": (0, 0, 5, 5)}}, source_size=SOURCE, proxy_size=PROXY
            )
        )


def box_record(
    sam_id: str, frame: int | None, edges: tuple[float, ...]
) -> SegmentationBoxRecord:
    return SegmentationBoxRecord(
        order=0,
        object_id=sam_id,
        left=edges[0],
        top=edges[1],
        right=edges[2],
        bottom=edges[3],
        frame=None if frame is None else FrameReference(frame),
    )


def mask_record(
    sam_id: str, frame: int, edges: tuple[float, ...]
) -> SegmentationMaskRecord:
    return SegmentationMaskRecord(
        order=0,
        object_id=sam_id,
        identity=SegmentationMaskIdentity("video", frame, sam_id),
        revision=0,
        mask=SegmentationMask("one_bit", "!", 1, 1),
        bounds=SegmentationMaskBounds(*edges),
        frame=FrameReference(frame),
    )


def test_box_scaling_rounds_outward_and_clamps() -> None:
    records = [box_record("1", 3, (-5.0, 10.2, 959.6, 541.0))]
    tracks = tracks_from_records(records, {1: "u_1"}, SOURCE, PROXY)
    assert tracks["u_1"][0] == TrackBox(3, 0, 20, 1920, 1080)


def test_mask_bounds_are_used_only_when_no_box_exists() -> None:
    records: list[SegmentationRecord] = [
        mask_record("1", 0, (0.0, 0.0, 10.0, 10.0)),
        box_record("1", 0, (1.0, 1.0, 11.0, 11.0)),
        mask_record("1", 0, (5.0, 5.0, 6.0, 6.0)),
        mask_record("2", 4, (2.0, 2.0, 4.0, 4.0)),
    ]
    tracks = tracks_from_records(records, {1: "u_1", 2: "u_2"}, SOURCE, PROXY)
    assert tracks["u_1"] == (TrackBox(0, 2, 2, 22, 22),)
    assert tracks["u_2"] == (TrackBox(4, 4, 4, 8, 8),)


def test_unknown_ids_and_frameless_records_are_ignored() -> None:
    records = [
        box_record("9", 0, (0.0, 0.0, 5.0, 5.0)),
        box_record("1", None, (0.0, 0.0, 5.0, 5.0)),
        box_record("x", 0, (0.0, 0.0, 5.0, 5.0)),
    ]
    assert tracks_from_records(records, {1: "u_1"}, SOURCE, PROXY) == {}

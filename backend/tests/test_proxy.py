import asyncio
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest

from db.store import ApiUsageRecord
from meta_client import CostMeter, MetaClient, create_openai_client
from replay.highlights import (
    AnchorSnapshot,
    Highlight,
    RecordingMeta,
    ReplayError,
)
from replay.proxy import (
    PROXY_FPS,
    PROXY_WIDTH,
    Segment,
    build_prompts,
    build_proxy,
    delete_upload,
    proxy_dimensions,
    track_highlights,
    upload_proxy,
)
from vision.sam import RecordingBox, TrackBox


@dataclass
class MemoryLog:
    records: list[ApiUsageRecord] = field(default_factory=list)

    def record_api_usage(self, record: ApiUsageRecord) -> None:
        self.records.append(record)

    def total_api_cost(self) -> Decimal:
        return Decimal(0)


def rejected() -> openai.APIStatusError:
    request = httpx2.Request("POST", "https://api.meta.ai/v1/files")
    response = httpx2.Response(400, request=request)
    return openai.APIStatusError("bad", response=response, body=None)


class FakeFiles:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.deleted: list[str] = []
        self.reject_first = 0
        self.reject_all = False
        self.delete_error: Exception | None = None

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        kwargs["bytes"] = kwargs["file"].read()
        self.created.append(kwargs)
        if self.reject_all or len(self.created) <= self.reject_first:
            raise rejected()
        return SimpleNamespace(id="file_123")

    async def delete(self, file_id: str) -> SimpleNamespace:
        if self.delete_error is not None:
            raise self.delete_error
        self.deleted.append(file_id)
        return SimpleNamespace(id=file_id, deleted=True)


class FakeSdk:
    def __init__(self) -> None:
        self.files = FakeFiles()


class FakeClient(MetaClient):
    def __init__(self) -> None:
        self.log = MemoryLog()
        super().__init__(
            create_openai_client("test-key"),
            CostMeter(self.log),
            wall_clock=lambda: datetime(2026, 11, 4, tzinfo=UTC),
        )
        self.fake = FakeSdk()

    def sdk(self) -> Any:
        return self.fake


def highlight(
    start: float = 10.0, duration: float = 8.0, kind: str = "kubo_hit"
) -> Highlight:
    return Highlight(kind, 1, start, duration, ())


def make_meta(
    root: Path, anchors: Sequence[AnchorSnapshot] | None = None
) -> RecordingMeta:
    video = root / "night.mp4"
    video.write_bytes(b"video")
    return RecordingMeta(
        video_path=video,
        width=1920,
        height=1080,
        fps=25,
        started_t_ms=0,
        duration_s=100.0,
        anchors=tuple(
            anchors
            if anchors is not None
            else [
                AnchorSnapshot(0.0, {"u_1": (0, 0, 100, 100)}),
                AnchorSnapshot(30.0, {"u_1": (50, 50, 150, 150), "u_2": (5, 5, 9, 9)}),
            ]
        ),
        sprites={},
    )


class FakeRunner:
    def __init__(self, fail_on: int | None = None, code: int = 1) -> None:
        self.calls: list[list[str]] = []
        self.kwargs: list[dict[str, Any]] = []
        self.fail_on = fail_on
        self.code = code
        self.error: Exception | None = None

    def __call__(self, args: list[str], **kwargs: Any) -> SimpleNamespace:
        self.calls.append(list(args))
        self.kwargs.append(kwargs)
        if self.error is not None:
            raise self.error
        index = len(self.calls) - 1
        if self.fail_on == index:
            return SimpleNamespace(returncode=self.code)
        Path(args[-1]).write_bytes(b"out")
        return SimpleNamespace(returncode=0)


def test_build_proxy_cuts_each_segment_then_concats(tmp_path: Path) -> None:
    meta = make_meta(tmp_path)
    runner = FakeRunner()
    work = tmp_path / "work"
    path, segments = build_proxy(
        meta, [highlight(10.0), highlight(40.0, 6.5)], work, tmp_path, "ffmpeg", runner
    )
    assert path == (work / "proxy.mp4").resolve()
    assert path.is_file()
    assert [(s.first_frame, s.frame_count) for s in segments] == [(0, 80), (80, 65)]
    assert len(runner.calls) == 3
    cut = runner.calls[0]
    assert cut[0] == "ffmpeg"
    assert cut[cut.index("-ss") + 1] == "10.000"
    assert cut[cut.index("-t") + 1] == "8.000"
    assert cut[cut.index("-vf") + 1] == f"fps={PROXY_FPS},scale={PROXY_WIDTH}:-2"
    assert cut[cut.index("-frames:v") + 1] == "80"
    assert "libx264" in cut and "+faststart" in cut
    assert cut[cut.index("-i") + 1] == str(meta.video_path.resolve())
    concat = runner.calls[2]
    assert concat[concat.index("-f") + 1] == "concat"
    assert concat[concat.index("-safe") + 1] == "0"
    assert concat[concat.index("-c") + 1] == "copy"
    assert concat[-1] == str(path)


def test_runner_gets_list_args_no_shell_and_timeouts(tmp_path: Path) -> None:
    runner = FakeRunner()
    build_proxy(
        make_meta(tmp_path), [highlight()], tmp_path / "w", tmp_path, "ffmpeg", runner
    )
    for call, kwargs in zip(runner.calls, runner.kwargs, strict=True):
        assert isinstance(call, list) and all(isinstance(a, str) for a in call)
        assert kwargs["shell"] is False
        assert kwargs["check"] is False
        assert kwargs["timeout"] > 0
        assert kwargs["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)


def test_intermediate_files_are_removed(tmp_path: Path) -> None:
    work = tmp_path / "w"
    build_proxy(
        make_meta(tmp_path),
        [highlight(), highlight(30.0)],
        work,
        tmp_path,
        "ffmpeg",
        FakeRunner(),
    )
    assert sorted(p.name for p in work.iterdir()) == ["proxy.mp4"]


def test_concat_list_names_segments_in_order(tmp_path: Path) -> None:
    seen: list[str] = []

    def runner(args: list[str], **kwargs: Any) -> SimpleNamespace:
        if "concat" in args:
            seen.append(Path(args[args.index("-i") + 1]).read_text(encoding="utf-8"))
        Path(args[-1]).write_bytes(b"x")
        return SimpleNamespace(returncode=0)

    build_proxy(
        make_meta(tmp_path),
        [highlight(), highlight(30.0)],
        tmp_path / "w",
        tmp_path,
        "ffmpeg",
        runner,
    )
    assert seen == ["file 'seg_0.mp4'\nfile 'seg_1.mp4'\n"]


def test_missing_ffmpeg_raises(tmp_path: Path) -> None:
    with pytest.raises(ReplayError, match="ffmpeg was not found"):
        build_proxy(make_meta(tmp_path), [highlight()], tmp_path / "w", tmp_path, None)


def test_no_highlights_raises(tmp_path: Path) -> None:
    with pytest.raises(ReplayError):
        build_proxy(
            make_meta(tmp_path), [], tmp_path / "w", tmp_path, "ffmpeg", FakeRunner()
        )


def test_paths_outside_root_are_refused(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "other"
    outside.mkdir()
    meta = make_meta(outside)
    runner = FakeRunner()
    with pytest.raises(ReplayError, match="outside"):
        build_proxy(meta, [highlight()], root / "w", root, "ffmpeg", runner)
    inside_meta = make_meta(root)
    with pytest.raises(ReplayError, match="outside"):
        build_proxy(inside_meta, [highlight()], outside / "w", root, "ffmpeg", runner)
    with pytest.raises(ReplayError, match="outside"):
        build_proxy(inside_meta, [highlight()], root, root, "ffmpeg", runner)
    assert runner.calls == []


def test_missing_recording_file_raises(tmp_path: Path) -> None:
    meta = make_meta(tmp_path)
    meta.video_path.unlink()
    with pytest.raises(ReplayError, match="missing"):
        build_proxy(
            meta, [highlight()], tmp_path / "w", tmp_path, "ffmpeg", FakeRunner()
        )


@pytest.mark.parametrize("fail_on", [0, 1, 2])
def test_failed_step_raises_and_cleans_up(tmp_path: Path, fail_on: int) -> None:
    work = tmp_path / "w"
    runner = FakeRunner(fail_on=fail_on)
    with pytest.raises(ReplayError, match="failed"):
        build_proxy(
            make_meta(tmp_path),
            [highlight(), highlight(30.0)],
            work,
            tmp_path,
            "ffmpeg",
            runner,
        )
    assert not any(p.name.startswith("seg_") for p in work.iterdir())
    assert len(runner.calls) == fail_on + 1


def test_timeout_and_start_errors_become_replay_errors(tmp_path: Path) -> None:
    runner = FakeRunner()
    runner.error = subprocess.TimeoutExpired("ffmpeg", 1)
    with pytest.raises(ReplayError, match="timed out"):
        build_proxy(
            make_meta(tmp_path),
            [highlight()],
            tmp_path / "w",
            tmp_path,
            "ffmpeg",
            runner,
        )
    runner.error = FileNotFoundError()
    with pytest.raises(ReplayError, match="could not start"):
        build_proxy(
            make_meta(tmp_path),
            [highlight()],
            tmp_path / "w",
            tmp_path,
            "ffmpeg",
            runner,
        )


def test_ffmpeg_that_writes_nothing_is_an_error(tmp_path: Path) -> None:
    def runner(args: list[str], **kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(returncode=0)

    with pytest.raises(ReplayError, match="no proxy"):
        build_proxy(
            make_meta(tmp_path),
            [highlight()],
            tmp_path / "w",
            tmp_path,
            "ffmpeg",
            runner,
        )


def test_proxy_dimensions_round_to_even_height() -> None:
    meta = RecordingMeta(Path("a.mp4"), 1920, 1080, 25, 0, 1.0, (), {})
    assert proxy_dimensions(meta) == (960, 540)
    odd = RecordingMeta(Path("a.mp4"), 1280, 720, 25, 0, 1.0, (), {})
    assert proxy_dimensions(odd) == (960, 540)
    wide = RecordingMeta(Path("a.mp4"), 1000, 563, 25, 0, 1.0, (), {})
    assert proxy_dimensions(wide)[1] % 2 == 0


def proxy_file(tmp_path: Path) -> Path:
    path = tmp_path / "proxy.mp4"
    path.write_bytes(b"proxy-bytes")
    return path


def test_upload_sets_expires_after_and_returns_the_id(tmp_path: Path) -> None:
    client = FakeClient()
    file_id = asyncio.run(upload_proxy(client, proxy_file(tmp_path)))
    assert file_id == "file_123"
    sent = client.fake.files.created[0]
    assert sent["purpose"] == "user_data"
    assert sent["expires_after"] == {"anchor": "created_at", "seconds": 86400}
    assert sent["bytes"] == b"proxy-bytes"


def test_upload_falls_back_to_extra_body_with_expiry(tmp_path: Path) -> None:
    client = FakeClient()
    client.fake.files.reject_first = 1
    file_id = asyncio.run(upload_proxy(client, proxy_file(tmp_path)))
    assert file_id == "file_123"
    second = client.fake.files.created[1]
    assert "expires_after" not in second
    assert second["extra_body"] == {
        "expires_after": {"anchor": "created_at", "seconds": 86400}
    }


def test_upload_never_sends_without_an_expiry(tmp_path: Path) -> None:
    client = FakeClient()
    client.fake.files.reject_all = True
    with pytest.raises(ReplayError):
        asyncio.run(upload_proxy(client, proxy_file(tmp_path)))
    assert all(
        "expires_after" in c or "extra_body" in c for c in client.fake.files.created
    )
    assert len(client.fake.files.created) == 2


def test_upload_refuses_non_mp4_and_missing_files(tmp_path: Path) -> None:
    client = FakeClient()
    other = tmp_path / "a.txt"
    other.write_text("x")
    for path in (other, tmp_path / "gone.mp4"):
        with pytest.raises(ReplayError):
            asyncio.run(upload_proxy(client, path))
    assert client.fake.files.created == []


def test_upload_without_an_id_is_an_error(tmp_path: Path) -> None:
    client = FakeClient()

    async def create(**kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace()

    client.fake.files.create = create  # type: ignore[method-assign]
    with pytest.raises(ReplayError, match="file id"):
        asyncio.run(upload_proxy(client, proxy_file(tmp_path)))


def test_delete_calls_the_files_api() -> None:
    client = FakeClient()
    asyncio.run(delete_upload(client, "file_9"))
    assert client.fake.files.deleted == ["file_9"]


def test_upload_and_delete_are_logged_through_execute(tmp_path: Path) -> None:
    client = FakeClient()
    asyncio.run(upload_proxy(client, proxy_file(tmp_path)))
    asyncio.run(delete_upload(client, "file_123"))
    assert [r.kind for r in client.log.records] == ["files", "files"]


class FakeTracker:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def track(
        self,
        file_id: str,
        segments: Sequence[int],
        prompts: Mapping[int, Mapping[str, RecordingBox]],
        *,
        source_size: tuple[int, int],
        proxy_size: tuple[int, int],
    ) -> dict[str, tuple[TrackBox, ...]]:
        self.calls.append(
            {
                "file_id": file_id,
                "segments": list(segments),
                "prompts": prompts,
                "source": source_size,
                "proxy": proxy_size,
            }
        )
        if self.error is not None:
            raise self.error
        return {"u_1": (TrackBox(0, 1, 2, 3, 4),)}


def two_segments() -> list[Segment]:
    return [Segment(highlight(0.0), 0, 80), Segment(highlight(30.0), 80, 80)]


def test_track_highlights_uploads_tracks_and_deletes(tmp_path: Path) -> None:
    client = FakeClient()
    tracker = FakeTracker()
    result = asyncio.run(
        track_highlights(
            client,
            lambda _: tracker,
            make_meta(tmp_path),
            proxy_file(tmp_path),
            two_segments(),
        )
    )
    assert result == {"u_1": (TrackBox(0, 1, 2, 3, 4),)}
    assert client.fake.files.deleted == ["file_123"]
    call = tracker.calls[0]
    assert call["file_id"] == "file_123"
    assert call["segments"] == [0, 80]
    assert call["source"] == (1920, 1080)
    assert call["proxy"] == (960, 540)
    assert call["prompts"][0] == {"u_1": (0, 0, 100, 100)}
    assert call["prompts"][80] == {"u_1": (50, 50, 150, 150), "u_2": (5, 5, 9, 9)}


def test_delete_runs_when_the_tracker_fails(tmp_path: Path) -> None:
    client = FakeClient()
    tracker = FakeTracker(error=RuntimeError("sam down"))
    with pytest.raises(RuntimeError, match="sam down"):
        asyncio.run(
            track_highlights(
                client,
                lambda _: tracker,
                make_meta(tmp_path),
                proxy_file(tmp_path),
                two_segments(),
            )
        )
    assert client.fake.files.deleted == ["file_123"]


def test_delete_runs_when_the_factory_fails(tmp_path: Path) -> None:
    client = FakeClient()

    def factory(_: MetaClient) -> FakeTracker:
        raise RuntimeError("no tracker")

    with pytest.raises(RuntimeError):
        asyncio.run(
            track_highlights(
                client,
                factory,
                make_meta(tmp_path),
                proxy_file(tmp_path),
                two_segments(),
            )
        )
    assert client.fake.files.deleted == ["file_123"]


def test_delete_runs_when_the_task_is_cancelled(tmp_path: Path) -> None:
    client = FakeClient()

    class Slow(FakeTracker):
        async def track(
            self, *args: Any, **kwargs: Any
        ) -> dict[str, tuple[TrackBox, ...]]:
            await asyncio.sleep(30)
            return {}

    async def scenario() -> None:
        task = asyncio.create_task(
            track_highlights(
                client,
                lambda _: Slow(),
                make_meta(tmp_path),
                proxy_file(tmp_path),
                two_segments(),
            )
        )
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert client.fake.files.deleted == ["file_123"]


def test_a_failed_delete_does_not_hide_the_result(tmp_path: Path) -> None:
    client = FakeClient()
    client.fake.files.delete_error = rejected()
    result = asyncio.run(
        track_highlights(
            client,
            lambda _: FakeTracker(),
            make_meta(tmp_path),
            proxy_file(tmp_path),
            two_segments(),
        )
    )
    assert "u_1" in result


def test_nothing_is_uploaded_without_anchors(tmp_path: Path) -> None:
    client = FakeClient()
    meta = make_meta(tmp_path, anchors=[])
    with pytest.raises(ReplayError, match="anchor"):
        asyncio.run(
            track_highlights(
                client,
                lambda _: FakeTracker(),
                meta,
                proxy_file(tmp_path),
                two_segments(),
            )
        )
    assert client.fake.files.created == []


def test_prompts_use_the_nearest_anchor_snapshot(tmp_path: Path) -> None:
    meta = make_meta(tmp_path)
    prompts = build_prompts(
        meta, [Segment(highlight(2.0), 0, 80), Segment(highlight(25.0), 80, 80)]
    )
    assert prompts[0] == {"u_1": (0, 0, 100, 100)}
    assert prompts[80]["u_2"] == (5, 5, 9, 9)

import asyncio
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import numpy.typing as npt
import pytest

from config import MetaModel
from meta_client import (
    CostMeter,
    MetaClient,
    MetaRequestError,
    MetaUnavailableError,
    create_openai_client,
)
from tests.test_meta_client import MemoryLog
from vision.barrio_map import (
    MAP_LONG_SIDE_PX,
    BarrioMapService,
    baseline_reference_png,
    fit_to_play_area,
    map_prompt,
)
from vision.sprites import SpriteError, decode_png, encode_png

Image = npt.NDArray[np.uint8]
CAMPAIGN = "0b1f6c1e-2a3d-4e5f-8a9b-0c1d2e3f4a5b"


def baseline() -> Image:
    frame = np.full((400, 600, 3), (96, 110, 120), dtype=np.uint8)
    cv2.rectangle(frame, (50, 50), (150, 120), (60, 60, 200), -1)
    return frame


def generated() -> bytes:
    image = np.full((1024, 1024, 3), (30, 60, 40), dtype=np.uint8)
    image[300:700, 300:700] = (80, 120, 60)
    return encode_png(image)


class ScriptedService(BarrioMapService):
    def __init__(
        self,
        maps_dir: Path,
        results: list[bytes | BaseException],
        client: MetaClient | None = None,
    ) -> None:
        super().__init__(client or make_client(), maps_dir)
        self.results = results
        self.references: list[bytes] = []
        self.anchors: list[bytes | None] = []

    async def _call(
        self, reference_png: bytes, style_anchor_png: bytes | None
    ) -> bytes:
        self.references.append(reference_png)
        self.anchors.append(style_anchor_png)
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def make_client(total: Decimal = Decimal(0), keyed: bool = True) -> MetaClient:
    sdk = create_openai_client("test-key") if keyed else None
    return MetaClient(sdk, CostMeter(MemoryLog(starting_total=total)))


def run(service: BarrioMapService, demo_safe: bool = False) -> Path | None:
    return asyncio.run(
        service.ensure_map(CAMPAIGN, baseline(), None, demo_safe=demo_safe)
    )


def test_success_saves_a_map_at_the_play_area_aspect(tmp_path: Path) -> None:
    service = ScriptedService(tmp_path, [generated()])
    path = run(service)
    assert path == tmp_path / f"{CAMPAIGN}.png"
    assert path is not None
    saved = decode_png(path.read_bytes())
    assert saved.shape[1] == MAP_LONG_SIDE_PX
    assert saved.shape[0] == round(MAP_LONG_SIDE_PX / 1.5)
    assert service.cached_map(CAMPAIGN) == path


def test_reference_is_the_baseline_and_anchor_is_forwarded(tmp_path: Path) -> None:
    service = ScriptedService(tmp_path, [generated()])
    asyncio.run(service.ensure_map(CAMPAIGN, baseline(), b"anchor", demo_safe=False))
    assert service.anchors == [b"anchor"]
    assert decode_png(service.references[0]).shape[1] == 768


def test_runs_at_most_once_per_campaign(tmp_path: Path) -> None:
    service = ScriptedService(tmp_path, [generated(), generated()])
    first = run(service)
    second = run(service)
    assert first == second
    assert len(service.references) == 1


def test_failure_is_not_retried_in_the_same_session(tmp_path: Path) -> None:
    service = ScriptedService(tmp_path, [MetaUnavailableError("down"), generated()])
    assert run(service) is None
    assert run(service) is None
    assert len(service.references) == 1
    assert service.cached_map(CAMPAIGN) is None


def test_content_policy_leaves_a_marker_and_never_retries(tmp_path: Path) -> None:
    service = ScriptedService(
        tmp_path, [MetaRequestError("blocked", is_content_policy=True)]
    )
    assert run(service) is None
    fresh = ScriptedService(tmp_path, [generated()])
    assert run(fresh) is None
    assert fresh.references == []


def test_demo_safe_makes_no_call(tmp_path: Path) -> None:
    service = ScriptedService(tmp_path, [generated()])
    assert run(service, demo_safe=True) is None
    assert service.references == []


def test_demo_safe_still_returns_an_existing_map(tmp_path: Path) -> None:
    service = ScriptedService(tmp_path, [generated()])
    path = run(service)
    assert run(service, demo_safe=True) == path


def test_no_key_makes_no_call(tmp_path: Path) -> None:
    service = ScriptedService(tmp_path, [generated()], make_client(keyed=False))
    assert run(service) is None
    assert service.references == []


def test_hard_stop_makes_no_call(tmp_path: Path) -> None:
    service = ScriptedService(tmp_path, [generated()], make_client(Decimal(125)))
    assert run(service) is None
    assert service.references == []


def test_open_breaker_makes_no_call(tmp_path: Path) -> None:
    client = make_client()
    breaker = client.breaker(MetaModel.IMAGE)
    for _ in range(10):
        breaker.record_failure()
    service = ScriptedService(tmp_path, [generated()], client)
    assert run(service) is None
    assert service.references == []


def test_garbage_output_returns_none(tmp_path: Path) -> None:
    service = ScriptedService(tmp_path, [b"not a png"])
    assert run(service) is None
    assert service.cached_map(CAMPAIGN) is None


def test_unsafe_campaign_id_is_refused(tmp_path: Path) -> None:
    service = ScriptedService(tmp_path, [generated()])
    result = asyncio.run(
        service.ensure_map("../evil", baseline(), None, demo_safe=False)
    )
    assert result is None
    assert service.references == []
    assert service.cached_map("../evil") is None
    with pytest.raises(ValueError):
        service.map_path("..\\evil")


def test_delete_map_removes_file_and_marker(tmp_path: Path) -> None:
    service = ScriptedService(tmp_path, [generated(), generated()])
    path = run(service)
    assert path is not None
    service.delete_map(CAMPAIGN)
    assert not path.exists()
    assert run(service) is not None
    service.delete_map("../evil")


def test_unusable_baseline_makes_no_call(tmp_path: Path) -> None:
    service = ScriptedService(tmp_path, [generated()])
    empty = np.zeros((0, 0, 3), dtype=np.uint8)
    result = asyncio.run(service.ensure_map(CAMPAIGN, empty, None, demo_safe=False))
    assert result is None
    assert service.references == []


def test_helpers_validate_input() -> None:
    with pytest.raises(SpriteError):
        baseline_reference_png(np.zeros((4, 4), dtype=np.uint8))
    with pytest.raises(SpriteError):
        fit_to_play_area(np.zeros((8, 8, 4), dtype=np.uint8), 0.0)
    tall = fit_to_play_area(np.zeros((8, 8, 4), dtype=np.uint8), 0.5)
    assert tall.shape[:2] == (MAP_LONG_SIDE_PX, MAP_LONG_SIDE_PX // 2)
    assert "second image" in map_prompt(True)
    assert "second image" not in map_prompt(False)


class RecordingImages:
    def __init__(self, result: str) -> None:
        self.result = result
        self.kwargs: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs.append(kwargs)
        item = SimpleNamespace(type="image_generation_call", result=self.result)
        return SimpleNamespace(id="r1", output=[item], usage=None)


def test_real_call_path_meters_one_image_and_stores_false(tmp_path: Path) -> None:
    import base64

    log = MemoryLog(starting_total=Decimal(0))
    sdk = create_openai_client("test-key")
    client = MetaClient(sdk, CostMeter(log))
    recorder = RecordingImages(base64.b64encode(generated()).decode("ascii"))
    sdk.responses = recorder  # type: ignore[assignment,misc]
    service = BarrioMapService(client, tmp_path)
    path = run(service)
    assert path is not None
    assert recorder.kwargs[0]["store"] is False
    assert recorder.kwargs[0]["model"] == MetaModel.IMAGE.value
    assert len(log.records) == 1
    assert log.records[0].images == 1
    assert log.records[0].cost_usd == Decimal("0.01")

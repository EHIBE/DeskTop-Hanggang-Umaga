import json
from collections.abc import Callable, Iterator
from decimal import Decimal
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt
import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from capture.calibration import Corners, PlayArea, compute_calibration
from capture.camera import CameraInfo, MicrophoneInfo, VideoSource
from config import AppSettings
from db.store import Store
from game.night import FramePump, GameController
from gm.schemas import ContentFilter
from meta_client import CostMeter
from server import Services, create_app
from state import Broadcast, LiveState
from tests.test_meta_client import MemoryLog
from vision.sam import TrackerOnlySegmenter
from vision.sprites import GeneratedSprite, SpriteJob, SpriteService
from vision.summon import FallbackDetector, SummonPipeline

Image = npt.NDArray[np.uint8]
TOKEN = "t" * 64
ORIGIN = "http://localhost:5173"
CONTENT = ContentFilter.from_data_dir()
SHEET: Corners = ((820.0, 300.0), (1140.0, 310.0), (1190.0, 760.0), (780.0, 750.0))


def scene() -> Image:
    area = PlayArea()
    width, height = area.warped_size
    rng = np.random.default_rng(3)
    noise = rng.integers(0, 255, size=(height // 8, width // 8), dtype=np.uint8)
    board = cv2.cvtColor(
        cv2.resize(noise, (width, height), interpolation=cv2.INTER_NEAREST),
        cv2.COLOR_GRAY2BGR,
    )
    inverse = np.linalg.inv(compute_calibration(SHEET, area).homography)
    return np.asarray(cv2.warpPerspective(board, inverse, (1920, 1080)), dtype=np.uint8)


SCENE = scene()


class SceneSource:
    def isOpened(self) -> bool:
        return True

    def set(self, prop_id: int, value: float) -> bool:
        return True

    def get(self, prop_id: int) -> float:
        return 1920.0 if prop_id == cv2.CAP_PROP_FRAME_WIDTH else 1080.0

    def read(self) -> tuple[bool, Image | None]:
        return True, SCENE.copy()

    def release(self) -> None:
        return None


class StaticGenerator:
    is_available = True

    async def generate(
        self, job: SpriteJob, style_anchor_png: bytes | None
    ) -> GeneratedSprite:
        return GeneratedSprite(png=b"PNG-test", response_id=None)


class BusySource(SceneSource):
    def isOpened(self) -> bool:
        return False


def make_factory(
    tmp_path: Path, busy: bool = False, spent: Decimal = Decimal(0)
) -> Callable[[AppSettings], Services]:
    def factory(settings: AppSettings) -> Services:
        store = Store(settings.database_path)
        live = LiveState()
        meter = CostMeter(MemoryLog(starting_total=spent))
        broadcast = Broadcast()

        def source(_: int) -> VideoSource:
            return BusySource() if busy else SceneSource()

        controller = GameController(
            store,
            live,
            has_api_key=False,
            camera_factory=source,
            list_camera_devices=lambda: [CameraInfo(0, 1920, 1080)],
            list_microphone_devices=lambda: [MicrophoneInfo(1, "Mic")],
            sleep=lambda _: None,
            pipeline_factory=lambda _: SummonPipeline(
                FallbackDetector(), TrackerOnlySegmenter(), CONTENT
            ),
            meter=meter,
            sprite_service_factory=lambda _: SpriteService(store, StaticGenerator()),
            broadcast=broadcast,
        )
        pump = FramePump(controller, live)

        def close() -> None:
            pump.stop()
            controller.close()
            store.close()

        return Services(
            settings=settings,
            controller=controller,
            pump=pump,
            live=live,
            content=CONTENT,
            meter=meter,
            broadcast=broadcast,
            close=close,
        )

    return factory


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = AppSettings(token=TOKEN, data_dir=tmp_path, port=8765, api_key=None)
    app = create_app(settings, frozenset({ORIGIN}), make_factory(tmp_path))
    with TestClient(app) as test_client:
        yield test_client


def connect(
    client: TestClient, token: str = TOKEN, origin: str = ORIGIN
) -> WebSocketTestSession:
    return client.websocket_connect(
        "/ws", subprotocols=["desktop", token], headers={"origin": origin}
    )


def receive_type(
    ws: WebSocketTestSession, wanted: str, limit: int = 200
) -> dict[str, object]:
    for _ in range(limit):
        message: dict[str, object] = json.loads(ws.receive_text())
        if message["type"] == wanted:
            return message
    raise AssertionError(f"no {wanted} message")


def test_health_requires_token(client: TestClient) -> None:
    assert client.get("/health").status_code == 401
    assert (
        client.get("/health", headers={"x-desktop-token": "wrong"}).status_code == 401
    )
    response = client.get("/health", headers={"x-desktop-token": TOKEN})
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_docs_are_disabled(client: TestClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path, headers={"x-desktop-token": TOKEN}).status_code == 404


@pytest.mark.parametrize(
    ("token", "origin"), [("wrong", ORIGIN), ("", ORIGIN), (TOKEN, "http://evil.test")]
)
def test_websocket_rejects_bad_token_or_origin(
    client: TestClient, token: str, origin: str
) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as info,
        connect(client, token, origin) as ws,
    ):
        ws.receive_text()
    assert info.value.code == 1008


def test_connect_sends_start_state(client: TestClient) -> None:
    with connect(client) as ws:
        state = receive_type(ws, "state")
        assert state["phase"] == "START"
        assert state["campaign"] is None
        assert state["has_api_key"] is False


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        json.dumps({"type": "nope"}),
        json.dumps({"type": "campaign.list", "extra": 1}),
        json.dumps({"type": "camera.select", "index": 9}),
        json.dumps({"type": "camera.select", "index": "0"}),
        json.dumps(
            {"type": "campaign.start", "new": {"name": "", "difficulty": "normal"}}
        ),
        json.dumps(
            {"type": "campaign.start", "new": {"name": "x", "difficulty": "easy"}}
        ),
        json.dumps({"type": "demo_safe", "on": "yes"}),
        "x" * 20_000,
    ],
)
def test_invalid_messages_get_a_notice(client: TestClient, payload: str) -> None:
    with connect(client) as ws:
        receive_type(ws, "state")
        ws.send_text(payload)
        notice = receive_type(ws, "notice")
        assert notice["copy_key"] == "cmd.unknown"


def test_corners_are_rejected_outside_calibrate(client: TestClient) -> None:
    with connect(client) as ws:
        receive_type(ws, "state")
        ws.send_text(
            json.dumps(
                {
                    "type": "calibrate.corners",
                    "corners": SHEET,
                    "play_w_cm": 60,
                    "play_h_cm": 40,
                }
            )
        )
        assert receive_type(ws, "notice")["copy_key"] == "cmd.unknown"


def test_unknown_campaign_id_gets_a_notice(client: TestClient) -> None:
    with connect(client) as ws:
        receive_type(ws, "state")
        ws.send_text(
            json.dumps(
                {
                    "type": "campaign.start",
                    "campaign_id": "6f1d2a1e-7c1b-4c2e-9a3b-0a1b2c3d4e5f",
                }
            )
        )
        assert receive_type(ws, "notice")["copy_key"] == "cmd.unknown"


def test_devices_and_campaign_lists(client: TestClient) -> None:
    with connect(client) as ws:
        receive_type(ws, "state")
        ws.send_text(json.dumps({"type": "devices.list"}))
        devices = receive_type(ws, "devices")
        assert devices["cameras"] == [{"index": 0, "width": 1920, "height": 1080}]
        assert devices["microphones"] == [{"index": 1, "name": "Mic"}]
        ws.send_text(json.dumps({"type": "campaign.list"}))
        assert receive_type(ws, "campaigns")["campaigns"] == []


def test_full_calibration_flow_reaches_summon(client: TestClient) -> None:
    with connect(client) as ws:
        receive_type(ws, "state")
        ws.send_text(
            json.dumps(
                {
                    "type": "campaign.start",
                    "new": {"name": "Barkada", "difficulty": "normal"},
                }
            )
        )
        assert receive_type(ws, "state")["phase"] == "CALIBRATE"
        ws.send_text(
            json.dumps(
                {
                    "type": "calibrate.corners",
                    "corners": SHEET,
                    "play_w_cm": 60,
                    "play_h_cm": 40,
                }
            )
        )
        assert receive_type(ws, "notice")["copy_key"] == "cam.busy"
        receive_type(ws, "state")
        ws.send_text(json.dumps({"type": "camera.select", "index": 0}))
        state = receive_type(ws, "state")
        assert state["camera"] == {"index": 0, "width": 1920, "height": 1080}
        raw = receive_type(ws, "frame")
        assert raw["view"] == "raw"
        assert (raw["width"], raw["height"]) == (1920, 1080)
        ws.send_text(
            json.dumps(
                {
                    "type": "calibrate.corners",
                    "corners": SHEET,
                    "play_w_cm": 60,
                    "play_h_cm": 40,
                }
            )
        )
        assert receive_type(ws, "state")["calibration_preview"] is True
        warped = receive_type(ws, "frame")
        for _ in range(50):
            if warped["view"] == "warped":
                break
            warped = receive_type(ws, "frame")
        assert warped["view"] == "warped"
        assert (warped["width"], warped["height"]) == (1200, 800)
        ws.send_text(json.dumps({"type": "calibrate.done"}))
        final = receive_type(ws, "state")
        assert final["phase"] == "SUMMON"
        assert final["calibrated"] is True


def test_bad_corners_get_calibration_notice(client: TestClient) -> None:
    with connect(client) as ws:
        receive_type(ws, "state")
        ws.send_text(
            json.dumps(
                {"type": "campaign.start", "new": {"name": "B", "difficulty": "madali"}}
            )
        )
        receive_type(ws, "state")
        ws.send_text(json.dumps({"type": "camera.select", "index": 0}))
        receive_type(ws, "state")
        flipped = [SHEET[0], SHEET[3], SHEET[2], SHEET[1]]
        ws.send_text(
            json.dumps(
                {
                    "type": "calibrate.corners",
                    "corners": flipped,
                    "play_w_cm": 60,
                    "play_h_cm": 40,
                }
            )
        )
        assert receive_type(ws, "notice")["copy_key"] == "calib.tap"


def test_demo_safe_toggle_persists_in_state(client: TestClient) -> None:
    with connect(client) as ws:
        receive_type(ws, "state")
        ws.send_text(json.dumps({"type": "demo_safe", "on": True}))
        assert receive_type(ws, "state")["demo_safe"] is True


def test_busy_camera_gets_notice(tmp_path: Path) -> None:
    settings = AppSettings(token=TOKEN, data_dir=tmp_path, port=8765, api_key=None)
    app = create_app(settings, frozenset({ORIGIN}), make_factory(tmp_path, busy=True))
    with TestClient(app) as busy_client, connect(busy_client) as ws:
        receive_type(ws, "state")
        ws.send_text(
            json.dumps(
                {"type": "campaign.start", "new": {"name": "B", "difficulty": "normal"}}
            )
        )
        receive_type(ws, "state")
        ws.send_text(json.dumps({"type": "camera.select", "index": 0}))
        assert receive_type(ws, "notice")["copy_key"] == "cam.busy"


def test_binary_frames_get_a_notice(client: TestClient) -> None:
    with connect(client) as ws:
        receive_type(ws, "state")
        ws.send_bytes(b"\x00\x01")
        assert receive_type(ws, "notice")["copy_key"] == "cmd.unknown"
        ws.send_text(json.dumps({"type": "campaign.list"}))
        assert receive_type(ws, "campaigns")["campaigns"] == []


def calibrated(ws: WebSocketTestSession) -> None:
    receive_type(ws, "state")
    ws.send_text(
        json.dumps(
            {"type": "campaign.start", "new": {"name": "B", "difficulty": "normal"}}
        )
    )
    receive_type(ws, "state")
    ws.send_text(json.dumps({"type": "camera.select", "index": 0}))
    receive_type(ws, "state")
    ws.send_text(
        json.dumps(
            {
                "type": "calibrate.corners",
                "corners": SHEET,
                "play_w_cm": 60,
                "play_h_cm": 40,
            }
        )
    )
    receive_type(ws, "state")
    ws.send_text(json.dumps({"type": "calibrate.done"}))
    state = receive_type(ws, "state")
    assert state["phase"] == "SUMMON"
    assert state["units"] == []
    assert state["begin_block_key"] == "summon.kubo_first"


def test_offline_summon_asks_for_a_tap_then_makes_the_kubo(client: TestClient) -> None:
    with connect(client) as ws:
        calibrated(ws)
        ws.send_text(json.dumps({"type": "summon.name", "name": "Bahay Kubo"}))
        assert receive_type(ws, "notice")["copy_key"] == "summon.which"
        assert receive_type(ws, "state")["awaiting_tap"] is True
        ws.send_text(json.dumps({"type": "summon.tap", "point": [600, 400]}))
        card = receive_type(ws, "card")["unit"]
        assert isinstance(card, dict)
        assert card["id"] == "u_kubo"
        assert card["class"] == "kubo"
        assert card["name"] == "Bahay Kubo"
        assert card["x_cm"] == pytest.approx(30.0, abs=0.1)
        state = receive_type(ws, "state")
        assert state["awaiting_tap"] is False
        assert len(state["units"]) == 1  # type: ignore[arg-type]
        assert state["begin_block_key"] == "summon.need_units"


def test_summon_messages_are_validated_and_phase_checked(client: TestClient) -> None:
    with connect(client) as ws:
        receive_type(ws, "state")
        ws.send_text(json.dumps({"type": "summon.name", "name": "Pen"}))
        assert receive_type(ws, "notice")["copy_key"] == "cmd.unknown"
        for payload in (
            {"type": "summon.name", "name": ""},
            {"type": "summon.name", "name": "x" * 41},
            {"type": "summon.tap", "point": [-1, 5]},
            {"type": "unit.reroll", "unit_id": "short"},
            {
                "type": "unit.rename",
                "unit_id": "6f1d2a1e-7c1b-4c2e-9a3b-0a1b2c3d4e5f",
                "name": "",
            },
        ):
            ws.send_text(json.dumps(payload))
            assert receive_type(ws, "notice")["copy_key"] == "cmd.unknown"


def test_tap_without_a_pending_summon_is_rejected(client: TestClient) -> None:
    with connect(client) as ws:
        calibrated(ws)
        ws.send_text(json.dumps({"type": "summon.tap", "point": [600, 400]}))
        assert receive_type(ws, "notice")["copy_key"] == "cmd.unknown"


def test_hard_stop_turns_on_demo_safe_and_warns(tmp_path: Path) -> None:
    settings = AppSettings(token=TOKEN, data_dir=tmp_path, port=8765, api_key=None)
    app = create_app(
        settings, frozenset({ORIGIN}), make_factory(tmp_path, spent=Decimal(120))
    )
    with TestClient(app) as stopped_client, connect(stopped_client) as ws:
        assert receive_type(ws, "notice")["copy_key"] == "credits.low"
        assert receive_type(ws, "state")["demo_safe"] is True


def test_cost_messages_only_in_dev(tmp_path: Path) -> None:
    dev = AppSettings(
        token=TOKEN, data_dir=tmp_path, port=8765, api_key=None, is_dev=True
    )
    app = create_app(
        dev, frozenset({ORIGIN}), make_factory(tmp_path, spent=Decimal("95.5"))
    )
    with TestClient(app) as dev_client, connect(dev_client) as ws:
        cost = receive_type(ws, "cost")
        assert (cost["spent_usd"], cost["warn"], cost["stopped"]) == (
            "95.500000",
            True,
            False,
        )


def test_no_cost_messages_outside_dev(client: TestClient) -> None:
    with connect(client) as ws:
        receive_type(ws, "state")
        ws.send_text(json.dumps({"type": "demo_safe", "on": False}))
        assert json.loads(ws.receive_text())["type"] == "state"


def test_sprite_arrives_after_the_card(client: TestClient) -> None:
    with connect(client) as ws:
        calibrated(ws)
        ws.send_text(json.dumps({"type": "summon.name", "name": "Bahay Kubo"}))
        receive_type(ws, "notice")
        ws.send_text(json.dumps({"type": "summon.tap", "point": [600, 400]}))
        card = receive_type(ws, "card")["unit"]
        assert isinstance(card, dict)
        sprite = receive_type(ws, "sprite")
        assert sprite["unit_id"] == card["unit_id"]
        assert sprite["sprite_png"] == "UE5HLXRlc3Q="
        ws.send_text(json.dumps({"type": "campaign.list"}))
        receive_type(ws, "campaigns")
        units = receive_type(ws, "state")["units"]
        assert isinstance(units, list)
        assert units[0]["sprite_png"] == "UE5HLXRlc3Q="

import asyncio
import hmac
import json
import logging
import os
import sys
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Final, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from capture.calibration import CalibrationError
from capture.camera import CameraError
from config import STREAM_FPS, AppSettings, load_settings
from db.store import Campaign, NotFoundError, Store, StoreError
from game.night import FramePump, GameController, GameError, Snapshot
from rules.units import Difficulty
from state import EncodedFrame, LiveState

logger = logging.getLogger("desktop.server")

TOKEN_HEADER: Final = "x-desktop-token"
SUBPROTOCOL: Final = "desktop"
SUBPROTOCOL_HEADER: Final = "sec-websocket-protocol"
POLICY_VIOLATION: Final = 1008
MAX_MESSAGE_BYTES: Final = 16_384
INVALID_MESSAGE_KEY: Final = "cmd.unknown"
FAILURE_KEY: Final = "restore"
DEV_FLAG: Final = "DESKTOP_DEV"
PARENT_WATCH_FLAG: Final = "DESKTOP_PARENT_WATCH"
BACKEND_DIR: Final = Path(__file__).resolve().parent


class ClientModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class CampaignListMessage(ClientModel):
    type: Literal["campaign.list"]


class NewCampaign(ClientModel):
    name: Annotated[str, Field(min_length=1, max_length=40)]
    difficulty: Difficulty


class CampaignStartExisting(ClientModel):
    type: Literal["campaign.start"]
    campaign_id: Annotated[str, Field(min_length=36, max_length=36)]


class CampaignStartNew(ClientModel):
    type: Literal["campaign.start"]
    new: NewCampaign


class DevicesListMessage(ClientModel):
    type: Literal["devices.list"]


class CameraSelectMessage(ClientModel):
    type: Literal["camera.select"]
    index: Annotated[int, Field(ge=0, le=5)]


Coordinate = Annotated[float, Field(ge=-10_000, le=10_000, allow_inf_nan=False)]


class CalibrateCornersMessage(ClientModel):
    type: Literal["calibrate.corners"]
    corners: tuple[
        tuple[Coordinate, Coordinate],
        tuple[Coordinate, Coordinate],
        tuple[Coordinate, Coordinate],
        tuple[Coordinate, Coordinate],
    ]
    play_w_cm: Annotated[float, Field(ge=30, le=120, allow_inf_nan=False)]
    play_h_cm: Annotated[float, Field(ge=30, le=120, allow_inf_nan=False)]


class CalibrateDoneMessage(ClientModel):
    type: Literal["calibrate.done"]


class CalibrateRestartMessage(ClientModel):
    type: Literal["calibrate.restart"]


class DemoSafeMessage(ClientModel):
    type: Literal["demo_safe"]
    on: bool


ClientMessage = (
    CampaignListMessage
    | CampaignStartExisting
    | CampaignStartNew
    | DevicesListMessage
    | CameraSelectMessage
    | CalibrateCornersMessage
    | CalibrateDoneMessage
    | CalibrateRestartMessage
    | DemoSafeMessage
)
CLIENT_MESSAGE: Final = TypeAdapter[ClientMessage](ClientMessage)

JsonObject = dict[str, object]


@dataclass(frozen=True)
class Services:
    settings: AppSettings
    controller: GameController
    pump: FramePump
    live: LiveState
    close: Callable[[], None]


ServicesFactory = Callable[[AppSettings], Services]


def build_services(settings: AppSettings) -> Services:
    store = Store(settings.database_path)
    live = LiveState()
    controller = GameController(store, live, has_api_key=settings.api_key is not None)
    pump = FramePump(controller, live)

    def close() -> None:
        pump.stop()
        controller.close()
        store.close()

    return Services(
        settings=settings, controller=controller, pump=pump, live=live, close=close
    )


def is_token_valid(expected: str, supplied: str | None) -> bool:
    if supplied is None:
        return False
    return hmac.compare_digest(expected.encode("utf-8"), supplied.encode("utf-8"))


def token_from_subprotocols(header: str | None) -> str | None:
    if header is None:
        return None
    parts = [part.strip() for part in header.split(",")]
    if len(parts) != 2 or parts[0] != SUBPROTOCOL:
        return None
    return parts[1]


def allowed_origins_from_env(raw: str) -> frozenset[str]:
    return frozenset(origin.strip() for origin in raw.split(",") if origin.strip())


def campaign_json(campaign: Campaign) -> JsonObject:
    return {
        "id": campaign.id,
        "name": campaign.name,
        "difficulty": campaign.difficulty.value,
        "nights_survived": campaign.nights_survived,
        "created_at": campaign.created_at,
    }


def state_json(snapshot: Snapshot) -> JsonObject:
    camera = snapshot.camera
    return {
        "type": "state",
        "phase": snapshot.phase.value,
        "campaign": None
        if snapshot.campaign is None
        else campaign_json(snapshot.campaign),
        "camera": None
        if camera is None
        else {"index": camera.index, "width": camera.width, "height": camera.height},
        "calibrated": snapshot.is_calibrated,
        "calibration_preview": snapshot.is_previewing,
        "play_w_cm": snapshot.play_w_cm,
        "play_h_cm": snapshot.play_h_cm,
        "demo_safe": snapshot.is_demo_safe,
        "has_api_key": snapshot.has_api_key,
    }


def frame_json(frame: EncodedFrame) -> JsonObject:
    return {
        "type": "frame",
        "view": frame.view.value,
        "width": frame.width,
        "height": frame.height,
        "jpg": frame.jpg_base64,
        "poses": [
            {"id": p.id, "x_cm": p.x_cm, "y_cm": p.y_cm, "uncertain": p.uncertain}
            for p in frame.poses
        ],
    }


def notice_json(copy_key: str) -> JsonObject:
    return {"type": "notice", "copy_key": copy_key, "params": {}}


class Connection:
    def __init__(self, socket: WebSocket, services: Services) -> None:
        self._socket = socket
        self._services = services
        self._seq = 0
        self._send_lock = asyncio.Lock()

    async def send(self, message: JsonObject) -> None:
        async with self._send_lock:
            self._seq += 1
            await self._socket.send_text(json.dumps({**message, "seq": self._seq}))

    async def send_state(self) -> None:
        await self.send(state_json(self._services.controller.snapshot()))

    async def stream_frames(self) -> None:
        last_sequence = -1
        interval = 1.0 / STREAM_FPS
        while True:
            frame = self._services.live.latest()
            if frame is not None and frame.sequence != last_sequence:
                last_sequence = frame.sequence
                await self.send(frame_json(frame))
            await asyncio.sleep(interval)

    async def receive(self) -> None:
        while True:
            event = await self._socket.receive()
            if event["type"] == "websocket.disconnect":
                raise WebSocketDisconnect(code=int(event.get("code", 1000)))
            raw = event.get("text")
            if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
                logger.warning("rejected oversized websocket message")
                await self.send(notice_json(INVALID_MESSAGE_KEY))
                continue
            try:
                message = CLIENT_MESSAGE.validate_json(raw)
            except ValidationError:
                logger.warning("rejected invalid websocket message")
                await self.send(notice_json(INVALID_MESSAGE_KEY))
                continue
            await self.dispatch(message)

    async def dispatch(self, message: ClientMessage) -> None:
        controller = self._services.controller
        try:
            reply = await self._handle(controller, message)
        except GameError as error:
            await self.send(notice_json(error.copy_key))
            await self.send_state()
            return
        except NotFoundError:
            await self.send(notice_json(INVALID_MESSAGE_KEY))
            return
        except (StoreError, CalibrationError, CameraError, OSError, ValueError):
            logger.exception("message handling failed")
            await self.send(notice_json(FAILURE_KEY))
            await self.send_state()
            return
        if reply is not None:
            await self.send(reply)
        await self.send_state()

    async def _handle(
        self, controller: GameController, message: ClientMessage
    ) -> JsonObject | None:
        if isinstance(message, CampaignListMessage):
            campaigns = await asyncio.to_thread(controller.list_campaigns)
            return {
                "type": "campaigns",
                "campaigns": [campaign_json(c) for c in campaigns],
            }
        if isinstance(message, DevicesListMessage):
            devices = await asyncio.to_thread(controller.devices)
            return {
                "type": "devices",
                "cameras": [
                    {"index": c.index, "width": c.width, "height": c.height}
                    for c in devices.cameras
                ],
                "microphones": [
                    {"index": m.index, "name": m.name} for m in devices.microphones
                ],
            }
        if isinstance(message, CampaignStartNew):
            await asyncio.to_thread(
                controller.start_new_campaign, message.new.name, message.new.difficulty
            )
            return None
        if isinstance(message, CampaignStartExisting):
            await asyncio.to_thread(controller.continue_campaign, message.campaign_id)
            return None
        if isinstance(message, CameraSelectMessage):
            await asyncio.to_thread(controller.select_camera, message.index)
            return None
        if isinstance(message, CalibrateCornersMessage):
            await asyncio.to_thread(
                controller.submit_corners,
                message.corners,
                message.play_w_cm,
                message.play_h_cm,
            )
            return None
        if isinstance(message, CalibrateDoneMessage):
            await asyncio.to_thread(controller.confirm_calibration)
            return None
        if isinstance(message, CalibrateRestartMessage):
            await asyncio.to_thread(controller.restart_calibration)
            return None
        await asyncio.to_thread(controller.set_demo_safe, message.on)
        return None


def create_app(
    settings: AppSettings,
    allowed_origins: frozenset[str],
    services_factory: ServicesFactory = build_services,
) -> FastAPI:
    holder: dict[str, Services] = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        services = services_factory(settings)
        services.pump.start()
        holder["services"] = services
        yield
        services.close()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.middleware("http")
    async def require_token(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not is_token_valid(settings.token, request.headers.get(TOKEN_HEADER)):
            logger.warning("rejected http request with a missing or wrong token")
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return await call_next(request)

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.websocket("/ws")
    async def websocket_endpoint(socket: WebSocket) -> None:
        origin = socket.headers.get("origin")
        if origin not in allowed_origins:
            logger.warning("rejected websocket from an unexpected origin")
            await socket.close(code=POLICY_VIOLATION)
            return
        supplied = token_from_subprotocols(socket.headers.get(SUBPROTOCOL_HEADER))
        if not is_token_valid(settings.token, supplied):
            logger.warning("rejected websocket with a missing or wrong token")
            await socket.close(code=POLICY_VIOLATION)
            return
        services = holder["services"]
        await socket.accept(subprotocol=SUBPROTOCOL)
        logger.info("websocket accepted")
        connection = Connection(socket, services)
        await connection.send_state()
        sender = asyncio.create_task(connection.stream_frames())
        try:
            await connection.receive()
        except WebSocketDisconnect:
            logger.info("websocket closed")
        finally:
            sender.cancel()

    return app


def exit_when_parent_closes_stdin() -> None:
    sys.stdin.buffer.read()
    logger.warning("parent process closed stdin, shutting down")
    os._exit(0)


def create_app_from_env() -> FastAPI:
    if os.environ.get(DEV_FLAG) == "1":
        load_dotenv(BACKEND_DIR / ".env", override=False)
    if os.environ.get(PARENT_WATCH_FLAG) == "1":
        threading.Thread(
            target=exit_when_parent_closes_stdin, name="parent-watch", daemon=True
        ).start()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    settings = load_settings(os.environ)
    origins = allowed_origins_from_env(os.environ.get("DESKTOP_ALLOWED_ORIGINS", ""))
    return create_app(settings, origins)

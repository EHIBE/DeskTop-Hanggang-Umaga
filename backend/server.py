import asyncio
import hmac
import json
import logging
import os
import sys
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Final, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from capture.calibration import CalibrationError
from capture.camera import CameraError
from capture.recorder import Recorder, find_ffmpeg
from config import STREAM_FPS, AppSettings, load_settings
from db.store import Campaign, NotFoundError, Store, StoreError
from game.night import (
    STATE_CHANGED,
    FinalScore,
    FramePump,
    GameController,
    GameError,
    NightView,
    PipelineFactory,
    RecorderFactory,
    ReplayRunner,
    SegmenterFactory,
    Snapshot,
    SpriteServiceFactory,
    UnitView,
    VoiceFactory,
)
from gm.narrator import LineBank, NarrationService, SparkNarrator
from gm.schemas import ContentFilter
from meta_client import CostMeter, MetaClient, create_openai_client
from replay.render import ReelRequest, ReelResult, make_reel
from rules.resolve import Action
from rules.units import Difficulty
from state import Broadcast, EncodedFrame, LiveState
from vision.sam import SamSegmenter, SamVideoTracker, Segmenter, TrackerOnlySegmenter
from vision.sprites import MuseImageGenerator, PlaceholderGenerator, SpriteService
from vision.summon import FallbackDetector, SparkDetector, SummonPipeline
from voice.session import (
    Caption,
    SoundDeviceMicrophone,
    VoiceMode,
    VoiceSession,
    VoiceStatus,
    WebsocketsConnector,
)

logger = logging.getLogger("desktop.server")

TOKEN_HEADER: Final = "x-desktop-token"
SUBPROTOCOL: Final = "desktop"
SUBPROTOCOL_HEADER: Final = "sec-websocket-protocol"
POLICY_VIOLATION: Final = 1008
MAX_MESSAGE_BYTES: Final = 16_384
INVALID_MESSAGE_KEY: Final = "cmd.unknown"
FAILURE_KEY: Final = "err.generic"
DEV_FLAG: Final = "DESKTOP_DEV"
PARENT_WATCH_FLAG: Final = "DESKTOP_PARENT_WATCH"
PACKAGED_FLAG: Final = "DESKTOP_PACKAGED"
PACKAGED_RENDERER_ORIGIN: Final = "null"
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


class CampaignDeleteMessage(ClientModel):
    type: Literal["campaign.delete"]
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


UnitId = Annotated[str, Field(min_length=36, max_length=36)]
UnitName = Annotated[str, Field(min_length=1, max_length=40)]
PixelCoordinate = Annotated[int, Field(ge=0, le=10_000)]


class SummonNameMessage(ClientModel):
    type: Literal["summon.name"]
    name: UnitName


class SummonTapMessage(ClientModel):
    type: Literal["summon.tap"]
    point: tuple[PixelCoordinate, PixelCoordinate]


class UnitRerollMessage(ClientModel):
    type: Literal["unit.reroll"]
    unit_id: UnitId


class UnitRenameMessage(ClientModel):
    type: Literal["unit.rename"]
    unit_id: UnitId
    name: UnitName


UnitGameId = Annotated[str, Field(pattern=r"^u_(kubo|[0-9]{1,2})$")]
TargetGameId = Annotated[
    str, Field(pattern=r"^(u_(kubo|[0-9]{1,2})|e_[a-z]{1,12}_[0-9]{1,3})$")
]


class NightBeginMessage(ClientModel):
    type: Literal["night.begin"]


class ClaimTapMessage(ClientModel):
    type: Literal["claim.tap"]
    player_name: Annotated[str, Field(min_length=1, max_length=24)]
    unit_ids: Annotated[list[UnitGameId], Field(max_length=12)]


class ClaimDoneMessage(ClientModel):
    type: Literal["claim.done"]


class IntentTapMessage(ClientModel):
    type: Literal["intent.tap"]
    unit_id: UnitGameId
    action: Action
    target_id: TargetGameId | None


class ChipCancelMessage(ClientModel):
    type: Literal["chip.cancel"]
    chip_id: Annotated[str, Field(min_length=36, max_length=36)]


class EndTurnMessage(ClientModel):
    type: Literal["end_turn"]


class NightNextMessage(ClientModel):
    type: Literal["night.next"]


class NightQuitMessage(ClientModel):
    type: Literal["night.quit"]


class NightPauseMessage(ClientModel):
    type: Literal["night.pause"]


class NightResumeMessage(ClientModel):
    type: Literal["night.resume"]
    force: bool = False


class DemoSafeMessage(ClientModel):
    type: Literal["demo_safe"]
    on: bool


class ConsentMessage(ClientModel):
    type: Literal["consent"]
    player_name: Annotated[str, Field(min_length=1, max_length=24)]
    agree: bool


class ReplayRequestMessage(ClientModel):
    type: Literal["replay.request"]


class EffectDoneMessage(ClientModel):
    type: Literal["effect.done"]


class PttMessage(ClientModel):
    type: Literal["ptt"]
    down: bool


class VoiceModeMessage(ClientModel):
    type: Literal["voice.mode"]
    mode: VoiceMode


class VoiceRetryMessage(ClientModel):
    type: Literal["voice.retry"]


class DemoSafeSamMessage(ClientModel):
    type: Literal["demo_safe.sam"]
    on: bool


ClientMessage = (
    CampaignListMessage
    | CampaignStartExisting
    | CampaignDeleteMessage
    | CampaignStartNew
    | DevicesListMessage
    | CameraSelectMessage
    | CalibrateCornersMessage
    | CalibrateDoneMessage
    | CalibrateRestartMessage
    | SummonNameMessage
    | SummonTapMessage
    | UnitRerollMessage
    | UnitRenameMessage
    | NightBeginMessage
    | ClaimTapMessage
    | ClaimDoneMessage
    | IntentTapMessage
    | ChipCancelMessage
    | EndTurnMessage
    | NightNextMessage
    | NightQuitMessage
    | NightPauseMessage
    | NightResumeMessage
    | DemoSafeMessage
    | DemoSafeSamMessage
    | PttMessage
    | EffectDoneMessage
    | ConsentMessage
    | ReplayRequestMessage
    | VoiceModeMessage
    | VoiceRetryMessage
)
CLIENT_MESSAGE: Final = TypeAdapter[ClientMessage](ClientMessage)

JsonObject = dict[str, object]


@dataclass(frozen=True)
class Services:
    settings: AppSettings
    controller: GameController
    pump: FramePump
    live: LiveState
    content: ContentFilter
    meter: CostMeter | None
    broadcast: Broadcast
    close: Callable[[], None]


ServicesFactory = Callable[[AppSettings], Services]


def build_services(settings: AppSettings) -> Services:
    store = Store(settings.database_path)
    live = LiveState()
    content = ContentFilter.from_data_dir()
    ffmpeg = find_ffmpeg(env=os.environ)
    sdk = None if settings.api_key is None else create_openai_client(settings.api_key)
    meta = MetaClient(sdk, CostMeter(store))
    broadcast = Broadcast()
    controller: GameController | None = None

    def log_invalid(reason: str) -> None:
        if controller is not None:
            controller.log_invalid(reason)

    controller = GameController(
        store,
        live,
        has_api_key=settings.api_key is not None,
        pipeline_factory=build_pipeline_factory(meta, content, log_invalid),
        meter=meta.meter,
        sprite_service_factory=build_sprite_factory(store, meta),
        segmenter_factory=build_segmenter_factory(meta),
        broadcast=broadcast,
        narration=build_narration(meta, content, log_invalid),
        voice_factory=build_voice_factory(settings.api_key, meta.meter),
        clean_name=content.clean_player_name,
        recorder_factory=build_recorder_factory(ffmpeg),
        replay_runner=build_replay_runner(meta),
        ffmpeg=ffmpeg,
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
        content=content,
        meter=meta.meter,
        broadcast=broadcast,
        close=close,
    )


def build_pipeline_factory(
    meta: MetaClient, content: ContentFilter, log_invalid: Callable[[str], None]
) -> PipelineFactory:
    def factory(is_demo_safe: bool) -> SummonPipeline:
        if is_demo_safe or not meta.has_credentials:
            return SummonPipeline(FallbackDetector(), TrackerOnlySegmenter(), content)
        return SummonPipeline(
            SparkDetector(meta, content, log_invalid), SamSegmenter(meta), content
        )

    return factory


def build_narration(
    meta: MetaClient, content: ContentFilter, log_invalid: Callable[[str], None]
) -> NarrationService:
    line_bank = LineBank()
    if not meta.has_credentials:
        return NarrationService(line_bank)
    return NarrationService(
        line_bank, lambda: SparkNarrator(meta, content, line_bank, log_invalid)
    )


def build_replay_runner(meta: MetaClient) -> ReplayRunner:
    async def runner(request: ReelRequest, is_paid: bool) -> ReelResult:
        if is_paid and meta.has_credentials:
            return await make_reel(request, meta, SamVideoTracker)
        return await make_reel(request, None, None)

    return runner


def build_recorder_factory(ffmpeg: str | None) -> RecorderFactory:
    def factory(path: Path, width: int, height: int, root: Path) -> Recorder:
        return Recorder(path, width, height, ffmpeg=ffmpeg, root=root)

    return factory


def build_voice_factory(api_key: str | None, meter: CostMeter) -> VoiceFactory | None:
    if api_key is None:
        return None
    key = api_key

    def factory(
        keywords: Sequence[str],
        on_caption: Callable[[Caption], None],
        on_final: Callable[[Caption], None],
        on_overlap: Callable[[], None],
        on_status: Callable[[VoiceStatus], None],
    ) -> VoiceSession:
        return VoiceSession(
            key,
            keywords,
            lambda: SoundDeviceMicrophone(None),
            WebsocketsConnector(),
            on_caption,
            on_final,
            on_overlap,
            on_status,
            meter,
            time.monotonic,
        )

    return factory


def build_segmenter_factory(meta: MetaClient) -> SegmenterFactory:
    live = SamSegmenter(meta)
    offline = TrackerOnlySegmenter()

    def factory(_: bool) -> Segmenter:
        return live if meta.has_credentials else offline

    return factory


def build_sprite_factory(store: Store, meta: MetaClient) -> SpriteServiceFactory:
    live_generator = MuseImageGenerator(meta, SamSegmenter(meta))
    placeholder = PlaceholderGenerator()

    def factory(is_demo_safe: bool) -> SpriteService:
        if is_demo_safe or not meta.has_credentials:
            return SpriteService(store, placeholder)
        return SpriteService(store, live_generator)

    return factory


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


def websocket_origins(raw: str, is_packaged: bool) -> frozenset[str]:
    origins = allowed_origins_from_env(raw)
    if not is_packaged:
        return origins
    return origins | {PACKAGED_RENDERER_ORIGIN}


def campaign_json(campaign: Campaign) -> JsonObject:
    return {
        "id": campaign.id,
        "name": campaign.name,
        "difficulty": campaign.difficulty.value,
        "nights_survived": campaign.nights_survived,
        "created_at": campaign.created_at,
    }


def unit_json(unit: UnitView) -> JsonObject:
    card = unit.card
    return {
        "id": unit.game_id,
        "unit_id": unit.unit_id,
        "sam_id": unit.sam_id,
        "name": card.name,
        "class": card.unit_class.value,
        "hp": unit.hp_current,
        "hp_max": card.hp_max,
        "atk": card.atk,
        "move": card.move_class.value,
        "range": card.range_class.value,
        "power_id": card.power_id.value,
        "power_name_tl": card.power_name_tl,
        "card_text_tl": card.card_text_tl,
        "card_text_en": card.card_text_en,
        "x_cm": unit.x_cm,
        "y_cm": unit.y_cm,
        "rerolls_left": unit.rerolls_left,
        "sprite_png": unit.sprite_png,
    }


def night_json(night: NightView) -> JsonObject:
    return {
        "number": night.number,
        "turn": night.turn,
        "difficulty": night.difficulty,
        "players": list(night.players),
        "units": [
            {
                "id": u.game_id,
                "hp": u.hp,
                "hp_max": u.hp_max,
                "cooldown": u.cooldown,
                "is_down": u.is_down,
                "is_move_legal": u.is_move_legal,
                "start_x_cm": u.start[0],
                "start_y_cm": u.start[1],
                "move_cm": u.move_cm,
                "range_cm": u.range_cm,
                "owner": u.owner,
                "status": list(u.status),
            }
            for u in night.units
        ],
        "enemies": [
            {
                "id": e.id,
                "type": e.type,
                "part": e.part,
                "hp": e.hp,
                "hp_max": e.hp_max,
                "x_cm": e.x_cm,
                "y_cm": e.y_cm,
                "intent": None
                if e.target_id is None
                else {"target_id": e.target_id, "dmg": e.intent_dmg or 0},
                "stunned": e.is_stunned,
            }
            for e in night.enemies
        ],
        "chips": [
            {
                "chip_id": c.chip_id,
                "unit_id": c.unit_id,
                "action": c.action,
                "target_id": c.target_id,
                "source": c.source,
                "speaker": c.speaker,
            }
            for c in night.chips
        ],
        "illegal_units": list(night.illegal_units),
        "kubo_hp": night.kubo_hp,
        "kubo_hp_max": night.kubo_hp_max,
        "effects": [
            {"kind": e.kind, "unit_id": e.unit_id, "x_cm": e.x_cm, "y_cm": e.y_cm}
            for e in night.effects
        ],
        "effect_seconds_left": night.effect_seconds_left,
    }


def score_json(score: FinalScore) -> JsonObject:
    return {
        "units_alive": score.units_alive,
        "kubo_hp": score.kubo_hp,
        "enemies_defeated": score.enemies_defeated,
        "score": score.score,
        "bayani": list(score.bayani),
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
        "demo_safe_sam": snapshot.is_demo_safe_sam,
        "has_api_key": snapshot.has_api_key,
        "units": [unit_json(unit) for unit in snapshot.units],
        "begin_block_key": snapshot.begin_block_key,
        "awaiting_tap": snapshot.is_awaiting_tap,
        "resume_turn": snapshot.resume_turn,
        "recording": snapshot.is_recording,
        "replay": {
            "status": snapshot.replay_status,
            "file": snapshot.replay_file,
            "available": snapshot.can_replay,
        },
        "consents": dict(snapshot.consents),
        "voice": {
            "status": snapshot.voice.status,
            "mode": snapshot.voice.mode,
            "ptt_down": snapshot.voice.is_ptt_down,
        },
        "night": None if snapshot.night is None else night_json(snapshot.night),
        "score": None if snapshot.score is None else score_json(snapshot.score),
    }


def card_json(unit: UnitView) -> JsonObject:
    return {"type": "card", "unit": unit_json(unit)}


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


COST_QUANTUM: Final = Decimal("0.000001")
REEL_TITLE_TL: Final = "SUMIKAT NA"
REEL_TITLE_EN: Final = "SUNRISE"


def cost_json(meter: CostMeter) -> JsonObject:
    return {
        "type": "cost",
        "spent_usd": str(meter.spent_usd.quantize(COST_QUANTUM)),
        "warn": meter.is_warning,
        "stopped": meter.is_stopped,
    }


def notice_json(copy_key: str, params: dict[str, str] | None = None) -> JsonObject:
    return {"type": "notice", "copy_key": copy_key, "params": params or {}}


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
        controller = self._services.controller
        controller.enforce_budget()
        for copy_key, params in controller.drain_notices():
            await self.send(notice_json(copy_key, params))
        await self.send(state_json(controller.snapshot()))
        meter = self._services.meter
        if self._services.settings.is_dev and meter is not None:
            await self.send(cost_json(meter))

    async def forward_broadcasts(self) -> None:
        queue = self._services.broadcast.subscribe()
        try:
            while True:
                message = await queue.get()
                if message.get("type") == STATE_CHANGED:
                    await self.send_state()
                else:
                    await self.send(message)
        finally:
            self._services.broadcast.unsubscribe(queue)

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
            await self.send(notice_json(error.copy_key, error.params))
            await self.send_state()
            return
        except NotFoundError:
            await self.send(notice_json(INVALID_MESSAGE_KEY))
            return
        except (
            StoreError,
            CalibrationError,
            CameraError,
            OSError,
            ValueError,
        ) as error:
            logger.warning("message handling failed with %s", type(error).__name__)
            await self.send(notice_json(FAILURE_KEY))
            await self.send_state()
            return
        except Exception:
            logger.exception("unexpected error while handling a message")
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
        if isinstance(message, CampaignDeleteMessage):
            await asyncio.to_thread(controller.delete_campaign, message.campaign_id)
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
                    {
                        "index": c.index,
                        "width": c.width,
                        "height": c.height,
                        "has_picture": c.has_picture,
                    }
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
        if isinstance(message, SummonNameMessage):
            return card_json(await controller.summon(message.name))
        if isinstance(message, SummonTapMessage):
            return card_json(await controller.summon_tap(message.point))
        if isinstance(message, UnitRerollMessage):
            return card_json(await controller.reroll_unit(message.unit_id))
        if isinstance(message, UnitRenameMessage):
            content = self._services.content
            return card_json(
                controller.rename_unit(
                    message.unit_id, message.name, content.clean_player_name
                )
            )
        if isinstance(message, NightBeginMessage):
            controller.begin_night()
            return None
        if isinstance(message, ClaimTapMessage):
            content = self._services.content
            controller.claim(
                message.player_name, message.unit_ids, content.clean_player_name
            )
            return None
        if isinstance(message, ClaimDoneMessage):
            controller.finish_claims()
            return None
        if isinstance(message, IntentTapMessage):
            controller.add_intent(message.unit_id, message.action, message.target_id)
            return None
        if isinstance(message, ChipCancelMessage):
            controller.cancel_chip(message.chip_id)
            return None
        if isinstance(message, EndTurnMessage):
            await controller.end_turn()
            return None
        if isinstance(message, NightNextMessage):
            controller.next_night()
            return None
        if isinstance(message, NightQuitMessage):
            controller.quit_night()
            return None
        if isinstance(message, NightPauseMessage):
            controller.pause_night()
            return None
        if isinstance(message, NightResumeMessage):
            await asyncio.to_thread(controller.resume_night, message.force)
            return None
        if isinstance(message, ReplayRequestMessage):
            controller.request_replay(REEL_TITLE_TL, REEL_TITLE_EN)
            return None
        if isinstance(message, ConsentMessage):
            controller.give_consent(message.player_name, message.agree)
            return None
        if isinstance(message, EffectDoneMessage):
            controller.finish_effects_now()
            return None
        if isinstance(message, PttMessage):
            controller.set_ptt(message.down)
            return None
        if isinstance(message, VoiceModeMessage):
            controller.set_voice_mode(message.mode)
            return None
        if isinstance(message, VoiceRetryMessage):
            controller.retry_voice()
            return None
        if isinstance(message, DemoSafeSamMessage):
            await asyncio.to_thread(controller.set_demo_safe_sam, message.on)
            return None
        await asyncio.to_thread(controller.set_demo_safe, message.on)
        return None


RECOVERY_INTERVAL_S: Final = 1.0


async def recover_forever(controller: GameController) -> None:
    while True:
        await asyncio.sleep(RECOVERY_INTERVAL_S)
        try:
            controller.enforce_claim_timeout()
            controller.enforce_effects()
        except GameError:
            logger.warning("timed night step skipped")
        except Exception:
            logger.exception("timed night step failed, will retry")
        try:
            await controller.recover_lost_objects()
        except GameError:
            logger.warning("between-turn recovery skipped")
        except Exception:
            logger.exception("between-turn recovery failed, will retry")


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
        recovery = asyncio.create_task(recover_forever(services.controller))
        yield
        recovery.cancel()
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
        forwarder = asyncio.create_task(connection.forward_broadcasts())
        try:
            await connection.receive()
        except WebSocketDisconnect:
            logger.info("websocket closed")
        finally:
            sender.cancel()
            forwarder.cancel()

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
    origins = websocket_origins(
        os.environ.get("DESKTOP_ALLOWED_ORIGINS", ""),
        os.environ.get(PACKAGED_FLAG) == "1",
    )
    return create_app(settings, origins)

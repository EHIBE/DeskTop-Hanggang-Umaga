from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import re
import threading
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Final

import cv2
import numpy as np
import numpy.typing as npt

from capture.calibration import (
    Calibration,
    CalibrationError,
    Corners,
    PlayArea,
    compute_calibration,
    is_camera_moved,
    warp,
)
from capture.camera import (
    Camera,
    CameraError,
    CameraInfo,
    MicrophoneInfo,
    SourceFactory,
    list_cameras,
    list_microphones,
    open_directshow,
)
from capture.recorder import Recorder, RecorderError
from capture.tracker import TrackedPose, TrackerSet
from config import (
    HANDS_OFF_WAIT_S,
    NIGHT_COST_ALERT_USD,
    PHYSICAL_EFFECT_TIMEOUT_S,
    PUSH_COMPLIANCE_CM,
    REANCHOR_BOX_PADDING,
    SAM_ACCEPT_CONFIDENCE,
    STILL_FRAME_MEAN_DIFF_MAX,
    STREAM_FPS,
    STREAM_JPEG_QUALITY,
    STREAM_WIDTH_PX,
    SUMMON_SNAPSHOT_DELAY_S,
    VOICE_CLAIM_TIMEOUT_S,
)
from db.store import (
    Campaign,
    CardFields,
    EnemySave,
    NightRecord,
    SavedNight,
    SignatureFields,
    Store,
    StoreError,
    UnitPlacement,
    UnitRecord,
    UnitSave,
)
from game.demo_safe import DemoSafeMode
from game.state_machine import Transition, TurnEvent, TurnState, TurnStateMachine
from gm.narrator import (
    Narration,
    NarrationEnemy,
    NarrationPhase,
    NarrationRequest,
    NarrationService,
    NarrationUnit,
)
from meta_client import CostMeter, MetaError
from replay.highlights import ReplayError, TurnLogRow
from replay.render import ReelRequest, ReelResult
from rules.enemies import EnemyType, Part, enemy_stats
from rules.geometry import Hull, Point, is_move_legal
from rules.resolve import (
    TURNS_PER_NIGHT,
    Action,
    BoardState,
    EnemyState,
    Event,
    EventType,
    Intent,
    Outcome,
    UnitState,
    apply_enemy_tags,
    apply_unit_tags,
    bayani,
    begin_turn,
    check_outcome,
    enemy_status_tags,
    illegal_moves,
    intent_error,
    moved_kubo,
    resolve_turn,
    score,
    start_night,
    unit_status_tags,
    with_positions,
)
from rules.units import (
    MOVE_CM,
    RANGE_CM,
    REROLLS_PER_UNIT,
    Difficulty,
    UnitClass,
    begin_night_block_key,
    clamp_card,
)
from state import Broadcast, EncodedFrame, FrameView, LiveState, Pose
from vision.sam import (
    Anchor,
    ObjectMask,
    ObjectPrompt,
    PixelBox,
    ReanchorTarget,
    SegmentationError,
    Segmenter,
    TrackerOnlySegmenter,
    clamp_box,
    pad_box,
    reanchor,
)
from vision.signature import SignatureError, bhattacharyya, histogram
from vision.sprites import (
    FALLBACK_SUBJECT,
    SpriteError,
    SpriteJob,
    SpriteService,
    prepare_crop,
)
from vision.summon import (
    Detection,
    KnownObject,
    SummonError,
    SummonOutcome,
    SummonPipeline,
    SummonRequest,
)
from voice.claim import ClaimUnit, parse_claim
from voice.grammar import (
    Command,
    CommandKind,
    GrammarContext,
    GrammarEnemy,
    GrammarUnit,
    parse_command,
)
from voice.session import Caption, VoiceMode, VoiceSession, VoiceStatus

logger = logging.getLogger("desktop.game")

ReplayRunner = Callable[[ReelRequest, bool], Awaitable[ReelResult]]

RecorderFactory = Callable[[Path, int, int, Path], Recorder]

VoiceFactory = Callable[
    [
        Sequence[str],
        Callable[[Caption], None],
        Callable[[Caption], None],
        Callable[[], None],
        Callable[[VoiceStatus], None],
    ],
    VoiceSession,
]

TAP_SOURCE: Final = "tap"
VOICE_SOURCE: Final = "voice"

Image = npt.NDArray[np.uint8]

FIRST_FRAME_TIMEOUT_S: Final = 3.0
FIRST_FRAME_POLL_S: Final = 0.05
CAMERA_SETTING: Final = "camera_index"
REROLLS_FLAG: Final = "rerolls"
SETUP_TURN: Final = 0
SUMMON_PHASE: Final = "SUMMON"
DEFAULT_BOX_HALF_CM: Final = 2.0
KUBO_GAME_ID: Final = "u_kubo"
KUBO_SAM_ID: Final = 1
BUSY_KEY: Final = "endturn.checking"
OFFLINE_KEY: Final = "net.down"
SPARK_FEATURE: Final = "Muse Spark"


class AppPhase(StrEnum):
    START = "START"
    CALIBRATE = "CALIBRATE"
    SUMMON = "SUMMON"
    VOICE_CLAIM = "VOICE_CLAIM"
    SPAWN_TELEGRAPH = "SPAWN_TELEGRAPH"
    PLAYER_PHASE = "PLAYER_PHASE"
    END_TURN_SNAPSHOT = "END_TURN_SNAPSHOT"
    VALIDATE = "VALIDATE"
    RESOLVE_PLAYER = "RESOLVE_PLAYER"
    RESOLVE_ENEMY = "RESOLVE_ENEMY"
    PHYSICAL_EFFECTS = "PHYSICAL_EFFECTS"
    CHECK_END = "CHECK_END"
    SUNRISE = "SUNRISE"
    DEFEAT = "DEFEAT"
    REPLAY = "REPLAY"
    PAUSED = "PAUSED"


@dataclass(frozen=True)
class NightUnitView:
    game_id: str
    hp: int
    hp_max: int
    cooldown: int
    is_down: bool
    is_move_legal: bool
    start: tuple[float, float]
    move_cm: float
    range_cm: float
    owner: str | None
    status: tuple[str, ...] = ()


@dataclass(frozen=True)
class EnemyView:
    id: str
    type: str
    part: str | None
    hp: int
    hp_max: int
    x_cm: float
    y_cm: float
    target_id: str | None
    intent_dmg: int | None
    is_stunned: bool


@dataclass(frozen=True)
class ChipView:
    chip_id: str
    unit_id: str
    action: str
    target_id: str | None
    source: str = TAP_SOURCE
    speaker: str | None = None


@dataclass(frozen=True)
class NightView:
    number: int
    turn: int
    difficulty: str
    players: tuple[str, ...]
    units: tuple[NightUnitView, ...]
    enemies: tuple[EnemyView, ...]
    chips: tuple[ChipView, ...]
    illegal_units: tuple[str, ...]
    kubo_hp: int
    kubo_hp_max: int
    effects: tuple[PhysicalEffect, ...] = ()
    effect_seconds_left: int = 0


class GameError(Exception):
    def __init__(self, copy_key: str, params: dict[str, str] | None = None) -> None:
        super().__init__(copy_key)
        self.copy_key = copy_key
        self.params: dict[str, str] = params or {}


@dataclass(frozen=True)
class UnitView:
    game_id: str
    unit_id: str
    sam_id: int
    card: CardFields
    hp_current: int
    x_cm: float
    y_cm: float
    rerolls_left: int
    sprite_png: str | None = None


PipelineFactory = Callable[[bool], SummonPipeline]
SpriteServiceFactory = Callable[[bool], SpriteService]
SegmenterFactory = Callable[[bool], Segmenter]
NO_MATCH_DISTANCE: Final = float("inf")


def safe_histogram(image: Image, mask: ObjectMask) -> tuple[float, ...]:
    try:
        return histogram(image, mask)
    except SignatureError:
        return ()


def safe_distance(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    if not first or not second or len(first) != len(second):
        return NO_MATCH_DISTANCE
    try:
        return bhattacharyya(first, second)
    except SignatureError:
        return NO_MATCH_DISTANCE


TrackerFactory = Callable[[float, tuple[int, int]], TrackerSet]


def default_tracker(px_per_cm: float, warped_size: tuple[int, int]) -> TrackerSet:
    return TrackerSet(px_per_cm=px_per_cm, warped_size=warped_size)


def game_id_for(sam_id: int) -> str:
    return KUBO_GAME_ID if sam_id == KUBO_SAM_ID else f"u_{sam_id}"


@dataclass(frozen=True)
class VoiceView:
    status: str
    mode: str
    is_ptt_down: bool


@dataclass(frozen=True)
class Snapshot:
    phase: AppPhase
    campaign: Campaign | None
    camera: CameraInfo | None
    is_calibrated: bool
    is_previewing: bool
    play_w_cm: float
    play_h_cm: float
    is_demo_safe: bool
    is_demo_safe_sam: bool
    has_api_key: bool
    units: tuple[UnitView, ...] = field(default=())
    begin_block_key: str | None = None
    is_awaiting_tap: bool = False
    resume_turn: int | None = None
    is_recording: bool = False
    consents: tuple[tuple[str, bool], ...] = ()
    replay_status: str = "idle"
    replay_file: str | None = None
    can_replay: bool = False
    voice: VoiceView = VoiceView(VoiceStatus.OFF.value, VoiceMode.OPEN.value, False)
    night: NightView | None = None
    score: FinalScore | None = None


@dataclass(frozen=True)
class Devices:
    cameras: tuple[CameraInfo, ...]
    microphones: tuple[MicrophoneInfo, ...]


def encode_jpeg(image: Image) -> tuple[str, int, int]:
    height, width = image.shape[:2]
    scale = STREAM_WIDTH_PX / width
    resized = cv2.resize(
        image, (STREAM_WIDTH_PX, round(height * scale)), interpolation=cv2.INTER_AREA
    )
    ok, buffer = cv2.imencode(
        ".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, STREAM_JPEG_QUALITY]
    )
    if not ok:
        raise GameError("cam.busy")
    return base64.b64encode(buffer.tobytes()).decode("ascii"), width, height


def encode_png(image: Image) -> bytes:
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise GameError("cam.busy")
    return buffer.tobytes()


class GameController:
    def __init__(
        self,
        store: Store,
        live: LiveState,
        has_api_key: bool,
        camera_factory: SourceFactory = open_directshow,
        list_camera_devices: Callable[[], list[CameraInfo]] = list_cameras,
        list_microphone_devices: Callable[[], list[MicrophoneInfo]] = list_microphones,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        pipeline_factory: PipelineFactory | None = None,
        meter: CostMeter | None = None,
        sprite_service_factory: SpriteServiceFactory | None = None,
        broadcast: Broadcast | None = None,
        segmenter_factory: SegmenterFactory | None = None,
        tracker_factory: TrackerFactory = default_tracker,
        narration: NarrationService | None = None,
        voice_factory: VoiceFactory | None = None,
        clean_name: Callable[[str, str], str] | None = None,
        recorder_factory: RecorderFactory | None = None,
        replay_runner: ReplayRunner | None = None,
        ffmpeg: str | None = None,
    ) -> None:
        self._replay_runner = replay_runner
        self._ffmpeg = ffmpeg
        self._recorder_factory = recorder_factory
        self._recorder: Recorder | None = None
        self._sidecar: dict[str, object] | None = None
        self._sidecar_path: Path | None = None
        self._last_sidecar: Path | None = None
        self._replay_status = REPLAY_IDLE
        self._replay_file: str | None = None
        self._replay_task: asyncio.Task[None] | None = None
        self._clean_name = clean_name
        self._consents: dict[str, bool] = {}
        self._voice_players: dict[str, str] = {}
        self._narration = narration
        self._voice_factory = voice_factory
        self._voice: VoiceSession | None = None
        self._voice_status = VoiceStatus.OFF
        self._voice_mode = VoiceMode.OPEN
        self._is_ptt_down = False
        self._voice_tasks: set[asyncio.Task[None]] = set()
        self._voice_turns: set[asyncio.Task[None]] = set()
        self._segmenter_factory = segmenter_factory
        self._tracker_factory = tracker_factory
        self._tracker: TrackerSet | None = None
        self._is_tracker_dirty = True
        self._poses: dict[int, TrackedPose] = {}
        self._uncertain: set[int] = set()
        self._sprite_service_factory = sprite_service_factory
        self._session: NightSession | None = None
        self._resume_turn: int | None = None
        self._baseline: Image | None = None
        self._effects_started = 0.0
        self._effect_events: tuple[Event, ...] = ()
        self._claim_started = 0.0
        self._broadcast = broadcast
        self._crops: dict[str, Image] = {}
        self._subjects: dict[str, str] = {}
        self._sprites: dict[str, str] = {}
        self._sprite_tasks: set[asyncio.Task[None]] = set()
        self._sprite_jobs: dict[str, asyncio.Task[None]] = {}
        self._sprite_versions: dict[str, int] = {}
        self._store = store
        self._meter = meter
        self._notices: list[tuple[str, dict[str, str]]] = []
        self._night_spend_start = Decimal(0)
        self._is_night_alerted = False
        self._pipeline_factory = pipeline_factory
        self._night: NightRecord | None = None
        self._units: list[UnitRecord] = []
        self._boxes: dict[int, PixelBox] = {}
        self._pending: Detection | None = None
        self._pending_name = ""
        self._summon_lock = asyncio.Lock()
        self._live = live
        self._has_api_key = has_api_key
        self._camera_factory = camera_factory
        self._list_cameras = list_camera_devices
        self._list_microphones = list_microphone_devices
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.RLock()
        self._campaign: Campaign | None = None
        self._camera: Camera | None = None
        self._camera_info: CameraInfo | None = None
        self._area = PlayArea()
        self._calibration: Calibration | None = None
        self._is_calibrated = False
        self._is_stored_calibration = False
        self._demo_safe = DemoSafeMode.load(store)

    def snapshot(self) -> Snapshot:
        with self._lock:
            return Snapshot(
                phase=self._phase(),
                campaign=self._campaign,
                camera=self._camera_info,
                is_calibrated=self._is_calibrated,
                is_previewing=self._calibration is not None and not self._is_calibrated,
                play_w_cm=self._area.width_cm,
                play_h_cm=self._area.height_cm,
                is_demo_safe=self._demo_safe.is_on,
                is_demo_safe_sam=self._demo_safe.is_sam_reanchor_on,
                has_api_key=self._has_api_key,
                units=tuple(self._unit_view(unit) for unit in self._units),
                begin_block_key=begin_night_block_key(
                    [u.card.unit_class for u in self._units]
                ),
                is_awaiting_tap=self._pending is not None,
                resume_turn=self._resume_turn,
                is_recording=self.is_recording,
                replay_status=self._replay_status,
                replay_file=self._replay_file,
                can_replay=self._last_sidecar is not None
                and self._replay_runner is not None,
                consents=tuple(self._consents.items()),
                voice=VoiceView(
                    self._voice_status.value, self._voice_mode.value, self._is_ptt_down
                ),
                night=self._night_view(),
                score=None if self._session is None else self._session.final_score,
            )

    def _phase(self) -> AppPhase:
        if self._campaign is None:
            return AppPhase.START
        if not self._is_calibrated:
            return AppPhase.CALIBRATE
        if self._session is not None:
            return AppPhase(self._session.state.value)
        return AppPhase.SUMMON

    def _night_view(self) -> NightView | None:
        session = self._session
        night = self._night
        if session is None or night is None or self._campaign is None:
            return None
        board = session.board
        poses = {pose.id: (pose.x_cm, pose.y_cm) for pose in self._pose_list()}
        units: list[NightUnitView] = []
        enemies: list[EnemyView] = []
        kubo_hp, kubo_max = 0, 0
        if board is not None:
            for unit in board.units:
                current = poses.get(unit.id, unit.position)
                move_cm = MOVE_CM[unit.move]
                legal = unit.is_kubo or is_move_legal(unit.start, current, move_cm)
                units.append(
                    NightUnitView(
                        game_id=unit.id,
                        hp=max(0, unit.hp),
                        hp_max=unit.hp_max,
                        cooldown=unit.cooldown,
                        is_down=unit.is_down,
                        is_move_legal=legal and unit.id not in session.illegal_units,
                        start=unit.start,
                        move_cm=0.0 if unit.is_kubo else move_cm,
                        range_cm=RANGE_CM[unit.range],
                        owner=unit.owner,
                        status=unit_status_tags(unit),
                    )
                )
                if unit.is_kubo:
                    kubo_hp, kubo_max = max(0, unit.hp), unit.hp_max
            enemies = [
                EnemyView(
                    id=e.id,
                    type=e.type.value,
                    part=None if e.part is None else e.part.value,
                    hp=max(0, e.hp),
                    hp_max=e.hp_max,
                    x_cm=e.position[0],
                    y_cm=e.position[1],
                    target_id=e.target_id,
                    intent_dmg=e.intent_dmg,
                    is_stunned=e.is_stunned,
                )
                for e in board.enemies
                if e.is_alive
            ]
        chips = tuple(
            ChipView(
                c.chip_id,
                c.intent.unit_id,
                c.intent.action.value,
                c.intent.target_id,
                c.source,
                c.speaker,
            )
            for c in session.chips
        )
        return NightView(
            number=night.number,
            turn=0 if board is None else board.turn,
            difficulty=self._campaign.difficulty.value,
            players=session.players,
            units=tuple(units),
            enemies=tuple(enemies),
            chips=chips,
            illegal_units=session.illegal_units,
            kubo_hp=kubo_hp,
            kubo_hp_max=kubo_max,
            effects=session.effects,
            effect_seconds_left=max(
                0,
                math.ceil(
                    PHYSICAL_EFFECT_TIMEOUT_S - (self._clock() - self._effects_started)
                ),
            )
            if session.effects
            else 0,
        )

    def _notify(self, copy_key: str, params: dict[str, str]) -> None:
        self._notices.append((copy_key, params))

    def _session_or_error(self) -> NightSession:
        if self._session is None:
            raise GameError("cmd.unknown")
        return self._session

    def _run_session[T](self, action: Callable[[], T]) -> T:
        try:
            return action()
        except SessionError as error:
            raise GameError(error.copy_key, error.params) from error

    def begin_night(self) -> None:
        self._require_phase(AppPhase.SUMMON)
        night = self._night
        if night is None or self._campaign is None:
            raise GameError("start.ready")
        block = begin_night_block_key([u.card.unit_class for u in self._units])
        if block is not None:
            raise GameError(block)
        saved = self._store.saved_night(night.id)
        session = NightSession(
            self._store,
            night,
            self._units,
            {u.unit_id: game_id_for(u.sam_object_id) for u in self._units},
            self._campaign.difficulty,
            (self._area.width_cm, self._area.height_cm),
            self._notify,
            self._clock,
        )
        self._stop_narration()
        if saved is not None:
            self._resume(session, saved)
            return
        self._run_session(session.begin)
        self._session = session
        self._consents = {}
        self._claim_started = self._clock()
        self._notify("night.start", {})
        self._start_voice()

    def enforce_claim_timeout(self) -> bool:
        session = self._session
        if session is None or session.state is not TurnState.VOICE_CLAIM:
            return False
        if self._clock() - self._claim_started < VOICE_CLAIM_TIMEOUT_S:
            return False
        self.finish_claims()
        if self._broadcast is not None:
            self._broadcast.publish({"type": STATE_CHANGED})
        return True

    def _resume(self, session: NightSession, saved: SavedNight) -> None:
        night = self._night
        if night is None:
            raise GameError("start.ready")
        game_ids = {u.unit_id: game_id_for(u.sam_object_id) for u in self._units}
        owners = {
            game_ids[unit_id]: name
            for unit_id, name in self._store.unit_owners(night.id).items()
            if unit_id in game_ids
        }
        poses = {pose.id: (pose.x_cm, pose.y_cm) for pose in self._pose_list()}
        sizes = self._unit_sizes()
        result = self._run_session(lambda: session.restore(saved, poses, sizes, owners))
        self._session = session
        self._resume_turn = None
        self._seed_boxes_from_board(session)
        self._notify("restore", {})
        self._publish_events(result)
        self._narrate(NarrationPhase.RESOLUTION_THEN_TELEGRAPH, result.telegraph)
        self._start_voice()

    def claim(
        self,
        player_name: str,
        game_ids: Sequence[str],
        clean: Callable[[str, str], str],
    ) -> None:
        session = self._session_or_error()
        name = clean(player_name, "")
        if not name:
            raise GameError("claim.who")
        self._run_session(lambda: session.claim(name, game_ids))

    def finish_claims(self) -> None:
        session = self._session_or_error()
        poses = {pose.id: (pose.x_cm, pose.y_cm) for pose in self._pose_list()}
        sizes = self._unit_sizes()
        is_agreed = self.is_recording_agreed
        result = self._run_session(lambda: session.finish_claims(poses, sizes))
        night = self._night
        if night is not None:
            try:
                self._store.set_recording_consent(night.id, is_agreed)
            except StoreError:
                logger.warning("consent write failed")
        self._publish_events(result)
        if is_agreed:
            self._start_recording()
        self._narrate(NarrationPhase.NIGHT_START, result.telegraph)
        self._start_voice()

    def _unit_sizes(self) -> dict[str, tuple[float, float]]:
        ppc = float(self._area.px_per_cm)
        sizes: dict[str, tuple[float, float]] = {}
        for unit in self._units:
            box = self._boxes.get(unit.sam_object_id)
            if box is None:
                continue
            sizes[game_id_for(unit.sam_object_id)] = (
                box.width / ppc / 2,
                box.height / ppc / 2,
            )
        return sizes

    def add_intent(self, game_id: str, action: Action, target_id: str | None) -> None:
        session = self._session_or_error()
        self._run_session(lambda: session.add_intent(game_id, action, target_id))

    def cancel_chip(self, chip_id: str) -> None:
        session = self._session_or_error()
        self._run_session(lambda: session.cancel_chip(chip_id))

    async def end_turn(self) -> None:
        session = self._session_or_error()
        self._run_session(session.start_end_turn)
        try:
            frame = await asyncio.to_thread(self.wait_for_still_frame)
            if frame is None:
                raise GameError("cam.busy")
            if self._is_camera_moved(frame):
                session.cancel_end_turn()
                self._run_session(session.pause)
                self._stop_voice()
                self._notify("cam.moved", {})
                return
            anchors = await self.reanchor_all(frame)
        except GameError:
            session.cancel_end_turn()
            raise
        except (StoreError, OSError, ValueError, cv2.error) as error:
            logger.exception("end turn snapshot failed")
            session.cancel_end_turn()
            raise GameError("restore") from error
        ppc = float(self._area.px_per_cm)
        positions: dict[str, tuple[float, float]] = {}
        hulls: dict[str, Hull] = {}
        for unit in self._units:
            game_id = game_id_for(unit.sam_object_id)
            anchor = anchors.get(unit.sam_object_id)
            if anchor is None:
                continue
            positions[game_id] = (anchor.x_cm, anchor.y_cm)
            hulls[game_id] = hull_offsets_from_box(
                anchor.box.width / ppc / 2, anchor.box.height / ppc / 2
            )
        result = self._run_session(lambda: session.finish_end_turn(positions, hulls))
        self._publish_events(result)
        if result.is_blocked:
            return
        if result.effects:
            self._effects_started = self._clock()
            self._effect_events = result.events
            return
        self._after_resolution(session, result.events, result.telegraph)

    def _after_resolution(
        self,
        session: NightSession,
        events: tuple[Event, ...],
        telegraph: tuple[Event, ...],
    ) -> None:
        if session.state is TurnState.SUNRISE:
            self._narrate(NarrationPhase.SUNRISE, events)
            self._stop_voice()
            self._stop_recording()
        elif session.state is TurnState.DEFEAT:
            self._narrate(NarrationPhase.DEFEAT, events)
            self._stop_voice()
            self._stop_recording()
        else:
            self._narrate(NarrationPhase.RESOLUTION_THEN_TELEGRAPH, events + telegraph)

    def enforce_effects(self) -> bool:
        session = self._session
        if session is None or session.state is not TurnState.PHYSICAL_EFFECTS:
            return False
        poses = {pose.id: pose for pose in self._pose_list()}
        is_done = all(self._is_effect_done(effect, poses) for effect in session.effects)
        if (
            not is_done
            and self._clock() - self._effects_started < PHYSICAL_EFFECT_TIMEOUT_S
        ):
            return False
        if not is_done:
            self._notify("effect.timeout", {})
        self._finish_effects(session, poses)
        return True

    def finish_effects_now(self) -> None:
        session = self._session_or_error()
        if session.state is not TurnState.PHYSICAL_EFFECTS:
            raise GameError("cmd.unknown")
        self._finish_effects(session, {pose.id: pose for pose in self._pose_list()})

    @staticmethod
    def _is_effect_done(effect: PhysicalEffect, poses: Mapping[str, Pose]) -> bool:
        pose = poses.get(effect.unit_id)
        if effect.kind == STEAL_EFFECT:
            return pose is None or pose.uncertain
        if pose is None or pose.uncertain:
            return False
        return (
            math.hypot(pose.x_cm - effect.x_cm, pose.y_cm - effect.y_cm)
            <= PUSH_COMPLIANCE_CM
        )

    def _finish_effects(self, session: NightSession, poses: Mapping[str, Pose]) -> None:
        positions = {
            game_id: (pose.x_cm, pose.y_cm)
            for game_id, pose in poses.items()
            if not pose.uncertain
        }
        result = self._run_session(lambda: session.finish_effects(positions))
        self._publish_events(result)
        events = self._effect_events
        self._effect_events = ()
        self._after_resolution(session, events, result.telegraph)
        self._push_state()

    def _publish_events(self, result: TurnResult) -> None:
        if self._broadcast is None:
            return
        session = self._session
        turn = 0 if session is None or session.board is None else session.board.turn
        if result.events:
            self._broadcast.publish(
                {
                    "type": "events",
                    "turn": max(0, turn - 1) if result.telegraph else turn,
                    "events": [event_json(e) for e in result.events],
                }
            )
        if result.telegraph:
            self._broadcast.publish(
                {
                    "type": "events",
                    "turn": turn,
                    "events": [event_json(e) for e in result.telegraph],
                }
            )

    def _is_camera_moved(self, warped: Image) -> bool:
        baseline = self._baseline
        if baseline is None or baseline.shape != warped.shape:
            return False
        try:
            return is_camera_moved(baseline, warped, self._area)
        except (CalibrationError, cv2.error):
            logger.exception("camera move check failed")
            return False

    def pause_night(self) -> None:
        session = self._session_or_error()
        self._run_session(session.pause)
        self._stop_voice()

    def resume_night(self, is_forced: bool) -> None:
        session = self._session_or_error()
        if session.state is not TurnState.PAUSED:
            raise GameError("cmd.unknown")
        frame = self.wait_for_still_frame()
        if frame is not None and self._is_camera_moved(frame):
            if not is_forced:
                raise GameError("cam.moved")
            self._baseline = frame
        self._run_session(session.resume)
        self._start_voice()

    def _reset_replay(self) -> None:
        if self._replay_status != REPLAY_WORKING:
            self._replay_status = REPLAY_IDLE
            self._replay_file = None
            self._last_sidecar = None

    def next_night(self) -> None:
        session = self._session_or_error()
        if session.state not in (TurnState.SUNRISE, TurnState.DEFEAT):
            raise GameError("cmd.unknown")
        self._stop_narration()
        self._reset_replay()
        self._session = None
        self._enter_summon()

    def quit_night(self) -> None:
        session = self._session_or_error()
        if session.state not in (TurnState.SUNRISE, TurnState.DEFEAT):
            raise GameError("cmd.unknown")
        self._stop_narration()
        self._session = None
        with self._lock:
            self._campaign = None
            self._night = None
            self._units = []
            self._boxes = {}
            self._is_calibrated = False
            self._calibration = None

    def list_campaigns(self) -> list[Campaign]:
        return self._store.list_campaigns()

    def delete_campaign(self, campaign_id: str) -> None:
        self._require_phase(AppPhase.START)
        try:
            is_deleted = self._store.delete_campaign(campaign_id)
        except StoreError as error:
            logger.exception("campaign delete failed")
            raise GameError("delete.failed") from error
        if not is_deleted:
            raise GameError("cmd.unknown")
        self._notify("delete.done", {})

    def devices(self) -> Devices:
        return Devices(
            cameras=tuple(self._list_cameras()),
            microphones=tuple(self._list_microphones()),
        )

    def start_new_campaign(self, name: str, difficulty: Difficulty) -> None:
        campaign = self._store.create_campaign(name.strip(), difficulty)
        self._enter_campaign(campaign)

    def continue_campaign(self, campaign_id: str) -> None:
        self._enter_campaign(self._store.get_campaign(campaign_id))

    def _enter_campaign(self, campaign: Campaign) -> None:
        session = self._session
        if session is not None and session.state not in (
            TurnState.SUNRISE,
            TurnState.DEFEAT,
        ):
            raise GameError("cmd.unknown")
        self._stop_narration()
        self._session = None
        with self._lock:
            self._campaign = campaign
            self._calibration = None
            self._is_calibrated = False
            self._is_stored_calibration = False
            self._area = PlayArea()
            self._night = None
            self._units = []
            self._boxes = {}
            self._pending = None
            stored = self._store.latest_calibration(campaign.id)
            if stored is None:
                return
            try:
                area = PlayArea(width_cm=stored.play_w_cm, height_cm=stored.play_h_cm)
            except CalibrationError:
                logger.warning("stored calibration has an invalid play area")
                return
            self._area = area
            self._calibration = Calibration(
                homography=np.array(stored.homography, dtype=np.float64).reshape(3, 3),
                area=area,
            )
            self._is_stored_calibration = True
            if self._camera is not None:
                self._check_stored_calibration()

    def select_camera(self, index: int) -> None:
        with self._lock:
            self._close_camera()
            camera = Camera(index, factory=self._camera_factory, clock=self._clock)
            try:
                width, height = camera.open()
            except CameraError as error:
                logger.warning(
                    "camera %s could not open: %s", index, type(error).__name__
                )
                raise GameError("cam.busy") from error
            camera.start()
            self._camera = camera
            self._camera_info = CameraInfo(index=index, width=width, height=height)
            self._store.set_setting(CAMERA_SETTING, str(index))
            if self._is_stored_calibration and not self._is_calibrated:
                self._check_stored_calibration()

    def _check_stored_calibration(self) -> None:
        if self._campaign is None or self._calibration is None:
            return
        stored = self._store.latest_calibration(self._campaign.id)
        frame = self.wait_for_frame()
        if stored is None or frame is None:
            return
        try:
            encoded = stored.baseline_path.read_bytes()
        except OSError as error:
            raise GameError("cam.moved") from error
        baseline = cv2.imdecode(
            np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR
        )
        current = warp(frame, self._calibration)
        if baseline is None or baseline.shape != current.shape:
            raise GameError("cam.moved")
        stored_baseline = np.asarray(baseline, dtype=np.uint8)
        if is_camera_moved(stored_baseline, current, self._area):
            raise GameError("cam.moved")
        self._baseline = stored_baseline
        self._is_calibrated = True
        self._enter_summon()

    def wait_for_frame(self) -> Image | None:
        camera = self._camera
        if camera is None:
            return None
        deadline = self._clock() + FIRST_FRAME_TIMEOUT_S
        while self._clock() < deadline:
            frame = camera.latest()
            if frame is not None:
                return frame.image
            self._sleep(FIRST_FRAME_POLL_S)
        return None

    def submit_corners(
        self, corners: Corners, width_cm: float, height_cm: float
    ) -> None:
        with self._lock:
            self._require_phase(AppPhase.CALIBRATE)
            if self._camera is None:
                raise GameError("cam.busy")
            try:
                area = PlayArea(width_cm=width_cm, height_cm=height_cm)
                calibration = compute_calibration(corners, area)
            except CalibrationError as error:
                raise GameError("calib.tap") from error
            self._area = area
            self._calibration = calibration
            self._is_stored_calibration = False

    def confirm_calibration(self) -> None:
        with self._lock:
            self._require_phase(AppPhase.CALIBRATE)
            if self._calibration is None or self._campaign is None:
                raise GameError("calib.tap")
            frame = self.wait_for_frame()
            if frame is None:
                raise GameError("cam.busy")
            baseline = warp(frame, self._calibration)
            self._baseline = baseline
            self._store.save_calibration(
                self._campaign.id,
                self._calibration.homography_list(),
                float(self._area.px_per_cm),
                (self._area.width_cm, self._area.height_cm),
                encode_png(baseline),
            )
            self._is_calibrated = True
            self._enter_summon()

    def restart_calibration(self) -> None:
        session = self._session
        if session is not None and session.state in ACTIVE_NIGHT_STATES:
            raise GameError("cmd.unknown")
        with self._lock:
            if self._campaign is None:
                raise GameError("start.ready")
            self._calibration = None
            self._is_calibrated = False
            self._is_stored_calibration = False

    def _enter_summon(self) -> None:
        if self._campaign is None:
            return
        self._night = self._store.start_or_resume_night(self._campaign.id)
        self._night_spend_start = (
            self._meter.spent_usd if self._meter is not None else Decimal(0)
        )
        self._is_night_alerted = False
        self._units = self._store.night_units(self._night.id)
        saved = (
            None
            if self._session is not None
            else self._store.saved_night(self._night.id)
        )
        self._resume_turn = None if saved is None else saved.turns_completed + 1
        self._boxes = {
            unit.sam_object_id: self._default_box(unit) for unit in self._units
        }
        self._pending = None
        self._tracker = self._tracker_factory(
            float(self._area.px_per_cm), self._area.warped_size
        )
        self._is_tracker_dirty = True
        self._poses = {}
        self._uncertain = set()

    def _absent_sam_ids(self) -> set[int]:
        session = self._session
        board = None if session is None else session.board
        if board is None:
            return set()
        absent = {u.id for u in board.units if u.is_absent}
        return {
            u.sam_object_id
            for u in self._units
            if game_id_for(u.sam_object_id) in absent
        }

    def _seed_boxes_from_board(self, session: NightSession) -> None:
        board = session.board
        if board is None:
            return
        ppc = float(self._area.px_per_cm)
        width, height = self._area.warped_size
        by_id = {u.id: u for u in board.units}
        with self._lock:
            for record in self._units:
                unit = by_id.get(game_id_for(record.sam_object_id))
                if unit is None:
                    continue
                xs = [x for x, _ in unit.hull_offsets]
                ys = [y for _, y in unit.hull_offsets]
                x, y = unit.position
                box = PixelBox(
                    round((x + min(xs)) * ppc),
                    round((y + min(ys)) * ppc),
                    round((x + max(xs)) * ppc),
                    round((y + max(ys)) * ppc),
                )
                self._boxes[record.sam_object_id] = clamp_box(box, width, height)
            self._is_tracker_dirty = True

    def _default_box(self, unit: UnitRecord) -> PixelBox:
        ppc = self._area.px_per_cm
        half = DEFAULT_BOX_HALF_CM * ppc
        width, height = self._area.warped_size
        x, y = unit.x_cm * ppc, unit.y_cm * ppc
        box = PixelBox(
            round(x - half), round(y - half), round(x + half), round(y + half)
        )
        return clamp_box(box, width, height)

    def _rerolled(self) -> list[str]:
        if self._night is None:
            return []
        value = self._night.flags.get(REROLLS_FLAG, [])
        return [str(item) for item in value] if isinstance(value, list) else []

    def _unit_view(self, unit: UnitRecord) -> UnitView:
        used = self._rerolled().count(unit.unit_id)
        return UnitView(
            game_id=game_id_for(unit.sam_object_id),
            unit_id=unit.unit_id,
            sam_id=unit.sam_object_id,
            card=unit.card,
            hp_current=unit.hp_current,
            x_cm=unit.x_cm,
            y_cm=unit.y_cm,
            rerolls_left=max(0, REROLLS_PER_UNIT - used),
            sprite_png=self._sprite_b64(unit),
        )

    def log_invalid(self, reason: str) -> None:
        night = self._night
        if night is None:
            return
        session = self._session
        turn, phase = SETUP_TURN, SUMMON_PHASE
        if session is not None and session.board is not None:
            turn = min(session.board.turn, TURNS_PER_NIGHT)
            phase = session.state.value
        self._store.log_turn(night.id, turn, phase, "gm_invalid", {"reason": reason}, 0)

    def _narrate(self, phase: NarrationPhase, events: Sequence[Event]) -> None:
        narration = self._narration
        session = self._session
        night = self._night
        campaign = self._campaign
        if narration is None or session is None or night is None or campaign is None:
            return
        board = session.board
        if board is None:
            return
        names = {game_id_for(u.sam_object_id): u.card.name for u in self._units}
        aliases = {
            name: f"{PLAYER_ALIAS_PREFIX}{i + 1}"
            for i, name in enumerate(session.players)
        }
        kubo = board.kubo
        request = NarrationRequest(
            night=night.number,
            turn=min(board.turn, TURNS_PER_NIGHT),
            phase=phase.value,
            difficulty=campaign.difficulty.value,
            kubo_hp=0 if kubo is None else max(0, kubo.hp),
            kubo_hp_max=0 if kubo is None else kubo.hp_max,
            units=tuple(
                NarrationUnit(
                    u.id,
                    names.get(u.id, u.id),
                    u.unit_class.value,
                    max(0, u.hp),
                    u.hp_max,
                    None if u.owner is None else aliases.get(u.owner),
                )
                for u in board.units
                if not u.is_kubo
            ),
            enemies=tuple(
                NarrationEnemy(e.id, e.type.value, max(0, e.hp))
                for e in board.enemies
                if e.is_alive
            ),
            events=tuple(events),
        )
        players = {alias: name for name, alias in aliases.items()}
        started = self._clock()
        self._write_narration_log(
            request, NARRATION_REQUEST_EVENT, {"phase": request.phase}, 0
        )
        narration.submit(
            request,
            not self._demo_safe.allows_spark,
            lambda sent, reply: self._publish_narration(sent, reply, players, started),
        )

    def _write_narration_log(
        self,
        request: NarrationRequest,
        event: str,
        payload: dict[str, object],
        t_ms: int,
    ) -> None:
        night = self._night
        session = self._session
        if night is None or session is None:
            return
        try:
            self._store.log_turn(
                night.id, request.turn, session.state.value, event, payload, t_ms
            )
        except StoreError:
            logger.warning("narration log write failed")

    def give_consent(self, player_name: str, is_given: bool) -> None:
        session = self._session_or_error()
        if session.state is not TurnState.VOICE_CLAIM:
            raise GameError("cmd.unknown")
        if player_name not in session.players:
            raise GameError("claim.who")
        self._consents[player_name] = is_given

    @property
    def is_recording_agreed(self) -> bool:
        session = self._session
        if session is None or not session.players:
            return False
        return all(self._consents.get(name) is True for name in session.players)

    def _publish_narration(
        self,
        request: NarrationRequest,
        narration: Narration,
        players: Mapping[str, str],
        started: float,
    ) -> None:
        latency_ms = max(0, round((self._clock() - started) * 1000))
        self._write_narration_log(
            request,
            NARRATION_EVENT,
            {
                "source": narration.source.value,
                "phase": request.phase,
                "latency_ms": latency_ms,
            },
            latency_ms,
        )
        if self._broadcast is None:
            return
        narration = restore_player_names(narration, players)
        self._broadcast.publish(
            {
                "type": "narration",
                "night": request.night,
                "turn": request.turn,
                "phase": request.phase,
                "narration_tl": narration.narration_tl,
                "narration_en": narration.narration_en,
                "mood": narration.mood.value,
                "callouts": [
                    {"entity_id": c.entity_id, "text_tl": c.text_tl}
                    for c in narration.callouts
                ],
                "hint_tl": narration.hint_tl,
                "source": narration.source.value,
            }
        )

    async def wait_for_narration(self) -> None:
        if self._narration is not None:
            await self._narration.wait()

    def _stop_narration(self) -> None:
        if self._narration is not None:
            self._narration.cancel()
        self._stop_voice()
        self._stop_recording()

    def _start_recording(self) -> None:
        factory = self._recorder_factory
        night = self._night
        campaign = self._campaign
        if (
            factory is None
            or night is None
            or campaign is None
            or self._recorder is not None
        ):
            return
        width, height = self._area.warped_size
        path = (
            self._store.campaign_dir(campaign.id)
            / RECORDINGS_DIR
            / f"night_{night.number}_{int(self._clock() * 1000)}.mp4"
        )
        recorder = factory(path, width, height, self._store.data_root)
        try:
            recorder.start()
        except RecorderError:
            logger.warning("recording could not start")
            self._notify("rec.unavailable", {})
            return
        self._recorder = recorder
        session = self._session
        self._sidecar = {
            "version": SIDECAR_VERSION,
            "video": path.name,
            "width": width,
            "height": height,
            "fps": RECORDING_FPS,
            "started_t_ms": 0 if session is None else session.t_ms,
            "duration_s": 0.0,
            "anchors": [],
            "sprites": {
                game_id_for(u.sam_object_id): u.sprite_id
                for u in self._units
                if u.sprite_id is not None
            },
        }
        self._sidecar_path = path.with_suffix(".json")
        self._record_anchor_snapshot()
        self._notify("rec.on", {})

    def _stop_recording(self) -> None:
        recorder = self._recorder
        self._recorder = None
        if recorder is None:
            return
        result = recorder.stop()
        if not result.ok:
            logger.warning("recording ended with an error")
        if self._sidecar is not None:
            self._sidecar["duration_s"] = round(result.seconds, 3)
            self._write_sidecar()
            if result.ok:
                self._last_sidecar = self._sidecar_path
        self._sidecar = None
        self._sidecar_path = None

    def _record_anchor_snapshot(self) -> None:
        sidecar = self._sidecar
        session = self._session
        if sidecar is None or session is None:
            return
        anchors = sidecar["anchors"]
        if not isinstance(anchors, list):
            return
        with self._lock:
            boxes = {
                game_id_for(u.sam_object_id): [
                    box.left,
                    box.top,
                    box.right,
                    box.bottom,
                ]
                for u in self._units
                if (box := self._boxes.get(u.sam_object_id)) is not None
            }
        anchors.append({"t_ms": session.t_ms, "boxes": boxes})
        self._write_sidecar()

    def _write_sidecar(self) -> None:
        path = self._sidecar_path
        if path is None or self._sidecar is None:
            return
        temp = path.with_suffix(".json.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp.write_text(json.dumps(self._sidecar), encoding="utf-8")
            temp.replace(path)
        except OSError:
            logger.warning("recording sidecar write failed")

    def request_replay(self, title_tl: str, title_en: str) -> None:
        session = self._session_or_error()
        night = self._night
        sidecar = self._last_sidecar
        runner = self._replay_runner
        if session.state not in (TurnState.SUNRISE, TurnState.DEFEAT) or night is None:
            raise GameError("cmd.unknown")
        if (
            sidecar is None
            or runner is None
            or not self._store.recording_consent(night.id)
        ):
            raise GameError("replay.none")
        if self._replay_status == REPLAY_WORKING:
            raise GameError(BUSY_KEY)
        rows = tuple(
            TurnLogRow(turn, phase, event_type, payload, t_ms)
            for turn, phase, event_type, payload, t_ms in self._store.turn_log_rows(
                night.id
            )
        )
        sprites: dict[str, bytes] = {}
        for unit in self._units:
            if unit.sprite_id is None:
                continue
            try:
                sprites[game_id_for(unit.sam_object_id)] = self._store.sprite_png(
                    unit.sprite_id
                )
            except (StoreError, OSError):
                logger.warning("sprite unavailable for the reel")
        request = ReelRequest(
            sidecar=sidecar,
            rows=rows,
            sprites=sprites,
            out_path=sidecar.with_name(f"reel_{sidecar.stem}.mp4"),
            work_dir=sidecar.with_name(f"work_{sidecar.stem}"),
            root=self._store.data_root,
            ffmpeg=self._ffmpeg,
            title_tl=title_tl,
            title_en=title_en,
            night_number=night.number,
        )
        self._replay_status = REPLAY_WORKING
        self._replay_file = None
        self._notify("replay.making", {})
        is_paid = self._demo_safe.allows_sam_video
        task = asyncio.get_running_loop().create_task(
            self._run_replay(runner, request, is_paid, night.id)
        )
        self._replay_task = task

    async def _run_replay(
        self, runner: ReplayRunner, request: ReelRequest, is_paid: bool, night_id: str
    ) -> None:
        try:
            result = await runner(request, is_paid)
            self._store.set_replay_path(night_id, result.path)
        except (ReplayError, StoreError, OSError, ValueError) as error:
            logger.warning("replay failed with %s", type(error).__name__)
            self._replay_status = REPLAY_FAILED
            self._notify("replay.failed", {})
        else:
            self._replay_status = REPLAY_DONE
            self._replay_file = result.path.name
            self._notify("replay.done", {"file": result.path.name})
        self._push_state()

    async def wait_for_replay(self) -> None:
        task = self._replay_task
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)

    @property
    def is_recording(self) -> bool:
        recorder = self._recorder
        return recorder is not None and recorder.is_recording

    def _start_voice(self) -> None:
        factory = self._voice_factory
        if (
            factory is None
            or self._voice is not None
            or not self._demo_safe.allows_voice
        ):
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        names = [u.card.name for u in self._units]
        owner: list[VoiceSession] = []

        def is_current() -> bool:
            return bool(owner) and self._voice is owner[0]

        def on_caption(caption: Caption) -> None:
            if is_current():
                self._publish_caption(caption)

        def on_final(caption: Caption) -> None:
            if is_current():
                self._on_voice_final(caption)

        def on_overlap() -> None:
            if is_current():
                self._on_voice_overlap()

        def on_status(status: VoiceStatus) -> None:
            if is_current():
                self._on_voice_status(status)

        voice = factory(
            [*VOICE_KEYWORDS, *names], on_caption, on_final, on_overlap, on_status
        )
        owner.append(voice)
        if self._voice_players:
            self._voice_players = {}
            self._notify("voice.reclaim", {})
        voice.set_mode(self._voice_mode)
        self._voice = voice
        self._track_voice_task(loop.create_task(voice.run()))

    def _track_voice_task(self, task: asyncio.Task[None]) -> None:
        self._voice_tasks.add(task)
        task.add_done_callback(self._voice_tasks.discard)

    def _stop_voice(self) -> None:
        voice = self._voice
        self._voice = None
        self._is_ptt_down = False
        if voice is not None:
            voice.stop()
        self._voice_status = VoiceStatus.OFF

    async def wait_for_voice_end_turns(self) -> None:
        if self._voice_turns:
            await asyncio.gather(*self._voice_turns, return_exceptions=True)

    async def wait_for_voice(self) -> None:
        if self._voice_tasks:
            await asyncio.gather(*self._voice_tasks, return_exceptions=True)

    def set_voice_mode(self, mode: VoiceMode) -> None:
        self._voice_mode = mode
        self._is_ptt_down = False
        if self._voice is not None:
            self._voice.set_mode(mode)
            self._voice.set_ptt(False)

    def set_ptt(self, is_down: bool) -> None:
        if self._voice_mode is not VoiceMode.PTT:
            if not is_down:
                return
            raise GameError("cmd.unknown")
        self._is_ptt_down = is_down
        if self._voice is not None:
            self._voice.set_ptt(is_down)

    def retry_voice(self) -> None:
        session = self._session_or_error()
        if session.state not in VOICE_STATES:
            raise GameError("cmd.unknown")
        self._stop_voice()
        self._start_voice()

    def _push_state(self) -> None:
        if self._broadcast is not None:
            self._broadcast.publish({"type": STATE_CHANGED})

    def _publish_caption(self, caption: Caption) -> None:
        if self._broadcast is None:
            return
        self._broadcast.publish(
            {
                "type": "caption",
                "turn_id": caption.turn_id,
                "text": caption.text,
                "is_final": caption.is_final,
                "speaker": self._speaker_name(caption.speaker),
            }
        )

    def _on_voice_status(self, status: VoiceStatus) -> None:
        if self._voice is None:
            return
        if status is VoiceStatus.OFF:
            status = VoiceStatus.DOWN
        self._voice_status = status
        if status is VoiceStatus.DOWN:
            self._notify("net.down", {})
        self._push_state()

    def _on_voice_overlap(self) -> None:
        self._notify("cmd.overlap", {})
        self._push_state()

    def _speaker_name(self, label: str | None) -> str | None:
        if label is None:
            return None
        return self._voice_players.get(label, label)

    def _on_voice_final(self, caption: Caption) -> None:
        session = self._session
        if session is None:
            return
        try:
            if session.state is TurnState.VOICE_CLAIM:
                self._apply_voice_claim(session, caption, is_claim_phase=True)
            elif session.state is TurnState.PLAYER_PHASE:
                context = self._grammar_context(session)
                command = (
                    None if context is None else parse_command(caption.text, context)
                )
                if command is None and self._apply_voice_claim(
                    session, caption, is_claim_phase=False
                ):
                    self._push_state()
                    return
                self._apply_voice_command(
                    session, command, self._speaker_name(caption.speaker)
                )
            else:
                return
        except SessionError as error:
            self._notify(error.copy_key, error.params)
        self._push_state()

    def _apply_voice_claim(
        self, session: NightSession, caption: Caption, is_claim_phase: bool
    ) -> bool:
        units = [
            ClaimUnit(
                game_id_for(u.sam_object_id), u.card.name, u.card.unit_class.value
            )
            for u in self._units
        ]
        command = parse_claim(caption.text, units)
        if command is None:
            return False
        label = caption.speaker
        name = None
        if command.player_name is not None and self._clean_name is not None:
            name = self._clean_name(command.player_name, "") or None
        if name is not None:
            known = {player.casefold(): player for player in session.players}
            name = known.get(name.casefold(), None if not is_claim_phase else name)
        if name is not None and label is not None:
            self._voice_players[label] = name
            session.rename_speaker(label, name)
        player = name or (None if label is None else self._voice_players.get(label))
        if not is_claim_phase:
            return name is not None
        if command.unit_ids and player is None:
            self._notify("claim.who", {})
            return True
        if player is not None and command.unit_ids:
            owned = [g for g in session.owned_by(player) if g not in command.unit_ids]
            session.claim(player, [*owned, *command.unit_ids])
        return True

    def _apply_voice_command(
        self, session: NightSession, command: Command | None, speaker: str | None
    ) -> None:
        if command is None:
            self._notify("cmd.unknown", {})
            return
        if command.kind is CommandKind.END_TURN:
            task = asyncio.get_running_loop().create_task(self._voice_end_turn())
            self._voice_turns.add(task)
            task.add_done_callback(self._voice_turns.discard)
            return
        if command.kind is CommandKind.CANCEL:
            session.cancel_last_voice_chip(speaker)
            self._notify("cmd.cancel", {})
            return
        if command.unit_id is None:
            self._notify("cmd.unknown", {})
            return
        session.add_intent(
            command.unit_id,
            Action(command.kind.value),
            command.target_id,
            VOICE_SOURCE,
            speaker,
        )

    async def _voice_end_turn(self) -> None:
        try:
            await self.end_turn()
        except GameError as error:
            self._notify(error.copy_key, error.params)
        self._push_state()

    def _grammar_context(self, session: NightSession) -> GrammarContext | None:
        board = session.board
        if board is None:
            return None
        names = {game_id_for(u.sam_object_id): u.card.name for u in self._units}
        return GrammarContext(
            units=tuple(
                GrammarUnit(
                    u.id,
                    names.get(u.id, u.id),
                    u.unit_class.value,
                    u.position[0],
                    u.position[1],
                )
                for u in board.units
            ),
            enemies=tuple(
                GrammarEnemy(e.id, e.type.value, e.position[0], e.position[1])
                for e in board.enemies
                if e.is_alive
            ),
        )

    def drain_notices(self) -> list[tuple[str, dict[str, str]]]:
        notices = self._notices
        self._notices = []
        return notices

    def enforce_budget(self) -> None:
        meter = self._meter
        if meter is None:
            return
        if meter.is_stopped and not self._demo_safe.is_on:
            logger.warning("cost hard stop reached, switching to Demo Safe Mode")
            self.set_demo_safe(True)
            self._notices.append(("credits.low", {}))
        night_spend = meter.spent_usd - self._night_spend_start
        if night_spend > NIGHT_COST_ALERT_USD and not self._is_night_alerted:
            logger.warning("night spend passed the alert threshold")
            self._is_night_alerted = True

    def _pipeline(self) -> SummonPipeline:
        self.enforce_budget()
        if self._pipeline_factory is None:
            raise GameError(OFFLINE_KEY, {"feature": SPARK_FEATURE})
        return self._pipeline_factory(not self._demo_safe.allows_spark)

    def wait_for_still_frame(self) -> Image | None:
        camera = self._camera
        calibration = self._calibration
        if camera is None or calibration is None:
            return None
        deadline = self._clock() + HANDS_OFF_WAIT_S + SUMMON_SNAPSHOT_DELAY_S
        previous = self.wait_for_frame()
        while previous is not None and self._clock() < deadline:
            self._sleep(SUMMON_SNAPSHOT_DELAY_S)
            latest = camera.latest()
            if latest is None:
                break
            difference = cv2.absdiff(
                cv2.cvtColor(previous, cv2.COLOR_BGR2GRAY),
                cv2.cvtColor(latest.image, cv2.COLOR_BGR2GRAY),
            )
            previous = latest.image
            if float(difference.mean()) <= STILL_FRAME_MEAN_DIFF_MAX:
                break
        return None if previous is None else warp(previous, calibration)

    def _sync_boxes_from_tracker(self) -> None:
        tracker = self._tracker
        if tracker is None or self._is_tracker_dirty:
            return
        with self._lock:
            self._boxes.update(tracker.boxes())

    def _relock_after_summon(self, snapshot: Image, outcome: SummonOutcome) -> None:
        tracker = self._tracker
        if tracker is None or self._is_tracker_dirty:
            return
        width, height = self._area.warped_size
        with self._lock:
            for sam_id in (*outcome.known_masks, outcome.sam_id):
                box = self._boxes.get(sam_id)
                if box is not None:
                    tracker.relock(sam_id, snapshot, clamp_box(box, width, height))

    def _summon_request(
        self, snapshot: Image, name: str, tap: tuple[int, int] | None
    ) -> SummonRequest:
        if self._campaign is None:
            raise GameError("start.ready")
        self._sync_boxes_from_tracker()
        known = tuple(
            KnownObject(
                sam_id=unit.sam_object_id,
                label=unit.card.name,
                unit_class=unit.card.unit_class,
                box=self._boxes.get(unit.sam_object_id) or self._default_box(unit),
            )
            for unit in self._units
        )
        return SummonRequest(
            snapshot=snapshot,
            spoken_name=name,
            known=known,
            difficulty=self._campaign.difficulty,
            px_per_cm=float(self._area.px_per_cm),
            tap_point=tap,
            prior=self._pending,
        )

    async def summon(self, name: str) -> UnitView:
        self._require_phase(AppPhase.SUMMON)
        self._require_fresh_night()
        if self._summon_lock.locked():
            raise GameError(BUSY_KEY)
        self._pending = None
        self._pending_name = ""
        return await self._run_summon(name, None)

    async def summon_tap(self, point: tuple[int, int]) -> UnitView:
        self._require_phase(AppPhase.SUMMON)
        if self._pending is None:
            raise GameError("cmd.unknown")
        width, height = self._area.warped_size
        if not (0 <= point[0] < width and 0 <= point[1] < height):
            raise GameError("summon.which")
        return await self._run_summon(self._pending_name, point)

    async def _run_summon(self, name: str, tap: tuple[int, int] | None) -> UnitView:
        if self._summon_lock.locked():
            raise GameError(BUSY_KEY)
        async with self._summon_lock:
            started = self._clock()
            snapshot = await asyncio.to_thread(self.wait_for_still_frame)
            if snapshot is None:
                raise GameError("cam.busy")
            pipeline = self._pipeline()
            request = self._summon_request(snapshot, name, tap)
            detection = await pipeline.detect(request)
            try:
                outcome = await pipeline.run(request, detection)
            except SummonError as error:
                if error.copy_key == "summon.which":
                    self._pending = detection
                    self._pending_name = name
                raise GameError(error.copy_key) from error
            unit = self._persist(outcome, started)
            self._relock_after_summon(snapshot, outcome)
            self._remember_crop(unit, snapshot, outcome)
            self._schedule_sprite(unit)
            return self._unit_view(unit)

    def _persist(self, outcome: SummonOutcome, started: float) -> UnitRecord:
        night = self._night
        if night is None:
            raise GameError("start.ready")
        card = CardFields(
            name=outcome.name,
            unit_class=outcome.card.unit_class,
            hp_max=outcome.card.hp_max,
            atk=outcome.card.atk,
            move_class=outcome.card.move,
            range_class=outcome.card.range,
            power_id=outcome.card.power_id,
            power_name_tl=outcome.text.power_name_tl,
            card_text_tl=outcome.text.card_text_tl,
            card_text_en=outcome.text.card_text_en,
        )
        signature = outcome.signature.signature
        unit = self._store.add_unit(
            night,
            card,
            SignatureFields(
                label=signature.label,
                histogram=signature.histogram,
                area_cm2=signature.area_cm2,
                aspect=signature.aspect,
                ref_crop_png=outcome.signature.ref_crop_png,
            ),
            UnitPlacement(
                sam_object_id=outcome.sam_id, x_cm=outcome.x_cm, y_cm=outcome.y_cm
            ),
        )
        width, height = self._area.warped_size
        for sam_id, mask in outcome.known_masks.items():
            self._boxes[sam_id] = clamp_box(mask.bounds, width, height)
        self._boxes[outcome.sam_id] = clamp_box(outcome.mask.bounds, width, height)
        self._units.append(unit)
        self._pending = None
        elapsed_ms = max(0, round((self._clock() - started) * 1000))
        self._store.log_turn(
            night.id,
            SETUP_TURN,
            SUMMON_PHASE,
            "summon",
            {
                "unit": game_id_for(outcome.sam_id),
                "class": card.unit_class.value,
                "source": outcome.source,
            },
            elapsed_ms,
        )
        return unit

    def _find_unit(self, unit_id: str) -> UnitRecord:
        for unit in self._units:
            if unit.unit_id == unit_id:
                return unit
        raise GameError("cmd.unknown")

    def rename_unit(
        self, unit_id: str, name: str, clean: Callable[[str, str], str]
    ) -> UnitView:
        self._require_phase(AppPhase.SUMMON)
        night = self._night
        if night is None:
            raise GameError("start.ready")
        unit = self._find_unit(unit_id)
        new_name = clean(name, unit.card.unit_class.value.title())
        card = replace(unit.card, name=new_name)
        return self._replace_card(night, unit, card)

    def _require_fresh_night(self) -> None:
        if self._resume_turn is not None:
            raise GameError("restore")

    async def reroll_unit(self, unit_id: str) -> UnitView:
        self._require_phase(AppPhase.SUMMON)
        self._require_fresh_night()
        if self._summon_lock.locked():
            raise GameError(BUSY_KEY)
        async with self._summon_lock:
            return await self._reroll(unit_id)

    async def _reroll(self, unit_id: str) -> UnitView:
        night = self._night
        if night is None or self._campaign is None:
            raise GameError("start.ready")
        unit = self._find_unit(unit_id)
        if self._unit_view(unit).rerolls_left <= 0:
            raise GameError("cmd.unknown")
        flags = dict(night.flags)
        flags[REROLLS_FLAG] = [*self._rerolled(), unit.unit_id]
        self._store.set_night_flags(night.id, flags)
        night = NightRecord(
            night.id, night.campaign_id, night.number, night.started_at, flags
        )
        self._night = night
        snapshot = await asyncio.to_thread(self.wait_for_frame)
        calibration = self._calibration
        if snapshot is None or calibration is None:
            raise GameError("cam.busy")
        pipeline = self._pipeline()
        others = [u for u in self._units if u.unit_id != unit.unit_id]
        request = self._summon_request(
            warp(snapshot, calibration), unit.card.name, None
        )
        request = SummonRequest(
            snapshot=request.snapshot,
            spoken_name=unit.card.name,
            known=tuple(k for k in request.known if k.sam_id != unit.sam_object_id),
            difficulty=request.difficulty,
            px_per_cm=request.px_per_cm,
        )
        detection = await pipeline.detect(request)
        if detection.draft is None or detection.source != "spark":
            raise GameError(OFFLINE_KEY, {"feature": SPARK_FEATURE})
        roster: list[UnitClass] = (
            [u.card.unit_class for u in others]
            if unit.sam_object_id != KUBO_SAM_ID
            else []
        )
        clamped = clamp_card(detection.draft, roster, self._campaign.difficulty)
        card = CardFields(
            name=unit.card.name,
            unit_class=clamped.unit_class,
            hp_max=clamped.hp_max,
            atk=clamped.atk,
            move_class=clamped.move,
            range_class=clamped.range,
            power_id=clamped.power_id,
            power_name_tl=detection.text.power_name_tl,
            card_text_tl=detection.text.card_text_tl,
            card_text_en=detection.text.card_text_en,
        )
        return self._replace_card(night, unit, card)

    def _sprite_b64(self, unit: UnitRecord) -> str | None:
        if unit.unit_id in self._sprites:
            return self._sprites[unit.unit_id]
        if unit.sprite_id is None:
            return None
        try:
            png = self._store.sprite_png(unit.sprite_id)
        except (OSError, ValueError, StoreError):
            logger.warning("stored sprite could not be read")
            return None
        encoded = base64.b64encode(png).decode("ascii")
        self._sprites[unit.unit_id] = encoded
        return encoded

    def _remember_crop(
        self, unit: UnitRecord, snapshot: Image, outcome: SummonOutcome
    ) -> None:
        try:
            self._crops[unit.unit_id] = prepare_crop(snapshot, outcome.mask)
        except SpriteError:
            logger.warning("sprite crop could not be prepared")
            return
        self._subjects[unit.unit_id] = (
            outcome.text.sprite_subject_en or FALLBACK_SUBJECT
        )

    def _schedule_sprite(self, unit: UnitRecord) -> None:
        crop = self._crops.get(unit.unit_id)
        night = self._night
        if crop is None or night is None or self._sprite_service_factory is None:
            return
        job = SpriteJob(
            unit_id=unit.unit_id,
            campaign_id=night.campaign_id,
            signature_id=unit.signature_id,
            unit_name=unit.card.name,
            unit_class=unit.card.unit_class.value,
            subject=self._subjects.get(unit.unit_id, unit.card.name),
            crop_rgb=crop,
        )
        version = self._sprite_versions.get(unit.unit_id, 0) + 1
        self._sprite_versions[unit.unit_id] = version
        previous = self._sprite_jobs.get(unit.unit_id)
        if previous is not None:
            previous.cancel()
        task = asyncio.get_running_loop().create_task(self._make_sprite(job, version))
        self._sprite_jobs[unit.unit_id] = task
        self._sprite_tasks.add(task)
        task.add_done_callback(self._sprite_tasks.discard)

    async def _make_sprite(self, job: SpriteJob, version: int) -> None:
        factory = self._sprite_service_factory
        if factory is None:
            return
        self.enforce_budget()
        service = factory(not self._demo_safe.allows_image)
        try:
            sprite_id = await service.ensure_sprite(job)
            if sprite_id is None:
                return
            encoded = base64.b64encode(self._store.sprite_png(sprite_id)).decode(
                "ascii"
            )
        except (StoreError, OSError, SpriteError) as error:
            logger.warning(
                "sprite job failed with %s, keeping the placeholder",
                type(error).__name__,
            )
            return
        if self._sprite_versions.get(job.unit_id) != version:
            return
        try:
            self._store.set_unit_sprite(job.unit_id, sprite_id)
        except StoreError:
            logger.exception("sprite could not be linked to its unit")
            return
        self._sprites[job.unit_id] = encoded
        self._units = [
            replace(u, sprite_id=sprite_id) if u.unit_id == job.unit_id else u
            for u in self._units
        ]
        if self._broadcast is not None:
            self._broadcast.publish(
                {"type": "sprite", "unit_id": job.unit_id, "sprite_png": encoded}
            )

    async def wait_for_sprites(self) -> None:
        if self._sprite_tasks:
            await asyncio.gather(*self._sprite_tasks, return_exceptions=True)

    def _replace_card(
        self, night: NightRecord, unit: UnitRecord, card: CardFields
    ) -> UnitView:
        self._store.update_unit_card(night.id, unit.unit_id, card)
        updated = UnitRecord(
            unit_id=unit.unit_id,
            signature_id=unit.signature_id,
            sam_object_id=unit.sam_object_id,
            card=card,
            hp_current=card.hp_max,
            x_cm=unit.x_cm,
            y_cm=unit.y_cm,
            sprite_id=unit.sprite_id,
        )
        self._units = [updated if u.unit_id == unit.unit_id else u for u in self._units]
        if card.unit_class is not unit.card.unit_class:
            self._sprites.pop(unit.unit_id, None)
            self._schedule_sprite(updated)
        return self._unit_view(updated)

    def set_demo_safe(self, is_on: bool) -> None:
        with self._lock:
            self._demo_safe = self._demo_safe.with_on(is_on)
            self._demo_safe.save(self._store)
        if is_on:
            self._stop_narration()
        elif self._session is not None and self._session.state in ACTIVE_NIGHT_STATES:
            self._start_voice()

    def set_demo_safe_sam(self, is_on: bool) -> None:
        with self._lock:
            self._demo_safe = self._demo_safe.with_sam_reanchor(is_on)
            self._demo_safe.save(self._store)

    def _require_phase(self, phase: AppPhase) -> None:
        if self._phase() is not phase:
            raise GameError("cmd.unknown")

    def render_frame(self, sequence: int) -> EncodedFrame | None:
        with self._lock:
            camera = self._camera
            calibration = self._calibration
        if camera is None:
            return None
        frame = camera.latest()
        if frame is None:
            return None
        if calibration is None:
            jpg, width, height = encode_jpeg(frame.image)
            return EncodedFrame(sequence, FrameView.RAW, width, height, jpg)
        warped = warp(frame.image, calibration)
        recorder = self._recorder
        if recorder is not None:
            recorder.write(warped)
        poses = self.track(warped)
        jpg, width, height = encode_jpeg(warped)
        return EncodedFrame(sequence, FrameView.WARPED, width, height, jpg, poses)

    def track(self, warped: Image) -> tuple[Pose, ...]:
        with self._lock:
            tracker = self._tracker
            if tracker is None or not self._is_calibrated or not self._boxes:
                return ()
            if self._is_tracker_dirty:
                tracker.reset(warped, dict(self._boxes))
                self._is_tracker_dirty = False
                return self._pose_list()
            for pose in tracker.update(warped):
                self._poses[pose.sam_id] = pose
            return self._pose_list()

    def _pose_list(self) -> tuple[Pose, ...]:
        poses: list[Pose] = []
        for unit in self._units:
            sam_id = unit.sam_object_id
            tracked = self._poses.get(sam_id)
            x_cm, y_cm = (
                (tracked.x_cm, tracked.y_cm) if tracked else (unit.x_cm, unit.y_cm)
            )
            is_frozen = tracked.is_frozen if tracked else False
            poses.append(
                Pose(
                    game_id_for(sam_id),
                    x_cm,
                    y_cm,
                    is_frozen or sam_id in self._uncertain,
                )
            )
        return tuple(poses)

    def _segmenter(self, is_allowed: bool) -> Segmenter | None:
        self.enforce_budget()
        if self._segmenter_factory is None:
            return None
        if not is_allowed:
            return None
        segmenter = self._segmenter_factory(False)
        return segmenter if segmenter.is_available else None

    async def recover_lost_objects(self) -> int:
        tracker = self._tracker
        calibration = self._calibration
        if tracker is None or calibration is None or not self._is_calibrated:
            return 0
        absent = self._absent_sam_ids()
        candidates = [c for c in tracker.recovery_candidates() if c not in absent]
        if not candidates:
            return 0
        segmenter = self._segmenter(self._demo_safe.allows_sam_recovery)
        frame = await asyncio.to_thread(self.wait_for_frame)
        if segmenter is None or frame is None:
            return 0
        warped = warp(frame, calibration)
        width, height = self._area.warped_size
        boxes = tracker.boxes()
        recovered = 0
        for sam_id in candidates:
            box = boxes.get(sam_id)
            if box is None:
                continue
            tracker.mark_recovery_used(sam_id)
            prompt = ObjectPrompt(
                sam_id, pad_box(box, REANCHOR_BOX_PADDING, width, height)
            )
            try:
                result = await segmenter.segment(warped, [prompt])
            except (SegmentationError, MetaError):
                logger.warning("between-turn recovery failed")
                return recovered
            mask = result.get(sam_id)
            if mask is None or (mask.confidence or 0.0) < SAM_ACCEPT_CONFIDENCE:
                continue
            box = clamp_box(mask.bounds, width, height)
            with self._lock:
                tracker.relock(sam_id, warped, box)
                self._boxes[sam_id] = box
                self._uncertain.discard(sam_id)
            recovered += 1
        return recovered

    async def reanchor_all(self, still: Image | None = None) -> dict[int, Anchor]:
        night = self._night
        calibration = self._calibration
        tracker = self._tracker
        if night is None or calibration is None or tracker is None:
            raise GameError("cmd.unknown")
        frame = (
            still
            if still is not None
            else await asyncio.to_thread(self.wait_for_still_frame)
        )
        if frame is None:
            raise GameError("cam.busy")
        signatures = self._store.unit_signatures(night.id)
        tracker.new_turn()
        tracked = tracker.boxes()
        absent = self._absent_sam_ids()
        targets = [
            ReanchorTarget(
                sam_id=unit.sam_object_id,
                tracker_box=tracked.get(unit.sam_object_id)
                or self._boxes.get(unit.sam_object_id)
                or self._default_box(unit),
                label=signatures.get(unit.unit_id, (unit.card.name, ()))[0],
                histogram=signatures.get(unit.unit_id, ("", ()))[1],
            )
            for unit in self._units
            if unit.sam_object_id not in absent
        ]
        segmenter = self._segmenter(self._demo_safe.allows_sam_reanchor)
        anchors = await reanchor(
            segmenter or TrackerOnlySegmenter(),
            frame,
            targets,
            float(self._area.px_per_cm),
            safe_histogram,
            safe_distance,
        )
        self._apply_anchors(night, frame, anchors)
        self._record_anchor_snapshot()
        return anchors

    def _apply_anchors(
        self, night: NightRecord, frame: Image, anchors: dict[int, Anchor]
    ) -> None:
        width, height = self._area.warped_size
        positions: dict[str, tuple[float, float]] = {}
        with self._lock:
            for unit in self._units:
                anchor = anchors.get(unit.sam_object_id)
                if anchor is None:
                    continue
                positions[unit.unit_id] = (anchor.x_cm, anchor.y_cm)
                box = clamp_box(anchor.box, width, height)
                self._boxes[unit.sam_object_id] = box
                if anchor.is_uncertain:
                    self._uncertain.add(unit.sam_object_id)
                    continue
                self._uncertain.discard(unit.sam_object_id)
                if self._tracker is not None:
                    self._tracker.relock(unit.sam_object_id, frame, box)
            self._units = [
                replace(u, x_cm=positions[u.unit_id][0], y_cm=positions[u.unit_id][1])
                if u.unit_id in positions
                else u
                for u in self._units
            ]
        self._store.update_positions(night.id, positions)

    def _close_camera(self) -> None:
        if self._camera is not None:
            self._camera.stop()
        self._camera = None
        self._camera_info = None
        self._live.clear()

    def close(self) -> None:
        for task in list(self._sprite_tasks):
            task.cancel()
        self._stop_narration()
        with self._lock:
            self._close_camera()


class FramePump:
    def __init__(
        self,
        controller: GameController,
        live: LiveState,
        fps: int = STREAM_FPS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._controller = controller
        self._live = live
        self._interval = 1.0 / fps
        self._clock = clock
        self._sleep = sleep
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="frame-pump", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def pump_once(self, sequence: int) -> bool:
        try:
            frame = self._controller.render_frame(sequence)
        except GameError:
            logger.warning("frame encode failed")
            return False
        if frame is None:
            return False
        self._live.publish(frame)
        return True

    def _loop(self) -> None:
        sequence = 0
        while not self._stop.is_set():
            started = self._clock()
            if self.pump_once(sequence + 1):
                sequence += 1
            self._sleep(max(0.0, self._interval - (self._clock() - started)))


MAX_PLAYERS: Final = 4
PLAYER_COLORS: Final = ("#F2C14E", "#3E7D4F", "#6B2D5C", "#C99A6B")
TRANSITION_EVENT: Final = "transition"
DOWN_STATUS: Final = "down"
STUNNED_STATUS: Final = "stunned"
REFORM_STATUS_PREFIX: Final = "reform_"
STATE_CHANGED: Final = "state.changed"
RECORDINGS_DIR: Final = "recordings"
REPLAY_IDLE: Final = "idle"
REPLAY_WORKING: Final = "working"
REPLAY_DONE: Final = "done"
REPLAY_FAILED: Final = "failed"
RECORDING_FPS: Final = 25
SIDECAR_VERSION: Final = 1
NARRATION_EVENT: Final = "narration"
NARRATION_REQUEST_EVENT: Final = "narration_request"
PUSH_EFFECT: Final = "push"
STEAL_EFFECT: Final = "steal"
EFFECT_NOTICES: Final[Mapping[EventType, str]] = {
    EventType.PUSH: "tik.push",
    EventType.THROWN: "tik.thrown",
    EventType.STEAL: "duw.steal",
    EventType.RETURN: "duw.back",
    EventType.ESCAPE: "duw.escape",
}
VOICE_KEYWORDS: Final = (
    "tapos na",
    "hindi",
    "wag",
    "atake",
    "banatan",
    "tira",
    "gamutin",
    "gamot",
    "pagalingin",
    "protektahan",
    "kubo",
    "anting-anting",
    "albularyo",
    "aswang",
    "tikbalang",
    "kapre",
    "manananggal",
    "duwende",
)
PLAYER_ALIAS_PREFIX: Final = "P"
PLAYER_ALIAS_PATTERN: Final = re.compile(r"\bP[1-4]\b")
ACTIVE_NIGHT_STATES: Final = frozenset(
    state
    for state in TurnState
    if state
    not in (TurnState.SUMMON, TurnState.PAUSED, TurnState.SUNRISE, TurnState.DEFEAT)
)
VOICE_STATES: Final = ACTIVE_NIGHT_STATES | {TurnState.PAUSED}
MIN_HULL_POINTS: Final = 3
RESTORE_EVENT: Final = "restore"


class SessionError(Exception):
    def __init__(self, copy_key: str, params: dict[str, str] | None = None) -> None:
        super().__init__(copy_key)
        self.copy_key = copy_key
        self.params: dict[str, str] = params or {}


@dataclass(frozen=True)
class Chip:
    chip_id: str
    intent: Intent
    source: str = TAP_SOURCE
    speaker: str | None = None


@dataclass(frozen=True)
class PhysicalEffect:
    kind: str
    unit_id: str
    x_cm: float
    y_cm: float


@dataclass(frozen=True)
class TurnResult:
    events: tuple[Event, ...]
    telegraph: tuple[Event, ...]
    is_blocked: bool
    effects: tuple[PhysicalEffect, ...] = ()


@dataclass(frozen=True)
class FinalScore:
    units_alive: int
    kubo_hp: int
    enemies_defeated: int
    score: int
    bayani: tuple[str, ...]


Notify = Callable[[str, dict[str, str]], None]
Clock = Callable[[], float]


def hull_offsets_from_box(half_w_cm: float, half_h_cm: float) -> Hull:
    return (
        (-half_w_cm, -half_h_cm),
        (half_w_cm, -half_h_cm),
        (half_w_cm, half_h_cm),
        (-half_w_cm, half_h_cm),
    )


class NightSession:
    def __init__(
        self,
        store: Store,
        night: NightRecord,
        units: Sequence[UnitRecord],
        game_ids: Mapping[str, str],
        difficulty: Difficulty,
        play_size_cm: tuple[float, float],
        notify: Notify,
        clock: Clock,
    ) -> None:
        self._store = store
        self._night = night
        self._records = {record.unit_id: record for record in units}
        self._game_ids = dict(game_ids)
        self._unit_ids = {game_id: unit_id for unit_id, game_id in game_ids.items()}
        self._difficulty = difficulty
        self._play_size = play_size_cm
        self._notify = notify
        self._clock = clock
        self._started = clock()
        self._pending_log: list[tuple[int, str, str, dict[str, object], int]] = []
        self._machine = TurnStateMachine(
            TurnState.SUMMON, on_transition=self._log_transition
        )
        self._owners: dict[str, str] = {}
        self._players: list[str] = []
        self._chips: list[Chip] = []
        self._illegal: tuple[str, ...] = ()
        self._board: BoardState | None = None
        self._final: FinalScore | None = None
        self._effects: tuple[PhysicalEffect, ...] = ()

    @property
    def state(self) -> TurnState:
        return self._machine.state

    @property
    def board(self) -> BoardState | None:
        return self._board

    @property
    def players(self) -> tuple[str, ...]:
        return tuple(self._players)

    @property
    def chips(self) -> tuple[Chip, ...]:
        return tuple(self._chips)

    @property
    def illegal_units(self) -> tuple[str, ...]:
        return self._illegal

    @property
    def final_score(self) -> FinalScore | None:
        return self._final

    def rename_speaker(self, label: str, name: str) -> None:
        self._chips = [
            replace(c, speaker=name)
            if c.source == VOICE_SOURCE and c.speaker == label
            else c
            for c in self._chips
        ]

    def owned_by(self, player_name: str) -> list[str]:
        return [
            game_id for game_id, owner in self._owners.items() if owner == player_name
        ]

    def owner_of(self, game_id: str) -> str | None:
        return self._owners.get(game_id)

    def _t_ms(self) -> int:
        return max(0, round((self._clock() - self._started) * 1000))

    @property
    def t_ms(self) -> int:
        return self._t_ms()

    def _turn(self) -> int:
        return 0 if self._board is None else self._board.turn

    def _log_transition(self, change: Transition) -> None:
        payload: dict[str, object] = {
            "from": change.source.value,
            "event": change.event.value,
        }
        self._pending_log.append(
            (
                min(self._turn(), TURNS_PER_NIGHT),
                change.target.value,
                TRANSITION_EVENT,
                payload,
                self._t_ms(),
            )
        )

    def _require(self, state: TurnState) -> None:
        if self._machine.state is not state:
            raise SessionError("cmd.unknown")

    def begin(self) -> None:
        self._require(TurnState.SUMMON)
        self._machine.transition(TurnEvent.BEGIN_NIGHT)
        self._flush_log()

    def claim(self, player_name: str, game_ids: Sequence[str]) -> None:
        self._require(TurnState.VOICE_CLAIM)
        if player_name not in self._players and len(self._players) >= MAX_PLAYERS:
            raise SessionError("cmd.unknown")
        unit_ids = [self._unit_ids.get(game_id) for game_id in game_ids]
        if any(unit_id is None for unit_id in unit_ids):
            raise SessionError("cmd.unknown")
        if player_name not in self._players and not game_ids:
            raise SessionError("claim.who")
        if player_name not in self._players:
            self._players.append(player_name)
        color = PLAYER_COLORS[self._players.index(player_name)]
        player_id = self._store.find_or_add_player(
            self._night.campaign_id, player_name, color
        )
        for game_id, owner in list(self._owners.items()):
            if owner == player_name and game_id not in game_ids:
                self._owners.pop(game_id)
                self._store.set_unit_owner(self._unit_ids[game_id], None)
        for game_id, unit_id in zip(game_ids, unit_ids, strict=True):
            if unit_id is None:
                continue
            self._owners[game_id] = player_name
            self._store.set_unit_owner(unit_id, player_id)
        self._players = [
            name for name in self._players if name in self._owners.values()
        ]

    def finish_claims(
        self, positions: Mapping[str, Point], sizes: Mapping[str, tuple[float, float]]
    ) -> TurnResult:
        self._require(TurnState.VOICE_CLAIM)
        self._machine.transition(TurnEvent.CLAIMS_DONE)
        units = [
            self._unit_state(record, positions, sizes)
            for record in self._records.values()
        ]
        units.sort(
            key=lambda unit: self._records[self._unit_ids[unit.id]].sam_object_id
        )
        flags = frozenset(str(k) for k, v in self._night.flags.items() if v is True)
        self._board = start_night(
            units,
            self._difficulty,
            max(1, len(self._players)),
            self._play_size[0],
            self._play_size[1],
            flags,
        )
        telegraph = self._next_turn()
        self._flush_log()
        return TurnResult(events=(), telegraph=telegraph, is_blocked=False)

    def restore(
        self,
        saved: SavedNight,
        positions: Mapping[str, Point],
        sizes: Mapping[str, tuple[float, float]],
        owners: Mapping[str, str],
    ) -> TurnResult:
        self._require(TurnState.SUMMON)
        self._owners = {g: name for g, name in owners.items() if g in self._unit_ids}
        meta = saved.board
        saved_names = meta.get("player_names", [])
        order = [str(n) for n in saved_names] if isinstance(saved_names, list) else []
        owning = set(self._owners.values())
        named = [name for name in order if name in owning]
        named += sorted(owning - set(named))
        self._players = named[:MAX_PLAYERS]
        flags = frozenset(str(k) for k, v in self._night.flags.items() if v is True)
        try:
            hulls = _meta_hulls(meta)
            units = []
            for record in self._records.values():
                save = saved.units.get(record.unit_id)
                cooldown = 0 if save is None else save.cooldown
                unit = self._unit_state(record, positions, sizes, cooldown)
                if save is not None:
                    unit = apply_unit_tags(unit, save.status)
                    if unit.is_absent:
                        unit = replace(unit, position=(save.x_cm, save.y_cm))
                units.append(
                    replace(unit, hull_offsets=hulls.get(unit.id, unit.hull_offsets))
                )
            units.sort(
                key=lambda unit: self._records[self._unit_ids[unit.id]].sam_object_id
            )
            self._board = BoardState(
                turn=saved.turns_completed,
                difficulty=self._difficulty,
                players=_meta_int(meta, "players", max(1, len(self._players))),
                play_w_cm=self._play_size[0],
                play_h_cm=self._play_size[1],
                units=tuple(units),
                enemies=tuple(
                    _enemy_from_save(e, self._difficulty) for e in saved.enemies
                ),
                flags=flags,
                enemies_defeated=_meta_int(meta, "enemies_defeated", 0),
                enemy_counter=_meta_counts(meta, "enemy_counter"),
                damage_by_owner=_meta_counts(meta, "damage_by_owner"),
            )
        except (ValueError, TypeError) as error:
            raise SessionError("restore") from error
        self._machine.force(TurnState.CHECK_END)
        self._pending_log.append(
            (
                saved.turns_completed,
                TurnState.CHECK_END.value,
                RESTORE_EVENT,
                {"turns_completed": saved.turns_completed},
                self._t_ms(),
            )
        )
        telegraph = self._next_turn_and_flush()
        return TurnResult(events=(), telegraph=telegraph, is_blocked=False)

    def _unit_state(
        self,
        record: UnitRecord,
        positions: Mapping[str, Point],
        sizes: Mapping[str, tuple[float, float]],
        cooldown: int = 0,
    ) -> UnitState:
        game_id = self._game_ids[record.unit_id]
        half_w, half_h = sizes.get(game_id, (2.0, 2.0))
        card = record.card
        return UnitState(
            id=game_id,
            unit_class=card.unit_class,
            hp=record.hp_current,
            hp_max=card.hp_max,
            atk=card.atk,
            move=card.move_class,
            range=card.range_class,
            power_id=card.power_id,
            cooldown=cooldown,
            position=positions.get(game_id, (record.x_cm, record.y_cm)),
            start=positions.get(game_id, (record.x_cm, record.y_cm)),
            hull_offsets=hull_offsets_from_box(half_w, half_h),
            owner=self._owners.get(game_id),
        )

    def _next_turn(self) -> tuple[Event, ...]:
        board = self._board
        if board is None:
            return ()
        self._board, events = begin_turn(board)
        if check_outcome(self._board) is Outcome.LOSE:
            self._announce(events)
            self._machine.force(TurnState.CHECK_END)
            self._conclude(Outcome.LOSE)
            return events
        self._machine.transition(TurnEvent.TELEGRAPHED)
        self._chips = []
        self._illegal = ()
        self._announce(events)
        return events

    def add_intent(
        self,
        game_id: str,
        action: Action,
        target_id: str | None,
        source: str = TAP_SOURCE,
        speaker: str | None = None,
    ) -> Chip:
        self._require(TurnState.PLAYER_PHASE)
        board = self._board
        if board is None:
            raise SessionError("cmd.unknown")
        intent = Intent(unit_id=game_id, action=action, target_id=target_id)
        error = intent_error(board, intent)
        if error is not None:
            raise SessionError(error, {"unit": self._name_of(game_id)})
        chip = Chip(
            chip_id=str(uuid.uuid4()), intent=intent, source=source, speaker=speaker
        )
        self._chips = [c for c in self._chips if c.intent.unit_id != game_id] + [chip]
        return chip

    def cancel_last_voice_chip(self, speaker: str | None) -> Chip:
        self._require(TurnState.PLAYER_PHASE)
        for chip in reversed(self._chips):
            if chip.source == VOICE_SOURCE and (
                speaker is None or chip.speaker == speaker
            ):
                self._chips = [c for c in self._chips if c.chip_id != chip.chip_id]
                return chip
        raise SessionError("cmd.unknown")

    def cancel_chip(self, chip_id: str) -> None:
        self._require(TurnState.PLAYER_PHASE)
        remaining = [c for c in self._chips if c.chip_id != chip_id]
        if len(remaining) == len(self._chips):
            raise SessionError("cmd.unknown")
        self._chips = remaining

    def start_end_turn(self) -> None:
        self._require(TurnState.PLAYER_PHASE)
        self._machine.transition(TurnEvent.END_TURN)

    def pause(self) -> None:
        self._require(TurnState.PLAYER_PHASE)
        self._machine.transition(TurnEvent.PAUSE)
        self._flush_log()

    def resume(self) -> None:
        self._require(TurnState.PAUSED)
        self._machine.transition(TurnEvent.RESUME)
        self._flush_log()

    def cancel_end_turn(self) -> None:
        self._require(TurnState.END_TURN_SNAPSHOT)
        self._machine.force(TurnState.PLAYER_PHASE)
        if (
            self._pending_log
            and self._pending_log[-1][1] == TurnState.END_TURN_SNAPSHOT.value
        ):
            self._pending_log.pop()

    def finish_end_turn(
        self, positions: Mapping[str, Point], hulls: Mapping[str, Hull] | None = None
    ) -> TurnResult:
        self._require(TurnState.END_TURN_SNAPSHOT)
        board = self._board
        if board is None:
            raise SessionError("cmd.unknown")
        board = with_positions(board, positions, hulls)
        self._board = board
        self._machine.transition(TurnEvent.SNAPSHOT_DONE)
        if moved_kubo(board):
            self._notify("kubo.moved", {})
        illegal = illegal_moves(board)
        if illegal:
            self._illegal = illegal
            self._machine.transition(TurnEvent.MOVES_ILLEGAL)
            self._notify("endturn.blocked", {})
            self._flush_log()
            return TurnResult(events=(), telegraph=(), is_blocked=True)
        self._illegal = ()
        self._machine.transition(TurnEvent.MOVES_LEGAL)
        resolved, events = resolve_turn(board, [chip.intent for chip in self._chips])
        self._board = resolved
        self._machine.transition(TurnEvent.PLAYER_RESOLVED)
        self._machine.transition(TurnEvent.ENEMY_RESOLVED)
        self._announce(events)
        for event in events:
            self._pending_log.append(
                (
                    resolved.turn,
                    TurnState.PHYSICAL_EFFECTS.value,
                    event.type.value,
                    _event_payload(event),
                    self._t_ms(),
                )
            )
        effects = self._physical_effects(resolved, events)
        if effects:
            self._effects = effects
            return TurnResult(
                events=events, telegraph=(), is_blocked=False, effects=effects
            )
        self._machine.transition(TurnEvent.EFFECTS_DONE)
        telegraph = self._conclude(check_outcome(resolved))
        return TurnResult(events=events, telegraph=telegraph, is_blocked=False)

    @property
    def effects(self) -> tuple[PhysicalEffect, ...]:
        return self._effects

    def _physical_effects(
        self, board: BoardState, events: Sequence[Event]
    ) -> tuple[PhysicalEffect, ...]:
        units = {u.id: u for u in board.units}
        effects: dict[str, PhysicalEffect] = {}
        for event in events:
            unit = units.get(event.dst or "")
            if unit is None:
                continue
            current = effects.get(unit.id)
            if event.type is EventType.PUSH and event.pos is not None:
                if current is not None and current.kind == STEAL_EFFECT:
                    continue
                effects[unit.id] = PhysicalEffect(
                    PUSH_EFFECT, unit.id, event.pos[0], event.pos[1]
                )
            elif event.type is EventType.STEAL:
                effects[unit.id] = PhysicalEffect(
                    STEAL_EFFECT, unit.id, unit.position[0], unit.position[1]
                )
        return tuple(effects.values())

    def finish_effects(self, positions: Mapping[str, Point]) -> TurnResult:
        self._require(TurnState.PHYSICAL_EFFECTS)
        board = self._board
        if board is None:
            raise SessionError("cmd.unknown")
        pushed = {e.unit_id for e in self._effects if e.kind == PUSH_EFFECT}
        units = tuple(
            replace(u, position=positions[u.id])
            if u.id in pushed and u.id in positions
            else u
            for u in board.units
        )
        self._board = replace(board, units=units)
        self._effects = ()
        self._machine.transition(TurnEvent.EFFECTS_DONE)
        telegraph = self._conclude(check_outcome(self._board))
        return TurnResult(events=(), telegraph=telegraph, is_blocked=False)

    def _conclude(self, outcome: Outcome) -> tuple[Event, ...]:
        board = self._board
        if board is None:
            return ()
        if outcome is Outcome.CONTINUE:
            self._autosave(None)
            return self._next_turn_and_flush()
        result = "win" if outcome is Outcome.WIN else "lose"
        self._machine.transition(
            TurnEvent.SURVIVED if outcome is Outcome.WIN else TurnEvent.FELL
        )
        self._final = self._score(board)
        self._notify("win" if outcome is Outcome.WIN else "lose", {})
        self._autosave(result)
        return ()

    def _next_turn_and_flush(self) -> tuple[Event, ...]:
        self._machine.transition(TurnEvent.NEXT_TURN)
        telegraph = self._next_turn()
        self._flush_log()
        return telegraph

    def _score(self, board: BoardState) -> FinalScore:
        kubo = board.kubo
        return FinalScore(
            units_alive=sum(
                1
                for u in board.units
                if not u.is_kubo and not u.is_down and not u.is_absent
            ),
            kubo_hp=0 if kubo is None else max(0, kubo.hp),
            enemies_defeated=board.enemies_defeated,
            score=score(board),
            bayani=bayani(board),
        )

    def _autosave(self, result: str | None) -> None:
        board = self._board
        if board is None:
            return
        units = [
            UnitSave(
                unit_id=self._unit_ids[u.id],
                hp_current=max(0, u.hp),
                x_cm=u.position[0],
                y_cm=u.position[1],
                cooldown=u.cooldown,
                status=((DOWN_STATUS,) if u.is_down else ()) + unit_status_tags(u),
            )
            for u in board.units
        ]
        enemies = [_enemy_save(e) for e in board.enemies]
        try:
            self._store.autosave(
                self._night.id,
                min(board.turn, TURNS_PER_NIGHT),
                units,
                enemies,
                result,
                self._pending_log,
                _board_meta(board, self._players),
            )
        except (StoreError, OSError):
            logger.exception("autosave failed and rolled back, play continues")
            self._notify("restore", {})
        self._pending_log = []

    def _flush_log(self) -> None:
        try:
            for turn, phase, event_type, payload, t_ms in self._pending_log:
                self._store.log_turn(
                    self._night.id, turn, phase, event_type, payload, t_ms
                )
        except (StoreError, OSError):
            logger.exception("turn log write failed")
        self._pending_log = []

    def _name_of(self, game_id: str) -> str:
        unit_id = self._unit_ids.get(game_id)
        if unit_id is None:
            return game_id
        return self._records[unit_id].card.name

    def _announce(self, events: Sequence[Event]) -> None:
        board = self._board
        for event in events:
            if (
                event.type is EventType.KUBO_HIT
                and board is not None
                and board.kubo is not None
            ):
                self._notify("kubo.hit", {"HP": str(max(0, board.kubo.hp))})
            elif (
                event.type is EventType.DOWN
                and event.dst is not None
                and event.dst in self._unit_ids
            ):
                self._notify("unit.down", {"unit": self._name_of(event.dst)})
            elif event.type is EventType.SPLIT:
                self._notify("mana.split", {})
            elif event.dst is not None and event.dst in self._unit_ids:
                key = EFFECT_NOTICES.get(event.type)
                if key is not None:
                    name = self._name_of(event.dst)
                    self._notify(key, {"unit": name, "object": name})


def restore_player_names(narration: Narration, players: Mapping[str, str]) -> Narration:
    def swap(text: str) -> str:
        return PLAYER_ALIAS_PATTERN.sub(
            lambda m: players.get(m.group(0), m.group(0)), text
        )

    return replace(
        narration,
        narration_tl=swap(narration.narration_tl),
        narration_en=swap(narration.narration_en),
        hint_tl=swap(narration.hint_tl),
        callouts=tuple(replace(c, text_tl=swap(c.text_tl)) for c in narration.callouts),
    )


def _event_payload(event: Event) -> dict[str, object]:
    return {
        "src": event.src,
        "dst": event.dst,
        "dmg": event.dmg,
        "edge": None if event.edge is None else event.edge.value,
        "pos": None if event.pos is None else list(event.pos),
    }


def _enemy_save(enemy: EnemyState) -> EnemySave:
    intent: dict[str, object] | None = None
    if enemy.target_id is not None:
        intent = {"target_id": enemy.target_id, "dmg": enemy.intent_dmg}
    return EnemySave(
        id=enemy.id,
        type=enemy.type.value,
        part=None if enemy.part is None else enemy.part.value,
        hp=enemy.hp,
        x_cm=enemy.position[0],
        y_cm=enemy.position[1],
        spawn_turn=max(1, min(enemy.spawn_turn, TURNS_PER_NIGHT)),
        intent=intent,
        status=_enemy_status(enemy),
    )


def _enemy_status(enemy: EnemyState) -> tuple[str, ...]:
    status: list[str] = []
    if enemy.is_stunned:
        status.append(STUNNED_STATUS)
    if enemy.reform_in is not None:
        status.append(f"{REFORM_STATUS_PREFIX}{enemy.reform_in}")
    return tuple(status) + enemy_status_tags(enemy)


def _board_meta(board: BoardState, players: Sequence[str]) -> dict[str, object]:
    return {
        "players": board.players,
        "player_names": list(players),
        "enemies_defeated": board.enemies_defeated,
        "enemy_counter": dict(board.enemy_counter),
        "damage_by_owner": dict(board.damage_by_owner),
        "hulls": {u.id: [list(point) for point in u.hull_offsets] for u in board.units},
    }


def _meta_hulls(meta: Mapping[str, object]) -> dict[str, Hull]:
    value = meta.get("hulls", {})
    if not isinstance(value, dict):
        raise TypeError("saved hulls is not an object")
    hulls: dict[str, Hull] = {}
    for game_id, points in value.items():
        if not isinstance(points, list) or len(points) < MIN_HULL_POINTS:
            raise ValueError("saved hull is too small")
        hull: list[tuple[float, float]] = []
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError("saved hull point is not a pair")
            hull.append((float(point[0]), float(point[1])))
        hulls[str(game_id)] = tuple(hull)
    return hulls


def _meta_int(meta: Mapping[str, object], key: str, default: int) -> int:
    value = meta.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"saved {key} is not a count")
    return value


def _meta_counts(meta: Mapping[str, object], key: str) -> tuple[tuple[str, int], ...]:
    value = meta.get(key, {})
    if not isinstance(value, dict):
        raise TypeError(f"saved {key} is not an object")
    counts: list[tuple[str, int]] = []
    for name, count in value.items():
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError(f"saved {key} has a bad count")
        counts.append((str(name), count))
    return tuple(counts)


def _enemy_from_save(save: EnemySave, difficulty: Difficulty) -> EnemyState:
    enemy_type = EnemyType(save.type)
    part = None if save.part is None else Part(save.part)
    hp_max, atk, move_cm, range_cm, flies = enemy_stats(enemy_type, part, difficulty)
    reform_in = None
    for status in save.status:
        if status.startswith(REFORM_STATUS_PREFIX):
            reform_in = int(status.removeprefix(REFORM_STATUS_PREFIX))
    enemy = EnemyState(
        id=save.id,
        type=enemy_type,
        part=part,
        hp=save.hp,
        hp_max=hp_max,
        atk=atk,
        move_cm=move_cm,
        range_cm=range_cm,
        flies=flies,
        position=(save.x_cm, save.y_cm),
        spawn_turn=save.spawn_turn,
        is_stunned=STUNNED_STATUS in save.status,
        reform_in=reform_in,
    )
    return apply_enemy_tags(enemy, save.status)


def event_json(event: Event) -> dict[str, object]:
    return {
        "type": event.type.value,
        "src": event.src,
        "dst": event.dst,
        "dmg": event.dmg,
        "edge": None if event.edge is None else event.edge.value,
        "pos": None
        if event.pos is None
        else {"x_cm": event.pos[0], "y_cm": event.pos[1]},
    }

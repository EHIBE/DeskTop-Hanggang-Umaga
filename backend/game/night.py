from __future__ import annotations

import asyncio
import base64
import logging
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal
from enum import StrEnum
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
from capture.tracker import TrackedPose, TrackerSet
from config import (
    HANDS_OFF_WAIT_S,
    NIGHT_COST_ALERT_USD,
    REANCHOR_BOX_PADDING,
    SAM_ACCEPT_CONFIDENCE,
    STILL_FRAME_MEAN_DIFF_MAX,
    STREAM_FPS,
    STREAM_JPEG_QUALITY,
    STREAM_WIDTH_PX,
    SUMMON_SNAPSHOT_DELAY_S,
)
from db.store import (
    Campaign,
    CardFields,
    EnemySave,
    NightRecord,
    SignatureFields,
    Store,
    StoreError,
    UnitPlacement,
    UnitRecord,
    UnitSave,
)
from game.state_machine import Transition, TurnEvent, TurnState, TurnStateMachine
from meta_client import CostMeter, MetaError
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
    bayani,
    begin_turn,
    check_outcome,
    illegal_moves,
    intent_error,
    moved_kubo,
    resolve_turn,
    score,
    start_night,
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

logger = logging.getLogger("desktop.game")

Image = npt.NDArray[np.uint8]

FIRST_FRAME_TIMEOUT_S: Final = 3.0
FIRST_FRAME_POLL_S: Final = 0.05
DEMO_SAFE_SETTING: Final = "demo_safe"
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
class Snapshot:
    phase: AppPhase
    campaign: Campaign | None
    camera: CameraInfo | None
    is_calibrated: bool
    is_previewing: bool
    play_w_cm: float
    play_h_cm: float
    is_demo_safe: bool
    has_api_key: bool
    units: tuple[UnitView, ...] = field(default=())
    begin_block_key: str | None = None
    is_awaiting_tap: bool = False
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
    ) -> None:
        self._segmenter_factory = segmenter_factory
        self._tracker_factory = tracker_factory
        self._tracker: TrackerSet | None = None
        self._is_tracker_dirty = True
        self._poses: dict[int, TrackedPose] = {}
        self._uncertain: set[int] = set()
        self._sprite_service_factory = sprite_service_factory
        self._session: NightSession | None = None
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
        self._is_demo_safe = store.get_setting(DEMO_SAFE_SETTING) == "1"

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
                is_demo_safe=self._is_demo_safe,
                has_api_key=self._has_api_key,
                units=tuple(self._unit_view(unit) for unit in self._units),
                begin_block_key=begin_night_block_key(
                    [u.card.unit_class for u in self._units]
                ),
                is_awaiting_tap=self._pending is not None,
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
                c.chip_id, c.intent.unit_id, c.intent.action.value, c.intent.target_id
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
        if self._store.night_turns_completed(night.id) > 0:
            raise GameError("restore")
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
        self._run_session(session.begin)
        self._session = session
        self._notify("night.start", {})

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
        result = self._run_session(lambda: session.finish_claims(poses, sizes))
        self._publish_events(result)

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
            anchors = await self.reanchor_all()
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

    def next_night(self) -> None:
        session = self._session_or_error()
        if session.state not in (TurnState.SUNRISE, TurnState.DEFEAT):
            raise GameError("cmd.unknown")
        self._session = None
        self._enter_summon()

    def quit_night(self) -> None:
        session = self._session_or_error()
        if session.state not in (TurnState.SUNRISE, TurnState.DEFEAT):
            raise GameError("cmd.unknown")
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
        if is_camera_moved(np.asarray(baseline, dtype=np.uint8), current, self._area):
            raise GameError("cam.moved")
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
        self._store.log_turn(
            night.id, SETUP_TURN, SUMMON_PHASE, "gm_invalid", {"reason": reason}, 0
        )

    def drain_notices(self) -> list[tuple[str, dict[str, str]]]:
        notices = self._notices
        self._notices = []
        return notices

    def enforce_budget(self) -> None:
        meter = self._meter
        if meter is None:
            return
        if meter.is_stopped and not self._is_demo_safe:
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
        return self._pipeline_factory(self._is_demo_safe)

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

    async def reroll_unit(self, unit_id: str) -> UnitView:
        self._require_phase(AppPhase.SUMMON)
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
        service = factory(self._is_demo_safe)
        try:
            sprite_id = await service.ensure_sprite(job)
            if sprite_id is None:
                return
            encoded = base64.b64encode(self._store.sprite_png(sprite_id)).decode(
                "ascii"
            )
        except (StoreError, OSError, SpriteError):
            logger.exception("sprite job failed, keeping the placeholder")
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
            self._is_demo_safe = is_on
            self._store.set_setting(DEMO_SAFE_SETTING, "1" if is_on else "0")

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

    def _segmenter(self, allow_in_demo_safe: bool) -> Segmenter | None:
        self.enforce_budget()
        if self._segmenter_factory is None:
            return None
        if self._is_demo_safe and not allow_in_demo_safe:
            return None
        segmenter = self._segmenter_factory(False)
        return segmenter if segmenter.is_available else None

    async def recover_lost_objects(self) -> int:
        tracker = self._tracker
        calibration = self._calibration
        if tracker is None or calibration is None or not self._is_calibrated:
            return 0
        candidates = tracker.recovery_candidates()
        if not candidates:
            return 0
        segmenter = self._segmenter(allow_in_demo_safe=False)
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

    async def reanchor_all(self) -> dict[int, Anchor]:
        night = self._night
        calibration = self._calibration
        tracker = self._tracker
        if night is None or calibration is None or tracker is None:
            raise GameError("cmd.unknown")
        frame = await asyncio.to_thread(self.wait_for_still_frame)
        if frame is None:
            raise GameError("cam.busy")
        signatures = self._store.unit_signatures(night.id)
        tracker.new_turn()
        tracked = tracker.boxes()
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
        ]
        segmenter = self._segmenter(allow_in_demo_safe=True)
        anchors = await reanchor(
            segmenter or TrackerOnlySegmenter(),
            frame,
            targets,
            float(self._area.px_per_cm),
            safe_histogram,
            safe_distance,
        )
        self._apply_anchors(night, frame, anchors)
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


class SessionError(Exception):
    def __init__(self, copy_key: str, params: dict[str, str] | None = None) -> None:
        super().__init__(copy_key)
        self.copy_key = copy_key
        self.params: dict[str, str] = params or {}


@dataclass(frozen=True)
class Chip:
    chip_id: str
    intent: Intent


@dataclass(frozen=True)
class TurnResult:
    events: tuple[Event, ...]
    telegraph: tuple[Event, ...]
    is_blocked: bool


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

    def owner_of(self, game_id: str) -> str | None:
        return self._owners.get(game_id)

    def _t_ms(self) -> int:
        return max(0, round((self._clock() - self._started) * 1000))

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

    def _unit_state(
        self,
        record: UnitRecord,
        positions: Mapping[str, Point],
        sizes: Mapping[str, tuple[float, float]],
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
            cooldown=0,
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
        self._machine.transition(TurnEvent.TELEGRAPHED)
        self._chips = []
        self._illegal = ()
        self._announce(events)
        return events

    def add_intent(self, game_id: str, action: Action, target_id: str | None) -> Chip:
        self._require(TurnState.PLAYER_PHASE)
        board = self._board
        if board is None:
            raise SessionError("cmd.unknown")
        intent = Intent(unit_id=game_id, action=action, target_id=target_id)
        error = intent_error(board, intent)
        if error is not None:
            raise SessionError(error, {"unit": self._name_of(game_id)})
        chip = Chip(chip_id=str(uuid.uuid4()), intent=intent)
        self._chips = [c for c in self._chips if c.intent.unit_id != game_id] + [chip]
        return chip

    def cancel_chip(self, chip_id: str) -> None:
        self._require(TurnState.PLAYER_PHASE)
        remaining = [c for c in self._chips if c.chip_id != chip_id]
        if len(remaining) == len(self._chips):
            raise SessionError("cmd.unknown")
        self._chips = remaining

    def start_end_turn(self) -> None:
        self._require(TurnState.PLAYER_PHASE)
        self._machine.transition(TurnEvent.END_TURN)

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
        self._machine.transition(TurnEvent.EFFECTS_DONE)
        self._announce(events)
        for event in events:
            self._pending_log.append(
                (
                    resolved.turn,
                    TurnState.CHECK_END.value,
                    event.type.value,
                    _event_payload(event),
                    self._t_ms(),
                )
            )
        outcome = check_outcome(resolved)
        telegraph = self._conclude(outcome)
        return TurnResult(events=events, telegraph=telegraph, is_blocked=False)

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
            units_alive=sum(1 for u in board.units if not u.is_kubo and not u.is_down),
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
                status=(DOWN_STATUS,) if u.is_down else (),
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
        status=(STUNNED_STATUS,) if enemy.is_stunned else (),
    )


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

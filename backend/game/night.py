import asyncio
import base64
import logging
import threading
import time
from collections.abc import Callable
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
from config import (
    HANDS_OFF_WAIT_S,
    NIGHT_COST_ALERT_USD,
    STILL_FRAME_MEAN_DIFF_MAX,
    STREAM_FPS,
    STREAM_JPEG_QUALITY,
    STREAM_WIDTH_PX,
    SUMMON_SNAPSHOT_DELAY_S,
)
from db.store import (
    Campaign,
    CardFields,
    NightRecord,
    SignatureFields,
    Store,
    StoreError,
    UnitPlacement,
    UnitRecord,
)
from meta_client import CostMeter
from rules.units import (
    REROLLS_PER_UNIT,
    Difficulty,
    UnitClass,
    begin_night_block_key,
    clamp_card,
)
from state import Broadcast, EncodedFrame, FrameView, LiveState
from vision.sam import PixelBox, clamp_box
from vision.sprites import SpriteError, SpriteJob, SpriteService, prepare_crop
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
    ) -> None:
        self._sprite_service_factory = sprite_service_factory
        self._broadcast = broadcast
        self._crops: dict[str, Image] = {}
        self._subjects: dict[str, str] = {}
        self._sprites: dict[str, str] = {}
        self._sprite_tasks: set[asyncio.Task[None]] = set()
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
            )

    def _phase(self) -> AppPhase:
        if self._campaign is None:
            return AppPhase.START
        if not self._is_calibrated:
            return AppPhase.CALIBRATE
        return AppPhase.SUMMON

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

    def _summon_request(
        self, snapshot: Image, name: str, tap: tuple[int, int] | None
    ) -> SummonRequest:
        if self._campaign is None:
            raise GameError("start.ready")
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
        night = self._night
        if night is None or self._campaign is None:
            raise GameError("start.ready")
        unit = self._find_unit(unit_id)
        if self._unit_view(unit).rerolls_left <= 0:
            raise GameError("cmd.unknown")
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
        flags = dict(night.flags)
        flags[REROLLS_FLAG] = [*self._rerolled(), unit.unit_id]
        self._store.set_night_flags(night.id, flags)
        self._night = NightRecord(
            night.id, night.campaign_id, night.number, night.started_at, flags
        )
        return self._replace_card(self._night, unit, card)

    def _sprite_b64(self, unit: UnitRecord) -> str | None:
        if unit.unit_id in self._sprites:
            return self._sprites[unit.unit_id]
        if unit.sprite_id is None:
            return None
        try:
            png = self._store.sprite_png(unit.sprite_id)
        except (OSError, ValueError):
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
        self._subjects[unit.unit_id] = outcome.text.sprite_subject_en or outcome.label

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
        task = asyncio.get_running_loop().create_task(self._make_sprite(job))
        self._sprite_tasks.add(task)
        task.add_done_callback(self._sprite_tasks.discard)

    async def _make_sprite(self, job: SpriteJob) -> None:
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
        jpg, width, height = encode_jpeg(warp(frame.image, calibration))
        return EncodedFrame(sequence, FrameView.WARPED, width, height, jpg)

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

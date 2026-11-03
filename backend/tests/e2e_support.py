import asyncio
import json
import math
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import cv2
import numpy as np
import numpy.typing as npt

from capture.calibration import PlayArea, compute_calibration
from capture.camera import CameraInfo, MicrophoneInfo
from capture.tracker import TrackerBackend, TrackerSet
from config import CallKind, MetaModel
from db.store import ApiUsageRecord, Store
from game.night import AppPhase, GameController, GameError, Snapshot
from gm.narrator import LineBank, NarrationService, SparkNarrator
from gm.recap import RecapBuilder, SparkRecapWriter
from gm.schemas import ContentFilter
from meta_client import CallSpec, CostMeter, MetaClient, Usage, response_usage
from rules.resolve import Action
from rules.units import CardDraft, Difficulty, PowerId, UnitClass
from server import (
    build_command_fallback,
    build_narration,
    build_pipeline_factory,
    build_recap_builder,
    build_segmenter_factory,
    build_sprite_factory,
)
from state import Broadcast, LiveState
from tests.test_server import SHEET
from vision.sam import (
    Anchor,
    AnchorStatus,
    ObjectMask,
    ObjectPrompt,
    PixelBox,
    SegmentationResult,
    TrackerOnlySegmenter,
)
from vision.sprites import GeneratedSprite, SpriteJob, SpriteService
from vision.summon import CardText, Detection, FallbackDetector, SummonPipeline

Image = npt.NDArray[np.uint8]
CONTENT = ContentFilter.from_data_dir()
PLAYERS = ("Migs", "Bea")
REAL_NAMES = ("Migs", "Bea", "Tala")
OBJECT_NAMES = ("Bahay Kubo", "Stapler", "Phone", "Mug")
PX_PER_CM = 20.0
WARPED_WIDTH = 1200
WARPED_FRAME = np.zeros((800, 1200, 3), dtype=np.uint8)
CARD_FIGHTER = CardDraft(UnitClass.FIGHTER, 0, 0, PowerId.P03)
CARD_SCOUT = CardDraft(UnitClass.SCOUT, 0, 0, PowerId.P08)
SAM_SPEC = CallSpec(MetaModel.SAM, CallKind.SAM_IMAGE, True)
SPARK_SPEC = CallSpec(MetaModel.SPARK, CallKind.SPARK, True)
IMAGE_SPEC = CallSpec(MetaModel.IMAGE, CallKind.IMAGE, True)

WIN_LAYOUT = (
    PixelBox(560, 360, 640, 440),
    PixelBox(440, 360, 500, 420),
    PixelBox(700, 360, 760, 420),
    PixelBox(560, 500, 620, 560),
)
FALL_LAYOUT = (
    PixelBox(560, 360, 640, 440),
    PixelBox(560, 100, 620, 160),
    PixelBox(560, 640, 620, 700),
    PixelBox(1000, 360, 1060, 420),
)
CAMPAIGN_TABLES = (
    "campaign",
    "calibration",
    "player",
    "object_signature",
    "sprite",
    "unit",
    "night",
    "night_unit",
    "enemy",
    "voice_map",
    "turn_log",
    "campaign_recap",
)

Policy = Callable[["Rig"], None]


def centre_of(box: PixelBox) -> tuple[int, int]:
    return (box.left + box.right) // 2, (box.top + box.bottom) // 2


class FixedClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class Hands:
    def __init__(self, boxes: Sequence[PixelBox]) -> None:
        self.centres: dict[int, list[float]] = {}
        self.sizes: dict[int, tuple[int, int]] = {}
        self.reset(boxes)

    def reset(self, boxes: Sequence[PixelBox]) -> None:
        for index, box in enumerate(boxes):
            self.centres[index + 1] = [
                (box.left + box.right) / 2,
                (box.top + box.bottom) / 2,
            ]
            self.sizes[index + 1] = (box.width, box.height)

    def move_cm(self, sam_id: int, x_cm: float, y_cm: float) -> None:
        self.centres[sam_id] = [x_cm * PX_PER_CM, y_cm * PX_PER_CM]

    def backend(self) -> TrackerBackend:
        return HandBackend(self)


class HandBackend:
    def __init__(self, hands: Hands) -> None:
        self._hands = hands
        self._sam_id = 0

    def init(self, frame: Image, box: tuple[int, int, int, int]) -> None:
        scale = frame.shape[1] / WARPED_WIDTH
        cx = (box[0] + box[2] / 2) / scale
        cy = (box[1] + box[3] / 2) / scale
        centres = self._hands.centres
        self._sam_id = min(
            centres,
            key=lambda i: math.hypot(centres[i][0] - cx, centres[i][1] - cy),
        )

    def update(self, frame: Image) -> tuple[bool, tuple[int, int, int, int]]:
        scale = frame.shape[1] / WARPED_WIDTH
        cx, cy = self._hands.centres[self._sam_id]
        width, height = self._hands.sizes[self._sam_id]
        return True, (
            round((cx - width / 2) * scale),
            round((cy - height / 2) * scale),
            round(width * scale),
            round(height * scale),
        )


OBJECT_COLOURS = ((30, 90, 160), (40, 40, 200), (200, 80, 40), (60, 170, 60))
ACCENT = (235, 235, 235)


@lru_cache(maxsize=8)
def desk_scene(layout: tuple[tuple[int, int, int, int], ...]) -> Image:
    area = PlayArea()
    width, height = area.warped_size
    rng = np.random.default_rng(3)
    noise = rng.integers(0, 255, size=(height // 8, width // 8), dtype=np.uint8)
    board = cv2.cvtColor(
        cv2.resize(noise, (width, height), interpolation=cv2.INTER_NEAREST),
        cv2.COLOR_GRAY2BGR,
    )
    for (left, top, right, bottom), colour in zip(layout, OBJECT_COLOURS, strict=False):
        cx, cy = (left + right) // 2, (top + bottom) // 2
        cv2.rectangle(board, (cx - 65, cy - 65), (cx + 65, cy + 65), colour, -1)
        cv2.rectangle(board, (cx - 65, cy - 12), (cx + 65, cy + 12), ACCENT, -1)
    inverse = np.linalg.inv(compute_calibration(SHEET, area).homography)
    return np.asarray(cv2.warpPerspective(board, inverse, (1920, 1080)), dtype=np.uint8)


class DeskCamera:
    def __init__(self, scene: Image) -> None:
        self.is_plugged = True
        self._scene = scene

    def isOpened(self) -> bool:
        return True

    def set(self, prop_id: int, value: float) -> bool:
        return True

    def get(self, prop_id: int) -> float:
        return 1920.0 if prop_id == 3 else 1080.0

    def read(self) -> tuple[bool, Image | None]:
        time.sleep(0.002)
        if not self.is_plugged:
            return False, None
        return True, self._scene.copy()

    def release(self) -> None:
        return None


class RecordingSdk:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.responses = self
        self.delay_s = 0.0
        self.slow_narrations = 0

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        extra = kwargs.get("extra_body")
        text = extra.get("text") if isinstance(extra, dict) else None
        name = text["format"]["name"] if text else ""
        output: dict[str, object] = {}
        if name == "gm_turn":
            if self.slow_narrations > 0:
                self.slow_narrations -= 1
                await asyncio.sleep(self.delay_s)
            output = {
                "narration_tl": "Kapit lang, P1, bumabalik ang liwanag.",
                "narration_en": "Hold on, P1, the light is coming back.",
                "mood": "kaba",
                "callouts": [],
                "hint_tl": "",
            }
        elif name == "night_recap":
            output = {
                "recap_tl": "Kagabi, nagtulungan kayo hanggang umaga.",
                "recap_en": "Last night you held together until dawn.",
            }
        return SimpleNamespace(
            output_text=json.dumps(output),
            id=f"resp_{len(self.calls)}",
            usage=SimpleNamespace(
                input_tokens=200,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
                output_tokens=40,
            ),
        )


class CountingMeta(MetaClient):
    def __init__(self, sdk: object | None, meter: CostMeter) -> None:
        super().__init__(cast(Any, sdk), meter)
        self.execute_calls = 0
        self.sdk_calls = 0

    async def execute[T](
        self,
        spec: CallSpec,
        operation: Callable[[], Awaitable[T]],
        usage_of: Callable[[T], Usage],
    ) -> T:
        self.execute_calls += 1
        return await super().execute(spec, operation, usage_of)

    def sdk(self) -> Any:
        self.sdk_calls += 1
        return super().sdk()


class MeteredSegmenter:
    is_available = True

    def __init__(self, meta: MetaClient, sdk: RecordingSdk) -> None:
        self._meta = meta
        self._sdk = sdk
        self.calls = 0

    async def segment(
        self, image: Image, prompts: Sequence[ObjectPrompt]
    ) -> SegmentationResult:
        self.calls += 1
        sdk = self._sdk

        async def operation() -> object:
            return await sdk.create(model=MetaModel.SAM.value, store=False, stream=True)

        await self._meta.execute(SAM_SPEC, operation, lambda _: Usage(images=1))
        masks: dict[int, ObjectMask] = {}
        for prompt in prompts:
            box = prompt.box
            masks[prompt.sam_id] = ObjectMask(
                prompt.sam_id,
                0.9,
                box,
                np.ones((box.height, box.width), dtype=np.bool_),
            )
        return SegmentationResult(masks=masks)


class MeteredDetector:
    is_available = True

    def __init__(
        self,
        meta: MetaClient,
        sdk: RecordingSdk,
        boxes: Sequence[PixelBox],
        drafts: Sequence[CardDraft],
    ) -> None:
        self._meta = meta
        self._sdk = sdk
        self._boxes = boxes
        self._drafts = drafts
        self._index = 0

    async def detect(
        self, snapshot: Image, spoken_name: str, known: object
    ) -> Detection:
        sdk = self._sdk

        async def operation() -> object:
            return await sdk.create(model=MetaModel.SPARK.value, store=False)

        await self._meta.execute(SPARK_SPEC, operation, cast(Any, response_usage))
        index = self._index
        self._index += 1
        return Detection(
            found_new=True,
            label=spoken_name.lower(),
            box=self._boxes[index % len(self._boxes)],
            draft=self._drafts[index % len(self._drafts)],
            text=CardText(),
            source="spark",
        )


class MeteredGenerator:
    is_available = True

    def __init__(self, meta: MetaClient, sdk: RecordingSdk) -> None:
        self._meta = meta
        self._sdk = sdk

    async def generate(
        self, job: SpriteJob, style_anchor_png: bytes | None
    ) -> GeneratedSprite:
        sdk = self._sdk

        async def operation() -> object:
            return await sdk.create(model=MetaModel.IMAGE.value, store=False)

        await self._meta.execute(IMAGE_SPEC, operation, lambda _: Usage(images=1))
        return GeneratedSprite(png=b"PNG-e2e", response_id=None)


@dataclass
class Rig:
    root: Path
    store: Store
    controller: GameController
    broadcast: Broadcast
    queue: asyncio.Queue[dict[str, object]]
    meta: CountingMeta
    meter: CostMeter
    sdk: RecordingSdk
    clock: FixedClock
    hands: Hands
    camera: DeskCamera
    boxes: Sequence[PixelBox]
    live: LiveState
    narration: NarrationService
    invalid: list[str] = field(default_factory=list)
    messages: list[dict[str, object]] = field(default_factory=list)

    def drain(self) -> list[dict[str, object]]:
        while not self.queue.empty():
            self.messages.append(self.queue.get_nowait())
        return self.messages

    def of_type(self, kind: str) -> list[dict[str, object]]:
        return [m for m in self.drain() if m["type"] == kind]

    def event_types(self) -> list[str]:
        found: list[str] = []
        for message in self.of_type("events"):
            events = cast(list[dict[str, object]], message["events"])
            found.extend(str(e["type"]) for e in events)
        return found

    @property
    def snapshot(self) -> Snapshot:
        return self.controller.snapshot()

    def phase(self) -> AppPhase:
        return self.controller.snapshot().phase

    def pump(self) -> None:
        self.controller.track(WARPED_FRAME)
        self.controller.track(WARPED_FRAME)

    def align_hands(self) -> None:
        night = self.controller.snapshot().night
        assert night is not None
        for unit in night.units:
            sam_id = 1 if unit.game_id == "u_kubo" else int(unit.game_id[2:])
            self.hands.sizes.setdefault(sam_id, (60, 60))
            self.hands.move_cm(sam_id, unit.start[0], unit.start[1])

    def close(self) -> None:
        self.controller.close()
        self.store.close()


def build_rig(
    root: Path,
    *,
    api_key: bool,
    demo_safe: bool,
    layout: Sequence[PixelBox] = WIN_LAYOUT,
    drafts: Sequence[CardDraft] = (CARD_FIGHTER,),
    narration_timeout_s: float = 20.0,
    store: Store | None = None,
    sdk: RecordingSdk | None = None,
    voice_factory: Any = None,
) -> Rig:
    root.mkdir(parents=True, exist_ok=True)
    opened = store if store is not None else Store(root / "db.sqlite")
    live_sdk = sdk if sdk is not None else RecordingSdk()
    meter = CostMeter(opened)
    meta = CountingMeta(live_sdk if api_key else None, meter)
    clock = FixedClock()
    broadcast = Broadcast()
    queue = broadcast.subscribe()
    line_bank = LineBank()
    hands = Hands(layout)
    camera = DeskCamera(
        desk_scene(tuple((b.left, b.top, b.right, b.bottom) for b in layout))
    )
    invalid: list[str] = []
    live = LiveState()
    detector = MeteredDetector(meta, live_sdk, layout, drafts)
    live_segmenter = MeteredSegmenter(meta, live_sdk)

    def pipeline_for(is_demo_safe: bool) -> SummonPipeline:
        if is_demo_safe or not meta.has_credentials:
            return SummonPipeline(FallbackDetector(), TrackerOnlySegmenter(), CONTENT)
        return SummonPipeline(detector, live_segmenter, CONTENT)

    def segmenter_for(is_demo_safe: bool) -> Any:
        return live_segmenter if meta.has_credentials else TrackerOnlySegmenter()

    def sprites_for(is_demo_safe: bool) -> SpriteService:
        if is_demo_safe or not meta.has_credentials:
            return build_sprite_factory(opened, meta)(True)
        return SpriteService(opened, MeteredGenerator(meta, live_sdk))

    if api_key:
        narration = NarrationService(
            line_bank,
            lambda: SparkNarrator(meta, CONTENT, line_bank, invalid.append),
            timeout_s=narration_timeout_s,
        )
        recap_builder = RecapBuilder(
            line_bank,
            CONTENT,
            SparkRecapWriter(meta, CONTENT, invalid.append),
            None,
        )
        pipeline_factory: Callable[[bool], SummonPipeline] = pipeline_for
        segmenter_factory: Any = segmenter_for
        sprite_factory: Any = sprites_for
    else:
        narration = build_narration(meta, CONTENT, invalid.append, line_bank)
        recap_builder = build_recap_builder(meta, CONTENT, invalid.append, line_bank)
        pipeline_factory = build_pipeline_factory(meta, CONTENT, invalid.append)
        segmenter_factory = build_segmenter_factory(meta)
        sprite_factory = build_sprite_factory(opened, meta)

    def tracker_factory(px_per_cm: float, size: tuple[int, int]) -> TrackerSet:
        return TrackerSet(
            px_per_cm=px_per_cm, warped_size=size, backend_factory=hands.backend
        )

    controller = GameController(
        opened,
        live,
        has_api_key=api_key,
        camera_factory=lambda _: camera,
        list_camera_devices=lambda: [CameraInfo(0, 1920, 1080)],
        list_microphone_devices=lambda: [MicrophoneInfo(1, "Mic")],
        clock=clock,
        sleep=lambda _: None,
        pipeline_factory=pipeline_factory,
        meter=meter,
        sprite_service_factory=sprite_factory,
        broadcast=broadcast,
        segmenter_factory=segmenter_factory,
        tracker_factory=tracker_factory,
        narration=narration,
        voice_factory=voice_factory,
        clean_name=CONTENT.clean_player_name,
        line_bank=line_bank,
        recap_builder=recap_builder,
        command_fallback=build_command_fallback(meta),
    )
    if demo_safe:
        controller.set_demo_safe(True)
    return Rig(
        root=root,
        store=opened,
        controller=controller,
        broadcast=broadcast,
        queue=queue,
        meta=meta,
        meter=meter,
        sdk=live_sdk,
        clock=clock,
        hands=hands,
        camera=camera,
        boxes=layout,
        live=live,
        narration=narration,
        invalid=invalid,
    )


def install_anchor_override(
    rig: Rig, sam_id: int, x_cm: float, y_cm: float
) -> dict[str, bool]:
    mode = {"on": False}
    original = rig.controller.reanchor_all

    async def reanchor(still: Image | None = None) -> dict[int, Anchor]:
        anchors = await original(still)
        if mode["on"]:
            anchors[sam_id] = Anchor(
                sam_id, PixelBox(10, 10, 50, 50), x_cm, y_cm, AnchorStatus.ACCEPTED
            )
        return anchors

    rig.controller.reanchor_all = reanchor  # type: ignore[method-assign]
    return mode


def start_campaign(rig: Rig, difficulty: Difficulty = Difficulty.NORMAL) -> None:
    controller = rig.controller
    controller.start_new_campaign("Barkada", difficulty)
    controller.select_camera(0)
    controller.submit_corners(SHEET, 60.0, 40.0)
    controller.confirm_calibration()


async def summon_roster(rig: Rig, names: Sequence[str] = OBJECT_NAMES) -> None:
    for name, box in zip(names, rig.boxes, strict=False):
        try:
            await rig.controller.summon(name)
        except GameError as error:
            assert error.copy_key == "summon.which"
            await rig.controller.summon_tap(centre_of(box))


def claim_two_players(controller: GameController) -> None:
    controller.begin_night()
    controller.claim(PLAYERS[0], ["u_kubo", "u_2", "u_4"], CONTENT.clean_player_name)
    controller.claim(PLAYERS[1], ["u_3"], CONTENT.clean_player_name)
    controller.finish_claims()


async def new_night(rig: Rig, names: Sequence[str] = OBJECT_NAMES) -> None:
    await summon_roster(rig, names)
    claim_two_players(rig.controller)
    rig.pump()


def threat_order(rig: Rig, spare: Iterable[str]) -> list[Any]:
    night = rig.snapshot.night
    assert night is not None
    skipped = set(spare)
    return sorted(
        (e for e in night.enemies if e.type not in skipped),
        key=lambda e: (e.target_id != "u_kubo", -(e.intent_dmg or 0), e.hp),
    )


def defend_policy(spare: Iterable[str] = ()) -> Policy:
    def policy(rig: Rig) -> None:
        night = rig.snapshot.night
        assert night is not None
        enemies = threat_order(rig, spare)
        if not enemies:
            return
        left = {e.id: e.hp for e in enemies}
        for unit in night.units:
            if unit.is_down or unit.game_id == "u_kubo":
                continue
            pool = [e for e in enemies if left[e.id] > 0] or enemies
            enemy = pool[0]
            left[enemy.id] -= 2
            dx = enemy.x_cm - unit.start[0]
            dy = enemy.y_cm - unit.start[1]
            distance = math.hypot(dx, dy)
            step = min(unit.move_cm * 0.8, max(0.0, distance - 3.0))
            x = unit.start[0] + (dx / distance * step if distance else 0.0)
            y = unit.start[1] + (dy / distance * step if distance else 0.0)
            rig.hands.move_cm(
                int(unit.game_id[2:]), min(57.5, max(2.5, x)), min(37.5, max(2.5, y))
            )
            try:
                rig.controller.add_intent(unit.game_id, Action.ATTACK, enemy.id)
            except GameError:
                continue

    return policy


def idle_policy(rig: Rig) -> None:
    return None


async def play_turn(rig: Rig, policy: Policy) -> Snapshot:
    policy(rig)
    rig.pump()
    await rig.controller.end_turn()
    if rig.phase() is AppPhase.PHYSICAL_EFFECTS:
        rig.controller.finish_effects_now()
    return rig.snapshot


async def play_to_end(
    rig: Rig, policy: Policy, after_turn: Callable[[], Awaitable[None]] | None = None
) -> list[int]:
    turns: list[int] = []
    for _ in range(12):
        snapshot = rig.snapshot
        if snapshot.phase is not AppPhase.PLAYER_PHASE or snapshot.night is None:
            break
        turns.append(snapshot.night.turn)
        await play_turn(rig, policy)
        if after_turn is not None:
            await after_turn()
    return turns


def table_counts(
    store: Store, tables: Iterable[str] = CAMPAIGN_TABLES
) -> dict[str, int]:
    counts: dict[str, int] = {}
    with store.transaction() as conn:
        for table in tables:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = int(row[0])
    return counts


def usage_rows(store: Store) -> list[tuple[str, str, float, int]]:
    with store.transaction() as conn:
        rows = conn.execute(
            "SELECT model, kind, cost_usd, ok FROM api_usage ORDER BY id"
        ).fetchall()
    return [(str(r[0]), str(r[1]), float(r[2]), int(r[3])) for r in rows]


def data_files(root: Path) -> list[str]:
    return sorted(
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    )


def spend(meter: CostMeter, usd: str) -> None:
    meter.record(
        ApiUsageRecord(
            model="muse-spark-1.3", kind="spark", cost_usd=Decimal(usd), ok=True
        )
    )


def transition_targets(store: Store, night_id: str) -> list[str]:
    return [
        phase
        for _, phase, kind, _, _ in store.turn_log_rows(night_id)
        if kind == "transition"
    ]


def saved_turns(store: Store, night_id: str) -> int:
    with store.transaction() as conn:
        row = conn.execute(
            "SELECT turns_completed FROM night WHERE id = ?", (night_id,)
        ).fetchone()
    return int(row[0])


def night_result(store: Store, night_id: str) -> str | None:
    with store.transaction() as conn:
        row = conn.execute(
            "SELECT result FROM night WHERE id = ?", (night_id,)
        ).fetchone()
    return None if row[0] is None else str(row[0])


def night_id_of(store: Store, number: int) -> str:
    with store.transaction() as conn:
        row = conn.execute(
            "SELECT id FROM night WHERE number = ?", (number,)
        ).fetchone()
    return str(row[0])


def unit_by_name(rig: Rig, name: str) -> Any:
    return next(u for u in rig.controller._units if u.card.name == name)


def view_units(snapshot: Snapshot) -> Mapping[str, Any]:
    assert snapshot.night is not None
    return {u.game_id: u for u in snapshot.night.units}

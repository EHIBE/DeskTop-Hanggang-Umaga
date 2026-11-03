import json
import logging
import math
import re
import shutil
import sqlite3
import threading
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final

from rules.units import Difficulty, MoveClass, PowerId, RangeClass, UnitClass

logger = logging.getLogger("desktop.store")

SCHEMA_VERSION: Final = 3
MIGRATIONS: Final[dict[int, str]] = {
    1: "ALTER TABLE night ADD COLUMN board_json TEXT;",
    2: (
        "ALTER TABLE unit ADD COLUMN scars_json TEXT;\n"
        "ALTER TABLE campaign ADD COLUMN map_image_path TEXT;\n"
        "CREATE TABLE campaign_recap (\n"
        "  campaign_id TEXT PRIMARY KEY REFERENCES campaign(id) ON DELETE CASCADE,\n"
        "  text TEXT NOT NULL CHECK (length(text) BETWEEN 1 AND 1000),\n"
        "  source TEXT NOT NULL CHECK (source IN ('spark','line_bank','glimmer')),\n"
        "  created_at TEXT NOT NULL\n"
        ");"
    ),
}
SCHEMA_PATH: Final = Path(__file__).with_name("schema.sql")
COST_SCALE: Final = 100_000_000
CAMPAIGN_PAGE_MAX: Final = 50
CAMPAIGNS_DIR_NAME: Final = "campaigns"
BASELINE_FILE_NAME: Final = "baseline.png"
HOMOGRAPHY_SIZE: Final = 9
REF_CROP_DIR_NAME: Final = "crops"
SPRITES_DIR_NAME: Final = "sprites"
SETUP_TURN: Final = 0
BARRIO_LEVEL_MAX: Final = 5
PROGRESS_ID_PATTERN: Final = re.compile(r"[a-z0-9_]{1,32}")
PROGRESS_LIST_MAX: Final = 8
RECAP_SOURCES: Final = ("spark", "line_bank", "glimmer")
RECAP_TEXT_MAX: Final = 1000
MIC_DEVICE_MAX: Final = 200
SettingValue = bool | int | str
SETTING_CHOICES: Final[dict[str, tuple[str, ...]]] = {
    "caption_language": ("tl", "en"),
    "difficulty": ("easy", "normal", "hard"),
}
SETTING_DEFAULTS: Final[dict[str, SettingValue]] = {
    "camera_device": 0,
    "mic_device": "default",
    "caption_language": "tl",
    "difficulty": "normal",
    "replay_enabled": True,
    "tts_enabled": False,
    "show_real_objects": True,
    "strict_ownership": False,
    "generated_map": False,
}

Clock = Callable[[], datetime]
IdFactory = Callable[[], str]


class StoreError(Exception):
    pass


class SchemaVersionError(StoreError):
    pass


class NotFoundError(StoreError):
    pass


class UnsafePathError(StoreError):
    pass


@dataclass(frozen=True)
class Campaign:
    id: str
    name: str
    difficulty: Difficulty
    barrio_level: int
    nights_survived: int
    created_at: str


@dataclass(frozen=True)
class Progression:
    barrio_level: int
    nights_survived: int


@dataclass(frozen=True)
class UnitProgress:
    badges: tuple[str, ...]
    scars: tuple[str, ...]


@dataclass(frozen=True)
class SavedRecap:
    campaign_id: str
    text: str
    source: str
    created_at: str


@dataclass(frozen=True)
class ApiUsageRecord:
    model: str
    kind: str
    cost_usd: Decimal
    ok: bool
    latency_ms: int | None = None
    input_tokens: int | None = None
    cached_tokens: int | None = None
    output_tokens: int | None = None
    images: int | None = None
    frames: int | None = None
    audio_seconds: int | None = None


@dataclass(frozen=True)
class CalibrationRecord:
    id: str
    campaign_id: str
    homography: tuple[float, ...]
    px_per_cm: float
    play_w_cm: float
    play_h_cm: float
    baseline_path: Path
    created_at: str


@dataclass(frozen=True)
class NightRecord:
    id: str
    campaign_id: str
    number: int
    started_at: str
    flags: dict[str, object]


@dataclass(frozen=True)
class CardFields:
    name: str
    unit_class: UnitClass
    hp_max: int
    atk: int
    move_class: MoveClass
    range_class: RangeClass
    power_id: PowerId
    power_name_tl: str
    card_text_tl: str
    card_text_en: str


@dataclass(frozen=True)
class SignatureFields:
    label: str
    histogram: tuple[float, ...]
    area_cm2: float
    aspect: float
    ref_crop_png: bytes


@dataclass(frozen=True)
class UnitPlacement:
    sam_object_id: int
    x_cm: float
    y_cm: float


@dataclass(frozen=True)
class UnitRecord:
    unit_id: str
    signature_id: str
    sam_object_id: int
    card: CardFields
    hp_current: int
    x_cm: float
    y_cm: float
    sprite_id: str | None


@dataclass(frozen=True)
class StoredSignature:
    label: str
    histogram: tuple[float, ...]
    area_cm2: float
    aspect: float
    ref_crop_path: Path


@dataclass(frozen=True)
class StoredUnit:
    unit_id: str
    signature_id: str
    card: CardFields
    sprite_id: str | None
    progress: UnitProgress
    signature: StoredSignature


@dataclass(frozen=True)
class SpriteRecord:
    id: str
    cache_key: str
    path: Path
    palette_version: str
    prompt_version: str
    source_response_id: str | None


@dataclass(frozen=True)
class UnitSave:
    unit_id: str
    hp_current: int
    x_cm: float
    y_cm: float
    cooldown: int
    status: tuple[str, ...]


@dataclass(frozen=True)
class EnemySave:
    id: str
    type: str
    part: str | None
    hp: int
    x_cm: float
    y_cm: float
    spawn_turn: int
    intent: dict[str, object] | None
    status: tuple[str, ...]


@dataclass(frozen=True)
class SavedNight:
    turns_completed: int
    board: dict[str, object]
    units: dict[str, UnitSave]
    enemies: tuple[EnemySave, ...]


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_uuid() -> str:
    return str(uuid.uuid4())


def to_cost_units(cost_usd: Decimal) -> int:
    if cost_usd < 0:
        raise StoreError("cost cannot be negative")
    return int((cost_usd * COST_SCALE).to_integral_value())


def from_cost_units(units: int) -> Decimal:
    return Decimal(units) / Decimal(COST_SCALE)


class Store:
    def __init__(
        self, path: Path, clock: Clock = utc_now, new_id: IdFactory = new_uuid
    ) -> None:
        self._clock = clock
        self._new_id = new_id
        self._lock = threading.RLock()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._data_root = path.parent.resolve()
        self._conn = sqlite3.connect(
            path, isolation_level=None, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA secure_delete = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        try:
            self._migrate()
        except BaseException:
            self._conn.close()
            raise

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _now_iso(self) -> str:
        return self._clock().astimezone(UTC).isoformat()

    def _migrate(self) -> None:
        version = int(self._conn.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise SchemaVersionError(
                f"database schema {version} is newer than {SCHEMA_VERSION}"
            )
        if version == SCHEMA_VERSION:
            return
        if version == 0:
            script = SCHEMA_PATH.read_text(encoding="utf-8")
        else:
            script = "\n".join(
                MIGRATIONS[step] for step in range(version, SCHEMA_VERSION)
            )
        with self._lock:
            try:
                self._conn.executescript(
                    f"BEGIN;\n{script}\nPRAGMA user_version = {SCHEMA_VERSION};\nCOMMIT;"
                )
            except sqlite3.Error:
                if self._conn.in_transaction:
                    self._conn.execute("ROLLBACK")
                raise

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    def schema_version(self) -> int:
        with self._lock:
            return int(self._conn.execute("PRAGMA user_version").fetchone()[0])

    def foreign_keys_enabled(self) -> bool:
        with self._lock:
            return bool(self._conn.execute("PRAGMA foreign_keys").fetchone()[0])

    def create_campaign(self, name: str, difficulty: Difficulty) -> Campaign:
        campaign = Campaign(
            id=self._new_id(),
            name=name,
            difficulty=difficulty,
            barrio_level=0,
            nights_survived=0,
            created_at=self._now_iso(),
        )
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO campaign (id, name, difficulty, created_at) VALUES (?, ?, ?, ?)",
                (
                    campaign.id,
                    campaign.name,
                    campaign.difficulty.value,
                    campaign.created_at,
                ),
            )
        return campaign

    def get_campaign(self, campaign_id: str) -> Campaign:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, name, difficulty, barrio_level, nights_survived, created_at "
                "FROM campaign WHERE id = ?",
                (campaign_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError("campaign not found")
        return _campaign_from_row(row)

    def list_campaigns(self, limit: int = 20, offset: int = 0) -> list[Campaign]:
        if not 1 <= limit <= CAMPAIGN_PAGE_MAX or offset < 0:
            raise StoreError("invalid page")
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, name, difficulty, barrio_level, nights_survived, created_at "
                "FROM campaign ORDER BY created_at DESC, id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [_campaign_from_row(row) for row in rows]

    def delete_campaign(self, campaign_id: str) -> bool:
        directory = self.campaign_dir(campaign_id)
        with self.transaction() as conn:
            sprite_rows = conn.execute(
                "SELECT s.id, s.path FROM sprite s "
                "WHERE NOT EXISTS (SELECT 1 FROM unit u WHERE u.sprite_id = s.id AND u.campaign_id <> ?) "
                "AND NOT EXISTS (SELECT 1 FROM campaign c WHERE c.style_anchor_sprite_id = s.id AND c.id <> ?)",
                (campaign_id, campaign_id),
            ).fetchall()
            sprite_paths = [self._sprite_file(str(row["path"])) for row in sprite_rows]
            cursor = conn.execute("DELETE FROM campaign WHERE id = ?", (campaign_id,))
            conn.executemany(
                "DELETE FROM sprite WHERE id = ?",
                [(str(row["id"]),) for row in sprite_rows],
            )
        with self._lock:
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._remove_files(directory, sprite_paths)
        return cursor.rowcount > 0

    def _sweep_sprite_files(self) -> list[Path]:
        sprite_root = self._data_root / SPRITES_DIR_NAME
        if not sprite_root.is_dir():
            return []
        with self._lock:
            known = {
                self._sprite_file(str(row[0]))
                for row in self._conn.execute("SELECT path FROM sprite").fetchall()
            }
        leftovers: list[Path] = []
        for path in sprite_root.glob("*.png"):
            resolved = path.resolve()
            if resolved in known:
                continue
            resolved.unlink(missing_ok=True)
            if resolved.exists():
                leftovers.append(resolved)
        return leftovers

    def _sprite_file(self, stored: str) -> Path:
        resolved = (self._data_root / stored).resolve()
        if not resolved.is_relative_to(self._data_root / SPRITES_DIR_NAME):
            raise UnsafePathError("stored sprite path escapes the sprite folder")
        return resolved

    def _remove_files(self, directory: Path, sprite_paths: Sequence[Path]) -> None:
        leftovers: list[Path] = []
        for sprite_path in sprite_paths:
            sprite_path.unlink(missing_ok=True)
            if sprite_path.exists():
                leftovers.append(sprite_path)
        leftovers.extend(self._sweep_sprite_files())
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)
        if directory.exists():
            leftovers.append(directory)
        if leftovers:
            raise StoreError("some campaign files could not be deleted")

    def record_api_usage(self, record: ApiUsageRecord) -> None:
        cost_units = to_cost_units(record.cost_usd)
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO api_usage (ts, model, kind, input_tokens, cached_tokens, "
                "output_tokens, images, frames, audio_seconds, cost_usd, latency_ms, ok) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self._now_iso(),
                    record.model,
                    record.kind,
                    record.input_tokens,
                    record.cached_tokens,
                    record.output_tokens,
                    record.images,
                    record.frames,
                    record.audio_seconds,
                    float(from_cost_units(cost_units)),
                    record.latency_ms,
                    int(record.ok),
                ),
            )

    def total_api_cost(self) -> Decimal:
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(CAST(ROUND(cost_usd * ?) AS INTEGER)), 0) FROM api_usage",
                (COST_SCALE,),
            ).fetchone()
        return from_cost_units(int(row[0]))

    def get_setting(self, key: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        return str(row[0])

    @property
    def data_root(self) -> Path:
        return self._data_root

    def campaign_dir(self, campaign_id: str) -> Path:
        if str(_parse_uuid(campaign_id)) != campaign_id:
            raise UnsafePathError("campaign id must be a canonical UUID")
        target = (self._data_root / CAMPAIGNS_DIR_NAME / campaign_id).resolve()
        if not target.is_relative_to(self._data_root / CAMPAIGNS_DIR_NAME):
            raise UnsafePathError("campaign path escapes the data root")
        return target

    def save_calibration(
        self,
        campaign_id: str,
        homography: Sequence[float],
        px_per_cm: float,
        play_size_cm: tuple[float, float],
        baseline_png: bytes,
    ) -> CalibrationRecord:
        values = tuple(float(value) for value in homography)
        if len(values) != HOMOGRAPHY_SIZE or not all(math.isfinite(v) for v in values):
            raise StoreError("homography must be 9 finite numbers")
        self.get_campaign(campaign_id)
        directory = self.campaign_dir(campaign_id)
        directory.mkdir(parents=True, exist_ok=True)
        baseline = directory / BASELINE_FILE_NAME
        baseline.write_bytes(baseline_png)
        record = CalibrationRecord(
            id=self._new_id(),
            campaign_id=campaign_id,
            homography=values,
            px_per_cm=px_per_cm,
            play_w_cm=play_size_cm[0],
            play_h_cm=play_size_cm[1],
            baseline_path=baseline,
            created_at=self._now_iso(),
        )
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO calibration (id, campaign_id, homography_json, px_per_cm, "
                "play_w_cm, play_h_cm, baseline_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.id,
                    campaign_id,
                    json.dumps(list(values)),
                    px_per_cm,
                    record.play_w_cm,
                    record.play_h_cm,
                    baseline.relative_to(self._data_root).as_posix(),
                    record.created_at,
                ),
            )
        return record

    def latest_calibration(self, campaign_id: str) -> CalibrationRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, campaign_id, homography_json, px_per_cm, play_w_cm, play_h_cm, "
                "baseline_path, created_at FROM calibration WHERE campaign_id = ? "
                "ORDER BY created_at DESC, id DESC LIMIT 1",
                (campaign_id,),
            ).fetchone()
        if row is None:
            return None
        baseline = (self._data_root / str(row["baseline_path"])).resolve()
        if not baseline.is_relative_to(self._data_root):
            raise UnsafePathError("stored baseline path escapes the data root")
        return CalibrationRecord(
            id=str(row["id"]),
            campaign_id=str(row["campaign_id"]),
            homography=tuple(float(v) for v in json.loads(str(row["homography_json"]))),
            px_per_cm=float(row["px_per_cm"]),
            play_w_cm=float(row["play_w_cm"]),
            play_h_cm=float(row["play_h_cm"]),
            baseline_path=baseline,
            created_at=str(row["created_at"]),
        )

    def start_or_resume_night(self, campaign_id: str) -> NightRecord:
        self.get_campaign(campaign_id)
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT id, campaign_id, number, started_at, flags_json FROM night "
                "WHERE campaign_id = ? AND result IS NULL ORDER BY number DESC LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if row is not None:
                return _night_from_row(row)
            last = conn.execute(
                "SELECT COALESCE(MAX(number), 0) FROM night WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            night = NightRecord(
                id=self._new_id(),
                campaign_id=campaign_id,
                number=int(last[0]) + 1,
                started_at=self._now_iso(),
                flags={},
            )
            conn.execute(
                "INSERT INTO night (id, campaign_id, number, started_at) VALUES (?, ?, ?, ?)",
                (night.id, campaign_id, night.number, night.started_at),
            )
        return night

    def set_night_flags(self, night_id: str, flags: dict[str, object]) -> None:
        with self.transaction() as conn:
            cursor = conn.execute(
                "UPDATE night SET flags_json = ? WHERE id = ?",
                (json.dumps(flags), night_id),
            )
        if cursor.rowcount == 0:
            raise NotFoundError("night not found")

    def turn_log_rows(
        self, night_id: str
    ) -> list[tuple[int, str, str, dict[str, object], int]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT turn, phase, event_type, payload_json, t_ms FROM turn_log "
                "WHERE night_id = ? ORDER BY id",
                (night_id,),
            ).fetchall()
        result: list[tuple[int, str, str, dict[str, object], int]] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            result.append(
                (
                    int(row["turn"]),
                    str(row["phase"]),
                    str(row["event_type"]),
                    payload if isinstance(payload, dict) else {},
                    int(row["t_ms"]),
                )
            )
        return result

    def set_replay_path(self, night_id: str, path: Path) -> None:
        relative = path.resolve().relative_to(self._data_root).as_posix()
        with self.transaction() as conn:
            cursor = conn.execute(
                "UPDATE night SET replay_path = ? WHERE id = ?", (relative, night_id)
            )
        if cursor.rowcount == 0:
            raise NotFoundError("night not found")

    def set_recording_consent(self, night_id: str, is_given: bool) -> None:
        with self.transaction() as conn:
            cursor = conn.execute(
                "UPDATE night SET recording_consent = ? WHERE id = ?",
                (int(is_given), night_id),
            )
        if cursor.rowcount == 0:
            raise NotFoundError("night not found")

    def recording_consent(self, night_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT recording_consent FROM night WHERE id = ?", (night_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError("night not found")
        return bool(row[0])

    def add_unit(
        self,
        night: NightRecord,
        card: CardFields,
        signature: SignatureFields,
        placement: UnitPlacement,
    ) -> UnitRecord:
        crops = self.campaign_dir(night.campaign_id) / REF_CROP_DIR_NAME
        crops.mkdir(parents=True, exist_ok=True)
        signature_id = self._new_id()
        unit_id = self._new_id()
        crop_path = crops / f"{signature_id}.png"
        crop_path.write_bytes(signature.ref_crop_png)
        try:
            with self.transaction() as conn:
                conn.execute(
                    "INSERT INTO object_signature (id, campaign_id, label, hist_json, area_cm2, "
                    "aspect, ref_crop_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        signature_id,
                        night.campaign_id,
                        signature.label,
                        json.dumps(list(signature.histogram)),
                        signature.area_cm2,
                        signature.aspect,
                        crop_path.relative_to(self._data_root).as_posix(),
                        self._now_iso(),
                    ),
                )
                conn.execute(
                    "INSERT INTO unit (id, campaign_id, object_signature_id, name, class, hp_max, "
                    "atk, move_class, range_class, power_id, power_name_tl, card_text_tl, "
                    "card_text_en) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (unit_id, night.campaign_id, signature_id, *_card_values(card)),
                )
                conn.execute(
                    "INSERT INTO night_unit (night_id, unit_id, sam_object_id, hp_current, "
                    "x_cm, y_cm) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        night.id,
                        unit_id,
                        placement.sam_object_id,
                        card.hp_max,
                        placement.x_cm,
                        placement.y_cm,
                    ),
                )
        except BaseException:
            crop_path.unlink(missing_ok=True)
            raise
        return UnitRecord(
            unit_id=unit_id,
            signature_id=signature_id,
            sam_object_id=placement.sam_object_id,
            card=card,
            hp_current=card.hp_max,
            x_cm=placement.x_cm,
            y_cm=placement.y_cm,
            sprite_id=None,
        )

    def attach_unit(
        self, night: NightRecord, unit_id: str, placement: UnitPlacement
    ) -> UnitRecord:
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT hp_max FROM unit WHERE id = ? AND campaign_id = ?",
                (unit_id, night.campaign_id),
            ).fetchone()
            if row is None:
                raise NotFoundError("unit not found")
            conn.execute(
                "INSERT INTO night_unit (night_id, unit_id, sam_object_id, hp_current, "
                "x_cm, y_cm) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    night.id,
                    unit_id,
                    placement.sam_object_id,
                    int(row["hp_max"]),
                    placement.x_cm,
                    placement.y_cm,
                ),
            )
        for record in self.night_units(night.id):
            if record.unit_id == unit_id:
                return record
        raise NotFoundError("unit not found")

    def unit_crops(self, night_id: str) -> dict[str, bytes]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT nu.unit_id, os.ref_crop_path FROM night_unit nu "
                "JOIN unit u ON u.id = nu.unit_id "
                "JOIN object_signature os ON os.id = u.object_signature_id "
                "WHERE nu.night_id = ?",
                (night_id,),
            ).fetchall()
        crops: dict[str, bytes] = {}
        for row in rows:
            path = (self._data_root / str(row["ref_crop_path"])).resolve()
            if not path.is_relative_to(self._data_root):
                continue
            try:
                crops[str(row["unit_id"])] = path.read_bytes()
            except OSError:
                continue
        return crops

    def update_unit_card(self, night_id: str, unit_id: str, card: CardFields) -> None:
        with self.transaction() as conn:
            cursor = conn.execute(
                "UPDATE unit SET name = ?, class = ?, hp_max = ?, atk = ?, move_class = ?, "
                "range_class = ?, power_id = ?, power_name_tl = ?, card_text_tl = ?, "
                "card_text_en = ? WHERE id = ?",
                (*_card_values(card), unit_id),
            )
            if cursor.rowcount == 0:
                raise NotFoundError("unit not found")
            conn.execute(
                "UPDATE night_unit SET hp_current = ? WHERE night_id = ? AND unit_id = ?",
                (card.hp_max, night_id, unit_id),
            )

    def night_units(self, night_id: str) -> list[UnitRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT u.id, u.object_signature_id, nu.sam_object_id, u.name, u.class, "
                "u.hp_max, u.atk, u.move_class, u.range_class, u.power_id, u.power_name_tl, "
                "u.card_text_tl, u.card_text_en, nu.hp_current, nu.x_cm, nu.y_cm, u.sprite_id "
                "FROM night_unit nu JOIN unit u ON u.id = nu.unit_id "
                "WHERE nu.night_id = ? ORDER BY nu.sam_object_id",
                (night_id,),
            ).fetchall()
        return [_unit_from_row(row) for row in rows]

    def unit_signatures(
        self, night_id: str
    ) -> dict[str, tuple[str, tuple[float, ...]]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT nu.unit_id, os.label, os.hist_json FROM night_unit nu "
                "JOIN unit u ON u.id = nu.unit_id "
                "JOIN object_signature os ON os.id = u.object_signature_id "
                "WHERE nu.night_id = ?",
                (night_id,),
            ).fetchall()
        return {
            str(row["unit_id"]): (
                str(row["label"]),
                tuple(float(v) for v in json.loads(str(row["hist_json"]))),
            )
            for row in rows
        }

    def update_positions(
        self, night_id: str, positions: dict[str, tuple[float, float]]
    ) -> None:
        with self.transaction() as conn:
            conn.executemany(
                "UPDATE night_unit SET x_cm = ?, y_cm = ? WHERE night_id = ? AND unit_id = ?",
                [(x, y, night_id, unit_id) for unit_id, (x, y) in positions.items()],
            )

    def find_or_add_player(
        self, campaign_id: str, display_name: str, color_hex: str
    ) -> str:
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT id FROM player WHERE campaign_id = ? AND display_name = ?",
                (campaign_id, display_name),
            ).fetchone()
            if row is not None:
                return str(row["id"])
            player_id = self._new_id()
            conn.execute(
                "INSERT INTO player (id, campaign_id, display_name, color_hex) VALUES (?, ?, ?, ?)",
                (player_id, campaign_id, display_name, color_hex),
            )
        return player_id

    def set_unit_owner(self, unit_id: str, player_id: str | None) -> None:
        with self.transaction() as conn:
            cursor = conn.execute(
                "UPDATE unit SET player_id = ? WHERE id = ?", (player_id, unit_id)
            )
        if cursor.rowcount == 0:
            raise NotFoundError("unit not found")

    def unit_owners(self, night_id: str) -> dict[str, str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT u.id, p.display_name FROM night_unit nu JOIN unit u ON u.id = nu.unit_id "
                "JOIN player p ON p.id = u.player_id WHERE nu.night_id = ?",
                (night_id,),
            ).fetchall()
        return {str(row["id"]): str(row["display_name"]) for row in rows}

    def autosave(
        self,
        night_id: str,
        turns_completed: int,
        units: Sequence[UnitSave],
        enemies: Sequence[EnemySave],
        result: str | None,
        events: Sequence[tuple[int, str, str, dict[str, object], int]],
        board: Mapping[str, object] | None = None,
    ) -> None:
        with self.transaction() as conn:
            conn.executemany(
                "UPDATE night_unit SET hp_current = ?, x_cm = ?, y_cm = ?, cooldown = ?, "
                "status_json = ? WHERE night_id = ? AND unit_id = ?",
                [
                    (
                        u.hp_current,
                        u.x_cm,
                        u.y_cm,
                        u.cooldown,
                        json.dumps(list(u.status)),
                        night_id,
                        u.unit_id,
                    )
                    for u in units
                ],
            )
            conn.execute("DELETE FROM enemy WHERE night_id = ?", (night_id,))
            conn.executemany(
                "INSERT INTO enemy (id, night_id, type, part, hp, x_cm, y_cm, spawn_turn, "
                "status_json, intent_json, alive) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        f"{night_id}:{e.id}",
                        night_id,
                        e.type,
                        e.part,
                        max(0, e.hp),
                        e.x_cm,
                        e.y_cm,
                        e.spawn_turn,
                        json.dumps(list(e.status)),
                        None if e.intent is None else json.dumps(e.intent),
                        int(e.hp > 0),
                    )
                    for e in enemies
                ],
            )
            conn.executemany(
                "INSERT INTO turn_log (night_id, turn, phase, event_type, payload_json, t_ms, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        night_id,
                        turn,
                        phase,
                        event_type,
                        json.dumps(payload),
                        t_ms,
                        self._now_iso(),
                    )
                    for turn, phase, event_type, payload, t_ms in events
                ],
            )
            conn.execute(
                "UPDATE night SET turns_completed = ?, result = ?, ended_at = ?, board_json = ? "
                "WHERE id = ?",
                (
                    turns_completed,
                    result,
                    None if result is None else self._now_iso(),
                    None if board is None else json.dumps(board),
                    night_id,
                ),
            )

    def saved_night(self, night_id: str) -> SavedNight | None:
        with self._lock:
            night = self._conn.execute(
                "SELECT turns_completed, result, board_json FROM night WHERE id = ?",
                (night_id,),
            ).fetchone()
            if night is None:
                raise NotFoundError("night not found")
            if int(night["turns_completed"]) == 0 or night["result"] is not None:
                return None
            unit_rows = self._conn.execute(
                "SELECT unit_id, hp_current, x_cm, y_cm, cooldown, status_json FROM night_unit "
                "WHERE night_id = ?",
                (night_id,),
            ).fetchall()
            enemy_rows = self._conn.execute(
                "SELECT id, type, part, hp, x_cm, y_cm, spawn_turn, intent_json, status_json "
                "FROM enemy WHERE night_id = ? ORDER BY rowid",
                (night_id,),
            ).fetchall()
        board = json.loads(night["board_json"]) if night["board_json"] else {}
        if not isinstance(board, dict):
            raise StoreError("saved board is not an object")
        prefix = f"{night_id}:"
        return SavedNight(
            turns_completed=int(night["turns_completed"]),
            board=board,
            units={
                str(row["unit_id"]): UnitSave(
                    unit_id=str(row["unit_id"]),
                    hp_current=int(row["hp_current"]),
                    x_cm=float(row["x_cm"]),
                    y_cm=float(row["y_cm"]),
                    cooldown=int(row["cooldown"]),
                    status=tuple(str(s) for s in json.loads(row["status_json"])),
                )
                for row in unit_rows
            },
            enemies=tuple(
                EnemySave(
                    id=str(row["id"]).removeprefix(prefix),
                    type=str(row["type"]),
                    part=None if row["part"] is None else str(row["part"]),
                    hp=int(row["hp"]),
                    x_cm=float(row["x_cm"]),
                    y_cm=float(row["y_cm"]),
                    spawn_turn=int(row["spawn_turn"]),
                    intent=None
                    if row["intent_json"] is None
                    else json.loads(row["intent_json"]),
                    status=tuple(str(s) for s in json.loads(row["status_json"])),
                )
                for row in enemy_rows
            ),
        )

    def log_turn(
        self,
        night_id: str,
        turn: int,
        phase: str,
        event_type: str,
        payload: dict[str, object],
        t_ms: int,
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO turn_log (night_id, turn, phase, event_type, payload_json, t_ms, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    night_id,
                    turn,
                    phase,
                    event_type,
                    json.dumps(payload),
                    t_ms,
                    self._now_iso(),
                ),
            )

    def turn_log_count(self, night_id: str, event_type: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM turn_log WHERE night_id = ? AND event_type = ?",
                (night_id, event_type),
            ).fetchone()
        return int(row[0])

    def find_sprite(self, cache_key: str) -> SpriteRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, cache_key, path, palette_version, prompt_version, source_response_id "
                "FROM sprite WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        return self._sprite_from_row(row)

    def get_sprite(self, sprite_id: str) -> SpriteRecord:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, cache_key, path, palette_version, prompt_version, source_response_id "
                "FROM sprite WHERE id = ?",
                (sprite_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError("sprite not found")
        return self._sprite_from_row(row)

    def _sprite_from_row(self, row: sqlite3.Row) -> SpriteRecord:
        sprite_path = self._sprite_file(str(row["path"]))
        response = row["source_response_id"]
        return SpriteRecord(
            id=str(row["id"]),
            cache_key=str(row["cache_key"]),
            path=sprite_path,
            palette_version=str(row["palette_version"]),
            prompt_version=str(row["prompt_version"]),
            source_response_id=None if response is None else str(response),
        )

    def save_sprite(
        self,
        cache_key: str,
        png: bytes,
        palette_version: str,
        prompt_version: str,
        source_response_id: str | None,
    ) -> SpriteRecord:
        existing = self.find_sprite(cache_key)
        if existing is not None:
            return existing
        sprite_id = self._new_id()
        directory = self._data_root / SPRITES_DIR_NAME
        directory.mkdir(parents=True, exist_ok=True)
        sprite_path = directory / f"{_parse_uuid(sprite_id)}.png"
        sprite_path.write_bytes(png)
        try:
            with self.transaction() as conn:
                conn.execute(
                    "INSERT INTO sprite (id, cache_key, path, palette_version, prompt_version, "
                    "source_response_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        sprite_id,
                        cache_key,
                        sprite_path.relative_to(self._data_root).as_posix(),
                        palette_version,
                        prompt_version,
                        source_response_id,
                        self._now_iso(),
                    ),
                )
        except BaseException:
            sprite_path.unlink(missing_ok=True)
            raise
        return SpriteRecord(
            sprite_id,
            cache_key,
            sprite_path,
            palette_version,
            prompt_version,
            source_response_id,
        )

    def set_unit_sprite(self, unit_id: str, sprite_id: str) -> None:
        with self.transaction() as conn:
            cursor = conn.execute(
                "UPDATE unit SET sprite_id = ? WHERE id = ?", (sprite_id, unit_id)
            )
        if cursor.rowcount == 0:
            raise NotFoundError("unit not found")

    def sprite_png(self, sprite_id: str) -> bytes:
        return self.get_sprite(sprite_id).path.read_bytes()

    def style_anchor(self, campaign_id: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT style_anchor_sprite_id FROM campaign WHERE id = ?",
                (campaign_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError("campaign not found")
        value = row[0]
        return None if value is None else str(value)

    def set_style_anchor_if_missing(self, campaign_id: str, sprite_id: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "UPDATE campaign SET style_anchor_sprite_id = ? "
                "WHERE id = ? AND style_anchor_sprite_id IS NULL",
                (sprite_id, campaign_id),
            )

    def set_setting(self, key: str, value: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def get_preference(self, key: str) -> SettingValue:
        default = _known_setting(key)
        stored = self.get_setting(key)
        if stored is None:
            return default
        try:
            return _validated_setting(key, json.loads(stored))
        except (ValueError, StoreError):
            return default

    def set_preference(self, key: str, value: SettingValue) -> None:
        _known_setting(key)
        checked = _validated_setting(key, value)
        self.set_setting(key, json.dumps(checked))

    def all_preferences(self) -> dict[str, SettingValue]:
        return {key: self.get_preference(key) for key in SETTING_DEFAULTS}

    def get_progression(self, campaign_id: str) -> Progression:
        with self._lock:
            row = self._conn.execute(
                "SELECT barrio_level, nights_survived FROM campaign WHERE id = ?",
                (campaign_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError("campaign not found")
        return Progression(int(row["barrio_level"]), int(row["nights_survived"]))

    def set_progression(
        self, campaign_id: str, barrio_level: int, nights_survived: int
    ) -> None:
        if not 0 <= barrio_level <= BARRIO_LEVEL_MAX or nights_survived < 0:
            raise StoreError("progression out of range")
        with self.transaction() as conn:
            cursor = conn.execute(
                "UPDATE campaign SET barrio_level = ?, nights_survived = ? WHERE id = ?",
                (barrio_level, nights_survived, campaign_id),
            )
        if cursor.rowcount == 0:
            raise NotFoundError("campaign not found")

    def get_unit_progress(self, unit_id: str) -> UnitProgress:
        with self._lock:
            row = self._conn.execute(
                "SELECT badges_json, scars_json FROM unit WHERE id = ?", (unit_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError("unit not found")
        return _progress_from_row(row)

    def set_unit_progress(
        self, unit_id: str, badges: Sequence[str], scars: Sequence[str]
    ) -> UnitProgress:
        progress = UnitProgress(_progress_ids(badges), _progress_ids(scars))
        with self.transaction() as conn:
            cursor = conn.execute(
                "UPDATE unit SET badges_json = ?, scars_json = ?, scars = ? WHERE id = ?",
                (
                    json.dumps(list(progress.badges)),
                    json.dumps(list(progress.scars)),
                    len(progress.scars),
                    unit_id,
                ),
            )
        if cursor.rowcount == 0:
            raise NotFoundError("unit not found")
        return progress

    def save_recap(self, campaign_id: str, text: str, source: str) -> SavedRecap:
        if source not in RECAP_SOURCES:
            raise StoreError("unknown recap source")
        if not 1 <= len(text) <= RECAP_TEXT_MAX:
            raise StoreError("recap text length out of range")
        recap = SavedRecap(campaign_id, text, source, self._now_iso())
        with self.transaction() as conn:
            known = conn.execute(
                "SELECT 1 FROM campaign WHERE id = ?", (campaign_id,)
            ).fetchone()
            if known is None:
                raise NotFoundError("campaign not found")
            conn.execute(
                "INSERT INTO campaign_recap (campaign_id, text, source, created_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(campaign_id) DO UPDATE SET "
                "text = excluded.text, source = excluded.source, "
                "created_at = excluded.created_at",
                (campaign_id, text, source, recap.created_at),
            )
        return recap

    def get_recap(self, campaign_id: str) -> SavedRecap | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT campaign_id, text, source, created_at FROM campaign_recap "
                "WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
        if row is None:
            return None
        return SavedRecap(
            str(row["campaign_id"]),
            str(row["text"]),
            str(row["source"]),
            str(row["created_at"]),
        )

    def clear_recap(self, campaign_id: str) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM campaign_recap WHERE campaign_id = ?", (campaign_id,)
            )
        return cursor.rowcount > 0

    def campaign_units(self, campaign_id: str) -> list[StoredUnit]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT u.id, u.object_signature_id, u.name, u.class, u.hp_max, u.atk, "
                "u.move_class, u.range_class, u.power_id, u.power_name_tl, u.card_text_tl, "
                "u.card_text_en, u.sprite_id, u.badges_json, u.scars_json, os.label, "
                "os.hist_json, os.area_cm2, os.aspect, os.ref_crop_path "
                "FROM unit u JOIN object_signature os ON os.id = u.object_signature_id "
                "WHERE u.campaign_id = ? ORDER BY u.rowid",
                (campaign_id,),
            ).fetchall()
        return [self._stored_unit(row) for row in rows]

    def _stored_unit(self, row: sqlite3.Row) -> StoredUnit:
        crop = (self._data_root / str(row["ref_crop_path"])).resolve()
        if not crop.is_relative_to(self._data_root):
            raise UnsafePathError("stored crop path escapes the data root")
        sprite = row["sprite_id"]
        return StoredUnit(
            unit_id=str(row["id"]),
            signature_id=str(row["object_signature_id"]),
            card=_card_from_row(row),
            sprite_id=None if sprite is None else str(sprite),
            progress=_progress_from_row(row),
            signature=StoredSignature(
                label=str(row["label"]),
                histogram=tuple(float(v) for v in json.loads(str(row["hist_json"]))),
                area_cm2=float(row["area_cm2"]),
                aspect=float(row["aspect"]),
                ref_crop_path=crop,
            ),
        )

    def set_map_image(self, campaign_id: str, path: Path | None) -> None:
        stored: str | None = None
        if path is not None:
            resolved = path.resolve()
            if not resolved.is_relative_to(self.campaign_dir(campaign_id)):
                raise UnsafePathError("map image must live in the campaign folder")
            stored = resolved.relative_to(self._data_root).as_posix()
        with self.transaction() as conn:
            cursor = conn.execute(
                "UPDATE campaign SET map_image_path = ? WHERE id = ?",
                (stored, campaign_id),
            )
        if cursor.rowcount == 0:
            raise NotFoundError("campaign not found")

    def get_map_image(self, campaign_id: str) -> Path | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT map_image_path FROM campaign WHERE id = ?", (campaign_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError("campaign not found")
        if row[0] is None:
            return None
        resolved = (self._data_root / str(row[0])).resolve()
        if not resolved.is_relative_to(self.campaign_dir(campaign_id)):
            raise UnsafePathError("stored map path escapes the campaign folder")
        return resolved


def _card_values(card: CardFields) -> tuple[object, ...]:
    return (
        card.name,
        card.unit_class.value,
        card.hp_max,
        card.atk,
        card.move_class.value,
        card.range_class.value,
        card.power_id.value,
        card.power_name_tl,
        card.card_text_tl,
        card.card_text_en,
    )


def _known_setting(key: str) -> SettingValue:
    if key not in SETTING_DEFAULTS:
        raise StoreError("unknown setting")
    return SETTING_DEFAULTS[key]


def _validated_setting(key: str, value: object) -> SettingValue:
    default = SETTING_DEFAULTS[key]
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
    elif key == "camera_device":
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    elif key in SETTING_CHOICES:
        if isinstance(value, str) and value in SETTING_CHOICES[key]:
            return value
    elif isinstance(value, str) and 1 <= len(value) <= MIC_DEVICE_MAX:
        return value
    raise StoreError("invalid value for setting")


def _progress_ids(ids: Sequence[str]) -> tuple[str, ...]:
    unique = tuple(dict.fromkeys(ids))
    if len(unique) > PROGRESS_LIST_MAX or not all(
        PROGRESS_ID_PATTERN.fullmatch(item) for item in unique
    ):
        raise StoreError("invalid progression ids")
    return unique


def _json_ids(raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    try:
        parsed = json.loads(str(raw))
    except (ValueError, TypeError):
        logger.warning("progress ids are corrupt, using none")
        return ()
    if not isinstance(parsed, list):
        return ()
    return tuple(str(item) for item in parsed)


def _progress_from_row(row: sqlite3.Row) -> UnitProgress:
    return UnitProgress(_json_ids(row["badges_json"]), _json_ids(row["scars_json"]))


def _night_from_row(row: sqlite3.Row) -> NightRecord:
    flags = json.loads(str(row["flags_json"]))
    return NightRecord(
        id=str(row["id"]),
        campaign_id=str(row["campaign_id"]),
        number=int(row["number"]),
        started_at=str(row["started_at"]),
        flags=flags if isinstance(flags, dict) else {},
    )


def _card_from_row(row: sqlite3.Row) -> CardFields:
    return CardFields(
        name=str(row["name"]),
        unit_class=UnitClass(row["class"]),
        hp_max=int(row["hp_max"]),
        atk=int(row["atk"]),
        move_class=MoveClass(row["move_class"]),
        range_class=RangeClass(row["range_class"]),
        power_id=PowerId(row["power_id"]),
        power_name_tl=str(row["power_name_tl"] or ""),
        card_text_tl=str(row["card_text_tl"] or ""),
        card_text_en=str(row["card_text_en"] or ""),
    )


def _unit_from_row(row: sqlite3.Row) -> UnitRecord:
    sprite = row["sprite_id"]
    return UnitRecord(
        unit_id=str(row["id"]),
        signature_id=str(row["object_signature_id"]),
        sam_object_id=int(row["sam_object_id"]),
        card=_card_from_row(row),
        hp_current=int(row["hp_current"]),
        x_cm=float(row["x_cm"]),
        y_cm=float(row["y_cm"]),
        sprite_id=None if sprite is None else str(sprite),
    )


def _parse_uuid(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as error:
        raise UnsafePathError("campaign id must be a UUID") from error


def _campaign_from_row(row: sqlite3.Row) -> Campaign:
    return Campaign(
        id=str(row["id"]),
        name=str(row["name"]),
        difficulty=Difficulty(row["difficulty"]),
        barrio_level=int(row["barrio_level"]),
        nights_survived=int(row["nights_survived"]),
        created_at=str(row["created_at"]),
    )

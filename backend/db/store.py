import json
import math
import sqlite3
import threading
import uuid
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final

from rules.units import Difficulty, MoveClass, PowerId, RangeClass, UnitClass

SCHEMA_VERSION: Final = 1
SCHEMA_PATH: Final = Path(__file__).with_name("schema.sql")
COST_SCALE: Final = 100_000_000
CAMPAIGN_PAGE_MAX: Final = 50
CAMPAIGNS_DIR_NAME: Final = "campaigns"
BASELINE_FILE_NAME: Final = "baseline.png"
HOMOGRAPHY_SIZE: Final = 9
REF_CROP_DIR_NAME: Final = "crops"
SETUP_TURN: Final = 0

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
        script = SCHEMA_PATH.read_text(encoding="utf-8")
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

    def delete_campaign_rows(self, campaign_id: str) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM campaign WHERE id = ?", (campaign_id,))
        return cursor.rowcount > 0

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

    def set_setting(self, key: str, value: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )


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


def _night_from_row(row: sqlite3.Row) -> NightRecord:
    flags = json.loads(str(row["flags_json"]))
    return NightRecord(
        id=str(row["id"]),
        campaign_id=str(row["campaign_id"]),
        number=int(row["number"]),
        started_at=str(row["started_at"]),
        flags=flags if isinstance(flags, dict) else {},
    )


def _unit_from_row(row: sqlite3.Row) -> UnitRecord:
    card = CardFields(
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
    sprite = row["sprite_id"]
    return UnitRecord(
        unit_id=str(row["id"]),
        signature_id=str(row["object_signature_id"]),
        sam_object_id=int(row["sam_object_id"]),
        card=card,
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

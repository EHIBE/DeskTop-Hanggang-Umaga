import sqlite3
import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Final

SCHEMA_VERSION: Final = 1
SCHEMA_PATH: Final = Path(__file__).with_name("schema.sql")
COST_SCALE: Final = 100_000_000
CAMPAIGN_PAGE_MAX: Final = 50

Clock = Callable[[], datetime]
IdFactory = Callable[[], str]


class StoreError(Exception):
    pass


class SchemaVersionError(StoreError):
    pass


class NotFoundError(StoreError):
    pass


class Difficulty(StrEnum):
    MADALI = "madali"
    NORMAL = "normal"
    MAHIRAP = "mahirap"


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
        self._conn = sqlite3.connect(
            path, isolation_level=None, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._migrate()

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

    def set_setting(self, key: str, value: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )


def _campaign_from_row(row: sqlite3.Row) -> Campaign:
    return Campaign(
        id=str(row["id"]),
        name=str(row["name"]),
        difficulty=Difficulty(row["difficulty"]),
        barrio_level=int(row["barrio_level"]),
        nights_survived=int(row["nights_survived"]),
        created_at=str(row["created_at"]),
    )

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Final


class ConfigError(Exception):
    pass


class MetaModel(StrEnum):
    SPARK = "muse-spark-1.3"
    SAM = "sam-3.1"
    IMAGE = "muse-image-1.0"
    VOICE = "muse-voice-transcribe-1.0"
    FILES = "files"


class CallKind(StrEnum):
    SPARK = "spark"
    SAM_IMAGE = "sam_image"
    SAM_VIDEO = "sam_video"
    IMAGE = "image"
    FILES = "files"


META_BASE_URL: Final = "https://api.meta.ai/v1"
META_REALTIME_URL: Final = "wss://api.meta.ai/v1/asr/realtime"

PX_PER_CM: Final = 20
DEFAULT_PLAY_W_CM: Final = 60.0
DEFAULT_PLAY_H_CM: Final = 40.0
A4_W_CM: Final = 21.0
A4_H_CM: Final = 29.7
CAMERA_CAPTURE_SIZE: Final = (1920, 1080)
CAMERA_MIN_SIZE: Final = (1280, 720)

STREAM_WIDTH_PX: Final = 960
STREAM_JPEG_QUALITY: Final = 70
STREAM_FPS: Final = 25

TRACKING_WIDTH_PX: Final = 640
POSITION_EMA_ALPHA: Final = 0.4
SAM_ACCEPT_CONFIDENCE: Final = 0.5
SAM_TRACKER_IOU_ACCEPT: Final = 0.3
HISTOGRAM_MATCH_MAX: Final = 0.35
RECOVERY_SEARCH_RADIUS_CM: Final = 15.0
REANCHOR_BOX_PADDING: Final = 0.20
SPRITE_CROP_PADDING: Final = 0.15
TRACKER_LOSS_SAM_DELAY_S: Final = 5.0
MAX_BETWEEN_TURN_SAM_CALLS: Final = 3
HANDS_OFF_WAIT_S: Final = 3.0
SUMMON_SNAPSHOT_DELAY_S: Final = 1.0
STACK_OVERLAP: Final = 0.60
STILL_FRAME_MEAN_DIFF_MAX: Final = 6.0
BRIGHTNESS_CHANGE_ALERT: Final = 0.30
CAMERA_MOVED_CM: Final = 2.0
CHROMA_KEY_HSV_DISTANCE: Final = 40
SPRITE_SIZE_PX: Final = 48
SPRITE_SOURCE_LONG_SIDE_PX: Final = 512
SPRITE_ALPHA_MIN: Final = 0.15
SPRITE_ALPHA_MAX: Final = 0.90
SIGNATURE_MATCH_MIN: Final = 0.8
SIGNATURE_TIE_MARGIN: Final = 0.05
VOICE_CLAIM_FUZZY_RATIO: Final = 0.75
GRAMMAR_FUZZY_CUTOFF: Final = 75

TIMEOUT_S: Final[Mapping[CallKind, float]] = {
    CallKind.SPARK: 20.0,
    CallKind.SAM_IMAGE: 10.0,
    CallKind.SAM_VIDEO: 120.0,
    CallKind.IMAGE: 45.0,
    CallKind.FILES: 60.0,
}
MAX_RETRIES: Final = 2
RETRY_BACKOFF_S: Final = (0.5, 1.0)
RETRY_JITTER_MAX_S: Final = 0.25
BREAKER_FAILURE_THRESHOLD: Final = 3
BREAKER_OPEN_S: Final = 120.0
END_TURN_SNAPSHOT_TIMEOUT_S: Final = 10.0
VOICE_CLAIM_TIMEOUT_S: Final = 60.0
NARRATION_TIMEOUT_S: Final = 20.0

COST_WARN_USD: Final = Decimal(90)
COST_STOP_USD: Final = Decimal(120)
NIGHT_COST_ALERT_USD: Final = Decimal(3)

SPARK_INPUT_PER_TOKEN_USD: Final = Decimal("1.25") / Decimal(1_000_000)
SPARK_CACHED_INPUT_PER_TOKEN_USD: Final = Decimal("0.15") / Decimal(1_000_000)
SPARK_OUTPUT_PER_TOKEN_USD: Final = Decimal("4.25") / Decimal(1_000_000)
SAM_PER_IMAGE_USD: Final = Decimal("2.50") / Decimal(1_000)
SAM_PER_VIDEO_FRAME_USD: Final = Decimal("0.20") / Decimal(1_000)
SAM_VIDEO_MIN_FRAMES: Final = 50
IMAGE_PER_IMAGE_USD: Final = Decimal("0.01")
VOICE_PER_SECOND_USD: Final = Decimal("0.18") / Decimal(3_600)

UNMETERED_CALL_ESTIMATE_USD: Final[Mapping[CallKind, Decimal]] = {
    CallKind.SPARK: Decimal("0.02"),
    CallKind.SAM_IMAGE: Decimal("0.0025"),
    CallKind.SAM_VIDEO: Decimal("0.24"),
    CallKind.IMAGE: Decimal("0.01"),
    CallKind.FILES: Decimal(0),
}

PALETTE_VERSION: Final = "gabi16-v1"
PROMPT_VERSION: Final = "sprite-v1"

DEFAULT_PORT: Final = 8765
MIN_TOKEN_LENGTH: Final = 32
DATA_DIR_NAME: Final = "DeskTop"
DATABASE_FILE_NAME: Final = "desktop.sqlite"


@dataclass(frozen=True)
class AppSettings:
    token: str = field(repr=False)
    data_dir: Path
    port: int
    api_key: str | None = field(repr=False)

    @property
    def database_path(self) -> Path:
        return self.data_dir / DATABASE_FILE_NAME


def _default_data_dir(env: Mapping[str, str]) -> Path:
    appdata = env.get("APPDATA", "").strip()
    if not appdata:
        raise ConfigError("DESKTOP_DATA_DIR and APPDATA are both unset")
    return Path(appdata) / DATA_DIR_NAME


def _parse_port(raw: str) -> int:
    if not raw.isdigit():
        raise ConfigError("DESKTOP_PORT must be an integer")
    port = int(raw)
    if not 1024 <= port <= 65535:
        raise ConfigError("DESKTOP_PORT must be between 1024 and 65535")
    return port


def load_settings(env: Mapping[str, str]) -> AppSettings:
    token = env.get("DESKTOP_TOKEN", "").strip()
    if len(token) < MIN_TOKEN_LENGTH:
        raise ConfigError("DESKTOP_TOKEN is missing or too short")
    raw_data_dir = env.get("DESKTOP_DATA_DIR", "").strip()
    data_dir = Path(raw_data_dir) if raw_data_dir else _default_data_dir(env)
    port = _parse_port(env.get("DESKTOP_PORT", "").strip() or str(DEFAULT_PORT))
    api_key = env.get("MODEL_API_KEY", "").strip() or None
    return AppSettings(
        token=token, data_dir=data_dir.resolve(), port=port, api_key=api_key
    )

import base64
import json
import mimetypes
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

from config import DATA_DIR_NAME, DATABASE_FILE_NAME
from db.store import Store
from meta_client import CostMeter, MetaClient, Usage, create_openai_client

BACKEND_DIR: Final = Path(__file__).resolve().parent.parent
REPO_DIR: Final = BACKEND_DIR.parent
FIXTURES_DIR: Final = REPO_DIR / "fixtures"
SECRET_KEYS: Final = frozenset(
    {"authorization", "api_key", "accesstoken", "access_token"}
)
BEARER_PREFIX: Final = "bearer "
REDACTED: Final = "[redacted]"

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


class SmokeError(Exception):
    pass


@dataclass(frozen=True)
class SmokeContext:
    client: MetaClient
    store: Store
    api_key: str


def open_smoke_context() -> SmokeContext:
    load_dotenv(BACKEND_DIR / ".env")
    api_key = os.environ.get("MODEL_API_KEY", "").strip()
    if not api_key:
        raise SmokeError("MODEL_API_KEY is empty. Put the key in backend/.env first.")
    raw_data_dir = os.environ.get("DESKTOP_DATA_DIR", "").strip()
    appdata = os.environ.get("APPDATA", "").strip()
    if not raw_data_dir and not appdata:
        raise SmokeError("Set DESKTOP_DATA_DIR or APPDATA so api_usage can be logged.")
    data_dir = Path(raw_data_dir) if raw_data_dir else Path(appdata) / DATA_DIR_NAME
    store = Store(data_dir / DATABASE_FILE_NAME)
    client = MetaClient(create_openai_client(api_key), CostMeter(store))
    return SmokeContext(client=client, store=store, api_key=api_key)


def scrub(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return {
            key: REDACTED if key.lower() in SECRET_KEYS else scrub(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, str) and value.lower().startswith(BEARER_PREFIX):
        return REDACTED
    return value


def assert_no_secret(text: str, secret: str) -> None:
    if secret and secret in text:
        raise SmokeError("refusing to write a fixture that contains the API key")


def save_json_fixture(name: str, data: JsonValue, secret: str) -> Path:
    text = json.dumps(scrub(data), indent=2, ensure_ascii=False)
    assert_no_secret(text, secret)
    return _write_fixture(name, text.encode("utf-8"))


def save_jsonl_fixture(name: str, rows: Sequence[JsonValue], secret: str) -> Path:
    text = "\n".join(json.dumps(scrub(row), ensure_ascii=False) for row in rows) + "\n"
    assert_no_secret(text, secret)
    return _write_fixture(name, text.encode("utf-8"))


def save_text_fixture(name: str, text: str, secret: str) -> Path:
    assert_no_secret(text, secret)
    return _write_fixture(name, text.encode("utf-8"))


def save_binary_fixture(name: str, data: bytes) -> Path:
    return _write_fixture(name, data)


def _write_fixture(name: str, data: bytes) -> Path:
    target = (FIXTURES_DIR / name).resolve()
    if target.parent != FIXTURES_DIR.resolve():
        raise SmokeError("fixture name must be a plain file name")
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def image_data_url(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if mime not in ("image/jpeg", "image/png"):
        raise SmokeError("image must be a .jpg or .png file")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def to_json(model: object) -> JsonValue:
    dump = getattr(model, "model_dump", None)
    if dump is None:
        raise SmokeError("response object has no model_dump")
    data: JsonValue = json.loads(json.dumps(dump(mode="json"), default=str))
    return data


def usage_from_responses(usage: Mapping[str, JsonValue] | None) -> Usage:
    if usage is None:
        return Usage()
    details = usage.get("input_tokens_details")
    cached = details.get("cached_tokens", 0) if isinstance(details, dict) else 0
    return Usage(
        input_tokens=_as_int(usage.get("input_tokens")),
        cached_tokens=_as_int(cached),
        output_tokens=_as_int(usage.get("output_tokens")),
    )


def usage_from_chat(usage: Mapping[str, JsonValue] | None) -> Usage:
    if usage is None:
        return Usage()
    details = usage.get("prompt_tokens_details")
    cached = details.get("cached_tokens", 0) if isinstance(details, dict) else 0
    return Usage(
        input_tokens=_as_int(usage.get("prompt_tokens")),
        cached_tokens=_as_int(cached),
        output_tokens=_as_int(usage.get("completion_tokens")),
    )


def _as_int(value: JsonValue) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value

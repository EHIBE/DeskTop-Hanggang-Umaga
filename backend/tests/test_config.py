from decimal import Decimal
from pathlib import Path

import pytest

from config import (
    COST_STOP_USD,
    COST_WARN_USD,
    DATABASE_FILE_NAME,
    TIMEOUT_S,
    CallKind,
    ConfigError,
    load_settings,
)

TOKEN = "a" * 64


def test_load_settings_reads_every_value(tmp_path: Path) -> None:
    settings = load_settings(
        {
            "DESKTOP_TOKEN": TOKEN,
            "DESKTOP_DATA_DIR": str(tmp_path),
            "DESKTOP_PORT": "9000",
            "MODEL_API_KEY": "key",
        }
    )
    assert settings.token == TOKEN
    assert settings.data_dir == tmp_path.resolve()
    assert settings.port == 9000
    assert settings.api_key == "key"
    assert settings.database_path == tmp_path.resolve() / DATABASE_FILE_NAME


def test_missing_token_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_settings({"DESKTOP_DATA_DIR": str(tmp_path)})


def test_blank_token_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_settings({"DESKTOP_TOKEN": "   ", "DESKTOP_DATA_DIR": str(tmp_path)})


def test_short_token_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_settings({"DESKTOP_TOKEN": "a" * 31, "DESKTOP_DATA_DIR": str(tmp_path)})


def test_repr_hides_secrets(tmp_path: Path) -> None:
    settings = load_settings(
        {
            "DESKTOP_TOKEN": TOKEN,
            "DESKTOP_DATA_DIR": str(tmp_path),
            "MODEL_API_KEY": "sk-secret",
        }
    )
    assert TOKEN not in repr(settings)
    assert "sk-secret" not in repr(settings)


def test_data_dir_defaults_to_appdata(tmp_path: Path) -> None:
    settings = load_settings({"DESKTOP_TOKEN": TOKEN, "APPDATA": str(tmp_path)})
    assert settings.data_dir == (tmp_path / "DeskTop").resolve()


def test_missing_data_dir_and_appdata_raises() -> None:
    with pytest.raises(ConfigError):
        load_settings({"DESKTOP_TOKEN": TOKEN})


def test_default_port_and_missing_key(tmp_path: Path) -> None:
    settings = load_settings(
        {"DESKTOP_TOKEN": TOKEN, "DESKTOP_DATA_DIR": str(tmp_path)}
    )
    assert settings.port == 8765
    assert settings.api_key is None


def test_blank_port_uses_default(tmp_path: Path) -> None:
    settings = load_settings(
        {"DESKTOP_TOKEN": TOKEN, "DESKTOP_DATA_DIR": str(tmp_path), "DESKTOP_PORT": " "}
    )
    assert settings.port == 8765


@pytest.mark.parametrize("raw_port", ["abc", "80", "70000", "-1"])
def test_invalid_port_raises(tmp_path: Path, raw_port: str) -> None:
    with pytest.raises(ConfigError):
        load_settings(
            {
                "DESKTOP_TOKEN": TOKEN,
                "DESKTOP_DATA_DIR": str(tmp_path),
                "DESKTOP_PORT": raw_port,
            }
        )


def test_documented_timeouts_and_budget() -> None:
    assert TIMEOUT_S[CallKind.SPARK] == 20.0
    assert TIMEOUT_S[CallKind.SAM_IMAGE] == 10.0
    assert TIMEOUT_S[CallKind.SAM_VIDEO] == 120.0
    assert TIMEOUT_S[CallKind.IMAGE] == 45.0
    assert TIMEOUT_S[CallKind.FILES] == 60.0
    assert COST_WARN_USD == Decimal(90)
    assert COST_STOP_USD == Decimal(120)


def test_dev_flag(tmp_path: Path) -> None:
    env = {"DESKTOP_TOKEN": TOKEN, "DESKTOP_DATA_DIR": str(tmp_path)}
    assert load_settings({**env, "DESKTOP_DEV": "1"}).is_dev
    assert not load_settings(env).is_dev

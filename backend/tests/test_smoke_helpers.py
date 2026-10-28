import pytest

from meta_client import Usage
from smoke import (
    JsonValue,
    SmokeError,
    assert_no_secret,
    save_text_fixture,
    scrub,
    usage_from_chat,
    usage_from_responses,
)
from smoke.sam import build_prompt, parse_box
from smoke.voice import VoiceRun, handshake


def test_scrub_removes_secret_keys_and_bearer_values() -> None:
    data: JsonValue = {
        "authorization": {"accessToken": "Bearer abc"},
        "nested": [{"api_key": "k", "note": "Bearer xyz", "ok": "fine"}],
    }
    assert scrub(data) == {
        "authorization": "[redacted]",
        "nested": [{"api_key": "[redacted]", "note": "[redacted]", "ok": "fine"}],
    }


def test_assert_no_secret_blocks_the_key() -> None:
    with pytest.raises(SmokeError):
        assert_no_secret('{"text": "sk-live-123"}', "sk-live-123")
    assert_no_secret('{"text": "safe"}', "sk-live-123")


@pytest.mark.parametrize("name", ["../escape.txt", "sub/dir.txt"])
def test_fixture_names_cannot_escape_the_folder(name: str) -> None:
    with pytest.raises(SmokeError):
        save_text_fixture(name, "x", "secret")


def test_usage_from_responses_reads_cached_tokens() -> None:
    usage: dict[str, JsonValue] = {
        "input_tokens": 4500,
        "input_tokens_details": {"cached_tokens": 1200},
        "output_tokens": 850,
    }
    assert usage_from_responses(usage) == Usage(
        input_tokens=4500, cached_tokens=1200, output_tokens=850
    )
    assert usage_from_responses(None) == Usage()


def test_usage_from_chat_reads_prompt_tokens() -> None:
    usage: dict[str, JsonValue] = {
        "prompt_tokens": 100,
        "prompt_tokens_details": {"cached_tokens": 40},
        "completion_tokens": 20,
    }
    assert usage_from_chat(usage) == Usage(
        input_tokens=100, cached_tokens=40, output_tokens=20
    )


def test_sam_box_prompt_uses_the_wire_grammar() -> None:
    prompt = build_prompt((1200, 800), [parse_box("1,400,300,490,400")])
    assert prompt.startswith("<0f>1<|box;")
    assert "w=1200;h=800" in prompt


@pytest.mark.parametrize("raw", ["1,2,3", "17,0,0,10,10", "1,10,10,5,20", "a,1,2,3,4"])
def test_sam_box_argument_is_validated(raw: str) -> None:
    with pytest.raises(Exception, match="box|id"):
        parse_box(raw)


def test_voice_handshake_extras_are_optional() -> None:
    with_extras = handshake(
        "key", VoiceRun(mode="DIARIZATION", seconds=5, with_extras=True)
    )
    plain = handshake("key", VoiceRun(mode="ENDPOINTING", seconds=5, with_extras=False))
    assert '"languageBias"' in with_extras
    assert '"keywords"' in with_extras
    assert '"languageBias"' not in plain
    assert '"mode": "ENDPOINTING"' in plain

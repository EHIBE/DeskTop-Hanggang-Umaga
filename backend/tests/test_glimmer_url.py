import pytest

from gm.glimmer import normalize_glimmer_url


@pytest.mark.parametrize(
    "url",
    [
        r"http://evil\@127.0.0.1",
        "http://u:p@127.0.0.1:11434",
        "http://127.0.0.1@evil",
        "http://localhost.evil.com",
        "http://127.0.0.1:11434?x=1",
        "http://127.0.0.1:11434#frag",
        "http://127.0.0.1 :11434",
        "https://127.0.0.1",
    ],
)
def test_unsafe_urls_are_rejected(url: str) -> None:
    assert normalize_glimmer_url(url) is None


def test_ipv6_loopback_is_kept() -> None:
    assert normalize_glimmer_url("http://[::1]:11434") == "http://[::1]:11434"


def test_url_is_rebuilt_without_trailing_slash() -> None:
    assert normalize_glimmer_url("http://localhost:11434/") == "http://localhost:11434"

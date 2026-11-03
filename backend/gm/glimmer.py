import logging
import os
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import urlsplit

import httpx2

from db.store import ApiUsageRecord
from gm.prompts import (
    BANTER_SPEAKERS,
    BANTER_SYSTEM_PROMPT,
    RECAP_SYSTEM_PROMPT,
    banter_input_text,
    recap_input_text,
)
from gm.schemas import ContentFilter, SchemaError, parse_recap, recap_json_schema

if TYPE_CHECKING:
    from gm.recap import NightSummary

logger = logging.getLogger("desktop.glimmer")

GLIMMER_URL_ENV: Final = "DESKTOP_GLIMMER_URL"
GLIMMER_MODEL_ENV: Final = "DESKTOP_GLIMMER_MODEL"
GLIMMER_DEFAULT_MODEL: Final = "muse-glimmer"
GLIMMER_KIND: Final = "glimmer"
GLIMMER_SOURCE: Final = "glimmer"
GLIMMER_TIMEOUT_S: Final = 8.0
GLIMMER_CHAT_PATH: Final = "/api/chat"
LOOPBACK_HOSTS: Final = frozenset({"127.0.0.1", "localhost", "::1"})
SITUATION_MAX: Final = 120
DIGIT_PATTERN: Final = re.compile(r"\d")


@dataclass(frozen=True)
class GlimmerText:
    text_tl: str
    text_en: str
    source: str = GLIMMER_SOURCE


def normalize_glimmer_url(raw: str | None) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    if "\\" in text or any(ch.isspace() for ch in text):
        _reject()
        return None
    try:
        parts = urlsplit(text)
        host = parts.hostname
        port = parts.port
    except ValueError:
        return None
    if (
        parts.scheme != "http"
        or host not in LOOPBACK_HOSTS
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or "?" in text
        or "#" in text
        or "@" in parts.netloc
    ):
        _reject()
        return None
    shown = f"[{host}]" if ":" in host else host
    base = f"http://{shown}" + (f":{port}" if port is not None else "")
    return base + parts.path.rstrip("/")


def _reject() -> None:
    logger.warning("glimmer url ignored, only local http addresses are allowed")


class GlimmerClient:
    def __init__(
        self,
        base_url: str,
        content: ContentFilter,
        log_usage: Callable[[ApiUsageRecord], None] | None = None,
        model: str = GLIMMER_DEFAULT_MODEL,
        timeout_s: float = GLIMMER_TIMEOUT_S,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._content = content
        self._log_usage = log_usage
        self._model = model
        self._timeout_s = timeout_s
        self._transport = transport

    async def recap(self, summary: "NightSummary") -> GlimmerText | None:
        return await self._write(RECAP_SYSTEM_PROMPT, recap_input_text(summary))

    async def banter(self, speaker: str, situation: str) -> GlimmerText | None:
        if speaker not in BANTER_SPEAKERS:
            return None
        prompt = banter_input_text(speaker, situation[:SITUATION_MAX])
        text = await self._write(BANTER_SYSTEM_PROMPT, prompt)
        if text is None:
            return None
        if DIGIT_PATTERN.search(text.text_tl) or DIGIT_PATTERN.search(text.text_en):
            logger.warning("glimmer banter rejected, it wrote a number")
            return None
        return text

    async def _write(self, system: str, user: str) -> GlimmerText | None:
        started = time.monotonic()
        raw = await self._chat(system, user)
        self._record(started, is_ok=raw is not None)
        if raw is None:
            return None
        try:
            draft = parse_recap(raw)
        except SchemaError:
            logger.warning("glimmer output failed validation")
            return None
        texts = (draft.recap_tl, draft.recap_en)
        if not all(self._content.is_safe_narration(text) for text in texts):
            logger.warning("glimmer output failed the safety filter")
            return None
        return GlimmerText(draft.recap_tl, draft.recap_en)

    async def _chat(self, system: str, user: str) -> str | None:
        body: dict[str, Any] = {
            "model": self._model,
            "stream": False,
            "format": recap_json_schema(),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            async with httpx2.AsyncClient(
                timeout=self._timeout_s,
                transport=self._transport,
                trust_env=False,
            ) as http:
                response = await http.post(
                    self._base_url + GLIMMER_CHAT_PATH, json=body
                )
                response.raise_for_status()
                payload = response.json()
            content = payload["message"]["content"]
        except (httpx2.HTTPError, ValueError, KeyError, TypeError):
            logger.warning("glimmer unavailable, using the next recap source")
            return None
        return content if isinstance(content, str) else None

    def _record(self, started: float, *, is_ok: bool) -> None:
        if self._log_usage is None:
            return
        self._log_usage(
            ApiUsageRecord(
                model=self._model,
                kind=GLIMMER_KIND,
                cost_usd=Decimal(0),
                ok=is_ok,
                latency_ms=round((time.monotonic() - started) * 1000),
            )
        )


def glimmer_from_env(
    content: ContentFilter,
    log_usage: Callable[[ApiUsageRecord], None] | None = None,
    environ: Mapping[str, str] | None = None,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> GlimmerClient | None:
    env = environ if environ is not None else os.environ
    base_url = normalize_glimmer_url(env.get(GLIMMER_URL_ENV))
    if base_url is None:
        return None
    model = env.get(GLIMMER_MODEL_ENV, "").strip() or GLIMMER_DEFAULT_MODEL
    return GlimmerClient(base_url, content, log_usage, model, transport=transport)

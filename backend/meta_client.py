import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime
from typing import Final, Protocol

import openai

from config import (
    BREAKER_FAILURE_THRESHOLD,
    BREAKER_OPEN_S,
    COST_STOP_USD,
    COST_WARN_USD,
    IMAGE_PER_IMAGE_USD,
    MAX_RETRIES,
    META_BASE_URL,
    RETRY_BACKOFF_S,
    RETRY_JITTER_MAX_S,
    SAM_PER_IMAGE_USD,
    SAM_PER_VIDEO_FRAME_USD,
    SAM_VIDEO_MIN_FRAMES,
    SPARK_CACHED_INPUT_PER_TOKEN_USD,
    SPARK_INPUT_PER_TOKEN_USD,
    SPARK_OUTPUT_PER_TOKEN_USD,
    TIMEOUT_S,
    UNMETERED_CALL_ESTIMATE_USD,
    VOICE_PER_SECOND_USD,
    CallKind,
    MetaModel,
)
from db.store import ApiUsageRecord

logger = logging.getLogger("desktop.meta")

HTTP_BAD_REQUEST: Final = 400
HTTP_PAYMENT_REQUIRED: Final = 402
HTTP_REQUEST_TIMEOUT: Final = 408
HTTP_CONFLICT: Final = 409
HTTP_TOO_MANY_REQUESTS: Final = 429
HTTP_SERVER_ERROR_MIN: Final = 500
CONTENT_POLICY_CODE: Final = "content_policy_violation"

MonotonicClock = Callable[[], float]
Sleeper = Callable[[float], Awaitable[None]]
JitterSource = Callable[[], float]


class MetaError(Exception):
    pass


class MetaUnavailableError(MetaError):
    pass


class BreakerOpenError(MetaUnavailableError):
    pass


class BudgetExceededError(MetaUnavailableError):
    pass


class MetaRequestError(MetaError):
    def __init__(self, message: str, *, is_content_policy: bool) -> None:
        super().__init__(message)
        self.is_content_policy = is_content_policy


class UsageLog(Protocol):
    def record_api_usage(self, record: ApiUsageRecord) -> None: ...

    def total_api_cost(self) -> Decimal: ...


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    images: int = 0
    frames: int = 0
    audio_seconds: int = 0


@dataclass(frozen=True)
class CallSpec:
    model: MetaModel
    kind: CallKind
    is_idempotent: bool


def price_usage(kind: CallKind, usage: Usage) -> Decimal:
    if kind is CallKind.SPARK:
        uncached = max(0, usage.input_tokens - usage.cached_tokens)
        return (
            uncached * SPARK_INPUT_PER_TOKEN_USD
            + usage.cached_tokens * SPARK_CACHED_INPUT_PER_TOKEN_USD
            + usage.output_tokens * SPARK_OUTPUT_PER_TOKEN_USD
        )
    if kind is CallKind.SAM_IMAGE:
        return usage.images * SAM_PER_IMAGE_USD
    if kind is CallKind.SAM_VIDEO:
        return max(usage.frames, SAM_VIDEO_MIN_FRAMES) * SAM_PER_VIDEO_FRAME_USD
    if kind is CallKind.IMAGE:
        return usage.images * IMAGE_PER_IMAGE_USD
    return Decimal(0)


def price_voice_seconds(seconds: int) -> Decimal:
    return max(0, seconds) * VOICE_PER_SECOND_USD


class CostMeter:
    def __init__(
        self,
        log: UsageLog,
        warn_usd: Decimal = COST_WARN_USD,
        stop_usd: Decimal = COST_STOP_USD,
    ) -> None:
        self._log = log
        self._warn_usd = warn_usd
        self._stop_usd = stop_usd
        self._spent = log.total_api_cost()
        self._is_forced_stop = False

    @property
    def spent_usd(self) -> Decimal:
        return self._spent

    @property
    def is_warning(self) -> bool:
        return self._spent >= self._warn_usd

    @property
    def is_stopped(self) -> bool:
        return self._is_forced_stop or self._spent >= self._stop_usd

    def ensure_can_spend(self) -> None:
        if not self.is_stopped:
            return
        logger.warning("paid call blocked by cost hard stop")
        raise BudgetExceededError("cost hard stop reached")

    def force_stop(self) -> None:
        if not self._is_forced_stop:
            logger.warning("credits exhausted, paid calls stopped")
        self._is_forced_stop = True

    def record(self, record: ApiUsageRecord) -> None:
        self._log.record_api_usage(record)
        was_warning = self.is_warning
        self._spent += record.cost_usd
        if self.is_warning and not was_warning:
            logger.warning("cost warning threshold reached")


@dataclass
class CircuitBreaker:
    clock: MonotonicClock
    threshold: int = BREAKER_FAILURE_THRESHOLD
    open_s: float = BREAKER_OPEN_S
    _failures: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        return self.clock() - self._opened_at < self.open_s

    def allow(self) -> bool:
        return not self.is_open

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        if self._opened_at is not None and not self.is_open:
            self._opened_at = self.clock()
            logger.warning("circuit breaker reopened")
            return
        self._failures += 1
        if self._failures < self.threshold:
            return
        self._opened_at = self.clock()
        logger.warning("circuit breaker opened")


def create_openai_client(api_key: str) -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(api_key=api_key, base_url=META_BASE_URL, max_retries=0)


def _retry_after_s(error: openai.APIStatusError, now: datetime) -> float | None:
    raw = error.response.headers.get("retry-after")
    if raw is None:
        return None
    text = raw.strip()
    if text.replace(".", "", 1).isdigit():
        return float(text)
    try:
        moment = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    return max(0.0, (moment - now).total_seconds())


def _is_content_policy(error: openai.APIStatusError) -> bool:
    body = error.body
    if isinstance(body, dict):
        code = body.get("code")
        nested = body.get("error")
        if code == CONTENT_POLICY_CODE:
            return True
        if isinstance(nested, dict) and nested.get("code") == CONTENT_POLICY_CODE:
            return True
    return CONTENT_POLICY_CODE in str(error)


def _is_rejected_request(status: int) -> bool:
    if status in (HTTP_REQUEST_TIMEOUT, HTTP_CONFLICT, HTTP_TOO_MANY_REQUESTS):
        return False
    return HTTP_BAD_REQUEST <= status < HTTP_SERVER_ERROR_MIN


def _is_retryable_status(status: int) -> bool:
    if status in (HTTP_REQUEST_TIMEOUT, HTTP_CONFLICT, HTTP_TOO_MANY_REQUESTS):
        return True
    return status >= HTTP_SERVER_ERROR_MIN


@dataclass(frozen=True)
class _AttemptFailure:
    is_retryable: bool
    retry_after_s: float | None


class MetaClient:
    def __init__(
        self,
        openai_client: openai.AsyncOpenAI | None,
        meter: CostMeter,
        clock: MonotonicClock = time.monotonic,
        sleep: Sleeper = asyncio.sleep,
        jitter: JitterSource = random.random,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        timeouts: Mapping[CallKind, float] = TIMEOUT_S,
    ) -> None:
        self._openai = openai_client
        self._timeouts = timeouts
        self._meter = meter
        self._clock = clock
        self._sleep = sleep
        self._jitter = jitter
        self._wall_clock = wall_clock
        self._breakers: dict[MetaModel, CircuitBreaker] = {}

    @property
    def meter(self) -> CostMeter:
        return self._meter

    @property
    def has_credentials(self) -> bool:
        return self._openai is not None

    def sdk(self) -> openai.AsyncOpenAI:
        if self._openai is None:
            raise MetaUnavailableError("no API key configured")
        return self._openai

    def breaker(self, model: MetaModel) -> CircuitBreaker:
        if model not in self._breakers:
            self._breakers[model] = CircuitBreaker(clock=self._clock)
        return self._breakers[model]

    def is_available(self, model: MetaModel) -> bool:
        return (
            self.has_credentials
            and self.breaker(model).allow()
            and not self._meter.is_stopped
        )

    async def execute[T](
        self,
        spec: CallSpec,
        operation: Callable[[], Awaitable[T]],
        usage_of: Callable[[T], Usage],
    ) -> T:
        if self._openai is None:
            raise MetaUnavailableError("no API key configured")
        breaker = self.breaker(spec.model)
        if not breaker.allow():
            raise BreakerOpenError(f"{spec.model.value} breaker open")
        max_attempts = 1 + (MAX_RETRIES if spec.is_idempotent else 0)
        for attempt in range(max_attempts):
            self._meter.ensure_can_spend()
            started = self._clock()
            try:
                result = await asyncio.wait_for(
                    operation(), timeout=self._timeouts[spec.kind]
                )
            except (
                TimeoutError,
                openai.APIConnectionError,
                openai.APIStatusError,
            ) as error:
                failure = self._handle_failure(spec, error, started)
                if not failure.is_retryable or attempt == max_attempts - 1:
                    breaker.record_failure()
                    raise MetaUnavailableError(
                        f"{spec.model.value} call failed"
                    ) from error
                await self._sleep(self._retry_delay(attempt, failure.retry_after_s))
                continue
            self._record_success(spec, self._usage_or_none(usage_of, result), started)
            breaker.record_success()
            return result
        raise MetaUnavailableError(f"{spec.model.value} call failed")

    def _retry_delay(self, attempt: int, retry_after_s: float | None) -> float:
        backoff = RETRY_BACKOFF_S[min(attempt, len(RETRY_BACKOFF_S) - 1)]
        delay = backoff + self._jitter() * RETRY_JITTER_MAX_S
        if retry_after_s is None:
            return delay
        return max(delay, retry_after_s)

    def _latency_ms(self, started: float) -> int:
        return max(0, int((self._clock() - started) * 1000))

    def _usage_or_none[T](
        self, usage_of: Callable[[T], Usage], result: T
    ) -> Usage | None:
        try:
            return usage_of(result)
        except (AttributeError, KeyError, TypeError, ValueError):
            logger.warning("usage missing from a paid response, charging the estimate")
            return None

    def _record_success(
        self, spec: CallSpec, usage: Usage | None, started: float
    ) -> None:
        if usage is None:
            self._record_estimate(spec, started, is_ok=True)
            return
        self._meter.record(
            ApiUsageRecord(
                model=spec.model.value,
                kind=spec.kind.value,
                cost_usd=price_usage(spec.kind, usage),
                ok=True,
                latency_ms=self._latency_ms(started),
                input_tokens=usage.input_tokens,
                cached_tokens=usage.cached_tokens,
                output_tokens=usage.output_tokens,
                images=usage.images,
                frames=usage.frames,
                audio_seconds=usage.audio_seconds,
            )
        )

    def _record_estimate(self, spec: CallSpec, started: float, *, is_ok: bool) -> None:
        self._record_flat(
            spec, started, UNMETERED_CALL_ESTIMATE_USD[spec.kind], is_ok=is_ok
        )

    def _record_flat(
        self, spec: CallSpec, started: float, cost_usd: Decimal, *, is_ok: bool
    ) -> None:
        self._meter.record(
            ApiUsageRecord(
                model=spec.model.value,
                kind=spec.kind.value,
                cost_usd=cost_usd,
                ok=is_ok,
                latency_ms=self._latency_ms(started),
            )
        )

    def _handle_failure(
        self,
        spec: CallSpec,
        error: TimeoutError | openai.APIConnectionError | openai.APIStatusError,
        started: float,
    ) -> _AttemptFailure:
        if isinstance(error, openai.APIConnectionError) and not isinstance(
            error, openai.APITimeoutError
        ):
            self._record_flat(spec, started, Decimal(0), is_ok=False)
            return _AttemptFailure(is_retryable=True, retry_after_s=None)
        if not isinstance(error, openai.APIStatusError):
            self._record_estimate(spec, started, is_ok=False)
            return _AttemptFailure(is_retryable=True, retry_after_s=None)
        status = error.status_code
        is_maybe_billed = status >= HTTP_SERVER_ERROR_MIN
        cost = UNMETERED_CALL_ESTIMATE_USD[spec.kind] if is_maybe_billed else Decimal(0)
        self._record_flat(spec, started, cost, is_ok=False)
        retry_after = _retry_after_s(error, self._wall_clock())
        is_credit_exhausted = status == HTTP_PAYMENT_REQUIRED or (
            status == HTTP_TOO_MANY_REQUESTS and retry_after is None
        )
        if is_credit_exhausted:
            self._meter.force_stop()
            raise BudgetExceededError("credits exhausted") from error
        if _is_rejected_request(status):
            raise MetaRequestError(
                f"{spec.model.value} rejected the request with HTTP {status}",
                is_content_policy=status == HTTP_BAD_REQUEST
                and _is_content_policy(error),
            ) from error
        is_wait_too_long = (
            retry_after is not None and retry_after > self._timeouts[spec.kind]
        )
        return _AttemptFailure(
            is_retryable=_is_retryable_status(status) and not is_wait_too_long,
            retry_after_s=retry_after,
        )

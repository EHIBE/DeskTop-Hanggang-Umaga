import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

import httpx2
import openai
import pytest

from config import CallKind, MetaModel
from db.store import ApiUsageRecord
from meta_client import (
    BreakerOpenError,
    BudgetExceededError,
    CallSpec,
    CircuitBreaker,
    CostMeter,
    MetaClient,
    MetaRequestError,
    MetaUnavailableError,
    Usage,
    create_openai_client,
    price_usage,
    price_voice_seconds,
)

SPARK = CallSpec(model=MetaModel.SPARK, kind=CallKind.SPARK, is_idempotent=True)
SAM = CallSpec(model=MetaModel.SAM, kind=CallKind.SAM_IMAGE, is_idempotent=True)
FILES = CallSpec(model=MetaModel.FILES, kind=CallKind.FILES, is_idempotent=False)
NOW = datetime(2026, 10, 28, 3, 0, tzinfo=UTC)


@dataclass
class MemoryLog:
    records: list[ApiUsageRecord] = field(default_factory=list)
    starting_total: Decimal = Decimal(0)

    def record_api_usage(self, record: ApiUsageRecord) -> None:
        self.records.append(record)

    def total_api_cost(self) -> Decimal:
        return self.starting_total


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@dataclass
class Harness:
    client: MetaClient
    log: MemoryLog
    clock: FakeClock
    sleeps: list[float]


def make_harness(starting_total: Decimal = Decimal(0), jitter: float = 0.0) -> Harness:
    log = MemoryLog(starting_total=starting_total)
    clock = FakeClock()
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    client = MetaClient(
        create_openai_client("test-key"),
        CostMeter(log),
        clock=clock,
        sleep=fake_sleep,
        jitter=lambda: jitter,
        wall_clock=lambda: NOW,
    )
    return Harness(client=client, log=log, clock=clock, sleeps=sleeps)


def status_error(
    status: int, headers: dict[str, str] | None = None, body: object = None
) -> openai.APIStatusError:
    request = httpx2.Request("POST", "https://api.meta.ai/v1/responses")
    response = httpx2.Response(status, headers=headers or {}, request=request)
    return openai.APIStatusError(f"status {status}", response=response, body=body)


def scripted(*outcomes: object) -> tuple[Callable[[], Awaitable[str]], list[int]]:
    calls: list[int] = []

    async def operation() -> str:
        calls.append(1)
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return str(outcome)

    return operation, calls


def spark_usage(_: str) -> Usage:
    return Usage(input_tokens=3000, output_tokens=1500)


def run[T](awaitable: Awaitable[T]) -> T:
    async def wrapper() -> T:
        return await awaitable

    return asyncio.run(wrapper())


def test_success_logs_cost_and_latency() -> None:
    harness = make_harness()
    operation, calls = scripted("ok")
    assert run(harness.client.execute(SPARK, operation, spark_usage)) == "ok"
    assert len(calls) == 1
    record = harness.log.records[0]
    assert record.ok
    assert record.cost_usd == Decimal("0.010125")
    assert record.model == "muse-spark-1.3"
    assert harness.client.meter.spent_usd == Decimal("0.010125")


def test_retries_twice_with_backoff_and_jitter() -> None:
    harness = make_harness(jitter=1.0)
    operation, calls = scripted(status_error(500), TimeoutError(), "ok")
    assert run(harness.client.execute(SPARK, operation, spark_usage)) == "ok"
    assert len(calls) == 3
    assert harness.sleeps == [0.75, 1.25]
    assert [r.ok for r in harness.log.records] == [False, False, True]


def test_gives_up_after_two_retries() -> None:
    harness = make_harness()
    operation, calls = scripted(status_error(503), status_error(503), status_error(503))
    with pytest.raises(MetaUnavailableError):
        run(harness.client.execute(SAM, operation, lambda _: Usage(images=1)))
    assert len(calls) == 3
    assert harness.sleeps == [0.5, 1.0]


def test_no_retry_on_bad_request() -> None:
    harness = make_harness()
    operation, calls = scripted(status_error(400))
    with pytest.raises(MetaRequestError) as info:
        run(harness.client.execute(SPARK, operation, spark_usage))
    assert len(calls) == 1
    assert not info.value.is_content_policy
    assert harness.sleeps == []


def test_content_policy_violation_is_flagged() -> None:
    harness = make_harness()
    body = {"error": {"code": "content_policy_violation"}}
    operation, _ = scripted(status_error(400, body=body))
    spec = CallSpec(model=MetaModel.IMAGE, kind=CallKind.IMAGE, is_idempotent=True)
    with pytest.raises(MetaRequestError) as info:
        run(harness.client.execute(spec, operation, lambda _: Usage(images=1)))
    assert info.value.is_content_policy


def test_non_idempotent_call_is_not_retried() -> None:
    harness = make_harness()
    operation, calls = scripted(status_error(503), "ok")
    with pytest.raises(MetaUnavailableError):
        run(harness.client.execute(FILES, operation, lambda _: Usage()))
    assert len(calls) == 1


def test_retry_after_seconds_is_honored() -> None:
    harness = make_harness()
    operation, _ = scripted(status_error(429, headers={"Retry-After": "3"}), "ok")
    run(harness.client.execute(SPARK, operation, spark_usage))
    assert harness.sleeps == [3.0]


def test_retry_after_http_date_is_honored() -> None:
    harness = make_harness()
    header = {"Retry-After": "Wed, 28 Oct 2026 03:00:04 GMT"}
    operation, _ = scripted(status_error(503, headers=header), "ok")
    run(harness.client.execute(SPARK, operation, spark_usage))
    assert harness.sleeps == [4.0]


def test_retry_after_longer_than_timeout_fails_fast() -> None:
    harness = make_harness()
    operation, calls = scripted(status_error(503, headers={"Retry-After": "300"}), "ok")
    with pytest.raises(MetaUnavailableError):
        run(harness.client.execute(SPARK, operation, spark_usage))
    assert len(calls) == 1
    assert harness.sleeps == []


def test_rate_limit_without_retry_window_stops_paid_calls() -> None:
    harness = make_harness()
    operation, calls = scripted(status_error(429))
    with pytest.raises(BudgetExceededError):
        run(harness.client.execute(SPARK, operation, spark_usage))
    assert len(calls) == 1
    assert harness.client.meter.is_stopped


def test_payment_required_stops_paid_calls() -> None:
    harness = make_harness()
    operation, _ = scripted(status_error(402))
    with pytest.raises(BudgetExceededError):
        run(harness.client.execute(SPARK, operation, spark_usage))
    blocked, blocked_calls = scripted("ok")
    with pytest.raises(BudgetExceededError):
        run(harness.client.execute(SAM, blocked, lambda _: Usage(images=1)))
    assert blocked_calls == []


def test_hard_stop_blocks_before_calling() -> None:
    harness = make_harness(starting_total=Decimal(120))
    operation, calls = scripted("ok")
    with pytest.raises(BudgetExceededError):
        run(harness.client.execute(SPARK, operation, spark_usage))
    assert calls == []


def test_warning_threshold() -> None:
    assert not make_harness(starting_total=Decimal("89.99")).client.meter.is_warning
    harness = make_harness(starting_total=Decimal("89.995"))
    operation, _ = scripted("ok")
    run(harness.client.execute(SPARK, operation, spark_usage))
    assert harness.client.meter.is_warning
    assert not harness.client.meter.is_stopped


def test_crossing_hard_stop_blocks_next_call() -> None:
    harness = make_harness(starting_total=Decimal("119.995"))
    first, _ = scripted("ok")
    run(harness.client.execute(SPARK, first, spark_usage))
    second, second_calls = scripted("ok")
    with pytest.raises(BudgetExceededError):
        run(harness.client.execute(SPARK, second, spark_usage))
    assert second_calls == []


def test_unreadable_usage_charges_the_estimate() -> None:
    harness = make_harness()
    operation, _ = scripted("ok")

    def broken_usage(_: str) -> Usage:
        raise KeyError("usage")

    assert run(harness.client.execute(SPARK, operation, broken_usage)) == "ok"
    assert harness.log.records[0].cost_usd == Decimal("0.02")
    assert harness.log.records[0].ok


def test_ambiguous_failures_charge_the_estimate() -> None:
    harness = make_harness()
    operation, _ = scripted(TimeoutError(), status_error(502), "ok")
    run(harness.client.execute(SAM, operation, lambda _: Usage(images=1)))
    assert [r.cost_usd for r in harness.log.records] == [
        Decimal("0.0025"),
        Decimal("0.0025"),
        Decimal("0.0025"),
    ]


def test_unsent_and_rejected_requests_cost_nothing() -> None:
    harness = make_harness()
    request = httpx2.Request("POST", "https://api.meta.ai/v1/responses")
    operation, _ = scripted(
        openai.APIConnectionError(request=request), status_error(400)
    )
    with pytest.raises(MetaRequestError):
        run(harness.client.execute(SPARK, operation, spark_usage))
    assert [r.cost_usd for r in harness.log.records] == [Decimal(0), Decimal(0)]


def test_breaker_opens_after_three_failed_calls_and_recovers() -> None:
    harness = make_harness()
    for _ in range(3):
        operation, _ = scripted(TimeoutError(), TimeoutError(), TimeoutError())
        with pytest.raises(MetaUnavailableError):
            run(harness.client.execute(SAM, operation, lambda _: Usage(images=1)))
    assert not harness.client.is_available(MetaModel.SAM)
    assert harness.client.is_available(MetaModel.SPARK)
    blocked, blocked_calls = scripted("ok")
    with pytest.raises(BreakerOpenError):
        run(harness.client.execute(SAM, blocked, lambda _: Usage(images=1)))
    assert blocked_calls == []
    harness.clock.advance(120.0)
    trial, _ = scripted("ok")
    assert run(harness.client.execute(SAM, trial, lambda _: Usage(images=1))) == "ok"
    assert harness.client.is_available(MetaModel.SAM)


def test_breaker_half_open_failure_reopens() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(clock=clock)
    for _ in range(3):
        breaker.record_failure()
    assert breaker.is_open
    clock.advance(120.0)
    assert breaker.allow()
    breaker.record_failure()
    assert breaker.is_open


def test_success_resets_breaker_count() -> None:
    breaker = CircuitBreaker(clock=FakeClock())
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    assert not breaker.is_open


def test_missing_key_is_unavailable() -> None:
    client = MetaClient(None, CostMeter(MemoryLog()))
    operation, calls = scripted("ok")
    with pytest.raises(MetaUnavailableError):
        run(client.execute(SPARK, operation, spark_usage))
    assert calls == []
    assert not client.is_available(MetaModel.SPARK)


def test_timeout_is_enforced_per_attempt() -> None:
    log = MemoryLog()
    attempts: list[int] = []

    async def hangs() -> str:
        attempts.append(1)
        await asyncio.Event().wait()
        return "never"

    async def no_sleep(_: float) -> None:
        return None

    client = MetaClient(
        create_openai_client("test-key"),
        CostMeter(log),
        sleep=no_sleep,
        timeouts={kind: 0.01 for kind in CallKind},
    )
    with pytest.raises(MetaUnavailableError):
        run(client.execute(SPARK, hangs, spark_usage))
    assert len(attempts) == 3
    assert [r.ok for r in log.records] == [False, False, False]


@pytest.mark.parametrize(
    ("kind", "usage", "expected"),
    [
        (
            CallKind.SPARK,
            Usage(input_tokens=4500, cached_tokens=1200, output_tokens=850),
            "0.0079175",
        ),
        (CallKind.SAM_IMAGE, Usage(images=1), "0.0025"),
        (CallKind.SAM_VIDEO, Usage(frames=400), "0.08"),
        (CallKind.SAM_VIDEO, Usage(frames=10), "0.01"),
        (CallKind.IMAGE, Usage(images=1), "0.01"),
        (CallKind.FILES, Usage(), "0"),
    ],
)
def test_price_table(kind: CallKind, usage: Usage, expected: str) -> None:
    assert price_usage(kind, usage) == Decimal(expected)


def test_voice_price_per_hour() -> None:
    assert price_voice_seconds(3600) == Decimal("0.18")

"""Deterministic resource-governor helpers for Printer V1 scheduling."""

from datetime import datetime, timezone

from printer_v1.scheduler.contracts import JOB_PRIORITY_VALUE, JobKind


TOKEN_LEVEL_JOB_KINDS = frozenset(
    {
        JobKind.OPEN_PAPER_TRADE_MONITOR,
        JobKind.ACTIVE_EXIT_RISK_TOKEN,
        JobKind.TRACK_FAST_MICRO_EVENT,
        JobKind.TRACK_FAST_FIRST_15M,
        JobKind.TRACK_NORMAL_FIRST_15M,
        JobKind.MEMORY_WINDOW_CLOSE,
        JobKind.TRACKED_TOKEN_SAFETY_LIQUIDITY_REFRESH,
    }
)

BROAD_CONTEXT_JOB_KINDS = frozenset(
    {
        JobKind.MARKET_REGIME_CONTEXT,
        JobKind.SOLANA_CHAIN_HEAT_CONTEXT,
    }
)

CRITICAL_JOB_KINDS = frozenset(
    {
        JobKind.OPEN_PAPER_TRADE_MONITOR,
        JobKind.ACTIVE_EXIT_RISK_TOKEN,
    }
)


def as_job_kind(job_kind: JobKind | str) -> JobKind:
    return job_kind if isinstance(job_kind, JobKind) else JobKind(job_kind)


def priority_value(job_kind: JobKind | str) -> int:
    return JOB_PRIORITY_VALUE[as_job_kind(job_kind)]


def is_higher_priority(left: JobKind | str, right: JobKind | str) -> bool:
    return priority_value(left) < priority_value(right)


def compare_job_priority(left: JobKind | str, right: JobKind | str) -> int:
    left_value = priority_value(left)
    right_value = priority_value(right)
    return (left_value > right_value) - (left_value < right_value)


def effective_priority_value(
    job_kind: JobKind | str,
    scheduled_for: datetime | None = None,
    now: datetime | None = None,
) -> int:
    kind = as_job_kind(job_kind)
    value = priority_value(kind)
    if kind in CRITICAL_JOB_KINDS or scheduled_for is None:
        return value

    current_time = now or datetime.now(timezone.utc)
    age_seconds = max((current_time - scheduled_for).total_seconds(), 0)
    if age_seconds >= 3600:
        value -= 2
    elif age_seconds >= 1800:
        value -= 1
    return max(value, priority_value(JobKind.TRACK_FAST_MICRO_EVENT))


def should_allow_when_limited(job_kind: JobKind | str) -> bool:
    kind = as_job_kind(job_kind)
    return kind in TOKEN_LEVEL_JOB_KINDS or kind == JobKind.DISCOVERY_REFRESH


def should_delay_for_resource_pressure(
    job_kind: JobKind | str,
    pending_higher_priority_token_jobs: int,
) -> bool:
    kind = as_job_kind(job_kind)
    if pending_higher_priority_token_jobs <= 0:
        return False
    if kind in BROAD_CONTEXT_JOB_KINDS or kind == JobKind.BACKUP_SOURCE_CHECK:
        return True
    return False


def next_check_interval_seconds(job_kind: JobKind | str) -> int:
    intervals = {
        JobKind.OPEN_PAPER_TRADE_MONITOR: 30,
        JobKind.ACTIVE_EXIT_RISK_TOKEN: 60,
        JobKind.TRACK_FAST_MICRO_EVENT: 60,
        JobKind.TRACK_FAST_FIRST_15M: 120,
        JobKind.TRACK_NORMAL_FIRST_15M: 300,
        JobKind.MEMORY_WINDOW_CLOSE: 60,
        JobKind.TRACKED_TOKEN_SAFETY_LIQUIDITY_REFRESH: 300,
        JobKind.DISCOVERY_REFRESH: 600,
        JobKind.MARKET_REGIME_CONTEXT: 900,
        JobKind.SOLANA_CHAIN_HEAT_CONTEXT: 1200,
        JobKind.BACKUP_SOURCE_CHECK: 1800,
    }
    return intervals[as_job_kind(job_kind)]


def should_cooldown_failed_job(
    job_kind: JobKind | str,
    retry_count: int,
    max_retries: int = 3,
) -> bool:
    del job_kind
    return retry_count < max_retries


def get_retry_cooldown_seconds(job_kind: JobKind | str, retry_count: int) -> int:
    base_intervals = {
        JobKind.OPEN_PAPER_TRADE_MONITOR: 30,
        JobKind.ACTIVE_EXIT_RISK_TOKEN: 60,
        JobKind.TRACK_FAST_MICRO_EVENT: 90,
        JobKind.TRACK_FAST_FIRST_15M: 120,
        JobKind.TRACK_NORMAL_FIRST_15M: 300,
        JobKind.MEMORY_WINDOW_CLOSE: 120,
        JobKind.TRACKED_TOKEN_SAFETY_LIQUIDITY_REFRESH: 300,
        JobKind.DISCOVERY_REFRESH: 600,
        JobKind.MARKET_REGIME_CONTEXT: 900,
        JobKind.SOLANA_CHAIN_HEAT_CONTEXT: 1200,
        JobKind.BACKUP_SOURCE_CHECK: 1800,
    }
    return base_intervals[as_job_kind(job_kind)] * max(retry_count, 1)

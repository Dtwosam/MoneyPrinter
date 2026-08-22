"""Scheduler contracts for Printer V1 Phase 3."""

from enum import StrEnum


class JobKind(StrEnum):
    OPEN_PAPER_TRADE_MONITOR = "OPEN_PAPER_TRADE_MONITOR"
    ACTIVE_EXIT_RISK_TOKEN = "ACTIVE_EXIT_RISK_TOKEN"
    TRACK_FAST_MICRO_EVENT = "TRACK_FAST_MICRO_EVENT"
    TRACK_FAST_FIRST_15M = "TRACK_FAST_FIRST_15M"
    TRACK_FAST_1H = "TRACK_FAST_1H"
    TRACK_FAST_4H = "TRACK_FAST_4H"
    TRACK_NORMAL_FIRST_15M = "TRACK_NORMAL_FIRST_15M"
    TRACK_NORMAL_1H = "TRACK_NORMAL_1H"
    TRACK_NORMAL_4H = "TRACK_NORMAL_4H"
    MEMORY_WINDOW_CLOSE = "MEMORY_WINDOW_CLOSE"
    TRACKED_TOKEN_SAFETY_LIQUIDITY_REFRESH = "TRACKED_TOKEN_SAFETY_LIQUIDITY_REFRESH"
    DISCOVERY_REFRESH = "DISCOVERY_REFRESH"
    PRE_ADMISSION_DISCOVERY_SELECTION = "PRE_ADMISSION_DISCOVERY_SELECTION"
    MARKET_REGIME_CONTEXT = "MARKET_REGIME_CONTEXT"
    SOLANA_CHAIN_HEAT_CONTEXT = "SOLANA_CHAIN_HEAT_CONTEXT"
    BACKUP_SOURCE_CHECK = "BACKUP_SOURCE_CHECK"


JOB_PRIORITY_ORDER: tuple[JobKind, ...] = (
    JobKind.OPEN_PAPER_TRADE_MONITOR,
    JobKind.ACTIVE_EXIT_RISK_TOKEN,
    JobKind.TRACK_FAST_MICRO_EVENT,
    JobKind.TRACK_FAST_FIRST_15M,
    JobKind.TRACK_FAST_1H,
    JobKind.TRACK_FAST_4H,
    JobKind.TRACK_NORMAL_FIRST_15M,
    JobKind.TRACK_NORMAL_1H,
    JobKind.TRACK_NORMAL_4H,
    JobKind.MEMORY_WINDOW_CLOSE,
    JobKind.TRACKED_TOKEN_SAFETY_LIQUIDITY_REFRESH,
    JobKind.DISCOVERY_REFRESH,
    JobKind.PRE_ADMISSION_DISCOVERY_SELECTION,
    JobKind.MARKET_REGIME_CONTEXT,
    JobKind.SOLANA_CHAIN_HEAT_CONTEXT,
    JobKind.BACKUP_SOURCE_CHECK,
)


TRACK_FAST_JOB_KINDS = frozenset(
    {
        JobKind.TRACK_FAST_MICRO_EVENT,
        JobKind.TRACK_FAST_FIRST_15M,
        JobKind.TRACK_FAST_1H,
        JobKind.TRACK_FAST_4H,
    }
)

TRACK_NORMAL_JOB_KINDS = frozenset(
    {
        JobKind.TRACK_NORMAL_FIRST_15M,
        JobKind.TRACK_NORMAL_1H,
        JobKind.TRACK_NORMAL_4H,
    }
)

DISCOVERY_JOB_KINDS = frozenset(
    {
        JobKind.DISCOVERY_REFRESH,
        JobKind.PRE_ADMISSION_DISCOVERY_SELECTION,
    }
)


def job_resource_category(job_kind: JobKind | str) -> JobKind:
    """Return the canonical AGENTS resource-category representative.

    The representative is the first member of that category already present
    in ``JOB_PRIORITY_ORDER``.  This groups only the JobKinds that AGENTS names
    as one resource category and does not create a second priority value.
    """
    kind = job_kind if isinstance(job_kind, JobKind) else JobKind(job_kind)
    if kind in TRACK_FAST_JOB_KINDS:
        return JobKind.TRACK_FAST_MICRO_EVENT
    if kind in TRACK_NORMAL_JOB_KINDS:
        return JobKind.TRACK_NORMAL_FIRST_15M
    if kind in DISCOVERY_JOB_KINDS:
        return JobKind.DISCOVERY_REFRESH
    return kind


JOB_RESOURCE_CATEGORY_ORDER: tuple[JobKind, ...] = tuple(
    dict.fromkeys(job_resource_category(job_kind) for job_kind in JOB_PRIORITY_ORDER)
)

JOB_PRIORITY_VALUE = {
    job_kind: index + 1 for index, job_kind in enumerate(JOB_PRIORITY_ORDER)
}


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    COOLDOWN = "COOLDOWN"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


ACTIVE_JOB_STATUSES = (
    JobStatus.PENDING,
    JobStatus.RUNNING,
    JobStatus.COOLDOWN,
)


class LockResult(StrEnum):
    ACQUIRED = "ACQUIRED"
    ALREADY_LOCKED = "ALREADY_LOCKED"
    NOT_DUE = "NOT_DUE"
    NOT_FOUND = "NOT_FOUND"
    DUPLICATE_ACTIVE_JOB = "DUPLICATE_ACTIVE_JOB"
    SOURCE_NOT_ALLOWED = "SOURCE_NOT_ALLOWED"
    RESOURCE_LIMITED = "RESOURCE_LIMITED"

"""Read-only source request budget accounting for Printer V1.

Provides count_recent_source_requests so callers can supply an accurate
recent_request_count to can_request_source (Source Governor) without
bypassing Source Governor or making network calls.

The count represents consumed source/provider attempts, not every
printer_source_requests row. Pure governor rejections that never reached
the adapter/provider must not increase the rate-limit count.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
import sqlite3


DEFAULT_WINDOW_SECONDS: int = 60

_PRE_ADAPTER_FAILURE_TYPES = {
    "governor_rejection",
    "governor_rejected",
    "rate_limit_exceeded",
    "paid_dependency_rejected",
    "unknown_source",
    "request_kind_not_allowed",
    "not_solana_token_level_source",
    "jupiter_quote_paper_only",
    "test_fixture",
}


class ConsumedProviderAttemptEvidence(StrEnum):
    RESPONSE_BACKED = "RESPONSE_BACKED"
    ATTRIBUTABLE_FAILURE = "ATTRIBUTABLE_FAILURE"


@dataclass(frozen=True, order=True)
class ConsumedProviderAttempt:
    source_request_id: int
    source_name: str
    request_kind: str
    requested_at: datetime
    evidence_class: ConsumedProviderAttemptEvidence


class SourceBudgetAccountingEvidenceError(RuntimeError):
    """Current persisted evidence cannot support exact provider accounting."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(self.code if not detail else f"{self.code}:{self.detail}")


@contextmanager
def _read_connection(db: str | Path | sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    if isinstance(db, sqlite3.Connection):
        yield db
        return
    conn = sqlite3.connect(Path(db))
    try:
        yield conn
    finally:
        conn.close()


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _failure_filter_sql() -> tuple[str, tuple[str, ...]]:
    placeholders = ", ".join("?" for _ in _PRE_ADAPTER_FAILURE_TYPES)
    return (
        f"lower(coalesce(f.failure_type, '')) NOT IN ({placeholders})",
        tuple(sorted(_PRE_ADAPTER_FAILURE_TYPES)),
    )


def _require_current_attempt_schema(conn: sqlite3.Connection) -> None:
    required_columns = {
        "printer_source_requests": {
            "id",
            "source_name",
            "request_kind",
            "requested_at",
        },
        "printer_source_responses": {"source_request_id", "source_name"},
        "printer_source_failures": {
            "source_request_id",
            "source_name",
            "request_kind",
            "failure_type",
            "created_at",
        },
    }
    for table, required in required_columns.items():
        missing = required - _table_columns(conn, table)
        if missing:
            raise SourceBudgetAccountingEvidenceError(
                "CONSUMED_ATTEMPT_SCHEMA_UNSUPPORTED",
                f"{table}:{','.join(sorted(missing))}",
            )


def _canonical_sqlite_created_at_utc(
    raw: object,
    *,
    failure_id: int,
) -> datetime:
    if not isinstance(raw, str):
        raise SourceBudgetAccountingEvidenceError(
            "CONSUMED_ATTEMPT_LINKAGE_AMBIGUOUS",
            f"printer_source_failures:{failure_id}",
        )
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise SourceBudgetAccountingEvidenceError(
            "CONSUMED_ATTEMPT_LINKAGE_AMBIGUOUS",
            f"printer_source_failures:{failure_id}",
        ) from exc
    if parsed.strftime("%Y-%m-%d %H:%M:%S") != raw:
        raise SourceBudgetAccountingEvidenceError(
            "CONSUMED_ATTEMPT_LINKAGE_AMBIGUOUS",
            f"printer_source_failures:{failure_id}",
        )
    return parsed.replace(tzinfo=timezone.utc)


def _require_unambiguous_current_window_attempt_linkage(
    conn: sqlite3.Connection,
    source_name: str,
    *,
    cutoff: datetime,
) -> None:
    response_rows = conn.execute(
        """
        SELECT
            resp.id,
            resp.source_request_id,
            resp.source_name,
            r.id,
            r.source_name,
            r.requested_at
        FROM printer_source_responses resp
        LEFT JOIN printer_source_requests r ON r.id = resp.source_request_id
        WHERE (resp.source_name = ? OR r.source_name = ?)
        ORDER BY resp.id ASC
        """,
        (source_name, source_name),
    ).fetchall()
    for row in response_rows:
        response_id = int(row[0])
        if row[1] is None or row[3] is None:
            raise SourceBudgetAccountingEvidenceError(
                "CONSUMED_ATTEMPT_LINKAGE_AMBIGUOUS",
                f"printer_source_responses:{response_id}",
            )
        requested_at = _canonical_utc_timestamp(row[5], request_id=int(row[3]))
        if requested_at < cutoff:
            continue
        if str(row[2]) != str(row[4]):
            raise SourceBudgetAccountingEvidenceError(
                "CONSUMED_ATTEMPT_LINKAGE_AMBIGUOUS",
                f"printer_source_responses:{response_id}",
            )

    failure_rows = conn.execute(
        """
        SELECT
            f.id,
            f.source_request_id,
            f.source_name,
            f.request_kind,
            f.failure_type,
            f.created_at,
            r.id,
            r.source_name,
            r.request_kind,
            r.requested_at
        FROM printer_source_failures f
        LEFT JOIN printer_source_requests r ON r.id = f.source_request_id
        WHERE (f.source_name = ? OR r.source_name = ?)
        ORDER BY f.id ASC
        """,
        (source_name, source_name),
    ).fetchall()
    for row in failure_rows:
        failure_id = int(row[0])
        if row[1] is None or row[6] is None:
            created_at = _canonical_sqlite_created_at_utc(
                row[5],
                failure_id=failure_id,
            )
            if created_at < cutoff:
                continue
            raise SourceBudgetAccountingEvidenceError(
                "CONSUMED_ATTEMPT_LINKAGE_AMBIGUOUS",
                f"printer_source_failures:{failure_id}",
            )

        requested_at = _canonical_utc_timestamp(row[9], request_id=int(row[6]))
        if requested_at < cutoff:
            continue
        if (
            str(row[2]) != str(row[7])
            or str(row[3]) != str(row[8])
            or not isinstance(row[4], str)
            or not row[4].strip()
        ):
            raise SourceBudgetAccountingEvidenceError(
                "CONSUMED_ATTEMPT_LINKAGE_AMBIGUOUS",
                f"printer_source_failures:{failure_id}",
            )


def _canonical_utc_timestamp(raw: object, *, request_id: int) -> datetime:
    if not isinstance(raw, str) or not raw.strip():
        raise SourceBudgetAccountingEvidenceError(
            "CONSUMED_ATTEMPT_TIMESTAMP_AMBIGUOUS", str(request_id)
        )
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SourceBudgetAccountingEvidenceError(
            "CONSUMED_ATTEMPT_TIMESTAMP_AMBIGUOUS", str(request_id)
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SourceBudgetAccountingEvidenceError(
            "CONSUMED_ATTEMPT_TIMESTAMP_AMBIGUOUS", str(request_id)
        )
    return parsed.astimezone(timezone.utc)


def _current_utc(now: datetime | None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise SourceBudgetAccountingEvidenceError("WINDOW_TIMESTAMP_AMBIGUOUS")
    return current.astimezone(timezone.utc)


def _select_consumed_provider_attempts(
    conn: sqlite3.Connection,
    source_name: str,
    *,
    cutoff: datetime,
) -> tuple[ConsumedProviderAttempt, ...]:
    _require_current_attempt_schema(conn)
    _require_unambiguous_current_window_attempt_linkage(
        conn,
        source_name,
        cutoff=cutoff,
    )
    failure_filter, failure_params = _failure_filter_sql()
    rows = conn.execute(
        f"""
        WITH evidence AS (
            SELECT
                r.id AS source_request_id,
                r.source_name,
                r.request_kind,
                r.requested_at,
                EXISTS (
                    SELECT 1
                    FROM printer_source_responses resp
                    WHERE resp.source_request_id = r.id
                ) AS response_backed,
                EXISTS (
                    SELECT 1
                    FROM printer_source_failures f
                    WHERE f.source_request_id = r.id
                      AND {failure_filter}
                ) AS attributable_failure
            FROM printer_source_requests r
            WHERE r.source_name = ?
        )
        SELECT
            source_request_id,
            source_name,
            request_kind,
            requested_at,
            response_backed,
            attributable_failure
        FROM evidence
        WHERE response_backed = 1 OR attributable_failure = 1
        ORDER BY source_request_id ASC
        """,
        (*failure_params, source_name),
    ).fetchall()

    attempts: list[ConsumedProviderAttempt] = []
    for row in rows:
        request_id = int(row[0])
        response_backed = bool(row[4])
        attributable_failure = bool(row[5])
        if response_backed and attributable_failure:
            raise SourceBudgetAccountingEvidenceError(
                "CONSUMED_ATTEMPT_EVIDENCE_AMBIGUOUS", str(request_id)
            )
        requested_at = _canonical_utc_timestamp(row[3], request_id=request_id)
        if requested_at < cutoff:
            continue
        evidence_class = (
            ConsumedProviderAttemptEvidence.RESPONSE_BACKED
            if response_backed
            else ConsumedProviderAttemptEvidence.ATTRIBUTABLE_FAILURE
        )
        attempts.append(
            ConsumedProviderAttempt(
                source_request_id=request_id,
                source_name=str(row[1]),
                request_kind=str(row[2]),
                requested_at=requested_at,
                evidence_class=evidence_class,
            )
        )
    return tuple(
        sorted(
            attempts,
            key=lambda item: (item.requested_at, item.source_request_id),
        )
    )


def recent_consumed_provider_attempts(
    db: str | Path | sqlite3.Connection,
    source_name: str,
    *,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    now: datetime | None = None,
) -> tuple[ConsumedProviderAttempt, ...]:
    """Return exact current-window attempts using request ``requested_at``.

    Response rows and non-pre-adapter failure rows establish provider-reaching
    evidence. Missing current-schema linkage or timestamp evidence raises
    instead of being projected as unused capacity.
    """
    current_time = _current_utc(now)
    cutoff = current_time - timedelta(seconds=window_seconds)
    with _read_connection(db) as conn:
        return _select_consumed_provider_attempts(
            conn,
            source_name,
            cutoff=cutoff,
        )


def count_recent_source_requests(
    db: str | Path | sqlite3.Connection,
    source_name: str,
    *,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    now: datetime | None = None,
) -> int:
    """Count consumed source/provider attempts for *source_name* within the window.

    Counted:
    - requests with a recorded source response
    - source/adapter/network failures when the schema can attribute them to the source

    Not counted:
    - pure request rows without response/failure evidence
    - pure governor rejections that never reached the adapter/provider

    Read-only. Never mutates the database.
    """
    return len(
        recent_consumed_provider_attempts(
            db,
            source_name,
            window_seconds=window_seconds,
            now=now,
        )
    )

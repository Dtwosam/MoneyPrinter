from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.scheduler import scheduler
from printer_v1.sources import budget_accounting, governed_execution


SOURCE_NAME = "dexscreener"
REQUEST_KIND = "pair_market_snapshot"
OTHER_SOURCE_NAME = "geckoterminal"
OTHER_REQUEST_KIND = "geckoterminal_new_pool_discovery"

PRE_ADAPTER_FAILURE_TYPES = (
    "governor_rejection",
    "governor_rejected",
    "rate_limit_exceeded",
    "paid_dependency_rejected",
    "unknown_source",
    "request_kind_not_allowed",
    "not_solana_token_level_source",
    "jupiter_quote_paper_only",
    "test_fixture",
)


@pytest.fixture
def current_schema_connection(tmp_path) -> sqlite3.Connection:
    db_path = tmp_path / "provider-attempt-detail.sqlite3"
    apply_migrations(db_path)
    connection = sqlite3.connect(db_path)
    try:
        yield connection
    finally:
        connection.close()


def _insert_request(
    connection: sqlite3.Connection,
    *,
    source_name: str = SOURCE_NAME,
    request_kind: str = REQUEST_KIND,
    requested_at: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO printer_source_requests(
            source_name, request_kind, requested_at,
            source_status, data_quality_label
        ) VALUES (?, ?, ?, 'COMPLETE', 'CLEAN_DATA')
        """,
        (source_name, request_kind, requested_at),
    )
    return int(cursor.lastrowid)


def _insert_response(
    connection: sqlite3.Connection,
    *,
    source_request_id: int,
    source_name: str = SOURCE_NAME,
    received_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO printer_source_responses(
            source_request_id, source_name, received_at,
            status_code, source_status, data_quality_label
        ) VALUES (?, ?, ?, 200, 'COMPLETE', 'CLEAN_DATA')
        """,
        (source_request_id, source_name, received_at),
    )


def _insert_failure(
    connection: sqlite3.Connection,
    *,
    source_request_id: int | None,
    source_name: str = SOURCE_NAME,
    request_kind: str = REQUEST_KIND,
    failed_at: str,
    failure_type: str,
) -> None:
    connection.execute(
        """
        INSERT INTO printer_source_failures(
            source_name, request_kind, failed_at,
            failure_type, failure_message,
            source_status, data_quality_label, source_request_id
        ) VALUES (?, ?, ?, ?, 'fixture failure',
                  'FAILED', 'MISSING_CRITICAL_DATA', ?)
        """,
        (
            source_name,
            request_kind,
            failed_at,
            failure_type,
            source_request_id,
        ),
    )


def test_provider_attempt_details_share_count_law_and_request_timestamp(
    current_schema_connection: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = current_schema_connection
    now = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
    response_requested_at = now - timedelta(seconds=40)
    failure_requested_at = now - timedelta(seconds=20)

    response_request_id = _insert_request(
        connection,
        requested_at=response_requested_at.isoformat(),
    )
    _insert_response(
        connection,
        source_request_id=response_request_id,
        received_at=(now + timedelta(hours=2)).isoformat(),
    )

    failure_request_id = _insert_request(
        connection,
        requested_at=failure_requested_at.isoformat(),
    )
    _insert_failure(
        connection,
        source_request_id=failure_request_id,
        failed_at=(now + timedelta(hours=3)).isoformat(),
        failure_type="network_error",
    )

    for ordinal, failure_type in enumerate(PRE_ADAPTER_FAILURE_TYPES, start=1):
        request_id = _insert_request(
            connection,
            requested_at=(now - timedelta(seconds=ordinal)).isoformat(),
        )
        _insert_failure(
            connection,
            source_request_id=request_id,
            failed_at=(now + timedelta(hours=ordinal)).isoformat(),
            failure_type=failure_type,
        )

    _insert_request(
        connection,
        requested_at=(now - timedelta(seconds=5)).isoformat(),
    )

    old_request_id = _insert_request(
        connection,
        requested_at=(now - timedelta(seconds=61)).isoformat(),
    )
    _insert_response(
        connection,
        source_request_id=old_request_id,
        received_at=(now + timedelta(hours=4)).isoformat(),
    )

    other_request_id = _insert_request(
        connection,
        source_name=OTHER_SOURCE_NAME,
        request_kind=OTHER_REQUEST_KIND,
        requested_at=(now - timedelta(seconds=10)).isoformat(),
    )
    _insert_response(
        connection,
        source_request_id=other_request_id,
        source_name=OTHER_SOURCE_NAME,
        received_at=(now + timedelta(hours=5)).isoformat(),
    )
    connection.commit()

    def forbidden_activity(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("provider-attempt detail invoked operational activity")

    monkeypatch.setattr(
        governed_execution, "execute_source_request_with_governor", forbidden_activity
    )
    monkeypatch.setattr(scheduler, "enqueue_job", forbidden_activity)
    monkeypatch.setattr(scheduler, "claim_due_job", forbidden_activity)
    monkeypatch.setattr(scheduler, "cancel_job", forbidden_activity)

    traced_statements: list[str] = []
    connection.set_trace_callback(traced_statements.append)
    changes_before = connection.total_changes
    attempts = budget_accounting.recent_consumed_provider_attempts(
        connection,
        SOURCE_NAME,
        now=now,
    )
    repeated = budget_accounting.recent_consumed_provider_attempts(
        connection,
        SOURCE_NAME,
        now=now,
    )
    counted = budget_accounting.count_recent_source_requests(
        connection,
        SOURCE_NAME,
        now=now,
    )
    other_attempts = budget_accounting.recent_consumed_provider_attempts(
        connection,
        OTHER_SOURCE_NAME,
        now=now,
    )
    connection.set_trace_callback(None)

    assert attempts == repeated
    assert tuple(
        (
            row.source_request_id,
            row.source_name,
            row.request_kind,
            row.requested_at,
            str(row.evidence_class),
        )
        for row in attempts
    ) == (
        (
            response_request_id,
            SOURCE_NAME,
            REQUEST_KIND,
            response_requested_at,
            "RESPONSE_BACKED",
        ),
        (
            failure_request_id,
            SOURCE_NAME,
            REQUEST_KIND,
            failure_requested_at,
            "ATTRIBUTABLE_FAILURE",
        ),
    )
    assert counted == len(attempts) == 2
    assert tuple(row.source_request_id for row in other_attempts) == (
        other_request_id,
    )
    assert connection.total_changes == changes_before
    assert not any(
        statement.lstrip().upper().startswith(
            ("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP")
        )
        for statement in traced_statements
    )
    with pytest.raises(FrozenInstanceError):
        attempts[0].source_name = OTHER_SOURCE_NAME


@pytest.mark.parametrize("linkage_mode", ("missing", "mismatched"))
def test_provider_attempt_details_fail_closed_on_ambiguous_linkage(
    current_schema_connection: sqlite3.Connection,
    linkage_mode: str,
) -> None:
    connection = current_schema_connection
    now = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
    source_request_id = None
    failure_source_name = SOURCE_NAME
    failure_request_kind = REQUEST_KIND
    if linkage_mode == "mismatched":
        source_request_id = _insert_request(
            connection,
            requested_at=(now - timedelta(seconds=10)).isoformat(),
        )
        failure_source_name = OTHER_SOURCE_NAME
        failure_request_kind = OTHER_REQUEST_KIND
    _insert_failure(
        connection,
        source_request_id=source_request_id,
        source_name=failure_source_name,
        request_kind=failure_request_kind,
        failed_at=now.isoformat(),
        failure_type="network_error",
    )
    connection.commit()

    with pytest.raises(
        budget_accounting.SourceBudgetAccountingEvidenceError
    ) as exc_info:
        budget_accounting.recent_consumed_provider_attempts(
            connection,
            SOURCE_NAME,
            now=now,
        )
    assert exc_info.value.code == "CONSUMED_ATTEMPT_LINKAGE_AMBIGUOUS"


def test_provider_attempt_details_fail_closed_on_missing_request_timestamp(
    current_schema_connection: sqlite3.Connection,
) -> None:
    connection = current_schema_connection
    now = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
    source_request_id = _insert_request(connection, requested_at="")
    _insert_response(
        connection,
        source_request_id=source_request_id,
        received_at=now.isoformat(),
    )
    connection.commit()

    with pytest.raises(
        budget_accounting.SourceBudgetAccountingEvidenceError
    ) as exc_info:
        budget_accounting.recent_consumed_provider_attempts(
            connection,
            SOURCE_NAME,
            now=now,
        )
    assert exc_info.value.code == "CONSUMED_ATTEMPT_TIMESTAMP_AMBIGUOUS"

from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.scheduler import scheduler
from printer_v1.sources import budget_accounting, governed_execution
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.governed_execution import (
    FIXTURE_FAILURE,
    build_fixture_source_adapter,
    execute_source_request_with_governor,
)


SOURCE_NAME = "dexscreener"
REQUEST_KIND = "pair_market_snapshot"
OTHER_SOURCE_NAME = "geckoterminal"
OTHER_REQUEST_KIND = "geckoterminal_new_pool_discovery"
NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def connection(tmp_path) -> sqlite3.Connection:
    db_path = tmp_path / "current-window-frontier.sqlite3"
    apply_migrations(db_path)
    opened = sqlite3.connect(db_path)
    try:
        yield opened
    finally:
        opened.close()


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
) -> None:
    connection.execute(
        """
        INSERT INTO printer_source_responses(
            source_request_id, source_name, received_at,
            status_code, source_status, data_quality_label
        ) VALUES (?, ?, '2099-01-01T00:00:00+00:00', 200,
                  'COMPLETE', 'CLEAN_DATA')
        """,
        (source_request_id, source_name),
    )


def _insert_failure(
    connection: sqlite3.Connection,
    *,
    source_request_id: int | None,
    created_at: str,
    source_name: str = SOURCE_NAME,
    request_kind: str = REQUEST_KIND,
    failure_type: str = "network_error",
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO printer_source_failures(
            source_request_id, source_name, request_kind, failed_at,
            failure_type, failure_message, source_status,
            data_quality_label, created_at
        ) VALUES (?, ?, ?, '2099-01-01T00:00:00+00:00', ?,
                  'fixture failure', 'FAILED', 'MISSING_CRITICAL_DATA', ?)
        """,
        (
            source_request_id,
            source_name,
            request_kind,
            failure_type,
            created_at,
        ),
    )
    return int(cursor.lastrowid)


def _assert_linkage_ambiguous(connection: sqlite3.Connection) -> None:
    with pytest.raises(
        budget_accounting.SourceBudgetAccountingEvidenceError
    ) as exc_info:
        budget_accounting.recent_consumed_provider_attempts(
            connection,
            SOURCE_NAME,
            now=NOW,
        )
    assert exc_info.value.code == "CONSUMED_ATTEMPT_LINKAGE_AMBIGUOUS"


def test_historical_unlinked_failure_is_outside_the_blocking_frontier(
    connection: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _insert_failure(
        connection,
        source_request_id=None,
        created_at="2026-08-13 11:58:59",
    )
    connection.commit()

    def forbidden_activity(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("read-only projection invoked operational activity")

    monkeypatch.setattr(
        governed_execution,
        "execute_source_request_with_governor",
        forbidden_activity,
    )
    monkeypatch.setattr(scheduler, "enqueue_job", forbidden_activity)
    monkeypatch.setattr(scheduler, "claim_due_job", forbidden_activity)
    monkeypatch.setattr(scheduler, "cancel_job", forbidden_activity)

    statements: list[str] = []
    connection.set_trace_callback(statements.append)
    changes_before = connection.total_changes
    attempts = budget_accounting.recent_consumed_provider_attempts(
        connection,
        SOURCE_NAME,
        now=NOW,
    )
    count = budget_accounting.count_recent_source_requests(
        connection,
        SOURCE_NAME,
        now=NOW,
    )
    connection.set_trace_callback(None)

    assert attempts == ()
    assert count == len(attempts) == 0
    assert connection.total_changes == changes_before
    assert not any(
        statement.lstrip().upper().startswith(
            ("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP")
        )
        for statement in statements
    )


@pytest.mark.parametrize(
    "created_at",
    (
        "2026-08-13 11:59:00",
        "2026-08-13 11:59:01",
    ),
)
def test_unlinked_failure_at_or_after_cutoff_fails_closed(
    connection: sqlite3.Connection,
    created_at: str,
) -> None:
    _insert_failure(
        connection,
        source_request_id=None,
        created_at=created_at,
    )
    connection.commit()

    _assert_linkage_ambiguous(connection)


@pytest.mark.parametrize(
    "created_at",
    (
        "",
        "not-a-timestamp",
        "2026-08-13T11:58:59",
        "2026-08-13 11:58:59.000000",
        "2026-08-13 11:58:59Z",
        "2026-08-13 11:58:59+00:00",
    ),
)
def test_unlinked_failure_requires_exact_canonical_sqlite_created_at(
    connection: sqlite3.Connection,
    created_at: str,
) -> None:
    _insert_failure(
        connection,
        source_request_id=None,
        created_at=created_at,
    )
    connection.commit()

    _assert_linkage_ambiguous(connection)


@pytest.mark.parametrize(
    ("failure_source_name", "failure_request_kind"),
    (
        (OTHER_SOURCE_NAME, REQUEST_KIND),
        (SOURCE_NAME, OTHER_REQUEST_KIND),
    ),
)
def test_current_window_linked_identity_mismatch_fails_closed(
    connection: sqlite3.Connection,
    failure_source_name: str,
    failure_request_kind: str,
) -> None:
    request_id = _insert_request(
        connection,
        requested_at="2026-08-13T11:59:50+00:00",
    )
    _insert_failure(
        connection,
        source_request_id=request_id,
        source_name=failure_source_name,
        request_kind=failure_request_kind,
        created_at="2026-08-13 11:59:51",
    )
    connection.commit()

    _assert_linkage_ambiguous(connection)


def test_historical_linked_mismatch_does_not_contaminate_current_capacity(
    connection: sqlite3.Connection,
) -> None:
    request_id = _insert_request(
        connection,
        requested_at="2026-08-13T11:58:59+00:00",
    )
    _insert_failure(
        connection,
        source_request_id=request_id,
        source_name=OTHER_SOURCE_NAME,
        request_kind=OTHER_REQUEST_KIND,
        created_at="2026-08-13 11:59:30",
    )
    connection.commit()

    attempts = budget_accounting.recent_consumed_provider_attempts(
        connection,
        SOURCE_NAME,
        now=NOW,
    )

    assert attempts == ()


@pytest.mark.parametrize(
    ("created_at", "is_historical"),
    (
        ("2026-08-13 11:58:59", True),
        ("2026-08-13 11:59:00", False),
    ),
)
def test_orphan_failure_linkage_requires_strict_historical_proof(
    connection: sqlite3.Connection,
    created_at: str,
    is_historical: bool,
) -> None:
    _insert_failure(
        connection,
        source_request_id=999_999,
        created_at=created_at,
    )
    connection.commit()

    if is_historical:
        assert budget_accounting.recent_consumed_provider_attempts(
            connection,
            SOURCE_NAME,
            now=NOW,
        ) == ()
    else:
        _assert_linkage_ambiguous(connection)


def test_linked_response_and_attributable_failure_accounting_is_unchanged(
    connection: sqlite3.Connection,
) -> None:
    response_request_id = _insert_request(
        connection,
        requested_at="2026-08-13T11:59:20+00:00",
    )
    _insert_response(connection, source_request_id=response_request_id)
    failure_request_id = _insert_request(
        connection,
        requested_at="2026-08-13T11:59:40+00:00",
    )
    _insert_failure(
        connection,
        source_request_id=failure_request_id,
        created_at="2026-08-13 11:59:41",
    )
    connection.commit()

    attempts = budget_accounting.recent_consumed_provider_attempts(
        connection,
        SOURCE_NAME,
        now=NOW,
    )
    count = budget_accounting.count_recent_source_requests(
        connection,
        SOURCE_NAME,
        now=NOW,
    )

    assert tuple(
        (
            attempt.source_request_id,
            attempt.requested_at,
            str(attempt.evidence_class),
        )
        for attempt in attempts
    ) == (
        (
            response_request_id,
            datetime(2026, 8, 13, 11, 59, 20, tzinfo=timezone.utc),
            "RESPONSE_BACKED",
        ),
        (
            failure_request_id,
            datetime(2026, 8, 13, 11, 59, 40, tzinfo=timezone.utc),
            "ATTRIBUTABLE_FAILURE",
        ),
    )
    assert count == len(attempts) == 2


def test_canonical_governed_failure_persists_exact_request_lineage(
    connection: sqlite3.Connection,
) -> None:
    request = build_governed_source_request(
        SOURCE_NAME,
        REQUEST_KIND,
        now=NOW,
    )
    result = execute_source_request_with_governor(
        connection,
        request,
        build_fixture_source_adapter(SOURCE_NAME, fixture_kind=FIXTURE_FAILURE),
        now=NOW,
    )

    assert result.failure_record is not None
    assert result.failure_record.source_request_id == result.request_record.id
    persisted = connection.execute(
        """
        SELECT source_request_id
        FROM printer_source_failures
        WHERE id = ?
        """,
        (result.failure_record.id,),
    ).fetchone()
    assert persisted is not None
    assert int(persisted[0]) == result.request_record.id

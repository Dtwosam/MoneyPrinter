from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import importlib
import sqlite3
import urllib.request

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import holder_reliability_budget_control
from printer_v1.operator_cli.source_free_discovery_capacity import (
    build_source_free_discovery_attempt_manifest,
)
from printer_v1.scheduler import scheduler
from printer_v1.sources import governed_execution
from printer_v1.sources.registry import SOURCE_REGISTRY


NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
DEX = "dexscreener"
DEX_KIND = "dexscreener_fresh_profiles"
GECKO = "geckoterminal"
GECKO_KIND = "geckoterminal_trending_pool_reference"


@pytest.fixture
def connection(tmp_path) -> sqlite3.Connection:
    db_path = tmp_path / "source-free-provider-capacity.sqlite3"
    apply_migrations(db_path)
    opened = sqlite3.connect(db_path)
    try:
        yield opened
    finally:
        opened.close()


def _capacity_owner():
    return importlib.import_module(
        "printer_v1.operator_cli.source_free_discovery_provider_capacity"
    )


def _set_rate_ceiling(
    monkeypatch: pytest.MonkeyPatch,
    source_name: str,
    ceiling: int,
) -> None:
    monkeypatch.setitem(
        SOURCE_REGISTRY,
        source_name,
        replace(
            SOURCE_REGISTRY[source_name],
            default_rate_limit_per_minute=ceiling,
        ),
    )


def _insert_response_attempt(
    connection: sqlite3.Connection,
    *,
    source_name: str,
    request_kind: str,
    requested_at: datetime,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO printer_source_requests(
            source_name, request_kind, requested_at,
            source_status, data_quality_label
        ) VALUES (?, ?, ?, 'COMPLETE', 'CLEAN_DATA')
        """,
        (source_name, request_kind, requested_at.isoformat()),
    )
    request_id = int(cursor.lastrowid)
    connection.execute(
        """
        INSERT INTO printer_source_responses(
            source_request_id, source_name, received_at,
            status_code, source_status, data_quality_label
        ) VALUES (?, ?, '2099-01-01T00:00:00+00:00', 200,
                  'COMPLETE', 'CLEAN_DATA')
        """,
        (request_id, source_name),
    )
    connection.commit()
    return request_id


def _insert_failure_attempt(
    connection: sqlite3.Connection,
    *,
    source_name: str,
    request_kind: str,
    requested_at: datetime,
    failed_at: str,
    retry_after_at: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO printer_source_requests(
            source_name, request_kind, requested_at,
            source_status, data_quality_label
        ) VALUES (?, ?, ?, 'COMPLETE', 'CLEAN_DATA')
        """,
        (source_name, request_kind, requested_at.isoformat()),
    )
    request_id = int(cursor.lastrowid)
    connection.execute(
        """
        INSERT INTO printer_source_failures(
            source_request_id, source_name, request_kind, failed_at,
            failure_type, failure_message, source_status,
            data_quality_label, retry_after_at
        ) VALUES (?, ?, ?, ?, 'network_error', 'fixture failure',
                  'FAILED', 'MISSING_CRITICAL_DATA', ?)
        """,
        (request_id, source_name, request_kind, failed_at, retry_after_at),
    )
    connection.commit()
    return request_id


def _snapshots_by_source(result) -> dict[str, object]:
    return {snapshot.source_name: snapshot for snapshot in result.provider_snapshots}


def test_package_fit_uses_current_attempts_manifest_totals_and_registry_ceiling(
    connection: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _capacity_owner()
    _set_rate_ceiling(monkeypatch, DEX, 2)
    manifest = build_source_free_discovery_attempt_manifest()
    _insert_response_attempt(
        connection,
        source_name=DEX,
        request_kind=DEX_KIND,
        requested_at=NOW - timedelta(seconds=10),
    )

    result = owner.compose_later_cycle_discovery_capacity(
        connection,
        manifest=manifest,
        now=NOW,
    )
    snapshots = _snapshots_by_source(result)
    dex = snapshots[DEX]

    assert (dex.consumed_attempt_count, dex.package_required_attempts) == (1, 1)
    assert dex.rate_ceiling == 2
    assert dex.package_fits_now is True
    assert dex.package_ready_at is None
    assert dex.reason == "PACKAGE_FITS_CURRENT_PROVIDER_WINDOW"
    assert all(
        snapshot.package_required_attempts
        == manifest.provider_governed_request_totals[snapshot.source_name]
        for snapshot in result.provider_snapshots
    )
    assert all(
        snapshot.rate_ceiling
        == SOURCE_REGISTRY[snapshot.source_name].default_rate_limit_per_minute
        for snapshot in result.provider_snapshots
    )


def test_package_requirement_above_registry_ceiling_has_no_future_boundary(
    connection: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _capacity_owner()
    _set_rate_ceiling(monkeypatch, DEX, 0)

    result = owner.compose_later_cycle_discovery_capacity(
        connection,
        manifest=build_source_free_discovery_attempt_manifest(),
        now=NOW,
    )
    dex = _snapshots_by_source(result)[DEX]

    assert (dex.consumed_attempt_count, dex.package_required_attempts) == (0, 1)
    assert dex.rate_ceiling == 0
    assert dex.package_fits_now is False
    assert dex.package_ready_at is None
    assert dex.evidence_complete is True
    assert dex.reason == "PACKAGE_REQUIREMENT_EXCEEDS_PROVIDER_RATE_CEILING"
    assert result.provider_budgets_available is False
    assert result.recheck_at is None


def test_inclusive_window_expires_at_first_representable_instant_after_sixty_seconds(
    connection: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _capacity_owner()
    _set_rate_ceiling(monkeypatch, DEX, 1)
    attempted_at = datetime(2026, 8, 13, 11, 59, tzinfo=timezone.utc)
    request_id = _insert_response_attempt(
        connection,
        source_name=DEX,
        request_kind=DEX_KIND,
        requested_at=attempted_at,
    )
    manifest = build_source_free_discovery_attempt_manifest()

    exact_boundary = owner.compose_later_cycle_discovery_capacity(
        connection,
        manifest=manifest,
        now=datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc),
    )
    exact_dex = _snapshots_by_source(exact_boundary)[DEX]
    assert exact_dex.consumed_attempt_count == 1
    assert tuple(row.source_request_id for row in exact_dex.consumed_attempts) == (
        request_id,
    )
    assert exact_dex.package_fits_now is False
    assert exact_dex.package_ready_at == datetime(
        2026, 8, 13, 12, 0, 0, 1, tzinfo=timezone.utc
    )

    first_after = owner.compose_later_cycle_discovery_capacity(
        connection,
        manifest=manifest,
        now=datetime(2026, 8, 13, 12, 0, 0, 1, tzinfo=timezone.utc),
    )
    after_dex = _snapshots_by_source(first_after)[DEX]
    assert after_dex.consumed_attempt_count == 0
    assert after_dex.package_fits_now is True
    assert after_dex.package_ready_at is None


def test_blocked_provider_boundary_uses_needed_expiration_index(
    connection: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _capacity_owner()
    _set_rate_ceiling(monkeypatch, DEX, 3)
    request_ids = tuple(
        _insert_response_attempt(
            connection,
            source_name=DEX,
            request_kind=DEX_KIND,
            requested_at=requested_at,
        )
        for requested_at in (
            NOW - timedelta(seconds=50),
            NOW - timedelta(seconds=40),
            NOW - timedelta(seconds=30),
            NOW - timedelta(seconds=20),
        )
    )

    result = owner.compose_later_cycle_discovery_capacity(
        connection,
        manifest=build_source_free_discovery_attempt_manifest(),
        now=NOW,
    )
    dex = _snapshots_by_source(result)[DEX]

    assert (dex.consumed_attempt_count, dex.package_required_attempts) == (4, 1)
    assert tuple(row.source_request_id for row in dex.consumed_attempts) == request_ids
    assert dex.package_fits_now is False
    assert dex.package_ready_at == NOW + timedelta(seconds=20, microseconds=1)
    assert dex.reason == "PACKAGE_BLOCKED_BY_CURRENT_PROVIDER_CONSUMPTION"


def test_multiple_blocked_providers_use_latest_whole_package_boundary(
    connection: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _capacity_owner()
    _set_rate_ceiling(monkeypatch, DEX, 1)
    _set_rate_ceiling(monkeypatch, GECKO, 2)
    _insert_response_attempt(
        connection,
        source_name=DEX,
        request_kind=DEX_KIND,
        requested_at=NOW - timedelta(seconds=50),
    )
    _insert_response_attempt(
        connection,
        source_name=GECKO,
        request_kind=GECKO_KIND,
        requested_at=NOW - timedelta(seconds=20),
    )

    result = owner.compose_later_cycle_discovery_capacity(
        connection,
        manifest=build_source_free_discovery_attempt_manifest(),
        now=NOW,
    )
    snapshots = _snapshots_by_source(result)

    assert snapshots[DEX].package_ready_at == NOW + timedelta(
        seconds=10, microseconds=1
    )
    assert snapshots[GECKO].package_ready_at == NOW + timedelta(
        seconds=40, microseconds=1
    )
    assert result.provider_budgets_available is False
    assert result.recheck_at == NOW + timedelta(seconds=40, microseconds=1)


def test_any_blocked_provider_without_future_boundary_removes_composed_recheck(
    connection: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _capacity_owner()
    _set_rate_ceiling(monkeypatch, DEX, 1)
    _set_rate_ceiling(monkeypatch, GECKO, 1)
    _insert_response_attempt(
        connection,
        source_name=DEX,
        request_kind=DEX_KIND,
        requested_at=NOW - timedelta(seconds=10),
    )

    result = owner.compose_later_cycle_discovery_capacity(
        connection,
        manifest=build_source_free_discovery_attempt_manifest(),
        now=NOW,
    )

    assert _snapshots_by_source(result)[DEX].package_ready_at is not None
    assert _snapshots_by_source(result)[GECKO].reason == (
        "PACKAGE_REQUIREMENT_EXCEEDS_PROVIDER_RATE_CEILING"
    )
    assert result.recheck_at is None


def test_intervening_consumption_changes_fresh_projection_without_reservation(
    connection: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _capacity_owner()
    _set_rate_ceiling(monkeypatch, DEX, 1)
    manifest = build_source_free_discovery_attempt_manifest()

    before = owner.compose_later_cycle_discovery_capacity(
        connection,
        manifest=manifest,
        now=NOW,
    )
    assert _snapshots_by_source(before)[DEX].package_fits_now is True
    assert before.provider_budgets_available is True

    _insert_response_attempt(
        connection,
        source_name=DEX,
        request_kind=DEX_KIND,
        requested_at=NOW,
    )
    after = owner.compose_later_cycle_discovery_capacity(
        connection,
        manifest=manifest,
        now=NOW,
    )

    assert _snapshots_by_source(after)[DEX].package_fits_now is False
    assert _snapshots_by_source(after)[DEX].package_ready_at == NOW + timedelta(
        seconds=60, microseconds=1
    )
    assert after.provider_budgets_available is False


def test_discovery_shape_validity_is_independent_of_provider_availability(
    connection: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _capacity_owner()
    _set_rate_ceiling(monkeypatch, DEX, 0)
    manifest = build_source_free_discovery_attempt_manifest()

    blocked = owner.compose_later_cycle_discovery_capacity(
        connection,
        manifest=manifest,
        now=NOW,
    )
    assert blocked.manifest_valid is True
    assert blocked.discovery_capacity_available is True
    assert blocked.provider_budgets_available is False

    invalid = owner.compose_later_cycle_discovery_capacity(
        connection,
        manifest=replace(manifest, target_count=3),
        now=NOW,
    )
    assert invalid.manifest_valid is False
    assert invalid.discovery_capacity_available is False
    assert invalid.provider_budgets_available is False
    assert invalid.provider_snapshots == ()
    assert invalid.recheck_at is None
    assert invalid.reasons == (
        "DISCOVERY_ATTEMPT_MANIFEST_INVALID:EXACT_TWO_TOKEN_TARGET_REQUIRED",
    )


def test_ambiguous_attempt_evidence_fails_closed_without_synthetic_recheck(
    connection: sqlite3.Connection,
) -> None:
    owner = _capacity_owner()
    connection.execute(
        """
        INSERT INTO printer_source_failures(
            source_request_id, source_name, request_kind, failed_at,
            failure_type, failure_message, source_status,
            data_quality_label, created_at
        ) VALUES (NULL, ?, ?, '2099-01-01T00:00:00+00:00',
                  'network_error', 'fixture failure', 'FAILED',
                  'MISSING_CRITICAL_DATA', '2026-08-13 11:59:30')
        """,
        (DEX, DEX_KIND),
    )
    connection.commit()

    result = owner.compose_later_cycle_discovery_capacity(
        connection,
        manifest=build_source_free_discovery_attempt_manifest(),
        now=NOW,
    )
    dex = _snapshots_by_source(result)[DEX]

    assert dex.consumed_attempts == ()
    assert dex.consumed_attempt_count is None
    assert dex.package_fits_now is False
    assert dex.package_ready_at is None
    assert dex.evidence_complete is False
    assert dex.reason == (
        "PROVIDER_ATTEMPT_EVIDENCE_INCOMPLETE:"
        "CONSUMED_ATTEMPT_LINKAGE_AMBIGUOUS:printer_source_failures:1"
    )
    assert result.manifest_valid is True
    assert result.discovery_capacity_available is True
    assert result.provider_budgets_available is False
    assert result.recheck_at is None


def test_projection_uses_request_time_only_and_performs_no_operational_activity(
    connection: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _capacity_owner()
    _set_rate_ceiling(monkeypatch, DEX, 1)
    attempted_at = NOW - timedelta(seconds=15)
    _insert_failure_attempt(
        connection,
        source_name=DEX,
        request_kind=DEX_KIND,
        requested_at=attempted_at,
        failed_at="1999-01-01T00:00:00+00:00",
        retry_after_at="2099-01-01T00:00:00+00:00",
    )

    def forbidden_activity(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("capacity projection invoked operational activity")

    monkeypatch.setattr(sqlite3, "connect", forbidden_activity)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden_activity)
    monkeypatch.setattr(
        governed_execution,
        "execute_source_request_with_governor",
        forbidden_activity,
    )
    monkeypatch.setattr(scheduler, "enqueue_job", forbidden_activity)
    monkeypatch.setattr(scheduler, "claim_due_job", forbidden_activity)
    monkeypatch.setattr(scheduler, "cancel_job", forbidden_activity)
    monkeypatch.setattr(
        holder_reliability_budget_control,
        "SequentialRequestPacer",
        forbidden_activity,
    )

    statements: list[str] = []
    connection.set_trace_callback(statements.append)
    changes_before = connection.total_changes
    result = owner.compose_later_cycle_discovery_capacity(
        connection,
        manifest=build_source_free_discovery_attempt_manifest(),
        now=NOW,
    )
    connection.set_trace_callback(None)
    dex = _snapshots_by_source(result)[DEX]

    assert dex.package_ready_at == attempted_at + timedelta(
        seconds=60, microseconds=1
    )
    assert connection.total_changes == changes_before
    assert not any(
        statement.lstrip().upper().startswith(
            ("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP")
        )
        for statement in statements
    )
    with pytest.raises(FrozenInstanceError):
        dex.package_fits_now = True
    with pytest.raises(FrozenInstanceError):
        result.provider_budgets_available = True

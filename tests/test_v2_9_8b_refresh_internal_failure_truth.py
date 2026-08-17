"""Slice F: refresh-stage exceptions keep source and internal failures distinct."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from printer_v1.db import apply_migrations
from printer_v1.discovery.pre_lifecycle_refresh_composition import (
    PreLifecycleRefreshCompositionError,
)
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    INTERNAL_INVARIANT,
    INTERNAL_RUNTIME_ERROR,
    REFRESH_SOURCE_FAILURE,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    LiveTransportError,
)
from printer_v1.operator_cli.pre_lifecycle_persistent_refresh_owner import (
    FAILURE_DOMAIN_INTERNAL,
    FAILURE_DOMAIN_SOURCE,
    PreLifecycleTemporalRefreshError,
    PreLifecycleTemporalRefreshOwner,
    classify_refresh_stage_exception,
)


NOW = datetime(2026, 8, 17, 16, 0, tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _clock(current: list[datetime]):
    def clock() -> str:
        return _iso(current[0])

    return clock


def _waiter(current: list[datetime]):
    def waiter(seconds: float) -> bool:
        current[0] = current[0] + timedelta(seconds=seconds)
        return False

    return waiter


def _owner(tmp_path: Path, *, stage, current: list[datetime] | None = None):
    ticks = current or [NOW]
    return PreLifecycleTemporalRefreshOwner(
        tmp_path / "refresh-f.sqlite3",
        campaign_id="campaign-f",
        run_id="run-f",
        cycle_id="cycle-f",
        supervision_id="supervision-f",
        source_governor=True,
        central_scheduler=True,
        acquisition_deadline_at="2026-08-17T16:40:00+00:00",
        work_deadline_at="2026-08-17T17:00:00+00:00",
        refresh_stage=stage,
        supervision_probe=lambda: {
            "supervision_active": True,
            "cancellation_requested": False,
        },
        waiter=_waiter(ticks),
        clock=_clock(ticks),
        refresh_interval_seconds=600,
    )


def _request(owner, *, remaining: int = 10):
    apply_migrations(owner.db_path)
    return owner.request_temporal_refresh(
        reserve_depth=2,
        required_capacity=4,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=remaining,
        provider_terminal_failure=False,
        now=_iso(NOW),
    )


def _insert_complete_clean(connection: sqlite3.Connection, request_key: str) -> int:
    request_id = int(
        connection.execute(
            "INSERT INTO printer_source_requests("
            "source_name,request_kind,requested_at,request_key,source_status,"
            "data_quality_label) VALUES ('solana_rpc',"
            "'restored_pump_migration_transaction',?,?, 'COMPLETE','CLEAN_DATA')",
            (_iso(NOW), request_key),
        ).lastrowid
    )
    connection.execute(
        "INSERT INTO printer_source_responses("
        "source_request_id,source_name,received_at,source_status,data_quality_label) "
        "VALUES (?,'solana_rpc',?,'COMPLETE','CLEAN_DATA')",
        (request_id, _iso(NOW)),
    )
    connection.commit()
    return request_id


def test_classify_transport_and_rate_failures_are_source() -> None:
    status, domain, cause = classify_refresh_stage_exception(
        LiveTransportError("TRANSPORT_UNAVAILABLE", "getTransaction")
    )
    assert status == REFRESH_SOURCE_FAILURE
    assert domain == FAILURE_DOMAIN_SOURCE
    assert "SOURCE_FAILURE" in cause
    status, domain, _cause = classify_refresh_stage_exception(
        LiveTransportError("HTTP_429", "getSignaturesForAddress")
    )
    assert status == REFRESH_SOURCE_FAILURE
    assert domain == FAILURE_DOMAIN_SOURCE


def test_classify_known_internal_and_unexpected_runtime() -> None:
    status, domain, cause = classify_refresh_stage_exception(
        PreLifecycleRefreshCompositionError("DIRECT_PUMP_REFRESH_ACCOUNTING_BLOCKED")
    )
    assert status == INTERNAL_INVARIANT
    assert domain == FAILURE_DOMAIN_INTERNAL
    assert "INTERNAL_INVARIANT" in cause
    status, domain, cause = classify_refresh_stage_exception(RuntimeError("boom"))
    assert status == INTERNAL_RUNTIME_ERROR
    assert domain == FAILURE_DOMAIN_INTERNAL
    assert "INTERNAL_RUNTIME" in cause


def test_governed_provider_transport_failure_is_source(tmp_path) -> None:
    def stage(connection, **kwargs):
        del connection, kwargs
        raise LiveTransportError("TRANSPORT_UNAVAILABLE", "getTransaction")

    outcome = _request(_owner(tmp_path, stage=stage))
    assert outcome.status == REFRESH_SOURCE_FAILURE
    assert outcome.failure_domain == FAILURE_DOMAIN_SOURCE
    assert outcome.provider_failures == 1


def test_governed_rate_source_failure_is_source(tmp_path) -> None:
    def stage(connection, **kwargs):
        del connection, kwargs
        raise LiveTransportError("HTTP_429", "dexscreener")

    outcome = _request(_owner(tmp_path, stage=stage))
    assert outcome.status == REFRESH_SOURCE_FAILURE
    assert outcome.failure_domain == FAILURE_DOMAIN_SOURCE
    assert outcome.provider_failures == 1


def test_accounting_identity_after_success_is_internal(tmp_path) -> None:
    def stage(connection, **kwargs):
        _insert_complete_clean(connection, "cycle-f-success-then-identity")
        return {
            "source_operations": 1,
            "provider_failures": 0,
            "channels_unavailable": (),
            "campaign_id": "campaign-f",
            "run_id": "run-f",
            "cycle_id": "wrong-cycle",
        }

    outcome = _request(_owner(tmp_path, stage=stage))
    assert outcome.status == INTERNAL_INVARIANT
    assert outcome.failure_domain == FAILURE_DOMAIN_INTERNAL
    assert outcome.provider_failures == 0
    assert outcome.source_operations == 1
    db = sqlite3.connect(tmp_path / "refresh-f.sqlite3")
    row = db.execute(
        "SELECT source_status,data_quality_label FROM printer_source_responses"
    ).fetchone()
    db.close()
    assert row == ("COMPLETE", "CLEAN_DATA")


def test_malformed_internal_stage_evidence_is_internal(tmp_path) -> None:
    def stage(connection, **kwargs):
        del connection, kwargs
        return {"source_operations": "two", "provider_failures": 0}

    outcome = _request(_owner(tmp_path, stage=stage))
    assert outcome.status == INTERNAL_INVARIANT
    assert outcome.failure_domain == FAILURE_DOMAIN_INTERNAL
    assert outcome.provider_failures == 0


def test_unexpected_local_exception_is_internal_runtime(tmp_path) -> None:
    def stage(connection, **kwargs):
        del connection, kwargs
        raise RuntimeError("local programming accident")

    outcome = _request(_owner(tmp_path, stage=stage))
    assert outcome.status == INTERNAL_RUNTIME_ERROR
    assert outcome.failure_domain == FAILURE_DOMAIN_INTERNAL
    assert outcome.provider_failures == 0


def test_complete_clean_survives_later_internal_exception(tmp_path) -> None:
    def stage(connection, **kwargs):
        _insert_complete_clean(connection, "cycle-f-complete-survives")
        raise PreLifecycleTemporalRefreshError(
            "PRE_LIFECYCLE_REFRESH_STAGE_IDENTITY_MISMATCH:cycle_id"
        )

    outcome = _request(_owner(tmp_path, stage=stage))
    assert outcome.status == INTERNAL_INVARIANT
    assert outcome.failure_domain == FAILURE_DOMAIN_INTERNAL
    assert outcome.provider_failures == 0
    db = sqlite3.connect(tmp_path / "refresh-f.sqlite3")
    request = db.execute(
        "SELECT source_status,data_quality_label FROM printer_source_requests"
    ).fetchone()
    response = db.execute(
        "SELECT source_status,data_quality_label FROM printer_source_responses"
    ).fetchone()
    failures = db.execute("SELECT COUNT(*) FROM printer_source_failures").fetchone()[0]
    db.close()
    assert request == ("COMPLETE", "CLEAN_DATA")
    assert response == ("COMPLETE", "CLEAN_DATA")
    assert int(failures) == 0


def test_internal_failure_does_not_increment_source_failure_counters(tmp_path) -> None:
    def stage(connection, **kwargs):
        del connection, kwargs
        raise PreLifecycleRefreshCompositionError("DIRECT_PUMP_REFRESH_ACCOUNTING_BLOCKED")

    outcome = _request(_owner(tmp_path, stage=stage))
    assert outcome.status == INTERNAL_INVARIANT
    assert outcome.provider_failures == 0
    assert outcome.failure_domain != FAILURE_DOMAIN_SOURCE

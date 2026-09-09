"""V2-9.8B downstream paper financial capability-lock regression.

Disposable SQLite only. The implemented paper position/monitor, audit, and PnL
subsystems remain inspectable as history/contracts, but their current activation
surfaces must fail closed until a separate deliberate capability change enables
them.
"""

from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

import pytest

from printer_v1.contracts import capability_locks
from printer_v1.contracts.capability_locks import CapabilityLockedError
from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db.migrate import apply_migrations
from printer_v1.hardening.flow_validation import (
    run_synthetic_paper_audit,
    run_synthetic_paper_monitor,
)
from printer_v1.lifecycle.contracts import LifecycleEvent, TokenLifecycleState
from printer_v1.lifecycle.tracking_queue import (
    claim_tracking_item,
    get_due_tracking_items,
    record_lifecycle_event,
    sync_tracking_state_with_scheduler,
    update_tracking_lane,
)
from printer_v1.paper_audit.classifier import (
    classify_paper_audit_result,
    paper_audit_passes,
)
from printer_v1.paper_audit.recorder import (
    build_and_record_paper_audit,
    build_audit_payload,
    enqueue_paper_audit_job,
    get_latest_paper_audit,
    get_paper_audits_for_position,
    record_paper_audit_report,
)
from printer_v1.paper_audit.reports import build_paper_audit_report
from printer_v1.paper_monitor.events import (
    build_paper_trade_event_payload,
    event_has_no_live_execution,
    event_is_paper_only,
)
from printer_v1.paper_monitor.monitor import (
    build_monitor_update,
    build_paper_exit_payload,
    classify_exit_reason,
    classify_paper_monitor_state,
    paper_position_should_close,
)
from printer_v1.paper_monitor.positions import (
    calculate_paper_token_amount,
    calculate_realized_pnl,
    calculate_unrealized_pnl,
    classify_entry_status,
    classify_paper_pnl_state,
)
from printer_v1.paper_monitor.recorder import (
    close_paper_position,
    enqueue_paper_monitor_job,
    get_latest_paper_position,
    get_open_paper_positions,
    monitor_paper_position,
    open_paper_position_from_decision,
    record_paper_position,
    record_paper_trade_audit,
    record_paper_trade_event,
)
from printer_v1.paper_monitor.reports import (
    report_is_paper_only,
    summarize_paper_pnl,
)
from printer_v1.scheduler import scheduler
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.snapshots.contracts import (
    CoverageLabel,
    SnapshotGapLabel,
    SnapshotMode,
)
from printer_v1.snapshots.recorder import (
    enqueue_next_snapshot_job,
    record_snapshot_gap_audit,
    record_token_snapshot,
)


NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "paper-financial-lockout.sqlite3"
    apply_migrations(path)
    monkeypatch.setattr(capability_locks, "PAPER_POSITIONS_ENABLED", False)
    monkeypatch.setattr(capability_locks, "PAPER_AUDITS_ENABLED", False)
    monkeypatch.setattr(capability_locks, "PAPER_PNL_ENABLED", False)
    return path


def _count(path, table: str) -> int:
    connection = sqlite3.connect(path)
    try:
        return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        connection.close()


def _insert_token_pair(path) -> tuple[int, int]:
    connection = sqlite3.connect(path)
    try:
        token_id = int(
            connection.execute(
                "INSERT INTO printer_tokens(token_mint,chain) VALUES ('paper-lock-mint','solana')"
            ).lastrowid
        )
        pair_id = int(
            connection.execute(
                "INSERT INTO printer_pairs(token_id,pair_address,dex,pool_source) "
                "VALUES (?,'paper-lock-pair','pumpswap','fixture')",
                (token_id,),
            ).lastrowid
        )
        connection.commit()
        return token_id, pair_id
    finally:
        connection.close()


def _assert_locked(
    exc: pytest.ExceptionInfo[CapabilityLockedError],
    code: str,
) -> None:
    assert exc.value.code == code
    assert str(exc.value) == code


def test_current_downstream_paper_capabilities_default_locked() -> None:
    assert capability_locks.PAPER_POSITIONS_ENABLED is False
    assert capability_locks.PAPER_AUDITS_ENABLED is False
    assert capability_locks.PAPER_PNL_ENABLED is False


def test_position_monitor_and_pnl_outputs_fail_closed(db_path) -> None:
    decision = {
        "id": 1,
        "decision_gate_label": "DECISION_ALLOWED",
        "paper_decision_status_label": "PAPER_DECISION_PROPOSED",
        "final_action_label": "BUY",
    }
    entry_evidence = {
        "token_snapshot": {"price_usd": 1.0},
        "liquidity_exit": {
            "entry_realism_label": "ENTRY_REALISTIC",
            "exit_realism_label": "EXIT_REALISTIC",
        },
        "safety": {"safety_status_label": "SAFETY_CLEAN"},
    }
    position = {
        "id": 1,
        "paper_decision_id": 1,
        "paper_position_status_label": "PAPER_POSITION_OPEN",
        "entry_price_usd": 1.0,
        "paper_token_amount": 100.0,
        "current_price_usd": 1.2,
    }
    monitor_evidence = {"token_snapshot": {"price_usd": 1.2}}

    for callable_, args in (
        (classify_entry_status, (decision, entry_evidence)),
        (calculate_paper_token_amount, (100.0, 1.0)),
        (classify_paper_monitor_state, (position, monitor_evidence)),
        (classify_exit_reason, (position, monitor_evidence)),
        (paper_position_should_close, (position, monitor_evidence)),
        (build_paper_trade_event_payload, (1, 1, 1, 1, "position_opened")),
    ):
        with pytest.raises(CapabilityLockedError) as exc:
            callable_(*args)
        _assert_locked(exc, "PAPER_POSITIONS_LOCKED")

    for callable_, args in (
        (calculate_unrealized_pnl, (1.0, 1.2, 100.0)),
        (calculate_realized_pnl, (1.0, 1.2, 100.0)),
        (classify_paper_pnl_state, (20.0, None)),
        (summarize_paper_pnl, ({"realized_pnl_usd": 20.0},)),
    ):
        with pytest.raises(CapabilityLockedError) as exc:
            callable_(*args)
        _assert_locked(exc, "PAPER_PNL_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        build_paper_exit_payload(position, monitor_evidence, NOW)
    _assert_locked(exc, "PAPER_POSITIONS_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        build_monitor_update(db_path, 1)
    _assert_locked(exc, "PAPER_POSITIONS_LOCKED")


def test_position_monitor_recorders_and_synthetic_bypass_fail_before_write(db_path) -> None:
    for callable_, args in (
        (record_paper_position, (db_path, {})),
        (record_paper_trade_event, (db_path, {})),
        (open_paper_position_from_decision, (db_path, 1, NOW)),
        (monitor_paper_position, (db_path, 1)),
        (close_paper_position, (db_path, 1, {}, NOW)),
        (enqueue_paper_monitor_job, (db_path, 1, NOW, "locked")),
        (run_synthetic_paper_monitor, (db_path,)),
    ):
        with pytest.raises(CapabilityLockedError) as exc:
            callable_(*args)
        _assert_locked(exc, "PAPER_POSITIONS_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        record_paper_trade_audit(db_path, {})
    _assert_locked(exc, "PAPER_AUDITS_LOCKED")

    assert _count(db_path, "printer_paper_positions") == 0
    assert _count(db_path, "printer_paper_trade_events") == 0
    assert _count(db_path, "printer_paper_trade_audits") == 0
    assert _count(db_path, "printer_scheduler_jobs") == 0


def test_paper_audit_outputs_and_writes_fail_closed(db_path) -> None:
    for callable_, args in (
        (classify_paper_audit_result, ({},)),
        (paper_audit_passes, ({},)),
        (build_audit_payload, ({}, NOW)),
        (record_paper_audit_report, (db_path, {})),
        (build_and_record_paper_audit, (db_path,)),
        (enqueue_paper_audit_job, (db_path, 1, 1, NOW, "locked")),
        (run_synthetic_paper_audit, (db_path,)),
        (
            build_paper_audit_report,
            (
                {},
                {
                    "audit_issues": [],
                    "paper_audit_result_label": "PAPER_AUDIT_PASS",
                },
            ),
        ),
    ):
        with pytest.raises(CapabilityLockedError) as exc:
            callable_(*args)
        _assert_locked(exc, "PAPER_AUDITS_LOCKED")

    assert _count(db_path, "printer_paper_audit_reports") == 0
    assert _count(db_path, "printer_scheduler_jobs") == 0


def test_paper_monitoring_lane_and_snapshot_activation_are_unreachable(db_path) -> None:
    token_id, pair_id = _insert_token_pair(db_path)

    with pytest.raises(CapabilityLockedError) as exc:
        claim_tracking_item(
            db_path,
            token_id=token_id,
            pair_id=pair_id,
            tracking_lane=TokenLifecycleState.PAPER_MONITORING,
            tracking_action=LifecycleEvent.ENTER_PAPER_MONITORING,
            priority_reason="must-remain-locked",
            next_check_at=NOW,
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.CLEAN_DATA,
        )
    _assert_locked(exc, "PAPER_POSITIONS_LOCKED")
    assert _count(db_path, "printer_tracking_queue") == 0

    created, queue_id = claim_tracking_item(
        db_path,
        token_id=token_id,
        pair_id=pair_id,
        tracking_lane=TokenLifecycleState.TRACK_FAST,
        tracking_action=LifecycleEvent.PROMOTE_TO_TRACK_FAST,
        priority_reason="ordinary-track-fast",
        next_check_at=NOW,
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
    )
    assert created is True
    assert queue_id is not None

    with pytest.raises(CapabilityLockedError) as exc:
        update_tracking_lane(
            db_path,
            queue_id=queue_id,
            tracking_lane=TokenLifecycleState.PAPER_MONITORING,
            tracking_action=LifecycleEvent.ENTER_PAPER_MONITORING,
            priority_reason="must-remain-locked",
            next_check_at=NOW,
        )
    _assert_locked(exc, "PAPER_POSITIONS_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        record_lifecycle_event(
            db_path,
            token_id=token_id,
            pair_id=pair_id,
            previous_state=TokenLifecycleState.TRACK_FAST,
            new_state=TokenLifecycleState.PAPER_MONITORING,
            lifecycle_event=LifecycleEvent.ENTER_PAPER_MONITORING,
            priority_reason="must-remain-locked",
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.CLEAN_DATA,
        )
    _assert_locked(exc, "PAPER_POSITIONS_LOCKED")
    assert _count(db_path, "printer_token_lifecycle_events") == 0

    paper_snapshot = {
        "token_id": token_id,
        "pair_id": pair_id,
        "captured_at": NOW.isoformat(),
        "tracking_lane": TokenLifecycleState.PAPER_MONITORING.value,
        "snapshot_mode": SnapshotMode.PAPER_EXIT_PROTECTION_MODE.value,
        "price_usd": 1.0,
        "liquidity_usd": 50_000,
        "source_status": SourceStatus.COMPLETE.value,
        "data_quality_label": DataQualityLabel.CLEAN_DATA.value,
    }
    with pytest.raises(CapabilityLockedError) as exc:
        record_token_snapshot(db_path, paper_snapshot, NOW)
    _assert_locked(exc, "PAPER_POSITIONS_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        enqueue_next_snapshot_job(
            db_path,
            token_id,
            pair_id,
            TokenLifecycleState.PAPER_MONITORING,
            SnapshotMode.PAPER_EXIT_PROTECTION_MODE,
            NOW,
        )
    _assert_locked(exc, "PAPER_POSITIONS_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        record_snapshot_gap_audit(
            db_path,
            token_id=token_id,
            pair_id=pair_id,
            tracking_lane=TokenLifecycleState.PAPER_MONITORING,
            snapshot_mode=SnapshotMode.PAPER_EXIT_PROTECTION_MODE,
            expected_captured_at=NOW,
            actual_captured_at=None,
            gap_seconds=60,
            snapshot_gap_label=SnapshotGapLabel.MINOR_GAP,
            coverage_label=CoverageLabel.PARTIAL_COVERAGE,
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.CLEAN_DATA,
        )
    _assert_locked(exc, "PAPER_POSITIONS_LOCKED")

    assert _count(db_path, "printer_token_snapshots") == 0
    assert _count(db_path, "printer_snapshot_gap_audits") == 0
    assert _count(db_path, "printer_scheduler_jobs") == 0

    due = get_due_tracking_items(db_path, now=NOW)
    assert [row["tracking_lane"] for row in due] == [TokenLifecycleState.TRACK_FAST.value]


def test_central_scheduler_cannot_bypass_paper_financial_locks(db_path) -> None:
    acquired, ordinary_job_id = scheduler.enqueue_job(
        db_path,
        job_name="ordinary-memory-close",
        job_kind=JobKind.MEMORY_WINDOW_CLOSE,
        target_table="printer_memory_windows",
        target_id=1,
        scheduled_for=NOW,
    )
    assert acquired is LockResult.ACQUIRED
    assert ordinary_job_id is not None

    with pytest.raises(CapabilityLockedError) as exc:
        scheduler.enqueue_job(
            db_path,
            job_name="forbidden-position-target",
            job_kind=JobKind.MEMORY_WINDOW_CLOSE,
            target_table="printer_paper_positions",
            target_id=1,
            scheduled_for=NOW,
        )
    _assert_locked(exc, "PAPER_POSITIONS_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        scheduler.enqueue_job(
            db_path,
            job_name="forbidden-audit-target",
            job_kind=JobKind.MEMORY_WINDOW_CLOSE,
            target_table="printer_paper_audit_reports",
            target_id=1,
            scheduled_for=NOW,
        )
    _assert_locked(exc, "PAPER_AUDITS_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        scheduler.enqueue_job(
            db_path,
            job_name="forbidden-monitor-kind",
            job_kind=JobKind.OPEN_PAPER_TRADE_MONITOR,
            target_table="printer_token_snapshots",
            target_id=1,
            scheduled_for=NOW,
        )
    _assert_locked(exc, "PAPER_POSITIONS_LOCKED")

    assert _count(db_path, "printer_scheduler_jobs") == 1


def test_read_only_downstream_history_inspection_remains_available(db_path) -> None:
    assert get_open_paper_positions(db_path) == []
    assert get_latest_paper_position(db_path) is None
    assert get_latest_paper_audit(db_path) is None
    assert get_paper_audits_for_position(db_path, 1) == []

    historical_event = {
        "event_payload": {"paper_only": True, "live_execution": False}
    }
    assert event_is_paper_only(historical_event) is True
    assert event_has_no_live_execution(historical_event) is True
    assert report_is_paper_only({"mode": "paper_only", "live_execution": False}) is True

    assert _count(db_path, "printer_paper_positions") == 0
    assert _count(db_path, "printer_paper_trade_events") == 0
    assert _count(db_path, "printer_paper_trade_audits") == 0
    assert _count(db_path, "printer_paper_audit_reports") == 0

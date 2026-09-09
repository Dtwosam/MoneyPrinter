"""V2-9.8B clean-memory consumer capability-lock regression.

Disposable SQLite only. Proves that completed/clean memory remains inspectable,
but retrieval activation and paper-decision output/writes/Scheduler targeting
stay fail-closed until a separate deliberate capability change enables them.
"""

from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

import pytest

from printer_v1.contracts import capability_locks
from printer_v1.contracts.capability_locks import CapabilityLockedError
from printer_v1.db.migrate import apply_migrations
from printer_v1.hardening.flow_validation import (
    run_synthetic_memory_retrieval,
    run_synthetic_paper_decision,
)
from printer_v1.memory.fingerprints import record_memory_fingerprint
from printer_v1.memory_retrieval.recorder import (
    build_and_record_memory_retrieval_report,
    enqueue_memory_retrieval_job,
    record_memory_retrieval_matches,
    record_memory_retrieval_query,
)
from printer_v1.memory_retrieval.retriever import (
    retrieve_memory_matches_for_current_setup,
)
from printer_v1.paper_decision.classifier import (
    classify_final_paper_action,
    classify_paper_decision_status,
    classify_requested_action_from_memory_evidence,
    paper_decision_can_be_recorded,
    paper_decision_can_open_position_later,
)
from printer_v1.paper_decision.recorder import (
    build_and_record_paper_decision,
    build_decision_payload,
    enqueue_paper_decision_job,
    get_latest_paper_decision,
    record_paper_decision,
    record_paper_decision_audit,
)
from printer_v1.scheduler import scheduler
from printer_v1.scheduler.contracts import JobKind, LockResult


NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "consumer-lockout.sqlite3"
    apply_migrations(path)
    monkeypatch.setattr(capability_locks, "RETRIEVAL_ACTIVATION_ENABLED", False)
    monkeypatch.setattr(capability_locks, "PAPER_DECISIONS_ENABLED", False)
    return path


def _count(path, table: str) -> int:
    connection = sqlite3.connect(path)
    try:
        return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        connection.close()


def _assert_locked(exc: pytest.ExceptionInfo[CapabilityLockedError], code: str) -> None:
    assert exc.value.code == code
    assert str(exc.value) == code


def test_current_consumer_capabilities_default_locked() -> None:
    assert capability_locks.RETRIEVAL_ACTIVATION_ENABLED is False
    assert capability_locks.PAPER_DECISIONS_ENABLED is False


def test_retrieval_activation_apis_fail_before_any_write(db_path) -> None:
    query_payload = {
        "query_type": "CURRENT_SETUP_QUERY",
        "token_id": 1,
        "pair_id": 1,
        "query_at": NOW.isoformat(),
        "context": {},
    }

    with pytest.raises(CapabilityLockedError) as exc:
        record_memory_retrieval_query(db_path, query_payload, {})
    _assert_locked(exc, "RETRIEVAL_ACTIVATION_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        record_memory_retrieval_matches(db_path, 1, [])
    _assert_locked(exc, "RETRIEVAL_ACTIVATION_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        build_and_record_memory_retrieval_report(db_path, query_payload, NOW)
    _assert_locked(exc, "RETRIEVAL_ACTIVATION_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        enqueue_memory_retrieval_job(
            db_path,
            1,
            1,
            NOW,
            reason="must-remain-locked",
        )
    _assert_locked(exc, "RETRIEVAL_ACTIVATION_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        run_synthetic_memory_retrieval(db_path)
    _assert_locked(exc, "RETRIEVAL_ACTIVATION_LOCKED")

    assert _count(db_path, "printer_memory_retrieval_queries") == 0
    assert _count(db_path, "printer_memory_retrieval_matches") == 0
    assert _count(db_path, "printer_scheduler_jobs") == 0


def test_paper_decision_output_and_writes_fail_before_any_mutation(db_path) -> None:
    action_evidence = {
        "token_id": 1,
        "pair_id": 1,
        "memory_retrieval": {
            "clean_matches": [
                {
                    "outcome_label": "SUSTAINED_PUMP",
                    "action_lesson_label": "ACTION_BUY_WORKED",
                }
            ]
        },
        "current_context": {
            "exit_realism_label": "EXIT_REALISTIC",
            "entry_realism_label": "ENTRY_REALISTIC",
            "realism_gate_label": "REALISM_CONTEXT_ACCEPTABLE",
        },
    }
    for callable_, args in (
        (classify_requested_action_from_memory_evidence, (action_evidence,)),
        (classify_final_paper_action, (action_evidence,)),
        (classify_paper_decision_status, (action_evidence,)),
        (paper_decision_can_be_recorded, (action_evidence,)),
        (
            paper_decision_can_open_position_later,
            (
                {
                    "final_action_label": "BUY",
                    "paper_decision_status_label": "PAPER_DECISION_PROPOSED",
                    "decision_gate_label": "DECISION_ALLOWED",
                },
            ),
        ),
    ):
        with pytest.raises(CapabilityLockedError) as exc:
            callable_(*args)
        _assert_locked(exc, "PAPER_DECISIONS_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        build_decision_payload({})
    _assert_locked(exc, "PAPER_DECISIONS_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        record_paper_decision(db_path, {})
    _assert_locked(exc, "PAPER_DECISIONS_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        record_paper_decision_audit(db_path, 1, {})
    _assert_locked(exc, "PAPER_DECISIONS_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        build_and_record_paper_decision(db_path, 1, 1)
    _assert_locked(exc, "PAPER_DECISIONS_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        enqueue_paper_decision_job(
            db_path,
            1,
            1,
            NOW,
            reason="must-remain-locked",
        )
    _assert_locked(exc, "PAPER_DECISIONS_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        run_synthetic_paper_decision(db_path)
    _assert_locked(exc, "PAPER_DECISIONS_LOCKED")

    assert _count(db_path, "printer_paper_decisions") == 0
    assert _count(db_path, "printer_paper_decision_audits") == 0
    assert _count(db_path, "printer_scheduler_jobs") == 0


def test_central_scheduler_cannot_bypass_consumer_locks(db_path) -> None:
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
            job_name="forbidden-retrieval",
            job_kind=JobKind.MEMORY_WINDOW_CLOSE,
            target_table="printer_memory_retrieval_queries",
            target_id=1,
            scheduled_for=NOW,
        )
    _assert_locked(exc, "RETRIEVAL_ACTIVATION_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        scheduler.enqueue_job(
            db_path,
            job_name="forbidden-paper-decision",
            job_kind=JobKind.MEMORY_WINDOW_CLOSE,
            target_table="printer_paper_decisions",
            target_id=1,
            scheduled_for=NOW,
        )
    _assert_locked(exc, "PAPER_DECISIONS_LOCKED")

    assert _count(db_path, "printer_scheduler_jobs") == 1


def test_clean_four_hour_memory_is_visible_but_cannot_activate_consumers(
    db_path,
) -> None:
    connection = sqlite3.connect(db_path)
    try:
        token_id = int(
            connection.execute(
                "INSERT INTO printer_tokens(token_mint,chain) VALUES ('clean-4h-mint','solana')"
            ).lastrowid
        )
        pair_id = int(
            connection.execute(
                "INSERT INTO printer_pairs(token_id,pair_address,dex,pool_source) "
                "VALUES (?,'clean-4h-pair','pumpswap','fixture')",
                (token_id,),
            ).lastrowid
        )
        window_id = int(
            connection.execute(
                """INSERT INTO printer_memory_windows(
                       token_id,pair_id,window_kind,opened_at,closed_at,
                       memory_status,data_quality_label,memory_quality_label,
                       do_not_train
                   ) VALUES (?,?, 'WINDOW_4H', ?, ?,
                       'CLEAN_MEMORY','CLEAN_DATA','CLEAN_MEMORY',0)""",
                (
                    token_id,
                    pair_id,
                    "2026-09-09T08:00:00+00:00",
                    NOW.isoformat(),
                ),
            ).lastrowid
        )
        episode_id = int(
            connection.execute(
                """INSERT INTO printer_episodes(
                       memory_window_id,token_id,pair_id,episode_kind,
                       episode_status,memory_status,data_quality_label,
                       window_kind,episode_outcome_label,memory_quality_label,
                       action_lesson_label,do_not_train
                   ) VALUES (?,?,?,'WINDOW_4H_CLEAN_MEMORY','EPISODE_BUILT',
                       'CLEAN_MEMORY','CLEAN_DATA','WINDOW_4H','SUSTAINED_PUMP',
                       'CLEAN_MEMORY','ACTION_WAIT_FAILED',0)""",
                (window_id, token_id, pair_id),
            ).lastrowid
        )
        connection.commit()
    finally:
        connection.close()

    record_memory_fingerprint(
        db_path,
        episode_id,
        {
            "episode_id": episode_id,
            "window_id": window_id,
            "window_kind": "WINDOW_4H",
            "outcome_label": "SUSTAINED_PUMP",
            "market_regime_label": "RISK_ON",
            "chain_heat_label": "SOLANA_HOT",
            "safety_status_label": "SAFETY_CLEAN",
            "liquidity_state_label": "LIQUIDITY_USABLE",
            "exit_realism_label": "EXIT_REALISTIC",
            "flow_direction_label": "FLOW_ACCUMULATION",
            "flow_pressure_label": "PRESSURE_STRONG_INFLOW",
            "trend_structure_label": "TREND_UP",
            "volatility_label": "VOLATILITY_ELEVATED",
            "candle_path_label": "PATH_STEADY_CLIMB",
            "micro_event_state_label": "TRADABLE_MICRO_PUMP",
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        },
        "CLEAN_MEMORY",
    )

    query_payload = {
        "query_type": "CURRENT_SETUP_QUERY",
        "token_id": token_id,
        "pair_id": pair_id,
        "context": {
            "window_kind": "WINDOW_4H",
            "outcome_label": "SUSTAINED_PUMP",
            "market_regime_label": "RISK_ON",
            "chain_heat_label": "SOLANA_HOT",
            "safety_status_label": "SAFETY_CLEAN",
            "liquidity_state_label": "LIQUIDITY_USABLE",
            "exit_realism_label": "EXIT_REALISTIC",
            "flow_direction_label": "FLOW_ACCUMULATION",
            "flow_pressure_label": "PRESSURE_STRONG_INFLOW",
            "trend_structure_label": "TREND_UP",
            "volatility_label": "VOLATILITY_ELEVATED",
            "candle_path_label": "PATH_STEADY_CLIMB",
            "micro_event_state_label": "TRADABLE_MICRO_PUMP",
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        },
    }
    matches = retrieve_memory_matches_for_current_setup(db_path, query_payload)
    assert len(matches) == 1
    assert int(matches[0]["episode_id"]) == episode_id
    assert matches[0]["window_kind"] == "WINDOW_4H"
    assert matches[0]["included_as_clean_evidence"] is True

    with pytest.raises(CapabilityLockedError) as exc:
        build_and_record_memory_retrieval_report(db_path, query_payload, NOW)
    _assert_locked(exc, "RETRIEVAL_ACTIVATION_LOCKED")

    with pytest.raises(CapabilityLockedError) as exc:
        build_decision_payload(
            {
                "token_id": token_id,
                "pair_id": pair_id,
                "retrieval_result_label": "RETRIEVAL_HAS_CLEAN_MATCHES",
                "memory_evidence_label": "MEMORY_EVIDENCE_STRONG",
            }
        )
    _assert_locked(exc, "PAPER_DECISIONS_LOCKED")

    assert _count(db_path, "printer_memory_retrieval_queries") == 0
    assert _count(db_path, "printer_memory_retrieval_matches") == 0
    assert _count(db_path, "printer_paper_decisions") == 0
    assert _count(db_path, "printer_paper_decision_audits") == 0
    assert _count(db_path, "printer_scheduler_jobs") == 0


def test_read_only_memory_and_decision_inspection_remain_available(db_path) -> None:
    matches = retrieve_memory_matches_for_current_setup(
        db_path,
        {
            "query_type": "CURRENT_SETUP_QUERY",
            "token_id": 1,
            "context": {"window_kind": "WINDOW_4H"},
        },
    )
    assert matches == []
    assert get_latest_paper_decision(db_path) is None

    assert _count(db_path, "printer_memory_retrieval_queries") == 0
    assert _count(db_path, "printer_memory_retrieval_matches") == 0
    assert _count(db_path, "printer_paper_decisions") == 0
    assert _count(db_path, "printer_paper_decision_audits") == 0

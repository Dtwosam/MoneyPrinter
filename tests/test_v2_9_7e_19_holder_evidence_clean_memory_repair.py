from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    HOLDER_ELIGIBILITY_CANDIDATE_MAX,
    _holder_execution_fact,
    _holder_eligibility_from_bundle,
)
from printer_v1.operator_cli.e2m_snapshot_persistence import (
    _normalize_verified_inactivity,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    _cancel_campaign_discovery_jobs,
    _four_hour_terminal_validation,
)


def _execution(
    *,
    mint: str = "mint-a",
    label: str = "HOLDER_CONCENTRATION_LOW",
    status: str = "COMPLETE",
    quality: str = "CLEAN_DATA",
    response: bool = True,
):
    return SimpleNamespace(
        response_record=SimpleNamespace(id=1) if response else None,
        normalized_result=SimpleNamespace(
            source_status=SimpleNamespace(value=status),
            data_quality_label=SimpleNamespace(value=quality),
            normalized_payload={
                "token_mint": mint,
                "holder_concentration_label": label,
                "top_10_holder_percent": 12.0,
            },
        ),
    )


def test_holder_evidence_valid_missing_mismatch_stale_failed_and_unknown() -> None:
    assert _holder_execution_fact(
        _execution(), token_mint="mint-a", source_name="solana_rpc"
    )["eligible"]
    cases = (
        (None, "HOLDER_EVIDENCE_UNAVAILABLE"),
        (_execution(mint="other"), "HOLDER_EVIDENCE_TARGET_MISMATCH"),
        (_execution(status="STALE"), "HOLDER_EVIDENCE_STALE"),
        (_execution(status="FAILED", response=False), "HOLDER_EVIDENCE_FAILED"),
        (_execution(label="HOLDER_CONCENTRATION_UNKNOWN"), "HOLDER_CONCENTRATION_UNKNOWN"),
    )
    for execution, reason in cases:
        fact = _holder_execution_fact(
            execution, token_mint="mint-a", source_name="solana_rpc"
        )
        assert fact == {
            "eligible": False, "reason": reason, "source_name": "solana_rpc"
        }


def test_holder_path_prefers_valid_goplus_then_existing_rpc_fallback() -> None:
    goplus = _execution(label="HOLDER_CONCENTRATION_LOW")
    assert _holder_eligibility_from_bundle(
        {"executions": {"safety": goplus}}, token_mint="mint-a"
    )["source_name"] == "goplus"
    unknown = _execution(label="HOLDER_CONCENTRATION_UNKNOWN")
    rpc = _execution(label="HOLDER_CONCENTRATION_MEDIUM")
    fact = _holder_eligibility_from_bundle(
        {"executions": {"safety": unknown, "holder": rpc}},
        token_mint="mint-a",
    )
    assert fact["eligible"] and fact["source_name"] == "solana_rpc"
    assert HOLDER_ELIGIBILITY_CANDIDATE_MAX == 8


def _inactive_pair(**changes):
    pair = {
        "price_usd": 0.001,
        "liquidity_usd": 5000.0,
        "volume_1h": 0.0,
        "txns_1h": 0,
        "volume_5m": None,
        "volume_15m": None,
        "txns_5m": None,
        "txns_15m": None,
        "price_change_5m": None,
        "price_change_15m": None,
    }
    pair.update(changes)
    return pair


def test_verified_inactivity_converts_only_missing_short_activity() -> None:
    result = _normalize_verified_inactivity(
        _inactive_pair(volume_5m=7.0, txns_5m=2)
    )
    assert result["volume_5m"] == 7.0
    assert result["txns_5m"] == 2
    assert result["volume_15m"] == 0
    assert result["price_change_15m"] == 0
    provenance = result["snapshot_inactivity_evidence"]
    assert provenance["label"] == "SNAPSHOT_VERIFIED_INACTIVE"
    assert "volume_5m" not in provenance["converted_fields"]


def test_inactivity_missing_price_liquidity_or_wider_activity_stays_missing() -> None:
    for changes in (
        {"price_usd": None},
        {"liquidity_usd": None},
        {"volume_1h": None},
        {"txns_1h": None},
    ):
        result = _normalize_verified_inactivity(_inactive_pair(**changes))
        assert result["volume_15m"] is None
        assert "snapshot_inactivity_evidence" not in result


def test_active_market_values_are_invariant() -> None:
    active = _inactive_pair(
        volume_5m=4.0, volume_15m=6.0, txns_5m=2, txns_15m=4,
        price_change_5m=1.5, price_change_15m=2.5,
    )
    assert _normalize_verified_inactivity(active) == active
    wider_active = _inactive_pair(txns_1h=1)
    assert _normalize_verified_inactivity(wider_active) == wider_active


def _natural_terminal(*, dirty: bool = False, operational: bool = True):
    steps = []
    windows = {}
    for token_id in (1, 2):
        window_id = token_id
        steps.append({
            "step_kind": "WINDOW_CLOSE",
            "step_status": "SUCCEEDED",
            "token_id": token_id,
            "memory_window_id": window_id,
            "result_json": json.dumps({
                "continuation_plan": {
                    "verdict": "STOP_AFTER_15M", "planned_jobs": 0
                }
            }),
        })
        windows[window_id] = {
            "window_kind": "WINDOW_15M",
            "window_status": "COMPLETE",
            "memory_status": "DIRTY_MEMORY" if dirty else "CLEAN_MEMORY",
            "memory_quality_label": "DIRTY_MEMORY" if dirty else "CLEAN_MEMORY",
            "data_quality_label": "DIRTY_DATA" if dirty else "CLEAN_DATA",
            "do_not_train": 1 if dirty else 0,
        }
    return _four_hour_terminal_validation(
        config={
            "continuous_four_hour": True,
            "operational_natural_disposition": operational,
        },
        steps=steps,
        windows_by_id=windows,
        budgets={
            "four_hour_phase_usage": {"state": "NOT_STARTED"},
            "cumulative_lifecycle_usage": {"budget_verdict": "WITHIN_CEILING"},
        },
        pending_steps=0,
        running_jobs=0,
    )


def test_two_clean_natural_stops_complete_but_dirty_or_proof_mode_does_not() -> None:
    clean = _natural_terminal()
    assert clean["complete"]
    assert clean["run_status"] == "COMPLETED"
    assert not _natural_terminal(dirty=True)["complete"]
    proof = _natural_terminal(operational=False)
    assert not proof["complete"]
    assert "four_hour_phase_not_started" in proof["reasons"]


def test_started_continuation_still_requires_complete_four_hour_audit() -> None:
    result = _four_hour_terminal_validation(
        config={
            "continuous_four_hour": True,
            "operational_natural_disposition": True,
        },
        steps=[{
            "step_kind": "LONG_CONTINUATION_CLOSE",
            "step_status": "FAILED",
            "tracking_lane": "TRACK_NORMAL",
            "error_or_skip_reason": "source failed",
        }],
        windows_by_id={},
        budgets={
            "four_hour_phase_usage": {"state": "STARTED"},
            "cumulative_lifecycle_usage": {"budget_verdict": "WITHIN_CEILING"},
        },
        pending_steps=0,
        running_jobs=0,
    )
    assert not result["complete"]
    assert "terminal_4h_step_failure" in result["reasons"]


def test_exact_discovery_cleanup_is_idempotent_and_preserves_unrelated_jobs() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE printer_scheduler_jobs (
            id INTEGER PRIMARY KEY, job_kind TEXT, status TEXT, finished_at TEXT,
            locked_at TEXT, lock_owner TEXT, updated_at TEXT
        );
        CREATE TABLE printer_discovery_work (
            discovery_batch_id TEXT, scheduler_job_id INTEGER
        );
        """
    )
    rows = (
        (1, "DISCOVERY_REFRESH", "PENDING"),
        (2, "DISCOVERY_REFRESH", "RUNNING"),
        (3, "DISCOVERY_REFRESH", "PENDING"),
        (4, "TOKEN_SNAPSHOT", "PENDING"),
    )
    conn.executemany(
        "INSERT INTO printer_scheduler_jobs VALUES (?, ?, ?, NULL, NULL, NULL, NULL)",
        rows,
    )
    conn.executemany(
        "INSERT INTO printer_discovery_work VALUES (?, ?)",
        (("batch-a", 1), ("batch-a", 2), ("batch-b", 3), ("batch-a", 4)),
    )
    first = _cancel_campaign_discovery_jobs(conn, "batch-a")
    second = _cancel_campaign_discovery_jobs(conn, "batch-a")
    assert first["cancelled_jobs"] == 2
    assert second["cancelled_jobs"] == 0
    statuses = dict(conn.execute("SELECT id, status FROM printer_scheduler_jobs"))
    assert statuses == {1: "CANCELLED", 2: "CANCELLED", 3: "PENDING", 4: "PENDING"}

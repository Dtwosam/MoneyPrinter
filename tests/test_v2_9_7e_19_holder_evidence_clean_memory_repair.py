from __future__ import annotations

import json
import pathlib
import sqlite3
import tempfile
from types import SimpleNamespace

from printer_v1.db.migrate import apply_migrations
from printer_v1.scheduler.contracts import JobKind
from printer_v1.scheduler.scheduler import enqueue_job
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
        (_execution(status="FAILED", response=False), "HOLDER_EVIDENCE_FAILED:missing_response"),
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


def test_natural_stops_complete_regardless_of_memory_quality() -> None:
    """V2-9.7E.47 A4 supersedes the original assertion.

    This test previously asserted that a DIRTY two-token natural stop was NOT a
    complete lifecycle. That conflated lifecycle completion with clean-memory
    success and produced the false ``SAFE_STOP_4H_TERMINAL_INCOMPLETE`` recorded
    at V2-9.7E.46 §10. A lawful no-continuation close is now a COMPLETED
    governed lifecycle; only the pilot ACCEPTANCE verdict is blocked by dirty or
    audit-only memory. Proof mode still requires the 4h phase.
    """
    clean = _natural_terminal()
    assert clean["complete"]
    assert clean["run_status"] == "COMPLETED"
    assert clean["memory_acceptance"]["verdict"] == "CLEAN_MEMORY_ACHIEVED"

    dirty = _natural_terminal(dirty=True)
    assert dirty["complete"]
    assert dirty["run_status"] == "COMPLETED"
    assert dirty["memory_acceptance"]["verdict"] == "MEMORY_EVIDENCE_BLOCKED"
    assert dirty["memory_acceptance"]["dirty_or_audit_only_windows"] == 2

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
    """V2-9.7E.47 A2 supersedes the original blanket-cancel assertion.

    Cancelling every active ``DISCOVERY_REFRESH`` job was the wrong terminal for
    work that had already SUCCEEDED. Parity now follows the work row's own
    terminal state through the committed Scheduler owner. Unrelated jobs are
    still untouched and repeat calls are still idempotent.
    """
    with tempfile.TemporaryDirectory() as tmp:
        db = pathlib.Path(tmp) / "cleanup.sqlite3"
        apply_migrations(str(db))
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        now = "2026-07-25T12:00:00+00:00"
        conn.execute(
            """INSERT INTO printer_memory_factory_campaigns(
                   campaign_id, campaign_state, db_mode, db_target_identity,
                   proof_source_db_identity, policy_version,
                   created_at, updated_at)
               VALUES ('camp','RUNNING','PROOF_ISOLATED','iso','src','v1',?,?)""",
            (now, now),
        )
        conn.execute(
            """INSERT INTO printer_memory_factory_campaign_configurations(
                   configuration_id, campaign_id, configuration_hash,
                   configuration_json, launch_provenance_json, created_at)
               VALUES ('cfg','camp',?, '{}', '{}', ?)""",
            ("c" * 64, now),
        )
        conn.execute(
            """INSERT INTO printer_memory_factory_campaign_runs(
                   run_id, campaign_id, run_ordinal, run_state,
                   created_at, updated_at)
               VALUES ('run','camp',1,'RUNNING',?,?)""",
            (now, now),
        )
        # Two cycles in one campaign; the schema pins one discovery batch per
        # cycle, so batch-b is the "other batch that must stay untouched".
        for batch, cycle, ordinal in (
            ("batch-a", "cyc-a", 1), ("batch-b", "cyc-b", 2),
        ):
            conn.execute(
                """INSERT INTO printer_memory_factory_campaign_cycles(
                       cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                       created_at, updated_at)
                   VALUES (?, 'camp', 'run', ?, 'PLANNED', ?, ?)""",
                (cycle, ordinal, now, now),
            )
            conn.execute(
                """INSERT INTO printer_discovery_batches(
                       discovery_batch_id, campaign_id, configuration_id, run_id,
                       cycle_id, cycle_cutoff, policy_version,
                       provider_contract_versions_json, git_provenance_identity,
                       campaign_selection_seed_identity, cycle_seed_hash,
                       pump_continuity_state, batch_state, canonical_hash,
                       created_at)
                   VALUES (?, 'camp', 'cfg', 'run', ?, ?, 'v1', '{}', ?, 'seed',
                           ?, 'NONE', 'DISCOVERING', ?, ?)""",
                (batch, cycle, now, "0" * 40, "a" * 64, "b" * 64, now),
            )
        seeded: dict[str, int] = {}
        plan = (
            ("batch-a", "camp", "cyc-a", "DISCOVERY_PUMPFUN_LATEST", "SUCCEEDED"),
            ("batch-a", "camp", "cyc-a", "DISCOVERY_IDENTITY_MERGE", "FAILED"),
            ("batch-a", "camp", "cyc-a", "DISCOVERY_UNIFORM_SELECTION", "RUNNING"),
            ("batch-b", "camp", "cyc-b", "DISCOVERY_PUMPFUN_LATEST", "SUCCEEDED"),
        )
        for index, (batch, campaign, cycle, work_type, state) in enumerate(plan, start=1):
            _result, job_id = enqueue_job(
                conn,
                job_name=f"{work_type}:{batch}",
                job_kind=JobKind.DISCOVERY_REFRESH,
                target_table="printer_discovery_batches",
            )
            seeded[f"{batch}-{index}"] = int(job_id)
            terminal = state not in {"PENDING", "RUNNING", "COOLDOWN"}
            conn.execute(
                """INSERT INTO printer_discovery_work(
                       discovery_work_id, discovery_batch_id, campaign_id, run_id,
                       cycle_id, scheduler_job_id, work_type, work_state,
                       deadline_at, first_terminal_cause, terminal_at,
                       created_at, updated_at)
                   VALUES (?,?,?, 'run', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"work-{index}", batch, campaign, cycle, int(job_id),
                    work_type, state, now,
                    "DIRECT_COMPLETE" if terminal else None,
                    now if terminal else None, now, now,
                ),
            )
        # An unrelated non-discovery job must survive untouched.
        _result, unrelated = enqueue_job(
            conn, job_name="unrelated-snapshot",
            job_kind=JobKind.TRACK_NORMAL_FIRST_15M,
            target_table="printer_tracking_queue",
        )
        conn.commit()

        first = _cancel_campaign_discovery_jobs(conn, "batch-a")
        second = _cancel_campaign_discovery_jobs(conn, "batch-a")
        conn.commit()
        statuses = {
            int(row["id"]): str(row["status"])
            for row in conn.execute(
                "SELECT id, status FROM printer_scheduler_jobs"
            ).fetchall()
        }
        conn.close()

    assert first["completed_jobs"] == 1
    assert first["failed_jobs"] == 1
    assert first["cancelled_jobs"] == 1
    assert first["terminal_work_with_active_job"] == 0
    assert second["job_actions"] == {}
    assert statuses[seeded["batch-a-1"]] == "SUCCEEDED"
    assert statuses[seeded["batch-a-2"]] == "FAILED"
    assert statuses[seeded["batch-a-3"]] == "CANCELLED"
    # Another batch and an unrelated job kind are untouched.
    assert statuses[seeded["batch-b-4"]] == "PENDING"
    assert statuses[int(unrelated)] == "PENDING"

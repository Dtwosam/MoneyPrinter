from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

from printer_v1.db.migrate import apply_migrations
from printer_v1.operator_cli.proof_db_schema_readiness import CANONICAL_PERSISTENT_DB


ROOT = Path(__file__).resolve().parents[1]
INSPECTOR_PATH = ROOT / "scripts" / "v2_9_8b_checkpoint8_independent_inspection.py"

CAMPAIGN_ID = "c8-real-campaign"
CAMPAIGN_RUN_ID = "c8-real-campaign-run"
FACTORY_RUN_ID = "11111111-2222-3333-4444-555555555555"
ALT_FACTORY_RUN_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
CONFIGURATION_ID = "c8-real-configuration"
CYCLE_ID = "c8-real-cycle"
EXECUTION_ID = "c8-real-execution"
SUPERVISION_ID = "c8-real-supervision"
PROOF_ID = "C8_DTW57_REAL_SCHEMA_RED"
MANIFEST = "a" * 64
NOW = "2026-08-08T00:00:00+00:00"


def _load_inspector(name: str):
    spec = importlib.util.spec_from_file_location(name, INSPECTOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _canonical_bytes(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _summary_hash(payload: dict) -> str:
    unsigned = dict(payload)
    unsigned.pop("frozen_evidence_sha256", None)
    return hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()


def _write_summary(proof_dir: Path, payload: dict) -> None:
    payload["frozen_evidence_sha256"] = _summary_hash(payload)
    (proof_dir / "checkpoint8-controlling-proof-summary.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _insert_base_graph(connection: sqlite3.Connection, artifact_root: Path) -> dict:
    connection.execute("PRAGMA foreign_keys = ON")

    connection.execute(
        """
        INSERT INTO printer_memory_factory_campaigns (
            campaign_id, campaign_state, db_mode, db_target_identity,
            proof_source_db_identity, policy_version,
            first_terminal_cause, terminal_at, created_at, updated_at
        ) VALUES (?, 'TERMINAL_COMPLETED', 'PROOF_ISOLATED', ?, ?, 'V2-9.8B',
                  'COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED', ?, ?, ?)
        """,
        (CAMPAIGN_ID, "sha256:target", "sha256:source", NOW, NOW, NOW),
    )
    connection.execute(
        """
        INSERT INTO printer_memory_factory_campaign_configurations (
            configuration_id, campaign_id, configuration_hash,
            configuration_json, launch_provenance_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            CONFIGURATION_ID,
            CAMPAIGN_ID,
            "b" * 64,
            json.dumps({"window_kind": "WINDOW_15M"}, sort_keys=True),
            json.dumps({"git_head": "c" * 40}, sort_keys=True),
            NOW,
        ),
    )
    connection.execute(
        """
        INSERT INTO printer_memory_factory_runs (
            run_id, run_status, stop_reason, window_kind, db_mode,
            config_hash, config_json, selected_token_count,
            started_at, finished_at, final_report_json
        ) VALUES (?, 'COMPLETED', NULL, 'WINDOW_15M', 'PROOF_ONLY',
                  ?, ?, 2, ?, ?, ?)
        """,
        (
            FACTORY_RUN_ID,
            "d" * 64,
            json.dumps({"window_kind": "WINDOW_15M"}, sort_keys=True),
            NOW,
            NOW,
            json.dumps({"status": "COMPLETED"}, sort_keys=True),
        ),
    )
    connection.execute(
        """
        INSERT INTO printer_memory_factory_runs (
            run_id, run_status, stop_reason, window_kind, db_mode,
            config_hash, config_json, selected_token_count,
            started_at, finished_at, final_report_json
        ) VALUES (?, 'COMPLETED', NULL, 'WINDOW_15M', 'PROOF_ONLY',
                  ?, ?, 0, ?, ?, ?)
        """,
        (
            ALT_FACTORY_RUN_ID,
            "e" * 64,
            json.dumps({"window_kind": "WINDOW_15M"}, sort_keys=True),
            NOW,
            NOW,
            json.dumps({"status": "UNRELATED"}, sort_keys=True),
        ),
    )
    connection.execute(
        """
        INSERT INTO printer_memory_factory_campaign_runs (
            run_id, campaign_id, run_ordinal, run_state, authoritative_run_id,
            first_terminal_cause, terminal_at, created_at, updated_at
        ) VALUES (?, ?, 1, 'TERMINAL_COMPLETED', ?,
                  'COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED', ?, ?, ?)
        """,
        (CAMPAIGN_RUN_ID, CAMPAIGN_ID, FACTORY_RUN_ID, NOW, NOW, NOW),
    )
    connection.execute(
        """
        INSERT INTO printer_memory_factory_campaign_cycles (
            cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
            first_terminal_cause, terminal_at, created_at, updated_at
        ) VALUES (?, ?, ?, 1, 'TERMINAL_COMPLETED', 'COMPLETED', ?, ?, ?)
        """,
        (CYCLE_ID, CAMPAIGN_ID, CAMPAIGN_RUN_ID, NOW, NOW, NOW),
    )
    connection.execute(
        """
        INSERT INTO printer_memory_factory_campaign_supervision (
            supervision_id, campaign_id, configuration_id, run_id, owner_id,
            supervision_state, terminal_status, first_terminal_cause,
            heartbeat_at, lease_expires_at, lease_lock_path,
            cleanup_completed_at, lease_released_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'c8-owner', 'TERMINAL', 'COMPLETED', 'COMPLETED',
                  ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            SUPERVISION_ID,
            CAMPAIGN_ID,
            CONFIGURATION_ID,
            CAMPAIGN_RUN_ID,
            NOW,
            NOW,
            str(artifact_root / "campaign.lease.lock"),
            NOW,
            NOW,
            NOW,
            NOW,
        ),
    )

    for token_id, pair_id, mint, pair in (
        (1, 11, "MintAlpha11111111111111111111111111111111", "PairAlpha11111111111111111111111111111111"),
        (2, 22, "MintBravo11111111111111111111111111111111", "PairBravo11111111111111111111111111111111"),
    ):
        connection.execute(
            """
            INSERT INTO printer_tokens (
                id, token_mint, chain, symbol, name, token_status, created_at, updated_at
            ) VALUES (?, ?, 'solana', ?, ?, 'ACTIVE', ?, ?)
            """,
            (token_id, mint, f"T{token_id}", f"Token {token_id}", NOW, NOW),
        )
        connection.execute(
            """
            INSERT INTO printer_pairs (
                id, token_id, pair_address, dex, pool_source,
                base_token_mint, quote_token_mint, created_at, updated_at
            ) VALUES (?, ?, ?, 'pumpswap', 'PUMPSWAP', ?, 'So11111111111111111111111111111111111111112', ?, ?)
            """,
            (pair_id, token_id, pair, mint, NOW, NOW),
        )

    for slot, token_id, pair_id, mint, pair in (
        (1, 1, 11, "MintAlpha11111111111111111111111111111111", "PairAlpha11111111111111111111111111111111"),
        (2, 2, 22, "MintBravo11111111111111111111111111111111", "PairBravo11111111111111111111111111111111"),
    ):
        slot_id = f"slot-{slot}"
        window_id = f"campaign-window-{slot}"
        memory_window_id = 100 + slot
        episode_id = 200 + slot
        connection.execute(
            """
            INSERT INTO printer_memory_factory_campaign_token_slots (
                token_slot_id, campaign_id, run_id, cycle_id, slot_ordinal,
                token_identity, token_row_id, mint_identity, pair_identity,
                pair_row_id, lifecycle_identity, token_state, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'WINDOW_15M_CLOSED', ?, ?)
            """,
            (
                slot_id,
                CAMPAIGN_ID,
                CAMPAIGN_RUN_ID,
                CYCLE_ID,
                slot,
                mint,
                token_id,
                mint,
                pair,
                pair_id,
                f"lifecycle-{slot}",
                NOW,
                NOW,
            ),
        )
        connection.execute(
            """
            INSERT INTO printer_memory_windows (
                id, token_id, pair_id, window_kind, opened_at, closed_at,
                expected_snapshot_count, actual_snapshot_count, missing_snapshot_count,
                coverage_state, memory_status, data_quality_label, do_not_train,
                window_status, memory_quality_label, created_at, updated_at
            ) VALUES (?, ?, ?, 'WINDOW_15M', ?, ?, 8, 8, 0,
                      'COMPLETE', 'PARTIAL_MEMORY', 'CLEAN_DATA', 0,
                      'WINDOW_CLOSED', 'PARTIAL_MEMORY', ?, ?)
            """,
            (memory_window_id, token_id, pair_id, NOW, NOW, NOW, NOW),
        )
        connection.execute(
            """
            INSERT INTO printer_episodes (
                id, memory_window_id, token_id, pair_id, episode_kind,
                episode_status, memory_status, data_quality_label, do_not_train,
                window_kind, memory_quality_label, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'WINDOW_15M_CLEAN_MEMORY',
                      'COMPLETE', 'CLEAN_MEMORY', 'CLEAN_DATA', 0,
                      'WINDOW_15M', 'CLEAN_MEMORY', ?, ?)
            """,
            (episode_id, memory_window_id, token_id, pair_id, NOW, NOW),
        )
        fingerprint_payload = {
            "episode_id": episode_id,
            "window_id": memory_window_id,
            "token_id": token_id,
            "pair_id": pair_id,
            "window_kind": "WINDOW_15M",
        }
        connection.execute(
            """
            INSERT INTO printer_memory_fingerprints (
                id, episode_id, fingerprint_kind, fingerprint_payload_json,
                memory_status, data_quality_label, do_not_train, created_at
            ) VALUES (?, ?, 'STATIC_CONDITION_SUMMARY', ?,
                      'CLEAN_MEMORY', 'CLEAN_DATA', 0, ?)
            """,
            (300 + slot, episode_id, json.dumps(fingerprint_payload, sort_keys=True), NOW),
        )
        connection.execute(
            """
            INSERT INTO printer_memory_factory_campaign_windows (
                window_id, campaign_id, run_id, cycle_id, token_slot_id,
                token_row_id, pair_row_id, window_kind, window_state,
                root_15m_lifecycle_identity, memory_window_row_id,
                checkpoint_cutoff, support_only, first_terminal_cause,
                terminal_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'WINDOW_15M', 'CLEAN_PROMOTED',
                      ?, ?, ?, 0, 'CLEAN_PROMOTED', ?, ?, ?)
            """,
            (
                window_id,
                CAMPAIGN_ID,
                CAMPAIGN_RUN_ID,
                CYCLE_ID,
                slot_id,
                token_id,
                pair_id,
                f"lifecycle-{slot}",
                memory_window_id,
                NOW,
                NOW,
                NOW,
                NOW,
            ),
        )

    for job_id in range(1, 29):
        connection.execute(
            """
            INSERT INTO printer_scheduler_jobs (
                id, job_name, job_kind, target_table, target_id, priority,
                status, scheduled_for, started_at, finished_at, locked_at,
                lock_owner, retry_count, created_at, updated_at
            ) VALUES (?, ?, 'CHECKPOINT8_FIXTURE', NULL, NULL, 0,
                      'COMPLETED', ?, ?, ?, NULL, NULL, 0, ?, ?)
            """,
            (job_id, f"c8-job-{job_id}", NOW, NOW, NOW, NOW, NOW),
        )

    for request_id in range(1, 5):
        source_name = "solana_rpc" if request_id <= 2 else "dexscreener"
        connection.execute(
            """
            INSERT INTO printer_source_requests (
                id, source_name, request_kind, requested_at, request_key,
                tracking_priority, source_status, data_quality_label, created_at
            ) VALUES (?, ?, ?, ?, ?, 0, 'COMPLETE', 'CLEAN_DATA', ?)
            """,
            (
                request_id,
                source_name,
                f"REQUEST_KIND_{request_id}",
                NOW,
                f"request-{request_id}",
                NOW,
            ),
        )
        connection.execute(
            """
            INSERT INTO printer_source_responses (
                id, source_request_id, source_name, received_at, status_code,
                source_status, data_quality_label, response_hash,
                normalized_payload_json, created_at
            ) VALUES (?, ?, ?, ?, 200, 'COMPLETE', 'CLEAN_DATA', ?, ?, ?)
            """,
            (
                request_id,
                request_id,
                source_name,
                NOW,
                hashlib.sha256(f"response-{request_id}".encode()).hexdigest(),
                json.dumps({"ok": True, "request_id": request_id}, sort_keys=True),
                NOW,
            ),
        )

    lifecycle_job = 1
    for slot in (1, 2):
        for ordinal in range(1, 10):
            job_id = lifecycle_job
            lifecycle_job += 1
            source_request_id = 1 if job_id == 1 else (2 if job_id == 10 else None)
            source_response_id = source_request_id
            connection.execute(
                """
                INSERT INTO printer_memory_factory_campaign_scheduler_work (
                    scheduler_work_id, campaign_id, run_id, cycle_id,
                    token_slot_id, window_id, work_intent, deadline_at,
                    work_state, scheduler_job_id, source_request_id,
                    source_response_id, ownership_contract_version, stage_id,
                    work_scope, target_category, target_identity, factory_run_id,
                    first_terminal_cause, terminal_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'SUCCEEDED', ?, ?, ?,
                          'V2_STAGE_SCOPED', ?, 'WINDOW_LIFECYCLE',
                          'TOKEN_PAIR', ?, ?, 'COMPLETED', ?, ?, ?)
                """,
                (
                    f"lifecycle-work-{job_id}",
                    CAMPAIGN_ID,
                    CAMPAIGN_RUN_ID,
                    CYCLE_ID,
                    f"slot-{slot}",
                    f"campaign-window-{slot}",
                    f"WINDOW_{ordinal}",
                    NOW,
                    job_id,
                    source_request_id,
                    source_response_id,
                    f"stage-window-{slot}",
                    f"slot-{slot}",
                    FACTORY_RUN_ID,
                    NOW,
                    NOW,
                    NOW,
                ),
            )
            step_kind = "WINDOW_CLOSE" if ordinal == 9 else "SNAPSHOT"
            connection.execute(
                """
                INSERT INTO printer_memory_factory_run_steps (
                    run_id, step_key, step_kind, step_status, token_id, pair_id,
                    token_mint, pair_address, scheduler_job_id, source_request_id,
                    source_response_id, memory_window_id, result_json,
                    started_at, finished_at, created_at, updated_at
                ) VALUES (?, ?, ?, 'SUCCEEDED', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    FACTORY_RUN_ID,
                    f"slot-{slot}-step-{ordinal}",
                    step_kind,
                    slot,
                    11 if slot == 1 else 22,
                    "MintAlpha11111111111111111111111111111111"
                    if slot == 1
                    else "MintBravo11111111111111111111111111111111",
                    "PairAlpha11111111111111111111111111111111"
                    if slot == 1
                    else "PairBravo11111111111111111111111111111111",
                    job_id,
                    source_request_id,
                    source_response_id,
                    (100 + slot) if step_kind == "WINDOW_CLOSE" else None,
                    json.dumps({"ordinal": ordinal}, sort_keys=True),
                    NOW,
                    NOW,
                    NOW,
                    NOW,
                ),
            )

    discovery_types = (
        "DISCOVERY_PUMPFUN_LATEST",
        "DISCOVERY_DEXSCREENER_ACTIVE",
        "DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE",
        "DISCOVERY_IDENTITY_MERGE",
        "DISCOVERY_ORIGIN_VERIFICATION",
        "DISCOVERY_PUMPSWAP_CONFIRMATION",
        "DISCOVERY_FIXED_ELIGIBILITY_GATES",
        "DISCOVERY_UNIFORM_SELECTION",
    )
    connection.execute(
        """
        INSERT INTO printer_discovery_batches (
            discovery_batch_id, campaign_id, configuration_id, run_id, cycle_id,
            cycle_cutoff, policy_version, provider_contract_versions_json,
            git_provenance_identity, campaign_selection_seed_identity,
            cycle_seed_hash, pump_continuity_state, batch_state, canonical_hash,
            first_terminal_cause, created_at, terminal_at
        ) VALUES ('batch-c8', ?, ?, ?, ?, ?, 'V2-9.8B', '{}',
                  'git-c8', 'seed-c8', ?, 'CONTIGUOUS',
                  'TERMINAL_COMPLETED', ?, 'COMPLETED', ?, ?)
        """,
        (CAMPAIGN_ID, CONFIGURATION_ID, CAMPAIGN_RUN_ID, CYCLE_ID, NOW, "f" * 64, "1" * 64, NOW, NOW),
    )
    for offset, work_type in enumerate(discovery_types, start=19):
        connection.execute(
            """
            INSERT INTO printer_memory_factory_campaign_scheduler_work (
                scheduler_work_id, campaign_id, run_id, cycle_id,
                work_intent, deadline_at, work_state, scheduler_job_id,
                ownership_contract_version, stage_id, work_scope,
                target_category, target_identity, first_terminal_cause,
                terminal_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'SUCCEEDED', ?,
                      'V2_STAGE_SCOPED', 'stage-discovery', 'DISCOVERY_SELECTION',
                      'DISCOVERY', ?, 'COMPLETED', ?, ?, ?)
            """,
            (
                f"discovery-scheduler-work-{offset}",
                CAMPAIGN_ID,
                CAMPAIGN_RUN_ID,
                CYCLE_ID,
                work_type,
                NOW,
                offset,
                work_type,
                NOW,
                NOW,
                NOW,
            ),
        )
        connection.execute(
            """
            INSERT INTO printer_discovery_work (
                discovery_work_id, discovery_batch_id, campaign_id, run_id,
                cycle_id, scheduler_job_id, work_type, work_state, deadline_at,
                first_terminal_cause, terminal_at, created_at, updated_at
            ) VALUES (?, 'batch-c8', ?, ?, ?, ?, ?, 'SUCCEEDED', ?,
                      'COMPLETED', ?, ?, ?)
            """,
            (
                f"discovery-work-{offset}",
                CAMPAIGN_ID,
                CAMPAIGN_RUN_ID,
                CYCLE_ID,
                offset,
                work_type,
                NOW,
                NOW,
                NOW,
                NOW,
            ),
        )

    for job_id, slot in ((27, 1), (28, 2)):
        connection.execute(
            """
            INSERT INTO printer_memory_factory_campaign_scheduler_work (
                scheduler_work_id, campaign_id, run_id, cycle_id, token_slot_id,
                work_intent, deadline_at, work_state, scheduler_job_id,
                ownership_contract_version, stage_id, work_scope,
                target_category, target_identity, first_terminal_cause,
                terminal_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'HANDOFF', ?, 'SUCCEEDED', ?,
                      'V2_STAGE_SCOPED', 'stage-handoff', 'FIRST_15M_HANDOFF',
                      'TOKEN_SLOT', ?, 'COMPLETED', ?, ?, ?)
            """,
            (
                f"handoff-work-{slot}",
                CAMPAIGN_ID,
                CAMPAIGN_RUN_ID,
                CYCLE_ID,
                f"slot-{slot}",
                NOW,
                job_id,
                f"slot-{slot}",
                NOW,
                NOW,
                NOW,
            ),
        )

    for ordinal, (work_id, request_id) in enumerate(
        (("discovery-work-19", 3), ("discovery-work-20", 4)),
        start=1,
    ):
        connection.execute(
            """
            INSERT INTO printer_discovery_work_source_links (
                discovery_work_id, link_ordinal, source_request_id,
                source_response_id, source_failure_id, created_at
            ) VALUES (?, ?, ?, ?, NULL, ?)
            """,
            (work_id, ordinal, request_id, request_id, NOW),
        )

    owner_transport = [
        {
            "governed_request_kind": "SOLANA_RPC",
            "source_name": "solana_rpc",
            "stage_id": "stage-window-1",
            "target_category": "TOKEN_PAIR",
            "target_identity": "slot-1",
            "ordinal": 1,
            "result": "SUCCESS",
        },
        {
            "governed_request_kind": "DEXSCREENER",
            "source_name": "dexscreener",
            "stage_id": "stage-discovery",
            "target_category": "DISCOVERY",
            "target_identity": "DISCOVERY_DEXSCREENER_ACTIVE",
            "ordinal": 1,
            "result": "SUCCESS",
        },
    ]
    full_run_accounting = {
        "owner_evidence": {"transport_operations": owner_transport},
        "action_local_evidence": {"transport_operations": list(owner_transport)},
        "scheduler_work_identities": [
            {"scheduler_job_id": job_id, "stage_id": "fixture-stage"}
            for job_id in range(1, 29)
        ],
        "local_validation_identities": [
            {"subject_identity": "slot-1", "validation_kind": "FIXTURE_VALIDATION", "validation_ordinal": 1},
            {"subject_identity": "slot-2", "validation_kind": "FIXTURE_VALIDATION", "validation_ordinal": 2},
        ],
        "lifecycle_reservation_identities": [
            {
                "factory_run_id": FACTORY_RUN_ID,
                "token_id": slot,
                "pair_id": 11 if slot == 1 else 22,
                "window_kind": "WINDOW_15M",
                "reservation_ordinal": slot,
                "stage_id": f"stage-window-{slot}",
            }
            for slot in (1, 2)
        ],
    }
    identity = {
        "campaign_id": CAMPAIGN_ID,
        "campaign_run_id": CAMPAIGN_RUN_ID,
        "configuration_id": CONFIGURATION_ID,
        "cycle_id": CYCLE_ID,
        "execution_id": EXECUTION_ID,
        "factory_run_id": FACTORY_RUN_ID,
        "supervision_id": SUPERVISION_ID,
    }
    authorization_and_invocation = {
        "evidence_mode": "DISPOSABLE_PUBLIC_COMPOSITION_PROOF",
        "proof_expectation": {
            "proof_id": PROOF_ID,
            "fixture_composition_manifest_sha256": MANIFEST,
            "campaign_id": CAMPAIGN_ID,
            "campaign_run_id": CAMPAIGN_RUN_ID,
            "configuration_id": CONFIGURATION_ID,
            "cycle_id": CYCLE_ID,
            "execution_id": EXECUTION_ID,
            "factory_run_id": FACTORY_RUN_ID,
            "provider_execution_allowed": False,
            "automatic_retry_allowed": False,
            "manual_rerun_allowed": False,
            "resume_allowed": False,
            "restart_allowed": False,
            "successor_allowed": False,
        },
    }
    full_run_terminal_evidence = {
        "identity": identity,
        "authorization_and_invocation": authorization_and_invocation,
        "full_run_accounting": full_run_accounting,
        "campaign_acceptance_verdict": "CAMPAIGN_PASS",
        "campaign_pass": True,
    }
    report_payload = {
        "report_kind": "TERMINAL",
        "campaign_acceptance_verdict": "CAMPAIGN_PASS",
        "campaign_acceptance": True,
        "identity": {
            "campaign_id": CAMPAIGN_ID,
            "run_id": CAMPAIGN_RUN_ID,
            "configuration_id": CONFIGURATION_ID,
            "cycle_id": CYCLE_ID,
            "execution_id": EXECUTION_ID,
            "factory_run_id": FACTORY_RUN_ID,
            "supervision_id": SUPERVISION_ID,
            "report_id": "report-c8",
        },
        "full_run_terminal_evidence": full_run_terminal_evidence,
        "restart_created": False,
        "successor_created": False,
    }
    report_text = json.dumps(
        report_payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    report_hash = hashlib.sha256(report_text.encode("utf-8")).hexdigest()
    connection.execute(
        """
        INSERT INTO printer_memory_factory_campaign_reports (
            report_id, campaign_id, configuration_id, report_kind,
            report_state, replay_of_report_id, report_hash, report_json, created_at
        ) VALUES ('report-c8', ?, ?, 'TERMINAL', 'REPORT_TERMINAL',
                  NULL, ?, ?, ?)
        """,
        (CAMPAIGN_ID, CONFIGURATION_ID, report_hash, report_text, NOW),
    )

    artifact_dir = artifact_root / EXECUTION_ID
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "c8.campaign-report.json"
    artifact_path.write_bytes(report_text.encode("utf-8"))

    return {
        "report_payload": report_payload,
        "report_text": report_text,
        "report_hash": report_hash,
        "artifact_path": artifact_path,
        "full_run_terminal_evidence": full_run_terminal_evidence,
    }


def _build_fixture(tmp_path: Path) -> tuple[Path, Path, dict]:
    proof_dir = tmp_path / "proof"
    proof_dir.mkdir()
    artifact_root = proof_dir / "checkpoint8-artifacts"
    artifact_root.mkdir()
    db_path = proof_dir / "checkpoint8-controlling-proof.sqlite3"
    apply_migrations(db_path)

    connection = sqlite3.connect(db_path)
    try:
        details = _insert_base_graph(connection, artifact_root)
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        assert violations == []
        connection.commit()
    finally:
        connection.close()

    report_package = {
        "artifact_count": 1,
        "artifact_created": True,
        "artifact_path": str(details["artifact_path"]),
        "artifacts": [str(details["artifact_path"])],
        "campaign_id": CAMPAIGN_ID,
        "configuration_id": CONFIGURATION_ID,
        "report_hash": details["report_hash"],
        "report_id": "report-c8",
        "report_rows": 1,
    }
    report_only = {
        "status": "REPLAYED",
        "mode": "REPORT_ONLY",
        "report_kind": "TERMINAL",
        "requested_identity": {
            "campaign_id": CAMPAIGN_ID,
            "run_id": CAMPAIGN_RUN_ID,
        },
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "database_writes": 0,
        "replay_new_source_calls": 0,
        "replay_new_scheduler_calls": 0,
        "replay_database_writes": 0,
        "full_run_terminal_evidence": details["full_run_terminal_evidence"],
    }
    summary = {
        "summary_schema": "CHECKPOINT8_CONTROLLING_PROOF_SUMMARY_V1",
        "proof_id": PROOF_ID,
        "git_head": "c" * 40,
        "campaign_id": CAMPAIGN_ID,
        "run_id": CAMPAIGN_RUN_ID,
        "campaign_acceptance_verdict": "CAMPAIGN_PASS",
        "campaign_pass": True,
        "fixture_composition_manifest_sha256": MANIFEST,
        "fixture_transport_operation_count": 4,
        "network_attempt_count": 0,
        "network_attempts": [],
        "replay_zero_work": True,
        "pre_run_evidence": {
            "db_path": str(db_path.resolve()),
            "artifact_root": str(artifact_root.resolve()),
            "fixture_composition_manifest_sha256": MANIFEST,
        },
        "post_run_evidence": {
            "integrity_check": "ok",
            "foreign_key_violations": 0,
            "protected_capability_deltas": {
                "printer_memory_retrieval_queries": 0,
                "printer_memory_retrieval_matches": 0,
                "printer_paper_decisions": 0,
                "printer_paper_positions": 0,
                "printer_paper_trade_events": 0,
                "printer_paper_trade_audits": 0,
            },
            "longer_window_counts": {
                "WINDOW_1H": 0,
                "WINDOW_4H": 0,
                "WINDOW_12H": 0,
                "WINDOW_24H": 0,
            },
        },
        "terminal": {
            "campaign_id": CAMPAIGN_ID,
            "run_id": CAMPAIGN_RUN_ID,
            "campaign_acceptance_verdict": "CAMPAIGN_PASS",
            "campaign_pass": True,
            "execution_id": EXECUTION_ID,
            "report": report_package,
        },
        "report_only": report_only,
        "sentinel_path": str((proof_dir / "checkpoint8-controlling-attempt.json").resolve()),
    }
    (proof_dir / "checkpoint8-controlling-attempt.json").write_text(
        json.dumps(
            {
                "attempt_ordinal": 1,
                "git_head": summary["git_head"],
                "proof_id": PROOF_ID,
                "sentinel_schema": "CHECKPOINT8_CONTROLLING_ATTEMPT_V1",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_summary(proof_dir, summary)
    return proof_dir, db_path, summary


def _mutate_db(db_path: Path, sql: str, params: tuple = ()) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(sql, params)
        connection.commit()
    finally:
        connection.close()


def _replace_row(
    db_path: Path,
    table: str,
    key_column: str,
    key_value,
    updates: dict,
) -> None:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        row = connection.execute(
            f'SELECT * FROM "{table}" WHERE "{key_column}"=?',
            (key_value,),
        ).fetchone()
        assert row is not None
        payload = dict(row)
        payload.update(updates)
        connection.execute(
            f'DELETE FROM "{table}" WHERE "{key_column}"=?',
            (key_value,),
        )
        columns = tuple(payload)
        placeholders = ",".join("?" for _ in columns)
        column_sql = ",".join(f'"{column}"' for column in columns)
        connection.execute(
            f'INSERT INTO "{table}" ({column_sql}) VALUES ({placeholders})',
            tuple(payload[column] for column in columns),
        )
        connection.commit()
    finally:
        connection.close()


def _delete_clean_episode_chain(db_path: Path, episode_id: int) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            "DELETE FROM printer_memory_fingerprints WHERE episode_id=?",
            (episode_id,),
        )
        connection.execute(
            "DELETE FROM printer_episodes WHERE id=?",
            (episode_id,),
        )
        connection.commit()
    finally:
        connection.close()


def _mutate_summary(proof_dir: Path, mutate) -> None:
    path = proof_dir / "checkpoint8-controlling-proof-summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    _write_summary(proof_dir, payload)


def test_representative_real_schema_fixture_should_pass_full_independent_inspection(
    tmp_path: Path,
) -> None:
    inspector = _load_inspector("dtw57_real_schema_success")
    proof_dir, _db_path, _summary = _build_fixture(tmp_path)

    result = inspector.inspect_checkpoint8_frozen_proof_directory(proof_dir)

    assert result["pass"] is True
    assert result["verdict"] == "CHECKPOINT8_INDEPENDENT_INSPECTION_PASS"
    assert result["graph_projection"]["exact_two_terminal_window_15m"] is True
    assert result["graph_projection"]["both_clean_memory"] is True
    assert result["graph_projection"]["both_fingerprints_present"] is True


@pytest.mark.parametrize(
    ("case_name", "mutator", "expected_error"),
    [
        (
            "missing_factory_binding",
            lambda proof_dir, db_path: _replace_row(
                db_path,
                "printer_memory_factory_campaign_runs",
                "run_id",
                CAMPAIGN_RUN_ID,
                {"authoritative_run_id": None},
            ),
            "CURRENT_FACTORY_RUN_BINDING_MISSING",
        ),
        (
            "conflicting_factory_identity",
            lambda proof_dir, db_path: _mutate_summary(
                proof_dir,
                lambda payload: payload["report_only"]["full_run_terminal_evidence"][
                    "identity"
                ].__setitem__("factory_run_id", ALT_FACTORY_RUN_ID),
            ),
            "CURRENT_FACTORY_RUN_IDENTITY_CONFLICT",
        ),
        (
            "campaign_window_memory_binding_missing",
            lambda proof_dir, db_path: _replace_row(
                db_path,
                "printer_memory_factory_campaign_windows",
                "window_id",
                "campaign-window-1",
                {"memory_window_row_id": None},
            ),
            "CAMPAIGN_MEMORY_WINDOW_BINDING_MISSING",
        ),
        (
            "clean_episode_missing",
            lambda proof_dir, db_path: _delete_clean_episode_chain(
                db_path,
                201,
            ),
            "CLEAN_EPISODE_CARDINALITY_MISMATCH",
        ),
        (
            "fingerprint_payload_mismatch",
            lambda proof_dir, db_path: _mutate_db(
                db_path,
                "UPDATE printer_memory_fingerprints "
                "SET fingerprint_payload_json=? WHERE episode_id=201",
                (
                    json.dumps(
                        {
                            "episode_id": 999,
                            "window_id": 101,
                            "token_id": 1,
                            "pair_id": 11,
                            "window_kind": "WINDOW_15M",
                        },
                        sort_keys=True,
                    ),
                ),
            ),
            "FINGERPRINT_PAYLOAD_IDENTITY_MISMATCH",
        ),
        (
            "scheduler_join_missing",
            lambda proof_dir, db_path: _mutate_db(
                db_path,
                "DELETE FROM printer_memory_factory_campaign_scheduler_work "
                "WHERE scheduler_work_id='lifecycle-work-1'",
            ),
            "SCHEDULER_JOIN_MISMATCH",
        ),
        (
            "lifecycle_factory_run_mismatch",
            lambda proof_dir, db_path: _replace_row(
                db_path,
                "printer_memory_factory_campaign_scheduler_work",
                "scheduler_work_id",
                "lifecycle-work-1",
                {"factory_run_id": ALT_FACTORY_RUN_ID},
            ),
            "LIFECYCLE_FACTORY_RUN_IDENTITY_MISMATCH",
        ),
        (
            "source_request_response_mismatch",
            lambda proof_dir, db_path: _mutate_db(
                db_path,
                "UPDATE printer_source_responses SET source_request_id=2 WHERE id=1",
            ),
            "SOURCE_REQUEST_RESPONSE_LINK_MISMATCH",
        ),
        (
            "report_artifact_bytes_mismatch",
            lambda proof_dir, db_path: (
                next((proof_dir / "checkpoint8-artifacts").rglob("*.campaign-report.json"))
                .write_text('{"tampered":true}', encoding="utf-8")
            ),
            "REPORT_ARTIFACT_HASH_MISMATCH",
        ),
        (
            "replay_requested_identity_mismatch",
            lambda proof_dir, db_path: _mutate_summary(
                proof_dir,
                lambda payload: payload["report_only"]["requested_identity"].__setitem__(
                    "run_id", "wrong-campaign-run"
                ),
            ),
            "REPORT_REPLAY_IDENTITY_MISMATCH",
        ),
    ],
)
def test_representative_real_schema_negative_cases_fail_closed_at_exact_boundary(
    tmp_path: Path,
    case_name,
    mutator,
    expected_error: str,
) -> None:
    inspector = _load_inspector(f"dtw57_{case_name}")
    proof_dir, db_path, _summary = _build_fixture(tmp_path)
    mutator(proof_dir, db_path)

    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match=expected_error,
    ):
        inspector.inspect_checkpoint8_frozen_proof_directory(proof_dir)

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import operational_campaign_recovery as recovery
from printer_v1.operator_cli.campaign_ownership import create_cycle_with_two_slots
from printer_v1.operator_cli.campaign_supervision import acquire_campaign_supervision
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES


EXECUTION_ID = "20260814T172224Z-490856f405bf"
CAMPAIGN_ID = f"{EXECUTION_ID}-campaign"
CONFIGURATION_ID = f"{EXECUTION_ID}-configuration"
RUN_ID = f"{EXECUTION_ID}-campaign-run"
CYCLE_ID = f"{EXECUTION_ID}-cycle"
SUPERVISION_ID = f"{EXECUTION_ID}-supervision"
OWNER_ID = f"{EXECUTION_ID}-owner"
FACTORY_RUN_ID = "ed0fa279-38e6-401b-8b34-0a9531a9c720"
CAUSE = "FourTokenFactoryAdapterError: cycle terminal reconciliation requires a fresh transaction"
MINT_1 = "yUmeQo96g6MurikjHiMg7u23X5yQXJ9SQpoJPcbpump"
MINT_2 = "CAGtwKrcnwgLABdg5o16oMczxUV6i1pj973K9XWQpump"
START = datetime(2026, 8, 14, 17, 22, 24, 788541, tzinfo=timezone.utc)
NOW = datetime(2026, 8, 15, 8, 0, 0, tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _downgrade_fixture_to_055(db: Path) -> None:
    connection = sqlite3.connect(db)
    try:
        connection.executescript(
            """
            DROP TRIGGER IF EXISTS printer_four_token_pre_lifecycle_provenance_exact_shape;
            DROP TRIGGER IF EXISTS printer_four_token_pre_lifecycle_provenance_immutable_update;
            DROP TRIGGER IF EXISTS printer_four_token_pre_lifecycle_provenance_immutable_delete;
            DROP TRIGGER IF EXISTS printer_pre_admission_attempt_forbids_pre_lifecycle_provenance;
            DROP TRIGGER IF EXISTS printer_pre_admission_attempt_immutable_delete;
            DROP TABLE IF EXISTS printer_four_token_pre_lifecycle_terminal_provenance;
            DELETE FROM printer_schema_migrations
            WHERE version='056_four_token_pre_lifecycle_terminal_provenance.sql';
            """
        )
        connection.commit()
    finally:
        connection.close()


def _locked_snapshot(db: Path) -> dict[str, list[tuple[object, ...]]]:
    connection = sqlite3.connect(db)
    try:
        result: dict[str, list[tuple[object, ...]]] = {}
        for table in LOCKED_CAPABILITY_TABLES:
            rows = connection.execute(f'SELECT * FROM "{table}"').fetchall()
            result[table] = sorted(tuple(row) for row in rows)
        return result
    finally:
        connection.close()


def _artifact_payloads() -> dict[str, bytes]:
    child = {
        "error_type": "FourTokenFactoryAdapterError",
        "error_message": "cycle terminal reconciliation requires a fresh transaction",
        "terminal_truth_status": "RECONSTRUCTED",
    }
    summary = {
        "original_exception_type": "FourTokenFactoryAdapterError",
        "closure_errors": [
            "cleanup:OperationalError:database is locked",
            "reconciliation:OperationalError:database is locked",
        ],
        "accounting_status": "NOT_FINALIZED_CLEANUP_UNPROVEN",
        "report_block_reason": "TERMINAL_CLEANUP_UNPROVEN",
    }
    return {
        "application-marker.json": b'{"execution":"historical"}\n',
        "git-provenance-manifest.json": b'{"git_head":"aa5ab488c74b90ba57b1ca8e390bb50507609537"}\n',
        "wrapper-terminal.json": b'{"status":"failed"}\n',
        "child-terminal.json": b'{"status":"blocked"}\n',
        "child-stderr.txt": (json.dumps(child, sort_keys=True) + "\n").encode(),
        "terminal-summary.json": (json.dumps(summary, sort_keys=True) + "\n").encode(),
    }


def _prepare_exact_residue(tmp_path: Path, *, include_discovery_batch: bool = False):
    db = tmp_path / "historical.sqlite3"
    apply_migrations(db)
    _downgrade_fixture_to_055(db)
    pre_campaign = tmp_path / "printer_v1.pre-campaign.backup.sqlite3"
    shutil.copy2(db, pre_campaign)

    root = tmp_path / EXECUTION_ID
    root.mkdir()
    payloads = _artifact_payloads()
    for name, payload in payloads.items():
        (root / name).write_bytes(payload)

    connection = sqlite3.connect(db)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES (?,?,?,?,?)",
        (
            CAMPAIGN_ID,
            "RUNNING",
            "OPERATIONAL_PERSISTENT",
            f"sha256:{_sha256(pre_campaign)}",
            "V2-9.8B-FOUR-TOKEN-BOUNDED-CAPACITY-PROOF-V1",
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json) VALUES (?,?,?,?,?)",
        (
            CONFIGURATION_ID,
            CAMPAIGN_ID,
            "a" * 64,
            json.dumps({"execution_id": EXECUTION_ID, "run_id": RUN_ID}),
            json.dumps({"git_head": "aa5ab488c74b90ba57b1ca8e390bb50507609537"}),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,updated_at) "
        "VALUES (?,?,?,?,NULL,?,?)",
        (RUN_ID, CAMPAIGN_ID, 1, "RUNNING", START.isoformat(), START.isoformat()),
    )
    for token_id, pair_id, mint in ((53, 57, MINT_1), (54, 58, MINT_2)):
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?,'solana')",
            (token_id, mint),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) VALUES (?,?,?,?)",
            (pair_id, token_id, f"pool-{pair_id}", mint),
        )
    for queue_id, token_id, pair_id in ((58, 53, 57), (59, 54, 58)):
        connection.execute(
            "INSERT INTO printer_tracking_queue("
            "id,token_id,pair_id,tracking_lane,tracking_action,priority_reason,"
            "queue_status,source_status,data_quality_label) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                queue_id,
                token_id,
                pair_id,
                "TRACK_NORMAL",
                "PROMOTE_TO_TRACK_NORMAL",
                "combined_discovery_handoff",
                "QUEUED",
                "COMPLETE",
                "CLEAN_DATA",
            ),
        )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            FACTORY_RUN_ID,
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "b" * 64,
            json.dumps(
                {
                    "campaign_id": CAMPAIGN_ID,
                    "campaign_run_id": RUN_ID,
                    "cycle_id": CYCLE_ID,
                    "git_provenance": {
                        "git_head": "aa5ab488c74b90ba57b1ca8e390bb50507609537"
                    },
                },
                sort_keys=True,
            ),
            START.isoformat(),
        ),
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaign_runs SET authoritative_run_id=? WHERE run_id=?",
        (FACTORY_RUN_ID, RUN_ID),
    )
    create_cycle_with_two_slots(
        connection,
        campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID,
        cycle_id=CYCLE_ID,
        cycle_ordinal=1,
        slots=(
            {
                "token_slot_id": f"slot-{CYCLE_ID}-1",
                "slot_ordinal": 1,
                "token_identity": f"solana-mainnet:{MINT_1}",
                "token_row_id": 53,
                "mint_identity": MINT_1,
                "pair_identity": "pool-57",
                "pair_row_id": 57,
                "lifecycle_identity": "PUMPSWAP_GRADUATED_CONFIRMED",
                "tracking_queue_id": 58,
                "replacement_predecessor_slot_id": None,
            },
            {
                "token_slot_id": f"slot-{CYCLE_ID}-2",
                "slot_ordinal": 2,
                "token_identity": f"solana-mainnet:{MINT_2}",
                "token_row_id": 54,
                "mint_identity": MINT_2,
                "pair_identity": "pool-58",
                "pair_row_id": 58,
                "lifecycle_identity": "PUMPSWAP_GRADUATED_CONFIRMED",
                "tracking_queue_id": 59,
                "replacement_predecessor_slot_id": None,
            },
        ),
        now=START.isoformat(),
    )
    connection.commit()
    connection.close()

    acquire_campaign_supervision(
        db,
        lock_path=root / "campaign.lease.lock",
        supervision_id=SUPERVISION_ID,
        campaign_id=CAMPAIGN_ID,
        configuration_id=CONFIGURATION_ID,
        run_id=RUN_ID,
        owner_id=OWNER_ID,
        lease_seconds=90,
        now=START,
    )

    connection = sqlite3.connect(db)
    for offset, job_id in enumerate(range(2011, 2021)):
        succeeded = job_id <= 2018
        status = "SUCCEEDED" if succeeded else "CANCELLED"
        connection.execute(
            "INSERT INTO printer_scheduler_jobs("
            "id,job_name,job_kind,status,scheduled_for,finished_at,locked_at,lock_owner) "
            "VALUES (?,?,?,?,?,?,NULL,NULL)",
            (
                job_id,
                f"historical-{job_id}",
                "DISCOVERY_REFRESH" if succeeded else "TRACK_NORMAL_FIRST_15M",
                status,
                START.isoformat(),
                START.isoformat(),
            ),
        )
        scope = "DISCOVERY_SELECTION" if succeeded else "FIRST_15M_HANDOFF"
        slot_id = None if succeeded else f"slot-{CYCLE_ID}-{job_id - 2018}"
        connection.execute(
            "INSERT INTO printer_memory_factory_campaign_scheduler_work("
            "scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,window_id,"
            "work_intent,deadline_at,work_state,scheduler_job_id,"
            "ownership_contract_version,stage_id,work_scope,target_category,"
            "target_identity,factory_run_id,first_terminal_cause,terminal_at,created_at,updated_at) "
            "VALUES (?,?,?,?,?,NULL,?,?,?,?,?,?,?,?,?,NULL,?,?,?,?)",
            (
                f"historical-work-{job_id}",
                CAMPAIGN_ID,
                RUN_ID,
                CYCLE_ID,
                slot_id,
                scope,
                START.isoformat(),
                status,
                job_id,
                "V2_STAGE_SCOPED",
                f"historical-stage-{job_id}",
                scope,
                "CAMPAIGN" if succeeded else "TOKEN_SLOT",
                CAMPAIGN_ID if succeeded else str(slot_id),
                f"HISTORICAL_{status}",
                START.isoformat(),
                START.isoformat(),
                START.isoformat(),
            ),
        )
    if include_discovery_batch:
        batch_id = (
            "discovery-batch:20260814T172224Z-490856f405bf-campaign:"
            "20260814T172224Z-490856f405bf-campaign-run:"
            "20260814T172224Z-490856f405bf-cycle"
        )
        work_types = (
            "DISCOVERY_PUMPFUN_LATEST",
            "DISCOVERY_IDENTITY_MERGE",
            "DISCOVERY_ORIGIN_VERIFICATION",
            "DISCOVERY_PUMPSWAP_CONFIRMATION",
            "DISCOVERY_FIXED_ELIGIBILITY_GATES",
            "DISCOVERY_UNIFORM_SELECTION",
            "DISCOVERY_TRACKING_HANDOFF_SLOT_1",
            "DISCOVERY_TRACKING_HANDOFF_SLOT_2",
        )
        connection.execute(
            """INSERT INTO printer_discovery_batches(
                   discovery_batch_id,campaign_id,configuration_id,run_id,cycle_id,
                   cycle_cutoff,policy_version,provider_contract_versions_json,
                   git_provenance_identity,campaign_selection_seed_identity,
                   cycle_seed_hash,pump_cursor_slot,pump_cursor_signature,
                   pump_continuity_state,batch_state,canonical_hash,created_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'UNKNOWN','DISCOVERING',?,?)""",
            (
                batch_id,
                CAMPAIGN_ID,
                CONFIGURATION_ID,
                RUN_ID,
                CYCLE_ID,
                START.isoformat(),
                "V2-9.8B-FOUR-TOKEN-BOUNDED-CAPACITY-PROOF-V1",
                '{"direct":"V2-9.7E.11","geckoterminal":"V2-9.7D.7B.4B"}',
                "live-operational:V2-9.7E.11",
                "b4c15ed2f729d353afa0d3e6cc1ae600b9fbfc37cbd9c35733be5a30fdffb4c7",
                "092dcebfe80c993630c94d6e5b6e29fefc84194acf64e50e6b69121ec98c7288",
                None,
                None,
                "4071014af1e602c399482f07b1da357dad9ec48474edc67a6a787945838f0443",
                START.isoformat(),
            ),
        )
        for index, (job_id, work_type) in enumerate(
            zip(range(2011, 2019), work_types, strict=True), start=1
        ):
            connection.execute(
                """INSERT INTO printer_discovery_work(
                       discovery_work_id,discovery_batch_id,campaign_id,run_id,cycle_id,
                       scheduler_job_id,work_type,work_state,deadline_at,
                       first_terminal_cause,terminal_at,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,'SUCCEEDED',?,?,?,?,?)""",
                (
                    f"work:{work_type}:{batch_id}",
                    batch_id,
                    CAMPAIGN_ID,
                    RUN_ID,
                    CYCLE_ID,
                    job_id,
                    work_type,
                    START.isoformat(),
                    f"HISTORICAL_DISCOVERY_WORK_SUCCEEDED_{index}",
                    START.isoformat(),
                    START.isoformat(),
                    START.isoformat(),
                ),
            )
    connection.commit()
    connection.close()

    expected_artifacts = {
        name: hashlib.sha256(payload).hexdigest() for name, payload in payloads.items()
    }
    contract_type = getattr(recovery, "HistoricalFourTokenRecoveryContract", None)
    assert contract_type is not None, "HistoricalFourTokenRecoveryContract is missing"
    contract = contract_type(
        expected_current_sha256=_sha256(db),
        pre_campaign_backup_sha256=_sha256(pre_campaign),
        expected_artifact_sha256=expected_artifacts,
    )
    return db, pre_campaign, root, contract


def _run_recovery(db, pre_campaign, root, contract, tmp_path, **overrides):
    function = getattr(recovery, "reconcile_exact_historical_four_token_execution", None)
    assert callable(function), "exact historical reconciliation API is missing"
    kwargs = {
        "operator_approved": True,
        "current_db": db,
        "pre_campaign_backup": pre_campaign,
        "artifact_root": root,
        "recovery_root": tmp_path / "recovery",
        "contract": contract,
        "live_process_probe": lambda _execution: False,
        "now": NOW,
    }
    kwargs.update(overrides)
    return function(**kwargs)


def test_exact_historical_reconciliation_closes_only_approved_residue(tmp_path: Path) -> None:
    db, pre_campaign, root, contract = _prepare_exact_residue(
        tmp_path, include_discovery_batch=True
    )
    locked_before = _locked_snapshot(db)
    result = _run_recovery(db, pre_campaign, root, contract, tmp_path)

    assert result["status"] == "V2_9_8B_HISTORICAL_FOUR_TOKEN_RECONCILED"
    assert result["source_calls"] == 0
    assert result["scheduler_runtime_calls"] == 0
    assert result["migration_056_provenance_rows"] == 0
    assert result["changed_database_row_identities"] == 10
    assert not (root / "campaign.lease.lock").exists()

    connection = sqlite3.connect(db)
    try:
        assert connection.execute(
            "SELECT campaign_state FROM printer_memory_factory_campaigns WHERE campaign_id=?",
            (CAMPAIGN_ID,),
        ).fetchone()[0] == "TERMINAL_FAILED"
        assert connection.execute(
            "SELECT run_state FROM printer_memory_factory_campaign_runs WHERE run_id=?",
            (RUN_ID,),
        ).fetchone()[0] == "TERMINAL_FAILED"
        assert connection.execute(
            "SELECT cycle_state FROM printer_memory_factory_campaign_cycles WHERE cycle_id=?",
            (CYCLE_ID,),
        ).fetchone()[0] == "TERMINAL_FAILED"
        assert connection.execute(
            "SELECT token_state FROM printer_memory_factory_campaign_token_slots "
            "WHERE cycle_id=? ORDER BY slot_ordinal",
            (CYCLE_ID,),
        ).fetchall() == [("MANUAL_REVIEW",), ("MANUAL_REVIEW",)]
        assert connection.execute(
            "SELECT queue_status,tracking_action,priority_reason FROM printer_tracking_queue "
            "WHERE id IN (58,59) ORDER BY id"
        ).fetchall() == [
            ("SKIPPED", "MANUAL_REVIEW", f"campaign_terminal:{CAUSE}"),
            ("SKIPPED", "MANUAL_REVIEW", f"campaign_terminal:{CAUSE}"),
        ]
        supervision = connection.execute(
            "SELECT supervision_state,terminal_status,cleanup_completed_at,lease_released_at "
            "FROM printer_memory_factory_campaign_supervision WHERE supervision_id=?",
            (SUPERVISION_ID,),
        ).fetchone()
        assert supervision[0:2] == ("TERMINAL", "FAILED")
        assert supervision[2] is not None and supervision[3] is not None
        factory = connection.execute(
            "SELECT run_status,stop_reason,finished_at FROM printer_memory_factory_runs WHERE run_id=?",
            (FACTORY_RUN_ID,),
        ).fetchone()
        assert factory[0] == "SAFE_STOPPED"
        assert factory[1] == CAUSE
        assert factory[2] is not None
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows WHERE campaign_id=?",
            (CAMPAIGN_ID,),
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps WHERE run_id=?",
            (FACTORY_RUN_ID,),
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts WHERE campaign_id=?",
            (CAMPAIGN_ID,),
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
            "AND name='printer_four_token_pre_lifecycle_terminal_provenance'"
        ).fetchone()[0] == 0
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()
    assert _locked_snapshot(db) == locked_before


def test_exact_historical_reconciliation_rejects_queue_drift_and_live_process(tmp_path: Path) -> None:
    db, pre_campaign, root, contract = _prepare_exact_residue(tmp_path)
    connection = sqlite3.connect(db)
    connection.execute(
        "UPDATE printer_tracking_queue SET queue_status='SKIPPED' WHERE id=58"
    )
    connection.commit()
    connection.close()
    drifted_contract = type(contract)(
        expected_current_sha256=_sha256(db),
        pre_campaign_backup_sha256=contract.pre_campaign_backup_sha256,
        expected_artifact_sha256=contract.expected_artifact_sha256,
    )
    error_type = getattr(recovery, "OperationalCampaignRecoveryError")
    with pytest.raises(error_type, match="tracking queue|queue"):
        _run_recovery(db, pre_campaign, root, drifted_contract, tmp_path)

    other = tmp_path / "live"
    other.mkdir()
    db2, backup2, root2, contract2 = _prepare_exact_residue(other)
    with pytest.raises(error_type, match="live Printer"):
        _run_recovery(
            db2,
            backup2,
            root2,
            contract2,
            other,
            live_process_probe=lambda _execution: True,
        )


def test_exact_historical_reconciliation_is_idempotent_without_second_mutation(tmp_path: Path) -> None:
    db, pre_campaign, root, contract = _prepare_exact_residue(
        tmp_path, include_discovery_batch=True
    )
    first = _run_recovery(db, pre_campaign, root, contract, tmp_path)
    first_sha = _sha256(db)
    second = _run_recovery(
        db,
        pre_campaign,
        root,
        contract,
        tmp_path,
        recovery_root=tmp_path / "recovery-second",
    )
    assert first["status"] == "V2_9_8B_HISTORICAL_FOUR_TOKEN_RECONCILED"
    assert second["status"] == "V2_9_8B_HISTORICAL_FOUR_TOKEN_ALREADY_RECONCILED"
    assert second["database_writes"] == 0
    assert _sha256(db) == first_sha

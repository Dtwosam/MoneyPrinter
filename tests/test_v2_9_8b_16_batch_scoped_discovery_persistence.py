"""Disposable proof for V2-9.8B.16 batch-scoped discovery persistence."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.db import apply_migrations
from printer_v1.discovery import combined_executor as combined_module
from printer_v1.discovery.combined_executor import (
    CombinedDiscoveryFixtures,
    CombinedPumpfunCampaignExecutor,
    FixtureOriginProof,
    FixturePumpSwapProof,
)
from printer_v1.discovery.persistence import (
    DiscoveryPersistenceError,
    count_locked_financial_rows,
    insert_merged_candidate,
    insert_origin_verification,
    insert_provider_observation,
    insert_pumpswap_confirmation,
)
from printer_v1.operator_cli import operational_memory_factory_command as operational
from printer_v1.operator_cli.abstract_campaign_command import (
    AbstractCampaignCommand,
    CAMPAIGN_MODE,
    CENTRAL_SCHEDULER_OWNER,
    CampaignCeilings,
    OwnerPort,
    SOURCE_GOVERNOR_OWNER,
)
from printer_v1.operator_cli.campaign_ownership import create_campaign_run
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.origin_lifecycle_campaign import (
    OriginToLifecycleCampaignDriver,
)
from printer_v1.operator_cli.unified_terminal_closure import (
    build_campaign_terminal_report,
)


NOW = "2026-07-27T20:00:00+00:00"
CUTOFF = "2026-07-27T20:06:00+00:00"
MINT = "BatchScopedMint11111111111111111111111111111"
POOL = "BatchScopedPool11111111111111111111111111111"
SIGNATURE = "batch-scoped-migration-signature"
POLICY = "v2-9.8b.16"


def _provenance() -> dict[str, object]:
    return {
        "git_head": "e89efa47d63032e78458ea57c96f259e0daed393",
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": NOW,
    }


class BatchScopedDiscoveryPersistenceProof(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "proof.sqlite3"
        apply_migrations(self.db)
        self.source_port = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
        self.scheduler_port = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _create_command(self, ordinal: int) -> tuple[AbstractCampaignCommand, str]:
        campaign_id = f"campaign-{ordinal}"
        configuration_id = f"configuration-{ordinal}"
        run_id = f"run-{ordinal}"
        cycle_id = f"cycle-{ordinal}"
        seed = "batch-scoped-proof-seed"
        ceilings = CampaignCeilings(
            campaign_count=1,
            cycle_count=1,
            duration_seconds=3600,
            source_calls=45,
            scheduler_work=40,
            storage_bytes=8_000_000,
            failures=10,
        )
        configuration = {
            "token_capacity": 2,
            "campaign_selection_seed": seed,
            "ceilings": {
                "campaign_count": 1,
                "cycle_count": 1,
                "duration_seconds": 3600,
                "source_calls": 45,
                "scheduler_work": 40,
                "storage_bytes": 8_000_000,
                "failures": 10,
            },
        }
        created = create_campaign(
            self.db,
            campaign_id=campaign_id,
            configuration_id=configuration_id,
            configuration=configuration,
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity=f"disposable-target-{ordinal}",
            proof_source_db_identity="read-only-source-identity",
            policy_version=POLICY,
        )
        connection = sqlite3.connect(self.db)
        try:
            create_campaign_run(
                connection,
                campaign_id=campaign_id,
                run_id=run_id,
                run_ordinal=1,
                now=NOW,
            )
            with connection:
                connection.execute(
                    """
                    INSERT INTO printer_memory_factory_campaign_cycles(
                        cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, 1, 'PLANNED', ?, ?)
                    """,
                    (cycle_id, campaign_id, run_id, NOW, NOW),
                )
                connection.execute(
                    "UPDATE printer_memory_factory_campaigns "
                    "SET campaign_state='RUNNING' WHERE campaign_id=?",
                    (campaign_id,),
                )
                connection.execute(
                    "UPDATE printer_memory_factory_campaign_runs "
                    "SET run_state='RUNNING' WHERE run_id=?",
                    (run_id,),
                )
        finally:
            connection.close()
        return (
            AbstractCampaignCommand(
                mode=CAMPAIGN_MODE,
                db_path=self.db,
                db_target_identity=f"disposable-target-{ordinal}",
                campaign_id=campaign_id,
                configuration_id=configuration_id,
                configuration_hash=str(created["configuration_hash"]),
                policy_version=POLICY,
                token_capacity=2,
                ceilings=ceilings,
                report_directory=self.root,
                report_directory_identity="path-sha256:" + "d" * 64,
                launch_git_provenance=_provenance(),
                run_id=run_id,
                report_id=f"report-{ordinal}",
            ),
            cycle_id,
        )

    def _fixtures(self, cycle_id: str) -> CombinedDiscoveryFixtures:
        origin = FixtureOriginProof(
            mint=MINT,
            signature=SIGNATURE,
            slot=900,
            block_time=1_722_112_000,
            origin_route="GRADUATION_NATIVE",
        )
        return CombinedDiscoveryFixtures(
            cycle_id=cycle_id,
            cycle_cutoff=CUTOFF,
            campaign_selection_seed="batch-scoped-proof-seed",
            provider_contract_versions={"direct": "V2-9.7E.45"},
            git_provenance_identity="git-v2-9.8b.16-proof",
            evaluated_at=NOW,
            direct_observations=(origin,),
            pumpswap_proofs={
                MINT: FixturePumpSwapProof(mint=MINT, pool_address=POOL)
            },
            # Preserve fixed policy and end with no selection or active tracking.
            holder_evidence_eligibility={
                MINT.lower(): {
                    "eligible": False,
                    "reason": "DISPOSABLE_PROOF_INELIGIBLE",
                    "source_name": "fixture",
                }
            },
        )

    def _execute(self, ordinal: int):
        command, cycle_id = self._create_command(ordinal)
        fixtures = self._fixtures(cycle_id)
        result = CombinedPumpfunCampaignExecutor(fixtures).execute(
            command=command,
            source_governor=self.source_port,
            central_scheduler=self.scheduler_port,
        )
        return command, fixtures, result

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def test_sequential_campaigns_and_same_batch_persistence_contracts(self) -> None:
        _, _, first = self._execute(1)
        _, _, second = self._execute(2)
        self.assertNotEqual("PERSISTENCE_FAULT", first.first_terminal_cause)
        self.assertNotEqual("PERSISTENCE_FAULT", second.first_terminal_cause)

        connection = self._connect()
        try:
            table_and_id = (
                ("printer_discovery_provider_observations", "observation_id"),
                ("printer_discovery_merged_candidates", "merged_candidate_id"),
                ("printer_discovery_origin_verifications", "origin_verification_id"),
                ("printer_discovery_pumpswap_confirmations", "pumpswap_confirmation_id"),
            )
            for table, identity in table_and_id:
                rows = connection.execute(
                    f"SELECT discovery_batch_id, {identity} FROM {table} "
                    "WHERE mint_identity=? ORDER BY discovery_batch_id",
                    (MINT,),
                ).fetchall()
                self.assertEqual(2, len(rows), table)
                self.assertEqual(2, len({row["discovery_batch_id"] for row in rows}))
                self.assertEqual(2, len({row[identity] for row in rows}))

            observation = connection.execute(
                "SELECT * FROM printer_discovery_provider_observations "
                "WHERE campaign_id='campaign-1'"
            ).fetchone()
            candidate = connection.execute(
                "SELECT * FROM printer_discovery_merged_candidates "
                "WHERE campaign_id='campaign-1'"
            ).fetchone()
            origin = connection.execute(
                "SELECT * FROM printer_discovery_origin_verifications "
                "WHERE discovery_batch_id=?",
                (observation["discovery_batch_id"],),
            ).fetchone()
            pumpswap = connection.execute(
                "SELECT * FROM printer_discovery_pumpswap_confirmations "
                "WHERE discovery_batch_id=?",
                (observation["discovery_batch_id"],),
            ).fetchone()

            observation_args = {
                "observation_id": observation["observation_id"],
                "discovery_batch_id": observation["discovery_batch_id"],
                "discovery_work_id": observation["discovery_work_id"],
                "campaign_id": observation["campaign_id"],
                "run_id": observation["run_id"],
                "cycle_id": observation["cycle_id"],
                "source_name": observation["source_name"],
                "request_kind": observation["request_kind"],
                "channel": observation["channel"],
                "mint_identity": observation["mint_identity"],
                "market_identity": observation["market_identity"],
                "lifecycle_identity": observation["lifecycle_identity"],
                "observed_at": observation["observed_at"],
                "captured_at": observation["captured_at"],
                "raw_payload_hash": observation["raw_payload_hash"],
                "factual_payload": json.loads(observation["factual_payload_json"]),
                "source_request_id": observation["source_request_id"],
                "source_response_id": observation["source_response_id"],
                "source_failure_id": observation["source_failure_id"],
                "now": NOW,
            }
            self.assertEqual(
                observation["observation_hash"],
                insert_provider_observation(connection, **observation_args),
            )
            conflict = dict(observation_args)
            conflict["observed_at"] = "2026-07-27T20:00:01+00:00"
            with self.assertRaisesRegex(
                DiscoveryPersistenceError,
                "conflicting provider observation repeat rejected",
            ):
                insert_provider_observation(connection, **conflict)

            candidate_args = {
                "merged_candidate_id": candidate["merged_candidate_id"],
                "discovery_batch_id": candidate["discovery_batch_id"],
                "campaign_id": candidate["campaign_id"],
                "run_id": candidate["run_id"],
                "cycle_id": candidate["cycle_id"],
                "mint_identity": candidate["mint_identity"],
                "market_identity": candidate["market_identity"],
                "lifecycle_identity": candidate["lifecycle_identity"],
                "channel_labels": json.loads(candidate["channel_labels_json"]),
                "identity_conflicts": json.loads(candidate["identity_conflicts_json"]),
                "evidence_gaps": json.loads(candidate["evidence_gaps_json"]),
                "origin_verification_state": candidate["origin_verification_state"],
                "pumpswap_confirmation_state": candidate["pumpswap_confirmation_state"],
                "first_failed_eligibility_gate": candidate["first_failed_eligibility_gate"],
                "now": NOW,
            }
            self.assertEqual(
                candidate["merged_candidate_hash"],
                insert_merged_candidate(connection, **candidate_args),
            )
            conflict = dict(candidate_args)
            conflict["channel_labels"] = ("TOP_PUMPFUN",)
            with self.assertRaisesRegex(
                DiscoveryPersistenceError,
                "conflicting merged candidate repeat rejected",
            ):
                insert_merged_candidate(connection, **conflict)

            origin_args = {
                "origin_verification_id": origin["origin_verification_id"],
                "discovery_batch_id": origin["discovery_batch_id"],
                "merged_candidate_id": origin["merged_candidate_id"],
                "mint_identity": origin["mint_identity"],
                "admission_state": origin["admission_state"],
                "verification_state": origin["verification_state"],
                "source_request_id": origin["source_request_id"],
                "source_response_id": origin["source_response_id"],
                "source_failure_id": origin["source_failure_id"],
                "transaction_signature": origin["transaction_signature"],
                "program_id": origin["program_id"],
                "slot": origin["slot"],
                "evidence_detail": json.loads(origin["evidence_detail_json"]),
                "now": NOW,
            }
            insert_origin_verification(connection, **origin_args)
            conflict = dict(origin_args)
            conflict["evidence_detail"] = {"source": "conflicting-fixture"}
            with self.assertRaisesRegex(
                DiscoveryPersistenceError,
                "conflicting origin verification repeat rejected",
            ):
                insert_origin_verification(connection, **conflict)

            pumpswap_args = {
                "pumpswap_confirmation_id": pumpswap["pumpswap_confirmation_id"],
                "discovery_batch_id": pumpswap["discovery_batch_id"],
                "merged_candidate_id": pumpswap["merged_candidate_id"],
                "mint_identity": pumpswap["mint_identity"],
                "market_identity": pumpswap["market_identity"],
                "admission_state": pumpswap["admission_state"],
                "confirmation_state": pumpswap["confirmation_state"],
                "source_request_id": pumpswap["source_request_id"],
                "source_response_id": pumpswap["source_response_id"],
                "source_failure_id": pumpswap["source_failure_id"],
                "pool_address": pumpswap["pool_address"],
                "program_id": pumpswap["program_id"],
                "evidence_detail": json.loads(pumpswap["evidence_detail_json"]),
                "now": NOW,
            }
            insert_pumpswap_confirmation(connection, **pumpswap_args)
            conflict = dict(pumpswap_args)
            conflict["confirmation_state"] = "FAILED"
            with self.assertRaisesRegex(
                DiscoveryPersistenceError,
                "conflicting pumpswap confirmation repeat rejected",
            ):
                insert_pumpswap_confirmation(connection, **conflict)

            connection.rollback()
            self.assertEqual("ok", connection.execute("PRAGMA integrity_check").fetchone()[0])
            self.assertEqual([], connection.execute("PRAGMA foreign_key_check").fetchall())
            self.assertEqual(
                0,
                connection.execute(
                    "SELECT COUNT(*) FROM printer_scheduler_jobs "
                    "WHERE status IN ('PENDING','RUNNING','RETRY')"
                ).fetchone()[0],
            )
            self.assertEqual(
                0,
                connection.execute(
                    "SELECT COUNT(*) FROM printer_discovery_work "
                    "WHERE work_state IN ('PLANNED','RUNNING')"
                ).fetchone()[0],
            )
            self.assertTrue(all(value == 0 for value in count_locked_financial_rows(connection).values()))
        finally:
            connection.close()

    def test_true_conflict_rolls_back_every_staged_path(self) -> None:
        command, cycle_id = self._create_command(3)
        fixtures = self._fixtures(cycle_id)
        connection = self._connect()
        relevant_tables = (
            "printer_discovery_batches",
            "printer_discovery_work",
            "printer_discovery_provider_observations",
            "printer_discovery_merged_candidates",
            "printer_discovery_origin_verifications",
            "printer_discovery_pumpswap_confirmations",
            "printer_discovery_selection_links",
            "printer_discovery_selected_item_links",
            "printer_selection_batches",
            "printer_selection_batch_items",
            "printer_tracking_queue",
            "printer_scheduler_jobs",
            "printer_memory_factory_campaign_token_slots",
            "printer_memory_factory_runs",
            "printer_memory_factory_run_steps",
            "printer_memory_windows",
            "printer_episodes",
            "printer_memory_fingerprints",
        )
        baseline = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in relevant_tables
        }
        locked_before = count_locked_financial_rows(connection)
        connection.close()

        original_insert = combined_module.insert_provider_observation

        def insert_then_conflict(db_connection, **kwargs):
            prior = dict(kwargs)
            prior["observed_at"] = "2026-07-27T19:59:59+00:00"
            original_insert(db_connection, **prior)
            return original_insert(db_connection, **kwargs)

        with patch.object(
            combined_module,
            "insert_provider_observation",
            side_effect=insert_then_conflict,
        ):
            result = CombinedPumpfunCampaignExecutor(fixtures).execute(
                command=command,
                source_governor=self.source_port,
                central_scheduler=self.scheduler_port,
            )
        self.assertEqual("FAILED", result.terminal_status)
        self.assertEqual("PERSISTENCE_FAULT", result.first_terminal_cause)
        self.assertEqual("DISCOVERY_PROVIDER_OBSERVATION", result.fault_details["persistence_stage"])
        self.assertEqual("provider_observation", result.fault_details["object_kind"])

        connection = self._connect()
        try:
            after = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in relevant_tables
            }
            self.assertEqual(baseline, after)
            self.assertEqual(locked_before, count_locked_financial_rows(connection))
            self.assertEqual("ok", connection.execute("PRAGMA integrity_check").fetchone()[0])
            self.assertEqual([], connection.execute("PRAGMA foreign_key_check").fetchall())
        finally:
            connection.close()

    def test_safe_fault_details_reach_terminal_evidence(self) -> None:
        command, cycle_id = self._create_command(4)
        secret = "api_key=DO_NOT_EXPOSE"
        with patch.object(
            combined_module,
            "insert_provider_observation",
            side_effect=DiscoveryPersistenceError(secret),
        ):
            result = OriginToLifecycleCampaignDriver().run(
                command=command,
                fixtures=self._fixtures(cycle_id),
                backup_path=self.root / "unused-backup.sqlite3",
                source_governor=self.source_port,
                central_scheduler=self.scheduler_port,
                selection_seed="batch-scoped-proof-seed",
            )
        expected_keys = {
            "exception_type",
            "safe_message",
            "persistence_stage",
            "object_kind",
            "first_terminal_cause",
            "lifecycle_started",
        }
        details = dict(result.lifecycle["fault_details"])
        self.assertEqual(expected_keys, set(details))
        self.assertEqual("DiscoveryPersistenceError", details["exception_type"])
        self.assertEqual("discovery persistence contract rejected", details["safe_message"])
        self.assertEqual("PERSISTENCE_FAULT", details["first_terminal_cause"])
        self.assertFalse(details["lifecycle_started"])
        self.assertFalse(result.lifecycle_started)

        report = build_campaign_terminal_report(
            campaign_id=command.campaign_id,
            configuration_id=command.configuration_id,
            run_id=command.run_id,
            cycle_id=cycle_id,
            report_id=command.report_id,
            factory_run_id=None,
            execution_id="disposable-proof",
            terminal_status="FAILED",
            terminal_cause="PERSISTENCE_FAULT",
            run_status="NOT_STARTED",
            lifecycle_started=False,
            reconciliation={},
            fault_details=details,
        )
        self.assertEqual(details, report["terminal"]["fault_details"])
        self.assertNotIn(secret, json.dumps(report, sort_keys=True))

    def test_artifact_logging_contract_is_truthful(self) -> None:
        paths = operational._artifact_paths("disposable-proof")
        self.assertNotIn("stdout", paths)
        self.assertNotIn("stderr", paths)
        source = inspect.getsource(operational.run_operational_campaign)
        self.assertNotIn('paths["stdout"]', source)
        self.assertNotIn('paths["stderr"]', source)
        wrapper = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "Start-PrinterV1-MemoryFactory.ps1"
        ).read_text(encoding="utf-8")
        self.assertNotIn("stdout.log", wrapper)
        self.assertNotIn("stderr.log", wrapper)


if __name__ == "__main__":
    unittest.main()

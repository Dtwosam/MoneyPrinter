"""Checkpoint 3 focused RED gates for discovery, selection and accounting.

Fixture-only and disposable SQLite. No provider, runtime, authorization,
authoritative database, memory, retrieval, decision or financial capability.
"""

from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import (
    CombinedDiscoveryFixtures,
    CombinedPumpfunCampaignExecutor,
    FixtureOriginProof,
    FixturePumpSwapProof,
)
from printer_v1.discovery.permanent_discovery_availability import (
    derive_campaign_source_request_key_root,
    request_key_belongs_to_root,
)
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

NOW = "2026-08-06T18:00:00+00:00"
CUTOFF = "2026-08-06T18:06:00+00:00"


def _mint(label: str) -> str:
    return (f"{label}Mint" + "1" * 44)[:44]


def _pool(label: str) -> str:
    return (f"{label}Pool" + "1" * 44)[:44]


MINT_A = _mint("Checkpoint3A")
MINT_B = _mint("Checkpoint3B")
FOREIGN_MINT = _mint("Checkpoint3Foreign")
POOL_A = _pool("Checkpoint3A")
POOL_B = _pool("Checkpoint3B")


def _provenance() -> dict[str, object]:
    return {
        "git_head": "d" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": NOW,
    }


class _RequestBeforeFailureExecutor(CombinedPumpfunCampaignExecutor):
    """Observe durable request count at the exact failure-persistence boundary."""

    def __init__(self, fixtures: CombinedDiscoveryFixtures) -> None:
        super().__init__(fixtures)
        self.request_counts_at_failure: list[int] = []

    def _store_failure(self, connection, usage, **kwargs):  # type: ignore[no-untyped-def]
        self.request_counts_at_failure.append(
            int(connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0])
        )
        return super()._store_failure(connection, usage, **kwargs)


class Checkpoint3Harness(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = Path(self.temp.name) / "checkpoint3.sqlite3"
        apply_migrations(self.db)
        configuration = {
            "token_capacity": 2,
            "ceilings": {
                "campaign_count": 1,
                "cycle_count": 1,
                "duration_seconds": 360,
                "source_calls": 45,
                "scheduler_work": 40,
                "storage_bytes": 8_000_000,
                "failures": 10,
            },
            "campaign_selection_seed": "checkpoint-3-seed",
            "report_directory_identity": "path-sha256:" + "e" * 64,
            "backup_preflight_references": {
                "preflight_status": "READY",
                "source_identity": "sha256:" + "a" * 64,
                "backup_sha256": "b" * 64,
                "required_migration": "032_campaign_ownership_schema.sql",
                "latest_migration": "050_campaign_scheduler_ownership_scope.sql",
            },
        }
        created = create_campaign(
            self.db,
            campaign_id="checkpoint-3-campaign",
            configuration_id="checkpoint-3-configuration",
            configuration=configuration,
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="checkpoint-3-isolated",
            proof_source_db_identity="checkpoint-3-source",
            policy_version="checkpoint-3",
        )
        self.configuration_hash = str(created["configuration_hash"])
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        create_campaign_run(
            connection,
            campaign_id="checkpoint-3-campaign",
            run_id="checkpoint-3-run",
            run_ordinal=1,
            now=NOW,
        )
        with connection:
            connection.execute(
                """
                INSERT INTO printer_memory_factory_campaign_cycles(
                    cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                    created_at, updated_at
                ) VALUES (
                    'checkpoint-3-cycle', 'checkpoint-3-campaign',
                    'checkpoint-3-run', 1, 'PLANNED', ?, ?
                )
                """,
                (NOW, NOW),
            )
            connection.execute(
                "UPDATE printer_memory_factory_campaigns SET campaign_state='RUNNING'"
            )
            connection.execute(
                "UPDATE printer_memory_factory_campaign_runs SET run_state='RUNNING'"
            )
        connection.close()
        self.command = AbstractCampaignCommand(
            mode=CAMPAIGN_MODE,
            db_path=self.db,
            db_target_identity="checkpoint-3-isolated",
            campaign_id="checkpoint-3-campaign",
            configuration_id="checkpoint-3-configuration",
            configuration_hash=self.configuration_hash,
            policy_version="checkpoint-3",
            token_capacity=2,
            ceilings=CampaignCeilings(
                campaign_count=1,
                cycle_count=1,
                duration_seconds=360,
                source_calls=45,
                scheduler_work=40,
                storage_bytes=8_000_000,
                failures=10,
            ),
            report_directory=Path(self.temp.name),
            report_directory_identity="path-sha256:" + "e" * 64,
            launch_git_provenance=_provenance(),
            run_id="checkpoint-3-run",
            report_id="checkpoint-3-report",
        )
        self.source_governor = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
        self.central_scheduler = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def fixtures(self, **overrides) -> CombinedDiscoveryFixtures:
        base = CombinedDiscoveryFixtures(
            cycle_id="checkpoint-3-cycle",
            cycle_cutoff=CUTOFF,
            campaign_selection_seed="checkpoint-3-seed",
            provider_contract_versions={"direct": "CHECKPOINT_3"},
            git_provenance_identity="checkpoint-3-git",
            evaluated_at=NOW,
            direct_observations=(
                FixtureOriginProof(
                    mint=MINT_A,
                    signature="MigrationSigA" + "z" * 30,
                    slot=500,
                    block_time=1_700_000_000,
                    bonding_curve="curveA" + "9" * 38,
                    origin_route="GRADUATION_NATIVE",
                ),
                FixtureOriginProof(
                    mint=MINT_B,
                    signature="MigrationSigB" + "z" * 30,
                    slot=501,
                    block_time=1_700_000_100,
                    bonding_curve="curveB" + "9" * 38,
                    origin_route="GRADUATION_NATIVE",
                ),
            ),
            pumpswap_proofs={
                MINT_A: FixturePumpSwapProof(mint=MINT_A, pool_address=POOL_A),
                MINT_B: FixturePumpSwapProof(mint=MINT_B, pool_address=POOL_B),
            },
        )
        return replace(base, **overrides) if overrides else base

    def execute(self, executor: CombinedPumpfunCampaignExecutor):
        return executor.execute(
            command=self.command,
            source_governor=self.source_governor,
            central_scheduler=self.central_scheduler,
        )


class Checkpoint3RedTests(Checkpoint3Harness):
    def test_existing_pair_must_match_candidate_token_identity(self) -> None:
        connection = sqlite3.connect(self.db)
        with connection:
            foreign_token_id = int(
                connection.execute(
                    "INSERT INTO printer_tokens(token_mint, token_status) "
                    "VALUES (?, 'TRACK_NORMAL')",
                    (FOREIGN_MINT,),
                ).lastrowid
            )
            connection.execute(
                """
                INSERT INTO printer_pairs(token_id, pair_address, base_token_mint)
                VALUES (?, ?, ?)
                """,
                (foreign_token_id, POOL_A, FOREIGN_MINT),
            )
        connection.close()

        result = self.execute(CombinedPumpfunCampaignExecutor(self.fixtures()))

        self.assertEqual(result.terminal_status, "FAILED")
        self.assertEqual(result.first_terminal_cause, "PAIR_TOKEN_IDENTITY_MISMATCH")
        connection = sqlite3.connect(self.db)
        try:
            self.assertEqual(
                int(
                    connection.execute(
                        "SELECT COUNT(*) FROM "
                        "printer_memory_factory_campaign_token_slots"
                    ).fetchone()[0]
                ),
                0,
            )
            self.assertEqual(
                int(connection.execute("SELECT COUNT(*) FROM printer_tracking_queue").fetchone()[0]),
                0,
            )
        finally:
            connection.close()

    def test_direct_failure_is_persisted_only_after_governed_request(self) -> None:
        fixtures = self.fixtures(
            direct_observations=(),
            pumpswap_proofs={},
            provider_failures_injected={"direct": "transport_unavailable"},
        )
        executor = _RequestBeforeFailureExecutor(fixtures)

        self.execute(executor)

        self.assertEqual(executor.request_counts_at_failure, [1])
        connection = sqlite3.connect(self.db)
        try:
            self.assertEqual(
                int(connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]),
                1,
            )
            self.assertEqual(
                int(connection.execute("SELECT COUNT(*) FROM printer_source_failures").fetchone()[0]),
                1,
            )
        finally:
            connection.close()

    def test_campaign_request_scope_rejects_prefix_collision(self) -> None:
        root = derive_campaign_source_request_key_root("checkpoint-3-execution")
        self.assertTrue(request_key_belongs_to_root(root, root))
        self.assertTrue(request_key_belongs_to_root(f"{root}-discovery-1", root))
        self.assertFalse(request_key_belongs_to_root(f"{root}shadow", root))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

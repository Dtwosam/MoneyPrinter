"""V2-9.7E.45 focused proof — typed graduation-native atomic activation (Route B).

Proves a migration-discovered graduated candidate activates through the executor
WITHOUT a Pump create transaction and WITHOUT writing (or fabricating) a create
origin row, while producing token/pair/queue/scheduler/slot identities identical
to the create-native route (Route A), which remains unchanged. Activation is
two-or-none. Zero real network; fixture-backed executor only.
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

NOW = "2026-07-24T15:00:00+00:00"
CUTOFF = "2026-07-24T15:06:00+00:00"
WSOL = "So11111111111111111111111111111111111111112"


def _mint(label: str) -> str:
    return (f"{label}Mint" + "1" * 44)[:44]


def _pool(label: str) -> str:
    return (f"{label}Pool" + "1" * 44)[:44]


MINT_A = _mint("A")
MINT_B = _mint("B")
POOL_A = _pool("A")
POOL_B = _pool("B")
# A real migration signature is base58-ish; its exact value must never reach the
# create origin registry.
MIG_SIG_A = "MigrationSigA" + "z" * 30
MIG_SIG_B = "MigrationSigB" + "z" * 30


def _provenance() -> dict[str, object]:
    return {
        "git_head": "d" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": NOW,
    }


class _Harness(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = Path(self.temp.name) / "gn.sqlite3"
        apply_migrations(self.db)
        self.ceilings = CampaignCeilings(
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
            "ceilings": {
                "campaign_count": 1,
                "cycle_count": 1,
                "duration_seconds": 3600,
                "source_calls": 45,
                "scheduler_work": 40,
                "storage_bytes": 8_000_000,
                "failures": 10,
            },
            "campaign_selection_seed": "e45-seed",
            "report_directory_identity": "path-sha256:" + "e" * 64,
            "backup_preflight_references": {
                "preflight_status": "READY",
                "source_identity": "sha256:" + "a" * 64,
                "backup_sha256": "b" * 64,
                "required_migration": "032_campaign_ownership_schema.sql",
                "latest_migration": "034_discovery_persistence_reconciliation.sql",
            },
        }
        created = create_campaign(
            self.db,
            campaign_id="campaign-45",
            configuration_id="configuration-45",
            configuration=configuration,
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="isolated-45",
            proof_source_db_identity="source-45",
            policy_version="v2-9.7e.45",
        )
        self.configuration_hash = str(created["configuration_hash"])
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        create_campaign_run(
            self.connection,
            campaign_id="campaign-45",
            run_id="run-45",
            run_ordinal=1,
            now=NOW,
        )
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO printer_memory_factory_campaign_cycles(
                    cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                    created_at, updated_at
                ) VALUES ('cycle-45', 'campaign-45', 'run-45', 1, 'PLANNED', ?, ?)
                """,
                (NOW, NOW),
            )
            self.connection.execute(
                "UPDATE printer_memory_factory_campaigns SET campaign_state='RUNNING'"
            )
            self.connection.execute(
                "UPDATE printer_memory_factory_campaign_runs SET run_state='RUNNING'"
            )
        self.command = AbstractCampaignCommand(
            mode=CAMPAIGN_MODE,
            db_path=self.db,
            db_target_identity="isolated-45",
            campaign_id="campaign-45",
            configuration_id="configuration-45",
            configuration_hash=self.configuration_hash,
            policy_version="v2-9.7e.45",
            token_capacity=2,
            ceilings=self.ceilings,
            report_directory=Path(self.temp.name),
            report_directory_identity="path-sha256:" + "e" * 64,
            launch_git_provenance=_provenance(),
            run_id="run-45",
            report_id="report-45",
        )
        self.ports = (
            OwnerPort(SOURCE_GOVERNOR_OWNER, True),
            OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        try:
            self.temp.cleanup()
        except Exception:
            pass

    def _grad_native_fixtures(self, **overrides) -> CombinedDiscoveryFixtures:
        base = CombinedDiscoveryFixtures(
            cycle_id="cycle-45",
            cycle_cutoff=CUTOFF,
            campaign_selection_seed="e45-seed",
            provider_contract_versions={"direct": "V2-9.7E.45"},
            git_provenance_identity="git-45",
            evaluated_at=NOW,
            direct_observations=(
                FixtureOriginProof(
                    mint=MINT_A,
                    signature=MIG_SIG_A,
                    slot=500,
                    block_time=1_700_000_000,
                    bonding_curve="curveA" + "9" * 38,
                    origin_route="GRADUATION_NATIVE",
                ),
                FixtureOriginProof(
                    mint=MINT_B,
                    signature=MIG_SIG_B,
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

    def _execute(self, fixtures: CombinedDiscoveryFixtures):
        executor = CombinedPumpfunCampaignExecutor(fixtures)
        source, scheduler = self.ports
        return executor.execute(
            command=self.command,
            source_governor=source,
            central_scheduler=scheduler,
        )

    def _reopen(self) -> sqlite3.Connection:
        self.connection.close()
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        return self.connection


class GraduationNativeActivationTests(_Harness):
    def test_two_graduation_native_candidates_activate_atomically(self) -> None:
        result = self._execute(self._grad_native_fixtures())
        self.assertEqual(result.terminal_status, "COMPLETED")
        c = self._reopen()
        slots = c.execute(
            "SELECT mint_identity, pair_identity, token_state FROM "
            "printer_memory_factory_campaign_token_slots ORDER BY slot_ordinal"
        ).fetchall()
        self.assertEqual(len(slots), 2)
        activated = {row["mint_identity"] for row in slots}
        self.assertEqual(activated, {MINT_A, MINT_B})
        # The activated pair identity is the exact confirmed PumpSwap pool (the
        # tracking market identity was rebound to the post-graduation pool).
        pairs = {row["mint_identity"]: row["pair_identity"] for row in slots}
        self.assertEqual(pairs[MINT_A], POOL_A)
        self.assertEqual(pairs[MINT_B], POOL_B)
        # Tokens, pairs, tracking-queue rows and first-15m jobs exist.
        self.assertEqual(
            c.execute("SELECT COUNT(*) FROM printer_tokens").fetchone()[0], 2
        )
        self.assertEqual(
            c.execute("SELECT COUNT(*) FROM printer_pairs").fetchone()[0], 2
        )
        self.assertEqual(
            c.execute(
                "SELECT COUNT(*) FROM printer_tracking_queue WHERE queue_status='QUEUED'"
            ).fetchone()[0],
            2,
        )
        first_15m = c.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE job_kind = ?",
            ("TRACK_NORMAL_FIRST_15M",),
        ).fetchone()[0]
        self.assertEqual(first_15m, 2)

    def test_graduation_native_writes_no_create_origin_row(self) -> None:
        self._execute(self._grad_native_fixtures())
        c = self._reopen()
        rows = c.execute(
            "SELECT mint_identity, transaction_signature FROM "
            "printer_pumpfun_finalized_origin_registry"
        ).fetchall()
        # Route B never touches the create origin registry.
        self.assertEqual(rows, [])
        # The migration signature is never persisted into any create-signature field.
        sigs = c.execute(
            "SELECT transaction_signature FROM "
            "printer_pumpfun_finalized_origin_registry"
        ).fetchall()
        self.assertNotIn(MIG_SIG_A, [r[0] for r in sigs])
        self.assertNotIn(MIG_SIG_B, [r[0] for r in sigs])

    def test_origin_evidence_source_is_migration_lineage(self) -> None:
        self._execute(self._grad_native_fixtures())
        c = self._reopen()
        rows = c.execute(
            "SELECT evidence_detail_json FROM printer_discovery_origin_verifications"
        ).fetchall()
        self.assertTrue(rows)
        for row in rows:
            self.assertIn("migration_graduation_lineage", row[0])
            self.assertNotIn("direct_finalized_create", row[0])

    def test_one_valid_one_invalid_activates_neither(self) -> None:
        # MINT_B has an ambiguous graduation proof -> not eligible. With only one
        # eligible candidate, INITIAL mode fails closed with no slots (two-or-none).
        fixtures = self._grad_native_fixtures(
            pumpswap_proofs={
                MINT_A: FixturePumpSwapProof(mint=MINT_A, pool_address=POOL_A),
                MINT_B: FixturePumpSwapProof(
                    mint=MINT_B, pool_address=POOL_B, ambiguous=True
                ),
            }
        )
        result = self._execute(fixtures)
        self.assertEqual(result.terminal_status, "FAILED")
        self.assertEqual(
            result.first_terminal_cause, "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL"
        )
        c = self._reopen()
        self.assertEqual(
            c.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            c.execute("SELECT COUNT(*) FROM printer_tokens").fetchone()[0], 0
        )

    def test_create_route_still_writes_create_origin(self) -> None:
        # Route A (create-native) must remain unchanged: a PUMP_CREATE proof still
        # records a create origin row with its real create signature.
        from printer_v1.sources.pumpfun_direct import PUMP_PROGRAM_ID  # noqa: F401

        fixtures = self._grad_native_fixtures(
            direct_observations=(
                FixtureOriginProof(
                    mint=MINT_A,
                    signature="createSigA" + "0" * 34,
                    slot=500,
                    block_time=1_700_000_000,
                    bonding_curve="curveA" + "9" * 38,
                    origin_route="PUMP_CREATE",
                ),
                FixtureOriginProof(
                    mint=MINT_B,
                    signature=MIG_SIG_B,
                    slot=501,
                    block_time=1_700_000_100,
                    bonding_curve="curveB" + "9" * 38,
                    origin_route="GRADUATION_NATIVE",
                ),
            ),
        )
        self._execute(fixtures)
        c = self._reopen()
        create_rows = c.execute(
            "SELECT mint_identity, transaction_signature FROM "
            "printer_pumpfun_finalized_origin_registry"
        ).fetchall()
        # Only the create-native mint has a create origin row.
        self.assertEqual([r["mint_identity"] for r in create_rows], [MINT_A])
        self.assertEqual(create_rows[0]["transaction_signature"], "createSigA" + "0" * 34)

    def test_deterministic_selection_across_fresh_dbs(self) -> None:
        first = self._execute(self._grad_native_fixtures())
        self.assertEqual(first.terminal_status, "COMPLETED")
        c = self._reopen()
        selected_first = sorted(
            r[0]
            for r in c.execute(
                "SELECT mint_identity FROM "
                "printer_memory_factory_campaign_token_slots"
            ).fetchall()
        )
        # A second identical fixtures build on a fresh isolated DB selects the same
        # two mints (deterministic, zero-source selection).
        second_env = _Harness()
        second_env.setUp()
        try:
            second = second_env._execute(second_env._grad_native_fixtures())
            self.assertEqual(second.terminal_status, "COMPLETED")
            c2 = second_env._reopen()
            selected_second = sorted(
                r[0]
                for r in c2.execute(
                    "SELECT mint_identity FROM "
                    "printer_memory_factory_campaign_token_slots"
                ).fetchall()
            )
        finally:
            second_env.tearDown()
        self.assertEqual(selected_first, selected_second)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

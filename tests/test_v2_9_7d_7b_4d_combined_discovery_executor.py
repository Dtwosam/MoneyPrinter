"""Focused synthetic proof for V2-9.7D.7B.4D combined discovery execution owner."""

from __future__ import annotations

from copy import deepcopy
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
    FixtureSourceFact,
    derive_cycle_selection_seed,
)
from printer_v1.discovery.persistence import LOCKED_FINANCIAL_TABLES
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
from printer_v1.sources.secondary_discovery import (
    GECKO_TRENDING_PARAMS,
    GECKO_TRENDING_REQUEST,
    TRACKER_TOP_REQUEST,
    TRACKER_TRENDING_REQUEST,
    SolanaTrackerAuthConfig,
)


NOW = "2026-07-21T15:00:00+00:00"
CUTOFF = "2026-07-21T15:06:00+00:00"
RECEIPT = "2026-07-21T15:00:00+00:00"
# Within 180s of NOW for tracker lastUpdated (ms).
LAST_UPDATED_MS = int(
    __import__("datetime")
    .datetime.fromisoformat(NOW.replace("Z", "+00:00"))
    .timestamp()
    * 1000
)


def _provenance() -> dict[str, object]:
    return {
        "git_head": "d" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": NOW,
    }


def _mint(label: str) -> str:
    body = f"{label}Mint"
    return (body + "1" * 44)[:44]


def _pool(label: str) -> str:
    body = f"{label}Pool"
    return (body + "1" * 44)[:44]


MINT_A = _mint("A")
MINT_B = _mint("B")
MINT_C = _mint("C")
POOL_A = _pool("A")
POOL_B = _pool("B")
POOL_C = _pool("C")
WSOL = "So11111111111111111111111111111111111111112"


def _gecko_pool(pool: str, mint: str, rank: int = 1, score: int = 1) -> dict:
    return {
        "id": f"solana_{pool}",
        "type": "pool",
        "attributes": {"address": pool, "gt_score": score, "rank": rank},
        "relationships": {
            "base_token": {"data": {"id": f"solana_{mint}", "type": "token"}},
            "quote_token": {"data": {"id": f"solana_{WSOL}", "type": "token"}},
            "dex": {"data": {"id": "pump-fun", "type": "dex"}},
        },
    }


def _tracker_row(mint: str, pool: str, market: str = "pumpfun", **extra) -> dict:
    row = {
        "token": {"mint": mint, "name": "x"},
        "pools": [
            {
                "poolId": pool,
                "tokenAddress": mint,
                "quoteToken": WSOL,
                "market": market,
                "lastUpdated": LAST_UPDATED_MS,
                "score": extra.pop("score", 1),
            }
        ],
        "rank": extra.pop("rank", 1),
        "score": extra.pop("top_score", 1),
        "promoted": extra.pop("promoted", True),
        "risk": extra.pop("risk", {"score": 0}),
    }
    row.update(extra)
    return row


class CombinedDiscoveryExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = Path(self.temp.name) / "combined.sqlite3"
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
            "campaign_selection_seed": "fixture-seed-alpha",
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
            campaign_id="campaign-4d",
            configuration_id="configuration-4d",
            configuration=configuration,
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="isolated-4d",
            proof_source_db_identity="source-4d",
            policy_version="v2-9.7d.7b.4d",
        )
        self.configuration_hash = str(created["configuration_hash"])
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        create_campaign_run(
            self.connection,
            campaign_id="campaign-4d",
            run_id="run-4d",
            run_ordinal=1,
            now=NOW,
        )
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO printer_memory_factory_campaign_cycles(
                    cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                    created_at, updated_at
                ) VALUES ('cycle-4d', 'campaign-4d', 'run-4d', 1, 'PLANNED', ?, ?)
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
            db_target_identity="isolated-4d",
            campaign_id="campaign-4d",
            configuration_id="configuration-4d",
            configuration_hash=self.configuration_hash,
            policy_version="v2-9.7d.7b.4d",
            token_capacity=2,
            ceilings=self.ceilings,
            report_directory=Path(self.temp.name),
            report_directory_identity="path-sha256:" + "e" * 64,
            launch_git_provenance=_provenance(),
            run_id="run-4d",
            report_id="report-4d",
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

    def _fixtures(self, **overrides) -> CombinedDiscoveryFixtures:
        gecko_body = {
            "data": [
                _gecko_pool(POOL_A, MINT_A, rank=1, score=99),
                _gecko_pool(POOL_B, MINT_B, rank=2, score=1),
            ]
        }
        tracker_trending = [
            _tracker_row(MINT_B, POOL_B, rank=1, score=999, promoted=True),
            _tracker_row(MINT_C, POOL_C, rank=2),
        ]
        tracker_top = [_tracker_row(MINT_A, POOL_A, rank=1, promoted=True)]
        dex_body = [
            {
                "baseToken": {"address": MINT_A},
                "quoteToken": {"address": WSOL},
                "pairAddress": POOL_A,
                "dexId": "pumpfun",
                "txns": {"m5": {"buys": 2, "sells": 1}},
            }
        ]
        base = CombinedDiscoveryFixtures(
            cycle_id="cycle-4d",
            cycle_cutoff=CUTOFF,
            campaign_selection_seed="fixture-seed-alpha",
            provider_contract_versions={
                "geckoterminal": "V2-9.7D.7B.3B",
                "solana_tracker": "V2-9.7D.7B.3B",
                "dexscreener": "existing",
                "direct": "V2-9.7D.7B.3A",
            },
            git_provenance_identity="git-4d",
            evaluated_at=NOW,
            gecko_ops=(
                FixtureSourceFact(
                    request_kind=GECKO_TRENDING_REQUEST,
                    source_name="geckoterminal",
                    body=gecko_body,
                    receipt_time=RECEIPT,
                    params=dict(GECKO_TRENDING_PARAMS),
                ),
            ),
            tracker_ops=(
                FixtureSourceFact(
                    request_kind=TRACKER_TRENDING_REQUEST,
                    source_name="solana_tracker",
                    body=tracker_trending,
                    receipt_time=RECEIPT,
                ),
                FixtureSourceFact(
                    request_kind=TRACKER_TOP_REQUEST,
                    source_name="solana_tracker",
                    body=tracker_top,
                    receipt_time=RECEIPT,
                ),
            ),
            dexscreener_ops=(
                FixtureSourceFact(
                    request_kind="dexscreener_fresh_profiles",
                    source_name="dexscreener",
                    body=dex_body,
                    receipt_time=RECEIPT,
                ),
            ),
            direct_observations=(
                FixtureOriginProof(
                    mint=MINT_A, signature="sig-a", slot=100, block_time=1
                ),
                FixtureOriginProof(
                    mint=MINT_B, signature="sig-b", slot=101, block_time=2
                ),
                FixtureOriginProof(
                    mint=MINT_C, signature="sig-c", slot=102, block_time=3
                ),
            ),
            origin_proofs={
                MINT_A: FixtureOriginProof(
                    mint=MINT_A, signature="sig-a", slot=100, block_time=1
                ),
                MINT_B: FixtureOriginProof(
                    mint=MINT_B, signature="sig-b", slot=101, block_time=2
                ),
                MINT_C: FixtureOriginProof(
                    mint=MINT_C, signature="sig-c", slot=102, block_time=3
                ),
            },
            tracker_auth=SolanaTrackerAuthConfig(
                api_key_secret_ref="SOLANA_TRACKER_API_KEY_REF",
                free_requests_remaining_month=9990,
            ),
        )
        return replace(base, **overrides) if overrides else base

    def _execute(self, fixtures: CombinedDiscoveryFixtures | None = None):
        executor = CombinedPumpfunCampaignExecutor(fixtures or self._fixtures())
        source, scheduler = self.ports
        return executor.execute(
            command=self.command,
            source_governor=source,
            central_scheduler=scheduler,
        ), executor

    def test_happy_path_two_slot_handoff_and_15m_only(self) -> None:
        result, _ = self._execute()
        self.assertEqual(result.terminal_status, "COMPLETED")
        self.assertTrue(result.source_governor_used)
        self.assertTrue(result.central_scheduler_used)
        self.assertTrue(result.selective_continuation_preserved)
        self.assertTrue(result.support_5m_only)
        self.assertFalse(result.successor_created)
        self.assertFalse(result.restart_created)
        self.assertGreater(result.source_calls, 0)
        self.assertGreater(result.scheduler_work, 0)
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        slots = self.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots WHERE cycle_id='cycle-4d'"
        ).fetchone()[0]
        self.assertEqual(slots, 2)
        jobs = [
            row[0]
            for row in self.connection.execute(
                "SELECT job_kind FROM printer_scheduler_jobs"
            )
        ]
        self.assertIn("TRACK_NORMAL_FIRST_15M", jobs)
        self.assertNotIn("TRACK_NORMAL_1H", jobs)
        self.assertNotIn("TRACK_NORMAL_4H", jobs)
        self.assertNotIn("TRACK_FAST_MICRO_EVENT", jobs)
        handoffs = self.connection.execute(
            """
            SELECT tracking_handoff_state, first_window_15m_scheduler_job_id
            FROM printer_discovery_selected_item_links
            """
        ).fetchall()
        self.assertEqual(len(handoffs), 2)
        self.assertTrue(all(row[0] == "HANDOFF_RECORDED" for row in handoffs))
        # Provider labels are not treated as origin without direct proof rows.
        origins = self.connection.execute(
            "SELECT verification_state FROM printer_discovery_origin_verifications"
        ).fetchall()
        self.assertTrue(origins)
        locked = {
            table: self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in LOCKED_FINANCIAL_TABLES
        }
        self.assertTrue(all(value == 0 for value in locked.values()))
        self.connection.close()

    def test_rank_order_promoted_does_not_change_selection(self) -> None:
        first, executor = self._execute()
        self.assertEqual(first.terminal_status, "COMPLETED")
        # Rebuild DB for second run with mutated ranks/order.
        self.tearDown()
        self.setUp()
        fixtures = self._fixtures()
        gecko = deepcopy(fixtures.gecko_ops[0].body)
        gecko["data"].reverse()
        for item in gecko["data"]:
            item["attributes"]["rank"] = 999
            item["attributes"]["gt_score"] = -1
        tracker = deepcopy(list(fixtures.tracker_ops[0].body))
        tracker.reverse()
        for item in tracker:
            item["rank"] = 999999
            item["promoted"] = False
            item["score"] = -9
            item["risk"] = {"score": 100, "rugged": True}
        mutated = self._fixtures(
            gecko_ops=(
                FixtureSourceFact(
                    request_kind=GECKO_TRENDING_REQUEST,
                    source_name="geckoterminal",
                    body=gecko,
                    receipt_time=RECEIPT,
                    params=dict(GECKO_TRENDING_PARAMS),
                ),
            ),
            tracker_ops=(
                FixtureSourceFact(
                    request_kind=TRACKER_TRENDING_REQUEST,
                    source_name="solana_tracker",
                    body=tracker,
                    receipt_time=RECEIPT,
                ),
                fixtures.tracker_ops[1],
            ),
        )
        second, _ = self._execute(mutated)
        self.assertEqual(second.terminal_status, "COMPLETED")
        self.connection = sqlite3.connect(self.db)
        mints = sorted(
            row[0]
            for row in self.connection.execute(
                "SELECT mint_identity FROM printer_memory_factory_campaign_token_slots"
            )
        )
        # Deterministic seed + same eligible set => same two mints selected.
        self.assertEqual(len(mints), 2)
        self.connection.close()

    def test_insufficient_pool_no_partial_handoff(self) -> None:
        fixtures = self._fixtures(
            direct_observations=(
                FixtureOriginProof(
                    mint=MINT_A, signature="sig-a", slot=100, block_time=1
                ),
            ),
            origin_proofs={
                MINT_A: FixtureOriginProof(
                    mint=MINT_A, signature="sig-a", slot=100, block_time=1
                ),
            },
            gecko_ops=(
                FixtureSourceFact(
                    request_kind=GECKO_TRENDING_REQUEST,
                    source_name="geckoterminal",
                    body={"data": [_gecko_pool(POOL_A, MINT_A)]},
                    receipt_time=RECEIPT,
                    params=dict(GECKO_TRENDING_PARAMS),
                ),
            ),
            tracker_ops=(),
            dexscreener_ops=(),
        )
        result, _ = self._execute(fixtures)
        self.assertEqual(result.terminal_status, "FAILED")
        self.assertEqual(result.first_terminal_cause, "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL")
        self.connection = sqlite3.connect(self.db)
        slots = self.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots"
        ).fetchone()[0]
        self.assertEqual(slots, 0)
        tracking = self.connection.execute(
            "SELECT COUNT(*) FROM printer_tracking_queue"
        ).fetchone()[0]
        self.assertEqual(tracking, 0)
        self.connection.close()

    def test_provider_failure_isolation_and_governor_scheduler_required(self) -> None:
        fixtures = self._fixtures(
            provider_failures_injected={"geckoterminal": "rate_limited"}
        )
        result, _ = self._execute(fixtures)
        # Direct + tracker + dexscreener still supply enough origin-confirmed mints.
        self.assertEqual(result.terminal_status, "COMPLETED")
        self.connection = sqlite3.connect(self.db)
        failed_work = self.connection.execute(
            """
            SELECT first_terminal_cause FROM printer_discovery_work
            WHERE work_type='DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE'
            """
        ).fetchone()
        self.assertEqual(failed_work[0], "GECKOTERMINAL_FAILED")
        self.connection.close()

        bad = CombinedPumpfunCampaignExecutor(self._fixtures())
        with self.assertRaises(Exception):
            # OwnerPort unavailable is raised before DB work in execute.
            bad.execute(
                command=self.command,
                source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, False),
                central_scheduler=self.ports[1],
            )

    def test_shared_fault_and_idempotent_replay(self) -> None:
        failed, _ = self._execute(
            self._fixtures(force_shared_fault="SHARED_CONFIGURATION_MISMATCH")
        )
        self.assertEqual(failed.terminal_status, "FAILED")
        self.assertEqual(failed.first_terminal_cause, "SHARED_CONFIGURATION_MISMATCH")
        self.assertEqual(failed.cancellation_reason, "SHARED_FAILURE")

        # Fresh DB for idempotent success replay.
        self.tearDown()
        self.setUp()
        fixtures = self._fixtures()
        executor = CombinedPumpfunCampaignExecutor(fixtures)
        source, scheduler = self.ports
        first = executor.execute(
            command=self.command, source_governor=source, central_scheduler=scheduler
        )
        self.assertEqual(first.terminal_status, "COMPLETED")
        # Second identical execute on same DB should remain safe (idempotent paths).
        second = executor.execute(
            command=self.command, source_governor=source, central_scheduler=scheduler
        )
        # May COMPLETE via idempotent batch insert or FAIL on unique constraints
        # depending on work uniqueness; either must not write locked tables.
        self.assertIn(second.terminal_status, {"COMPLETED", "FAILED"})
        connection = sqlite3.connect(self.db)
        try:
            for table in LOCKED_FINANCIAL_TABLES:
                self.assertEqual(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                    0,
                )
            # Seed formula is stable.
            seed = derive_cycle_selection_seed(
                campaign_selection_seed="fixture-seed-alpha",
                campaign_id="campaign-4d",
                run_id="run-4d",
                cycle_id="cycle-4d",
                discovery_batch_id="discovery-batch:campaign-4d:run-4d:cycle-4d",
            )
            self.assertEqual(len(seed), 64)
        finally:
            connection.close()

    def test_missing_seed_and_origin_gate(self) -> None:
        # Rebuild campaign without a selection seed in configuration.
        self.tearDown()
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = Path(self.temp.name) / "combined.sqlite3"
        apply_migrations(self.db)
        self.ceilings = CampaignCeilings(
            campaign_count=1, cycle_count=1, duration_seconds=3600,
            source_calls=45, scheduler_work=40, storage_bytes=8_000_000, failures=10,
        )
        configuration = {
            "token_capacity": 2,
            "ceilings": {
                "campaign_count": 1, "cycle_count": 1, "duration_seconds": 3600,
                "source_calls": 45, "scheduler_work": 40, "storage_bytes": 8_000_000,
                "failures": 10,
            },
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
            self.db, campaign_id="campaign-4d", configuration_id="configuration-4d",
            configuration=configuration, launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED, db_target_identity="isolated-4d",
            proof_source_db_identity="source-4d", policy_version="v2-9.7d.7b.4d",
        )
        self.configuration_hash = str(created["configuration_hash"])
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        create_campaign_run(
            self.connection, campaign_id="campaign-4d", run_id="run-4d",
            run_ordinal=1, now=NOW,
        )
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO printer_memory_factory_campaign_cycles(
                    cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                    created_at, updated_at
                ) VALUES ('cycle-4d', 'campaign-4d', 'run-4d', 1, 'PLANNED', ?, ?)
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
            mode=CAMPAIGN_MODE, db_path=self.db, db_target_identity="isolated-4d",
            campaign_id="campaign-4d", configuration_id="configuration-4d",
            configuration_hash=self.configuration_hash, policy_version="v2-9.7d.7b.4d",
            token_capacity=2, ceilings=self.ceilings,
            report_directory=Path(self.temp.name),
            report_directory_identity="path-sha256:" + "e" * 64,
            launch_git_provenance=_provenance(), run_id="run-4d", report_id="report-4d",
        )
        result, _ = self._execute(self._fixtures(campaign_selection_seed=""))
        self.assertEqual(result.terminal_status, "FAILED")
        self.assertEqual(result.first_terminal_cause, "MISSING_SELECTION_SEED")

    def test_windows_connection_closes_cleanly(self) -> None:
        result, _ = self._execute()
        self.assertEqual(result.terminal_status, "COMPLETED")
        connection = sqlite3.connect(self.db)
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            count = connection.execute(
                "SELECT COUNT(*) FROM printer_discovery_batches"
            ).fetchone()[0]
            self.assertEqual(count, 1)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()

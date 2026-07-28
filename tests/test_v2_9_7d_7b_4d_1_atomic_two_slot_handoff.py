"""Focused proofs for V2-9.7D.7B.4D.1 atomic initial two-slot handoff repair."""

from __future__ import annotations

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
    FixtureSourceFact,
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
from printer_v1.operator_cli.campaign_ownership import (
    create_campaign_run,
    create_cycle_with_two_slots,
)
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


NOW = "2026-07-21T16:00:00+00:00"
CUTOFF = "2026-07-21T16:06:00+00:00"
RECEIPT = "2026-07-21T16:00:00+00:00"
LAST_UPDATED_MS = int(
    __import__("datetime")
    .datetime.fromisoformat(NOW.replace("Z", "+00:00"))
    .timestamp()
    * 1000
)
WSOL = "So11111111111111111111111111111111111111112"


def _provenance() -> dict[str, object]:
    return {
        "git_head": "e" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": NOW,
    }


def _mint(label: str) -> str:
    return (f"{label}Mint" + "1" * 44)[:44]


def _pool(label: str) -> str:
    return (f"{label}Pool" + "1" * 44)[:44]


MINT_A = _mint("A")
MINT_B = _mint("B")
MINT_C = _mint("C")
POOL_A = _pool("A")
POOL_B = _pool("B")
POOL_C = _pool("C")


def _gecko_pool(pool: str, mint: str) -> dict:
    return {
        "id": f"solana_{pool}",
        "type": "pool",
        "attributes": {"address": pool, "gt_score": 1, "rank": 1},
        "relationships": {
            "base_token": {"data": {"id": f"solana_{mint}", "type": "token"}},
            "quote_token": {"data": {"id": f"solana_{WSOL}", "type": "token"}},
            "dex": {"data": {"id": "pump-fun", "type": "dex"}},
        },
    }


def _tracker_row(mint: str, pool: str) -> dict:
    return {
        "token": {"mint": mint},
        "pools": [
            {
                "poolId": pool,
                "tokenAddress": mint,
                "quoteToken": WSOL,
                "market": "pumpfun",
                "lastUpdated": LAST_UPDATED_MS,
            }
        ],
    }


class AtomicTwoSlotHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = Path(self.temp.name) / "atomic.sqlite3"
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
            "campaign_selection_seed": "atomic-seed",
            "report_directory_identity": "path-sha256:" + "f" * 64,
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
            campaign_id="campaign-atomic",
            configuration_id="configuration-atomic",
            configuration=configuration,
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="isolated-atomic",
            proof_source_db_identity="source-atomic",
            policy_version="v2-9.7d.7b.4d.1",
        )
        self.configuration_hash = str(created["configuration_hash"])
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        create_campaign_run(
            self.connection,
            campaign_id="campaign-atomic",
            run_id="run-atomic",
            run_ordinal=1,
            now=NOW,
        )
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO printer_memory_factory_campaign_cycles(
                    cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                    created_at, updated_at
                ) VALUES ('cycle-atomic', 'campaign-atomic', 'run-atomic', 1, 'PLANNED', ?, ?)
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
            db_target_identity="isolated-atomic",
            campaign_id="campaign-atomic",
            configuration_id="configuration-atomic",
            configuration_hash=self.configuration_hash,
            policy_version="v2-9.7d.7b.4d.1",
            token_capacity=2,
            ceilings=self.ceilings,
            report_directory=Path(self.temp.name),
            report_directory_identity="path-sha256:" + "f" * 64,
            launch_git_provenance=_provenance(),
            run_id="run-atomic",
            report_id="report-atomic",
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
        base = CombinedDiscoveryFixtures(
            cycle_id="cycle-atomic",
            cycle_cutoff=CUTOFF,
            campaign_selection_seed="atomic-seed",
            provider_contract_versions={
                "geckoterminal": "V2-9.7D.7B.3B",
                "solana_tracker": "V2-9.7D.7B.3B",
                "dexscreener": "existing",
                "direct": "V2-9.7D.7B.3A",
            },
            git_provenance_identity="git-atomic",
            evaluated_at=NOW,
            gecko_ops=(
                FixtureSourceFact(
                    request_kind=GECKO_TRENDING_REQUEST,
                    source_name="geckoterminal",
                    body={
                        "data": [
                            _gecko_pool(POOL_A, MINT_A),
                            _gecko_pool(POOL_B, MINT_B),
                        ]
                    },
                    receipt_time=RECEIPT,
                    params=dict(GECKO_TRENDING_PARAMS),
                ),
            ),
            tracker_ops=(
                FixtureSourceFact(
                    request_kind=TRACKER_TRENDING_REQUEST,
                    source_name="solana_tracker",
                    body=[
                        _tracker_row(MINT_B, POOL_B),
                        _tracker_row(MINT_C, POOL_C),
                    ],
                    receipt_time=RECEIPT,
                ),
                FixtureSourceFact(
                    request_kind=TRACKER_TOP_REQUEST,
                    source_name="solana_tracker",
                    body=[_tracker_row(MINT_A, POOL_A)],
                    receipt_time=RECEIPT,
                ),
            ),
            dexscreener_ops=(
                FixtureSourceFact(
                    request_kind="dexscreener_fresh_profiles",
                    source_name="dexscreener",
                    body=[
                        {
                            "baseToken": {"address": MINT_A},
                            "quoteToken": {"address": WSOL},
                            "pairAddress": POOL_A,
                            "dexId": "pumpfun",
                            "txns": {"m5": {"buys": 2, "sells": 1}},
                        }
                    ],
                    receipt_time=RECEIPT,
                ),
            ),
            direct_observations=(
                FixtureOriginProof(mint=MINT_A, signature="sig-a", slot=1, block_time=1),
                FixtureOriginProof(mint=MINT_B, signature="sig-b", slot=2, block_time=2),
                FixtureOriginProof(mint=MINT_C, signature="sig-c", slot=3, block_time=3),
            ),
            origin_proofs={
                MINT_A: FixtureOriginProof(
                    mint=MINT_A, signature="sig-a", slot=1, block_time=1
                ),
                MINT_B: FixtureOriginProof(
                    mint=MINT_B, signature="sig-b", slot=2, block_time=2
                ),
                MINT_C: FixtureOriginProof(
                    mint=MINT_C, signature="sig-c", slot=3, block_time=3
                ),
            },
            tracker_auth=SolanaTrackerAuthConfig(
                api_key_secret_ref="SOLANA_TRACKER_API_KEY_REF",
                free_requests_remaining_month=9990,
            ),
            # V2-9.7E.41 graduation-only law: graduate MINT_A/B/C to a confirmed
            # PumpSwap pool so the atomic two-slot handoff plumbing operates on
            # lawful graduated candidates.
            pumpswap_proofs={
                MINT_A: FixturePumpSwapProof(mint=MINT_A, pool_address=POOL_A),
                MINT_B: FixturePumpSwapProof(mint=MINT_B, pool_address=POOL_B),
                MINT_C: FixturePumpSwapProof(mint=MINT_C, pool_address=POOL_C),
            },
        )
        from dataclasses import replace

        return replace(base, **overrides) if overrides else base

    def _execute(self, fixtures: CombinedDiscoveryFixtures | None = None):
        executor = CombinedPumpfunCampaignExecutor(fixtures or self._fixtures())
        source, scheduler = self.ports
        return executor.execute(
            command=self.command,
            source_governor=source,
            central_scheduler=scheduler,
        )

    def _reopen(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _activation_counts(self, connection: sqlite3.Connection) -> dict[str, int]:
        return {
            "slots": int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots "
                    "WHERE cycle_id='cycle-atomic'"
                ).fetchone()[0]
            ),
            "tracking": int(
                connection.execute("SELECT COUNT(*) FROM printer_tracking_queue").fetchone()[0]
            ),
            "window15m": int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_scheduler_jobs "
                    "WHERE job_kind='TRACK_NORMAL_FIRST_15M'"
                ).fetchone()[0]
            ),
            "selected_links": int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_discovery_selected_item_links"
                ).fetchone()[0]
            ),
            "selection_batches": int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_selection_batches"
                ).fetchone()[0]
            ),
        }

    def _seed_tracking(
        self,
        mint: str,
        pool: str,
        status: str,
        *,
        next_check_at: str = NOW,
        last_checked_at: str | None = None,
    ) -> int:
        with self.connection:
            token = self.connection.execute(
                "SELECT id FROM printer_tokens WHERE token_mint=?", (mint,)
            ).fetchone()
            if token is None:
                token_id = int(self.connection.execute(
                    "INSERT INTO printer_tokens(token_mint,token_status) "
                    "VALUES (?, 'TRACK_NORMAL')", (mint,)
                ).lastrowid)
            else:
                token_id = int(token[0])
            pair = self.connection.execute(
                "SELECT id FROM printer_pairs WHERE pair_address=?", (pool,)
            ).fetchone()
            if pair is None:
                pair_id = int(self.connection.execute(
                    "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) "
                    "VALUES (?,?,?)", (token_id, pool, mint)
                ).lastrowid)
            else:
                pair_id = int(pair[0])
            return int(self.connection.execute(
                """
                INSERT INTO printer_tracking_queue(
                    token_id,pair_id,tracking_lane,tracking_action,priority_reason,
                    next_check_at,last_checked_at,queue_status,source_status,data_quality_label
                ) VALUES (?,?,'TRACK_NORMAL','PROMOTE_TO_TRACK_NORMAL','fixture',
                          ?,?,?,'COMPLETE','CLEAN_DATA')
                """,
                (token_id, pair_id, next_check_at, last_checked_at, status),
            ).lastrowid)

    def _assert_owned_candidate_uses_reserve(self, status: str) -> None:
        seeded_id = self._seed_tracking(MINT_A, POOL_A, status)
        result = self._execute()
        self.assertEqual(result.terminal_status, "COMPLETED")
        connection = self._reopen()
        try:
            selected_mints = {
                row["mint_identity"]
                for row in connection.execute(
                    "SELECT mint_identity FROM printer_memory_factory_campaign_token_slots "
                    "WHERE cycle_id='cycle-atomic'"
                )
            }
            self.assertEqual(selected_mints, {MINT_B, MINT_C})
            seeded = connection.execute(
                "SELECT queue_status FROM printer_tracking_queue WHERE id=?",
                (seeded_id,),
            ).fetchone()
            self.assertEqual(seeded["queue_status"], status)
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_tracking_queue"
                ).fetchone()[0],
                3,
            )
        finally:
            connection.close()

    def test_successful_initial_activation_commits_both(self) -> None:
        result = self._execute()
        self.assertEqual(result.terminal_status, "COMPLETED")
        connection = self._reopen()
        try:
            counts = self._activation_counts(connection)
            self.assertEqual(counts["slots"], 2)
            self.assertEqual(counts["tracking"], 2)
            self.assertEqual(counts["window15m"], 2)
            self.assertEqual(counts["selected_links"], 2)
            jobs = {
                row[0]
                for row in connection.execute("SELECT job_kind FROM printer_scheduler_jobs")
            }
            self.assertIn("TRACK_NORMAL_FIRST_15M", jobs)
            self.assertNotIn("TRACK_NORMAL_1H", jobs)
            self.assertNotIn("TRACK_NORMAL_4H", jobs)
            self.assertNotIn("TRACK_FAST_MICRO_EVENT", jobs)
            for table in LOCKED_FINANCIAL_TABLES:
                self.assertEqual(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0
                )
        finally:
            connection.close()

    def test_cooldown_candidate_is_excluded_and_valid_reserve_activates(self) -> None:
        self._assert_owned_candidate_uses_reserve("COOLDOWN")

    def test_queued_candidate_is_excluded_and_valid_reserve_activates(self) -> None:
        self._assert_owned_candidate_uses_reserve("QUEUED")

    def test_active_candidate_is_excluded_and_valid_reserve_activates(self) -> None:
        self._assert_owned_candidate_uses_reserve("ACTIVE")

    def test_paused_candidate_is_excluded_and_valid_reserve_activates(self) -> None:
        self._assert_owned_candidate_uses_reserve("PAUSED")

    def test_cooldown_shortfall_is_not_mislabeled_active_duplication(self) -> None:
        self._seed_tracking(MINT_A, POOL_A, "COOLDOWN")
        self._seed_tracking(MINT_B, POOL_B, "COOLDOWN")
        result = self._execute()
        self.assertEqual(result.terminal_status, "FAILED")
        self.assertEqual(result.first_terminal_cause, "COOLDOWN_REOPEN_REQUIRED")
        connection = self._reopen()
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_tracking_queue"
                ).fetchone()[0],
                2,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_scheduler_jobs "
                    "WHERE job_kind='TRACK_NORMAL_FIRST_15M'"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()

    def test_expired_cooldown_requalifies_into_exact_lane_once(self) -> None:
        from datetime import datetime, timedelta

        instant = datetime.fromisoformat(NOW)
        old_queue_id = self._seed_tracking(
            MINT_A,
            POOL_A,
            "COOLDOWN",
            next_check_at=(instant - timedelta(hours=2)).isoformat(),
            last_checked_at=(instant - timedelta(hours=1)).isoformat(),
        )
        fixtures = self._fixtures(
            holder_evidence_eligibility={
                MINT_A.lower(): {
                    "eligible": True,
                    "tracking_requalification_required": True,
                    "source_name": "fixture-current-holder",
                },
                MINT_B.lower(): {"eligible": True},
                MINT_C.lower(): {"eligible": False, "reason": "fixture-reserve"},
            }
        )
        result = self._execute(fixtures)
        self.assertEqual(result.terminal_status, "COMPLETED")
        connection = self._reopen()
        try:
            queues = connection.execute(
                "SELECT id,queue_status,tracking_action FROM printer_tracking_queue "
                "WHERE token_id=(SELECT id FROM printer_tokens WHERE token_mint=?) "
                "ORDER BY id",
                (MINT_A,),
            ).fetchall()
            self.assertEqual(
                [(row["queue_status"], row["tracking_action"]) for row in queues],
                [
                    ("COOLDOWN", "PROMOTE_TO_TRACK_NORMAL"),
                    ("QUEUED", "REOPEN_REVIVED_TOKEN"),
                ],
            )
            self.assertEqual(queues[0]["id"], old_queue_id)
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_token_lifecycle_events "
                    "WHERE lifecycle_event='REOPEN_REVIVED_TOKEN'"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_scheduler_jobs "
                    "WHERE job_kind='TRACK_NORMAL_FIRST_15M'"
                ).fetchone()[0],
                2,
            )
        finally:
            connection.close()

    def test_failure_before_first_leaves_both_vacant(self) -> None:
        result = self._execute(self._fixtures(force_handoff_failure="BEFORE_FIRST"))
        self.assertEqual(result.terminal_status, "FAILED")
        self.assertEqual(result.first_terminal_cause, "HANDOFF_BEFORE_FIRST")
        connection = self._reopen()
        try:
            counts = self._activation_counts(connection)
            self.assertEqual(counts["slots"], 0)
            self.assertEqual(counts["tracking"], 0)
            self.assertEqual(counts["window15m"], 0)
            self.assertEqual(counts["selected_links"], 0)
            self.assertEqual(counts["selection_batches"], 0)
            batch = connection.execute(
                "SELECT batch_state, first_terminal_cause FROM printer_discovery_batches"
            ).fetchone()
            self.assertEqual(batch["batch_state"], "TERMINAL_FAILED")
            self.assertEqual(batch["first_terminal_cause"], "HANDOFF_BEFORE_FIRST")
            # Discovery facts remain (not full-cycle wipe).
            self.assertGreater(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_discovery_provider_observations"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()

    def test_failure_during_second_rolls_back_first(self) -> None:
        result = self._execute(self._fixtures(force_handoff_failure="DURING_SECOND"))
        self.assertEqual(result.terminal_status, "FAILED")
        self.assertEqual(result.first_terminal_cause, "HANDOFF_DURING_SECOND")
        connection = self._reopen()
        try:
            counts = self._activation_counts(connection)
            self.assertEqual(counts["slots"], 0)
            self.assertEqual(counts["tracking"], 0)
            self.assertEqual(counts["window15m"], 0)
            self.assertEqual(counts["selected_links"], 0)
            self.assertEqual(counts["selection_batches"], 0)
        finally:
            connection.close()

    def test_second_scheduler_job_failure_rolls_back_both(self) -> None:
        result = self._execute(self._fixtures(force_handoff_failure="SECOND_SCHEDULER_JOB"))
        self.assertEqual(result.terminal_status, "FAILED")
        self.assertEqual(result.first_terminal_cause, "FIRST_15M_JOB_FAILED")
        connection = self._reopen()
        try:
            counts = self._activation_counts(connection)
            self.assertEqual(counts["slots"], 0)
            self.assertEqual(counts["tracking"], 0)
            self.assertEqual(counts["window15m"], 0)
            self.assertEqual(counts["selected_links"], 0)
        finally:
            connection.close()

    def test_duplicate_active_causes_full_rollback(self) -> None:
        result = self._execute(self._fixtures(force_handoff_failure="DUPLICATE_ACTIVE"))
        self.assertEqual(result.terminal_status, "FAILED")
        self.assertEqual(result.first_terminal_cause, "DUPLICATE_ACTIVE_TRACKING")
        connection = self._reopen()
        try:
            counts = self._activation_counts(connection)
            self.assertEqual(counts["slots"], 0)
            self.assertEqual(counts["tracking"], 0)
            self.assertEqual(counts["window15m"], 0)
        finally:
            connection.close()

    def test_conflicting_slot_causes_full_rollback(self) -> None:
        result = self._execute(self._fixtures(force_handoff_failure="CONFLICTING_SLOT"))
        self.assertEqual(result.terminal_status, "FAILED")
        self.assertEqual(result.first_terminal_cause, "CONFLICTING_SLOT")
        connection = self._reopen()
        try:
            counts = self._activation_counts(connection)
            self.assertEqual(counts["slots"], 0)
            self.assertEqual(counts["tracking"], 0)
            self.assertEqual(counts["window15m"], 0)
        finally:
            connection.close()

    def test_replacement_failure_preserves_healthy_slot(self) -> None:
        # Seed a cycle with one healthy slot and one vacancy target.
        with self.connection:
            self.connection.execute("DELETE FROM printer_memory_factory_campaign_cycles")
        create_campaign_run(
            self.connection,
            campaign_id="campaign-atomic",
            run_id="run-replace",
            run_ordinal=2,
            now=NOW,
        )
        with self.connection:
            self.connection.execute(
                "INSERT INTO printer_tokens(id, token_mint) VALUES (10, ?), (11, ?)",
                (MINT_A, MINT_B),
            )
            self.connection.execute(
                """
                INSERT INTO printer_pairs(id, token_id, pair_address) VALUES
                    (10, 10, ?), (11, 11, ?)
                """,
                (POOL_A, POOL_B),
            )
        create_cycle_with_two_slots(
            self.connection,
            campaign_id="campaign-atomic",
            run_id="run-replace",
            cycle_id="cycle-replace",
            cycle_ordinal=1,
            slots=(
                {
                    "token_slot_id": "healthy-slot",
                    "slot_ordinal": 1,
                    "token_identity": f"solana-mainnet:{MINT_A}",
                    "token_row_id": 10,
                    "mint_identity": MINT_A,
                    "pair_identity": POOL_A,
                    "pair_row_id": 10,
                    "lifecycle_identity": "PUMP_LIFECYCLE_UNKNOWN",
                },
                {
                    "token_slot_id": "vacant-slot",
                    "slot_ordinal": 2,
                    "token_identity": f"solana-mainnet:{MINT_B}",
                    "token_row_id": 11,
                    "mint_identity": MINT_B,
                    "pair_identity": POOL_B,
                    "pair_row_id": 11,
                    "lifecycle_identity": "PUMP_LIFECYCLE_UNKNOWN",
                },
            ),
            now=NOW,
        )
        with self.connection:
            self.connection.execute(
                """
                UPDATE printer_memory_factory_campaign_token_slots
                SET token_state='FAILED', first_terminal_cause='prior', terminal_at=?
                WHERE token_slot_id='vacant-slot'
                """,
                (NOW,),
            )
        command = AbstractCampaignCommand(
            mode=CAMPAIGN_MODE,
            db_path=self.db,
            db_target_identity="isolated-atomic",
            campaign_id="campaign-atomic",
            configuration_id="configuration-atomic",
            configuration_hash=self.configuration_hash,
            policy_version="v2-9.7d.7b.4d.1",
            token_capacity=2,
            ceilings=self.ceilings,
            report_directory=Path(self.temp.name),
            report_directory_identity="path-sha256:" + "f" * 64,
            launch_git_provenance=_provenance(),
            run_id="run-replace",
            report_id="report-replace",
        )
        fixtures = self._fixtures(
            cycle_id="cycle-replace",
            mode="REPLACEMENT",
            vacant_slot_ordinals=(2,),
            healthy_slot_ids=("healthy-slot",),
            force_handoff_failure="DUPLICATE_ACTIVE",
        )
        # Pre-seed active tracking for MINT_B so replacement handoff fails.
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO printer_tracking_queue(
                    token_id, pair_id, tracking_lane, tracking_action, priority_reason,
                    next_check_at, queue_status, source_status, data_quality_label
                ) VALUES (11, 11, 'TRACK_NORMAL', 'PROMOTE_TO_TRACK_NORMAL', 'seed',
                          ?, 'ACTIVE', 'COMPLETE', 'CLEAN_DATA')
                """,
                (NOW,),
            )
        executor = CombinedPumpfunCampaignExecutor(fixtures)
        source, scheduler = self.ports
        result = executor.execute(
            command=command, source_governor=source, central_scheduler=scheduler
        )
        self.assertEqual(result.terminal_status, "FAILED")
        connection = self._reopen()
        try:
            healthy = connection.execute(
                """
                SELECT mint_identity, token_state FROM printer_memory_factory_campaign_token_slots
                WHERE token_slot_id='healthy-slot'
                """
            ).fetchone()
            self.assertEqual(healthy["mint_identity"], MINT_A)
            self.assertEqual(healthy["token_state"], "SELECTED")
            vacant = connection.execute(
                """
                SELECT mint_identity, token_state FROM printer_memory_factory_campaign_token_slots
                WHERE token_slot_id='vacant-slot'
                """
            ).fetchone()
            self.assertEqual(vacant["mint_identity"], MINT_B)
            self.assertEqual(vacant["token_state"], "FAILED")
        finally:
            connection.close()

    def test_windows_connection_closes_cleanly(self) -> None:
        result = self._execute()
        self.assertEqual(result.terminal_status, "COMPLETED")
        connection = self._reopen()
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM printer_discovery_batches").fetchone()[0],
                1,
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()

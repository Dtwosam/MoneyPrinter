"""Focused V2-9.7D.7B.4C discovery persistence reconciliation tests."""

from __future__ import annotations

from pathlib import Path
import os
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.db import migrate as migration_runner
from printer_v1.discovery.persistence import (
    DiscoveryPersistenceError,
    FORBIDDEN_FACTUAL_FIELDS,
    LOCKED_FINANCIAL_TABLES,
    count_locked_financial_rows,
    get_discovery_batch,
    insert_discovery_batch,
    insert_discovery_work,
    insert_merged_candidate,
    insert_origin_verification,
    insert_provider_observation,
    insert_provider_report_link,
    insert_pumpswap_confirmation,
    link_candidate_contribution,
    link_discovery_work_source,
    link_selected_item,
    link_selection_batch,
    list_provider_observations,
)
from printer_v1.operator_cli.campaign_ownership import (
    create_campaign_run,
    create_cycle_with_two_slots,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)


NOW = "2026-07-21T12:00:00+00:00"
CUTOFF = "2026-07-21T12:30:00+00:00"
MIGRATION_034 = "034_discovery_persistence_reconciliation.sql"
SEED_HASH = "a" * 64
RAW_HASH = "b" * 64


def _apply_through(db_path: Path, maximum_prefix: int) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS printer_schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        applied = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations"
            )
        }
        for path in sorted(migration_runner.MIGRATIONS_DIR.glob("*.sql")):
            if int(path.name.split("_", 1)[0]) > maximum_prefix:
                continue
            if path.name not in applied:
                connection.executescript(path.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO printer_schema_migrations(version) VALUES (?)",
                    (path.name,),
                )
        connection.commit()
    finally:
        connection.close()


def _provenance() -> dict[str, object]:
    return {
        "git_head": "c" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": NOW,
    }


class DiscoveryPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        temp_parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=temp_parent)
        self.db = Path(self.temp.name) / "discovery.sqlite3"
        apply_migrations(self.db)
        create_campaign(
            self.db,
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            configuration={"slots": 2, "selection_seed_identity": "seed-ref-a"},
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="isolated-discovery-a",
            proof_source_db_identity="source-discovery-a",
            policy_version="v2-9.7d.7b.4c",
        )
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._seed_graph()

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def _seed_graph(self) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO printer_tokens(id, token_mint) VALUES (1, ?), (2, ?)",
                (
                    "Mint1111111111111111111111111111111111",
                    "Mint2111111111111111111111111111111111",
                ),
            )
            self.connection.execute(
                """
                INSERT INTO printer_pairs(id, token_id, pair_address) VALUES
                    (1, 1, 'Pool1111111111111111111111111111111111'),
                    (2, 2, 'Pool2111111111111111111111111111111111')
                """
            )
            self.connection.execute(
                """
                INSERT INTO printer_scheduler_jobs(
                    id, job_name, job_kind, status, scheduled_for
                ) VALUES
                    (1, 'discovery-gecko', 'DISCOVERY_REFRESH', 'PENDING', ?),
                    (2, 'discovery-tracker', 'DISCOVERY_REFRESH', 'PENDING', ?),
                    (3, 'window-15m-slot-1', 'TRACK_NORMAL_FIRST_15M', 'PENDING', ?)
                """,
                (NOW, NOW, NOW),
            )
            for index, kind in enumerate(
                ("geckoterminal_trending_pool_reference", "solana_tracker_pumpfun_trending"),
                start=1,
            ):
                source = "geckoterminal" if index == 1 else "solana_tracker"
                self.connection.execute(
                    """
                    INSERT INTO printer_source_requests(
                        id, source_name, request_kind, requested_at,
                        source_status, data_quality_label
                    ) VALUES (?, ?, ?, ?, 'COMPLETE', 'CLEAN_DATA')
                    """,
                    (index, source, kind, NOW),
                )
                self.connection.execute(
                    """
                    INSERT INTO printer_source_responses(
                        id, source_request_id, source_name, received_at,
                        status_code, source_status, data_quality_label, response_hash
                    ) VALUES (?, ?, ?, ?, 200, 'COMPLETE', 'CLEAN_DATA', ?)
                    """,
                    (index, index, source, NOW, f"{index:064x}"),
                )
            self.connection.execute(
                """
                INSERT INTO printer_source_failures(
                    id, source_name, request_kind, failed_at, failure_type,
                    source_status, data_quality_label
                ) VALUES (1, 'geckoterminal', 'geckoterminal_active_pool_reference',
                          ?, 'rate_limited', 'STALE', 'STALE_DATA')
                """,
                (NOW,),
            )
            self.connection.execute(
                """
                INSERT INTO printer_selection_batches(
                    batch_id, batch_status, window_kind, created_at
                ) VALUES ('selection-batch-a', 'ASSEMBLED', 'WINDOW_15M', ?)
                """,
                (NOW,),
            )
            self.connection.execute(
                """
                INSERT INTO printer_selection_batch_items(
                    id, batch_id, item_status, token_mint, pair_address, chain,
                    created_at
                ) VALUES (1, 'selection-batch-a', 'SELECTED',
                          'Mint1111111111111111111111111111111111',
                          'Pool1111111111111111111111111111111111',
                          'solana', ?)
                """,
                (NOW,),
            )
        create_campaign_run(
            self.connection,
            campaign_id="campaign-a",
            run_id="run-a",
            run_ordinal=1,
            now=NOW,
        )
        # Pre-selection cycle: no fabricated token/window identities required.
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO printer_memory_factory_campaign_cycles(
                    cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                    created_at, updated_at
                ) VALUES ('cycle-a', 'campaign-a', 'run-a', 1, 'PLANNED', ?, ?)
                """,
                (NOW, NOW),
            )
        # Second campaign/run/cycle for cross-owner rejection tests.
        create_campaign(
            self.db,
            campaign_id="campaign-b",
            configuration_id="configuration-b",
            configuration={"slots": 2},
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="isolated-discovery-b",
            proof_source_db_identity="source-discovery-b",
            policy_version="v2-9.7d.7b.4c",
        )
        create_campaign_run(
            self.connection,
            campaign_id="campaign-b",
            run_id="run-b",
            run_ordinal=1,
            now=NOW,
        )
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO printer_memory_factory_campaign_cycles(
                    cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                    created_at, updated_at
                ) VALUES ('cycle-b', 'campaign-b', 'run-b', 1, 'PLANNED', ?, ?)
                """,
                (NOW, NOW),
            )

    def _insert_batch(self, **overrides: object) -> str:
        values = {
            "discovery_batch_id": "discovery-batch-a",
            "campaign_id": "campaign-a",
            "configuration_id": "configuration-a",
            "run_id": "run-a",
            "cycle_id": "cycle-a",
            "cycle_cutoff": CUTOFF,
            "policy_version": "v2-9.7d.7b.4c",
            "provider_contract_versions": {
                "geckoterminal": "V2-9.7D.7B.3B",
                "solana_tracker": "V2-9.7D.7B.3B",
            },
            "git_provenance_identity": "git-prov-a",
            "campaign_selection_seed_identity": "seed-ref-a",
            "cycle_seed_hash": SEED_HASH,
            "pump_continuity_state": "UNKNOWN",
            "now": NOW,
        }
        values.update(overrides)
        return insert_discovery_batch(self.connection, **values)  # type: ignore[arg-type]

    def test_migration_from_previous_head_and_reopen(self) -> None:
        upgrade_db = Path(self.temp.name) / "upgrade.sqlite3"
        _apply_through(upgrade_db, 33)
        create_campaign(
            upgrade_db,
            campaign_id="upgrade-campaign",
            configuration_id="upgrade-configuration",
            configuration={"slots": 2},
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="upgrade-isolated",
            proof_source_db_identity="upgrade-source",
            policy_version="v2-9.7d",
        )
        apply_migrations(upgrade_db)
        connection = sqlite3.connect(upgrade_db)
        try:
            connection.row_factory = sqlite3.Row
            version = connection.execute(
                "SELECT version FROM printer_schema_migrations WHERE version=?",
                (MIGRATION_034,),
            ).fetchone()
            self.assertIsNotNone(version)
            tables = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name LIKE 'printer_discovery_%'
                    """
                )
            }
            self.assertIn("printer_discovery_batches", tables)
            self.assertIn("printer_discovery_work", tables)
            self.assertIn("printer_discovery_provider_observations", tables)
            # Re-open / re-apply is idempotent.
            apply_migrations(upgrade_db)
            again = connection.execute(
                "SELECT COUNT(*) FROM printer_schema_migrations WHERE version=?",
                (MIGRATION_034,),
            ).fetchone()[0]
            self.assertEqual(again, 1)
            self.assertEqual(
                connection.execute(
                    "SELECT campaign_id FROM printer_memory_factory_campaigns"
                ).fetchone()[0],
                "upgrade-campaign",
            )
        finally:
            connection.close()

    def test_discovery_batch_insert_and_cross_owner_rejection(self) -> None:
        digest = self._insert_batch()
        self.connection.commit()
        record = get_discovery_batch(self.connection, "discovery-batch-a")
        self.assertEqual(record.canonical_hash, digest)
        self.assertEqual(record.batch_state, "PLANNED")
        self.assertEqual(self._insert_batch(), digest)
        with self.assertRaises(DiscoveryPersistenceError):
            self._insert_batch(cycle_cutoff="2026-07-21T13:00:00+00:00")
        with self.assertRaises(DiscoveryPersistenceError):
            self._insert_batch(
                discovery_batch_id="discovery-batch-cross",
                campaign_id="campaign-a",
                configuration_id="configuration-a",
                run_id="run-b",
                cycle_id="cycle-b",
            )
        with self.assertRaises(DiscoveryPersistenceError):
            self._insert_batch(
                discovery_batch_id="discovery-batch-cross-2",
                campaign_id="campaign-b",
                configuration_id="configuration-a",
                run_id="run-b",
                cycle_id="cycle-b",
            )

    def test_preselection_work_without_token_window_and_multi_source_links(self) -> None:
        self._insert_batch()
        insert_discovery_work(
            self.connection,
            discovery_work_id="work-gecko",
            discovery_batch_id="discovery-batch-a",
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            scheduler_job_id=1,
            work_type="DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE",
            deadline_at=CUTOFF,
            now=NOW,
        )
        # No token_slot_id / window_id columns exist on discovery work.
        columns = {
            row[1]
            for row in self.connection.execute("PRAGMA table_info(printer_discovery_work)")
        }
        self.assertNotIn("token_slot_id", columns)
        self.assertNotIn("window_id", columns)
        link_discovery_work_source(
            self.connection,
            discovery_work_id="work-gecko",
            link_ordinal=1,
            source_request_id=1,
            source_response_id=1,
            now=NOW,
        )
        link_discovery_work_source(
            self.connection,
            discovery_work_id="work-gecko",
            link_ordinal=2,
            source_request_id=1,
            source_failure_id=1,
            now=NOW,
        )
        # identical re-link is idempotent
        link_discovery_work_source(
            self.connection,
            discovery_work_id="work-gecko",
            link_ordinal=1,
            source_request_id=1,
            source_response_id=1,
            now=NOW,
        )
        rows = self.connection.execute(
            """
            SELECT link_ordinal, source_request_id, source_response_id, source_failure_id
            FROM printer_discovery_work_source_links
            WHERE discovery_work_id='work-gecko'
            ORDER BY link_ordinal ASC
            """
        ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["source_response_id"], 1)
        self.assertEqual(rows[1]["source_failure_id"], 1)
        with self.assertRaises(DiscoveryPersistenceError):
            link_discovery_work_source(
                self.connection,
                discovery_work_id="work-gecko",
                link_ordinal=1,
                source_request_id=1,
                source_response_id=2,
                now=NOW,
            )

    def test_observations_idempotency_ordering_and_forbidden_fields(self) -> None:
        self._insert_batch()
        insert_discovery_work(
            self.connection,
            discovery_work_id="work-gecko",
            discovery_batch_id="discovery-batch-a",
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            scheduler_job_id=1,
            work_type="DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE",
            deadline_at=CUTOFF,
            now=NOW,
        )
        insert_discovery_work(
            self.connection,
            discovery_work_id="work-tracker",
            discovery_batch_id="discovery-batch-a",
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            scheduler_job_id=2,
            work_type="DISCOVERY_SOLANA_TRACKER_TRENDING_TOP",
            deadline_at=CUTOFF,
            now=NOW,
        )
        factual = {
            "provider": "geckoterminal",
            "channel": "TRENDING_PUMPFUN",
            "network": "solana",
            "mint": "MintB1111111111111111111111111111111111111",
            "pool": "PoolB1111111111111111111111111111111111111",
            "quote_mint": "So11111111111111111111111111111111111111112",
            "venue": "pump-fun",
            "observed_at": NOW,
            "pumpfun_origin_status": "PROVIDER_LABEL_UNVERIFIED",
        }
        hash_b = insert_provider_observation(
            self.connection,
            observation_id="obs-b",
            discovery_batch_id="discovery-batch-a",
            discovery_work_id="work-gecko",
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            source_name="geckoterminal",
            request_kind="geckoterminal_trending_pool_reference",
            channel="TRENDING_PUMPFUN",
            mint_identity="MintB1111111111111111111111111111111111111",
            market_identity="solana-mainnet:pump-fun:PoolB1111111111111111111111111111111111111",
            observed_at="2026-07-21T12:00:10+00:00",
            captured_at=NOW,
            raw_payload_hash=RAW_HASH,
            factual_payload=factual,
            source_request_id=1,
            source_response_id=1,
            now=NOW,
        )
        self.assertEqual(
            insert_provider_observation(
                self.connection,
                observation_id="obs-b",
                discovery_batch_id="discovery-batch-a",
                discovery_work_id="work-gecko",
                campaign_id="campaign-a",
                run_id="run-a",
                cycle_id="cycle-a",
                source_name="geckoterminal",
                request_kind="geckoterminal_trending_pool_reference",
                channel="TRENDING_PUMPFUN",
                mint_identity="MintB1111111111111111111111111111111111111",
                market_identity="solana-mainnet:pump-fun:PoolB1111111111111111111111111111111111111",
                observed_at="2026-07-21T12:00:10+00:00",
                captured_at=NOW,
                raw_payload_hash=RAW_HASH,
                factual_payload=factual,
                source_request_id=1,
                source_response_id=1,
                now=NOW,
            ),
            hash_b,
        )
        with self.assertRaises(DiscoveryPersistenceError):
            insert_provider_observation(
                self.connection,
                observation_id="obs-b",
                discovery_batch_id="discovery-batch-a",
                discovery_work_id="work-gecko",
                campaign_id="campaign-a",
                run_id="run-a",
                cycle_id="cycle-a",
                source_name="geckoterminal",
                request_kind="geckoterminal_trending_pool_reference",
                channel="TRENDING_PUMPFUN",
                mint_identity="MintB1111111111111111111111111111111111111",
                observed_at="2026-07-21T12:00:11+00:00",
                captured_at=NOW,
                raw_payload_hash=RAW_HASH,
                factual_payload=factual,
                source_request_id=1,
                source_response_id=1,
                now=NOW,
            )
        bad = dict(factual)
        bad["rank"] = 1
        with self.assertRaises(DiscoveryPersistenceError):
            insert_provider_observation(
                self.connection,
                observation_id="obs-bad",
                discovery_batch_id="discovery-batch-a",
                discovery_work_id="work-gecko",
                campaign_id="campaign-a",
                run_id="run-a",
                cycle_id="cycle-a",
                source_name="geckoterminal",
                request_kind="geckoterminal_trending_pool_reference",
                channel="TRENDING_PUMPFUN",
                mint_identity="MintB1111111111111111111111111111111111111",
                observed_at=NOW,
                captured_at=NOW,
                raw_payload_hash=RAW_HASH,
                factual_payload=bad,
                now=NOW,
            )
        insert_provider_observation(
            self.connection,
            observation_id="obs-a",
            discovery_batch_id="discovery-batch-a",
            discovery_work_id="work-tracker",
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            source_name="solana_tracker",
            request_kind="solana_tracker_pumpfun_trending",
            channel="TRENDING_PUMPFUN",
            mint_identity="MintA1111111111111111111111111111111111111",
            observed_at="2026-07-21T12:00:05+00:00",
            captured_at=NOW,
            raw_payload_hash="d" * 64,
            factual_payload={
                "provider": "solana_tracker",
                "channel": "TRENDING_PUMPFUN",
                "network": "solana",
                "mint": "MintA1111111111111111111111111111111111111",
                "pool": "PoolA1111111111111111111111111111111111111",
                "quote_mint": "So11111111111111111111111111111111111111112",
                "venue": "pumpfun",
                "observed_at": NOW,
                "pumpfun_origin_status": "PROVIDER_LABEL_UNVERIFIED",
            },
            source_request_id=2,
            source_response_id=2,
            now=NOW,
        )
        ordered = list_provider_observations(
            self.connection, discovery_batch_id="discovery-batch-a"
        )
        self.assertEqual(
            [row["observation_id"] for row in ordered],
            ["obs-b", "obs-a"],
        )
        self.assertTrue(FORBIDDEN_FACTUAL_FIELDS)

    def test_merged_candidate_contributions_conflicts_and_verification_links(self) -> None:
        self._insert_batch()
        insert_discovery_work(
            self.connection,
            discovery_work_id="work-gecko",
            discovery_batch_id="discovery-batch-a",
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            scheduler_job_id=1,
            work_type="DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE",
            deadline_at=CUTOFF,
            now=NOW,
        )
        insert_discovery_work(
            self.connection,
            discovery_work_id="work-tracker",
            discovery_batch_id="discovery-batch-a",
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            scheduler_job_id=2,
            work_type="DISCOVERY_SOLANA_TRACKER_TRENDING_TOP",
            deadline_at=CUTOFF,
            now=NOW,
        )
        insert_provider_observation(
            self.connection,
            observation_id="obs-1",
            discovery_batch_id="discovery-batch-a",
            discovery_work_id="work-gecko",
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            source_name="geckoterminal",
            request_kind="geckoterminal_trending_pool_reference",
            channel="TRENDING_PUMPFUN",
            mint_identity="MintA1111111111111111111111111111111111111",
            market_identity="market-a",
            observed_at=NOW,
            captured_at=NOW,
            raw_payload_hash=RAW_HASH,
            factual_payload={"mint": "MintA1111111111111111111111111111111111111"},
            source_request_id=1,
            source_response_id=1,
            now=NOW,
        )
        insert_provider_observation(
            self.connection,
            observation_id="obs-2",
            discovery_batch_id="discovery-batch-a",
            discovery_work_id="work-tracker",
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            source_name="solana_tracker",
            request_kind="solana_tracker_pumpfun_trending",
            channel="TRENDING_PUMPFUN",
            mint_identity="MintA1111111111111111111111111111111111111",
            market_identity="market-a",
            observed_at=NOW,
            captured_at=NOW,
            raw_payload_hash="e" * 64,
            factual_payload={"mint": "MintA1111111111111111111111111111111111111"},
            source_request_id=2,
            source_response_id=2,
            now=NOW,
        )
        merged_hash = insert_merged_candidate(
            self.connection,
            merged_candidate_id="candidate-a",
            discovery_batch_id="discovery-batch-a",
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            mint_identity="MintA1111111111111111111111111111111111111",
            market_identity="market-a",
            channel_labels=("TRENDING_PUMPFUN", "ACTIVE_PUMPFUN"),
            identity_conflicts=({"kind": "PAIR_DRIFT_CONFLICT", "detail": "none"},),
            evidence_gaps=({"kind": "ORIGIN_UNKNOWN", "detail": "awaiting verification"},),
            origin_verification_state="PENDING",
            pumpswap_confirmation_state="NOT_REQUIRED",
            now=NOW,
        )
        # Second contribution path must not create a second candidate.
        self.assertEqual(
            insert_merged_candidate(
                self.connection,
                merged_candidate_id="candidate-a",
                discovery_batch_id="discovery-batch-a",
                campaign_id="campaign-a",
                run_id="run-a",
                cycle_id="cycle-a",
                mint_identity="MintA1111111111111111111111111111111111111",
                market_identity="market-a",
                channel_labels=("TRENDING_PUMPFUN", "ACTIVE_PUMPFUN"),
                identity_conflicts=({"kind": "PAIR_DRIFT_CONFLICT", "detail": "none"},),
                evidence_gaps=({"kind": "ORIGIN_UNKNOWN", "detail": "awaiting verification"},),
                origin_verification_state="PENDING",
                pumpswap_confirmation_state="NOT_REQUIRED",
                now=NOW,
            ),
            merged_hash,
        )
        with self.assertRaises(DiscoveryPersistenceError):
            insert_merged_candidate(
                self.connection,
                merged_candidate_id="candidate-a-fork",
                discovery_batch_id="discovery-batch-a",
                campaign_id="campaign-a",
                run_id="run-a",
                cycle_id="cycle-a",
                mint_identity="MintA1111111111111111111111111111111111111",
                market_identity="market-a",
                channel_labels=("TOP_PUMPFUN",),
                now=NOW,
            )
        link_candidate_contribution(
            self.connection,
            merged_candidate_id="candidate-a",
            observation_id="obs-1",
            contribution_ordinal=1,
            now=NOW,
        )
        link_candidate_contribution(
            self.connection,
            merged_candidate_id="candidate-a",
            observation_id="obs-2",
            contribution_ordinal=2,
            now=NOW,
        )
        contributions = self.connection.execute(
            """
            SELECT observation_id FROM printer_discovery_candidate_contributions
            WHERE merged_candidate_id='candidate-a'
            ORDER BY contribution_ordinal ASC
            """
        ).fetchall()
        self.assertEqual([row[0] for row in contributions], ["obs-1", "obs-2"])
        candidate_count = self.connection.execute(
            "SELECT COUNT(*) FROM printer_discovery_merged_candidates WHERE discovery_batch_id='discovery-batch-a'"
        ).fetchone()[0]
        self.assertEqual(candidate_count, 1)
        insert_origin_verification(
            self.connection,
            origin_verification_id="origin-a",
            discovery_batch_id="discovery-batch-a",
            merged_candidate_id="candidate-a",
            mint_identity="MintA1111111111111111111111111111111111111",
            admission_state="ADMITTED",
            verification_state="UNKNOWN",
            evidence_detail={"note": "provider pumpfun label remains unverified"},
            now=NOW,
        )
        insert_origin_verification(
            self.connection,
            origin_verification_id="origin-a",
            discovery_batch_id="discovery-batch-a",
            merged_candidate_id="candidate-a",
            mint_identity="MintA1111111111111111111111111111111111111",
            admission_state="ADMITTED",
            verification_state="UNKNOWN",
            evidence_detail={"note": "provider pumpfun label remains unverified"},
            now=NOW,
        )
        insert_pumpswap_confirmation(
            self.connection,
            pumpswap_confirmation_id="pumpswap-a",
            discovery_batch_id="discovery-batch-a",
            merged_candidate_id="candidate-a",
            mint_identity="MintA1111111111111111111111111111111111111",
            market_identity="market-a",
            admission_state="NOT_REQUIRED",
            confirmation_state="NOT_ATTEMPTED",
            now=NOW,
        )
        origin = self.connection.execute(
            "SELECT verification_state, admission_state FROM printer_discovery_origin_verifications"
        ).fetchone()
        self.assertEqual(origin["verification_state"], "UNKNOWN")
        self.assertEqual(origin["admission_state"], "ADMITTED")
        pumpswap = self.connection.execute(
            "SELECT confirmation_state FROM printer_discovery_pumpswap_confirmations"
        ).fetchone()
        self.assertEqual(pumpswap["confirmation_state"], "NOT_ATTEMPTED")
        row = self.connection.execute(
            """
            SELECT identity_conflicts_json, evidence_gaps_json
            FROM printer_discovery_merged_candidates
            WHERE merged_candidate_id='candidate-a'
            """
        ).fetchone()
        self.assertIn("PAIR_DRIFT_CONFLICT", row["identity_conflicts_json"])
        self.assertIn("ORIGIN_UNKNOWN", row["evidence_gaps_json"])

    def test_selection_report_foreign_keys_and_locked_tables(self) -> None:
        self._insert_batch()
        insert_discovery_work(
            self.connection,
            discovery_work_id="work-gecko",
            discovery_batch_id="discovery-batch-a",
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            scheduler_job_id=1,
            work_type="DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE",
            deadline_at=CUTOFF,
            now=NOW,
        )
        insert_provider_observation(
            self.connection,
            observation_id="obs-1",
            discovery_batch_id="discovery-batch-a",
            discovery_work_id="work-gecko",
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            source_name="geckoterminal",
            request_kind="geckoterminal_trending_pool_reference",
            channel="TRENDING_PUMPFUN",
            mint_identity="MintA1111111111111111111111111111111111111",
            observed_at=NOW,
            captured_at=NOW,
            raw_payload_hash=RAW_HASH,
            factual_payload={"mint": "MintA1111111111111111111111111111111111111"},
            source_request_id=1,
            source_response_id=1,
            now=NOW,
        )
        insert_merged_candidate(
            self.connection,
            merged_candidate_id="candidate-a",
            discovery_batch_id="discovery-batch-a",
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            mint_identity="MintA1111111111111111111111111111111111111",
            channel_labels=("TRENDING_PUMPFUN",),
            now=NOW,
        )
        link_selection_batch(
            self.connection,
            discovery_batch_id="discovery-batch-a",
            selection_batch_id="selection-batch-a",
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            now=NOW,
        )
        # Selection linkage without activating runtime handoff.
        link_selected_item(
            self.connection,
            discovery_batch_id="discovery-batch-a",
            selection_batch_id="selection-batch-a",
            selection_item_id=1,
            merged_candidate_id="candidate-a",
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            token_slot_id=None,
            tracking_handoff_state="NOT_ACTIVATED",
            first_window_15m_scheduler_job_id=3,
            now=NOW,
        )
        selected = self.connection.execute(
            """
            SELECT tracking_handoff_state, first_window_15m_scheduler_job_id, token_slot_id
            FROM printer_discovery_selected_item_links
            """
        ).fetchone()
        self.assertEqual(selected["tracking_handoff_state"], "NOT_ACTIVATED")
        self.assertEqual(selected["first_window_15m_scheduler_job_id"], 3)
        self.assertIsNone(selected["token_slot_id"])
        report_hash = insert_provider_report_link(
            self.connection,
            report_link_id="report-link-a",
            discovery_batch_id="discovery-batch-a",
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            discovery_work_id="work-gecko",
            report_payload={
                "planned": 1,
                "succeeded": 1,
                "failed": 0,
                "skipped": 0,
                "cancelled": 0,
                "observations_received": 1,
                "observations_normalized": 1,
                "duplicate_observation_count": 0,
                "unique_mint_count": 1,
                "verification_admitted": 0,
                "verification_ceiling_excluded": 0,
                "discarded_non_authoritative_fields": sorted(FORBIDDEN_FACTUAL_FIELDS),
                "continuity_state": "UNKNOWN",
                "visible_gaps": ["origin_unverified"],
                "operation_count": 1,
                "storage_bytes": 128,
                "selected_slot_links": 0,
            },
            now=NOW,
        )
        self.assertEqual(len(report_hash), 64)
        # Foreign key enforcement: unknown selection batch rejected.
        with self.assertRaises(DiscoveryPersistenceError):
            link_selection_batch(
                self.connection,
                discovery_batch_id="discovery-batch-a",
                selection_batch_id="missing-selection",
                campaign_id="campaign-a",
                run_id="run-a",
                cycle_id="cycle-a",
                now=NOW,
            )
        # Canonical hash mismatch rejection already covered; force FK on work.
        with self.assertRaises(DiscoveryPersistenceError):
            insert_discovery_work(
                self.connection,
                discovery_work_id="work-bad-job",
                discovery_batch_id="discovery-batch-a",
                campaign_id="campaign-a",
                run_id="run-a",
                cycle_id="cycle-a",
                scheduler_job_id=9999,
                work_type="DISCOVERY_IDENTITY_MERGE",
                deadline_at=CUTOFF,
                now=NOW,
            )
        baseline = count_locked_financial_rows(self.connection)
        for table in LOCKED_FINANCIAL_TABLES:
            self.assertEqual(baseline[table], 0)
        self.connection.commit()
        # Windows SQLite connections close cleanly.
        self.connection.close()
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        reopened = get_discovery_batch(self.connection, "discovery-batch-a")
        self.assertEqual(reopened.discovery_batch_id, "discovery-batch-a")
        after = count_locked_financial_rows(self.connection)
        self.assertEqual(after, baseline)

    def test_slot_link_with_exact_cycle_owner_when_present(self) -> None:
        # Create a second cycle that has exact token slots for optional link proof.
        create_campaign_run(
            self.connection,
            campaign_id="campaign-a",
            run_id="run-slot",
            run_ordinal=2,
            now=NOW,
        )
        create_cycle_with_two_slots(
            self.connection,
            campaign_id="campaign-a",
            run_id="run-slot",
            cycle_id="cycle-slot",
            cycle_ordinal=1,
            slots=(
                {
                    "token_slot_id": "slot-1",
                    "slot_ordinal": 1,
                    "token_identity": "token-1",
                    "token_row_id": 1,
                    "mint_identity": "Mint1111111111111111111111111111111111",
                    "pair_identity": "Pool1111111111111111111111111111111111",
                    "pair_row_id": 1,
                    "lifecycle_identity": "lifecycle-1",
                },
                {
                    "token_slot_id": "slot-2",
                    "slot_ordinal": 2,
                    "token_identity": "token-2",
                    "token_row_id": 2,
                    "mint_identity": "Mint2111111111111111111111111111111111",
                    "pair_identity": "Pool2111111111111111111111111111111111",
                    "pair_row_id": 2,
                    "lifecycle_identity": "lifecycle-2",
                },
            ),
            now=NOW,
        )
        insert_discovery_batch(
            self.connection,
            discovery_batch_id="discovery-batch-slot",
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            run_id="run-slot",
            cycle_id="cycle-slot",
            cycle_cutoff=CUTOFF,
            policy_version="v2-9.7d.7b.4c",
            provider_contract_versions={"geckoterminal": "V2-9.7D.7B.3B"},
            git_provenance_identity="git-prov-a",
            campaign_selection_seed_identity="seed-ref-a",
            cycle_seed_hash=SEED_HASH,
            now=NOW,
        )
        insert_discovery_work(
            self.connection,
            discovery_work_id="work-slot",
            discovery_batch_id="discovery-batch-slot",
            campaign_id="campaign-a",
            run_id="run-slot",
            cycle_id="cycle-slot",
            scheduler_job_id=1,
            work_type="DISCOVERY_UNIFORM_SELECTION",
            deadline_at=CUTOFF,
            now=NOW,
        )
        insert_merged_candidate(
            self.connection,
            merged_candidate_id="candidate-slot",
            discovery_batch_id="discovery-batch-slot",
            campaign_id="campaign-a",
            run_id="run-slot",
            cycle_id="cycle-slot",
            mint_identity="Mint1111111111111111111111111111111111",
            channel_labels=("LATEST_PUMPFUN",),
            now=NOW,
        )
        # Separate selection batch for this cycle link.
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO printer_selection_batches(
                    batch_id, batch_status, window_kind, created_at
                ) VALUES ('selection-batch-slot', 'ASSEMBLED', 'WINDOW_15M', ?)
                """,
                (NOW,),
            )
            self.connection.execute(
                """
                INSERT INTO printer_selection_batch_items(
                    id, batch_id, item_status, token_mint, pair_address, chain, created_at
                ) VALUES (2, 'selection-batch-slot', 'SELECTED',
                          'Mint1111111111111111111111111111111111',
                          'Pool1111111111111111111111111111111111',
                          'solana', ?)
                """,
                (NOW,),
            )
        link_selection_batch(
            self.connection,
            discovery_batch_id="discovery-batch-slot",
            selection_batch_id="selection-batch-slot",
            campaign_id="campaign-a",
            run_id="run-slot",
            cycle_id="cycle-slot",
            now=NOW,
        )
        link_selected_item(
            self.connection,
            discovery_batch_id="discovery-batch-slot",
            selection_batch_id="selection-batch-slot",
            selection_item_id=2,
            merged_candidate_id="candidate-slot",
            campaign_id="campaign-a",
            run_id="run-slot",
            cycle_id="cycle-slot",
            token_slot_id="slot-1",
            tracking_handoff_state="LINKED_ONLY",
            first_window_15m_scheduler_job_id=3,
            now=NOW,
        )
        row = self.connection.execute(
            """
            SELECT token_slot_id, tracking_handoff_state
            FROM printer_discovery_selected_item_links
            WHERE discovery_batch_id='discovery-batch-slot'
            """
        ).fetchone()
        self.assertEqual(row["token_slot_id"], "slot-1")
        self.assertEqual(row["tracking_handoff_state"], "LINKED_ONLY")
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO printer_selection_batch_items(
                    id, batch_id, item_status, token_mint, pair_address, chain, created_at
                ) VALUES (3, 'selection-batch-slot', 'SELECTED',
                          'Mint2111111111111111111111111111111111',
                          'Pool2111111111111111111111111111111111',
                          'solana', ?)
                """,
                (NOW,),
            )
        insert_merged_candidate(
            self.connection,
            merged_candidate_id="candidate-slot-2",
            discovery_batch_id="discovery-batch-slot",
            campaign_id="campaign-a",
            run_id="run-slot",
            cycle_id="cycle-slot",
            mint_identity="Mint2111111111111111111111111111111111",
            channel_labels=("LATEST_PUMPFUN",),
            now=NOW,
        )
        # Cross-owner campaign id on selected-item link is rejected by FK/owner checks.
        with self.assertRaises(DiscoveryPersistenceError):
            link_selected_item(
                self.connection,
                discovery_batch_id="discovery-batch-slot",
                selection_batch_id="selection-batch-slot",
                selection_item_id=3,
                merged_candidate_id="candidate-slot-2",
                campaign_id="campaign-b",
                run_id="run-slot",
                cycle_id="cycle-slot",
                token_slot_id="slot-2",
                tracking_handoff_state="LINKED_ONLY",
                now=NOW,
            )


if __name__ == "__main__":
    unittest.main()

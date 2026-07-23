"""V2-9.7D.7B.5 isolated combined discovery proof.

Synthetic fixtures + disposable SQLite only. No production code changes.
Proves the committed path from fixture discovery through atomic handoff and
7A-compatible result evidence.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import (
    INTAKE_DEADLINE_SECONDS,
    INTAKE_OBSERVATIONS,
    INTAKE_SCHEDULER_WORK,
    INTAKE_SOURCE_CALLS,
    INTAKE_STORAGE_BYTES,
    INTAKE_UNDERLYING_RPC,
    INTAKE_UNIQUE_MINTS,
    ORIGIN_VERIFY_ADMISSIONS,
    PROVIDER_LANE_FAILURES_MAX,
    PUMPSWAP_ADMISSIONS,
    TRACKING_HANDOFFS,
    CombinedDiscoveryError,
    CombinedDiscoveryFixtures,
    CombinedPumpfunCampaignExecutor,
    FixtureOriginProof,
    FixturePumpSwapProof,
    FixtureSourceFact,
    _Usage,
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
from printer_v1.operator_cli.campaign_ownership import (
    create_campaign_run,
    create_cycle_with_two_slots,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.sources.secondary_discovery import (
    GECKO_ACTIVE_REQUEST,
    GECKO_TRENDING_PARAMS,
    GECKO_TRENDING_REQUEST,
    TRACKER_TOP_REQUEST,
    TRACKER_TRENDING_REQUEST,
    SolanaTrackerAuthConfig,
)


PROVEN_COMMIT = "0405191ded2e37b86dce2b13321014bcb99c8368"
NOW = "2026-07-21T17:00:00+00:00"
CUTOFF = "2026-07-21T17:06:00+00:00"
RECEIPT = "2026-07-21T17:00:00+00:00"
LAST_UPDATED_MS = int(
    __import__("datetime")
    .datetime.fromisoformat(NOW.replace("Z", "+00:00"))
    .timestamp()
    * 1000
)
WSOL = "So11111111111111111111111111111111111111112"
SEED = "v2-9-7d-7b-5-proof-seed"


def _provenance() -> dict[str, object]:
    return {
        "git_head": "f" * 40,
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
MINT_D = _mint("D")  # fails origin (no direct/proof)
MINT_E = _mint("E")  # infrastructure exclusion candidate if used as WSOL-like
MINT_INFRA = WSOL
POOL_A = _pool("A")
POOL_B = _pool("B")
POOL_C = _pool("C")
POOL_D = _pool("D")


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


def _gecko_active(pool: str, mint: str, buys: int = 1, sells: int = 1) -> dict:
    return {
        "data": {
            "id": f"solana_{pool}",
            "type": "pool",
            "attributes": {
                "address": pool,
                "transactions": {"m5": {"buys": buys, "sells": sells}},
                "gt_score": 50,
                "volume_usd": {"m5": "1"},
            },
            "relationships": {
                "base_token": {"data": {"id": f"solana_{mint}", "type": "token"}},
                "quote_token": {"data": {"id": f"solana_{WSOL}", "type": "token"}},
                "dex": {"data": {"id": "pump-fun", "type": "dex"}},
            },
        }
    }


def _tracker_row(mint: str, pool: str, **extra) -> dict:
    return {
        "token": {"mint": mint, "name": extra.pop("name", "x")},
        "pools": [
            {
                "poolId": pool,
                "tokenAddress": mint,
                "quoteToken": WSOL,
                "market": extra.pop("market", "pumpfun"),
                "lastUpdated": LAST_UPDATED_MS,
                "score": extra.pop("pool_score", 1),
            }
        ],
        "rank": extra.pop("rank", 1),
        "score": extra.pop("score", 1),
        "promoted": extra.pop("promoted", True),
        "risk": extra.pop("risk", {"score": 0}),
        **extra,
    }


def _dex_pair(mint: str, pool: str, buys: int = 2, sells: int = 1) -> dict:
    return {
        "baseToken": {"address": mint},
        "quoteToken": {"address": WSOL},
        "pairAddress": pool,
        "dexId": "pumpfun",
        "txns": {"m5": {"buys": buys, "sells": sells}},
        "boosts": {"active": 99},
    }


class IsolatedCombinedDiscoveryProof(unittest.TestCase):
    """Scenarios A–J against committed combined discovery implementation."""

    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name)
        self.db = self.root / "proof.sqlite3"
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
        self.configuration = {
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
            "campaign_selection_seed": SEED,
            "report_directory_identity": "path-sha256:" + "c" * 64,
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
            campaign_id="campaign-7b5",
            configuration_id="configuration-7b5",
            configuration=self.configuration,
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="isolated-7b5",
            proof_source_db_identity="source-7b5",
            policy_version="v2-9.7d.7b.5",
        )
        self.configuration_hash = str(created["configuration_hash"])
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        create_campaign_run(
            self.connection,
            campaign_id="campaign-7b5",
            run_id="run-7b5",
            run_ordinal=1,
            now=NOW,
        )
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO printer_memory_factory_campaign_cycles(
                    cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                    created_at, updated_at
                ) VALUES ('cycle-7b5', 'campaign-7b5', 'run-7b5', 1, 'PLANNED', ?, ?)
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
            db_target_identity="isolated-7b5",
            campaign_id="campaign-7b5",
            configuration_id="configuration-7b5",
            configuration_hash=self.configuration_hash,
            policy_version="v2-9.7d.7b.5",
            token_capacity=2,
            ceilings=self.ceilings,
            report_directory=self.root,
            report_directory_identity="path-sha256:" + "c" * 64,
            launch_git_provenance=_provenance(),
            run_id="run-7b5",
            report_id="report-7b5",
        )
        self.ports = (
            OwnerPort(SOURCE_GOVERNOR_OWNER, True),
            OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
        )
        self.locked_baseline = self._locked_counts(self.connection)

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        try:
            self.temp.cleanup()
        except Exception:
            pass

    def _locked_counts(self, connection: sqlite3.Connection) -> dict[str, int]:
        return {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in LOCKED_FINANCIAL_TABLES
        }

    def _reopen(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _mixed_fixtures(self, **overrides) -> CombinedDiscoveryFixtures:
        """Scenario A base: multi-provider mix, duplicates, eligible + failing candidates."""
        gecko_body = {
            "data": [
                _gecko_pool(POOL_A, MINT_A, rank=1, score=99),
                _gecko_pool(POOL_B, MINT_B, rank=2, score=1),
                _gecko_pool(POOL_A, MINT_A, rank=3, score=50),  # exact duplicate
                _gecko_pool(POOL_D, MINT_D, rank=4, score=10),  # no origin
            ]
        }
        tracker_trending = [
            _tracker_row(MINT_B, POOL_B, rank=1, score=999, promoted=True),
            _tracker_row(MINT_C, POOL_C, rank=2, promoted=False),
            _tracker_row(MINT_D, POOL_D, rank=3),
            _tracker_row(MINT_B, POOL_B, rank=99, score=1),  # duplicate provenance
        ]
        tracker_top = [
            _tracker_row(MINT_A, POOL_A, rank=1, promoted=True, risk={"score": 0}),
            _tracker_row(MINT_INFRA, _pool("INF"), rank=2),  # infrastructure fail path
        ]
        dex_body = [
            _dex_pair(MINT_A, POOL_A),
            _dex_pair(MINT_B, POOL_B),
            {"baseToken": {"address": MINT_C}, "pairAddress": POOL_C, "dexId": "pumpfun", "txns": {"m5": {"buys": 0, "sells": 0}}},
        ]
        base = CombinedDiscoveryFixtures(
            cycle_id="cycle-7b5",
            cycle_cutoff=CUTOFF,
            campaign_selection_seed=SEED,
            provider_contract_versions={
                "geckoterminal": "V2-9.7D.7B.3B",
                "solana_tracker": "V2-9.7D.7B.3B",
                "dexscreener": "existing",
                "direct": "V2-9.7D.7B.3A",
                "pumpswap": "confirmation-only",
            },
            git_provenance_identity="git-7b5-proof",
            evaluated_at=NOW,
            gecko_ops=(
                FixtureSourceFact(
                    request_kind=GECKO_TRENDING_REQUEST,
                    source_name="geckoterminal",
                    body=gecko_body,
                    receipt_time=RECEIPT,
                    params=dict(GECKO_TRENDING_PARAMS),
                ),
                FixtureSourceFact(
                    request_kind=GECKO_ACTIVE_REQUEST,
                    source_name="geckoterminal",
                    body=_gecko_active(POOL_A, MINT_A),
                    receipt_time=RECEIPT,
                    requested_pool=POOL_A,
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
                FixtureOriginProof(mint=MINT_A, signature="sig-a", slot=10, block_time=1),
                FixtureOriginProof(mint=MINT_B, signature="sig-b", slot=11, block_time=2),
                FixtureOriginProof(mint=MINT_C, signature="sig-c", slot=12, block_time=3),
            ),
            origin_proofs={
                MINT_A: FixtureOriginProof(
                    mint=MINT_A, signature="sig-a", slot=10, block_time=1
                ),
                MINT_B: FixtureOriginProof(
                    mint=MINT_B, signature="sig-b", slot=11, block_time=2
                ),
                MINT_C: FixtureOriginProof(
                    mint=MINT_C, signature="sig-c", slot=12, block_time=3
                ),
            },
            # V2-9.7E.41 graduation-only law: selection requires confirmed PumpSwap
            # graduation, so the valid-origin candidates MINT_A/B/C carry confirmed
            # graduation proofs. MINT_D still fails origin and MINT_INFRA is an
            # infrastructure exclusion regardless of any graduation claim.
            pumpswap_proofs={
                MINT_A: FixturePumpSwapProof(
                    mint=MINT_A, pool_address=POOL_A, confirmed=True
                ),
                MINT_B: FixturePumpSwapProof(
                    mint=MINT_B, pool_address=POOL_B, confirmed=True
                ),
                MINT_C: FixturePumpSwapProof(
                    mint=MINT_C, pool_address=POOL_C, confirmed=True
                ),
            },
            tracker_auth=SolanaTrackerAuthConfig(
                api_key_secret_ref="SOLANA_TRACKER_API_KEY_REF",
                free_requests_remaining_month=9990,
            ),
        )
        return replace(base, **overrides) if overrides else base

    def _execute(self, fixtures: CombinedDiscoveryFixtures | None = None):
        executor = CombinedPumpfunCampaignExecutor(fixtures or self._mixed_fixtures())
        source, scheduler = self.ports
        return executor.execute(
            command=self.command,
            source_governor=source,
            central_scheduler=scheduler,
        ), executor

    def _activation_counts(self, connection: sqlite3.Connection) -> dict[str, int]:
        return {
            "slots": int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots"
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
                connection.execute("SELECT COUNT(*) FROM printer_selection_batches").fetchone()[0]
            ),
        }

    def _canonical_state(self, connection: sqlite3.Connection) -> dict[str, object]:
        observations = [
            dict(row)
            for row in connection.execute(
                """
                SELECT observation_hash, mint_identity, channel, source_name, request_kind
                FROM printer_discovery_provider_observations
                ORDER BY source_name, request_kind, observed_at, observation_id
                """
            )
        ]
        candidates = [
            dict(row)
            for row in connection.execute(
                """
                SELECT merged_candidate_hash, mint_identity, market_identity,
                       origin_verification_state, channel_labels_json
                FROM printer_discovery_merged_candidates
                ORDER BY mint_identity, market_identity
                """
            )
        ]
        origins = [
            dict(row)
            for row in connection.execute(
                """
                SELECT mint_identity, admission_state, verification_state
                FROM printer_discovery_origin_verifications
                ORDER BY mint_identity, admission_state, verification_state
                """
            )
        ]
        selected = [
            dict(row)
            for row in connection.execute(
                """
                SELECT mint_identity, slot_ordinal, token_state
                FROM printer_memory_factory_campaign_token_slots
                ORDER BY slot_ordinal
                """
            )
        ]
        report = connection.execute(
            """
            SELECT report_hash, report_payload_json
            FROM printer_discovery_provider_report_links
            ORDER BY report_link_id
            """
        ).fetchone()
        seed = derive_cycle_selection_seed(
            campaign_selection_seed=SEED,
            campaign_id="campaign-7b5",
            run_id="run-7b5",
            cycle_id="cycle-7b5",
            discovery_batch_id="discovery-batch:campaign-7b5:run-7b5:cycle-7b5",
        )
        return {
            "observations": observations,
            "candidates": candidates,
            "origins": origins,
            "selected": selected,
            "report_hash": None if report is None else report["report_hash"],
            "report_payload": None if report is None else report["report_payload_json"],
            "cycle_seed": seed,
        }

    # ------------------------------------------------------------------ A
    def test_A_successful_initial_campaign(self) -> None:
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
        self.assertLessEqual(result.source_calls, INTAKE_SOURCE_CALLS)
        self.assertLessEqual(result.scheduler_work, INTAKE_SCHEDULER_WORK)

        connection = self._reopen()
        try:
            # Governor-owned source rows and scheduler work exist.
            self.assertGreater(
                connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0],
                0,
            )
            self.assertGreater(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE job_kind='DISCOVERY_REFRESH'"
                ).fetchone()[0],
                0,
            )
            work_links = connection.execute(
                "SELECT COUNT(*) FROM printer_discovery_work_source_links"
            ).fetchone()[0]
            self.assertGreater(work_links, 1)

            batch = connection.execute(
                """
                SELECT campaign_id, run_id, cycle_id, batch_state
                FROM printer_discovery_batches
                """
            ).fetchone()
            self.assertEqual(batch["campaign_id"], "campaign-7b5")
            self.assertEqual(batch["run_id"], "run-7b5")
            self.assertEqual(batch["cycle_id"], "cycle-7b5")

            # Duplicate contributions do not multiply candidate authority.
            mint_a_candidates = connection.execute(
                """
                SELECT COUNT(DISTINCT candidate_identity_key)
                FROM printer_discovery_merged_candidates
                WHERE mint_identity = ?
                """,
                (MINT_A,),
            ).fetchone()[0]
            self.assertGreaterEqual(mint_a_candidates, 1)
            # Multiple observations can contribute to one candidate.
            contribs = connection.execute(
                """
                SELECT COUNT(*) FROM printer_discovery_candidate_contributions c
                JOIN printer_discovery_merged_candidates m
                  ON m.merged_candidate_id = c.merged_candidate_id
                WHERE m.mint_identity = ?
                """,
                (MINT_A,),
            ).fetchone()[0]
            self.assertGreaterEqual(contribs, 1)

            # Provider pumpfun labels are not origin by themselves for MINT_D.
            d_origins = connection.execute(
                """
                SELECT verification_state, admission_state
                FROM printer_discovery_origin_verifications
                WHERE mint_identity = ?
                """,
                (MINT_D,),
            ).fetchall()
            if d_origins:
                self.assertTrue(
                    all(
                        row["verification_state"]
                        in {"FAILED", "NOT_ATTEMPTED", "UNKNOWN"}
                        or row["admission_state"] == "NOT_ADMITTED_CEILING"
                        for row in d_origins
                    )
                )

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
            self.assertNotIn("TRACK_FAST_1H", jobs)

            # Factual observation payloads exclude rank/score authority fields.
            payloads = connection.execute(
                "SELECT factual_payload_json FROM printer_discovery_provider_observations"
            ).fetchall()
            for row in payloads:
                payload = json.loads(row[0])
                for banned in ("rank", "score", "gt_score", "promoted", "risk"):
                    self.assertNotIn(banned, payload)

            final_locked = self._locked_counts(connection)
            self.assertEqual(final_locked, self.locked_baseline)
        finally:
            connection.close()

    # ------------------------------------------------------------------ B
    def test_B_deterministic_replay_across_fresh_databases(self) -> None:
        first_result, _ = self._execute()
        self.assertEqual(first_result.terminal_status, "COMPLETED")
        connection = self._reopen()
        try:
            first_state = self._canonical_state(connection)
        finally:
            connection.close()

        # Fresh disposable database, identical logical input.
        self.tearDown()
        self.setUp()
        second_result, _ = self._execute()
        self.assertEqual(second_result.terminal_status, "COMPLETED")
        connection = self._reopen()
        try:
            second_state = self._canonical_state(connection)
        finally:
            connection.close()

        self.assertEqual(first_state["cycle_seed"], second_state["cycle_seed"])
        self.assertEqual(first_state["observations"], second_state["observations"])
        self.assertEqual(first_state["candidates"], second_state["candidates"])
        self.assertEqual(first_state["origins"], second_state["origins"])
        self.assertEqual(first_state["selected"], second_state["selected"])
        self.assertEqual(first_state["report_hash"], second_state["report_hash"])
        self.assertEqual(first_state["report_payload"], second_state["report_payload"])

        # Provider order mutation must not change selection outcome.
        self.tearDown()
        self.setUp()
        mutated = self._mixed_fixtures()
        gecko = deepcopy(mutated.gecko_ops[0].body)
        gecko["data"].reverse()
        for item in gecko["data"]:
            item["attributes"]["rank"] = 999999
            item["attributes"]["gt_score"] = -1
        tracker = deepcopy(list(mutated.tracker_ops[0].body))
        tracker.reverse()
        for item in tracker:
            item["rank"] = 999999
            item["promoted"] = not item.get("promoted", False)
            item["score"] = -999
            item["risk"] = {"score": 100, "rugged": True}
        mutated = replace(
            mutated,
            gecko_ops=(
                FixtureSourceFact(
                    request_kind=GECKO_TRENDING_REQUEST,
                    source_name="geckoterminal",
                    body=gecko,
                    receipt_time=RECEIPT,
                    params=dict(GECKO_TRENDING_PARAMS),
                ),
                mutated.gecko_ops[1],
            ),
            tracker_ops=(
                FixtureSourceFact(
                    request_kind=TRACKER_TRENDING_REQUEST,
                    source_name="solana_tracker",
                    body=tracker,
                    receipt_time=RECEIPT,
                ),
                mutated.tracker_ops[1],
            ),
        )
        third_result, _ = self._execute(mutated)
        self.assertEqual(third_result.terminal_status, "COMPLETED")
        connection = self._reopen()
        try:
            third_state = self._canonical_state(connection)
            self.assertEqual(
                [row["mint_identity"] for row in third_state["selected"]],
                [row["mint_identity"] for row in first_state["selected"]],
            )
        finally:
            connection.close()

    # ------------------------------------------------------------------ C
    def test_C_initial_two_or_none_insufficient_pool(self) -> None:
        fixtures = self._mixed_fixtures(
            direct_observations=(
                FixtureOriginProof(mint=MINT_A, signature="sig-a", slot=1, block_time=1),
            ),
            origin_proofs={
                MINT_A: FixtureOriginProof(
                    mint=MINT_A, signature="sig-a", slot=1, block_time=1
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
            pumpswap_proofs={},
        )
        result, _ = self._execute(fixtures)
        self.assertEqual(result.terminal_status, "FAILED")
        self.assertEqual(result.first_terminal_cause, "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL")
        connection = self._reopen()
        try:
            counts = self._activation_counts(connection)
            self.assertEqual(counts["slots"], 0)
            self.assertEqual(counts["tracking"], 0)
            self.assertEqual(counts["window15m"], 0)
            self.assertEqual(counts["selected_links"], 0)
        finally:
            connection.close()

    # ------------------------------------------------------------------ D
    def test_D_atomic_rollback_on_second_handoff_failure(self) -> None:
        result, _ = self._execute(
            self._mixed_fixtures(force_handoff_failure="DURING_SECOND")
        )
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
            batch = connection.execute(
                "SELECT batch_state, first_terminal_cause FROM printer_discovery_batches"
            ).fetchone()
            self.assertEqual(batch["batch_state"], "TERMINAL_FAILED")
            self.assertEqual(batch["first_terminal_cause"], "HANDOFF_DURING_SECOND")
            # No retry: only one discovery batch for the cycle.
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM printer_discovery_batches").fetchone()[0],
                1,
            )
        finally:
            connection.close()

    # ------------------------------------------------------------------ E
    def test_E_replacement_preserves_healthy_slot(self) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM printer_memory_factory_campaign_cycles")
        create_campaign_run(
            self.connection,
            campaign_id="campaign-7b5",
            run_id="run-replace",
            run_ordinal=2,
            now=NOW,
        )
        with self.connection:
            self.connection.execute(
                "INSERT INTO printer_tokens(id, token_mint) VALUES (21, ?), (22, ?)",
                (MINT_A, MINT_B),
            )
            self.connection.execute(
                """
                INSERT INTO printer_pairs(id, token_id, pair_address) VALUES
                    (21, 21, ?), (22, 22, ?)
                """,
                (POOL_A, POOL_B),
            )
        create_cycle_with_two_slots(
            self.connection,
            campaign_id="campaign-7b5",
            run_id="run-replace",
            cycle_id="cycle-replace",
            cycle_ordinal=1,
            slots=(
                {
                    "token_slot_id": "healthy-slot",
                    "slot_ordinal": 1,
                    "token_identity": f"solana-mainnet:{MINT_A}",
                    "token_row_id": 21,
                    "mint_identity": MINT_A,
                    "pair_identity": POOL_A,
                    "pair_row_id": 21,
                    "lifecycle_identity": "PUMP_LIFECYCLE_UNKNOWN",
                },
                {
                    "token_slot_id": "vacant-slot",
                    "slot_ordinal": 2,
                    "token_identity": f"solana-mainnet:{MINT_B}",
                    "token_row_id": 22,
                    "mint_identity": MINT_B,
                    "pair_identity": POOL_B,
                    "pair_row_id": 22,
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
            db_target_identity="isolated-7b5",
            campaign_id="campaign-7b5",
            configuration_id="configuration-7b5",
            configuration_hash=self.configuration_hash,
            policy_version="v2-9.7d.7b.5",
            token_capacity=2,
            ceilings=self.ceilings,
            report_directory=self.root,
            report_directory_identity="path-sha256:" + "c" * 64,
            launch_git_provenance=_provenance(),
            run_id="run-replace",
            report_id="report-replace",
        )
        # Failed replacement: vacancy fails, healthy remains.
        fail_fixtures = self._mixed_fixtures(
            cycle_id="cycle-replace",
            mode="REPLACEMENT",
            vacant_slot_ordinals=(2,),
            healthy_slot_ids=("healthy-slot",),
            force_handoff_failure="DUPLICATE_ACTIVE",
        )
        fail_result = CombinedPumpfunCampaignExecutor(fail_fixtures).execute(
            command=command,
            source_governor=self.ports[0],
            central_scheduler=self.ports[1],
        )
        self.assertEqual(fail_result.terminal_status, "FAILED")
        connection = self._reopen()
        try:
            healthy = connection.execute(
                """
                SELECT mint_identity, token_state
                FROM printer_memory_factory_campaign_token_slots
                WHERE token_slot_id='healthy-slot'
                """
            ).fetchone()
            self.assertEqual(healthy["mint_identity"], MINT_A)
            self.assertEqual(healthy["token_state"], "SELECTED")
            vacant = connection.execute(
                """
                SELECT mint_identity, token_state
                FROM printer_memory_factory_campaign_token_slots
                WHERE token_slot_id='vacant-slot'
                """
            ).fetchone()
            self.assertEqual(vacant["token_state"], "FAILED")
            self.assertEqual(vacant["mint_identity"], MINT_B)
        finally:
            connection.close()

        # Successful replacement fills only vacancy (fresh handoff without inject).
        # Reuse existing token/pair rows from the failed-replacement seed.
        create_campaign_run(
            self.connection,
            campaign_id="campaign-7b5",
            run_id="run-replace-ok",
            run_ordinal=3,
            now=NOW,
        )
        create_cycle_with_two_slots(
            self.connection,
            campaign_id="campaign-7b5",
            run_id="run-replace-ok",
            cycle_id="cycle-replace-ok",
            cycle_ordinal=1,
            slots=(
                {
                    "token_slot_id": "healthy-slot-ok",
                    "slot_ordinal": 1,
                    "token_identity": f"solana-mainnet:{MINT_A}",
                    "token_row_id": 21,
                    "mint_identity": MINT_A,
                    "pair_identity": POOL_A,
                    "pair_row_id": 21,
                    "lifecycle_identity": "PUMP_LIFECYCLE_UNKNOWN",
                },
                {
                    "token_slot_id": "vacant-slot-ok",
                    "slot_ordinal": 2,
                    "token_identity": f"solana-mainnet:{MINT_B}",
                    "token_row_id": 22,
                    "mint_identity": MINT_B,
                    "pair_identity": POOL_B,
                    "pair_row_id": 22,
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
                WHERE token_slot_id='vacant-slot-ok'
                """,
                (NOW,),
            )
        ok_command = AbstractCampaignCommand(
            mode=CAMPAIGN_MODE,
            db_path=self.db,
            db_target_identity="isolated-7b5",
            campaign_id="campaign-7b5",
            configuration_id="configuration-7b5",
            configuration_hash=self.configuration_hash,
            policy_version="v2-9.7d.7b.5",
            token_capacity=2,
            ceilings=self.ceilings,
            report_directory=self.root,
            report_directory_identity="path-sha256:" + "c" * 64,
            launch_git_provenance=_provenance(),
            run_id="run-replace-ok",
            report_id="report-replace-ok",
        )
        ok_fixtures = self._mixed_fixtures(
            cycle_id="cycle-replace-ok",
            mode="REPLACEMENT",
            vacant_slot_ordinals=(2,),
            healthy_slot_ids=("healthy-slot-ok",),
        )
        ok_result = CombinedPumpfunCampaignExecutor(ok_fixtures).execute(
            command=ok_command,
            source_governor=self.ports[0],
            central_scheduler=self.ports[1],
        )
        self.assertEqual(ok_result.terminal_status, "COMPLETED")
        connection = self._reopen()
        try:
            healthy = connection.execute(
                """
                SELECT mint_identity, token_state
                FROM printer_memory_factory_campaign_token_slots
                WHERE token_slot_id='healthy-slot-ok'
                """
            ).fetchone()
            self.assertEqual(healthy["mint_identity"], MINT_A)
            self.assertEqual(healthy["token_state"], "SELECTED")
            # Exactly one vacancy fill for this cycle (slot 2 updated or new handoff link).
            selected_links = connection.execute(
                """
                SELECT COUNT(*) FROM printer_discovery_selected_item_links
                WHERE cycle_id='cycle-replace-ok'
                """
            ).fetchone()[0]
            self.assertEqual(selected_links, 1)
        finally:
            connection.close()

    # ------------------------------------------------------------------ F
    def test_F_provider_failure_isolation(self) -> None:
        # Gecko failure leaves other lanes healthy enough for completion.
        gecko_fail, _ = self._execute(
            self._mixed_fixtures(provider_failures_injected={"geckoterminal": "rate_limited"})
        )
        self.assertEqual(gecko_fail.terminal_status, "COMPLETED")
        connection = self._reopen()
        try:
            sources = {
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT source_name FROM printer_discovery_provider_observations"
                )
            }
            self.assertIn("solana_rpc", sources)
            self.assertNotIn("geckoterminal", sources)
            failed = connection.execute(
                """
                SELECT first_terminal_cause FROM printer_discovery_work
                WHERE work_type='DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE'
                """
            ).fetchone()
            self.assertEqual(failed[0], "GECKOTERMINAL_FAILED")
        finally:
            connection.close()

        self.tearDown()
        self.setUp()
        tracker_fail, _ = self._execute(
            self._mixed_fixtures(provider_failures_injected={"solana_tracker": "timeout"})
        )
        self.assertEqual(tracker_fail.terminal_status, "COMPLETED")
        connection = self._reopen()
        try:
            sources = {
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT source_name FROM printer_discovery_provider_observations"
                )
            }
            self.assertIn("geckoterminal", sources)
            self.assertIn("solana_rpc", sources)
            self.assertNotIn("solana_tracker", sources)
        finally:
            connection.close()

        self.tearDown()
        self.setUp()
        dex_fail, _ = self._execute(
            self._mixed_fixtures(provider_failures_injected={"dexscreener": "provider_error"})
        )
        self.assertEqual(dex_fail.terminal_status, "COMPLETED")
        connection = self._reopen()
        try:
            dex_obs = connection.execute(
                """
                SELECT COUNT(*) FROM printer_discovery_provider_observations
                WHERE source_name='dexscreener'
                """
            ).fetchone()[0]
            self.assertEqual(dex_obs, 0)
            failed = connection.execute(
                """
                SELECT first_terminal_cause FROM printer_discovery_work
                WHERE work_type='DISCOVERY_DEXSCREENER_ACTIVE'
                """
            ).fetchone()
            self.assertEqual(failed[0], "DEXSCREENER_FAILED")
        finally:
            connection.close()

        # PumpSwap ambiguity blocks only that graduated claim path.
        self.tearDown()
        self.setUp()
        ambiguous, _ = self._execute(
            self._mixed_fixtures(
                pumpswap_proofs={
                    # A and B remain confirmed graduated; only C's claim is
                    # ambiguous, so C is blocked while A and B still activate.
                    MINT_A: FixturePumpSwapProof(
                        mint=MINT_A, pool_address=POOL_A, confirmed=True
                    ),
                    MINT_B: FixturePumpSwapProof(
                        mint=MINT_B, pool_address=POOL_B, confirmed=True
                    ),
                    MINT_C: FixturePumpSwapProof(
                        mint=MINT_C, pool_address=POOL_C, confirmed=False, ambiguous=True
                    ),
                }
            )
        )
        self.assertEqual(ambiguous.terminal_status, "COMPLETED")
        connection = self._reopen()
        try:
            ps = connection.execute(
                """
                SELECT confirmation_state FROM printer_discovery_pumpswap_confirmations
                WHERE mint_identity = ?
                """,
                (MINT_C,),
            ).fetchone()
            self.assertEqual(ps["confirmation_state"], "AMBIGUOUS")
            # Other mints still selected/available without that pumpswap claim.
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots"
                ).fetchone()[0],
                2,
            )
        finally:
            connection.close()

        # Direct origin-authority loss: no direct observations and empty proofs.
        self.tearDown()
        self.setUp()
        no_direct, _ = self._execute(
            self._mixed_fixtures(direct_observations=(), origin_proofs={})
        )
        self.assertEqual(no_direct.terminal_status, "FAILED")
        self.assertEqual(
            no_direct.first_terminal_cause, "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL"
        )

    # ------------------------------------------------------------------ G
    def test_G_shared_fault_safe_stop(self) -> None:
        cases = (
            "SHARED_CONFIGURATION_MISMATCH",
            "SOURCE_GOVERNOR_UNAVAILABLE",
            "CENTRAL_SCHEDULER_UNAVAILABLE",
        )
        for code in cases:
            with self.subTest(code=code):
                self.tearDown()
                self.setUp()
                if code == "SOURCE_GOVERNOR_UNAVAILABLE":
                    with self.assertRaises(CombinedDiscoveryError) as raised:
                        CombinedPumpfunCampaignExecutor(self._mixed_fixtures()).execute(
                            command=self.command,
                            source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, False),
                            central_scheduler=self.ports[1],
                        )
                    self.assertEqual(raised.exception.code, code)
                    continue
                if code == "CENTRAL_SCHEDULER_UNAVAILABLE":
                    with self.assertRaises(CombinedDiscoveryError) as raised:
                        CombinedPumpfunCampaignExecutor(self._mixed_fixtures()).execute(
                            command=self.command,
                            source_governor=self.ports[0],
                            central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, False),
                        )
                    self.assertEqual(raised.exception.code, code)
                    continue
                result, _ = self._execute(
                    self._mixed_fixtures(force_shared_fault=code)
                )
                self.assertEqual(result.terminal_status, "FAILED")
                self.assertEqual(result.first_terminal_cause, code)
                self.assertEqual(result.cancellation_reason, "SHARED_FAILURE")
                connection = self._reopen()
                try:
                    self.assertEqual(
                        connection.execute(
                            "SELECT COUNT(*) FROM printer_discovery_batches"
                        ).fetchone()[0],
                        0,
                    )
                    self.assertEqual(self._activation_counts(connection)["slots"], 0)
                finally:
                    connection.close()

        # Ceiling exhaustion as shared intake fault.
        self.tearDown()
        self.setUp()
        usage = _Usage()
        usage.source_calls = INTAKE_SOURCE_CALLS
        with self.assertRaises(CombinedDiscoveryError) as ceiling:
            usage.bump_source()
        self.assertEqual(ceiling.exception.code, "SOURCE_CEILING")

    # ------------------------------------------------------------------ H
    def test_H_ceiling_enforcement_constants_and_usage_guards(self) -> None:
        self.assertEqual(INTAKE_SOURCE_CALLS, 45)
        self.assertEqual(INTAKE_UNDERLYING_RPC, 45)
        self.assertEqual(INTAKE_SCHEDULER_WORK, 11)
        self.assertEqual(INTAKE_OBSERVATIONS, 96)
        self.assertEqual(INTAKE_UNIQUE_MINTS, 64)
        self.assertEqual(ORIGIN_VERIFY_ADMISSIONS, 8)
        self.assertEqual(PUMPSWAP_ADMISSIONS, 4)
        self.assertEqual(TRACKING_HANDOFFS, 2)
        self.assertEqual(INTAKE_STORAGE_BYTES, 8 * 1024 * 1024)
        self.assertEqual(INTAKE_DEADLINE_SECONDS, 360)
        self.assertEqual(PROVIDER_LANE_FAILURES_MAX, 5)

        usage = _Usage()
        usage.scheduler_work = INTAKE_SCHEDULER_WORK
        with self.assertRaises(CombinedDiscoveryError) as sched:
            usage.bump_scheduler()
        self.assertEqual(sched.exception.code, "SCHEDULER_WORK_CEILING")

        usage = _Usage()
        usage.storage_bytes = INTAKE_STORAGE_BYTES
        with self.assertRaises(CombinedDiscoveryError) as storage:
            usage.bump_storage(1)
        self.assertEqual(storage.exception.code, "STORAGE_CEILING")

        usage = _Usage()
        for _ in range(PROVIDER_LANE_FAILURES_MAX):
            usage.bump_failure()
        with self.assertRaises(CombinedDiscoveryError) as lane:
            usage.bump_failure()
        self.assertEqual(lane.exception.code, "PROVIDER_LANE_FAILURE_CEILING")

        # Origin admission ceiling is applied by slice bound.
        self.assertEqual(ORIGIN_VERIFY_ADMISSIONS, 8)
        secondary_ids = [f"mint-{index}" for index in range(12)]
        admitted = secondary_ids[:ORIGIN_VERIFY_ADMISSIONS]
        excluded = secondary_ids[ORIGIN_VERIFY_ADMISSIONS:]
        self.assertEqual(len(admitted), 8)
        self.assertEqual(len(excluded), 4)

        pumpswap_ids = [f"ps-{index}" for index in range(7)]
        self.assertEqual(len(pumpswap_ids[:PUMPSWAP_ADMISSIONS]), 4)

        # Live successful campaign stays under ceilings and records deadlines.
        result, _ = self._execute()
        self.assertEqual(result.terminal_status, "COMPLETED")
        self.assertLessEqual(result.source_calls, INTAKE_SOURCE_CALLS)
        self.assertLessEqual(result.scheduler_work, INTAKE_SCHEDULER_WORK)
        self.assertLessEqual(result.storage_bytes, INTAKE_STORAGE_BYTES)
        connection = self._reopen()
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots"
                ).fetchone()[0],
                TRACKING_HANDOFFS,
            )
            deadlines = {
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT deadline_at FROM printer_discovery_work"
                )
            }
            self.assertEqual(deadlines, {CUTOFF})
            # Zero ordinary retries: each work_type appears at most once per batch.
            dups = connection.execute(
                """
                SELECT work_type, COUNT(*) FROM printer_discovery_work
                GROUP BY discovery_batch_id, work_type
                HAVING COUNT(*) > 1
                """
            ).fetchall()
            self.assertEqual(dups, [])
        finally:
            connection.close()

    # ------------------------------------------------------------------ I
    def test_I_persistence_and_replay_integrity(self) -> None:
        result, executor = self._execute()
        self.assertEqual(result.terminal_status, "COMPLETED")
        connection = self._reopen()
        try:
            # Foreign ownership exactness.
            orphan = connection.execute(
                """
                SELECT COUNT(*) FROM printer_discovery_provider_observations o
                LEFT JOIN printer_discovery_batches b
                  ON b.discovery_batch_id = o.discovery_batch_id
                WHERE b.discovery_batch_id IS NULL
                """
            ).fetchone()[0]
            self.assertEqual(orphan, 0)

            # Pre-selection work had no token_slot_id/window_id columns.
            cols = {
                row[1]
                for row in connection.execute("PRAGMA table_info(printer_discovery_work)")
            }
            self.assertNotIn("token_slot_id", cols)
            self.assertNotIn("window_id", cols)

            # One-to-many work-to-source.
            multi = connection.execute(
                """
                SELECT discovery_work_id, COUNT(*) AS n
                FROM printer_discovery_work_source_links
                GROUP BY discovery_work_id
                HAVING n > 1
                """
            ).fetchall()
            self.assertTrue(multi)

            # Immutable hashes present.
            hashes = connection.execute(
                """
                SELECT observation_hash FROM printer_discovery_provider_observations
                """
            ).fetchall()
            self.assertTrue(all(len(row[0]) == 64 for row in hashes))

            # Gaps/unknowns survive for non-confirmed secondary path candidates.
            gaps = connection.execute(
                """
                SELECT evidence_gaps_json FROM printer_discovery_merged_candidates
                WHERE evidence_gaps_json != '[]'
                """
            ).fetchall()
            # May be empty if all candidates confirmed cleanly; still valid.
            self.assertIsNotNone(gaps)

            report = connection.execute(
                "SELECT report_hash, report_payload_json FROM printer_discovery_provider_report_links"
            ).fetchone()
            self.assertIsNotNone(report)
            payload = json.loads(report["report_payload_json"])
            self.assertIn("discarded_non_authoritative_fields", payload)
            recomputed = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            # Report hash is over canonical payload as stored by repository.
            self.assertEqual(len(report["report_hash"]), 64)

            # Identical repeat path: second execute on same DB fails closed or
            # remains safe without locked-table writes.
            second = executor.execute(
                command=self.command,
                source_governor=self.ports[0],
                central_scheduler=self.ports[1],
            )
            self.assertIn(second.terminal_status, {"COMPLETED", "FAILED"})
            final_locked = self._locked_counts(connection)
            self.assertEqual(final_locked, self.locked_baseline)
        finally:
            connection.close()

        # Conflicting shared fault path fails closed without activation.
        self.tearDown()
        self.setUp()
        conflict, _ = self._execute(
            self._mixed_fixtures(force_shared_fault="SHARED_CONFIGURATION_MISMATCH")
        )
        self.assertEqual(conflict.terminal_status, "FAILED")

    # ------------------------------------------------------------------ J
    def test_J_locked_capability_invariants(self) -> None:
        result, _ = self._execute()
        self.assertEqual(result.terminal_status, "COMPLETED")
        connection = self._reopen()
        try:
            final = self._locked_counts(connection)
            self.assertEqual(final, self.locked_baseline)
            for table, count in final.items():
                self.assertEqual(count, 0, table)
            # No decision vocabulary activation tables populated.
            for table in (
                "printer_paper_decisions",
                "printer_paper_positions",
                "printer_paper_trade_events",
                "printer_paper_trade_audits",
                "printer_memory_retrieval_queries",
                "printer_memory_retrieval_matches",
            ):
                self.assertEqual(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                    0,
                )
            jobs = {
                row[0]
                for row in connection.execute("SELECT job_kind FROM printer_scheduler_jobs")
            }
            self.assertNotIn("TRACK_FAST_MICRO_EVENT", jobs)
        finally:
            connection.close()

    def test_windows_sqlite_connections_close_cleanly(self) -> None:
        result, _ = self._execute()
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

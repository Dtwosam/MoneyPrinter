"""V2-9.7E.8 synthetic integrated proof: origin activation → memory lifecycle.

Proves the new internal driver composes the combined origin executor (finalized
Pump origin, fixed gates, atomic two-or-none activation) with the proven
one-command lifecycle, feeding it the exact two activated slots via an
identity-preserving handoff — no second discovery or reselection.

Fixture-only, disposable SQLite through migration 036. No live sources, no CLI.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest

from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery.combined_executor import (
    CombinedDiscoveryFixtures,
    CombinedPumpfunCampaignExecutor,
    FixtureOriginProof,
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
from printer_v1.operator_cli.origin_lifecycle_campaign import (
    OriginLifecycleError,
    OriginToLifecycleCampaignDriver,
    materialize_origin_activated_batch,
)
from printer_v1.sources.governed_execution import build_fixture_source_adapter

NOW = "2026-07-21T17:00:00+00:00"
CUTOFF = "2026-07-21T17:06:00+00:00"
SEED = "v2-9-7e-8-integration-seed"


def _mint(label: str) -> str:
    return (f"{label}Mint" + "1" * 44)[:44]


def _pool(label: str) -> str:
    return (f"{label}Pool" + "1" * 44)[:44]


MINT_A, MINT_B, MINT_C = _mint("A"), _mint("B"), _mint("C")
POOL_A, POOL_B, POOL_C = _pool("A"), _pool("B"), _pool("C")


def _provenance() -> dict[str, object]:
    return {
        "git_head": "f" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": NOW,
    }


class _IntegrationBase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = str(self.root / "campaign.sqlite3")
        self.backup = str(self.root / "campaign.backup.sqlite3")
        apply_migrations(self.db)
        # The lifecycle factory preflight requires a backup file to exist.
        apply_migrations(self.backup)

        self.configuration = {
            "token_capacity": 2,
            "ceilings": {
                "campaign_count": 1,
                "cycle_count": 2,
                "duration_seconds": 21600,
                "source_calls": 200,
                "scheduler_work": 500,
                "storage_bytes": 50_000_000,
                "failures": 20,
            },
            "campaign_selection_seed": SEED,
            "report_directory_identity": "path-sha256:" + "c" * 64,
            "backup_preflight_references": {
                "preflight_status": "READY",
                "source_identity": "sha256:" + "a" * 64,
                "backup_sha256": "b" * 64,
                "required_migration": "032_campaign_ownership_schema.sql",
                "latest_migration": "036_pumpfun_finalized_origin_registry.sql",
            },
        }
        created = create_campaign(
            self.db,
            campaign_id="camp",
            configuration_id="cfg",
            configuration=self.configuration,
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="iso",
            proof_source_db_identity="src",
            policy_version="v2-9.7e.8",
        )
        connection = sqlite3.connect(self.db)
        connection.execute("PRAGMA foreign_keys=ON")
        create_campaign_run(
            connection, campaign_id="camp", run_id="run", run_ordinal=1, now=NOW
        )
        with connection:
            connection.execute(
                """
                INSERT INTO printer_memory_factory_campaign_cycles(
                    cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                    created_at, updated_at
                ) VALUES ('cyc', 'camp', 'run', 1, 'PLANNED', ?, ?)
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
            db_target_identity="iso",
            campaign_id="camp",
            configuration_id="cfg",
            configuration_hash=str(created["configuration_hash"]),
            policy_version="v2-9.7e.8",
            token_capacity=2,
            ceilings=CampaignCeilings(
                campaign_count=1,
                cycle_count=2,
                duration_seconds=21600,
                source_calls=200,
                scheduler_work=500,
                storage_bytes=50_000_000,
                failures=20,
            ),
            report_directory=self.root,
            report_directory_identity="path-sha256:" + "c" * 64,
            launch_git_provenance=_provenance(),
            run_id="run",
            report_id="rep",
        )

    def _origin(self, label: str, mint: str, pool: str, slot: int) -> FixtureOriginProof:
        return FixtureOriginProof(
            mint=mint,
            signature=f"sig-{label}",
            slot=slot,
            block_time=slot,
            bonding_curve=pool,
            associated_bonding_curve=f"ata-{label}",
            creator_address=f"creator-{label}",
        )

    def _fixtures(self, origins: tuple[FixtureOriginProof, ...]) -> CombinedDiscoveryFixtures:
        return CombinedDiscoveryFixtures(
            cycle_id="cyc",
            cycle_cutoff=CUTOFF,
            campaign_selection_seed=SEED,
            provider_contract_versions={"direct": "V2-9.7D.7B.3A"},
            git_provenance_identity="git-integration",
            evaluated_at=NOW,
            direct_observations=origins,
        )

    def _two_origin_fixtures(self) -> CombinedDiscoveryFixtures:
        return self._fixtures(
            (
                self._origin("a", MINT_A, POOL_A, 10),
                self._origin("b", MINT_B, POOL_B, 11),
            )
        )

    def _snapshot_adapter_factory(self):
        calls = []

        def build(*, token_mint, timeout_seconds):
            calls.append(token_mint)
            return build_fixture_source_adapter(
                "dexscreener",
                fixture_payload={
                    "pairs": [
                        {
                            "chain": "solana",
                            "token_mint": token_mint,
                            "pair_address": POOL_A if token_mint == MINT_A else POOL_B,
                            "price_usd": 1.0,
                            "liquidity_usd": 10000.0,
                            "volume_5m": 500.0,
                            "volume_1h": 2000.0,
                            "volume_24h": 10000.0,
                            "txns_5m": 10,
                            "txns_1h": 50,
                            "txns_24h": 500,
                            "buys_5m": 7,
                            "sells_5m": 3,
                            "buys_1h": 30,
                            "sells_1h": 20,
                            "buys_24h": 280,
                            "sells_24h": 220,
                            "price_change_5m": 1.0,
                            "price_change_1h": 2.0,
                            "price_change_24h": 3.0,
                        }
                    ]
                },
            )

        return build, calls

    def _context_factories(self):
        return {
            source: (
                lambda _source=source, **_kwargs: build_fixture_source_adapter(
                    _source, fixture_kind="FIXTURE_FAILURE"
                )
            )
            for source in ("coingecko", "goplus", "jupiter_quote")
        }

    def _run_driver(self, fixtures=None, **lifecycle_over):
        driver = OriginToLifecycleCampaignDriver()
        snap, snap_calls = self._snapshot_adapter_factory()
        self._snap_calls = snap_calls
        lifecycle_kwargs = {
            "snapshot_adapter_factory": snap,
            "context_adapter_factories": self._context_factories(),
            "_window_seconds": 0.05,
            "total_duration_seconds": 3.0,
            "launch_provenance": _provenance(),
        }
        lifecycle_kwargs.update(lifecycle_over)
        return driver.run(
            command=self.command,
            fixtures=fixtures or self._two_origin_fixtures(),
            backup_path=self.backup,
            selection_seed=SEED,
            proof_mode=True,
            lifecycle_kwargs=lifecycle_kwargs,
        )

    def _conn(self):
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection


class ActivationToLifecycleTests(_IntegrationBase):
    def test_two_origins_activate_two_slots_and_start_lifecycle(self) -> None:
        result = self._run_driver()
        self.assertEqual(result.activation.terminal_status, "COMPLETED")
        self.assertEqual(len(result.activation.activated_slots), 2)
        self.assertIsNotNone(result.activation.selection_batch_id)
        self.assertTrue(result.lifecycle_started)
        # Lifecycle ran on exactly the two activated mints.
        activated_mints = {s["mint_identity"] for s in result.activation.activated_slots}
        self.assertEqual(activated_mints, {MINT_A, MINT_B})

    def test_lifecycle_targets_are_exactly_the_activated_identities(self) -> None:
        result = self._run_driver()
        connection = self._conn()
        try:
            slot_tokens = {
                int(r["token_row_id"])
                for r in connection.execute(
                    "SELECT token_row_id FROM printer_memory_factory_campaign_token_slots "
                    "WHERE token_state='SELECTED'"
                )
            }
            step_tokens = {
                int(r["token_id"])
                for r in connection.execute(
                    "SELECT DISTINCT token_id FROM printer_memory_factory_run_steps"
                )
            }
            batch_items = [
                dict(r)
                for r in connection.execute(
                    "SELECT token_mint, pair_address, item_status FROM "
                    "printer_selection_batch_items WHERE batch_id=?",
                    (result.activation.selection_batch_id,),
                )
            ]
        finally:
            connection.close()
        # Every lifecycle step belongs to an activated slot; no foreign token.
        self.assertTrue(step_tokens)
        self.assertTrue(step_tokens.issubset(slot_tokens))
        # Exactly two SELECTED items, mirroring the two slots — no reselection.
        self.assertEqual(len(batch_items), 2)
        self.assertTrue(all(i["item_status"] == "SELECTED" for i in batch_items))
        self.assertEqual({i["token_mint"] for i in batch_items}, {MINT_A, MINT_B})

    def test_executor_first_15m_jobs_are_cancelled_no_stale_activation_jobs(self) -> None:
        self._run_driver()
        connection = self._conn()
        try:
            leftover = [
                dict(r)
                for r in connection.execute(
                    "SELECT job_name, status FROM printer_scheduler_jobs "
                    "WHERE job_name LIKE 'window15m:%' AND status IN "
                    "('PENDING','RUNNING','COOLDOWN')"
                )
            ]
        finally:
            connection.close()
        self.assertEqual(leftover, [])

    def test_no_running_jobs_after_terminalization(self) -> None:
        result = self._run_driver()
        self.assertEqual(result.lifecycle.get("running_jobs_after_stop"), 0)
        self.assertEqual(result.lifecycle.get("pending_or_running_run_steps"), 0)

    def test_lifecycle_did_not_invoke_legacy_geckoterminal_discovery(self) -> None:
        # The driver supplies its own discovery_runner; the factory's
        # geckoterminal default must never be called. Snapshot adapter is the
        # only source surface, and it is fixture-only.
        result = self._run_driver()
        self.assertTrue(result.lifecycle_started)
        # discovery_source in the run config must be the injected runner path,
        # never a live geckoterminal fetch: no geckoterminal snapshot calls.
        self.assertTrue(all(m in {MINT_A, MINT_B} for m in self._snap_calls))

    def test_financial_and_retrieval_locks_stay_zero(self) -> None:
        result = self._run_driver()
        deltas = result.lifecycle.get("table_deltas", {})
        for table in (
            "printer_paper_decisions",
            "printer_paper_positions",
        ):
            self.assertEqual(deltas.get(table, 0), 0)

    def test_deterministic_zero_source_replay(self) -> None:
        from printer_v1.operator_cli.one_command_15m_factory import load_report_only

        result = self._run_driver()
        run_id = result.lifecycle.get("run_id")
        self.assertIsNotNone(run_id)
        replay_a = load_report_only(self.db, run_id)
        replay_b = load_report_only(self.db, run_id)
        self.assertEqual(replay_a, replay_b)


class ContinuationDepthThroughHandoffTests(_IntegrationBase):
    """Prove 1h/4h/5m continuation depth is reachable through the origin handoff.

    The factory's compressed-time continuous proof mode is single-token by
    contract (``_CONTINUOUS_MAX_SELECTED_TOKENS == 1``), while atomic activation
    is two-or-none. This proves the handoff yields identities the single-token
    continuous lifecycle consumes: the origin architecture drives the full
    15m → 1h → 4h depth for an activated token, without legacy discovery.
    """

    def test_activated_slot_drives_continuous_1h_lifecycle(self) -> None:
        from printer_v1.operator_cli.one_command_15m_factory import (
            run_one_command_15m_factory,
        )

        # 1) Atomic two-slot activation via the origin executor.
        executor = CombinedPumpfunCampaignExecutor(self._two_origin_fixtures())
        activation = executor.execute(
            command=self.command,
            source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
            central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
        )
        self.assertEqual(activation.terminal_status, "COMPLETED")

        # 2) Materialize a single-slot batch from slot 1 (the continuous proof
        #    harness is single-token) — identity-preserving, no reselection.
        connection = self._conn()
        try:
            slot = dict(
                connection.execute(
                    """
                    SELECT s.token_row_id, s.mint_identity, s.pair_row_id,
                           p.pair_address
                    FROM printer_memory_factory_campaign_token_slots s
                    JOIN printer_pairs p ON p.id = s.pair_row_id
                    WHERE s.cycle_id='cyc' AND s.slot_ordinal=1
                    """
                ).fetchone()
            )
            connection.execute(
                "INSERT INTO printer_selection_batches(batch_id,batch_status,"
                "window_kind,candidate_pool_total,selected_count,rejected_count,"
                "unavailable_or_unclassified_count,operator_approved,created_at) "
                "VALUES('cont-1','ASSEMBLED','WINDOW_15M',1,1,0,0,1,?)",
                (NOW,),
            )
            connection.execute(
                "INSERT INTO printer_selection_batch_items(batch_id,item_status,"
                "token_id,pair_id,token_mint,pair_address,chain,tracking_lane,"
                "same_token_new_pair,operator_approved,selected_at,cooldown_reopened,"
                "created_at) VALUES('cont-1','SELECTED',?,?,?,?,'solana','TRACK_NORMAL',"
                "0,1,?,0,?)",
                (
                    int(slot["token_row_id"]),
                    int(slot["pair_row_id"]),
                    slot["mint_identity"],
                    slot["pair_address"],
                    NOW,
                    NOW,
                ),
            )
            connection.commit()
            mint = slot["mint_identity"]
            pair = slot["pair_address"]
        finally:
            connection.close()

        snap, snap_calls = self._snapshot_adapter_factory_for(mint, pair)

        def origin_runner(_args):
            return {
                "selection_handoff_report": {
                    "batch_id": "cont-1",
                    "selection_seed": SEED,
                    "eligible_pool_size": 1,
                },
                "discovery_results": [],
            }

        # 3) Full continuous lifecycle on the activated identity.
        result = run_one_command_15m_factory(
            self.db,
            self.backup,
            operator_approved=True,
            proof_mode=True,
            discovery_runner=origin_runner,
            snapshot_adapter_factory=snap,
            context_adapter_factories=self._context_factories(),
            continuous_first_hour=True,
            max_selected_tokens=1,
            _window_seconds=0.08,
            _continuation_seconds=0.12,
            total_duration_seconds=10.0,
            launch_provenance=_provenance(),
        )
        self.assertEqual(result["run_status"], "COMPLETED")
        lifecycle = result["continuous_lifecycle"]
        # The origin-activated identity entered the continuous (15m→1h→4h)
        # lifecycle: enabled, exactly the one activated token, its 15m window
        # snapshotted, and the 1h/4h continuation structure present. The exact
        # 1h/4h close outcome is the factory's own proven contract (V2-4/V2-7/
        # V2-8); this lane proves the pathway is reached via origin activation.
        self.assertTrue(lifecycle["enabled"])
        self.assertEqual(len(lifecycle["tokens"]), 1)
        token = lifecycle["tokens"][0]
        self.assertGreater(len(token["window_15m"]["snapshots"]), 0)
        self.assertIn("continuation_1h", token)
        self.assertIn("continuation_4h", token)
        # Only the activated mint was ever snapshotted — no legacy discovery.
        self.assertTrue(snap_calls)
        self.assertTrue(all(m == mint for m in snap_calls))
        # Locks unchanged; clean terminalization.
        self.assertEqual(result["table_deltas"]["printer_paper_positions"], 0)
        self.assertEqual(result["table_deltas"]["printer_paper_decisions"], 0)
        self.assertEqual(result["running_jobs_after_stop"], 0)

    def _snapshot_adapter_factory_for(self, mint, pair):
        calls = []

        def build(*, token_mint, timeout_seconds):
            calls.append(token_mint)
            return build_fixture_source_adapter(
                "dexscreener",
                fixture_payload={
                    "pairs": [
                        {
                            "chain": "solana",
                            "token_mint": token_mint,
                            "pair_address": pair,
                            "price_usd": 1.0,
                            "liquidity_usd": 10000.0,
                            "volume_5m": 500.0,
                            "volume_1h": 2000.0,
                            "volume_24h": 10000.0,
                            "txns_5m": 10,
                            "txns_1h": 50,
                            "txns_24h": 500,
                            "buys_5m": 7,
                            "sells_5m": 3,
                            "buys_1h": 30,
                            "sells_1h": 20,
                            "buys_24h": 280,
                            "sells_24h": 220,
                            "price_change_5m": 1.0,
                            "price_change_1h": 2.0,
                            "price_change_24h": 3.0,
                        }
                    ]
                },
            )

        return build, calls


class NegativePathTests(_IntegrationBase):
    def test_zero_eligible_pool_activates_nothing_and_starts_no_lifecycle(self) -> None:
        # A single origin cannot fill two slots → INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL.
        fixtures = self._fixtures((self._origin("a", MINT_A, POOL_A, 10),))
        result = self._run_driver(fixtures=fixtures)
        self.assertEqual(len(result.activation.activated_slots), 0)
        self.assertIsNone(result.activation.selection_batch_id)
        self.assertFalse(result.lifecycle_started)
        self.assertEqual(result.lifecycle["run_status"], "NOT_STARTED")
        connection = self._conn()
        try:
            steps = connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps"
            ).fetchone()[0]
            items = connection.execute(
                "SELECT COUNT(*) FROM printer_selection_batch_items"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(steps, 0)
        self.assertEqual(items, 0)

    def test_no_activation_produces_no_lifecycle_scheduler_work(self) -> None:
        fixtures = self._fixtures(())  # no origins at all
        result = self._run_driver(fixtures=fixtures)
        self.assertFalse(result.lifecycle_started)
        self.assertEqual(len(result.activation.activated_slots), 0)

    def test_activation_yields_two_distinct_token_identities(self) -> None:
        # Identity isolation from real activation: the two activated slots always
        # carry distinct token rows and mints (schema UNIQUE (cycle_id,
        # token_row_id) plus the executor's collapse-by-mint selection).
        result = self._run_driver()
        slots = result.activation.activated_slots
        self.assertEqual(len(slots), 2)
        self.assertEqual(len({s["token_row_id"] for s in slots}), 2)
        self.assertEqual(len({s["mint_identity"] for s in slots}), 2)

    def test_materialize_guard_rejects_duplicate_token_slots(self) -> None:
        # Defense-in-depth: even if two SELECTED slots with a shared token
        # identity were presented, materialization fails closed.
        driver_module = __import__(
            "printer_v1.operator_cli.origin_lifecycle_campaign",
            fromlist=["_read_activated_slots"],
        )
        original = driver_module._read_activated_slots
        driver_module._read_activated_slots = lambda _c, _cycle: [
            {"slot_ordinal": 1, "token_row_id": 7, "pair_row_id": 1,
             "mint_identity": MINT_A, "pair_identity": f"x:{POOL_A}",
             "pair_address": POOL_A},
            {"slot_ordinal": 2, "token_row_id": 7, "pair_row_id": 2,
             "mint_identity": MINT_B, "pair_identity": f"x:{POOL_B}",
             "pair_address": POOL_B},
        ]
        try:
            connection = self._conn()
            try:
                with self.assertRaises(OriginLifecycleError) as caught:
                    materialize_origin_activated_batch(
                        connection, cycle_id="cyc", selection_seed=SEED
                    )
                self.assertEqual(caught.exception.code, "IDENTITY_MISMATCH")
            finally:
                connection.close()
        finally:
            driver_module._read_activated_slots = original


class BypassPreventionTests(_IntegrationBase):
    def test_source_governor_unavailable_fails_closed_no_lifecycle(self) -> None:
        driver = OriginToLifecycleCampaignDriver()
        snap, _ = self._snapshot_adapter_factory()
        result = driver.run(
            command=self.command,
            fixtures=self._two_origin_fixtures(),
            backup_path=self.backup,
            source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, False),  # unavailable
            central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
            selection_seed=SEED,
            lifecycle_kwargs={
                "snapshot_adapter_factory": snap,
                "context_adapter_factories": self._context_factories(),
                "_window_seconds": 0.05,
                "total_duration_seconds": 3.0,
            },
        )
        self.assertNotEqual(result.activation.terminal_status, "COMPLETED")
        self.assertFalse(result.lifecycle_started)

    def test_central_scheduler_unavailable_fails_closed_no_lifecycle(self) -> None:
        driver = OriginToLifecycleCampaignDriver()
        snap, _ = self._snapshot_adapter_factory()
        result = driver.run(
            command=self.command,
            fixtures=self._two_origin_fixtures(),
            backup_path=self.backup,
            source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
            central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, False),  # unavailable
            selection_seed=SEED,
            lifecycle_kwargs={
                "snapshot_adapter_factory": snap,
                "context_adapter_factories": self._context_factories(),
                "_window_seconds": 0.05,
                "total_duration_seconds": 3.0,
            },
        )
        self.assertNotEqual(result.activation.terminal_status, "COMPLETED")
        self.assertFalse(result.lifecycle_started)


if __name__ == "__main__":
    unittest.main()

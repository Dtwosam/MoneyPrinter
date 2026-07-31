"""V2-9.8B full-run wiring integration: real factory path + finalize.

Drives the actual ``run_one_command_15m_factory`` (with injected adapters and
the new lifecycle operation observer + ownership context) to two real terminal
WINDOW_15M closes on a disposable database, then runs the real
``finalize_full_run_ownership_and_report`` boundary the coordinator invokes.
No operational command, no authoritative DB, injected transports only.
"""

from __future__ import annotations

from pathlib import Path
import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.campaign_ownership import (
    bind_authoritative_run_id,
    create_campaign_run,
    create_cycle_with_two_slots,
)
from printer_v1.operator_cli.campaign_full_run_accounting import (
    OperationalLifecycleOwnershipContext,
    VERDICT_BLOCKED_UNSAFE,
    VERDICT_PASS,
    build_lifecycle_action_local_observer,
    finalize_full_run_ownership_and_report,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    run_one_command_15m_factory,
)
from printer_v1.sources.campaign_six_unit_accounting import CampaignActionLocalLedger
from printer_v1.sources.governed_execution import (
    FIXTURE_FAILURE,
    build_fixture_source_adapter,
)


NOW = "2026-07-31T00:00:00+00:00"
CAMPAIGN = "campaign-w"
CONFIG = "configuration-w"
RUN = "run-w"
CYCLE = "cycle-w"
TEST_GIT_PROVENANCE = {
    "git_head": "a" * 40,
    "git_tracked_tree_clean": True,
    "git_staged_changes_present": False,
    "git_unstaged_changes_present": False,
    "git_untracked_present": False,
    "git_provenance_captured_at": NOW,
}
MINTS = {1: "mintaaaa1", 2: "mintbbbb2"}
PAIRS = {1: "pairaaaa1", 2: "pairbbbb2"}


class FullRunWiringIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prov = patch(
            "printer_v1.operator_cli.one_command_15m_factory.capture_git_provenance",
            return_value=dict(TEST_GIT_PROVENANCE),
        )
        self._prov.start()
        temp_parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=temp_parent)
        root = Path(self.temp.name)
        self.db = root / "wiring.sqlite3"
        self.backup = root / "wiring.backup.sqlite3"
        apply_migrations(self.db)
        create_campaign(
            self.db, campaign_id=CAMPAIGN, configuration_id=CONFIG,
            configuration={"slots": 2}, launch_provenance=dict(TEST_GIT_PROVENANCE),
            db_mode=DB_MODE_PROOF_ISOLATED, db_target_identity="isolated-w",
            proof_source_db_identity="source-w", policy_version="v2-9.8b",
        )
        self._seed_campaign_graph()
        shutil.copy2(self.db, self.backup)
        self.captured_run_id: str | None = None

    def tearDown(self) -> None:
        self.temp.cleanup()
        self._prov.stop()

    def _seed_campaign_graph(self) -> None:
        conn = sqlite3.connect(self.db)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                for tok in (1, 2):
                    conn.execute(
                        "INSERT INTO printer_tokens(id,token_mint,chain,token_status) "
                        "VALUES (?,?,'solana','TRACK_NORMAL')",
                        (tok, MINTS[tok]),
                    )
                    conn.execute(
                        "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
                        "VALUES (?,?,?,?)",
                        (tok, tok, PAIRS[tok], MINTS[tok]),
                    )
        finally:
            conn.close()
        create_campaign_run(
            sqlite3.connect(self.db), campaign_id=CAMPAIGN, run_id=RUN,
            run_ordinal=1, now=NOW,
        )
        conn = sqlite3.connect(self.db)
        try:
            create_cycle_with_two_slots(
                conn, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
                cycle_ordinal=1, now=NOW,
                slots=[
                    {
                        "token_slot_id": f"slot-{tok}", "slot_ordinal": tok,
                        "token_identity": f"token-{tok}", "token_row_id": tok,
                        "mint_identity": MINTS[tok], "pair_identity": PAIRS[tok],
                        "pair_row_id": tok, "lifecycle_identity": f"lifecycle-{tok}",
                    }
                    for tok in (1, 2)
                ],
            )
        finally:
            conn.close()

    def _discovery_runner(self):
        def run(_args):
            conn = sqlite3.connect(self.db)
            try:
                conn.execute(
                    "INSERT INTO printer_selection_batches(batch_id,batch_status,"
                    "window_kind,candidate_pool_total,selected_count,operator_approved) "
                    "VALUES ('batch-w','ASSEMBLED','WINDOW_15M',2,2,1)"
                )
                for tok in (1, 2):
                    conn.execute(
                        "INSERT INTO printer_selection_batch_items"
                        "(batch_id,item_status,token_id,pair_id,token_mint,pair_address,"
                        "tracking_lane,operator_approved) "
                        "VALUES ('batch-w','SELECTED',?,?,?,?, 'TRACK_NORMAL',1)",
                        (tok, tok, MINTS[tok], PAIRS[tok]),
                    )
                conn.commit()
            finally:
                conn.close()
            return {
                "selection_handoff_report": {
                    "batch_id": "batch-w", "selection_seed": "wiring-seed",
                    "eligible_pool_size": 2,
                },
                "discovery_results": [],
            }
        return run

    def _snapshot_adapter_factory(self):
        def build(*, token_mint, timeout_seconds):
            return build_fixture_source_adapter(
                "dexscreener",
                fixture_payload={"pairs": [{
                    "chain": "solana", "token_mint": token_mint,
                    "pair_address": PAIRS[1] if token_mint == MINTS[1] else PAIRS[2],
                    "price_usd": 1.0, "liquidity_usd": 10000.0, "volume_5m": 500.0,
                    "volume_1h": 2000.0, "volume_24h": 10000.0,
                    "txns_5m": 10, "txns_1h": 50, "txns_24h": 500,
                    "buys_5m": 7, "sells_5m": 3, "buys_1h": 30, "sells_1h": 20,
                    "buys_24h": 280, "sells_24h": 220,
                    "price_change_5m": 1.0, "price_change_1h": 2.0,
                    "price_change_24h": 3.0,
                }]},
            )
        return build

    def _failing_context_factories(self):
        return {
            source: (lambda _s=source, **_k: build_fixture_source_adapter(
                _s, fixture_kind=FIXTURE_FAILURE))
            for source in ("coingecko", "goplus", "jupiter_quote")
        } | {
            "solana_rpc_holder": lambda **_k: build_fixture_source_adapter(
                "solana_rpc", fixture_kind=FIXTURE_FAILURE)
        }

    def _drive_real_factory(self, *, with_observer=True):
        """Drive the real factory to two closes; return raw observed records."""
        raw_records: list[dict] = []

        def capture_run_id(run_id: str) -> None:
            self.captured_run_id = run_id

        result = run_one_command_15m_factory(
            self.db, self.backup, operator_approved=True, proof_mode=True,
            discovery_runner=self._discovery_runner(),
            snapshot_adapter_factory=self._snapshot_adapter_factory(),
            context_adapter_factories=self._failing_context_factories(),
            max_selected_tokens=2, max_source_requests=1,
            _window_seconds=0.08, total_duration_seconds=5.0,
            campaign_id=CAMPAIGN, campaign_run_id=RUN, cycle_id=CYCLE,
            configuration_id=CONFIG,
            factory_run_initialized=capture_run_id,
            lifecycle_ownership_context={
                "campaign_id": CAMPAIGN, "campaign_run_id": RUN, "cycle_id": CYCLE,
            },
            lifecycle_operation_observer=(
                raw_records.append if with_observer else None
            ),
        )
        return result, raw_records

    def _context(self) -> OperationalLifecycleOwnershipContext:
        return OperationalLifecycleOwnershipContext(
            campaign_id=CAMPAIGN, campaign_run_id=RUN, cycle_id=CYCLE,
            configuration_id=CONFIG, factory_run_id=str(self.captured_run_id),
        )

    def _build_action_local(self, context, raw_records) -> CampaignActionLocalLedger:
        ledger = CampaignActionLocalLedger(
            campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE, lifecycle_started=True,
        )
        observe = build_lifecycle_action_local_observer(context, ledger)
        for record in raw_records:
            observe(record)
        return ledger

    def _bind_and_finalize(self, context, ledger):
        conn = sqlite3.connect(self.db)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            bind_authoritative_run_id(
                conn, campaign_run_id=RUN,
                factory_run_id=str(self.captured_run_id), now=NOW,
            )
        except Exception:
            pass  # factory may already have bound it
        try:
            return finalize_full_run_ownership_and_report(
                conn, context=context, action_local=ledger, execution_id="exec-w",
                supervision_id=1, launch_git_provenance=dict(TEST_GIT_PROVENANCE),
                db_target_identity="isolated-w",
                authorized_invocation_count=1,
                runtime_terminal_status="TERMINAL_COMPLETED",
                lease_released=True,
                forbidden_capability_deltas={
                    "retrieval_queries": 0, "paper_decisions": 0, "paper_trades": 0,
                },
                now=NOW,
            )
        finally:
            conn.close()

    # -- tests ------------------------------------------------------------ #
    def test_real_factory_completes_two_closes_and_fires_observer(self) -> None:
        result, raw_records = self._drive_real_factory()
        self.assertEqual(result["run_status"], "COMPLETED")
        self.assertIsNotNone(self.captured_run_id)
        # The observer fired at both real boundaries: the scheduler-enqueue
        # boundary and the actual measured source-transport boundary, for both
        # tokens.
        self.assertTrue(raw_records)
        boundaries = {r["boundary"] for r in raw_records}
        self.assertEqual(boundaries, {"SCHEDULER_ENQUEUE", "SOURCE_TRANSPORT"})
        self.assertTrue(
            any(r["boundary"] == "SOURCE_TRANSPORT" and r.get("source_request_id")
                for r in raw_records)
        )
        self.assertEqual({r["token_id"] for r in raw_records}, {1, 2})
        conn = sqlite3.connect(self.db)
        try:
            closes = conn.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
                "WHERE run_id=? AND step_kind='WINDOW_CLOSE' AND step_status='SUCCEEDED'",
                (self.captured_run_id,),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(closes, 2)

    def test_finalize_registers_two_windows_projects_jobs_and_reconciles(self) -> None:
        _result, raw = self._drive_real_factory()
        context = self._context()
        ledger = self._build_action_local(context, raw)
        outcome = self._bind_and_finalize(context, ledger)

        # 2 exact campaign-owned terminal windows.
        self.assertEqual(len(outcome["registered_windows"]), 2)
        # Every lifecycle scheduler job projected (one row per existing job).
        conn = sqlite3.connect(self.db)
        try:
            owned = conn.execute(
                "SELECT scheduler_job_id, COUNT(*) c FROM "
                "printer_memory_factory_campaign_scheduler_work WHERE campaign_id=? "
                "GROUP BY scheduler_job_id",
                (CAMPAIGN,),
            ).fetchall()
            step_jobs = conn.execute(
                "SELECT COUNT(DISTINCT scheduler_job_id) FROM "
                "printer_memory_factory_run_steps WHERE run_id=? AND "
                "step_kind IN ('SNAPSHOT','WINDOW_CLOSE')",
                (self.captured_run_id,),
            ).fetchone()[0]
            # Both memory windows carry the exact cycle id.
            cycles = conn.execute(
                "SELECT DISTINCT cycle_id FROM printer_memory_windows "
                "WHERE id IN (SELECT memory_window_row_id FROM "
                "printer_memory_factory_campaign_windows WHERE campaign_id=?)",
                (CAMPAIGN,),
            ).fetchall()
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            conn.close()
        self.assertEqual(len(owned), step_jobs)
        self.assertTrue(all(row[1] == 1 for row in owned))
        self.assertEqual([r[0] for r in cycles], [CYCLE])

        # Non-vacuous exact equality (owner sealed vs execution-time action-local).
        recon = outcome["reconciliation"]
        self.assertTrue(recon["equal"], recon["mismatch_reason"])
        self.assertTrue(recon["lifecycle_started"])
        # Report + gate consumed; Campaign PASS separate from runtime COMPLETED.
        self.assertEqual(outcome["verdict"], VERDICT_PASS, outcome["blocked_reasons"])
        self.assertTrue(outcome["campaign_acceptance"]["pass"])
        report = outcome["report"]
        self.assertEqual(
            sorted(report["selection_and_lifecycle"]["terminal_window_ids"]),
            sorted(outcome["registered_windows"]),
        )
        self.assertEqual(report["runtime_terminal_status"], "TERMINAL_COMPLETED")

    def test_pass_blocked_when_action_local_evidence_missing(self) -> None:
        _result, _raw = self._drive_real_factory()
        context = self._context()
        empty_ledger = CampaignActionLocalLedger(
            campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE, lifecycle_started=True,
        )
        outcome = self._bind_and_finalize(context, empty_ledger)
        self.assertNotEqual(outcome["verdict"], VERDICT_PASS)
        self.assertFalse(outcome["reconciliation"]["equal"])
        self.assertFalse(outcome["campaign_acceptance"]["pass"])

    def test_pass_blocked_when_a_scheduler_identity_is_removed(self) -> None:
        _result, raw = self._drive_real_factory()
        context = self._context()
        # Remove one observed enqueue -> action-local misses one identity.
        ledger = self._build_action_local(context, raw[:-1])
        outcome = self._bind_and_finalize(context, ledger)
        self.assertNotEqual(outcome["verdict"], VERDICT_PASS)
        self.assertFalse(outcome["reconciliation"]["equal"])

    def test_factory_run_identity_drift_fails_closed(self) -> None:
        # A pre-bound factory-run id that disagrees with the factory's own run id
        # must fail closed at the lifecycle boundary: the run never COMPLETES and
        # no terminal windows are produced, so Campaign PASS is impossible.
        result = run_one_command_15m_factory(
            self.db, self.backup, operator_approved=True, proof_mode=True,
            discovery_runner=self._discovery_runner(),
            snapshot_adapter_factory=self._snapshot_adapter_factory(),
            context_adapter_factories=self._failing_context_factories(),
            max_selected_tokens=2, _window_seconds=0.08, total_duration_seconds=5.0,
            campaign_id=CAMPAIGN, campaign_run_id=RUN, cycle_id=CYCLE,
            configuration_id=CONFIG,
            lifecycle_ownership_context={
                "campaign_id": CAMPAIGN, "campaign_run_id": RUN, "cycle_id": CYCLE,
                "factory_run_id": "a-different-factory-run",
            },
        )
        self.assertNotEqual(result.get("run_status"), "COMPLETED")
        conn = sqlite3.connect(self.db)
        try:
            closes = conn.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
                "WHERE step_kind='WINDOW_CLOSE' AND step_status='SUCCEEDED'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(closes, 0)

    def test_coordinator_helper_consumes_primitives_and_gates_pass(self) -> None:
        # Drives the exact helper _run_operational_campaign invokes after the
        # factory returns, proving the ordinary coordinator path consumes the
        # full-run primitives (registration, projection, reconcile, report, gate).
        from printer_v1.operator_cli.operational_memory_factory_command import (
            _apply_full_run_campaign_acceptance,
        )
        _result, raw = self._drive_real_factory()
        conn = sqlite3.connect(self.db)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            bind_authoritative_run_id(
                conn, campaign_run_id=RUN,
                factory_run_id=str(self.captured_run_id), now=NOW,
            )
        except Exception:
            pass
        finally:
            conn.close()
        outcome = _apply_full_run_campaign_acceptance(
            db_path=self.db, campaign_id=CAMPAIGN, campaign_run_id=RUN,
            cycle_id=CYCLE, configuration_id=CONFIG,
            factory_run_id=self.captured_run_id, execution_id="exec-w",
            supervision_id=1, launch_git_provenance=dict(TEST_GIT_PROVENANCE),
            db_target_identity="isolated-w", lifecycle_started=True,
            lifecycle_operation_records=raw,
            forbidden_deltas={"retrieval_queries": 0},
        )
        self.assertEqual(outcome["verdict"], VERDICT_PASS, outcome.get("blocked_reasons"))
        self.assertTrue(outcome["campaign_acceptance"]["pass"])
        self.assertEqual(len(outcome["registered_windows"]), 2)

    def test_coordinator_helper_pre_lifecycle_is_honest_blocked(self) -> None:
        from printer_v1.operator_cli.operational_memory_factory_command import (
            _apply_full_run_campaign_acceptance,
        )
        outcome = _apply_full_run_campaign_acceptance(
            db_path=self.db, campaign_id=CAMPAIGN, campaign_run_id=RUN,
            cycle_id=CYCLE, configuration_id=CONFIG, factory_run_id=None,
            execution_id="exec-w", supervision_id=1,
            launch_git_provenance=dict(TEST_GIT_PROVENANCE),
            db_target_identity="isolated-w", lifecycle_started=False,
            lifecycle_operation_records=[], forbidden_deltas={},
        )
        self.assertNotEqual(outcome["verdict"], VERDICT_PASS)
        self.assertFalse(outcome["campaign_acceptance"]["pass"])

    def test_quality_consistency_and_zero_forbidden_deltas(self) -> None:
        _result, raw = self._drive_real_factory()
        context = self._context()
        ledger = self._build_action_local(context, raw)
        outcome = self._bind_and_finalize(context, ledger)
        report = outcome["report"]
        self.assertTrue(report["terminal_safety"]["zero_forbidden_deltas"])
        # Slot terminal disposition preserved COOLDOWN, never MANUAL_REVIEW.
        for disposition in report["selection_and_lifecycle"]["slot_dispositions"]:
            self.assertEqual(disposition["slot_terminal_state"], "COOLDOWN")
        # Retrieval and financial tables untouched by the whole wiring path.
        conn = sqlite3.connect(self.db)
        try:
            for table in (
                "printer_memory_retrieval_queries", "printer_paper_decisions",
                "printer_paper_positions", "printer_paper_trade_events",
            ):
                self.assertEqual(
                    conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0
                )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()

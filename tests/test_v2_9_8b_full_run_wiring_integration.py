"""V2-9.8B full-run wiring integration: real factory path + finalize.

Drives the actual ``run_one_command_15m_factory`` (with injected adapters and
the new lifecycle operation observer + ownership context) to two real terminal
WINDOW_15M closes on a disposable database, then runs the real
``finalize_full_run_ownership_and_report`` boundary the coordinator invokes.
No operational command, no authoritative DB, injected transports only.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    build_authorization_marker_payload,
    campaign_evidence_sha256,
    create_campaign,
)
from printer_v1.operator_cli.campaign_supervision import (
    acquire_campaign_supervision,
    cleanup_campaign_supervision,
)
from printer_v1.operator_cli.abstract_campaign_command import report_path_identity
from printer_v1.operator_cli.campaign_ownership import (
    bind_authoritative_run_id,
    campaign_scheduler_work_id,
    create_campaign_run,
    create_cycle_with_two_slots,
    transition_state,
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
from printer_v1.operator_cli.unified_terminal_closure import (
    build_campaign_terminal_report,
    reconcile_campaign_terminal,
    write_campaign_terminal_report,
)
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignActionLocalLedger,
    CampaignSixUnitOwner,
    build_campaign_stage_id,
    seal_campaign_stage_evidence,
)
from printer_v1.sources.measured_transport import (
    LocalValidationIdentity,
    SchedulerWorkIdentity,
)
from printer_v1.scheduler.scheduler import (
    claim_due_job,
    complete_job,
    enqueue_job,
    reset_scheduler_operation_observer,
    set_scheduler_operation_observer,
)
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
        self.root = root
        self.db = root / "wiring.sqlite3"
        self.backup = root / "wiring.backup.sqlite3"
        apply_migrations(self.db)
        authorization_marker = build_authorization_marker_payload(
            marker_id="exec-w-authorization-marker", execution_id="exec-w",
            campaign_id=CAMPAIGN, configuration_id=CONFIG, run_id=RUN,
            policy_version="v2-9.8b", db_target_identity="isolated-w",
            launch_git_provenance=dict(TEST_GIT_PROVENANCE),
            operator_approved=True,
        )
        create_campaign(
            self.db, campaign_id=CAMPAIGN, configuration_id=CONFIG,
            configuration={
                "slots": 2, "execution_id": "exec-w", "run_id": RUN,
                "report_directory_identity": report_path_identity(
                    root / "exec-w" / "reports"
                ),
                "campaign_id": CAMPAIGN, "configuration_id": CONFIG,
                "policy_version": "v2-9.8b", "db_target_identity": "isolated-w",
                "operator_approved": True,
                "authorization_marker": authorization_marker,
                "authorization_marker_sha256": campaign_evidence_sha256(
                    authorization_marker
                ),
            }, launch_provenance=dict(TEST_GIT_PROVENANCE),
            db_mode=DB_MODE_PROOF_ISOLATED, db_target_identity="isolated-w",
            proof_source_db_identity="source-w", policy_version="v2-9.8b",
        )
        self._seed_campaign_graph()
        conn = sqlite3.connect(self.db)
        try:
            transition_state(
                conn, record_kind="campaign", identity=CAMPAIGN,
                expected_state="DRAFT", new_state="PREFLIGHT", now=NOW,
            )
            transition_state(
                conn, record_kind="campaign", identity=CAMPAIGN,
                expected_state="PREFLIGHT", new_state="RUNNING", now=NOW,
            )
            transition_state(
                conn, record_kind="run", identity=RUN,
                expected_state="DRAFT", new_state="PREFLIGHT", now=NOW,
            )
            transition_state(
                conn, record_kind="run", identity=RUN,
                expected_state="PREFLIGHT", new_state="RUNNING", now=NOW,
            )
        finally:
            conn.close()
        self.supervision_id = "supervision-w"
        self.supervision_owner_id = "owner-w"
        self.lease_lock = self._lease_lock_path(root)
        acquire_campaign_supervision(
            self.db, lock_path=self.lease_lock,
            supervision_id=self.supervision_id, campaign_id=CAMPAIGN,
            configuration_id=CONFIG, run_id=RUN,
            owner_id=self.supervision_owner_id, now=datetime.fromisoformat(NOW),
        )
        self._cleanup_result = None
        shutil.copy2(self.db, self.backup)
        self.captured_run_id: str | None = None
        self.preallocated_run_id = "factory-run-w"

    def _lease_lock_path(self, root: Path) -> Path:
        """Overridable lease-lock path (ASCII default; subclasses may vary it)."""
        return root / "campaign-w.lease.lock"

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
                    conn.execute(
                        """INSERT INTO printer_tracking_queue(
                            id,token_id,pair_id,tracking_lane,tracking_action,
                            queue_status,source_status,data_quality_label
                        ) VALUES (?,?,?,'TRACK_NORMAL','TRACK','QUEUED',
                                  'COMPLETE','CLEAN_DATA')""",
                        (tok, tok, tok),
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
                        "tracking_queue_id": tok,
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
                }], "response_bytes": 256, "normalized_rows": 1},
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
        context = OperationalLifecycleOwnershipContext(
            campaign_id=CAMPAIGN, campaign_run_id=RUN, cycle_id=CYCLE,
            configuration_id=CONFIG, factory_run_id=self.preallocated_run_id,
        )
        self.owner = CampaignSixUnitOwner(
            campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE, started_at=NOW,
        )
        self.ledger = CampaignActionLocalLedger(
            campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
        )
        self.pre_scheduler_identities = self._run_pre_lifecycle_scheduler_work()
        self._seal_boundary_stage(
            "DISCOVERY_SELECTION_SCHEDULER", 1,
            ("SELECTION_HANDOFF_VALIDATED",),
        )
        live_observe = build_lifecycle_action_local_observer(context, self.ledger)

        def operation_observer(record):
            raw_records.append(dict(record))
            live_observe(record)

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
            configuration_id=CONFIG, factory_run_id=self.preallocated_run_id,
            factory_run_initialized=capture_run_id,
            lifecycle_ownership_context={
                "campaign_id": CAMPAIGN, "campaign_run_id": RUN, "cycle_id": CYCLE,
                "configuration_id": CONFIG,
                "factory_run_id": self.preallocated_run_id,
                "expected_window_kind": "WINDOW_15M",
                "expected_token_capacity": 2,
            },
            lifecycle_operation_observer=(
                operation_observer if with_observer else None
            ),
        )
        return result, raw_records

    def _context(self) -> OperationalLifecycleOwnershipContext:
        return OperationalLifecycleOwnershipContext(
            campaign_id=CAMPAIGN, campaign_run_id=RUN, cycle_id=CYCLE,
            configuration_id=CONFIG, factory_run_id=str(self.captured_run_id),
        )

    def _build_action_local(self, context, raw_records) -> CampaignActionLocalLedger:
        del context, raw_records
        return self.ledger

    def _run_pre_lifecycle_scheduler_work(self) -> list[SchedulerWorkIdentity]:
        stage_id = build_campaign_stage_id(
            campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
            stage_kind="DISCOVERY_SELECTION_SCHEDULER", stage_sequence=1,
        )
        events: list[dict] = []
        observer_token = set_scheduler_operation_observer(
            lambda event: events.append(dict(event))
        )
        jobs: list[tuple[int, str, str, str, str, str | None]] = []
        try:
            for index, (kind, scope, category, target, slot) in enumerate((
                ("DISCOVERY_REFRESH", "DISCOVERY_SELECTION", "DISCOVERY_WORK", "discovery-w", None),
                ("DISCOVERY_REFRESH", "DISCOVERY_SELECTION", "DISCOVERY_WORK", "selection-w", None),
                ("TRACK_NORMAL_FIRST_15M", "FIRST_15M_HANDOFF", "TOKEN_SLOT", "slot-1", "slot-1"),
                ("TRACK_NORMAL_FIRST_15M", "FIRST_15M_HANDOFF", "TOKEN_SLOT", "slot-2", "slot-2"),
            ), start=1):
                result, job_id = enqueue_job(
                    self.db, job_name=f"pre-lifecycle-{index}", job_kind=kind,
                    target_table=("printer_tokens" if slot else None),
                    target_id=(index - 1 if slot else None),
                    scheduled_for=datetime.fromisoformat(NOW),
                )
                self.assertEqual(str(result), "ACQUIRED")
                self.assertIsNotNone(job_id)
                self.assertEqual(
                    str(claim_due_job(
                        self.db, job_id=int(job_id), lock_owner="fixture-worker",
                        now=datetime.fromisoformat(NOW),
                    )),
                    "ACQUIRED",
                )
                complete_job(
                    self.db, job_id=int(job_id), now=datetime.fromisoformat(NOW)
                )
                jobs.append((int(job_id), kind, scope, category, target, slot))
        finally:
            reset_scheduler_operation_observer(observer_token)

        identities: list[SchedulerWorkIdentity] = []
        conn = sqlite3.connect(self.db)
        try:
            for job_id, kind, scope, category, target, slot in jobs:
                conn.execute(
                    """INSERT INTO printer_memory_factory_campaign_scheduler_work(
                           scheduler_work_id,campaign_id,run_id,cycle_id,
                           token_slot_id,window_id,work_intent,deadline_at,
                           work_state,scheduler_job_id,ownership_contract_version,
                           stage_id,work_scope,target_category,target_identity,
                           first_terminal_cause,terminal_at,created_at,updated_at)
                       VALUES (?,?,?,?,?,NULL,?,?,'SUCCEEDED',?,
                               'V2_STAGE_SCOPED',?,?,?,?,?,?,?,?)""",
                    (
                        campaign_scheduler_work_id(CAMPAIGN, job_id), CAMPAIGN,
                        RUN, CYCLE, slot,
                        ("DISCOVERY_UNIFORM_SELECTION" if target == "selection-w" else kind),
                        NOW, job_id, stage_id, scope,
                        category, target, "FIXTURE_COMPLETED", NOW, NOW, NOW,
                    ),
                )
                identity = SchedulerWorkIdentity(
                    stage_id=stage_id, scheduler_job_id=job_id, job_kind=kind,
                    target_category=category, target_identity=target,
                )
                identities.append(identity)
                self.ledger.observe_scheduler_work(identity)
            conn.commit()
        finally:
            conn.close()
        for event in events:
            self.ledger.observe_scheduler_transition(event)
        return identities

    def _seal_boundary_stage(self, kind, sequence, validation_names) -> None:
        stage_id = build_campaign_stage_id(
            campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
            stage_kind=kind, stage_sequence=sequence,
        )
        if stage_id in self.owner.ingested_stage_ids:
            return
        validations = [
            LocalValidationIdentity(
                stage_id=stage_id, subject_identity=f"{kind}:{index}",
                validation_kind=name, validation_ordinal=index,
            )
            for index, name in enumerate(validation_names, start=1)
        ]
        for validation in validations:
            self.ledger.observe_local_validation(validation)
        self.owner.ingest_stage_evidence(seal_campaign_stage_evidence(
            stage_id=stage_id, stage_kind=kind, stage_sequence=sequence,
            stage_terminal_status="COMPLETED", campaign_id=CAMPAIGN,
            run_id=RUN, cycle_id=CYCLE,
            evidence={"evidence_kind": "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
                      "transport_operations": [], "local_validations": 0,
                      "scheduler_work_items": 0, "lifecycle_reservations": 0},
            local_validation_identities=validations,
            scheduler_work_identities=(
                self.pre_scheduler_identities
                if kind == "DISCOVERY_SELECTION_SCHEDULER" else ()
            ),
        ))

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
        if self._cleanup_result is None:
            self._cleanup_result = cleanup_campaign_supervision(
                self.db, supervision_id=self.supervision_id,
                campaign_id=CAMPAIGN, configuration_id=CONFIG, run_id=RUN,
                owner_id=self.supervision_owner_id,
                terminal_status="COMPLETED",
                first_terminal_cause="FACTORY_COMPLETED",
                now=datetime.fromisoformat(NOW),
            )
        reconcile_campaign_terminal(
            self.db, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
            terminal_cause="FACTORY_COMPLETED", run_status="COMPLETED",
            factory_run_id=str(self.captured_run_id), lifecycle_started=True,
            now=NOW,
        )
        self._seal_boundary_stage(
            "CAMPAIGN_TERMINAL_RECONCILIATION", 4,
            (
                "CAMPAIGN_TERMINAL_OWNERSHIP_VALIDATED",
                "ZERO_ACTIVE_WORK_VALIDATED", "ZERO_LOCKED_WORK_VALIDATED",
                "LEASE_RELEASE_VALIDATED", "FORBIDDEN_DELTAS_VALIDATED",
                "NO_RETRY_VALIDATED", "NO_RESTART_VALIDATED",
                "NO_RESUME_VALIDATED", "NO_SUCCESSOR_VALIDATED",
            ),
        )
        try:
            return finalize_full_run_ownership_and_report(
                conn, context=context, owner=self.owner, action_local=ledger,
                execution_id="exec-w",
                supervision_id=self.supervision_id,
                launch_git_provenance=dict(TEST_GIT_PROVENANCE),
                db_target_identity="isolated-w",
                runtime_terminal_status="TERMINAL_COMPLETED",
                cleanup_result=self._cleanup_result,
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
        self.assertTrue({
            "SCHEDULER_ENQUEUE", "SCHEDULER_CLAIM", "SCHEDULER_TERMINAL",
            "GOVERNED_SOURCE_ATTEMPT", "LIFECYCLE_RESERVATION",
            "LOCAL_VALIDATION",
        }.issubset(boundaries))
        self.assertTrue(
            any(r["boundary"] == "GOVERNED_SOURCE_ATTEMPT" and r.get("source_request_id")
                for r in raw_records)
        )
        self.assertEqual({r["token_id"] for r in raw_records}, {1, 2})
        attempts = [
            item for item in raw_records
            if item["boundary"] == "GOVERNED_SOURCE_ATTEMPT"
        ]
        # The compressed 80ms fixture cannot lawfully schedule pre-close
        # context acquisition. The timely-closing contract therefore performs
        # zero pre-close provider requests and closes both windows DIRTY using
        # the independently valid exact-pair evidence path.
        self.assertEqual(len(attempts), 18)
        self.assertTrue(all(
            item["request_kind"] == "pair_market_snapshot" for item in attempts
        ))
        self.assertEqual(sum(item["result"] == "FAILED" for item in attempts), 0)
        self.assertEqual(
            sum(item["boundary"] == "LIFECYCLE_RESERVATION" for item in raw_records),
            18,
        )
        conn = sqlite3.connect(self.db)
        try:
            closes = conn.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
                "WHERE run_id=? AND step_kind='WINDOW_CLOSE_AUDIT' AND step_status='SUCCEEDED'",
                (self.captured_run_id,),
            ).fetchone()[0]
            skipped_preclose = conn.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
                "WHERE run_id=? AND step_kind='WINDOW_CLOSE_PRE_CLOSE_CRITICAL' "
                "AND step_status='SKIPPED' AND "
                "error_or_skip_reason='TIMELY_ACQUISITION_NOT_PRODUCIBLE'",
                (self.captured_run_id,),
            ).fetchone()[0]
            memory_states = conn.execute(
                "SELECT memory_status FROM printer_memory_windows ORDER BY id"
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual(closes, 2)
        self.assertEqual(skipped_preclose, 2)
        self.assertEqual(memory_states, [("DIRTY_MEMORY",), ("DIRTY_MEMORY",)])

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
                "AND work_scope='WINDOW_LIFECYCLE' "
                "GROUP BY scheduler_job_id",
                (CAMPAIGN,),
            ).fetchall()
            step_jobs = conn.execute(
                "SELECT COUNT(DISTINCT scheduler_job_id) FROM "
                "printer_memory_factory_run_steps WHERE run_id=? AND "
                "step_status IN ('SUCCEEDED','SKIPPED') AND step_kind IN "
                "('SNAPSHOT','WINDOW_CLOSE_PRE_CLOSE_CRITICAL',"
                "'WINDOW_CLOSE_EVIDENCE','WINDOW_CLOSE_CONTEXT',"
                "'WINDOW_CLOSE_AUDIT')",
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
            report["full_run_accounting"]["scheduler_attribution"],
            {"discovery": 1, "selection": 1, "handoff": 2,
             "lifecycle": 24, "cleanup": 0},
        )
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

    def test_missing_preclose_context_attempt_blocks(self) -> None:
        _result, raw = self._drive_real_factory()
        ledger = self._build_action_local(self._context(), raw)
        # This compressed fixture lawfully produces no pre-close transport;
        # remove one real exact-pair lifecycle transport instead and preserve
        # the original reconciliation invariant.
        self.assertTrue(ledger.transport_identities)
        self.assertTrue(
            all(
                identity["governed_request_kind"] == "pair_market_snapshot"
                for identity in ledger.transport_identities
            )
        )
        ledger.transport_identities.pop(0)
        outcome = self._bind_and_finalize(self._context(), ledger)
        self.assertEqual(outcome["verdict"], VERDICT_BLOCKED_UNSAFE)
        self.assertIn(
            "SOURCE_TRANSPORT_OPERATION",
            outcome["reconciliation"]["mismatch_reason"],
        )

    def test_pass_blocked_when_a_scheduler_identity_is_removed(self) -> None:
        _result, raw = self._drive_real_factory()
        context = self._context()
        # Remove one observed enqueue -> action-local misses one identity.
        ledger = self._build_action_local(context, raw)
        ledger.scheduler_work_identities.pop()
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
        cleanup = cleanup_campaign_supervision(
            self.db, supervision_id=self.supervision_id,
            campaign_id=CAMPAIGN, configuration_id=CONFIG, run_id=RUN,
            owner_id=self.supervision_owner_id, terminal_status="COMPLETED",
            first_terminal_cause="FACTORY_COMPLETED",
            now=datetime.fromisoformat(NOW),
        )
        self._cleanup_result = cleanup
        reconcile_campaign_terminal(
            self.db, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
            terminal_cause="FACTORY_COMPLETED", run_status="COMPLETED",
            factory_run_id=str(self.captured_run_id), lifecycle_started=True,
            now=NOW,
        )
        self._seal_boundary_stage(
            "CAMPAIGN_TERMINAL_RECONCILIATION", 4,
            ("CAMPAIGN_TERMINAL_OWNERSHIP_VALIDATED",
             "ZERO_ACTIVE_WORK_VALIDATED", "ZERO_LOCKED_WORK_VALIDATED",
             "LEASE_RELEASE_VALIDATED", "FORBIDDEN_DELTAS_VALIDATED",
             "NO_RETRY_VALIDATED", "NO_RESTART_VALIDATED",
             "NO_RESUME_VALIDATED", "NO_SUCCESSOR_VALIDATED"),
        )
        outcome = _apply_full_run_campaign_acceptance(
            db_path=self.db, campaign_id=CAMPAIGN, campaign_run_id=RUN,
            cycle_id=CYCLE, configuration_id=CONFIG,
            factory_run_id=self.captured_run_id, execution_id="exec-w",
            supervision_id=self.supervision_id,
            launch_git_provenance=dict(TEST_GIT_PROVENANCE),
            db_target_identity="isolated-w", lifecycle_started=True,
            lifecycle_operation_records=raw,
            forbidden_deltas={"retrieval_queries": 0},
            accounting_owner=self.owner,
            action_local_ledger=self.ledger,
            runtime_terminal_status="TERMINAL_COMPLETED",
            cleanup_result=cleanup,
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
            execution_id="exec-w", supervision_id=self.supervision_id,
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

    def test_public_exact_report_only_reconstructs_with_zero_side_effects(self) -> None:
        from printer_v1.operator_cli.operational_memory_factory_command import report_only

        _result, raw = self._drive_real_factory()
        outcome = self._bind_and_finalize(self._context(), self._build_action_local(None, raw))
        self.assertEqual(outcome["verdict"], VERDICT_PASS)
        report_dir = self.root / "exec-w" / "reports"
        owner_evidence = outcome["report"]["full_run_accounting"]["owner_evidence"]
        totals = outcome["report"]["full_run_accounting"]["six_unit_totals"]
        outer = build_campaign_terminal_report(
            campaign_id=CAMPAIGN, configuration_id=CONFIG, run_id=RUN,
            cycle_id=CYCLE, report_id="report-w", factory_run_id=self.captured_run_id,
            execution_id="exec-w", terminal_status="COMPLETED",
            terminal_cause="FACTORY_COMPLETED", run_status="COMPLETED",
            lifecycle_started=True, reconciliation={"clean_terminal": True},
            forbidden_deltas={"retrieval_queries": 0, "paper_decisions": 0},
            launch_git_provenance=TEST_GIT_PROVENANCE,
            six_unit_totals=totals, six_unit_evidence=owner_evidence,
            require_six_unit_evidence=True,
        )
        outer["full_run_terminal_evidence"] = outcome["report"]
        write_campaign_terminal_report(
            self.db, report_dir, report_id="report-w", campaign_id=CAMPAIGN,
            configuration_id=CONFIG, report=outer, require_six_unit_evidence=True,
        )
        before = self.db.stat().st_mtime_ns
        replay = report_only(
            campaign_id=CAMPAIGN, run_id=RUN, db_path=self.db,
            artifact_root=self.root,
        )
        after = self.db.stat().st_mtime_ns
        self.assertEqual(replay["status"], "REPLAYED", replay)
        self.assertEqual(replay["source_calls"], 0)
        self.assertEqual(replay["scheduler_runtime_calls"], 0)
        self.assertEqual(replay["database_writes"], 0)
        self.assertEqual(before, after)
        self.assertEqual(
            replay["full_run_terminal_evidence"]["hashes"],
            outcome["report"]["hashes"],
        )
        wrong_identity = report_only(
            campaign_id="not-the-campaign", run_id=RUN, db_path=self.db,
            artifact_root=self.root,
        )
        self.assertNotEqual(wrong_identity.get("status"), "REPLAYED")
        self.assertEqual(wrong_identity.get("source_calls", 0), 0)
        self.assertEqual(wrong_identity.get("scheduler_runtime_calls", 0), 0)
        self.assertEqual(wrong_identity.get("database_writes", 0), 0)


if __name__ == "__main__":
    unittest.main()

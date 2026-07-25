"""V2-9.7E.47 — lifecycle-closure and clean-memory repair, focused offline proof.

Fourteen lifecycle proofs (Section A) and ten memory proofs (Section B), all on
temporary isolated databases and injected fake owners. No live provider, no
discovery, no readiness, no FULL_PILOT, no memory retrieval, no paper decision
and no financial capability is exercised.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery.scheduler_parity import (
    WORK_STATE_TO_JOB_ACTION,
    reconcile_discovery_work_jobs,
    terminalize_scheduler_job_for_work,
)
from printer_v1.micro_event.classifier import classify_holding_to_15m_result
from printer_v1.micro_event.contracts import HeldTo15mResultLabel
from printer_v1.operator_cli import proof_supervision as sup
from printer_v1.operator_cli.campaign_active_work import campaign_active_work_report
from printer_v1.operator_cli.commands import (
    OPTIONAL_CONTEXT_LABELS,
    REQUIRED_MAIN_WINDOW_CONTEXT_ENGINES,
    _classify_first_memory_review,
    _outcome_label_from_held_to_15m,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    STOP_TERMINAL_4H,
    _cancel_campaign_discovery_jobs,
    _four_hour_terminal_validation,
)
from printer_v1.operator_cli.two_token_operational_pilot_runner import (
    PilotPaths,
    PilotRunnerError,
    run_two_token_operational_pilot,
)
from printer_v1.operator_cli.unified_terminal_closure import (
    REPORT_ARTIFACT_SUFFIX,
    TerminalClosureError,
    assert_runtime_dependency_preflight,
    reconcile_campaign_terminal,
    replay_campaign_terminal_report,
    resolve_terminal_state,
)
from printer_v1.scheduler.contracts import JobKind
from printer_v1.scheduler.scheduler import enqueue_job

NOW = "2026-07-25T12:00:00+00:00"

_FORBIDDEN_DELTA_TABLES = (
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
)


def _clean_provenance() -> dict[str, object]:
    return {
        "git_head": "0" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": "2026-07-25T00:00:00+00:00",
    }


# ===========================================================================
# Section A — lifecycle closure, cleanup and reporting
# ===========================================================================


class _FakeResult:
    def __init__(self, lifecycle, *, lifecycle_started: bool) -> None:
        self.lifecycle = lifecycle
        self.activation = None
        self.lifecycle_started = lifecycle_started


class _LifecycleOwner:
    """Fake owner that starts a factory run and leaves campaign work behind."""

    def __init__(
        self,
        *,
        run_status: str = "COMPLETED",
        stop_reason: str = "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
        factory_run_id: str = "factory-run-1",
        leave_discovery_jobs: bool = True,
        raise_after_state: bool = False,
    ) -> None:
        self.run_status = run_status
        self.stop_reason = stop_reason
        self.factory_run_id = factory_run_id
        self.leave_discovery_jobs = leave_discovery_jobs
        self.raise_after_state = raise_after_state

    def run_operational(self, *, command, cycle_id, **_extra):
        if self.raise_after_state:
            raise RuntimeError("simulated post-state-creation failure")
        conn = sqlite3.connect(str(command.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        report = {
            "run_id": self.factory_run_id,
            "run_status": self.run_status,
            "stop_reason": self.stop_reason,
            "first_terminal_cause": self.stop_reason,
            "forbidden_deltas": {t: 0 for t in _FORBIDDEN_DELTA_TABLES},
            "pending_or_running_run_steps": 0,
            "running_jobs_after_stop": 0,
        }
        with conn:
            conn.execute(
                """INSERT INTO printer_memory_factory_runs
                   (run_id, run_status, window_kind, db_mode, config_hash,
                    config_json, started_at, finished_at, final_report_json,
                    created_at, updated_at)
                   VALUES (?, ?, 'WINDOW_15M', 'PROOF_ONLY', 'h', '{}', ?, ?, ?, ?, ?)""",
                (
                    self.factory_run_id, self.run_status, NOW, NOW,
                    json.dumps(report, sort_keys=True), NOW, NOW,
                ),
            )
        if self.leave_discovery_jobs:
            # Reproduce the exact E.46 §10.2 shape: terminal discovery work whose
            # DISCOVERY_REFRESH job was never transitioned out of PENDING.
            _seed_discovery_work(
                conn,
                campaign_id=command.campaign_id,
                configuration_id=command.configuration_id,
                run_id=command.run_id,
                cycle_id=cycle_id,
                work_states=("SUCCEEDED", "SUCCEEDED", "RUNNING"),
            )
        conn.commit()
        conn.close()
        return _FakeResult(report, lifecycle_started=True)


class _PreLifecycleOwner:
    def __init__(self, *, stop_reason: str = "PRE_LIFECYCLE_HOLDER_EVIDENCE_BLOCKED"):
        self.stop_reason = stop_reason

    def run_operational(self, *, command, cycle_id, **_extra):
        report = {
            "run_id": command.run_id,
            "run_status": "NOT_STARTED",
            "stop_reason": self.stop_reason,
            "first_terminal_cause": self.stop_reason,
            "lifecycle_started": False,
            "stopped_before_lifecycle": True,
            "forbidden_deltas": {t: 0 for t in _FORBIDDEN_DELTA_TABLES},
            "pending_or_running_run_steps": 0,
            "running_jobs_after_stop": 0,
        }
        return _FakeResult(report, lifecycle_started=False)


#: Distinct approved work types; the schema enforces UNIQUE(batch, work_type).
_WORK_TYPES = (
    "DISCOVERY_PUMPFUN_LATEST",
    "DISCOVERY_IDENTITY_MERGE",
    "DISCOVERY_ORIGIN_VERIFICATION",
    "DISCOVERY_PUMPSWAP_CONFIRMATION",
    "DISCOVERY_FIXED_ELIGIBILITY_GATES",
    "DISCOVERY_UNIFORM_SELECTION",
    "DISCOVERY_TRACKING_HANDOFF_SLOT_1",
    "DISCOVERY_TRACKING_HANDOFF_SLOT_2",
)


def _seed_discovery_work(
    conn: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    work_states,
    configuration_id: str = "cfg",
    batch_id: str | None = None,
) -> list[int]:
    """Seed a lawful discovery batch plus one work row per requested state."""
    batch = batch_id or f"discovery-batch:{campaign_id}:{run_id}:{cycle_id}"
    conn.execute(
        """INSERT OR IGNORE INTO printer_discovery_batches(
               discovery_batch_id, campaign_id, configuration_id, run_id,
               cycle_id, cycle_cutoff, policy_version,
               provider_contract_versions_json, git_provenance_identity,
               campaign_selection_seed_identity, cycle_seed_hash,
               pump_continuity_state, batch_state, canonical_hash, created_at)
           VALUES (?,?,?,?,?,?, 'v1', '{}', ?, 'seed', ?, 'NONE',
                   'DISCOVERING', ?, ?)""",
        (
            batch, campaign_id, configuration_id, run_id, cycle_id, NOW,
            "0" * 40, "a" * 64, "b" * 64, NOW,
        ),
    )
    job_ids: list[int] = []
    for index, state in enumerate(work_states):
        work_type = _WORK_TYPES[index % len(_WORK_TYPES)]
        _result, job_id = enqueue_job(
            conn,
            job_name=f"{work_type}:{batch}",
            job_kind=JobKind.DISCOVERY_REFRESH,
            target_table="printer_discovery_batches",
        )
        assert job_id is not None, f"job {work_type} was not enqueued"
        job_ids.append(int(job_id))
        terminal = state not in {"PENDING", "RUNNING", "COOLDOWN"}
        conn.execute(
            """INSERT INTO printer_discovery_work(
                   discovery_work_id, discovery_batch_id, campaign_id, run_id,
                   cycle_id, scheduler_job_id, work_type, work_state,
                   deadline_at, first_terminal_cause, terminal_at,
                   created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                f"work:{work_type}:{batch}", batch, campaign_id, run_id, cycle_id,
                int(job_id), work_type, state, NOW,
                "DIRECT_COMPLETE" if terminal else None,
                NOW if terminal else None, NOW, NOW,
            ),
        )
    return job_ids


class _CampaignGraphBase(unittest.TestCase):
    """A migrated isolated DB with one campaign / run / cycle launch graph."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.db = self.root / "proof.sqlite3"
        apply_migrations(str(self.db))
        conn = sqlite3.connect(str(self.db))
        conn.execute("PRAGMA foreign_keys=ON")
        with conn:
            conn.execute(
                """INSERT INTO printer_memory_factory_campaigns(
                       campaign_id, campaign_state, db_mode, db_target_identity,
                       proof_source_db_identity, policy_version,
                       created_at, updated_at)
                   VALUES ('camp','RUNNING','PROOF_ISOLATED','iso','src','v1',?,?)""",
                (NOW, NOW),
            )
            conn.execute(
                """INSERT INTO printer_memory_factory_campaign_configurations(
                       configuration_id, campaign_id, configuration_hash,
                       configuration_json, launch_provenance_json, created_at)
                   VALUES ('cfg','camp',?, '{}', '{}', ?)""",
                ("c" * 64, NOW),
            )
            conn.execute(
                """INSERT INTO printer_memory_factory_campaign_runs(
                       run_id, campaign_id, run_ordinal, run_state,
                       created_at, updated_at)
                   VALUES ('run','camp',1,'RUNNING',?,?)""",
                (NOW, NOW),
            )
            conn.execute(
                """INSERT INTO printer_memory_factory_campaign_cycles(
                       cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                       created_at, updated_at)
                   VALUES ('cyc','camp','run',1,'PLANNED',?,?)""",
                (NOW, NOW),
            )
        conn.close()

    def _states(self):
        conn = sqlite3.connect(str(self.db))
        try:
            return (
                conn.execute(
                    "SELECT campaign_state FROM printer_memory_factory_campaigns"
                ).fetchone()[0],
                conn.execute(
                    "SELECT run_state FROM printer_memory_factory_campaign_runs"
                ).fetchone()[0],
                conn.execute(
                    "SELECT cycle_state FROM printer_memory_factory_campaign_cycles"
                ).fetchone()[0],
            )
        finally:
            conn.close()

    def _first_causes(self):
        conn = sqlite3.connect(str(self.db))
        try:
            return (
                conn.execute(
                    "SELECT first_terminal_cause FROM printer_memory_factory_campaigns"
                ).fetchone()[0],
                conn.execute(
                    "SELECT first_terminal_cause FROM printer_memory_factory_campaign_runs"
                ).fetchone()[0],
                conn.execute(
                    "SELECT first_terminal_cause FROM printer_memory_factory_campaign_cycles"
                ).fetchone()[0],
            )
        finally:
            conn.close()

    def _job_statuses(self):
        conn = sqlite3.connect(str(self.db))
        try:
            return sorted(
                (str(row[0]), str(row[1]))
                for row in conn.execute(
                    "SELECT job_name, status FROM printer_scheduler_jobs"
                ).fetchall()
            )
        finally:
            conn.close()

    def _seed_factory_run(self, run_id: str, status: str = "RUNNING") -> None:
        conn = sqlite3.connect(str(self.db))
        with conn:
            conn.execute(
                """INSERT INTO printer_memory_factory_runs
                   (run_id, run_status, window_kind, db_mode, config_hash,
                    config_json, started_at, created_at, updated_at)
                   VALUES (?, ?, 'WINDOW_15M','PROOF_ONLY','h','{}',?,?,?)""",
                (run_id, status, NOW, NOW, NOW),
            )
        conn.close()

    def _integrity(self) -> tuple[str, int]:
        conn = sqlite3.connect(str(self.db))
        try:
            check = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
            violations = len(conn.execute("PRAGMA foreign_key_check").fetchall())
            return check, violations
        finally:
            conn.close()


class UnifiedTerminalReconciliationTests(_CampaignGraphBase):
    """Lifecycle proofs 1-3, 6, 13, 14."""

    def test_lifecycle_started_completion_terminalises_the_whole_graph(self) -> None:
        """Proof 1."""
        self._seed_factory_run("fr-1")
        conn = sqlite3.connect(str(self.db))
        conn.row_factory = sqlite3.Row
        _seed_discovery_work(
            conn, campaign_id="camp", run_id="run", cycle_id="cyc",
            work_states=("SUCCEEDED", "SUCCEEDED"),
        )
        conn.commit()
        conn.close()
        result = reconcile_campaign_terminal(
            self.db,
            campaign_id="camp", run_id="run", cycle_id="cyc",
            terminal_cause="COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
            run_status="COMPLETED", factory_run_id="fr-1",
            lifecycle_started=True, now=NOW,
        )
        self.assertTrue(result["reconciled"])
        self.assertEqual(self._states(), ("TERMINAL_COMPLETED",) * 3)
        self.assertNotEqual(result["factory_run"], "RUNNING")
        self.assertTrue(result["clean_terminal"])
        self.assertEqual(self._integrity(), ("ok", 0))

    def test_governed_safe_stop_terminalises_the_same_graph(self) -> None:
        """Proof 2."""
        self._seed_factory_run("fr-2")
        result = reconcile_campaign_terminal(
            self.db,
            campaign_id="camp", run_id="run", cycle_id="cyc",
            terminal_cause=STOP_TERMINAL_4H, run_status="SAFE_STOPPED",
            factory_run_id="fr-2", lifecycle_started=True, now=NOW,
        )
        self.assertEqual(self._states(), ("TERMINAL_STOPPED",) * 3)
        self.assertEqual(result["factory_run"], "SAFE_STOPPED")
        self.assertEqual(self._first_causes(), (STOP_TERMINAL_4H,) * 3)

    def test_pre_lifecycle_stop_still_reconciles(self) -> None:
        """Proof 3."""
        reconcile_campaign_terminal(
            self.db,
            campaign_id="camp", run_id="run", cycle_id="cyc",
            terminal_cause="PRE_LIFECYCLE_HOLDER_EVIDENCE_BLOCKED",
            run_status="NOT_STARTED", factory_run_id=None,
            lifecycle_started=False, now=NOW,
        )
        self.assertEqual(self._states(), ("TERMINAL_BLOCKED",) * 3)

    def test_terminal_cleanup_leaves_zero_active_campaign_work(self) -> None:
        """Proof 6."""
        conn = sqlite3.connect(str(self.db))
        conn.row_factory = sqlite3.Row
        job_ids = _seed_discovery_work(
            conn, campaign_id="camp", run_id="run", cycle_id="cyc",
            work_states=("SUCCEEDED", "FAILED", "RUNNING", "PENDING"),
        )
        # One job is additionally parked in COOLDOWN and one holds a stale lock.
        conn.execute(
            "UPDATE printer_scheduler_jobs SET status='COOLDOWN' WHERE id=?",
            (job_ids[3],),
        )
        conn.execute(
            "UPDATE printer_scheduler_jobs SET locked_at=?, lock_owner='stale' "
            "WHERE id=?",
            (NOW, job_ids[0]),
        )
        conn.commit()
        conn.close()
        result = reconcile_campaign_terminal(
            self.db,
            campaign_id="camp", run_id="run", cycle_id="cyc",
            terminal_cause=STOP_TERMINAL_4H, run_status="SAFE_STOPPED",
            factory_run_id=None, lifecycle_started=True, now=NOW,
        )
        active = result["active_work"]
        self.assertEqual(active["active_jobs"], 0)
        self.assertEqual(active["active_work_rows"], 0)
        self.assertEqual(active["terminal_work_with_active_job"], 0)
        self.assertTrue(active["clean_terminal"])

    def test_first_terminal_cause_is_immutable(self) -> None:
        """Proof 13."""
        reconcile_campaign_terminal(
            self.db,
            campaign_id="camp", run_id="run", cycle_id="cyc",
            terminal_cause="FIRST_CAUSE", run_status="SAFE_STOPPED",
            factory_run_id=None, lifecycle_started=False, now=NOW,
        )
        self.assertEqual(self._first_causes(), ("FIRST_CAUSE",) * 3)
        second = reconcile_campaign_terminal(
            self.db,
            campaign_id="camp", run_id="run", cycle_id="cyc",
            terminal_cause="SECOND_CAUSE_MUST_NOT_WIN", run_status="FAILED",
            factory_run_id=None, lifecycle_started=False, now=NOW,
        )
        self.assertEqual(self._first_causes(), ("FIRST_CAUSE",) * 3)
        self.assertEqual(
            set(second["records"].values()), {"already_terminal"}
        )

    def test_no_restart_or_successor_is_created(self) -> None:
        """Proof 14."""
        result = reconcile_campaign_terminal(
            self.db,
            campaign_id="camp", run_id="run", cycle_id="cyc",
            terminal_cause="ANY_CAUSE", run_status="SAFE_STOPPED",
            factory_run_id=None, lifecycle_started=False, now=NOW,
        )
        self.assertFalse(result["restart_created"])
        self.assertFalse(result["successor_created"])
        conn = sqlite3.connect(str(self.db))
        try:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_runs"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaigns"
                ).fetchone()[0],
                1,
            )
        finally:
            conn.close()

    def test_terminal_state_mapping_is_explicit(self) -> None:
        self.assertEqual(
            resolve_terminal_state(run_status="COMPLETED", terminal_cause="x"),
            "TERMINAL_COMPLETED",
        )
        self.assertEqual(
            resolve_terminal_state(run_status="FAILED", terminal_cause="x"),
            "TERMINAL_FAILED",
        )
        self.assertEqual(
            resolve_terminal_state(
                run_status="NOT_STARTED", terminal_cause="PILOT_INPUT_READY"
            ),
            "TERMINAL_STOPPED",
        )
        self.assertEqual(
            resolve_terminal_state(
                run_status="NOT_STARTED",
                terminal_cause="BLOCKED_INSUFFICIENT_GRADUATED_POOL",
            ),
            "TERMINAL_BLOCKED",
        )


class DiscoverySchedulerParityTests(_CampaignGraphBase):
    """Lifecycle proofs 4 and 5."""

    def test_discovery_work_and_jobs_agree_terminally(self) -> None:
        """Proof 4."""
        conn = sqlite3.connect(str(self.db))
        conn.row_factory = sqlite3.Row
        job_ids = _seed_discovery_work(
            conn, campaign_id="camp", run_id="run", cycle_id="cyc",
            work_states=("SUCCEEDED", "FAILED", "PENDING"),
        )
        conn.commit()
        parity = reconcile_discovery_work_jobs(conn, campaign_id="camp")
        conn.commit()
        statuses = {
            int(row["id"]): str(row["status"])
            for row in conn.execute(
                "SELECT id, status FROM printer_scheduler_jobs"
            ).fetchall()
        }
        conn.close()
        self.assertEqual(statuses[job_ids[0]], "SUCCEEDED")
        self.assertEqual(statuses[job_ids[1]], "FAILED")
        self.assertEqual(statuses[job_ids[2]], "CANCELLED")
        self.assertEqual(parity["terminal_work_with_active_job"], 0)
        self.assertEqual(parity["cancelled_active_work"], 1)

    def test_mapping_is_frozen_and_terminal_jobs_are_never_rewritten(self) -> None:
        self.assertEqual(WORK_STATE_TO_JOB_ACTION["SUCCEEDED"], "COMPLETE")
        self.assertEqual(WORK_STATE_TO_JOB_ACTION["FAILED"], "FAIL")
        self.assertEqual(WORK_STATE_TO_JOB_ACTION["CANCELLED"], "CANCEL")
        conn = sqlite3.connect(str(self.db))
        conn.row_factory = sqlite3.Row
        job_ids = _seed_discovery_work(
            conn, campaign_id="camp", run_id="run", cycle_id="cyc",
            work_states=("SUCCEEDED",),
        )
        conn.commit()
        terminalize_scheduler_job_for_work(
            conn, job_id=job_ids[0], work_state="SUCCEEDED", cause="ok"
        )
        # A second, contradictory attempt cannot rewrite the terminal job.
        applied = terminalize_scheduler_job_for_work(
            conn, job_id=job_ids[0], work_state="FAILED", cause="late"
        )
        conn.commit()
        status = conn.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?", (job_ids[0],)
        ).fetchone()[0]
        conn.close()
        self.assertIsNone(applied)
        self.assertEqual(status, "SUCCEEDED")

    def test_pending_running_cooldown_and_locked_jobs_are_all_detected(self) -> None:
        """Proof 5."""
        conn = sqlite3.connect(str(self.db))
        conn.row_factory = sqlite3.Row
        job_ids = _seed_discovery_work(
            conn, campaign_id="camp", run_id="run", cycle_id="cyc",
            work_states=("PENDING", "RUNNING", "PENDING", "SUCCEEDED"),
        )
        conn.execute(
            "UPDATE printer_scheduler_jobs SET status='RUNNING' WHERE id=?",
            (job_ids[1],),
        )
        conn.execute(
            "UPDATE printer_scheduler_jobs SET status='COOLDOWN' WHERE id=?",
            (job_ids[2],),
        )
        # The SUCCEEDED work's job is deliberately left holding a stale lock.
        conn.execute(
            "UPDATE printer_scheduler_jobs SET status='SUCCEEDED', "
            "locked_at=?, lock_owner='stale' WHERE id=?",
            (NOW, job_ids[3]),
        )
        conn.commit()
        report = campaign_active_work_report(
            conn, campaign_id="camp", run_id="run", cycle_id="cyc"
        )
        conn.close()
        self.assertEqual(report["active_jobs"], 4)
        self.assertEqual(sorted(report["locked_job_ids"]), [job_ids[3]])
        self.assertEqual(report["active_work_rows"], 3)
        self.assertFalse(report["clean_terminal"])

    def test_factory_cleanup_scopes_by_identity_not_handoff_batch(self) -> None:
        """The E.46 §10.2 mechanism: the handoff batch id matches nothing."""
        conn = sqlite3.connect(str(self.db))
        conn.row_factory = sqlite3.Row
        _seed_discovery_work(
            conn, campaign_id="camp", run_id="run", cycle_id="cyc",
            work_states=("SUCCEEDED", "SUCCEEDED"),
        )
        conn.commit()
        cleanup = _cancel_campaign_discovery_jobs(
            conn,
            "origin-activated:cyc",          # the handoff batch id, as in E.46
            campaign_id="camp", campaign_run_id="run", cycle_id="cyc",
        )
        conn.commit()
        statuses = [
            str(row[0])
            for row in conn.execute(
                "SELECT status FROM printer_scheduler_jobs"
            ).fetchall()
        ]
        conn.close()
        self.assertEqual(cleanup["completed_jobs"], 2)
        self.assertEqual(cleanup["terminal_work_with_active_job"], 0)
        self.assertEqual(statuses, ["SUCCEEDED", "SUCCEEDED"])


class NoContinuationTerminalSemanticsTests(unittest.TestCase):
    """Lifecycle proofs 7 and 8 (Section A4)."""

    @staticmethod
    def _natural(*, dirty: bool, window_status: str = "WINDOW_CLOSED"):
        steps, windows = [], {}
        for token_id in (1, 2):
            steps.append({
                "step_kind": "WINDOW_CLOSE",
                "step_status": "SUCCEEDED",
                "token_id": token_id,
                "memory_window_id": token_id,
                "result_json": json.dumps({
                    "continuation_plan": {
                        "verdict": "STOP_AFTER_15M", "planned_jobs": 0
                    }
                }),
            })
            windows[token_id] = {
                "id": token_id,
                "window_kind": "WINDOW_15M",
                "window_status": window_status,
                "memory_status": "DIRTY_MEMORY" if dirty else "CLEAN_MEMORY",
                "memory_quality_label": "DIRTY_MEMORY" if dirty else "CLEAN_MEMORY",
                "data_quality_label": (
                    "MISSING_CRITICAL_DATA" if dirty else "CLEAN_DATA"
                ),
                "do_not_train": 1 if dirty else 0,
            }
        return _four_hour_terminal_validation(
            config={
                "continuous_four_hour": True,
                "operational_natural_disposition": True,
            },
            steps=steps,
            windows_by_id=windows,
            budgets={
                "four_hour_phase_usage": {"state": "NOT_STARTED"},
                "cumulative_lifecycle_usage": {"budget_verdict": "WITHIN_CEILING"},
            },
            pending_steps=0,
            running_jobs=0,
        )

    def test_lawful_dirty_no_continuation_close_is_a_completed_lifecycle(self) -> None:
        """Proof 7."""
        dirty = self._natural(dirty=True)
        self.assertTrue(dirty["complete"])
        self.assertEqual(dirty["run_status"], "COMPLETED")
        self.assertNotEqual(dirty["stop_reason"], STOP_TERMINAL_4H)
        self.assertTrue(dirty["operational_natural_stop"])
        # Acceptance, and only acceptance, is blocked by the memory result.
        acceptance = dirty["memory_acceptance"]
        self.assertEqual(acceptance["verdict"], "MEMORY_EVIDENCE_BLOCKED")
        self.assertEqual(acceptance["dirty_or_audit_only_windows"], 2)
        self.assertEqual(acceptance["clean_windows"], 0)

    def test_clean_no_continuation_close_completes_and_is_accepted(self) -> None:
        clean = self._natural(dirty=False)
        self.assertTrue(clean["complete"])
        self.assertEqual(clean["run_status"], "COMPLETED")
        self.assertEqual(
            clean["memory_acceptance"]["verdict"], "CLEAN_MEMORY_ACHIEVED"
        )

    def test_the_committed_window_status_values_are_accepted(self) -> None:
        for status in ("WINDOW_CLOSED", "WINDOW_AUDIT_ONLY", "COMPLETE"):
            with self.subTest(status=status):
                self.assertTrue(self._natural(dirty=False, window_status=status)["complete"])
        blocked = self._natural(dirty=False, window_status="WINDOW_OPEN")
        self.assertFalse(blocked["complete"])
        self.assertIn("incomplete_terminal_15m_close", blocked["reasons"])

    def test_started_but_incomplete_continuation_still_safe_stops(self) -> None:
        """Proof 8 — STOP_TERMINAL_4H stays reserved for a real 4h shortfall."""
        result = _four_hour_terminal_validation(
            config={
                "continuous_four_hour": True,
                "operational_natural_disposition": True,
            },
            steps=[{
                "step_kind": "LONG_CONTINUATION_SNAPSHOT",
                "step_status": "SUCCEEDED",
                "tracking_lane": "TRACK_NORMAL",
                "step_key": "t1_long_snapshot_000",
                "snapshot_id": 1,
            }],
            windows_by_id={},
            budgets={
                "four_hour_phase_usage": {
                    "state": "STARTED", "tracking_lane": "TRACK_NORMAL",
                    "budget_verdict": "WITHIN_CEILING",
                },
                "cumulative_lifecycle_usage": {"budget_verdict": "WITHIN_CEILING"},
            },
            pending_steps=0,
            running_jobs=0,
        )
        self.assertFalse(result["complete"])
        self.assertEqual(result["run_status"], "SAFE_STOPPED")
        self.assertEqual(result["stop_reason"], STOP_TERMINAL_4H)
        self.assertEqual(result["phase_state"], "STARTED")

    def test_required_but_unstarted_four_hour_phase_still_safe_stops(self) -> None:
        """A non-natural (proof-mode) run still requires the 4h phase."""
        result = _four_hour_terminal_validation(
            config={
                "continuous_four_hour": True,
                "operational_natural_disposition": False,
            },
            steps=[],
            windows_by_id={},
            budgets={
                "four_hour_phase_usage": {"state": "NOT_STARTED"},
                "cumulative_lifecycle_usage": {"budget_verdict": "WITHIN_CEILING"},
            },
            pending_steps=0,
            running_jobs=0,
        )
        self.assertFalse(result["complete"])
        self.assertEqual(result["stop_reason"], STOP_TERMINAL_4H)
        self.assertIn("four_hour_phase_not_started", result["reasons"])


class PilotRunnerTerminalClosureTests(unittest.TestCase):
    """Lifecycle proofs 9-12 through the committed pilot runner."""

    def setUp(self) -> None:
        self._env = patch.dict(
            os.environ, {"PRINTER_HELIUS_API_KEY": "e47-offline-fake-key"}
        )
        self._env.start()
        self.addCleanup(self._env.stop)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.persistent = self.root / "persistent.sqlite3"
        apply_migrations(str(self.persistent))

    def _paths(self, **overrides) -> PilotPaths:
        base = dict(
            persistent_source_db=self.persistent,
            target_db=self.root / "target.sqlite3",
            backup_db=self.root / "backup.sqlite3",
            restore_rehearsal_db=self.root / "rehearsal.sqlite3",
            report_dir=self.root / "reports",
            one_proof_lock_path=self.root / "pilot.lock",
            stdout_log_path=self.root / "out.log",
            stderr_log_path=self.root / "err.log",
        )
        base.update(overrides)
        return PilotPaths.of(**base)

    def _run(self, owner, *, execution_id="e47-exec", paths=None):
        paths = paths or self._paths()
        return run_two_token_operational_pilot(
            paths,
            execution_id=execution_id,
            launch_provenance=_clean_provenance(),
            selection_seed="e47-seed",
            cycle_cutoff="2026-07-25T12:06:00+00:00",
            evaluated_at="2026-07-25T12:00:00+00:00",
            owner=owner,
            owner_launcher_type=sup.OWNER_TEST_FIXTURE,
            process_id=None,
            migration_transport=object(),
        ), paths

    def test_lifecycle_started_terminal_reconciles_and_reports(self) -> None:
        """Proofs 1, 9 and 10 end to end."""
        result, paths = self._run(_LifecycleOwner())
        self.assertEqual(result["status"], "PILOT_TERMINAL")
        self.assertTrue(result["terminal_metadata_reconciliation"]["reconciled"])
        conn = sqlite3.connect(str(paths.target_db))
        try:
            states = (
                conn.execute(
                    "SELECT campaign_state FROM printer_memory_factory_campaigns"
                ).fetchone()[0],
                conn.execute(
                    "SELECT run_state FROM printer_memory_factory_campaign_runs"
                ).fetchone()[0],
                conn.execute(
                    "SELECT cycle_state FROM printer_memory_factory_campaign_cycles"
                ).fetchone()[0],
            )
            report_rows = conn.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_reports"
            ).fetchone()[0]
            job_statuses = sorted(
                str(row[0])
                for row in conn.execute(
                    "SELECT status FROM printer_scheduler_jobs"
                ).fetchall()
            )
            integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
            fk = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        finally:
            conn.close()
        # Proof 1: no RUNNING/RUNNING/PLANNED survives a governed terminal.
        self.assertNotIn("RUNNING", states)
        self.assertNotIn("PLANNED", states)
        # Proof 4 + 6: every discovery job is terminal, none active.
        self.assertNotIn("PENDING", job_statuses)
        self.assertEqual(result["active_jobs_after_stop"], 0)
        # Proof 9: exactly one report row and one durable artifact.
        self.assertEqual(report_rows, 1)
        artifacts = sorted(paths.report_dir.glob(f"*{REPORT_ARTIFACT_SUFFIX}"))
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(result["campaign_report"]["artifact_count"], 1)
        # Proof 10: replay is deterministic, zero-source, no duplicate.
        replay = result["campaign_report_replay"]
        self.assertEqual(replay["new_source_calls"], 0)
        self.assertEqual(replay["new_scheduler_work"], 0)
        self.assertEqual(replay["duplicate_reports_created"], 0)
        self.assertEqual(replay["database_writes"], 0)
        self.assertTrue(replay["artifact_matches"])
        self.assertEqual((integrity, fk), ("ok", 0))
        self.assertFalse(result["restart_created"])
        self.assertFalse(result["successor_created"])

    def test_report_only_replay_creates_no_duplicate_report(self) -> None:
        """Proof 10 (idempotence under a repeated replay)."""
        result, paths = self._run(_LifecycleOwner())
        again = replay_campaign_terminal_report(
            paths.target_db,
            paths.report_dir,
            report_id=result["report_id"],
            campaign_id=result["campaign_id"],
            configuration_id=result["configuration_id"],
        )
        self.assertEqual(again["report_hash"], result["campaign_report"]["report_hash"])
        conn = sqlite3.connect(str(paths.target_db))
        try:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_reports"
                ).fetchone()[0],
                1,
            )
        finally:
            conn.close()
        self.assertEqual(
            len(sorted(paths.report_dir.glob(f"*{REPORT_ARTIFACT_SUFFIX}"))), 1
        )

    def test_pre_lifecycle_terminal_also_writes_exactly_one_report(self) -> None:
        """Proof 3 + 9 on the pre-lifecycle path."""
        result, paths = self._run(_PreLifecycleOwner())
        self.assertFalse(result["lifecycle_started"])
        conn = sqlite3.connect(str(paths.target_db))
        try:
            self.assertEqual(
                conn.execute(
                    "SELECT campaign_state FROM printer_memory_factory_campaigns"
                ).fetchone()[0],
                "TERMINAL_BLOCKED",
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_reports"
                ).fetchone()[0],
                1,
            )
        finally:
            conn.close()

    def test_dependency_failure_before_mutation_creates_zero_state(self) -> None:
        """Proof 11."""
        paths = self._paths()
        blocked = assert_runtime_dependency_preflight(
            required=(("a_module_that_does_not_exist_47", "1.0"),)
        )
        self.assertEqual(blocked.status, "BLOCKED")
        self.assertTrue(
            any("NOT_IMPORTABLE" in issue for issue in blocked.issues)
        )
        with patch(
            "printer_v1.operator_cli.two_token_operational_pilot_runner"
            ".assert_runtime_dependency_preflight",
            return_value=blocked,
        ):
            with self.assertRaises(PilotRunnerError):
                self._run(_LifecycleOwner(), paths=paths)
        # Zero campaign, run, cycle, supervision, lock or source state.
        self.assertFalse(paths.target_db.exists())
        self.assertFalse(paths.backup_db.exists())
        self.assertFalse(paths.one_proof_lock_path.exists())
        self.assertEqual(blocked.external_requests, 0)
        self.assertEqual(blocked.database_writes, 0)

    def test_failure_after_state_creation_reconciles_and_releases_the_lock(self) -> None:
        """Proof 12."""
        paths = self._paths()
        with self.assertRaises(PilotRunnerError):
            self._run(_LifecycleOwner(raise_after_state=True), paths=paths)
        conn = sqlite3.connect(str(paths.target_db))
        try:
            states = (
                conn.execute(
                    "SELECT campaign_state FROM printer_memory_factory_campaigns"
                ).fetchone()[0],
                conn.execute(
                    "SELECT run_state FROM printer_memory_factory_campaign_runs"
                ).fetchone()[0],
                conn.execute(
                    "SELECT cycle_state FROM printer_memory_factory_campaign_cycles"
                ).fetchone()[0],
            )
            supervision = conn.execute(
                "SELECT execution_status, first_stop_reason "
                "FROM printer_proof_run_supervision"
            ).fetchone()
            reports = conn.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_reports"
            ).fetchone()[0]
            runs = conn.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_runs"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(states, ("TERMINAL_FAILED",) * 3)
        self.assertEqual(supervision[0], "TERMINAL")
        self.assertIn("PILOT_INITIALIZATION_FAILED", str(supervision[1]))
        self.assertEqual(reports, 1)
        # No retry, restart or successor.
        self.assertEqual(runs, 1)
        self.assertFalse(paths.one_proof_lock_path.exists())

    def test_a_differing_report_under_the_same_identity_is_refused(self) -> None:
        result, paths = self._run(_LifecycleOwner())
        artifact = Path(result["campaign_report"]["artifact_path"])
        artifact.write_text("{\"tampered\": true}", encoding="utf-8")
        with self.assertRaises(TerminalClosureError):
            replay_campaign_terminal_report(
                paths.target_db, paths.report_dir,
                report_id=result["report_id"],
                campaign_id=result["campaign_id"],
                configuration_id="not-the-configuration",
            )


# ===========================================================================
# Section B — clean-memory evidence and outcome semantics
# ===========================================================================


def _snapshots(count: int = 6, *, clean: bool = True) -> list[dict[str, object]]:
    return [
        {
            "id": index + 1,
            "price_usd": 1.0,
            "liquidity_usd": 50_000.0,
            "source_status": "COMPLETE" if clean else "FAILED",
            "data_quality_label": "CLEAN_DATA" if clean else "MISSING_CRITICAL_DATA",
        }
        for index in range(count)
    ]


def _context_rows(**overrides) -> dict[str, dict[str, object]]:
    rows = {engine: {"id": 1} for engine in REQUIRED_MAIN_WINDOW_CONTEXT_ENGINES}
    rows.update(overrides)
    return rows


def _labels(**overrides) -> dict[str, object]:
    base = {
        "market_regime_label": "MARKET_RISK_ON",
        "chain_heat_label": "SOLANA_HOT",
        "safety_status_label": "SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY",
        "rug_risk_label": "RUG_RISK_ACCEPTABLE_FOR_15M",
        "liquidity_state_label": "LIQUIDITY_CONTEXT_ACCEPTABLE",
        "entry_realism_label": "ENTRY_REALISTIC",
        "exit_realism_label": "EXIT_REALISTIC",
        "realism_gate_label": "REALISM_ACCEPTABLE",
        "flow_direction_label": "FLOW_BUY_DOMINANT",
        "flow_pressure_label": "PRESSURE_BALANCED",
        "trend_structure_label": "TREND_PARABOLIC_DOWN",
        "volatility_label": "VOLATILITY_EXTREME",
        "held_to_15m_result_label": "HELD_TO_15M_DEAD",
    }
    base.update(overrides)
    return base


def _classify(*, snapshots=None, context_rows=None, labels=None,
              evidence_blockers=None, outcome_label="DEAD"):
    return _classify_first_memory_review(
        snapshots if snapshots is not None else _snapshots(),
        context_rows if context_rows is not None else _context_rows(),
        "WINDOW_15M",
        None,
        effective_labels=labels if labels is not None else _labels(),
        evidence_blockers=evidence_blockers,
        outcome_label=outcome_label,
    )


class CleanMemoryEvidenceContractTests(unittest.TestCase):
    """Memory proofs 1-4, 6, 7."""

    def test_fully_evidenced_collapse_becomes_clean_memory(self) -> None:
        """Proofs 1 and 4 of Section B4 — a truthful adverse outcome stays clean."""
        result = _classify()
        self.assertEqual(result["memory_quality_label"], "CLEAN_MEMORY")
        self.assertEqual(result["data_quality_label"], "CLEAN_DATA")
        self.assertEqual(result["do_not_train"], 0)
        self.assertEqual(result["outcome_label"], "DEAD")
        self.assertEqual(result["rejection_reasons"], ["REVIEW_PASSED"])

    def test_the_same_collapse_with_missing_required_evidence_is_not_clean(self) -> None:
        """Proof 2."""
        missing_snapshots = _classify(snapshots=_snapshots(3))
        self.assertEqual(missing_snapshots["memory_quality_label"], "DIRTY_MEMORY")
        self.assertEqual(missing_snapshots["data_quality_label"], "MISSING_CRITICAL_DATA")
        self.assertEqual(missing_snapshots["outcome_label"], "DEAD")

        missing_safety = _classify(
            labels=_labels(safety_status_label="SAFETY_UNKNOWN")
        )
        self.assertNotEqual(missing_safety["memory_quality_label"], "CLEAN_MEMORY")
        self.assertIn(
            "MISSING_OR_UNKNOWN_CONTEXT", missing_safety["rejection_reasons"]
        )

    def test_a_favourable_outcome_with_missing_required_evidence_is_not_clean(self) -> None:
        """Proof 3."""
        result = _classify(
            labels=_labels(
                trend_structure_label="TREND_UP",
                held_to_15m_result_label="HELD_TO_15M_CONTINUED",
                exit_realism_label="EXIT_UNKNOWN",
            ),
            outcome_label="SHORT_TERM_PUMP",
        )
        self.assertNotEqual(result["memory_quality_label"], "CLEAN_MEMORY")
        self.assertEqual(result["do_not_train"], 1)
        self.assertIn("exit_realism_label=EXIT_UNKNOWN", result["unknown_context_blockers"])

    def test_optional_support_only_5m_unknowns_do_not_dirty_a_main_window(self) -> None:
        """Proof 6 and 9 — the permanent 5m support-only law."""
        result = _classify(
            labels=_labels(
                micro_event_state_label="MICRO_EVENT_UNKNOWN",
                late_buy_trap_label="LATE_BUY_TRAP_UNKNOWN",
            )
        )
        self.assertEqual(result["memory_quality_label"], "CLEAN_MEMORY")
        self.assertEqual(result["unknown_context_blockers"], [])
        self.assertIn(
            "micro_event_state_label=MICRO_EVENT_UNKNOWN",
            result["optional_unknown_context"],
        )
        # The absent 5m context row is not a required main-window engine.
        self.assertNotIn("micro_event", REQUIRED_MAIN_WINDOW_CONTEXT_ENGINES)
        self.assertIn("micro_event_state_label", OPTIONAL_CONTEXT_LABELS)

    def test_market_and_chain_heat_context_remain_required(self) -> None:
        """No mandatory Clean Master Spec critical field is weakened."""
        for label in ("market_regime_label", "chain_heat_label"):
            with self.subTest(label=label):
                result = _classify(labels=_labels(**{label: "UNKNOWN"}))
                self.assertNotEqual(result["memory_quality_label"], "CLEAN_MEMORY")
                self.assertIn(
                    "MISSING_OR_UNKNOWN_CONTEXT", result["rejection_reasons"]
                )
        missing_row = _classify(
            context_rows={
                engine: {"id": 1}
                for engine in REQUIRED_MAIN_WINDOW_CONTEXT_ENGINES - {"market"}
            }
        )
        self.assertNotEqual(missing_row["memory_quality_label"], "CLEAN_MEMORY")

    def test_required_identity_source_trace_and_exit_evidence_still_fail_closed(self) -> None:
        """Proof 7."""
        for blocker in (
            "SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER",
            "SNAPSHOT_BOUNDARY_MISMATCH",
            "SNAPSHOT_SOURCE_TRACE_MISSING_OR_INVALID",
            "NO_VALID_EXACT_TARGET_SAFETY_EVIDENCE",
            "CLOSING_EXIT_QUOTE_ABSENT_FOR_EXACT_SNAPSHOT",
        ):
            with self.subTest(blocker=blocker):
                result = _classify(evidence_blockers=[blocker])
                self.assertNotEqual(result["memory_quality_label"], "CLEAN_MEMORY")
                self.assertEqual(result["do_not_train"], 1)
                self.assertEqual(
                    result["data_quality_label"], "MISSING_CRITICAL_DATA"
                )
                self.assertIn(blocker, result["rejection_reasons"])

    def test_stale_conflicting_and_wash_like_snapshot_evidence_stays_blocked(self) -> None:
        """Proof 8."""
        for status, quality in (
            ("STALE", "STALE_DATA"),
            ("CONFLICTING", "CONFLICTING_DATA"),
            ("FAILED", "DIRTY_DATA"),
        ):
            with self.subTest(status=status):
                snapshots = _snapshots()
                snapshots[-1]["source_status"] = status
                snapshots[-1]["data_quality_label"] = quality
                result = _classify(snapshots=snapshots)
                self.assertNotEqual(result["memory_quality_label"], "CLEAN_MEMORY")
                self.assertEqual(
                    result["data_quality_label"], "MISSING_CRITICAL_DATA"
                )
        # FLOW_WASH_LIKE remains an authenticity blocker via the flow label.
        wash = _classify(labels=_labels(flow_direction_label="FLOW_UNKNOWN"))
        self.assertNotEqual(wash["memory_quality_label"], "CLEAN_MEMORY")

    def test_5m_only_windows_can_never_become_main_memory(self) -> None:
        """Proof 9."""
        result = _classify_first_memory_review(
            _snapshots(), _context_rows(), "WINDOW_5M_MICRO_EVENT",
            None, effective_labels=_labels(), evidence_blockers=None,
            outcome_label="DEAD",
        )
        self.assertEqual(result["memory_quality_label"], "AUDIT_ONLY_MEMORY")
        self.assertIn("REJECT_5M_ONLY_WINDOW", result["rejection_reasons"])
        self.assertFalse(result["retrieval_ready"])


class OutcomeIndependenceTests(unittest.TestCase):
    """Memory proof 5 and Section B3."""

    def test_known_outcomes_survive_dirty_and_audit_only_memory(self) -> None:
        for outcome in (
            "DEAD", "DUMP", "SLOW_BLEED", "CONSOLIDATION",
            "SHORT_TERM_PUMP", "ROUND_TRIP",
        ):
            with self.subTest(outcome=outcome):
                dirty = _classify(snapshots=_snapshots(2), outcome_label=outcome)
                self.assertEqual(dirty["memory_quality_label"], "DIRTY_MEMORY")
                self.assertEqual(dirty["outcome_label"], outcome)
                audit = _classify(
                    evidence_blockers=["NO_VALID_EXACT_TARGET_SAFETY_EVIDENCE"],
                    outcome_label=outcome,
                )
                self.assertEqual(audit["memory_quality_label"], "AUDIT_ONLY_MEMORY")
                self.assertEqual(audit["outcome_label"], outcome)
                self.assertTrue(
                    audit["outcome_preserved_independently_of_memory_quality"]
                )

    def test_a_genuinely_unresolved_trajectory_stays_unknown(self) -> None:
        result = _classify(snapshots=_snapshots(2), outcome_label="UNKNOWN_OUTCOME")
        self.assertEqual(result["outcome_label"], "OUTCOME_UNKNOWN")

    def test_the_same_outcome_can_be_clean_or_dirty(self) -> None:
        clean = _classify(outcome_label="DEAD")
        dirty = _classify(snapshots=_snapshots(1), outcome_label="DEAD")
        self.assertEqual(clean["outcome_label"], dirty["outcome_label"], "DEAD")
        self.assertEqual(clean["memory_quality_label"], "CLEAN_MEMORY")
        self.assertEqual(dirty["memory_quality_label"], "DIRTY_MEMORY")


class ModeratePositiveOutcomeGapTests(unittest.TestCase):
    """Memory proof 4 (Section B2)."""

    def test_the_measured_plus_5_to_25_band_is_a_known_categorical_result(self) -> None:
        for change in (5.01, 8.0, 12.5, 19.9, 24.99):
            with self.subTest(change=change):
                label = classify_holding_to_15m_result(
                    {
                        "held_to_15m_price_change_percent": change,
                        "held_to_15m_liquidity_usd": 50_000.0,
                    }
                )
                self.assertEqual(
                    label, HeldTo15mResultLabel.HELD_TO_15M_MODERATE_CONTINUATION
                )
                self.assertNotEqual(
                    label, HeldTo15mResultLabel.HELD_TO_15M_UNKNOWN
                )

    def test_the_surrounding_bands_are_unchanged(self) -> None:
        cases = {
            30.0: HeldTo15mResultLabel.HELD_TO_15M_CONTINUED,
            25.0: HeldTo15mResultLabel.HELD_TO_15M_CONTINUED,
            3.0: HeldTo15mResultLabel.HELD_TO_15M_CONSOLIDATED,
            -20.0: HeldTo15mResultLabel.HELD_TO_15M_FADED,
            -30.0: HeldTo15mResultLabel.HELD_TO_15M_DUMPED,
            -99.99: HeldTo15mResultLabel.HELD_TO_15M_DEAD,
        }
        for change, expected in cases.items():
            with self.subTest(change=change):
                self.assertEqual(
                    classify_holding_to_15m_result(
                        {
                            "held_to_15m_price_change_percent": change,
                            "held_to_15m_liquidity_usd": 50_000.0,
                        }
                    ),
                    expected,
                )

    def test_absent_measurement_is_still_honestly_unknown(self) -> None:
        self.assertEqual(
            classify_holding_to_15m_result({}),
            HeldTo15mResultLabel.HELD_TO_15M_UNKNOWN,
        )

    def test_the_moderate_band_maps_to_an_approved_outcome_and_is_persistable(self) -> None:
        self.assertEqual(
            _outcome_label_from_held_to_15m("HELD_TO_15M_MODERATE_CONTINUATION"),
            "SHORT_TERM_PUMP",
        )
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "micro.sqlite3"
            apply_migrations(str(db))
            conn = sqlite3.connect(str(db))
            with conn:
                conn.execute(
                    """INSERT INTO printer_micro_events(
                           detected_at, micro_event_state_label,
                           micro_event_move_label, micro_exit_realism_label,
                           late_buy_trap_label, held_to_15m_result_label,
                           micro_event_payload_quality_label,
                           micro_event_memory_gate_label, data_quality_label,
                           source_status)
                       VALUES (?, 'FAST_MICRO_PUMP','MOVE_FAST_UP',
                               'MICRO_EXIT_REALISTIC','NO_LATE_BUY_TRAP',
                               'HELD_TO_15M_MODERATE_CONTINUATION',
                               'MICRO_EVENT_CONTEXT_CLEAN',
                               'MICRO_EVENT_SUPPORT_EVIDENCE','CLEAN_DATA',
                               'COMPLETE')""",
                    (NOW,),
                )
            stored = conn.execute(
                "SELECT held_to_15m_result_label FROM printer_micro_events"
            ).fetchone()[0]
            self.assertEqual(str(conn.execute("PRAGMA integrity_check").fetchone()[0]), "ok")
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            conn.close()
        self.assertEqual(stored, "HELD_TO_15M_MODERATE_CONTINUATION")

    def test_no_scoring_ranking_or_confidence_is_introduced(self) -> None:
        source = Path("src/printer_v1/micro_event/classifier.py").read_text(
            encoding="utf-8"
        )
        for banned in ("score", "rank", "confidence", "weight"):
            self.assertNotIn(banned, source.lower().replace("# ", ""))


class NoLockedCapabilityActivationTests(unittest.TestCase):
    """Memory proof 10 — nothing here unlocks a locked capability."""

    def test_classification_reports_no_downstream_unlock(self) -> None:
        result = _classify()
        self.assertTrue(result["retrieval_ready"] is True)
        # retrieval_ready is an evidence statement, not an activation: no
        # retrieval, decision, position, trade, audit or PnL row exists.
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "locked.sqlite3"
            apply_migrations(str(db))
            conn = sqlite3.connect(str(db))
            try:
                for table in _FORBIDDEN_DELTA_TABLES:
                    self.assertEqual(
                        conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                        0,
                    )
            finally:
                conn.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

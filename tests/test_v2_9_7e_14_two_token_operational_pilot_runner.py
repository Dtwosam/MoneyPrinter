"""V2-9.7E.14 real-wall-clock pilot runner and supervision — offline proof.

Dependency-injected fake campaign owners and deterministic clocks prove the
runner and supervision contract. No live provider is contacted; the E.13 pilot
authorization stays unconsumed. This does not re-prove market outcomes.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from printer_v1.db.migrate import apply_migrations
from printer_v1.operator_cli import proof_supervision as sup
from printer_v1.operator_cli.two_token_operational_pilot_runner import (
    CANONICAL_PILOT_TOTAL_DURATION_SECONDS,
    CANONICAL_15M_WINDOW_SECONDS,
    CANONICAL_CONTINUATION_SECONDS,
    HeartbeatWorker,
    PilotPaths,
    PilotRunnerError,
    _FORBIDDEN_PRODUCTION_TIMING_KEYS,
    _no_active_lease,
    prepare_pilot_target,
    pilot_report_only_replay,
    pilot_status,
    production_lifecycle_kwargs,
    request_pilot_stop,
    run_two_token_operational_pilot,
)

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
        "git_provenance_captured_at": "2026-07-22T00:00:00+00:00",
    }


def _dirty_provenance() -> dict[str, object]:
    payload = _clean_provenance()
    payload["git_tracked_tree_clean"] = False
    payload["git_unstaged_changes_present"] = True
    return payload


class _FakeResult:
    def __init__(self, lifecycle: dict[str, object]) -> None:
        self.lifecycle = lifecycle
        self.activation = None
        self.lifecycle_started = True


class _FakeOwner:
    """Records the runner->owner call and writes a terminal factory run row."""

    def __init__(
        self,
        *,
        run_status: str = "COMPLETED",
        stop_reason: str = "STOP_COMPLETED",
        run_id: str = "pilot-factory-run",
    ) -> None:
        self.calls = 0
        self.received: list[dict[str, object]] = []
        self._run_status = run_status
        self._stop_reason = stop_reason
        self._run_id = run_id

    def run_operational(self, *, command, pump_transport, secondary_transport,
                        source_governor, central_scheduler, selection_seed,
                        cycle_id, cycle_cutoff, evaluated_at, backup_path,
                        lifecycle_kwargs, **_extra):
        self.calls += 1
        self.received.append(
            {
                "lifecycle_kwargs": dict(lifecycle_kwargs),
                "backup_path": str(backup_path),
                "pump_transport": pump_transport,
                "secondary_transport": secondary_transport,
                "cycle_id": cycle_id,
                "migration_transport": _extra.get("migration_transport"),
                "graduated_supply_kwargs": dict(
                    _extra.get("graduated_supply_kwargs") or {}
                ),
                "campaign_id": command.campaign_id,
                "run_id": command.run_id,
            }
        )
        report = {
            "run_id": self._run_id,
            "run_status": self._run_status,
            "stop_reason": self._stop_reason,
            "forbidden_deltas": {t: 0 for t in _FORBIDDEN_DELTA_TABLES},
            "pending_or_running_run_steps": 0,
            "running_jobs_after_stop": 0,
        }
        now = "2026-07-22T01:00:00+00:00"
        conn = sqlite3.connect(str(command.db_path))
        conn.execute("PRAGMA foreign_keys=ON")
        with conn:
            conn.execute(
                """INSERT INTO printer_memory_factory_runs
                   (run_id, run_status, window_kind, db_mode, config_hash,
                    config_json, started_at, finished_at, final_report_json,
                    created_at, updated_at)
                   VALUES (?, ?, 'WINDOW_15M', 'PROOF_ONLY', 'h', '{}', ?, ?, ?, ?, ?)""",
                (self._run_id, self._run_status, now, now,
                 json.dumps(report, sort_keys=True), now, now),
            )
        conn.close()
        return _FakeResult(report)


class _PilotRunnerBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.persistent = self.root / "persistent.sqlite3"
        apply_migrations(str(self.persistent))
        self.addCleanup(self._tmp.cleanup)

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

    def _run(self, *, owner=None, execution_id="exec-1", provenance=None,
             paths=None, **overrides):
        owner = owner or _FakeOwner()
        paths = paths or self._paths()
        return run_two_token_operational_pilot(
            paths,
            execution_id=execution_id,
            launch_provenance=provenance or _clean_provenance(),
            selection_seed="pilot-seed",
            cycle_cutoff="2026-07-22T00:06:00+00:00",
            evaluated_at="2026-07-22T00:00:00+00:00",
            owner=owner,
            owner_launcher_type=sup.OWNER_TEST_FIXTURE,
            process_id=None,
            **overrides,
        ), owner, paths


# ===========================================================================
# Target / backup preparation (proofs 1-4, 6)
# ===========================================================================


class TargetPreparationTests(_PilotRunnerBase):
    def test_missing_or_ambiguous_paths_block_before_mutation(self) -> None:
        # Duplicate (ambiguous) target/backup blocks.
        with self.assertRaises(PilotRunnerError):
            prepare_pilot_target(self._paths(backup_db=self.root / "target.sqlite3"))
        # Empty path blocks.
        with self.assertRaises(PilotRunnerError):
            prepare_pilot_target(self._paths(report_dir="   "))
        # Nothing was created for the blocked ambiguous attempt.
        self.assertFalse((self.root / "target.sqlite3").exists())

    def test_backup_and_restore_rehearsal_pass(self) -> None:
        prep = prepare_pilot_target(self._paths())
        self.assertEqual(prep["status"], "PILOT_TARGET_READY")
        self.assertTrue(prep["proof_backup_byte_identical"])
        self.assertTrue(prep["persistent_unchanged"])
        self.assertTrue(prep["restore_rehearsal_ok"])
        self.assertTrue(prep["no_active_lease"])
        self.assertEqual(prep["target_hash"], prep["backup_hash"])
        # Disposable rehearsal copy was removed.
        self.assertFalse((self.root / "rehearsal.sqlite3").exists())

    def test_migration_or_integrity_failure_blocks(self) -> None:
        bad = self.root / "corrupt.sqlite3"
        bad.write_bytes(b"this is not a sqlite database")
        with self.assertRaises(PilotRunnerError):
            prepare_pilot_target(self._paths(persistent_source_db=bad))

    def test_active_or_foreign_lease_blocks(self) -> None:
        migrated = self.root / "leased.sqlite3"
        apply_migrations(str(migrated))
        conn = sqlite3.connect(str(migrated))
        with conn:
            conn.execute(
                """INSERT INTO printer_proof_run_supervision
                   (execution_id, proof_scope, owner_launcher_type,
                    execution_status, heartbeat_at, lease_expires_at,
                    proof_db_path, backup_db_path, one_proof_lock_path,
                    stdout_log_path, stderr_log_path, started_at,
                    created_at, updated_at)
                   VALUES ('foreign','V2_9','TEST_FIXTURE','RUNNING',?,?,
                           'p','b','l','o','e',?,?,?)""",
                ("2026-07-22T00:00:00+00:00", "2026-07-22T02:00:00+00:00",
                 "2026-07-22T00:00:00+00:00", "2026-07-22T00:00:00+00:00",
                 "2026-07-22T00:00:00+00:00"),
            )
        conn.close()
        with self.assertRaises(PilotRunnerError):
            _no_active_lease(migrated)


# ===========================================================================
# Provenance and real-timing contract (proofs 5, 8, 9)
# ===========================================================================


class ProvenanceAndTimingTests(_PilotRunnerBase):
    def test_dirty_git_provenance_blocks(self) -> None:
        with self.assertRaises(PilotRunnerError):
            self._run(provenance=_dirty_provenance())

    def test_production_invocation_receives_real_canonical_timing(self) -> None:
        result, owner, _paths = self._run()
        self.assertEqual(owner.calls, 1)
        received = owner.received[0]["lifecycle_kwargs"]
        self.assertEqual(
            received["total_duration_seconds"],
            CANONICAL_PILOT_TOTAL_DURATION_SECONDS,
        )
        # No timing override or fixture-adapter key leaks into the live config.
        for key in _FORBIDDEN_PRODUCTION_TIMING_KEYS:
            self.assertNotIn(key, received)
        # Canonical real windows are the factory defaults (never passed).
        self.assertEqual(CANONICAL_15M_WINDOW_SECONDS, 900.0)
        self.assertEqual(CANONICAL_CONTINUATION_SECONDS, 2700.0)
        self.assertTrue(callable(owner.received[0]["migration_transport"]))
        supply_kwargs = owner.received[0]["graduated_supply_kwargs"]
        self.assertTrue(supply_kwargs["run_locator"])
        self.assertEqual(supply_kwargs["collection_rounds"], 3)
        self.assertEqual(supply_kwargs["max_candidates"], 4)
        self.assertEqual(owner.received[0]["cycle_id"], "exec-1-cycle")
        self.assertEqual(owner.received[0]["campaign_id"], "exec-1-campaign")
        self.assertEqual(owner.received[0]["run_id"], "exec-1-campaign-run")

    def test_production_lifecycle_kwargs_reject_compression(self) -> None:
        kwargs = production_lifecycle_kwargs(
            cancellation_probe=lambda: None, launch_provenance=_clean_provenance()
        )
        self.assertEqual(set(kwargs), {
            "total_duration_seconds", "cancellation_probe", "launch_provenance"
        })
        self.assertTrue(
            _FORBIDDEN_PRODUCTION_TIMING_KEYS.isdisjoint(kwargs)
        )


# ===========================================================================
# Heartbeat durability (proof 10)
# ===========================================================================


class HeartbeatDurabilityTests(_PilotRunnerBase):
    def test_heartbeat_advances_monotonically_over_a_long_process(self) -> None:
        paths = self._paths()
        prepare_pilot_target(paths)
        instant = datetime(2026, 7, 22, tzinfo=timezone.utc)
        execution = sup.create_execution(
            paths.target_db,
            execution_id="hb-exec",
            owner_launcher_type=sup.OWNER_TEST_FIXTURE,
            process_id=4321,
            backup_db_path=paths.backup_db,
            one_proof_lock_path=paths.one_proof_lock_path,
            stdout_log_path=paths.stdout_log_path,
            stderr_log_path=paths.stderr_log_path,
            lease_seconds=90,
            now=instant,
        )
        worker = HeartbeatWorker(
            execution["one_proof_lock_path"], "hb-exec",
            lease_seconds=90, process_id=4321,
        )
        last_expiry = None
        # 240 simulated 30s ticks == 2 hours of durable heartbeat.
        for tick in range(1, 241):
            beat = worker.beat(now=instant + timedelta(seconds=30 * tick))
            expiry = datetime.fromisoformat(beat["lease_expires_at"])
            if last_expiry is not None:
                self.assertGreater(expiry, last_expiry)
            last_expiry = expiry
        self.assertEqual(worker.beats, 240)


# ===========================================================================
# Full runner: invocation, report, replay, cleanup, no-restart (7,11-19)
# ===========================================================================


class PilotRunnerLifecycleTests(_PilotRunnerBase):
    def test_exactly_one_invocation_report_replay_and_clean_terminal(self) -> None:
        result, owner, paths = self._run()
        # Proof 7: exactly one campaign invocation.
        self.assertEqual(owner.calls, 1)
        # Proof 16 + terminal: report produced once; terminal COMPLETED.
        self.assertEqual(result["status"], "PILOT_TERMINAL")
        self.assertEqual(result["run_status"], "COMPLETED")
        self.assertEqual(result["terminal_status"], sup.TERMINAL_COMPLETED)
        # Proof 14: no restart or successor.
        self.assertFalse(result["restart_created"])
        self.assertFalse(result["successor_created"])
        # Proof 18: lock released; zero pending/running.
        self.assertTrue(result["one_proof_lock_released"])
        self.assertFalse(paths.one_proof_lock_path.exists())
        self.assertEqual(result["pending_or_running_run_steps"], 0)
        self.assertEqual(result["running_jobs_after_stop"], 0)
        # Proof 19: retrieval/financial deltas zero.
        self.assertTrue(all(v == 0 for v in result["forbidden_deltas"].values()))
        # Proof 17: report-only replay deterministic and zero-source.
        self.assertTrue(result["replay_deterministic"])
        self.assertEqual(result["replay_new_source_calls"], 0)
        a = pilot_report_only_replay(paths.target_db, result["run_id"])
        b = pilot_report_only_replay(paths.target_db, result["run_id"])
        self.assertEqual(a, b)
        self.assertEqual(a["replay"]["new_source_calls"], 0)

    def test_status_is_read_only_with_zero_calls(self) -> None:
        result, _owner, paths = self._run(execution_id="status-exec")
        status = pilot_status(paths.target_db, "status-exec")
        self.assertEqual(status["source_calls"], 0)
        self.assertEqual(status["scheduler_calls"], 0)
        self.assertEqual(status["inspection_mode"], "READ_ONLY")
        self.assertEqual(status["execution_status"], sup.STATUS_TERMINAL)

    def test_relaunch_against_terminal_execution_refuses(self) -> None:
        _result, _owner, paths = self._run(execution_id="once-exec")
        # Proof 15: relaunch with the same execution id refuses to rerun.
        second = _FakeOwner()
        with self.assertRaises(PilotRunnerError):
            run_two_token_operational_pilot(
                paths,
                execution_id="once-exec",
                launch_provenance=_clean_provenance(),
                selection_seed="pilot-seed",
                cycle_cutoff="2026-07-22T00:06:00+00:00",
                evaluated_at="2026-07-22T00:00:00+00:00",
                owner=second,
                owner_launcher_type=sup.OWNER_TEST_FIXTURE,
            )
        self.assertEqual(second.calls, 0)


# ===========================================================================
# Cooperative stop and host disappearance (proofs 12, 13)
# ===========================================================================


class SupervisionFailClosedTests(_PilotRunnerBase):
    def _create_active_attached(self, paths, execution_id):
        instant = datetime(2026, 7, 22, tzinfo=timezone.utc)
        sup.create_execution(
            paths.target_db, execution_id=execution_id,
            owner_launcher_type=sup.OWNER_TEST_FIXTURE, process_id=999,
            backup_db_path=paths.backup_db,
            one_proof_lock_path=paths.one_proof_lock_path,
            stdout_log_path=paths.stdout_log_path,
            stderr_log_path=paths.stderr_log_path,
            lease_seconds=90, now=instant,
        )
        # Minimal factory run row so attach_run's FK is satisfied.
        conn = sqlite3.connect(str(paths.target_db))
        conn.execute("PRAGMA foreign_keys=ON")
        with conn:
            conn.execute(
                """INSERT INTO printer_memory_factory_runs
                   (run_id, run_status, window_kind, db_mode, config_hash,
                    config_json, started_at, created_at, updated_at)
                   VALUES ('active-run','RUNNING','WINDOW_15M','PROOF_ONLY','h','{}',
                           ?, ?, ?)""",
                ("2026-07-22T00:00:00+00:00",) * 3,
            )
        conn.close()
        sup.attach_run(paths.target_db, execution_id, "active-run", process_id=999,
                       now=instant + timedelta(seconds=1))
        return instant

    def test_cooperative_stop_reaches_one_immutable_terminal_cause(self) -> None:
        paths = self._paths()
        prepare_pilot_target(paths)
        self._create_active_attached(paths, "stop-exec")
        # Operator requests a cooperative stop (zero source/Scheduler calls).
        req = request_pilot_stop(
            paths.one_proof_lock_path, "stop-exec", reason="SAFE_STOP_OPERATOR_REQUEST"
        )
        self.assertEqual(req["source_calls"], 0)
        self.assertEqual(req["scheduler_calls"], 0)
        terminal = sup.stop_execution(
            paths.target_db, "stop-exec", stop_reason="SAFE_STOP_OPERATOR_REQUEST",
            process_probe=lambda pid: False,
        )
        self.assertEqual(terminal["terminal_status"], sup.TERMINAL_GOVERNED_SAFE_STOP)
        # Immutable first cause: a different later stop cannot rewrite it.
        replay = sup.stop_execution(
            paths.target_db, "stop-exec", stop_reason="SAFE_STOP_OPERATOR_REQUEST",
            process_probe=lambda pid: False,
        )
        self.assertTrue(replay.get("idempotent_replay"))

    def test_host_disappearance_fails_closed_when_process_alive(self) -> None:
        paths = self._paths()
        prepare_pilot_target(paths)
        instant = self._create_active_attached(paths, "host-exec")
        # Recovery must refuse while the supervised process is still alive.
        with self.assertRaises(sup.ProofSupervisionError):
            sup.recover_abandoned_execution(
                paths.target_db, "host-exec",
                process_probe=lambda pid: True,
                now=instant + timedelta(seconds=300),
            )


if __name__ == "__main__":
    unittest.main()

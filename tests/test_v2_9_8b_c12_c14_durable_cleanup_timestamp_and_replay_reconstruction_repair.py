"""V2-9.8B C12-C14 durable cleanup timestamp + replay reconstruction repair.

Focused, disposable-database proofs for the three repeat-review blockers:

* F1 - initial Campaign PASS and public replay both require a non-empty,
  parseable, timezone-aware durable ``cleanup_completed_at`` and a
  ``lease_released_at`` that never precedes it.
* F2 - creation, acceptance, and report-only replay all compute the
  authorization/invocation marker digests through the single canonical owner
  ``campaign_evidence_sha256`` (so a valid non-ASCII lease-lock path replays).
* F3 - report-only replay independently reconstructs ``factory_config_hash``
  from the exact ``printer_memory_factory_runs`` row rather than copying the
  report-carried value.

Every test uses the real disposable-database wiring fixture; no operational
command, authoritative database, provider, RPC, or WebSocket path runs.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sqlite3
import unittest
from datetime import datetime

from printer_v1.operator_cli.campaign_ownership import bind_authoritative_run_id
from printer_v1.operator_cli.campaign_persistence import campaign_evidence_sha256
from printer_v1.operator_cli.campaign_supervision import (
    build_invocation_marker_payload,
    cleanup_campaign_supervision,
)
from printer_v1.operator_cli.campaign_full_run_accounting import (
    VERDICT_PASS,
    evaluate_campaign_acceptance_gate,
)
from printer_v1.operator_cli.operational_memory_factory_command import report_only
from printer_v1.operator_cli.unified_terminal_closure import (
    build_campaign_terminal_report,
    reconcile_campaign_terminal,
    write_campaign_terminal_report,
)

import test_v2_9_8b_full_run_wiring_integration as _wiring
from test_v2_9_8b_full_run_wiring_integration import (
    CAMPAIGN,
    CONFIG,
    CYCLE,
    NOW,
    RUN,
    TEST_GIT_PROVENANCE,
)


def _replay_canonical(value: object) -> bytes:
    """The owner/action/body local canonical form used by the replay path."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


class _RepairFixtureBase(_wiring.FullRunWiringIntegrationTests):
    """Shared disposable-DB helpers; inherits the real factory wiring setUp."""

    def _drive_bind_and_cleanup(self):
        """Drive the real factory to two closes, bind, and cleanup supervision.

        Cleanup writes the durable ``cleanup_completed_at`` / ``lease_released_at``
        so gate-negative tests can mutate the exact durable row before finalize.
        """
        _result, raw = self._drive_real_factory()
        context = self._context()
        ledger = self._build_action_local(context, raw)
        conn = sqlite3.connect(self.db)
        try:
            bind_authoritative_run_id(
                conn, campaign_run_id=RUN,
                factory_run_id=str(self.captured_run_id), now=NOW,
            )
        except Exception:
            pass
        finally:
            conn.close()
        self._cleanup_result = cleanup_campaign_supervision(
            self.db, supervision_id=self.supervision_id, campaign_id=CAMPAIGN,
            configuration_id=CONFIG, run_id=RUN,
            owner_id=self.supervision_owner_id, terminal_status="COMPLETED",
            first_terminal_cause="FACTORY_COMPLETED",
            now=datetime.fromisoformat(NOW),
        )
        return context, ledger

    def _mutate_supervision(self, assignment: str, params: tuple = ()) -> None:
        conn = sqlite3.connect(self.db)
        try:
            with conn:
                conn.execute(
                    "UPDATE printer_memory_factory_campaign_supervision "
                    f"SET {assignment} WHERE supervision_id=?",
                    (*params, self.supervision_id),
                )
        finally:
            conn.close()

    def _force_durable_cleanup_completed_at(self, value) -> None:
        """Inject a bad durable ``cleanup_completed_at`` on the disposable DB.

        The durable row is genuinely immutable once TERMINAL (a real integrity
        trigger enforces it), so a negative fixture must drop that trigger on
        this throwaway database to construct the corrupt-durable-state scenario.
        """
        conn = sqlite3.connect(self.db)
        try:
            with conn:
                conn.execute(
                    "DROP TRIGGER IF EXISTS "
                    "printer_campaign_supervision_terminal_immutable"
                )
                if value is None:
                    conn.execute(
                        "UPDATE printer_memory_factory_campaign_supervision "
                        "SET cleanup_completed_at=NULL WHERE supervision_id=?",
                        (self.supervision_id,),
                    )
                else:
                    conn.execute(
                        "UPDATE printer_memory_factory_campaign_supervision "
                        "SET cleanup_completed_at=? WHERE supervision_id=?",
                        (value, self.supervision_id),
                    )
        finally:
            conn.close()

    def _store_terminal_report(self, outcome, report=None, *, db_path=None):
        """Attach a full-run report to a durable terminal report + artifact."""
        report = outcome["report"] if report is None else report
        target_db = db_path or self.db
        report_dir = self.root / "exec-w" / "reports"
        owner_evidence = report["full_run_accounting"]["owner_evidence"]
        totals = report["full_run_accounting"]["six_unit_totals"]
        outer = build_campaign_terminal_report(
            campaign_id=CAMPAIGN, configuration_id=CONFIG, run_id=RUN,
            cycle_id=CYCLE, report_id="report-w",
            factory_run_id=self.captured_run_id, execution_id="exec-w",
            terminal_status="COMPLETED", terminal_cause="FACTORY_COMPLETED",
            run_status="COMPLETED", lifecycle_started=True,
            reconciliation={"clean_terminal": True},
            forbidden_deltas={"retrieval_queries": 0, "paper_decisions": 0},
            launch_git_provenance=TEST_GIT_PROVENANCE,
            six_unit_totals=totals, six_unit_evidence=owner_evidence,
            require_six_unit_evidence=True,
        )
        outer["full_run_terminal_evidence"] = report
        write_campaign_terminal_report(
            target_db, report_dir, report_id="report-w", campaign_id=CAMPAIGN,
            configuration_id=CONFIG, report=outer, require_six_unit_evidence=True,
        )
        return report_dir

    def _recompute_body_hash(self, report) -> None:
        """Rebuild ``report_body_sha256`` exactly as the replay path derives it."""
        body = dict(report)
        body_hashes = dict(report.get("hashes") or {})
        body_hashes.pop("report_body_sha256", None)
        body["hashes"] = body_hashes
        report["hashes"]["report_body_sha256"] = hashlib.sha256(
            _replay_canonical(body)
        ).hexdigest()


# The inherited wiring fixture defines its own heavy test_* methods. Null them
# on the repair base so subclasses run only their focused proofs (the wiring
# suite still runs from its own module).
for _name in list(vars(_wiring.FullRunWiringIntegrationTests)):
    if _name.startswith("test_"):
        setattr(_RepairFixtureBase, _name, None)


class DurableCleanupTimestampGateTests(_RepairFixtureBase):
    """F1: initial Campaign PASS requires durable cleanup completion truth."""

    def test_valid_durable_cleanup_and_release_timestamps_pass(self) -> None:
        context, ledger = self._drive_bind_and_cleanup()
        outcome = self._bind_and_finalize(context, ledger)
        self.assertEqual(outcome["verdict"], VERDICT_PASS, outcome["blocked_reasons"])
        safety = outcome["report"]["terminal_safety"]
        self.assertTrue(safety["durable_cleanup_completed_at"])
        self.assertTrue(safety["lease_released_at"])
        checks = outcome["campaign_acceptance"]["checks"]
        self.assertTrue(checks["durable_cleanup_completion_timestamp_present"])
        self.assertTrue(checks["durable_cleanup_and_release_timestamps_valid"])

    def test_null_durable_cleanup_completed_at_blocks(self) -> None:
        # A TERMINAL supervision row cannot durably hold a null
        # cleanup_completed_at (a schema CHECK enforces it), so the code-level
        # gate law is proven directly: a report whose durable cleanup timestamp
        # is null can never reach Campaign PASS.
        context, ledger = self._drive_bind_and_cleanup()
        outcome = self._bind_and_finalize(context, ledger)
        self.assertEqual(outcome["verdict"], VERDICT_PASS, outcome["blocked_reasons"])
        nulled = copy.deepcopy(outcome["report"])
        nulled["terminal_safety"]["durable_cleanup_completed_at"] = None
        gate = evaluate_campaign_acceptance_gate(nulled)
        self.assertFalse(gate["pass"])
        self.assertIn(
            "durable_cleanup_completion_timestamp_present", gate["failing_checks"]
        )
        self.assertIn(
            "durable_cleanup_and_release_timestamps_valid", gate["failing_checks"]
        )

    def _assert_invalid_cleanup_timestamp_blocks(self, value: str) -> None:
        context, ledger = self._drive_bind_and_cleanup()
        self._force_durable_cleanup_completed_at(value)
        outcome = self._bind_and_finalize(context, ledger)
        self.assertNotEqual(outcome["verdict"], VERDICT_PASS)
        checks = outcome["campaign_acceptance"]
        self.assertIn(
            "durable_cleanup_and_release_timestamps_valid",
            checks["failing_checks"],
        )
        # Presence alone is satisfied; only validity blocks.
        self.assertTrue(
            checks["checks"]["durable_cleanup_completion_timestamp_present"]
        )

    def test_malformed_cleanup_timestamp_blocks(self) -> None:
        self._assert_invalid_cleanup_timestamp_blocks("not-a-timestamp")

    def test_timezone_naive_cleanup_timestamp_blocks(self) -> None:
        self._assert_invalid_cleanup_timestamp_blocks("2026-07-31T00:00:00")

    def test_release_before_cleanup_completion_blocks(self) -> None:
        context, ledger = self._drive_bind_and_cleanup()
        # Cleanup completion stays at NOW; release is stamped one day earlier.
        self._mutate_supervision(
            "lease_released_at=?", ("2026-07-30T00:00:00+00:00",)
        )
        outcome = self._bind_and_finalize(context, ledger)
        self.assertNotEqual(outcome["verdict"], VERDICT_PASS)
        self.assertIn(
            "durable_cleanup_and_release_timestamps_valid",
            outcome["campaign_acceptance"]["failing_checks"],
        )


class NonAsciiMarkerReplayTests(_RepairFixtureBase):
    """F2: one canonical marker-hash owner across creation/acceptance/replay."""

    NON_ASCII_LOCK = "campaign-wüö-café.lease.lock"

    def _lease_lock_path(self, root):
        return root / self.NON_ASCII_LOCK

    def test_non_ascii_lease_lock_path_replays_with_identical_digest(self) -> None:
        # The lease-lock path really is non-ASCII, so the two JSON serializers
        # diverge and only the canonical owner keeps creation == replay.
        self.assertTrue(any(ord(ch) > 127 for ch in self.NON_ASCII_LOCK))
        context, ledger = self._drive_bind_and_cleanup()
        outcome = self._bind_and_finalize(context, ledger)
        self.assertEqual(outcome["verdict"], VERDICT_PASS, outcome["blocked_reasons"])

        invocation_marker = outcome["report"]["authorization_and_invocation"][
            "invocation_marker"
        ]
        self.assertIsInstance(invocation_marker, dict)
        self.assertIn(
            self.NON_ASCII_LOCK, str(invocation_marker.get("lease_lock_path"))
        )
        # Creation-time digest recomputed independently from the durable row.
        conn = sqlite3.connect(self.db)
        try:
            row = conn.execute(
                "SELECT * FROM printer_memory_factory_campaign_supervision "
                "WHERE supervision_id=?",
                (self.supervision_id,),
            ).fetchone()
            columns = [d[0] for d in conn.execute(
                "SELECT * FROM printer_memory_factory_campaign_supervision "
                "WHERE supervision_id=?", (self.supervision_id,)
            ).description]
        finally:
            conn.close()
        supervision = dict(zip(columns, row))
        creation_marker = build_invocation_marker_payload(
            supervision, authorization_marker_id="exec-w-authorization-marker",
        )
        creation_digest = campaign_evidence_sha256(creation_marker)
        acceptance_digest = outcome["report"]["hashes"]["invocation_marker_sha256"]
        # creation == acceptance (both via the canonical owner).
        self.assertEqual(creation_digest, acceptance_digest)
        # The rejected replay-local serializer would have produced other bytes.
        legacy_digest = hashlib.sha256(
            _replay_canonical(invocation_marker)
        ).hexdigest()
        self.assertNotEqual(legacy_digest, acceptance_digest)

        # acceptance == replay: report-only recomputes the same digest and
        # returns REPLAYED with zero side effects.
        self._store_terminal_report(outcome)
        before = self.db.stat().st_mtime_ns
        replay = report_only(
            campaign_id=CAMPAIGN, run_id=RUN, db_path=self.db,
            artifact_root=self.root,
        )
        after = self.db.stat().st_mtime_ns
        self.assertEqual(replay["status"], "REPLAYED", replay)
        self.assertEqual(
            replay["full_run_terminal_evidence"]["hashes"][
                "invocation_marker_sha256"
            ],
            acceptance_digest,
        )
        self.assertEqual(replay["source_calls"], 0)
        self.assertEqual(replay["scheduler_runtime_calls"], 0)
        self.assertEqual(replay["database_writes"], 0)
        self.assertEqual(before, after)
        self.assertFalse(self.lease_lock.exists())


class FactoryConfigReplayReconstructionTests(_RepairFixtureBase):
    """F3: replay reconstructs factory_config_hash from its durable owner."""

    def _valid_pass_outcome(self):
        context, ledger = self._drive_bind_and_cleanup()
        outcome = self._bind_and_finalize(context, ledger)
        self.assertEqual(outcome["verdict"], VERDICT_PASS, outcome["blocked_reasons"])
        return outcome

    def test_exact_replay_zero_side_effects_and_unchanged_mtime(self) -> None:
        outcome = self._valid_pass_outcome()
        self._store_terminal_report(outcome)
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

    def test_tampered_report_factory_config_hash_blocks_replay(self) -> None:
        outcome = self._valid_pass_outcome()
        report = copy.deepcopy(outcome["report"])
        real_hash = report["identity"]["factory_config_hash"]
        bogus = hashlib.sha256(b"tampered-factory-config").hexdigest()
        self.assertNotEqual(bogus, real_hash)
        # Change only the report-carried factory config hash in both surfaces.
        report["identity"]["factory_config_hash"] = bogus
        report["authorization_and_invocation"]["factory_config_hash"] = bogus
        # Recompute the body hash so every report/body hash is self-consistent;
        # only the durable factory-run reconstruction can now block.
        self._recompute_body_hash(report)
        self._store_terminal_report(outcome, report=report)
        replay = report_only(
            campaign_id=CAMPAIGN, run_id=RUN, db_path=self.db,
            artifact_root=self.root,
        )
        self.assertEqual(replay["status"], "REPLAY_BLOCKED", replay)
        self.assertEqual(
            replay["block_reason"], "FULL_RUN_DURABLE_RECONSTRUCTION_MISMATCH"
        )
        self.assertEqual(replay["source_calls"], 0)
        self.assertEqual(replay["scheduler_runtime_calls"], 0)
        self.assertEqual(replay["database_writes"], 0)

    def test_missing_factory_run_row_blocks_replay(self) -> None:
        outcome = self._valid_pass_outcome()
        self._store_terminal_report(outcome)
        tampered_db = self.root / "missing-factory-row.sqlite3"
        shutil.copy2(self.db, tampered_db)
        conn = sqlite3.connect(tampered_db)  # FK enforcement off by default
        try:
            with conn:
                conn.execute(
                    "DELETE FROM printer_memory_factory_runs WHERE run_id=?",
                    (str(self.captured_run_id),),
                )
        finally:
            conn.close()
        replay = report_only(
            campaign_id=CAMPAIGN, run_id=RUN, db_path=tampered_db,
            artifact_root=self.root,
        )
        self.assertEqual(replay["status"], "REPLAY_BLOCKED", replay)
        self.assertEqual(
            replay["block_reason"], "FULL_RUN_DURABLE_RECONSTRUCTION_MISMATCH"
        )

    def test_empty_durable_factory_config_hash_blocks_replay(self) -> None:
        # ``config_hash`` is NOT NULL, so the missing-hash scenario is an empty
        # durable value; replay must still fail closed on the empty owner value.
        outcome = self._valid_pass_outcome()
        self._store_terminal_report(outcome)
        tampered_db = self.root / "empty-factory-config.sqlite3"
        shutil.copy2(self.db, tampered_db)
        conn = sqlite3.connect(tampered_db)
        try:
            with conn:
                conn.execute(
                    "UPDATE printer_memory_factory_runs SET config_hash='' "
                    "WHERE run_id=?",
                    (str(self.captured_run_id),),
                )
        finally:
            conn.close()
        replay = report_only(
            campaign_id=CAMPAIGN, run_id=RUN, db_path=tampered_db,
            artifact_root=self.root,
        )
        self.assertEqual(replay["status"], "REPLAY_BLOCKED", replay)
        self.assertEqual(
            replay["block_reason"], "FULL_RUN_DURABLE_RECONSTRUCTION_MISMATCH"
        )


if __name__ == "__main__":
    unittest.main()

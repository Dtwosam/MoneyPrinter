"""Focused C12-C14 authorization, invocation, and lease conformance repair.

Disposable databases and frozen/injected transports only.  These tests drive
the existing immutable campaign-configuration owner, campaign-supervision
acquisition owner, unified cleanup owner, and public read-only replay owner.
"""

from __future__ import annotations

import copy
import sqlite3
import unittest

from printer_v1.operator_cli.campaign_full_run_accounting import (
    VERDICT_PASS,
    evaluate_campaign_acceptance_gate,
    finalize_full_run_ownership_and_report,
)
from printer_v1.operator_cli.operational_memory_factory_command import (
    _apply_full_run_campaign_acceptance,
    report_only,
)
from printer_v1.operator_cli.unified_terminal_closure import (
    build_campaign_terminal_report,
    write_campaign_terminal_report,
)
import test_v2_9_8b_full_run_wiring_integration as _wiring_fixture

from test_v2_9_8b_full_run_wiring_integration import (
    CAMPAIGN,
    CONFIG,
    CYCLE,
    NOW,
    RUN,
    TEST_GIT_PROVENANCE,
)


class C12C14AuthorizationLeaseRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = _wiring_fixture.FullRunWiringIntegrationTests(
            "test_real_factory_completes_two_closes_and_fires_observer"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        _result, self.raw = self.fixture._drive_real_factory()
        self.context = self.fixture._context()
        self.ledger = self.fixture._build_action_local(self.context, self.raw)
        self.outcome = self.fixture._bind_and_finalize(self.context, self.ledger)
        self.assertEqual(
            self.outcome["verdict"], VERDICT_PASS,
            self.outcome.get("campaign_acceptance", {}).get("failing_checks"),
        )

    def _report(self):
        return copy.deepcopy(self.outcome["report"])

    def _gate(self, report):
        return evaluate_campaign_acceptance_gate(report)

    def _finalize_with_cleanup(self, cleanup):
        connection = sqlite3.connect(self.fixture.db)
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            return finalize_full_run_ownership_and_report(
                connection,
                context=self.context,
                owner=self.fixture.owner,
                action_local=self.ledger,
                execution_id="exec-w",
                supervision_id=self.fixture.supervision_id,
                launch_git_provenance=dict(TEST_GIT_PROVENANCE),
                db_target_identity="isolated-w",
                runtime_terminal_status="TERMINAL_COMPLETED",
                cleanup_result=cleanup,
                forbidden_capability_deltas={
                    "retrieval_queries": 0,
                    "paper_decisions": 0,
                    "paper_trades": 0,
                },
                now=NOW,
            )
        finally:
            connection.close()

    def test_omitted_cleanup_and_lease_evidence_blocks(self) -> None:
        outcome = _apply_full_run_campaign_acceptance(
            db_path=self.fixture.db,
            campaign_id=CAMPAIGN,
            campaign_run_id=RUN,
            cycle_id=CYCLE,
            configuration_id=CONFIG,
            factory_run_id=self.fixture.captured_run_id,
            execution_id="exec-w",
            supervision_id=self.fixture.supervision_id,
            launch_git_provenance=dict(TEST_GIT_PROVENANCE),
            db_target_identity="isolated-w",
            lifecycle_started=True,
            lifecycle_operation_records=self.raw,
            forbidden_deltas={"retrieval_queries": 0},
            accounting_owner=self.fixture.owner,
            action_local_ledger=self.ledger,
            runtime_terminal_status="TERMINAL_COMPLETED",
        )
        self.assertNotEqual(outcome["verdict"], VERDICT_PASS)
        self.assertFalse(
            outcome["campaign_acceptance"]["checks"][
                "cleanup_evidence_present_and_exact"
            ]
        )

    def test_none_false_and_non_boolean_lease_release_block(self) -> None:
        for value in (None, False, "true"):
            with self.subTest(value=value):
                cleanup = dict(self.fixture._cleanup_result)
                cleanup["lease_released"] = value
                outcome = self._finalize_with_cleanup(cleanup)
                self.assertNotEqual(outcome["verdict"], VERDICT_PASS)
                self.assertFalse(
                    outcome["campaign_acceptance"]["checks"]["lease_released"]
                )

    def test_real_cleanup_durable_release_and_absent_lock_pass(self) -> None:
        report = self.outcome["report"]
        safety = report["terminal_safety"]
        self.assertIs(safety["cleanup_completed"], True)
        self.assertIs(safety["lease_released"], True)
        self.assertTrue(safety["lease_released_at"])
        self.assertIs(safety["lease_lock_absent"], True)
        self.assertFalse(self.fixture.lease_lock.exists())
        self.assertEqual(self.outcome["verdict"], VERDICT_PASS)

    def test_missing_authorization_marker_blocks(self) -> None:
        report = self._report()
        report["authorization_and_invocation"]["authorization_marker"] = None
        gate = self._gate(report)
        self.assertFalse(gate["checks"]["marker_payload_identities_exact"])
        self.assertNotEqual(gate["verdict"], VERDICT_PASS)

    def test_factory_config_hash_substituted_as_marker_hash_blocks(self) -> None:
        report = self._report()
        report["hashes"]["authorization_marker_sha256"] = report["identity"][
            "factory_config_hash"
        ]
        gate = self._gate(report)
        self.assertFalse(
            gate["checks"]["configuration_hash_not_substituted_as_marker"]
        )

    def test_missing_invocation_marker_blocks(self) -> None:
        report = self._report()
        report["authorization_and_invocation"]["invocation_marker"] = None
        gate = self._gate(report)
        self.assertFalse(gate["checks"]["marker_payload_identities_exact"])
        self.assertNotEqual(gate["verdict"], VERDICT_PASS)

    def test_authorization_counts_zero_and_two_block(self) -> None:
        for count in (0, 2):
            with self.subTest(count=count):
                report = self._report()
                markers = report["authorization_and_invocation"]
                markers["authorization_count"] = count
                markers["exact_authorization_count"] = count
                gate = self._gate(report)
                self.assertFalse(gate["checks"]["exactly_one_authorization_marker"])

    def test_invocation_counts_zero_and_two_block(self) -> None:
        for count in (0, 2):
            with self.subTest(count=count):
                report = self._report()
                report["authorization_and_invocation"]["invocation_count"] = count
                gate = self._gate(report)
                self.assertFalse(
                    gate["checks"]["exactly_one_matching_supervision_invocation"]
                )

    def test_wrong_campaign_run_configuration_supervision_and_owner_block(self) -> None:
        mutations = (
            ("authorization_marker", "campaign_id"),
            ("authorization_marker", "run_id"),
            ("authorization_marker", "configuration_id"),
            ("invocation_marker", "supervision_id"),
            ("invocation_marker", "owner_id"),
        )
        for marker_name, field in mutations:
            with self.subTest(marker=marker_name, field=field):
                report = self._report()
                report["authorization_and_invocation"][marker_name][field] = "wrong"
                gate = self._gate(report)
                self.assertFalse(gate["checks"]["marker_payload_identities_exact"])

    def test_both_marker_digest_mismatches_block(self) -> None:
        for hash_name, check_name in (
            ("authorization_marker_sha256", "authorization_marker_digest_exact"),
            ("invocation_marker_sha256", "invocation_marker_digest_exact"),
        ):
            with self.subTest(hash_name=hash_name):
                report = self._report()
                report["hashes"][hash_name] = "0" * 64
                gate = self._gate(report)
                self.assertFalse(gate["checks"][check_name])

    def test_duplicate_supervision_history_blocks(self) -> None:
        report = self._report()
        markers = report["authorization_and_invocation"]
        markers["supervision_history_count"] = 2
        markers["additional_supervision_history_count"] = 1
        gate = self._gate(report)
        self.assertFalse(gate["checks"]["zero_additional_supervision_history"])

    def test_factory_binding_mismatch_blocks(self) -> None:
        report = self._report()
        markers = report["authorization_and_invocation"]
        markers["factory_binding_count"] = 0
        markers["configuration_supervision_binding_correspondence_exact"] = False
        gate = self._gate(report)
        self.assertFalse(gate["checks"]["exactly_one_matching_factory_binding"])
        self.assertFalse(
            gate["checks"]["authorization_supervision_binding_correspondence_exact"]
        )

    def test_missing_release_timestamp_or_remaining_lock_blocks(self) -> None:
        for field in ("lease_released_at", "lease_lock_absent"):
            with self.subTest(field=field):
                report = self._report()
                report["terminal_safety"][field] = (
                    None if field == "lease_released_at" else False
                )
                gate = self._gate(report)
                self.assertNotEqual(gate["verdict"], VERDICT_PASS)

    def test_historical_or_report_carried_substitute_blocks(self) -> None:
        report = self._report()
        markers = report["authorization_and_invocation"]
        markers["authorization_marker"] = {
            "historical_v1_authorization": True,
            "report_carried_hash": report["hashes"]["authorization_marker_sha256"],
        }
        gate = self._gate(report)
        self.assertFalse(gate["checks"]["marker_payload_identities_exact"])
        self.assertFalse(gate["checks"]["authorization_marker_digest_exact"])

    def test_public_exact_marker_replay_is_read_only_and_side_effect_free(self) -> None:
        report_dir = self.fixture.root / "exec-w" / "reports"
        report = self.outcome["report"]
        outer = build_campaign_terminal_report(
            campaign_id=CAMPAIGN,
            configuration_id=CONFIG,
            run_id=RUN,
            cycle_id=CYCLE,
            report_id="report-c12-c14",
            factory_run_id=self.fixture.captured_run_id,
            execution_id="exec-w",
            terminal_status="COMPLETED",
            terminal_cause="FACTORY_COMPLETED",
            run_status="COMPLETED",
            lifecycle_started=True,
            reconciliation={"clean_terminal": True},
            forbidden_deltas={"retrieval_queries": 0, "paper_decisions": 0},
            launch_git_provenance=TEST_GIT_PROVENANCE,
            six_unit_totals=report["full_run_accounting"]["six_unit_totals"],
            six_unit_evidence=report["full_run_accounting"]["owner_evidence"],
            require_six_unit_evidence=True,
        )
        outer["full_run_terminal_evidence"] = report
        write_campaign_terminal_report(
            self.fixture.db,
            report_dir,
            report_id="report-c12-c14",
            campaign_id=CAMPAIGN,
            configuration_id=CONFIG,
            report=outer,
            require_six_unit_evidence=True,
        )
        before = self.fixture.db.stat().st_mtime_ns
        replay = report_only(
            campaign_id=CAMPAIGN,
            run_id=RUN,
            db_path=self.fixture.db,
            artifact_root=self.fixture.root,
        )
        after = self.fixture.db.stat().st_mtime_ns
        self.assertEqual(replay["status"], "REPLAYED", replay)
        self.assertEqual(replay["source_calls"], 0)
        self.assertEqual(replay["scheduler_runtime_calls"], 0)
        self.assertEqual(replay["database_writes"], 0)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()

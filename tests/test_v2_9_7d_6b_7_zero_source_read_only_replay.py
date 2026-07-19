"""Focused V2-9.7D.6B.7 zero-source read-only replay tests."""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from printer_v1.operator_cli.final_campaign_report import (
    persist_final_campaign_report,
)
from printer_v1.operator_cli.zero_source_campaign_replay import (
    REPLAY_BLOCKED,
    REPLAY_VERIFIED,
    replay_terminal_campaign_report,
)
import printer_v1.operator_cli.zero_source_campaign_replay as replay_module
import test_v2_9_7d_6b_6_final_campaign_report as _fixture


class ZeroSourceReadOnlyReplayTests(unittest.TestCase):
    _slot = staticmethod(_fixture.FinalCampaignReportTests._slot)
    _seed_authoritative_graph = (
        _fixture.FinalCampaignReportTests._seed_authoritative_graph
    )

    def setUp(self) -> None:
        _fixture.FinalCampaignReportTests.setUp(self)
        persisted = persist_final_campaign_report(
            self.db, report_id="report-a", campaign_id="campaign-a",
            configuration_id="configuration-a", run_id="run-a",
        )
        self.report_hash = str(persisted["report_hash"])

    def tearDown(self) -> None:
        _fixture.FinalCampaignReportTests.tearDown(self)

    def _replay(self, **changes: str) -> dict[str, object]:
        values = {
            "campaign_id": "campaign-a",
            "configuration_id": "configuration-a",
            "report_id": "report-a",
            "report_hash": self.report_hash,
            **changes,
        }
        return replay_terminal_campaign_report(self.db, **values)

    @staticmethod
    def _hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _replace_report(self, payload: str, digest: str) -> None:
        with self.connection:
            self.connection.execute("DROP TRIGGER printer_campaign_report_immutable_update")
            self.connection.execute(
                """UPDATE printer_memory_factory_campaign_reports
                   SET report_json=?,report_hash=? WHERE report_id='report-a'""",
                (payload, digest),
            )

    def test_valid_replay_is_deterministic_and_preserves_gaps(self) -> None:
        before_hash = self._hash(self.db)
        before_reports = self.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_reports"
        ).fetchone()[0]
        first = self._replay()
        second = self._replay()

        self.assertEqual(first, second)
        self.assertEqual(first["replay_state"], REPLAY_VERIFIED)
        self.assertEqual(first["reasons"], [])
        self.assertTrue(
            first["diagnostics"]["visible_unknowns_and_evidence_gaps"]
        )
        self.assertNotEqual(
            first["diagnostics"]["opportunity_outcome_layers"][0][
                "full_window_outcome"
            ],
            first["diagnostics"]["opportunity_outcome_layers"][0][
                "internal_trade_opportunity_outcome"
            ],
        )
        self.assertEqual(
            first["zero_work_evidence"],
            {
                "source_calls": 0, "scheduler_work": 0,
                "memory_writes": 0, "database_writes": 0,
            },
        )
        evidence = first["database_read_only_evidence"]
        self.assertEqual(evidence["before_sha256"], evidence["after_sha256"])
        self.assertEqual(evidence["before_row_counts"], evidence["after_row_counts"])
        self.assertEqual(evidence["total_changes"], 0)
        self.assertEqual(before_hash, self._hash(self.db))
        self.assertEqual(
            before_reports,
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_reports"
            ).fetchone()[0],
        )
        self.assertFalse(first["replay_row_persisted"])

    def test_hash_payload_and_identity_mismatches_block_exactly(self) -> None:
        cases = (
            ({"report_hash": "x" * 64}, "expected report hash is malformed"),
            ({"report_hash": "0" * 64}, "expected report hash mismatch"),
            ({"campaign_id": "campaign-b"}, "report identity or state mismatch"),
            ({"configuration_id": "configuration-b"}, "report identity or state mismatch"),
            ({"report_id": "report-b"}, "report identity or state mismatch"),
        )
        for changes, reason in cases:
            with self.subTest(changes=changes):
                result = self._replay(**changes)
                self.assertEqual(result["replay_state"], REPLAY_BLOCKED)
                self.assertEqual(result["reasons"], [reason])
                self.assertEqual(
                    result["database_read_only_evidence"]["total_changes"], 0
                )

    def test_noncanonical_or_malformed_payload_blocks(self) -> None:
        row = self.connection.execute(
            "SELECT report_json FROM printer_memory_factory_campaign_reports"
        ).fetchone()
        parsed = json.loads(row[0])
        noncanonical = json.dumps(parsed, sort_keys=False, indent=2)
        digest = hashlib.sha256(noncanonical.encode("utf-8")).hexdigest()
        self._replace_report(noncanonical, digest)
        self.report_hash = digest
        result = self._replay()
        self.assertEqual(result["replay_state"], REPLAY_BLOCKED)
        self.assertEqual(
            result["reasons"], ["stored report payload is not canonical JSON"]
        )

    def test_provenance_mismatch_blocks(self) -> None:
        row = self.connection.execute(
            "SELECT report_json FROM printer_memory_factory_campaign_reports"
        ).fetchone()
        report = json.loads(row[0])
        report["launch_git_provenance"]["git_head"] = "d" * 40
        canonical = json.dumps(
            report, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self._replace_report(canonical, digest)
        self.report_hash = digest
        result = self._replay()
        self.assertEqual(result["replay_state"], REPLAY_BLOCKED)
        self.assertEqual(
            result["reasons"], ["stored launch Git provenance mismatch"]
        )

    def test_missing_authoritative_object_links_block(self) -> None:
        with self.connection:
            self.connection.execute(
                "DROP TRIGGER printer_campaign_report_object_immutable_delete"
            )
            self.connection.execute(
                "DELETE FROM printer_memory_factory_campaign_report_objects"
            )
        result = self._replay()
        self.assertEqual(result["replay_state"], REPLAY_BLOCKED)
        self.assertEqual(result["reasons"], ["stored report object links mismatch"])

    def test_source_scheduler_git_and_replay_writers_are_never_called(self) -> None:
        source = inspect.getsource(replay_module)
        for forbidden_dependency in (
            "source_governor", "central_scheduler", "capture_git_provenance",
            "persist_report_replay", "load_report_only",
        ):
            self.assertNotIn(forbidden_dependency, source)
        with (
            patch(
                "printer_v1.operator_cli.git_provenance.capture_git_provenance",
                side_effect=AssertionError("Git capture called"),
            ),
            patch(
                "printer_v1.operator_cli.campaign_persistence.persist_report_replay",
                side_effect=AssertionError("replay writer called"),
            ),
            patch(
                "printer_v1.operator_cli.one_command_15m_factory.load_report_only",
                side_effect=AssertionError("legacy replay called"),
            ),
        ):
            result = self._replay()
        self.assertEqual(result["replay_state"], REPLAY_VERIFIED)


if __name__ == "__main__":
    unittest.main()

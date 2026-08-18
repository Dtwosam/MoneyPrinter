"""Slice J — hermetic reporting-truth and report-only regressions.

The final campaign report owns promotion/safety truth.  The public operational
``report_only`` command owns exact-identity, zero-work replay behavior.  These
are deliberately separate read-only authorities; this test proves both without
inventing a new production reporting contract.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli.final_campaign_report import persist_final_campaign_report
from printer_v1.operator_cli.one_command_15m_factory import (
    ALREADY_EXISTS_IDEMPOTENT,
    CLEAN_PROMOTED,
    DIRTY_OR_BLOCKED,
    NO_PROMOTION,
)
from printer_v1.operator_cli.zero_source_campaign_replay import (
    REPLAY_VERIFIED,
    replay_terminal_campaign_report,
)
from printer_v1.safety.composite import (
    SAFETY_CONTEXT_ACCEPTABLE,
    SAFETY_CONTEXT_BLOCKED,
    SAFETY_CONTEXT_UNKNOWN,
)
import test_v2_9_7d_6b_6_final_campaign_report as _final_fixture


PROMOTION_STATES = frozenset(
    {CLEAN_PROMOTED, DIRTY_OR_BLOCKED, ALREADY_EXISTS_IDEMPOTENT, NO_PROMOTION}
)
SAFETY_STATES = frozenset(
    {SAFETY_CONTEXT_ACCEPTABLE, SAFETY_CONTEXT_BLOCKED, SAFETY_CONTEXT_UNKNOWN}
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SliceJReportingTruthTests(unittest.TestCase):
    def test_final_report_replay_keeps_promotion_and_safety_truth_separate(self) -> None:
        # Reuse the established final-report fixture by composition, not
        # inheritance, so none of its test methods are accidentally collected.
        fixture = _final_fixture.FinalCampaignReportTests(
            methodName="test_complete_report_is_deterministic_and_preserves_independent_layers"
        )
        fixture.setUp()
        try:
            persisted = persist_final_campaign_report(
                fixture.db,
                report_id="slice-j-report",
                campaign_id="campaign-a",
                configuration_id="configuration-a",
                run_id="run-a",
            )
            before_hash = _sha256(fixture.db)
            replay = replay_terminal_campaign_report(
                fixture.db,
                campaign_id="campaign-a",
                configuration_id="configuration-a",
                report_id="slice-j-report",
                report_hash=str(persisted["report_hash"]),
            )

            self.assertEqual(replay["replay_state"], REPLAY_VERIFIED)
            diagnostics = replay["diagnostics"]
            self.assertIsInstance(diagnostics, dict)

            promotions = diagnostics["promotion_outcomes_b1"]
            safety_contexts = diagnostics["safety_contexts_b2"]
            self.assertTrue(promotions)
            self.assertTrue(safety_contexts)

            promotion_values = {
                str(item["promotion_status"]) for item in promotions
            }
            safety_values = {
                str(
                    item["effective_safety_context"][
                        "effective_safety_context_result"
                    ]
                )
                for item in safety_contexts
            }

            self.assertTrue(promotion_values <= PROMOTION_STATES)
            self.assertTrue(safety_values <= SAFETY_STATES)
            self.assertTrue(PROMOTION_STATES.isdisjoint(SAFETY_STATES))
            self.assertTrue(promotion_values.isdisjoint(SAFETY_STATES))
            self.assertTrue(safety_values.isdisjoint(PROMOTION_STATES))

            # Replay is reporting only: no collection, Scheduler work, memory
            # mutation, report persistence, or Git-provenance recapture.
            self.assertEqual(
                replay["zero_work_evidence"],
                {
                    "source_calls": 0,
                    "scheduler_work": 0,
                    "memory_writes": 0,
                    "database_writes": 0,
                },
            )
            self.assertEqual(replay["database_read_only_evidence"]["total_changes"], 0)
            self.assertEqual(_sha256(fixture.db), before_hash)
            self.assertFalse(replay["git_provenance_recaptured"])
            self.assertFalse(replay["replay_row_persisted"])
        finally:
            fixture.tearDown()

    def test_public_report_only_exact_identity_block_is_zero_work(self) -> None:
        # The public operational report-only surface has a different report
        # schema.  Prove its permanent contract independently: exact identity,
        # fail closed when absent, and no source/Scheduler/database work.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            db = root / "public-report-only.sqlite3"
            apply_migrations(db)
            before_hash = _sha256(db)

            result = command.report_only(
                campaign_id="missing-campaign",
                run_id="missing-run",
                db_path=db,
                artifact_root=root / "artifacts",
            )

            self.assertEqual(result["status"], "REPLAY_BLOCKED")
            self.assertEqual(
                result["requested_identity"],
                {
                    "campaign_id": "missing-campaign",
                    "run_id": "missing-run",
                },
            )
            self.assertFalse(result["fallback_used"])
            self.assertEqual(result["source_calls"], 0)
            self.assertEqual(result["scheduler_runtime_calls"], 0)
            self.assertEqual(result["database_writes"], 0)
            self.assertEqual(result["replay_new_source_calls"], 0)
            self.assertEqual(result["replay_new_scheduler_calls"], 0)
            self.assertEqual(_sha256(db), before_hash)


if __name__ == "__main__":
    unittest.main()

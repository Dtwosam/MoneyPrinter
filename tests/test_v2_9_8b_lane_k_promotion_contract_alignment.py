"""Regression: E2Y batch mandatory only in batch mode; individual uses per-window gates."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from printer_v1.db.migrate import apply_migrations
from printer_v1.operator_cli.e2z_clean_memory_creation import (
    E2Z_STATUS_BLOCKED,
    create_clean_memory_from_window,
)
from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import (
    _RECOMMENDED_NEXT_ACTION,
)


class LaneKPromotionContractAlignment(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "promo.sqlite3"
        apply_migrations(self.db)

    def test_batch_mode_requires_e2y(self) -> None:
        # Batch-mode E2Y validation runs before DB window fetch.
        result = create_clean_memory_from_window(
            self.db,
            1,
            operator_approved=True,
            individual_promotion=False,
            e2y_report=None,
        )
        self.assertEqual(result.get("e2z_status"), E2Z_STATUS_BLOCKED)
        reasons = " ".join(result.get("blocked_reasons") or [])
        self.assertIn("e2y_report", reasons.lower())

    def test_batch_mode_requires_set_gate_passed(self) -> None:
        result = create_clean_memory_from_window(
            self.db,
            2,
            operator_approved=True,
            individual_promotion=False,
            e2y_report={
                "set_gate_passed": False,
                "candidate_set_summary": {"candidate_ids": [2]},
            },
        )
        self.assertEqual(result.get("e2z_status"), E2Z_STATUS_BLOCKED)
        reasons = " ".join(str(r) for r in (result.get("blocked_reasons") or []))
        self.assertIn("set_gate_passed", reasons)

    def test_individual_mode_skips_e2y_but_still_applies_per_window_gate(self) -> None:
        # No window row: individual mode skips E2Y but still fail-closes on
        # the per-window DB gate (missing window).
        result = create_clean_memory_from_window(
            self.db,
            3,
            operator_approved=True,
            individual_promotion=True,
            e2y_report=None,
        )
        self.assertEqual(result.get("e2z_status"), E2Z_STATUS_BLOCKED)
        reasons = " ".join(str(r) for r in (result.get("blocked_reasons") or []))
        self.assertTrue(
            reasons,
            msg="individual promotion must still surface per-window blockers",
        )
        # Must not have failed solely for missing e2y_report.
        self.assertNotIn("e2y_report is required", reasons)

    def test_recommended_action_no_longer_requires_e2y_for_individual(self) -> None:
        text = _RECOMMENDED_NEXT_ACTION.lower()
        self.assertIn("individual_promotion", text)
        self.assertIn("informational", text)
        # Must not claim E2Y batch passage is mandatory for operational promotion.
        self.assertNotIn(
            "if e2y set gate did not pass, verify that at least 5 eligible",
            text,
        )

    def test_module_docstring_aligns_with_individual_promotion(self) -> None:
        import printer_v1.operator_cli.lane_k_e2z_pipeline_wiring as lane_k

        doc = (lane_k.__doc__ or "").lower()
        self.assertIn("individual_promotion", doc)
        self.assertIn("informational", doc)
        self.assertNotIn("e2y (and therefore e2z) still requires", doc)


if __name__ == "__main__":
    unittest.main()

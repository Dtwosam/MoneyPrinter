"""V2-9.7B.2 timeframe-neutral safety reporting checks."""

import json
import sqlite3
import unittest
from unittest.mock import patch

from printer_v1.operator_cli.commands import _apply_clean_audit_evidence_labels
from printer_v1.safety.composite import (
    SAFETY_CONTEXT_ACCEPTABLE,
    SAFETY_CONTEXT_BLOCKED,
    SAFETY_CONTEXT_UNKNOWN,
    composite_row_is_acceptable,
    effective_safety_context_report,
)


def _legacy_composite(*, blocked=False):
    return {
        "id": 7,
        "token_id": 1,
        "pair_id": 2,
        "snapshot_id": 3,
        "memory_window_id": None,
        "target_status": "TARGET_MATCH",
        "freshness_label": "SAFETY_EVIDENCE_FRESH",
        "source_status": "COMPLETE" if not blocked else "PARTIAL",
        "data_quality_label": (
            "CLEAN_DATA" if not blocked else "ACCEPTABLE_PARTIAL_DATA"
        ),
        "provenance_complete": 1,
        "paper_only_context": 1,
        "safety_context_label": "SAFETY_UNKNOWN",
        "safety_action_label": "BLOCK_CLEAN_MEMORY",
        "safety_contract_label": (
            "SAFETY_BLOCKED_FOR_15M_MEMORY"
            if blocked
            else "SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY"
        ),
        # Holder concentration is descriptive after E.48 / Slice I.  A blocked
        # fixture must therefore carry a real hard safety blocker rather than
        # treating HOLDER_CONCENTRATION_EXTREME as an admission veto.
        "mint_authority_status": (
            "MINT_AUTHORITY_PRESENT" if blocked else "MINT_AUTHORITY_RENOUNCED"
        ),
        "freeze_authority_status": "FREEZE_AUTHORITY_DISABLED",
        "metadata_mutability_status": "METADATA_IMMUTABLE",
        "supply_sanity_label": "SUPPLY_SANITY_OK",
        "holder_concentration_label": (
            "HOLDER_CONCENTRATION_EXTREME"
            if blocked
            else "HOLDER_CONCENTRATION_HEALTHY"
        ),
        "liquidity_lock_or_burn_label": "LIQUIDITY_LOCK_OR_BURN_UNKNOWN",
        "known_risk_flag_label": "KNOWN_RISK_FLAGS_UNKNOWN",
        "token_program_label": "SPL_TOKEN_OR_TOKEN_2022_VERIFIED",
        "blockers_json": json.dumps(
            ["mint_authority_status"] if blocked else []
        ),
        "optional_unknowns_json": json.dumps(
            ["liquidity_lock_or_burn_label", "known_risk_flag_label"]
        ),
    }


class TimeframeAwareSafetyReportingTests(unittest.TestCase):
    def _overlay(self, window_kind, safety_row):
        connection = sqlite3.connect(":memory:")
        before = connection.total_changes

        def latest(_connection, table_name, **_kwargs):
            if table_name == "printer_safety_evidence_composites":
                return safety_row
            return {}

        with patch(
            "printer_v1.operator_cli.commands._table_exists",
            return_value=True,
        ), patch(
            "printer_v1.operator_cli.commands._latest_audit_evidence_row",
            side_effect=latest,
        ):
            result = _apply_clean_audit_evidence_labels(
                connection,
                window={
                    "id": 10,
                    "token_id": 1,
                    "pair_id": 2,
                    "snapshot_end_id": 3,
                    "window_kind": window_kind,
                },
                labels={},
            )
        self.assertEqual(connection.total_changes, before)
        connection.close()
        return result

    def test_legacy_acceptable_composite_is_neutral_for_15m_1h_and_4h(self):
        row = _legacy_composite()
        self.assertTrue(composite_row_is_acceptable(row))
        for window_kind in ("WINDOW_15M", "WINDOW_1H", "WINDOW_4H"):
            with self.subTest(window_kind=window_kind):
                result = self._overlay(window_kind, row)
                labels = result["labels"]
                self.assertEqual(
                    labels["effective_safety_context_result"],
                    SAFETY_CONTEXT_ACCEPTABLE,
                )
                self.assertEqual(
                    result["overlays"]["safety_context_report"]["window_kind"],
                    window_kind,
                )
                self.assertEqual(
                    labels["raw_safety_contract_label"],
                    "SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY",
                )
                self.assertEqual(
                    labels["raw_safety_context_label"], "SAFETY_UNKNOWN"
                )
                self.assertEqual(
                    labels["raw_safety_action_label"], "BLOCK_CLEAN_MEMORY"
                )
                self.assertEqual(
                    labels["safety_action_label"],
                    SAFETY_CONTEXT_ACCEPTABLE,
                )
                self.assertIn(
                    "liquidity_lock_or_burn_label",
                    result["overlays"]["source_coverage_pending_fields"],
                )

    def test_explicit_danger_and_missing_mandatory_evidence_remain_blocked(self):
        dangerous = _legacy_composite(blocked=True)
        self.assertFalse(composite_row_is_acceptable(dangerous))
        result = self._overlay("WINDOW_4H", dangerous)
        self.assertEqual(
            result["labels"]["effective_safety_context_result"],
            SAFETY_CONTEXT_BLOCKED,
        )
        missing = self._overlay("WINDOW_1H", {})
        self.assertEqual(
            missing["labels"]["effective_safety_context_result"],
            SAFETY_CONTEXT_BLOCKED,
        )
        self.assertTrue(missing["overlays"]["evidence_blockers"])

    def test_not_evaluated_is_unknown_without_relabeling_raw_evidence(self):
        row = _legacy_composite()
        report = effective_safety_context_report(
            row,
            gate_accepted=None,
            window_kind="WINDOW_1H",
        )
        self.assertEqual(
            report["effective_safety_context_result"],
            SAFETY_CONTEXT_UNKNOWN,
        )
        self.assertEqual(
            report["raw_safety_context_label"], "SAFETY_UNKNOWN"
        )
        self.assertEqual(
            report["raw_safety_contract_label"],
            "SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY",
        )


if __name__ == "__main__":
    unittest.main()

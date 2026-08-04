"""Focused proof: separate pre-lifecycle readiness is not required for WINDOW_15M auth.

Covers the operator decision that normal final-authorization preparation and
independent review succeed without a readiness artifact, while ordinary
provenance / package-hash / one-use rules remain mandatory and the dormant
artifact path is not invoked on the normal path.
"""

from __future__ import annotations

import ast
import inspect
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from printer_v1.db.migrate import apply_migrations
from printer_v1.operator_cli.pre_lifecycle_readiness_artifact import (
    compute_db_identity,
    validate_pre_lifecycle_readiness_artifact,
)
from printer_v1.operator_cli.pre_lifecycle_readiness_authorization_gate import (
    assert_authorization_preparation_readiness_gate,
    evaluate_authorization_preparation_readiness_gate,
)


class RemoveSeparateReadinessPrerequisite(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "auth.sqlite3"
        apply_migrations(self.db)
        self.db_identity = compute_db_identity(self.db)
        self.head = "1be704c8c618bbb72a34b2bd5b2e86d4c02a059a"
        self.now = datetime(2026, 8, 3, 20, 0, 0, tzinfo=timezone.utc)

    def test_final_authorization_preparation_succeeds_without_readiness(self) -> None:
        with mock.patch(
            "printer_v1.operator_cli.pre_lifecycle_readiness_authorization_gate."
            "validate_pre_lifecycle_readiness_artifact"
        ) as validate_mock:
            gate = evaluate_authorization_preparation_readiness_gate(
                readiness_artifact=None,
                now=self.now,
                expected_head=self.head,
                expected_db_identity=self.db_identity,
            )
            # Normal path must not call readiness validation at all.
            validate_mock.assert_not_called()
        self.assertTrue(gate["valid"])
        self.assertEqual(
            gate["status"],
            "AUTHORIZATION_PREPARATION_READINESS_GATE_NOT_REQUIRED",
        )
        self.assertFalse(gate["readiness_required"])
        self.assertFalse(gate["provider_contacted"])
        self.assertFalse(gate["authorization_emitted"])
        # assert API also accepts absent artifact
        asserted = assert_authorization_preparation_readiness_gate(
            readiness_artifact=None,
            now=self.now,
            expected_head=self.head,
            expected_db_identity=self.db_identity,
        )
        self.assertTrue(asserted["valid"])

    def test_independent_review_succeeds_without_readiness(self) -> None:
        # Independent review uses the same gate owner; absent artifact is PASS.
        review = evaluate_authorization_preparation_readiness_gate(
            readiness_artifact=None,
            now=self.now.isoformat(),
            expected_head=self.head,
            expected_db_identity=self.db_identity,
        )
        self.assertTrue(review["valid"])
        self.assertTrue(
            review["status"].endswith("_NOT_REQUIRED")
            or review["status"].endswith("_PASS")
        )
        self.assertEqual(review["blockers"], [])
        self.assertFalse(review["provider_contacted"])
        self.assertFalse(review["wrapper_invoked"])

    def test_absent_artifact_validator_still_reports_absent_when_called_directly(
        self,
    ) -> None:
        # Dormant validator retains fail-closed semantics if invoked directly.
        validation = validate_pre_lifecycle_readiness_artifact(
            None,
            now=self.now,
            expected_head=self.head,
            expected_db_identity=self.db_identity,
        )
        self.assertFalse(validation["valid"])
        self.assertIn("artifact_absent", validation["blockers"])

    def test_gate_source_has_no_provider_or_qualification_calls(self) -> None:
        from printer_v1.operator_cli import (
            pre_lifecycle_readiness_authorization_gate as gate_mod,
        )

        source = inspect.getsource(gate_mod)
        tree = ast.parse(source)
        call_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    call_names.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    call_names.add(node.func.attr)
        forbidden = {
            "urlopen",
            "requests",
            "Session",
            "build_pre_lifecycle_readiness_artifact",
            "run_readiness_only",
            "run_snapshot_readiness",
            "contact_provider",
        }
        self.assertTrue(forbidden.isdisjoint(call_names))
        self.assertIn("validate_pre_lifecycle_readiness_artifact", call_names)
        # validate is only reached when an artifact is supplied (branch protection
        # covered by the mock test above for the None path).


if __name__ == "__main__":
    unittest.main()

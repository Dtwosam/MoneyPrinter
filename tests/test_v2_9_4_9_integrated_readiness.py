"""V2-9.4.9 -- integrated readiness: the V2-9.4.x repairs compose.

Every contract below is already proven in isolation by an existing fixture. The
one gap this file closes is their *composition*: no existing test asserts that a
fully evidenced 15m close reaches clean_memory_context_ready through the real
shared-context resolver with the exact-ledger intersection active. V2-9.4.8
recorded that gap as its risk 1.

The neighbouring V2-4 test `test_governed_close_context_reaches_exact_target_and_
side_aware_flow` runs the same path and asserts each section is READY, but stops
short of the integrated question -- can these repairs together still produce
clean memory, or did they compose into a window that can never be clean?

Patching WINDOW_SECONDS to 0 is the established technique in this suite (three
V2-4 tests already do it) for running the *real* resolver against the compressed
harness, whose windows span fractions of a second.

Paper-only. Temporary isolated DB. No live sources, no retrieval, no financial
deltas, no production change.
"""

import json
import pathlib
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

import test_v2_4_one_command_15m_factory as v24  # noqa: E402  (shared harness)


class IntegratedReadinessTest(unittest.TestCase):
    """Harness helpers are borrowed by reference so the V2-4 tests are not re-collected."""

    setUp = v24.OneCommand15mFactoryTests.setUp
    tearDown = v24.OneCommand15mFactoryTests.tearDown
    _discovery = v24.OneCommand15mFactoryTests._discovery
    _adapter_factory = v24.OneCommand15mFactoryTests._adapter_factory
    _failing_context_factories = v24.OneCommand15mFactoryTests._failing_context_factories
    _clean_context_factories = v24.OneCommand15mFactoryTests._clean_context_factories
    _run = v24.OneCommand15mFactoryTests._run

    def test_repairs_compose_into_a_clean_capable_15m_close(self):
        with patch("printer_v1.context_evidence.window_15m.WINDOW_SECONDS", 0):
            result, _calls = self._run(
                context_adapter_factories=self._clean_context_factories()
            )
        close = next(
            step for step in result["steps"] if step["step_kind"] == "WINDOW_CLOSE"
        )
        close_result = json.loads(close["result_json"])
        shared = close_result["context_quality"]["shared_context_evidence"]

        # V2-9.4.8: the closing snapshot was attached to the current-run ledger
        # before context resolved, and the resolver used the exact ledger range.
        self.assertTrue(close_result["ledger_attachment"]["attached"])
        self.assertEqual(
            close_result["ledger_attachment"]["snapshot_id"], close["snapshot_id"]
        )
        self.assertEqual(shared["snapshot_end_id"], close["snapshot_id"])

        # V2-9.4.6: no false boundary or ledger blocker survives composition.
        self.assertEqual(shared["non_ledger_snapshot_ids"], [])
        for false_blocker in (
            "SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER",
            "SNAPSHOT_BOUNDARY_MISMATCH",
        ):
            self.assertNotIn(false_blocker, shared["blockers"], false_blocker)

        # V2-9.4.8: the 15m closing-lateness contract stays at 0 seconds and is
        # not widened to the 4h 60s allowance.
        self.assertEqual(shared["closing_evidence_allowance_seconds"], 0)
        self.assertEqual(
            shared["closing_evidence_cutoff_at"], shared["window_end_at"]
        )

        # V2-9.4.7: flow is honestly partial because no adapter supplies split
        # volume or wallet participation -- and that alone does not block.
        flow = shared["sections"]["trading_flow"]
        self.assertEqual(
            flow["labels"]["trading_flow_payload_quality_label"],
            "TRADING_FLOW_CONTEXT_PARTIAL",
        )
        self.assertEqual(
            flow["labels"]["flow_memory_gate_label"], "FLOW_CONTEXT_CAUTION"
        )
        self.assertTrue(flow["can_support_clean_memory"])

        # The integrated question: the repairs compose into a window that can
        # still be clean, rather than one that can never be clean.
        self.assertEqual(shared["blockers"], [])
        self.assertTrue(shared["clean_memory_context_ready"])

        # Nothing financial or retrieval-related moved, and the run stopped clean.
        self.assertTrue(all(v == 0 for v in result["forbidden_deltas"].values()))
        self.assertEqual(result["running_jobs_after_stop"], 0)
        self.assertFalse(shared["writes_performed"])
        self.assertFalse(any(shared["downstream_unlocks"].values()))


if __name__ == "__main__":
    unittest.main()

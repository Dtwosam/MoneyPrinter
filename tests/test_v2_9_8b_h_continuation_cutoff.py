from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

from printer_v1.safety.composite import SAFETY_CONTEXT_ACCEPTABLE
from printer_v1.scheduler.token_local_continuation import ContinuationVerdict


def _load_selective_fixture_module():
    path = Path(__file__).with_name("test_v2_9_8b_operational_selective_1h.py")
    spec = importlib.util.spec_from_file_location("h_selective_fixture", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load selective-1h fixture module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_FIXTURE_MODULE = _load_selective_fixture_module()
Selective1hFixture = _FIXTURE_MODULE.Selective1hFixture
T0 = _FIXTURE_MODULE.T0
NOW = _FIXTURE_MODULE.NOW
_iso = _FIXTURE_MODULE._iso


class HContinuationCutoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = Selective1hFixture()

    def tearDown(self) -> None:
        self.fx.close()

    def test_exact_predecessor_close_beats_stale_campaign_checkpoint(self) -> None:
        self.fx.prepare_eligible(token_id=1, window_id=201, outcome="CONSOLIDATION")
        self.fx.prepare_eligible(token_id=2, window_id=202, outcome="NO_PUMP")

        # Reproduce the historical defect: the campaign checkpoint predates
        # slot-1's exact close-time safety evidence, while its linked physical
        # closing snapshot remains the authoritative T15 close.
        with self.fx.connection:
            self.fx.connection.execute(
                """
                UPDATE printer_memory_factory_campaign_windows
                SET checkpoint_cutoff=?
                WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                  AND cycle_id='cycle-1h' AND token_slot_id='slot-1'
                  AND window_kind='WINDOW_15M'
                """,
                (_iso(T0),),
            )

        safety = self.fx.safety(token_id=1, window_id=201)
        self.assertTrue(safety["gate_accepted"])
        self.assertEqual(safety["evidence_cutoff_source"], "EXACT_CLOSING_SNAPSHOT")
        self.assertEqual(safety["evidence_cutoff"], NOW)
        self.assertEqual(
            safety["effective_safety_context"]["effective_safety_context_result"],
            SAFETY_CONTEXT_ACCEPTABLE,
        )
        self.assertEqual(
            safety["raw_composite"]["liquidity_lock_or_burn_label"],
            "LIQUIDITY_LOCK_OR_BURN_UNKNOWN",
        )
        self.assertEqual(
            safety["raw_composite"]["known_risk_flag_label"],
            "KNOWN_RISK_FLAGS_UNKNOWN",
        )

        result = self.fx.evaluate()
        plans = {int(item["token_row_id"]): item for item in result["token_plans"]}
        self.assertEqual(
            plans[1]["verdict"], ContinuationVerdict.CONTINUE_TO_WINDOW_1H
        )
        self.assertEqual(
            plans[2]["verdict"], ContinuationVerdict.CONTINUE_TO_WINDOW_1H
        )
        self.assertEqual(result["continue_count"], 2)
        self.assertEqual(result["block_count"], 0)

    def test_real_hard_safety_block_remains_token_local(self) -> None:
        self.fx.prepare_eligible(token_id=1, window_id=211, outcome="DUMP")
        self.fx.prepare_eligible(token_id=2, window_id=212, outcome="CONSOLIDATION")

        safety = self.fx.safety(token_id=1, window_id=211)
        composite_id = int(safety["safety_composite_id"])
        with self.fx.connection:
            self.fx.connection.execute(
                """
                UPDATE printer_safety_evidence_composites
                SET blockers_json='["mint_authority_status"]'
                WHERE id=?
                """,
                (composite_id,),
            )

        result = self.fx.evaluate()
        plans = {int(item["token_row_id"]): item for item in result["token_plans"]}
        self.assertEqual(plans[1]["verdict"], ContinuationVerdict.BLOCK_CONTINUATION)
        self.assertEqual(
            plans[2]["verdict"], ContinuationVerdict.CONTINUE_TO_WINDOW_1H
        )
        self.assertEqual(result["continue_count"], 1)
        self.assertEqual(result["block_count"], 1)


if __name__ == "__main__":
    unittest.main()

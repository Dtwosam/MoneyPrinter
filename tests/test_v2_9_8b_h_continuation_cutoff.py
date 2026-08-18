from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

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
T15 = _FIXTURE_MODULE.T15
_iso = _FIXTURE_MODULE._iso


class HContinuationCutoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = Selective1hFixture()

    def tearDown(self) -> None:
        self.fx.close()

    def _set_real_15m_bounds(self, *window_ids: int) -> None:
        with self.fx.connection:
            for window_id in window_ids:
                self.fx.connection.execute(
                    """
                    UPDATE printer_memory_windows
                    SET window_start_at=?, window_end_at=?
                    WHERE id=?
                    """,
                    (_iso(T0), _iso(T15), int(window_id)),
                )

    def test_15m_to_1h_uses_exact_predecessor_close_not_campaign_checkpoint(self) -> None:
        """A stale campaign checkpoint must not replace the exact 15m close cutoff."""
        self.fx.prepare_eligible(token_id=1, window_id=201, outcome="CONSOLIDATION")
        self.fx.prepare_eligible(token_id=2, window_id=202, outcome="NO_PUMP")
        self._set_real_15m_bounds(201, 202)

        # Deliberately make only slot-1's campaign checkpoint predate the real
        # close-time safety evidence. The exact physical predecessor still has
        # a valid T15 closing snapshot and T15 fixed window end.
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


if __name__ == "__main__":
    unittest.main()

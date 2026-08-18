from __future__ import annotations

import unittest
from types import SimpleNamespace


class FourTokenFreezeInputTruncationRepairTests(unittest.TestCase):
    def test_permanent_observation_admission_uses_full_reserve_not_selected_pair(self) -> None:
        # RED contract: the permanent observation universe must be the full
        # lawful reserve, not the already-selected two-slot handoff pair.
        from printer_v1.operator_cli.authoritative_live_operational_campaign import (
            _permanent_observation_admission_inputs,
        )

        selected_pair = ("selected-a", "selected-b")
        full_reserve = tuple(f"reserve-{index}" for index in range(8))
        supply = SimpleNamespace(
            graduated_supply=selected_pair,
            holder_reserve_supply=full_reserve,
        )

        actual = _permanent_observation_admission_inputs(supply)

        self.assertEqual(actual, full_reserve)
        self.assertEqual(len(actual), 8)
        self.assertNotEqual(actual, selected_pair)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from types import SimpleNamespace


class FourTokenFreezeInputTruncationRepairTests(unittest.TestCase):
    @staticmethod
    def _observation_candidates(count: int) -> list[dict[str, object]]:
        return [
            {
                "mint": f"mint-{index}",
                "pool": f"pool-{index}",
                "memory_observation_eligible": True,
                "tracking_handoff_eligible": True,
                "tracking_requalification_required": False,
                "evidence_expires_at": "2026-08-18T23:30:00+00:00",
            }
            for index in range(count)
        ]

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

    def test_eight_candidate_incident_shape_reaches_freeze_without_two_slot_truncation(self) -> None:
        from printer_v1.discovery.permanent_discovery_availability import (
            freeze_eligible_reserve,
        )
        from printer_v1.operator_cli.authoritative_live_operational_campaign import (
            _permanent_observation_admission_inputs,
        )

        full_reserve = tuple(self._observation_candidates(8))
        supply = SimpleNamespace(
            graduated_supply=full_reserve[:2],
            holder_reserve_supply=full_reserve,
        )

        admission = _permanent_observation_admission_inputs(supply)
        frozen = freeze_eligible_reserve(
            admission,
            cycle_seed="four-token-freeze-incident-shape",
            at="2026-08-18T22:30:00+00:00",
        )

        self.assertEqual(len(admission), 8)
        self.assertEqual(len(frozen.selected), 2)
        self.assertGreaterEqual(len(frozen.alternates), 2)
        self.assertEqual(len(frozen.alternates[:2]), 2)
        self.assertFalse(bool(frozen.selection_authority.get("coverage_blocker")))
        self.assertEqual(
            int(frozen.selection_authority.get("minimum_freeze_depth") or 0), 4
        )
        self.assertEqual(
            int(frozen.selection_authority.get("observation_eligible_count") or 0), 8
        )

    def test_freeze_depth_four_still_yields_two_selected_and_two_alternates(self) -> None:
        from printer_v1.discovery.permanent_discovery_availability import (
            freeze_eligible_reserve,
        )

        frozen = freeze_eligible_reserve(
            self._observation_candidates(4),
            cycle_seed="four-token-freeze-positive",
            at="2026-08-18T22:30:00+00:00",
        )

        self.assertEqual(len(frozen.selected), 2)
        self.assertEqual(len(frozen.alternates), 2)
        self.assertFalse(bool(frozen.selection_authority.get("coverage_blocker")))
        self.assertEqual(
            int(frozen.selection_authority.get("minimum_freeze_depth") or 0), 4
        )

    def test_freeze_depth_three_still_blocks_truthfully(self) -> None:
        from printer_v1.discovery.permanent_discovery_availability import (
            freeze_eligible_reserve,
        )

        frozen = freeze_eligible_reserve(
            self._observation_candidates(3),
            cycle_seed="four-token-freeze-negative",
            at="2026-08-18T22:30:00+00:00",
        )

        self.assertEqual(frozen.selected, ())
        self.assertEqual(frozen.alternates, ())
        self.assertTrue(bool(frozen.selection_authority.get("coverage_blocker")))
        self.assertEqual(
            int(frozen.selection_authority.get("observation_eligible_count") or 0), 3
        )


if __name__ == "__main__":
    unittest.main()

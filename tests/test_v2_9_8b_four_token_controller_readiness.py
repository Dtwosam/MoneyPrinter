"""Focused read-only controller readiness contract for V2-9.8B.

No source work, Scheduler mutation, cycle reservation, discovery callback,
memory generation, or runtime activation is permitted here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from printer_v1.operator_cli import four_token_proof_integration as integration
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
    MultiCycleCampaignBinding,
)
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    AdmissionDecision,
    AdmissionEvaluation,
)


class FourTokenControllerReadinessTests(unittest.TestCase):
    def test_controller_composes_canonical_read_only_admission_with_factory_wake(self) -> None:
        controller_type = getattr(
            integration,
            "FourTokenProofController",
            None,
        )
        self.assertIsNotNone(
            controller_type,
            "read-only four-token controller must exist before factory-loop wiring",
        )

        controller = controller_type.exact()

        self.assertEqual(
            controller.policy.configured_through_4h_token_ceiling,
            4,
        )
        self.assertEqual(
            controller.policy.configured_active_cycle_ceiling,
            2,
        )
        self.assertEqual(
            controller.policy.total_cycle_admission_ceiling,
            2,
        )
        self.assertGreaterEqual(
            controller.policy.min_admission_spacing_seconds,
            300,
        )

        now = datetime(2026, 8, 13, 12, 10, tzinfo=timezone.utc)
        binding = MultiCycleCampaignBinding(
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            configuration_id="configuration-1",
            authoritative_factory_run_id="factory-1",
        )
        health = MultiCycleAdmissionHealth()
        connection = object()

        admit_snapshot = SimpleNamespace(
            admission_evaluation=AdmissionEvaluation(
                decision=AdmissionDecision.ADMIT,
                reason="CAPACITY_AVAILABLE",
                next_admission_at=None,
            )
        )

        with patch.object(
            integration,
            "load_multi_cycle_campaign_snapshot",
            return_value=admit_snapshot,
        ) as loader:
            readiness = controller.evaluate_factory_wake(
                connection,
                binding=binding,
                now=now,
                next_due_work_at=now,
                proof_deadline=now + timedelta(hours=5),
                admission_health=health,
            )

        self.assertIs(readiness.snapshot, admit_snapshot)
        self.assertEqual(readiness.wake.at, now)
        self.assertEqual(
            readiness.wake.reason,
            "LIFECYCLE_WORK",
            "already-due lifecycle work must outrank fresh admission",
        )

        loader.assert_called_once_with(
            connection,
            binding,
            controller.policy,
            now=now,
            health=health,
        )

        spacing_boundary = now + timedelta(seconds=300)
        spacing_snapshot = SimpleNamespace(
            admission_evaluation=AdmissionEvaluation(
                decision=AdmissionDecision.IDLE,
                reason="ADMISSION_SPACING_ACTIVE",
                next_admission_at=spacing_boundary,
            )
        )

        with patch.object(
            integration,
            "load_multi_cycle_campaign_snapshot",
            return_value=spacing_snapshot,
        ):
            readiness = controller.evaluate_factory_wake(
                connection,
                binding=binding,
                now=now,
                next_due_work_at=now + timedelta(minutes=10),
                proof_deadline=now + timedelta(hours=5),
                admission_health=health,
            )

        self.assertEqual(readiness.wake.at, spacing_boundary)
        self.assertEqual(readiness.wake.reason, "CYCLE_ADMISSION")

        source = inspect.getsource(controller_type.evaluate_factory_wake)

        self.assertIn(
            "load_multi_cycle_campaign_snapshot",
            source,
            "controller readiness must reuse canonical persisted admission evaluation",
        )
        self.assertNotIn(
            "reserve_exact_two_token_cycle",
            source,
            "readiness evaluation must not reserve a cycle",
        )
        self.assertNotIn(
            "later_cycle_discovery_callback",
            source,
            "readiness evaluation must not invoke discovery",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

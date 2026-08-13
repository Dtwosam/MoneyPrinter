"""Focused read-only controller readiness contract for V2-9.8B.

No cycle admission, discovery, Scheduler execution, runtime activation, or
authoritative database mutation is permitted by this seam.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3
import unittest
from unittest.mock import patch

from printer_v1.operator_cli import four_token_proof_integration as integration
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
    MultiCycleCampaignBinding,
    MultiCycleCampaignSnapshot,
)
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    AdmissionDecision,
    AdmissionEvaluation,
    MultiCycleSessionPhase,
    MultiCycleSessionSnapshot,
)


class FourTokenControllerReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 13, 12, 10, tzinfo=timezone.utc)
        self.binding = MultiCycleCampaignBinding(
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            configuration_id="configuration-1",
            authoritative_factory_run_id="factory-1",
        )
        self.health = MultiCycleAdmissionHealth()
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute("CREATE TABLE sentinel(value TEXT NOT NULL)")
        self.connection.commit()

    def tearDown(self) -> None:
        self.connection.close()

    def _snapshot(
        self,
        *,
        decision: AdmissionDecision,
        reason: str,
        last_cycle_admitted_at: datetime | None,
    ) -> MultiCycleCampaignSnapshot:
        return MultiCycleCampaignSnapshot(
            campaign_id=self.binding.campaign_id,
            campaign_run_id=self.binding.campaign_run_id,
            configuration_id=self.binding.configuration_id,
            authoritative_factory_run_id=(
                self.binding.authoritative_factory_run_id
            ),
            cycle_ids=("cycle-1",),
            active_cycle_ids=("cycle-1",),
            active_token_slot_ids=("slot-1", "slot-2"),
            first_cycle_id="cycle-1",
            session=MultiCycleSessionSnapshot(
                intake_started_at=self.now - timedelta(minutes=10),
                intake_deadline=self.now + timedelta(hours=4),
                configured_through_4h_token_ceiling=4,
                configured_active_cycle_ceiling=2,
                total_cycle_admission_ceiling=2,
                active_through_4h_tokens=2,
                active_cycles=1,
                admissions_completed=1,
                last_cycle_admitted_at=last_cycle_admitted_at,
                phase=MultiCycleSessionPhase.ACTIVE_INTAKE,
            ),
            admission_evaluation=AdmissionEvaluation(
                decision=decision,
                reason=reason,
            ),
        )

    def _evaluate(
        self,
        snapshot: MultiCycleCampaignSnapshot,
        *,
        next_due_work_at: datetime | None,
        proof_deadline: datetime | None = None,
    ):
        controller = integration.FourTokenProofController.exact()
        changes_before = self.connection.total_changes
        with patch.object(
            integration,
            "load_multi_cycle_campaign_snapshot",
            return_value=snapshot,
        ) as loader:
            readiness = controller.evaluate_factory_wake(
                self.connection,
                binding=self.binding,
                now=self.now,
                next_due_work_at=next_due_work_at,
                proof_deadline=proof_deadline or self.now + timedelta(hours=5),
                admission_health=self.health,
            )
        loader.assert_called_once_with(
            self.connection,
            binding=self.binding,
            policy=controller.policy,
            now=self.now,
            health=self.health,
        )
        self.assertEqual(self.connection.total_changes, changes_before)
        self.assertFalse(self.connection.in_transaction)
        return readiness

    def test_controller_composes_persisted_admission_readiness_without_writes(self) -> None:
        controller = integration.FourTokenProofController.exact()
        self.assertEqual(
            (
                controller.policy.configured_through_4h_token_ceiling,
                controller.policy.configured_active_cycle_ceiling,
                controller.policy.total_cycle_admission_ceiling,
            ),
            (4, 2, 2),
        )

        admit = self._snapshot(
            decision=AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE,
            reason="all_pair_admission_requirements_met",
            last_cycle_admitted_at=self.now - timedelta(minutes=5),
        )
        readiness = self._evaluate(admit, next_due_work_at=self.now)
        self.assertIs(readiness.snapshot, admit)
        self.assertEqual(readiness.wake.at, self.now)
        self.assertEqual(readiness.wake.reason, "LIFECYCLE_WORK")

        spacing = self._snapshot(
            decision=AdmissionDecision.DEFER,
            reason="minimum_admission_spacing_not_elapsed",
            last_cycle_admitted_at=self.now - timedelta(seconds=60),
        )
        readiness = self._evaluate(
            spacing,
            next_due_work_at=self.now + timedelta(minutes=10),
        )
        self.assertEqual(readiness.wake.at, self.now + timedelta(minutes=4))
        self.assertEqual(readiness.wake.reason, "CYCLE_ADMISSION")

        for decision, reason in (
            (AdmissionDecision.DEFER, "source_budget_unavailable"),
            (AdmissionDecision.DRAIN, "intake_closed_drain_only"),
            (AdmissionDecision.COMPLETE, "bounded_drain_complete"),
            (AdmissionDecision.BLOCKED, "authoritative_db_unhealthy"),
        ):
            with self.subTest(decision=decision):
                no_admission = self._snapshot(
                    decision=decision,
                    reason=reason,
                    last_cycle_admitted_at=self.now - timedelta(minutes=5),
                )
                readiness = self._evaluate(
                    no_admission,
                    next_due_work_at=self.now + timedelta(minutes=10),
                    proof_deadline=self.now + timedelta(minutes=3),
                )
                self.assertEqual(
                    (readiness.wake.at, readiness.wake.reason),
                    (self.now + timedelta(minutes=3), "PROOF_DEADLINE"),
                )

    def test_spacing_defer_without_persisted_admission_time_fails_closed(self) -> None:
        controller = integration.FourTokenProofController.exact()
        snapshot = self._snapshot(
            decision=AdmissionDecision.DEFER,
            reason="minimum_admission_spacing_not_elapsed",
            last_cycle_admitted_at=None,
        )
        changes_before = self.connection.total_changes
        with patch.object(
            integration,
            "load_multi_cycle_campaign_snapshot",
            return_value=snapshot,
        ):
            with self.assertRaisesRegex(
                integration.FourTokenProofPolicyError,
                "spacing defer requires persisted last-cycle admission time",
            ):
                controller.evaluate_factory_wake(
                    self.connection,
                    binding=self.binding,
                    now=self.now,
                    next_due_work_at=self.now + timedelta(minutes=10),
                    proof_deadline=self.now + timedelta(hours=5),
                    admission_health=self.health,
                )
        self.assertEqual(self.connection.total_changes, changes_before)
        self.assertFalse(self.connection.in_transaction)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

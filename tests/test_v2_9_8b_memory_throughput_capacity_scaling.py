"""Focused tests for V2-9.8B multi-cycle Memory Factory capacity scaling."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from printer_v1.operator_cli.multi_cycle_memory_growth import (
    AdmissionDecision,
    MAX_ACTIVE_TWO_TOKEN_CYCLES,
    MAX_NEW_TOKENS_PER_24H_SESSION,
    MAX_THROUGH_4H_TOKENS,
    MAX_TOTAL_CYCLE_ADMISSIONS_PER_24H_SESSION,
    MIN_CYCLE_ADMISSION_SPACING_SECONDS,
    TOKENS_PER_CYCLE,
    MultiCycleAdmissionState,
    MultiCycleCapacityPolicy,
    MultiCycleSessionPhase,
    evaluate_cycle_admission,
    evaluate_session_phase,
    scaled_session_capacity_contract,
    scaled_standard_four_hour_capacity_contract,
)
from printer_v1.operator_cli.operational_standard_4h import (
    standard_four_hour_capacity_contract,
)
from printer_v1.scheduler.contracts import JobKind, JobStatus
from printer_v1.scheduler.multi_cycle_fairness import (
    TwoTokenCycleWork,
    select_multi_cycle_scheduler_work,
)
from printer_v1.scheduler.two_token_fairness import (
    CampaignSchedulerCeilings,
    SchedulerSelectionStatus,
    SchedulerWorkIntent,
    SchedulerWorkItem,
    TwoTokenSlot,
)


class MultiCycleCapacityPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
        self.policy6 = MultiCycleCapacityPolicy(
            configured_through_4h_token_ceiling=6,
            configured_active_cycle_ceiling=3,
            total_cycle_admission_ceiling=15,
            intake_duration_seconds=86_400,
        )

    def _state(self, **overrides) -> MultiCycleAdmissionState:
        values = {
            "now": self.start,
            "intake_started_at": self.start,
            "active_through_4h_tokens": 0,
            "active_cycles": 0,
            "admissions_completed": 0,
            "last_cycle_admitted_at": None,
            "source_budget_available": True,
            "provider_budgets_available": True,
            "scheduler_budget_available": True,
            "scheduler_due_work_healthy": True,
            "close_reserve_available": True,
            "campaign_supervision_healthy": True,
            "lease_healthy": True,
            "db_healthy": True,
            "shared_terminal_condition": False,
            "cancellation_requested": False,
            "discovery_capacity_available": True,
            "protected_work_capacity_available": True,
        }
        values.update(overrides)
        return MultiCycleAdmissionState(**values)

    def test_compiled_capacity_is_six_active_and_thirty_new_tokens_per_24h(self) -> None:
        self.assertEqual(MAX_THROUGH_4H_TOKENS, 6)
        self.assertEqual(MAX_ACTIVE_TWO_TOKEN_CYCLES, 3)
        self.assertEqual(TOKENS_PER_CYCLE, 2)
        self.assertEqual(MIN_CYCLE_ADMISSION_SPACING_SECONDS, 300)
        self.assertEqual(MAX_TOTAL_CYCLE_ADMISSIONS_PER_24H_SESSION, 15)
        self.assertEqual(MAX_NEW_TOKENS_PER_24H_SESSION, 30)

    def test_configured_active_capacity_accepts_two_four_or_six_only(self) -> None:
        for tokens, active_cycles in ((2, 1), (4, 2), (6, 3)):
            with self.subTest(tokens=tokens):
                policy = MultiCycleCapacityPolicy(
                    configured_through_4h_token_ceiling=tokens,
                    configured_active_cycle_ceiling=active_cycles,
                    total_cycle_admission_ceiling=15,
                    intake_duration_seconds=3_600,
                )
                policy.validate()

        for tokens, active_cycles in (
            (0, 0),
            (1, 1),
            (3, 2),
            (4, 3),
            (6, 2),
            (8, 4),
        ):
            with self.subTest(tokens=tokens, active_cycles=active_cycles):
                with self.assertRaises(ValueError):
                    MultiCycleCapacityPolicy(
                        configured_through_4h_token_ceiling=tokens,
                        configured_active_cycle_ceiling=active_cycles,
                        total_cycle_admission_ceiling=15,
                        intake_duration_seconds=3_600,
                    ).validate()

    def test_total_session_cycle_ceiling_is_separate_from_active_cycle_ceiling(self) -> None:
        MultiCycleCapacityPolicy(
            configured_through_4h_token_ceiling=6,
            configured_active_cycle_ceiling=3,
            total_cycle_admission_ceiling=15,
            intake_duration_seconds=86_400,
        ).validate()

        for total in (0, 2, 16):
            with self.subTest(total=total):
                with self.assertRaises(ValueError):
                    MultiCycleCapacityPolicy(
                        configured_through_4h_token_ceiling=6,
                        configured_active_cycle_ceiling=3,
                        total_cycle_admission_ceiling=total,
                        intake_duration_seconds=86_400,
                    ).validate()

    def test_scaled_active_capacity_is_derived_from_existing_two_token_contract(self) -> None:
        base = standard_four_hour_capacity_contract()
        four = scaled_standard_four_hour_capacity_contract(4)
        six = scaled_standard_four_hour_capacity_contract(6)

        self.assertEqual(four["configured_active_cycles"], 2)
        self.assertEqual(
            four["lifecycle_request_outer_ceiling"],
            2 * int(base["lifecycle_request_outer_ceiling"]),
        )
        self.assertEqual(
            four["lifecycle_scheduler_outer_ceiling"],
            2 * int(base["lifecycle_scheduler_outer_ceiling"]),
        )
        self.assertEqual(six["configured_active_cycles"], 3)
        self.assertEqual(
            six["lifecycle_request_outer_ceiling"],
            3 * int(base["lifecycle_request_outer_ceiling"]),
        )
        self.assertEqual(
            six["lifecycle_scheduler_outer_ceiling"],
            3 * int(base["lifecycle_scheduler_outer_ceiling"]),
        )
        self.assertEqual(
            six["lifecycle_requests_per_token"],
            int(base["lifecycle_requests_per_token"]),
        )

    def test_24h_session_ceiling_projects_fifteen_two_token_cycles(self) -> None:
        base = standard_four_hour_capacity_contract()
        session = scaled_session_capacity_contract(
            configured_through_4h_tokens=6,
            total_cycle_admission_ceiling=15,
        )
        self.assertEqual(session["configured_active_cycles"], 3)
        self.assertEqual(session["session_cycle_admission_ceiling"], 15)
        self.assertEqual(session["session_new_token_admission_ceiling"], 30)
        self.assertEqual(
            session["session_lifecycle_request_outer_ceiling"],
            15 * int(base["lifecycle_request_outer_ceiling"]),
        )
        self.assertEqual(
            session["session_lifecycle_scheduler_outer_ceiling"],
            15 * int(base["lifecycle_scheduler_outer_ceiling"]),
        )

    def test_three_staggered_pair_admissions_reach_six_without_exceeding_it(self) -> None:
        first = evaluate_cycle_admission(self.policy6, self._state())
        second = evaluate_cycle_admission(
            self.policy6,
            self._state(
                now=self.start + timedelta(minutes=5),
                active_through_4h_tokens=2,
                active_cycles=1,
                admissions_completed=1,
                last_cycle_admitted_at=self.start,
            ),
        )
        third = evaluate_cycle_admission(
            self.policy6,
            self._state(
                now=self.start + timedelta(minutes=10),
                active_through_4h_tokens=4,
                active_cycles=2,
                admissions_completed=2,
                last_cycle_admitted_at=self.start + timedelta(minutes=5),
            ),
        )
        full = evaluate_cycle_admission(
            self.policy6,
            self._state(
                now=self.start + timedelta(minutes=15),
                active_through_4h_tokens=6,
                active_cycles=3,
                admissions_completed=3,
                last_cycle_admitted_at=self.start + timedelta(minutes=10),
            ),
        )
        self.assertEqual(first.decision, AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE)
        self.assertEqual(second.decision, AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE)
        self.assertEqual(third.decision, AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE)
        self.assertEqual(full.decision, AdmissionDecision.DEFER)
        self.assertEqual(full.reason, "through_4h_capacity_full")

    def test_five_minutes_is_minimum_spacing_not_guaranteed_admission(self) -> None:
        too_soon = evaluate_cycle_admission(
            self.policy6,
            self._state(
                now=self.start + timedelta(minutes=4, seconds=59),
                active_through_4h_tokens=2,
                active_cycles=1,
                admissions_completed=1,
                last_cycle_admitted_at=self.start,
            ),
        )
        on_time_but_source_busy = evaluate_cycle_admission(
            self.policy6,
            self._state(
                now=self.start + timedelta(minutes=5),
                active_through_4h_tokens=2,
                active_cycles=1,
                admissions_completed=1,
                last_cycle_admitted_at=self.start,
                source_budget_available=False,
            ),
        )
        self.assertEqual(too_soon.decision, AdmissionDecision.DEFER)
        self.assertEqual(too_soon.reason, "minimum_admission_spacing_not_elapsed")
        self.assertEqual(on_time_but_source_busy.decision, AdmissionDecision.DEFER)
        self.assertEqual(on_time_but_source_busy.reason, "source_budget_unavailable")

    def test_released_pair_capacity_can_be_reused_while_intake_is_open(self) -> None:
        result = evaluate_cycle_admission(
            self.policy6,
            self._state(
                now=self.start + timedelta(hours=4, minutes=1),
                active_through_4h_tokens=4,
                active_cycles=2,
                admissions_completed=3,
                last_cycle_admitted_at=self.start + timedelta(minutes=10),
            ),
        )
        self.assertEqual(result.decision, AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE)

    def test_one_early_token_failure_does_not_create_single_token_refill(self) -> None:
        result = evaluate_cycle_admission(
            self.policy6,
            self._state(
                now=self.start + timedelta(minutes=20),
                active_through_4h_tokens=5,
                active_cycles=3,
                admissions_completed=3,
                last_cycle_admitted_at=self.start + timedelta(minutes=10),
            ),
        )
        self.assertEqual(result.decision, AdmissionDecision.DEFER)
        self.assertEqual(result.reason, "active_cycle_capacity_full")

    def test_every_admission_health_gate_fails_closed_or_defers(self) -> None:
        defer_gates = {
            "source_budget_available": "source_budget_unavailable",
            "provider_budgets_available": "provider_budget_unavailable",
            "scheduler_budget_available": "scheduler_budget_unavailable",
            "scheduler_due_work_healthy": "scheduler_due_work_unhealthy",
            "close_reserve_available": "close_reserve_unavailable",
            "discovery_capacity_available": "discovery_capacity_unavailable",
            "protected_work_capacity_available": "protected_work_capacity_unavailable",
        }
        for field, reason in defer_gates.items():
            with self.subTest(field=field):
                result = evaluate_cycle_admission(
                    self.policy6,
                    self._state(**{field: False}),
                )
                self.assertEqual(result.decision, AdmissionDecision.DEFER)
                self.assertEqual(result.reason, reason)

        blocked_gates = {
            "campaign_supervision_healthy": "campaign_supervision_unhealthy",
            "lease_healthy": "campaign_lease_unhealthy",
            "db_healthy": "authoritative_db_unhealthy",
            "shared_terminal_condition": "shared_terminal_condition",
        }
        for field, reason in blocked_gates.items():
            with self.subTest(field=field):
                value = True if field == "shared_terminal_condition" else False
                result = evaluate_cycle_admission(
                    self.policy6,
                    self._state(**{field: value}),
                )
                self.assertEqual(result.decision, AdmissionDecision.BLOCKED)
                self.assertEqual(result.reason, reason)

    def test_intake_deadline_enters_drain_then_zero_active_becomes_complete(self) -> None:
        deadline = self.start + timedelta(days=1)
        draining = self._state(
            now=deadline,
            active_through_4h_tokens=4,
            active_cycles=2,
            admissions_completed=10,
            last_cycle_admitted_at=deadline - timedelta(hours=1),
        )
        complete = self._state(
            now=deadline + timedelta(hours=4),
            active_through_4h_tokens=0,
            active_cycles=0,
            admissions_completed=10,
            last_cycle_admitted_at=deadline - timedelta(hours=1),
        )
        self.assertEqual(evaluate_session_phase(self.policy6, draining), MultiCycleSessionPhase.DRAIN)
        self.assertEqual(
            evaluate_cycle_admission(self.policy6, draining).decision,
            AdmissionDecision.DRAIN,
        )
        self.assertEqual(evaluate_session_phase(self.policy6, complete), MultiCycleSessionPhase.COMPLETE)
        self.assertEqual(
            evaluate_cycle_admission(self.policy6, complete).decision,
            AdmissionDecision.COMPLETE,
        )

    def test_total_cycle_admission_ceiling_enters_drain_before_time_deadline(self) -> None:
        draining = self._state(
            now=self.start + timedelta(hours=20),
            active_through_4h_tokens=2,
            active_cycles=1,
            admissions_completed=15,
            last_cycle_admitted_at=self.start + timedelta(hours=19),
        )
        complete = self._state(
            now=self.start + timedelta(hours=20),
            active_through_4h_tokens=0,
            active_cycles=0,
            admissions_completed=15,
            last_cycle_admitted_at=self.start + timedelta(hours=19),
        )
        self.assertEqual(evaluate_session_phase(self.policy6, draining), MultiCycleSessionPhase.DRAIN)
        self.assertEqual(
            evaluate_cycle_admission(self.policy6, draining).decision,
            AdmissionDecision.DRAIN,
        )
        self.assertEqual(evaluate_session_phase(self.policy6, complete), MultiCycleSessionPhase.COMPLETE)
        self.assertEqual(
            evaluate_cycle_admission(self.policy6, complete).decision,
            AdmissionDecision.COMPLETE,
        )

    def test_impossible_state_or_admission_count_is_blocked(self) -> None:
        too_many_tokens = evaluate_cycle_admission(
            self.policy6,
            self._state(
                active_through_4h_tokens=7,
                active_cycles=3,
                admissions_completed=3,
            ),
        )
        more_active_cycles_than_admissions = evaluate_cycle_admission(
            self.policy6,
            self._state(
                active_through_4h_tokens=4,
                active_cycles=2,
                admissions_completed=1,
            ),
        )
        too_many_admissions = evaluate_cycle_admission(
            self.policy6,
            self._state(admissions_completed=16),
        )
        for result in (
            too_many_tokens,
            more_active_cycles_than_admissions,
            too_many_admissions,
        ):
            self.assertEqual(result.decision, AdmissionDecision.BLOCKED)
            self.assertTrue(result.reason.startswith("invalid_state:"))


class MultiCycleFairnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 13, 12, 10, tzinfo=timezone.utc)
        self.slots = [
            TwoTokenSlot(
                slot_id=f"slot-{index}",
                token_id=f"token-{index}",
                mint_id=f"mint-{index}",
                pair_id=f"pair-{index}",
                lifecycle_id=f"lifecycle-{index}",
                token_state="TRACK_FAST",
            )
            for index in range(1, 7)
        ]

    def _work(
        self,
        work_id: str,
        slot: TwoTokenSlot,
        *,
        intent: SchedulerWorkIntent = SchedulerWorkIntent.ORDINARY,
        kind: JobKind = JobKind.TRACK_FAST_4H,
        created_minutes_ago: int = 1,
        deadline_minutes: int | None = None,
    ) -> SchedulerWorkItem:
        return SchedulerWorkItem(
            scheduler_work_id=work_id,
            token_slot_id=slot.slot_id,
            token_id=slot.token_id,
            job_kind=kind,
            work_intent=intent,
            status=JobStatus.PENDING,
            scheduled_for=self.now - timedelta(minutes=created_minutes_ago),
            deadline_at=(
                self.now + timedelta(minutes=deadline_minutes)
                if deadline_minutes is not None
                else None
            ),
            created_at=self.now - timedelta(minutes=created_minutes_ago),
        )

    def _cycle(self, ordinal: int, slots, works) -> TwoTokenCycleWork:
        return TwoTokenCycleWork(
            cycle_id=f"cycle-{ordinal}",
            cycle_ordinal=ordinal,
            token_slots=tuple(slots),
            work_items=tuple(works),
        )

    def test_earliest_main_window_close_wins_across_three_cycles(self) -> None:
        cycles = (
            self._cycle(
                1,
                self.slots[0:2],
                [
                    self._work(
                        "close-1",
                        self.slots[0],
                        intent=SchedulerWorkIntent.MAIN_WINDOW_CLOSE,
                        kind=JobKind.MEMORY_WINDOW_CLOSE,
                        deadline_minutes=3,
                    )
                ],
            ),
            self._cycle(
                2,
                self.slots[2:4],
                [
                    self._work(
                        "close-2",
                        self.slots[2],
                        intent=SchedulerWorkIntent.MAIN_WINDOW_CLOSE,
                        kind=JobKind.MEMORY_WINDOW_CLOSE,
                        deadline_minutes=1,
                    )
                ],
            ),
            self._cycle(
                3,
                self.slots[4:6],
                [self._work("ordinary-3", self.slots[4])],
            ),
        )
        result = select_multi_cycle_scheduler_work(cycles=cycles, now=self.now)
        self.assertEqual(result.status, SchedulerSelectionStatus.SELECTED)
        self.assertEqual(result.selected_cycle_id, "cycle-2")
        self.assertEqual(result.selected_work.scheduler_work_id, "close-2")

    def test_safe_stop_precedes_ordinary_work_across_cycles(self) -> None:
        cycles = (
            self._cycle(
                1,
                self.slots[0:2],
                [self._work("ordinary-1", self.slots[0], created_minutes_ago=20)],
            ),
            self._cycle(
                2,
                self.slots[2:4],
                [
                    self._work(
                        "safe-2",
                        self.slots[2],
                        intent=SchedulerWorkIntent.SAFE_STOP,
                    )
                ],
            ),
        )
        result = select_multi_cycle_scheduler_work(cycles=cycles, now=self.now)
        self.assertEqual(result.selected_work.scheduler_work_id, "safe-2")

    def test_ordinary_service_count_is_fair_across_cycles(self) -> None:
        served = TwoTokenSlot(**{**self.slots[0].__dict__, "ordinary_service_count": 2})
        cycles = (
            self._cycle(
                1,
                (served, self.slots[1]),
                [self._work("old-but-served", served, created_minutes_ago=50)],
            ),
            self._cycle(
                2,
                self.slots[2:4],
                [self._work("less-served", self.slots[2], created_minutes_ago=1)],
            ),
        )
        result = select_multi_cycle_scheduler_work(cycles=cycles, now=self.now)
        self.assertEqual(result.selected_work.scheduler_work_id, "less-served")

    def test_three_cycles_are_supported_but_fourth_cycle_is_blocked(self) -> None:
        three = tuple(
            self._cycle(
                ordinal,
                self.slots[(ordinal - 1) * 2 : ordinal * 2],
                [self._work(f"work-{ordinal}", self.slots[(ordinal - 1) * 2])],
            )
            for ordinal in range(1, 4)
        )
        result = select_multi_cycle_scheduler_work(cycles=three, now=self.now)
        self.assertEqual(result.status, SchedulerSelectionStatus.SELECTED)

        fourth_slots = (
            TwoTokenSlot(
                "slot-7",
                "token-7",
                "mint-7",
                "pair-7",
                "lifecycle-7",
                "TRACK_FAST",
            ),
            TwoTokenSlot(
                "slot-8",
                "token-8",
                "mint-8",
                "pair-8",
                "lifecycle-8",
                "TRACK_FAST",
            ),
        )
        four = (
            *three,
            self._cycle(4, fourth_slots, [self._work("work-4", fourth_slots[0])]),
        )
        blocked = select_multi_cycle_scheduler_work(cycles=four, now=self.now)
        self.assertEqual(blocked.status, SchedulerSelectionStatus.BLOCKED)
        self.assertEqual(
            blocked.reason,
            "active_cycle_count_exceeds_compiled_maximum",
        )

    def test_shared_ceiling_exhaustion_blocks_all_cycles(self) -> None:
        cycles = (
            self._cycle(1, self.slots[0:2], [self._work("work-1", self.slots[0])]),
            self._cycle(2, self.slots[2:4], [self._work("work-2", self.slots[2])]),
        )
        result = select_multi_cycle_scheduler_work(
            cycles=cycles,
            now=self.now,
            ceilings=CampaignSchedulerCeilings(
                scheduler_work_ceiling=10,
                scheduler_work_used=10,
            ),
        )
        self.assertEqual(result.status, SchedulerSelectionStatus.BLOCKED)
        self.assertEqual(result.reason, "scheduler_work_ceiling_exhausted")

    def test_token_local_failure_remains_isolated_inside_its_cycle(self) -> None:
        failed = TwoTokenSlot(
            **{**self.slots[0].__dict__, "token_local_failure": True}
        )
        cycles = (
            self._cycle(
                1,
                (failed, self.slots[1]),
                [
                    self._work("failed-work", failed),
                    self._work("healthy-peer", self.slots[1]),
                ],
            ),
            self._cycle(2, self.slots[2:4], []),
        )
        result = select_multi_cycle_scheduler_work(cycles=cycles, now=self.now)
        self.assertEqual(result.status, SchedulerSelectionStatus.SELECTED)
        self.assertEqual(result.selected_work.scheduler_work_id, "healthy-peer")
        self.assertIn("failed-work", result.excluded_work_ids)

    def test_selection_is_deterministic_for_equal_ordinary_work(self) -> None:
        cycles = (
            self._cycle(
                2,
                self.slots[2:4],
                [self._work("work-cycle-2", self.slots[2], created_minutes_ago=5)],
            ),
            self._cycle(
                1,
                self.slots[0:2],
                [self._work("work-cycle-1", self.slots[0], created_minutes_ago=5)],
            ),
        )
        first = select_multi_cycle_scheduler_work(cycles=cycles, now=self.now)
        second = select_multi_cycle_scheduler_work(
            cycles=tuple(reversed(cycles)),
            now=self.now,
        )
        self.assertEqual(first.selected_work.scheduler_work_id, "work-cycle-1")
        self.assertEqual(second.selected_work.scheduler_work_id, "work-cycle-1")


if __name__ == "__main__":
    unittest.main()

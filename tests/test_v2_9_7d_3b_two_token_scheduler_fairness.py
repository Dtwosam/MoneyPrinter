"""V2-9.7D.3B two-token scheduler fairness tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.scheduler.contracts import JobKind, JobStatus
from printer_v1.scheduler.two_token_fairness import (
    CampaignSchedulerCeilings,
    SchedulerSelectionStatus,
    SchedulerWorkIntent,
    SchedulerWorkItem,
    TWO_TOKEN_ACTIVE_SLOT_COUNT,
    TwoTokenSlot,
    select_two_token_scheduler_work,
)


class TwoTokenSchedulerFairnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        self.slot_a = TwoTokenSlot(
            slot_id="slot-a",
            token_id="token-a",
            mint_id="mint-a",
            pair_id="pair-a",
            lifecycle_id="lifecycle-a",
            token_state="TRACK_FAST",
        )
        self.slot_b = TwoTokenSlot(
            slot_id="slot-b",
            token_id="token-b",
            mint_id="mint-b",
            pair_id="pair-b",
            lifecycle_id="lifecycle-b",
            token_state="TRACK_NORMAL",
        )

    def _work(
        self,
        work_id: str,
        slot: TwoTokenSlot,
        *,
        kind: JobKind = JobKind.TRACK_FAST_FIRST_15M,
        intent: SchedulerWorkIntent = SchedulerWorkIntent.ORDINARY,
        minutes_old: int = 1,
        deadline_minutes: int | None = None,
        status: JobStatus = JobStatus.PENDING,
        eligible: bool = True,
    ) -> SchedulerWorkItem:
        return SchedulerWorkItem(
            scheduler_work_id=work_id,
            token_slot_id=slot.slot_id,
            token_id=slot.token_id,
            job_kind=kind,
            work_intent=intent,
            status=status,
            scheduled_for=self.now - timedelta(minutes=minutes_old),
            deadline_at=(
                self.now + timedelta(minutes=deadline_minutes)
                if deadline_minutes is not None
                else None
            ),
            created_at=self.now - timedelta(minutes=minutes_old),
            eligible=eligible,
        )

    def _select(self, slots, works, **kwargs):
        return select_two_token_scheduler_work(
            token_slots=slots,
            work_items=works,
            now=self.now,
            ceilings=kwargs.pop("ceilings", CampaignSchedulerCeilings()),
            shared_stop_reasons=kwargs.pop("shared_stop_reasons", ()),
        )

    def test_exactly_two_active_token_slots_constant(self) -> None:
        self.assertEqual(TWO_TOKEN_ACTIVE_SLOT_COUNT, 2)

    def test_no_third_active_token_is_accepted(self) -> None:
        slot_c = TwoTokenSlot(
            slot_id="slot-c",
            token_id="token-c",
            mint_id="mint-c",
            pair_id="pair-c",
            lifecycle_id="lifecycle-c",
            token_state="TRACK_NORMAL",
        )
        result = self._select(
            [self.slot_a, self.slot_b, slot_c],
            [self._work("work-a", self.slot_a)],
        )
        self.assertEqual(result.status, SchedulerSelectionStatus.BLOCKED)
        self.assertEqual(result.reason, "active_token_slot_count_not_two")

    def test_no_starvation_less_served_token_gets_ordinary_work_first(self) -> None:
        served_a = TwoTokenSlot(**{**self.slot_a.__dict__, "ordinary_service_count": 1})
        result = self._select(
            [served_a, self.slot_b],
            [
                self._work("work-a-old", served_a, minutes_old=30),
                self._work("work-b-new", self.slot_b, minutes_old=1),
            ],
        )
        self.assertEqual(result.status, SchedulerSelectionStatus.SELECTED)
        self.assertEqual(result.selected_work.scheduler_work_id, "work-b-new")

    def test_both_tokens_receive_ordinary_service_before_second_unit(self) -> None:
        served_a = TwoTokenSlot(**{**self.slot_a.__dict__, "ordinary_service_count": 1})
        result = self._select(
            [served_a, self.slot_b],
            [
                self._work("work-a-second", served_a, minutes_old=50),
                self._work("work-b-first", self.slot_b, minutes_old=2),
            ],
        )
        self.assertEqual(result.selected_work.scheduler_work_id, "work-b-first")

    def test_close_deadlines_preempt_ordinary_work_earliest_deadline_first(self) -> None:
        result = self._select(
            [self.slot_a, self.slot_b],
            [
                self._work("ordinary-a", self.slot_a, minutes_old=60),
                self._work(
                    "close-b-later",
                    self.slot_b,
                    kind=JobKind.MEMORY_WINDOW_CLOSE,
                    intent=SchedulerWorkIntent.MAIN_WINDOW_CLOSE,
                    deadline_minutes=4,
                    minutes_old=5,
                ),
                self._work(
                    "close-a-sooner",
                    self.slot_a,
                    kind=JobKind.MEMORY_WINDOW_CLOSE,
                    intent=SchedulerWorkIntent.MAIN_WINDOW_CLOSE,
                    deadline_minutes=1,
                    minutes_old=2,
                ),
            ],
        )
        self.assertEqual(result.selected_work.scheduler_work_id, "close-a-sooner")

    def test_fairness_resumes_after_close_preemption(self) -> None:
        served_a = TwoTokenSlot(**{**self.slot_a.__dict__, "ordinary_service_count": 1})
        result = self._select(
            [served_a, self.slot_b],
            [
                self._work("ordinary-a", served_a, minutes_old=30),
                self._work("ordinary-b", self.slot_b, minutes_old=1),
            ],
        )
        self.assertEqual(result.selected_work.scheduler_work_id, "ordinary-b")

    def test_overdue_evidence_gap_or_safe_stop_precedes_ordinary(self) -> None:
        result = self._select(
            [self.slot_a, self.slot_b],
            [
                self._work("ordinary-old", self.slot_a, minutes_old=50),
                self._work(
                    "safe-stop-new",
                    self.slot_b,
                    intent=SchedulerWorkIntent.SAFE_STOP,
                    minutes_old=1,
                ),
            ],
        )
        self.assertEqual(result.selected_work.scheduler_work_id, "safe-stop-new")

    def test_deterministic_tie_breaking_uses_older_work_before_slot_order(self) -> None:
        first = self._select(
            [self.slot_a, self.slot_b],
            [
                self._work("work-b-older", self.slot_b, minutes_old=20),
                self._work("work-a-newer", self.slot_a, minutes_old=10),
            ],
        )
        second = self._select(
            [self.slot_a, self.slot_b],
            [
                self._work("work-a-newer", self.slot_a, minutes_old=10),
                self._work("work-b-older", self.slot_b, minutes_old=20),
            ],
        )
        self.assertEqual(first.selected_work.scheduler_work_id, "work-b-older")
        self.assertEqual(second.selected_work.scheduler_work_id, "work-b-older")

    def test_stable_slot_order_is_final_tie_breaker(self) -> None:
        created = self.now - timedelta(minutes=10)
        work_a = self._work("same-time-work", self.slot_a, minutes_old=10)
        work_b = SchedulerWorkItem(
            scheduler_work_id="same-time-work-b",
            token_slot_id=self.slot_b.slot_id,
            token_id=self.slot_b.token_id,
            job_kind=JobKind.TRACK_NORMAL_FIRST_15M,
            work_intent=SchedulerWorkIntent.ORDINARY,
            scheduled_for=self.now - timedelta(minutes=10),
            created_at=created,
        )
        work_a = SchedulerWorkItem(**{**work_a.__dict__, "created_at": created})
        result = self._select([self.slot_a, self.slot_b], [work_a, work_b])
        self.assertEqual(result.selected_work.scheduler_work_id, "same-time-work")

    def test_terminal_cancelled_blocked_or_ineligible_work_is_never_selected(self) -> None:
        terminal = TwoTokenSlot(**{**self.slot_a.__dict__, "token_state": "ARCHIVED"})
        blocked = self._work("blocked-work", self.slot_b, eligible=False)
        cancelled = self._work("cancelled-work", self.slot_b, status=JobStatus.CANCELLED)
        result = self._select(
            [terminal, self.slot_b],
            [
                self._work("terminal-work", terminal),
                blocked,
                cancelled,
                self._work("eligible-work", self.slot_b),
            ],
        )
        self.assertEqual(result.selected_work.scheduler_work_id, "eligible-work")
        self.assertEqual(
            set(result.excluded_work_ids),
            {"terminal-work", "blocked-work", "cancelled-work"},
        )

    def test_token_local_failure_isolates_that_token(self) -> None:
        failed_a = TwoTokenSlot(**{**self.slot_a.__dict__, "token_local_failure": True})
        result = self._select(
            [failed_a, self.slot_b],
            [self._work("failed-token-work", failed_a), self._work("healthy-token-work", self.slot_b)],
        )
        self.assertEqual(result.status, SchedulerSelectionStatus.SELECTED)
        self.assertEqual(result.selected_work.scheduler_work_id, "healthy-token-work")
        self.assertEqual(result.excluded_work_ids, ("failed-token-work",))

    def test_shared_db_lease_integrity_or_campaign_budget_failure_blocks(self) -> None:
        for reason in (
            "SHARED_DB_FAILURE",
            "SHARED_LEASE_FAILURE",
            "SHARED_INTEGRITY_FAILURE",
            "CAMPAIGN_BUDGET_FAILURE",
        ):
            with self.subTest(reason=reason):
                result = self._select(
                    [self.slot_a, self.slot_b],
                    [self._work("work-a", self.slot_a)],
                    shared_stop_reasons=(reason,),
                )
                self.assertEqual(result.status, SchedulerSelectionStatus.BLOCKED)
                self.assertEqual(result.reason, reason.lower())

    def test_exhausted_ceilings_create_honest_blocked_result(self) -> None:
        result = self._select(
            [self.slot_a, self.slot_b],
            [self._work("work-a", self.slot_a)],
            ceilings=CampaignSchedulerCeilings(
                scheduler_work_ceiling=2,
                scheduler_work_used=2,
                source_request_ceiling=9,
                source_requests_used=0,
            ),
        )
        self.assertEqual(result.status, SchedulerSelectionStatus.BLOCKED)
        self.assertEqual(result.reason, "scheduler_work_ceiling_exhausted")
        self.assertIsNone(result.selected_work)


class TwoTokenFairnessSideEffectTests(unittest.TestCase):
    TABLES_THAT_MUST_NOT_CHANGE = (
        "printer_source_requests",
        "printer_memory_windows",
        "printer_memory_retrieval_queries",
        "printer_memory_retrieval_matches",
        "printer_paper_decisions",
        "printer_paper_positions",
        "printer_paper_trade_events",
        "printer_paper_trade_audits",
        "printer_paper_audit_reports",
    )

    def setUp(self) -> None:
        configured_temp = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=configured_temp)
        self.db_path = Path(self.temp.name) / "fairness.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _counts(self) -> dict[str, int]:
        connection = sqlite3.connect(self.db_path)
        try:
            return {
                table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in self.TABLES_THAT_MUST_NOT_CHANGE
            }
        finally:
            connection.close()

    def test_policy_selection_creates_no_locked_capability_rows(self) -> None:
        before = self._counts()
        slot_a = TwoTokenSlot(
            slot_id="slot-a",
            token_id="token-a",
            mint_id="mint-a",
            pair_id="pair-a",
            lifecycle_id="lifecycle-a",
            token_state="TRACK_FAST",
        )
        slot_b = TwoTokenSlot(
            slot_id="slot-b",
            token_id="token-b",
            mint_id="mint-b",
            pair_id="pair-b",
            lifecycle_id="lifecycle-b",
            token_state="TRACK_NORMAL",
        )
        result = select_two_token_scheduler_work(
            token_slots=(slot_a, slot_b),
            work_items=(
                SchedulerWorkItem(
                    scheduler_work_id="ordinary-a",
                    token_slot_id="slot-a",
                    token_id="token-a",
                    job_kind=JobKind.TRACK_FAST_FIRST_15M,
                    work_intent=SchedulerWorkIntent.ORDINARY,
                    scheduled_for=self.now,
                    created_at=self.now,
                ),
            ),
            now=self.now,
        )
        after = self._counts()
        self.assertEqual(result.status, SchedulerSelectionStatus.SELECTED)
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()

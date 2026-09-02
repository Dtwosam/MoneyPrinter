from __future__ import annotations

import inspect
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone

from printer_v1.operator_cli import one_command_15m_factory as factory


class CooperativeLaterCycleRepairTests(unittest.TestCase):
    def _running_boundary(self, *, wake_at: datetime | None = None):
        self.assertTrue(
            hasattr(factory, "_cooperative_later_cycle_recheck"),
            "cooperative later-cycle recheck helper must exist",
        )
        self.assertTrue(
            hasattr(factory.FourTokenAdmissionBoundaryResult, "__dataclass_fields__")
            and "attempt_wake_at" in factory.FourTokenAdmissionBoundaryResult.__dataclass_fields__,
            "boundary result must expose an optional later-cycle wake",
        )
        return factory.FourTokenAdmissionBoundaryResult(
            disposition=object(),
            admitted=False,
            attempt_id="attempt-2",
            attempt_state="RUNNING",
            attempt_wake_at=wake_at,
        )

    def test_running_quantum_without_refresh_requires_immediate_recheck(self) -> None:
        boundary = self._running_boundary()
        proof_deadline = datetime(2026, 8, 20, 2, 0, tzinfo=timezone.utc)
        should_recheck, wake_at = factory._cooperative_later_cycle_recheck(
            boundary,
            next_due_work_at=proof_deadline - timedelta(minutes=5),
            proof_deadline=proof_deadline,
        )
        self.assertTrue(should_recheck)
        self.assertIsNone(wake_at)

    def test_running_refresh_wait_wakes_at_nearest_lifecycle_deadline(self) -> None:
        base = datetime(2026, 8, 20, 1, 30, tzinfo=timezone.utc)
        boundary = self._running_boundary(wake_at=base + timedelta(minutes=10))
        lifecycle_due = base + timedelta(minutes=2)
        should_recheck, wake_at = factory._cooperative_later_cycle_recheck(
            boundary,
            next_due_work_at=lifecycle_due,
            proof_deadline=base + timedelta(minutes=20),
        )
        self.assertTrue(should_recheck)
        self.assertEqual(wake_at, lifecycle_due)

    def test_running_refresh_wait_is_capped_by_proof_deadline(self) -> None:
        base = datetime(2026, 8, 20, 1, 30, tzinfo=timezone.utc)
        boundary = self._running_boundary(wake_at=base + timedelta(minutes=10))
        proof_deadline = base + timedelta(minutes=3)
        should_recheck, wake_at = factory._cooperative_later_cycle_recheck(
            boundary,
            next_due_work_at=base + timedelta(minutes=5),
            proof_deadline=proof_deadline,
        )
        self.assertTrue(should_recheck)
        self.assertEqual(wake_at, proof_deadline)

    def test_non_running_attempt_does_not_reenter_acquisition_loop(self) -> None:
        self.assertTrue(hasattr(factory, "_cooperative_later_cycle_recheck"))
        boundary = factory.FourTokenAdmissionBoundaryResult(
            disposition=object(),
            admitted=False,
            attempt_id="attempt-2",
            attempt_state="NO_PAIR_AVAILABLE",
        )
        should_recheck, wake_at = factory._cooperative_later_cycle_recheck(
            boundary,
            next_due_work_at=None,
            proof_deadline=datetime(2026, 8, 20, 2, 0, tzinfo=timezone.utc),
        )
        self.assertFalse(should_recheck)
        self.assertIsNone(wake_at)

    def _wait_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:")
        connection.execute(
            """
            CREATE TABLE printer_pre_lifecycle_discovery_refresh_waits (
                wait_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                cycle_id TEXT NOT NULL,
                supervision_id TEXT NOT NULL,
                scheduler_job_id INTEGER NOT NULL,
                refresh_ordinal INTEGER NOT NULL,
                wait_state TEXT NOT NULL,
                scheduled_for TEXT NOT NULL,
                acquisition_deadline_at TEXT NOT NULL,
                first_terminal_cause TEXT,
                terminal_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        return connection

    def _insert_wait(
        self,
        connection: sqlite3.Connection,
        *,
        wait_id: str,
        ordinal: int,
        state: str,
        scheduled_for: datetime,
    ) -> None:
        timestamp = datetime(2026, 8, 20, 1, 30, tzinfo=timezone.utc).isoformat()
        connection.execute(
            """
            INSERT INTO printer_pre_lifecycle_discovery_refresh_waits (
                wait_id, campaign_id, run_id, cycle_id, supervision_id,
                scheduler_job_id, refresh_ordinal, wait_state, scheduled_for,
                acquisition_deadline_at, created_at, updated_at
            ) VALUES (?, 'campaign', 'run', 'cycle-2', 'supervision', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                wait_id,
                ordinal,
                ordinal,
                state,
                scheduled_for.isoformat(),
                (scheduled_for + timedelta(minutes=30)).isoformat(),
                timestamp,
                timestamp,
            ),
        )
        connection.commit()

    def test_active_refresh_wake_is_none_without_active_wait(self) -> None:
        self.assertTrue(
            hasattr(factory, "_active_later_cycle_refresh_wake_at"),
            "later-cycle refresh wake resolver must exist",
        )
        connection = self._wait_connection()
        try:
            wake_at = factory._active_later_cycle_refresh_wake_at(
                connection,
                campaign_id="campaign",
                run_id="run",
                cycle_id="cycle-2",
            )
            self.assertIsNone(wake_at)
        finally:
            connection.close()

    def test_active_refresh_wake_returns_exact_waiting_due_time(self) -> None:
        self.assertTrue(hasattr(factory, "_active_later_cycle_refresh_wake_at"))
        connection = self._wait_connection()
        due = datetime(2026, 8, 20, 1, 40, tzinfo=timezone.utc)
        try:
            self._insert_wait(
                connection,
                wait_id="wait-1",
                ordinal=1,
                state="WAITING",
                scheduled_for=due,
            )
            wake_at = factory._active_later_cycle_refresh_wake_at(
                connection,
                campaign_id="campaign",
                run_id="run",
                cycle_id="cycle-2",
            )
            self.assertEqual(wake_at, due)
        finally:
            connection.close()

    def test_active_refresh_wake_reenters_immediately_on_claimed_wait(self) -> None:
        self.assertTrue(hasattr(factory, "_active_later_cycle_refresh_wake_at"))
        due = datetime(2026, 8, 20, 1, 40, tzinfo=timezone.utc)
        claimed = self._wait_connection()
        try:
            self._insert_wait(
                claimed,
                wait_id="wait-claimed",
                ordinal=1,
                state="CLAIMED",
                scheduled_for=due,
            )
            wake_at = factory._active_later_cycle_refresh_wake_at(
                claimed,
                campaign_id="campaign",
                run_id="run",
                cycle_id="cycle-2",
            )
            self.assertIsNone(wake_at)
        finally:
            claimed.close()

    def test_active_refresh_wake_fails_closed_on_ambiguous_wait(self) -> None:
        self.assertTrue(hasattr(factory, "_active_later_cycle_refresh_wake_at"))
        due = datetime(2026, 8, 20, 1, 40, tzinfo=timezone.utc)

        ambiguous = self._wait_connection()
        try:
            self._insert_wait(
                ambiguous,
                wait_id="wait-1",
                ordinal=1,
                state="WAITING",
                scheduled_for=due,
            )
            self._insert_wait(
                ambiguous,
                wait_id="wait-2",
                ordinal=2,
                state="WAITING",
                scheduled_for=due + timedelta(minutes=1),
            )
            with self.assertRaises(ValueError):
                factory._active_later_cycle_refresh_wake_at(
                    ambiguous,
                    campaign_id="campaign",
                    run_id="run",
                    cycle_id="cycle-2",
                )
        finally:
            ambiguous.close()

    def test_running_recheck_occurs_before_stale_pending_terminal_branch(self) -> None:
        source = inspect.getsource(factory.run_one_command_15m_factory)
        boundary_pos = source.index("_run_four_token_admission_boundary(")
        pending_terminal_pos = source.index("if pending is None:", boundary_pos)
        self.assertIn("_cooperative_later_cycle_recheck(", source[boundary_pos:pending_terminal_pos])


if __name__ == "__main__":
    unittest.main()

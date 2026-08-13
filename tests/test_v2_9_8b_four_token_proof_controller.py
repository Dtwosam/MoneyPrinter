"""Focused non-network tests for the four-token proof admission controller."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import sqlite3
import unittest

from printer_v1.operator_cli.four_token_proof_controller import (
    FourTokenProofControllerError,
    LaterCycleDiscoveryResult,
    attempt_second_cycle_admission,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
)


class FourTokenProofControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE printer_memory_factory_campaign_runs(
                run_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                run_state TEXT NOT NULL,
                authoritative_run_id TEXT
            );
            CREATE TABLE printer_memory_factory_campaign_cycles(
                cycle_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                cycle_ordinal INTEGER NOT NULL,
                cycle_state TEXT NOT NULL,
                first_terminal_cause TEXT,
                terminal_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(run_id, cycle_ordinal)
            );
            CREATE TABLE printer_memory_factory_campaign_token_slots(
                token_slot_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                cycle_id TEXT NOT NULL,
                slot_ordinal INTEGER NOT NULL,
                token_identity TEXT NOT NULL,
                token_row_id INTEGER NOT NULL,
                mint_identity TEXT NOT NULL,
                pair_identity TEXT NOT NULL,
                pair_row_id INTEGER NOT NULL,
                lifecycle_identity TEXT NOT NULL,
                token_state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        self.conn.execute(
            "INSERT INTO printer_memory_factory_campaign_runs VALUES (?,?,?,?)",
            ("campaign-run-1", "campaign-1", "RUNNING", "factory-1"),
        )
        self.conn.execute(
            """INSERT INTO printer_memory_factory_campaign_cycles(
                   cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
                   created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?)""",
            (
                "cycle-1", "campaign-1", "campaign-run-1", 1, "TRACKING",
                self.start.isoformat(), self.start.isoformat(),
            ),
        )
        for ordinal in (1, 2):
            self.conn.execute(
                """INSERT INTO printer_memory_factory_campaign_token_slots(
                       token_slot_id,campaign_id,run_id,cycle_id,slot_ordinal,
                       token_identity,token_row_id,mint_identity,pair_identity,
                       pair_row_id,lifecycle_identity,token_state,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    f"slot-1-{ordinal}", "campaign-1", "campaign-run-1", "cycle-1",
                    ordinal, f"token-1-{ordinal}", ordinal, f"mint-1-{ordinal}",
                    f"pair-1-{ordinal}", 100 + ordinal, f"lifecycle-1-{ordinal}",
                    "WINDOW_15M_ACTIVE", self.start.isoformat(), self.start.isoformat(),
                ),
            )
        self.conn.commit()
        self.calls: list[object] = []

    def tearDown(self) -> None:
        self.conn.close()

    def _successful_discovery(self, request):
        self.calls.append(request)
        at = request.requested_at.isoformat()
        for ordinal in (1, 2):
            self.conn.execute(
                """INSERT INTO printer_memory_factory_campaign_token_slots(
                       token_slot_id,campaign_id,run_id,cycle_id,slot_ordinal,
                       token_identity,token_row_id,mint_identity,pair_identity,
                       pair_row_id,lifecycle_identity,token_state,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    f"slot-2-{ordinal}", "campaign-1", "campaign-run-1", request.cycle_id,
                    ordinal, f"token-2-{ordinal}", 10 + ordinal, f"mint-2-{ordinal}",
                    f"pair-2-{ordinal}", 200 + ordinal, f"lifecycle-2-{ordinal}",
                    "SELECTED", at, at,
                ),
            )
        self.conn.execute(
            "UPDATE printer_memory_factory_campaign_cycles SET cycle_state='TRACKING' "
            "WHERE cycle_id=?",
            (request.cycle_id,),
        )
        self.conn.commit()
        return LaterCycleDiscoveryResult(
            cycle_id=request.cycle_id,
            terminal_status="COMPLETED",
            first_terminal_cause="DISCOVERY_CYCLE_COMPLETED",
            selected_count=2,
            selection_batch_id=f"origin-activated:{request.cycle_id}",
            source_calls=2,
            scheduler_work=11,
        )

    def test_before_spacing_defers_without_reservation_or_callback(self) -> None:
        result = attempt_second_cycle_admission(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            first_cycle_id="cycle-1",
            now=self.start + timedelta(seconds=299),
            next_due_lifecycle_at=self.start + timedelta(minutes=10),
            health=MultiCycleAdmissionHealth(),
            discovery_callback=self._successful_discovery,
        )
        self.assertEqual(result.status, "DEFERRED")
        self.assertEqual(result.reason, "MINIMUM_ADMISSION_SPACING_NOT_ELAPSED")
        self.assertEqual(self.calls, [])
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles").fetchone()[0],
            1,
        )

    def test_due_lifecycle_work_defers_before_source_callback(self) -> None:
        boundary = self.start + timedelta(seconds=300)
        result = attempt_second_cycle_admission(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            first_cycle_id="cycle-1",
            now=boundary,
            next_due_lifecycle_at=boundary,
            health=MultiCycleAdmissionHealth(),
            discovery_callback=self._successful_discovery,
        )
        self.assertEqual(result.status, "DEFERRED")
        self.assertEqual(result.reason, "LIFECYCLE_WORK_DUE_FIRST")
        self.assertEqual(self.calls, [])

    def test_unhealthy_budget_gate_defers_without_source_callback(self) -> None:
        result = attempt_second_cycle_admission(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            first_cycle_id="cycle-1",
            now=self.start + timedelta(seconds=300),
            next_due_lifecycle_at=self.start + timedelta(minutes=10),
            health=replace(MultiCycleAdmissionHealth(), source_budget_available=False),
            discovery_callback=self._successful_discovery,
        )
        self.assertEqual(result.status, "DEFERRED")
        self.assertEqual(result.reason, "source_budget_unavailable")
        self.assertEqual(self.calls, [])

    def test_lawful_second_cycle_calls_same_owner_once_and_validates_two_slots(self) -> None:
        result = attempt_second_cycle_admission(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            first_cycle_id="cycle-1",
            now=self.start + timedelta(seconds=300),
            next_due_lifecycle_at=self.start + timedelta(minutes=10),
            health=MultiCycleAdmissionHealth(),
            discovery_callback=self._successful_discovery,
        )
        self.assertEqual(result.status, "ADMITTED")
        self.assertEqual(result.cycle_id, "cycle-1-2")
        self.assertEqual(result.selected_count, 2)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0].factory_run_id, "factory-1")
        self.assertEqual(self.calls[0].cycle_ordinal, 2)

    def test_no_third_cycle_or_repeat_second_cycle_attempt(self) -> None:
        first = attempt_second_cycle_admission(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            first_cycle_id="cycle-1",
            now=self.start + timedelta(seconds=300),
            next_due_lifecycle_at=self.start + timedelta(minutes=10),
            health=MultiCycleAdmissionHealth(),
            discovery_callback=self._successful_discovery,
        )
        self.assertEqual(first.status, "ADMITTED")
        second = attempt_second_cycle_admission(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            first_cycle_id="cycle-1",
            now=self.start + timedelta(seconds=600),
            next_due_lifecycle_at=self.start + timedelta(minutes=20),
            health=MultiCycleAdmissionHealth(),
            discovery_callback=self._successful_discovery,
        )
        self.assertEqual(second.status, "COMPLETE")
        self.assertEqual(second.reason, "FOUR_TOKEN_PROOF_CYCLE_CEILING_REACHED")
        self.assertEqual(len(self.calls), 1)

    def test_insufficient_pool_terminalizes_empty_reserved_cycle_only(self) -> None:
        def blocked(request):
            self.calls.append(request)
            return LaterCycleDiscoveryResult(
                cycle_id=request.cycle_id,
                terminal_status="FAILED",
                first_terminal_cause="INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL",
                selected_count=0,
                selection_batch_id=None,
                source_calls=2,
                scheduler_work=9,
            )

        result = attempt_second_cycle_admission(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            first_cycle_id="cycle-1",
            now=self.start + timedelta(seconds=300),
            next_due_lifecycle_at=self.start + timedelta(minutes=10),
            health=MultiCycleAdmissionHealth(),
            discovery_callback=blocked,
        )
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason, "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL")
        cycle2 = self.conn.execute(
            "SELECT cycle_state,first_terminal_cause FROM printer_memory_factory_campaign_cycles "
            "WHERE cycle_ordinal=2"
        ).fetchone()
        self.assertEqual(cycle2["cycle_state"], "TERMINAL_BLOCKED")
        run = self.conn.execute(
            "SELECT run_state FROM printer_memory_factory_campaign_runs"
        ).fetchone()
        self.assertEqual(run["run_state"], "RUNNING")

    def test_partial_or_wrong_cycle_discovery_result_fails_closed(self) -> None:
        def partial(request):
            self.calls.append(request)
            return LaterCycleDiscoveryResult(
                cycle_id=request.cycle_id,
                terminal_status="COMPLETED",
                first_terminal_cause="DISCOVERY_CYCLE_COMPLETED",
                selected_count=1,
                selection_batch_id="bad",
                source_calls=2,
                scheduler_work=10,
            )

        with self.assertRaises(FourTokenProofControllerError):
            attempt_second_cycle_admission(
                self.conn,
                campaign_id="campaign-1",
                campaign_run_id="campaign-run-1",
                factory_run_id="factory-1",
                first_cycle_id="cycle-1",
                now=self.start + timedelta(seconds=300),
                next_due_lifecycle_at=self.start + timedelta(minutes=10),
                health=MultiCycleAdmissionHealth(),
                discovery_callback=partial,
            )


if __name__ == "__main__":
    unittest.main()

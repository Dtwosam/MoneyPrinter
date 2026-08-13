"""Focused proof-only adapter tests for the four-token factory integration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3
import unittest

from printer_v1.operator_cli.four_token_factory_adapter import (
    FourTokenFactoryAdapterError,
    build_cycle_lifecycle_ownership_context,
    four_token_scaled_capacity_contract,
    reserve_second_proof_cycle,
    terminalize_unfilled_reserved_cycle,
    validate_second_cycle_atomic_activation,
)


class FourTokenFactoryAdapterTests(unittest.TestCase):
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
            CREATE TABLE printer_memory_factory_campaign_scheduler_work(
                scheduler_work_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                cycle_id TEXT NOT NULL,
                token_slot_id TEXT,
                window_id TEXT,
                scheduler_job_id INTEGER,
                factory_run_id TEXT,
                ownership_contract_version TEXT NOT NULL,
                work_scope TEXT NOT NULL,
                stage_id TEXT,
                target_category TEXT,
                target_identity TEXT
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
                    f"slot-cycle-1-{ordinal}", "campaign-1", "campaign-run-1",
                    "cycle-1", ordinal, f"token-{ordinal}", ordinal,
                    f"mint-{ordinal}", f"pair-{ordinal}", 100 + ordinal,
                    f"lifecycle-{ordinal}", "WINDOW_15M_ACTIVE",
                    self.start.isoformat(), self.start.isoformat(),
                ),
            )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_four_token_capacity_contract_is_derived_and_does_not_change_rates(self) -> None:
        contract = four_token_scaled_capacity_contract()
        self.assertEqual(contract["configured_through_4h_tokens"], 4)
        self.assertEqual(contract["configured_active_cycles"], 2)
        self.assertEqual(contract["tokens_per_cycle"], 2)
        self.assertFalse(contract["long_windows_activated"])
        self.assertEqual(contract["automatic_retries"], 0)
        self.assertFalse(contract["endpoint_rotation"])

    def test_second_cycle_cannot_be_reserved_before_300_seconds(self) -> None:
        with self.assertRaises(FourTokenFactoryAdapterError):
            reserve_second_proof_cycle(
                self.conn,
                campaign_id="campaign-1",
                campaign_run_id="campaign-run-1",
                factory_run_id="factory-1",
                first_cycle_id="cycle-1",
                now=self.start + timedelta(seconds=299),
            )
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles"
            ).fetchone()[0],
            1,
        )

    def test_second_cycle_reservation_creates_only_planned_cycle_not_slots(self) -> None:
        result = reserve_second_proof_cycle(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            first_cycle_id="cycle-1",
            now=self.start + timedelta(seconds=300),
        )
        self.assertEqual(result.cycle_id, "cycle-1-2")
        self.assertEqual(result.cycle_ordinal, 2)
        self.assertEqual(result.cycle_state, "PLANNED")
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots "
                "WHERE cycle_id='cycle-1-2'"
            ).fetchone()[0],
            0,
        )

    def test_second_cycle_reservation_requires_one_factory_run_and_exact_first_pair(self) -> None:
        self.conn.execute(
            "UPDATE printer_memory_factory_campaign_runs SET authoritative_run_id='factory-wrong'"
        )
        with self.assertRaises(FourTokenFactoryAdapterError):
            reserve_second_proof_cycle(
                self.conn,
                campaign_id="campaign-1",
                campaign_run_id="campaign-run-1",
                factory_run_id="factory-1",
                first_cycle_id="cycle-1",
                now=self.start + timedelta(seconds=300),
            )

    def test_existing_second_cycle_blocks_duplicate_reservation(self) -> None:
        reserve_second_proof_cycle(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            first_cycle_id="cycle-1",
            now=self.start + timedelta(seconds=300),
        )
        with self.assertRaises(FourTokenFactoryAdapterError):
            reserve_second_proof_cycle(
                self.conn,
                campaign_id="campaign-1",
                campaign_run_id="campaign-run-1",
                factory_run_id="factory-1",
                first_cycle_id="cycle-1",
                now=self.start + timedelta(seconds=600),
            )

    def test_atomic_activation_validation_requires_two_distinct_new_pairs(self) -> None:
        reserved = reserve_second_proof_cycle(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            first_cycle_id="cycle-1",
            now=self.start + timedelta(seconds=300),
        )
        admitted_at = self.start + timedelta(seconds=300)
        for ordinal in (1, 2):
            self.conn.execute(
                """INSERT INTO printer_memory_factory_campaign_token_slots(
                       token_slot_id,campaign_id,run_id,cycle_id,slot_ordinal,
                       token_identity,token_row_id,mint_identity,pair_identity,
                       pair_row_id,lifecycle_identity,token_state,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    f"slot-cycle-2-{ordinal}", "campaign-1", "campaign-run-1",
                    reserved.cycle_id, ordinal, f"token-2-{ordinal}", 10 + ordinal,
                    f"mint-2-{ordinal}", f"pair-2-{ordinal}", 200 + ordinal,
                    f"lifecycle-2-{ordinal}", "SELECTED",
                    admitted_at.isoformat(), admitted_at.isoformat(),
                ),
            )
        self.conn.commit()
        result = validate_second_cycle_atomic_activation(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            cycle_id=reserved.cycle_id,
        )
        self.assertEqual(result["slot_count"], 2)
        self.assertEqual(result["slot_ordinals"], (1, 2))
        self.assertTrue(result["distinct_from_first_cycle"])

    def test_unfilled_reserved_cycle_can_terminalize_without_touching_shared_run(self) -> None:
        reserved = reserve_second_proof_cycle(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            first_cycle_id="cycle-1",
            now=self.start + timedelta(seconds=300),
        )
        result = terminalize_unfilled_reserved_cycle(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            cycle_id=reserved.cycle_id,
            cause="INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL",
            now=self.start + timedelta(seconds=301),
        )
        self.assertEqual(result["cycle_state"], "TERMINAL_BLOCKED")
        run = self.conn.execute(
            "SELECT run_state,authoritative_run_id FROM printer_memory_factory_campaign_runs"
        ).fetchone()
        self.assertEqual(run["run_state"], "RUNNING")
        self.assertEqual(run["authoritative_run_id"], "factory-1")

    def test_scheduler_owned_job_builds_existing_two_token_context_for_cycle_2(self) -> None:
        reserved = reserve_second_proof_cycle(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            first_cycle_id="cycle-1",
            now=self.start + timedelta(seconds=300),
        )
        self.conn.execute(
            """INSERT INTO printer_memory_factory_campaign_scheduler_work(
                   scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,
                   window_id,scheduler_job_id,factory_run_id,
                   ownership_contract_version,work_scope,stage_id,
                   target_category,target_identity
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "work-201", "campaign-1", "campaign-run-1", reserved.cycle_id,
                "slot-cycle-2-1", "window-cycle-2-1", 201, "factory-1",
                "V2_STAGE_SCOPED", "WINDOW_LIFECYCLE", "WINDOW_15M_SLOT_1",
                "CAMPAIGN_WINDOW", "window-cycle-2-1",
            ),
        )
        context = build_cycle_lifecycle_ownership_context(
            self.conn,
            scheduler_job_id=201,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            configuration_id="configuration-1",
            factory_run_id="factory-1",
        )
        self.assertEqual(context.cycle_id, reserved.cycle_id)
        self.assertEqual(context.factory_run_id, "factory-1")
        self.assertEqual(context.expected_token_capacity, 2)


if __name__ == "__main__":
    unittest.main()

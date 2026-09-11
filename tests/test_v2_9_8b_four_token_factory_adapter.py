"""Focused proof-only adapter tests for the four-token factory integration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3
import unittest
from unittest.mock import patch

from printer_v1.operator_cli.campaign_full_run_accounting import (
    project_four_token_selection_provenance,
)

from printer_v1.operator_cli.four_token_factory_adapter import (
    FourTokenFactoryAdapterError,
    build_cycle_lifecycle_ownership_context,
    four_token_cycle_through_4h_validation,
    four_token_scaled_capacity_contract,
    reconcile_four_token_cycle_terminal,
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

    def test_selection_provenance_reproves_both_cycle_inputs(self) -> None:
        self.conn.executescript(
            """
            ALTER TABLE printer_memory_factory_campaign_token_slots
                ADD COLUMN tracking_queue_id INTEGER;
            CREATE TABLE printer_memory_factory_runs(
                run_id TEXT PRIMARY KEY,
                selection_batch_id TEXT
            );
            CREATE TABLE printer_selection_batch_items(
                id INTEGER PRIMARY KEY,
                batch_id TEXT NOT NULL,
                item_status TEXT NOT NULL,
                token_id INTEGER,
                pair_id INTEGER,
                token_mint TEXT NOT NULL,
                pair_address TEXT NOT NULL,
                tracking_lane TEXT
            );
            CREATE TABLE printer_tracking_queue(
                id INTEGER PRIMARY KEY,
                token_id INTEGER NOT NULL,
                pair_id INTEGER,
                tracking_lane TEXT NOT NULL
            );
            CREATE TABLE printer_pre_admission_discovery_attempts(
                attempt_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                campaign_run_id TEXT NOT NULL,
                authoritative_factory_run_id TEXT NOT NULL,
                proposed_cycle_id TEXT NOT NULL,
                proposed_cycle_ordinal INTEGER NOT NULL,
                attempt_state TEXT NOT NULL,
                consumed_cycle_id TEXT
            );
            CREATE TABLE printer_pre_admission_discovery_attempt_items(
                attempt_id TEXT NOT NULL,
                slot_ordinal INTEGER NOT NULL,
                token_identity TEXT NOT NULL,
                token_row_id INTEGER NOT NULL,
                mint_identity TEXT NOT NULL,
                pair_identity TEXT NOT NULL,
                pair_row_id INTEGER NOT NULL,
                lifecycle_identity TEXT NOT NULL,
                frozen_tracking_lane TEXT
            );
            """
        )
        self.conn.execute(
            "INSERT INTO printer_memory_factory_runs VALUES (?,?)",
            ("factory-1", "cycle-1-selected"),
        )
        for ordinal in (1, 2):
            queue_id = 200 + ordinal
            self.conn.execute(
                "INSERT INTO printer_tracking_queue VALUES (?,?,?,?)",
                (queue_id, ordinal, 100 + ordinal, "TRACK_NORMAL"),
            )
            self.conn.execute(
                "UPDATE printer_memory_factory_campaign_token_slots "
                "SET tracking_queue_id=? WHERE token_slot_id=?",
                (queue_id, f"slot-cycle-1-{ordinal}"),
            )
            self.conn.execute(
                "INSERT INTO printer_selection_batch_items "
                "(batch_id,item_status,token_id,pair_id,token_mint,pair_address,"
                "tracking_lane) VALUES "
                "('cycle-1-selected','SELECTED',?,?,?,?,?)",
                (
                    ordinal,
                    100 + ordinal,
                    f"mint-{ordinal}",
                    f"pair-{ordinal}",
                    "TRACK_NORMAL",
                ),
            )

        self.conn.execute(
            """INSERT INTO printer_memory_factory_campaign_cycles(
                   cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
                   created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?)""",
            (
                "cycle-2", "campaign-1", "campaign-run-1", 2, "TRACKING",
                self.start.isoformat(), self.start.isoformat(),
            ),
        )
        for ordinal,row_id in ((1,3),(2,4)):
            queue_id = 300 + ordinal
            self.conn.execute(
                "INSERT INTO printer_tracking_queue VALUES (?,?,?,?)",
                (queue_id, row_id, 100 + row_id, "TRACK_FAST"),
            )
            self.conn.execute(
                """INSERT INTO printer_memory_factory_campaign_token_slots(
                       token_slot_id,campaign_id,run_id,cycle_id,slot_ordinal,
                       token_identity,token_row_id,mint_identity,pair_identity,
                       pair_row_id,lifecycle_identity,token_state,created_at,updated_at,
                       tracking_queue_id
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    f"slot-cycle-2-{ordinal}", "campaign-1", "campaign-run-1",
                    "cycle-2", ordinal, f"token-{row_id}", row_id,
                    f"mint-{row_id}", f"pair-{row_id}", 100 + row_id,
                    f"lifecycle-{row_id}", "WINDOW_15M_ACTIVE",
                    self.start.isoformat(), self.start.isoformat(), queue_id,
                ),
            )
        self.conn.execute(
            """INSERT INTO printer_pre_admission_discovery_attempts
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                "attempt-2", "campaign-1", "campaign-run-1", "factory-1",
                "cycle-2", 2, "CONSUMED", "cycle-2",
            ),
        )
        for ordinal,row_id in ((1,3),(2,4)):
            self.conn.execute(
                """INSERT INTO printer_pre_admission_discovery_attempt_items
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    "attempt-2", ordinal, f"token-{row_id}", row_id,
                    f"mint-{row_id}", f"pair-{row_id}", 100 + row_id,
                    f"lifecycle-{row_id}", "TRACK_FAST",
                ),
            )
        self.conn.commit()
        rows = self.conn.execute(
            "SELECT cycle_id,cycle_ordinal FROM "
            "printer_memory_factory_campaign_cycles ORDER BY cycle_ordinal"
        ).fetchall()
        result = project_four_token_selection_provenance(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            cycle_rows=rows,
        )
        self.assertTrue(result["exact"], result)
        self.assertTrue(result["cycle_1"]["exact"])
        self.assertTrue(result["cycle_2"]["exact"])

        self.conn.execute(
            "UPDATE printer_selection_batch_items SET pair_address='wrong-pair' "
            "WHERE batch_id='cycle-1-selected' AND token_id=1"
        )
        broken = project_four_token_selection_provenance(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            cycle_rows=rows,
        )
        self.assertFalse(broken["exact"])
        self.assertIn(
            "CYCLE1_SELECTION_SLOT_PROVENANCE_MISMATCH",
            broken["reasons"],
        )

    def test_four_token_strict_4h_validation_rejects_generic_selective_success(
        self,
    ) -> None:
        generic_complete_one_4h = {
            "enabled": True,
            "complete": True,
            "reasons": [],
            "aggregate_state": "HANDOFF_COMMITTED",
            "expected_continuation_count": 1,
            "window_count": 1,
            "per_token": [
                {"token_slot_id": "slot-1", "outcome": "SUCCEEDED"},
                {"token_slot_id": "slot-2", "outcome": "INELIGIBLE"},
            ],
            "eligible_window_details": [
                {
                    "token_slot_id": "slot-1",
                    "token_state": "WINDOW_4H_CLOSED",
                    "window_state": "DIRTY",
                    "memory_window_row_id": 91,
                    "reasons": [],
                }
            ],
        }
        with patch(
            "printer_v1.operator_cli.one_command_15m_factory."
            "_standard_campaign_four_hour_terminal_validation",
            return_value=generic_complete_one_4h,
        ):
            result = four_token_cycle_through_4h_validation(
                self.conn,
                campaign_id="campaign-1",
                campaign_run_id="campaign-run-1",
                factory_run_id="factory-1",
                cycle_id="cycle-1",
            )
        self.assertFalse(result["four_token_through_4h_complete"])
        self.assertIn(
            "FOUR_TOKEN_CYCLE_REQUIRES_TWO_4H_CONTINUATIONS",
            result["reasons"],
        )
        self.assertIn(
            "FOUR_TOKEN_CYCLE_REQUIRES_TWO_SUCCEEDED_4H_OUTCOMES",
            result["reasons"],
        )

    def test_four_token_strict_4h_validation_rejects_nonclean_terminal_memories(
        self,
    ) -> None:
        strict_complete = {
            "enabled": True,
            "complete": True,
            "reasons": [],
            "aggregate_state": "HANDOFF_COMMITTED",
            "expected_continuation_count": 2,
            "window_count": 2,
            "per_token": [
                {"token_slot_id": "slot-cycle-1-1", "outcome": "SUCCEEDED"},
                {"token_slot_id": "slot-cycle-1-2", "outcome": "SUCCEEDED"},
            ],
            "eligible_window_details": [
                {
                    "token_slot_id": "slot-cycle-1-1",
                    "token_state": "WINDOW_4H_CLOSED",
                    "window_state": "DIRTY",
                    "memory_window_row_id": 91,
                    "reasons": [],
                },
                {
                    "token_slot_id": "slot-cycle-1-2",
                    "token_state": "WINDOW_4H_CLOSED",
                    "window_state": "NO_PROMOTION",
                    "memory_window_row_id": 92,
                    "reasons": [],
                },
            ],
        }
        with patch(
            "printer_v1.operator_cli.one_command_15m_factory."
            "_standard_campaign_four_hour_terminal_validation",
            return_value=strict_complete,
        ):
            result = four_token_cycle_through_4h_validation(
                self.conn,
                campaign_id="campaign-1",
                campaign_run_id="campaign-run-1",
                factory_run_id="factory-1",
                cycle_id="cycle-1",
            )
        self.assertFalse(result["four_token_through_4h_complete"])
        self.assertIn(
            "FOUR_TOKEN_4H_MEMORY_NOT_CLEAN:slot-cycle-1-1",
            result["reasons"],
        )
        self.assertIn(
            "FOUR_TOKEN_4H_MEMORY_NOT_CLEAN:slot-cycle-1-2",
            result["reasons"],
        )

    def test_four_token_strict_4h_validation_rejects_foreign_slot_set(self) -> None:
        strict_mismatch = {
            "enabled": True,
            "complete": True,
            "reasons": [],
            "aggregate_state": "HANDOFF_COMMITTED",
            "expected_continuation_count": 2,
            "window_count": 2,
            "per_token": [
                {"token_slot_id": "slot-cycle-1-1", "outcome": "SUCCEEDED"},
                {"token_slot_id": "slot-cycle-1-2", "outcome": "SUCCEEDED"},
            ],
            "eligible_window_details": [
                {
                    "token_slot_id": "slot-cycle-1-1",
                    "token_state": "WINDOW_4H_CLOSED",
                    "window_state": "DIRTY",
                    "memory_window_row_id": 91,
                    "reasons": [],
                },
                {
                    "token_slot_id": "foreign-slot",
                    "token_state": "WINDOW_4H_CLOSED",
                    "window_state": "NO_PROMOTION",
                    "memory_window_row_id": 92,
                    "reasons": [],
                },
            ],
        }
        with patch(
            "printer_v1.operator_cli.one_command_15m_factory."
            "_standard_campaign_four_hour_terminal_validation",
            return_value=strict_mismatch,
        ):
            result = four_token_cycle_through_4h_validation(
                self.conn,
                campaign_id="campaign-1",
                campaign_run_id="campaign-run-1",
                factory_run_id="factory-1",
                cycle_id="cycle-1",
            )
        self.assertFalse(result["four_token_through_4h_complete"])
        self.assertIn(
            "FOUR_TOKEN_CYCLE_4H_WINDOW_SLOT_SET_MISMATCH",
            result["reasons"],
        )
        self.assertIn(
            "FOUR_TOKEN_CYCLE_PROGRESSION_WINDOW_SLOT_SET_MISMATCH",
            result["reasons"],
        )

    def test_terminal_cross_cycle_identity_requires_four_distinct_targets(self) -> None:
        from printer_v1.operator_cli.campaign_full_run_accounting import (
            four_token_cross_cycle_identity_exact,
        )

        cycles = [
            {
                "cycle_ordinal": 1,
                "tokens": [
                    {
                        "token_slot_id": "c1-s1",
                        "token_row_id": 1,
                        "pair_row_id": 101,
                        "mint_identity": "mint-1",
                        "pair_identity": "pair-1",
                    },
                    {
                        "token_slot_id": "c1-s2",
                        "token_row_id": 2,
                        "pair_row_id": 102,
                        "mint_identity": "mint-2",
                        "pair_identity": "pair-2",
                    },
                ],
            },
            {
                "cycle_ordinal": 2,
                "tokens": [
                    {
                        "token_slot_id": "c2-s1",
                        "token_row_id": 3,
                        "pair_row_id": 103,
                        "mint_identity": "mint-3",
                        "pair_identity": "pair-3",
                    },
                    {
                        "token_slot_id": "c2-s2",
                        "token_row_id": 4,
                        "pair_row_id": 104,
                        "mint_identity": "mint-4",
                        "pair_identity": "pair-4",
                    },
                ],
            },
        ]
        self.assertTrue(four_token_cross_cycle_identity_exact(cycles))
        cycles[1]["tokens"][0]["mint_identity"] = "mint-1"
        self.assertFalse(four_token_cross_cycle_identity_exact(cycles))

    def test_four_token_terminal_refuses_generic_success_without_two_4h_memories(
        self,
    ) -> None:
        with patch(
            "printer_v1.operator_cli.four_token_factory_adapter."
            "derive_cycle_terminal_accounting_result",
            return_value={
                "execution_outcome": "TERMINAL_SUCCESS",
                "primary_fault": None,
            },
        ), patch(
            "printer_v1.operator_cli.four_token_factory_adapter."
            "four_token_cycle_through_4h_validation",
            return_value={
                "four_token_through_4h_complete": False,
                "reasons": ["FOUR_TOKEN_CYCLE_REQUIRES_TWO_4H_CONTINUATIONS"],
            },
        ):
            with self.assertRaises(FourTokenFactoryAdapterError):
                reconcile_four_token_cycle_terminal(
                    self.conn,
                    campaign_id="campaign-1",
                    campaign_run_id="campaign-run-1",
                    factory_run_id="factory-1",
                    cycle_id="cycle-1",
                    configuration_id="configuration-1",
                    now=self.start,
                )
        state = self.conn.execute(
            "SELECT cycle_state FROM printer_memory_factory_campaign_cycles "
            "WHERE cycle_id='cycle-1'"
        ).fetchone()[0]
        self.assertEqual(state, "TRACKING")

    def test_completed_cycle1_with_no_cycle2_admission_becomes_safe_stop(self) -> None:
        from printer_v1.operator_cli.one_command_15m_factory import (
            _resolve_four_token_no_accounting_shared_terminal,
        )

        self.conn.execute(
            """CREATE TABLE printer_pre_admission_discovery_attempts(
                   attempt_id TEXT PRIMARY KEY,
                   campaign_id TEXT NOT NULL,
                   campaign_run_id TEXT NOT NULL,
                   authoritative_factory_run_id TEXT NOT NULL,
                   proposed_cycle_ordinal INTEGER NOT NULL,
                   attempt_state TEXT NOT NULL,
                   first_terminal_cause TEXT,
                   consumed_cycle_id TEXT
               )"""
        )
        self.conn.execute(
            """INSERT INTO printer_pre_admission_discovery_attempts(
                   attempt_id,campaign_id,campaign_run_id,
                   authoritative_factory_run_id,proposed_cycle_ordinal,
                   attempt_state,first_terminal_cause,consumed_cycle_id
               ) VALUES (
                   'attempt-2','campaign-1','campaign-run-1','factory-1',2,
                   'NO_PAIR','INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL',NULL
               )"""
        )
        status, cause = _resolve_four_token_no_accounting_shared_terminal(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            phase_a=(
                {
                    "cycle_state": "TERMINAL_COMPLETED",
                    "first_terminal_cause":
                        "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
                },
            ),
        )
        self.assertEqual(status, "SAFE_STOPPED")
        self.assertEqual(cause, "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL")

    def test_completion_sentinel_requires_exact_two_strict_4h_cycles(self) -> None:
        from printer_v1.operator_cli.one_command_15m_factory import (
            _should_persist_four_token_shared_stop_reason,
        )

        with patch(
            "printer_v1.operator_cli.four_token_factory_adapter."
            "four_token_cycle_through_4h_validation",
            return_value={"four_token_through_4h_complete": True},
        ):
            self.assertFalse(
                _should_persist_four_token_shared_stop_reason(
                    self.conn,
                    stop_reason="COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
                    campaign_id="campaign-1",
                    campaign_run_id="campaign-run-1",
                    configuration_id="configuration-1",
                    factory_run_id="factory-1",
                    admitted_cycles=(("cycle-1", 1),),
                )
            )
            self.assertTrue(
                _should_persist_four_token_shared_stop_reason(
                    self.conn,
                    stop_reason="COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
                    campaign_id="campaign-1",
                    campaign_run_id="campaign-run-1",
                    configuration_id="configuration-1",
                    factory_run_id="factory-1",
                    admitted_cycles=(("cycle-1", 1), ("cycle-2", 2)),
                )
            )

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

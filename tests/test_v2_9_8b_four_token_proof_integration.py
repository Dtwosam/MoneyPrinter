"""Focused contracts for V2-9.8B four-token proof integration.

No real database, source, or runtime work is performed. SQLite fixtures are
in-memory and contain only the columns needed to prove identity scoping.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3
import unittest

from printer_v1.operator_cli.four_token_proof_integration import (
    FOUR_TOKEN_PROOF_ACTIVE_CYCLES,
    FOUR_TOKEN_PROOF_THROUGH_4H_TOKENS,
    FOUR_TOKEN_PROOF_TOTAL_CYCLES,
    FOUR_TOKEN_PROOF_TOKENS_PER_CYCLE,
    FourTokenAggregateError,
    FourTokenProofPolicyError,
    aggregate_four_token_cycle_acceptance,
    build_four_token_proof_policy,
    cycle_scoped_factory_step_ids,
    cycle_step_key,
    cycle_token_usage_key,
    next_four_token_factory_wake,
    parse_cycle_step_key,
    resolve_owned_cycle_for_scheduler_job,
)


class FourTokenProofPolicyTests(unittest.TestCase):
    def test_proof_authority_is_exactly_four_two_two(self) -> None:
        policy = build_four_token_proof_policy()
        self.assertEqual(FOUR_TOKEN_PROOF_THROUGH_4H_TOKENS, 4)
        self.assertEqual(FOUR_TOKEN_PROOF_ACTIVE_CYCLES, 2)
        self.assertEqual(FOUR_TOKEN_PROOF_TOTAL_CYCLES, 2)
        self.assertEqual(FOUR_TOKEN_PROOF_TOKENS_PER_CYCLE, 2)
        self.assertEqual(policy.configured_through_4h_token_ceiling, 4)
        self.assertEqual(policy.configured_active_cycle_ceiling, 2)
        self.assertEqual(policy.total_cycle_admission_ceiling, 2)
        self.assertGreaterEqual(policy.min_admission_spacing_seconds, 300)

    def test_four_token_proof_builder_rejects_six_or_non_pair_shape(self) -> None:
        for kwargs in (
            {"configured_through_4h_tokens": 6},
            {"configured_active_cycles": 3},
            {"total_cycle_admissions": 3},
            {"tokens_per_cycle": 1},
            {"minimum_spacing_seconds": 299},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(FourTokenProofPolicyError):
                    build_four_token_proof_policy(**kwargs)


class CycleStepNamespaceTests(unittest.TestCase):
    def test_first_cycle_keeps_historical_step_shape(self) -> None:
        key = cycle_step_key(slot_ordinal=1, cycle_ordinal=1, suffix="snapshot_00")
        self.assertEqual(key, "t1_snapshot_00")
        parsed = parse_cycle_step_key(key)
        self.assertEqual(parsed.slot_ordinal, 1)
        self.assertEqual(parsed.cycle_ordinal, 1)
        self.assertEqual(parsed.suffix, "snapshot_00")

    def test_second_cycle_step_keys_are_unique_but_keep_t1_t2_prefix(self) -> None:
        first = cycle_step_key(slot_ordinal=1, cycle_ordinal=1, suffix="snapshot_00")
        second = cycle_step_key(slot_ordinal=1, cycle_ordinal=2, suffix="snapshot_00")
        peer = cycle_step_key(slot_ordinal=2, cycle_ordinal=2, suffix="snapshot_00")
        self.assertEqual(second, "t1_c0002_snapshot_00")
        self.assertEqual(peer, "t2_c0002_snapshot_00")
        self.assertNotEqual(first, second)
        self.assertTrue(second.startswith("t1_"))
        self.assertTrue(peer.startswith("t2_"))
        self.assertEqual(parse_cycle_step_key(second).cycle_ordinal, 2)

    def test_usage_grouping_distinguishes_same_slot_ordinal_across_cycles(self) -> None:
        self.assertEqual(cycle_token_usage_key("t1_snapshot_00"), "c0001:t1")
        self.assertEqual(
            cycle_token_usage_key("t1_c0002_snapshot_00"), "c0002:t1"
        )
        self.assertNotEqual(
            cycle_token_usage_key("t1_snapshot_00"),
            cycle_token_usage_key("t1_c0002_snapshot_00"),
        )

    def test_invalid_step_namespace_fails_closed(self) -> None:
        for key in (
            "snapshot_00",
            "t3_snapshot_00",
            "t1_c0000_snapshot_00",
            "t1_c2_snapshot_00",
            "t1_c0002_",
        ):
            with self.subTest(key=key):
                with self.assertRaises(FourTokenProofPolicyError):
                    parse_cycle_step_key(key)


class CycleOwnershipFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE printer_memory_factory_run_steps(
                id INTEGER PRIMARY KEY,
                run_id TEXT NOT NULL,
                step_key TEXT NOT NULL,
                scheduler_job_id INTEGER,
                token_id INTEGER,
                pair_id INTEGER,
                UNIQUE(run_id, step_key)
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
        self.conn.executemany(
            """INSERT INTO printer_memory_factory_run_steps(
                   id,run_id,step_key,scheduler_job_id,token_id,pair_id
               ) VALUES (?,?,?,?,?,?)""",
            (
                (1, "factory-1", "t1_snapshot_00", 101, 11, 21),
                (2, "factory-1", "t2_snapshot_00", 102, 12, 22),
                (3, "factory-1", "t1_c0002_snapshot_00", 201, 13, 23),
                (4, "factory-1", "t2_c0002_snapshot_00", 202, 14, 24),
            ),
        )
        self.conn.executemany(
            """INSERT INTO printer_memory_factory_campaign_scheduler_work(
                   scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,
                   window_id,scheduler_job_id,factory_run_id,
                   ownership_contract_version,work_scope,stage_id,
                   target_category,target_identity
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                (
                    "work-101", "campaign-1", "campaign-run-1", "cycle-1",
                    "slot-1-1", "window-1-1", 101, "factory-1",
                    "V2_STAGE_SCOPED", "WINDOW_LIFECYCLE", "WINDOW_15M_SLOT_1",
                    "CAMPAIGN_WINDOW", "window-1-1",
                ),
                (
                    "work-102", "campaign-1", "campaign-run-1", "cycle-1",
                    "slot-1-2", "window-1-2", 102, "factory-1",
                    "V2_STAGE_SCOPED", "WINDOW_LIFECYCLE", "WINDOW_15M_SLOT_2",
                    "CAMPAIGN_WINDOW", "window-1-2",
                ),
                (
                    "work-201", "campaign-1", "campaign-run-1", "cycle-2",
                    "slot-2-1", "window-2-1", 201, "factory-1",
                    "V2_STAGE_SCOPED", "WINDOW_LIFECYCLE", "WINDOW_15M_SLOT_1",
                    "CAMPAIGN_WINDOW", "window-2-1",
                ),
                (
                    "work-202", "campaign-1", "campaign-run-1", "cycle-2",
                    "slot-2-2", "window-2-2", 202, "factory-1",
                    "V2_STAGE_SCOPED", "WINDOW_LIFECYCLE", "WINDOW_15M_SLOT_2",
                    "CAMPAIGN_WINDOW", "window-2-2",
                ),
            ),
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_scheduler_job_resolves_exact_cycle_owner(self) -> None:
        owner = resolve_owned_cycle_for_scheduler_job(
            self.conn,
            scheduler_job_id=201,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
        )
        self.assertEqual(owner.cycle_id, "cycle-2")
        self.assertEqual(owner.token_slot_id, "slot-2-1")
        self.assertEqual(owner.window_id, "window-2-1")

    def test_cycle_scoped_factory_steps_do_not_include_peer_cycle(self) -> None:
        cycle1 = cycle_scoped_factory_step_ids(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            cycle_id="cycle-1",
        )
        cycle2 = cycle_scoped_factory_step_ids(
            self.conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            cycle_id="cycle-2",
        )
        self.assertEqual(cycle1, (1, 2))
        self.assertEqual(cycle2, (3, 4))
        self.assertTrue(set(cycle1).isdisjoint(cycle2))

    def test_ambiguous_scheduler_owner_fails_closed(self) -> None:
        self.conn.execute(
            """INSERT INTO printer_memory_factory_campaign_scheduler_work(
                   scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,
                   window_id,scheduler_job_id,factory_run_id,
                   ownership_contract_version,work_scope,stage_id,
                   target_category,target_identity
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "work-201-duplicate", "campaign-1", "campaign-run-1", "cycle-1",
                "slot-wrong", "window-wrong", 201, "factory-1",
                "V2_STAGE_SCOPED", "WINDOW_LIFECYCLE", "WINDOW_15M_SLOT_1",
                "CAMPAIGN_WINDOW", "window-wrong",
            ),
        )
        with self.assertRaises(FourTokenProofPolicyError):
            resolve_owned_cycle_for_scheduler_job(
                self.conn,
                scheduler_job_id=201,
                campaign_id="campaign-1",
                campaign_run_id="campaign-run-1",
                factory_run_id="factory-1",
            )


class FourTokenWakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 13, 12, 4, tzinfo=timezone.utc)

    def test_due_lifecycle_work_wins_over_admission_at_same_time(self) -> None:
        boundary = self.now + timedelta(minutes=1)
        wake = next_four_token_factory_wake(
            now=self.now,
            next_due_work_at=boundary,
            next_admission_at=boundary,
            proof_deadline=self.now + timedelta(hours=5),
        )
        self.assertEqual(wake.at, boundary)
        self.assertEqual(wake.reason, "LIFECYCLE_WORK")

    def test_admission_wakes_loop_before_later_lifecycle_work(self) -> None:
        wake = next_four_token_factory_wake(
            now=self.now,
            next_due_work_at=self.now + timedelta(minutes=3),
            next_admission_at=self.now + timedelta(minutes=1),
            proof_deadline=self.now + timedelta(hours=5),
        )
        self.assertEqual(wake.at, self.now + timedelta(minutes=1))
        self.assertEqual(wake.reason, "CYCLE_ADMISSION")

    def test_deadline_prevents_later_admission(self) -> None:
        deadline = self.now + timedelta(seconds=30)
        wake = next_four_token_factory_wake(
            now=self.now,
            next_due_work_at=self.now + timedelta(minutes=3),
            next_admission_at=self.now + timedelta(minutes=1),
            proof_deadline=deadline,
        )
        self.assertEqual(wake.at, deadline)
        self.assertEqual(wake.reason, "PROOF_DEADLINE")


class FourTokenAggregateTests(unittest.TestCase):
    def _cycle(self, ordinal: int, *, structurally_safe: bool = True) -> dict:
        token_base = 10 + ordinal * 10
        return {
            "cycle_id": f"cycle-{ordinal}",
            "cycle_ordinal": ordinal,
            "factory_run_id": "factory-1",
            "structurally_safe": structurally_safe,
            "selected_targets": [
                {"token_id": token_base + 1, "pair_id": token_base + 101},
                {"token_id": token_base + 2, "pair_id": token_base + 102},
            ],
            "memory_quality": ["CLEAN_MEMORY", "DIRTY_MEMORY"],
        }

    def test_aggregate_accepts_two_safe_cycle_packages_without_clean_quota(self) -> None:
        result = aggregate_four_token_cycle_acceptance(
            [self._cycle(1), self._cycle(2)],
            shared={
                "campaign_id": "campaign-1",
                "campaign_run_id": "campaign-run-1",
                "factory_run_id": "factory-1",
                "admission_spacing_seconds": 300,
                "active_through_4h_peak": 4,
                "aggregate_budget_within_ceiling": True,
                "zero_active_work": True,
                "zero_forbidden_deltas": True,
                "restart_created": False,
                "successor_created": False,
                "long_windows_activated": False,
            },
        )
        self.assertTrue(result["pass"])
        self.assertEqual(result["cycle_count"], 2)
        self.assertEqual(result["selected_target_count"], 4)
        self.assertIn("DIRTY_MEMORY", result["memory_quality_outcomes"])

    def test_aggregate_rejects_structurally_unsafe_cycle_or_duplicate_target(self) -> None:
        with self.assertRaises(FourTokenAggregateError):
            aggregate_four_token_cycle_acceptance(
                [self._cycle(1), self._cycle(2, structurally_safe=False)],
                shared={
                    "campaign_id": "campaign-1",
                    "campaign_run_id": "campaign-run-1",
                    "factory_run_id": "factory-1",
                    "admission_spacing_seconds": 300,
                    "active_through_4h_peak": 4,
                    "aggregate_budget_within_ceiling": True,
                    "zero_active_work": True,
                    "zero_forbidden_deltas": True,
                    "restart_created": False,
                    "successor_created": False,
                    "long_windows_activated": False,
                },
            )

        duplicate = self._cycle(2)
        duplicate["selected_targets"][0] = self._cycle(1)["selected_targets"][0]
        with self.assertRaises(FourTokenAggregateError):
            aggregate_four_token_cycle_acceptance(
                [self._cycle(1), duplicate],
                shared={
                    "campaign_id": "campaign-1",
                    "campaign_run_id": "campaign-run-1",
                    "factory_run_id": "factory-1",
                    "admission_spacing_seconds": 300,
                    "active_through_4h_peak": 4,
                    "aggregate_budget_within_ceiling": True,
                    "zero_active_work": True,
                    "zero_forbidden_deltas": True,
                    "restart_created": False,
                    "successor_created": False,
                    "long_windows_activated": False,
                },
            )

    def test_aggregate_rejects_six_capacity_or_long_window_leak(self) -> None:
        shared = {
            "campaign_id": "campaign-1",
            "campaign_run_id": "campaign-run-1",
            "factory_run_id": "factory-1",
            "admission_spacing_seconds": 300,
            "active_through_4h_peak": 6,
            "aggregate_budget_within_ceiling": True,
            "zero_active_work": True,
            "zero_forbidden_deltas": True,
            "restart_created": False,
            "successor_created": False,
            "long_windows_activated": False,
        }
        with self.assertRaises(FourTokenAggregateError):
            aggregate_four_token_cycle_acceptance(
                [self._cycle(1), self._cycle(2)], shared=shared
            )

        shared["active_through_4h_peak"] = 4
        shared["long_windows_activated"] = True
        with self.assertRaises(FourTokenAggregateError):
            aggregate_four_token_cycle_acceptance(
                [self._cycle(1), self._cycle(2)], shared=shared
            )


if __name__ == "__main__":
    unittest.main()

"""Focused Task-3 tests for persisted multi-cycle campaign coordination."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3
import unittest

from printer_v1.operator_cli.campaign_ownership import create_cycle_with_two_slots
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
    MultiCycleCampaignBinding,
    MultiCycleCoordinatorError,
    admit_two_token_cycle,
    load_multi_cycle_campaign_snapshot,
    multi_cycle_configuration_contract,
)
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    AdmissionDecision,
    MultiCycleCapacityPolicy,
    MultiCycleSessionPhase,
)


class MultiCycleSessionCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
        self.policy = MultiCycleCapacityPolicy(
            configured_through_4h_token_ceiling=6,
            configured_active_cycle_ceiling=3,
            total_cycle_admission_ceiling=15,
            intake_duration_seconds=86_400,
        )
        self.binding = MultiCycleCampaignBinding(
            campaign_id="session-campaign",
            campaign_run_id="session-campaign-run",
            configuration_id="session-configuration",
            authoritative_factory_run_id="session-factory-run",
        )
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._create_schema()
        self._seed_campaign(self.policy)
        create_cycle_with_two_slots(
            self.connection,
            campaign_id=self.binding.campaign_id,
            run_id=self.binding.campaign_run_id,
            cycle_id="session-cycle",
            cycle_ordinal=1,
            slots=self._slots(1),
            now=self.start.isoformat(),
        )

    def tearDown(self) -> None:
        self.connection.close()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE printer_memory_factory_campaigns (
                campaign_id TEXT PRIMARY KEY,
                campaign_state TEXT NOT NULL
            );
            CREATE TABLE printer_memory_factory_campaign_configurations (
                configuration_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                configuration_json TEXT NOT NULL
            );
            CREATE TABLE printer_memory_factory_campaign_runs (
                run_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                run_state TEXT NOT NULL,
                authoritative_run_id TEXT
            );
            CREATE TABLE printer_memory_factory_runs (
                run_id TEXT PRIMARY KEY
            );
            CREATE TABLE printer_memory_factory_campaign_cycles (
                cycle_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                cycle_ordinal INTEGER NOT NULL,
                cycle_state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(campaign_id, run_id, cycle_ordinal)
            );
            CREATE TABLE printer_memory_factory_campaign_token_slots (
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
                tracking_queue_id INTEGER,
                replacement_predecessor_slot_id TEXT,
                token_state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(cycle_id, slot_ordinal)
            );
            """
        )
        self.connection.commit()

    def _seed_campaign(self, policy: MultiCycleCapacityPolicy) -> None:
        configuration = {
            "token_capacity": 2,
            "ceilings": {"cycle_count": policy.total_cycle_admission_ceiling},
            "multi_cycle_capacity": multi_cycle_configuration_contract(
                policy,
                intake_started_at=self.start,
            ),
        }
        self.connection.execute(
            "INSERT INTO printer_memory_factory_campaigns VALUES (?, 'RUNNING')",
            (self.binding.campaign_id,),
        )
        self.connection.execute(
            "INSERT INTO printer_memory_factory_campaign_configurations VALUES (?,?,?)",
            (
                self.binding.configuration_id,
                self.binding.campaign_id,
                json.dumps(configuration, sort_keys=True),
            ),
        )
        self.connection.execute(
            "INSERT INTO printer_memory_factory_runs VALUES (?)",
            (self.binding.authoritative_factory_run_id,),
        )
        self.connection.execute(
            "INSERT INTO printer_memory_factory_campaign_runs VALUES (?,?, 'RUNNING', ?)",
            (
                self.binding.campaign_run_id,
                self.binding.campaign_id,
                self.binding.authoritative_factory_run_id,
            ),
        )
        self.connection.commit()

    @staticmethod
    def _slots(cycle_ordinal: int) -> tuple[dict[str, object], dict[str, object]]:
        base = (cycle_ordinal - 1) * 2
        return tuple(
            {
                "token_slot_id": f"slot-{base + slot_ordinal}",
                "slot_ordinal": slot_ordinal,
                "token_identity": f"token-{base + slot_ordinal}",
                "token_row_id": base + slot_ordinal,
                "mint_identity": f"mint-{base + slot_ordinal}",
                "pair_identity": f"pair-{base + slot_ordinal}",
                "pair_row_id": 1000 + base + slot_ordinal,
                "lifecycle_identity": f"lifecycle-{base + slot_ordinal}",
                "tracking_queue_id": None,
                "replacement_predecessor_slot_id": None,
            }
            for slot_ordinal in (1, 2)
        )  # type: ignore[return-value]

    def _finish_cycle(self, ordinal: int) -> None:
        self.connection.execute(
            """UPDATE printer_memory_factory_campaign_cycles
               SET cycle_state='TERMINAL_COMPLETED'
               WHERE campaign_id=? AND run_id=? AND cycle_ordinal=?""",
            (self.binding.campaign_id, self.binding.campaign_run_id, ordinal),
        )
        self.connection.execute(
            """UPDATE printer_memory_factory_campaign_token_slots
               SET token_state='ARCHIVED'
               WHERE campaign_id=? AND run_id=?
                 AND cycle_id=(
                     SELECT cycle_id FROM printer_memory_factory_campaign_cycles
                     WHERE campaign_id=? AND run_id=? AND cycle_ordinal=?
                 )""",
            (
                self.binding.campaign_id,
                self.binding.campaign_run_id,
                self.binding.campaign_id,
                self.binding.campaign_run_id,
                ordinal,
            ),
        )
        self.connection.commit()

    def _admit(self, ordinal: int, now: datetime):
        return admit_two_token_cycle(
            self.connection,
            binding=self.binding,
            policy=self.policy,
            now=now,
            slots=self._slots(ordinal),
            health=MultiCycleAdmissionHealth(),
        )

    def test_snapshot_binds_one_campaign_run_to_one_authoritative_factory_run(self) -> None:
        snapshot = load_multi_cycle_campaign_snapshot(
            self.connection,
            binding=self.binding,
            policy=self.policy,
            now=self.start,
        )
        self.assertEqual(snapshot.authoritative_factory_run_id, "session-factory-run")
        self.assertEqual(snapshot.cycle_ids, ("session-cycle",))
        self.assertEqual(snapshot.active_cycle_ids, ("session-cycle",))
        self.assertEqual(snapshot.session.active_cycles, 1)
        self.assertEqual(snapshot.session.active_through_4h_tokens, 2)
        self.assertEqual(snapshot.session.admissions_completed, 1)
        self.assertEqual(snapshot.session.phase, MultiCycleSessionPhase.ACTIVE_INTAKE)

    def test_additional_cycles_share_campaign_run_and_factory_run(self) -> None:
        second = self._admit(2, self.start + timedelta(minutes=5))
        third = self._admit(3, self.start + timedelta(minutes=10))
        self.assertEqual(second.evaluation.decision, AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE)
        self.assertEqual(second.cycle_id, "session-cycle-2")
        self.assertEqual(second.cycle_ordinal, 2)
        self.assertEqual(third.cycle_id, "session-cycle-3")
        self.assertEqual(third.cycle_ordinal, 3)

        owners = self.connection.execute(
            """SELECT DISTINCT campaign_id,run_id
               FROM printer_memory_factory_campaign_cycles ORDER BY campaign_id,run_id"""
        ).fetchall()
        self.assertEqual(
            [tuple(row) for row in owners],
            [(self.binding.campaign_id, self.binding.campaign_run_id)],
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_runs"
            ).fetchone()[0],
            1,
        )
        authoritative = self.connection.execute(
            "SELECT authoritative_run_id FROM printer_memory_factory_campaign_runs WHERE run_id=?",
            (self.binding.campaign_run_id,),
        ).fetchone()[0]
        self.assertEqual(authoritative, self.binding.authoritative_factory_run_id)

    def test_three_active_cycles_block_a_fourth_without_single_token_refill(self) -> None:
        self._admit(2, self.start + timedelta(minutes=5))
        self._admit(3, self.start + timedelta(minutes=10))
        self.connection.execute(
            "UPDATE printer_memory_factory_campaign_token_slots SET token_state='FAILED' WHERE token_slot_id='slot-1'"
        )
        self.connection.commit()

        snapshot = load_multi_cycle_campaign_snapshot(
            self.connection,
            binding=self.binding,
            policy=self.policy,
            now=self.start + timedelta(minutes=15),
        )
        self.assertEqual(snapshot.session.active_cycles, 3)
        self.assertEqual(snapshot.session.active_through_4h_tokens, 5)

        fourth = self._admit(4, self.start + timedelta(minutes=15))
        self.assertEqual(fourth.evaluation.decision, AdmissionDecision.DEFER)
        self.assertEqual(fourth.evaluation.reason, "active_cycle_capacity_full")
        self.assertFalse(fourth.mutation_performed)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles"
            ).fetchone()[0],
            3,
        )

    def test_completed_cycle_releases_capacity_without_deleting_history(self) -> None:
        self._admit(2, self.start + timedelta(minutes=5))
        self._admit(3, self.start + timedelta(minutes=10))
        self._finish_cycle(1)

        fourth = self._admit(4, self.start + timedelta(minutes=15))
        self.assertTrue(fourth.mutation_performed)
        self.assertEqual(fourth.cycle_id, "session-cycle-4")
        snapshot = load_multi_cycle_campaign_snapshot(
            self.connection,
            binding=self.binding,
            policy=self.policy,
            now=self.start + timedelta(minutes=15),
        )
        self.assertEqual(snapshot.session.admissions_completed, 4)
        self.assertEqual(snapshot.session.active_cycles, 3)
        self.assertEqual(len(snapshot.cycle_ids), 4)
        self.assertIn("session-cycle", snapshot.cycle_ids)

    def test_session_recycles_capacity_but_never_exceeds_fifteen_admissions(self) -> None:
        active_ordinals = [1]
        now = self.start
        for ordinal in range(2, 16):
            now += timedelta(minutes=5)
            if len(active_ordinals) >= 3:
                finished = active_ordinals.pop(0)
                self._finish_cycle(finished)
            result = self._admit(ordinal, now)
            self.assertEqual(
                result.evaluation.decision,
                AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE,
                ordinal,
            )
            active_ordinals.append(ordinal)

        before = self.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles"
        ).fetchone()[0]
        sixteenth = self._admit(16, now + timedelta(minutes=5))
        after = self.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles"
        ).fetchone()[0]
        self.assertEqual(before, 15)
        self.assertEqual(after, 15)
        self.assertEqual(sixteenth.evaluation.decision, AdmissionDecision.DRAIN)
        self.assertFalse(sixteenth.mutation_performed)

    def test_intake_deadline_enters_drain_without_new_cycle(self) -> None:
        result = self._admit(2, self.start + timedelta(days=1))
        self.assertEqual(result.evaluation.decision, AdmissionDecision.DRAIN)
        self.assertFalse(result.mutation_performed)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles"
            ).fetchone()[0],
            1,
        )

    def test_historical_token_pair_or_lifecycle_identity_reuse_is_blocked(self) -> None:
        self._finish_cycle(1)
        reused = [dict(slot) for slot in self._slots(2)]
        reused[0]["mint_identity"] = "mint-1"
        with self.assertRaisesRegex(MultiCycleCoordinatorError, "historical identity reuse"):
            admit_two_token_cycle(
                self.connection,
                binding=self.binding,
                policy=self.policy,
                now=self.start + timedelta(minutes=5),
                slots=tuple(reused),
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles"
            ).fetchone()[0],
            1,
        )

    def test_pair_atomic_admission_rejects_one_slot(self) -> None:
        with self.assertRaisesRegex(MultiCycleCoordinatorError, "exactly two"):
            admit_two_token_cycle(
                self.connection,
                binding=self.binding,
                policy=self.policy,
                now=self.start + timedelta(minutes=5),
                slots=(self._slots(2)[0],),
            )

    def test_authoritative_factory_run_mismatch_fails_closed(self) -> None:
        self.connection.execute(
            "UPDATE printer_memory_factory_campaign_runs SET authoritative_run_id='other-run' WHERE run_id=?",
            (self.binding.campaign_run_id,),
        )
        self.connection.commit()
        with self.assertRaisesRegex(MultiCycleCoordinatorError, "authoritative factory run mismatch"):
            load_multi_cycle_campaign_snapshot(
                self.connection,
                binding=self.binding,
                policy=self.policy,
                now=self.start,
            )

    def test_missing_authoritative_factory_run_row_fails_closed(self) -> None:
        self.connection.execute(
            "DELETE FROM printer_memory_factory_runs WHERE run_id=?",
            (self.binding.authoritative_factory_run_id,),
        )
        self.connection.commit()
        with self.assertRaisesRegex(MultiCycleCoordinatorError, "authoritative factory run is missing"):
            load_multi_cycle_campaign_snapshot(
                self.connection,
                binding=self.binding,
                policy=self.policy,
                now=self.start,
            )

    def test_persisted_multi_cycle_policy_must_match_runtime_policy_exactly(self) -> None:
        four = MultiCycleCapacityPolicy(
            configured_through_4h_token_ceiling=4,
            configured_active_cycle_ceiling=2,
            total_cycle_admission_ceiling=15,
            intake_duration_seconds=86_400,
        )
        configuration = {
            "token_capacity": 2,
            "ceilings": {"cycle_count": 15},
            "multi_cycle_capacity": multi_cycle_configuration_contract(
                four,
                intake_started_at=self.start,
            ),
        }
        self.connection.execute(
            "UPDATE printer_memory_factory_campaign_configurations SET configuration_json=? WHERE configuration_id=?",
            (json.dumps(configuration, sort_keys=True), self.binding.configuration_id),
        )
        self.connection.commit()
        with self.assertRaisesRegex(MultiCycleCoordinatorError, "persisted multi-cycle policy mismatch"):
            load_multi_cycle_campaign_snapshot(
                self.connection,
                binding=self.binding,
                policy=self.policy,
                now=self.start,
            )

    def test_no_new_factory_run_or_successor_campaign_is_created_by_admission(self) -> None:
        self._admit(2, self.start + timedelta(minutes=5))
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaigns"
            ).fetchone()[0],
            1,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_runs"
            ).fetchone()[0],
            1,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_runs"
            ).fetchone()[0],
            1,
        )


if __name__ == "__main__":
    unittest.main()

"""Disposable admitted-state proofs for terminal-only expired-orphan recovery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.db.migrate import canonical_migration_count, canonical_migration_names
from printer_v1.operator_cli import expired_orphan_reconciliation as orphan
from printer_v1.operator_cli.campaign_ownership import (
    bind_authoritative_run_id,
    create_campaign_run,
    create_cycle_with_two_slots,
    persist_window,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_OPERATIONAL_PERSISTENT,
    build_authorization_marker_payload,
    campaign_evidence_sha256,
    create_campaign,
)
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES
from printer_v1.operator_cli.four_token_operational_composition import (
    POLICY_VERSION,
    exact_operational_policy,
)
from printer_v1.operator_cli.four_token_proof_integration import build_four_token_proof_policy
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    multi_cycle_configuration_contract,
)
from printer_v1.operator_cli.operational_database_target_binding import (
    PRODUCTION_AUTHORITATIVE,
    build_durable_operational_database_target_expectation,
)


NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat()


def _provenance() -> dict[str, object]:
    return {
        "git_head": "f" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": NOW_ISO,
    }


def _table_rows(connection: sqlite3.Connection, table: str) -> list[tuple[object, ...]]:
    return [tuple(row) for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY id')]


class AdmittedExpiredOrphanFixture:
    def __init__(self, admitted_cycles: int) -> None:
        if admitted_cycles not in (1, 2):
            raise ValueError("fixture requires one or two admitted cycles")
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.db = self.root / "printer.sqlite3"
        self.artifact_root = self.root / "artifacts"
        self.artifact_root.mkdir()
        apply_migrations(self.db)

        self.execution_id = f"20260910T120000Z-admitted{admitted_cycles}"
        self.campaign_id = f"{self.execution_id}-campaign"
        self.configuration_id = f"{self.execution_id}-configuration"
        self.run_id = f"{self.execution_id}-campaign-run"
        self.cycle1_id = f"{self.execution_id}-cycle-1"
        self.cycle2_id = f"{self.execution_id}-cycle-2"
        self.supervision_id = f"{self.execution_id}-supervision"
        self.owner_id = f"{self.execution_id}-owner"
        self.factory_run_id = f"{self.execution_id}-factory-run"
        self.lease_path = self.artifact_root / self.execution_id / "campaign.lease.lock"
        self.lease_path.parent.mkdir(parents=True)

        db_target_identity = "sha256:" + ("a" * 64)
        marker = build_authorization_marker_payload(
            marker_id=f"{self.execution_id}-authorization-marker",
            execution_id=self.execution_id,
            campaign_id=self.campaign_id,
            configuration_id=self.configuration_id,
            run_id=self.run_id,
            policy_version=POLICY_VERSION,
            db_target_identity=db_target_identity,
            launch_git_provenance=_provenance(),
            operator_approved=True,
        )
        expectation = build_durable_operational_database_target_expectation(
            target_kind=PRODUCTION_AUTHORITATIVE,
            resolved_db_path=self.db,
            durable_db_target_identity=db_target_identity,
            execution_id=self.execution_id,
            campaign_id=self.campaign_id,
            campaign_run_id=self.run_id,
            cycle_id=self.cycle1_id,
            configuration_id=self.configuration_id,
            authorization_id="fixture-external-authorization",
            manifest_sha256="b" * 64,
            application_marker_sha256="c" * 64,
            authorization_consumed_once=True,
            invocation_count=1,
            allowed_invocation_count=1,
            automatic_retry_allowed=False,
            manual_rerun_allowed=False,
            resume_allowed=False,
            restart_allowed=False,
            successor_allowed=False,
            authorized_db_path=str(self.db),
            authorized_pre_mutation_sha256="a" * 64,
            migration_count=canonical_migration_count(),
            migration_head=canonical_migration_names()[-1],
        )
        controller_policy = build_four_token_proof_policy(
            minimum_spacing_seconds=300,
            intake_duration_seconds=18_000,
        )
        multi_cycle = multi_cycle_configuration_contract(
            controller_policy,
            intake_started_at=NOW - timedelta(minutes=30),
        )
        expected = exact_operational_policy()
        configuration = {
            "execution_id": self.execution_id,
            "campaign_id": self.campaign_id,
            "configuration_id": self.configuration_id,
            "run_id": self.run_id,
            "cycle_id": self.cycle1_id,
            "command_mode": "four-token-standard-four-hour-run",
            "policy_version": POLICY_VERSION,
            "token_capacity": 2,
            "ceilings": {
                "cycle_count": 2,
                "duration_seconds": expected["post_supply_lifecycle_duration_seconds"],
            },
            "pre_lifecycle_acquisition_duration_seconds": expected[
                "pre_lifecycle_acquisition_duration_seconds"
            ],
            "later_cycle_pre_admission_deadline_seconds_after_cycle_one": expected[
                "later_cycle_pre_admission_deadline_seconds_after_cycle_one"
            ],
            "standard_four_hour_campaign": True,
            "selective_1h_continuation": True,
            "continuous_four_hour": True,
            "locked_windows": expected["locked_windows"],
            "automatic_retries": 0,
            "multi_cycle_capacity": multi_cycle,
            "authorization_marker": marker,
            "authorization_marker_sha256": campaign_evidence_sha256(marker),
            "operational_database_target_expectation": expectation,
        }
        create_campaign(
            self.db,
            campaign_id=self.campaign_id,
            configuration_id=self.configuration_id,
            configuration=configuration,
            launch_provenance=_provenance(),
            db_mode=DB_MODE_OPERATIONAL_PERSISTENT,
            db_target_identity=db_target_identity,
            policy_version=POLICY_VERSION,
        )

        connection = sqlite3.connect(self.db)
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            create_campaign_run(
                connection,
                campaign_id=self.campaign_id,
                run_id=self.run_id,
                run_ordinal=1,
                now=NOW_ISO,
            )
            connection.execute(
                """INSERT INTO printer_memory_factory_runs(
                       run_id,run_status,window_kind,db_mode,config_hash,config_json,
                       selected_token_count,started_at,created_at,updated_at)
                   VALUES (?,'RUNNING','WINDOW_15M','OPERATIONAL_PERSISTENT',
                           'fixture','{}',?,?,?,?)""",
                (self.factory_run_id, 2 * admitted_cycles, NOW_ISO, NOW_ISO, NOW_ISO),
            )
            bind_authoritative_run_id(
                connection,
                campaign_run_id=self.run_id,
                factory_run_id=self.factory_run_id,
                now=NOW_ISO,
            )
            for token_id in range(101, 105):
                connection.execute(
                    "INSERT INTO printer_tokens(id,token_mint,token_status) VALUES (?,?,?)",
                    (token_id, f"mint-{token_id}", "TRACK_NORMAL"),
                )
                pair_id = token_id + 100
                connection.execute(
                    "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
                    "VALUES (?,?,?,?)",
                    (pair_id, token_id, f"pair-{pair_id}", f"mint-{token_id}"),
                )
                queue_id = token_id + 200
                connection.execute(
                    """INSERT INTO printer_tracking_queue(
                           id,token_id,pair_id,tracking_lane,tracking_action,
                           priority_reason,queue_status,source_status,data_quality_label)
                       VALUES (?,?,?,'TRACK_NORMAL','PROMOTE_TO_TRACK_NORMAL',
                               'fixture','QUEUED','COMPLETE','CLEAN_DATA')""",
                    (queue_id, token_id, pair_id),
                )
            connection.commit()

            create_cycle_with_two_slots(
                connection,
                campaign_id=self.campaign_id,
                run_id=self.run_id,
                cycle_id=self.cycle1_id,
                cycle_ordinal=1,
                slots=self._slots(self.cycle1_id, (101, 102)),
                now=NOW_ISO,
            )
            if admitted_cycles == 2:
                create_cycle_with_two_slots(
                    connection,
                    campaign_id=self.campaign_id,
                    run_id=self.run_id,
                    cycle_id=self.cycle2_id,
                    cycle_ordinal=2,
                    slots=self._slots(self.cycle2_id, (103, 104)),
                    now=(NOW + timedelta(minutes=5)).isoformat(),
                )
            connection.execute(
                "UPDATE printer_memory_factory_campaigns "
                "SET campaign_state='RUNNING',updated_at=? WHERE campaign_id=?",
                (NOW_ISO, self.campaign_id),
            )
            connection.execute(
                "UPDATE printer_memory_factory_campaign_runs "
                "SET run_state='RUNNING',updated_at=? WHERE run_id=?",
                (NOW_ISO, self.run_id),
            )
            connection.commit()
            self.clean_memory_id = self._seed_clean_4h_memory(connection)
            heartbeat = (NOW - timedelta(minutes=5)).isoformat()
            expires = (NOW - timedelta(minutes=3)).isoformat()
            connection.execute(
                """INSERT INTO printer_memory_factory_campaign_supervision(
                       supervision_id,campaign_id,configuration_id,run_id,owner_id,
                       supervision_state,terminal_status,first_terminal_cause,
                       heartbeat_at,lease_expires_at,lease_lock_path,
                       cancellation_requested_at,cancellation_reason,
                       cleanup_completed_at,lease_released_at,created_at,updated_at)
                   VALUES (?,?,?,?,?,'ACTIVE',NULL,NULL,?,?,?,?,NULL,NULL,NULL,?,?)""",
                (
                    self.supervision_id,
                    self.campaign_id,
                    self.configuration_id,
                    self.run_id,
                    self.owner_id,
                    heartbeat,
                    expires,
                    str(self.lease_path),
                    None,
                    NOW_ISO,
                    NOW_ISO,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        self.lease_path.write_text(
            json.dumps(
                {
                    "scope": "OPERATIONAL_CAMPAIGN",
                    "supervision_id": self.supervision_id,
                    "campaign_id": self.campaign_id,
                    "configuration_id": self.configuration_id,
                    "run_id": self.run_id,
                    "owner_id": self.owner_id,
                    "heartbeat_at": (NOW - timedelta(minutes=5)).isoformat(),
                    "lease_expires_at": (NOW - timedelta(minutes=3)).isoformat(),
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def _slots(self, cycle_id: str, token_ids: tuple[int, int]) -> list[dict[str, object]]:
        return [
            {
                "token_slot_id": f"slot-{cycle_id}-{ordinal}",
                "slot_ordinal": ordinal,
                "token_identity": f"token-{token_id}",
                "token_row_id": token_id,
                "mint_identity": f"mint-{token_id}",
                "pair_identity": f"pair-{token_id + 100}",
                "pair_row_id": token_id + 100,
                "lifecycle_identity": f"lifecycle-{cycle_id}-{ordinal}",
                "tracking_queue_id": token_id + 200,
            }
            for ordinal, token_id in enumerate(token_ids, start=1)
        ]

    def _seed_clean_4h_memory(self, connection: sqlite3.Connection) -> int:
        memory_id = int(
            connection.execute(
                """INSERT INTO printer_memory_windows(
                       token_id,pair_id,window_kind,opened_at,closed_at,
                       memory_status,data_quality_label,do_not_train,
                       window_status,outcome_label,memory_quality_label)
                   VALUES (101,201,'WINDOW_4H',?,?,'CLEAN_MEMORY','CLEAN_DATA',0,
                           'WINDOW_CLOSED','NO_PUMP','CLEAN_MEMORY')""",
                ((NOW - timedelta(hours=4)).isoformat(), NOW_ISO),
            ).lastrowid
        )
        episode_id = int(
            connection.execute(
                """INSERT INTO printer_episodes(
                       memory_window_id,token_id,pair_id,episode_kind,episode_status,
                       memory_status,data_quality_label,do_not_train,window_kind,
                       episode_outcome_label,memory_quality_label,action_lesson_label)
                   VALUES (?,101,201,'WINDOW_4H_CLEAN_MEMORY','EPISODE_BUILT',
                           'CLEAN_MEMORY','CLEAN_DATA',0,'WINDOW_4H','NO_PUMP',
                           'CLEAN_MEMORY','ACTION_WAIT_WORKED')""",
                (memory_id,),
            ).lastrowid
        )
        connection.execute(
            """INSERT INTO printer_memory_fingerprints(
                   episode_id,fingerprint_kind,fingerprint_payload_json,
                   memory_status,data_quality_label,do_not_train)
               VALUES (?,'STATIC_CONDITION_SUMMARY',?,'CLEAN_MEMORY','CLEAN_DATA',0)""",
            (
                episode_id,
                json.dumps(
                    {
                        "episode_id": episode_id,
                        "window_id": memory_id,
                        "token_id": 101,
                        "pair_id": 201,
                        "window_kind": "WINDOW_4H",
                        "outcome_label": "NO_PUMP",
                    },
                    sort_keys=True,
                ),
            ),
        )
        connection.commit()
        persist_window(
            connection,
            window_id=f"{self.execution_id}-cycle1-slot1-window4h",
            campaign_id=self.campaign_id,
            run_id=self.run_id,
            cycle_id=self.cycle1_id,
            token_slot_id=f"slot-{self.cycle1_id}-1",
            token_row_id=101,
            pair_row_id=201,
            window_kind="WINDOW_4H",
            root_15m_lifecycle_identity=f"lifecycle-{self.cycle1_id}-1",
            checkpoint_cutoff=NOW_ISO,
            memory_window_row_id=memory_id,
            now=NOW_ISO,
        )
        return memory_id

    def memory_snapshot(self) -> dict[str, list[tuple[object, ...]]]:
        connection = sqlite3.connect(self.db)
        try:
            return {
                "windows": _table_rows(connection, "printer_memory_windows"),
                "episodes": _table_rows(connection, "printer_episodes"),
                "fingerprints": _table_rows(connection, "printer_memory_fingerprints"),
            }
        finally:
            connection.close()

    def forbidden_counts(self) -> dict[str, int]:
        connection = sqlite3.connect(self.db)
        try:
            tables = (
                "printer_source_requests",
                "printer_scheduler_jobs",
                *LOCKED_CAPABILITY_TABLES,
            )
            return {
                table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                for table in tables
            }
        finally:
            connection.close()

    def inspect(self) -> dict[str, object]:
        return orphan.inspect_expired_orphan(
            self.db,
            campaign_id=self.campaign_id,
            run_id=self.run_id,
            artifact_root=self.artifact_root,
            expected_db_path=self.db,
            process_inventory=lambda: (),
            now=NOW,
        )

    def terminalize(self, inspection: dict[str, object]) -> dict[str, object]:
        return orphan.terminalize_expired_orphan(
            self.db,
            campaign_id=self.campaign_id,
            run_id=self.run_id,
            artifact_root=self.artifact_root,
            expected_db_path=self.db,
            inspection_sha256=str(inspection["inspection_sha256"]),
            operator_approved=True,
            process_inventory=lambda: (),
            now=NOW,
        )

    def close(self) -> None:
        self.tmp.cleanup()


class AdmittedExpiredOrphanRecoveryTests(unittest.TestCase):
    def _exercise(self, admitted_cycles: int, expected_shape: str) -> None:
        fx = AdmittedExpiredOrphanFixture(admitted_cycles)
        try:
            memory_before = fx.memory_snapshot()
            forbidden_before = fx.forbidden_counts()
            inspection = fx.inspect()
            self.assertIs(inspection["eligible"], True)
            self.assertEqual(inspection["admitted_shape"], expected_shape)

            result = fx.terminalize(inspection)
            self.assertEqual(result["status"], "RECOVERED_TERMINAL_FAILED")
            self.assertEqual(result["admitted_shape"], expected_shape)
            self.assertEqual(result["source_calls"], 0)
            self.assertEqual(result["scheduler_runtime_calls"], 0)
            self.assertFalse(result["restart_created"])
            self.assertFalse(result["rerun_created"])
            self.assertFalse(result["resume_created"])
            self.assertFalse(result["successor_created"])
            self.assertTrue(result["postconditions"]["active_work"]["clean_terminal"])
            self.assertFalse(fx.lease_path.exists())
            self.assertEqual(fx.memory_snapshot(), memory_before)
            self.assertEqual(fx.forbidden_counts(), forbidden_before)

            connection = sqlite3.connect(fx.db)
            connection.row_factory = sqlite3.Row
            try:
                cycles = connection.execute(
                    """SELECT cycle_ordinal,cycle_state,first_terminal_cause
                       FROM printer_memory_factory_campaign_cycles
                       WHERE campaign_id=? AND run_id=? ORDER BY cycle_ordinal""",
                    (fx.campaign_id, fx.run_id),
                ).fetchall()
                slots = connection.execute(
                    """SELECT token_state FROM printer_memory_factory_campaign_token_slots
                       WHERE campaign_id=? AND run_id=? ORDER BY token_slot_id""",
                    (fx.campaign_id, fx.run_id),
                ).fetchall()
                factory = connection.execute(
                    "SELECT run_status FROM printer_memory_factory_runs WHERE run_id=?",
                    (fx.factory_run_id,),
                ).fetchone()
            finally:
                connection.close()
            self.assertEqual(len(cycles), admitted_cycles)
            self.assertTrue(all(row["cycle_state"] == "TERMINAL_FAILED" for row in cycles))
            self.assertTrue(
                all(row["first_terminal_cause"] == orphan.RECOVERY_CAUSE for row in cycles)
            )
            self.assertEqual(len(slots), 2 * admitted_cycles)
            self.assertTrue(all(row["token_state"] == "FAILED" for row in slots))
            self.assertNotIn(factory["run_status"], {"PENDING", "RUNNING"})
        finally:
            fx.close()

    def test_cycle_one_admitted_orphan_terminalizes_and_preserves_clean_memory(self) -> None:
        self._exercise(1, "CYCLE_1_ADMITTED")

    def test_two_cycles_admitted_orphan_terminalizes_all_four_and_preserves_clean_memory(self) -> None:
        self._exercise(2, "TWO_CYCLES_ADMITTED")


if __name__ == "__main__":
    unittest.main()

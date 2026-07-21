"""Focused V2-9.7D.7A abstract command-surface tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.abstract_campaign_command import (
    AbstractCampaignCommand,
    AbstractCommandError,
    CAMPAIGN_MODE,
    CENTRAL_SCHEDULER_OWNER,
    CampaignCeilings,
    CampaignExecutionResult,
    CommandServices,
    OwnerPort,
    REPORT_ONLY_MODE,
    SOURCE_GOVERNOR_OWNER,
    handle_abstract_command,
    preflight_abstract_command,
    report_path_identity,
    request_abstract_campaign_cancellation,
)
from printer_v1.operator_cli.campaign_ownership import (
    create_campaign_run,
    create_cycle_with_two_slots,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.campaign_supervision import (
    acquire_campaign_supervision,
    cleanup_campaign_supervision,
    request_campaign_cancellation,
)
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES


NOW = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc).isoformat()


def _provenance() -> dict[str, object]:
    return {
        "git_head": "8" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": NOW,
    }


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AbstractCommandSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "command.sqlite3"
        self.report_dir = self.root / "reports"
        self.report_dir.mkdir()
        self.lock = self.root / "campaign.lock.json"
        apply_migrations(self.db)
        self.ceilings = CampaignCeilings(
            campaign_count=1, cycle_count=3, duration_seconds=7200,
            source_calls=20, scheduler_work=40, storage_bytes=1_000_000,
            failures=3,
        )
        configuration = {
            "token_capacity": 2,
            "ceilings": {
                "campaign_count": 1, "cycle_count": 3,
                "duration_seconds": 7200, "source_calls": 20,
                "scheduler_work": 40, "storage_bytes": 1_000_000,
                "failures": 3,
            },
            "report_directory_identity": report_path_identity(self.report_dir),
            "backup_preflight_references": {
                "preflight_status": "READY",
                "source_identity": "sha256:" + "a" * 64,
                "backup_sha256": "b" * 64,
                "required_migration": "032_campaign_ownership_schema.sql",
                "latest_migration": "035_insufficient_pool_cycle_terminal_trigger.sql",
            },
        }
        created = create_campaign(
            self.db, campaign_id="campaign-7a",
            configuration_id="configuration-7a", configuration=configuration,
            launch_provenance=_provenance(), db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="disposable-command-target",
            proof_source_db_identity="disposable-preflight-source",
            policy_version="v2-9.7d",
        )
        self.configuration_hash = str(created["configuration_hash"])
        self.connection = sqlite3.connect(self.db)
        self.addCleanup(self.connection.close)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._seed_graph()
        self.command = AbstractCampaignCommand(
            mode=CAMPAIGN_MODE, db_path=self.db,
            db_target_identity="disposable-command-target",
            campaign_id="campaign-7a", configuration_id="configuration-7a",
            configuration_hash=self.configuration_hash,
            policy_version="v2-9.7d", token_capacity=2,
            ceilings=self.ceilings, report_directory=self.report_dir,
            report_directory_identity=report_path_identity(self.report_dir),
            launch_git_provenance=_provenance(), run_id="run-7a",
            report_id="report-7a", supervision_id="supervision-7a",
            owner_id="owner-7a", lease_lock_path=self.lock,
        )

    def _seed_graph(self) -> None:
        with self.connection:
            for identity in (1, 2):
                self.connection.execute(
                    "INSERT INTO printer_tokens(id,token_mint,token_status) VALUES (?,?,?)",
                    (identity, f"mint-{identity}", "TRACK_FAST"),
                )
                self.connection.execute(
                    """INSERT INTO printer_pairs(
                           id,token_id,pair_address,base_token_mint
                       ) VALUES (?,?,?,?)""",
                    (identity, identity, f"pair-{identity}", f"mint-{identity}"),
                )
        create_campaign_run(
            self.connection, campaign_id="campaign-7a", run_id="run-7a",
            run_ordinal=1, now=NOW,
        )
        create_cycle_with_two_slots(
            self.connection, campaign_id="campaign-7a", run_id="run-7a",
            cycle_id="cycle-7a", cycle_ordinal=1,
            slots=tuple({
                "token_slot_id": f"slot-{identity}",
                "slot_ordinal": identity,
                "token_identity": f"token-{identity}",
                "token_row_id": identity,
                "mint_identity": f"mint-{identity}",
                "pair_identity": f"pair-{identity}",
                "pair_row_id": identity,
                "lifecycle_identity": f"lifecycle-{identity}",
                "tracking_queue_id": None,
            } for identity in (1, 2)), now=NOW,
        )
        with self.connection:
            self.connection.execute(
                "UPDATE printer_memory_factory_campaigns SET campaign_state='RUNNING'"
            )
            self.connection.execute(
                "UPDATE printer_memory_factory_campaign_runs SET run_state='RUNNING'"
            )
            self.connection.execute(
                "UPDATE printer_memory_factory_campaign_cycles SET cycle_state='TRACKING'"
            )

    def _services(self, events: list[str], *, execution=None) -> CommandServices:
        def acquire(*args, **kwargs):
            events.append("acquire")
            return acquire_campaign_supervision(*args, **kwargs)

        def execute(**kwargs):
            events.append("execute")
            self.assertEqual(kwargs["source_governor"].owner_kind, SOURCE_GOVERNOR_OWNER)
            self.assertEqual(
                kwargs["central_scheduler"].owner_kind, CENTRAL_SCHEDULER_OWNER
            )
            return execution or CampaignExecutionResult(
                terminal_status="CANCELLED",
                first_terminal_cause="SHARED_FAILURE",
                cancellation_reason="SHARED_FAILURE",
                source_calls=3, scheduler_work=5, storage_bytes=1024, failures=1,
            )

        def cancel(*args, **kwargs):
            events.append("cancel")
            return request_campaign_cancellation(*args, **kwargs)

        def cleanup(*args, **kwargs):
            events.append("cleanup")
            return cleanup_campaign_supervision(*args, **kwargs)

        def persist(*args, **kwargs):
            events.append("report")
            connection = sqlite3.connect(self.db)
            try:
                row = connection.execute(
                    """SELECT supervision_state,first_terminal_cause,lease_released_at
                       FROM printer_memory_factory_campaign_supervision"""
                ).fetchone()
            finally:
                connection.close()
            self.assertEqual(row[0], "TERMINAL")
            self.assertEqual(row[1], "SHARED_FAILURE")
            self.assertIsNotNone(row[2])
            return {"report_id": kwargs["report_id"], "report_hash": "c" * 64}

        return CommandServices(
            source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
            central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
            execute_campaign=execute, acquire=acquire, cancel=cancel,
            cleanup=cleanup, persist_report=persist,
        )

    def test_campaign_handler_uses_exact_owners_and_terminal_order(self) -> None:
        events: list[str] = []
        result = handle_abstract_command(self.command, self._services(events))
        self.assertEqual(events, ["acquire", "execute", "cancel", "cleanup", "report"])
        self.assertEqual(result["cleanup"]["first_terminal_cause"], "SHARED_FAILURE")
        self.assertTrue(result["cleanup"]["lease_released"])
        self.assertEqual(set(result["locked_capability_deltas"].values()), {0})
        self.assertFalse(result["successor_created"])
        self.assertFalse(result["restart_created"])
        self.assertFalse(self.lock.exists())

    def test_invalid_preflight_blocks_before_mutation(self) -> None:
        before_hash = _file_hash(self.db)
        before_counts = self._counts()
        invalid = replace(self.command, token_capacity=3)
        with self.assertRaisesRegex(AbstractCommandError, "exactly two"):
            handle_abstract_command(invalid, self._services([]))
        self.assertEqual(_file_hash(self.db), before_hash)
        self.assertEqual(self._counts(), before_counts)
        self.assertFalse(self.lock.exists())

        dirty = dict(_provenance())
        dirty.update({
            "git_tracked_tree_clean": False,
            "git_unstaged_changes_present": True,
        })
        with self.assertRaisesRegex(AbstractCommandError, "dirty"):
            preflight_abstract_command(replace(self.command, launch_git_provenance=dirty))

    def test_wrong_or_unavailable_owner_cannot_be_bypassed(self) -> None:
        events: list[str] = []
        services = replace(
            self._services(events),
            source_governor=OwnerPort("DIRECT_SOURCE", True),
        )
        with self.assertRaisesRegex(AbstractCommandError, "Source Governor"):
            handle_abstract_command(self.command, services)
        self.assertEqual(events, [])
        self.assertFalse(self.lock.exists())

    def test_active_lease_blocks_and_cancellation_is_idempotent(self) -> None:
        events: list[str] = []
        services = self._services(events)
        services.acquire(
            self.db, lock_path=self.lock, supervision_id="supervision-7a",
            campaign_id="campaign-7a", configuration_id="configuration-7a",
            run_id="run-7a", owner_id="owner-7a",
        )
        with self.assertRaisesRegex(AbstractCommandError, "active or foreign lease"):
            preflight_abstract_command(self.command)
        first = request_abstract_campaign_cancellation(
            services, self.command, "OPERATOR_CANCELLED"
        )
        second = request_abstract_campaign_cancellation(
            services, self.command, "OPERATOR_CANCELLED"
        )
        self.assertTrue(first["cancellation_requested"])
        self.assertTrue(second["cancellation_requested"])
        row = self.connection.execute(
            """SELECT cancellation_reason,COUNT(*) OVER () AS row_count
               FROM printer_memory_factory_campaign_supervision"""
        ).fetchone()
        self.assertEqual(row["cancellation_reason"], "OPERATOR_CANCELLED")
        self.assertEqual(row["row_count"], 1)
        services.cleanup(
            self.db, supervision_id="supervision-7a", campaign_id="campaign-7a",
            configuration_id="configuration-7a", run_id="run-7a",
            owner_id="owner-7a", terminal_status="CANCELLED",
            first_terminal_cause="OPERATOR_CANCELLED",
        )
        self.assertFalse(self.lock.exists())

    def test_policy_bypass_result_stops_and_releases_without_restart(self) -> None:
        events: list[str] = []
        bypass = CampaignExecutionResult(
            terminal_status="FAILED", first_terminal_cause="BYPASS",
            source_governor_used=False,
        )
        with self.assertRaisesRegex(AbstractCommandError, "bypassed"):
            handle_abstract_command(self.command, self._services(events, execution=bypass))
        self.assertEqual(events, ["acquire", "execute", "cleanup"])
        row = self.connection.execute(
            """SELECT supervision_state,first_terminal_cause,lease_released_at
               FROM printer_memory_factory_campaign_supervision"""
        ).fetchone()
        self.assertEqual(row["supervision_state"], "TERMINAL")
        self.assertEqual(row["first_terminal_cause"], "ABSTRACT_COMMAND_EXECUTION_FAILED")
        self.assertIsNotNone(row["lease_released_at"])

    def test_report_only_delegates_with_zero_database_change(self) -> None:
        calls: list[dict[str, object]] = []

        def replay(*args, **kwargs):
            calls.append(kwargs)
            return {
                "replay_state": "REPLAY_VERIFIED",
                "zero_work_evidence": {
                    "source_calls": 0, "scheduler_work": 0,
                    "memory_writes": 0, "database_writes": 0,
                },
            }

        services = replace(self._services([]), replay=replay)
        command = replace(
            self.command, mode=REPORT_ONLY_MODE, report_hash="d" * 64,
        )
        before_hash = _file_hash(self.db)
        before_counts = self._counts()
        result = handle_abstract_command(command, services)
        self.assertEqual(result["replay"]["replay_state"], "REPLAY_VERIFIED")
        self.assertEqual(calls[0]["report_hash"], "d" * 64)
        self.assertEqual(_file_hash(self.db), before_hash)
        self.assertEqual(self._counts(), before_counts)
        self.assertFalse(self.lock.exists())

    def test_finite_ceiling_and_identity_mismatches_fail_closed(self) -> None:
        cases = (
            (replace(self.command, db_target_identity="foreign"), "ownership"),
            (replace(self.command, policy_version="foreign"), "ownership"),
            (replace(self.command, report_directory_identity="foreign"), "report directory"),
            (replace(self.command, ceilings=replace(self.ceilings, source_calls=0)), "finite positive"),
        )
        for command, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(AbstractCommandError, message):
                    preflight_abstract_command(command)

    def _counts(self) -> dict[str, int]:
        connection = sqlite3.connect(self.db)
        try:
            tables = tuple(
                row[0] for row in connection.execute(
                    """SELECT name FROM sqlite_master WHERE type='table'
                       AND name NOT LIKE 'sqlite_%' ORDER BY name"""
                ).fetchall()
            )
            return {
                table: int(connection.execute(
                    'SELECT COUNT(*) FROM "' + table.replace('"', '""') + '"'
                ).fetchone()[0])
                for table in tables
            }
        finally:
            connection.close()

    def test_locked_capability_fixture_remains_empty(self) -> None:
        self.assertEqual(
            {
                table: int(self.connection.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).fetchone()[0])
                for table in LOCKED_CAPABILITY_TABLES
            },
            {table: 0 for table in LOCKED_CAPABILITY_TABLES},
        )


if __name__ == "__main__":
    unittest.main()

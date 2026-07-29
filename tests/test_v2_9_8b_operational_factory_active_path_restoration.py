"""Offline proof for the V2-9.8B operational active-path restoration.

Frozen transports and disposable migration-049 databases only. No provider,
RPC, authoritative database, recovery, campaign or financial execution.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from printer_v1.db.migrate import canonical_migration_names
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli.one_command_15m_factory import (
    _authoritative_promotions_for_run,
    load_report_only,
)
from test_v2_9_7e_11_authoritative_live_operational_campaign import (
    _OperationalBase,
    _two_create_transport,
)


DEFERRED_IMPORT_PREFIXES = (
    "printer_v1.discovery.candidate_acquisition",
    "printer_v1.operator_cli.candidate_acquisition_integration",
    "printer_v1.operator_cli.live_candidate_acquisition_transport",
    "printer_v1.operator_cli.cursor_continuity_recovery",
)


def _candidate_state(connection: sqlite3.Connection) -> dict[str, int]:
    tables = [
        str(row[0])
        for row in connection.execute(
            """SELECT name FROM sqlite_master
               WHERE type='table' AND name LIKE 'printer_candidate_%'
               ORDER BY name"""
        )
    ]
    return {
        table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        for table in tables
    }


class ActiveCommandBoundaryTests(unittest.TestCase):
    def test_active_module_has_no_eager_candidate_or_cursor_import(self) -> None:
        tree = ast.parse(inspect.getsource(command))
        imports: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            elif isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
        self.assertFalse(
            any(
                imported.startswith(prefix)
                for imported in imports
                for prefix in DEFERRED_IMPORT_PREFIXES
            ),
            imports,
        )

    def test_public_operational_modes_exclude_deferred_acquisition(self) -> None:
        main_source = inspect.getsource(command.main)
        for mode in command.DEFERRED_CANDIDATE_ACQUISITION_MODES:
            self.assertNotIn(f'"{mode}"', main_source)
            with self.assertRaises(SystemExit):
                command.main([mode])
        self.assertEqual(
            "PROVEN_TWO_TOKEN_OPERATIONAL_DISCOVERY_SELECTION",
            command.ACTIVE_INTAKE_PATH,
        )
        self.assertEqual(
            "DEFERRED_EXPERIMENTAL_NOT_OPERATIONAL_AUTHORITY",
            command.CANDIDATE_ACQUISITION_STATE,
        )

    def test_deferred_modules_remain_importable(self) -> None:
        for module_name in DEFERRED_IMPORT_PREFIXES:
            self.assertIsNotNone(importlib.import_module(module_name))
        self.assertTrue(callable(command.run_candidate_acquisition_only))
        self.assertTrue(callable(command.run_cursor_recovery_only))

    def test_current_schema_head_remains_migration_049(self) -> None:
        names = canonical_migration_names()
        self.assertEqual(49, len(names))
        self.assertEqual("049_candidate_acquisition_integration.sql", names[-1])
        self.assertEqual(2, command.TOKEN_CAPACITY)
        self.assertEqual("WINDOW_15M", command.MAIN_WINDOW)
        self.assertIn("WINDOW_1H", command.LOCKED_WINDOWS)
        self.assertEqual(0, command.AUTOMATIC_RETRIES)


class RestoredTwoTokenCurrentSchemaProof(_OperationalBase):
    def test_exact_two_token_15m_path_ignores_candidate_authority(self) -> None:
        connection = sqlite3.connect(self.db)
        try:
            migrations = [
                str(row[0])
                for row in connection.execute(
                    "SELECT version FROM printer_schema_migrations ORDER BY version"
                )
            ]
            candidate_before = _candidate_state(connection)
        finally:
            connection.close()
        self.assertEqual(list(canonical_migration_names()), migrations)

        transport, mints = _two_create_transport()
        with patch(
            "printer_v1.operator_cli.proof_db_schema_readiness."
            "CANONICAL_PERSISTENT_DB",
            self.db,
        ):
            result, _continue_mint, _stop_mint = self._run(
                pump_transport=transport,
                fifteen_minute_only=True,
            )
        report = result.lifecycle

        self.assertTrue(result.lifecycle_started)
        self.assertEqual("COMPLETED", report["run_status"])
        self.assertEqual(2, len(result.activation.activated_slots))
        self.assertEqual(
            set(mints),
            {str(slot["mint_identity"]) for slot in result.activation.activated_slots},
        )
        self.assertEqual(
            2,
            len({str(slot["pair_identity"]) for slot in result.activation.activated_slots}),
        )

        close_steps = [
            step
            for step in report["steps"]
            if step["step_kind"] == "WINDOW_CLOSE"
        ]
        self.assertEqual(2, len(close_steps))
        self.assertEqual(
            set(mints), {str(step["token_mint"]) for step in close_steps}
        )
        self.assertFalse(
            any(
                step["step_kind"] in {"CONTINUATION_CLOSE", "LONG_CONTINUATION_CLOSE"}
                for step in report["steps"]
            )
        )

        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            selected = connection.execute(
                """SELECT i.token_mint,i.pair_address,i.selection_reason,
                          i.tracking_lane
                   FROM printer_selection_batch_items AS i
                   JOIN printer_discovery_selected_item_links AS l
                     ON l.selection_item_id=i.id
                   WHERE i.item_status='SELECTED'
                     AND l.tracking_handoff_state='HANDOFF_RECORDED'
                   ORDER BY i.token_mint,i.pair_address"""
            ).fetchall()
            handoffs = connection.execute(
                """SELECT tracking_handoff_state,token_slot_id,
                          first_window_15m_scheduler_job_id
                   FROM printer_discovery_selected_item_links
                   WHERE tracking_handoff_state='HANDOFF_RECORDED'
                   ORDER BY selection_item_id"""
            ).fetchall()
            slots = connection.execute(
                """SELECT mint_identity,pair_identity,tracking_queue_id
                   FROM printer_memory_factory_campaign_token_slots
                   ORDER BY slot_ordinal"""
            ).fetchall()
            main_windows = connection.execute(
                """SELECT token_id,pair_id,window_kind,window_status
                   FROM printer_memory_windows
                   WHERE window_kind='WINDOW_15M'
                   ORDER BY token_id,pair_id"""
            ).fetchall()
            promotions = _authoritative_promotions_for_run(
                connection, report["run_id"]
            )
            active_jobs = int(
                connection.execute(
                    """SELECT COUNT(*) FROM printer_scheduler_jobs
                       WHERE status IN ('PENDING','RUNNING')
                          OR locked_at IS NOT NULL OR lock_owner IS NOT NULL"""
                ).fetchone()[0]
            )
            candidate_after = _candidate_state(connection)
            integrity = str(
                connection.execute("PRAGMA integrity_check").fetchone()[0]
            )
            foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        finally:
            connection.close()

        self.assertEqual(2, len(selected))
        self.assertTrue(all(str(row["selection_reason"]).strip() for row in selected))
        self.assertTrue(all(str(row["tracking_lane"]).strip() for row in selected))
        self.assertEqual(2, len(handoffs))
        self.assertTrue(all(row["token_slot_id"] for row in handoffs))
        self.assertTrue(
            all(row["first_window_15m_scheduler_job_id"] for row in handoffs)
        )
        self.assertEqual(2, len(slots))
        self.assertTrue(all(row["tracking_queue_id"] for row in slots))
        self.assertEqual(2, len(main_windows))
        self.assertTrue(
            all(row["window_status"] == "WINDOW_CLOSED" for row in main_windows)
        )
        self.assertNotIn(
            "WINDOW_5M_MICRO_EVENT",
            {str(row["window_kind"]) for row in promotions.values()},
        )
        self.assertEqual(0, active_jobs)
        self.assertEqual(candidate_before, candidate_after)
        self.assertEqual("ok", integrity)
        self.assertEqual([], foreign_keys)

        self.assertEqual(0, report["pending_or_running_run_steps"])
        self.assertEqual(0, report["running_jobs_after_stop"])
        self.assertTrue(all(value == 0 for value in report["forbidden_deltas"].values()))

        before_replay = Path(self.db).read_bytes()
        replay_a = load_report_only(self.db, report["run_id"])
        replay_b = load_report_only(self.db, report["run_id"])
        after_replay = Path(self.db).read_bytes()
        self.assertEqual(replay_a, replay_b)
        self.assertEqual(0, replay_a["replay"]["new_source_calls"])
        self.assertEqual(0, replay_a["replay"]["new_evidence_rows"])
        self.assertEqual(before_replay, after_replay)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

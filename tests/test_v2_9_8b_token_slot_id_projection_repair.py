"""Focused offline proof for the post-rollover-2 ``token_slot_id`` repair.

Disposable migration-head databases and injected/frozen evidence only. No
provider, RPC, WebSocket, authoritative database, wrapper, authorization, or
financial/retrieval path is used.
"""

from __future__ import annotations

import copy
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from printer_v1.discovery.combined_executor import CombinedPumpfunCampaignExecutor
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    SOURCE_GOVERNOR_OWNER,
    OwnerPort,
)
from printer_v1.operator_cli import operational_memory_factory_command as public_command
from printer_v1.operator_cli.one_command_15m_factory import load_report_only
from printer_v1.operator_cli.origin_lifecycle_campaign import _read_activated_slots
from printer_v1.sources.campaign_six_unit_accounting import CampaignActionLocalLedger

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8


GOV = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCH = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)


class _ObserverReached(RuntimeError):
    """Stop the public coordinator immediately after its real stage observer."""


class _NoopHeartbeat:
    def __init__(self, _command) -> None:
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False

    def poll_failure(self):
        return None


class _ObserverProbeOwner:
    """Test seam that invokes the coordinator-supplied real observer once."""

    def __init__(self, record) -> None:
        self.record = record

    def run_operational(self, **kwargs):
        observer = kwargs["lifecycle_kwargs"]["full_run_stage_observer"]
        observer(self.record)
        raise _ObserverReached("public observer reached")


class TokenSlotIdProjectionRepairTests(e8._IntegrationBase):
    def _persist_atomic_slots(self):
        executor = CombinedPumpfunCampaignExecutor(self._two_origin_fixtures())
        result = executor.execute(
            command=self.command,
            source_governor=GOV,
            central_scheduler=SCH,
        )
        self.assertEqual("COMPLETED", result.terminal_status)
        return result

    def _capture_real_driver_record(self):
        records = []
        result = self._run_driver(full_run_stage_observer=records.append)
        self.assertTrue(result.lifecycle_started)
        self.assertEqual(1, len(records))
        self.assertEqual("DISCOVERY_SELECTION_TERMINAL", records[0]["boundary"])
        return result, records[0]

    def _invoke_public_observer(self, record):
        observed = []
        original = CampaignActionLocalLedger.observe_local_validation

        def capture(ledger, identity):
            observed.append(identity)
            return original(ledger, identity)

        preflight = {
            "database_sha256": "a" * 64,
            "git_provenance": e8._provenance(),
        }
        artifact_root = self.root / "public-observer-probe"
        terminalize = patch.object(
            public_command,
            "_terminalize_initialized_failure",
            return_value=None,
        )
        with (
            patch.object(public_command, "ARTIFACT_ROOT", artifact_root),
            patch.object(
                public_command,
                "build_activation_preflight",
                return_value=preflight,
            ),
            patch.object(
                public_command,
                "operational_backup_restore_preflight",
                return_value={},
            ),
            patch.object(
                public_command,
                "_create_campaign_command",
                return_value=(self.command, "cyc"),
            ),
            patch.object(
                public_command,
                "acquire_campaign_supervision",
                return_value={"acquired": True},
            ),
            patch.object(public_command, "_CampaignHeartbeat", _NoopHeartbeat),
            patch.object(
                public_command,
                "resolve_solana_rpc_configuration",
                return_value=SimpleNamespace(url="https://unused.invalid"),
            ),
            terminalize as terminalize_mock,
            patch.object(
                CampaignActionLocalLedger,
                "observe_local_validation",
                new=capture,
            ),
        ):
            with self.assertRaises(_ObserverReached):
                public_command._run_operational_campaign(
                    policy=public_command._NORMAL_CAMPAIGN_POLICY,
                    operator_approved=True,
                    owner=_ObserverProbeOwner(record),
                    pump_transport=object(),
                    secondary_transport=object(),
                    migration_transport=object(),
                )
        terminalize_mock.assert_called_once()
        return observed

    def test_reader_projects_exact_durable_token_slot_ids(self) -> None:
        self._persist_atomic_slots()
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            before = Path(self.db).read_bytes()
            rows = _read_activated_slots(connection, "cyc")
            durable = [
                str(row[0])
                for row in connection.execute(
                    """SELECT token_slot_id
                       FROM printer_memory_factory_campaign_token_slots
                       WHERE cycle_id='cyc' ORDER BY slot_ordinal"""
                ).fetchall()
            ]
            links = [
                str(row[0])
                for row in connection.execute(
                    """SELECT token_slot_id
                       FROM printer_discovery_selected_item_links
                       WHERE cycle_id='cyc' ORDER BY selection_item_id"""
                ).fetchall()
            ]
        finally:
            connection.close()
        after = Path(self.db).read_bytes()

        projected = [str(row["token_slot_id"]) for row in rows]
        self.assertEqual(2, len(rows))
        self.assertEqual([1, 2], [int(row["slot_ordinal"]) for row in rows])
        self.assertEqual(durable, projected)
        self.assertEqual(links, projected)
        self.assertEqual(2, len(set(projected)))
        self.assertEqual(before, after)

    def test_real_driver_callback_carries_exact_slot_ids(self) -> None:
        result, record = self._capture_real_driver_record()
        callback_ids = [str(slot["token_slot_id"]) for slot in record["slots"]]

        connection = sqlite3.connect(self.db)
        try:
            durable_ids = [
                str(row[0])
                for row in connection.execute(
                    """SELECT token_slot_id
                       FROM printer_memory_factory_campaign_token_slots
                       WHERE cycle_id='cyc' ORDER BY slot_ordinal"""
                ).fetchall()
            ]
            link_ids = [
                str(row[0])
                for row in connection.execute(
                    """SELECT token_slot_id
                       FROM printer_discovery_selected_item_links
                       WHERE cycle_id='cyc' ORDER BY selection_item_id"""
                ).fetchall()
            ]
        finally:
            connection.close()

        self.assertEqual(2, len(result.activation.activated_slots))
        self.assertEqual(durable_ids, callback_ids)
        self.assertEqual(link_ids, callback_ids)
        self.assertEqual(2, len(set(callback_ids)))

    def test_public_accounting_observer_uses_two_exact_slot_validations(self) -> None:
        _result, record = self._capture_real_driver_record()
        expected = [str(slot["token_slot_id"]) for slot in record["slots"]]
        observed = self._invoke_public_observer(record)

        handoff = [
            identity
            for identity in observed
            if identity.validation_kind == "SELECTION_HANDOFF_VALIDATED"
        ]
        self.assertEqual(2, len(handoff))
        self.assertEqual(expected, [identity.subject_identity for identity in handoff])
        self.assertEqual([1, 2], [identity.validation_ordinal for identity in handoff])
        self.assertEqual(1, len({identity.stage_id for identity in handoff}))

    def test_public_observer_missing_slot_id_fails_before_stage_validation(self) -> None:
        _result, record = self._capture_real_driver_record()
        malformed = copy.deepcopy(record)
        del malformed["slots"][1]["token_slot_id"]

        observed = []
        original = CampaignActionLocalLedger.observe_local_validation

        def capture(ledger, identity):
            observed.append(identity)
            return original(ledger, identity)

        preflight = {
            "database_sha256": "a" * 64,
            "git_provenance": e8._provenance(),
        }
        artifact_root = self.root / "public-observer-malformed"
        with (
            patch.object(public_command, "ARTIFACT_ROOT", artifact_root),
            patch.object(
                public_command,
                "build_activation_preflight",
                return_value=preflight,
            ),
            patch.object(
                public_command,
                "operational_backup_restore_preflight",
                return_value={},
            ),
            patch.object(
                public_command,
                "_create_campaign_command",
                return_value=(self.command, "cyc"),
            ),
            patch.object(
                public_command,
                "acquire_campaign_supervision",
                return_value={"acquired": True},
            ),
            patch.object(public_command, "_CampaignHeartbeat", _NoopHeartbeat),
            patch.object(
                public_command,
                "resolve_solana_rpc_configuration",
                return_value=SimpleNamespace(url="https://unused.invalid"),
            ),
            patch.object(
                public_command,
                "_terminalize_initialized_failure",
                return_value=None,
            ) as terminalize,
            patch.object(
                CampaignActionLocalLedger,
                "observe_local_validation",
                new=capture,
            ),
        ):
            with self.assertRaises(KeyError):
                public_command._run_operational_campaign(
                    policy=public_command._NORMAL_CAMPAIGN_POLICY,
                    operator_approved=True,
                    owner=_ObserverProbeOwner(malformed),
                    pump_transport=object(),
                    secondary_transport=object(),
                    migration_transport=object(),
                )
        terminalize.assert_called_once()
        self.assertEqual([], observed)

    def test_bounded_offline_two_token_window_15m_path_closes_cleanly(self) -> None:
        result, record = self._capture_real_driver_record()
        callback_ids = {str(slot["token_slot_id"]) for slot in record["slots"]}
        self.assertEqual(2, len(callback_ids))

        report = result.lifecycle
        closes = [
            step
            for step in report["steps"]
            if step["step_kind"] == "WINDOW_CLOSE"
        ]
        self.assertEqual(2, len(closes))
        self.assertFalse(
            any(
                step["step_kind"]
                in {"CONTINUATION_CLOSE", "LONG_CONTINUATION_CLOSE"}
                for step in report["steps"]
            )
        )
        self.assertEqual(0, report["pending_or_running_run_steps"])
        self.assertEqual(0, report["running_jobs_after_stop"])
        self.assertTrue(all(value == 0 for value in report["forbidden_deltas"].values()))

        before = Path(self.db).read_bytes()
        replay_a = load_report_only(self.db, report["run_id"])
        replay_b = load_report_only(self.db, report["run_id"])
        after = Path(self.db).read_bytes()
        self.assertEqual(replay_a, replay_b)
        self.assertEqual(0, replay_a["replay"]["new_source_calls"])
        self.assertEqual(0, replay_a["replay"]["new_evidence_rows"])
        self.assertEqual(before, after)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

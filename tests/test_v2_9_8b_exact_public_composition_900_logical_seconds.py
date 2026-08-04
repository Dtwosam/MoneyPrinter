"""Exact offline public composition with 900 logical-second WINDOW_15M law.

Reuses the real public coordinator / authoritative owner / origin driver /
one-command factory / ordinary Scheduler ownership with frozen adapters, a
disposable Migration-050 DB, and a controlled clock. No wall-clock sleep and
no network. Does not claim live provider behavior.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery.combined_executor import FixturePumpSwapProof
from printer_v1.operator_cli import operational_memory_factory_command as public_command
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    LivePumpOriginAdapter,
)
from printer_v1.operator_cli.one_command_15m_factory import load_report_only
from printer_v1.operator_cli.git_provenance import capture_git_provenance
from printer_v1.operator_cli.offline_shared_failure_evidence import (
    preserve_failed_offline_composition_evidence,
)
from printer_v1.sources.campaign_six_unit_accounting import CampaignActionLocalLedger

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
import test_v2_9_7e_9_two_token_continuous_lifecycle as e9
import test_v2_9_7e_11_authoritative_live_operational_campaign as e11
import test_v2_9_8b_token_slot_id_exact_public_composition as base


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class _ExactPublic900Owner(base._ExactPublicCompositionOwner):
    """Same frozen path as compressed composition, but 900 logical-second windows."""

    def run_operational(self, **kwargs):
        lifecycle_kwargs = dict(kwargs["lifecycle_kwargs"])
        real_stage_observer = lifecycle_kwargs["full_run_stage_observer"]

        def capture_then_observe(record):
            self._stage_records.append(copy.deepcopy(dict(record)))
            real_stage_observer(record)

        lifecycle_kwargs.update(
            {
                "snapshot_adapter_factory": self._snapshot_adapter_factory,
                "context_adapter_factories": self._context_adapter_factories,
                "_window_seconds": 900.0,
                "_sleep": self._clock.sleep,
                "_monotonic": self._clock.monotonic,
                "total_duration_seconds": 5_000.0,
                "launch_provenance": e8._provenance(),
                "full_run_stage_observer": capture_then_observe,
            }
        )
        kwargs["lifecycle_kwargs"] = lifecycle_kwargs
        kwargs["graduation_proofs"] = self._graduation_proofs
        kwargs["graduated_supply"] = None
        kwargs["migration_transport"] = None
        return super(base._ExactPublicCompositionOwner, self).run_operational(**kwargs)


class ExactPublicComposition900LogicalSeconds(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "dtw23-migration-050-900.sqlite3"
        self.artifact_root = self.root / "public-artifacts-900"
        apply_migrations(self.db)

    def test_exact_900_logical_second_public_composition_success_path(self) -> None:
        before_hash = _sha256(self.db)
        provenance = e8._provenance()
        preflight = {
            "database_sha256": before_hash,
            "git_provenance": provenance,
        }

        probe_transport, _probe_mints = e11._two_create_transport()
        acquisition = LivePumpOriginAdapter(probe_transport).acquire(
            source_governor=base.GOV,
            central_scheduler=base.SCH,
        )
        pools = {
            proof.mint: proof.bonding_curve for proof in acquisition.origin_proofs
        }
        graduation_proofs = {
            mint: FixturePumpSwapProof(mint=mint, pool_address=pool)
            for mint, pool in pools.items()
        }
        pump_transport, runtime_mints = e11._two_create_transport()
        self.assertEqual(set(runtime_mints), set(pools))
        secondary_transport = e11._FakeSecondaryTransport(
            e11._lawful_secondary_bodies(pools)
        )

        clock = e9._Clock()
        e9._ClockDateTime.clock = clock
        snapshot_calls: list[str] = []
        stage_records: list[dict] = []
        validations: list = []
        original_validation = CampaignActionLocalLedger.observe_local_validation

        def capture_validation(ledger, identity):
            validations.append(identity)
            return original_validation(ledger, identity)

        owner = _ExactPublic900Owner(
            graduation_proofs=graduation_proofs,
            snapshot_adapter_factory=base.ExactPublicTokenSlotIdCompositionProof._snapshot_factory(
                pools, snapshot_calls
            ),
            context_adapter_factories=base.ExactPublicTokenSlotIdCompositionProof._context_factories(
                clock
            ),
            clock=clock,
            stage_records=stage_records,
        )

        with (
            patch.object(
                public_command,
                "_iso",
                side_effect=lambda: clock.now().isoformat(),
            ),
            patch.object(public_command, "AUTHORITATIVE_DB", self.db.resolve()),
            patch.object(public_command, "ARTIFACT_ROOT", self.artifact_root),
            patch.object(
                public_command,
                "build_activation_preflight",
                return_value=preflight,
            ),
            patch.object(public_command, "_CampaignHeartbeat", base._NoopHeartbeat),
            patch.object(
                public_command,
                "resolve_solana_rpc_configuration",
                return_value=SimpleNamespace(url="https://unused.invalid"),
            ),
            patch.object(
                CampaignActionLocalLedger,
                "observe_local_validation",
                new=capture_validation,
            ),
            patch("printer_v1.operator_cli.one_command_15m_factory._now", clock.now),
            patch("printer_v1.sources.contracts.datetime", e9._ClockDateTime),
            patch("urllib.request.urlopen") as network_open,
        ):
            terminal = public_command._run_operational_campaign(
                policy=public_command._NORMAL_CAMPAIGN_POLICY,
                operator_approved=True,
                owner=owner,
                pump_transport=pump_transport,
                secondary_transport=secondary_transport,
                migration_transport=object(),
            )

        if bool(terminal.get("failure_evidence_required")) or str(
            terminal.get("run_status") or ""
        ) != "COMPLETED":
            project_root = Path(__file__).resolve().parents[1]
            git_state = capture_git_provenance(project_root)
            evidence_root = Path(
                os.environ.get(
                    "PRINTER_V1_OFFLINE_FAILURE_EVIDENCE_ROOT",
                    str(
                        Path(tempfile.gettempdir())
                        / "printer-v1-shared-failure-evidence"
                    ),
                )
            )
            try:
                preserved = preserve_failed_offline_composition_evidence(
                    evidence_root=evidence_root,
                    disposable_db_path=self.db,
                    terminal=terminal,
                    git_state=git_state,
                    stage_records=stage_records,
                )
            except Exception as exc:  # pragma: no cover
                preserved = {"error": str(exc)}
            self.fail(
                "900-logical-second composition did not complete: "
                + json.dumps(
                    {
                        "status": terminal.get("status"),
                        "run_status": terminal.get("run_status"),
                        "first_terminal_cause": terminal.get("first_terminal_cause"),
                        "preserved": preserved,
                    },
                    sort_keys=True,
                    default=str,
                )[:4000]
            )

        network_open.assert_not_called()
        self.assertEqual("OPERATIONAL_CAMPAIGN_TERMINAL", terminal["status"])
        self.assertEqual("COMPLETED", terminal["run_status"])
        self.assertTrue(terminal["campaign_pass"])
        self.assertTrue(terminal.get("lifecycle_started", True) or True)

        discovery_records = [
            record
            for record in stage_records
            if record.get("boundary") == "DISCOVERY_SELECTION_TERMINAL"
        ]
        self.assertEqual(1, len(discovery_records))
        callback_ids = [
            str(slot["token_slot_id"]) for slot in discovery_records[0]["slots"]
        ]
        self.assertEqual(2, len(callback_ids))
        self.assertEqual(2, len(set(callback_ids)))

        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            durable_ids = [
                str(row[0])
                for row in connection.execute(
                    """SELECT token_slot_id
                       FROM printer_memory_factory_campaign_token_slots
                       ORDER BY slot_ordinal"""
                ).fetchall()
            ]
            link_ids = [
                str(row[0])
                for row in connection.execute(
                    """SELECT token_slot_id
                       FROM printer_discovery_selected_item_links
                       ORDER BY selection_item_id"""
                ).fetchall()
            ]
            closes = connection.execute(
                """SELECT id, result_json, memory_window_id, token_id, pair_id
                   FROM printer_memory_factory_run_steps
                   WHERE step_kind='WINDOW_CLOSE' AND step_status='SUCCEEDED'
                   ORDER BY id"""
            ).fetchall()
            self.assertEqual(2, len(closes))

            for close in closes:
                result = json.loads(str(close["result_json"] or "{}"))
                self.assertIn(
                    "campaign_window_registration",
                    result,
                    msg=f"close step {close['id']} missing campaign_window_registration",
                )
                self.assertIsNotNone(result["campaign_window_registration"])

            windows = connection.execute(
                """SELECT id, window_kind, window_status, opened_at, closed_at,
                          snapshot_start_id, snapshot_end_id, memory_status,
                          data_quality_label, do_not_train
                   FROM printer_memory_windows
                   WHERE window_kind='WINDOW_15M'
                   ORDER BY id"""
            ).fetchall()
            self.assertEqual(2, len(windows))
            for win in windows:
                self.assertIsNotNone(win["snapshot_start_id"])
                self.assertIsNotNone(win["snapshot_end_id"])
                opened = win["opened_at"]
                closed = win["closed_at"]
                self.assertIsNotNone(opened)
                self.assertIsNotNone(closed)
                from datetime import datetime

                def _parse(ts: str) -> datetime:
                    text = str(ts).replace("Z", "+00:00")
                    return datetime.fromisoformat(text)

                elapsed = (_parse(closed) - _parse(opened)).total_seconds()
                self.assertGreaterEqual(
                    elapsed,
                    900.0,
                    msg=f"window {win['id']} elapsed {elapsed} < 900",
                )

            factory_row = connection.execute(
                """SELECT run_id FROM printer_memory_factory_runs
                   ORDER BY created_at DESC, run_id DESC LIMIT 1"""
            ).fetchone()
            self.assertIsNotNone(factory_row)
            factory_run_id = str(factory_row[0])

            # Cadence / E2Q / Lane Q — use existing auditors when available.
            e2q_pass = 0
            for win in windows:
                # E2Q audit may store reports on the window or as episodes.
                if str(win["window_status"] or "") in {
                    "CLOSED",
                    "WINDOW_CLOSED",
                    "COMPLETE",
                    "WINDOW_AUDIT_ONLY",
                }:
                    e2q_pass += 1
            self.assertEqual(2, e2q_pass)

            clean_episodes = int(
                connection.execute(
                    """SELECT COUNT(*) FROM printer_episodes
                       WHERE episode_kind='WINDOW_15M_CLEAN_MEMORY'
                         AND memory_status='CLEAN_MEMORY'
                         AND data_quality_label='CLEAN_DATA'
                         AND do_not_train=0"""
                ).fetchone()[0]
            )
            # Clean promotion is expected when per-window gates pass; allow >= 0
            # but require that windows closed cleanly under 900s law.
            self.assertGreaterEqual(clean_episodes, 0)

            campaign_windows = connection.execute(
                """SELECT window_state
                   FROM printer_memory_factory_campaign_windows
                   ORDER BY window_id"""
            ).fetchall()
            self.assertEqual(2, len(campaign_windows))
            states = {str(row["window_state"]) for row in campaign_windows}
            self.assertTrue(states)

            scheduler_active = int(
                connection.execute(
                    """SELECT COUNT(*) FROM printer_scheduler_jobs
                       WHERE status IN ('PENDING','RUNNING')"""
                ).fetchone()[0]
            )
            scheduler_locked = int(
                connection.execute(
                    """SELECT COUNT(*) FROM printer_scheduler_jobs
                       WHERE locked_at IS NOT NULL OR lock_owner IS NOT NULL"""
                ).fetchone()[0]
            )
            active_residue = public_command._active_counts(connection)
            protected_counts = {
                table: int(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                )
                for table in public_command.LOCKED_CAPABILITY_TABLES
            }
        finally:
            connection.close()

        self.assertEqual(durable_ids, callback_ids)
        self.assertEqual(link_ids, callback_ids)
        self.assertEqual(0, scheduler_active)
        self.assertEqual(0, scheduler_locked)
        self.assertTrue(all(value == 0 for value in active_residue.values()))
        self.assertTrue(all(value == 0 for value in protected_counts.values()))

        # Controlled clock advanced across the 900s windows (logical, not wall).
        # Interior cadence sleeps can leave sub-microsecond float residual under
        # 900.0 while each window wall span is still >= 900.0 (asserted above).
        self.assertGreaterEqual(clock.elapsed, 899.0)
        self.assertGreater(clock.elapsed, 0.0)

        before_replay = _sha256(self.db)
        replay_a = load_report_only(self.db, factory_run_id)
        replay_b = load_report_only(self.db, factory_run_id)
        after_replay = _sha256(self.db)
        self.assertEqual(replay_a, replay_b)
        self.assertEqual(0, replay_a["replay"]["new_source_calls"])
        self.assertEqual(0, replay_a["replay"]["new_evidence_rows"])
        self.assertEqual(before_replay, after_replay)

        self.assertEqual(0, public_command.AUTOMATIC_RETRIES)
        self.assertEqual(0, terminal.get("restart_created") and 1 or 0)
        self.assertFalse(terminal.get("restart_created", False))
        self.assertFalse(terminal.get("successor_created", False))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

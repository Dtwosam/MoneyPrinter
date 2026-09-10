"""Focused disposable proofs for terminal-only expired-orphan reconciliation.

No live provider/RPC/Scheduler execution and no authoritative production DB use.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.db.migrate import canonical_migration_count, canonical_migration_names
from printer_v1.operator_cli.campaign_ownership import create_campaign_run
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_OPERATIONAL_PERSISTENT,
    build_authorization_marker_payload,
    campaign_evidence_sha256,
    create_campaign,
)
from printer_v1.operator_cli.four_token_operational_composition import (
    POLICY_VERSION,
    exact_operational_policy,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    build_four_token_proof_policy,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    multi_cycle_configuration_contract,
)
from printer_v1.operator_cli.operational_database_target_binding import (
    PRODUCTION_AUTHORITATIVE,
    build_durable_operational_database_target_expectation,
)


NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat()


def _load_orphan_module():
    try:
        return importlib.import_module(
            "printer_v1.operator_cli.expired_orphan_reconciliation"
        )
    except ModuleNotFoundError:
        return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _provenance() -> dict[str, object]:
    return {
        "git_head": "f" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": NOW_ISO,
    }


class ExpiredOrphanFixture:
    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.db = self.root / "printer.sqlite3"
        self.artifact_root = self.root / "artifacts"
        self.artifact_root.mkdir()
        apply_migrations(self.db)

        self.execution_id = "20260910T110000Z-expiredorphan"
        self.campaign_id = f"{self.execution_id}-campaign"
        self.configuration_id = f"{self.execution_id}-configuration"
        self.run_id = f"{self.execution_id}-campaign-run"
        self.cycle_id = f"{self.execution_id}-cycle"
        self.supervision_id = f"{self.execution_id}-supervision"
        self.owner_id = f"{self.execution_id}-owner"
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
            cycle_id=self.cycle_id,
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
        multi_cycle = multi_cycle_configuration_contract(
            build_four_token_proof_policy(
                minimum_spacing_seconds=300,
                intake_duration_seconds=18_000,
            ),
            intake_started_at=NOW - timedelta(minutes=30),
        )
        expected = exact_operational_policy()
        configuration = {
            "execution_id": self.execution_id,
            "campaign_id": self.campaign_id,
            "configuration_id": self.configuration_id,
            "run_id": self.run_id,
            "cycle_id": self.cycle_id,
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
        try:
            create_campaign_run(
                connection,
                campaign_id=self.campaign_id,
                run_id=self.run_id,
                run_ordinal=1,
                now=NOW_ISO,
            )
            connection.execute(
                """INSERT INTO printer_memory_factory_campaign_cycles(
                       cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
                       created_at,updated_at
                   ) VALUES (?,?,?,1,'PLANNED',?,?)""",
                (self.cycle_id, self.campaign_id, self.run_id, NOW_ISO, NOW_ISO),
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
            heartbeat = (NOW - timedelta(minutes=5)).isoformat()
            expires = (NOW - timedelta(minutes=3)).isoformat()
            connection.execute(
                """INSERT INTO printer_memory_factory_campaign_supervision(
                       supervision_id,campaign_id,configuration_id,run_id,owner_id,
                       supervision_state,terminal_status,first_terminal_cause,
                       heartbeat_at,lease_expires_at,lease_lock_path,
                       cancellation_requested_at,cancellation_reason,
                       cleanup_completed_at,lease_released_at,created_at,updated_at
                   ) VALUES (?,?,?,?,?,'ACTIVE',NULL,NULL,?,?,?,?,NULL,NULL,NULL,?,?)""",
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

    def close(self) -> None:
        self.tmp.cleanup()


class ExpiredOrphanInspectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orphan = _load_orphan_module()
        self.fx = ExpiredOrphanFixture()

    def tearDown(self) -> None:
        self.fx.close()

    def _inspect(self, *, now: datetime = NOW):
        self.assertIsNotNone(
            self.orphan,
            "expired orphan inspector is not implemented",
        )
        return self.orphan.inspect_expired_orphan(
            self.fx.db,
            campaign_id=self.fx.campaign_id,
            run_id=self.fx.run_id,
            artifact_root=self.fx.artifact_root,
            expected_db_path=self.fx.db,
            process_inventory=lambda: (),
            now=now,
        )

    def test_inspection_detects_exact_eligible_pre_admission_expired_orphan(self) -> None:
        result = self._inspect()
        self.assertIs(result["eligible"], True)
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["admitted_shape"], "PRE_ADMISSION")
        self.assertEqual(len(result["inspection_sha256"]), 64)
        self.assertEqual(result["source_calls"], 0)
        self.assertEqual(result["scheduler_runtime_calls"], 0)
        self.assertEqual(result["database_writes"], 0)

    def test_inspection_sha_is_stable_when_only_observation_time_advances(self) -> None:
        first = self._inspect(now=NOW)
        second = self._inspect(now=NOW + timedelta(minutes=10))
        self.assertEqual(first["inspection_sha256"], second["inspection_sha256"])


if __name__ == "__main__":
    unittest.main()

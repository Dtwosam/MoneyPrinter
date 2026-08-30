import json
from pathlib import Path
import signal
import sqlite3
import tempfile
import unittest

from printer_v1.operator_cli.linux_remote_host_portability import (
    LinuxPortabilityError,
    StopSignalState,
    attempt_exact_active_cancellation,
    fsync_directory_required,
    resolve_exact_active_supervision,
)


MANIFEST_SHA = "1" * 64
APPLICATION_MARKER_SHA = "2" * 64
OTHER_MANIFEST_SHA = "3" * 64
OTHER_APPLICATION_MARKER_SHA = "4" * 64


class FullPathDurabilityIdentityTests(unittest.TestCase):
    def test_parent_symlink_alias_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            real = root / "real"
            target = real / "nested"
            target.mkdir(parents=True)
            alias = root / "alias"
            try:
                alias.symlink_to(real, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unsupported")

            # The final component is a real directory. The alias exists only in
            # a parent component, which must still fail closed.
            with self.assertRaises(LinuxPortabilityError):
                fsync_directory_required(alias / "nested")


class ExactWrapperInvocationBindingTests(unittest.TestCase):
    def _database(self, root: Path) -> Path:
        path = root / "supervision.sqlite3"
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            CREATE TABLE printer_memory_factory_campaign_supervision (
                supervision_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                configuration_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                supervision_state TEXT NOT NULL,
                cancellation_requested_at TEXT,
                cancellation_reason TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE printer_memory_factory_campaign_configurations (
                configuration_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                configuration_json TEXT NOT NULL
            );
            """
        )
        conn.commit()
        conn.close()
        return path

    def _insert_bound_active(
        self,
        path: Path,
        *,
        suffix: str = "1",
        manifest_sha: str = MANIFEST_SHA,
        application_marker_sha: str = APPLICATION_MARKER_SHA,
    ) -> None:
        campaign_id = f"camp-{suffix}"
        configuration_id = f"cfg-{suffix}"
        run_id = f"run-{suffix}"
        execution_id = f"exec-{suffix}"
        expectation = {
            "expectation_version": "OPERATIONAL_DATABASE_TARGET_EXPECTATION_V1",
            "authorization_id": f"auth-{suffix}",
            "authorization_marker_sha256": manifest_sha,
            "application_marker_sha256": application_marker_sha,
            "execution_id": execution_id,
            "campaign_id": campaign_id,
            "campaign_run_id": run_id,
            "cycle_id": f"cycle-{suffix}",
            "configuration_id": configuration_id,
            "authorization_consumed_once": True,
            "invocation_count": 1,
            "allowed_invocation_count": 1,
            "automatic_retry_allowed": False,
            "manual_rerun_allowed": False,
            "resume_allowed": False,
            "restart_allowed": False,
            "successor_allowed": False,
        }
        configuration = {
            "authorization_marker": {
                "marker_id": f"{execution_id}-authorization-marker",
                "execution_id": execution_id,
                "campaign_id": campaign_id,
                "configuration_id": configuration_id,
                "run_id": run_id,
            },
            "operational_database_target_expectation": expectation,
        }
        conn = sqlite3.connect(path)
        conn.execute(
            """INSERT INTO printer_memory_factory_campaign_configurations(
                   configuration_id,campaign_id,configuration_json
               ) VALUES (?,?,?)""",
            (configuration_id, campaign_id, json.dumps(configuration, sort_keys=True)),
        )
        conn.execute(
            """INSERT INTO printer_memory_factory_campaign_supervision(
                   supervision_id,campaign_id,configuration_id,run_id,owner_id,
                   supervision_state,created_at
               ) VALUES (?,?,?,?,?,'ACTIVE',?)""",
            (
                f"sup-{suffix}",
                campaign_id,
                configuration_id,
                run_id,
                f"owner-{suffix}",
                "2999-01-01T00:00:00+00:00",
            ),
        )
        conn.commit()
        conn.close()

    def test_temporal_uniqueness_without_wrapper_binding_is_not_authority(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._database(Path(td))
            self._insert_bound_active(
                path,
                manifest_sha=OTHER_MANIFEST_SHA,
                application_marker_sha=OTHER_APPLICATION_MARKER_SHA,
            )
            with self.assertRaises(LinuxPortabilityError):
                resolve_exact_active_supervision(
                    path,
                    child_started_at="2026-08-27T18:00:00+00:00",
                    expected_manifest_sha256=MANIFEST_SHA,
                    expected_application_marker_sha256=APPLICATION_MARKER_SHA,
                )

    def test_exact_wrapper_hash_binding_resolves_one_supervision(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._database(Path(td))
            self._insert_bound_active(path)
            row = resolve_exact_active_supervision(
                path,
                child_started_at="2026-08-27T18:00:00+00:00",
                expected_manifest_sha256=MANIFEST_SHA,
                expected_application_marker_sha256=APPLICATION_MARKER_SHA,
            )
            self.assertEqual(row["supervision_id"], "sup-1")
            self.assertEqual(row["execution_id"], "exec-1")

    def test_only_exactly_bound_row_can_receive_cancellation(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._database(Path(td))
            self._insert_bound_active(path)
            state = StopSignalState()
            state.handle_signal(signal.SIGTERM, None)
            calls = []

            def requester(db_path, **kwargs):
                calls.append((Path(db_path), kwargs))
                return {"cancellation_requested": True}

            applied = attempt_exact_active_cancellation(
                path,
                stop_state=state,
                child_started_at="2026-08-27T18:00:00+00:00",
                expected_manifest_sha256=MANIFEST_SHA,
                expected_application_marker_sha256=APPLICATION_MARKER_SHA,
                requester=requester,
            )
            self.assertTrue(applied)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][1]["supervision_id"], "sup-1")


if __name__ == "__main__":
    unittest.main()

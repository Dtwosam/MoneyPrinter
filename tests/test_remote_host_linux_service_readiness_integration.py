from pathlib import Path
import tempfile
import unittest

from printer_v1.operator_cli import four_token_standard_four_hour_linux_service as service


class ServiceReadinessIntegrationTests(unittest.TestCase):
    def test_disk_and_time_readiness_run_before_authorization_application(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "data" / "printer.sqlite3"
            db.parent.mkdir()
            db.write_bytes(b"db")
            order = []

            def filesystem_preflight(paths, **kwargs):
                order.append("filesystem")
                return {key: {"approved": True} for key in paths}

            def disk_space_preflight(**kwargs):
                order.append("disk")
                self.assertEqual(Path(kwargs["authoritative_db_path"]), db.resolve())
                self.assertEqual(kwargs["storage_growth_ceiling_bytes"], 100)
                self.assertEqual(
                    set(kwargs["write_paths"]),
                    {
                        "authoritative_db_parent",
                        "application_root",
                        "operational_artifact_root",
                    },
                )
                return {"required_free_bytes": 123, "paths": {}}

            def time_sync_preflight(**kwargs):
                order.append("time")
                return {"ntp_synchronized": True, "approved": True}

            def apply_authorization(**kwargs):
                order.append("apply")
                return {"terminal_classification": "fixture"}

            result = service.run_linux_service(
                authorization_file=root / "authorization.json",
                authorization_sha256="a" * 64,
                operator_approved=True,
                repository_root=root,
                application_root=root / "applications",
                authoritative_db_path=db,
                artifact_root=root / "artifacts",
                filesystem_preflight=filesystem_preflight,
                disk_space_preflight=disk_space_preflight,
                time_sync_preflight=time_sync_preflight,
                storage_growth_ceiling_bytes=100,
                apply_authorization=apply_authorization,
            )

            self.assertEqual(order, ["filesystem", "disk", "time", "apply"])
            self.assertEqual(
                result["host_readiness"]["disk_space"]["required_free_bytes"],
                123,
            )
            self.assertTrue(
                result["host_readiness"]["time_sync"]["ntp_synchronized"]
            )

    def test_stop_during_disk_preflight_blocks_time_and_application(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "printer.sqlite3"
            db.write_bytes(b"db")
            state = service.StopSignalState()
            order = []

            def filesystem_preflight(paths, **kwargs):
                order.append("filesystem")
                return {key: {"approved": True} for key in paths}

            def disk_space_preflight(**kwargs):
                order.append("disk")
                state.handle_signal(15, None)
                return {"required_free_bytes": 123, "paths": {}}

            def time_sync_preflight(**kwargs):
                order.append("time")
                return {"ntp_synchronized": True, "approved": True}

            def apply_authorization(**kwargs):
                order.append("apply")
                return {"terminal_classification": "fixture"}

            with self.assertRaises(service.LinuxPortabilityError):
                service.run_linux_service(
                    authorization_file=root / "authorization.json",
                    authorization_sha256="a" * 64,
                    operator_approved=True,
                    repository_root=root,
                    application_root=root / "applications",
                    authoritative_db_path=db,
                    artifact_root=root / "artifacts",
                    filesystem_preflight=filesystem_preflight,
                    disk_space_preflight=disk_space_preflight,
                    time_sync_preflight=time_sync_preflight,
                    storage_growth_ceiling_bytes=100,
                    apply_authorization=apply_authorization,
                    stop_state=state,
                )

            self.assertEqual(order, ["filesystem", "disk"])


if __name__ == "__main__":
    unittest.main()

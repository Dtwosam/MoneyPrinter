import importlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


MODULE = "printer_v1.operator_cli.four_token_standard_four_hour_linux_service"


class ServiceEntrypointTests(unittest.TestCase):
    def test_service_preflight_precedes_application(self):
        spec = importlib.util.find_spec(MODULE)
        self.assertIsNotNone(spec, "Linux service entrypoint module is missing")
        if spec is None:
            return
        service = importlib.import_module(MODULE)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "data" / "printer.sqlite3"
            db.parent.mkdir()
            db.write_bytes(b"db")
            app = root / "applications"
            artifacts = root / "artifacts"
            order = []

            def preflight(paths, **kwargs):
                order.append(("preflight", dict(paths)))
                return {key: {"approved": True} for key in paths}

            def disk_space_preflight(**kwargs):
                return {"required_free_bytes": 1, "paths": {}}

            def time_sync_preflight(**kwargs):
                return {"ntp_synchronized": True, "approved": True}

            def apply_authorization(**kwargs):
                order.append(("apply", kwargs))
                return {"status": "fixture"}

            result = service.run_linux_service(
                authorization_file=root / "authorization.json",
                authorization_sha256="a" * 64,
                operator_approved=True,
                repository_root=root,
                application_root=app,
                authoritative_db_path=db,
                artifact_root=artifacts,
                filesystem_preflight=preflight,
                disk_space_preflight=disk_space_preflight,
                time_sync_preflight=time_sync_preflight,
                storage_growth_ceiling_bytes=100,
                apply_authorization=apply_authorization,
            )
            self.assertEqual(
                [item[0] for item in order], ["preflight", "apply"]
            )
            self.assertTrue(callable(order[1][1]["process_launcher"]))
            self.assertEqual(
                Path(order[1][1]["authoritative_db_path"]), db.resolve()
            )
            self.assertIs(
                order[1][1]["printer_host_process_inventory"],
                service.linux_verified_host_process_inventory,
            )
            self.assertEqual(
                result["filesystem_preflight"]["authoritative_db"]["approved"],
                True,
            )

    def test_pre_marker_stop_blocks_application(self):
        spec = importlib.util.find_spec(MODULE)
        self.assertIsNotNone(spec, "Linux service entrypoint module is missing")
        if spec is None:
            return
        service = importlib.import_module(MODULE)
        state = service.StopSignalState()
        state.handle_signal(15, None)
        calls = []
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "data" / "printer.sqlite3"
            db.parent.mkdir()
            db.write_bytes(b"db")

            def preflight(paths, **kwargs):
                calls.append("preflight")
                return {key: {"approved": True} for key in paths}

            def apply_authorization(**kwargs):
                calls.append("apply")
                return {"status": "fixture"}

            with self.assertRaises(service.LinuxPortabilityError):
                service.run_linux_service(
                    authorization_file=root / "authorization.json",
                    authorization_sha256="a" * 64,
                    operator_approved=True,
                    repository_root=root,
                    application_root=root / "applications",
                    authoritative_db_path=db,
                    artifact_root=root / "artifacts",
                    filesystem_preflight=preflight,
                    storage_growth_ceiling_bytes=100,
                    apply_authorization=apply_authorization,
                    stop_state=state,
                )
        self.assertEqual(calls, ["preflight"])

    def test_main_rejects_zero_exit_with_invalid_terminal_truth(self):
        service = importlib.import_module(MODULE)
        with patch.object(
            service,
            "run_linux_service",
            return_value={
                "terminal_classification": "CHILD_EXITED_ZERO_TERMINAL_INVALID"
            },
        ):
            code = service.main(
                [
                    "--authorization-file",
                    "/tmp/auth.json",
                    "--authorization-sha256",
                    "a" * 64,
                    "--operator-approved",
                ]
            )
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()

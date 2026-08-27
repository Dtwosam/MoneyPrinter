from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.operator_cli import window_15m_one_shot_wrapper as wrapper


class SharedOneShotDirectoryDurabilityTests(unittest.TestCase):
    def test_linux_create_once_syncs_parent_after_file_fsync(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "application" / "application-marker.json"
            sync_calls = []
            with (
                patch.object(wrapper.sys, "platform", "linux"),
                patch.object(
                    wrapper,
                    "_fsync_directory",
                    side_effect=lambda value: sync_calls.append(Path(value)),
                ),
            ):
                wrapper._write_exclusive(path, b"marker\n")
            self.assertEqual(sync_calls, [path.parent])
            self.assertEqual(path.read_bytes(), b"marker\n")

    def test_linux_create_once_durability_failure_keeps_created_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "application" / "application-marker.json"
            with (
                patch.object(wrapper.sys, "platform", "linux"),
                patch.object(
                    wrapper,
                    "_fsync_directory",
                    side_effect=wrapper.OneShotWrapperError(
                        "injected directory durability failure"
                    ),
                ),
            ):
                with self.assertRaises(wrapper.OneShotWrapperError):
                    wrapper._write_exclusive(path, b"marker\n")
            self.assertTrue(path.exists())

    def test_linux_directory_sync_failure_is_not_swallowed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with (
                patch.object(wrapper.sys, "platform", "linux"),
                patch(
                    "printer_v1.operator_cli.linux_remote_host_portability."
                    "fsync_directory_required",
                    side_effect=RuntimeError("injected fsync failure"),
                ),
            ):
                with self.assertRaises(wrapper.OneShotWrapperError):
                    wrapper._fsync_directory(root)


if __name__ == "__main__":
    unittest.main()

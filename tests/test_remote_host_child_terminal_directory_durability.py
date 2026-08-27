from pathlib import Path
import tempfile
import unittest

from printer_v1.operator_cli import window_15m_child_terminal as child_terminal


class ChildTerminalDirectoryDurabilityTests(unittest.TestCase):
    def _binding(self, root: Path) -> child_terminal.ChildTerminalBinding:
        return child_terminal.ChildTerminalBinding(
            terminal_path=root / "child-terminal.json",
            marker_path=root / "application-marker.json",
            authorization_id="auth-1",
            marker_sha256="a" * 64,
        )

    def test_publication_syncs_parent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sync_calls = []
            child_terminal.write_child_terminal_envelope(
                binding=self._binding(root),
                source={"status": "OK"},
                mode="run",
                exit_code=0,
                success=True,
                directory_sync=lambda path: sync_calls.append(Path(path)),
            )
            self.assertEqual(sync_calls, [root])

    def test_sync_failure_blocks_and_keeps_created_terminal(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            binding = self._binding(root)

            def fail_sync(_path):
                raise OSError("injected directory fsync failure")

            with self.assertRaises(child_terminal.ChildTerminalError):
                child_terminal.write_child_terminal_envelope(
                    binding=binding,
                    source={"status": "OK"},
                    mode="run",
                    exit_code=0,
                    success=True,
                    directory_sync=fail_sync,
                )

            self.assertTrue(binding.terminal_path.exists())


if __name__ == "__main__":
    unittest.main()

import subprocess
import unittest

from printer_v1.operator_cli import operational_campaign_recovery as recovery


class _Result:
    def __init__(self, *, stdout: str, returncode: int = 0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


class LinuxProcessInventoryTests(unittest.TestCase):
    def test_posix_inventory_uses_one_bounded_ps_pass_and_parses(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return _Result(
                stdout=(
                    "  101 /opt/printer/.venv/bin/python -m "
                    "printer_v1.operator_cli.operational_memory_factory_command "
                    "four-token-standard-four-hour-run --operator-approved\n"
                    "  202 /usr/bin/other-process\n"
                )
            )

        inventory = recovery.host_process_inventory(runner=runner)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], ["ps", "-axo", "pid=,command="])
        self.assertEqual(calls[0][1]["shell"], False)
        self.assertEqual(calls[0][1]["check"], False)
        self.assertGreater(calls[0][1]["timeout"], 0)
        self.assertEqual(inventory[0][0], 101)
        self.assertIn("four-token-standard-four-hour-run", inventory[0][1])

    def test_malformed_nonempty_ps_line_fails_closed(self):
        def runner(command, **kwargs):
            return _Result(stdout="not-a-pid ambiguous-command\n")

        with self.assertRaises(recovery.OperationalCampaignRecoveryError):
            recovery.host_process_inventory(runner=runner)

    def test_ps_failure_fails_closed(self):
        def runner(command, **kwargs):
            return _Result(stdout="", returncode=1)

        with self.assertRaises(recovery.OperationalCampaignRecoveryError):
            recovery.host_process_inventory(runner=runner)


if __name__ == "__main__":
    unittest.main()

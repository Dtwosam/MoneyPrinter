from __future__ import annotations

import inspect
import os
import unittest
from unittest import mock

from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli import authoritative_live_operational_campaign as live


class StandardFourHourActivationFinalPublicWiringTests(unittest.TestCase):
    def test_standard_policy_has_distinct_identity_and_expected_outer_locks(self) -> None:
        policy = command.STANDARD_FOUR_HOUR_POLICY
        self.assertEqual(policy.mode, command.STANDARD_FOUR_HOUR_MODE)
        self.assertEqual(policy.policy_version, command.STANDARD_FOUR_HOUR_POLICY_VERSION)
        self.assertTrue(policy.selective_1h_continuation)
        self.assertTrue(policy.continuous_four_hour)
        self.assertTrue(policy.standard_four_hour_campaign)
        self.assertEqual(policy.locked_windows, ("WINDOW_12H", "WINDOW_24H"))
        self.assertEqual(policy.governed_request_ceiling, 230)
        self.assertEqual(policy.governed_requests_per_token, 114)
        self.assertEqual(policy.scheduler_row_ceiling, 210)
        self.assertFalse(command._NORMAL_CAMPAIGN_POLICY.continuous_four_hour)
        self.assertFalse(command._NORMAL_CAMPAIGN_POLICY.standard_four_hour_campaign)

    def test_standard_preflight_is_distinct_read_only_policy_projection(self) -> None:
        self.assertTrue(hasattr(command, "build_standard_four_hour_preflight"))
        base = {
            "status": "V2_9_8_OPERATIONAL_PREFLIGHT_READY",
            "database_path": "/tmp/fake.sqlite3",
            "database_sha256": "a" * 64,
            "policy": {"locked_windows": command.LOCKED_WINDOWS},
            "ceilings": {},
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        }
        with mock.patch.object(command, "build_activation_preflight", return_value=base):
            result = command.build_standard_four_hour_preflight()
        self.assertEqual(result["mode"], command.STANDARD_FOUR_HOUR_PREFLIGHT_MODE)
        self.assertEqual(result["status"], "V2_9_8B_STANDARD_FOUR_HOUR_PREFLIGHT_READY")
        self.assertTrue(result["standard_four_hour_policy"]["continuous_first_hour"])
        self.assertTrue(result["standard_four_hour_policy"]["continuous_four_hour"])
        self.assertTrue(result["standard_four_hour_policy"]["standard_four_hour_campaign"])
        self.assertEqual(
            tuple(result["standard_four_hour_policy"]["locked_windows"]),
            ("WINDOW_12H", "WINDOW_24H"),
        )
        self.assertEqual(result["standard_four_hour_ceilings"]["governed_requests"], 230)
        self.assertEqual(result["standard_four_hour_ceilings"]["scheduler_rows"], 210)
        self.assertEqual(result["source_calls"], 0)
        self.assertEqual(result["scheduler_runtime_calls"], 0)
        self.assertEqual(result["database_writes"], 0)

    def test_standard_run_wrapper_selects_only_standard_policy(self) -> None:
        self.assertTrue(hasattr(command, "run_standard_four_hour_campaign"))
        authorization = object()
        with mock.patch.object(command, "_run_operational_campaign", return_value={"ok": True}) as runner:
            result = command.run_standard_four_hour_campaign(
                operator_approved=True,
                git_provenance_authorization=authorization,
            )
        self.assertEqual(result, {"ok": True})
        kwargs = runner.call_args.kwargs
        self.assertIs(kwargs["policy"], command.STANDARD_FOUR_HOUR_POLICY)
        self.assertIs(kwargs["git_provenance_authorization"], authorization)
        self.assertTrue(kwargs["operator_approved"])

    def test_standard_policy_routes_standard_preflight_and_authorized_db_binding(self) -> None:
        source = inspect.getsource(command._run_operational_campaign)
        self.assertIn("policy.standard_four_hour_campaign", source)
        self.assertIn("build_standard_four_hour_preflight", source)
        self.assertIn("validated_authorization_runtime_facts", source)
        self.assertNotIn(
            "if policy.selective_1h_continuation or disposable_proof is not None",
            source,
        )

    def test_standard_campaign_configuration_uses_selected_policy_truth(self) -> None:
        source = inspect.getsource(command._create_campaign_command)
        self.assertIn('"policy_version": policy.policy_version', source)
        self.assertIn('"continuous_four_hour": bool(policy.continuous_four_hour)', source)
        self.assertIn(
            '"standard_four_hour_campaign": bool(policy.standard_four_hour_campaign)',
            source,
        )
        self.assertIn("policy_version=policy.policy_version", source)

    def test_live_owner_has_explicit_persistent_standard_authority(self) -> None:
        signature = inspect.signature(live.AuthoritativeLiveOperationalCampaignOwner.run_operational)
        self.assertIn("standard_four_hour_campaign", signature.parameters)
        self.assertFalse(signature.parameters["standard_four_hour_campaign"].default)
        source = inspect.getsource(live.AuthoritativeLiveOperationalCampaignOwner.run_operational)
        self.assertIn("standard_four_hour_campaign", source)
        self.assertIn("operational_persistent_mode=fifteen_minute_only", source)
        self.assertIn("continuous_first_hour", source)
        self.assertIn("continuous_four_hour", source)
        self.assertIn("four_hour_proof_mode", source)

    def test_public_coordinator_threads_standard_authority_to_live_owner_and_factory(self) -> None:
        source = inspect.getsource(command._run_operational_campaign)
        self.assertIn("standard_four_hour_campaign=policy.standard_four_hour_campaign", source)
        self.assertIn('"standard_four_hour_campaign": (', source)
        self.assertIn("policy.standard_four_hour_campaign", source)
        self.assertIn("policy.continuous_four_hour", source)

    def test_terminal_summary_reports_selected_four_hour_policy(self) -> None:
        source = inspect.getsource(command._run_operational_campaign)
        self.assertIn('"continuous_four_hour": policy.continuous_four_hour', source)
        self.assertIn(
            '"standard_four_hour_campaign": policy.standard_four_hour_campaign',
            source,
        )
        self.assertIn('"policy_version": policy.policy_version', source)

    def test_main_standard_mode_dispatches_only_after_wrapper_binding(self) -> None:
        authorization = object()
        terminal_binding = object()
        result = {
            "status": "OPERATIONAL_CAMPAIGN_TERMINAL",
            "continuous_four_hour": True,
            "standard_four_hour_campaign": True,
        }
        env = {
            "PRINTER_V1_GIT_PROVENANCE_MANIFEST_PATH": "/tmp/manifest.json",
            "PRINTER_V1_GIT_PROVENANCE_MANIFEST_SHA256": "a" * 64,
            "PRINTER_V1_APPLICATION_MARKER_PATH": "/tmp/marker.json",
            "PRINTER_V1_APPLICATION_MARKER_SHA256": "b" * 64,
        }
        with mock.patch.dict(os.environ, env, clear=False), mock.patch(
            "printer_v1.operator_cli.window_15m_child_terminal.resolve_child_terminal_binding",
            return_value=terminal_binding,
        ), mock.patch.object(
            command, "_resolve_git_provenance_authorization", return_value=authorization
        ), mock.patch.object(
            command, "run_standard_four_hour_campaign", return_value=result, create=True
        ) as runner, mock.patch(
            "printer_v1.operator_cli.window_15m_child_terminal.write_child_terminal_envelope"
        ) as terminal_writer:
            exit_code = command.main([command.STANDARD_FOUR_HOUR_MODE, "--operator-approved"])
        self.assertEqual(exit_code, 0)
        runner.assert_called_once_with(
            operator_approved=True,
            git_provenance_authorization=authorization,
        )
        terminal_writer.assert_called_once()

    def test_direct_unwrapped_standard_mode_remains_fail_closed(self) -> None:
        with mock.patch.dict(
            os.environ,
            {name: "" for name in command.GIT_PROVENANCE_MANIFEST_ENV_VARS},
            clear=False,
        ), mock.patch.object(command, "run_standard_four_hour_campaign", create=True) as runner:
            exit_code = command.main([command.STANDARD_FOUR_HOUR_MODE, "--operator-approved"])
        self.assertEqual(exit_code, 1)
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()

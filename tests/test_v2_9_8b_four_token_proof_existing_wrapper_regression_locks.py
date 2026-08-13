"""Regression locks: the four-token lane must not widen existing wrappers.

Offline only. These locks pin the ordinary WINDOW_15M and standard-four-hour
authorization surfaces so a later four-token change cannot silently widen the
public two-token production boundary.
"""

from __future__ import annotations

import inspect
import unittest

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli import standard_four_hour_one_shot_wrapper as standard
from printer_v1.operator_cli import window_15m_child_terminal as child_terminal
from printer_v1.operator_cli import window_15m_one_shot_wrapper as ordinary
from printer_v1.operator_cli.operational_standard_4h import (
    standard_four_hour_capacity_contract,
)


class ExistingWrapperRegressionLockTests(unittest.TestCase):
    def test_ordinary_profile_is_unchanged(self) -> None:
        profile = git_auth.ORDINARY_AUTHORIZATION_PROFILE
        self.assertEqual(profile.command_mode, "run")
        self.assertEqual(
            profile.authorization_package_root,
            "operator-runs/v2-9-8b-window-15m-final-authorization",
        )
        self.assertEqual(
            profile.authorization_package_kind, "WINDOW_15M_AUTHORIZATION_EVIDENCE"
        )
        self.assertEqual(
            profile.manifest_schema_version, "PRINTER_V1_GIT_PROVENANCE_MANIFEST_V2"
        )
        self.assertEqual(
            profile.historical_authorization_package_roots,
            ("operator-runs/v2-9-8b-window-15m-final-authorization",),
        )
        self.assertEqual(
            profile.migration_package_root,
            "operator-runs/v2-9-8b-authoritative-mig050",
        )
        self.assertEqual(profile.migration_package_kind, "MIGRATION_050_EVIDENCE")
        self.assertIs(git_auth._resolved_profile(None), profile)

    def test_standard_four_hour_profile_is_unchanged(self) -> None:
        profile = git_auth.STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        self.assertEqual(profile.command_mode, "standard-four-hour-run")
        self.assertEqual(
            profile.authorization_package_root,
            "operator-runs/v2-9-8b-standard-four-hour-final-authorization",
        )
        self.assertEqual(
            profile.authorization_package_kind,
            "STANDARD_FOUR_HOUR_AUTHORIZATION_EVIDENCE",
        )
        self.assertEqual(
            profile.manifest_schema_version,
            "PRINTER_V1_GIT_PROVENANCE_MANIFEST_STANDARD_4H_V1",
        )
        self.assertEqual(
            profile.historical_authorization_package_roots,
            (
                "operator-runs/v2-9-8b-window-15m-final-authorization",
                "operator-runs/v2-9-8b-standard-four-hour-final-authorization",
            ),
        )
        self.assertEqual(
            profile.migration_package_root,
            "operator-runs/v2-9-8b-authoritative-mig050",
        )
        self.assertEqual(profile.migration_package_kind, "MIGRATION_050_EVIDENCE")

    def test_standard_four_hour_wrapper_contract_is_unchanged(self) -> None:
        capacity = standard_four_hour_capacity_contract()
        self.assertEqual(standard.AUTHORIZED_COMMAND_MODE, "standard-four-hour-run")
        self.assertEqual(
            standard.FINAL_AUTHORIZATION_SCHEMA_VERSION,
            "PRINTER_V1_STANDARD_FOUR_HOUR_FINAL_AUTHORIZATION_V1",
        )
        self.assertEqual(
            standard.WRAPPER_SCHEMA_VERSION,
            "PRINTER_V1_STANDARD_FOUR_HOUR_ONE_SHOT_WRAPPER_V1",
        )
        self.assertEqual(standard.POST_SUPPLY_DURATION_SECONDS, 14_700)
        self.assertEqual(standard.PRE_LIFECYCLE_DURATION_SECONDS, 900)
        self.assertEqual(
            standard.LIFECYCLE_REQUEST_OUTER_CEILING,
            int(capacity["lifecycle_request_outer_ceiling"]),
        )
        self.assertEqual(
            standard.LIFECYCLE_SCHEDULER_OUTER_CEILING,
            int(capacity["lifecycle_scheduler_outer_ceiling"]),
        )
        self.assertEqual(
            standard.APPLICATION_ROOT.name,
            "standard-four-hour-one-shot-applications",
        )
        self.assertEqual(
            standard.build_child_command("/usr/bin/python3")[-2:],
            ["standard-four-hour-run", "--operator-approved"],
        )

    def test_standard_document_still_binds_exactly_two_tokens(self) -> None:
        document = standard.fixture_authorization_document(
            branch="agent/lock",
            head="a" * 40,
            database={
                "path": "/tmp/printer.sqlite3",
                "sha256": "b" * 64,
                "size": 1,
                "inode": 1,
                "mtime_ns": 1,
                "migration_count": 54,
                "migration_head": "054_pre_lifecycle_discovery_refresh_wait.sql",
            },
        )
        validated = standard.validate_standard_four_hour_authorization_document(
            document
        )
        self.assertEqual(validated["campaign_policy"]["token_capacity"], 2)
        self.assertEqual(
            validated["campaign_policy"]["root_main_window"], "WINDOW_15M"
        )
        self.assertEqual(
            validated["campaign_policy"]["locked_windows"],
            ["WINDOW_12H", "WINDOW_24H"],
        )
        self.assertNotIn("proof_policy", validated)

    def test_ordinary_one_shot_primitives_are_untouched(self) -> None:
        self.assertEqual(
            ordinary.BINDING_ENV_VARS,
            (
                "PRINTER_V1_GIT_PROVENANCE_MANIFEST_PATH",
                "PRINTER_V1_GIT_PROVENANCE_MANIFEST_SHA256",
                "PRINTER_V1_APPLICATION_MARKER_PATH",
                "PRINTER_V1_APPLICATION_MARKER_SHA256",
            ),
        )
        self.assertEqual(
            child_terminal.CHILD_TERMINAL_MODE_SCHEMAS["run"],
            "PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_V1",
        )
        self.assertEqual(
            child_terminal.CHILD_TERMINAL_MODE_SCHEMAS["standard-four-hour-run"],
            "PRINTER_V1_STANDARD_FOUR_HOUR_CHILD_TERMINAL_V1",
        )

    def test_public_command_surface_is_unchanged(self) -> None:
        self.assertEqual(command.TOKEN_CAPACITY, 2)
        self.assertEqual(command.STANDARD_FOUR_HOUR_MODE, "standard-four-hour-run")
        self.assertEqual(command.STANDARD_FOUR_HOUR_TOTAL_DURATION_SECONDS, 14_700)
        policy = command.STANDARD_FOUR_HOUR_POLICY
        self.assertEqual(policy.duration_seconds, 14_700)
        self.assertEqual(policy.locked_windows, ("WINDOW_12H", "WINDOW_24H"))
        self.assertIs(policy.standard_four_hour_campaign, True)
        for original in ("preflight-only", "run", "standard-four-hour-run"):
            self.assertIn(
                original, command.GIT_PROVENANCE_MANIFEST_SUPPORTED_MODES
            )
        for runner in (
            command.run_operational_campaign,
            command.run_standard_four_hour_campaign,
            command.run_selective_1h_proof,
        ):
            parameters = inspect.signature(runner).parameters
            self.assertNotIn("four_token_proof_controller", parameters)
            self.assertNotIn("token_capacity", parameters)


if __name__ == "__main__":  # pragma: no cover - direct invocation guard
    unittest.main()

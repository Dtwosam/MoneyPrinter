"""RED contract for the proof-only four-token canonical factory wiring.

This file is intentionally offline at this step. It must not start Printer,
perform source work, or mutate an authoritative database.
"""

from __future__ import annotations

import ast
from datetime import datetime
import inspect
from pathlib import Path
import unittest
from unittest.mock import patch

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli.four_token_proof_integration import (
    build_four_token_proof_policy,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    multi_cycle_configuration_contract,
)


class FourTokenCanonicalFactoryWiringContractTests(unittest.TestCase):
    def test_private_canonical_coordinator_has_optional_proof_controller_seam(self) -> None:
        parameter = inspect.signature(command._run_operational_campaign).parameters.get(
            "four_token_proof_controller"
        )
        self.assertIsNotNone(parameter)
        self.assertEqual(parameter.kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIsNone(parameter.default)

    def test_proof_controller_seam_is_not_public_runtime_authority(self) -> None:
        self.assertEqual(command.TOKEN_CAPACITY, 2)
        for public_runner in (
            command.run_operational_campaign,
            command.run_standard_four_hour_campaign,
            command.run_selective_1h_proof,
        ):
            with self.subTest(public_runner=public_runner.__name__):
                self.assertNotIn(
                    "four_token_proof_controller",
                    inspect.signature(public_runner).parameters,
                )

    def test_proof_controller_fails_closed_outside_private_standard_four_hour_path(self) -> None:
        controller = object()
        cases = (
            (command._NORMAL_CAMPAIGN_POLICY, "build_activation_preflight"),
            (command._SELECTIVE_1H_PROOF_POLICY, "build_selective_1h_preflight"),
        )
        for policy, preflight_name in cases:
            with self.subTest(policy=policy.mode):
                with patch.object(
                    command,
                    preflight_name,
                    side_effect=AssertionError("proof controller reached a forbidden preflight"),
                ) as preflight:
                    with self.assertRaisesRegex(
                        command.OperationalMemoryFactoryError,
                        r"^FOUR_TOKEN_PROOF_CONTROLLER_REQUIRES_STANDARD_FOUR_HOUR_POLICY$",
                    ):
                        command._run_operational_campaign(
                            policy=policy,
                            operator_approved=True,
                            four_token_proof_controller=controller,
                        )
                preflight.assert_not_called()

    def test_proof_controller_is_forwarded_through_existing_lifecycle_kwargs(self) -> None:
        tree = ast.parse(inspect.getsource(command._run_operational_campaign))
        run_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run_operational"
        ]
        self.assertEqual(len(run_calls), 1)
        lifecycle_keywords = [
            keyword
            for keyword in run_calls[0].keywords
            if keyword.arg == "lifecycle_kwargs"
        ]
        self.assertEqual(len(lifecycle_keywords), 1)
        lifecycle_dict = lifecycle_keywords[0].value
        self.assertIsInstance(lifecycle_dict, ast.Dict)
        propagated = any(
            isinstance(key, ast.Constant)
            and key.value == "four_token_proof_controller"
            and isinstance(value, ast.Name)
            and value.id == "four_token_proof_controller"
            for key, value in zip(lifecycle_dict.keys, lifecycle_dict.values)
        )
        self.assertTrue(
            propagated,
            "private proof controller is not wired into the existing lifecycle kwargs channel",
        )

    def test_factory_has_optional_proof_controller_seam(self) -> None:
        parameter = inspect.signature(factory.run_one_command_15m_factory).parameters.get(
            "four_token_proof_controller"
        )
        self.assertIsNotNone(parameter)
        self.assertEqual(parameter.kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIsNone(parameter.default)

    def test_factory_has_optional_non_invoked_later_cycle_discovery_callback_seam(self) -> None:
        parameter = inspect.signature(
            factory.run_one_command_15m_factory
        ).parameters.get("later_cycle_discovery_callback")

        self.assertIsNotNone(
            parameter,
            "canonical factory must expose optional later-cycle discovery callback seam",
        )
        self.assertEqual(
            parameter.kind,
            inspect.Parameter.KEYWORD_ONLY,
        )
        self.assertIsNone(parameter.default)

        tree = ast.parse(
            inspect.getsource(factory.run_one_command_15m_factory)
        )
        callback_invocations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "later_cycle_discovery_callback"
        ]
        self.assertEqual(
            callback_invocations,
            [],
            "factory callback seam must remain non-invoked at this TDD step",
        )

        for public_runner in (
            command.run_operational_campaign,
            command.run_standard_four_hour_campaign,
            command.run_selective_1h_proof,
        ):
            with self.subTest(public_runner=public_runner.__name__):
                self.assertNotIn(
                    "later_cycle_discovery_callback",
                    inspect.signature(public_runner).parameters,
                )

    def test_private_four_token_capability_persists_exact_multi_cycle_authority(self) -> None:
        now = "2026-08-13T09:00:00+00:00"
        paths = {
            "reports": Path("/tmp/printer-four-token-reports"),
            "lock": Path("/tmp/printer-four-token.lock"),
        }
        preflight = {
            "database_sha256": "0" * 64,
            "database_path": "/tmp/printer-v1.sqlite3",
            "migration_count": 53,
            "latest_migration": "053_test.sql",
            "git_provenance": {"commit": "test"},
        }
        backup = {
            "source_identity": "sha256:" + "0" * 64,
            "backup_hash": "1" * 64,
            "latest_rehearsed_migration": "053_test.sql",
        }
        with patch.object(
            command,
            "build_authorization_marker_payload",
            return_value={"marker": "test"},
        ), patch.object(
            command,
            "create_operational_campaign_graph",
            return_value={"configuration_hash": "test-hash"},
        ) as create_graph:
            command._create_campaign_command(
                execution_id="four-token-test",
                paths=paths,
                preflight=preflight,
                backup=backup,
                now=now,
                operator_approved=True,
                policy=command.STANDARD_FOUR_HOUR_POLICY,
                four_token_proof_controller=object(),
            )

        persisted = create_graph.call_args.kwargs["configuration"]
        expected_multi_cycle = multi_cycle_configuration_contract(
            build_four_token_proof_policy(),
            intake_started_at=datetime.fromisoformat(now),
        )
        self.assertEqual(persisted["token_capacity"], 2)
        self.assertEqual(persisted["ceilings"]["cycle_count"], 2)
        self.assertEqual(persisted["multi_cycle_capacity"], expected_multi_cycle)
        self.assertTrue(persisted["standard_four_hour_campaign"])

    def test_canonical_coordinator_forwards_controller_into_campaign_creation(self) -> None:
        tree = ast.parse(inspect.getsource(command._run_operational_campaign))
        create_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_create_campaign_command"
        ]
        self.assertEqual(len(create_calls), 1)
        controller_keywords = [
            keyword
            for keyword in create_calls[0].keywords
            if keyword.arg == "four_token_proof_controller"
        ]
        self.assertEqual(len(controller_keywords), 1)
        self.assertIsInstance(controller_keywords[0].value, ast.Name)
        self.assertEqual(
            controller_keywords[0].value.id,
            "four_token_proof_controller",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

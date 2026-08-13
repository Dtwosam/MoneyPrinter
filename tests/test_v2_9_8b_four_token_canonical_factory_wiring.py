"""RED contract for the proof-only four-token canonical factory wiring.

This file is intentionally offline/static at this step. It must not start Printer,
perform source work, or mutate an authoritative database.
"""

from __future__ import annotations

import ast
import inspect
import unittest
from unittest.mock import patch

from printer_v1.operator_cli import operational_memory_factory_command as command


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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

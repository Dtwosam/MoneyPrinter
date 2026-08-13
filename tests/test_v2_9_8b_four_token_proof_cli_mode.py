"""Focused contract for the dedicated proof-only four-token CLI mode.

Offline only. No campaign runs here: the canonical coordinator is patched so the
test observes exactly which composition the mode constructs and how many times
it calls the one canonical factory path.
"""

from __future__ import annotations

import inspect
import tempfile
import unittest
from unittest import mock

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli import (
    four_token_proof_one_shot_wrapper as four_token,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    FourTokenProofController,
    build_four_token_proof_policy,
)


class FourTokenProofCliModeTests(unittest.TestCase):
    def test_dedicated_proof_mode_identity(self) -> None:
        self.assertEqual(
            command.FOUR_TOKEN_PROOF_MODE,
            "four-token-bounded-capacity-proof-run",
        )
        self.assertEqual(
            command.FOUR_TOKEN_PROOF_MODE, four_token.AUTHORIZED_COMMAND_MODE
        )
        self.assertIn(
            command.FOUR_TOKEN_PROOF_MODE,
            command.GIT_PROVENANCE_MANIFEST_SUPPORTED_MODES,
        )

    def test_proof_mode_routes_to_the_four_token_profile(self) -> None:
        env = {
            command.GIT_PROVENANCE_MANIFEST_ENV_VARS[0]: "/tmp/manifest.json",
            command.GIT_PROVENANCE_MANIFEST_ENV_VARS[1]: "a" * 64,
            command.GIT_PROVENANCE_MANIFEST_ENV_VARS[2]: "/tmp/marker.json",
            command.GIT_PROVENANCE_MANIFEST_ENV_VARS[3]: "b" * 64,
        }
        sentinel = object()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            command, "validate_git_provenance_authorization", return_value=sentinel
        ) as validator:
            result = command._resolve_git_provenance_authorization(
                command.FOUR_TOKEN_PROOF_MODE, environ=env, repository_root=tmp
            )
        self.assertIs(result, sentinel)
        self.assertEqual(
            validator.call_args.kwargs["profile"],
            git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE,
        )

    def test_proof_policy_derives_from_the_one_scaled_capacity_authority(
        self,
    ) -> None:
        policy = command.FOUR_TOKEN_PROOF_POLICY
        self.assertEqual(policy.mode, command.FOUR_TOKEN_PROOF_MODE)
        self.assertIs(policy.standard_four_hour_campaign, True)
        self.assertEqual(
            policy.duration_seconds, four_token.POST_SUPPLY_PROOF_DURATION_SECONDS
        )
        self.assertEqual(
            policy.pre_lifecycle_acquisition_duration_seconds,
            four_token.PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS,
        )
        self.assertEqual(
            policy.governed_request_ceiling,
            four_token.LIFECYCLE_REQUEST_OUTER_CEILING,
        )
        self.assertEqual(
            policy.scheduler_row_ceiling,
            four_token.LIFECYCLE_SCHEDULER_OUTER_CEILING,
        )
        self.assertEqual(policy.locked_windows, ("WINDOW_12H", "WINDOW_24H"))

    def test_proof_mode_calls_the_one_canonical_factory_path_once(self) -> None:
        authorization = object()
        with mock.patch.object(
            command, "_run_operational_campaign", return_value={"ok": True}
        ) as coordinator:
            result = command.run_four_token_bounded_capacity_proof_campaign(
                operator_approved=True,
                git_provenance_authorization=authorization,
            )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(coordinator.call_count, 1)
        kwargs = coordinator.call_args.kwargs
        self.assertIs(kwargs["policy"], command.FOUR_TOKEN_PROOF_POLICY)
        self.assertIs(kwargs["git_provenance_authorization"], authorization)
        controller = kwargs["four_token_proof_controller"]
        self.assertIsInstance(controller, FourTokenProofController)
        self.assertEqual(controller.policy, build_four_token_proof_policy())

    def test_proof_mode_is_not_a_generic_capacity_selector(self) -> None:
        self.assertEqual(command.TOKEN_CAPACITY, 2)
        signature = inspect.signature(
            command.run_four_token_bounded_capacity_proof_campaign
        )
        for forbidden in (
            "token_capacity",
            "configured_through_4h_tokens",
            "four_token_proof_controller",
            "policy",
        ):
            self.assertNotIn(forbidden, signature.parameters, forbidden)
        for public_runner in (
            command.run_operational_campaign,
            command.run_standard_four_hour_campaign,
            command.run_selective_1h_proof,
        ):
            self.assertNotIn(
                "four_token_proof_controller",
                inspect.signature(public_runner).parameters,
            )

    def test_proof_mode_requires_external_wrapper_authorization(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True), mock.patch.object(
            command,
            "run_four_token_bounded_capacity_proof_campaign",
            side_effect=AssertionError("proof mode ran without wrapper authority"),
        ):
            exit_code = command.main(
                [command.FOUR_TOKEN_PROOF_MODE, "--operator-approved"]
            )
        self.assertNotEqual(exit_code, 0)


if __name__ == "__main__":  # pragma: no cover - direct invocation guard
    unittest.main()
